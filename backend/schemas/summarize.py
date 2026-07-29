"""Summarize request / response models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    root: str
    model: str
    provider: str = "Gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    source_indices: List[int] = []
    profile_name: str = ""


class SummarizeResponse(BaseModel):
    success: bool
    summary: str = ""
    tokens_used: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    model_used: Optional[str] = None
    provider_used: Optional[str] = None
    fallback_used: bool = False
    fallback_info: Optional[Dict[str, Any]] = None
