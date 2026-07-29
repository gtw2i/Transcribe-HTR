"""Outlier identification (spec §12, §22)."""

import numpy as np
import pytest

from backend.analysis import matrices as mx
from backend.analysis import outliers as ol

pytestmark = pytest.mark.unit


def _matrices_from(cer: np.ndarray, wer: np.ndarray = None) -> mx.PairwiseMatrices:
    """Build matrices directly so the disagreement structure is exactly controlled."""
    wer = cer if wer is None else wer
    n = cer.shape[0]
    ids = tuple(f"a{i}" for i in range(n))
    zeros = np.zeros((n, n))
    return mx.PairwiseMatrices(ids, cer.copy(), wer.copy(), zeros, zeros)


def _tight_group(n=5, level=0.04):
    matrix = np.full((n, n), level)
    np.fill_diagonal(matrix, 0.0)
    return matrix


def _with_outlier(n=5, level=0.04, outlier_level=0.60, index=None):
    index = n - 1 if index is None else index
    matrix = _tight_group(n, level)
    matrix[index, :] = outlier_level
    matrix[:, index] = outlier_level
    np.fill_diagonal(matrix, 0.0)
    return matrix


# ── Robust scoring ────────────────────────────────────────────────────────────


def test_robust_scores_use_median_and_mad():
    scores = ol.robust_scores([0.04, 0.05, 0.06, 0.045, 0.60])
    assert scores.method == ol.METHOD_MAD
    assert scores.median == pytest.approx(0.05)
    assert scores.scores[4] > scores.scores[0]
    assert scores.statuses[4] == ol.STATUS_STRONG


def test_mad_of_zero_falls_back_to_a_ratio_rule():
    """Most attempts identical collapses the usual scale estimate."""
    scores = ol.robust_scores([0.10, 0.10, 0.10, 0.10, 0.50])
    assert scores.method == ol.METHOD_RATIO
    assert scores.scores[4] == pytest.approx(5.0)


def test_all_zero_disagreement_produces_no_scores_and_no_crash():
    scores = ol.robust_scores([0.0, 0.0, 0.0, 0.0], ol.MIN_ABSOLUTE_CER)
    assert all(s == 0.0 for s in scores.scores)
    assert all(s == ol.STATUS_NONE for s in scores.statuses)


def test_a_perfectly_agreeing_group_still_identifies_a_divergent_attempt():
    """Neither a z-score nor a ratio is defined when the group agrees exactly,
    but this is the clearest outlier case there is."""
    scores = ol.robust_scores([0.0, 0.0, 0.0, 0.0, 0.40], ol.MIN_ABSOLUTE_CER)
    assert scores.method == ol.METHOD_ABSOLUTE
    assert scores.statuses[4] == ol.STATUS_STRONG
    assert scores.statuses[0] == ol.STATUS_NONE


def test_only_the_high_side_is_flagged():
    """An attempt that agrees unusually *well* is not an outlier."""
    scores = ol.robust_scores([0.001, 0.40, 0.42, 0.41, 0.43])
    assert scores.statuses[0] == ol.STATUS_NONE


# ── Detection (§12) ───────────────────────────────────────────────────────────


def test_a_divergent_attempt_among_four_agreeing_ones_is_flagged():
    report = ol.detect_outliers(_matrices_from(_with_outlier()))
    assert report.applicable is True
    assert report.flagged_ids == ["a4"]
    assert report.verdicts[4].status in (ol.STATUS_POSSIBLE, ol.STATUS_STRONG)


def test_a_homogeneous_group_flags_nobody():
    report = ol.detect_outliers(_matrices_from(_tight_group()))
    assert report.applicable is True
    assert report.flagged_ids == []


def test_identical_attempts_do_not_crash_detection():
    matrix = np.zeros((5, 5))
    report = ol.detect_outliers(_matrices_from(matrix))
    assert report.flagged_ids == []


def test_detection_considers_the_whole_group_not_one_pairwise_comparison():
    """§12 — one large cell between two otherwise-typical attempts is not an
    outlier; sustained disagreement with everyone is.

    Scoring on row means would flag both members of the aberrant pair (their
    means rise to 0.15 against a group of 0.05); scoring on row medians leaves
    every attempt at 0.05.
    """
    matrix = _tight_group(6, 0.05)
    matrix[0, 1] = matrix[1, 0] = 0.55  # a single divergent pair
    np.fill_diagonal(matrix, 0.0)
    report = ol.detect_outliers(_matrices_from(matrix))
    assert report.flagged_ids == []


def test_the_scored_statistic_is_the_median_not_the_mean():
    matrix = _tight_group(6, 0.05)
    matrix[0, 1] = matrix[1, 0] = 0.55
    np.fill_diagonal(matrix, 0.0)
    verdict = ol.detect_outliers(_matrices_from(matrix)).verdicts[0]
    assert verdict.median_cer == pytest.approx(0.05)
    assert verdict.mean_cer == pytest.approx(0.15)
    assert verdict.status == ol.STATUS_NONE


def test_the_method_note_explains_why_the_median_is_used():
    report = ol.detect_outliers(_matrices_from(_with_outlier()))
    assert "median is used rather than the mean" in report.note


# ── Absolute floor (§12) ──────────────────────────────────────────────────────


def test_a_trivially_small_disagreement_is_never_flagged():
    """Four identical attempts and one differing by a hair: the ratio rule makes
    the score enormous, but 1% disagreement is not 'substantially different'."""
    matrix = np.zeros((5, 5))
    matrix[4, :] = matrix[:, 4] = 0.01
    np.fill_diagonal(matrix, 0.0)
    report = ol.detect_outliers(_matrices_from(matrix))
    assert report.flagged_ids == []


def _barely_different():
    """Group agreeing at 0.5%, one attempt at 1.5%.

    The MAD collapses to zero so the ratio rule applies and scores that attempt
    at 3x the group median — a strong relative signal from an absolute
    difference of one percentage point.
    """
    matrix = np.full((5, 5), 0.005)
    matrix[4, :] = matrix[:, 4] = 0.015
    np.fill_diagonal(matrix, 0.0)
    return matrix


def test_the_ratio_rule_alone_would_flag_a_one_percent_difference():
    """Establishes that the floor is doing real work in the test below."""
    medians = mx.median_disagreement_vector(_matrices_from(_barely_different()), "cer")
    assert ol.robust_scores(medians).statuses[4] == ol.STATUS_STRONG


def test_the_floored_attempt_records_why_it_was_not_flagged():
    verdict = ol.detect_outliers(_matrices_from(_barely_different())).verdicts[4]
    assert verdict.status == ol.STATUS_NONE
    assert any("too small in absolute terms" in note for note in verdict.notes)


def test_the_method_note_reports_that_a_floor_was_applied():
    report = ol.detect_outliers(_matrices_from(_barely_different()))
    assert "in absolute terms were not flagged" in report.note


def test_a_disagreement_above_the_floor_is_still_flagged():
    """The floor removes noise, not genuine outliers."""
    matrix = np.zeros((5, 5))
    matrix[4, :] = matrix[:, 4] = 0.40
    np.fill_diagonal(matrix, 0.0)
    report = ol.detect_outliers(_matrices_from(matrix))
    assert report.flagged_ids == ["a4"]


def test_the_floor_only_ever_removes_flags():
    """Applied to a clearly divergent group it changes nothing."""
    matrix = _with_outlier(outlier_level=0.60)
    assert ol.detect_outliers(_matrices_from(matrix)).flagged_ids == ["a4"]


def test_the_floor_applies_per_metric():
    """CER above its floor but WER below its own still suppresses the flag,
    because both metrics must agree."""
    cer = np.zeros((5, 5))
    cer[4, :] = cer[:, 4] = 0.30
    np.fill_diagonal(cer, 0.0)
    wer = np.zeros((5, 5))
    wer[4, :] = wer[:, 4] = 0.02  # below MIN_ABSOLUTE_WER
    np.fill_diagonal(wer, 0.0)
    report = ol.detect_outliers(_matrices_from(cer, wer))
    assert report.flagged_ids == []


def test_a_more_extreme_attempt_earns_the_stronger_status():
    mild = ol.detect_outliers(_matrices_from(_with_outlier(outlier_level=0.12)))
    severe = ol.detect_outliers(_matrices_from(_with_outlier(outlier_level=0.90)))
    assert ol._SEVERITY[severe.verdicts[4].status] >= ol._SEVERITY[mild.verdicts[4].status]
    assert severe.verdicts[4].status == ol.STATUS_STRONG


# ── CER and WER must agree ────────────────────────────────────────────────────


def test_both_metrics_must_agree_before_an_attempt_is_flagged():
    cer = _with_outlier()  # a4 is divergent on CER
    wer = _tight_group()  # ...but not on WER
    report = ol.detect_outliers(_matrices_from(cer, wer))
    assert report.flagged_ids == []


def test_a_single_metric_flag_is_downgraded_and_annotated():
    cer = _with_outlier()
    wer = _tight_group()
    verdict = ol.detect_outliers(_matrices_from(cer, wer)).verdicts[4]
    assert verdict.status == ol.STATUS_NONE
    assert verdict.cer_status != ol.STATUS_NONE
    assert verdict.notes
    assert "weaker of the two" in verdict.notes[0]


def test_agreement_on_both_metrics_produces_a_flag():
    matrix = _with_outlier()
    report = ol.detect_outliers(_matrices_from(matrix, matrix))
    assert report.verdicts[4].cer_status != ol.STATUS_NONE
    assert report.verdicts[4].wer_status != ol.STATUS_NONE
    assert report.verdicts[4].is_flagged


# ── Small samples (§22) ───────────────────────────────────────────────────────


@pytest.mark.parametrize("n", [2, 3])
def test_detection_is_not_applicable_below_four_attempts(n):
    matrix = _with_outlier(n=n, index=n - 1)
    report = ol.detect_outliers(_matrices_from(matrix))
    assert report.applicable is False
    assert report.flagged_ids == []
    assert "not meaningful" in report.note


def test_two_attempts_explain_that_there_is_no_group_to_compare_against():
    report = ol.detect_outliers(_matrices_from(_with_outlier(n=2, index=1)))
    assert "no independent group" in report.note


def test_detection_becomes_available_at_four_attempts():
    report = ol.detect_outliers(_matrices_from(_with_outlier(n=4, index=3)))
    assert report.applicable is True
    assert ol.MIN_ATTEMPTS_FOR_OUTLIERS == 4


# ── Diagnostic language (§12) ─────────────────────────────────────────────────


def test_the_message_describes_disagreement_not_incorrectness():
    labels = {f"a{i}": f"Run {i + 1}" for i in range(5)}
    report = ol.detect_outliers(_matrices_from(_with_outlier()), labels)
    message = report.verdicts[4].message

    assert "disagreement with the remaining transcription attempts" in message
    assert "Run 5" in message
    for banned in ("incorrect", "wrong", "bad", "error", "inaccurate"):
        assert banned not in message.lower()


def test_the_report_ships_the_alternative_explanations_verbatim():
    report = ol.detect_outliers(_matrices_from(_with_outlier()))
    assert "the transcription captured text omitted by other runs" in report.alternative_explanations
    assert "the document contains genuinely ambiguous handwriting" in report.alternative_explanations
    assert len(report.alternative_explanations) == 6


def test_the_report_carries_the_diagnostic_disclaimer():
    report = ol.detect_outliers(_matrices_from(_with_outlier()))
    assert "not evidence that a transcription is incorrect" in report.disclaimer


def test_a_consistent_attempt_gets_a_plain_reassuring_message():
    report = ol.detect_outliers(_matrices_from(_tight_group()))
    assert "consistent with the rest of the group" in report.verdicts[0].message


def test_labels_fall_back_to_ids_when_not_supplied():
    report = ol.detect_outliers(_matrices_from(_with_outlier()))
    assert report.verdicts[0].label == "a0"


# ── Serialization ─────────────────────────────────────────────────────────────


def test_report_as_dict_is_complete():
    labels = {f"a{i}": f"Run {i + 1}" for i in range(5)}
    as_dict = ol.detect_outliers(_matrices_from(_with_outlier()), labels).as_dict()

    assert as_dict["applicable"] is True
    assert as_dict["flagged_ids"] == ["a4"]
    assert len(as_dict["verdicts"]) == 5
    assert as_dict["verdicts"][4]["is_flagged"] is True
    assert as_dict["disclaimer"]
    assert len(as_dict["alternative_explanations"]) == 6


def test_the_method_note_explains_the_fallback_when_it_was_used():
    matrix = np.full((5, 5), 0.10)
    matrix[4, :] = matrix[:, 4] = 0.50
    np.fill_diagonal(matrix, 0.0)
    report = ol.detect_outliers(_matrices_from(matrix))
    assert "median absolute deviation was zero" in report.note
