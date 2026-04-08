import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.analytics import stats_engine
from utils import config


def generate_report(
    filepath, date_from=None, date_to=None, camera_id=None, rule_name=None, min_alarm_level=None, time_basis=None, gender=None
):
    doc = SimpleDocTemplate(filepath, pagesize=A4, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=24, textColor=colors.HexColor("#1a73e8"), spaceAfter=20)
    subtitle_style = ParagraphStyle("Subtitle", parent=styles["Normal"], fontSize=12, textColor=colors.grey, spaceAfter=10)
    section_style = ParagraphStyle(
        "Section", parent=styles["Heading2"], fontSize=16, textColor=colors.HexColor("#333333"), spaceBefore=20, spaceAfter=10
    )
    elements = []
    logo_path = config.get("report_logo_path", "")
    if logo_path and os.path.exists(logo_path):
        try:
            logo = Image(logo_path, width=2 * inch, height=1 * inch)
            logo.hAlign = "CENTER"
            elements.append(logo)
            elements.append(Spacer(1, 10))
        except Exception:
            pass
    elements.append(Paragraph("SmartEye Analytics Report", title_style))
    date_range = ""
    if date_from and date_to:
        date_range = f"Period: {date_from} to {date_to}"
    elif date_from:
        date_range = f"From: {date_from}"
    elif date_to:
        date_range = f"Until: {date_to}"
    else:
        date_range = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    elements.append(Paragraph(date_range, subtitle_style))
    filters = []
    if time_basis:
        filters.append(f"Time basis: {time_basis}")
    if rule_name:
        filters.append(f"Rule: {rule_name}")
    if min_alarm_level is not None:
        filters.append(f"Min alarm level: {min_alarm_level}")
    if gender:
        filters.append(f"Gender: {str(gender).title()}")
    if filters:
        elements.append(Paragraph(" | ".join(filters), subtitle_style))
    elements.append(Spacer(1, 20))
    summary = stats_engine.get_summary(date_from, date_to, camera_id, min_alarm_level=min_alarm_level, gender=gender)
    elements.append(Paragraph("Summary", section_style))
    summary_data = [
        ["Metric", "Value"],
        ["Total Detections", str(summary["total_detections"])],
        ["Violations", str(summary["violations"])],
        ["Compliant", str(summary["compliant"])],
        ["Compliance Rate", f"{summary['compliance_rate']}%"],
    ]
    summary_table = Table(summary_data, colWidths=[3 * inch, 3 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a73e8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Hourly Violation Distribution", section_style))
    hourly = stats_engine.get_hourly_violation_chart(
        date_from,
        date_to,
        camera_id=camera_id,
        rule_name=rule_name,
        min_alarm_level=min_alarm_level,
        time_basis=time_basis,
        gender=gender,
    )
    hourly_data = [["Hour", "Violations"]]
    for h in hourly:
        hourly_data.append([h["hour"] + ":00", str(h["count"])])
    hourly_table = Table(hourly_data, colWidths=[2 * inch, 2 * inch])
    hourly_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34a853")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ]
        )
    )
    elements.append(hourly_table)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Top Violators", section_style))
    persons = stats_engine.get_person_violations(
        date_from, date_to, camera_id=camera_id, rule_name=rule_name, min_alarm_level=min_alarm_level, gender=gender
    )
    person_data = [["Person", "Gender", "Violations"]]
    for p in persons:
        person_data.append([p["identity"], (p.get("gender") or "unknown").title(), str(p["count"])])
    if len(person_data) > 1:
        person_table = Table(person_data, colWidths=[2.8 * inch, 1.2 * inch, 1.0 * inch])
        person_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ea4335")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ]
            )
        )
        elements.append(person_table)
    else:
        elements.append(Paragraph("No violations recorded in this period.", styles["Normal"]))

    elements.append(Spacer(1, 20))
    elements.append(Paragraph("Violations by Gender", section_style))
    by_gender = stats_engine.get_gender_violations(
        date_from=date_from,
        date_to=date_to,
        camera_id=camera_id,
        rule_name=rule_name,
        min_alarm_level=min_alarm_level,
        gender=gender,
    )
    gender_data = [["Gender", "Violations"]]
    for row in by_gender:
        gender_data.append([(row.get("gender") or "unknown").title(), str(row.get("count", 0))])
    gender_table = Table(gender_data, colWidths=[2.5 * inch, 2.5 * inch])
    gender_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4285f4")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ]
        )
    )
    elements.append(gender_table)
    doc.build(elements)
    return filepath
