"""Text normalization and tokenization for consistency analysis.

Spec §4. Normalization is applied *only* to produce the strings that CER/WER are
measured on. The stored transcription text is never modified — every function
here is pure and returns a new string (§4.1).

A profile is an ordered list of named steps. The step list and profile version
are recorded in the analysis provenance (§4.2, §25) so a result can be
reproduced exactly.

This module imports nothing from the rest of the backend.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Callable, Dict, List, Tuple

# ── Individual normalization steps ────────────────────────────────────────────
# Each step is a pure str -> str function. Steps must be idempotent on their own
# so that any profile built from them is idempotent as a whole; this is asserted
# in the test suite.


def step_nfc(text: str) -> str:
    """Unicode canonical composition."""
    return unicodedata.normalize("NFC", text)


def step_nfkc(text: str) -> str:
    """Unicode compatibility composition (folds ligatures, fullwidth forms...)."""
    return unicodedata.normalize("NFKC", text)


def step_strip_document_edges(text: str) -> str:
    """Strip leading/trailing whitespace from the whole document."""
    return text.strip()


def step_strip_line_edges(text: str) -> str:
    """Strip leading/trailing whitespace from every line."""
    return "\n".join(line.strip() for line in text.split("\n"))


def step_collapse_spaces(text: str) -> str:
    """Collapse runs of spaces/tabs into a single space. Newlines are untouched."""
    return re.sub(r"[ \t]+", " ", text)


def step_collapse_blank_lines(text: str) -> str:
    """Collapse three or more consecutive newlines into two (one blank line)."""
    return re.sub(r"\n{3,}", "\n\n", text)


def step_drop_empty_lines(text: str) -> str:
    """Remove every blank line."""
    return "\n".join(line for line in text.split("\n") if line.strip())


def step_join_linebreak_hyphens(text: str) -> str:
    """Rejoin words split across a line break by a hyphen: ``wo-\\nrd`` -> ``word``.

    Uses zero-width look-around so that adjacent occurrences all match in a
    single pass — a consuming pattern would need repeated application and would
    therefore not be idempotent.
    """
    return re.sub(r"(?<=\w)-\n[ \t]*(?=\w)", "", text)


def step_newlines_to_spaces(text: str) -> str:
    """Flatten all line structure into single spaces."""
    return re.sub(r"\n+", " ", text)


def step_lowercase(text: str) -> str:
    """Case-fold."""
    return text.lower()


def step_strip_punctuation(text: str) -> str:
    """Remove every Unicode punctuation character (category ``P*``).

    Characters are removed rather than replaced with a space, so ``don't``
    becomes ``dont``. The rare ``word.Next`` (missing space after a stop) will
    merge into one token; that is an accepted trade-off in the aggressive
    ``normalized`` profile and is documented in its description.
    """
    return "".join(ch for ch in text if not unicodedata.category(ch).startswith("P"))


STEPS: Dict[str, Callable[[str], str]] = {
    "nfc": step_nfc,
    "nfkc": step_nfkc,
    "strip_document_edges": step_strip_document_edges,
    "strip_line_edges": step_strip_line_edges,
    "collapse_spaces": step_collapse_spaces,
    "collapse_blank_lines": step_collapse_blank_lines,
    "drop_empty_lines": step_drop_empty_lines,
    "join_linebreak_hyphens": step_join_linebreak_hyphens,
    "newlines_to_spaces": step_newlines_to_spaces,
    "lowercase": step_lowercase,
    "strip_punctuation": step_strip_punctuation,
}


# ── Profiles (§4.2, §4.3) ─────────────────────────────────────────────────────

NORMALIZATION_VERSION = "1.0"

DEFAULT_PROFILE = "standard_historical"

NORMALIZATION_PROFILES: Dict[str, Dict[str, object]] = {
    "standard_historical": {
        "label": "Standard (historical)",
        "description": (
            "Preserves capitalization and punctuation as substantive editorial "
            "data; normalizes whitespace and line-break hyphenation, which are "
            "artifacts of how the model formatted its output."
        ),
        "steps": [
            "nfc",
            "strip_line_edges",
            "collapse_spaces",
            "join_linebreak_hyphens",
            "collapse_blank_lines",
            "strip_document_edges",
        ],
    },
    "diplomatic": {
        "label": "Diplomatic (literal)",
        "description": (
            "Unicode normalization only. Every difference in case, punctuation, "
            "spacing and line breaks counts as disagreement."
        ),
        "steps": ["nfc"],
    },
    "normalized": {
        "label": "Normalized (content only)",
        "description": (
            "Ignores orthographic and layout variation: case-folded, punctuation "
            "removed, line structure flattened. Use to isolate how much "
            "disagreement is substantive rather than orthographic."
        ),
        "steps": [
            "nfc",
            "strip_line_edges",
            "collapse_spaces",
            "join_linebreak_hyphens",
            "lowercase",
            "strip_punctuation",
            "newlines_to_spaces",
            "collapse_spaces",
            "strip_document_edges",
        ],
    },
}


class UnknownProfileError(ValueError):
    """Raised when a normalization profile id is not registered."""


class UnknownTokenizerError(ValueError):
    """Raised when a tokenizer id is not registered."""


def normalize(text: str, profile: str = DEFAULT_PROFILE) -> str:
    """Apply a normalization profile to *text*, returning a new string.

    The input is never mutated (§4.1).
    """
    if profile not in NORMALIZATION_PROFILES:
        raise UnknownProfileError(
            f"Unknown normalization profile {profile!r}. "
            f"Known profiles: {sorted(NORMALIZATION_PROFILES)}"
        )
    if text is None:
        return ""
    result = text
    for step_name in NORMALIZATION_PROFILES[profile]["steps"]:  # type: ignore[index]
        result = STEPS[step_name](result)
    return result


def describe_profile(profile: str = DEFAULT_PROFILE) -> Dict[str, object]:
    """Return the provenance record for a profile (§4.2, §25)."""
    if profile not in NORMALIZATION_PROFILES:
        raise UnknownProfileError(f"Unknown normalization profile {profile!r}.")
    spec = NORMALIZATION_PROFILES[profile]
    return {
        "id": profile,
        "label": spec["label"],
        "description": spec["description"],
        "version": NORMALIZATION_VERSION,
        "steps": list(spec["steps"]),  # type: ignore[arg-type]
    }


def list_profiles() -> List[Dict[str, object]]:
    """All registered profiles, for the settings UI."""
    return [describe_profile(name) for name in NORMALIZATION_PROFILES]


# ── Tokenization (§6) ─────────────────────────────────────────────────────────

_WORD_PUNCT_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)

DEFAULT_TOKENIZER = "word_simple"


def _tokenize_word_simple(text: str) -> List[str]:
    return text.split()


def _tokenize_word_punct(text: str) -> List[str]:
    return _WORD_PUNCT_RE.findall(text)


TOKENIZERS: Dict[str, Callable[[str], List[str]]] = {
    "word_simple": _tokenize_word_simple,
    "word_punct": _tokenize_word_punct,
}

TOKENIZER_DESCRIPTIONS: Dict[str, str] = {
    "word_simple": (
        "Split on whitespace. Attached punctuation stays part of the word, so "
        "'word,' and 'word' count as different tokens."
    ),
    "word_punct": (
        "Split words and punctuation into separate tokens, so punctuation "
        "differences are counted independently of the words they follow."
    ),
}


def tokenize(text: str, tokenizer: str = DEFAULT_TOKENIZER) -> List[str]:
    """Split normalized *text* into word tokens.

    The same tokenizer must be used for every comparison in one analysis (§6);
    the id is recorded in provenance.
    """
    if tokenizer not in TOKENIZERS:
        raise UnknownTokenizerError(
            f"Unknown tokenizer {tokenizer!r}. Known tokenizers: {sorted(TOKENIZERS)}"
        )
    return TOKENIZERS[tokenizer](text)


def list_tokenizers() -> List[Dict[str, str]]:
    """All registered tokenizers, for the settings UI."""
    return [
        {"id": name, "description": TOKENIZER_DESCRIPTIONS[name]} for name in TOKENIZERS
    ]


#: Span-aware equivalents of the tokenizers above. ``str.split()`` is exactly
#: ``re.findall(r"\S+", text)``, so both tokenizers can report positions — which
#: is what lets the consensus reassemble line structure from a backbone
#: transcription (§14) instead of emitting a flat stream of words.
TOKENIZER_PATTERNS: Dict[str, "re.Pattern[str]"] = {
    "word_simple": re.compile(r"\S+"),
    "word_punct": _WORD_PUNCT_RE,
}


def tokenize_with_spans(
    text: str, tokenizer: str = DEFAULT_TOKENIZER
) -> List[Tuple[str, int, int]]:
    """Tokenize, returning ``(token, start, end)`` for each token.

    Produces exactly the same token sequence as :func:`tokenize`; the offsets
    additionally allow the original separator between two tokens to be
    recovered.
    """
    if tokenizer not in TOKENIZER_PATTERNS:
        raise UnknownTokenizerError(
            f"Unknown tokenizer {tokenizer!r}. "
            f"Known tokenizers: {sorted(TOKENIZER_PATTERNS)}"
        )
    return [
        (match.group(0), match.start(), match.end())
        for match in TOKENIZER_PATTERNS[tokenizer].finditer(text)
    ]
