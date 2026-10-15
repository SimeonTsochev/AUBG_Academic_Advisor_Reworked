"""Generate plans for realistic students on the shipped catalog and audit them independently.

Each sweep test checks one invariant for every major at several stages (fresh student, and the same
student after completing the first N terms of their fresh plan), plus a few double-major combinations.
The targeted tests below reproduce individual bugs found on the real catalog.
"""
import os
import re
import sys
import unittest
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Set
from unittest.mock import patch

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase, load_real_excel_index  # noqa: E402

import degree_engine  # noqa: E402
import excel_course_catalog  # noqa: E402
from catalog_cache import getCatalogCache  # noqa: E402
from catalog_options import options_offered  # noqa: E402
from degree_engine import (  # noqa: E402
    _course_credits,
    _course_prereq_expr,
    _is_free_elective,
    _prereq_expr_satisfied,
    build_requirement_slots,
    generate_plan,
    select_courses_for_slots,
)

START_SEASON, START_YEAR = "Spring", 2027
MAX_CREDITS = 16
STAGES = (0, 2, 5)
COMBINATIONS = (
    (["Business Administration", "Economics"], ["Mathematics"]),
    (["Computer Science", "Mathematics"], ["Physics"]),
    (["Psychology"], ["Economics", "Philosophy"]),
)
STANDING_CREDITS = {"sophomore standing": 27, "junior standing": 57, "senior standing": 87}
COMPLETED_CREDITS_RE = re.compile(r"completion of (\d+) credits", re.IGNORECASE)


@dataclass
class Scenario:
    label: str
    majors: List[str]
    minors: List[str]
    completed: Set[str]
    stage: int
    result: Dict = field(default_factory=dict)


def _required_options(catalog: Dict, majors: List[str]) -> Dict[str, List[str]]:
    """The first real choice for each required major option (French for the European Studies language)."""
    chosen = {}
    for major in majors:
        options = options_offered(catalog, "major", major)
        if options is not None and options.required:
            chosen[major] = [next(choice.name for choice in options.choices.values() if choice.blocks)]
    return chosen


def _plan(catalog: Dict, majors: List[str], minors: List[str], completed: Set[str], **kwargs) -> Dict:
    return generate_plan(
        catalog=catalog,
        majors=majors,
        minors=minors,
        completed_courses=set(completed),
        max_credits_per_semester=MAX_CREDITS,
        start_term_season=START_SEASON,
        start_term_year=START_YEAR,
        program_options=_required_options(catalog, majors),
        **kwargs,
    )


def _real_courses(term: Dict) -> List[Dict]:
    return [c for c in term.get("courses", []) if not _is_free_elective(c["code"])]


def _completed_after(fresh: Dict, terms: int) -> Set[str]:
    return {c["code"] for term in fresh["semester_plan"][:terms] for c in _real_courses(term)}


def _min_credits_stated_in_catalog(catalog: Dict, code: str) -> int:
    text = (catalog.get("course_meta", {}).get(code, {}).get("prereq_text") or "").lower()
    required = max([credits for phrase, credits in STANDING_CREDITS.items() if phrase in text], default=0)
    for match in COMPLETED_CREDITS_RE.finditer(text):
        required = max(required, int(match.group(1)))
    return required


def _term_of(result: Dict, code: str) -> str | None:
    for term in result["semester_plan"]:
        if any(c["code"] == code for c in term["courses"]):
            return term["term"]
    return None


class RealCatalogScenarioTests(IsolatedTestCase):
    excel_index = "real"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        clock = patch.object(degree_engine, "_current_start_term", return_value=("Fall", 2026))
        clock.start()
        cls.addClassCleanup(clock.stop)
        cls.addClassCleanup(
            excel_course_catalog.restore_course_catalog_state,
            excel_course_catalog.snapshot_course_catalog_state(),
        )
        load_real_excel_index()

        cls.catalog = getCatalogCache().default_catalog
        cls.scenarios: List[Scenario] = []
        for major in cls.catalog["majors"]:
            fresh = _plan(cls.catalog, [major], [], set())
            for stage in STAGES:
                completed = _completed_after(fresh, stage)
                result = fresh if stage == 0 else _plan(cls.catalog, [major], [], completed)
                cls.scenarios.append(Scenario(f"{major} after {stage} terms", [major], [], completed, stage, result))
        for majors, minors in COMBINATIONS:
            result = _plan(cls.catalog, majors, minors, set())
            cls.scenarios.append(Scenario(f"{' + '.join(majors + minors)}", majors, minors, set(), 0, result))

    def _earned_before_each_term(self, scenario: Scenario) -> List[int]:
        earned = sum(_course_credits(self.catalog, code) for code in scenario.completed)
        totals = []
        for term in scenario.result["semester_plan"]:
            totals.append(earned)
            earned += term["credits"]
        return totals

    # --- Sweep invariants -------------------------------------------------------------------------

    def test_generated_plans_pass_the_engines_own_validation(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                self.assertEqual(s.result["validation_errors"], [])

    def test_plans_cover_every_requirement(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                planned = {c["code"] for t in s.result["semester_plan"] for c in _real_courses(t)}
                taken = s.completed | planned
                slots = build_requirement_slots(
                    self.catalog, s.majors, s.minors, program_options=_required_options(self.catalog, s.majors)
                )
                selection = select_courses_for_slots(self.catalog, slots, taken)
                unmet = sorted(
                    {sid for sid, code in selection["slot_assignment"].items() if code not in taken}
                    | set(selection["remaining_slots"])
                )
                self.assertEqual(unmet, [])

    def test_no_duplicate_courses_and_per_term_credit_limits(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                seen: Set[str] = set()
                for term in s.result["semester_plan"]:
                    self.assertLessEqual(term["credits"], MAX_CREDITS, term["term"])
                    for course in _real_courses(term):
                        self.assertNotIn(course["code"], seen | s.completed, term["term"])
                        seen.add(course["code"])

    def test_prerequisites_are_completed_in_earlier_terms(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                done = set(s.completed)
                for term in s.result["semester_plan"]:
                    for course in _real_courses(term):
                        expr = _course_prereq_expr(self.catalog, course["code"])
                        if expr:
                            self.assertTrue(
                                _prereq_expr_satisfied(expr, done),
                                f"{course['code']} in {term['term']} before its prerequisites",
                            )
                    done |= {c["code"] for c in _real_courses(term)}

    def test_standing_stated_in_the_catalog_is_met(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                earned_before = self._earned_before_each_term(s)
                for idx, term in enumerate(s.result["semester_plan"]):
                    for course in _real_courses(term):
                        required = _min_credits_stated_in_catalog(self.catalog, course["code"])
                        self.assertGreaterEqual(
                            earned_before[idx],
                            required,
                            f"{course['code']} in {term['term']} needs {required} credits",
                        )

    def test_fresh_students_take_foundation_courses_in_the_first_year(self):
        foundation = set(self.catalog.get("foundation_courses") or [])
        for s in self.scenarios:
            if s.stage != 0:
                continue
            with self.subTest(s.label):
                for idx, term in enumerate(s.result["semester_plan"]):
                    for course in _real_courses(term):
                        if course["code"] in foundation:
                            self.assertLess(idx, 2, f"{course['code']} planned for {term['term']}")
                self.assertEqual(_term_of(s.result, "ENG 1000"), _term_of(s.result, "ENG 1001"))

    def test_plans_reach_the_graduation_credit_total(self):
        total_required = self.catalog.get("degree_total_credits") or 120
        for s in self.scenarios:
            with self.subTest(s.label):
                completed = sum(_course_credits(self.catalog, code) for code in s.completed)
                planned = sum(term["credits"] for term in s.result["semester_plan"])
                self.assertGreaterEqual(completed + planned, total_required)

    def test_every_planned_course_states_why_it_is_there(self):
        for s in self.scenarios:
            with self.subTest(s.label):
                for term in s.result["semester_plan"]:
                    for course in _real_courses(term):
                        self.assertTrue(
                            course.get("requirements") or course.get("unlocks"),
                            f"{course['code']} in {term['term']} has no stated reason",
                        )

    # --- Targeted regressions ----------------------------------------------------------------------

    def _fresh(self, major: str) -> Dict:
        return next(s.result for s in self.scenarios if s.majors == [major] and s.stage == 0)

    def test_unlocks_only_name_courses_planned_later(self):
        # "Prerequisite for X" on a course planned after X read like a violation (X's "A or B" was met by A).
        for s in self.scenarios:
            with self.subTest(s.label):
                term_of = {c["code"]: i for i, t in enumerate(s.result["semester_plan"]) for c in t["courses"]}
                for index, term in enumerate(s.result["semester_plan"]):
                    for course in term["courses"]:
                        early = [code for code in course.get("unlocks") or [] if term_of.get(code, -1) <= index]
                        self.assertEqual(early, [], f"{course['code']} in {term['term']}")

    def test_removing_a_required_course_makes_the_plan_invalid(self):
        result = _plan(self.catalog, ["Computer Science"], [], set(), overrides={"remove": [{"code": "COS 2021"}]})
        self.assertIsNone(_term_of(result, "COS 2021"))
        self.assertFalse(result["is_valid"])
        self.assertTrue(any("COS 2021" in error or "Computer Science" in error for error in result["validation_errors"]))

    def test_moving_a_course_before_its_standing_is_reported(self):
        fresh = self._fresh("Business Administration")
        source = _term_of(fresh, "BUS 3000")
        target = fresh["semester_plan"][2]["term"]
        result = _plan(
            self.catalog,
            ["Business Administration"],
            [],
            set(),
            overrides={"move": [{"from_term": source, "to_term": target, "code": "BUS 3000"}]},
        )
        self.assertEqual(_term_of(result, "BUS 3000"), target)
        self.assertTrue(any("BUS 3000" in e and "junior standing" in e for e in result["validation_errors"]))

    def test_removing_elective_placeholders_reports_the_credit_shortfall(self):
        fresh = self._fresh("Computer Science")
        removes = [
            {"term": t["term"], "code": c["code"], "instance_id": c["instance_id"]}
            for t in fresh["semester_plan"]
            for c in t["courses"]
            if _is_free_elective(c["code"])
        ]
        self.assertTrue(removes)
        result = _plan(self.catalog, ["Computer Science"], [], set(), overrides={"remove": removes})
        self.assertFalse(result["is_valid"])
        self.assertTrue(any("credits required to graduate" in e for e in result["validation_errors"]))
        self.assertLess(result["summary"]["projected_credits"], result["summary"]["degree_total_credits"])

    def test_splitting_a_corequisite_pair_is_reported(self):
        fresh = self._fresh("Computer Science")
        source = _term_of(fresh, "ENG 1000")
        target = fresh["semester_plan"][3]["term"]
        result = _plan(
            self.catalog,
            ["Computer Science"],
            [],
            set(),
            overrides={"move": [{"from_term": source, "to_term": target, "code": "ENG 1000"}]},
        )
        self.assertEqual(_term_of(result, "ENG 1000"), target)
        self.assertTrue(any("co-requisite ENG 1001" in e for e in result["validation_errors"]))
        self.assertTrue(any(w["type"] == "FOUNDATION_LATE" and w["course"] == "ENG 1000" for w in result["warnings"]))

    def test_continuing_students_can_take_upper_level_courses_right_away(self):
        fresh = self._fresh("Computer Science")
        completed = {
            c["code"] for t in fresh["semester_plan"] for c in _real_courses(t) if c["code"] != "COS 4091"
        }
        # The CS plan's own courses come to ~85 credits; add courses from another plan to reach senior standing.
        for term in self._fresh("Economics")["semester_plan"]:
            for course in _real_courses(term):
                if sum(_course_credits(self.catalog, c) for c in completed) < 95:
                    completed.add(course["code"])
        self.assertGreaterEqual(sum(_course_credits(self.catalog, c) for c in completed), 87)
        result = _plan(self.catalog, ["Computer Science"], [], completed)
        self.assertEqual(_term_of(result, "COS 4091"), result["semester_plan"][0]["term"])

    def test_foundation_courses_the_student_is_past_are_not_planned(self):
        # Passing ENG 1001 (ENG 1000's co-requisite) and taking "MAT 1000 or equivalent" courses means
        # the placement put the student above ENG 1000 and MAT 1000; they used to be planned afterwards.
        in_progress = {"MAT 1005", "PHY 1010"}
        result = _plan(
            self.catalog, ["Business Administration"], [], {"ENG 1001", "BUS 1001"} | in_progress,
            in_progress_courses=in_progress,
        )
        self.assertIsNone(_term_of(result, "ENG 1000"))
        self.assertIsNone(_term_of(result, "MAT 1000"))
        self.assertIn("ENG 1000", result["completed_courses"])
        # Waived, not earned: ENG 1001 and BUS 1001 only.
        self.assertEqual(result["summary"]["completed_credits"], 7)

    def test_nothing_is_added_to_a_term_the_student_is_registered_for(self):
        # The current term's registration is done: a 6-credit load stays as registered and the missing
        # credits go to later terms, not into it (the frontend sends in-progress courses as completed too).
        in_progress = {"COS 2021", "STA 1005"}
        completed = {"MAT 1003", "COS 1050", "ENG 1000", "ENG 1001", "BUS 1001"}
        result = generate_plan(
            catalog=self.catalog,
            majors=["Computer Science"],
            minors=[],
            completed_courses=completed | in_progress,
            in_progress_courses=in_progress,
            current_term_label="Fall 2026",
            start_term_season="Fall",
            start_term_year=2026,
            program_options=_required_options(self.catalog, ["Computer Science"]),
            placement_waivers=["COS 1020"],
        )
        current = next((t for t in result["semester_plan"] if t["term"] == "Fall 2026"), None)
        self.assertEqual(current["courses"] if current else [], [])
        self.assertEqual(result["validation_errors"], [])
        self.assertGreaterEqual(result["summary"]["projected_credits"], 120)

    def test_excel_only_courses_can_be_added_to_future_terms(self):
        # BUS 4482 (Excel-only, listed for Fall 2026) replaces an elective slot in a senior-year term,
        # the way the app's "add course" flow does it.
        fresh = self._fresh("Computer Science")
        term, slot = next(
            (t["term"], c)
            for t in fresh["semester_plan"][5:]
            for c in t["courses"]
            if _is_free_elective(c["code"])
        )
        result = _plan(
            self.catalog,
            ["Computer Science"],
            [],
            set(),
            overrides={
                "remove": [{"term": term, "code": slot["code"], "instance_id": slot["instance_id"]}],
                "add": [{"term": term, "code": "BUS 4482", "instance_id": "added-bus-4482"}],
            },
        )
        self.assertEqual(_term_of(result, "BUS 4482"), term)
        self.assertEqual(result["validation_errors"], [])

    def test_completed_courses_outside_the_requirements_still_count_toward_credits(self):
        # BUS 4482 is an Excel-only elective: it fills no CS requirement but its 3 credits are earned.
        result = _plan(self.catalog, ["Computer Science"], [], {"BUS 4482"})
        planned = sum(term["credits"] for term in result["semester_plan"])
        self.assertEqual(result["summary"]["projected_credits"] - planned, 3)
        self.assertIsNone(_term_of(result, "BUS 4482"))

    def test_progress_rows_count_completed_electives_after_the_caps(self):
        # "No more than one 4000-level EUR course" (pp.108-109): two completed ones earn 3 elective credits.
        program = "Political Science and International Relations"
        result = _plan(self.catalog, [program], [], {"EUR 4400", "EUR 4401"})
        electives = next(e for e in result["elective_progress"] if e["program"] == program)
        self.assertEqual(electives["credits_done"], 3)
        self.assertEqual(result["category_progress"]["majors"][program]["completed"], 3)

    def test_zero_credit_policy_overrides_are_honored(self):
        self.assertEqual(_course_credits(self.catalog, "AUB 1000"), 0)
        self.assertEqual(_course_credits(self.catalog, "MAT 1001"), 0)

    def test_zero_credit_labs_count_zero_and_fill_no_gened(self):
        # The Excel notes say "Credits: 0 CR" for the physics labs; they used to fall back to 3 credits
        # and, through their lecture's Scientific Investigation tag, could fill a GenEd slot.
        for lab in ("PHY 1011", "PHY 1021"):
            self.assertEqual(_course_credits(self.catalog, lab), 0)
            self.assertEqual(degree_engine._course_gened_categories(self.catalog, lab), [])
        self.assertEqual(_course_credits(self.catalog, "PHY 1010"), 4)
        for scenario in self.scenarios:
            planned = {c["code"] for t in scenario.result["semester_plan"] for c in t["courses"]}
            self.assertFalse(planned & {"PHY 1011", "PHY 1021"}, scenario.label)

    def test_economics_minor_plans_the_intermediate_course_the_student_picked(self):
        # The minor needs ECO 3001 or ECO 3002. Picking ECO 3002 used to be sent as "remove ECO 3001",
        # which left the choice empty and raised "Requirements not covered ... Minor: Economics (choice)".
        programs = (["Business Administration", "Journalism and Mass Communication"], ["Economics"])
        default = _plan(self.catalog, *programs, set())
        self.assertIsNotNone(_term_of(default, "ECO 3001"))
        self.assertIsNone(_term_of(default, "ECO 3002"))

        picked = _plan(self.catalog, *programs, set(), preferred_courses={"ECO 3002"})
        self.assertIsNotNone(_term_of(picked, "ECO 3002"))
        self.assertIsNone(_term_of(picked, "ECO 3001"))
        self.assertIsNone(_term_of(picked, "ECO 3000"))  # ECO 3001's prerequisite is not needed any more
        self.assertFalse([e for e in picked["validation_errors"] if "not covered" in e], picked["validation_errors"])

    def test_a_chosen_elective_can_be_swapped_for_another(self):
        fresh = self._fresh("Computer Science")
        term, slot = next(
            (t["term"], c) for t in fresh["semester_plan"] for c in t["courses"] if _is_free_elective(c["code"])
        )
        # Overrides exactly as the frontend sent them: elective A was put in the slot and removed again
        # (the slot was "restored" as an add), then elective B was put into the same slot.
        overrides = {
            "remove": [
                {"term": term, "instance_id": str(uuid.uuid4())},
                {"term": term, "code": slot["code"], "instance_id": slot["instance_id"]},
            ],
            "add": [
                {"term": term, "code": slot["code"], "instance_id": slot["instance_id"]},
                {"term": term, "code": "COS 3031", "instance_id": str(uuid.uuid4())},
            ],
        }
        result = _plan(self.catalog, ["Computer Science"], [], set(), overrides=overrides)
        term_courses = next(t["courses"] for t in result["semester_plan"] if t["term"] == term)
        self.assertIn("COS 3031", [c["code"] for c in term_courses])
        self.assertNotIn(slot["instance_id"], [c["instance_id"] for c in term_courses])
        self.assertTrue(any(w["type"] == "OVERRIDE_CONFLICT" for w in result["warnings"]))

    def test_a_chosen_elective_can_be_swapped_with_the_new_override_edits(self):
        # The fixed frontend sends a clean swap: one removal of the slot and one add of the new elective.
        fresh = self._fresh("Computer Science")
        term, slot = next(
            (t["term"], c) for t in fresh["semester_plan"] for c in t["courses"] if _is_free_elective(c["code"])
        )
        for elective in ("COS 2031", "COS 3031"):
            overrides = {
                "remove": [{"term": term, "code": slot["code"], "instance_id": slot["instance_id"]}],
                "add": [{"term": term, "code": elective, "instance_id": f"chosen-{elective}"}],
            }
            result = _plan(self.catalog, ["Computer Science"], [], set(), overrides=overrides)
            codes = [c["code"] for t in result["semester_plan"] if t["term"] == term for c in t["courses"]]
            self.assertIn(elective, codes)
            self.assertNotIn(slot["code"], codes)
            self.assertFalse([w for w in result["warnings"] if w["type"].startswith("OVERRIDE_")])


if __name__ == "__main__":
    unittest.main()
