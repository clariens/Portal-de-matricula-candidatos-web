from fastapi import APIRouter, Depends

from app.api.deps import gateway
from app.schemas.publico import Cabecalho
from app.services.lyceum import LyceumGateway

router = APIRouter(tags=["publico"])


@router.get("/publico/cabecalho", response_model=Cabecalho)
async def cabecalho(gw: LyceumGateway = Depends(gateway)):
    """Áreas de interesse (subgrupos de Graduação) e link de cadastro do Processo Seletivo. Não exige login."""
    return await gw.cabecalho()
