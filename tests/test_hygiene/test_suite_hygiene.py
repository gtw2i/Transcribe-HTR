import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = ROOT / "tests"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _test_py_files() -> list[Path]:
    return [
        p
        for p in TESTS_DIR.rglob("test_*.py")
        if p.is_file() and p.name != "__init__.py"
    ]


def test_pytest_ini_enforces_strict_collection_rules():
    content = _read(ROOT / "pytest.ini")

    assert "--strict-markers" in content
    assert "--strict-config" in content
    assert "python_files = test_*.py" in content


def test_hygiene_suite_is_discoverable_in_current_structure():
    assert (TESTS_DIR / "test_hygiene").exists()
    assert (TESTS_DIR / "test_hygiene" / "test_suite_hygiene.py").exists()


def test_no_broken_test_files_remaining():
    broken = list(TESTS_DIR.rglob("*.broken"))
    assert broken == []


def _has_direct_non_none_return(func_node):
    """Return True if func_node has a non-None return NOT inside a nested function/class."""
    pending = list(func_node.body)
    while pending:
        node = pending.pop()
        if isinstance(node, ast.Return) and node.value is not None:
            return True
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue  # don't descend into nested scopes
        pending.extend(ast.iter_child_nodes(node))
    return False


def test_test_functions_do_not_return_non_none_values():
    offenders = []

    for path in _test_py_files():
        tree = ast.parse(_read(path), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                if _has_direct_non_none_return(node):
                    offenders.append(f"{path}:{node.name}")

    assert offenders == []


def test_placeholder_example_tests_are_retired_from_active_suite():
    path = TESTS_DIR / "tests_example.py"
    if not path.exists():
        return  # File deleted — placeholder tests have been retired
    src = _read(path)
    assert "test_always_passes" not in src
