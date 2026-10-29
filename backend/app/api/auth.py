from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import gateway
from app.config import Settings, get_settings
from app.core.session import (
    SessionUser,
    clear_session,
    ler_sessao,
    novo_sid,
    sessao_atual,
    set_session,
)
from app.schemas.auth import LoginIn, Pessoa
from app.schemas.publico import RecuperarSenhaIn, RecuperarSenhaResultado
from app.services.lyceum import LyceumGateway

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=Pessoa)
async def login(body: LoginIn, response: Response, gw: LyceumGateway = Depends(gateway),
                s: Settings = Depends(get_settings)):
    sid = novo_sid()  # amarra a sessão do legado (cookie criptografado) a esta sessão do portal
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


@router.get("/me", response_model=Pessoa | None)
async def me(request: Request, s: Settings = Depends(get_settings)):
    """Quem está logado. Sem sessão responde 200 com null: abrir o site sem login não é erro (as rotas
    protegidas continuam respondendo 401)."""
    user = ler_sessao(request, s)
    if not user:
        return None
    return Pessoa(cod_pessoa=user.cod_pessoa, login=user.login, nome=user.nome, email=user.email)


@router.post("/auth/recuperar-senha", response_model=RecuperarSenhaResultado)
async def recuperar_senha(body: RecuperarSenhaIn, gw: LyceumGateway = Depends(gateway)):
    """Esqueci minha senha: o Processo Seletivo envia as instruções ao e-mail cadastrado."""
    return RecuperarSenhaResultado(mensagem=await gw.recuperar_senha(body.login))
