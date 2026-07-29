"""Difference inspection between two transcriptions.

Spec §18. A numerical disagreement score alone does not tell a user *what*
differs, so this module turns an alignment into labelled segments and counts
the kinds of change involved: spelling, punctuation, spacing, omitted words,
inserted words, substituted words, missing lines, reordered material, and
outright transcription failure.

Works for any two texts — two attempts, or an attempt against a consensus.

This module imports nothing from the rest of the backend.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from .metrics import PreparedText, align_opcodes, edit_counts

# ── Change categories (§18) ───────────────────────────────────────────────────

CAT_EQUAL = "equal"
CAT_CASE = "case"
CAT_PUNCTUATION = "punctuation"
CAT_SPACING = "spacing"
CAT_SPELLING = "spelling"
CAT_SUBSTITUTION = "substitution"
CAT_OMISSION = "omission"
CAT_INSERTION = "insertion"
CAT_LINE_OMISSION = "line_omission"
CAT_LINE_INSERTION = "line_insertion"

CATEGORY_LABELS: Dict[str, str] = {
    CAT_EQUAL: "Identical",
    CAT_CASE: "Capitalization only",
    CAT_PUNCTUATION: "Punctuation only",
    CAT_SPACING: "Word spacing",
    CAT_SPELLING: "Spelling variant",
    CAT_SUBSTITUTION: "Different word",
    CAT_OMISSION: "Words omitted",
    CAT_INSERTION: "Words inserted",
    CAT_LINE_OMISSION: "Line or passage omitted",
    CAT_LINE_INSERTION: "Line or passage inserted",
}

#: A run of this many consecutive omitted or inserted tokens is reported as a
#: whole line or passage rather than as individual words.
LINE_RUN_THRESHOLD = 5

#: Token pairs within this edit distance are treated as spelling variants of
#: one another rather than as different words.
SPELLING_DISTANCE = 2

#: When at least this fraction of the reference's tokens are involved in a
#: change, the pair is additionally flagged as a substantial divergence.
MAJOR_DIVERGENCE_FRACTION = 0.25


def _strip_punctuation(token: str) -> str:
    return "".join(
        ch for ch in token if not unicodedata.category(ch).startswith("P")
    )


def _categorize_substitution(a_tokens: Sequence[str], b_tokens: Sequence[str]) -> str:
    """Classify a replaced run of tokens (§18)."""
    a_joined, b_joined = "".join(a_tokens), "".join(b_tokens)

    # A word split or joined across a space: "in to" vs "into".
    if a_joined == b_joined and list(a_tokens) != list(b_tokens):
        return CAT_SPACING

    if len(a_tokens) == 1 and len(b_tokens) == 1:
        a, b = a_tokens[0], b_tokens[0]
        if a.lower() == b.lower():
            return CAT_CASE
        if _strip_punctuation(a) == _strip_punctuation(b):
            return CAT_PUNCTUATION
        if _strip_punctuation(a).lower() == _strip_punctuation(b).lower():
            return CAT_CASE
        if edit_counts(a, b).distance <= SPELLING_DISTANCE:
            return CAT_SPELLING
        return CAT_SUBSTITUTION

    if a_joined.lower() == b_joined.lower():
        return CAT_SPACING
    return CAT_SUBSTITUTION


@dataclass(frozen=True)
class DiffSegment:
    """One aligned run of tokens, with what kind of change it represents."""

    tag: str
    category: str
    a_tokens: Tuple[str, ...]
    b_tokens: Tuple[str, ...]
    a_start: int
    b_start: int

    @property
    def is_change(self) -> bool:
        return self.tag != "equal"

    def as_dict(self) -> dict:
        return {
            "tag": self.tag,
            "category": self.category,
            "category_label": CATEGORY_LABELS.get(self.category, self.category),
            "a_tokens": list(self.a_tokens),
            "b_tokens": list(self.b_tokens),
            "a_text": " ".join(self.a_tokens),
            "b_text": " ".join(self.b_tokens),
            "a_start": self.a_start,
            "b_start": self.b_start,
        }


@dataclass(frozen=True)
class DiffResult:
    """A two-way difference, and what kinds of change it consists of (§18)."""

    a_id: str
    b_id: str
    segments: Tuple[DiffSegment, ...]
    category_counts: Dict[str, int]
    a_token_count: int
    b_token_count: int
    changed_token_count: int
    major_divergence: bool
    #: The unmodified source texts stay available (§18, final clause).
    a_original: str = ""
    b_original: str = ""

    @property
    def changed_fraction(self) -> float:
        if self.a_token_count == 0:
            return 1.0 if self.b_token_count else 0.0
        return self.changed_token_count / self.a_token_count

    def summary(self) -> str:
        """Plain-language account of what differs, for the UI and exports."""
        if not any(seg.is_change for seg in self.segments):
            return "The two transcriptions are identical after normalization."

        parts = [
            f"{count} {CATEGORY_LABELS.get(category, category).lower()}"
            for category, count in sorted(
                self.category_counts.items(), key=lambda kv: (-kv[1], kv[0])
            )
            if category != CAT_EQUAL and count
        ]
        text = "Differences: " + ", ".join(parts) + "."
        if self.major_divergence:
            text += (
                f" {self.changed_fraction:.0%} of the reference's words are "
                f"involved, which indicates substantial divergence rather than "
                f"isolated variation."
            )
        return text

    def as_dict(self) -> dict:
        return {
            "a_id": self.a_id,
            "b_id": self.b_id,
            "segments": [s.as_dict() for s in self.segments],
            "category_counts": dict(self.category_counts),
            "category_labels": {
                k: CATEGORY_LABELS.get(k, k) for k in self.category_counts
            },
            "a_token_count": self.a_token_count,
            "b_token_count": self.b_token_count,
            "changed_token_count": self.changed_token_count,
            "changed_fraction": self.changed_fraction,
            "major_divergence": self.major_divergence,
            "summary": self.summary(),
            "a_original": self.a_original,
            "b_original": self.b_original,
        }


def _merge_spacing_runs(segments: Sequence[DiffSegment]) -> List[DiffSegment]:
    """Recognise word splits and joins that span several aligned blocks.

    A token-level alignment renders ``into`` against ``in to`` as a replace
    followed by an insert, which would be reported as a spelling variant plus an
    inserted word. Whenever a run of consecutive changes has the same text on
    both sides once whitespace is removed, it is really one spacing difference
    (§18), so the run is merged and relabelled.
    """
    merged: List[DiffSegment] = []
    index = 0
    while index < len(segments):
        if not segments[index].is_change:
            merged.append(segments[index])
            index += 1
            continue

        end = index
        while end < len(segments) and segments[end].is_change:
            end += 1

        run = segments[index:end]
        a_run = tuple(token for seg in run for token in seg.a_tokens)
        b_run = tuple(token for seg in run for token in seg.b_tokens)

        if len(run) > 1 and a_run and b_run and "".join(a_run) == "".join(b_run):
            merged.append(
                DiffSegment(
                    tag="replace",
                    category=CAT_SPACING,
                    a_tokens=a_run,
                    b_tokens=b_run,
                    a_start=run[0].a_start,
                    b_start=run[0].b_start,
                )
            )
        else:
            merged.extend(run)
        index = end
    return merged


def diff_tokens(
    a_tokens: Sequence[str],
    b_tokens: Sequence[str],
    a_id: str = "a",
    b_id: str = "b",
    a_original: str = "",
    b_original: str = "",
) -> DiffResult:
    """Align two token sequences and classify every difference (§18)."""
    raw: List[DiffSegment] = []

    for tag, i1, i2, j1, j2 in align_opcodes(list(a_tokens), list(b_tokens)):
        a_run = tuple(a_tokens[i1:i2])
        b_run = tuple(b_tokens[j1:j2])

        if tag == "equal":
            category = CAT_EQUAL
        elif tag == "replace":
            category = _categorize_substitution(a_run, b_run)
        elif tag == "delete":
            category = (
                CAT_LINE_OMISSION if len(a_run) >= LINE_RUN_THRESHOLD else CAT_OMISSION
            )
        else:
            category = (
                CAT_LINE_INSERTION
                if len(b_run) >= LINE_RUN_THRESHOLD
                else CAT_INSERTION
            )

        raw.append(DiffSegment(tag, category, a_run, b_run, i1, j1))

    segments = _merge_spacing_runs(raw)

    counts: Counter = Counter()
    changed = 0
    for segment in segments:
        counts[segment.category] += 1
        if segment.is_change:
            changed += max(len(segment.a_tokens), len(segment.b_tokens))

    a_count = len(a_tokens)
    major = a_count > 0 and (changed / a_count) >= MAJOR_DIVERGENCE_FRACTION

    return DiffResult(
        a_id=a_id,
        b_id=b_id,
        segments=tuple(segments),
        category_counts=dict(counts),
        a_token_count=a_count,
        b_token_count=len(b_tokens),
        changed_token_count=changed,
        major_divergence=major,
        a_original=a_original,
        b_original=b_original,
    )


def diff_prepared(a: PreparedText, b: PreparedText) -> DiffResult:
    """Difference between two prepared attempts, keeping their original texts."""
    return diff_tokens(
        a.tokens,
        b.tokens,
        a_id=a.attempt_id,
        b_id=b.attempt_id,
        a_original=a.original,
        b_original=b.original,
    )
