import { describe, expect, it } from "vitest";
import { describeDeclaredPrograms, mergeDeclaredPrograms } from "./declaredPrograms";

const available = {
  majors: ["Computer Science", "Economics", "Business Administration"],
  minors: ["Economics", "Finance", "Psychology", "Computer Science"],
};

describe("mergeDeclaredPrograms", () => {
  it("selects the declared programs when nothing is chosen yet", () => {
    expect(
      mergeDeclaredPrograms({ majors: [], minors: [] }, { majors: ["Computer Science"], minors: ["Economics"] }, available, 2),
    ).toEqual({ majors: ["Computer Science"], minors: ["Economics"] });
  });

  it("keeps the student's own choices and respects the limit", () => {
    expect(
      mergeDeclaredPrograms(
        { majors: ["Economics", "Business Administration"], minors: ["Finance"] },
        { majors: ["Computer Science"], minors: ["Psychology"] },
        available,
        2,
      ),
    ).toEqual({ majors: ["Economics", "Business Administration"], minors: ["Finance", "Psychology"] });
  });

  it("moves a program chosen as a minor to the majors when it is a declared major", () => {
    expect(
      mergeDeclaredPrograms({ majors: [], minors: ["Economics"] }, { majors: ["Economics"], minors: [] }, available, 2),
    ).toEqual({ majors: ["Economics"], minors: [] });
  });

  it("returns null when the transcript adds nothing or names unknown programs", () => {
    expect(mergeDeclaredPrograms({ majors: [], minors: [] }, { majors: [], minors: [] }, available, 2)).toBeNull();
    expect(mergeDeclaredPrograms({ majors: [], minors: [] }, undefined, available, 2)).toBeNull();
    expect(mergeDeclaredPrograms({ majors: [], minors: [] }, { majors: ["Astrology"], minors: [] }, available, 2)).toBeNull();
    expect(
      mergeDeclaredPrograms({ majors: ["Economics"], minors: [] }, { majors: ["Economics"], minors: [] }, available, 2),
    ).toBeNull();
  });
});

describe("describeDeclaredPrograms", () => {
  it("names the majors and minors", () => {
    expect(describeDeclaredPrograms({ majors: ["Computer Science"], minors: ["Economics", "Finance"] })).toBe(
      "Major: Computer Science · Minors: Economics, Finance",
    );
    expect(describeDeclaredPrograms({ majors: [], minors: ["Finance"] })).toBe("Minor: Finance");
  });
});
