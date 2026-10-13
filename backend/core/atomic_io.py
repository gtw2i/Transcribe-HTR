# atomic_io.py
"""
Crash-safe file writes.

Writing a document's JSON in place means a crash, power cut or full disk part
way through leaves a truncated file, and with a persistent workspace that is
the user's only copy of their results. These helpers write to a temporary
file in the same directory, fsync it, then os.replace() it over the target,
which is atomic on both NTFS and APFS: readers see either the old file or the
new one, never a partial one.

The temp file is named ".<name>.<random>.tmp" so the workspace scan (which
globs top-level *.json) never mistakes it for a document.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


def _replace(src: str, dst: Path, attempts: int = 10, delay: float = 0.05) -> None:
    for attempt in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            # Windows: an antivirus scanner or the search indexer can hold the
            # target open for a moment. Retry briefly before giving up.
            if attempt == attempts - 1:
                raise
            time.sleep(delay * (attempt + 1))


def atomic_write_bytes(path, data: bytes) -> None:
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        _replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def atomic_write_text(path, text: str, encoding: str = "utf-8") -> None:
    atomic_write_bytes(path, text.encode(encoding))


def atomic_write_json(path, obj: Any, **dump_kwargs) -> None:
    atomic_write_text(path, json.dumps(obj, **dump_kwargs))
