"""Consistency analysis request / response models.

The analyze and diff responses are the ``as_dict()`` forms of the dataclasses in
``analysis/`` — deeply nested and already the canonical §5.3 record — so they
are returned as plain dicts rather than mirrored into Pydantic models that
would have to be kept in step by hand. The request models are where validation
actually matters, and they are complete.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Everything needed to reproduce an analysis (§25, §27).

    The request is the complete input: given the same body, the response is
    byte-identical.
    """

    root: str
    #: Attempts to include. Empty means "the default selection" — every healthy
    #: independent attempt (§3.2). Order is ignored; the server imposes the
    #: canonical order so two clients sending the same set agree (D10).
    attempt_ids: List[str] = Field(default_factory=list)
    normalization_profile: str = "standard_historical"
    tokenizer: str = "word_simple"
    #: Text not yet persisted, keyed by attempt id, so an in-flight edit can be
    #: analyzed without saving it first (D3).
    text_overrides: Dict[str, str] = Field(default_factory=dict)
    #: Also compute the medoid and deterministic consensus (§14, §15).
    with_consensus: bool = True


class SaveRequest(AnalyzeRequest):
    """Persist an analysis (D11).

    Carries the analyze parameters rather than a client-supplied report, so the
    stored record is always what the server computes — the recomputation is a
    cache hit, so it costs nothing.
    """

    user_note: str = ""


class ExportRequest(AnalyzeRequest):
    """Build an export bundle (§26). ``section`` selects part of it."""

    section: str = "all"


class SavedAnalysisSummary(BaseModel):
    """One row of the saved-analyses list."""

    analysis_id: str
    saved_at: Optional[str] = None
    created_at: Optional[str] = None
    user_note: str = ""
    n_attempts: int = 0
    n_pairs: int = 0
    median_cer: Optional[float] = None
    median_wer: Optional[float] = None
    attempts_included: List[str] = Field(default_factory=list)
    attempts_excluded: List[Dict[str, Any]] = Field(default_factory=list)
    normalization_profile: Optional[str] = None
    tokenizer: Optional[str] = None


class SavedAnalysisListResponse(BaseModel):
    root: str
    analyses: List[SavedAnalysisSummary]


class SaveResponse(BaseModel):
    success: bool
    analysis_id: Optional[str] = None
    saved_at: Optional[str] = None
    error: Optional[str] = None


class DiffRequest(BaseModel):
    """A two-way difference between attempts, or an attempt and a consensus (§18)."""

    root: str
    a_id: str
    b_id: str
    normalization_profile: str = "standard_historical"
    tokenizer: str = "word_simple"
    text_overrides: Dict[str, str] = Field(default_factory=dict)
    #: Text for ids that are not attempts of this document — supply
    #: ``{"__consensus__": "..."}`` to diff an attempt against a consensus.
    texts: Dict[str, str] = Field(default_factory=dict)


class AttemptSummary(BaseModel):
    """One row of the selection list (§3.1). The full text is fetched separately."""

    attempt_id: str
    label: str
    source_type: str
    is_replicate: bool
    run_index: Optional[int] = None
    output_index: Optional[int] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    profile_name: Optional[str] = None
    temperature: Optional[float] = None
    created_at: Optional[str] = None
    run_id: Optional[str] = None
    edited_in_session: bool = False
    char_count: int = 0
    health: Dict[str, Any] = Field(default_factory=dict)


class AttemptListResponse(BaseModel):
    """All attempts associated with a document, and which are checked by default."""

    root: str
    attempts: List[AttemptSummary]
    default_selection: List[str]
    n_replicates: int
    n_available: int


class AttemptTextResponse(BaseModel):
    """One attempt's full text, for inspection before including it (§3.1)."""

    attempt_id: str
    label: str
    text: str
    normalized: str
    char_count: int
    word_count: int


class NormalizationProfileInfo(BaseModel):
    id: str
    label: str
    description: str
    version: str
    steps: List[str]


class TokenizerInfo(BaseModel):
    id: str
    description: str


class OptionsResponse(BaseModel):
    """Comparison settings the client can offer (§4.2, §4.3, §6)."""

    normalization_profiles: List[NormalizationProfileInfo]
    default_normalization_profile: str
    tokenizers: List[TokenizerInfo]
    default_tokenizer: str
    analysis_version: str
    backend: str
    definitions: Dict[str, Any]
