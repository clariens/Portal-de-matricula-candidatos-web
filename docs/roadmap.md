# Próximas etapas

Situação em 29/10/2026 e o que falta, em ordem de prioridade. O andamento item a item fica no
[CHECKLIST](../CHECKLIST.md).

## Onde estamos
| Parte | Situação contra o Lyceum DEV |
|---|---|
| Login, histórico, recuperação de senha | ✅ funcionando (Processo Seletivo legado, na sessão do candidato) |
| Etapa 1 · Dados | ✅ leitura e gravação reais (`/r/ingresso`, `atualizar.json`) |
| Etapa 2 · Documentos | ✅ conferência por IA, envio um documento por chamada (o primeiro pela rota do form, os seguintes pela avulsa) com resultado e progresso por documento, confirmados em "Documentos Ingresso" |
| Etapa 3 · Pagamento | ⚠ planos e cupom reais; confirmação **só em simulação** (`LYCEUM_PAGAMENTO_MODO=simular`) |
| Etapa 4 · Conclusão | ❌ responde 501 contra o Lyceum real (só funciona no dublê dos testes) |
| Cabeçalho: Área de interesse e Cadastre-se | ⚠ links para as **páginas do legado** (o portal ainda não tem as próprias) |
| Hospedagem | ✅ Vercel (Services), sem banco de dados; homologação interna |

## Etapa A · Pagamento funcionando de ponta a ponta (prioridade)

O que falta para a tela de pagamento sair da simulação e levar o candidato até a matrícula:

1. **Primeiro envio real do `efetivar.json` em DEV.** Ele **cria a matrícula**, então precisa de autorização
   antes. Ligar `LYCEUM_PAGAMENTO_MODO=enviar` só para esse teste, com um candidato de teste em "Convocado" e
   documentos enviados. Registrar a resposta (redirecionamento para `/r/terminoIngresso`), o que muda no histórico
   e o que a secretaria vê.
2. **Valores na tela.** A página do legado não informa valor de parcela nem total (`hdnValorTotal` vazio). Avaliar
   `GET /v2/tabela/concursos?pk[concurso]=` (`boleto_valor`, `planopag`) ou a tabela de planos na API v2. Se não
   houver fonte confiável, manter "6 mensalidades no semestre" sem preço.
3. **Cupom de 100%.** O legado troca o plano por `N:N:N:1` e esconde as formas de pagamento. Tratar no BFF
   (`efetivar_pagamento` aceitar esse plano só quando o cupom validado for 100%) e na tela (esconder as formas e
   mostrar "Bolsa integral").
4. **Depois de confirmar: a cobrança.** Ler `/r/terminoIngresso` após o `efetivar.json` e mostrar o que o Lyceum
   devolver (boleto ou PIX da 1ª parcela, vencimento). Hoje a tela mostra só as instruções fixas.
5. **Etapa 4 · Conclusão pelo legado.** Mapear `/r/terminoIngresso` (dados da matrícula, contrato) e
   `POST /r/terminoIngresso/proximo.json` (concluir; leva ao `/r/questionario`). O `proximo.json` também é
   irreversível: precisa de autorização antes do primeiro envio real.
6. **Página de pagamento fechada.** Hoje, se o candidato voltar direto ao pagamento numa sessão nova, a tela pede
   "Revisar meus dados" (o legado exige salvar os dados na mesma sessão). Avaliar refazer esse caminho
   automaticamente no BFF (salvar os dados atuais sem mudança e abrir os documentos) para o candidato não perceber.
7. **Cartão de crédito** (fase 2): gateway com tokenização no navegador (PCI). O BFF nunca recebe dados de cartão.

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

## Etapa C · Endurecimento antes de produção
- Recuperação de senha real testada com uma conta autorizada (envia e-mail ao dono da conta).
- Rate limit no login e na recuperação de senha.
- CI (lint + testes + e2e) e variáveis de produção (`LYCEUM_*` de produção, `PORTAL_COOKIE_SECURE=true`).
- Limites de upload de produção confirmados com o time Lyceum (DEV aceita 1 MB por arquivo e 1 MiB por envio).
- Aval de LGPD / IA CoE: fotos de RG passam pela IA (Claude) e ficam no navegador até o envio.
- Teto de gasto da IA compartilhado entre instâncias (hoje é por instância).
- Rotação das credenciais coladas durante o desenvolvimento (senha da API Lyceum e chave da Anthropic).
- Acessibilidade e teste em celulares reais; piloto com uma unidade e plano de corte do portal antigo.

## Etapa D · Migração para a API Techne v2 (quando o Lyceum liberar)
O portal usa o Processo Seletivo legado porque a API v2 não autentica candidato e não expõe as rotas de inscrição.
Cada método do gateway pode trocar de fonte sem mexer nas telas (tabela `ENDPOINTS` em `techne.py`). Ver
[integracao-techne.md](integracao-techne.md).
