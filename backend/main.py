"""FastAPI application entry point."""

import os
import sys
from pathlib import Path

# ── Import path setup ─────────────────────────────────────────────────────────
# backend/ and backend/core/ must be on sys.path so all flat imports work
# (e.g. `from config import *`, `from logging_config import ...`)
_BACKEND = Path(__file__).parent
for _p in (_BACKEND, _BACKEND / "core"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

# ── FastAPI app ───────────────────────────────────────────────────────────────
import secrets

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app_paths import frontend_dist_dir
from app_version import APP_VERSION
from desktop_security import (
    ALLOWED_HOSTS,
    AUTH_PATH,
    LaunchTokenMiddleware,
    launch_token,
    make_auth_endpoint,
)
from routers import (
    colorize,
    consistency,
    export,
    files,
    harmonization,
    models,
    ner,
    profiles,
    session,
    settings,
    summarize,
    transcription,
    tts,
)
from schemas.common import HealthResponse

SECRET_KEY = os.getenv("SESSION_SECRET_KEY") or secrets.token_hex(32)

# Set by the desktop launcher; enables local-server hardening (see
# core/desktop_security.py). Unset in web mode, development and tests.
_LAUNCH_TOKEN = launch_token()
_DESKTOP = _LAUNCH_TOKEN is not None

app = FastAPI(
    title="Transcribe-HTR API",
    version=APP_VERSION,
    docs_url=None if _DESKTOP else "/docs",
    redoc_url=None if _DESKTOP else "/redoc",
    openapi_url=None if _DESKTOP else "/openapi.json",
)

# Session middleware (cookie-based, signed with SECRET_KEY)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="session")

if _DESKTOP:
    # Added last = outermost: the Host check runs before the token check.
    app.add_middleware(LaunchTokenMiddleware, token=_LAUNCH_TOKEN)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
    app.add_api_route(AUTH_PATH, make_auth_endpoint(_LAUNCH_TOKEN), methods=["GET"], include_in_schema=False)
else:
    # CORS — allow the React dev server (or any localhost during development)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8501"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(session.router,        prefix="/api")
app.include_router(files.router,          prefix="/api")
app.include_router(transcription.router,  prefix="/api")
app.include_router(harmonization.router,  prefix="/api")
app.include_router(consistency.router,    prefix="/api")
app.include_router(colorize.router,       prefix="/api")
app.include_router(ner.router,            prefix="/api")
app.include_router(summarize.router,      prefix="/api")
app.include_router(tts.router,            prefix="/api")
app.include_router(profiles.router,       prefix="/api")
app.include_router(models.router,         prefix="/api")
app.include_router(export.router,         prefix="/api")
app.include_router(settings.router,       prefix="/api")


# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health():
    return {"status": "ok"}


# ── Static frontend (compiled React SPA) ─────────────────────────────────────
# MUST be registered last: Starlette matches routes in registration order, and
# the catch-all below would otherwise shadow every /api/* router above.
#
# FRONTEND_DIST overrides the build location; it defaults to
# <repo>/frontend/dist (or its mirror in the frozen bundle), so `npm run build`
# followed by `python run.py` serves the built SPA from the backend too. When
# no build exists the whole block is skipped and the dev workflow (Vite on
# :5173 proxying /api to :8000) is unaffected.
_FRONTEND_DIST = frontend_dist_dir()

if _FRONTEND_DIST.is_dir():
    # Hashed, immutable build artefacts.
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIST / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        """Serve public/ files verbatim; fall back to index.html for the SPA."""
        # Never let the SPA swallow an unmatched API route — an API typo should
        # return a JSON 404, not the HTML shell.
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        root = _FRONTEND_DIST.resolve()
        candidate = (root / full_path).resolve()
        if full_path and candidate.is_file() and root in candidate.parents:
            return FileResponse(candidate)

        # index.html must never be cached: it points at hash-named assets that
        # disappear on the next deploy, and a stale copy is a white screen.
        return FileResponse(
            _FRONTEND_DIST / "index.html",
            headers={"Cache-Control": "no-store"},
        )
