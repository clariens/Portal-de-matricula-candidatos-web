# Pagamento no Processo Seletivo (legado): boleto, PIX e cartão

Mapa do que a tela de pagamento do legado usa, para levar o mesmo comportamento à nossa tela (Etapa A do
[roadmap](roadmap.md)). Levantado em 30/10/2026 no DEV, lendo os scripts da página (`pagamentoIngresso.js`,
`terminoIngresso.js`, `historico.js`) e o HTML das telas. Nenhuma chamada que gere cobrança foi feita.

## Resumo
- **Escolher a forma de pagamento não gera nada.** Na tela de pagamento, clicar em Boleto, PIX ou Cartão só troca
  o que aparece. A cobrança (boleto ou PIX da 1ª parcela) só existe **depois** do `efetivar.json`, que cria a
  matrícula.
- **Boleto e PIX são gerados na tela seguinte**, `/r/terminoIngresso` (e também no Histórico, para cobranças
  pendentes).
- **Os dados do cartão vão dentro do `efetivar.json`**: o legado recebe número, validade e código de segurança
  em texto. Se a nossa tela fizer o mesmo, os dados do cartão passam pelo BFF (escopo PCI).

## Fluxo do legado
```
/r/pagamentoIngresso  ──(Confirmar: POST r/pagamentoIngresso/efetivar.json)──►  /r/terminoIngresso
  escolhe responsável, plano                    cria a matrícula e a cobrança        boleto: GET r/terminoIngresso/gerarBoleto
  (Boleto | PIX | Cartão) e cupom               cartão: dados vão neste corpo        PIX:    POST r/historico/geraPix
                                                                                      cartão: GET r/terminocompra/verificaProcessamentoPedidoCartao
                                                                                      seguir: POST r/terminoIngresso/proximo.json → /r/questionario
```

## 1. Tela de pagamento: `/r/pagamentoIngresso` (`pagamentoIngresso.js`)
| O quê | Como |
|---|---|
| Planos | `<select id="planoPagamento">`, valor `planoPadrao:codigoPlano:formaPagamento:numParcelas` (ex.: `N:PG_PIX:PIX:6`). Já lido pelo portal |
| Cupom | `POST r/pagamentoIngresso/validarvoucher` (form `voucher=`). Já ligado no portal |
| Forma = Cartão | mostra o bloco `#cartao` **na mesma página** (nenhuma chamada) |
| Forma = Boleto ou PIX | esconde o bloco do cartão (nenhuma chamada) |
| Confirmar | `$.lyceumJsonPOST("r/pagamentoIngresso/efetivar.json", dados)` → redireciona para `r/terminoIngresso` |
| Remover responsável | `GET r/pagamentoIngresso/removerResponsavel?nome=` |

**Campos do cartão** (bloco `#cartao`, validados no navegador e enviados no `efetivar.json`):

| Grupo | Campos |
|---|---|
| Cartão novo | `numeroCartao` (máscara `9999 9999 9999 999?9`), `titularCartao`, `mesValidadeCartao` (1–12), `anoValidadeCartao` (ano atual + 9), `codSegurancaCartao` (`999?9`), `docPortadorCartao` (CPF do portador) |
| Endereço do portador | `cepCartao`, `enderecoCartao`, `enderecoNumCartao`, `enderecoComplCartao`, `enderecoBairroCartao`, `enderecoMunicipioCartao`, `enderecoUfCartao`, `enderecoPaisCartao`; estrangeiro: `cepEsCartao`, `enderecoMunicipioEsCartao`, `enderecoUfEsCartao` |
| Contato | `emailCartao`, `telefoneCartao` (preenchidos com os do candidato e travados, quando existem) |
| Cartão salvo | `cartaoPagamento` (escolhe um salvo) + `codSegurancaCartaoSalvo`; `autorizaSalvarCartao`, `autorizaDebitoAutomCartao` |
| Antifraude | `verificafraudeInput`, `requerTelefoneInput` (ocultos) |

Regras do navegador: número com 15 dígitos se começar com 3 (Amex), 16 nos demais; validade maior que o mês atual.

**Cartões salvos:** listar com `GET r/historico/listarCartoes`; remover com `GET r/pagamentoCartao/removerCartao?codigoCartao=`.

## 2. Tela de término: `/r/terminoIngresso` (`terminoIngresso.js`)
| O quê | Rota | Resposta |
|---|---|---|
| Boleto da 1ª parcela | `GET r/terminoIngresso/gerarBoleto` (na sessão; sem parâmetros) | `item[0]` = PDF em base64; o legado abre numa janela nova (`boleto_<data>.pdf`) |
| PIX | `POST r/historico/geraPix` com `{"candidato","concurso","valorTotal","listaDeCobrancas":[idCobranca]}` | `item[0].tagHtml` (QR code em `<img>`), `item[0].payload` (copia e cola), `item[0].recebedor` |
| Cartão: pedido em processamento | `GET r/terminocompra/verificaProcessamentoPedidoCartao` (`numPedidoCartao`), repetido com `setTimeout` até ter resposta | situação do pedido; recusado mostra o formulário de nova tentativa |
| Cartão: nova tentativa | `POST r/pagamentoCartao/tentarNovoPagamento` (mesmos campos do cartão) | volta para `r/terminoIngresso` |
| Seguir | `POST r/terminoIngresso/proximo.json` | leva a `r/questionario`. **Irreversível**: precisa de autorização antes do primeiro envio real |

`valorTotal` e `idCobranca` do PIX vêm do HTML da tela de término (chamada `openModalPix(codCandidato, codConcurso,
valor, idCobranca)` no botão). Ainda não vimos esse HTML: ele só existe depois de um `efetivar.json` real.

## 3. Histórico: cobranças pendentes (`historico.js`)
Mapeado de novo em 04/11/2026 (DEV): a linha de uma inscrição **Pré-Matriculado** com cobrança **Em Aberto** tem:

| Botão | Chamada | No portal |
|---|---|---|
| Boleto | `obtemBoleto(codCandidato, codConcurso)` → `GET r/historico/gerarBoleto` | ação `boleto`: "Boleto" no card → conclusão com o boleto |
| Tentar Novo Pagamento Cartão/PIX | `openModalWindown(oferta, pedido, valor, parcelas, candidato, concurso, podeBoletar, podeCartao, 'Boleto', idBoleto, permiteBoleto, permitePix, idCobranca)` abre `#myModal`; os planos vêm de `GET r/listarMetodosPagamento?oferta=&permitePlanosPix=` (em DEV: `PG_CARTÃO_A` Cartao e `PG_PIX` PIX, 6 parcelas); PIX → `geraPix`; cartão → `POST r/pagamentoCartao/tentarNovoPagamento` | ação `pix` (quando `permitePix` = true): "Pagar com PIX" no card → conclusão com o PIX. Cartão continua "Em breve" (PCI) |
| Contrato | `chamaContrato(códigoDoAluno)` → `r/contrato/geraContratoAceite` + `/r/contrato` | ação `contrato`: "Ver contrato" |
| Documentos Ingresso | link `r/documentosPorProcessoCandidato?q=` | ação `documentos`: consulta |

Valor das opções do modal: `plano:formaPagamento:numParcelasCartao:candidato:concurso:valor:idCobranca`.

Usado pelo legado quando a pessoa volta depois para pagar (taxa de inscrição ou parcela em aberto).

| O quê | Rota |
|---|---|
| Boleto | `GET r/historico/gerarBoleto?codConcurso=&codCandidato=[&codBoleto=]` → `item[0]` PDF em base64 |
| PIX | `POST r/historico/geraPix` (mesmo corpo da tela de término) |
| Planos para novo pagamento | `GET r/listarMetodosPagamento?oferta=&permitePlanosPix=` |
| Novo pagamento no cartão | `POST r/pagamentoCartao/tentarNovoPagamento` (matrícula) ou `tentarNovoPagamentoCandidato` (taxa de inscrição) |
| Novo boleto | `POST r/pagamentoCartao/tentarNovoPagamentoBoleto` → `r/terminoIngresso` |

## 4. Nossa tela

**Implementado (04/11/2026):** `GET /api/v1/inscricoes/{ref}/pagamento/boleto` (PDF) e `POST /api/v1/inscricoes/{ref}/pagamento/pix` (QR, copia e cola, recebedor, valor), e o bloco "Primeira parcela" na conclusão, que gera o boleto ou o PIX assim que a tela abre. Validado com o dublê; falta o teste real em DEV depois do primeiro `efetivar.json`. Cartão continua "Em breve".

Desenho:
| A pessoa faz | A tela mostra | Chamada |
|---|---|---|
| Escolhe **Cartão** | o formulário do cartão na hora, com os campos do item 1 | nenhuma |
| Escolhe **Boleto** ou **PIX** | o que vai acontecer ao confirmar ("o boleto da 1ª parcela aparece em seguida") | nenhuma |
| **Confirma** | — | `efetivar.json` (cria a matrícula) |
| Depois de confirmar, Boleto | o PDF do boleto na própria tela, com "Baixar" | `gerarBoleto` |
| Depois de confirmar, PIX | QR code, código copia e cola com "Copiar", valor e recebedor ("confira se o recebedor é …") | `geraPix` |
| Depois de confirmar, Cartão | "Processando pagamento…" e o resultado; se recusado, nova tentativa | `verificaProcessamentoPedidoCartao`, `tentarNovoPagamento` |
| Volta depois | boleto e PIX de novo, pela inscrição | rotas do Histórico (item 3) |

No BFF, cada uma vira uma rota sob `/inscricoes/{ref}/pagamento/…`, na sessão do candidato, como as demais.
O PDF e o QR vão para a tela sem guardar nada no servidor.

## Teste real em DEV (04/11/2026, autorizado)
Inscrição de teste 2027100000285 (concurso 1363), plano `N:PG_PIX:PIX:6`, responsável "Eu mesmo".

| Passo | Resultado |
|---|---|
| `efetivar.json` | **gravou**, mas levou mais de 20 s: o BFF desistiu de esperar e respondeu 502. O histórico já mostrava "Pré-Matriculado", cobrança "Em Aberto", vencimento 05/11/2026. Corrigido: espera de 120 s e, sem resposta, o BFF confere o histórico antes de dizer que falhou (nunca reenvia sozinho) |
| `/r/terminoIngresso` numa sessão nova | **302** (a tela de término só existe na sessão que confirmou) |
| `r/terminoIngresso/gerarBoleto` numa sessão nova | recusado: "Não foram encontrados os dados do aluno para gerar o Boleto." |
| `r/historico/gerarBoleto?codConcurso&codCandidato` | **PDF de 18 KB** ✅ |
| Botão de pagamento do Histórico | `openModalWindown('8553','','13091.00',1,'2027100000285','1363', false, true, 'Boleto', '3539201', true,'true','35489069')`: valor 13091.00, boleto 3539201, cobrança 35489069 |
| `r/historico/geraPix` com `valorTotal` 13091.00 e `listaDeCobrancas` [35489069] | **PIX** ✅: QR em `data:image/png;base64` (1,5 KB), copia e cola de 194 caracteres (`000201…`), recebedor "Imepac Araguari Santander" |

Também existe `GET r/historico/gerarBoletoPDF?codConcurso=&codCandidato=&codBoleto=` (abre o PDF direto, link do
Histórico); o portal usa o `gerarBoleto` (JSON com o PDF em base64).

O portal tenta primeiro a tela de término (sessão que acabou de confirmar) e, se ela não estiver disponível, o
Histórico, para o boleto e para o PIX.

## Pendências e riscos
- **Gerar no clique, antes de confirmar, não é possível**: a cobrança nasce com a matrícula no `efetivar.json`.
- **HTML da tela de término** ainda não foi visto (só existe na sessão que confirmou). O `openModalPix` dela é lido
  pelo portal, mas a reserva pelo Histórico é a que foi validada.
- **`gerarBoleto` e `geraPix` não são só leitura**: registram a cobrança no banco. Em DEV o usuário liberou
  (04/11/2026); em produção, cada clique gera cobrança, e o portal gera uma vez por página aberta.
- **Cartão (PCI):** no legado os dados do cartão passam em texto pelo servidor. Copiar isso põe o BFF no escopo PCI.
  Decisão pendente: tokenizar no navegador (gateway de pagamento) ou manter "Em breve".
