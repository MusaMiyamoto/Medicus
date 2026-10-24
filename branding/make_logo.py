"""Make the Medicus logo files from the icon image.

    python3 branding/make_logo.py

Source: branding/medicus-icon-source.png (the green round badge with the Rod of Asclepius, on a dark
background). The badge is found in the image by its white ring, so a new source image just works.
Writes:
    medicus-logo.png    the badge, 512x512, transparent outside the circle
    medicus-logo.svg    the same image inside an SVG, which is what the system uses everywhere
    wallpaper.svg       its faint rod-and-snake mark is replaced with the white parts of the badge

To change the logo: replace medicus-icon-source.png and run this again.
"""
import base64
import io
import re
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
SIZE = 512
RING = 0.13  # the white ring and the light inner rim, as a share of the size; left out of the wallpaper mark
EDGE = 0.006  # trimmed off the outside, so no background pixel shows along the edge
WALLPAPER_MARK = re.compile(r'<g transform="translate\(1180 120\) scale\(6\.6\)".*?\n  </g>', re.S)


def badge_box(src: Image.Image) -> tuple[int, int, int, int]:
    """The square around the white ring: the bright pixels' bounding box."""
    bright = src.convert("L").point(lambda v: 255 if v > 200 else 0)
    x0, y0, x1, y1 = bright.getbbox()
    side = max(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    return cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2


def circle_mask(size: int, inset: float = 0) -> Image.Image:
    # Drawn four times larger and shrunk, for a smooth edge.
    big = Image.new("L", (size * 4, size * 4), 0)
    pad = inset * size * 4
    ImageDraw.Draw(big).ellipse((pad, pad, size * 4 - 1 - pad, size * 4 - 1 - pad), fill=255)
    return big.resize((size, size), Image.LANCZOS)


def round_icon(src: Image.Image) -> Image.Image:
    icon = src.crop(badge_box(src)).convert("RGBA").resize((SIZE, SIZE), Image.LANCZOS)
    icon.putalpha(circle_mask(SIZE, EDGE))
    return icon


def white_mark(icon: Image.Image) -> Image.Image:
    """Only the light parts (rod and snake), as white with transparency, for the wallpaper."""
    rgb = icon.convert("RGB")
    alpha = Image.new("L", rgb.size)
    alpha.putdata([max(0, min(255, (min(p) - 110) * 2)) for p in rgb.getdata()])
    # Keep only what is well inside the white ring.
    alpha = Image.composite(alpha, Image.new("L", rgb.size, 0), circle_mask(SIZE, RING))
    mark = Image.new("RGBA", rgb.size, (255, 255, 255, 0))
    mark.putalpha(alpha)
    return mark


def data_uri(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


if __name__ == "__main__":
    icon = round_icon(Image.open(HERE / "medicus-icon-source.png"))
    icon.save(HERE / "medicus-logo.png", optimize=True)
    (HERE / "medicus-logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">\n'
        "  <title>Medicus – Asklepiosstaven</title>\n"
        "  <!-- Made by branding/make_logo.py from medicus-icon-source.png: change it there, not here. -->\n"
        f'  <image width="128" height="128" href="{data_uri(icon)}"/>\n'
        "</svg>\n", encoding="utf-8")

    mark = white_mark(icon)
    wallpaper = HERE / "wallpaper.svg"
    text = wallpaper.read_text(encoding="utf-8")
    group = (f'<g transform="translate(1180 120) scale(6.6)" opacity="0.13">\n'
             f'    <image x="0" y="0" width="128" height="128" href="{data_uri(mark.resize((464, 464), Image.LANCZOS))}"/>\n'
             f'  </g>')
    text, count = WALLPAPER_MARK.subn(lambda _m: group, text, count=1)
    if count != 1:
        raise SystemExit("Fant ikke merket i wallpaper.svg")
    wallpaper.write_text(text, encoding="utf-8")
