"""Text-to-Speech endpoint."""

import base64

from fastapi import APIRouter

from engines.tts_engine import TTSEngine
from schemas.tts import TtsRequest, TtsResponse

router = APIRouter(tags=["tts"])


@router.post("/tts/generate", response_model=TtsResponse)
def generate_tts(req: TtsRequest):
    """Generate speech from text and return base64-encoded WAV audio."""
    engine = TTSEngine(api_key=req.openai_api_key)
    result = engine.generate_speech(
        text=req.text,
        model=req.model,
        voice=req.voice,
        use_cache=req.use_cache,
        original_image_filename=req.original_image_filename,
    )

    if not result.get("success"):
        return TtsResponse(success=False, error=result.get("error"))

    audio_b64 = base64.b64encode(result["audio_data"]).decode()
    return TtsResponse(
        success=True,
        audio_b64=audio_b64,
        metadata=result.get("metadata"),
        from_cache=result.get("from_cache", False),
        model_used=result.get("model_used"),
        fallback_used=result.get("fallback_used", False),
        fallback_info=result.get("fallback_info"),
    )
