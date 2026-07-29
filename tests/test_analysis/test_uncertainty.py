"""Uncertainty estimation over replicate attempts (spec §10, §22)."""

import numpy as np
import pytest

from backend.analysis import matrices as mx
from backend.analysis import metrics as m
from backend.analysis import uncertainty as un

pytestmark = pytest.mark.unit


def _matrix(texts):
    prepared = [m.prepare(f"a{i}", t) for i, t in enumerate(texts)]
    return mx.build_matrices(
        [p.attempt_id for p in prepared], mx.compute_pairs(prepared)
    )


FIVE = [
    "The regiment marched south at dawn.",
    "The regiment marched south at dawn.",
    "The regiment marched south by dawn.",
    "The regiment marched south at dawn!",
    "A company rode north during the night.",
]


# ── Leave-one-out mechanics ───────────────────────────────────────────────────


def test_leave_one_out_drops_a_whole_row_and_column():
    """The resampling unit is the attempt: dropping one removes all N-1 of its
    comparisons, not a single pair."""
    matrix = np.array(
        [
            [0.0, 0.1, 0.2, 0.3],
            [0.1, 0.0, 0.4, 0.5],
            [0.2, 0.4, 0.0, 0.6],
            [0.3, 0.5, 0.6, 0.0],
        ]
    )
    estimates = un.leave_one_out_means(matrix)
    assert len(estimates) == 4
    # Dropping attempt 0 leaves pairs (1,2), (1,3), (2,3) = 0.4, 0.5, 0.6.
    assert estimates[0] == pytest.approx((0.4 + 0.5 + 0.6) / 3)
    # Dropping attempt 3 leaves pairs (0,1), (0,2), (1,2) = 0.1, 0.2, 0.4.
    assert estimates[3] == pytest.approx((0.1 + 0.2 + 0.4) / 3)


def test_leave_one_out_uses_unique_pairs_only():
    matrix = np.array([[0.0, 0.2, 0.4], [0.2, 0.0, 0.6], [0.4, 0.6, 0.0]])
    # Dropping one of three leaves exactly one pair.
    assert un.leave_one_out_means(matrix) == [
        pytest.approx(0.6),
        pytest.approx(0.4),
        pytest.approx(0.2),
    ]


# ── Jackknife ─────────────────────────────────────────────────────────────────


def test_jackknife_matches_the_hand_computed_value():
    matrix = np.array(
        [
            [0.0, 0.1, 0.2, 0.3],
            [0.1, 0.0, 0.4, 0.5],
            [0.2, 0.4, 0.0, 0.6],
            [0.3, 0.5, 0.6, 0.0],
        ]
    )
    theta = np.array(un.leave_one_out_means(matrix))
    expected = np.sqrt((4 - 1) / 4 * np.sum((theta - theta.mean()) ** 2))

    estimate = un.jackknife_se(matrix)
    assert estimate.applicable is True
    assert estimate.value == pytest.approx(float(expected))


def test_jackknife_is_zero_when_every_pair_agrees():
    matrix = np.full((4, 4), 0.2)
    np.fill_diagonal(matrix, 0.0)
    assert un.jackknife_se(matrix).value == pytest.approx(0.0)


def test_jackknife_grows_when_one_attempt_dominates_the_variation():
    tight = np.full((5, 5), 0.05)
    np.fill_diagonal(tight, 0.0)

    skewed = tight.copy()
    skewed[4, :] = 0.9
    skewed[:, 4] = 0.9
    np.fill_diagonal(skewed, 0.0)

    assert un.jackknife_se(skewed).value > un.jackknife_se(tight).value


def test_jackknife_is_deterministic():
    """No RNG anywhere: repeated calls must agree exactly (§27)."""
    matrix = _matrix(FIVE).cer_symmetric
    first = un.jackknife_se(matrix).value
    for _ in range(10):
        assert un.jackknife_se(matrix).value == first


@pytest.mark.parametrize("n", [2, 3])
def test_jackknife_is_suppressed_for_small_samples(n):
    """§22 — do not imply precision that the sample size cannot support."""
    matrix = np.full((n, n), 0.1)
    np.fill_diagonal(matrix, 0.0)
    estimate = un.jackknife_se(matrix)
    assert estimate.applicable is False
    assert estimate.value is None
    assert "too few" in estimate.note


def test_jackknife_becomes_available_at_four_attempts():
    matrix = np.full((4, 4), 0.1)
    np.fill_diagonal(matrix, 0.0)
    assert un.jackknife_se(matrix).applicable is True
    assert un.MIN_ATTEMPTS_FOR_UNCERTAINTY == 4


# ── Labelling (§10) ───────────────────────────────────────────────────────────


def test_the_estimate_always_says_what_it_represents():
    """§10 — the user must never be shown an unlabelled '±' value."""
    estimate = un.jackknife_se(_matrix(FIVE).cer_symmetric)
    assert estimate.label
    assert "jackknife" in estimate.label.lower()
    assert "not independent observations" in estimate.description


def test_the_description_explains_why_the_attempt_is_the_resampling_unit():
    assert "resampling unit is the attempt, not the pair" in un.JACKKNIFE_DESCRIPTION


def test_estimate_as_dict_carries_the_label_and_method():
    as_dict = un.jackknife_se(_matrix(FIVE).cer_symmetric).as_dict()
    assert as_dict["method"] == un.JACKKNIFE_METHOD
    assert as_dict["label"]
    assert as_dict["applicable"] is True
    assert len(as_dict["leave_one_out"]) == 5


# ── The three §10 quantities ──────────────────────────────────────────────────


def test_variability_separates_central_tendency_spread_and_uncertainty():
    matrices = _matrix(FIVE)
    pairs = mx.compute_pairs([m.prepare(f"a{i}", t) for i, t in enumerate(FIVE)])
    summary = mx.summarize_pairs(pairs, 5)["cer"]

    report = un.describe_variability(summary, matrices.cer_symmetric, "cer")
    assert report.central_value == summary.median
    assert report.spread_low == summary.iqr_low
    assert report.spread_high == summary.iqr_high
    assert report.sd == summary.sd
    assert report.uncertainty.applicable is True

    # All three are distinct, labelled quantities.
    assert "Median" in report.central_label
    assert "IQR" in report.spread_label
    assert "Jackknife" in report.uncertainty.label


def test_summary_sentence_names_every_measure_it_quotes():
    matrices = _matrix(FIVE)
    pairs = mx.compute_pairs([m.prepare(f"a{i}", t) for i, t in enumerate(FIVE)])
    summary = mx.summarize_pairs(pairs, 5)["cer"]
    sentence = un.describe_variability(summary, matrices.cer_symmetric, "cer").summary_sentence()

    assert "Median pairwise CER disagreement" in sentence
    assert "IQR across" in sentence
    assert "Jackknife SE" in sentence
    # No bare plus-minus anywhere.
    assert "±" not in sentence


def test_summary_sentence_omits_uncertainty_when_not_applicable():
    matrices = _matrix(FIVE[:3])
    pairs = mx.compute_pairs([m.prepare(f"a{i}", t) for i, t in enumerate(FIVE[:3])])
    summary = mx.summarize_pairs(pairs, 3)["cer"]
    sentence = un.describe_variability(summary, matrices.cer_symmetric, "cer").summary_sentence()

    assert "Jackknife" not in sentence
    assert "±" not in sentence


def test_variability_as_dict_keeps_the_three_quantities_apart():
    matrices = _matrix(FIVE)
    pairs = mx.compute_pairs([m.prepare(f"a{i}", t) for i, t in enumerate(FIVE)])
    summary = mx.summarize_pairs(pairs, 5)["wer"]
    as_dict = un.describe_variability(summary, matrices.wer_symmetric, "wer").as_dict()

    assert set(as_dict) == {"central", "spread", "uncertainty"}
    assert as_dict["central"]["label"].startswith("Median pairwise WER")
