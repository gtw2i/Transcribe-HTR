"""Medoid, deterministic consensus and consensus comparison (spec §13-§15, §17)."""

import numpy as np
import pytest

from backend.analysis import consensus as cs
from backend.analysis import matrices as mx
from backend.analysis import metrics as m

pytestmark = pytest.mark.unit


def _prepared(texts, tokenizer="word_simple"):
    return [m.prepare(f"a{i}", t, tokenizer=tokenizer) for i, t in enumerate(texts)]


def _setup(texts, tokenizer="word_simple"):
    prep = _prepared(texts, tokenizer)
    matrices = mx.build_matrices(
        [p.attempt_id for p in prep], mx.compute_pairs(prep)
    )
    return prep, matrices


#: Three attempts differing at exactly one token, plus one minority insertion.
#: a0 and a1 agree on "cat" and differ only at "the"/"a"; a2 reads "hat" and
#: appends "today". a0 is the medoid, "cat" carries 2/3, "today" carries 1/3.
THREE = [
    "the quick brown cat jumped over the lazy dog",
    "the quick brown cat jumped over a lazy dog",
    "the quick brown hat jumped over the lazy dog today",
]


# ── Medoid (§15) ──────────────────────────────────────────────────────────────


def test_medoid_is_the_attempt_closest_to_all_others():
    _, matrices = _setup(THREE)
    assert cs.select_medoid(matrices).attempt_id == "a0"


def test_medoid_reports_its_aggregate_disagreement():
    _, matrices = _setup(THREE)
    medoid = cs.select_medoid(matrices)
    means = mx.mean_disagreement_vector(matrices, "cer")
    assert medoid.mean_cer == pytest.approx(float(means.min()))


def test_medoid_ranks_every_attempt():
    _, matrices = _setup(THREE)
    assert set(cs.select_medoid(matrices).rank) == {"a0", "a1", "a2"}
    assert cs.select_medoid(matrices).rank[0] == "a0"


def test_medoid_picks_the_central_attempt_not_an_extreme_one():
    _, matrices = _setup(
        [
            "alpha beta gamma delta",
            "alpha beta gamma delta epsilon",
            "alpha beta gamma delta epsilon zeta eta theta",
        ]
    )
    assert cs.select_medoid(matrices).attempt_id == "a1"


def test_medoid_ties_break_deterministically_by_canonical_order():
    ids = ("a0", "a1", "a2")
    identical = np.array([[0.0, 0.2, 0.2], [0.2, 0.0, 0.2], [0.2, 0.2, 0.0]])
    zeros = np.zeros((3, 3))
    matrices = mx.PairwiseMatrices(ids, identical, identical, zeros, zeros)
    assert cs.select_medoid(matrices).attempt_id == "a0"


def test_medoid_needs_two_attempts():
    prep = _prepared(["only one"])
    matrices = mx.build_matrices(["a0"], [])
    with pytest.raises(ValueError):
        cs.select_medoid(matrices)


def test_medoid_text_is_verbatim_from_a_real_attempt():
    """§15 — guaranteed to consist entirely of text one attempt produced."""
    prep, matrices = _setup(THREE)
    medoid = cs.select_medoid(matrices)
    chosen = next(p for p in prep if p.attempt_id == medoid.attempt_id)
    assert chosen.original in THREE


# ── Deterministic consensus (§14) ─────────────────────────────────────────────


def test_consensus_matches_the_hand_derived_expected_string():
    """Phase 3 exit criterion.

    Backbone is a0. At the "cat"/"hat" column, "cat" has 2 votes to 1 and wins.
    At "the"/"a", "the" has 2 votes (a0, a2) to 1 and wins. "today" is inserted
    by a2 alone — 1 of 3 is not a strict majority — so it is dropped.
    """
    prep, matrices = _setup(THREE)
    result = cs.deterministic_consensus(prep, matrices)
    assert result.text == "the quick brown cat jumped over the lazy dog"
    assert result.backbone_attempt_id == "a0"
    assert result.method == cs.DETERMINISTIC_METHOD


def test_the_majority_token_wins_a_contested_column():
    prep, matrices = _setup(
        ["red green blue", "red green blue", "red yellow blue"]
    )
    assert cs.deterministic_consensus(prep, matrices).text == "red green blue"


def test_a_minority_insertion_is_dropped():
    prep, matrices = _setup(
        ["alpha beta gamma", "alpha beta gamma", "alpha beta extra gamma"]
    )
    assert "extra" not in cs.deterministic_consensus(prep, matrices).text


def test_a_majority_insertion_is_kept():
    prep, matrices = _setup(
        ["alpha beta gamma", "alpha beta extra gamma", "alpha beta extra gamma"]
    )
    assert "extra" in cs.deterministic_consensus(prep, matrices).text


def test_a_majority_omission_removes_the_token():
    prep, matrices = _setup(
        ["alpha beta spurious gamma", "alpha beta gamma", "alpha beta gamma"]
    )
    assert "spurious" not in cs.deterministic_consensus(prep, matrices).text


def test_identical_attempts_produce_that_same_text():
    text = "The regiment marched south at dawn."
    prep, matrices = _setup([text, text, text])
    result = cs.deterministic_consensus(prep, matrices)
    assert result.text == text
    assert result.n_low_support == 0
    assert result.mean_support == pytest.approx(1.0)


def test_line_structure_comes_from_the_backbone():
    prep, matrices = _setup(
        [
            "Line one here\nLine two here",
            "Line one here\nLine two here",
            "Line one there\nLine two here",
        ]
    )
    assert cs.deterministic_consensus(prep, matrices).text == (
        "Line one here\nLine two here"
    )


def test_support_is_recorded_for_every_emitted_token():
    prep, matrices = _setup(THREE)
    result = cs.deterministic_consensus(prep, matrices)
    assert len(result.tokens) == len(result.text.split())
    assert all(0.0 < t.support <= 1.0 for t in result.tokens)


def test_contested_tokens_are_marked_low_support():
    prep, matrices = _setup(
        ["alpha one gamma", "alpha two gamma", "alpha three gamma", "alpha four gamma"]
    )
    result = cs.deterministic_consensus(prep, matrices)
    contested = [t for t in result.tokens if t.low_support]
    assert contested
    assert all(t.support < cs.LOW_SUPPORT_THRESHOLD for t in contested)


def test_unanimous_tokens_are_not_marked_low_support():
    prep, matrices = _setup(["alpha one", "alpha two", "alpha three"])
    result = cs.deterministic_consensus(prep, matrices)
    alpha = next(t for t in result.tokens if t.token == "alpha")
    assert alpha.support == pytest.approx(1.0)
    assert alpha.low_support is False


def test_consensus_is_marked_as_not_generated():
    """§16 — only an LLM consensus is 'generated' rather than observed."""
    prep, matrices = _setup(THREE)
    assert cs.deterministic_consensus(prep, matrices).generated is False


def test_consensus_needs_two_attempts():
    prep = _prepared(["only one"])
    matrices = mx.build_matrices(["a0"], [])
    with pytest.raises(ValueError):
        cs.deterministic_consensus(prep, matrices)


def test_consensus_warns_when_the_backbone_is_unusually_short():
    prep, matrices = _setup(
        [
            "alpha beta",
            "alpha beta gamma delta epsilon zeta eta theta iota kappa",
            "alpha beta gamma delta epsilon zeta eta theta iota lambda",
        ]
    )
    result = cs.deterministic_consensus(prep, matrices)
    if result.backbone_attempt_id == "a0":
        assert result.warnings
        assert "under-represented" in result.warnings[0]


def test_documented_limitations_travel_with_the_result():
    prep, matrices = _setup(THREE)
    limitations = cs.deterministic_consensus(prep, matrices).limitations
    assert any("backbone" in text for text in limitations)
    assert any("Reordered material" in text for text in limitations)


# ── Reproducibility (§14, §27) ────────────────────────────────────────────────


def test_the_same_inputs_produce_byte_identical_output_fifty_times():
    """Phase 3 exit criterion — 50 repetitions, no drift."""
    prep, matrices = _setup(THREE)
    first = cs.deterministic_consensus(prep, matrices).text
    for _ in range(50):
        assert cs.deterministic_consensus(prep, matrices).text == first


def test_input_order_does_not_change_the_consensus():
    """The medoid backbone removes any dependence on which attempt came first."""
    forward_prep, forward_matrices = _setup(THREE)
    forward = cs.deterministic_consensus(forward_prep, forward_matrices).text

    reversed_texts = list(reversed(THREE))
    prep = [m.prepare(f"a{2 - i}", t) for i, t in enumerate(reversed_texts)]
    matrices = mx.build_matrices(
        [p.attempt_id for p in prep], mx.compute_pairs(prep)
    )
    assert cs.deterministic_consensus(prep, matrices).text == forward


def test_the_method_id_is_recorded_so_a_future_version_cannot_masquerade():
    prep, matrices = _setup(THREE)
    assert cs.deterministic_consensus(prep, matrices).as_dict()["method"] == (
        "deterministic_vote_v1"
    )


# ── Serialization ─────────────────────────────────────────────────────────────


def test_consensus_as_dict_is_complete():
    prep, matrices = _setup(THREE)
    as_dict = cs.deterministic_consensus(prep, matrices).as_dict()
    for key in (
        "method",
        "text",
        "backbone_attempt_id",
        "n_attempts",
        "n_tokens",
        "n_low_support",
        "mean_support",
        "tokens",
        "warnings",
        "limitations",
        "generated",
    ):
        assert key in as_dict


# ── Comparison against the consensus (§17) ────────────────────────────────────


def test_every_attempt_is_compared_against_the_consensus():
    prep, matrices = _setup(THREE)
    result = cs.deterministic_consensus(prep, matrices)
    comparisons = cs.compare_to_consensus(result.text, prep)
    assert [c.attempt_id for c in comparisons] == ["a0", "a1", "a2"]


def test_the_backbone_agrees_perfectly_with_a_consensus_it_produced():
    prep, matrices = _setup(THREE)
    result = cs.deterministic_consensus(prep, matrices)
    comparisons = {c.attempt_id: c for c in cs.compare_to_consensus(result.text, prep)}
    assert comparisons["a0"].cer == pytest.approx(0.0)
    assert comparisons["a0"].wer == pytest.approx(0.0)


def test_the_divergent_attempt_is_furthest_from_the_consensus():
    prep, matrices = _setup(THREE)
    result = cs.deterministic_consensus(prep, matrices)
    comparisons = {c.attempt_id: c for c in cs.compare_to_consensus(result.text, prep)}
    assert comparisons["a2"].wer > comparisons["a1"].wer


def test_consensus_comparison_retains_the_edit_counts():
    prep, matrices = _setup(THREE)
    result = cs.deterministic_consensus(prep, matrices)
    comparison = cs.compare_to_consensus(result.text, prep)[2].as_dict()
    for key in (
        "cer_vs_consensus",
        "wer_vs_consensus",
        "char_substitutions",
        "char_deletions",
        "char_insertions",
        "word_substitutions",
        "word_deletions",
        "word_insertions",
    ):
        assert key in comparison


def test_the_comparison_carries_its_non_independence_caveat():
    """§17 — the consensus was derived from the same attempts."""
    assert "not independent of the attempts" in cs.CONSENSUS_COMPARISON_CAVEAT


def test_median_consensus_wer_summarizes_the_comparison():
    prep, matrices = _setup(THREE)
    result = cs.deterministic_consensus(prep, matrices)
    comparisons = cs.compare_to_consensus(result.text, prep)
    expected = float(np.median([c.wer for c in comparisons]))
    assert cs.median_consensus_wer(comparisons) == pytest.approx(expected)


def test_median_consensus_wer_of_nothing_is_none():
    assert cs.median_consensus_wer([]) is None


# ── Consensus uses only the selected attempts (§13) ───────────────────────────


def test_the_consensus_contains_only_material_from_the_selected_attempts():
    prep, matrices = _setup(THREE)
    result = cs.deterministic_consensus(prep, matrices)
    vocabulary = {token for p in prep for token in p.tokens}
    assert all(t.token in vocabulary for t in result.tokens)
