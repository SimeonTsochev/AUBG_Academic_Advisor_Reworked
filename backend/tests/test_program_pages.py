"""The committed frontend/seo/programs.json must match what the engine produces today."""
import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
BACKEND_DIR = os.path.dirname(CURRENT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from _isolation import IsolatedTestCase  # noqa: E402

from catalog_artifacts import read_json_artifact  # noqa: E402
from catalog_cache import getCatalogCache  # noqa: E402
from program_pages import (  # noqa: E402
    PROGRAM_PAGES_ARTIFACT_PATH,
    build_program_pages_payload,
    catalog_text_lines,
    slugify,
)


class ProgramPagesArtifactTests(IsolatedTestCase):
    excel_index = "real"

    def setUp(self) -> None:
        super().setUp()
        self.payload = build_program_pages_payload(getCatalogCache().default_catalog)

    def test_committed_artifact_is_up_to_date(self) -> None:
        self.assertEqual(
            read_json_artifact(PROGRAM_PAGES_ARTIFACT_PATH),
            self.payload,
            "Run `python scripts/build_program_pages_artifact.py` and commit frontend/seo/programs.json.",
        )

    def test_every_program_has_a_unique_slug_and_some_requirement(self) -> None:
        paths = [(p["kind"], p["slug"]) for p in self.payload["programs"]]
        self.assertEqual(len(paths), len(set(paths)))
        for program in self.payload["programs"]:
            self.assertTrue(
                program["required"] or program["choices"] or program["electives"],
                program["name"],
            )

    def test_programs_without_a_page_are_named_not_dropped(self) -> None:
        catalog = getCatalogCache().default_catalog
        covered = {(p["kind"], p["name"]) for p in self.payload["programs"]}
        skipped = {(p["kind"], p["name"]) for p in self.payload["not_covered"]}
        offered = {("major", name) for name in catalog["majors"]} | {("minor", name) for name in catalog["minors"]}
        self.assertEqual(covered | skipped, offered)
        self.assertFalse(covered & skipped)

    def test_program_choice_blocks_become_required_courses(self) -> None:
        cs_major = next(
            p for p in self.payload["programs"] if p["kind"] == "major" and p["name"] == "Computer Science"
        )
        self.assertIn("COS 2021", [course["code"] for course in cs_major["required"]])
        self.assertNotIn("Program Choice", [block["label"] for block in cs_major["electives"]])

    def test_listed_courses_have_titles_and_credits(self) -> None:
        missing = [
            course["code"]
            for program in self.payload["programs"]
            for course in program["required"]
            if not course["title"] or course["credits"] is None
        ]
        self.assertEqual(missing, [])


class CatalogTextTests(IsolatedTestCase):
    def test_slugify(self) -> None:
        self.assertEqual(
            slugify("Political Science and International Relations"),
            "political-science-and-international-relations",
        )

    def test_catalog_text_drops_page_footer_and_splits_course_lines(self) -> None:
        lines = catalog_text_lines(
            "Two courses out of the following: BUS 4090 Senior Project BUS 4[4-9]NN Topics in Finance "
            "COS/INF 4081 Internship a place- ment test Minor Programs 121"
        )
        self.assertEqual(
            lines,
            [
                "Two courses out of the following:",
                "BUS 4090 Senior Project",
                "BUS 4[4-9]NN Topics in Finance",
                "COS/INF 4081 Internship a placement test",
            ],
        )
