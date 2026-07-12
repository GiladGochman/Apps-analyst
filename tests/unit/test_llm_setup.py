from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils import llm_setup


class _FakeOllamaOffline:
    def list(self):
        raise ConnectionError("no server running")


def test_check_and_pull_model_returns_offline_marker_when_ollama_not_running(monkeypatch) -> None:
    monkeypatch.setattr(llm_setup, "ollama", _FakeOllamaOffline())

    result = llm_setup.check_and_pull_model(model_name="gemma3:1b")

    assert result == "ERROR_OLLAMA_OFFLINE"


class _FakeOllamaModelPresent:
    def list(self):
        return {"models": [{"name": "gemma3:1b"}]}

    def pull(self, model_name, stream=True):
        raise AssertionError("pull should not be called when the model is already installed")


def test_check_and_pull_model_returns_true_when_model_already_installed(monkeypatch) -> None:
    monkeypatch.setattr(llm_setup, "ollama", _FakeOllamaModelPresent())

    result = llm_setup.check_and_pull_model(model_name="gemma3:1b")

    assert result is True


class _FakeOllamaNeedsPull:
    def list(self):
        return {"models": [{"name": "other-model"}]}

    def pull(self, model_name, stream=True):
        yield {"status": "pulling manifest"}
        yield {"completed": 50, "total": 100, "digest": "sha256:abc"}
        yield {"completed": 100, "total": 100, "digest": "sha256:abc"}


def test_check_and_pull_model_streams_progress_and_succeeds(monkeypatch) -> None:
    monkeypatch.setattr(llm_setup, "ollama", _FakeOllamaNeedsPull())
    messages: list[str] = []

    result = llm_setup.check_and_pull_model(
        model_name="gemma3:1b",
        progress_callback=lambda message, update_last=False: messages.append(message),
    )

    assert result is True
    assert any("Downloading" in message for message in messages)
    assert any("%" in message for message in messages)


class _FakeOllamaPullFails:
    def list(self):
        return {"models": []}

    def pull(self, model_name, stream=True):
        raise RuntimeError("network unreachable")


def test_check_and_pull_model_returns_error_message_when_pull_fails(monkeypatch) -> None:
    monkeypatch.setattr(llm_setup, "ollama", _FakeOllamaPullFails())

    result = llm_setup.check_and_pull_model(model_name="gemma3:1b")

    assert result == "network unreachable"


def test_check_and_pull_model_defaults_to_configured_model_name(monkeypatch) -> None:
    seen_names = []

    class _FakeOllamaRecordsModelName:
        def list(self):
            return {"models": []}

        def pull(self, model_name, stream=True):
            seen_names.append(model_name)
            return iter([{"completed": 1, "total": 1, "digest": "sha256:x"}])

    monkeypatch.setattr(llm_setup, "ollama", _FakeOllamaRecordsModelName())
    monkeypatch.setattr(llm_setup, "get_model_name", lambda: "configured-model")

    result = llm_setup.check_and_pull_model()

    assert result is True
    assert seen_names == ["configured-model"]
