# Integração com o Lyceum (Techne)

O portal fala com o Lyceum **apenas pela API REST Techne**, sempre pelo BFF. O mapa de rotas do portal legado
(`/processo-seletivo/r/*.json`, capturado em 08/10/2026) é usado só como **especificação funcional**: mostra o que
cada etapa precisa ler e gravar. O portal não chama o legado.

## Como a chamada é feita
- Base: `LYCEUM_API_BASE_URL` (TST: `https://tst-lyceum.clariens.com.br/api`).
- Header em toda chamada: `Authorization: Basic base64(LYCEUM_API_BASIC_USER:LYCEUM_API_BASIC_PASSWORD)`, `Accept: application/json`
  e, quando houver corpo, `Content-Type: application/json`. Não há token: o header é montado a cada requisição por `lyceum_basic_header()`.
- Cliente: um `httpx.AsyncClient` compartilhado (criado no `lifespan` do app).
- Timeouts: `LYCEUM_TIMEOUT_LEITURA` (20 s) e `LYCEUM_TIMEOUT_UPLOAD` (60 s). Leituras têm 1 retentativa; gravações não têm nenhuma.
- Log: `[lyceum] MÉTODO caminho → HTTP status` em nível WARNING, sem corpo e sem PII.

Código: [backend/app/services/lyceum/techne.py](../backend/app/services/lyceum/techne.py).

## Análise do Swagger de TST (16/10/2026)

Swagger em `/api/swagger-resources`, com 4 grupos:

| Grupo | Rotas | Acesso com o usuário técnico de TST |
|---|---|---|
| 1. Versão 1 – Autenticação Básica (sem prefixo) | 437 | **403 "Access is denied" em todas as rotas testadas** |
| 2. Versão 2 – Autenticação JWT (`/v2/...`) | 249 | **200 com Basic** (apesar do nome do grupo) |
| 3. Carga de Dados – Autenticação Básica (`/v2/tabela/...`) | 48 | **200** (CRUD direto em tabelas) |
| 4. Custom | 0 | — |

A análise usou **apenas GETs de leitura**, com a inscrição de teste 2027100000162 / concurso 1364 / pessoa 767919.
Os GETs que alteram estado (alterar senha, prorrogar boleto, cancelar solicitação, gerar contrato, `ep-*`) não foram chamados.

### Conclusão principal
**As rotas de processo seletivo existem só no grupo 1 (v1), e o usuário técnico não tem permissão nele.** São elas:
`/processoseletivo/*`, `/pix/gerarPix`, `/financeiro/pagarComCartaoCreditoCandidato`, `/comum/planos-ofertados`,
`/comum/processo-documento` e `/integracao/ingresso-crm`. O grupo v2 é voltado ao **aluno** (precisa de `codAluno`) e não tem
endpoints de candidato. A única exceção é a tabela `/v2/tabela/candidatos`.

**Pedido ao time Lyceum**: liberar para o usuário técnico do portal as rotas v1 da tabela abaixo (ou equivalentes v2),
e explicar o fluxo oficial de **ingresso do candidato** (virada de candidato para aluno com `codAluno`).

### Necessidades → endpoints

A chave da tabela `ENDPOINTS` em `techne.py` vem primeiro. Enquanto estiver `None`, o método responde **501**.

| Chave | Necessidade | Opção v2 (acessível hoje) | Opção v1 (403 hoje) | Situação |
|---|---|---|---|---|
| `autenticar` | Login | `POST /v2/pessoas/autenticacao`: **só aluno por RA**; recusa candidato ("Seu número de matrícula não existe…") | `POST /pessoas/autenticacao_aluno` (também de aluno) | **Ligado em DEV com `LYCEUM_AUTH_MODO=legado`**: CPF/senha validados no `/processo-seletivo/j_security_check`, `idPessoa` lido em `/r/alterarDados`, pessoa via `/v2/pessoas/idPessoa/{id}/obterPessoa`. Exceção temporária: pedir ao Lyceum login de candidato na API |
| `listar_inscricoes` | Histórico do candidato | **Nenhuma**: `/v2/tabela/candidatos` exige `pk[candidato]`+`pk[concurso]`, sem busca por pessoa/CPF | `GET /processoseletivo/candidatos/inscritos?candidato&concurso&idProspectoCaptacao` → `CandidatosInscritosRetDto[]` (situação, cobrança, boleto, `codigoAluno`, `existeQuestionarioPendente`…) | **Bloqueado**: liberar v1 ou criar consulta por pessoa |
| `obter_candidato` | Dados da etapa 1 | `GET /v2/tabela/candidatos?pk[candidato]=&pk[concurso]=` (✅ 200; traz `pessoa`, `sit_candidato_vest`, `aluno`, endereço com `municipio` código Lyceum) + `GET /v2/pessoas/idPessoa/{id}/obterPessoa` (✅ 200) | — | **Disponível** |
| `atualizar_candidato` | Gravar etapa 1 | `PUT /v2/tabela/candidatos` (escrita direta na tabela, **sem regras de negócio**) · `POST /v2/pessoas/alterarPessoa` | `PATCH /processoseletivo/inscricao/concurso/{c}/candidato/{c}` (`CandidatoDTO`) | Preferir v1 PATCH; confirmar com o Lyceum |
| (buscar_cep) | CEP → endereço | `GET /v2/comum/cep/{cep}/enderecos` (✅ 200, traz `municipio` "002174", `nomeMunicipio`, `ufSigla`, `nomeBairro`, `txbLogradouro`) | `GET /pessoas/cep/{cep}/obterEndereco` | **Disponível**: substitui o ViaCEP |
| `listar_paises` etc. | Listas | `GET /v2/comum/ufs`, `/paises`, `/estados-civis`, `/orgaos-emissores`, `/nacionalidades` (✅ 200); `POST /v2/comum/municipios` (busca; não testado) | `/pessoas/listar*` | **Disponível** |
| `listar_documentos` | Documentos exigidos no processo | — (`/v2/comum/documentos/tipos-documento` só traz o tipo de RG) | `GET /comum/processo-documento`, `GET /comum/tipo-documento` | **Bloqueado** |
| `enviar_documento` | Upload | `POST /v2/alunos/documentos/documento-pessoa/upload` + `POST /v2/alunos/documentos` (pedem `codAluno`) | `POST /pessoas/upload_documento_pessoa` (`fileData` Base64) + `POST /pessoas/inclui_documento` (`codPessoa`, `idDocumentoProcesso`) | Bloqueado para candidato sem `codAluno` |
| `opcoes_pagamento` | Planos e valores | `GET /v2/tabela/concursos?pk[concurso]=` (✅ traz `planopag`, `boleto_valor`, `exigir_resp_finan`) | `GET /comum/planos-ofertados?oferta=`, `GET /comum/formas-pagamento` | **Ligado em DEV pelo legado**: planos lidos de `/r/pagamentoIngresso` (`<select id="planoPagamento">`, valor `planoPadrao:codigoPlano:formaPagamento:numParcelas`; a página não traz valores). Só abre depois de salvar os dados e abrir os documentos na mesma sessão; fechada, redireciona para `/r/historico` |
| `validar_cupom` | Cupom | — | — | **Ligado em DEV pelo legado**: `POST /r/pagamentoIngresso/validarvoucher` (form `voucher=…`) → `item[0]{descPercValor, desconto}`. Sem rota na API |
| `efetivar_pagamento` | Ingresso + financeiro | `POST /v2/alunos/contratos` (gera contrato e boleto; pede `codAluno`) | `POST /integracao/ingresso-crm` (`DadosIngressoCrmDTO`) ou `/integracao/crm-dynamics/ingresso` (`DadosIngressoDTO`: `codigoConcurso`, `codigoOferta`, `inscricao`, dados do responsável) · `POST /pix/gerarPix` (`candidato`, `concurso`) | **Ligado pelo legado, em simulação** (`LYCEUM_PAGAMENTO_MODO=simular`): `POST /r/pagamentoIngresso/efetivar.json` com o `frm-pagamento` serializado (só a seção do responsável escolhido; cartão vazio). **Cria a matrícula**: o primeiro envio real precisa de autorização. Na API: definir o fluxo oficial de ingresso |
| `obter_matricula` | Matrícula, disciplinas, contrato | `GET /v2/alunos/{codAluno}/dados-academicos`, `/v2/matriculas/alunos/{a}/ano/{y}/periodo/{p}/disciplinas/pre-matriculadas`, `/v2/acordos/alunos/{a}/contratos` | — | Disponível **após** existir `codAluno` |
| `confirmar_matricula` | Concluir | `POST /v2/alunos/contratos/aceitar-contrato` | `POST /matricula/confirmar-matricula` | Disponível após `codAluno` |
| `questionarios_pendentes` | Questionário | `GET /v2/questionarios/questionarios-pendentes` | `GET /avaliacaoInstitucional/questionarios/questionariosPendentesAluno?aluno=` | Disponível após `codAluno` |

### Observações da análise
- **Ambiente**: em TST, a inscrição 2027100000162 está como `sit_candidato_vest = "Confirmado"`, com `aluno = null`. A captura do
  legado (Pré-Matriculado, matrícula 2716520002) foi feita em `desenvolvimento-lyceum`, que é outro ambiente.
- **Autorização**: `/v2/tabela/candidatos` devolve `pessoa`. O BFF pode conferir `candidato.pessoa == pessoa da sessão` antes de
  mostrar ou gravar qualquer coisa, que é a mesma regra de `inscricao_autorizada`.
- **Dados sensíveis**: a tabela de candidatos traz `senha_web`, e a de pessoa traz `resp_senha` e `senha_tac`. O mapper **nunca** pode repassar
  o JSON bruto ao front.
- **Estado civil**: o Lyceum usa `Solteiro, Casado, Divorciado, Marital, Separado, Separado Consensualmente, Separado
  Judicialmente, União Estável…`. A lista fixa do portal (`União estável`) diverge e deve passar a vir de `/v2/comum/estados-civis`.
- **Não usar** `GET /pessoas/{usuario}/{senha}/autenticacao` nem `GET /v2/pessoas/usuario/{usuario}/senha/{senha}/autenticacao`,
  porque a senha vai na URL e acaba em logs.
- **Escrita via `/v2/tabela/*`**: é carga de dados direta, sem as validações e entry-points do processo seletivo. Só usar
  com aval do time Lyceum.

### Como ligar um endpoint
1. Capture request e response reais em TST, mascare os dados pessoais e salve em `backend/tests/fixtures/techne/<chave>/`.
2. Preencha a chave em `ENDPOINTS` e implemente o método em `TechneGateway` com `self._request(...)`, usando
   `idempotente=True` em leituras.
3. Escreva o mapper em `mappers.py` (tolerante a variações de chave, com `pick(...)`) para o modelo Pydantic do portal.
4. Escreva o teste com `respx` em `tests/test_techne.py` usando a fixture.
5. Atualize esta tabela, o [CHECKLIST](../CHECKLIST.md) e o [CHANGELOG](../CHANGELOG.md).

## Tratamento de erros (login)
| Situação no Lyceum | Resposta do BFF |
|---|---|
| Rede/timeout | 502 "Não foi possível conectar à API de autenticação" |
| 400/401/403, ou 5xx com `status` interno 401/403/412 | 401 com a mensagem passada por `sanitize_lyceum_error` |
| Outro status, ou JSON sem identificador/login | 502 "Resposta inválida da API de autenticação" |
| `LYCEUM_API_BASE_URL` ou Basic vazios | 503 "Variável X não configurada no servidor" |

## Pontos de atenção
- **Tamanho do upload**: o nginx na frente do TST devolveu 413 com body de ~3,9 MB no portal ENAMED. Com Base64 (+33%),
  o limite de 10 MB do portal exige `client_max_body_size` ≥ 14 MB.
- **Antes de produção**: trocar a base URL e o Basic pelos de produção e conferir o nginx.
