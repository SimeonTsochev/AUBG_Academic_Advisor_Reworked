from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
import json
import re

BUSINESS_MAJOR_NAME = "Business Administration"
GENERAL_BUSINESS_CONCENTRATION = "General"

BACKEND_DIR = Path(__file__).resolve().parent
DATA_DIR = BACKEND_DIR / "data"
BUSINESS_CONCENTRATIONS_PATH = DATA_DIR / "business_concentrations.json"

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

_COURSE_CODE_RE = re.compile(r"^([A-Z]{2,4})\s?(\d{3,4}[A-Z]?)$")


def _normalize_text(value: object) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_course_code(value: object) -> str:
    text = str(value or "").strip().upper()
    match = _COURSE_CODE_RE.match(text)
    if not match:
        return text
    return f"{match.group(1)} {match.group(2)}"


def _empty_config() -> Dict[str, Any]:
    return {
        "major": BUSINESS_MAJOR_NAME,
        "general_label": GENERAL_BUSINESS_CONCENTRATION,
        "concentrations": {
            GENERAL_BUSINESS_CONCENTRATION: {
                "label": GENERAL_BUSINESS_CONCENTRATION,
                "rules": [],
            }
        },
    }


def _normalize_config(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    config = _empty_config()
    if not isinstance(payload, dict):
        return config

    major = str(payload.get("major") or BUSINESS_MAJOR_NAME).strip()
    config["major"] = major or BUSINESS_MAJOR_NAME

    general_label = str(payload.get("general_label") or GENERAL_BUSINESS_CONCENTRATION).strip()
    config["general_label"] = general_label or GENERAL_BUSINESS_CONCENTRATION

    concentrations = payload.get("concentrations")
    if isinstance(concentrations, dict):
        normalized_concentrations: Dict[str, Dict[str, Any]] = {}
        for name, raw_entry in concentrations.items():
            if not isinstance(name, str):
                continue
            entry = raw_entry if isinstance(raw_entry, dict) else {}
            rules = entry.get("rules")
            normalized_concentrations[name] = {
                "label": str(entry.get("label") or name).strip() or name,
                "rules": [rule for rule in (rules or []) if isinstance(rule, dict)],
            }
        if normalized_concentrations:
            config["concentrations"] = normalized_concentrations

    if config["general_label"] not in config["concentrations"]:
        config["concentrations"][config["general_label"]] = {
            "label": config["general_label"],
            "rules": [],
        }
    return config


@lru_cache(maxsize=1)
def load_business_concentrations() -> Dict[str, Any]:
    if not BUSINESS_CONCENTRATIONS_PATH.exists():
        return _empty_config()
    with BUSINESS_CONCENTRATIONS_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return _normalize_config(payload if isinstance(payload, dict) else None)


def _config(catalog: Dict[str, Any] | None = None) -> Dict[str, Any]:
    raw = catalog.get("business_concentrations") if isinstance(catalog, dict) else None
    if isinstance(raw, dict):
        return _normalize_config(raw)
    return load_business_concentrations()


def available_business_concentrations(catalog: Dict[str, Any] | None = None) -> List[str]:
    return list((_config(catalog).get("concentrations") or {}).keys())


def is_business_major_selected(majors: Iterable[str] | None) -> bool:
    major_norm = _normalize_text(BUSINESS_MAJOR_NAME)
    return any(_normalize_text(name) == major_norm for name in (majors or []))


def normalize_business_concentration(
    value: object,
    catalog: Dict[str, Any] | None = None,
) -> str:
    config = _config(catalog)
    concentrations = config.get("concentrations") or {}
    if isinstance(value, str):
        needle = _normalize_text(value)
        for name in concentrations.keys():
            if _normalize_text(name) == needle:
                return name
    return str(config.get("general_label") or GENERAL_BUSINESS_CONCENTRATION)


def active_business_concentration(
    majors: Iterable[str] | None,
    value: object,
    catalog: Dict[str, Any] | None = None,
) -> Optional[str]:
    if not is_business_major_selected(majors):
        return None
    return normalize_business_concentration(value, catalog=catalog)


def get_business_concentration_required_courses(
    catalog: Dict[str, Any],
    majors: Iterable[str] | None,
    business_concentration: object,
) -> List[str]:
    concentration = active_business_concentration(majors, business_concentration, catalog=catalog)
    if concentration is None:
        return []

    config = _config(catalog)
    if concentration == config.get("general_label"):
        return []

    rules = (((config.get("concentrations") or {}).get(concentration) or {}).get("rules") or [])
    required_courses: List[str] = []
    seen: Set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("type") or "").strip().lower() != "required_course":
            continue
        code = _normalize_course_code(rule.get("course"))
        if not code or code in seen:
            continue
        seen.add(code)
        required_courses.append(code)
    return required_courses


def _excel_by_code(catalog: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    excel_catalog = catalog.get("excel_catalog") or catalog.get("excel_course_catalog") or {}
    by_code = excel_catalog.get("by_code") if isinstance(excel_catalog, dict) else {}
    return by_code if isinstance(by_code, dict) else {}


def _catalog_course_codes(catalog: Dict[str, Any]) -> Set[str]:
    codes: Set[str] = set()
    for code in (_excel_by_code(catalog) or {}).keys():
        if isinstance(code, str):
            normalized = _normalize_course_code(code)
            if normalized:
                codes.add(normalized)
    for code in (catalog.get("courses") or {}).keys():
        if isinstance(code, str):
            normalized = _normalize_course_code(code)
            if normalized:
                codes.add(normalized)
    return codes


def _course_title(catalog: Dict[str, Any], code: str) -> str:
    normalized = _normalize_course_code(code)
    excel_entry = _excel_by_code(catalog).get(normalized) or {}
    title = excel_entry.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()

    meta = (catalog.get("course_meta") or {}).get(normalized) or {}
    for key in ("title", "name"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    course_entry = (catalog.get("courses") or {}).get(normalized) or {}
    name = course_entry.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return normalized


def _course_credits(catalog: Dict[str, Any], code: str) -> int:
    normalized = _normalize_course_code(code)
    for source in (
        (_excel_by_code(catalog).get(normalized) or {}),
        ((catalog.get("course_meta") or {}).get(normalized) or {}),
        ((catalog.get("courses") or {}).get(normalized) or {}),
    ):
        raw = source.get("credits")
        if isinstance(raw, bool):
            continue
        if isinstance(raw, (int, float)) and raw > 0:
            return int(round(float(raw)))
        if isinstance(raw, str):
            match = re.search(r"\d+(?:\.\d+)?", raw)
            if match:
                try:
                    value = float(match.group(0))
                except ValueError:
                    value = 0
                if value > 0:
                    return int(round(value))
    return 3


def _course_prefix(code: str) -> str:
    normalized = _normalize_course_code(code)
    parts = normalized.split()
    return parts[0] if parts else ""


def _course_number(code: str) -> Optional[int]:
    normalized = _normalize_course_code(code)
    match = re.match(r"^[A-Z]{2,4}\s?(\d{3,4})", normalized)
    if not match:
        return None
    return int(match.group(1))


def _course_search_text(catalog: Dict[str, Any], code: str) -> str:
    normalized = _normalize_course_code(code)
    entry = _excel_by_code(catalog).get(normalized) or {}
    text_parts = [
        normalized,
        _course_title(catalog, normalized),
        entry.get("_search_blob") or "",
        " ".join(entry.get("tags") or []),
        " ".join(entry.get("area_of_study_tags") or []),
    ]
    return _normalize_text(" ".join(str(part) for part in text_parts if part))


def _business_required_courses(catalog: Dict[str, Any]) -> Set[str]:
    majors = catalog.get("majors") or {}
    if not isinstance(majors, dict):
        return set()
    for name, data in majors.items():
        if _normalize_text(name) != _normalize_text(BUSINESS_MAJOR_NAME):
            continue
        required = (data or {}).get("required_courses") or []
        if not isinstance(required, list):
            return set()
        return {
            _normalize_course_code(code)
            for code in required
            if isinstance(code, str) and _normalize_course_code(code)
        }
    return set()


def _is_business_upper_level_elective(code: str) -> bool:
    normalized = _normalize_course_code(code)
    prefix = _course_prefix(normalized)
    number = _course_number(normalized)
    return prefix in {"BUS", "ENT"} and number is not None and 3000 <= number <= 4999


def _counts_as_general_business_elective(catalog: Dict[str, Any], code: str) -> bool:
    normalized = _normalize_course_code(code)
    if not normalized:
        return False
    if normalized in _business_required_courses(catalog):
        return False
    if normalized in BUSINESS_ADMIN_NON_BUS_ELECTIVES:
        return True
    if normalized in BUSINESS_ADMIN_THESIS_PROJECT_ELECTIVES:
        return True
    return _is_business_upper_level_elective(normalized)


def _manual_match_entries(catalog: Dict[str, Any], concentration: str, key: str) -> List[Dict[str, str]]:
    policy = catalog.get("policy_overrides") or {}
    raw_matches = policy.get("business_concentration_manual_matches") or {}
    if not isinstance(raw_matches, dict):
        return []

    target_concentration: Optional[Dict[str, Any]] = None
    concentration_norm = _normalize_text(concentration)
    for name, value in raw_matches.items():
        if _normalize_text(name) == concentration_norm and isinstance(value, dict):
            target_concentration = value
            break
    if target_concentration is None:
        return []

    raw_entries = target_concentration.get(key) or []
    if not isinstance(raw_entries, list):
        return []

    entries: List[Dict[str, str]] = []
    for entry in raw_entries:
        if isinstance(entry, str):
            code = _normalize_course_code(entry)
            if code:
                entries.append({"code": code, "note": ""})
            continue
        if not isinstance(entry, dict):
            continue
        code = _normalize_course_code(entry.get("code"))
        if not code:
            continue
        note = str(entry.get("note") or "").strip()
        entries.append({"code": code, "note": note})
    return entries


def _selector_match_notes(
    catalog: Dict[str, Any],
    concentration: str,
    selector: Dict[str, Any],
    code: str,
) -> List[str]:
    selector_type = str(selector.get("type") or "").strip().lower()
    if selector_type != "manual_match":
        return []
    key = str(selector.get("key") or selector.get("match_key") or "").strip()
    if not key:
        return []
    notes = ["Manual review needed"]
    for entry in _manual_match_entries(catalog, concentration, key):
        if entry["code"] != _normalize_course_code(code):
            continue
        if entry["note"]:
            notes.append(entry["note"])
    return list(dict.fromkeys(note for note in notes if note))


def _selector_matches_course(
    catalog: Dict[str, Any],
    concentration: str,
    selector: Dict[str, Any],
    code: str,
) -> bool:
    normalized = _normalize_course_code(code)
    if not normalized:
        return False

    selector_type = str(selector.get("type") or "").strip().lower()
    if selector_type == "course":
        return normalized == _normalize_course_code(selector.get("course"))

    if selector_type == "topic_pattern":
        pattern = _normalize_text(selector.get("pattern"))
        if not pattern:
            return False
        prefixes = selector.get("prefixes") or []
        if isinstance(prefixes, list):
            prefix_set = {
                str(prefix).strip().upper()
                for prefix in prefixes
                if isinstance(prefix, str) and str(prefix).strip()
            }
            if prefix_set and _course_prefix(normalized) not in prefix_set:
                return False
        return pattern in _course_search_text(catalog, normalized)

    if selector_type == "manual_match":
        key = str(selector.get("key") or selector.get("match_key") or "").strip()
        if not key:
            return False
        return any(
            entry["code"] == normalized
            for entry in _manual_match_entries(catalog, concentration, key)
        )

    return False


def _rule_matches_course(
    catalog: Dict[str, Any],
    concentration: str,
    rule: Dict[str, Any],
    code: str,
) -> Tuple[bool, List[str]]:
    normalized = _normalize_course_code(code)
    if not normalized:
        return False, []

    matched = False
    notes: List[str] = []

    prefixes = rule.get("prefixes") or []
    if isinstance(prefixes, list):
        prefix_set = {
            str(prefix).strip().upper()
            for prefix in prefixes
            if isinstance(prefix, str) and str(prefix).strip()
        }
        if prefix_set and _course_prefix(normalized) in prefix_set:
            matched = True

    selectors = rule.get("selectors") or []
    if isinstance(selectors, list):
        for selector in selectors:
            if not isinstance(selector, dict):
                continue
            if _selector_matches_course(catalog, concentration, selector, normalized):
                matched = True
                notes.extend(_selector_match_notes(catalog, concentration, selector, normalized))

    note = str(rule.get("note") or "").strip()
    if matched and note:
        notes.append(note)

    return matched, list(dict.fromkeys(note for note in notes if note))


def _minor_name_matches(selected_minors: Iterable[str], target_minor: str) -> bool:
    target = _normalize_text(target_minor)
    return any(_normalize_text(minor) == target for minor in selected_minors)


def classify_business_course(
    catalog: Dict[str, Any],
    code: str,
    majors: Iterable[str] | None,
    minors: Iterable[str] | None,
    business_concentration: object,
) -> Optional[Dict[str, Any]]:
    if not is_business_major_selected(majors):
        return None

    normalized = _normalize_course_code(code)
    if not normalized:
        return None

    concentration = active_business_concentration(majors, business_concentration, catalog=catalog)
    config = _config(catalog)
    concentration_rules = (
        ((config.get("concentrations") or {}).get(concentration) or {}).get("rules") or []
        if concentration
        else []
    )

    required_for_bus_core = normalized in _business_required_courses(catalog)
    required_for_concentration = False
    elective_for_concentration = False
    manual_review = False
    badges: List[str] = []

    if concentration and concentration != config.get("general_label"):
        for rule in concentration_rules:
            if not isinstance(rule, dict):
                continue
            rule_type = str(rule.get("type") or "").strip().lower()
            if rule_type == "required_course" and normalized == _normalize_course_code(rule.get("course")):
                required_for_concentration = True
            elif rule_type in {"credits_from_pool", "subset_credit_cap"}:
                matched, notes = _rule_matches_course(catalog, concentration, rule, normalized)
                if rule_type == "credits_from_pool" and matched:
                    elective_for_concentration = True
                if any("manual review" in _normalize_text(note) for note in notes):
                    manual_review = True
                for note in notes:
                    if note not in badges:
                        badges.append(note)

        if required_for_concentration:
            badges.append(f"Required for {concentration} Concentration")
        elif elective_for_concentration:
            badges.append(f"Elective for {concentration} Concentration")

    counts_as_bus_elective = _counts_as_general_business_elective(catalog, normalized) and not required_for_concentration

    if normalized in BUSINESS_ADMIN_NON_BUS_ELECTIVES and "Max 3 non-BUS credits" not in badges:
        badges.append("Max 3 non-BUS credits")

    if manual_review and "Manual review needed" not in badges:
        badges.append("Manual review needed")

    if not badges and not required_for_bus_core and not counts_as_bus_elective:
        return None

    return {
        "concentration": concentration,
        "required_for_bus_core": required_for_bus_core,
        "required_for_concentration": required_for_concentration,
        "elective_for_concentration": elective_for_concentration,
        "counts_as_bus_elective": counts_as_bus_elective,
        "manual_review": manual_review,
        "badges": badges,
    }


def _status_map(
    completed_courses: Iterable[str],
    planned_courses: Iterable[str],
) -> Dict[str, str]:
    status: Dict[str, str] = {}
    for code in planned_courses:
        normalized = _normalize_course_code(code)
        if normalized:
            status[normalized] = "planned"
    for code in completed_courses:
        normalized = _normalize_course_code(code)
        if normalized:
            status[normalized] = "completed"
    return status


def _pool_candidates(
    catalog: Dict[str, Any],
    concentration: str,
    rule: Dict[str, Any],
    status_by_code: Dict[str, str],
    used_codes: Set[str],
    cap_rules: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for code in sorted(_catalog_course_codes(catalog)):
        if code in used_codes:
            continue
        status = status_by_code.get(code)
        if status not in {"completed", "planned"}:
            continue
        matched, notes = _rule_matches_course(catalog, concentration, rule, code)
        if not matched:
            continue
        matched_caps = [
            cap_rule
            for cap_rule in cap_rules
            if _rule_matches_course(catalog, concentration, cap_rule, code)[0]
        ]
        candidates.append({
            "code": code,
            "title": _course_title(catalog, code),
            "credits": _course_credits(catalog, code),
            "status": status,
            "notes": notes,
            "matched_caps": matched_caps,
        })
    candidates.sort(
        key=lambda entry: (
            len(entry["matched_caps"]),
            0 if entry["status"] == "completed" else 1,
            -int(entry["credits"] or 0),
            entry["code"],
        )
    )
    return candidates


def _evaluate_pool_rule(
    catalog: Dict[str, Any],
    concentration: str,
    rule: Dict[str, Any],
    status_by_code: Dict[str, str],
    used_codes: Set[str],
    cap_rules: List[Dict[str, Any]],
) -> Dict[str, Any]:
    required_credits = int(rule.get("required_credits") or 0)
    courses_required = int(rule.get("courses_required") or 0)

    cap_remaining: Dict[str, int] = {
        str(cap_rule.get("label") or cap_rule.get("id") or index): int(cap_rule.get("max_credits") or 0)
        for index, cap_rule in enumerate(cap_rules)
    }

    counted_courses: List[Dict[str, Any]] = []
    counted_course_codes: List[str] = []
    counted_credits = 0
    counted_course_count = 0
    remaining_credits = required_credits
    remaining_courses = courses_required
    notes: List[str] = []

    for candidate in _pool_candidates(catalog, concentration, rule, status_by_code, used_codes, cap_rules):
        if remaining_credits <= 0 and remaining_courses <= 0:
            break

        credits_available = int(candidate["credits"] or 0)
        if credits_available <= 0:
            continue

        for cap_rule in candidate["matched_caps"]:
            cap_key = str(cap_rule.get("label") or cap_rule.get("id") or "")
            if cap_key and cap_key in cap_remaining:
                credits_available = min(credits_available, cap_remaining[cap_key])

        if required_credits > 0:
            credits_available = min(credits_available, max(remaining_credits, 0))

        if credits_available <= 0:
            continue

        counted_credits += credits_available
        counted_course_count += 1
        remaining_credits = max(0, required_credits - counted_credits)
        remaining_courses = max(0, courses_required - counted_course_count)

        counted_courses.append({
            "code": candidate["code"],
            "title": candidate["title"],
            "credits": candidate["credits"],
            "counted_credits": credits_available,
            "status": candidate["status"],
        })
        counted_course_codes.append(candidate["code"])
        notes.extend(candidate["notes"])

        for cap_rule in candidate["matched_caps"]:
            cap_key = str(cap_rule.get("label") or cap_rule.get("id") or "")
            if cap_key and cap_key in cap_remaining:
                cap_remaining[cap_key] = max(0, cap_remaining[cap_key] - credits_available)
            cap_note = str(cap_rule.get("note") or "").strip()
            if cap_note:
                notes.append(cap_note)

    rule_note = str(rule.get("note") or "").strip()
    if rule_note:
        notes.append(rule_note)

    return {
        "id": str(rule.get("id") or rule.get("label") or "pool").strip() or "pool",
        "label": str(rule.get("label") or "Elective pool").strip() or "Elective pool",
        "required_credits": required_credits,
        "counted_credits": counted_credits,
        "remaining_credits": remaining_credits,
        "courses_required": courses_required,
        "counted_courses": counted_course_count,
        "remaining_courses": remaining_courses,
        "matched_courses": counted_courses,
        "counted_course_codes": counted_course_codes,
        "notes": list(dict.fromkeys(note for note in notes if note)),
    }


def build_business_concentration_audit(
    catalog: Dict[str, Any],
    majors: Iterable[str] | None,
    minors: Iterable[str] | None,
    business_concentration: object,
    completed_courses: Iterable[str] | None,
    planned_courses: Iterable[str] | None = None,
) -> Optional[Dict[str, Any]]:
    concentration = active_business_concentration(majors, business_concentration, catalog=catalog)
    if concentration is None:
        return None

    config = _config(catalog)
    concentration_entry = ((config.get("concentrations") or {}).get(concentration) or {})
    rules = concentration_entry.get("rules") or []
    status_by_code = _status_map(completed_courses or [], planned_courses or [])
    used_codes: Set[str] = set()

    required_courses: List[Dict[str, Any]] = []
    elective_pools: List[Dict[str, Any]] = []
    messages: List[Dict[str, str]] = []
    cap_rules_by_pool: Dict[str, List[Dict[str, Any]]] = {}

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("type") or "").strip().lower() != "subset_credit_cap":
            continue
        pool_key = str(rule.get("pool") or "").strip()
        if pool_key:
            cap_rules_by_pool.setdefault(pool_key, []).append(rule)

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule_type = str(rule.get("type") or "").strip().lower()

        if rule_type == "required_course":
            code = _normalize_course_code(rule.get("course"))
            if not code:
                continue
            status = status_by_code.get(code) or "missing"
            required_courses.append({
                "code": code,
                "title": _course_title(catalog, code),
                "credits": _course_credits(catalog, code),
                "status": status,
            })
            if status in {"completed", "planned"}:
                used_codes.add(code)
            continue

        if rule_type == "credits_from_pool":
            pool_id = str(rule.get("id") or rule.get("label") or "").strip()
            pool_progress = _evaluate_pool_rule(
                catalog=catalog,
                concentration=concentration,
                rule=rule,
                status_by_code=status_by_code,
                used_codes=used_codes,
                cap_rules=cap_rules_by_pool.get(pool_id, []),
            )
            elective_pools.append(pool_progress)
            used_codes.update(pool_progress.get("counted_course_codes") or [])
            if any("manual review" in _normalize_text(note) for note in pool_progress.get("notes") or []):
                messages.append({
                    "kind": "manual_review",
                    "message": f"{pool_progress['label']}: manual review needed.",
                })
            continue

        if rule_type == "forbidden_with_minor":
            target_minor = str(rule.get("minor") or "").strip()
            note = str(rule.get("note") or "").strip()
            if target_minor and _minor_name_matches(minors or [], target_minor):
                messages.append({
                    "kind": "conflict",
                    "message": note or f"{concentration} concentration cannot be combined with {target_minor}.",
                })
            continue

    missing_required_courses = [entry for entry in required_courses if entry["status"] == "missing"]
    remaining_required_course_credits = sum(int(entry["credits"] or 0) for entry in missing_required_courses)
    remaining_pool_credits = sum(int(pool.get("remaining_credits") or 0) for pool in elective_pools)
    remaining_pool_courses = sum(int(pool.get("remaining_courses") or 0) for pool in elective_pools)

    return {
        "selected": concentration,
        "required_courses": required_courses,
        "elective_pools": elective_pools,
        "messages": messages,
        "summary": {
            "missing_required_courses": len(missing_required_courses),
            "remaining_required_course_credits": remaining_required_course_credits,
            "remaining_pool_credits": remaining_pool_credits,
            "remaining_pool_courses": remaining_pool_courses,
            "_remaining_score": (
                remaining_required_course_credits * 100
                + len(missing_required_courses) * 1_000
                + remaining_pool_courses * 100
                + remaining_pool_credits
            ),
        },
    }


def business_concentration_messages(
    catalog: Dict[str, Any],
    majors: Iterable[str] | None,
    minors: Iterable[str] | None,
    business_concentration: object,
    completed_courses: Iterable[str] | None = None,
    planned_courses: Iterable[str] | None = None,
) -> List[Dict[str, str]]:
    audit = build_business_concentration_audit(
        catalog=catalog,
        majors=majors,
        minors=minors,
        business_concentration=business_concentration,
        completed_courses=completed_courses or [],
        planned_courses=planned_courses or [],
    )
    if not audit:
        return []
    messages = audit.get("messages") or []
    return [message for message in messages if isinstance(message, dict) and isinstance(message.get("message"), str)]


def _audit_remaining_score(audit: Optional[Dict[str, Any]]) -> int:
    if not isinstance(audit, dict):
        return 0
    summary = audit.get("summary") or {}
    return int(summary.get("_remaining_score") or 0)


def _candidate_codes_for_rule(
    catalog: Dict[str, Any],
    concentration: str,
    rule: Dict[str, Any],
) -> Set[str]:
    matches: Set[str] = set()
    for code in _catalog_course_codes(catalog):
        matched, _notes = _rule_matches_course(catalog, concentration, rule, code)
        if matched:
            matches.add(code)
    return matches


def get_business_concentration_recommendations(
    catalog: Dict[str, Any],
    majors: Iterable[str] | None,
    minors: Iterable[str] | None,
    business_concentration: object,
    completed_courses: Iterable[str] | None,
    planned_courses: Iterable[str] | None,
    limit: int = 30,
) -> List[Dict[str, Any]]:
    concentration = active_business_concentration(majors, business_concentration, catalog=catalog)
    if concentration is None:
        return []

    config = _config(catalog)
    if concentration == config.get("general_label"):
        return []

    taken = {
        _normalize_course_code(code)
        for code in [*(completed_courses or []), *(planned_courses or [])]
        if _normalize_course_code(code)
    }

    base_audit = build_business_concentration_audit(
        catalog=catalog,
        majors=majors,
        minors=minors,
        business_concentration=concentration,
        completed_courses=completed_courses or [],
        planned_courses=planned_courses or [],
    )
    base_score = _audit_remaining_score(base_audit)
    rules = (((config.get("concentrations") or {}).get(concentration) or {}).get("rules") or [])

    recommendations: List[Dict[str, Any]] = []
    seen_codes: Set[str] = set()

    for required in (base_audit or {}).get("required_courses") or []:
        code = _normalize_course_code(required.get("code"))
        if not code or code in taken or required.get("status") != "missing":
            continue
        classification = classify_business_course(
            catalog=catalog,
            code=code,
            majors=majors,
            minors=minors,
            business_concentration=concentration,
        ) or {"badges": [f"Required for {concentration} Concentration"]}
        recommendations.append({
            "code": code,
            "name": _course_title(catalog, code),
            "credits": _course_credits(catalog, code),
            "requirementsSatisfied": 1,
            "tags": classification.get("badges") or [f"Required for {concentration} Concentration"],
            "explanation": f"Required for the {concentration} concentration.",
            "_priority_bucket": 0,
            "_priority_score": 10_000,
        })
        seen_codes.add(code)

    candidate_codes: Set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if str(rule.get("type") or "").strip().lower() != "credits_from_pool":
            continue
        candidate_codes.update(_candidate_codes_for_rule(catalog, concentration, rule))

    for code in sorted(candidate_codes):
        normalized = _normalize_course_code(code)
        if not normalized or normalized in taken or normalized in seen_codes:
            continue

        next_audit = build_business_concentration_audit(
            catalog=catalog,
            majors=majors,
            minors=minors,
            business_concentration=concentration,
            completed_courses=completed_courses or [],
            planned_courses=[*(planned_courses or []), normalized],
        )
        improvement = base_score - _audit_remaining_score(next_audit)
        if improvement <= 0:
            continue

        classification = classify_business_course(
            catalog=catalog,
            code=normalized,
            majors=majors,
            minors=minors,
            business_concentration=concentration,
        ) or {"badges": [f"Elective for {concentration} Concentration"]}
        recommendations.append({
            "code": normalized,
            "name": _course_title(catalog, normalized),
            "credits": _course_credits(catalog, normalized),
            "requirementsSatisfied": 1,
            "tags": classification.get("badges") or [f"Elective for {concentration} Concentration"],
            "explanation": f"Improves progress in the {concentration} concentration.",
            "_priority_bucket": 1,
            "_priority_score": improvement,
        })
        seen_codes.add(normalized)

    recommendations.sort(
        key=lambda entry: (
            int(entry["_priority_bucket"]) if entry.get("_priority_bucket") is not None else 9,
            -int(entry.get("_priority_score") or 0),
            -int(entry.get("credits") or 0),
            str(entry.get("code") or ""),
        )
    )
    return recommendations[:limit]
