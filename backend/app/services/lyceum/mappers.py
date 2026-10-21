"""Tradução JSON Techne v2 → modelos do portal.

Os nomes de campo do Lyceum variam entre endpoints/versões; os mappers aceitam
várias chaves (mesma estratégia de map_academic_fields do portal ENAMED).
"""

from typing import Any

from app.core.validators import mask_cpf
from app.schemas.auth import Pessoa


def pick(d: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
    if not d:
        return default
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return default


def map_pessoa(d: dict[str, Any], login_informado: str) -> Pessoa | None:
    """Resposta de POST /v2/pessoas/autenticacao (UsuarioDTO). Retorna None se faltar identificador.

    O UsuarioDTO traz o código da pessoa em `id` e o RA em `codAluno`; também traz `password`,
    que nunca é copiado para o modelo do portal.
    """
    cod = pick(d, "pessoa", "codPessoa", "idPessoa", "codigoPessoa", "id")
    login = pick(d, "login", default=login_informado)
    if not cod or not login:
        return None
    cpf = pick(d, "cpf", "nrCpf")
    return Pessoa(
        cod_pessoa=str(cod),
        login=str(login),
        nome=str(pick(d, "name", "nome", "nomeCompleto", default=login)),
        email=pick(d, "email", "emailPessoal", "eMail"),
        cpf=mask_cpf(str(cpf)) if cpf else None,
    )


def map_pessoa_lyceum(d: dict[str, Any], login_informado: str) -> Pessoa | None:
    """Resposta de GET /v2/pessoas/idPessoa/{id}/obterPessoa (`data`, colunas de LY_PESSOA).

    A tabela traz campos de senha (resp_senha, senha_tac…): só os campos abaixo são copiados.
    """
    cod = pick(d, "pessoa")
    if not cod:
        return None
    cpf = pick(d, "cpf")
    return Pessoa(
        cod_pessoa=str(cod),
        login=login_informado,
        nome=str(pick(d, "nome_social", "nome_compl", default=login_informado)).strip(),
        email=pick(d, "e_mail"),
        cpf=mask_cpf(str(cpf)) if cpf else None,
    )


SITUACOES = {
    "convocado": "Convocado",
    "confirmado": "Confirmado",
    "pre-matriculado": "Pré-Matriculado",
    "pré-matriculado": "Pré-Matriculado",
    "pre matriculado": "Pré-Matriculado",
    "matriculado": "Matriculado",
    "cancelado": "Cancelado",
    "inscrito": "Inscrito",
}


def normalizar_situacao(v: str | None) -> str:
    return SITUACOES.get((v or "").strip().lower(), "Inscrito")
