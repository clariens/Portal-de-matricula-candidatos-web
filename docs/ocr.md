# OCR dos documentos

O OCR roda **no navegador** do candidato, com tesseract.js 5 (idioma `por`) e pdf.js 3.11 (o PDF é lido pela 1ª página).
O resultado é informativo: ajuda o candidato a corrigir o envio na hora, mas a conferência oficial continua com a secretaria.

## Assets self-hosted
`npm install` executa `scripts/copy-ocr-assets.mjs`, que copia para `public/ocr/`:
- `worker.min.js` (tesseract.js)
- `core/tesseract-core*.{js,wasm}` (tesseract.js-core, com e sem SIMD/LSTM)
- `lang/por.traineddata.gz` (`@tesseract.js-data/por`, modelo `4.0.0_best_int`)

Nada é baixado de CDN. O engine (`lib/ocr/engine.ts`) é carregado sob demanda no primeiro upload.

## Fluxo
1. O candidato escolhe ou arrasta o arquivo e o front valida extensão e tamanho.
2. `fileToCanvas` converte para canvas (no máximo 2400 px) e gera a miniatura.
3. `reconhecer` extrai o texto e a confiança, com barra de progresso.
4. `analisar(texto, regra, dados da etapa 1)` devolve o veredito.
5. **ok**: envia ao BFF automaticamente. **atenção/divergente/ilegível/erro**: mostra os alertas e pede
   "Enviar para conferência manual" ou "Escolher outro arquivo".
6. O BFF recebe o arquivo e `{veredito, confianca, campos, alertas}`. O servidor marca o documento como `em_conferencia` quando o veredito não é ok.

## Regras (`lib/ocr/analisar.ts`)
| Regra | Documentos | Confere |
|---|---|---|
| `cpf` | 05 CPF | CPF válido no texto igual ao da etapa 1 |
| `id` | 04 Identidade | nome (≥ 60% dos tokens) e data de nascimento |
| `escolar` | 03 Histórico | nome e ano de conclusão |
| `declaracao` | 02 Declaração EM | nome e ano ≤ **2022** (`ANO_LIMITE_DECLARACAO`) |
| `residencia` | 11 Comprovante | CEP igual ao da etapa 1 |
| `foto` | 01 Foto 3x4 | não lê texto |
| `nome` | demais | presença do nome |

Texto com menos de 25 caracteres resulta em **ilegível**.

## Testes
- Unitários das regras: `frontend/src/lib/lib.test.ts`.
- E2E com OCR real em Chromium (imagens geradas no teste): `frontend/e2e/matricula.spec.ts`.
