"""File listing and image retrieval."""

import base64
import io
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from atomic_io import atomic_write_bytes
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


def _root_of(filename: str) -> str:
    """Document root for a workspace filename (mirrors FileIndex.register_file)."""
    if filename.endswith(".transcription.json"):
        return filename[: -len(".transcription.json")]
    return Path(filename).stem


@router.delete("/files/{root}")
def remove_document(root: str, workspace=Depends(get_workspace), file_index=Depends(get_file_index)):
    """Move every file of a document into <workspace>/trash/<timestamp>/.

    Nothing is deleted outright: the trash folder is the undo. All files whose
    root matches are moved (image, canonical and legacy JSON, audio), so a
    later rescan of the workspace cannot bring the document back.
    """
    if root not in file_index.records:
        raise HTTPException(status_code=404, detail=f"Root '{root}' not found.")
    ws_path = Path(workspace.workspace_path)
    trash = ws_path / "trash" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    moved = []
    for path in ws_path.iterdir():
        if path.is_file() and not path.name.startswith(".") and _root_of(path.name) == root:
            trash.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(trash / path.name))
            moved.append(path.name)
    del file_index.records[root]
    return {"root": root, "moved": sorted(moved), "trash": str(trash) if moved else None}


class RotateRequest(BaseModel):
    degrees: int  # clockwise; a multiple of 90


@router.post("/files/{root}/rotate")
def rotate_image(root: str, req: RotateRequest, file_index=Depends(get_file_index)):
    """Permanently rotate a document's stored page image (clockwise).

    For pages that were scanned or photographed sideways: the stored copy is
    what thumbnails show and what future transcriptions send to the AI. Only
    the workspace copy changes, never the user's original file, and existing
    transcriptions are left as they are. Quarter turns are exact pixel
    transposes, so no quality is lost.
    """
    from PIL import Image

    turns = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180, 270: Image.Transpose.ROTATE_90}
    degrees = req.degrees % 360
    if req.degrees % 90 != 0 or degrees == 0:
        raise HTTPException(status_code=400, detail="Rotation must be 90, 180 or 270 degrees.")
    if root not in file_index.records or not file_index.records[root].has_image():
        raise HTTPException(status_code=404, detail=f"No image for root '{root}'.")

    path = Path(file_index.records[root].image_path)
    with Image.open(path) as im:
        im.load()
        fmt = im.format or "PNG"
        rotated = im.transpose(turns[degrees])
    buf = io.BytesIO()
    if fmt == "JPEG":
        rotated.save(buf, format="JPEG", quality=95)
    else:
        rotated.save(buf, format=fmt)
    atomic_write_bytes(path, buf.getvalue())
    return {"root": root, "degrees": degrees, "width": rotated.width, "height": rotated.height}


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
