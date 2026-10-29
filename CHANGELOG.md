# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Versionamento: [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]
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

### Pendente
- Mapear no Swagger Techne v2 os endpoints de inscrições, candidato, documentos, pagamento e conclusão (ver `docs/integracao-techne.md`).
- Pagamento com cartão via gateway com tokenização (PCI).

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
