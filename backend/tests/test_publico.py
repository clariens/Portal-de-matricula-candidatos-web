"""Telas públicas: cabeçalho (áreas de interesse) e recuperação de senha pelo legado.

Markup reduzido da home e fluxo de /recuperarsenha observados em 29/10/2026 (DEV e produção, versão 8.2.0).
"""

import json

import httpx
import pytest
import respx

from app.core.errors import LyceumIndisponivel, PortalError
from app.services.lyceum.legado import ClienteLegado, SessoesLegado, parse_cabecalho
from tests.conftest import H

LEG = "https://legado.exemplo/processo-seletivo"
HOME_HTML = """
<ul class="nav navbar-nav">
<li class="dropdown"><a href="#" class="dropdown-toggle custom-anchor-submenu" data-hover="dropdown">Escolha a área do seu
interesse <span class="margem-direita140 caret"></span></a>
<ul class="dropdown-menu drop-top">
<li class="dropdown dropdown-submenu">
<a href="#" class="dropdown-toggle js-activated custom-anchor-submenu"> Graduação</a><span class="right glyphicon"></span>
<ul class="dropdown-menu dropdown-bg">
<li><a href="/processo-seletivo/subgrupo?id=4">Vestibular Tradicional</a>
</li>
<li><a href="/processo-seletivo/subgrupo?id=16">Enem</a>
</li>
</ul>
</li>
</ul></li>
</ul>
<ul class="nav navbar-nav navbar-right">
<li><a href="/processo-seletivo/r/historico">Login </a></li>
<li class="cadastre-se"><a href="/processo-seletivo/cadastro?et=4">Cadastre-se</a></li>
</ul>
"""
OK = {"lyceumRetorno": {"tipo": "OK", "mensagem": "", "item": None}}


def _cliente():
    return ClienteLegado(LEG, 5, SessoesLegado())


def test_parse_cabecalho_da_home():
    cab = parse_cabecalho(HOME_HTML, "https://legado.exemplo")
    assert [a.nome for a in cab.areas] == ["Graduação"]
    assert [(i.nome, i.url) for i in cab.areas[0].itens] == [
        ("Vestibular Tradicional", "https://legado.exemplo/processo-seletivo/subgrupo?id=4"),
        ("Enem", "https://legado.exemplo/processo-seletivo/subgrupo?id=16")]
    assert cab.cadastro_url == "https://legado.exemplo/processo-seletivo/cadastro?et=4"


@respx.mock
async def test_cabecalho_em_cache_e_fallback_com_legado_fora():
    cl = _cliente()
    rota = respx.get(f"{LEG}/home").mock(return_value=httpx.Response(401, text=HOME_HTML))  # sem login: 401 + página
    assert len((await cl.cabecalho()).areas[0].itens) == 2
    await cl.cabecalho()
    assert rota.call_count == 1  # cache
    fora = _cliente()
    caiu = respx.get(f"{LEG}/home").mock(return_value=httpx.Response(502, text="Bad Gateway"))
    antes = caiu.call_count
    cab = await fora.cabecalho()
    await fora.cabecalho()
    assert caiu.call_count - antes == 1  # a reserva também fica em cache: a segunda página não espera o legado
    assert [i.nome for i in cab.areas[0].itens][:3] == ["Vestibular Tradicional", "Transferência Externa", "Enem"]
    assert cab.areas[0].itens[2].url == f"{LEG}/subgrupo?id=16" and cab.cadastro_url == f"{LEG}/cadastro?et=4"


@respx.mock
async def test_recuperar_senha_segue_o_fluxo_do_legado():
    pagina = respx.get(f"{LEG}/recuperarsenha").mock(return_value=httpx.Response(
        200, text="<form id='recuperar-senha'>", headers={"Set-Cookie": "JSESSIONID=anon; Path=/processo-seletivo"}))
    post = respx.post(f"{LEG}/recuperarsenha/recuperar.json").mock(return_value=httpx.Response(200, json=OK))
    respx.get(f"{LEG}/recuperarsenha/sucesso").mock(return_value=httpx.Response(200, json={"lyceumRetorno": {
        "tipo": "OK", "item": ["Um e-mail foi enviado para lu***@gmail.com com as instru&ccedil;&otilde;es."]}}))
    msg = await _cliente().recuperar_senha("52998224725")
    assert pagina.called and json.loads(post.calls.last.request.content) == {"login": "52998224725"}
    assert post.calls.last.request.headers["x-requested-with"] == "XMLHttpRequest"
    assert "JSESSIONID=anon" in post.calls.last.request.headers.get("cookie", "")  # mesma sessão anônima
    assert msg == "Um e-mail foi enviado para lu***@gmail.com com as instruções."


@respx.mock
async def test_recuperar_senha_mostra_a_recusa_do_legado():
    respx.get(f"{LEG}/recuperarsenha").mock(return_value=httpx.Response(200, text="ok"))
    respx.post(f"{LEG}/recuperarsenha/recuperar.json").mock(return_value=httpx.Response(200, json={
        "lyceumRetorno": {"tipo": "ERRO", "mensagem": "Login não encontrado.", "item": None}}))
    with pytest.raises(PortalError) as e:
        await _cliente().recuperar_senha("00000000000")
    assert e.value.status == 422 and e.value.mensagem == "Login não encontrado."


@respx.mock
async def test_recuperar_senha_com_legado_fora():
    respx.get(f"{LEG}/recuperarsenha").mock(side_effect=httpx.ConnectTimeout("fora"))
    with pytest.raises(LyceumIndisponivel):
        await _cliente().recuperar_senha("52998224725")


def test_api_cabecalho_publico(client):
    r = client.get("/api/v1/publico/cabecalho")  # sem login
    assert r.status_code == 200
    assert r.json()["areas"][0]["nome"] == "Graduação" and r.json()["cadastroUrl"].endswith("/cadastro?et=4")


def test_api_recuperar_senha(client):
    r = client.post("/api/v1/auth/recuperar-senha", json={"login": "123.456.789-09"}, headers=H)
    assert r.status_code == 200 and "e-mail" in r.json()["mensagem"]
    r = client.post("/api/v1/auth/recuperar-senha", json={"login": "000.000.000-00"}, headers=H)
    assert r.status_code == 422
    assert client.post("/api/v1/auth/recuperar-senha", json={"login": "x"}, headers=H).status_code == 422
    assert client.post("/api/v1/auth/recuperar-senha", json={"login": "123.456.789-09"}).status_code == 403  # CSRF


@respx.mock
async def test_cabecalho_nao_espera_o_timeout_longo():
    """Legado sem responder: o menu desiste em poucos segundos (não nos 20 s das outras leituras)."""
    from app.services.lyceum import legado

    rota = respx.get(f"{LEG}/home").mock(side_effect=httpx.ReadTimeout("lento"))
    cab = await _cliente().cabecalho()
    assert cab.areas[0].nome == "Graduação"
    assert rota.calls.last.request.extensions["timeout"]["read"] == legado.CABECALHO_TIMEOUT


@respx.mock
async def test_processo_seletivo_fora_do_ar_tem_mensagem_clara():
    """Visto em DEV (29/10/2026): o proxy responde 502 com o Tomcat parado."""
    from app.services.lyceum.legado import MSG_FORA_DO_AR

    respx.get(f"{LEG}/r/historico").mock(return_value=httpx.Response(502, text="Bad Gateway"))
    respx.get(f"{LEG}/recuperarsenha").mock(return_value=httpx.Response(502, text="Bad Gateway"))
    respx.post(f"{LEG}/recuperarsenha/recuperar.json").mock(return_value=httpx.Response(502, text="Bad Gateway"))
    cl = _cliente()
    with pytest.raises(LyceumIndisponivel) as e:
        await cl.login("sid", "52998224725", "s")
    assert e.value.status == 502 and e.value.mensagem == MSG_FORA_DO_AR
    with pytest.raises(LyceumIndisponivel) as e:
        await cl.recuperar_senha("52998224725")
    assert e.value.mensagem == MSG_FORA_DO_AR
