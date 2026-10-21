"""Dados do candidato (etapa 1).

Substitui o payload de /r/ingresso/atualizar.json: sem campos duplicados
(codCandidato/codigoCandidato, pais/paisSelect, municipio/enderecoMunicipioCode, cep/cepEs),
sem flags obrigatorio* e sem ids vindos do cliente (eles vêm da sessão + URL autorizada).
"""

from datetime import date
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.core.validators import EMAIL_RE, cpf_valido, digits, mask_cep, mask_cpf, parse_data_br
from app.schemas.base import ApiModel

# Valores aceitos pelo Lyceum (select estadoCivil de /r/ingresso e /v2/comum/estados-civis)
ESTADOS_CIVIS = ["Solteiro", "Casado", "Divorciado", "Viúvo", "União Estável", "Marital", "Separado",
                 "Separado Consensualmente", "Separado Judicialmente"]
SEXOS = {"F": "Feminino", "M": "Masculino", "O": "Outros"}


class Endereco(ApiModel):
    pais: str = "BRASIL"
    cep: str
    uf: str = Field(min_length=2, max_length=2)
    municipio: str = Field(min_length=1)
    municipio_codigo: str | None = None
    endereco: str = Field(min_length=1)
    numero: str = Field(min_length=1, max_length=20)
    complemento: str | None = None
    bairro: str = Field(min_length=1)

    @field_validator("cep")
    @classmethod
    def _cep(cls, v: str) -> str:
        if len(digits(v)) != 8:
            raise ValueError("CEP com 8 dígitos.")
        return mask_cep(v)

    @field_validator("uf")
    @classmethod
    def _uf(cls, v: str) -> str:
        return v.upper()


class CandidatoBase(ApiModel):
    nome_completo: str
    data_nascimento: str = Field(description="dd/mm/aaaa")
    sexo: Literal["M", "F", "O"] | None = None  # pode vir vazio do Lyceum; obrigatório ao salvar
    tipo_doc: Literal["cpf", "passaporte"] = "cpf"
    cpf: str | None = None
    identidade: str | None = None
    passaporte: str | None = None
    estado_civil: str | None = None  # idem
    email_pessoal: str
    celular: str
    telefone: str | None = None
    pais_nascimento: str | None = "Brasil"
    municipio_nascimento: str | None = None
    endereco: Endereco


class Candidato(CandidatoBase):
    cod_candidato: str
    cod_concurso: str


class CandidatoUpdate(CandidatoBase):
    # valida também os campos omitidos (sexo/estado civil têm default None no modelo base)
    model_config = ConfigDict(**CandidatoBase.model_config, validate_default=True)

    @field_validator("nome_completo")
    @classmethod
    def _nome(cls, v: str) -> str:
        v = " ".join(v.split())
        if len(v.split(" ")) < 2:
            raise ValueError("Informe nome e sobrenome.")
        return v

    @field_validator("data_nascimento")
    @classmethod
    def _nasc(cls, v: str) -> str:
        try:
            d = parse_data_br(v)
        except ValueError:
            raise ValueError("Use o formato dd/mm/aaaa.") from None
        hoje = date.today()
        idade = hoje.year - d.year - ((hoje.month, hoje.day) < (d.month, d.day))
        if not 14 <= idade <= 100:
            raise ValueError("Data de nascimento fora do intervalo esperado.")
        return v

    @field_validator("email_pessoal")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip()
        if not EMAIL_RE.match(v):
            raise ValueError("E-mail inválido.")
        return v

    @field_validator("celular")
    @classmethod
    def _cel(cls, v: str) -> str:
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

    @field_validator("estado_civil")
    @classmethod
    def _ec(cls, v: str | None) -> str:
        if not v:
            raise ValueError("Selecione o estado civil.")
        if v not in ESTADOS_CIVIS:
            raise ValueError("Estado civil inválido.")
        return v

    @field_validator("sexo")
    @classmethod
    def _sexo(cls, v: str | None) -> str:
        if not v:
            raise ValueError("Selecione o sexo.")
        return v

    @model_validator(mode="after")
    def _doc(self):
        if self.tipo_doc == "cpf":
            if not cpf_valido(self.cpf):
                raise ValueError("cpf: CPF inválido. Confira os dígitos.")
            self.cpf = mask_cpf(self.cpf or "")
        elif not (self.passaporte or "").strip():
            raise ValueError("passaporte: Informe o número do passaporte.")
        return self


class Uf(ApiModel):
    sigla: str
    nome: str


class Municipio(ApiModel):
    codigo: str
    nome: str


class CepResultado(ApiModel):
    cep: str
    uf: str
    municipio: str
    municipio_codigo: str | None = None
    bairro: str | None = None
    endereco: str | None = None
