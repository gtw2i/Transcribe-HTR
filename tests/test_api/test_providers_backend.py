"""
Tests for backend/providers/ model-list filtering.

The module loads backend/providers/__init__.py and its submodules directly from
their file paths under private sys.modules keys, stubbing
backend/core/config.py, backend/core/retry_utils.py, and
backend/core/logging_config.py. The real contents of those three don't affect
the pure filtering functions under test, and isolating them keeps this module
from depending on import order or on the AI SDKs being installed.
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"


def _install_stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


def _load_module(name: str, path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_backend_providers():
    """Load backend/providers/__init__.py and its submodules in isolation,
    restoring any pre-existing sys.modules entries afterwards.

    filter_model_list() does its provider-specific imports lazily (at call
    time), so it's exercised here -- inside the isolated context -- rather
    than returned for later use, where sys.modules would no longer resolve
    providers.* to these backend modules.
    """
    keys = (
        "config", "core", "core.retry_utils", "logging_config",
        "providers", "providers.gemini_provider",
        "providers.anthropic_provider", "providers.openai_provider",
    )
    saved = {k: sys.modules.get(k) for k in keys}
    try:
        for k in keys:
            sys.modules.pop(k, None)

        _install_stub(
            "config",
            PROVIDER_GEMINI="Gemini",
            PROVIDER_ANTHROPIC="Anthropic",
            MAX_COMPLETION_TOKENS=40000,
            MAX_COMPLETION_TOKENS_HARMONIZATION=40000,
            MAX_TOKENS_LEGACY=40000,
            MAX_TOKENS_LEGACY_HARMONIZATION=40000,
            TEMPERATURE=1.0,
            MAX_COMPLETION_TOKENS_ANTHROPIC=8192,
            MAX_COMPLETION_TOKENS_HARMONIZATION_ANTHROPIC=8192,
        )
        retry_utils = _install_stub(
            "core.retry_utils",
            ErrorCategory=type("ErrorCategory", (), {}),
            classify_error=lambda e: None,
            with_retry=lambda fn, *a, **k: fn(*a, **k),
        )
        core_pkg = _install_stub("core")
        core_pkg.retry_utils = retry_utils
        _install_stub("logging_config", get_logger=lambda name=None: __import__("logging").getLogger(name or "test"))

        _load_module("providers.gemini_provider", _BACKEND / "providers" / "gemini_provider.py")
        _load_module("providers.anthropic_provider", _BACKEND / "providers" / "anthropic_provider.py")
        _load_module("providers.openai_provider", _BACKEND / "providers" / "openai_provider.py")
        providers_init = _load_module("providers", _BACKEND / "providers" / "__init__.py")
        openai_provider = sys.modules["providers.openai_provider"]

        filter_model_list = providers_init.filter_model_list
        return {
            "is_transcription_model": openai_provider._is_transcription_model,
            "gemini": filter_model_list("Gemini", [
                "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-tts", "embedding-001",
            ]),
            "anthropic": filter_model_list("Anthropic", [
                "claude-opus-4-5", "claude-sonnet-4-5", "claude-instant-1.2", "claude-2.1",
            ]),
            "openai": filter_model_list("OpenAI", [
                "gpt-4o", "gpt-5", "gpt-4o-mini-tts", "gpt-image-1", "whisper-1",
            ]),
        }
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


_results = _load_backend_providers()
_is_transcription_model = _results["is_transcription_model"]


# ---------------------------------------------------------------------------
# providers/openai_provider.py — _is_transcription_model
# ---------------------------------------------------------------------------


class TestIsTranscriptionModelOpenAI:
    @pytest.mark.parametrize("name", [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-5",
        "gpt-5.1",
        "gpt-4-turbo",
    ])
    def test_keeps_base_chat_vision_models(self, name):
        assert _is_transcription_model(name) is True

    @pytest.mark.parametrize("name", [
        "whisper-1",                 # not gpt-prefixed
        "claude-opus-4-5",           # not gpt-prefixed
        "gpt-4o-mini-tts",           # tts
        "gpt-4o-transcribe",         # transcribe
        "gpt-4o-mini-transcribe",    # transcribe
        "gpt-4o-realtime-preview",   # realtime
        "gpt-4o-audio-preview",      # audio
        "gpt-4o-search-preview",     # search
        "gpt-5-codex",               # codex
        "gpt-4o-chat-latest",        # chat-latest
        "gpt-image-1",               # image
        "gpt-image-1-mini",          # image
        "gpt-4o-2024-08-06",         # dated snapshot
    ])
    def test_excludes_irrelevant_models(self, name):
        assert _is_transcription_model(name) is False


# ---------------------------------------------------------------------------
# providers/__init__.py — filter_model_list
# ---------------------------------------------------------------------------


class TestFilterModelList:
    def test_gemini_keeps_transcription_models_only(self):
        result = _results["gemini"]
        assert "gemini-2.5-pro" in result
        assert "gemini-2.5-flash" in result
        assert "gemini-2.5-flash-tts" not in result
        assert "embedding-001" not in result

    def test_anthropic_keeps_transcription_models_only(self):
        result = _results["anthropic"]
        assert "claude-opus-4-5" in result
        assert "claude-sonnet-4-5" in result
        assert "claude-instant-1.2" not in result
        assert "claude-2.1" not in result

    def test_openai_keeps_transcription_models_only(self):
        result = _results["openai"]
        assert "gpt-4o" in result
        assert "gpt-5" in result
        assert "gpt-4o-mini-tts" not in result
        assert "gpt-image-1" not in result
        assert "whisper-1" not in result
