"""Desktop shell: launcher smoke test, single-instance lock, download bridge.

None of these open a window; --window-check covers that on machines with a
display (and in the release workflow).
"""

import http.server
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from desktop.bridge import Bridge, _filename
from desktop.single_instance import SingleInstance

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def user_dirs(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    return {
        **os.environ,
        "FRONTEND_DIST": str(dist),
        "TRANSCRIBE_HTR_DATA_DIR": str(tmp_path / "data"),
        "TRANSCRIBE_HTR_LOG_DIR": str(tmp_path / "logs"),
        "TRANSCRIBE_HTR_CACHE_DIR": str(tmp_path / "cache"),
        "TRANSCRIBE_HTR_SECRET_BACKEND": "file",
    }


def _launch(args, env):
    return subprocess.run(
        [sys.executable, str(REPO / "desktop" / "launcher.py"), *args],
        cwd=str(Path(env["TRANSCRIBE_HTR_DATA_DIR"]).parent),  # not the repo
        env=env, capture_output=True, text=True, timeout=180,
    )


class TestLauncher:
    def test_smoke_test_passes(self, user_dirs):
        out = _launch(["--smoke-test"], user_dirs)
        assert out.returncode == 0, out.stdout + out.stderr
        assert '"session": "desktop"' in out.stdout
        assert '"locked_without_token": true' in out.stdout

    def test_version(self, user_dirs):
        out = _launch(["--version"], user_dirs)
        assert out.stdout.strip() == (REPO / "VERSION").read_text(encoding="utf-8").strip()


class TestSingleInstance:
    def test_second_holder_is_refused_until_release(self, tmp_path):
        first, second = SingleInstance(tmp_path / "i.lock"), SingleInstance(tmp_path / "i.lock")
        assert first.acquire()
        assert not second.acquire()
        first.release()
        assert second.acquire()
        second.release()

    def test_publish_and_read_back(self, tmp_path):
        lock = SingleInstance(tmp_path / "i.lock")
        assert lock.acquire()
        lock.publish(1234, "tok")
        assert SingleInstance(tmp_path / "i.lock").running_instance()["port"] == 1234
        lock.release()
        assert SingleInstance(tmp_path / "i.lock").running_instance() is None

    def test_locks_are_per_user_directory(self, tmp_path):
        alice, bob = SingleInstance(tmp_path / "alice" / "i.lock"), SingleInstance(tmp_path / "bob" / "i.lock")
        assert alice.acquire() and bob.acquire()
        alice.release()
        bob.release()


class _ExportHandler(http.server.BaseHTTPRequestHandler):
    seen_tokens = []

    def _reply(self):
        self.seen_tokens.append(self.headers.get("X-HTR-Token"))
        body = b"PK-fake-zip"
        self.send_response(200)
        self.send_header("Content-Disposition", 'attachment; filename="../../evil/report.zip"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_GET = _reply

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self._reply()

    def log_message(self, *args):
        pass


@pytest.fixture
def export_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _ExportHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


def _bridge(port, ask):
    return Bridge(port, "tok", folders={}, diagnostics=dict, ask_save_path=ask)


class TestBridge:
    def test_saves_where_the_user_chose(self, export_server, tmp_path):
        target = tmp_path / "chosen.zip"
        suggested = []
        bridge = _bridge(export_server, lambda name: suggested.append(name) or str(target))

        result = bridge.save_from_api({"method": "POST", "path": "/api/consistency/export", "body": {"root": "a"}})

        assert result == {"status": "saved", "name": "chosen.zip", "path": str(target)}
        assert target.read_bytes() == b"PK-fake-zip"
        assert suggested == ["report.zip"]  # directory parts of the header dropped
        assert _ExportHandler.seen_tokens[-1] == "tok"

    def test_cancel_leaves_nothing_behind(self, export_server, tmp_path, monkeypatch):
        monkeypatch.setenv("TMP", str(tmp_path))
        monkeypatch.setenv("TEMP", str(tmp_path))
        monkeypatch.setenv("TMPDIR", str(tmp_path))
        import tempfile

        monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
        result = _bridge(export_server, lambda name: None).save_from_api({"path": "/api/export", "params": {"format": "zip"}})
        assert result == {"status": "cancelled"}
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize(
        "request_",
        [
            {"method": "GET", "path": "/api/settings/keys"},
            {"method": "GET", "path": "http://example.com/x"},
            {"method": "DELETE", "path": "/api/export"},
            {"method": "GET", "path": "/api/consistency/export"},
        ],
    )
    def test_only_allowlisted_downloads(self, request_):
        result = _bridge(1, lambda n: "x").save_from_api(request_)
        assert result["status"] == "error"

    def test_filename_never_contains_directories(self):
        assert _filename('attachment; filename="..\\..\\x.docx"', "f") == "x.docx"
        assert _filename('attachment; filename="/etc/passwd"', "f") == "passwd"
        assert _filename('attachment; filename=".."', "f") == "export"
        assert _filename(None, "fallback.json") == "fallback.json"

    def test_unknown_folder(self):
        assert _bridge(1, None).open_folder("system32") is False
