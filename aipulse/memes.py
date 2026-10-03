"""Meme of the day (in the daily email) and meme of the week (on the front page), made without any AI model.

Each meme is a cartoon of ours (meme_art.py: a techie, two women and a robot, saved as PNGs in templates/memes/)
posed in the layout of a well-known meme format (nope/yep, the distracted look back, "this is fine", two buttons,
the expanding brain, yelling at the cat, "is this a...?", panik/kalm), with captions filled from our own data: the
day's or week's launches, raises, papers, power stories and glossary words, named as the headlines name them. No
meme photo, film still or real person's likeness is used, only the idea of each layout. Jokes are light: about the AI
industry's habits, never a person; politics and any story about harm, death, crime, lawsuits, layoffs, war or
children are never used. A format is picked by the date from those the stories can fill, so the same day always
gives the same meme. The meme of the week is last week's (Monday to Sunday), so it changes every Monday.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from html import escape

from . import glossary, rss

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
    every Monday. Its pictures are the site's own (memes/...)."""
    today = today or date.today()
    monday = today - timedelta(days=today.weekday() + 7)
    meme = of_the_week(cards, monday)
    return {"from": monday.isoformat(), "to": (monday + timedelta(days=6)).isoformat(),
            "html": html(meme, base="") if meme else "", "format": meme["format"] if meme else None}


# ---------- Laid out in tables that work in email and on the site; the cartoons are PNGs on the site ----------

CAP = "font-family:'Arial Black',Arial,Helvetica,sans-serif;font-weight:900;color:#1d2433"


def _img(base: str, name: str, width: int, alt: str) -> str:
    return (f'<img src="{escape(base)}memes/{name}.png" width="{width}" alt="{escape(alt)}" '
            f'style="display:block;width:100%;max-width:{width}px;height:auto;border:0">')


def _cells(labels: list[str], size: int = 14) -> str:
    w = 100 // len(labels)
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="table-layout:fixed"><tr>'
            + "".join(f'<td width="{w}%" align="center" valign="top" style="{CAP};font-size:{size}px;line-height:1.25;padding:8px 6px">'
                      f'{escape(l)}</td>' for l in labels) + '</tr></table>')


def _rows(rows: list[tuple[str, str]], width: int) -> str:
    """Text on the left, a picture on the right, one row each (nope/yep, the brain, panik/kalm)."""
    return ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            + "".join(f'<tr><td valign="middle" style="{CAP};font-size:16px;line-height:1.3;padding:8px 14px 8px 4px;'
                      f'border-bottom:2px solid #1d2433">{t}</td>'
                      f'<td width="{width}" valign="middle" style="border-bottom:2px solid #1d2433;border-left:2px solid #1d2433">{i}</td></tr>'
                      for t, i in rows) + '</table>')


def html(meme: dict, base: str = rss.SITE) -> str:
    f = meme["format"]
    if f == "distracted":
        body = _img(base, "distracted", 600, "A techie turns to stare at a shiny robot while his partner glares") + _cells(
            [meme["labels"][0], meme["labels"][1], meme["labels"][2]])
    elif f == "buttons":
        body = (_cells(meme["labels"], 15) + _img(base, "buttons", 600, "Two big red buttons and a sweating techie")
                + _cells([meme["caption"]], 16))
    elif f == "nopeyep":
        body = (_cells([meme["who"]], 15)
                + _rows([(escape(meme["nope"]), _img(base, "nope", 150, "Nope")), (escape(meme["yep"]), _img(base, "yep", 150, "Yep"))], 150))
    elif f == "fine":
        body = _cells([meme["caption"]], 17) + _img(base, "fine", 600, "A techie at a desk in a burning room says “This is fine.”") \
            + _cells([meme["under"]], 15)
    elif f == "brain":
        body = _rows([(escape(t), _img(base, f"brain{i}", 140, f"Brain, level {i}")) for i, t in enumerate(meme["rows"], 1)], 140)
    elif f == "yelling":
        body = _img(base, "yelling", 600, "A woman yells and points at a confused robot at a dinner table") + _cells(meme["labels"])
    elif f == "pigeon":
        body = (_img(base, "pigeon", 600, "A techie points at a butterfly") + _cells(meme["labels"])
                + _cells([meme["caption"]], 20))
    elif f == "panik":
        body = _rows([(f'<span style="font-size:20px">{escape(k.upper())}</span><br><span style="font-size:14px">{escape(t)}</span>',
                       _img(base, "kalm" if k == "Kalm" else "panik", 140, k)) for k, t in meme["rows"]], 140)
    else:
        return ""
    if meme.get("by") == "gemini":  # said plainly: the words came from an AI model, the drawing is ours
        body += ('<div style="font-size:11px;color:#5f6368;padding:4px 8px 6px;text-align:right">'
                 'Captions written with Gemini · drawing by AI Pulse</div>')
    return (f'<div style="max-width:600px;background:#ffffff;border:2px solid #1d2433;border-radius:6px;overflow:hidden;'
            f'font-family:Arial,Helvetica,sans-serif;color:#1d2433">{body}</div>')


def text(meme: dict) -> list[str]:
    """The meme in the plain-text email: the cartoon described, then its captions."""
    f = meme["format"]
    out = [meme["title"].upper() + ":"]
    if f == "distracted":
        new, who, old = meme["labels"]
        out.append(f"{who}, turning to stare at {new}, while {old} glares.")
    elif f == "buttons":
        out += [f"Two buttons: “{meme['labels'][0]}” or “{meme['labels'][1]}”.", f"Sweating: {meme['caption']}."]
    elif f == "nopeyep":
        out += [meme["who"] + ":", f"  Nope: {meme['nope']}", f"  Yep: {meme['yep']}"]
    elif f == "fine":
        out += [meme["caption"] + ".", f"{meme['under']}: “This is fine.”"]
    elif f == "brain":
        out += [f"  {'🧠' * i} {t}" for i, t in enumerate(meme["rows"], 1)]
    elif f == "yelling":
        out.append(f"{meme['labels'][0]}, yelling at a robot at the dinner table: {meme['labels'][1]}")
    elif f == "pigeon":
        out += [f"{meme['labels'][0]}, pointing at {meme['labels'][1]}:", meme["caption"]]
    elif f == "panik":
        out += [f"  {k.upper()}: {t}" for k, t in meme["rows"]]
    return out
