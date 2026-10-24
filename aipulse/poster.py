"""The poster email (the daily email since 25 Oct 2026): the daily digest in the site's Swiss-poster look. In order: the hot story (the
day's most-reported), top news, the word and meme of the day, the number of the day, the newest page on the site,
the rest of the day by reader ("Pick your lane"), the review strip, then The Firehose: a row per stream that opens
every story of the day on the site. One layout at every width (no phone-only rules), so phones show what a computer
does. Nothing in it is written by AI: headlines and sentences are the outlets' own (the subject is the lead's own
words, shortened by rule or, when no rule cuts it cleanly, by Gemini picking which to keep: see _subject), pictures are our own drawings
(templates/photos/cartoons, as PNG: mail apps don't show SVG), picked by each story's tags and linked from the site
(see _picture); only the meme travels inside the email.

    python -m aipulse digest --to someone@example.com --layout poster [--day 2026-10-23] [--dry-run page.html]
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

from . import classify, digest, pages, rss

ART = Path(__file__).resolve().parent.parent / "templates" / "photos" / "cartoons" / "png"
HEAD = "'Archivo Black','Arial Black',Arial,sans-serif"  # headings; Gmail has no web fonts: Arial Black there, and phones lack Arial Black, so every heading also says font-weight:900
BODY = "Arial,Helvetica,sans-serif"
INK, GREY, YELLOW, BLUE, VERMILION = "#000000", "#4a4a4a", "#F0E442", "#0072B2", "#B85000"
# The streams' Okabe-Ito fills (the site's --f-*), black text on them
FILL = {"releases": "#009E73", "news": "#56B4E9", "research": "#C85BC3", "regulation": "#F85C48", "policy": "#E69F00",
        "infra": "#8BEC8B"}
FEATURE_FILL = {"tool": FILL["releases"], "news": FILL["news"], "research": FILL["research"], "reg": FILL["regulation"],
                "policy": FILL["policy"], "infra": FILL["infra"]}
TOP_NEWS = 6  # after the hot story
PER_STREAM = 2  # top news tiles from one stream, unless a story there has more outlets than the rest (see _spread)

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

# "Pick your lane": who a story matters to, from its stream, tags and headline (a story goes in the first lane that
# takes it, in this order). Investors: markets, IPOs and $1B+ sums; Founders: startups and their rounds (a raise with
# an amount), not every Funding or Agents tag, which caught launches and hacks (checked on 17-23 Oct 2026)
_MARKET = re.compile(r"\b(stocks?|shares|share price|markets?|earnings|investors|valuations?|rall(?:y|ies)|selloff|sell-off|"
                     r"short sellers?|futures|revenue|profits?|guidance|IPO|listing|bonds?|yield)\b", re.I)
_BILLIONS = re.compile(r"[$€£]\s?\d[\d.,]*\s?(?:trillion|billion|bn|tn|B)\b|\b\d[\d.,]*\s?(?:trillion|billion)\b", re.I)
_STARTUP = re.compile(r"\b(start-?ups?|founders|seed round|pre-seed|Series [A-H]|unicorn|spin-?outs?|acquires|acquired|acquisition|buys)\b"
                      r"|\b(raises?|raised|raising|secures?|lands|closes)\b[^.]{0,30}?(?:[$€£]|\b(?:US|R|HK|S)\$|\b\d[\d.,]*\s?"
                      r"(?:million|billion|crore|lakh|yuan|won)\b|\bfunding\b|\binvestment\b|\bround\b)", re.I)
_POLICY_TAGS = {"Law", "Regulation", "Governance", "Export Controls", "Elections", "Deepfakes", "Copyright", "Antitrust", "Privacy",
                "Misuse", "AI Act"}
LANES = [
    ("Researchers", "research", lambda n, t, title: n == "research" or (n == "news" and bool(t & {"Study Report", "Benchmarks"}))),
    ("Policy & law", "policy", lambda n, t, title: n in ("policy", "regulation") or (n != "releases" and bool(t & _POLICY_TAGS))),
    ("Investors", "investors", lambda n, t, title: "IPO" in t or bool(_MARKET.search(title) or _BILLIONS.search(title))),
    ("Founders", "founders", lambda n, t, title: bool(_STARTUP.search(title))),
    ("Builders", "builders", lambda n, t, title: n == "releases" or bool(t & {"Coding Tools", "Open Models", "Agents", "Multimodal"})),
]

# The number of the day: a sum of money in a story's headline or summary, shown with the outlet's own sentence
_MONEY = re.compile(r"(?:US|A|C|S|HK)?([$€£])\s?(\d{1,4}(?:\.\d{1,2})?)\s?(trillion|billion|million|bn|mn|tn)\b", re.I)
_UNIT = {"trillion": "T", "tn": "T", "billion": "B", "bn": "B", "million": "M", "mn": "M"}
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“])")
_ABBREVIATION = re.compile(r"\b(?:Inc|Co|Corp|Ltd|Mr|Ms|Dr|St|No|vs|[A-Z])\.$")  # "Pathos AI Inc. today ..." is one sentence

# Hover where mail apps allow it (Gmail on the web, Apple Mail): links dim, rows shade
STYLE = (":root{color-scheme:light only;supported-color-schemes:light only}"  # keep our colours in dark mode
         "a:hover{opacity:.75}.p-row:hover td{background:#f2f2f2}"
         # a phone: the same layout as on a computer, only smaller (type, gaps, margins)
         "@media (max-width:480px){.p-tile{padding:0 3px 8px!important}.p-tt{font-size:11.5px!important}"
         ".p-ts{font-size:10px!important}.p-mast{font-size:14px!important}.p-hh{font-size:20px!important}"
         ".p-hh2{font-size:15px!important}.p-hot{padding:16px 14px!important}.p-pad{padding-left:12px!important;padding-right:12px!important}"
         ".p-numc{padding:12px 8px!important}.p-num{font-size:20px!important}}")


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
    return (f'<div style="font-family:{HEAD};font-weight:900;font-size:20px;line-height:1.2;color:{color};border-bottom:3px solid {color};'
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


SUBJECT_WORDS = 7  # the owner's limit for a subject after "Daily Digest: " (6 or 7 words, never "…")
# Labels and words a subject can lose without changing what the headline says
_LABEL = re.compile(r"^(?:exclusive|opinion|analysis|breaking|update|updated|explainer|interview|report|watch|live|podcast)\s*:\s*", re.I)
_FILLER = {"a", "an", "the", "reportedly", "officially", "now", "just", "finally", "also", "today", "very", "fully",
           "massively", "potentially", "quietly", "publicly", "formally", "newly", "highly", "largely", "widely",
           "rapidly", "recently", "significantly", "dramatically", "sharply", "once", "again", "still"}
# A leading clause that can go ("Amid hardware legal battle, OpenAI releases...")
_LEAD = {"amid", "as", "after", "while", "despite", "with", "following", "ahead", "before", "in", "when", "facing"}
# A tail starting with one of these can go: the rest still says what happened ("Apple sues OpenAI | over...")
_TAIL = {"with", "for", "in", "on", "at", "amid", "after", "as", "while", "despite", "from", "ahead", "before", "using",
         "via", "following", "over", "across", "against", "during", "until", "since", "because", "without", "through",
         "–", "—", "-", "|", "but", "and", "which", "that", "who", "into", "under", "between", "than"}
# A subject never ends on one of these: they leave the line hanging ("…plans to", "…models let you")
_SMALL = {"a", "an", "the", "to", "of", "in", "on", "at", "for", "with", "and", "or", "but", "by", "from", "as", "its",
          "it", "their", "his", "her", "our", "your", "you", "is", "are", "was", "were", "will", "be", "been", "has",
          "have", "had", "that", "this", "than", "into", "over", "after", "says", "said", "can", "could", "would",
          "should", "may", "might", "must", "not", "about", "amid", "while", "despite", "via", "how", "why", "what",
          "who", "which", "when", "new", "more", "most", "if", "like", "do", "does", "set", "plans", "wants", "seeks",
          "aims", "expected", "let", "lets", "make", "makes", "gives", "give", "takes", "take", "built", "led", "made",
          "called", "generated", "tried", "demanding", "designed", "asks", "urges", "tells", "helps", "allows",
          "brings", "puts", "adds", "turns", "sees", "vs", "vs.", "&", "up", "out", "off", "being", "getting", "going",
          "trying"}
_SHORTENED: dict[str, str] = {}  # headline -> subject, so each headline is shortened (and Gemini asked) once per run
GEMINI_ASKS = [3]  # at most this many Gemini asks per run, so subjects never use up the memes' free allowance


def _bare(w: str) -> str:
    return w.lower().replace("’", "'").strip(",:;.!?'\"“”‘()[]")


def _ends_well(cut: list[str]) -> bool:
    """Does a shortened headline end cleanly: not on a small word, a sign or a lone letter, no quote or bracket open?"""
    last, t = cut[-1], " ".join(cut)
    return (_bare(last) not in _SMALL and bool(re.search(r"[A-Za-z]{2}|\d", last)) and last[-1] not in ",:;"
            and t.count("(") == t.count(")") and t.count("“") == t.count("”") and t.count('"') % 2 == 0
            and t.count("‘") <= t.count("’") and not re.search(r"\$\s*$|\bR \$", t))


def _cut(title: str) -> str | None:
    """The headline in at most SUBJECT_WORDS of its own words, by rule: without labels and filler words, its first
    clause or up to a tail it can lose; None when no cut ends cleanly (any cut would change what it says)."""
    t = _LABEL.sub("", " ".join(title.split()))
    t = re.sub(r",? (?:a )?reports? (?:says|said)$|,? (?:sources|people) say$", "", t, flags=re.I)
    t = re.sub(r"\b([A-Z]{1,3}) \$ ?(?=\d)|\$ (?=\d)", lambda m: (m.group(1) or "") + "$", t)  # "R $ 163.5" -> "R$163.5"
    # "AI drug development startup Pathos AI closes..." -> "Pathos AI closes..."
    t = re.sub(r"^(?:[a-z][\w-]* |AI ){0,4}(?:startup|company|firm|maker|giant|unicorn|chipmaker|lab) (?=[A-Z])", "", t)
    m = re.match(r"(\S+)[^,]{0,60}, (.+)", t)
    if m and _bare(m.group(1)) in _LEAD:
        t = m.group(2)
    t = t.rstrip(" .,:;—–-")
    # the headline's words as they are, then (only if no cut fits) without its filler words
    for words in (t.split(), [w for i, w in enumerate(t.split()) if i == 0 or _bare(w) not in _FILLER]):
        if len(words) <= SUBJECT_WORDS:
            return " ".join(words)
        first = re.split(r"\s*(?::|;|\||\s[—–-]\s|,|\.\s)\s*", " ".join(words))[0].split()
        if 3 <= len(first) <= SUBJECT_WORDS and _ends_well(first):
            return " ".join(first)
        for k in range(SUBJECT_WORDS, 2, -1):
            nxt, cut = words[k], [w.rstrip(",:;") for w in words[:k]]
            figure = any(re.search(r"\d", w) for w in cut)  # "raises $52M seed | to build..."
            if (_bare(nxt) in _TAIL or (_bare(nxt) == "to" and figure) or words[k - 1][-1] in ",:;") and _ends_well(cut):
                return " ".join(cut)
    return None


def _kept(short: str, title: str) -> bool:
    """Is `short` 3 to SUBJECT_WORDS of the headline's own words, in the headline's order, ending cleanly, without
    leaving out a name, number or currency before its last word ("Claude [Duet] is...", "raise [R $] 163.5 billion")?"""
    words, have = title.split(), [w for w in short.split() if _bare(w)]
    said = [_bare(w) for w in words]
    if not 3 <= len(have) <= SUBJECT_WORDS or "…" in short or "..." in short or not _ends_well(have):
        return False
    i = 0
    for w in have:
        start = i
        while i < len(said) and said[i] != _bare(w):
            i += 1
        if i == len(said):
            return False
        if any(re.search(r"[A-Z\d$€£¥₹]", words[j]) for j in range(start, i) if j > 0):
            return False
        i += 1
    return True


def _gemini(title: str, ask=None) -> str | None:
    """For a headline no rule cuts cleanly, Gemini (free tier, memegen._ask) picks which of its words to keep; the
    answer must pass _kept (only the headline's own words, in order), so it can't add or change a fact."""
    key = os.environ.get("GEMINI_API_KEY")
    if not (ask or key) or GEMINI_ASKS[0] <= 0:
        return None
    GEMINI_ASKS[0] -= 1
    from . import memegen
    prompt = (f"Shorten this news headline to {SUBJECT_WORDS - 1} or {SUBJECT_WORDS} words for an email subject. "
              "Use only words from the headline, in the same order, unchanged; keep who did what, so it reads as a "
              "complete, plain phrase that says the same thing. No ellipsis, no added words. "
              f'Answer as JSON: {{"subject": "..."}}\n\nHeadline: {title}')
    try:
        answer = json.loads((ask or (lambda p: memegen._ask(p, key, timeout=60, temperature=0.2)))(prompt))["subject"]
    except Exception:  # no network, no allowance, a bad answer: the fallback in _subject
        return None
    answer = " ".join(str(answer).split()).rstrip(" .,:;—–-")
    return answer if _kept(answer, title) else None


def _subject(title: str, ask=None) -> str:
    """The lead headline in at most SUBJECT_WORDS of its own words, never with "…": cut by rule (_cut), or by Gemini
    when no rule cuts it cleanly (_gemini); failing both, its first words up to the last that ends cleanly."""
    if title not in _SHORTENED:
        short = _cut(title) or _gemini(title, ask)
        if not short:
            cut = re.split(r"\s*(?::|;|\||\s[—–-]\s)\s*", title)[0].split()[:SUBJECT_WORDS]
            while len(cut) > 3 and not _ends_well(cut):
                cut.pop()
            short = " ".join(cut).rstrip(" ,:;—–-")
        _SHORTENED[title] = short[:1].upper() + short[1:]
    return _SHORTENED[title]


# The inbox shows only the subject: mail apps fill the line after it from the email's first text (Gmail from the
# plain-text copy too), so both copies start with blank characters long enough to fill that line: combining grapheme
# joiner, zero-width non-joiner and no-break space, which Gmail doesn't trim away
BLANK = "͏‌ " * 110
BLANK_PREVIEW = "&#847;&zwnj;&nbsp;" * 110


def _tile(c: dict, n: str, picture: str, yours: bool) -> str:
    """A top-news story as a tile: its stream and picture on the stream's colour, then its headline and outlets."""
    kicker = rss.FEEDS[n][1] + (" · Your choice" if yours else "")
    return _table(f'<tr><td style="background:{FILL[n]};border-bottom:2px solid {INK};padding:0">{_label(kicker)}'
                  f'<a href="{escape(c["url"])}"><img src="{picture}" width="190" alt="" style="display:block;width:100%;'
                  f'height:auto;border:0"></a></td></tr><tr><td style="padding:8px 8px 10px;overflow-wrap:break-word;'
                  f'word-break:break-word"><a class="p-tt" href="{escape(c["url"])}" style="color:{INK};text-decoration:none;'
                  f'font-weight:bold;font-size:13px;line-height:1.35">{escape(c["title"])}</a>'
                  f'<div class="p-ts" style="font-size:11px;color:{GREY};margin-top:5px">'
                  f'{escape(_by(c))}</div></td></tr>', f"border:2px solid {INK}")


def _word_tile(kicker: str, e: dict, came_up: str) -> str:
    """A glossary word in the site's blue tile: the word on yellow, its meaning, where it came up (HTML)."""
    return _table(f'<tr><td style="padding:16px 18px;background:{BLUE};border:2px solid {INK};color:#ffffff">'
                  f'<div style="font-weight:bold;font-size:12px;letter-spacing:.5px">{kicker}</div>'
                  f'<div style="font-family:{HEAD};font-weight:900;font-size:24px;line-height:1.2;margin:6px 0 8px"><span style="background:{YELLOW};'
                  f'color:{INK};padding:0 5px">{escape(e["term"])}</span></div>'
                  f'<div style="font-size:15px;line-height:1.5">{escape(e["def"])}</div>{came_up}'
                  f'<div style="font-size:13px;margin-top:8px"><a href="{rss.SITE}glossary/" style="color:#ffffff;'
                  f'font-weight:bold">More words in the glossary →</a></div></td></tr>', "margin:0 0 14px")


def _meme_tile(meme: dict, picture: bytes, src: str, cid: str, kicker: str) -> str:
    """A meme in the vermilion tile: the site's copy at `src` (static.py publishes it), so nothing is attached;
    inside the email (as `cid`) if the site doesn't have it yet."""
    from . import memes
    try:
        with urllib.request.urlopen(urllib.request.Request(src, method="HEAD"), timeout=10) as r:
            online = r.status == 200
    except OSError:
        online = False
    if not online:
        digest.INLINE[cid] = picture
        src = "cid:" + cid
    return _table(f'<tr><td align="center" style="padding:14px;background:{VERMILION};border:2px solid {INK}">'
                  f'<div style="font-weight:bold;font-size:12px;letter-spacing:.5px;color:#ffffff;margin-bottom:10px">'
                  f'{kicker}</div>{memes.html(meme, src, small=True)}</td></tr>', "margin:0 0 26px")


def _word_and_meme(cards: list[dict], day: date, streams: list[str], prefs: dict, tiers: list[list[dict]]) -> tuple[list[str], str]:
    """The word of the day (digest._word_entry) in the site's blue tile, and the meme of the day in a vermilion one."""
    e, story = digest._word_entry(cards, day, streams, prefs, tiers)
    text = ["WORD OF THE DAY: " + e["term"], e["def"], *([f"Where it came up: {story['title']} {story['url']}"] if story else []), ""]
    html = _word_tile("WORD OF THE DAY", e, f'<div style="font-size:13px;line-height:1.45;margin-top:8px">Where it came up: '
                      f'<a href="{escape(story["url"])}" style="color:#ffffff">{escape(story["title"])}</a></div>' if story else "")
    from . import memes
    meme = memes.of_the_day(cards, day)
    picture = meme and memes.render(meme)
    if picture:
        src = f"{rss.SITE}daily/{day.isoformat()}-meme.{'png' if digest._kind(picture) == 'png' else 'jpg'}"
        text += memes.text(meme) + [""]
        html += _meme_tile(meme, picture, src, digest.MEME_CID, "MEME OF THE DAY")
    return text, html


def _nth(d: date) -> str:
    return f"{d.day}{'th' if 10 < d.day % 100 < 14 else {1: 'st', 2: 'nd', 3: 'rd'}.get(d.day % 10, 'th')}"


def _masthead(day: date) -> str:
    """ "Daily digest for Friday 23rd October 2026"; Sunday's (weekly readers get only it): "Weekly digest for 19th–24th
    October 2026"."""
    if not digest.weekly(day):
        return f"Daily digest for {day:%A} {_nth(day)} {day:%B %Y}"
    monday, _ = digest._span(day)
    start = _nth(monday) + ("" if monday.month == day.month else f" {monday:%B}")
    return f"Weekly digest for {start}–{_nth(day)} {day:%B %Y}"


def _week_span(day: date) -> str:
    monday, _ = digest._span(day)
    return f"{monday.day} {monday:%b} – {day.day} {day:%b}"


def _hero(c: dict, n: str, kicker: str, half: bool = False) -> str:
    """A lead story (Hot today, Sunday's story of the week) as a cell: its labels, headline, summary, outlets and
    button, no picture; `half` for Sunday's two side by side (smaller type)."""
    summary = digest._short(c.get("summary") or "", 160 if half else 200, c.get("source", ""))
    size, width = (19, ' width="50%"') if half else (24, "")
    return (f'<td class="p-hot"{width} valign="top" style="padding:18px 16px 20px 20px">'
            f'{_label(kicker, YELLOW, INK)} {_label(rss.FEEDS[n][1].upper())}'
            f'<div style="margin:10px 0 8px"><a class="{"p-hh2" if half else "p-hh"}" href="{escape(c["url"])}" '
            f'style="font-family:{HEAD};font-weight:900;font-size:{size}px;line-height:1.15;color:{INK};text-decoration:none">{escape(c["title"])}</a></div>'
            + (f'<div style="font-size:{14 if half else 15}px;line-height:1.5;margin-bottom:8px">{escape(summary)}</div>' if summary else "")
            + f'<div style="font-size:12px;color:{GREY};margin-bottom:14px">{escape(_by(c))}</div>'
              f'{_button("Read the story →", c["url"])}</td>')


def _hero_text(c: dict, kicker: str) -> list[str]:
    summary = digest._short(c.get("summary") or "", 200, c.get("source", ""))
    return [kicker, c["title"], *([summary] if summary else []), _by(c), c["url"], ""]


def _band(title: str, dates: str, style: str = "") -> str:
    """A black band across the email: a title and its dates (on Sunday, the day after the week's part)."""
    return (f'<tr><td class="p-pad" style="{style}padding:14px 20px;background:{INK};color:#ffffff"><span style="font-family:{HEAD};font-weight:900;'
            f'font-size:22px;line-height:1.2;color:#ffffff">{escape(title)}</span><span style="font-size:14px;color:#ffffff;'
            f'margin-left:10px">{escape(dates)}</span></td></tr>')


def _dossier(dossier: dict | None) -> tuple[list[str], str]:
    """The weekly dossier card, in every subscriber's Sunday email (`dossier` as digest._dossier takes it): the
    dossier page's drawing on yellow, then a line and the button: "Get my dossier" (the reader's own question box on
    ask.html) or, once they have one, "Open your weekly dossier"."""
    if not dossier or not (dossier.get("entries") or dossier.get("ask")):
        return [], ""
    ask = dossier.get("ask") or ""
    pitch = "Ask what you want to follow in AI, and get last week's stories on it, picked just for you."
    if dossier.get("entries"):  # the button opens the dossier page with the question box (ask.html), or, without it, the dossier
        link = ask if ask.startswith(rss.SITE + "ask.html#") else dossier["link"]
        text = [f"YOUR WEEKLY DOSSIER, {dossier['week']}", f"Open your weekly dossier: {link}"]
        kicker, title, words = f"YOUR WEEKLY DOSSIER · {dossier['week'].upper()}", "This week on what you follow", "Open your weekly dossier →"
    else:
        link = ask
        text = ["YOUR WEEKLY DOSSIER", pitch, f"Get my dossier: {link}"]
        kicker, title, words = "YOUR WEEKLY DOSSIER", "Follow what you care about", "Get my dossier →"
    html = _table(f'<tr><td width="30%" valign="middle" style="width:30%;background:{YELLOW};border:2px solid {INK};padding:0">'
                  f'<a href="{escape(link)}"><img src="{_picture("pages/ask")}" width="170" alt="" style="display:block;width:100%;'
                  f'height:auto;border:0"></a></td><td valign="top" style="padding:12px 14px 14px;border:2px solid {INK};'
                  f'border-left:0">{_label(kicker)}<div style="font-family:{HEAD};font-weight:900;font-size:18px;line-height:1.2;margin:8px 0 6px">'
                  f'{escape(title)}</div><div style="font-size:14px;line-height:1.45;margin-bottom:12px">{escape(pitch)}</div>'
                  f'{_button(words, link)}</td></tr>', "margin:0 0 6px")
    return text, html


def _week_word_and_meme(cards: list[dict], day: date) -> tuple[list[str], str]:
    """Sunday's word and meme: the word of the week (digest._week_word, with how many of the week's stories used it)
    in the blue tile, and the meme of the week in the vermilion one."""
    from . import glossary, memes
    text, html = [], ""
    monday, days = digest._span(day)
    wid = digest._week_word(cards, day)
    if wid:
        e = next(x for x in glossary.ENTRIES if x["id"] == wid)
        used = sorted([c for c in cards if (c.get("date") or "") in days and glossary.mentions(wid, digest._text(c))],
                      key=lambda c: (1 + len(c.get("also") or []), c.get("date") or ""), reverse=True)
        text += ["WORD OF THE WEEK: " + e["term"], e["def"], f"It came up in {len(used)} of the week's stories, like:",
                 *(f"  {c['title']} {c['url']}" for c in used[:2]), ""]
        html += _word_tile("WORD OF THE WEEK", e, f'<div style="font-size:13px;line-height:1.45;margin-top:8px">It came up in '
                           f'{len(used)} of the week\'s stories, like: ' + " · ".join(
                               f'<a href="{escape(c["url"])}" style="color:#ffffff">{escape(c["title"])}</a>' for c in used[:2])
                           + '</div>')
    meme = memes.of_the_week([c for c in cards if (c.get("date") or "") <= day.isoformat()], monday)
    picture = meme and memes.render(meme)
    if picture:
        src = f"{rss.SITE}daily/{day.isoformat()}-week-meme.{'png' if digest._kind(picture) == 'png' else 'jpg'}"
        text += memes.text(meme) + [""]
        html += _meme_tile(meme, picture, src, digest.MEME_WEEK_CID, "MEME OF THE WEEK")
    return text, html


def day_lanes(cards: list[dict], day: date) -> list[tuple[str, str, list[tuple[dict, str]]]]:
    """The day's lanes, (title, icon, [(story, stream)]): every story of the day in every stream, the most-reported
    first, each in the first lane that takes it; lanes without a story are left out. The same for every reader."""
    by_stream = digest.by_streams(cards, list(rss.FEEDS), day)
    stories = sorted([(c, n) for n in rss.FEEDS for c in by_stream[n] if c.get("kind") not in digest.SIDE_KINDS],
                     key=lambda cn: digest._rank(cn[0]), reverse=True)
    taken: set[int] = set()
    out = []
    for title, icon, fits in LANES:
        theirs = [(c, n) for c, n in stories if id(c) not in taken and fits(n, _tags(c), c.get("title") or "")]
        taken |= {id(c) for c, _ in theirs}
        if theirs:
            out.append((title, icon, theirs))
    return out


def lanes_page(day: date) -> str:
    """The web page with that day's lanes (static.py publishes it next to the day's full email)."""
    return f"{rss.SITE}daily/{day.isoformat()}-lanes.html"


def lanes_html(cards: list[dict], day: date) -> str | None:
    """The day's lanes page: a jump button per lane, then each lane's stories as a table (headline, outlets, stream);
    None on a day without one."""
    lanes = day_lanes(cards, day)
    if not lanes:
        return None
    # the jump buttons: one row, equal widths, at every width (a phone only shrinks the type)
    jumps = '<div style="display:flex;gap:5px">' + "".join(
        f'<a class="l-jump" href="#{icon}" style="flex:1 1 0;min-width:0;padding:7px 4px;border:2px solid {INK};color:{INK};'
        f'text-decoration:none;font-weight:bold;font-size:14px;line-height:1.25;text-align:center"><img src="'
        f'{_picture("lanes/" + icon)}" width="16" height="16" alt="" style="vertical-align:middle;border:0"> {escape(title)}'
        f'<div style="font-weight:normal;color:{GREY}">{len(theirs)}</div></a>' for title, icon, theirs in lanes) + '</div>'
    sections = []
    for title, icon, theirs in lanes:
        rows = "".join(f'<tr class="p-row"><td style="padding:9px 10px 9px 0;border-top:1px solid #cccccc;font-size:15px;line-height:1.35">'
                       f'<a href="{escape(c["url"])}" style="color:{INK};text-decoration:none;font-weight:bold">{escape(c["title"])}</a>'
                       f'<div style="font-size:12px;color:{GREY};margin-top:3px">{escape(_by(c))}</div></td><td width="96" '
                       f'align="right" valign="top" style="width:96px;padding:9px 0;border-top:1px solid #cccccc">'
                       f'{_label(rss.FEEDS[n][1].upper(), FILL[n], INK)}</td></tr>' for c, n in theirs)
        count = f"{len(theirs)} {'story' if len(theirs) == 1 else 'stories'}"
        sections.append(f'<div id="{icon}" style="margin:26px 0 0"><h2 style="margin:0;font-family:{HEAD};font-size:22px;'
                        f'font-weight:900;border-bottom:3px solid {INK};padding-bottom:6px"><img src="{_picture("lanes/" + icon)}" '
                        f'width="24" height="24" alt="" style="vertical-align:middle;border:0"> {escape(title)} <span style="'
                        f'font-family:{BODY};font-size:14px;color:{GREY}">{count}</span></h2>{_table(rows)}</div>')
    title = f"Pick your lane · {digest.long_day(day)}"
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&amp;display=swap" rel="stylesheet">'
            f'<title>{escape(title)}</title><style>a:hover{{opacity:.75}}.p-row:hover td{{background:#f2f2f2}}'
            '@media (max-width:480px){.l-jump{font-size:10px!important;padding:6px 1px!important;letter-spacing:-.2px}.l-jump img{display:block;'
            'margin:0 auto 3px}}</style></head>'
            f'<body style="margin:0;background:#ffffff;font-family:{BODY};color:{INK}"><div style="max-width:680px;margin:0 auto">'
            f'<div style="background:{INK};color:#ffffff;padding:20px"><a href="{rss.SITE}" style="color:#ffffff;font-size:13px;'
            f'font-weight:bold;text-decoration:none">AI Pulse</a><h1 style="margin:6px 0 0;font-family:{HEAD};font-size:26px;'
            f'font-weight:900">Pick your lane</h1><div style="font-size:14px;margin-top:4px">{digest.long_day(day)}: the day\'s '
            f'stories sorted by who they matter to. Each story sits in one lane.</div></div><div style="padding:16px 16px 30px">'
            f'{jumps}{"".join(sections)}<div style="margin-top:26px;font-size:14px"><a href="{escape(digest.full_page(day))}" '
            f'style="color:{INK};font-weight:bold">Every story of {day:%A} →</a></div></div></div></body></html>')


def _spread(ranked: list[dict], taken: list[dict], n: int, stream_of: dict[int, str]) -> list[dict]:
    """Up to n more top news stories after `taken` (the hot story first, which isn't a tile), in rank order but at
    most PER_STREAM tiles from a stream; a story over that still goes first when more outlets carried it than the
    best one left from another stream (on a quiet day, when most stories have one outlet, the tiles mix the streams
    instead of filling with the first stream's)."""
    per = Counter(stream_of[id(c)] for c in taken[1:])
    left, out = [c for c in ranked if c not in taken], []
    while left and len(out) < n:
        c = next((c for c in left if per[stream_of[id(c)]] < PER_STREAM), left[0])
        if digest._outlets(left[0]) > digest._outlets(c):
            c = left[0]
        out.append(c)
        left.remove(c)
        per[stream_of[id(c)]] += 1
    return out


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
    lead = (mine + [c for c in main if c not in mine])[:1] or ranked[:1]
    taken = lead + [c for c in mine if c not in lead]
    top = taken[:1 + TOP_NEWS]
    top += _spread([c for c in main if c not in mine] or ranked, top, 1 + TOP_NEWS - len(top), stream_of)
    shown = {id(c) for c in top}
    text, html = [], []
    stories = len(todays)  # stories, not outlets: the stream rows add up to it
    pad = 'class="p-pad" style="padding:20px 20px 0"'

    # The masthead: which day (or, on Sunday, week) this is (the inbox already shows the sender's name and picture)
    html.append(f'<tr><td class="p-pad p-mast" style="padding:14px 20px;border-bottom:3px solid {INK};font-family:{HEAD};font-weight:900;'
                f'font-size:18px;line-height:1.25">{escape(_masthead(day))}</td></tr>')

    # The lead: Hot today, the day's most-reported story (no picture); on Sunday beside the story of the week (as the
    # site picks it, digest._week_story), the masthead already naming the week
    week = digest._week_story(cards, day, prefs) if digest.weekly(day) else None
    leads = []
    if week:
        n = next((n for n in rss.FEEDS if rss.FEEDS[n][0] == week["category"]), "news")
        text += [f"THE WEEK IN AI, {_week_span(day)}", ""] + _hero_text(week, "STORY OF THE WEEK")
        leads.append((week, n, "STORY OF THE WEEK"))
    if top:
        hot = top[0]
        kicker = "HOT TODAY" + (" · YOUR CHOICE" if id(hot) in picks else "")
        text += _hero_text(hot, kicker)
        leads.append((hot, stream_of[id(hot)], kicker))
    if leads:
        cells = f'<td width="3" style="width:3px;padding:0;background:{INK}"></td>'.join(
            _hero(c, n, kicker, half=len(leads) == 2) for c, n, kicker in leads)
        html.append(f'<tr><td style="padding:0;border-bottom:3px solid {INK}">' + _table(f'<tr>{cells}</tr>') + '</td></tr>')

    # Sunday: the week's word and meme (in place of the day's) and the reader's dossier, then the day's band; the
    # day's own sections follow it
    if digest.weekly(day):
        word_text, word_html = _week_word_and_meme(cards, day)
        dossier_text, dossier_html = _dossier(dossier)
        text += word_text + ([*dossier_text, ""] if dossier_html else []) + [f"{day:%A} {day.day} {day:%B}".upper(), ""]
        html.append(f'<tr><td {pad}>{word_html}{dossier_html}</td></tr>'
                    + _band(f"{day:%A}", f"{day.day} {day:%b}", "margin-top:20px;"))

    body = []  # the sections in the padded column
    if len(top) > 1:
        text += ["TOP NEWS", *(f"• [{rss.FEEDS[stream_of[id(c)]][1]}] {c['title']} ({_by(c)}) {c['url']}" for c in top[1:]), ""]
        tiles = [_tile(c, stream_of[id(c)], _art(c, stream_of[id(c)]), id(c) in picks) for c in top[1:]]
        # three to a row on every screen (a phone only shrinks the type, see STYLE)
        grid = "".join(f'<div class="p-tile" style="display:inline-block;vertical-align:top;width:33.33%;box-sizing:border-box;'
                       f'padding:0 5px 10px;font-size:15px">{tile}</div>' for tile in tiles)
        body.append(_heading("Top news") + f'<div style="margin:0 -5px 14px;font-size:0">{grid}</div>')
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
        body.append(_table(f'<tr><td class="p-numc" width="34%" valign="middle" style="width:34%;padding:14px 16px;background:{YELLOW};'
                           f'border:2px solid {INK};border-right:0"><div style="font-weight:bold;font-size:12px;letter-spacing:.5px">'
                           f'NUMBER OF THE DAY</div><div class="p-num" style="font-family:{HEAD};font-weight:900;font-size:34px;line-height:1.1;'
                           f'white-space:nowrap">{escape(figure)}</div></td>'
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
                           f'<div style="font-family:{HEAD};font-weight:900;font-size:18px;line-height:1.2;margin:8px 0 6px">{escape(name)}</div>'
                           f'<div style="font-size:14px;line-height:1.45">{escape(what)}</div><div style="margin-top:8px">'
                           f'<a href="{escape(rss.SITE + path)}" style="color:{INK};font-weight:bold;font-size:13px">Have a look →</a>'
                           f'</div></td></tr>', "margin:0 0 26px"))
    html.append(f'<tr><td {pad}>{"".join(body)}</td></tr>')

    # Pick your lane: a row per lane, each opening that lane on the day's lanes page (every story of the day, all
    # streams, so the counts are the page's); under the name, the lane's first story not already shown above
    lanes = day_lanes(cards, day)
    if lanes:
        web_lanes = lanes_page(day)
        text += ["PICK YOUR LANE", f"The day sorted by who it matters to: {web_lanes}"]
        rows = []
        for title, icon, theirs_ in lanes:
            count = f"{len(theirs_)} {'story' if len(theirs_) == 1 else 'stories'}"
            first = next((c for c, _ in theirs_ if id(c) not in shown), theirs_[0][0])
            href = escape(f"{web_lanes}#{icon}")
            text.append(f"  {title}: {count}")
            rows.append(f'<tr class="p-row"><td width="30" style="width:30px;padding:11px 0;border-bottom:1px solid #cccccc">'
                        f'<img src="{_picture("lanes/" + icon)}" width="22" height="22" alt="" style="vertical-align:middle;border:0">'
                        f'</td><td style="padding:11px 8px;border-bottom:1px solid #cccccc"><a href="{href}" style="color:{INK};'
                        f'text-decoration:none;font-weight:bold;font-size:15px">{escape(title)}</a><div style="font-size:12px;'
                        f'color:{GREY};margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
                        f'{escape(first["title"])}</div></td><td width="92" align="right" style="width:92px;padding:11px 0;'
                        f'border-bottom:1px solid #cccccc;font-size:14px;white-space:nowrap"><a href="{href}" style="color:{INK};'
                        f'text-decoration:none">{count} ▸</a></td></tr>')
        text.append("")
        html.append(f'<tr><td class="p-pad" style="padding:18px 20px 16px;background:{INK};color:#ffffff">'
                    f'<div style="font-family:{HEAD};font-weight:900;font-size:20px;line-height:1.2;color:#ffffff">Pick your lane</div>'
                    f'<div style="font-size:14px;margin-top:4px;color:#ffffff">The day sorted by who it matters to.</div></td></tr>'
                    f'<tr><td class="p-pad" style="padding:6px 20px 22px">{_table("".join(rows))}<div style="margin-top:16px">'
                    f'{_button("See every lane →", web_lanes)}</div></td></tr>')

    # How useful is it: 1 to 5, each opens the site's review form with that number picked (all five alike)
    review = rss.SITE + "review/"
    text += ["HOW USEFUL IS AI PULSE TO YOU? Tap a number, then four more quick questions: " + review, ""]
    numbers = "".join(f'<td style="padding:0 6px 0 0"><a href="{escape(review)}#useful-{k}" style="display:block;width:34px;'
                      f'height:34px;line-height:34px;text-align:center;border:2px solid {INK};font-weight:bold;font-size:16px;'
                      f'color:{INK};text-decoration:none">{k}</a></td>' for k in range(1, 6))
    html.append(f'<tr><td class="p-pad" style="padding:20px">' + _table(
        f'<tr><td style="padding:12px 14px;border:2px solid {INK}"><div style="font-weight:bold;font-size:15px">How useful is '
        f'AI Pulse to you?</div><div style="font-size:12px;color:{GREY};margin:3px 0 10px">Tap a number, then four more quick '
        f'questions. 1 not useful · 5 very useful</div><table role="presentation" cellpadding="0" cellspacing="0"><tr>{numbers}'
        f'</tr></table></td></tr>') + '</td></tr>')

    # The Firehose: a row per stream, each opening that stream's part of the day's page on the site (every story)
    web = digest.full_page(day)
    text += ["THE FIREHOSE", f"All {stories} stories of {day:%A}: {web}"]
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
    html.append(f'<tr><td class="p-pad" style="padding:18px 20px 16px;background:{INK};color:#ffffff"><div style="font-family:{HEAD};font-weight:900;'
                f'font-size:22px;line-height:1.2;color:#ffffff">The Firehose</div><div style="font-size:14px;line-height:1.45;'
                f'margin-top:4px;color:#ffffff">'
                f'All {stories} stories of {day:%A}.</div></td></tr>'
                f'<tr><td class="p-pad" style="padding:6px 20px 22px">{_table("".join(rows))}<div style="margin-top:16px">'
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

    # "Daily Digest: " (Sunday: "Weekly Digest: " and the story of the week), then the lead in a few of its own words
    lead = week or (top[0] if top else None)
    subject = (("Weekly Digest: " if digest.weekly(day) else "Daily Digest: ")
               + (_subject(lead["title"]) if lead else digest.long_day(day)))
    page = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
            '<meta name="color-scheme" content="light only"><meta name="supported-color-schemes" content="light only">'
            '<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&amp;display=swap" rel="stylesheet">'
            f'<title>{escape(subject)}</title><style>{STYLE}</style></head><body style="margin:0;padding:0;background:#ffffff">'
            f'<div style="display:none!important;visibility:hidden;mso-hide:all;max-height:0;max-width:0;overflow:hidden;'
            f'opacity:0;font-size:0;line-height:0;color:#ffffff">{BLANK_PREVIEW}</div>'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff"><tr>'
            '<td align="center" style="padding:10px 6px 20px">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;background:#ffffff;'
            f'border:3px solid {INK};border-collapse:collapse;font-family:{BODY};font-size:15px;color:{INK}">' + "".join(html)
            + '</table></td></tr></table></body></html>')
    return subject, "\n".join([BLANK, *text]), page
