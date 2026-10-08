"""How many elective credits each selected program already has from completed and planned courses.

A course counts toward program P's electives when it does not fill one of P's own requirement slots and
- it is listed in one of P's elective blocks (or matches a wildcard such as "ENT 4[4-9]NN"), or
- the Excel catalog tags it as a P elective ("ECO Major Elective"), or
- it matches an elective rule: "Any other ECO courses", "any JMC course",
  "BUS/ENT 3000-4000 level courses".
A course required by another selected program still counts: students may double count across programs.
Capped blocks ("At most 3 credits may come from ...") limit what their courses contribute.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from degree_engine import (
    _catalog_courses,
    _counted_credits_with_caps,
    _course_credits,
    _course_number,
    _elective_block_rule_text,
    _excel_course_record,
    _expand_wildcard_allowed_courses,
    _normalize_course_code,
    _parse_number,
)
from excel_catalog import PROGRAM_TAG_ALIASES, is_program_elective_tag

CAP_RE = re.compile(r"\b(at\s+most|no\s+more\s+than|up\s+to)\b", re.IGNORECASE)
# "BUS/ENT 3000-4000 level", "JMC 3000- or 4000-level"
LEVEL_RANGE_RE = re.compile(
    r"\b([A-Z]{2,4}(?:\s*/\s*[A-Z]{2,4})*)\s+([1-4])000\s*-?\s*(?:or|to|-)?\s*([1-4])000[\s-]*level",
    re.IGNORECASE,
)
# "Any other ECO courses", "any JMC course"
ANY_PREFIX_RE = re.compile(r"\b(?i:any)\s+(?:(?i:other)\s+)?([A-Z]{2,4})\s+(?i:courses?)\b")


@dataclass(frozen=True)
class _RuleMatcher:
    prefix: str
    min_level: int = 0
    max_level: int = 9999

    def matches(self, code: str) -> bool:
        level = _course_number(code)
        return code.startswith(self.prefix + " ") and level is not None and self.min_level <= level <= self.max_level


def _elective_blocks(program_data: Dict) -> List[Dict]:
    # "Program Choice" blocks are requirement choices (ECO 3001 or ECO 3002), not electives.
    return [
        block
        for block in (program_data.get("elective_requirements") or [])
        if isinstance(block, dict)
        and not ("program choice" in str(block.get("label") or "").lower() and not block.get("is_total"))
    ]


def _listed_courses(block: Dict, catalog_courses: Set[str]) -> Set[str]:
    listed = {
        _normalize_course_code(code) for code in (block.get("allowed_courses") or []) if isinstance(code, str)
    } & catalog_courses
    return listed | _expand_wildcard_allowed_courses(catalog_courses, _elective_block_rule_text(block))


def _rule_matchers(program: str, blocks: List[Dict], has_listed_courses: bool) -> List[_RuleMatcher]:
    matchers: List[_RuleMatcher] = []
    for block in blocks:
        text = _elective_block_rule_text(block)
        for prefixes, low, high in LEVEL_RANGE_RE.findall(text):
            for prefix in re.split(r"\s*/\s*", prefixes.upper()):
                matchers.append(_RuleMatcher(prefix, int(low) * 1000, int(high) * 1000 + 999))
        for prefix in ANY_PREFIX_RE.findall(text):
            matchers.append(_RuleMatcher(prefix.upper()))
    if not matchers and not has_listed_courses:
        # Blocks that only state a credit total ("9 credits required") mean courses in the program's subject.
        matchers = [_RuleMatcher(alias) for alias in PROGRAM_TAG_ALIASES.get(program, []) if alias.isupper()]
    return matchers


def _excel_tagged_elective(catalog: Dict, program: str, code: str) -> bool:
    record = _excel_course_record(catalog, code)
    tags = record.get("area_of_study_tags") or record.get("tags") or []
    return any(isinstance(tag, str) and is_program_elective_tag(tag, program) for tag in tags)


def _total_requirement(blocks: List[Dict]) -> Tuple[int | None, int | None, str]:
    totals = [block for block in blocks if block.get("is_total")]
    credits = [int(n) for n in (_parse_number(b.get("credits_required")) for b in totals) if n and n > 0]
    courses = [int(n) for n in (_parse_number(b.get("courses_required")) for b in totals) if n and n > 0]
    rule_text = next((_elective_block_rule_text(b) for b in totals if _elective_block_rule_text(b)), "")
    return (max(credits) if credits else None, max(courses) if courses else None, rule_text)


def _own_requirement_courses(program: str, slots: Dict, taken: Set[str]) -> Set[str]:
    """Taken courses that fill `program`'s own requirement slots, so they are not also its electives."""
    own: Set[str] = set()
    for slot in slots.get("slots", []):
        if slot.get("program") != program:
            continue
        if slot.get("type") == "fixed":
            own.add(slot["course"])
        elif slot.get("type") == "choice":
            # Only `count` courses fill the choice; any other option the student took is an elective.
            own.update(sorted(set(slot.get("courses") or []) & taken)[: int(slot.get("count") or 1)])
    return own


def compute_elective_progress(
    catalog: Dict,
    programs: Iterable[Tuple[str, str]],
    slots: Dict,
    completed: Set[str],
    planned: Set[str],
    manual_major_elective_credits: Dict[str, int],
) -> List[Dict]:
    """One entry per (program, "major"/"minor") that has an elective requirement."""
    catalog_courses = _catalog_courses(catalog)
    taken = completed | planned
    progress: List[Dict] = []
    for program, program_type in programs:
        program_data = (catalog.get(f"{program_type}s") or {}).get(program) or {}
        blocks = _elective_blocks(program_data)
        credits_required, courses_required, rule_text = _total_requirement(blocks)
        if credits_required is None and courses_required is None:
            continue

        listed = set().union(*(_listed_courses(block, catalog_courses) for block in blocks)) if blocks else set()
        matchers = _rule_matchers(program, blocks, bool(listed))
        own = _own_requirement_courses(program, slots, taken)

        def counts(code: str) -> bool:
            return code not in own and (
                code in listed
                or any(m.matches(code) for m in matchers)
                or _excel_tagged_elective(catalog, program, code)
            )

        cap_blocks = [
            block
            for block in blocks
            if not block.get("is_total")
            and _parse_number(block.get("credits_required"))
            and CAP_RE.search(_elective_block_rule_text(block))
        ]
        counted_courses = sorted(code for code in taken if counts(code) and _course_credits(catalog, code) > 0)
        credits_counted = _counted_credits_with_caps(
            catalog=catalog,
            taken=set(counted_courses),
            cap_blocks=cap_blocks,
            required_exclusions=set(),
            allowed_predicate=lambda code: True,
        ) + int(manual_major_elective_credits.get(program, 0) if program_type == "major" else 0)

        if credits_required is not None:
            remaining = max(0, credits_required - credits_counted)
        else:
            remaining = max(0, (courses_required or 0) - len(counted_courses))
        progress.append({
            "program": program,
            "program_type": program_type,
            "credits_required": credits_required,
            "courses_required": courses_required if credits_required is None else None,
            "credits_counted": credits_counted,
            "remaining": remaining,
            "unit": "credits" if credits_required is not None else "courses",
            "rule_text": rule_text,
            "courses": [
                {"code": code, "credits": _course_credits(catalog, code), "completed": code in completed}
                for code in counted_courses
            ],
        })
    return progress
