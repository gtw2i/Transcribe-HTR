"""Normalization profiles and tokenizers (spec §4, §6)."""

import importlib

import pytest

# ``backend.analysis`` re-exports the ``normalize()`` *function*, which shadows
# the ``normalize`` *submodule* of the same name, so ``from backend.analysis
# import normalize`` yields the function. Import the module explicitly.
nz = importlib.import_module("backend.analysis.normalize")

pytestmark = pytest.mark.unit


# ── Individual steps ──────────────────────────────────────────────────────────


def test_strip_line_edges_trims_every_line():
    assert nz.step_strip_line_edges("  a  \n\t b \n") == "a\nb\n"


def test_collapse_spaces_leaves_newlines_alone():
    assert nz.step_collapse_spaces("a   \t b\n\n  c") == "a b\n\n c"


def test_collapse_blank_lines_caps_at_one_blank():
    assert nz.step_collapse_blank_lines("a\n\n\n\n\nb") == "a\n\nb"
    assert nz.step_collapse_blank_lines("a\n\nb") == "a\n\nb"


def test_drop_empty_lines():
    assert nz.step_drop_empty_lines("a\n\n b \n\nc") == "a\n b \nc"


def test_join_linebreak_hyphens_rejoins_split_word():
    assert nz.step_join_linebreak_hyphens("regi-\nment") == "regiment"


def test_join_linebreak_hyphens_handles_adjacent_occurrences_in_one_pass():
    """A consuming pattern would need two passes and so would not be idempotent."""
    once = nz.step_join_linebreak_hyphens("a-\nb-\nc")
    assert once == "abc"
    assert nz.step_join_linebreak_hyphens(once) == once


def test_join_linebreak_hyphens_leaves_real_hyphens():
    assert nz.step_join_linebreak_hyphens("well-known") == "well-known"
    # A hyphen at the end of a line followed by a blank line is not a word split.
    assert nz.step_join_linebreak_hyphens("dash -\n\nnext") == "dash -\n\nnext"


def test_strip_punctuation_removes_unicode_punctuation():
    assert nz.step_strip_punctuation("Don't — really?") == "Dont  really"


def test_lowercase():
    assert nz.step_lowercase("ABC") == "abc"


def test_nfc_composes():
    decomposed = "é"  # e + combining acute accent
    composed = "é"  # precomposed e-acute
    assert decomposed != composed
    assert nz.step_nfc(decomposed) == composed


def test_nfc_makes_visually_identical_text_compare_equal():
    """Two attempts spelling the same accented word in different Unicode
    forms must not register as disagreement over the encoding alone."""
    assert nz.normalize("François") == nz.normalize("François")


# ── Profiles ──────────────────────────────────────────────────────────────────


def test_default_profile_is_standard_historical():
    assert nz.DEFAULT_PROFILE == "standard_historical"


def test_all_three_profiles_are_registered():
    assert set(nz.NORMALIZATION_PROFILES) == {
        "standard_historical",
        "diplomatic",
        "normalized",
    }


def test_standard_historical_preserves_case_and_punctuation():
    text = "The 21st Ohio, under Col. Smith, held the line."
    assert nz.normalize(text, "standard_historical") == text


def test_standard_historical_normalizes_whitespace_and_hyphenation():
    text = "  The regi-\n  ment marched   south.  \n\n\n\nIt rained.  "
    assert (
        nz.normalize(text, "standard_historical")
        == "The regiment marched south.\n\nIt rained."
    )


def test_diplomatic_changes_nothing_but_unicode_form():
    text = "  The  Regi-\nment.  \n\n\n"
    assert nz.normalize(text, "diplomatic") == text


def test_normalized_folds_case_punctuation_and_layout():
    text = "The Regiment, marching.\nIt rained!"
    assert nz.normalize(text, "normalized") == "the regiment marching it rained"


@pytest.mark.parametrize("profile", sorted(nz.NORMALIZATION_PROFILES))
def test_every_profile_is_idempotent(profile):
    text = "  The regi-\n  ment, marching   south.  \n\n\n\nIt rained!  \n"
    once = nz.normalize(text, profile)
    assert nz.normalize(once, profile) == once


@pytest.mark.parametrize("profile", sorted(nz.NORMALIZATION_PROFILES))
def test_normalize_does_not_mutate_the_original(profile):
    """§4.1 — the stored transcription text must remain unchanged."""
    original = "  Mixed   Case, with\npunctuation.  "
    unchanged = "  Mixed   Case, with\npunctuation.  "
    nz.normalize(original, profile)
    assert original == unchanged


def test_normalize_handles_none_as_empty():
    assert nz.normalize(None) == ""


def test_unknown_profile_raises():
    with pytest.raises(nz.UnknownProfileError):
        nz.normalize("x", "no_such_profile")


# ── Provenance ────────────────────────────────────────────────────────────────


def test_describe_profile_carries_the_step_list_for_provenance():
    described = nz.describe_profile("standard_historical")
    assert described["id"] == "standard_historical"
    assert described["version"] == nz.NORMALIZATION_VERSION
    assert described["steps"][0] == "nfc"
    assert "join_linebreak_hyphens" in described["steps"]


def test_every_profile_step_name_is_a_registered_step():
    for spec in nz.NORMALIZATION_PROFILES.values():
        for step in spec["steps"]:
            assert step in nz.STEPS, f"unregistered step {step!r}"


def test_list_profiles_returns_all_of_them():
    assert len(nz.list_profiles()) == len(nz.NORMALIZATION_PROFILES)


# ── Tokenizers ────────────────────────────────────────────────────────────────


def test_word_simple_keeps_punctuation_attached():
    assert nz.tokenize("the cat, sat", "word_simple") == ["the", "cat,", "sat"]


def test_word_punct_separates_punctuation():
    assert nz.tokenize("the cat, sat", "word_punct") == ["the", "cat", ",", "sat"]


def test_default_tokenizer_is_word_simple():
    assert nz.DEFAULT_TOKENIZER == "word_simple"


def test_unknown_tokenizer_raises():
    with pytest.raises(nz.UnknownTokenizerError):
        nz.tokenize("x", "no_such_tokenizer")


def test_list_tokenizers_describes_each_one():
    listed = nz.list_tokenizers()
    assert {t["id"] for t in listed} == set(nz.TOKENIZERS)
    assert all(t["description"] for t in listed)
