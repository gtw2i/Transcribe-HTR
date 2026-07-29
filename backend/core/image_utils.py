"""Image utilities — resize/process images before API calls."""

import io

from PIL import Image


def resize_image_for_api(img_bytes: bytes, max_size: int = 2048) -> bytes:
    """Resize image to fit within max_size x max_size while preserving aspect ratio."""
    img = Image.open(io.BytesIO(img_bytes))
    img = img.convert("RGB")
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
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
