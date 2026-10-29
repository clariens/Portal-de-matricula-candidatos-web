import httpx
import pytest
import respx

from app.config import Settings
from app.core.errors import (
    EndpointNaoMapeado,
    LyceumIndisponivel,
    NaoConfigurado,
    PortalError,
    sanitize_lyceum_error,
)
from app.core.session import sessao_atual
from app.services.lyceum.legado import SessaoLegadoExpirada, parse_historico
from app.services.lyceum.techne import TechneGateway, lyceum_basic_header

BASE = "https://tst-lyceum.exemplo/api"


def _settings(**kw):
    d = {"lyceum_auth_modo": "techne", "lyceum_api_base_url": BASE, "lyceum_api_basic_user": "svc",
             "lyceum_api_basic_password": "pwd", "portal_session_secret": "x"}
    d.update(kw)
    return Settings(_env_file=None, **d)


def test_basic_header():
    assert lyceum_basic_header(_settings()) == "Basic c3ZjOnB3ZA=="


@pytest.mark.parametrize(
    "msg,esperado",
    [
        ("TechneApplicationException: Senha incorreta|detalhe interno", "Senha incorreta"),
        ("Traceback (most recent call last) ...", "Usuário ou senha inválidos."),
        ("Falha no Basic auth", "Usuário ou senha inválidos."),
        (None, "Usuário ou senha inválidos."),
    ],
)
def test_sanitize(msg, esperado):
    assert sanitize_lyceum_error(msg) == esperado


@respx.mock
async def test_autenticar_ok():
    route = respx.post(f"{BASE}/v2/pessoas/autenticacao").mock(return_value=httpx.Response(200, json={
        "codAluno": None, "pessoa": 767919, "login": "12345678909", "name": "Ana Beatriz Rocha",
        "email": "ana@exemplo.com", "cpf": "12345678909"}))
    async with httpx.AsyncClient() as c:
        p = await TechneGateway(_settings(), c).autenticar("123.456.789-09", "s")
    assert p.cod_pessoa == "767919" and p.cpf == "123.456.789-09"
    req = route.calls.last.request
    assert req.headers["authorization"] == "Basic c3ZjOnB3ZA=="
    assert req.headers["content-type"] == "application/json"


@respx.mock
async def test_autenticar_senha_errada():
    respx.post(f"{BASE}/v2/pessoas/autenticacao").mock(return_value=httpx.Response(
        500, json={"status": 401, "message": "TechneApplicationException: Senha inválida|x"}))
    async with httpx.AsyncClient() as c:
        with pytest.raises(PortalError) as e:
            await TechneGateway(_settings(), c).autenticar("a", "b")
    assert e.value.status == 401 and e.value.mensagem == "Senha inválida"


@respx.mock
async def test_autenticar_usuario_dto_real():
    """Formato do UsuarioDTO de DEV: código da pessoa em `id`; `password` nunca vai para o modelo."""
    respx.post(f"{BASE}/v2/pessoas/autenticacao").mock(return_value=httpx.Response(200, json={
        "id": 767919, "codAluno": "2716520002", "login": "2716520002", "name": "Aluno Teste",
        "email": "aluno@exemplo.com", "cpf": "12345678909", "password": "nao-expor", "situacaoAluno": "Ativo"}))
    async with httpx.AsyncClient() as c:
        p = await TechneGateway(_settings(), c).autenticar("2716520002", "s")
    assert p.cod_pessoa == "767919" and p.login == "2716520002"
    assert "nao-expor" not in p.model_dump_json()


@respx.mock
async def test_autenticar_erro_412_formato_dev():
    """Erro real de DEV: HTTP 500 com status interno 412 e texto em titulo/mensagemDetalhada."""
    msg = ("Erro de autenticação: Seu número de matrícula não existe ou foi digitado incorretamente "
           "ou aluno não está ativo.")
    respx.post(f"{BASE}/v2/pessoas/autenticacao").mock(return_value=httpx.Response(
        500, json={"titulo": msg, "status": 412, "timeStamp": 1, "mensagemDetalhada": msg}))
    async with httpx.AsyncClient() as c:
        with pytest.raises(PortalError) as e:
            await TechneGateway(_settings(), c).autenticar("naoexiste99", "x")
    assert e.value.status == 401
    assert e.value.mensagem.startswith("Seu número de matrícula não existe")


@respx.mock
async def test_autenticar_resposta_invalida():
    respx.post(f"{BASE}/v2/pessoas/autenticacao").mock(return_value=httpx.Response(200, json={"foo": 1}))
    async with httpx.AsyncClient() as c:
        with pytest.raises(LyceumIndisponivel):
            await TechneGateway(_settings(), c).autenticar("", "b")


@respx.mock
async def test_autenticar_timeout():
    respx.post(f"{BASE}/v2/pessoas/autenticacao").mock(side_effect=httpx.ConnectTimeout("t"))
    async with httpx.AsyncClient() as c:
        with pytest.raises(LyceumIndisponivel) as e:
            await TechneGateway(_settings(), c).autenticar("a", "b")
    assert e.value.status == 502


async def test_sem_config_503():
    async with httpx.AsyncClient() as c:
        with pytest.raises(NaoConfigurado) as e:
            await TechneGateway(_settings(lyceum_api_basic_user=""), c).autenticar("a", "b")
    assert e.value.status == 503


async def test_endpoint_nao_mapeado_501():
    async with httpx.AsyncClient() as c:
        with pytest.raises(EndpointNaoMapeado) as e:
            await TechneGateway(_settings(), c).listar_inscricoes("1")
    assert e.value.status == 501


# ---------- login de candidato via j_security_check (LYCEUM_AUTH_MODO=legado) ----------
LEG = "https://legado.exemplo/processo-seletivo"
FALHA_HTML = '<input type="hidden" id="msgErro" value="usu&aacute;rio e/ou senha incorretos."/>'
DADOS_HTML = '<input type="hidden" id="idPessoa" name="idPessoa"\n                    value="100001">'


def _legado(**kw):
    return _settings(**{"lyceum_auth_modo": "legado", "lyceum_legado_base_url": LEG, **kw})


def _mock_legado(post_status=303, post_html="", dados_html=DADOS_HTML):
    respx.get(f"{LEG}/r/historico").mock(return_value=httpx.Response(401, text="login"))
    post = respx.post(f"{LEG}/j_security_check").mock(return_value=httpx.Response(
        post_status, text=post_html, headers={"Location": "/processo-seletivo/r/historico"} if post_status == 303 else {}))
    respx.get(f"{LEG}/r/alterarDados").mock(return_value=httpx.Response(200, text=dados_html))
    logout = respx.get(f"{LEG}/logout").mock(return_value=httpx.Response(302))
    return post, logout


@respx.mock
async def test_login_candidato_legado_ok():
    post, logout = _mock_legado()
    respx.get(f"{BASE}/v2/pessoas/idPessoa/100001/obterPessoa").mock(return_value=httpx.Response(200, json={"data": {
        "pessoa": 100001, "nome_compl": "Candidato Teste ", "e_mail": "c@exemplo.com", "cpf": "52998224725",
        "resp_senha": "nao-expor"}}))
    sessao_atual.set("sid-teste")
    async with httpx.AsyncClient() as c:
        gw = TechneGateway(_legado(), c)
        p = await gw.autenticar("52998224725", "s")
    assert (p.cod_pessoa, p.nome, p.cpf, p.login) == ("100001", "Candidato Teste", "529.982.247-25", "52998224725")
    assert "nao-expor" not in p.model_dump_json()
    assert post.calls.last.request.content == b"j_username=52998224725&j_password=s"
    assert not logout.called  # a sessão Java fica aberta (no servidor) para as próximas telas
    gw.legado.sessoes.obter("sid-teste")  # não lança: sessão guardada


@respx.mock
async def test_login_candidato_legado_senha_errada():
    _, logout = _mock_legado(post_status=401, post_html=FALHA_HTML)
    async with httpx.AsyncClient() as c:
        with pytest.raises(PortalError) as e:
            await TechneGateway(_legado(), c).autenticar("00000000191", "x")
    assert e.value.status == 401 and e.value.mensagem == "Usuário e/ou senha incorretos."
    assert not logout.called


@respx.mock
async def test_login_candidato_legado_fora_do_ar():
    respx.get(f"{LEG}/r/historico").mock(side_effect=httpx.ConnectTimeout("t"))
    async with httpx.AsyncClient() as c:
        with pytest.raises(LyceumIndisponivel):
            await TechneGateway(_legado(), c).autenticar("52998224725", "s")


async def test_login_candidato_legado_sem_config():
    async with httpx.AsyncClient() as c:
        with pytest.raises(NaoConfigurado):
            await TechneGateway(_legado(lyceum_legado_base_url=""), c).autenticar("a", "b")


# ---------- histórico legado (/r/historico) ----------
def _linha(cod, opcao, situacao, venc, pag, botoes=""):
    def td(classe, v):
        return f'<td data-title="x" class="txt-center col-data-{classe}">{v}</td>'
    return ("<tr>" + td("cod-inscricao", cod) + td("inscricao", "03/09/2026 00:00:00") + td("opcoes-escolhidas", opcao)
            + td("nome-aluno", "Candidato Teste") + td("unidade", "Centro Universit&aacute;rio Imepac -Araguari<br />")
            + td("agendamento", "-") + td("sala", "-") + td("situacao", situacao) + td("forma-pagamento", "Boleto")
            + td("vencimento-pagamento", venc) + td("status-pagamento", pag) + td("contrato-aceito", "-")
            + f'<td class="th-btn">{botoes}</td></tr>')


HISTORICO_HTML = (
    "<table><thead><tr><th>Código</th></tr></thead><tbody>"
    + _linha("2026200004178", "2026.2 - Processo Seletivo ENEM - IMEPAC - Medicina", "Inscrito", "-", "Cancelado")
    + _linha("2027100000285", "2027.1 - Processo Seletivo ENEM - IMEPAC - Medicina", "Convocado", "08/09/2026", "Pago",
             "<button id=\"btMatricule\" onclick=\"window.location.href='/processo-seletivo/r/ingresso?"
             "codCandidato=2027100000285&codConcurso=1363'\">Matricule-se</button>")
    + _linha("2027100000162", "2027.1 - Processo Seletivo Tradicional - IMEPAC - Medicina", "Pré-Matriculado", "-", "Pendente",
             "<a onclick=\"chamaContrato('2027100000162')\">Contrato</a>"
             "<a href=\"/processo-seletivo/r/documentosPorProcessoCandidato?q=MTM2NHNlcGFyYWRvcmI2NDIwMjcxMDAwMDAxNjI=\">Docs</a>")
    + "</tbody></table>"
)


def test_parse_historico():
    a, b, c = parse_historico(HISTORICO_HTML)
    assert (a.cod_candidato, a.cod_concurso, a.situacao, a.acoes) == ("2026200004178", None, "Inscrito", [])
    assert (a.processo, a.curso, a.data_inscricao, a.vencimento) == (
        "2026.2 - Processo Seletivo ENEM - IMEPAC", "Medicina", "03/09/2026", None)
    assert a.unidade == "Centro Universitário Imepac -Araguari"
    assert (b.cod_concurso, b.situacao, b.acoes, b.status_pagamento) == ("1363", "Convocado", ["matricular"], "Pago")
    assert (c.cod_concurso, c.situacao, c.acoes) == ("1364", "Pré-Matriculado", ["contrato", "documentos"])
    assert "Candidato Teste" not in a.model_dump_json()  # nome do aluno não é exposto


@respx.mock
async def test_historico_e_logout_legado():
    _, logout = _mock_legado()
    respx.get(f"{BASE}/v2/pessoas/idPessoa/100001/obterPessoa").mock(
        return_value=httpx.Response(200, json={"data": {"pessoa": 100001, "nome_compl": "C"}}))
    sessao_atual.set("sid-h")
    async with httpx.AsyncClient() as c:
        gw = TechneGateway(_legado(), c)
        await gw.autenticar("52998224725", "s")
        respx.get(f"{LEG}/r/historico").mock(return_value=httpx.Response(200, text=HISTORICO_HTML))
        itens = await gw.listar_inscricoes("100001")
        assert [i.cod_candidato for i in itens] == ["2026200004178", "2027100000285", "2027100000162"]
        await gw.sair()
        assert logout.called
        with pytest.raises(SessaoLegadoExpirada):
            await gw.listar_inscricoes("100001")


@respx.mock
async def test_sessao_legado_expirada_no_servidor():
    _mock_legado()
    respx.get(f"{BASE}/v2/pessoas/idPessoa/100001/obterPessoa").mock(
        return_value=httpx.Response(200, json={"data": {"pessoa": 100001, "nome_compl": "C"}}))
    sessao_atual.set("sid-x")
    async with httpx.AsyncClient() as c:
        gw = TechneGateway(_legado(), c)
        await gw.autenticar("52998224725", "s")
        respx.get(f"{LEG}/r/historico").mock(return_value=httpx.Response(401, text="login"))  # Tomcat derrubou
        with pytest.raises(PortalError) as e:
            await gw.listar_inscricoes("100001")
    assert e.value.status == 401


def test_sem_configuracao_do_lyceum_o_servidor_nao_inicia():
    # Não existe modo de demonstração: sem o .env o portal recusa iniciar, em vez de subir com dados fictícios
    from app.services.lyceum import build_gateway

    with pytest.raises(RuntimeError, match="LYCEUM_API_BASE_URL"):
        build_gateway(Settings(_env_file=None), httpx.AsyncClient())
