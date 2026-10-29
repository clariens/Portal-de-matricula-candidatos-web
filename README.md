# Portal de Matrícula do Candidato — Clariens

Substitui o portal legado do Processo Seletivo (`/processo-seletivo`, Java EE + jQuery) por uma SPA com wizard de
matrícula. O navegador fala só com um BFF, que fala com o Lyceum.

```
Navegador (React SPA)  ── cookies httpOnly ──▶  BFF FastAPI /api/v1  ──▶  Processo Seletivo (legado, sessão do candidato)
  anexos no IndexedDB                              sem estado entre          + API Techne v2 (Basic de serviço)
                                                   requisições               + Claude (conferência de documentos)
```

Fluxo do candidato: **Login → Minhas inscrições → Dados → Documentos (conferência por IA) → Pagamento → Conclusão**.

| Parte | Situação (Lyceum DEV) |
|---|---|
| Login, histórico, esqueci minha senha, cabeçalho | ✅ funcionando |
| Dados e Documentos | ✅ leitura e gravação reais |
| Pagamento | ⚠ planos e cupom reais; confirmação em simulação |
| Conclusão | ❌ ainda não ligada ao Lyceum |
| Áreas de interesse e Cadastre-se | ⚠ abrem as páginas do legado; telas próprias são a próxima fase |

**Próximas etapas:** [docs/roadmap.md](docs/roadmap.md): (A) pagamento de ponta a ponta e conclusão; (B) telas
próprias das áreas de interesse, busca, oferta e cadastro.

| Pasta | Conteúdo |
|---|---|
| [backend/](backend/) | BFF FastAPI + httpx, `LyceumGateway` (Processo Seletivo legado + API Techne v2), conferência por IA |
| [frontend/](frontend/) | React 18 + TypeScript + Vite, visual portado do protótipo |
| [docs/](docs/) | Roadmap, arquitetura, integração, contrato da API, segurança, conferência de documentos, deploy, cabeçalho |
| [CHECKLIST.md](CHECKLIST.md) | Andamento por fase |
| [CHANGELOG.md](CHANGELOG.md) | Histórico de versões |

## Pré-requisitos
- Python 3.12+ (a Vercel usa 3.14) e Node 20+

## Rodar localmente (contra o Lyceum DEV)

```bash
# backend
cd backend
python -m venv .venv
.venv/Scripts/activate            # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env              # preencha credenciais da API e PORTAL_SESSION_SECRET
python -m uvicorn app.main:app --reload     # http://127.0.0.1:8000/api/docs
# (use "python -m uvicorn": nas máquinas Clariens o uvicorn.exe da .venv é bloqueado com "Acesso negado")

# frontend (outro terminal)
cd frontend
npm install                       # o postinstall copia os assets do OCR para public/ocr
npm run dev                       # http://localhost:5173 (proxy /api → :8000)
```

O portal **não tem modo de demonstração**: sempre fala com o Lyceum configurado no `backend/.env`
(`LYCEUM_API_BASE_URL`, `LYCEUM_API_BASIC_USER`, `LYCEUM_API_BASIC_PASSWORD`, `LYCEUM_LEGADO_BASE_URL` e um
`PORTAL_SESSION_SECRET` forte). Sem essas variáveis o servidor **não inicia** e diz o que falta. O `backend/.env` é
lido de qualquer pasta. Entre com um candidato real do ambiente (CPF e senha do Processo Seletivo).

Gravações irreversíveis ficam em simulação por padrão: `LYCEUM_DOCUMENTOS_MODO` e `LYCEUM_PAGAMENTO_MODO`
(`simular` | `enviar`). Ver [docs/integracao-techne.md](docs/integracao-techne.md) e, para publicar,
[docs/deploy.md](docs/deploy.md) (Vercel).

## Testes

```bash
cd backend && .venv/Scripts/python -m pytest      # 118 testes: API com dublê do Lyceum (tests/fake_lyceum.py), legado e Techne com respx
cd frontend && npm test                           # máscaras, CPF/CNPJ, regras do OCR
cd frontend && npx playwright install chromium && npm run e2e   # fluxo completo no navegador com o dublê do Lyceum (só teste)
```

## Contrato front ⇄ BFF
Os tipos TypeScript são gerados do OpenAPI do FastAPI:

```bash
cd backend && .venv/Scripts/python scripts/export_openapi.py
cd frontend && npm run gen:api     # gera src/api/schema.d.ts
```
