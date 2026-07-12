from __future__ import annotations

from datetime import datetime

from collectors.win_apps_scanner import WinAppsScanner
from ui_models import AppRecord


class ScanService:
    @staticmethod
    def default_scan_depth() -> str:
        return WinAppsScanner().scan_depth

    @staticmethod
    def scan(progress_callback=None, include_registry=True, include_filesystem=True, scan_depth=None) -> list[AppRecord]:
        registry_apps, exe_apps = WinAppsScanner(scan_depth=scan_depth).scan(
            progress_callback=progress_callback,
            include_registry=include_registry,
            include_filesystem=include_filesystem,
        )
        discovered_at = datetime.now()
        unified: list[AppRecord] = []

        for raw in registry_apps:
            unified.append(ScanService._to_app_record(raw, "Registry", discovered_at))

        for raw in exe_apps:
            unified.append(ScanService._to_app_record(raw, "Filesystem", discovered_at))

        unified.sort(key=lambda app: (app.name.lower(), app.source_kind, app.install_location.lower()))
        return unified

    @staticmethod
    def _to_app_record(raw: dict, source_kind: str, discovered_at: datetime) -> AppRecord:
        source_key = "registry" if source_kind == "Registry" else "filesystem"
        return AppRecord(
            record_id=ScanService._record_id(raw, source_key),
            name=raw.get("name", "Unknown"),
            version=raw.get("version", "Unknown"),
            publisher=raw.get("publisher", "Unknown"),
            install_location=raw.get("install_location", "Unknown"),
            source_kind=source_kind,
            discovered_at=discovered_at,
            install_date=raw.get("install_date", "Unknown"),
            source_registry=raw.get("source_registry", "Unknown"),
            raw=raw,
        )

    @staticmethod
    def _record_id(raw: dict, source_kind: str) -> str:
        name = raw.get("name", "unknown").strip().lower()
        location = raw.get("install_location", "unknown").strip().lower()
        version = raw.get("version", "unknown").strip().lower()
        return f"{source_kind}:{name}:{version}:{location}"
