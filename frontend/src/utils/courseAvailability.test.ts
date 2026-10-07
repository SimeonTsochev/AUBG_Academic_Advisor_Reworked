import { describe, expect, it } from "vitest";
import { getCourseAvailabilityInfo } from "./courseAvailability";

const fallOnly = { semester_availability: ["Fall 2026"] };

describe("getCourseAvailabilityInfo", () => {
  it("never blocks courses that are not Excel-only", () => {
    const info = getCourseAvailabilityInfo(fallOnly, {
      mode: "plan_add",
      isExcelOnly: false,
      currentTermLabel: "Fall 2026",
      targetTermLabel: "Spring 2027",
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
    });
    expect(info.isSelectionBlocked).toBe(false);
  });

  it("only warns (never blocks) when marking a course completed", () => {
    const info = getCourseAvailabilityInfo(fallOnly, {
      mode: "completed",
      isExcelOnly: true,
      currentTermLabel: "Spring 2026",
    });
    expect(info.isSelectionBlocked).toBe(false);
    expect(info.warningLabel).toContain("OK if completed earlier");
  });

  it("flags but does not block an in-progress course outside its listed term", () => {
    const info = getCourseAvailabilityInfo(fallOnly, {
      mode: "in_progress",
      isExcelOnly: true,
      currentTermLabel: "Spring 2026",
    });
    expect(info.unavailableThisTerm).toBe(true);
    expect(info.isSelectionBlocked).toBe(false);
  });
});
