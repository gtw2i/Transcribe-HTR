"""Persistent single-user workspace (TRANSCRIBE_HTR_PERSISTENT_WORKSPACE).

The desktop app keeps the user's documents in their data directory so work
survives restarts. These tests simulate a restart by clearing the in-process
session store, and pin that web mode (the default) is unchanged.
"""

import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from starlette.middleware.sessions import SessionMiddleware

import dependencies
from routers import files as files_router
from routers import session as session_router


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buf, format="PNG")
    return buf.getvalue()


def _restart():
    """What a process restart does to backend state."""
    dependencies._session_store.clear()


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_HTR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("TRANSCRIBE_SESSION_ROOT", str(tmp_path / "sessions_root"))
    _restart()
    yield tmp_path / "data"
    _restart()


@pytest.fixture
def persistent(data_dir, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_HTR_PERSISTENT_WORKSPACE", "true")
    return data_dir


def _client():
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test")
    app.include_router(session_router.router, prefix="/api")
    app.include_router(files_router.router, prefix="/api")
    return TestClient(app)


def _roots(client):
    return sorted(r["root"] for r in client.get("/api/files/roots").json())


class TestPersistentMode:
    def test_session_is_a_single_fixed_workspace_in_user_data(self, persistent):
        assert dependencies.create_session() == "desktop"
        assert dependencies.create_session() == "desktop"
        ws = dependencies._session_store["desktop"]["workspace"]
        assert ws.workspace_path == persistent / "workspace"
        assert json.loads((persistent / "workspace-info.json").read_text())["layout_version"] == 1

    def test_layout_marker_is_not_listed_as_a_document(self, persistent):
        client = _client()
        client.post("/api/session/init")
        assert _roots(client) == []

    def test_work_survives_a_restart(self, persistent):
        client = _client()
        client.post("/api/session/init")
        client.post("/api/upload", files=[("files", ("letter.png", _png()))])
        ws = persistent / "workspace"
        (ws / "letter.transcription.json").write_text(
            json.dumps({"version": "2.0", "runs": [{"id": 1}, {"id": 2}]}), encoding="utf-8"
        )

        _restart()
        client = _client()  # new process, no cookie
        client.post("/api/session/init")

        roots = client.get("/api/files/roots").json()
        assert [(r["root"], r["run_count"]) for r in roots] == [("letter", 2)]
        assert client.get("/api/files/letter/image").status_code == 200

    def test_no_cookie_needed(self, persistent):
        # A request before (or without) init still resolves the one session.
        assert _client().get("/api/files/roots").status_code == 200

    def test_files_added_to_the_folder_appear_on_init(self, persistent):
        client = _client()
        client.post("/api/session/init")
        (persistent / "workspace" / "dropped.png").write_bytes(_png())
        assert _roots(client) == []
        client.post("/api/session/init")
        assert _roots(client) == ["dropped"]

    def test_reupload_never_overwrites(self, persistent):
        client = _client()
        client.post("/api/session/init")
        first = client.post("/api/upload", files=[("files", ("page.png", _png()))]).json()
        second = client.post("/api/upload", files=[("files", ("page.png", _png()))]).json()
        assert first["roots"] == ["page"]
        assert second["roots"] == ["page-1"]
        assert _roots(client) == ["page", "page-1"]


class TestWebModeUnchanged:
    def test_each_init_is_a_new_temp_session(self, data_dir, monkeypatch):
        monkeypatch.delenv("TRANSCRIBE_HTR_PERSISTENT_WORKSPACE", raising=False)
        a, b = dependencies.create_session(), dependencies.create_session()
        assert a != b and "desktop" not in (a, b)
        assert not (data_dir / "workspace").exists()

    def test_requests_need_a_session_cookie(self, data_dir, monkeypatch):
        monkeypatch.delenv("TRANSCRIBE_HTR_PERSISTENT_WORKSPACE", raising=False)
        assert _client().get("/api/files/roots").status_code == 401
