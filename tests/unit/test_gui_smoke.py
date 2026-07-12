from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

pytest.importorskip("PySide6")

from gui import AnalysisPage, DashboardPage, MainWindow, ReportPage
from ui_models import AppRecord, RiskAssessment

pytestmark = [pytest.mark.gui]


def _make_app(record_id: str, name: str, source_kind: str = "Registry") -> AppRecord:
    return AppRecord(
        record_id=record_id,
        name=name,
        version="1.0",
        publisher="Example Publisher",
        install_location=r"C:\Program Files\Example",
        source_kind=source_kind,
        discovered_at=datetime(2026, 1, 1, 12, 0, 0),
    )


def _make_assessment(app: AppRecord, risk_level: str = "high", risk_flags=None) -> RiskAssessment:
    return RiskAssessment(
        app_id=app.record_id,
        app_name=app.name,
        overview="Overview text.",
        risk_flags=risk_flags or [True, False, False, False],
        risk_level=risk_level,
        evidence={},
        detected_indicators=[],
        why_this_matters="Matters.",
        user_warning="Warning.",
        recommended_action="Action.",
        raw_llm_text="raw",
    )


def test_dashboard_page_set_metrics_updates_stat_cards(qtbot) -> None:
    page = DashboardPage()
    qtbot.addWidget(page)

    page.set_metrics(10, 2, 1, "12:30")

    assert page.total_card.value_label.text() == "10"
    assert page.high_card.value_label.text() == "2"
    assert page.medium_card.value_label.text() == "1"
    assert page.last_card.value_label.text() == "12:30"


def test_dashboard_page_shows_placeholder_when_no_detections(qtbot) -> None:
    page = DashboardPage()
    qtbot.addWidget(page)

    page.set_detections([], {})

    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "No detections yet"


def test_dashboard_page_lists_high_risk_detection(qtbot) -> None:
    page = DashboardPage()
    qtbot.addWidget(page)
    app = _make_app("registry:app:1.0:loc", "TeamViewer")
    assessment = _make_assessment(app, risk_level="high", risk_flags=[True, False, False, False])

    page.set_detections([app], {app.record_id: assessment})

    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "TeamViewer"
    assert page.table.item(0, 3).text() == "High"


def test_report_page_enables_export_buttons_only_when_analyzed(qtbot) -> None:
    page = ReportPage()
    qtbot.addWidget(page)

    page.set_summary(5, 0, 0, 0)
    assert not page.pdf_button.isEnabled()
    assert not page.csv_button.isEnabled()

    page.set_summary(5, 3, 1, 1)
    assert page.pdf_button.isEnabled()
    assert page.csv_button.isEnabled()


def test_analysis_page_search_filters_visible_apps(qtbot) -> None:
    page = AnalysisPage()
    qtbot.addWidget(page)
    apps = [
        _make_app("registry:teamviewer:1.0:loc", "TeamViewer"),
        _make_app("registry:notepad:1.0:loc", "Notepad"),
    ]

    page.set_apps(apps, {})
    assert page.table.rowCount() == 2

    page.search.setText("team")

    assert page.table.rowCount() == 1
    assert page.table.item(0, 1).text() == "TeamViewer"


def test_main_window_builds_and_switches_pages(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.nav_buttons["dashboard"].isChecked()

    window.switch_page("reports")

    assert window.stack.currentIndex() == 2
    assert window.nav_buttons["reports"].isChecked()
