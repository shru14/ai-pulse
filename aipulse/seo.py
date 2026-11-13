"""Headlines written into the pages' HTML, so search engines see the stories without running the page's script.

The pages draw their stories in the reader's browser from data.json (several MB) or a page's own JSON. Until that
arrives, a page held only "Loading…", and that is what Google read (6 Nov 2026: no page of the site indexed). Now
each page ships its newest headlines as plain links (title, outlet, date; no summaries: owner, 6 Nov 2026), and
the script replaces them with its full view once its data has loaded. If the data never loads, they stay.
"""
from __future__ import annotations

import json
from datetime import date
from html import escape


def day(d: str) -> str:
    """'2026-11-06' -> 'Fri, 6 Nov 2026', as the page's own dates read."""
    return f"{date.fromisoformat(d[:10]):%a}, {int(d[8:10])} {date.fromisoformat(d[:10]):%b %Y}"


def newest(cards: list[dict], n: int) -> list[dict]:
    return sorted(cards, key=lambda c: c["date"], reverse=True)[:n]


def link(c: dict) -> str:
    return f'<a href="{escape(c["url"])}" rel="noopener">{escape(c["title"].strip())}</a>'


def items(cards: list[dict]) -> str:
    """<li>s as the sub-pages' own list draws them: the headline, then its date and outlet."""
    return "".join(f'<li>{link(c)}<div class="meta">{escape(" · ".join(filter(None, (day(c["date"]), c.get("source")))))}'
                   '</div></li>' for c in cards)


def feed(cards: list[dict]) -> str:
    """A stream page's stories by day, in the markup its script draws (section.day > h2 + article.item h3)."""
    out: list[str] = []
    by: dict[str, list[dict]] = {}
    for c in cards:
        by.setdefault(c["date"][:10], []).append(c)
    for d, cs in by.items():
        arts = "".join(f'<article class="item {escape(c["category"])}"><div class="body"><h3>{link(c)}</h3>'
                       f'<p class="authors">{escape(c.get("source") or "")}</p></div></article>' for c in cs)
        out.append(f'<section class="day"><h2>{day(d)}</h2><div class="items">{arts}</div></section>')
    return "".join(out)


def data(id_: str, cards: list[dict], keys: tuple[str, ...]) -> str:
    """A page's own stories in its HTML, as JSON its script reads at once: only `keys` of each card, so a sub-page
    or word page needs no download of data.json (6.7 MB) to list its stories (owner, 12 Nov 2026)."""
    rows = [{k: c[k] for k in keys if c.get(k) not in (None, "", [])} for c in cards]
    text = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="{id_}">{text}</script>\n'
