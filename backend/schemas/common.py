"""Shared response models."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class SessionInfo(BaseModel):
    session_id: str


class ErrorResponse(BaseModel):
    detail: str
