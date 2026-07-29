"""Exportable results (§26).

Builds a bundle suitable for research use: CSV for statistics packages, JSON for
programmatic reuse, PNG and SVG at 300 dpi for publication, and the consensus
and normalized texts.

Every file in the bundle is derivable from ``analysis.json`` alone — that record
is the reproducibility anchor (§25, §27), and the rest is convenience.

Only the figure rendering needs matplotlib; the CSVs are written with the
standard library, so the export path adds no dependency of its own.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from .consensus import CONSENSUS_COMPARISON_CAVEAT
from .metrics import PreparedText

#: What a caller may ask for. "all" is the full bundle.
SECTIONS = ("all", "numerical", "text", "figures", "json")


def _safe(name: str) -> str:
    """Attempt ids contain a colon, which is not a legal Windows filename."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _csv_bytes(header: Sequence[str], rows: Sequence[Sequence]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _matrix_csv(matrix, ids: Sequence[str], labels: Dict[str, str], orientation: str) -> bytes:
    header = [orientation] + [labels.get(a, a) for a in ids]
    rows = [
        [labels.get(row_id, row_id)] + ["" if v is None else v for v in matrix[i]]
        for i, row_id in enumerate(ids)
    ]
    return _csv_bytes(header, rows)


def build_numerical_files(report: Dict, labels: Dict[str, str]) -> List[Tuple[str, bytes]]:
    """The eight numerical artifacts §26 requires, as CSV."""
    results = report["results"]
    ids = report["attempts_included"]
    files: List[Tuple[str, bytes]] = []

    files.append(
        ("matrix_cer_symmetric.csv", _matrix_csv(results["matrix_cer_symmetric"], ids, labels, "attempt"))
    )
    files.append(
        ("matrix_wer_symmetric.csv", _matrix_csv(results["matrix_wer_symmetric"], ids, labels, "attempt"))
    )
    files.append(
        (
            "matrix_cer_directional.csv",
            _matrix_csv(results["matrix_cer_directional"], ids, labels, "reference\\hypothesis"),
        )
    )
    files.append(
        (
            "matrix_wer_directional.csv",
            _matrix_csv(results["matrix_wer_directional"], ids, labels, "reference\\hypothesis"),
        )
    )

    files.append((
        "per_attempt_summary.csv",
        _csv_bytes(
            ["attempt_id", "label", "mean_cer", "median_cer", "min_cer", "max_cer",
             "mean_wer", "median_wer", "min_wer", "max_wer"],
            [
                [s["attempt_id"], labels.get(s["attempt_id"], s["attempt_id"]),
                 s["mean_cer"], s["median_cer"], s["min_cer"], s["max_cer"],
                 s["mean_wer"], s["median_wer"], s["min_wer"], s["max_wer"]]
                for s in results["per_attempt"]
            ],
        ),
    ))

    overall_rows = []
    for metric in ("cer", "wer"):
        summary = results[metric]
        variability = results["variability"][metric]
        overall_rows.append([
            metric.upper(), summary["n_attempts"], summary["n_pairs"],
            summary["mean"], summary["median"], summary["sd"],
            summary["iqr"][0], summary["iqr"][1], summary["min"], summary["max"],
            variability["uncertainty"]["method"],
            variability["uncertainty"]["value"] if variability["uncertainty"]["applicable"] else "",
        ])
    files.append((
        "overall_summary.csv",
        _csv_bytes(
            ["metric", "n_attempts", "n_pairs", "mean", "median", "sd",
             "iqr_low", "iqr_high", "min", "max", "uncertainty_method", "uncertainty_value"],
            overall_rows,
        ),
    ))

    files.append((
        "pairwise_edit_counts.csv",
        _csv_bytes(
            ["a_id", "b_id", "char_distance", "char_substitutions", "char_deletions",
             "char_insertions", "len_a_chars", "len_b_chars", "cer_a_to_b", "cer_b_to_a",
             "cer_sym", "word_distance", "word_substitutions", "word_deletions",
             "word_insertions", "len_a_words", "len_b_words", "wer_a_to_b", "wer_b_to_a",
             "wer_sym"],
            [
                [p["a_id"], p["b_id"], p["char_distance"], p["char_substitutions"],
                 p["char_deletions"], p["char_insertions"], p["len_a_chars"], p["len_b_chars"],
                 "" if p["cer_a_to_b"] is None else p["cer_a_to_b"],
                 "" if p["cer_b_to_a"] is None else p["cer_b_to_a"],
                 p["cer_sym"], p["word_distance"], p["word_substitutions"],
                 p["word_deletions"], p["word_insertions"], p["len_a_words"], p["len_b_words"],
                 "" if p["wer_a_to_b"] is None else p["wer_a_to_b"],
                 "" if p["wer_b_to_a"] is None else p["wer_b_to_a"],
                 p["wer_sym"]]
                for p in results["pairwise"]
            ],
        ),
    ))

    files.append((
        "outlier_diagnostics.csv",
        _csv_bytes(
            ["attempt_id", "label", "status", "cer_status", "wer_status", "cer_score",
             "wer_score", "median_cer", "median_wer", "mean_cer", "mean_wer",
             "group_median_cer", "group_median_wer", "message"],
            [
                [v["attempt_id"], v["label"], v["status"], v["cer_status"], v["wer_status"],
                 v["cer_score"], v["wer_score"], v["median_cer"], v["median_wer"],
                 v["mean_cer"], v["mean_wer"], v["group_median_cer"], v["group_median_wer"],
                 v["message"]]
                for v in results["outliers"]["verdicts"]
            ],
        ),
    ))

    comparison = results.get("consensus_comparison") or []
    files.append((
        "consensus_comparison.csv",
        _csv_bytes(
            ["attempt_id", "label", "cer_vs_consensus", "wer_vs_consensus",
             "char_substitutions", "char_deletions", "char_insertions",
             "word_substitutions", "word_deletions", "word_insertions"],
            [
                [c["attempt_id"], labels.get(c["attempt_id"], c["attempt_id"]),
                 c["cer_vs_consensus"], c["wer_vs_consensus"],
                 c["char_substitutions"], c["char_deletions"], c["char_insertions"],
                 c["word_substitutions"], c["word_deletions"], c["word_insertions"]]
                for c in comparison
            ],
        ),
    ))

    return files


def build_text_files(
    report: Dict, prepared: Sequence[PreparedText], labels: Dict[str, str]
) -> List[Tuple[str, bytes]]:
    """Consensus, representative attempt, and the texts actually measured (§26)."""
    results = report["results"]
    files: List[Tuple[str, bytes]] = []

    consensus = results.get("consensus")
    if consensus and consensus.get("text"):
        files.append(("consensus_deterministic.txt", consensus["text"].encode("utf-8")))

    medoid_id = results.get("medoid_attempt_id")
    if medoid_id:
        match = next((p for p in prepared if p.attempt_id == medoid_id), None)
        if match:
            files.append((
                "representative_attempt.txt",
                (f"# Most representative existing transcription: "
                 f"{labels.get(medoid_id, medoid_id)}\n\n{match.original}").encode("utf-8"),
            ))

    for item in prepared:
        stem = _safe(item.attempt_id)
        files.append((f"originals/attempt_{stem}.txt", item.original.encode("utf-8")))
        files.append((f"normalized/attempt_{stem}.txt", item.normalized.encode("utf-8")))

    return files


def build_readme(report: Dict) -> bytes:
    """Method definitions and the terminology caveat, shipped with the data."""
    settings = report["settings"]
    results = report["results"]
    normalization = settings["normalization"]

    lines = [
        "CONSISTENCY ANALYSIS EXPORT",
        "===========================",
        "",
        f"Document:          {report['source_document']['root']}",
        f"Analysis id:       {report['analysis_id']}",
        f"Created:           {report['created_at']}",
        f"Analysis version:  {report['analysis_version']}",
        "",
        "WHAT THIS MEASURES",
        "------------------",
        "These figures describe how much repeated transcription attempts of the",
        "same document disagree with one another. They do NOT measure accuracy.",
        "Several attempts can agree closely and still be wrong in the same way,",
        "and an attempt that disagrees with the others may be the one that read",
        "the manuscript correctly. Measuring accuracy requires a verified",
        "reference transcription, which this analysis does not use.",
        "",
        "DEFINITIONS",
        "-----------",
        f"CER:        {settings['cer_definition']}",
        f"WER:        {settings['wer_definition']}",
        f"Symmetric:  {settings['symmetric_definition']}",
        f"Uncertainty:{settings['uncertainty_method']}",
        f"Backend:    {settings['backend']}",
        "",
        "NORMALIZATION",
        "-------------",
        f"Profile:  {normalization['label']} ({normalization['id']}, v{normalization['version']})",
        f"Steps:    {' -> '.join(normalization['steps'])}",
        f"Tokenizer:{settings['tokenizer']['id']}",
        "",
        "ATTEMPTS",
        "--------",
        f"Included ({results['n_attempts']}): {', '.join(report['attempts_included'])}",
    ]
    if report["attempts_excluded"]:
        lines.append("Excluded:")
        for excluded in report["attempts_excluded"]:
            lines.append(f"  {excluded['attempt_id']} ({excluded['reason']})")
    lines += [
        f"Unique pairwise comparisons: {results['n_pairs']}",
        "",
        "CONSENSUS",
        "---------",
    ]
    consensus = results.get("consensus")
    if consensus:
        lines.append(f"Method:   {consensus['method']}")
        lines.append(f"Backbone: {consensus['backbone_attempt_id']}")
    else:
        lines.append("No consensus was computed for this analysis.")
    lines += ["", CONSENSUS_COMPARISON_CAVEAT, "", "FILES", "-----",
              "analysis.json  the complete record; every other file derives from it",
              "numerical/     CSV tables for statistical software",
              "text/          consensus, representative attempt, and the measured texts",
              "figures/       heat maps at 300 dpi (PNG) and as vectors (SVG)",
              "summary.md     the research summary",
              ""]
    return "\n".join(lines).encode("utf-8")


def build_bundle(
    report: Dict,
    prepared: Sequence[PreparedText],
    labels: Optional[Dict[str, str]] = None,
    section: str = "all",
) -> Tuple[bytes, str, str]:
    """Assemble an export. Returns ``(data, filename, mime)``.

    *section* selects a subset: ``json`` returns the record alone, the others
    return a ZIP containing that part of the bundle.
    """
    if section not in SECTIONS:
        raise ValueError(f"Unknown export section {section!r}. Expected one of {SECTIONS}.")

    labels = labels or {}
    root = report["source_document"]["root"]
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    stem = f"{_safe(root)}_consistency_{stamp}"

    if section == "json":
        data = json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8")
        return data, f"{stem}.json", "application/json"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        if section in ("all", "json"):
            archive.writestr(
                f"{stem}/analysis.json",
                json.dumps(report, indent=2, ensure_ascii=False),
            )
        if section == "all":
            archive.writestr(f"{stem}/README.txt", build_readme(report))
            archive.writestr(f"{stem}/summary.md", _summary_markdown(report))

        if section in ("all", "numerical"):
            for name, payload in build_numerical_files(report, labels):
                archive.writestr(f"{stem}/numerical/{name}", payload)

        if section in ("all", "text"):
            for name, payload in build_text_files(report, prepared, labels):
                archive.writestr(f"{stem}/text/{name}", payload)

        if section in ("all", "figures"):
            from .figures import render_report_figures

            for name, payload in render_report_figures(report, labels):
                archive.writestr(f"{stem}/figures/{name}", payload)

    buffer.seek(0)
    return buffer.read(), f"{stem}.zip", "application/zip"


def _summary_markdown(report: Dict) -> bytes:
    results = report["results"]
    lines = [
        f"# Consistency analysis — {report['source_document']['root']}",
        "",
        report["narrative"],
        "",
        "## Headline figures",
        "",
        "| Metric | Median | IQR | Mean | SD |",
        "|---|---|---|---|---|",
    ]
    for metric in ("cer", "wer"):
        summary = results[metric]
        lines.append(
            f"| {metric.upper()} | {summary['median']:.4f} | "
            f"{summary['iqr'][0]:.4f}–{summary['iqr'][1]:.4f} | "
            f"{summary['mean']:.4f} | {summary['sd']:.4f} |"
        )
    lines += [
        "",
        f"{results['n_attempts']} attempts · {results['n_pairs']} unique pairwise comparisons",
        "",
        "> These figures describe consistency among repeated transcription attempts.",
        "> They do not establish accuracy, which would require a verified reference",
        "> transcription.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")
