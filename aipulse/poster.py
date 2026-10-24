"""The poster email (on trial): the daily digest in the site's Swiss-poster look. In order: the hot story (the
day's most-reported), top news, the word and meme of the day, the number of the day, the newest page on the site,
the rest of the day by reader ("Pick your lane"), the review strip, then The Firehose: a row per stream that opens
every story of the day on the site. One layout at every width (no phone-only rules), so phones show what a computer
does. Nothing in it is written by AI: headlines and sentences are the outlets' own, pictures are our own drawings
(templates/photos/cartoons, as PNG: mail apps don't show SVG), picked by each story's tags and linked from the site
(see _picture); only the meme travels inside the email.

    python -m aipulse digest --to someone@example.com --layout poster [--day 2026-10-23] [--dry-run page.html]
"""

from __future__ import annotations

import os
import re
import urllib.request
from datetime import date
from html import escape
from pathlib import Path

from . import classify, digest, pages, rss

ART = Path(__file__).resolve().parent.parent / "templates" / "photos" / "cartoons" / "png"
HEAD = "'Archivo Black','Arial Black',Arial,sans-serif"  # headings; Gmail has no web fonts: Arial Black there
BODY = "Arial,Helvetica,sans-serif"
INK, GREY, YELLOW, BLUE, VERMILION = "#000000", "#4a4a4a", "#F0E442", "#0072B2", "#B85000"
# The streams' Okabe-Ito fills (the site's --f-*), black text on them
FILL = {"releases": "#009E73", "news": "#56B4E9", "research": "#C85BC3", "regulation": "#F85C48", "policy": "#E69F00",
        "infra": "#8BEC8B"}
FEATURE_FILL = {"tool": FILL["releases"], "news": FILL["news"], "research": FILL["research"], "reg": FILL["regulation"],
                "policy": FILL["policy"], "infra": FILL["infra"]}
TOP_NEWS = 6  # after the hot story
LANE_STORIES = 3

# A story's picture: a drawing that shows its subject, only when its tags or headline name that subject (a
# court case: a gavel; chips: a chip; power: a power plant); else its stream's own drawing, which says what kind of
# story it is. Drawings that only stand for one of our pages (timelines, checklists, cards) are never used here.
ART_RULES = [
    (set(), r"\b(sues?|sued|lawsuits?|court|judge|trial)\b", "ai-in-court"),
    (set(), r"\b(fined|fines|fining|penalt(?:y|ies)|banned|bans|ban on)\b", "ai-fines-and-bans"),
    ({"Export Controls"}, r"\bexport", "chip-export-rules"),
    ({"M&A"}, r"\b(acquires?|acquired|acquisition|buys|buyout|takeover)\b", "ai-buyouts"),
    ({"IPO", "Funding"}, r"\b(IPO|raises|raised|funding|investment|round|Series [A-H]|valuation|stake)\b", "who-owns-a-piece-of-whom"),
    (set(), r"\b(retire[sd]?|deprecat\w*|shut(?:s|ting)? down|sunset)\b", "models-being-retired"),
    (set(), r"\b(prices?|pricing)\b", "model-economy"),
    ({"Jobs & Labor"}, r"\b(jobs?|layoffs?|laid off|workers?|workforce|hiring|cuts|culls?|staff)\b", "jobs-blamed-on-ai"),
    ({"Deepfakes", "Misuse", "Elections"}, "", "harm-to-rule"),
    ({"Safety", "Alignment", "Existential Risk"}, "", "ai-safety-hub"),
    ({"Benchmarks"}, r"\b(benchmarks?|leaderboards?|scores?|tests?|evals?|evaluations?)\b", "new-tests-for-ai"),
    ({"Chips"}, "", "compute-behind-notable-models"),
    ({"Land & local pushback", "Rules & permits"}, r"\b(oppos\w*|protest\w*|pushback|permits?|zoning|moratorium|reject\w*|deny|denied|residents|community)\b", "pushback-and-permits"),
    ({"Power & grid", "Energy", "Water", "Emissions & climate"}, r"\b(power|energy|grid|electric\w*|nuclear|solar|wind|gas|water|cooling|emissions|[MG]W|megawatts?|gigawatts?)\b", "who-powers-ai"),
    ({"Builds & deals", "Compute & Data Centers"}, r"\b(data cent(?:er|re)s?|campus|build)", "data-centre-builds"),
]

# "Pick your lane": who a story matters to, from its stream and tags (a story goes in the first lane that takes it)
_MONEY_WORDS = re.compile(r"\b(stocks?|shares|markets?|earnings|investors?|valuation|rally|futures|revenue|forecast|IPO)\b", re.I)
LANES = [
    ("Founders", "founders", lambda n, t, title: n in ("news", "releases") and bool(t & {"Funding", "M&A", "Agents", "Healthcare"})),
    ("Builders", "builders", lambda n, t, title: n == "releases" or (n != "research" and bool(t & {"Coding Tools", "Open Models", "Benchmarks", "Multimodal"}))),
    ("Investors", "investors", lambda n, t, title: bool(t & {"IPO", "Funding", "M&A", "Chips", "Builds & deals"}) or bool(_MONEY_WORDS.search(title))),
    ("Policy & law", "policy", lambda n, t, title: n in ("policy", "regulation") or bool(t & {"Law", "Regulation", "Governance", "Export Controls", "Elections", "Deepfakes", "Copyright", "Antitrust", "Privacy", "Misuse"})),
    ("Researchers", "research", lambda n, t, title: n == "research"),
]

# The number of the day: a sum of money in a story's headline or summary, shown with the outlet's own sentence
_MONEY = re.compile(r"(?:US|A|C|S|HK)?([$€£])\s?(\d{1,4}(?:\.\d{1,2})?)\s?(trillion|billion|million|bn|mn|tn)\b", re.I)
_UNIT = {"trillion": "T", "tn": "T", "billion": "B", "bn": "B", "million": "M", "mn": "M"}
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“])")
_ABBREVIATION = re.compile(r"\b(?:Inc|Co|Corp|Ltd|Mr|Ms|Dr|St|No|vs|[A-Z])\.$")  # "Pathos AI Inc. today ..." is one sentence

# Hover where mail apps allow it (Gmail on the web, Apple Mail): links dim, rows shade
STYLE = "a:hover{opacity:.75}.p-row:hover td{background:#f2f2f2}"


def _sentences(text: str) -> list[str]:
    out = []
    for piece in _SENTENCE.split(text):
        if out and _ABBREVIATION.search(out[-1]):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return out


def _tags(c: dict) -> set[str]:
    return set(classify.tags_for(c.get("title") or "", c.get("summary") or "", source=c.get("source") or ""))


def _picture(name: str) -> str:
    """A drawing's address: on the site (static.py publishes templates/photos), or, for a sample sent from another
    branch on GitHub Actions, that branch's copy on GitHub. Linked, not attached, so the inbox lists no attachments."""
    ref = os.environ.get("GITHUB_REF_NAME", "main")
    if ref == "main":
        return f"{rss.SITE}photos/cartoons/png/{name}.png"
    repo = os.environ.get("GITHUB_REPOSITORY", "shru14/ai-pulse")
    return f"https://raw.githubusercontent.com/{repo}/{ref}/templates/photos/cartoons/png/{name}.png"


def _art(c: dict, n: str) -> str:
    """The picture for a story: the first ART_RULES drawing whose tags (all of a rule's tags count) or headline words
    (where a rule has both, a tag and the words must both be there) it has, else its stream's drawing."""
    t, title = _tags(c), c.get("title") or ""
    for tags, words, name in ART_RULES:
        tagged, said = bool(t & tags), bool(words and re.search(words, title, re.I))
        if (tagged and said) if tags and words else (tagged or said):
            return _picture(f"features/{name}")
    return _picture(f"streams/{rss.FEEDS[n][0]}")


def _by(c: dict) -> str:
    more = digest._outlets(c) - 1
    return c.get("source", "") + (f" +{more} outlet{'s' if more > 1 else ''}" if more else "")


def _label(words: str, bg: str = INK, fg: str = "#ffffff") -> str:
    return (f'<span style="display:inline-block;font-family:{BODY};font-weight:bold;font-size:11px;letter-spacing:.5px;'
            f'background:{bg};color:{fg};padding:3px 7px;line-height:1.3">{escape(words)}</span>')


def _button(words: str, href: str) -> str:
    return (f'<a href="{escape(href)}" style="display:inline-block;background:{INK};color:#ffffff;font-family:{BODY};'
            f'font-weight:bold;font-size:14px;padding:10px 16px;text-decoration:none;box-shadow:4px 4px 0 {BLUE}">'
            f'{escape(words)}</a>')


def _heading(words: str, color: str = INK) -> str:
    return (f'<div style="font-family:{HEAD};font-size:20px;line-height:1.2;color:{color};border-bottom:3px solid {color};'
            f'padding-bottom:5px;margin-bottom:12px">{escape(words)}</div>')


def _table(rows: str, style: str = "") -> str:
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;'
            f'table-layout:fixed;{style}">{rows}</table>')


def _number(stories: list[dict]) -> tuple[str, str, dict] | None:
    """The day's number: the first sum of money in the ranked stories' headlines or summaries, as "$3.5B", with the
    sentence that says what it is (the outlet's own words) and the story; None on a day without one."""
    for c in stories:
        for text in (c.get("title") or "", c.get("summary") or ""):
            m = _MONEY.search(text)
            if not m:
                continue
            figure = f"{m.group(1)}{m.group(2)}{_UNIT[m.group(3).lower()]}"
            said = next((s for s in _sentences(text) if m.group(0) in s), text).strip()
            return figure, digest._short(said, 240), c
    return None


SUBJECT_WORDS = 6  # the owner's limit for a subject
_SMALL = {"a", "an", "the", "to", "of", "in", "on", "at", "for", "with", "and", "or", "by", "from", "as", "its", "it",
          "their", "is", "are", "was", "were", "will", "be", "that", "this", "than", "into", "over", "after", "says"}


def _subject(title: str) -> str:
    """The lead headline's first SUBJECT_WORDS words, as the outlet wrote them, then "…"; never ending on a small word
    ("to", "the", "will"...). The whole headline is in the preview line (_also)."""
    words = title.split()
    if len(words) <= SUBJECT_WORDS:
        return title
    cut = words[:SUBJECT_WORDS]
    # nor on a sign, a number or a lone letter ("raise R $…")
    while len(cut) > 3 and (cut[-1].lower().strip(",:;'’\"“”") in _SMALL or not re.search(r"[A-Za-z]{2}", cut[-1])):
        cut.pop()
    return " ".join(cut).rstrip(",:;—–-") + "…"


def _also(top: list[dict], total: int) -> str:
    """The preview line after the subject: the lead headline, then the companies in the next stories (our tags) and
    how many more."""
    seen = _tags(top[0]) & set(classify.COMPANY_TERMS)
    names = []
    for c in top[1:]:
        name = next((t for t in digest.story_tags(c) if t in classify.COMPANY_TERMS and t not in seen and t not in names), None)
        if name:
            names.append(name)
        if len(names) == 2:
            break
    more = total - 1 - len(names)
    if not names:
        return f"{top[0]['title']} · and {more} more" if more > 0 else top[0]["title"]
    return f"{top[0]['title']} · plus " + (" and ".join(names) if more <= 0 else ", ".join(names) + f" and {more} more")


def _tile(c: dict, n: str, picture: str, yours: bool) -> str:
    """A top-news story as a tile: its stream and picture on the stream's colour, then its headline and outlets."""
    kicker = rss.FEEDS[n][1] + (" · Your choice" if yours else "")
    return _table(f'<tr><td style="background:{FILL[n]};border-bottom:2px solid {INK};padding:0">{_label(kicker)}'
                  f'<a href="{escape(c["url"])}"><img src="{picture}" width="190" alt="" style="display:block;width:100%;'
                  f'height:auto;border:0"></a></td></tr><tr><td style="padding:8px 8px 10px">'
                  f'<a href="{escape(c["url"])}" style="color:{INK};text-decoration:none;font-weight:bold;font-size:13px;'
                  f'line-height:1.35">{escape(c["title"])}</a><div style="font-size:11px;color:{GREY};margin-top:5px">'
                  f'{escape(_by(c))}</div></td></tr>', f"border:2px solid {INK}")


def _word_and_meme(cards: list[dict], day: date, streams: list[str], prefs: dict, tiers: list[list[dict]]) -> tuple[list[str], str]:
    """The word of the day (digest._word_entry) in the site's blue tile, and the meme of the day in a vermilion one."""
    e, story = digest._word_entry(cards, day, streams, prefs, tiers)
    glossary_page = f"{rss.SITE}glossary/"
    text = ["WORD OF THE DAY: " + e["term"], e["def"], *([f"Where it came up: {story['title']} {story['url']}"] if story else []), ""]
    html = (_table(f'<tr><td style="padding:16px 18px;background:{BLUE};border:2px solid {INK};color:#ffffff">'
                   f'<div style="font-weight:bold;font-size:12px;letter-spacing:.5px">WORD OF THE DAY</div>'
                   f'<div style="font-family:{HEAD};font-size:24px;line-height:1.2;margin:6px 0 8px"><span style="background:{YELLOW};'
                   f'color:{INK};padding:0 5px">{escape(e["term"])}</span></div>'
                   f'<div style="font-size:15px;line-height:1.5">{escape(e["def"])}</div>'
                   + (f'<div style="font-size:13px;line-height:1.45;margin-top:8px">Where it came up: <a href="{escape(story["url"])}" '
                      f'style="color:#ffffff">{escape(story["title"])}</a></div>' if story else "")
                   + f'<div style="font-size:13px;margin-top:8px"><a href="{escape(glossary_page)}" style="color:#ffffff;'
                     f'font-weight:bold">More words in the glossary →</a></div></td></tr>', "margin:0 0 14px"))
    from . import memes
    meme = memes.of_the_day(cards, day)
    picture = meme and memes.render(meme)
    if picture:
        # the site's copy (static.py publishes the past week's), so nothing is attached; inside the email if not there yet
        src = f"{rss.SITE}daily/{day.isoformat()}-meme.{'png' if digest._kind(picture) == 'png' else 'jpg'}"
        try:
            with urllib.request.urlopen(urllib.request.Request(src, method="HEAD"), timeout=10) as r:
                online = r.status == 200
        except OSError:
            online = False
        if not online:
            digest.INLINE[digest.MEME_CID] = picture
            src = "cid:" + digest.MEME_CID
        text += memes.text(meme) + [""]
        html += _table(f'<tr><td align="center" style="padding:14px;background:{VERMILION};border:2px solid {INK}">'
                       f'<div style="font-weight:bold;font-size:12px;letter-spacing:.5px;color:#ffffff;margin-bottom:10px">'
                       f'MEME OF THE DAY</div>{memes.html(meme, src, small=True)}</td></tr>', "margin:0 0 26px")
    return text, html


def build(cards: list[dict], by_stream: dict[str, list[dict]], left: list[dict], streams: list[str], day: date,
          prefs: dict | None, dossier: dict | None, unsubscribe: str, change: str, stop: str) -> tuple[str, str, str]:
    """(subject, plain text, HTML) of the poster email (see digest.build for the arguments)."""
    todays = [c for n in streams for c in by_stream[n]]
    stream_of = {id(c): n for n in streams for c in by_stream[n]}
    ranked = sorted([c for c in todays if digest._fits_top(c)], key=digest._rank, reverse=True)
    main = [c for c in ranked if c.get("kind") not in digest.SIDE_KINDS]
    prefs = prefs or {}
    _, theirs = digest._mine(prefs)
    tuned = bool(prefs.get("more") or prefs.get("words"))
    picks = {id(c) for c in todays if tuned and theirs(c)}
    mine = [c for c in main if id(c) in picks][:digest.PICKS]
    top = (mine + [c for c in main if c not in mine])[:1 + TOP_NEWS] or ranked[:1 + TOP_NEWS]
    shown = {id(c) for c in top}
    text, html = [], []
    stories = len(todays)  # stories, not outlets: the stream rows add up to it
    pad = 'style="padding:20px 20px 0"'

    # The masthead: the mark, the name, the day
    html.append(f'<tr><td style="padding:12px 20px;border-bottom:3px solid {INK}">' + _table(
        f'<tr><td valign="middle"><img src="{_picture("mark")}" width="30" height="30" alt="" style="display:inline-block;'
        f'vertical-align:middle;border:0"><span style="font-family:{HEAD};font-size:20px;vertical-align:middle;'
        f'margin-left:8px">AI Pulse</span></td><td align="right" valign="middle" style="font-weight:bold;font-size:14px">'
        f'{day:%a} {day.day} {day:%b}</td></tr>') + '</td></tr>')

    # Sunday: the week's story, word and meme (as in the short email), and the reader's dossier
    if digest.weekly(day):
        week_text, week_html = digest._the_week(cards, day, prefs)
        dossier_text, dossier_html = digest._dossier(dossier)
        text += [*week_text, *dossier_text, ""]
        html.append(f'<tr><td {pad}>{week_html}{dossier_html}</td></tr>')

    if top:
        # Hot today: the day's most-reported story, with its picture beside it
        hot, n = top[0], stream_of[id(top[0])]
        summary = digest._short(hot.get("summary") or "", 200, hot.get("source", ""))
        text += ["HOT TODAY", hot["title"], *([summary] if summary else []), _by(hot), hot["url"], ""]
        html.append(f'<tr><td style="padding:0;border-bottom:3px solid {INK}">' + _table(
            f'<tr><td valign="top" style="padding:18px 16px 20px 20px">'
            f'{_label("HOT TODAY" + (" · YOUR CHOICE" if id(hot) in picks else ""), YELLOW, INK)} {_label(rss.FEEDS[n][1].upper())}'
            f'<div style="margin:10px 0 8px"><a href="{escape(hot["url"])}" style="font-family:{HEAD};font-size:24px;'
            f'line-height:1.15;color:{INK};text-decoration:none">{escape(hot["title"])}</a></div>'
            + (f'<div style="font-size:15px;line-height:1.5;margin-bottom:8px">{escape(summary)}</div>' if summary else "")
            + f'<div style="font-size:12px;color:{GREY};margin-bottom:14px">{escape(_by(hot))}</div>'
              f'{_button("Read the story →", hot["url"])}</td>'
              f'<td width="34%" valign="bottom" style="width:34%;background:{FILL[n]};border-left:3px solid {INK};padding:0">'
              f'<img src="{_art(hot, n)}" width="220" alt="" style="display:block;width:100%;height:auto;border:0"></td></tr>')
            + '</td></tr>')

    body = []  # the sections in the padded column
    if len(top) > 1:
        text += ["TOP NEWS", *(f"• [{rss.FEEDS[stream_of[id(c)]][1]}] {c['title']} ({_by(c)}) {c['url']}" for c in top[1:]), ""]
        tiles = [_tile(c, stream_of[id(c)], _art(c, stream_of[id(c)]), id(c) in picks) for c in top[1:]]
        tiles += [""] * (-len(tiles) % 3)
        # three to a row at every width, as on a computer (a phone shows the same, smaller)
        grid = "".join("<tr>" + "".join(f'<td width="33%" valign="top" style="padding:0 {5 if k % 3 < 2 else 0}px 10px '
                                        f'{5 if k % 3 else 0}px">{tiles[k]}</td>' for k in range(r, r + 3)) + "</tr>"
                       for r in range(0, len(tiles), 3))
        body.append(_heading("Top news") + _table(grid, "margin:0 0 14px"))
    made_for = digest._left_note(prefs, left)
    if made_for:
        text += [made_for, ""]
        body.append(f'<div style="font-size:12px;color:{GREY};margin:0 0 18px">{escape(made_for)}</div>')

    # The word and the meme of the day, high up (Sunday's email has the week's, above)
    if not digest.weekly(day):
        word_text, word_html = _word_and_meme(cards, day, streams, prefs, [digest._biggest(by_stream, streams), top, todays])
        text += word_text
        body.append(word_html)

    news = digest._new_stream(day, streams)
    if news:
        text += [news, f"Add Infra: {change}", ""]
        body.append(_table(f'<tr><td style="background:{FILL["infra"]};border:2px solid {INK};padding:12px 14px;font-size:14px;'
                           f'line-height:1.45">{escape(news)}<div style="margin-top:10px">{_button("Add Infra →", change)}</div>'
                           f'</td></tr>', "margin:0 0 26px"))

    # The number of the day, with the outlet's sentence that says what it counts (the hot story's only if no other has one)
    number = _number(top[1:] + [c for c in main if id(c) not in shown] + top[:1])
    if number:
        figure, said, c = number
        text += [f"NUMBER OF THE DAY: {figure}", said, f"{c['source']}: {c['url']}", ""]
        body.append(_table(f'<tr><td width="34%" valign="middle" style="width:34%;padding:14px 16px;background:{YELLOW};'
                           f'border:2px solid {INK};border-right:0"><div style="font-weight:bold;font-size:12px;letter-spacing:.5px">'
                           f'NUMBER OF THE DAY</div><div style="font-family:{HEAD};font-size:34px;line-height:1.1">{escape(figure)}</div></td>'
                           f'<td valign="middle" style="padding:14px 16px;background:{YELLOW};border:2px solid {INK};border-left:0;'
                           f'font-size:14px;line-height:1.45">{escape(said)}<div style="font-size:12px;margin-top:6px">'
                           f'{escape(c["source"])} · <a href="{escape(c["url"])}" style="color:{INK};font-weight:bold">Read it →</a>'
                           f'</div></td></tr>', "margin:0 0 26px"))

    # New on AI Pulse: the page this day's email introduces, with its own drawing
    feature = digest._feature(day)
    if feature:
        name, what, path = feature
        fill = FEATURE_FILL.get(pages.FEATURES.get(path, ("news",))[0], YELLOW)
        art = f"features/{path.strip('/')}"
        picture = _picture(art) if (ART / f"{art}.png").exists() else _picture("streams/all")
        text += [f"NEW ON AI PULSE: {name}", what, f"Have a look: {rss.SITE}{path}", ""]
        body.append(_table(f'<tr><td width="30%" valign="middle" style="width:30%;background:{fill};border:2px solid {INK};'
                           f'padding:0"><img src="{picture}" width="170" alt="" style="display:block;width:100%;height:auto;border:0"></td>'
                           f'<td valign="top" style="padding:12px 14px;border:2px solid {INK};border-left:0">{_label("NEW ON AI PULSE")}'
                           f'<div style="font-family:{HEAD};font-size:18px;line-height:1.2;margin:8px 0 6px">{escape(name)}</div>'
                           f'<div style="font-size:14px;line-height:1.45">{escape(what)}</div><div style="margin-top:8px">'
                           f'<a href="{escape(rss.SITE + path)}" style="color:{INK};font-weight:bold;font-size:13px">Have a look →</a>'
                           f'</div></td></tr>', "margin:0 0 26px"))
    html.append(f'<tr><td {pad}>{"".join(body)}</td></tr>')

    # Pick your lane: the rest of the day by who it matters to (a story in one lane only, none from above)
    rest = [c for c in main if id(c) not in shown]
    taken: set[int] = set()
    lanes = []
    for title, icon, fits in LANES:
        theirs_ = [c for c in rest if id(c) not in taken and fits(stream_of[id(c)], _tags(c), c.get("title") or "")][:LANE_STORIES]
        taken |= {id(c) for c in theirs_}
        if theirs_:
            lanes.append((title, icon, theirs_))
    if lanes:
        text.append("PICK YOUR LANE")
        boxes = []
        for title, icon, theirs_ in lanes:
            text += [title.upper(), *(f"  • {c['title']} {c['url']}" for c in theirs_)]
            rows = "".join(f'<tr><td style="padding:8px 10px;border-top:1px solid #cccccc;font-size:13px;line-height:1.35">'
                           f'<a href="{escape(c["url"])}" style="color:{INK};text-decoration:none">{escape(c["title"])}</a></td></tr>'
                           for c in theirs_)
            boxes.append(_table(f'<tr><td style="padding:8px 10px;border-bottom:2px solid {INK}"><img src="{_picture("lanes/" + icon)}" '
                                f'width="18" height="18" alt="" style="vertical-align:middle;border:0"><span style="font-weight:bold;'
                                f'font-size:15px;vertical-align:middle;margin-left:6px">{escape(title)}</span></td></tr>{rows}',
                                f"background:#ffffff;color:{INK}"))
        boxes.append(_table(f'<tr><td style="padding:14px;background:{YELLOW};color:{INK}"><div style="font-weight:bold;font-size:15px">'
                            f'Want your lane on top?</div><div style="font-size:13px;line-height:1.4;margin:6px 0 8px">Tell us who you '
                            f'are, and your lane leads your email.</div><a href="{escape(change)}" style="color:{INK};font-weight:bold;'
                            f'font-size:13px">Choose in 10 seconds →</a></td></tr>'))
        boxes += [""] * (len(boxes) % 2)
        grid = "".join(f'<tr><td width="50%" valign="top" style="padding:0 6px 12px 0">{boxes[k]}</td>'
                       f'<td width="50%" valign="top" style="padding:0 0 12px 6px">{boxes[k + 1]}</td></tr>'
                       for k in range(0, len(boxes), 2))
        text.append("")
        html.append(f'<tr><td style="padding:20px 20px 8px;background:{INK};color:#ffffff">'
                    f'<div style="font-family:{HEAD};font-size:20px;line-height:1.2;color:#ffffff">Pick your lane</div>'
                    f'<div style="font-size:14px;margin:4px 0 14px;color:#ffffff">The rest of the day, sorted by who it matters to.</div>'
                    f'{_table(grid)}</td></tr>')

    # How useful is it: 1 to 5, each opens the site's review form with that number picked (all five alike)
    review = rss.SITE + "review/"
    text += ["HOW USEFUL IS AI PULSE TO YOU? Tap a number, then four more quick questions: " + review, ""]
    numbers = "".join(f'<td style="padding:0 6px 0 0"><a href="{escape(review)}#useful-{k}" style="display:block;width:34px;'
                      f'height:34px;line-height:34px;text-align:center;border:2px solid {INK};font-weight:bold;font-size:16px;'
                      f'color:{INK};text-decoration:none">{k}</a></td>' for k in range(1, 6))
    html.append(f'<tr><td style="padding:20px">' + _table(
        f'<tr><td style="padding:12px 14px;border:2px solid {INK}"><div style="font-weight:bold;font-size:15px">How useful is '
        f'AI Pulse to you?</div><div style="font-size:12px;color:{GREY};margin:3px 0 10px">Tap a number, then four more quick '
        f'questions. 1 not useful · 5 very useful</div><table role="presentation" cellpadding="0" cellspacing="0"><tr>{numbers}'
        f'</tr></table></td></tr>') + '</td></tr>')

    # The Firehose: a row per stream, each opening that stream's part of the day's page on the site (every story)
    web = digest.full_page(day)
    text += ["THE FIREHOSE", f"All {stories} stories of {day:%A}, nothing held back: {web}"]
    rows = []
    for n in streams:
        name, count = rss.FEEDS[n][1], len(by_stream[n])
        text.append(f"  {name}: {count} {'story' if count == 1 else 'stories'}")
        words = f"{count} {'story' if count == 1 else 'stories'}" if count else "nothing new"
        rows.append(f'<tr class="p-row"><td width="14" style="width:14px;padding:11px 0"><div style="width:12px;height:12px;'
                    f'background:{FILL[n] if count else "#cccccc"};border:2px solid {INK}"></div></td>'
                    f'<td style="padding:11px 10px;border-bottom:1px solid #cccccc"><a href="{escape(web)}#{n}" style="color:{INK};'
                    f'text-decoration:none;font-weight:bold;font-size:15px">{escape(name)}</a></td>'
                    f'<td align="right" style="padding:11px 0;border-bottom:1px solid #cccccc;font-size:14px;white-space:nowrap">'
                    f'<a href="{escape(web)}#{n}" style="color:{INK if count else GREY};text-decoration:none">{words} ▸</a></td></tr>')
    html.append(f'<tr><td style="padding:18px 20px 16px;background:{INK};color:#ffffff"><div style="font-family:{HEAD};'
                f'font-size:22px;line-height:1.2;color:#ffffff">The Firehose</div><div style="font-size:14px;line-height:1.45;'
                f'margin-top:4px;color:#ffffff">'
                f'All {stories} stories of {day:%A}. No filter, nothing held back, free.</div></td></tr>'
                f'<tr><td style="padding:6px 20px 22px">{_table("".join(rows))}<div style="margin-top:16px">'
                f'{_button(f"Open all {stories} stories →", web)}</div></td></tr>')

    # The footer: pass it on, the reader's streams, their links
    chose = ", ".join(rss.FEEDS[n][1] for n in streams)
    text += ["", f"Know someone who'd like this? Forward this email; they can sign up free at {rss.SITE}#subscribe",
             f"You chose: {chose}.", f"Change my streams and choices: {change}", f"Unsubscribe: {stop}",
             f"AI Pulse is free and non-commercial: {rss.SITE}"]
    html.append(f'<tr><td style="border-top:3px solid {INK};padding:14px 20px 18px;font-size:12px;line-height:1.7;color:{GREY}">'
                f'Know someone who&#39;d like this? Forward it; they can <a href="{rss.SITE}#subscribe" style="color:{INK};'
                f'font-weight:bold">sign up free</a>.<br>You chose: {escape(chose)}.<br><a href="{escape(change)}" '
                f'style="color:{GREY}">Change my streams and choices</a> · <a href="{escape(stop)}" style="color:{GREY}">'
                f'Unsubscribe</a><br>AI Pulse is free and non-commercial · <a href="{rss.SITE}" style="color:{GREY}">{rss.SITE}</a>'
                f'</td></tr>')

    subject = _subject(top[0]["title"]) if top else f"AI Pulse · {digest.long_day(day)}"
    preheader = _also(top, len(todays)) if top else ""  # shown after the subject
    page = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&amp;display=swap" rel="stylesheet">'
            f'<title>{escape(subject)}</title><style>{STYLE}</style></head><body style="margin:0;padding:0;background:#ffffff">'
            f'<div style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(preheader)}</div>'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff"><tr>'
            '<td align="center" style="padding:10px 6px 20px">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:#ffffff;'
            f'border:3px solid {INK};border-collapse:collapse;font-family:{BODY};font-size:15px;color:{INK}">' + "".join(html)
            + '</table></td></tr></table></body></html>')
    return subject, "\n".join(text), page
