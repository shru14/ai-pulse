"""The poster email (on trial): the daily digest in the site's Swiss-poster look. In order: the hot story (the
day's most-reported), top news, the word and meme of the day, the number of the day, the newest page on the site,
the rest of the day by reader ("Pick your lane"), the review strip, then every story of the day ("The Firehose").
Nothing in it is written by AI: headlines and sentences are the outlets' own, pictures are our own drawings
(templates/photos/cartoons, as PNG: mail apps don't show SVG), picked by each story's tags.

    python -m aipulse digest --to someone@example.com --layout poster [--day 2026-10-23] [--dry-run page.html]
"""

from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

from . import classify, digest, pages, rss

ART = Path(__file__).resolve().parent.parent / "templates" / "photos" / "cartoons" / "png"
HEAD = "'Archivo Black','Arial Black',Arial,sans-serif"  # Gmail has no web fonts: Arial Black there
BODY = "Archivo,Arial,Helvetica,sans-serif"
INK, YELLOW, BLUE, VERMILION = "#000000", "#F0E442", "#0072B2", "#B85000"
# The streams' Okabe-Ito fills (the site's --f-*), black text on them
FILL = {"releases": "#009E73", "news": "#56B4E9", "research": "#C85BC3", "regulation": "#F85C48", "policy": "#E69F00",
        "infra": "#8BEC8B"}
FEATURE_FILL = {"tool": FILL["releases"], "news": FILL["news"], "research": FILL["research"], "reg": FILL["regulation"],
                "policy": FILL["policy"], "infra": FILL["infra"]}
TOP_NEWS = 6  # after the hot story, two rows of three
LANE_STORIES = 3

# A story's picture: a feature drawing whose tags it has, else its stream's own drawing (see _art)
ART_RULES = [
    ({"IPO", "Funding", "M&A"}, "who-owns-a-piece-of-whom"),
    ({"IPO", "Funding", "M&A"}, "ai-buyouts"),
    ({"Jobs & Labor"}, "jobs-blamed-on-ai"),
    ({"Elections", "Deepfakes", "Misuse"}, "harm-to-rule"),
    ({"Safety", "Alignment", "Interpretability", "Existential Risk"}, "ai-safety-hub"),
    ({"Export Controls", "Chips"}, "chip-export-rules"),
    ({"Power & grid", "Energy", "Water", "Emissions & climate"}, "who-powers-ai"),
    ({"Land & local pushback", "Rules & permits"}, "pushback-and-permits"),
    ({"Builds & deals", "Hardware & compute", "Compute & Data Centers"}, "data-centre-builds"),
    ({"Benchmarks"}, "new-tests-for-ai"),
    ({"Open Models"}, "release-cards"),
]
LAB_TAGS = {"OpenAI", "Anthropic", "Google", "Meta", "DeepSeek", "xAI", "Mistral", "Alibaba"}

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


def _sentences(text: str) -> list[str]:
    out = []
    for piece in _SENTENCE.split(text):
        if out and _ABBREVIATION.search(out[-1]):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return out

STYLE = ("@media (max-width:560px){.p-cell,.p-stack{display:block!important;width:100%!important;box-sizing:border-box}"
         ".p-cell{padding:0 0 14px 0!important}"
         ".p-side{display:block!important;width:100%!important;border-left:0!important;border-right:0!important;"
         "border-top:4px solid #000!important}.p-hh{font-size:30px!important}.p-num{font-size:56px!important}"
         ".p-pad{padding:18px 14px!important}.p-timg{width:55%!important;margin:0 auto!important}}")


def _tags(c: dict) -> set[str]:
    return set(classify.tags_for(c.get("title") or "", c.get("summary") or "", source=c.get("source") or ""))


def _picture(name: str) -> str:
    """A drawing's content ID, its PNG put inside the email (digest.INLINE)."""
    cid = f"art-{name.replace('/', '-')}@aipulse"
    digest.INLINE[cid] = (ART / f"{name}.png").read_bytes()
    return "cid:" + cid


def _art(c: dict, n: str, used: set[str]) -> str:
    """The picture for a story: the first drawing not yet used in this email among the feature drawings its tags
    match, a lab's (timelines, then promises) for lab news, release cards for a release, then its stream's; when all
    are used, the best fit again."""
    t = _tags(c)
    fits = [f"features/{name}" for tags, name in ART_RULES if t & tags]
    if n == "news" and t & LAB_TAGS:
        fits += ["features/lab-timelines", "features/promises"]
    if n == "releases":
        fits.append("features/release-cards")
    fits.append(f"streams/{rss.FEEDS[n][0]}")
    pick = next((f for f in fits if f not in used), fits[0])
    used.add(pick)
    return _picture(pick)


def _by(c: dict) -> str:
    more = digest._outlets(c) - 1
    return c.get("source", "") + (f" +{more} outlet{'s' if more > 1 else ''}" if more else "")


def _label(words: str, bg: str = INK, fg: str = "#ffffff", size: int = 11) -> str:
    return (f'<span style="display:inline-block;font-family:{HEAD};font-size:{size}px;background:{bg};color:{fg};'
            f'padding:4px 8px;line-height:1.2">{escape(words)}</span>')


def _button(words: str, href: str) -> str:
    return (f'<a href="{escape(href)}" style="display:inline-block;background:{INK};color:#ffffff;font-family:{BODY};'
            f'font-weight:bold;font-size:14px;padding:12px 18px;text-decoration:none;box-shadow:6px 6px 0 {BLUE}">'
            f'{escape(words)}</a>')


def _heading(words: str, size: int = 28) -> str:
    return (f'<div style="font-family:{HEAD};font-size:{size}px;line-height:1.1;color:{INK};border-bottom:4px solid {INK};'
            f'padding-bottom:6px;margin-bottom:16px">{escape(words)}</div>')


def _grid(cells: list[str], columns: int, gap: int = 14) -> str:
    """Cells in rows of `columns` (one column on a phone, see STYLE)."""
    cells = cells + [""] * (-len(cells) % columns)
    width = f"{100 // columns}%"
    rows = "".join("<tr>" + "".join(f'<td class="p-cell" width="{width}" valign="top" style="padding:0 {gap // 2}px {gap}px">'
                                    f'{cell}</td>' for cell in cells[k:k + columns]) + "</tr>"
                   for k in range(0, len(cells), columns))
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;'
            f'table-layout:fixed">{rows}</table>')


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


def _subject(top: list[dict], total: int) -> str:
    """The lead headline as the outlet wrote it, then the companies in the next stories (our tags) and how many more."""
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
    kicker = rss.FEEDS[n][1] + (" · Your choice" if yours else "")
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:3px solid {INK};'
            f'border-collapse:collapse"><tr><td style="background:{FILL[n]};border-bottom:3px solid {INK};padding:0">'
            f'{_label(kicker)}<img class="p-timg" src="{picture}" width="190" alt="" style="display:block;width:100%;height:auto;border:0">'
            f'</td></tr><tr><td style="padding:10px 10px 12px;font-family:{BODY}">'
            f'<a href="{escape(c["url"])}" style="color:{INK};text-decoration:none;font-weight:bold;font-size:14px;'
            f'line-height:1.3">{escape(c["title"])}</a>'
            f'<div style="font-size:11.5px;color:#444444;margin-top:6px">{escape(_by(c))}</div></td></tr></table>')


def _word_and_meme(cards: list[dict], day: date, streams: list[str], prefs: dict, tiers: list[list[dict]]) -> tuple[list[str], str]:
    """The word of the day (digest._word_entry) in the site's blue tile, and the meme of the day in a vermilion one."""
    e, story = digest._word_entry(cards, day, streams, prefs, tiers)
    glossary_page = f"{rss.SITE}glossary/"
    text = ["WORD OF THE DAY: " + e["term"], e["def"], *([f"Where it came up: {story['title']} {story['url']}"] if story else []), ""]
    html = (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BLUE};'
            f'border:3px solid {INK};margin:0 0 16px"><tr><td style="padding:18px;color:#ffffff;font-family:{BODY}">'
            f'<div style="font-family:{HEAD};font-size:13px">Word of the day</div>'
            f'<div style="font-family:{HEAD};font-size:34px;line-height:1.15;margin:6px 0 8px"><span style="background:{YELLOW};'
            f'color:{INK};padding:0 5px">{escape(e["term"])}</span></div>'
            f'<div style="font-size:14px;line-height:1.5">{escape(e["def"])}</div>'
            + (f'<div style="font-size:12.5px;line-height:1.45;margin-top:8px">Where it came up: <a href="{escape(story["url"])}" '
               f'style="color:#ffffff">{escape(story["title"])}</a></div>' if story else "")
            + f'<div style="font-size:13px;margin-top:8px"><a href="{escape(glossary_page)}" style="color:#ffffff;'
              f'font-weight:bold">More words in the glossary →</a></div></td></tr></table>')
    from . import memes
    meme = memes.of_the_day(cards, day)
    picture = meme and memes.render(meme)
    if picture:
        digest.INLINE[digest.MEME_CID] = picture
        text += memes.text(meme) + [""]
        html += (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{VERMILION};'
                 f'border:3px solid {INK};margin:0 0 30px"><tr><td align="center" style="padding:16px">'
                 f'<div style="font-family:{HEAD};font-size:13px;color:#ffffff;margin-bottom:10px">Meme of the day</div>'
                 f'{memes.html(meme, "cid:" + digest.MEME_CID, small=True)}</td></tr></table>')
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
    used: set[str] = set()
    text, html = [], []
    stories = len(todays)  # stories, not outlets: the stream buttons add up to it

    # The masthead: the mark, the name, the day
    html.append(f'<tr><td style="padding:14px 22px;border-bottom:4px solid {INK}"><table role="presentation" width="100%" '
                f'cellpadding="0" cellspacing="0"><tr><td valign="middle"><img src="{_picture("mark")}" width="34" height="34" '
                f'alt="" style="display:inline-block;vertical-align:middle;border:0"><span style="font-family:{HEAD};'
                f'font-size:24px;color:{INK};vertical-align:middle;margin-left:10px">AI Pulse</span></td>'
                f'<td align="right" valign="middle" style="font-family:{HEAD};font-size:16px;color:{INK}">'
                f'{day:%a} {day.day} {day:%b}</td></tr></table></td></tr>')

    # Sunday: the week's story, word and meme (as in the short email), and the reader's dossier
    if digest.weekly(day):
        week_text, week_html = digest._the_week(cards, day, prefs)
        dossier_text, dossier_html = digest._dossier(dossier)
        text += [*week_text, *dossier_text, ""]
        html.append(f'<tr><td class="p-pad" style="padding:20px 22px;border-bottom:4px solid {INK}">{week_html}{dossier_html}</td></tr>')

    if top:
        # Hot today: the day's most-reported story, big, with its picture
        hot, n = top[0], stream_of[id(top[0])]
        summary = digest._short(hot.get("summary") or "", 200, hot.get("source", ""))
        text += ["HOT TODAY", hot["title"], *([summary] if summary else []), _by(hot), hot["url"], ""]
        html.append(f'<tr><td style="border-bottom:4px solid {INK};padding:0"><table role="presentation" width="100%" '
                    f'cellpadding="0" cellspacing="0"><tr><td class="p-pad p-stack" valign="top" style="padding:22px;font-family:{BODY}">'
                    f'{_label("Hot today" + (" · Your choice" if id(hot) in picks else ""), YELLOW, INK, 13)} {_label(rss.FEEDS[n][1], size=13)}'
                    f'<div style="margin:14px 0 12px"><a class="p-hh" href="{escape(hot["url"])}" style="font-family:{HEAD};'
                    f'font-size:40px;line-height:1.02;color:{INK};text-decoration:none;letter-spacing:-1px">'
                    f'{escape(hot["title"])}</a></div>'
                    + (f'<div style="font-size:15px;line-height:1.5;color:{INK};margin-bottom:10px">{escape(summary)}</div>' if summary else "")
                    + f'<div style="font-size:12px;font-weight:bold;margin-bottom:16px">{escape(_by(hot))}</div>'
                      f'{_button("Read the story →", hot["url"])}</td>'
                      f'<td class="p-side" width="220" valign="bottom" style="width:220px;background:{FILL[n]};'
                      f'border-left:4px solid {INK};padding:0">'
                      f'<img class="p-timg" src="{_art(hot, n, used)}" width="220" alt="" style="display:block;width:100%;height:auto;border:0">'
                      f'</td></tr></table></td></tr>')

    body = []  # the sections inside the padded column
    if len(top) > 1:
        tiles = [_tile(c, stream_of[id(c)], _art(c, stream_of[id(c)], used), id(c) in picks) for c in top[1:]]
        text += ["TOP NEWS", *(f"• [{rss.FEEDS[stream_of[id(c)]][1]}] {c['title']} ({_by(c)}) {c['url']}" for c in top[1:]), ""]
        body.append(_heading("Top news") + _grid(tiles, 3))
    made_for = digest._left_note(prefs, left)
    if made_for:
        text += [made_for, ""]
        body.append(f'<div style="font-size:12px;color:#444444;margin:0 0 20px">{escape(made_for)}</div>')

    # The word and the meme of the day, high up (Sunday's email has the week's, above)
    if not digest.weekly(day):
        word_text, word_html = _word_and_meme(cards, day, streams, prefs, [digest._biggest(by_stream, streams), top, todays])
        text += word_text
        body.append(f'<div style="height:10px"></div>{word_html}')

    news = digest._new_stream(day, streams)
    if news:
        text += [news, f"Add Infra: {change}", ""]
        body.append(f'<div style="background:{FILL["infra"]};border:3px solid {INK};padding:12px 14px;margin:0 0 30px;'
                    f'font-size:14px;line-height:1.45">{escape(news)}<br><br>{_button("Add Infra →", change)}</div>')

    # The number of the day, with the outlet's sentence that says what it counts (the hot story's only if no other has one)
    number = _number(top[1:] + [c for c in main if id(c) not in shown] + top[:1])
    if number:
        figure, said, c = number
        text += [f"NUMBER OF THE DAY: {figure}", said, f"{c['source']}: {c['url']}", ""]
        body.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{YELLOW};'
                    f'border:3px solid {INK};box-shadow:8px 8px 0 {INK};margin:0 0 34px"><tr>'
                    f'<td class="p-cell" valign="middle" style="padding:18px 20px;white-space:nowrap">'
                    f'<div style="font-family:{HEAD};font-size:13px">Number of the day</div>'
                    f'<div class="p-num" style="font-family:{HEAD};font-size:72px;line-height:.95;letter-spacing:-3px">{escape(figure)}</div></td>'
                    f'<td class="p-cell" valign="middle" style="padding:18px 20px 18px 0;font-size:14px;line-height:1.45">'
                    f'{escape(said)}<div style="font-size:12px;font-weight:bold;margin-top:6px">{escape(c["source"])} · '
                    f'<a href="{escape(c["url"])}" style="color:{INK}">Read it →</a></div></td></tr></table>')

    # New on AI Pulse: the page this day's email introduces, with its own drawing
    feature = digest._feature(day)
    if feature:
        name, what, path = feature
        fill = FEATURE_FILL.get(pages.FEATURES.get(path, ("news",))[0], YELLOW)
        art = f"features/{path.strip('/')}"
        picture = _picture(art) if (ART / f"{art}.png").exists() else _picture("streams/all")
        text += [f"NEW ON AI PULSE: {name}", what, f"Have a look: {rss.SITE}{path}", ""]
        body.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:3px solid {INK};'
                    f'margin:0 0 30px"><tr><td class="p-side" width="170" valign="bottom" style="width:170px;background:{fill};'
                    f'border-right:3px solid {INK};padding:0"><img src="{picture}" width="170" alt="" style="display:block;'
                    f'width:100%;height:auto;border:0"></td><td class="p-stack" valign="top" style="padding:16px;font-family:{BODY}">'
                    f'{_label("New on AI Pulse")}<div style="font-family:{HEAD};font-size:24px;line-height:1.05;margin:10px 0 8px">'
                    f'{escape(name)}</div><div style="font-size:14px;line-height:1.45">{escape(what)}</div>'
                    f'<div style="margin-top:10px"><a href="{escape(rss.SITE + path)}" style="color:{INK};font-weight:bold;'
                    f'font-size:13px">Have a look →</a></div></td></tr></table>')
    html.append(f'<tr><td class="p-pad" style="padding:24px 22px 0;font-family:{BODY};color:{INK}">{"".join(body)}</td></tr>')

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
            rows = "".join(f'<tr><td style="padding:9px 12px;{"border-top:1px solid #000000;" if k else ""}font-size:13px;'
                           f'font-weight:bold;line-height:1.35"><a href="{escape(c["url"])}" style="color:{INK};'
                           f'text-decoration:none">{escape(c["title"])}</a></td></tr>' for k, c in enumerate(theirs_))
            boxes.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;'
                         f'border-collapse:collapse"><tr><td style="padding:10px 12px;border-bottom:3px solid {INK}">'
                         f'<img src="{_picture("lanes/" + icon)}" width="20" height="20" alt="" style="vertical-align:middle;border:0">'
                         f'<span style="font-family:{HEAD};font-size:17px;color:{INK};vertical-align:middle;margin-left:8px">'
                         f'{escape(title)}</span></td></tr>{rows}</table>')
        boxes.append(f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{YELLOW}">'
                     f'<tr><td style="padding:16px;color:{INK}"><div style="font-family:{HEAD};font-size:19px;line-height:1.1">'
                     f'Want your lane on top?</div><div style="font-size:13px;line-height:1.4;margin:8px 0">Tell us who you are, '
                     f'and your lane leads your email.</div><a href="{escape(change)}" style="color:{INK};font-weight:bold;'
                     f'font-size:13px">Choose in 10 seconds →</a></td></tr></table>')
        text.append("")
        html.append(f'<tr><td class="p-pad" style="background:{INK};padding:24px 22px 12px;font-family:{BODY};color:#ffffff">'
                    f'<div style="font-family:{HEAD};font-size:28px;line-height:1.1">Pick your lane</div>'
                    f'<div style="font-size:14px;margin:4px 0 16px">The rest of the day, sorted by who it matters to.</div>'
                    f'{_grid(boxes, 2)}</td></tr>')

    # How useful is it: 1 to 5, each opens the site's review form with that number picked (all five alike)
    review = rss.SITE + "review/"
    text += ["HOW USEFUL IS AI PULSE TO YOU? Tap a number, then four more quick questions: " + review, ""]
    numbers = "".join(f'<td style="padding:0 6px 0 0"><a href="{escape(review)}#useful-{k}" style="display:block;width:38px;'
                      f'height:38px;line-height:38px;text-align:center;border:3px solid {INK};font-family:{HEAD};font-size:18px;'
                      f'color:{INK};text-decoration:none">{k}</a></td>' for k in range(1, 6))
    html.append(f'<tr><td class="p-pad" style="padding:26px 22px;font-family:{BODY};color:{INK}"><table role="presentation" '
                f'width="100%" cellpadding="0" cellspacing="0" style="border:3px solid {INK}"><tr><td style="padding:14px 16px">'
                f'<div style="font-family:{HEAD};font-size:18px">How useful is AI Pulse to you?</div><div style="font-size:12px;'
                f'margin:4px 0 10px">Tap a number, then four more quick questions. 1 not useful · 5 very useful</div>'
                f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>{numbers}</tr></table></td></tr></table></td></tr>')

    # The Firehose: every story of the day, one line each, by stream
    chips, rows = [], []
    text += ["THE FIREHOSE", f"All {stories} stories, nothing held back."]
    for n in streams:
        name = rss.FEEDS[n][1]
        listed = sorted(by_stream[n], key=lambda c: (not c.get("late"), *digest._rank(c)), reverse=True)
        if not listed:
            chips.append(f'<span style="display:inline-block;font-size:12px;color:#bbbbbb;border:2px dashed #777777;'
                         f'padding:5px 9px;margin:0 6px 6px 0">{escape(name)} 0</span>')
            continue
        chips.append(f'<a href="#p-{n}" style="display:inline-block;font-weight:bold;font-size:12px;background:{FILL[n]};'
                     f'color:{INK};border:2px solid #ffffff;padding:5px 9px;margin:0 6px 6px 0;text-decoration:none">'
                     f'{escape(name)} {len(listed)}</a>')
        text += ["", f"{name.upper()} ({len(listed)})", *(f"  • {c['title']} ({_by(c)}) {c['url']}" for c in listed)]
        rows.append(f'<tr><td id="p-{n}" style="padding:16px 0 4px;border-bottom:4px solid {FILL[n]};font-family:{HEAD};'
                    f'font-size:15px">{escape(name)} · {len(listed)}</td></tr>')
        rows += [f'<tr><td style="padding:6px 0;border-bottom:1px solid #dddddd;font-size:13px;line-height:1.35">'
                 f'<a href="{escape(c["url"])}" style="color:{INK};text-decoration:none">{escape(c["title"])}</a> '
                 f'<span style="color:#555555;font-size:11.5px">· {escape(_by(c))}</span></td></tr>' for c in listed]
    html.append(f'<tr><td class="p-pad" style="background:{INK};padding:24px 22px 18px;font-family:{BODY};color:#ffffff">'
                f'<div style="font-family:{HEAD};font-size:44px;line-height:1;letter-spacing:-1px">The Firehose</div>'
                f'<div style="font-size:15px;line-height:1.45;margin:10px 0 12px">All <b>{stories}</b> stories of {day:%A}. '
                f'No filter, nothing held back, free. Jump to a stream:</div>{"".join(chips)}</td></tr>'
                f'<tr><td class="p-pad" style="padding:6px 22px 26px;font-family:{BODY};color:{INK}"><table role="presentation" '
                f'width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">{"".join(rows)}</table>'
                f'<div style="margin-top:18px">{_button("This firehose on the web →", digest.full_page(day))}</div></td></tr>')

    # The footer: pass it on, the reader's streams, their links
    chose = ", ".join(rss.FEEDS[n][1] for n in streams)
    text += ["", f"Know someone who'd like this? Forward this email; they can sign up free at {rss.SITE}#subscribe",
             f"You chose: {chose}.", f"Change my streams and choices: {change}", f"Unsubscribe: {stop}",
             f"AI Pulse is free and non-commercial: {rss.SITE}"]
    html.append(f'<tr><td style="border-top:4px solid {INK};padding:16px 22px 20px;font-family:{BODY};font-size:12px;'
                f'line-height:1.7;color:{INK}">Know someone who&#39;d like this? Forward it; they can '
                f'<a href="{rss.SITE}#subscribe" style="color:{INK};font-weight:bold">sign up free</a>.<br>'
                f'You chose: {escape(chose)}.<br><a href="{escape(change)}" style="color:{INK}">Change my streams and choices</a>'
                f' · <a href="{escape(stop)}" style="color:{INK}">Unsubscribe</a><br>AI Pulse is free and non-commercial · '
                f'<a href="{rss.SITE}" style="color:{INK}">{rss.SITE}</a></td></tr>')

    subject = _subject(top, len(todays)) if top else f"AI Pulse · {digest.long_day(day)}"
    preheader = "Also: " + " · ".join(c["title"] for c in top[1:3]) if len(top) > 1 else ""  # shown after the subject
    page = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&amp;family=Archivo:wght@400;700&amp;display=swap" rel="stylesheet">'
            f'<title>{escape(subject)}</title><style>{STYLE}</style></head><body style="margin:0;padding:0;background:#ffffff">'
            f'<div style="display:none;max-height:0;overflow:hidden;opacity:0">{escape(preheader)}</div>'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff"><tr>'
            '<td align="center" style="padding:12px 8px 24px">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;background:#ffffff;'
            f'border:3px solid {INK};border-collapse:collapse;color:{INK}">' + "".join(html)
            + '</table></td></tr></table></body></html>')
    return subject, "\n".join(text), page
