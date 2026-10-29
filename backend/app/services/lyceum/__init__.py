import httpx

from app.config import Settings
from app.services.lyceum.base import LyceumGateway
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
        raise RuntimeError(f"Configure no backend/.env: {', '.join(faltando)}")
    return TechneGateway(settings, client)


__all__ = ["LyceumGateway", "TechneGateway", "build_gateway"]
