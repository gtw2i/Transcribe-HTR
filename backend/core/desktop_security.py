# desktop_security.py
"""
Local-server hardening for the desktop app.

The desktop app runs this backend on 127.0.0.1. Loopback is not private:
every other account logged in to the same computer (Fast User Switching,
Remote Desktop) and every web page open in any browser can send requests to
it. Without protection, they could read the user's documents or spend the
user's stored API keys.

When the launcher sets TRANSCRIBE_HTR_LAUNCH_TOKEN (a fresh random value per
launch), main.py enables:

* LaunchTokenMiddleware: every request must carry the token, either in the
  HttpOnly cookie set by AUTH_PATH or in the X-HTR-Token header (used by the
  launcher itself). Only /api/health and AUTH_PATH are open.
* TrustedHostMiddleware with ALLOWED_HOSTS: rejects DNS-rebinding requests,
  whose Host header names the attacker's domain.
* No /docs, /redoc or /openapi.json, and no dev CORS origins.

The window first opens AUTH_PATH?token=..., which sets the cookie and moves
to "/". The cookie is set from a 200 response rather than a redirect because
WebKit has dropped cookies set on redirects.

Without the token (web mode, development, tests) none of this is active.
"""

import hmac
import os
from typing import Optional

from starlette.requests import Request
from starlette.responses import HTMLResponse, PlainTextResponse

ENV_TOKEN = "TRANSCRIBE_HTR_LAUNCH_TOKEN"
COOKIE_NAME = "htr_desktop_auth"
HEADER_NAME = "x-htr-token"
AUTH_PATH = "/api/desktop/auth"
OPEN_PATHS = frozenset({"/api/health", AUTH_PATH})
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]


def launch_token() -> Optional[str]:
    return os.getenv(ENV_TOKEN) or None


def _matches(supplied: Optional[str], token: str) -> bool:
    return bool(supplied) and hmac.compare_digest(supplied.encode(), token.encode())


class LaunchTokenMiddleware:
    """Pure ASGI middleware: 403 unless the request carries the launch token."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] in OPEN_PATHS:
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        supplied = request.headers.get(HEADER_NAME) or request.cookies.get(COOKIE_NAME)
        if _matches(supplied, self.token):
            await self.app(scope, receive, send)
            return
        await PlainTextResponse("Forbidden", status_code=403)(scope, receive, send)


def make_auth_endpoint(token: str):
    def desktop_auth(request: Request):
        if not _matches(request.query_params.get("token"), token):
            return PlainTextResponse("Forbidden", status_code=403)
        response = HTMLResponse(
            "<!doctype html><meta charset=utf-8><title>Transcribe-HTR</title>"
            "<script>location.replace('/')</script>",
            headers={"Cache-Control": "no-store"},
        )
        response.set_cookie(
            COOKIE_NAME, token, httponly=True, samesite="strict", path="/"
        )
        return response

    return desktop_auth
