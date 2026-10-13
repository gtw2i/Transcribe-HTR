# Changelog

All notable changes to Transcribe-HTR are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/). The version number lives in
[`VERSION`](VERSION).

## [Unreleased]

Work toward a turnkey Windows/macOS desktop app. See
[docs/development/DESKTOP_PLAN.md](docs/development/DESKTOP_PLAN.md).

### Added
- `backend/core/app_paths.py` is the single source of filesystem locations.
  It covers bundled resources and per-user, local data/log/cache directories.
  New overrides are `TRANSCRIBE_HTR_DATA_DIR` and `TRANSCRIBE_HTR_CACHE_DIR`.
- `VERSION` file, `CHANGELOG.md`, and a test that keeps every version string
  in step.
- CI runs on Windows and macOS (Apple Silicon), and on PRs into feature
  branches.
- **Persistent workspace mode** (`TRANSCRIBE_HTR_PERSISTENT_WORKSPACE=true`,
  used by the desktop app):
  - One private workspace in the user's data directory, so documents and
    results survive restarts.
  - Files placed in the folder appear on the next load.
  - Re-uploading a file name creates a new document (`page-1`) instead of
    replacing the existing one.

### Changed
- **Logs** moved from `./logs` (relative to wherever the server started) to the
  per-user log directory:
  - Windows: `%LOCALAPPDATA%\Transcribe-HTR\Logs`
  - macOS: `~/Library/Logs/Transcribe-HTR`
  - Linux: `~/.local/state/Transcribe-HTR/log`

  `TRANSCRIBE_HTR_LOG_DIR` still overrides it.
- The **TTS audio cache** moved from `./tmp/audio` to the per-user cache
  directory.
- **Profiles** are now in two layers:
  - Profiles shipped in `backend/profiles` are always read-only and appear
    as templates (clone them to customise).
  - Profiles you create are saved in your per-user data directory.

  `greek_papyrus_htr` therefore becomes a template.
- HEIC/HEIF is no longer offered as an upload type, because it never worked.
  Supporting it needs a codec plugin whose licensing is still under review.
- `backend/run.py` loads `<repo>/.env` when it exists.

### Fixed
- Saving a profile from the UI always failed with HTTP 422 (payload shape
  mismatch).
- "Named Entities" colorization crashed on matplotlib 3.9+ (`cm.get_cmap`
  was removed).
- TIFF uploads were accepted by the UI but rejected on save. 16-bit TIFFs
  are now rescaled instead of washed out, and EXIF rotation is applied.
- Logs did not redact `anthropic_api_key` and other key-like fields.
- The server crashed at startup when the working directory was not writable.

### Removed
- spaCy, together with `SPACY_ENABLED` and the unused code paths that loaded
  it. NER is done by the LLM providers.

### Security
- Profile slugs are validated (`^[a-z0-9_-]{1,64}$`). A crafted slug could
  previously write or delete `.yaml` files outside the profiles directory.
- `SessionWorkspace.cleanup_session` can no longer delete anything outside
  its own session directory.

## [2.0.0] - 2026-07-29

First public release: React + FastAPI HTR app with OpenAI, Gemini and
Anthropic providers, harmonization, NER, summarization, consistency analysis
and JSON/TXT/DOCX export.
