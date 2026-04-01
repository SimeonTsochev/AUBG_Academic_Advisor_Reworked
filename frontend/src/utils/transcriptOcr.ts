import type { TranscriptImportLineInput } from "../api";

const normalizeOcrLine = (value: string) => value.replace(/\s+/g, " ").trim();

export async function extractTranscriptLinesFromImage(
  file: File,
): Promise<TranscriptImportLineInput[]> {
  const { recognize } = await import("tesseract.js");
  const result = await recognize(file, "eng");
  const rawLines = Array.isArray(result.data?.lines)
    ? result.data.lines.map((line) => ({
        text: normalizeOcrLine(String(line.text ?? "")),
        page_number: 1,
        confidence:
          typeof line.confidence === "number" && Number.isFinite(line.confidence)
            ? line.confidence / 100
            : 1,
      }))
    : [];

  const normalizedLines = rawLines.filter((line) => line.text.length > 0);
  if (normalizedLines.length > 0) {
    return normalizedLines;
  }

  return String(result.data?.text ?? "")
    .split(/\r?\n/)
    .map((line) => normalizeOcrLine(line))
    .filter((line) => line.length > 0)
    .map((text) => ({
      text,
      page_number: 1,
      confidence: 1,
    }));
}
