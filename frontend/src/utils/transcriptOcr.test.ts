import { describe, expect, it } from "vitest";
import { ocrRenderScale, transcriptLinesFromOcrPage } from "./transcriptOcr";

describe("ocrRenderScale", () => {
  it("renders letter and A4 pages at 4x", () => {
    expect(ocrRenderScale(612, 792)).toBe(4);
    expect(ocrRenderScale(595, 842)).toBe(4);
  });

  it("scales very large pages down so the canvas stays within 4000 px", () => {
    const scale = ocrRenderScale(1224, 1584);
    expect(scale).toBeLessThan(4);
    expect(Math.ceil(1584 * scale)).toBeLessThanOrEqual(4000);
  });

  it("falls back to 4x for a page with no size", () => {
    expect(ocrRenderScale(0, 0)).toBe(4);
    expect(ocrRenderScale(Number.NaN, 792)).toBe(4);
  });
});

describe("transcriptLinesFromOcrPage", () => {
  it("reads lines and their confidence from tesseract v6 blocks", () => {
    const lines = transcriptLinesFromOcrPage({
      text: "ignored when blocks are present",
      blocks: [
        {
          paragraphs: [
            { lines: [{ text: "  COS 1020   Intro to Programming ", confidence: 91.5 }, { text: "   ", confidence: 99 }] },
            { lines: [{ text: "MAT 1000 Calculus", confidence: 42 }] },
          ],
        },
      ],
    });
    expect(lines).toEqual([
      { text: "COS 1020 Intro to Programming", page_number: 1, confidence: 0.915 },
      { text: "MAT 1000 Calculus", page_number: 1, confidence: 0.42 },
    ]);
  });

  it("falls back to plain text with full confidence when no blocks are returned", () => {
    expect(transcriptLinesFromOcrPage({ text: "ENG 1001\r\n\r\n  BUS 1001  ", blocks: null })).toEqual([
      { text: "ENG 1001", page_number: 1, confidence: 1 },
      { text: "BUS 1001", page_number: 1, confidence: 1 },
    ]);
  });

  it("returns nothing for an empty result", () => {
    expect(transcriptLinesFromOcrPage(null)).toEqual([]);
    expect(transcriptLinesFromOcrPage({ text: "", blocks: [] })).toEqual([]);
  });
});
