# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/). Versionamento: [SemVer](https://semver.org/lang/pt-BR/).

## [Não lançado]
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
- Gravação real da Etapa 1 validada em DEV (`atualizar.json`), incluindo os campos montados por JavaScript no legado
  (`enderecoUf`, `paisSelect`), sem os quais o legado recusa o envio.
- Contexto TLS único no processo (`app/core/http.py`): cada cliente HTTP novo recarregava os certificados (~0,5 s).
- Sexo "Outros" (`O`) e lista de estado civil do Lyceum (`União Estável`, `Marital`, `Separado …`).

### Alterado
- `codConcurso` de `Inscricao` passou a ser opcional (o histórico legado só o expõe em Convocado/Pré-Matriculado).
- Testes isolados do `backend/.env` real (`PORTAL_ENV_FILE`).

### Corrigido
- Login Techne validado contra o Lyceum **DEV**: o `UsuarioDTO` traz o código da pessoa em `id` (o mapper não lia esse campo).
- Erro de login do Techne (HTTP 500 com `status` 412 e texto em `titulo`/`mensagemDetalhada`) agora chega ao usuário, sem o prefixo "Erro de autenticação:".
- Logs do httpx em WARNING, para não registrar URLs com dados pessoais.

### Descoberto
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
