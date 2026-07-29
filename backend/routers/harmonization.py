"""Harmonization endpoint."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from core.json_manager import load_v2_json
from dependencies import get_file_index, get_workspace
from engines.harmonization_engine import HarmonizationEngine
from schemas.harmonization import HarmonizeRequest, HarmonizeResponse

router = APIRouter(tags=["harmonization"])


@router.post("/harmonize", response_model=HarmonizeResponse)
def harmonize(req: HarmonizeRequest, workspace=Depends(get_workspace), file_index=Depends(get_file_index)):
    """Harmonize selected transcriptions for a root."""
    if req.root not in file_index.records:
        raise HTTPException(status_code=404, detail=f"Root '{req.root}' not found.")
    record = file_index.records[req.root]
    if not record.has_json():
        raise HTTPException(status_code=400, detail=f"No transcription JSON for root '{req.root}'.")

    json_data = load_v2_json(Path(record.json_path))
    if json_data is None:
        raise HTTPException(status_code=500, detail="Failed to load transcription JSON.")

    # Collect all text outputs from runs
    all_outputs: list[str] = []
    for run in json_data.get("runs", []):
        for output in run.get("outputs", []):
            text = output.get("text", "") if isinstance(output, dict) else str(output)
            all_outputs.append(text)

    if not all_outputs:
        raise HTTPException(status_code=400, detail="No transcription outputs found in JSON.")

    # Select by index (default: all)
    indices = req.source_indices or list(range(len(all_outputs)))
    selected = [{"text": all_outputs[i], "index": i} for i in indices if i < len(all_outputs)]

    if len(selected) < 2:
        raise HTTPException(status_code=400, detail="At least 2 transcriptions required for harmonization.")

    engine = HarmonizationEngine(profile_name=req.profile_name or None)

    try:
        result = engine.harmonize_transcriptions(
            transcriptions=selected,
            api_key=req.openai_api_key,
            model=req.model,
            provider=req.provider,
            gemini_api_key=req.gemini_api_key,
            anthropic_api_key=req.anthropic_api_key,
            active_root=req.root,
            workspace=workspace,
            file_index=file_index,
            ner_entity_bundle=req.ner_entity_bundle,
        )
    except RuntimeError as e:
        return HarmonizeResponse(success=False, error=str(e))

    return HarmonizeResponse(
        success=True,
        harmonized_text=result.get("harmonized_text", ""),
        tokens_used=result.get("tokens_used"),
        model_used=result.get("model_used"),
        fallback_used=result.get("fallback_used", False),
        fallback_info=result.get("fallback_info"),
    )
