# Imagem única: build do front + BFF FastAPI servindo /api/v1 e o SPA na mesma origem.
FROM node:20-alpine AS front
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
COPY frontend/scripts ./scripts
RUN npm ci
COPY frontend/ ./
RUN npx vite build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/backend
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir .
COPY --from=front /src/frontend/dist /srv/frontend/dist
RUN useradd -r portal && chown -R portal /srv
USER portal
EXPOSE 8000
# Variáveis obrigatórias em produção: LYCEUM_MODE=techne, LYCEUM_API_*, PORTAL_SESSION_SECRET, PORTAL_COOKIE_SECURE=true
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
