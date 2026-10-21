# Conferência automática dos documentos

Há dois modos, escolhidos pelo backend (`GET /api/v1/recursos` → `conferenciaDocumentos`):

| Modo | Quando | Quem lê | Quem decide |
|---|---|---|---|
| **IA** (recomendado) | `IA_DOCUMENTOS_ATIVA=true` + `ANTHROPIC_API_KEY` | Claude (visão), no servidor | `backend/app/services/conferencia.py` |
| **Navegador** | sem chave | Tesseract no navegador | `frontend/src/lib/ocr/analisar.ts` |

## Modo IA (servidor)

```
candidato anexa ─▶ BFF valida formato/tamanho ─▶ reduz a imagem (2000 px, corrige rotação EXIF)
   ─▶ Claude devolve JSON (schema): tipo, lado, legível, qualidade, problemas, nome, CPF, RG, nascimento, ano, CEP
   ─▶ conferencia.py compara com o cadastro ─▶ ✓ / ⚠ / ✗
   ─▶ tipo errado: NÃO anexa (só outro arquivo) | demais: anexa (⚠ = secretaria confere)
```

- A IA só **lê e classifica**; quem aprova são as regras do código. Texto escrito no documento é tratado como dado.
- O resultado enviado pelo navegador é ignorado: o servidor é a fonte da verdade.
- Falha, timeout, 429, recusa ou teto de gasto → "Não foi possível conferir automaticamente agora" e o
  documento segue para conferência manual (nunca trava o candidato).
- Frente/verso: só a frente do RG → ⚠ pede o verso; só o verso → confere nome e nascimento.
- A tela mostra "Analisando" pulsando e uma barra fina; vários documentos podem ser analisados ao mesmo tempo.
- Código: `backend/app/services/ia_documentos.py` (chamada, schema, custo) e `conferencia.py` (regras).

### Custos medidos (21/10/2026, fotos reais de RG, `claude-opus-5-5`, esforço `low`)

| Item | Valor |
|---|---|
| Tokens por foto | ~3.700 de entrada / 160–390 de saída |
| Custo por análise | **US$ 0,018–0,023** |
| Tempo por análise | 4–6 s |

Cada chamada registra no log `[ia-documentos] … custo≈US$…` e o acumulado do dia. Controles: teto diário
(`IA_DOCUMENTOS_LIMITE_DIARIO_USD`), no máximo `IA_DOCUMENTOS_CONCORRENCIA` chamadas simultâneas, e limite de
`IA_DOCUMENTOS_TENTATIVAS_POR_DOCUMENTO` análises por documento na sessão. Configure também um limite de gasto no
workspace da Anthropic (Console).

## Modo navegador (OCR local)


O OCR roda **no navegador** do candidato, com tesseract.js 5 (idioma `por`) e pdf.js 3.11 (o PDF é lido pela 1ª página).
A análise começa **no momento em que o arquivo é anexado**, não no envio final, e o resultado aparece na própria linha.

## Sequência para cada arquivo

```
escolher/arrastar arquivo
  └─ 1. formato e tamanho (extensões da página do legado + WEBP; até 10 MB)
  └─ 2. vira imagem (PDF: 1ª página) → miniatura; WEBP é convertido para JPG (o Lyceum não aceita WEBP)
  └─ 3. leitura do texto (OCR) com barra de progresso
  └─ 4. legível?                → não: ⚠ Ilegível                    (outro arquivo OU conferência manual)
  └─ 5. é o documento pedido?   → leitura boa (≥ 60%) e não é: ✗ Documento não reconhecido (só aceita outro arquivo)
                                → leitura fraca (< 60%): ⚠ Não conferido (outro arquivo OU conferência manual)
  └─ 6. os dados conferem?      → não: ✗ Dados não conferem          (outro arquivo OU conferência manual)
                                → ponto a confirmar: ⚠              (anexa com aviso)
  └─ 7. tudo certo              → ✓ Documento conferido              (anexa sozinho)
```

Anexar ≠ enviar: o arquivo fica no servidor do portal como "pronto para envio". O envio ao Lyceum acontece em
"Enviar documentos e continuar" (ver `LYCEUM_DOCUMENTOS_MODO`).

Código: `frontend/src/lib/ocr/analisar.ts` (regras, funções puras) e `frontend/src/pages/wizard/EtapaDocumentos.tsx` (tela).

## O que o candidato pode fazer com cada resultado (`ACAO_POR_VEREDITO`)

| Resultado | Selo | Ação |
|---|---|---|
| `ok` | ✓ Documento conferido | anexa sozinho |
| `atencao` | ⚠ Conferido com ressalva | anexa sozinho, com o aviso |
| `divergente` | ✗ Dados não conferem | "Escolher outro arquivo" ou "Manter este e enviar para conferência manual" |
| `erro` (leitura fraca, < 60%, ou o navegador não conseguiu ler) | ⚠ Não conferido | idem |
| `ilegivel` | ⚠ Ilegível | idem |
| `tipo_errado` (só com leitura ≥ 60%) | ✗ Documento não reconhecido | **só** "Escolher outro arquivo" |

O backend também recusa (422) anexar com `tipo_errado`, para a regra valer mesmo sem passar pela tela.

## Passo 5 — identificação do tipo (`MARCAS_DOCUMENTO`)

Cada documento (pelo código do Lyceum) tem uma lista de expressões típicas; basta uma aparecer no texto lido
(comparação sem acento, sem caixa e sem pontuação).

| Código | Documento | Exemplos de marcas |
|---|---|---|
| 05 | CPF | CADASTRO DE PESSOAS FÍSICAS, RECEITA FEDERAL, CPF |
| 04 | Identidade | REGISTRO GERAL, CARTEIRA DE IDENTIDADE, HABILITAÇÃO, FILIAÇÃO |
| 03 | Histórico / Certificado | HISTÓRICO ESCOLAR, CERTIFICADO DE CONCLUSÃO, ENSINO MÉDIO |
| 02 | Declaração Ensino Médio | DECLARAÇÃO, DECLARAMOS |
| 11 | Comprovante de residência | CONTA, FATURA, ENERGIA, ÁGUA, VENCIMENTO, ALUGUEL |
| 09 / 10 | Certidões | NASCIMENTO / CASAMENTO, REGISTRO CIVIL |
| 06 / 07 | Título / Votação | JUSTIÇA ELEITORAL, TÍTULO ELEITORAL, QUITAÇÃO ELEITORAL |
| 08 | Militar | RESERVISTA, ALISTAMENTO, MINISTÉRIO DA DEFESA |
| 14 | Vacina | VACINA, VACINAÇÃO, DOSE |
| 12 | Histórico de graduação | GRADUAÇÃO, ENSINO SUPERIOR, DISCIPLINA |
| 13 | Termo de confissão de dívida | CONFISSÃO DE DÍVIDA, TERMO |
| 01 | Foto 3x4 | (sem texto: não verifica) |

Limites conhecidos: a nova Carteira de Identidade traz o CPF, então ela é aceita no campo CPF (desde que o número
confira). Marcas genéricas (ex.: "CONTA", "TERMO") reduzem recusas indevidas, mas deixam passar alguns documentos errados.

## Passo 6 — conferência dos dados

| Regra | Documentos | Confere |
|---|---|---|
| `cpf` | 05 | CPF válido no texto igual ao de Seus dados (sem número → ⚠) |
| `id` | 04 | nome (≥ 60% das palavras) e data de nascimento (data ausente → ⚠) |
| `escolar` | 03 | nome e ano de conclusão |
| `declaracao` | 02 | nome e ano ≤ **2022** (`ANO_LIMITE_DECLARACAO`) |
| `residencia` | 11 | CEP igual ao de Seus dados (diferente → ⚠) |
| `nome` | demais | presença do nome (ausente → ⚠) |

Texto com menos de 25 caracteres é ilegível. O texto bruto lido nunca é enviado ao servidor, apenas veredito,
confiança, campos conferidos e alertas.

## Limite medido com fotos reais (21/10/2026)

Fotos de celular de um RG verdadeiro (modelo antigo de MG, frente e verso, fundo verde de segurança, plástico,
verso girado) foram lidas com **25% a 47% de confiança** e texto sem sentido, mesmo com pré-tratamento (canal verde,
contraste, binarização, 4 rotações). Documentos nítidos ficam acima de 90%.

Por isso, com leitura abaixo de `CONFIANCA_MINIMA` (60%) o portal **nunca** afirma que o documento está errado nem que
os dados divergem: mostra "Não conferido" e deixa o candidato enviar outra foto ou seguir para conferência manual.
Conclusão: o OCR no navegador (Tesseract) ajuda com documentos digitais e escaneados, mas **não basta para conferir
fotos reais de documentos de identidade**. Ver alternativas em Pendências.

## Pendências

- **Motor de leitura mais forte, no servidor**: visão computacional/IA (ex.: Claude com visão, Google Cloud Vision,
  Azure Document Intelligence) lê fotos reais de RG, inclusive giradas, e identifica frente/verso. Exige avaliação
  LGPD: o RG traz foto e digital, que são **dados biométricos (sensíveis)**, e o envio a um serviço externo precisa de
  base legal, contrato com o fornecedor e aval do IA CoE/DPO.
- **Frente e verso**: o legado aceita um arquivo por documento; o candidato precisa juntar os dois lados (PDF de 2
  páginas ou uma foto com os dois). Hoje só a 1ª página do PDF é lida.
- **Validação no servidor**: hoje o servidor confia no resultado enviado pelo navegador. Para que a garantia valha
  contra quem manipula a requisição, o BFF precisa refazer o OCR (Tesseract instalado no servidor/Docker).
- **Aviso para a secretaria**: o formulário legado não tem campo para o resultado da conferência; ele precisa ir para
  um relatório ou log consultável.

## WEBP

O candidato pode anexar WEBP sempre que o documento aceita JPG. O navegador converte para JPG (qualidade 92%, até
2400 px no maior lado, fundo branco no lugar de transparência) a mesma imagem usada no OCR, e é o JPG que vai para o
servidor e para o Lyceum. A linha mostra "arquivo.jpg (convertido de WEBP)". O backend continua aceitando só os
formatos do Lyceum: um `.webp` enviado direto à API é recusado (422).

## Assets self-hosted

`npm install` executa `scripts/copy-ocr-assets.mjs`, que copia para `public/ocr/` o worker do tesseract.js, o core WASM
e `por.traineddata.gz`. Nada é baixado de CDN; o engine é carregado sob demanda no primeiro anexo.

## Testes

- Regras e identificação de tipo: `frontend/src/lib/lib.test.ts` (RG no lugar do CPF, conta de luz no lugar da
  declaração, divergências, atenção).
- E2E com OCR real em Chromium: `frontend/e2e/matricula.spec.ts`.
