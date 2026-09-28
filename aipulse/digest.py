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

from . import brief, jurisdictions, quality, rss

# Every story wears a tag saying what it is. Industry's are its sub-categories (classify.news_kind; AI-incidents
# come from the AI Incident Database), in this order: label, tag background, tag text colour.
KIND = {
    "news": ("News", "#e8eaf6", "#3949ab"),
    "incident": ("AI-incident", "#fde7e9", "#c5221f"),
    "study": ("Study", "#e6f4ea", "#137333"),
    "analysis": ("Opinion & analysis", "#fef7e0", "#8a5a00"),
    "blog": ("Company blog", "#e8f0fe", "#1967d2"),
    "tutorial": ("Tutorial", "#f3e8fd", "#7b1fa2"),
    "event": ("Event", "#e0f7fa", "#00737a"),
}
STREAM_TAG = {"releases": "Release", "research": "Research paper", "regulation": "Tracker", "policy": "Policy"}
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
PER_STREAM = 25  # a longer stream ends with a link to the rest (the RSS feed and the page have them all)
SUMMARY = 160    # characters of summary in the table; the story's page has the rest
GREY, INK, LINK, RULE = "#5f6368", "#1a1a1a", "#1a4fd6", "#eceef1"
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


def by_streams(cards: list[dict], streams: list[str], day: date) -> dict[str, list[dict]]:
    """What the email shows: each chosen stream's stories that day, less any that don't name AI (quality.on_topic).
    Industry is ordered by its tags (news first, then AI-incidents, studies, opinion...)."""
    out = {n: [c for c in _day_cards(cards, rss.FEEDS[n][0], day) if quality.on_topic(c)] for n in streams}
    if "news" in out:
        out["news"].sort(key=lambda c: list(KIND).index(c.get("kind") if c.get("kind") in KIND else "news"))
    return out


def left_out(cards: list[dict], streams: list[str], day: date) -> list[dict]:
    """The day's stories kept out of the email for not naming AI."""
    return [c for n in streams for c in _day_cards(cards, rss.FEEDS[n][0], day) if not quality.on_topic(c)]


def long_day(day: date) -> str:
    return f"{day:%A}, {day.day} {day:%B %Y}"  # "Sunday, 27 September 2026": no short forms


def _quiet(by_stream: dict[str, list[dict]], cards: list[dict], streams: list[str], day: date) -> str:
    """On a thin day, a line saying so and how it compares with a usual day; "" otherwise."""
    n = quality.total(by_stream)
    if n >= quality.THIN:
        return ""
    usual = round(sum(quality.usual(cards, rss.FEEDS[s][0], day) for s in streams))
    line = f"A quiet day for AI: only {n} {'story' if n == 1 else 'stories'} across your streams"
    line += f", where a usual day brings about {usual}." if usual > n else "."
    if day.weekday() >= 5:
        line += " Weekends are usually slow: fewer launches, and arXiv doesn't publish new papers."
    return line


def tag(c: dict, stream: str) -> tuple[str, str, str]:
    """(label, background, text colour) of a story's tag: Industry's sub-category, a tracker card's kind and
    places ("Proposal · Brazil"), or the stream's kind of story."""
    if stream == "news":
        return KIND.get(c.get("kind") or "news", KIND["news"])
    if stream == "regulation":
        places = ["International" if j == "INTL" else jurisdictions.JURISDICTIONS.get(j, (j,))[0]
                  for j in c.get("jurisdictions") or []]
        label = " · ".join(filter(None, [ACTION_LABEL.get(c.get("action") or "", ""), ", ".join(places[:3])]))
        return label or STREAM_TAG[stream], "#fce4ec", "#ad1457"
    return STREAM_TAG[stream], "#f1f3f4", COLOR[stream]


def breakdown(day_cards: list[dict], stream: str) -> str:
    """Industry's count by tag ("12 news · 1 study · 3 opinion & analysis"); other streams say what they hold."""
    if stream != "news":
        return SECTION_NOTE[stream]
    counts = Counter(c.get("kind") or "news" for c in day_cards)
    return " · ".join(f"{counts[k]} {label if label.startswith('AI') else label.lower()}"
                      for k, (label, _, _) in KIND.items() if counts[k]) or SECTION_NOTE[stream]


def _short(summary: str) -> str:
    return summary if len(summary) <= SUMMARY else summary[:SUMMARY - 3].rsplit(" ", 1)[0] + "…"


def _others(c: dict) -> list[dict]:
    """Other outlets' versions of the same story (never the story's own outlet)."""
    return list({o["source"]: o for o in c.get("also") or [] if o["source"] != c["source"]}.values())


def _opening(by_stream: dict[str, list[dict]], cards: list[dict], streams: list[str], day: date) -> tuple[list[str], str]:
    """The top of the email: a line inviting the reader in, what was read and how it's sorted, who came up most,
    a quiet-day line when there was little, and the day at a glance (a row per stream, linking to its part of
    the table). Returns (plain-text lines, HTML)."""
    todays = [c for n in streams for c in by_stream[n]]
    outlets = {o["source"] for c in todays for o in [c, *(c.get("also") or [])] if o.get("source")}
    stories = sum(1 + len(c.get("also") or []) for c in todays)
    hello = f"Let's explore what happened in AI on {long_day(day)}."
    what = {"releases": "launches", "news": "the business of AI", "research": "new research",
            "regulation": "laws in the making", "policy": "what governments did"}
    kinds = [what[n] for n in streams]
    sorted_into = (f"your {['two', 'three', 'four', 'five'][len(streams) - 2]} streams: {', '.join(kinds[:-1])} and {kinds[-1]}" if len(streams) > 1
                   else f"your stream, {kinds[0]}")
    intro = (f"We read {stories} {'story' if stories == 1 else 'stories'} from {len(outlets)} "
             f"{'source' if len(outlets) == 1 else 'sources'} and sorted them into {sorted_into}.")
    top = _mentioned(todays)
    names = ("The names that came up most: " + ", ".join(f"{t} ({k} stories)" for t, k in top) + ".") if top else ""
    quiet = _quiet(by_stream, cards, streams, day)
    lines = [hello, "", intro, *([names] if names else []), *([quiet] if quiet else []), "", "THE DAY AT A GLANCE"]
    lines += [f"{rss.FEEDS[n][1]}: {len(by_stream[n])} ({breakdown(by_stream[n], n)})" for n in streams]
    rows = "".join(
        f'<tr><td style="padding:8px 10px;border-bottom:1px solid {RULE};border-left:4px solid {COLOR[n]}">'
        f'<a href="#{n}" style="color:{INK};text-decoration:none;font-weight:bold">{escape(rss.FEEDS[n][1])}</a>'
        f'<div style="font-size:12px;color:{GREY}">{escape(breakdown(by_stream[n], n))}</div></td>'
        f'<td align="right" style="padding:8px 10px;border-bottom:1px solid {RULE};font-size:20px;font-weight:bold">'
        f'{len(by_stream[n]):,}</td></tr>' for n in streams)
    html = (f'<div style="font-size:22px;font-weight:bold;line-height:1.3;margin:0 0 8px">{escape(hello)}</div>'
            f'<p style="margin:0 0 8px;font-size:15px;line-height:1.5">{escape(intro)}</p>'
            + (f'<p style="margin:0 0 10px;font-size:14px;color:{GREY}">{escape(names)}</p>' if names else "")
            + (f'<p style="margin:0 0 10px;font-size:14px;background:#fff8e6;padding:8px 10px">{escape(quiet)}</p>' if quiet else "")
            + f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;'
              f'margin:6px 0 8px;background:#f8f9fb">{rows}</table>')
    return lines, html


def _pill(label: str, bg: str, fg: str) -> str:
    return (f'<span style="display:inline-block;background:{bg};color:{fg};font-size:11px;font-weight:bold;'
            f'padding:3px 8px;border-radius:10px;white-space:nowrap">{escape(label)}</span>')


def _ledger(by_stream: dict[str, list[dict]], streams: list[str], day: date) -> tuple[list[str], str]:
    """The day as one table (type | story and a line of summary | source), a part per stream. Returns
    (plain-text lines, HTML)."""
    cell = f"padding:8px;border-bottom:1px solid {RULE}"
    rows = ["<tr>" + "".join(f'<th align="left" style="padding:6px 8px;font-size:11px;color:{GREY};text-transform:uppercase;'
                             f'letter-spacing:.4px;border-bottom:2px solid #d9dce1">{h}</th>' for h in ("Type", "Story", "Source"))
            + "</tr>"]
    text = []
    for n in streams:
        category, stream, _ = rss.FEEDS[n]
        day_cards, more = by_stream[n], f"{rss.SITE}#{category}"
        text += ["", f"{stream.upper()} ({len(day_cards)}): {SECTION_NOTE[n]}"]
        rows.append(f'<tr id="{n}"><td colspan="3" style="padding:18px 8px 6px;font-size:15px;font-weight:bold;'
                    f'border-bottom:2px solid {COLOR[n]}">{escape(stream)} <span style="font-weight:normal;color:{GREY};'
                    f'font-size:13px">· {len(day_cards)} · {escape(SECTION_NOTE[n])}</span></td></tr>')
        if not day_cards:
            note = _empty_note(n, day)
            text.append(note)
            rows.append(f'<tr><td colspan="3" style="padding:8px;font-size:13px;color:{GREY}">{escape(note)}</td></tr>')
        for i, c in enumerate(day_cards[:PER_STREAM]):
            label, bg, fg = tag(c, n)
            summary, others = _short(c.get("summary") or ""), _others(c)
            text.append(f"• [{label}] {c['title']} ({c['source']})" + (f"\n  {summary}" if summary else "")
                        + (f"\n  Also reported by {', '.join(o['source'] for o in others)}" if others else "")
                        + f"\n  {c['url']}")
            also = ", ".join(f'<a href="{escape(o["url"])}" style="color:{GREY}">{escape(o["source"])}</a>' for o in others)
            rows.append(f'<tr style="background:{"#fafbfc" if i % 2 else "#ffffff"}">'
                        f'<td valign="top" style="{cell}">{_pill(label, bg, fg)}</td>'
                        f'<td valign="top" style="{cell}"><a href="{escape(c["url"])}" style="color:{LINK};font-weight:bold;'
                        f'font-size:14px;line-height:1.35;text-decoration:none">{escape(c["title"])}</a>'
                        + (f'<div style="font-size:13px;color:#3c4043;margin-top:2px;line-height:1.4">{escape(summary)}</div>'
                           if summary else "")
                        + f'</td><td valign="top" style="{cell};font-size:12px;color:{GREY}">{escape(c["source"])}'
                        + (f'<div style="margin-top:3px">also reported by {also}</div>' if others else "") + "</td></tr>")
        rest = len(day_cards) - PER_STREAM
        if rest > 0:
            text.append(f"…and {rest} more: {more}")
            rows.append(f'<tr><td colspan="3" style="padding:8px;font-size:13px"><a href="{escape(more)}" style="color:{LINK}">'
                        f'…and {rest} more {escape(stream)} stories on AI Pulse</a></td></tr>')
    return text, (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;'
                  f'margin-top:14px">{"".join(rows)}</table>')


def _empty_note(name: str, day: date) -> str:
    if name == "research" and day.weekday() >= 5:
        return "No new papers: arXiv doesn't publish new papers at weekends."
    return "Nothing new in this stream on this day."


def build(cards: list[dict], streams: list[str], day: date) -> tuple[str, str, str] | None:
    """(subject, plain text, HTML) for one day, or None if the chosen streams had nothing that day."""
    by_stream = by_streams(cards, streams, day)
    if not any(by_stream.values()):
        return None
    subject = f"AI Pulse daily · {long_day(day)}"
    chose = ", ".join(rss.FEEDS[n][1] for n in streams)
    change = _mailto("CHANGE " + " ".join(streams))
    stop = _mailto("UNSUBSCRIBE")
    open_text, open_html = _opening(by_stream, cards, streams, day)
    table_text, table_html = _ledger(by_stream, streams, day)
    feeds = [(rss.FEEDS[n][1], f"{rss.SITE}feeds/{n}.xml") for n in streams]
    text = [*open_text, *table_text, "", f"You chose: {chose}.",
            "RSS: " + " · ".join(f"{name} {url}" for name, url in feeds),
            f"Change streams: {change}", f"Unsubscribe: {stop}", f"AI Pulse is free and non-commercial: {rss.SITE}"]
    html = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '</head><body style="margin:0;padding:0;background:#eef0f3">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:12px 8px 24px">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;background:#ffffff;'
            f'border-radius:6px;font-family:Arial,sans-serif;color:{INK}"><tr><td style="padding:22px 20px 10px">'
            + open_html + table_html
            + f'<p style="margin-top:28px;padding-top:12px;border-top:1px solid #e3e5e8;color:{GREY};font-size:13px;'
              f'line-height:1.6">You chose: {escape(chose)}.<br>RSS: '
            + " · ".join(f'<a href="{escape(url)}" style="color:{GREY}">{escape(name)}</a>' for name, url in feeds)
            + f'<br><a href="{escape(change)}" style="color:{GREY}">Change streams</a> · '
              f'<a href="{escape(stop)}" style="color:{GREY}">Unsubscribe</a><br>'
              f'AI Pulse is free and non-commercial · <a href="{rss.SITE}" style="color:{GREY}">{rss.SITE}</a></p>'
              '</td></tr></table></td></tr></table></body></html>')
    return subject, "\n".join(text), html


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
