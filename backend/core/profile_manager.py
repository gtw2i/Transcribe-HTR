# profile_manager.py
"""
Manages YAML-based transcription profiles.

A profile is a YAML file in the profiles/ directory that contains prompts
and settings for a specific transcription domain (e.g. Civil War HTR).

Priority for verbalize_enabled:
  1. Profile field `verbalize_enabled` (if present)
  2. VERBALIZE_ENABLED env var / config.py fallback
"""

from pathlib import Path
from typing import Optional

import yaml

from config import ACTIVE_PROFILE, PROFILES_DIR, VERBALIZE_ENABLED

# Required fields every profile must have
_REQUIRED_FIELDS = [
    "name",
    "system_prompt",
    "transcription_prompt",
    "harmonization_system_prompt",
    "harmonization_prompt",
]


def list_profiles() -> list[str]:
    """Return sorted list of profile stems (filenames without .yaml) found in PROFILES_DIR."""
    try:
        return sorted(p.stem for p in Path(PROFILES_DIR).glob("*.yaml"))
    except Exception:
        return [ACTIVE_PROFILE]


def load_profile(profile_name: str) -> Optional[dict]:
    """
    Load and validate a profile by stem name (e.g. 'civil_war_htr').
    Returns the profile dict on success, or None if the file is missing or invalid.
    """
    path = Path(PROFILES_DIR) / f"{profile_name}.yaml"
    if not path.exists():
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
    """Return True if a .yaml file already exists for this slug."""
    return (Path(PROFILES_DIR) / f"{slug}.yaml").exists()


def make_slug(name: str) -> str:
    """Convert a display name to a safe YAML filename stem."""
    from slugify import slugify  # python-slugify (already in requirements.txt)
    result = slugify(name, separator="_")
    return result or "profile"


def save_profile(slug: str, data: dict) -> None:
    """Write profile data to profiles/<slug>.yaml."""
    path = Path(PROFILES_DIR) / f"{slug}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def delete_profile(slug: str) -> bool:
    """Delete profiles/<slug>.yaml. Returns True if the file existed."""
    path = Path(PROFILES_DIR) / f"{slug}.yaml"
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
