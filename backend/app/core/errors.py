"""Erros do portal e tradução das mensagens do Lyceum.

Formato de erro devolvido ao front (status HTTP + corpo):
    { "erro": { "mensagem": "...", "campos": { "cpf": "CPF inválido." } } }
"""

import re

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class PortalError(Exception):
    def __init__(self, status: int, mensagem: str, campos: dict[str, str] | None = None):
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem
        self.campos = campos or {}


class NaoConfigurado(PortalError):
    def __init__(self, variavel: str):
        super().__init__(503, f"Variável {variavel} não configurada no servidor")


class LyceumIndisponivel(PortalError):
    def __init__(self, mensagem: str = "Não foi possível conectar ao Lyceum. Tente novamente em instantes."):
        super().__init__(502, mensagem)


class EndpointNaoMapeado(PortalError):
    """Necessidade sem endpoint Techne v2 identificado (ver docs/integracao-techne.md)."""

    def __init__(self, necessidade: str):
        super().__init__(501, f"Integração ainda não disponível: {necessidade}")


GENERIC_LOGIN = "Usuário ou senha inválidos."
_CAMPO_RE = re.compile(r"^([A-Za-z][\w.]*): (.+)$", re.DOTALL)


def sanitize_lyceum_error(msg: str | None, fallback: str = GENERIC_LOGIN) -> str:
    """Limpa mensagens do Lyceum antes de mostrar ao usuário (mesma regra do portal ENAMED)."""
    if not msg:
        return fallback
    text = str(msg).replace("TechneApplicationException:", "").strip()
    text = text.split("|", 1)[0].strip()
    text = re.sub(r"^erro de autentica[çc][ãa]o:\s*", "", text, flags=re.IGNORECASE)
    low = text.lower()
    if not text or "traceback" in low or "basic" in low or "exception" in low or "\tat " in text:
        return fallback
    return text[:300]


def _body(mensagem: str, campos: dict[str, str] | None = None) -> dict:
    return {"erro": {"mensagem": mensagem, "campos": campos or {}}}


async def portal_error_handler(_: Request, exc: PortalError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=_body(exc.mensagem, exc.campos))


async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    campos: dict[str, str] = {}
    for e in exc.errors():
        loc = [str(p) for p in e.get("loc", []) if p not in ("body", "query", "path")]
        key = ".".join(loc) or "_"
        msg = e.get("msg", "Valor inválido.").removeprefix("Value error, ")
        # model_validator sinaliza o campo com o prefixo "campo: mensagem"
        m = _CAMPO_RE.match(msg)
        if m:
            key = f"{key}.{m[1]}" if key != "_" else m[1]
            msg = m[2]
        if e.get("type") == "missing":
            msg = "Campo obrigatório."
        campos.setdefault(key, msg)
    return JSONResponse(status_code=422, content=_body("Revise os campos destacados.", campos))
