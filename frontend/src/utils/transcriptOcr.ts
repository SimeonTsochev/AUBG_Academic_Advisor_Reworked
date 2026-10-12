import type { TranscriptImportLineInput } from "../api";

const normalizeOcrLine = (value: string) => value.replace(/\s+/g, " ").trim();

// Structural subset of tesseract.js's Page, so the parsing can be tested without running OCR.
type OcrLine = { text?: string | null; confidence?: number | null };
export type OcrPage = {
  text?: string | null;
  blocks?: { paragraphs?: { lines?: OcrLine[] | null }[] | null }[] | null;
};

export function transcriptLinesFromOcrPage(
  page: OcrPage | null | undefined,
): TranscriptImportLineInput[] {
  const ocrLines = (page?.blocks ?? [])
    .flatMap((block) => block?.paragraphs ?? [])
    .flatMap((paragraph) => paragraph?.lines ?? []);
  const normalizedLines = ocrLines
    .map((line) => ({
      text: normalizeOcrLine(String(line?.text ?? "")),
      page_number: 1,
      confidence:
        typeof line?.confidence === "number" && Number.isFinite(line.confidence)
          ? line.confidence / 100
          : 1,
    }))
    .filter((line) => line.text.length > 0);
  if (normalizedLines.length > 0) {
    return normalizedLines;
  }

  return String(page?.text ?? "")
    .split(/\r?\n/)
    .map((line) => normalizeOcrLine(line))
    .filter((line) => line.length > 0)
    .map((text) => ({
      text,
      page_number: 1,
      confidence: 1,
    }));
}

export async function extractTranscriptLinesFromImage(
  file: File,
): Promise<TranscriptImportLineInput[]> {
  const { createWorker } = await import("tesseract.js");
  const worker = await createWorker("eng");
  try {
    // tesseract.js v6 only returns per-line text and confidence when block output is requested;
    // `data.lines` no longer exists, so every line used to fall back to confidence 1.
    const result = await worker.recognize(file, {}, { text: true, blocks: true });
    return transcriptLinesFromOcrPage(result.data);
  } finally {
    await worker.terminate();
  }
}

// 4x the PDF's 72 dpi (about 290 dpi, near tesseract's preferred 300). At 2x the portal transcript's
// small table text lost half its rows and misread "2026" as "2028"; at 4x every row read correctly.
const OCR_RENDER_SCALE = 4;
// Keeps a page's canvas (4 bytes a pixel) within phone memory: a letter page at 4x is 2448x3168.
const OCR_MAX_CANVAS_SIDE = 4000;

/** Render scale for OCR of a page `width` x `height` PDF units: 4x, reduced for very large pages. */
export function ocrRenderScale(width: number, height: number): number {
  const longestSide = Math.max(width, height);
  if (!Number.isFinite(longestSide) || longestSide <= 0) return OCR_RENDER_SCALE;
  return Math.min(OCR_RENDER_SCALE, OCR_MAX_CANVAS_SIDE / longestSide);
}

// PDFs printed from a browser ("Microsoft Print to PDF") draw text as vector shapes, so the backend
// finds no text layer. Render each page and OCR it in the browser instead.
export async function extractTranscriptLinesFromPdf(
  file: File,
): Promise<TranscriptImportLineInput[]> {
  const [pdfjs, { default: workerUrl }, { createWorker }] = await Promise.all([
    import("pdfjs-dist"),
    import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
    import("tesseract.js"),
  ]);
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

  const pdf = await pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) }).promise;
  const worker = await createWorker("eng");
  try {
    const lines: TranscriptImportLineInput[] = [];
    for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
      const page = await pdf.getPage(pageNumber);
      const unscaled = page.getViewport({ scale: 1 });
      const viewport = page.getViewport({ scale: ocrRenderScale(unscaled.width, unscaled.height) });
      const canvas = document.createElement("canvas");
      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);
      await page.render({ canvas, viewport }).promise;
      const result = await worker.recognize(canvas, {}, { text: true, blocks: true });
      lines.push(
        ...transcriptLinesFromOcrPage(result.data).map((line) => ({ ...line, page_number: pageNumber })),
      );
      // Release the page's pixels before rendering the next one.
      canvas.width = 0;
      canvas.height = 0;
      page.cleanup();
    }
    return lines;
  } finally {
    await worker.terminate();
    await pdf.destroy();
  }
}
