"""Transcribe-HTR desktop launcher.

Starts the FastAPI backend on a random 127.0.0.1 port inside this process and
shows the React UI in a native window (WebView2 on Windows, WKWebView on
macOS) via pywebview. If no webview is available it opens the default browser
instead.

    python desktop/launcher.py               # the app
    python desktop/launcher.py --smoke-test  # no window: start, check, exit 0/1
    python desktop/launcher.py --self-check  # no window: check bundled deps
    python desktop/launcher.py --window-check  # open, verify the UI loaded, close
    python desktop/launcher.py --version
    python desktop/launcher.py --forget-keys   # delete remembered API keys (uninstaller)

Desktop behaviour is switched on through environment variables that the
backend already understands (set here, before the backend is imported):

    TRANSCRIBE_HTR_PERSISTENT_WORKSPACE  one workspace in the user's data dir
    TRANSCRIBE_HTR_LAUNCH_TOKEN          per-launch secret; locks the API
    MPLCONFIGDIR                         matplotlib cache in the user cache dir
"""

import http.cookiejar
import json
import logging
import multiprocessing
import os
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

APP_TITLE = "Transcribe-HTR"
HEALTH_TIMEOUT_S = 90  # first launch can be slow while antivirus scans the files
BROWSER_IDLE_EXIT_S = 120  # browser fallback: quit when the page stops pinging

log = logging.getLogger("transcribe_htr.launcher")

LOADING_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
font-family:system-ui,-apple-system,"Segoe UI",sans-serif;background:#fafafa;color:#31333f}
.box{text-align:center}.spin{width:36px;height:36px;margin:0 auto 16px;border:4px solid #ddd;
border-top-color:#ff4b4b;border-radius:50%;animation:s 1s linear infinite}
@keyframes s{to{transform:rotate(360deg)}}p{margin:4px 0}small{color:#808495}
@media (prefers-color-scheme:dark){body{background:#0e1117;color:#fafafa}}
</style></head><body><div class="box"><div class="spin"></div>
<p><b>Starting Transcribe-HTR…</b></p><small>The first start can take a little longer.</small>
</div></body></html>"""

ERROR_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;padding:40px;color:#31333f}
code{background:#f0f2f6;padding:2px 6px;border-radius:4px}</style></head><body>
<h2>Transcribe-HTR could not start</h2><p>The background service did not respond.</p>
<p>Please close this window and try again. If it keeps happening, send the log file in
<code>{log_dir}</code> to your support contact.</p></body></html>"""


# ── Process setup ────────────────────────────────────────────────────────────


def _resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def _setup_import_paths() -> None:
    root = _resource_root()
    # Repo root for the `desktop` package (from source), then the backend's
    # flat-import directories (see CLAUDE.md "Import layout").
    for p in (root, root / "backend", root / "backend" / "core"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))


def _load_build_info() -> dict:
    """build_info.json, written by scripts/build_desktop.py and bundled with
    the app: version, commit, whether it was signed, and environment defaults
    chosen at build time (e.g. a signed macOS build uses the Keychain). An
    explicit environment variable still wins. Absent when run from source."""
    try:
        info = json.loads((_resource_root() / "build_info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    for key, value in (info.get("defaults") or {}).items():
        os.environ.setdefault(key, str(value))
    return info


def _setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "launcher.log"
    # A windowed (no console) build has no stdout/stderr; anything that writes
    # to them (uvicorn, print, warnings) would crash.
    if sys.stdout is None or sys.stderr is None:
        stream = open(log_file, "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or stream
        sys.stderr = sys.stderr or stream
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _configure_environment(token: str, cache_dir: Path) -> None:
    os.environ["TRANSCRIBE_HTR_PERSISTENT_WORKSPACE"] = "true"
    os.environ["TRANSCRIBE_HTR_LAUNCH_TOKEN"] = token
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir / "matplotlib"))
    # Never pick up a developer's .env or a stray SESSION_SECRET_KEY: the
    # desktop app has no use for either.
    os.environ.pop("SESSION_SECRET_KEY", None)


def _use_system_certificates() -> None:
    # University networks often inspect TLS with their own root certificate,
    # which lives in the OS trust store, not in certifi's bundle.
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception as e:  # optional: certifi still works on ordinary networks
        log.info("truststore not used: %s", e)


# ── Server ───────────────────────────────────────────────────────────────────


class Server:
    def __init__(self, app):
        import uvicorn

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))  # port 0: the OS picks a free port
        self.port = self._sock.getsockname()[1]
        config = uvicorn.Config(app, log_config=None, access_log=False, workers=1)
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(
            target=self._server.run, kwargs={"sockets": [self._sock]}, daemon=True
        )

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        self._thread.start()

    def wait_healthy(self, timeout: float = HEALTH_TIMEOUT_S) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{self.base_url}/api/health", timeout=2) as r:
                    if r.status == 200:
                        return True
            except OSError:
                pass
            time.sleep(0.2)
        return False

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)


def _add_shell_routes(app, state: dict) -> None:
    """Routes only the desktop shell needs. POST, so the SPA's GET catch-all
    (registered earlier in main.py) cannot shadow them; behind the launch
    token like everything else."""

    @app.post("/api/desktop/focus", include_in_schema=False)
    def focus():
        window = state.get("window")
        if window is not None:
            window.restore()
            window.show()
            window.on_top = True  # bring to front, then behave normally
            window.on_top = False
        return {"ok": window is not None}

    @app.post("/api/desktop/heartbeat", include_in_schema=False)
    def heartbeat():
        state["last_heartbeat"] = time.monotonic()
        return {"ok": True}


# ── Window ───────────────────────────────────────────────────────────────────


def _webview2_available() -> bool:
    """Windows: is the Evergreen WebView2 runtime installed (machine or user)?"""
    if sys.platform != "win32":
        return True
    import winreg

    client = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    for hive, key in (
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\{client}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\{client}"),
        (winreg.HKEY_CURRENT_USER, rf"Software\{client}"),
    ):
        try:
            with winreg.OpenKey(hive, key) as k:
                version, _ = winreg.QueryValueEx(k, "pv")
                if version and version != "0.0.0.0":
                    return True
        except OSError:
            continue
    return False


def _check_window(window, bridge, result: dict) -> None:
    """--window-check: confirm the SPA rendered and authenticated, then close."""
    deadline = time.monotonic() + 45
    rendered = False
    while time.monotonic() < deadline and not rendered:
        time.sleep(0.5)
        rendered = bool(window.evaluate_js(
            "!!document.querySelector('.tab-content') && !!window.pywebview"
        ))
    time.sleep(2)  # let startup requests (session, app-info, keys) finish
    result.update(
        rendered=rendered,
        backend_unreachable_banner=bool(window.evaluate_js(
            "document.body.innerText.includes('Cannot reach')"
        )),
        bridge=bool(window.evaluate_js("typeof window.pywebview.api.save_from_api === 'function'")),
        # Desktop-only UI appears once the app knows it is in the desktop shell.
        # textContent, not innerText: the card title is uppercased by CSS.
        desktop_ui=bool(window.evaluate_js("document.body.textContent.includes('Your data on this computer')")),
        engine=window.evaluate_js("navigator.userAgent"),
    )
    window.evaluate_js("window.pywebview.api.set_busy(true)")
    time.sleep(0.5)
    result["busy_flag_reaches_python"] = bridge._is_busy()
    bridge.set_busy(False)  # let the window close without asking
    result["ok"] = (
        result["rendered"] and result["bridge"] and result["desktop_ui"]
        and result["busy_flag_reaches_python"] and not result["backend_unreachable_banner"]
    )
    print("WINDOWCHECK " + json.dumps(result), flush=True)
    window.destroy()


def _run_window(server: Server, auth_url: str, bridge, state: dict, log_dir: Path, check: bool = False) -> dict:
    import webview

    window = webview.create_window(
        APP_TITLE, html=LOADING_HTML, js_api=bridge, width=1320, height=880, min_size=(900, 600)
    )
    bridge._attach(window)
    state["window"] = window

    def on_closing():
        if not bridge._is_busy():
            return True
        return window.create_confirmation_dialog(
            "Quit Transcribe-HTR?",
            "A transcription batch is still running. If you quit now, it stops after the "
            "current document. Quit anyway?",
        )

    window.events.closing += on_closing

    result: dict = {}

    def after_start():
        if server.wait_healthy():
            window.load_url(auth_url)
            if check:
                _check_window(window, bridge, result)
        else:
            window.load_html(ERROR_HTML.replace("{log_dir}", str(log_dir)))
            if check:
                window.destroy()

    webview.start(after_start, gui="edgechromium" if sys.platform == "win32" else None)
    return result


def _run_browser(server: Server, auth_url: str, state: dict) -> None:
    """Fallback without a webview: use the default browser and quit once the
    page has stopped sending heartbeats (the tab was closed)."""
    if not server.wait_healthy():
        return
    state["last_heartbeat"] = time.monotonic()
    webbrowser.open(auth_url)
    while time.monotonic() - state["last_heartbeat"] < BROWSER_IDLE_EXIT_S:
        time.sleep(5)


def _focus_running_instance(info: dict) -> bool:
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{info['port']}/api/desktop/focus",
            data=b"{}",
            method="POST",
            headers={"X-HTR-Token": info["token"], "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except (OSError, KeyError, TypeError):
        return False


# ── Check modes (no window) ──────────────────────────────────────────────────


def _smoke_test(server: Server, token: str) -> int:
    """End-to-end check of a built app: the API is locked, the auth flow
    unlocks it, the SPA is served and the persistent session works."""
    result = {"healthy": server.wait_healthy()}
    if result["healthy"]:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        base = server.base_url

        def status(url, method="GET"):
            try:
                with opener.open(urllib.request.Request(base + url, method=method, data=b"" if method == "POST" else None), timeout=10) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                return e.code, b""

        result["locked_without_token"] = status("/api/profiles")[0] == 403
        result["auth"] = status(f"/api/desktop/auth?token={token}")[0] == 200
        code, html = status("/")
        result["spa"] = code == 200 and b'id="root"' in html
        code, body = status("/api/session/init", "POST")
        result["session"] = json.loads(body).get("session_id") if code == 200 else code
        code, body = status("/api/app-info")
        result["app_info"] = json.loads(body) if code == 200 else code
        result["matplotlib_at_start"] = "matplotlib" in sys.modules
    ok = (
        result["healthy"]
        and result.get("locked_without_token")
        and result.get("auth")
        and result.get("spa")
        and result.get("session") == "desktop"
        and isinstance(result.get("app_info"), dict)
        and result["app_info"].get("desktop") is True
    )
    print("SMOKE " + json.dumps(result), flush=True)
    return 0 if ok else 1


def _self_check() -> int:
    """Exercise lazily imported dependencies that the smoke test never loads."""
    import io

    checks = {}

    def run(name, fn):
        try:
            checks[name] = fn() or "ok"
        except Exception as e:  # noqa: BLE001 - diagnostics
            checks[name] = f"FAIL {type(e).__name__}: {e}"

    def tls():
        import ssl

        import certifi

        # With truststore injected this is the OS trust store; otherwise certifi.
        ctx = ssl.create_default_context(cafile=certifi.where())
        return f"ok ({type(ctx).__module__}.{type(ctx).__name__})"

    def providers():
        import anthropic  # noqa: F401
        import openai  # noqa: F401
        from google import genai  # noqa: F401

    def figure():
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots()
        ax.plot([0, 1])
        buf = io.BytesIO()
        fig.savefig(buf, format="png")

    def docx():
        from docx import Document

        Document().save(io.BytesIO())

    def keyring_backend():
        from secret_store import get_secret_store

        return f"ok ({get_secret_store().name})"

    for name, fn in (("tls", tls), ("providers", providers), ("figure", figure), ("docx", docx), ("secret_store", keyring_backend)):
        run(name, fn)
    print("SELFCHECK " + json.dumps(checks), flush=True)
    return 0 if all(str(v).startswith("ok") for v in checks.values()) else 1


# ── Entry point ──────────────────────────────────────────────────────────────


def main(argv) -> int:
    _setup_import_paths()
    build_info = _load_build_info()
    from app_paths import user_cache_dir, user_data_dir, user_log_dir, user_workspace_dir

    _setup_logging(user_log_dir())
    if "--version" in argv:
        from app_version import APP_VERSION

        print(APP_VERSION)
        return 0
    if "--forget-keys" in argv:
        # Used by the Windows uninstaller when the user removes their data.
        from secret_store import PROVIDERS, get_secret_store

        store = get_secret_store()
        for provider in PROVIDERS:
            store.delete(provider)
        log.info("Remembered API keys removed (%s).", store.name)
        return 0

    window_check = "--window-check" in argv
    check_mode = window_check or "--smoke-test" in argv or "--self-check" in argv
    from desktop.single_instance import SingleInstance

    lock = SingleInstance(user_data_dir() / "instance.lock")
    if not check_mode and not lock.acquire():
        info = lock.running_instance()
        log.info("Already running; focusing the existing window.")
        if info and _focus_running_instance(info):
            return 0
        log.warning("Another instance holds the lock but did not respond.")
        return 1

    token = secrets.token_urlsafe(32)
    _configure_environment(token, user_cache_dir())
    _use_system_certificates()

    if "--self-check" in argv:
        return _self_check()

    import main as backend  # noqa: E402 - after the environment is configured
    from app_version import APP_VERSION
    from desktop.bridge import Bridge

    state: dict = {}
    _add_shell_routes(backend.app, state)
    server = Server(backend.app)
    server.start()
    log.info("Transcribe-HTR %s serving on port %d", APP_VERSION, server.port)

    try:
        if "--smoke-test" in argv:
            return _smoke_test(server, token)

        if not check_mode:  # check runs never hand over to / take over from the app
            lock.publish(server.port, token)
        auth_url = f"{server.base_url}/api/desktop/auth?token={token}"
        bridge = Bridge(
            server.port,
            token,
            folders={"data": user_data_dir(), "workspace": user_workspace_dir(), "logs": user_log_dir()},
            diagnostics=lambda: {
                "version": APP_VERSION,
                "build": f"{build_info.get('commit', 'source')} {build_info.get('built', '')}".strip(),
                "signed": build_info.get("signed", False),
                "data folder": user_data_dir(),
                "log folder": user_log_dir(),
                "frozen": bool(getattr(sys, "frozen", False)),
            },
        )
        if window_check:
            return 0 if _run_window(server, auth_url, bridge, state, user_log_dir(), check=True).get("ok") else 1
        if _webview2_available():
            try:
                _run_window(server, auth_url, bridge, state, user_log_dir())
                return 0
            except Exception:  # noqa: BLE001 - fall back rather than fail to start
                log.exception("Native window failed; falling back to the browser.")
        _run_browser(server, auth_url, state)
        return 0
    finally:
        server.stop()
        lock.release()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main(sys.argv[1:]))
