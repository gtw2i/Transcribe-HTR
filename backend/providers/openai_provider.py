# providers/openai_provider.py
"""
OpenAI provider: model list fetching, transcription, harmonization/
summarization text calls, and NER (grounded research + structured
extraction) for OpenAI models.
"""

import base64
import json
import mimetypes
import re

from config import (
    MAX_COMPLETION_TOKENS,
    MAX_COMPLETION_TOKENS_HARMONIZATION,
    MAX_TOKENS_LEGACY,
    MAX_TOKENS_LEGACY_HARMONIZATION,
    TEMPERATURE,
)
from core.retry_utils import ErrorCategory, classify_error, with_retry
from logging_config import get_logger

logger = get_logger(__name__)

_OPENAI_EXCLUDE_SUBSTRINGS = [
    "tts", "transcribe", "realtime", "audio", "search", "codex", "chat-latest", "image",
]
_DATED_SNAPSHOT_RE = re.compile(r"-\d{4}-\d{2}-\d{2}$")

# Models that only support temperature=1.0
_TEMPERATURE_RESTRICTED_MODELS = {"gpt-4o", "gpt-4o-mini", "gpt-4-vision-preview", "gpt-5"}


def _is_transcription_model(name: str) -> bool:
    """Keep only base GPT chat/vision models; exclude specialized and dated-snapshot variants."""
    if not name.startswith("gpt-"):
        return False
    lower = name.lower()
    if any(pat in lower for pat in _OPENAI_EXCLUDE_SUBSTRINGS):
        return False
    if _DATED_SNAPSHOT_RE.search(name):
        return False
    return True


def fetch_openai_model_list(api_key: str) -> list:
    """
    Fetch the list of OpenAI vision-capable models.
    Returns [] on failure so callers can fall back to cached/hardcoded lists.
    """
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = with_retry(client.models.list)
        models = sorted(
            (m.id for m in response.data if _is_transcription_model(m.id)),
            reverse=True,
        )
        logger.info(f"Fetched {len(models)} OpenAI models from API")
        return models
    except Exception as e:
        logger.warning(f"Failed to fetch OpenAI model list: {e}")
        return []


# ---------------------------------------------------------------------------
# Transcription (vision)
# ---------------------------------------------------------------------------

def _encode_image_b64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def query_model_openai(
    client,
    image_path,
    model,
    system_prompt,
    user_prompt,
    n_responses,
    temperature,
    retry_kwargs: dict | None = None,
) -> dict:
    """
    Run OpenAI vision transcription, requesting n_responses choices in a
    single client.chat.completions.create() call (OpenAI caches the shared
    image/prompt prefix automatically across choices and repeated calls).

    Returns the same dict shape as query_model_gemini/query_model_anthropic:
        success, text, outputs, prompt_tokens, completion_tokens,
        thinking_tokens, total_tokens, prompt_tokens_details
    """
    messages = [{"role": "system", "content": system_prompt}]
    user_content = [{"type": "text", "text": user_prompt}]
    if image_path is not None:
        base64_image = _encode_image_b64(image_path)
        mime_type, _ = mimetypes.guess_type(image_path)
        if mime_type not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            mime_type = "image/jpeg"
        user_content.append(
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}
        )
    messages.append({"role": "user", "content": user_content})

    api_temperature = 1.0 if model in _TEMPERATURE_RESTRICTED_MODELS else temperature

    try:
        api_params = {
            "model": model,
            "n": n_responses,
            "temperature": api_temperature,
            "messages": messages,
        }
        if model.startswith("gpt-5"):
            api_params["max_completion_tokens"] = MAX_COMPLETION_TOKENS
        else:
            api_params["max_tokens"] = MAX_TOKENS_LEGACY

        response = with_retry(client.chat.completions.create, **api_params, **(retry_kwargs or {}))

        for i, choice in enumerate(response.choices):
            if getattr(choice.message, "refusal", None):
                raise RuntimeError(f"Model refused to respond: {choice.message.refusal}")
            if choice.message.content is None:
                raise RuntimeError(f"API returned None content for choice {i}")

        outputs = [re.sub(r"`", "", choice.message.content).strip() for choice in response.choices]

        usage = response.usage
        prompt_tokens_details = None
        if hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
            prompt_tokens_details = {
                "cached_tokens": getattr(usage.prompt_tokens_details, "cached_tokens", 0)
            }

        return {
            "success": True,
            "text": outputs[0] if outputs else "",
            "outputs": outputs,
            "prompt_tokens": int(usage.prompt_tokens or 0),
            "completion_tokens": int(usage.completion_tokens or 0),
            "thinking_tokens": 0,
            "total_tokens": int(usage.total_tokens or 0),
            "prompt_tokens_details": prompt_tokens_details,
        }

    except Exception as e:
        logger.error(f"OpenAI transcription failed: {e}")
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
# Harmonization / summarization (text-only)
# ---------------------------------------------------------------------------

def query_text_openai(
    client,
    model: str,
    system_prompt: str,
    user_prompt: str,
    retry_kwargs: dict | None = None,
) -> dict:
    """
    Run a text-only OpenAI chat completion for harmonization/summarization.

    Returns: success, text, prompt_tokens, completion_tokens, thinking_tokens,
    prompt_tokens_details (optional, present only when caching was used).
    """
    api_params = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": TEMPERATURE,
    }
    if model.startswith("gpt-5"):
        api_params["max_completion_tokens"] = MAX_COMPLETION_TOKENS_HARMONIZATION
    else:
        api_params["max_tokens"] = MAX_TOKENS_LEGACY_HARMONIZATION

    try:
        response = with_retry(client.chat.completions.create, **api_params, **(retry_kwargs or {}))
        message = response.choices[0].message

        if message.content is None:
            if getattr(message, "refusal", None):
                return {
                    "success": False,
                    "error": f"Model refused to respond: {message.refusal}",
                    "error_category": ErrorCategory.INVALID_REQUEST.value,
                }
            return {
                "success": False,
                "error": "API returned None content without refusal: model or quota issue",
                "error_category": ErrorCategory.INVALID_REQUEST.value,
            }

        usage = response.usage
        result = {
            "success": True,
            "text": message.content,
            "prompt_tokens": int(usage.prompt_tokens or 0),
            "completion_tokens": int(usage.completion_tokens or 0),
            "thinking_tokens": 0,
        }
        if hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
            result["prompt_tokens_details"] = {
                "cached_tokens": getattr(usage.prompt_tokens_details, "cached_tokens", 0)
            }
        return result

    except Exception as e:
        logger.error(f"OpenAI text call failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "error_category": classify_error(e).value,
            "text": "",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "thinking_tokens": 0,
        }


# ---------------------------------------------------------------------------
# NER Pass 1 — grounded research via the OpenAI Responses API web_search tool
# ---------------------------------------------------------------------------

def run_pass1_openai(
    client,
    prompt: str,
    model: str,
    min_search_queries: int,
    max_output_tokens: int,
    system_prompt: str,
    retry_kwargs: dict | None = None,
) -> tuple[str, dict, dict]:
    """
    Pass 1: grounded research via the OpenAI Responses API's built-in
    web_search tool.

    Returns (raw_text, grounding_info, token_counts) — same shape as the
    Gemini/Anthropic pass1 helpers.
    """
    response = with_retry(
        client.responses.create,
        model=model,
        instructions=system_prompt,
        input=prompt,
        tools=[{"type": "web_search"}],
        max_output_tokens=max_output_tokens,
        **(retry_kwargs or {}),
    )

    raw_text = response.output_text or ""

    queries: list[str] = []
    sources: list[dict] = []

    for item in response.output:
        item_type = getattr(item, "type", None)
        if item_type == "web_search_call":
            action = getattr(item, "action", None)
            query = getattr(action, "query", None) if action else None
            if query:
                queries.append(str(query))
        elif item_type == "message":
            for content in getattr(item, "content", None) or []:
                for annotation in getattr(content, "annotations", None) or []:
                    if getattr(annotation, "type", None) == "url_citation":
                        sources.append({
                            "uri": getattr(annotation, "url", None),
                            "title": getattr(annotation, "title", None),
                        })

    grounding_info = {"web_search_queries": queries, "sources": sources}

    usage = response.usage
    inp = int(getattr(usage, "input_tokens", 0) or 0)
    out = int(getattr(usage, "output_tokens", 0) or 0)
    token_counts = {"input_tokens": inp, "output_tokens": out, "thinking_tokens": 0, "total_tokens": inp + out}

    return raw_text, grounding_info, token_counts


# ---------------------------------------------------------------------------
# NER Pass 2 — strict entity-bundle extraction via Structured Outputs
# ---------------------------------------------------------------------------

def run_pass2_openai(
    client,
    prompt: str,
    model: str,
    max_output_tokens: int,
    json_schema: dict,
    system_prompt: str,
    retry_kwargs: dict | None = None,
) -> tuple[dict, dict]:
    """
    Pass 2: strict entity-bundle extraction via OpenAI Structured Outputs.

    `json_schema` must already be in OpenAI strict-mode shape (see
    core.schema_utils.to_openai_strict_schema).

    Returns (entity_bundle, token_counts).
    """
    api_params = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": 1.0 if model in _TEMPERATURE_RESTRICTED_MODELS else 0.0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "entity_bundle", "schema": json_schema, "strict": True},
        },
    }
    if model.startswith("gpt-5"):
        api_params["max_completion_tokens"] = max_output_tokens
    else:
        api_params["max_tokens"] = max_output_tokens

    response = with_retry(client.chat.completions.create, **api_params, **(retry_kwargs or {}))

    entity_bundle = json.loads(response.choices[0].message.content)

    usage = response.usage
    inp = int(usage.prompt_tokens or 0)
    out = int(usage.completion_tokens or 0)
    token_counts = {"input_tokens": inp, "output_tokens": out, "thinking_tokens": 0, "total_tokens": inp + out}

    return entity_bundle, token_counts
