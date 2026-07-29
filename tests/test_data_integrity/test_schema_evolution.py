from datetime import datetime, timedelta
from pathlib import Path

import json_manager as jm
import session_workspace as sw


def test_create_v2_schema_contains_required_fields_and_optional_metadata():
    schema = sw.create_v2_json_schema(
        root="doc001",
        image_filename="doc001.jpg",
        settings={"provider": "OpenAI"},
        app_version="2.1.0",
        session_id="session-abc",
    )

    assert schema["schema_version"] == "2.0"
    assert schema["metadata"]["root"] == "doc001"
    assert schema["metadata"]["image_filename"] == "doc001.jpg"
    assert schema["metadata"]["settings"] == {"provider": "OpenAI"}
    assert schema["metadata"]["app_version"] == "2.1.0"
    assert schema["metadata"]["session_id"] == "session-abc"
    assert schema["runs"] == []
    assert schema["harmonizations"] == []


def test_create_and_validate_run_record_round_trip():
    started = datetime.utcnow()
    completed = started + timedelta(seconds=2)

    run = sw.create_run_record(
        model="gpt-4o",
        temperature=1.0,
        base_prompt="system",
        domain_prompt="domain hint",
        tokens_in=123,
        tokens_out=45,
        token_method="api_response",
        started_at=started,
        completed_at=completed,
        outputs=["t1", "t2"],
        provider="OpenAI",
        profile_name="civil_war_htr",
        estimated_cost_usd=0.02,
    )

    assert sw.validate_run_record(run) is True
    assert run["duration_ms"] >= 2000
    assert run["provider"] == "OpenAI"
    assert run["profile_name"] == "civil_war_htr"


def test_append_run_updates_metadata_and_schema_validates():
    schema = sw.create_v2_json_schema(root="r1", image_filename="r1.jpg")
    before = schema["metadata"]["updated_at"]

    started = datetime.utcnow()
    run = sw.create_run_record(
        model="gpt-4o-mini",
        temperature=0.7,
        base_prompt="system",
        domain_prompt="",
        tokens_in=10,
        tokens_out=20,
        token_method="api_response",
        started_at=started,
        completed_at=started + timedelta(milliseconds=50),
        outputs=["ok"],
    )

    sw.append_run_to_v2_json(schema, run)

    assert len(schema["runs"]) == 1
    assert schema["metadata"]["updated_at"] >= before
    assert sw.validate_v2_json_schema(schema) is True


def test_append_harmonization_creates_missing_array_and_updates_timestamp():
    schema = sw.create_v2_json_schema(root="r2", image_filename="r2.jpg")
    del schema["harmonizations"]
    before = schema["metadata"]["updated_at"]

    harm = sw.create_harmonization_record(
        harmonized_text="final text",
        source_run_ids=["run-1"],
        source_indices=[0],
        model_used="gpt-4o",
        temperature=0.3,
        tokens_used={"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        created_at=datetime.utcnow(),
    )

    sw.append_harmonization_to_v2_json(schema, harm)

    assert "harmonizations" in schema
    assert len(schema["harmonizations"]) == 1
    assert schema["metadata"]["updated_at"] >= before


def test_validate_v2_schema_rejects_missing_or_invalid_fields():
    missing_required = {"schema_version": "2.0", "metadata": {}}
    wrong_version = {"schema_version": "1.0", "metadata": {}, "runs": []}
    runs_not_list = {"schema_version": "2.0", "metadata": {}, "runs": {}}

    assert sw.validate_v2_json_schema(missing_required) is False
    assert sw.validate_v2_json_schema(wrong_version) is False
    assert sw.validate_v2_json_schema(runs_not_list) is False


def test_file_index_registers_corrupted_json_without_crashing(monkeypatch, tmp_path):
    monkeypatch.setenv("TRANSCRIBE_SESSION_ROOT", str(tmp_path))

    ws = sw.SessionWorkspace(session_id="schema-corrupt")
    assert ws.ensure_workspace() is True

    bad_json = ws.workspace_path / "bad.transcription.json"
    bad_json.write_text("{ this is not valid json", encoding="utf-8")

    idx = sw.FileIndex(ws)
    record = idx.register_file(bad_json)

    assert record.json_path == str(bad_json)
    assert "metadata_error" in record.summary
    assert record.run_count == 0


def test_json_manager_validate_json_structure_handles_v2_and_legacy():
    v2 = sw.create_v2_json_schema(root="r3", image_filename="r3.jpg")
    legacy = {"transcriptions": ["a", "b"]}
    invalid = ["not", "a", "dict"]

    assert jm.validate_json_structure(v2) is True
    assert jm.validate_json_structure(legacy) is True
    assert jm.validate_json_structure(invalid) is False
