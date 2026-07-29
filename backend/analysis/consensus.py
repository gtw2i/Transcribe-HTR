"""Consensus transcriptions from a set of replicate attempts.

Spec §13 (consensus from the selected attempts only), §14 (deterministic
consensus), §15 (medoid / most representative existing attempt), §17 (comparing
each attempt against the consensus), §33 (the consensus is what the replicate
evidence most strongly supports).

Two distinct things live here, and the UI must never conflate them (§16):

* :func:`select_medoid` — the *existing* attempt closest to the others. Its text is verbatim from one transcription; nothing is synthesized.
* :func:`deterministic_consensus` — a *synthesized* transcription assembled by voting among the attempts. Reproducible, and it uses no generative model.

Neither uses the source image, a prior consensus, unselected attempts, or any
external information (§13).

This module imports nothing from the rest of the backend.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .matrices import PairwiseMatrices, mean_disagreement_vector
from .metrics import PreparedText, align_opcodes, compare, prepare
from .normalize import DEFAULT_PROFILE, DEFAULT_TOKENIZER, tokenize_with_spans

#: Identifier for the algorithm below. Recorded with every consensus (§14) so a
#: future revision can never silently reinterpret a stored result.
DETERMINISTIC_METHOD = "deterministic_vote_v1"

METHOD_MEDOID = "medoid"
METHOD_DETERMINISTIC = "deterministic"
METHOD_LLM = "llm"

#: Emitted tokens supported by less than this fraction of attempts are marked
#: low-support so the UI can shade them.
LOW_SUPPORT_THRESHOLD = 0.6

#: The backbone is warned about when its token count deviates from the group
#: median by more than this fraction — a backbone that is much shorter than the
#: group may be missing material the vote cannot recover (see LIMITATIONS).
BACKBONE_DEVIATION_WARNING = 0.20

LIMITATIONS: Tuple[str, ...] = (
    "Material absent from the backbone transcription can only enter through the "
    "strict-majority insertion rule, so a backbone with a large omission "
    "under-recovers it.",
    "Reordered material is treated as a deletion plus an insertion, not as a move.",
    "Voting operates on the normalized text, so the consensus inherits the "
    "normalization profile: under the aggressive 'normalized' profile the "
    "result is case-folded and stripped of punctuation.",
)


class _Omitted:
    """Sentinel vote for "this attempt has no token at this position"."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<omitted>"


OMITTED = _Omitted()


# ── Medoid (§15) ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MedoidResult:
    """The existing attempt most representative of the selected set (§15)."""

    attempt_id: str
    mean_cer: float
    mean_wer: float
    max_cer: float
    rank: Tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "attempt_id": self.attempt_id,
            "mean_cer": self.mean_cer,
            "mean_wer": self.mean_wer,
            "max_cer": self.max_cer,
            "rank": list(self.rank),
        }


def select_medoid(matrices: PairwiseMatrices) -> MedoidResult:
    """The attempt with the lowest aggregate disagreement with the others (§15).

    The criterion is the *mean* symmetric CER disagreement, which is what §15
    asks for — lowest aggregate disagreement with the rest of the set. (Outlier
    detection deliberately uses the median instead; see ``outliers``.)

    Ties break by lowest maximum pairwise disagreement, then lowest mean WER,
    then canonical order — so the choice is deterministic (§27).
    """
    n = matrices.n
    if n < 2:
        raise ValueError("Medoid selection requires at least 2 attempts.")

    mean_cer = mean_disagreement_vector(matrices, "cer")
    mean_wer = mean_disagreement_vector(matrices, "wer")
    max_cer = np.array(
        [np.delete(matrices.cer_symmetric[i], i).max() for i in range(n)], dtype=float
    )

    order = sorted(
        range(n),
        key=lambda i: (
            round(float(mean_cer[i]), 12),
            round(float(max_cer[i]), 12),
            round(float(mean_wer[i]), 12),
            i,
        ),
    )
    best = order[0]
    return MedoidResult(
        attempt_id=matrices.attempt_ids[best],
        mean_cer=float(mean_cer[best]),
        mean_wer=float(mean_wer[best]),
        max_cer=float(max_cer[best]),
        rank=tuple(matrices.attempt_ids[i] for i in order),
    )


# ── Deterministic consensus (§14) ─────────────────────────────────────────────


@dataclass(frozen=True)
class ConsensusToken:
    """One emitted token and how much of the group supported it."""

    token: str
    support: float
    from_gap: bool = False

    @property
    def low_support(self) -> bool:
        return self.support < LOW_SUPPORT_THRESHOLD

    def as_dict(self) -> dict:
        return {
            "token": self.token,
            "support": self.support,
            "from_gap": self.from_gap,
            "low_support": self.low_support,
        }


@dataclass(frozen=True)
class ConsensusResult:
    """A synthesized consensus transcription (§14)."""

    method: str
    text: str
    backbone_attempt_id: str
    tokens: Tuple[ConsensusToken, ...]
    n_attempts: int
    n_low_support: int
    warnings: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = LIMITATIONS
    generated: bool = False

    @property
    def mean_support(self) -> float:
        if not self.tokens:
            return 0.0
        return float(np.mean([t.support for t in self.tokens]))

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "text": self.text,
            "backbone_attempt_id": self.backbone_attempt_id,
            "n_attempts": self.n_attempts,
            "n_tokens": len(self.tokens),
            "n_low_support": self.n_low_support,
            "mean_support": self.mean_support,
            "low_support_threshold": LOW_SUPPORT_THRESHOLD,
            "tokens": [t.as_dict() for t in self.tokens],
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
            "generated": self.generated,
        }


def _separators(text: str, tokenizer: str) -> Tuple[List[str], List[str]]:
    """Tokens of *text* plus the separator that follows each one."""
    spans = tokenize_with_spans(text, tokenizer)
    tokens = [token for token, _, _ in spans]
    separators: List[str] = []
    for index, (_, _, end) in enumerate(spans):
        next_start = spans[index + 1][1] if index + 1 < len(spans) else len(text)
        separators.append(text[end:next_start])
    return tokens, separators


def _collect_votes(
    backbone: Sequence[str], others: Sequence[Sequence[str]]
) -> Tuple[List[List[object]], List[List[Tuple[str, ...]]]]:
    """Map every attempt onto the backbone's positions.

    Returns ``(column_votes, gap_votes)``: one vote per backbone position per
    attempt (a token or ``OMITTED``), and one contributed token run per gap
    slot per attempt.
    """
    n_columns = len(backbone)
    column_votes: List[List[object]] = [[token] for token in backbone]
    gap_votes: List[List[Tuple[str, ...]]] = [[()] for _ in range(n_columns + 1)]

    for other in others:
        columns: List[object] = [OMITTED] * n_columns
        gaps: List[List[str]] = [[] for _ in range(n_columns + 1)]

        for tag, i1, i2, j1, j2 in align_opcodes(list(backbone), list(other)):
            if tag in ("equal", "replace"):
                paired = min(i2 - i1, j2 - j1)
                for offset in range(paired):
                    columns[i1 + offset] = other[j1 + offset]
                # Defensive: rapidfuzz keeps replace blocks 1:1, but a fallback
                # need not, so route any surplus to the neighbouring slots.
                for offset in range(paired, j2 - j1):
                    gaps[i2].append(other[j1 + offset])
            elif tag == "delete":
                for position in range(i1, i2):
                    columns[position] = OMITTED
            elif tag == "insert":
                gaps[i1].extend(other[j1:j2])

        for index in range(n_columns):
            column_votes[index].append(columns[index])
        for index in range(n_columns + 1):
            gap_votes[index].append(tuple(gaps[index]))

    return column_votes, gap_votes


def _vote_column(votes: Sequence[object], backbone_token: str) -> Tuple[object, float]:
    """Plurality winner for one backbone position; ties go to the backbone."""
    counts = Counter(votes)
    best = max(counts.values())
    if counts[backbone_token] == best:
        winner: object = backbone_token
    else:
        # Deterministic tie-break among non-backbone candidates: first in the
        # order they were cast.
        winner = next(v for v in votes if counts[v] == best)
    return winner, counts[winner] / len(votes)


def _vote_gap(votes: Sequence[Tuple[str, ...]]) -> Tuple[Tuple[str, ...], float]:
    """Emit an inserted run only on a strict majority (§14).

    Deliberately conservative: it stops a single verbose attempt from injecting
    text the rest of the group does not support.
    """
    counts = Counter(votes)
    non_empty = [(run, count) for run, count in counts.items() if run]
    if not non_empty:
        return (), 0.0
    run, count = max(non_empty, key=lambda item: (item[1], -len(item[0])))
    if count * 2 <= len(votes):
        return (), count / len(votes)
    return run, count / len(votes)


def deterministic_consensus(
    prepared: Sequence[PreparedText],
    matrices: PairwiseMatrices,
    tokenizer: str = DEFAULT_TOKENIZER,
) -> ConsensusResult:
    """Assemble a consensus by aligning to a backbone and voting (§14).

    The backbone is the medoid, so the result is anchored to a transcription a
    model actually produced rather than to an arbitrary first attempt — which
    also removes any dependence on input order.

    Every step is deterministic: medoid choice, alignment, plurality, and all
    tie-breaks. No RNG, no model call.
    """
    if len(prepared) < 2:
        raise ValueError("A consensus requires at least 2 transcription attempts.")

    by_id = {p.attempt_id: p for p in prepared}
    medoid = select_medoid(matrices)
    backbone = by_id[medoid.attempt_id]

    backbone_tokens, separators = _separators(backbone.normalized, tokenizer)
    others = [p.tokens for p in prepared if p.attempt_id != backbone.attempt_id]

    column_votes, gap_votes = _collect_votes(backbone_tokens, others)
    n_attempts = len(prepared)

    emitted: List[ConsensusToken] = []
    pieces: List[str] = []

    for index in range(len(backbone_tokens) + 1):
        run, _ = _vote_gap(gap_votes[index])
        for token in run:
            support = sum(
                1 for votes in gap_votes[index] if token in votes
            ) / n_attempts
            emitted.append(ConsensusToken(token, support, from_gap=True))
            pieces.append(token + " ")

        if index < len(backbone_tokens):
            winner, support = _vote_column(column_votes[index], backbone_tokens[index])
            if winner is not OMITTED:
                emitted.append(ConsensusToken(str(winner), support))
                pieces.append(str(winner) + separators[index])

    text = _tidy("".join(pieces))

    warnings: List[str] = []
    token_counts = [len(p.tokens) for p in prepared]
    median_tokens = float(np.median(token_counts))
    if median_tokens > 0:
        deviation = abs(len(backbone_tokens) - median_tokens) / median_tokens
        if deviation > BACKBONE_DEVIATION_WARNING:
            warnings.append(
                f"The backbone transcription ({medoid.attempt_id}) has "
                f"{len(backbone_tokens)} words against a group median of "
                f"{median_tokens:.0f}, a deviation of {deviation:.0%}. Material "
                f"absent from the backbone may be under-represented in the "
                f"consensus."
            )

    return ConsensusResult(
        method=DETERMINISTIC_METHOD,
        text=text,
        backbone_attempt_id=backbone.attempt_id,
        tokens=tuple(emitted),
        n_attempts=n_attempts,
        n_low_support=sum(1 for t in emitted if t.low_support),
        warnings=tuple(warnings),
    )


def _tidy(text: str) -> str:
    """Collapse the whitespace left by dropped tokens, keeping line structure."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Comparison against a consensus (§17) ──────────────────────────────────────

CONSENSUS_COMPARISON_CAVEAT = (
    "Consensus comparisons are not independent of the attempts: the consensus "
    "was derived from this same set. They are reported separately from the "
    "pairwise statistics for that reason."
)


@dataclass(frozen=True)
class ConsensusComparison:
    """One attempt measured against the chosen consensus (§17)."""

    attempt_id: str
    cer: float
    wer: float
    char_substitutions: int
    char_deletions: int
    char_insertions: int
    word_substitutions: int
    word_deletions: int
    word_insertions: int

    def as_dict(self) -> dict:
        return {
            "attempt_id": self.attempt_id,
            "cer_vs_consensus": self.cer,
            "wer_vs_consensus": self.wer,
            "char_substitutions": self.char_substitutions,
            "char_deletions": self.char_deletions,
            "char_insertions": self.char_insertions,
            "word_substitutions": self.word_substitutions,
            "word_deletions": self.word_deletions,
            "word_insertions": self.word_insertions,
        }


def compare_to_consensus(
    consensus_text: str,
    prepared: Sequence[PreparedText],
    profile: str = DEFAULT_PROFILE,
    tokenizer: str = DEFAULT_TOKENIZER,
) -> List[ConsensusComparison]:
    """Measure every attempt against the consensus (§17).

    The consensus is the reference, so ``cer`` is the disagreement of each
    attempt relative to the consensus text.
    """
    reference = prepare("__consensus__", consensus_text, profile, tokenizer)
    comparisons: List[ConsensusComparison] = []
    for attempt in prepared:
        pair = compare(reference, attempt)
        comparisons.append(
            ConsensusComparison(
                attempt_id=attempt.attempt_id,
                cer=pair.cer_a_to_b if pair.cer_a_to_b is not None else 1.0,
                wer=pair.wer_a_to_b if pair.wer_a_to_b is not None else 1.0,
                char_substitutions=pair.char_substitutions,
                char_deletions=pair.char_deletions,
                char_insertions=pair.char_insertions,
                word_substitutions=pair.word_substitutions,
                word_deletions=pair.word_deletions,
                word_insertions=pair.word_insertions,
            )
        )
    return comparisons


def median_consensus_wer(comparisons: Sequence[ConsensusComparison]) -> Optional[float]:
    """Median WER of the attempts against the consensus, for the §30 summary."""
    if not comparisons:
        return None
    return float(np.median([c.wer for c in comparisons]))
