from fastapi import APIRouter, Depends, Path

from app.api.deps import gateway
from app.core.errors import PortalError
from app.core.session import current_user
from app.schemas.candidato import CepResultado, Municipio, Uf
from app.services.lyceum import LyceumGateway

router = APIRouter(prefix="/enderecos", tags=["enderecos"], dependencies=[Depends(current_user)])


@router.get("/ufs", response_model=list[Uf])
async def ufs(gw: LyceumGateway = Depends(gateway)):
    return await gw.listar_ufs()


@router.get("/paises", response_model=list[str])
async def paises(gw: LyceumGateway = Depends(gateway)):
    return await gw.listar_paises()


@router.get("/ufs/{uf}/municipios", response_model=list[Municipio])
async def municipios(uf: str = Path(pattern=r"^[A-Za-z]{2}$"), gw: LyceumGateway = Depends(gateway)):
    return await gw.listar_municipios(uf.upper())


@router.get("/cep/{cep}", response_model=CepResultado)
async def cep(cep: str = Path(pattern=r"^\d{5}-?\d{3}$"), gw: LyceumGateway = Depends(gateway)):
    r = await gw.buscar_cep(cep)
    if not r:
        raise PortalError(404, "CEP não encontrado. Preencha o endereço manualmente.")
    return r
