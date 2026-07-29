"""Document summarization endpoint."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from core.json_manager import load_v2_json, save_summary
from dependencies import get_file_index, get_workspace
from engines.summary_engine import summarize_document
from logging_config import log_warning
from schemas.summarize import SummarizeRequest, SummarizeResponse

router = APIRouter(tags=["summarize"])


@router.post("/summarize", response_model=SummarizeResponse)
def summarize(req: SummarizeRequest, workspace=Depends(get_workspace), file_index=Depends(get_file_index)):
    """Summarize transcriptions for a root, noting entity uncertainty."""
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

    result = summarize_document(
        transcriptions=selected,
        provider=req.provider,
        model=req.model,
        gemini_api_key=req.gemini_api_key,
        openai_api_key=req.openai_api_key,
        anthropic_api_key=req.anthropic_api_key,
    )

    if not result["success"]:
        return SummarizeResponse(success=False, error=result.get("error"))

    try:
        ok = save_summary(
            workspace=workspace,
            file_index=file_index,
            root=req.root,
            summary_text=result.get("summary", ""),
            source_indices=indices,
            model_used=result["model"],
            provider=result["provider"],
            temperature=result["temperature"],
            system_prompt=result["system_prompt"],
            tokens_used=result.get("tokens_used"),
            task_prompt=result["task_prompt"],
        )
        if not ok:
            log_warning("Failed to save summary to JSON")
    except Exception as save_error:
        log_warning(f"Auto-save summary failed: {save_error}")

    return SummarizeResponse(
        success=True,
        summary=result.get("summary", ""),
        tokens_used=result.get("tokens_used"),
        model_used=result.get("model"),
        provider_used=result.get("provider"),
        fallback_used=result.get("fallback_used", False),
        fallback_info=result.get("fallback_info"),
    )
