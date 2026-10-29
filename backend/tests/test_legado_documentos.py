"""Etapa Documentos no legado: lista da página real, anexos no servidor e envio (simulado x real).

Markup reduzido de /r/documentosPorProcesso observado em DEV (21/10/2026).
"""

import httpx
import pytest
import respx

from app.core.errors import PortalError
from app.schemas.documento import OcrResultado
from app.services.lyceum.legado import (
    ClienteLegado,
    SessoesLegado,
    parse_documentos,
    parse_documentos_entregues,
)

LEG = "https://legado.exemplo/ps"
SID, CAND, CONC = "sid-doc", "2027100000285", "1363"


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


def _entregue(id_, codigo, titulo, aceito="Pendente", motivo="", data="22/10/26"):
    return (f'<tr><td data-title="Documento" class="txt-center col-data-documento">{titulo}</td>'
            f'<td class="txt-center col-data-aceito"><span class="neutro" id="aceito" title="{aceito}"></span></td>'
            f'<td class="txt-center col-data-motivo-recusa">{motivo}</td>'
            f'<td class="txt-center col-data-data-entrega">{data}</td>'
            f"""<td class="txt-center col-data-envio"><button onclick="openModalWindown('{id_}','{codigo}','"""
            f"""{titulo}','Ingresso');"></button></td></tr>""")


NENHUM_ENTREGUE = "<p>Não foram enviados documentos para esta inscrição.</p>"
ENTREGUES_HTML = ("<table><tbody>" + _entregue("51", "02", "Declaração") + _entregue("52", "04", "Identidade", "Sim")
                  + _entregue("53", "05", "CPF", "Não", "Foto ilegível") + _entregue("54", "03", "Histórico")
                  + "</tbody></table>")


def _cliente(pagina=DOCS_HTML, entregues=NENHUM_ENTREGUE):
    s = SessoesLegado()
    s.criar(SID, httpx.Cookies())
    respx.get(f"{LEG}/r/documentosPorProcesso").mock(return_value=httpx.Response(200, text=pagina))
    respx.route(method="GET", url__startswith=f"{LEG}/r/documentosPorProcessoCandidato").mock(
        return_value=httpx.Response(200, text=entregues))
    return ClienteLegado(LEG, 5, s)


def _lyceum_grava(rota_envio, entregues_depois):
    """Documentos Ingresso passa a listar `entregues_depois` assim que a rota de envio é chamada."""
    respx.route(method="GET", url__startswith=f"{LEG}/r/documentosPorProcessoCandidato").mock(
        side_effect=lambda req: httpx.Response(200, text=entregues_depois() if rota_envio.called else _ATUAL[0]))


_ATUAL = [NENHUM_ENTREGUE]


def _tabela(*codigos):
    return "<table><tbody>" + "".join(_entregue(str(60 + i), c, f"Doc {c}", data="29/10/26")
                                      for i, c in enumerate(codigos)) + "</tbody></table>"


@respx.mock
async def test_pagina_bloqueada_sem_salvar_dados():
    cl = _cliente(ERRO_HTML)
    with pytest.raises(PortalError) as e:
        await cl.documentos(SID, CAND, CONC)
    assert e.value.status == 409 and "Confirme seus dados" in e.value.mensagem


@respx.mock
async def test_anexar_listar_remover():
    cl = _cliente()
    ok = OcrResultado(veredito="ok")
    st = await cl.anexar(SID, CAND, CONC, "05", "cpf.pdf", PDF, "application/pdf", ok)
    assert (st.status, st.arquivo, st.observacao) == ("anexado", "cpf.pdf", None)
    div = await cl.anexar(SID, CAND, CONC, "04", "rg.png", b"\x89PNG", "image/png", OcrResultado(veredito="divergente"))
    assert div.observacao == "Será conferido pela secretaria."
    lista = {d.codigo: d.status for d in await cl.documentos(SID, CAND, CONC)}
    assert lista == {"14": "pendente", "03": "pendente", "05": "anexado", "04": "anexado", "01": "pendente"}
    assert (await cl.remover_anexo(SID, CAND, "04")).status == "pendente"
    with pytest.raises(PortalError) as e:
        await cl.anexar(SID, CAND, CONC, "99", "x.pdf", PDF, "application/pdf", ok)
    assert e.value.status == 404
    with pytest.raises(PortalError) as e:
        await cl.anexar(SID, CAND, CONC, "05", "x.docx", b"PK", "application/msword", ok)
    assert e.value.status == 422


@respx.mock
async def test_envio_exige_obrigatorios():
    cl = _cliente()
    await cl.anexar(SID, CAND, CONC, "05", "cpf.pdf", PDF, "application/pdf", None)
    with pytest.raises(PortalError) as e:
        await cl.enviar_documentos(SID, CAND, CONC, simular=True)
    assert e.value.status == 409 and "Documento de Identidade" in e.value.mensagem


@respx.mock
async def test_envio_simulado_nao_chama_o_lyceum():
    cl = _cliente()
    upload = respx.post(f"{LEG}/r/uploadDocumentosPorProcesso").mock(return_value=httpx.Response(303))
    for c in ("03", "05", "04"):
        await cl.anexar(SID, CAND, CONC, c, f"{c}.pdf", PDF, "application/pdf", None)
    r = await cl.enviar_documentos(SID, CAND, CONC, simular=True)
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
        await cl.anexar(SID, CAND, CONC, c, f"doc{c}.pdf", PDF, "application/pdf", None)
    _lyceum_grava(upload, lambda: _tabela("03", "05", "04"))
    r = await cl.enviar_documentos(SID, CAND, CONC, simular=False)
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
        await cl.anexar(SID, CAND, CONC, c, f"{c}.pdf", PDF, "application/pdf", None)
    with pytest.raises(PortalError) as e:
        await cl.enviar_documentos(SID, CAND, CONC, simular=False)
    assert e.value.status == 422 and e.value.mensagem == "Documento excede o tamanho"


@respx.mock
async def test_lista_de_documentos_em_cache_e_etapa_no_historico():
    from app.services.lyceum.legado import CACHE_HISTORICO  # noqa: F401
    cl = _cliente()
    pagina = respx.routes[0]
    await cl.documentos(SID, CAND, CONC)
    await cl.anexar(SID, CAND, CONC, "05", "a.pdf", PDF, "application/pdf", None)
    await cl.documentos(SID, CAND, CONC)
    assert pagina.call_count == 1  # página lida uma vez só
    cl.avancar_etapa(SID, CAND, "pagamento")
    from app.schemas.inscricao import Inscricao
    insc = Inscricao(cod_candidato=CAND, cod_concurso="1363", data_inscricao="", processo="", curso="", unidade="",
                     situacao="Convocado", acoes=["matricular"])
    s = cl.sessoes.obter(SID)
    s.historico = (__import__("time").monotonic(), [insc])  # cache quente
    (i,) = await cl.historico(SID)
    assert i.etapa_atual == "pagamento" and i.acoes == ["continuar_matricula"]


@respx.mock
async def test_envio_real_200_confirmado_em_documentos_ingresso():
    """Legado devolve 200 (não redireciona): vale o que aparece em Documentos Ingresso."""
    cl = _cliente()
    upload = respx.post(f"{LEG}/r/uploadDocumentosPorProcesso").mock(return_value=httpx.Response(200, text="ok"))
    for c in ("03", "05", "04"):
        await cl.anexar(SID, CAND, CONC, c, f"{c}.pdf", PDF, "application/pdf", None)
    _lyceum_grava(upload, lambda: _tabela("03", "05", "04"))
    r = await cl.enviar_documentos(SID, CAND, CONC, simular=False)
    assert not r.simulado and r.mensagem == "Documentos enviados."
    assert cl.sessoes.obter(SID).etapas[CAND] == "pagamento"


@respx.mock
async def test_envio_real_200_sem_gravar_e_erro():
    """Visto em DEV (29/10/2026): o legado responde 200 e não grava nada. Não pode virar "enviado"."""
    cl = _cliente()
    respx.post(f"{LEG}/r/uploadDocumentosPorProcesso").mock(return_value=httpx.Response(200, text="<html></html>"))
    for c in ("03", "05", "04"):
        await cl.anexar(SID, CAND, CONC, c, f"{c}.pdf", PDF, "application/pdf", None)
    with pytest.raises(PortalError) as e:
        await cl.enviar_documentos(SID, CAND, CONC, simular=False)
    assert "não registrou" in e.value.mensagem
    assert set(cl._anexos(SID, CAND)) == {"03", "05", "04"}  # continuam anexados para tentar de novo


@respx.mock
async def test_documento_novo_depois_do_primeiro_envio_vai_pela_rota_avulsa():
    """Com os obrigatórios já entregues, cada documento novo vai por /r/documentosCandidato/upload."""
    cl = _cliente(entregues=ENTREGUES_HTML)
    lote = respx.post(f"{LEG}/r/uploadDocumentosPorProcesso").mock(return_value=httpx.Response(200))
    avulso = respx.post(f"{LEG}/r/documentosCandidato/upload").mock(return_value=httpx.Response(204))
    await cl.anexar(SID, CAND, CONC, "14", "vacina.pdf", PDF, "application/pdf", None)
    await cl.anexar(SID, CAND, CONC, "01", "foto.pdf", PDF, "application/pdf", None)
    _ATUAL[0] = ENTREGUES_HTML
    try:  # o Lyceum grava a vacina e não grava a foto
        _lyceum_grava(avulso, lambda: ENTREGUES_HTML.replace("</tbody>", _entregue("70", "14", "Vacina") + "</tbody>"))
        r = await cl.enviar_documentos(SID, CAND, CONC, simular=False)
    finally:
        _ATUAL[0] = NENHUM_ENTREGUE
    assert not lote.called and avulso.call_count == 2
    campos = [c.request.content for c in avulso.calls]
    assert b'name="14,Ingresso"; filename="vacina.pdf"' in campos[0] and b'name="01,Ingresso"' in campos[1]
    st = {d.codigo: d.status for d in r.documentos}
    assert st["14"] == "enviado" and st["01"] == "anexado" and "exceto: Foto 3X4" in r.mensagem
    assert set(cl._anexos(SID, CAND)) == {"01"}


@respx.mock
async def test_documento_novo_simulado_nao_chama_o_lyceum():
    cl = _cliente(entregues=ENTREGUES_HTML)
    avulso = respx.post(f"{LEG}/r/documentosCandidato/upload").mock(return_value=httpx.Response(204))
    await cl.anexar(SID, CAND, CONC, "14", "vacina.pdf", PDF, "application/pdf", None)
    r = await cl.enviar_documentos(SID, CAND, CONC, simular=True)
    assert r.simulado and not avulso.called


def test_parse_documentos_entregues():
    e = parse_documentos_entregues(ENTREGUES_HTML)
    assert set(e) == {"02", "04", "05", "03"}
    assert (e["04"].aceito, e["05"].aceito, e["05"].motivo, e["02"].data) == ("Sim", "Não", "Foto ilegível", "22/10/26")
    assert parse_documentos_entregues(NENHUM_ENTREGUE) == {}


@respx.mock
async def test_lista_usa_o_que_o_lyceum_ja_registrou_mesmo_com_a_pagina_fechada():
    cl = _cliente(pagina=ERRO_HTML, entregues=ENTREGUES_HTML)
    st = {d.codigo: (d.status, d.enviado_em) for d in await cl.documentos(SID, CAND, CONC)}
    # aceito, pendente ou recusado na secretaria: para o candidato é só "enviado"
    assert st["02"] == st["04"] == st["05"] == st["03"] == ("enviado", "22/10/26")
    assert st["01"][0] == "pendente"
    assert cl.sessoes.obter(SID).etapas[CAND] == "pagamento"  # obrigatórios entregues → segue para pagamento


@respx.mock
async def test_nao_anexa_documento_ja_entregue():
    cl = _cliente(entregues=ENTREGUES_HTML)
    with pytest.raises(PortalError) as e:
        await cl.anexar(SID, CAND, CONC, "05", "cpf.pdf", PDF, "application/pdf", None)
    assert e.value.status == 409 and "já foi enviado" in e.value.mensagem


@respx.mock
async def test_nunca_reenvia_quando_o_lyceum_ja_tem_os_obrigatorios():
    """Depois do envio o legado continua mostrando o formulário: reenviar duplicaria os documentos."""
    cl = _cliente(entregues=ENTREGUES_HTML)
    upload = respx.post(f"{LEG}/r/uploadDocumentosPorProcesso").mock(return_value=httpx.Response(302))
    r = await cl.enviar_documentos(SID, CAND, CONC, simular=False)
    assert not upload.called and "já foram enviados" in r.mensagem


# ---------- tamanho: compressão de fotos e limites do Lyceum ----------
def _foto_grande() -> bytes:
    """JPEG de 'celular' (3000x4000 com ruído): vários MB."""
    import io
    import os

    from PIL import Image
    img = Image.frombytes("RGB", (3000, 4000), os.urandom(3000 * 4000 * 3))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=95)
    return buf.getvalue()


@respx.mock
async def test_foto_de_celular_e_comprimida_antes_de_ir_ao_lyceum():
    cl = _cliente()
    foto = _foto_grande()
    assert len(foto) > 4 * 1024 * 1024
    st = await cl.anexar(SID, CAND, CONC, "04", "rg.png", foto, "image/png", None)
    anexo = cl.sessoes.obter(SID).anexos[CAND]["04"]
    assert st.arquivo == "rg.jpg" and anexo.mime == "image/jpeg"
    assert len(anexo.conteudo) < 2048 * 1024  # dentro do limite por arquivo


@respx.mock
async def test_pdf_acima_do_limite_por_arquivo_e_recusado_no_anexo():
    cl = _cliente()
    pdf_grande = b"%PDF-1.4" + b"0" * (3 * 1024 * 1024)
    with pytest.raises(PortalError) as e:
        await cl.anexar(SID, CAND, CONC, "03", "historico.pdf", pdf_grande, "application/pdf", None)
    assert e.value.status == 422 and "3,0 MB" in e.value.mensagem and "2,0 MB por arquivo" in e.value.mensagem


@respx.mock
async def test_total_acima_do_limite_nao_chega_a_enviar():
    s = SessoesLegado()
    s.criar(SID, httpx.Cookies())
    respx.get(f"{LEG}/r/documentosPorProcesso").mock(return_value=httpx.Response(200, text=DOCS_HTML))
    respx.route(method="GET", url__startswith=f"{LEG}/r/documentosPorProcessoCandidato").mock(
        return_value=httpx.Response(200, text=NENHUM_ENTREGUE))
    cl = ClienteLegado(LEG, 5, s, max_kb_arquivo=1024, max_kb_total=2048)
    upload = respx.post(f"{LEG}/r/uploadDocumentosPorProcesso").mock(return_value=httpx.Response(302))
    pdf = b"%PDF-1.4" + b"0" * (900 * 1024)
    for c in ("03", "05", "04"):
        await cl.anexar(SID, CAND, CONC, c, f"{c}.pdf", pdf, "application/pdf", None)
    with pytest.raises(PortalError) as e:
        await cl.enviar_documentos(SID, CAND, CONC, simular=False)
    assert not upload.called and "limite por envio" in e.value.mensagem


@respx.mock
@pytest.mark.parametrize("resposta,trecho", [
    (httpx.Response(413, text="<title>413 Request Entity Too Large</title>"), "limite de tamanho do Lyceum"),
    (httpx.Response(500, text="<title>Erro</title>FileSizeLimitExceededException: ..."), "limite por arquivo"),
])
async def test_erros_de_tamanho_do_legado_viram_mensagens_claras(resposta, trecho):
    cl = _cliente()
    respx.post(f"{LEG}/r/uploadDocumentosPorProcesso").mock(return_value=resposta)
    for c in ("03", "05", "04"):
        await cl.anexar(SID, CAND, CONC, c, f"{c}.pdf", PDF, "application/pdf", None)
    with pytest.raises(PortalError) as e:
        await cl.enviar_documentos(SID, CAND, CONC, simular=False)
    assert e.value.status == 422 and trecho in e.value.mensagem
