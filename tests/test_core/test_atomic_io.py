"""Crash-safe writes (backend/core/atomic_io.py).

A failed write must leave the previous file intact and leave no temp file
that the workspace scan (top-level *.json) could mistake for a document.
"""

import json
import os

import pytest

import atomic_io
import json_manager


def test_writes_and_replaces(tmp_path):
    target = tmp_path / "doc.transcription.json"
    atomic_io.atomic_write_json(target, {"v": 1})
    atomic_io.atomic_write_json(target, {"v": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 2}
    assert [p.name for p in tmp_path.iterdir()] == ["doc.transcription.json"]


def test_failure_keeps_the_old_file_and_cleans_up(tmp_path):
    target = tmp_path / "doc.transcription.json"
    atomic_io.atomic_write_json(target, {"v": 1})

    with pytest.raises(TypeError):
        atomic_io.atomic_write_json(target, {"v": object()})  # not serializable

    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["doc.transcription.json"]


def test_failure_during_replace_keeps_the_old_file(tmp_path, monkeypatch):
    target = tmp_path / "doc.transcription.json"
    atomic_io.atomic_write_json(target, {"v": 1})

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        atomic_io.atomic_write_json(target, {"v": 2})

    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 1}
    assert not list(tmp_path.glob("*.tmp")) and not list(tmp_path.glob(".*.tmp"))


def test_transient_windows_lock_is_retried(tmp_path, monkeypatch):
    target = tmp_path / "doc.json"
    real_replace = os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("held by antivirus")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    atomic_io.atomic_write_json(target, {"ok": True})
    assert calls["n"] == 3
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_temp_files_are_invisible_to_the_workspace_scan(tmp_path):
    (tmp_path / ".doc.transcription.json.abc123.tmp").write_text("{}", encoding="utf-8")
    assert list(tmp_path.glob("*.json")) == []


def test_json_manager_uses_atomic_writes():
    # Guard against regressions to in-place writes of document JSON.
    import inspect

    source = inspect.getsource(json_manager)
    assert 'open(json_path, "w"' not in source
    assert "atomic_write_json" in source
