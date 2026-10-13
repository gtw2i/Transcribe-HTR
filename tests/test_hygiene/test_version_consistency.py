"""The version string must agree everywhere it is written down.

<repo>/VERSION is the single source of truth. The copies in pyproject.toml,
frontend/package.json and CITATION.cff exist because each tool reads its own
file; this test makes a release fail if one was not bumped. The release
workflow separately checks that the git tag matches VERSION.
"""

import json
import re
from pathlib import Path

import yaml

from app_version import APP_VERSION

REPO = Path(__file__).resolve().parents[2]
VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()


def test_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", VERSION), VERSION


def test_backend_reports_the_version_file():
    assert APP_VERSION == VERSION


def test_pyproject_matches():
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1) == VERSION


def test_package_json_matches():
    pkg = json.loads((REPO / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert pkg["version"] == VERSION


def test_citation_matches():
    cff = yaml.safe_load((REPO / "CITATION.cff").read_text(encoding="utf-8"))
    assert str(cff["version"]) == VERSION


def test_changelog_has_an_entry_for_the_version():
    changelog = (REPO / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{VERSION}]" in changelog
