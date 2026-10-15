import { describe, expect, it } from "vitest";
import { describeEditWarning, describeEditWarnings } from "./planWarnings";

describe("describeEditWarning", () => {
  it("explains an add the planner refused because the course is not offered that term", () => {
    expect(
      describeEditWarning({ type: "OVERRIDE_ADD_TERM_UNAVAILABLE", course: "THR 2030", term: "Fall 2026", offered_terms: [] })
    ).toBe("THR 2030 was not added to Fall 2026: it is not on that term's published schedule.");
    expect(
      describeEditWarning({
        type: "OVERRIDE_MOVE_TERM_UNAVAILABLE",
        course: "COS 3060",
        term: "Fall 2026",
        from: "Spring 2027",
        to: "Fall 2026",
        offered_terms: ["Spring 2027"],
      })
    ).toBe("COS 3060 was not moved to Fall 2026: it is offered in Spring 2027.");
  });

  it("explains conflicts and courses the planner moved to make room", () => {
    expect(
      describeEditWarning({ type: "OVERRIDE_CONFLICT", course: "FREE ELECTIVE 3", term: "Fall 2027", instance_id: "x" })
    ).toBe("FREE ELECTIVE 3 was both added and removed in Fall 2027; the removal was kept.");
    expect(
      describeEditWarning({ type: "OVERRIDE_COURSE_RELIEVED", course: "ECO 1001", term: "Spring 2028", from: "Fall 2027" })
    ).toBe("ECO 1001 moved from Fall 2027 to Spring 2028 to make room for your changes.");
  });

  it("ignores warnings that need no action or are shown elsewhere", () => {
    expect(describeEditWarning({ type: "OVERRIDE_REMOVE_NOT_FOUND", course: "COS 2030", term: "Fall 2027" })).toBeNull();
    expect(describeEditWarning({ type: "OVERRIDE_REMOVE_RELOCATED", course: "COS 2030", term: "Fall 2027" })).toBeNull();
    expect(describeEditWarning({ type: "PREREQ_UNMET", course: "EUR 2012", unmet: ["POS 1001 OR EUR 1011"] })).toBeNull();
    expect(describeEditWarning({ type: "TERM_UNAVAILABLE", course: "EUR 2012", term: "Spring 2028" })).toBeNull();
  });
});

describe("describeEditWarnings", () => {
  it("keeps one sentence per distinct problem", () => {
    const warning = { type: "OVERRIDE_ADD_UNKNOWN", course: "ABC 1234", term: "Fall 2027" };
    expect(describeEditWarnings([warning, warning, { type: "FOUNDATION_LATE", course: "ENG 1000" }])).toEqual([
      "ABC 1234 was not added: it is not in the course catalog.",
    ]);
    expect(describeEditWarnings(undefined)).toEqual([]);
  });
});
