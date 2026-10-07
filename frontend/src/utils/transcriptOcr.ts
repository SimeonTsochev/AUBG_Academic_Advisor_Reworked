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
