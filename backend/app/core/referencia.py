"""Referência opaca da inscrição nas URLs (telas e API).

O número da inscrição não aparece na barra de endereço, no histórico do navegador, em links compartilhados nem nos
logs de acesso. Em vez dele, vai uma referência criptografada com AES-SIV (determinística: a mesma inscrição gera a
mesma referência durante a sessão, então dá para recarregar a página) e amarrada à sessão de quem entrou: fora dela
não abre nada e não revela o número. A autorização continua em `inscricao_autorizada` (a inscrição tem que ser da
pessoa logada); a referência só esconde o número.
"""

import base64
import hashlib

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV

from app.config import Settings
from app.core.session import SessionUser

REF_PATTERN = r"^[A-Za-z0-9_-]{20,120}$"


def _aead(s: Settings) -> AESSIV:
    return AESSIV(hashlib.sha512(b"ref-inscricao:" + s.portal_session_secret.encode()).digest())


def _contexto(user: SessionUser) -> list[bytes]:
    return [f"{user.sid or ''}|{user.cod_pessoa}".encode()]


def ref_inscricao(s: Settings, user: SessionUser, cod_candidato: str) -> str:
    bruto = _aead(s).encrypt(cod_candidato.encode(), _contexto(user))
    return base64.urlsafe_b64encode(bruto).rstrip(b"=").decode()


def cod_da_ref(s: Settings, user: SessionUser, ref: str) -> str | None:
    """Número da inscrição, ou None se a referência for inválida ou de outra sessão."""
    try:
        bruto = base64.urlsafe_b64decode(ref + "=" * (-len(ref) % 4))
        cod = _aead(s).decrypt(bruto, _contexto(user)).decode()
    except (InvalidTag, ValueError):
        return None
    return cod if cod.isdigit() else None
