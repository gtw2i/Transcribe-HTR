"""Multi-transcription consistency and consensus analysis.

Treats repeated transcription attempts as **replicate measurements** of an
uncertain process and quantifies how much they disagree (§33). Nothing computed
here establishes accuracy: in the absence of a verified reference transcription
every quantity is *disagreement*, *consistency* or *variability*, never *error
rate* or *accuracy* (§1, §28).

The package is pure Python — no FastAPI, no HTTP, no Streamlit, no session
state. Routers instantiate it, pass plain arguments and receive plain
dataclasses, which is what makes the reproducibility requirement (§27) testable
in isolation.

Phase 1 delivers text preparation (§4), the CER/WER metrics (§5, §6), the
pairwise matrices (§7), document-level summary statistics (§9), per-attempt
consistency scores (§11), and attempt collection with health screening
(§2, §3.1, §23, §24).

Phase 2 adds uncertainty estimation (§10), outlier identification (§12),
small-sample guidance (§22), and the assembled report with its provenance
record (§25) and research summary (§30). ``build_report`` is the entry point.

Note: the re-exported ``normalize()`` function shadows the ``normalize``
submodule of the same name, so ``from backend.analysis import normalize`` gives
the function. To reach the module use ``from backend.analysis.normalize import
...`` or ``importlib.import_module("backend.analysis.normalize")``.
"""

from .attempts import (
    REPLICATE_SOURCE_TYPES,
    SOURCE_AI,
    SOURCE_CONSENSUS,
    SOURCE_HUMAN,
    SOURCE_REFERENCE,
    AttemptHealth,
    TranscriptionAttempt,
    collect_attempts,
    default_selection,
    screen_health,
    selected_attempts,
)
from .consensus import (
    CONSENSUS_COMPARISON_CAVEAT,
    DETERMINISTIC_METHOD,
    LOW_SUPPORT_THRESHOLD,
    METHOD_DETERMINISTIC,
    METHOD_LLM,
    METHOD_MEDOID,
    ConsensusComparison,
    ConsensusResult,
    ConsensusToken,
    MedoidResult,
    compare_to_consensus,
    deterministic_consensus,
    median_consensus_wer,
    select_medoid,
)
from .diffing import (
    CATEGORY_LABELS,
    DiffResult,
    DiffSegment,
    diff_prepared,
    diff_tokens,
)
from .matrices import (
    AttemptStats,
    DisagreementSummary,
    HeatmapSpec,
    InsufficientAttemptsError,
    PairwiseMatrices,
    build_matrices,
    compute_pairs,
    heatmap_spec,
    matrix_to_json,
    mean_disagreement_vector,
    median_disagreement_vector,
    n_unique_pairs,
    per_attempt_stats,
    summarize,
    summarize_directional,
    summarize_pairs,
)
from .metrics import (
    BACKEND,
    CER_DEFINITION,
    SYMMETRIC_DEFINITION,
    WER_DEFINITION,
    EditCounts,
    PairMetrics,
    PreparedText,
    align_opcodes,
    compare,
    edit_counts,
    error_rate,
    metric_definitions,
    prepare,
    symmetric_rate,
)
from .normalize import (
    DEFAULT_PROFILE,
    DEFAULT_TOKENIZER,
    NORMALIZATION_PROFILES,
    NORMALIZATION_VERSION,
    TOKENIZERS,
    UnknownProfileError,
    UnknownTokenizerError,
    describe_profile,
    list_profiles,
    list_tokenizers,
    normalize,
    tokenize,
    tokenize_with_spans,
)
from .outliers import (
    ALTERNATIVE_EXPLANATIONS,
    DIAGNOSTIC_DISCLAIMER,
    MIN_ATTEMPTS_FOR_OUTLIERS,
    STATUS_NONE,
    STATUS_POSSIBLE,
    STATUS_STRONG,
    OutlierReport,
    OutlierVerdict,
    detect_outliers,
    robust_scores,
)
from .report import (
    ANALYSIS_VERSION,
    ConsistencyReport,
    SmallSampleGuidance,
    assess_sample_size,
    build_narrative,
    build_report,
    report_from_dict,
)
from .uncertainty import (
    JACKKNIFE_METHOD,
    MIN_ATTEMPTS_FOR_UNCERTAINTY,
    UncertaintyEstimate,
    VariabilityReport,
    describe_variability,
    jackknife_se,
    leave_one_out_means,
)

__all__ = [
    # normalize
    "DEFAULT_PROFILE",
    "DEFAULT_TOKENIZER",
    "NORMALIZATION_PROFILES",
    "NORMALIZATION_VERSION",
    "TOKENIZERS",
    "UnknownProfileError",
    "UnknownTokenizerError",
    "describe_profile",
    "list_profiles",
    "list_tokenizers",
    "normalize",
    "tokenize",
    "tokenize_with_spans",
    # metrics
    "BACKEND",
    "CER_DEFINITION",
    "WER_DEFINITION",
    "SYMMETRIC_DEFINITION",
    "EditCounts",
    "PairMetrics",
    "PreparedText",
    "align_opcodes",
    "compare",
    "edit_counts",
    "error_rate",
    "metric_definitions",
    "prepare",
    "symmetric_rate",
    # matrices
    "AttemptStats",
    "DisagreementSummary",
    "HeatmapSpec",
    "InsufficientAttemptsError",
    "PairwiseMatrices",
    "build_matrices",
    "compute_pairs",
    "heatmap_spec",
    "matrix_to_json",
    "mean_disagreement_vector",
    "median_disagreement_vector",
    "n_unique_pairs",
    "per_attempt_stats",
    "summarize",
    "summarize_directional",
    "summarize_pairs",
    # attempts
    "REPLICATE_SOURCE_TYPES",
    "SOURCE_AI",
    "SOURCE_CONSENSUS",
    "SOURCE_HUMAN",
    "SOURCE_REFERENCE",
    "AttemptHealth",
    "TranscriptionAttempt",
    "collect_attempts",
    "default_selection",
    "screen_health",
    "selected_attempts",
    # uncertainty
    "JACKKNIFE_METHOD",
    "MIN_ATTEMPTS_FOR_UNCERTAINTY",
    "UncertaintyEstimate",
    "VariabilityReport",
    "describe_variability",
    "jackknife_se",
    "leave_one_out_means",
    # outliers
    "ALTERNATIVE_EXPLANATIONS",
    "DIAGNOSTIC_DISCLAIMER",
    "MIN_ATTEMPTS_FOR_OUTLIERS",
    "STATUS_NONE",
    "STATUS_POSSIBLE",
    "STATUS_STRONG",
    "OutlierReport",
    "OutlierVerdict",
    "detect_outliers",
    "robust_scores",
    # report
    "ANALYSIS_VERSION",
    "ConsistencyReport",
    "SmallSampleGuidance",
    "assess_sample_size",
    "build_narrative",
    "build_report",
    "report_from_dict",
    # consensus
    "CONSENSUS_COMPARISON_CAVEAT",
    "DETERMINISTIC_METHOD",
    "LOW_SUPPORT_THRESHOLD",
    "METHOD_DETERMINISTIC",
    "METHOD_LLM",
    "METHOD_MEDOID",
    "ConsensusComparison",
    "ConsensusResult",
    "ConsensusToken",
    "MedoidResult",
    "compare_to_consensus",
    "deterministic_consensus",
    "median_consensus_wer",
    "select_medoid",
    # diffing
    "CATEGORY_LABELS",
    "DiffResult",
    "DiffSegment",
    "diff_prepared",
    "diff_tokens",
]
