"""Export endpoint — download transcription bundle(s)."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from core.export_utils import build_single_format_export, build_zip_export
from core.file_manager import get_sorted_roots
from core.json_manager import load_v2_json
from logging_config import log_warning
from dependencies import get_file_index

router = APIRouter(tags=["export"])

VALID_FORMATS = {"json", "txt", "docx"}


@router.get("/export")
def export_all(format: str = "json", file_index=Depends(get_file_index)):
    """
    Download transcription data for every processed document in the session.
    format: 'json' (default), 'txt', or 'docx'.
    Returns a single file if exactly one document has been processed,
    otherwise a ZIP with one file per document.
    """
    if format not in VALID_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported format '{format}'.")

    roots = [r for r in get_sorted_roots(file_index) if file_index.records[r].has_json()]
    if not roots:
        raise HTTPException(status_code=400, detail="No transcription data available.")

    built = []  # list of (data, filename, mime)
    for root in roots:
        record = file_index.records[root]
        json_data = load_v2_json(Path(record.json_path))
        if json_data is None:
            log_warning(f"Skipping '{root}' in bulk export — failed to load JSON.")
            continue
        built.append(build_single_format_export(json_data, root, format, image_path=record.image_path))

    if not built:
        raise HTTPException(status_code=500, detail="Failed to load transcription data.")

    if len(built) == 1:
        data, filename, mime = built[0]
    else:
        data, filename, mime = build_zip_export([(d, f) for d, f, _ in built], format)

    return Response(
        content=data,
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
