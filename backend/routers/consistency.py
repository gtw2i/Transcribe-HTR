"""Multi-transcription consistency and consensus analysis endpoints.

Spec §4a. Everything here is deterministic and read-only: ``/analyze`` computes,
it never writes. Persisting a result is a separate call (D11), and the LLM
consensus is a separate endpoint again (D7), so a client that never calls it is
guaranteed to have used no generative model.

All computation lives in ``analysis/``, which has no FastAPI imports; this
module is the transport layer and nothing more.
"""

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from analysis import (
    ANALYSIS_VERSION,
    BACKEND,
    DEFAULT_PROFILE,
    DEFAULT_TOKENIZER,
    build_report,
    collect_attempts,
    default_selection,
    diff_prepared,
    list_profiles,
    list_tokenizers,
    metric_definitions,
    prepare,
)
from analysis.export import build_bundle
from analysis.normalize import UnknownProfileError, UnknownTokenizerError
from core.json_manager import (
    delete_analysis,
    list_analyses,
    load_v2_json,
    save_analysis,
)
from dependencies import get_file_index, get_workspace
from schemas.consistency import (
    AnalyzeRequest,
    AttemptListResponse,
    AttemptTextResponse,
    DiffRequest,
    ExportRequest,
    OptionsResponse,
    SavedAnalysisListResponse,
    SaveRequest,
    SaveResponse,
)

router = APIRouter(tags=["consistency"])

#: How many distinct analyses to memoize. The payload is small and the cost is
#: dominated by the pairwise alignments, so a shallow cache pays for itself
#: whenever the client re-selects a previous combination (D8).
_CACHE_SIZE = 32


# ── Loading ───────────────────────────────────────────────────────────────────


def _load_json(root: str, file_index) -> Dict[str, Any]:
    """Load a document's v2 JSON, or raise the usual 404/400."""
    if root not in file_index.records:
        raise HTTPException(status_code=404, detail=f"Root '{root}' not found.")
    record = file_index.records[root]
    if not record.has_json():
        raise HTTPException(
            status_code=400, detail=f"No transcription JSON for root '{root}'."
        )
    data = load_v2_json(Path(record.json_path))
    if data is None:
        raise HTTPException(status_code=500, detail="Failed to load transcription JSON.")
    return data


def _json_fingerprint(root: str, file_index) -> int:
    """Modification time of the document record, for cache invalidation."""
    record = file_index.records.get(root)
    if not record or not record.json_path:
        return 0
    try:
        return Path(record.json_path).stat().st_mtime_ns
    except OSError:
        return 0


# ── Cached analysis (D8) ──────────────────────────────────────────────────────


@lru_cache(maxsize=_CACHE_SIZE)
def _analyze_cached(
    root: str,
    fingerprint: int,
    attempt_ids: Tuple[str, ...],
    overrides: Tuple[Tuple[str, str], ...],
    profile: str,
    tokenizer: str,
    with_consensus: bool,
    payload: str,
) -> Dict[str, Any]:
    """Compute one analysis. Pure, so caching is a cost question only.

    *payload* carries the serialized document so the cached function stays a
    function of its arguments alone; *fingerprint* makes the key change when the
    document does.

    The ``analysis_id`` and ``created_at`` are produced here, which means two
    identical requests receive an identical response — including the id. That is
    the intended reading of an idempotent computation; the id becomes durable
    only when the analysis is explicitly saved.
    """
    import json

    json_data = json.loads(payload)
    attempts = collect_attempts(json_data, text_overrides=dict(overrides))
    selection = list(attempt_ids) or default_selection(attempts)

    report = build_report(
        attempts,
        selection,
        root=root,
        image_filename=json_data.get("metadata", {}).get("image_filename"),
        normalization_profile=profile,
        tokenizer=tokenizer,
        with_consensus=with_consensus,
    )
    return report.as_dict()


def clear_analysis_cache() -> None:
    """Drop the memoized analyses. Used by tests and after a document changes."""
    _analyze_cached.cache_clear()


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/consistency/options", response_model=OptionsResponse)
def get_options():
    """Comparison settings the client can offer the user (§4.2, §4.3, §6).

    Includes each profile's exact step list, so the UI can show what a profile
    does rather than just naming it.
    """
    return {
        "normalization_profiles": list_profiles(),
        "default_normalization_profile": DEFAULT_PROFILE,
        "tokenizers": list_tokenizers(),
        "default_tokenizer": DEFAULT_TOKENIZER,
        "analysis_version": ANALYSIS_VERSION,
        "backend": BACKEND,
        "definitions": metric_definitions(),
    }


@router.get("/consistency/attempts", response_model=AttemptListResponse)
def list_attempts(root: str = Query(...), file_index=Depends(get_file_index)):
    """Every transcription attempt associated with a document (§3.1).

    Degenerate and consensus records are included so the user can see what data
    exists; ``default_selection`` says which are checked to begin with (§3.2).
    """
    attempts = collect_attempts(_load_json(root, file_index))
    return {
        "root": root,
        "attempts": [a.as_dict() for a in attempts],
        "default_selection": default_selection(attempts),
        "n_replicates": sum(1 for a in attempts if a.is_replicate),
        "n_available": len(attempts),
    }


@router.get("/consistency/attempt", response_model=AttemptTextResponse)
def get_attempt(
    root: str = Query(...),
    attempt_id: str = Query(...),
    normalization_profile: str = Query(DEFAULT_PROFILE),
    tokenizer: str = Query(DEFAULT_TOKENIZER),
    file_index=Depends(get_file_index),
):
    """One attempt's full text, so it can be inspected before being included (§3.1)."""
    attempts = collect_attempts(_load_json(root, file_index))
    match = next((a for a in attempts if a.attempt_id == attempt_id), None)
    if match is None:
        raise HTTPException(
            status_code=404, detail=f"Attempt '{attempt_id}' not found for root '{root}'."
        )
    try:
        prepared = prepare(match.attempt_id, match.text, normalization_profile, tokenizer)
    except (UnknownProfileError, UnknownTokenizerError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "attempt_id": match.attempt_id,
        "label": match.label,
        "text": match.text,
        "normalized": prepared.normalized,
        "char_count": prepared.n_chars,
        "word_count": prepared.n_words,
    }


@router.post("/consistency/analyze")
def analyze(req: AnalyzeRequest, file_index=Depends(get_file_index)):
    """Run the deterministic consistency analysis (§4a).

    Pure: no document is written. Repeating the request returns the identical
    response (§27).
    """
    import json

    json_data = _load_json(req.root, file_index)

    known = {a.attempt_id for a in collect_attempts(json_data)}
    unknown = [a for a in req.attempt_ids if a not in known]
    if unknown:
        raise HTTPException(
            status_code=400, detail=f"Unknown attempt id(s): {sorted(unknown)}"
        )

    try:
        return _analyze_cached(
            req.root,
            _json_fingerprint(req.root, file_index),
            tuple(sorted(req.attempt_ids)),
            tuple(sorted(req.text_overrides.items())),
            req.normalization_profile,
            req.tokenizer,
            req.with_consensus,
            json.dumps(json_data, sort_keys=True),
        )
    except (UnknownProfileError, UnknownTokenizerError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        # Raised as InsufficientAttemptsError when fewer than two are selected.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/consistency/diff")
def diff(req: DiffRequest, file_index=Depends(get_file_index)):
    """Inspect the differences between two transcriptions (§18).

    Either side may be a pseudo-id whose text is supplied in ``texts`` — that is
    how an attempt is compared against a consensus.
    """
    attempts = collect_attempts(
        _load_json(req.root, file_index), text_overrides=req.text_overrides
    )
    by_id = {a.attempt_id: a for a in attempts}

    def _resolve(attempt_id: str):
        if attempt_id in req.texts:
            return attempt_id, req.texts[attempt_id]
        if attempt_id in by_id:
            return attempt_id, by_id[attempt_id].text
        raise HTTPException(
            status_code=404,
            detail=(
                f"Attempt '{attempt_id}' not found for root '{req.root}'. Supply its "
                f"text in 'texts' if it is a consensus."
            ),
        )

    a_id, a_text = _resolve(req.a_id)
    b_id, b_text = _resolve(req.b_id)

    try:
        left = prepare(a_id, a_text, req.normalization_profile, req.tokenizer)
        right = prepare(b_id, b_text, req.normalization_profile, req.tokenizer)
    except (UnknownProfileError, UnknownTokenizerError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return diff_prepared(left, right).as_dict()


# ── Persistence (D11) ─────────────────────────────────────────────────────────


def _compute(req, file_index) -> Dict[str, Any]:
    """Run (or fetch from cache) the analysis described by *req*."""
    import json

    json_data = _load_json(req.root, file_index)
    try:
        return _analyze_cached(
            req.root,
            _json_fingerprint(req.root, file_index),
            tuple(sorted(req.attempt_ids)),
            tuple(sorted(req.text_overrides.items())),
            req.normalization_profile,
            req.tokenizer,
            req.with_consensus,
            json.dumps(json_data, sort_keys=True),
        )
    except (UnknownProfileError, UnknownTokenizerError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _summarize_saved(record: Dict[str, Any]) -> Dict[str, Any]:
    """Compact row for the saved-analyses list."""
    results = record.get("results", {})
    settings = record.get("settings", {})
    return {
        "analysis_id": record.get("analysis_id", ""),
        "saved_at": record.get("saved_at"),
        "created_at": record.get("created_at"),
        "user_note": record.get("user_note", "") or "",
        "n_attempts": results.get("n_attempts", 0),
        "n_pairs": results.get("n_pairs", 0),
        "median_cer": (results.get("cer") or {}).get("median"),
        "median_wer": (results.get("wer") or {}).get("median"),
        "attempts_included": record.get("attempts_included", []),
        "attempts_excluded": record.get("attempts_excluded", []),
        "normalization_profile": (settings.get("normalization") or {}).get("id"),
        "tokenizer": (settings.get("tokenizer") or {}).get("id"),
    }


@router.post("/consistency/save", response_model=SaveResponse)
def save(
    req: SaveRequest,
    workspace=Depends(get_workspace),
    file_index=Depends(get_file_index),
):
    """Persist an analysis to the document record (D11).

    Saving is explicit and additive: it never overwrites an earlier analysis,
    and a fresh ``analysis_id`` is minted here rather than reusing the
    provisional one from the cached analyze response.
    """
    report = _compute(req, file_index)
    record = save_analysis(workspace, file_index, req.root, report, user_note=req.user_note)
    if record is None:
        return SaveResponse(success=False, error="Could not write the analysis to the document.")
    return SaveResponse(
        success=True,
        analysis_id=record["analysis_id"],
        saved_at=record.get("saved_at"),
    )


@router.get("/consistency/saved", response_model=SavedAnalysisListResponse)
def list_saved(root: str = Query(...), file_index=Depends(get_file_index)):
    """Previously saved analyses for a document, oldest first."""
    if root not in file_index.records:
        raise HTTPException(status_code=404, detail=f"Root '{root}' not found.")
    return {
        "root": root,
        "analyses": [_summarize_saved(r) for r in list_analyses(file_index, root)],
    }


@router.get("/consistency/saved/{analysis_id}")
def get_saved(
    analysis_id: str,
    root: str = Query(...),
    file_index=Depends(get_file_index),
):
    """One saved analysis in full, for reloading into the view (§21)."""
    from core.json_manager import get_analysis

    record = get_analysis(file_index, root, analysis_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"Analysis '{analysis_id}' not found for root '{root}'."
        )
    return record


@router.delete("/consistency/saved/{analysis_id}", response_model=SaveResponse)
def remove_saved(
    analysis_id: str,
    root: str = Query(...),
    file_index=Depends(get_file_index),
):
    """Delete a saved analysis."""
    if not delete_analysis(file_index, root, analysis_id):
        raise HTTPException(
            status_code=404, detail=f"Analysis '{analysis_id}' not found for root '{root}'."
        )
    return SaveResponse(success=True, analysis_id=analysis_id)


# ── Export (§26) ──────────────────────────────────────────────────────────────


@router.post("/consistency/export")
def export(req: ExportRequest, file_index=Depends(get_file_index)):
    """Download the analysis bundle (§26).

    Works on the current analysis and does **not** require it to have been
    saved first — a user may only want the CSVs.
    """
    report = _compute(req, file_index)
    json_data = _load_json(req.root, file_index)

    attempts = collect_attempts(json_data, text_overrides=req.text_overrides)
    by_id = {a.attempt_id: a for a in attempts}
    labels = {a.attempt_id: a.label for a in attempts}

    prepared = [
        prepare(
            attempt_id,
            by_id[attempt_id].text,
            req.normalization_profile,
            req.tokenizer,
        )
        for attempt_id in report["attempts_included"]
        if attempt_id in by_id
    ]

    try:
        data, filename, mime = build_bundle(report, prepared, labels, section=req.section)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
