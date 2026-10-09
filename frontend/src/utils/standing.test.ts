import { describe, expect, it } from "vitest";
import { ordinal, semesterOfStudy, standingRequirement } from "./standing";

describe("standingRequirement", () => {
  it("maps standings to the first semester they start in", () => {
    expect(standingRequirement("ECO 2001", "Sophomore standing")).toEqual({ minSemester: 3, reason: "sophomore standing" });
    expect(standingRequirement("ECO 2001", "ECO 1001 and junior standing")).toEqual({ minSemester: 5, reason: "junior standing" });
    expect(standingRequirement("ECO 2001", "Senior standing.")).toEqual({ minSemester: 7, reason: "senior standing" });
  });

  it("has no restriction for a lower-level course without a standing rule", () => {
    expect(standingRequirement("COS 1020", "MAT 1000")).toEqual({ minSemester: 1, reason: null });
    expect(standingRequirement("COS 1020", undefined)).toEqual({ minSemester: 1, reason: null });
  });

  it("uses course level and declared major", () => {
    expect(standingRequirement("BUS 3001", "")).toEqual({ minSemester: 3, reason: "sophomore standing (3000-level course)" });
    expect(standingRequirement("BUS 4001", "")).toEqual({ minSemester: 5, reason: "junior standing (4000-level course)" });
    expect(standingRequirement("BUS 2001", "declared major")).toEqual({ minSemester: 3, reason: "sophomore standing (declared major)" });
  });

  it("takes the strictest rule", () => {
    expect(standingRequirement("BUS 4001", "senior standing")).toEqual({ minSemester: 7, reason: "senior standing" });
    expect(standingRequirement("BUS 3001", "junior standing")).toEqual({ minSemester: 5, reason: "junior standing" });
  });
});

describe("semesterOfStudy / ordinal", () => {
  it("counts the start term as the 1st semester", () => {
    expect(semesterOfStudy(10, 10)).toBe(1);
    expect(semesterOfStudy(14, 10)).toBe(5);
    expect([1, 2, 3, 4, 11, 12, 13, 21].map(ordinal)).toEqual(["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st"]);
  });
});
