"""TTS request / response models."""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class TtsRequest(BaseModel):
    text: str
    model: str = "tts-1"
    voice: str = "onyx"
    openai_api_key: str
    use_cache: bool = True
    original_image_filename: Optional[str] = None


class TtsResponse(BaseModel):
    success: bool
    audio_b64: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    from_cache: bool = False
    error: Optional[str] = None
    model_used: Optional[str] = None
    fallback_used: bool = False
    fallback_info: Optional[Dict[str, Any]] = None
