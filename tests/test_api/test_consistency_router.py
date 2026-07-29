"""Contract tests for backend/routers/consistency.py (spec §4a, §27).

The backend uses flat imports (``from core.json_manager import ...``, and inside
``core/`` bare names like ``from logging_config import ...``) that resolve
because ``pytest.ini`` puts ``backend/`` and its subpackages on ``sys.path``,
mirroring what ``backend/main.py`` arranges at import time.

The app under test is a minimal FastAPI instance around the router with the
session dependency overridden, so no cookie or session middleware is involved.
"""

import csv
import io
import json
import zipfile
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi", reason="fastapi is required for router tests")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

_BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"

pytestmark = pytest.mark.api


@pytest.fixture(scope="module")
def backend_env():
    """Import the backend dependency module and the consistency router."""
    import importlib

    dependencies = importlib.import_module("dependencies")
    router_module = importlib.import_module("routers.consistency")
    return dependencies, router_module


TIGHT = "The regiment marched south at dawn, and the men were in good spirits."
VARIANT_1 = "The regiment marched south at dawn, and the men were in good spirit."
VARIANT_2 = "The regiment marched south at dawn and the men were in good spirits."
VARIANT_3 = "The regiment marched south at dawn, and the men were in fine spirits."
DIVERGENT = "A company of cavalry rode north through the night, and it rained hard."

FIVE = [TIGHT, VARIANT_1, VARIANT_2, VARIANT_3, DIVERGENT]


class _Record:
    """Minimal stand-in for a session_workspace.FileRecord."""

    def __init__(self, json_path):
        self.json_path = str(json_path) if json_path else None
        self.image_path = None
        self.run_count = 0

    def has_json(self):
        return self.json_path is not None


class _FileIndex:
    def __init__(self, records):
        self.records = records


def _document(texts, harmonizations=None):
    return {
        "schema_version": "2.0",
        "metadata": {"root": "letter_042", "image_filename": "letter_042.jpg"},
        "runs": [
            {
                "timestamp": f"2026-07-24T09:0{i}:00Z",
                "started_at": f"2026-07-24T09:0{i}:00Z",
                "model": "gemini-2.5-flash" if i < 3 else "gpt-4o",
                "provider": "Gemini" if i < 3 else "OpenAI",
                "profile_name": "civil_war_htr",
                "temperature": 1.0,
                "outputs": [text],
            }
            for i, text in enumerate(texts)
        ],
        "harmonizations": harmonizations or [],
    }


@pytest.fixture
def client(tmp_path, backend_env):
    """A client whose session resolves to a document written under tmp_path."""
    dependencies, consistency_router = backend_env

    json_path = tmp_path / "letter_042.transcription.json"
    json_path.write_text(json.dumps(_document(FIVE)), encoding="utf-8")

    index = _FileIndex({"letter_042": _Record(json_path)})

    app = FastAPI()
    app.include_router(consistency_router.router, prefix="/api")
    app.dependency_overrides[dependencies.get_file_index] = lambda: index
    # The save endpoint also resolves a workspace. It is not used to locate the
    # document — the file index is — but the dependency is declared, so it has
    # to be satisfied for the route to run without a session cookie.
    app.dependency_overrides[dependencies.get_workspace] = lambda: None

    consistency_router.clear_analysis_cache()
    with TestClient(app) as test_client:
        test_client.json_path = json_path
        test_client.index = index
        yield test_client
    consistency_router.clear_analysis_cache()


# ── Options ───────────────────────────────────────────────────────────────────


def test_options_lists_the_normalization_profiles_with_their_steps(client):
    body = client.get("/api/consistency/options").json()
    ids = {p["id"] for p in body["normalization_profiles"]}
    assert ids == {"standard_historical", "diplomatic", "normalized"}
    assert body["default_normalization_profile"] == "standard_historical"
    standard = next(
        p for p in body["normalization_profiles"] if p["id"] == "standard_historical"
    )
    assert "join_linebreak_hyphens" in standard["steps"]


def test_options_reports_the_metric_definitions_and_backend(client):
    body = client.get("/api/consistency/options").json()
    assert "harmonic mean" in body["definitions"]["symmetric_definition"]
    assert body["backend"]
    assert body["analysis_version"]


def test_options_lists_the_tokenizers(client):
    body = client.get("/api/consistency/options").json()
    assert {t["id"] for t in body["tokenizers"]} == {"word_simple", "word_punct"}


# ── Attempts (§3.1) ───────────────────────────────────────────────────────────


def test_attempts_returns_every_attempt_with_identifying_metadata(client):
    body = client.get("/api/consistency/attempts?root=letter_042").json()
    assert body["n_available"] == 5
    assert body["n_replicates"] == 5

    first = body["attempts"][0]
    assert first["attempt_id"] == "r0:o0"
    assert first["label"] == "Run 1"
    assert first["model"] == "gemini-2.5-flash"
    assert first["provider"] == "Gemini"
    assert first["profile_name"] == "civil_war_htr"
    assert first["created_at"] == "2026-07-24T09:00:00Z"
    assert first["health"]["status"] == "ok"


def test_attempts_does_not_ship_the_full_text_in_the_list(client):
    """§3.1 — the selection list does not need the text; it is fetched on demand."""
    body = client.get("/api/consistency/attempts?root=letter_042").json()
    assert "text" not in body["attempts"][0]
    assert body["attempts"][0]["char_count"] > 0


def test_attempts_distinguishes_the_models_used(client):
    body = client.get("/api/consistency/attempts?root=letter_042").json()
    assert [a["model"] for a in body["attempts"]] == [
        "gemini-2.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash",
        "gpt-4o",
        "gpt-4o",
    ]


def test_default_selection_covers_the_healthy_replicates(client):
    body = client.get("/api/consistency/attempts?root=letter_042").json()
    assert body["default_selection"] == ["r0:o0", "r1:o0", "r2:o0", "r3:o0", "r4:o0"]


def test_a_degenerate_attempt_is_listed_but_unselected(client, tmp_path):
    client.json_path.write_text(
        json.dumps(_document(FIVE[:4] + [""])), encoding="utf-8"
    )
    body = client.get("/api/consistency/attempts?root=letter_042").json()
    assert body["n_available"] == 5
    assert "r4:o0" not in body["default_selection"]
    assert body["attempts"][4]["health"]["status"] == "empty"
    assert body["attempts"][4]["health"]["is_suitable"] is False


def test_a_consensus_record_is_listed_but_is_not_a_replicate(client):
    client.json_path.write_text(
        json.dumps(_document(FIVE, harmonizations=[{"harmonized_text": TIGHT}])),
        encoding="utf-8",
    )
    body = client.get("/api/consistency/attempts?root=letter_042").json()
    consensus = next(a for a in body["attempts"] if a["source_type"] == "consensus")
    assert consensus["is_replicate"] is False
    assert consensus["attempt_id"] not in body["default_selection"]


def test_unknown_root_is_a_404(client):
    assert client.get("/api/consistency/attempts?root=nope").status_code == 404


def test_a_root_without_a_json_record_is_a_400(client):
    client.index.records["bare"] = _Record(None)
    response = client.get("/api/consistency/attempts?root=bare")
    assert response.status_code == 400
    assert "No transcription JSON" in response.json()["detail"]


# ── Attempt text (§3.1) ───────────────────────────────────────────────────────


def test_attempt_text_can_be_inspected_before_selection(client):
    body = client.get(
        "/api/consistency/attempt?root=letter_042&attempt_id=r0:o0"
    ).json()
    assert body["text"] == TIGHT
    assert body["normalized"] == TIGHT
    assert body["word_count"] == len(TIGHT.split())


def test_unknown_attempt_text_is_a_404(client):
    response = client.get("/api/consistency/attempt?root=letter_042&attempt_id=r9:o9")
    assert response.status_code == 404


def test_attempt_text_rejects_an_unknown_profile(client):
    response = client.get(
        "/api/consistency/attempt?root=letter_042&attempt_id=r0:o0"
        "&normalization_profile=nope"
    )
    assert response.status_code == 400


# ── Analyze (§4a, §27) ────────────────────────────────────────────────────────


def _analyze(client, **overrides):
    body = {"root": "letter_042"}
    body.update(overrides)
    return client.post("/api/consistency/analyze", json=body)


def test_analyze_returns_the_full_record(client):
    body = _analyze(client).json()
    assert body["analysis_version"]
    assert body["source_document"]["root"] == "letter_042"
    assert body["source_document"]["image_filename"] == "letter_042.jpg"
    results = body["results"]
    assert results["n_attempts"] == 5
    assert results["n_pairs"] == 10
    assert len(results["matrix_cer_symmetric"]) == 5
    assert len(results["per_attempt"]) == 5
    assert results["outliers"]["applicable"] is True
    assert body["narrative"]


def test_analyze_defaults_to_the_healthy_replicates(client):
    body = _analyze(client).json()
    assert body["attempts_included"] == ["r0:o0", "r1:o0", "r2:o0", "r3:o0", "r4:o0"]


def test_analyze_honours_an_explicit_selection(client):
    body = _analyze(client, attempt_ids=["r0:o0", "r1:o0", "r2:o0"]).json()
    assert body["results"]["n_attempts"] == 3
    assert body["results"]["n_pairs"] == 3
    excluded = {e["attempt_id"] for e in body["attempts_excluded"]}
    assert excluded == {"r3:o0", "r4:o0"}


def test_identical_requests_return_byte_identical_responses(client):
    """§27 over the wire, not merely inside the library."""
    first = _analyze(client)
    second = _analyze(client)
    assert first.status_code == second.status_code == 200
    assert first.content == second.content


def test_attempt_id_order_does_not_affect_the_response(client):
    """D10 — the server imposes canonical order rather than trusting the client."""
    forward = _analyze(client, attempt_ids=["r0:o0", "r1:o0", "r2:o0"])
    shuffled = _analyze(client, attempt_ids=["r2:o0", "r0:o0", "r1:o0"])
    assert forward.content == shuffled.content


def test_analyze_never_writes_to_the_document(client):
    """§4a — analyze is pure; persistence is a separate call (D11)."""
    before_mtime = client.json_path.stat().st_mtime_ns
    before_bytes = client.json_path.read_bytes()
    _analyze(client)
    assert client.json_path.stat().st_mtime_ns == before_mtime
    assert client.json_path.read_bytes() == before_bytes


def test_a_changed_document_is_not_served_from_cache(client):
    before = _analyze(client).json()["results"]["n_attempts"]
    client.json_path.write_text(json.dumps(_document(FIVE[:3])), encoding="utf-8")
    after = _analyze(client).json()["results"]["n_attempts"]
    assert before == 5
    assert after == 3


def test_fewer_than_two_selected_attempts_is_a_400(client):
    response = _analyze(client, attempt_ids=["r0:o0"])
    assert response.status_code == 400
    assert "at least 2" in response.json()["detail"].lower()


def test_unknown_attempt_ids_are_a_400(client):
    response = _analyze(client, attempt_ids=["r0:o0", "r9:o9"])
    assert response.status_code == 400
    assert "r9:o9" in response.json()["detail"]


def test_an_unknown_normalization_profile_is_a_400(client):
    assert _analyze(client, normalization_profile="nope").status_code == 400


def test_an_unknown_tokenizer_is_a_400(client):
    assert _analyze(client, tokenizer="nope").status_code == 400


def test_analyze_on_an_unknown_root_is_a_404(client):
    response = client.post("/api/consistency/analyze", json={"root": "nope"})
    assert response.status_code == 404


def test_the_normalization_profile_changes_the_result(client):
    standard = _analyze(client, normalization_profile="standard_historical").json()
    diplomatic = _analyze(client, normalization_profile="diplomatic").json()
    assert standard["settings"]["normalization"]["id"] == "standard_historical"
    assert diplomatic["settings"]["normalization"]["id"] == "diplomatic"


def test_text_overrides_allow_an_unsaved_edit_to_be_analyzed(client):
    body = _analyze(client, text_overrides={"r4:o0": TIGHT}).json()
    edited = next(
        m for m in body["attempt_metadata"] if m["attempt_id"] == "r4:o0"
    )
    assert edited["edited_in_session"] is True
    # With the divergent attempt replaced by an agreeing one, nothing stands out.
    assert body["results"]["outliers"]["flagged_ids"] == []


def test_consensus_is_computed_by_default(client):
    results = _analyze(client).json()["results"]
    assert results["consensus"]["method"] == "deterministic_vote_v1"
    assert results["medoid_attempt_id"] in {"r0:o0", "r1:o0", "r2:o0", "r3:o0"}
    assert len(results["consensus_comparison"]) == 5


def test_consensus_can_be_skipped(client):
    results = _analyze(client, with_consensus=False).json()["results"]
    assert results["consensus"] is None
    assert results["medoid_attempt_id"] is None


def test_the_divergent_attempt_is_flagged_as_an_outlier(client):
    results = _analyze(client).json()["results"]
    assert results["outliers"]["flagged_ids"] == ["r4:o0"]
    verdict = next(
        v for v in results["outliers"]["verdicts"] if v["attempt_id"] == "r4:o0"
    )
    assert "disagreement with the remaining transcription attempts" in verdict["message"]


def test_the_response_carries_the_provenance_needed_to_reproduce_it(client):
    settings = _analyze(client).json()["settings"]
    assert settings["normalization"]["steps"]
    assert settings["tokenizer"]["id"] == "word_simple"
    assert settings["uncertainty_method"] == "jackknife_over_attempts"
    assert settings["cer_definition"] and settings["wer_definition"]
    assert settings["backend"]


def test_the_response_is_json_serializable_without_nan(client):
    """NaN is not valid JSON; undefined directional cells must serialize as null."""
    raw = _analyze(client).text
    assert "NaN" not in raw
    json.loads(raw)


# ── Diff (§18) ────────────────────────────────────────────────────────────────


def test_diff_between_two_attempts(client):
    body = client.post(
        "/api/consistency/diff",
        json={"root": "letter_042", "a_id": "r0:o0", "b_id": "r1:o0"},
    ).json()
    assert body["a_id"] == "r0:o0"
    assert body["b_id"] == "r1:o0"
    assert body["summary"]
    assert any(seg["tag"] != "equal" for seg in body["segments"])


def test_diff_reports_change_categories(client):
    body = client.post(
        "/api/consistency/diff",
        json={"root": "letter_042", "a_id": "r0:o0", "b_id": "r2:o0"},
    ).json()
    assert body["category_counts"]
    assert body["category_labels"]


def test_diff_keeps_both_original_texts(client):
    body = client.post(
        "/api/consistency/diff",
        json={"root": "letter_042", "a_id": "r0:o0", "b_id": "r4:o0"},
    ).json()
    assert body["a_original"] == TIGHT
    assert body["b_original"] == DIVERGENT


def test_diff_flags_substantial_divergence(client):
    body = client.post(
        "/api/consistency/diff",
        json={"root": "letter_042", "a_id": "r0:o0", "b_id": "r4:o0"},
    ).json()
    assert body["major_divergence"] is True


def test_an_attempt_can_be_diffed_against_a_consensus(client):
    consensus_text = _analyze(client).json()["results"]["consensus"]["text"]
    body = client.post(
        "/api/consistency/diff",
        json={
            "root": "letter_042",
            "a_id": "__consensus__",
            "b_id": "r4:o0",
            "texts": {"__consensus__": consensus_text},
        },
    ).json()
    assert body["a_id"] == "__consensus__"
    assert body["a_original"] == consensus_text


def test_diff_with_an_unknown_id_is_a_404(client):
    response = client.post(
        "/api/consistency/diff",
        json={"root": "letter_042", "a_id": "r0:o0", "b_id": "__consensus__"},
    )
    assert response.status_code == 404
    assert "texts" in response.json()["detail"]


def test_diff_of_identical_attempts_reports_no_changes(client):
    client.json_path.write_text(json.dumps(_document([TIGHT, TIGHT])), encoding="utf-8")
    body = client.post(
        "/api/consistency/diff",
        json={"root": "letter_042", "a_id": "r0:o0", "b_id": "r1:o0"},
    ).json()
    assert body["changed_token_count"] == 0
    assert "identical" in body["summary"]


# ── Mounting ──────────────────────────────────────────────────────────────────


def test_the_router_is_mounted_on_the_real_app(backend_env):
    """The endpoints must actually be reachable in backend/main.py.

    Loaded by explicit path rather than ``import main`` so this test binds to
    the file under test regardless of what else is on ``sys.path``, and so the
    app is constructed fresh instead of reusing a cached module.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "backend_main_for_test", _BACKEND / "main.py"
    )
    backend_main = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(backend_main)
    except ModuleNotFoundError as exc:  # pragma: no cover - environment dependent
        pytest.skip(
            f"backend/main.py needs the full declared dependency set; "
            f"'{exc.name}' is not installed in this environment."
        )
    except RuntimeError as exc:  # pragma: no cover - environment dependent
        # Some optional extras are reported by their consumer rather than by the
        # import system. FastAPI, for example, raises RuntimeError (not
        # ModuleNotFoundError) when python-multipart is absent and a route
        # declares File()/Form(). Treat only that shape as a skip.
        if "to be installed" not in str(exc):
            raise
        pytest.skip(
            f"backend/main.py needs the full declared dependency set: {exc}"
        )

    # Included routers are wrapped by Starlette, so enumerate the OpenAPI paths
    # rather than app.routes — that is the published contract in any case.
    paths = set(backend_main.app.openapi()["paths"])
    for path in (
        "/api/consistency/options",
        "/api/consistency/attempts",
        "/api/consistency/attempt",
        "/api/consistency/analyze",
        "/api/consistency/diff",
    ):
        assert path in paths, f"{path} is not mounted in backend/main.py"


# ── Persistence (D11, §25) ────────────────────────────────────────────────────


def test_save_writes_an_analysis_to_the_document(client):
    body = client.post(
        "/api/consistency/save",
        json={"root": "letter_042", "user_note": "first pass"},
    ).json()
    assert body["success"] is True
    assert body["analysis_id"]
    assert body["saved_at"]

    stored = json.loads(client.json_path.read_text(encoding="utf-8"))
    assert len(stored["analyses"]) == 1
    assert stored["analyses"][0]["user_note"] == "first pass"


def test_saving_is_additive_and_never_replaces(client):
    client.post("/api/consistency/save", json={"root": "letter_042"})
    client.post(
        "/api/consistency/save",
        json={"root": "letter_042", "attempt_ids": ["r0:o0", "r1:o0", "r2:o0"]},
    )
    stored = json.loads(client.json_path.read_text(encoding="utf-8"))
    assert len(stored["analyses"]) == 2
    assert stored["analyses"][0]["results"]["n_attempts"] == 5
    assert stored["analyses"][1]["results"]["n_attempts"] == 3


def test_each_saved_analysis_gets_its_own_id(client):
    """The provisional id from a cached analyze response is not reused."""
    first = client.post("/api/consistency/save", json={"root": "letter_042"}).json()
    second = client.post("/api/consistency/save", json={"root": "letter_042"}).json()
    assert first["analysis_id"] != second["analysis_id"]


def test_a_saved_analysis_round_trips_with_identical_values(client):
    """Exit criterion: save then reload gives identical numbers."""
    computed = _analyze(client).json()
    saved_id = client.post(
        "/api/consistency/save", json={"root": "letter_042"}
    ).json()["analysis_id"]

    reloaded = client.get(
        f"/api/consistency/saved/{saved_id}", params={"root": "letter_042"}
    ).json()

    assert reloaded["results"] == computed["results"]
    assert reloaded["settings"] == computed["settings"]
    assert reloaded["attempts_included"] == computed["attempts_included"]
    assert reloaded["narrative"] == computed["narrative"]


def test_saved_list_summarizes_each_record(client):
    client.post(
        "/api/consistency/save", json={"root": "letter_042", "user_note": "note"}
    )
    body = client.get("/api/consistency/saved", params={"root": "letter_042"}).json()
    assert body["root"] == "letter_042"
    assert len(body["analyses"]) == 1

    row = body["analyses"][0]
    assert row["n_attempts"] == 5
    assert row["n_pairs"] == 10
    assert row["median_cer"] is not None
    assert row["user_note"] == "note"
    assert row["normalization_profile"] == "standard_historical"


def test_saved_list_is_empty_before_anything_is_saved(client):
    body = client.get("/api/consistency/saved", params={"root": "letter_042"}).json()
    assert body["analyses"] == []


def test_a_saved_analysis_can_be_deleted(client):
    analysis_id = client.post(
        "/api/consistency/save", json={"root": "letter_042"}
    ).json()["analysis_id"]

    deleted = client.delete(
        f"/api/consistency/saved/{analysis_id}", params={"root": "letter_042"}
    )
    assert deleted.status_code == 200

    stored = json.loads(client.json_path.read_text(encoding="utf-8"))
    assert stored["analyses"] == []


def test_deleting_an_unknown_analysis_is_a_404(client):
    response = client.delete(
        "/api/consistency/saved/does-not-exist", params={"root": "letter_042"}
    )
    assert response.status_code == 404


def test_fetching_an_unknown_saved_analysis_is_a_404(client):
    response = client.get(
        "/api/consistency/saved/does-not-exist", params={"root": "letter_042"}
    )
    assert response.status_code == 404


def test_saving_leaves_the_transcription_runs_untouched(client):
    before = json.loads(client.json_path.read_text(encoding="utf-8"))["runs"]
    client.post("/api/consistency/save", json={"root": "letter_042"})
    after = json.loads(client.json_path.read_text(encoding="utf-8"))["runs"]
    assert before == after


def test_a_document_without_an_analyses_array_still_saves(client):
    """Existing documents predate the array; it is created on first write."""
    document = _document(FIVE)
    document.pop("analyses", None)
    assert "analyses" not in document
    client.json_path.write_text(json.dumps(document), encoding="utf-8")

    saved = client.post("/api/consistency/save", json={"root": "letter_042"}).json()
    assert saved["success"] is True

    stored = json.loads(client.json_path.read_text(encoding="utf-8"))
    assert len(stored["analyses"]) == 1
    assert stored["schema_version"] == "2.0"


# ── Export (§26) ──────────────────────────────────────────────────────────────


def _export(client, section="all"):
    return client.post(
        "/api/consistency/export", json={"root": "letter_042", "section": section}
    )


def test_export_returns_a_zip_with_a_filename(client):
    response = _export(client)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "letter_042_consistency_" in response.headers["content-disposition"]


def test_the_bundle_contains_every_artifact_the_spec_requires(client):
    archive = zipfile.ZipFile(io.BytesIO(_export(client).content))
    names = {n.split("/", 1)[1] for n in archive.namelist() if "/" in n}

    for expected in (
        "analysis.json",
        "README.txt",
        "summary.md",
        "numerical/matrix_cer_symmetric.csv",
        "numerical/matrix_cer_directional.csv",
        "numerical/matrix_wer_symmetric.csv",
        "numerical/matrix_wer_directional.csv",
        "numerical/per_attempt_summary.csv",
        "numerical/overall_summary.csv",
        "numerical/consensus_comparison.csv",
        "numerical/outlier_diagnostics.csv",
        "numerical/pairwise_edit_counts.csv",
        "text/consensus_deterministic.txt",
        "text/representative_attempt.txt",
        "figures/heatmap_cer.png",
        "figures/heatmap_cer.svg",
        "figures/heatmap_wer.png",
        "figures/heatmap_wer.svg",
    ):
        assert expected in names, f"{expected} missing from the export bundle"


def test_the_bundle_includes_the_measured_and_original_texts(client):
    archive = zipfile.ZipFile(io.BytesIO(_export(client).content))
    names = [n for n in archive.namelist() if "/text/" in n]
    assert any("originals/attempt_r0_o0.txt" in n for n in names)
    assert any("normalized/attempt_r0_o0.txt" in n for n in names)


def test_the_exported_record_matches_the_analyze_response(client):
    computed = _analyze(client).json()
    archive = zipfile.ZipFile(io.BytesIO(_export(client).content))
    name = next(n for n in archive.namelist() if n.endswith("analysis.json"))
    assert json.loads(archive.read(name))["results"] == computed["results"]


def test_the_matrix_csv_is_labelled_and_square(client):
    archive = zipfile.ZipFile(io.BytesIO(_export(client).content))
    name = next(n for n in archive.namelist() if n.endswith("matrix_cer_symmetric.csv"))
    rows = list(csv.reader(io.StringIO(archive.read(name).decode("utf-8"))))
    assert rows[0][0] == "attempt"
    assert len(rows) == 6
    assert len(rows[1]) == 6


def test_the_readme_states_that_this_is_not_accuracy(client):
    archive = zipfile.ZipFile(io.BytesIO(_export(client).content))
    name = next(n for n in archive.namelist() if n.endswith("README.txt"))
    readme = archive.read(name).decode("utf-8")
    assert "do NOT measure accuracy" in readme
    assert "verified" in readme


def test_the_figures_are_real_images(client):
    archive = zipfile.ZipFile(io.BytesIO(_export(client).content))
    png = archive.read(
        next(n for n in archive.namelist() if n.endswith("heatmap_cer.png"))
    )
    svg = archive.read(
        next(n for n in archive.namelist() if n.endswith("heatmap_cer.svg"))
    )
    assert png.startswith(b"\x89PNG\r\n")
    assert b"<svg" in svg[:400]


def test_export_works_without_the_analysis_having_been_saved(client):
    """A user may only want the CSVs."""
    stored = json.loads(client.json_path.read_text(encoding="utf-8"))
    assert stored.get("analyses", []) == []
    assert _export(client).status_code == 200


@pytest.mark.parametrize("section", ["numerical", "text", "figures"])
def test_individual_sections_can_be_exported(client, section):
    response = _export(client, section)
    assert response.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(response.content)).namelist()
    assert names
    assert all(f"/{section}/" in n for n in names)


def test_the_record_can_be_exported_on_its_own_as_json(client):
    response = _export(client, "json")
    assert response.headers["content-type"] == "application/json"
    assert json.loads(response.content)["results"]["n_pairs"] == 10


def test_an_unknown_export_section_is_a_400(client):
    assert _export(client, "bogus").status_code == 400
