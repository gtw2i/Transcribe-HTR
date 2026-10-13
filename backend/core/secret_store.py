# secret_store.py
"""
Remembered API keys for the desktop app, one entry per provider.

Two backends behind one small interface:

* "keyring": the OS credential store, i.e. Windows Credential Manager or the
  macOS login Keychain, selected explicitly (keyring's auto-discovery can fail
  in a frozen app).
* "file": <user data>/secrets.json, readable only by its owner (0600 on POSIX;
  on Windows the per-user AppData ACL already restricts it to the user).

Default backend: keyring on Windows, file elsewhere. macOS ties a Keychain
item's access to the app's code signature, and an unsigned (ad-hoc signed)
build gets a new signature on every update, so the Keychain would ask for the
user's password after every update. Signed macOS builds set
TRANSCRIBE_HTR_SECRET_BACKEND=keyring. If the keyring cannot be used, the
file backend is used instead.

Both backends are per user: on a shared computer every account has its own.
"""

import json
import logging
import os
import sys
from typing import Dict, Optional

from app_paths import user_data_dir
from atomic_io import atomic_write_text

logger = logging.getLogger(__name__)

PROVIDERS = ("openai", "gemini", "anthropic")
SERVICE = "Transcribe-HTR"
ENV_BACKEND = "TRANSCRIBE_HTR_SECRET_BACKEND"


class FileSecretStore:
    name = "file"

    def _path(self):
        return user_data_dir() / "secrets.json"

    def _load(self) -> Dict[str, str]:
        try:
            data = json.loads(self._path().read_text(encoding="utf-8"))
            return {k: v for k, v in data.items() if k in PROVIDERS and isinstance(v, str)}
        except (OSError, ValueError):
            return {}

    def _save(self, data: Dict[str, str]) -> None:
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(data))
        if os.name == "posix":
            os.chmod(path, 0o600)

    def get(self, provider: str) -> Optional[str]:
        return self._load().get(provider)

    def set(self, provider: str, key: str) -> None:
        data = self._load()
        data[provider] = key
        self._save(data)

    def delete(self, provider: str) -> None:
        data = self._load()
        if data.pop(provider, None) is not None:
            self._save(data)


class KeyringSecretStore:
    name = "keyring"

    def __init__(self):
        import keyring

        if sys.platform == "win32":
            from keyring.backends.Windows import WinVaultKeyring

            keyring.set_keyring(WinVaultKeyring())
        elif sys.platform == "darwin":
            from keyring.backends.macOS import Keyring

            keyring.set_keyring(Keyring())
        self._keyring = keyring

    def get(self, provider: str) -> Optional[str]:
        return self._keyring.get_password(SERVICE, provider)

    def set(self, provider: str, key: str) -> None:
        self._keyring.set_password(SERVICE, provider, key)

    def delete(self, provider: str) -> None:
        try:
            self._keyring.delete_password(SERVICE, provider)
        except self._keyring.errors.PasswordDeleteError:
            pass


def _default_backend() -> str:
    return os.getenv(ENV_BACKEND, "").strip().lower() or ("keyring" if sys.platform == "win32" else "file")


def get_secret_store():
    if _default_backend() == "keyring":
        try:
            return KeyringSecretStore()
        except Exception as e:  # missing package, no backend, locked store
            logger.warning(f"OS credential store unavailable ({type(e).__name__}); using file store.")
    return FileSecretStore()


def check_provider(provider: str) -> str:
    provider = provider.lower()
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Expected one of: {', '.join(PROVIDERS)}.")
    return provider
