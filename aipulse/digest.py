"""The daily email digest: the chosen streams' stories from one UTC day's four 6-hour updates, the same days
and cards as the daily RSS feeds (rss.daily).

Sent through the project's Gmail account (smtp.gmail.com, an app password), from GitHub Actions:
DIGEST_EMAIL and DIGEST_APP_PASSWORD are repository secrets, never in the code. Every email says which
streams the reader chose and how to change them or unsubscribe (a subscriber's own one-click link, also as a
List-Unsubscribe header, which mail apps show as an "Unsubscribe" button). No tracking pixels or tracked links: links go straight to the story.

    python -m aipulse digest --to someone@example.com [--streams releases,regulation] [--day 2026-09-27] [--dry-run page.html]
"""

from __future__ import annotations

import os
import re
import smtplib
import ssl
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from pathlib import Path

from . import brief, classify, glossary, jurisdictions, quality, rss, subscribers
from .sources import SOURCES

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
STREAM_TAG = {"releases": "Release", "research": "Research paper", "regulation": "Tracker", "policy": "Policy",
              "infra": "Infra & climate"}
# What each stream holds, in a line under its heading, and its colour on the site.
SECTION_NOTE = {
    "releases": "New models, products and open-source launches.",
    "news": "What companies are doing, and what's being said about AI.",
    "research": "New papers from arXiv, top labs and leading scholars.",
    "regulation": "Bills and laws on their way from proposal to force, AI bodies and AI standards.",
    "policy": "What governments, courts and politicians are doing about AI.",
    "infra": "AI's data centres and what they draw on: power, water, land and emissions.",
}
COLOR = {"releases": "#0f9d76", "news": "#5b5fd6", "research": "#9153d9", "regulation": "#d6457e", "policy": "#d9822b",
         "infra": "#5c940d"}
ACTION_LABEL = {"proposal": "Proposal", "law": "Law adopted", "body": "AI body", "standard": "Standard"}
PER_STREAM = 25  # a longer stream ends with a link to the rest (the RSS feed and the page have them all)
SUMMARY = 160    # characters of summary in the table; the story's page has the rest
GREY, INK, LINK, RULE = "#5f6368", "#1a1a1a", "#1a4fd6", "#eceef1"
# the short email's look: a navy header band, a coloured rule over each of the top stories
NAVY, PAGE, HEADLINE = "#14213d", "#e9eef7", "#1c3faa"
BRIGHT = {"releases": "#12b886", "news": "#4c6ef5", "research": "#9c36b5", "regulation": "#e64980", "policy": "#f76707",
          "infra": "#74b816"}
SMTP_HOST = "smtp.gmail.com"


def sender() -> str:
    return os.environ.get("DIGEST_EMAIL", "").strip()


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


def _short(summary: str, limit: int = SUMMARY) -> str:
    return summary if len(summary) <= limit else summary[:limit - 3].rsplit(" ", 1)[0] + "…"


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
            "regulation": "laws in the making", "policy": "what governments did", "infra": "AI's footprint"}
    kinds = [what[n] for n in streams]
    sorted_into = (f"your {['two', 'three', 'four', 'five', 'six'][len(streams) - 2]} streams: {', '.join(kinds[:-1])} and {kinds[-1]}" if len(streams) > 1
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


# The short email: the day's most-reported stories in full, then each stream's next few headlines.
TOP = 10          # stories in "10 things that mattered today", 5 rows of 2
HEADLINES = 3     # further headlines per stream
LIGHT = TOP       # this many stories or fewer in a reader's streams: all of them in the table, never more than TOP
SIDE_KINDS = {"tutorial", "event", "blog"}  # counted in the short email, not listed
PICKS = 5         # a reader with choices: up to this many of theirs in the top 10, then the day's biggest


_OWN_BLOGS = {s["name"] for s in SOURCES if s["category"] == "tool"}  # labs' and companies' own posts


TAGS = 5  # tags shown per story in the email


def story_tags(c: dict, in_stream: bool = False) -> list[str]:
    """A story's tags as the site shows them, countries first (then companies and topics), so a reader sees at a
    glance where and who a story is about: tracker cards' countries, then the story's own tags. `in_stream`: listed
    under its own stream, where an infrastructure story leaves out the stream's name."""
    places = ["International" if j == "INTL" else jurisdictions.JURISDICTIONS.get(j, (j,))[0]
              for j in c.get("jurisdictions") or []]
    # worked out with the current rules (classify.tags_for), so the email matches the site after its next re-sort
    tags = [t for t in classify.tags_for(c.get("title") or "", c.get("summary") or "", source=c.get("source") or "") if t not in ("Research", "Study Report")]
    # Infra & climate right after the places, so a Research or Policy story about it shows the tag
    infra = [classify.INFRA_TAG] if classify.INFRA_TAG in tags and not (in_stream and c.get("category") == "infra") else []
    ordered = (places + [t for t in tags if t in brief._PLACE_TAGS] + infra
               + [t for t in tags if t not in brief._PLACE_TAGS and t != classify.INFRA_TAG])
    return list(dict.fromkeys(ordered))[:TAGS]


def _band(hello: str, daily: bool = True) -> str:
    """The short email's header: a navy row across the top of the card ("AI Pulse daily" above it, but not for a
    weekly reader, who gets only Sunday's)."""
    return (f'<tr><td style="background:{NAVY};color:#ffffff;padding:22px 20px 18px;border-radius:6px 6px 0 0">'
            + ('<div style="font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#9fb3ff;margin-bottom:6px">'
               'AI Pulse daily</div>' if daily else "")
            + f'<div style="font-size:22px;font-weight:bold;line-height:1.3;color:#ffffff">'
            f'{escape(hello)}</div></td></tr>')


def _outlets(c: dict) -> int:
    return 1 + len(_others(c))


def _rank(c: dict) -> tuple:
    """How much a story mattered, without any AI: more outlets reporting it, then a company's own launch post,
    then reporting over opinion, then an official action."""
    own = c.get("category") == "tool" and (c.get("source") or "") in _OWN_BLOGS
    return (_outlets(c), own, (c.get("kind") or "news") in ("news", "incident"), c.get("category") in ("regulation", "policy"))


def _mine(prefs: dict | None):
    """A reader's choices as tests on a story: (left out?, one of theirs?). Labels as the site shows them
    (preferences.labels, themes and continents included); their own words in the headline."""
    from . import preferences  # it builds on this module's labels
    prefs = prefs or {}
    less, more = set(prefs.get("less") or []), set(prefs.get("more") or [])
    words = [w for w in prefs.get("words") or [] if w.strip()]
    said = re.compile(r"(?<!\w)(?:" + "|".join(re.escape(w) for w in words) + r")(?!\w)", re.I) if words else None
    left = lambda c: bool(less & preferences.labels(c))
    theirs = lambda c: bool(more & preferences.labels(c)) or bool(said and said.search(c.get("title") or ""))
    return left, theirs


def _leave_out(by_stream: dict[str, list[dict]], prefs: dict | None) -> tuple[dict[str, list[dict]], list[dict]]:
    """A reader's streams without what they left out, and the stories left out (they stay in the full email)."""
    if not (prefs or {}).get("less"):
        return by_stream, []
    left, _ = _mine(prefs)
    out = {n: [c for c in v if not left(c)] for n, v in by_stream.items()}
    return out, [c for v in by_stream.values() for c in v if left(c)]


WORD_FROM = 5  # the word of the day comes from the day's 5 biggest stories in the reader's email
# The word of the day is one of these hand-marked specialist words: technical and medium hard (not an everyday
# word like Token or GPU, a product or money word, nor a niche one like JEPA; not chain of thought)
SPECIALIST = {
    "vlm", "vla", "world-model", "diffusion-model", "attention", "mixture-of-experts", "context-window", "embedding",
    "lora", "reinforcement-learning", "rlhf", "distillation", "scaling-laws", "quantization",
    "supervised-fine-tuning", "reward-model", "on-policy-distillation", "kl-divergence",
    "computer-use-agent", "mcp", "rag", "vector-database",
    "red-teaming", "prompt-injection", "interpretability", "recursive-self-improvement",
    "tpu", "asic", "hbm", "cuda", "kv-cache", "speculative-decoding", "bf16-and-fp8", "rack-scale-system",
    "test-time-compute", "swe-bench", "zero-shot-few-shot"}
_TERMS: dict[str, frozenset[str]] = {}


def _terms(c: dict) -> frozenset[str]:
    """The glossary words a story uses (worked out once per story and run)."""
    text = f"{c.get('title') or ''} {c.get('summary') or ''}"
    if text not in _TERMS:
        _TERMS[text] = frozenset(glossary.terms_in(text))
    return _TERMS[text]


def _biggest(by_stream: dict[str, list[dict]], streams: list[str]) -> list[dict]:
    """The day's WORD_FROM biggest stories in a reader's email (their streams, without what they left out),
    whatever they asked for more of."""
    todays = [c for n in streams for c in by_stream.get(n) or [] if c.get("kind") not in SIDE_KINDS]
    return sorted(todays, key=_rank, reverse=True)[:WORD_FROM]


def _text(c: dict) -> str:
    return f"{c.get('title') or ''} {c.get('summary') or ''}"


def _hardest(stories: list[dict], cards: list[dict], avoid: set[str] = frozenset()) -> str | None:
    """The hardest specialist word these stories use (SPECIALIST, not one of `avoid`): the one used least in the
    stories we have, the least familiar. None when they use none."""
    found = {i for c in stories for i in _terms(c) if i in SPECIALIST and i not in avoid}
    if not found:
        return None
    seen = Counter(i for c in cards for i in _terms(c) & found)
    # a tie goes to the word of the bigger story, then the one its headline shows
    first = {i: next(k for k, c in enumerate(stories) if i in _terms(c)) for i in found}
    return min(found, key=lambda i: (seen[i], first[i], not glossary.mentions(i, stories[first[i]].get("title") or ""), i))


def _pick_word(cards: list[dict], tiers: list[list[dict]], avoid: set[str] = frozenset()) -> tuple[str | None, list[dict]]:
    """The hardest technical word in the first tier of stories that has one: (word, that tier's stories)."""
    for stories in tiers:
        wid = _hardest(stories, cards, avoid)
        if wid:
            return wid, stories
    return None, []


def _word(cards: list[dict], day: date, streams: list[str] | None = None, prefs: dict | None = None,
          tiers: list[list[dict]] | None = None) -> tuple[list[str], str]:
    """The word of the day: the hardest specialist word in the day's biggest stories in this reader's email, else
    in their top 10, else anywhere in their email (`tiers`), and not one the week before gave; else
    glossary.word_of_the_day among SPECIALIST. With its meaning, the story that used it (a headline that shows it first) and a
    link to it in the site's glossary."""
    streams = streams or list(rss.FEEDS)
    week = set()
    for back in range(1, 8):  # the words the week before gave (their biggest stories), so none comes back within a week
        by_day = _leave_out(by_streams(cards, streams, day - timedelta(days=back)), prefs)[0]
        week.add(_pick_word(cards, [_biggest(by_day, streams)])[0])
    wid, stories = _pick_word(cards, tiers or [], week - {None})
    e = next(x for x in glossary.ENTRIES if x["id"] == wid) if wid else glossary.word_of_the_day(day, SPECIALIST)
    if wid:
        used = [c for c in stories if wid in _terms(c)]
    else:
        since = (day - timedelta(days=6)).isoformat()
        used = [c for c in cards if since <= (c.get("date") or "") <= day.isoformat() and glossary.mentions(e["id"], _text(c))]
    # A headline that shows the word beats one whose summary does; then the latest, then the most reported
    story = max(used, key=lambda c: (glossary.mentions(e["id"], c.get("title") or ""), c["date"], _outlets(c)), default=None)
    more = f"{rss.SITE}glossary/"  # the glossary page, every word A to Z
    text = ["WORD OF THE DAY: " + e["term"], e["def"], *([f"Where it came up: {story['title']} {story['url']}"] if story else []),
            f"More words in the AI Pulse glossary: {more}"]
    html = (f'<div style="margin:14px 0 12px;padding:14px 16px;background:#eef2ff;border-left:4px solid {NAVY};border-radius:4px">'
            f'<div style="font-size:11px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;color:{HEADLINE};'
            f'margin-bottom:4px">Word of the day</div>'
            f'<div style="font-size:18px;font-weight:bold;color:{NAVY}">{escape(e["term"])}</div>'
            f'<div style="font-size:14px;line-height:1.5;color:#3c4043;margin-top:3px">{escape(e["def"])}</div>'
            + (f'<div style="font-size:12.5px;line-height:1.45;color:{GREY};margin-top:7px">Where it came up: '
               f'<a href="{escape(story["url"])}" style="color:{LINK};text-decoration:none">{escape(story["title"])}</a></div>'
               if story else "")
            + f'<div style="font-size:13px;margin-top:7px"><a href="{escape(more)}" style="color:{LINK};text-decoration:none">'
              f'More words in the AI Pulse glossary →</a></div></div>')
    return text, html


# Pictures that travel inside the email (content ID -> JPEG or PNG), so the memes and the dossier's icon show in
# every mail app without waiting for the site to publish them
INLINE: dict[str, bytes] = {}
MEME_CID, MEME_WEEK_CID, DOSSIER_CID = "meme-of-the-day@aipulse", "meme-of-the-week@aipulse", "dossier@aipulse"
DOSSIER_ICON = Path(__file__).resolve().parent.parent / "templates" / "icons" / "dossier.png"  # our own drawing


def _kind(data: bytes) -> str:
    return "png" if data[:4] == b"\x89PNG" else "jpeg"


def _meme(cards: list[dict], day: date) -> tuple[list[str], str]:
    """The meme of the day (memes.py): a real meme template with the day's captions written on, sent inside the
    email; none on a day whose stories can't fill one, or when the picture can't be made."""
    from . import memes
    meme = memes.of_the_day(cards, day)
    picture = meme and memes.render(meme)
    if not picture:
        return [], ""
    INLINE[MEME_CID] = picture
    return memes.text(meme), (f'<div style="margin:0 0 14px"><div style="font-size:11px;font-weight:bold;letter-spacing:2px;'
                              f'text-transform:uppercase;color:{HEADLINE};margin-bottom:6px">Meme of the day</div>'
                              f'{memes.html(meme, "cid:" + MEME_CID, small=True)}</div>')


def preview(html: str) -> str:
    """The email as a file to look at (a dry run): its inline pictures put in the page itself."""
    import base64
    for cid, data in INLINE.items():
        html = html.replace(f"cid:{cid}", f"data:image/{_kind(data)};base64," + base64.b64encode(data).decode())
    return html


def _left_note(prefs: dict, left: list[dict]) -> str:
    """The line telling a reader what their email left out, as they asked (their own picks are marked in place)."""
    from . import preferences
    if not left:
        return ""
    why = sorted({t for c in left for t in preferences.labels(c) & set(prefs["less"])})
    return (f"Left out, as you asked: {len(left)} {'story' if len(left) == 1 else 'stories'} ({', '.join(why[:4])}); "
            f"they're in the full email.")


NEW_STREAM_UNTIL = date(2026, 10, 31)  # the new stream is announced in every email until then


def _new_stream(day: date, streams: list[str]) -> str:
    """While the sixth stream is new, for a reader who hasn't chosen it: the same note every day (the owner's
    words), with its button (see _brief). Nothing for a reader who has it."""
    if day > NEW_STREAM_UNTIL or "infra" in streams:
        return ""
    return ("New on AI Pulse: Infra & climate section, AI's data centres and the power, water and land they "
            "draw on. Add it to your feed by clicking on following button")


def _dossier(dossier: dict | None) -> tuple[list[str], str]:
    """The Sunday email's weekly dossier box, in every subscriber's email (`dossier`: {"ask": the reader's own form
    at its question box}, and for a reader whose questions have a dossier, weekly.note's {"link", "week", "entries"}):
    a line and a button with the dossier's icon: "Get my dossier" (to the form), or, once they have one, "Open your
    weekly dossier"."""
    if not dossier or not (dossier.get("entries") or dossier.get("ask")):
        return [], ""
    paper, line = "#f4f6fa", "#e3e5e8"  # the email's own colours
    ask, has = dossier.get("ask") or "", bool(dossier.get("entries"))
    pitch = "Ask what you want to follow in AI, and get last week's stories on it, picked just for you."
    icon = DOSSIER_ICON.read_bytes() if DOSSIER_ICON.exists() else b""
    if icon:
        INLINE[DOSSIER_CID] = icon

    def button(href: str, words: str) -> str:
        return (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:12px;border-collapse:separate">'
                f'<tr><td style="background:#ffffff;border:2px solid {NAVY};border-radius:8px;padding:8px 14px 8px 10px;'
                f'white-space:nowrap">'
                f'<a href="{escape(href)}" style="text-decoration:none;color:{NAVY};font-size:15px;font-weight:bold">'
                + (f'<img src="cid:{DOSSIER_CID}" width="30" height="30" alt="" style="display:inline-block;vertical-align:middle;'
                   f'border:0;margin-right:8px">' if icon else "")
                + f'<span style="vertical-align:middle;white-space:nowrap">{words}&nbsp;→</span></a></td></tr></table>')

    if has:  # the button opens the dossier page with the question box (ask.html), or, without it, the dossier
        link = ask if ask.startswith(rss.SITE + "ask.html#") else dossier["link"]
        text = [f"YOUR WEEKLY DOSSIER, {dossier['week']}", f"Open your weekly dossier: {link}"]
        kicker, title = f'WEEKLY DOSSIER · {escape(dossier["week"].upper())}', "This week on what you follow"
        action = button(link, "Open your weekly dossier")
    else:  # no questions yet: the button opens the reader's own form at its question box
        text = ["YOUR WEEKLY DOSSIER", pitch, f"Get my dossier: {ask}"]
        kicker, title, action = "WEEKLY DOSSIER", "Follow what you care about", button(ask, "Get my dossier")
    html = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0 6px;background:{paper};'
            f'border:1px solid {line};border-collapse:collapse"><tr><td style="padding:14px 16px 16px">'
            f'<div style="font-size:11px;font-weight:bold;letter-spacing:2px;color:{HEADLINE}">{kicker}</div>'
            f'<div style="font-size:19px;font-weight:bold;line-height:1.25;color:{INK};margin:4px 0 2px">{title}</div>'
            f'<div style="font-size:13.5px;line-height:1.45;color:#4a4f57">{escape(pitch)}</div>{action}</td></tr></table>')
    return text, html


# ---------- Sunday: the week ----------

WEEKLY = 5  # the day Sunday's email covers (a Saturday): it brings the week's story, word and meme (Monday to
            # Saturday) and the reader's weekly dossier, in place of the word and the meme of the day
WORD_RULE_FROM = date(2026, 9, 28)  # as the site: from this week on, never the week before's word
_STREAMS = {v[0] for v in rss.FEEDS.values()}


def weekly(day: date) -> bool:
    """Is this day's email the Sunday one, with the week?"""
    return day.weekday() == WEEKLY


def due(readers: dict, day: date) -> dict:
    """The readers who get this day's email: daily readers every day; weekly readers (choices "often": "weekly")
    only Sunday's (the day is a Saturday). `readers` as subscribers.readers gives them."""
    return {to: r for to, r in readers.items() if weekly(day) or r[3].get("often") != "weekly"}


def _week_has(cards: list[dict], day: date) -> bool:
    """Did the week (Monday to `day`) have any story in the streams?"""
    _, days = _span(day)
    return any((c.get("date") or "") in days and c.get("category") in _STREAMS for c in cards)


def _span(day: date) -> tuple[date, list[str]]:
    monday = day - timedelta(days=day.weekday())
    return monday, [(monday + timedelta(days=k)).isoformat() for k in range((day - monday).days + 1)]


def _week_story(cards: list[dict], day: date, prefs: dict | None = None) -> dict | None:
    """The story of the week, as the site picks it: the week's most reported story (then the latest), in any
    stream, not one the reader left out."""
    left, _ = _mine(prefs)
    _, days = _span(day)
    pool = [c for c in cards if (c.get("date") or "") in days and c.get("category") in _STREAMS and not left(c)]
    return max(pool, key=lambda c: (1 + len(c.get("also") or []), c.get("date") or ""), default=None)


_WEEK_WORD: dict = {}


def _week_word(cards: list[dict], day: date) -> str | None:
    """The word of the week, as the site picks it: the glossary word in the most of the week's stories, worked
    out from 3 weeks back so it's never the word of the week before (the same for every reader)."""
    if (day, len(cards)) in _WEEK_WORD:
        return _WEEK_WORD[(day, len(cards))]
    monday, _ = _span(day)
    texts = [(c.get("date") or "", _text(c)) for c in cards]
    word = None
    for back in (3, 2, 1, 0):
        since = monday - timedelta(days=7 * back)
        until = day if not back else since + timedelta(days=6)
        week = [t for d, t in texts if since.isoformat() <= d <= until.isoformat()]
        best, most = None, 0
        for e in glossary.ENTRIES:
            if e["id"] == word and since >= WORD_RULE_FROM:
                continue
            k = sum(1 for t in week if glossary.mentions(e["id"], t))
            if k > most:
                best, most = e["id"], k
        word = best
    _WEEK_WORD[(day, len(cards))] = word
    return word


def _week_meme(cards: list[dict], day: date) -> tuple[list[str], str]:
    """The meme of the week, Monday to Saturday's stories (the one the site shows from Monday, memegen.prepare)."""
    from . import memes
    monday, _ = _span(day)
    meme = memes.of_the_week([c for c in cards if (c.get("date") or "") <= day.isoformat()], monday)
    picture = meme and memes.render(meme)
    if not picture:
        return [], ""
    INLINE[MEME_WEEK_CID] = picture
    return memes.text(meme), (f'<div style="margin:16px 0 4px"><div style="font-size:11px;font-weight:bold;letter-spacing:2px;'
                              f'text-transform:uppercase;color:{HEADLINE};margin-bottom:6px">Meme of the week</div>'
                              f'{memes.html(meme, "cid:" + MEME_WEEK_CID, small=True)}</div>')


def _the_week(cards: list[dict], day: date, prefs: dict | None = None) -> tuple[list[str], str]:
    """Sunday's opening: the week (Monday to Saturday) in its story, its word and its meme."""
    monday, days = _span(day)
    span = f"{monday.day} {monday:%b} – {day.day} {day:%b}"
    week = [c for c in cards if (c.get("date") or "") in days]
    label = lambda words: (f'<div style="font-size:11px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;'
                           f'color:{HEADLINE};margin-bottom:6px">{escape(words)}</div>')
    text = [f"THE WEEK IN AI, {span}", ""]
    html = (f'<div style="font-size:22px;font-weight:bold;line-height:1.2;color:{INK};margin:22px 0 2px;padding-top:10px;'
            f'border-top:3px solid {INK}">The week in AI</div><div style="font-size:13px;color:{GREY};margin-bottom:14px">'
            f'{escape(span)}</div>')
    story = _week_story(cards, day, prefs)
    if story:
        name = next((rss.FEEDS[n][1] for n in rss.FEEDS if rss.FEEDS[n][0] == story["category"]), "")
        more = _outlets(story) - 1
        by = story["source"] + (f" +{more} outlet{'s' if more > 1 else ''}" if more else "")
        summary = _short(story.get("summary") or "", 180)
        text += ["STORY OF THE WEEK: " + story["title"], *([summary] if summary else []), f"{by}", story["url"], ""]
        html += (f'<div style="padding:12px 0 14px;border-top:4px solid {BRIGHT.get(next((n for n in rss.FEEDS if rss.FEEDS[n][0] == story["category"]), ""), NAVY)}">'
                 + label("Story of the week" + (f" · {name}" if name else ""))
                 + f'<a href="{escape(story["url"])}" style="color:{INK};font-size:19px;font-weight:bold;line-height:1.3;'
                   f'text-decoration:none">{escape(story["title"])}</a>'
                 + (f'<div style="font-size:14px;line-height:1.5;margin-top:6px;color:#4a4f57">{escape(summary)}</div>' if summary else "")
                 + f'<div style="font-size:12px;color:{GREY};margin-top:8px">{escape(by)}</div></div>')
    wid = _week_word(cards, day)
    if wid:
        e = next(x for x in glossary.ENTRIES if x["id"] == wid)
        used = sorted([c for c in week if glossary.mentions(wid, _text(c))],
                      key=lambda c: (1 + len(c.get("also") or []), c.get("date") or ""), reverse=True)
        more = f"{rss.SITE}glossary/"
        text += ["WORD OF THE WEEK: " + e["term"], e["def"], f"It came up in {len(used)} of the week's stories, like:",
                 *(f"  {c['title']} {c['url']}" for c in used[:2]), f"More words in the AI Pulse glossary: {more}", ""]
        html += (f'<div style="margin:12px 0;padding:14px 16px;background:#eef2ff;border-left:4px solid {NAVY};border-radius:4px">'
                 + label("Word of the week")
                 + f'<div style="font-size:18px;font-weight:bold;color:{NAVY}">{escape(e["term"])}</div>'
                   f'<div style="font-size:14px;line-height:1.5;color:#3c4043;margin-top:3px">{escape(e["def"])}</div>'
                   f'<div style="font-size:12.5px;line-height:1.45;color:{GREY};margin-top:7px">It came up in {len(used)} of the '
                   f'week\'s stories, like: '
                 + " · ".join(f'<a href="{escape(c["url"])}" style="color:{LINK};text-decoration:none">{escape(c["title"])}</a>'
                              for c in used[:2])
                 + f'</div><div style="font-size:13px;margin-top:7px"><a href="{escape(more)}" style="color:{LINK};'
                   f'text-decoration:none">More words in the AI Pulse glossary →</a></div></div>')
    meme_text, meme_html = _week_meme(cards, day)
    text += [*meme_text, *([""] if meme_text else [])]
    return text, html + meme_html


def _brief(by_stream: dict[str, list[dict]], cards: list[dict], streams: list[str], day: date,
           prefs: dict | None = None, left: list[dict] | None = None, dossier: dict | None = None,
           change: tuple[str, str] = ("", "")) -> tuple[list[str], str]:
    """The short email's body: an opening line, the TOP stories that mattered most (tag, headline, one line,
    how many outlets), then per stream its count, next HEADLINES headlines and a link to the rest.
    A reader with choices (`prefs`; `left`, what they left out) gets up to PICKS of theirs first, marked, then the
    day's biggest. Returns (plain-text lines, HTML)."""
    todays = [c for n in streams for c in by_stream[n]]
    outlets = {o["source"] for c in todays for o in [c, *(c.get("also") or [])] if o.get("source")}
    stories = sum(1 + len(c.get("also") or []) for c in todays)
    stream_of = {id(c): n for n in streams for c in by_stream[n]}
    sunday = weekly(day)
    hello = (f"Your week in AI, and what happened on {long_day(day)}." if sunday else
             f"Let's explore what happened in AI on {long_day(day)}.")
    counted = (f"{stories} {'story' if stories == 1 else 'stories'} from {len(outlets)} "
               f"{'source' if len(outlets) == 1 else 'sources'}")
    light = len(todays) <= LIGHT  # a lighter day in these streams: every story in the table, said plainly
    intro = f"A lighter day in your streams: {counted}." if light else f"{counted}."
    # the counts: on Sunday the week's (Monday to Saturday) and the day's, a line each, so neither is mistaken
    counts = [intro]
    if sunday:
        monday, days = _span(day)
        n = sum(1 for c in cards if (c.get("date") or "") in days and c.get("category") in _STREAMS)
        counts = [f"This week, {monday.day} {monday:%b} – {day.day} {day:%b}: {n} {'story' if n == 1 else 'stories'}.",
                  f"{day:%A}: nothing new in your streams." if not todays else
                  f"{day:%A}: {intro[0].lower() + intro[1:] if intro.startswith('A lighter') else intro}"]
    quiet = _quiet(by_stream, cards, streams, day) if todays else ""  # an empty day (a Sunday) says so once
    everything = full_page(day)  # every story of the day, whatever streams this reader chose
    top = (sorted(todays, key=_rank, reverse=True) if light else
           sorted([c for c in todays if c.get("kind") not in SIDE_KINDS], key=_rank, reverse=True)[:TOP])
    prefs = prefs or {}
    tuned = bool(prefs.get("more") or prefs.get("words"))
    _, theirs = _mine(prefs)
    picks = {id(c) for c in todays if tuned and theirs(c)}
    if tuned and not light:
        # up to PICKS of the reader's own (any kind, a tutorial too if they asked for it), then the day's biggest
        mine = sorted([c for c in todays if id(c) in picks], key=_rank, reverse=True)[:PICKS]
        biggest = [c for c in top + sorted(todays, key=_rank, reverse=True) if c not in mine]
        top = mine + list({id(c): c for c in biggest}.values())[:TOP - len(mine)]
    elif tuned:  # a lighter day: every story is in, the reader's own first
        top = sorted(top, key=lambda c: id(c) not in picks)
    title = (f"Here {'is the one story' if len(top) == 1 else f'are all {len(top)} stories'} of the day." if light
             else f"Here are the {len(top)} that mattered most.")
    if sunday:  # after the week, the day: said plainly which
        title = (f"{'The one story' if len(top) == 1 else f'All {len(top)} stories'} of {day:%A}." if light
                 else f"The {len(top)} that mattered most on {day:%A}.")
    made_for = _left_note(prefs, left or [])
    news = _new_stream(day, streams)
    # In order: the count, the word and the meme of the day, the stories, the rest in brief,
    # then the full email
    if sunday:  # the week's story, word and meme in place of the day's word and meme
        week_text, week_html = _the_week(cards, day, prefs)
        word_text, word_html, meme_text, meme_html = [], "", [], ""
    else:
        week_text, week_html = [], ""
        word_text, word_html = _word(cards, day, streams, prefs, [_biggest(by_stream, streams), top, todays])
        meme_text, meme_html = _meme(cards, day)
    dossier_text, dossier_html = _dossier(dossier)  # Sundays, for a reader with questions: their weekly dossier
    # the new stream's note carries a highlighted button to the sign-up form (`change`: the reader's own link,
    # which opens it with their email and choices filled in), so readers see their choices can be changed
    go, go_words = change[0], "Add Infra & climate"
    news_button = (f'<a href="{escape(go)}" style="display:inline-block;margin-top:8px;background:{NAVY};color:#ffffff;'
                   f'font-size:13px;font-weight:bold;text-decoration:none;padding:7px 12px;border-radius:5px">'
                   f'{escape(go_words)} →</a>' if news and go else "")
    lines = [hello, "", *counts, *([made_for] if made_for else []), *([news] if news else []),
             *([f"{go_words}: {go}"] if news_button else []),
             *([quiet] if quiet else []), *(["", *week_text] if week_text else []),
             *([*dossier_text, ""] if dossier_text else []), *(["", *word_text, ""] if word_text else []),
             *([*meme_text, ""] if meme_text else []), title]
    head = lambda words: (f'<div style="font-size:13px;font-weight:bold;color:{GREY};text-transform:uppercase;'
                          f'letter-spacing:.5px;margin:22px 0 8px">{escape(words)}</div>')
    note = lambda words, style: f'<p style="margin:0 0 10px;font-size:13px;line-height:1.5;{style}">{escape(words)}</p>'
    html = ["".join(f'<p style="margin:0 0 {4 if k < len(counts) - 1 else 10}px;font-size:15px;line-height:1.5;color:#3c4043">'
                    f'{escape(c)}</p>' for k, c in enumerate(counts))
            + (note(made_for, f"color:{GREY}") if made_for else "")
            + (f'<div style="margin:0 0 10px;font-size:13px;line-height:1.5;background:#e3f6d5;color:#2b5d0a;'
               f'padding:8px 10px 10px;border-radius:4px">{escape(news)}{"<br>" + news_button if news_button else ""}</div>'
               if news else "")
            + (note(quiet, "background:#fff8e6;padding:8px 10px;border-radius:4px") if quiet else "")
            + week_html + dossier_html + word_html + meme_html]
    if not todays:  # only on a Sunday (see build): the week above, and for the day one line, no top 10
        title = f"Nothing new in your streams on {day:%A}."
        lines[-1] = title
        lines += ["", f"Every story of the day in one table: {everything}"]
        html.append(f'<p style="margin:24px 0 0;padding-top:12px;border-top:3px solid {INK};font-size:15px;color:#3c4043">'
                    f'{escape(title)}</p><p style="margin:10px 0 0;font-size:14px"><a href="{escape(everything)}" '
                    f'style="color:{LINK};text-decoration:none;font-weight:bold">Every story of the day in one table →</a></p>')
        return lines, "".join(html)
    html.append(f'<div style="font-size:22px;font-weight:bold;line-height:1.2;color:{INK};margin:26px 0 14px;'
                f'padding-top:10px;border-top:3px solid {INK}">{escape(title)}</div>')
    cells = []
    for c in top:  # ordered by _rank, but not numbered: past the few big stories, most tie
        label, bg, fg = tag(c, stream_of[id(c)])
        more, summary, tags = _outlets(c) - 1, _short(c.get("summary") or "", 100), story_tags(c)
        by = c["source"] + (f" +{more} outlet{'s' if more > 1 else ''}" if more else "")
        yours = id(c) in picks
        lines += [f"• [{label}]{' [Your choice]' if yours else ''} {c['title']}", *([f"   {' '.join('#' + t for t in tags)}"] if tags else []), *([f"   {summary}"] if summary else []), f"   {by}", f"   {c['url']}"]
        rule = BRIGHT[stream_of[id(c)]]
        kicker = label.upper() + (" · Your choice" if yours else "").upper()
        cells.append(f'<td class="cell" valign="top" width="50%" style="padding:12px 2px 16px;border-top:4px solid {rule}">'
                     f'<div style="font-size:10.5px;font-weight:bold;letter-spacing:1.5px;color:{INK};margin-bottom:6px">'
                     f'{escape(kicker)}</div>'
                     f'<a href="{escape(c["url"])}" style="color:{INK};font-size:16px;font-weight:bold;line-height:1.3;'
                     f'text-decoration:none">{escape(c["title"])}</a>'
                     + (f'<div style="font-size:13px;line-height:1.45;margin-top:6px;color:#4a4f57">{escape(summary)}</div>'
                        if summary else "")
                     + f'<div style="font-size:11px;letter-spacing:.3px;color:{GREY};margin-top:8px">'
                       f'{escape(" · ".join([by, *("#" + t for t in tags[:2])]))}</div></td>')
    if len(cells) % 2:
        cells.append('<td class="cell" width="50%"></td>')
    # a grid of two (one on a phone): a coloured rule over each story, its kind, the headline, one line, who reported it
    gap = '<td class="gap" width="20" style="width:20px;font-size:0">&nbsp;</td>'
    html.append('<table class="grid" role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                'style="border-collapse:collapse;table-layout:fixed">'
                + "".join(f"<tr>{cells[k]}{gap}{cells[k + 1]}</tr>" for k in range(0, len(cells), 2)) + "</table>")
    lines += ["", "THE REST OF THE DAY"]
    html.append(head("The rest of the day") + '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                'style="border-collapse:collapse">')
    shown = {id(c) for c in top}
    covered, empty = [], []  # streams said in one line: all in the top stories; nothing that day
    for n in streams:
        category, stream, _ = rss.FEEDS[n]
        rest = sorted([c for c in by_stream[n] if id(c) not in shown and c.get("kind") not in SIDE_KINDS],
                      key=_rank, reverse=True)
        side = Counter(c["kind"] for c in by_stream[n] if c.get("kind") in SIDE_KINDS)
        side_words = ", ".join(f"{k} {'company blog' if w == 'blog' else w}{'s' if k > 1 else ''}" for w, k in side.items())
        extra, more = len(rest) - HEADLINES + sum(side.values()), f"{rss.SITE}#{category}"
        count = f"{len(by_stream[n])} {'story' if len(by_stream[n]) == 1 else 'stories'}"
        if not by_stream[n]:
            empty.append(stream + (" (arXiv doesn't publish at weekends)" if n == "research" and day.weekday() >= 5 else ""))
            continue
        if not rest and extra <= 0:
            covered.append(stream)
            continue
        lines.append(f"{stream} ({count})")
        if not rest:
            note = "In the list above." if light else f"In the top {len(top)} above."
            lines.append(f"  {note}")
            heads = f'<div style="font-size:13px;color:{GREY}">{escape(note)}</div>'
        else:
            lines += [f"  • {c['title']} {c['url']}" + (f"  ({' '.join('#' + t for t in story_tags(c, True))})" if story_tags(c, True) else "")
                      for c in rest[:HEADLINES]]
            heads = "".join(f'<div style="margin:0 0 7px;line-height:1.35"><a href="{escape(c["url"])}" style="color:{INK};'
                            f'font-size:14px;text-decoration:none">{escape(c["title"])}</a>'
                            + (f'<div style="font-size:11.5px;color:{GREY};margin-top:1px">'
                               f'{escape(" · ".join("#" + t for t in story_tags(c, True)))}</div>' if story_tags(c, True) else "")
                            + '</div>' for c in rest[:HEADLINES])
        if extra > 0:
            lines.append(f"  +{extra} more: {more}" + (f" (incl. {side_words})" if side_words else ""))
            heads += (f'<a href="{escape(more)}" style="color:{LINK};font-size:13px;text-decoration:none">+{extra} more on '
                      f'AI Pulse →</a>' + (f'<span style="font-size:12px;color:{GREY}"> (incl. {escape(side_words)})</span>'
                                           if side_words else ""))
        html.append(f'<tr><td valign="top" width="118" style="padding:10px;border-top:1px solid {RULE};border-left:4px solid '
                    f'{COLOR[n]}"><div style="font-size:14px;font-weight:bold">{escape(stream)}</div><div style="font-size:12px;'
                    f'color:{GREY}">{count}</div></td><td valign="top" style="padding:10px 0 10px 8px;border-top:1px solid '
                    f'{RULE}">{heads}</td></tr>')
    said = [*([("In the list above" if light else f"All in the top {len(top)}", ", ".join(covered))] if covered else []),
            *([("Nothing new today", ", ".join(empty))] if empty else [])]
    html.extend(f'<tr><td valign="top" width="118" style="padding:10px;border-top:1px solid {RULE};border-left:4px solid {RULE};'
                f'font-size:13px;font-weight:bold;color:{GREY}">{escape(k)}</td><td valign="top" style="padding:10px 0 10px 8px;'
                f'border-top:1px solid {RULE};font-size:13px;color:{GREY}">{escape(v)}</td></tr>' for k, v in said)
    html.append("</table>")
    lines += [*(f"{k}: {v}." for k, v in said), "", f"Every story of the day in one table: {everything}"]
    html.append(f'<p style="margin:16px 0 0;font-size:14px"><a href="{escape(everything)}" style="color:{LINK};'
                f'text-decoration:none;font-weight:bold">Every story of the day in one table →</a></p>')
    return lines, "".join(html)


def full_page(day: date) -> str:
    """The web page with that day's full email: every story, every stream (static.py publishes it)."""
    return f"{rss.SITE}daily/{day.isoformat()}.html"


def build(cards: list[dict], streams: list[str], day: date, unsubscribe: str = "",
          layout: str = "short", web: bool = False, prefs: dict | None = None,
          dossier: dict | None = None) -> tuple[str, str, str] | None:
    """(subject, plain text, HTML) for one day, or None if the chosen streams had nothing that day (Sunday's short
    email still goes if the week had stories: it says the day had none).
    `unsubscribe`: the reader's own one-click link (subscribers.py); without one, the footer points to the site.
    `layout`: "short", the daily email (the ten stories that mattered most, then each stream's headlines), or
    "full" (every story in one tagged table). `web`: the page version of a full email (daily/ on the site),
    with a sign-up line in place of a reader's own settings. `prefs`: the reader's choices (subscribers.prefs_of):
    what they left out never appears in their short email, and their own come first; the full email is the same
    for everyone. `dossier`: on Sundays, the reader's weekly dossier (see _dossier), in the short email only.
    Sunday's short email (the day is a Saturday, see WEEKLY) opens with the week: its story, word and meme."""
    by_stream = by_streams(cards, streams, day)
    left = []
    if layout == "short":
        by_stream, left = _leave_out(by_stream, prefs)
    sunday = layout == "short" and weekly(day)
    if not any(by_stream.values()) and not (sunday and _week_has(cards, day)):
        return None  # nothing that day; but Sunday's email goes whenever the week had stories, for the week
    subject = (f"AI Pulse · The week in AI, and {long_day(day)}" if layout == "short" and weekly(day) else
               f"AI Pulse daily · {long_day(day)}")
    chose = ", ".join(rss.FEEDS[n][1] for n in streams)
    # A reader's own link opens the form with their streams and choices filled in; saving changes them at once.
    # Without one (a sample, the web page), the sign-up form: the same address with new streams asks to confirm.
    change = subscribers.choices_link(unsubscribe) if unsubscribe else f"{rss.SITE}#subscribe"
    change_words = "Change my streams and choices" if unsubscribe else "Change streams"
    stop = unsubscribe or change
    page, band, top = "#eef0f3", "", 22
    if layout == "short":
        if weekly(day):  # every Sunday email: the dossier's button opens the reader's own form at its question box
            dossier = {**(dossier or {}), "ask": subscribers.ask_link(unsubscribe) if unsubscribe else change}  # (a sample: sign-up)
        open_text, open_html = _brief(by_stream, cards, streams, day, prefs, left, dossier, (change, change_words))
        table_text, table_html = [], ""
        page, band, top = PAGE, _band(open_text[0], (prefs or {}).get("often") != "weekly"), 16
    else:
        open_text, open_html = _opening(by_stream, cards, streams, day)
        table_text, table_html = _ledger(by_stream, streams, day)
    feeds = [(rss.FEEDS[n][1], f"{rss.SITE}feeds/{n}.xml") for n in streams]
    # a reader's email asks them to pass it on; the friend signs up on the site
    forward = f"Know someone who'd like this? Forward this email; they can sign up free at {rss.SITE}#subscribe"
    settings = (["Get AI Pulse daily in your inbox: " + change] if web else
                [forward, f"You chose: {chose}.", "RSS: " + " · ".join(f"{name} {url}" for name, url in feeds),
                 f"{change_words}: {change}", f"Unsubscribe: {stop}"])
    text = [*open_text, *table_text, "", *settings, f"AI Pulse is free and non-commercial: {rss.SITE}"]
    settings_html = (f'<a href="{escape(change)}" style="color:{GREY}">Get AI Pulse daily in your inbox</a><br>' if web else
                     f'<span style="color:{INK}">Know someone who&#39;d like this? Forward this email; they can '
                     f'<a href="{rss.SITE}#subscribe" style="color:{LINK}">sign up free</a>.</span><br>'
                     f'You chose: {escape(chose)}.<br>RSS: '
                     + " · ".join(f'<a href="{escape(url)}" style="color:{GREY}">{escape(name)}</a>' for name, url in feeds)
                     + f'<br><a href="{escape(change)}" style="color:{GREY}">{change_words}</a> · '
                       f'<a href="{escape(stop)}" style="color:{GREY}">Unsubscribe</a><br>')
    html = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(subject)}</title><style>@media (max-width:520px){{.grid .cell{{display:block!important;'
            f'width:100%!important}}.grid .gap{{display:none!important}}}}</style></head><body style="margin:0;padding:0;background:{page}">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{page}"><tr>'
            '<td align="center" style="padding:12px 8px 24px">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;background:#ffffff;'
            f'border-radius:6px;font-family:Arial,sans-serif;color:{INK}">{band}<tr><td style="padding:{top}px 20px 10px">'
            + open_html + table_html
            + f'<p style="margin-top:28px;padding-top:12px;border-top:1px solid #e3e5e8;color:{GREY};font-size:13px;'
              f'line-height:1.6">' + settings_html
            + f'AI Pulse is free and non-commercial · <a href="{rss.SITE}" style="color:{GREY}">{rss.SITE}</a></p>'
              '</td></tr></table></td></tr></table></body></html>')
    return subject, "\n".join(text), html


def _message(to: str, subject: str, text: str, html: str, unsubscribe: str = "") -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr(("AI Pulse", sender()))
    msg["To"] = to  # one reader per email: nobody sees anyone else's address
    msg["Subject"] = subject
    if unsubscribe.startswith("https://"):  # mail apps show an "Unsubscribe" button that works in one click
        msg["List-Unsubscribe"] = f"<{unsubscribe}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    for cid, data in INLINE.items():  # the meme, inside the email
        if f"cid:{cid}" in html:
            kind = _kind(data)
            msg.get_payload()[1].add_related(data, "image", kind, cid=f"<{cid}>",
                                             filename=f"{'dossier' if cid == DOSSIER_CID else 'meme'}.{'png' if kind == 'png' else 'jpg'}")
    return msg


def send_all(emails: list[tuple]) -> int:
    """Send (to, subject, text, HTML[, unsubscribe link]) emails through the project's Gmail account over one connection.
    Returns how many were sent; one failed address doesn't stop the rest."""
    address, password = sender(), os.environ.get("DIGEST_APP_PASSWORD", "").replace(" ", "")
    if not (address and password):
        raise RuntimeError("DIGEST_EMAIL and DIGEST_APP_PASSWORD must be set")
    sent = 0
    with smtplib.SMTP_SSL(SMTP_HOST, 465, context=ssl.create_default_context(), timeout=30) as smtp:
        smtp.login(address, password)
        for email in emails:
            try:
                smtp.send_message(_message(*email))
                sent += 1
            except smtplib.SMTPRecipientsRefused:
                pass  # a bad address; counted as not sent (never printed: the logs are public)
    return sent


def send(to: str, subject: str, text: str, html: str) -> None:
    """Send one email through the project's Gmail account."""
    if not send_all([(to, subject, text, html)]):
        raise RuntimeError("the email was refused")


def yesterday() -> date:
    return datetime.now(timezone.utc).date() - timedelta(days=1)
