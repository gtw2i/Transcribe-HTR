"""Transcription endpoint."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from core.image_utils import load_image_bytes
from dependencies import get_file_index, get_workspace
from engines.transcription_engine import TranscriptionEngine
from schemas.transcription import TranscribeRequest, TranscribeResponse

router = APIRouter(tags=["transcription"])


@router.post("/transcribe", response_model=TranscribeResponse)
def transcribe(req: TranscribeRequest, workspace=Depends(get_workspace), file_index=Depends(get_file_index)):
    """Run transcription on the image for the given root."""
    if req.root not in file_index.records:
        raise HTTPException(status_code=404, detail=f"Root '{req.root}' not found.")
    record = file_index.records[req.root]
    if not record.has_image():
        raise HTTPException(status_code=400, detail=f"No image found for root '{req.root}'.")

    img_path = Path(record.image_path)
    if not img_path.exists():
        raise HTTPException(status_code=404, detail=f"Image file missing for root '{req.root}'.")

    try:
        img_bytes = load_image_bytes(str(img_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not load image: {e}")

    engine = TranscriptionEngine()
    result = engine.run_transcription(
        api_key=req.openai_api_key,
        img_bytes=img_bytes,
        model=req.model,
        n_responses=req.n_responses,
        prompt=req.domain_knowledge,
        source_choice=req.source_choice,
        active_root=req.root,
        provider=req.provider,
        gemini_api_key=req.gemini_api_key,
        anthropic_api_key=req.anthropic_api_key,
        profile_name=req.profile_name,
        workspace=workspace,
        file_index=file_index,
    )

    if not result["success"]:
        return TranscribeResponse(success=False, error=result.get("error"))

    text_outputs = [o["text"] for o in result.get("outputs", [])]
    return TranscribeResponse(
        success=True,
        outputs=text_outputs,
        tokens_usage=result.get("tokens_usage"),
        fallback_used=result.get("fallback_used", False),
        fallback_info=result.get("fallback_info"),
    )
