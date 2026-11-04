from pydantic import Field, field_validator

from app.core.validators import login_normalizado
from app.schemas.base import ApiModel


class LoginIn(ApiModel):
    login: str = Field(min_length=3, max_length=120, description="E-mail ou CPF (com ou sem pontuação)")
    senha: str = Field(min_length=1, max_length=200)

    @field_validator("login")
    @classmethod
    def _cpf_sem_pontuacao(cls, v: str) -> str:
        return login_normalizado(v)


class Pessoa(ApiModel):
    cod_pessoa: str
    login: str
    nome: str
    email: str | None = None
    cpf: str | None = None
