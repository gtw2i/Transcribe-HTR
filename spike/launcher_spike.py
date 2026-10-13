"""THROWAWAY Phase 0.5 packaging spike — not production code.

Proves that the real backend + built SPA can be frozen with PyInstaller and
shown in a pywebview window on Windows (WebView2) and macOS (WKWebView).
Findings go into docs/development/DESKTOP_PLAN.md; the real launcher is
written in Phase 1.

    python spike/launcher_spike.py               # window
    python spike/launcher_spike.py --smoke-test  # no window; exit 0 if healthy
"""

import json
import multiprocessing
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

T0 = time.perf_counter()


def _fix_std_streams() -> None:
    # A windowed (no console) frozen app has sys.stdout/stderr = None; uvicorn
    # and print() would crash writing to them.
    if sys.stdout is None or sys.stderr is None:
        log_dir = Path(os.environ.get("TEMP", "/tmp"))
        stream = open(log_dir / "transcribe_htr_spike.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream


def _import_app():
    if getattr(sys, "frozen", False):
        root = Path(sys._MEIPASS)
    else:
        root = Path(__file__).resolve().parents[1]
        os.environ.setdefault("FRONTEND_DIST", str(root / "frontend" / "dist"))
    for p in (root / "backend", root / "backend" / "core"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import main  # noqa: E402

    return main.app


def _start_server(app):
    import uvicorn

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    config = uvicorn.Config(app, log_config=None, access_log=False, workers=1)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    return server, port


def _wait_healthy(port: int, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
                return r.status == 200
        except OSError:
            time.sleep(0.2)
    return False


def smoke_test() -> int:
    t_import = time.perf_counter()
    app = _import_app()
    import_s = time.perf_counter() - t_import
    server, port = _start_server(app)
    healthy = _wait_healthy(port)
    result = {"healthy": healthy, "import_s": round(import_s, 2),
              "ready_s": round(time.perf_counter() - T0, 2), "frozen": bool(getattr(sys, "frozen", False))}
    if healthy:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as r:
            result["index_has_root"] = b'id="root"' in r.read()
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/profiles", timeout=5) as r:
            result["profiles"] = [p["slug"] for p in json.load(r)]
        result["mpl_loaded_at_start"] = "matplotlib" in sys.modules
    print("SMOKE", json.dumps(result), flush=True)
    server.should_exit = True
    ok = healthy and result.get("index_has_root") and result.get("profiles")
    return 0 if ok else 1


def self_check() -> int:
    """Exercise lazily-imported dependencies that the smoke test never touches."""
    _import_app()
    results = {}

    def check(name, fn):
        try:
            results[name] = fn() or "ok"
        except Exception as e:  # noqa: BLE001 - spike diagnostics
            results[name] = f"FAIL {type(e).__name__}: {e}"

    def tls():
        import ssl

        import certifi

        ctx = ssl.create_default_context(cafile=certifi.where())
        return f"ok ({len(ctx.get_ca_certs())} CAs, {Path(certifi.where()).name})"

    def providers():
        import anthropic  # noqa: F401
        import openai  # noqa: F401
        from google import genai  # noqa: F401

        return "ok"

    def figure():
        import numpy as np

        from analysis import figures

        names = [n for n, f in vars(figures).items() if callable(f)]
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.imshow(np.eye(3))
        import io

        buf = io.BytesIO()
        fig.savefig(buf, format="png")
        return f"ok ({len(buf.getvalue())} bytes png; figures exports {len(names)} callables)"

    def docx():
        import io

        from docx import Document

        d = Document()
        d.add_paragraph("x")
        buf = io.BytesIO()
        d.save(buf)
        return f"ok ({len(buf.getvalue())} bytes docx)"

    def tiff():
        import io

        from PIL import Image

        from core.image_utils import resize_image_for_api

        buf = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buf, format="TIFF")
        return f"ok ({len(resize_image_for_api(buf.getvalue()))} bytes png)"

    for name, fn in [("tls", tls), ("providers", providers), ("figure", figure), ("docx", docx), ("tiff", tiff)]:
        check(name, fn)
    print("SELFCHECK", json.dumps(results), flush=True)
    return 0 if all(str(v).startswith("ok") for v in results.values()) else 1


def run_window(check: bool = False) -> int:
    import webview

    app = _import_app()
    server, port = _start_server(app)
    if not _wait_healthy(port):
        return 1
    print(f"ready in {time.perf_counter() - T0:.2f}s on port {port}", flush=True)
    window = webview.create_window("Transcribe-HTR (spike)", f"http://127.0.0.1:{port}/",
                                   width=1280, height=860)
    window.events.closed += lambda: setattr(server, "should_exit", True)
    outcome = {"ok": not check}

    def verify():
        # Runs on pywebview's worker thread once the GUI loop is up.
        import dependencies

        result = {}
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                n = window.evaluate_js("document.querySelector('#root')?.children.length || 0")
                if n:
                    break
                time.sleep(0.5)
            result["root_children"] = n
            result["title"] = window.evaluate_js("document.title")
            result["engine"] = window.evaluate_js("navigator.userAgent")
            # The SPA calls /api/session/init on load; seeing a session in the
            # in-process store proves cookies + same-origin XHR work.
            time.sleep(2)
            result["sessions"] = len(dependencies.get_session_store())
            result["secure_context"] = window.evaluate_js("window.isSecureContext")
            result["clipboard_api"] = window.evaluate_js("!!(navigator.clipboard && navigator.clipboard.writeText)")
            result["ready_s"] = round(time.perf_counter() - T0, 2)
            outcome["ok"] = bool(n) and result["sessions"] > 0
        except Exception as e:  # noqa: BLE001
            result["error"] = repr(e)
        print("WINDOWCHECK", json.dumps(result), flush=True)
        window.destroy()

    gui = "edgechromium" if sys.platform == "win32" else None
    webview.start(verify if check else None, gui=gui)
    return 0 if outcome["ok"] else 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _fix_std_streams()
    if "--smoke-test" in sys.argv:
        sys.exit(smoke_test())
    if "--self-check" in sys.argv:
        sys.exit(self_check())
    sys.exit(run_window(check="--window-check" in sys.argv))
