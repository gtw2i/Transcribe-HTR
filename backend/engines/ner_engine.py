# engines/ner_engine.py
"""NER engine with web-search grounding, supporting Gemini, OpenAI, and Anthropic.
Attempts single-pass JSON output; falls back to a second schema-normalization
pass if the first pass returns invalid JSON."""

import copy
import json
import pathlib
import re
from typing import Any, Optional

from config import PROVIDER_ANTHROPIC, PROVIDER_GEMINI
from core.retry_utils import classify_error, with_retry
from core.schema_utils import to_anthropic_tool_schema, to_openai_strict_schema
from fallback import build_model_chain, retry_kwargs_for, run_with_fallback
from providers import run_pass1_anthropic, run_pass1_openai, run_pass2_anthropic, run_pass2_openai
from resource_loaders import get_anthropic_client, get_client

# Schema lives at <project_root>/entity-data/entity_schema_v2.json
# Path: backend/engines/ -> backend/ -> project_root/
_SCHEMA_PATH = pathlib.Path(__file__).parent.parent.parent / "entity-data" / "entity_schema_v2.json"
_ENTITY_SCHEMA: dict = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def _build_schema(entity_types: list[str] | None) -> dict:
    """Return a copy of the entity schema with a custom entity-type enum, or the original if None."""
    if not entity_types:
        return _ENTITY_SCHEMA
    schema = copy.deepcopy(_ENTITY_SCHEMA)
    schema["properties"]["entities"]["items"]["properties"]["type"]["enum"] = entity_types
    return schema

# ---------------------------------------------------------------------------
# Prompts — verbatim from NER_Gemini_Combined_04.ipynb cell c08-prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_PASS1 = (
    "You are an expert Civil War historical research assistant specializing in "
    "military correspondence, ranks, units, and 19th-century administrative structures."
)

_COMBINED_PROMPT_TEMPLATE = r'''
CIVIL WAR DOCUMENT ENTITY EXTRACTION

You are assisting with Civil War document interpretation and entity normalization.

You will be given MULTIPLE transcription candidates of the same document, each with
variations due to handwriting ambiguity, OCR-like errors, abbreviations, and misspellings.

============================================================
GOALS
============================================================

1) Identify ALL named entities across transcription variants.
2) Merge misspellings, abbreviations, and partial forms into unified records.
3) Normalize each entity to an accurate canonical form when possible.
4) Conduct web-grounded research to verify identity and relevance, especially for obscure entities.

Be over-inclusive rather than minimal. Preserve competing hypotheses when necessary.
Do not suppress entities simply because resolution is incomplete.

============================================================
RESEARCH RULES
============================================================

- Prefer official, scholarly, archival, or academic sources.
- Do NOT fabricate biographical details.
- Explicitly state when something is uncertain.
- If evidence is weak or conflicting, say so clearly.
- Distinguish between inference and confirmed fact.

============================================================
OUTPUT FORMAT — REQUIRED
============================================================

- Output ONLY a valid JSON object. No markdown, no code fences, no commentary before or after.
- The JSON must conform exactly to the schema below.
- All required fields must be present for every entity.
- Use "Unresolved: <best guess>" for `canonical` when identity is uncertain; set `confidence` to "low".
- Complete ALL web research BEFORE writing the JSON — run at least {min_search_queries} distinct searches first.

SCHEMA:
{ENTITY_SCHEMA}

============================================================
TRANSCRIPTIONS
============================================================

{transcriptions_block}
'''.strip()

_SYSTEM_PROMPT_PASS2 = (
    "You are an expert Civil War historical research assistant. You are performing strict "
    "normalization and consolidation into an enforced JSON schema."
)

_PASS2_PROMPT_TEMPLATE = r'''
CIVIL WAR ENTITY NORMALIZATION — PASS 2 (STRICT JSON OUTPUT)

You are performing PASS 2 of a two-pass pipeline.

PASS 1 took several variant transcriptions of the same historical document and produced an over-inclusive, semi-structured research bundle with:
- candidate entities
- variants
- background notes
- uncertainty notes
- open questions
- search notes

Your job in PASS 2 is to convert that Pass 1 content into a STRICT JSON object that conforms EXACTLY
to the provided JSON schema.

============================================================
PASS 2 RESPONSIBILITIES
============================================================

1) Parse Pass 1 content and extract all entity records described there.
2) Deduplicate / merge entities that are clearly the same (typos, abbreviations, alternate spellings).
3) Preserve ambiguity: if Pass 1 did not resolve an entity confidently, keep it unresolved.
4) Ensure every entity includes ALL required fields from the schema.
5) Keep "observed_variants" comprehensive (include all spellings/abbrevs mentioned in Pass 1).
6) Output ONLY the JSON object. No commentary, no markdown.

============================================================
PASS 1 RESPONSE
============================================================

{raw_text_pass1}
'''.strip()

_SEARCH_NUDGE_TEMPLATE = (
    "IMPORTANT: Use the web search tool. Run at least {min_search_queries} "
    "distinct web searches to verify/identify ambiguous names, units, offices, "
    "and places before writing your response.\n\n"
)


# ---------------------------------------------------------------------------
# Shared prompt builder
# ---------------------------------------------------------------------------

def _build_pass1_prompt(transcriptions: list[str], min_search_queries: int, entity_types: list[str] | None) -> str:
    joined = "\n\n".join(
        f"--- Transcription candidate #{i + 1} ---\n{t}"
        for i, t in enumerate(transcriptions)
    )
    entity_schema_str = json.dumps(_build_schema(entity_types), ensure_ascii=False, indent=2)
    prompt = _COMBINED_PROMPT_TEMPLATE.format(
        ENTITY_SCHEMA=entity_schema_str,
        transcriptions_block=joined,
        min_search_queries=min_search_queries,
    )
    nudge = _SEARCH_NUDGE_TEMPLATE.format(min_search_queries=min_search_queries)
    return nudge + prompt


# ---------------------------------------------------------------------------
# Gemini response parsing helpers
# ---------------------------------------------------------------------------

def _try_parse_json(text: str) -> dict | None:
    """Strip markdown code fences and attempt JSON parse. Returns None on failure."""
    stripped = re.sub(r"^```(?:json)?\s*", "", text.strip())
    stripped = re.sub(r"\s*```$", "", stripped).strip()
    try:
        return json.loads(stripped)
    except Exception:
        return None


def _extract_token_counts(response) -> dict:
    meta = getattr(response, "usage_metadata", None)
    if not meta:
        return {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "total_tokens": 0}
    inp   = getattr(meta, "prompt_token_count",     0) or 0
    out   = getattr(meta, "candidates_token_count", 0) or 0
    think = getattr(meta, "thoughts_token_count",   0) or 0
    return {"input_tokens": inp, "output_tokens": out, "thinking_tokens": think, "total_tokens": inp + out + think}


def _extract_text(response) -> str:
    text = getattr(response, "text", None) or ""
    if not text:
        try:
            parts = response.candidates[0].content.parts or []
            text = "".join((getattr(p, "text", None) or "") for p in parts)
        except Exception:
            pass
    return text


def _extract_grounding(response) -> dict:
    queries: list[str] = []
    sources: list[dict] = []
    try:
        gm = getattr(response.candidates[0], "grounding_metadata", None)
        if gm is None:
            return {"web_search_queries": queries, "sources": sources}
        raw_q = getattr(gm, "web_search_queries", None) or []
        queries = [str(q) for q in raw_q if str(q).strip()]
        chunks = getattr(gm, "grounding_chunks", None) or []
        for i, ch in enumerate(chunks):
            web = getattr(ch, "web", None)
            uri = title = None
            if web:
                uri = getattr(web, "uri", None)
                title = getattr(web, "title", None)
            sources.append({"chunk_index": i, "uri": uri, "title": title})
    except Exception:
        pass
    return {"web_search_queries": queries, "sources": sources}


# ---------------------------------------------------------------------------
# Pass 1 — grounded research
# ---------------------------------------------------------------------------

def _run_pass1_gemini(
    client,
    transcriptions: list[str],
    model: str,
    min_search_queries: int,
    max_output_tokens: int,
    entity_types: list[str] | None = None,
    retry_kwargs: dict | None = None,
) -> tuple[str, dict, dict]:
    from google.genai import types
    from google.genai.types import GenerateContentConfig

    prompt = _build_pass1_prompt(transcriptions, min_search_queries, entity_types)

    config = GenerateContentConfig(
        system_instruction=_SYSTEM_PROMPT_PASS1,
        temperature=0.2,
        tools=[types.Tool(google_search=types.GoogleSearch())],
        candidate_count=1,
        max_output_tokens=max_output_tokens,
    )
    response = with_retry(client.models.generate_content, model=model, contents=prompt, config=config, **(retry_kwargs or {}))
    return _extract_text(response), _extract_grounding(response), _extract_token_counts(response)


def _run_pass1_openai(
    client,
    transcriptions: list[str],
    model: str,
    min_search_queries: int,
    max_output_tokens: int,
    entity_types: list[str] | None = None,
    retry_kwargs: dict | None = None,
) -> tuple[str, dict, dict]:
    prompt = _build_pass1_prompt(transcriptions, min_search_queries, entity_types)
    return run_pass1_openai(
        client, prompt, model, min_search_queries, max_output_tokens,
        system_prompt=_SYSTEM_PROMPT_PASS1, retry_kwargs=retry_kwargs,
    )


def _run_pass1_anthropic(
    client,
    transcriptions: list[str],
    model: str,
    min_search_queries: int,
    max_output_tokens: int,
    entity_types: list[str] | None = None,
    retry_kwargs: dict | None = None,
) -> tuple[str, dict, dict]:
    prompt = _build_pass1_prompt(transcriptions, min_search_queries, entity_types)
    return run_pass1_anthropic(
        client, prompt, model, min_search_queries, max_output_tokens,
        system_prompt=_SYSTEM_PROMPT_PASS1, retry_kwargs=retry_kwargs,
    )


# ---------------------------------------------------------------------------
# Pass 2 — strict JSON normalization
# ---------------------------------------------------------------------------

def _run_pass2_gemini(
    client,
    raw_text_pass1: str,
    model: str,
    max_output_tokens: int,
    entity_types: list[str] | None = None,
    retry_kwargs: dict | None = None,
) -> tuple[dict, dict]:
    from google.genai.types import GenerateContentConfig

    prompt = _PASS2_PROMPT_TEMPLATE.format(raw_text_pass1=raw_text_pass1)
    config = GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_build_schema(entity_types),
        temperature=0.0,
        max_output_tokens=max_output_tokens,
    )
    response = with_retry(client.models.generate_content,
        model=model,
        contents=[_SYSTEM_PROMPT_PASS2, prompt],
        config=config,
        **(retry_kwargs or {}),
    )
    try:
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            entity_bundle = parsed
        else:
            entity_bundle = json.loads(response.text)
    except Exception:
        raw = getattr(response, "text", "")
        entity_bundle = {"error": "Could not parse JSON", "raw_output": raw, "entities": []}

    for i, entity in enumerate(entity_bundle.get("entities", [])):
        entity["entity_id"] = f"E{i:02d}"

    return entity_bundle, _extract_token_counts(response)


def _run_pass2_openai(
    client,
    raw_text_pass1: str,
    model: str,
    max_output_tokens: int,
    entity_types: list[str] | None = None,
    retry_kwargs: dict | None = None,
) -> tuple[dict, dict]:
    prompt = _PASS2_PROMPT_TEMPLATE.format(raw_text_pass1=raw_text_pass1)
    schema = to_openai_strict_schema(_build_schema(entity_types))
    entity_bundle, token_counts = run_pass2_openai(
        client, prompt, model, max_output_tokens, schema,
        system_prompt=_SYSTEM_PROMPT_PASS2, retry_kwargs=retry_kwargs,
    )
    for i, entity in enumerate(entity_bundle.get("entities", [])):
        entity["entity_id"] = f"E{i:02d}"
    return entity_bundle, token_counts


def _run_pass2_anthropic(
    client,
    raw_text_pass1: str,
    model: str,
    max_output_tokens: int,
    entity_types: list[str] | None = None,
    retry_kwargs: dict | None = None,
) -> tuple[dict, dict]:
    prompt = _PASS2_PROMPT_TEMPLATE.format(raw_text_pass1=raw_text_pass1)
    schema = to_anthropic_tool_schema(_build_schema(entity_types))
    entity_bundle, token_counts = run_pass2_anthropic(
        client, prompt, model, max_output_tokens, schema,
        system_prompt=_SYSTEM_PROMPT_PASS2, retry_kwargs=retry_kwargs,
    )
    for i, entity in enumerate(entity_bundle.get("entities", [])):
        entity["entity_id"] = f"E{i:02d}"
    return entity_bundle, token_counts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_ner(
    transcriptions: list[str],
    provider: str,
    api_key: str,
    model: str,
    min_search_queries: int = 5,
    pass1_max_tokens: int = 10000,
    pass2_max_tokens: int = 20000,
    entity_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run two-pass NER (grounded research + structured extraction) on a list of
    transcription strings, using whichever provider (Gemini/OpenAI/Anthropic)
    is selected.

    Attempts single-pass JSON extraction with web grounding. Falls back to a
    second schema-normalization pass if the first pass returns non-JSON output.

    Returns:
        {"success": True, "entity_bundle": dict, "grounding_info": dict, "pass2_used": bool, ...}
        {"success": False, "error": str}
    """
    if not transcriptions:
        return {"success": False, "error": "No transcriptions provided."}
    if not api_key:
        return {"success": False, "error": f"{provider} API key is required for NER."}

    try:
        if provider == PROVIDER_GEMINI:
            from google import genai
            client = genai.Client(api_key=api_key)
            run_pass1_fn, run_pass2_fn = _run_pass1_gemini, _run_pass2_gemini
        elif provider == PROVIDER_ANTHROPIC:
            client = get_anthropic_client(api_key)
            run_pass1_fn, run_pass2_fn = _run_pass1_anthropic, _run_pass2_anthropic
        else:
            client = get_client(api_key)
            run_pass1_fn, run_pass2_fn = _run_pass1_openai, _run_pass2_openai

        def call_fn(candidate_model, is_last):
            rk = retry_kwargs_for(is_last)
            try:
                raw_text_pass1, grounding_info, pass1_tokens = run_pass1_fn(
                    client, transcriptions, candidate_model, min_search_queries, pass1_max_tokens,
                    entity_types=entity_types, retry_kwargs=rk,
                )
                parsed = _try_parse_json(raw_text_pass1)
                if parsed is not None:
                    for i, entity in enumerate(parsed.get("entities", [])):
                        entity["entity_id"] = f"E{i:02d}"
                    zeros = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "total_tokens": 0}
                    return {
                        "success": True,
                        "entity_bundle": parsed,
                        "grounding_info": grounding_info,
                        "tokens_usage": {"pass1": pass1_tokens, "pass2": zeros, "total": pass1_tokens},
                        "pass2_used": False,
                        "model": candidate_model,
                        "provider": provider,
                        "temperature": 0.2,
                        "system_prompt": _SYSTEM_PROMPT_PASS1,
                        "task_prompt": _COMBINED_PROMPT_TEMPLATE,
                    }

                entity_bundle, pass2_tokens = run_pass2_fn(
                    client, raw_text_pass1, candidate_model, pass2_max_tokens,
                    entity_types=entity_types, retry_kwargs=rk,
                )
                tokens_usage = {
                    "pass1": pass1_tokens,
                    "pass2": pass2_tokens,
                    "total": {
                        "input_tokens":    pass1_tokens["input_tokens"]    + pass2_tokens["input_tokens"],
                        "output_tokens":   pass1_tokens["output_tokens"]   + pass2_tokens["output_tokens"],
                        "thinking_tokens": pass1_tokens["thinking_tokens"] + pass2_tokens["thinking_tokens"],
                        "total_tokens":    pass1_tokens["total_tokens"]    + pass2_tokens["total_tokens"],
                    },
                }
                return {
                    "success": True,
                    "entity_bundle": entity_bundle,
                    "grounding_info": grounding_info,
                    "tokens_usage": tokens_usage,
                    "pass2_used": True,
                    "model": candidate_model,
                    "provider": provider,
                    "temperature": 0.2,
                    "system_prompt": _SYSTEM_PROMPT_PASS1,
                    "task_prompt": _COMBINED_PROMPT_TEMPLATE,
                }
            except Exception as exc:
                return {"success": False, "error": str(exc), "error_category": classify_error(exc).value}

        models = build_model_chain(provider, model)
        result = run_with_fallback(models, call_fn, provider=provider)

        if result["success"]:
            return result
        return {"success": False, "error": result["error"]}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
