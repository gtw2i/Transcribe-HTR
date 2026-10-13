"""Tests for POST /api/upload image handling.

The UI accepts TIFF (the usual archival master format) but the upload route
only converted jpg/png/gif/webp/bmp, so TIFFs fell through to the workspace,
which stores only .png/.jpg/.jpeg, and were rejected with "Failed to save".
"""

import io

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

import dependencies
from core.image_utils import resize_image_for_api
from core.session_workspace import FileIndex, SessionWorkspace
from routers import session as session_router


def _image_bytes(fmt: str, img: Image.Image, **save_kwargs) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format=fmt, **save_kwargs)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TRANSCRIBE_SESSION_ROOT", str(tmp_path))
    ws = SessionWorkspace(session_id="test")
    assert ws.ensure_workspace()
    index = FileIndex(ws)

    app = FastAPI()
    app.include_router(session_router.router, prefix="/api")
    app.dependency_overrides[dependencies.get_workspace] = lambda: ws
    app.dependency_overrides[dependencies.get_file_index] = lambda: index
    with TestClient(app) as c:
        c.ws = ws
        yield c


@pytest.mark.parametrize("name", ["scan.tif", "scan.TIFF", "page.jpg", "page.webp", "page.bmp"])
def test_every_accepted_image_type_is_stored_as_png(client, name):
    fmt = {"tif": "TIFF", "tiff": "TIFF", "jpg": "JPEG", "webp": "WEBP", "bmp": "BMP"}[name.rsplit(".", 1)[1].lower()]
    data = _image_bytes(fmt, Image.new("RGB", (40, 30), "white"))

    body = client.post("/api/upload", files=[("files", (name, data))]).json()

    assert body["errors"] == []
    stem = name.rsplit(".", 1)[0]
    assert body["roots"] == [stem]
    assert (client.ws.workspace_path / f"{stem}.png").exists()


class TestImageNormalization:
    def test_sixteen_bit_greyscale_keeps_its_contrast(self):
        # A dark page with mid-grey text, 16-bit, as produced by archival scanners.
        arr = np.full((20, 20), 4000, dtype=np.uint16)
        arr[5:15, 5:15] = 30000
        src = Image.fromarray(arr, mode="I;16")
        png = Image.open(io.BytesIO(resize_image_for_api(_image_bytes("TIFF", src)))).convert("L")
        lo, hi = png.getextrema()
        assert hi - lo > 150, "16-bit image was clipped instead of rescaled"

    def test_exif_rotation_is_applied(self):
        img = Image.new("RGB", (60, 20), "white")  # landscape pixels
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation: rotate 90 CW to display (portrait)
        data = _image_bytes("JPEG", img, exif=exif.tobytes())
        out = Image.open(io.BytesIO(resize_image_for_api(data)))
        assert out.size == (20, 60)

    def test_large_images_are_bounded(self):
        data = _image_bytes("PNG", Image.new("RGB", (4000, 1000), "white"))
        out = Image.open(io.BytesIO(resize_image_for_api(data, max_size=2048)))
        assert max(out.size) == 2048
