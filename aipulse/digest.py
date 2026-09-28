"""The daily email digest: the chosen streams' stories from one UTC day's four 6-hour updates, the same days
and cards as the daily RSS feeds (rss.daily).

Sent through the project's Gmail account (smtp.gmail.com, an app password), from GitHub Actions:
DIGEST_EMAIL and DIGEST_APP_PASSWORD are repository secrets, never in the code. Every email says which
streams the reader chose and how to change them or unsubscribe (also as a List-Unsubscribe header, which
Gmail shows as an "Unsubscribe" button). No tracking pixels or tracked links: links go straight to the story.

    python -m aipulse digest --to someone@example.com [--streams releases,regulation] [--day 2026-09-27] [--dry-run page.html]
"""

from __future__ import annotations

import os
import smtplib
import ssl
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

from . import brief, rss

# Industry cards that aren't reporting, labelled (classify.news_kind), listed after the news.
KIND_LABEL = {"incident": "AI-incident", "tutorial": "Tutorial", "event": "Event", "blog": "Company blog"}
OTHER_KINDS = {"tutorial", "event", "blog"}  # AI-incidents are reporting: they stay with the news, badged
OTHER_HEADING = "Company blogs, tutorials & events"
PER_STREAM = 25
PER_LABELLED = 8  # Industry's company blogs, tutorials and events, after its news  # a long day's stream ends with a link to the rest (the RSS feed and the page have them all)
SMTP_HOST = "smtp.gmail.com"


def sender() -> str:
    return os.environ.get("DIGEST_EMAIL", "").strip()


def _mailto(subject: str) -> str:
    return f"mailto:{sender()}?subject={subject.replace(' ', '%20')}"


def _mentioned(cards: list[dict], n: int = 5) -> list[tuple[str, int]]:
    """The companies and people named most across the day's stories (tags that aren't places or topics)."""
    skip = brief._PLACE_TAGS | brief._TOPIC_TAGS | {"Research", "Study Report"}
    counts = Counter(t for c in cards for t in set(c.get("tags") or []) if t not in skip)
    return [(t, k) for t, k in counts.most_common(n) if k >= 2]


def _kpis(cards: list[dict], streams: list[str], day: date) -> tuple[list[str], str]:
    """The top of the email: each chosen stream's count for the day against the day before, and who was
    mentioned most. Returns (plain-text lines, HTML)."""
    before = day - timedelta(days=1)
    tiles, text, todays = [], [], []
    for name in streams:
        category, stream, _ = rss.FEEDS[name]
        by_day = rss.daily(cards, category, today=day + timedelta(days=1), days=2)
        now, prev = len(by_day.get(day, [])), len(by_day.get(before, []))
        todays += by_day.get(day, [])
        change = now - prev
        vs = f"{'+' if change > 0 else '−' if change < 0 else ''}{abs(change) if change else 'same as'} {'vs ' if change else ''}{before:%a}"
        text.append(f"{stream} {now} ({vs})")
        tiles.append(f'<td width="{100 // len(streams)}%" style="background:#f6f7f9;border:1px solid #e3e5e8;padding:7px 4px;'
                     f'text-align:left;vertical-align:top">'
                     f'<div style="font-size:10px;line-height:1.25;color:#5f6368">{escape(stream)}</div>'
                     f'<div style="font-size:24px;font-weight:bold;color:#1a1a1a;line-height:1.2">{now:,}</div>'
                     f'<div style="font-size:10px;color:#5f6368">{escape(vs)}</div></td>')
    top = _mentioned(todays)
    lines = ["Today: " + " · ".join(text)]
    html = ('<table role="presentation" width="100%" cellspacing="4" cellpadding="0" style="border-collapse:separate;'
            'table-layout:fixed;margin:0 0 8px"><tr>' + "".join(tiles) + "</tr></table>")
    if top:
        who = " · ".join(f"{t} ({k})" for t, k in top)
        lines.append(f"Most mentioned: {who}")
        html += f'<p style="margin:0 0 8px;font-size:13px;color:#5f6368">Most mentioned: <span style="color:#1a1a1a">{escape(who)}</span></p>'
    return lines, html


def _story_list(cards: list[dict], limit: int, more: str, text: list[str], html: list[str]) -> None:
    """Up to `limit` stories (headline, summary, source, other outlets' versions), then a link to the rest."""
    if not cards:
        return
    html.append('<ul style="padding-left:18px">')
    for c in cards[:limit]:
        kind = KIND_LABEL.get(c.get("kind", ""))
        summary = c.get("summary") or ""
        # Other outlets' versions of the same story, grouped under this one (never the story's own outlet).
        also = list({o["source"]: o for o in c.get("also") or [] if o["source"] != c["source"]}.values())
        text.append(f"• {f'[{kind}] ' if kind else ''}{c['title']}\n  {summary + ' ' if summary else ''}({c['source']})\n  {c['url']}"
                    + (f"\n  Also reported by {', '.join(o['source'] for o in also)}" if also else ""))
        others = ", ".join(f'<a href="{escape(o["url"])}" style="color:#5f6368">{escape(o["source"])}</a>' for o in also)
        badge = (f'<span style="font-size:11px;color:#5f6368;border:1px solid #d5d8dc;border-radius:3px;padding:0 4px;'
                 f'margin-right:6px">{escape(kind)}</span>') if kind else ""
        html.append(f'<li style="margin-bottom:10px">{badge}<a href="{escape(c["url"])}" style="color:#1a4fd6;font-weight:bold;'
                    f'text-decoration:none">{escape(c["title"])}</a>'
                    + (f'<br><span>{escape(summary)}</span>' if summary else "")
                    + f' <span style="color:#888">({escape(c["source"])})</span>'
                    + (f'<br><span style="font-size:13px;color:#5f6368">Also reported by {others}</span>' if also else "")
                    + "</li>")
    html.append("</ul>")
    rest = len(cards) - limit
    if rest > 0:
        text.append(f"…and {rest} more: {more}")
        html.append(f'<p><a href="{escape(more)}">…and {rest} more on AI Pulse</a></p>')


def build(cards: list[dict], streams: list[str], day: date) -> tuple[str, str, str] | None:
    """(subject, plain text, HTML) for one day, or None if the chosen streams had nothing that day."""
    label = f"{day:%a} {day.day} {day:%b %Y}"
    parts = []
    for name in streams:
        category, stream, _ = rss.FEEDS[name]
        day_cards = rss.daily(cards, category, today=day + timedelta(days=1), days=1).get(day, [])
        if day_cards:
            parts.append((name, stream, category, day_cards))
    if not parts:
        return None
    subject = f"AI Pulse daily · {label}"
    chose = ", ".join(rss.FEEDS[n][1] for n in streams)
    change = _mailto("CHANGE " + " ".join(streams))
    stop = _mailto("UNSUBSCRIBE")

    kpi_text, kpi_html = _kpis(cards, streams, day)
    text = [f"AI Pulse · Daily update · {label}", "", *kpi_text, ""]
    html = ['<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '</head><body style="margin:0;padding:12px;background:#ffffff">'
            f'<div style="font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#1a1a1a">'
            f'<h2 style="margin:0 0 4px">AI Pulse</h2><p style="margin:0 0 14px;color:#666">Daily update · {label}</p>' + kpi_html]
    for name, stream, category, day_cards in parts:
        text.append(stream.upper())
        html.append(f'<h3 style="margin:24px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px">{escape(stream)}</h3>')
        # Industry: the news first, then the labelled rest (company blogs, tutorials, events), each list with its own limit.
        news = [c for c in day_cards if c.get("kind") not in OTHER_KINDS]
        labelled = [c for c in day_cards if c.get("kind") in OTHER_KINDS]
        more = f"{rss.SITE}#{category}"
        _story_list(news, PER_STREAM, more, text, html)
        if labelled:
            text.append(f"  {OTHER_HEADING}:")
            html.append(f'<p style="margin:14px 0 6px;font-size:13px;font-weight:bold;color:#5f6368">{escape(OTHER_HEADING)}</p>')
            _story_list(labelled, PER_LABELLED, more, text, html)
        text.append("")
    feeds = [(rss.FEEDS[n][1], f"{rss.SITE}feeds/{n}.xml") for n in streams]
    text += [f"You chose: {chose}.", "RSS: " + " · ".join(f"{name} {url}" for name, url in feeds),
             f"Change streams: {change}", f"Unsubscribe: {stop}",
             f"AI Pulse is free and non-commercial: {rss.SITE}"]
    html.append(f'<p style="margin-top:28px;color:#666;font-size:13px">You chose: {escape(chose)}. '
                f'RSS: ' + " · ".join(f'<a href="{escape(url)}">{escape(name)}</a>' for name, url in feeds) + '<br>'
                f'<a href="{escape(change)}">Change streams</a> · <a href="{escape(stop)}">Unsubscribe</a><br>'
                f'AI Pulse is free and non-commercial · <a href="{rss.SITE}">{rss.SITE}</a></p></div></body></html>')
    return subject, "\n".join(text), "".join(html)


def send(to: str, subject: str, text: str, html: str) -> None:
    """Send one email through the project's Gmail account."""
    address, password = sender(), os.environ.get("DIGEST_APP_PASSWORD", "").replace(" ", "")
    if not (address and password):
        raise RuntimeError("DIGEST_EMAIL and DIGEST_APP_PASSWORD must be set")
    msg = EmailMessage()
    msg["From"] = formataddr(("AI Pulse", address))
    msg["To"] = to
    msg["Subject"] = subject
    msg["List-Unsubscribe"] = f"<{_mailto('UNSUBSCRIBE')}>"
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    with smtplib.SMTP_SSL(SMTP_HOST, 465, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(address, password)
        smtp.send_message(msg)


def yesterday() -> date:
    return datetime.now(timezone.utc).date() - timedelta(days=1)
