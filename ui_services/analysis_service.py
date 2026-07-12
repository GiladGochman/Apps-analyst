from __future__ import annotations

import re

from analysis.llm_analyzer import parseOllamaRes, sendToOllama
from analysis.web_researcher import search_web_info
from ui_models import AppRecord, RiskAssessment
from utils.llm_setup import check_and_pull_model

CAPABILITY_LABELS = [
    "Remote Administration",
    "Remote File Sharing",
    "Keylogging",
    "Server Hosting",
]

RISK_DESCRIPTIONS = {
    "Remote Administration": (
        "May allow a stranger to remotely control the computer, access files, "
        "or execute actions without the user's understanding."
    ),
    "Remote File Sharing": (
        "May allow sending, receiving, uploading, or downloading files from "
        "outside the device."
    ),
    "Keylogging": (
        "May capture keyboard input and expose passwords, payment details, "
        "or private messages."
    ),
    "Server Hosting": (
        "May expose services or files over the network and create an access "
        "point on the device."
    ),
}

CAPABILITY_PATTERNS = {
    "Remote Administration": (
        "remote access",
        "remote control",
        "remote desktop",
        "remote support",
        "unattended access",
        "remotely control",
        "desktop management",
    ),
    "Remote File Sharing": (
        "file transfer",
        "upload",
        "download",
        "sending files",
        "receiving files",
        "share files",
        "sync files",
        "manage files",
    ),
    "Keylogging": (
        "keylogging",
        "keylogger",
        "keystroke",
        "records keystrokes",
        "keyboard input",
    ),
    "Server Hosting": (
        "web server",
        "host a website",
        "hosting service",
        "network-accessible service",
        "browser-accessible service",
        "serve files",
    ),
}


class AnalysisService:
    @staticmethod
    def ensure_model(progress_callback=None):
        return check_and_pull_model(progress_callback=progress_callback)

    @staticmethod
    def analyze(app: AppRecord) -> RiskAssessment:
        web_info = search_web_info(app.name)
        llm_result = sendToOllama(web_info)
        if not llm_result:
            raise RuntimeError(f"LLM analysis failed for {app.name}.")
        risk_flags = parseOllamaRes(llm_result)
        return AnalysisService._build_assessment(app, llm_result, risk_flags)

    @staticmethod
    def _build_assessment(app: AppRecord, llm_text: str, risk_flags: list[bool]) -> RiskAssessment:
        explicit_overview = AnalysisService._extract_single_line(llm_text, "App Overview")
        overview = explicit_overview or f"{app.name} was analyzed from web search results."

        explicit_evidence = {
            label: AnalysisService._extract_explicit_evidence(llm_text, label)
            for label in CAPABILITY_LABELS
        }
        evidence = {
            label: explicit_evidence[label] or RISK_DESCRIPTIONS[label]
            for label in CAPABILITY_LABELS
        }
        indicators = AnalysisService._extract_bullets(llm_text, "Detected Indicators")
        why_this_matters = AnalysisService._extract_block(llm_text, "Why This Matters") or (
            "Unexpected remote-control or file-transfer tools can be used in scams or social-engineering attacks."
        )
        user_warning = AnalysisService._extract_block(llm_text, "User Warning") or (
            "If you did not expect this software, do not keep using it until you verify the source."
        )
        recommended_action = AnalysisService._extract_block(llm_text, "Recommended Action") or (
            "Verify the software source and remove it if it was not intentionally installed."
        )
        risk_level = AnalysisService._extract_single_line(llm_text, "Risk Level").lower()
        if risk_level not in {"low", "medium", "high"}:
            risk_level = AnalysisService._derive_risk_level(risk_flags)

        if not indicators:
            indicators = [
                label
                for label, flagged in zip(CAPABILITY_LABELS, risk_flags)
                if flagged
            ]

        risk_flags = AnalysisService._reconcile_risk_flags(
            risk_flags,
            explicit_overview,
            explicit_evidence,
            indicators,
        )

        derived_risk_level = AnalysisService._derive_risk_level(risk_flags)
        if (
            risk_level not in {"low", "medium", "high"}
            or AnalysisService._risk_rank(risk_level) < AnalysisService._risk_rank(derived_risk_level)
        ):
            risk_level = derived_risk_level

        return RiskAssessment(
            app_id=app.record_id,
            app_name=app.name,
            overview=overview,
            risk_flags=list(risk_flags),
            risk_level=risk_level,
            evidence=evidence,
            detected_indicators=indicators,
            why_this_matters=why_this_matters,
            user_warning=user_warning,
            recommended_action=recommended_action,
            raw_llm_text=llm_text,
        )

    @staticmethod
    def _derive_risk_level(risk_flags: list[bool]) -> str:
        if risk_flags[0] or risk_flags[2]:
            return "high"
        if any(risk_flags):
            return "medium"
        return "low"

    @staticmethod
    def _reconcile_risk_flags(
        risk_flags: list[bool],
        overview: str,
        evidence: dict[str, str],
        indicators: list[str],
    ) -> list[bool]:
        inference_text = "\n".join(
            part for part in [overview, *evidence.values(), *indicators] if part
        ).lower()
        resolved = list(risk_flags)
        for index, label in enumerate(CAPABILITY_LABELS):
            if resolved[index]:
                continue
            if any(pattern in inference_text for pattern in CAPABILITY_PATTERNS[label]):
                resolved[index] = True
        return resolved

    @staticmethod
    def _risk_rank(risk_level: str) -> int:
        return {"low": 0, "medium": 1, "high": 2}.get(risk_level, -1)

    @staticmethod
    def _extract_single_line(text: str, label: str) -> str:
        pattern = rf"^{re.escape(label)}:\s*(.+)$"
        match = re.search(pattern, text, flags=re.MULTILINE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_evidence(text: str, label: str) -> str:
        pattern = rf"^- {re.escape(label)}:\s*(.+)$"
        match = re.search(pattern, text, flags=re.MULTILINE)
        if match:
            return match.group(1).strip()
        return RISK_DESCRIPTIONS[label]

    @staticmethod
    def _extract_explicit_evidence(text: str, label: str) -> str:
        pattern = rf"^- {re.escape(label)}:\s*(.+)$"
        match = re.search(pattern, text, flags=re.MULTILINE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_bullets(text: str, section: str) -> list[str]:
        block = AnalysisService._extract_block(text, section)
        if not block:
            return []
        items = []
        for line in block.splitlines():
            stripped = line.strip()
            if stripped.startswith("- "):
                items.append(stripped[2:].strip())
        return items

    @staticmethod
    def _extract_block(text: str, label: str) -> str:
        pattern = rf"{re.escape(label)}:\s*(.*?)(?:\n[A-Z][A-Za-z ]+:\s|\Z)"
        match = re.search(pattern, text, flags=re.DOTALL)
        if not match:
            return ""
        block = match.group(1).strip()
        lines = [line.rstrip() for line in block.splitlines() if line.strip()]
        return "\n".join(lines).strip()
