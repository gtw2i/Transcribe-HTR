"""Harmonization request / response models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class HarmonizeRequest(BaseModel):
    root: str
    model: str
    provider: str = "OpenAI"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    source_indices: List[int] = []
    profile_name: str = ""
    ner_entity_bundle: Optional[Dict[str, Any]] = None


class HarmonizeResponse(BaseModel):
    success: bool
    harmonized_text: str = ""
    tokens_used: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    model_used: Optional[str] = None
    fallback_used: bool = False
    fallback_info: Optional[Dict[str, Any]] = None
