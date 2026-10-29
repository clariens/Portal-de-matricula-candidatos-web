import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, enderecos, inscricoes
from app.config import get_settings
from app.core.errors import PortalError, portal_error_handler, validation_error_handler
from app.core.http import TLS_CONTEXT
from app.core.session import require_csrf
from app.services.ia_documentos import LeitorDocumentos
from app.services.lyceum import build_gateway

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
# httpx loga a URL completa de cada chamada em INFO; as rotas do Lyceum levam CPF/códigos no path.
logging.getLogger("httpx").setLevel(logging.WARNING)
FRONT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.portal_session_secret in ("dev-inseguro", "troque-este-segredo"):
        raise RuntimeError("Defina PORTAL_SESSION_SECRET no backend/.env")
    # Os testes automáticos trocam a fábrica por um dublê (backend/tests/fake_lyceum.py); o app só conhece o Lyceum real
    fabrica = getattr(app.state, "gateway_factory", build_gateway)
    async with httpx.AsyncClient(verify=TLS_CONTEXT) as client:
        app.state.gateway = fabrica(s, client)
        # conferência de documentos com IA (Claude) só com chave configurada e ativada
        app.state.leitor = LeitorDocumentos(s) if s.ia_documentos_ativa and s.anthropic_api_key else None
        app.state.tentativas_ia = {}
        logging.getLogger("portal").info(
            "Portal iniciado | Lyceum %s (login: %s) | conferência de documentos: %s", s.lyceum_api_base_url or "-",
            s.lyceum_auth_modo,
            f"IA ({s.ia_documentos_modelo}, teto US${s.ia_documentos_limite_diario_usd:.2f}/dia)" if app.state.leitor
            else "navegador (OCR local)")
        yield


app = FastAPI(
    title="Portal de Matrícula do Candidato — BFF",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
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

api_deps = [Depends(require_csrf)]
for r in (auth.router, enderecos.router, inscricoes.router):
    app.include_router(r, prefix="/api/v1", dependencies=api_deps)


@app.get("/api/v1/recursos", tags=["infra"])
async def recursos(request: Request):
    """Recursos ligados neste ambiente (o front escolhe o fluxo de conferência de documentos)."""
    leitor = getattr(request.app.state, "leitor", None)
    return {"conferenciaDocumentos": "ia" if leitor else "navegador"}


@app.get("/api/v1/health", tags=["infra"])
async def health(request: Request):
    ok = await request.app.state.gateway.ping()
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
