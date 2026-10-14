# Desktop app: developer guide

This guide covers how the Windows and macOS desktop app is put together, run and built. Background, decisions and status are in [DESKTOP_PLAN.md](DESKTOP_PLAN.md).

## How it fits together

```
Transcribe-HTR.exe / Transcribe-HTR.app        (PyInstaller onedir bundle)
└─ desktop/launcher.py
   ├─ sets env: TRANSCRIBE_HTR_PERSISTENT_WORKSPACE, TRANSCRIBE_HTR_LAUNCH_TOKEN, MPLCONFIGDIR
   ├─ uvicorn (thread) ── backend/main.py on 127.0.0.1:<random port>
   └─ pywebview window ── loads /api/desktop/auth?token=… → cookie → the React UI
        └─ window.pywebview.api = desktop/bridge.py (Save dialog, open folder, diagnostics, busy flag)
```

- **Paths:** all of them come from `backend/core/app_paths.py`.
  - The bundle is read-only and mirrors the repo layout.
  - User data goes in per-user folders: `%LOCALAPPDATA%\Transcribe-HTR` on Windows, `~/Library/Application Support/Transcribe-HTR` on macOS.
- **Security:** the API answers only requests that carry the per-launch token (`backend/core/desktop_security.py`).
- **Single instance:** the app runs once per user account (`desktop/single_instance.py`). A second launch brings the open window to the front.

## Run from source

```bash
pip install -r backend/requirements.txt -r desktop/requirements.txt
cd frontend && npm ci && npm run build && cd ..
python desktop/launcher.py
```

You can point the launcher at a frontend built somewhere else with `FRONTEND_DIST=<dir>`. Check modes:

| Flag | Opens a window | What it does |
|---|---|---|
| `--smoke-test` | no | Starts the app and checks that the API is locked, that auth unlocks it, the SPA, the persistent session and `app-info` |
| `--self-check` | no | Loads the lazily imported dependencies (TLS, provider SDKs, matplotlib, DOCX, secret store) |
| `--window-check` | yes, closes itself | Checks that the UI rendered and authenticated, the desktop UI is shown, and the bridge works |
| `--version` | no | Prints the version |
| `--forget-keys` | no | Deletes the remembered API keys (used by the Windows uninstaller) |

A built app with no console writes these results to `launcher.log` in the user's log folder.

## Build an installer

```bash
pip install --require-hashes --no-deps -r packaging/locks/windows-x64.txt   # or macos-arm64.txt
python scripts/build_desktop.py --out <build dir> [--frontend-dist frontend/dist] [--no-installer]
```

**Keep `--out` outside OneDrive or iCloud.** Syncing locks files in the middle of a build.

The script runs these steps in order:
1. Build the frontend.
2. Write `build_info.json`.
3. Run PyInstaller (`packaging/pyinstaller/transcribe_htr.spec`).
4. Sign the app.
5. Run the frozen `--smoke-test` and `--self-check`.
6. Build the installer: Inno Setup on Windows, needing `ISCC.exe` (Inno Setup 6); a `.dmg` on macOS.
7. Sign the installer.
8. Write `SHA256SUMS.txt`.

CI does the same in `.github/workflows/desktop-build.yaml`. It then installs the result on a clean runner, runs `--smoke-test` and `--window-check` against the installed app, and uninstalls it. The installers are uploaded as workflow artifacts.

**Conda Python, Windows only:** put `<env>\Library\bin` on `PATH` before building. Otherwise PyInstaller misses OpenSSL and the app cannot make HTTPS calls. CI uses python.org Python and is not affected.

**Smart App Control:** Windows 11 with Smart App Control turned on can block an unsigned local build ("An Application Control policy has blocked this file"). That is expected until builds are signed (see below). Test unsigned builds through CI, or on a machine where it is off.

## Dependencies

- `packaging/requirements-desktop.in` is the input.
- `packaging/locks/*.txt` are hashed, per-platform locks. Release builds install only from these.
- After changing `backend/requirements.txt`, `desktop/requirements.txt` or the `.in` file, regenerate the locks and commit them together:

```bash
pip install uv
python scripts/lock_desktop.py            # add --upgrade to move to newest allowed versions
```

## Signing (off until credentials exist)

`packaging/sign/sign_windows.ps1` and `packaging/sign/sign_macos.sh` exit without doing anything when no credentials are set. To turn signing on, add repository secrets; no code changes are needed.

**Windows:**
- `WINDOWS_SIGNING_MODE=pfx` uses `WINDOWS_PFX_BASE64` and `WINDOWS_PFX_PASSWORD`.
- `WINDOWS_SIGNING_MODE=azure` uses Azure Artifact Signing (`AZURE_SIGNING_DLIB`, `AZURE_SIGNING_METADATA`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`). Wiring the Azure variables into the workflow is a follow-up, done when an account exists.
- Every `.exe`, `.dll` and `.pyd` is signed, because Smart App Control checks each one.

**macOS:**
- `APPLE_SIGNING_IDENTITY`, `APPLE_CERT_P12_BASE64` and `APPLE_CERT_PASSWORD` for signing; `APPLE_ID`, `APPLE_TEAM_ID` and `APPLE_APP_PASSWORD` for notarization.
- The script signs every binary with the hardened runtime (`packaging/sign/entitlements.plist`), notarizes, and staples.
- A signed macOS build also defaults to storing keys in the Keychain (through `build_info.json`).

## Permanent identifiers. Never change these.

- macOS bundle ID: `org.transcribe-htr.app` (in the spec).
- Windows installer AppId: `{3B228E44-1F43-4EFF-8DB4-CF0BA7179BD1}` (in `installer.iss`).

## Icons

`packaging/icons/make_icons.py` generates a placeholder icon. To use designed artwork, replace `icon.png` (1024 px) and run `make_icons.py --from-png`.
