import { describe, expect, it } from "vitest";
import { transcriptLinesFromOcrPage } from "./transcriptOcr";

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
