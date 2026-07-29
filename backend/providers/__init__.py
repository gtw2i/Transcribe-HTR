# providers/__init__.py
"""
Public API for the providers package.

Each provider module (gemini_provider, openai_provider, anthropic_provider)
owns its model-list fetching, transcription, harmonization/summarization
text calls, and NER pass1/pass2 functions. This package re-exports them and
provides the cross-provider fetch_model_list/filter_model_list helpers.
"""

from config import PROVIDER_ANTHROPIC, PROVIDER_GEMINI

from providers.anthropic_provider import (
    fetch_anthropic_model_list,
    get_anthropic_client,
    query_model_anthropic,
    query_text_anthropic,
    run_pass1_anthropic,
    run_pass2_anthropic,
)
from providers.gemini_provider import (
    fetch_gemini_model_list,
    get_gemini_client,
    query_model_gemini,
    query_text_gemini,
)
from providers.openai_provider import (
    fetch_openai_model_list,
    query_model_openai,
    query_text_openai,
    run_pass1_openai,
    run_pass2_openai,
)


def fetch_model_list(provider: str, api_key: str) -> list:
    """
    Fetch the live model list for the given provider.
    Returns [] on failure — callers should fall back to registry/hardcoded lists.
    """
    if provider == PROVIDER_GEMINI:
        return fetch_gemini_model_list(api_key)
    elif provider == PROVIDER_ANTHROPIC:
        return fetch_anthropic_model_list(api_key)
    else:
        return fetch_openai_model_list(api_key)


def filter_model_list(provider: str, models: list) -> list:
    """
    Apply provider-specific filter and alphabetical sort to a cached model list.
    Used when loading from the registry so stale unfiltered data gets cleaned up.
    """
    if provider == PROVIDER_GEMINI:
        from providers.gemini_provider import _is_transcription_model
        return sorted(
            (m for m in models if _is_transcription_model(m)),
            reverse=True,
        )
    elif provider == PROVIDER_ANTHROPIC:
        from providers.anthropic_provider import _is_transcription_model
        return sorted(
            (m for m in models if _is_transcription_model(m)),
            reverse=True,
        )
    else:
        from providers.openai_provider import _is_transcription_model
        return sorted(
            (m for m in models if _is_transcription_model(m)),
            reverse=True,
        )


__all__ = [
    "fetch_model_list",
    "filter_model_list",
    "fetch_gemini_model_list",
    "fetch_openai_model_list",
    "fetch_anthropic_model_list",
    "get_gemini_client",
    "get_anthropic_client",
    "query_model_gemini",
    "query_model_openai",
    "query_model_anthropic",
    "query_text_gemini",
    "query_text_openai",
    "query_text_anthropic",
    "run_pass1_openai",
    "run_pass2_openai",
    "run_pass1_anthropic",
    "run_pass2_anthropic",
]
