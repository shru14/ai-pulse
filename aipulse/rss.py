"""Daily digests, one RSS feed per stream: feeds/releases.xml, feeds/news.xml, feeds/policy.xml,
feeds/research.xml and feeds/regulation.xml.

A day's digest is what happened that day: the stream's cards dated that day (UTC), newest first, with
headline, one-line summary, source and link. It appears once the day is over. Each feed keeps the last DAYS
digests; a day with nothing in a stream gets no post. The email digest is built from daily() too.

The static build writes the feeds next to data.json; the local server answers /feeds/<name>.xml the same way.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import format_datetime
from xml.sax.saxutils import escape

SITE = "https://projectaipulse.com/"
DAYS = 14
# File name -> (category, stream name, what it carries); the names match the page's streams.
FEEDS = {
    "releases": ("tool", "Releases", "New models, products and open-source launches, straight from the labs."),
    "news": ("news", "Industry", "Company news, deals, market moves and AI incidents, from newsrooms worldwide."),
    "research": ("research", "Research", "New AI papers, from arXiv, the big labs and leading scholars."),
    "regulation": ("regulation", "Regulation tracker", "AI bills, laws, bodies and standards, from proposal to force, by country."),
    "policy": ("policy", "Policy", "What governments, courts and politicians do about AI, worldwide."),
    "infra": ("infra", "Infra & climate", "AI's data centres and their power, water, land and emissions, worldwide."),
}
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")  # not allowed in XML


def _text(value: str) -> str:
    return escape(_CONTROL.sub("", value or ""))


def daily(cards: list[dict], category: str, today: date | None = None, days: int = DAYS) -> dict[date, list[dict]]:
    """A stream's cards by the day they're dated, for the last `days` complete days (newest day first, newest
    card first within a day). Today isn't over, so it isn't included."""
    today = today or datetime.now(timezone.utc).date()
    first = (today - timedelta(days=days)).isoformat()
    out: dict[date, list[dict]] = {}
    for c in cards:
        if c["category"] == category and first <= c["date"] < today.isoformat():
            out.setdefault(date.fromisoformat(c["date"]), []).append(c)
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
