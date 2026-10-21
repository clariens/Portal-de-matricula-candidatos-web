import json
import os

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import ValidationError

from app.api.deps import gateway, inscricao_autorizada
from app.config import Settings, get_settings
from app.core.errors import PortalError
from app.core.session import SessionUser, current_user
from app.schemas.candidato import Candidato, CandidatoUpdate
from app.schemas.documento import (
    VEREDITOS_BLOQUEADOS,
    DocumentoStatus,
    EnvioDocumentosResultado,
    OcrResultado,
)
from app.schemas.inscricao import Inscricao
from app.schemas.matricula import ConfirmacaoResultado, Matricula, Questionario
from app.schemas.pagamento import CupomIn, CupomResultado, OpcoesPagamento, PagamentoIn, PagamentoResultado
from app.services.conferencia import conferir
from app.services.ia_documentos import IAIndisponivel, LeitorDocumentos
from app.services.lyceum import LyceumGateway
from app.services.lyceum.catalogo import EXTENSOES_ACEITAS, MAGIC

router = APIRouter(tags=["inscricoes"])
MSG_IA_INDISPONIVEL = ("Não foi possível conferir este documento automaticamente agora. Ele vai para a secretaria "
                       "conferir; se preferir, envie outro arquivo.")
Insc = Depends(inscricao_autorizada)
User = Depends(current_user)
Gw = Depends(gateway)


# ---------- histórico ----------
@router.get("/inscricoes", response_model=list[Inscricao])
async def listar(user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.listar_inscricoes(user.cod_pessoa)


@router.get("/inscricoes/{cod_candidato}", response_model=Inscricao)
async def obter(insc: Inscricao = Insc):
    return insc


# ---------- etapa: dados ----------
@router.get("/inscricoes/{cod_candidato}/candidato", response_model=Candidato)
async def obter_candidato(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.obter_candidato(user.cod_pessoa, insc)


@router.put("/inscricoes/{cod_candidato}/candidato", response_model=Candidato)
async def atualizar_candidato(body: CandidatoUpdate, insc: Inscricao = Insc, user: SessionUser = User,
                              gw: LyceumGateway = Gw):
    return await gw.atualizar_candidato(user.cod_pessoa, insc, body)


# ---------- etapa: documentos ----------
@router.get("/inscricoes/{cod_candidato}/documentos", response_model=list[DocumentoStatus])
async def listar_documentos(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.listar_documentos(user.cod_pessoa, insc)


@router.post("/inscricoes/{cod_candidato}/documentos/{tipo}", response_model=DocumentoStatus)
async def enviar_documento(
    request: Request,
    tipo: str,
    arquivo: UploadFile = File(...),
    ocr: str | None = Form(default=None, description="JSON de OcrResultado produzido no navegador"),
    insc: Inscricao = Insc,
    user: SessionUser = User,
    gw: LyceumGateway = Gw,
    s: Settings = Depends(get_settings),
):
    nome = os.path.basename(arquivo.filename or "documento")
    ext = os.path.splitext(nome)[1].lower()
    mime = EXTENSOES_ACEITAS.get(ext)
    if not mime:
        raise PortalError(422, "Formato não aceito. Envie JPG, PNG ou PDF.", {"arquivo": "Formato não aceito."})
    limite = s.portal_upload_max_mb * 1024 * 1024
    conteudo = await arquivo.read(limite + 1)
    if len(conteudo) > limite:
        raise PortalError(413, f"Arquivo acima de {s.portal_upload_max_mb} MB.", {"arquivo": "Arquivo grande demais."})
    if not conteudo:
        raise PortalError(422, "Arquivo vazio.", {"arquivo": "Arquivo vazio."})
    if not any(conteudo.startswith(m) for m in MAGIC[mime]):
        raise PortalError(422, "O conteúdo do arquivo não corresponde à extensão.", {"arquivo": "Arquivo inválido."})
    leitor: LeitorDocumentos | None = getattr(request.app.state, "leitor", None)
    if leitor:
        # Conferência com IA no servidor: o resultado do navegador é ignorado (o servidor é a fonte da verdade)
        return await _conferir_com_ia(leitor, s, request, insc, user, gw, tipo, nome, conteudo, mime)

    ocr_res = None
    if ocr:
        try:
            ocr_res = OcrResultado.model_validate(json.loads(ocr))
        except (ValueError, ValidationError):
            ocr_res = None  # resultado ilegível do navegador: o documento vai para conferência manual
    if ocr_res and ocr_res.veredito in VEREDITOS_BLOQUEADOS:
        motivo = ocr_res.alertas[0] if ocr_res.alertas else "Documento não reconhecido."
        raise PortalError(422, motivo, {"arquivo": "Envie outro arquivo."})
    return await gw.enviar_documento(user.cod_pessoa, insc, tipo, nome, conteudo, mime, ocr_res)


async def _conferir_com_ia(leitor, s: Settings, request: Request, insc: Inscricao, user: SessionUser,
                           gw: LyceumGateway, tipo: str, nome: str, conteudo: bytes, mime: str) -> DocumentoStatus:
    esperado = next((d for d in await gw.listar_documentos(user.cod_pessoa, insc) if d.codigo == tipo), None)
    if not esperado:
        raise PortalError(404, "Documento não solicitado neste processo.")
    # limite de análises por documento na sessão: evita gasto descontrolado com trocas repetidas
    tentativas = request.app.state.tentativas_ia
    chave = (user.sid, insc.cod_candidato, tipo)
    tentativas[chave] = tentativas.get(chave, 0) + 1
    if tentativas[chave] > s.ia_documentos_tentativas_por_documento:
        resultado = OcrResultado(veredito="erro", fonte="ia", alertas=[
            "Você já enviou este documento várias vezes. Este arquivo vai para a secretaria conferir."])
    else:
        try:
            cand = await gw.obter_candidato(user.cod_pessoa, insc)
            lido = await leitor.ler(conteudo, mime, f"tipo={tipo}")
            resultado = conferir(lido.leitura, esperado, cand)
        except IAIndisponivel:
            resultado = OcrResultado(veredito="erro", fonte="ia", alertas=[MSG_IA_INDISPONIVEL])
    if resultado.veredito in VEREDITOS_BLOQUEADOS:
        # documento errado: não é anexado; o candidato precisa enviar outro arquivo
        return DocumentoStatus(**esperado.model_dump(exclude={"analise"}) | {"status": esperado.status}, analise=resultado)
    st = await gw.enviar_documento(user.cod_pessoa, insc, tipo, nome, conteudo, mime, resultado)
    st.analise = resultado
    return st


@router.delete("/inscricoes/{cod_candidato}/documentos/{tipo}", response_model=DocumentoStatus)
async def remover_documento(tipo: str, insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.remover_documento(user.cod_pessoa, insc, tipo)


@router.post("/inscricoes/{cod_candidato}/envio-documentos", response_model=EnvioDocumentosResultado)
async def enviar_documentos(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    """Envia ao Lyceum, de uma vez, os documentos anexados. No legado isso FINALIZA a inscrição."""
    return await gw.enviar_documentos(user.cod_pessoa, insc)


# ---------- etapa: pagamento ----------
@router.get("/inscricoes/{cod_candidato}/pagamento/opcoes", response_model=OpcoesPagamento)
async def opcoes_pagamento(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.opcoes_pagamento(user.cod_pessoa, insc)


@router.post("/inscricoes/{cod_candidato}/cupons/validar", response_model=CupomResultado)
async def validar_cupom(body: CupomIn, insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.validar_cupom(user.cod_pessoa, insc, body.codigo)


@router.post("/inscricoes/{cod_candidato}/pagamento", response_model=PagamentoResultado)
async def efetivar_pagamento(body: PagamentoIn, insc: Inscricao = Insc, user: SessionUser = User,
                             gw: LyceumGateway = Gw):
    return await gw.efetivar_pagamento(user.cod_pessoa, insc, body)


# ---------- etapa: conclusão ----------
@router.get("/inscricoes/{cod_candidato}/matricula", response_model=Matricula)
async def obter_matricula(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.obter_matricula(user.cod_pessoa, insc)


@router.post("/inscricoes/{cod_candidato}/matricula/confirmar", response_model=ConfirmacaoResultado)
async def confirmar_matricula(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.confirmar_matricula(user.cod_pessoa, insc)


@router.get("/questionarios/pendentes", response_model=list[Questionario])
async def questionarios(user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.questionarios_pendentes(user.cod_pessoa)
