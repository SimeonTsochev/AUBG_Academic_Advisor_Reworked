from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple
import datetime
import logging
import math
import re
import statistics
import uuid

from excel_catalog import (
    PROGRAM_TAG_ALIASES,
    get_recommended_electives,
    get_case_studies_gened_courses,
    get_selected_program_elective_tags,
)
from excel_course_catalog import (
    get_course as get_excel_course_record,
    get_course_codes as get_excel_course_codes,
)

MIN_CREDITS_PER_TERM = 14
CATEGORY_PREREQS = {
    "Historical Research": {"Historical Sources"},
}

COURSE_CODE_PATTERN = re.compile(r"\b[A-Z]{2,4}\s?\d{3,4}\b")
PREREQ_OR_GROUP_RE = re.compile(
    r"(?:[A-Z]{2,4}\s?\d{3,4})(?:\s*(?:/|OR)\s*(?:[A-Z]{2,4}\s?\d{3,4}))+"
)
GEN_ED_SPLIT_RE = re.compile(r"[,/;|]+")
GEN_ED_TAG_RE = re.compile(r"\bgen[\s-]?ed\b", re.IGNORECASE)

SOURCE_REASON_MAJOR = "MAJOR_REQUIRED"
SOURCE_REASON_MINOR = "MINOR_REQUIRED"
SOURCE_REASON_GENED = "GENED_REQUIRED"
SOURCE_REASON_PREREQ = "PREREQ_FOR_REQUIRED"
SOURCE_REASON_FREE = "FREE_ELECTIVE_PLACEHOLDER"
ALLOWED_SOURCE_REASONS = {
    SOURCE_REASON_MAJOR,
    SOURCE_REASON_MINOR,
    SOURCE_REASON_GENED,
    SOURCE_REASON_PREREQ,
    SOURCE_REASON_FREE,
}

INSTANCE_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "aubg-plan-instance-v1")

CS_MINOR_REQUIRED_COURSES = {"COS 1020"}
CS_MINOR_GROUPS: Dict[str, Set[str]] = {
    "Foundations": {"COS 1050", "COS 2035", "COS 3031", "MAT 2050"},
    "Software Development": {"COS 2021", "COS 3015", "COS 4060"},
    "Advanced Topics": {"COS 2031", "COS 4040", "COS 4070"},
}
CS_MINOR_ELECTIVE_CREDITS_REQUIRED = 15

CREATIVE_WRITING_REQUIRED_OPTIONS = {"ENG 2005", "ENG 2006"}
CREATIVE_WRITING_BASE_ELECTIVES = {"JMC 1050", "FLM 2021", "ENG 3005", "JMC 4045"}
CREATIVE_WRITING_ELECTIVE_CREDITS_REQUIRED = 16
CREATIVE_WRITING_MIN_UPPER_LEVEL_ELECTIVES = 2

# Sustainability Studies minor rules (AY 2025-26 screenshots):
# - Total: 18 credits
# - Required: SUS 1000 and SUS 2010
# - Electives: 12 credits with distribution: minimum 9 credits from ONE thematic area and 3 credits from another.
SUSTAINABILITY_REQUIRED_COURSES = {"SUS 1000", "SUS 2010"}
SUSTAINABILITY_ELECTIVE_CREDITS_REQUIRED = 12
SUSTAINABILITY_PRIMARY_THEME_CREDITS = 9
SUSTAINABILITY_SECONDARY_THEME_CREDITS = 3

# Common rule-text helpers for elective blocks.
ELECTIVE_CAP_RE = re.compile(r"\bno\s+more\s+than\b", re.IGNORECASE)
ELECTIVE_MIN_RE = re.compile(r"\b(at\s+least|minimum)\b", re.IGNORECASE)
ELECTIVE_UPPER_LEVEL_RE = re.compile(r"\b(3000|4000)[-\s]*(?:and/or|or|/)?\s*(3000|4000)?\b", re.IGNORECASE)

FINE_ARTS_GROUP_A = {"FAR 1003", "FAR 1009", "THR 2011"}
FINE_ARTS_GROUP_B = {"FAR 3007", "FAR 3009", "FAR 3010"}
FINE_ARTS_GROUP_C = {"FAR 1005", "FAR 1021", "FAR 1022", "FAR 2003", "FAR 4003", "THR 1030", "THR 2022", "THR 2030"}
FINE_ARTS_GROUP_C_CREDITS_REQUIRED = 6
FINE_ARTS_ELECTIVE_CREDITS_REQUIRED = 6

BUSINESS_ADMIN_ELECTIVE_CREDITS_REQUIRED = 9
BUSINESS_ADMIN_NON_BUS_ELECTIVES = {
    "EUR 3003",
    "EUR 3020",
    "JMC 2020",
    "JMC 3070",
    "JMC 3089",
    "SUS 3001",
    "SUS 4500",
}
BUSINESS_ADMIN_NON_BUS_ELECTIVE_CAP = 3
BUSINESS_ADMIN_THESIS_PROJECT_ELECTIVES = {"BUS 4090", "BUS 4091", "BUS 4092"}
BUSINESS_ADMIN_THESIS_PROJECT_ELECTIVE_CAP = 3


def _normalize_course_code(code: str) -> str:
    code = code.strip().upper()
    m = re.match(r"^([A-Z]{3})\s?(\d{3,4})$", code)
    if not m:
        return code
    return f"{m.group(1)} {m.group(2)}"


def _norm_minor_name(value: object) -> str:
    text = str(value).strip().lower()
    # Remove parenthetical aliases like "(COS)" to match stored UI/program labels.
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("&", " and ")
    # Ignore punctuation differences in comparisons.
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_selected_program_minor(minor_name: str, majors: List[str], minors: List[str]) -> bool:
    target = _norm_minor_name(minor_name)
    if not target:
        return False
    selected_norm = {
        _norm_minor_name(name)
        for name in [*(majors or []), *(minors or [])]
        if isinstance(name, str)
    }
    return target in selected_norm


def _is_cs_minor(minor_name: str) -> bool:
    n = _norm_minor_name(minor_name)
    return ("computer science" in n) or n.startswith("cos") or re.search(r"\bcos\b", n) is not None


def _is_creative_writing_minor(minor_name: str) -> bool:
    return "creative writing" in _norm_minor_name(minor_name)


def _is_fine_arts_minor(minor_name: str) -> bool:
    n = _norm_minor_name(minor_name)
    return "fine arts" in n or n == "fine art"


def _is_business_administration_major(major_name: str) -> bool:
    return _norm_minor_name(major_name) == "business administration"


def _course_number(code: str) -> int | None:
    m = re.match(r"^[A-Z]{2,4}\s?(\d{3,4})$", str(code).strip().upper())
    if not m:
        return None
    return int(m.group(1))


def _is_business_administration_bus_ent_upper_level(code: str) -> bool:
    normalized = _normalize_course_code(code)
    parts = normalized.split()
    if len(parts) != 2:
        return False
    if parts[0] not in {"BUS", "ENT"}:
        return False
    number = _course_number(normalized)
    return number is not None and 3000 <= int(number) <= 4999


def _business_administration_required_courses(catalog: Dict) -> Set[str]:
    majors = catalog.get("majors", {}) or {}
    if not isinstance(majors, dict):
        return set()
    for major_name, major_data in majors.items():
        if not isinstance(major_name, str) or not _is_business_administration_major(major_name):
            continue
        if not isinstance(major_data, dict):
            continue
        required = major_data.get("required_courses") or []
        if not isinstance(required, list):
            continue
        return {
            _normalize_course_code(code)
            for code in required
            if isinstance(code, str) and _normalize_course_code(code)
        }
    return set()


def _business_administration_elective_credit_breakdown(catalog: Dict, taken_courses: Set[str]) -> Dict[str, int]:
    taken = {
        _normalize_course_code(code)
        for code in (taken_courses or set())
        if isinstance(code, str) and _normalize_course_code(code)
    }
    required_courses = _business_administration_required_courses(catalog)

    non_bus_earned = sum(
        _course_credits(catalog, code)
        for code in taken
        if code in BUSINESS_ADMIN_NON_BUS_ELECTIVES
    )
    thesis_project_earned = sum(
        _course_credits(catalog, code)
        for code in taken
        if code in BUSINESS_ADMIN_THESIS_PROJECT_ELECTIVES
    )

    bus_ent_upper_level_earned = 0
    for code in taken:
        if code in required_courses:
            continue
        if code in BUSINESS_ADMIN_THESIS_PROJECT_ELECTIVES:
            continue
        if _is_business_administration_bus_ent_upper_level(code):
            bus_ent_upper_level_earned += _course_credits(catalog, code)

    non_bus_counted = min(BUSINESS_ADMIN_NON_BUS_ELECTIVE_CAP, int(non_bus_earned))
    thesis_project_counted = min(BUSINESS_ADMIN_THESIS_PROJECT_ELECTIVE_CAP, int(thesis_project_earned))
    counted_total = min(
        BUSINESS_ADMIN_ELECTIVE_CREDITS_REQUIRED,
        int(non_bus_counted + thesis_project_counted + bus_ent_upper_level_earned),
    )
    remaining = max(0, BUSINESS_ADMIN_ELECTIVE_CREDITS_REQUIRED - counted_total)
    return {
        "required": BUSINESS_ADMIN_ELECTIVE_CREDITS_REQUIRED,
        "counted_total": counted_total,
        "remaining": int(remaining),
        "non_bus_counted": int(non_bus_counted),
        "thesis_project_counted": int(thesis_project_counted),
        "bus_ent_upper_level_counted": int(bus_ent_upper_level_earned),
    }


def _tag_prefix(tag: object) -> str:
    if not isinstance(tag, str):
        return ""
    parts = tag.strip().split()
    if not parts:
        return ""
    return parts[0].upper()


def _limit_business_administration_non_bus_elective_candidates(
    candidates: List[Dict[str, object]],
    majors: List[str],
) -> List[Dict[str, object]]:
    if not any(_is_business_administration_major(name) for name in majors or []):
        return candidates

    non_bus_used = 0
    limited: List[Dict[str, object]] = []

    for entry in candidates:
        code = entry.get("code")
        if not isinstance(code, str):
            limited.append(entry)
            continue

        matched_major = entry.get("matched_major_tags") or []
        matched_minor = entry.get("matched_minor_tags") or []
        if not isinstance(matched_major, list):
            matched_major = []
        if not isinstance(matched_minor, list):
            matched_minor = []

        has_bus_major_match = any(_tag_prefix(tag) == "BUS" for tag in matched_major)
        if code in BUSINESS_ADMIN_NON_BUS_ELECTIVES and has_bus_major_match:
            if non_bus_used >= 1:
                pruned_major = [tag for tag in matched_major if _tag_prefix(tag) != "BUS"]
                if not pruned_major and not matched_minor:
                    continue
                next_entry = dict(entry)
                next_entry["matched_major_tags"] = pruned_major
                limited.append(next_entry)
                continue
            non_bus_used += 1

        limited.append(entry)

    return limited


def _parse_number(value: object) -> float | None:
    """Parse numeric values from int/float/numeric strings; return None for invalid values."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if not math.isfinite(numeric):
            return None
        return numeric
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
            return None
        try:
            numeric = float(text)
        except ValueError:
            return None
        if not math.isfinite(numeric):
            return None
        return numeric
    return None


def _typical_credit_for_allowed_set(catalog: Dict, allowed_set: Set[str]) -> float:
    """Estimate a representative course credit value for an elective block.

    Uses median credits from allowed course codes when available; falls back to 3.
    """
    if not allowed_set:
        return 3.0
    credits: List[float] = []
    for code in allowed_set:
        credit_value = _course_credits(catalog, code)
        if isinstance(credit_value, (int, float)) and credit_value > 0:
            credits.append(float(credit_value))
    if not credits:
        return 3.0
    typical = float(statistics.median(credits))
    if typical <= 0 or not math.isfinite(typical):
        return 3.0
    return typical


def _coerce_positive_int(value: object, default: int = 1) -> int:
    parsed = _parse_number(value)
    if parsed is None:
        return default
    rounded = round(parsed)
    if abs(parsed - rounded) > 1e-9 or rounded <= 0:
        return default
    return int(rounded)


def _coerce_minor_choice_group(
    raw_group: object,
    catalog_courses: Set[str],
    fallback_label: str,
) -> Dict[str, object] | None:
    if isinstance(raw_group, (list, tuple, set)):
        raw_group = {
            "courses": list(raw_group),
            "count": 1,
            "label": fallback_label,
        }
    if not isinstance(raw_group, dict):
        return None

    option_sources: List[object] = []
    for key in ("courses", "options", "choices", "items", "blocks", "allowed_courses"):
        value = raw_group.get(key)
        if isinstance(value, (list, tuple, set)):
            option_sources.extend(list(value))

    if not option_sources:
        code_value = raw_group.get("code") or raw_group.get("course")
        if isinstance(code_value, str):
            option_sources = [code_value]

    options: List[str] = []
    seen: Set[str] = set()

    def add_option(raw: object) -> None:
        if isinstance(raw, str):
            code = _normalize_course_code(raw)
            if code in catalog_courses and code not in seen:
                seen.add(code)
                options.append(code)
            return
        if isinstance(raw, dict):
            code_value = raw.get("code") or raw.get("course")
            if isinstance(code_value, str):
                add_option(code_value)

    for source in option_sources:
        add_option(source)

    if not options:
        return None

    count_value = raw_group.get("count")
    if count_value is None:
        for key in ("choose", "courses_required", "required_count", "min_count"):
            if raw_group.get(key) is not None:
                count_value = raw_group.get(key)
                break
    count = min(_coerce_positive_int(count_value, default=1), len(options))
    if count <= 0:
        return None

    label = str(raw_group.get("label") or raw_group.get("name") or fallback_label).strip()
    if not label:
        label = fallback_label
    return {
        "courses": options,
        "count": count,
        "label": label,
    }


def _extract_minor_required_structure(
    minor_data: Dict,
    catalog_courses: Set[str],
) -> Tuple[Set[str], List[Dict[str, object]]]:
    requirements = minor_data.get("requirements")
    if requirements is None:
        requirements = minor_data.get("required_courses")

    fixed: List[str] = []
    fixed_seen: Set[str] = set()
    choice_groups: List[Dict[str, object]] = []
    choice_seen: Set[Tuple[Tuple[str, ...], int]] = set()
    group_index = 1

    def add_fixed(raw_code: object) -> None:
        if not isinstance(raw_code, str):
            return
        code = _normalize_course_code(raw_code)
        if code not in catalog_courses or code in fixed_seen:
            return
        fixed_seen.add(code)
        fixed.append(code)

    def add_choice_group(raw_group: object, label_hint: str = "Requirement choice") -> bool:
        nonlocal group_index
        group = _coerce_minor_choice_group(
            raw_group=raw_group,
            catalog_courses=catalog_courses,
            fallback_label=f"{label_hint} {group_index}",
        )
        if not group:
            return False
        signature = (tuple(group["courses"]), int(group["count"]))
        if signature in choice_seen:
            return True
        choice_seen.add(signature)
        choice_groups.append(group)
        group_index += 1
        return True

    def parse_fixed_container(value: object, label_hint: str = "Requirement choice") -> None:
        if isinstance(value, str):
            add_fixed(value)
            return
        if not isinstance(value, (list, tuple, set)):
            return
        for item in value:
            if isinstance(item, str):
                add_fixed(item)
                continue
            if add_choice_group(item, label_hint=label_hint):
                continue
            if isinstance(item, dict):
                add_fixed(item.get("code") or item.get("course"))

    if isinstance(requirements, str):
        add_fixed(requirements)
    elif isinstance(requirements, (list, tuple, set)):
        parse_fixed_container(requirements, label_hint="Requirement choice")
    elif isinstance(requirements, dict):
        for key in ("required_courses", "required", "fixed"):
            parse_fixed_container(requirements.get(key), label_hint=f"{key.replace('_', ' ').title()} choice")

        courses_value = requirements.get("courses")
        if isinstance(courses_value, (list, tuple, set)):
            if requirements.get("count") is not None or requirements.get("choose") is not None:
                add_choice_group(
                    {
                        "courses": list(courses_value),
                        "count": requirements.get("count") if requirements.get("count") is not None else requirements.get("choose"),
                        "label": requirements.get("label") or requirements.get("name"),
                    },
                    label_hint="Requirement choice",
                )
            else:
                parse_fixed_container(courses_value, label_hint="Requirement choice")
        elif isinstance(courses_value, str):
            add_fixed(courses_value)

        for key in ("choices", "choice_groups", "groups", "options"):
            value = requirements.get(key)
            if value is None:
                continue
            if isinstance(value, (list, tuple, set)):
                if value and all(isinstance(item, str) for item in value):
                    add_choice_group(
                        {
                            "courses": list(value),
                            "count": 1,
                            "label": f"{key.replace('_', ' ').title()}",
                        },
                        label_hint="Requirement choice",
                    )
                else:
                    for item in value:
                        add_choice_group(item, label_hint=f"{key.replace('_', ' ').title()}")
            else:
                add_choice_group(value, label_hint=f"{key.replace('_', ' ').title()}")

        req_type = str(requirements.get("type") or "").strip().lower()
        is_group_like = req_type in {"choice", "or", "select", "one_of", "one-of", "group"}
        if requirements.get("choices") is not None or requirements.get("choice_groups") is not None:
            is_group_like = True
        if requirements.get("groups") is not None or requirements.get("options") is not None:
            is_group_like = True
        if (requirements.get("count") is not None or requirements.get("choose") is not None) and requirements.get("courses") is not None:
            is_group_like = True
        if is_group_like:
            add_choice_group(requirements, label_hint="Requirement choice")

    return set(fixed), choice_groups


def _choice_group_deficits(
    catalog: Dict,
    minor_name: str,
    taken: Set[str],
    choice_groups: List[Dict[str, object]],
) -> Tuple[int, List[str], int, Set[str]]:
    slots: List[Dict[str, object]] = []
    for idx, group in enumerate(choice_groups, start=1):
        courses = {
            _normalize_course_code(code)
            for code in group.get("courses", []) or []
            if isinstance(code, str)
        }
        if not courses:
            continue
        count = _coerce_positive_int(group.get("count"), default=1)
        count = max(1, min(count, len(courses)))
        label = str(group.get("label") or f"{minor_name} choice group {idx}").strip()
        for slot_idx in range(count):
            slot_label = label if count == 1 else f"{label} ({slot_idx + 1})"
            slots.append({
                "courses": courses,
                "label": slot_label,
            })

    if not slots:
        return 0, [], 0, set()

    slot_match: Dict[int, str] = {}
    course_match: Dict[str, int] = {}

    def dfs(slot_index: int, seen_courses: Set[str]) -> bool:
        slot_courses = slots[slot_index].get("courses", set())
        for course in sorted(slot_courses & taken):
            if course in seen_courses:
                continue
            seen_courses.add(course)
            owner = course_match.get(course)
            if owner is None or dfs(owner, seen_courses):
                course_match[course] = slot_index
                slot_match[slot_index] = course
                return True
        return False

    for slot_index in range(len(slots)):
        dfs(slot_index, set())

    missing_labels: List[str] = []
    missing_credits = 0
    for slot_index, slot in enumerate(slots):
        if slot_index in slot_match:
            continue
        missing_labels.append(str(slot.get("label") or f"{minor_name} choice group"))
        slot_courses = slot.get("courses", set())
        missing_credits += min((_course_credits(catalog, c) for c in slot_courses), default=3)

    return len(missing_labels), missing_labels, int(missing_credits), set(course_match.keys())


def _choice_count_hint_from_text(text: str) -> int | None:
    if not isinstance(text, str) or not text.strip():
        return None
    normalized = text.strip().lower()
    word_to_num = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
    }

    def to_num(token: str) -> int | None:
        token = token.strip().lower()
        if token.isdigit():
            val = int(token)
            return val if val > 0 else None
        return word_to_num.get(token)

    # choose/select one|two|...
    m = re.search(r"\b(?:choose|select)\s+(\d+|one|two|three|four|five|six)\b", normalized)
    if m:
        return to_num(m.group(1))

    # one|two|... of the following
    m = re.search(r"\b(\d+|one|two|three|four|five|six)\s+of\b", normalized)
    if m:
        return to_num(m.group(1))

    if re.search(r"\bone of\b", normalized):
        return 1
    return None


def _extract_required_from_program_choice_blocks(
    minor_data: Dict,
    catalog_courses: Set[str],
) -> Tuple[Set[str], List[Dict[str, object]]]:
    fixed_required: Set[str] = set()
    choice_groups: List[Dict[str, object]] = []
    choice_signatures: Set[Tuple[Tuple[str, ...], int]] = set()

    blocks = minor_data.get("elective_requirements") or []
    if not isinstance(blocks, list):
        return fixed_required, choice_groups

    for raw_block in blocks:
        if not isinstance(raw_block, dict):
            continue
        label = str(raw_block.get("label") or "").strip().lower()
        is_total = bool(raw_block.get("is_total"))
        looks_like_program_choice = ("program choice" in label) or ("choice" in label and not is_total)
        if not looks_like_program_choice:
            continue

        allowed_set = {
            _normalize_course_code(code)
            for code in (raw_block.get("allowed_courses") or [])
            if isinstance(code, str)
        } & set(catalog_courses)
        if not allowed_set:
            continue

        rule_text = str(raw_block.get("rule_text") or "")
        rule_text_norm = re.sub(r"\s+", " ", rule_text).strip().lower()
        placement_test_block = "placement test" in rule_text_norm

        grouped_codes: Set[str] = set()
        # Prefer explicit OR groups from prose (e.g., BUS 2060 OR ENT 2061).
        or_groups: List[Set[str]] = []
        seen_or_signatures: Set[Tuple[str, ...]] = set()

        if not placement_test_block:
            # Adjacent-code OR detection avoids over-grouping unrelated codes.
            text_upper = rule_text.upper()
            code_matches = list(COURSE_CODE_PATTERN.finditer(text_upper))
            for idx in range(len(code_matches) - 1):
                left = _normalize_course_code(code_matches[idx].group(0))
                right = _normalize_course_code(code_matches[idx + 1].group(0))
                if left not in allowed_set or right not in allowed_set or left == right:
                    continue
                between = text_upper[code_matches[idx].end() : code_matches[idx + 1].start()]
                if len(between) > 120:
                    continue
                if re.search(r"\bOR\b|/", between):
                    signature = tuple(sorted({left, right}))
                    if signature in seen_or_signatures:
                        continue
                    seen_or_signatures.add(signature)
                    or_groups.append(set(signature))

            # Conservative fallback for slash/or chains.
            if not or_groups:
                for raw_group in _extract_or_prereq_groups(rule_text):
                    group = {
                        _normalize_course_code(code)
                        for code in raw_group
                        if isinstance(code, str)
                    } & allowed_set
                    if len(group) < 2:
                        continue
                    signature = tuple(sorted(group))
                    if signature in seen_or_signatures:
                        continue
                    seen_or_signatures.add(signature)
                    or_groups.append(set(group))

        for group in or_groups:
            if len(group) < 2:
                continue
            count = 1
            signature = (tuple(sorted(group)), count)
            if signature not in choice_signatures:
                choice_signatures.add(signature)
                choice_groups.append({
                    "courses": sorted(group),
                    "count": count,
                    "label": " / ".join(sorted(group)),
                })
            grouped_codes |= group

        # If no explicit OR groups, allow "one of / choose N" semantics over entire block.
        if not grouped_codes:
            courses_required_num = _parse_number(raw_block.get("courses_required"))
            choose_count: int | None = None
            if courses_required_num is not None and courses_required_num > 0:
                rounded = round(courses_required_num)
                if abs(courses_required_num - rounded) < 1e-9:
                    choose_count = int(rounded)
            if choose_count is None:
                choose_count = _choice_count_hint_from_text(rule_text)
            if choose_count is None and len(allowed_set) == 2 and rule_text_norm.startswith("or "):
                choose_count = 1

            if choose_count is not None and 0 < choose_count < len(allowed_set):
                signature = (tuple(sorted(allowed_set)), int(choose_count))
                if signature not in choice_signatures:
                    choice_signatures.add(signature)
                    choice_groups.append({
                        "courses": sorted(allowed_set),
                        "count": int(choose_count),
                        "label": str(raw_block.get("label") or "Program Choice"),
                    })
                grouped_codes = set(allowed_set)

        fixed_required |= (allowed_set - grouped_codes)

    return fixed_required, choice_groups


def _expand_wildcard_allowed_courses(catalog_courses: Set[str], rule_text: str) -> Set[str]:
    if not isinstance(rule_text, str) or not rule_text.strip():
        return set()

    expanded: Set[str] = set()
    # Examples:
    #   ENG 3[4-9]NN -> ENG 3400-3999
    #   BUS 4[4-9]NN -> BUS 4400-4999
    wildcard_pattern = re.compile(r"\b([A-Z]{2,4})\s*([0-9])\[(\d)-(\d)\]NN\b", re.IGNORECASE)
    matches = wildcard_pattern.findall(rule_text.upper())
    if not matches:
        return expanded

    for subject, thousand, low, high in matches:
        low_digit = int(low)
        high_digit = int(high)
        if high_digit < low_digit:
            low_digit, high_digit = high_digit, low_digit
        for code in catalog_courses:
            parts = str(code).split()
            if len(parts) != 2:
                continue
            prefix, number = parts
            if prefix != subject:
                continue
            if not number.isdigit() or len(number) < 4:
                continue
            if number[0] != thousand:
                continue
            second_digit = int(number[1])
            if low_digit <= second_digit <= high_digit:
                expanded.add(code)
    return expanded


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_gened_label(label: str) -> str:
    cleaned = _normalize_space(label or "")
    if not cleaned:
        return ""
    cleaned = GEN_ED_TAG_RE.sub("", cleaned)
    cleaned = _normalize_space(cleaned).strip(" -:;,")
    return cleaned


def _catalog_gened_lookup(catalog: Dict) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    gen_ed = catalog.get("gen_ed", {}) or {}
    for source in (gen_ed.get("rules", {}), gen_ed.get("categories", {})):
        if not isinstance(source, dict):
            continue
        for category in source.keys():
            if not isinstance(category, str):
                continue
            normalized = _normalize_gened_label(category).lower()
            if normalized and normalized not in lookup:
                lookup[normalized] = category
    return lookup


def _canonicalize_gened_labels(catalog: Dict, labels: List[str]) -> List[str]:
    lookup = _catalog_gened_lookup(catalog)
    normalized_lookup = {v: v for v in lookup.values()}
    out: List[str] = []
    for raw in labels:
        cleaned = _normalize_gened_label(raw)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered == "historical analysis":
            if "Historical Sources" in normalized_lookup:
                out.append("Historical Sources")
            if "Historical Research" in normalized_lookup:
                out.append("Historical Research")
            continue
        if lowered == "textual analysis":
            if "Principles of Textual Analysis" in normalized_lookup:
                out.append("Principles of Textual Analysis")
            if "Case Studies in Textual Analysis" in normalized_lookup:
                out.append("Case Studies in Textual Analysis")
            continue
        out.append(lookup.get(lowered, cleaned))
    return list(dict.fromkeys(out))


def _coerce_gened_labels(raw: object) -> List[str]:
    labels: List[str] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                labels.extend([part for part in GEN_ED_SPLIT_RE.split(item) if isinstance(part, str)])
    elif isinstance(raw, str):
        parts = GEN_ED_SPLIT_RE.split(raw)
        labels.extend([p for p in parts if isinstance(p, str)])
    return list(dict.fromkeys([_normalize_space(label) for label in labels if _normalize_space(label)]))

def _is_free_elective(code: str) -> bool:
    return code.startswith("FREE_ELECTIVE") or code.startswith("FREE ELECTIVE")

def _make_warning(warning_type: str, course: str | None = None, **fields: object) -> Dict:
    warning: Dict[str, object] = {"type": warning_type, "course": course}
    for key, value in fields.items():
        if value is not None:
            warning[key] = value
    return warning

def _free_elective_code_generator(used_codes: Set[str]):
    counter = 1

    def next_code() -> str:
        nonlocal counter
        while True:
            code = f"FREE ELECTIVE {counter}"
            counter += 1
            if code not in used_codes:
                used_codes.add(code)
                return code

    return next_code


def _course_instance_id(term: str, code: str, seed: str | None = None) -> str:
    name = f"{term}|{code}"
    if seed:
        name = f"{name}|{seed}"
    return str(uuid.uuid5(INSTANCE_ID_NAMESPACE, name))


def _ensure_instance_ids(semester_plan: List[Dict]) -> None:
    used_instance_ids: Set[str] = set()

    def next_instance_id(term_name: str, code: str) -> str:
        suffix = 0
        while True:
            seed = None if suffix == 0 else f"dup-{suffix}"
            candidate = _course_instance_id(term_name, code, seed)
            if candidate not in used_instance_ids:
                return candidate
            suffix += 1

    for term in semester_plan:
        term_name = term.get("term", "")
        for course in term.get("courses", []) or []:
            if not isinstance(course, dict):
                continue
            code = str(course.get("code", ""))
            raw_instance_id = course.get("instance_id")
            instance_id = None
            if isinstance(raw_instance_id, str) and raw_instance_id.strip():
                instance_id = raw_instance_id.strip()
            if instance_id and instance_id not in used_instance_ids:
                used_instance_ids.add(instance_id)
                course["instance_id"] = instance_id
                continue
            course["instance_id"] = next_instance_id(term_name, code)
            used_instance_ids.add(course["instance_id"])



def _planned_course_credits(catalog: Dict, course: Dict | str) -> int:
    if isinstance(course, dict):
        raw_credits = course.get("credits")
        if isinstance(raw_credits, (int, float)) and math.isfinite(raw_credits):
            return int(raw_credits)
        if isinstance(raw_credits, str):
            text = raw_credits.strip()
            if re.fullmatch(r"-?\d+", text):
                return int(text)
        code = course.get("code")
        if isinstance(code, str) and code:
            return 3 if _is_free_elective(code) else _course_credits(catalog, code)
        return 0
    if isinstance(course, str) and course:
        return 3 if _is_free_elective(course) else _course_credits(catalog, course)
    return 0


def _dedupe_semester_plan(
    catalog: Dict,
    semester_plan: List[Dict],
    completed_courses: Set[str] | None = None,
) -> List[Dict]:
    # Keep all occurrences (retakes included); sanitize entries and recompute term credits.
    if not semester_plan:
        return semester_plan
    ordered_terms = sorted(semester_plan, key=lambda t: _term_label_index(t.get("term", "")))
    for term in ordered_terms:
        courses = term.get("courses", []) or []
        normalized_courses: List[Dict] = []
        for course in courses:
            if not isinstance(course, dict):
                continue
            code = course.get("code")
            if not isinstance(code, str) or not code:
                continue
            normalized_courses.append(course)
        term["courses"] = normalized_courses
        term["credits"] = sum(
            _planned_course_credits(catalog, c)
            for c in normalized_courses
        )
    return semester_plan


def _resolve_active_attempt_instance_ids(
    semester_plan: List[Dict],
    completed_courses: Set[str] | None = None,
) -> Tuple[Set[str], Set[str], Set[str]]:
    """Resolve latest active attempt instance IDs by course code.

    Tie-breaker for attempts in the same term:
    1) COMPLETED > IN_PROGRESS > PLANNED (if status exists)
    2) later appearance order in the semester_plan traversal
    """
    status_rank = {"PLANNED": 0, "IN_PROGRESS": 1, "COMPLETED": 2}
    attempts_by_code: Dict[str, List[Dict[str, Any]]] = {}
    sequence = 0
    for term in semester_plan or []:
        term_label = term.get("term", "")
        term_idx = _term_label_index(term_label) if isinstance(term_label, str) else 999999
        for course in term.get("courses", []) or []:
            if not isinstance(course, dict):
                continue
            code = course.get("code")
            if not isinstance(code, str) or not code:
                continue
            normalized_code = _normalize_course_code(code)
            if not normalized_code or _is_free_elective(normalized_code):
                continue
            instance_id = course.get("instance_id")
            if not isinstance(instance_id, str) or not instance_id.strip():
                continue
            raw_status = course.get("status")
            normalized_status = ""
            if isinstance(raw_status, str):
                normalized_status = raw_status.strip().replace("-", "_").upper()
            attempts_by_code.setdefault(normalized_code, []).append(
                {
                    "instance_id": instance_id.strip(),
                    "term_idx": term_idx,
                    "status_rank": status_rank.get(normalized_status, 0),
                    "seq": sequence,
                }
            )
            sequence += 1

    completed_normalized = {
        _normalize_course_code(code)
        for code in (completed_courses or set())
        if isinstance(code, str)
    }
    active_instance_ids: Set[str] = set()
    replaced_instance_ids: Set[str] = set()
    duplicate_context_codes: Set[str] = set()

    for code, attempts in attempts_by_code.items():
        if not attempts:
            continue
        has_duplicate_context = len(attempts) > 1 or code in completed_normalized
        if has_duplicate_context:
            duplicate_context_codes.add(code)
        ordered = sorted(
            attempts,
            key=lambda entry: (entry["term_idx"], entry["status_rank"], entry["seq"]),
        )
        active = ordered[-1]
        active_instance_ids.add(active["instance_id"])
        if len(ordered) > 1:
            for prior in ordered[:-1]:
                replaced_instance_ids.add(prior["instance_id"])

    return active_instance_ids, replaced_instance_ids, duplicate_context_codes


def _apply_latest_attempt_credit_rule(
    catalog: Dict,
    semester_plan: List[Dict],
    completed_courses: Set[str] | None = None,
) -> None:
    if not semester_plan:
        return
    _ensure_instance_ids(semester_plan)
    active_ids, replaced_ids, duplicate_context_codes = _resolve_active_attempt_instance_ids(
        semester_plan,
        completed_courses=completed_courses,
    )

    for term in semester_plan:
        normalized_courses: List[Dict[str, Any]] = []
        for course in term.get("courses", []) or []:
            if not isinstance(course, dict):
                continue
            code = course.get("code")
            instance_id = course.get("instance_id")
            if not isinstance(code, str) or not code:
                normalized_courses.append(course)
                continue
            normalized_code = _normalize_course_code(code)
            if not normalized_code or _is_free_elective(normalized_code):
                normalized_courses.append(course)
                continue
            if not isinstance(instance_id, str) or not instance_id.strip():
                normalized_courses.append(course)
                continue
            normalized_instance_id = instance_id.strip()
            tags = course.get("tags")
            clean_tags = [tag for tag in tags if isinstance(tag, str)] if isinstance(tags, list) else []
            clean_tags = [tag for tag in clean_tags if tag != "Previous Attempt"]

            if normalized_instance_id in replaced_ids:
                course["credits"] = 0
                course["satisfies"] = []
                course["is_retake"] = True
                if "Previous Attempt" not in clean_tags:
                    clean_tags.append("Previous Attempt")
                course["tags"] = clean_tags
                normalized_courses.append(course)
                continue

            if (
                normalized_instance_id in active_ids
                and normalized_code in duplicate_context_codes
            ):
                course["credits"] = _course_credits(catalog, normalized_code)
                course["is_retake"] = True
                if "Retake" not in clean_tags:
                    clean_tags.append("Retake")
                course["tags"] = clean_tags
                normalized_courses.append(course)
                continue

            course["tags"] = clean_tags
            normalized_courses.append(course)

        term["courses"] = normalized_courses
        term["credits"] = sum(_planned_course_credits(catalog, c) for c in normalized_courses)

def _catalog_courses(catalog: Dict) -> Set[str]:
    return {code for code in catalog.get("courses", {}).keys() if isinstance(code, str)}


def _excel_catalog_by_code(catalog: Dict) -> Dict[str, Dict[str, Any]]:
    excel_catalog = catalog.get("excel_catalog") or catalog.get("excel_course_catalog") or {}
    by_code = excel_catalog.get("by_code") if isinstance(excel_catalog, dict) else {}
    if not isinstance(by_code, dict):
        return {}
    return by_code


def _planning_course_pool(catalog: Dict) -> Set[str]:
    courses = set(_catalog_courses(catalog))
    # Opt into Excel-only GenEd courses only when a paired Excel catalog is present.
    # This prevents synthetic unit-test catalogs from being polluted by global Excel state.
    if not catalog.get("excel_catalog"):
        return courses

    categories: Set[str] = set()
    gen_ed = catalog.get("gen_ed", {}) or {}
    if isinstance(gen_ed.get("rules"), dict):
        categories.update([c for c in gen_ed["rules"].keys() if isinstance(c, str)])
    if isinstance(gen_ed.get("categories"), dict):
        categories.update([c for c in gen_ed["categories"].keys() if isinstance(c, str)])

    excel_codes = set(_excel_catalog_by_code(catalog).keys())
    if not excel_codes:
        excel_codes = get_excel_course_codes()

    for code in excel_codes:
        if not isinstance(code, str):
            continue
        cats = _course_gened_categories(catalog, code)
        if not cats:
            continue
        if categories and not set(cats).intersection(categories):
            continue
        courses.add(code)
    return courses


def _course_entry(catalog: Dict, code: str) -> Dict:
    return catalog.get("courses", {}).get(code, {})


def _excel_course_record(catalog: Dict, code: str) -> Dict:
    course = _excel_catalog_by_code(catalog).get(code)
    if isinstance(course, dict):
        return course
    course = get_excel_course_record(code)
    if isinstance(course, dict):
        return course
    return {}


def _course_is_wic(catalog: Dict, code: str) -> bool:
    excel_wic = _excel_course_record(catalog, code).get("wic")
    if isinstance(excel_wic, bool):
        return excel_wic
    meta = catalog.get("course_meta", {}).get(code, {})
    wic = meta.get("wic")
    if isinstance(wic, bool):
        return wic
    if isinstance(wic, str):
        text = wic.strip().lower()
        return "writing intensive course" in text or text == "wic"
    return False


def _planned_course_tags(catalog: Dict, code: str) -> List[str]:
    tags = ["Planned"]
    if _course_is_wic(catalog, code):
        tags.append("Writing Intensive Course")
    return tags


def _course_name(catalog: Dict, code: str) -> str:
    excel_title = _excel_course_record(catalog, code).get("title")
    if isinstance(excel_title, str) and excel_title:
        return excel_title
    meta_title = catalog.get("course_meta", {}).get(code, {}).get("title")
    if meta_title:
        return meta_title
    return _course_entry(catalog, code).get("name") or code


def _course_credits(catalog: Dict, code: str) -> int:
    excel_credits = _excel_course_record(catalog, code).get("credits")
    if isinstance(excel_credits, (int, float)) and excel_credits > 0:
        return int(excel_credits)
    meta = catalog.get("course_meta", {}).get(code, {})
    credits = meta.get("credits")
    if isinstance(credits, int) and credits > 0:
        return credits
    entry = _course_entry(catalog, code)
    credits = entry.get("credits")
    if isinstance(credits, int) and credits > 0:
        return credits
    return 3


def _course_gened_categories(catalog: Dict, code: str) -> List[str]:
    excel = _excel_course_record(catalog, code)
    excel_tags = _coerce_gened_labels(excel.get("gen_ed_tags"))
    if excel_tags:
        return _canonicalize_gened_labels(catalog, excel_tags)

    entry = _course_entry(catalog, code)
    fallback_labels: List[str] = []

    cats = _coerce_gened_labels(entry.get("gen_ed"))
    if cats:
        fallback_labels.extend(cats)

    meta = catalog.get("course_meta", {}).get(code, {})
    meta_tags = _coerce_gened_labels(meta.get("gen_ed_tags"))
    if meta_tags:
        fallback_labels.extend(meta_tags)
    meta_gened = _coerce_gened_labels(meta.get("gen_ed"))
    if meta_gened:
        fallback_labels.extend(meta_gened)

    return _canonicalize_gened_labels(catalog, fallback_labels)


def _course_prereqs(catalog: Dict, code: str) -> Set[str]:
    meta = catalog.get("course_meta", {}).get(code, {})
    prereqs = meta.get("prereq_codes")
    if not isinstance(prereqs, list):
        prereqs = meta.get("prereqs") or []
    return set([_normalize_course_code(c) for c in prereqs if isinstance(c, str)])


def _extract_or_prereq_groups(prereq_text: str) -> List[List[str]]:
    if not prereq_text:
        return []
    text = prereq_text.upper()
    cleaned = re.sub(r"[()\\[\\]{}]", " ", text)
    cleaned = cleaned.replace("/", " OR ")
    tokens = re.findall(r"[A-Z]{2,4}\s?\d{3,4}|OR", cleaned)
    groups: List[List[str]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok != "OR" and i + 1 < len(tokens) and tokens[i + 1] == "OR":
            group = [tok]
            i += 1
            while i + 1 < len(tokens) and tokens[i] == "OR" and tokens[i + 1] != "OR":
                group.append(tokens[i + 1])
                i += 2
            if len(group) >= 2:
                groups.append(group)
            continue
        i += 1
    if not groups:
        for match in PREREQ_OR_GROUP_RE.finditer(text):
            codes = [_normalize_course_code(c) for c in COURSE_CODE_PATTERN.findall(match.group(0))]
            unique = [c for c in codes if isinstance(c, str)]
            if len(unique) >= 2:
                groups.append(unique)
    return groups


def _dedupe_course_codes(codes: List[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for raw in codes:
        if not isinstance(raw, str):
            continue
        code = _normalize_course_code(raw)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _prereq_block_signature(block: Dict[str, object]) -> str:
    block_type = str(block.get("type") or "").lower()
    if block_type == "course":
        return f"course:{block.get('code')}"
    if block_type == "or":
        courses = block.get("courses")
        if isinstance(courses, list):
            normalized = _dedupe_course_codes([c for c in courses if isinstance(c, str)])
            return "or:" + "|".join(normalized)
        items = block.get("items")
        if isinstance(items, list):
            return "or-items:" + "|".join(_prereq_block_signature(i) for i in items if isinstance(i, dict))
    if block_type == "and":
        items = block.get("items")
        if isinstance(items, list):
            return "and:" + "|".join(_prereq_block_signature(i) for i in items if isinstance(i, dict))
    return "unknown"


def _normalize_prereq_block(raw: object) -> Dict[str, object] | None:
    if isinstance(raw, str):
        code = _normalize_course_code(raw)
        if code:
            return {"type": "course", "code": code}
        return None

    if not isinstance(raw, dict):
        return None

    block_type = str(raw.get("type") or "").strip().lower()
    if block_type == "course":
        code = raw.get("code")
        if isinstance(code, str) and code.strip():
            return {"type": "course", "code": _normalize_course_code(code)}
        return None

    if block_type == "and":
        items_raw = raw.get("items")
        if not isinstance(items_raw, list):
            items_raw = raw.get("blocks") if isinstance(raw.get("blocks"), list) else []
        items: List[Dict[str, object]] = []
        for item in items_raw:
            normalized = _normalize_prereq_block(item)
            if normalized:
                items.append(normalized)
        if not items:
            return None
        return {"type": "and", "items": items}

    if block_type == "or":
        options: List[Dict[str, object]] = []
        courses = raw.get("courses")
        if isinstance(courses, list):
            for course in courses:
                normalized = _normalize_prereq_block(course)
                if normalized:
                    options.append(normalized)
        for key in ("items", "blocks", "options", "choices"):
            values = raw.get(key)
            if not isinstance(values, list):
                continue
            for value in values:
                normalized = _normalize_prereq_block(value)
                if normalized:
                    options.append(normalized)
        if not options:
            return None
        deduped: List[Dict[str, object]] = []
        seen: Set[str] = set()
        for option in options:
            signature = _prereq_block_signature(option)
            if signature in seen:
                continue
            seen.add(signature)
            deduped.append(option)
        if deduped and all(str(opt.get("type")) == "course" for opt in deduped):
            courses_only = [str(opt.get("code")) for opt in deduped if isinstance(opt.get("code"), str)]
            return {"type": "or", "courses": _dedupe_course_codes(courses_only)}
        return {"type": "or", "items": deduped}

    return None


def _normalize_prereq_blocks(raw: object) -> List[Dict[str, object]]:
    if isinstance(raw, list):
        out: List[Dict[str, object]] = []
        for item in raw:
            normalized = _normalize_prereq_block(item)
            if normalized:
                out.append(normalized)
        return out

    normalized = _normalize_prereq_block(raw)
    if not normalized:
        return []
    if str(normalized.get("type")) == "and":
        items = normalized.get("items")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return [normalized]


def _prereq_block_to_expr_node(block: Dict[str, object]) -> object | None:
    block_type = str(block.get("type") or "").lower()
    if block_type == "course":
        code = block.get("code")
        if isinstance(code, str) and code.strip():
            return _normalize_course_code(code)
        return None
    if block_type == "or":
        items: List[object] = []
        for raw in block.get("courses", []) or []:
            if isinstance(raw, str) and raw.strip():
                items.append(_normalize_course_code(raw))
        for raw in block.get("items", []) or []:
            if not isinstance(raw, dict):
                continue
            expr = _prereq_block_to_expr_node(raw)
            if expr is not None:
                items.append(expr)
        if not items:
            return None
        return {"or": items}
    if block_type == "and":
        items: List[object] = []
        for raw in block.get("items", []) or []:
            if not isinstance(raw, dict):
                continue
            expr = _prereq_block_to_expr_node(raw)
            if expr is not None:
                items.append(expr)
        if not items:
            return None
        return {"and": items}
    return None


def _prereq_blocks_to_expr(blocks: List[Dict[str, object]]) -> Dict[str, List[object]] | None:
    items: List[object] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        expr = _prereq_block_to_expr_node(block)
        if expr is not None:
            items.append(expr)
    if not items:
        return None
    return {"and": items}


def _normalize_prereq_expr_node(raw: object) -> object | None:
    if isinstance(raw, str):
        code = _normalize_course_code(raw)
        return code if code else None

    if isinstance(raw, list):
        items: List[object] = []
        for item in raw:
            normalized = _normalize_prereq_expr_node(item)
            if normalized is not None:
                items.append(normalized)
        if not items:
            return None
        return {"and": items}

    if not isinstance(raw, dict):
        return None

    if "and" in raw:
        values = raw.get("and")
        if not isinstance(values, list):
            return None
        items: List[object] = []
        for value in values:
            normalized = _normalize_prereq_expr_node(value)
            if normalized is not None:
                items.append(normalized)
        if not items:
            return None
        return {"and": items}

    if "or" in raw:
        values = raw.get("or")
        if not isinstance(values, list):
            return None
        items: List[object] = []
        for value in values:
            normalized = _normalize_prereq_expr_node(value)
            if normalized is not None:
                items.append(normalized)
        if not items:
            return None
        return {"or": items}

    block = _normalize_prereq_block(raw)
    if block:
        return _prereq_block_to_expr_node(block)
    return None


def _normalize_prereq_expr(raw: object) -> Dict[str, List[object]] | None:
    normalized = _normalize_prereq_expr_node(raw)
    if normalized is None:
        return None
    if isinstance(normalized, dict) and "and" in normalized and isinstance(normalized.get("and"), list):
        return {"and": normalized["and"]}
    return {"and": [normalized]}


def _prereq_expr_node_to_block(node: object) -> Dict[str, object] | None:
    if isinstance(node, str):
        code = _normalize_course_code(node)
        if code:
            return {"type": "course", "code": code}
        return None
    if not isinstance(node, dict):
        return None
    if "and" in node:
        values = node.get("and")
        if not isinstance(values, list):
            return None
        items: List[Dict[str, object]] = []
        for value in values:
            block = _prereq_expr_node_to_block(value)
            if block:
                items.append(block)
        if not items:
            return None
        return {"type": "and", "items": items}
    if "or" in node:
        values = node.get("or")
        if not isinstance(values, list):
            return None
        items: List[Dict[str, object]] = []
        for value in values:
            block = _prereq_expr_node_to_block(value)
            if block:
                items.append(block)
        if not items:
            return None
        if all(str(item.get("type")) == "course" for item in items):
            courses = [
                str(item.get("code"))
                for item in items
                if isinstance(item.get("code"), str)
            ]
            return {"type": "or", "courses": _dedupe_course_codes(courses)}
        return {"type": "or", "items": items}
    return None


def _prereq_expr_to_blocks(expr: object) -> List[Dict[str, object]]:
    normalized = _normalize_prereq_expr(expr)
    if not normalized:
        return []
    values = normalized.get("and", [])
    blocks: List[Dict[str, object]] = []
    for value in values:
        block = _prereq_expr_node_to_block(value)
        if not block:
            continue
        if str(block.get("type")) == "and" and isinstance(block.get("items"), list):
            blocks.extend([item for item in block["items"] if isinstance(item, dict)])
            continue
        blocks.append(block)
    return blocks


def _fallback_prereq_blocks_from_flat(prereq_codes: Set[str], prereq_text: str) -> List[Dict[str, object]]:
    if not prereq_codes:
        return []

    raw_groups = _extract_or_prereq_groups(prereq_text or "")
    or_groups: List[List[str]] = []
    grouped_codes: Set[str] = set()
    for group in raw_groups:
        filtered = _dedupe_course_codes([
            _normalize_course_code(c)
            for c in group
            if _normalize_course_code(c) in prereq_codes
        ])
        if len(filtered) >= 2:
            or_groups.append(filtered)
            grouped_codes.update(filtered)

    blocks: List[Dict[str, object]] = []
    for req in sorted(set(prereq_codes) - grouped_codes):
        blocks.append({"type": "course", "code": req})
    for group in or_groups:
        blocks.append({"type": "or", "courses": group})

    if blocks:
        return blocks
    return [{"type": "course", "code": req} for req in sorted(prereq_codes)]


def _course_prereq_expr(catalog: Dict, code: str) -> Dict[str, List[object]] | None:
    meta = catalog.get("course_meta", {}).get(code, {})

    normalized_expr = _normalize_prereq_expr(meta.get("prereq_expr"))
    if normalized_expr:
        return normalized_expr

    raw_blocks = meta.get("prereq_blocks")
    if isinstance(raw_blocks, (list, dict)):
        normalized_blocks = _normalize_prereq_blocks(raw_blocks)
        if normalized_blocks:
            expr = _prereq_blocks_to_expr(normalized_blocks)
            if expr:
                return expr

    raw_prereqs = meta.get("prereqs")
    if isinstance(raw_prereqs, (list, dict)):
        if isinstance(raw_prereqs, dict) or any(isinstance(item, dict) for item in raw_prereqs):
            normalized_blocks = _normalize_prereq_blocks(raw_prereqs)
            if normalized_blocks:
                expr = _prereq_blocks_to_expr(normalized_blocks)
                if expr:
                    return expr

    prereq_codes = _course_prereqs(catalog, code)
    if not prereq_codes:
        return None

    fallback_blocks = _fallback_prereq_blocks_from_flat(prereq_codes, meta.get("prereq_text") or "")
    return _prereq_blocks_to_expr(fallback_blocks)


def _course_prereq_blocks(catalog: Dict, code: str) -> List[Dict[str, object]]:
    expr = _course_prereq_expr(catalog, code)
    if not expr:
        return []
    return _prereq_expr_to_blocks(expr)


def _prereq_block_options(block: Dict[str, object]) -> List[Dict[str, object]]:
    options: List[Dict[str, object]] = []
    courses = block.get("courses")
    if isinstance(courses, list):
        for course in courses:
            normalized = _normalize_prereq_block(course)
            if normalized:
                options.append(normalized)
    for key in ("items", "blocks", "options", "choices"):
        values = block.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            normalized = _normalize_prereq_block(value)
            if normalized:
                options.append(normalized)
    deduped: List[Dict[str, object]] = []
    seen: Set[str] = set()
    for option in options:
        signature = _prereq_block_signature(option)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(option)
    return deduped


def _prereq_block_items(block: Dict[str, object]) -> List[Dict[str, object]]:
    items_raw = block.get("items")
    if not isinstance(items_raw, list):
        items_raw = block.get("blocks") if isinstance(block.get("blocks"), list) else []
    items: List[Dict[str, object]] = []
    for item in items_raw:
        normalized = _normalize_prereq_block(item)
        if normalized:
            items.append(normalized)
    return items


def _prereq_block_label(block: Dict[str, object]) -> str:
    block_type = str(block.get("type") or "").lower()
    if block_type == "course":
        code = block.get("code")
        return code if isinstance(code, str) else ""
    if block_type == "or":
        labels = [_prereq_block_label(option) for option in _prereq_block_options(block)]
        labels = [label for label in labels if label]
        if labels:
            return " OR ".join(labels)
    if block_type == "and":
        labels = [_prereq_block_label(item) for item in _prereq_block_items(block)]
        labels = [label for label in labels if label]
        if labels:
            return " AND ".join(labels)
    return ""


def _prereq_expr_label(expr: object) -> str:
    normalized = _normalize_prereq_expr_node(expr)
    if normalized is None:
        return ""
    if isinstance(normalized, str):
        return normalized
    if isinstance(normalized, dict):
        if "or" in normalized and isinstance(normalized.get("or"), list):
            labels = [_prereq_expr_label(item) for item in normalized["or"]]
            labels = [label for label in labels if label]
            if labels:
                return " OR ".join(labels)
        if "and" in normalized and isinstance(normalized.get("and"), list):
            labels = [_prereq_expr_label(item) for item in normalized["and"]]
            labels = [label for label in labels if label]
            if labels:
                return " AND ".join(labels)
    return ""


def _prereq_expr_satisfied(expr: object, completed_and_prior_planned_codes: Set[str]) -> bool:
    normalized = _normalize_prereq_expr_node(expr)
    if normalized is None:
        return True
    if isinstance(normalized, str):
        return normalized in completed_and_prior_planned_codes
    if isinstance(normalized, dict):
        if "and" in normalized and isinstance(normalized.get("and"), list):
            items = normalized["and"]
            if not items:
                return True
            return all(
                _prereq_expr_satisfied(item, completed_and_prior_planned_codes)
                for item in items
            )
        if "or" in normalized and isinstance(normalized.get("or"), list):
            items = normalized["or"]
            if not items:
                return True
            return any(
                _prereq_expr_satisfied(item, completed_and_prior_planned_codes)
                for item in items
            )
    return True


def _missing_prereq_items(expr: object, completed_and_prior_planned_codes: Set[str]) -> List[str]:
    normalized = _normalize_prereq_expr_node(expr)
    if normalized is None or _prereq_expr_satisfied(normalized, completed_and_prior_planned_codes):
        return []
    if isinstance(normalized, str):
        return [normalized]
    if isinstance(normalized, dict):
        if "and" in normalized and isinstance(normalized.get("and"), list):
            missing: List[str] = []
            for item in normalized["and"]:
                missing.extend(_missing_prereq_items(item, completed_and_prior_planned_codes))
            return missing
        if "or" in normalized and isinstance(normalized.get("or"), list):
            label = _prereq_expr_label(normalized)
            return [label] if label else []
    return []


def _prereq_block_satisfied(block: Dict[str, object], satisfied: Set[str]) -> bool:
    block_type = str(block.get("type") or "").lower()
    if block_type == "course":
        code = block.get("code")
        return isinstance(code, str) and code in satisfied
    if block_type == "or":
        options = _prereq_block_options(block)
        if not options:
            return True
        return any(_prereq_block_satisfied(option, satisfied) for option in options)
    if block_type == "and":
        items = _prereq_block_items(block)
        if not items:
            return True
        return all(_prereq_block_satisfied(item, satisfied) for item in items)
    return True


def _unmet_prereq_labels_for_block(block: Dict[str, object], satisfied: Set[str]) -> List[str]:
    if _prereq_block_satisfied(block, satisfied):
        return []

    block_type = str(block.get("type") or "").lower()
    if block_type == "course":
        code = block.get("code")
        return [code] if isinstance(code, str) else []
    if block_type == "and":
        unmet: List[str] = []
        for item in _prereq_block_items(block):
            unmet.extend(_unmet_prereq_labels_for_block(item, satisfied))
        return unmet
    if block_type == "or":
        label = _prereq_block_label(block)
        return [label] if label else []
    return []


def _prereqs_satisfied(
    catalog: Dict,
    code: str,
    satisfied: Set[str],
) -> bool:
    expr = _course_prereq_expr(catalog, code)
    return _prereq_expr_satisfied(expr, satisfied)


def _unmet_prereq_labels(
    catalog: Dict,
    code: str,
    satisfied: Set[str],
) -> List[str]:
    expr = _course_prereq_expr(catalog, code)
    labels = _missing_prereq_items(expr, satisfied)
    deduped: List[str] = []
    seen: Set[str] = set()
    for label in labels:
        if label in seen:
            continue
        seen.add(label)
        deduped.append(label)
    return deduped


def _prereq_option_rank(
    block: Dict[str, object],
    needed: Set[str],
    prefer_set: Set[str],
    completed: Set[str],
) -> Tuple[int, int, str]:
    not_preferred = len([c for c in needed if c not in prefer_set and c not in completed])
    return (not_preferred, len(needed), _prereq_block_label(block))


def _prereq_block_course_codes(block: Dict[str, object]) -> Set[str]:
    block_type = str(block.get("type") or "").lower()
    if block_type == "course":
        code = block.get("code")
        if isinstance(code, str) and code:
            return {code}
        return set()
    if block_type == "or":
        codes: Set[str] = set()
        for option in _prereq_block_options(block):
            codes |= _prereq_block_course_codes(option)
        return codes
    if block_type == "and":
        codes: Set[str] = set()
        for item in _prereq_block_items(block):
            codes |= _prereq_block_course_codes(item)
        return codes
    return set()


def _minimal_prereqs_for_block(
    catalog: Dict,
    block: Dict[str, object],
    prefer_set: Set[str],
    completed: Set[str],
    memo: Dict[str, Set[str]],
    visiting: Set[str],
    catalog_courses: Set[str],
) -> Set[str]:
    block_type = str(block.get("type") or "").lower()
    if block_type == "course":
        code = block.get("code")
        if not isinstance(code, str):
            return set()
        if code in completed or code in visiting or code not in catalog_courses:
            return set()
        needed = {code}
        needed |= _minimal_prereqs_for_course(catalog, code, prefer_set, completed, memo, visiting)
        return needed

    if block_type == "and":
        needed: Set[str] = set()
        for item in _prereq_block_items(block):
            needed |= _minimal_prereqs_for_block(
                catalog, item, prefer_set, completed, memo, visiting, catalog_courses
            )
        return needed

    if block_type == "or":
        options = _prereq_block_options(block)
        if not options:
            return set()
        # Prefer an OR branch already present in the student's program track,
        # so we do not recommend adding the alternative unnecessarily.
        preferred_courses = set(prefer_set) | set(completed)
        preferred_options = [
            option for option in options
            if _prereq_block_course_codes(option).intersection(preferred_courses)
        ]
        if preferred_options:
            options = preferred_options
        best_needed: Set[str] | None = None
        best_rank: Tuple[int, int, str] | None = None
        for option in options:
            option_needed = _minimal_prereqs_for_block(
                catalog, option, prefer_set, completed, memo, visiting, catalog_courses
            )
            rank = _prereq_option_rank(option, option_needed, prefer_set, completed)
            if best_rank is None or rank < best_rank:
                best_rank = rank
                best_needed = option_needed
        return set(best_needed or set())

    return set()


def _minimal_prereqs_for_course(
    catalog: Dict,
    code: str,
    prefer_set: Set[str],
    completed: Set[str],
    memo: Dict[str, Set[str]],
    visiting: Set[str],
) -> Set[str]:
    if code in memo:
        return memo[code]
    if code in visiting:
        return set()
    visiting.add(code)

    catalog_courses = _catalog_courses(catalog)
    result: Set[str] = set()
    for block in _course_prereq_blocks(catalog, code):
        result |= _minimal_prereqs_for_block(
            catalog, block, prefer_set, completed, memo, visiting, catalog_courses
        )

    visiting.remove(code)
    memo[code] = result
    return result


def _expand_prereqs_minimal(
    catalog: Dict,
    course_codes: Set[str],
    completed: Set[str],
    prefer_set: Set[str],
) -> Set[str]:
    memo: Dict[str, Set[str]] = {}
    visiting: Set[str] = set()
    needed: Set[str] = set()
    for code in sorted(course_codes):
        needed |= _minimal_prereqs_for_course(catalog, code, prefer_set, completed, memo, visiting)
    # Remove already satisfied or directly required courses
    return needed - set(course_codes) - set(completed)

def _expand_prereqs(
    catalog: Dict,
    course_codes: List[str],
    completed: Set[str],
    prefer_set: Set[str] | None = None,
) -> Set[str]:
    prefer = set(prefer_set or course_codes)
    return _expand_prereqs_minimal(catalog, set(course_codes), completed, prefer)

def _completed_gened_categories(catalog: Dict, completed: Set[str]) -> Set[str]:
    cats: Set[str] = set()
    for code in completed:
        cats.update(_course_gened_categories(catalog, code))
    return cats


def _current_start_term() -> Tuple[str, int]:
    today = datetime.date.today()
    if 1 <= today.month <= 5:
        return "Spring", today.year
    if 6 <= today.month <= 8:
        return "Fall", today.year
    return "Fall", today.year


def _term_index(season: str, year: int) -> int:
    season_val = 1 if season == "Fall" else 0
    return year * 2 + season_val


def _normalize_start_term(start_term_season: str | None, start_term_year: int | None) -> Tuple[str, int]:
    current_season, current_year = _current_start_term()
    if start_term_season in {"Fall", "Spring"} and isinstance(start_term_year, int) and start_term_year > 0:
        if _term_index(start_term_season, start_term_year) < _term_index(current_season, current_year):
            return current_season, current_year
        return start_term_season, start_term_year
    return current_season, current_year


def _terms_completed_from_start(start_term_season: str | None, start_term_year: int | None) -> int:
    if start_term_season not in {"Fall", "Spring"} or not isinstance(start_term_year, int) or start_term_year <= 0:
        return 0
    current_season, current_year = _current_start_term()
    return max(0, _term_index(current_season, current_year) - _term_index(start_term_season, start_term_year))


def _term_name(idx: int, base_season: str, base_year: int) -> str:
    if base_season not in {"Fall", "Spring"}:
        base_season = "Fall"
    season = base_season if idx % 2 == 0 else ("Spring" if base_season == "Fall" else "Fall")
    if base_season == "Fall":
        year = base_year + (idx // 2) + (1 if idx % 2 == 1 else 0)
    else:
        year = base_year + (idx // 2)
    return f"{season} {year}"


def _term_label_index(term: str) -> int:
    m = re.match(r"^(Spring|Fall)\s+(\d{4})$", term)
    if not m:
        return 999999
    season_val = 1 if m.group(1) == "Fall" else 0
    return int(m.group(2)) * 2 + season_val


def _normalize_term_label(term: str | None) -> str | None:
    if not isinstance(term, str):
        return None
    label = term.strip()
    if _term_label_index(label) == 999999:
        return None
    return label


def _compute_in_progress_occupied_credits(
    catalog: Dict,
    in_progress_courses: Set[str],
    in_progress_terms: Dict[str, str] | None,
    current_term_label: str | None,
) -> Dict[str, int]:
    if not in_progress_courses:
        return {}

    normalized_terms: Dict[str, str] = {}
    for raw_code, raw_term in (in_progress_terms or {}).items():
        if not isinstance(raw_code, str):
            continue
        term_label = _normalize_term_label(raw_term)
        if not term_label:
            continue
        normalized_terms[_normalize_course_code(raw_code)] = term_label

    fallback_term = _normalize_term_label(current_term_label)
    if not fallback_term:
        season, year = _current_start_term()
        fallback_term = f"{season} {year}"

    occupied: Dict[str, int] = {}
    for code in in_progress_courses:
        term_label = normalized_terms.get(code, fallback_term)
        occupied[term_label] = occupied.get(term_label, 0) + _course_credits(catalog, code)
    return occupied


def _completed_credit_total(catalog: Dict, completed: Set[str]) -> int:
    total = 0
    base_catalog_courses = _catalog_courses(catalog)
    for code in completed:
        if _is_free_elective(code):
            total += 3
            continue
        if code not in base_catalog_courses and not _excel_course_record(catalog, code):
            continue
        total += _course_credits(catalog, code)
    return total


def _min_term_index_for_course(
    catalog: Dict,
    code: str,
    completed_credits: int | None = None,
) -> int:
    meta = catalog.get("course_meta", {}).get(code, {})
    text = (meta.get("prereq_text") or "").lower()
    min_term = 0

    if "junior standing" in text:
        if completed_credits is None or completed_credits < 60:
            min_term = max(min_term, 4)
    if "sophomore standing" in text:
        if completed_credits is None or completed_credits < 30:
            min_term = max(min_term, 2)

    m = re.match(r"^[A-Z]{3}\s?(\d{3,4})$", code)
    if m:
        level = int(m.group(1))
        if level >= 4000:
            min_term = max(min_term, 4)
        elif level >= 3000:
            min_term = max(min_term, 2)
    return min_term


def _min_term_reasons(catalog: Dict, code: str) -> List[str]:
    meta = catalog.get("course_meta", {}).get(code, {})
    text = (meta.get("prereq_text") or "").lower()
    reasons: List[str] = []
    if "junior standing" in text:
        reasons.append("junior standing")
    if "sophomore standing" in text:
        reasons.append("sophomore standing")
    m = re.match(r"^[A-Z]{3}\s?(\d{3,4})$", code)
    if m:
        level = int(m.group(1))
        if level >= 4000:
            reasons.append("4000-level course")
        elif level >= 3000:
            reasons.append("3000-level course")
    return reasons


def build_requirement_slots(catalog: Dict, majors: List[str], minors: List[str]) -> Dict:
    slots: List[Dict] = []
    by_id: Dict[str, Dict] = {}
    slot_id = 0
    catalog_courses = _catalog_courses(catalog)

    def add_slot(slot: Dict) -> None:
        nonlocal slot_id
        slot["id"] = f"S{slot_id:04d}"
        slot_id += 1
        slots.append(slot)
        by_id[slot["id"]] = slot

    def add_fixed_course(course: str, program_name: str, program_type: str) -> None:
        if course not in catalog_courses:
            return
        add_slot({
            "type": "fixed",
            "course": course,
            "owner": "program",
            "program": program_name,
            "program_type": program_type,
            "group_id": None,
            "label": f"{program_type.title()}: {program_name}",
        })

    def add_choice_group(courses: List[str], count: int, program_name: str, program_type: str, label: str) -> None:
        group_id = f"choice:{program_type}:{program_name}:{label}"
        filtered = [c for c in courses if c in catalog_courses]
        if not filtered or count <= 0:
            return
        usable_count = min(count, len(filtered))
        for _ in range(max(0, usable_count)):
            add_slot({
                "type": "choice",
                "courses": filtered,
                "count": count,
                "owner": "program",
                "program": program_name,
                "program_type": program_type,
                "group_id": group_id,
                "label": label,
            })

    def parse_requirements(program_data: Dict) -> Tuple[List[str], List[Dict]]:
        reqs = program_data.get("required_courses")
        if reqs is None:
            reqs = program_data.get("requirements")
        fixed: List[str] = []
        choices: List[Dict] = []
        if isinstance(reqs, list):
            fixed = [r for r in reqs if isinstance(r, str)]
        elif isinstance(reqs, dict):
            fixed = [r for r in reqs.get("required_courses", []) if isinstance(r, str)]
            if not fixed:
                fixed = [r for r in reqs.get("fixed", []) if isinstance(r, str)]
                fixed += [r for r in reqs.get("required", []) if isinstance(r, str)]
                fixed += [r for r in reqs.get("courses", []) if isinstance(r, str)]
        fixed = [
            code for code in (
                _normalize_course_code(raw_code)
                for raw_code in fixed
                if isinstance(raw_code, str)
            )
            if code
        ]
        fixed = list(dict.fromkeys(fixed))
        return fixed, choices

    def merge_program_choice_requirements(
        program_name: str,
        program_data: Dict,
        fixed: List[str],
        choices: List[Dict],
    ) -> Tuple[List[str], List[Dict]]:
        if _is_fine_arts_minor(program_name):
            return fixed, choices

        block_fixed_required, block_choice_groups = _extract_required_from_program_choice_blocks(
            minor_data=program_data,
            catalog_courses=catalog_courses,
        )
        fixed_seen = {
            _normalize_course_code(code)
            for code in fixed
            if isinstance(code, str)
        }
        merged_fixed = list(fixed)
        for course in sorted(block_fixed_required):
            normalized = _normalize_course_code(course)
            if normalized in fixed_seen:
                continue
            merged_fixed.append(normalized)
            fixed_seen.add(normalized)

        merged_choices = list(choices)
        if block_choice_groups:
            existing_choice_signatures = {
                (
                    tuple(
                        sorted(
                            _normalize_course_code(code)
                            for code in (group.get("courses", []) or [])
                            if isinstance(code, str)
                        )
                    ),
                    int(_coerce_positive_int(group.get("count"), default=1)),
                )
                for group in merged_choices
                if isinstance(group, dict)
            }
            for group in block_choice_groups:
                if not isinstance(group, dict):
                    continue
                signature = (
                    tuple(
                        sorted(
                            _normalize_course_code(code)
                            for code in (group.get("courses", []) or [])
                            if isinstance(code, str)
                        )
                    ),
                    int(_coerce_positive_int(group.get("count"), default=1)),
                )
                if not signature[0] or signature in existing_choice_signatures:
                    continue
                existing_choice_signatures.add(signature)
                merged_choices.append(group)

        return merged_fixed, merged_choices

    for major in majors:
        data = catalog.get("majors", {}).get(major, {})
        fixed, choices = parse_requirements(data)
        fixed, choices = merge_program_choice_requirements(major, data, fixed, choices)
        for course in fixed:
            add_fixed_course(course, major, "major")
        for group in choices:
            add_choice_group(group["courses"], group["count"], major, "major", group["label"])

    for minor in minors:
        data = catalog.get("minors", {}).get(minor, {})
        fixed, choices = parse_requirements(data)
        fixed, choices = merge_program_choice_requirements(minor, data, fixed, choices)

        # Economics minor special case from catalog:
        # Required: ECO 1001, ECO 1002, and (ECO 3001 OR ECO 3002).
        # If the parser/structure lists both ECO 3001 and ECO 3002 as fixed required,
        # convert them into a single OR choice group so we don't schedule both.
        if minor.strip().lower() == "economics":
            or_group = {"ECO 3001", "ECO 3002"}
            fixed_set = set(fixed)
            if fixed_set & or_group:
                fixed = [c for c in fixed if c not in or_group]
                add_choice_group(sorted(or_group), 1, minor, "minor", "Economics minor: ECO 3001 OR ECO 3002")

        if _is_cs_minor(minor):
            for course in sorted(CS_MINOR_REQUIRED_COURSES):
                normalized = _normalize_course_code(course)
                if normalized in catalog_courses and normalized not in fixed:
                    fixed.append(normalized)
            existing_choice_signatures = {
                (
                    tuple(
                        sorted(
                            _normalize_course_code(code)
                            for code in (group.get("courses", []) or [])
                            if isinstance(code, str)
                        )
                    ),
                    int(_coerce_positive_int(group.get("count"), default=1)),
                )
                for group in choices
                if isinstance(group, dict)
            }
            for label, group_codes in CS_MINOR_GROUPS.items():
                normalized_group_codes = sorted(
                    {
                        _normalize_course_code(code)
                        for code in group_codes
                        if _normalize_course_code(code) in catalog_courses
                    }
                )
                signature = (tuple(normalized_group_codes), 1)
                if not normalized_group_codes or signature in existing_choice_signatures:
                    continue
                existing_choice_signatures.add(signature)
                choices.append({
                    "courses": normalized_group_codes,
                    "count": 1,
                    "label": f"Computer Science group ({label})",
                })

        if _is_fine_arts_minor(minor):
            existing_choice_signatures = {
                (
                    tuple(
                        sorted(
                            _normalize_course_code(code)
                            for code in (group.get("courses", []) or [])
                            if isinstance(code, str)
                        )
                    ),
                    int(_coerce_positive_int(group.get("count"), default=1)),
                )
                for group in choices
                if isinstance(group, dict)
            }
            fine_arts_groups = [
                ("Fine Arts group A", sorted(c for c in FINE_ARTS_GROUP_A if c in catalog_courses), 1),
                ("Fine Arts group B", sorted(c for c in FINE_ARTS_GROUP_B if c in catalog_courses), 1),
                (
                    "Fine Arts group C",
                    sorted(c for c in FINE_ARTS_GROUP_C if c in catalog_courses),
                    max(1, int(math.ceil(FINE_ARTS_GROUP_C_CREDITS_REQUIRED / 3.0))),
                ),
            ]
            for label, group_codes, count in fine_arts_groups:
                signature = (tuple(group_codes), int(count))
                if not group_codes or signature in existing_choice_signatures:
                    continue
                existing_choice_signatures.add(signature)
                choices.append({
                    "courses": group_codes,
                    "count": int(count),
                    "label": label,
                })

        for course in fixed:
            add_fixed_course(course, minor, "minor")
        for group in choices:
            add_choice_group(group["courses"], group["count"], minor, "minor", group["label"])

    for course in sorted(set(catalog.get("foundation_courses", []) or [])):
        if course not in catalog_courses:
            continue
        add_slot({
            "type": "fixed",
            "course": course,
            "owner": "foundation",
            "program": None,
            "program_type": None,
            "group_id": None,
            "label": "Foundation",
        })

    gen_ed_rules = catalog.get("gen_ed", {}).get("rules", {})
    for category in sorted(gen_ed_rules.keys()):
        count = int(gen_ed_rules[category])
        group_id = f"gened:{category}"
        for _ in range(max(0, count)):
            add_slot({
                "type": "gened",
                "category": category,
                "owner": "gened",
                "group_id": group_id,
                "label": f"GenEd: {category}",
            })

    return {
        "slots": slots,
        "by_id": by_id,
    }


def compute_course_satisfies(catalog: Dict, course_code: str, slots: Dict) -> Set[str]:
    out: Set[str] = set()
    code = _normalize_course_code(course_code)
    course_gened = set(_course_gened_categories(catalog, code))
    for slot in slots.get("slots", []):
        if slot["type"] == "fixed" and slot.get("course") == code:
            out.add(slot["id"])
        elif slot["type"] == "choice" and code in slot.get("courses", []):
            out.add(slot["id"])
        elif slot["type"] == "gened" and slot.get("category") in course_gened:
            out.add(slot["id"])
    return out


def _select_one_per_group(slot_ids: Set[str], slots_by_id: Dict[str, Dict], covered: Set[str]) -> Set[str]:
    chosen: Set[str] = set()
    used_groups: Set[str] = set()
    for sid in sorted(slot_ids):
        if sid in covered:
            continue
        slot = slots_by_id[sid]
        group = slot.get("group_id") or sid
        if group in used_groups:
            continue
        used_groups.add(group)
        chosen.add(sid)
    return chosen


def _slot_label(slot: Dict) -> str:
    if slot["type"] == "gened":
        return f"GenEd: {slot.get('category')}"
    if slot["type"] in {"fixed", "choice"}:
        if slot.get("owner") == "foundation":
            return "Foundation"
        program = slot.get("program")
        program_type = slot.get("program_type")
        if program and program_type:
            if slot["type"] == "choice":
                return f"{program_type.title()}: {program} (choice)"
            return f"{program_type.title()}: {program}"
    return "Requirement"


def _assign_course_to_slots(
    course_code: str,
    catalog: Dict,
    slots: Dict,
    covered: Set[str],
    slot_assignment: Dict[str, str],
    course_assignments: Dict[str, Set[str]],
) -> Set[str]:
    possible = compute_course_satisfies(catalog, course_code, slots)
    chosen = _select_one_per_group(possible, slots["by_id"], covered)
    if not chosen:
        return set()
    for sid in chosen:
        slot_assignment[sid] = course_code
    covered.update(chosen)
    course_assignments.setdefault(course_code, set()).update(chosen)
    return chosen


def _pick_best_course(
    catalog: Dict,
    slots: Dict,
    covered: Set[str],
    selected: Set[str],
    completed: Set[str],
    prefer_high_credits: bool,
    eligible_only: Set[str] | None = None,
    retake_courses: Set[str] | None = None,
) -> Tuple[str | None, Set[str]]:
    best_code = None
    best_slots: Set[str] = set()
    best_score = None
    catalog_courses = _planning_course_pool(catalog)
    retakes = set(retake_courses or set())
    candidates = sorted(catalog_courses)
    for code in candidates:
        if code in selected or (code in completed and code not in retakes):
            continue
        if eligible_only is not None and code not in eligible_only:
            continue
        possible = compute_course_satisfies(catalog, code, slots)
        possible -= covered
        chosen = _select_one_per_group(possible, slots["by_id"], covered)
        if not chosen:
            continue
        covers_program = any(slots["by_id"][sid]["owner"] == "program" for sid in chosen)
        covers_gened = any(slots["by_id"][sid]["owner"] == "gened" for sid in chosen)
        multipurpose = 1 if (covers_program and covers_gened) else 0
        credit_score = _course_credits(catalog, code) if prefer_high_credits else 0
        score = (len(chosen), multipurpose, credit_score)
        if best_score is None or score > best_score:
            best_score = score
            best_code = code
            best_slots = chosen
    return best_code, best_slots


def select_courses_for_slots(
    catalog: Dict,
    slots: Dict,
    completed_courses: Set[str],
    retake_courses: Set[str] | None = None,
) -> Dict:
    completed = set([_normalize_course_code(c) for c in completed_courses])
    planning_course_pool = _planning_course_pool(catalog)
    completed &= planning_course_pool
    retakes = {
        _normalize_course_code(c)
        for c in (retake_courses or set())
        if isinstance(c, str)
    }
    retakes &= planning_course_pool

    covered: Set[str] = set()
    slot_assignment: Dict[str, str] = {}
    course_assignments: Dict[str, Set[str]] = {}

    for code in sorted(completed):
        _assign_course_to_slots(code, catalog, slots, covered, slot_assignment, course_assignments)

    fixed_courses = sorted({
        slot.get("course") for slot in slots.get("slots", [])
        if slot.get("type") == "fixed" and slot.get("course")
    })

    selected: Set[str] = set()
    for code in fixed_courses:
        if code in completed and code not in retakes:
            continue
        selected.add(code)
        _assign_course_to_slots(code, catalog, slots, covered, slot_assignment, course_assignments)

    all_slot_ids = {slot["id"] for slot in slots.get("slots", [])}
    remaining_slots = set(all_slot_ids - covered)

    while remaining_slots:
        code, chosen = _pick_best_course(
            catalog=catalog,
            slots=slots,
            covered=covered,
            selected=selected,
            completed=completed,
            prefer_high_credits=False,
            retake_courses=retakes,
        )
        if not code:
            break
        selected.add(code)
        _assign_course_to_slots(code, catalog, slots, covered, slot_assignment, course_assignments)
        remaining_slots = set(all_slot_ids - covered)

    return {
        "selected_courses": sorted(selected),
        "covered_slots": covered,
        "slot_assignment": slot_assignment,
        "course_assignments": course_assignments,
        "remaining_slots": remaining_slots,
        "completed_courses": completed,
        "retake_courses": retakes,
    }


def _build_direct_reason_map(slots: Dict, course_assignments: Dict[str, Set[str]]) -> Dict[str, str]:
    reasons: Dict[str, str] = {}
    for code, sids in course_assignments.items():
        has_major = any(
            slots["by_id"][sid].get("owner") == "program"
            and slots["by_id"][sid].get("program_type") == "major"
            for sid in sids
        )
        has_minor = any(
            slots["by_id"][sid].get("owner") == "program"
            and slots["by_id"][sid].get("program_type") == "minor"
            for sid in sids
        )
        has_gened = any(
            slots["by_id"][sid].get("owner") in {"gened", "foundation"}
            for sid in sids
        )
        if has_major:
            reasons[code] = SOURCE_REASON_MAJOR
        elif has_minor:
            reasons[code] = SOURCE_REASON_MINOR
        elif has_gened:
            reasons[code] = SOURCE_REASON_GENED
    return reasons


def _course_level(code: str) -> int:
    m = re.match(r"^[A-Z]{3}\s?(\d{3,4})$", code)
    if not m:
        return 9999
    return int(m.group(1))


def _eligible_for_term(
    catalog: Dict,
    code: str,
    term_idx: int,
    completed: Set[str],
    completed_gened: Set[str] | None = None,
) -> bool:
    completed_credits = _completed_credit_total(catalog, completed)
    if _min_term_index_for_course(catalog, code, completed_credits) > term_idx:
        return False
    if not _prereqs_satisfied(catalog, code, completed):
        return False
    if completed_gened is None:
        completed_gened = _completed_gened_categories(catalog, completed)
    course_cats = set(_course_gened_categories(catalog, code))
    for cat in course_cats:
        prereq_cats = CATEGORY_PREREQS.get(cat)
        if prereq_cats and not prereq_cats.issubset(completed_gened):
            return False
    return True


def _schedule_courses(
    catalog: Dict,
    selected_courses: List[str],
    course_types: Dict[str, str],
    completed_courses: Set[str],
    retake_courses: Set[str] | None,
    base_season: str,
    base_year: int,
    max_terms: int,
    min_credits: int,
    target_credits: int,
    max_credits: int,
    occupied_credits_by_term: Dict[str, int] | None = None,
) -> List[Dict]:
    completed_for_skip = set(completed_courses) - set(retake_courses or set())
    remaining = set(selected_courses) - completed_for_skip
    plan: List[Dict] = []
    completed = set(completed_courses)
    type_order = {"FOUNDATION": 0, "PROGRAM": 1, "GENED": 2, "FREE": 3, "FREE_ELECTIVE": 3}
    occupied = occupied_credits_by_term or {}

    for term_idx in range(max_terms):
        term_name = _term_name(term_idx, base_season, base_year)
        occupied_credits = max(0, int(occupied.get(term_name, 0) or 0))
        available_max = max(0, max_credits - occupied_credits)
        available_target = min(target_credits, available_max)
        term_courses: List[str] = []
        term_credits = 0

        completed_gened = _completed_gened_categories(catalog, completed)
        available = [
            c for c in remaining
            if _eligible_for_term(catalog, c, term_idx, completed, completed_gened)
        ]
        available.sort(key=lambda c: (type_order.get(course_types.get(c, "FREE"), 9), _course_level(c), c))

        for code in available:
            credits = _course_credits(catalog, code)
            if term_credits + credits > available_max:
                continue
            term_courses.append(code)
            term_credits += credits
            if term_credits >= available_target:
                break

        for code in term_courses:
            remaining.discard(code)
            completed.add(code)

        plan.append({"term": term_name, "courses": term_courses, "credits": term_credits})
        if not remaining:
            break

    return plan


def balance_term_credits(
    plan: List[Dict],
    catalog: Dict,
    slots: Dict,
    completed_courses: Set[str],
    selected_courses: Set[str],
    covered_slots: Set[str],
    slot_assignment: Dict[str, str],
    course_assignments: Dict[str, Set[str]],
    min_credits: int = 14,
    target_credits: int = 16,
    max_credits: int = 16,
    occupied_credits_by_term: Dict[str, int] | None = None,
) -> List[Dict]:
    used_codes = {
        code
        for term in plan
        for code in (term.get("courses", []) or [])
        if isinstance(code, str)
    }
    next_free_code = _free_elective_code_generator(used_codes)
    occupied = occupied_credits_by_term or {}

    def term_credit_bounds(term_obj: Dict) -> Tuple[int, int]:
        term_label = term_obj.get("term", "")
        occupied_credits = max(0, int(occupied.get(term_label, 0) or 0))
        available_min = max(0, min_credits - occupied_credits)
        available_max = max(0, max_credits - occupied_credits)
        return available_min, available_max

    def add_free_elective(term: Dict) -> bool:
        _, available_max = term_credit_bounds(term)
        if term["credits"] + 3 > available_max:
            return False
        code = next_free_code()
        term["courses"].append(code)
        term["credits"] += 3
        return True

    # Normalize credits
    for term in plan:
        term["credits"] = sum(_course_credits(catalog, c) if not _is_free_elective(c) else 3 for c in term["courses"])

    # Pull-forward pass
    for i in range(len(plan)):
        term = plan[i]
        available_min, available_max = term_credit_bounds(term)
        completed = set(completed_courses)
        for prev in plan[:i]:
            completed |= set(prev["courses"])
        completed_gened = _completed_gened_categories(catalog, completed)
        while term["credits"] < available_min:
            moved = False
            for j in range(i + 1, len(plan)):
                future = plan[j]
                for code in list(future["courses"]):
                    if _is_free_elective(code):
                        continue
                    if not _eligible_for_term(catalog, code, i, completed, completed_gened):
                        continue
                    credits = _course_credits(catalog, code)
                    if term["credits"] + credits > available_max:
                        continue
                    future["courses"].remove(code)
                    future["credits"] -= credits
                    term["courses"].append(code)
                    term["credits"] += credits
                    completed.add(code)
                    moved = True
                    break
                if moved:
                    break
            if not moved:
                break

    # Fill pass
    all_slot_ids = {slot["id"] for slot in slots.get("slots", [])}
    remaining_slots = set(all_slot_ids - covered_slots)
    for i in range(len(plan)):
        term = plan[i]
        available_min, _ = term_credit_bounds(term)
        completed = set(completed_courses)
        for prev in plan[:i]:
            completed |= set(prev["courses"])
        completed_gened = _completed_gened_categories(catalog, completed)

        while term["credits"] < available_min:
            # Do not auto-pick real courses as fillers; use placeholders only.
            if not add_free_elective(term):
                break

    return plan


def generate_semester_plan(
    catalog: Dict,
    slots: Dict,
    completed_courses: Set[str],
    retake_courses: Set[str] | None,
    start_term: Tuple[str, int],
    max_terms: int = 8,
    min_credits: int = 14,
    target_credits: int = 16,
    max_credits: int = 16,
    fill_underloaded_terms: bool = True,
    occupied_credits_by_term: Dict[str, int] | None = None,
) -> Dict:
    selection = select_courses_for_slots(
        catalog,
        slots,
        completed_courses,
        retake_courses=retake_courses,
    )
    direct_reason_map = _build_direct_reason_map(slots, selection["course_assignments"])
    direct_required_all = set(selection.get("course_assignments", {}).keys())
    completed_for_skip = set(selection["completed_courses"]) - set(selection.get("retake_courses", set()))
    direct_required_pending = set(selection["selected_courses"]) - completed_for_skip
    prereq_courses = _expand_prereqs(
        catalog,
        sorted(direct_required_pending),
        selection["completed_courses"],
        prefer_set=direct_required_all,
    )
    allowed_auto = set(direct_required_pending) | set(prereq_courses)
    selected_courses = sorted(allowed_auto)
    selection["selected_courses"] = selected_courses
    selection["direct_required"] = set(direct_required_pending)
    selection["needed_prereqs"] = set(prereq_courses)
    selection["allowed_auto"] = set(allowed_auto)
    selection["direct_reason_map"] = direct_reason_map
    selection["completed_for_skip"] = set(completed_for_skip)
    base_season, base_year = start_term

    course_types = {}
    for code, sids in selection["course_assignments"].items():
        if code not in direct_required_pending:
            continue
        if any(slots["by_id"][sid]["owner"] == "foundation" for sid in sids):
            course_types[code] = "FOUNDATION"
        elif any(slots["by_id"][sid]["owner"] == "program" for sid in sids):
            course_types[code] = "PROGRAM"
        elif any(slots["by_id"][sid]["owner"] == "gened" for sid in sids):
            course_types[code] = "GENED"
        else:
            course_types[code] = "FREE"
    for code in prereq_courses:
        course_types.setdefault(code, "FREE")

    plan = _schedule_courses(
        catalog=catalog,
        selected_courses=selected_courses,
        course_types=course_types,
        completed_courses=selection["completed_courses"],
        retake_courses=set(selection.get("retake_courses", set())),
        base_season=base_season,
        base_year=base_year,
        max_terms=max_terms,
        min_credits=min_credits,
        target_credits=target_credits,
        max_credits=max_credits,
        occupied_credits_by_term=occupied_credits_by_term,
    )

    if fill_underloaded_terms:
        plan = balance_term_credits(
            plan=plan,
            catalog=catalog,
            slots=slots,
            completed_courses=selection["completed_courses"],
            selected_courses=set(selected_courses),
            covered_slots=selection["covered_slots"],
            slot_assignment=selection["slot_assignment"],
            course_assignments=selection["course_assignments"],
            min_credits=min_credits,
            target_credits=target_credits,
            max_credits=max_credits,
            occupied_credits_by_term=occupied_credits_by_term,
        )

    return {
        "plan": plan,
        "selection": selection,
    }


def compute_minor_proximity(catalog: Dict, minor_name: str, completed_and_planned_program_courses: Set[str]) -> Tuple[int, List[str]]:
    # Keep the public proximity helper aligned with smart proximity semantics:
    # required courses + elective deficits + known OR requirement groups.
    return compute_minor_proximity_smart(
        catalog=catalog,
        minor_name=minor_name,
        completed_and_planned_courses=completed_and_planned_program_courses,
    )


def _infer_allowed_prefixes_for_minor_electives(minor_name: str, rule_text: str) -> List[str]:
    """Best-effort inference for elective rules like: 'Any other ECO courses.'

    Returns a list of subject prefixes (e.g., ["ECO"]) to treat as eligible.
    Conservative: if we can't infer, return [].
    """
    text = (rule_text or "").upper()
    prefixes: List[str] = []

    # Pattern like: "Any other POLS courses", "Any POLS courses", "Any other POLS course"
    m = re.search(r"\bANY\s+(?:OTHER\s+)?([A-Z]{2,4})\s+COURSE(?:S)?\b", text)
    if m:
        prefixes.append(m.group(1))

    # Pattern like: "Any other ECO" (without 'courses')
    if not prefixes:
        m2 = re.search(r"\bANY\s+(?:OTHER\s+)?([A-Z]{2,4})\b", text)
        if m2:
            prefixes.append(m2.group(1))

    # Fallback: if the minor name is the same as a known prefix alias (from excel_catalog), use it.
    if not prefixes:
        try:
            # PROGRAM_TAG_ALIASES maps program names to possible subject prefixes.
            from excel_catalog import PROGRAM_TAG_ALIASES
            for alias in (PROGRAM_TAG_ALIASES.get(minor_name, []) or []):
                a = str(alias).upper().strip()
                if 2 <= len(a) <= 4 and a.isalpha():
                    prefixes.append(a)
        except Exception:
            pass

    # De-dupe while preserving order
    seen: Set[str] = set()
    out: List[str] = []
    for p in prefixes:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _elective_block_rule_text(block: Dict[str, object]) -> str:
    text = block.get("rule_text")
    if isinstance(text, str):
        return text
    lines = block.get("rule_lines")
    if isinstance(lines, list):
        joined = " ".join(str(x) for x in lines if isinstance(x, str))
        return joined
    return ""


def _elective_block_is_cap(block: Dict[str, object]) -> bool:
    text = _elective_block_rule_text(block)
    return bool(ELECTIVE_CAP_RE.search(text or ""))


def _elective_block_is_level_constraint(block: Dict[str, object]) -> bool:
    allowed = block.get("allowed_courses") or []
    has_allowed = isinstance(allowed, list) and any(isinstance(x, str) and x.strip() for x in allowed)
    if has_allowed:
        return False
    text = _elective_block_rule_text(block)
    if not text:
        return False
    # Typical phrasing: "At least two ... must be at the 3000- or 4000-level".
    return bool(ELECTIVE_UPPER_LEVEL_RE.search(text))


def _is_upper_level_course(code: str) -> bool:
    level = _course_number(code)
    return level is not None and 3000 <= int(level) <= 4999


def _counted_credits_with_caps(
    catalog: Dict,
    taken: Set[str],
    cap_blocks: List[Dict[str, object]],
    required_exclusions: Set[str],
    allowed_predicate,
) -> int:
    """Compute elective credits counted toward the *total elective requirement* with cap constraints.

    Some minors include caps such as: "No more than three credit hours may be chosen out of the following".
    We count credits from capped subsets up to their cap; the rest of taken credits count normally.
    """
    taken_eligible = {c for c in taken if allowed_predicate(c) and c not in required_exclusions}
    if not taken_eligible:
        return 0

    counted = 0
    used_in_caps: Set[str] = set()
    for block in cap_blocks:
        cap_value = _parse_number(block.get("credits_required"))
        if cap_value is None or cap_value <= 0:
            continue
        rule_text = _elective_block_rule_text(block)
        allowed_set = {
            _normalize_course_code(code)
            for code in (block.get("allowed_courses") or [])
            if isinstance(code, str)
        }
        allowed_set |= _expand_wildcard_allowed_courses(_catalog_courses(catalog), rule_text)
        allowed_set &= _catalog_courses(catalog)
        prefix_fallback = [] if allowed_set else _infer_allowed_prefixes_for_minor_electives("", rule_text)

        def cap_allowed(code: str) -> bool:
            if code in allowed_set:
                return True
            for p in prefix_fallback:
                if code.startswith(p + " "):
                    return True
            return False

        subset = {c for c in taken_eligible if cap_allowed(c)}
        if not subset:
            continue
        earned = sum(_course_credits(catalog, c) for c in subset)
        counted += int(min(float(cap_value), float(earned)))
        used_in_caps |= subset

    # Remaining eligible courses not in any cap subset count fully.
    for code in (taken_eligible - used_in_caps):
        counted += int(_course_credits(catalog, code))
    return int(counted)


def _parse_sustainability_themes(rule_text: str, catalog_courses: Set[str]) -> Dict[str, Set[str]]:
    """Parse Sustainability Studies elective themes from block rule text.

    The catalog uses thematic headings followed by course lists. The parser does not always split
    these into separate elective blocks, so we recover themes by scanning for heading-like lines.
    """
    if not isinstance(rule_text, str) or not rule_text.strip():
        return {}
    lines = [ln.strip() for ln in str(rule_text).splitlines() if ln.strip()]
    if len(lines) <= 1:
        # Sometimes rule_text is space-joined; fall back to a best-effort split.
        lines = [ln.strip() for ln in re.split(r"\s{2,}|\n", str(rule_text)) if ln.strip()]

    themes: Dict[str, Set[str]] = {}
    current: str | None = None
    for ln in lines:
        # Heading heuristic: long-ish line with few course codes and looks like a title.
        codes = [_normalize_course_code(c) for c in COURSE_CODE_PATTERN.findall(ln.upper())]
        looks_heading = (
            len(codes) == 0
            and len(ln) >= 18
            and (":" in ln or "Perspective" in ln or "Foundations" in ln)
        )
        if looks_heading:
            current = _normalize_space(ln).rstrip(":")
            themes.setdefault(current, set())
            continue
        if current is None:
            continue
        for raw in codes:
            code = _normalize_course_code(raw)
            if code in catalog_courses:
                themes[current].add(code)

    # Keep only meaningful themes (>=2 courses listed)
    pruned = {k: v for k, v in themes.items() if len(v) >= 2}
    return pruned


def compute_minor_proximity_smart_details(
    catalog: Dict,
    minor_name: str,
    completed_and_planned_courses: Set[str],
) -> Tuple[int, List[str], int]:
    """Return (remaining_course_count, remaining_items_list, remaining_credits) for a minor.

    Smart proximity includes:
    - fixed required courses
    - structured required choice groups (choose N of options)
    - OR requirement fallback for known catalog quirks (Economics: ECO 3001 OR ECO 3002)
    - CS/COS minor group constraints (Foundations, Software Development, Advanced Topics)
    - elective requirement blocks (credits_required or courses_required)

    remaining_items_list can include placeholders like "ECO elective" to represent
    missing elective credits.
    """
    minor_data = catalog.get("minors", {}).get(minor_name, {}) or {}
    catalog_courses = _catalog_courses(catalog)
    taken = {
        _normalize_course_code(c)
        for c in completed_and_planned_courses
        if isinstance(c, str) and (not _is_free_elective(_normalize_course_code(c)))
    }
    taken &= catalog_courses

    # --- required courses ---
    required_set, choice_groups = _extract_minor_required_structure(
        minor_data=minor_data,
        catalog_courses=catalog_courses,
    )
    block_fixed_required, block_choice_groups = _extract_required_from_program_choice_blocks(
        minor_data=minor_data,
        catalog_courses=catalog_courses,
    )
    required_set |= set(block_fixed_required)
    if block_choice_groups:
        existing_choice_signatures = {
            (
                tuple(
                    sorted(
                        _normalize_course_code(code)
                        for code in (group.get("courses", []) or [])
                        if isinstance(code, str)
                    )
                ),
                int(_coerce_positive_int(group.get("count"), default=1)),
            )
            for group in choice_groups
            if isinstance(group, dict)
        }
        for group in block_choice_groups:
            if not isinstance(group, dict):
                continue
            signature = (
                tuple(
                    sorted(
                        _normalize_course_code(code)
                        for code in (group.get("courses", []) or [])
                        if isinstance(code, str)
                    )
                ),
                int(_coerce_positive_int(group.get("count"), default=1)),
            )
            if not signature[0]:
                continue
            if signature in existing_choice_signatures:
                continue
            existing_choice_signatures.add(signature)
            choice_groups.append(group)

    remaining_items: List[str] = []
    total_remaining_credits = 0
    remaining_required = set(required_set)
    required_exclusions = set(required_set)
    required_used_for_progress = {c for c in taken if c in required_set}

    # Computer Science minor core required course.
    if _is_cs_minor(minor_name):
        cs_required = {_normalize_course_code(c) for c in CS_MINOR_REQUIRED_COURSES}
        cs_required &= catalog_courses
        required_set |= cs_required
        remaining_required |= cs_required
        required_exclusions |= cs_required
        required_used_for_progress |= (taken & cs_required)
        if not cs_required:
            logging.warning("CS minor key '%s' matched but COS 1020 is missing from catalog courses.", minor_name)

    # Economics minor fallback: ECO 3001 OR ECO 3002 counts as ONE requirement.
    if _norm_minor_name(minor_name) == "economics":
        econ_required_core = {"ECO 1001", "ECO 1002"} & catalog_courses
        econ_or_group = {"ECO 3001", "ECO 3002"} & catalog_courses
        required_set |= econ_required_core
        remaining_required |= econ_required_core
        required_exclusions |= econ_required_core
        required_exclusions |= econ_or_group
        required_used_for_progress |= (taken & econ_required_core)
        if len(econ_or_group) >= 2:
            has_econ_choice_group = any(
                econ_or_group <= {
                    _normalize_course_code(code)
                    for code in (group.get("courses", []) or [])
                    if isinstance(code, str)
                }
                for group in choice_groups
            )
            if not has_econ_choice_group:
                choice_groups.append({
                    "courses": sorted(econ_or_group),
                    "count": 1,
                    "label": "ECO 3001 / ECO 3002",
                })
            remaining_required -= econ_or_group

    missing_fixed = sorted(remaining_required - taken)
    remaining_items.extend(missing_fixed)
    remaining_count = len(missing_fixed)
    total_remaining_credits += sum(_course_credits(catalog, c) for c in missing_fixed)
    required_used_for_progress |= (taken & remaining_required)

    apply_generic_choice_logic = not (
        _is_cs_minor(minor_name)
        or _is_creative_writing_minor(minor_name)
        or _is_fine_arts_minor(minor_name)
    )
    if apply_generic_choice_logic and choice_groups:
        choice_missing_count, choice_missing_items, choice_missing_credits, choice_used_courses = _choice_group_deficits(
            catalog=catalog,
            minor_name=minor_name,
            taken=taken,
            choice_groups=choice_groups,
        )
        if choice_missing_count > 0:
            remaining_count += int(choice_missing_count)
            remaining_items.extend(choice_missing_items)
            total_remaining_credits += int(choice_missing_credits)
        required_used_for_progress |= choice_used_courses

    # --- elective blocks ---
    # Exclude required courses from elective counts ("Any other ECO courses" etc.)
    required_all = set(required_exclusions) | set(required_used_for_progress)

    # Computer Science minor special handling:
    # - at least one course from each of 3 groups
    # - 15 elective credits from COS elective pool (excluding required courses)
    if _is_cs_minor(minor_name):
        cs_groups = {
            label: {c for c in codes if c in catalog_courses}
            for label, codes in CS_MINOR_GROUPS.items()
        }

        cs_allowed: Set[str] = set()
        for block in minor_data.get("elective_requirements", []) or []:
            if not isinstance(block, dict):
                continue
            for code in block.get("allowed_courses", []) or []:
                if isinstance(code, str):
                    normalized = _normalize_course_code(code)
                    if normalized in catalog_courses:
                        cs_allowed.add(normalized)
        for group_codes in cs_groups.values():
            cs_allowed |= group_codes

        if not any(cs_groups.values()) and not cs_allowed:
            logging.warning(
                "CS minor key '%s' matched but no CS group/elective course mapping was found in catalog.",
                minor_name,
            )

        elective_taken = {c for c in taken if c in cs_allowed and c not in required_all}

        for label, group_codes in cs_groups.items():
            if not group_codes:
                continue
            if not (taken & group_codes):
                remaining_count += 1
                remaining_items.append(f"CS elective ({label})")
                total_remaining_credits += min((_course_credits(catalog, c) for c in group_codes), default=3)

        earned = sum(_course_credits(catalog, c) for c in elective_taken)
        credits_deficit = max(0, CS_MINOR_ELECTIVE_CREDITS_REQUIRED - earned)
        if credits_deficit > 0:
            est_courses = (credits_deficit + 2) // 3
            remaining_count += int(est_courses)
            remaining_items.extend(["CS elective"] * int(est_courses))
            total_remaining_credits += int(credits_deficit)

        if len(remaining_items) < remaining_count:
            remaining_items.extend(["CS elective"] * (remaining_count - len(remaining_items)))
        return remaining_count, remaining_items, int(total_remaining_credits)

    # Creative Writing minor strict handling:
    # - Required: one of ENG 2005 / ENG 2006
    # - Electives: 16 credits from structured set (including ENG 3[4-9]NN)
    # - At least 2 counted electives must be 3000-4000 level
    if _is_creative_writing_minor(minor_name):
        required_options = {c for c in CREATIVE_WRITING_REQUIRED_OPTIONS if c in catalog_courses}
        if required_options and not (required_options & taken):
            remaining_count += 1
            remaining_items.append("ENG 2005 / ENG 2006")
            total_remaining_credits += min((_course_credits(catalog, c) for c in required_options), default=3)

        explicit_elective_codes: Set[str] = {
            c for c in CREATIVE_WRITING_BASE_ELECTIVES if c in catalog_courses
        }
        for block in minor_data.get("elective_requirements", []) or []:
            if not isinstance(block, dict):
                continue
            for code in block.get("allowed_courses", []) or []:
                if isinstance(code, str):
                    normalized = _normalize_course_code(code)
                    if normalized in catalog_courses:
                        explicit_elective_codes.add(normalized)
            rule_text = str(block.get("rule_text") or "")
            for code in COURSE_CODE_PATTERN.findall(rule_text.upper()):
                normalized = _normalize_course_code(code)
                if normalized in catalog_courses:
                    explicit_elective_codes.add(normalized)

        eng_topics_codes = {
            code
            for code in catalog_courses
            if re.match(r"^ENG\s3[4-9]\d{2}$", code)
        }

        allowed_electives = (explicit_elective_codes | eng_topics_codes) - required_options
        elective_taken = {c for c in taken if c in allowed_electives}
        earned_elective_credits = sum(_course_credits(catalog, c) for c in elective_taken)
        credits_deficit = max(0, CREATIVE_WRITING_ELECTIVE_CREDITS_REQUIRED - earned_elective_credits)
        typical_creative_credit = _typical_credit_for_allowed_set(catalog, allowed_electives)
        credits_course_equiv = int(math.ceil(float(credits_deficit) / max(typical_creative_credit, 1e-9))) if credits_deficit > 0 else 0

        def is_upper_level_creative_writing(code: str) -> bool:
            level = _course_number(code)
            return level is not None and 3000 <= level <= 4999

        upper_level_count = sum(
            1
            for code in elective_taken
            if is_upper_level_creative_writing(code)
        )
        upper_level_deficit = max(0, CREATIVE_WRITING_MIN_UPPER_LEVEL_ELECTIVES - upper_level_count)
        upper_level_allowed = {code for code in allowed_electives if is_upper_level_creative_writing(code)}
        upper_level_typical_credit = _typical_credit_for_allowed_set(
            catalog,
            upper_level_allowed if upper_level_allowed else allowed_electives,
        )

        elective_needed = max(int(credits_course_equiv), int(upper_level_deficit))
        if elective_needed > 0:
            remaining_count += elective_needed
            remaining_items.extend(
                ["Creative Writing elective (3000-4000 level)"] * int(upper_level_deficit)
            )
            extra_general = elective_needed - int(upper_level_deficit)
            if extra_general > 0:
                remaining_items.extend(["Creative Writing elective"] * extra_general)
            total_remaining_credits += int(
                max(
                    math.ceil(float(credits_deficit)),
                    math.ceil(float(upper_level_deficit) * max(upper_level_typical_credit, 1e-9)),
                )
            )

        if len(remaining_items) < remaining_count:
            remaining_items.extend(["Creative Writing elective"] * (remaining_count - len(remaining_items)))
        return remaining_count, remaining_items, int(total_remaining_credits)

    # Fine Arts minor strict handling:
    # - Group A: one of FAR 1003/FAR 1009/THR 2011
    # - Group B: one of FAR 3007/FAR 3009/FAR 3010
    # - Group C: 6 credits from structured FAR/THR set
    # - Electives: 6 credits additional FAR courses, excluding FAR used for required groups
    if _is_fine_arts_minor(minor_name):
        group_a = {c for c in FINE_ARTS_GROUP_A if c in catalog_courses}
        group_b = {c for c in FINE_ARTS_GROUP_B if c in catalog_courses}
        group_c = {c for c in FINE_ARTS_GROUP_C if c in catalog_courses}

        taken_a = sorted(group_a & taken)
        taken_b = sorted(group_b & taken)
        taken_c = sorted(group_c & taken)

        a_choices: List[str | None] = taken_a if taken_a else [None]
        b_choices: List[str | None] = taken_b if taken_b else [None]

        c_subsets: List[Set[str]] = []
        if not group_c:
            c_subsets = [set()]
        else:
            total_c_credits = sum(_course_credits(catalog, code) for code in taken_c)
            if total_c_credits < FINE_ARTS_GROUP_C_CREDITS_REQUIRED:
                c_subsets = [set(taken_c)]
            else:
                n = len(taken_c)
                for mask in range(1 << n):
                    subset: Set[str] = set()
                    subset_credits = 0
                    for idx in range(n):
                        if mask & (1 << idx):
                            code = taken_c[idx]
                            subset.add(code)
                            subset_credits += _course_credits(catalog, code)
                    if subset_credits >= FINE_ARTS_GROUP_C_CREDITS_REQUIRED:
                        c_subsets.append(subset)
                if not c_subsets:
                    c_subsets = [set(taken_c)]

        best: Tuple[int, int, List[str]] | None = None
        for a_choice in a_choices:
            for b_choice in b_choices:
                for c_used in c_subsets:
                    items = list(remaining_items)
                    count = int(remaining_count)
                    credits = int(total_remaining_credits)

                    missing_a = bool(group_a) and (a_choice is None)
                    missing_b = bool(group_b) and (b_choice is None)
                    if missing_a:
                        count += 1
                        items.append("Fine Arts group A (FAR 1003 / FAR 1009 / THR 2011)")
                        credits += min((_course_credits(catalog, c) for c in group_a), default=3)
                    if missing_b:
                        count += 1
                        items.append("Fine Arts group B (FAR 3007 / FAR 3009 / FAR 3010)")
                        credits += min((_course_credits(catalog, c) for c in group_b), default=3)

                    c_earned = sum(_course_credits(catalog, code) for code in c_used)
                    c_deficit = max(0, FINE_ARTS_GROUP_C_CREDITS_REQUIRED - c_earned) if group_c else 0
                    c_courses_needed = (c_deficit + 2) // 3
                    if c_courses_needed > 0:
                        count += int(c_courses_needed)
                        items.extend(["Fine Arts group C course"] * int(c_courses_needed))
                        credits += int(c_deficit)

                    used_required_far = {
                        code
                        for code in c_used
                        if isinstance(code, str) and code.startswith("FAR ")
                    }
                    if isinstance(a_choice, str) and a_choice.startswith("FAR "):
                        used_required_far.add(a_choice)
                    if isinstance(b_choice, str) and b_choice.startswith("FAR "):
                        used_required_far.add(b_choice)

                    elective_far_taken = {
                        code
                        for code in taken
                        if isinstance(code, str) and code.startswith("FAR ")
                    } - used_required_far
                    elective_earned = sum(_course_credits(catalog, code) for code in elective_far_taken)
                    elective_deficit = max(0, FINE_ARTS_ELECTIVE_CREDITS_REQUIRED - elective_earned)
                    elective_courses_needed = (elective_deficit + 2) // 3
                    if elective_courses_needed > 0:
                        count += int(elective_courses_needed)
                        items.extend(["Fine Arts elective (additional FAR)"] * int(elective_courses_needed))
                        credits += int(elective_deficit)

                    if len(items) < count:
                        items.extend(["Fine Arts elective"] * (count - len(items)))

                    candidate = (count, credits, items)
                    if best is None or candidate[0] < best[0] or (
                        candidate[0] == best[0] and candidate[1] < best[1]
                    ):
                        best = candidate

        if best is not None:
            return int(best[0]), list(best[2]), int(best[1])

    # --- Generic elective evaluation (catalog-driven) ---
    elective_blocks = minor_data.get("elective_requirements", []) or []
    if not isinstance(elective_blocks, list):
        elective_blocks = []

    total_blocks = [b for b in elective_blocks if isinstance(b, dict) and bool(b.get("is_total"))]
    cap_blocks = [b for b in elective_blocks if isinstance(b, dict) and _elective_block_is_cap(b)]
    level_blocks = [b for b in elective_blocks if isinstance(b, dict) and _elective_block_is_level_constraint(b)]
    min_blocks = [
        b for b in elective_blocks
        if isinstance(b, dict)
        and (not bool(b.get("is_total")))
        and (not _elective_block_is_cap(b))
        and (not _elective_block_is_level_constraint(b))
    ]

    # Detect Sustainability Studies (special distribution rule).
    if "sustain" in _norm_minor_name(minor_name):
        # Ensure required courses are treated as required exclusions.
        required_all |= (SUSTAINABILITY_REQUIRED_COURSES & catalog_courses)

        # Find the main elective block (usually total electives) and parse themes from its rule text.
        main_block = total_blocks[0] if total_blocks else (elective_blocks[0] if elective_blocks else {})
        main_text = _elective_block_rule_text(main_block if isinstance(main_block, dict) else {})
        themes = _parse_sustainability_themes(main_text, catalog_courses)
        if themes:
            # Elective pool is any SUS/BUS/ECO/etc listed inside themes, excluding required.
            theme_courses_all = set().union(*themes.values()) - set(required_all)
            elective_taken = {c for c in taken if c in theme_courses_all}

            # Evaluate best (primary theme=9 credits, secondary theme=3 credits) combination.
            best: Tuple[int, int, List[str]] | None = None
            for primary_name, primary_courses in themes.items():
                if not primary_courses:
                    continue
                primary_taken = elective_taken & primary_courses
                primary_earned = sum(_course_credits(catalog, c) for c in primary_taken)
                primary_deficit = max(0, SUSTAINABILITY_PRIMARY_THEME_CREDITS - int(primary_earned))

                for secondary_name, secondary_courses in themes.items():
                    if secondary_name == primary_name or not secondary_courses:
                        continue
                    secondary_taken = elective_taken & secondary_courses
                    secondary_earned = sum(_course_credits(catalog, c) for c in secondary_taken)
                    secondary_deficit = max(0, SUSTAINABILITY_SECONDARY_THEME_CREDITS - int(secondary_earned))

                    total_earned = sum(_course_credits(catalog, c) for c in elective_taken)
                    total_deficit = max(0, SUSTAINABILITY_ELECTIVE_CREDITS_REQUIRED - int(total_earned))

                    # Missing credits can overlap: picking primary/secondary courses also counts to total.
                    # For proximity we approximate courses needed by the maximum of:
                    # - total elective credit deficit
                    # - primary deficit
                    # - secondary deficit
                    worst_credit_deficit = max(total_deficit, primary_deficit + secondary_deficit)
                    est_courses = int(math.ceil(float(worst_credit_deficit) / 3.0)) if worst_credit_deficit > 0 else 0

                    items: List[str] = []
                    if primary_deficit > 0:
                        items.extend([f"Sustainability elective (theme: {primary_name})"] * int(math.ceil(primary_deficit / 3.0)))
                    if secondary_deficit > 0:
                        items.extend([f"Sustainability elective (theme: {secondary_name})"] * int(math.ceil(secondary_deficit / 3.0)))
                    while len(items) < est_courses:
                        items.append("Sustainability elective")

                    candidate = (est_courses, worst_credit_deficit, items)
                    if best is None or candidate[0] < best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
                        best = candidate

            if best is not None and best[0] > 0:
                remaining_count += int(best[0])
                remaining_items.extend(best[2])
                total_remaining_credits += int(best[1])

            if len(remaining_items) < remaining_count:
                remaining_items.extend(["Sustainability elective"] * (remaining_count - len(remaining_items)))
            return remaining_count, remaining_items, int(total_remaining_credits)

    # Generic total elective rule (credits or courses).
    total_required_credits: float | None = None
    total_required_courses: int | None = None
    total_allowed_set: Set[str] = set()
    total_prefixes: List[str] = []
    if total_blocks:
        total_block = total_blocks[0]
        total_required_credits = _parse_number(total_block.get("credits_required"))
        total_courses_num = _parse_number(total_block.get("courses_required"))
        if total_courses_num is not None:
            rounded = round(total_courses_num)
            if total_courses_num > 0 and abs(total_courses_num - rounded) < 1e-9:
                total_required_courses = int(rounded)
        total_rule_text = _elective_block_rule_text(total_block)
        total_allowed_set = {
            _normalize_course_code(c)
            for c in (total_block.get("allowed_courses") or [])
            if isinstance(c, str)
        } & catalog_courses
        total_allowed_set |= _expand_wildcard_allowed_courses(catalog_courses, total_rule_text)
        if not total_allowed_set:
            total_prefixes = _infer_allowed_prefixes_for_minor_electives(minor_name, total_rule_text)

    def total_is_allowed(code: str) -> bool:
        if total_allowed_set and code in total_allowed_set:
            return True
        if not total_allowed_set and total_prefixes:
            return any(code.startswith(p + " ") for p in total_prefixes)
        # If the catalog doesn't specify an elective universe, conservatively allow only listed codes.
        return False

    elective_taken_total_pool = {c for c in taken if c not in required_all and (total_is_allowed(c) if total_blocks else False)}

    # Count total credits with caps applied.
    counted_total_credits = 0
    if total_blocks:
        counted_total_credits = _counted_credits_with_caps(
            catalog=catalog,
            taken=taken,
            cap_blocks=cap_blocks,
            required_exclusions=set(required_all),
            allowed_predicate=total_is_allowed,
        )

    typical_total_credit = _typical_credit_for_allowed_set(catalog, total_allowed_set) if total_allowed_set else 3.0
    total_course_equiv_needed = 0
    total_credit_deficit = 0
    if total_required_courses is not None and total_required_courses > 0:
        total_course_equiv_needed = max(0, total_required_courses - len(elective_taken_total_pool))
        total_credit_deficit = int(total_course_equiv_needed * math.ceil(typical_total_credit))
    elif total_required_credits is not None and total_required_credits > 0:
        total_credit_deficit = max(0, int(math.ceil(float(total_required_credits) - float(counted_total_credits))))
        total_course_equiv_needed = int(math.ceil(float(total_credit_deficit) / max(typical_total_credit, 1e-9))) if total_credit_deficit > 0 else 0

    # Evaluate subset minimum constraints and upper-level constraints.
    subset_course_equiv_needed = 0
    subset_items: List[str] = []
    subset_credit_deficit_total = 0
    for block in min_blocks:
        label = str(block.get("label") or "Elective")
        rule_text = _elective_block_rule_text(block)
        allowed_set = {
            _normalize_course_code(c)
            for c in (block.get("allowed_courses") or [])
            if isinstance(c, str)
        } & catalog_courses
        allowed_set |= _expand_wildcard_allowed_courses(catalog_courses, rule_text)
        prefixes = _infer_allowed_prefixes_for_minor_electives(minor_name, rule_text) if not allowed_set else []

        def allowed(code: str) -> bool:
            if code in allowed_set:
                return True
            return any(code.startswith(p + " ") for p in prefixes)

        elective_taken = {c for c in taken if c not in required_all and allowed(c)}
        typical_credit = _typical_credit_for_allowed_set(catalog, allowed_set) if allowed_set else 3.0

        credits_required_num = _parse_number(block.get("credits_required"))
        courses_required_num = _parse_number(block.get("courses_required"))
        courses_required_int: int | None = None
        if courses_required_num is not None and courses_required_num > 0:
            rounded = round(courses_required_num)
            if abs(courses_required_num - rounded) < 1e-9:
                courses_required_int = int(rounded)

        if courses_required_int is not None and courses_required_int > 0:
            deficit = max(0, courses_required_int - len(elective_taken))
            if deficit > 0:
                subset_course_equiv_needed = max(subset_course_equiv_needed, int(deficit))
                subset_items.extend([f"{minor_name} elective ({label})"] * int(deficit))
                subset_credit_deficit_total = max(subset_credit_deficit_total, int(math.ceil(deficit * typical_credit)))
            continue

        if credits_required_num is not None and credits_required_num > 0:
            earned = sum(_course_credits(catalog, c) for c in elective_taken)
            deficit_credits = max(0, int(math.ceil(float(credits_required_num) - float(earned))))
            if deficit_credits > 0:
                course_equiv = int(math.ceil(float(deficit_credits) / max(typical_credit, 1e-9)))
                subset_course_equiv_needed = max(subset_course_equiv_needed, int(course_equiv))
                subset_items.extend([f"{minor_name} elective ({label})"] * int(course_equiv))
                subset_credit_deficit_total = max(subset_credit_deficit_total, int(deficit_credits))

    # Upper-level constraints (e.g., "At least two courses must be at the 3000- or 4000-level").
    upper_level_deficit = 0
    if level_blocks and total_blocks:
        # Count upper-level among electives that count toward the minor's total elective pool.
        upper_taken = [c for c in elective_taken_total_pool if _is_upper_level_course(c)]
        # If multiple level blocks exist, take the maximum "at least N" requirement.
        needed_upper = 0
        for block in level_blocks:
            text = _elective_block_rule_text(block).lower()
            hint = _choice_count_hint_from_text(text)
            if hint is None:
                num = _parse_number(block.get("courses_required"))
                if num is not None:
                    rounded = round(num)
                    if num > 0 and abs(num - rounded) < 1e-9:
                        hint = int(rounded)
            if hint is None:
                # Default common case: "at least two".
                hint = 2
            needed_upper = max(needed_upper, int(hint))
        upper_level_deficit = max(0, int(needed_upper) - len(upper_taken))

    elective_course_equiv_needed = max(
        int(total_course_equiv_needed),
        int(subset_course_equiv_needed),
        int(upper_level_deficit),
    )

    if elective_course_equiv_needed > 0:
        # Prefer to surface the "tightest" constraints first.
        if upper_level_deficit > 0:
            remaining_items.extend([
                f"{minor_name} elective (3000-4000 level)"
            ] * int(upper_level_deficit))
        if subset_items:
            # De-duplicate while preserving order.
            for item in subset_items:
                remaining_items.append(item)

        # Pad with generic electives to match elective_course_equiv_needed.
        while (
            len([it for it in remaining_items if "elective" in str(it).lower()])
            < elective_course_equiv_needed
        ):
            remaining_items.append(f"{minor_name} elective")

        remaining_count += int(elective_course_equiv_needed)
        # Credits: for display purposes, use the maximum deficit that could bind.
        total_remaining_credits += int(max(total_credit_deficit, subset_credit_deficit_total, upper_level_deficit * 3))

    if len(remaining_items) < remaining_count:
        remaining_items.extend([f"{minor_name} elective"] * (remaining_count - len(remaining_items)))
    return remaining_count, remaining_items, int(total_remaining_credits)


def compute_minor_proximity_smart(
    catalog: Dict,
    minor_name: str,
    completed_and_planned_courses: Set[str],
) -> Tuple[int, List[str]]:
    remaining_count, remaining_items, _remaining_credits = compute_minor_proximity_smart_details(
        catalog=catalog,
        minor_name=minor_name,
        completed_and_planned_courses=completed_and_planned_courses,
    )
    return remaining_count, remaining_items


def _compute_minor_alerts(
    catalog: Dict,
    majors: List[str],
    minors: List[str],
    completed_courses: Set[str],
    in_progress_courses: Set[str],
    semester_plan: List[Dict],
) -> List[Dict]:
    planned_real_courses: Set[str] = set()
    for term in semester_plan:
        for course in term.get("courses", []) or []:
            if not isinstance(course, dict):
                continue
            code = course.get("code")
            if isinstance(code, str) and code and (not _is_free_elective(code)):
                planned_real_courses.add(_normalize_course_code(code))

    proximity_course_pool = completed_courses | in_progress_courses | planned_real_courses

    minor_alerts: List[Dict] = []
    for minor_name in sorted(catalog.get("minors", {}).keys()):
        if _is_selected_program_minor(minor_name, majors, minors):
            continue
        remaining_count, remaining_list, _remaining_credits = compute_minor_proximity_smart_details(
            catalog=catalog,
            minor_name=minor_name,
            completed_and_planned_courses=proximity_course_pool,
        )
        # Minor close alert rule: only 1-2 course-equivalents away.
        if 1 <= remaining_count <= 2:
            if _is_cs_minor(minor_name):
                # CS structural deficits (core/group requirements) should block "close" alerts.
                has_cs_structural_gap = any(
                    item == "COS 1020"
                    or item.startswith("CS elective (")
                    or item.startswith("Computer Science group (")
                    for item in remaining_list
                )
                if has_cs_structural_gap:
                    continue
            minor_alerts.append({
                "minor": minor_name,
                "remaining_courses": remaining_list,
                "remaining_count": remaining_count,
            })

    minor_alerts.sort(key=lambda item: (int(item.get("remaining_count") or 0), str(item.get("minor") or "")))
    return minor_alerts


def compute_minor_suggestions(
    catalog: Dict,
    majors: List[str],
    minors: List[str],
    completed_courses: Set[str],
    semester_plan: List[Dict],
    in_progress_courses: Set[str] | None = None,
    top_k: int = 5,
) -> List[Dict]:
    selected_minor_count = len({
        _norm_minor_name(name)
        for name in (minors or [])
        if isinstance(name, str) and _norm_minor_name(name)
    })
    if selected_minor_count >= 2:
        return []

    planned_real_courses: Set[str] = set()
    free_slots: List[Dict[str, object]] = []
    catalog_courses = _catalog_courses(catalog)
    free_slot_index_by_term: Dict[str, int] = {}

    for term in semester_plan:
        term_label = str(term.get("term") or "")
        for course in term.get("courses", []) or []:
            if not isinstance(course, dict):
                continue
            raw_code = course.get("code")
            if not isinstance(raw_code, str) or not raw_code.strip():
                continue
            code = _normalize_course_code(raw_code)
            if _is_free_elective(code):
                slot_index = free_slot_index_by_term.get(term_label, 0)
                free_slot_index_by_term[term_label] = slot_index + 1
                raw_instance_id = course.get("instance_id")
                replace_instance_id = (
                    str(raw_instance_id).strip()
                    if isinstance(raw_instance_id, str) and str(raw_instance_id).strip()
                    else None
                )
                free_slots.append({
                    "term": term_label,
                    "replace_code": code,
                    "replace_instance_id": replace_instance_id,
                    "replace_slot_index": int(slot_index),
                })
                continue
            planned_real_courses.add(code)

    proximity_pool = (
        set(completed_courses)
        | set(in_progress_courses or set())
        | planned_real_courses
    )

    def _swap_target_from_item(item: str) -> str | None:
        normalized = _normalize_course_code(item)
        if normalized in catalog_courses:
            return normalized
        for match in COURSE_CODE_PATTERN.findall(item.upper()):
            code = _normalize_course_code(match)
            if code in catalog_courses:
                return code
        return None

    suggestions: List[Dict] = []
    for minor_name in sorted(catalog.get("minors", {}).keys()):
        if _is_selected_program_minor(minor_name, majors, minors):
            continue

        remaining_count, remaining_courses, _remaining_credits = compute_minor_proximity_smart_details(
            catalog=catalog,
            minor_name=minor_name,
            completed_and_planned_courses=proximity_pool,
        )
        # Show only close minors in Smart Minor Suggestions.
        if not (1 <= int(remaining_count) <= 3):
            continue

        score = 100.0 - (30.0 * float(remaining_count))
        if remaining_count <= len(free_slots):
            score += 10.0
        score = max(score, 0.0)

        if remaining_count <= len(free_slots) and free_slots:
            why = f"You are {remaining_count} course(s) away. You can use free electives to complete this minor."
        else:
            why = f"You are {remaining_count} course(s) away."

        swap_suggestions: List[Dict] = []
        if remaining_count > 0 and free_slots:
            swap_targets: List[str] = []
            seen_targets: Set[str] = set()
            for item in remaining_courses:
                target = _swap_target_from_item(item)
                if not target or target in seen_targets:
                    continue
                seen_targets.add(target)
                swap_targets.append(target)

            max_swaps = min(2, len(free_slots), len(swap_targets))
            for idx in range(max_swaps):
                slot = free_slots[idx]
                term_label = str(slot.get("term") or "")
                replace_code = str(slot.get("replace_code") or "")
                replace_instance_id = (
                    str(slot.get("replace_instance_id")).strip()
                    if isinstance(slot.get("replace_instance_id"), str) and str(slot.get("replace_instance_id")).strip()
                    else None
                )
                replace_slot_index = int(slot.get("replace_slot_index") or 0)
                add_code = swap_targets[idx]
                swap_suggestions.append({
                    "term": term_label,
                    "replace_code": replace_code,
                    "replace_instance_id": replace_instance_id,
                    "replace_slot_index": replace_slot_index,
                    "add_code": add_code,
                    "reason": "Uses a FREE ELECTIVE placeholder in your plan.",
                })

        suggestions.append({
            "minor": minor_name,
            "remaining_courses": remaining_courses,
            "remaining_count": int(remaining_count),
            "score": float(score),
            "why": why,
            "swap_suggestions": swap_suggestions,
        })

    suggestions.sort(
        key=lambda item: (
            -float(item.get("score") or 0.0),
            int(item.get("remaining_count") or 0),
            str(item.get("minor") or ""),
        )
    )
    return suggestions[: max(0, int(top_k or 5))]


def _build_course_output(
    catalog: Dict,
    code: str,
    slots: Dict,
    course_assignments: Dict[str, Set[str]],
    prereq_courses: Set[str] | None,
    source_reasons: Dict[str, str],
) -> Dict:
    if _is_free_elective(code):
        return {
            "code": code,
            "name": "Free Elective",
            "credits": 3,
            "tags": ["Planned"],
            "satisfies": [],
            "type": "FREE_ELECTIVE",
            "source_reason": SOURCE_REASON_FREE,
        }

    satisfies_ids = course_assignments.get(code, set())
    satisfies = sorted({_slot_label(slots["by_id"][sid]) for sid in satisfies_ids})
    source_reason = source_reasons.get(code)
    if source_reason is None and prereq_courses and code in prereq_courses:
        source_reason = SOURCE_REASON_PREREQ
    if source_reason is None:
        source_reason = SOURCE_REASON_PREREQ

    course_type = "FREE"
    if source_reason in {SOURCE_REASON_MAJOR, SOURCE_REASON_MINOR}:
        course_type = "PROGRAM"
    elif source_reason == SOURCE_REASON_GENED:
        if any(slots["by_id"][sid]["owner"] == "foundation" for sid in satisfies_ids):
            course_type = "FOUNDATION"
        else:
            course_type = "GENED"
    elif source_reason == SOURCE_REASON_PREREQ:
        course_type = "FREE"
    return {
        "code": code,
        "name": _course_name(catalog, code),
        "credits": _course_credits(catalog, code),
        "tags": _planned_course_tags(catalog, code),
        "satisfies": satisfies,
        "type": course_type,
        "source_reason": source_reason,
    }


def _compute_prereq_warnings(
    catalog: Dict,
    semester_plan: List[Dict],
    completed_courses: Set[str],
) -> List[Dict]:
    warnings: List[Dict] = []
    satisfied = set(completed_courses)
    ordered_terms = sorted(semester_plan, key=lambda t: _term_label_index(t.get("term", "")))
    for term in ordered_terms:
        for course in term.get("courses", []):
            code = course.get("code")
            if not code or not isinstance(code, str):
                continue
            unmet = _unmet_prereq_labels(catalog, code, satisfied)
            if unmet:
                warnings.append(_make_warning("PREREQ_UNMET", course=code, unmet=unmet))
        for course in term.get("courses", []):
            code = course.get("code")
            if isinstance(code, str):
                satisfied.add(code)
    return warnings


def _rebalance_term_mix(
    catalog: Dict,
    semester_plan: List[Dict],
    completed_courses: Set[str],
    min_credits: int,
    max_credits: int,
    occupied_credits_by_term: Dict[str, int] | None = None,
) -> List[Dict]:
    if not semester_plan:
        return semester_plan

    terms = sorted(semester_plan, key=lambda t: _term_label_index(t.get("term", "")))

    occupied = occupied_credits_by_term or {}

    def available_bounds(term_label: str) -> Tuple[int, int]:
        occupied_credits = max(0, int(occupied.get(term_label, 0) or 0))
        return max(0, min_credits - occupied_credits), max(0, max_credits - occupied_credits)

    def course_group(course: Dict) -> str:
        ctype = course.get("type")
        if ctype in {"PROGRAM", "FOUNDATION"}:
            return "program"
        if ctype == "GENED":
            return "gened"
        return "other"

    def term_credits(term_courses: List[Dict]) -> int:
        return sum(_planned_course_credits(catalog, c) for c in term_courses)

    def completed_before(term_idx: int) -> Tuple[Set[str], Set[str]]:
        completed = set(completed_courses)
        completed_gened = _completed_gened_categories(catalog, completed)
        for t in terms[:term_idx]:
            for course in t.get("courses", []):
                code = course.get("code")
                if isinstance(code, str):
                    completed.add(code)
                    completed_gened.update(_course_gened_categories(catalog, code))
        return completed, completed_gened

    def term_is_eligible(term_idx: int, term_courses: List[Dict], completed: Set[str], completed_gened: Set[str]) -> bool:
        for course in term_courses:
            code = course.get("code")
            if not isinstance(code, str):
                return False
            if _is_free_elective(code):
                continue
            if not _eligible_for_term(catalog, code, term_idx, completed, completed_gened):
                return False
        return True

    def attempt_swap(idx_a: int, idx_b: int) -> bool:
        term_a = terms[idx_a]
        term_b = terms[idx_b]
        courses_a = term_a.get("courses", []) or []
        courses_b = term_b.get("courses", []) or []

        group_a = [course_group(c) for c in courses_a]
        group_b = [course_group(c) for c in courses_b]

        a_program = [i for i, g in enumerate(group_a) if g == "program"]
        a_gened = [i for i, g in enumerate(group_a) if g == "gened"]
        b_program = [i for i, g in enumerate(group_b) if g == "program"]
        b_gened = [i for i, g in enumerate(group_b) if g == "gened"]

        if a_gened and not a_program and b_program:
            from_a = a_gened
            from_b = b_program
        elif a_program and not a_gened and b_gened:
            from_a = a_program
            from_b = b_gened
        else:
            return False

        completed_a, completed_gened_a = completed_before(idx_a)

        for idx_course_a in from_a:
            for idx_course_b in from_b:
                next_a = list(courses_a)
                next_b = list(courses_b)
                next_a[idx_course_a], next_b[idx_course_b] = next_b[idx_course_b], next_a[idx_course_a]

                credits_a = term_credits(next_a)
                credits_b = term_credits(next_b)
                min_a, max_a = available_bounds(term_a.get("term", ""))
                min_b, max_b = available_bounds(term_b.get("term", ""))
                if credits_a < min_a or credits_a > max_a:
                    continue
                if credits_b < min_b or credits_b > max_b:
                    continue

                if not term_is_eligible(idx_a, next_a, completed_a, completed_gened_a):
                    continue

                completed_b = set(completed_a)
                completed_gened_b = set(completed_gened_a)
                for course in next_a:
                    code = course.get("code")
                    if isinstance(code, str):
                        completed_b.add(code)
                        completed_gened_b.update(_course_gened_categories(catalog, code))

                if not term_is_eligible(idx_b, next_b, completed_b, completed_gened_b):
                    continue

                term_a["courses"] = next_a
                term_b["courses"] = next_b
                term_a["credits"] = credits_a
                term_b["credits"] = credits_b
                return True
        return False

    for i in range(len(terms) - 1):
        attempt_swap(i, i + 1)

    return terms


def validate_plan(
    catalog: Dict,
    semester_plan: List[Dict],
    completed_courses: Set[str],
    start_term: Tuple[str, int],
    min_credits: int,
    max_credits: int,
    strict_prereqs: bool = False,
    remaining_slots: Set[str] | None = None,
    slots: Dict | None = None,
    occupied_credits_by_term: Dict[str, int] | None = None,
) -> List[str]:
    errors: List[str] = []
    if not semester_plan:
        errors.append("Plan has no semesters.")
        return errors

    base_season, base_year = start_term
    base_idx = _term_label_index(f"{base_season} {base_year}")
    if base_idx == 999999:
        errors.append("Invalid start term.")

    catalog_courses = _planning_course_pool(catalog)
    satisfied = set(completed_courses)
    earned_credits = _completed_credit_total(catalog, satisfied)
    seen_instance_ids: Set[str] = set()
    occupied = occupied_credits_by_term or {}

    ordered_terms = sorted(semester_plan, key=lambda t: _term_label_index(t.get("term", "")))
    planned_term_labels: Set[str] = set()
    for term in ordered_terms:
        term_label = term.get("term", "")
        planned_term_labels.add(term_label)
        term_idx = _term_label_index(term_label)
        if term_idx == 999999:
            errors.append(f"Invalid term label: {term_label}")
            continue
        if base_idx != 999999 and term_idx < base_idx:
            errors.append(f"Term {term_label} is earlier than the start term.")

        term_courses = term.get("courses", []) or []
        codes: List[str] = []
        normalized_term_courses: List[Dict[str, Any]] = []
        for course in term_courses:
            code = course.get("code") if isinstance(course, dict) else None
            if not code or not isinstance(code, str):
                errors.append(f"Invalid course entry in {term_label}.")
                continue
            if isinstance(course, dict):
                normalized_term_courses.append(course)
            if isinstance(course, dict):
                raw_instance_id = course.get("instance_id")
                if isinstance(raw_instance_id, str) and raw_instance_id.strip():
                    instance_id = raw_instance_id.strip()
                    if instance_id in seen_instance_ids:
                        errors.append(f"Duplicate course instance_id in plan: {instance_id}")
                    else:
                        seen_instance_ids.add(instance_id)
            codes.append(code)

        calc_credits = sum(
            _planned_course_credits(catalog, course)
            for course in normalized_term_courses
        )
        term_has_only_retakes = bool(normalized_term_courses) and all(
            course.get("is_retake") is True and _planned_course_credits(catalog, course) == 0
            for course in normalized_term_courses
        )
        term_credits = term.get("credits", calc_credits)
        if isinstance(term_credits, int) and term_credits != calc_credits:
            errors.append(f"{term_label} credits mismatch (reported {term_credits}, actual {calc_credits}).")
        occupied_credits = max(0, int(occupied.get(term_label, 0) or 0))
        total_term_credits = calc_credits + occupied_credits
        if total_term_credits > max_credits:
            errors.append(f"{term_label} exceeds max credits ({total_term_credits} > {max_credits}).")
        if total_term_credits < min_credits and not term_has_only_retakes:
            errors.append(f"{term_label} is below the minimum credit load ({total_term_credits} < {min_credits}).")

        for code in codes:
            if _is_free_elective(code):
                satisfied.add(code)
                continue
            if code not in catalog_courses:
                errors.append(f"Course not found in catalog: {code}")
                satisfied.add(code)
                continue

            min_term = _min_term_index_for_course(catalog, code, earned_credits)
            if base_idx != 999999 and term_idx < base_idx + min_term:
                earliest = _term_name(min_term, base_season, base_year)
                reasons = _min_term_reasons(catalog, code)
                reason_text = f" based on {', '.join(reasons)}" if reasons else ""
                errors.append(
                    f"{code} may be scheduled too early in {term_label}. "
                    f"Earliest recommended term is {earliest}{reason_text}."
                )

            unmet = _unmet_prereq_labels(catalog, code, satisfied)
            if unmet and strict_prereqs:
                errors.append(f"{code} scheduled before prerequisites: {', '.join(unmet)}.")
            satisfied.add(code)

        earned_credits += term_credits

        earned_credits += term_credits

    # Terms that only contain in-progress load are not in semester_plan,
    # but they can still exceed the cap and should be surfaced.
    for term_label, occupied_credits in occupied.items():
        if term_label in planned_term_labels:
            continue
        total_credits = max(0, int(occupied_credits or 0))
        if total_credits > max_credits:
            errors.append(f"{term_label} exceeds max credits ({total_credits} > {max_credits}).")

    if remaining_slots:
        label_samples: List[str] = []
        if slots and isinstance(slots.get("by_id"), dict):
            for sid in sorted(remaining_slots):
                slot = slots["by_id"].get(sid)
                if slot:
                    label_samples.append(_slot_label(slot))
                if len(label_samples) >= 5:
                    break
        sample = ", ".join(label_samples) if label_samples else ", ".join(sorted(list(remaining_slots))[:5])
        errors.append(
            f"Unfilled requirement slots ({len(remaining_slots)})."
            + (f" Examples: {sample}" if sample else "")
        )

    errors.extend(_textual_analysis_sequence_errors(catalog, semester_plan, completed_courses))

    return errors


def _effective_completed_courses_after_plan(
    completed_courses: Set[str],
    semester_plan: List[Dict],
) -> Set[str]:
    # Any planned real-course attempt supersedes historical completion for reporting.
    # This preserves "latest attempt wins" without affecting prerequisite checks,
    # which continue to rely on the original completed_courses set.
    effective = set(completed_courses)
    ordered_terms = sorted(semester_plan or [], key=lambda t: _term_label_index(t.get("term", "")))
    for term in ordered_terms:
        for course in term.get("courses", []) or []:
            if not isinstance(course, dict):
                continue
            code = course.get("code")
            if not isinstance(code, str) or not code:
                continue
            normalized = _normalize_course_code(code)
            if not normalized or _is_free_elective(normalized):
                continue
            effective.discard(normalized)
    return effective


def _textual_analysis_sequence_errors(
    catalog: Dict,
    semester_plan: List[Dict],
    completed_courses: Set[str],
) -> List[str]:
    principles_label = "Principles of Textual Analysis"
    case_studies_label = "Case Studies in Textual Analysis"
    lookup = _catalog_gened_lookup(catalog)
    if principles_label.lower() not in lookup or case_studies_label.lower() not in lookup:
        return []

    principles_satisfied_earlier = any(
        principles_label in _course_gened_categories(catalog, code)
        for code in completed_courses
        if isinstance(code, str)
    )

    errors: List[str] = []
    ordered_terms = sorted(semester_plan or [], key=lambda t: _term_label_index(t.get("term", "")))
    for term in ordered_terms:
        term_label = str(term.get("term") or "").strip()
        has_principles_this_term = False
        has_case_studies_this_term = False
        for course in term.get("courses", []) or []:
            if not isinstance(course, dict):
                continue
            code = course.get("code")
            if not isinstance(code, str):
                continue
            categories = _course_gened_categories(catalog, code)
            if principles_label in categories:
                has_principles_this_term = True
            if case_studies_label in categories:
                has_case_studies_this_term = True

        if has_case_studies_this_term and not principles_satisfied_earlier:
            errors.append(
                f"{case_studies_label} must be scheduled after {principles_label} "
                f"(invalid term: {term_label})."
            )
        if has_principles_this_term:
            principles_satisfied_earlier = True

    return errors


def _gen_ed_status(
    slots: Dict,
    slot_assignment: Dict[str, str],
    completed_courses: Set[str],
) -> Dict[str, Dict[str, int]]:
    status: Dict[str, Dict[str, int]] = {}
    for slot in slots.get("slots", []):
        if slot["type"] != "gened":
            continue
        cat = slot.get("category")
        status.setdefault(cat, {"required": 0, "completed": 0, "planned": 0})
        status[cat]["required"] += 1
        assigned = slot_assignment.get(slot["id"])
        if assigned:
            if assigned in completed_courses:
                status[cat]["completed"] += 1
            else:
                status[cat]["planned"] += 1
    return status


def _category_credit_progress(
    catalog: Dict,
    slots: Dict,
    slot_assignment: Dict[str, str],
    completed_courses: Set[str],
    waived_courses: Set[str] | None = None,
    selected_majors: List[str] | None = None,
) -> Dict[str, Dict]:
    majors: Dict[str, Dict[str, int]] = {}
    minors: Dict[str, Dict[str, int]] = {}
    gen_ed = {"required": 0, "completed": 0}
    foundation = {"required": 0, "completed": 0}

    for slot in slots.get("slots", []):
        assigned = slot_assignment.get(slot["id"])
        credits = _course_credits(catalog, assigned) if assigned else 3

        bucket: Dict[str, int] | None = None
        if slot["type"] == "gened":
            bucket = gen_ed
        elif slot.get("owner") == "foundation":
            bucket = foundation
        elif slot.get("owner") == "program":
            program = slot.get("program")
            program_type = slot.get("program_type")
            if program_type == "major" and program:
                bucket = majors.setdefault(program, {"required": 0, "completed": 0})
            elif program_type == "minor" and program:
                bucket = minors.setdefault(program, {"required": 0, "completed": 0})

        if bucket is None:
            continue

        bucket["required"] += credits
        if assigned and assigned in completed_courses and (not waived_courses or assigned not in waived_courses):
            bucket["completed"] += credits

    completed_non_waived = {
        code for code in completed_courses
        if (not waived_courses) or (code not in waived_courses)
    }
    selected_major_names = {
        name for name in (selected_majors or [])
        if isinstance(name, str) and name
    }
    slot_major_names = {
        slot.get("program")
        for slot in slots.get("slots", [])
        if slot.get("owner") == "program"
        and slot.get("program_type") == "major"
        and isinstance(slot.get("program"), str)
    }
    for major_name in sorted(set(selected_major_names) | set(slot_major_names)):
        if not _is_business_administration_major(major_name):
            continue
        progress = _business_administration_elective_credit_breakdown(catalog, completed_non_waived)
        bucket = majors.setdefault(major_name, {"required": 0, "completed": 0})
        bucket["required"] += int(progress.get("required") or 0)
        bucket["completed"] += int(progress.get("counted_total") or 0)

    minors_required = sum(v["required"] for v in minors.values())
    minors_completed = sum(v["completed"] for v in minors.values())

    minors_gened = {
        "required": gen_ed["required"] + foundation["required"] + minors_required,
        "completed": gen_ed["completed"] + foundation["completed"] + minors_completed,
    }

    return {
        "majors": majors,
        "minors": minors,
        "gen_ed": gen_ed,
        "foundation": foundation,
        "minors_gened": minors_gened,
    }


def _manual_credit_breakdown(
    manual_credits: List[Dict[str, Any]] | None,
    selected_majors: List[str] | None,
    catalog_gened_categories: Dict[str, Any] | None,
) -> Dict[str, Any]:
    breakdown: Dict[str, Any] = {
        "total": 0,
        "free_elective": 0,
        "gened": {},
        "major_electives": {},
    }
    if not manual_credits:
        return breakdown

    major_lookup = {
        name.strip().lower(): name
        for name in (selected_majors or [])
        if isinstance(name, str) and name.strip()
    }
    gened_lookup = {
        _normalize_gened_label(category).lower(): category
        for category in (catalog_gened_categories or {}).keys()
        if isinstance(category, str) and _normalize_gened_label(category)
    }

    for entry in manual_credits:
        if not isinstance(entry, dict):
            continue
        if _normalize_course_code(entry.get("code")) != "OTH 0001":
            continue

        raw_credits = entry.get("credits")
        try:
            credits = int(raw_credits)
        except (TypeError, ValueError):
            continue
        if credits <= 0:
            continue

        breakdown["total"] += credits
        credit_type = str(entry.get("credit_type") or "").strip().upper()

        if credit_type == "FREE_ELECTIVE":
            breakdown["free_elective"] += credits
            continue

        if credit_type == "GENED":
            raw_category = _normalize_gened_label(str(entry.get("gened_category") or ""))
            if not raw_category:
                continue
            category = gened_lookup.get(raw_category.lower(), raw_category)
            breakdown["gened"][category] = int(breakdown["gened"].get(category, 0) or 0) + credits
            continue

        if credit_type == "MAJOR_ELECTIVE":
            raw_program = str(entry.get("program") or "").strip()
            if not raw_program:
                continue
            program = major_lookup.get(raw_program.lower())
            if not program:
                continue
            breakdown["major_electives"][program] = (
                int(breakdown["major_electives"].get(program, 0) or 0) + credits
            )

    return breakdown


def _apply_manual_credit_progress(
    category_progress: Dict[str, Dict],
    manual_credit_breakdown: Dict[str, Any],
) -> None:
    gened_total = sum(
        int(credits or 0)
        for credits in (manual_credit_breakdown.get("gened") or {}).values()
    )
    if gened_total > 0:
        gen_ed_bucket = category_progress.setdefault("gen_ed", {"required": 0, "completed": 0})
        gen_ed_bucket["completed"] = int(gen_ed_bucket.get("completed", 0) or 0) + gened_total

    major_progress = category_progress.setdefault("majors", {})
    for program, credits in (manual_credit_breakdown.get("major_electives") or {}).items():
        bucket = major_progress.setdefault(program, {"required": 0, "completed": 0})
        bucket["completed"] = int(bucket.get("completed", 0) or 0) + int(credits or 0)

    free_credits = int(manual_credit_breakdown.get("free_elective", 0) or 0)
    if free_credits > 0:
        free_bucket = category_progress.setdefault(
            "free_elective",
            {"required": free_credits, "completed": 0},
        )
        free_bucket["required"] = max(int(free_bucket.get("required", 0) or 0), free_credits)
        free_bucket["completed"] = int(free_bucket.get("completed", 0) or 0) + free_credits


def _slots_after_manual_credit_reduction(
    slots: Dict[str, Any],
    manual_credit_breakdown: Dict[str, Any],
) -> Dict[str, Any]:
    gened_breakdown = manual_credit_breakdown.get("gened") or {}
    if not isinstance(gened_breakdown, dict) or not gened_breakdown:
        return slots

    remove_by_category_norm: Dict[str, int] = {}
    for category, credits in gened_breakdown.items():
        normalized = _normalize_gened_label(str(category or "")).lower()
        if not normalized:
            continue
        try:
            credits_int = int(credits)
        except (TypeError, ValueError):
            continue
        slot_count = max(0, credits_int // 3)
        if slot_count <= 0:
            continue
        remove_by_category_norm[normalized] = remove_by_category_norm.get(normalized, 0) + slot_count

    if not remove_by_category_norm:
        return slots

    filtered_slots: List[Dict[str, Any]] = []
    removed_any = False
    for slot in slots.get("slots", []) or []:
        if not isinstance(slot, dict):
            continue
        if slot.get("type") != "gened":
            filtered_slots.append(dict(slot))
            continue
        normalized_category = _normalize_gened_label(str(slot.get("category") or "")).lower()
        remaining_to_remove = remove_by_category_norm.get(normalized_category, 0)
        if remaining_to_remove > 0:
            remove_by_category_norm[normalized_category] = remaining_to_remove - 1
            removed_any = True
            continue
        filtered_slots.append(dict(slot))

    if not removed_any:
        return slots

    filtered_by_id = {
        slot.get("id"): slot
        for slot in filtered_slots
        if isinstance(slot.get("id"), str)
    }
    return {
        "slots": filtered_slots,
        "by_id": filtered_by_id,
    }


def _collect_elective_placeholders(catalog: Dict, majors: List[str], minors: List[str]) -> List[Dict]:
    placeholders: List[Dict] = []

    def add_placeholders(programs: List[str], program_type: str) -> None:
        for name in programs:
            data = catalog.get("majors" if program_type == "major" else "minors", {}).get(name, {}) or {}
            for block in data.get("elective_requirements", []) or []:
                if not isinstance(block, dict):
                    continue
                label = str(block.get("label") or "").strip().lower()
                if "program choice" in label and not bool(block.get("is_total")):
                    continue
                placeholders.append({
                    "id": block.get("id") or f"{name}-{program_type}-elective",
                    "program": name,
                    "program_type": program_type,
                    "label": block.get("label") or "Elective Courses",
                    "credits_required": block.get("credits_required"),
                    "courses_required": block.get("courses_required"),
                    "allowed_courses": block.get("allowed_courses") or [],
                    "rule_text": block.get("rule_text") or "",
                    "is_total": bool(block.get("is_total")),
                })

    add_placeholders(majors, "major")
    add_placeholders(minors, "minor")
    return placeholders

def compute_elective_recommendations(
    catalog: Dict,
    majors: List[str],
    minors: List[str],
    completed_courses: Set[str],
    planned_courses: List[str],
    limit: int = 30,
) -> List[Dict]:
    excel_catalog: Dict = catalog.get("excel_catalog") or {}
    taken = {
        _normalize_course_code(code)
        for code in (set(completed_courses) | set(planned_courses))
        if isinstance(code, str) and code.strip()
    }
    catalog_courses = _catalog_courses(catalog)
    result_by_code: Dict[str, Dict] = {}

    def _merge_recommendation(code: str, tags: List[str], program_keys: Set[str]) -> None:
        normalized_code = _normalize_course_code(code)
        if not normalized_code or normalized_code in taken or normalized_code not in catalog_courses:
            return

        entry = result_by_code.get(normalized_code)
        if entry is None:
            entry = {
                "code": normalized_code,
                "name": _course_name(catalog, normalized_code),
                "credits": _course_credits(catalog, normalized_code),
                "tags": [],
                "_program_keys": set(),
            }
            result_by_code[normalized_code] = entry

        for tag in tags:
            if isinstance(tag, str) and tag and tag not in entry["tags"]:
                entry["tags"].append(tag)
        entry["_program_keys"].update({
            key for key in program_keys
            if isinstance(key, str) and key
        })

    if excel_catalog:
        candidates = get_recommended_electives(
            excel_catalog=excel_catalog,
            selected_majors=majors,
            selected_minors=minors,
        )
        candidates = _limit_business_administration_non_bus_elective_candidates(candidates, majors)
    else:
        candidates = []

    for entry in candidates:
        code = entry.get("code")
        if not isinstance(code, str):
            continue
        tags = entry.get("tags") or []
        if not isinstance(tags, list):
            tags = []
        matched_major = entry.get("matched_major_tags") or []
        matched_minor = entry.get("matched_minor_tags") or []
        if not isinstance(matched_major, list):
            matched_major = []
        if not isinstance(matched_minor, list):
            matched_minor = []

        display_tags: List[str] = []
        for tag in matched_major + matched_minor:
            if isinstance(tag, str) and tag not in display_tags:
                display_tags.append(tag)
        for tag in tags:
            if isinstance(tag, str) and tag not in display_tags:
                display_tags.append(tag)

        unique_programs: Set[str] = set()
        for line in matched_major:
            if isinstance(line, str) and line.split():
                unique_programs.add(f"major:{line.split()[0]}")
        for line in matched_minor:
            if isinstance(line, str) and line.split():
                unique_programs.add(f"minor:{line.split()[0]}")

        _merge_recommendation(code, display_tags, unique_programs)

    # Selected minors should also recommend from the PDF-parsed elective blocks, which are
    # the source of truth for the "Elective Requirements" panel.
    for minor_name in minors:
        minor_data = (catalog.get("minors", {}) or {}).get(minor_name, {}) or {}
        elective_blocks = minor_data.get("elective_requirements", []) or []
        if not isinstance(elective_blocks, list) or not elective_blocks:
            continue

        header_totals = [
            block
            for block in elective_blocks
            if isinstance(block, dict)
            and bool(block.get("is_total"))
            and (
                _parse_number(block.get("credits_required")) is not None
                or _parse_number(block.get("courses_required")) is not None
            )
        ]
        total_required_credits = (
            max(
                int(math.ceil(float(_parse_number(block.get("credits_required")) or 0)))
                for block in header_totals
            )
            if header_totals
            else sum(
                int(math.ceil(float(_parse_number(block.get("credits_required")) or 0)))
                for block in elective_blocks
                if isinstance(block, dict)
            )
        )
        total_required_courses = (
            max(
                int(math.ceil(float(_parse_number(block.get("courses_required")) or 0)))
                for block in header_totals
            )
            if header_totals
            else sum(
                int(math.ceil(float(_parse_number(block.get("courses_required")) or 0)))
                for block in elective_blocks
                if isinstance(block, dict)
            )
        )

        allowed_courses: List[str] = []
        seen_allowed: Set[str] = set()
        for block in elective_blocks:
            if not isinstance(block, dict):
                continue
            for raw_code in block.get("allowed_courses", []) or []:
                if not isinstance(raw_code, str):
                    continue
                normalized = _normalize_course_code(raw_code)
                if not normalized or normalized not in catalog_courses or normalized in seen_allowed:
                    continue
                seen_allowed.add(normalized)
                allowed_courses.append(normalized)
        if not allowed_courses:
            continue

        required_courses = {
            _normalize_course_code(code)
            for code in (minor_data.get("required_courses") or [])
            if isinstance(code, str)
        }
        counted_taken = [code for code in allowed_courses if code in taken and code not in required_courses]
        counted_credits = sum(_course_credits(catalog, code) for code in counted_taken)

        is_complete = False
        if total_required_credits > 0:
            is_complete = counted_credits >= total_required_credits
        elif total_required_courses > 0:
            is_complete = len(counted_taken) >= total_required_courses
        if is_complete:
            continue

        aliases = PROGRAM_TAG_ALIASES.get(minor_name) or []
        display_prefix = next(
            (str(alias).strip() for alias in aliases if isinstance(alias, str) and str(alias).strip()),
            "",
        )
        if not display_prefix:
            display_prefix = minor_name.strip()
        display_tag = f"{display_prefix} Minor Elective"
        program_key = f"minor:{_norm_minor_name(minor_name) or minor_name}"

        for code in allowed_courses:
            _merge_recommendation(code, [display_tag], {program_key})

    results = list(result_by_code.values())
    for entry in results:
        program_keys = entry.get("_program_keys") or set()
        if not isinstance(program_keys, set):
            program_keys = set()
        has_major = any(isinstance(key, str) and key.startswith("major:") for key in program_keys)
        has_minor = any(isinstance(key, str) and key.startswith("minor:") for key in program_keys)
        entry["requirementsSatisfied"] = len(program_keys)
        if has_major and has_minor:
            entry["explanation"] = "Matches electives for your majors and minors."
        elif has_major:
            entry["explanation"] = "Matches electives for your selected major(s)."
        else:
            entry["explanation"] = "Matches electives for your selected minor(s)."
        entry["_major_matches"] = sum(
            1 for key in program_keys
            if isinstance(key, str) and key.startswith("major:")
        )

    results.sort(key=lambda r: (-r["_major_matches"], -r["requirementsSatisfied"], -r["credits"], r["code"]))
    trimmed = results[:limit]
    for r in trimmed:
        r.pop("_major_matches", None)
        r.pop("_program_keys", None)
    return trimmed


def _excel_course_summary(catalog: Dict, code: str, tags: List[str]) -> Dict:
    return {
        "code": code,
        "name": _course_name(catalog, code),
        "credits": _course_credits(catalog, code),
        "tags": [t for t in tags if isinstance(t, str)],
    }


def generate_plan(
    catalog: Dict,
    majors: List[str],
    minors: List[str],
    completed_courses: Set[str],
    manual_credits: List[Dict[str, Any]] | None = None,
    retake_courses: Set[str] | List[str] | None = None,
    max_credits_per_semester: int = 16,
    start_term_season: str | None = None,
    start_term_year: int | None = None,
    waived_mat1000: bool = False,
    waived_eng1000: bool = False,
    strict_prereqs: bool = False,
    fill_underloaded_terms: bool = True,
    overrides: Dict | None = None,
    in_progress_courses: Set[str] | List[str] | None = None,
    in_progress_terms: Dict[str, str] | None = None,
    current_term_label: str | None = None,
) -> Dict:
    if not catalog.get("gen_ed", {}).get("rules"):
        raise ValueError("Gen Ed rules are missing from the catalog. Please re-upload a catalog with Gen Ed requirements.")

    completed_courses = set([_normalize_course_code(c) for c in completed_courses])
    catalog_courses = _catalog_courses(catalog)
    planning_course_pool = _planning_course_pool(catalog)
    completed_courses &= planning_course_pool
    normalized_retakes = {
        _normalize_course_code(code)
        for code in (retake_courses or set())
        if isinstance(code, str)
    }
    normalized_retakes &= planning_course_pool
    normalized_retakes &= completed_courses

    normalized_in_progress = {
        _normalize_course_code(code)
        for code in (in_progress_courses or set())
        if isinstance(code, str)
    }
    normalized_in_progress &= planning_course_pool

    occupied_credits_by_term = _compute_in_progress_occupied_credits(
        catalog=catalog,
        in_progress_courses=normalized_in_progress,
        in_progress_terms=in_progress_terms,
        current_term_label=current_term_label,
    )

    waived_courses: Set[str] = set()
    if waived_mat1000 and "MAT 1000" in catalog_courses:
        completed_courses.add("MAT 1000")
        waived_courses.add("MAT 1000")
    if waived_eng1000 and "ENG 1000" in catalog_courses:
        completed_courses.add("ENG 1000")
        waived_courses.add("ENG 1000")

    manual_credit_breakdown = _manual_credit_breakdown(
        manual_credits=manual_credits,
        selected_majors=majors,
        catalog_gened_categories=(catalog.get("gen_ed", {}) or {}).get("categories", {}) or {},
    )

    slots = build_requirement_slots(catalog, majors, minors)
    planning_slots = _slots_after_manual_credit_reduction(slots, manual_credit_breakdown)
    base_season, base_year = _normalize_start_term(start_term_season, start_term_year)
    max_terms_remaining = 8
    max_credits = max(14, int(max_credits_per_semester))
    min_credits = min(MIN_CREDITS_PER_TERM, max_credits)
    target_credits = min(max_credits, 15)

    semester_result = generate_semester_plan(
        catalog=catalog,
        slots=planning_slots,
        completed_courses=completed_courses,
        retake_courses=normalized_retakes,
        start_term=(base_season, base_year),
        max_terms=max_terms_remaining,
        min_credits=min_credits,
        target_credits=target_credits,
        max_credits=max_credits,
        fill_underloaded_terms=fill_underloaded_terms,
        occupied_credits_by_term=occupied_credits_by_term,
    )

    plan = semester_result["plan"]
    selection = semester_result["selection"]

    uncovered_gened = [
        slot for slot in planning_slots.get("slots", [])
        if slot.get("type") == "gened" and slot.get("id") not in selection["covered_slots"]
    ]
    if uncovered_gened:
        missing_categories = sorted({slot.get("category") for slot in uncovered_gened if slot.get("category")})
        raise ValueError(
            "Unable to satisfy General Education requirements for: " + ", ".join(missing_categories)
        )

    # Build course outputs per term
    planned_courses = []
    for term in plan:
        planned_courses.extend(term["courses"])

    prereq_only = set(selection.get("needed_prereqs", set()))
    source_reasons = selection.get("direct_reason_map", {})
    allowed_auto = set(selection.get("allowed_auto", set()))
    course_outputs = {
        code: _build_course_output(
            catalog,
            code,
            planning_slots,
            selection["course_assignments"],
            prereq_only,
            source_reasons,
        )
        for code in planned_courses
    }

    semester_plan = []
    for term in plan:
        courses = [{**course_outputs[c]} for c in term["courses"]]
        credits = sum(c["credits"] for c in courses)
        semester_plan.append({
            "term": term["term"],
            "courses": courses,
            "credits": credits,
        })

    semester_plan = _rebalance_term_mix(
        catalog=catalog,
        semester_plan=semester_plan,
        completed_courses=completed_courses,
        min_credits=min_credits,
        max_credits=max_credits,
        occupied_credits_by_term=occupied_credits_by_term,
    )

    semester_plan = _dedupe_semester_plan(catalog, semester_plan, completed_courses)
    _ensure_instance_ids(semester_plan)
    _apply_latest_attempt_credit_rule(
        catalog=catalog,
        semester_plan=semester_plan,
        completed_courses=completed_courses,
    )
    effective_completed_courses = _effective_completed_courses_after_plan(completed_courses, semester_plan)

    # Computed after overrides/final shaping so alerts reflect the final plan state.
    minor_alerts: List[Dict] = []
    all_slot_ids = {slot["id"] for slot in slots.get("slots", [])}
    completed_slots = {
        sid
        for sid, course in selection["slot_assignment"].items()
        if course in effective_completed_courses
    }
    total_required = len(all_slot_ids)
    completed_count = len(completed_slots)
    remaining_count = max(0, total_required - completed_count)

    gen_ed_status = _gen_ed_status(slots, selection["slot_assignment"], effective_completed_courses)
    category_progress = _category_credit_progress(
        catalog,
        slots,
        selection["slot_assignment"],
        effective_completed_courses,
        waived_courses,
        selected_majors=majors,
    )
    total_manual_credits = int(manual_credit_breakdown.get("total", 0) or 0)

    # Credit totals derived from slot buckets (more accurate than assuming 3 credits per course)
    total_required_credits = (
        sum(v.get("required", 0) for v in category_progress.get("majors", {}).values())
        + sum(v.get("required", 0) for v in category_progress.get("minors", {}).values())
        + int(category_progress.get("gen_ed", {}).get("required", 0) or 0)
        + int(category_progress.get("foundation", {}).get("required", 0) or 0)
    )
    total_completed_credits = (
        sum(v.get("completed", 0) for v in category_progress.get("majors", {}).values())
        + sum(v.get("completed", 0) for v in category_progress.get("minors", {}).values())
        + int(category_progress.get("gen_ed", {}).get("completed", 0) or 0)
        + int(category_progress.get("foundation", {}).get("completed", 0) or 0)
    )
    _apply_manual_credit_progress(category_progress, manual_credit_breakdown)
    total_completed_credits += total_manual_credits

    course_reasons = {}
    for code, entry in course_outputs.items():
        if entry["satisfies"]:
            course_reasons[code] = "; ".join(entry["satisfies"])

    elective_recommendations = compute_elective_recommendations(
        catalog=catalog,
        majors=majors,
        minors=minors,
        completed_courses=completed_courses,
        planned_courses=planned_courses,
    )

    elective_course_codes: List[str] = []
    excel_elective_tags: Dict[str, List[str]] = {}
    excel_catalog = catalog.get("excel_catalog") or {}
    if excel_catalog:
        elective_entries = get_recommended_electives(
            excel_catalog=excel_catalog,
            selected_majors=majors,
            selected_minors=minors,
        )
        elective_entries = _limit_business_administration_non_bus_elective_candidates(elective_entries, majors)
        excel_elective_tags = get_selected_program_elective_tags(
            excel_catalog=excel_catalog,
            selected_majors=majors,
            selected_minors=minors,
        )
        elective_course_codes = sorted({
            entry.get("code")
            for entry in elective_entries
            if isinstance(entry.get("code"), str)
        })
        if elective_course_codes and catalog_courses:
            elective_course_codes = [c for c in elective_course_codes if c in catalog_courses]

    case_studies_codes = get_case_studies_gened_courses(excel_catalog)
    case_studies: List[Dict] = []
    if case_studies_codes:
        by_code = excel_catalog.get("by_code", {}) if isinstance(excel_catalog, dict) else {}
        for code in case_studies_codes:
            if code not in catalog_courses:
                continue
            tags = []
            if isinstance(by_code, dict):
                tags = (by_code.get(code) or {}).get("tags") or []
            case_studies.append(_excel_course_summary(catalog, code, tags))

    elective_placeholders = _collect_elective_placeholders(catalog, majors, minors)

    # Apply user overrides (manual add/remove/move) and top-up fillers if needed
    override_warnings: List[Dict] = []
    if overrides:
        semester_plan, override_warnings = _apply_plan_overrides(
            catalog=catalog,
            semester_plan=semester_plan,
            completed_courses=completed_courses,
            overrides=overrides,
            max_credits=max_credits,
            min_credits=min_credits,
            slots=slots,
            course_assignments=selection["course_assignments"],
            prereq_courses=prereq_only,
            source_reasons=source_reasons,
            allowed_auto=allowed_auto,
            retake_courses=normalized_retakes,
            occupied_credits_by_term=occupied_credits_by_term,
        )
        _ensure_instance_ids(semester_plan)

    semester_plan = _dedupe_semester_plan(catalog, semester_plan, completed_courses)
    _ensure_instance_ids(semester_plan)
    _apply_latest_attempt_credit_rule(
        catalog=catalog,
        semester_plan=semester_plan,
        completed_courses=completed_courses,
    )
    effective_completed_courses = _effective_completed_courses_after_plan(completed_courses, semester_plan)

    # Enforce hard cap on total terms
    if len(semester_plan) > max_terms_remaining:
        semester_plan = semester_plan[:max_terms_remaining]
    _apply_latest_attempt_credit_rule(
        catalog=catalog,
        semester_plan=semester_plan,
        completed_courses=completed_courses,
    )

    minor_alerts = _compute_minor_alerts(
        catalog=catalog,
        majors=majors,
        minors=minors,
        completed_courses=completed_courses,
        in_progress_courses=normalized_in_progress,
        semester_plan=semester_plan,
    )
    minor_suggestions = compute_minor_suggestions(
        catalog=catalog,
        majors=majors,
        minors=minors,
        completed_courses=completed_courses,
        in_progress_courses=normalized_in_progress,
        semester_plan=semester_plan,
    )

    warnings = _compute_prereq_warnings(catalog, semester_plan, completed_courses)
    if override_warnings:
        warnings.extend(override_warnings)

    validation_errors = validate_plan(
        catalog=catalog,
        semester_plan=semester_plan,
        completed_courses=completed_courses,
        start_term=(base_season, base_year),
        min_credits=min_credits,
        max_credits=max_credits,
        strict_prereqs=strict_prereqs,
        remaining_slots=set(selection.get("remaining_slots") or []),
        slots=slots,
        occupied_credits_by_term=occupied_credits_by_term,
    )
    is_valid = True
    validation_errors_out: List[str] = []
    if validation_errors:
        is_valid = False
        validation_errors_out = validation_errors

    if excel_elective_tags:
        for term in semester_plan:
            for course in term.get("courses", []) or []:
                code = course.get("code")
                if not isinstance(code, str):
                    continue
                matched = excel_elective_tags.get(code) or []
                if matched:
                    course["excel_elective_tags"] = list(matched)

    effective_completed_courses = _effective_completed_courses_after_plan(completed_courses, semester_plan)
    completed_slots = {
        sid
        for sid, course in selection["slot_assignment"].items()
        if course in effective_completed_courses
    }
    completed_count = len(completed_slots)
    remaining_count = max(0, total_required - completed_count)
    gen_ed_status = _gen_ed_status(slots, selection["slot_assignment"], effective_completed_courses)
    category_progress = _category_credit_progress(
        catalog,
        slots,
        selection["slot_assignment"],
        effective_completed_courses,
        waived_courses,
        selected_majors=majors,
    )
    total_required_credits = (
        sum(v.get("required", 0) for v in category_progress.get("majors", {}).values())
        + sum(v.get("required", 0) for v in category_progress.get("minors", {}).values())
        + int(category_progress.get("gen_ed", {}).get("required", 0) or 0)
        + int(category_progress.get("foundation", {}).get("required", 0) or 0)
    )
    total_completed_credits = (
        sum(v.get("completed", 0) for v in category_progress.get("majors", {}).values())
        + sum(v.get("completed", 0) for v in category_progress.get("minors", {}).values())
        + int(category_progress.get("gen_ed", {}).get("completed", 0) or 0)
        + int(category_progress.get("foundation", {}).get("completed", 0) or 0)
    )
    _apply_manual_credit_progress(category_progress, manual_credit_breakdown)
    total_completed_credits += total_manual_credits

    return {
        "majors": majors,
        "minors": minors,
        "completed_courses": sorted(completed_courses),
        "remaining_courses": [
            c for term in semester_plan
            for c in [course.get("code") if isinstance(course, dict) else None for course in term.get("courses", [])]
            if c and c not in effective_completed_courses
        ],
        "semester_plan": semester_plan,
        "minor_alerts": minor_alerts,
        "minor_suggestions": minor_suggestions,
        "elective_recommendations": elective_recommendations,
        "elective_course_codes": elective_course_codes,
        "excel_elective_tags": excel_elective_tags,
        "elective_placeholders": elective_placeholders,
        "gened_discovery": {
            "case_studies_textual_analysis": case_studies,
        },
        "summary": {
            "total_required": total_required,
            "completed": completed_count,
            "remaining": remaining_count,
            "total_required_credits": int(total_required_credits),
            "completed_credits": int(total_completed_credits),
        },
        "gen_ed_status": gen_ed_status,
        "category_progress": category_progress,
        "course_reasons": course_reasons,
        "warnings": warnings,
        "is_valid": is_valid,
        "validation_errors": validation_errors_out,
    }

def _apply_plan_overrides(
    catalog: Dict,
    semester_plan: List[Dict],
    completed_courses: Set[str],
    overrides: Dict | None,
    max_credits: int,
    min_credits: int,
    slots: Dict,
    course_assignments: Dict[str, Set[str]],
    prereq_courses: Set[str],
    source_reasons: Dict[str, str],
    allowed_auto: Set[str],
    retake_courses: Set[str] | None,
    occupied_credits_by_term: Dict[str, int] | None = None,
) -> Tuple[List[Dict], List[Dict]]:
    """Apply user overrides (add/remove/move) to a generated semester_plan.

    Returns (updated_semester_plan, override_warnings).
    Notes:
    - We do NOT fail on constraint violations; we emit warnings.
    - If min credits are violated after removals, we attempt to top-up with FREE_ELECTIVE fillers.
    """
    if not overrides:
        return semester_plan, []

    # Build quick lookup
    term_map = {t["term"]: t for t in semester_plan}
    all_terms_in_order = [t["term"] for t in semester_plan]
    catalog_courses = _planning_course_pool(catalog)
    occupied = occupied_credits_by_term or {}
    integrity = catalog.get("excel_integrity")
    excel_only_codes: Set[str] = set()
    if isinstance(integrity, dict):
        excel_only = integrity.get("excel_only")
        if isinstance(excel_only, list):
            excel_only_codes = {code for code in excel_only if isinstance(code, str)}
    retake_set = {
        _normalize_course_code(code)
        for code in (retake_courses or set())
        if isinstance(code, str)
    }

    def occupied_credits_for_term(term_label: str) -> int:
        return max(0, int(occupied.get(term_label, 0) or 0))

    def available_bounds(term_obj: Dict) -> Tuple[int, int]:
        term_label = term_obj.get("term", "")
        occupied_credits = occupied_credits_for_term(term_label)
        available_min = max(0, min_credits - occupied_credits)
        available_max = max(0, max_credits - occupied_credits)
        return available_min, available_max

    def ensure_term(term: str) -> None:
        if term in term_map:
            return
        term_obj = {"term": term, "courses": [], "credits": 0}
        semester_plan.append(term_obj)
        semester_plan.sort(key=lambda t: _term_label_index(t.get("term", "")))
        term_map.clear()
        term_map.update({t["term"]: t for t in semester_plan})
        all_terms_in_order.clear()
        all_terms_in_order.extend([t["term"] for t in semester_plan])

    def course_credits(code: str) -> int:
        meta = catalog.get("course_meta", {}).get(code) or {}
        return int(meta.get("credits") or 3)

    def _normalize_term_for_compare(term_label: str | None) -> str:
        if not isinstance(term_label, str):
            return ""
        return re.sub(r"\s+", " ", term_label.strip()).lower()

    def _offered_terms_for_course(code: str) -> List[str]:
        terms: List[str] = []
        meta = catalog.get("course_meta", {}).get(code) or {}
        raw_terms = meta.get("semester_availability")
        if isinstance(raw_terms, list):
            terms.extend(
                term.strip()
                for term in raw_terms
                if isinstance(term, str) and term.strip()
            )
        if terms:
            return list(dict.fromkeys(terms))
        excel_record = _excel_course_record(catalog, code)
        excel_terms = excel_record.get("semester_availability") if isinstance(excel_record, dict) else None
        if isinstance(excel_terms, list):
            terms.extend(
                term.strip()
                for term in excel_terms
                if isinstance(term, str) and term.strip()
            )
        return list(dict.fromkeys(terms))

    def ensure_course_obj(code: str, term: str | None = None, instance_id: str | None = None) -> Dict:
        obj = _build_course_output(
            catalog=catalog,
            code=code,
            slots=slots,
            course_assignments=course_assignments,
            prereq_courses=prereq_courses,
            source_reasons=source_reasons,
        )
        if instance_id:
            obj["instance_id"] = instance_id
        elif term:
            obj["instance_id"] = _course_instance_id(term, code, "override")
        return obj

    override_warnings: List[Dict] = []
    suppressed_terms: Set[str] = set()

    # Normalize overrides
    adds = overrides.get("add") or []
    removes = overrides.get("remove") or []
    moves = overrides.get("move") or []

    # Apply removals (by term if provided, otherwise anywhere)
    for r in removes:
        code = r.get("code")
        instance_id = r.get("instance_id")
        term = r.get("term")
        if not instance_id and not code:
            continue
        removed_any = False
        removed_code = None
        for t in semester_plan:
            if term and t["term"] != term:
                continue
            new_courses = []
            for c in t["courses"]:
                match = False
                if instance_id:
                    match = c.get("instance_id") == instance_id
                elif code:
                    match = c.get("code") == code
                if match:
                    removed_any = True
                    removed_code = c.get("code") if isinstance(c, dict) else code
                    if c.get("type") == "FREE_ELECTIVE" or _is_free_elective(str(c.get("code", ""))):
                        suppressed_terms.add(t["term"])
                    continue
                new_courses.append(c)
            t["courses"] = new_courses
        if not removed_any and instance_id and code:
            for t in semester_plan:
                if term and t["term"] != term:
                    continue
                new_courses = []
                for c in t["courses"]:
                    if c.get("code") == code:
                        removed_any = True
                        removed_code = code
                        if c.get("type") == "FREE_ELECTIVE" or _is_free_elective(str(c.get("code", ""))):
                            suppressed_terms.add(t["term"])
                        continue
                    new_courses.append(c)
                t["courses"] = new_courses

        if not removed_any and code:
            for t in semester_plan:
                new_courses = []
                for c in t["courses"]:
                    if c.get("code") == code:
                        removed_any = True
                        removed_code = code
                        if c.get("type") == "FREE_ELECTIVE" or _is_free_elective(str(c.get("code", ""))):
                            suppressed_terms.add(t["term"])
                        continue
                    new_courses.append(c)
                t["courses"] = new_courses

        if not removed_any:
            override_warnings.append(
                _make_warning("OVERRIDE_REMOVE_NOT_FOUND", course=code or removed_code, term=term)
            )

    # Apply moves
    for mv in moves:
        code = mv.get("code")
        instance_id = mv.get("instance_id")
        from_term = mv.get("from_term")
        to_term = mv.get("to_term")
        if not from_term or not to_term:
            continue
        if from_term not in term_map or to_term not in term_map:
            if from_term not in term_map:
                override_warnings.append(
                    _make_warning(
                        "OVERRIDE_MOVE_TERM_NOT_FOUND",
                        course=code,
                        **{"from": from_term, "to": to_term},
                    )
                )
                continue
            ensure_term(to_term)
        from_courses = term_map[from_term]["courses"]
        course_obj = None
        if instance_id:
            for c in from_courses:
                if c.get("instance_id") == instance_id:
                    course_obj = c
                    break
        elif code:
            for c in from_courses:
                if c.get("code") == code:
                    course_obj = c
                    break
        if not course_obj:
            override_warnings.append(
                _make_warning(
                    "OVERRIDE_MOVE_NOT_FOUND",
                    course=code,
                    **{"from": from_term, "to": to_term},
                )
            )
            continue
        original_from_courses = list(term_map[from_term]["courses"])
        original_to_courses = list(term_map[to_term]["courses"])
        if instance_id:
            term_map[from_term]["courses"] = [
                c for c in from_courses if c.get("instance_id") != instance_id
            ]
        else:
            term_map[from_term]["courses"] = [
                c for c in from_courses if c.get("code") != code
            ]
        if instance_id:
            exists = any(c.get("instance_id") == instance_id for c in term_map[to_term]["courses"])
        elif code:
            exists = any(c.get("code") == code for c in term_map[to_term]["courses"])
        else:
            exists = False
        if not exists:
            term_map[to_term]["courses"].append(course_obj)
        sequence_errors = _textual_analysis_sequence_errors(catalog, semester_plan, completed_courses)
        if sequence_errors:
            term_map[from_term]["courses"] = original_from_courses
            term_map[to_term]["courses"] = original_to_courses
            override_warnings.append(
                _make_warning(
                    "OVERRIDE_MOVE_INELIGIBLE",
                    course=code,
                    **{"from": from_term, "to": to_term},
                )
            )

    # Apply adds
    for a in adds:
        code = a.get("code")
        term = a.get("term")
        instance_id = a.get("instance_id")
        gen_ed_category = a.get("gen_ed_category")
        is_retake = bool(a.get("is_retake"))
        if not code or not term:
            continue
        normalized_code = _normalize_course_code(code)
        if not is_retake and normalized_code in completed_courses and normalized_code not in retake_set:
            override_warnings.append(_make_warning("OVERRIDE_ADD_ALREADY_COMPLETED", course=code, term=term))
            continue
        if code in excel_only_codes and not is_retake:
            offered_terms = _offered_terms_for_course(code)
            normalized_target = _normalize_term_for_compare(_normalize_term_label(term) or term)
            if offered_terms and normalized_target and not any(
                _normalize_term_for_compare(offered) == normalized_target
                for offered in offered_terms
            ):
                override_warnings.append(
                    _make_warning(
                        "OVERRIDE_ADD_TERM_UNAVAILABLE",
                        course=code,
                        term=term,
                        offered_terms=offered_terms,
                    )
                )
                continue
        manual_gened_override_known = bool(gen_ed_category) and bool(
            _excel_course_record(catalog, normalized_code)
        )
        if not _is_free_elective(code) and code not in allowed_auto:
            if code not in catalog_courses and not manual_gened_override_known:
                override_warnings.append(_make_warning("OVERRIDE_ADD_UNKNOWN", course=code, term=term))
                continue
            if not gen_ed_category:
                # Manual override: allow user-selected electives to replace FREE ELECTIVE slots.
                source_reasons.setdefault(code, SOURCE_REASON_FREE)
        if term not in term_map:
            ensure_term(term)
        # Preserve existing occurrences for explicit retakes.
        if not is_retake and normalized_code not in retake_set:
            for t in semester_plan:
                if t["term"] == term:
                    continue
                t["courses"] = [c for c in t["courses"] if c.get("code") != code]
        if instance_id:
            if is_retake:
                exists = any(c.get("instance_id") == instance_id for c in term_map[term]["courses"])
            else:
                exists = any(
                    c.get("instance_id") == instance_id or c.get("code") == code
                    for c in term_map[term]["courses"]
                )
        else:
            if is_retake:
                exists = False
            else:
                exists = any(c.get("code") == code for c in term_map[term]["courses"])
        if not exists:
            if is_retake:
                retake_obj = ensure_course_obj(code, term=term, instance_id=instance_id)
                tags = retake_obj.get("tags") if isinstance(retake_obj.get("tags"), list) else []
                tags = [tag for tag in tags if isinstance(tag, str)]
                if "Retake" not in tags:
                    tags.append("Retake")
                retake_obj["tags"] = tags
                retake_obj["is_retake"] = True
                term_map[term]["courses"].append(retake_obj)
            elif gen_ed_category:
                source_reasons[code] = SOURCE_REASON_GENED
                term_map[term]["courses"].append({
                    "code": code,
                    "name": _course_name(catalog, code),
                    "credits": _course_credits(catalog, code),
                    "tags": _planned_course_tags(catalog, code),
                    "satisfies": [f"GenEd: {gen_ed_category}"],
                    "type": "GENED",
                    "source_reason": SOURCE_REASON_GENED,
                    "instance_id": instance_id or _course_instance_id(term, code, "override"),
                })
            else:
                term_map[term]["courses"].append(ensure_course_obj(code, term=term, instance_id=instance_id))

    semester_plan = _dedupe_semester_plan(catalog, semester_plan, completed_courses)
    _ensure_instance_ids(semester_plan)
    _apply_latest_attempt_credit_rule(
        catalog=catalog,
        semester_plan=semester_plan,
        completed_courses=completed_courses,
    )

    # Recompute credits and enforce max/min via warnings and FREE ELECTIVE placeholders
    used_codes: Set[str] = set()
    for t in semester_plan:
        for c in (t.get("courses", []) or []):
            if not isinstance(c, dict):
                continue
            code = c.get("code")
            if isinstance(code, str):
                used_codes.add(code)
    used_codes |= set(completed_courses)
    next_free_code = _free_elective_code_generator(used_codes)

    def add_filler(term_obj: Dict) -> bool:
        _, available_max = available_bounds(term_obj)
        if term_obj["credits"] + 3 > available_max:
            return False
        code = next_free_code()
        term_obj["courses"].append({
            "code": code,
            "name": "Free Elective",
            "credits": 3,
            "tags": ["Planned"],
            "satisfies": [],
            "type": "FREE_ELECTIVE",
            "source_reason": SOURCE_REASON_FREE,
            "instance_id": _course_instance_id(term_obj.get("term", ""), code, "filler"),
        })
        term_obj["credits"] += 3
        return True

    def term_has_only_retakes(term_obj: Dict) -> bool:
        courses = term_obj.get("courses", []) or []
        has_retake = False
        for course in courses:
            if not isinstance(course, dict):
                return False
            if course.get("is_retake") is True and _planned_course_credits(catalog, course) == 0:
                has_retake = True
                continue
            return False
        return has_retake

    for term_obj in semester_plan:
        credits = 0
        for c in term_obj["courses"]:
            credits += _planned_course_credits(catalog, c)
        term_obj["credits"] = credits
        occupied_credits = occupied_credits_for_term(term_obj.get("term", ""))
        total_credits = credits + occupied_credits
        available_min, _ = available_bounds(term_obj)
        if total_credits > max_credits:
            override_warnings.append(
                _make_warning(
                    "TERM_CREDITS_EXCEED_MAX",
                    course=None,
                    term=term_obj["term"],
                    credits=total_credits,
                    max=max_credits,
                )
            )
        if total_credits < min_credits:
            if term_has_only_retakes(term_obj):
                continue
            # top up only planned credits budget left after in-progress occupancy.
            if term_obj.get("term") not in suppressed_terms:
                while term_obj["credits"] < available_min:
                    if not add_filler(term_obj):
                        break
            total_after_fill = term_obj["credits"] + occupied_credits
            if total_after_fill < min_credits:
                override_warnings.append(
                    _make_warning(
                        "TERM_CREDITS_BELOW_MIN",
                        course=None,
                        term=term_obj["term"],
                        credits=total_after_fill,
                        min=min_credits,
                    )
                )

    return semester_plan, override_warnings
  
