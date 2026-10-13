"""Tests for backend/core/app_paths.py — the single source of filesystem locations.

The desktop app runs from a read-only bundle with an arbitrary working
directory, possibly on a computer shared by several accounts. These tests pin
the properties that make that work: resources resolve against the source tree
or the bundle (never the cwd), user locations are per-user and absolute, and
every location honours its environment override.
"""

import sys
from pathlib import Path

import pytest

import app_paths

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestResources:
    def test_resource_root_is_the_repo_root_from_source(self):
        assert app_paths.resource_root() == REPO_ROOT

    @pytest.mark.parametrize(
        "path_fn",
        [
            app_paths.bundled_profiles_dir,
            app_paths.templates_dir,
            app_paths.entity_schema_path,
        ],
    )
    def test_shipped_resources_exist(self, path_fn):
        assert path_fn().exists()

    def test_resources_do_not_depend_on_the_working_directory(self, tmp_path, monkeypatch):
        before = app_paths.entity_schema_path()
        monkeypatch.chdir(tmp_path)
        assert app_paths.entity_schema_path() == before

    def test_frozen_bundle_resolves_against_meipass(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
        assert app_paths.is_frozen()
        assert app_paths.resource_root() == tmp_path
        assert app_paths.bundled_profiles_dir() == tmp_path / "backend" / "profiles"
        assert app_paths.entity_schema_path() == tmp_path / "entity-data" / "entity_schema_v2.json"

    def test_frontend_dist_honours_its_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FRONTEND_DIST", str(tmp_path))
        assert app_paths.frontend_dist_dir() == tmp_path

    def test_frontend_dist_defaults_into_the_resource_tree(self, monkeypatch):
        monkeypatch.delenv("FRONTEND_DIST", raising=False)
        assert app_paths.frontend_dist_dir() == REPO_ROOT / "frontend" / "dist"


class TestUserLocations:
    @pytest.mark.parametrize(
        "env_var, path_fn",
        [
            ("TRANSCRIBE_HTR_DATA_DIR", app_paths.user_data_dir),
            ("TRANSCRIBE_HTR_LOG_DIR", app_paths.user_log_dir),
            ("TRANSCRIBE_HTR_CACHE_DIR", app_paths.user_cache_dir),
        ],
    )
    def test_each_location_honours_its_override(self, env_var, path_fn, tmp_path, monkeypatch):
        monkeypatch.setenv(env_var, str(tmp_path / "x"))
        assert path_fn() == tmp_path / "x"

    @pytest.mark.parametrize(
        "env_var, path_fn",
        [
            ("TRANSCRIBE_HTR_DATA_DIR", app_paths.user_data_dir),
            ("TRANSCRIBE_HTR_LOG_DIR", app_paths.user_log_dir),
            ("TRANSCRIBE_HTR_CACHE_DIR", app_paths.user_cache_dir),
        ],
    )
    def test_defaults_are_absolute_per_user_paths(self, env_var, path_fn, monkeypatch):
        monkeypatch.delenv(env_var, raising=False)
        path = path_fn()
        assert path.is_absolute()
        assert app_paths.APP_NAME in path.parts
        # Per-user: inside the current account's home directory.
        assert Path.home() in path.parents

    def test_windows_data_is_local_not_roaming(self, monkeypatch):
        if sys.platform != "win32":
            pytest.skip("Windows-specific")
        monkeypatch.delenv("TRANSCRIBE_HTR_DATA_DIR", raising=False)
        assert "Roaming" not in app_paths.user_data_dir().parts

    def test_derived_locations_follow_their_parent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TRANSCRIBE_HTR_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("TRANSCRIBE_HTR_CACHE_DIR", str(tmp_path / "cache"))
        assert app_paths.user_profiles_dir() == tmp_path / "data" / "profiles"
        assert app_paths.tts_cache_dir() == tmp_path / "cache" / "audio"


def test_logging_uses_the_per_user_log_directory():
    from logging_config import LOG_DIRECTORY

    assert LOG_DIRECTORY == app_paths.user_log_dir()
    assert LOG_DIRECTORY.is_absolute()
