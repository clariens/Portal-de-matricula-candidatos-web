"""Meus dados: contato, endereço e senha de quem está logado (tela "Meus Dados" do Processo Seletivo).

A pessoa vem sempre da sessão: o navegador nunca informa de quem são os dados.
"""

from fastapi import APIRouter

from app.api.inscricoes import Gw, User
from app.core.session import SessionUser
from app.schemas.meus_dados import AlterarSenhaIn, Mensagem, MeusDados, MeusDadosUpdate
from app.services.lyceum import LyceumGateway

router = APIRouter(tags=["meus-dados"])


@router.get("/meus-dados", response_model=MeusDados)
async def obter(user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.meus_dados(user.cod_pessoa)


@router.put("/meus-dados", response_model=MeusDados)
async def salvar(body: MeusDadosUpdate, user: SessionUser = User, gw: LyceumGateway = Gw):
    return await gw.salvar_meus_dados(user.cod_pessoa, body)


@router.post("/meus-dados/senha", response_model=Mensagem)
async def alterar_senha(body: AlterarSenhaIn, user: SessionUser = User, gw: LyceumGateway = Gw):
    await gw.alterar_senha(user.cod_pessoa, body.senha_atual, body.nova_senha)
    return Mensagem(mensagem="Senha alterada. Use a nova senha no próximo acesso.")
