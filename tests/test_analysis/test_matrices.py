"""Pairwise matrices and consistency statistics (spec §7, §9, §11)."""

import math

import numpy as np
import pytest

from backend.analysis import matrices as mx
from backend.analysis import metrics as m

pytestmark = pytest.mark.unit


def _prepared(texts):
    return [m.prepare(f"a{i}", text) for i, text in enumerate(texts)]


#: Four attempts: the first three agree closely, the fourth is divergent.
GROUP = [
    "The regiment marched south at dawn.",
    "The regiment marched south at dawn.",
    "The regiment marched south by dawn.",
    "A company rode north during the night.",
]


@pytest.fixture
def group_matrices():
    prepared = _prepared(GROUP)
    pairs = mx.compute_pairs(prepared)
    return mx.build_matrices([p.attempt_id for p in prepared], pairs), pairs


# ── Pair enumeration (§9) ─────────────────────────────────────────────────────


@pytest.mark.parametrize("n,expected", [(2, 1), (3, 3), (4, 6), (5, 10), (10, 45)])
def test_unique_pair_count_formula(n, expected):
    assert mx.n_unique_pairs(n) == expected


def test_compute_pairs_produces_exactly_the_unique_pairs():
    prepared = _prepared(GROUP)
    pairs = mx.compute_pairs(prepared)
    assert len(pairs) == mx.n_unique_pairs(4) == 6
    seen = {(p.a_id, p.b_id) for p in pairs}
    assert len(seen) == 6
    # No pair appears in both orientations.
    assert not any((b, a) in seen for a, b in seen)


def test_five_attempts_give_the_ten_pairs_of_the_acceptance_scenario():
    pairs = mx.compute_pairs(_prepared(GROUP + ["Another reading entirely."]))
    assert len(pairs) == 10


def test_fewer_than_two_attempts_is_refused():
    with pytest.raises(mx.InsufficientAttemptsError):
        mx.compute_pairs(_prepared(["only one"]))


# ── Matrix structure (§7) ─────────────────────────────────────────────────────


def test_diagonal_is_exactly_zero(group_matrices):
    matrices, _ = group_matrices
    for matrix in (
        matrices.cer_symmetric,
        matrices.wer_symmetric,
        matrices.cer_directional,
        matrices.wer_directional,
    ):
        assert np.array_equal(np.diag(matrix), np.zeros(matrices.n))


def test_symmetric_matrices_are_exactly_symmetric(group_matrices):
    """Not merely close — the same value is mirrored into both cells."""
    matrices, _ = group_matrices
    assert np.array_equal(matrices.cer_symmetric, matrices.cer_symmetric.T)
    assert np.array_equal(matrices.wer_symmetric, matrices.wer_symmetric.T)


def test_directional_matrix_is_row_reference_column_hypothesis():
    prepared = _prepared(["one two", "one two three four"])
    pairs = mx.compute_pairs(prepared)
    matrices = mx.build_matrices(["a0", "a1"], pairs)
    pair = pairs[0]
    # Row 0 = attempt a0 as reference.
    assert matrices.wer_directional[0, 1] == pytest.approx(pair.wer_a_to_b)
    assert matrices.wer_directional[1, 0] == pytest.approx(pair.wer_b_to_a)
    assert matrices.wer_directional[0, 1] != matrices.wer_directional[1, 0]


def test_directional_matrix_is_generally_asymmetric(group_matrices):
    matrices, _ = group_matrices
    assert not np.array_equal(matrices.cer_directional, matrices.cer_directional.T)


def test_matrix_ordering_follows_the_supplied_attempt_ids(group_matrices):
    matrices, _ = group_matrices
    assert matrices.attempt_ids == ("a0", "a1", "a2", "a3")


def test_identical_attempts_have_zero_disagreement(group_matrices):
    matrices, _ = group_matrices
    # a0 and a1 are byte-identical but from separate positions (§24).
    assert matrices.cer_symmetric[0, 1] == 0.0
    assert matrices.wer_symmetric[0, 1] == 0.0


def test_divergent_attempt_shows_the_largest_disagreement(group_matrices):
    matrices, _ = group_matrices
    means = mx.mean_disagreement_vector(matrices, "cer")
    assert means.argmax() == 3


def test_matrix_to_json_converts_nan_to_none():
    matrix = np.array([[0.0, float("nan")], [1.0, 0.0]])
    assert mx.matrix_to_json(matrix) == [[0.0, None], [1.0, 0.0]]


def test_undefined_directional_rate_becomes_nan_in_the_matrix():
    prepared = _prepared(["", "some words here"])
    pairs = mx.compute_pairs(prepared)
    matrices = mx.build_matrices(["a0", "a1"], pairs)
    # Row 0 is the empty attempt used as reference: undefined.
    assert math.isnan(matrices.cer_directional[0, 1])
    assert not math.isnan(matrices.cer_directional[1, 0])


# ── Summary statistics (§9) ───────────────────────────────────────────────────


def test_summary_counts_each_comparison_once_not_twice(group_matrices):
    """Regression guard for §9: directional cells must not be double-counted."""
    _, pairs = group_matrices
    summaries = mx.summarize_pairs(pairs, n_attempts=4)
    assert summaries["cer"].n_pairs == 6
    assert summaries["wer"].n_pairs == 6
    assert summaries["cer"].n_attempts == 4


def test_summary_statistics_are_computed_correctly():
    summary = mx.summarize([0.0, 0.2, 0.4, 0.6], n_attempts=4)
    assert summary.mean == pytest.approx(0.3)
    assert summary.median == pytest.approx(0.3)
    assert summary.minimum == 0.0
    assert summary.maximum == 0.6
    assert summary.sd == pytest.approx(np.std([0.0, 0.2, 0.4, 0.6], ddof=1))
    assert summary.iqr_low == pytest.approx(0.15)
    assert summary.iqr_high == pytest.approx(0.45)


def test_single_pair_reports_zero_standard_deviation():
    """With one pair the sample SD is undefined; 0.0 is reported, not nan."""
    summary = mx.summarize([0.25], n_attempts=2)
    assert summary.n_pairs == 1
    assert summary.sd == 0.0
    assert not math.isnan(summary.sd)


def test_summary_as_dict_exposes_the_iqr_as_a_pair():
    summary = mx.summarize([0.1, 0.2, 0.3], n_attempts=3).as_dict()
    assert summary["iqr"] == [pytest.approx(0.15), pytest.approx(0.25)]
    assert summary["n_pairs"] == 3


def test_directional_values_are_summarized_separately_and_labelled(group_matrices):
    _, pairs = group_matrices
    directional = mx.summarize_directional(pairs, n_attempts=4)
    assert "not independent observations" in directional["note"]
    # Both orientations of all six pairs.
    assert directional["cer"]["n_pairs"] == 12


def test_summarize_refuses_an_empty_sequence():
    with pytest.raises(mx.InsufficientAttemptsError):
        mx.summarize([], n_attempts=0)


# ── Per-attempt scores (§11) ──────────────────────────────────────────────────


def test_per_attempt_stats_cover_every_attempt(group_matrices):
    matrices, _ = group_matrices
    stats = mx.per_attempt_stats(matrices)
    assert [s.attempt_id for s in stats] == ["a0", "a1", "a2", "a3"]


def test_per_attempt_stats_exclude_the_self_comparison():
    """The diagonal zero must not drag the minimum down to 0 for every attempt."""
    prepared = _prepared(["alpha beta", "gamma delta", "epsilon zeta"])
    matrices = mx.build_matrices(
        [p.attempt_id for p in prepared], mx.compute_pairs(prepared)
    )
    for stat in mx.per_attempt_stats(matrices):
        assert stat.min_wer > 0.0


def test_per_attempt_values_match_the_matrix_row(group_matrices):
    matrices, _ = group_matrices
    stats = mx.per_attempt_stats(matrices)
    row = np.delete(matrices.cer_symmetric[3], 3)
    assert stats[3].mean_cer == pytest.approx(row.mean())
    assert stats[3].max_cer == pytest.approx(row.max())
    assert stats[3].min_cer == pytest.approx(row.min())


def test_an_attempt_agreeing_with_a_twin_still_scores_high_against_the_group():
    """§11 — a divergent attempt is identifiable even when others agree closely."""
    matrices = mx.build_matrices(
        [f"a{i}" for i in range(4)], mx.compute_pairs(_prepared(GROUP))
    )
    stats = {s.attempt_id: s for s in mx.per_attempt_stats(matrices)}
    assert stats["a3"].mean_cer > stats["a0"].mean_cer
    # Even a3's *closest* neighbour is farther away than a0's typical distance
    # to the group. (a3.min_cer and a0.max_cer are the same matrix cell, so
    # they are equal by construction and cannot be compared against each other.)
    assert stats["a3"].min_cer > stats["a0"].mean_cer


def test_per_attempt_stats_need_two_attempts():
    prepared = _prepared(["solo"])
    matrices = mx.build_matrices(["a0"], [])
    with pytest.raises(mx.InsufficientAttemptsError):
        mx.per_attempt_stats(matrices)


def test_attempt_stats_as_dict_is_complete(group_matrices):
    matrices, _ = group_matrices
    as_dict = mx.per_attempt_stats(matrices)[0].as_dict()
    for key in ("attempt_id", "mean_cer", "median_cer", "min_cer", "max_cer",
                "mean_wer", "median_wer", "min_wer", "max_wer"):
        assert key in as_dict


# ── Heat-map spec (§8) ────────────────────────────────────────────────────────


def test_heatmap_spec_reports_the_true_values(group_matrices):
    matrices, _ = group_matrices
    spec = mx.heatmap_spec(matrices, "cer")
    assert spec.attempt_ids == matrices.attempt_ids
    assert spec.values[0][1] == matrices.cer_symmetric[0, 1]
    assert spec.vmin == 0.0
    assert "CER" in spec.label


def test_heatmap_clips_the_colour_domain_so_one_outlier_cannot_flatten_the_rest():
    """§8 — a single extreme pair must not obscure the remaining differences."""
    matrices = mx.build_matrices(
        [f"a{i}" for i in range(4)], mx.compute_pairs(_prepared(GROUP))
    )
    spec = mx.heatmap_spec(matrices, "cer", percentile=50.0)
    assert spec.clipped is True
    assert spec.vmax < spec.raw_max
    # Clipping is presentational only — the real numbers are still there.
    assert max(max(row) for row in spec.values) == pytest.approx(spec.raw_max)


def test_heatmap_is_not_marked_clipped_when_nothing_exceeds_the_cap(group_matrices):
    matrices, _ = group_matrices
    spec = mx.heatmap_spec(matrices, "cer", percentile=100.0)
    assert spec.clipped is False


def test_heatmap_enforces_a_minimum_colour_span_for_identical_attempts():
    """Otherwise a near-zero domain would amplify float noise into a dramatic map."""
    matrices = mx.build_matrices(
        ["a0", "a1"], mx.compute_pairs(_prepared(["same text", "same text"]))
    )
    spec = mx.heatmap_spec(matrices, "cer")
    assert spec.vmax >= mx.MIN_COLOR_SPAN
    assert spec.raw_max == 0.0


def test_heatmap_rejects_an_unknown_level(group_matrices):
    matrices, _ = group_matrices
    with pytest.raises(ValueError):
        mx.heatmap_spec(matrices, "bogus")


def test_heatmap_as_dict_is_json_ready(group_matrices):
    matrices, _ = group_matrices
    as_dict = mx.heatmap_spec(matrices, "wer").as_dict()
    assert as_dict["attempt_ids"] == list(matrices.attempt_ids)
    assert isinstance(as_dict["values"][0][0], float)
    assert as_dict["clip_percentile"] == 95.0


# ── Reproducibility (§27) ─────────────────────────────────────────────────────


def test_repeating_the_computation_gives_identical_numbers():
    first = mx.compute_pairs(_prepared(GROUP))
    second = mx.compute_pairs(_prepared(GROUP))
    assert [p.as_dict() for p in first] == [p.as_dict() for p in second]
