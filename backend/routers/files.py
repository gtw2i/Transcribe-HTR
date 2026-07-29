"""File listing and image retrieval."""

import base64
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.file_manager import get_root_status_tag, get_sorted_roots
from core.json_manager import get_json_summary, load_v2_json
from dependencies import get_file_index, get_workspace

router = APIRouter(tags=["files"])


@router.get("/files/roots")
def list_roots(file_index=Depends(get_file_index)):
    """Return all roots and their status tags."""
    roots = get_sorted_roots(file_index)
    return [
        {
            "root": r,
            "status": get_root_status_tag(r, file_index),
            "run_count": file_index.records[r].run_count if r in file_index.records else 0,
        }
        for r in roots
    ]


@router.get("/files/{root}/image")
def get_image(root: str, file_index=Depends(get_file_index)):
    """Return the image for a root as base64-encoded PNG."""
    if root not in file_index.records:
        raise HTTPException(status_code=404, detail=f"Root '{root}' not found.")
    record = file_index.records[root]
    if not record.has_image():
        raise HTTPException(status_code=404, detail=f"No image for root '{root}'.")
    path = Path(record.image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Image file missing for root '{root}'.")
    data = path.read_bytes()
    return {"root": root, "image_b64": base64.b64encode(data).decode(), "mime": "image/png"}


@router.get("/files/{root}/json")
def get_json(root: str, file_index=Depends(get_file_index)):
    """Return the full V2 JSON transcription data for a root."""
    if root not in file_index.records:
        raise HTTPException(status_code=404, detail=f"Root '{root}' not found.")
    record = file_index.records[root]
    if not record.has_json():
        raise HTTPException(status_code=404, detail=f"No JSON for root '{root}'.")
    path = Path(record.json_path)
    data = load_v2_json(path)
    if data is None:
        raise HTTPException(status_code=500, detail="Failed to load JSON file.")
    return data


@router.get("/files/{root}/summary")
def get_summary(root: str, file_index=Depends(get_file_index)):
    """Return a brief summary (run count, format) for a root's JSON file."""
    if root not in file_index.records:
        raise HTTPException(status_code=404, detail=f"Root '{root}' not found.")
    record = file_index.records[root]
    if not record.has_json():
        return {"root": root, "format": "None", "runs": 0, "total_outputs": 0}
    path = Path(record.json_path)
    return get_json_summary(path)
