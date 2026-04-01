from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, Optional
import re

import fitz
import pdfplumber
from rapidfuzz import fuzz
from rapidocr_onnxruntime import RapidOCR

from catalog_cache import getCatalogCache
from excel_course_catalog import (
    get_course as get_excel_course_record,
    list_courses as list_excel_courses,
    normalize_course_code,
)

TranscriptStatus = Literal["completed", "in_progress"]

SUPPORTED_TRANSCRIPT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

_COURSE_CODE_RE = re.compile(r"\b([A-Z]{2,4})\s*[-/ ]\s*([0-9OILS]{3,4}[A-Z]?)\b", re.IGNORECASE)
_TERM_RE = re.compile(r"\b(Spring|Summer|Fall|Winter)\s+([12][0-9]{3})\b", re.IGNORECASE)
_TERM_TOTAL_RE = re.compile(
    r"\bterm\b.*?\b(Spring|Summer|Fall|Winter)\s+([12][0-9]{3})\b.*?\btotals?\b",
    re.IGNORECASE,
)
_IN_PROGRESS_RE = re.compile(
    r"\b(in\s*progress|current\s*term|registered|registration|enrolled|status\s*:\s*ip|ip)\b",
    re.IGNORECASE,
)
_COMPLETED_CONTEXT_RE = re.compile(r"\b(completed|past\s*term|prior\s*term|earned)\b", re.IGNORECASE)
_SPACE_RE = re.compile(r"\s+")
_YEAR_RE = re.compile(r"^[12][0-9]{3}$")
_CREDIT_TOKEN_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
_GRADE_TOKEN_RE = re.compile(r"^(?:A|A-|A\+|B|B-|B\+|C|C-|C\+|D|D\+|D-|F|P|S|U|W|IP|AU|TR|NR)$")
_INSTRUCTOR_SPLIT_RE = re.compile(r"\b(?:instructor|professor)\b.*$", re.IGNORECASE)
_COURSE_TRAILER_RE = re.compile(
    r"\b(?:credits?|ects|attempted|earned|points?|standing|gpa|term\s+totals?|semester\s+totals?)\b.*$",
    re.IGNORECASE,
)
_HEADER_NOISE_RE = re.compile(
    r"\b(?:course\s+code|course\s+title|class\s+standing|good\s+standing|advisor|student|transcript|"
    r"cumulative|quality\s+points|academic\s+status|term\s+gpa|cum(?:ulative)?\s+gpa|credits\s+attempted|"
    r"credits\s+earned|page\s+\d+|totals?)\b",
    re.IGNORECASE,
)
_TABLE_HEADER_LINE_RE = re.compile(
    r"^(?:course|title|instructor|final\s+grade|course\s+credits|credits\s+earned)$",
    re.IGNORECASE,
)

_OCR_ENGINE: Optional[RapidOCR] = None


@dataclass
class TranscriptLine:
    page_number: int
    text: str
    confidence: float = 1.0


@dataclass
class ParsedTranscriptCourse:
    raw_code: str
    normalized_code: str
    raw_title: Optional[str]
    status: TranscriptStatus
    term: Optional[str]
    page_number: int
    text_confidence: float


@dataclass(frozen=True)
class CatalogSearchRecord:
    code: str
    title: str
    code_compact: str
    prefix: str
    title_key: str


def import_transcript_document(file_bytes: bytes, filename: str) -> dict[str, Any]:
    if not file_bytes:
        raise ValueError("Please upload a transcript file.")

    extension = Path(filename or "").suffix.lower()
    if extension not in SUPPORTED_TRANSCRIPT_EXTENSIONS:
        raise ValueError("Unsupported file type. Please upload a PDF, PNG, JPG, or JPEG transcript.")

    lines, extraction_warnings = extract_transcript_lines_from_bytes(file_bytes, extension)
    parsed_courses = parse_transcript_lines(lines)
    if not parsed_courses:
        raise ValueError(
            "No course rows could be detected from this file. Please try another transcript or add courses manually."
        )

    response = build_transcript_import_response(parsed_courses)
    response["warnings"] = list(dict.fromkeys([*extraction_warnings, *response["warnings"]]))
    return response


def extract_transcript_lines_from_bytes(
    file_bytes: bytes,
    extension: str,
) -> tuple[list[TranscriptLine], list[str]]:
    warnings: list[str] = []

    if extension == ".pdf":
        direct_lines = _extract_pdf_text_lines(file_bytes)
        if _looks_like_useful_transcript_text(direct_lines):
            return direct_lines, warnings

        ocr_lines = _extract_pdf_ocr_lines(file_bytes)
        if ocr_lines:
            warnings.append("OCR was used to read this transcript. Please review the detected courses before importing.")
            return ocr_lines, warnings

        return direct_lines, warnings

    ocr_lines = _extract_ocr_lines_from_image_bytes(file_bytes, page_number=1)
    if ocr_lines:
        warnings.append("OCR was used to read this transcript. Please review the detected courses before importing.")
    return ocr_lines, warnings


def parse_transcript_lines(lines: list[TranscriptLine]) -> list[ParsedTranscriptCourse]:
    ordered_lines = [
        TranscriptLine(
            page_number=line.page_number,
            text=_normalize_space(_normalize_transcript_text(line.text)),
            confidence=line.confidence,
        )
        for line in lines
        if _normalize_space(_normalize_transcript_text(line.text))
    ]

    parsed: list[tuple[int, ParsedTranscriptCourse]] = []
    current_term: Optional[str] = None
    current_status: TranscriptStatus = "completed"
    open_section_course_start = 0

    for index, line in enumerate(ordered_lines):
        text = line.text
        if not text:
            continue

        if _is_course_table_header_line(text):
            open_section_course_start = len(parsed)
            continue

        term_label = _extract_term_label(text)
        if term_label:
            if _looks_like_term_totals_line(text):
                parsed = _apply_term_to_recent_courses(parsed, open_section_course_start, term_label)
                open_section_course_start = len(parsed)
                current_term = None
                current_status = "completed"
            else:
                current_term = term_label
                if _line_marks_in_progress(text):
                    current_status = "in_progress"
                elif _COMPLETED_CONTEXT_RE.search(text):
                    current_status = "completed"
                elif _HEADER_NOISE_RE.search(text) or _looks_like_term_header(text):
                    current_status = "completed"

        if _is_context_only_line(text):
            if _line_marks_in_progress(text):
                current_status = "in_progress"
            elif _COMPLETED_CONTEXT_RE.search(text):
                current_status = "completed"
            continue

        course = _parse_course_line(
            ordered_lines=ordered_lines,
            index=index,
            current_term=current_term,
            current_status=current_status,
        )
        if course is not None:
            parsed.append((index, course))

    return _dedupe_parsed_courses([course for _, course in parsed])


def build_transcript_import_response(parsed_courses: list[ParsedTranscriptCourse]) -> dict[str, Any]:
    catalog_records = _catalog_search_space()
    completed: list[dict[str, Any]] = []
    in_progress: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for course in parsed_courses:
        response_course = _match_transcript_course(course, catalog_records)
        if course.status == "completed":
            completed.append(response_course)
        else:
            in_progress.append(response_course)
        if not response_course["matched_confidently"]:
            unmatched.append(dict(response_course))

    warnings: list[str] = []
    if unmatched:
        warnings.append("Some courses could not be matched and need review.")

    return {
        "completed": completed,
        "in_progress": in_progress,
        "unmatched": unmatched,
        "warnings": warnings,
    }


def _catalog_search_space() -> list[CatalogSearchRecord]:
    _ensure_catalog_index_loaded()
    records: list[CatalogSearchRecord] = []
    for raw_record in list_excel_courses():
        code = str(raw_record.get("code") or "").strip()
        title = str(raw_record.get("title") or code).strip() or code
        if not code:
            continue
        records.append(
            CatalogSearchRecord(
                code=code,
                title=title,
                code_compact=_compact_code(code),
                prefix=code.split(" ", 1)[0],
                title_key=_normalize_text_key(title),
            )
        )
    return records


def _match_transcript_course(
    course: ParsedTranscriptCourse,
    catalog_records: list[CatalogSearchRecord],
) -> dict[str, Any]:
    exact = get_excel_course_record(course.normalized_code)
    if exact is not None:
        title = str(exact.get("title") or course.raw_title or course.normalized_code)
        return {
            "raw_code": course.raw_code,
            "matched_code": exact.get("code"),
            "title": title,
            "raw_title": course.raw_title,
            "status": course.status,
            "term": course.term,
            "confidence": 0.99,
            "matched_confidently": True,
            "match_candidates": [
                {
                    "code": str(exact.get("code") or course.normalized_code),
                    "title": title,
                    "confidence": 0.99,
                }
            ],
        }

    raw_code_compact = _compact_code(course.normalized_code or course.raw_code)
    raw_title_key = _normalize_text_key(course.raw_title or "")
    raw_prefix = _code_prefix(course.normalized_code or course.raw_code)
    ranked_candidates: list[dict[str, Any]] = []

    for record in catalog_records:
        code_ratio = fuzz.ratio(raw_code_compact, record.code_compact) / 100 if raw_code_compact else 0.0
        code_partial = fuzz.partial_ratio(raw_code_compact, record.code_compact) / 100 if raw_code_compact else 0.0
        title_ratio = fuzz.token_set_ratio(raw_title_key, record.title_key) / 100 if raw_title_key else 0.0

        score = max(code_ratio, code_partial * 0.96)
        if raw_title_key:
            score = (0.75 * score) + (0.25 * title_ratio) if raw_code_compact else title_ratio
        if raw_prefix and raw_prefix == record.prefix:
            score += 0.04

        if score < 0.55:
            continue

        ranked_candidates.append(
            {
                "code": record.code,
                "title": record.title,
                "confidence": round(min(score, 0.99), 3),
                "code_ratio": code_ratio,
                "title_ratio": title_ratio,
            }
        )

    ranked_candidates.sort(
        key=lambda item: (
            -item["confidence"],
            -item["code_ratio"],
            -item["title_ratio"],
            item["code"],
        )
    )
    top_candidates = ranked_candidates[:5]
    best = top_candidates[0] if top_candidates else None

    matched_confidently = bool(
        best
        and (
            best["confidence"] >= 0.94
            or (best["code_ratio"] >= 0.9 and best["title_ratio"] >= 0.8)
        )
    )
    matched_code = best["code"] if best and best["confidence"] >= 0.82 else None
    matched_title = best["title"] if best and matched_code else (course.raw_title or course.normalized_code)
    confidence = float(best["confidence"]) if best else 0.0

    return {
        "raw_code": course.raw_code,
        "matched_code": matched_code,
        "title": matched_title,
        "raw_title": course.raw_title,
        "status": course.status,
        "term": course.term,
        "confidence": confidence,
        "matched_confidently": matched_confidently,
        "match_candidates": [
            {
                "code": candidate["code"],
                "title": candidate["title"],
                "confidence": float(candidate["confidence"]),
            }
            for candidate in top_candidates
        ],
    }


def _parse_course_line(
    *,
    ordered_lines: list[TranscriptLine],
    index: int,
    current_term: Optional[str],
    current_status: TranscriptStatus,
) -> Optional[ParsedTranscriptCourse]:
    line = ordered_lines[index]
    text = line.text
    match = _COURSE_CODE_RE.search(text)
    if match is None:
        return None
    if _HEADER_NOISE_RE.search(text) and len(text.split()) <= 8:
        return None

    prefix = match.group(1).upper()
    raw_number = match.group(2).upper()
    normalized_number = _normalize_course_number(raw_number)
    raw_code = f"{prefix}-{raw_number}"
    normalized_code = normalize_course_code(f"{prefix} {normalized_number}")
    if not normalized_code:
        return None

    status = _infer_course_status(ordered_lines, index, current_status)
    raw_title = _extract_course_title(ordered_lines, index, match)

    return ParsedTranscriptCourse(
        raw_code=raw_code,
        normalized_code=normalized_code,
        raw_title=raw_title,
        status=status,
        term=current_term,
        page_number=line.page_number,
        text_confidence=line.confidence,
    )


def _extract_course_title(
    ordered_lines: list[TranscriptLine],
    index: int,
    code_match: re.Match[str],
) -> Optional[str]:
    current = _clean_course_title_fragment(ordered_lines[index].text[code_match.end():])
    if current:
        return current

    def best_title_for_offsets(offsets: tuple[int, ...]) -> str:
        best_local_title = ""
        best_local_score = float("-inf")

        for offset in offsets:
            candidate_index = index + offset
            if candidate_index < 0 or candidate_index >= len(ordered_lines):
                continue
            candidate_text = ordered_lines[candidate_index].text
            if _COURSE_CODE_RE.search(candidate_text):
                continue
            if _looks_like_term_header(candidate_text) or _looks_like_term_totals_line(candidate_text):
                continue
            if _is_context_only_line(candidate_text) or _looks_like_instructor_line(candidate_text):
                continue
            candidate_title = _clean_course_title_fragment(candidate_text)
            if not _is_viable_title_text(candidate_title):
                continue

            word_count = len(candidate_title.split())
            score = (word_count * 8) + len(candidate_title) - (abs(offset) * 6)
            if score > best_local_score:
                best_local_score = score
                best_local_title = candidate_title

        return best_local_title

    forward_title = best_title_for_offsets((1, 2, 3))
    if forward_title:
        return forward_title

    backward_title = best_title_for_offsets((-1, -2, -3))
    return backward_title or None


def _clean_course_title_fragment(fragment: str) -> str:
    text = _normalize_space(_normalize_transcript_text(fragment))
    if not text:
        return ""

    text = _INSTRUCTOR_SPLIT_RE.sub("", text)
    text = _COURSE_TRAILER_RE.sub("", text)
    text = _TERM_RE.sub("", text)
    text = re.sub(r"\b(?:in\s*progress|current\s*term|registered|ip)\b", "", text, flags=re.IGNORECASE)
    text = text.replace("|", " ").replace("•", " ")

    tokens: list[str] = []
    for raw_token in text.split():
        token = raw_token.strip(",;:()[]{}")
        if not token:
            continue
        upper = token.upper()
        lower = token.lower()
        if lower in {"spring", "summer", "fall", "winter"}:
            continue
        if _YEAR_RE.match(token):
            continue
        if _CREDIT_TOKEN_RE.match(token):
            continue
        if upper in {"CR", "ECTS"}:
            continue
        if token == token.upper() and _GRADE_TOKEN_RE.match(upper):
            continue
        tokens.append(token)

    cleaned = _normalize_space(" ".join(tokens))
    if not cleaned or not any(char.isalpha() for char in cleaned):
        return ""
    return cleaned


def _is_viable_title_text(text: str) -> bool:
    if not text:
        return False
    if len(text) <= 2:
        return False
    if not any(char.isalpha() for char in text):
        return False
    if _TABLE_HEADER_LINE_RE.match(text):
        return False
    return True


def _looks_like_instructor_line(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    if lower.startswith("prof.") or lower.startswith("professor"):
        return True
    words = [token for token in re.split(r"\s+", text) if token]
    if not words:
        return False
    return (
        len(words) <= 2
        and all(word[0].isupper() for word in words if word and word[0].isalpha())
        and all(word.replace(".", "").isalpha() for word in words)
    )


def _dedupe_parsed_courses(courses: list[ParsedTranscriptCourse]) -> list[ParsedTranscriptCourse]:
    deduped: dict[str, ParsedTranscriptCourse] = {}
    for course in courses:
        key = course.normalized_code
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = course
            continue
        deduped[key] = _merge_parsed_courses(existing, course)
    return list(deduped.values())


def _merge_parsed_courses(
    left: ParsedTranscriptCourse,
    right: ParsedTranscriptCourse,
) -> ParsedTranscriptCourse:
    if left.status != right.status:
        preferred = right if right.status == "in_progress" else left
        other = left if preferred is right else right
    else:
        preferred = right if _course_term_sort_key(right.term) >= _course_term_sort_key(left.term) else left
        other = left if preferred is right else right

    return ParsedTranscriptCourse(
        raw_code=preferred.raw_code or other.raw_code,
        normalized_code=preferred.normalized_code,
        raw_title=preferred.raw_title or other.raw_title,
        status=preferred.status,
        term=preferred.term or other.term,
        page_number=preferred.page_number,
        text_confidence=max(preferred.text_confidence, other.text_confidence),
    )


def _apply_term_to_recent_courses(
    parsed_courses: list[tuple[int, ParsedTranscriptCourse]],
    start_index: int,
    term_label: str,
) -> list[tuple[int, ParsedTranscriptCourse]]:
    if start_index >= len(parsed_courses):
        return parsed_courses

    updated: list[tuple[int, ParsedTranscriptCourse]] = []
    for position, (line_index, course) in enumerate(parsed_courses):
        if position < start_index:
            updated.append((line_index, course))
            continue
        updated.append(
            (
                line_index,
                ParsedTranscriptCourse(
                    raw_code=course.raw_code,
                    normalized_code=course.normalized_code,
                    raw_title=course.raw_title,
                    status=course.status,
                    term=term_label,
                    page_number=course.page_number,
                    text_confidence=course.text_confidence,
                ),
            )
        )
    return updated


def _extract_pdf_text_lines(file_bytes: bytes) -> list[TranscriptLine]:
    extracted: list[TranscriptLine] = []
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []
            if words:
                extracted.extend(_pdf_words_to_lines(page_index, words))
                continue
            page_text = page.extract_text() or ""
            extracted.extend(
                TranscriptLine(page_number=page_index, text=line_text, confidence=1.0)
                for line_text in page_text.splitlines()
                if _normalize_space(line_text)
            )
    return extracted


def _pdf_words_to_lines(page_number: int, words: list[dict[str, Any]]) -> list[TranscriptLine]:
    ordered_words = sorted(
        words,
        key=lambda item: (round(float(item.get("top", 0.0)) / 3.0), float(item.get("x0", 0.0))),
    )
    lines: list[TranscriptLine] = []
    current_words: list[dict[str, Any]] = []
    current_top: Optional[float] = None

    def flush() -> None:
        if not current_words:
            return
        text = _normalize_space(" ".join(str(word.get("text") or "") for word in sorted(current_words, key=lambda item: float(item.get("x0", 0.0)))))
        if text:
            lines.append(TranscriptLine(page_number=page_number, text=text, confidence=1.0))

    for word in ordered_words:
        top = float(word.get("top", 0.0))
        if current_top is None or abs(top - current_top) <= 3.0:
            current_words.append(word)
            current_top = top if current_top is None else min(current_top, top)
            continue
        flush()
        current_words = [word]
        current_top = top

    flush()
    return lines


def _extract_pdf_ocr_lines(file_bytes: bytes) -> list[TranscriptLine]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        extracted: list[TranscriptLine] = []
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            extracted.extend(_extract_ocr_lines_from_image_bytes(pix.tobytes("png"), page_number=page_index + 1))
        return extracted
    finally:
        doc.close()


def _extract_ocr_lines_from_image_bytes(file_bytes: bytes, page_number: int) -> list[TranscriptLine]:
    ocr_engine = _get_ocr_engine()
    results, _ = ocr_engine(file_bytes)
    if not results:
        return []

    ordered: list[tuple[float, float, TranscriptLine]] = []
    for item in results:
        if not isinstance(item, list) or len(item) < 3:
            continue
        box = item[0]
        text = _normalize_space(str(item[1] or ""))
        confidence = float(item[2]) if isinstance(item[2], (int, float)) else 0.0
        if not text:
            continue

        y_value = 0.0
        x_value = 0.0
        if isinstance(box, list) and box:
            first_point = box[0]
            if isinstance(first_point, list) and len(first_point) >= 2:
                x_value = float(first_point[0])
                y_value = float(first_point[1])

        ordered.append(
            (
                y_value,
                x_value,
                TranscriptLine(page_number=page_number, text=text, confidence=confidence),
            )
        )

    ordered.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ordered]


def _get_ocr_engine() -> RapidOCR:
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def _ensure_catalog_index_loaded() -> None:
    if list_excel_courses():
        return
    getCatalogCache()


def _looks_like_useful_transcript_text(lines: list[TranscriptLine]) -> bool:
    total_chars = sum(len(line.text) for line in lines)
    course_code_hits = sum(1 for line in lines if _COURSE_CODE_RE.search(line.text))
    return total_chars >= 80 and course_code_hits >= 1


def _normalize_course_number(value: str) -> str:
    cleaned = value.upper()
    translation = str.maketrans({
        "O": "0",
        "I": "1",
        "L": "1",
        "S": "5",
    })
    return cleaned.translate(translation)


def _line_marks_in_progress(text: str) -> bool:
    return bool(_IN_PROGRESS_RE.search(text))


def _looks_like_term_header(text: str) -> bool:
    return bool(_TERM_RE.search(text)) and _COURSE_CODE_RE.search(text) is None


def _looks_like_term_totals_line(text: str) -> bool:
    return bool(_TERM_TOTAL_RE.search(text))


def _extract_term_label(text: str) -> Optional[str]:
    match = _TERM_TOTAL_RE.search(text) or _TERM_RE.search(text)
    if match is None:
        return None
    season = match.group(1).capitalize()
    year = match.group(2)
    return f"{season} {year}"


def _is_context_only_line(text: str) -> bool:
    if _COURSE_CODE_RE.search(text):
        return False
    return bool(_IN_PROGRESS_RE.search(text) or _COMPLETED_CONTEXT_RE.search(text) or _HEADER_NOISE_RE.search(text) or _TERM_RE.search(text))


def _is_course_table_header_line(text: str) -> bool:
    return bool(_TABLE_HEADER_LINE_RE.match(text))


def _infer_course_status(
    ordered_lines: list[TranscriptLine],
    index: int,
    current_status: TranscriptStatus,
) -> TranscriptStatus:
    text = ordered_lines[index].text
    if _line_marks_in_progress(text):
        return "in_progress"
    if _COMPLETED_CONTEXT_RE.search(text):
        return "completed"

    for look_ahead in range(index + 1, min(len(ordered_lines), index + 6)):
        candidate = ordered_lines[look_ahead].text
        if _COURSE_CODE_RE.search(candidate) or _looks_like_term_header(candidate):
            break
        if _line_marks_in_progress(candidate):
            return "in_progress"
        if _COMPLETED_CONTEXT_RE.search(candidate):
            return "completed"

    return "in_progress" if current_status == "in_progress" else "completed"


def _course_term_sort_key(term: Optional[str]) -> tuple[int, int]:
    if not term:
        return (0, 0)
    match = _TERM_RE.search(term)
    if match is None:
        return (0, 0)
    season = match.group(1).capitalize()
    year = int(match.group(2))
    season_rank = {
        "Winter": 1,
        "Spring": 2,
        "Summer": 3,
        "Fall": 4,
    }.get(season, 0)
    return (year, season_rank)


def _normalize_text_key(text: str) -> str:
    cleaned = _normalize_space(_normalize_transcript_text(text)).lower()
    return re.sub(r"[^a-z0-9 ]+", " ", cleaned).strip()


def _normalize_transcript_text(text: str) -> str:
    normalized = (
        str(text or "")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2212", "-")
        .replace("\u00a0", " ")
    )
    normalized = re.sub(r"(?i)\b(Term)(Spring|Summer|Fall|Winter)", r"\1 \2", normalized)
    normalized = re.sub(r"(?i)\b(Spring|Summer|Fall|Winter)(\d{4})\b", r"\1 \2", normalized)
    normalized = re.sub(r"\b(Good)(Standing)\b", r"\1 \2", normalized, flags=re.IGNORECASE)
    return normalized


def _normalize_space(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip()


def _compact_code(code: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(code or "").upper())


def _code_prefix(code: str) -> str:
    match = re.match(r"([A-Z]{2,4})", str(code or "").upper())
    return match.group(1) if match else ""
