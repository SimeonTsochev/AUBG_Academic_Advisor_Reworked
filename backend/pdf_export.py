from __future__ import annotations
from typing import Dict
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

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
    for sem in plan.get("semester_plan", []):
        course_codes = []
        for c in sem.get("courses", []):
            if isinstance(c, dict):
                course_codes.append(c.get("code", ""))
            else:
                course_codes.append(str(c))
        data.append([
            sem.get("term", ""),
            ", ".join([c for c in course_codes if c]),
            str(sem.get("credits", 0))
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
