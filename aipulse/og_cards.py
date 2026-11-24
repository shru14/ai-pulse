"""Link-preview pictures for glossary words and topics (owner, 24 Nov 2026): the site picture's look (og-pulse.png: dark
grid, blue pulse line) with the page's own headline and line, so a shared link shows what the page answers. Drawn with
Pillow from the site's own fonts at build time; any other page keeps og-pulse.png.
"""
from __future__ import annotations

from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS = Path(__file__).resolve().parent.parent / "templates" / "fonts"
W, H, PAD = 1200, 630, 62
BG, GRID, TEXT, SOFT, MUTED = "#111318", "#20232b", "#FFFFFF", "#E9EBEF", "#C9CCD3"
LINE, DOT = "#2B9BE0", "#0072B2"
GLOSSARY, TOPIC = "#CC79A7", "#F0E442"  # the glossary's and the topics' section colours (Okabe-Ito)


@cache
def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for word in text.split():
        if lines and draw.textlength(f"{lines[-1]} {word}", font=font) <= width:
            lines[-1] += f" {word}"
        else:
            lines.append(word)
    return lines


def draw(path: Path, label: str, colour: str, headline: str, line: str, address: str) -> None:
    """One 1200x630 picture: "Pulse Central" and the section's pill, the headline (smaller, then two lines, when
    long), the page's line (at most 3 lines) and its address."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 40):
        d.line([(x, 0), (x, H)], fill=GRID)
    for y in range(0, H, 40):
        d.line([(0, y), (W, y)], fill=GRID)
    # the top row: the site's name, then the section in its colour
    name = _font("archivo-latin-600-normal.woff2", 26)
    d.text((PAD, 74), "Pulse Central", font=name, fill=TEXT, anchor="lm")
    pill = _font("archivo-latin-600-normal.woff2", 22)
    x0 = PAD + d.textlength("Pulse Central", font=name) + 16
    x1 = x0 + d.textlength(label, font=pill) + 36
    d.rounded_rectangle((x0, 56, x1, 92), radius=18, fill=colour)
    d.text(((x0 + x1) / 2, 74), label, font=pill, fill="#111111", anchor="mm")
    # the headline: one line beside the pulse line if it fits, else smaller and up to two lines across the picture
    size = 92
    big = _font("archivo-black-latin-400-normal.woff2", size)
    heads, room = [headline], d.textlength(headline, font=big) <= 690
    for size in () if room else (76, 64):
        big = _font("archivo-black-latin-400-normal.woff2", size)
        heads = _wrap(d, headline, big, W - 2 * PAD)
        if len(heads) <= 2:
            break
    heads = heads[:2]
    y = 138
    for h in heads:
        d.text((PAD, y), h, font=big, fill=TEXT)
        y += int(size * 1.08)
    # the pulse line: beside a short headline, along the bottom otherwise
    py = 183 if room else 545
    pts = [(780, py), (900, py), (940, py - 56), (980, py + 55), (1015, py - 26), (1040, py), (1160, py)]
    d.line(pts, fill=LINE, width=7, joint="curve")
    d.ellipse((1161, py - 14, 1189, py + 14), fill=DOT)
    # the page's line, at most 3 lines (cut with an ellipsis), then the address
    body = _font("archivo-latin-400-normal.woff2", 31)
    rows = _wrap(d, line, body, W - 2 * PAD - 60)
    if len(rows) > 3:
        rows = rows[:3]
        while d.textlength(rows[2] + "…", font=body) > W - 2 * PAD - 60:
            rows[2] = rows[2].rsplit(" ", 1)[0]
        rows[2] += "…"
    y += 22
    for r in rows:
        d.text((PAD, y), r, font=body, fill=SOFT)
        y += 44
    d.text((PAD, H - 58), address, font=_font("ibm-plex-mono-latin-400-normal.woff2", 22), fill=MUTED, anchor="ls")
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, optimize=True)
