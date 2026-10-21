"""Etapa Documentos no legado: lista da página real, anexos no servidor e envio (simulado x real).

Markup reduzido de /r/documentosPorProcesso observado em DEV (21/10/2026).
"""

import httpx
import pytest
import respx

from app.core.errors import PortalError
from app.schemas.documento import OcrResultado
from app.services.lyceum.legado import ClienteLegado, SessoesLegado, parse_documentos

LEG = "https://legado.exemplo/ps"
SID, CAND = "sid-doc", "2027100000285"


def _doc(codigo, titulo, obrigatorio=False):
    req = "\n                          required " if obrigatorio else " "
    sufixo = " - Obrigat&oacute;rio" if obrigatorio else ""
    return f"""
              <h4 class="line-bottom">Upload de {titulo}{sufixo} (Extens&otilde;es permitidas:  JPEG, JPG, PDF, PNG)</h4>
                <div class="row"><div class="col-sm-6 col-md-6">
                    <input type="file" name="{codigo}"
                          placeholder="Upload de {titulo}" onchange="validarExtensao(this,'[JPEG, JPG, PDF, PNG]');"
                          class="btn btn-default btn-file"{req}/>
                </div></div><br>"""


DOCS_HTML = ('<form method="post" enctype="multipart/form-data" action="/processo-seletivo/r/uploadDocumentosPorProcesso"'
             ' id="frm-documentos"><div class="alert">(Os formatos aceitos são: PDF, DOC, PPT)</div>'
             + _doc("14", "Cart&atilde;o de Vacina")
             + _doc("03", "Certificado de Conclus&atilde;o / Hist&oacute;rico Escolar", True)
             + _doc("05", "CPF", True)
             + _doc("04", "Documento de Identidade", True).replace("Obrigat&oacute;rio", "obrigat&oacute;rio")
             + _doc("01", "Foto 3X4")
             + '<button type="submit">Próximo</button></form>')
ERRO_HTML = "<title>&#9888; Erro</title><p>Ocorreu um erro.</p>"
PDF = b"%PDF-1.4 teste"


def test_parse_documentos_da_pagina_real():
    tipos = parse_documentos(DOCS_HTML)
    assert [t.codigo for t in tipos] == ["14", "03", "05", "04", "01"]
    assert [t.codigo for t in tipos if t.obrigatorio] == ["03", "05", "04"]  # `required` e "- Obrigatório"
    t03 = tipos[1]
    assert t03.nome == "Certificado de Conclusão / Histórico Escolar" and t03.regra == "escolar"
    assert t03.extensoes == ["jpeg", "jpg", "pdf", "png"]
    assert tipos[0].nome == "Cartão de Vacina" and tipos[4].regra == "foto"


def _cliente(pagina=DOCS_HTML):
    s = SessoesLegado()
    s.criar(SID, httpx.Cookies())
    respx.get(f"{LEG}/r/documentosPorProcesso").mock(return_value=httpx.Response(200, text=pagina))
    return ClienteLegado(LEG, 5, s)


@respx.mock
async def test_pagina_bloqueada_sem_salvar_dados():
    cl = _cliente(ERRO_HTML)
    with pytest.raises(PortalError) as e:
        await cl.documentos(SID, CAND)
    assert e.value.status == 409 and "Confirme seus dados" in e.value.mensagem


@respx.mock
async def test_anexar_listar_remover():
    cl = _cliente()
    ok = OcrResultado(veredito="ok")
    st = await cl.anexar(SID, CAND, "05", "cpf.pdf", PDF, "application/pdf", ok)
    assert (st.status, st.arquivo, st.observacao) == ("anexado", "cpf.pdf", None)
    div = await cl.anexar(SID, CAND, "04", "rg.png", b"\x89PNG", "image/png", OcrResultado(veredito="divergente"))
    assert div.observacao == "Será conferido pela secretaria."
    lista = {d.codigo: d.status for d in await cl.documentos(SID, CAND)}
    assert lista == {"14": "pendente", "03": "pendente", "05": "anexado", "04": "anexado", "01": "pendente"}
    assert (await cl.remover_anexo(SID, CAND, "04")).status == "pendente"
    with pytest.raises(PortalError) as e:
        await cl.anexar(SID, CAND, "99", "x.pdf", PDF, "application/pdf", ok)
    assert e.value.status == 404
    with pytest.raises(PortalError) as e:
        await cl.anexar(SID, CAND, "05", "x.docx", b"PK", "application/msword", ok)
    assert e.value.status == 422


@respx.mock
async def test_envio_exige_obrigatorios():
    cl = _cliente()
    await cl.anexar(SID, CAND, "05", "cpf.pdf", PDF, "application/pdf", None)
    with pytest.raises(PortalError) as e:
        await cl.enviar_documentos(SID, CAND, simular=True)
    assert e.value.status == 409 and "Documento de Identidade" in e.value.mensagem


@respx.mock
async def test_envio_simulado_nao_chama_o_lyceum():
    cl = _cliente()
    upload = respx.post(f"{LEG}/r/uploadDocumentosPorProcesso").mock(return_value=httpx.Response(303))
    for c in ("03", "05", "04"):
        await cl.anexar(SID, CAND, c, f"{c}.pdf", PDF, "application/pdf", None)
    r = await cl.enviar_documentos(SID, CAND, simular=True)
    assert r.simulado and "nada foi enviado" in r.mensagem
    assert not upload.called  # o POST real FINALIZA a inscrição: nunca em modo simulação
    assert cl.sessoes.obter(SID).etapas[CAND] == "pagamento"
    assert sum(d.status == "anexado" for d in r.documentos) == 3  # anexos preservados


@respx.mock
async def test_envio_real_monta_multipart_igual_ao_form():
    cl = _cliente()
    upload = respx.post(f"{LEG}/r/uploadDocumentosPorProcesso").mock(
        return_value=httpx.Response(303, headers={"Location": "/processo-seletivo/r/pagamentoIngresso"}))
    for c in ("03", "05", "04"):
        await cl.anexar(SID, CAND, c, f"doc{c}.pdf", PDF, "application/pdf", None)
    r = await cl.enviar_documentos(SID, CAND, simular=False)
    assert not r.simulado and {d.codigo: d.status for d in r.documentos}["05"] == "enviado"
    corpo = upload.calls.last.request.content
    assert upload.calls.last.request.headers["content-type"].startswith("multipart/form-data")
    for c in ("14", "03", "05", "04", "01"):  # um campo por documento da página, inclusive os vazios
        assert f'name="{c}"'.encode() in corpo
    assert b'filename="doc05.pdf"' in corpo and b'name="14"; filename=""' in corpo


@respx.mock
async def test_envio_real_recusado_pelo_lyceum():
    cl = _cliente()
    respx.post(f"{LEG}/r/uploadDocumentosPorProcesso").mock(
        return_value=httpx.Response(500, headers={"mensagem": "Documento excede o tamanho"}))
    for c in ("03", "05", "04"):
        await cl.anexar(SID, CAND, c, f"{c}.pdf", PDF, "application/pdf", None)
    with pytest.raises(PortalError) as e:
        await cl.enviar_documentos(SID, CAND, simular=False)
    assert e.value.status == 422 and e.value.mensagem == "Documento excede o tamanho"


@respx.mock
async def test_lista_de_documentos_em_cache_e_etapa_no_historico():
    from app.services.lyceum.legado import CACHE_HISTORICO  # noqa: F401
    cl = _cliente()
    pagina = respx.routes[0]
    await cl.documentos(SID, CAND)
    await cl.anexar(SID, CAND, "05", "a.pdf", PDF, "application/pdf", None)
    await cl.documentos(SID, CAND)
    assert pagina.call_count == 1  # página lida uma vez só
    cl.avancar_etapa(SID, CAND, "pagamento")
    from app.schemas.inscricao import Inscricao
    insc = Inscricao(cod_candidato=CAND, cod_concurso="1363", data_inscricao="", processo="", curso="", unidade="",
                     situacao="Convocado", acoes=["matricular"])
    s = cl.sessoes.obter(SID)
    s.historico = (__import__("time").monotonic(), [insc])  # cache quente
    (i,) = await cl.historico(SID)
    assert i.etapa_atual == "pagamento" and i.acoes == ["continuar_matricula"]
