"""Selo de documento conferido.

Os anexos ficam no navegador do candidato até o envio final (o servidor não guarda estado). Quando o portal
confere um arquivo, devolve um selo assinado com: inscrição, tipo, hash SHA-256 do arquivo, nome e o resultado
da conferência. No envio final o navegador manda o arquivo de volta com o selo; o servidor recalcula o hash e
aceita só se bater. Assim ninguém troca o arquivo depois da conferência nem forja o resultado da IA.
"""

import hashlib

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings
from app.core.errors import PortalError
from app.schemas.documento import OcrResultado

VALIDADE_SELO = 24 * 3600  # s; depois disso o candidato anexa de novo


def _ser(s: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(s.portal_session_secret, salt="selo-documento")


def emitir_selo(s: Settings, cod_candidato: str, tipo: str, nome: str, conteudo: bytes,
                analise: OcrResultado | None) -> str:
    return _ser(s).dumps({"c": cod_candidato, "t": tipo, "n": nome, "h": hashlib.sha256(conteudo).hexdigest(),
                          "a": analise.model_dump(mode="json") if analise else None})


def verificar_selo(s: Settings, selo: str, cod_candidato: str, tipo: str,
                   conteudo: bytes) -> tuple[str, OcrResultado | None]:
    """Devolve (nome, resultado da conferência) ou erro 422 se o selo não vale para este arquivo."""
    try:
        d = _ser(s).loads(selo, max_age=VALIDADE_SELO)
    except SignatureExpired:
        raise PortalError(422, "A conferência deste documento venceu. Anexe o arquivo de novo.",
                          {f"documento.{tipo}": "Anexe de novo."}) from None
    except BadSignature:
        d = None
    if not d or d.get("c") != cod_candidato or d.get("t") != tipo or d.get("h") != hashlib.sha256(conteudo).hexdigest():
        raise PortalError(422, "Este arquivo não é o que foi conferido. Anexe o documento de novo.",
                          {f"documento.{tipo}": "Anexe de novo."})
    return d["n"], OcrResultado.model_validate(d["a"]) if d.get("a") else None
