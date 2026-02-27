import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from catalog_parser import _parse_prereq_blocks, _prereq_blocks_to_expr  # noqa: E402
from degree_engine import validate_plan  # noqa: E402


def _base_catalog() -> dict:
    courses = {
        "AAA 1000": {"name": "A", "credits": 3, "gen_ed": []},
        "BBB 1000": {"name": "B", "credits": 3, "gen_ed": []},
        "CCC 1000": {"name": "C", "credits": 3, "gen_ed": []},
        "BUS 2060": {"name": "Business Fundamentals", "credits": 3, "gen_ed": []},
        "ENT 2061": {"name": "Entrepreneurship Fundamentals", "credits": 3, "gen_ed": []},
        "STA 1005": {"name": "Intro Statistics", "credits": 3, "gen_ed": []},
        "BUS 3062": {"name": "Applied Business Analysis", "credits": 3, "gen_ed": []},
        "TGT 2000": {"name": "Target OR", "credits": 3, "gen_ed": []},
        "TGT 2100": {"name": "Target AND OR", "credits": 3, "gen_ed": []},
        "TGT 2200": {"name": "Target Legacy", "credits": 3, "gen_ed": []},
    }
    bus3062_blocks = _parse_prereq_blocks(
        "Prerequisite: BUS 2060 or ENT 2061 and STA 1005."
    )
    bus3062_expr = _prereq_blocks_to_expr(bus3062_blocks)
    course_meta = {
        "AAA 1000": {"credits": 3, "prereq_codes": []},
        "BBB 1000": {"credits": 3, "prereq_codes": []},
        "CCC 1000": {"credits": 3, "prereq_codes": []},
        "BUS 2060": {"credits": 3, "prereq_codes": []},
        "ENT 2061": {"credits": 3, "prereq_codes": []},
        "STA 1005": {"credits": 3, "prereq_codes": []},
        "BUS 3062": {
            "credits": 3,
            "prereq_codes": ["BUS 2060", "ENT 2061", "STA 1005"],
            "prereq_text": "Prerequisite: BUS 2060 or ENT 2061 and STA 1005.",
            "prereq_expr": bus3062_expr,
            "prereq_blocks": bus3062_blocks,
        },
        "TGT 2000": {
            "credits": 3,
            "prereq_codes": ["AAA 1000", "BBB 1000"],
            "prereq_text": "Prerequisite: AAA 1000 or BBB 1000.",
            "prereq_blocks": [{"type": "or", "courses": ["AAA 1000", "BBB 1000"]}],
        },
        "TGT 2100": {
            "credits": 3,
            "prereq_codes": ["AAA 1000", "BBB 1000", "CCC 1000"],
            "prereq_text": "Prerequisite: AAA 1000 and (BBB 1000 or CCC 1000).",
            "prereq_blocks": [
                {"type": "course", "code": "AAA 1000"},
                {"type": "or", "courses": ["BBB 1000", "CCC 1000"]},
            ],
        },
        "TGT 2200": {
            "credits": 3,
            "prereq_codes": ["AAA 1000", "BBB 1000"],
            "prereq_text": "Prerequisite: AAA 1000 and BBB 1000.",
        },
    }
    return {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {},
        "minors": {},
        "foundation_courses": [],
        "gen_ed": {"categories": {"Dummy": []}, "rules": {"Dummy": 0}},
    }


def _or_impact_catalog() -> dict:
    courses = {
        "BUS 2020": {"name": "BUS 2020", "credits": 3, "gen_ed": []},
        "ENT 2020": {"name": "ENT 2020", "credits": 3, "gen_ed": []},
        "ECO 1001": {"name": "ECO 1001", "credits": 3, "gen_ed": []},
        "STA 1005": {"name": "STA 1005", "credits": 3, "gen_ed": []},
        "FIN 3000": {"name": "FIN 3000", "credits": 3, "gen_ed": []},
    }
    expr_text = "BUS 2020 (or ENT 2020), ECO 1001, and STA 1005"
    blocks = _parse_prereq_blocks(expr_text)
    course_meta = {
        "BUS 2020": {"credits": 3, "prereq_codes": []},
        "ENT 2020": {"credits": 3, "prereq_codes": []},
        "ECO 1001": {"credits": 3, "prereq_codes": []},
        "STA 1005": {"credits": 3, "prereq_codes": []},
        "FIN 3000": {
            "credits": 3,
            "prereq_text": expr_text,
            "prereq_codes": ["BUS 2020", "ENT 2020", "ECO 1001", "STA 1005"],
            "prereq_expr": _prereq_blocks_to_expr(blocks),
        },
    }
    return {
        "courses": courses,
        "course_meta": course_meta,
        "majors": {},
        "minors": {},
        "foundation_courses": [],
        "gen_ed": {"categories": {"Dummy": []}, "rules": {"Dummy": 0}},
    }


def _prereq_violation(catalog: dict, target: str, completed: set[str]) -> bool:
    semester_plan = [
        {
            "term": "Fall 2025",
            "courses": [{"code": target, "name": target, "credits": 3}],
            "credits": 3,
        }
    ]
    errors = validate_plan(
        catalog=catalog,
        semester_plan=semester_plan,
        completed_courses=completed,
        start_term=("Fall", 2025),
        min_credits=0,
        max_credits=20,
        strict_prereqs=True,
    )
    needle = f"{target} scheduled before prerequisites"
    return any(needle in error for error in errors)


def _prereq_errors(catalog: dict, target: str, completed: set[str]) -> list[str]:
    semester_plan = [
        {
            "term": "Fall 2025",
            "courses": [{"code": target, "name": target, "credits": 3}],
            "credits": 3,
        }
    ]
    return validate_plan(
        catalog=catalog,
        semester_plan=semester_plan,
        completed_courses=completed,
        start_term=("Fall", 2025),
        min_credits=0,
        max_credits=20,
        strict_prereqs=True,
    )


class PrereqOrLogicTests(unittest.TestCase):
    def test_catalog_parser_builds_structured_or_blocks(self):
        blocks = _parse_prereq_blocks("Prerequisite: COS 1010 and Either MAT 1050 or MAT 1100.")
        self.assertEqual(
            blocks,
            [
                {"type": "course", "code": "COS 1010"},
                {"type": "or", "courses": ["MAT 1050", "MAT 1100"]},
            ],
        )

        one_of = _parse_prereq_blocks("Prerequisite: One of the following: MAT 1050, MAT 1100.")
        self.assertEqual(one_of, [{"type": "or", "courses": ["MAT 1050", "MAT 1100"]}])

    def test_bus3062_or_and_parse_and_eval(self):
        blocks = _parse_prereq_blocks("Prerequisite: BUS 2060 or ENT 2061 and STA 1005.")
        self.assertEqual(
            blocks,
            [
                {"type": "or", "courses": ["BUS 2060", "ENT 2061"]},
                {"type": "course", "code": "STA 1005"},
            ],
        )

        catalog = _base_catalog()
        self.assertFalse(_prereq_violation(catalog, "BUS 3062", {"BUS 2060", "STA 1005"}))
        self.assertFalse(_prereq_violation(catalog, "BUS 3062", {"ENT 2061", "STA 1005"}))
        self.assertTrue(_prereq_violation(catalog, "BUS 3062", {"BUS 2060"}))
        self.assertTrue(_prereq_violation(catalog, "BUS 3062", {"STA 1005"}))

    def test_bus3062_catalog_style_text_with_commas(self):
        blocks = _parse_prereq_blocks(
            "Completion of BUS 2060 or ENT 2061 with a grade of C or better, STA 1005, and junior standing"
        )
        self.assertEqual(
            blocks,
            [
                {"type": "or", "courses": ["BUS 2060", "ENT 2061"]},
                {"type": "course", "code": "STA 1005"},
            ],
        )
        expr = _prereq_blocks_to_expr(blocks)
        self.assertEqual(
            expr,
            {"and": [{"or": ["BUS 2060", "ENT 2061"]}, "STA 1005"]},
        )

    def test_prereq_expr_only_is_supported(self):
        catalog = _base_catalog()
        catalog["course_meta"]["BUS 3062"] = {
            "credits": 3,
            "prereq_text": "Prerequisite: BUS 2060 (or ENT 2061), STA 1005.",
            "prereq_expr": {"and": [{"or": ["BUS 2060", "ENT 2061"]}, "STA 1005"]},
        }
        self.assertFalse(_prereq_violation(catalog, "BUS 3062", {"BUS 2060", "STA 1005"}))
        self.assertFalse(_prereq_violation(catalog, "BUS 3062", {"ENT 2061", "STA 1005"}))
        self.assertTrue(_prereq_violation(catalog, "BUS 3062", {"STA 1005"}))

    def test_unmet_or_group_is_reported_as_single_item(self):
        catalog = _base_catalog()
        errors = _prereq_errors(catalog, "BUS 3062", {"STA 1005"})
        joined = " | ".join(errors)
        self.assertIn("BUS 2060 OR ENT 2061", joined)

    def test_requested_or_impact_case(self):
        blocks = _parse_prereq_blocks("BUS 2020 (or ENT 2020), ECO 1001, and STA 1005")
        self.assertEqual(
            blocks,
            [
                {"type": "or", "courses": ["BUS 2020", "ENT 2020"]},
                {"type": "course", "code": "ECO 1001"},
                {"type": "course", "code": "STA 1005"},
            ],
        )
        catalog = _or_impact_catalog()
        self.assertFalse(_prereq_violation(catalog, "FIN 3000", {"ENT 2020", "ECO 1001", "STA 1005"}))
        self.assertTrue(_prereq_violation(catalog, "FIN 3000", {"ECO 1001", "STA 1005"}))

    def test_or_prereq_allows_either_course(self):
        catalog = _base_catalog()
        self.assertFalse(_prereq_violation(catalog, "TGT 2000", {"AAA 1000"}))
        self.assertFalse(_prereq_violation(catalog, "TGT 2000", {"BBB 1000"}))
        self.assertTrue(_prereq_violation(catalog, "TGT 2000", set()))

    def test_and_with_or_prereq_logic(self):
        catalog = _base_catalog()
        self.assertFalse(_prereq_violation(catalog, "TGT 2100", {"AAA 1000", "BBB 1000"}))
        self.assertFalse(_prereq_violation(catalog, "TGT 2100", {"AAA 1000", "CCC 1000"}))
        self.assertTrue(_prereq_violation(catalog, "TGT 2100", {"AAA 1000"}))
        self.assertTrue(_prereq_violation(catalog, "TGT 2100", {"BBB 1000"}))

    def test_legacy_flat_prereq_list_stays_and(self):
        catalog = _base_catalog()
        self.assertTrue(_prereq_violation(catalog, "TGT 2200", {"AAA 1000"}))
        self.assertFalse(_prereq_violation(catalog, "TGT 2200", {"AAA 1000", "BBB 1000"}))


if __name__ == "__main__":
    unittest.main()
