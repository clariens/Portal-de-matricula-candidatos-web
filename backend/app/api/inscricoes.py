import json
import os
import re

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import ValidationError
from starlette.datastructures import UploadFile as StarletteUpload

from app.api.deps import com_ref, gateway, inscricao_autorizada
from app.config import Settings, get_settings
from app.core.errors import PortalError
from app.core.selo import emitir_selo, verificar_selo
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
from app.services.lyceum.legado import mensagem_envio, resumo_recusas

router = APIRouter(tags=["inscricoes"])
MSG_IA_INDISPONIVEL = ("Não foi possível conferir este documento automaticamente agora. Ele vai para a secretaria "
                       "conferir; se preferir, envie outro arquivo.")
Insc = Depends(inscricao_autorizada)
User = Depends(current_user)
Gw = Depends(gateway)
TIPO_RE = re.compile(r"\w{1,10}")


# ---------- histórico ----------
@router.get("/inscricoes", response_model=list[Inscricao])
async def listar(user: SessionUser = User, gw: LyceumGateway = Gw, s: Settings = Depends(get_settings)):
    return com_ref([i.model_copy() for i in await gw.listar_inscricoes(user.cod_pessoa)], user, s)


@router.get("/inscricoes/{ref}", response_model=Inscricao)
async def obter(insc: Inscricao = Insc):
    return insc


# ---------- etapa: dados ----------
@router.get("/inscricoes/{ref}/candidato", response_model=Candidato)
async def obter_candidato(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.obter_candidato(user.cod_pessoa, insc)


@router.put("/inscricoes/{ref}/candidato", response_model=Candidato)
async def atualizar_candidato(body: CandidatoUpdate, insc: Inscricao = Insc, user: SessionUser = User,
                              gw: LyceumGateway = Gw):
    return await gw.atualizar_candidato(user.cod_pessoa, insc, body)


# ---------- etapa: documentos ----------
@router.get("/inscricoes/{ref}/documentos", response_model=list[DocumentoStatus])
async def listar_documentos(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.listar_documentos(user.cod_pessoa, insc)


@router.post("/inscricoes/{ref}/documentos/{tipo}", response_model=DocumentoStatus)
async def anexar_documento(
    request: Request,
    tipo: str,
    arquivo: UploadFile = File(...),
    ocr: str | None = Form(default=None, description="JSON de OcrResultado produzido no navegador"),
    insc: Inscricao = Insc,
    user: SessionUser = User,
    gw: LyceumGateway = Gw,
    s: Settings = Depends(get_settings),
):
    """Confere o documento e devolve o resultado com um selo assinado. Nada fica guardado no servidor: o
    navegador guarda o arquivo + selo e os devolve em POST /envio-documentos."""
    conteudo = await arquivo.read(s.portal_upload_max_mb * 1024 * 1024 + 1)
    nome, mime = _validar_arquivo(arquivo.filename, conteudo, s)
    leitor: LeitorDocumentos | None = getattr(request.app.state, "leitor", None)
    if leitor:
        # Conferência com IA no servidor: o resultado do navegador é ignorado (o servidor é a fonte da verdade)
        resultado = await _conferir_com_ia(leitor, s, request, insc, user, gw, tipo, conteudo, mime)
        if resultado.status != "anexado":
            return resultado  # documento errado: não recebe selo; o candidato envia outro arquivo
        analise = resultado.analise
    else:
        analise = None
        if ocr:
            try:
                analise = OcrResultado.model_validate(json.loads(ocr))
            except (ValueError, ValidationError):
                analise = None  # resultado ilegível do navegador: o documento vai para conferência manual
        if analise and analise.veredito in VEREDITOS_BLOQUEADOS:
            motivo = analise.alertas[0] if analise.alertas else "Documento não reconhecido."
            raise PortalError(422, motivo, {"arquivo": "Envie outro arquivo."})
    st, _ = await gw.anexar_documento(user.cod_pessoa, insc, tipo, nome, conteudo, mime, analise)
    st.analise = analise
    st.selo = emitir_selo(s, insc.cod_candidato, tipo, nome, conteudo, analise)
    return st


def _validar_arquivo(nome_bruto: str | None, conteudo: bytes, s: Settings) -> tuple[str, str]:
    nome = os.path.basename(nome_bruto or "documento")
    mime = EXTENSOES_ACEITAS.get(os.path.splitext(nome)[1].lower())
    if not mime:
        raise PortalError(422, "Formato não aceito. Envie JPG, PNG ou PDF.", {"arquivo": "Formato não aceito."})
    if len(conteudo) > s.portal_upload_max_mb * 1024 * 1024:
        raise PortalError(413, f"Arquivo acima de {s.portal_upload_max_mb} MB.", {"arquivo": "Arquivo grande demais."})
    if not conteudo:
        raise PortalError(422, "Arquivo vazio.", {"arquivo": "Arquivo vazio."})
    if not any(conteudo.startswith(m) for m in MAGIC[mime]):
        raise PortalError(422, "O conteúdo do arquivo não corresponde à extensão.", {"arquivo": "Arquivo inválido."})
    return nome, mime


async def _conferir_com_ia(leitor, s: Settings, request: Request, insc: Inscricao, user: SessionUser,
                           gw: LyceumGateway, tipo: str, conteudo: bytes, mime: str) -> DocumentoStatus:
    """Lê com IA e decide. Devolve o status "anexado" com a análise, ou o status atual se for documento errado."""
    esperado = next((d for d in await gw.listar_documentos(user.cod_pessoa, insc) if d.codigo == tipo), None)
    if not esperado:
        raise PortalError(404, "Documento não solicitado neste processo.")
    # limite de análises por documento (por instância): evita gasto descontrolado com trocas repetidas
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
    status = esperado.status if resultado.veredito in VEREDITOS_BLOQUEADOS else "anexado"
    return DocumentoStatus(**esperado.model_dump(exclude={"analise", "status"}), status=status, analise=resultado)


@router.post("/inscricoes/{ref}/envio-documentos", response_model=EnvioDocumentosResultado,
             openapi_extra={"requestBody": {"content": {"multipart/form-data": {"schema": {
                 "type": "object", "description": "Para cada documento: arquivo_<código> (arquivo) e "
                                                  "selo_<código> (o selo devolvido no anexo)."}}}}})
async def enviar_documentos(request: Request, insc: Inscricao = Insc, user: SessionUser = User,
                            gw: LyceumGateway = Gw, s: Settings = Depends(get_settings)):
    """Envia ao Lyceum os documentos que o navegador guardou (arquivo + selo de cada um), com resultado por
    documento: o que estiver certo segue e o que for recusado volta em `recusados` (código → motivo).
    Aceita N documentos, mas o navegador manda UM por chamada (progresso na tela e requisições pequenas).
    No legado o primeiro envio FINALIZA a inscrição."""
    form = await request.form(max_files=40)
    anexos, recusados = {}, {}
    for chave, valor in form.multi_items():
        tipo = chave.removeprefix("arquivo_")
        if tipo == chave or not isinstance(valor, StarletteUpload) or not TIPO_RE.fullmatch(tipo):
            continue
        conteudo = await valor.read(s.portal_upload_max_mb * 1024 * 1024 + 1)
        try:
            nome, analise = verificar_selo(s, str(form.get(f"selo_{tipo}") or ""), insc.cod_candidato, tipo, conteudo)
            nome, mime = _validar_arquivo(nome, conteudo, s)
            _, anexos[tipo] = await gw.anexar_documento(user.cod_pessoa, insc, tipo, nome, conteudo, mime, analise)
        except PortalError as e:
            if e.status != 409:  # 409 = o Lyceum já tem este documento: nunca reenviar
                recusados[tipo] = e.mensagem  # ex.: selo vencido ou acima do limite: só este fica para trás
    if recusados:
        nomes = {d.codigo: d.nome for d in await gw.listar_documentos(user.cod_pessoa, insc)}
        if not anexos:
            raise PortalError(422, resumo_recusas(nomes, recusados), recusados)
    resultado = await gw.enviar_documentos(user.cod_pessoa, insc, anexos)
    if recusados:
        resultado.recusados = {**recusados, **resultado.recusados}
        resultado.mensagem = mensagem_envio(nomes, resultado.recusados)
    return resultado


# ---------- etapa: pagamento ----------
@router.get("/inscricoes/{ref}/pagamento/opcoes", response_model=OpcoesPagamento)
async def opcoes_pagamento(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.opcoes_pagamento(user.cod_pessoa, insc)


@router.post("/inscricoes/{ref}/cupons/validar", response_model=CupomResultado)
async def validar_cupom(body: CupomIn, insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.validar_cupom(user.cod_pessoa, insc, body.codigo)


@router.post("/inscricoes/{ref}/pagamento", response_model=PagamentoResultado)
async def efetivar_pagamento(body: PagamentoIn, insc: Inscricao = Insc, user: SessionUser = User,
                             gw: LyceumGateway = Gw):
    return await gw.efetivar_pagamento(user.cod_pessoa, insc, body)


# ---------- etapa: conclusão ----------
@router.get("/inscricoes/{ref}/matricula", response_model=Matricula)
async def obter_matricula(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.obter_matricula(user.cod_pessoa, insc)


@router.post("/inscricoes/{ref}/matricula/confirmar", response_model=ConfirmacaoResultado)
async def confirmar_matricula(insc: Inscricao = Insc, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.confirmar_matricula(user.cod_pessoa, insc)


@router.get("/questionarios/pendentes", response_model=list[Questionario])
async def questionarios(user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.questionarios_pendentes(user.cod_pessoa)
