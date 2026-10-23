"""Make the Medicus logo files from the icon image.

    python3 branding/make_logo.py

Source: branding/medicus-icon-source.png (the green rounded square with the Rod of Asclepius).
Writes:
    medicus-logo.png    the icon, 512x512, transparent outside the rounded corners
    medicus-logo.svg    the same image inside an SVG, which is what the system uses everywhere
    wallpaper.svg       its faint rod-and-snake mark is replaced with the white parts of the icon

To change the logo: replace medicus-icon-source.png, check BOX below, and run this again.
"""
import base64
import io
import re
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
BOX = (271, 45, 753, 527)  # the rounded square (with its white border) in the source image
RADIUS = 101               # its corner radius, in source pixels
BORDER = 14                # the white border; left out of the wallpaper mark
SIZE = 512


def rounded_icon(src: Image.Image) -> Image.Image:
    icon = src.crop(BOX).convert("RGBA")
    # Draw the corner mask four times larger and shrink it, for smooth edges.
    big = Image.new("L", (icon.width * 4, icon.height * 4), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1), RADIUS * 4, fill=255)
    icon.putalpha(big.resize(icon.size, Image.LANCZOS))
    return icon.resize((SIZE, SIZE), Image.LANCZOS)


def white_mark(src: Image.Image) -> Image.Image:
    """Only the light parts (rod and snake), as white with transparency, for the wallpaper."""
    x0, y0, x1, y1 = BOX
    inside = src.crop((x0 + BORDER, y0 + BORDER, x1 - BORDER, y1 - BORDER)).convert("RGB")
    alpha = Image.new("L", inside.size)
    alpha.putdata([max(0, min(255, (min(p) - 110) * 2)) for p in inside.getdata()])
    # Keep only what is well inside the rounded border, so no bit of the white corners shows.
    keep = Image.new("L", inside.size, 0)
    ImageDraw.Draw(keep).rounded_rectangle((12, 12, inside.width - 12, inside.height - 12), RADIUS - BORDER, fill=255)
    alpha = Image.composite(alpha, keep, keep)
    mark = Image.new("RGBA", inside.size, (255, 255, 255, 0))
    mark.putalpha(alpha)
    return mark


def data_uri(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


if __name__ == "__main__":
    source = Image.open(HERE / "medicus-icon-source.png")
    icon = rounded_icon(source)
    icon.save(HERE / "medicus-logo.png", optimize=True)
    (HERE / "medicus-logo.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">\n'
        "  <title>Medicus – Asklepiosstaven</title>\n"
        "  <!-- Made by branding/make_logo.py from medicus-icon-source.png: change it there, not here. -->\n"
        f'  <image width="128" height="128" href="{data_uri(icon)}"/>\n'
        "</svg>\n", encoding="utf-8")

    mark = white_mark(source)
    wallpaper = HERE / "wallpaper.svg"
    text = wallpaper.read_text(encoding="utf-8")
    group = (f'<g transform="translate(1180 120) scale(6.6)" opacity="0.13">\n'
             f'    <image x="6" y="6" width="116" height="116" href="{data_uri(mark.resize((464, 464), Image.LANCZOS))}"/>\n'
             f'  </g>')
    text = re.sub(r'<g transform="translate\(1180 120\) scale\(6\.6\)".*?\n  </g>', lambda _m: group, text, count=1, flags=re.S)
    wallpaper.write_text(text, encoding="utf-8")
