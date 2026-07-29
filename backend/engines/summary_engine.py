# engines/summary_engine.py
"""Document summarization engine — provider-following with cross-provider fallback."""

import re
from typing import Any

from config import (
    PROVIDER_ANTHROPIC,
    PROVIDER_GEMINI,
    PROVIDER_MODEL_DEFAULTS,
    PROVIDER_OPENAI,
    estimate_cost_usd,
)
from core.retry_utils import classify_error, with_retry
from fallback import build_model_chain, retry_kwargs_for, run_with_fallback_chain
from providers import query_text_anthropic
from resource_loaders import get_anthropic_client, get_client


_SYSTEM_PROMPT = (
    "You are an expert historical document analyst specializing in "
    "handwritten correspondence, military records, and 19th-century primary sources."
)

_SUMMARY_PROMPT_TEMPLATE = """\
DOCUMENT SUMMARIZATION

You are analyzing MULTIPLE transcription candidates of the same historical handwritten document.
Each candidate may differ due to handwriting ambiguity, abbreviations, and spelling variations.

============================================================
TASK
============================================================

Produce a concise 2–4 sentence summary describing:
1. What type of document this appears to be (letter, order, report, etc.) and its general purpose.
2. The key people, places, dates, and military units mentioned.
3. Any named entities that are uncertain or vary across the transcription candidates — explicitly
   note this uncertainty (e.g., "a person whose name is unclear, possibly 'Terman' or 'Herman'").

Be specific about content but brief overall. Do not pad with generic statements.
Output only the summary text — no headers, no JSON, no markdown.

============================================================
TRANSCRIPTION CANDIDATES
============================================================

{transcriptions_block}
""".strip()

_SUMMARY_MAX_TOKENS = 1024


def _extract_token_counts(response) -> dict:
    meta = getattr(response, "usage_metadata", None)
    if not meta:
        return {"prompt_tokens": 0, "completion_tokens": 0, "thinking_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0}
    inp   = getattr(meta, "prompt_token_count",     0) or 0
    out   = getattr(meta, "candidates_token_count", 0) or 0
    think = getattr(meta, "thoughts_token_count",   0) or 0
    return {
        "prompt_tokens": inp,
        "completion_tokens": out,
        "thinking_tokens": think,
        "total_tokens": inp + out + think,
        "estimated_cost_usd": 0,
    }


def _build_prompt(transcriptions: list[str]) -> str:
    joined = "\n\n".join(
        f"--- Transcription candidate #{i + 1} ---\n{t}"
        for i, t in enumerate(transcriptions)
    )
    return _SUMMARY_PROMPT_TEMPLATE.format(transcriptions_block=joined)


def _summarize_gemini(api_key: str, transcriptions: list[str], model: str, retry_kwargs: dict) -> dict:
    """Summarize via Gemini. Returns success dict (summary/tokens_used/temperature)
    or {"success": False, "error", "error_category"} — never raises."""
    from google import genai
    from google.genai.types import GenerateContentConfig

    try:
        client = genai.Client(api_key=api_key)
        prompt = _build_prompt(transcriptions)

        config = GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            temperature=0.2,
            max_output_tokens=_SUMMARY_MAX_TOKENS,
        )
        response = with_retry(
            client.models.generate_content,
            model=model,
            contents=prompt,
            config=config,
            **retry_kwargs,
        )

        summary = getattr(response, "text", None) or ""
        # Strip any accidental markdown fences
        summary = re.sub(r"^```[^\n]*\n?", "", summary.strip())
        summary = re.sub(r"\n?```$", "", summary).strip()

        return {
            "success": True,
            "summary": summary,
            "tokens_used": _extract_token_counts(response),
            "temperature": 0.2,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "error_category": classify_error(exc).value}


def _summarize_openai(api_key: str, transcriptions: list[str], model: str, retry_kwargs: dict) -> dict:
    """Summarize via OpenAI. Returns success dict (summary/tokens_used/temperature)
    or {"success": False, "error", "error_category"} — never raises."""
    try:
        client = get_client(api_key)
        prompt = _build_prompt(transcriptions)

        api_params = {
            "model": model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
        if model.startswith("gpt-5"):
            api_params["max_completion_tokens"] = _SUMMARY_MAX_TOKENS
        else:
            api_params["max_tokens"] = _SUMMARY_MAX_TOKENS

        response = with_retry(client.chat.completions.create, **api_params, **retry_kwargs)

        summary = response.choices[0].message.content or ""
        summary = re.sub(r"^```[^\n]*\n?", "", summary.strip())
        summary = re.sub(r"\n?```$", "", summary).strip()

        usage = response.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)

        return {
            "success": True,
            "summary": summary,
            "tokens_used": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "thinking_tokens": 0,
                "total_tokens": int(getattr(usage, "total_tokens", 0) or 0),
                "estimated_cost_usd": estimate_cost_usd(prompt_tokens, completion_tokens, model),
            },
            # gpt-5* models only support the default temperature (1.0)
            "temperature": 1.0,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "error_category": classify_error(exc).value}


def _summarize_anthropic(api_key: str, transcriptions: list[str], model: str, retry_kwargs: dict) -> dict:
    """Summarize via Anthropic. Returns success dict (summary/tokens_used/temperature)
    or {"success": False, "error", "error_category"} — never raises."""
    try:
        client = get_anthropic_client(api_key)
        prompt = _build_prompt(transcriptions)

        result = query_text_anthropic(client, model, _SYSTEM_PROMPT, prompt, retry_kwargs=retry_kwargs)
        if not result["success"]:
            return result

        pt = result.get("prompt_tokens", 0)
        ct = result.get("completion_tokens", 0)
        tt = result.get("thinking_tokens", 0)

        return {
            "success": True,
            "summary": result["text"] or "",
            "tokens_used": {
                "prompt_tokens": pt,
                "completion_tokens": ct,
                "thinking_tokens": tt,
                "total_tokens": pt + ct + tt,
                "estimated_cost_usd": estimate_cost_usd(pt, ct, model),
            },
            "temperature": 1.0,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc), "error_category": classify_error(exc).value}


_SUMMARIZERS = {
    PROVIDER_GEMINI: _summarize_gemini,
    PROVIDER_OPENAI: _summarize_openai,
    PROVIDER_ANTHROPIC: _summarize_anthropic,
}


def summarize_document(
    transcriptions: list[str],
    provider: str,
    model: str,
    gemini_api_key: str = "",
    openai_api_key: str = "",
    anthropic_api_key: str = "",
) -> dict[str, Any]:
    """
    Summarize a document from multiple transcription variants.

    Tries the requested provider/model first (plus its fallback models), then
    falls back to the other providers (if their API keys are present) as a
    last resort.

    Returns:
        {"success": True, "summary": str, "tokens_used": dict, "model": str,
         "provider": str, "temperature": float, "system_prompt": str,
         "task_prompt": str, "fallback_used": bool, "fallback_info": dict | None}
        {"success": False, "error": str}
    """
    if not transcriptions:
        return {"success": False, "error": "No transcriptions provided."}

    keys = {
        PROVIDER_GEMINI: gemini_api_key,
        PROVIDER_OPENAI: openai_api_key,
        PROVIDER_ANTHROPIC: anthropic_api_key,
    }

    if not keys.get(provider):
        return {"success": False, "error": f"{provider} API key is required for summarization."}

    candidates = [(provider, m) for m in build_model_chain(provider, model)]
    for other_provider, other_key in keys.items():
        if other_provider == provider or not other_key:
            continue
        candidates += [
            (other_provider, m)
            for m in build_model_chain(other_provider, PROVIDER_MODEL_DEFAULTS[other_provider])
        ]

    def call_fn(cand_provider, candidate_model, is_last):
        rk = retry_kwargs_for(is_last)
        return _SUMMARIZERS[cand_provider](keys[cand_provider], transcriptions, candidate_model, rk)

    result = run_with_fallback_chain(candidates, call_fn)

    if not result["success"]:
        return {"success": False, "error": result["error"]}

    fallback_used = result.get("fallback_used", False)
    fallback_info = result.get("fallback_info")
    if fallback_used and fallback_info:
        used_provider = fallback_info["used_provider"]
        used_model = fallback_info["used_model"]
    else:
        used_provider, used_model = candidates[0]

    return {
        "success": True,
        "summary": result["summary"],
        "tokens_used": result["tokens_used"],
        "model": used_model,
        "provider": used_provider,
        "temperature": result["temperature"],
        "system_prompt": _SYSTEM_PROMPT,
        "task_prompt": _SUMMARY_PROMPT_TEMPLATE,
        "fallback_used": fallback_used,
        "fallback_info": fallback_info,
    }
