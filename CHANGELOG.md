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
- **Remove document** (✕ on each card in the Upload tab;
  `DELETE /api/files/{root}`). The document's files are moved to
  `<workspace>/trash/<timestamp>/`, not deleted outright.
- Document JSON, uploads and user profiles are written atomically, so a crash
  mid-save cannot corrupt them.
- **Remembered API keys** (desktop app only):
  - The keys are kept per user account, and the "Remember my API keys" box is
    on by default.
  - Storage is Windows Credential Manager on Windows. Elsewhere it is an
    owner-only file, until the macOS builds are signed.
  - Endpoints: `GET/PUT/DELETE /api/settings/keys` (desktop launch token
    required, otherwise 404) and `GET /api/app-info`.
- **Desktop launcher** (`desktop/`): runs the backend in-process and shows
  the UI in a native window (WebView2 / WKWebView), falling back to the
  browser.
  - One instance per user: a second launch focuses the open window.
  - Downloads go through a native Save dialog.
  - Asks before quitting during a batch.
  - Check modes: `--smoke-test`, `--self-check`, `--window-check`.
  - New in the UI:
    - A "Your data on this computer" card: open the documents folder, open
      the log folder, copy diagnostics.
    - "Show in folder" after saving an export.
- CI runs the launcher with a real native window on Windows and macOS.
- **Desktop installers:**
  - Windows: Inno Setup `.exe` (per-user or all-users, WebView2 bootstrapper, uninstall keeps user data unless you choose otherwise).
  - macOS: Apple Silicon `.dmg`.
  - Built by `scripts/build_desktop.py` from hashed per-platform dependency locks.
  - CI installs each one on a clean machine and checks the installed app.
- Signing hooks for Windows and macOS, off until credentials are configured.
- Placeholder app icons. Permanent identifiers: bundle ID `org.transcribe-htr.app` and installer AppId.
- `docs/development/DESKTOP.md` developer guide.
- **Desktop local-server hardening** (`TRANSCRIBE_HTR_LAUNCH_TOKEN`):
  - Requests need the per-launch token.
  - Foreign `Host` headers are rejected.
  - API docs and the dev CORS origins are turned off.

- **Image viewer on the Analysis tab** for comparing a page with its transcription:
  - Rotate left or right.
  - Zoom with buttons, the mouse wheel (toward the cursor) or a double-click.
  - Drag to move the page.
  - Fit, Width and 100% views, plus Reset.
  - Keyboard shortcuts: arrows, +/−, R, 0.
  - The view is remembered per document.
  - **Save rotation** permanently turns the stored page upright (`POST /api/files/{root}/rotate`), so thumbnails and future transcriptions use it. Original files and existing transcriptions are untouched.

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
- After a restart, or on switching documents, the Analysis tab offered only one transcription per page. Each transcription in a batch is saved as its own run, but only the last run was restored. All saved transcriptions are now restored, in the same order the Consistency tab uses.
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
