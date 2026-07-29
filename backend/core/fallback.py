# core/fallback.py
"""Generic model/provider fallback orchestration for LLM calls.

Given an ordered list of (provider, model) candidates, calls a provided
function for each candidate until one succeeds. A failure advances to the
next candidate UNLESS it's an auth error, in which case remaining candidates
for that same provider are skipped (same API key would fail identically) —
but candidates for a different provider (e.g. Summary's Gemini -> OpenAI
chain) are still tried.
"""

from typing import Callable, Optional

from config import (
    FALLBACK_RETRY_KWARGS,
    MAX_FALLBACK_ATTEMPTS,
    MODEL_FALLBACK_ENABLED,
    PROVIDER_MODEL_LISTS_FALLBACK,
)
from core.retry_utils import ErrorCategory
from logging_config import log_info, log_warning


def build_model_chain(provider: str, requested_model: str) -> list[str]:
    """Ordered list of models to try for `provider`: `requested_model`
    first, then the provider's fallback list (deduped), capped at
    MAX_FALLBACK_ATTEMPTS. Returns [requested_model] only if
    MODEL_FALLBACK_ENABLED is False."""
    if not MODEL_FALLBACK_ENABLED:
        return [requested_model]
    chain = [requested_model]
    for candidate in PROVIDER_MODEL_LISTS_FALLBACK.get(provider, []):
        if candidate not in chain:
            chain.append(candidate)
    return chain[:MAX_FALLBACK_ATTEMPTS]


def retry_kwargs_for(is_last: bool) -> dict:
    """Retry budget for a fallback candidate: a short budget for non-final
    candidates (fail fast and move on), the full with_retry() defaults for
    the final candidate (nothing left to fall back to)."""
    return {} if is_last else FALLBACK_RETRY_KWARGS


def run_with_fallback_chain(
    candidates: list[tuple[str, str]],
    call_fn: Callable[[str, str, bool], dict],
) -> dict:
    """
    Try call_fn(provider, model, is_last) for each (provider, model) pair in
    `candidates`, in order. call_fn must return a dict with "success": bool
    and, on failure, "error": str and "error_category": str (an
    ErrorCategory value).

    - On success: if this wasn't the first candidate, annotate the result
      with fallback_used=True and fallback_info (requested vs. used
      provider/model plus the list of failed attempts); otherwise
      fallback_used=False. All other keys in the result pass through
      unchanged.
    - On failure with error_category == "auth": no further candidates for
      THIS provider are tried, but candidates for a different provider
      continue.
    - is_last is True only for the final candidate in the whole chain (gets
      the full retry budget — see retry_kwargs_for).
    - If every candidate fails: {"success": False, "error": <aggregated
      message>, "fallback_used": False, "fallback_info": {"attempts": [...]}}.
    """
    attempts: list[dict] = []
    exhausted_providers: set[str] = set()
    requested_provider, requested_model = candidates[0]

    for i, (provider, model) in enumerate(candidates):
        if provider in exhausted_providers:
            continue

        is_last = i == len(candidates) - 1
        result = call_fn(provider, model, is_last)

        if result.get("success"):
            if i == 0:
                result["fallback_used"] = False
            else:
                result["fallback_used"] = True
                result["fallback_info"] = {
                    "requested_provider": requested_provider,
                    "requested_model": requested_model,
                    "used_provider": provider,
                    "used_model": model,
                    "attempts": attempts,
                }
                log_info(
                    f"Model fallback succeeded: {requested_provider}/{requested_model} "
                    f"-> {provider}/{model}"
                )
            return result

        category = result.get("error_category", ErrorCategory.UNKNOWN.value)
        error_msg = result.get("error", "")
        attempts.append({"provider": provider, "model": model, "error": error_msg, "error_category": category})
        log_warning(f"Model candidate {provider}/{model} failed ({category}): {error_msg}")

        if category == ErrorCategory.AUTH.value:
            exhausted_providers.add(provider)

    return {
        "success": False,
        "error": "; ".join(f"{a['provider']}/{a['model']}: {a['error']}" for a in attempts),
        "fallback_used": False,
        "fallback_info": {
            "requested_provider": requested_provider,
            "requested_model": requested_model,
            "attempts": attempts,
        },
    }


def run_with_fallback(
    models: list[str],
    call_fn: Callable[[str, bool], dict],
    provider: Optional[str] = None,
) -> dict:
    """Single-provider convenience wrapper around run_with_fallback_chain:
    pairs each model in `models` with `provider` and adapts call_fn's
    signature from (model, is_last) to (provider, model, is_last)."""
    candidates = [(provider, m) for m in models]
    return run_with_fallback_chain(candidates, lambda p, m, is_last: call_fn(m, is_last))
