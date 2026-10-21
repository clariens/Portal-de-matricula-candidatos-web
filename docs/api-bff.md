# API do BFF (`/api/v1`)

A documentação interativa fica em **`/api/docs`** (Swagger do FastAPI), e o contrato em `/api/openapi.json`.

## Convenções
- JSON em camelCase. Datas no formato `dd/mm/aaaa`.
- Sessão: cookie `portal_session` (httpOnly). O front envia `credentials: "include"`.
- **POST/PUT/DELETE exigem o header `X-Requested-With`**, senão a resposta é 403.
- Erro: status HTTP + corpo

```json
{ "erro": { "mensagem": "Revise os campos destacados.", "campos": { "endereco.cep": "CEP com 8 dígitos." } } }
```

| Status | Quando |
|---|---|
| 401 | Sem sessão ou login inválido |
| 403 | Falta `X-Requested-With` |
| 404 | Inscrição não pertence à pessoa ou não existe |
| 409 | Ação fora de ordem (ex.: pagar sem os documentos obrigatórios, editar após a pré-matrícula) |
| 413 | Arquivo acima do limite |
| 422 | Validação (com `campos`) |
| 501 | Endpoint Techne ainda não mapeado |
| 502 | Lyceum indisponível ou resposta inválida |
| 503 | Configuração ausente |

## Endpoints
| Método | Rota | Corpo → Resposta |
|---|---|---|
| POST | `/auth/login` | `{login, senha}` → `Pessoa` + cookie |
| POST | `/auth/logout` | → 204 |
| GET | `/me` | → `Pessoa` |
| GET | `/inscricoes` | → `Inscricao[]` (com `acoes` e `etapaAtual`) |
| GET | `/inscricoes/{cod}` | → `Inscricao` |
| GET | `/inscricoes/{cod}/candidato` | → `Candidato` |
| PUT | `/inscricoes/{cod}/candidato` | `CandidatoUpdate` → `Candidato` |
| GET | `/enderecos/ufs` · `/enderecos/paises` · `/enderecos/ufs/{uf}/municipios` | listas |
| GET | `/enderecos/cep/{cep}` | → `CepResultado` ou 404 |
| GET | `/inscricoes/{cod}/documentos` | → `DocumentoStatus[]` |
| POST | `/inscricoes/{cod}/documentos/{tipo}` | multipart `arquivo` + `ocr` (JSON de `OcrResultado`) → `DocumentoStatus` |
| GET | `/inscricoes/{cod}/pagamento/opcoes` | → `OpcoesPagamento` |
| POST | `/inscricoes/{cod}/cupons/validar` | `{codigo}` → `CupomResultado` |
| POST | `/inscricoes/{cod}/pagamento` | `PagamentoIn` → `PagamentoResultado` |
| GET | `/inscricoes/{cod}/matricula` | → `Matricula` |
| POST | `/inscricoes/{cod}/matricula/confirmar` | → `ConfirmacaoResultado` |
| GET | `/questionarios/pendentes` | → `Questionario[]` |
| GET | `/health` | → `{status, modo, lyceum}` (503 se degradado) |

## Diferenças em relação ao legado
| Legado | BFF |
|---|---|
| `lyceumRetorno.tipo = OK/erro` com HTTP 200 | Status HTTP + `erro.campos` |
| `codCandidato` + `codigoCandidato`, `pais` + `paisSelect`, `cep` + `cepEs`, `municipio` + `enderecoMunicipioCode` | Um campo cada; ids vêm da URL autorizada |
| Flags `obrigatorio*` enviadas pelo cliente | A obrigatoriedade é regra do servidor |
| `planoPadrao:codigoPlano:formaPagamento:numParcelas` em uma string | `codigoPlano` (o servidor resolve o resto) |
| Upload de todos os documentos em um multipart | Um documento por chamada, com resultado do OCR |
| Dados de cartão no `efetivar.json` | Não aceitos (cartão desabilitado até haver tokenização) |
| Cache-buster `_` | Removido |
