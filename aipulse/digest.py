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
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from html import escape

from . import rss

PER_STREAM = 25  # a long day's stream ends with a link to the rest (the RSS feed and the page have them all)
SMTP_HOST = "smtp.gmail.com"


def sender() -> str:
    return os.environ.get("DIGEST_EMAIL", "").strip()


def _mailto(subject: str) -> str:
    return f"mailto:{sender()}?subject={subject.replace(' ', '%20')}"


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
    total = sum(len(p[3]) for p in parts)
    subject = f"AI Pulse · {label}: {total} {'story' if total == 1 else 'stories'}"
    chose = ", ".join(rss.FEEDS[n][1] for n in streams)
    change = _mailto("CHANGE " + " ".join(streams))
    stop = _mailto("UNSUBSCRIBE")

    text = [f"AI Pulse daily digest · {label} (UTC) · the day's four 6-hour updates", ""]
    html = [f'<div style="font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#1a1a1a">'
            f'<h2 style="margin:0 0 4px">AI Pulse</h2><p style="margin:0 0 20px;color:#666">Daily digest · {label} (UTC) · '
            f"the day's four 6-hour updates</p>"]
    for name, stream, category, day_cards in parts:
        shown, rest = day_cards[:PER_STREAM], len(day_cards) - PER_STREAM
        text.append(f"{stream.upper()} ({len(day_cards)})")
        html.append(f'<h3 style="margin:24px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px">{escape(stream)} ({len(day_cards)})</h3><ul style="padding-left:18px">')
        for c in shown:
            summary = c.get("summary") or ""
            text.append(f"• {c['title']}\n  {summary + ' ' if summary else ''}({c['source']})\n  {c['url']}")
            html.append(f'<li style="margin-bottom:10px"><a href="{escape(c["url"])}" style="color:#1a4fd6;font-weight:bold;'
                        f'text-decoration:none">{escape(c["title"])}</a>'
                        + (f'<br><span>{escape(summary)}</span>' if summary else "")
                        + f' <span style="color:#888">({escape(c["source"])})</span></li>')
        html.append("</ul>")
        if rest > 0:
            more = f"{rss.SITE}#{category}"
            text.append(f"…and {rest} more: {more}")
            html.append(f'<p><a href="{escape(more)}">…and {rest} more on AI Pulse</a></p>')
        text.append("")
    text += [f"You chose: {chose}.", f"Change streams: {change}", f"Unsubscribe: {stop}",
             f"AI Pulse is free and non-commercial: {rss.SITE}"]
    html.append(f'<p style="margin-top:28px;color:#666;font-size:13px">You chose: {escape(chose)}. '
                f'<a href="{escape(change)}">Change streams</a> · <a href="{escape(stop)}">Unsubscribe</a><br>'
                f'AI Pulse is free and non-commercial · <a href="{rss.SITE}">{rss.SITE}</a></p></div>')
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
