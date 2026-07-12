from __future__ import annotations

import csv
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from ui_models import AppRecord, ExportOptions, RiskAssessment


class ExportService:
    _FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")

    @staticmethod
    def _csv_safe(value: str) -> str:
        text = str(value)
        if text.startswith(ExportService._FORMULA_TRIGGER_CHARS):
            return f"'{text}"
        return text

    @staticmethod
    def export_csv(path: str, apps: list[AppRecord], results: dict[str, RiskAssessment], options: ExportOptions) -> None:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "App Name",
                    "Risk Level",
                    "Remote Administration",
                    "Remote File Sharing",
                    "Keylogging",
                    "Server Hosting",
                    "Publisher",
                    "Location",
                    "Recommended Action",
                ]
            )

            for app in apps:
                assessment = results.get(app.record_id)
                if not assessment:
                    continue
                writer.writerow(
                    [
                        ExportService._csv_safe(assessment.app_name),
                        assessment.risk_level.title(),
                        ExportService._yes_no(assessment.risk_flags[0]),
                        ExportService._yes_no(assessment.risk_flags[1]),
                        ExportService._yes_no(assessment.risk_flags[2]),
                        ExportService._yes_no(assessment.risk_flags[3]),
                        ExportService._csv_safe(app.publisher),
                        ExportService._csv_safe(app.install_location),
                        ExportService._csv_safe(assessment.recommended_action),
                    ]
                )

            if options.include_system_log:
                writer.writerow([])
                writer.writerow(["Export Metadata", "", "", "", "", "", "", "", ""])
                writer.writerow(["Generated At", datetime.now().isoformat(), "", "", "", "", "", "", ""])
                writer.writerow(["Export Options", str(asdict(options)), "", "", "", "", "", "", ""])

    @staticmethod
    def export_pdf(path: str, apps: list[AppRecord], results: dict[str, RiskAssessment], options: ExportOptions) -> None:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
        except Exception as exc:
            raise RuntimeError(
                "reportlab is required to export PDF. Install with: pip install reportlab"
            ) from exc

        doc = SimpleDocTemplate(path, pagesize=letter)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "AppsAnalystTitle",
            parent=styles["Heading1"],
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=18,
        )
        section_style = ParagraphStyle(
            "AppsAnalystSection",
            parent=styles["Heading2"],
            textColor=colors.HexColor("#1152d4"),
            spaceAfter=8,
        )
        body_style = ParagraphStyle(
            "AppsAnalystBody",
            parent=styles["BodyText"],
            leading=14,
            spaceAfter=6,
        )

        elements = [Paragraph("Apps-Analyst Security Report", title_style)]
        elements.append(Paragraph(f"Time Range: {xml_escape(options.time_range)}", body_style))
        elements.append(Spacer(1, 10))

        export_rows = [["App", "Level", "Remote", "File", "Keylog", "Server"]]
        for app in apps:
            assessment = results.get(app.record_id)
            if not assessment:
                continue
            export_rows.append(
                [
                    Paragraph(xml_escape(assessment.app_name), body_style),
                    assessment.risk_level.title(),
                    ExportService._yes_no(assessment.risk_flags[0]),
                    ExportService._yes_no(assessment.risk_flags[1]),
                    ExportService._yes_no(assessment.risk_flags[2]),
                    ExportService._yes_no(assessment.risk_flags[3]),
                ]
            )

        if len(export_rows) == 1:
            elements.append(Paragraph("No analyzed results are available for export.", body_style))
        else:
            table = Table(export_rows, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1152d4")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#f8fafc")]),
                        ("PADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            elements.append(table)

        if options.include_detailed_risks:
            elements.append(Spacer(1, 16))
            elements.append(Paragraph("Detailed Findings", section_style))
            for app in apps:
                assessment = results.get(app.record_id)
                if not assessment:
                    continue
                elements.append(
                    Paragraph(
                        f"<b>{xml_escape(assessment.app_name)}</b> ({xml_escape(assessment.risk_level.title())})",
                        body_style,
                    )
                )
                elements.append(Paragraph(xml_escape(assessment.overview), body_style))
                elements.append(Paragraph(f"Warning: {xml_escape(assessment.user_warning)}", body_style))
                elements.append(Paragraph(f"Action: {xml_escape(assessment.recommended_action)}", body_style))
                elements.append(Spacer(1, 8))

        if options.include_system_log:
            elements.append(Spacer(1, 16))
            elements.append(Paragraph("Export Metadata", section_style))
            elements.append(Paragraph(f"Generated At: {datetime.now().isoformat()}", body_style))
            elements.append(Paragraph(f"Export Path: {xml_escape(Path(path).name)}", body_style))

        doc.build(elements)

    @staticmethod
    def _yes_no(value: bool) -> str:
        return "Yes" if value else "No"
