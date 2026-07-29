# providers/gemini_provider.py
"""
Gemini provider: all Google Gemini API logic for transcription, harmonization,
and model list fetching.
"""

import mimetypes
import re
from typing import Any

from core.retry_utils import classify_error, with_retry
from logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def get_gemini_client(api_key: str):
    """
    Create and return a google.genai Client configured with the given key.
    """
    from google import genai
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Model list fetching
# ---------------------------------------------------------------------------

_GEMINI_EXCLUDE_SUBSTRINGS = [
    "tts", "computer-use", "robotics", "deep-research",
    "lyria", "-image", "tools", "lite"
]


def _is_transcription_model(name: str) -> bool:
    """Keep only versioned gemini-N... models suitable for vision/transcription."""
    if not re.match(r"^gemini-\d", name):
        return False
    lower = name.lower()
    return not any(pat in lower for pat in _GEMINI_EXCLUDE_SUBSTRINGS)


def fetch_gemini_model_list(api_key: str) -> list:
    """
    Fetch the list of Gemini models that support content generation.
    Strips the 'models/' prefix and filters to vision/transcription-capable models only.
    Returns [] on failure so callers can fall back to cached/hardcoded lists.
    """
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        models = []
        for m in with_retry(client.models.list):
            if "generateContent" in (getattr(m, "supported_actions", []) or []):
                name = m.name
                if name.startswith("models/"):
                    name = name[len("models/"):]
                if _is_transcription_model(name):
                    models.append(name)
        models = sorted(models, reverse=True)  # show newer versions first
        logger.info(f"Fetched {len(models)} Gemini models from API")
        return models
    except Exception as e:
        logger.warning(f"Failed to fetch Gemini model list: {e}")
        return []


# ---------------------------------------------------------------------------
# Transcription (vision)
# ---------------------------------------------------------------------------

def candidate_to_text(candidate: Any) -> str:
    parts = getattr(getattr(candidate, "content", None), "parts", None) or []
    raw = getattr(parts[0], "text", None)
    raw = re.sub(r"^```[^\n]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return raw.strip()


def _supports_candidate_count(model: str) -> bool:
    """Returns False for Gemini 3+ models, which require separate API calls."""
    m = re.search(r"gemini-(\d+)", model)
    if m and int(m.group(1)) >= 3:
        return False
    return True


def query_model_gemini(
    client,          # google.genai.Client returned by get_gemini_client()
    image_path: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    n_responses: int,
    temperature: float,
    retry_kwargs: dict | None = None,
) -> dict:
    """
    Run Gemini vision transcription, returning n_responses outputs.

    For Gemini 1.x/2.x: single API call using candidate_count=n_responses.
    For Gemini 3+: n_responses sequential API calls (candidate_count unsupported).

    Returns the same dict shape as openai_provider.query_model_openai():
        success, text, outputs, prompt_tokens, completion_tokens, total_tokens
    """
    try:
        from google.genai import types

        with open(image_path, "rb") as f:
            image_bytes = f.read()
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"

        contents = [
            user_prompt,
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ]

        if _supports_candidate_count(model):
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                candidate_count=n_responses,
            )
            response = with_retry(client.models.generate_content,
                model=model,
                contents=contents,
                config=config,
                **(retry_kwargs or {}),
            )
            candidates = getattr(response, "candidates", None) or []
            outputs = [candidate_to_text(c) for c in candidates]
            usage = getattr(response, "usage_metadata", None)
            total_prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
            total_completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
            total_thinking_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0) if usage else 0
        else:
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
            )
            outputs = []
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_thinking_tokens = 0
            for _ in range(n_responses):
                response = with_retry(client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=config,
                    **(retry_kwargs or {}),
                )
                candidates = getattr(response, "candidates", None) or []
                if candidates:
                    outputs.append(candidate_to_text(candidates[0]))
                usage = getattr(response, "usage_metadata", None)
                if usage:
                    total_prompt_tokens += int(getattr(usage, "prompt_token_count", 0) or 0)
                    total_completion_tokens += int(getattr(usage, "candidates_token_count", 0) or 0)
                    total_thinking_tokens += int(getattr(usage, "thoughts_token_count", 0) or 0)

        logger.info(
            f"Gemini call: model={model}, n_responses={n_responses}, "
            f"candidates_returned={len(outputs)}"
        )

        return {
            "success": True,
            "text": outputs[0] if outputs else "",
            "outputs": outputs,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "thinking_tokens": total_thinking_tokens,
            "total_tokens": total_prompt_tokens + total_completion_tokens + total_thinking_tokens,
            "prompt_tokens_details": None,
        }

    except Exception as e:
        logger.error(f"Gemini transcription failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_category": classify_error(e).value,
            "text": "",
            "outputs": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }


# ---------------------------------------------------------------------------
# Harmonization (text-only)
# ---------------------------------------------------------------------------

def query_text_gemini(
    client,          # google.genai.Client returned by get_gemini_client()
    model: str,
    system_prompt: str,
    user_prompt: str,
    retry_kwargs: dict | None = None,
) -> dict:
    """
    Run a text-only Gemini call for harmonization.

    Returns: success, text, prompt_tokens, completion_tokens
    """
    try:
        from google.genai import types

        config = types.GenerateContentConfig(system_instruction=system_prompt)
        response = with_retry(client.models.generate_content,
            model=model,
            contents=user_prompt,
            config=config,
            **(retry_kwargs or {}),
        )
        text = response.text or ""
        text = re.sub(r"^```[^\n]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
        text = text.strip()

        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = 0
        completion_tokens = 0
        thinking_tokens = 0
        if usage:
            prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
            completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
            thinking_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0)

        logger.info(
            f"Gemini harmonization: model={model}, output_len={len(text)}, "
            f"tokens={prompt_tokens}+{completion_tokens}"
        )

        return {
            "success": True,
            "text": text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "thinking_tokens": thinking_tokens,
        }

    except Exception as e:
        logger.error(f"Gemini harmonization failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_category": classify_error(e).value,
            "text": "",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "thinking_tokens": 0,
        }
