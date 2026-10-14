"""Build the Transcribe-HTR desktop app and its installer for this platform.

    python scripts/build_desktop.py --out <dir> [--frontend-dist <dir>] [--no-installer]

Steps (each stops the build on failure):
  1. Frontend: `npm ci && npm run build` (or reuse --frontend-dist).
  2. build_info.json: version, commit, build time, signed flag, env defaults.
  3. PyInstaller onedir app (packaging/pyinstaller/transcribe_htr.spec).
  4. Sign the app (packaging/sign/*; a no-op without credentials).
  5. Frozen checks: --smoke-test and --self-check against throwaway user dirs.
  6. Installer: Inno Setup .exe on Windows, .dmg on macOS; signed likewise.
  7. SHA256SUMS.txt for the installer.

Install the pinned build environment first (release builds):
    pip install --require-hashes -r packaging/locks/<platform>.txt

Keep --out OUTSIDE OneDrive/iCloud folders: syncing a build tree causes file
locks mid-build. CI uses the workspace's build/desktop.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APP = "Transcribe-HTR"
WEBVIEW2_BOOTSTRAPPER_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"


def step(msg: str) -> None:
    print(f"\n=== {msg}", flush=True)


def run(cmd, **kwargs) -> None:
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kwargs)


def version() -> str:
    return (REPO / "VERSION").read_text(encoding="utf-8").strip()


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short=10", "HEAD"], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=REPO,
                               capture_output=True, text=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def signing_configured() -> bool:
    return bool(os.getenv("WINDOWS_SIGNING_MODE") if IS_WIN else os.getenv("APPLE_SIGNING_IDENTITY"))


def build_frontend(out: Path, given: str) -> Path:
    if given:
        dist = Path(given)
    else:
        npm = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm:
            sys.exit("npm not found; install Node 22 or pass --frontend-dist")
        run([npm, "ci"], cwd=REPO / "frontend")
        run([npm, "run", "build"], cwd=REPO / "frontend")
        dist = REPO / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        sys.exit(f"No built frontend at {dist}")
    target = out / "frontend-dist"
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(dist, target)
    return target


def write_build_info(out: Path, signed: bool) -> Path:
    info = {
        "version": version(),
        "commit": git_commit(),
        "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "platform": f"{sys.platform}-{os.uname().machine if hasattr(os, 'uname') else 'x64'}",
        "signed": signed,
        # A signed macOS build can use the Keychain without re-prompting after
        # every update; unsigned builds use the owner-only file store.
        "defaults": {"TRANSCRIBE_HTR_SECRET_BACKEND": "keyring"} if (signed and IS_MAC) else {},
    }
    path = out / "build_info.json"
    path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(json.dumps(info, indent=2))
    return path


def pyinstaller(out: Path, frontend: Path, build_info: Path) -> Path:
    env = {**os.environ, "HTR_FRONTEND_DIST": str(frontend), "HTR_BUILD_INFO": str(build_info)}
    run([sys.executable, "-m", "PyInstaller", REPO / "packaging" / "pyinstaller" / "transcribe_htr.spec",
         "--noconfirm", "--clean", "--log-level", "WARN",
         "--workpath", out / "work", "--distpath", out / "dist"], env=env)
    return out / "dist" / (f"{APP}.app" if IS_MAC else APP)


def app_binary(app: Path) -> Path:
    if IS_MAC:
        return app / "Contents" / "MacOS" / APP
    return app / (f"{APP}.exe" if IS_WIN else APP)


def sign(kind: str, target: Path) -> None:
    if IS_WIN:
        run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             REPO / "packaging" / "sign" / "sign_windows.ps1", target])
    elif IS_MAC:
        run(["bash", REPO / "packaging" / "sign" / "sign_macos.sh", kind, target])


def frozen_checks(app: Path) -> None:
    exe = app_binary(app)
    with tempfile.TemporaryDirectory(prefix="htr-check-") as tmp:
        env = {
            **os.environ,
            "TRANSCRIBE_HTR_DATA_DIR": str(Path(tmp) / "data"),
            "TRANSCRIBE_HTR_LOG_DIR": str(Path(tmp) / "logs"),
            "TRANSCRIBE_HTR_CACHE_DIR": str(Path(tmp) / "cache"),
            "TRANSCRIBE_HTR_SECRET_BACKEND": "file",
        }
        env.pop("FRONTEND_DIST", None)
        for mode in ("--smoke-test", "--self-check"):
            # Windowed builds have no console: the result is in launcher.log.
            proc = subprocess.run([str(exe), mode], env=env, cwd=tmp, capture_output=True, text=True, timeout=300)
            log = Path(tmp) / "logs" / "launcher.log"
            output = (proc.stdout or "") + (log.read_text(encoding="utf-8", errors="replace") if log.exists() else "")
            result = [line for line in output.splitlines() if line.startswith(("SMOKE", "SELFCHECK"))]
            print(f"{mode}: exit {proc.returncode} {result[-1] if result else '(no result line)'}", flush=True)
            if proc.returncode != 0:
                print(output[-3000:])
                sys.exit(f"Frozen {mode} failed")


def webview2_bootstrapper(out: Path):
    path = out / "MicrosoftEdgeWebview2Setup.exe"
    if not path.exists():
        try:
            urllib.request.urlretrieve(WEBVIEW2_BOOTSTRAPPER_URL, path)
        except OSError as e:
            print(f"WARNING: WebView2 bootstrapper not downloaded ({e}); installer will not include it.")
            return None
    return path


def find_iscc():
    candidates = [shutil.which("iscc"), shutil.which("ISCC")]
    for base in (os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles"), os.getenv("LOCALAPPDATA")):
        if base:
            candidates += [Path(base) / "Inno Setup 6" / "ISCC.exe", Path(base) / "Programs" / "Inno Setup 6" / "ISCC.exe"]
    return next((Path(c) for c in candidates if c and Path(c).is_file()), None)


def windows_installer(out: Path, app: Path) -> Path:
    iscc = find_iscc()
    if not iscc:
        sys.exit("Inno Setup 6 (ISCC.exe) not found: install it or pass --no-installer")
    defines = [f"/DAppVersion={version()}", f"/DSourceDir={app}", f"/DOutputDir={out / 'installer'}"]
    bootstrapper = webview2_bootstrapper(out)
    if bootstrapper:
        defines.append(f"/DWebView2Bootstrapper={bootstrapper}")
    run([iscc, "/Q", *defines, REPO / "packaging" / "windows" / "installer.iss"])
    return out / "installer" / f"{APP}-{version()}-windows-x64-setup.exe"


def macos_dmg(out: Path, app: Path) -> Path:
    stage = out / "dmg-stage"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    # ditto preserves the bundle's signature and extended attributes.
    run(["ditto", app, stage / app.name])
    (stage / "Applications").symlink_to("/Applications")
    dmg = out / "installer" / f"{APP}-{version()}-macos-arm64.dmg"
    dmg.parent.mkdir(parents=True, exist_ok=True)
    dmg.unlink(missing_ok=True)
    run(["hdiutil", "create", "-volname", APP, "-srcfolder", stage, "-fs", "HFS+",
         "-format", "UDZO", "-ov", dmg])
    return dmg


def checksums(files) -> Path:
    lines = []
    for f in files:
        digest = hashlib.sha256(Path(f).read_bytes()).hexdigest()
        lines.append(f"{digest}  {Path(f).name}")
    path = Path(files[0]).parent / "SHA256SUMS.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(REPO / "build" / "desktop"), help="build directory")
    parser.add_argument("--frontend-dist", default="", help="reuse an existing frontend build")
    parser.add_argument("--no-installer", action="store_true", help="stop after the app and its checks")
    args = parser.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if "onedrive" in str(out).lower() or "icloud" in str(out).lower():
        print("WARNING: building inside a synced folder can fail with locked files; prefer --out elsewhere.")
    signed = signing_configured()

    step(f"Transcribe-HTR {version()} desktop build -> {out}")
    step("1/6 Frontend")
    frontend = build_frontend(out, args.frontend_dist)
    step("2/6 Build info")
    build_info = write_build_info(out, signed)
    step("3/6 PyInstaller")
    app = pyinstaller(out, frontend, build_info)
    step("4/6 Sign app")
    sign("app", app)
    step("5/6 Frozen checks")
    frozen_checks(app)
    if args.no_installer:
        print(f"\nApp: {app}")
        return 0
    step("6/6 Installer")
    installer = windows_installer(out, app) if IS_WIN else macos_dmg(out, app)
    sign("dmg" if IS_MAC else "installer", installer)
    sums = checksums([installer])
    print(f"\nInstaller: {installer} ({installer.stat().st_size / 1e6:.0f} MB)\nChecksums: {sums}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
