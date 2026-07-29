"""Attempt collection and health screening (spec §2, §3.1, §23, §24)."""

import pytest

from backend.analysis import attempts as at

pytestmark = pytest.mark.unit


def _run(model="gemini-2.5-flash", outputs=None, timestamp="2026-07-24T09:12:00Z", **extra):
    run = {
        "timestamp": timestamp,
        "started_at": timestamp,
        "model": model,
        "provider": "Gemini",
        "profile_name": "civil_war_htr",
        "temperature": 1.0,
        "outputs": outputs if outputs is not None else ["Some transcription text here."],
    }
    run.update(extra)
    return run


def _doc(runs, harmonizations=None):
    return {
        "schema_version": "2.0",
        "metadata": {"root": "letter_042"},
        "runs": runs,
        "harmonizations": harmonizations or [],
    }


LONG_A = "The regiment marched south at dawn, and the men were in good spirits."
LONG_B = "The regiment marched south at dawn, and the men were in good spirit."


# ── Collection and identity (§3.1, D10) ───────────────────────────────────────


def test_every_output_of_every_run_becomes_an_attempt():
    doc = _doc([_run(outputs=["a", "b"]), _run(outputs=["c"]), _run(outputs=["d", "e"])])
    collected = at.collect_attempts(doc)
    assert len(collected) == 5


def test_attempt_ids_encode_run_and_output_position():
    doc = _doc([_run(outputs=["a", "b"]), _run(outputs=["c"])])
    ids = [a.attempt_id for a in at.collect_attempts(doc)]
    assert ids == ["r0:o0", "r0:o1", "r1:o0"]


def test_attempts_are_returned_in_canonical_order():
    doc = _doc([_run(outputs=["a", "b"]), _run(outputs=["c", "d"])])
    collected = at.collect_attempts(doc)
    assert [(a.run_index, a.output_index) for a in collected] == [
        (0, 0),
        (0, 1),
        (1, 0),
        (1, 1),
    ]


def test_run_metadata_is_attached_to_each_attempt():
    doc = _doc([_run(model="gpt-4o", outputs=["x", "y"])])
    first = at.collect_attempts(doc)[0]
    assert first.model == "gpt-4o"
    assert first.provider == "Gemini"
    assert first.profile_name == "civil_war_htr"
    assert first.temperature == 1.0
    assert first.created_at == "2026-07-24T09:12:00Z"


def test_metadata_is_not_flattened_away_across_runs():
    """The harmonization router collapses runs into one anonymous list; §3.1
    needs per-attempt model identity, so this must not do the same."""
    doc = _doc([_run(model="gemini-2.5-flash"), _run(model="gpt-4o")])
    models = [a.model for a in at.collect_attempts(doc)]
    assert models == ["gemini-2.5-flash", "gpt-4o"]


def test_labels_distinguish_multi_output_runs_from_single_output_runs():
    doc = _doc([_run(outputs=["a", "b"]), _run(outputs=["c"])])
    labels = [a.label for a in at.collect_attempts(doc)]
    assert labels == ["Run 1·1", "Run 1·2", "Run 2"]


def test_missing_run_id_does_not_break_identity():
    """save_transcription_run does not write run_id, so identity must not need it."""
    doc = _doc([_run(outputs=["a"])])
    attempt = at.collect_attempts(doc)[0]
    assert attempt.run_id is None
    assert attempt.attempt_id == "r0:o0"


def test_run_id_is_carried_through_when_present():
    doc = _doc([_run(outputs=["a"], run_id="abc-123")])
    assert at.collect_attempts(doc)[0].run_id == "abc-123"


def test_empty_document_yields_no_attempts():
    assert at.collect_attempts(_doc([])) == []


def test_missing_runs_key_is_tolerated():
    assert at.collect_attempts({"metadata": {}}) == []


# ── Output shapes (D3) ────────────────────────────────────────────────────────


def test_string_outputs_are_read_directly():
    doc = _doc([_run(outputs=["plain string"])])
    assert at.collect_attempts(doc)[0].text == "plain string"


def test_dict_outputs_with_a_text_key_are_supported():
    doc = _doc([_run(outputs=[{"text": "from a dict", "tokens": 12}])])
    assert at.collect_attempts(doc)[0].text == "from a dict"


def test_none_output_becomes_empty_text():
    doc = _doc([_run(outputs=[None])])
    attempt = at.collect_attempts(doc)[0]
    assert attempt.text == ""
    assert attempt.health.status == at.HEALTH_EMPTY


# ── Text overrides (D3) ───────────────────────────────────────────────────────


def test_text_override_replaces_the_stored_text_and_is_flagged():
    doc = _doc([_run(outputs=["stored", "untouched"])])
    collected = at.collect_attempts(doc, text_overrides={"r0:o0": "edited in session"})
    assert collected[0].text == "edited in session"
    assert collected[0].edited_in_session is True
    assert collected[1].edited_in_session is False


# ── Consensus records (§2.1) ──────────────────────────────────────────────────


def test_harmonizations_are_surfaced_as_consensus_records():
    doc = _doc(
        [_run(outputs=["a"])],
        harmonizations=[{"harmonized_text": "merged text", "model_used": "gpt-4o"}],
    )
    collected = at.collect_attempts(doc)
    consensus = [a for a in collected if a.source_type == at.SOURCE_CONSENSUS]
    assert len(consensus) == 1
    assert consensus[0].label == "Harmonization 1"
    assert consensus[0].text == "merged text"


def test_a_consensus_is_never_an_independent_replicate():
    doc = _doc(
        [_run(outputs=["a"])], harmonizations=[{"harmonized_text": "merged text"}]
    )
    collected = at.collect_attempts(doc)
    consensus = next(a for a in collected if a.source_type == at.SOURCE_CONSENSUS)
    assert consensus.is_replicate is False
    assert at.SOURCE_CONSENSUS not in at.REPLICATE_SOURCE_TYPES


def test_consensus_records_can_be_omitted():
    doc = _doc([_run(outputs=["a"])], harmonizations=[{"harmonized_text": "m"}])
    collected = at.collect_attempts(doc, include_consensus=False)
    assert all(a.source_type == at.SOURCE_AI for a in collected)


def test_a_reference_is_not_a_replicate_either():
    assert at.SOURCE_REFERENCE not in at.REPLICATE_SOURCE_TYPES


# ── Health screening (§23) ────────────────────────────────────────────────────


def test_empty_output_is_flagged_not_scored():
    health = at.screen_health("   \n  ")
    assert health.status == at.HEALTH_EMPTY
    assert health.is_suitable is False


def test_very_short_output_is_near_empty():
    assert at.screen_health("too short").status == at.HEALTH_NEAR_EMPTY


def test_output_far_below_the_group_median_is_near_empty():
    text = "A short line of text that is over the absolute floor."
    assert at.screen_health(text).status == at.HEALTH_OK
    assert at.screen_health(text, median_length=5000).status == at.HEALTH_NEAR_EMPTY


@pytest.mark.parametrize(
    "text",
    [
        "I'm sorry, I cannot transcribe this image.",
        "I am unable to read the handwriting in this document.",
        "Error: the model returned no content for this request.",
        "As an AI language model, I must decline to process this.",
        "Unable to determine the contents of the provided image file.",
    ],
)
def test_refusal_and_error_messages_are_flagged(text):
    health = at.screen_health(text)
    assert health.status == at.HEALTH_ERROR_TEXT
    assert health.is_suitable is False


def test_ordinary_transcription_beginning_with_a_similar_word_is_not_flagged():
    """The patterns are anchored, so historical prose is not caught."""
    text = "Sorrowfully I write to inform you of the loss of our dear friend."
    assert at.screen_health(text).status == at.HEALTH_OK


def test_a_fenced_code_block_response_is_flagged():
    health = at.screen_health("```json\n{\"error\": \"no text detected here at all\"}\n```")
    assert health.status == at.HEALTH_ERROR_TEXT


def test_replacement_characters_mark_text_as_corrupt():
    assert at.screen_health("abc" + "�" * 40).status == at.HEALTH_CORRUPT


def test_control_characters_mark_text_as_corrupt():
    assert at.screen_health("ab" + "\x00" * 40).status == at.HEALTH_CORRUPT


def test_healthy_text_passes():
    health = at.screen_health(LONG_A)
    assert health.status == at.HEALTH_OK
    assert health.is_suitable is True
    assert health.char_count == len(LONG_A)


def test_health_flags_do_not_depend_on_the_chosen_analysis_profile():
    """Screening uses a fixed normalization so a flag cannot appear or vanish
    when the user changes comparison settings."""
    assert at.SCREENING_PROFILE == "standard_historical"


# ── Duplicates (§24) ──────────────────────────────────────────────────────────


def test_identical_text_from_separate_runs_stays_two_distinct_attempts():
    """Separate runs producing identical output are evidence of reproducibility
    and must not be collapsed."""
    doc = _doc(
        [
            _run(outputs=[LONG_A], timestamp="2026-07-24T09:00:00Z"),
            _run(outputs=[LONG_A], timestamp="2026-07-24T10:00:00Z"),
        ]
    )
    collected = at.collect_attempts(doc)
    assert len(collected) == 2
    assert all(a.health.status == at.HEALTH_OK for a in collected)
    assert all(a.health.is_suitable for a in collected)


def test_identical_content_is_cross_linked_as_information():
    doc = _doc(
        [
            _run(outputs=[LONG_A], timestamp="2026-07-24T09:00:00Z"),
            _run(outputs=[LONG_A], timestamp="2026-07-24T10:00:00Z"),
        ]
    )
    first, second = at.collect_attempts(doc)
    assert first.health.identical_to == ("r1:o0",)
    assert second.health.identical_to == ("r0:o0",)


def test_differing_attempts_are_not_cross_linked():
    doc = _doc([_run(outputs=[LONG_A]), _run(outputs=[LONG_B], timestamp="2026-07-24T10:00:00Z")])
    for attempt in at.collect_attempts(doc):
        assert attempt.health.identical_to == ()


def test_the_same_record_stored_twice_is_flagged_as_a_duplicate_record():
    run = _run(outputs=[LONG_A])
    doc = _doc([run, dict(run)])
    first, second = at.collect_attempts(doc)
    assert first.health.status == at.HEALTH_OK
    assert second.health.status == at.HEALTH_DUPLICATE_RECORD
    assert second.health.is_suitable is False


def test_duplicate_records_are_detected_by_run_id_when_present():
    run_a = _run(outputs=["first text that is long enough"], run_id="same-id")
    run_b = _run(
        outputs=["different text entirely but same id"],
        run_id="same-id",
        timestamp="2026-07-24T11:00:00Z",
    )
    _, second = at.collect_attempts(_doc([run_a, run_b]))
    assert second.health.status == at.HEALTH_DUPLICATE_RECORD


# ── Selection helpers (§3.2, D10) ─────────────────────────────────────────────


def test_default_selection_checks_healthy_replicates_only():
    doc = _doc(
        [
            _run(outputs=[LONG_A]),
            _run(outputs=[""], timestamp="2026-07-24T10:00:00Z"),
            _run(outputs=[LONG_B], timestamp="2026-07-24T11:00:00Z"),
        ],
        harmonizations=[{"harmonized_text": LONG_A}],
    )
    collected = at.collect_attempts(doc)
    assert at.default_selection(collected) == ["r0:o0", "r2:o0"]


def test_degenerate_attempts_remain_visible_even_though_unchecked():
    """§3.2 — excluded attempts stay visible so the user can see what exists."""
    doc = _doc([_run(outputs=[LONG_A, ""])])
    collected = at.collect_attempts(doc)
    assert len(collected) == 2
    assert "r0:o1" not in at.default_selection(collected)


def test_selected_attempts_returns_canonical_order_regardless_of_input_order():
    """Two clients sending the same set in different orders must get the same
    result, so client ordering is discarded (D10)."""
    doc = _doc([_run(outputs=["a", "b", "c"])])
    collected = at.collect_attempts(doc)
    forward = at.selected_attempts(collected, ["r0:o0", "r0:o1", "r0:o2"])
    shuffled = at.selected_attempts(collected, ["r0:o2", "r0:o0", "r0:o1"])
    assert [a.attempt_id for a in forward] == [a.attempt_id for a in shuffled]


def test_selected_attempts_rejects_unknown_ids():
    collected = at.collect_attempts(_doc([_run(outputs=["a"])]))
    with pytest.raises(KeyError):
        at.selected_attempts(collected, ["r9:o9"])


def test_attempt_as_dict_carries_the_selection_list_metadata():
    doc = _doc([_run(outputs=[LONG_A])])
    as_dict = at.collect_attempts(doc)[0].as_dict()
    for key in (
        "attempt_id",
        "label",
        "model",
        "provider",
        "profile_name",
        "created_at",
        "source_type",
        "is_replicate",
        "char_count",
        "health",
    ):
        assert key in as_dict
    # The full text is fetched separately, on demand (§3.1).
    assert "text" not in as_dict
