# engines/transcription_engine.py
"""Transcription engine — no Streamlit."""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import PROVIDER_ANTHROPIC, PROVIDER_GEMINI, TEMPERATURE, estimate_cost_usd
from fallback import build_model_chain, retry_kwargs_for, run_with_fallback
from json_manager import save_transcription_run
from logging_config import audit_logger, get_logger, log_error, log_info, log_warning
from providers import query_model_anthropic, query_model_gemini, query_model_openai
from resource_loaders import get_anthropic_client, get_client, get_gemini_client, get_helpers

logger = get_logger(__name__)


class TranscriptionEngine:
    """Handles transcription logic, API calls, and result processing."""

    def __init__(self):
        self.client = None
        self.helpers = None

    def ensure_resources(
        self,
        api_key: str = None,
        provider: str = "OpenAI",
        gemini_api_key: str = None,
        anthropic_api_key: str = None,
        profile_name: str = None,
    ) -> bool:
        """Ensure the appropriate AI client and helpers are loaded."""
        try:
            if provider == PROVIDER_GEMINI:
                self.client = get_gemini_client(gemini_api_key)
            elif provider == PROVIDER_ANTHROPIC:
                self.client = get_anthropic_client(anthropic_api_key)
            else:
                self.client = get_client(api_key)
            self.helpers = get_helpers(profile_name)
            return self.client is not None and self.helpers is not None
        except Exception as e:
            log_error("Failed to load transcription resources", error=str(e))
            raise RuntimeError(f"Failed to load resources: {e}") from e

    def validate_settings(
        self,
        api_key: str,
        img_bytes: Optional[bytes],
        provider: str = "OpenAI",
        gemini_api_key: str = None,
        anthropic_api_key: str = None,
        profile_name: str = None,
    ) -> Tuple[bool, str]:
        """Return (is_valid, error_message)."""
        if not img_bytes:
            return False, "No image loaded. Please upload an image first."

        if provider == PROVIDER_GEMINI:
            active_key = gemini_api_key or ""
        elif provider == PROVIDER_ANTHROPIC:
            active_key = anthropic_api_key or ""
        else:
            active_key = api_key or ""
        if not active_key.strip():
            return False, f"{provider} API key is required."

        try:
            self.ensure_resources(api_key, provider, gemini_api_key, anthropic_api_key, profile_name)
        except RuntimeError as e:
            return False, str(e)

        return True, ""

    def run_transcription(
        self,
        api_key: str,
        img_bytes: bytes,
        model: str,
        n_responses: int,
        prompt: str,
        source_choice: str,
        active_root: Optional[str] = None,
        provider: str = "OpenAI",
        gemini_api_key: str = None,
        anthropic_api_key: str = None,
        profile_name: str = "",
        workspace=None,
        file_index=None,
    ) -> Dict[str, Any]:
        """
        Run transcription and return results dict:
          success, outputs (list[dict with text/tokens/timing]), tokens_usage, timing_data
        """
        started_at = datetime.now()
        log_info("Starting transcription", model=model, n_responses=n_responses, source_choice=source_choice)
        audit_logger.log_transcription_start(model, n_responses, "")

        try:
            is_valid, error_msg = self.validate_settings(api_key, img_bytes, provider, gemini_api_key, anthropic_api_key, profile_name)
            if not is_valid:
                log_warning("Transcription validation failed", error=error_msg)
                return {"success": False, "error": error_msg}

            if provider == "OpenAI":
                self.client.api_key = api_key

            outputs = []
            total_prompt_tokens = 0
            total_completion_tokens = 0
            total_thinking_tokens = 0
            per_call_tokens = []
            per_call_timings = []
            total_duration_ms = 0
            result = {}
            used_model = model
            fallback_used = False
            fallback_info = None

            if source_choice == "Use hardcoded outputs":
                hardcoded_texts = [
                    "This is a hardcoded transcription output #1.",
                    "This is a hardcoded transcription output #2.",
                    "This is a hardcoded transcription output #3.",
                ][:n_responses]
                for i, text in enumerate(hardcoded_texts):
                    sp, sc = 100, len(text.split()) * 2
                    outputs.append({"text": text, "prompt_tokens": sp, "completion_tokens": sc, "call_sequence": i + 1})
                    total_prompt_tokens += sp
                    total_completion_tokens += sc
                    per_call_tokens.append({"prompt_tokens": sp, "completion_tokens": sc})
                    per_call_timings.append({"call_started_at": started_at.isoformat() + "Z", "call_completed_at": started_at.isoformat() + "Z", "call_duration_ms": 1000})
                total_duration_ms = n_responses * 1000

            else:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(img_bytes)
                    tmp_image_path = tmp.name

                try:
                    _template = self.helpers.TRANSCRIBE_PROMPT_TEMPLATE
                    if "{}" in _template:
                        formatted_user_prompt = _template.format(prompt)
                    elif prompt:
                        formatted_user_prompt = _template + "\n\n" + prompt
                    else:
                        formatted_user_prompt = _template

                    call_started_at = datetime.now()

                    models = build_model_chain(provider, model)

                    def call_fn(candidate_model, is_last):
                        rk = retry_kwargs_for(is_last)
                        if provider == PROVIDER_GEMINI:
                            return query_model_gemini(
                                self.client, tmp_image_path, candidate_model,
                                self.helpers.SYSTEM_PROMPT, formatted_user_prompt,
                                n_responses, TEMPERATURE,
                                retry_kwargs=rk,
                            )
                        elif provider == PROVIDER_ANTHROPIC:
                            return query_model_anthropic(
                                self.client, tmp_image_path, candidate_model,
                                self.helpers.SYSTEM_PROMPT, formatted_user_prompt,
                                n_responses, TEMPERATURE,
                                retry_kwargs=rk,
                            )
                        return query_model_openai(
                            self.client, tmp_image_path, candidate_model,
                            self.helpers.SYSTEM_PROMPT, formatted_user_prompt,
                            n_responses, TEMPERATURE,
                            retry_kwargs=rk,
                        )

                    result = run_with_fallback(models, call_fn, provider=provider)

                    call_completed_at = datetime.now()
                    call_duration_ms = int((call_completed_at - call_started_at).total_seconds() * 1000)
                    total_duration_ms = call_duration_ms

                    if result["success"]:
                        fallback_used = result.get("fallback_used", False)
                        fallback_info = result.get("fallback_info")
                        if fallback_used and fallback_info:
                            used_model = fallback_info.get("used_model", model)

                        api_outputs = result.get("outputs") or [result["text"]]

                        total_api_prompt_tokens = result.get("prompt_tokens", 0)
                        total_api_completion_tokens = result.get("completion_tokens", 0)
                        total_api_thinking_tokens = result.get("thinking_tokens", 0)
                        n_out = len(api_outputs) or 1
                        avg_pt = total_api_prompt_tokens // n_out
                        avg_ct = total_api_completion_tokens // n_out

                        for i, output_text in enumerate(api_outputs):
                            if not output_text or not output_text.strip():
                                log_warning(f"API returned empty output {i} - marking as empty response")
                                output_text = "[EMPTY RESPONSE - API returned no content for this transcription]"
                            outputs.append({"text": output_text, "prompt_tokens": avg_pt, "completion_tokens": avg_ct, "call_sequence": i + 1})
                            per_call_tokens.append({"prompt_tokens": avg_pt, "completion_tokens": avg_ct})
                            per_call_timings.append({"call_started_at": call_started_at.isoformat() + "Z", "call_completed_at": call_completed_at.isoformat() + "Z", "call_duration_ms": call_duration_ms})

                        total_prompt_tokens = total_api_prompt_tokens
                        total_completion_tokens = total_api_completion_tokens
                        total_thinking_tokens = total_api_thinking_tokens
                        log_info(f"API call successful — {len(api_outputs)} responses", prompt_tokens=total_api_prompt_tokens, completion_tokens=total_api_completion_tokens)
                    else:
                        error_msg = f"API call failed: {result.get('error', 'Unknown error')}"
                        log_error(error_msg)
                        audit_logger.log_error_event("api_call_failed", error_msg, "", model=model)
                        return {"success": False, "error": error_msg}

                except Exception as api_error:
                    error_msg = f"API call failed: {str(api_error)}"
                    log_error(error_msg)
                    audit_logger.log_error_event("api_exception", str(api_error), "", model=model)
                    return {"success": False, "error": error_msg}
                finally:
                    try:
                        os.unlink(tmp_image_path)
                    except Exception:
                        pass

            # Save results if workspace is provided
            if active_root and outputs and workspace and file_index:
                try:
                    completed_at = datetime.now()
                    text_outputs = [o["text"] for o in outputs]
                    self._save_transcription_results(
                        workspace=workspace,
                        file_index=file_index,
                        active_root=active_root,
                        outputs=text_outputs,
                        model=used_model,
                        prompt=prompt,
                        total_prompt_tokens=total_prompt_tokens,
                        total_completion_tokens=total_completion_tokens,
                        started_at=started_at,
                        completed_at=completed_at,
                        per_call_tokens=per_call_tokens,
                        per_call_timings=per_call_timings,
                        provider=provider,
                        profile_name=profile_name,
                        thinking_tokens=total_thinking_tokens,
                    )
                except Exception as save_error:
                    log_warning("Transcription succeeded but saving failed", error=str(save_error))

            log_info("Transcription completed successfully", output_count=len(outputs), total_tokens=total_prompt_tokens + total_completion_tokens)
            audit_logger.log_transcription_complete(model, total_prompt_tokens + total_completion_tokens, True, "")

            tokens_usage = {
                "prompt_tokens": total_prompt_tokens,
                "completion_tokens": total_completion_tokens,
                "thinking_tokens": total_thinking_tokens,
                "total_tokens": total_prompt_tokens + total_completion_tokens + total_thinking_tokens,
                "model": used_model,
                "provider": provider,
                "estimated_cost_usd": estimate_cost_usd(total_prompt_tokens, total_completion_tokens, used_model),
            }
            if source_choice == "Call API" and result.get("prompt_tokens_details"):
                tokens_usage["prompt_tokens_details"] = result["prompt_tokens_details"]

            return {
                "success": True,
                "outputs": outputs,
                "tokens_usage": tokens_usage,
                "request_id": result.get("id") if source_choice == "Call API" else None,
                "timing_data": {"per_call_timings": per_call_timings, "total_duration_ms": total_duration_ms},
                "fallback_used": fallback_used,
                "fallback_info": fallback_info,
            }

        except Exception as e:
            error_msg = f"Transcription failed: {str(e)}"
            log_error(error_msg)
            audit_logger.log_transcription_complete(model, 0, False, "")
            audit_logger.log_error_event("transcription_exception", str(e), "", model=model)
            return {"success": False, "error": error_msg}

    def _save_transcription_results(
        self,
        workspace,
        file_index,
        active_root: str,
        outputs: List[str],
        model: str,
        prompt: str,
        total_prompt_tokens: int,
        total_completion_tokens: int,
        started_at: datetime,
        completed_at: datetime,
        per_call_tokens: List[dict] = None,
        per_call_timings: List[dict] = None,
        provider: str = "",
        profile_name: str = "",
        thinking_tokens: int = 0,
    ):
        """Save transcription results to JSON file via json_manager."""
        system_prompt = self.helpers.SYSTEM_PROMPT if self.helpers else ""
        estimated_cost = estimate_cost_usd(total_prompt_tokens, total_completion_tokens, model)

        ok = save_transcription_run(
            workspace=workspace,
            file_index=file_index,
            root=active_root,
            model=model,
            temperature=TEMPERATURE,
            base_prompt=system_prompt,
            domain_prompt=prompt,
            tokens_in=total_prompt_tokens,
            tokens_out=total_completion_tokens,
            token_method="api_response",
            transcription_outputs=outputs,
            provider=provider,
            profile_name=profile_name,
            estimated_cost_usd=estimated_cost,
            started_at=started_at,
            completed_at=completed_at,
            thinking_tokens=thinking_tokens,
        )
        if not ok:
            raise Exception(f"save_transcription_run returned False for root={active_root}")
