"""What a program lets the student choose, and the placement tests it accepts (policy_overrides.json).

Programs (majors and minors) can carry, each citing its catalog page:
- `options`: choices such as a CS or IS concentration (pp.87, 96), the European Studies language
  (p.90) or an MLC language focus (pp.102, 124). Each choice has course blocks with a role, and can
  add elective rules and an elective pool.
- `placement_waivers`: courses a placement test waives (COS 1020, INF 1030, MLL 2025, ...).

This module is the one place that reads those shapes; everything else uses the typed model.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from course_codes import normalize_course_code


@dataclass(frozen=True)
class OptionBlock:
    courses: Tuple[str, ...]
    count: int
    role: str
    """"elective" (the program's electives, tagged `concentration` on their slots), "required" (its
    own required courses once the choice is made) or "collateral" (outside its credits: a language)."""
    prefer: Tuple[str, ...]
    """Courses the planner should prefer when it picks `count` of `courses`."""


@dataclass(frozen=True)
class OptionChoice:
    name: str
    blocks: Tuple[OptionBlock, ...]
    elective_rules: Tuple[Dict, ...]
    elective_pool: Dict | None


@dataclass(frozen=True)
class ProgramOptions:
    label: str | None
    description: str | None
    required: bool
    multiple: bool
    requirement_label: str
    """A slot label template, e.g. "{choice} language proficiency (B1)"."""
    missing_message: str | None
    choices: Dict[str, OptionChoice]

    def chosen(self, selection: Iterable[str]) -> List[OptionChoice]:
        """The selected choices this program offers, in the order selected."""
        return [self.choices[name] for name in selection if name in self.choices]

    def slot_label(self, choice: str) -> str:
        return self.requirement_label.format(choice=choice)


@dataclass(frozen=True)
class PlacementWaiver:
    course: str
    label: str
    replace_with_elective: bool
    """The student takes another elective instead (catalog p.86): the program's electives grow."""


def program_data(catalog: Dict, kind: str, name: str) -> Dict:
    """A major's or minor's catalog entry (`kind` is "major" or "minor")."""
    data = (catalog.get(f"{kind}s") or {}).get(name)
    return data if isinstance(data, dict) else {}


def selected_programs(majors: Iterable[str], minors: Iterable[str]) -> List[Tuple[str, str]]:
    return [("major", name) for name in majors] + [("minor", name) for name in minors]


def options_offered(catalog: Dict, kind: str, name: str) -> ProgramOptions | None:
    raw = program_data(catalog, kind, name).get("options")
    if not isinstance(raw, dict):
        return None
    elective_by_default = raw.get("counts_as_major_elective")
    return ProgramOptions(
        label=raw.get("label"),
        description=raw.get("description"),
        required=bool(raw.get("required")),
        multiple=bool(raw.get("multiple")),
        requirement_label=str(raw.get("requirement_label") or "{choice}"),
        missing_message=raw.get("missing_message"),
        choices={
            choice: _choice(choice, entry if isinstance(entry, dict) else {}, elective_by_default)
            for choice, entry in (raw.get("choices") or {}).items()
        },
    )


def _choice(name: str, entry: Dict, elective_by_default: object) -> OptionChoice:
    blocks = []
    for block in entry.get("blocks") or []:
        role = block.get("role") or (
            "elective" if block.get("counts_as_major_elective", elective_by_default) else "collateral"
        )
        blocks.append(OptionBlock(
            courses=tuple(normalize_course_code(c) for c in block.get("courses") or [] if isinstance(c, str)),
            count=int(block.get("count") or 0),
            role=role,
            prefer=tuple(normalize_course_code(c) for c in block.get("prefer") or [] if isinstance(c, str)),
        ))
    pool = entry.get("elective_pool")
    return OptionChoice(
        name=name,
        blocks=tuple(blocks),
        elective_rules=tuple(r for r in entry.get("elective_rules") or [] if isinstance(r, dict)),
        elective_pool=pool if isinstance(pool, dict) else None,
    )


def chosen_choices(catalog: Dict, kind: str, name: str, selection: Dict[str, List[str]] | None) -> List[OptionChoice]:
    """The choices the student made for this program, among those it offers."""
    options = options_offered(catalog, kind, name)
    return options.chosen((selection or {}).get(name) or []) if options else []


def placement_tests(catalog: Dict, kind: str, name: str) -> List[PlacementWaiver]:
    return [
        PlacementWaiver(
            course=normalize_course_code(entry["course"]),
            label=entry.get("label") or entry["course"],
            replace_with_elective=bool(entry.get("replace_with_elective")),
        )
        for entry in program_data(catalog, kind, name).get("placement_waivers") or []
        if isinstance(entry, dict) and entry.get("course")
    ]


def offered_placement_waivers(
    catalog: Dict, majors: List[str], minors: List[str], requested: Iterable[str] | None
) -> Set[str]:
    """Requested placement waivers that one of the selected programs accepts."""
    offered = {
        test.course for kind, name in selected_programs(majors, minors) for test in placement_tests(catalog, kind, name)
    }
    return {normalize_course_code(c) for c in requested or [] if isinstance(c, str)} & offered


def preferred_courses(
    catalog: Dict, majors: List[str], minors: List[str], selection: Dict[str, List[str]] | None
) -> Set[str]:
    """Courses the chosen options' blocks `prefer` when the planner picks among them (Data Science
    prefers INF 4080 and MAT 2001 over a fourth COS course, which the IS elective cap would not count)."""
    return {
        code
        for kind, name in selected_programs(majors, minors)
        for choice in chosen_choices(catalog, kind, name, selection)
        for block in choice.blocks
        for code in block.prefer
    }
