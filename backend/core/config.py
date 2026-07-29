# config.py — backend copy
# PROFILES_DIR points to backend/profiles/ (one level up from core/)
"""Configuration constants for the Transcribe backend."""

from pathlib import Path
import os as _os

# Image processing
SUPPORTED_IMAGE_FORMATS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]

# Transcription settings
TEMPERATURE = 1.0
MAX_COMPLETION_TOKENS = 40000
MAX_TOKENS_LEGACY = 40000
MAX_COMPLETION_TOKENS_HARMONIZATION = 40000
MAX_TOKENS_LEGACY_HARMONIZATION = 40000

# Anthropic requires a mandatory max_tokens (no automatic default like OpenAI/Gemini)
MAX_COMPLETION_TOKENS_ANTHROPIC = 8192
MAX_TOKENS_LEGACY_ANTHROPIC = 8192
MAX_COMPLETION_TOKENS_HARMONIZATION_ANTHROPIC = 8192

# Provider configuration
PROVIDER_OPENAI = "OpenAI"
PROVIDER_GEMINI = "Gemini"
PROVIDER_ANTHROPIC = "Anthropic"
PROVIDERS = [PROVIDER_OPENAI, PROVIDER_GEMINI, PROVIDER_ANTHROPIC]
PROVIDER_DEFAULT = PROVIDER_GEMINI

OPENAI_MODEL_LIST_FALLBACK = [
    "gpt-5.5", "gpt-5", "gpt-5.1", "gpt-5.2",
    "gpt-4o", "gpt-4o-mini",
]
GEMINI_MODEL_LIST_FALLBACK = [
    "gemini-3.1-pro-preview",
    "gemini-3-pro-preview", "gemini-3-flash-preview",
    "gemini-2.5-pro", "gemini-2.5-flash",
]
ANTHROPIC_MODEL_LIST_FALLBACK = [
    "claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5",
]

PROVIDER_MODEL_LISTS_FALLBACK = {
    PROVIDER_OPENAI: OPENAI_MODEL_LIST_FALLBACK,
    PROVIDER_GEMINI: GEMINI_MODEL_LIST_FALLBACK,
    PROVIDER_ANTHROPIC: ANTHROPIC_MODEL_LIST_FALLBACK,
}
PROVIDER_MODEL_DEFAULTS = {
    PROVIDER_OPENAI: "gpt-5.5",
    PROVIDER_GEMINI: "gemini-3.1-pro-preview",
    PROVIDER_ANTHROPIC: "claude-opus-4-5",
}

MODEL_DEFAULT = PROVIDER_MODEL_DEFAULTS[PROVIDER_GEMINI]
MODEL_LIST = GEMINI_MODEL_LIST_FALLBACK

# Model/provider fallback (core/fallback.py)
MAX_FALLBACK_ATTEMPTS = 4
FALLBACK_RETRY_KWARGS = {"max_retries": 2, "base_delay": 1.0, "max_delay": 10.0}
MODEL_FALLBACK_ENABLED = _os.getenv("MODEL_FALLBACK_ENABLED", "true").strip().lower() not in ("false", "0", "no")
TTS_MODEL_FALLBACK_ORDER = ["tts-1", "tts-1-hd"]  # keys of TTS_MODELS

MAX_COMPLETION_TOKENS_GEMINI = 40000
MAX_N_RESPONSES = 5

WORKSPACE_PATH = Path.cwd()

# Profiles dir is backend/profiles/ — one level up from core/
PROFILES_DIR = Path(__file__).parent.parent / "profiles"
ACTIVE_PROFILE = "default_htr"

# Templates dir is backend/templates/ — one level up from core/
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

STEP_NAMES = {0: "📤 Input", 1: "📖 Transcribe", 2: "📤 Export"}

VERBALIZE_ENABLED = _os.getenv("VERBALIZE_ENABLED", "true").strip().lower() not in ("false", "0", "no")
SPACY_ENABLED = _os.getenv("SPACY_ENABLED", "true").strip().lower() not in ("false", "0", "no")

COLORIZATION_OPTIONS = ["Word-level", "Char-level", "Named Entities"]

TTL_HOURS = 24
MAX_WORKSPACES = 100

DEBUG_MODE = False

TTS_MODELS = {
    "tts-1": {
        "name": "TTS-1 Standard",
        "description": "Standard quality, faster generation",
        "max_chars": 4096,
        "cost_per_1k_chars": 0.015,
        "supported_voices": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
    },
    "tts-1-hd": {
        "name": "TTS-1 HD",
        "description": "Higher quality, slower generation",
        "max_chars": 4096,
        "cost_per_1k_chars": 0.030,
        "supported_voices": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
    },
}

MODEL_PRICING = {
    "gpt-4o":               {"input_per_1m": 2.50,  "output_per_1m": 10.00},
    "gpt-4o-mini":          {"input_per_1m": 0.15,  "output_per_1m": 0.60},
    "gpt-4-turbo":          {"input_per_1m": 10.00, "output_per_1m": 30.00},
    "gpt-4-vision-preview": {"input_per_1m": 10.00, "output_per_1m": 30.00},
    "gpt-4":                {"input_per_1m": 30.00, "output_per_1m": 60.00},
    "gpt-3.5-turbo":        {"input_per_1m": 0.50,  "output_per_1m": 1.50},
    "gpt-5":                None,
    "gpt-5.1":              None,
    "gpt-5.2":              None,
    "gemini-2.0-flash":      {"input_per_1m": 0.10,  "output_per_1m": 0.40},
    "gemini-2.0-flash-lite": {"input_per_1m": 0.075, "output_per_1m": 0.30},
    "gemini-2.0-pro":        {"input_per_1m": 1.25,  "output_per_1m": 5.00},
    "gemini-1.5-pro":        {"input_per_1m": 1.25,  "output_per_1m": 5.00},
    "gemini-1.5-flash":      {"input_per_1m": 0.075, "output_per_1m": 0.30},
    "gemini-2.5-pro":        {"input_per_1m": 2.00,  "output_per_1m": 15.00},
    "gemini-2.5-flash":      {"input_per_1m": 0.50,  "output_per_1m": 3.50},
    "gemini-3.0":            None,
    "gemini-3.1":            None,
    "claude-opus-4-5":   {"input_per_1m": 5.00,  "output_per_1m": 25.00},
    "claude-sonnet-4-5": {"input_per_1m": 3.00,  "output_per_1m": 15.00},
    "claude-haiku-4-5":  {"input_per_1m": 1.00,  "output_per_1m": 5.00},
}


def estimate_cost_usd(input_tokens: int, output_tokens: int, model: str):
    """Return estimated USD cost, or None if model pricing is unknown."""
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return None
    return (input_tokens / 1_000_000) * pricing["input_per_1m"] \
         + (output_tokens / 1_000_000) * pricing["output_per_1m"]


TTS_VOICES = {
    "onyx": {"name": "Onyx", "description": "Deep male voice", "gender": "male", "tone": "dramatic", "recommended_for": ["military documents"], "historical_context": ""},
    "echo": {"name": "Echo", "description": "Authoritative male", "gender": "male", "tone": "authoritative", "recommended_for": ["official documents"], "historical_context": ""},
    "fable": {"name": "Fable", "description": "British accent", "gender": "male", "tone": "educated", "recommended_for": ["formal letters"], "historical_context": ""},
    "alloy": {"name": "Alloy", "description": "Balanced, neutral", "gender": "neutral", "tone": "balanced", "recommended_for": ["any document"], "historical_context": ""},
    "nova": {"name": "Nova", "description": "Female voice", "gender": "female", "tone": "warm", "recommended_for": ["personal letters"], "historical_context": ""},
    "shimmer": {"name": "Shimmer", "description": "Soft female voice", "gender": "female", "tone": "soft", "recommended_for": ["personal correspondence"], "historical_context": ""},
}

TTS_DEFAULT_MODEL = "tts-1"
TTS_DEFAULT_VOICE = "onyx"
TTS_DEFAULT_SYSTEM_PROMPT = "You are reading a historical document from the American Civil War era."

LOG_RETENTION_DAYS = 30
LOG_FORCE_FLUSH = True
