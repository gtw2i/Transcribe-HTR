"""Colorization endpoint."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from engines.colorization_engine import compute_colorization

router = APIRouter(tags=["colorize"])


class ColorizeRequest(BaseModel):
    outputs: List[str]
    sel_idx: int = 0
    mode: str = "Word-level"
    ner_result: Optional[Dict[str, Any]] = None


class ColorizeResponse(BaseModel):
    html: Optional[str] = None
    reason: Optional[str] = None


@router.post("/colorize", response_model=ColorizeResponse)
def colorize(req: ColorizeRequest):
    """Return colorized HTML for the selected transcription output."""
    html, reason = compute_colorization(
        outputs=req.outputs,
        sel_idx=req.sel_idx,
        mode=req.mode,
        ner_result=req.ner_result,
    )
    return ColorizeResponse(html=html, reason=reason)
