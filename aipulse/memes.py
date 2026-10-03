"""Meme of the day (in the daily email) and meme of the week (on the front page).

Each meme is a well-known internet meme template (Drake, Distracted Boyfriend, This Is Fine, Two Buttons, Expanding
Brain, Woman Yelling at Cat, Is This a Pigeon?, Panik Kalm Panik; copies in templates/memes/, from Imgflip's free
template list) with captions written onto it: by Gemini (memegen.py) or, without it, filled from our own data: the
day's or week's launches, raises, papers, power stories and glossary words, named as the headlines name them. The
templates are used as parody and commentary on a free, non-commercial site, credited under every meme. Jokes are light: about the AI
industry's habits, never a person; politics and any story about harm, death, crime, lawsuits, layoffs, war or
children are never used. A format is picked by the date from those the stories can fill, so the same day always
gives the same meme. The meme of the week is last week's (Monday to Sunday), so it changes every Monday.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, timedelta
from html import escape
from io import BytesIO
from pathlib import Path

from . import glossary

_SERIOUS_TAGS = {"Misuse", "Deepfakes", "Defense", "Elections", "Existential Risk", "Security", "Jobs & Labor",
                 "Surveillance", "Healthcare", "AI-incident", "Safety", "Alignment"}  # AI safety: never a joke (owner's rule)
_SERIOUS = re.compile(r"\b(?:die[sd]?|death|dead|deaths|kill\w*|suicid\w*|murder\w*|shoot\w*|war|wars|attack\w*|abus\w*|"
                      r"child\w*|minors?|teens?|victims?|harass\w*|assault\w*|sextortion|explicit|porn\w*|fraud\w*|"
                      r"scam\w*|arrest\w*|jail\w*|prison\w*|lawsuits?|su(?:e|es|ed|ing)|court|layoffs?|laid off|fired|"
                      r"crash\w*|injur\w*|weapons?|bombs?|terror\w*|hate|racis\w*|discriminat\w*|threat\w*|"
                      r"hack\w*|breach\w*|leak\w*|outage|grief|mental health|self-harm|smuggl\w*|sanction\w*|"
                      r"safety|unsafe|deceptive|existential|extinction|doom\w*)\b", re.I)
POLITICS = {"policy", "regulation"}  # governments, courts and politicians: never in a meme
# "Harvey raises $550M": who raised how much, only when the headline says so in those words (not a valuation, a
# deal's price or a round that was called off)
_RAISE = re.compile(r"\b([A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*)?)\s+(?:raises|raised|lands|secures|closes)\s+"
                    r"(\$\s?(\d+(?:\.\d+)?)\s?(billion|million|bn|[BM])\b)")


def light(c: dict) -> bool:
    """A story a joke may touch: nothing political, and nothing about harm, crime, lawsuits, layoffs, war or children."""
    text = f"{c.get('title') or ''} {c.get('summary') or ''}"
    return (c.get("kind") != "incident" and c.get("category") not in POLITICS
            and not _SERIOUS_TAGS & set(c.get("tags") or []) and not _SERIOUS.search(text))


def _pick(options: list[dict], when: date) -> dict | None:
    return options[when.toordinal() % len(options)] if options else None






# "Microsoft AI Releases MAI-Transcribe-2", "AWS debuts Strands Decider 2B, a ...": who launched what, only when the
# headline says it in those words
_LAUNCH = re.compile(r"^(?P<maker>[A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*){0,2})\s+"
                     r"(?i:launches|releases|debuts|introduces|unveils|open-sources|ships|rolls out)\s+(?:its\s+|the\s+|an?\s+|new\s+)*"
                     r"(?P<product>[A-Za-z0-9][\w.+-]*(?:\s+[A-Z0-9][\w.+-]*){0,3})"
                     r"(?=\s*[:,–—]|\s+-\s|\s+(?:a|an|for|with|that|to|in|and|on)\b|$)")


def launch_of(c: dict) -> tuple[str, str] | None:
    """(maker, product) when the headline names both."""
    m = _LAUNCH.match(c.get("title") or "")
    if not m:
        return None
    maker, product = m.group("maker"), m.group("product")
    first = product.split()[0]
    if len(product) > 30 or not (first[0].isupper() or re.search(r"[\d-]", first)):
        return None
    return maker, product


def facts(cards: list[dict]) -> dict:
    """What the stories say, for the jokes: launches by name, the biggest amount raised, papers, power, the busiest word."""
    ok = [c for c in cards if light(c)]
    launches = [c for c in ok if c.get("category") == "tool"]
    named, makers = [], set()
    for c in launches:
        if (lp := launch_of(c)) and lp[0] not in makers:  # one launch a maker, so two named launches are two makers
            named.append((*lp, c))
            makers.add(lp[0])
    money = []
    for c in ok:
        m = _RAISE.search(c.get("title") or "")
        if m and "Funding" in (c.get("tags") or []):
            value = float(m.group(3)) * (1000 if m.group(4).lower() in ("billion", "bn", "b") else 1)
            who = m.group(1).split()
            if len(who) == 2 and ("-" in who[0] or who[0].lower().endswith("tech")):  # "Iceland-based Treble", "Insurtech Outmarket"
                who = who[1:]
            money.append((value, m.group(2).replace(" ", ""), " ".join(who), c))
    # a word is never sensitive: counted over every story, as the front page's word of the week counts it
    words = Counter(e for c in cards for e in dict.fromkeys(glossary.terms_in(f"{c.get('title')} {c.get('summary') or ''}")))
    word = None
    if words:
        wid, n = words.most_common(1)[0]
        word = (next(x for x in glossary.ENTRIES if x["id"] == wid)["term"], n)
    return {
        "stories": len(cards), "launches": launches, "named": named,
        "money": max(money, key=lambda m: m[0]) if money else None,
        "power": [c for c in ok if c.get("category") == "infra" and {"Power & grid", "Builds & deals"} & set(c.get("tags") or [])],
        "papers": sum(c.get("category") == "research" for c in cards), "word": word,
    }


# ---------- The formats: each returns a meme, or None when the stories can't back the joke up ----------
# span is "today" or "this week"; the thresholds are for a day and are raised for a week.

def _of(name: str) -> str:
    """Who owns it: "OpenAI's", "Supersonic Labs'"."""
    return name + ("'" if name.endswith("s") else "'s")


def _when(span: str) -> str:
    return "this morning" if span == "today" else "earlier this week"


def _distracted(f, span):
    """The distracted look back: developers turning to the newest launch while the last one glares."""
    if not f["named"]:
        return None
    (maker, product, c), *rest = f["named"]
    old = f"{_of(rest[0][0])} {rest[0][1]}, launched {_when(span)}" if rest else "the model they switched to last week"
    return {"format": "distracted", "labels": [f"{_of(maker)} {product}", "Developers", old],
            "based_on": [c["title"]] + ([rest[0][2]["title"]] if rest else [])}


def _buttons(f, span):
    """Two buttons: two launches, one free afternoon."""
    if len(f["named"]) < 2:
        return None
    (m1, p1, c1), (m2, p2, c2) = f["named"][:2]
    return {"format": "buttons", "labels": [f"Try {_of(m1)} {p1}", f"Try {_of(m2)} {p2}"],
            "caption": "Developers with one free afternoon", "based_on": [c1["title"], c2["title"]]}


def _nope_yep(f, span):
    """Nope / yep: where the money went."""
    if not f["money"]:
        return None
    _, amount, who, c = f["money"]
    return {"format": "nopeyep", "who": "AI investors " + span,
            "nope": "Putting money in a nice, sensible savings account", "yep": f"Handing {who} {amount}", "based_on": [c["title"]]}


def _fine(f, span):
    """This is fine: the day's pile of launches."""
    n = len(f["launches"])
    if n < (4 if span == "today" else 15):
        return None
    return {"format": "fine", "caption": f"{n} new AI models and tools {span}",
            "under": "Me, still trying out last week's", "based_on": []}


def _brain(f, span):
    """The expanding brain: how to keep up with the papers."""
    n = f["papers"]
    if n < (5 if span == "today" else 20):
        return None
    return {"format": "brain", "rows": ["Reading the headline", "Reading the abstract",
                                        f"Reading all {n} AI papers out {span}", "Letting AI Pulse pick the ones that matter"],
            "based_on": []}


def _yelling(f, span):
    """Yelling at the robot at the dinner table: the power grid and the data centres."""
    if not f["power"]:
        return None
    return {"format": "yelling", "labels": ["Every power grid in 2026", "“I just need one more data centre.”"],
            "based_on": [f["power"][0]["title"]]}


# "Is this a ...?": what gets called the word of the day, when it shouldn't be
MISNAMED = {
    "AI agent": "a chatbot with a to-do list", "Coding agent": "autocomplete that opens pull requests",
    "Computer-use agent": "a bot clicking buttons very slowly", "AGI": "a slightly better autocomplete",
    "Superintelligence": "a chatbot that's good at maths", "Reasoning model": "a model that says “let me think”",
    "Open source": "a model with a download button", "Open-weight model": "a model with a download button",
    "Multimodal": "a chatbot that can see your cat", "Copilot": "a sidebar", "Frontier model": "whatever came out this morning",
    "World model": "a really good video game", "Humanoid robot": "a very expensive mannequin",
    "Sovereign AI": "a data centre with a flag on it", "MCP": "any plug-in", "RAG": "a search box with extra steps",
    "Small language model": "a big model on a diet", "On-device AI": "your phone getting warm",
    "Data center": "a warehouse with a power bill", "Hyperscaler": "anyone with a data centre",
    "State of the art": "this week's benchmark", "Foundation model": "a model with a big launch video",
}


def _pigeon(f, span):
    """Is this a ...?: the busiest word, pinned on the wrong thing."""
    if not f["word"] or f["word"][0] not in MISNAMED:
        return None
    term = f["word"][0]
    article = "an" if term[0].lower() in "aeiou" or term in ("MCP", "RAG", "LLM") else "a"
    return {"format": "pigeon", "labels": [f"Every launch {span}", MISNAMED[term]], "caption": f"Is this {article} {term}?",
            "based_on": []}


def _panik(f, span):
    """Panik / kalm / panik: a launch, the email, the boss."""
    if not f["named"]:
        return None
    maker, product, c = f["named"][-1]
    return {"format": "panik", "rows": [("Panik", f"{maker} launches {product}"), ("Kalm", "Your code still works"),
                                        ("Panik", "Your boss saw the demo")], "based_on": [c["title"]]}


FORMATS = [_distracted, _buttons, _nope_yep, _fine, _brain, _yelling, _pigeon, _panik]
GENERATED: dict = {}  # ("day" | "week", date) -> a meme Gemini wrote (memegen.prepare); used instead of the rules


def of_the_day(cards: list[dict], day: date) -> dict | None:
    """The day's meme, from that day's stories (the same for every reader)."""
    f = facts([c for c in cards if c.get("date") == day.isoformat()])
    meme = GENERATED.get(("day", day)) or _pick([m for g in FORMATS if (m := g(f, "today"))], day)
    return meme and {**meme, "title": "Meme of the day"}


def of_the_week(cards: list[dict], monday: date) -> dict | None:
    """The meme of the week from Monday to Sunday's stories."""
    week = [c for c in cards if monday.isoformat() <= (c.get("date") or "") < (monday + timedelta(days=7)).isoformat()]
    f = facts(week)
    meme = GENERATED.get(("week", monday)) or _pick([m for g in FORMATS if (m := g(f, "this week"))], monday)
    return meme and {**meme, "title": "Meme of the week"}


def payload(cards: list[dict], today: date | None = None) -> dict:
    """meme.json for the front page: last week's meme (Monday to Sunday, UTC, as the word of the week). It changes
    every Monday. Its picture is made by the build (memes/week-<monday>.jpg)."""
    today = today or date.today()
    monday = today - timedelta(days=today.weekday() + 7)
    meme = of_the_week(cards, monday)
    image = f"memes/week-{monday.isoformat()}.jpg"  # the finished picture, written by the build (static.py)
    ok = bool(meme and render(meme))
    # the news behind it, linked to the stories themselves (a meme made from the week's words has none)
    week = {c["title"]: c for c in cards if monday.isoformat() <= (c.get("date") or "") < (monday + timedelta(days=7)).isoformat()}
    behind = [{"title": t, "url": week[t]["url"], "source": week[t].get("source") or ""}
              for t in (meme or {}).get("based_on") or [] if t in week and week[t].get("url")][:3]
    return {"from": monday.isoformat(), "to": (monday + timedelta(days=6)).isoformat(),
            "html": html(meme, image) if ok else "", "format": meme["format"] if ok else None, "image": image if ok else None,
            "stories": behind if ok else [], "week": len(week)}


# ---------- The real meme templates, captions written onto them (one finished picture, the same in every mail app) ----------

# The well-known templates, from Imgflip's free template list (api.imgflip.com/get_memes); a copy of each is kept here
# so old emails never lose their picture. Used as parody and commentary on a free, non-commercial site (the owner's
# choice, 2026-10-04), with the template credited under every meme.
DIR = Path(__file__).resolve().parent.parent / "templates" / "memes"
WIDTH = 800  # every finished meme is this wide
# format: (template file, its name, the caption boxes as fractions of the picture: x, y, width, height, style, turn)
# style "photo": white capitals with a black outline, on a picture; "panel": black text on a white panel
TEMPLATES = {
    "distracted": ("distracted.jpg", "Distracted Boyfriend",
                   [(.10, .55, .38, .18, "photo", 0), (.45, .36, .32, .14, "photo", 0), (.72, .48, .27, .26, "photo", 0)]),
    "buttons": ("buttons.jpg", "Two Buttons",
                [(.06, .12, .40, .12, "photo", 14), (.44, .04, .38, .12, "photo", 14), (.04, .82, .92, .12, "photo", 0)]),
    "nopeyep": ("nopeyep.jpg", "Drake Hotline Bling", [(.52, .04, .46, .42, "panel", 0), (.52, .54, .46, .42, "panel", 0)]),
    "fine": ("fine.jpg", "This Is Fine", [(.02, .03, .47, .30, "photo", 0), (.52, .72, .46, .26, "photo", 0)]),
    "brain": ("brain.jpg", "Expanding Brain", [(.02, .0, .46, .24, "panel", 0), (.02, .25, .46, .24, "panel", 0),
                                               (.02, .51, .46, .22, "panel", 0), (.02, .74, .46, .25, "panel", 0)]),
    "yelling": ("yelling.jpg", "Woman Yelling at Cat", [(.01, .0, .49, .22, "panel", 0), (.51, .0, .48, .22, "panel", 0)]),
    "pigeon": ("pigeon.jpg", "Is This a Pigeon?",
               [(.03, .48, .46, .17, "photo", 0), (.60, .27, .38, .19, "photo", 0), (.05, .83, .90, .15, "photo", 0)]),
    "panik": ("panik.png", "Panik Kalm Panik", [(.02, .0, .45, .33, "panel", 0), (.02, .34, .45, .33, "panel", 0),
                                                (.02, .67, .45, .33, "panel", 0)]),
}
TALL = {"buttons", "nopeyep", "brain", "panik"}  # taller than wide
FONTS = {"photo": DIR / "fonts" / "Anton-Regular.ttf", "panel": DIR / "fonts" / "ArchivoBlack-Regular.ttf"}


def captions(meme: dict) -> list[str]:
    """The meme's captions in the order of its template's boxes."""
    f = meme["format"]
    if f in ("distracted", "yelling"):
        return list(meme["labels"])
    if f in ("buttons", "pigeon"):
        return [*meme["labels"], meme["caption"]]
    if f == "nopeyep":
        return [meme["nope"], meme["yep"]]
    if f == "fine":
        return [meme["caption"], meme["under"]]
    if f == "brain":
        return list(meme["rows"])
    if f == "panik":
        return [t for _, t in meme["rows"]]
    return []


def _fit(draw, text: str, font_file: Path, w: int, h: int, start: int):
    """The biggest font size at which the text, wrapped on words, fits the box; and its lines."""
    from PIL import ImageFont
    for size in range(start, 9, -1):
        font = ImageFont.truetype(str(font_file), size)
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=font) <= w or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
        if max(draw.textlength(l, font=font) for l in lines) <= w and len(lines) * size * 1.12 <= h:
            break
    return font, lines, size


def _caption(img, text: str, box: tuple) -> None:
    from PIL import Image, ImageDraw
    x, y, w, h, style, turn = box
    W, H = img.size
    bw, bh = int(w * W), int(h * H)
    layer = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    text = text.upper() if style == "photo" else text
    font, lines, size = _fit(draw, text, FONTS[style], bw - 8, bh - 4, max(14, min(bh, int(W * .085))))
    stroke = max(2, size // 11) if style == "photo" else 0
    step = size * 1.12
    top = (bh - step * len(lines)) / 2
    for i, line in enumerate(lines):
        lw = draw.textlength(line, font=font)
        draw.text(((bw - lw) / 2, top + i * step), line, font=font, fill="white" if style == "photo" else "black",
                  stroke_width=stroke, stroke_fill="black")
    if turn:
        layer = layer.rotate(turn, expand=True, resample=Image.BICUBIC)
    cx, cy = int((x + w / 2) * W), int((y + h / 2) * H)
    img.alpha_composite(layer, (cx - layer.width // 2, cy - layer.height // 2))


_RENDERED: dict[str, bytes | None] = {}


def render(meme: dict) -> bytes | None:
    """The finished meme as a JPEG: the template with its captions written on, or None if it can't be made (no
    Pillow, an unknown format); the email and the site then leave the meme out."""
    key = json.dumps([meme.get("format"), meme.get("who"), captions(meme) if meme.get("format") in TEMPLATES else None])
    if key in _RENDERED:
        return _RENDERED[key]
    try:
        from PIL import Image
        file, _, boxes = TEMPLATES[meme["format"]]
        img = Image.open(DIR / file).convert("RGBA")
        img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
        for words, box in zip(captions(meme), boxes):
            _caption(img, words, box)
        if meme["format"] == "nopeyep" and meme.get("who"):  # whose choice: a white band on top
            band = Image.new("RGBA", (WIDTH, 90), "white")
            _caption(band, meme["who"], (.02, .05, .96, .9, "panel", 0))
            full = Image.new("RGBA", (WIDTH, img.height + 90), "white")
            full.paste(band, (0, 0))
            full.paste(img, (0, 90))
            img = full
        out = BytesIO()
        img.convert("RGB").save(out, "JPEG", quality=86, optimize=True)
        _RENDERED[key] = out.getvalue()
    except (ImportError, KeyError, OSError, ValueError):
        _RENDERED[key] = None
    return _RENDERED[key]


def html(meme: dict, src: str) -> str:
    """The finished picture (src: its address, or "cid:..." for the copy inside an email), its words as the alt
    text, and the credits: Gemini's captions said plainly, and the template's source."""
    credit = ("Captions written with Gemini · " if meme.get("by") == "gemini" else "") + "via imgflip.com"  # the source, not the template's name
    alt = " ".join(text(meme)[1:])
    width = 420 if meme["format"] in TALL else 600  # a tall template stays short enough to read without scrolling
    return (f'<div style="max-width:{width}px;background:#ffffff;border:2px solid #1d2433;border-radius:6px;overflow:hidden;'
            f'font-family:Arial,Helvetica,sans-serif;color:#1d2433">'
            f'<img src="{escape(src)}" width="{width}" alt="{escape(alt)}" '
            f'style="display:block;width:100%;max-width:{width}px;height:auto;border:0">'
            f'<div style="font-size:11px;color:#5f6368;padding:4px 8px 6px;text-align:right">{escape(credit)}</div></div>')


def text(meme: dict) -> list[str]:
    """The meme in the plain-text email: what happens in it, with its captions."""
    f = meme["format"]
    out = [meme["title"].upper() + ":"]
    if f == "distracted":
        new, who, old = meme["labels"]
        out.append(f"{who}, walking with {old}, turning to stare at {new}.")
    elif f == "buttons":
        out += [f"Two buttons: “{meme['labels'][0]}” or “{meme['labels'][1]}”.", f"Sweating: {meme['caption']}."]
    elif f == "nopeyep":
        out += [meme["who"] + ":", f"  Nope: {meme['nope']}", f"  Yep: {meme['yep']}"]
    elif f == "fine":
        out += [meme["caption"] + ".", f"{meme['under']}: “This is fine.”"]
    elif f == "brain":
        out += [f"  {'🧠' * i} {t}" for i, t in enumerate(meme["rows"], 1)]
    elif f == "yelling":
        out.append(f"{meme['labels'][0]} / the cat: {meme['labels'][1]}")
    elif f == "pigeon":
        out += [f"{meme['labels'][0]}, pointing at {meme['labels'][1]}:", meme["caption"]]
    elif f == "panik":
        out += [f"  {k.upper()}: {t}" for k, t in meme["rows"]]
    return out
