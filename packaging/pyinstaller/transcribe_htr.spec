# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Transcribe-HTR desktop app (onedir).

Run through scripts/build_desktop.py, which builds the frontend, writes
build_info.json and passes their locations in:

    HTR_FRONTEND_DIST   built SPA (contains index.html)
    HTR_BUILD_INFO      build_info.json to bundle (version, commit, defaults)

The bundle mirrors the repo layout (backend/profiles, backend/templates,
entity-data, frontend/dist, VERSION) so backend/core/app_paths.py resolves
resources the same way frozen or not.
"""

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parents[1]
BACKEND = ROOT / "backend"
ICONS = ROOT / "packaging" / "icons"
APP_NAME = "Transcribe-HTR"
BUNDLE_ID = "org.transcribe-htr.app"  # permanent: see DESKTOP_PLAN.md decisions
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

FRONTEND_DIST = Path(os.environ.get("HTR_FRONTEND_DIST", ROOT / "frontend" / "dist"))
BUILD_INFO = Path(os.environ.get("HTR_BUILD_INFO", ""))
if not (FRONTEND_DIST / "index.html").is_file():
    raise SystemExit(f"No built frontend at {FRONTEND_DIST}; run scripts/build_desktop.py")
if not BUILD_INFO.is_file():
    raise SystemExit("HTR_BUILD_INFO must point at build_info.json; run scripts/build_desktop.py")

# The backend imports by flat module name (CLAUDE.md "Import layout"): its
# directories are search paths and every module is listed explicitly.
SEARCH = [ROOT, BACKEND, BACKEND / "core", BACKEND / "engines"]
for p in SEARCH:
    sys.path.insert(0, str(p))

hidden = collect_submodules("uvicorn") + collect_submodules("keyring.backends")
for pkg in ("routers", "schemas", "providers", "engines", "analysis", "core", "desktop"):
    hidden += collect_submodules(pkg)
for d in (BACKEND, BACKEND / "core", BACKEND / "engines"):
    hidden += [f.stem for f in d.glob("*.py") if f.stem not in ("run", "__init__")]

datas = [
    (str(FRONTEND_DIST), "frontend/dist"),
    (str(BACKEND / "profiles"), "backend/profiles"),
    (str(BACKEND / "templates"), "backend/templates"),
    (str(ROOT / "entity-data"), "entity-data"),
    (str(ROOT / "VERSION"), "."),
    (str(BUILD_INFO), "."),
]

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(p) for p in SEARCH],
    datas=datas,
    hiddenimports=hidden,
    excludes=[
        "tkinter", "matplotlib.backends.backend_tkagg", "matplotlib.backends.backend_qtagg",
        "PyQt5", "PyQt6", "PySide2", "PySide6", "IPython", "pytest", "notebook",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)


def _windows_version_file() -> str:
    """VS_VERSIONINFO so Explorer's Properties > Details shows name and version."""
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
    )

    nums = tuple(int(x) for x in VERSION.split("-")[0].split("+")[0].split(".")) + (0,)
    info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=nums[:4], prodvers=nums[:4]),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", "Transcribe-HTR project"),
                StringStruct("FileDescription", "Transcribe-HTR"),
                StringStruct("FileVersion", VERSION),
                StringStruct("ProductName", "Transcribe-HTR"),
                StringStruct("ProductVersion", VERSION),
                StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
                StringStruct("LegalCopyright", "BSD-2-Clause. Copyright (c) 2024-2026 Graham West and John Wallin"),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )
    path = Path(workpath) / "version_info.txt"
    path.write_text(str(info), encoding="utf-8")
    return str(path)


exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    console=False,
    upx=False,  # UPX-packed binaries trigger antivirus false positives
    icon=str(ICONS / ("app.icns" if sys.platform == "darwin" else "app.ico")),
    version=_windows_version_file() if sys.platform == "win32" else None,
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name=APP_NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(ICONS / "app.icns"),
        bundle_identifier=BUNDLE_ID,
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "BSD-2-Clause. Copyright (c) 2024-2026 Graham West and John Wallin",
            # The UI is served from 127.0.0.1 over plain HTTP.
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        },
    )
