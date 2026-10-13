# -*- mode: python ; coding: utf-8 -*-
# THROWAWAY Phase 0.5 spike spec. Build from the repo root:
#   pyinstaller spike/spike.spec --noconfirm --workpath <outside OneDrive> --distpath <outside OneDrive>
# FRONTEND_DIST_SRC points at a built frontend (default: frontend/dist).
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
BACKEND = ROOT / "backend"
DIST_SRC = Path(os.environ.get("FRONTEND_DIST_SRC", ROOT / "frontend" / "dist"))
if not (DIST_SRC / "index.html").exists():
    raise SystemExit(f"No built frontend at {DIST_SRC}")

# The backend imports by flat module name (see CLAUDE.md "Import layout"),
# so its directories are search paths and every module is listed explicitly.
SEARCH = [BACKEND, BACKEND / "core", BACKEND / "engines"]
for p in SEARCH:
    sys.path.insert(0, str(p))

hidden = collect_submodules("uvicorn")
for pkg in ("routers", "schemas", "providers", "engines", "analysis", "core"):
    hidden += collect_submodules(pkg)
for d in (BACKEND, BACKEND / "core", BACKEND / "engines"):
    hidden += [f.stem for f in d.glob("*.py") if f.stem not in ("run", "__init__")]

datas = [
    (str(DIST_SRC), "frontend/dist"),
    (str(BACKEND / "profiles"), "backend/profiles"),
    (str(BACKEND / "templates"), "backend/templates"),
    (str(ROOT / "entity-data"), "entity-data"),
    (str(ROOT / "VERSION"), "."),
]

a = Analysis(
    [str(ROOT / "spike" / "launcher_spike.py")],
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
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Transcribe-HTR",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="Transcribe-HTR")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Transcribe-HTR.app",
        bundle_identifier="org.transcribe-htr.spike",
        info_plist={
            "LSMinimumSystemVersion": "11.0",
            "NSHighResolutionCapable": True,
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        },
    )
