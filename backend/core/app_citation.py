# app_citation.py
"""
How to cite Transcribe-HTR: the one copy the app uses.

Written into every new document's JSON and into every JSON/TXT/DOCX export.
CITATION.cff and README.md carry the same reference for people and for
GitHub's "Cite this repository"; tests/test_hygiene/test_citation_consistency.py
keeps all three in step.
"""

CITATION_DOI = "10.1145/3805696.3848486"

CITATION = (
    "West, G., Wallin, J., Brusuelas, J., & Fialka, A. (2026). "
    "Transcribe-HTR: An Auditable, LLM-Based Historical Document Intelligence Platform. "
    "In Proceedings of the 26th ACM/IEEE Joint Conference on Digital Libraries (JCDL '26), "
    f"Article 141, 1-4. https://doi.org/{CITATION_DOI}"
)
