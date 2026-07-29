"""Pairwise matrices and consistency statistics.

Spec §7 (matrices), §9 (document-level summary), §11 (per-attempt scores).

The primary quantity everywhere is the *symmetric* disagreement (§7.1): the
directional values are computed and retained, but never form the headline
statistic. Summary statistics are taken over the ``N(N-1)/2`` unique unordered
pairs only — counting both directions would treat one comparison as two
independent observations, which §9 explicitly forbids.

This module imports nothing from the rest of the backend.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .metrics import PairMetrics, PreparedText, compare


class InsufficientAttemptsError(ValueError):
    """Fewer than two attempts were selected (§3.2)."""


def n_unique_pairs(n_attempts: int) -> int:
    """``N(N-1)/2`` — the number of unique unordered pairs (§9)."""
    return n_attempts * (n_attempts - 1) // 2


def compute_pairs(prepared: Sequence[PreparedText]) -> List[PairMetrics]:
    """Compare every unique unordered pair, in canonical order.

    Exactly ``n_unique_pairs(len(prepared))`` comparisons are performed — one
    alignment per pair, with the reverse direction derived (see ``metrics``).
    """
    if len(prepared) < 2:
        raise InsufficientAttemptsError(
            f"At least 2 transcription attempts are required; got {len(prepared)}."
        )
    return [compare(a, b) for a, b in combinations(prepared, 2)]


# ── Matrices (§7) ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PairwiseMatrices:
    """The four N x N matrices for one analysis.

    Symmetric matrices are built on the upper triangle and mirrored, so
    ``M[i][j]`` and ``M[j][i]`` are the same float object value — equal
    bitwise, not merely close.

    Directional matrices read **row = reference, column = hypothesis**. A cell
    is ``nan`` where the rate is undefined (empty reference); use
    ``to_json`` to serialize, which converts ``nan`` to ``None``.
    """

    attempt_ids: Tuple[str, ...]
    cer_symmetric: np.ndarray
    wer_symmetric: np.ndarray
    cer_directional: np.ndarray
    wer_directional: np.ndarray

    @property
    def n(self) -> int:
        return len(self.attempt_ids)


def _nan_if_none(value: Optional[float]) -> float:
    return float("nan") if value is None else value


def build_matrices(
    attempt_ids: Sequence[str], pairs: Sequence[PairMetrics]
) -> PairwiseMatrices:
    """Assemble the four matrices from the pair list.

    ``attempt_ids`` fixes the row/column order; every heat map, table and export
    in one analysis uses this same ordering (§8, §19).
    """
    ids = tuple(attempt_ids)
    index = {attempt_id: i for i, attempt_id in enumerate(ids)}
    n = len(ids)

    cer_sym = np.zeros((n, n), dtype=float)
    wer_sym = np.zeros((n, n), dtype=float)
    cer_dir = np.zeros((n, n), dtype=float)
    wer_dir = np.zeros((n, n), dtype=float)

    for pair in pairs:
        i, j = index[pair.a_id], index[pair.b_id]

        # Mirror the identical value into both cells so symmetry is exact.
        cer_sym[i, j] = cer_sym[j, i] = pair.cer_sym
        wer_sym[i, j] = wer_sym[j, i] = pair.wer_sym

        # Row = reference. cer_a_to_b treats A (row i) as the reference.
        cer_dir[i, j] = _nan_if_none(pair.cer_a_to_b)
        cer_dir[j, i] = _nan_if_none(pair.cer_b_to_a)
        wer_dir[i, j] = _nan_if_none(pair.wer_a_to_b)
        wer_dir[j, i] = _nan_if_none(pair.wer_b_to_a)

    # The diagonal is a transcription compared with itself: exactly zero (§7.1).
    np.fill_diagonal(cer_sym, 0.0)
    np.fill_diagonal(wer_sym, 0.0)
    np.fill_diagonal(cer_dir, 0.0)
    np.fill_diagonal(wer_dir, 0.0)

    return PairwiseMatrices(ids, cer_sym, wer_sym, cer_dir, wer_dir)


def matrix_to_json(matrix: np.ndarray) -> List[List[Optional[float]]]:
    """Nested lists with ``None`` in place of ``nan``, safe for JSON."""
    return [[None if math.isnan(v) else float(v) for v in row] for row in matrix]


# ── Summary statistics (§9) ───────────────────────────────────────────────────


@dataclass(frozen=True)
class DisagreementSummary:
    """Document-level statistics over the unique pairs (§9)."""

    n_attempts: int
    n_pairs: int
    mean: float
    median: float
    sd: float
    iqr_low: float
    iqr_high: float
    minimum: float
    maximum: float

    def as_dict(self) -> dict:
        return {
            "n_attempts": self.n_attempts,
            "n_pairs": self.n_pairs,
            "mean": self.mean,
            "median": self.median,
            "sd": self.sd,
            "iqr": [self.iqr_low, self.iqr_high],
            "min": self.minimum,
            "max": self.maximum,
        }


def summarize(values: Sequence[float], n_attempts: int) -> DisagreementSummary:
    """Summarize a sequence of unique-pair disagreement values.

    ``sd`` is the sample standard deviation (ddof=1), and is 0.0 for a single
    pair where it is undefined rather than meaningful.
    """
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        raise InsufficientAttemptsError("No pairwise values to summarize.")

    sd = float(array.std(ddof=1)) if array.size > 1 else 0.0
    q1, q3 = (float(v) for v in np.percentile(array, [25, 75]))

    return DisagreementSummary(
        n_attempts=n_attempts,
        n_pairs=int(array.size),
        mean=float(array.mean()),
        median=float(np.median(array)),
        sd=sd,
        iqr_low=q1,
        iqr_high=q3,
        minimum=float(array.min()),
        maximum=float(array.max()),
    )


def summarize_pairs(
    pairs: Sequence[PairMetrics], n_attempts: int
) -> Dict[str, DisagreementSummary]:
    """CER and WER summaries over the unique pairs.

    Takes the pair list — not a matrix — precisely so that each comparison
    contributes exactly once (§9).
    """
    return {
        "cer": summarize([p.cer_sym for p in pairs], n_attempts),
        "wer": summarize([p.wer_sym for p in pairs], n_attempts),
    }


def summarize_directional(pairs: Sequence[PairMetrics], n_attempts: int) -> dict:
    """Directional values summarized separately (§9, final clause).

    Kept apart from the primary statistics so the two can never be conflated:
    these 2 x n_pairs values are not independent observations.
    """

    def _defined(values):
        return [v for v in values if v is not None]

    cer_values = _defined([p.cer_a_to_b for p in pairs]) + _defined(
        [p.cer_b_to_a for p in pairs]
    )
    wer_values = _defined([p.wer_a_to_b for p in pairs]) + _defined(
        [p.wer_b_to_a for p in pairs]
    )
    return {
        "note": (
            "Directional values, both orientations of every pair. These are not "
            "independent observations and are reported separately from the "
            "primary pairwise statistics."
        ),
        "cer": summarize(cer_values, n_attempts).as_dict() if cer_values else None,
        "wer": summarize(wer_values, n_attempts).as_dict() if wer_values else None,
    }


# ── Per-attempt consistency scores (§11) ──────────────────────────────────────


@dataclass(frozen=True)
class AttemptStats:
    """One attempt's disagreement with all the others (§11)."""

    attempt_id: str
    mean_cer: float
    median_cer: float
    min_cer: float
    max_cer: float
    mean_wer: float
    median_wer: float
    min_wer: float
    max_wer: float

    def as_dict(self) -> dict:
        return {
            "attempt_id": self.attempt_id,
            "mean_cer": self.mean_cer,
            "median_cer": self.median_cer,
            "min_cer": self.min_cer,
            "max_cer": self.max_cer,
            "mean_wer": self.mean_wer,
            "median_wer": self.median_wer,
            "min_wer": self.min_wer,
            "max_wer": self.max_wer,
        }


def _off_diagonal(matrix: np.ndarray, i: int) -> np.ndarray:
    """Row *i* with its diagonal cell removed."""
    return np.delete(matrix[i], i)


def per_attempt_stats(matrices: PairwiseMatrices) -> List[AttemptStats]:
    """Mean/median/min/max disagreement of each attempt against the others.

    An attempt that disagrees strongly with most others is identifiable here
    even when the remaining attempts agree closely among themselves (§11) —
    the score is over that attempt's whole row, not a single comparison.
    """
    if matrices.n < 2:
        raise InsufficientAttemptsError(
            "Per-attempt statistics require at least 2 attempts."
        )

    stats: List[AttemptStats] = []
    for i, attempt_id in enumerate(matrices.attempt_ids):
        cer = _off_diagonal(matrices.cer_symmetric, i)
        wer = _off_diagonal(matrices.wer_symmetric, i)
        stats.append(
            AttemptStats(
                attempt_id=attempt_id,
                mean_cer=float(cer.mean()),
                median_cer=float(np.median(cer)),
                min_cer=float(cer.min()),
                max_cer=float(cer.max()),
                mean_wer=float(wer.mean()),
                median_wer=float(np.median(wer)),
                min_wer=float(wer.min()),
                max_wer=float(wer.max()),
            )
        )
    return stats


def mean_disagreement_vector(matrices: PairwiseMatrices, level: str = "cer") -> np.ndarray:
    """Each attempt's *mean* symmetric disagreement with the others.

    This is the aggregate criterion for medoid selection (§15, Phase 3), where
    §15 asks for the lowest total disagreement with the rest of the set.
    """
    matrix = matrices.cer_symmetric if level == "cer" else matrices.wer_symmetric
    return np.array(
        [_off_diagonal(matrix, i).mean() for i in range(matrices.n)], dtype=float
    )


def median_disagreement_vector(
    matrices: PairwiseMatrices, level: str = "cer"
) -> np.ndarray:
    """Each attempt's *median* symmetric disagreement with the others.

    This is the input to outlier detection (§12). The median is used rather
    than the mean because §12 asks whether an attempt's *pattern* of
    disagreement differs from the group, judged against all the others rather
    than any single pairwise comparison — and a mean can be dragged upward by
    one aberrant pair.

    Concretely, for a group agreeing at 0.05 with a single anomalous pair at
    0.55, the two attempts in that pair have row means of 0.15 against a group
    of 0.05 and would be flagged, though neither is out of step with the group
    as a whole; their row medians remain 0.05. For a genuinely divergent
    attempt the median also separates it more sharply than the mean, because
    the others' means are inflated by their comparisons *with* the outlier.
    """
    matrix = matrices.cer_symmetric if level == "cer" else matrices.wer_symmetric
    return np.array(
        [float(np.median(_off_diagonal(matrix, i))) for i in range(matrices.n)],
        dtype=float,
    )


# ── Heat-map specification (§8, D5) ───────────────────────────────────────────


@dataclass(frozen=True)
class HeatmapSpec:
    """Everything both renderers need, computed once so they cannot diverge.

    The colour domain is clipped at a high percentile of the off-diagonal
    values so that one extreme pair cannot flatten the rest of the map (§8).
    Clipping is presentational only: ``values`` are the true numbers, and the
    raw maximum is reported alongside so the UI can label the off-scale cells.
    """

    attempt_ids: Tuple[str, ...]
    values: List[List[float]]
    vmin: float
    vmax: float
    raw_max: float
    clipped: bool
    clip_percentile: float
    label: str

    def as_dict(self) -> dict:
        return {
            "attempt_ids": list(self.attempt_ids),
            "values": self.values,
            "vmin": self.vmin,
            "vmax": self.vmax,
            "raw_max": self.raw_max,
            "clipped": self.clipped,
            "clip_percentile": self.clip_percentile,
            "label": self.label,
        }


#: Minimum colour-domain span, so a set of near-identical transcriptions does
#: not get a domain of width ~0 that amplifies floating-point noise into a
#: dramatic-looking map.
MIN_COLOR_SPAN = 1e-4


def heatmap_spec(
    matrices: PairwiseMatrices,
    level: str = "cer",
    percentile: float = 95.0,
) -> HeatmapSpec:
    """Build the render spec for one symmetric matrix."""
    if level == "cer":
        matrix = matrices.cer_symmetric
        label = "Pairwise CER disagreement"
    elif level == "wer":
        matrix = matrices.wer_symmetric
        label = "Pairwise WER disagreement"
    else:
        raise ValueError(f"level must be 'cer' or 'wer', got {level!r}")

    n = matrices.n
    off_diag = np.array(
        [matrix[i, j] for i in range(n) for j in range(n) if i != j], dtype=float
    )

    raw_max = float(off_diag.max()) if off_diag.size else 0.0
    cap = float(np.percentile(off_diag, percentile)) if off_diag.size else 0.0
    vmax = max(cap, MIN_COLOR_SPAN)

    return HeatmapSpec(
        attempt_ids=matrices.attempt_ids,
        values=[[float(v) for v in row] for row in matrix],
        vmin=0.0,
        vmax=vmax,
        raw_max=raw_max,
        clipped=raw_max > vmax,
        clip_percentile=percentile,
        label=label,
    )
