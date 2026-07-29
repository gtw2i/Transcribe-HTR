"""Assembling a complete consistency analysis.

Spec §22 (small-sample behaviour), §25 (provenance), §30 (research summary).

``build_report`` runs the whole deterministic pipeline — prepare, compare,
matrices, statistics, uncertainty, outliers, narrative — and returns a
``ConsistencyReport`` that serializes to the provenance-bearing record the
export bundle and the ``analyses[]`` array are built from.

Nothing here calls a generative model. Consensus fields are present but unset;
Phase 3 fills them.

This module imports nothing from the rest of the backend.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .attempts import TranscriptionAttempt
from .consensus import (
    CONSENSUS_COMPARISON_CAVEAT,
    METHOD_DETERMINISTIC,
    ConsensusResult,
    compare_to_consensus,
    deterministic_consensus,
    median_consensus_wer,
    select_medoid,
)
from .matrices import (
    AttemptStats,
    DisagreementSummary,
    PairwiseMatrices,
    build_matrices,
    compute_pairs,
    matrix_to_json,
    per_attempt_stats,
    summarize_directional,
    summarize_pairs,
)
from .metrics import PairMetrics, metric_definitions, prepare
from .normalize import (
    DEFAULT_PROFILE,
    DEFAULT_TOKENIZER,
    TOKENIZER_DESCRIPTIONS,
    describe_profile,
)
from .outliers import OutlierReport, OutlierVerdict, detect_outliers
from .uncertainty import (
    JACKKNIFE_METHOD,
    UncertaintyEstimate,
    VariabilityReport,
    describe_variability,
)

#: Bumped whenever a definition changes, so a stored analysis is never
#: reinterpreted under new rules (§25).
ANALYSIS_VERSION = "1.0"


# ── Small-sample behaviour (§22) ──────────────────────────────────────────────

SAMPLE_MINIMAL = "minimal"
SAMPLE_SMALL = "small"
SAMPLE_ADEQUATE = "adequate"


@dataclass(frozen=True)
class SmallSampleGuidance:
    """What can and cannot be concluded at this sample size (§22)."""

    n_attempts: int
    level: str
    message: str
    outlier_detection_available: bool
    uncertainty_available: bool

    def as_dict(self) -> dict:
        return {
            "n_attempts": self.n_attempts,
            "level": self.level,
            "message": self.message,
            "outlier_detection_available": self.outlier_detection_available,
            "uncertainty_available": self.uncertainty_available,
        }


def assess_sample_size(n_attempts: int) -> SmallSampleGuidance:
    """Describe the limits of a given number of replicate attempts (§22)."""
    if n_attempts <= 2:
        return SmallSampleGuidance(
            n_attempts=n_attempts,
            level=SAMPLE_MINIMAL,
            message=(
                "Pairwise CER and WER are calculated, but outlier detection is "
                "not meaningful with two transcription attempts: there is no "
                "independent group against which either can be evaluated."
            ),
            outlier_detection_available=False,
            uncertainty_available=False,
        )
    if n_attempts == 3:
        return SmallSampleGuidance(
            n_attempts=n_attempts,
            level=SAMPLE_SMALL,
            message=(
                "Pairwise analysis and consensus are available, but conclusions "
                "about variability and outliers rest on a small number of "
                "attempts and should be treated as provisional."
            ),
            outlier_detection_available=False,
            uncertainty_available=False,
        )
    return SmallSampleGuidance(
        n_attempts=n_attempts,
        level=SAMPLE_ADEQUATE,
        message=(
            f"Consistency, consensus and outlier analysis are all available for "
            f"{n_attempts} transcription attempts. Repeated transcription of a "
            f"single document supports statements about reproducibility, not "
            f"about how closely any attempt matches the manuscript."
        ),
        outlier_detection_available=True,
        uncertainty_available=True,
    )


# ── Exclusion bookkeeping (§25) ───────────────────────────────────────────────

EXCLUDED_USER = "user_excluded"
EXCLUDED_NOT_REPLICATE = "not_an_independent_attempt"


def _exclusion_reason(attempt: TranscriptionAttempt) -> str:
    if not attempt.is_replicate:
        return EXCLUDED_NOT_REPLICATE
    if not attempt.health.is_suitable:
        return f"health:{attempt.health.status}"
    return EXCLUDED_USER


# ── The report ────────────────────────────────────────────────────────────────


@dataclass
class ConsistencyReport:
    """A complete analysis, with everything needed to reproduce it (§25)."""

    analysis_id: str
    created_at: str
    analysis_version: str
    root: str
    image_filename: Optional[str]

    attempts_included: Tuple[str, ...]
    attempts_excluded: Tuple[Dict[str, str], ...]
    attempt_metadata: Tuple[Dict[str, Any], ...]
    settings: Dict[str, Any]

    matrices: PairwiseMatrices
    pairs: Tuple[PairMetrics, ...]
    summaries: Dict[str, DisagreementSummary]
    directional: Dict[str, Any]
    per_attempt: Tuple[AttemptStats, ...]
    variability: Dict[str, VariabilityReport]
    outliers: OutlierReport
    small_sample: SmallSampleGuidance
    narrative: str

    medoid_attempt_id: Optional[str] = None
    medoid: Optional[Dict[str, Any]] = None
    consensus: Optional[Dict[str, Any]] = None
    consensus_comparison: Optional[List[Dict[str, Any]]] = None
    consensus_caveat: str = CONSENSUS_COMPARISON_CAVEAT
    user_note: str = ""

    @property
    def n_attempts(self) -> int:
        return len(self.attempts_included)

    @property
    def n_pairs(self) -> int:
        return len(self.pairs)

    def as_dict(self) -> dict:
        """The §5.3 record — the machine-readable master for every export."""
        return {
            "analysis_id": self.analysis_id,
            "created_at": self.created_at,
            "analysis_version": self.analysis_version,
            "source_document": {
                "root": self.root,
                "image_filename": self.image_filename,
            },
            "attempts_included": list(self.attempts_included),
            "attempts_excluded": [dict(e) for e in self.attempts_excluded],
            "attempt_metadata": [dict(m) for m in self.attempt_metadata],
            "settings": dict(self.settings),
            "results": {
                "n_attempts": self.n_attempts,
                "n_pairs": self.n_pairs,
                "cer": self.summaries["cer"].as_dict(),
                "wer": self.summaries["wer"].as_dict(),
                "variability": {
                    level: report.as_dict() for level, report in self.variability.items()
                },
                "directional": self.directional,
                "matrix_cer_symmetric": matrix_to_json(self.matrices.cer_symmetric),
                "matrix_wer_symmetric": matrix_to_json(self.matrices.wer_symmetric),
                "matrix_cer_directional": matrix_to_json(self.matrices.cer_directional),
                "matrix_wer_directional": matrix_to_json(self.matrices.wer_directional),
                "pairwise": [p.as_dict() for p in self.pairs],
                "per_attempt": [s.as_dict() for s in self.per_attempt],
                "outliers": self.outliers.as_dict(),
                "small_sample": self.small_sample.as_dict(),
                "medoid_attempt_id": self.medoid_attempt_id,
                "medoid": self.medoid,
                "consensus": self.consensus,
                "consensus_comparison": self.consensus_comparison,
                "consensus_caveat": self.consensus_caveat,
            },
            "narrative": self.narrative,
            "user_note": self.user_note,
        }


# ── Deserialization (round-trip) ──────────────────────────────────────────────


def _matrix_from_json(rows: Sequence[Sequence[Optional[float]]]) -> np.ndarray:
    return np.array(
        [[float("nan") if v is None else float(v) for v in row] for row in rows],
        dtype=float,
    )


def _summary_from_dict(data: dict) -> DisagreementSummary:
    return DisagreementSummary(
        n_attempts=data["n_attempts"],
        n_pairs=data["n_pairs"],
        mean=data["mean"],
        median=data["median"],
        sd=data["sd"],
        iqr_low=data["iqr"][0],
        iqr_high=data["iqr"][1],
        minimum=data["min"],
        maximum=data["max"],
    )


def _uncertainty_from_dict(data: dict) -> UncertaintyEstimate:
    return UncertaintyEstimate(
        method=data["method"],
        label=data["label"],
        description=data["description"],
        value=data["value"],
        applicable=data["applicable"],
        note=data.get("note", ""),
        leave_one_out=data.get("leave_one_out"),
    )


def _variability_from_dict(data: dict) -> VariabilityReport:
    return VariabilityReport(
        central_label=data["central"]["label"],
        central_value=data["central"]["value"],
        spread_label=data["spread"]["label"],
        spread_low=data["spread"]["low"],
        spread_high=data["spread"]["high"],
        sd=data["spread"]["sd"],
        uncertainty=_uncertainty_from_dict(data["uncertainty"]),
    )


def _pair_from_dict(data: dict) -> PairMetrics:
    return PairMetrics(**data)


def _attempt_stats_from_dict(data: dict) -> AttemptStats:
    return AttemptStats(**data)


def _outliers_from_dict(data: dict) -> OutlierReport:
    verdicts = []
    for verdict in data["verdicts"]:
        payload = {k: v for k, v in verdict.items() if k != "is_flagged"}
        payload["notes"] = tuple(payload.get("notes", ()))
        verdicts.append(OutlierVerdict(**payload))
    return OutlierReport(
        applicable=data["applicable"],
        method=data["method"],
        note=data["note"],
        verdicts=tuple(verdicts),
        disclaimer=data["disclaimer"],
        alternative_explanations=tuple(data["alternative_explanations"]),
    )


def report_from_dict(data: dict) -> ConsistencyReport:
    """Rebuild a report from its serialized form.

    ``report_from_dict(r.as_dict()).as_dict() == r.as_dict()`` — the record is
    a faithful representation, which is what makes a saved analysis reloadable
    for the full-set-versus-filtered comparison (§21).
    """
    results = data["results"]
    return ConsistencyReport(
        analysis_id=data["analysis_id"],
        created_at=data["created_at"],
        analysis_version=data["analysis_version"],
        root=data["source_document"]["root"],
        image_filename=data["source_document"]["image_filename"],
        attempts_included=tuple(data["attempts_included"]),
        attempts_excluded=tuple(data["attempts_excluded"]),
        attempt_metadata=tuple(data["attempt_metadata"]),
        settings=data["settings"],
        matrices=PairwiseMatrices(
            attempt_ids=tuple(data["attempts_included"]),
            cer_symmetric=_matrix_from_json(results["matrix_cer_symmetric"]),
            wer_symmetric=_matrix_from_json(results["matrix_wer_symmetric"]),
            cer_directional=_matrix_from_json(results["matrix_cer_directional"]),
            wer_directional=_matrix_from_json(results["matrix_wer_directional"]),
        ),
        pairs=tuple(_pair_from_dict(p) for p in results["pairwise"]),
        summaries={
            "cer": _summary_from_dict(results["cer"]),
            "wer": _summary_from_dict(results["wer"]),
        },
        directional=results["directional"],
        per_attempt=tuple(
            _attempt_stats_from_dict(s) for s in results["per_attempt"]
        ),
        variability={
            level: _variability_from_dict(payload)
            for level, payload in results["variability"].items()
        },
        outliers=_outliers_from_dict(results["outliers"]),
        small_sample=SmallSampleGuidance(**results["small_sample"]),
        narrative=data["narrative"],
        medoid_attempt_id=results.get("medoid_attempt_id"),
        medoid=results.get("medoid"),
        consensus=results.get("consensus"),
        consensus_comparison=results.get("consensus_comparison"),
        consensus_caveat=results.get("consensus_caveat", CONSENSUS_COMPARISON_CAVEAT),
        user_note=data.get("user_note", ""),
    )


# ── Research summary (§30) ────────────────────────────────────────────────────

_COUNT_WORDS = {
    2: "Two",
    3: "Three",
    4: "Four",
    5: "Five",
    6: "Six",
    7: "Seven",
    8: "Eight",
    9: "Nine",
    10: "Ten",
}


def _count_word(n: int) -> str:
    return _COUNT_WORDS.get(n, str(n))


def build_narrative(
    *,
    n_attempts: int,
    summaries: Dict[str, DisagreementSummary],
    variability: Dict[str, VariabilityReport],
    outliers: OutlierReport,
    excluded: Sequence[Dict[str, str]],
    small_sample: SmallSampleGuidance,
    consensus_method: Optional[str] = None,
    consensus_median_wer: Optional[float] = None,
) -> str:
    """A concise summary suitable for a research record (§30).

    Reports the number of attempts, CER and WER consistency, variability,
    unusual attempts, whether anything was excluded, and the consensus method.
    Describes disagreement among replicates throughout; it never characterises
    any of it as accuracy (§28).
    """
    cer, wer = summaries["cer"], summaries["wer"]
    sentences: List[str] = []

    sentences.append(
        f"{_count_word(n_attempts)} independent transcription attempts were "
        f"analyzed across {cer.n_pairs} unique pairwise comparisons."
    )
    sentences.append(
        f"Median pairwise character disagreement was {cer.median:.1%} "
        f"(IQR {cer.iqr_low:.1%}–{cer.iqr_high:.1%}), and median pairwise word "
        f"disagreement was {wer.median:.1%} "
        f"(IQR {wer.iqr_low:.1%}–{wer.iqr_high:.1%})."
    )

    cer_uncertainty = variability["cer"].uncertainty
    if cer_uncertainty.applicable and cer_uncertainty.value is not None:
        sentences.append(
            f"The jackknife standard error of the mean character disagreement, "
            f"resampling over attempts, was {cer_uncertainty.value:.1%}."
        )

    flagged = outliers.flagged
    if not outliers.applicable:
        sentences.append(
            "Outlier analysis was not applicable at this sample size."
        )
    elif not flagged:
        sentences.append(
            "No attempt showed substantially greater disagreement with the "
            "others than the group as a whole."
        )
    else:
        names = ", ".join(v.label for v in flagged)
        plural = "attempts" if len(flagged) > 1 else "attempt"
        strength = (
            "substantially greater"
            if any(v.status == "strong" for v in flagged)
            else "greater"
        )
        sentences.append(
            f"{len(flagged)} {plural} ({names}) showed {strength} disagreement "
            f"with the remaining attempts and {'are' if len(flagged) > 1 else 'is'} "
            f"flagged for inspection rather than treated as incorrect."
        )

    if excluded:
        reasons = sorted({e.get("reason", "unspecified") for e in excluded})
        sentences.append(
            f"{len(excluded)} available transcription "
            f"{'attempts were' if len(excluded) > 1 else 'attempt was'} excluded "
            f"from this analysis ({'; '.join(reasons)})."
        )
    else:
        sentences.append("No available transcription attempts were excluded.")

    if consensus_method:
        if consensus_median_wer is not None:
            sentences.append(
                f"The {consensus_method} consensus transcription had a median "
                f"word disagreement of {consensus_median_wer:.1%} relative to "
                f"the analyzed attempts."
            )
        else:
            sentences.append(
                f"The consensus transcription was produced by the "
                f"{consensus_method} method."
            )
    else:
        sentences.append("No consensus transcription was computed.")

    if small_sample.level != SAMPLE_ADEQUATE:
        sentences.append(small_sample.message)

    sentences.append(
        "These figures describe consistency among repeated transcription "
        "attempts. They do not establish accuracy, which would require a "
        "verified reference transcription."
    )

    return " ".join(sentences)


# ── Orchestration ─────────────────────────────────────────────────────────────


def build_report(
    attempts: Sequence[TranscriptionAttempt],
    selected_ids: Sequence[str],
    *,
    root: str,
    image_filename: Optional[str] = None,
    normalization_profile: str = DEFAULT_PROFILE,
    tokenizer: str = DEFAULT_TOKENIZER,
    analysis_id: Optional[str] = None,
    created_at: Optional[str] = None,
    user_note: str = "",
    with_consensus: bool = True,
) -> ConsistencyReport:
    """Run the full deterministic analysis over the selected attempts.

    *selected_ids* is treated as a set: the canonical attempt order is imposed
    here rather than taken from the caller, so two clients sending the same
    selection in different orders get identical results (D10, §27).

    ``with_consensus`` also computes the medoid and the deterministic consensus,
    which §14 designates the default statistical consensus. It stays optional so
    that the pairwise statistics can be obtained on their own.

    ``analysis_id`` and ``created_at`` are injectable so that tests can assert
    byte-identical output; every other field is a deterministic function of the
    inputs.
    """
    wanted = set(selected_ids)
    unknown = wanted - {a.attempt_id for a in attempts}
    if unknown:
        raise KeyError(f"Unknown attempt id(s): {sorted(unknown)}")

    included = [a for a in attempts if a.attempt_id in wanted]
    excluded = [
        {"attempt_id": a.attempt_id, "label": a.label, "reason": _exclusion_reason(a)}
        for a in attempts
        if a.attempt_id not in wanted
    ]

    prepared = [
        prepare(a.attempt_id, a.text, normalization_profile, tokenizer)
        for a in included
    ]
    pairs = compute_pairs(prepared)
    ids = [p.attempt_id for p in prepared]
    matrices = build_matrices(ids, pairs)

    summaries = summarize_pairs(pairs, len(ids))
    labels = {a.attempt_id: a.label for a in included}
    outlier_report = detect_outliers(matrices, labels)
    small_sample = assess_sample_size(len(ids))

    variability = {
        "cer": describe_variability(summaries["cer"], matrices.cer_symmetric, "cer"),
        "wer": describe_variability(summaries["wer"], matrices.wer_symmetric, "wer"),
    }

    settings = {
        "normalization": describe_profile(normalization_profile),
        "tokenizer": {
            "id": tokenizer,
            "description": TOKENIZER_DESCRIPTIONS.get(tokenizer, ""),
        },
        "uncertainty_method": JACKKNIFE_METHOD,
        **metric_definitions(),
    }

    medoid_result = None
    consensus_result: Optional[ConsensusResult] = None
    comparisons = None
    consensus_wer = None

    if with_consensus:
        medoid_result = select_medoid(matrices)
        consensus_result = deterministic_consensus(prepared, matrices, tokenizer)
        comparisons = compare_to_consensus(
            consensus_result.text, prepared, normalization_profile, tokenizer
        )
        consensus_wer = median_consensus_wer(comparisons)

    narrative = build_narrative(
        n_attempts=len(ids),
        summaries=summaries,
        variability=variability,
        outliers=outlier_report,
        excluded=excluded,
        small_sample=small_sample,
        consensus_method=METHOD_DETERMINISTIC if consensus_result else None,
        consensus_median_wer=consensus_wer,
    )

    return ConsistencyReport(
        analysis_id=analysis_id or str(uuid.uuid4()),
        created_at=created_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        analysis_version=ANALYSIS_VERSION,
        root=root,
        image_filename=image_filename,
        attempts_included=tuple(ids),
        attempts_excluded=tuple(excluded),
        attempt_metadata=tuple(a.as_dict() for a in included),
        settings=settings,
        matrices=matrices,
        pairs=tuple(pairs),
        summaries=summaries,
        directional=summarize_directional(pairs, len(ids)),
        per_attempt=tuple(per_attempt_stats(matrices)),
        variability=variability,
        outliers=outlier_report,
        small_sample=small_sample,
        narrative=narrative,
        medoid_attempt_id=medoid_result.attempt_id if medoid_result else None,
        medoid=medoid_result.as_dict() if medoid_result else None,
        consensus=consensus_result.as_dict() if consensus_result else None,
        consensus_comparison=(
            [c.as_dict() for c in comparisons] if comparisons is not None else None
        ),
        user_note=user_note,
    )
