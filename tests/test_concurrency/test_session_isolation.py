"""Workspace isolation between concurrent sessions.

Scope note: session *identity* and the per-session FileIndex cache are no
longer concerns of session_workspace. In the FastAPI backend they live in
backend/dependencies.py (get_workspace/get_file_index, keyed off the signed
session cookie) and are exercised through the API in tests/test_api/. What
remains here is the part session_workspace still owns: that two session IDs
never share a directory, even under concurrent writes.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import session_workspace as sw


def test_session_workspace_paths_are_isolated_by_session_id(monkeypatch, tmp_path):
    monkeypatch.setenv("TRANSCRIBE_SESSION_ROOT", str(tmp_path))

    ws_a = sw.SessionWorkspace(session_id="session-a")
    ws_b = sw.SessionWorkspace(session_id="session-b")

    assert ws_a.ensure_workspace() is True
    assert ws_b.ensure_workspace() is True

    assert ws_a.workspace_path != ws_b.workspace_path
    assert "session-a" in str(ws_a.workspace_path)
    assert "session-b" in str(ws_b.workspace_path)


def test_parallel_persist_uploaded_files_stay_isolated(monkeypatch, tmp_path):
    """Two sessions writing the SAME filename concurrently must not collide."""
    monkeypatch.setenv("TRANSCRIBE_SESSION_ROOT", str(tmp_path))

    def _persist_for_session(session_id: str) -> Path:
        ws = sw.SessionWorkspace(session_id=session_id)
        assert ws.ensure_workspace() is True
        saved = ws.persist_uploaded_file(
            "shared_name.png",
            f"payload-{session_id}".encode(),
            allow_overwrite=True,
        )
        assert saved is not None
        return saved

    with ThreadPoolExecutor(max_workers=2) as pool:
        future_a = pool.submit(_persist_for_session, "S-A")
        future_b = pool.submit(_persist_for_session, "S-B")
        path_a = future_a.result()
        path_b = future_b.result()

    assert path_a != path_b
    assert path_a.exists() and path_b.exists()
    assert path_a.read_bytes() == b"payload-S-A"
    assert path_b.read_bytes() == b"payload-S-B"
