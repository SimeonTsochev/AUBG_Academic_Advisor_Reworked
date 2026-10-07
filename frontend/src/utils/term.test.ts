import { describe, expect, it } from "vitest";
import { applyRolloverIfNeeded, isEarlierTerm, previousTermLabel, termToNumber } from "./term";

describe("termToNumber / isEarlierTerm", () => {
  it("orders Spring before Fall within a year and years ascending", () => {
    const ordered = ["Fall 2025", "Spring 2026", "Fall 2026", "Spring 2027"].map(termToNumber);
    expect(ordered).toEqual([...ordered].sort((a, b) => (a ?? 0) - (b ?? 0)));
    expect(isEarlierTerm("Spring 2026", "Fall 2026")).toBe(true);
    expect(isEarlierTerm("Fall 2026", "Spring 2027")).toBe(true);
    expect(isEarlierTerm("Fall 2026", "Fall 2026")).toBe(false);
  });

  it("rejects labels outside the Fall/Spring YYYY format", () => {
    expect(termToNumber("Summer 2026")).toBeNull();
    expect(termToNumber("fall 2026")).toBeNull();
    expect(termToNumber("")).toBeNull();
    expect(isEarlierTerm("Summer 2026", "Fall 2026")).toBe(false);
  });
});

describe("previousTermLabel", () => {
  it("steps back one semester across the year boundary", () => {
    expect(previousTermLabel("Spring 2027")).toBe("Fall 2026");
    expect(previousTermLabel("Fall 2026")).toBe("Spring 2026");
    expect(previousTermLabel("Summer 2026")).toBeNull();
  });
});

describe("applyRolloverIfNeeded", () => {
  const base = {
    completedCourses: ["ENG 1001"],
    inProgressCourses: ["COS 1020", "MAT 1000", "BUS 1001"],
    completedOverrides: {} as Record<string, string>,
    inProgressOverrides: { "COS 1020": "Spring 2026", "MAT 1000": "Fall 2026" } as Record<string, string>,
  };

  it("is a no-op when the rollover already ran for the current term", () => {
    const result = applyRolloverIfNeeded({ ...base, currentTermLabel: "Fall 2026", lastRolloverTermApplied: "Fall 2026" });
    expect(result.changed).toBe(false);
    expect(result.inProgressCourses).toBe(base.inProgressCourses);
  });

  it("promotes in-progress courses from past terms only", () => {
    const result = applyRolloverIfNeeded({ ...base, currentTermLabel: "Fall 2026" });
    expect(result.changed).toBe(true);
    expect(result.completedCourses).toEqual(expect.arrayContaining(["ENG 1001", "COS 1020"]));
    expect(result.completedOverrides).toEqual({ "COS 1020": "Spring 2026" });
    // Current-term course stays in progress; a course without a term override is left alone.
    expect(result.inProgressCourses).toEqual(expect.arrayContaining(["MAT 1000", "BUS 1001"]));
    expect(result.inProgressCourses).not.toContain("COS 1020");
    expect(result.lastRolloverTermApplied).toBe("Fall 2026");
  });

  it("keeps an existing completed-term override", () => {
    const result = applyRolloverIfNeeded({
      ...base,
      completedOverrides: { "COS 1020": "Fall 2025" },
      currentTermLabel: "Fall 2026",
    });
    expect(result.completedOverrides["COS 1020"]).toBe("Fall 2025");
  });
});
