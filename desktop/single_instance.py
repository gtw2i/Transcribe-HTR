"""One running app per user account.

The lock file lives in the user's own data directory, so it is per user: on a
shared computer every account can run the app at the same time, while a second
launch by the same user hands over to the window that is already open. The
file also records the running instance's port and token so the second launch
can ask it to come to the front.

The OS lock (msvcrt on Windows, flock elsewhere) is released automatically if
the process dies, so a crash never leaves a stale lock behind.
"""

import json
import os
from pathlib import Path
from typing import Optional

if os.name == "nt":
    import msvcrt
else:
    import fcntl


class SingleInstance:
    def __init__(self, lock_path: Path):
        self.lock_path = Path(lock_path)
        self._fh = None

    def acquire(self) -> bool:
        """Take the lock. False if another instance of this user holds it."""
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.lock_path, "a+", encoding="utf-8")
        try:
            if os.name == "nt":
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def publish(self, port: int, token: str) -> None:
        """Record how a second launch can reach this instance."""
        # Written beside the lock file: on Windows the locked byte range of the
        # lock file cannot be read by another process.
        info = self.lock_path.with_suffix(".json")
        info.write_text(json.dumps({"port": port, "token": token, "pid": os.getpid()}), encoding="utf-8")
        if os.name == "posix":
            os.chmod(info, 0o600)

    def running_instance(self) -> Optional[dict]:
        try:
            return json.loads(self.lock_path.with_suffix(".json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            self.lock_path.with_suffix(".json").unlink(missing_ok=True)
            if os.name == "nt":
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._fh.close()
            self._fh = None
