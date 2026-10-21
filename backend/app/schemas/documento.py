from typing import Literal

from pydantic import Field

from app.schemas.base import ApiModel

Regra = Literal["cpf", "id", "escolar", "declaracao", "residencia", "foto", "nome"]
# anexado = recebido pelo portal e pronto para envio; ainda NÃO foi ao Lyceum
StatusDoc = Literal["pendente", "anexado", "enviado", "em_conferencia", "aprovado", "recusado"]
Veredito = Literal["ok", "atencao", "divergente", "tipo_errado", "ilegivel", "erro"]
# Único resultado que impede anexar: leitura boa e nenhuma marca do documento (certeza de que é outro).
# Ilegível e leitura fraca NÃO bloqueiam: foto ruim de documento verdadeiro vai para conferência manual.
VEREDITOS_BLOQUEADOS = {"tipo_errado"}


class OcrCampo(ApiModel):
    k: str
    v: str
    ok: bool


class OcrResultado(ApiModel):
    """Resultado do OCR feito no navegador. Informativo: não substitui a conferência da secretaria."""

    veredito: Veredito
    confianca: int | None = Field(default=None, ge=0, le=100)
    campos: list[OcrCampo] = []
    alertas: list[str] = []
    # quem conferiu: a IA no servidor (autoritativo) ou o OCR do navegador (informativo)
    fonte: Literal["ia", "navegador"] = "navegador"


class TipoDocumento(ApiModel):
    codigo: str
    nome: str
    obrigatorio: bool
    regra: Regra = "nome"
    extensoes: list[str] = ["pdf", "jpg", "jpeg", "png"]


class DocumentoStatus(TipoDocumento):
    status: StatusDoc = "pendente"
    arquivo: str | None = None
    enviado_em: str | None = None
    ocr_veredito: Veredito | None = None
    observacao: str | None = None
    # resultado da conferência deste envio (presente na resposta do anexo)
    analise: OcrResultado | None = None


class EnvioDocumentosResultado(ApiModel):
    simulado: bool
    mensagem: str
    documentos: list[DocumentoStatus]
