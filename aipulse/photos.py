"""The stories' photos: openly licensed pictures from Wikimedia Commons, chosen by hand, kept in templates/photos/.

A story shows one by its topic (chips, data centres, robots, courts...) or else its stream; the page picks it (index.html,
storyPhoto). Each photo's author, licence and Commons page are in templates/photos/credits.json; the site lists them on
photos/credits.html, linked from every page's footer, and each picture carries its credit as a tooltip. Only public
domain, CC0, CC BY and CC BY-SA photos are used. No news photo is copied from a publisher.
"""

from __future__ import annotations

import json
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


def credits_page() -> str:
    rows = "".join(
        f'<tr><td><img src="{escape(c["photo"])}" alt="" width="120" height="90" loading="lazy"></td>'
        f'<td><a href="{escape(c["source"])}">{escape(c["title"].replace("_", " "))}</a><br>{escape(c["author"] or "Unknown author")}'
        + (f'<br><small>{escape(c["attribution"])}</small>' if c["attribution"] and c["attribution"] != c["author"] else "")
        + f'</td><td>' + (f'<a href="{escape(c["licence_url"])}">{escape(c["licence"])}</a>' if c["licence_url"] else escape(c["licence"]))
        + '</td></tr>' for c in credits())
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Photo credits · AI Pulse</title><style>body{font:15px/1.5 Arial,Helvetica,sans-serif;margin:0 auto;max-width:960px;padding:24px 16px;'
            'color:#000;background:#fff}h1{font:900 30px Arial Black,Arial,sans-serif;text-transform:uppercase;border-bottom:4px solid #000;padding-bottom:8px}'
            'table{border-collapse:collapse;width:100%;table-layout:fixed}td{border-top:2px solid #000;padding:8px;vertical-align:top;overflow-wrap:anywhere}'
            'td:first-child{width:136px}td:last-child{width:130px}img{display:block;object-fit:cover}'
            'a{color:#0072B2}@media (prefers-color-scheme:dark){body{background:#0A0A0A;color:#fff}td{border-color:#fff}h1{border-color:#fff}a{color:#56B4E9}}</style></head><body>'
            '<h1>Photo credits</h1><p>The photos on AI Pulse are openly licensed pictures from Wikimedia Commons, shown in the colour of '
            'each stream. They illustrate a story\'s topic; they are not photos of the story itself. <a href="../">Back to AI Pulse</a></p>'
            f'<table>{rows}</table></body></html>')
