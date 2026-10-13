"""Development launcher: python run.py from inside backend/.

Loads <repo>/.env if present (via uvicorn's --env-file), so the keys and flags
documented in .env.example take effect. This is for development only: the
desktop launcher never reads .env, and .env is never bundled.
"""
import subprocess
import sys
from pathlib import Path


def build_command(backend_dir: Path) -> list[str]:
    cmd = [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"]
    env_file = backend_dir.parent / ".env"
    if env_file.is_file():
        cmd += ["--env-file", str(env_file)]
    return cmd


if __name__ == "__main__":
    backend_dir = Path(__file__).parent
    subprocess.run(build_command(backend_dir), cwd=str(backend_dir))
