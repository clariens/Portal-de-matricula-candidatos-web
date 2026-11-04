# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Versionamento: [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]
### Adicionado
- **Meus dados.** Tela `/meus-dados` (link "Meus dados" no topo), como o "Meus Dados" do Processo Seletivo:
  e-mail, celular, telefone e endereço (`alterarPessoaFisica.json`) e troca de senha com a senha atual
  (`alterarSenhaPessoa.json`). O `idPessoa` vem da sessão; senhas fora do log; com reCAPTCHA na página, a troca
  é recusada com aviso. Mapa em `docs/meus-dados-legado.md`. Validado em DEV.
- **Contrato e documentos abrem na hora.** Ao carregar "Minhas inscrições", o portal busca em segundo plano o
  contrato, a lista de documentos e as prévias das inscrições que têm esses botões (`lib/cacheTelas.ts`, cache em
  memória da aba por 5 min, apagado ao sair ou quando a sessão expira). Boleto e PIX ficam de fora: cada geração
  registra uma cobrança no banco.
- **Telas próprias de Contrato e Documentos de ingresso.** No histórico, "Ver contrato" abre
  `/inscricoes/{ref}/contrato` (matrícula, turma, pagamento e como assinar pela Clicksign) e "Documentos" abre
  `/inscricoes/{ref}/documentos` (o que o Lyceum registrou, com prévia e visor), fora do assistente de matrícula.
  "Boleto" e "Pagar com PIX" continuam abrindo a conclusão. Visor e bloco de assinatura viraram componentes
  (`components/Visor.tsx`, `components/AssinaturaContrato.tsx`).
- **Boleto e PIX pelo histórico.** Como o histórico do legado (mapeado de novo em 04/11/2026), a inscrição
  pré-matriculada com cobrança em aberto ganha os botões "Boleto" e "Pagar com PIX" (ações `boleto` e `pix`, lidas de
  `obtemBoleto` e do modal "Tentar Novo Pagamento Cartão/PIX"), que abrem a conclusão já com a forma escolhida. Na
  1ª parcela dá para trocar entre boleto e PIX.
- **Contrato e documentos depois do pagamento.** Para inscrição pré-matriculada, "Ver contrato" abre a conclusão
  com o número da matrícula (código do aluno do histórico), a situação do contrato e as instruções de assinatura
  lidas da página de contrato do legado (Clicksign pelo WhatsApp do responsável financeiro); a 1ª parcela usa a forma
  e a situação do histórico (paga não gera nada). "Documentos" mostra, em consulta, o que o Lyceum registrou.
  Antes os dois davam erro (o portal exigia a inscrição em "Convocado" e a conclusão não estava ligada ao legado).
- **Boleto e PIX da 1ª parcela.** Depois de confirmar o pagamento, a conclusão mostra o bloco "Primeira parcela":
  boleto em PDF ("Abrir boleto" e "Baixar") ou PIX com QR code, código copia e cola ("Copiar código"), valor e
  recebedor, gerados na hora pelo Processo Seletivo (`r/terminoIngresso/gerarBoleto` ou `r/historico/gerarBoleto`;
  `r/historico/geraPix` com o valor e a cobrança do botão do PIX da tela de término). Rotas
  `GET /api/v1/inscricoes/{ref}/pagamento/boleto` e `POST …/pagamento/pix`. Cada geração acontece uma vez por página
  aberta. O bloco aparece mesmo enquanto os dados da matrícula ainda não vêm do Lyceum real.
- **Prévia dos documentos enviados.** Na etapa Documentos, o que o Lyceum já recebeu aparece com a miniatura do
  arquivo (ou "PDF") e abre num visor com "Baixar", também quando a pessoa volta depois por outro caminho. O
  arquivo vem da coluna Download da tela "Documentos Ingresso" do legado (`/r/documentosCandidato/download`), na
  sessão do candidato, pela rota `GET /api/v1/inscricoes/{ref}/documentos/{tipo}/arquivo` (`no-store`). Quando o
  Lyceum guardou o registro sem o arquivo (visto em DEV: "Byte array must not be null"), a linha mostra "prévia
  indisponível". Os anexos ainda não enviados também abrem no visor.
- **Mapa do pagamento do legado** em `docs/pagamento-legado.md`: boleto (`gerarBoleto`), PIX (`geraPix`: QR,
  copia e cola, recebedor), campos do cartão, cartões salvos, tela de término e o desenho proposto para a nossa
  tela. Boleto e PIX só existem depois do `efetivar.json` (a cobrança nasce com a matrícula).
- **Plano das próximas etapas** em `docs/roadmap.md` (pagamento de ponta a ponta e telas próprias das
  áreas de interesse) e CHECKLIST reorganizado com a situação real.
- **Cabeçalho com "Área de interesse"** (Graduação → Vestibular Tradicional, Transferência Externa, Enem,
  Segunda Graduação, Tradicional Catalão) e **"Cadastre-se"** à direita para quem não entrou. Os dados vêm do
  cabeçalho do Processo Seletivo (`GET /api/v1/publico/cabecalho`), com os subgrupos conhecidos se o legado
  estiver fora. Mapeamento em `docs/cabecalho-processo-seletivo.md`.
- **Esqueci minha senha** funcionando no card de login (`POST /api/v1/auth/recuperar-senha`), pelo mesmo fluxo do
  `/recuperarsenha` do legado: o Processo Seletivo envia as instruções ao e-mail cadastrado.
- Logo "Clariens Educação" centralizado no card de login, sem o subtítulo "Área do candidato". No cabeçalho, o
  logo sozinho substitui "Clariens Educação · Medicina".
- **Envio de documentos um por chamada, do navegador até o Lyceum.** Antes, o navegador mandava todos os arquivos
  numa requisição e o primeiro envio ao Lyceum levava todos os obrigatórios juntos: com 6 obrigatórios (1.047.131
  bytes) o nginx do DEV (1 MiB por requisição) devolvia 413 e nada era enviado. Agora:
  - o navegador manda um documento por vez (obrigatórios primeiro, do menor para o maior), com "Enviando 2 de 6" no
    botão e "Enviando…" na linha da vez; o que entra vira "Enviado" na hora e sai do navegador;
  - o primeiro documento da inscrição vai sozinho pela rota do form (`/r/uploadDocumentosPorProcesso`, que abre a
    etapa) e os seguintes por `/r/documentosCandidato/upload`; o limite de tamanho vale por arquivo, nunca pela soma;
  - o que for recusado (grande demais, conferência vencida, não registrado) fica marcado em vermelho com o motivo e
    "Escolher outro arquivo", e os demais seguem. Se o primeiro documento não entrar, os outros esperam (o portal
    não tenta abrir a etapa de novo com outro arquivo);
  - o pagamento só abre com todos os obrigatórios no Lyceum; o servidor deixou de exigir os obrigatórios na mesma
    chamada.
- **Ícone da aba** (favicon) com o "C" da Clariens: `favicon.svg` (fica branco em aba escura), `favicon.ico` de
  reserva e `apple-touch-icon.png` para a tela inicial do celular, em `frontend/public/`.
- **Monitor cardíaco** na apresentação do login: linha vermelha desenhada, um sinal brilhante percorrendo o traçado
  em loop e um coração batendo em dois tempos com anel pulsando. Fica parado com `prefers-reduced-motion`.

### Segurança
- **Número da inscrição fora das URLs.** Telas e API usam uma referência opaca (AES-SIV, válida só na sessão de
  quem entrou) em vez do número: `/matricula/MPPLPxqz…/documentos`. Número na URL → 422; referência de outra sessão
  → 404. O número segue visível na tela para o próprio candidato.

### Alterado
- **Área de interesse travada.** As inscrições não são feitas pelo portal: o menu abre, mas os subgrupos aparecem
  com cadeado, sem link, e um aviso no topo. Para religar, `INSCRICOES_PELO_PORTAL = true` em `Shell.tsx`.
- **Login aceita CPF com ou sem pontuação.** O servidor tira a pontuação quando o texto tem formato de CPF
  (11 dígitos), no login e no "esqueci minha senha"; e-mail, RG e passaporte seguem como digitados.
- Títulos e destaques em Montserrat 700 em todas as telas (a Syne, larga, ficava achatada em negrito). A Syne fica
  só no título de apresentação do login.

### Corrigido (pagamento)
- **Depois de confirmar, a tela não chegava à conclusão (sem boleto).** O legado fecha o formulário de dados
  (`/r/ingresso` → 409) quando a inscrição vira "Pré-Matriculado", e o Wizard exigia esses dados para abrir qualquer
  etapa. Agora, fora de "Convocado", o Wizard usa só o nome de quem está logado (documentos em consulta e conclusão
  não precisam do resto). O dublê dos testes passou a recusar os dados como o legado.
- **Confirmação do pagamento demorada dava erro falso.** Em DEV o `efetivar.json` levou mais de 20 s e o portal
  respondia "Não foi possível conectar", embora a matrícula tivesse sido criada. Agora espera até 120 s e, sem
  resposta, confere o histórico: se a inscrição já está "Pré-Matriculado", segue como sucesso. Nunca reenvia sozinho.

### Corrigido (login)
- O menu "Área de interesse" demorava até 20 s para aparecer com o Processo Seletivo fora: agora desiste em 4 s,
  guarda a lista de reserva por 2 min e mostra o botão (carregando) desde o início.
- `GET /api/v1/me` sem sessão responde 200 com `null` em vez de 401. Abrir o site não mostra mais erro no console;
  as rotas protegidas continuam com 401.
- Processo Seletivo fora do ar (502 do proxy ou sem conexão): o login e a recuperação de senha mostram "O Processo
  Seletivo está fora do ar no momento. Tente novamente em alguns minutos." em vez de "Resposta inválida".
- **Preparação para a Vercel** (homologação interna): `vercel.json` com Services (`front` Vite + `bff`
  FastAPI no mesmo domínio), `.vercelignore` (nunca envia `backend/.env`) e `backend/.python-version`.
- **Backend sem estado entre requisições e sem banco** (a instituição não usa Redis):
  - a sessão do legado (JSESSIONID) e a etapa do wizard vão num cookie `portal_legado` criptografado e httpOnly;
  - os anexos ficam no IndexedDB do navegador até o envio final. Sobrevivem a recarregar a página e são apagados
    ao enviar, ao remover, ao sair e depois de 24 h;
  - a conferência devolve um **selo** assinado (hash do arquivo + resultado). No envio o navegador devolve arquivo
    e selo, e arquivo trocado ou selo forjado são recusados;
  - saiu a rota `DELETE /documentos/{tipo}` (remover é só no navegador). `POST /envio-documentos` passou a receber
    `arquivo_<código>` + `selo_<código>`;
  - validado em DEV com duas instâncias atendendo o mesmo candidato. Se a sessão cair, o candidato entra de novo.

### Corrigido
- **Documento novo depois do primeiro envio não chegava ao Lyceum** (visto em DEV, 29/10/2026). Depois do primeiro
  envio, o legado responde 200 a `POST /r/uploadDocumentosPorProcesso` e não grava nada, e o portal dizia
  "Documentos enviados". Agora:
  - o primeiro envio continua no lote do `frm-documentos`;
  - os documentos seguintes vão um a um por `POST /r/documentosCandidato/upload`, com o campo `"<código>,Ingresso"`
    (a rota do modal da tela "Documentos Ingresso"). Validado em DEV com as certidões de nascimento e casamento;
  - um documento só conta como enviado quando aparece em "Documentos Ingresso". O que não foi gravado continua
    anexado, e a mensagem diz qual tentar de novo. Saiu a conferência pela página de pagamento, que dava falso
    positivo.

### Removido
- **Modo mock** (`LYCEUM_MODE`): o portal só fala com o Lyceum real. Sem a configuração (`LYCEUM_API_*`,
  `LYCEUM_LEGADO_BASE_URL`, `PORTAL_SESSION_SECRET`) o servidor não inicia e diz o que falta. Antes, um servidor
  iniciado sem ler o `.env` subia em mock em silêncio e recusava candidatos reais com "credencial inválida".
  Os dados fictícios viraram um dublê só de testes (`backend/tests/fake_lyceum.py`, usado pelo pytest e pelo e2e).
  O aviso de login de demonstração saiu da tela de login. `LYCEUM_AUTH_MODO` passa a ter `legado` como padrão.

### Adicionado
- **Login real de candidato (CPF/e-mail + senha) em DEV** com `LYCEUM_AUTH_MODO=legado`: o BFF valida no
  `j_security_check` do Processo Seletivo, lê o `idPessoa` em `/r/alterarDados`, encerra a sessão Java e busca a
  pessoa na API (`/v2/pessoas/idPessoa/{id}/obterPessoa`). É uma exceção à regra "só Techne", restrita à autenticação,
  até o Lyceum expor login de candidato na API.
- **Integração com o portal legado na sessão do candidato** (`backend/app/services/lyceum/legado.py`): a sessão Java
  (JSESSIONID) fica só no servidor, indexada pelo `sid` aleatório do cookie do portal; o navegador nunca a recebe.
  Expira com o legado (~25 min) e o logout do portal encerra também a do legado.
- **Histórico real** (`/r/historico`): situação, pagamento, concurso (do link Matricule-se ou Documentos Ingresso) e ações.
- **Etapa 1 – Dados (leitura real)**: form de `/r/ingresso` + `/endereco/obterMunicipioCandidato`.
- **Etapa 1 – Dados (gravação)**: `POST /r/ingresso/atualizar.json` com os campos da página + os editados (ocultos
  preservados, vazio → null). Implementada e testada com fixtures; **ainda não executada contra DEV**.
- **Busca de CEP com ViaCEP**: o BFF consulta em paralelo o ViaCEP (logradouro, bairro, cidade, UF) e o Lyceum
  (`/v2/comum/cep/{cep}/enderecos`, só para o código de município exigido na gravação). Se o ViaCEP disser que o CEP
  não existe, responde na hora (antes esperava ~3,5 s pelo erro do Lyceum); se o ViaCEP estiver fora, usa o Lyceum.
- Campo CEP: a busca dispara com **Tab** (só se o CEP mudou), **Enter** ou a **lupa** (sempre); preenche os campos,
  leva o foco para "Número" e mostra o estado (buscando, encontrado, não encontrado, CEP incompleto).
- **Data de nascimento formatada**: o form do legado traz `ddmmaaaa` (a máscara era só visual); o BFF normaliza
  para `dd/mm/aaaa` (aceita também `aaaa-mm-dd` e com hora) e o front reaplica a máscara.
- **Etapa Documentos (legado)**:
  - Lista de documentos lida da página real `/r/documentosPorProcesso` (nome, obrigatoriedade, extensões), não mais
    fixa. Conferida em DEV: 14 documentos, obrigatórios 03, 05, 02 e 04 (iguais à doc). A página só abre depois de
    salvar os dados na mesma sessão; antes disso o portal pede para confirmar os dados.
  - Cada arquivo anexado (com o resultado do OCR) fica no servidor como **"Pronto para envio"**; pode ser trocado
    ou removido (`DELETE /inscricoes/{id}/documentos/{tipo}`). Nada vai ao Lyceum nesse momento.
  - "Enviar documentos e continuar" (`POST /inscricoes/{id}/envio-documentos`) monta um multipart igual ao do
    navegador (inclusive `filename=""` nos não anexados) para `/r/uploadDocumentosPorProcesso`.
  - **`LYCEUM_DOCUMENTOS_MODO=simular` (padrão)**: esse POST finaliza a inscrição no Lyceum, então em DEV ele só
    valida, registra no log o que seria enviado e avança o wizard. Envio real só com `enviar`. Em DEV, nenhum
    upload real foi feito.
- **Conferência de documentos com identificação do tipo**: além dos dados, o OCR verifica se o arquivo é o documento
  pedido (marcas por código, ex.: "CADASTRO DE PESSOAS FÍSICAS", "REGISTRO GERAL"). Sequência: legível → tipo → dados.
  Selos ✓ conferido / ⚠ ressalva / ✗ com a mensagem na linha. Documento ilegível ou não reconhecido só aceita outro
  arquivo (o backend também recusa); dados divergentes permitem outro arquivo ou conferência manual.
- **Envio real dos documentos ao Lyceum** (`LYCEUM_DOCUMENTOS_MODO=enviar`): validado em DEV em 22/10/2026 com a
  inscrição de teste 2027100000285. `POST /r/uploadDocumentosPorProcesso` → 302 `/r/pagamentoIngresso`, e os 4
  obrigatórios aparecem em "Documentos Ingresso" com data de entrega. Se a resposta vier diferente do esperado, o
  portal confirma pela abertura da etapa de pagamento antes de acusar erro.
- **Envio recusado por tamanho (422) corrigido**: fotos JPG/PNG passam a ser comprimidas no anexo (rotação EXIF,
  ≤ 2000 px, JPEG 85%, de 2–5 MB para ~300–600 KB) antes de ir ao Lyceum; limites provisórios por arquivo (2 MB) e
  por envio (8 MB) checados antes do POST, com mensagem dizendo o tamanho e quais arquivos trocar; respostas 413 e
  500 `SizeLimitExceeded` do legado viram mensagens claras; o log registra status, título da página de erro e total
  enviado; na tela, o erro do envio aparece também em aviso flutuante e a página rola até ele.
- **Sem reenvio duplicado**: depois do envio o legado continua mostrando o formulário de upload. O portal passa a ler
  os documentos já entregues em `/r/documentosPorProcessoCandidato` (fonte da verdade): mostra Enviado / Aceito /
  "Enviado" (com a data) mesmo em sessão nova, não deixa anexar documento já entregue e não refaz o POST quando
  o Lyceum já tem os obrigatórios (só avança para o pagamento). Aceite/recusa é processo interno da secretaria
  (tela de aceite de documentos do Lyceum) e não aparece para o candidato.
- **Conferência de documentos com IA (Claude, visão) no servidor**: o Claude lê e classifica (tipo, frente/verso,
  legibilidade, nome, CPF, RG, nascimento, ano, CEP) em JSON validado por schema; as regras do backend decidem.
  Testado com fotos reais de RG em DEV: frente e verso identificados, verso girado lido corretamente, RG no lugar do
  comprovante recusado; US$ 0,018–0,023 e 4–6 s por análise. Teto diário de gasto, concorrência limitada, limite de
  tentativas e queda para conferência manual em qualquer falha. Tela: "Analisando" pulsando + barra fina, análises
  em paralelo. Sem chave, segue o OCR no navegador.
- **OCR nunca trava documento verdadeiro por leitura fraca**: teste com fotos reais de RG deu 25–47% de confiança.
  Abaixo de 60% o resultado é "Não conferido" (outra foto ou conferência manual), nunca "não reconhecido";
  ilegível também deixou de bloquear. Datas com dia/mês de 1 dígito ("26/9/2004") passam a ser lidas.
- **WEBP aceito nos documentos**: convertido para JPG no navegador antes de anexar (o Lyceum só aceita JPEG, JPG,
  PDF e PNG); a linha indica "(convertido de WEBP)".
- Gravação real da Etapa 1 validada em DEV (`atualizar.json`), incluindo os campos montados por JavaScript no legado
  (`enderecoUf`, `paisSelect`), sem os quais o legado recusa o envio.
- Contexto TLS único no processo (`app/core/http.py`): cada cliente HTTP novo recarregava os certificados (~0,5 s).
- Sexo "Outros" (`O`) e lista de estado civil do Lyceum (`União Estável`, `Marital`, `Separado …`).
- **Etapa Pagamento (legado)**:
  - Planos lidos da página real `/r/pagamentoIngresso` (Boleto, PIX e Cartão em 6 parcelas, com o texto de desconto
    do Lyceum). O "6" do código do plano é o número de mensalidades do curso, igual nas três formas (não é
    parcelamento; o legado nem o mostra), e a tela o exibe como "6 mensalidades". A página não traz valores.
    Cartão segue "Em breve" (PCI).
  - O legado só abre o pagamento depois de salvar os dados e abrir os documentos na mesma sessão. O BFF tenta
    reabrir os documentos; se ainda assim estiver fechado, a tela oferece "Revisar meus dados".
  - Cupom validado em `POST /r/pagamentoIngresso/validarvoucher` (percentual ou valor).
  - Confirmação monta o mesmo corpo do `frm-pagamento` para `efetivar.json`: só a seção do responsável escolhido,
    CPF/CNPJ/CEP com máscara, data `dd/mm/aaaa`, código do município do Lyceum, HTML removido, vazio → `null`.
  - Responsável "Outra pessoa" pede os campos obrigatórios do legado: nascimento, sexo, estado civil, e-mail,
    celular e telefone (RG opcional). "Empresa" pede CNPJ e inscrições estadual/municipal (opcionais).
  - Nova configuração `LYCEUM_PAGAMENTO_MODO=simular|enviar` (padrão `simular`): `efetivar.json` **cria a matrícula**.
    Em simulação nada vai ao Lyceum e a tela avisa que o pagamento foi simulado.
  - Como no legado, nenhuma forma de pagamento vem marcada.

### Alterado
- `codConcurso` de `Inscricao` passou a ser opcional (o histórico legado só o expõe em Convocado/Pré-Matriculado).
- Testes isolados do `backend/.env` real (`PORTAL_ENV_FILE`).

### Corrigido
- Login Techne validado contra o Lyceum **DEV**: o `UsuarioDTO` traz o código da pessoa em `id` (o mapper não lia esse campo).
- Erro de login do Techne (HTTP 500 com `status` 412 e texto em `titulo`/`mensagemDetalhada`) agora chega ao usuário, sem o prefixo "Erro de autenticação:".
- Logs do httpx em WARNING, para não registrar URLs com dados pessoais.

### Descoberto
- **Limite de upload do legado em DEV** (medido em 29/10/2026): 1.000.000 bytes por arquivo (Tomcat, HTTP 500
  genérico) e 1 MiB por requisição (nginx, HTTP 413). No primeiro envio, a soma dos documentos tem que caber em
  ~1 MiB. Detalhes em `docs/deploy.md`.
- `POST /v2/pessoas/autenticacao` autentica **aluno por RA**, não candidato por CPF/e-mail. Candidato sem RA não consegue entrar (ver `docs/integracao-techne.md`).
- `/v2/tabela/candidatos` expõe `senha_web` aparentemente em texto puro: reportar ao time Lyceum.

### Pendente (detalhes em `docs/roadmap.md`)
- **Etapa A · Pagamento de ponta a ponta:** primeiro `efetivar.json` real (com autorização), valores das parcelas,
  cupom de 100%, cobrança após confirmar e Conclusão pelo legado (`/r/terminoIngresso`, `proximo.json`).
- **Etapa B · Telas próprias das áreas de interesse:** lista por subgrupo, busca, detalhe da oferta, inscrição e
  cadastro no portal (hoje o cabeçalho abre as páginas do legado).
- Pagamento com cartão via gateway com tokenização (PCI).
- Rotas de candidato na API Techne v2, quando o Lyceum liberar.

## [0.1.0] - 2026-10-16
Primeira versão funcional de ponta a ponta em modo mock. Integração real limitada ao login.

### Adicionado
- **BFF FastAPI** (`backend/`) com API REST `/api/v1`: auth, inscrições, candidato, endereços, documentos, pagamento, matrícula, questionários e health.
- `LyceumGateway` (interface) com duas implementações, escolhidas por `LYCEUM_MODE`:
  - `MockGateway`: dados do protótipo em memória, com regras de negócio (documentos obrigatórios antes do pagamento, bloqueio após pré-matrícula, cupom, cartão indisponível).
  - `TechneGateway`: Basic de serviço (`lyceum_basic_header`), `POST /v2/pessoas/autenticacao` ligado, `sanitize_lyceum_error`, timeouts de 20 s/60 s, uma retentativa só em leituras, 503 sem configuração, 502 em falha de rede, 501 para endpoints não mapeados.
- Sessão por cookie `portal_session` assinado (itsdangerous), httpOnly, SameSite=Lax, 12 h. Exigência de `X-Requested-With` em métodos mutáveis (CSRF).
- Autorização por pessoa: toda rota `/inscricoes/{cod}` confirma que a inscrição pertence à pessoa da sessão.
- Erros padronizados `{ erro: { mensagem, campos } }`, com erro por campo nas validações Pydantic.
- Upload de documento individual (multipart): validação de extensão, tamanho (10 MB) e assinatura mágica do arquivo. Resultado do OCR anexado (sem o texto bruto).
- **Frontend React + TypeScript + Vite** (`frontend/`) com o visual do protótipo: login, histórico em cartões, wizard de 4 etapas com stepper e resumo da vaga, retomável por URL (`/matricula/:id/:etapa`).
- Etapa Dados: máscaras, validação local e do servidor, CEP preenchendo UF/cidade/bairro/logradouro.
- Etapa Documentos: arrastar e soltar, prévia, progresso, **OCR no navegador** (tesseract.js 5 + pdf.js 3) com assets self-hosted em `/ocr`. Divergente ou ilegível exige confirmação para seguir à conferência manual.
- Etapa Pagamento: responsável (eu, outra pessoa, empresa) com formulário completo, cartões Boleto/PIX com valor da parcela, cartão desabilitado ("Em breve") e cupom com validação imediata.
- Etapa Conclusão: matrícula, primeira parcela, status do contrato Clicksign, disciplinas, confirmação e questionário pendente.
- Inspetor de chamadas de API (somente `npm run dev`).
- Tipos TS gerados do OpenAPI (`npm run gen:api`).
- Testes: 26 pytest (fluxo, segurança, Techne com respx), 7 vitest (máscaras e regras de OCR) e 1 e2e Playwright do fluxo completo com OCR real.
- Dockerfile de imagem única (BFF servindo o SPA na mesma origem).
- Documentação: README, CHECKLIST, `docs/` (arquitetura, integração Techne, API, segurança, OCR, deploy).

### Alterado (em relação ao portal legado)
- Payload do candidato sem campos duplicados (`codCandidato`/`codigoCandidato`, `pais`/`paisSelect`, `municipio`/`enderecoMunicipioCode`, `cep`/`cepEs`) nem flags `obrigatorio*`.
- `lyceumRetorno` substituído por status HTTP + erros por campo; cache-buster `_` removido.
- Documentos enviados um a um, no lugar de um único multipart com todos.

### Segurança
- Dados de cartão não trafegam pelo BFF (cartão desabilitado na fase 1).
- pdf.js com `isEvalSupported: false` (mitigação do CVE-2024-4367).
- O backend recusa iniciar em `LYCEUM_MODE=techne` com segredo de sessão padrão.
