# CLAUDE.md — Transcribe-HTR

Handwritten text recognition (HTR) app supporting OpenAI, Gemini, and Anthropic
(Claude) vision models. React + FastAPI is the only application in the tree; the
original Streamlit prototype was removed for the public release.

**Naming:** the product is **Transcribe-HTR** and the GitHub repository is
`Transcribe-HTR`.

---

## Running the app

**Backend** (FastAPI, port 8000):
```bash
cd backend
python run.py
# or: python -m uvicorn main:app --reload --port 8000
```

**Desktop app from source** (native window; needs a built frontend):
```bash
pip install -r desktop/requirements.txt         # pywebview, truststore
cd frontend && npm run build && cd ..
python desktop/launcher.py                      # or --smoke-test / --self-check / --window-check
```
The launcher (`desktop/launcher.py`) runs uvicorn in-process on a random
127.0.0.1 port and sets `TRANSCRIBE_HTR_PERSISTENT_WORKSPACE` and a per-launch
`TRANSCRIBE_HTR_LAUNCH_TOKEN` before importing `main`. `desktop/bridge.py` is
the `window.pywebview.api` surface (downloads, open folder, diagnostics).
Plan and status: `docs/development/DESKTOP_PLAN.md`.

**Frontend** (React/Vite, port 5173):
```bash
cd frontend
npm run dev
```

Environment variables (all optional):
```bash
OPENAI_API_KEY=sk-...          # pre-fill OpenAI key
GOOGLE_API_KEY=...             # pre-fill Gemini key
ANTHROPIC_API_KEY=sk-ant-...   # pre-fill Anthropic (Claude) key
VERBALIZE_ENABLED=false        # hide TTS tab (default: true; UI also hard-disabled via featureFlags.js)
SESSION_SECRET_KEY=...         # signs session cookies (auto-generated if unset)
MODEL_FALLBACK_ENABLED=false   # disable automatic model/provider fallback (default: true)
```

## Installing dependencies

**Backend:**
```bash
pip install -r backend/requirements.txt        # THE runtime file
pip install -r requirements-dev.txt            # dev/test tools
```

NER is done by the LLM providers (`engines/ner_engine.py`); there is no
spaCy dependency.

**Frontend:**
```bash
cd frontend && npm install                     # Node 22+ required by Vite 8
```

Python 3.11 recommended (floor is 3.10, declared in `pyproject.toml`). Conda:
```bash
conda create -n transcribe-htr python=3.11
conda activate transcribe-htr
pip install -r backend/requirements.txt
```

## Running tests

```bash
python -m pytest                                   # all tests
python -m pytest tests/test_analysis/              # consistency analysis
python -m pytest tests/test_api/                   # API tests
python -m pytest --cov=backend --cov-report=html   # with coverage
```

`pytest.ini` sets `pythonpath = . backend backend/core backend/engines`, which
mirrors the `sys.path` setup in `backend/main.py`. That is what lets tests use
the same flat module names the backend uses internally (`from config import
...`, `from logging_config import ...`).

`tests/conftest.py` points the per-user data/log/cache directories at a temp
dir for the whole run, so tests never write into the repo or your profile.

The suite passes fully only with `backend/requirements.txt` installed. Tests
self-skip rather than fail when a declared dependency is absent, so a partial
environment reports passes plus skips — check the skip reasons (`-rs`) before
trusting a green run. The usual culprits are `rapidfuzz` (10 metrics tests) and
`python-multipart` (the router-mounting test).

Use `python -m pytest` rather than bare `pytest` — on Windows the `pytest`
script may not be on PATH even when the package is installed.

---

## Architecture

### Backend (`backend/`)

```
backend/
  main.py                     # FastAPI app, CORS, session middleware, router
                              #   mounts, and the static SPA catch-all (LAST)
  run.py                      # dev launcher (python run.py); loads <repo>/.env
  dependencies.py             # FastAPI DI: get_workspace(), get_file_index()
                              #   NB: sessions live in an in-process dict —
                              #   the app must run as a SINGLE worker/machine
  requirements.txt            # THE runtime dependency list

  routers/                    # one file per feature group, all mounted at /api
    session.py                # session init, file upload
    files.py                  # file index, upload, image serving
    transcription.py          # POST /transcribe
    harmonization.py          # POST /harmonize
    consistency.py            # multi-attempt CER/WER analysis + export
    summarize.py              # POST /summarize (document summary, separate from harmonization)
    colorize.py               # POST /colorize (NER highlighting)
    ner.py                    # POST /ner
    tts.py                    # POST /tts
    profiles.py               # GET/POST/PUT/DELETE /profiles
    models.py                 # POST /models (live model list for a provider)
    export.py                 # GET /export (json|txt|docx, single file or zip)

  analysis/                   # consistency analysis (pure, no FastAPI deps)
    metrics.py                # CER/WER via rapidfuzz
    consensus.py              # token-level consensus across attempts
    outliers.py               # flag divergent attempts
    diffing.py, matrices.py, normalize.py, report.py,
    attempts.py, uncertainty.py

  engines/                    # business logic, no FastAPI deps
    transcription_engine.py   # image → text via API
    harmonization_engine.py   # N transcriptions → 1 consensus
    summary_engine.py         # transcription(s) → document summary
    ner_engine.py             # named-entity recognition
    colorization_engine.py    # HTML entity colorization
    tts_engine.py             # text → audio

  schemas/                    # Pydantic request/response models
    common.py                 # HealthResponse, shared types
    transcription.py          # TranscribeRequest, TranscribeResponse
    harmonization.py
    summarize.py              # SummarizeRequest, SummarizeResponse
    ner.py
    tts.py

  providers/                  # AI provider abstraction — OpenAI, Gemini, Anthropic
    gemini_provider.py        # Gemini API calls + model list fetch
    openai_provider.py        # OpenAI API calls, pass1/pass2 NER, model list fetch
    anthropic_provider.py     # Anthropic (Claude) API calls, pass1/pass2 NER, model list fetch
    __init__.py               # fetch_model_list()/filter_model_list() public API, re-exports per-provider fns

  core/                       # shared utilities
    app_paths.py              # THE source of filesystem locations: bundled
                              #   resources + per-user data/log/cache dirs
    app_version.py            # APP_VERSION, read from <repo>/VERSION
    image_utils.py
    config.py                 # constants and feature flags
    fallback.py               # model/provider fallback chain (MODEL_FALLBACK_ENABLED)
    retry_utils.py            # retry-with-backoff helpers used by fallback
    export_utils.py           # build json/txt/docx exports (single + zip)
    json_manager.py           # load/save the v2 per-document JSON record
    session_workspace.py      # per-session workspace directory helpers
    schema_utils.py           # shared NER/entity schema helpers
    resource_loaders.py       # provider API clients + profile prompt proxy
    ...

  profiles/                   # bundled YAML profiles (read-only templates)
  templates/                  # Jinja templates for TXT export
```

### Frontend (`frontend/src/`)

```
api/                          # thin axios wrappers per endpoint
  client.js                   # axios instance, baseURL='/api', withCredentials
  transcription.js, ner.js, harmonization.js, summarize.js, colorize.js,
  files.js, profiles.js, models.js, session.js, tts.js, settings.js

utils/download.js             # downloadFromApi(): native Save dialog via the
                              #   desktop bridge, else blob + <a download>

hooks/                        # react-query hooks
  useRoots.js, useImage.js, useProfiles.js, useModelList.js,
  useSession.js, useJsonData.js, useColorize.js
  useRememberedKeys.js        # desktop: sync key fields with the secret store
  useDesktopShell.js          # desktop: busy flag / browser-fallback heartbeat

store/
  appStore.js                 # Zustand — all client state (mirrors ss.* shape)

featureFlags.js                # hard UI toggles for not-yet-ready features (e.g. TTS_UI_ENABLED)

components/
  help/                       # StartTab — landing/getting-started page
  upload/                     # UploadTab
  transcription/              # TranscriptionTab (harmonization + summarization UI live here)
  analysis/                   # AnalysisTab (NER)
  consistency/                # ConsistencyTab (CER/WER matrices, consensus)
  export/                     # ExportTab (json/txt/docx)
  harmonization/              # HarmonizationTab — NOT routed in App.jsx; the UI
                              #   was folded into TranscriptionTab. Dead code.
  modals/                     # dialogs
  layout/                     # shell, nav, TabBar (6 tabs)
  shared/                     # reusable widgets (incl. FallbackNotice, PasswordInput)

styles/
  variables.css               # design tokens (primary: #ff4b4b, inherited from
                              #   the original Streamlit theme)
  base.css, layout.css, components.css

App.jsx                       # tab routing via Zustand activeTab (no React Router)
```

### Import layout (`backend/`)

`backend/` modules import each other by **flat name** (`from config import ...`,
`from logging_config import ...`) rather than by package path. This works
because `backend/main.py` inserts both `backend/` and `backend/core/` onto
`sys.path` before importing anything else, and `pytest.ini` mirrors that with
`pythonpath = . backend backend/core backend/engines`.

Consequence: `backend/main.py` must be imported with `backend/` as the working
directory — hence `backend/run.py` launching `main:app` (not `backend.main:app`)
and `pytest.ini` adding those paths explicitly. Changing the flat-import style
would require touching every module in `backend/`.

---

## Key design decisions

**React state**
- **Zustand** (`appStore.js`) for all client state
- **React Query** for server data (roots, images, profiles, model lists)
- No React Router — active tab is a Zustand field (`activeTab`)
- Vite proxy routes `/api/*` → `localhost:8000` (eliminates CORS in dev)
- `DOMPurify` sanitizes HTML from `/api/colorize` before `dangerouslySetInnerHTML`
- Plain CSS only — no Tailwind/MUI

**Session model**
Cookie-based session (`session` cookie, signed with `SESSION_SECRET_KEY`).
FastAPI `SessionMiddleware` stores per-session workspace path server-side.
`get_workspace()` and `get_file_index()` in `dependencies.py` are the DI roots.

**Filesystem locations**
Never build paths from `__file__` or the working directory — use
`core/app_paths.py`. Resources (bundled profiles, templates, entity schema,
frontend dist) resolve against the repo, or `sys._MEIPASS` when frozen.
Writable state goes to per-user, local (non-roaming) platformdirs locations
(`%LOCALAPPDATA%\Transcribe-HTR`, `~/Library/Application Support/Transcribe-HTR`),
overridable via `TRANSCRIBE_HTR_DATA_DIR` / `_LOG_DIR` / `_CACHE_DIR`. The
desktop app installs read-only and may be shared by several accounts.

**Profile system**
Two layers (`core/profile_manager.py`): bundled profiles in
`backend/profiles/*.yaml` are always read-only and reported as templates;
profiles users create go to `<user data>/profiles` and cannot shadow a bundled
name. Slugs must match `^[a-z0-9_-]{1,64}$` (they become filenames). Users
clone templates to get editable copies. `verbalize_enabled` in a profile
overrides the `VERBALIZE_ENABLED` env var.

**Provider routing**
`PROVIDER_DEFAULT = PROVIDER_GEMINI` in `config.py`. OpenAI, Gemini, and
Anthropic are all fully supported across transcription, harmonization, NER,
and summarization — every provider module returns the same dict shape so
downstream code is provider-agnostic. Model lists are fetched live on each
`POST /api/models` (no cache); `filter_model_list()` removes
non-transcription models before display.

**Model/provider fallback**
`core/fallback.py` (gated by `MODEL_FALLBACK_ENABLED`, default on) retries a
failed call against the next model/provider in
`PROVIDER_MODEL_LISTS_FALLBACK` / `PROVIDER_MODEL_DEFAULTS`, up to
`MAX_FALLBACK_ATTEMPTS`. Engines return `fallback_used` / `fallback_info` in
their result dicts; the frontend surfaces this via
`components/shared/FallbackNotice.jsx`.

**Summarization**
Document summarization is a standalone feature (`summary_engine.py` /
`routers/summarize.py` / `POST /api/summarize`), separate from harmonization.
It takes one or more transcription outputs for a root and produces a single
summary, saved into the document's v2 JSON via `json_manager.save_summary()`.

**Export**
`GET /api/export?format=json|txt|docx` builds per-document exports via
`core/export_utils.py`. A single processed document returns one file; multiple
documents are bundled into a ZIP. DOCX export embeds the source image.

**Consistency analysis**
`backend/analysis/` computes pairwise CER/WER across multiple transcription
attempts for one page, flags outliers, and builds a token-level consensus.
Exposed via `routers/consistency.py` and the 📊 Consistency tab. Design
rationale: `docs/development/CONSISTENCY_ANALYSIS_PLAN.md`.

**Engines are pure**
Engine classes (`TranscriptionEngine`, `NerEngine`, etc.) have no FastAPI
imports. Routers instantiate them; engines take plain args and return plain
dicts/objects.

**Serving the SPA**
`backend/main.py` mounts `/assets` and a `/{full_path:path}` catch-all that
falls back to `index.html`, guarded by `FRONTEND_DIST` existing. It **must stay
last** in the file — Starlette matches routes in registration order, so moving
it above the routers would shadow every `/api/*` endpoint. The catch-all
explicitly re-raises 404 for `/api/*` so API typos return JSON, not HTML.
`tests/test_operability/test_app_operability.py` guards this ordering.

---

## Config quick-reference

| Constant | Default | Notes |
|---|---|---|
| `ACTIVE_PROFILE` | `"default_htr"` | Default profile stem |
| `PROFILES_DIR` | `backend/profiles/` | Bundled (read-only) profiles, via `app_paths` |
| `PROVIDER_DEFAULT` | `"Gemini"` | Active provider at startup |
| `PROVIDERS` | `["OpenAI", "Gemini", "Anthropic"]` | All supported providers |
| `TEMPERATURE` | `1.0` | API temperature |
| `MAX_COMPLETION_TOKENS` | `40000` | Per-call token cap (OpenAI/Gemini) |
| `MAX_COMPLETION_TOKENS_ANTHROPIC` | `8192` | Anthropic requires a mandatory max_tokens |
| `MODEL_FALLBACK_ENABLED` | `true` | Override: `MODEL_FALLBACK_ENABLED=false` |
| `MAX_FALLBACK_ATTEMPTS` | `4` | Max model/provider fallback attempts |
| `VERBALIZE_ENABLED` | `true` | Backend flag; TTS tab is also hard-disabled via `frontend/src/featureFlags.js` (`TTS_UI_ENABLED`) |
| `TTS_DEFAULT_MODEL` | `"tts-1"` | Standard quality TTS |
| `TTS_DEFAULT_VOICE` | `"onyx"` | Dramatic male voice |
| `LOG_RETENTION_DAYS` | `30` | Declared but not enforced yet; logs go to the per-user log dir |

---

## Profiles

YAML fields (all required except `description`, `verbalize_enabled`, `template`):

```yaml
name:                        # display name in dropdown
description:                 # one-liner shown next to dropdown
template: true               # if present and true → read-only in UI
verbalize_enabled: true      # overrides VERBALIZE_ENABLED env var
system_prompt: |             # AI role/persona (keep brief)
transcription_prompt: |      # main prompt; must contain {}
harmonization_system_prompt: |
harmonization_intro: |
harmonization_closing: |
```

The `{}` in `transcription_prompt` is replaced with the user's domain-knowledge
text at runtime.

---

## Running it anywhere

There is no container or hosting config in the repo — the app is run from source.
Two invariants hold wherever it runs:

- **cwd must be `backend/`.** `main.py` adds `backend/` to `sys.path` only *after*
  uvicorn imports it, so the working directory is what makes `main:app`
  resolvable. `backend/run.py` handles this; do not switch to `backend.main:app`.
- **A single worker.** `dependencies.py` holds sessions in a process-local dict,
  so more than one worker (or any load balancing without sticky routing) will
  reject roughly half of all requests.

---

## Stale worktrees

Claude Code creates worktrees under `.claude/worktrees/`. These contain
machine-specific absolute paths and must not be committed (listed in `.gitignore`).
If git errors with "not a git repository: .../worktrees/...":

```bash
git worktree prune
rm -rf .claude/worktrees/
```
