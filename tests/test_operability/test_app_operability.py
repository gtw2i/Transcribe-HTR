"""Operability guards for the FastAPI app itself.

A single FastAPI/uvicorn process serves the JSON API on /api/* and, when a
frontend build exists, the compiled React SPA on everything else. These tests
pin the two invariants that silently break that arrangement: the health
endpoint's path, and the registration order that keeps the SPA catch-all from
shadowing every API route.
"""

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_backend_serves_the_health_endpoint():
    """/api/health must exist as a route in backend/main.py.

    Anything probing the app for liveness — a container orchestrator, a reverse
    proxy, an uptime monitor — targets this path. Renaming or removing it breaks
    those probes without failing any other test.
    """
    backend = _read("backend/main.py")

    assert '@app.get("/api/health"' in backend


def test_backend_serves_the_spa_without_shadowing_the_api():
    """The SPA catch-all must be registered last and must reject /api/* itself."""
    content = _read("backend/main.py")

    assert 'app.mount(\n        "/assets"' in content or 'app.mount("/assets"' in content
    assert '@app.get("/{full_path:path}"' in content
    assert 'full_path.startswith("api/")' in content

    # Registration order is what keeps /api/* reachable: every include_router
    # call must appear before the catch-all route.
    catch_all = content.index('@app.get("/{full_path:path}"')
    assert content.rindex("app.include_router(") < catch_all
