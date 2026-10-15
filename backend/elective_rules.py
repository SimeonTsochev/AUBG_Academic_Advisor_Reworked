"""Elective sub-rules from the catalog's program pages (AY 2026-27 pp.82-132).

The PDF parser keeps a program's elective sub-rules only as text: "at least nine credit hours of the
following", "no more than six credit hours from each group", "only one MLL course", "at least two
courses must be at the 3000- or 4000-level". policy_overrides.json states them per program as
`elective_rules`, and elective_progress.py evaluates them against the courses that count as the
program's electives, so the elective card can say which rule is still unmet.

A rule:
    {"kind": "at_least" | "at_most" | "at_least_in_one_group",
     "credits": n  or  "courses": n,
     "courses_in": [codes], "patterns": ["ENG 3[4-9]NN", "COS L[1-2]NN"], "prefixes": ["PSY"],
     "except": [codes], "exclude_prefixes": ["COS"], "min_level": 3000,
     "and_excel_tags": ["MLC Major (German Focus) Elective"],
     "any_of": [{course set}, ...],           # union of course sets, e.g. listed courses or tagged topics
     "groups": {name: {course set}},          # at_least_in_one_group only
     "label": "student-facing wording"}
A rule's course set (a `CourseSet`) has members and filters. Members: listed codes, patterns,
prefixes and the `any_of` sets (a union); a set that names no members, e.g. a level rule, covers
every counted course. Filters apply to the whole set: not in `except` or under an excluded prefix,
a number of at least `min_level`, and, with `and_excel_tags`, one of those Excel tags (an MLL topics
course in the German focus, say: the code alone does not tell the language).

`at_most` caps what courses contribute (credits beyond the cap do not count); `at_least` rules
must be met; `at_least_in_one_group` needs the amount from a single group (Sustainability Studies).
A rule with `"plus_waived": true` grows by the credits a placement test waived (an MLC focus, whose
waived course is "replaced with an elective" in the same language).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Dict, FrozenSet, Iterable, List, Set, Tuple

from degree_engine import _course_credits, _course_number, _excel_course_record

# "ENG 3[4-9]NN", "COS L[1-2]NN" (L = level 1-4), "MLL L098", "MLL 10XX"
_PATTERN_TOKEN = re.compile(r"\[(\d)-(\d)\]|N|X|L|\d|\s+|[A-Z]")
# A topics range written as a pattern in a rule's label: "POS 4[4-9]NN".
_RANGE_IN_LABEL = re.compile(r"\b([A-Z]{2,4}) (\d)\[(\d)-(\d)\]NN\b")


def readable_label(label: str) -> str:
    """A rule label as students read it: "POS 4[4-9]NN topics" becomes "POS 4400-4999 topics"."""
    return _RANGE_IN_LABEL.sub(lambda m: f"{m[1]} {m[2]}{m[3]}00–{m[2]}{m[4]}99", label)


def pattern_regex(pattern: str) -> re.Pattern:
    text = pattern.strip().upper()
    prefix, _, number = text.partition(" ")
    parts = []
    for match in _PATTERN_TOKEN.finditer(number):
        token = match.group(0)
        if match.group(1):
            parts.append(f"[{match.group(1)}-{match.group(2)}]")
        elif token in ("N", "X"):
            parts.append(r"\d")
        elif token == "L":
            parts.append("[1-4]")
        else:
            parts.append(re.escape(token))
    return re.compile(rf"^{re.escape(prefix)} {''.join(parts)}$")


def _codes(values: Iterable) -> FrozenSet[str]:
    return frozenset(str(c).strip().upper() for c in values or [])


def _prefixes(values: Iterable) -> Tuple[str, ...]:
    return tuple(f"{p.upper()} " for p in values or [])


@dataclass(frozen=True)
class CourseSet:
    listed: FrozenSet[str]
    patterns: Tuple[re.Pattern, ...]
    prefixes: Tuple[str, ...]
    any_of: Tuple["CourseSet", ...]
    excluded: FrozenSet[str]
    excluded_prefixes: Tuple[str, ...]
    min_level: int
    excel_tags: FrozenSet[str]

    @classmethod
    def parse(cls, spec: Dict) -> "CourseSet":
        return cls(
            listed=_codes(spec.get("courses_in")),
            patterns=tuple(pattern_regex(p) for p in spec.get("patterns") or []),
            prefixes=_prefixes(spec.get("prefixes")),
            any_of=tuple(cls.parse(part) for part in spec.get("any_of") or []),
            excluded=_codes(spec.get("except")),
            excluded_prefixes=_prefixes(spec.get("exclude_prefixes")),
            min_level=int(spec.get("min_level") or 0),
            excel_tags=frozenset(spec.get("and_excel_tags") or []),
        )

    @property
    def names_members(self) -> bool:
        return bool(self.listed or self.patterns or self.prefixes or self.any_of)

    def contains(self, catalog: Dict, code: str) -> bool:
        if code in self.excluded or code.startswith(self.excluded_prefixes):
            return False
        if self.min_level and (_course_number(code) or 0) < self.min_level:
            return False
        if self.excel_tags:
            record = _excel_course_record(catalog, code)
            if not self.excel_tags & set(record.get("area_of_study_tags") or record.get("tags") or []):
                return False
        if not self.names_members:
            return True
        return (
            code in self.listed
            or code.startswith(self.prefixes)
            or any(p.match(code) for p in self.patterns)
            or any(part.contains(catalog, code) for part in self.any_of)
        )


@dataclass(frozen=True)
class ElectiveRule:
    kind: str
    unit: str
    """"courses" (counts courses with credit) or "credits"."""
    amount: int
    courses: CourseSet
    groups: Tuple[CourseSet, ...]
    """`at_least_in_one_group` only."""
    plus_waived: bool
    label: str

    @classmethod
    def parse(cls, spec: Dict) -> "ElectiveRule":
        return cls(
            kind=spec.get("kind") or "",
            unit="courses" if spec.get("courses") else "credits",
            amount=int(spec.get("courses") or spec.get("credits") or 0),
            courses=CourseSet.parse(spec),
            groups=tuple(CourseSet.parse(g) for g in (spec.get("groups") or {}).values()),
            plus_waived=bool(spec.get("plus_waived")),
            label=readable_label(spec.get("label") or ""),
        )

    def measure(self, codes: Iterable[str], credit: Dict[str, int]) -> int:
        if self.unit == "courses":
            return sum(1 for c in codes if credit[c] > 0)
        return sum(credit[c] for c in codes)

    def status(self, counted: int, required: int, met: bool) -> Dict:
        return {
            "label": self.label,
            "kind": self.kind,
            "unit": self.unit,
            "required": required,
            "counted": counted,
            "met": met,
        }


def pool_matcher(catalog: Dict, rules: Iterable[Dict], pools: Iterable[Dict] = ()):
    """Courses the rules (and the program's `elective_pool`s) name are eligible electives. A level
    minimum limits what counts toward its rule, not which courses are electives."""
    sets = [s for s in (CourseSet.parse(r) for r in rules) if s.names_members]
    sets += [CourseSet.parse(g) for r in rules for g in (r.get("groups") or {}).values()]
    sets += [CourseSet.parse(p) for p in pools if p]
    sets = [replace(s, min_level=0) for s in sets]
    return lambda code: any(s.contains(catalog, code) for s in sets)


def evaluate(
    catalog: Dict,
    rules: List[Dict],
    courses: List[str],
    completed: Set[str],
    waived: Set[str] | None = None,
    extra_credits: int = 0,
) -> Tuple[Dict[str, int], List[Dict]]:
    """Credits each course contributes after the caps, and the status of every rule.

    Completed courses are counted first, so a cap drops planned courses before completed ones.
    A placement-waived course satisfies the minimums it belongs to but contributes no credits.
    """
    waived = waived or set()
    order = sorted(courses, key=lambda c: (c not in completed, c))
    credit = {c: _course_credits(catalog, c) for c in order}
    parsed = [ElectiveRule.parse(r) for r in rules]
    statuses: List[Dict] = []

    for rule in parsed:
        if rule.kind != "at_most":
            continue
        members = [c for c in order if rule.courses.contains(catalog, c)]
        cap = rule.amount
        raw = len(members) if rule.unit == "courses" else sum(credit[c] for c in members)
        used = 0
        for code in members:
            if rule.unit == "courses":
                if used >= cap:
                    credit[code] = 0
                elif credit[code] > 0:
                    used += 1
            else:
                allowed = max(0, min(credit[code], cap - used))
                used += allowed
                credit[code] = allowed
        # A cap never fails: credits beyond it simply do not count (the card says so).
        statuses.append({**rule.status(raw, cap, met=True), "over_cap": raw > cap})

    for rule in parsed:
        required = rule.amount + (extra_credits if rule.plus_waived and rule.unit == "credits" else 0)
        if rule.kind == "at_least":
            counted = rule.measure([c for c in order if rule.courses.contains(catalog, c)], credit)
            statuses.append(rule.status(counted, required, met=counted >= required))
        elif rule.kind == "at_least_in_one_group":
            best = max(
                (rule.measure([c for c in order if group.contains(catalog, c)], credit) for group in rule.groups),
                default=0,
            )
            statuses.append(rule.status(best, required, met=best >= required))
    for code in waived & set(order):
        credit[code] = 0
    return credit, statuses


def deficit_credits(statuses: List[Dict], unit: str = "credits") -> int:
    """What the largest unmet minimum still needs, in `unit` (a course is taken as 3 credits)."""
    deficits = []
    for s in statuses:
        if s["kind"] == "at_most" or s["met"]:
            continue
        missing = s["required"] - s["counted"]
        if s["unit"] != unit:
            missing = missing * 3 if unit == "credits" else -(-missing // 3)
        deficits.append(missing)
    return max(deficits, default=0)
