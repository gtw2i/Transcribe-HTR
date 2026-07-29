# providers/anthropic_provider.py
"""
Anthropic provider: all Claude API logic for transcription, harmonization,
NER (grounded research + structured extraction), and model list fetching.
"""

import base64
import mimetypes
import re

from config import (
    MAX_COMPLETION_TOKENS_ANTHROPIC,
    MAX_COMPLETION_TOKENS_HARMONIZATION_ANTHROPIC,
)
from core.retry_utils import classify_error, with_retry
from logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def get_anthropic_client(api_key: str):
    """Create and return an Anthropic client configured with the given key."""
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Model list fetching
# ---------------------------------------------------------------------------

_ANTHROPIC_EXCLUDE_SUBSTRINGS = ["instant"]
_LEGACY_CLAUDE_RE = re.compile(r"^claude-[12](\.\d+)?(-|$)")


def _is_transcription_model(name: str) -> bool:
    """Keep only versioned claude-N... models suitable for vision/transcription."""
    if not name.startswith("claude-"):
        return False
    if _LEGACY_CLAUDE_RE.match(name):
        return False
    lower = name.lower()
    return not any(pat in lower for pat in _ANTHROPIC_EXCLUDE_SUBSTRINGS)


def fetch_anthropic_model_list(api_key: str) -> list:
    """
    Fetch the list of Claude models that support vision/transcription.
    Returns [] on failure so callers can fall back to cached/hardcoded lists.
    """
    try:
        client = get_anthropic_client(api_key)
        response = with_retry(client.models.list, limit=1000)
        models = sorted(
            (m.id for m in response.data if _is_transcription_model(m.id)),
            reverse=True,  # show newer versions first
        )
        logger.info(f"Fetched {len(models)} Anthropic models from API")
        return models
    except Exception as e:
        logger.warning(f"Failed to fetch Anthropic model list: {e}")
        return []


# ---------------------------------------------------------------------------
# Transcription (vision)
# ---------------------------------------------------------------------------

def _encode_image_b64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def query_model_anthropic(
    client,          # anthropic.Anthropic returned by get_anthropic_client()
    image_path: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    n_responses: int,
    temperature: float,
    retry_kwargs: dict | None = None,
) -> dict:
    """
    Run Anthropic vision transcription via n_responses sequential
    client.messages.create() calls.

    When n_responses > 1, marks ephemeral cache breakpoints on the system
    prompt and the user message's text block so the repeated image + prompt
    are served from Anthropic's prompt cache on calls after the first.

    Returns the same dict shape as query_model_gemini/query_model_openai:
        success, text, outputs, prompt_tokens, completion_tokens,
        thinking_tokens, total_tokens, prompt_tokens_details
    """
    try:
        image_b64 = _encode_image_b64(image_path)
        mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"

        text_block = {"type": "text", "text": user_prompt}
        if n_responses > 1:
            text_block["cache_control"] = {"type": "ephemeral"}

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
                    text_block,
                ],
            }
        ]

        if n_responses > 1:
            system = [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]
        else:
            system = system_prompt

        outputs = []
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_cache_read = 0
        total_cache_creation = 0

        for _ in range(n_responses):
            response = with_retry(
                client.messages.create,
                model=model,
                system=system,
                messages=messages,
                temperature=temperature,
                max_tokens=MAX_COMPLETION_TOKENS_ANTHROPIC,
                **(retry_kwargs or {}),
            )
            text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
            outputs.append("".join(text_parts).strip())

            usage = response.usage
            total_prompt_tokens += int(getattr(usage, "input_tokens", 0) or 0)
            total_completion_tokens += int(getattr(usage, "output_tokens", 0) or 0)
            total_cache_read += int(getattr(usage, "cache_read_input_tokens", 0) or 0)
            total_cache_creation += int(getattr(usage, "cache_creation_input_tokens", 0) or 0)

        logger.info(
            f"Anthropic call: model={model}, n_responses={n_responses}, "
            f"outputs_returned={len(outputs)}"
        )

        prompt_tokens_details = None
        if total_cache_read or total_cache_creation:
            prompt_tokens_details = {
                "cached_tokens": total_cache_read,
                "cache_creation_tokens": total_cache_creation,
            }

        return {
            "success": True,
            "text": outputs[0] if outputs else "",
            "outputs": outputs,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "thinking_tokens": 0,
            "total_tokens": total_prompt_tokens + total_completion_tokens,
            "prompt_tokens_details": prompt_tokens_details,
        }

    except Exception as e:
        logger.error(f"Anthropic transcription failed: {e}")
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

def query_text_anthropic(
    client,          # anthropic.Anthropic returned by get_anthropic_client()
    model: str,
    system_prompt: str,
    user_prompt: str,
    retry_kwargs: dict | None = None,
) -> dict:
    """
    Run a text-only Anthropic call for harmonization/summarization.

    Returns: success, text, prompt_tokens, completion_tokens, thinking_tokens,
    prompt_tokens_details (optional, present only when caching was used).
    """
    try:
        response = with_retry(
            client.messages.create,
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=MAX_COMPLETION_TOKENS_HARMONIZATION_ANTHROPIC,
            **(retry_kwargs or {}),
        )
        text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
        text = "".join(text_parts).strip()
        text = re.sub(r"^```[^\n]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

        usage = response.usage
        prompt_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        cache_read = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        cache_creation = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)

        logger.info(
            f"Anthropic text call: model={model}, output_len={len(text)}, "
            f"tokens={prompt_tokens}+{completion_tokens}"
        )

        result = {
            "success": True,
            "text": text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "thinking_tokens": 0,
        }
        if cache_read or cache_creation:
            result["prompt_tokens_details"] = {
                "cached_tokens": cache_read,
                "cache_creation_tokens": cache_creation,
            }
        return result

    except Exception as e:
        logger.error(f"Anthropic text call failed: {e}")
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
# NER Pass 1 — grounded research via Anthropic web search
# ---------------------------------------------------------------------------

def run_pass1_anthropic(
    client,
    prompt: str,
    model: str,
    min_search_queries: int,
    max_output_tokens: int,
    system_prompt: str,
    retry_kwargs: dict | None = None,
) -> tuple[str, dict, dict]:
    """
    Pass 1: grounded research via Anthropic's server-side web_search tool.

    Returns (raw_text, grounding_info, token_counts) — same shape as the
    Gemini/OpenAI pass1 helpers.
    """
    tools = [{
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": max(min_search_queries * 2, 5),
    }]

    response = with_retry(
        client.messages.create,
        model=model,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
        tools=tools,
        temperature=0.2,
        max_tokens=max_output_tokens,
        **(retry_kwargs or {}),
    )

    raw_text_parts: list[str] = []
    queries: list[str] = []
    sources: list[dict] = []

    for block in response.content:
        btype = getattr(block, "type", None)
        if btype == "text":
            raw_text_parts.append(block.text)
        elif btype == "server_tool_use" and getattr(block, "name", None) == "web_search":
            query = (block.input or {}).get("query")
            if query:
                queries.append(str(query))
        elif btype == "web_search_tool_result":
            items = getattr(block, "content", None) or []
            for i, item in enumerate(items):
                sources.append({
                    "chunk_index": i,
                    "uri": getattr(item, "url", None),
                    "title": getattr(item, "title", None),
                })

    raw_text = "".join(raw_text_parts).strip()
    grounding_info = {"web_search_queries": queries, "sources": sources}

    usage = response.usage
    inp = int(getattr(usage, "input_tokens", 0) or 0)
    out = int(getattr(usage, "output_tokens", 0) or 0)
    token_counts = {"input_tokens": inp, "output_tokens": out, "thinking_tokens": 0, "total_tokens": inp + out}

    return raw_text, grounding_info, token_counts


# ---------------------------------------------------------------------------
# NER Pass 2 — strict entity-bundle extraction via forced tool use
# ---------------------------------------------------------------------------

def run_pass2_anthropic(
    client,
    prompt: str,
    model: str,
    max_output_tokens: int,
    input_schema: dict,
    system_prompt: str,
    retry_kwargs: dict | None = None,
) -> tuple[dict, dict]:
    """
    Pass 2: strict normalization into `input_schema` via a forced Anthropic
    tool call (`tool_choice={"type": "tool", "name": "submit_entities"}`).

    Returns (entity_bundle, token_counts).
    """
    tools = [{
        "name": "submit_entities",
        "description": "Submit the extracted and normalized entity bundle.",
        "input_schema": input_schema,
    }]

    response = with_retry(
        client.messages.create,
        model=model,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
        tools=tools,
        tool_choice={"type": "tool", "name": "submit_entities"},
        temperature=0.0,
        max_tokens=max_output_tokens,
        **(retry_kwargs or {}),
    )

    entity_bundle: dict = {"entities": []}
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "submit_entities":
            entity_bundle = block.input
            break

    usage = response.usage
    inp = int(getattr(usage, "input_tokens", 0) or 0)
    out = int(getattr(usage, "output_tokens", 0) or 0)
    token_counts = {"input_tokens": inp, "output_tokens": out, "thinking_tokens": 0, "total_tokens": inp + out}

    return entity_bundle, token_counts
