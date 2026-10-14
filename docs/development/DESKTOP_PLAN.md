# Transcribe-HTR Desktop: turnkey Windows + macOS app

## Status (updated 2026-10-13)

**Branch:** `feature/desktop-app`, with work-in-progress commits pushed to GitHub. The throwaway spike is on `desktop/spike-packaging`, which is never merged.

**Tests:** 698 pass, 1 skipped on Windows (the POSIX-only file-permission test, which runs on macOS/Linux). The baseline before this work was 561. CI covers Linux (Python 3.10–3.12), Windows and macOS 14 (Apple Silicon).

**Progress against the plan:** Phases 0, 0.5 and 1 are done, apart from the hands-on checks listed under "Still to do". That is ahead of the timeline below, which allowed about 7 weeks for this much.

### Done

| Phase | Item | Notes |
|---|---|---|
| Setup | Branch, plan committed as an ADR, CI on `feature/**` plus a Windows/macOS matrix | |
| 0 | `core/app_paths.py`: one source for every path; per-user, local (non-roaming) data/log/cache directories | Multi-user safe. Fixes the startup crash when the working directory is not writable |
| 0 | Profiles split into read-only bundled templates and per-user profiles; slug validation | Closes a path-traversal hole. **Also fixes:** profile saving from the UI always failed (422) |
| 0 | spaCy removed (dead code, the biggest dependency) | |
| 0 | NER colorize crash on matplotlib ≥ 3.9 fixed; matplotlib off the startup path | |
| 0 | API-key log redaction covers every key field | |
| 0 | TIFF uploads work; 16-bit scans and EXIF rotation handled; HEIC dropped (licensing open item) | |
| 0 | `cleanup_session` can no longer delete outside its own session | |
| 0 | `.env` loaded in development; `VERSION` + `CHANGELOG.md` + version consistency test; stale docs fixed | |
| 0.5 | Packaging spike: PyInstaller + pywebview frozen builds pass smoke, self-check and window checks on Windows and macOS | **G1 = GO.** Results are in the Phase 0.5 section below |
| 1.1 | Persistent single-user workspace that survives restarts and rescans the folder on load | |
| 1.2 | Atomic writes (documents, uploads, profiles); uploads never overwrite; "Remove document" moves files to a trash folder | |
| 1.3 | Local-server hardening: per-launch token, auth cookie, Host allowlist, docs and CORS off in desktop mode | |
| 1.4 | Remembered API keys: `SecretStore` (Credential Manager, or an owner-only file), `/api/settings/keys` (desktop only), "Remember my API keys" option | |
| 1.5 | `desktop/launcher.py`. Features: in-process server on a random port, loading page, WebView2 check with browser fallback and heartbeat, per-user single instance (second launch focuses the open window), confirm-before-quit during a batch, std-stream redirect, truststore. Check modes: `--smoke-test`, `--self-check`, `--window-check`, `--version` | Verified from source on Windows (real window) |
| 1.6 | Download bridge: `save_from_api` with an allowlist, a native Save dialog, and streaming through a temp file; both export sites use `utils/download.js` | Bridge logic is unit-tested; the dialog itself is not yet clicked through by hand |

| 1.6 | Desktop-only UI: a "Your data on this computer" card (open the documents and log folders, copy diagnostics) and "Show in folder" after a save. The Print button is hidden. Key-storage wording, plain file input for the dropzone, reload wording | |
| 1 (CI) | A `desktop` CI job runs the launcher from source on `windows-latest` and `macos-14`: smoke test, self-check and a real native-window check. The window check covers UI rendered and authenticated, desktop UI shown, and the bridge busy flag reaching Python | **macOS verified in CI** (WKWebView, Apple Silicon) |

### Still to do

**Phase 1: hands-on checks**
- **Windows, done by hand on 2026-10-14:**

  | Check | Result |
  |---|---|
  | Document upload | ✅ |
  | API key entry and remembering | ✅ |
  | Full workflow with real keys (Gemini) | ✅ |
  | All exports through the native Save dialog | ✅ |
  | Confirm prompt when quitting during a batch | ✅ |
  | Documents persist across restarts | ✅ |
  | Data card | ✅ |

  - The diagnostics box could not be closed; it now has a "Hide diagnostics" button.
- **Windows, not yet checked:** a TIFF upload (covered by automated tests) and launching a second copy (covered by the single-instance tests, but not yet watched by hand).
- **macOS, by hand:** the same list. Deferred to Phase 4 QA because no Mac is available. The CI `desktop` job covers the automated part.

**Phase 2: Packaging (not started)**
- Real PyInstaller spec, building on the spike's spec, with the permanent bundle ID.
- Windows Inno Setup installer: per-user and all-users modes, WebView2 bootstrapper, uninstaller that keeps user data.
- macOS `.dmg`; app icons; pinned per-platform lock files; `scripts/build_desktop.py`.
- Signing hooks that do nothing until credentials are configured.

**Phase 3: Release pipeline (not started)**
- Tag-triggered `release.yaml`: version check, builds, frozen smoke test, window check, checksums, provenance attestations, draft GitHub Release.
- Update notice in the app.
- Bump the GitHub Actions versions (Node 20 deprecation).

**Phase 4: QA, documentation, beta (not started)**
- Clean-VM QA matrix, including a standard account, two users at once, and Smart App Control.
- Install guides with screenshots (unsigned first-run steps).
- `docs/development/DESKTOP.md`; README install section; beta with digital-humanities users.

### Decisions and open items

- **G2, code signing (decide by mid-December):** the recommendation is an Apple Developer membership before the beta, and a Windows signing decision based on what beta users run. See "Unsigned builds" below.
- **HEIC support:** `pillow-heif` bundles LGPL/GPL codecs, so a licensing review is needed before adding it.
- **Import of exports or project folders:** deferred. Today, files dropped into the workspace folder appear in the app.
- **Delete `desktop/spike-packaging`** once Phase 3's release workflow replaces it.

## Context

Today Transcribe-HTR runs from source. That means Python 3.10+, `pip install`, Node 22, `npm install`, and two terminals (FastAPI on :8000, Vite on :5173). The target users are digital-humanities researchers with low to intermediate coding experience, so that setup is a barrier.

**Goal.** Ship an app that is downloaded, double-clicked, and used, with no Python, Node or terminal. It runs on Windows 10/11 and on Apple Silicon Macs.

**Decisions already made by the user**
- **Window:** a native window that reuses the existing React UI.
- **Data:** a persistent single-user workspace. An import capability may come later; keep it simple for now.
- **Mac:** Apple Silicon only.
- **Code signing:** none for now, but it must be an easy, pluggable step to add later.
- **Process:** all work goes on a new branch, using strong software-engineering practice.
- **Multi-user:** the app must work on shared, multi-user computers. Each user's data stays in that user's own local directory (see "Multi-user computers and data locations").

**Review summary (why this is feasible).** The UI is only loosely tied to a browser:
- It uses a relative `/api` base URL.
- It has no router, no localStorage, no websockets or SSE.
- Images arrive as base64 JSON.

The backend, however, assumes it runs from source with `cwd=backend/`. Several issues block freezing it, and some are latent bugs today:

| Issue | Where |
|---|---|
| Log directory is cwd-relative and created at import time, so the app crashes when launched from Finder | `core/logging_config.py:29,42` |
| `tmp/audio` is cwd-relative | `engines/tts_engine.py:48`, `core/export_utils.py:571` |
| User profiles are written inside the app folder, and the slug is unvalidated (path traversal) | `core/config.py:69`, `routers/profiles.py` |
| Entity schema is loaded from outside `backend/` at import time | `engines/ner_engine.py:21` |
| Live NER colorize path is broken on matplotlib ≥3.9 because `cm.get_cmap` was removed | `core/transcription_utils.py:518,587` |
| spaCy is required but never called; it is the largest dead weight in the bundle | `resource_loaders.get_spacy_model`, `transcription_utils.colorize_ner` |
| `.env` is never loaded: there is no python-dotenv, despite what the README says | — |
| A new empty temp-dir session is created on every page load; `cleanup_session()` would `rmtree` the workspace's **parent** | `routers/session.py`, `session_workspace.py:593` |
| TIFF/HEIC uploads are accepted by the UI but rejected on save | `routers/session.py:41` |
| `run.py` launches `-m uvicorn --reload`, which is impossible in a frozen app | `run.py` |
| CI is Ubuntu-only and runs only for PRs into `main` | `.github/workflows/ci.yaml:5-7` |
| Versions are scattered across 5 places; there are no tags and no CHANGELOG | — |

---

## GUI options and tradeoffs

| Option | What the user sees | Effort | Pros | Cons |
|---|---|---|---|---|
| **A. Browser + local server** (launcher or tray) | Double-click opens a browser tab | Low | Most robust; no webview quirks | Feels like a website; closing the tab does not quit; needs a tray icon to quit; risk of multiple tabs |
| **B. pywebview native window** ✅ chosen | A real app window (WebView2 / WKWebView) | Low–Med | Reuses 100% of the React UI; Python-only toolchain; small shell; falls back to option A | Downloads, print and drag-drop need care; on Windows it depends on WebView2 (preinstalled on Win11 and most Win10); less polished updater and installer story |
| **C. Tauri + Python sidecar** | A real app window | Med–High | Good built-in installer, updater and signing tooling; small shell | Adds a Rust toolchain plus two build systems; sidecar process management; tauri:// origin vs cookies/CORS; same webview quirks as B |
| **D. Electron + Python sidecar** | A real app window | Med–High | Identical Chromium on all platforms; mature auto-update (electron-builder) | About 150 MB of extra Chromium; Node plus Python runtimes; heaviest to maintain |
| **E. Native rewrite (PySide6/Qt)** | A native widgets app | Very high (months) | No web stack at runtime | Rewrites about 3,900 lines of JSX and 1,340 of CSS, including the consistency heat map, diff viewer and colorized-HTML view; leaves two UIs to maintain; LGPL compliance |
| **F. Hosted web service** (not a desktop app) | A URL | Med plus ongoing operations | Zero install | Hosting cost; manuscript privacy; server-side API keys; sessions limited to a single worker; not "own your data" |

**Why B.** It gives an app-like feel at the lowest cost and keeps one UI codebase. Most of the work (path refactor, persistent workspace, security, packaging, CI) is shared with every other option. If B ever disappoints, migrating to C or D only replaces the thin launcher.

**Packaging tool.** Use **PyInstaller in onedir mode**. It is the most mature tool with pywebview, and onedir avoids onefile's slow temp extraction and antivirus false positives. Briefcase and Nuitka were considered; neither offers a decisive advantage here.

**Installers**
- Windows: Inno Setup with two modes, per-user (no admin) or all-users (admin). Details are in the multi-user section below. It checks for WebView2 and installs it via the bootstrapper if missing.
- macOS: an arm64 `.app` inside a `.dmg`.

---

## Multi-user computers and data locations

**Short answer:** yes. Each user's data lives in their own **local** (non-roaming) profile directory. One installed copy of the program can serve many users, and they never see each other's documents, keys or settings.

Today this is **not** the case. Workspaces go to the system temp directory and are thrown away; logs go next to the process's working directory; user profiles are written into the program folder, which all users share. Phase 0 and Phase 1 fix this.

### Program files vs. user data

| | Windows | macOS |
|---|---|---|
| **Program (read-only, shared)**: code, bundled profiles, UI | All-users install: `C:\Program Files\Transcribe-HTR\`<br>Per-user install: `%LOCALAPPDATA%\Programs\Transcribe-HTR\` | `/Applications/Transcribe-HTR.app` (shared by all accounts) |
| **User data (private, per user)**: workspace, user profiles, `workspace.json`, trash | `%LOCALAPPDATA%\Transcribe-HTR\` (e.g. `C:\Users\alice\AppData\Local\Transcribe-HTR\`) | `~/Library/Application Support/Transcribe-HTR/` |
| **Logs (per user)** | `%LOCALAPPDATA%\Transcribe-HTR\Logs\` | `~/Library/Logs/Transcribe-HTR/` |
| **Cache (per user, safe to delete)**: matplotlib font cache, TTS audio | `%LOCALAPPDATA%\Transcribe-HTR\Cache\` | `~/Library/Caches/Transcribe-HTR/` |
| **API keys (per user)** | Windows Credential Manager (the user's vault) | The user's login Keychain |

`app_paths.py` gets these from `platformdirs` with `roaming=False`. Choosing the *Local* rather than *Roaming* AppData matters for two reasons:
- On university domains with roaming profiles, multi-GB workspaces would otherwise be copied at every logon and logoff.
- AppData is never redirected into OneDrive, so the data is not affected by OneDrive folder redirection.

### Behaviour when several people use one machine

- **Privacy:** these directories are readable only by their owner by default. On Windows, the profile ACLs allow the user, SYSTEM and Administrators. On macOS, `~/Library` is 700. The fallback secret file is created owner-only (0600 / user-only ACL).
- **Simultaneous sessions** (Fast User Switching, or Remote Desktop on a lab server):
  - Each user runs their own process on a random port. Two users can therefore run the app at the same moment.
  - The per-launch token protects the API from *other logged-in users*. Without it, user B could call user A's server on `127.0.0.1` and read A's documents or spend A's API keys. On a shared computer the token is required, not optional hardening.
- **Single-instance lock is per user, never global:**
  - Windows: a named mutex in the `Local\` (per-session) namespace.
  - macOS: a lock file in the user's data directory.
  - A global lock would block the second user.
- **Profiles:** bundled templates are shared and read-only. Profiles a user creates are visible only to that user. Sharing a profile is done by exporting and importing the YAML (a later "import" item).
- **Uninstall:** removes the program only. Each user's data stays in their own profile. The uninstaller offers to delete *the current user's* data only; it never touches other users.
- **Temp files:** every remaining temp file uses the per-user temp directory (`%LOCALAPPDATA%\Temp`, or the macOS per-user `$TMPDIR`). Nothing goes to a shared `/tmp`.

### Installation modes on Windows

| Mode | Who installs | Admin needed | Who can use it | Best for |
|---|---|---|---|---|
| Per-user (default when not admin) | Each user, themselves | No | Only that user | Personal laptops |
| All-users | An administrator, once | Yes (UAC prompt) | Every account | Lab and shared machines; also needed where AppLocker blocks AppData (see below) |
| Silent all-users (`/ALLUSERS /VERYSILENT`) | IT via SCCM/Intune | Yes | Every account | Managed university fleets |

Inno Setup's `PrivilegesRequiredOverridesAllowed=dialog commandline` provides all three modes from one installer. The user data location is identical in every mode.

**macOS:** dragging the app to `/Applications` makes it available to all accounts. A standard (non-admin) user can still drag it to `~/Applications` for personal use.

---

## Engineering process

- **Before branching:** resolve the uncommitted `.env.example` change on `main` (commit it or stash it), then create the integration branch **`feature/desktop-app`**.
- **First commit on the branch:** copy this plan into the repo as `docs/development/DESKTOP_PLAN.md` (an ADR-style record of the GUI decision).
- **Workflow:** each phase is done as small topic branches (`desktop/<topic>`), each a PR into `feature/desktop-app` with green CI and review. Merge `main` into the branch regularly. Release with a PR to `main` plus a `vX.Y.Z` tag.
  - Option: Phase 0 changes also improve web mode, so those PRs can be cherry-picked to `main` early to reduce drift.
- **Web mode must keep working throughout.** Desktop behavior sits behind flags, with defaults unchanged. The existing 572 tests must stay green.
- **Versioning:** SemVer with a single source of truth (`VERSION`), plus `CHANGELOG.md` in Keep a Changelog format and a test that all version stamps agree.
- **Builds:** use pinned per-platform lock files for reproducible release builds. Build outside OneDrive (`--workpath`/`--distpath` under `%LOCALAPPDATA%`); CI builds are authoritative.

---

## Phases

Each phase has exit criteria; don't start the next until they are met.

### Phase 0: Foundations and hardening (web mode, no behavior change)

1. **CI**
   - Trigger on PRs into `feature/**`.
   - Add a `windows-latest` + `macos-14` test matrix.
2. **`backend/core/app_paths.py`** is the one source for all paths.
   - Resource dir: frozen-aware via `sys._MEIPASS`; otherwise the repo.
   - User data, logs and cache: via `platformdirs` with `appauthor=False`.
   - Environment-variable overrides are kept: `TRANSCRIBE_HTR_LOG_DIR`, `TRANSCRIBE_SESSION_ROOT`, `FRONTEND_DIST`, plus a new `TRANSCRIBE_HTR_DATA_DIR`.
   - It is used by:
     - `logging_config` (keep the `LOG_DIRECTORY` attribute and use `mkdir(parents=True)`)
     - the TTS cache (`tts_engine`, `export_utils`)
     - `ner_engine` (schema)
     - `export_utils` (template)
     - `main.py` (frontend dist)
3. **Profiles**
   - Bundled profiles are always read-only.
   - User profiles live in `<data>/profiles` and cannot shadow a bundled name.
   - Validate slugs with `^[a-z0-9_-]{1,64}$`.
   - Files: `core/profile_manager.py`, `routers/profiles.py`.
4. **Fix and trim**
   - Replace `cm.get_cmap` with a hard-coded `tab10` palette and a pure-Python gradient. This also removes matplotlib from the startup path; keep it, lazily loaded, for the consistency heat-map export.
   - Remove spaCy: `get_spacy_model`, `colorize_ner`, `SPACY_ENABLED`, and the `requirements.txt` entry.
   - Delete dead config: `WORKSPACE_PATH`, unused TTL constants.
   - Redact `anthropic_api_key` and `api_key` in logs.
   - Add TIFF to the upload conversion list. Either add `pillow-heif` or drop HEIC from the accepted types.
   - Make `cleanup_session` refuse to delete anything outside the session root.
   - Load python-dotenv in `run.py` only (dev).
5. **Versioning:** add `VERSION`, `CHANGELOG.md` and a version-consistency test. Replace the hard-coded `"2.0"` in `main.py` and `json_manager.py:133`.
6. **Tests:** in `tests/conftest.py`, point the log and data directories at `tmp_path`.
7. **Docs:** fix stale `CLAUDE.md` claims: the profiles junction, `model_registry.json`, the session destroy route, and spaCy.

**Exit:** all tests pass on Windows, macOS and Linux. `npm run build` followed by `python run.py` works unchanged.

### Phase 0.5: Packaging spike (throwaway, de-risks everything else)

- A minimal PyInstaller + pywebview build of the real backend on `windows-latest` and `macos-14` in CI.
- Prove the following:
  - The flat-import hidden imports work; the spec uses search paths `backend` and `backend/core`.
  - WebView2 (forced `edgechromium`) and WKWebView render the SPA.
  - Upload and drag-drop work.
  - Cookies on `127.0.0.1` work.
  - Windowed mode with no stdout/stderr works.
  - Startup time is acceptable.
  - Bundle size is recorded (expected 150–250 MB).
- Write the findings into `DESKTOP_PLAN.md`.

#### Spike results (2026-10-13): **G1 = GO**

The spike was built on branch `desktop/spike-packaging` with `spike/launcher_spike.py` and `spike/spike.spec`. It used PyInstaller 6.22.3 and pywebview 6.2.1 (pythonnet 3.2.1 on Windows, pyobjc 12.2.2 on macOS). The frozen builds were exercised in three modes:

- `--smoke-test`: serves the API and the SPA.
- `--self-check`: TLS/certifi, the OpenAI, Anthropic and Gemini SDKs, matplotlib figure render, DOCX export, TIFF conversion.
- `--window-check`: opens the real webview, checks that the SPA renders, that its session init reaches the backend (so cookies on `127.0.0.1` work), that it is a secure context, and that the clipboard API is present.

| | Windows (CI, python.org 3.11) | Windows (local, conda 3.11) | macOS 14 arm64 (CI) |
|---|---|---|---|
| Smoke / self-check / window check | ✅ / ✅ / ✅ | ✅ / ✅ / ✅ | ✅ / ✅ / ✅ |
| Engine | WebView2, Edge 153 | WebView2, Edge 155 | WKWebView (AppleWebKit 605.1.15) |
| Onedir size | 125 MB | 130 MB | 107 MB (`.app`) |
| Backend ready (smoke) | 1.6 s | 2.2 s (6.4 s wall time on first, antivirus-scanned launch) | 2.0 s |
| Window showing the SPA | 10.2 s (CI) | 5.7 s | 9.2 s (CI) |
| PyInstaller build | 100 s | 50 s | 58 s |

**Findings that feed Phase 1/2**

- **Size** is well under the 150–250 MB estimate, thanks to removing spaCy.
- **Imports:**
  - The flat-import layout freezes cleanly with search paths `backend`, `backend/core` and `backend/engines`.
  - Every module in those directories is listed as a hidden import, plus `collect_submodules` for the packages and for uvicorn.
  - matplotlib is not loaded at startup.
- **Windowed builds** have `sys.stdout`/`stderr` set to `None`. The launcher must redirect them to a log file before uvicorn starts (verified working). Use `log_config=None` with uvicorn.
- **Port allocation:** bind a socket to port 0 and pass it to `uvicorn.Server.run(sockets=[...])`. This works on both OSes with no port race.
- **macOS signing:** PyInstaller ad-hoc signs the bundle (`Signature=adhoc`, arm64 thin). `codesign --verify --deep --strict` passes, so the "unsigned" macOS build path is confirmed.
- **Conda Python** needs `<env>\Library\bin` on PATH while building. Otherwise OpenSSL, libffi and others are silently left out, and the frozen app could not make HTTPS calls. Release builds use python.org Python in CI, so this only affects local builds. It is documented for developers.
- **matplotlib** builds a font cache on first figure render. The launcher must set `MPLCONFIGDIR` to the cache directory; otherwise the cache goes to `~/.matplotlib`.
- **CI maintenance:** GitHub warns that the v4/v5 actions run on a deprecated Node 20. Bump the action versions in Phase 3.
- **Still to verify by hand** (Phase 4 QA; not automatable in the spike): the native file-open dialog, drag-and-drop from Explorer/Finder, and downloads. Downloads get their own bridge in Phase 1.6.

### Phase 1: Desktop runtime

1. **Persistent single-user workspace.** Enabled by `TRANSCRIBE_HTR_PERSISTENT_WORKSPACE`, which is separate from the security flag so the Vite dev setup still works.
   - `SessionWorkspace` gets an optional `workspace_path`.
   - `dependencies.py` builds one cached `"desktop"` session at `<data>/workspace`.
     - `create_session()` is idempotent and re-runs `FileIndex.populate_from_workspace()`. Re-running it means files dropped into the folder appear in the app: a free first step toward "import".
     - `get_session` ignores the cookie in this mode.
     - Keep the `get_workspace`/`get_file_index` signatures; tests override them.
   - Add `workspace.json` as a layout version marker for future migration.
   - No frontend change is needed for restore: `AnalysisTab` already rebuilds results from saved JSON.
2. **Data-safety fixes**
   - Atomic JSON writes in `core/atomic_io.py`: temp file `*.json.tmp`, then `os.replace`, with retry on Windows.
   - Uploads never overwrite silently: a name collision (case-insensitive) gets a unique suffix.
   - `DELETE /api/files/{root}` moves a document to `<data>/trash`; add a remove button in `UploadTab`.
3. **Local-server security (`core/desktop_security.py`).** Enabled by `TRANSCRIBE_HTR_REQUIRE_TOKEN`, which only the launcher sets.
   - Bind to `127.0.0.1` only, on a random port (socket bound to port 0).
   - A per-launch token arrives in the URL. A 200 response sets the HttpOnly, SameSite=Strict cookie `htr_desktop_auth`, then calls `location.replace('/')`.
   - TrustedHost allowlist.
   - `/docs` and `/openapi.json` disabled; dev CORS origins dropped.
4. **API keys: `core/secret_store.py` and `routers/settings.py`**
   - A `SecretStore` interface with two backends:
     - `keyring`, with the WinVault / macOS backend selected explicitly;
     - an owner-only file in the user data directory.
   - Windows uses Credential Manager.
   - **Unsigned macOS builds default to the file backend**, because the Keychain re-prompts after every update. Signed builds switch to the Keychain through a build-time flag.
   - `GET/PUT/DELETE /api/settings/keys` (token-protected) and `/api/app-info` (version, paths).
   - Frontend: a "Remember this key" checkbox; stored keys are loaded into the Zustand store at startup, so the existing button-enable logic is unchanged.
5. **Launcher: `desktop/launcher.py`, `desktop/bridge.py`, `desktop/single_instance.py`, `desktop/loading.html`**
   - Startup:
     - Call `multiprocessing.freeze_support()`.
     - Redirect stdout/stderr to a log file.
     - Call `truststore.inject_into_ssl()` so university TLS-inspection proxies work.
     - Set environment variables *before* importing `main`.
     - Set `MPLCONFIGDIR` to the cache directory.
   - Run uvicorn on a background thread with an explicit log config, and pywebview on the main thread (required on macOS).
   - Show the loading page immediately (the first launch can take 5–20 s while antivirus scans), poll `/api/health`, then navigate to the app.
   - Use a per-user single-instance lock: a second launch by the *same* user focuses the existing window, while other users on the machine are unaffected.
   - Fall back to the browser if WebView2 is missing.
   - Ask before closing the window while a batch is running.
   - A `--smoke-test` flag starts the server, checks health and exits 0.
6. **Downloads and other webview gaps**
   - `frontend/src/utils/download.js` replaces the blob+anchor code in `ExportTab.jsx` and `api/consistency.js`.
     - In desktop mode it calls `pywebview.api.save_from_api({path, params})`.
     - Python checks the path against an allowlist, streams the response from the local server to a temp file, shows the native Save dialog, moves the file, and returns the path for "Show in folder".
     - Web mode keeps the blob approach, with the revoke deferred.
   - Hide `window.print()` in desktop mode.
   - Replace "refresh the page" and "port 8000" error messages.
   - Add "Open data folder", "Open logs folder" and "Copy diagnostics" actions.
   - Set react-dropzone `useFsAccessApi: false`.

**Exit:** `python desktop/launcher.py` runs the complete workflow in a native window on both operating systems, and work persists across restarts. New tests cover:
- `app_paths`
- desktop-session restore and idempotence
- profile layering and slug validation
- the token and TrustedHost checks
- atomic writes
- colorize/NER
- the version check
- the launcher smoke test

### Phase 2: Packaging

- `packaging/pyinstaller/transcribe_htr.spec`
  - Bundles data files: `frontend/dist`, profiles, templates, and `entity-data`.
  - Excludes tkinter and the Qt/Tk backends; no UPX.
  - Sets Info.plist values: a fixed bundle ID, `LSMinimumSystemVersion` 11.0, and `NSAllowsLocalNetworking`.
- `packaging/windows/installer.iss`
  - Per-user **or** all-users install (`PrivilegesRequiredOverridesAllowed=dialog commandline`), plus silent switches for IT.
  - Start-menu shortcut, WebView2 bootstrapper, and an uninstaller that keeps user data. It offers to remove only the current user's data.
- `packaging/macos/` contains the dmg settings and an `entitlements.plist` (ready for signing later).
- `packaging/icons/` holds `.ico` and `.icns`.
- `packaging/requirements-desktop.in` adds `pywebview` (pinned), `platformdirs`, `keyring` and `truststore`, plus per-platform locks.
- `scripts/build_desktop.py` is one command: build the frontend, run PyInstaller, then the installer step.
- **Signing hooks:** `packaging/sign/sign_windows.ps1` and `sign_macos.sh` exit as no-ops when credentials are unset. CI maps secrets into `env` and gates on `env.X != ''`. Adding signing later means adding secrets, with no code change.

### Phase 3: CI release pipeline and updates

- `.github/workflows/release.yaml` runs on a `v*` tag.
  - It verifies that the tag matches `VERSION`.
  - It builds on `windows-latest` and `macos-14` without the pip cache, runs `--smoke-test` against the frozen binary, and uploads the installers plus SHA-256 checksums to a **draft** GitHub Release.
- Update notice: the app checks the GitHub Releases API at startup (it can be switched off) and shows "a new version is available" with a link. No auto-update in v1.

### Phase 4: Quality assurance, documentation, beta

- Manual QA checklist on clean virtual machines with no Python installed:
  - Windows 10 22H2, and Windows 11 with Smart App Control on and off
  - macOS 14 and 15 on Apple Silicon
  - a non-ASCII username, a long path, and a proxy
  - a **standard (non-admin) account**, and **two accounts running the app at the same time** (Fast User Switching / RDP)
  - all-users and per-user installs on Windows
- User guides with screenshots in `docs/user/INSTALL_WINDOWS.md` and `INSTALL_MACOS.md`, covering the unsigned first-run steps:
  - Windows: SmartScreen → "More info → Run anyway".
  - macOS Sequoia: try to open the app → System Settings → Privacy & Security → "Open Anyway"; also, drag the app to Applications.
- Developer guide: `docs/development/DESKTOP.md`. Update the README's install section.
- Beta with 3–5 digital-humanities users; track issues with a GitHub issue template.

---

## Timeline

**Assumptions**
- One developer working about full-time, using Claude Code.
- At 50% time, calendar time roughly doubles.
- Add a **20–30% contingency**. The main schedule risks are surprises in the packaging spike, antivirus false positives, and quirks of the macOS CI runners.

| # | Phase | Effort | Illustrative dates (start Mon 19 Oct 2026) | Milestone and gate |
|---|---|---|---|---|
| — | Setup: branch, commit plan to repo, CI triggers | 1–2 days | 19–20 Oct | **M0:** branch and CI green on 3 operating systems |
| 0 | Foundations and hardening | 2 wk | 19 Oct – 30 Oct | **M1:** path refactor merged; web mode unchanged; tests pass on Win/Mac/Linux |
| 0.5 | Packaging spike | 1 wk | 2 – 6 Nov | **G1, go/no-go:** pywebview viable on both OSes? If not, switch to option A (browser) with no lost work |
| 1 | Desktop runtime | 4–5 wk | 9 Nov – 11 Dec (includes Thanksgiving) | **M2, internal alpha:** full workflow in a native window from source; persistence and multi-user safety tested |
| 2 | Packaging and installers | 2 wk | 14 – 18 Dec, then 4 – 8 Jan (winter break between) | **M3:** first installers built locally; **G2:** signing decision (see below) |
| 3 | CI release pipeline and update notice | 1 wk | 11 – 15 Jan | **M4:** a tag produces a draft release automatically |
| 4a | QA on clean VMs, user docs | 1.5–2 wk | 18 – 29 Jan | **M5, beta:** released to 3–5 digital-humanities users at the start of spring semester |
| 4b | Beta feedback and fixes (about half-time) | 3–4 wk calendar | 1 – 26 Feb | — |
| — | **1.0 release** | — | **early March 2027** | **M6:** tagged v2.1.0 (or 3.0.0) on `main` |

**Total:** about 12 engineering weeks plus a 3–4 week beta, so about 4.5 months of calendar time with the holidays.

**Signing track (parallel, optional).** If signing is approved at G2 (mid-December), start enrolment straight away. Apple organisation enrolment, which needs a D-U-N-S number, and Azure identity validation can each take one to several weeks. Once credentials exist, wiring them into CI takes about 2–3 days thanks to the Phase 2 hooks, so signed builds could be ready for the beta.

---

## Unsigned builds: what happens and what it costs

Code signing is not a licence. The BSD-2 licence is unaffected either way. A signature is a cryptographic statement of who published a file. Windows and macOS use it, together with Apple's notarisation and Microsoft's reputation service, to decide whether to warn about the file or block it. Without one, the operating system treats the app as coming from an *unknown publisher*. Here is what each user will see.

### Windows (unsigned `.exe` installer)

| # | When | What the user sees | User action | Severity |
|---|---|---|---|---|
| 1 | Downloading in Edge or Chrome | "Transcribe-HTR-Setup.exe isn't commonly downloaded" (Edge), or a similar Chrome warning | Edge: "…" → Keep → Show more → Keep anyway | Low: a few confusing clicks |
| 2 | First run of the installer | Blue **"Windows protected your PC"** (SmartScreen), Publisher: *Unknown publisher* | "More info" → "Run anyway" | Medium: looks alarming, and many users stop here |
| 3 | All-users install | UAC prompt with a yellow banner, "Publisher: Unknown" | An admin clicks Yes | Low |
| 4 | **Smart App Control** is On (Windows 11 clean installs; it starts in evaluation mode, then switches itself on or off) | "Smart App Control blocked an app that may be unsafe", **with no Run-anyway option**. It checks every DLL and `.pyd` loaded, not just the `.exe` | Only option: turn SAC off for the whole PC in Windows Security. On many builds it cannot be turned back on without reinstalling Windows | **High:** effectively blocked; the workaround lowers system security |
| 5 | Defender or other antivirus | PyInstaller's launcher sometimes triggers heuristic detection: the app is quarantined, "disappears", or silently fails to start | Restore from quarantine and add an exclusion | Medium–high when it happens; unpredictable from release to release |
| 6 | **University-managed PCs** (AppLocker/WDAC) | "This app has been blocked by your system administrator." AppLocker's default rules allow only `Program Files` and `Windows`, so per-user installs in AppData are blocked | IT must allow-list it. Unsigned, IT can only allow by **file hash**, which changes every release | **High:** every update needs an IT ticket |
| 7 | Every update | Steps 1–2 repeat. Reputation is tracked per file hash, so each new version starts at zero | Repeat | Medium: recurring friction |

**Not affected on Windows:**
- Windows Firewall, because the server binds only to `127.0.0.1`.
- Credential Manager key storage, which does not depend on a signature.

### macOS on Apple Silicon (ad-hoc-signed, not notarised)

Apple Silicon refuses to run *any* unsigned native code. PyInstaller therefore applies an **ad-hoc** signature: an anonymous one that lets the app run, but carries no Developer ID and is not notarised by Apple.

| # | When | What the user sees | User action | Severity |
|---|---|---|---|---|
| 1 | First launch on **macOS 15 Sequoia and later** | **"'Transcribe-HTR' Not Opened. Apple could not verify 'Transcribe-HTR' is free of malware…"**, with only *Done* and *Move to Trash* | System Settings → Privacy & Security → scroll to Security → "Open Anyway" (the button appears only for a while after the blocked attempt) → authenticate → "Open Anyway" again | **Medium–high:** hard to discover without the guide. The old Control-click → Open shortcut was removed in Sequoia |
| 2 | First launch on macOS 14 or earlier | Same warning | Control-click → Open → Open | Medium |
| 3 | **Standard (non-admin) users**, e.g. lab Macs | Same block, but "Open Anyway" needs an administrator's password | An admin must approve it on that machine | **High** on shared machines |
| 4 | Sometimes, if quarantine or the signature isn't handled perfectly | **"'Transcribe-HTR' is damaged and can't be opened. You should move it to the Trash."** The wording wrongly suggests a corrupt download | Only fix: Terminal command `xattr -cr /Applications/Transcribe-HTR.app` | **High:** not turnkey. The spike and QA must confirm our builds take path 1, not this one |
| 5 | Run straight from the DMG or Downloads | App Translocation: runs from a hidden read-only copy | Drag to Applications first (in the guide) | Low: our design doesn't write into the app bundle |
| 6 | Stored API keys after **every update** | "Transcribe-HTR wants to use your confidential information stored in … your keychain." The keychain entry is tied to the exact ad-hoc build | Enter password → *Always Allow*. Clicking *Deny* makes saved keys seem to vanish | Medium. **Mitigation:** unsigned macOS builds default to the owner-only file store and switch to Keychain once signed |
| 7 | MDM-managed Macs set to "App Store and identified developers" with no override | Blocked | IT exception | High |
| 8 | Every update | Steps 1/3 repeat for each newly downloaded version | Repeat | Medium |

**Not affected on macOS:** the application firewall, because the server binds only to loopback. The Phase 0.5 spike verifies this.

### Impact by deployment scenario

| Scenario | Unsigned outcome |
|---|---|
| Personal Windows laptop, Smart App Control off | ✅ Works; 2–4 extra clicks per version |
| New Windows 11 PC, Smart App Control on | ❌ Blocked unless SAC is switched off for the whole PC |
| University-managed Windows PC or lab | ❌ Usually blocked; IT allow-list needed for every release |
| Personal Mac, admin user | ⚠️ Works after the Settings detour and password; repeats per update |
| Shared or lab Mac, standard user | ❌ Needs an admin on every machine, for every version |

**Indirect costs**
- Warnings teach users to click through security prompts.
- "Unknown publisher" undermines trust with reviewers and IT departments.
- Support load: most beta issue reports will likely be about installation.

### Mitigations while unsigned (all included in the plan)

- Install guides with screenshots for each OS version (Phase 4).
- SHA-256 checksums and free **GitHub build-provenance attestations** (`actions/attest-build-provenance`, checkable with `gh attestation verify`). These let careful users and IT confirm the file came from our CI, although the operating system ignores them.
- Submit each Windows release to Microsoft's false-positive portal.
- An all-users installer with silent switches, so IT can deploy and allow-list it.
- A loopback-only server, so there are no firewall prompts.
- The file-based key store on unsigned macOS builds.
- A test of the "damaged" path on clean VMs.

### What signing would fix, and what it costs (decision G2)

| Platform | Option | Approx. cost | Lead time | Notes |
|---|---|---|---|---|
| macOS | Apple Developer Program + Developer ID + notarisation | $99/yr (individual or organisation; MTSU may already be enrolled) | Days for an individual; 1–3 wk for an organisation (needs D-U-N-S) | Removes **all** of Mac issues 1–4 and 6–8. The single biggest improvement for the money |
| Windows | Azure Artifact Signing (formerly Trusted Signing) | ~$10/month | Days–weeks for identity validation; eligibility rules apply (check current terms) | CI-friendly with no hardware token |
| Windows | SignPath Foundation | Free for qualifying open-source projects | Application review | Requires their build process in public CI |
| Windows | Organisation-validated (OV) certificate from a commercial CA | ~$200–500/yr | 1–2 wk | Since 2023 the key must live on a hardware token or cloud HSM, which is awkward in CI |

Windows signing does the following:
- It removes "Unknown publisher".
- It makes the app acceptable to Smart App Control.
- It lets IT allow-list by **publisher once** instead of by hash every release.
- It stops each release resetting SmartScreen reputation.

It does **not** remove SmartScreen warnings instantly. Since 2024 even EV certificates must earn reputation over time.

**Recommendation:** ship the alpha unsigned. Get the Apple Developer membership before the beta. Decide on Windows signing at G2, based on how many beta users are on managed or SAC-enabled PCs.

---

## Risks and open items

- **Unsigned builds are the main risk to a turnkey experience.** See the section above. Fresh Windows 11 machines, managed university PCs and lab Macs are effectively blocked without IT help.
- **Antivirus false positives on PyInstaller builds:** mitigated by onedir, no UPX, and submitting false-positive reports. Building the bootloader from source is an option.
- **Import capability (deferred):** Phase 1 gives folder-drop import for free. A real "Import project/export ZIP" or user-chosen project folders can be added later; `workspace.json` versioning keeps that migration possible.
- **WebView quirks:** de-risked by the Phase 0.5 spike, and the browser fallback always exists.
- **The repo lives in OneDrive:** do heavy builds outside it, and consider moving the working clone (e.g. to `C:\dev\Transcribe-HTR`).

## Verification

- **Every PR:** `python -m pytest -rs` on Windows, macOS and Linux (572+ tests, no unexplained skips); `npm run lint` and `npm run build`; the import check.
- **Phase 1:** run `python desktop/launcher.py` and do the full flow: enter and remember a key; upload a JPG and a TIFF; transcribe; NER colorize; summarize; consistency export ZIP; DOCX export via the Save dialog. Quit, relaunch, and confirm the documents, results and key are restored. Confirm a second launch focuses the existing window. Confirm that `curl` to the API without the token, or with a bad Host header, returns 403.
- **Multi-user:** with two accounts logged in at once, both apps run. Each user sees only their own documents, profiles and keys. User B's request to user A's port without A's token returns 403. Uninstalling as one user leaves the other user's data intact.
- **Phase 2/3:** the frozen `--smoke-test` passes in CI. Install from the CI artifact on a clean VM, repeat the Phase 1 flow, uninstall, and confirm user data was kept.
- **Release:** a tag produces a draft release with both installers and checksums, and the version is identical in the app's About panel, the installer, `VERSION` and `CHANGELOG`.
