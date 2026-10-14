"""Generate the app icons: icon.png (1024 px), app.ico (Windows), app.icns (macOS).

PLACEHOLDER artwork: a rounded square in the app's primary colour with a
serif "T" and a pen stroke. Replace icon.png with designed artwork and
re-run with --from-png to regenerate the platform formats from it.

    python packaging/icons/make_icons.py               # draw placeholder + convert
    python packaging/icons/make_icons.py --from-png    # convert existing icon.png
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SIZE = 1024
PRIMARY = (255, 75, 75, 255)  # --color-primary in frontend/src/styles/variables.css
WHITE = (255, 255, 255, 255)


def _font(size: int):
    for name in ("georgiab.ttf", "Georgia Bold.ttf", "DejaVuSerif-Bold.ttf", "timesbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def draw_placeholder() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    margin = 64  # macOS icons sit inside a margin on a transparent canvas
    d.rounded_rectangle((margin, margin, SIZE - margin, SIZE - margin), radius=200, fill=PRIMARY)
    font = _font(620)
    box = d.textbbox((0, 0), "T", font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    d.text(((SIZE - w) / 2 - box[0], (SIZE - h) / 2 - box[1] - 90), "T", font=font, fill=WHITE)
    # A handwritten squiggle under the letter.
    # Drawn as overlapping dots: a polyline of short segments leaves seams.
    for x in range(270, 741):
        y = 805 - 22 * math.sin((x - 270) / 470 * 3 * math.pi)
        d.ellipse((x - 15, y - 15, x + 15, y + 15), fill=WHITE)
    return img


def convert(png: Image.Image) -> None:
    png = png.convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
    png.save(HERE / "app.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    png.save(HERE / "app.icns")


def main() -> None:
    if "--from-png" in sys.argv:
        img = Image.open(HERE / "icon.png")
    else:
        img = draw_placeholder()
        img.save(HERE / "icon.png")
    convert(img)
    for name in ("icon.png", "app.ico", "app.icns"):
        print(name, (HERE / name).stat().st_size, "bytes")


if __name__ == "__main__":
    main()
