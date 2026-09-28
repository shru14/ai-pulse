"""Daily digests, one RSS feed per stream: feeds/releases.xml, feeds/news.xml, feeds/policy.xml,
feeds/research.xml and feeds/regulation.xml.

A digest is one day's four 6-hour collections together: every card collected that UTC day (runs at 00:00,
06:00, 12:00 and 18:00 UTC), newest first, with its headline, one-line summary, source and link. A day's
digest appears once the day is over, so the first run of the next day publishes it (~05:30 India time).
Each feed keeps the last DAYS digests; a day with nothing in a stream gets no post. The email digest
(same days, same cards) is built from daily() too.

The static build writes the feeds next to data.json; the local server answers /feeds/<name>.xml the same way.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

from .sources import SOURCES

SITE = "https://shru14.github.io/ai-pulse/"
DAYS = 14
# How far back each source's normal collection reaches (collect: 3 days, or the source's max_age_days, e.g. 14
# for arXiv, where papers turn up a week or more after submission). A card dated further back than its source
# reaches came from a history backfill, not a regular update, so it isn't in a daily digest.
REACH: dict[str, int] = {}
for _s in SOURCES:
    REACH[_s["name"]] = max(REACH.get(_s["name"], 3), _s.get("max_age_days", 3))
STALE_DAYS = max(REACH.values())  # the furthest any source reaches (how many days of cards to read)
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


def collected_day(card: dict) -> date | None:
    """The UTC day AI Pulse collected the card, or None for a backfilled old story."""
    try:
        added = datetime.fromisoformat(card.get("added_at") or "").astimezone(timezone.utc).date()
    except ValueError:
        return None
    reach = REACH.get(card.get("source"), 3) + 1  # a day's slack for time zones
    return added if date.fromisoformat(card["date"]) >= added - timedelta(days=reach) else None


def daily(cards: list[dict], category: str, today: date | None = None, days: int = DAYS) -> dict[date, list[dict]]:
    """A stream's cards by collection day, for the last `days` complete days (newest day first, newest card
    first within a day). Today isn't over, so it isn't included."""
    today = today or datetime.now(timezone.utc).date()
    first = today - timedelta(days=days)
    out: dict[date, list[dict]] = {}
    for c in cards:
        day = collected_day(c) if c["category"] == category else None
        if day and first <= day < today:
            out.setdefault(day, []).append(c)
    for day_cards in out.values():
        day_cards.sort(key=lambda c: c.get("added_at") or "", reverse=True)
    return dict(sorted(out.items(), reverse=True))


def _item_html(c: dict) -> str:
    summary = f"<br>{escape(c['summary'])}" if c.get("summary") else ""
    return f'<li><a href="{escape(c["url"])}">{escape(c["title"])}</a>{summary} <i>({escape(c["source"])})</i></li>'


def feed_xml(name: str, cards: list[dict], today: date | None = None, site: str = SITE) -> bytes:
    """One stream's feed: a post per day, each listing that day's cards."""
    category, stream, about = FEEDS[name]
    items = []
    for day, day_cards in daily(cards, category, today).items():
        label = f"{day:%a} {day.day} {day:%b %Y}"
        body = "<ul>" + "".join(map(_item_html, day_cards)) + "</ul>"
        published = format_datetime(datetime.combine(day + timedelta(days=1), time(), timezone.utc))
        items.append(f"<item><title>{_text(stream)} · {label}</title><link>{_text(site + '#' + category)}</link>"
                     f"<description>{_text(_CONTROL.sub('', body))}</description><pubDate>{published}</pubDate>"
                     f'<guid isPermaLink="false">aipulse-{name}-{day.isoformat()}</guid></item>')
    now = format_datetime(datetime.now(timezone.utc))
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
            f"<title>AI Pulse · {_text(stream)} (daily)</title><link>{_text(site + '#' + category)}</link>"
            f"<description>{_text(about)} One post a day.</description>"
            f"<language>en</language><lastBuildDate>{now}</lastBuildDate>"
            f'<atom:link href="{_text(site + "feeds/" + name + ".xml")}" rel="self" type="application/rss+xml"/>'
            + "".join(items) + "</channel></rss>\n").encode("utf-8")
