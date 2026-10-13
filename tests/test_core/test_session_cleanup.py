"""SessionWorkspace.cleanup_session must only ever delete its own session dir.

It used to rmtree(workspace_path.parent). For the temp layout that is the
session directory, but for a workspace placed anywhere else it is whatever
directory happens to contain it — for a persistent desktop workspace at
<user data>/workspace, that would be the user's entire data directory.
"""

from core.session_workspace import SessionWorkspace


def test_cleanup_removes_only_the_session_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_SESSION_ROOT", str(tmp_path))
    keep = SessionWorkspace("keep")
    gone = SessionWorkspace("gone")
    keep.ensure_workspace()
    gone.ensure_workspace()

    gone.cleanup_session()

    assert not (tmp_path / "sessions" / "gone").exists()
    assert keep.workspace_path.exists()
    assert (tmp_path / "sessions").exists()


def test_cleanup_refuses_a_workspace_outside_the_session_root(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_SESSION_ROOT", str(tmp_path / "root"))
    data_dir = tmp_path / "user_data"
    (data_dir / "profiles").mkdir(parents=True)
    (data_dir / "profiles" / "mine.yaml").write_text("name: x", encoding="utf-8")
    ws = SessionWorkspace("desktop")
    ws.workspace_path = data_dir / "workspace"
    ws.workspace_path.mkdir()

    ws.cleanup_session()

    assert (data_dir / "profiles" / "mine.yaml").exists()
    assert ws.workspace_path.exists()


def test_cleanup_refuses_a_traversing_session_id(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_SESSION_ROOT", str(tmp_path / "root"))
    victim = tmp_path / "victim"
    victim.mkdir()
    ws = SessionWorkspace("../../victim")
    ws.workspace_path = victim / "workspace"
    ws.workspace_path.mkdir()

    ws.cleanup_session()

    assert victim.exists()
