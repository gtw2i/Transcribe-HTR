"""Regenerate the pinned desktop dependency locks for every release platform.

    pip install uv
    python scripts/lock_desktop.py            # refresh both locks
    python scripts/lock_desktop.py --upgrade  # also move to newest allowed versions

uv resolves for a target platform without being on it, so both locks can be
produced from any machine. Each lock pins every package with hashes, so a
release build gets exactly the reviewed set (pip install --require-hashes).
Commit the lock changes together with whatever changed the inputs.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INPUT = REPO / "packaging" / "requirements-desktop.in"
PYTHON = "3.11"
TARGETS = {
    "windows-x64": "x86_64-pc-windows-msvc",
    "macos-arm64": "aarch64-apple-darwin",
}


def main() -> int:
    out_dir = REPO / "packaging" / "locks"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, platform in TARGETS.items():
        cmd = [
            sys.executable, "-m", "uv", "pip", "compile", str(INPUT.relative_to(REPO)),
            "--python-version", PYTHON,
            "--python-platform", platform,
            "--generate-hashes",
            "--no-header",
            "--output-file", f"packaging/locks/{name}.txt",
        ]
        if "--upgrade" in sys.argv:
            cmd.append("--upgrade")
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, cwd=REPO, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
