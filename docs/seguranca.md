# Segurança

## Credencial do Lyceum
- O Basic de serviço fica **só** no backend (`backend/.env`, ou secret do ambiente). Nunca use prefixo `VITE_*`.
- Verificação: depois do `npm run build`, `grep -r LYCEUM frontend/dist` não pode encontrar nada.

## Autorização por pessoa (o ponto mais crítico)
Quem tem o Basic consegue agir em nome de **qualquer** candidato, porque o Lyceum só recebe códigos no path ou no body. Por isso:
- A identidade (`codPessoa`) vem **somente** do cookie de sessão assinado.
- Toda rota `/inscricoes/{cod}/…` passa por `inscricao_autorizada` ([deps.py](../backend/app/api/deps.py)), que lista as
  inscrições da pessoa da sessão e responde 404 se `{cod}` não estiver entre elas.
- O corpo das requisições não carrega ids de pessoa, candidato ou concurso.

## Sessão
- Cookie `portal_session`: assinado com `PORTAL_SESSION_SECRET` (itsdangerous), `HttpOnly`, `SameSite=Lax`, `Secure` em
  produção (`PORTAL_COOKIE_SECURE=true`), expira em `PORTAL_SESSION_HORAS` (12 h).
- O backend **recusa iniciar** em `LYCEUM_MODE=techne` com o segredo padrão.
- CSRF: SameSite=Lax mais exigência de `X-Requested-With` em métodos mutáveis. Um formulário cross-site não consegue enviar esse header.

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

## Pendências
- Rate limit no `/auth/login` (no proxy ou com middleware).
- Content-Security-Policy no proxy, com `worker-src 'self' blob:` e `wasm-unsafe-eval` para o tesseract.
