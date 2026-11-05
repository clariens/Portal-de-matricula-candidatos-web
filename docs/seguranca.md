# Segurança

## Credencial do Lyceum
- O Basic de serviço fica **só** no backend (`backend/.env`, ou secret do ambiente). Nunca use prefixo `VITE_*`.
- Verificação: depois do `npm run build`, `grep -r LYCEUM frontend/dist` não pode encontrar nada.

## Autorização por pessoa (o ponto mais crítico)
Quem tem o Basic consegue agir em nome de **qualquer** candidato, porque o Lyceum só recebe códigos no path ou no body. Por isso:
- A identidade (`codPessoa`) vem **somente** do cookie de sessão assinado.
- Toda rota `/inscricoes/{ref}/…` passa por `inscricao_autorizada` ([deps.py](../backend/app/api/deps.py)), que lista as
  inscrições da pessoa da sessão e responde 404 se a inscrição de `{ref}` não estiver entre elas.
- O corpo das requisições não carrega ids de pessoa, candidato ou concurso.

## Número da inscrição fora das URLs
- As telas (`/matricula/{ref}/…`) e a API (`/api/v1/inscricoes/{ref}/…`) usam uma referência opaca, criptografada com
  AES-SIV (chave derivada do `PORTAL_SESSION_SECRET`) e amarrada à sessão (sid + pessoa). O número da inscrição não
  aparece na barra de endereço, no histórico do navegador, em links compartilhados nem nos logs de acesso.
- A referência só esconde o número: a autorização continua sendo `inscricao_autorizada` (a inscrição tem que ser
  da pessoa logada). Referência de outra sessão ou adulterada → 404.
- O número continua visível **na tela** para o próprio candidato (histórico e topo do wizard), para falar com a
  secretaria.

## Sessão
- Cookie `portal_session`: assinado com `PORTAL_SESSION_SECRET` (itsdangerous), `HttpOnly`, `SameSite=Lax`, `Secure` em
  produção (`PORTAL_COOKIE_SECURE=true`), expira em `PORTAL_SESSION_HORAS` (12 h).
- O backend **recusa iniciar** com o segredo de sessão padrão. Sem a configuração do Lyceum ele inicia, mas as
  rotas respondem 503 (`NaoConfigurado`).
- Sessão do legado (JSESSIONID do candidato): cookie `portal_legado` **criptografado** (Fernet, chave derivada do
  `PORTAL_SESSION_SECRET`), `HttpOnly`, `Path=/api` e com validade de 25 min. O navegador não lê o JSESSIONID, e
  cookie adulterado ou de outra sessão é descartado. Trocar o `PORTAL_SESSION_SECRET` derruba todas as sessões.

## Anexos no navegador (LGPD)
- Até o envio final, os documentos (inclusive RG) ficam no **IndexedDB do navegador** do candidato. São apagados
  ao enviar, ao remover, ao **sair** e depois de 24 h. Em computador compartilhado, o candidato deve clicar em Sair.
- O selo assinado (`app/core/selo.py`) impede trocar o arquivo depois da conferência ou forjar o resultado da IA.
- CSRF: SameSite=Lax mais exigência de `X-Requested-With` em métodos mutáveis. Um formulário cross-site não consegue enviar esse header.

## Prévia dos documentos enviados
- O arquivo vem do legado na sessão do próprio candidato. O `id` do documento é lido da tela "Documentos Ingresso"
  no servidor, nunca recebido do navegador, e a inscrição passa pela mesma checagem de dona (`inscricao_autorizada`).
- Resposta com `Cache-Control: private, no-store`, `X-Content-Type-Options: nosniff` e `Content-Disposition: inline`.
  O tipo é decidido pela assinatura do arquivo (JPEG, PNG ou PDF); qualquer outra coisa vira "prévia indisponível".
- No navegador, a prévia fica só em memória (URL de objeto), liberada ao sair da etapa. Nada vai para o IndexedDB.

## Cache das telas no navegador
- Lista de inscrições, Meus dados, contrato, lista de documentos e prévias ficam **só em memória** na aba
  (`lib/cacheTelas.ts`), por até 5 min. Nada vai para `localStorage`, IndexedDB ou cache HTTP.
- Apagado ao entrar, ao sair e quando a sessão expira (401), para nada de uma conta ficar para a próxima pessoa
  no mesmo computador. Boleto e PIX nunca entram (cada geração registra uma cobrança).

## Meus dados
- O `idPessoa` enviado ao legado vem da página "Meus Dados" aberta na sessão do candidato, nunca do navegador.
- A troca de senha exige a senha atual; nenhuma senha vai para o log. Se o legado pedir reCAPTCHA, o portal recusa
  (409) em vez de tentar contornar.

## Upload
- Extensões aceitas: pdf, jpg, jpeg, png. A **assinatura mágica** do conteúdo é conferida (não basta a extensão).
- Limite de `PORTAL_UPLOAD_MAX_MB` (10 MB), lido com teto para não carregar arquivos maiores em memória.
- Nome do arquivo reduzido a `basename`.
- O texto bruto do OCR **não** é enviado ao servidor, só veredito, confiança, campos conferidos e alertas.

## Pagamento (PCI)
- Na fase 1 o cartão fica desabilitado e o BFF rejeita o plano de cartão (422).
- Quando o cartão for habilitado: tokenizar no navegador com o SDK do gateway, e só o token chega ao BFF. Nunca número, CVV ou validade.

## PDF
- pdf.js 3.11 com `isEvalSupported: false` (mitigação do CVE-2024-4367). Atualizar para pdf.js 4.x quando possível.

## Logs
- `[lyceum] MÉTODO caminho → status`, sem corpo, CPF ou nome. Não logar o header `Authorization`.

## Análise de segurança (05/11/2026)
Revisão só de leitura do BFF, da tela, do deploy e das dependências. Os achados de severidade Alta e Média foram
conferidos no código. Nenhuma chamada foi feita ao Lyceum.

**Resultado geral:** não há IDOR (ninguém age sobre a inscrição de outra pessoa), CSRF, XSS nem segredo no
histórico do git. Os problemas reais são de **disponibilidade, abuso e integridade** (cobrança na inscrição errada
ou em duplicidade, custo da IA, documentos esquecidos no navegador) e de **endurecimento** (headers, cookies,
limites).

| # | Sev. | Achado | Onde | Correção | Situação |
|---|---|---|---|---|---|
| S1 | Alta | Imagem "bomba" (PNG de 20 KB com 13000×13000 px) consome cerca de 2 GB ao ser decodificada; o Pillow só avisa abaixo de 179 M pixels. Qualquer candidato Convocado derruba a instância | `services/imagens.py:13`, `ia_documentos.py:175`, `legado.py:793` | Ler só o tamanho (`Image.open`) e recusar acima de cerca de 40 MP antes de decodificar; `DecompressionBombWarning` como erro; `img.draft()` no JPEG | pendente |
| S2 | Alta | `efetivar.json` pode rodar duas vezes: o prazo do legado (120 s) passa do `maxDuration` da Vercel (60 s); a função morre antes de conferir o histórico e o candidato tenta de novo. Não há trava contra clique duplo | `legado.py:1237`, `vercel.json` | Prazos abaixo do `maxDuration` (ou subir o `maxDuration`); marcar "efetivando" no cookie e recusar nova tentativa por alguns minutos; revalidar o histórico antes do POST; uma requisição por vez na tela | pendente |
| S3 | Média | Pagamento, primeiro envio de documentos e boleto do término agem sobre a inscrição **aberta na sessão do legado**, não sobre a da URL. Com duas inscrições Convocado em duas abas, a matrícula e a cobrança podem cair na outra | `legado.py:518` (`_pagina_pagamento`), `:553`, `:628`, `_enviar_primeiro` | Guardar no cookie qual inscrição o legado tem aberta (atualizado no `form_ingresso`) e, se não for a da URL, reabrir antes de gravar; se o legado não liberar, pedir para revisar os dados | pendente (validar em DEV com uma inscrição Convocado) |
| S4 | Média | Sem limite de tentativas: login (teste de senhas por CPF), recuperar senha (bombardeio de e-mail), cupom (enumeração), boleto e PIX (cada chamada registra uma cobrança no banco), conferência por IA | `api/auth.py`, `api/inscricoes.py` | Regras de rate limit no Vercel Firewall por IP para `/api/v1/auth/*`, `/cupons/*`, `/pagamento/*` e `/documentos/*`; intervalo mínimo entre gerações de boleto/PIX guardado no cookie (429); boleto como POST | pendente |
| S5 | Média | Teto de gasto da IA contornável: o contador usa o `sid` (novo login zera) e o teto diário é por instância; PDF vai inteiro (até 100 páginas) | `ia_documentos.py:124-172`, `inscricoes.py:154` | Limite de gasto no workspace da Anthropic (o único teto global); mandar só as 1 ou 2 primeiras páginas; chave do contador por pessoa + inscrição + tipo; validações baratas antes da IA | pendente |
| S6 | Média | Documentos (RG, CPF, com nome e CPF lidos) ficam no IndexedDB se a sessão expira, a aba fecha ou outra pessoa entra no mesmo computador; o vencimento de 24 h só roda na etapa de documentos | `auth.tsx`, `lib/anexosLocais.ts:72` | Limpar vencidos ao abrir o portal; apagar no 401 e quando entrar outra pessoa; guardar o dono em cada registro; limpar também a `sessionStorage` e o cache de boleto/PIX ao sair | pendente |
| S7 | Média | Nenhum header de segurança: sem CSP, sem proteção contra iframe (clickjacking), sem HSTS, Referrer-Policy ou Permissions-Policy | `vercel.json`, `main.py` | Headers no `vercel.json` (testar a CSP primeiro em modo Report-Only); CSP para `/arquivo`: `sandbox; default-src 'none'` | pendente |
| S8 | Média (a confirmar) | O `idPessoa` do login é lido por regex sem âncora em qualquer ponto da página "Meus Dados". Se o legado ecoar o e-mail sem escapar antes do campo real, um e-mail forjado faria a sessão carregar nome e CPF de outra pessoa | `legado.py:102`, `:282` | Ler pelo `frm-pessoa-fisica` (`parse_form`) e exigir o mesmo id nos dois forms; conferir o CPF do `obterPessoa` com o login; recusar `"<>` no e-mail. Confirmar na página real do DEV | pendente |
| S9 | Baixa | Cookies: `Secure` desligado por padrão (depende da variável), sem prefixo `__Host-`; segredo de sessão sem tamanho mínimo; sessão do portal vale 12 h e o logout não a revoga | `config.py:52-53`, `main.py:28`, `auth.py:31` | `Secure` por padrão; `__Host-portal_session`; exigir 32+ bytes no segredo; `/me` nulo sem sessão do legado; reduzir as 12 h | pendente |
| S10 | Baixa | Exposição: `/api/docs` e `/api/openapi.json` públicos; `/health` sem login consulta o Lyceum a cada chamada; mensagens do legado e nomes de variáveis de ambiente chegam ao navegador | `main.py:86-88`, `core/errors.py:24`, `legado.py` `_retorno` | Desligar docs em produção; cache de 30 s no `/health`; mensagens genéricas | pendente |
| S11 | Baixa | Dependências do navegador: `react-router-dom` 6.26.2 (redirecionamento aberto; não explorável hoje) e `pdfjs-dist` 3.11 (CVE-2024-4367, mitigada com `isEvalSupported: false`). `tar`/`node-pre-gyp` (crítico no `npm audit`) só na instalação, não vão para o site | `frontend/package.json` | `react-router-dom` 6.30.6; `pdfjs-dist` ≥ 4.2.67 (worker `.mjs`); `npm audit` e `pip-audit` na CI | pendente |
| S12 | Baixa | Uploads: o multipart inteiro é lido antes do limite por arquivo (`max_files=40`); arquivo com assinatura JPEG e conteúdo inválido passa com veredito "erro"; sem IA, o selo assina a análise que veio do navegador; envios em paralelo podem duplicar documentos | `inscricoes.py:108,119,181`, `legado.py:821` | Limite de corpo; `max_files` baixo; recusar arquivo que o Pillow não abre; marcar a análise do navegador como `navegador`; um envio por vez | pendente |
| S13 | Baixa | Entradas sem formato ou tamanho: `municipioCodigo`, `voucher`, campos do responsável; `href` do questionário sem checar o esquema (`javascript:`); URL absoluta no QR do PIX vai a outro host | `candidato.py:26`, `pagamento.py`, `EtapaConclusao.tsx:117`, `legado.py:680` | `pattern`/`max_length`; aceitar só `https:` do legado; QR só da mesma origem ou `data:image/png` / `data:image/jpeg` | pendente |
| S14 | Info | `_TITULO_RE` definida duas vezes (o log de erro do primeiro upload sai vazio); regex com backtracking em `_DOC_RE` (só conteúdo do legado chega nela); Google Fonts manda o IP do candidato ao Google | `legado.py:100,1088-1089`, `index.html` | Renomear; parser HTML; hospedar as fontes | pendente |

**Conferido e OK:**
- **Autorização:**
  - Todas as rotas com `{ref}` usam `inscricao_autorizada`.
  - A ref é AES-SIV amarrada a `sid|pessoa`.
  - O corpo das requisições não traz ids de pessoa nem de inscrição.
  - `tipo`, plano e id do arquivo são validados contra a página do legado.
- **Sessão e cookies:**
  - O `portal_legado` de outra sessão é ignorado.
  - Cada login gera um `sid` novo.
  - Cada uso do segredo tem sal próprio.
- **CSRF:** `X-Requested-With` em todos os métodos mutáveis, inclusive login, logout e recuperar senha.
- **Legado:**
  - Não há SSRF a partir do navegador: as URLs vêm só da configuração, sem seguir redirecionamento.
  - Os parâmetros vão codificados (`params`/`data`/`json`).
- **Selo:** amarra inscrição, tipo e sha256 do arquivo; vale 24 h.
- **Tela:**
  - Nenhum `dangerouslySetInnerHTML`/`innerHTML`/`eval`.
  - Os textos do legado são mostrados como texto.
  - Todo `target=_blank` tem `rel`.
  - O inspetor de API fica fora do build de produção.
  - Não há source maps em produção.
- **Segredos e logs:**
  - `backend/.env` nunca entrou no git.
  - Não há `VITE_*` com segredo, e o build não contém `LYCEUM_*`, `PORTAL_*` nem `ANTHROPIC`.
  - Os logs não levam senha, CPF, corpo nem o header `Authorization`.
- **Gravações irreversíveis:** simulação por padrão. Boleto e PIX ficam bloqueados em simulação, e o `efetivar` nunca é reenviado sozinho.

## Pendências
- Os itens S1 a S14 da análise acima.
