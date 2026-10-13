"""Remembered API keys (core/secret_store.py, routers/settings.py).

Keys are served back to the UI only in desktop mode, where the launch token
proves every request comes from the user's own app window. tests/conftest.py
forces the file backend so the suite never touches the real OS credential
store.
"""

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import secret_store

MAIN = Path(__file__).resolve().parents[2] / "backend" / "main.py"
TOKEN = "settings-test-token"


def _fresh_app():
    spec = importlib.util.spec_from_file_location("main_for_settings_test", MAIN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_HTR_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRONTEND_DIST", str(tmp_path / "no-dist"))
    return tmp_path / "data"


@pytest.fixture
def desktop(data_dir, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_HTR_LAUNCH_TOKEN", TOKEN)
    client = TestClient(_fresh_app(), base_url="http://127.0.0.1:5000")
    client.headers["X-HTR-Token"] = TOKEN
    return client


@pytest.fixture
def web(data_dir, monkeypatch):
    monkeypatch.delenv("TRANSCRIBE_HTR_LAUNCH_TOKEN", raising=False)
    return TestClient(_fresh_app())


class TestDesktop:
    def test_round_trip(self, desktop, data_dir):
        assert desktop.put("/api/settings/keys/anthropic", json={"key": " sk-ant-1 "}).json()["stored"]
        body = desktop.get("/api/settings/keys").json()
        assert body["backend"] == "file"
        assert body["keys"] == {"openai": "", "gemini": "", "anthropic": "sk-ant-1"}
        assert json.loads((data_dir / "secrets.json").read_text()) == {"anthropic": "sk-ant-1"}

    def test_empty_key_forgets(self, desktop):
        desktop.put("/api/settings/keys/openai", json={"key": "sk-1"})
        desktop.put("/api/settings/keys/openai", json={"key": "  "})
        assert desktop.get("/api/settings/keys").json()["keys"]["openai"] == ""

    def test_delete(self, desktop):
        desktop.put("/api/settings/keys/gemini", json={"key": "AIza-1"})
        desktop.delete("/api/settings/keys/gemini")
        assert desktop.get("/api/settings/keys").json()["keys"]["gemini"] == ""

    def test_unknown_provider(self, desktop):
        assert desktop.put("/api/settings/keys/../x", json={"key": "k"}).status_code == 404
        assert desktop.put("/api/settings/keys/mistral", json={"key": "k"}).status_code == 404

    def test_keys_require_the_launch_token(self, desktop):
        del desktop.headers["X-HTR-Token"]
        assert desktop.get("/api/settings/keys").status_code == 403

    def test_app_info_reports_locations(self, desktop, data_dir):
        info = desktop.get("/api/app-info").json()
        assert info["desktop"] is True
        assert info["data_dir"] == str(data_dir)
        assert info["workspace_dir"] == str(data_dir / "workspace")
        assert info["secret_backend"] == "file"

    @pytest.mark.skipif(os.name != "posix", reason="POSIX permission bits")
    def test_secrets_file_is_owner_only(self, desktop, data_dir):
        desktop.put("/api/settings/keys/openai", json={"key": "sk-1"})
        mode = stat.S_IMODE((data_dir / "secrets.json").stat().st_mode)
        assert mode == 0o600


class TestWebMode:
    def test_keys_are_never_served(self, web):
        assert web.get("/api/settings/keys").status_code == 404
        assert web.put("/api/settings/keys/openai", json={"key": "k"}).status_code == 404

    def test_app_info_has_no_paths(self, web):
        info = web.get("/api/app-info").json()
        assert info["desktop"] is False
        assert set(info) == {"version", "desktop"}


class TestBackends:
    def test_defaults(self, monkeypatch):
        monkeypatch.delenv("TRANSCRIBE_HTR_SECRET_BACKEND", raising=False)
        monkeypatch.setattr(sys, "platform", "win32")
        assert secret_store._default_backend() == "keyring"
        monkeypatch.setattr(sys, "platform", "darwin")
        assert secret_store._default_backend() == "file"  # unsigned macOS builds

    def test_unusable_keyring_falls_back_to_file(self, monkeypatch, data_dir):
        monkeypatch.setenv("TRANSCRIBE_HTR_SECRET_BACKEND", "keyring")

        def broken():
            raise RuntimeError("no backend")

        monkeypatch.setattr(secret_store, "KeyringSecretStore", broken)
        assert secret_store.get_secret_store().name == "file"

    def test_keyring_backend_round_trip(self, monkeypatch):
        keyring = pytest.importorskip("keyring")
        from keyring.backend import KeyringBackend

        class Memory(KeyringBackend):
            priority = 1
            store = {}

            def get_password(self, service, user):
                return self.store.get((service, user))

            def set_password(self, service, user, password):
                self.store[(service, user)] = password

            def delete_password(self, service, user):
                if self.store.pop((service, user), None) is None:
                    raise keyring.errors.PasswordDeleteError(user)

        previous = keyring.get_keyring()
        monkeypatch.setattr(sys, "platform", "linux")  # skip explicit OS backend
        keyring.set_keyring(Memory())
        try:
            store = secret_store.KeyringSecretStore()
            store.set("openai", "sk-9")
            assert store.get("openai") == "sk-9"
            store.delete("openai")
            store.delete("openai")  # deleting twice is fine
            assert store.get("openai") is None
            assert Memory.store == {}
        finally:
            keyring.set_keyring(previous)
