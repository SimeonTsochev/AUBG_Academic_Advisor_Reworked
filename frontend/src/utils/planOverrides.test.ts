import { describe, expect, it } from "vitest";
import type { PlanOverrides, ProgramSnapshotSwappedElective } from "../api";
import {
  fillSlotWithCourse,
  isAddedInstance,
  moveAddedCourse,
  removeChosenElective,
  swapChosenElective,
  withOverrideAdd,
} from "./planOverrides";

const TERM = "Fall 2027";
const SLOT = { instanceId: "slot-x", code: "FREE ELECTIVE 2" };
const empty = (): PlanOverrides => ({ add: [], remove: [], move: [] });

const recordFor = (code: string, instanceId: string): ProgramSnapshotSwappedElective => ({
  termLabel: TERM,
  addedCourseCode: code,
  addedCourseInstanceId: instanceId,
  replacedPlaceholderInstanceId: SLOT.instanceId,
  placeholderCode: SLOT.code,
  placeholderCredits: 3,
});

// The state the backend sees: exactly one removal of the slot and one add of the final course.
const expectSlotHolds = (overrides: PlanOverrides, code: string) => {
  expect(overrides.remove.filter((r) => r.instance_id === SLOT.instanceId)).toHaveLength(1);
  expect(overrides.add.filter((a) => a.instance_id === SLOT.instanceId)).toHaveLength(0);
  expect(overrides.add.map((a) => a.code)).toEqual([code]);
};

describe("elective slot overrides", () => {
  it("fill A, remove A, fill B", () => {
    const withA = fillSlotWithCourse(empty(), TERM, SLOT, { term: TERM, code: "COS 2031", instance_id: "a" });
    expectSlotHolds(withA, "COS 2031");

    // The screen records the generic removal first, then undoes the fill.
    const afterRemove = removeChosenElective(
      { ...withA, remove: [...withA.remove, { term: TERM, code: "COS 2031", instance_id: "a" }] },
      recordFor("COS 2031", "a"),
      "a"
    );
    expect(afterRemove.add).toEqual([]);
    expect(afterRemove.remove).toEqual([]);

    const withB = fillSlotWithCourse(afterRemove, TERM, SLOT, { term: TERM, code: "COS 3031", instance_id: "b" });
    expectSlotHolds(withB, "COS 3031");
  });

  it("swaps A for B in one step", () => {
    const withA = fillSlotWithCourse(empty(), TERM, SLOT, { term: TERM, code: "COS 2031", instance_id: "a" });
    const withB = swapChosenElective(withA, recordFor("COS 2031", "a"), { term: TERM, code: "COS 3031", instance_id: "b" });
    expectSlotHolds(withB, "COS 3031");
    expect(withB.add[0]).toMatchObject({ term: TERM, instance_id: "b" });
  });

  it("swaps A for B and back to A", () => {
    const withA = fillSlotWithCourse(empty(), TERM, SLOT, { term: TERM, code: "COS 2031", instance_id: "a" });
    const withB = swapChosenElective(withA, recordFor("COS 2031", "a"), { term: TERM, code: "COS 3031", instance_id: "b" });
    const backToA = swapChosenElective(withB, recordFor("COS 3031", "b"), { term: TERM, code: "COS 2031", instance_id: "a2" });
    expectSlotHolds(backToA, "COS 2031");
  });

  it("repairs overrides saved by the old screen (slot restored as an add)", () => {
    const legacy: PlanOverrides = {
      ...empty(),
      remove: [{ term: TERM, instance_id: "a" }],
      add: [{ term: TERM, code: SLOT.code, instance_id: SLOT.instanceId }],
    };
    const withB = fillSlotWithCourse(legacy, TERM, SLOT, { term: TERM, code: "COS 3031", instance_id: "b" });
    expectSlotHolds(withB, "COS 3031");
  });

  it("moves a chosen elective by changing its add, so it can swap with a FREE ELECTIVE slot", () => {
    const withA = fillSlotWithCourse(empty(), TERM, SLOT, { term: TERM, code: "COS 2031", instance_id: "a" });
    // A swap: the elective goes to Spring 2028, another slot comes over to TERM via a move override.
    const swapped = moveAddedCourse(
      { ...withA, move: [{ from_term: TERM, to_term: "Spring 2028", code: "COS 2031", instance_id: "a" }] },
      "a",
      "Spring 2028"
    );
    expect(isAddedInstance(swapped, "a")).toBe(true);
    expect(isAddedInstance(swapped, SLOT.instanceId)).toBe(false);
    expect(swapped.add).toEqual([expect.objectContaining({ code: "COS 2031", instance_id: "a", term: "Spring 2028" })]);
    expect(swapped.move).toEqual([]);
    expectSlotHolds(swapped, "COS 2031");

    // Swapping the moved elective for another course keeps one removal of the original slot.
    const moved = recordFor("COS 2031", "a");
    const withB = swapChosenElective(swapped, { ...moved, termLabel: "Spring 2028" }, { term: TERM, code: "COS 3031", instance_id: "b" });
    expectSlotHolds(withB, "COS 3031");
    expect(withB.add[0]).toMatchObject({ term: "Spring 2028", instance_id: "b" });
  });

  it("keeps a GenEd category from an earlier add of the same course", () => {
    const first = withOverrideAdd(empty(), { term: TERM, code: "FAR 1009", instance_id: "f1", gen_ed_category: "Aesthetic Expression" });
    const second = withOverrideAdd(first, { term: "Spring 2028", code: "FAR 1009", instance_id: "f2" });
    expect(second.add).toEqual([
      { term: "Spring 2028", code: "FAR 1009", instance_id: "f2", gen_ed_category: "Aesthetic Expression", is_retake: undefined },
    ]);
  });
});
