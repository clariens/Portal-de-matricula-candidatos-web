# Checklist de entrega

Legenda: `[x]` feito · `[ ]` pendente · **(Lyceum)** depende do time Lyceum/Techne.

## Fase 0 — Fundação e descoberta
- [x] Scaffold backend (FastAPI, pydantic-settings, ruff, pytest) e frontend (Vite React TS, vitest)
- [x] `.env.example`, `.gitignore`, README, CHANGELOG `0.1.0`
- [x] Contrato da API `/api/v1` (Pydantic → OpenAPI → tipos TS)
- [x] `LyceumGateway` + `MockGateway` + `TechneGateway` com tabela `ENDPOINTS`
- [ ] Levantar no Swagger Techne v2 os endpoints de cada necessidade e capturar fixtures mascaradas — **(Lyceum)**
- [ ] Confirmar se `/v2/pessoas/autenticacao` aceita candidato (CPF/e-mail) e qual id retorna (pessoa vs. candidato) — **(Lyceum)**
- [ ] Registrar as lacunas sem endpoint v2 como pendências formais com o time Lyceum — **(Lyceum)**

## Fase 1 — Login e histórico
- [x] Sessão por cookie httpOnly assinado, `/auth/login`, `/auth/logout`, `/me`
- [x] Guarda de rota no front e retorno à página pedida após o login
- [x] Login ligado ao Techne v2 (`POST /v2/pessoas/autenticacao`)
- [x] Histórico em cartões, com ação principal conforme a situação
- [ ] `listar_inscricoes` no Techne v2 — **(Lyceum)**
- [ ] "Esqueci minha senha": definir o fluxo (Techne ou portal atual) — **(Lyceum)**

## Fase 2 — Etapa Dados
- [x] GET/PUT candidato com payload limpo e erros por campo
- [x] Máscaras, validação local, CEP preenchendo o endereço automaticamente
- [x] Retomada por URL e "Continuar depois"
- [ ] `obter_candidato` / `atualizar_candidato` no Techne v2 — **(Lyceum)**
- [ ] Código de município Lyceum (ex.: `002174`) a partir do CEP — hoje a CEP vem do ViaCEP no modo techne — **(Lyceum)**
- [ ] Países/municípios de nascimento (o legado envia `paisNascimento`/`municipioNascimento`)

## Fase 3 — Etapa Documentos
- [x] Upload individual com arrastar e soltar, prévia e progresso
- [x] OCR local self-hosted (sem CDN) com regras cpf/id/escolar/declaração (≤ 2022)/residência/nome
- [x] Divergente/ilegível exige confirmação antes do envio para conferência manual
- [x] BFF valida extensão, tamanho e assinatura mágica
- [ ] `listar_documentos` / `enviar_documento` no Techne v2 — **(Lyceum)**
- [ ] Confirmar a tabela código↔documento (hoje pela ordem do DOM legado) — **(Lyceum)**
- [ ] Testar o limite de body do nginx (`client_max_body_size`) com PDF de ~10 MB em Base64

## Fase 4 — Etapa Pagamento
- [x] Responsável financeiro: Eu, Outra pessoa (CPF), Empresa (CNPJ) com endereço
- [x] Boleto e PIX com valor da parcela; cartão desabilitado
- [x] Cupom com validação imediata e recálculo dos planos
- [ ] `opcoes_pagamento` / `validar_cupom` / `efetivar_pagamento` no Techne v2 — **(Lyceum)**
- [ ] Gateway de cartão com tokenização (PCI) — decisão de fornecedor
- [ ] Linha digitável / PIX copia e cola na tela (se o Lyceum devolver)

## Fase 5 — Conclusão e pós-matrícula
- [x] Tela de sucesso: matrícula, 1ª parcela, contrato Clicksign, disciplinas
- [x] Confirmar conclusão e mostrar questionário pendente
- [x] Histórico mostra "Pré-Matriculado" com Contrato e Documentos
- [ ] `obter_matricula` / `confirmar_matricula` / `questionarios_pendentes` no Techne v2 — **(Lyceum)**
- [ ] Status real do contrato Clicksign (webhook ou consulta)

## Fase 6 — Endurecimento e entrega
- [x] Testes: pytest (26), vitest (7) e e2e Playwright (fluxo completo com OCR real)
- [x] Logs `[lyceum]` sem PII; `/api/v1/health`
- [x] Dockerfile de imagem única
- [ ] Auditoria de acessibilidade (leitor de tela, contraste) e teste em celulares reais
- [ ] Rate limit no login (BFF ou proxy)
- [ ] CI (lint + testes + e2e) no pipeline
- [ ] Variáveis de produção (base URL, Basic, segredo, `PORTAL_COOKIE_SECURE=true`)
- [ ] Piloto com uma unidade e plano de corte do portal antigo
