from fastapi import Depends, Path, Request

from app.core.errors import PortalError
from app.core.session import SessionUser, current_user
from app.schemas.inscricao import Inscricao
from app.services.lyceum import LyceumGateway


def gateway(request: Request) -> LyceumGateway:
    return request.app.state.gateway


async def inscricao_autorizada(
    cod_candidato: str = Path(pattern=r"^\d{6,20}$"),
    user: SessionUser = Depends(current_user),
    gw: LyceumGateway = Depends(gateway),
) -> Inscricao:
    """Garante que a inscrição da URL pertence à pessoa da sessão.

    O Basic de serviço do Lyceum aceita qualquer codCandidato; esta checagem é a
    única barreira contra acesso a inscrições de terceiros.
    """
    for i in await gw.listar_inscricoes(user.cod_pessoa):
        if i.cod_candidato == cod_candidato:
            return i
    raise PortalError(404, "Inscrição não encontrada.")
