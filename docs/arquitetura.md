# Arquitetura

```
┌──────────────── Navegador ────────────────┐      ┌──────────── BFF (FastAPI) ────────────┐      ┌─────────────┐
│ React SPA (Vite)                          │      │ /api/v1  routers (auth, inscricoes,   │      │ Lyceum      │
│  • Login / Histórico / Wizard 4 etapas    │ HTTP │          enderecos)                   │ HTTP │ Techne v2   │
│  • OCR local: tesseract.js + pdf.js       │─────▶│ deps: sessão + inscrição autorizada   │─────▶│ (Basic de   │
│  • cookie portal_session (httpOnly)       │      │ LyceumGateway ─── TechneGateway       │      │  serviço)   │
└───────────────────────────────────────────┘      │  (API v2 + legado na sessão) ─────────│      └─────────────┘
                                                   └───────────────────────────────────────┘
```

## Decisões
| Decisão | Motivo |
|---|---|
| BFF entre o navegador e o Lyceum | A credencial Basic permite agir por qualquer pessoa e não pode ir para o front |
| Somente Techne v2, sem proxy do legado | O legado guarda estado de navegação na sessão Java (`JSESSIONID`) e depende de páginas renderizadas, o que o torna frágil para integração |
| Interface `LyceumGateway` | Routers isolados do Lyceum; os testes automáticos usam um dublê (`backend/tests/fake_lyceum.py`). Não há modo de demonstração no app |
| Contract-first (Pydantic → OpenAPI → TS) | Uma fonte de verdade, sem divergência entre front e back |
| OCR no navegador | Retorno imediato, sem custo de servidor e o arquivo não sai do dispositivo durante a leitura. É informativo: a secretaria confere |
| Mesma origem em produção (BFF serve o `dist/`) | Cookie SameSite=Lax sem CORS e deploy simples |
| Cartão desabilitado na fase 1 | PCI: dados de cartão só via tokenização do gateway |

## Backend (`backend/app`)
| Módulo | Papel |
|---|---|
| `main.py` | App, `lifespan` (cliente httpx e gateway), handlers de erro, CORS em dev, SPA estático |
| `config.py` | `Settings` (pydantic-settings, `.env`) |
| `core/session.py` | Cookie assinado, `current_user`, `require_csrf` |
| `core/errors.py` | `PortalError`, 501/502/503, `sanitize_lyceum_error`, formato `{erro:{mensagem,campos}}` |
| `core/validators.py` | CPF, CNPJ, máscaras, datas |
| `api/deps.py` | `inscricao_autorizada`: a inscrição da URL precisa pertencer à pessoa da sessão |
| `api/*.py` | Routers finos: validam a entrada e delegam ao gateway |
| `schemas/*.py` | Contrato (camelCase no JSON) |
| `services/lyceum/` | `base.py` (Protocol), `techne.py`, `legado.py`, `mappers.py`, `catalogo.py` |

## Frontend (`frontend/src`)
| Pasta | Papel |
|---|---|
| `api/` | `client.ts` (fetch, `X-Requested-With`, `ApiError` com campos, inspetor em dev), `schema.d.ts` gerado, `types.ts` |
| `components/` | `Shell` (topbar + inspetor), `auth` (contexto + `RequireAuth`), `ui` (Field, Select, Chip, Toast…), `EnderecoFields` |
| `pages/` | `Login`, `Historico`, `wizard/` (`Wizard` + 4 etapas) |
| `lib/` | `format.ts` (máscaras/validações), `ocr/analisar.ts` (regras puras), `ocr/engine.ts` (tesseract/pdf.js, carregado sob demanda) |
| `styles/app.css` | Tokens e componentes do protótipo |

## Rotas do front
| Rota | Tela |
|---|---|
| `/login` | Login |
| `/inscricoes` | Histórico |
| `/matricula/:id` | Redireciona para a etapa liberada mais adiante |
| `/matricula/:id/{dados,documentos,pagamento,conclusao}` | Wizard |

Regra das etapas (`etapasPermitidas` em `Wizard.tsx`): com situação **Convocado**, libera até a etapa atual da inscrição
(`etapaAtual`); com **Pré-Matriculado**, libera só documentos (consulta) e conclusão; nas demais situações, volta ao histórico.
