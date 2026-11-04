"""Telas públicas (sem login): cabeçalho com as áreas de interesse e recuperação de senha."""

from pydantic import Field, field_validator

from app.core.validators import login_normalizado
from app.schemas.base import ApiModel


class LinkLegado(ApiModel):
    nome: str
    url: str  # página do Processo Seletivo (legado), aberta pelo navegador


class AreaInteresse(ApiModel):
    nome: str  # ex.: "Graduação"
    itens: list[LinkLegado]


class Cabecalho(ApiModel):
    areas: list[AreaInteresse]
    cadastro_url: str


class RecuperarSenhaIn(ApiModel):
    login: str = Field(min_length=3, max_length=120, description="E-mail, CPF, RG ou passaporte cadastrado")

    @field_validator("login")
    @classmethod
    def _limpo(cls, v: str) -> str:
        v = login_normalizado(v)  # CPF com pontuação vira só os dígitos
        if len(v) < 3:
            raise ValueError("Informe o e-mail, CPF, RG ou passaporte cadastrado.")
        return v


class RecuperarSenhaResultado(ApiModel):
    mensagem: str
