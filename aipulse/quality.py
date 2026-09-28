"""Checks a day's digest before it's emailed. Any problem holds the email for everyone and an alert goes to the
project inbox instead: a wrongly sorted, duplicated, garbled or off-topic story is never mailed to readers.

What's checked, for every story in the chosen streams (the ones the email shows):
  - sorting: a government's own publication never in Industry or Releases; no paper (arXiv) in the tracker;
    no standards story in Releases; AI-incidents only in Industry; every Industry story has a label;
  - on topic: a story from a general feed that doesn't name AI is left out of the email (not held; logged);
  - no duplicates: the same link or headline never twice, and no story listed under itself;
  - clean text: a real headline (not empty or "No title"), no leftover HTML, no garbled characters, and
    every link a plain http(s) address;
  - an unusual day: a stream with far more stories than usual (a source misbehaving), or nothing at all.
A thin day (a few stories) isn't a problem: it's sent, saying it was a quiet day.
"""

from __future__ import annotations

import re
import statistics
from datetime import date, timedelta

from . import rss
from .classify import about_standards, is_ai_related
from .sources import SOURCES

GOVERNMENT = {s["name"] for s in SOURCES if s.get("government")}
# General feeds whose stories are kept only when they name AI (as collect.py filters them), plus the two science
# feeds that are re-checked; AI-only feeds (labs' blogs, MarkTechPost, arXiv) are about AI by definition.
MUST_NAME_AI = {s["name"] for s in SOURCES if not s.get("ai_only", s["category"] == "tool")} | {"ScienceDaily", "Tech Xplore"}
LABELS = {"news", "incident", "study", "analysis", "blog", "tutorial", "event"}  # digest.KIND_GROUPS
PLACEHOLDER = re.compile(r"^\s*(?:no title|untitled|none|null|undefined|n/?a|title|\[?removed\]?|-+)\s*$", re.I)
HTML_LEFTOVER = re.compile(r"</?[a-z][a-z0-9]*(?:\s[^<>]*)?/?>|&(?:[a-z]+|#\d+|#x[0-9a-f]+);", re.I)
# Mojibake (UTF-8 read as Latin-1: "â€™", "Ã©"), the replacement character and control characters.
GARBLED = re.compile("�|â€|Ã[\u0080-¿]|Â[ -¿]|[\u0000-\u0008\u000b\u000c\u000e-\u001f]")
LINK = re.compile(r"^https?://[^\s<>\"']+$")
SURGE, SURGE_FLOOR, HISTORY_DAYS = 3, 25, 14  # a stream over 3x its usual day (and over 25) is held
THIN = 5  # fewer stories than this: sent, with a line saying it was a quiet day


def _norm(title: str) -> str:
    return re.sub(r"\W+", " ", title.lower()).strip()


def on_topic(c: dict) -> bool:
    """False for a story from a general feed that doesn't name AI: it's left out of the email (and logged),
    rather than holding everyone's email over one borderline story."""
    return (c.get("source") not in MUST_NAME_AI or c.get("category") == "regulation"
            or is_ai_related(c.get("title") or "", c.get("summary") or ""))


def _story_problems(c: dict, stream: str) -> list[str]:
    title, summary, url, source = c.get("title") or "", c.get("summary") or "", c.get("url") or "", c.get("source") or ""
    category = c.get("category")
    out = []
    if len(title.strip()) < 8 or PLACEHOLDER.match(title):
        out.append("no real headline")
    for name, text in (("headline", title), ("summary", summary)):
        if HTML_LEFTOVER.search(text):
            out.append(f"HTML left in the {name}")
        if GARBLED.search(text):
            out.append(f"garbled characters in the {name}")
    if not LINK.match(url):
        out.append(f"link isn't a plain web address ({url[:60] or 'empty'})")
    if source in GOVERNMENT and category in ("news", "tool") and c.get("action") != "incident":
        out.append(f"a government's own publication ({source}) in {stream}")
    if category == "regulation" and ("arxiv.org" in url or source.lower().startswith("arxiv")):
        out.append(f"a research paper in {stream}")
    if category == "tool" and about_standards(title):
        out.append(f"a standards story in {stream}")
    if c.get("action") == "incident" and category != "news":
        out.append(f"an AI-incident in {stream}")
    if category == "news" and (c.get("kind") or "news") not in LABELS:
        out.append(f"no label in {stream} ({c.get('kind')})")
    for o in c.get("also") or []:
        if o.get("url") == url or o.get("source") == source and _norm(o.get("title") or "") == _norm(title):
            out.append("listed under itself as another outlet's version")
            break
    return out


def usual(cards: list[dict], category: str, day: date) -> float:
    """A stream's median day over the two weeks before `day` (0 for a new stream)."""
    before = rss.daily(cards, category, today=day, days=HISTORY_DAYS)
    return statistics.median([len(before.get(day - timedelta(days=k), [])) for k in range(1, HISTORY_DAYS + 1)])


def problems(by_stream: dict[str, list[dict]], cards: list[dict], day: date) -> list[str]:
    """Everything wrong with the day's email, one line each ("" list: fine to send). `by_stream` is what the
    email shows; `cards` covers the two weeks before too, for what's usual."""
    out, links, titles = [], {}, {}
    for name, day_cards in by_stream.items():
        category, stream, _ = rss.FEEDS[name]
        for c in day_cards:
            where = f'{stream}: "{(c.get("title") or "")[:90]}" ({c.get("source")}, {c.get("url")})'
            out += [f"{p}. {where}" for p in _story_problems(c, stream)]
            for seen, key in ((links, c.get("url")), (titles, _norm(c.get("title") or ""))):
                if key and key in seen:
                    out.append(f"shown twice (also in {seen[key]}). {where}")
                elif key:
                    seen[key] = stream
        typical = usual(cards, category, day)
        if len(day_cards) > max(SURGE * typical, SURGE_FLOOR):
            out.append(f"{stream} has {len(day_cards)} stories, over {SURGE}x its usual {typical:g} a day: a source may "
                       "have misbehaved (or old stories were re-dated).")
    if not any(by_stream.values()):
        out.append(f"No stories at all on {day}: collection may have failed.")
    return out


def total(by_stream: dict[str, list[dict]]) -> int:
    return sum(len(v) for v in by_stream.values())


def alert(day: date, found: list[str], streams: list[str]) -> tuple[str, str, str]:
    """(subject, text, HTML) of the note to the project inbox when a digest is held."""
    from html import escape
    subject = f"AI Pulse digest HELD · {day}: {len(found)} problem{'s' if len(found) != 1 else ''}"
    intro = (f"The daily digest for {day} ({', '.join(streams)}) was not sent to anyone, because the check "
             "before sending found the problems below. Fix them (or the rule that flagged them) and send it again.")
    text = "\n".join([intro, "", *[f"- {p}" for p in found]])
    html = ('<div style="font-family:Arial,sans-serif;max-width:640px;color:#1a1a1a">'
            f'<p style="font-size:15px">{escape(intro)}</p><ol style="font-size:14px;line-height:1.5">'
            + "".join(f"<li>{escape(p)}</li>" for p in found) + "</ol></div>")
    return subject, text, html
