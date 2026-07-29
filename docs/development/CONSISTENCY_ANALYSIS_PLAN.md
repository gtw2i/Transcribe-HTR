# Multi-Transcription Consistency and Consensus Analysis — Design & Implementation Plan

**Status:** ✅ Implemented. Retained as the design rationale for the shipped feature —
see `backend/analysis/`, `backend/routers/consistency.py`,
`frontend/src/components/consistency/`, and the 📊 Consistency tab.
All six design decisions resolved — see §15.
**Date:** 2026-07-26 · **Revised** 2026-07-26 for the React + FastAPI architecture
**Spec source:** "Requirements Specification: Multi-Transcription Consistency and Consensus Analysis" (§1–§33)
**Target:** the FastAPI backend + React frontend.

> **Historical note.** This document was written while the repository still
> contained a deprecated Streamlit implementation under `legacy-streamlit/`.
> That tree was removed before the public release, so references to it below
> describe a directory that no longer exists. Everything stated about
> `backend/analysis/` and the API layer remains current.

> **Revision note.** The first draft of this plan targeted the Streamlit app. The
> React/FastAPI migration changes *where* the feature lives, not *what it computes*:
> §5 (data model), §6 (all algorithms and definitions), §9 (ground-truth mode) and §11
> (performance) are unchanged. Rewritten for the new stack: D1–D3, D5, D6, D8, D11, §7
> (UI), §8 (export), §10 (dependencies), §12 (testing), §13 (phases). The migration also
> **removed** the plan's single largest correctness hazard — see D3.

---

## 1. Executive summary

The app can already produce N independent transcriptions of one document image and
harmonize them with an LLM. What it cannot do is *measure* how much those N attempts
agree, identify which attempt is anomalous, build a reproducible non-LLM consensus, or
export any of that for research use.

This feature adds a **deterministic, LLM-free statistical layer** that treats repeated
transcription attempts as **replicate measurements**. It reports pairwise CER/WER
disagreement, per-attempt consistency scores, heat maps, robust outlier diagnostics, a
medoid ("most representative existing") transcription, a voting-based deterministic
consensus, and a full provenance-bearing export bundle.

The governing methodological constraint (§1, §28, §33) is that **none of this measures
accuracy**. Every label, column header, chart title, and exported field must say
*disagreement / consistency / variability*, never *error rate / accuracy*, unless a
human-verified reference has been explicitly designated (§29).

### What makes this non-trivial in the current codebase

1. The existing `levenshtein_distance` is pure-Python O(n·m) and returns only a distance
   ([backend/core/transcription_utils.py](../../backend/core/transcription_utils.py)) — no
   substitution/deletion/insertion breakdown, and far too slow for char-level comparison
   of full pages. See D4.
2. `levenshtein_distance_pairwise` already builds symmetric matrices, but normalizes by
   `max_len` with an epsilon — **that is not CER**. It has to be replaced, not extended.
3. Run outputs are stored as plain strings: `create_run_record(..., transcription_outputs:
   List[str], ...)` in [backend/core/json_manager.py:82](../../backend/core/json_manager.py#L82).
   Per-attempt metadata (model, provider, timestamp) exists only at the *run* level, so
   §3.1's selection list has to derive attempt identity from run structure. Straightforward
   server-side — see D3.
4. `routers/harmonization.py` flattens every run's outputs into one anonymous list
   ([backend/routers/harmonization.py:29-33](../../backend/routers/harmonization.py#L29-L33)) and
   selects by bare integer index. Workable for harmonizing; not sufficient for an analysis
   that must report *which* run produced each attempt. The new router must not copy this.
5. There is no persistence slot for an analysis and no ground-truth concept.

Everything else is reusable as-is, and more of it than in the Streamlit design: session
workspace, the v2 JSON record, the profile system, provider routing across all three
providers, the pure-engine convention, and an export layer that already builds
multi-format bundles.

---

## 2. Terminology contract (§28)

This table is normative. It drives UI strings, dataclass field names, CSV column
headers, and docstrings. Reviewers should reject any PR that introduces a banned term
outside ground-truth mode.

| Use | Never use (outside §29 ground-truth mode) |
|---|---|
| transcription **consistency** | accuracy |
| pairwise **disagreement** | error rate, true error rate |
| internal consistency | correctness |
| replicate variability | precision (ambiguous) |
| transcription-to-transcription CER / WER | transcription error rate |
| consensus disagreement | consensus accuracy |
| **possible** outlier / **strong** outlier | bad run, wrong transcription, failed run |
| deterministic consensus | the correct transcription |

Field-naming convention in code: `cer_disagreement`, `wer_disagreement`,
`mean_pairwise_cer`, `outlier_status`. Ground-truth-mode fields get an explicit prefix:
`gt_cer`, `gt_wer`, `gt_accuracy`.

The metric *math* for CER/WER is the standard ASR/HTR formula; only the **interpretation
and labeling** change. That distinction is worth stating once, prominently, in the UI
methods note.

---

## 3. Gap analysis — what exists vs. what §1–§33 need

| Spec area | Current state | Verdict |
|---|---|---|
| §2 Document group | v2 JSON groups runs per image root; `harmonizations[]` already separate from `runs[]`; backend reads it directly | **Mostly there** |
| §2 Attempt vs consensus vs reference | Harmonizations and summaries stored separately (good); no reference concept | **Gap** (reference) |
| §3 Selection UI w/ metadata | `POST /api/harmonize` selects by bare integer index; no metadata reaches the client | **Gap** |
| §4 Normalization | None | **Gap** |
| §5/§6 CER/WER + S/D/I counts | `levenshtein_distance` (distance only, pure Python) | **Gap** |
| §7 Matrices | `levenshtein_distance_pairwise` returns symmetric matrices but with `max_len` + epsilon normalization — **not CER** | **Wrong metric; rewrite** |
| §8 Heat maps | None. No charting library in `frontend/package.json` | **Gap** — see D5 |
| §9–§11 Summary/uncertainty/per-attempt stats | None | **Gap** |
| §12 Outliers | None | **Gap** |
| §13–§16 Consensus | LLM harmonization only (`backend/engines/harmonization_engine.py`) | **LLM path exists; deterministic + medoid are gaps** |
| §17 Consensus comparison table | None | **Gap** |
| §18 Difference inspection | NER colorization exists (`colorization_engine.py`, `POST /api/colorize`) — entity highlighting, not a 2-way diff | **Adjacent, not sufficient** |
| §19 Sorting/linked views | None | **Gap** |
| §22 Small-sample behavior | None | **Gap** |
| §23 Degenerate detection | Harmonize router rejects `< 2` outputs; nothing else | **Gap** |
| §24 Duplicates | Not modeled | **Gap** |
| §25 Provenance | Run-level provenance is good; no analysis-level | **Gap** |
| §26 Export | `GET /api/export?format=json\|txt\|docx`, single file or ZIP, via `core/export_utils.py` | **Strong foundation to extend** |
| §27 Reproducibility | N/A | **Gap (design constraint)** |
| §29 Ground truth | None | **Gap (design for it, build later)** |

Two rows improved materially in the migration: **§26 Export** (a real multi-format bundle
builder now exists, rather than a two-branch blob function) and **§2 Document group** (the
backend reads the v2 JSON directly instead of flattening it into session state).

---

## 4. Architectural decisions

Each decision is numbered so it can be referenced in review and revisited.

### D1 — `backend/analysis/` package, pure — no FastAPI, no HTTP

All computation goes into a new backend package with **zero FastAPI imports**, matching
the branch's stated convention: *"Engine classes have no FastAPI imports. Routers
instantiate them; engines take plain args and return plain dicts/objects."* This is what
makes §27 (reproducibility) testable and keeps the whole feature usable from a notebook,
a test, or a future CLI.

```text
backend/analysis/
  __init__.py            # public API surface
  attempts.py            # TranscriptionAttempt, collection from v2 JSON, health screening
  normalize.py           # normalization profiles + tokenizers
  metrics.py             # edit-distance backend, CER/WER, PairMetrics
  matrices.py            # pairwise matrices, summary + per-attempt statistics
  uncertainty.py         # jackknife over attempts
  outliers.py            # robust (median/MAD) outlier classification
  consensus.py           # medoid + deterministic voting consensus
  llm_consensus.py       # thin adapter over harmonization_engine
  diffing.py             # 2-way diff model, serialized to the client
  report.py              # ConsistencyReport dataclass, provenance, narrative summary
  export.py              # CSV / JSON / figure bundle builder
  figures.py             # matplotlib heat-map rendering (export only — see D5)
```

**Placement:** a sibling of `engines/`, not a module inside it. The existing engines each
wrap one provider call; this is a multi-module numerical library with its own submodule
structure, and `engines/consistency_engine.py` would misrepresent it. `llm_consensus.py`
is the one piece that behaves like a conventional engine, and it delegates to
`engines/harmonization_engine.py` rather than duplicating provider logic.

**Router:** `backend/routers/consistency.py`, mounted at `/api` alongside the other
eleven in `backend/main.py`. **Schemas:** `backend/schemas/consistency.py` (Pydantic),
following the one-file-per-feature convention.

Nothing in this package imports from `frontend/` or `legacy-streamlit/`, and nothing in
`legacy-streamlit/` is modified.

### D2 — New sixth tab in the React tab bar *(decided 2026-07-26)*

`frontend/src/components/layout/TabBar.jsx:3-9` defines five tabs. **Harmonization is not
among them** — it was folded into TranscriptionTab, which calls the `harmonize` API
directly. Consistency becomes the sixth, between Analysis and Export:

```text
🚀 Start · 📤 Upload · 📝 Transcription · 🔬 Analysis · 📊 Consistency · 📦 Export
```

This preserves the decision already made — Consistency sits immediately after Analysis —
under the new tab set. The workflow reads *transcribe → read the text → measure the
replicates → export*.

Wiring is two lines plus a component:

- one entry in the `TABS` array in `TabBar.jsx`;
- one `{activeTab === 'consistency' && <ConsistencyTab />}` line in `App.jsx:40-44`;
- `frontend/src/components/consistency/` — the new component tree;
- `frontend/src/api/consistency.js` — axios wrapper, matching the per-endpoint convention.

`AnalysisTab.jsx` is **not** modified. No React Router change is needed: `activeTab` is a
plain Zustand field.

Optionally gate the tab behind `featureFlags.js` (`CONSISTENCY_UI_ENABLED`) during
development, following the existing `TTS_UI_ENABLED` precedent, so the tab can merge
before it is finished.

### D3 — Attempt metadata read straight from the v2 JSON *(simplified by the migration)*

> The Streamlit draft of this decision described a positional reconciliation between the
> canonical JSON and `st.session_state.outputs`, needed because six code paths wrote that
> flat list. **That entire mechanism is now unnecessary** — it was the plan's largest
> correctness hazard, and the migration deleted the problem rather than solving it.

`analysis.attempts.collect_attempts(json_data)` takes the loaded v2 JSON, walks `runs[]`
in order, and enumerates each run's `outputs`, emitting one `TranscriptionAttempt` per
output with the run's metadata attached: `run_id`, `model`, `provider`, `profile_name`,
`temperature`, `started_at`, plus the run index and the output index within the run.

No session state is involved, so there is no list to keep in sync, no count-mismatch
fallback, and no "metadata unavailable" caption. The function is pure — JSON in, list of
attempts out — which also makes it trivially testable from a fixture file.

Two details it must handle:

- **Outputs may be strings or dicts.** `create_run_record` writes `List[str]`, but `routers/harmonization.py:32` already defends with `output.get("text", "") if isinstance(output, dict) else str(output)`. Use the same coercion so both shapes work.
- **Do not copy the flattening pattern.** `routers/harmonization.py:29-33` collapses every run's outputs into one anonymous list and selects by integer index. That is why the client cannot show §3.1's metadata today. The consistency router returns attempts as objects with stable IDs (D10) and never exposes a bare positional index.

Editing a transcription is a separate concern: the React client holds edits in Zustand
(`updateOutputText`) before they are persisted. The analyze endpoint therefore accepts
**optional inline text overrides** keyed by `attempt_id`, so an in-flight edit can be
analyzed without first saving it. Overridden attempts are marked `edited_in_session:
true` and the flag is recorded in provenance (§25).

### D4 — `rapidfuzz` as the edit-distance backend, with a numpy fallback

Char-level Levenshtein on a full manuscript page (~3–5k chars) is ~16–25M DP cells.
Pure Python: **10–30 s per pair**; 5 attempts = 10 pairs = **several minutes**.
Unacceptable for an interactive tab.

- **Primary:** `rapidfuzz` (`rapidfuzz.distance.Levenshtein.opcodes` / `.editops`) — C++, sub-100 ms per pair, pure wheels on all platforms, no compiler needed, works on any hashable sequence (so it serves both char and word level).
- **Fallback:** numpy row-wise DP with a `uint8` traceback matrix, used only if `rapidfuzz` is absent. ~25 MB peak for a 5k×5k page; acceptable and still ~100× faster than pure Python.

`analysis/metrics.py` selects the backend at import and records which one ran in
provenance (both must give identical S/D/I counts — enforced by a cross-backend test).

Not chosen: `jiwer` (opinionated normalization we'd have to fight, and it depends on
rapidfuzz anyway); `python-Levenshtein` (GPL-adjacent licensing history, str-only).

### D5 — Heat maps: CSS-grid in React on screen, matplotlib server-side for export

`frontend/package.json` contains **no charting library**, and the branch is deliberately
lean — *"Plain CSS only — no Tailwind/MUI."* Adding Recharts/visx/D3 for one view would
cut against that, so the two jobs get two purpose-fit implementations:

**On screen — a plain CSS-grid component**, `components/consistency/HeatMap.jsx`:

- an N×N `display: grid` of cells; background colour interpolated from the cell value; row/column headers are the short attempt labels;
- the numeric value rendered directly in the cell when N ≤ 8, and on hover/focus otherwise (§8 allows either — "display the numeric value for each cell **or** expose it interactively");
- `onClick` sets `focusAttemptId` in Zustand, which highlights the matching row in the per-attempt table and the matching cells in the other heat map (§19 linked views);
- colours come from `styles/variables.css` tokens, so the map inherits the existing palette instead of introducing a second one.

Roughly 100 lines, no dependency, fully interactive, and accessible (real DOM cells carry
`title` and `aria-label`). N is small by construction — this is a document's replicate
count, not a large matrix.

**For export — matplotlib, server-side** in `backend/analysis/figures.py`, returning
300-dpi PNG + SVG through the export endpoint. §26 requires publication-quality figures,
and rendering them in Python is both higher quality and simpler than driving a canvas
export from the browser.

The two renderers read the same `HeatmapSpec` (values, labels, colour domain, clipping
threshold) computed once in `matrices.py`, so the on-screen and exported figures cannot
diverge. This is a **better** split than the Streamlit plan's Altair + matplotlib pair:
the interactive version costs no dependency, and the publication version lives where the
data already is.

`scipy` is installed transitively but **not** declared — do not depend on it. All
statistics use numpy only.

### D6 — Analysis results persist in v2 JSON under a new `analyses[]` array

> **Revised during Phase 6 (2026-07-27): no version bump.** The original
> decision was to move `schema_version` to `"2.1"`. Two facts found in the code
> overrode it:
>
> - the branch had already added **two** record arrays — `summaries` and `ner_results` — to `create_v2_json_schema` **without** bumping the version, establishing that additive arrays are not a schema break here;
> - `tests/test_data_integrity/test_schema_evolution.py:30` asserts that a newly created schema has `schema_version == "2.0"`, so bumping would have broken a passing test to no benefit.
>
> `analyses[]` therefore follows the same pattern: present in new schemas,
> created on demand for older files (`if "analyses" not in v2_json`). The
> validator was widened to accept `{"2.0", "2.1"}` for forward tolerance, which
> costs nothing and leaves `"1.0"` correctly rejected.

Follows the existing `harmonizations[]` precedent exactly, in
`backend/core/session_workspace.py` and `backend/core/json_manager.py`. `schema_version`
becomes `"2.1"`; every validator accepts `{"2.0", "2.1"}` and the schema constructor adds
`"analyses": []`. Old files load unchanged — the array is created on first write, the
same defensive pattern as `append_harmonization_to_v2_json`.

`json_manager.save_summary()` (added for the summarization feature) is the closest
existing model for the write path; `save_analysis()` should mirror its shape.

### D7 — Deterministic core, LLM strictly optional and always labeled

§27: the CER/WER path must never call a model. `backend/analysis/` has no provider
imports except in `llm_consensus.py`, and the LLM path is a **separate endpoint**
(`POST /api/consistency/llm-consensus`) rather than a branch inside the analyze call —
so it cannot be reached accidentally, and a client that never calls it is guaranteed
LLM-free. The UI badges the three consensus kinds distinctly (§16):

- 🅰 **Most representative existing** — verbatim text from one attempt (medoid)
- ⚙ **Deterministic consensus** — computed by voting, reproducible
- 🤖 **LLM consensus** — *generated*, not observed

### D8 — Two-layer caching: React Query on the client, LRU on the server

`@st.cache_data` is gone with Streamlit. Its replacement is the stack's existing pattern:

**Client** — React Query, as the other server data already does (`useRoots`, `useProfiles`,
`useModelList`). The query key is `['consistency', root, sortedAttemptIds, normProfile,
tokenizer]`, so changing the selection or the normalization settings refetches
automatically and re-selecting a previous combination is instant. Keep the branch's
existing `refetchOnWindowFocus: false` default — a deterministic computation has no
reason to refetch on focus.

**Server** — a small `functools.lru_cache`-backed memo in the router keyed on the same
tuple, so two clients (or a refetch after a client-side cache eviction) do not recompute
an identical matrix. Bounded at a few dozen entries; the payload is small.

Because `compute_consistency_report()` is pure and deterministic (D1, §27), both layers
are safe by construction — there is no staleness question, only a cost question. The key
deliberately includes the normalization settings so a settings change recomputes (§3.2).

### D9 — Two-slot result model for full-set vs filtered (§21)

The Zustand store holds `baselineReport` (all non-degenerate attempts, computed on first
open of a document) and `report` (current selection). The comparison panel renders both.
The baseline is never overwritten by an exclusion, satisfying §3.3 ("the original
full-set analysis shall remain recoverable"). Both are ordinary React Query results, so
the baseline costs nothing to keep — it is simply a second cached key.

### D10 — Stable attempt ordering is part of the contract

Reproducibility (§27) and tie-breaking (medoid, voting) both depend on a deterministic
order. Canonical order = **(run index in JSON, output index within run)** — now the only
rule, since attempts are built directly from `runs[]` (D3) and there is no session list
to fall back to. Attempt IDs are stable strings (`r2:o1`), not positions, so excluding an
attempt does not renumber the others in exports.

The server **sorts the incoming `attempt_ids` into canonical order** before computing,
rather than trusting client order. Two clients sending the same set in different orders
must get byte-identical results.

### D11 — Review first, save explicitly *(decided 2026-07-26)*

Running an analysis **never** writes to disk. `POST /api/consistency/analyze` is a pure
computation that returns a report; persistence is a *separate* call,
`POST /api/consistency/save`, triggered by the user clicking **💾 Save this analysis**.

The compute/persist split is cleaner over HTTP than it was in session state: analyze is
idempotent, cacheable (D8), and safe to call on every settings change, while save is the
only endpoint that mutates the document record.

This matches the working reality: the first run of a document often includes a bad
attempt the user only recognizes *after* seeing the heat map. Auto-saving would litter
the JSON with superseded records and make "which analysis is the real one?" ambiguous in
the exported file.

Behavior:

- The save button sits at the bottom of the results, next to Export, and carries an optional one-line note field (e.g. *"excluded Run 4 — empty output"*) stored as `user_note`.
- Unsaved state is visible: a caption reads *"Not saved — this analysis exists only in this session."*
- Saving is **additive and non-destructive**. Re-running after excluding attempts and saving again produces a second record; nothing is overwritten. Each record's `attempts_included` / `attempts_excluded` makes the difference self-documenting.
- A **🗑 Delete** control on each saved record handles genuine mistakes (`DELETE /api/consistency/{analysis_id}`), with a confirmation modal — the project's confirm-destructive-actions convention, and the existing `Modal.jsx` covers it.
- Export (§8) works on the in-session report and does **not** require saving first — a user may only want the CSVs.
- Switching tabs keeps the report (it is a live React Query cache entry); switching documents invalidates it, with a warning if unsaved.
- Saving invalidates the `['consistency', 'saved', root]` query so the "Previous analyses" list refreshes without a manual reload.

Saved analyses appear in a compact "Previous analyses" expander at the top of the tab
(timestamp · N attempts · median CER/WER · note), each loadable back into the view for
comparison. This is the natural home for the §21 full-set-vs-filtered comparison once
more than one analysis exists for a document.

---

## 4a. API surface

`backend/routers/consistency.py`, mounted at `/api` in `backend/main.py`. Request and
response models live in `backend/schemas/consistency.py`. All routes take
`workspace=Depends(get_workspace)` and `file_index=Depends(get_file_index)` and follow
the existing 404/400 conventions from `routers/harmonization.py:18-26`.

| Method | Path | Purpose | LLM? |
|---|---|---|---|
| `GET` | `/consistency/attempts?root=` | List available attempts with §3.1 metadata and health flags. Feeds the selection UI. | no |
| `POST` | `/consistency/analyze` | The whole deterministic pipeline: matrices, statistics, per-attempt scores, outliers, medoid, deterministic consensus, consensus comparison. Returns a `ConsistencyReport`. **Pure — no writes.** | **no** |
| `POST` | `/consistency/diff` | 2-way diff between two attempts, or an attempt and a consensus (§18). Separate call because it is per-pair and on demand. | no |
| `POST` | `/consistency/llm-consensus` | Optional LLM consensus (§16). Separate endpoint by design (D7). | **yes** |
| `POST` | `/consistency/save` | Append the report to `analyses[]` in the document's v2 JSON (D11). | no |
| `GET` | `/consistency/saved?root=` | List previously saved analyses for the document. | no |
| `DELETE` | `/consistency/{analysis_id}` | Remove a saved analysis. | no |
| `GET` | `/consistency/export` | Bundle (§8) — `format=zip\|csv\|json\|png`. Mirrors the existing `/api/export` conventions. | no |

`AnalyzeRequest` carries: `root`, `attempt_ids: list[str]`, `normalization_profile`,
`tokenizer`, optional `text_overrides: dict[str, str]` (D3), and optional
`consensus_method`. Everything needed to reproduce the result is in the request, which is
what makes §27 checkable end-to-end and the D8 cache key well-defined.

Only `/llm-consensus` accepts API keys, and it takes all three
(`openai_api_key` / `gemini_api_key` / `anthropic_api_key`) following the
`HarmonizeRequest` precedent.

---

## 5. Data model

### 5.1 `TranscriptionAttempt` (in-memory)

```python
@dataclass(frozen=True)
class TranscriptionAttempt:
    attempt_id: str            # stable, e.g. "r2:o1"
    label: str                 # display, e.g. "Run 2 · Attempt 1"
    text: str                  # ORIGINAL text — never mutated (§4.1)
    source_type: str           # "ai" | "human" | "consensus" | "reference"
    run_index: int | None
    output_index: int | None
    model: str | None
    provider: str | None
    profile_name: str | None
    temperature: float | None
    created_at: str | None     # ISO 8601
    run_id: str | None
    edited_in_session: bool = False
    # populated by the health screen (§23/§24)
    health: AttemptHealth = ...
```

`source_type` enforces §2.1: an attempt with `"consensus"` or `"reference"` is **never**
auto-included in the replicate set. Consensus records surface in the selection list as
greyed, unchecked rows labeled *"consensus — not an independent attempt"*.

### 5.2 `AttemptHealth` (§23, §24)

```python
@dataclass(frozen=True)
class AttemptHealth:
    status: str              # "ok" | "empty" | "near_empty" | "error_text" | "corrupt"
    reasons: list[str]
    char_count: int
    identical_to: list[str]  # attempt_ids with byte-identical normalized text
```

Screening rules (all deterministic, all documented in the report):

| Check | Rule |
|---|---|
| empty | `text.strip() == ""` |
| near-empty | `len(normalized) < 20` **or** `< 5%` of the group's median normalized length |
| error text | matches an anchored refusal/error pattern list (`^\s*(error|sorry|i (can'?t|cannot|am unable)|as an ai)`), or is ≥90% fenced code block |
| corrupt | `> 5%` of chars are U+FFFD, or `> 30%` are C0 control chars |
| identical content | normalized text equals another attempt's — **flag only** |

**Critical, per §23/§24:** `empty` / `error_text` / `corrupt` attempts are **unchecked by
default and visibly flagged**, never silently scored as high-error. Identical attempts
from separate runs stay as **distinct** attempts with pairwise CER/WER = 0 — that is
meaningful reproducibility evidence and must not be deduplicated. Only true duplicate
*records* (same `run_id` **and** same `output_index`) are collapsed.

### 5.3 Persisted analysis record (V2 JSON `analyses[]`)

```jsonc
{
  "analysis_id": "uuid4",
  "created_at": "2026-07-26T14:03:11Z",
  "analysis_version": "1.0",          // bump when any definition changes
  "app_version": "2.1",
  "source_document": { "root": "letter_042", "image_filename": "letter_042.jpg" },
  "attempts_included": ["r1:o0", "r1:o1", "r2:o0"],
  "attempts_excluded": [
    { "attempt_id": "r2:o1", "reason": "user_excluded" },
    { "attempt_id": "r3:o0", "reason": "health:empty" }
  ],
  "attempt_metadata": [ /* model, provider, profile, timestamp per included attempt */ ],
  "settings": {
    "normalization_profile": "standard_historical",
    "normalization_version": "1.0",
    "normalization_steps": ["nfc", "strip_line_edges", "collapse_spaces", "..."],
    "tokenizer": "word_simple",
    "cer_definition": "(S+D+I)/N_ref_chars, unit-cost Levenshtein",
    "wer_definition": "(S+D+I)/N_ref_words, unit-cost Levenshtein over tokens",
    "symmetric_definition": "2*d/(len_A+len_B)  [= harmonic mean of the two directional rates]",
    "uncertainty_method": "jackknife_over_attempts",
    "backend": "rapidfuzz-3.x"
  },
  "results": {
    "n_attempts": 5, "n_pairs": 10,
    "cer": { "mean": 0.041, "median": 0.038, "sd": 0.019, "iqr": [0.029, 0.047],
             "jackknife_se": 0.008 },
    "wer": { "...": "..." },
    "matrix_symmetric_cer": [[0.0, "..."]],
    "matrix_directional_cer": [[0.0, "..."]],
    "matrix_symmetric_wer": [[0.0, "..."]],
    "matrix_directional_wer": [[0.0, "..."]],
    "per_attempt": [ { "attempt_id": "r1:o0", "mean_cer": 0.035, "median_cer": 0.034,
                       "min_cer": 0.021, "max_cer": 0.052, "...": "...",
                       "outlier_status": "none", "robust_z": 0.4 } ],
    "medoid_attempt_id": "r1:o1",
    "consensus": { "method": "deterministic_vote_v1", "text": "...",
                   "support": [0.8, 1.0, 0.6], "low_support_count": 12 },
    "consensus_comparison": [ { "attempt_id": "r1:o0", "cer_vs_consensus": 0.030, "...": "..." } ]
  },
  "narrative": "Five independent transcription attempts were analyzed. ..."
}
```

This single record satisfies §25 (provenance) and is the payload behind every §26 export.

---

## 6. Algorithms and definitions

### 6.1 Normalization (§4)

A profile is an **ordered list of named, versioned steps**. The original text is never
touched; normalization produces a parallel string used only for measurement (§4.1).

| Step id | Effect |
|---|---|
| `nfc` / `nfkc` | Unicode normalization |
| `strip_document_edges` | strip leading/trailing whitespace of the whole text |
| `strip_line_edges` | strip each line's leading/trailing whitespace |
| `collapse_spaces` | runs of spaces/tabs → single space |
| `collapse_blank_lines` | 3+ consecutive newlines → 2 |
| `drop_empty_lines` | remove all blank lines |
| `join_linebreak_hyphens` | `word-\nfrag` → `wordfrag` (line-break hyphenation) |
| `newlines_to_spaces` | flatten all line structure |
| `lowercase` | case folding |
| `strip_punctuation` | remove Unicode `P*` categories |

**Shipped profiles** *(decided 2026-07-26: `standard_historical` is the default, and
`diplomatic` is a first-class alternative, not a hidden option — some projects transcribe
diplomatically and must be able to select it in one click.)*

| Profile | Steps | Purpose |
|---|---|---|
| **`standard_historical`** *(default)* | `nfc`, `strip_line_edges`, `collapse_spaces`, `join_linebreak_hyphens`, `collapse_blank_lines`, `strip_document_edges` | Preserves case, punctuation, and paragraph structure — the defensible default for historical HTR |
| **`diplomatic`** | `nfc` only | Literal/diplomatic comparison: every difference in case, punctuation, spacing, and line breaks counts (§4.3) |
| `normalized` | standard + `lowercase`, `strip_punctuation`, `newlines_to_spaces` | Content-only comparison; ignores orthographic and layout variation |

Rationale for the default: capitalization and punctuation are *substantive editorial
data* in manuscript transcription, so folding them would hide real disagreement.
Whitespace and line-break hyphenation are *rendering artifacts* of the model's output
format, so normalizing them removes noise that is not about reading the handwriting.
This reasoning ships in the UI help text — §4.2 requires the default be "clearly
documented".

**UI treatment:** the profile selector is a visible radio/segmented control (not a
buried dropdown) with a one-line description each, and the exact step list for the
current choice is shown beneath it. Because the profile is part of the cache key (D8),
switching it refetches immediately, so a project can compare
`standard_historical` against `diplomatic` on the same document in two clicks — which is
itself a useful finding (how much of the disagreement is orthographic vs. substantive).

Adding a profile means adding one entry to the `NORMALIZATION_PROFILES` registry in
`analysis/normalize.py`; nothing else changes (§4.3).

**Tokenizers (§6):** `word_simple` (whitespace split, default) and `word_punct`
(`\w+|[^\w\s]`, splits punctuation into its own tokens). The choice is recorded in
provenance; it must be identical across every comparison in one analysis.

### 6.2 CER and WER, directional and symmetric (§5, §6)

For sequences A (reference) and B (hypothesis), unit-cost Levenshtein alignment yields
substitutions S, deletions D, insertions I, and edit distance `d = S + D + I`.

```
CER(A→B) = (S + D + I) / |A|      WER(A→B) = (S + D + I) / |tokens(A)|
CER(B→A) = (S + D + I) / |B|      WER(B→A) = (S + D + I) / |tokens(B)|
```

**A property worth exploiting.** With unit costs, `d(A,B) = d(B,A)`. So the two
directional rates share a numerator and differ *only in the denominator*, and the edit
counts simply swap roles:

```
S(B→A) = S(A→B)      D(B→A) = I(A→B)      I(B→A) = D(A→B)
```

Consequently one alignment per pair suffices; the reverse direction is derived, not
recomputed. This halves the work and guarantees the two directions can never disagree
numerically.

**Symmetric disagreement** — the primary displayed metric *(decided 2026-07-26)*:

```text
CER_sym(A,B) = 2d / (|A| + |B|)
```

which is exactly the **harmonic mean of the two directional CERs**. That is the
documented definition (§5 requires the definition appear in the output), and it is
reference-designation-independent by construction. WER_sym is identical over tokens.

Chosen over the arithmetic mean of the directional rates because it falls directly out of
the shared-numerator identity above — one line of algebra to show in a paper, no extra
parameter, and it needs no caveat about why two different denominators were averaged.

### 6.2.1 Retention policy — keep everything *(decided 2026-07-26)*

Nothing computed is discarded. `PairMetrics` is the full record for a pair, and every
field reaches the export:

```python
@dataclass(frozen=True)
class PairMetrics:
    a_id: str; b_id: str
    # character level
    char_distance: int                  # d, symmetric
    char_sub: int; char_del: int; char_ins: int   # A as reference; B derived by role-swap
    len_a_chars: int; len_b_chars: int
    cer_a_to_b: float; cer_b_to_a: float; cer_sym: float
    # word level
    word_distance: int
    word_sub: int; word_del: int; word_ins: int
    len_a_words: int; len_b_words: int
    wer_a_to_b: float; wer_b_to_a: float; wer_sym: float
    # retained for the diff viewer and change categorization (§18)
    word_opcodes: tuple[tuple[str, int, int, int, int], ...]
```

The symmetric score is what the heat maps and headline statistics display; the
directional rates and raw S/D/I counts sit behind an expander in the UI and are written
unconditionally to `pairwise_edit_counts.csv` and to the `analysis.json` record. This
satisfies §5/§6 ("shall retain the directional results rather than immediately discarding
them") and leaves the door open for analyses not yet specified — asymmetry diagnostics
(is one attempt systematically longer?), insertion-vs-deletion bias per model, or a
different symmetric definition computed after the fact from stored primitives.

Storage cost is trivial: ~20 floats/ints per pair, 45 pairs at 10 attempts.

**Edge cases**, all explicit and tested:
- both sides empty → disagreement `0.0`
- one side empty → directional rate against the empty reference is undefined (0/0); report `null`, and set the symmetric rate to `1.0` (`2d/(0+|B|) = 2` clipped — instead define: if either side is empty, `CER_sym = 1.0`). Such attempts are health-flagged out by default anyway.
- CER **can exceed 1.0** when the hypothesis is much longer than the reference. Do not clip; render values >1.0 honestly and note it in the methods text.

### 6.3 Matrices (§7)

Four N×N matrices: symmetric CER, symmetric WER, directional CER, directional WER.
Diagonal is exactly `0.0`. Symmetric matrices are computed on the upper triangle and
mirrored — so `M[i][j] == M[j][i]` bitwise, not just approximately. Directional matrices
read row = reference, column = hypothesis; this orientation is stated in the UI and in
the exported CSV header.

### 6.4 Summary statistics (§9)

Computed over the **N(N−1)/2 unique unordered pairs only** — never over all N²−N
directional cells (§9 is explicit about this).

Reported: `n_attempts`, `n_pairs`, mean, median, standard deviation, IQR, min, max — for
CER and WER separately. Directional statistics are summarized in a separate collapsed
panel so they cannot be mistaken for the primary figure.

### 6.5 Uncertainty (§10)

Pairwise cells share attempts, so they are **not independent observations**. Treating
`sd/√n_pairs` as a standard error would overstate precision — the spec explicitly
forbids implying that.

Three clearly-labeled quantities, never merged into an unlabeled "±":

| Quantity | Definition | Label shown |
|---|---|---|
| Central tendency | median pairwise disagreement (mean also shown) | "Median pairwise CER disagreement" |
| Variability among attempts | IQR of the unique pairwise values; SD secondary | "IQR across 10 pairs" |
| Uncertainty of the aggregate | **jackknife over attempts** (leave-one-attempt-out, recompute the mean over remaining pairs, `SE_jack = sqrt((N−1)/N · Σ(θ̂₍ᵢ₎ − θ̄)²)`) | "Jackknife SE (resampling over the 5 attempts)" |

The resampling unit is the **attempt**, not the pair — that is what makes it valid under
the shared-attempt dependency. Suppressed entirely for N < 4, with a note (§22).

*Decided 2026-07-26:* **jackknife only** for now. Bootstrap-over-attempts is deliberately
deferred — it needs an RNG seed in provenance, and at N = 5 a percentile interval from
resampling five items is barely more informative than the jackknife while looking
considerably more authoritative. Two consequences for implementation:

- `backend/analysis/uncertainty.py` ships `jackknife_se(values_by_attempt)` and nothing else; no RNG seed appears in the request, the store, or provenance.
- The `uncertainty_method` field in the record is still a **string**, not a boolean — so adding `"bootstrap_percentile"` later never invalidates or silently reinterprets an analysis saved today.

The jackknife is itself fully deterministic, which keeps §27 clean: with bootstrap
omitted, *no* part of the numerical pipeline touches an RNG.

Every error bar in the UI carries an explicit caption naming what it is. No bare `±`
anywhere (§10, final clause).

### 6.6 Per-attempt consistency scores (§11)

For attempt *i*, over the symmetric matrix row excluding the diagonal: mean, median,
min, max — for CER and WER. These are the sortable columns of the main table (§19) and
the input to outlier detection.

### 6.7 Outlier identification (§12)

Robust, whole-group, and deliberately conservative:

1. Let `x_i` = **median** symmetric disagreement of attempt *i* with all others (computed for CER and WER independently).
2. `MAD = median(|x_i − median(x)|)`; robust score `z_i = 0.6745·(x_i − median(x)) / MAD`.
3. Degenerate `MAD = 0` but `median > 0` (most attempts agree exactly) → fall back to the ratio rule `x_i / median(x)`, thresholds 1.5 / 2.5.
4. Degenerate `MAD = 0` **and** `median = 0` (the group agrees *perfectly*) → neither a z-score nor a ratio is defined. Score on the raw disagreement, classified by the absolute floor in step 6.
5. Classification: `z ≥ 3.5` → **strong outlier**; `3.5 > z ≥ 2.5` → **possible outlier**; else **none**. An attempt is only flagged if **both** CER and WER agree on at least "possible" — a single-metric flag is downgraded and annotated.
6. **Absolute floor.** An attempt is never flagged when its disagreement is below `MIN_ABSOLUTE_CER = 0.02` / `MIN_ABSOLUTE_WER = 0.05`, however extreme its relative score. Applied per metric, and only ever removes flags.
7. **Requires N ≥ 4.** For N = 2 or 3 the system reports "outlier detection not meaningful at this sample size" (§22) and computes nothing.

> **Steps 4 and 6 added during Phase 4 (2026-07-27)** after running the endpoint
> against realistic data. Step 6 fixes a false positive: an attempt differing by
> a single punctuation mark scored 3× the group median under the ratio rule and
> was flagged, though 1.6% character disagreement is not "substantially
> different" on any reading. Step 4 fixes the opposite and more serious defect —
> with four byte-identical attempts the median *and* MAD are both zero, so the
> old code fell through to an all-zeros score and flagged **nothing**, missing
> the clearest outlier case there is.

Only high-side deviation is flagged. An attempt that agrees *unusually well* is not an
outlier.

> **Revised during Phase 2 implementation (2026-07-26).** Step 1 originally used
> the *mean* row disagreement. Measurement showed the mean is the wrong
> statistic for §12's "pattern of disagreement … rather than relying on a single
> pairwise comparison":
>
> | Scenario (group agreeing at 0.05) | Row means | Row medians |
> |---|---|---|
> | One aberrant pair between two otherwise-typical attempts | `0.15, 0.15, 0.05, 0.05, …` → **both flagged** | `0.05, 0.05, 0.05, …` → correctly clean |
> | One genuinely divergent attempt | `0.16 …, 0.60` → contrast 3.8× | `0.05 …, 0.60` → contrast 12× |
>
> The median is robust to a single aberrant pair *and* separates a true outlier
> more sharply, because the other attempts' means are inflated by their own
> comparisons with the outlier. `mean_disagreement_vector` is retained and is
> still the criterion for medoid selection (§15), where §15 explicitly asks for
> lowest *aggregate* disagreement; the verdict payload reports both.

Presentation is diagnostic, never a verdict (§12). Fixed wording:

> **Attempt 4 — possible outlier.** It shows substantially greater disagreement with the
> remaining attempts (mean pairwise CER 0.18 vs. group median 0.04; robust z = 4.1).
> This may reflect a poor transcription, text the other attempts omitted, genuinely
> ambiguous handwriting, or a different reading of the document. Inspect the differences
> before deciding.

That list of alternative explanations from §12 ships verbatim in an expander next to the
flag.

### 6.8 Medoid — most representative existing transcription (§15)

`argmin_i mean_{j≠i} CER_sym[i][j]`. Ties break by: lowest max pairwise → lowest
mean WER → earliest canonical order. Labeled distinctly from any synthesized consensus,
and guaranteed to be verbatim text from a real attempt.

### 6.9 Deterministic consensus (§14)

Requirements: no LLM, reproducible, derived from agreement among the selected attempts,
and it must **preserve wording rather than improve it**.

**Method `deterministic_vote_v1` — medoid-anchored alignment + token voting:**

1. Normalize and tokenize all selected attempts (words).
2. **Backbone** = the WER medoid. Anchoring to a real attempt (rather than progressive pairwise merging) avoids order-dependence and keeps the output grammatically coherent.
3. For each other attempt, compute word-level Levenshtein **opcodes** against the backbone. This yields, per backbone token position, each attempt's aligned token (`equal`/`replace`), or ε (`delete`), plus any inserted token runs assigned to the gap slot between backbone positions.
4. **Column vote:** for each backbone position, plurality over `{backbone token} ∪ {each attempt's aligned token or ε}`. ε is a legitimate vote for omission. **Ties resolve to the backbone token** — deterministic and biased toward text that a real attempt actually produced.
5. **Gap slots:** an inserted token run is emitted only if the *same* run is contributed by a **strict majority** of attempts (`> N/2`). Otherwise it is dropped. This is intentionally conservative: it prevents one verbose attempt from injecting text.
6. **Support map:** each emitted token carries its vote fraction. Tokens below a threshold (default 0.6) are marked low-support so the UI can shade them. Returned as structured data (token + support float), **not** as pre-rendered HTML — the client styles it. This differs from `/api/colorize`, which returns HTML sanitized with DOMPurify; there is no reason to ship markup for something the React component can render from numbers.
7. **Reassembly:** line and paragraph structure is taken from the **backbone's original text**, so the consensus reads like a transcription rather than a token stream. Original casing/punctuation of the winning token is preserved (voting operates on normalized tokens; the emitted surface form is the winning attempt's original token).

**Determinism:** given a stable attempt order (D10), every step — medoid choice, opcode
computation, plurality, tie-breaks — is deterministic. No RNG is involved.

**Documented limitations** (they belong in the methods text, not hidden):
- A single backbone means material present in a majority of *non-backbone* attempts but absent from the backbone enters only through the strict-majority gap rule; large structural omissions in the backbone are therefore under-recovered. Mitigation: the medoid is by definition the *least* eccentric attempt, so this is rare, and the UI warns when the backbone's length deviates > 20% from the group median.
- Reordered material is handled as delete + insert, not as a move.
- A full profile-HMM/MSA approach would relax both; deferred as `deterministic_vote_v2` behind the versioned `method` field.

The method id `deterministic_vote_v1` is recorded in every output (§14 final clause), so
a future v2 never silently changes past results.

### 6.10 LLM consensus (§16)

A thin adapter over the existing `HarmonizationEngine`, with three constraints added:

- input = **only** the currently selected attempts (§13: no image, no prior consensus, no unselected attempts, no external info);
- a **dedicated prompt** that instructs resolution of discrepancies without modernizing, summarizing, or rewriting historical language (see below);
- result is stored with `source_type = "consensus"`, `generated = true`, plus model, provider, temperature, and token usage (§25).

It never becomes the default consensus and never replaces the deterministic one.

#### Dedicated `consensus_*` profile fields *(decided 2026-07-26)*

The existing harmonization prompts are **not** reused or overloaded. Consensus and
harmonization are different tasks with different failure modes: harmonization is allowed
to produce the best *reading* of the document, whereas a consensus must report what the
replicates jointly support and must not smooth over genuine disagreement. Sharing one
prompt would force it to serve both and do neither well — and any future edit for one
task would silently change the other.

**Two** new optional profile YAML fields — not three. The backend profile schema is not
the legacy one: `backend/core/profile_manager.py:21-26` requires
`harmonization_system_prompt` and `harmonization_prompt` (a single body containing `{}`),
having collapsed the old `harmonization_intro`/`harmonization_closing` pair, with
backward-compat merging at lines 56-60. The consensus fields follow the *current*
convention:

```yaml
consensus_system_prompt: |     # role: adjudicate replicates, do not re-transcribe
consensus_prompt: |            # body; must contain {} for the attempt block
```

Resolution order — and this is what keeps existing profiles working without overloading
anything:

1. the active profile's `consensus_*` field, if present;
2. otherwise a module-level default in `backend/analysis/llm_consensus.py` (`DEFAULT_CONSENSUS_SYSTEM_PROMPT`, `DEFAULT_CONSENSUS_PROMPT`).

Explicitly **not** a fallback to `harmonization_*`. Existing user profiles on disk have
no `consensus_*` fields and will use the shipped defaults, which are written for this
task. The fields stay out of `_REQUIRED_FIELDS`, so nothing already saved breaks and no
migration is needed.

Touched by this change (Phase 6):

- `backend/core/profile_manager.py` — optional-field handling in the load path and save round-trip; `_REQUIRED_FIELDS` unchanged;
- `frontend/src/components/modals/ProfileEditorModal.jsx` — two more `TextArea`s. Note its client-side validation at lines 84-85 asserts the *harmonization* fields are non-empty; the consensus fields must **not** get equivalent checks, or optionality is lost in the UI even though the backend allows it;
- all four templates in `backend/profiles/` (`default_htr`, `civil_war_htr`, `greek_papyrus_htr`, `scientific_tables_htr`);
- the YAML field table in the branch's `CLAUDE.md`.

### 6.11 Consensus comparison (§17)

Once a consensus is chosen (medoid | deterministic | LLM), compare every selected attempt
against it: CER, WER, and full char/word edit counts. Rendered as the §17 table:

| Attempt | CER vs consensus | WER vs consensus | Mean pairwise CER | Mean pairwise WER | Outlier status |

With a standing caption (§17): *"Consensus comparisons are not independent of the
attempts — the consensus was derived from this same set. They are shown separately from
the pairwise statistics for that reason."*

### 6.12 Difference inspection (§18)

Any two selected attempts, or an attempt vs. the consensus. Built on the same word-level
opcodes:

- side-by-side aligned view and an inline unified view, toggleable;
- color coding: unchanged / substituted / inserted / deleted;
- a **change-category breakdown** so the user can answer §18's question directly — counts classified as: case-only, punctuation-only, whitespace-only, spelling variant (edit distance ≤ 2 on the token), omitted word, inserted word, substituted word, whole-line omission (≥ 5 consecutive deletions), major divergence (≥ 25% of tokens differing);
- a toggle back to the **unmodified original text** of either side (§18 final clause).

This categorization is what turns a bare 4% number into an actionable finding, and it is
cheap — it reads the opcodes already computed for the matrices.

---

## 7. UI design

`frontend/src/components/consistency/ConsistencyTab.jsx`, the sixth tab (D2). Layout
follows the §20 workflow top-to-bottom, which also satisfies §31's required output list.

```text
┌─ 📊 Consistency Analysis ─────────────────────────────────────────────┐
│ Document: letter_042.jpg          [ⓘ What this measures — and doesn't]│
├───────────────────────────────────────────────────────────────────────┤
│ ▸ Previous analyses (2 saved)                              [expand ▾] │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 1. Transcription attempts (5 available · 5 selected)                │
│   [Select all] [Clear all] [Reset to full set]                        │
│   ☑ Run 1 · Attempt 1  gemini-2.5-flash  2026-07-24 09:12  civil_war  │
│   ☑ Run 1 · Attempt 2  gemini-2.5-flash  2026-07-24 09:12  civil_war  │
│   ☑ Run 2 · Attempt 1  gpt-4o            2026-07-24 09:31  civil_war  │
│   ☑ Run 2 · Attempt 2  gpt-4o    ⚠ possible outlier                   │
│   ☐ Run 3 · Attempt 1  gemini-2.5-pro    ⛔ empty output — excluded    │
│   ⊘ Harmonization 1 (consensus — not an independent attempt)          │
│     └ [Inspect ▾]  full text of any row, on demand                    │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 2. Comparison settings                                              │
│   Normalization: [standard_historical ▾]  Tokenizer: [word_simple ▾]  │
│   └ shows the exact step list for the chosen profile                  │
├───────────────────────────────────────────────────────────────────────┤
│              [ Run consistency analysis ]   (deterministic · no API)  │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 3. Overall consistency        ⚠ Based on 4 of 5 available attempts  │
│   Median pairwise CER   3.8%   IQR 2.9–4.7%   jackknife SE 0.8%       │
│   Median pairwise WER   7.4%   IQR 6.1–9.0%   jackknife SE 1.4%       │
│   5 attempts · 10 unique pairs                                        │
│   [ⓘ What the error bars mean]                                        │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 4. Pairwise heat maps       [CER] [WER]   [ symmetric | directional ]│
│   (robust color scale; hover for exact values and edit counts)        │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 5. Per-attempt consistency   sort ▾ [mean CER | mean WER | vs cons.] │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 6. Consensus   🅰 Representative  ⚙ Deterministic  🤖 LLM (generate) │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 7. Consensus comparison table                                       │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 8. Difference inspection      A: [Run 2·1 ▾]  B: [Consensus ▾]      │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 9. Full set vs. filtered  (side-by-side, §21)                       │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 10. Research summary  (§30 narrative, copyable)                     │
├───────────────────────────────────────────────────────────────────────┤
│ ▸ 11. Export  [CSV bundle] [JSON] [Figures] [Consensus text] [All ZIP]│
├───────────────────────────────────────────────────────────────────────┤
│   Not saved — this analysis exists only in this session.              │
│   note: [excluded Run 4 — empty output          ]  [💾 Save analysis] │
└───────────────────────────────────────────────────────────────────────┘
```

**Heat map specifics (§8).** Same attempt ordering on both maps and in every table.
Both axes labeled with the short attempt label. Diagonal rendered as an explicit zero in
a neutral color. Sequential single-hue scale, low = light. To satisfy "a single extreme
value shall not obscure differences among the remaining pairs", the color domain is
**clipped at the 95th percentile of off-diagonal values** (with a minimum span), and
cells beyond the cap are drawn in a distinct "off-scale" hue with a legend note. The raw
value is always in the tooltip and always in the export, so the clipping is presentational
only. A "linear / robust scale" toggle lets the user see the unclipped version.

**Small-sample banners (§22).** N=2 → analysis runs, but a banner states that outlier
detection is not meaningful and uncertainty is not estimated. N=3 → analysis and consensus
run with a small-sample caveat. N≥4 → full feature set. Never display a confidence
interval that implies precision the sample size does not support.

**Linked selection (§19).** A single `focusAttemptId` field in the Zustand store drives
highlighting in both heat maps, the per-attempt table, and the diff selectors
simultaneously — one subscription, three consumers, no prop drilling.

### Component tree

```text
components/consistency/
  ConsistencyTab.jsx        # orchestration; owns the React Query calls
  AttemptSelector.jsx       # §3 checkbox list w/ metadata, health badges, inspect
  ComparisonSettings.jsx    # normalization profile + tokenizer, shows step list
  OverallStats.jsx          # §9/§10 headline figures with labeled variability
  HeatMap.jsx               # reusable CSS-grid matrix (D5); rendered twice
  PerAttemptTable.jsx       # §11 sortable table, outlier badges
  ConsensusPanel.jsx        # §13-§16 three consensus kinds, distinctly badged
  ConsensusComparison.jsx   # §17 table
  DiffViewer.jsx            # §18 side-by-side / inline + change categories
  FullSetComparison.jsx     # §21
  ResearchSummary.jsx       # §30 narrative, copy button
  ExportControls.jsx        # §26 download buttons
  SavePanel.jsx             # D11 save/note/unsaved indicator
```

Reuse the existing `shared/` widgets rather than inventing new ones: `Button`, `Alert`,
`Expander`, `Modal`, `TextArea`, `TwoColumn`, `Spinner`. Only `HeatMap.jsx` is a genuinely
new primitive.

### State

Zustand (`appStore.js`), following the existing naming style — a `consistency` slice
rather than a flat prefix:

```js
consistency: {
  selectedIds: [], normProfile: 'standard_historical', tokenizer: 'word_simple',
  consensusKind: 'deterministic', focusAttemptId: null, sortKey: 'meanCer',
  scaleMode: 'robust', diffA: null, diffB: null, saveNote: '',
}
```

Reports themselves are **not** in Zustand — they are React Query cache entries (D8),
keyed by the request. That keeps the store to user intent and leaves server data to the
layer built for it, matching how `useRoots` / `useProfiles` already work.

New hook: `hooks/useConsistency.js` — wraps the analyze, attempts, saved-list, and diff
queries.

---

## 8. Export (§26)

`backend/analysis/export.py`, served through `GET /api/consistency/export`, following the
conventions already set by `routers/export.py` and `core/export_utils.py` — including the
`Content-Disposition` header, which `backend/main.py:52` already exposes through CORS so
the browser can read the filename.

It builds a ZIP with a fixed layout, plus individual downloads for each part:

```
letter_042_consistency_20260726T140311/
  analysis.json                     # the complete §25 record — the machine-readable master
  README.txt                        # method definitions, terminology note, how to cite
  numerical/
    matrix_cer_symmetric.csv
    matrix_cer_directional.csv      # header states row=reference, col=hypothesis
    matrix_wer_symmetric.csv
    matrix_wer_directional.csv
    per_attempt_summary.csv
    overall_summary.csv
    consensus_comparison.csv
    outlier_diagnostics.csv
    pairwise_edit_counts.csv        # S/D/I and reference lengths per pair
  text/
    consensus_deterministic.txt
    consensus_llm.txt               # only when generated
    representative_attempt.txt
    normalized/attempt_<id>.txt     # the exact strings that were measured
    originals/attempt_<id>.txt
  figures/
    heatmap_cer.png  heatmap_cer.svg    # 300 dpi
    heatmap_wer.png  heatmap_wer.svg
  summary.md                        # the §30 narrative
```

CSV for statistics packages, JSON for programmatic reuse, PNG+SVG for publication. Every
file is derivable from `analysis.json` alone, which is the reproducibility anchor.

---

## 9. Ground-truth mode (§29) — design now, build later

Not implemented in this plan's phases, but the architecture must not preclude it:

- `TranscriptionAttempt.source_type` already carries `"reference"`, and a reference is structurally excluded from the replicate set (§29 final clause);
- a `designate_reference(attempt_id)` action and a `reference_attempt_id` field on the analysis record;
- `backend/analysis/metrics.py` is direction-aware, so `gt_cer = CER(reference → attempt)` needs no new math — only new labeling;
- ground-truth results render in a **visually distinct** panel with the accuracy vocabulary unlocked, and the narrative gains the §29 "relationship between internal consistency and measured accuracy" comparison (correlation of `mean_pairwise_cer` against `gt_cer` across attempts).

Reserving the field names and the `source_type` value now costs nothing and prevents a
schema migration later.

---

## 10. Dependencies

**Backend** (`backend/requirements.txt`):

| Package | Status | Action |
|---|---|---|
| `numpy>=1.21.0` | already declared | — |
| `matplotlib>=3.5.0` | already declared | — used for export figures (D5) |
| `rapidfuzz` | **not present** | **add** `rapidfuzz>=3.6` — pure wheels, no build step |
| `pandas` | **not present** | **do not add** — see below |
| `scipy` | installed transitively, undeclared | **do not use** |

**Frontend:** **no new dependencies.** The heat map is a CSS grid (D5); tables and the
diff viewer are plain React. `package.json` is unchanged.

So the entire feature costs **one** new dependency, ~2 MB.

**Why no pandas.** The Streamlit draft assumed pandas for tables and CSV writing. Neither
applies now: tables render in React from JSON, and CSV export is a dozen lines of
`csv.writer` from the stdlib. Adding pandas (~50 MB with its numpy/pytz/dateutil tail) to
a service that deploys on 512 MB, for string formatting, would be a poor trade. If a
future need for pandas appears it can be added then — nothing in the design depends on
its absence.

Memory note: the app runs on 512 MB with `SPACY_ENABLED=false`. `rapidfuzz` adds ~2 MB
and no runtime memory pressure; the numpy fallback's traceback matrix is the only
memory-sensitive path, and it is only reached when rapidfuzz is missing. Peak per pair is
bounded and released immediately. Worth a deploy-time smoke check on a long document.

Note that `requirements-core.txt` (the legacy Streamlit runtime) is **not** modified —
`legacy-streamlit/` receives none of this work.

---

## 11. Performance

| Scenario | Char-level cost per pair | Total (rapidfuzz) |
|---|---|---|
| 5 attempts × 3 k chars, 10 pairs | ~10–30 ms | **< 0.5 s** |
| 10 attempts × 5 k chars, 45 pairs | ~40–80 ms | **~2–4 s** |
| Pure-Python fallback, 5 × 3 k | ~10–20 s | unusable — hence D4 |

Word level is ~10× cheaper (fewer tokens). Mitigations: the two-layer cache (D8); an
explicit "Run analysis" action rather than recompute-on-every-keystroke; a spinner via
the existing `Spinner.jsx` when `n_pairs > 20`; and a soft warning above ~15 attempts.

One new consideration on this stack: the analyze endpoint is **synchronous** and holds a
uvicorn worker for its duration. At the numbers above that is fine (sub-second to a few
seconds). If document sets ever grow past ~20 attempts, move it to a background task with
a polling status endpoint rather than raising the request timeout. Not needed now; worth
knowing before someone tries it on 50 replicates.

---

## 12. Testing plan

New directory `tests/test_analysis/`, following the existing `tests/test_core/` layout.

**Unit — metrics** (`test_metrics.py`)
- Known-answer CER/WER against hand-computed examples ("kitten"/"sitting" → d=3).
- `d(A,B) == d(B,A)`; `S/D/I` role-swap identity across directions.
- `CER_sym` equals the harmonic mean of the directional rates.
- Empty/one-empty/both-empty edge cases; CER > 1.0 permitted and not clipped.
- **Cross-backend equivalence:** rapidfuzz and the numpy fallback produce identical S/D/I on a corpus of random and real strings.

**Unit — normalization** (`test_normalize.py`)
- Each step in isolation; profile step order; idempotence of each profile.
- Original text is never mutated (§4.1) — assert object identity of the input.

**Unit — matrices & statistics** (`test_matrices.py`)
- Diagonal exactly zero; exact symmetry (`M[i][j] is M[j][i]` value-equal, bitwise).
- `n_pairs == N(N−1)/2`; summary statistics use unique pairs only (§9) — a regression test that would fail if directional cells were double-counted.
- Jackknife SE against a hand-computed small case.

**Unit — outliers** (`test_outliers.py`)
- Synthetic group of 4 near-identical + 1 divergent → the divergent one is flagged.
- All-identical group (MAD = 0) → no flag, no crash.
- N=2 and N=3 → detection suppressed with the documented message.

**Unit — consensus** (`test_consensus.py`)
- Medoid selection on a constructed matrix; tie-break order.
- Deterministic consensus of 3 attempts differing at one token → majority token wins.
- Minority insertion is dropped; majority insertion is kept.
- **Reproducibility:** 50 repeated runs produce byte-identical output; shuffling the input list then restoring canonical order yields the same result.
- Identical inputs → consensus equals the input.

**Unit — health/duplicates** (`test_attempts.py`)
- Empty, near-empty, refusal text, and U+FFFD-heavy inputs are each classified correctly.
- Two identical texts from different runs remain **two** attempts with pairwise 0 (§24).
- True duplicate records (same run_id + output index) collapse to one.

**Unit — attempt collection** (`test_attempts.py`, continued)
- `collect_attempts()` on a fixture v2 JSON with 3 runs × 2 outputs → 6 attempts, correct run/output indices, metadata attached from the right run.
- String outputs and dict outputs both handled (D3).
- Harmonization records are surfaced with `source_type="consensus"` and are **not** included in the replicate set (§2.1).

**API** (`tests/test_api/test_consistency_router.py`, alongside the existing
`test_providers_backend.py`)
- FastAPI `TestClient`: `GET /api/consistency/attempts` returns §3.1 metadata; unknown root → 404; `< 2` selected → 400 (mirroring `routers/harmonization.py:43`).
- `POST /analyze` twice with identical bodies → byte-identical JSON (§27 over the wire, not just in the library).
- Attempt IDs sent in a shuffled order produce identical results (D10 server-side canonical sort).
- `POST /analyze` never writes: the document JSON's mtime and content are unchanged afterward (D11).
- `POST /save` then `GET /saved` round-trips; `DELETE` removes it.

**Integration** (`test_analysis_integration.py`)
- The full §32 acceptance scenario, driven headlessly through the `backend/analysis` package.
- Round-trip: report → JSON → reload → identical values.
- v2 schema 2.0 files still load after the 2.1 bump (extends `tests/test_data_integrity/test_schema_evolution.py`).

**Frontend.** There is **no JS test infrastructure on this branch** — no vitest, no
testing-library, and `package.json` has only `lint` alongside the build scripts. Adding a
test runner is out of scope for this feature and shouldn't be smuggled in with it. Two
consequences, stated plainly rather than papered over:

- component correctness is covered by `npm run lint` plus manual verification of the §32 acceptance scenario in the browser;
- the API contract is therefore where the real automated confidence lives, which is an argument for keeping the router tests thorough.

If a runner is added later, `HeatMap.jsx` (colour-domain clipping, diagonal, click-to-focus)
is the component most worth unit-testing first.

**Terminology guard** (extends `tests/test_hygiene/`)
- Grep `backend/analysis/` and `frontend/src/components/consistency/` for banned terms ("accuracy", "error rate", "correct transcription") outside the ground-truth module. Cheap, and it enforces §28 mechanically rather than by reviewer vigilance. Covering the JSX too means the guard reaches user-visible strings, which is where §28 actually matters.

---

## 13. Implementation phases

Each phase is independently reviewable and leaves the app working.

### Phase 1 — Measurement core (pure Python, no HTTP)
`backend/analysis/`: `normalize.py`, `metrics.py`, `matrices.py`, `attempts.py`. Add
`rapidfuzz>=3.6` to `backend/requirements.txt`. Full unit-test coverage.
**Delivers:** §4, §5, §6, §7, §9, §11, §23, §24, §27 (core).
**Exit:** `python -m pytest tests/test_analysis/` green; a matrix computable from two
strings in a REPL with no FastAPI import anywhere in the package.

### Phase 2 — Statistics & diagnostics
`uncertainty.py`, `outliers.py`, `report.py` (incl. the §30 narrative generator).
**Delivers:** §10, §12, §22, §25, §30.
**Exit:** a `ConsistencyReport` serializes to the §5.3 JSON and round-trips.

### Phase 3 — Consensus
`consensus.py` (medoid + `deterministic_vote_v1`), `diffing.py`.
**Delivers:** §13, §14, §15, §17, §18 (data model), §33.
**Exit:** reproducibility tests pass 50/50; consensus of a known 3-attempt fixture matches
a hand-derived expected string.

### Phase 4 — API layer *(new phase — no Streamlit equivalent)*
`backend/schemas/consistency.py`, `backend/routers/consistency.py`, router mounted in
`backend/main.py`; the analyze / attempts / diff endpoints and the D8 server-side memo.
**Delivers:** §4a; makes Phases 1–3 reachable.
**Exit:** `tests/test_api/test_consistency_router.py` green, including the
identical-request-identical-response and shuffled-ID checks.

### Phase 5 — Frontend
`components/consistency/` (12 components), `api/consistency.js`, `hooks/useConsistency.js`,
the `consistency` Zustand slice, the sixth entry in `TabBar.jsx` and `App.jsx`,
`HeatMap.jsx` and its CSS. `AnalysisTab.jsx` untouched.
**Delivers:** §3, §8, §19, §20, §21, §31.
**Exit:** the §32 acceptance scenario is performable end-to-end in the browser;
`npm run lint` clean.

### Phase 6 — Persistence & export
`analyses[]` + schema 2.1 in `backend/core/session_workspace.py` and
`backend/core/json_manager.py` (`save_analysis()` mirroring `save_summary()`); save /
saved / delete endpoints; `analysis/export.py` and `analysis/figures.py`; `SavePanel.jsx`
and `ExportControls.jsx`.
**Delivers:** §25, §26.
**Exit:** exported ZIP contains every §26 artifact; save → reload → identical values; 2.0
files still load; export works without saving.

### Phase 7 — LLM consensus (optional)
`analysis/llm_consensus.py` with `DEFAULT_CONSENSUS_*` prompts; two optional `consensus_*`
fields in `backend/core/profile_manager.py`, `ProfileEditorModal.jsx`, and all four
templates in `backend/profiles/`; the `/llm-consensus` endpoint; provider/model selector
reusing the harmonization pattern; "generated" badging.
**Delivers:** §16.
**Exit:** an existing profile with no `consensus_*` fields loads, validates, and generates
a consensus from the shipped defaults.

### Phase 8 — Ground-truth mode (deferred)
Reference designation, `gt_*` metrics, consistency-vs-accuracy comparison.
**Delivers:** §29.

**Suggested split.** Phases 1–3 are pure library work with no dependency on the rest of
the branch — they can start immediately and are fully testable in isolation. Phase 4 is
small and mechanical. Phase 5 is the largest single chunk and depends on 1–4. The phase
count grew from seven to eight purely because the API layer, previously implicit in "the
UI phase", is now its own reviewable unit — which is an improvement: it puts a tested
contract between the math and the interface.

---

## 14. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Pure-Python edit distance makes the feature unusable | High | D4 — rapidfuzz primary, numpy fallback; never ship pure Python on the hot path |
| Deterministic consensus produces poor output on structurally divergent attempts | Medium | Medoid backbone + strict-majority insertions + backbone-length deviation warning; documented limitations; versioned method id |
| Users read "3.8% CER" as accuracy | **High** — this is the spec's central concern | §28 terminology contract, mandatory methods note, hygiene test covering JSX strings, "what this does not measure" panel at the top of the tab |
| A saved analysis is mistaken for *the* analysis of a document | Medium | D11 — save is explicit and additive; every record carries `attempts_included`/`attempts_excluded` and an optional user note, so multiple saved analyses are self-documenting rather than ambiguous |
| `consensus_*` fields break existing profiles | Low | Fields stay out of `_REQUIRED_FIELDS`; absent → `DEFAULT_CONSENSUS_*` constants. Watch `ProfileEditorModal.jsx:84-85` — do not add client-side required checks |
| Sixth tab crowds the navigation | Low | Accepted for discoverability. `TabBar.jsx` uses a flex row with `tab-bar-inner`; a commit on this branch already addressed tab-bar scrolling, so check the six-tab row at ~1280 px during Phase 5 |
| Heat map colour scale hidden by one extreme pair | Medium | 95th-percentile robust clipping + off-scale hue + raw values in tooltip/export + linear-scale toggle |
| Schema 2.1 breaks existing files | Medium | Validators accept `{2.0, 2.1}`; array created on demand; schema-evolution test extended |
| **No frontend test infrastructure** | Medium | Stated openly in §12 rather than assumed away. Automated confidence lives in the router tests; component correctness is lint + manual §32 walkthrough. Do not bundle a test-runner migration into this feature |
| Synchronous analyze endpoint blocks a worker | Low | Sub-second at realistic N. Documented threshold (~20 attempts) at which to move to a background task rather than raise the timeout |
| Branch diverges from `main` while this is built | Medium | `main` is 2 commits ahead, touching files now under `legacy-streamlit/`. This feature adds nothing to `legacy-streamlit/`, so it contributes no new merge conflicts — but it does not resolve the existing ones either |
| 512 MB memory ceiling | Low | One new dependency (~2 MB); no pandas. Memory-heavy numpy fallback is rarely reached |

---

## 15. Decisions — resolved 2026-07-26

All six open questions are settled. Recorded here with their consequences; the body of
the document reflects them.

| # | Decision | Consequence (as revised for React/FastAPI) |
|---|---|---|
| 1 | **Its own tab**, not a sub-view of Analysis | D2 — sixth entry in `TabBar.jsx`, one line in `App.jsx`; `AnalysisTab.jsx` untouched |
| 2 | **Harmonic mean** `2d / (len_A + len_B)` as the symmetric score; **retain all scores internally** for export and later analysis | §6.2 + §6.2.1 — full `PairMetrics` (directional rates, S/D/I, lengths, word opcodes) returned by the API, persisted, and exported; not just the displayed symmetric value |
| 3 | Default **`standard_historical`**; **`diplomatic`** a first-class selectable option | §6.1 — three profiles ship; the selector is a visible control showing the step list, not a buried dropdown |
| 4 | **Jackknife only** for uncertainty, for now | §6.5 — bootstrap deferred; no RNG anywhere in the numerical pipeline; `uncertainty_method` stays a string so bootstrap can be added later without reinterpreting saved records |
| 5 | **Review, then decide to save** | D11 — `POST /analyze` is pure and never writes; `POST /save` is a separate call. Additive, deletable, export works unsaved |
| 6 | **New `consensus_*` profile fields**; do not overload harmonization | §6.10 — **two** optional YAML fields (`consensus_system_prompt`, `consensus_prompt`), matching the backend's current single-body convention rather than the legacy intro/closing pair. Falls back to `DEFAULT_CONSENSUS_*` constants, never to `harmonization_*` |

**Tab order confirmed 2026-07-26:** Consistency sits immediately after Analysis. Under the
React tab set — where Harmonization is no longer a tab, having moved into Transcription —
that places it between Analysis and Export:

```text
🚀 Start · 📤 Upload · 📝 Transcription · 🔬 Analysis · 📊 Consistency · 📦 Export
```

### What the migration changed about these decisions

Nothing was reversed. Five of the six carried over unaltered in substance; only #6's field
*count* changed, because the backend profile schema had already collapsed
`harmonization_intro`/`closing` into a single `harmonization_prompt`.

Three things got materially better:

- **D3** — the positional-reconciliation mechanism, the plan's largest correctness hazard, became unnecessary. Attempts are read straight from `runs[]`.
- **D5** — no charting dependency at all. A CSS-grid heat map is more interactive than the Altair plan *and* free; matplotlib moves server-side where §26 wanted the figures anyway.
- **Dependencies** — pandas dropped entirely. The feature costs one new package.

One thing got worse: there is **no frontend test infrastructure**, so component-level
automated testing is unavailable (§12).

**No open decisions remain.** Phase 1 can begin.

---

## 16. Requirements traceability

| § | Requirement | Where handled |
|---|---|---|
| 1 | Purpose, consistency ≠ accuracy | §2 terminology, §7 UI methods note |
| 2 | Document group, attempt/consensus/reference distinction | §5.1 `source_type`, D3 |
| 3 | Selection UI, include/exclude, outlier exclusion | §7 panel 1, D9 |
| 4 | Normalization, configurable, profiles | §6.1 |
| 5 | Pairwise CER, directional + symmetric + counts | §6.2 |
| 6 | Pairwise WER, directional + symmetric + counts | §6.2 |
| 7 | CER/WER matrices | §6.3 |
| 8 | Heat maps | §7, D5 |
| 9 | Overall statistics, unique pairs only | §6.4 |
| 10 | Uncertainty, labeled error bars | §6.5 |
| 11 | Per-attempt consistency scores | §6.6 |
| 12 | Outlier identification, diagnostic language | §6.7 |
| 13 | Consensus from selected attempts only | §6.9, §6.10 |
| 14 | Deterministic consensus | §6.9 |
| 15 | Medoid / representative | §6.8 |
| 16 | LLM consensus, distinct and labeled | §6.10, D7 |
| 17 | Consensus comparison table | §6.11 |
| 18 | Difference inspection | §6.12 |
| 19 | Sorting and linked diagnostic views | §7 |
| 20 | Workflow | §7 layout, Phase 5 |
| 21 | Full-set vs filtered | D9, §7 panel 9 |
| 22 | Small-sample behavior | §6.5, §6.7, §7 banners |
| 23 | Failed/degenerate transcriptions | §5.2 |
| 24 | Duplicates remain distinct | §5.2 |
| 25 | Provenance | §5.3 |
| 26 | Exportable results | §8, `GET /api/consistency/export` |
| 27 | Reproducibility | D1, D7, D8, D10, §12 tests (library **and** API level) |
| 28 | Terminology | §2, hygiene test over Python and JSX |
| 29 | Ground-truth mode | §9, Phase 8 |
| 30 | Research summary | §6 report, Phase 2 |
| 31 | Primary analysis outputs | §7 layout |
| 32 | Acceptance criteria | Phase 5 exit + integration test |
| 33 | Methodological principle | §2, §6.7, §6.9 |
| — | API surface | §4a |

---

## 17. Implementation notes and deferred issues

Recorded during implementation for later consideration. Nothing here blocks the
remaining phases; none of it has been acted on, in line with the instruction to
extend the branch rather than tidy it.

### 17.1 Pre-existing: `run_id` is never written

`backend/core/json_manager.py:96-113` builds its run record without a `run_id`
key, and nothing adds one afterwards — `append_run_to_v2_json` only appends.
But `save_harmonization` reads `run.get("run_id", "")` when mapping selected
outputs back to their runs
([json_manager.py:181-191](../../backend/core/json_manager.py#L181-L191)), so
`source_run_ids` on every stored harmonization is a list of empty strings.

Consequences for this feature — both already handled, neither requiring a fix:

- attempt identity comes from position (`r0:o1`), per D10, so nothing depends on `run_id`;
- duplicate-record detection (§24) falls back to a content fingerprint (timestamp, model, provider, outputs) instead of comparing ids.

**If it is ever fixed**, generate the `run_id` in `save_transcription_run` and
leave `collect_attempts` alone: it already prefers `run_id` when present and
carries it into provenance. Fixing it would also repair harmonization
provenance, which is arguably the more valuable outcome.

### 17.2 Deviation from the plan: `word_opcodes` omitted from `PairMetrics`

§6.2.1 lists `word_opcodes` among the retained per-pair fields. The
implementation omits it. The `/diff` endpoint (§4a) recomputes opcodes for the
one pair being inspected, on demand, so storing them for all *N(N−1)/2* pairs
would inflate the analyze response with data nothing reads — and the response
is serialized to JSON over HTTP on every settings change.

Every other retained field is present: directional rates, S/D/I counts, both
lengths, and the symmetric score. Revisit only if a view needs opcodes for
*all* pairs at once; per-pair recomputation is a few milliseconds.

### 17.3 Naming: the package shadows its own submodule

`backend/analysis/__init__.py` re-exports the `normalize()` function, which
shadows the `normalize` submodule. `from backend.analysis import normalize`
therefore yields the *function*; reaching the module needs
`from backend.analysis.normalize import ...` or `importlib.import_module`.

Documented in the package docstring and at the one test that hit it. Worth
knowing when wiring the router in Phase 4. Renaming the export (e.g. to
`normalize_text`) would remove the trap at the cost of a less natural public
API; deferred rather than decided.

### 17.4 Pre-existing: 22 suite failures from the migration

The full suite reports 22 failures on this branch **before** any of this work:
confirmed by stashing the new files and re-running (22 failed / 396 passed
baseline; 22 failed / 561 passed with Phase 1 added — the same 22, plus 165 new
passes).

All 22 assert a repository layout the migration changed:

- `test_app_integration.py` / `test_validation_suite.py` — require `config.py`, `state_manager.py`, `ui_components.py` … at the repository **root**, and glob the root non-recursively for a Python-file count, now finding only `main.py`;
- `test_core/test_batch_transcription.py`, `test_providers.py`, `test_security/test_privacy_controls.py` — exercise legacy Streamlit modules and UI files.

These are the migration's to resolve — either by repointing the assertions at
`backend/` and `legacy-streamlit/`, or by retiring the tests that only describe
the old layout. Flagged here so a future green-suite goal is not mistaken for a
regression introduced by this feature.

### 17.5 Consensus surface forms come from the normalized text

§6.9 step 7 specifies that the emitted surface form should be "the winning
attempt's **original** token", with voting on normalized tokens. The
implementation emits the normalized token instead.

Under the two profiles that matter this is not a difference: `diplomatic`
applies only Unicode composition, and `standard_historical` normalizes
whitespace and line-break hyphenation while preserving case and punctuation —
so a normalized token *is* the original token. Under the aggressive
`normalized` profile the consensus comes back case-folded and stripped of
punctuation.

Recorded as a documented limitation on every `ConsensusResult` rather than
hidden. Mapping voted tokens back to original offsets across N attempts is real
work for a benefit confined to one profile that is explicitly a diagnostic
lens, not a transcription-production setting. Revisit if anyone wants to
publish a consensus produced under `normalized`.

### 17.6 Addition beyond the plan: spacing-difference merge in the diff viewer

§18 requires the user to be able to tell whether a difference arises from
*spacing*. A token-level alignment cannot express this directly: `into` against
`in to` becomes a replace block plus an insert block, which would be reported
as a spelling variant plus an inserted word.

`diffing._merge_spacing_runs` therefore post-processes the segments: whenever a
run of consecutive changes has identical text on both sides once whitespace is
removed, the run is merged and relabelled as a single spacing difference. This
is additive — the merge only fires on exact concatenation equality, so it can
never mask a substantive change.

### 17.7 Backend tests must isolate `sys.path` and `sys.modules`

Six top-level module names exist under **both** `backend/` and
`legacy-streamlit/`: `json_manager`, `session_workspace`, `logging_config`,
`audio_pairing`, `providers`, and `main`. Because `pytest.ini` sets
`pythonpath = . legacy-streamlit`, whichever copy is imported first wins for the
whole session.

The backend's flat-import convention makes this unavoidable for any test that
touches a router: `routers/consistency.py` imports `core.json_manager`, which
does a bare `from session_workspace import ...`, which needs `backend/core` on
the path.

Adding those paths at module scope **breaks other test modules** — it produced
three collection errors in `test_audio_pairing.py`, `test_failure_modes.py` and
`test_privacy_controls.py`. The working pattern, in
`tests/test_api/test_consistency_router.py::backend_env`, is a module-scoped
fixture that:

1. snapshots `sys.path` and `sys.modules`;
2. evicts every cached module whose top-level name the backend also provides (enumerated from the directory listing, not hard-coded);
3. inserts `backend/` and `backend/core/`;
4. imports the router;
5. restores both snapshots on teardown.

Any future backend router test should reuse this fixture rather than reinvent
it. `test_providers_backend.py` solves the same problem differently, by loading
modules from file paths under private `sys.modules` keys with stubs; either
works, but the two should not be mixed within one module.

### 17.8 Addition beyond §4a: `GET /consistency/options` and `/consistency/attempt`

§4a lists eight endpoints. Phase 4 implements the three in scope (`attempts`,
`analyze`, `diff`) plus two the UI cannot work without:

- **`GET /consistency/options`** — the normalization profiles with their exact step lists, the tokenizers, and the metric definitions. §4.2 requires the default profile be "clearly documented" and §7 shows the step list beneath the selector; without this the client would have to hard-code them and drift.
- **`GET /consistency/attempt`** — one attempt's full text. §3.1 says the selection list need not show the text *but the user must be able to inspect it before deciding*, and `attempts` deliberately omits text to keep the list small.

Both are read-only and deterministic.

### 17.9 `analysis_id` is stable across identical analyze requests

The D8 memo caches the whole response, so two identical `POST /analyze` bodies
return an identical payload — including `analysis_id` and `created_at`. That is
the intended reading of an idempotent pure computation and is what makes the
§27 over-the-wire test exact.

The consequence for Phase 6: the id in an analyze response is **provisional**.
`POST /consistency/save` should mint a fresh `analysis_id` at save time rather
than trusting the one it is handed, otherwise two users saving the same analysis
of the same document would write records sharing an id.

### 17.10 ~~Open defect~~ **Fixed 2026-07-27**: outlier flags on trivially small disagreement

Found by running the Phase 4 demo, not by a test. Given five attempts where four
are byte-identical and one differs by a single punctuation mark (`.` versus `!`),
the detector flags **both** that attempt and the genuinely divergent one:

```text
median CER 0.016 | outliers: ['r2:o0', 'r4:o0']
```

The mechanism is correct but the outcome is not useful. With four identical
attempts the MAD is zero, so scoring falls back to the ratio rule (§6.7 step 3);
against a group median of ~0 even a one-character difference is a large *ratio*.
§12 asks for attempts "substantially different from the group", and 1.6%
character disagreement is not substantial by any practical reading.

**Proposed fix** — a minimum absolute floor, checked before the ratio rule: do
not flag an attempt whose median disagreement is below some small absolute
threshold (on the order of 0.02 CER / 0.05 WER), however large the ratio. This
only ever removes flags, so it cannot suppress a real outlier, and it leaves the
MAD path untouched.

**Implemented 2026-07-27** as §6.7 step 6, with `MIN_ABSOLUTE_CER = 0.02` and
`MIN_ABSOLUTE_WER = 0.05`. The floored attempt records why it was not flagged,
and the report's method note says a floor was applied.

**A second, more serious defect surfaced while fixing it.** Building the test
fixture revealed that a group of *byte-identical* attempts plus one wildly
divergent attempt produced **no flag at all**: with the median and MAD both
zero, the old code took an "every attempt agrees, nothing can deviate" branch
and returned all-zero scores. That is the single clearest outlier case there is,
and it was silently invisible. Fixed as §6.7 step 4 (`METHOD_ABSOLUTE`).

Both are covered by tests, including one asserting that the ratio rule *alone*
would still flag the 1% case — so the floor is demonstrably doing the work
rather than the fixture having gone slack.

### 17.11 Phase 5: save and export controls (now delivered in Phase 6)

§31's list of primary outputs includes export controls, and Phase 5 is listed as
delivering §31. The tab implements every other item on that list; **export and
save are not present**, because they are Phase 6's deliverable (`analyses[]`,
schema 2.1, `analysis/export.py`, the save/delete endpoints).

No placeholder UI was added for them — an inert button is worse than an absent
one. The tab is otherwise complete against §3, §8, §19, §20 and §21.

### 17.12 Phase 5: pre-existing frontend lint failures

`npm run lint` reports **11 problems (10 errors, 1 warning)** on this branch,
all pre-existing, in `ProfileEditorModal.jsx`, `TranscriptionTab.jsx`,
`UploadTab.jsx` and `useColorize.js` — unused variables, a fast-refresh export
violation, and a `set-state-in-effect` error. Everything under
`components/consistency/`, plus the new API module, hook, store slice and the
two wiring edits, lints clean.

So "lint is clean" cannot be the gate for this project as it stands; "lint
introduces no new problems" is the workable standard until those 11 are dealt
with. `npm run build` succeeds.

### 17.13 Phase 6: `save_analysis` takes an unused `workspace` argument

`save_analysis(workspace, file_index, root, ...)` mirrors the signatures of
`save_summary` and `save_harmonization` alongside it, and like them it locates
the document through the **file index**, never through the workspace. The
parameter is therefore inert in all three.

Kept for symmetry rather than trimmed, since a future implementation that
creates a missing document record would need it — `save_transcription_run` uses
the workspace for exactly that. The consequence is that `POST
/consistency/save` declares a `get_workspace` dependency it does not use, which
a test must satisfy; noted in the router test fixture.

### 17.14 Phase 6: one unreproducible suite reading

A single full-suite run reported **23 failed / 786 passed** rather than the
usual 22 / 787. That run was executed *concurrently with* `npm run build`, which
writes into `frontend/dist/`. Several failing tests in this suite walk the
repository tree and count files, so a race against the build is the likely
cause.

Three subsequent isolated runs were stable at 22 / 787. Recorded rather than
dismissed: if a 23rd failure reappears, start with the repo-scanning tests in
`test_app_integration.py` and `test_validation_suite.py`, and do not run the
suite alongside a frontend build.

### 17.15 No frontend test infrastructure

Restated from §12 because it is a standing constraint rather than a one-off:
`frontend/package.json` has no test runner. Component behaviour in Phase 5 will
rest on `npm run lint` plus a manual §32 walkthrough, with automated confidence
concentrated in the Phase 4 router tests.
