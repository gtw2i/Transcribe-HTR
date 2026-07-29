"""Collecting transcription attempts from a document's v2 JSON record.

Spec §2 (analysis unit), §3.1 (identifying metadata), §23 (degenerate
transcriptions), §24 (duplicates).

``collect_attempts`` is pure: it takes the already-loaded v2 JSON dict and
returns plain dataclasses. It reads ``runs[]`` directly, so every attempt keeps
the model/provider/timestamp of the run that produced it — the flattening in
``routers/harmonization.py`` (which collapses all outputs into one anonymous
list and selects by integer index) is deliberately *not* reproduced here,
because §3.1 requires that metadata in the selection UI.

This module imports nothing from the rest of the backend.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .normalize import normalize

# ── Source types (§2.1) ───────────────────────────────────────────────────────
# A consensus or a verified reference is never automatically treated as an
# independent replicate. Only SOURCE_AI and SOURCE_HUMAN are eligible.

SOURCE_AI = "ai"
SOURCE_HUMAN = "human"
SOURCE_CONSENSUS = "consensus"
SOURCE_REFERENCE = "reference"

REPLICATE_SOURCE_TYPES = frozenset({SOURCE_AI, SOURCE_HUMAN})

# ── Health screening (§23) ────────────────────────────────────────────────────

HEALTH_OK = "ok"
HEALTH_EMPTY = "empty"
HEALTH_NEAR_EMPTY = "near_empty"
HEALTH_ERROR_TEXT = "error_text"
HEALTH_CORRUPT = "corrupt"
HEALTH_DUPLICATE_RECORD = "duplicate_record"

#: Statuses that make an attempt unsuitable for ordinary comparison. These are
#: unchecked by default in the UI and are *never* silently scored as ordinary
#: high-disagreement transcriptions (§23).
UNSUITABLE_STATUSES = frozenset(
    {HEALTH_EMPTY, HEALTH_ERROR_TEXT, HEALTH_CORRUPT, HEALTH_DUPLICATE_RECORD}
)

#: Health flags are computed against a fixed normalization, independent of the
#: profile chosen for the analysis, so that a flag does not appear or vanish
#: when the user changes comparison settings.
SCREENING_PROFILE = "standard_historical"

#: Absolute floor, in characters, below which an output cannot be a page of
#: handwriting.
NEAR_EMPTY_ABSOLUTE = 20

#: An output shorter than this fraction of the group's median length is treated
#: as near-empty even if it clears the absolute floor.
NEAR_EMPTY_RELATIVE = 0.05

_REFUSAL_RE = re.compile(
    r"^\s*("
    r"sorry\b"
    r"|i'?m sorry\b"
    r"|i am sorry\b"
    r"|i apolog"
    r"|i can'?t\b"
    r"|i cannot\b"
    r"|i can not\b"
    r"|i'?m unable\b"
    r"|i am unable\b"
    r"|i'?m not able\b"
    r"|i am not able\b"
    r"|unable to\b"
    r"|as an ai\b"
    r"|error[:\s]"
    r"|failed to\b"
    r"|no text\b"
    r")",
    re.IGNORECASE,
)

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)

REPLACEMENT_CHAR_THRESHOLD = 0.05
CONTROL_CHAR_THRESHOLD = 0.30
FENCE_DOMINANCE_THRESHOLD = 0.90


@dataclass(frozen=True)
class AttemptHealth:
    """Screening verdict for one attempt (§23, §24)."""

    status: str
    reasons: Tuple[str, ...] = ()
    char_count: int = 0
    identical_to: Tuple[str, ...] = ()

    @property
    def is_suitable(self) -> bool:
        return self.status not in UNSUITABLE_STATUSES

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "reasons": list(self.reasons),
            "char_count": self.char_count,
            "identical_to": list(self.identical_to),
            "is_suitable": self.is_suitable,
        }


def _control_char_ratio(text: str) -> float:
    if not text:
        return 0.0
    controls = sum(
        1
        for ch in text
        if unicodedata.category(ch) == "Cc" and ch not in ("\t", "\n", "\r")
    )
    return controls / len(text)


def _replacement_char_ratio(text: str) -> float:
    if not text:
        return 0.0
    return text.count("�") / len(text)


def _fenced_fraction(text: str) -> float:
    stripped = text.strip()
    if not stripped or "```" not in stripped:
        return 0.0
    fenced = sum(len(m.group(0)) for m in _FENCE_RE.finditer(stripped))
    return fenced / len(stripped)


def screen_health(text: str, median_length: Optional[float] = None) -> AttemptHealth:
    """Classify one attempt's text (§23).

    *median_length* is the group's median screened length; when supplied, the
    relative near-empty rule applies in addition to the absolute floor.
    """
    screened = normalize(text or "", SCREENING_PROFILE)
    char_count = len(screened)
    reasons: List[str] = []

    if not screened:
        return AttemptHealth(HEALTH_EMPTY, ("output is empty",), 0)

    replacement_ratio = _replacement_char_ratio(screened)
    control_ratio = _control_char_ratio(screened)
    if replacement_ratio > REPLACEMENT_CHAR_THRESHOLD:
        reasons.append(
            f"{replacement_ratio:.0%} of characters are Unicode replacement characters"
        )
    if control_ratio > CONTROL_CHAR_THRESHOLD:
        reasons.append(f"{control_ratio:.0%} of characters are control characters")
    if reasons:
        return AttemptHealth(HEALTH_CORRUPT, tuple(reasons), char_count)

    if _REFUSAL_RE.match(screened):
        return AttemptHealth(
            HEALTH_ERROR_TEXT,
            ("output begins like a refusal or error message",),
            char_count,
        )
    if _fenced_fraction(screened) >= FENCE_DOMINANCE_THRESHOLD:
        return AttemptHealth(
            HEALTH_ERROR_TEXT,
            ("output is almost entirely a fenced code block",),
            char_count,
        )

    if char_count < NEAR_EMPTY_ABSOLUTE:
        reasons.append(f"only {char_count} characters")
    elif median_length and char_count < NEAR_EMPTY_RELATIVE * median_length:
        reasons.append(
            f"{char_count} characters, under {NEAR_EMPTY_RELATIVE:.0%} of the "
            f"group median ({median_length:.0f})"
        )
    if reasons:
        return AttemptHealth(HEALTH_NEAR_EMPTY, tuple(reasons), char_count)

    return AttemptHealth(HEALTH_OK, (), char_count)


# ── Attempts (§2, §3.1) ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class TranscriptionAttempt:
    """One transcription attempt with the provenance needed to identify it."""

    attempt_id: str
    label: str
    text: str
    source_type: str = SOURCE_AI
    run_index: Optional[int] = None
    output_index: Optional[int] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    profile_name: Optional[str] = None
    temperature: Optional[float] = None
    created_at: Optional[str] = None
    run_id: Optional[str] = None
    edited_in_session: bool = False
    health: AttemptHealth = field(
        default_factory=lambda: AttemptHealth(HEALTH_OK, (), 0)
    )

    @property
    def is_replicate(self) -> bool:
        """Whether this counts as an independent attempt (§2.1)."""
        return self.source_type in REPLICATE_SOURCE_TYPES

    def as_dict(self) -> dict:
        """Selection-list payload (§3.1). Text is sent separately, on demand."""
        return {
            "attempt_id": self.attempt_id,
            "label": self.label,
            "source_type": self.source_type,
            "is_replicate": self.is_replicate,
            "run_index": self.run_index,
            "output_index": self.output_index,
            "model": self.model,
            "provider": self.provider,
            "profile_name": self.profile_name,
            "temperature": self.temperature,
            "created_at": self.created_at,
            "run_id": self.run_id,
            "edited_in_session": self.edited_in_session,
            "char_count": self.health.char_count,
            "health": self.health.as_dict(),
        }


def _output_text(output: Any) -> str:
    """Coerce one stored output to text.

    ``save_transcription_run`` writes plain strings, but the harmonization
    router already defends against dicts carrying a ``text`` key, so both
    shapes are accepted here too.
    """
    if isinstance(output, dict):
        return str(output.get("text", "") or "")
    if output is None:
        return ""
    return output if isinstance(output, str) else str(output)


def _run_fingerprint(run: Dict[str, Any]) -> Tuple:
    """Identity of a *record*, for duplicate-record detection (§24).

    ``run_id`` is used when present. It usually is not: the backend's
    ``save_transcription_run`` does not write one, so the fallback fingerprint —
    timestamp, model, provider and the outputs themselves — is the normal path.

    This detects the same record stored twice. It deliberately does **not**
    detect two separate runs that happened to produce identical text: those are
    distinct experimental attempts and are meaningful evidence of
    reproducibility (§24).
    """
    run_id = run.get("run_id")
    if run_id:
        return ("run_id", run_id)
    return (
        "fingerprint",
        run.get("timestamp"),
        run.get("started_at"),
        run.get("model"),
        run.get("provider"),
        tuple(_output_text(o) for o in run.get("outputs", []) or []),
    )


def _label_for(run_number: int, output_number: int, outputs_in_run: int) -> str:
    if outputs_in_run <= 1:
        return f"Run {run_number}"
    return f"Run {run_number}·{output_number}"


def collect_attempts(
    json_data: Dict[str, Any],
    text_overrides: Optional[Dict[str, str]] = None,
    include_consensus: bool = True,
) -> List[TranscriptionAttempt]:
    """Build the attempt list for a document from its loaded v2 JSON.

    Attempts appear in canonical order — ``(run index, output index within
    run)`` — which fixes matrix row/column order and every tie-break downstream
    (D10). Attempt ids are stable strings (``r2:o1``) rather than positions, so
    excluding one attempt does not renumber the others.

    ``text_overrides`` maps ``attempt_id`` to replacement text, so an edit the
    user has not yet persisted can still be analyzed; those attempts are marked
    ``edited_in_session``.

    Consensus records from ``harmonizations[]`` are appended when
    *include_consensus* is set, flagged ``source_type="consensus"`` so the UI
    can show them while keeping them out of the replicate set (§2.1).
    """
    overrides = text_overrides or {}
    attempts: List[TranscriptionAttempt] = []
    seen_records: Dict[Tuple, int] = {}

    runs = json_data.get("runs", []) or []
    for run_index, run in enumerate(runs):
        if not isinstance(run, dict):
            continue

        fingerprint = _run_fingerprint(run)
        duplicate_of = seen_records.get(fingerprint)
        if duplicate_of is None:
            seen_records[fingerprint] = run_index

        outputs = run.get("outputs", []) or []
        for output_index, output in enumerate(outputs):
            attempt_id = f"r{run_index}:o{output_index}"
            text = overrides.get(attempt_id, _output_text(output))

            attempts.append(
                TranscriptionAttempt(
                    attempt_id=attempt_id,
                    label=_label_for(run_index + 1, output_index + 1, len(outputs)),
                    text=text,
                    source_type=SOURCE_AI,
                    run_index=run_index,
                    output_index=output_index,
                    model=run.get("model") or None,
                    provider=run.get("provider") or None,
                    profile_name=run.get("profile_name") or None,
                    temperature=run.get("temperature"),
                    created_at=run.get("started_at") or run.get("timestamp"),
                    run_id=run.get("run_id") or None,
                    edited_in_session=attempt_id in overrides,
                    health=AttemptHealth(
                        HEALTH_DUPLICATE_RECORD,
                        (f"duplicate of the record at run index {duplicate_of}",),
                        0,
                    )
                    if duplicate_of is not None
                    else AttemptHealth(HEALTH_OK, (), 0),
                )
            )

    attempts = _apply_health(attempts)

    if include_consensus:
        attempts.extend(_collect_consensus(json_data))

    return attempts


def _collect_consensus(json_data: Dict[str, Any]) -> List[TranscriptionAttempt]:
    """Surface stored harmonizations as consensus records (§2.1).

    They are listed so the user can see what data exists, but they are not
    independent attempts and are excluded from the replicate set.
    """
    records: List[TranscriptionAttempt] = []
    harmonizations = json_data.get("harmonizations", []) or []
    for i, record in enumerate(harmonizations):
        if not isinstance(record, dict):
            continue
        text = str(record.get("harmonized_text", "") or "")
        records.append(
            TranscriptionAttempt(
                attempt_id=f"h{i}",
                label=f"Harmonization {i + 1}",
                text=text,
                source_type=SOURCE_CONSENSUS,
                model=record.get("model_used") or None,
                provider=record.get("provider") or None,
                temperature=record.get("temperature"),
                created_at=record.get("created_at"),
                health=screen_health(text),
            )
        )
    return records


def _apply_health(attempts: Sequence[TranscriptionAttempt]) -> List[TranscriptionAttempt]:
    """Screen every attempt, then cross-link identical content (§23, §24)."""
    if not attempts:
        return []

    screened_texts = {
        a.attempt_id: normalize(a.text or "", SCREENING_PROFILE) for a in attempts
    }
    lengths = sorted(len(t) for t in screened_texts.values() if t)
    median_length = _median(lengths) if lengths else None

    by_text: Dict[str, List[str]] = {}
    for attempt_id, text in screened_texts.items():
        if text:
            by_text.setdefault(text, []).append(attempt_id)

    result: List[TranscriptionAttempt] = []
    for attempt in attempts:
        # A duplicate *record* verdict is structural and outranks text screening.
        if attempt.health.status == HEALTH_DUPLICATE_RECORD:
            health = AttemptHealth(
                HEALTH_DUPLICATE_RECORD,
                attempt.health.reasons,
                len(screened_texts[attempt.attempt_id]),
            )
        else:
            health = screen_health(attempt.text, median_length)

        twins = tuple(
            other
            for other in by_text.get(screened_texts[attempt.attempt_id], [])
            if other != attempt.attempt_id
        )
        result.append(
            _replace_health(
                attempt,
                AttemptHealth(
                    status=health.status,
                    reasons=health.reasons,
                    char_count=health.char_count,
                    identical_to=twins,
                ),
            )
        )
    return result


def _replace_health(
    attempt: TranscriptionAttempt, health: AttemptHealth
) -> TranscriptionAttempt:
    return TranscriptionAttempt(
        attempt_id=attempt.attempt_id,
        label=attempt.label,
        text=attempt.text,
        source_type=attempt.source_type,
        run_index=attempt.run_index,
        output_index=attempt.output_index,
        model=attempt.model,
        provider=attempt.provider,
        profile_name=attempt.profile_name,
        temperature=attempt.temperature,
        created_at=attempt.created_at,
        run_id=attempt.run_id,
        edited_in_session=attempt.edited_in_session,
        health=health,
    )


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return float(ordered[mid])
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def default_selection(attempts: Sequence[TranscriptionAttempt]) -> List[str]:
    """Attempt ids checked by default: replicates that passed screening.

    Degenerate attempts are left visible but unchecked — the user decides
    whether an unusual-but-valid transcription stays in (§23, final clause).
    """
    return [
        a.attempt_id for a in attempts if a.is_replicate and a.health.is_suitable
    ]


def selected_attempts(
    attempts: Sequence[TranscriptionAttempt], attempt_ids: Sequence[str]
) -> List[TranscriptionAttempt]:
    """Resolve ids to attempts in canonical order, ignoring client ordering.

    Two clients sending the same set in different orders must get identical
    results (D10), so selection order is discarded here rather than trusted.
    """
    wanted = set(attempt_ids)
    unknown = wanted - {a.attempt_id for a in attempts}
    if unknown:
        raise KeyError(f"Unknown attempt id(s): {sorted(unknown)}")
    return [a for a in attempts if a.attempt_id in wanted]
