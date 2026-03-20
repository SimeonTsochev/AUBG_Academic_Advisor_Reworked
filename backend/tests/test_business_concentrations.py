import os
import sys
import unittest

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from business_concentrations import (  # noqa: E402
    build_business_concentration_audit,
    classify_business_course,
)
from degree_engine import compute_elective_recommendations, generate_plan  # noqa: E402


def _catalog(courses: dict[str, str]) -> dict:
    return {
        "courses": {
            code: {"name": title, "credits": 3, "gen_ed": []}
            for code, title in courses.items()
        },
        "course_meta": {
            code: {"credits": 3, "prereq_codes": []}
            for code in courses
        },
        "majors": {
            "Business Administration": {
                "required_courses": ["BUS 1001"],
                "elective_requirements": [],
            },
        },
        "minors": {
            "Integrated Marketing Communications": {
                "required_courses": [],
                "elective_requirements": [],
            },
        },
        "policy_overrides": {
            "business_concentration_manual_matches": {
                "Tourism and Hospitality": {
                    "tourism_special_topics": [
                        {"code": "BUS 4010", "note": "Approved Tourism and Hospitality Management match."},
                        {"code": "BUS 4011", "note": "Approved Tourism and Hospitality Marketing match."},
                    ]
                }
            }
        },
        "foundation_courses": [],
        "gen_ed": {"categories": {"Dummy": []}, "rules": {"Dummy": 0}},
    }


class BusinessConcentrationTests(unittest.TestCase):
    def test_marketing_audit_reports_minor_conflict_and_non_bus_cap(self):
        catalog = _catalog(
            {
                "BUS 1001": "Business Core",
                "BUS 2060": "Marketing Principles",
                "BUS 3061": "Consumer Behavior",
                "BUS 3062": "Advanced Marketing",
                "JMC 2020": "Media Planning",
                "JMC 3070": "Public Relations Writing",
            }
        )

        audit = build_business_concentration_audit(
            catalog=catalog,
            majors=["Business Administration"],
            minors=["Integrated Marketing Communications"],
            business_concentration="Marketing",
            completed_courses=["BUS 2060", "BUS 3061", "JMC 2020", "JMC 3070"],
        )

        self.assertIsNotNone(audit)
        assert audit is not None
        self.assertIn(
            "Marketing concentration cannot be combined with IMC minor.",
            [entry["message"] for entry in audit["messages"]],
        )
        pool = next(pool for pool in audit["elective_pools"] if pool["id"] == "marketing-electives")
        self.assertEqual(pool["counted_credits"], 3)
        self.assertEqual(pool["remaining_credits"], 3)
        self.assertIn("Max 3 non-BUS credits", pool["notes"])

    def test_tourism_manual_matches_are_flagged_for_review(self):
        catalog = _catalog(
            {
                "BUS 1001": "Business Core",
                "BUS 2021": "Accounting Basics",
                "BUS 2060": "Marketing Principles",
                "BUS 3040": "Operations Management",
                "BUS 4010": "Independent Study in Tourism and Hospitality Management",
                "BUS 4011": "Independent Study in Tourism and Hospitality Marketing",
            }
        )

        classification = classify_business_course(
            catalog=catalog,
            code="BUS 4010",
            majors=["Business Administration"],
            minors=[],
            business_concentration="Tourism and Hospitality",
        )

        self.assertIsNotNone(classification)
        assert classification is not None
        self.assertTrue(classification["manual_review"])
        self.assertIn("Elective for Tourism and Hospitality Concentration", classification["badges"])
        self.assertIn("Manual review needed", classification["badges"])

        audit = build_business_concentration_audit(
            catalog=catalog,
            majors=["Business Administration"],
            minors=[],
            business_concentration="Tourism and Hospitality",
            completed_courses=["BUS 2021", "BUS 2060", "BUS 3040", "BUS 4010", "BUS 4011"],
        )

        self.assertIsNotNone(audit)
        assert audit is not None
        special_topics = next(pool for pool in audit["elective_pools"] if pool["id"] == "tourism-special-topics")
        self.assertEqual(special_topics["counted_courses"], 2)
        self.assertEqual(special_topics["remaining_courses"], 0)
        self.assertIn(
            "Approved Tourism and Hospitality Management match.",
            special_topics["notes"],
        )

    def test_recommendations_prioritize_missing_required_concentration_courses(self):
        catalog = _catalog(
            {
                "BUS 1001": "Business Core",
                "BUS 3030": "Finance Required 1",
                "BUS 4030": "Finance Required 2",
                "BUS 4031": "Finance Elective 1",
                "BUS 4033": "Finance Elective 2",
            }
        )

        recommendations = compute_elective_recommendations(
            catalog=catalog,
            majors=["Business Administration"],
            minors=[],
            business_concentration="Finance",
            completed_courses=set(),
            planned_courses=[],
            limit=10,
        )

        codes = [entry["code"] for entry in recommendations[:4]]
        self.assertEqual(codes[:2], ["BUS 3030", "BUS 4030"])
        self.assertIn("Required for Finance Concentration", recommendations[0]["tags"])
        self.assertIn("Elective for Finance Concentration", recommendations[2]["tags"])

    def test_generate_plan_schedules_required_concentration_courses(self):
        catalog = _catalog(
            {
                "BUS 1001": "Business Core",
                "BUS 3030": "Finance Required 1",
                "BUS 4030": "Finance Required 2",
                "BUS 4031": "Finance Elective 1",
                "BUS 4033": "Finance Elective 2",
            }
        )

        plan = generate_plan(
            catalog=catalog,
            majors=["Business Administration"],
            minors=[],
            business_concentration="Finance",
            completed_courses={"BUS 1001"},
            max_credits_per_semester=16,
            start_term_season="Fall",
            start_term_year=2025,
        )

        scheduled_codes = {
            course["code"]
            for term in plan["semester_plan"]
            for course in term["courses"]
        }
        self.assertIn("BUS 3030", scheduled_codes)
        self.assertIn("BUS 4030", scheduled_codes)

        audit = plan["business_concentration_audit"]
        required_status = {
            course["code"]: course["status"]
            for course in (audit or {}).get("required_courses", [])
        }
        self.assertIn(required_status.get("BUS 3030"), {"completed", "planned"})
        self.assertIn(required_status.get("BUS 4030"), {"completed", "planned"})


if __name__ == "__main__":
    unittest.main()
