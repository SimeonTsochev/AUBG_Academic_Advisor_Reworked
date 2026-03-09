from __future__ import annotations
from typing import Any, Dict
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors


def _term_sort_key(term: str) -> tuple[int, int, str]:
    if not isinstance(term, str):
        return (9999, 9, "")
    parts = term.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        return (9999, 9, term)
    season_rank = {"Spring": 0, "Fall": 1}.get(parts[0], 9)
    return (int(parts[1]), season_rank, term)


def _manual_credit_label(entry: Dict[str, Any]) -> str:
    credits = entry.get("credits", 0)
    credit_type = str(entry.get("credit_type") or "").strip().upper()
    suffix = "Transfer Credit"
    if credit_type == "GENED":
        category = str(entry.get("gened_category") or "").strip()
        if category:
            suffix = f"Transfer Credit; GenEd: {category}"
    elif credit_type == "MAJOR_ELECTIVE":
        program = str(entry.get("program") or "").strip()
        if program:
            suffix = f"Transfer Credit; Major Elective: {program}"
    elif credit_type == "FREE_ELECTIVE":
        suffix = "Transfer Credit; Free Elective"
    return f"OTH 0001 - {suffix} ({credits} cr)"


def _course_label_for_pdf(course: Dict[str, Any]) -> str:
    code = str(course.get("code") or "").strip()
    name = str(course.get("name") or "").strip()
    tags = course.get("tags") if isinstance(course.get("tags"), list) else []
    credits = int(course.get("credits", 0) or 0)
    is_retake = bool(course.get("is_retake")) or any(
        isinstance(tag, str) and tag.strip().lower() == "retake"
        for tag in tags
    )
    is_previous_attempt = any(
        isinstance(tag, str) and tag.strip().lower() == "previous attempt"
        for tag in tags
    )
    if not code:
        return ""
    if is_previous_attempt:
        if name and name != code:
            return f"{code} - {name} (Replaced by Retake, 0 cr)"
        return f"{code} (Replaced by Retake, 0 cr)"
    if is_retake:
        if name and name != code:
            return f"{code} - {name} (Retake, {credits} cr)"
        return f"{code} (Retake, {credits} cr)"
    return code

def plan_to_pdf_bytes(plan: Dict) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title="Degree Plan")
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("AUBG Degree Plan", styles["Title"]))
    story.append(Spacer(1, 12))

    majors = ", ".join(plan.get("majors", [])) or "—"
    minors = ", ".join(plan.get("minors", [])) or "—"
    story.append(Paragraph(f"<b>Majors:</b> {majors}", styles["Normal"]))
    story.append(Paragraph(f"<b>Minors:</b> {minors}", styles["Normal"]))
    story.append(Spacer(1, 12))

    summary = plan.get("summary", {})
    story.append(Paragraph(
        f"<b>Summary:</b> required {summary.get('total_required', 0)}, "
        f"completed {summary.get('completed', 0)}, remaining {summary.get('remaining', 0)}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Semester-by-semester plan</b>", styles["Heading2"]))
    data = [["Term", "Courses", "Credits"]]
    term_rows: Dict[str, Dict[str, Any]] = {}
    for sem in plan.get("semester_plan", []):
        if not isinstance(sem, dict):
            continue
        term = sem.get("term", "")
        if not isinstance(term, str):
            term = ""
        row = term_rows.setdefault(term, {"courses": [], "credits": 0})
        for c in sem.get("courses", []):
            if isinstance(c, dict):
                label = _course_label_for_pdf(c)
                if label:
                    row["courses"].append(label)
            elif c:
                row["courses"].append(str(c))
        row["credits"] += int(sem.get("credits", 0) or 0)

    for entry in plan.get("manual_credits", []):
        if not isinstance(entry, dict):
            continue
        term = entry.get("term", "")
        if not isinstance(term, str):
            continue
        row = term_rows.setdefault(term, {"courses": [], "credits": 0})
        row["courses"].append(_manual_credit_label(entry))
        row["credits"] += int(entry.get("credits", 0) or 0)

    for term in sorted(term_rows.keys(), key=_term_sort_key):
        row = term_rows[term]
        data.append([
            term,
            ", ".join([c for c in row.get("courses", []) if c]),
            str(int(row.get("credits", 0) or 0))
        ])
    table = Table(data, colWidths=[90, 360, 60])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.whitesmoke, colors.white]),
    ]))
    story.append(table)

    alerts = plan.get("minor_alerts", [])
    if alerts:
        story.append(Spacer(1, 16))
        story.append(Paragraph("<b>Minor opportunities</b>", styles["Heading2"]))
        for a in alerts:
            story.append(Paragraph(
                f"You are close to completing <b>{a.get('minor')}</b>. Remaining: "
                f"{', '.join(a.get('remaining_courses', []))}",
                styles["Normal"]
            ))

    doc.build(story)
    return buf.getvalue()
