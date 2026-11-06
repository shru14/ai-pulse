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


def _v(f, options):
    """One of several wordings, by the meme's turn (the date), so a format that comes back doesn't repeat its joke."""
    return options[f.get("turn", 0) % len(options)]


def _distracted(f, span):
    """The distracted look back: the newest launch turns heads while the last one glares."""
    if not f["named"]:
        return None
    (maker, product, c), *rest = f["named"]
    old = f"{_of(rest[0][0])} {rest[0][1]}, launched {_when(span)}" if rest else _v(f, [
        "the model they switched to last week", "the model they called the best ever last month",
        "the setup they finished yesterday", "last week's favourite"])
    return {"format": "distracted",
            "labels": [f"{_of(maker)} {product}", _v(f, ["Developers", "AI researchers", "Everyone with a GPU", "Tech teams"]), old],
            "based_on": [c["title"]] + ([rest[0][2]["title"]] if rest else [])}


def _buttons(f, span):
    """Two buttons: two launches, one free afternoon."""
    if len(f["named"]) < 2:
        return None
    (m1, p1, c1), (m2, p2, c2) = f["named"][:2]
    return {"format": "buttons", "labels": [f"Try {_of(m1)} {p1}", f"Try {_of(m2)} {p2}"],
            "caption": _v(f, ["Developers with one free afternoon", "Every team with one GPU",
                              "Anyone with one API budget", "Developers before the stand-up"]),
            "based_on": [c1["title"], c2["title"]]}


def _nope_yep(f, span):
    """Nope / yep: where the money went."""
    if not f["money"]:
        return None
    _, amount, who, c = f["money"]
    return {"format": "nopeyep", "who": "AI investors " + span,
            "nope": _v(f, ["Putting money in a nice, sensible savings account", "Waiting to see a profit first",
                           "Asking what the product does", "Reading the business plan"]),
            "yep": f"Handing {who} {amount}", "based_on": [c["title"]]}


def _fine(f, span):
    """This is fine: the day's pile of launches."""
    n = len(f["launches"])
    if n < (4 if span == "today" else 15):
        return None
    return {"format": "fine", "caption": f"{n} new AI models and tools {span}",
            "under": _v(f, ["Me, still trying out last week's", "My prompts, written for the old ones",
                            "Developers, halfway through a migration", "My carefully tuned set-up"]), "based_on": []}


def _brain(f, span):
    """The expanding brain: the day's pile of papers, and what becomes of them."""
    n = f["papers"]
    if n < (5 if span == "today" else 20):
        return None
    return {"format": "brain", "rows": _v(f, [
        ["Reading the paper", "Reading the abstract", "Reading the title", f"Citing all {n} AI papers out {span} anyway"],
        ["One good AI paper", "Ten good AI papers", f"{n} AI papers out {span}", "Every one of them state of the art"],
        ["Running the code", "Trusting the chart", "Trusting the title", f"Saving all {n} AI papers out {span} for later"],
        ["A new method", "A new benchmark", "A new benchmark for the method", f"{n} AI papers out {span}, all beating it"]]),
        "based_on": []}


def _yelling(f, span):
    """Yelling at the cat at the dinner table: the power grid and the data centres."""
    if not f["power"]:
        return None
    return {"format": "yelling", "labels": _v(f, [
        ["Every power grid in 2026", "“I just need one more data centre.”"],
        ["Every power company", "“Just one more gigawatt, I promise.”"],
        ["Every town near a data centre", "“I'll be quiet, it's only a few fans.”"],
        ["Every electricity bill", "“Training runs aren't cheap, you know.”"]]),
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
    who = _v(f, ["Every launch", "Every press release", "Every demo", "Every keynote"])
    return {"format": "pigeon", "labels": [f"{who} {span}", MISNAMED[term]], "caption": f"Is this {article} {term}?",
            "based_on": []}


def _panik(f, span):
    """Panik / kalm / panik: a launch, then what it means for you."""
    if not f["named"]:
        return None
    maker, product, c = f["named"][-1]
    kalm, panik = _v(f, [("Your code still works", "Your boss saw the demo"),
                         ("It's only a preview", "Your team wants to switch tonight"),
                         ("Your prompts still work", "They were written for the old model"),
                         ("You don't have to switch", "Your rival already did")])
    return {"format": "panik", "rows": [("Panik", f"{maker} launches {product}"), ("Kalm", kalm), ("Panik", panik)],
            "based_on": [c["title"]]}


FORMATS = [_distracted, _buttons, _nope_yep, _fine, _brain, _yelling, _pigeon, _panik]
GENERATED: dict = {}  # ("day" | "week", date) -> a meme Gemini wrote (memegen.prepare); used instead of the rules


# The day's template, by the date, in this order: each comes back only every 8 days, never within 5, the same for
# a dry run and the morning's send (wide and tall ones alternate)
ROTATION = ["distracted", "buttons", "fine", "nopeyep", "yelling", "brain", "pigeon", "panik"]


# A day's template when its stories can't fill it (and Gemini wrote nothing): a joke about the AI industry's habits
# (launches, naming, benchmarks, GPUs), with no names or numbers, so there's nothing in it to get wrong. Never about
# reading or keeping up with the news: that's a plug for us (owner, 2026-11-06). Several of each, taken in turn, so a
# template that comes back brings a new joke (owner: "do variations, otherwise the memes get boring", 2026-11-06)
STANDBY = {
    "distracted": [{"labels": ["Whatever just launched", "Developers", "The model they set up last week"]},
                   {"labels": ["A brand-new benchmark", "AI labs", "The benchmark they topped last month"]},
                   {"labels": ["The next funding round", "AI start-ups", "The product from the last one"]},
                   {"labels": ["A bigger context window", "Model makers", "Getting the answer right"]}],
    "buttons": [{"labels": ["Wait for the benchmarks", "Ship it on launch day"], "caption": "Every team after a new model drops"},
                {"labels": ["Call it open source", "Share the training data"], "caption": "Every AI lab with new weights"},
                {"labels": ["Make it bigger", "Make it cheaper"], "caption": "Every AI lab at planning time"},
                {"labels": ["Fix the bug yourself", "Ask the AI to fix it"], "caption": "Developers at 5pm on a Friday"}],
    "fine": [{"caption": "A new AI model every morning", "under": "My prompts, written for last week's"},
             {"caption": "The GPU waiting list", "under": "AI start-ups, launching next month for sure"},
             {"caption": "Every benchmark beaten by lunchtime", "under": "The people who made the benchmark"},
             {"caption": "The AI power bill", "under": "Every data centre, adding one more rack"}],
    "nopeyep": [{"who": "AI companies", "nope": "Calling it version 2", "yep": "Calling it a new era"},
                {"who": "AI labs", "nope": "One clear model name", "yep": "Pro Max Ultra Preview Turbo"},
                {"who": "AI start-ups", "nope": "Making money", "yep": "Raising money"},
                {"who": "Developers", "nope": "Writing the tests", "yep": "Asking the AI if it works"}],
    "yelling": [{"labels": ["Every AI budget", "“I just need one more GPU.”"]},
                {"labels": ["Developers asking for a short answer", "“Great question! Let's dive in.”"]},
                {"labels": ["Every benchmark maker", "“I've seen this test before.”"]},
                {"labels": ["Every power grid", "“I just need one more data centre.”"]}],
    "brain": [{"rows": ["Calling it an update", "Calling it a new model", "Calling it a breakthrough", "Calling it a new era"]},
              {"rows": ["Asking the chatbot", "Asking it to think step by step", "Asking it to check its work",
                        "Asking it to ask another chatbot"]},
              {"rows": ["A chatbot", "A chatbot with tools", "A chatbot with a browser", "An AI agent with a launch video"]},
              {"rows": ["Training a model", "Training a bigger model", "Training a model to train models",
                        "Calling the result AGI"]}],
    "pigeon": [{"labels": ["Every app update", "a chatbot in a sidebar"], "caption": "Is this an AI agent?"},
               {"labels": ["Every launch video", "a chatbot that can do maths"], "caption": "Is this AGI?"},
               {"labels": ["Every press release", "a model with a download button"], "caption": "Is this open source?"},
               {"labels": ["Every laptop advert", "your laptop getting warm"], "caption": "Is this on-device AI?"}],
    "panik": [{"rows": [("Panik", "A new model drops overnight"), ("Kalm", "Your code still works"),
                        ("Panik", "Your boss saw the demo")]},
              {"rows": [("Panik", "The GPU order is late"), ("Kalm", "The cloud has GPUs"), ("Panik", "The cloud bill arrived")]},
              {"rows": [("Panik", "The model gave a wrong answer"), ("Kalm", "It said sorry"),
                        ("Panik", "It gave the same answer again")]},
              {"rows": [("Panik", "A rival tops the benchmark"), ("Kalm", "Benchmarks don't mean much"),
                        ("Panik", "Your investors saw the benchmark")]}],
}


def _turn(when: date, days: int = 8) -> int:
    """Which wording: the next each time a template comes back (every 8 days; the Sunday meme every 28)."""
    return when.toordinal() // days


def _made(want: str, f: dict, span: str, have: bool) -> dict | None:
    """The template's rule-based meme from the stories, else its standby wording of this turn (none without stories)."""
    made = next((m for g in FORMATS if (m := g(f, span)) and m["format"] == want), None)
    return made or ({"format": want, **_v(f, STANDBY[want]), "based_on": []} if have else None)


def template_of(day: date) -> str:
    return ROTATION[day.toordinal() % len(ROTATION)]


# The Sunday email's meme of the week takes only the wide templates, the next each Monday (the site's tile takes all
# of ROTATION, a new one each day: of_the_7_days)
WEEK_ROTATION = ["distracted", "fine", "yelling", "pigeon"]


def template_of_week(monday: date) -> str:
    """The meme of the week's template: the next in WEEK_ROTATION each week, so the site's meme changes every Monday."""
    return WEEK_ROTATION[(monday.toordinal() // 7 + 3) % len(WEEK_ROTATION)]  # set so 21 Sep 2026's week keeps its meme (distracted)


def template_of_7_days(today: date) -> str:
    """The site's meme of the week's template: the next in ROTATION each day, so no format comes back within a week
    (owner, 2026-11-06); set so 6 Nov 2026 keeps its meme (yelling). Tall ones shrink to the tile; a click opens them."""
    return ROTATION[(today.toordinal() + 6) % len(ROTATION)]


def last_7_days(cards: list[dict], today: date) -> list[dict]:
    """The stories of today and the 6 days before."""
    return [c for c in cards if (today - timedelta(days=6)).isoformat() <= (c.get("date") or "") <= today.isoformat()]


def of_the_day(cards: list[dict], day: date) -> dict | None:
    """The day's meme, from that day's stories (the same for every reader), on the day's template (none if the
    stories can't fill it)."""
    made, want = GENERATED.get(("day", day)), template_of(day)
    if not (made and made.get("format") == want):
        f = {**facts([c for c in cards if c.get("date") == day.isoformat()]), "turn": _turn(day)}
        made = _made(want, f, "today", day.isoformat() in {c.get("date") for c in cards})
    return made and {**made, "title": "Meme of the day"}


def of_the_week(cards: list[dict], monday: date) -> dict | None:
    """The meme of the week from Monday to Sunday's stories."""
    week = [c for c in cards if monday.isoformat() <= (c.get("date") or "") < (monday + timedelta(days=7)).isoformat()]
    made, want = GENERATED.get(("week", monday)), template_of_week(monday)
    if not (made and made.get("format") == want):
        made = _made(want, {**facts(week), "turn": _turn(monday, 28)}, "this week", bool(week))
    return made and {**made, "title": "Meme of the week"}


def of_the_7_days(cards: list[dict], today: date) -> dict | None:
    """The site's meme of the week, from the past 7 days' stories (today and the 6 days before): a new one each day."""
    week = last_7_days(cards, today)
    made, want = GENERATED.get(("7days", today)), template_of_7_days(today)
    if not (made and made.get("format") == want):
        made = _made(want, {**facts(week), "turn": _turn(today + timedelta(days=6))}, "this week", bool(week))
    return made and {**made, "title": "Meme of the week"}


def payload(cards: list[dict], today: date | None = None) -> dict:
    """meme.json for the front page: the past 7 days' meme (today and the 6 days before, UTC, as the word of the
    week). It changes every day. Its picture is made by the build (memes/7days-<today>.jpg)."""
    today = today or date.today()
    meme = of_the_7_days(cards, today)
    image = f"memes/7days-{today.isoformat()}.jpg"  # the finished picture, written by the build (static.py)
    ok = bool(meme and render(meme))
    # the news behind it, linked to the stories themselves (a meme made from the week's words has none)
    week = {c["title"]: c for c in last_7_days(cards, today)}
    behind = [{"title": t, "url": week[t]["url"], "source": week[t].get("source") or ""}
              for t in (meme or {}).get("based_on") or [] if t in week and week[t].get("url")][:3]
    return {"from": (today - timedelta(days=6)).isoformat(), "to": today.isoformat(),
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


def html(meme: dict, src: str, small: bool = False) -> str:
    """The finished picture (src: its address, or "cid:..." for the copy inside an email), its words as the alt
    text, and the template's source as its credit (who wrote the captions is in the README, not shown to readers). `small`: the email's size,
    so the meme never fills a phone's screen."""
    credit = "via imgflip.com"  # the source, not the template's name
    alt = " ".join(text(meme)[1:])
    width = (340 if small else 420) if meme["format"] in TALL else (460 if small else 600)  # a tall template stays short enough to read without scrolling
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
