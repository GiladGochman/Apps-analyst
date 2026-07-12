from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui_models import AppRecord, ExportOptions, RiskAssessment
from ui_services.export_service import ExportService


def _make_app(record_id: str, name: str) -> AppRecord:
    return AppRecord(
        record_id=record_id,
        name=name,
        version="1.0",
        publisher="Example Publisher",
        install_location=r"C:\Program Files\Example",
        source_kind="Registry",
        discovered_at=datetime(2026, 1, 1, 12, 0, 0),
    )


def _make_assessment(app_id: str, app_name: str, risk_level: str, risk_flags: list[bool]) -> RiskAssessment:
    return RiskAssessment(
        app_id=app_id,
        app_name=app_name,
        overview=f"{app_name} overview",
        risk_flags=risk_flags,
        risk_level=risk_level,
        evidence={},
        detected_indicators=[],
        why_this_matters="Why this matters text.",
        user_warning="User warning text.",
        recommended_action="Recommended action text.",
        raw_llm_text="raw",
    )


def test_export_csv_writes_expected_row_for_analyzed_app(tmp_path: Path) -> None:
    app = _make_app("registry:teamviewer:1.0:c:\\program files\\example", "TeamViewer")
    assessment = _make_assessment(app.record_id, "TeamViewer", "high", [True, False, False, False])
    path = tmp_path / "report.csv"

    ExportService.export_csv(str(path), [app], {app.record_id: assessment}, ExportOptions())

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[0][0] == "App Name"
    assert rows[1][:2] == ["TeamViewer", "High"]
    assert rows[1][2] == "Yes"
    assert rows[1][3] == "No"


def test_export_csv_skips_apps_without_an_assessment(tmp_path: Path) -> None:
    analyzed = _make_app("registry:analyzed:1.0:loc", "Analyzed App")
    unanalyzed = _make_app("registry:unanalyzed:1.0:loc", "Unanalyzed App")
    assessment = _make_assessment(analyzed.record_id, "Analyzed App", "low", [False, False, False, False])
    path = tmp_path / "report.csv"

    ExportService.export_csv(
        str(path), [analyzed, unanalyzed], {analyzed.record_id: assessment}, ExportOptions()
    )

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    app_names = [row[0] for row in rows[1:] if row]
    assert "Analyzed App" in app_names
    assert "Unanalyzed App" not in app_names


def test_export_csv_appends_metadata_rows_when_requested(tmp_path: Path) -> None:
    app = _make_app("registry:teamviewer:1.0:loc", "TeamViewer")
    assessment = _make_assessment(app.record_id, "TeamViewer", "low", [False, False, False, False])
    path = tmp_path / "report.csv"

    ExportService.export_csv(
        str(path), [app], {app.record_id: assessment}, ExportOptions(include_system_log=True)
    )

    content = path.read_text(encoding="utf-8")
    assert "Export Metadata" in content
    assert "Generated At" in content


def test_export_csv_neutralizes_formula_injection_in_app_name(tmp_path: Path) -> None:
    malicious_name = "=cmd|' /c calc'!A1"
    app = _make_app("registry:malicious:1.0:loc", malicious_name)
    assessment = _make_assessment(app.record_id, malicious_name, "low", [False, False, False, False])
    path = tmp_path / "report.csv"

    ExportService.export_csv(str(path), [app], {app.record_id: assessment}, ExportOptions())

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[1][0] == f"'{malicious_name}"


def test_export_csv_neutralizes_formula_injection_in_publisher_and_location(tmp_path: Path) -> None:
    app = AppRecord(
        record_id="registry:app:1.0:loc",
        name="App",
        version="1.0",
        publisher="+cmd|' /c calc'!A1",
        install_location="@cmd|' /c calc'!A1",
        source_kind="Registry",
        discovered_at=datetime(2026, 1, 1, 12, 0, 0),
    )
    assessment = _make_assessment(app.record_id, "App", "low", [False, False, False, False])
    path = tmp_path / "report.csv"

    ExportService.export_csv(str(path), [app], {app.record_id: assessment}, ExportOptions())

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))

    assert rows[1][6] == f"'{app.publisher}"
    assert rows[1][7] == f"'{app.install_location}"


def test_export_pdf_creates_a_non_empty_pdf_file(tmp_path: Path) -> None:
    app = _make_app("registry:teamviewer:1.0:loc", "TeamViewer")
    assessment = _make_assessment(app.record_id, "TeamViewer", "high", [True, True, False, False])
    path = tmp_path / "report.pdf"

    ExportService.export_pdf(str(path), [app], {app.record_id: assessment}, ExportOptions())

    assert path.exists()
    assert path.stat().st_size > 0
    assert path.read_bytes().startswith(b"%PDF")


def test_export_pdf_handles_special_characters_without_raising(tmp_path: Path) -> None:
    tricky_name = "Weird & <Tool> \"Name\""
    app = _make_app("registry:weird:1.0:loc", tricky_name)
    assessment = RiskAssessment(
        app_id=app.record_id,
        app_name=tricky_name,
        overview="Overview with <tags> & ampersands.",
        risk_flags=[True, False, False, False],
        risk_level="high",
        evidence={},
        detected_indicators=[],
        why_this_matters="Matters.",
        user_warning="Warning with <b>markup-looking</b> text & symbols.",
        recommended_action="Action with & <angle> brackets.",
        raw_llm_text="raw",
    )
    path = tmp_path / "report.pdf"

    ExportService.export_pdf(str(path), [app], {app.record_id: assessment}, ExportOptions())

    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF")


def test_export_pdf_handles_no_analyzed_results(tmp_path: Path) -> None:
    app = _make_app("registry:teamviewer:1.0:loc", "TeamViewer")
    path = tmp_path / "report.pdf"

    ExportService.export_pdf(str(path), [app], {}, ExportOptions())

    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF")
