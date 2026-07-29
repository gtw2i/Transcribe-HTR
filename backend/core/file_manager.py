"""File management utilities — pure functions, no Streamlit."""

import re
from pathlib import Path
from typing import List, Optional


def natural_sort_key(text: str) -> List:
    """Convert a string into a list of mixed strings and integers for natural sorting."""
    def tryint(s):
        try:
            return int(s)
        except ValueError:
            return s
    return [tryint(c) for c in re.split(r"(\d+)", text)]


def get_sorted_roots(file_index) -> List[str]:
    """Get all roots from FileIndex sorted in natural alphanumeric order."""
    if not file_index or not file_index.records:
        return []
    return sorted(file_index.records.keys(), key=natural_sort_key)


def get_root_status_tag(root: str, file_index) -> str:
    """Get status tag for a root: paired, image-only, json-only, or empty."""
    if not file_index or not file_index.records or root not in file_index.records:
        return "unknown"
    record = file_index.records[root]
    has_image = record.has_image()
    has_json = record.has_json()
    if has_image and has_json:
        return "paired"
    elif has_image:
        return "image-only"
    elif has_json:
        return "json-only"
    else:
        return "empty"


def format_dropdown_option(root: str, status: str) -> str:
    return f"{root} [{status}]"


def get_file_type_indicator(root: str, file_index) -> str:
    """Return a short indicator string showing which file types exist for a root."""
    if not file_index or root not in file_index.records:
        return ""
    record = file_index.records[root]
    if record.has_image() and record.has_json() and record.has_audio():
        return "image+json+audio"
    elif record.has_image() and record.has_json():
        return "image+json"
    elif record.has_image():
        return "image-only"
    elif record.has_json():
        return "json-only"
    elif record.has_audio():
        return "audio-only"
    return "empty"
