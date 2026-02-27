from __future__ import annotations

import io
import re
from typing import Dict, List, Optional, Tuple

import pdfplumber

COURSE_CODE_RE = re.compile(r"\b[A-Z]{3}\s?\d{3,4}\b")
BUSINESS_ADMIN_NON_BUS_ELECTIVES = [
    "EUR 3003",
    "EUR 3020",
    "JMC 2020",
    "JMC 3070",
    "JMC 3089",
    "SUS 3001",
    "SUS 4500",
]
BUSINESS_ADMIN_THESIS_PROJECT_ELECTIVES = ["BUS 4090", "BUS 4091", "BUS 4092"]


def _normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _normalize_course_code(code: str) -> str:
    code = code.strip().upper()
    m = re.match(r"^([A-Z]{3})\s?(\d{3,4})$", code)
    if not m:
        return code
    return f"{m.group(1)} {m.group(2)}"


def _dedupe_codes(codes: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for raw in codes:
        if not isinstance(raw, str):
            continue
        code = _normalize_course_code(raw)
        if not code or code in seen:
            continue
        seen.add(code)
        out.append(code)
    return out


def _extract_codes_in_order(text: str, exclude: Optional[str] = None) -> List[str]:
    excluded = _normalize_course_code(exclude) if isinstance(exclude, str) and exclude.strip() else None
    found: List[str] = []
    for match in COURSE_CODE_RE.finditer((text or "").upper()):
        code = _normalize_course_code(match.group(0))
        if excluded and code == excluded:
            continue
        found.append(code)
    return _dedupe_codes(found)


def _word_boundary_match(text: str, idx: int, word: str) -> bool:
    end = idx + len(word)
    if not text.startswith(word, idx):
        return False
    if idx > 0 and text[idx - 1].isalnum():
        return False
    if end < len(text) and text[end].isalnum():
        return False
    return True


def _strip_wrapping_parens(text: str) -> str:
    s = text.strip()
    while len(s) >= 2 and s[0] == "(" and s[-1] == ")":
        depth = 0
        wraps = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(s) - 1:
                    wraps = False
                    break
            if depth < 0:
                wraps = False
                break
        if not wraps or depth != 0:
            break
        s = s[1:-1].strip()
    return s


def _split_top_level(text: str, connectors: List[str], punctuation: str = "") -> List[str]:
    s = text or ""
    lower = s.lower()
    parts: List[str] = []
    chunk: List[str] = []
    depth = 0
    i = 0

    while i < len(s):
        ch = s[i]
        if ch in "([{":
            depth += 1
            chunk.append(ch)
            i += 1
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            chunk.append(ch)
            i += 1
            continue

        if depth == 0:
            if punctuation and ch in punctuation:
                part = _normalize_spaces("".join(chunk).strip(" ,;:"))
                if part:
                    parts.append(part)
                chunk = []
                i += 1
                continue
            matched = None
            for connector in connectors:
                if _word_boundary_match(lower, i, connector):
                    matched = connector
                    break
            if matched is not None:
                part = _normalize_spaces("".join(chunk).strip(" ,;:"))
                if part:
                    parts.append(part)
                chunk = []
                i += len(matched)
                continue

        chunk.append(ch)
        i += 1

    tail = _normalize_spaces("".join(chunk).strip(" ,;:"))
    if tail:
        parts.append(tail)
    return parts


def _parse_prereq_segment(segment: str, course_code: Optional[str] = None) -> List[Dict[str, object]]:
    text = _strip_wrapping_parens(_normalize_spaces(segment.strip(" .;:")))
    if not text:
        return []

    force_or = bool(re.search(r"\bone of the following\b|\beither\b", text, re.IGNORECASE))
    cleaned = re.sub(r"\bone of the following\b", " ", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\beither\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = _normalize_spaces(cleaned)
    if not cleaned:
        return []

    top_level_or_parts = _split_top_level(cleaned, connectors=["or"], punctuation="/")
    has_top_level_or = len(top_level_or_parts) > 1

    # Commas usually separate additional AND requirements (e.g. "X or Y, Z, and junior standing").
    # Keep comma splitting disabled only for explicit "one of the following"/"either" list phrasing.
    and_punct = ";" if force_or else ",;"
    and_parts = _split_top_level(cleaned, connectors=["and"], punctuation=and_punct)
    if len(and_parts) > 1:
        out: List[Dict[str, object]] = []
        for part in and_parts:
            out.extend(_parse_prereq_segment(part, course_code))
        return out

    # Handle "X (or Y)" form where OR sits inside parentheses.
    paren_or = re.search(r"\(\s*or\b([^)]*)\)", cleaned, re.IGNORECASE)
    if paren_or:
        left_text = (cleaned[:paren_or.start()] + " " + cleaned[paren_or.end():]).strip()
        right_text = paren_or.group(1).strip()
        left_codes = _extract_codes_in_order(left_text, course_code)
        right_codes = _extract_codes_in_order(right_text, course_code)
        grouped = _dedupe_codes(left_codes + right_codes)
        if len(grouped) >= 2:
            return [{"type": "or", "courses": grouped}]

    if force_or or has_top_level_or:
        codes: List[str] = []
        source_parts = top_level_or_parts if has_top_level_or else [cleaned]
        for part in source_parts:
            codes.extend(_extract_codes_in_order(part, course_code))
        unique_codes = _dedupe_codes(codes)
        if len(unique_codes) >= 2:
            return [{"type": "or", "courses": unique_codes}]
        if len(unique_codes) == 1:
            return [{"type": "course", "code": unique_codes[0]}]
        return []

    return [{"type": "course", "code": code} for code in _extract_codes_in_order(cleaned, course_code)]


def _collect_prereq_codes_from_blocks(blocks: List[Dict[str, object]]) -> List[str]:
    codes: List[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").lower()
        if block_type == "course":
            code = block.get("code")
            if isinstance(code, str):
                codes.append(_normalize_course_code(code))
        elif block_type == "or":
            for raw in block.get("courses", []) or []:
                if isinstance(raw, str):
                    codes.append(_normalize_course_code(raw))
    return _dedupe_codes(codes)


def _parse_prereq_blocks(prereq_text: str, course_code: Optional[str] = None) -> List[Dict[str, object]]:
    text = _normalize_spaces(prereq_text or "")
    if not text:
        return []
    text = re.sub(r"^\s*prerequisites?\s*:?\s*", "", text, flags=re.IGNORECASE)
    text = text.strip(" .;:")
    if not text:
        return []
    return _parse_prereq_segment(text, course_code)


def _prereq_block_to_expr(block: Dict[str, object]) -> object | None:
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
            expr = _prereq_block_to_expr(raw)
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
            expr = _prereq_block_to_expr(raw)
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
        expr = _prereq_block_to_expr(block)
        if expr is not None:
            items.append(expr)
    if not items:
        return None
    return {"and": items}


def _normalize_gen_ed(gen_ed: str) -> str:
    if not gen_ed:
        return ""
    s = _normalize_spaces(gen_ed)
    # Fix split single-letter fragments (e.g., "T extual" -> "Textual")
    s = re.sub(r"\b([A-Za-z])\s+([A-Za-z]{2,})\b", r"\1\2", s)
    parts = s.split()
    dedup = []
    for w in parts:
        if not dedup or dedup[-1] != w:
            dedup.append(w)
    s = " ".join(dedup)
    for _ in range(3):
        s = re.sub(r"(\b[A-Za-z]+(?:\s+[A-Za-z]+){0,6}\b)(?:\s+\\1)+", r"\1", s)
    return s.strip()


def _split_gen_ed_tags(gen_ed: str) -> List[str]:
    s = _normalize_gen_ed(gen_ed)
    if not s:
        return []
    s = s.replace("/", ",").replace(";", ",")
    out = []
    for part in s.split(","):
        part = _normalize_spaces(part)
        if not part:
            continue
        out.append(part)
    return out


def _dedupe_display_letters(s: str) -> str:
    out = []
    prev = None
    for ch in s:
        if prev is not None and ch == prev:
            continue
        out.append(ch)
        prev = ch
    return "".join(out)

def _looks_duplicated_text(s: str) -> bool:
    if not s:
        return False
    repeats = 0
    for i in range(1, len(s)):
        if s[i] == s[i - 1]:
            repeats += 1
    return repeats / max(1, len(s)) > 0.18

def _clean_title(raw: str) -> str:
    title = _normalize_spaces(raw)
    if not title:
        return title
    # Cut off obvious description markers
    title = re.split(r"\b(?:credit hours?|credits?|cr\.|prereq|prerequisite|gen ed|wic|frequency|cross)\b", title, 1, flags=re.IGNORECASE)[0]
    title = title.strip(" -—:")
    words = title.split()
    if len(words) > 12:
        title = " ".join(words[:12])
    if _looks_duplicated_text(title):
        title = _dedupe_display_letters(title)
    words = title.split()
    if words and words[-1].lower() in {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}:
        title = " ".join(words[:-1]).strip()
    return title.strip()

def _join_hyphenated(text: str) -> str:
    return re.sub(r"(\w)-\s+(\w)", r"\1\2", text)

def _is_reasonable_title(title: str) -> bool:
    if not title:
        return False
    if len(title) > 80:
        return False
    words = title.split()
    if len(words) > 10:
        return False
    if any(w.lower() in {"course", "courses"} for w in words) and len(words) > 6:
        return False
    return True

def _find_title_in_text(pages_text: List[str], code: str) -> Optional[str]:
    m = re.match(r"^([A-Z]{3})\s?(\d{3,4})$", code)
    if not m:
        return None
    prefix, num = m.group(1), m.group(2)
    pattern = re.compile(rf"^({prefix})\s?({num})\s+(.+)$", re.IGNORECASE)
    for text in pages_text:
        if not text:
            continue
        for line in text.splitlines():
            line = _normalize_spaces(line)
            if not line:
                continue
            mline = pattern.match(line)
            if not mline:
                continue
            tail = mline.group(3)
            title = _clean_title(tail)
            if _is_reasonable_title(title) and title.upper() != code.replace(" ", ""):
                return title
    return None

def extract_foundation_courses(text: str) -> List[str]:
    markers = [
        "General Education Foundation courses",
        "Foundation courses in verbal, mathematical, and life skills",
    ]
    for marker in markers:
        idx = text.find(marker)
        if idx == -1:
            continue
        window = text[idx: idx + 600]
        codes = [_normalize_course_code(c) for c in COURSE_CODE_RE.findall(window)]
        if codes:
            return sorted(set(codes))
    return []

def _extract_gen_ed_section_lines(pages_text: List[str]) -> List[str]:
    lines: List[str] = []
    started = False
    for text in pages_text:
        if not text:
            continue
        lowered = text.lower()
        if not started:
            if "mode of inquiry" in lowered or re.search(r"general education\s+78", text, re.IGNORECASE):
                started = True
            elif re.search(r"general education requirements|general education program", text, re.IGNORECASE):
                if (
                    "mode of inquiry" in lowered
                    or "courses that satisfy the" in lowered
                    or "aesthetic expression" in lowered
                ):
                    started = True
        if started:
            page_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            lines.extend(page_lines)
            if re.search(r"WRITING-INTENSIVE", text, re.IGNORECASE):
                break
    return lines

def _parse_gen_ed_from_section(lines: List[str]) -> Tuple[Dict[str, int], Dict[str, List[str]]]:
    rules: Dict[str, int] = {}
    categories: Dict[str, List[str]] = {}
    if not lines:
        return rules, categories

    def _is_bullet_line(line: str) -> bool:
        stripped = line.lstrip()
        if re.match(r"^[\u2022\u00b7\*\-]", stripped):
            return True
        return stripped.startswith(("\u00e2\u20ac\u00a2", "\u0432\u0402\u045e"))

    bullet_lines: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _is_bullet_line(line):
            if "(" not in line:
                i += 1
                continue
            buf = [line]
            while i + 1 < len(lines) and ")" not in "".join(buf) and len(buf) < 4:
                if _is_bullet_line(lines[i + 1]):
                    break
                buf.append(lines[i + 1])
                i += 1
            joined = _join_hyphenated(" ".join(buf))
            bullet_lines.append(joined)
        i += 1

    word_to_num = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    def _parse_count(text: str) -> Optional[int]:
        m = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b", text, re.IGNORECASE)
        if not m:
            return None
        token = m.group(1).lower()
        if token in word_to_num:
            return word_to_num[token]
        try:
            return int(token)
        except ValueError:
            return None

    for bullet in bullet_lines:
        bullet = re.sub(r"^(?:\u00e2\u20ac\u00a2|\u0432\u0402\u045e|[\s\u2022\u00b7\*\-\u2013\u2014])+", "", bullet).strip()
        bullet = _join_hyphenated(bullet)
        if "(" in bullet:
            category = bullet.split("(", 1)[0].strip()
            detail = bullet.split("(", 1)[1].rsplit(")", 1)[0]
        else:
            category = bullet
            detail = bullet
        category = _normalize_gen_ed(category)
        if category == "Historical Analysis":
            rules.setdefault("Historical Sources", 1)
            rules.setdefault("Historical Research", 1)
        elif category == "Textual Analysis":
            rules.setdefault("Principles of Textual Analysis", 1)
            rules.setdefault("Case Studies in Textual Analysis", 1)
        else:
            count = _parse_count(detail) or 0
            if count:
                rules.setdefault(category, count)

    def _dedupe_category(name: str) -> str:
        name = _normalize_gen_ed(name)
        words = name.split()
        for k in range(1, len(words) // 2 + 1):
            if len(words) % k != 0:
                continue
            first = words[:k]
            if all(words[i:i + k] == first for i in range(0, len(words), k)):
                return " ".join(first)
        return name

    current_category = None
    collecting = False
    for line in lines:
        if "Courses that satisfy the" in line:
            m = re.search(r"Courses that satisfy the (.+?) mode of inquiry", line, re.IGNORECASE)
            if m:
                current_category = _dedupe_category(m.group(1).strip())
                categories.setdefault(current_category, [])
                collecting = True
            continue
        if collecting:
            codes = [_normalize_course_code(c) for c in COURSE_CODE_RE.findall(line)]
            if codes:
                categories.setdefault(current_category, []).extend(codes)
            else:
                if re.search(r"following", line, re.IGNORECASE):
                    continue
                if len(line) < 12:
                    continue
                if line.lower().startswith("learning outcomes"):
                    collecting = False
                    continue
                if re.match(r"^[A-Z][A-Za-z &\-]+$", line):
                    collecting = False
                    continue
                # default stop when list clearly ends
                collecting = False

    for cat in list(categories.keys()):
        categories[cat] = sorted(set(categories[cat]))
    for cat in rules.keys():
        categories.setdefault(cat, [])

    return rules, categories


def extract_text_all_pages(pdf_bytes: bytes) -> List[str]:
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def detect_course_table_pages(pages_text: List[str]) -> List[int]:
    indices: List[int] = []
    for idx, text in enumerate(pages_text):
        if not text:
            continue
        lowered = text.lower()
        code_count = len(COURSE_CODE_RE.findall(text))
        if code_count < 6:
            continue
        has_header = bool(re.search(r"\bCode\s+Title\s+Description\s+Credits\b", text, re.IGNORECASE))
        keyword_hits = 0
        for kw in ["credits", "cr.", "gen ed", "wic", "prereq", "frequency", "cross"]:
            if kw in lowered:
                keyword_hits += 1
        if has_header or (code_count >= 10 and keyword_hits >= 1) or (code_count >= 6 and keyword_hits >= 2):
            indices.append(idx)
    return indices


def extract_courses_from_pages(pages_text: List[str], page_indices: List[int]) -> Dict[str, Dict]:
    courses: Dict[str, Dict] = {}
    credit_re = re.compile(r"\b(\d+(?:-\d+)?)\s*(?:Cr\.|Credits?)\b", re.IGNORECASE)
    for idx in page_indices:
        if idx < 0 or idx >= len(pages_text):
            continue
        for line in pages_text[idx].splitlines():
            line = _normalize_spaces(line)
            if not line:
                continue
            if "code" in line.lower() and "credits" in line.lower():
                continue
            m = re.match(r"^([A-Z]{3})\s?(\d{3,4})(?:/(\d{3,4}))?\s+(.*)$", line)
            if not m:
                continue
            codes = []
            if m.group(3):
                codes.append(_normalize_course_code(f"{m.group(1)} {m.group(2)}"))
                codes.append(_normalize_course_code(f"{m.group(1)} {m.group(3)}"))
            else:
                codes.append(_normalize_course_code(f"{m.group(1)} {m.group(2)}"))

            tail = m.group(4)
            credits = None
            credit_match = credit_re.search(tail)
            if credit_match:
                token = credit_match.group(1)
                try:
                    credits = int(token.split("-")[0])
                except ValueError:
                    credits = None

            title = re.split(r"\s{2,}|\.{3,}", tail)[0]
            title = credit_re.sub("", title).strip(" -")
            if "(" in title:
                title = title.split("(")[0].strip()
            title = _clean_title(title)
            if len(title) < 3:
                title = codes[0]

            gen_ed_tags: List[str] = []
            gen_match = re.search(r"(?:Gen(?:eral)?\s*Ed\.?:?|Gen Ed:)\s*([A-Za-z][A-Za-z &/-]+)", tail, re.IGNORECASE)
            if gen_match:
                gen_ed_tags = _split_gen_ed_tags(gen_match.group(1))

            for code in codes:
                courses[code] = {
                    "name": title,
                    "credits": credits or 3,
                    "gen_ed": gen_ed_tags,
                }
    return courses


def extract_catalog_year(text: str) -> Optional[str]:
    m = re.search(r"\bAY\s+(\d{4}-\d{2})\b", text)
    return m.group(1) if m else None


def _extract_toc_block(text: str, start_marker: str, end_marker: str, max_chars: int = 15000) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    sub = text[start:start + max_chars]
    end = sub.find(end_marker)
    if end != -1:
        sub = sub[:end]
    return sub


def _extract_names_from_toc_block(block: str) -> List[str]:
    names: List[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        if "Programs" in line and "." in line:
            continue
        has_page = bool(re.search(r"\.{3,}\s*\d+\s*$", line) or re.search(r"\s\d+\s*$", line))
        if not has_page:
            continue
        cleaned = re.sub(r"\.{3,}\s*\d+\s*$", "", line).strip()
        cleaned = re.sub(r"\s\d+\s*$", "", cleaned).strip()
        if len(cleaned) < 3:
            continue
        if cleaned.lower() in {"major programs", "minor programs", "honors", "general education"}:
            continue
        if re.match(r"^[A-Za-z][A-Za-z &\-]+$", cleaned):
            names.append(cleaned)
    seen = set()
    out = []
    for n in names:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            out.append(n)
    return out


def _is_toc_line(line: str) -> bool:
    return bool(re.search(r"\.{3,}\s*\d+\s*$", line) or re.search(r"\s\d+\s*$", line))


def _extract_toc_list_after_heading(lines: List[str], heading: str, max_lookahead: int = 120) -> str:
    candidates = []
    for i, line in enumerate(lines):
        if heading in line and _is_toc_line(line):
            end_idx = None
            for j in range(i + 1, min(len(lines), i + 1 + max_lookahead)):
                if "Courses" in lines[j] and _is_toc_line(lines[j]):
                    end_idx = j
                    break
            score = 0
            limit = end_idx if end_idx is not None else min(len(lines), i + 1 + max_lookahead)
            for j in range(i + 1, limit):
                if _is_toc_line(lines[j]):
                    score += 1
            candidates.append((end_idx is not None, score, i, end_idx))

    if not candidates:
        return ""

    candidates.sort(key=lambda t: (t[0], t[1]))
    has_courses, _, start_idx, end_idx = candidates[-1]

    collected: List[str] = []
    stop_at = end_idx if (has_courses and end_idx is not None) else len(lines)
    for j in range(start_idx + 1, stop_at):
        ln = lines[j].strip()
        if not ln:
            continue
        if re.fullmatch(r"[IVXLC]+", ln):
            continue
        if not _is_toc_line(ln):
            break
        collected.append(ln)
    return "\n".join(collected)


def extract_program_names(text: str) -> Tuple[List[str], List[str]]:
    majors_block = _extract_toc_block(text, "Major Programs", "Minor Programs")
    majors = _extract_names_from_toc_block(majors_block)

    lines = text.splitlines()
    minors_block = _extract_toc_list_after_heading(lines, "Minor Programs")
    minors = _extract_names_from_toc_block(minors_block)

    return majors, minors


def extract_program_requirements(
    text: str,
    program_names: List[str],
    section_hint: Optional[str] = None,
) -> Dict[str, object]:
    reqs: Dict[str, object] = {}
    lines = text.splitlines()
    normalized_lines = []
    for ln in lines:
        ln2 = _normalize_spaces(ln)
        if not ln2:
            normalized_lines.append("")
            continue
        if COURSE_CODE_RE.search(ln2):
            normalized_lines.append(ln2)
        elif ln2.isupper() or re.match(r"^[A-Z\s&\-]{8,}$", ln2):
            normalized_lines.append(_dedupe_display_letters(ln2))
        else:
            normalized_lines.append(ln2)

    program_headings = {_dedupe_display_letters(n.upper()) for n in program_names}

    word_to_num = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
    }

    def _to_num(token: str) -> Optional[int]:
        token = token.lower()
        if token in word_to_num:
            return word_to_num[token]
        try:
            return int(token)
        except ValueError:
            return None

    def _parse_credit_count(line: str) -> Optional[int]:
        m = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b\s*(?:credit|cr)", line, re.IGNORECASE)
        if not m:
            return None
        credits = _to_num(m.group(1))
        if not credits:
            return None
        return int(credits)

    def _parse_course_count(line: str) -> Optional[int]:
        m = re.search(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b\s*(?:course|courses)\b", line, re.IGNORECASE)
        if not m:
            return None
        return _to_num(m.group(1))

    def _parse_header_credit_count(line: str, header: str) -> Optional[int]:
        lower = line.lower()
        header_lower = header.lower()
        idx = lower.find(header_lower)
        if idx == -1:
            return _parse_credit_count(line)
        tail = line[idx + len(header):]
        tail = re.sub(r"^[^A-Za-z0-9]+", "", tail)
        if "(" in tail:
            m = re.search(r"\(([^)]*)\)", tail)
            if m:
                tail = m.group(1)
        return _parse_credit_count(tail)

    def _is_elective_subheader(line: str) -> bool:
        return bool(re.match(r"^\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b.*\b(credit|cr|course|courses)\b", line, re.IGNORECASE))

    def _is_required_header(line: str) -> bool:
        return bool(re.match(r"^\s*Required\s+Courses?\b", line, re.IGNORECASE))

    def _is_elective_header(line: str) -> bool:
        if re.match(r"^\s*(?:[A-Za-z&/\-]+\s+){0,3}Electives?\b", line, re.IGNORECASE):
            return True
        return False

    def _is_total_elective_header(line: str) -> bool:
        return bool(
            re.match(r"^\s*Elective\s+Courses?\b", line, re.IGNORECASE)
            or re.match(r"^\s*Electives?\b", line, re.IGNORECASE)
        )

    def _is_choice_line(line: str, codes: List[str]) -> bool:
        """Heuristic for detecting 'choice' requirements (OR / choose N / from the following).

        The catalog PDF often wraps OR options across multiple lines, e.g.
          "MAT 2001 Mathematical Statistics or"
          "MAT 2013 Introduction to Differential Equations"

        In those cases, the first line may contain only ONE course code. We still want
        to start a 'Program Choice' block so subsequent lines can add more codes.
        """
        if len(codes) >= 1 and re.search(r"\b(or|choose|select)\b", line, re.IGNORECASE):
            return True
        if re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\b\s+(of|courses?)\b", line, re.IGNORECASE):
            return True
        if re.search(r"\bfrom the following\b|\bchoose from\b|\bselect from\b", line, re.IGNORECASE):
            return True
        return False

    def _slug(name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
        return slug or "program"

    def _is_business_administration(name: str) -> bool:
        return _normalize_spaces(name).lower() == "business administration"

    def _business_administration_elective_blocks(name: str) -> List[Dict[str, object]]:
        slug = _slug(name)
        blocks: List[Dict[str, object]] = [
            {
                "label": "Elective Courses",
                "credits_required": 9,
                "courses_required": None,
                "allowed_courses": [],
                "rule_text": "Business Administration major electives: 9 credits required.",
                "is_total": True,
            },
            {
                "label": "Non-BUS allowed electives",
                "credits_required": 3,
                "courses_required": None,
                "allowed_courses": list(BUSINESS_ADMIN_NON_BUS_ELECTIVES),
                "rule_text": (
                    "At most 3 credits may come from these non-BUS electives: "
                    + ", ".join(BUSINESS_ADMIN_NON_BUS_ELECTIVES)
                    + "."
                ),
                "is_total": False,
            },
            {
                "label": "Project/Thesis elective cap",
                "credits_required": 3,
                "courses_required": None,
                "allowed_courses": list(BUSINESS_ADMIN_THESIS_PROJECT_ELECTIVES),
                "rule_text": (
                    "At most 3 credits may come from BUS 4090 or BUS 4091/BUS 4092 toward electives."
                ),
                "is_total": False,
            },
            {
                "label": "BUS/ENT upper-level electives",
                "credits_required": None,
                "courses_required": None,
                "allowed_courses": [],
                "rule_text": "Remaining elective credits must be BUS/ENT 3000-4000 level courses.",
                "is_total": False,
            },
        ]
        for idx, block in enumerate(blocks, start=1):
            block["id"] = f"{slug}-elective-{idx}"
        return blocks

    def _find_section_start(label: str) -> Optional[int]:
        label_key = _dedupe_display_letters(label.upper())
        indices = [i for i, ln in enumerate(normalized_lines) if _dedupe_display_letters(ln.upper()) == label_key]
        if not indices:
            return None
        if len(indices) == 1:
            return indices[0]
        best_idx = indices[-1]
        for idx in indices:
            found = False
            for j in range(idx + 1, min(len(normalized_lines), idx + 400)):
                ln = normalized_lines[j]
                if not ln:
                    continue
                if re.search(r"Required Courses|Elective Courses|Electives", ln, re.IGNORECASE):
                    found = True
                    break
            if found:
                best_idx = idx
        return best_idx

    def _find_start_idx(target: str, min_index: int = 0, max_index: Optional[int] = None) -> Optional[int]:
        candidates: List[Tuple[int, int]] = []
        limit = max_index if max_index is not None else len(normalized_lines)
        for i in range(min_index, min(limit, len(normalized_lines))):
            ln = normalized_lines[i]
            if not ln:
                continue
            line_key = _dedupe_display_letters(ln.upper())
            if target in line_key:
                score = 0
                if line_key == target:
                    score += 2
                if len(ln) <= len(target) + 6:
                    score += 1
                candidates.append((score, i))
        if not candidates:
            return None
        best_idx = candidates[0][1]
        best_score = None
        for base_score, i in candidates:
            heading_found = False
            code_found = False
            for j in range(i + 1, min(len(normalized_lines), i + 200, limit)):
                ln = normalized_lines[j]
                if not ln:
                    continue
                if ln in program_headings and ln != target:
                    break
                if re.search(r"Required Courses|Elective Courses|Electives", ln, re.IGNORECASE):
                    heading_found = True
                if COURSE_CODE_RE.search(ln):
                    code_found = True
                if heading_found and code_found:
                    break
            score = base_score + (3 if heading_found else 0) + (1 if code_found else 0)
            if best_score is None or score > best_score:
                best_score = score
                best_idx = i
        return best_idx

    def _is_stop_line(ln: str, target: str) -> bool:
        if not ln:
            return False
        line_key = _dedupe_display_letters(ln.upper())
        if line_key in program_headings and line_key != target:
            return True
        if (
            line_key.startswith("CONCENTRATIONS")
            or line_key.startswith("CONCENTRATION")
            or line_key.startswith("SPECIALIZATIONS")
            or line_key.startswith("SPECIALIZATION")
            or line_key.startswith("TRACKS")
            or line_key.startswith("TRACK")
        ):
            if len(ln) <= 40:
                return True
        return False

    section_start_idx = None
    if section_hint == "major":
        section_start_idx = _find_section_start("Major Programs")
    elif section_hint == "minor":
        section_start_idx = _find_section_start("Minor Programs")

    section_end_idx = None
    if section_start_idx is not None:
        for i in range(section_start_idx + 1, len(normalized_lines)):
            ln = normalized_lines[i]
            if _dedupe_display_letters(ln.upper()) == "COURSES":
                section_end_idx = i
                break

    for name in program_names:
        target = _dedupe_display_letters(name.upper())
        start_idx = _find_start_idx(
            target,
            min_index=section_start_idx or 0,
            max_index=section_end_idx,
        )
        if start_idx is None:
            reqs[name] = []
            continue

        required: List[str] = []
        elective_requirements: List[Dict[str, object]] = []
        current_section: Optional[str] = None
        current_elective: Optional[Dict[str, object]] = None
        current_choice: Optional[Dict[str, object]] = None
        total_credits: Optional[int] = None
        required_credits_header: Optional[int] = None

        def _start_elective_block(
            label: str,
            rule_line: str,
            is_total: bool = False,
            credits_override: Optional[int] = None,
            courses_override: Optional[int] = None,
        ) -> Dict[str, object]:
            credits_required = credits_override if credits_override is not None else _parse_credit_count(rule_line)
            courses_required = courses_override if courses_override is not None else _parse_course_count(rule_line)
            return {
                "label": _normalize_spaces(label) or "Elective Courses",
                "credits_required": credits_required,
                "courses_required": courses_required,
                "allowed_courses": [],
                "rule_lines": [rule_line] if rule_line else [],
                "is_total": is_total,
            }

        def _finalize_elective_block(block: Dict[str, object]) -> None:
            allowed = sorted(set(block.get("allowed_courses", []) or []))
            rule_text = _normalize_spaces(" ".join(block.get("rule_lines", []) or []))
            elective_requirements.append({
                "label": block.get("label") or "Elective Courses",
                "credits_required": block.get("credits_required"),
                "courses_required": block.get("courses_required"),
                "allowed_courses": allowed,
                "rule_text": rule_text,
                "is_total": bool(block.get("is_total")),
            })

        def _adjust_total_elective_credits() -> None:
            nonlocal elective_requirements
            if not elective_requirements:
                return
            if total_credits is None or required_credits_header is None:
                return
            if total_credits <= 0 or required_credits_header < 0:
                return
            if total_credits > 80:
                return
            expected = total_credits - required_credits_header
            if expected <= 0:
                return
            total_blocks = [b for b in elective_requirements if b.get("is_total")]
            if total_blocks:
                for b in total_blocks:
                    current = b.get("credits_required")
                    if current is None or current != expected:
                        b["credits_required"] = expected
                    b["is_total"] = True
                    break
                return
            sum_credits = sum(int(b.get("credits_required") or 0) for b in elective_requirements)
            if sum_credits == expected:
                return
            if sum_credits == 0:
                elective_requirements[0]["credits_required"] = expected
                elective_requirements[0]["is_total"] = True
                return
            elective_requirements.insert(0, {
                "label": "Elective Courses",
                "credits_required": expected,
                "courses_required": None,
                "allowed_courses": [],
                "rule_text": "",
                "is_total": True,
            })

        for j in range(start_idx + 1, len(normalized_lines)):
            if section_end_idx is not None and j >= section_end_idx:
                break
            ln = normalized_lines[j]
            if _is_stop_line(ln, target):
                break

            if total_credits is None and re.match(r"^\s*Total\b", ln, re.IGNORECASE):
                total_credits = _parse_header_credit_count(ln, "Total")

            if _is_required_header(ln):
                current_section = "required"
                if current_choice is not None:
                    _finalize_elective_block(current_choice)
                    current_choice = None
                current_elective = None
                if required_credits_header is None:
                    required_credits_header = _parse_header_credit_count(ln, "Required Courses")
                continue
            if _is_elective_header(ln):
                current_section = "elective"
                if current_choice is not None:
                    _finalize_elective_block(current_choice)
                    current_choice = None
                if current_elective is not None:
                    _finalize_elective_block(current_elective)
                label = _normalize_spaces(re.sub(r"\(.*?\)", "", ln))
                header_key = "Electives" if re.match(r"^\s*Electives?\b", ln, re.IGNORECASE) else "Elective Courses"
                header_credits = _parse_header_credit_count(ln, header_key)
                header_courses = _parse_course_count(ln)
                has_total = _is_total_elective_header(ln)
                current_elective = _start_elective_block(
                    label,
                    ln,
                    is_total=has_total,
                    credits_override=header_credits,
                    courses_override=header_courses,
                )
                continue

            if current_section is None:
                continue

            codes = [_normalize_course_code(c) for c in COURSE_CODE_RE.findall(ln)]
            if current_choice is not None:
                if not ln.strip():
                    _finalize_elective_block(current_choice)
                    current_choice = None
                    continue
                if _is_required_header(ln) or _is_elective_header(ln) or _is_stop_line(ln, target):
                    _finalize_elective_block(current_choice)
                    current_choice = None
                else:
                    if codes:
                        current_choice.setdefault("allowed_courses", []).extend(codes)
                    current_choice.setdefault("rule_lines", []).append(ln)
                    continue

            if current_section == "required":
                if _is_choice_line(ln, codes):
                    current_choice = _start_elective_block("Program Choice", ln)
                    if codes:
                        current_choice.setdefault("allowed_courses", []).extend(codes)
                    continue
                if not codes:
                    continue
                required.extend(codes)
            elif current_section == "elective":
                if current_elective is None:
                    current_elective = _start_elective_block("Elective Courses", "")
                if _is_elective_subheader(ln) and (current_elective.get("rule_lines") or current_elective.get("allowed_courses")):
                    only_header = (
                        len(current_elective.get("rule_lines", [])) <= 1
                        and not current_elective.get("allowed_courses")
                        and current_elective.get("credits_required") is None
                        and current_elective.get("courses_required") is None
                        and (current_elective.get("label") or "").lower().startswith("elective")
                    )
                    if only_header:
                        current_elective["label"] = _normalize_spaces(ln)
                        current_elective["rule_lines"] = [ln]
                    else:
                        _finalize_elective_block(current_elective)
                        current_elective = _start_elective_block(ln, ln)
                else:
                    current_elective.setdefault("rule_lines", []).append(ln)
                if codes:
                    current_elective.setdefault("allowed_courses", []).extend(codes)
                if current_elective.get("credits_required") is None:
                    current_elective["credits_required"] = _parse_credit_count(ln)
                if current_elective.get("courses_required") is None:
                    current_elective["courses_required"] = _parse_course_count(ln)

        if current_elective is not None:
            _finalize_elective_block(current_elective)
        if current_choice is not None:
            _finalize_elective_block(current_choice)
        _adjust_total_elective_credits()

        required = sorted(set(required))
        if section_hint == "major" and _is_business_administration(name):
            elective_requirements = _business_administration_elective_blocks(name)

        if required or elective_requirements:
            slug = _slug(name)
            for idx, block in enumerate(elective_requirements, start=1):
                block["id"] = f"{slug}-elective-{idx}"
            reqs[name] = {
                "required_courses": required,
                "elective_requirements": elective_requirements,
            }
            continue

        # Fallback: collect codes within the bounded program window
        collected: List[str] = []
        for j in range(start_idx + 1, len(normalized_lines)):
            ln = normalized_lines[j]
            if _is_stop_line(ln, target):
                break
            collected.extend([_normalize_course_code(c) for c in COURSE_CODE_RE.findall(ln)])
        reqs[name] = {
            "required_courses": sorted(set(collected)),
            "elective_requirements": [],
        }

    return reqs


def extract_course_table_from_pdf(pdf_bytes: bytes, page_indices: List[int]) -> Dict[str, Dict]:
    course_meta: Dict[str, Dict] = {}
    start_re = re.compile(r"^([A-Z]{3})\s?(\d{3,4})$")

    def _col_for_x(x0: float) -> str:
        if x0 < 100:
            return "code"
        if x0 < 200:
            return "title"
        if x0 < 480:
            return "description"
        if x0 < 540:
            return "credits"
        if x0 < 595:
            return "gen_ed"
        if x0 < 625:
            return "wic"
        if x0 < 690:
            return "prereq"
        if x0 < 740:
            return "frequency"
        return "cross"

    if not page_indices:
        return course_meta

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pno in sorted(set(page_indices)):
            if pno < 0 or pno >= len(pdf.pages):
                continue
            page = pdf.pages[pno]
            words = page.extract_words()
            if not words:
                continue
            lines: List[List[Dict]] = []
            current = []
            current_top = None
            for w in sorted(words, key=lambda x: (x["top"], x["x0"])):
                if current_top is None or abs(w["top"] - current_top) <= 2:
                    current.append(w)
                    current_top = w["top"] if current_top is None else current_top
                else:
                    lines.append(current)
                    current = [w]
                    current_top = w["top"]
            if current:
                lines.append(current)

            current_course = None
            for line in lines:
                cols = {
                    "code": "",
                    "title": "",
                    "description": "",
                    "credits": "",
                    "gen_ed": "",
                    "wic": "",
                    "prereq": "",
                    "frequency": "",
                    "cross": "",
                }
                for w in line:
                    col = _col_for_x(w["x0"])
                    cols[col] += (w["text"] + " ")
                cols = {k: v.strip() for k, v in cols.items()}

                if cols["code"] in {"Code", "Courses"}:
                    continue
                if "Code Title Description Credits" in " ".join(cols.values()):
                    continue

                code_candidate = cols["code"].replace("  ", " ").strip()
                code_match = None
                code_pair_match = None
                if code_candidate:
                    code_match = start_re.match(code_candidate.replace(" ", ""))
                    if not code_match:
                        code_match = start_re.match(code_candidate)
                    if not code_match:
                        code_pair_match = re.match(r"^([A-Z]{3})\s?(\d{3,4})/(\d{3,4})$", code_candidate.replace(" ", ""))

                if code_match or code_pair_match:
                    if current_course:
                        for code in current_course["codes"]:
                            course_meta[code] = current_course
                    if code_pair_match:
                        code1 = _normalize_course_code(f"{code_pair_match.group(1)} {code_pair_match.group(2)}")
                        code2 = _normalize_course_code(f"{code_pair_match.group(1)} {code_pair_match.group(3)}")
                        codes = [code1, code2]
                    else:
                        code = _normalize_course_code(f"{code_match.group(1)} {code_match.group(2)}")
                        codes = [code]
                    current_course = {
                        "codes": codes,
                        "title": cols["title"],
                        "description": cols["description"],
                        "credits": cols["credits"],
                        "gen_ed": cols["gen_ed"],
                        "wic": cols["wic"],
                        "prereq_text": cols["prereq"],
                        "frequency": cols["frequency"],
                        "cross_listed": cols["cross"],
                    }
                elif current_course:
                    column_map = {
                        "title": "title",
                        "description": "description",
                        "credits": "credits",
                        "gen_ed": "gen_ed",
                        "wic": "wic",
                        "prereq_text": "prereq",
                        "frequency": "frequency",
                        "cross_listed": "cross",
                    }
                    for key, col in column_map.items():
                        extra = cols.get(col, "")
                        if extra:
                            existing = current_course.get(key, "")
                            current_course[key] = (existing + " " + extra).strip()

            if current_course:
                for code in current_course["codes"]:
                    course_meta[code] = current_course

    credit_re = re.compile(r"\b(\d+(?:-\d+)?)\s*Cr\.", re.IGNORECASE)
    for code, meta in list(course_meta.items()):
        credits = 3
        credit_match = credit_re.search(meta.get("credits", ""))
        if credit_match:
            credit_token = credit_match.group(1)
            try:
                credits = int(credit_token.split("-")[0])
            except ValueError:
                credits = 3

        gen_ed = _normalize_gen_ed(meta.get("gen_ed") or "") or None
        wic = "WIC" in (meta.get("wic") or "")
        prereq_text = meta.get("prereq_text") or None
        prereq_codes = sorted({_normalize_course_code(c) for c in COURSE_CODE_RE.findall(prereq_text or "")})
        if code in prereq_codes:
            prereq_codes = [c for c in prereq_codes if c != code]
        prereq_blocks = _parse_prereq_blocks(prereq_text or "", course_code=code)
        covered_codes = set(_collect_prereq_codes_from_blocks(prereq_blocks))
        for prereq_code in prereq_codes:
            if prereq_code not in covered_codes:
                prereq_blocks.append({"type": "course", "code": prereq_code})
                covered_codes.add(prereq_code)
        prereq_expr = _prereq_blocks_to_expr(prereq_blocks)

        title = _clean_title((meta.get("title") or "").strip())
        if not _is_reasonable_title(title):
            title = None
        course_meta[code] = {
            "title": title or None,
            "credits": credits,
            "gen_ed": gen_ed,
            "gen_ed_tags": _split_gen_ed_tags(gen_ed or ""),
            "wic": wic,
            "prereq_text": prereq_text,
            "prereq_codes": prereq_codes,
            "prereqs": prereq_codes,
            "prereq_expr": prereq_expr,
            "prereq_blocks": prereq_blocks,
            "frequency": (meta.get("frequency") or None),
            "cross_listed": (meta.get("cross_listed") or None),
        }

    return course_meta


def _extract_section(lines: List[str], keyword: str, max_lines: int = 220) -> List[str]:
    keyword = keyword.lower()
    for i, line in enumerate(lines):
        if keyword in line.lower():
            section = []
            for j in range(i, min(len(lines), i + max_lines)):
                ln = _normalize_spaces(lines[j])
                if not ln:
                    continue
                if j > i and ln.isupper() and len(ln) > 6:
                    break
                section.append(ln)
            return section
    return []


def extract_gen_ed_rules(text: str, categories: List[str]) -> Dict[str, int]:
    rules: Dict[str, int] = {}
    if not categories:
        return rules

    categories_sorted = sorted(categories, key=lambda s: (-len(s), s.lower()))
    lines = [ln for ln in (_normalize_spaces(l) for l in text.splitlines()) if ln]
    section_lines = []
    for marker in ["General Education Requirements", "General Education Program", "General Education"]:
        section_lines = _extract_section(lines, marker, max_lines=400)
        if section_lines:
            break
    search_lines = section_lines if section_lines else lines

    word_to_num = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }

    def _to_count(token: str) -> Optional[int]:
        token = token.lower()
        if token in word_to_num:
            return word_to_num[token]
        try:
            return int(token)
        except ValueError:
            return None

    def _extract_from_text(line: str, category: str) -> Optional[int]:
        cat = re.escape(category)
        patterns = [
            rf"{cat}[^0-9]{{0,12}}(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:course|credit|cr)\b",
            rf"{cat}[^0-9]{{0,12}}(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b",
            rf"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:course|credit|cr)\b[^a-zA-Z]{{0,12}}{cat}",
        ]
        for pat in patterns:
            m = re.search(pat, line, re.IGNORECASE)
            if not m:
                continue
            return _to_count(m.group(1))
        return None

    for line in search_lines:
        for category in categories_sorted:
            if category in rules:
                continue
            if category.lower() not in line.lower():
                continue
            count = _extract_from_text(line, category)
            if count:
                rules[category] = count

    if len(rules) < len(categories_sorted):
        combined = " ".join(search_lines)
        for category in categories_sorted:
            if category in rules:
                continue
            if category.lower() not in combined.lower():
                continue
            count = _extract_from_text(combined, category)
            if count:
                rules[category] = count

    core_categories = [
        "Aesthetic Expression",
        "Moral and Philosophical Reasoning",
        "Quantitative Reasoning",
        "Scientific Investigation",
        "Social and Cultural Analysis",
    ]
    if any(c in categories for c in core_categories):
        for c in core_categories:
            if c in categories and c not in rules:
                return {}

    return rules


def parse_catalog(pdf_file) -> Dict:
    pdf_bytes = pdf_file.read()
    pages_text = extract_text_all_pages(pdf_bytes)
    full_text = "\n".join(pages_text)

    year = extract_catalog_year(full_text)
    majors, minors = extract_program_names(full_text)

    course_table_pages = detect_course_table_pages(pages_text)
    course_meta = extract_course_table_from_pdf(pdf_bytes, course_table_pages)
    if not course_meta and pages_text:
        course_meta = extract_course_table_from_pdf(pdf_bytes, list(range(len(pages_text))))
    text_pages = course_table_pages if course_table_pages else list(range(len(pages_text)))
    extracted_courses = extract_courses_from_pages(pages_text, text_pages)

    courses: Dict[str, Dict] = {}

    for code, data in extracted_courses.items():
        name = _clean_title(data.get("name") or "") or code
        courses[code] = {
            "name": name,
            "credits": data.get("credits") or 3,
            "gen_ed": data.get("gen_ed") or [],
        }

    for code, meta in course_meta.items():
        entry = courses.get(code, {"name": code, "credits": 3, "gen_ed": []})
        if meta.get("title"):
            entry["name"] = meta.get("title")
        entry["credits"] = meta.get("credits") or entry.get("credits") or 3
        gen_ed_tags = meta.get("gen_ed_tags") or _split_gen_ed_tags(meta.get("gen_ed") or "")
        if gen_ed_tags:
            existing = set(entry.get("gen_ed", []))
            for tag in gen_ed_tags:
                if tag not in existing:
                    entry.setdefault("gen_ed", []).append(tag)
                    existing.add(tag)
        courses[code] = entry

    # Ensure we capture any codes found in the full text
    for raw in set(COURSE_CODE_RE.findall(full_text)):
        code = _normalize_course_code(raw)
        courses.setdefault(code, {"name": code, "credits": 3, "gen_ed": []})

    # Fill missing names from full-text lines when the title is just the code
    for code, entry in courses.items():
        if entry.get("name") == code:
            title = _find_title_in_text(pages_text, code)
            if title:
                entry["name"] = title

    major_reqs = extract_program_requirements(full_text, majors, section_hint="major")
    minor_reqs = extract_program_requirements(full_text, minors, section_hint="minor")
    foundation_courses = extract_foundation_courses(full_text)

    # Remove AUB 1000 and non-course building codes entirely from the system
    remove_codes = {"AUB 1000"}
    remove_prefixes = {"BAC", "MB", "ABF"}
    for code in list(courses.keys()):
        prefix = code.split()[0] if isinstance(code, str) and " " in code else code
        if prefix in remove_prefixes:
            remove_codes.add(code)
    for code in remove_codes:
        courses.pop(code, None)
        course_meta.pop(code, None)

    def _remove_codes_from_reqs(reqs_obj):
        if isinstance(reqs_obj, list):
            return [c for c in reqs_obj if c not in remove_codes]
        if isinstance(reqs_obj, dict):
            cleaned = dict(reqs_obj)
            if isinstance(cleaned.get("required_courses"), list):
                cleaned["required_courses"] = [c for c in cleaned["required_courses"] if c not in remove_codes]
            if isinstance(cleaned.get("required"), list):
                cleaned["required"] = [c for c in cleaned["required"] if c not in remove_codes]
            if isinstance(cleaned.get("fixed"), list):
                cleaned["fixed"] = [c for c in cleaned["fixed"] if c not in remove_codes]
            if isinstance(cleaned.get("courses"), list):
                cleaned["courses"] = [c for c in cleaned["courses"] if c not in remove_codes]
            if isinstance(cleaned.get("choices"), list):
                next_choices = []
                for group in cleaned["choices"]:
                    if not isinstance(group, dict):
                        continue
                    g = dict(group)
                    if isinstance(g.get("courses"), list):
                        g["courses"] = [c for c in g["courses"] if c not in remove_codes]
                    next_choices.append(g)
                cleaned["choices"] = next_choices
            if isinstance(cleaned.get("elective_requirements"), list):
                next_electives = []
                for block in cleaned["elective_requirements"]:
                    if not isinstance(block, dict):
                        continue
                    b = dict(block)
                    if isinstance(b.get("allowed_courses"), list):
                        b["allowed_courses"] = [c for c in b.get("allowed_courses", []) if c not in remove_codes]
                    next_electives.append(b)
                cleaned["elective_requirements"] = next_electives
            return cleaned
        return reqs_obj

    for name, reqs in major_reqs.items():
        major_reqs[name] = _remove_codes_from_reqs(reqs)
    for name, reqs in minor_reqs.items():
        minor_reqs[name] = _remove_codes_from_reqs(reqs)
    foundation_courses = [c for c in foundation_courses if c not in remove_codes]

    section_lines = _extract_gen_ed_section_lines(pages_text)
    section_rules, section_categories = _parse_gen_ed_from_section(section_lines)

    gen_ed_categories: Dict[str, List[str]] = {}
    if section_categories:
        normalized: Dict[str, List[str]] = {}
        for raw_cat, codes in section_categories.items():
            cat = _normalize_gen_ed(raw_cat)
            normalized.setdefault(cat, []).extend(codes)
        gen_ed_categories = {k: sorted(set(v)) for k, v in normalized.items()}
    else:
        for code, info in courses.items():
            for cat in info.get("gen_ed", []):
                gen_ed_categories.setdefault(cat, []).append(code)
        for cat in list(gen_ed_categories.keys()):
            gen_ed_categories[cat] = sorted(set(gen_ed_categories[cat]))

    for cat, codes in list(gen_ed_categories.items()):
        gen_ed_categories[cat] = [c for c in codes if c not in remove_codes]

    # Ensure course entries carry gen-ed tags derived from section lists
    for category, codes in gen_ed_categories.items():
        for code in codes:
            if code in courses:
                courses[code].setdefault("gen_ed", [])
                if category not in courses[code]["gen_ed"]:
                    courses[code]["gen_ed"].append(category)
            else:
                courses[code] = {"name": code, "credits": 3, "gen_ed": [category]}

    if section_rules:
        normalized_rules: Dict[str, int] = {}
        for raw_cat, count in section_rules.items():
            cat = _normalize_gen_ed(raw_cat)
            normalized_rules[cat] = count
        gen_ed_rules = normalized_rules
    else:
        gen_ed_rules = extract_gen_ed_rules(full_text, list(gen_ed_categories.keys()))

    return {
        "year": year,
        "catalog_year": year,
        "courses": courses,
        "course_meta": course_meta,
        "majors": {
            m: {
                "required_courses": (major_reqs.get(m, {}) or {}).get("required_courses", []),
                "elective_requirements": (major_reqs.get(m, {}) or {}).get("elective_requirements", []),
            }
            for m in majors
        },
        "minors": {
            m: {
                "required_courses": (minor_reqs.get(m, {}) or {}).get("required_courses", []),
                "elective_requirements": (minor_reqs.get(m, {}) or {}).get("elective_requirements", []),
            }
            for m in minors
        },
        "foundation_courses": foundation_courses,
        "gen_ed": {
            "categories": gen_ed_categories,
            "rules": gen_ed_rules,
        },
    }
