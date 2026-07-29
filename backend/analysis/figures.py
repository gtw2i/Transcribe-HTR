"""Publication-quality heat-map rendering for export (§26, D5).

The interactive heat map is a CSS grid in the browser; this module produces the
static figures that go into a paper or a talk. Both read the same values from
the report, so the on-screen and exported figures cannot disagree.

matplotlib is imported with the non-interactive Agg backend: this runs inside a
web request, with no display and no GUI event loop.
"""

from __future__ import annotations

import io
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

#: 300 dpi is the usual floor for print figures.
DPI = 300

#: Single-hue sequential ramp, light = agreement, matching the on-screen map.
_CMAP = LinearSegmentedColormap.from_list(
    "disagreement", ["#ffffff", "#ffd4d4", "#ff8080", "#ff4b4b", "#a01010"]
)

#: Cells above the colour cap are drawn in this hue and annotated, so one
#: extreme pair cannot flatten the rest of the map (§8).
_OFFSCALE_COLOR = "#7b2d8e"


def render_heatmap(
    matrix: Sequence[Sequence[Optional[float]]],
    attempt_ids: Sequence[str],
    labels: Optional[Dict[str, str]] = None,
    title: str = "Pairwise disagreement",
    percentile: float = 95.0,
    fmt: str = "png",
) -> bytes:
    """Render one symmetric matrix as a labelled heat map.

    Returns the encoded image bytes. *fmt* is ``png`` or ``svg``.
    """
    label_for = labels or {}
    names = [label_for.get(a, a) for a in attempt_ids]
    n = len(names)

    values = [[0.0 if v is None else float(v) for v in row] for row in matrix]
    off_diagonal = sorted(
        values[i][j] for i in range(n) for j in range(n) if i != j
    )
    raw_max = off_diagonal[-1] if off_diagonal else 0.0
    if off_diagonal:
        index = min(len(off_diagonal) - 1, max(0, int(percentile / 100 * len(off_diagonal)) - 1))
        cap = off_diagonal[index]
    else:
        cap = 0.0
    vmax = max(cap, 1e-4)
    clipped = raw_max > vmax

    size = max(4.0, 0.75 * n + 2.2)
    fig, ax = plt.subplots(figsize=(size, size * 0.85), dpi=DPI)

    image = ax.imshow(values, cmap=_CMAP, vmin=0.0, vmax=vmax)

    ax.set_xticks(range(n), labels=names, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(n), labels=names, fontsize=8)
    ax.set_title(title, fontsize=11, pad=12)

    for i in range(n):
        for j in range(n):
            value = values[i][j]
            if i == j:
                ax.text(j, i, "0", ha="center", va="center", fontsize=7, color="#808495")
                continue
            over = value > vmax
            if over:
                ax.add_patch(
                    plt.Rectangle(
                        (j - 0.5, i - 0.5), 1, 1, facecolor=_OFFSCALE_COLOR, edgecolor="none"
                    )
                )
            shade = value / vmax if vmax else 0.0
            color = "white" if over or shade > 0.6 else "#31333f"
            ax.text(j, i, f"{value * 100:.1f}", ha="center", va="center", fontsize=7, color=color)

    bar = fig.colorbar(image, ax=ax, fraction=0.045, pad=0.03)
    bar.ax.tick_params(labelsize=7)
    bar.set_label("disagreement", fontsize=8)

    if clipped:
        fig.text(
            0.5,
            0.02,
            f"Colour scale capped at {vmax * 100:.1f}%; "
            f"cells above it are shown in purple (highest pair {raw_max * 100:.1f}%).",
            ha="center",
            fontsize=7,
            color="#808495",
        )

    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format=fmt, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return buffer.getvalue()


def render_report_figures(
    report: Dict, labels: Optional[Dict[str, str]] = None
) -> List[Tuple[str, bytes]]:
    """Both heat maps, as ``(filename, bytes)``, in PNG and SVG (§26)."""
    results = report["results"]
    ids = report["attempts_included"]

    figures: List[Tuple[str, bytes]] = []
    for metric, matrix_key, title in (
        ("cer", "matrix_cer_symmetric", "Pairwise CER disagreement"),
        ("wer", "matrix_wer_symmetric", "Pairwise WER disagreement"),
    ):
        for fmt in ("png", "svg"):
            figures.append(
                (
                    f"heatmap_{metric}.{fmt}",
                    render_heatmap(
                        results[matrix_key], ids, labels, title=title, fmt=fmt
                    ),
                )
            )
    return figures
