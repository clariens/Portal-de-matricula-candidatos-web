"""Meus dados: contato, endereço e senha da pessoa (tela "Meus Dados" do Processo Seletivo, /r/alterarDados).

Nome, CPF e data de nascimento não são alterados aqui (o legado também não deixa).
"""

from pydantic import Field, field_validator, model_validator

from app.core.validators import EMAIL_RE, digits
from app.schemas.base import ApiModel
from app.schemas.candidato import Endereco


class MeusDados(ApiModel):
    email: str
    celular: str = Field(description="DDD + número, só dígitos")
    telefone: str | None = Field(default=None, description="DDD + número, só dígitos")
    endereco: Endereco


class MeusDadosUpdate(MeusDados):
    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip()
        if not EMAIL_RE.match(v) or len(v) > 100:
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

    @model_validator(mode="after")
    def _limites(self):
        # limites do formulário do legado (alteracaoDados.js)
        e = self.endereco
        for campo, valor, maximo in (("endereco", e.endereco, 50), ("numero", e.numero, 15),
                                     ("complemento", e.complemento or "", 50), ("bairro", e.bairro, 50)):
            if len(valor) > maximo:
                raise ValueError(f"endereco.{campo}: Máximo de {maximo} caracteres.")
        return self


class AlterarSenhaIn(ApiModel):
    senha_atual: str = Field(min_length=1, max_length=40)
    nova_senha: str = Field(min_length=1, max_length=40)
    confirmacao: str

    @model_validator(mode="after")
    def _confere(self):
        if self.confirmacao != self.nova_senha:
            raise ValueError("confirmacao: As senhas não conferem.")
        if self.nova_senha == self.senha_atual:
            raise ValueError("novaSenha: A nova senha deve ser diferente da atual.")
        return self


class Mensagem(ApiModel):
    mensagem: str
