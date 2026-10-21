"""Sessão do portal: cookie httpOnly assinado com itsdangerous.

O cookie carrega só a identidade (codPessoa, login, nome) e um id de sessão aleatório (`sid`).
Toda autorização sobre inscrições é feita no servidor a partir dela: ids vindos da URL ou do corpo
nunca são aceitos como autoridade, porque o Basic de serviço do Lyceum age em nome de qualquer pessoa.

O `sid` indexa estado que fica SÓ no servidor (ex.: a sessão JSESSIONID do candidato no portal
legado, ver services/lyceum/legado.py). Ele é exposto ao gateway pela context var `sessao_atual`,
definida pela dependência `current_user` (async, para rodar no mesmo contexto da rota).
"""

import secrets
from contextvars import ContextVar
from dataclasses import dataclass

from fastapi import Depends, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings, get_settings
from app.core.errors import PortalError

COOKIE = "portal_session"
CSRF_HEADER = "x-requested-with"

sessao_atual: ContextVar[str | None] = ContextVar("sessao_atual", default=None)


@dataclass(frozen=True)
class SessionUser:
    cod_pessoa: str
    login: str
    nome: str
    email: str | None = None
    sid: str | None = None


def novo_sid() -> str:
    return secrets.token_urlsafe(24)


def _serializer(s: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(s.portal_session_secret, salt="portal-matricula")


def set_session(resp: Response, user: SessionUser, s: Settings) -> None:
    token = _serializer(s).dumps(
        {"p": user.cod_pessoa, "l": user.login, "n": user.nome, "e": user.email, "s": user.sid}
    )
    resp.set_cookie(
        COOKIE,
        token,
        max_age=s.portal_session_horas * 3600,
        httponly=True,
        secure=s.portal_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session(resp: Response) -> None:
    resp.delete_cookie(COOKIE, path="/")


def ler_sessao(request: Request, s: Settings) -> SessionUser | None:
    token = request.cookies.get(COOKIE)
    if not token:
        return None
    try:
        d = _serializer(s).loads(token, max_age=s.portal_session_horas * 3600)
    except (BadSignature, SignatureExpired):
        return None
    return SessionUser(cod_pessoa=d["p"], login=d["l"], nome=d["n"], email=d.get("e"), sid=d.get("s"))


async def current_user(request: Request, s: Settings = Depends(get_settings)) -> SessionUser:
    user = ler_sessao(request, s)
    if not user:
        raise PortalError(401, "Sessão expirada. Entre novamente.")
    sessao_atual.set(user.sid)
    return user


def require_csrf(request: Request) -> None:
    """Métodos mutáveis exigem o header X-Requested-With (bloqueia POST cross-site simples)."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and not request.headers.get(CSRF_HEADER):
        raise PortalError(403, "Requisição recusada.")
