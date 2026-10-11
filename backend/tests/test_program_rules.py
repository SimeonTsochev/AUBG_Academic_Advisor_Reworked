"""Program-page rules from the AY 2026-27 catalog (pp.82-132): elective sub-rules, concentrations and
language focuses, placement tests, grade rules, internships, independent study and course order."""
import os
import sys
from unittest.mock import patch

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase  # noqa: E402

import degree_engine  # noqa: E402
from catalog_cache import getCatalogCache  # noqa: E402
from degree_engine import generate_plan  # noqa: E402
from elective_rules import pattern_regex  # noqa: E402


def grade(code, letter, term="Fall 2025"):
    return {"code": code, "grade": letter, "term": term}


class ProgramRuleTests(IsolatedTestCase):
    excel_index = "real"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.catalog = getCatalogCache().default_catalog

    def _plan(self, majors, minors=(), completed=(), **kwargs):
        with patch.object(degree_engine, "_current_start_term", return_value=("Fall", 2026)):
            return generate_plan(
                catalog=self.catalog,
                majors=list(majors),
                minors=list(minors),
                completed_courses=set(completed),
                start_term_season="Fall",
                start_term_year=2026,
                **kwargs,
            )

    def _electives(self, plan, program, kind):
        return next(e for e in plan["elective_progress"] if e["program"] == program and e["program_type"] == kind)

    def _rule(self, entry, text):
        return next(r for r in entry["rules"] if text in r["label"])

    # --- the pattern language ------------------------------------------------------------------

    def test_catalog_course_patterns(self):
        self.assertTrue(pattern_regex("ENG 3[4-9]NN").match("ENG 3483"))
        self.assertFalse(pattern_regex("ENG 3[4-9]NN").match("ENG 3088"))
        self.assertTrue(pattern_regex("COS L[1-2]NN").match("COS 3150"))
        self.assertTrue(pattern_regex("MLL L098").match("MLL 4098"))
        self.assertTrue(pattern_regex("EUR 4NNN").match("EUR 4401"))

    # --- elective sub-rules --------------------------------------------------------------------

    def test_cs_counts_at_most_six_credits_per_group(self):
        entry = self._electives(self._plan(["Computer Science"], completed={"COS 2031", "INF 1030", "INF 2080", "MAT 2001"}),
                                "Computer Science", "major")
        self.assertEqual(entry["credits_counted"], 6)
        self.assertTrue(self._rule(entry, "2000-level group")["over_cap"])

    def test_cs_counts_at_most_three_non_cos_courses(self):
        entry = self._electives(self._plan(["Computer Science"], completed={"INF 1030", "INF 3035", "INF 4080", "MAT 2014"}),
                                "Computer Science", "major")
        self.assertEqual(entry["credits_counted"], 9)
        self.assertTrue(self._rule(entry, "non-COS")["over_cap"])

    def test_information_systems_takes_one_mll_course(self):
        entry = self._electives(self._plan(["Information Systems"], completed={"MLL 1015", "MLL 2015", "INF 1050"}),
                                "Information Systems", "major")
        self.assertEqual(entry["credits_counted"], 6)  # INF 1050 and one MLL course
        self.assertFalse(self._rule(entry, "INF 1050, INF 3075, INF 4080")["met"])

    def test_economics_needs_three_advanced_courses(self):
        entry = self._electives(self._plan(["Economics"], completed={"ECO 2011", "ECO 2012", "ECO 2015", "ECO 2021"}),
                                "Economics", "major")
        self.assertFalse(self._rule(entry, "At least three courses")["met"])
        self.assertEqual(entry["remaining"], 9)  # three courses still missing

    def test_political_science_topics_and_exclusions(self):
        entry = self._electives(
            self._plan(["Political Science and International Relations"], completed={"EUR 4400", "EUR 4401", "POS 4400", "POS 4092"}),
            "Political Science and International Relations", "major",
        )
        # Topics courses outside the planning pool count; only one 4000-level EUR course; POS 4092 never.
        self.assertEqual(sorted(c["code"] for c in entry["courses"]), ["EUR 4400", "EUR 4401", "POS 4400"])
        self.assertEqual(entry["credits_counted"], 6)
        self.assertEqual(self._rule(entry, "At least 10 credits")["counted"], 6)

    def test_history_needs_both_survey_groups(self):
        entry = self._electives(self._plan(["History and Civilizations"], completed={"HTY 2012", "HTY 2013", "HTY 2014"}),
                                "History and Civilizations", "major")
        self.assertTrue(self._rule(entry, "two survey groups")["met"])
        self.assertFalse(self._rule(entry, "HTY 1008, 2021")["met"])

    def test_psychology_minor_needs_six_non_cross_listed_credits(self):
        entry = self._electives(self._plan(["Economics"], ["Psychology"], completed={"PSY 2075", "PSY 3061", "PSY 3040"}),
                                "Psychology", "minor")
        self.assertFalse(self._rule(entry, "not cross-listed")["met"])
        self.assertGreater(entry["remaining"], 0)

    def test_sustainability_needs_nine_credits_in_one_area(self):
        entry = self._electives(
            self._plan(["Economics"], ["Sustainability Studies"], completed={"ECO 2011", "SCI 1060", "POS 3006", "BUS 3000"}),
            "Sustainability Studies", "minor",
        )
        self.assertFalse(self._rule(entry, "one thematic area")["met"])

    def test_film_and_theater_needs_two_upper_level_courses(self):
        entry = self._electives(
            self._plan(["Economics"], ["Film and Theater Studies"], completed={"THR 1030", "THR 2030", "JMC 2033", "FLM 2021"}),
            "Film and Theater Studies", "minor",
        )
        self.assertFalse(self._rule(entry, "3000- or 4000-level")["met"])
        self.assertEqual(entry["remaining"], 2)

    def test_entrepreneurship_accepts_the_business_substitutes(self):
        plan = self._plan(["Business Administration"], ["Entrepreneurship"])
        planned = {c["code"] for t in plan["semester_plan"] for c in t["courses"]}
        self.assertNotIn("ENT 2020", planned)  # BUS 2020 substitutes (catalog p.115)
        self.assertNotIn("ENT 2061", planned)
        entry = self._electives(plan, "Entrepreneurship", "minor")
        self.assertNotIn("BUS 2020", [c["code"] for c in entry["courses"]])

    # --- options -------------------------------------------------------------------------------

    def test_information_systems_data_science_prefers_courses_the_major_counts(self):
        plan = self._plan(["Information Systems"], program_options={"Information Systems": ["Data Science"]})
        chosen = {c["code"] for t in plan["semester_plan"] for c in t["courses"]
                  if any("Data Science" in r["label"] for r in c.get("requirements") or [])}
        self.assertEqual(len(chosen), 4)
        self.assertTrue({"INF 4080", "MAT 2001"} <= chosen)

    def test_information_systems_e_commerce(self):
        plan = self._plan(["Information Systems"], program_options={"Information Systems": ["e-Commerce"]})
        chosen = {c["code"] for t in plan["semester_plan"] for c in t["courses"]
                  if any("e-Commerce" in r["label"] for r in c.get("requirements") or [])}
        self.assertEqual(chosen, {"COS 3015", "INF 3075", "INF 4081"})

    def test_mlc_major_needs_a_focus(self):
        plan = self._plan(["Modern Languages and Cultures"])
        self.assertTrue(any("needs a language focus" in e for e in plan["validation_errors"]))

    def test_mlc_major_focus_counts_only_its_language(self):
        plan = self._plan(["Modern Languages and Cultures"], completed={"MLL 1025", "MLL 3401", "MLL 1015", "MLL 1016", "MLL 2016"},
                          program_options={"Modern Languages and Cultures": ["German"]})
        required = {c["code"] for t in plan["semester_plan"] for c in t["courses"]
                    if any("German-language focus" in r["label"] for r in c.get("requirements") or [])}
        self.assertEqual(required, {"MLL 2025", "MLL 2026", "MLL 3002"})
        entry = self._electives(plan, "Modern Languages and Cultures", "major")
        focus = self._rule(entry, "German-focus electives")
        # MLL 1025, the German-tagged topics course MLL 3401, and MLL 1026/2027 the plan adds; no French.
        german = {"MLL 1025", "MLL 1026", "MLL 2027", "MLL 3401"}
        self.assertTrue(german <= {c["code"] for c in entry["courses"]})
        self.assertEqual(focus["counted"], 12)
        self.assertTrue(self._rule(entry, "additional electives")["over_cap"])  # French courses: at most 6

    def test_mlc_minor_focus_and_placement(self):
        plan = self._plan(["Economics"], ["Modern Languages and Cultures"], completed={"MLL 2056", "MLL 3003"},
                          program_options={"Modern Languages and Cultures": ["Spanish"]}, placement_waivers=["MLL 2055"])
        entry = self._electives(plan, "Modern Languages and Cultures", "minor")
        self.assertTrue(all(r["met"] for r in entry["rules"]))  # the waived MLL 2055 fills its group
        self.assertEqual(entry["credits_required"], 18)  # plus an extra course in the language
        self.assertEqual(entry["credits_counted"], 6)

    # --- placement tests -----------------------------------------------------------------------

    def test_cpp_placement_waives_cos1020_for_another_elective(self):
        plan = self._plan(["Computer Science"], placement_waivers=["COS 1020"])
        planned = {c["code"] for t in plan["semester_plan"] for c in t["courses"]}
        self.assertNotIn("COS 1020", planned)
        self.assertEqual(self._electives(plan, "Computer Science", "major")["credits_required"], 15)

    def test_a_placement_test_only_counts_for_programs_that_offer_it(self):
        plan = self._plan(["Economics"], placement_waivers=["COS 1020"])
        self.assertNotIn("COS 1020", plan["completed_courses"])

    # --- grade rules ---------------------------------------------------------------------------

    def test_declaring_business_needs_2_5_in_the_first_five_courses(self):
        five = ["BUS 1001", "BUS 2001", "BUS 2020", "BUS 2021", "BUS 2060"]
        plan = self._plan(["Business Administration"], completed=five, grades=[grade(c, "C") for c in five])
        self.assertTrue(any("Declaring the Business Administration major" in e for e in plan["validation_errors"]))
        plan = self._plan(["Business Administration"], completed=five, grades=[grade(c, "B") for c in five])
        self.assertFalse(any("Declaring" in e for e in plan["validation_errors"]))

    def test_finance_minor_needs_c_or_higher(self):
        plan = self._plan(["Economics"], ["Finance"], completed={"BUS 3030"}, grades=[grade("BUS 3030", "C-")])
        self.assertTrue(any("Finance minor courses need a grade of C or higher" in e for e in plan["validation_errors"]))

    def test_jmc_capstone_needs_3_25_in_the_major(self):
        completed = {"JMC 1041", "JMC 1050"}
        plan = self._plan(["Journalism and Mass Communication", "Economics"], completed=completed,
                          grades=[grade(c, "B") for c in completed],
                          overrides={"add": [{"term": "Spring 2029", "code": "JMC 4091", "instance_id": "capstone"}]})
        self.assertTrue(any("JMC 4091 needs a GPA in the Journalism" in e for e in plan["validation_errors"]))

    # --- saved edits on a reshuffled plan ------------------------------------------------------

    def test_a_saved_add_makes_room_by_moving_a_planner_course(self):
        baseline = self._plan(["Economics"])
        full = next(t for t in baseline["semester_plan"] if t["credits"] >= 16 and t["term"] != baseline["semester_plan"][-1]["term"])
        plan = self._plan(["Economics"], overrides={"add": [{"term": full["term"], "code": "PHI 2020", "instance_id": "mine"}]})
        term = next(t for t in plan["semester_plan"] if t["term"] == full["term"])
        self.assertIn("PHI 2020", [c["code"] for c in term["courses"]])  # the student's course stays
        self.assertLessEqual(term["credits"], 17)
        self.assertTrue(any(w["type"] == "OVERRIDE_COURSE_RELIEVED" for w in plan["warnings"]))
        self.assertFalse(any("more than 17 credits" in e for e in plan["validation_errors"]))

    # --- internships, independent study, course order -------------------------------------------

    def test_internship_credits_are_capped_at_three(self):
        plan = self._plan(["Economics"], completed={"EUR 4081", "PSY 4081"})
        self.assertTrue(any("internships" in e for e in plan["validation_errors"]))

    def test_independent_study_needs_thirty_credits(self):
        plan = self._plan(["Economics"], overrides={"add": [{"term": "Fall 2026", "code": "ECO 4098", "instance_id": "is"}]})
        self.assertTrue(any("Independent study needs 30 earned credits" in e for e in plan["validation_errors"]))

    def test_literature_minor_needs_eng2010_before_upper_level_courses(self):
        plan = self._plan(["Economics"], ["Literature"],
                          overrides={"add": [{"term": "Fall 2026", "code": "ENG 3088", "instance_id": "early"}]})
        self.assertTrue(any("ENG 2010 must be completed before 3000-level courses" in e for e in plan["validation_errors"]))
