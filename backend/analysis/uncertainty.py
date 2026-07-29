"""Uncertainty estimation for replicate transcription experiments.

Spec §10. Pairwise comparisons share transcription attempts, so the
``N(N-1)/2`` pairwise values are **not** independent observations: an ordinary
standard error over the pairwise cells would overstate precision, and §10
explicitly forbids implying otherwise.

The resampling unit here is therefore the **attempt**, not the pair. Leaving one
attempt out removes all ``N-1`` of its comparisons at once, which is what
respects the shared-attempt dependency.

Three quantities are reported and never merged into an unlabelled "±" (§10):

* central tendency  — median / mean pairwise disagreement;
* variability       — IQR and SD across the unique pairs;
* uncertainty       — jackknife standard error of the aggregate.

The jackknife is fully deterministic: no RNG is involved anywhere in this
module, which keeps the reproducibility requirement (§27) clean.

This module imports nothing from the rest of the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

#: Below this many attempts the jackknife is not reported. With three attempts
#: each leave-one-out replicate rests on a single pair, which produces a number
#: that looks like a standard error but carries almost no information (§22).
MIN_ATTEMPTS_FOR_UNCERTAINTY = 4

JACKKNIFE_METHOD = "jackknife_over_attempts"

JACKKNIFE_LABEL = "Jackknife SE (resampling over attempts)"

JACKKNIFE_DESCRIPTION = (
    "Standard error of the mean pairwise disagreement, estimated by leaving out "
    "each transcription attempt in turn and recomputing over the remaining "
    "pairs. The resampling unit is the attempt, not the pair, because pairwise "
    "comparisons share attempts and are not independent observations."
)


@dataclass(frozen=True)
class UncertaintyEstimate:
    """An uncertainty figure that always says what it represents (§10)."""

    method: str
    label: str
    description: str
    value: Optional[float]
    applicable: bool
    note: str = ""
    leave_one_out: Optional[List[float]] = None

    def as_dict(self) -> dict:
        return {
            "method": self.method,
            "label": self.label,
            "description": self.description,
            "value": self.value,
            "applicable": self.applicable,
            "note": self.note,
            "leave_one_out": (
                list(self.leave_one_out) if self.leave_one_out is not None else None
            ),
        }


def _off_diagonal_mean(matrix: np.ndarray) -> float:
    """Mean over the unique off-diagonal pairs of a symmetric matrix."""
    n = matrix.shape[0]
    upper = matrix[np.triu_indices(n, k=1)]
    return float(upper.mean())


def leave_one_out_means(matrix: np.ndarray) -> List[float]:
    """Mean pairwise disagreement with each attempt removed in turn.

    Dropping attempt *i* removes its whole row and column — all ``N-1``
    comparisons it participates in — leaving the ``(N-1)(N-2)/2`` pairs among
    the others.
    """
    n = matrix.shape[0]
    estimates: List[float] = []
    for i in range(n):
        reduced = np.delete(np.delete(matrix, i, axis=0), i, axis=1)
        estimates.append(_off_diagonal_mean(reduced))
    return estimates


def jackknife_se(matrix: np.ndarray) -> UncertaintyEstimate:
    """Jackknife standard error of the mean pairwise disagreement.

    ``SE = sqrt( (n-1)/n * sum_i (theta_i - theta_bar)^2 )`` where ``theta_i``
    is the mean over the pairs remaining after dropping attempt *i*.

    Returns a non-applicable estimate, with an explanatory note rather than a
    number, when there are too few attempts for the figure to mean anything
    (§22).
    """
    n = int(matrix.shape[0])

    if n < MIN_ATTEMPTS_FOR_UNCERTAINTY:
        return UncertaintyEstimate(
            method=JACKKNIFE_METHOD,
            label=JACKKNIFE_LABEL,
            description=JACKKNIFE_DESCRIPTION,
            value=None,
            applicable=False,
            note=(
                f"Not estimated: {n} transcription attempts is too few for a "
                f"resampling-based interval (at least "
                f"{MIN_ATTEMPTS_FOR_UNCERTAINTY} are needed). The reported "
                f"spread across pairs describes this sample only."
            ),
        )

    estimates = leave_one_out_means(matrix)
    theta = np.asarray(estimates, dtype=float)
    theta_bar = float(theta.mean())
    se = float(np.sqrt((n - 1) / n * np.sum((theta - theta_bar) ** 2)))

    return UncertaintyEstimate(
        method=JACKKNIFE_METHOD,
        label=JACKKNIFE_LABEL,
        description=JACKKNIFE_DESCRIPTION,
        value=se,
        applicable=True,
        leave_one_out=estimates,
    )


@dataclass(frozen=True)
class VariabilityReport:
    """The three §10 quantities, each separately labelled.

    Assembled so that a caller cannot render a bare "±": every field carries
    its own label, and ``summary_sentence`` produces prose that names the
    measure it is quoting.
    """

    central_label: str
    central_value: float
    spread_label: str
    spread_low: float
    spread_high: float
    sd: float
    uncertainty: UncertaintyEstimate

    def as_dict(self) -> dict:
        return {
            "central": {"label": self.central_label, "value": self.central_value},
            "spread": {
                "label": self.spread_label,
                "low": self.spread_low,
                "high": self.spread_high,
                "sd": self.sd,
            },
            "uncertainty": self.uncertainty.as_dict(),
        }

    def summary_sentence(self) -> str:
        text = (
            f"{self.central_label} {self.central_value:.1%}, "
            f"{self.spread_label} {self.spread_low:.1%}–{self.spread_high:.1%}"
        )
        if self.uncertainty.applicable and self.uncertainty.value is not None:
            text += f", {self.uncertainty.label} {self.uncertainty.value:.1%}"
        return text


def describe_variability(summary, matrix: np.ndarray, level: str) -> VariabilityReport:
    """Build the §10 triple from a ``DisagreementSummary`` and its matrix.

    *summary* is a ``matrices.DisagreementSummary``; it is duck-typed here so
    this module stays independent of the matrices module.
    """
    metric = level.upper()
    return VariabilityReport(
        central_label=f"Median pairwise {metric} disagreement",
        central_value=summary.median,
        spread_label=f"IQR across {summary.n_pairs} pairs",
        spread_low=summary.iqr_low,
        spread_high=summary.iqr_high,
        sd=summary.sd,
        uncertainty=jackknife_se(matrix),
    )
