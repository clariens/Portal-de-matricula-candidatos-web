"""Sessão do legado compartilhada entre instâncias (Vercel): duas SessoesLegado com o mesmo armazenamento."""

import asyncio

import httpx
import pytest

from app.schemas.documento import OcrResultado
from app.services.estado import MemoriaKV
from app.services.lyceum.legado import Anexo, SessaoLegadoExpirada, SessoesLegado

SID, CAND = "sid-x", "2027100000285"


def _anexo(nome):
    return Anexo(nome=nome, conteudo=b"%PDF-1.4 " + nome.encode(), mime="application/pdf", em="29/10/2026 10:00",
                 ocr=OcrResultado(veredito="ok", confianca=90, campos=[], alertas=[]))


async def _req(inst: SessoesLegado, sid=SID, carregar=True):
    req = inst.iniciar()
    if carregar:
        await inst.carregar(req, sid)
    return req


async def test_login_numa_instancia_e_uso_em_outra():
    kv = MemoriaKV()
    a, b = SessoesLegado(kv), SessoesLegado(kv)
    req = await _req(a, carregar=False)
    cookies = httpx.Cookies()
    cookies.set("JSESSIONID", "abc123", domain="legado.exemplo", path="/ps")
    a.criar(SID, cookies)
    a.obter(SID).etapas[CAND] = "documentos"
    await a.concluir(req)

    req = await _req(b)
    s = b.obter(SID)
    assert s.cookies.get("JSESSIONID") == "abc123" and s.etapas[CAND] == "documentos"
    s.anexos.setdefault(CAND, {})["05"] = _anexo("cpf.pdf")
    await b.concluir(req)
    assert SID not in b._s  # nada fica preso na memória da instância

    req = await _req(a)
    anexo = a.obter(SID).anexos[CAND]["05"]
    assert anexo.conteudo == b"%PDF-1.4 cpf.pdf" and anexo.ocr.veredito == "ok"
    await a.concluir(req)


async def test_uploads_simultaneos_de_documentos_diferentes_nao_se_perdem():
    kv = MemoriaKV()
    a, b, c = SessoesLegado(kv), SessoesLegado(kv), SessoesLegado(kv)
    req = await _req(a, carregar=False)
    a.criar(SID, httpx.Cookies())
    await a.concluir(req)
    # duas instâncias atendem ao mesmo tempo (cada requisição na sua task), cada uma anexa um documento
    carregou = asyncio.Event()
    prontos = []

    async def anexar(inst, tipo, nome):
        req = await _req(inst)
        prontos.append(tipo)
        if len(prontos) == 2:
            carregou.set()
        await carregou.wait()  # as duas leram o estado antes de qualquer uma salvar
        inst.obter(SID).anexos.setdefault(CAND, {})[tipo] = _anexo(nome)
        await inst.concluir(req)

    await asyncio.gather(asyncio.create_task(anexar(a, "05", "cpf.pdf")), asyncio.create_task(anexar(b, "04", "rg.pdf")))
    rc = await _req(c)
    assert set(c.obter(SID).anexos[CAND]) == {"05", "04"}
    # remover numa instância some para as outras
    del c.obter(SID).anexos[CAND]["05"]
    await c.concluir(rc)
    ra = await _req(a)
    assert set(a.obter(SID).anexos[CAND]) == {"04"}
    await a.concluir(ra)


async def test_logout_apaga_para_todas_as_instancias():
    kv = MemoriaKV()
    a, b = SessoesLegado(kv), SessoesLegado(kv)
    req = await _req(a, carregar=False)
    a.criar(SID, httpx.Cookies())
    await a.concluir(req)
    req = await _req(b)
    b.remover(SID)
    await b.concluir(req)
    req = await _req(a)
    with pytest.raises(SessaoLegadoExpirada):
        a.obter(SID)
    await a.concluir(req)
