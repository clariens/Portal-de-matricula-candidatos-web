from pydantic import Field

from app.schemas.base import ApiModel


class LoginIn(ApiModel):
    login: str = Field(min_length=3, max_length=120, description="E-mail ou CPF")
    senha: str = Field(min_length=1, max_length=200)


class Pessoa(ApiModel):
    cod_pessoa: str
    login: str
    nome: str
    email: str | None = None
    cpf: str | None = None
