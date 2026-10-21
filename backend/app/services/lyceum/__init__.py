import httpx

from app.config import Settings
from app.services.lyceum.base import LyceumGateway
from app.services.lyceum.mock import MockGateway
from app.services.lyceum.techne import TechneGateway


def build_gateway(settings: Settings, client: httpx.AsyncClient) -> LyceumGateway:
    if settings.lyceum_mode == "techne":
        return TechneGateway(settings, client)
    return MockGateway()


__all__ = ["LyceumGateway", "MockGateway", "TechneGateway", "build_gateway"]
