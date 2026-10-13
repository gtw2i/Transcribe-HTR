"""Session management — init and file upload."""

import base64
from typing import List

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse

from core.image_utils import resize_image_for_api
from dependencies import (
    create_session,
    get_file_index,
    get_session,
    get_workspace,
    persistent_workspace_enabled,
)
from schemas.common import SessionInfo

router = APIRouter(tags=["session"])

# Image types that are resized and normalized to PNG on upload. The workspace
# itself only stores .png/.jpg/.jpeg, so any image type the UI accepts must be
# listed here or the upload is rejected.
CONVERTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff")


@router.post("/session/init", response_model=SessionInfo)
def init_session(request: Request):
    """Create a new session and set the session cookie."""
    sid = create_session()
    request.session["session_id"] = sid
    return {"session_id": sid}


@router.post("/upload")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    workspace=Depends(get_workspace),
    file_index=Depends(get_file_index),
):
    """Upload image (and optionally audio) files to the session workspace."""
    roots = []
    errors = []
    # A persistent workspace keeps months of work: re-uploading "page1.jpg"
    # must create page1-1 rather than replace the image under page1's
    # existing transcriptions. Ephemeral web sessions keep overwrite semantics.
    allow_overwrite = not persistent_workspace_enabled()

    for upload in files:
        try:
            data = await upload.read()
            filename = upload.filename or "unknown"

            # Resize images before saving to save disk space
            if filename.lower().endswith(CONVERTED_IMAGE_EXTENSIONS):
                try:
                    data = resize_image_for_api(data, max_size=2048)
                    # Normalize to .png after resize
                    stem = filename.rsplit(".", 1)[0]
                    filename = stem + ".png"
                except Exception:
                    pass  # keep original bytes if resize fails

            path = workspace.persist_uploaded_file(
                filename, data, file_index=file_index, allow_overwrite=allow_overwrite
            )
            if path:
                root = path.stem
                if root not in roots:
                    roots.append(root)
            else:
                errors.append(f"Failed to save {filename}")
        except Exception as e:
            errors.append(f"{upload.filename}: {str(e)}")

    return {"roots": roots, "errors": errors}
