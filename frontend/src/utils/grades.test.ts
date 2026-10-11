import { describe, expect, it } from "vitest";
import {
  formatGpa,
  gradesFromTranscript,
  loadGrades,
  normalizeGrades,
  saveGrades,
  toGradeEntries,
  type GradeStorage,
} from "./grades";

function memoryStorage(): GradeStorage & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => void data.set(key, value),
  };
}

const throwingStorage: GradeStorage = {
  getItem: () => { throw new Error("blocked"); },
  setItem: () => { throw new Error("blocked"); },
};

describe("grade storage", () => {
  it("follows the plan to its new token and forgets the old one", () => {
    const storage = memoryStorage();
    saveGrades("first", { "STA 1005": { grade: "A", term: "Fall 2025" } }, null, storage, 1);
    saveGrades("second", loadGrades("first", storage), "first", storage, 2);
    expect(loadGrades("first", storage)).toEqual({});
    expect(loadGrades("second", storage)).toEqual({ "STA 1005": { grade: "A", term: "Fall 2025" } });
  });

  it("keeps only the most recent plans", () => {
    const storage = memoryStorage();
    for (let i = 0; i < 25; i += 1) saveGrades(`t${i}`, { "STA 1005": { grade: "A" } }, null, storage, i);
    expect(loadGrades("t0", storage)).toEqual({});
    expect(loadGrades("t24", storage)).toEqual({ "STA 1005": { grade: "A", term: null } });
  });

  it("survives missing or blocked storage", () => {
    expect(() => saveGrades("t", { "STA 1005": { grade: "A" } }, null, throwingStorage)).not.toThrow();
    expect(loadGrades("t", throwingStorage)).toEqual({});
    expect(loadGrades("t", null)).toEqual({});
    expect(loadGrades(null, memoryStorage())).toEqual({});
  });
});

describe("grade helpers", () => {
  it("takes grades of completed and failed transcript rows only", () => {
    const grades = gradesFromTranscript(
      [
        { matchedCode: "sta1005", status: "completed", grade: "b+", term: "Fall 2025" },
        { matchedCode: "ENG 1002", status: "failed", grade: "F", term: "Spring 2026" },
        { matchedCode: "ECO 1001", status: "in_progress", grade: null, term: "Fall 2026" },
        { matchedCode: null, status: "completed", grade: "A", term: null },
      ],
      (code) => (code === "sta1005" ? "STA 1005" : code),
    );
    expect(grades).toEqual({
      "STA 1005": { grade: "B+", term: "Fall 2025" },
      "ENG 1002": { grade: "F", term: "Spring 2026" },
    });
    expect(toGradeEntries(grades)).toContainEqual({ code: "ENG 1002", grade: "F", term: "Spring 2026" });
  });

  it("drops malformed stored entries", () => {
    expect(normalizeGrades({ A: { grade: " a- " }, B: { grade: "" }, C: "A", D: null })).toEqual({
      A: { grade: "A-", term: null },
    });
    expect(normalizeGrades([1, 2])).toEqual({});
  });

  it("formats GPA with three decimals", () => {
    expect(formatGpa(3.5)).toBe("3.500");
    expect(formatGpa(null)).toBe("–");
  });
});
