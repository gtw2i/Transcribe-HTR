"""The citation must agree everywhere it is written down.

backend/core/app_citation.py is what the app writes into documents and
exports; CITATION.cff drives GitHub's "Cite this repository"; README.md is
what people read. A reference update has to change all three.
"""

from pathlib import Path

import yaml

from app_citation import CITATION, CITATION_DOI
from export_utils import build_v2_download_schema

REPO = Path(__file__).resolve().parents[2]
TITLE = "Transcribe-HTR: An Auditable, LLM-Based Historical Document Intelligence Platform"


def test_citation_file_names_the_paper():
    ref = yaml.safe_load((REPO / "CITATION.cff").read_text(encoding="utf-8"))["preferred-citation"]
    assert ref["doi"] == CITATION_DOI
    assert ref["title"] == TITLE
    assert [a["family-names"] for a in ref["authors"]] == ["West", "Wallin", "Brusuelas", "Fialka"]


def test_readme_and_app_cite_the_same_paper():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for text in (readme, CITATION):
        assert TITLE in text
        assert f"https://doi.org/{CITATION_DOI}" in text


def test_exports_carry_the_current_citation_even_for_old_documents():
    old_doc = {"metadata": {"citation": "West, G. & Wallin, J. (2026). Transcribe-HTR: An AI-powered tool"}, "runs": []}
    assert build_v2_download_schema(old_doc)["metadata"]["citation"] == CITATION
