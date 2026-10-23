"""Build the boot graphics from the source SVGs.

    python3 branding/make_assets.py <output-dir>

Creates:
    splash.svg                  boot menu background (640x480), logo and wordmark centered
    plymouth/medicus.plymouth   start-up animation theme
    plymouth/watermark.png      logo + wordmark shown while booting
    plymouth/throbber-NNNN.png  heartbeat (ECG) animation frames
    avatar.png                  default profile picture

Needs rsvg-convert (librsvg2-bin) and Pillow (python3-pil).
"""

import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
GREEN_LIGHT = (127, 224, 173)
FRAMES = 40


def inner(svg: str, prefix: str) -> str:
    """The contents of an SVG file, with ids renamed so several files can be combined."""
    body = svg.split(">", 1)[1].rsplit("</svg>", 1)[0]
    body = re.sub(r"<title>.*?</title>", "", body, flags=re.S)
    for name in set(re.findall(r'id="([^"]+)"', body)):
        body = body.replace(f'id="{name}"', f'id="{prefix}{name}"').replace(f"url(#{name})", f"url(#{prefix}{name})")
    return body.strip()


def logo_and_wordmark(logo_size: int, logo_y: float, wordmark_y: float, cx: float) -> str:
    logo = inner((HERE / "medicus-logo.svg").read_text(encoding="utf-8"), "logo-")
    wordmark = inner((HERE / "wordmark.svg").read_text(encoding="utf-8"), "wm-")
    scale = logo_size / 128
    return (f'<g transform="translate({cx - logo_size / 2} {logo_y}) scale({scale})">{logo}</g>'
            f'<g transform="translate({cx - 220} {wordmark_y})">{wordmark}</g>')


def splash_svg() -> str:
    # The boot menu is drawn below y≈330 (see build.sh), so the brand sits centered above it.
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 480" width="640" height="480">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0.6" y2="1">
      <stop offset="0" stop-color="#05231a"/><stop offset="1" stop-color="#11583a"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.36" r="0.45">
      <stop offset="0" stop-color="#4cc38a" stop-opacity="0.30"/><stop offset="1" stop-color="#4cc38a" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="640" height="480" fill="url(#bg)"/>
  <rect width="640" height="480" fill="url(#glow)"/>
  <g fill="none" stroke="#7fe0ad" stroke-opacity="0.07">
    <circle cx="320" cy="140" r="64"/><circle cx="320" cy="140" r="90"/><circle cx="320" cy="140" r="118"/>
  </g>
  {logo_and_wordmark(96, 92, 196, 320)}
</svg>"""


def watermark_svg() -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 440 260" width="440" height="260">
  {logo_and_wordmark(128, 0, 138, 220)}
</svg>"""


def ecg_y(x: float, width: float, base: float, amp: float) -> float:
    """One heartbeat across the strip: P wave, QRS spike, T wave."""
    t = x / width
    shape = [(0.00, 0), (0.30, 0), (0.33, -0.10), (0.36, 0), (0.42, 0), (0.44, 0.12), (0.47, -1.0),
             (0.50, 0.35), (0.53, 0), (0.60, 0), (0.66, -0.22), (0.72, 0), (1.00, 0)]
    for (x0, y0), (x1, y1) in zip(shape, shape[1:]):
        if x0 <= t <= x1:
            return base + amp * (y0 + (y1 - y0) * (t - x0) / (x1 - x0))
    return base


def heartbeat_frames(out: Path, width=320, height=90, scale=3):
    w, h = width * scale, height * scale
    points = [(x, ecg_y(x, w, h * 0.62, h * 0.5)) for x in range(0, w + 1, 2)]
    for frame in range(FRAMES):
        head = int(len(points) * (frame + 1) / FRAMES)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.line(points, fill=GREEN_LIGHT + (28,), width=2 * scale)          # faint full trace
        tail = int(len(points) * 0.55)
        for i in range(max(1, head - tail), head):
            alpha = int(255 * (1 - (head - i) / tail))
            draw.line([points[i - 1], points[i]], fill=GREEN_LIGHT + (alpha,), width=3 * scale)
        hx, hy = points[head - 1]
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([hx - 9 * scale, hy - 9 * scale, hx + 9 * scale, hy + 9 * scale], fill=GREEN_LIGHT + (150,))
        img = Image.alpha_composite(glow.filter(ImageFilter.GaussianBlur(5 * scale)), img)
        ImageDraw.Draw(img).ellipse([hx - 3 * scale, hy - 3 * scale, hx + 3 * scale, hy + 3 * scale], fill=(255, 255, 255, 255))
        img.resize((width, height), Image.LANCZOS).save(out / f"throbber-{frame + 1:04d}.png")


PLYMOUTH_THEME = """[Plymouth Theme]
Name=Medicus
Description=Medicus OS – hjerteslag mens maskinen starter
ModuleName=two-step

[two-step]
Font=Noto Sans 12
TitleFont=Noto Sans Light 24
ImageDir=/usr/share/plymouth/themes/medicus
WatermarkHorizontalAlignment=.5
WatermarkVerticalAlignment=.42
HorizontalAlignment=.5
VerticalAlignment=.70
DialogHorizontalAlignment=.5
DialogVerticalAlignment=.70
TitleHorizontalAlignment=.5
TitleVerticalAlignment=.62
Transition=none
TransitionDuration=0.0
BackgroundStartColor=0x05231a
BackgroundEndColor=0x11583a
"""


def main(out_dir: str):
    out = Path(out_dir)
    plymouth = out / "plymouth"
    plymouth.mkdir(parents=True, exist_ok=True)
    (out / "splash.svg").write_text(splash_svg(), encoding="utf-8")
    watermark = out / "watermark.svg"
    watermark.write_text(watermark_svg(), encoding="utf-8")
    subprocess.run(["rsvg-convert", str(watermark), "-o", str(plymouth / "watermark.png")], check=True)
    heartbeat_frames(plymouth)
    (plymouth / "medicus.plymouth").write_text(PLYMOUTH_THEME, encoding="utf-8")
    # Profile picture for every user (~/.face), shown in the Start menu.
    subprocess.run(["rsvg-convert", "-w", "256", str(HERE / "avatar.svg"), "-o", str(out / "avatar.png")], check=True)


if __name__ == "__main__":
    main(sys.argv[1])
