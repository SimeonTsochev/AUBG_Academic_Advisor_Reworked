import { describe, expect, it } from "vitest";
import { describeFailedAttempt, normalizeFailedCourses, resolveActiveAttempts } from "./retakes";

describe("resolveActiveAttempts", () => {
  it("keeps the latest attempt of each course active", () => {
    const { activeInstanceIds, replacedInstanceIds } = resolveActiveAttempts([
      { instance_id: "first", code: "COS 1020", term: "Fall 2025", status: "COMPLETED" },
      { instance_id: "retake", code: "cos  1020", term: "Spring 2027", status: "PLANNED", is_retake: true },
      { instance_id: "other", code: "MAT 1000", term: "Fall 2025", status: "COMPLETED" },
    ]);
    expect([...activeInstanceIds].sort()).toEqual(["other", "retake"]);
    expect([...replacedInstanceIds]).toEqual(["first"]);
  });

  it("prefers completed over planned attempts in the same term", () => {
    const { activeInstanceIds } = resolveActiveAttempts([
      { instance_id: "completed", code: "ENG 1001", term: "Fall 2026", status: "COMPLETED" },
      { instance_id: "planned", code: "ENG 1001", term: "Fall 2026", status: "PLANNED" },
    ]);
    expect([...activeInstanceIds]).toEqual(["completed"]);
  });

  it("falls back to positional ids when instance ids are missing", () => {
    const { activeInstanceIds, replacedInstanceIds } = resolveActiveAttempts([
      { code: "BUS 1001", term: "Fall 2025" },
      { code: "BUS 1001", term: "Fall 2026" },
    ]);
    expect([...activeInstanceIds]).toEqual(["idx:1"]);
    expect([...replacedInstanceIds]).toEqual(["idx:0"]);
  });
});

describe('failed transcript attempts', () => {
  it('keeps well-formed entries, normalizes codes and grades, and drops junk', () => {
    expect(
      normalizeFailedCourses([
        { code: 'mat  1003', grade: 'f', term: 'Fall 2025' },
        { code: 'BUS 1001', grade: '', term: null },
        { code: 42 },
        null,
      ])
    ).toEqual([
      { code: 'MAT 1003', grade: 'F', term: 'Fall 2025' },
      { code: 'BUS 1001', grade: null, term: null },
    ]);
    expect(normalizeFailedCourses('not an array')).toEqual([]);
  });

  it('explains why a course is in the plan again', () => {
    expect(describeFailedAttempt({ code: 'MAT 1003', grade: 'F', term: 'Fall 2025' })).toBe(
      'Retake: not passed in Fall 2025 (grade F).'
    );
    expect(describeFailedAttempt({ code: 'MAT 1003', grade: null, term: null })).toBe('Retake: not passed.');
  });
});
