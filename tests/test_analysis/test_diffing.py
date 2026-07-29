"""Difference inspection and change categorization (spec §18)."""

import pytest

from backend.analysis import diffing as df
from backend.analysis import metrics as m

pytestmark = pytest.mark.unit


def _diff(a: str, b: str) -> df.DiffResult:
    return df.diff_prepared(m.prepare("a", a), m.prepare("b", b))


def _categories(result: df.DiffResult):
    return {seg.category for seg in result.segments if seg.is_change}


# ── Structure ─────────────────────────────────────────────────────────────────


def test_identical_texts_produce_no_changes():
    result = _diff("the cat sat on the mat", "the cat sat on the mat")
    assert not any(seg.is_change for seg in result.segments)
    assert result.changed_token_count == 0
    assert "identical after normalization" in result.summary()


def test_segments_cover_the_whole_of_both_sequences():
    result = _diff("the cat sat on the mat", "the dog sat upon the mat")
    covered_a = [t for seg in result.segments for t in seg.a_tokens]
    covered_b = [t for seg in result.segments for t in seg.b_tokens]
    assert covered_a == "the cat sat on the mat".split()
    assert covered_b == "the dog sat upon the mat".split()


def test_equal_runs_are_preserved_as_context():
    result = _diff("alpha beta gamma", "alpha DELTA gamma")
    equal = [seg for seg in result.segments if not seg.is_change]
    assert equal
    assert equal[0].a_tokens == ("alpha",)


def test_the_original_texts_remain_available():
    """§18, final clause — the difference view keeps access to the originals."""
    result = df.diff_prepared(
        m.prepare("a", "  The  cat.  "), m.prepare("b", "  The  dog.  ")
    )
    assert result.a_original == "  The  cat.  "
    assert result.b_original == "  The  dog.  "


# ── Categories (§18) ──────────────────────────────────────────────────────────


def test_capitalization_only_difference():
    result = _diff("the Regiment marched", "the regiment marched")
    assert df.CAT_CASE in _categories(result)


def test_punctuation_only_difference():
    result = _diff("the regiment, marched", "the regiment marched")
    assert df.CAT_PUNCTUATION in _categories(result)


def test_spelling_variant_is_distinguished_from_a_different_word():
    assert df.CAT_SPELLING in _categories(_diff("he recieved it", "he received it"))
    assert df.CAT_SUBSTITUTION in _categories(_diff("he received it", "he purchased it"))


def test_word_spacing_difference_is_recognised_across_aligned_blocks():
    """A token-level alignment splits this across two blocks; the merge pass
    recognises that the text is identical once whitespace is removed."""
    result = _diff("he went into town", "he went in to town")
    assert df.CAT_SPACING in _categories(result)


def test_joined_words_are_also_recognised_as_spacing():
    result = _diff("he went in to town", "he went into town")
    assert df.CAT_SPACING in _categories(result)


def test_omitted_word():
    result = _diff("the quick brown fox", "the brown fox")
    assert df.CAT_OMISSION in _categories(result)


def test_inserted_word():
    result = _diff("the brown fox", "the quick brown fox")
    assert df.CAT_INSERTION in _categories(result)


def test_a_long_omitted_run_is_reported_as_a_missing_line():
    a = "alpha beta gamma delta epsilon zeta eta theta"
    b = "alpha theta"
    assert df.CAT_LINE_OMISSION in _categories(_diff(a, b))


def test_a_long_inserted_run_is_reported_as_an_inserted_passage():
    a = "alpha theta"
    b = "alpha beta gamma delta epsilon zeta eta theta"
    assert df.CAT_LINE_INSERTION in _categories(_diff(a, b))


def test_a_short_omission_is_not_called_a_line():
    result = _diff("alpha beta gamma delta", "alpha delta")
    assert df.CAT_LINE_OMISSION not in _categories(result)
    assert df.CAT_OMISSION in _categories(result)


def test_every_category_has_a_human_readable_label():
    result = _diff("the Regiment, went into town", "the regiment went in to village")
    for category in _categories(result):
        assert df.CATEGORY_LABELS[category]


# ── Counts and divergence ─────────────────────────────────────────────────────


def test_category_counts_tally_the_segments():
    result = _diff("alpha beta gamma delta", "alpha BETA gamma DELTA")
    assert sum(
        count for cat, count in result.category_counts.items() if cat != df.CAT_EQUAL
    ) == len([s for s in result.segments if s.is_change])


def test_substantial_divergence_is_flagged():
    result = _diff(
        "the regiment marched south at dawn",
        "a company of cavalry rode north through the night",
    )
    assert result.major_divergence is True
    assert "substantial divergence" in result.summary()


def test_isolated_variation_is_not_flagged_as_divergence():
    result = _diff(
        "the regiment marched south at dawn and the men were in good spirits today",
        "the regiment marched south at dawn and the men were in good spirit today",
    )
    assert result.major_divergence is False
    assert "substantial divergence" not in result.summary()


def test_changed_fraction_is_reported():
    result = _diff("alpha beta gamma delta", "alpha beta gamma DELTA")
    assert result.changed_fraction == pytest.approx(0.25)


def test_token_counts_are_reported_for_both_sides():
    result = _diff("one two three", "one two three four")
    assert result.a_token_count == 3
    assert result.b_token_count == 4


def test_comparing_against_an_empty_text_is_total_divergence():
    result = _diff("alpha beta gamma", "")
    assert result.b_token_count == 0
    assert result.major_divergence is True


# ── Summary and serialization ─────────────────────────────────────────────────


def test_the_summary_names_the_kinds_of_change():
    result = _diff("the Regiment, marched", "the regiment marched")
    summary = result.summary()
    assert "Differences:" in summary
    assert "capitalization only" in summary.lower() or "punctuation only" in summary.lower()


def test_diff_as_dict_is_json_ready_and_complete():
    as_dict = _diff("the cat sat", "the dog sat").as_dict()
    for key in (
        "a_id",
        "b_id",
        "segments",
        "category_counts",
        "category_labels",
        "changed_fraction",
        "major_divergence",
        "summary",
        "a_original",
        "b_original",
    ):
        assert key in as_dict
    assert as_dict["segments"][0]["a_text"]


def test_segments_expose_joined_text_for_display():
    result = _diff("alpha beta gamma", "alpha DELTA EPSILON gamma")
    changed = next(seg for seg in result.segments if seg.is_change)
    assert changed.as_dict()["b_text"] == " ".join(changed.b_tokens)


def test_diff_tokens_works_without_prepared_texts():
    result = df.diff_tokens(["a", "b"], ["a", "c"], a_id="x", b_id="y")
    assert result.a_id == "x" and result.b_id == "y"
    assert result.changed_token_count == 1


# ── An attempt against a consensus (§18) ──────────────────────────────────────


def test_an_attempt_can_be_diffed_against_a_consensus():
    consensus = m.prepare("__consensus__", "the quick brown cat jumped")
    attempt = m.prepare("a2", "the quick brown hat jumped")
    result = df.diff_prepared(consensus, attempt)
    assert result.a_id == "__consensus__"
    assert df.CAT_SPELLING in _categories(result)
