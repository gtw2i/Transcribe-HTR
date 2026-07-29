"""Edit-distance metrics: CER, WER, and their symmetric disagreement forms.

Spec §5 and §6. Definitions used throughout, for sequences A (reference) and
B (hypothesis) under unit-cost Levenshtein alignment::

    d = S + D + I                        (substitutions, deletions, insertions)

    CER(A->B) = d / len(A)               WER(A->B) = d / len(tokens(A))
    CER(B->A) = d / len(B)               WER(B->A) = d / len(tokens(B))

    CER_sym(A,B) = 2d / (len(A) + len(B))

Because substitution, insertion and deletion all cost 1, ``d(A,B) == d(B,A)``:
the two directional rates share a numerator and differ only in the denominator,
and the edit counts simply swap roles::

    S(B->A) = S(A->B)    D(B->A) = I(A->B)    I(B->A) = D(A->B)

So one alignment per pair is sufficient and the reverse direction is derived
rather than recomputed. It also follows that ``CER_sym`` is exactly the harmonic
mean of the two directional rates, which is why it is the symmetric score of
record (§5) — it is reference-designation-independent by construction.

Terminology (§28): every quantity here is *disagreement* between two
transcription attempts, not error against a ground truth.

This module imports nothing from the rest of the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .normalize import DEFAULT_PROFILE, DEFAULT_TOKENIZER, normalize, tokenize

# ── Backend selection (D4) ────────────────────────────────────────────────────
# rapidfuzz is a declared dependency and is the intended path. The pure-Python
# fallback exists so the package remains importable and correct without it; it
# is roughly three orders of magnitude slower and is not a supported
# configuration for interactive use.

try:  # pragma: no cover - exercised by whichever backend is installed
    import rapidfuzz
    from rapidfuzz.distance import Levenshtein as _RFLevenshtein

    BACKEND = f"rapidfuzz-{rapidfuzz.__version__}"
    _HAVE_RAPIDFUZZ = True
except ImportError:  # pragma: no cover
    BACKEND = "python-dp"
    _HAVE_RAPIDFUZZ = False


@dataclass(frozen=True)
class EditCounts:
    """Substitution/deletion/insertion counts for one directional alignment.

    Counts are stated with the *first* sequence as reference. ``distance`` is
    symmetric; the individual counts are not (D and I swap when the reference
    designation is reversed).
    """

    substitutions: int
    deletions: int
    insertions: int

    @property
    def distance(self) -> int:
        return self.substitutions + self.deletions + self.insertions

    def reversed(self) -> "EditCounts":
        """The same alignment read with the other sequence as reference."""
        return EditCounts(
            substitutions=self.substitutions,
            deletions=self.insertions,
            insertions=self.deletions,
        )


def _edit_counts_rapidfuzz(ref: Sequence, hyp: Sequence) -> EditCounts:
    subs = dels = ins = 0
    for op in _RFLevenshtein.editops(ref, hyp):
        if op.tag == "replace":
            subs += 1
        elif op.tag == "delete":
            dels += 1
        elif op.tag == "insert":
            ins += 1
    return EditCounts(subs, dels, ins)


def _edit_counts_python(ref: Sequence, hyp: Sequence) -> EditCounts:
    """Pure-Python Levenshtein carrying S/D/I counts along one optimal path.

    Uses O(len(hyp)) memory. Ties are broken substitution > deletion >
    insertion, which is a common convention but is *not* guaranteed to match
    rapidfuzz's choice when several optimal alignments exist: the total distance
    always agrees, the split across S/D/I may not. The backend that produced a
    result is recorded in provenance for exactly this reason.
    """
    m, n = len(ref), len(hyp)
    # Each cell holds (distance, subs, dels, ins) for one optimal path.
    prev: List[Tuple[int, int, int, int]] = [(j, 0, 0, j) for j in range(n + 1)]
    for i in range(1, m + 1):
        cur: List[Tuple[int, int, int, int]] = [(i, 0, i, 0)]
        for j in range(1, n + 1):
            if ref[i - 1] == hyp[j - 1]:
                cur.append(prev[j - 1])
                continue
            d_sub, s_sub, del_sub, i_sub = prev[j - 1]
            d_del, s_del, del_del, i_del = prev[j]
            d_ins, s_ins, del_ins, i_ins = cur[j - 1]
            best = min(d_sub, d_del, d_ins)
            if best == d_sub:
                cur.append((best + 1, s_sub + 1, del_sub, i_sub))
            elif best == d_del:
                cur.append((best + 1, s_del, del_del + 1, i_del))
            else:
                cur.append((best + 1, s_ins, del_ins, i_ins + 1))
        prev = cur
    _, subs, dels, ins = prev[n]
    return EditCounts(subs, dels, ins)


def edit_counts(ref: Sequence, hyp: Sequence) -> EditCounts:
    """Align *ref* to *hyp* and return the edit counts, ``ref`` as reference.

    Works on any sequence of hashables — a ``str`` for character level, a
    sequence of tokens for word level.
    """
    if _HAVE_RAPIDFUZZ:
        return _edit_counts_rapidfuzz(ref, hyp)
    return _edit_counts_python(ref, hyp)


# ── Alignment opcodes ─────────────────────────────────────────────────────────
# Used by the consensus vote (§14) and the difference viewer (§18). Blocks are
# ``(tag, src_start, src_end, dest_start, dest_end)`` with tags "equal",
# "replace", "delete" and "insert" — the same vocabulary as difflib, but derived
# from a Levenshtein alignment. Note that unlike difflib, a "replace" block
# always spans the same number of positions on both sides; insertions and
# deletions are emitted as their own blocks.

Opcode = Tuple[str, int, int, int, int]


def _opcodes_rapidfuzz(a: Sequence, b: Sequence) -> List[Opcode]:
    return [
        (op.tag, op.src_start, op.src_end, op.dest_start, op.dest_end)
        for op in _RFLevenshtein.opcodes(a, b)
    ]


def _opcodes_python(a: Sequence, b: Sequence) -> List[Opcode]:
    """Pure-Python alignment with traceback.

    Needs the full O(len(a) x len(b)) traceback table, so it is used only when
    rapidfuzz is unavailable, and only on token sequences (a page of words, not
    a page of characters).
    """
    m, n = len(a), len(b)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        dp[i][0] = i
    for j in range(1, n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])

    # Walk back, emitting one tag per position, then merge runs into blocks.
    tags: List[str] = []
    i, j = m, n
    while i > 0 or j > 0:
        if i > 0 and j > 0 and a[i - 1] == b[j - 1] and dp[i][j] == dp[i - 1][j - 1]:
            tags.append("equal")
            i, j = i - 1, j - 1
        elif i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + 1:
            tags.append("replace")
            i, j = i - 1, j - 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] + 1:
            tags.append("delete")
            i -= 1
        else:
            tags.append("insert")
            j -= 1
    tags.reverse()

    opcodes: List[Opcode] = []
    src = dest = 0
    for tag in tags:
        consumes_src = tag in ("equal", "replace", "delete")
        consumes_dest = tag in ("equal", "replace", "insert")
        if opcodes and opcodes[-1][0] == tag:
            prev = opcodes[-1]
            opcodes[-1] = (
                tag,
                prev[1],
                prev[2] + (1 if consumes_src else 0),
                prev[3],
                prev[4] + (1 if consumes_dest else 0),
            )
        else:
            opcodes.append(
                (
                    tag,
                    src,
                    src + (1 if consumes_src else 0),
                    dest,
                    dest + (1 if consumes_dest else 0),
                )
            )
        src += 1 if consumes_src else 0
        dest += 1 if consumes_dest else 0
    return opcodes


def align_opcodes(a: Sequence, b: Sequence) -> List[Opcode]:
    """Aligned blocks transforming *a* into *b*."""
    if _HAVE_RAPIDFUZZ:
        return _opcodes_rapidfuzz(a, b)
    return _opcodes_python(a, b)


def error_rate(distance: int, reference_length: int) -> Optional[float]:
    """Directional rate ``distance / reference_length``.

    Returns ``None`` when the reference is empty: the rate is 0/0, undefined.
    Values above 1.0 are possible and are deliberately **not** clipped — a
    hypothesis much longer than its reference genuinely disagrees by more than
    the reference's own length, and clipping would hide that.
    """
    if reference_length == 0:
        return None
    return distance / reference_length


def symmetric_rate(distance: int, len_a: int, len_b: int) -> float:
    """``2d / (len_a + len_b)`` — the harmonic mean of the directional rates.

    Edge cases, both deliberate:

    * both sides empty -> ``0.0`` (two empty transcriptions do not disagree);
    * exactly one side empty -> ``1.0`` (total disagreement; the raw formula
      would give 2.0, which is not meaningful as a disagreement fraction).
    """
    if len_a == 0 and len_b == 0:
        return 0.0
    if len_a == 0 or len_b == 0:
        return 1.0
    return (2.0 * distance) / (len_a + len_b)


@dataclass(frozen=True)
class PreparedText:
    """An attempt's text after normalization and tokenization.

    Prepared once per attempt, then reused across all N-1 of its comparisons.
    """

    attempt_id: str
    original: str
    normalized: str
    tokens: Tuple[str, ...]

    @property
    def n_chars(self) -> int:
        return len(self.normalized)

    @property
    def n_words(self) -> int:
        return len(self.tokens)


def prepare(
    attempt_id: str,
    text: str,
    profile: str = DEFAULT_PROFILE,
    tokenizer: str = DEFAULT_TOKENIZER,
) -> PreparedText:
    """Normalize and tokenize one attempt. The original text is retained (§4.1)."""
    normalized = normalize(text, profile)
    return PreparedText(
        attempt_id=attempt_id,
        original=text,
        normalized=normalized,
        tokens=tuple(tokenize(normalized, tokenizer)),
    )


@dataclass(frozen=True)
class PairMetrics:
    """Every measurement for one unordered pair (§6.2.1 — nothing is discarded).

    Edit counts are stated with A as reference; the B-as-reference counts are
    ``EditCounts(...).reversed()`` and are not stored separately because they
    are fully determined (S is shared, D and I swap).
    """

    a_id: str
    b_id: str

    # character level
    char_distance: int
    char_substitutions: int
    char_deletions: int
    char_insertions: int
    len_a_chars: int
    len_b_chars: int
    cer_a_to_b: Optional[float]
    cer_b_to_a: Optional[float]
    cer_sym: float

    # word level
    word_distance: int
    word_substitutions: int
    word_deletions: int
    word_insertions: int
    len_a_words: int
    len_b_words: int
    wer_a_to_b: Optional[float]
    wer_b_to_a: Optional[float]
    wer_sym: float

    def as_dict(self) -> dict:
        """Flat dict for CSV export and the API payload."""
        return {
            "a_id": self.a_id,
            "b_id": self.b_id,
            "char_distance": self.char_distance,
            "char_substitutions": self.char_substitutions,
            "char_deletions": self.char_deletions,
            "char_insertions": self.char_insertions,
            "len_a_chars": self.len_a_chars,
            "len_b_chars": self.len_b_chars,
            "cer_a_to_b": self.cer_a_to_b,
            "cer_b_to_a": self.cer_b_to_a,
            "cer_sym": self.cer_sym,
            "word_distance": self.word_distance,
            "word_substitutions": self.word_substitutions,
            "word_deletions": self.word_deletions,
            "word_insertions": self.word_insertions,
            "len_a_words": self.len_a_words,
            "len_b_words": self.len_b_words,
            "wer_a_to_b": self.wer_a_to_b,
            "wer_b_to_a": self.wer_b_to_a,
            "wer_sym": self.wer_sym,
        }


def compare(a: PreparedText, b: PreparedText) -> PairMetrics:
    """Compute every character- and word-level measurement for one pair."""
    chars = edit_counts(a.normalized, b.normalized)
    words = edit_counts(a.tokens, b.tokens)

    return PairMetrics(
        a_id=a.attempt_id,
        b_id=b.attempt_id,
        char_distance=chars.distance,
        char_substitutions=chars.substitutions,
        char_deletions=chars.deletions,
        char_insertions=chars.insertions,
        len_a_chars=a.n_chars,
        len_b_chars=b.n_chars,
        cer_a_to_b=error_rate(chars.distance, a.n_chars),
        cer_b_to_a=error_rate(chars.distance, b.n_chars),
        cer_sym=symmetric_rate(chars.distance, a.n_chars, b.n_chars),
        word_distance=words.distance,
        word_substitutions=words.substitutions,
        word_deletions=words.deletions,
        word_insertions=words.insertions,
        len_a_words=a.n_words,
        len_b_words=b.n_words,
        wer_a_to_b=error_rate(words.distance, a.n_words),
        wer_b_to_a=error_rate(words.distance, b.n_words),
        wer_sym=symmetric_rate(words.distance, a.n_words, b.n_words),
    )


# ── Provenance (§25) ──────────────────────────────────────────────────────────

CER_DEFINITION = "(S+D+I) / reference character count, unit-cost Levenshtein"
WER_DEFINITION = "(S+D+I) / reference word count, unit-cost Levenshtein over tokens"
SYMMETRIC_DEFINITION = (
    "2*d / (len_A + len_B), the harmonic mean of the two directional rates; "
    "0.0 when both sides are empty, 1.0 when exactly one is"
)


def metric_definitions() -> dict:
    """The definitions to embed in every analysis output (§5, §25)."""
    return {
        "cer_definition": CER_DEFINITION,
        "wer_definition": WER_DEFINITION,
        "symmetric_definition": SYMMETRIC_DEFINITION,
        "backend": BACKEND,
    }
