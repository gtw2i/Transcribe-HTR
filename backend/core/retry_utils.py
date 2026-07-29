# core/retry_utils.py
"""Retry helper for LLM API calls — handles 503/429/etc. overload responses,
and classifies errors for the model-fallback orchestrator (core/fallback.py)."""

import logging
import random
import time
from enum import Enum

logger = logging.getLogger(__name__)

_MAX_DELAY = 60.0


class ErrorCategory(str, Enum):
    """Coarse classification of LLM API errors, used to decide whether to
    retry the same model and/or fall back to a different model/provider."""
    NOT_FOUND = "not_found"
    RATE_LIMITED = "rate_limited"
    OVERLOADED = "overloaded"
    AUTH = "auth"
    INVALID_REQUEST = "invalid_request"
    TRANSIENT = "transient"
    UNKNOWN = "unknown"


def classify_error(exc: Exception) -> ErrorCategory:
    """Classify an exception raised by a Gemini or OpenAI API call."""
    # google-genai SDK (current Gemini path): APIError.code carries the HTTP status
    try:
        from google.genai import errors as genai_errors
        if isinstance(exc, genai_errors.APIError):
            code = exc.code
            if code == 404:
                return ErrorCategory.NOT_FOUND
            if code == 429:
                return ErrorCategory.RATE_LIMITED
            if code == 503:
                return ErrorCategory.OVERLOADED
            if code in (401, 403):
                return ErrorCategory.AUTH
            if code == 400:
                return ErrorCategory.INVALID_REQUEST
            if code and code >= 500:
                return ErrorCategory.OVERLOADED
            if code and code >= 400:
                return ErrorCategory.INVALID_REQUEST
    except ImportError:
        pass

    # google.api_core (legacy Vertex AI SDK exceptions) — kept for back-compat
    try:
        from google.api_core import exceptions as gax
        if isinstance(exc, gax.NotFound):
            return ErrorCategory.NOT_FOUND
        if isinstance(exc, (gax.ResourceExhausted, gax.TooManyRequests)):
            return ErrorCategory.RATE_LIMITED
        if isinstance(exc, gax.ServiceUnavailable):
            return ErrorCategory.OVERLOADED
        if isinstance(exc, (gax.Unauthenticated, gax.PermissionDenied)):
            return ErrorCategory.AUTH
        if isinstance(exc, gax.InvalidArgument):
            return ErrorCategory.INVALID_REQUEST
    except ImportError:
        pass

    # OpenAI SDK
    try:
        import openai
        if isinstance(exc, openai.NotFoundError):
            return ErrorCategory.NOT_FOUND
        if isinstance(exc, openai.RateLimitError):
            return ErrorCategory.RATE_LIMITED
        if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
            return ErrorCategory.AUTH
        if isinstance(exc, openai.BadRequestError):
            return ErrorCategory.INVALID_REQUEST
        if isinstance(exc, openai.InternalServerError):
            return ErrorCategory.OVERLOADED
        if isinstance(exc, openai.APIStatusError):
            status = exc.status_code
            if status == 404:
                return ErrorCategory.NOT_FOUND
            if status == 429:
                return ErrorCategory.RATE_LIMITED
            if status in (401, 403):
                return ErrorCategory.AUTH
            if status == 400:
                return ErrorCategory.INVALID_REQUEST
            if status >= 500:
                return ErrorCategory.OVERLOADED
        if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
            return ErrorCategory.TRANSIENT
    except ImportError:
        pass

    # String-based fallback for anything not caught above
    msg = str(exc).lower()
    if "404" in msg or "not found" in msg:
        return ErrorCategory.NOT_FOUND
    if "429" in msg or "resource_exhausted" in msg or "rate limit" in msg or "quota" in msg:
        return ErrorCategory.RATE_LIMITED
    if "503" in msg or "unavailable" in msg or "overloaded" in msg:
        return ErrorCategory.OVERLOADED
    if "401" in msg or "403" in msg or "permission" in msg or "unauthorized" in msg or "api key" in msg:
        return ErrorCategory.AUTH
    if "400" in msg or "invalid" in msg:
        return ErrorCategory.INVALID_REQUEST
    return ErrorCategory.UNKNOWN


def _is_retryable(exc: Exception) -> bool:
    """Return True if the exception represents a transient condition worth
    retrying the SAME model for (overload, rate limit, network blip)."""
    return classify_error(exc) in (
        ErrorCategory.RATE_LIMITED,
        ErrorCategory.OVERLOADED,
        ErrorCategory.TRANSIENT,
    )


def with_retry(fn, *args, max_retries: int = 10, base_delay: float = 1.0, max_delay: float = _MAX_DELAY, **kwargs):
    """
    Call fn(*args, **kwargs), retrying on retriable errors with exponential backoff.

    Non-retriable exceptions (auth errors, bad requests, etc.) propagate immediately.
    After max_retries exhausted the final exception propagates to the caller.
    """
    for attempt in range(max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            if attempt == max_retries or not _is_retryable(exc):
                raise
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
            logger.warning(
                "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1, max_retries, delay, exc,
            )
            time.sleep(delay)
