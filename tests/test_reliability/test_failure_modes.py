import os
import types

import numpy as np
import pytest

import transcription_engine as te
import transcription_utils as tu
from providers import query_model_openai


class _Raises:
    def create(self, **kwargs):
        raise RuntimeError("simulated provider outage")


class _FakeClient:
    def __init__(self):
        self.chat = types.SimpleNamespace(completions=_Raises())


def test_query_model_returns_structured_failure_on_provider_exception(tmp_path):
    image_path = tmp_path / "image.png"
    image_path.write_bytes(b"not-a-real-image-but-base64-safe")

    result = query_model_openai(
        client=_FakeClient(),
        image_path=str(image_path),
        model="gpt-4o",
        system_prompt="sys",
        user_prompt="user",
        n_responses=1,
        temperature=1.0,
    )

    assert result["success"] is False
    assert "simulated provider outage" in result["error"]
    assert result["outputs"] == []
    assert result["prompt_tokens"] == 0
    assert result["completion_tokens"] == 0


def test_compute_token_disagreement_handles_none_input():
    result = tu.compute_token_disagreement(None, level="word")
    assert result == []


def test_compute_token_disagreement_invalid_level_falls_back_safely():
    result = tu.compute_token_disagreement(["abc"], level="invalid")
    assert len(result) == 1
    assert isinstance(result[0], np.ndarray)
    assert len(result[0]) == 3


def test_compute_token_disagreement_alignment_errors_do_not_crash(monkeypatch):
    def _always_fail(*args, **kwargs):
        raise RuntimeError("alignment failure")

    monkeypatch.setattr(tu, "get_alignments_with_agreement", _always_fail)

    result = tu.compute_token_disagreement(["one two", "one too"], level="word")

    assert len(result) == 2
    assert all(isinstance(v, np.ndarray) for v in result)
    assert all(len(v) == 2 for v in result)


@pytest.fixture
def engine_with_silenced_logging(monkeypatch):
    """The backend engine is pure — only its logging needs silencing."""
    engine = te.TranscriptionEngine()

    monkeypatch.setattr(te, "log_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(te, "log_error", lambda *args, **kwargs: None)
    monkeypatch.setattr(te, "log_warning", lambda *args, **kwargs: None)

    return engine


def test_validate_settings_rejects_missing_image(engine_with_silenced_logging):
    ok, msg = engine_with_silenced_logging.validate_settings(
        api_key="test-key",
        img_bytes=None,
        provider="OpenAI",
    )

    assert ok is False
    assert "No image loaded" in msg


def test_validate_settings_rejects_missing_provider_key(engine_with_silenced_logging):
    ok, msg = engine_with_silenced_logging.validate_settings(
        api_key="openai-key-present",
        img_bytes=b"img-bytes",
        provider="Gemini",
        gemini_api_key="",
    )

    assert ok is False
    assert "Gemini API key is required" in msg


def test_ensure_resources_raises_wrapped_error_when_loader_fails(
    engine_with_silenced_logging, monkeypatch
):
    """The backend engine surfaces loader failures to the caller (the router)
    as a wrapped RuntimeError rather than swallowing them into a False return,
    so the API can report a real status code."""

    def _boom(*args, **kwargs):
        raise RuntimeError("loader failed")

    monkeypatch.setattr(te, "get_client", _boom)

    with pytest.raises(RuntimeError, match="Failed to load resources"):
        engine_with_silenced_logging.ensure_resources(api_key="x", provider="OpenAI")


def test_run_transcription_returns_validation_error_without_image(
    engine_with_silenced_logging,
):
    result = engine_with_silenced_logging.run_transcription(
        api_key="test-key",
        img_bytes=b"",
        model="gpt-4o",
        n_responses=1,
        prompt="",
        source_choice="Call API",
        provider="OpenAI",
    )

    assert result["success"] is False
    assert "No image loaded" in result["error"]


def test_run_transcription_cleans_temp_file_on_query_exception(
    engine_with_silenced_logging, monkeypatch
):
    # Skip full resource init; drive directly into the API call path.
    monkeypatch.setattr(
        engine_with_silenced_logging,
        "validate_settings",
        lambda *args, **kwargs: (True, ""),
    )

    engine_with_silenced_logging.client = types.SimpleNamespace(api_key="")
    engine_with_silenced_logging.helpers = types.SimpleNamespace(
        TRANSCRIBE_PROMPT_TEMPLATE="{}",
        SYSTEM_PROMPT="sys",
    )

    def _raise_query(*args, **kwargs):
        raise RuntimeError("query blew up")

    monkeypatch.setattr(te, "query_model_openai", _raise_query)

    unlinked_paths = []
    original_unlink = os.unlink

    def _tracking_unlink(path):
        unlinked_paths.append(path)
        if os.path.exists(path):
            original_unlink(path)

    monkeypatch.setattr(os, "unlink", _tracking_unlink)

    result = engine_with_silenced_logging.run_transcription(
        api_key="test-key",
        img_bytes=b"image-bytes",
        model="gpt-4o",
        n_responses=1,
        prompt="domain hint",
        source_choice="Call API",
        provider="OpenAI",
    )

    assert result["success"] is False
    assert "API call failed" in result["error"]
    # The temp image must be unlinked in the finally block even though the
    # provider call raised.
    assert len(unlinked_paths) == 1
