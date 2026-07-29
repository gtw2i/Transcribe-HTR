"""Transcription request / response models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class TranscribeRequest(BaseModel):
    root: str
    model: str
    provider: str = "Gemini"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    n_responses: int = 1
    domain_knowledge: str = ""
    source_choice: str = "Call API"
    profile_name: str = ""


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    provider: str = ""
    estimated_cost_usd: Optional[float] = None


class TranscribeResponse(BaseModel):
    success: bool
    outputs: List[str] = []
    tokens_usage: Optional[TokenUsage] = None
    error: Optional[str] = None
    fallback_used: bool = False
    fallback_info: Optional[Dict[str, Any]] = None
