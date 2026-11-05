"""Etapa Pagamento no legado: planos da página real, cupom e corpo de /r/pagamentoIngresso/efetivar.json.

Markup reduzido de /r/pagamentoIngresso observado em DEV (22/10/2026), com dados fictícios.
"""

import json

import httpx
import pytest
import respx

from app.core.errors import PortalError
from app.schemas.pagamento import PagamentoIn
from app.services.lyceum.legado import ClienteLegado, SessoesLegado, parse_pagamento

LEG = "https://legado.exemplo/ps"
SID, CAND, CONC = "sid-pag", "2027100000285", "1363"

PAGAMENTO_HTML = """
<form role="form" id="frm-pagamento">
  <label for="tipoResp"> <input name="tipoResp" type="radio" id="tipoRespAluno" value="Pessoa"
      onclick="javascript:void(0);" /> Própria Pessoa</label>
  <label for="tipoResp"> <input name="tipoResp" type="radio" id="tipoRespOutraPessoa"
    value="OutraPessoa" onclick="javascript:void(0);" /> Outra Pessoa Física</label>
  <label for="tipoResp"> <input name="tipoResp" type="radio" id="tipoRespEmpresa"
    value="Empresa" onclick="javascript:void(0);" /> Empresa</label>
  <select id="planoPagamento" id="type" class="form-control">
    <option value="" disabled selected>Escolha uma forma de pagamento</option>
    <option
        value="N:PG_BOLETO:Boleto:6">Boleto:
        A modalidade de pagamento com Boleto será aplicado 5% de desconto a partir da 1ª mensalidade.</option>
     <option
        value="N:PG_CART&Atilde;O_A:Cartao:6">Cartao:
        A modalidade de pagamento com Cartão será aplicado desconto de 5% na 1ª mensalidade.</option>
     <option
        value="N:PG_PIX:PIX:6">PIX:
        A modalidade de pagamento com PIX será aplicado 5% de desconto a partir da 1ª mensalidade.</option>
  </select> <input type="hidden" id="planoPadrao" name="planoPadrao" />
</form>
<input type="hidden" id="verificafraudeInput" name="verificafraudeInput"
value="N" />
"""
OK = {"lyceumRetorno": {"tipo": "OK", "mensagem": "", "item": None}}
ENDERECO = {"cep": "38440000", "uf": "MG", "municipio": "Araguari", "municipioCodigo": "003105",
            "endereco": "Rua <b>A</b>", "numero": "10", "bairro": "Centro"}


def _cliente(paginas=(PAGAMENTO_HTML,)):
    s = SessoesLegado()
    s.criar(SID, httpx.Cookies())
    respx.get(f"{LEG}/r/pagamentoIngresso").mock(
        side_effect=[httpx.Response(200, text=p) if p else httpx.Response(302, headers={"location": "/ps/r/historico"})
                     for p in paginas])
    respx.get(f"{LEG}/r/documentosPorProcesso").mock(return_value=httpx.Response(200, text="<p>docs</p>"))
    return ClienteLegado(LEG, 5, s)


def test_parse_planos_da_pagina_real():
    p = parse_pagamento(PAGAMENTO_HTML)
    assert [x.codigo for x in p.planos] == ["N:PG_BOLETO:Boleto:6", "N:PG_CARTÃO_A:Cartao:6", "N:PG_PIX:PIX:6"]
    boleto, cartao, pix = p.planos
    assert boleto.forma_pagamento == "Boleto" and boleto.num_parcelas == 6 and boleto.valor_parcela is None
    assert boleto.descricao.startswith("A modalidade de pagamento com Boleto será aplicado 5%")
    assert cartao.forma_pagamento == "Cartao" and not cartao.disponivel
    assert pix.disponivel and pix.tag
    assert p.tipos_responsavel == ["Pessoa", "OutraPessoa", "Empresa"]


@respx.mock
async def test_pagina_reabre_documentos_antes_de_desistir():
    cl = _cliente((None, PAGAMENTO_HTML))
    op = await cl.opcoes_pagamento(SID, CAND, CONC)
    assert len(op.planos) == 3 and respx.calls.call_count == 3  # pagamento → documentos → pagamento


@respx.mock
async def test_pagina_fechada_pede_para_confirmar_dados():
    cl = _cliente((None, None))
    with pytest.raises(PortalError) as e:
        await cl.opcoes_pagamento(SID, CAND, CONC)
    assert e.value.status == 409 and "Confirme seus dados" in e.value.mensagem


@respx.mock
@pytest.mark.parametrize(("item", "valido", "trecho"), [
    ([{"descPercValor": "Percentual", "desconto": 10}], True, "10% de desconto"),
    ([{"descPercValor": "Valor", "desconto": 150.5}], True, "R$ 150,50"),
    (None, False, "não encontrado"),
])
async def test_cupom_validado_no_legado(item, valido, trecho):
    cl = _cliente()
    rota = respx.post(f"{LEG}/r/pagamentoIngresso/validarvoucher").mock(return_value=httpx.Response(
        200, json={"lyceumRetorno": {"tipo": "OK" if item else "ERRO", "mensagem": "", "item": item}}))
    r = await cl.validar_cupom(SID, CAND, CONC, "PROMO10")
    assert r.valido is valido and trecho in r.mensagem
    assert rota.calls.last.request.content == b"voucher=PROMO10"


@respx.mock
async def test_efetivar_simulado_nao_chama_o_lyceum():
    cl = _cliente()
    rota = respx.post(f"{LEG}/r/pagamentoIngresso/efetivar.json").mock(return_value=httpx.Response(200, json=OK))
    r = await cl.efetivar_pagamento(SID, CAND, CONC, PagamentoIn(tipo_resp="Pessoa", codigo_plano="N:PG_PIX:PIX:6"),
                                    simular=True)
    assert r.simulado and not rota.called and r.cobranca.forma_pagamento == "PIX"


@respx.mock
async def test_efetivar_real_pessoa_monta_corpo_igual_ao_form():
    cl = _cliente()
    rota = respx.post(f"{LEG}/r/pagamentoIngresso/efetivar.json").mock(return_value=httpx.Response(200, json=OK))
    r = await cl.efetivar_pagamento(
        SID, CAND, CONC, PagamentoIn(tipo_resp="Pessoa", codigo_plano="N:PG_BOLETO:Boleto:6", voucher=""), simular=False)
    assert not r.simulado and r.situacao == "Pré-Matriculado"
    corpo = json.loads(rota.calls.last.request.content)
    assert corpo == {"tipoResp": "Pessoa", "voucher": None, "planoPadrao": "N", "codigoPlano": "PG_BOLETO",
                     "formaPagamento": "Boleto", "numParcelas": "6", "numeroCartao": None, "titularCartao": None,
                     "mesValidadeCartao": None, "anoValidadeCartao": None, "codSegurancaCartao": None,
                     "docPortadorCartao": None}
    assert cl.sessoes.obter(SID).etapas.get(CAND) == "conclusao"


@respx.mock
async def test_efetivar_real_outra_pessoa():
    cl = _cliente()
    rota = respx.post(f"{LEG}/r/pagamentoIngresso/efetivar.json").mock(return_value=httpx.Response(200, json=OK))
    resp = {"nome": "Maria Rocha", "documento": "52998224725", "dataNascimento": "1/2/1970", "sexo": "F",
            "estadoCivil": "Casado", "email": "maria@exemplo.com", "celular": "(34) 99111-2222",
            "telefone": "34 3241-0000", "endereco": ENDERECO}
    dados = PagamentoIn.model_validate({"tipoResp": "OutraPessoa", "responsavel": resp,
                                        "codigoPlano": "N:PG_PIX:PIX:6"})
    await cl.efetivar_pagamento(SID, CAND, CONC, dados, simular=False)
    c = json.loads(rota.calls.last.request.content)
    assert c["cpf"] == "529.982.247-25" and c["titular"] == "Maria Rocha" and c["dataNascimento"] == "01/02/1970"
    assert (c["dddCelular"], c["celular"], c["dddFone"], c["fone"]) == ("34", "991112222", "34", "32410000")
    assert c["cep"] == "38440-000" and c["enderecoMunicipio"] == "003105" and c["endereco"] == "Rua A"
    assert c["passaporte"] is None and "cnpj" not in c


@respx.mock
async def test_efetivar_real_empresa():
    cl = _cliente()
    rota = respx.post(f"{LEG}/r/pagamentoIngresso/efetivar.json").mock(return_value=httpx.Response(200, json=OK))
    resp = {"nome": "Empresa Exemplo Ltda", "documento": "11222333000181", "inscricaoEstadual": "123",
            "endereco": ENDERECO}
    dados = PagamentoIn.model_validate({"tipoResp": "Empresa", "responsavel": resp,
                                        "codigoPlano": "N:PG_BOLETO:Boleto:6"})
    await cl.efetivar_pagamento(SID, CAND, CONC, dados, simular=False)
    c = json.loads(rota.calls.last.request.content)
    assert c["cnpj"] == "11.222.333/0001-81" and c["inscrEstadual"] == "123" and c["inscrMunicipal"] is None
    assert "cpf" not in c and "email" not in c


@respx.mock
async def test_efetivar_recusa_cartao_e_plano_desconhecido():
    cl = _cliente((PAGAMENTO_HTML, PAGAMENTO_HTML))
    for codigo in ("N:PG_CARTÃO_A:Cartao:6", "N:OUTRO:PIX:1"):
        with pytest.raises(PortalError) as e:
            await cl.efetivar_pagamento(SID, CAND, CONC, PagamentoIn(tipo_resp="Pessoa", codigo_plano=codigo),
                                        simular=False)
        assert e.value.status == 422


@respx.mock
async def test_efetivar_recusado_pelo_lyceum_mostra_a_mensagem():
    cl = _cliente()
    respx.post(f"{LEG}/r/pagamentoIngresso/efetivar.json").mock(return_value=httpx.Response(
        200, json={"lyceumRetorno": {"tipo": "ERRO", "mensagem": "Plano não disponível para o curso.", "item": None}}))
    with pytest.raises(PortalError) as e:
        await cl.efetivar_pagamento(SID, CAND, CONC, PagamentoIn(tipo_resp="Pessoa", codigo_plano="N:PG_PIX:PIX:6"),
                                    simular=False)
    assert e.value.mensagem == "Plano não disponível para o curso."


def test_responsavel_outra_pessoa_exige_campos_do_legado():
    with pytest.raises(ValueError, match=r"responsavel.sexo"):
        PagamentoIn.model_validate({"tipoResp": "OutraPessoa", "codigoPlano": "N:PG_PIX:PIX:6", "responsavel": {
            "nome": "Maria Rocha", "documento": "52998224725", "dataNascimento": "01/02/1970",
            "endereco": ENDERECO}})


# ---------- efetivar.json demorado (DEV, 04/11/2026: o legado criou a matrícula depois de mais de 20 s) ----------
@respx.mock
@pytest.mark.parametrize("situacao_depois,gravou", [("Pré-Matriculado", True), ("Convocado", False)])
async def test_efetivar_sem_resposta_confere_no_historico(situacao_depois, gravou):
    from tests.test_techne import _linha

    cl = _cliente()
    rota = respx.post(f"{LEG}/r/pagamentoIngresso/efetivar.json").mock(side_effect=httpx.ReadTimeout("demorou"))
    respx.get(f"{LEG}/r/historico").mock(return_value=httpx.Response(200, text=(
        "<table><tbody>" + _linha(CAND, "2027.1 - Processo Seletivo ENEM - IMEPAC - Medicina", situacao_depois,
                                  "05/11/2026", "Em Aberto") + "</tbody></table>")))
    dados = PagamentoIn(tipo_resp="Pessoa", codigo_plano="N:PG_PIX:PIX:6")
    if gravou:
        r = await cl.efetivar_pagamento(SID, CAND, CONC, dados, simular=False)
        assert r.situacao == "Pré-Matriculado" and cl.sessoes.obter(SID).etapas.get(CAND) == "conclusao"
        assert CAND not in cl.sessoes.obter(SID).pagando
    else:
        # o legado pode ainda estar gravando: avisa que está em processamento e trava uma nova confirmação
        for _ in range(2):
            with pytest.raises(PortalError) as e:
                await cl.efetivar_pagamento(SID, CAND, CONC, dados, simular=False)
            assert e.value.status == 409 and "Não confirme de novo" in e.value.mensagem
    assert rota.call_count == 1  # nunca reenvia (nem sozinho nem por um novo clique): duplicaria a cobrança


@respx.mock
async def test_recusa_do_lyceum_nao_trava_nova_tentativa():
    cl = _cliente(paginas=(PAGAMENTO_HTML, PAGAMENTO_HTML))
    rota = respx.post(f"{LEG}/r/pagamentoIngresso/efetivar.json").mock(side_effect=[httpx.Response(
        200, json={"lyceumRetorno": {"tipo": "ERRO", "mensagem": "Plano não disponível.", "item": None}}),
        httpx.Response(200, json=OK)])
    dados = PagamentoIn(tipo_resp="Pessoa", codigo_plano="N:PG_PIX:PIX:6")
    with pytest.raises(PortalError):
        await cl.efetivar_pagamento(SID, CAND, CONC, dados, simular=False)
    r = await cl.efetivar_pagamento(SID, CAND, CONC, dados, simular=False)  # resposta definitiva: pode tentar de novo
    assert r.situacao == "Pré-Matriculado" and rota.call_count == 2


def test_prazos_cabem_no_limite_da_funcao_na_vercel():
    import pathlib

    from app.services.lyceum import legado
    vercel = json.loads((pathlib.Path(__file__).parents[2] / "vercel.json").read_text(encoding="utf-8"))
    limite = vercel["services"]["bff"]["functions"]["app/main.py"]["maxDuration"]
    assert legado.EFETIVAR_TIMEOUT <= limite - 15 and legado.UPLOAD_TIMEOUT <= limite - 15


@respx.mock
async def test_com_outra_inscricao_aberta_reabre_a_certa_antes_de_pagar():
    # duas inscrições em duas abas: o legado ficou com a outra aberta (último /r/ingresso)
    cl = _cliente()
    cl.sessoes.obter(SID).aberta = "2027100000999"
    ingresso = respx.get(f"{LEG}/r/ingresso").mock(return_value=httpx.Response(200, text=(
        f'<form id="form-candidato"><input type="hidden" name="codCandidato" value="{CAND}"/></form>')))
    rota = respx.post(f"{LEG}/r/pagamentoIngresso/efetivar.json").mock(return_value=httpx.Response(200, json=OK))
    await cl.efetivar_pagamento(SID, CAND, CONC, PagamentoIn(tipo_resp="Pessoa", codigo_plano="N:PG_PIX:PIX:6"),
                                simular=False)
    assert ingresso.calls.last.request.url.params["codCandidato"] == CAND
    assert ingresso.calls.last.request.url.params["codConcurso"] == CONC
    assert rota.called and cl.sessoes.obter(SID).aberta == CAND


@respx.mock
async def test_se_o_legado_nao_reabrir_nada_e_gravado():
    cl = _cliente()
    cl.sessoes.obter(SID).aberta = "2027100000999"
    respx.get(f"{LEG}/r/ingresso").mock(return_value=httpx.Response(302, headers={"location": "/ps/r/historico"}))
    rota = respx.post(f"{LEG}/r/pagamentoIngresso/efetivar.json").mock(return_value=httpx.Response(200, json=OK))
    with pytest.raises(PortalError) as e:
        await cl.efetivar_pagamento(SID, CAND, CONC, PagamentoIn(tipo_resp="Pessoa", codigo_plano="N:PG_PIX:PIX:6"),
                                    simular=False)
    assert e.value.status == 409 and not rota.called
