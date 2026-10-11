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
A course belongs to a rule's set when it is listed, matches a pattern or has one of the prefixes (all
three are optional; a rule with none of them, e.g. a level rule, covers every counted course), is not
in `except` or under an excluded prefix, its number is at least `min_level`, and, with
`and_excel_tags`, the Excel catalog gives it one of those tags (an MLL topics course in the German
focus, say: the code alone does not tell the language).

`at_most` caps what courses contribute (credits beyond the cap do not count); `at_least` rules
must be met; `at_least_in_one_group` needs the amount from a single group (Sustainability Studies).
A rule with `"plus_waived": true` grows by the credits a placement test waived (an MLC focus, whose
waived course is "replaced with an elective" in the same language).
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Set, Tuple

from degree_engine import _course_credits, _course_number, _excel_course_record

# "ENG 3[4-9]NN", "COS L[1-2]NN" (L = level 1-4), "MLL L098", "MLL 10XX"
_PATTERN_TOKEN = re.compile(r"\[(\d)-(\d)\]|N|X|L|\d|\s+|[A-Z]")


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


def _course_set_matcher(catalog: Dict, spec: Dict):
    if spec.get("any_of"):
        parts = [_course_set_matcher(catalog, part) for part in spec["any_of"]]
        outer = _course_set_matcher(catalog, {k: v for k, v in spec.items() if k != "any_of"})
        has_own_set = bool(spec.get("courses_in") or spec.get("patterns") or spec.get("prefixes"))
        if has_own_set:
            return lambda code: outer(code) or any(part(code) for part in parts)
        # The outer spec only filters (except, min_level): it is an open set otherwise.
        return lambda code: outer(code) and any(part(code) for part in parts)
    listed = {str(c).strip().upper() for c in spec.get("courses_in") or []}
    patterns = [pattern_regex(p) for p in spec.get("patterns") or []]
    prefixes = tuple(f"{p.upper()} " for p in spec.get("prefixes") or [])
    excluded = {str(c).strip().upper() for c in spec.get("except") or []}
    excluded_prefixes = tuple(f"{p.upper()} " for p in spec.get("exclude_prefixes") or [])
    required_tags = set(spec.get("and_excel_tags") or [])
    min_level = int(spec.get("min_level") or 0)
    open_set = not (listed or patterns or prefixes)

    def matches(code: str) -> bool:
        if code in excluded or (excluded_prefixes and code.startswith(excluded_prefixes)):
            return False
        if min_level and (_course_number(code) or 0) < min_level:
            return False
        if required_tags:
            record = _excel_course_record(catalog, code)
            if not required_tags & set(record.get("area_of_study_tags") or record.get("tags") or []):
                return False
        if open_set:
            return True
        return code in listed or code.startswith(prefixes) or any(p.match(code) for p in patterns)

    return matches


def pool_matcher(catalog: Dict, rules: Iterable[Dict], pools: Iterable[Dict] = ()):
    """Courses the rules (and the program's `elective_pool`s) name are eligible electives."""
    specs = [r for r in rules if r.get("courses_in") or r.get("patterns") or r.get("prefixes") or r.get("any_of")]
    specs += [g for r in rules for g in (r.get("groups") or {}).values()]
    specs += [p for p in pools if p]
    matchers = [_course_set_matcher(catalog, {k: v for k, v in s.items() if k != "min_level"}) for s in specs]
    return lambda code: any(m(code) for m in matchers)


def _measure(rule: Dict, codes: Iterable[str], credit: Dict[str, int]) -> int:
    return sum(1 for c in codes if credit[c] > 0) if rule.get("courses") else sum(credit[c] for c in codes)


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
    statuses: List[Dict] = []

    for rule in rules:
        if rule.get("kind") != "at_most":
            continue
        matches = _course_set_matcher(catalog, rule)
        members = [c for c in order if matches(c)]
        cap = int(rule.get("courses") or rule.get("credits") or 0)
        raw = len(members) if rule.get("courses") else sum(credit[c] for c in members)
        used = 0
        for code in members:
            if rule.get("courses"):
                if used >= cap:
                    credit[code] = 0
                elif credit[code] > 0:
                    used += 1
            else:
                allowed = max(0, min(credit[code], cap - used))
                used += allowed
                credit[code] = allowed
        # A cap never fails: credits beyond it simply do not count (the card says so).
        statuses.append({**_status(rule, raw, cap, met=True), "over_cap": raw > cap})

    for rule in rules:
        kind = rule.get("kind")
        required = int(rule.get("courses") or rule.get("credits") or 0)
        if rule.get("plus_waived") and not rule.get("courses"):
            required += extra_credits
        if kind == "at_least":
            matches = _course_set_matcher(catalog, rule)
            counted = _measure(rule, [c for c in order if matches(c)], credit)
            statuses.append(_status(rule, counted, required, met=counted >= required))
        elif kind == "at_least_in_one_group":
            best = 0
            for group in (rule.get("groups") or {}).values():
                matches = _course_set_matcher(catalog, group)
                best = max(best, _measure(rule, [c for c in order if matches(c)], credit))
            statuses.append(_status(rule, best, required, met=best >= required))
    for code in waived & set(order):
        credit[code] = 0
    return credit, statuses


def _status(rule: Dict, counted: int, required: int, met: bool) -> Dict:
    return {
        "label": rule.get("label") or "",
        "kind": rule.get("kind"),
        "unit": "courses" if rule.get("courses") else "credits",
        "required": required,
        "counted": counted,
        "met": met,
    }


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
