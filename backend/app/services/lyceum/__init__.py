import httpx

from app.config import Settings
from app.services.lyceum.base import LyceumGateway
from app.services.lyceum.legado import SessoesLegado
from app.services.lyceum.techne import TechneGateway


def build_gateway(settings: Settings, client: httpx.AsyncClient) -> LyceumGateway:
    """O portal só fala com o Lyceum real (não há modo de demonstração)."""
    faltando = [nome for nome, valor in (
        ("LYCEUM_API_BASE_URL", settings.lyceum_api_base_url),
        ("LYCEUM_API_BASIC_USER", settings.lyceum_api_basic_user),
        ("LYCEUM_API_BASIC_PASSWORD", settings.lyceum_api_basic_password),
        ("LYCEUM_LEGADO_BASE_URL", settings.lyceum_legado_base_url if settings.lyceum_auth_modo == "legado" else "-"),
    ) if not valor]
    if faltando:
        # Falha ao iniciar, com o nome do que falta (ex.: servidor iniciado fora da pasta backend, sem ler o .env)
        raise RuntimeError(f"Defina as variáveis {', '.join(faltando)} (local: backend/.env; Vercel: Settings → Environment Variables)")
    # sessão do legado em cookie criptografado no navegador: nenhuma instância guarda estado (Vercel)
    sessoes = SessoesLegado(settings.portal_session_secret, settings.portal_cookie_secure)
    return TechneGateway(settings, client, sessoes)


__all__ = ["LyceumGateway", "TechneGateway", "build_gateway"]
