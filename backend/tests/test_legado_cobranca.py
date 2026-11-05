"""Cobrança da 1ª parcela no legado, depois do efetivar.json: boleto (gerarBoleto) e PIX (geraPix).

Formato das respostas tirado dos scripts do legado (terminoIngresso.js e historico.js, DEV, 30/10/2026):
gerarBoleto devolve item[0] = PDF em base64; geraPix devolve item[0] = {tagHtml (QR em <img>), payload, recebedor}.
O botão do PIX da tela de término chama openModalPix(codCandidato, codConcurso, valor, idCobranca).
"""

import base64
import json

import httpx
import pytest
import respx

from app.core.errors import PortalError
from app.services.lyceum.legado import ClienteLegado, SessoesLegado

LEG = "https://legado.exemplo/ps"
SID, CAND, CONC = "sid-cob", "2027100000285", "1363"
PDF = b"%PDF-1.4 boleto\n%%EOF"
PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
TERMINO_HTML = (f"<a id=\"boletoLink\" onclick=\"obtemBoleto()\">Boleto</a>"
                f"<button onclick=\"openModalPix('{CAND}','{CONC}', 1234.56, 998877)\">Pagar com PIX</button>")


def _ok(item):
    return httpx.Response(200, json={"lyceumRetorno": {"tipo": "OK", "item": item}})


def _erro(msg):
    return httpx.Response(200, json={"lyceumRetorno": {"tipo": "ERRO", "mensagem": msg}})


def _cliente(termino=TERMINO_HTML):
    s = SessoesLegado()
    s.criar(SID, httpx.Cookies())
    respx.get(f"{LEG}/r/terminoIngresso").mock(return_value=httpx.Response(200, text=termino))
    respx.get(f"{LEG}/r/historico").mock(return_value=httpx.Response(200, text="<p>Nenhuma cobrança em aberto</p>"))
    return ClienteLegado(LEG, 5, s)


@respx.mock
async def test_boleto_pela_tela_de_termino():
    cl = _cliente()
    termino = respx.get(f"{LEG}/r/terminoIngresso/gerarBoleto").mock(return_value=_ok([base64.b64encode(PDF).decode()]))
    historico = respx.get(f"{LEG}/r/historico/gerarBoleto").mock(return_value=_ok([None]))
    cl.sessoes.obter(SID).aberta = CAND  # a sessão acabou de confirmar esta inscrição
    assert await cl.boleto(SID, CAND, CONC) == PDF
    assert termino.called and not historico.called


@respx.mock
async def test_boleto_de_outra_inscricao_nao_usa_o_termino():
    # a sessão confirmou outra inscrição: o gerarBoleto do término daria o boleto dela
    cl = _cliente()
    cl.sessoes.obter(SID).aberta = "2027100000999"
    termino = respx.get(f"{LEG}/r/terminoIngresso/gerarBoleto").mock(return_value=_ok([base64.b64encode(PDF).decode()]))
    historico = respx.get(f"{LEG}/r/historico/gerarBoleto").mock(return_value=_ok([base64.b64encode(PDF).decode()]))
    assert await cl.boleto(SID, CAND, CONC) == PDF
    assert historico.called and not termino.called
    assert historico.calls.last.request.url.params["codCandidato"] == CAND


@respx.mock
async def test_boleto_pelo_historico_quando_o_termino_nao_tem():
    cl = _cliente(termino="<p>sem término nesta sessão</p>")
    respx.get(f"{LEG}/r/terminoIngresso/gerarBoleto").mock(return_value=_erro("Sessão sem inscrição."))
    historico = respx.get(f"{LEG}/r/historico/gerarBoleto").mock(return_value=_ok([base64.b64encode(PDF).decode()]))
    assert await cl.boleto(SID, CAND, CONC) == PDF
    params = historico.calls.last.request.url.params
    assert (params["codCandidato"], params["codConcurso"]) == (CAND, CONC)


@respx.mock
async def test_boleto_indisponivel():
    cl = _cliente()
    respx.get(f"{LEG}/r/terminoIngresso/gerarBoleto").mock(return_value=_ok([]))
    respx.get(f"{LEG}/r/historico/gerarBoleto").mock(return_value=_ok(["não é base64 de pdf"]))
    with pytest.raises(PortalError) as e:
        await cl.boleto(SID, CAND, CONC)
    assert e.value.status == 409 and "boleto ainda não está disponível" in e.value.mensagem


@respx.mock
async def test_pix_como_a_tela_de_termino():
    cl = _cliente()
    gera = respx.post(f"{LEG}/r/historico/geraPix").mock(return_value=_ok([{
        "tagHtml": f'<img src="data:image/png;base64,{PNG_B64}" width="250"/>',
        "payload": " 00020126580014br.gov.bcb.pix0136abc ", "recebedor": "CLARIENS EDUCACAO"}]))
    pix = await cl.pix(SID, CAND, CONC)
    assert json.loads(gera.calls.last.request.content) == {
        "candidato": CAND, "concurso": CONC, "valorTotal": 1234.56, "listaDeCobrancas": [998877]}
    assert pix.qr_code == f"data:image/png;base64,{PNG_B64}"
    assert pix.copia_e_cola == "00020126580014br.gov.bcb.pix0136abc"
    assert (pix.recebedor, pix.valor) == ("CLARIENS EDUCACAO", 1234.56)


@respx.mock
async def test_pix_com_qr_por_endereco_vira_data_uri():
    cl = _cliente()
    respx.post(f"{LEG}/r/historico/geraPix").mock(return_value=_ok([{
        "tagHtml": "<img src='/processo-seletivo/r/historico/qrcode?id=1'>", "payload": "000201", "recebedor": ""}]))
    respx.get(f"{LEG}/r/historico/qrcode").mock(
        return_value=httpx.Response(200, content=base64.b64decode(PNG_B64), headers={"content-type": "image/png"}))
    pix = await cl.pix(SID, CAND, CONC)
    assert pix.qr_code == f"data:image/png;base64,{PNG_B64}" and pix.recebedor is None


@respx.mock
@pytest.mark.parametrize("tag", [
    "<img src='https://outro-servidor.exemplo/qr.png'>",  # o BFF não busca nada fora do legado
    "<img src='data:image/svg+xml;base64,PHN2Zz48L3N2Zz4='>",  # SVG não chega ao <img> da tela
])
async def test_pix_recusa_qr_de_fora_do_legado_ou_svg(tag):
    cl = _cliente()
    respx.post(f"{LEG}/r/historico/geraPix").mock(return_value=_ok([{"tagHtml": tag, "payload": "000201"}]))
    fora = respx.get("https://outro-servidor.exemplo/qr.png").mock(return_value=httpx.Response(200))
    with pytest.raises(PortalError) as e:
        await cl.pix(SID, CAND, CONC)
    assert e.value.status == 502 and not fora.called


@respx.mock
@pytest.mark.parametrize("termino", [
    "<p>Sem cobrança PIX</p>",  # término sem o botão do PIX (ex.: plano de boleto)
    "<button onclick=\"openModalPix('9999999999999','1363', 10, 1)\">PIX</button>",  # botão de outra inscrição
])
async def test_pix_indisponivel_sem_o_botao_da_inscricao(termino):
    cl = _cliente(termino)
    gera = respx.post(f"{LEG}/r/historico/geraPix").mock(return_value=_ok([]))
    with pytest.raises(PortalError) as e:
        await cl.pix(SID, CAND, CONC)
    assert e.value.status == 409 and not gera.called


@respx.mock
async def test_pix_recusado_pelo_legado():
    cl = _cliente()
    respx.post(f"{LEG}/r/historico/geraPix").mock(return_value=_erro("Cobrança já paga."))
    with pytest.raises(PortalError) as e:
        await cl.pix(SID, CAND, CONC)
    assert e.value.status == 422 and e.value.mensagem == "Cobrança já paga."


# Numa sessão nova o término redireciona; o botão de pagamento do Histórico traz valor e cobrança (DEV, 04/11/2026)
HISTORICO_PAGAMENTO = (f"<button onclick=\"openModalWindown('8553','','13091.00',1,'{CAND}','{CONC}', false, true, "
                       "'Boleto', '3539201', true,'true','35489069');\">Pagar</button>"
                       "<button onclick=\"openModalWindown('51','02','Declaração','Ingresso');\">outro</button>")


@respx.mock
async def test_pix_pelo_historico_numa_sessao_nova():
    s = SessoesLegado()
    s.criar(SID, httpx.Cookies())
    respx.get(f"{LEG}/r/terminoIngresso").mock(return_value=httpx.Response(302, headers={"location": "/ps/r/historico"}))
    respx.get(f"{LEG}/r/historico").mock(return_value=httpx.Response(200, text=HISTORICO_PAGAMENTO))
    gera = respx.post(f"{LEG}/r/historico/geraPix").mock(return_value=_ok([{
        "tagHtml": f'<img src="data:image/png;base64,{PNG_B64}">', "payload": "000201abc", "recebedor": "Imepac"}]))
    pix = await ClienteLegado(LEG, 5, s).pix(SID, CAND, CONC)
    assert json.loads(gera.calls.last.request.content) == {
        "candidato": CAND, "concurso": CONC, "valorTotal": 13091.0, "listaDeCobrancas": [35489069]}
    assert (pix.valor, pix.recebedor) == (13091.0, "Imepac")
