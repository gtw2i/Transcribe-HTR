"""FastAPI dependency functions for session/workspace access.

Two modes:

* Web (default): every POST /api/session/init creates a new session with a
  disposable temp workspace, keyed by a signed session cookie.

* Persistent workspace (TRANSCRIBE_HTR_PERSISTENT_WORKSPACE=true; set by the
  desktop launcher): there is exactly one session, "desktop", whose workspace
  lives in the user's data directory and survives restarts. Its file index is
  rebuilt from disk on startup and on every session init, so files added to
  the folder outside the app also appear. The session cookie is not needed.
"""

import json
import os
import threading
import uuid

from fastapi import HTTPException, Request

from app_paths import user_data_dir, user_workspace_dir
from core.session_workspace import FileIndex, SessionWorkspace

# In-memory session store — swap for Redis in production
_session_store: dict[str, dict] = {}

DESKTOP_SESSION_ID = "desktop"
WORKSPACE_LAYOUT_VERSION = 1
_desktop_lock = threading.Lock()


def persistent_workspace_enabled() -> bool:
    value = os.getenv("TRANSCRIBE_HTR_PERSISTENT_WORKSPACE", "")
    return value.strip().lower() in ("1", "true", "yes")


def _write_layout_marker() -> None:
    # Lives beside the workspace, not in it: the workspace scan treats every
    # top-level *.json as a document. Lets a future layout change migrate data.
    marker = user_data_dir() / "workspace-info.json"
    if not marker.exists():
        marker.write_text(json.dumps({"layout_version": WORKSPACE_LAYOUT_VERSION}), encoding="utf-8")


def _desktop_session() -> dict:
    with _desktop_lock:
        session = _session_store.get(DESKTOP_SESSION_ID)
        if session is None:
            ws = SessionWorkspace(DESKTOP_SESSION_ID, workspace_path=user_workspace_dir())
            if not ws.ensure_workspace():
                raise HTTPException(status_code=500, detail="Could not create workspace directory.")
            _write_layout_marker()
            index = FileIndex(ws)
            index.populate_from_workspace()
            session = {"session_id": DESKTOP_SESSION_ID, "file_index": index, "workspace": ws}
            _session_store[DESKTOP_SESSION_ID] = session
        return session


def create_session() -> str:
    """Create a new session and return its ID."""
    if persistent_workspace_enabled():
        session = _desktop_session()
        with _desktop_lock:
            session["file_index"].populate_from_workspace()
        return DESKTOP_SESSION_ID
    sid = str(uuid.uuid4())
    ws = SessionWorkspace(session_id=sid)
    ws.ensure_workspace()
    _session_store[sid] = {"session_id": sid, "file_index": FileIndex(ws)}
    return sid


def get_session(request: Request) -> dict:
    """Return the session dict for the current request, or raise 401."""
    if persistent_workspace_enabled():
        return _desktop_session()
    sid = request.session.get("session_id")
    if sid and sid in _session_store:
        return _session_store[sid]
    raise HTTPException(status_code=401, detail="No active session. Call POST /api/session/init first.")


def get_workspace(request: Request) -> SessionWorkspace:
    """Return an initialized SessionWorkspace for the current session."""
    session = get_session(request)
    if "workspace" in session:
        return session["workspace"]
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
