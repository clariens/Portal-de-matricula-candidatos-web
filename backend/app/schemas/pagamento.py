"""Pagamento (etapa 2 do legado / etapa 3 do wizard).

Fase 1: só Boleto e PIX. Cartão aparece como indisponível até existir gateway com
tokenização (PCI): dados de cartão NUNCA passam pelo BFF.
"""

from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.core.validators import EMAIL_RE, cnpj_valido, cpf_valido, digits
from app.schemas.base import ApiModel
from app.schemas.candidato import Endereco

TipoResp = Literal["Pessoa", "OutraPessoa", "Empresa"]
Forma = Literal["Boleto", "PIX", "Cartao"]


class Plano(ApiModel):
    codigo: str  # ex.: PG_PIX
    forma_pagamento: Forma
    nome: str
    descricao: str
    plano_padrao: str = "N"
    num_parcelas: int
    valor_parcela: float
    valor_total: float
    disponivel: bool = True
    motivo_indisponivel: str | None = None
    tag: str | None = None


class OpcoesPagamento(ApiModel):
    tipos_responsavel: list[TipoResp]
    planos: list[Plano]
    cupom_aplicado: str | None = None


class CupomIn(ApiModel):
    codigo: str = Field(min_length=2, max_length=40)


class CupomResultado(ApiModel):
    valido: bool
    mensagem: str
    desconto_percentual: float | None = None
    planos: list[Plano] | None = None


class Responsavel(ApiModel):
    nome: str = Field(min_length=3, description="Nome completo ou razão social")
    documento: str = Field(description="CPF (OutraPessoa) ou CNPJ (Empresa)")
    data_nascimento: str | None = None
    sexo: Literal["M", "F", "O"] | None = None
    estado_civil: str | None = None
    email: str
    celular: str
    telefone: str | None = None
    endereco: Endereco

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        if not EMAIL_RE.match(v.strip()):
            raise ValueError("E-mail inválido.")
        return v.strip()

    @field_validator("celular")
    @classmethod
    def _cel(cls, v: str) -> str:
        if len(digits(v)) != 11:
            raise ValueError("Informe DDD + 9 dígitos.")
        return digits(v)


class PagamentoIn(ApiModel):
    tipo_resp: TipoResp
    responsavel: Responsavel | None = None
    codigo_plano: str
    voucher: str | None = None

    @model_validator(mode="after")
    def _check(self):
        if self.tipo_resp == "Pessoa":
            self.responsavel = None
            return self
        if not self.responsavel:
            raise ValueError("responsavel: Informe os dados do responsável financeiro.")
        doc = self.responsavel.documento
        if self.tipo_resp == "OutraPessoa" and not cpf_valido(doc):
            raise ValueError("responsavel.documento: CPF do responsável inválido.")
        if self.tipo_resp == "Empresa" and not cnpj_valido(doc):
            raise ValueError("responsavel.documento: CNPJ inválido.")
        if self.tipo_resp == "OutraPessoa" and not self.responsavel.data_nascimento:
            raise ValueError("responsavel.dataNascimento: Informe a data de nascimento.")
        return self


class Cobranca(ApiModel):
    forma_pagamento: Forma
    num_parcelas: int
    valor_parcela: float
    vencimento: str | None = None
    instrucoes: str


class PagamentoResultado(ApiModel):
    situacao: str
    cobranca: Cobranca
