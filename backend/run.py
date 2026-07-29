"""Convenience launcher: python run.py from inside backend/."""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    backend_dir = Path(__file__).parent
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "main:app", "--reload", "--port", "8000"],
        cwd=str(backend_dir),
    )
