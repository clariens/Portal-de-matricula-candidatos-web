# Portal de Matrícula do Candidato — Clariens

Substitui o portal legado do Processo Seletivo (`/processo-seletivo`, Java EE + jQuery) por uma SPA com wizard de matrícula,
integrada ao Lyceum **somente pela API REST Techne v2**, através de um BFF que guarda a credencial de serviço.

```
Navegador (React SPA)  ── cookie httpOnly ──▶  BFF FastAPI /api/v1  ── Basic de serviço ──▶  Lyceum Techne v2
   OCR local (tesseract.js)
```

Fluxo do candidato: **Login → Minhas inscrições → Dados → Documentos (OCR) → Pagamento → Conclusão (contrato Clicksign)**.

| Pasta | Conteúdo |
|---|---|
| [backend/](backend/) | BFF FastAPI + httpx, `LyceumGateway` com implementações `mock` e `techne` |
| [frontend/](frontend/) | React 18 + TypeScript + Vite, visual portado do protótipo |
| [docs/](docs/) | Arquitetura, integração Techne, contrato da API, segurança, OCR, deploy |
| [CHECKLIST.md](CHECKLIST.md) | Andamento por fase |
| [CHANGELOG.md](CHANGELOG.md) | Histórico de versões |

## Pré-requisitos
- Python 3.11+ e Node 20+

## Rodar localmente (modo mock, sem Lyceum)

```bash
# backend
cd backend
python -m venv .venv
.venv/Scripts/activate            # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env              # LYCEUM_MODE=mock
python -m uvicorn app.main:app --reload     # http://127.0.0.1:8000/api/docs
# (use "python -m uvicorn": nas máquinas Clariens o uvicorn.exe da .venv é bloqueado com "Acesso negado")

# frontend (outro terminal)
cd frontend
npm install                       # o postinstall copia os assets do OCR para public/ocr
npm run dev                       # http://localhost:5173 (proxy /api → :8000)
```

Login de demonstração no modo mock: **CPF `123.456.789-09`**, senha **`demonstracao`**. Cupom de teste: `CLARIENS10`.

## Rodar contra o Lyceum (modo techne)
No `backend/.env`: `LYCEUM_MODE=techne`, `LYCEUM_API_BASE_URL`, `LYCEUM_API_BASIC_USER`, `LYCEUM_API_BASIC_PASSWORD` e um
`PORTAL_SESSION_SECRET` forte. Hoje só o **login** está ligado ao Techne v2. As outras rotas respondem **501** até
seus endpoints serem mapeados. Ver [docs/integracao-techne.md](docs/integracao-techne.md).

## Testes

```bash
cd backend && .venv/Scripts/python -m pytest      # 26 testes (fluxo mock, segurança, TechneGateway com respx)
cd frontend && npm test                           # máscaras, CPF/CNPJ, regras do OCR
cd frontend && npx playwright install chromium && npm run e2e   # fluxo completo no navegador com OCR real
```

## Contrato front ⇄ BFF
Os tipos TypeScript são gerados do OpenAPI do FastAPI:

```bash
cd backend && .venv/Scripts/python scripts/export_openapi.py
cd frontend && npm run gen:api     # gera src/api/schema.d.ts
```
