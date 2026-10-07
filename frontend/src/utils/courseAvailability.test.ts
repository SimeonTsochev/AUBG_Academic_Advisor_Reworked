import { describe, expect, it } from "vitest";
import { getCourseAvailabilityInfo, scheduleTermsFromCourseMeta } from "./courseAvailability";

const fallOnly = { semester_availability: ["Fall 2026"] };
const scheduleTerms = ["Fall 2026"];

describe("scheduleTermsFromCourseMeta", () => {
  it("collects every term that any course is listed for", () => {
    expect(
      scheduleTermsFromCourseMeta({
        "BUS 4482": { semester_availability: ["Fall 2026"] },
        "COS 1020": { semester_availability: [" Fall 2026 ", "Spring 2027"] },
        "ENG 1001": {},
        "MAT 1000": undefined,
      }).sort()
    ).toEqual(["Fall 2026", "Spring 2027"]);
    expect(scheduleTermsFromCourseMeta(undefined)).toEqual([]);
  });
});

describe("getCourseAvailabilityInfo", () => {
  it("never blocks courses that are not Excel-only", () => {
    const info = getCourseAvailabilityInfo(fallOnly, {
      mode: "plan_add",
      isExcelOnly: false,
      currentTermLabel: "Fall 2026",
      targetTermLabel: "Spring 2027",
      scheduleTerms: ["Spring 2027"],
    });
    expect(info.isSelectionBlocked).toBe(false);
    expect(info.warningLabel).toBeNull();
  });

  it("allows adding an Excel-only course to a term it is listed for", () => {
    const info = getCourseAvailabilityInfo(fallOnly, {
      mode: "plan_add",
      isExcelOnly: true,
      currentTermLabel: "Fall 2026",
      targetTermLabel: "fall  2026",
      scheduleTerms,
    });
    expect(info.isSelectionBlocked).toBe(false);
  });

  it("allows adding an Excel-only course to a future term that has no published schedule", () => {
    // Regression: a single-semester schedule used to block every other term, forever.
    const info = getCourseAvailabilityInfo(fallOnly, {
      mode: "plan_add",
      isExcelOnly: true,
      currentTermLabel: "Fall 2026",
      targetTermLabel: "Fall 2027",
      scheduleTerms,
    });
    expect(info.isSelectionBlocked).toBe(false);
    expect(info.warningLabel).toBeNull();
  });

  it("blocks an Excel-only course in a published term that does not list it", () => {
    const info = getCourseAvailabilityInfo(
      { semester_availability: ["Spring 2027"] },
      {
        mode: "plan_add",
        isExcelOnly: true,
        currentTermLabel: "Fall 2026",
        targetTermLabel: "Fall 2026",
        scheduleTerms,
      }
    );
    expect(info.isSelectionBlocked).toBe(true);
    expect(info.warningLabel).toBe("Not offered in Fall 2026");
  });

  it("treats every term as unknown when no schedule terms are given", () => {
    const info = getCourseAvailabilityInfo(
      { semester_availability: ["Spring 2027"] },
      { mode: "plan_add", isExcelOnly: true, currentTermLabel: "Fall 2026", targetTermLabel: "Fall 2026" }
    );
    expect(info.isSelectionBlocked).toBe(false);
  });

  it("only warns (never blocks) when marking a course completed", () => {
    const info = getCourseAvailabilityInfo(fallOnly, {
      mode: "completed",
      isExcelOnly: true,
      currentTermLabel: "Spring 2026",
      scheduleTerms: ["Fall 2026", "Spring 2026"],
    });
    expect(info.isSelectionBlocked).toBe(false);
    expect(info.warningLabel).toContain("OK if completed earlier");
  });

  it("flags but does not block an in-progress course outside its listed term", () => {
    const info = getCourseAvailabilityInfo(fallOnly, {
      mode: "in_progress",
      isExcelOnly: true,
      currentTermLabel: "Spring 2026",
      scheduleTerms: ["Fall 2026", "Spring 2026"],
    });
    expect(info.unavailableThisTerm).toBe(true);
    expect(info.isSelectionBlocked).toBe(false);
  });
});
