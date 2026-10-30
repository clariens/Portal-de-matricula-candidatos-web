from typing import Literal

from app.schemas.base import ApiModel

Situacao = Literal["Convocado", "Confirmado", "Pré-Matriculado", "Matriculado", "Cancelado", "Inscrito"]
Acao = Literal["matricular", "continuar_matricula", "contrato", "documentos"]
Etapa = Literal["dados", "documentos", "pagamento", "conclusao"]


class Inscricao(ApiModel):
    cod_candidato: str
    # referência opaca para URLs (telas e API); o número da inscrição não vai na URL (app/core/referencia.py)
    ref: str | None = None
    cod_concurso: str | None = None  # o histórico legado só expõe o concurso em Convocado/Pré-Matriculado
    data_inscricao: str
    processo: str
    curso: str
    unidade: str
    situacao: Situacao
    forma_pagamento: str | None = None
    vencimento: str | None = None
    status_pagamento: str | None = None
    contrato_aceito: bool | None = None
    agendamento: str | None = None
    sala: str | None = None
    # Progresso do wizard de matrícula (quando situacao = Convocado)
    etapa_atual: Etapa | None = None
    acoes: list[Acao] = []
