"""Outlier identification among replicate transcription attempts.

Spec §12. An outlier is an attempt whose *pattern* of disagreement with the
others is substantially different from the group — judged against every other
selected attempt, never against a single pairwise comparison.

Method: a robust score on each attempt's **median** symmetric disagreement with
the others, using the group median and MAD rather than mean and SD, so that the
outlier being looked for does not inflate the very dispersion estimate used to
find it.

Four deliberate conservatisms:

* the scored statistic is each attempt's median disagreement, not its mean, so a single aberrant pair cannot make two otherwise-typical attempts look anomalous (see ``matrices.median_disagreement_vector``);
* only the high side is flagged — an attempt that agrees *unusually well* is not an outlier;
* CER and WER must independently agree before an attempt is flagged, so a quirk of one metric alone cannot produce a verdict;
* an absolute floor applies, so an attempt that is close to the group in real terms is never flagged however extreme its relative score.

Outlier status is **diagnostic information, not proof that a transcription is
incorrect** (§12). Every message here is phrased as disagreement with the group
and ships alongside the alternative explanations below.

This module imports nothing from the rest of the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .matrices import (
    PairwiseMatrices,
    mean_disagreement_vector,
    median_disagreement_vector,
)

# ── Status vocabulary (§12) ───────────────────────────────────────────────────

STATUS_NONE = "none"
STATUS_POSSIBLE = "possible"
STATUS_STRONG = "strong"

_SEVERITY = {STATUS_NONE: 0, STATUS_POSSIBLE: 1, STATUS_STRONG: 2}
_BY_SEVERITY = {v: k for k, v in _SEVERITY.items()}

#: Minimum attempts for outlier analysis to mean anything. With two attempts
#: there is no independent group to judge either against; with three, a single
#: attempt is being compared against a "group" of two (§22).
MIN_ATTEMPTS_FOR_OUTLIERS = 4

#: Modified z-score thresholds, on the median/MAD scale.
Z_POSSIBLE = 2.5
Z_STRONG = 3.5

#: Fallback thresholds, as a ratio to the group median, used when the MAD is
#: zero — which happens when most attempts are identical, so that the usual
#: scale estimate collapses.
RATIO_POSSIBLE = 1.5
RATIO_STRONG = 2.5

#: Absolute floors, below which an attempt is never flagged however large its
#: score. §12 asks for attempts "substantially different from the group", and a
#: disagreement of a couple of percent is not substantial on any practical
#: reading.
#:
#: These matter because of the ratio fallback above: when most attempts are
#: byte-identical the group median is near zero, so an attempt differing by a
#: single punctuation mark has a large *ratio* while being trivially close in
#: absolute terms. Applying the floor can only ever remove a flag, so it cannot
#: suppress a genuine outlier.
MIN_ABSOLUTE_CER = 0.02
MIN_ABSOLUTE_WER = 0.05

#: 0.6745 is the 75th percentile of the standard normal: it puts the MAD on the
#: same scale as a standard deviation for normally distributed data.
_MAD_TO_SIGMA = 0.6745

METHOD_MAD = "robust_z_median_mad"
METHOD_RATIO = "ratio_to_median"
#: Used when the group agrees *exactly* — median and MAD both zero — so neither
#: a z-score nor a ratio is defined. Any disagreement at all then stands out,
#: and the absolute floor becomes the classifier.
METHOD_ABSOLUTE = "absolute_when_group_agrees_exactly"

#: Shipped verbatim from §12 — an outlier verdict must never be presented as a
#: judgement about correctness, and these are the reasons why.
ALTERNATIVE_EXPLANATIONS: Tuple[str, ...] = (
    "the model produced a poor transcription",
    "the transcription captured text omitted by other runs",
    "the document contains genuinely ambiguous handwriting",
    "preprocessing differed",
    "the input document differed",
    "a model systematically interpreted the document differently",
)

DIAGNOSTIC_DISCLAIMER = (
    "Outlier status is diagnostic information about disagreement with the "
    "group. It is not evidence that a transcription is incorrect. Inspect the "
    "differences before drawing any conclusion."
)


@dataclass(frozen=True)
class MetricScores:
    """Robust scores for one metric across all attempts."""

    method: str
    median: float
    scale: float
    values: Tuple[float, ...]
    scores: Tuple[float, ...]
    statuses: Tuple[str, ...]


def _classify(score: float, method: str, floor: float) -> str:
    if method == METHOD_MAD:
        if score >= Z_STRONG:
            return STATUS_STRONG
        if score >= Z_POSSIBLE:
            return STATUS_POSSIBLE
        return STATUS_NONE
    if method == METHOD_ABSOLUTE:
        if score >= 2 * floor:
            return STATUS_STRONG
        if score >= floor:
            return STATUS_POSSIBLE
        return STATUS_NONE
    if score >= RATIO_STRONG:
        return STATUS_STRONG
    if score >= RATIO_POSSIBLE:
        return STATUS_POSSIBLE
    return STATUS_NONE


def robust_scores(values: Sequence[float], floor: float = 0.0) -> MetricScores:
    """Score each attempt's median disagreement against the group.

    Three regimes, in order of preference:

    1. ``MAD > 0`` — the modified z-score ``0.6745 * (x - median) / MAD``.
    2. ``MAD == 0`` but the median is positive — the scale estimate has
       collapsed because most attempts agree exactly, so the ratio
       ``x / median`` is used instead.
    3. ``MAD == 0`` and the median is zero — the group agrees *perfectly*.
       Neither a z-score nor a ratio is defined, but this is the clearest
       outlier case there is: everyone agrees and one attempt does not. The raw
       disagreement becomes the score and *floor* classifies it.

    Without regime 3 a set of byte-identical attempts plus one wildly divergent
    one would produce no flag at all.
    """
    array = np.asarray(list(values), dtype=float)
    median = float(np.median(array))
    mad = float(np.median(np.abs(array - median)))

    if mad > 0:
        method = METHOD_MAD
        scores = _MAD_TO_SIGMA * (array - median) / mad
    elif median > 0:
        method = METHOD_RATIO
        scores = array / median
    else:
        method = METHOD_ABSOLUTE
        scores = array.copy()

    # Only the high side is flagged.
    statuses = tuple(
        _classify(float(score), method, floor) if score > 0 else STATUS_NONE
        for score in scores
    )
    return MetricScores(
        method=method,
        median=median,
        scale=mad,
        values=tuple(float(v) for v in array),
        scores=tuple(float(s) for s in scores),
        statuses=statuses,
    )


@dataclass(frozen=True)
class OutlierVerdict:
    """One attempt's outlier assessment (§12)."""

    attempt_id: str
    label: str
    status: str
    cer_status: str
    wer_status: str
    cer_score: float
    wer_score: float
    #: The scored statistic: this attempt's median disagreement with the others.
    median_cer: float
    median_wer: float
    #: Reported alongside for display; not what the score is computed from.
    mean_cer: float
    mean_wer: float
    group_median_cer: float
    group_median_wer: float
    message: str
    notes: Tuple[str, ...] = ()

    @property
    def is_flagged(self) -> bool:
        return self.status != STATUS_NONE

    def as_dict(self) -> dict:
        return {
            "attempt_id": self.attempt_id,
            "label": self.label,
            "status": self.status,
            "cer_status": self.cer_status,
            "wer_status": self.wer_status,
            "cer_score": self.cer_score,
            "wer_score": self.wer_score,
            "median_cer": self.median_cer,
            "median_wer": self.median_wer,
            "mean_cer": self.mean_cer,
            "mean_wer": self.mean_wer,
            "group_median_cer": self.group_median_cer,
            "group_median_wer": self.group_median_wer,
            "message": self.message,
            "notes": list(self.notes),
            "is_flagged": self.is_flagged,
        }


@dataclass(frozen=True)
class OutlierReport:
    """Outlier analysis for one selection of attempts."""

    applicable: bool
    method: str
    note: str
    verdicts: Tuple[OutlierVerdict, ...]
    disclaimer: str = DIAGNOSTIC_DISCLAIMER
    alternative_explanations: Tuple[str, ...] = ALTERNATIVE_EXPLANATIONS

    @property
    def flagged(self) -> List[OutlierVerdict]:
        return [v for v in self.verdicts if v.is_flagged]

    @property
    def flagged_ids(self) -> List[str]:
        return [v.attempt_id for v in self.flagged]

    def as_dict(self) -> dict:
        return {
            "applicable": self.applicable,
            "method": self.method,
            "note": self.note,
            "verdicts": [v.as_dict() for v in self.verdicts],
            "flagged_ids": self.flagged_ids,
            "disclaimer": self.disclaimer,
            "alternative_explanations": list(self.alternative_explanations),
        }


def _describe(label: str, status: str, attempt_cer: float, group_cer: float,
              score: float, method: str) -> str:
    """Diagnostic wording (§12) — disagreement with the group, never a verdict."""
    if status == STATUS_NONE:
        return f"{label} is consistent with the rest of the group."

    strength = "substantially greater" if status == STATUS_STRONG else "greater"
    scale = "robust z" if method == METHOD_MAD else "ratio to group median"
    return (
        f"{label} shows {strength} disagreement with the remaining transcription "
        f"attempts (median pairwise CER {attempt_cer:.1%} against a group median "
        f"of {group_cer:.1%}; {scale} = {score:.1f})."
    )


def detect_outliers(
    matrices: PairwiseMatrices,
    labels: Optional[Dict[str, str]] = None,
) -> OutlierReport:
    """Assess every attempt in *matrices* for anomalous disagreement (§12).

    An attempt is flagged only when CER and WER independently reach at least
    "possible"; where they disagree the verdict takes the weaker of the two and
    records why. Below ``MIN_ATTEMPTS_FOR_OUTLIERS`` attempts nothing is
    flagged and the report says why (§22).

    Scoring uses each attempt's median disagreement with the others; the means
    are carried through for display only.
    """
    label_for = labels or {}
    ids = matrices.attempt_ids
    n = len(ids)

    cer_medians = median_disagreement_vector(matrices, "cer")
    wer_medians = median_disagreement_vector(matrices, "wer")
    cer_means = mean_disagreement_vector(matrices, "cer")
    wer_means = mean_disagreement_vector(matrices, "wer")

    if n < MIN_ATTEMPTS_FOR_OUTLIERS:
        note = (
            f"Outlier detection is not meaningful with {n} transcription "
            f"attempts: there is no independent group to evaluate an attempt "
            f"against. At least {MIN_ATTEMPTS_FOR_OUTLIERS} attempts are needed."
        )
        verdicts = tuple(
            OutlierVerdict(
                attempt_id=attempt_id,
                label=label_for.get(attempt_id, attempt_id),
                status=STATUS_NONE,
                cer_status=STATUS_NONE,
                wer_status=STATUS_NONE,
                cer_score=0.0,
                wer_score=0.0,
                median_cer=float(cer_medians[i]),
                median_wer=float(wer_medians[i]),
                mean_cer=float(cer_means[i]),
                mean_wer=float(wer_means[i]),
                group_median_cer=float(np.median(cer_medians)),
                group_median_wer=float(np.median(wer_medians)),
                message=note,
            )
            for i, attempt_id in enumerate(ids)
        )
        return OutlierReport(False, METHOD_MAD, note, verdicts)

    cer = robust_scores(cer_medians, MIN_ABSOLUTE_CER)
    wer = robust_scores(wer_medians, MIN_ABSOLUTE_WER)

    verdicts: List[OutlierVerdict] = []
    floored_any = False
    for i, attempt_id in enumerate(ids):
        label = label_for.get(attempt_id, attempt_id)
        cer_status, wer_status = cer.statuses[i], wer.statuses[i]

        notes: List[str] = []

        # Absolute floor: however extreme the score, an attempt that is close to
        # the group in absolute terms is not "substantially different" (§12).
        floored = []
        if cer_status != STATUS_NONE and cer.values[i] < MIN_ABSOLUTE_CER:
            cer_status = STATUS_NONE
            floored.append(f"CER {cer.values[i]:.1%} < {MIN_ABSOLUTE_CER:.0%}")
        if wer_status != STATUS_NONE and wer.values[i] < MIN_ABSOLUTE_WER:
            wer_status = STATUS_NONE
            floored.append(f"WER {wer.values[i]:.1%} < {MIN_ABSOLUTE_WER:.0%}")
        if floored:
            floored_any = True
            notes.append(
                "Score is high relative to the group, but the disagreement is "
                "too small in absolute terms to be substantial ("
                + "; ".join(floored)
                + ")."
            )

        severities = (_SEVERITY[cer_status], _SEVERITY[wer_status])
        status = _BY_SEVERITY[min(severities)]

        if min(severities) != max(severities):
            higher = "CER" if severities[0] > severities[1] else "WER"
            lower = "WER" if higher == "CER" else "CER"
            notes.append(
                f"{higher} alone would flag this attempt more strongly; {lower} "
                f"does not agree, so the verdict is the weaker of the two."
            )

        verdicts.append(
            OutlierVerdict(
                attempt_id=attempt_id,
                label=label,
                status=status,
                cer_status=cer_status,
                wer_status=wer_status,
                cer_score=cer.scores[i],
                wer_score=wer.scores[i],
                median_cer=cer.values[i],
                median_wer=wer.values[i],
                mean_cer=float(cer_means[i]),
                mean_wer=float(wer_means[i]),
                group_median_cer=cer.median,
                group_median_wer=wer.median,
                message=_describe(
                    label, status, cer.values[i], cer.median, cer.scores[i], cer.method
                ),
                notes=tuple(notes),
            )
        )

    method_note = (
        "Each attempt's median symmetric disagreement with all others is scored "
        "against the group median using the median absolute deviation. The "
        "median is used rather than the mean so that a single aberrant pair "
        "cannot make two otherwise-typical attempts look anomalous. CER and "
        "WER must independently agree before an attempt is flagged."
    )
    if cer.method == METHOD_RATIO or wer.method == METHOD_RATIO:
        method_note += (
            " The median absolute deviation was zero for at least one metric "
            "(most attempts agree exactly), so the ratio to the group median "
            "was used instead."
        )
    if cer.method == METHOD_ABSOLUTE or wer.method == METHOD_ABSOLUTE:
        method_note += (
            " The remaining attempts agree exactly for at least one metric, so "
            "neither a z-score nor a ratio is defined; any disagreement above "
            "the absolute threshold was scored directly."
        )
    if floored_any:
        method_note += (
            f" Attempts disagreeing by less than {MIN_ABSOLUTE_CER:.0%} (CER) or "
            f"{MIN_ABSOLUTE_WER:.0%} (WER) in absolute terms were not flagged, "
            f"however high their relative score."
        )

    return OutlierReport(True, cer.method, method_note, tuple(verdicts))
