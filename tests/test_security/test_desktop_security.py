"""Local-server hardening in desktop mode (backend/core/desktop_security.py).

The desktop backend listens on 127.0.0.1, which other accounts on the same
computer and any web page in any browser can reach. With a launch token set,
only the app's own window (cookie) or launcher (header) may use the API.
Each test builds a fresh app from backend/main.py, which reads the token at
import time.
"""

import importlib.util
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

MAIN = Path(__file__).resolve().parents[2] / "backend" / "main.py"
TOKEN = "t0ken-for-tests"
LOCAL = "http://127.0.0.1:51234"


def _fresh_app():
    spec = importlib.util.spec_from_file_location("main_for_security_test", MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


@pytest.fixture
def desktop(monkeypatch, tmp_path):
    monkeypatch.setenv("TRANSCRIBE_HTR_LAUNCH_TOKEN", TOKEN)
    monkeypatch.setenv("TRANSCRIBE_HTR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "no-dist"))
    return TestClient(_fresh_app(), base_url=LOCAL)


@pytest.fixture
def web(monkeypatch, tmp_path):
    monkeypatch.delenv("TRANSCRIBE_HTR_LAUNCH_TOKEN", raising=False)
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "no-dist"))
    return TestClient(_fresh_app(), base_url=LOCAL)


def _login(client):
    res = client.get(f"/api/desktop/auth?token={TOKEN}")
    assert res.status_code == 200
    return res


class TestDesktopMode:
    def test_api_is_closed_without_the_token(self, desktop):
        assert desktop.get("/api/profiles").status_code == 403
        assert desktop.post("/api/session/init").status_code == 403

    def test_health_stays_open_for_the_launcher(self, desktop):
        assert desktop.get("/api/health").status_code == 200

    def test_wrong_token_is_refused(self, desktop):
        assert desktop.get("/api/desktop/auth?token=nope").status_code == 403
        assert desktop.get("/api/desktop/auth").status_code == 403
        assert desktop.get("/api/profiles").status_code == 403

    def test_auth_sets_a_strict_httponly_cookie_and_unlocks_the_api(self, desktop):
        res = _login(desktop)
        cookie = res.headers["set-cookie"].lower()
        assert "htr_desktop_auth=" in cookie
        assert "httponly" in cookie and "samesite=strict" in cookie
        assert "location.replace('/')" in res.text
        assert desktop.get("/api/profiles").status_code == 200

    def test_header_token_works_for_the_launcher(self, desktop):
        assert desktop.get("/api/profiles", headers={"X-HTR-Token": TOKEN}).status_code == 200

    def test_foreign_host_header_is_rejected(self, desktop):
        # DNS rebinding: a page on evil.example resolves its name to 127.0.0.1.
        res = desktop.get("/api/health", headers={"host": "evil.example:51234"})
        assert res.status_code == 400

    def test_api_docs_are_disabled(self, desktop):
        _login(desktop)
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert desktop.get(path).status_code == 404

    def test_no_cross_origin_access(self, desktop):
        res = desktop.options(
            "/api/profiles",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
        assert "access-control-allow-origin" not in res.headers


class TestWebModeUnchanged:
    def test_no_token_needed(self, web):
        assert web.get("/api/profiles").status_code == 200

    def test_docs_available(self, web):
        assert web.get("/openapi.json").status_code == 200

    def test_no_auth_route(self, web):
        assert web.get(f"/api/desktop/auth?token={TOKEN}").status_code == 404
