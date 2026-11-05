# Arquitetura

```
┌──────────── Navegador ────────────┐        ┌────────────── BFF (FastAPI) ──────────────┐        ┌──────────────────────────┐
│ React SPA (Vite)                  │        │ /api/v1: auth, publico, inscricoes,       │        │ Processo Seletivo legado │
│ • Login, histórico, wizard        │  HTTP  │          enderecos                        │  HTTP  │ (sessão do candidato:    │
│ • anexos + selos no IndexedDB     │───────▶│ middleware: sessão do legado do cookie    │───────▶│  login, histórico, dados,│
│ • cookies httpOnly:               │        │ LyceumGateway ─── TechneGateway           │        │  documentos, pagamento)  │
│   portal_session (assinado)       │        │   ├─ ClienteLegado (legado.py)            │        ├──────────────────────────┤
│   portal_legado (criptografado)   │        │   └─ API Techne v2 (Basic de serviço)     │───────▶│ API Techne v2 (pessoa,   │
└───────────────────────────────────┘        │ conferência de documentos: Claude (IA)    │        │  CEP, tabelas)           │
                                             │ sem estado entre requisições (Vercel)     │        └──────────────────────────┘
                                             └───────────────────────────────────────────┘
```

## Decisões
| Decisão | Motivo |
|---|---|
| BFF entre o navegador e o Lyceum | A credencial Basic permite agir por qualquer pessoa e não pode ir para o front |
| Processo Seletivo legado na sessão do candidato (20/10/2026) | A API v2 só autentica aluno por RA e o usuário técnico não acessa as rotas de candidato; o legado autentica por CPF e mostra só as inscrições dele. A API v2 continua onde serve (pessoa, CEP) |
| Sem estado no servidor e sem banco (29/10/2026) | A instituição não usa Redis/banco. A sessão do legado vai num cookie criptografado e os anexos ficam no navegador com selo assinado; qualquer instância atende (Vercel). Se a sessão cair, o candidato entra de novo |
| Gravações irreversíveis em simulação por padrão | `LYCEUM_DOCUMENTOS_MODO` / `LYCEUM_PAGAMENTO_MODO`; o primeiro envio real de cada uma exige autorização |
| Conferência de documentos por IA no servidor | O OCR do navegador falhou com fotos reais. A IA lê e classifica; regras no código decidem. Só "tipo errado" impede anexar |
| Interface `LyceumGateway` | Routers isolados do Lyceum; os testes usam um dublê (`backend/tests/fake_lyceum.py`). Não há modo de demonstração |
| Contract-first (Pydantic → OpenAPI → TS) | Uma fonte de verdade, sem divergência entre front e back |
| Mesma origem (Vercel Services ou imagem única) | Cookies SameSite=Lax sem CORS |
| Cartão desabilitado na fase 1 | PCI: dados de cartão só via tokenização do gateway |

## Backend (`backend/app`)
| Módulo | Papel |
|---|---|
| `main.py` | App, `lifespan` (cliente httpx, gateway, leitor de IA), middleware `SessaoLegadoNoCookie`, handlers de erro, SPA estático |
| `config.py` | `Settings` (pydantic-settings; sempre `backend/.env`, ou `PORTAL_ENV_FILE`) |
| `core/session.py` | Cookie assinado, `current_user`, `require_csrf` |
| `core/selo.py` | Selo assinado do documento conferido (hash do arquivo + resultado), verificado no envio final |
| `core/errors.py` | `PortalError`, 501/502/503, `sanitize_lyceum_error`, formato `{erro:{mensagem,campos}}` |
| `core/validators.py` | CPF, CNPJ, máscaras, datas |
| `api/deps.py` | `inscricao_autorizada`: a inscrição da URL precisa pertencer à pessoa da sessão |
| `api/*.py` | Routers finos: validam a entrada e delegam ao gateway |
| `schemas/*.py` | Contrato (camelCase no JSON) |
| `services/lyceum/` | `base.py` (Protocol), `techne.py` (gateway), `legado.py` (cliente do Processo Seletivo: sessão em cookie, páginas, envios), `mappers.py`, `catalogo.py` |
| `services/ia_documentos.py`, `conferencia.py`, `imagens.py` | Leitura do documento pela IA, regras de conferência, compressão de fotos |

## Frontend (`frontend/src`)
| Pasta | Papel |
|---|---|
| `api/` | `client.ts` (fetch, `X-Requested-With`, `ApiError` com campos, aviso de gravação para o cache, inspetor em dev), `schema.d.ts` gerado, `types.ts` |
| `components/` | `Shell` (cabeçalho com logo, Área de interesse e Cadastre-se; logado: Minhas inscrições, Meus dados e Sair, recolhidos no botão "Menu" no celular; inspetor em dev), `auth` (contexto + `RequireAuth`), `ui`, `EnderecoFields`, `Visor`, `AssinaturaContrato` |
| `pages/` | `Login` (entrar e recuperar senha), `Historico`, `MeusDados`, `ContratoInscricao`, `DocumentosIngresso`, `wizard/` (`Wizard` + 4 etapas, `PrimeiraParcela`) |
| `lib/` | `format.ts`, `anexosLocais.ts` (IndexedDB dos anexos), `cacheTelas.ts` (cache em memória da aba), `imagem.ts`, `ocr/` (reserva quando a IA está desligada) |
| `styles/app.css` | Tokens e componentes do protótipo; bloco "celular" no fim (até 640 px) |

### Cache das telas (`lib/cacheTelas.ts`)
Minhas inscrições, Meus dados, Contrato e Documentos de ingresso ficam em memória na aba por 5 min, para abrir na
hora ao voltar. Ao carregar o histórico, o portal adianta Meus dados, contrato, lista de documentos e prévias.
Boleto e PIX nunca entram (cada geração registra uma cobrança). Cada gravação avisa o cache (`setWriteHandler` em
`client.ts` → `invalidarApos`):

| Gravação | Sai do cache |
|---|---|
| Qualquer `POST/PUT` em `/inscricoes/{ref}/…` | a lista de inscrições, Meus dados e tudo daquela inscrição |
| `PUT /meus-dados` | Meus dados (a tela guarda o que o servidor devolveu) |
| `POST /meus-dados/senha`, `/auth/*` | nada (entrar e sair limpam tudo) |

O cache inteiro é apagado ao entrar, ao sair e quando a sessão expira (401).

### Celular
Corte em 640 px (`styles/app.css`). O topo de quem está logado recolhe a navegação no botão "Menu". As 4 etapas
cabem lado a lado e o resumo da vaga começa recolhido (`<details>`). O rodapé da matrícula fica preso ao pé da
tela. Os campos curtos ficam em pares (classes `m4`/`m6`/`m8`), com fonte de 16 px para o iPhone não dar zoom. O
visor abre em tela cheia.

## Rotas do front
| Rota | Tela |
|---|---|
| `/login` | Login |
| `/inscricoes` | Histórico |
| `/inscricoes/:ref/contrato` | Contrato (matrícula e como assinar pela Clicksign) |
| `/inscricoes/:ref/documentos` | Documentos de ingresso (o que o Lyceum registrou, com prévia) |
| `/meus-dados` | Contato, endereço e troca de senha |
| `/matricula/:id` | Redireciona para a etapa liberada mais adiante |
| `/matricula/:id/{dados,documentos,pagamento,conclusao}` | Wizard |

Regra das etapas (`etapasPermitidas` em `Wizard.tsx`): com situação **Convocado**, libera até a etapa atual da inscrição
(`etapaAtual`); com **Pré-Matriculado**, libera só documentos (consulta) e conclusão; nas demais situações, volta ao histórico.

Telas próprias de áreas de interesse, oferta e cadastro ainda não existem (o cabeçalho abre o legado): ver [roadmap.md](roadmap.md), Etapa B.
