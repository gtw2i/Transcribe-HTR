"""Report assembly, provenance and research summary (spec §22, §25, §30)."""

import json

import pytest

from backend.analysis import attempts as at
from backend.analysis import report as rp

pytestmark = pytest.mark.unit


TIGHT = "The regiment marched south at dawn, and the men were in good spirits."
TIGHT_VARIANT = "The regiment marched south at dawn, and the men were in good spirit."
TIGHT_VARIANT_2 = "The regiment marched south at dawn and the men were in good spirits."
TIGHT_VARIANT_3 = "The regiment marched south at dawn, and the men were in fine spirits."
DIVERGENT = "A company of cavalry rode north through the night, and it rained heavily."


def _doc(texts, harmonizations=None):
    return {
        "schema_version": "2.0",
        "metadata": {"root": "letter_042"},
        "runs": [
            {
                "timestamp": f"2026-07-24T09:{i:02d}:00Z",
                "started_at": f"2026-07-24T09:{i:02d}:00Z",
                "model": "gemini-2.5-flash",
                "provider": "Gemini",
                "profile_name": "civil_war_htr",
                "temperature": 1.0,
                "outputs": [text],
            }
            for i, text in enumerate(texts)
        ],
        "harmonizations": harmonizations or [],
    }


FIVE = [TIGHT, TIGHT_VARIANT, TIGHT_VARIANT_2, TIGHT_VARIANT_3, DIVERGENT]


def _report(texts=None, **kwargs):
    texts = FIVE if texts is None else texts
    collected = at.collect_attempts(_doc(texts))
    kwargs.setdefault("root", "letter_042")
    kwargs.setdefault("analysis_id", "fixed-id")
    kwargs.setdefault("created_at", "2026-07-26T14:03:11+00:00")
    return rp.build_report(
        collected, at.default_selection(collected), **kwargs
    ), collected


# ── Assembly ──────────────────────────────────────────────────────────────────


def test_report_covers_every_selected_attempt():
    report, _ = _report()
    assert report.n_attempts == 5
    assert report.n_pairs == 10
    assert len(report.per_attempt) == 5
    assert len(report.attempt_metadata) == 5


def test_report_computes_the_ten_pairs_of_the_acceptance_scenario():
    report, _ = _report()
    assert report.summaries["cer"].n_pairs == 10
    assert report.summaries["wer"].n_pairs == 10


def test_selection_order_does_not_affect_the_result():
    """§27, D10 — canonical order is imposed server-side."""
    collected = at.collect_attempts(_doc(FIVE))
    ids = at.default_selection(collected)
    forward = rp.build_report(
        collected, ids, root="r", analysis_id="x", created_at="t"
    )
    shuffled = rp.build_report(
        collected, list(reversed(ids)), root="r", analysis_id="x", created_at="t"
    )
    assert forward.as_dict() == shuffled.as_dict()


def test_repeating_the_analysis_produces_identical_output():
    """§27 — the deterministic pipeline has no RNG and no ordering ambiguity."""
    first, _ = _report()
    second, _ = _report()
    assert first.as_dict() == second.as_dict()


def test_unknown_attempt_ids_are_rejected():
    collected = at.collect_attempts(_doc(FIVE))
    with pytest.raises(KeyError):
        rp.build_report(collected, ["r9:o9"], root="r")


def test_excluded_attempts_are_recorded_with_a_reason():
    collected = at.collect_attempts(_doc(FIVE))
    ids = at.default_selection(collected)[:4]
    report = rp.build_report(collected, ids, root="letter_042")

    assert report.n_attempts == 4
    excluded = {e["attempt_id"]: e["reason"] for e in report.attempts_excluded}
    assert excluded == {"r4:o0": rp.EXCLUDED_USER}


def test_degenerate_attempts_are_excluded_with_a_health_reason():
    collected = at.collect_attempts(_doc(FIVE[:4] + [""]))
    report = rp.build_report(
        collected, at.default_selection(collected), root="letter_042"
    )
    reasons = {e["attempt_id"]: e["reason"] for e in report.attempts_excluded}
    assert reasons["r4:o0"] == "health:empty"


def test_a_consensus_record_is_excluded_as_not_an_independent_attempt():
    collected = at.collect_attempts(
        _doc(FIVE, harmonizations=[{"harmonized_text": TIGHT}])
    )
    report = rp.build_report(
        collected, at.default_selection(collected), root="letter_042"
    )
    reasons = {e["attempt_id"]: e["reason"] for e in report.attempts_excluded}
    assert reasons["h0"] == rp.EXCLUDED_NOT_REPLICATE


def test_the_divergent_attempt_is_flagged():
    report, _ = _report()
    assert "r4:o0" in report.outliers.flagged_ids


# ── Provenance (§25) ──────────────────────────────────────────────────────────


def test_settings_record_everything_needed_to_reproduce_the_analysis():
    report, _ = _report()
    settings = report.settings

    assert settings["normalization"]["id"] == "standard_historical"
    assert settings["normalization"]["steps"]
    assert settings["normalization"]["version"]
    assert settings["tokenizer"]["id"] == "word_simple"
    assert settings["uncertainty_method"] == "jackknife_over_attempts"
    assert "harmonic mean" in settings["symmetric_definition"]
    assert settings["cer_definition"]
    assert settings["wer_definition"]
    assert settings["backend"]


def test_the_record_identifies_the_source_document_and_version():
    report, _ = _report(image_filename="letter_042.jpg")
    as_dict = report.as_dict()
    assert as_dict["source_document"] == {
        "root": "letter_042",
        "image_filename": "letter_042.jpg",
    }
    assert as_dict["analysis_version"] == rp.ANALYSIS_VERSION


def test_attempt_metadata_carries_model_and_run_provenance():
    report, _ = _report()
    first = report.attempt_metadata[0]
    assert first["model"] == "gemini-2.5-flash"
    assert first["provider"] == "Gemini"
    assert first["profile_name"] == "civil_war_htr"
    assert first["created_at"]


def test_both_included_and_excluded_attempts_are_listed():
    collected = at.collect_attempts(_doc(FIVE))
    report = rp.build_report(collected, at.default_selection(collected)[:3], root="r")
    as_dict = report.as_dict()
    assert len(as_dict["attempts_included"]) == 3
    assert len(as_dict["attempts_excluded"]) == 2


# ── Serialization round-trip ──────────────────────────────────────────────────


def test_the_record_is_json_serializable():
    report, _ = _report()
    encoded = json.dumps(report.as_dict())
    assert json.loads(encoded)["analysis_id"] == "fixed-id"


def test_report_round_trips_through_its_serialized_form():
    report, _ = _report()
    original = report.as_dict()
    restored = rp.report_from_dict(original)
    assert restored.as_dict() == original


def test_round_trip_preserves_matrices_including_undefined_cells():
    collected = at.collect_attempts(_doc([TIGHT, TIGHT_VARIANT]))
    report = rp.build_report(
        collected, at.default_selection(collected), root="r",
        analysis_id="x", created_at="t",
    )
    restored = rp.report_from_dict(report.as_dict())
    assert restored.matrices.cer_symmetric.tolist() == report.matrices.cer_symmetric.tolist()


def test_round_trip_survives_a_json_encode_decode_cycle():
    report, _ = _report()
    cycled = rp.report_from_dict(json.loads(json.dumps(report.as_dict())))
    assert cycled.as_dict() == report.as_dict()


def test_round_trip_preserves_the_outlier_verdicts():
    report, _ = _report()
    restored = rp.report_from_dict(report.as_dict())
    assert restored.outliers.flagged_ids == report.outliers.flagged_ids
    assert restored.outliers.alternative_explanations == report.outliers.alternative_explanations


def test_the_report_includes_the_medoid_and_deterministic_consensus():
    """§14 — the deterministic consensus is the default statistical consensus."""
    report, _ = _report()
    results = report.as_dict()["results"]
    assert results["medoid_attempt_id"] in report.attempts_included
    assert results["medoid"]["attempt_id"] == results["medoid_attempt_id"]
    assert results["consensus"]["method"] == "deterministic_vote_v1"
    assert results["consensus"]["text"]
    assert len(results["consensus_comparison"]) == 5
    assert "not independent of the attempts" in results["consensus_caveat"]


def test_consensus_can_be_skipped():
    collected = at.collect_attempts(_doc(FIVE))
    report = rp.build_report(
        collected, at.default_selection(collected), root="r", with_consensus=False
    )
    results = report.as_dict()["results"]
    assert results["medoid_attempt_id"] is None
    assert results["consensus"] is None
    assert results["consensus_comparison"] is None
    assert "No consensus transcription was computed" in report.narrative


def test_the_narrative_reports_the_consensus_disagreement():
    report, _ = _report()
    assert "deterministic consensus transcription had a median word disagreement" in (
        report.narrative
    )


# ── Small-sample guidance (§22) ───────────────────────────────────────────────


def test_two_attempts_report_that_outlier_detection_is_not_meaningful():
    guidance = rp.assess_sample_size(2)
    assert guidance.level == rp.SAMPLE_MINIMAL
    assert guidance.outlier_detection_available is False
    assert guidance.uncertainty_available is False
    assert "no independent group" in guidance.message


def test_three_attempts_are_available_but_caveated():
    guidance = rp.assess_sample_size(3)
    assert guidance.level == rp.SAMPLE_SMALL
    assert guidance.outlier_detection_available is False
    assert "small number of attempts" in guidance.message


def test_four_or_more_attempts_unlock_the_full_analysis():
    guidance = rp.assess_sample_size(4)
    assert guidance.level == rp.SAMPLE_ADEQUATE
    assert guidance.outlier_detection_available is True
    assert guidance.uncertainty_available is True


def test_a_two_attempt_report_still_computes_pairwise_values():
    report, _ = _report([TIGHT, DIVERGENT])
    assert report.n_pairs == 1
    assert report.summaries["cer"].median > 0
    assert report.small_sample.level == rp.SAMPLE_MINIMAL
    assert report.outliers.applicable is False
    assert report.variability["cer"].uncertainty.applicable is False


# ── Research summary (§30) ────────────────────────────────────────────────────


def test_the_narrative_reports_every_required_element():
    report, _ = _report()
    narrative = report.narrative

    assert "Five independent transcription attempts" in narrative
    assert "10 unique pairwise comparisons" in narrative
    assert "Median pairwise character disagreement" in narrative
    assert "median pairwise word disagreement" in narrative
    assert "IQR" in narrative
    assert "jackknife standard error" in narrative
    assert "consensus" in narrative.lower()


def test_the_narrative_names_the_unusual_attempt():
    report, _ = _report()
    assert "Run 5" in report.narrative
    assert "flagged for inspection rather than treated as incorrect" in report.narrative


def test_the_narrative_says_when_nothing_was_excluded():
    report, _ = _report()
    assert "No available transcription attempts were excluded" in report.narrative


def test_the_narrative_states_what_was_excluded():
    collected = at.collect_attempts(_doc(FIVE))
    report = rp.build_report(
        collected, at.default_selection(collected)[:4], root="r"
    )
    assert "1 available transcription attempt was excluded" in report.narrative


def test_the_narrative_reports_a_homogeneous_group_plainly():
    report, _ = _report([TIGHT, TIGHT_VARIANT, TIGHT_VARIANT_2, TIGHT_VARIANT_3])
    assert "No attempt showed substantially greater disagreement" in report.narrative


def test_the_narrative_never_claims_accuracy():
    """§28, §30 — consistency must not be presented as ground-truth accuracy."""
    report, _ = _report()
    lowered = report.narrative.lower()
    assert "do not establish accuracy" in lowered
    for banned in ("error rate", "true error", "correct transcription", "inaccurate"):
        assert banned not in lowered


def test_the_narrative_carries_the_small_sample_caveat_when_relevant():
    report, _ = _report([TIGHT, TIGHT_VARIANT, DIVERGENT])
    assert "provisional" in report.narrative


def test_the_narrative_mentions_the_consensus_method_when_supplied():
    narrative = rp.build_narrative(
        n_attempts=4,
        summaries=_report()[0].summaries,
        variability=_report()[0].variability,
        outliers=_report()[0].outliers,
        excluded=[],
        small_sample=rp.assess_sample_size(4),
        consensus_method="deterministic",
        consensus_median_wer=0.026,
    )
    assert "deterministic consensus transcription had a median word disagreement of 2.6%" in narrative
