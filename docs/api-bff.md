# API do BFF (`/api/v1`)

A documentação interativa fica em **`/api/docs`** (Swagger do FastAPI), e o contrato em `/api/openapi.json`.

## Convenções
- JSON em camelCase. Datas no formato `dd/mm/aaaa`.
- Sessão: cookie `portal_session` (httpOnly, assinado) + `portal_legado` (httpOnly, **criptografado**, `Path=/api`,
  com a sessão do candidato no Processo Seletivo). O front envia `credentials: "include"`. O servidor não guarda
  nada entre requisições.
- **POST/PUT/DELETE exigem o header `X-Requested-With`**, senão a resposta é 403.
- **`{ref}` nas rotas de inscrição é uma referência opaca**, não o número da inscrição. Ela vem no campo `ref` de
  `GET /inscricoes`, é criptografada (AES-SIV) e só vale na sessão de quem entrou. Número na URL → 422;
  referência de outra sessão ou pessoa → 404. Ver `backend/app/core/referencia.py`.
- Erro: status HTTP + corpo

```json
{ "erro": { "mensagem": "Revise os campos destacados.", "campos": { "endereco.cep": "CEP com 8 dígitos." } } }
```

| Status | Quando |
|---|---|
| 401 | Sem sessão, sessão do legado vencida ou login inválido (rotas protegidas) |
| 403 | Falta `X-Requested-With` |
| 404 | Inscrição não pertence à pessoa ou não existe |
| 409 | Ação fora de ordem (ex.: pagar sem os documentos obrigatórios, editar após a pré-matrícula) |
| 413 | Arquivo acima do limite |
| 422 | Validação (com `campos`) |
| 501 | Endpoint Techne ainda não mapeado |
| 502 | Lyceum indisponível (ex.: "O Processo Seletivo está fora do ar no momento…") ou resposta inválida |
| 503 | Configuração ausente |

## Endpoints
| Método | Rota | Corpo → Resposta |
|---|---|---|
| POST | `/auth/login` | `{login, senha}` → `Pessoa` + cookie |
| POST | `/auth/logout` | → 204 (apaga os dois cookies) |
| POST | `/auth/recuperar-senha` | `{login}` (e-mail, CPF, RG ou passaporte) → `{mensagem}` do Processo Seletivo |
| GET | `/me` | → `Pessoa`, ou `null` sem sessão (200) |
| GET | `/publico/cabecalho` | → `Cabecalho` (áreas de interesse + `cadastroUrl`), sem login |
| GET | `/recursos` | → `{conferenciaDocumentos: "ia" \| "navegador"}` |
| GET | `/inscricoes` | → `Inscricao[]` (com `acoes` e `etapaAtual`) |
| GET | `/inscricoes/{ref}` | → `Inscricao` |
| GET | `/inscricoes/{ref}/candidato` | → `Candidato` |
| PUT | `/inscricoes/{ref}/candidato` | `CandidatoUpdate` → `Candidato` |
| GET | `/enderecos/ufs` · `/enderecos/paises` · `/enderecos/ufs/{uf}/municipios` | listas |
| GET | `/enderecos/cep/{cep}` | → `CepResultado` ou 404 |
| GET | `/inscricoes/{ref}/documentos` | → `DocumentoStatus[]` |
| POST | `/inscricoes/{ref}/documentos/{tipo}` | multipart `arquivo` (+ `ocr` no modo navegador) → `DocumentoStatus` com `analise` e `selo`. **Não guarda o arquivo**: o navegador guarda arquivo + selo |
| POST | `/inscricoes/{ref}/envio-documentos` | multipart `arquivo_<código>` + `selo_<código>` de cada documento (aceita N; a tela manda **um por chamada**) → `EnvioDocumentosResultado`. Arquivo trocado, selo inválido ou acima do limite de tamanho → 422 com o nome do documento na mensagem e `campos` = `{código: aviso}` de cada documento a trocar (a tela marca essas linhas). Envio parcial → 200 com `recusados` = `{código: motivo}` dos que ficaram para trás |
| GET | `/inscricoes/{ref}/pagamento/opcoes` | → `OpcoesPagamento` |
| POST | `/inscricoes/{ref}/cupons/validar` | `{codigo}` → `CupomResultado` |
| POST | `/inscricoes/{ref}/pagamento` | `PagamentoIn` → `PagamentoResultado` |
| GET | `/inscricoes/{ref}/matricula` | → `Matricula` |
| POST | `/inscricoes/{ref}/matricula/confirmar` | → `ConfirmacaoResultado` |
| GET | `/questionarios/pendentes` | → `Questionario[]` |
| GET | `/health` | → `{status, lyceum}` (503 se degradado) |

## Diferenças em relação ao legado
| Legado | BFF |
|---|---|
| `lyceumRetorno.tipo = OK/erro` com HTTP 200 | Status HTTP + `erro.campos` |
| `codCandidato` + `codigoCandidato`, `pais` + `paisSelect`, `cep` + `cepEs`, `municipio` + `enderecoMunicipioCode` | Um campo cada; ids vêm da URL autorizada |
| Flags `obrigatorio*` enviadas pelo cliente | A obrigatoriedade é regra do servidor |
| `planoPadrao:codigoPlano:formaPagamento:numParcelas` em uma string | `codigoPlano` (o servidor resolve o resto) |
| Upload de todos os documentos em um multipart | Conferência um a um (IA), envio final com todos + selos; a tela manda um documento por chamada e o BFF faz uma requisição ao Lyceum por documento (o primeiro pela rota do form, os seguintes pela avulsa). Resultado por documento: o que for recusado volta em `recusados` e o resto segue |
| Dados de cartão no `efetivar.json` | Não aceitos (cartão desabilitado até haver tokenização) |
| Cache-buster `_` | Removido |
