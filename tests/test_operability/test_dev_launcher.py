"""backend/run.py must load <repo>/.env when it exists.

README and .env.example tell developers to put keys in .env, but nothing
loaded it, so the values only took effect if the shell exported them.
"""

import importlib.util
from pathlib import Path

RUN_PY = Path(__file__).resolve().parents[2] / "backend" / "run.py"


def _load_run():
    spec = importlib.util.spec_from_file_location("dev_run", RUN_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_env_file_is_passed_when_present(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    (tmp_path / ".env").write_text("OPENAI_API_KEY=x\n", encoding="utf-8")

    cmd = _load_run().build_command(backend)

    assert cmd[cmd.index("--env-file") + 1] == str(tmp_path / ".env")


def test_no_env_file_flag_without_a_file(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()

    assert "--env-file" not in _load_run().build_command(backend)
