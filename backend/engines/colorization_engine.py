# engines/colorization_engine.py
"""Colorization engine — wraps transcription_utils functions into a clean API."""

import re
from typing import List, Optional

import numpy as np

from transcription_utils import (
    colorize_chars,
    colorize_ner_gemini,
    colorize_words,
    compute_token_disagreement,
)


def compute_colorization(
    outputs: List[str],
    sel_idx: int,
    mode: str,
    ner_result: Optional[dict] = None,
) -> Optional[str]:
    """
    Return an HTML string with colorized text, or None if colorization isn't possible.

    Args:
        outputs:    All transcription texts (used to compute disagreement vectors).
        sel_idx:    Index of the text to colorize within `outputs`.
        mode:       One of 'Word-level', 'Char-level', 'Named Entities'.
        ner_result: Entity bundle from run_ner() — required for 'Named Entities' mode.

    Returns:
        HTML string, or None with an explanatory reason tuple (html, reason).
    """
    if not outputs or sel_idx >= len(outputs):
        return None, "No outputs available."

    text = outputs[sel_idx]
    n_compare = len(outputs)

    if mode == "Named Entities":
        if ner_result is None:
            return None, "No NER results available."
        html = colorize_ner_gemini(text, ner_result, transcription_id=sel_idx)
        if html is None:
            return None, "No named entities matched in this transcription."
        return html, None

    if n_compare < 2:
        import html as _html
        return _html.escape(text), "Only 1 transcription was used — no comparison highlighting available."

    if mode == "Char-level":
        all_vecs = compute_token_disagreement(outputs, level="char")
        if sel_idx >= len(all_vecs) or all_vecs[sel_idx] is None:
            return None, "Character disagreement data missing."
        vec = np.asarray(all_vecs[sel_idx], dtype=float)
        if len(vec) != len(list(text)):
            return None, f"Token/value mismatch: {len(list(text))} chars vs {len(vec)} values."
        return colorize_chars(text, vec), None

    # Default: Word-level
    all_vecs = compute_token_disagreement(outputs, level="word")
    if sel_idx >= len(all_vecs) or all_vecs[sel_idx] is None:
        return None, "Word disagreement data missing."
    vec = np.asarray(all_vecs[sel_idx], dtype=float)
    words_only = [tok for tok in re.split(r"(\s+)", text) if not tok.isspace()]
    if len(vec) == 0:
        return None, "No disagreement data available."
    if len(words_only) != len(vec):
        return None, f"Token/value mismatch: {len(words_only)} words vs {len(vec)} values."
    return colorize_words(text, vec), None
