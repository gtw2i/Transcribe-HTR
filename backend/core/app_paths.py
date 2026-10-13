# app_paths.py
"""
Single source of truth for every filesystem location the backend uses.

There are two kinds of location:

* Resources: read-only files shipped with the app (bundled profiles, export
  templates, the entity schema, the built frontend). They resolve against the
  source tree, or against the PyInstaller bundle when the app is frozen. The
  bundle mirrors the repo layout (backend/profiles, backend/templates,
  entity-data, frontend/dist), so one set of relative paths serves both.

* User locations: writable, per-user, local (non-roaming) directories for
  data, logs and cache. They come from platformdirs, so on a shared computer
  every account gets its own private copy:

      Windows  %LOCALAPPDATA%\\Transcribe-HTR\\{,Logs,Cache}
      macOS    ~/Library/{Application Support,Logs,Caches}/Transcribe-HTR
      Linux    ~/.local/share, ~/.local/state, ~/.cache (XDG)

Every location can be overridden with an environment variable, so tests,
development and the desktop launcher can redirect it. Nothing here creates
directories; callers create what they write to.
"""

import os
import sys
from pathlib import Path
from typing import Optional

import platformdirs

APP_NAME = "Transcribe-HTR"

# Environment overrides
ENV_DATA_DIR = "TRANSCRIBE_HTR_DATA_DIR"
ENV_LOG_DIR = "TRANSCRIBE_HTR_LOG_DIR"
ENV_CACHE_DIR = "TRANSCRIBE_HTR_CACHE_DIR"
ENV_FRONTEND_DIST = "FRONTEND_DIST"


def _env_path(name: str) -> Optional[Path]:
    value = os.getenv(name, "").strip()
    return Path(value).expanduser() if value else None


# =========================
# RESOURCES (read-only)
# =========================


def is_frozen() -> bool:
    """True when running from a PyInstaller (or similar) bundle."""
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Repo root from a source checkout; the bundle root when frozen."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def backend_dir() -> Path:
    return resource_root() / "backend"


def bundled_profiles_dir() -> Path:
    """Profiles shipped with the app. Always read-only."""
    return backend_dir() / "profiles"


def templates_dir() -> Path:
    return backend_dir() / "templates"


def entity_schema_path() -> Path:
    return resource_root() / "entity-data" / "entity_schema_v2.json"


def frontend_dist_dir() -> Path:
    return _env_path(ENV_FRONTEND_DIST) or resource_root() / "frontend" / "dist"


# =========================
# USER LOCATIONS (writable, per user)
# =========================


def user_data_dir() -> Path:
    return _env_path(ENV_DATA_DIR) or platformdirs.user_data_path(
        APP_NAME, appauthor=False, roaming=False
    )


def user_log_dir() -> Path:
    return _env_path(ENV_LOG_DIR) or platformdirs.user_log_path(
        APP_NAME, appauthor=False
    )


def user_cache_dir() -> Path:
    return _env_path(ENV_CACHE_DIR) or platformdirs.user_cache_path(
        APP_NAME, appauthor=False
    )


def user_profiles_dir() -> Path:
    """Profiles the user creates. Private to the current account."""
    return user_data_dir() / "profiles"


def tts_cache_dir() -> Path:
    return user_cache_dir() / "audio"
