# Checklist de entrega

Legenda: `[x]` feito · `[ ]` pendente · **(Lyceum)** depende do time Lyceum/Techne · **(autorização)** grava algo
irreversível no Lyceum e precisa de aval antes do primeiro envio real. Visão geral e prioridades em
[docs/roadmap.md](docs/roadmap.md).

## Fase 0 — Fundação e descoberta
- [x] Backend (FastAPI, pydantic-settings, ruff, pytest) e frontend (Vite React TS, vitest, Playwright)
- [x] Contrato da API `/api/v1` (Pydantic → OpenAPI → tipos TS)
- [x] `LyceumGateway` + `TechneGateway`; dublê do Lyceum só nos testes (`backend/tests/fake_lyceum.py`)
- [x] Integração pelo Processo Seletivo legado, na sessão do próprio candidato (a API v2 não autentica candidato)
- [x] Sem modo de demonstração: o portal só fala com o Lyceum configurado e não inicia sem configuração
- [ ] Rotas de candidato na API Techne v2 (login, inscrições, documentos, pagamento, conclusão) — **(Lyceum)**

## Fase 1 — Login, histórico e cabeçalho
- [x] Login real por CPF/e-mail (`j_security_check`), histórico real (`/r/historico`)
- [x] Sessão: cookie assinado + cookie criptografado com a sessão do legado (sem estado no servidor)
- [x] `/me` sem sessão responde `null` (sem erro no console ao abrir o site)
- [x] Tela de login com fundo de tela inteira, logo no card e monitor cardíaco animado
- [x] Esqueci minha senha pelo fluxo do legado (`/recuperarsenha`)
- [x] Cabeçalho: logo, Área de interesse (subgrupos lidos do legado) e Cadastre-se
- [x] Mensagem clara quando o Processo Seletivo está fora do ar
- [ ] Recuperação de senha testada de verdade com uma conta autorizada (envia e-mail ao dono)
- [ ] Rate limit no login e na recuperação de senha

## Fase 2 — Etapa Dados
- [x] Leitura (`/r/ingresso`) e gravação real (`atualizar.json`) validadas em DEV
- [x] CEP pelo ViaCEP + código de município do Lyceum; data de nascimento normalizada
- [x] Sexo "Outros" e lista de estado civil do Lyceum
- [ ] Países/municípios de nascimento (o legado envia `paisNascimento`/`municipioNascimento`)

## Fase 3 — Etapa Documentos
- [x] Lista de documentos lida da página real; obrigatórios conforme o processo
- [x] Conferência por IA (Claude) no servidor; OCR do navegador como reserva; WEBP aceito
- [x] Anexos guardados no navegador (IndexedDB) com selo assinado; nada no servidor entre requisições
- [x] Um documento por chamada: o primeiro pela rota do form (`uploadDocumentosPorProcesso`), sozinho; os seguintes por `documentosCandidato/upload`
- [x] Resultado por documento: o que for recusado fica marcado e o resto é enviado; progresso na tela
- [ ] Confirmar em DEV que o legado registra o primeiro envio com um documento só (próximo envio na inscrição que deu 413)
- [x] "Enviado" só quando aparece em "Documentos Ingresso"; nunca reenvia o que o Lyceum já tem
- [x] Compressão de fotos; limites de tamanho do DEV medidos (1.000.000 bytes por arquivo, 1 MiB por envio)
- [x] Envio recusado por tamanho aponta o documento e marca a linha dele
- [ ] Limites de upload de produção — **(Lyceum)**
- [ ] Substituir documento recusado pela secretaria (mesma rota `documentosCandidato/upload`)

## Fase 4 — Etapa Pagamento (próxima prioridade: Etapa A do roadmap)
- [x] Responsável financeiro: Eu, Outra pessoa (campos do legado), Empresa (CNPJ e inscrições)
- [x] Planos lidos da página real (Boleto, PIX; Cartão "Em breve"); "6 mensalidades no semestre"
- [x] Cupom validado no legado (`validarvoucher`)
- [x] Confirmação monta o corpo do `efetivar.json`; validada em simulação
- [ ] Primeiro `efetivar.json` real em DEV (cria a matrícula) — **(autorização)**
- [ ] Valores das parcelas e total (fonte a definir: `GET /v2/tabela/concursos` ou API de planos)
- [ ] Cupom de 100% (plano `N:N:N:1`, "Bolsa integral")
- [ ] Cobrança real depois de confirmar (boleto/PIX da 1ª parcela via `/r/terminoIngresso`)
- [ ] Abrir o pagamento numa sessão nova sem pedir "Revisar meus dados"
- [ ] Cartão de crédito com tokenização (PCI) — decisão de fornecedor

## Fase 5 — Conclusão e pós-matrícula
- [x] Tela de sucesso (matrícula, 1ª parcela, contrato, disciplinas) — hoje só no dublê dos testes
- [ ] Conclusão pelo legado: `/r/terminoIngresso` e `proximo.json` — **(autorização)**
- [ ] Questionário pendente (`/r/questionario`)
- [ ] Status real do contrato Clicksign

## Fase 6 — Áreas de interesse e cadastro próprios (Etapa B do roadmap)
- [x] Mapeamento do cabeçalho, busca, subgrupos e cadastro do legado (`docs/cabecalho-processo-seletivo.md`)
- [ ] Lista de processos por subgrupo (Vestibular Tradicional, Transferência Externa, Enem, Segunda Graduação, Tradicional Catalão)
- [ ] Busca de cursos no cabeçalho
- [ ] Detalhe da oferta (mapear `oferta?id=`)
- [ ] Inscrição em uma oferta (mapear o fluxo do legado) — **(autorização)**
- [ ] Cadastro próprio (`cadastrar.json`, aceite LGPD) — **(autorização)**
- [ ] Menu do cabeçalho apontando para as telas novas (legado como reserva)

## Fase 7 — Endurecimento e entrega
- [x] Testes: pytest (123), vitest (17) e e2e Playwright (fluxo completo, cabeçalho, recuperação de senha)
- [x] Logs `[lyceum]` sem PII; `/api/v1/health`
- [x] Vercel (Services) sem banco de dados; validado com duas instâncias atendendo o mesmo candidato
- [ ] CI (lint + testes + e2e) no pipeline
- [ ] Variáveis de produção (`LYCEUM_*` de produção, segredo novo, `PORTAL_COOKIE_SECURE=true`)
- [ ] Aval de LGPD / IA CoE; teto de gasto da IA compartilhado entre instâncias
- [ ] Rotação das credenciais usadas no desenvolvimento
- [ ] Acessibilidade e teste em celulares reais
- [ ] Piloto com uma unidade e plano de corte do portal antigo
