"""Pagamento (etapa 2 do legado / etapa 3 do wizard).

Fase 1: só Boleto e PIX. Cartão aparece como indisponível até existir gateway com
tokenização (PCI): dados de cartão NUNCA passam pelo BFF.

No legado (/r/pagamentoIngresso) os planos vêm como "planoPadrao:codigoPlano:formaPagamento:numParcelas"
(ex.: "N:PG_BOLETO:Boleto:6") e a página não informa valores; por isso valor_parcela/valor_total são opcionais.
"""

from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.core.validators import EMAIL_RE, cnpj_valido, cpf_valido, digits
from app.schemas.base import ApiModel
from app.schemas.candidato import ESTADOS_CIVIS, Endereco

TipoResp = Literal["Pessoa", "OutraPessoa", "Empresa"]
Forma = Literal["Boleto", "PIX", "Cartao"]


class Plano(ApiModel):
    codigo: str  # identificador do plano (no legado, o valor completo "N:PG_BOLETO:Boleto:6")
    forma_pagamento: Forma
    nome: str
    descricao: str
    plano_padrao: str = "N"
    num_parcelas: int
    valor_parcela: float | None = None
    valor_total: float | None = None
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
    desconto_valor: float | None = None
    planos: list[Plano] | None = None


class Responsavel(ApiModel):
    nome: str = Field(min_length=3, description="Nome completo ou razão social")
    documento: str = Field(description="CPF (OutraPessoa) ou CNPJ (Empresa)")
    data_nascimento: str | None = None
    sexo: Literal["M", "F", "O"] | None = None
    estado_civil: str | None = None
    rg: str | None = None
    email: str | None = None
    celular: str | None = None
    telefone: str | None = None
    inscricao_estadual: str | None = None
    inscricao_municipal: str | None = None
    endereco: Endereco

    @field_validator("email")
    @classmethod
    def _email(cls, v: str | None) -> str | None:
        if not v or not v.strip():
            return None
        if not EMAIL_RE.match(v.strip()):
            raise ValueError("E-mail inválido.")
        return v.strip()

    @field_validator("celular")
    @classmethod
    def _cel(cls, v: str | None) -> str | None:
        if not v or not digits(v):
            return None
        if len(digits(v)) != 11:
            raise ValueError("Informe DDD + 9 dígitos.")
        return digits(v)

    @field_validator("telefone")
    @classmethod
    def _tel(cls, v: str | None) -> str | None:
        if not v or not digits(v):
            return None
        if len(digits(v)) not in (10, 11):
            raise ValueError("Telefone com DDD.")
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
        r = self.responsavel
        if not r:
            raise ValueError("responsavel: Informe os dados do responsável financeiro.")
        if self.tipo_resp == "Empresa":
            if not cnpj_valido(r.documento):
                raise ValueError("responsavel.documento: CNPJ inválido.")
            return self
        # Outra pessoa: mesmos campos obrigatórios do formulário do legado
        if not cpf_valido(r.documento):
            raise ValueError("responsavel.documento: CPF do responsável inválido.")
        obrigatorios = [("dataNascimento", r.data_nascimento, "Informe a data de nascimento."),
                        ("sexo", r.sexo, "Selecione o sexo."),
                        ("estadoCivil", r.estado_civil, "Selecione o estado civil."),
                        ("email", r.email, "Informe o e-mail."),
                        ("celular", r.celular, "Informe o celular com DDD."),
                        ("telefone", r.telefone, "Informe um telefone com DDD.")]
        for campo, valor, msg in obrigatorios:
            if not valor:
                raise ValueError(f"responsavel.{campo}: {msg}")
        if r.estado_civil not in ESTADOS_CIVIS:
            raise ValueError("responsavel.estadoCivil: Estado civil inválido.")
        return self


class Cobranca(ApiModel):
    forma_pagamento: Forma
    num_parcelas: int
    valor_parcela: float | None = None
    vencimento: str | None = None
    instrucoes: str


class PagamentoResultado(ApiModel):
    situacao: str
    cobranca: Cobranca
    simulado: bool = False
    mensagem: str | None = None
