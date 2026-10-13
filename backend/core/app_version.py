# app_version.py
"""
The application version.

Single source of truth: <repo>/VERSION, which is also bundled into the desktop
app. pyproject.toml, frontend/package.json and CITATION.cff carry copies that
tests/test_hygiene/test_version_consistency.py keeps in step.
"""

from app_paths import resource_root


def _read_version() -> str:
    try:
        return (resource_root() / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0+unknown"


APP_VERSION = _read_version()
