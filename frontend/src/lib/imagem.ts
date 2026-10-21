// Utilitários de imagem leves (sem pdf.js/tesseract): miniatura e conversão WEBP → JPG.

export const ehPdf = (f: File) => f.type === "application/pdf" || /\.pdf$/i.test(f.name);
export const ehWebp = (f: File) => f.type === "image/webp" || /\.webp$/i.test(f.name);

/** Carrega uma imagem num canvas, limitada a `maxPx` no maior lado. */
export async function imagemParaCanvas(file: File, maxPx = 2400): Promise<HTMLCanvasElement> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((ok, falha) => {
      const i = new Image();
      i.onload = () => ok(i);
      i.onerror = falha;
      i.src = url;
    });
    const k = Math.min(1, maxPx / Math.max(img.width, img.height));
    const cv = document.createElement("canvas");
    cv.width = img.width * k;
    cv.height = img.height * k;
    cv.getContext("2d")!.drawImage(img, 0, 0, cv.width, cv.height);
    return cv;
  } finally {
    URL.revokeObjectURL(url);
  }
}

/**
 * Converte o canvas para JPG (qualidade 92%, fundo branco no lugar de transparência).
 * Usado no WEBP: o candidato pode enviar WEBP, mas o legado/Lyceum só aceita JPEG, JPG, PDF e PNG.
 */
export async function canvasParaJpeg(cv: HTMLCanvasElement, nomeOriginal: string): Promise<File> {
  const fundo = document.createElement("canvas");
  fundo.width = cv.width;
  fundo.height = cv.height;
  const g = fundo.getContext("2d")!;
  g.fillStyle = "#fff";
  g.fillRect(0, 0, fundo.width, fundo.height);
  g.drawImage(cv, 0, 0);
  const blob = await new Promise<Blob>((ok, falha) =>
    fundo.toBlob((b) => (b ? ok(b) : falha(new Error("conversão para JPG falhou"))), "image/jpeg", 0.92),
  );
  return new File([blob], nomeOriginal.replace(/\.webp$/i, "") + ".jpg", { type: "image/jpeg" });
}

/** Miniatura para a linha do documento (PDF não tem miniatura neste modo). */
export async function miniatura(file: File): Promise<string | undefined> {
  if (ehPdf(file)) return undefined;
  const cv = await imagemParaCanvas(file, 160);
  return cv.toDataURL("image/jpeg", 0.6);
}
