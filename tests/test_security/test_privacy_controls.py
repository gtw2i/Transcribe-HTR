from pathlib import Path

import pytest

import logging_config as lc
import resource_loaders as rl
from transcription_engine import TranscriptionEngine


def test_openai_client_missing_key_error_does_not_echo_secret(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError) as exc:
        rl.get_client(api_key="")

    message = str(exc.value)
    assert "No API key provided" in message
    assert "sk-" not in message


def test_gemini_client_missing_key_error_does_not_echo_secret(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    with pytest.raises(RuntimeError) as exc:
        rl.get_gemini_client(api_key="")

    message = str(exc.value)
    assert (
        "No Gemini API key provided" in message
        or "google-genai is not installed" in message
    )
    assert "AIza" not in message


def test_validate_settings_error_message_does_not_include_key_value():
    engine = TranscriptionEngine()

    ok, message = engine.validate_settings(
        api_key="sk-super-secret",
        img_bytes=b"img",
        provider="Gemini",
        gemini_api_key="",
    )

    assert ok is False
    assert "Gemini API key is required" in message
    assert "sk-super-secret" not in message


REPO_ROOT = Path(__file__).parent.parent.parent


def test_api_key_inputs_use_password_type_in_react_ui():
    """The React UI must mask API keys rather than rendering them in clear text."""
    password_input = REPO_ROOT / "frontend/src/components/shared/PasswordInput.jsx"
    source = password_input.read_text(encoding="utf-8")
    assert "'password'" in source or '"password"' in source

    # Every provider key field must go through that component.
    upload_tab = (REPO_ROOT / "frontend/src/components/upload/UploadTab.jsx").read_text(
        encoding="utf-8"
    )
    for label in ("OpenAI API Key", "Anthropic API Key", "Gemini API Key"):
        idx = upload_tab.index(label)
        # The element opening tag sits just above the label prop.
        window = upload_tab[max(0, idx - 120) : idx]
        assert "<PasswordInput" in window, f"{label} is not rendered with <PasswordInput>"


def test_log_formatter_includes_non_sensitive_context_fields():
    msg = lc._format_message("event", {"session_id": "abc", "count": 2})
    assert "session_id=abc" in msg
    assert "count=2" in msg


def test_log_formatter_should_redact_sensitive_keys():
    msg = lc._format_message(
        "event",
        {
            "openai_api_key": "sk-secret-value",
            "gemini_api_key": "AIza-secret-value",
            "token": "secret-token",
        },
    )

    assert "sk-secret-value" not in msg
    assert "AIza-secret-value" not in msg
    assert "secret-token" not in msg


