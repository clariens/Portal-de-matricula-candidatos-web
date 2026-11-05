# Próximas etapas

Situação em 05/11/2026 e o que falta, em ordem de prioridade. O andamento item a item fica no
[CHECKLIST](../CHECKLIST.md).

## Onde estamos
| Parte | Situação contra o Lyceum DEV |
|---|---|
| Login, histórico, recuperação de senha | ✅ funcionando (Processo Seletivo legado, na sessão do candidato); CPF com ou sem pontuação |
| Etapa 1 · Dados | ✅ leitura e gravação reais (`/r/ingresso`, `atualizar.json`) |
| Etapa 2 · Documentos | ✅ conferência por IA, envio um documento por chamada (o primeiro pela rota do form, os seguintes pela avulsa) com resultado e progresso por documento, confirmados em "Documentos Ingresso"; prévia dos enviados |
| Etapa 3 · Pagamento | ✅ `efetivar.json` real validado em DEV (04/11/2026); boleto (PDF) e PIX (QR + copia e cola) depois de confirmar. Cartão fora (PCI) |
| Etapa 4 · Conclusão | ⚠ matrícula, 1ª parcela e instruções do contrato reais; "Próximo" do contrato e `proximo.json` ainda não ligados (autorização) |
| Pós-matrícula | ✅ telas de Contrato e Documentos de ingresso; boleto e PIX pelo histórico |
| Meus dados | ✅ contato, endereço e troca de senha (validado em DEV) |
| Celular | ✅ layout próprio até 640 px, conferido no fluxo inteiro em 390 px (falta testar em aparelhos reais) |
| Cabeçalho: Área de interesse e Cadastre-se | ⚠ áreas **travadas** (inscrições fora do portal); Cadastre-se leva à página do legado |
| Hospedagem | ✅ Vercel (Services), sem banco de dados; homologação interna |

## Etapa A · Pagamento funcionando de ponta a ponta (prioridade)

O que falta para a tela de pagamento sair da simulação e levar o candidato até a matrícula:

1. ✅ **Feito em 04/11/2026** (ver [pagamento-legado.md](pagamento-legado.md#teste-real-em-dev-04112026-autorizado)). **Primeiro envio real do `efetivar.json` em DEV.** Ele **cria a matrícula**, então precisa de autorização
   antes. Ligar `LYCEUM_PAGAMENTO_MODO=enviar` só para esse teste, com um candidato de teste em "Convocado" e
   documentos enviados. Registrar a resposta (redirecionamento para `/r/terminoIngresso`), o que muda no histórico
   e o que a secretaria vê.
2. **Valores na tela.** A página do legado não informa valor de parcela nem total (`hdnValorTotal` vazio). Avaliar
   `GET /v2/tabela/concursos?pk[concurso]=` (`boleto_valor`, `planopag`) ou a tabela de planos na API v2. Se não
   houver fonte confiável, manter "6 mensalidades no semestre" sem preço.
3. **Cupom de 100%.** O legado troca o plano por `N:N:N:1` e esconde as formas de pagamento. Tratar no BFF
   (`efetivar_pagamento` aceitar esse plano só quando o cupom validado for 100%) e na tela (esconder as formas e
   mostrar "Bolsa integral").
4. ✅ **Feito em 04/11/2026. Depois de confirmar: a cobrança.** Boleto em PDF (`gerarBoleto` do término ou do
   Histórico) e PIX com QR, copia e cola e recebedor (`r/historico/geraPix`) na conclusão e pelo histórico. Falta
   o status do cartão (fase 2).
5. **Etapa 4 · Conclusão pelo legado.** ✅ Matrícula e instruções do contrato (`/r/contrato`). Falta
   `POST r/contrato/aceitaContrato.json` ("Próximo" do contrato) e `POST /r/terminoIngresso/proximo.json`
   (concluir; leva ao `/r/questionario`). Os dois são irreversíveis: precisam de autorização antes do primeiro
   envio real.
6. **Página de pagamento fechada.** Hoje, se o candidato voltar direto ao pagamento numa sessão nova, a tela pede
   "Revisar meus dados" (o legado exige salvar os dados na mesma sessão). Avaliar refazer esse caminho
   automaticamente no BFF (salvar os dados atuais sem mudança e abrir os documentos) para o candidato não perceber.
7. **Cartão de crédito** (fase 2): ao escolher Cartão, o formulário com os campos do legado
   ([pagamento-legado.md](pagamento-legado.md)). O legado recebe os dados do cartão em texto no `efetivar.json`;
   para o BFF não entrar no escopo PCI, tokenizar no navegador com um gateway. O BFF nunca recebe dados de cartão.

Pronto quando: um candidato de teste vai de "Convocado" a "Pré-Matriculado" pelo portal, e o histórico, a
secretaria e a cobrança batem com o que o legado faria.

## Etapa B · Telas próprias das áreas de interesse

Hoje "Área de interesse → Graduação → …" e "Cadastre-se" abrem as páginas do Processo Seletivo legado em nova
aba. O objetivo é ter essas telas no portal, com o mesmo visual, para quem ainda não é candidato.
Mapeamento das rotas do legado em [cabecalho-processo-seletivo.md](cabecalho-processo-seletivo.md).

1. **Lista de processos por subgrupo** (`/cursos/:subgrupo`, por exemplo Enem): cartões com processo, unidade e
   curso. Fonte: `GET /processo-seletivo/subgrupo?id=` (HTML; o BFF lê e devolve JSON, como já faz com o histórico)
   ou, se houver, a lista de ofertas na API v2.
2. **Busca de cursos** ("Qual curso você procura?" no cabeçalho): `POST /processo-seletivo/busca` (`buscar=`).
3. **Detalhe da oferta** (`/cursos/oferta/:id`): mapear `GET /processo-seletivo/oferta?id=` (descrição,
   calendário, documentos, valores) e o botão de inscrição.
4. **Inscrição em uma oferta**: mapear o fluxo do legado a partir da oferta. Ele cria a inscrição no Lyceum, então
   precisa de autorização antes do primeiro teste real.
5. **Cadastro próprio** ("Cadastre-se"): formulário do portal com o mesmo visual, usando
   `GET cadastro/validarPessoa` (CPF já cadastrado → login), `endereco/*` e `POST cadastro/cadastrar.json`.
   Cria a pessoa no Lyceum: só com a rota aprovada e autorização para o primeiro envio. Inclui o aceite LGPD.
6. **Menu do cabeçalho apontando para as telas novas**, com o legado como reserva enquanto cada tela não existir.
7. **Ids de produção x DEV**: os subgrupos (4, 15, 16, 17, 31) são iguais nos dois hoje. As ofertas mudam a cada
   processo, então nunca devem ficar fixas no código.

Pronto quando: um visitante encontra o curso, vê os detalhes, se cadastra e se inscreve sem sair do portal.

## Etapa E · Chat de suporte dentro do portal (próximo plano)
O candidato fala com o suporte sem sair do portal. Direção definida em 05/11/2026: **usuários de atendimento** e a
conversa guardada no **SQL Server interno**, com o **n8n** fazendo a ponte entre a nossa API e o banco (o banco só é
acessível de dentro da rede da empresa).

```
Navegador ──▶ BFF (/api/v1/suporte/…) ──HTTPS + segredo/HMAC──▶ n8n (webhooks) ──▶ SQL Server (rede interna)
                    ▲ identidade do candidato vem da sessão          ▲ a tela de atendimento também passa por aqui
```

1. **Decisões antes de começar:**
   - Quem atende (secretaria, central, comercial) e em que horário. Fora do horário: mensagem automática ou
     assistente com IA respondendo as dúvidas comuns e passando para um humano.
   - O n8n precisa ser alcançável pela Vercel (webhook público com autenticação forte), ou o BFF de produção
     precisa rodar dentro da rede. Confirmar com a infraestrutura.
   - **Muda uma decisão de arquitetura:** até aqui o portal não guarda nada. O chat é o primeiro dado
     persistente, e fica no SQL Server da empresa, não no BFF. A sessão continua sem estado.
   - LGPD: conversas com dados pessoais (CPF, documentos, pagamento). Definir retenção, quem acessa e aval do DPO.
2. **Modelo no SQL Server:** `atendente` (usuário de suporte, perfil e unidades), `conversa` (candidato, inscrição,
   unidade, situação, atendente), `mensagem` (autor, texto, data, lida). Criação dos usuários de atendimento:
   pelo n8n ou por uma tela de administração. O login dos atendentes nunca reaproveita o Basic do Lyceum.
3. **API do BFF:** `GET/POST /suporte/conversa` e `/suporte/mensagens?depois=` para o candidato. O BFF chama os
   webhooks do n8n com segredo próprio, assinatura HMAC e timeout; o candidato nunca fala direto com o n8n. O
   candidato é identificado pela sessão (`codPessoa`), nunca por id vindo do navegador. A mensagem já leva o
   contexto: inscrição, etapa, curso e unidade.
4. **Tempo real:** a Vercel não mantém WebSocket. Começar com consulta a cada poucos segundos, só com o chat aberto
   e com intervalo maior em segundo plano. Se o volume crescer, avaliar SSE ou um serviço de tempo real.
5. **Tela do candidato:** botão de ajuda flutuante (no celular, acima do rodapé da matrícula), conversa em painel,
   aviso de mensagem nova e anexo opcional (mesmas regras de upload dos documentos).
6. **Tela de atendimento:** fila por unidade, conversa com o contexto do candidato, aviso de mensagem nova. Login
   próprio dos atendentes (de preferência com a conta Microsoft da empresa).
7. **Segurança:** limite de mensagens por candidato e por minuto, tamanho máximo, texto sempre mostrado como texto
   (nunca HTML), webhooks do n8n que só aceitam o BFF, logs sem o conteúdo das mensagens.

Pronto quando: um candidato abre o chat no portal, a mensagem chega à fila da unidade, o atendente responde e a
resposta aparece para o candidato, com tudo guardado no SQL Server e nada exposto fora da rede além do webhook
autenticado.

## Etapa F · Tela inicial para todas as unidades
A tela de login hoje fala só de Medicina ("Educação médica · Seu jaleco começa na matrícula", ícones médicos e
traçado de ECG), mas o portal atende todas as unidades e cursos da Clariens.
1. Texto e imagens neutros, para qualquer curso, mantendo a identidade da marca (gradiente, hexágonos).
2. Nomes ou logos de todas as unidades: hoje aparecem só ZARNS, UNESUL BAHIA e IMEPAC. Avaliar ler a lista do
   cabeçalho do legado em vez de deixar fixa no código.
3. Decidir se o monitor cardíaco fica (marca de Medicina) ou vira uma animação neutra.
4. Conferir no celular e no computador; atualizar as capturas do e2e.

## Etapa C · Endurecimento antes de produção
- Recuperação de senha real testada com uma conta autorizada (envia e-mail ao dono da conta).
- Rate limit no login e na recuperação de senha.
- CI (lint + testes + e2e) e variáveis de produção (`LYCEUM_*` de produção, `PORTAL_COOKIE_SECURE=true`).
- Limites de upload de produção confirmados com o time Lyceum (DEV aceita 1 MB por arquivo e 1 MiB por envio).
- Aval de LGPD / IA CoE: fotos de RG passam pela IA (Claude) e ficam no navegador até o envio.
- Teto de gasto da IA compartilhado entre instâncias (hoje é por instância).
- Rotação das credenciais coladas durante o desenvolvimento (senha da API Lyceum e chave da Anthropic).
- Análise de segurança completa da aplicação (iniciada em 05/11/2026; resultado em [seguranca.md](seguranca.md)).
- Acessibilidade e teste em celulares reais; piloto com uma unidade e plano de corte do portal antigo.

## Etapa D · Migração para a API Techne v2 (quando o Lyceum liberar)
O portal usa o Processo Seletivo legado porque a API v2 não autentica candidato e não expõe as rotas de inscrição.
Cada método do gateway pode trocar de fonte sem mexer nas telas (tabela `ENDPOINTS` em `techne.py`). Ver
[integracao-techne.md](integracao-techne.md).
