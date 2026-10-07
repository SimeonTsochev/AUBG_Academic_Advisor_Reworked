import type { PlanOverrideAdd, PlanOverrides, ProgramSnapshotSwappedElective } from "../api";

/*
 * Pure edits on the plan overrides that /plan/generate applies (removes, then moves, then adds).
 *
 * A FREE ELECTIVE slot is identified by its instance id. Putting a course in a slot removes that
 * id; taking the course out again must *undo* that removal. Re-adding the slot under the same id
 * (what the screen used to do) breaks the next fill: the backend removes the id and then adds it
 * straight back, so the slot never disappears and the new elective is rolled back.
 */

export interface ElectiveSlot {
  instanceId: string;
  code: string;
}

const normalizeCode = (value: string | null | undefined) =>
  (value ?? "").replace(/\s+/g, " ").trim().toUpperCase();

export function withOverrideAdd(overrides: PlanOverrides, entry: PlanOverrideAdd): PlanOverrides {
  const isRetake = entry.is_retake === true;
  const existing = overrides.add.find((a) => a.code === entry.code && a.is_retake !== true);
  const kept = isRetake
    ? overrides.add.filter((a) => a.instance_id !== entry.instance_id)
    : overrides.add.filter((a) => !(a.code === entry.code && a.is_retake !== true));
  return {
    ...overrides,
    add: [
      ...kept,
      {
        term: entry.term,
        code: entry.code,
        instance_id: entry.instance_id,
        gen_ed_category: entry.gen_ed_category ?? existing?.gen_ed_category ?? undefined,
        is_retake: isRetake || undefined,
      },
    ],
  };
}

export function withOverrideRemove(
  overrides: PlanOverrides,
  term: string | null,
  instanceId?: string | null,
  code?: string
): PlanOverrides {
  const exists = overrides.remove.some(
    (r) =>
      (r.term ?? null) === term &&
      (instanceId ? r.instance_id === instanceId : !r.instance_id && r.code === code)
  );
  if (exists) return overrides;
  return { ...overrides, remove: [...overrides.remove, { term, code, instance_id: instanceId ?? undefined }] };
}

/** Put `course` into a FREE ELECTIVE slot of `term`. */
export function fillSlotWithCourse(
  overrides: PlanOverrides,
  term: string,
  slot: ElectiveSlot,
  course: PlanOverrideAdd
): PlanOverrides {
  // Drop any add that would bring the slot back (left behind by older versions of the screen).
  const withoutSlotRestore = { ...overrides, add: overrides.add.filter((a) => a.instance_id !== slot.instanceId) };
  return withOverrideAdd(withOverrideRemove(withoutSlotRestore, term, slot.instanceId, slot.code), course);
}

const isChosenElectiveAdd = (record: ProgramSnapshotSwappedElective) => (a: PlanOverrideAdd) =>
  a.instance_id === record.addedCourseInstanceId ||
  (a.term === record.termLabel && normalizeCode(a.code) === normalizeCode(record.addedCourseCode));

/** Take a chosen elective out of its slot; the slot comes back from the generated plan. */
export function removeChosenElective(
  overrides: PlanOverrides,
  record: ProgramSnapshotSwappedElective,
  electiveInstanceId?: string | null
): PlanOverrides {
  const isElectiveAdd = isChosenElectiveAdd(record);
  const removedIds = new Set(
    [record.replacedPlaceholderInstanceId, record.addedCourseInstanceId, electiveInstanceId].filter(Boolean)
  );
  return {
    ...overrides,
    add: overrides.add.filter((a) => !isElectiveAdd(a) && a.instance_id !== record.replacedPlaceholderInstanceId),
    remove: overrides.remove.filter((r) =>
      r.instance_id
        ? !removedIds.has(r.instance_id)
        : !((r.term ?? null) === record.termLabel && r.code === record.placeholderCode)
    ),
  };
}

/** Replace a chosen elective with another course in the same slot, in one step. */
export function swapChosenElective(
  overrides: PlanOverrides,
  record: ProgramSnapshotSwappedElective,
  course: PlanOverrideAdd
): PlanOverrides {
  const isElectiveAdd = isChosenElectiveAdd(record);
  const withoutOldElective = {
    ...overrides,
    add: overrides.add.filter((a) => !isElectiveAdd(a) && a.instance_id !== record.replacedPlaceholderInstanceId),
  };
  return withOverrideAdd(
    withOverrideRemove(withoutOldElective, record.termLabel, record.replacedPlaceholderInstanceId, record.placeholderCode),
    { ...course, term: record.termLabel }
  );
}
