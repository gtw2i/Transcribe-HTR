# engines/harmonization_engine.py
"""Harmonization engine — no Streamlit."""

import logging
from typing import Any, Dict, List, Optional

from config import (
    PROVIDER_ANTHROPIC,
    PROVIDER_GEMINI,
    PROVIDER_MODEL_DEFAULTS,
    PROVIDER_OPENAI,
    TEMPERATURE,
    estimate_cost_usd,
)
from fallback import build_model_chain, retry_kwargs_for, run_with_fallback
from json_manager import save_harmonization
from logging_config import audit_logger, log_error, log_info, log_warning
from providers import query_text_anthropic, query_text_gemini, query_text_openai
from resource_loaders import get_anthropic_client, get_client, get_gemini_client, get_helpers

logger = logging.getLogger(__name__)


class HarmonizationEngine:
    """Manages harmonization of multiple transcriptions."""

    def __init__(self, profile_name: str = None):
        self.helpers = get_helpers(profile_name)

    def harmonize_transcriptions(
        self,
        transcriptions: List[Dict[str, Any]],
        api_key: str,
        model: str = PROVIDER_MODEL_DEFAULTS[PROVIDER_OPENAI],
        provider: str = "OpenAI",
        gemini_api_key: str = None,
        anthropic_api_key: str = None,
        active_root: Optional[str] = None,
        workspace=None,
        file_index=None,
        ner_entity_bundle: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Harmonize multiple transcriptions into a single unified version.

        If active_root, workspace, and file_index are provided, the result is
        automatically saved to the workspace JSON.

        Returns dict: harmonized_text, source_count, model_used, temperature,
                      tokens_used, request_id, timing_data
        """
        try:
            from datetime import datetime

            log_info(f"Starting harmonization of {len(transcriptions)} transcriptions")
            audit_logger.log_transcription_start(model, len(transcriptions), "harmonization")

            started_at = datetime.now()

            system_prompt = self.helpers.HARMONIZE_SYSTEM_PROMPT
            task_prompt = self.helpers.HARMONIZE_USER_PROMPT
            user_prompt = self._prepare_harmonization_prompt(transcriptions, ner_entity_bundle)

            if provider == PROVIDER_GEMINI:
                client = get_gemini_client(gemini_api_key)
                query_fn = query_text_gemini
            elif provider == PROVIDER_ANTHROPIC:
                client = get_anthropic_client(anthropic_api_key)
                query_fn = query_text_anthropic
            else:
                client = get_client(api_key)
                query_fn = query_text_openai

            def call_fn(candidate_model, is_last):
                result = query_fn(
                    client, candidate_model, system_prompt, user_prompt,
                    retry_kwargs=retry_kwargs_for(is_last),
                )
                if not result["success"]:
                    return result

                pt = result.get("prompt_tokens", 0)
                ct = result.get("completion_tokens", 0)
                tt = result.get("thinking_tokens", 0)
                out = {
                    "success": True,
                    "harmonized_text": result["text"] or "",
                    "tokens_used": {
                        "prompt_tokens": pt,
                        "completion_tokens": ct,
                        "thinking_tokens": tt,
                        "total_tokens": pt + ct + tt,
                        "estimated_cost_usd": estimate_cost_usd(pt, ct, candidate_model),
                    },
                    "request_id": None,
                }
                if "prompt_tokens_details" in result:
                    out["tokens_used"]["prompt_tokens_details"] = result["prompt_tokens_details"]
                return out

            models = build_model_chain(provider, model)
            call_result = run_with_fallback(models, call_fn, provider=provider)

            if not call_result["success"]:
                raise RuntimeError(call_result["error"])

            completed_at = datetime.now()
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

            fallback_used = call_result.get("fallback_used", False)
            fallback_info = call_result.get("fallback_info")
            model_used = fallback_info["used_model"] if fallback_used and fallback_info else model

            harmonized_text = call_result["harmonized_text"]

            result = {
                "harmonized_text": harmonized_text,
                "source_count": len(transcriptions),
                "model_used": model_used,
                "temperature": TEMPERATURE,
                "tokens_used": call_result["tokens_used"],
                "request_id": call_result.get("request_id"),
                "timing_data": {
                    "started_at": started_at.isoformat() + "Z",
                    "completed_at": completed_at.isoformat() + "Z",
                    "duration_ms": duration_ms,
                },
                "fallback_used": fallback_used,
                "fallback_info": fallback_info,
            }

            log_info(f"Harmonization completed. Tokens: {result['tokens_used']['total_tokens']}")
            audit_logger.log_transcription_complete(model, result["tokens_used"]["total_tokens"], True, "harmonization")

            # Save to workspace JSON if context provided
            if active_root and workspace and file_index:
                try:
                    source_indices = [t.get("index", i) for i, t in enumerate(transcriptions)]
                    ok = save_harmonization(
                        workspace=workspace,
                        file_index=file_index,
                        root=active_root,
                        harmonized_text=harmonized_text,
                        source_indices=source_indices,
                        model_used=model_used,
                        temperature=TEMPERATURE,
                        tokens_used=result["tokens_used"],
                        provider=provider,
                        system_prompt=system_prompt,
                        task_prompt=task_prompt,
                    )
                    if ok:
                        log_info("Harmonization saved to JSON")
                    else:
                        log_warning("Failed to save harmonization to JSON")
                except Exception as save_error:
                    log_warning(f"Auto-save harmonization failed: {save_error}")

            return result

        except Exception as e:
            error_msg = f"Harmonization failed: {str(e)}"
            log_error(error_msg)
            raise RuntimeError(error_msg) from e

    def _prepare_harmonization_prompt(
        self,
        transcriptions: List[Dict[str, Any]],
        ner_entity_bundle: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Combine all transcription texts (and optional NER data) into the harmonization user prompt."""
        import json

        parts = []
        for i, transcription in enumerate(transcriptions, 1):
            text = transcription.get("text", "")
            if isinstance(text, list):
                text = "\n".join(text)
            parts.append(f"\n--- TRANSCRIPTION {i} ---")
            parts.append(text)
            parts.append(f"--- END TRANSCRIPTION {i} ---\n")

        if ner_entity_bundle:
            parts.append("\n--- NAMED ENTITIES (from NER analysis) ---")
            parts.append(json.dumps(ner_entity_bundle, indent=2))
            parts.append("--- END NAMED ENTITIES ---\n")

        transcriptions_block = "\n".join(parts)
        return self.helpers.HARMONIZE_USER_PROMPT.format(transcriptions_block)

    def validate_transcriptions(self, transcriptions: List[Dict[str, Any]]) -> bool:
        """Return True if transcriptions list is suitable for harmonization."""
        if not transcriptions:
            log_warning("No transcriptions provided for harmonization")
            return False
        if len(transcriptions) < 2:
            log_warning("At least 2 transcriptions required for harmonization")
            return False
        for i, transcription in enumerate(transcriptions):
            text = transcription.get("text", "")
            if not text or (isinstance(text, list) and not any(text)):
                log_warning(f"Transcription {i+1} has no text content")
                return False
        return True

    def estimate_tokens(self, transcriptions: List[Dict[str, Any]]) -> int:
        """Rough token estimate (4 chars per token) for a harmonization call."""
        total_chars = len(self.helpers.HARMONIZE_SYSTEM_PROMPT) + len(self.helpers.HARMONIZE_USER_PROMPT)
        for t in transcriptions:
            text = t.get("text", "")
            if isinstance(text, list):
                text = "\n".join(text)
            total_chars += len(text) + 50
        return total_chars // 4
