"""CER/WER metrics, directional and symmetric (spec §5, §6)."""

import pytest

from backend.analysis import metrics as m

pytestmark = pytest.mark.unit


PAIRS = [
    ("kitten", "sitting"),
    ("", "abc"),
    ("abc", ""),
    ("", ""),
    ("the cat sat", "the dog sat here"),
    ("identical", "identical"),
    ("ab", "ba"),
    ("Dear Mother, I write from camp.", "Dear Mother I write from the camp"),
]


# ── Known answers ─────────────────────────────────────────────────────────────


def test_kitten_sitting_is_the_textbook_case():
    counts = m.edit_counts("kitten", "sitting")
    assert counts.distance == 3
    assert counts.substitutions == 2
    assert counts.insertions == 1
    assert counts.deletions == 0


def test_word_level_counts_operate_on_tokens():
    counts = m.edit_counts(("the", "cat", "sat"), ("the", "dog", "sat", "here"))
    assert counts.distance == 2
    assert counts.substitutions == 1
    assert counts.insertions == 1


def test_identical_sequences_have_zero_distance():
    assert m.edit_counts("same", "same").distance == 0


# ── Structural identities (§5) ────────────────────────────────────────────────


@pytest.mark.parametrize("a,b", PAIRS)
def test_distance_is_symmetric(a, b):
    assert m.edit_counts(a, b).distance == m.edit_counts(b, a).distance


@pytest.mark.parametrize("a,b", PAIRS)
def test_counts_sum_to_distance(a, b):
    counts = m.edit_counts(a, b)
    assert counts.substitutions + counts.deletions + counts.insertions == counts.distance


def test_reversed_swaps_deletions_and_insertions():
    counts = m.EditCounts(substitutions=2, deletions=3, insertions=1)
    flipped = counts.reversed()
    assert flipped.substitutions == 2
    assert flipped.deletions == 1
    assert flipped.insertions == 3
    assert flipped.distance == counts.distance


def test_reading_the_alignment_backwards_matches_the_reverse_comparison():
    """For an unambiguous alignment, S is shared and D/I swap."""
    forward = m.edit_counts("kitten", "sitting")
    backward = m.edit_counts("sitting", "kitten")
    assert forward.reversed() == backward


# ── Directional and symmetric rates ───────────────────────────────────────────


def test_error_rate_is_distance_over_reference_length():
    assert m.error_rate(3, 6) == 0.5


def test_error_rate_is_undefined_for_an_empty_reference():
    assert m.error_rate(3, 0) is None


def test_error_rate_above_one_is_not_clipped():
    """A hypothesis far longer than its reference genuinely disagrees by more
    than the reference's own length; clipping would hide that."""
    assert m.error_rate(10, 4) == 2.5


def test_symmetric_rate_is_the_harmonic_mean_of_the_directional_rates():
    distance, len_a, len_b = 3, 6, 7
    cer_ab = m.error_rate(distance, len_a)
    cer_ba = m.error_rate(distance, len_b)
    harmonic = 2 / (1 / cer_ab + 1 / cer_ba)
    assert m.symmetric_rate(distance, len_a, len_b) == pytest.approx(harmonic)


def test_symmetric_rate_is_order_independent():
    assert m.symmetric_rate(5, 20, 30) == m.symmetric_rate(5, 30, 20)


def test_symmetric_rate_of_two_empty_sides_is_zero():
    assert m.symmetric_rate(0, 0, 0) == 0.0


def test_symmetric_rate_with_one_empty_side_is_total_disagreement():
    """The raw formula would give 2.0, which is not a meaningful fraction."""
    assert m.symmetric_rate(5, 0, 5) == 1.0
    assert m.symmetric_rate(5, 5, 0) == 1.0


# ── prepare / compare ─────────────────────────────────────────────────────────


def test_prepare_normalizes_and_tokenizes_while_keeping_the_original():
    prepared = m.prepare("a1", "  The  regi-\n  ment.  ")
    assert prepared.original == "  The  regi-\n  ment.  "
    assert prepared.normalized == "The regiment."
    assert prepared.tokens == ("The", "regiment.")
    assert prepared.n_chars == len("The regiment.")
    assert prepared.n_words == 2


def test_compare_produces_every_retained_measurement():
    a = m.prepare("a", "the cat sat")
    b = m.prepare("b", "the dog sat")
    pair = m.compare(a, b)

    assert pair.a_id == "a" and pair.b_id == "b"
    assert pair.word_distance == 1
    assert pair.word_substitutions == 1
    assert pair.len_a_words == 3 and pair.len_b_words == 3
    assert pair.wer_a_to_b == pytest.approx(1 / 3)
    assert pair.wer_b_to_a == pytest.approx(1 / 3)
    assert pair.wer_sym == pytest.approx(1 / 3)
    # "cat" -> "dog" is three character substitutions
    assert pair.char_distance == 3
    assert pair.cer_sym == pytest.approx(2 * 3 / (11 + 11))


def test_compare_of_identical_texts_is_zero_disagreement():
    a = m.prepare("a", "The regiment marched south.")
    b = m.prepare("b", "The regiment marched south.")
    pair = m.compare(a, b)
    assert pair.cer_sym == 0.0
    assert pair.wer_sym == 0.0
    assert pair.char_distance == 0


def test_compare_directional_rates_differ_when_lengths_differ():
    a = m.prepare("a", "one two")
    b = m.prepare("b", "one two three four")
    pair = m.compare(a, b)
    assert pair.wer_a_to_b == pytest.approx(2 / 2)
    assert pair.wer_b_to_a == pytest.approx(2 / 4)
    assert pair.wer_a_to_b != pair.wer_b_to_a
    # ...but the symmetric score does not depend on which is the reference
    assert pair.wer_sym == pytest.approx(2 * 2 / (2 + 4))


def test_pair_as_dict_is_flat_and_complete():
    pair = m.compare(m.prepare("a", "x y"), m.prepare("b", "x z"))
    as_dict = pair.as_dict()
    for key in (
        "cer_a_to_b",
        "cer_b_to_a",
        "cer_sym",
        "wer_a_to_b",
        "wer_b_to_a",
        "wer_sym",
        "char_substitutions",
        "char_deletions",
        "char_insertions",
        "word_substitutions",
        "len_a_chars",
        "len_b_words",
    ):
        assert key in as_dict


def test_empty_attempt_yields_undefined_directional_rate_but_defined_symmetric():
    a = m.prepare("a", "")
    b = m.prepare("b", "some text")
    pair = m.compare(a, b)
    assert pair.cer_a_to_b is None
    assert pair.cer_b_to_a is not None
    assert pair.cer_sym == 1.0


# ── Backend equivalence (D4) ──────────────────────────────────────────────────


@pytest.mark.parametrize("a,b", PAIRS)
def test_both_backends_agree_on_distance(a, b):
    """The distance is unique, so it must match exactly across backends.

    The S/D/I *split* is not asserted here: where several alignments are
    optimal (``ab``/``ba`` costs 2 either as two substitutions or as one
    insertion plus one deletion) the two backends may legitimately choose
    differently. That is why the backend is recorded in provenance.
    """
    if not m._HAVE_RAPIDFUZZ:  # pragma: no cover
        pytest.skip("rapidfuzz not installed")
    fast = m._edit_counts_rapidfuzz(a, b)
    slow = m._edit_counts_python(a, b)
    assert fast.distance == slow.distance


@pytest.mark.parametrize("a,b", PAIRS)
def test_python_fallback_counts_sum_to_its_distance(a, b):
    counts = m._edit_counts_python(a, b)
    assert counts.substitutions + counts.deletions + counts.insertions == counts.distance


def test_python_fallback_matches_the_textbook_case():
    counts = m._edit_counts_python("kitten", "sitting")
    assert (counts.substitutions, counts.deletions, counts.insertions) == (2, 0, 1)


def test_python_fallback_handles_token_sequences():
    counts = m._edit_counts_python(("a", "b", "c"), ("a", "x", "c"))
    assert counts.distance == 1
    assert counts.substitutions == 1


# ── Alignment opcodes ─────────────────────────────────────────────────────────


def _reconstruct(a, b, opcodes):
    """Rebuild both sequences from the blocks, proving the alignment is valid."""
    rebuilt_a, rebuilt_b = [], []
    for tag, i1, i2, j1, j2 in opcodes:
        rebuilt_a.extend(a[i1:i2])
        rebuilt_b.extend(b[j1:j2])
        if tag == "equal":
            assert list(a[i1:i2]) == list(b[j1:j2])
    return rebuilt_a, rebuilt_b


def _opcode_cost(opcodes):
    return sum(
        (i2 - i1) if tag in ("replace", "delete") else (j2 - j1) if tag == "insert" else 0
        for tag, i1, i2, j1, j2 in opcodes
    )


def test_opcodes_describe_a_simple_substitution():
    ops = m.align_opcodes(["the", "cat", "sat"], ["the", "dog", "sat"])
    assert [op[0] for op in ops] == ["equal", "replace", "equal"]


def test_opcodes_separate_insertions_from_replacements():
    ops = m.align_opcodes(["a"], ["a", "b"])
    assert [op[0] for op in ops] == ["equal", "insert"]


@pytest.mark.parametrize("a,b", PAIRS)
def test_opcodes_reconstruct_both_sequences(a, b):
    rebuilt_a, rebuilt_b = _reconstruct(a, b, m.align_opcodes(a, b))
    assert rebuilt_a == list(a)
    assert rebuilt_b == list(b)


@pytest.mark.parametrize("a,b", PAIRS)
def test_opcode_cost_equals_the_edit_distance(a, b):
    assert _opcode_cost(m.align_opcodes(a, b)) == m.edit_counts(a, b).distance


def test_both_opcode_backends_reconstruct_and_cost_the_same():
    """The consensus vote is built on these blocks, so the fallback must produce
    an equally valid and equally cheap alignment."""
    if not m._HAVE_RAPIDFUZZ:  # pragma: no cover
        pytest.skip("rapidfuzz not installed")
    import random

    random.seed(0)
    for _ in range(100):
        a = [random.choice("abcdef") for _ in range(random.randint(0, 8))]
        b = [random.choice("abcdef") for _ in range(random.randint(0, 8))]
        fast = m._opcodes_rapidfuzz(a, b)
        slow = m._opcodes_python(a, b)
        assert _reconstruct(a, b, fast) == (a, b)
        assert _reconstruct(a, b, slow) == (a, b)
        assert _opcode_cost(fast) == _opcode_cost(slow)


def test_rapidfuzz_replace_blocks_are_one_to_one():
    """Unlike difflib, a Levenshtein replace block spans equal lengths — the
    consensus column mapping relies on this."""
    if not m._HAVE_RAPIDFUZZ:  # pragma: no cover
        pytest.skip("rapidfuzz not installed")
    for a, b in PAIRS:
        for tag, i1, i2, j1, j2 in m._opcodes_rapidfuzz(a, b):
            if tag == "replace":
                assert (i2 - i1) == (j2 - j1)


# ── Provenance ────────────────────────────────────────────────────────────────


def test_metric_definitions_are_reported_for_provenance():
    definitions = m.metric_definitions()
    assert "harmonic mean" in definitions["symmetric_definition"]
    assert definitions["backend"] == m.BACKEND
    assert definitions["cer_definition"] == m.CER_DEFINITION
    assert definitions["wer_definition"] == m.WER_DEFINITION


def test_backend_is_reported_and_non_empty():
    assert m.BACKEND
