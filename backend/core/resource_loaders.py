"""Resource loaders — lazy-init API clients and profile proxy. No Streamlit."""

import os

# Module-level spaCy model cache
_SPACY_MODEL = None
_SPACY_LOADED = False


def get_client(api_key: str = None):
    """Lazy-load OpenAI client."""
    try:
        from openai import OpenAI
    except Exception as e:
        raise RuntimeError("OpenAI client is not available. Install/update the OpenAI SDK.") from e

    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("No API key provided. Please provide an API key.")
    return OpenAI(api_key=key)


def get_gemini_client(api_key: str = None):
    """Create and return a google.genai Client."""
    try:
        from google import genai
    except ImportError as e:
        raise RuntimeError("google-genai is not installed. Run: pip install google-genai") from e

    key = api_key or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("No Gemini API key provided.")
    return genai.Client(api_key=key)


def get_anthropic_client(api_key: str = None):
    """Create and return an Anthropic client."""
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("anthropic is not installed. Run: pip install anthropic") from e

    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("No Anthropic API key provided.")
    return anthropic.Anthropic(api_key=key)


def get_spacy_model():
    """Lazy-load a spaCy model, cached module-level."""
    global _SPACY_MODEL, _SPACY_LOADED
    if _SPACY_LOADED:
        return _SPACY_MODEL
    _SPACY_LOADED = True

    if os.getenv("SPACY_ENABLED", "true").strip().lower() in ("false", "0", "no"):
        return None
    try:
        import spacy
    except Exception:
        return None
    for name in ("en_core_web_trf", "en_core_web_sm"):
        try:
            _SPACY_MODEL = spacy.load(name)
            return _SPACY_MODEL
        except Exception:
            continue
    return None


class _ProfileProxy:
    """Proxy that reads prompts from a named profile (or the active default)."""

    _PROMPT_FIELDS = {
        "SYSTEM_PROMPT": "system_prompt",
        "TRANSCRIBE_PROMPT_TEMPLATE": "transcription_prompt",
        "HARMONIZE_SYSTEM_PROMPT": "harmonization_system_prompt",
        "HARMONIZE_USER_PROMPT": "harmonization_prompt",
    }

    def __init__(self, profile_name: str = None):
        self._profile_name = profile_name

    def __getattr__(self, name):
        if name in self._PROMPT_FIELDS:
            from profile_manager import get_active_profile
            profile = get_active_profile(self._profile_name)
            yaml_key = self._PROMPT_FIELDS[name]
            value = profile.get(yaml_key)
            if value:
                return value.rstrip("\n") if isinstance(value, str) else value
        raise AttributeError(f"_ProfileProxy has no attribute '{name}'")


def get_helpers(profile_name: str = None) -> _ProfileProxy:
    """Return a profile-aware proxy for transcription prompts."""
    return _ProfileProxy(profile_name)
