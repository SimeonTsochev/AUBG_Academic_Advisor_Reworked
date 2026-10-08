import { describe, expect, it } from "vitest";
import { describeCourseReason } from "./courseReasons";

describe("describeCourseReason", () => {
  it("lists every requirement and the courses it unlocks", () => {
    expect(
      describeCourseReason({
        satisfies: ["Major: Computer Science"],
        requirements: [
          { program: "Computer Science", program_type: "major", kind: "required", label: "Computer Science major: required course" },
          { program: null, program_type: "gened", kind: "gened", label: "GenEd: Quantitative Reasoning" },
        ],
        unlocks: ["COS 2021", "COS 3015"],
      })
    ).toBe(
      "Computer Science major: required course; GenEd: Quantitative Reasoning; Prerequisite for COS 2021, COS 3015"
    );
  });

  it("explains prerequisite-only courses", () => {
    expect(describeCourseReason({ satisfies: [], requirements: [], unlocks: ["BUS 3000"] })).toBe(
      "Prerequisite for BUS 3000"
    );
  });

  it("falls back to the coarse labels from older responses", () => {
    expect(describeCourseReason({ satisfies: ["GenEd: Aesthetic Expression"] })).toBe("GenEd: Aesthetic Expression");
    expect(describeCourseReason({ satisfies: [] })).toBeUndefined();
  });
});
