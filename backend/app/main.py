import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, enderecos, inscricoes, meus_dados, publico
from app.config import get_settings
from app.core.errors import PortalError, portal_error_handler, validation_error_handler
from app.core.http import TLS_CONTEXT
from app.core.session import SEGREDO_MIN, ler_sessao, require_csrf
from app.services.ia_documentos import LeitorDocumentos
from app.services.lyceum import build_gateway
from app.services.lyceum.legado import COOKIE_LEGADO

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# httpx loga a URL completa de cada chamada em INFO; as rotas do Lyceum levam CPF/códigos no path.
logging.getLogger("httpx").setLevel(logging.WARNING)
FRONT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
SAUDE_CACHE_S = 30


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.portal_session_secret in ("dev-inseguro", "troque-este-segredo"):
        raise RuntimeError("Defina a variável PORTAL_SESSION_SECRET (local: backend/.env; Vercel: Settings → Environment Variables)")
    if len(s.portal_session_secret) < SEGREDO_MIN:
        # assina a sessão e cifra a sessão do legado, as referências e os selos: curto, dá para quebrar offline
        raise RuntimeError(f"PORTAL_SESSION_SECRET precisa ter pelo menos {SEGREDO_MIN} caracteres. Gere com: "
                           'python -c "import secrets; print(secrets.token_urlsafe(48))"')
    # Os testes automáticos trocam a fábrica por um dublê (backend/tests/fake_lyceum.py); o app só conhece o Lyceum real
    fabrica = getattr(app.state, "gateway_factory", build_gateway)
    async with httpx.AsyncClient(verify=TLS_CONTEXT) as client:
        app.state.gateway = fabrica(s, client)
        # conferência de documentos com IA (Claude) só com chave configurada e ativada
        app.state.leitor = LeitorDocumentos(s) if s.ia_documentos_ativa and s.anthropic_api_key else None
        app.state.tentativas_ia = {}
        logging.getLogger("portal").info(
            "Portal iniciado | Lyceum %s (login: %s) | conferência de documentos: %s",
            s.lyceum_api_base_url or "-", s.lyceum_auth_modo,
            f"IA ({s.ia_documentos_modelo}, teto US${s.ia_documentos_limite_diario_usd:.2f}/dia)" if app.state.leitor
            else "navegador (OCR local)")
        yield


class SessaoLegadoNoCookie:
    """Carrega a sessão do legado do cookie criptografado no início da requisição e grava a versão nova na
    resposta (Set-Cookie). Nenhuma instância guarda estado: a próxima requisição pode cair em qualquer uma."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        gw = getattr(scope["app"].state, "gateway", None) if scope["type"] == "http" else None
        sessoes = getattr(getattr(gw, "legado", None), "sessoes", None)
        if not sessoes or not sessoes.no_cookie or not scope["path"].startswith("/api/"):
            await self.app(scope, receive, send)
            return
        req = sessoes.iniciar()
        request = Request(scope)
        user = ler_sessao(request, get_settings())
        if user and user.sid:
            sessoes.carregar(req, user.sid, request.cookies.get(COOKIE_LEGADO))
        concluido = False

        async def enviar(msg):
            nonlocal concluido
            if msg["type"] == "http.response.start" and not concluido:
                concluido = True
                cabecalhos = list(msg.get("headers", []))
                cabecalhos += [(b"set-cookie", c.encode("latin-1")) for c in sessoes.concluir(req)]
                msg = {**msg, "headers": cabecalhos}
            await send(msg)

        try:
            await self.app(scope, receive, enviar)
        finally:
            if not concluido:
                sessoes.concluir(req)


class _CorpoGrande(Exception):
    pass


class LimiteDoCorpo:
    """Recusa (413) corpo acima de PORTAL_UPLOAD_MAX_MB + 1 MB antes de o multipart ser lido para a memória ou o
    disco: o limite por arquivo das rotas só valeria depois de o corpo inteiro chegar. Confere o Content-Length e
    conta os bytes recebidos (corpo sem Content-Length)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limite = (get_settings().portal_upload_max_mb + 1) * 1024 * 1024
        declarado = dict(scope.get("headers") or []).get(b"content-length")
        if declarado is not None and (not declarado.isdigit() or int(declarado) > limite):
            await self._recusar(send)
            return
        recebido, iniciado = 0, False

        async def receber():
            nonlocal recebido
            msg = await receive()
            if msg["type"] == "http.request":
                recebido += len(msg.get("body", b""))
                if recebido > limite:
                    raise _CorpoGrande
            return msg

        async def enviar(msg):
            nonlocal iniciado
            iniciado = iniciado or msg["type"] == "http.response.start"
            await send(msg)

        try:
            await self.app(scope, receber, enviar)
        except _CorpoGrande:
            if not iniciado:
                await self._recusar(send)

    @staticmethod
    async def _recusar(send):
        mb = get_settings().portal_upload_max_mb
        await JSONResponse({"erro": {"mensagem": f"Arquivo acima de {mb} MB.", "campos": {"arquivo": "Arquivo grande demais."}}},
                           status_code=413)({"type": "http"}, None, send)


app = FastAPI(
    title="Portal de Matrícula do Candidato — BFF",
    version="0.1.0",
    lifespan=lifespan,
    # Swagger só quando ligado (PORTAL_API_DOCS=true, em desenvolvimento): em produção não expõe o mapa da API
    docs_url="/api/docs" if get_settings().portal_api_docs else None,
    openapi_url="/api/openapi.json" if get_settings().portal_api_docs else None,
)
app.add_exception_handler(PortalError, portal_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-Requested-With"],
)

app.add_middleware(SessaoLegadoNoCookie)
app.add_middleware(LimiteDoCorpo)  # o último adicionado roda primeiro: recusa antes de qualquer leitura

api_deps = [Depends(require_csrf)]
for r in (auth.router, enderecos.router, inscricoes.router, meus_dados.router, publico.router):
    app.include_router(r, prefix="/api/v1", dependencies=api_deps)


@app.get("/api/v1/recursos", tags=["infra"])
async def recursos(request: Request):
    """Recursos ligados neste ambiente (o front escolhe o fluxo de conferência de documentos)."""
    leitor = getattr(request.app.state, "leitor", None)
    return {"conferenciaDocumentos": "ia" if leitor else "navegador"}


@app.get("/api/v1/health", tags=["infra"])
async def health(request: Request):
    # público: guarda o resultado por 30 s para não virar um jeito de martelar o Lyceum
    saude = getattr(request.app.state, "saude", None)
    if saude is None or time.monotonic() - saude[0] > SAUDE_CACHE_S:
        saude = request.app.state.saude = (time.monotonic(), await request.app.state.gateway.ping())
    ok = saude[1]
    return JSONResponse({"status": "ok" if ok else "degradado", "lyceum": ok},
                        status_code=200 if ok else 503)


# Em produção o BFF também serve o build do front (mesma origem → cookie SameSite simples).
if FRONT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONT_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"erro": {"mensagem": "Rota não encontrada.", "campos": {}}}, status_code=404)
        f = FRONT_DIST / full_path
        if full_path and f.is_file() and FRONT_DIST in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(FRONT_DIST / "index.html")
