import { describe, expect, it } from "vitest";
import { resolveActiveAttempts } from "./retakes";

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
