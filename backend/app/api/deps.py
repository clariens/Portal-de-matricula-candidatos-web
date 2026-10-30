from fastapi import Depends, Path, Request

from app.config import Settings, get_settings
from app.core.errors import PortalError
from app.core.referencia import REF_PATTERN, cod_da_ref, ref_inscricao
from app.core.session import SessionUser, current_user
from app.schemas.inscricao import Inscricao
from app.services.lyceum import LyceumGateway


def gateway(request: Request) -> LyceumGateway:
    return request.app.state.gateway


async def inscricao_autorizada(
    ref: str = Path(pattern=REF_PATTERN, description="Referência opaca da inscrição (campo `ref` do histórico)"),
    user: SessionUser = Depends(current_user),
    gw: LyceumGateway = Depends(gateway),
    s: Settings = Depends(get_settings),
) -> Inscricao:
    """Garante que a inscrição da URL pertence à pessoa da sessão.

    A URL traz uma referência criptografada (app/core/referencia.py), não o número da inscrição. O Basic de serviço
    do Lyceum aceita qualquer codCandidato; esta checagem é a única barreira contra acesso a inscrições de terceiros.
    """
    cod = cod_da_ref(s, user, ref)
    if cod:
        for i in await gw.listar_inscricoes(user.cod_pessoa):
            if i.cod_candidato == cod:
                i.ref = ref
                return i
    raise PortalError(404, "Inscrição não encontrada.")


def com_ref(itens: list[Inscricao], user: SessionUser, s: Settings) -> list[Inscricao]:
    """Preenche a referência opaca que o front usa nas URLs."""
    for i in itens:
        i.ref = ref_inscricao(s, user, i.cod_candidato)
    return itens
