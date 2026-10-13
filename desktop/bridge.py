"""Python functions the desktop window can call as window.pywebview.api.*.

pywebview exposes every public method of this object to JavaScript, so the
surface is deliberately small, and private state lives in underscore
attributes (which pywebview does not expose).
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Optional

# The only responses the window may ask Python to save. Anything else is
# refused, so the bridge cannot be used to fetch arbitrary URLs.
ALLOWED_DOWNLOADS = frozenset({("GET", "/api/export"), ("POST", "/api/consistency/export")})


def _filename(disposition: Optional[str], fallback: str) -> str:
    match = re.search(r'filename="?([^";]+)"?', disposition or "")
    # Never trust a path from a header: keep the bare file name only, treating
    # both / and \ as separators whatever the OS.
    name = re.split(r"[\\/]", match.group(1) if match else fallback)[-1].strip(". ")
    return name or "export"


def _open_in_file_manager(path: Path, select: bool = False) -> None:
    if sys.platform == "win32":
        if select:
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            os.startfile(str(path))  # noqa: S606 - opening a folder the app owns
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if select else ["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path.parent if select else path)])


class Bridge:
    def __init__(
        self,
        port: int,
        token: str,
        folders: Dict[str, Path],
        diagnostics: Callable[[], dict],
        ask_save_path: Optional[Callable[[str], Optional[str]]] = None,
    ):
        self._base = f"http://127.0.0.1:{port}"
        self._token = token
        self._folders = folders
        self._diagnostics = diagnostics
        self._ask_save_path = ask_save_path or self._native_save_dialog
        self._window = None
        self._busy = False

    # ── Not exposed (underscore) ────────────────────────────────────────────
    def _attach(self, window) -> None:
        self._window = window

    def _is_busy(self) -> bool:
        return self._busy

    def _native_save_dialog(self, suggested: str) -> Optional[str]:
        import webview

        documents = Path.home() / "Documents"
        result = self._window.create_file_dialog(
            webview.FileDialog.SAVE,
            directory=str(documents if documents.is_dir() else Path.home()),
            save_filename=suggested,
        )
        if not result:
            return None
        return result[0] if isinstance(result, (list, tuple)) else str(result)

    # ── Exposed to JavaScript ───────────────────────────────────────────────
    def save_from_api(self, request: dict) -> dict:
        """Fetch an export from the local server and save it where the user picks."""
        method = str(request.get("method", "GET")).upper()
        path = str(request.get("path", ""))
        if (method, path) not in ALLOWED_DOWNLOADS:
            return {"status": "error", "message": "This download is not allowed."}

        query = urllib.parse.urlencode(request.get("params") or {})
        body = request.get("body")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"X-HTR-Token": self._token}
        if data is not None:
            headers["Content-Type"] = "application/json"
        url = f"{self._base}{path}" + (f"?{query}" if query else "")

        tmp = None
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=600) as resp:
                name = _filename(resp.headers.get("Content-Disposition"), request.get("fallback_name") or "export")
                fd, tmp = tempfile.mkstemp(prefix="htr-export-", suffix=Path(name).suffix)
                with os.fdopen(fd, "wb") as out:
                    shutil.copyfileobj(resp, out)
            target = self._ask_save_path(name)
            if not target:
                return {"status": "cancelled"}
            shutil.move(tmp, target)
            tmp = None
            return {"status": "saved", "name": Path(target).name, "path": str(target)}
        except urllib.error.HTTPError as e:
            return {"status": "error", "message": f"The export failed (HTTP {e.code})."}
        except OSError as e:
            return {"status": "error", "message": f"Could not save the file: {e}"}
        finally:
            if tmp:
                Path(tmp).unlink(missing_ok=True)

    def reveal(self, path: str) -> bool:
        """Show a saved file in Explorer / Finder."""
        p = Path(path)
        if not p.exists():
            return False
        _open_in_file_manager(p, select=True)
        return True

    def open_folder(self, kind: str) -> bool:
        """Open one of the app's own folders: 'data', 'workspace' or 'logs'."""
        folder = self._folders.get(kind)
        if folder is None:
            return False
        folder.mkdir(parents=True, exist_ok=True)
        _open_in_file_manager(folder)
        return True

    def diagnostics(self) -> str:
        """Plain-text summary for support requests (contains no keys)."""
        info = {
            **self._diagnostics(),
            "os": f"{platform.system()} {platform.release()} ({platform.machine()})",
            "python": platform.python_version(),
        }
        return "\n".join(f"{k}: {v}" for k, v in info.items())

    def set_busy(self, busy: bool) -> None:
        """The window reports a running batch, so quitting can ask first."""
        self._busy = bool(busy)
