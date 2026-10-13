"""Desktop settings: remembered API keys and app information.

The key endpoints exist only when the desktop launch token is active
(core/desktop_security.py), i.e. when every request is already proven to come
from this user's own app window. In web mode they return 404, so a deployed
server never hands out stored keys.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app_paths import user_data_dir, user_log_dir, user_workspace_dir
from app_version import APP_VERSION
from desktop_security import launch_token

router = APIRouter(tags=["settings"])


class KeyBody(BaseModel):
    key: str


def _require_desktop():
    if launch_token() is None:
        raise HTTPException(status_code=404, detail="Not Found")


def _store_and_provider(provider: str):
    from secret_store import check_provider, get_secret_store

    try:
        return get_secret_store(), check_provider(provider)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/app-info")
def app_info():
    info = {"version": APP_VERSION, "desktop": launch_token() is not None}
    if info["desktop"]:
        from secret_store import get_secret_store

        info.update(
            data_dir=str(user_data_dir()),
            workspace_dir=str(user_workspace_dir()),
            log_dir=str(user_log_dir()),
            secret_backend=get_secret_store().name,
        )
    return info


@router.get("/settings/keys")
def get_keys():
    """Return the remembered keys, so the UI can fill its key fields."""
    _require_desktop()
    from secret_store import PROVIDERS, get_secret_store

    store = get_secret_store()
    return {"backend": store.name, "keys": {p: store.get(p) or "" for p in PROVIDERS}}


@router.put("/settings/keys/{provider}")
def put_key(provider: str, body: KeyBody):
    _require_desktop()
    store, provider = _store_and_provider(provider)
    key = body.key.strip()
    if key:
        store.set(provider, key)
    else:
        store.delete(provider)
    return {"provider": provider, "stored": bool(key)}


@router.delete("/settings/keys/{provider}")
def delete_key(provider: str):
    _require_desktop()
    store, provider = _store_and_provider(provider)
    store.delete(provider)
    return {"provider": provider, "stored": False}
