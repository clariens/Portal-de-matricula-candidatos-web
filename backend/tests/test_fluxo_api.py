import json

from tests.conftest import CANDIDATO_OK, INSC, PDF, H

OBRIGATORIOS = ["05", "04", "03", "02"]


def _upload(c, tipo, veredito="ok", nome="doc.pdf", data=PDF):
    """Anexa como o navegador: guarda o arquivo + selo devolvido (no app, no IndexedDB) para o envio final."""
    ocr = json.dumps({"veredito": veredito, "confianca": 88, "campos": [], "alertas": []})
    r = c.post(f"/api/v1/inscricoes/{INSC}/documentos/{tipo}", files={"arquivo": (nome, data, "application/pdf")},
               data={"ocr": ocr}, headers=H)
    if r.status_code == 200 and r.json().get("selo"):
        c.__dict__.setdefault("guardados", {})[tipo] = (nome, data, r.json()["selo"])
    return r


def _envio(c, trocar=None):
    """Envio final: o navegador devolve cada arquivo guardado com o seu selo."""
    guardados = c.__dict__.get("guardados", {})
    files = [(f"arquivo_{t}", (n, (trocar or {}).get(t, d), "application/pdf")) for t, (n, d, _) in guardados.items()]
    data = {f"selo_{t}": selo for t, (_, _, selo) in guardados.items()}
    return c.post(f"/api/v1/inscricoes/{INSC}/envio-documentos", files=files or None, data=data, headers=H)


def test_login_invalido(client):
    r = client.post("/api/v1/auth/login", json={"login": "123.456.789-09", "senha": "x"}, headers=H)
    assert r.status_code == 401
    assert r.json()["erro"]["mensagem"] == "Usuário ou senha inválidos."


def test_sem_sessao_401(client):
    assert client.get("/api/v1/inscricoes").status_code == 401


def test_csrf_obrigatorio(client):
    r = client.post("/api/v1/auth/login", json={"login": "a@b.com", "senha": "x"})
    assert r.status_code == 403


def test_cookie_httponly(client):
    r = client.post("/api/v1/auth/login", json={"login": "ana.rocha@exemplo.com", "senha": "demonstracao"}, headers=H)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_inscricao_de_terceiro_404(logged):
    assert logged.get("/api/v1/inscricoes/9999999999999/candidato").status_code == 404


def test_historico(logged):
    r = logged.get("/api/v1/inscricoes")
    itens = r.json()
    assert len(itens) == 4
    conv = next(i for i in itens if i["codCandidato"] == INSC)
    assert conv["situacao"] == "Convocado" and conv["acoes"] == ["matricular"]


def test_validacao_por_campo(logged):
    body = {**CANDIDATO_OK, "cpf": "111.111.111-11", "celular": "123",
            "endereco": {**CANDIDATO_OK["endereco"], "cep": "123"}}
    r = logged.put(f"/api/v1/inscricoes/{INSC}/candidato", json=body, headers=H)
    assert r.status_code == 422
    campos = r.json()["erro"]["campos"]
    assert "celular" in campos and "endereco.cep" in campos


def test_cpf_invalido_campo(logged):
    r = logged.put(f"/api/v1/inscricoes/{INSC}/candidato", json={**CANDIDATO_OK, "cpf": "111.111.111-11"}, headers=H)
    assert r.status_code == 422
    assert r.json()["erro"]["campos"] == {"cpf": "CPF inválido. Confira os dígitos."}


def test_upload_rejeita_conteudo_falso(logged):
    r = _upload(logged, "05", data=b"nao sou pdf")
    assert r.status_code == 422


def test_upload_rejeita_extensao(logged):
    r = _upload(logged, "05", nome="doc.exe")
    assert r.status_code == 422


def test_pagamento_exige_documentos(logged):
    logged.put(f"/api/v1/inscricoes/{INSC}/candidato", json=CANDIDATO_OK, headers=H)
    r = logged.post(f"/api/v1/inscricoes/{INSC}/pagamento", json={"tipoResp": "Pessoa", "codigoPlano": "N:PG_PIX:PIX:6"},
                    headers=H)
    assert r.status_code == 409


def test_envio_exige_obrigatorios(logged):
    _upload(logged, "05")
    r = _envio(logged)
    assert r.status_code == 409 and "obrigatórios" in r.json()["erro"]["mensagem"]


def test_envio_recusa_arquivo_trocado_depois_da_conferencia(logged):
    for t in OBRIGATORIOS:
        _upload(logged, t)
    r = _envio(logged, trocar={"05": PDF + b"%outro arquivo"})
    assert r.status_code == 422 and "não é o que foi conferido" in r.json()["erro"]["mensagem"]


def test_envio_recusa_selo_forjado(logged):
    for t in OBRIGATORIOS:
        _upload(logged, t)
    nome, data, _ = logged.guardados["05"]
    logged.guardados["05"] = (nome, data, "selo-inventado")
    assert _envio(logged).status_code == 422


def test_nada_fica_guardado_no_servidor(logged):
    assert _upload(logged, "05").json()["status"] == "anexado"
    st = {d["codigo"]: d["status"] for d in logged.get(f"/api/v1/inscricoes/{INSC}/documentos").json()}
    assert st["05"] == "pendente"  # quem guarda o anexo é o navegador


def test_cartao_indisponivel(logged):
    for t in OBRIGATORIOS:
        _upload(logged, t)
    _envio(logged)
    r = logged.post(f"/api/v1/inscricoes/{INSC}/pagamento", json={"tipoResp": "Pessoa", "codigoPlano": "N:PG_CARTÃO_A:Cartao:6"},
                    headers=H)
    assert r.status_code == 422


def test_responsavel_outra_pessoa_cpf_invalido(logged):
    resp = {"nome": "Maria Rocha", "documento": "000.000.000-00", "dataNascimento": "01/01/1970",
            "email": "maria@exemplo.com", "celular": "34991112222", "endereco": CANDIDATO_OK["endereco"]}
    r = logged.post(f"/api/v1/inscricoes/{INSC}/pagamento",
                    json={"tipoResp": "OutraPessoa", "responsavel": resp, "codigoPlano": "N:PG_PIX:PIX:6"}, headers=H)
    assert r.status_code == 422
    assert "responsavel.documento" in r.json()["erro"]["campos"]


def test_fluxo_completo(logged):
    r = logged.put(f"/api/v1/inscricoes/{INSC}/candidato", json=CANDIDATO_OK, headers=H)
    assert r.status_code == 200 and r.json()["celular"] == "34991234567"

    assert logged.get("/api/v1/enderecos/cep/74215025").json()["municipio"] == "Goiânia"

    for t in OBRIGATORIOS:
        assert _upload(logged, t).json()["status"] == "anexado"  # ainda não foi ao Lyceum
    assert _upload(logged, "11", veredito="divergente").json()["observacao"] == "Será conferido pela secretaria."
    # pagar antes de enviar os documentos é recusado
    assert logged.post(f"/api/v1/inscricoes/{INSC}/pagamento", json={"tipoResp": "Pessoa", "codigoPlano": "N:PG_PIX:PIX:6"},
                       headers=H).status_code == 409
    env = _envio(logged)
    assert env.status_code == 200 and env.json()["simulado"] is False
    st = {d["codigo"]: d["status"] for d in env.json()["documentos"]}
    assert st["05"] == "enviado" and st["11"] == "enviado" and st["01"] == "pendente"

    assert logged.post(f"/api/v1/inscricoes/{INSC}/cupons/validar", json={"codigo": "NAOEXISTE"},
                       headers=H).json()["valido"] is False
    cup = logged.post(f"/api/v1/inscricoes/{INSC}/cupons/validar", json={"codigo": "clariens10"}, headers=H).json()
    assert cup["valido"] and cup["planos"][0]["valorParcela"] == 10332.0

    r = logged.post(f"/api/v1/inscricoes/{INSC}/pagamento", json={"tipoResp": "Pessoa", "codigoPlano": "N:PG_PIX:PIX:6"},
                    headers=H)
    assert r.status_code == 200 and r.json()["situacao"] == "Pré-Matriculado"

    m = logged.get(f"/api/v1/inscricoes/{INSC}/matricula").json()
    assert m["matricula"] == "2716520002" and len(m["disciplinas"]) == 6
    assert m["contrato"]["status"] == "aguardando_assinatura"

    c = logged.post(f"/api/v1/inscricoes/{INSC}/matricula/confirmar", headers=H).json()
    assert c["questionariosPendentes"]

    hist = {i["codCandidato"]: i for i in logged.get("/api/v1/inscricoes").json()}
    assert hist[INSC]["situacao"] == "Pré-Matriculado"
    assert hist[INSC]["acoes"] == ["contrato", "documentos"]

    # depois de pré-matriculado, dados não podem mais ser alterados
    assert logged.put(f"/api/v1/inscricoes/{INSC}/candidato", json=CANDIDATO_OK, headers=H).status_code == 409


def test_logout(logged):
    r = logged.post("/api/v1/auth/logout", headers=H)
    assert r.status_code == 204
    assert logged.get("/api/v1/me").status_code == 401


def test_documento_de_tipo_errado_nao_anexa(logged):
    r = _upload(logged, "05", veredito="tipo_errado")
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"arquivo": "Envie outro arquivo."}
    docs = {d["codigo"]: d["status"] for d in logged.get(f"/api/v1/inscricoes/{INSC}/documentos").json()}
    assert docs["05"] == "pendente"
    # divergente, ilegível e leitura fraca ("erro") podem ir para conferência manual
    for v in ("divergente", "ilegivel", "erro"):
        assert _upload(logged, "05", veredito=v).json()["status"] == "anexado"
