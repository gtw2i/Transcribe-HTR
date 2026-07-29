"""JSON operations for managing transcription data. No Streamlit."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from logging_config import audit_logger, log_error, log_info, log_warning
from session_workspace import (
    FileIndex,
    SessionWorkspace,
    append_analysis_to_v2_json,
    append_harmonization_to_v2_json,
    append_ner_result_to_v2_json,
    append_run_to_v2_json,
    append_summary_to_v2_json,
    create_analysis_record,
    create_harmonization_record,
    create_ner_record,
    create_summary_record,
    create_v2_json_schema,
    get_canonical_json_filename,
)


def validate_json_structure(json_obj: dict) -> bool:
    if not isinstance(json_obj, dict):
        return False
    if json_obj.get("schema_version") == "2.0":
        return all(k in json_obj for k in ["schema_version", "metadata", "runs"])
    if "transcriptions" in json_obj:
        return True
    return False


def get_json_summary(json_path: Path) -> Dict[str, Any]:
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            json_obj = json.load(f)
        if json_obj.get("schema_version") == "2.0":
            runs = json_obj.get("runs", [])
            total_outputs = sum(len(run.get("outputs", [])) for run in runs)
            return {
                "format": "V2",
                "runs": len(runs),
                "total_outputs": total_outputs,
                "created": json_obj.get("metadata", {}).get("created", "unknown"),
                "valid": True,
            }
        else:
            transcriptions = json_obj.get("transcriptions", [])
            return {
                "format": "Legacy",
                "runs": 1,
                "total_outputs": len(transcriptions),
                "created": "unknown",
                "valid": True,
            }
    except Exception as e:
        return {"format": "Unknown", "runs": 0, "total_outputs": 0, "created": "unknown", "valid": False, "error": str(e)}


def load_v2_json(json_path: Path) -> Optional[Dict[str, Any]]:
    """Load and return a V2 JSON transcription file, or None on error."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log_error(f"Failed to load JSON: {json_path}", error=str(e))
        return None


def save_transcription_run(
    workspace: SessionWorkspace,
    file_index: FileIndex,
    root: str,
    model: str,
    temperature: float,
    base_prompt: str,
    domain_prompt: str,
    tokens_in: int,
    tokens_out: int,
    token_method: str,
    transcription_outputs: List[str],
    provider: str = "",
    profile_name: str = "",
    estimated_cost_usd=None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    thinking_tokens: int = 0,
) -> bool:
    """Write a transcription run to the workspace JSON file for root."""
    try:
        now = datetime.utcnow()
        started_at = started_at or now
        completed_at = completed_at or now

        run_data = {
            "timestamp": now.isoformat() + "Z",
            "model": model,
            "provider": provider,
            "profile_name": profile_name,
            "temperature": temperature,
            "base_prompt": base_prompt,
            "domain_prompt": domain_prompt,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "thinking_tokens": thinking_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "token_method": token_method,
            "started_at": started_at.isoformat() + "Z",
            "completed_at": completed_at.isoformat() + "Z",
            "duration_ms": int((completed_at - started_at).total_seconds() * 1000),
            "outputs": transcription_outputs,
        }

        # Find or create JSON file path
        json_path: Optional[Path] = None
        if root in file_index.records and file_index.records[root].json_path:
            candidate = Path(file_index.records[root].json_path)
            if candidate.exists():
                json_path = candidate

        if json_path and json_path.exists():
            with open(json_path, "r", encoding="utf-8") as f:
                existing_json = json.load(f)
            append_run_to_v2_json(existing_json, run_data)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(existing_json, f, indent=2, ensure_ascii=False)
            if root in file_index.records:
                file_index.records[root].run_count = len(existing_json.get("runs", []))
        else:
            v2_json = create_v2_json_schema(root=root, image_filename=f"{root}.jpg", app_version="2.0")
            append_run_to_v2_json(v2_json, run_data)
            if not workspace.ensure_workspace() or not workspace.workspace_path:
                log_error("No workspace available for saving JSON", root=root)
                return False
            json_filename = get_canonical_json_filename(root)
            new_json_path = workspace.workspace_path / json_filename
            with open(new_json_path, "w", encoding="utf-8") as f:
                json.dump(v2_json, f, indent=2, ensure_ascii=False)
            file_index.register_file(new_json_path)

        audit_logger.log_json_save(str(json_path or "new"), "backend")
        return True

    except Exception as e:
        log_error(f"Error saving transcription run for {root}", error=str(e))
        return False


def save_harmonization(
    workspace: SessionWorkspace,
    file_index: FileIndex,
    root: str,
    harmonized_text: str,
    source_indices: List[int],
    model_used: str,
    temperature: float,
    tokens_used: Dict[str, int],
    provider: str = "",
    system_prompt: str = "",
    task_prompt: str = "",
) -> bool:
    """Append a harmonization record to the workspace JSON for root."""
    try:
        json_path: Optional[Path] = None
        if root in file_index.records and file_index.records[root].json_path:
            candidate = Path(file_index.records[root].json_path)
            if candidate.exists():
                json_path = candidate

        if not json_path:
            log_error(f"No JSON file found for root: {root}")
            return False

        with open(json_path, "r", encoding="utf-8") as f:
            existing_json = json.load(f)

        runs = existing_json.get("runs", [])
        source_run_ids = []
        output_idx = 0
        for run in runs:
            run_outputs = run.get("outputs", [])
            run_id = run.get("run_id", "")
            for _ in run_outputs:
                if output_idx in source_indices:
                    source_run_ids.append(run_id)
                output_idx += 1

        harm_record = create_harmonization_record(
            harmonized_text=harmonized_text,
            source_run_ids=list(dict.fromkeys(source_run_ids)),
            source_indices=source_indices,
            model_used=model_used,
            temperature=temperature,
            tokens_used=tokens_used,
            created_at=datetime.utcnow(),
            provider=provider,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
        )

        append_harmonization_to_v2_json(existing_json, harm_record)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(existing_json, f, indent=2, ensure_ascii=False)

        audit_logger.log_json_save(str(json_path), "backend")
        return True

    except Exception as e:
        log_error(f"Error saving harmonization for {root}", error=str(e))
        return False


def save_summary(
    workspace: SessionWorkspace,
    file_index: FileIndex,
    root: str,
    summary_text: str,
    source_indices: List[int],
    model_used: str,
    provider: str,
    temperature: float,
    system_prompt: str,
    tokens_used: Dict[str, Any],
    task_prompt: str = "",
) -> bool:
    """Append a summary record to the workspace JSON for root."""
    try:
        json_path: Optional[Path] = None
        if root in file_index.records and file_index.records[root].json_path:
            candidate = Path(file_index.records[root].json_path)
            if candidate.exists():
                json_path = candidate

        if not json_path:
            log_error(f"No JSON file found for root: {root}")
            return False

        with open(json_path, "r", encoding="utf-8") as f:
            existing_json = json.load(f)

        summary_record = create_summary_record(
            summary_text=summary_text,
            source_indices=source_indices,
            model_used=model_used,
            provider=provider,
            temperature=temperature,
            system_prompt=system_prompt,
            tokens_used=tokens_used,
            created_at=datetime.utcnow(),
            task_prompt=task_prompt,
        )

        append_summary_to_v2_json(existing_json, summary_record)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(existing_json, f, indent=2, ensure_ascii=False)

        audit_logger.log_json_save(str(json_path), "backend")
        return True

    except Exception as e:
        log_error(f"Error saving summary for {root}", error=str(e))
        return False


def save_ner_result(
    workspace: SessionWorkspace,
    file_index: FileIndex,
    root: str,
    entity_bundle: Dict[str, Any],
    grounding_info: Dict[str, Any],
    tokens_usage: Dict[str, Any],
    pass2_used: bool,
    source_indices: List[int],
    model_used: str,
    provider: str,
    temperature: float,
    system_prompt: str,
    task_prompt: str = "",
) -> bool:
    """Append a NER result record to the workspace JSON for root."""
    try:
        json_path: Optional[Path] = None
        if root in file_index.records and file_index.records[root].json_path:
            candidate = Path(file_index.records[root].json_path)
            if candidate.exists():
                json_path = candidate

        if not json_path:
            log_error(f"No JSON file found for root: {root}")
            return False

        with open(json_path, "r", encoding="utf-8") as f:
            existing_json = json.load(f)

        ner_record = create_ner_record(
            entity_bundle=entity_bundle,
            grounding_info=grounding_info,
            tokens_usage=tokens_usage,
            pass2_used=pass2_used,
            source_indices=source_indices,
            model_used=model_used,
            provider=provider,
            temperature=temperature,
            system_prompt=system_prompt,
            created_at=datetime.utcnow(),
            task_prompt=task_prompt,
        )

        append_ner_result_to_v2_json(existing_json, ner_record)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(existing_json, f, indent=2, ensure_ascii=False)

        audit_logger.log_json_save(str(json_path), "backend")
        return True

    except Exception as e:
        log_error(f"Error saving NER result for {root}", error=str(e))
        return False


# =========================
# CONSISTENCY ANALYSIS RECORDS
# =========================


def _resolve_json_path(file_index: FileIndex, root: str) -> Optional[Path]:
    """The document's canonical JSON path, or None if it has none yet."""
    record = file_index.records.get(root)
    if not record or not record.json_path:
        return None
    candidate = Path(record.json_path)
    return candidate if candidate.exists() else None


def save_analysis(
    workspace: SessionWorkspace,
    file_index: FileIndex,
    root: str,
    report: Dict[str, Any],
    user_note: str = "",
) -> Optional[Dict[str, Any]]:
    """Append a consistency analysis to the workspace JSON for root.

    Saving is additive and non-destructive (D11): re-running after excluding
    attempts and saving again produces a second record, and each one carries the
    attempts it included and excluded so the difference is self-documenting.

    Returns the stored record (with its freshly minted id) or None on failure.
    """
    try:
        json_path = _resolve_json_path(file_index, root)
        if not json_path:
            log_error(f"No JSON file found for root: {root}")
            return None

        with open(json_path, "r", encoding="utf-8") as f:
            existing_json = json.load(f)

        record = create_analysis_record(report, user_note=user_note)
        append_analysis_to_v2_json(existing_json, record)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(existing_json, f, indent=2, ensure_ascii=False)

        audit_logger.log_json_save(str(json_path), "backend")
        log_info(f"Saved consistency analysis for {root}", analysis_id=record["analysis_id"])
        return record

    except Exception as e:
        log_error(f"Error saving consistency analysis for {root}", error=str(e))
        return None


def list_analyses(file_index: FileIndex, root: str) -> List[Dict[str, Any]]:
    """Every stored consistency analysis for a document, oldest first."""
    json_path = _resolve_json_path(file_index, root)
    if not json_path:
        return []
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f).get("analyses", []) or []
    except Exception as e:
        log_error(f"Error reading analyses for {root}", error=str(e))
        return []


def get_analysis(file_index: FileIndex, root: str, analysis_id: str) -> Optional[Dict[str, Any]]:
    """One stored analysis by id."""
    for record in list_analyses(file_index, root):
        if record.get("analysis_id") == analysis_id:
            return record
    return None


def delete_analysis(file_index: FileIndex, root: str, analysis_id: str) -> bool:
    """Remove one stored analysis. Returns False when the id is not present."""
    try:
        json_path = _resolve_json_path(file_index, root)
        if not json_path:
            return False

        with open(json_path, "r", encoding="utf-8") as f:
            existing_json = json.load(f)

        analyses = existing_json.get("analyses", []) or []
        remaining = [a for a in analyses if a.get("analysis_id") != analysis_id]
        if len(remaining) == len(analyses):
            return False

        existing_json["analyses"] = remaining
        existing_json["metadata"]["updated_at"] = datetime.utcnow().isoformat() + "Z"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(existing_json, f, indent=2, ensure_ascii=False)

        audit_logger.log_json_save(str(json_path), "backend")
        return True

    except Exception as e:
        log_error(f"Error deleting analysis {analysis_id} for {root}", error=str(e))
        return False
