"""Depois do pagamento (Pré-Matriculado): matrícula e instruções do contrato, documentos em consulta.

Mapeado em DEV em 04/11/2026 com uma conta de teste pré-matriculada: o histórico traz chamaContrato('<código do
aluno>'), que chama GET r/contrato/geraContratoAceite?codigoAluno= e abre /r/contrato (instruções de assinatura
pela Clicksign em #contrato_id). O botão Documentos abre a tela "Documentos Ingresso". Markup reduzido, fictício.
"""

import httpx
import respx

from app.schemas.inscricao import Inscricao
from app.services.lyceum.legado import (
    ClienteLegado,
    SessoesLegado,
    parse_historico,
    parse_instrucoes_contrato,
)

LEG = "https://legado.exemplo/ps"
SID, CAND, CONC, MAT = "sid-pos", "2027100000391", "1363", "2716520012"

CONTRATO_HTML = """<h3>Contrato</h3><form id="frm-aceite-contrato"><div id="contrato_id" class="panel"><div>
<p><strong>Olá!</strong><br>Estamos iniciando um novo semestre e precisamos da sua assinatura.</p>
<p><strong>1º Passo:</strong><br>Você receberá uma mensagem da Clicksign.</p>
<p><strong>2º Passo:</strong><br>Acesse o link e informe CPF e data de nascimento.</p>
<p class="MsoNormal"></p></div><div><font>Concluído o processo, uma cópia vai para o seu e-mail.</font></div></div>
<div class="row"><p><button type="submit" id="Inscrever" class="btn btn-primary">Próximo</button></p></div></form>"""

INGRESSO_HTML = ("<table><tbody>"
                 "<tr><td class=\"txt-center col-data-documento\">CPF - Obrigatório</td>"
                 "<td class=\"txt-center col-data-data-entrega\">04/11/26</td>"
                 "<td><button onclick=\"openModalWindown('54','05','CPF - Obrigatório','Ingresso');\"></button></td></tr>"
                 "<tr><td class=\"txt-center col-data-documento\">Comprovante de Quitação Eleitoral</td>"
                 "<td class=\"txt-center col-data-data-entrega\">04/11/26</td>"
                 "<td><button onclick=\"openModalWindown('70','77','Comprovante','Ingresso');\"></button></td></tr>"
                 "</tbody></table>")


def _insc(**kw):
    base = {"cod_candidato": CAND, "cod_concurso": CONC, "data_inscricao": "06/09/2026",
            "processo": "2027.1 - Processo Seletivo ENEM - IMEPAC", "curso": "Medicina", "unidade": "Imepac Araguari",
            "situacao": "Pré-Matriculado", "forma_pagamento": "Boleto", "contrato_aceito": False, "matricula": MAT}
    return Inscricao(**{**base, **kw})


def _cliente():
    s = SessoesLegado()
    s.criar(SID, httpx.Cookies())
    return ClienteLegado(LEG, 5, s)


def test_historico_traz_o_numero_da_matricula_do_botao_do_contrato():
    from tests.test_techne import _linha

    pagina = ("<table><tbody>" + _linha(CAND, "2027.1 - Processo Seletivo ENEM - IMEPAC - Medicina", "Pré-Matriculado",
                                        "05/11/2026", "Em Aberto", f"<a onclick=\"chamaContrato('{MAT}')\">Contrato</a>")
              + "</tbody></table>")
    (i,) = parse_historico(pagina)
    assert i.matricula == MAT and "contrato" in i.acoes


def test_instrucoes_do_contrato_sem_html():
    linhas = parse_instrucoes_contrato(CONTRATO_HTML)
    assert linhas == ["Olá!", "Estamos iniciando um novo semestre e precisamos da sua assinatura.", "1º Passo:",
                      "Você receberá uma mensagem da Clicksign.", "2º Passo:", "Acesse o link e informe CPF e data de nascimento.",
                      "Concluído o processo, uma cópia vai para o seu e-mail."]
    assert "Próximo" not in linhas  # o botão do formulário não é instrução
    assert parse_instrucoes_contrato("<p>sem contrato</p>") == []


@respx.mock
async def test_matricula_como_o_botao_contrato_do_historico():
    cl = _cliente()
    gera = respx.get(f"{LEG}/r/contrato/geraContratoAceite").mock(return_value=httpx.Response(
        200, json={"lyceumRetorno": {"tipo": "OK", "item": [None]}}))
    respx.get(f"{LEG}/r/contrato").mock(return_value=httpx.Response(200, text=CONTRATO_HTML))
    aceite = respx.post(f"{LEG}/r/contrato/aceitaContrato.json")
    m = await cl.matricula(SID, _insc())
    assert gera.calls.last.request.url.params["codigoAluno"] == MAT
    assert (m.matricula, m.periodo, m.forma_pagamento, m.contrato.status) == (MAT, "2027.1", "Boleto", "aguardando_assinatura")
    assert m.contrato.instrucoes[2] == "1º Passo:" and m.disciplinas == []
    assert not aceite.called  # o "Próximo" do legado não é chamado ao abrir


@respx.mock
async def test_matricula_sem_instrucoes_continua_visivel():
    cl = _cliente()
    respx.get(f"{LEG}/r/contrato/geraContratoAceite").mock(return_value=httpx.Response(
        200, json={"lyceumRetorno": {"tipo": "ERRO", "mensagem": "Contrato indisponível."}}))
    m = await cl.matricula(SID, _insc(contrato_aceito=True))
    assert m.matricula == MAT and m.contrato.status == "assinado" and m.contrato.instrucoes == []


@respx.mock
async def test_documentos_em_consulta_depois_do_pagamento():
    cl = _cliente()
    respx.route(method="GET", url__startswith=f"{LEG}/r/documentosPorProcessoCandidato").mock(
        return_value=httpx.Response(200, text=INGRESSO_HTML))
    docs = {d.codigo: d for d in await cl.documentos_consulta(SID, CAND, CONC)}
    assert set(docs) == {"05", "77"} and all(d.status == "enviado" for d in docs.values())
    assert docs["05"].nome == "CPF"  # nome do catálogo
    assert docs["77"].nome == "Comprovante de Quitação Eleitoral"  # fora do catálogo: nome da tela, sem "- Obrigatório"
