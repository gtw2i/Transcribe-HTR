"""Model list endpoint."""

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["models"])


class ModelsRequest(BaseModel):
    provider: str
    api_key: str


@router.post("/models")
def fetch_models(req: ModelsRequest):
    """Fetch the live model list for a provider. Returns [] on failure."""
    from providers import fetch_model_list
    models = fetch_model_list(req.provider, req.api_key)
    return {"provider": req.provider, "models": models}
