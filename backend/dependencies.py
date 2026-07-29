"""FastAPI dependency functions for session/workspace access."""

import uuid
from typing import Optional

from fastapi import HTTPException, Request

from core.session_workspace import FileIndex, SessionWorkspace

# In-memory session store — swap for Redis in production
_session_store: dict[str, dict] = {}


def create_session() -> str:
    """Create a new session and return its ID."""
    sid = str(uuid.uuid4())
    ws = SessionWorkspace(session_id=sid)
    ws.ensure_workspace()
    _session_store[sid] = {"session_id": sid, "file_index": FileIndex(ws)}
    return sid


def get_session(request: Request) -> dict:
    """Return the session dict for the current request, or raise 401."""
    sid = request.session.get("session_id")
    if sid and sid in _session_store:
        return _session_store[sid]
    raise HTTPException(status_code=401, detail="No active session. Call POST /api/session/init first.")


def get_workspace(request: Request) -> SessionWorkspace:
    """Return an initialized SessionWorkspace for the current session."""
    session = get_session(request)
    ws = SessionWorkspace(session_id=session["session_id"])
    if not ws.ensure_workspace():
        raise HTTPException(status_code=500, detail="Could not create workspace directory.")
    return ws


def get_file_index(request: Request) -> FileIndex:
    """Return the FileIndex for the current session."""
    session = get_session(request)
    return session["file_index"]


def get_session_store() -> dict:
    """Return the raw session store (for internal use)."""
    return _session_store
