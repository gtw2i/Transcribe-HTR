# Transcribe-HTR

**LLM-assisted handwritten text recognition and analysis for historical manuscripts.**

Transcribe-HTR is a web application for transcribing handwritten historical documents using
vision-capable large language models. It supports **OpenAI**, **Google Gemini**, and
**Anthropic Claude** interchangeably, and goes beyond single-shot transcription: it can run the
same page through several models, measure how much they agree, reconcile them into a consensus
reading, extract named entities, and export the result as JSON, plain text, or a Word document with
the source image embedded.

It is built for archivists, digital-humanities researchers, and historians working with material
that off-the-shelf HTR engines handle poorly — idiosyncratic hands, non-standard spelling, and small
corpora that do not justify training a bespoke model.

- **Stack:** React 19 + Vite (frontend) · FastAPI (backend) · Python 3.10+
- **License:** [BSD 2-Clause](LICENSE)
- **Citation:** see [Citation](#citation) below

---

## Table of contents

- [Features](#features)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Usage walkthrough](#usage-walkthrough)
- [Architecture](#architecture)
- [Testing](#testing)
- [Citation](#citation)
- [License](#license)

---

## Features

**Transcription**
- Upload page images and transcribe them with any supported vision model.
- **Profiles** — reusable prompt sets tuned to a document type (Civil War manuscripts, Greek
  papyri, scientific tables, or your own). Stored as YAML in `backend/profiles/`.
- **Domain knowledge** — inject page-specific context (names, places, terminology) into the prompt
  at runtime to improve accuracy on proper nouns.
- **Automatic fallback** — if a model or provider fails, the request is retried down a configured
  chain of alternatives rather than failing outright.

**Consistency analysis**
- Run the same image through multiple models, or the same model multiple times, and compare.
- Character- and word-error-rate matrices between every pair of attempts, outlier detection, and a
  token-level consensus reading assembled from the attempts that agree.
- Surfaces *where* the models disagree, which is usually where a human should look first.

**Harmonization and summarization**
- Reconcile several transcriptions of one page into a single authoritative text.
- Generate a document-level summary across a page set.

**Analysis and export**
- Named-entity recognition with inline colorized highlighting.
- Export a single document or a whole set as JSON, plain text, or DOCX (with the source image
  embedded). Multi-document exports are bundled as a ZIP.

---

## Quick start

### Prerequisites

| | Version | Notes |
|---|---|---|
| Python | 3.10+ (3.11 recommended) | |
| Node.js | 22+ | required by Vite 8 |
| API key | at least one | OpenAI, Google Gemini, or Anthropic |

### 1. Clone and configure

```bash
git clone https://github.com/gtw2i/Transcribe-HTR.git
cd Transcribe-HTR
cp .env.example .env      # then edit .env and add at least one API key
```

You can skip the `.env` file entirely and paste an API key into the Upload tab at runtime instead.

### 2. Backend (port 8000)

```bash
conda create -n transcribe-htr python=3.11        # or: python -m venv .venv
conda activate transcribe-htr

pip install -r backend/requirements.txt
python -m spacy download en_core_web_sm       # optional — enables NER

cd backend
python run.py                                 # → http://localhost:8000
```

Interactive API docs are served at <http://localhost:8000/docs>.

### 3. Frontend (port 5173)

In a second terminal:

```bash
cd frontend
npm install
npm run dev                                   # → http://localhost:5173
```

Open <http://localhost:5173>. Vite proxies `/api/*` to the backend on port 8000, so there is no
CORS configuration to do in development.

> **Windows note:** use `python -m pytest` rather than bare `pytest` — the `pytest` script is often
> absent from `PATH` even when the package is installed.

### Running as a single process

For a production-style run, build the frontend first and let FastAPI serve it:

```bash
cd frontend && npm run build && cd ..
cd backend && python run.py
```

The backend detects `frontend/dist/` and serves the compiled SPA at `/` alongside the API at
`/api/*`, on one origin.

Two constraints apply to any such run:

- **Run exactly one process.** Sessions are held in an in-process dictionary, so multiple workers
  without sticky routing will reject roughly half of all requests. Keep uvicorn at a single worker.
- **Uploads are ephemeral.** Session workspaces live on the local filesystem under the system temp
  directory. They are not durable storage; uploaded images and transcriptions are lost when the
  workspace expires, and users are prompted to start a new session.

---

## Configuration

All environment variables are optional. See [.env.example](.env.example).

| Variable | Default | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | — | Pre-fill the OpenAI key |
| `GOOGLE_API_KEY` | — | Pre-fill the Gemini key |
| `ANTHROPIC_API_KEY` | — | Pre-fill the Anthropic key |
| `SESSION_SECRET_KEY` | random per start | Signs the session cookie. **Set this in any deployment** — otherwise every restart invalidates all sessions |
| `SPACY_ENABLED` | `true` | Set `false` to skip loading the spaCy NER model (saves ~500 MB RAM) |
| `MODEL_FALLBACK_ENABLED` | `true` | Set `false` to disable automatic model/provider fallback |
| `VERBALIZE_ENABLED` | `true` | Backend text-to-speech flag. The TTS UI is separately hard-disabled in [`frontend/src/featureFlags.js`](frontend/src/featureFlags.js) |

Further defaults — active profile, temperature, token caps, fallback chain — live in
[`backend/core/config.py`](backend/core/config.py).

---

## Usage walkthrough

The app is organized as six tabs, worked left to right.

**1. 🚀 Start** — orientation and getting-started notes.

**2. 📤 Upload** — drag in one or more page images (PNG/JPG). Enter an API key here if you did not
set one in `.env`. Uploaded files are grouped into *documents*; each image becomes a page under a
document root.

**3. 📝 Transcription** — pick a provider, a model, and a profile, optionally add domain knowledge
(for example: *"Letters from the 41st Ohio Infantry. Recurring names: Hazen, Wiley, Kimberly."*),
then transcribe. Run it more than once, or against different models, to build up several attempts
for the same page. Harmonization and summarization live at the bottom of this tab.

**4. 🔬 Analysis** — run named-entity recognition over a transcription and view the text with
entities colorized inline.

**5. 📊 Consistency** — the distinguishing feature. With two or more attempts on a page, this tab
shows pairwise CER/WER matrices, flags outlier attempts, and builds a token-level consensus
transcription. Disagreement between models is a useful proxy for passages a human should verify.

**6. 📦 Export** — download the current document or the whole set as JSON, TXT, or DOCX. Several
documents are bundled into a ZIP. DOCX exports embed the source image alongside the text.

A worked example: upload a letter scan, transcribe it three times with Gemini, GPT, and Claude, open
**Consistency** to see the three readings compared token by token, accept the consensus text, then
export to DOCX for editing.

---

## Architecture

```text
backend/                        FastAPI application
  main.py                       app, middleware, router mounts, static SPA serving
  run.py                        convenience launcher
  dependencies.py               DI roots: get_workspace(), get_file_index()
  routers/                      one module per feature, all mounted at /api
  engines/                      business logic — no FastAPI imports
  analysis/                     CER/WER metrics, consensus, outliers, diffing
  providers/                    OpenAI / Gemini / Anthropic abstraction
  schemas/                      Pydantic request & response models
  core/                         config, fallback, export, session workspace
  profiles/                     YAML transcription profiles

frontend/src/                   React + Vite single-page app
  api/                          axios wrappers, baseURL '/api'
  hooks/                        React Query hooks for server data
  store/appStore.js             Zustand — all client state
  components/                   one directory per tab
  styles/                       plain CSS with design tokens
```

**Design notes**

- *Engines are pure.* Engine classes take plain arguments and return plain dicts; only routers
  import FastAPI. This keeps the transcription and analysis logic usable from notebooks and scripts
  as well as from the API.
- *Providers are interchangeable.* Every provider module returns the same dict shape, so
  downstream code never branches on which vendor produced a transcription.
- *State.* Zustand holds client state, React Query holds server data. There is no router — the
  active tab is a store field.
- *Sessions.* A signed cookie identifies a per-session server-side workspace directory.

---

## Testing

```bash
pip install -r requirements-dev.txt

python -m pytest                            # full suite
python -m pytest tests/test_analysis/       # consistency-analysis unit tests
python -m pytest tests/test_api/            # API router tests
python -m pytest --cov=backend --cov-report=html
```

---

## Citation

If you use this software in a publication, presentation, or project, please cite:

> G. West, J. F. Wallin, A. Fialka, M. I. Swindall, J. Dyson, R. Sherridan, and J. H. Brusuelas.
> (2025). "An Application for LLM-Powered Document Transcription with Interactive Tools for Textual
> Analysis." *Past Meets Future 2025 Workshop.*

Machine-readable metadata is in [CITATION.cff](CITATION.cff); GitHub's "Cite this repository"
button will generate BibTeX or APA from it.

---

## License

BSD 2-Clause. See [LICENSE](LICENSE).
