// Copia worker, core WASM e dados de idioma do Tesseract para public/ocr,
// para o OCR rodar sem CDN (o arquivo do documento nunca sai do navegador).
import { cpSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const nm = join(root, "node_modules");
const out = join(root, "public", "ocr");
mkdirSync(join(out, "core"), { recursive: true });
mkdirSync(join(out, "lang"), { recursive: true });

const copy = (from, to) => {
  if (!existsSync(from)) {
    console.warn(`[ocr] não encontrado: ${from}`);
    return;
  }
  cpSync(from, to);
};

copy(join(nm, "tesseract.js", "dist", "worker.min.js"), join(out, "worker.min.js"));

const core = join(nm, "tesseract.js-core");
if (existsSync(core)) {
  for (const f of readdirSync(core)) {
    if (/^tesseract-core.*\.(js|wasm)$/.test(f)) copy(join(core, f), join(out, "core", f));
  }
}

copy(join(nm, "@tesseract.js-data", "por", "4.0.0_best_int", "por.traineddata.gz"), join(out, "lang", "por.traineddata.gz"));
console.log("[ocr] assets copiados para public/ocr");
