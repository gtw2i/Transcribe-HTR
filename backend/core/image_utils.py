"""Image utilities — resize/process images before API calls."""

import io

import numpy as np
from PIL import Image, ImageOps

# Pillow modes for 16/32-bit greyscale, common in archival TIFF scans.
# convert("RGB") clips these instead of scaling, washing the page out to white.
_HIGH_BIT_DEPTH_MODES = ("I;16", "I;16B", "I;16L", "I;16N", "I", "F")


def _to_rgb(img: Image.Image) -> Image.Image:
    """Upright, 8-bit RGB version of an image (first frame of multi-page files)."""
    img = ImageOps.exif_transpose(img)  # phone photos store rotation in EXIF
    if img.mode in _HIGH_BIT_DEPTH_MODES:
        arr = np.asarray(img, dtype=np.float64)
        peak = arr.max() or 1.0
        img = Image.fromarray((arr * (255.0 / peak)).clip(0, 255).astype(np.uint8), mode="L")
    return img.convert("RGB")


def resize_image_for_api(img_bytes: bytes, max_size: int = 2048) -> bytes:
    """Resize image to fit within max_size x max_size while preserving aspect ratio."""
    img = _to_rgb(Image.open(io.BytesIO(img_bytes)))
    w, h = img.size
    if w > max_size or h > max_size:
        scale = max_size / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def load_image_bytes(path: str) -> bytes:
    """Load image from disk and return as PNG bytes."""
    with open(path, "rb") as f:
        raw = f.read()
    img = _to_rgb(Image.open(io.BytesIO(raw)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
