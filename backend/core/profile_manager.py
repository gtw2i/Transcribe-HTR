# profile_manager.py
"""
Manages YAML-based transcription profiles.

A profile is a YAML file that contains prompts and settings for a specific
transcription domain (e.g. Civil War HTR). Profiles come from two layers:

  1. Bundled profiles (config.PROFILES_DIR): shipped with the app, always
     read-only, and reported as templates so the UI offers "clone" instead
     of "edit". They update with the app.
  2. User profiles (app_paths.user_profiles_dir()): created by the current
     user, private to their account, writable.

A user profile can never shadow a bundled one: bundled names win on lookup
and are refused on save.

Priority for verbalize_enabled:
  1. Profile field `verbalize_enabled` (if present)
  2. VERBALIZE_ENABLED env var / config.py fallback
"""

import re
from pathlib import Path
from typing import Optional

import yaml

from app_paths import user_profiles_dir
from config import ACTIVE_PROFILE, PROFILES_DIR, VERBALIZE_ENABLED

# Slugs become filenames, so they are restricted to a safe alphabet. This is
# what keeps a request like slug="../../x" from escaping the profile dirs.
_SLUG_RE = re.compile(r"^[a-z0-9_-]{1,64}$")


class ProfileError(Exception):
    """Base class for profile save/delete refusals."""


class InvalidSlugError(ProfileError, ValueError):
    pass


class ReadOnlyProfileError(ProfileError, PermissionError):
    pass


def is_valid_slug(slug: str) -> bool:
    return bool(isinstance(slug, str) and _SLUG_RE.match(slug))


def _bundled_path(slug: str) -> Path:
    return Path(PROFILES_DIR) / f"{slug}.yaml"


def _user_path(slug: str) -> Path:
    return user_profiles_dir() / f"{slug}.yaml"


def is_bundled(slug: str) -> bool:
    return is_valid_slug(slug) and _bundled_path(slug).exists()


def _find_profile_path(slug: str) -> Optional[Path]:
    if not is_valid_slug(slug):
        return None
    for path in (_bundled_path(slug), _user_path(slug)):
        if path.exists():
            return path
    return None

# Required fields every profile must have
_REQUIRED_FIELDS = [
    "name",
    "system_prompt",
    "transcription_prompt",
    "harmonization_system_prompt",
    "harmonization_prompt",
]


def list_profiles() -> list[str]:
    """Return sorted profile stems from both the bundled and user layers."""
    slugs = set()
    for directory in (Path(PROFILES_DIR), user_profiles_dir()):
        try:
            slugs.update(p.stem for p in directory.glob("*.yaml") if is_valid_slug(p.stem))
        except OSError:
            continue
    return sorted(slugs) or [ACTIVE_PROFILE]


def load_profile(profile_name: str) -> Optional[dict]:
    """
    Load and validate a profile by stem name (e.g. 'civil_war_htr').
    Returns the profile dict on success, or None if the file is missing or invalid.
    Bundled profiles always come back with template=True.
    """
    path = _find_profile_path(profile_name)
    if path is None:
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError:
        return None

    if not isinstance(data, dict):
        return None

    # Backward compat: merge old harmonization_intro/closing into harmonization_prompt
    if "harmonization_prompt" not in data:
        intro = (data.get("harmonization_intro") or "").rstrip("\n")
        closing = (data.get("harmonization_closing") or "").strip()
        data["harmonization_prompt"] = intro + "\n\n{}\n\n" + closing

    # Validate required fields
    for field in _REQUIRED_FIELDS:
        if field not in data or not data[field]:
            return None

    if path.parent == Path(PROFILES_DIR):
        data["template"] = True

    return data


def get_active_profile(profile_name: Optional[str] = None) -> dict:
    """
    Load the requested profile, falling back to ACTIVE_PROFILE, then to
    inline hardcoded defaults if no profile files are found.

    Always returns a valid dict with all required fields populated.
    """
    name = profile_name or ACTIVE_PROFILE

    profile = load_profile(name)
    if profile is None and name != ACTIVE_PROFILE:
        # Try the configured default before falling back to hardcoded
        profile = load_profile(ACTIVE_PROFILE)

    if profile is None:
        # Last resort: inline fallback prompts (equivalent to the old civil_war_htr template)
        profile = {
            "name": "Default (fallback)",
            "description": "Hardcoded fallback — profile file not found",
            "system_prompt": "Your job is to perform HTR/OCR, i.e., transcribe images of documents.",
            "transcription_prompt": (
                "You are presented with an image of a handwritten document. "
                "Your task is to produce an accurate transcription of the text it contains.\n\n"
                "{}\n\nBegin your transcription below:"
            ),
            "harmonization_system_prompt": (
                "You are an expert historical document transcription specialist. "
                "Your task is to create a single, accurate transcription by harmonizing "
                "multiple imperfect transcriptions of the same document."
            ),
            "harmonization_prompt": (
                "Below are multiple transcriptions of the same document. "
                "Please create a single, harmonized transcription:\n\n"
                "{}\n\n"
                "Provide a single harmonized transcription combining the best elements. "
                "Output only the final transcription without any commentary."
            ),
        }

    return profile


def is_template(profile_name: Optional[str] = None) -> bool:
    """Return True if the profile carries template: true in its YAML."""
    profile = load_profile(profile_name or ACTIVE_PROFILE)
    return bool(profile and profile.get("template", False))


def profile_slug_exists(slug: str) -> bool:
    """Return True if a .yaml file already exists for this slug in either layer."""
    return _find_profile_path(slug) is not None


def make_slug(name: str) -> str:
    """Convert a display name to a safe YAML filename stem."""
    from slugify import slugify  # python-slugify (already in requirements.txt)
    result = slugify(name, separator="_")
    return result or "profile"


def _check_writable(slug: str) -> None:
    if not is_valid_slug(slug):
        raise InvalidSlugError(
            f"Invalid profile id '{slug}': use 1-64 lowercase letters, digits, '-' or '_'."
        )
    if is_bundled(slug):
        raise ReadOnlyProfileError(f"'{slug}' is a built-in profile and is read-only.")


def save_profile(slug: str, data: dict) -> None:
    """Write a user profile to <user profiles dir>/<slug>.yaml."""
    _check_writable(slug)
    data = {k: v for k, v in data.items() if k != "template"}
    path = _user_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def delete_profile(slug: str) -> bool:
    """Delete a user profile. Returns True if the file existed."""
    _check_writable(slug)
    path = _user_path(slug)
    if path.exists():
        path.unlink()
        return True
    return False


def get_verbalize_enabled(profile_name: Optional[str] = None) -> bool:
    """
    Return the effective verbalize_enabled value for the given profile.

    Priority:
      1. Profile field `verbalize_enabled` (if present and is a bool)
      2. VERBALIZE_ENABLED from config.py (env var fallback)
    """
    profile = get_active_profile(profile_name)
    if "verbalize_enabled" in profile and isinstance(profile["verbalize_enabled"], bool):
        return profile["verbalize_enabled"]
    return VERBALIZE_ENABLED
