from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover - optional dependency during runtime
    yaml = None

DEFAULT_MODEL_NAME = "gemma3:1b"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.yaml"


def load_config() -> dict[str, Any]:
    if yaml is None:
        return {}
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except OSError:
        return {}


def get_model_name() -> str:
    config = load_config()
    model_name = config.get("llm_settings", {}).get("model_name")
    return str(model_name).strip() if model_name else DEFAULT_MODEL_NAME
