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
| `LYCEUM_MODE` | `techne` |
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

## Saúde
`GET /api/v1/health` → 200 `{status:"ok"}` ou 503 `degradado` (Lyceum inacessível ou sem configuração).

## Corte do portal antigo
1. Piloto com uma unidade (ex.: IMEPAC), com o link do e-mail de convocação apontando para o novo portal.
2. Acompanhar logs `[lyceum]` e as taxas de 4xx/5xx por rota.
3. Expandir para as demais unidades e redirecionar `/processo-seletivo/r/ingresso*` para o novo portal.
