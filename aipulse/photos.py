"""The stories' photos: openly licensed pictures from Wikimedia Commons, chosen by hand, kept in templates/photos/.

A story shows one by its topic (chips, data centres, robots, courts...) or else its stream; the page picks it (index.html,
storyPhoto). Each photo's author, licence and Commons page are in templates/photos/credits.json; the site lists them on
photos/credits.html, linked from every page's footer, and each picture carries its credit as a tooltip. Only public
domain, CC0, CC BY and CC BY-SA photos are used. No news photo is copied from a publisher.
"""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "templates" / "photos"


def credits() -> list[dict]:
    return json.loads((DIR / "credits.json").read_text(encoding="utf-8"))


def fill(page: str) -> str:
    """Put the photo list into the page: {topic: [[file, credit], ...]}."""
    by: dict[str, list] = {}
    for c in credits():
        by.setdefault(c["topic"], []).append([c["photo"], f"Photo: {c['author'] or 'Wikimedia Commons'}, {c['licence']}"])
    return page.replace("const PHOTOS = {};", "const PHOTOS = " + json.dumps(by, ensure_ascii=False, separators=(",", ":")) + ";", 1)


def _who(c) -> str:
    """The author's name alone: no web addresses, licence text or a name said twice (as Commons sometimes has it)."""
    t = re.sub(r"\(?(?:https?://|www\.)\S+\)?", "", c["author"] or c["attribution"] or "")
    t = re.split(r"\s(?:You are free|Under the following|Licensed under)", t)[0]
    t = re.sub(r"\(aka [^)]*\)", "", t)
    t = " ".join(t.split()).strip(" ,;:-–")
    half = t[:len(t) // 2].strip()
    if t and t == f"{half} {half}":
        t = half
    return t or "Unknown author"


def credits_page() -> str:
    """One line per photo: its title (linked to Commons), who made it, the licence."""
    def lic(c):
        return f'<a href="{escape(c["licence_url"])}">{escape(c["licence"])}</a>' if c["licence_url"] else escape(c["licence"])
    rows = "".join(
        f'<li><a href="{escape(c["source"])}">{escape(c["title"].replace("_", " ").rsplit(".", 1)[0])}</a>'
        f' · {escape(_who(c))} · {lic(c)}</li>' for c in credits())
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Photo credits · AI Pulse</title><style>body{font:14px/1.5 Arial,Helvetica,sans-serif;margin:0 auto;max-width:960px;'
            'padding:24px 16px;color:#222;background:#fff}h1{font-size:20px;font-weight:600;margin:0 0 6px}p{margin:0 0 14px;color:#555}'
            'ul{list-style:none;margin:0;padding:0}li{padding:5px 0;border-top:1px solid #ddd;overflow-wrap:anywhere}'
            'a{color:#0072B2}</style></head><body><h1>Photo credits</h1><p>Openly licensed photos from Wikimedia Commons, '
            'shown in each stream’s colour. They illustrate a topic, not the story itself. <a href="../">Back to AI Pulse</a></p>'
            f'<ul>{rows}</ul></body></html>')
