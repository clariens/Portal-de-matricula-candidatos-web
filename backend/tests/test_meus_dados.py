"""Meus dados: contato, endereço e senha (tela "Meus Dados" do legado, /r/alterarDados; mapeada em DEV em 04/11/2026).

Markup reduzido e fictício do formulário real (frm-pessoa-fisica e frm-altera-senha).
"""

import json

import httpx
import pytest
import respx

from app.core.errors import PortalError
from app.schemas.meus_dados import MeusDadosUpdate
from app.services.lyceum.legado import ClienteLegado, SessoesLegado
from tests.conftest import H

LEG = "https://legado.exemplo/ps"
SID = "sid-dados"

PAGINA = """
<form role="form" id="frm-pessoa-fisica" accept-charset="UTF-8" style="display: none">
  <input type="hidden" name="idPessoa" value="771461"/>
  <input type="text" name="dddFone" id="dddFone" value=""/>
  <input type="text" name="telefone" id="telefone" value=""/>
  <input type="text" name="dddCelular" id="dddCelular" value="34"/>
  <input type="text" name="celular" id="celular" value="991234567"/>
  <input type="text" name="email" id="email" value="ana.rocha@exemplo.com"/>
  <input type="text" name="cep" id="cep" value="38440000"/>
  <input type="hidden" name="enderecoMunicipioCode" value="003104"/>
  <select name="enderecoMunicipio" id="enderecoMunicipio"></select>
  <input type="text" name="endereco" id="endereco" value="Avenida Minas Gerais"/>
  <input type="text" name="enderecoNum" id="enderecoNum" value="1200"/>
  <input type="text" name="enderecoCompl" id="enderecoCompl" value=""/>
  <input type="text" name="enderecoBairro" id="enderecoBairro" value="Centro"/>
  <button type="submit">Salvar</button>
</form>
<form role="form" id="frm-altera-senha" accept-charset="UTF-8" style="display: none">
  <input type="hidden" name="idPessoa" value="771461"/>
  <input type="password" name="senhaAtual" id="senhaAtual"/>
  <input type="password" name="senha" id="senha"/>
  <input type="password" name="senhaRepeticao" id="senhaRepeticao"/>
  <input type="hidden" name="tokenCaptcha" id="tokenCaptcha" value=""/>
  <button type="submit">Salvar</button>
</form>"""
OK = {"lyceumRetorno": {"tipo": "OK", "mensagem": None, "item": None}}


def _cliente(pagina=PAGINA):
    s = SessoesLegado()
    s.criar(SID, httpx.Cookies())
    respx.get(f"{LEG}/r/alterarDados").mock(return_value=httpx.Response(200, text=pagina))
    respx.get(f"{LEG}/endereco/listarMunicipiosCodigo").mock(return_value=httpx.Response(200, json={
        "lyceumRetorno": {"tipo": "OK", "item": [{"codigo": "003104", "nome": "ARAGUARI", "uf": "MG", "cep": "NULL"}]}}))
    return ClienteLegado(LEG, 5, s)


# ---------- legado ----------
@respx.mock
async def test_le_contato_e_endereco_da_pagina():
    d = await _cliente().meus_dados(SID)
    assert (d.email, d.celular, d.telefone) == ("ana.rocha@exemplo.com", "34991234567", None)
    e = d.endereco
    assert (e.cep, e.uf, e.municipio, e.municipio_codigo, e.numero, e.complemento) == (
        "38440-000", "MG", "ARAGUARI", "003104", "1200", None)


@respx.mock
async def test_salva_como_o_formulario_do_legado():
    cl = _cliente()
    rota = respx.post(f"{LEG}/r/alterarDados/alterarPessoaFisica.json").mock(return_value=httpx.Response(200, json=OK))
    dados = MeusDadosUpdate(email="nova@exemplo.com", celular="(34) 98888-7777", telefone="(34) 3241-0000",
                            endereco={"cep": "38440-000", "uf": "MG", "municipio": "ARAGUARI", "municipio_codigo": "003104",
                                      "endereco": "Rua Nova", "numero": "10", "complemento": "Ap 2", "bairro": "Centro"})
    await cl.salvar_meus_dados(SID, dados)
    corpo = json.loads(rota.calls.last.request.content)
    assert corpo == {"idPessoa": "771461", "dddFone": "34", "telefone": "32410000", "dddCelular": "34",
                     "celular": "988887777", "email": "nova@exemplo.com", "cep": "38440-000",
                     "enderecoMunicipioCode": "003104", "enderecoMunicipio": "003104", "endereco": "Rua Nova",
                     "enderecoNum": "10", "enderecoCompl": "Ap 2", "enderecoBairro": "Centro", "tokenCaptcha": None}


@respx.mock
async def test_erro_do_legado_ao_salvar_vira_mensagem():
    cl = _cliente()
    respx.post(f"{LEG}/r/alterarDados/alterarPessoaFisica.json").mock(return_value=httpx.Response(200, json={
        "lyceumRetorno": {"tipo": "ERRO", "mensagem": "E-mail já cadastrado para outra pessoa."}}))
    dados = MeusDadosUpdate(email="x@exemplo.com", celular="34988887777",
                            endereco={"cep": "38440-000", "uf": "MG", "municipio": "ARAGUARI", "municipio_codigo": "003104",
                                      "endereco": "Rua", "numero": "1", "bairro": "Centro"})
    with pytest.raises(PortalError) as e:
        await cl.salvar_meus_dados(SID, dados)
    assert e.value.status == 422 and e.value.mensagem == "E-mail já cadastrado para outra pessoa."


@respx.mock
async def test_troca_a_senha_com_o_id_da_pagina():
    cl = _cliente()
    rota = respx.post(f"{LEG}/r/alterarDados/alterarSenhaPessoa.json").mock(return_value=httpx.Response(200, json=OK))
    await cl.alterar_senha(SID, "atual123", "nova456")
    assert json.loads(rota.calls.last.request.content) == {
        "idPessoa": "771461", "senhaAtual": "atual123", "senha": "nova456", "senhaRepeticao": "nova456",
        "tokenCaptcha": None}


@respx.mock
async def test_troca_de_senha_com_captcha_nao_e_enviada():
    cl = _cliente(PAGINA + '<div id="recaptcha"></div>')
    rota = respx.post(f"{LEG}/r/alterarDados/alterarSenhaPessoa.json")
    with pytest.raises(PortalError) as e:
        await cl.alterar_senha(SID, "atual123", "nova456")
    assert e.value.status == 409 and not rota.called


# ---------- API (dublê) ----------
def test_meus_dados_exige_sessao(client):
    assert client.get("/api/v1/meus-dados").status_code == 401


def test_ler_e_salvar_meus_dados(logged):
    d = logged.get("/api/v1/meus-dados").json()
    assert d["celular"] and d["endereco"]["cep"]
    d.update(email="nova@exemplo.com", celular="(34) 98888-7777")
    r = logged.put("/api/v1/meus-dados", json=d, headers=H)
    assert r.status_code == 200 and (r.json()["email"], r.json()["celular"]) == ("nova@exemplo.com", "34988887777")
    r = logged.put("/api/v1/meus-dados", json={**d, "celular": "349"}, headers=H)
    assert r.status_code == 422 and "celular" in r.json()["erro"]["campos"]


def test_alterar_senha(logged):
    url = "/api/v1/meus-dados/senha"
    r = logged.post(url, json={"senhaAtual": "demonstracao", "novaSenha": "nova123", "confirmacao": "outra"}, headers=H)
    assert r.status_code == 422 and "confirmacao" in r.json()["erro"]["campos"]
    r = logged.post(url, json={"senhaAtual": "errada", "novaSenha": "nova123", "confirmacao": "nova123"}, headers=H)
    assert r.status_code == 422 and r.json()["erro"]["mensagem"] == "Senha atual não confere."
    r = logged.post(url, json={"senhaAtual": "demonstracao", "novaSenha": "nova123", "confirmacao": "nova123"}, headers=H)
    assert r.status_code == 200 and "Senha alterada" in r.json()["mensagem"]
    login = {"login": "123.456.789-09"}
    assert logged.post("/api/v1/auth/login", json={**login, "senha": "demonstracao"}, headers=H).status_code == 401
    assert logged.post("/api/v1/auth/login", json={**login, "senha": "nova123"}, headers=H).status_code == 200
