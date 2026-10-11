// Full-time status takes at least 12 credits a semester (AY 2026-27 catalog p.57).
export const MIN_CREDITS_PER_TERM = 12;
// What the planner fills a semester to with free electives (backend PLANNING_MIN_CREDITS_PER_TERM).
export const PLANNING_MIN_CREDITS = 14;
// The catalog's standard maximum course load (AY 2026-27 catalog p.65). The planner never plans an
// overload; a student may add courses up to `academic_record.max_load` (19 with a GPA of 3.300+).
export const STANDARD_MAX_CREDITS = 17;
