# Deploy

## Imagem única (recomendado)
O `Dockerfile` na raiz faz o build do front e entrega o BFF servindo `/api/v1` e o SPA na **mesma origem**.

```bash
docker build -t portal-matricula .
docker run -p 8000:8000 --env-file backend/.env portal-matricula
```

## Variáveis de produção
| Variável | Valor |
|---|---|
| `LYCEUM_API_BASE_URL` | URL de produção da API Techne |
| `LYCEUM_API_BASIC_USER` / `LYCEUM_API_BASIC_PASSWORD` | Usuário técnico de produção (secret) |
| `PORTAL_SESSION_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` (secret) |
| `PORTAL_COOKIE_SECURE` | `true` |
| `PORTAL_CORS_ORIGINS` | Vazio (mesma origem) |
| `PORTAL_UPLOAD_MAX_MB` | `10` |

## Proxy / nginx
- TLS obrigatório (o cookie é `Secure`).
- `client_max_body_size 15m;`. Com Base64, um arquivo de 10 MB vira cerca de 14 MB no envio ao Lyceum. Ajustar também o nginx do Lyceum.
- Repassar `X-Forwarded-*` (o uvicorn sobe com `--proxy-headers`).
- Cache longo em `/assets/*` (nomes com hash) e em `/ocr/*`; sem cache no `index.html`.

## Limites de tamanho do legado (Processo Seletivo)
Medidos em DEV (`desenvolvimento-lyceum`) em 29/10/2026, com PDFs de teste em `POST /r/documentosCandidato/upload`.
Recusa não grava nada.

| Arquivo | Resposta | Gravou |
|---|---|---|
| 20, 10, 5, 3, 2 e 1 MiB | **413** (nginx, página HTML) | não |
| 1.039.993 e 1.000.993 bytes | **500** (Tomcat, sem mensagem) | não |
| 999.893 bytes (requisição ~1.000.150) | 204 | sim |
| 983.033 / 917.497 / 786.425 / 524.281 bytes | 204 | sim |

São duas barreiras:
- **por arquivo, 1.000.000 bytes** (1 MB decimal), na aplicação Java. Erro 500 genérico, sem cabeçalho `mensagem`;
- **por requisição, 1 MiB** (1.048.576 bytes), no nginx. É o `client_max_body_size` padrão do nginx, o que
  indica que o DEV não tem a configuração. O primeiro envio vai num multipart só com todos os documentos, então
  **a soma** dos documentos do primeiro envio precisa caber em ~1 MiB.

Em `backend/.env` do DEV: `LYCEUM_UPLOAD_MAX_KB_POR_ARQUIVO=976` e `LYCEUM_UPLOAD_MAX_KB_TOTAL=1000`.
Produção: confirmar os valores com o time Lyceum, que fala em 20 MB por documento.

## Saúde
`GET /api/v1/health` → 200 `{status:"ok"}` ou 503 `degradado` (Lyceum inacessível ou sem configuração).

## Corte do portal antigo
1. Piloto com uma unidade (ex.: IMEPAC), com o link do e-mail de convocação apontando para o novo portal.
2. Acompanhar logs `[lyceum]` e as taxas de 4xx/5xx por rota.
3. Expandir para as demais unidades e redirecionar `/processo-seletivo/r/ingresso*` para o novo portal.
