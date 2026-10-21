from typing import Literal

from app.schemas.base import ApiModel


class Disciplina(ApiModel):
    codigo: str
    nome: str


class Contrato(ApiModel):
    status: Literal["nao_enviado", "aguardando_assinatura", "assinado"]
    canal: str = "Clicksign · WhatsApp"
    destinatario: str | None = None  # celular mascarado do responsável financeiro


class Matricula(ApiModel):
    matricula: str
    curso: str
    turma: str | None = None
    periodo: str | None = None
    unidade: str | None = None
    disciplinas: list[Disciplina]
    contrato: Contrato
    forma_pagamento: str | None = None
    num_parcelas: int | None = None


class Questionario(ApiModel):
    codigo: str
    titulo: str
    url: str | None = None


class ConfirmacaoResultado(ApiModel):
    situacao: str
    questionarios_pendentes: list[Questionario] = []
