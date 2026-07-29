"""NER request / response models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class NerRequest(BaseModel):
    root: str
    model: str
    provider: str = "Gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    source_indices: List[int] = []
    min_search_queries: int = 5
    pass1_max_tokens: int = 10000
    pass2_max_tokens: int = 20000
    entity_types: Optional[List[str]] = None


class NerPassTokens(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    thinking_tokens: int = 0
    total_tokens: int = 0


class NerTokensUsage(BaseModel):
    pass1: NerPassTokens = NerPassTokens()
    pass2: NerPassTokens = NerPassTokens()
    total: NerPassTokens = NerPassTokens()


class NerResponse(BaseModel):
    success: bool
    entity_bundle: Optional[Dict[str, Any]] = None
    grounding_info: Optional[Dict[str, Any]] = None
    tokens_usage: Optional[NerTokensUsage] = None
    pass2_used: bool = True
    error: Optional[str] = None
    model_used: Optional[str] = None
    fallback_used: bool = False
    fallback_info: Optional[Dict[str, Any]] = None
