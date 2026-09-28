"""RSS feeds, one per stream: feeds/releases.xml, feeds/news.xml, feeds/policy.xml, feeds/research.xml and
feeds/regulation.xml. Each holds the stream's newest cards (one per event, like the page) with the headline,
the one-line summary, the source and a link to the original story.

The static build writes them next to data.json; the local server answers /feeds/<name>.xml the same way.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

SITE = "https://shru14.github.io/ai-pulse/"
PER_FEED = 50
# File name -> (category, stream name, what it carries); the names match the page's streams.
FEEDS = {
    "releases": ("tool", "Releases", "New models, products and open-source launches from AI labs and companies."),
    "news": ("news", "Industry news", "Funding, deals, partnerships and company moves in AI."),
    "policy": ("policy", "Policy", "What governments, courts and politicians are doing about AI."),
    "research": ("research", "Research", "New AI papers from arXiv, top labs and leading scholars."),
    "regulation": ("regulation", "Regulation tracker", "AI bills and laws followed from proposal to force, by country."),
}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")  # not allowed in XML


def _text(value: str) -> str:
    return escape(_CONTROL.sub("", value or ""))


def _when(card: dict) -> str:
    """The card's time: when it was collected if that was on its date, else the start of its date (UTC)."""
    added = card.get("added_at") or ""
    if added[:10] == card["date"]:
        try:
            return format_datetime(datetime.fromisoformat(added).astimezone(timezone.utc))
        except ValueError:
            pass
    return format_datetime(datetime.fromisoformat(card["date"]).replace(tzinfo=timezone.utc))


def feed_xml(name: str, cards: list[dict], site: str = SITE) -> bytes:
    """An RSS 2.0 feed for one stream from its cards (newest first)."""
    category, stream, about = FEEDS[name]
    items = []
    for c in cards[:PER_FEED]:
        summary = c.get("summary") or ""
        about_item = f"{summary} ({c['source']})" if summary else c["source"]
        tags = "".join(f"<category>{_text(t)}</category>" for t in c.get("tags") or [])
        items.append(f"<item><title>{_text(c['title'])}</title><link>{_text(c['url'])}</link>"
                     f"<description>{_text(about_item)}</description><pubDate>{_when(c)}</pubDate>"
                     f"<guid isPermaLink=\"false\">aipulse-{_text(c['id'])}</guid>{tags}</item>")
    now = format_datetime(datetime.now(timezone.utc))
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            f"<title>AI Pulse · {_text(stream)}</title><link>{_text(site + '#' + category)}</link>"
            f"<description>{_text(about)}</description><language>en</language><lastBuildDate>{now}</lastBuildDate>"
            f'<atom:link href="{_text(site + "feeds/" + name + ".xml")}" rel="self" type="application/rss+xml"/>'
            + "".join(items) + "</channel></rss>\n").encode("utf-8")


def by_stream(cards: list[dict]) -> dict[str, list[dict]]:
    """Each feed's cards, newest first, from the full card list."""
    out: dict[str, list[dict]] = {name: [] for name in FEEDS}
    names = {category: name for name, (category, _, _) in FEEDS.items()}
    for c in sorted(cards, key=lambda c: (c["date"], c.get("added_at") or ""), reverse=True):
        name = names.get(c["category"])
        if name and len(out[name]) < PER_FEED:
            out[name].append(c)
    return out
