import json

from tests.conftest import CANDIDATO_OK, INSC, PDF, H, ref

OBRIGATORIOS = ["05", "04", "03", "02"]


def _upload(c, tipo, veredito="ok", nome="doc.pdf", data=PDF):
    """Anexa como o navegador: guarda o arquivo + selo devolvido (no app, no IndexedDB) para o envio final."""
    ocr = json.dumps({"veredito": veredito, "confianca": 88, "campos": [], "alertas": []})
    r = c.post(f"/api/v1/inscricoes/{ref(c)}/documentos/{tipo}", files={"arquivo": (nome, data, "application/pdf")},
               data={"ocr": ocr}, headers=H)
    if r.status_code == 200 and r.json().get("selo"):
        c.__dict__.setdefault("guardados", {})[tipo] = (nome, data, r.json()["selo"])
    return r


def _envio(c, trocar=None, tipos=None):
    """Envio final: o navegador devolve cada arquivo guardado com o seu selo (no app, um documento por chamada)."""
    guardados = {t: g for t, g in c.__dict__.get("guardados", {}).items() if tipos is None or t in tipos}
    files = [(f"arquivo_{t}", (n, (trocar or {}).get(t, d), "application/pdf")) for t, (n, d, _) in guardados.items()]
    data = {f"selo_{t}": selo for t, (_, _, selo) in guardados.items()}
    return c.post(f"/api/v1/inscricoes/{ref(c)}/envio-documentos", files=files or None, data=data, headers=H)


def test_login_aceita_cpf_com_ou_sem_pontuacao(client):
    from app.main import app

    # CPF copiado e colado com pontuação: o Lyceum recebe só os dígitos
    for digitado in ("123.456.789-09", " 123.456.789-09 ", "12345678909", "123 456 789 09"):
        r = client.post("/api/v1/auth/login", json={"login": digitado, "senha": "demonstracao"}, headers=H)
        assert r.status_code == 200, digitado
        assert app.state.gateway.ultimo_login == "12345678909"
    # e-mail não é mexido (tem ponto, mas não é CPF)
    r = client.post("/api/v1/auth/login", json={"login": "ana.rocha@exemplo.com", "senha": "demonstracao"}, headers=H)
    assert r.status_code == 200 and app.state.gateway.ultimo_login == "ana.rocha@exemplo.com"
    # recuperar senha também
    client.post("/api/v1/auth/recuperar-senha", json={"login": "123.456.789-09"}, headers=H)
    assert app.state.gateway.ultimo_login == "12345678909"


def test_login_normalizado():
    from app.core.validators import login_normalizado

    assert login_normalizado("092.114.221-83") == "09211422183"
    assert login_normalizado("  09211422183 ") == "09211422183"
    assert login_normalizado("ana.rocha@exemplo.com") == "ana.rocha@exemplo.com"
    assert login_normalizado("12.345.678-9") == "12.345.678-9"  # RG: não tem 11 dígitos, fica como veio
    assert login_normalizado("AB123456") == "AB123456"  # passaporte


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


def test_cookie_em_producao_usa_host_e_secure(monkeypatch):
    from fastapi import Response

    from app.config import Settings
    from app.core.session import SessionUser, set_session
    s = Settings(_env_file=None, portal_session_secret="x" * 40, portal_cookie_secure=True)
    r = Response()
    set_session(r, SessionUser(cod_pessoa="1", login="a", nome="A", sid="s"), s)
    cookie = r.headers["set-cookie"]
    # __Host-: só https, Path=/ e sem Domain, então um subdomínio irmão não consegue plantar outro cookie
    assert cookie.startswith("__Host-portal_session=") and "Secure" in cookie and "Path=/" in cookie
    assert "Domain" not in cookie
    monkeypatch.delenv("PORTAL_COOKIE_SECURE")
    assert Settings(_env_file=None).portal_cookie_secure is True  # esquecer a variável não desliga o Secure


async def test_segredo_curto_nao_sobe(monkeypatch):
    import pytest

    from app import main
    from app.config import Settings
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=None, portal_session_secret="curto-demais"))
    with pytest.raises(RuntimeError, match="pelo menos 32"):
        async with main.lifespan(main.app):
            pass


def test_swagger_fechado_por_padrao(client):
    # PORTAL_API_DOCS não definida (como em produção): sem o mapa da API
    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404


def test_health_nao_consulta_o_lyceum_a_cada_chamada(client, monkeypatch):
    chamadas = []

    async def ping():
        chamadas.append(1)
        return True

    client.app.state.__dict__.pop("saude", None)
    monkeypatch.setattr(client.app.state.gateway, "ping", ping)
    for _ in range(5):
        assert client.get("/api/v1/health").json() == {"status": "ok", "lyceum": True}
    assert len(chamadas) == 1


def test_mensagem_de_configuracao_nao_mostra_variavel():
    from app.core.errors import NaoConfigurado
    e = NaoConfigurado("LYCEUM_API_BASIC_PASSWORD")
    assert e.status == 503 and "LYCEUM" not in e.mensagem


def test_inscricao_de_terceiro_404(logged):
    # sem o segredo do servidor não dá para montar a referência de outra inscrição: qualquer outra é 404
    assert logged.get("/api/v1/inscricoes/" + "A" * 40 + "/candidato").status_code == 404
    from app.config import get_settings
    from app.core.referencia import ref_inscricao
    from app.core.session import SessionUser

    # mesmo com uma referência válida de outra pessoa/sessão, a inscrição não pertence a quem está logado
    alheia = ref_inscricao(get_settings(), SessionUser(cod_pessoa="1", login="x", nome="x", sid="outra"), "9999999999999")
    assert logged.get(f"/api/v1/inscricoes/{alheia}/candidato").status_code == 404


def test_historico(logged):
    r = logged.get("/api/v1/inscricoes")
    itens = r.json()
    assert len(itens) == 4
    conv = next(i for i in itens if i["codCandidato"] == INSC)
    assert conv["situacao"] == "Convocado" and conv["acoes"] == ["matricular"]


def test_validacao_por_campo(logged):
    body = {**CANDIDATO_OK, "cpf": "111.111.111-11", "celular": "123",
            "endereco": {**CANDIDATO_OK["endereco"], "cep": "123"}}
    r = logged.put(f"/api/v1/inscricoes/{ref(logged)}/candidato", json=body, headers=H)
    assert r.status_code == 422
    campos = r.json()["erro"]["campos"]
    assert "celular" in campos and "endereco.cep" in campos


def test_cpf_invalido_campo(logged):
    r = logged.put(f"/api/v1/inscricoes/{ref(logged)}/candidato", json={**CANDIDATO_OK, "cpf": "111.111.111-11"}, headers=H)
    assert r.status_code == 422
    assert r.json()["erro"]["campos"] == {"cpf": "CPF inválido. Confira os dígitos."}


def test_upload_rejeita_conteudo_falso(logged):
    r = _upload(logged, "05", data=b"nao sou pdf")
    assert r.status_code == 422


def test_upload_rejeita_extensao(logged):
    r = _upload(logged, "05", nome="doc.exe")
    assert r.status_code == 422


def _png(largura, altura, modo="1"):
    import io

    from PIL import Image
    b = io.BytesIO()
    Image.new(modo, (largura, altura)).save(b, "PNG")
    return b.getvalue()


def test_upload_recusa_imagem_bomba_sem_decodificar(logged):
    bomba = _png(13000, 13000)  # poucos KB no disco, ~2 GB de memória se fosse decodificada
    assert len(bomba) < 100_000
    r = _upload(logged, "05", nome="rg.png", data=bomba)
    assert r.status_code == 422
    assert r.json()["erro"]["campos"] == {"arquivo": "Resolução grande demais."}


def test_upload_recusa_imagem_que_nao_abre(logged):
    r = _upload(logged, "05", nome="rg.png", data=b"\x89PNG\r\n\x1a\n" + b"lixo" * 50)
    assert r.status_code == 422
    assert r.json()["erro"]["campos"] == {"arquivo": "Imagem inválida."}


def test_preparar_imagem_reduz_sem_estourar():
    import io

    from PIL import Image

    from app.services.imagens import ImagemGrandeDemais, preparar_imagem
    jpg, mime = preparar_imagem(_png(3000, 2000, "P"), 1600)
    assert mime == "image/jpeg" and Image.open(io.BytesIO(jpg)).size == (1600, 1067)
    try:
        preparar_imagem(_png(13000, 13000), 1600)
        raise AssertionError("deveria recusar")
    except ImagemGrandeDemais:
        pass


def test_pagamento_exige_documentos(logged):
    logged.put(f"/api/v1/inscricoes/{ref(logged)}/candidato", json=CANDIDATO_OK, headers=H)
    r = logged.post(f"/api/v1/inscricoes/{ref(logged)}/pagamento", json={"tipoResp": "Pessoa", "codigoPlano": "N:PG_PIX:PIX:6"},
                    headers=H)
    assert r.status_code == 409


def test_envio_um_documento_por_vez_e_pagamento_so_com_todos_os_obrigatorios(logged):
    def pagar():
        return logged.post(f"/api/v1/inscricoes/{ref(logged)}/pagamento",
                           json={"tipoResp": "Pessoa", "codigoPlano": "N:PG_PIX:PIX:6"}, headers=H)

    for t in OBRIGATORIOS:
        _upload(logged, t)
    r = _envio(logged, tipos=["05"])  # como o navegador: um documento por chamada
    st = {d["codigo"]: d["status"] for d in r.json()["documentos"]}
    assert r.status_code == 200 and st["05"] == "enviado" and st["04"] == "pendente"
    assert "obrigatórios" in pagar().json()["erro"]["mensagem"]  # ainda faltam obrigatórios
    for t in OBRIGATORIOS[1:]:
        assert _envio(logged, tipos=[t]).status_code == 200
    assert "obrigatórios" not in (pagar().json().get("erro") or {}).get("mensagem", "")


def test_envio_recusa_arquivo_trocado_depois_da_conferencia(logged):
    for t in OBRIGATORIOS:
        _upload(logged, t)
    r = _envio(logged, trocar={"05": PDF + b"%outro arquivo"}, tipos=["05"])
    erro = r.json()["erro"]
    assert r.status_code == 422 and "não é o que foi conferido" in erro["mensagem"]
    # diz qual documento foi recusado: no texto e marcado pelo código (a tela destaca a linha)
    assert erro["mensagem"].startswith("CPF não foi enviado.") and set(erro["campos"]) == {"05"}


def test_opcional_recusado_nao_impede_o_envio_dos_outros(logged):
    for t in [*OBRIGATORIOS, "14"]:
        _upload(logged, t)
    r = _envio(logged, trocar={"14": PDF + b"%outro arquivo"})
    assert r.status_code == 200
    corpo = r.json()
    assert set(corpo["recusados"]) == {"14"} and "não é o que foi conferido" in corpo["recusados"]["14"]
    assert corpo["mensagem"] == "Documentos enviados, exceto: Cartão de Vacina. Troque esses arquivos e envie de novo."
    st = {d["codigo"]: d["status"] for d in corpo["documentos"]}
    assert all(st[t] == "enviado" for t in OBRIGATORIOS) and st["14"] == "pendente"


def test_envio_recusa_selo_forjado(logged):
    for t in OBRIGATORIOS:
        _upload(logged, t)
    nome, data, _ = logged.guardados["05"]
    logged.guardados["05"] = (nome, data, "selo-inventado")
    assert _envio(logged, tipos=["05"]).status_code == 422


def test_nada_fica_guardado_no_servidor(logged):
    assert _upload(logged, "05").json()["status"] == "anexado"
    st = {d["codigo"]: d["status"] for d in logged.get(f"/api/v1/inscricoes/{ref(logged)}/documentos").json()}
    assert st["05"] == "pendente"  # quem guarda o anexo é o navegador


def test_cartao_indisponivel(logged):
    for t in OBRIGATORIOS:
        _upload(logged, t)
    _envio(logged)
    r = logged.post(f"/api/v1/inscricoes/{ref(logged)}/pagamento", json={"tipoResp": "Pessoa", "codigoPlano": "N:PG_CARTÃO_A:Cartao:6"},
                    headers=H)
    assert r.status_code == 422


def test_responsavel_outra_pessoa_cpf_invalido(logged):
    resp = {"nome": "Maria Rocha", "documento": "000.000.000-00", "dataNascimento": "01/01/1970",
            "email": "maria@exemplo.com", "celular": "34991112222", "endereco": CANDIDATO_OK["endereco"]}
    r = logged.post(f"/api/v1/inscricoes/{ref(logged)}/pagamento",
                    json={"tipoResp": "OutraPessoa", "responsavel": resp, "codigoPlano": "N:PG_PIX:PIX:6"}, headers=H)
    assert r.status_code == 422
    assert "responsavel.documento" in r.json()["erro"]["campos"]


def test_fluxo_completo(logged):
    r = logged.put(f"/api/v1/inscricoes/{ref(logged)}/candidato", json=CANDIDATO_OK, headers=H)
    assert r.status_code == 200 and r.json()["celular"] == "34991234567"

    assert logged.get("/api/v1/enderecos/cep/74215025").json()["municipio"] == "Goiânia"

    for t in OBRIGATORIOS:
        assert _upload(logged, t).json()["status"] == "anexado"  # ainda não foi ao Lyceum
    assert _upload(logged, "11", veredito="divergente").json()["observacao"] == "Será conferido pela secretaria."
    # pagar antes de enviar os documentos é recusado
    assert logged.post(f"/api/v1/inscricoes/{ref(logged)}/pagamento", json={"tipoResp": "Pessoa", "codigoPlano": "N:PG_PIX:PIX:6"},
                       headers=H).status_code == 409
    env = _envio(logged)
    assert env.status_code == 200 and env.json()["simulado"] is False
    st = {d["codigo"]: d["status"] for d in env.json()["documentos"]}
    assert st["05"] == "enviado" and st["11"] == "enviado" and st["01"] == "pendente"

    assert logged.post(f"/api/v1/inscricoes/{ref(logged)}/cupons/validar", json={"codigo": "NAOEXISTE"},
                       headers=H).json()["valido"] is False
    cup = logged.post(f"/api/v1/inscricoes/{ref(logged)}/cupons/validar", json={"codigo": "clariens10"}, headers=H).json()
    assert cup["valido"] and cup["planos"][0]["valorParcela"] == 10332.0

    # boleto e PIX só existem depois de confirmar o pagamento
    assert logged.get(f"/api/v1/inscricoes/{ref(logged)}/pagamento/boleto").status_code == 409
    assert logged.post(f"/api/v1/inscricoes/{ref(logged)}/pagamento/pix", headers=H).status_code == 409
    r = logged.post(f"/api/v1/inscricoes/{ref(logged)}/pagamento", json={"tipoResp": "Pessoa", "codigoPlano": "N:PG_PIX:PIX:6"},
                    headers=H)
    assert r.status_code == 200 and r.json()["situacao"] == "Pré-Matriculado"
    # depois de confirmar: PIX (QR + copia e cola) e boleto em PDF
    pix = logged.post(f"/api/v1/inscricoes/{ref(logged)}/pagamento/pix", headers=H).json()
    assert pix["qrCode"].startswith("data:image/png;base64,") and pix["copiaECola"].startswith("000201")
    assert pix["recebedor"] and pix["valor"] == 1234.5
    bol = logged.get(f"/api/v1/inscricoes/{ref(logged)}/pagamento/boleto")
    assert bol.status_code == 200 and bol.content.startswith(b"%PDF") and bol.headers["content-type"] == "application/pdf"
    assert bol.headers["cache-control"] == "private, no-store"

    m = logged.get(f"/api/v1/inscricoes/{ref(logged)}/matricula").json()
    assert m["matricula"] == "2716520002" and len(m["disciplinas"]) == 6
    assert m["contrato"]["status"] == "aguardando_assinatura"

    c = logged.post(f"/api/v1/inscricoes/{ref(logged)}/matricula/confirmar", headers=H).json()
    assert c["questionariosPendentes"]

    hist = {i["codCandidato"]: i for i in logged.get("/api/v1/inscricoes").json()}
    assert hist[INSC]["situacao"] == "Pré-Matriculado"
    assert hist[INSC]["acoes"] == ["contrato", "documentos"]

    # depois de pré-matriculado, dados não podem mais ser alterados
    assert logged.put(f"/api/v1/inscricoes/{ref(logged)}/candidato", json=CANDIDATO_OK, headers=H).status_code == 409


def test_logout(logged):
    r = logged.post("/api/v1/auth/logout", headers=H)
    assert r.status_code == 204
    me = logged.get("/api/v1/me")
    assert me.status_code == 200 and me.json() is None  # sem sessão: não é erro
    assert logged.get("/api/v1/inscricoes").status_code == 401  # rotas protegidas continuam 401


def test_me_sem_login_nao_e_erro(client):
    r = client.get("/api/v1/me")
    assert r.status_code == 200 and r.json() is None


def test_documento_de_tipo_errado_nao_anexa(logged):
    r = _upload(logged, "05", veredito="tipo_errado")
    assert r.status_code == 422 and r.json()["erro"]["campos"] == {"arquivo": "Envie outro arquivo."}
    docs = {d["codigo"]: d["status"] for d in logged.get(f"/api/v1/inscricoes/{ref(logged)}/documentos").json()}
    assert docs["05"] == "pendente"
    # divergente, ilegível e leitura fraca ("erro") podem ir para conferência manual
    for v in ("divergente", "ilegivel", "erro"):
        assert _upload(logged, "05", veredito=v).json()["status"] == "anexado"


def test_url_nao_leva_o_numero_da_inscricao(logged):
    itens = logged.get("/api/v1/inscricoes").json()
    r = next(i["ref"] for i in itens if i["codCandidato"] == INSC)
    assert INSC not in r and len(r) >= 20
    assert logged.get(f"/api/v1/inscricoes/{r}").json()["codCandidato"] == INSC
    assert logged.get(f"/api/v1/inscricoes/{INSC}").status_code in (404, 422)  # número na URL não abre nada


def test_ref_de_outra_sessao_nao_vale(client):
    from tests.conftest import H as HH

    login = {"login": "123.456.789-09", "senha": "demonstracao"}
    client.post("/api/v1/auth/login", json=login, headers=HH)
    r = next(i["ref"] for i in client.get("/api/v1/inscricoes").json() if i["codCandidato"] == INSC)
    client.post("/api/v1/auth/logout", headers=HH)
    client.post("/api/v1/auth/login", json=login, headers=HH)  # nova sessão: outra referência
    assert client.get(f"/api/v1/inscricoes/{r}").status_code == 404
    novo = next(i["ref"] for i in client.get("/api/v1/inscricoes").json() if i["codCandidato"] == INSC)
    assert novo != r and client.get(f"/api/v1/inscricoes/{novo}").status_code == 200


def test_previa_do_documento_enviado(logged):
    _upload(logged, "05")
    assert _envio(logged, tipos=["05"]).status_code == 200
    r = logged.get(f"/api/v1/inscricoes/{ref(logged)}/documentos/05/arquivo")
    assert r.status_code == 200 and r.content == PDF and r.headers["content-type"] == "application/pdf"
    assert r.headers["cache-control"] == "private, no-store" and r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-disposition"] == 'inline; filename="documento-05.pdf"'
    # não enviado ainda (ou o Lyceum sem o arquivo): 404 com aviso
    r = logged.get(f"/api/v1/inscricoes/{ref(logged)}/documentos/04/arquivo")
    assert r.status_code == 404 and r.json()["erro"]["mensagem"] == "Prévia indisponível."
    # de outra inscrição (referência forjada): 404
    assert logged.get("/api/v1/inscricoes/" + "A" * 40 + "/documentos/05/arquivo").status_code == 404


def test_corpo_grande_demais_e_recusado_antes_de_ler(logged):
    from app.config import get_settings
    limite = (get_settings().portal_upload_max_mb + 1) * 1024 * 1024
    r = logged.post(f"/api/v1/inscricoes/{ref(logged)}/documentos/05", content=b"x" * (limite + 1),
                    headers={**H, "Content-Type": "multipart/form-data; boundary=b"})
    assert r.status_code == 413 and r.json()["erro"]["campos"] == {"arquivo": "Arquivo grande demais."}


def test_analise_do_navegador_nunca_vira_da_ia(logged):
    ocr = json.dumps({"veredito": "ok", "confianca": 99, "campos": [], "alertas": [], "fonte": "ia"})
    r = logged.post(f"/api/v1/inscricoes/{ref(logged)}/documentos/05",
                    files={"arquivo": ("doc.pdf", PDF, "application/pdf")}, data={"ocr": ocr}, headers=H)
    assert r.status_code == 200 and r.json()["analise"]["fonte"] == "navegador"
