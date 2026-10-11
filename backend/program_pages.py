"""Build the data behind the public, crawlable program requirement pages.

The frontend build turns this payload into static HTML (`frontend/scripts/generate-seo-pages.mjs`).
Requirements are taken from `build_requirement_slots`, so the pages list exactly what the planner
enforces (including the hard-coded program special cases), not a second interpretation of the PDF.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from business_concentrations import available_business_concentrations
from degree_engine import build_requirement_slots

PROGRAM_PAGES_ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "frontend" / "seo" / "programs.json"

# No page is published for these programs.
_SKIP_PROGRAMS = {
    # No published course requirements.
    ("major", "Self-Designed Major"),
    # The parsed requirements disagree with the catalog (checked against the AY 2025-26 PDF), so a
    # page would state wrong requirements. Remove an entry once the planner's rules are fixed.
    # "POS 2013 or EUR 2013" is parsed as "EUR 2013 or POS 2002"; the minor's "ten credit hours out of" is lost.
    ("major", "Political Science and International Relations"),
    ("minor", "Political Science and International Relations"),
    # "MAT 2001 or MAT 2013" is parsed as "MAT 2012 or MAT 2013".
    ("minor", "Mathematics"),
    # "Plus twelve credit hours out of the following" (six courses) is parsed as six required courses.
    ("major", "Literature"),
    # Both "at least six credit hours out of" lists are parsed as required courses.
    ("minor", "Southeast European Studies"),
    # One block per language focus, but the focus names are not in the parsed data.
    ("major", "Modern Languages and Cultures"),
    ("minor", "Modern Languages and Cultures"),
}

_PAGE_FOOTER_RE = re.compile(r"\s*(?:Major|Minor) Programs \d+\s*$")
_BROKEN_HYPHEN_RE = re.compile(r"(?<=[a-z])- (?=[a-z])")
# Start of a catalog course line: "COS 1020", "COS/INF 4081", "BUS 4[4-9]NN", "COS/INF L[1-2]NN".
_COURSE_LINE_RE = re.compile(r" (?=[A-Z]{3}(?:/[A-Z]{3})? (?:\d{4}\b|[0-9L]\[))")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def catalog_text_lines(rule_text: str) -> List[str]:
    """Clean a PDF-extracted rule and split it so each listed course starts a line."""
    text = re.sub(r"\s+", " ", str(rule_text or "")).strip()
    text = _PAGE_FOOTER_RE.sub("", text)
    text = _BROKEN_HYPHEN_RE.sub("", text)
    return [line.strip() for line in _COURSE_LINE_RE.split(text) if line.strip()]


def _course(catalog: Dict[str, Any], code: str) -> Dict[str, Any]:
    meta = (catalog.get("course_meta") or {}).get(code) or {}
    base = (catalog.get("courses") or {}).get(code) or {}
    excel = ((catalog.get("excel_catalog") or {}).get("by_code") or {}).get(code) or {}

    title = meta.get("title") or excel.get("title")
    if not title and base.get("name") and base.get("name") != code:
        title = base.get("name")

    credits = meta.get("credits")
    if credits is None:
        credits = base.get("credits")
    if credits is None:
        credits = excel.get("credits")

    return {
        "code": code,
        "title": title or None,
        "credits": credits,
        "prereq": (meta.get("prereq_text") or "").strip() or None,
    }


def _courses(catalog: Dict[str, Any], codes) -> List[Dict[str, Any]]:
    known = catalog.get("courses") or {}
    return [_course(catalog, code) for code in dict.fromkeys(codes) if code in known]


def _program(catalog: Dict[str, Any], kind: str, name: str) -> Dict[str, Any]:
    slots = build_requirement_slots(
        catalog,
        [name] if kind == "major" else [],
        [name] if kind == "minor" else [],
    )["slots"]
    own = [slot for slot in slots if slot.get("program") == name and slot.get("program_type") == kind]

    required = [slot["course"] for slot in own if slot.get("type") == "fixed"]
    choices: List[Dict[str, Any]] = []
    seen_groups = set()
    for slot in own:
        if slot.get("type") != "choice" or slot.get("group_id") in seen_groups:
            continue
        seen_groups.add(slot.get("group_id"))
        label = str(slot.get("label") or "")
        # "Program Choice" and "ECO 3001 / ECO 3002" say nothing the course list does not.
        generic = label == "Program Choice" or "/" in label
        choices.append({
            "label": None if generic else label,
            "count": int(slot.get("count") or 1),
            "courses": _courses(catalog, slot.get("courses") or []),
        })

    data = (catalog.get("majors" if kind == "major" else "minors") or {}).get(name) or {}
    electives: List[Dict[str, Any]] = []
    for block in data.get("elective_requirements") or []:
        label = str(block.get("label") or "").strip()
        if "program choice" in label.lower() and not block.get("is_total"):
            continue  # Already expressed as required courses and choices above.
        electives.append({
            "label": label or "Elective Courses",
            "credits_required": block.get("credits_required"),
            "courses_required": block.get("courses_required"),
            "courses": _courses(catalog, block.get("allowed_courses") or []),
            "catalog_text": catalog_text_lines(block.get("rule_text") or ""),
        })

    return {
        "kind": kind,
        "name": name,
        "slug": slugify(name),
        "required": _courses(catalog, required),
        "choices": choices,
        "electives": electives,
    }


def _business_concentrations(catalog: Dict[str, Any]) -> List[str]:
    # Names only: the concentration rules (topic patterns, manual matches) do not reduce to a course list.
    return [name for name in available_business_concentrations(catalog) if name != "General"]


def build_program_pages_payload(catalog: Dict[str, Any]) -> Dict[str, Any]:
    programs = [
        _program(catalog, kind, name)
        for kind, key in (("major", "majors"), ("minor", "minors"))
        for name in sorted(catalog.get(key) or {})
        if (kind, name) not in _SKIP_PROGRAMS
    ]

    gen_ed = catalog.get("gen_ed") or {}
    rules = gen_ed.get("rules") or {}
    categories = [
        {
            "name": name,
            "courses_required": rules.get(name),
            "courses": _courses(catalog, codes),
        }
        for name, codes in sorted((gen_ed.get("categories") or {}).items())
    ]

    return {
        "catalog_year": catalog.get("catalog_year"),
        "catalog_date": str(catalog.get("generated_at") or "")[:10],
        "degree_total_credits": catalog.get("degree_total_credits"),
        "programs": programs,
        # Offered by AUBG but without a page; the index pages name them.
        "not_covered": [
            {"kind": kind, "name": name}
            for kind, key in (("major", "majors"), ("minor", "minors"))
            for name in sorted(catalog.get(key) or {})
            if (kind, name) in _SKIP_PROGRAMS
        ],
        "business_concentrations": _business_concentrations(catalog),
        "foundation_courses": _courses(catalog, catalog.get("foundation_courses") or []),
        "gen_ed": categories,
    }
