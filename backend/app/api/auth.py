from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import gateway
from app.config import Settings, get_settings
from app.core.session import (
    SessionUser,
    clear_session,
    current_user,
    ler_sessao,
    novo_sid,
    sessao_atual,
    set_session,
)
from app.schemas.auth import LoginIn, Pessoa
from app.services.lyceum import LyceumGateway

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=Pessoa)
async def login(body: LoginIn, response: Response, gw: LyceumGateway = Depends(gateway),
                s: Settings = Depends(get_settings)):
    sid = novo_sid()  # indexa o estado da sessão que fica só no servidor (ex.: sessão legada)
    sessao_atual.set(sid)
    pessoa = await gw.autenticar(body.login.strip(), body.senha)
    set_session(response, SessionUser(cod_pessoa=pessoa.cod_pessoa, login=pessoa.login, nome=pessoa.nome,
                                      email=pessoa.email, sid=sid), s)
    return pessoa


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, gw: LyceumGateway = Depends(gateway), s: Settings = Depends(get_settings)):
    user = ler_sessao(request, s)
    if user:
        sessao_atual.set(user.sid)
        await gw.sair()
    r = Response(status_code=204)
    clear_session(r)
    return r


@router.get("/me", response_model=Pessoa)
async def me(user: SessionUser = Depends(current_user)):
    return Pessoa(cod_pessoa=user.cod_pessoa, login=user.login, nome=user.nome, email=user.email)
