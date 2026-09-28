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

from . import brief, jurisdictions, rss

# Industry is shown in groups, each saying what it holds (classify.news_kind; AI-incidents come from the AI
# Incident Database). Order, heading and a line on what the group is.
KIND_GROUPS = [
    ("news", "News", "Reporting on companies, products, deals and people."),
    ("incident", "AI incidents", "Harms from AI systems, confirmed by the AI Incident Database."),
    ("study", "Studies", "News about research findings."),
    ("analysis", "Opinion & analysis", "Commentary, explainers and comparisons."),
    ("blog", "Company blogs", "Companies' own posts that aren't launches."),
    ("tutorial", "Tutorials", "Guides and how-tos."),
    ("event", "Events", "Previews, recaps and podcasts."),
]
KIND_LABEL = {k: label for k, label, _ in KIND_GROUPS}  # plain-text labels, and the page's badges
# What each stream holds, in a line under its heading, and its colour on the site.
SECTION_NOTE = {
    "releases": "New models, products and open-source launches.",
    "news": "What companies are doing, and what's being said about AI.",
    "research": "New papers from arXiv, top labs and leading scholars.",
    "regulation": "Bills and laws on their way from proposal to force, AI bodies and AI standards.",
    "policy": "What governments, courts and politicians are doing about AI.",
}
COLOR = {"releases": "#0f9d76", "news": "#5b5fd6", "research": "#9153d9", "regulation": "#d6457e", "policy": "#d9822b"}
ACTION_LABEL = {"proposal": "Proposal", "law": "Law adopted", "body": "AI body", "standard": "Standard"}
PER_GROUP = 12  # a long group ends with a link to the rest (the RSS feed and the page have them all)
GREY = "#5f6368"
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


def _day_cards(cards: list[dict], category: str, day: date) -> list[dict]:
    return rss.daily(cards, category, today=day + timedelta(days=1), days=1).get(day, [])


def _kpis(by_stream: dict[str, list[dict]], streams: list[str]) -> tuple[list[str], str]:
    """The top of the email: how many stories and outlets, each chosen stream's count (a tile linking to its
    section), and who was mentioned most. Returns (plain-text lines, HTML)."""
    todays = [c for n in streams for c in by_stream[n]]
    outlets = {o["source"] for c in todays for o in [c, *(c.get("also") or [])] if o.get("source")}
    stories = sum(1 + len(c.get("also") or []) for c in todays)
    intro = (f"{stories} {'story' if stories == 1 else 'stories'} from {len(outlets)} "
             f"{'source' if len(outlets) == 1 else 'sources'}, sorted into your {len(streams)} "
             f"{'stream' if len(streams) == 1 else 'streams'}.")
    tiles = []
    for n in streams:
        name = rss.FEEDS[n][1]
        tiles.append(f'<td width="{100 // len(streams)}%" style="border-top:3px solid {COLOR[n]};background:#f6f7f9;'
                     f'padding:7px 5px;vertical-align:top"><a href="#{n}" style="text-decoration:none;color:#1a1a1a">'
                     f'<div style="font-size:22px;font-weight:bold;line-height:1.2">{len(by_stream[n]):,}</div>'
                     f'<div style="font-size:11px;line-height:1.3;color:{GREY}">{escape(name)}</div></a></td>')
    lines = [intro, " · ".join(f"{rss.FEEDS[n][1]} {len(by_stream[n])}" for n in streams)]
    html = (f'<p style="margin:0 0 10px;font-size:15px">{escape(intro)}</p>'
            '<table role="presentation" width="100%" cellspacing="4" cellpadding="0" style="border-collapse:separate;'
            'table-layout:fixed;margin:0 0 6px"><tr>' + "".join(tiles) + "</tr></table>")
    top = _mentioned(todays)
    if top:
        who = " · ".join(f"{t} ({k})" for t, k in top)
        lines.append(f"Most mentioned: {who}")
        html += (f'<p style="margin:0 0 4px;font-size:13px;color:{GREY}">Most mentioned: '
                 f'<span style="color:#1a1a1a">{escape(who)}</span></p>')
    return lines, html


def _tag(c: dict) -> str:
    """A tracker card's kind and places ("Proposal · Brazil"); nothing for other streams."""
    if c.get("category") != "regulation":
        return ""
    places = ["International" if j == "INTL" else jurisdictions.JURISDICTIONS.get(j, (j,))[0]
              for j in c.get("jurisdictions") or []]
    return " · ".join(filter(None, [ACTION_LABEL.get(c.get("action") or "", ""), ", ".join(places[:3])]))


def _story_list(cards: list[dict], limit: int, more: str, text: list[str], html: list[str]) -> None:
    """Up to `limit` stories: headline, summary, then outlet and other outlets' versions; then a link to the rest."""
    for c in cards[:limit]:
        summary = c.get("summary") or ""
        tag = _tag(c)
        # Other outlets' versions of the same story, grouped under this one (never the story's own outlet).
        also = list({o["source"]: o for o in c.get("also") or [] if o["source"] != c["source"]}.values())
        meta_text = c["source"] + (" · also reported by " + ", ".join(o["source"] for o in also) if also else "")
        text.append(f"• {'[' + tag + '] ' if tag else ''}{c['title']}"
                    + (f"\n  {summary}" if summary else "") + f"\n  {meta_text}\n  {c['url']}")
        meta = escape(c["source"]) + (" · also reported by " + ", ".join(
            f'<a href="{escape(o["url"])}" style="color:{GREY}">{escape(o["source"])}</a>' for o in also) if also else "")
        html.append('<div style="margin:0 0 14px">'
                    + (f'<div style="font-size:11px;font-weight:bold;color:{GREY};text-transform:uppercase;'
                       f'letter-spacing:.3px">{escape(tag)}</div>' if tag else "")
                    + f'<a href="{escape(c["url"])}" style="color:#1a4fd6;font-weight:bold;font-size:15px;line-height:1.35;'
                      f'text-decoration:none">{escape(c["title"])}</a>'
                    + (f'<div style="font-size:14px;line-height:1.45;margin-top:3px">{escape(summary)}</div>' if summary else "")
                    + f'<div style="font-size:12px;color:{GREY};margin-top:3px">{meta}</div></div>')
    rest = len(cards) - limit
    if rest > 0:
        text.append(f"…and {rest} more: {more}")
        html.append(f'<p style="margin:0 0 14px;font-size:13px"><a href="{escape(more)}">…and {rest} more on AI Pulse</a></p>')


def _empty_note(name: str, day: date) -> str:
    if name == "research" and day.weekday() >= 5:
        return "No new papers: arXiv doesn't publish new papers at weekends."
    return "Nothing new in this stream on this day."


def build(cards: list[dict], streams: list[str], day: date) -> tuple[str, str, str] | None:
    """(subject, plain text, HTML) for one day, or None if the chosen streams had nothing that day."""
    label = f"{day:%a} {day.day} {day:%b %Y}"
    by_stream = {n: _day_cards(cards, rss.FEEDS[n][0], day) for n in streams}
    if not any(by_stream.values()):
        return None
    subject = f"AI Pulse daily · {label}"
    chose = ", ".join(rss.FEEDS[n][1] for n in streams)
    change = _mailto("CHANGE " + " ".join(streams))
    stop = _mailto("UNSUBSCRIBE")

    # The subject and sender already say "AI Pulse daily" and the day, so the email opens with the numbers.
    kpi_text, kpi_html = _kpis(by_stream, streams)
    text = [*kpi_text, ""]
    html = ['<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '</head><body style="margin:0;padding:12px;background:#ffffff">'
            '<div style="font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#1a1a1a">' + kpi_html]
    for n in streams:
        category, stream, _ = rss.FEEDS[n]
        day_cards, more = by_stream[n], f"{rss.SITE}#{category}"
        text += [f"{stream.upper()} ({len(day_cards)})", SECTION_NOTE[n]]
        html.append(f'<div id="{n}" style="margin:28px 0 12px;border-left:4px solid {COLOR[n]};padding:2px 0 2px 10px">'
                    f'<div style="font-size:19px;font-weight:bold">{escape(stream)} '
                    f'<span style="font-weight:normal;color:{GREY};font-size:15px">{len(day_cards)}</span></div>'
                    f'<div style="font-size:13px;color:{GREY}">{escape(SECTION_NOTE[n])}</div></div>')
        if not day_cards:
            text.append(_empty_note(n, day))
            html.append(f'<p style="margin:0 0 8px;font-size:14px;color:{GREY}">{escape(_empty_note(n, day))}</p>')
        elif category == "news":
            # Industry in groups, each saying what it holds; the label is said once, in the group's heading.
            for kind, heading, note in KIND_GROUPS:
                group = [c for c in day_cards if (c.get("kind") or "news") == kind]
                if not group:
                    continue
                text += ["", f"  {heading} ({len(group)}): {note}"]
                html.append(f'<div style="margin:16px 0 8px;font-size:14px"><b>{escape(heading)}</b> '
                            f'<span style="color:{GREY}">({len(group)}) · {escape(note)}</span></div>')
                _story_list(group, PER_GROUP, more, text, html)
        else:
            _story_list(day_cards, PER_GROUP * 2, more, text, html)
        text.append("")
    feeds = [(rss.FEEDS[n][1], f"{rss.SITE}feeds/{n}.xml") for n in streams]
    text += [f"You chose: {chose}.", "RSS: " + " · ".join(f"{name} {url}" for name, url in feeds),
             f"Change streams: {change}", f"Unsubscribe: {stop}",
             f"AI Pulse is free and non-commercial: {rss.SITE}"]
    html.append(f'<p style="margin-top:28px;padding-top:12px;border-top:1px solid #e3e5e8;color:{GREY};font-size:13px;'
                f'line-height:1.6">You chose: {escape(chose)}.<br>RSS: '
                + " · ".join(f'<a href="{escape(url)}" style="color:{GREY}">{escape(name)}</a>' for name, url in feeds)
                + f'<br><a href="{escape(change)}" style="color:{GREY}">Change streams</a> · '
                  f'<a href="{escape(stop)}" style="color:{GREY}">Unsubscribe</a><br>'
                  f'AI Pulse is free and non-commercial · <a href="{rss.SITE}" style="color:{GREY}">{rss.SITE}</a></p>'
                  '</div></body></html>')
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
