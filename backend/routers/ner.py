"""Named Entity Recognition endpoint."""

from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from config import PROVIDER_ANTHROPIC, PROVIDER_OPENAI
from core.json_manager import load_v2_json, save_ner_result
from dependencies import get_file_index, get_workspace
from engines.ner_engine import _ENTITY_SCHEMA, run_ner
from logging_config import log_warning
from schemas.ner import NerRequest, NerResponse

router = APIRouter(tags=["ner"])


@router.get("/ner/entity-types", response_model=List[str])
def get_entity_types():
    """Return the default entity type enum from the schema."""
    return _ENTITY_SCHEMA["properties"]["entities"]["items"]["properties"]["type"]["enum"]


@router.post("/ner", response_model=NerResponse)
def named_entity_recognition(req: NerRequest, workspace=Depends(get_workspace), file_index=Depends(get_file_index)):
    """Run two-pass NER on selected transcriptions for a root."""
    if req.root not in file_index.records:
        raise HTTPException(status_code=404, detail=f"Root '{req.root}' not found.")
    record = file_index.records[req.root]
    if not record.has_json():
        raise HTTPException(status_code=400, detail=f"No transcription JSON for root '{req.root}'.")

    json_data = load_v2_json(Path(record.json_path))
    if json_data is None:
        raise HTTPException(status_code=500, detail="Failed to load transcription JSON.")

    all_outputs: list[str] = []
    for run in json_data.get("runs", []):
        for output in run.get("outputs", []):
            text = output.get("text", "") if isinstance(output, dict) else str(output)
            all_outputs.append(text)

    if not all_outputs:
        raise HTTPException(status_code=400, detail="No transcription outputs found.")

    indices = req.source_indices or list(range(len(all_outputs)))
    selected = [all_outputs[i] for i in indices if i < len(all_outputs)]

    if req.provider == PROVIDER_OPENAI:
        active_api_key = req.openai_api_key
    elif req.provider == PROVIDER_ANTHROPIC:
        active_api_key = req.anthropic_api_key
    else:
        active_api_key = req.gemini_api_key

    result = run_ner(
        transcriptions=selected,
        provider=req.provider,
        api_key=active_api_key,
        model=req.model,
        min_search_queries=req.min_search_queries,
        pass1_max_tokens=req.pass1_max_tokens,
        pass2_max_tokens=req.pass2_max_tokens,
        entity_types=req.entity_types or None,
    )

    if not result["success"]:
        return NerResponse(success=False, error=result.get("error"))

    try:
        ok = save_ner_result(
            workspace=workspace,
            file_index=file_index,
            root=req.root,
            entity_bundle=result.get("entity_bundle"),
            grounding_info=result.get("grounding_info"),
            tokens_usage=result.get("tokens_usage"),
            pass2_used=result.get("pass2_used", False),
            source_indices=indices,
            model_used=result["model"],
            provider=result["provider"],
            temperature=result["temperature"],
            system_prompt=result["system_prompt"],
            task_prompt=result["task_prompt"],
        )
        if not ok:
            log_warning("Failed to save NER result to JSON")
    except Exception as save_error:
        log_warning(f"Auto-save NER result failed: {save_error}")

    return NerResponse(
        success=True,
        entity_bundle=result.get("entity_bundle"),
        grounding_info=result.get("grounding_info"),
        tokens_usage=result.get("tokens_usage"),
        model_used=result.get("model"),
        fallback_used=result.get("fallback_used", False),
        fallback_info=result.get("fallback_info"),
    )
