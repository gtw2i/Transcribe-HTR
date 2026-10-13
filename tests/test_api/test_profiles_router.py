"""Tests for profile layering (bundled vs user) and the /api/profiles router.

Bundled profiles ship inside the app, which is read-only once installed, and
are shared by every account on the machine. User profiles live in the
current user's data directory. These tests pin that split, and that a slug can
never be used to read, write or delete files outside the profile directories.
"""

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import profile_manager as pm
from routers import profiles as profiles_router

VALID = {
    "name": "Sample",
    "system_prompt": "sys",
    "transcription_prompt": "transcribe {}",
    "harmonization_system_prompt": "hsys",
    "harmonization_prompt": "harmonize {}",
}


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled"
    bundled.mkdir()
    data = tmp_path / "data"
    monkeypatch.setattr(pm, "PROFILES_DIR", bundled)
    monkeypatch.setenv("TRANSCRIBE_HTR_DATA_DIR", str(data))
    # A bundled profile that does NOT declare template: true — it must still
    # be treated as read-only because it ships with the app.
    (bundled / "builtin.yaml").write_text(yaml.safe_dump({**VALID, "name": "Built-in"}), encoding="utf-8")
    return {"bundled": bundled, "user": data / "profiles", "root": tmp_path}


@pytest.fixture
def client(dirs):
    app = FastAPI()
    app.include_router(profiles_router.router, prefix="/api")
    return TestClient(app)


class TestLayering:
    def test_bundled_profiles_are_reported_as_templates(self, dirs):
        assert pm.load_profile("builtin")["template"] is True

    def test_saving_writes_to_the_user_directory_only(self, dirs):
        pm.save_profile("mine", VALID)
        assert (dirs["user"] / "mine.yaml").exists()
        assert not (dirs["bundled"] / "mine.yaml").exists()

    def test_list_merges_both_layers(self, dirs):
        pm.save_profile("mine", VALID)
        assert pm.list_profiles() == ["builtin", "mine"]

    def test_user_profiles_are_not_templates(self, dirs):
        pm.save_profile("mine", {**VALID, "template": True})
        assert not pm.load_profile("mine").get("template")

    def test_bundled_profiles_cannot_be_overwritten_or_shadowed(self, dirs):
        with pytest.raises(pm.ReadOnlyProfileError):
            pm.save_profile("builtin", VALID)
        assert not (dirs["user"] / "builtin.yaml").exists()

    def test_bundled_profiles_cannot_be_deleted(self, dirs):
        with pytest.raises(pm.ReadOnlyProfileError):
            pm.delete_profile("builtin")
        assert (dirs["bundled"] / "builtin.yaml").exists()


BAD_SLUGS = ["../evil", "..\\evil", "a/b", "../../x", "UPPER", "", "x" * 65, "sp ace", "dot.yaml"]


class TestSlugValidation:
    @pytest.mark.parametrize("slug", BAD_SLUGS)
    def test_bad_slugs_are_rejected(self, slug):
        assert not pm.is_valid_slug(slug)

    @pytest.mark.parametrize("slug", ["default_htr", "copy-of-civil-war", "a", "x" * 64])
    def test_good_slugs_are_accepted(self, slug):
        assert pm.is_valid_slug(slug)

    @pytest.mark.parametrize("slug", BAD_SLUGS)
    def test_bad_slugs_never_touch_the_filesystem(self, dirs, slug):
        with pytest.raises(pm.InvalidSlugError):
            pm.save_profile(slug, VALID)
        assert pm.load_profile(slug) is None
        written = [p for p in dirs["root"].rglob("*.yaml") if p.name != "builtin.yaml"]
        assert written == []


class TestRouter:
    def test_frontend_payload_shape_saves(self, client, dirs):
        # frontend/src/api/profiles.js sends {slug, data}
        res = client.post("/api/profiles", json={"slug": "mine", "data": VALID})
        assert res.status_code == 200
        assert (dirs["user"] / "mine.yaml").exists()

    def test_list_marks_bundled_as_template(self, client, dirs):
        client.post("/api/profiles", json={"slug": "mine", "data": VALID})
        listed = {p["slug"]: p["template"] for p in client.get("/api/profiles").json()}
        assert listed == {"builtin": True, "mine": False}

    def test_saving_over_a_bundled_profile_is_forbidden(self, client):
        res = client.post("/api/profiles", json={"slug": "builtin", "data": VALID})
        assert res.status_code == 403

    def test_traversal_slug_is_a_bad_request(self, client, dirs):
        res = client.post("/api/profiles", json={"slug": "../../evil", "data": VALID})
        assert res.status_code == 400
        assert not list(dirs["root"].parent.glob("evil.yaml"))

    def test_delete_user_profile(self, client, dirs):
        client.post("/api/profiles", json={"slug": "mine", "data": VALID})
        assert client.delete("/api/profiles/mine").status_code == 200
        assert not (dirs["user"] / "mine.yaml").exists()

    def test_delete_bundled_profile_is_forbidden(self, client):
        assert client.delete("/api/profiles/builtin").status_code == 403

    def test_get_with_invalid_slug_is_not_found(self, client):
        assert client.get("/api/profiles/UPPER").status_code == 404
