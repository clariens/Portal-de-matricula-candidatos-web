// Execução do OCR no navegador: tesseract.js + pdf.js, com assets servidos de /ocr (sem CDN).
// O arquivo do candidato não sai do dispositivo durante a leitura.
import * as pdfjsLib from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.js?url";
import { createWorker, type Worker } from "tesseract.js";
import { ehPdf } from "../imagem";

export { canvasParaJpeg, ehWebp } from "../imagem";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

export interface OcrProgresso { etapa: string; progresso: number }
let worker: Promise<Worker> | null = null;
let onProgress: ((p: OcrProgresso) => void) | null = null;

function getWorker() {
  if (!worker) {
    const base = new URL("/ocr/", location.origin).href;
    worker = createWorker("por", 1, {
      workerPath: base + "worker.min.js",
      corePath: base + "core",
      langPath: base + "lang",
      workerBlobURL: false,
      logger: (m) => {
        if (!onProgress) return;
        const lendo = m.status === "recognizing text";
        onProgress({ etapa: lendo ? "Lendo o documento" : "Carregando leitor de texto", progresso: lendo ? m.progress : 0 });
      },
    }).catch((e) => {
      worker = null;
      throw e;
    });
  }
  return worker;
}

/** Converte imagem ou 1ª página de PDF em canvas (limitado a 2400 px no maior lado). */
export async function fileToCanvas(file: File): Promise<HTMLCanvasElement> {
  const cv = document.createElement("canvas");
  if (ehPdf(file)) {
    // isEvalSupported:false mitiga CVE-2024-4367 (execução de JS via fonte maliciosa no pdf.js 3.x)
    const pdf = await pdfjsLib.getDocument({ data: await file.arrayBuffer(), isEvalSupported: false }).promise;
    const page = await pdf.getPage(1);
    const vp = page.getViewport({ scale: 2.2 });
    cv.width = vp.width;
    cv.height = vp.height;
    await page.render({ canvasContext: cv.getContext("2d")!, viewport: vp }).promise;
    return cv;
  }
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((res, rej) => {
      const i = new Image();
      i.onload = () => res(i);
      i.onerror = rej;
      i.src = url;
    });
    const k = Math.min(1, 2400 / Math.max(img.width, img.height));
    cv.width = img.width * k;
    cv.height = img.height * k;
    cv.getContext("2d")!.drawImage(img, 0, 0, cv.width, cv.height);
    return cv;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function reconhecer(cv: HTMLCanvasElement, progresso: (p: OcrProgresso) => void) {
  onProgress = progresso;
  try {
    progresso({ etapa: "Carregando leitor de texto", progresso: 0 });
    const w = await getWorker();
    const { data } = await w.recognize(cv);
    return { texto: data.text, confianca: Math.round(data.confidence) };
  } finally {
    onProgress = null;
  }
}
