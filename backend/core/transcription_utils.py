import logging
import re
from html import escape

import matplotlib.cm as cm
import matplotlib.colors as mcolors
import numpy as np
from tqdm import tqdm

# Set up logger for this module
logger = logging.getLogger(__name__)


# --- Levenshtein & Alignment Functions ---
def levenshtein_distance(s1, s2):
    m = len(s1)
    n = len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[m][n]


def levenshtein_distance_pairwise(transcriptions, epsilon=1):
    n = len(transcriptions)
    levs = []
    levs_norm = []
    lev_matrix = np.zeros((n, n), dtype=int)
    lev_matrix_norm = np.zeros((n, n))
    for i, t1 in enumerate(transcriptions):
        for j, t2 in enumerate(transcriptions):
            if i < j:
                lev_distance = levenshtein_distance(t1, t2)
                levs.append(lev_distance)
                max_len = max(len(t1), len(t2))
                levs_norm.append(lev_distance / max_len)
                lev_matrix[i, j] = lev_distance
                lev_matrix[j, i] = lev_distance
                lev_matrix_norm[i, j] = (lev_distance + epsilon) / (max_len + epsilon)
                lev_matrix_norm[j, i] = (lev_distance + epsilon) / (max_len + epsilon)
    return levs, levs_norm, lev_matrix, lev_matrix_norm


def get_alignments(X, Y):
    m = len(X)
    n = len(Y)
    L = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0 or j == 0:
                L[i][j] = 0
            elif X[i - 1] == Y[j - 1]:
                L[i][j] = L[i - 1][j - 1] + 1
            else:
                L[i][j] = max(L[i - 1][j], L[i][j - 1])
    i = m
    j = n
    align_X = []
    align_Y = []
    while i > 0 and j > 0:
        if X[i - 1] == Y[j - 1]:
            align_X.append(X[i - 1])
            align_Y.append(Y[j - 1])
            i -= 1
            j -= 1
        elif L[i - 1][j] >= L[i][j - 1]:
            align_X.append(X[i - 1])
            align_Y.append("_")
            i -= 1
        else:
            align_X.append("_")
            align_Y.append(Y[j - 1])
            j -= 1
    while i > 0:
        align_X.append(X[i - 1])
        align_Y.append("_")
        i -= 1
    while j > 0:
        align_X.append("_")
        align_Y.append(Y[j - 1])
        j -= 1
    align_X.reverse()
    align_Y.reverse()
    return align_X, align_Y


def get_combined_alignment(align_X, align_Y):
    alignment = []
    for x, y in zip(align_X, align_Y):
        if x == y and x != "_":
            alignment.append(x)
        else:
            alignment.append("_")
    return "".join(alignment)


def align_strings(X, Y):
    align_X, align_Y = get_alignments(X, Y)
    combined_alignment = get_combined_alignment(align_X, align_Y)
    return combined_alignment


def progressive_alignment(variants):
    assert len(variants) >= 2, "Need at least two variants to align."
    aligned = variants[0]
    for i in tqdm(range(1, len(variants)), ncols=50):
        aligned = align_strings(aligned, variants[i])
        aligned = re.sub("_+", "_", aligned)
    return aligned


def get_alignments_with_agreement(X, Y):
    m, n = len(X), len(Y)
    L = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            L[i][j] = (
                L[i - 1][j - 1] + 1
                if X[i - 1] == Y[j - 1]
                else max(L[i - 1][j], L[i][j - 1])
            )
    i, j = m, n
    align_X, align_Y = [], []
    matched_pairs = []
    while i > 0 and j > 0:
        if X[i - 1] == Y[j - 1]:
            align_X.append(X[i - 1])
            align_Y.append(Y[j - 1])
            matched_pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif L[i - 1][j] >= L[i][j - 1]:
            align_X.append(X[i - 1])
            align_Y.append("_")
            i -= 1
        else:
            align_X.append("_")
            align_Y.append(Y[j - 1])
            j -= 1
    while i > 0:
        align_X.append(X[i - 1])
        align_Y.append("_")
        i -= 1
    while j > 0:
        align_X.append("_")
        align_Y.append(Y[j - 1])
        j -= 1
    align_X.reverse()
    align_Y.reverse()
    agree_X = [0] * m
    agree_Y = [0] * n
    for ix, jy in matched_pairs:
        agree_X[ix] = 1
        agree_Y[jy] = 1
    agree_X = np.array(agree_X)
    agree_Y = np.array(agree_Y)
    return agree_X, agree_Y


def compute_token_disagreement(transcriptions, level="word"):
    try:
        # Normalize input to a list of strings
        if transcriptions is None:
            transcriptions = []
        elif isinstance(transcriptions, str):
            transcriptions = [transcriptions]
        else:
            try:
                # Ensure iterability
                _ = len(transcriptions)
            except Exception:
                transcriptions = [str(transcriptions)]

        # Coerce each item to a string (keep None as empty string)
        transcriptions = [
            t if isinstance(t, str) else ("" if t is None else str(t))
            for t in transcriptions
        ]

        n_variants = len(transcriptions)

        # Log input information
        logger.debug(
            f"compute_token_disagreement called with {n_variants} transcriptions, level='{level}'"
        )
        for i, t in enumerate(transcriptions):
            logger.debug(
                f"Transcription {i}: length={len(t)}, preview='{t[:50]}{'...' if len(t) > 50 else ''}'"
            )

        # Filter out empty transcriptions and normalize
        valid_transcriptions = []
        for i, t in enumerate(transcriptions):
            if t and t.strip():  # Non-empty and not just whitespace
                valid_transcriptions.append(t.strip())
            else:
                logger.debug(f"Skipping empty/whitespace transcription {i}")

        n_valid = len(valid_transcriptions)

        logger.debug(f"Valid transcriptions: {n_valid} out of {n_variants}")

        if n_valid < 2:
            logger.debug(
                f"Not enough valid transcriptions for disagreement analysis (need at least 2, got {n_valid})"
            )
            # Return dummy vectors for all original transcriptions to maintain indexing
            result = []
            for t in transcriptions:
                try:
                    tokens = t.split() if level == "word" else list(t)
                    result.append(np.zeros(len(tokens)))
                except Exception:
                    result.append(np.zeros(0))
            return result

        if level == "word":
            tokenized = [t.split() for t in valid_transcriptions]
        elif level == "char":
            tokenized = [list(t) for t in valid_transcriptions]
        else:
            logger.debug(f"Invalid level '{level}', must be 'word' or 'char'")
            return [
                np.zeros(len(t.split() if level == "word" else list(t)))
                for t in transcriptions
            ]

        logger.debug(f"Tokenized lengths: {[len(tokens) for tokens in tokenized]}")

        # Compute disagreement for valid transcriptions
        valid_disagree = []
        for idx in range(n_valid):
            logger.debug(f"Processing variant {idx+1}/{n_valid}")
            agree_vector = np.zeros(len(tokenized[idx]))

            for i in range(n_valid):
                try:
                    agree_X, _ = get_alignments_with_agreement(
                        tokenized[idx], tokenized[i]
                    )
                    agree_vector += agree_X
                except Exception as e:
                    logger.debug(f"Error in alignment for variants {idx} and {i}: {e}")
                    # If alignment fails, assume no agreement
                    continue

            if n_valid > 0:
                agree_vector /= n_valid
            disagree_vector = 1 - agree_vector
            valid_disagree.append(disagree_vector)
            logger.debug(
                f"Variant {idx+1}: disagreement vector length = {len(disagree_vector)}"
            )

        # Now map back to original transcription indices
        result_disagree = []
        valid_idx = 0

        for i, original_transcription in enumerate(transcriptions):
            if original_transcription and original_transcription.strip():
                # This was a valid transcription, use the computed disagreement
                if valid_idx < len(valid_disagree):
                    result_disagree.append(valid_disagree[valid_idx])
                    valid_idx += 1
                else:
                    # Fallback: create zero vector
                    tokens = (
                        original_transcription.split()
                        if level == "word"
                        else list(original_transcription)
                    )
                    result_disagree.append(np.zeros(len(tokens)))
            else:
                # This was empty/invalid, create a zero-length vector
                result_disagree.append(np.zeros(0))

        logger.debug(f"Returning {len(result_disagree)} disagreement vectors")
        for i, vec in enumerate(result_disagree):
            logger.debug(f"Result vector {i}: length = {len(vec)}")

        return result_disagree

    except Exception as e:
        logger.error(f"Exception in compute_token_disagreement: {e}")
        # Return empty vectors as fallback
        return [np.zeros(0) for _ in transcriptions]
        import traceback

        traceback.print_exc()

        # Return dummy vectors for all transcriptions to prevent crashes
        safe_result = []
        try:
            for t in transcriptions or []:
                try:
                    tokens = t.split() if level == "word" else list(t)
                    safe_result.append(np.zeros(len(tokens)))
                except Exception:
                    safe_result.append(np.zeros(0))
        except Exception:
            # If even building safe_result fails, return a single empty vector to avoid length=0 surprises
            safe_result = [np.zeros(0)]
        return safe_result


# --- Colorization Functions ---
def colorize_words(
    sentence,
    values,
    *,
    pad_x=0,
    pad_y=0,
    gap_x=0,
    gap_y=0,
    radius=0,
    block_pad_x=0,
    block_pad_y=0,
    transparent_at=0.0,
    font_family="inherit",
):
    tokens = re.split(r"(\s+)", sentence)
    words_only = [tok for tok in tokens if not tok.isspace()]
    assert len(words_only) == len(values), (
        f"Number of values must match number of non-whitespace tokens: "
        f"{len(words_only)} tokens vs {len(values)} values"
    )
    custom_cmap = mcolors.LinearSegmentedColormap.from_list(
        "green_yellow_orange_red", ["green", "yellow", "orange", "red"]
    )
    norm = mcolors.Normalize(vmin=0, vmax=1)
    container_style = (
        f"white-space: pre-wrap; display: inline-block;"
        f"padding:{block_pad_y}px {block_pad_x}px;"
        f"font-family:{font_family};"
    )
    html = [f'<div style="{container_style}">']
    word_idx = 0
    for tok in tokens:
        if tok.isspace():
            html.append(tok.replace("\n", "<br>"))
        else:
            v = float(values[word_idx])
            rgba = custom_cmap(norm(v))
            alpha = 0.0 if v == float(transparent_at) else 0.4
            rgba_str = f"rgba({int(rgba[0]*255)}, {int(rgba[1]*255)}, {int(rgba[2]*255)}, {alpha})"
            span_style = (
                f"background-color:{rgba_str};"
                f"padding:{pad_y}px {pad_x}px;"
                f"margin:{gap_y}px {gap_x}px;"
                f"border-radius:{radius}px;"
            )
            html.append(f'<span style="{span_style}">{escape(tok)}</span>')
            word_idx += 1
    html.append("</div>")
    return "".join(html)


def colorize_chars(
    sentence,
    values,
    *,
    pad_x=0,
    pad_y=0,
    gap_x=0,
    gap_y=0,
    radius=0,
    block_pad_x=0,
    block_pad_y=0,
    transparent_at=0.0,
    font_family="inherit",
):
    chars = list(sentence)
    assert len(chars) == len(
        values
    ), f"Number of values must match number of characters: {len(chars)} vs {len(values)}"
    custom_cmap = mcolors.LinearSegmentedColormap.from_list(
        "green_yellow_orange_red", ["green", "yellow", "orange", "red"]
    )
    norm = mcolors.Normalize(vmin=0, vmax=1)
    container_style = (
        f"white-space: pre-wrap; display: inline-block;"
        f"padding:{block_pad_y}px {block_pad_x}px;"
        f"font-family:{font_family};"
    )
    html_out = [f'<div style="{container_style}">']
    for ch, val in zip(chars, values):
        if ch == "\n":
            html_out.append("<br>")
            continue
        v = float(val)
        rgba = custom_cmap(norm(v))
        alpha = 0.0 if v == float(transparent_at) else 0.4
        rgba_str = (
            f"rgba({int(rgba[0]*255)}, {int(rgba[1]*255)}, {int(rgba[2]*255)}, {alpha})"
        )
        span_style = (
            f"background-color:{rgba_str};"
            f"padding:{pad_y}px {pad_x}px;"
            f"margin:{gap_y}px {gap_x}px;"
            f"border-radius:{radius}px;"
        )
        html_out.append(f'<span style="{span_style}">{escape(ch)}</span>')
    html_out.append("</div>")
    return "".join(html_out)


# ---------------------------------------------------------------------------
# Gemini NER span detection — verbatim from NER_Gemini_Combined_04.ipynb
# ---------------------------------------------------------------------------

def find_all_occurrences(
    text: str,
    sub: str,
    case_sensitive: bool = True,
) -> list:
    if not sub:
        return []
    haystack = text if case_sensitive else text.lower()
    needle = sub if case_sensitive else sub.lower()
    matches = []
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            break
        matches.append({"start_char": idx, "end_char": idx + len(sub)})
        start = idx + len(sub)
    return matches


def build_spans_from_entity_bundle(
    entity_bundle: dict,
    transcriptions: list,
    case_sensitive: bool = True,
) -> dict:
    """
    For each entity, iterate over observed_variants and find all verbatim occurrences
    across all transcriptions. Enriches entity_bundle in-place with a text_spans list.
    Each text_spans entry: {transcription_id, match_text, occurrences, n_occurrences, valid}
    """
    for entity in entity_bundle.get("entities", []):
        text_spans = []
        seen: set = set()
        for variant in entity.get("observed_variants", []):
            for tid, transcription in enumerate(transcriptions):
                key = (tid, variant)
                if key in seen:
                    continue
                seen.add(key)
                occs = find_all_occurrences(transcription, variant, case_sensitive)
                if occs:
                    text_spans.append({
                        "transcription_id": tid,
                        "match_text": variant,
                        "occurrences": occs,
                        "n_occurrences": len(occs),
                        "valid": True,
                    })
        entity["text_spans"] = text_spans
    return entity_bundle


def colorize_ner_gemini(
    text: str,
    entity_bundle: dict,
    transcription_id: int,
    alpha: float = 0.4,
) -> str | None:
    """
    Colorize text using Gemini NER entity_bundle results.

    Builds character-level spans for the given transcription_id and returns
    an HTML string with inline legend. Returns None if no entities match.
    """
    # Build spans treating `text` as the sole transcription (id=0)
    import copy
    bundle = copy.deepcopy(entity_bundle)
    build_spans_from_entity_bundle(bundle, [text], case_sensitive=True)

    # Collect all spans for transcription_id=0, sorted by start position
    span_rows = []
    for entity in bundle.get("entities", []):
        eid = entity.get("entity_id", "")
        canonical = entity.get("canonical", "")
        for span in entity.get("text_spans", []):
            if not span.get("valid", False):
                continue
            for occ in span.get("occurrences", []):
                span_rows.append({
                    "entity_id": eid,
                    "canonical": canonical,
                    "start_char": occ["start_char"],
                    "end_char": occ["end_char"],
                    "match_text": span["match_text"],
                })

    if not span_rows:
        return None

    # Sort by start, resolve overlaps (keep longest at each start position)
    span_rows.sort(key=lambda r: (r["start_char"], -(r["end_char"] - r["start_char"])))
    deduped = []
    last_end = 0
    for row in span_rows:
        if row["start_char"] >= last_end:
            deduped.append(row)
            last_end = row["end_char"]

    # Assign colors from tab10 keyed by entity_id
    unique_eids = list(dict.fromkeys(r["entity_id"] for r in deduped))
    n = max(len(unique_eids), 1)
    cmap = cm.get_cmap("tab10", n)
    eid_rgba: dict = {}
    eid_hex: dict = {}
    for i, eid in enumerate(unique_eids):
        r, g, b, _ = cmap(i)
        eid_rgba[eid] = f"rgba({int(r * 255)},{int(g * 255)},{int(b * 255)},{alpha})"
        eid_hex[eid] = mcolors.to_hex((r, g, b))

    # Build highlighted HTML
    container_style = "white-space:pre-wrap; display:inline-block; font-family:inherit; line-height:1.4;"
    parts = [f'<div style="{container_style}">']
    pos = 0
    for row in deduped:
        sc, ec = row["start_char"], row["end_char"]
        if sc > pos:
            parts.append(escape(text[pos:sc]))
        color = eid_rgba.get(row["entity_id"], "transparent")
        parts.append(
            f'<span style="background-color:{color}; padding:0 2px; border-radius:2px;">'
            f'{escape(text[sc:ec])}</span>'
        )
        pos = ec
    if pos < len(text):
        parts.append(escape(text[pos:]))
    parts.append("</div>")

    # Build legend
    legend_items = []
    for eid in unique_eids:
        canonical = next((r["canonical"] for r in deduped if r["entity_id"] == eid), eid)
        swatch = (
            f'<span style="display:inline-block; width:0.9em; height:0.9em; '
            f'background:{eid_hex[eid]}; border-radius:2px; margin-right:0.4em;"></span>'
        )
        legend_items.append(
            f'<div style="margin-right:1em; margin-bottom:0.3em; display:flex; align-items:center;">'
            f'{swatch}{escape(f"{eid}: {canonical}")}</div>'
        )
    legend_html = (
        '<div style="margin-top:0.5em; display:flex; flex-wrap:wrap; '
        'align-items:center; font-size:0.9em;">' + "".join(legend_items) + "</div>"
    )
    parts.append(legend_html)

    return "".join(parts)


def colorize_ner(
    sentence: str,
    nlp_model,
    *,
    alpha: float = 0.4,
    pad_x: int = 0,
    pad_y: int = 0,
    gap_x: int = 0,
    gap_y: int = 0,
    radius: int = 0,
    block_pad_x: int = 0,
    block_pad_y: int = 0,
    font_family: str = "inherit",
    show_legend: bool = True,
    cmap_name: str = "tab10",
) -> str:
    doc = nlp_model(sentence)
    labels_in_order = []
    for ent in doc.ents:
        if ent.label_ not in labels_in_order:
            labels_in_order.append(ent.label_)
    n_types = max(1, len(labels_in_order))
    cmap = cm.get_cmap(cmap_name, n_types)
    ent2rgba = {}
    ent2hex = {}
    for i, ent in enumerate(labels_in_order):
        r, g, b, _ = cmap(i)
        ent2rgba[ent] = f"rgba({int(r*255)},{int(g*255)},{int(b*255)},{alpha})"
        ent2hex[ent] = mcolors.to_hex((r, g, b))
    container_style = (
        f"white-space: pre-wrap; display: inline-block;"
        f"padding:{block_pad_y}px {block_pad_x}px;"
        f"font-family:{font_family}; line-height:1.4;"
    )
    html_parts = [f'<div style="{container_style}">']
    for token in doc:
        bg = (
            ent2rgba.get(token.ent_type_, "transparent")
            if token.ent_type_
            else "transparent"
        )
        token_html = escape(token.text_with_ws).replace("\n", "<br>")
        span_style = (
            f"background-color:{bg};"
            f"padding:{pad_y}px {pad_x}px;"
            f"margin:{gap_y}px {gap_x}px;"
            f"border-radius:{radius}px;"
        )
        html_parts.append(f'<span style="{span_style}">{token_html}</span>')
    html_parts.append("</div>")
    if show_legend and labels_in_order:
        legend_items = []
        try:
            import spacy as _spacy

            explain = _spacy.explain
        except Exception:
            explain = lambda _: None
        for ent in labels_in_order:
            descr = explain(ent) or ""
            swatch = (
                f'<span style="display:inline-block; width:0.9em; height:0.9em; '
                f'background:{ent2hex[ent]}; border-radius:2px; margin-right:0.4em;"></span>'
            )
            label_txt = escape(ent + (f" — {descr}" if descr else ""))
            legend_items.append(
                f'<div style="margin-right:1em; margin-bottom:0.3em; display:flex; align-items:center;">{swatch}{label_txt}</div>'
            )
        legend_html = (
            '<div style="margin-top:0.5em; display:flex; flex-wrap:wrap; '
            'align-items:center; font-size:0.9em;">' + "".join(legend_items) + "</div>"
        )
        html_parts.append(legend_html)
    return "".join(html_parts)
