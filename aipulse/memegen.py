"""Meme captions written by Google's Gemini on its free tier: the one place AI Pulse uses an AI model, by the
project owner's choice (2026-10-03). Nothing else (summaries, sorting, the tracker) uses it.

Gemini sees only public data, the period's headlines, and picks one of our drawn templates (memes.py, meme_art.py)
and writes its captions. It draws nothing: the pictures stay ours. Its answer must pass every check here (a known
template, short lines, no harm/politics/crime words, no real person named unless a headline names them, every number
taken from a headline) or the rule-based meme is used instead. No key, no network, a quota limit or a bad answer all
fall back the same way, so the email and the site never wait on it.

A meme is made once per period and kept in the database (meta "meme:week:<monday>", "meme:day:<date>"), so the site's
meme of the week doesn't change at each build and Gemini is asked about twice a week plus once a day.

Key: GEMINI_API_KEY (environment; never printed or logged). Use a key from a Google AI Studio project with no billing
account, so nothing can ever be billed. GEMINI_MODEL picks the model (default below).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import date, timedelta

from . import memes

MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")  # always Google's newest Flash model
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX = 72  # characters a caption may have

# What each of our drawn templates means, for the prompt; the fields Gemini fills
TEMPLATES = {
    "distracted": ('The "distracted boyfriend": a techie turns to stare at a shiny robot while his partner glares.',
                   {"labels": "3 captions: [the shiny new thing, who is distracted, what they already had]"}),
    "buttons": ('"Two buttons": a sweating techie can\'t choose between two red buttons.',
                {"labels": "2 captions, one per button", "caption": "who is sweating"}),
    "nopeyep": ('Drake-style "nope / yep": a techie rejects one thing and happily points at another.',
                {"who": "whose choice this is", "nope": "what they reject", "yep": "what they prefer"}),
    "fine": ('"This is fine": a techie calmly drinks coffee in a burning server room.',
             {"caption": "the situation, on top", "under": "who says “This is fine.”, underneath"}),
    "brain": ('"Expanding brain": four rows, each idea more "enlightened" (and more absurd) than the last.',
              {"rows": "4 captions, from plain to galaxy-brained"}),
    "yelling": ('"Woman yelling at cat": a woman points and yells; a confused robot sits at a dinner table.',
                {"labels": "2 captions: [the one yelling (often with their words), the robot's calm reply in quotes]"}),
    "pigeon": ('"Is this a pigeon?": a techie points at a butterfly and names it wrongly.',
               {"labels": "2 captions: [who points, what they point at]", "caption": "the question: Is this ...?"}),
    "panik": ('"Panik / Kalm / Panik": three rows of a techie panicking, calm, panicking again.',
              {"rows": "3 pairs [[\"Panik\", line], [\"Kalm\", line], [\"Panik\", line]]"}),
}

# Never in a caption, whatever the headline: politics and politicians (on top of memes' harm and crime words)
_POLITICS = re.compile(r"\b(?:trump|biden|harris|obama|vance|musk|putin|xi|modi|starmer|macron|president|prime minister|"
                       r"senat\w*|congress\w*|parliament\w*|minister\w*|election\w*|vote\w*|democrat\w*|republican\w*|"
                       r"party|parties|government\w*|white house|kremlin|beijing|tariff\w*)\b", re.I)


# The owner's own two asks, word for word, then how to answer (2026-10-03)
ASK = {"day": "Create a funny meme out of this current AI news for today.",
       "week": "Analyse these weekly AI updates and create a meme for the week for our readers."}


def _prompt(stories: list[dict], span: str) -> str:
    lines = "\n".join(f"{i}. {c['title']} ({c.get('source') or ''})" for i, c in enumerate(stories))
    kinds = "\n".join(f'- "{k}": {d} Fields: ' + "; ".join(f"{f}: {h}" for f, h in fields.items())
                      for k, (d, fields) in TEMPLATES.items())
    return f"""{ASK[span]}

The {"news for today" if span == "day" else "weekly AI updates"} (real headlines, numbered):
{lines}

Our readers are engineers, researchers and curious people worldwide who read AI Pulse, a free AI news briefing.
Use cartoon, caricatures and colourful presentation: the meme is drawn as a bright, colourful cartoon by our artist,
with a cast of caricatures (a techie in a hoodie, a woman, a friendly robot) acting out the joke. Your part is the
idea and the words: pick the cartoon below that fits the joke best and write its captions so the scene is instantly
funny. Think like the best meme pages: one sharp, specific observation; the punchline last; the kind of joke people
forward to their team. Prefer the most talked-about story.

The cartoons:
{kinds}

Rules (a meme that breaks one is thrown away):
- Don't make dark jokes and do not insult anyone. Laugh with the industry's habits (hype, launch days, naming,
  benchmarks, funding rounds, jargon, the reader keeping up), never at a person, company staff or group.
- Caricatures are of our cartoon cast only: never name, describe or draw a real person.
- Leave out AI safety, risk, deception, politics, governments, elections, war, crime, lawsuits, layoffs, health,
  death, children and religion entirely, even if a headline is about them.
- Do not invent facts: every number and every company or product you use must appear in the headlines above.
- Each caption at most {MAX} characters. Plain text, no emoji, no hashtags.
- "based_on": the numbers of the headlines the joke is about (1 to 3).

Write 3 different candidate memes, the funniest first. Answer with JSON only:
{{"memes": [{{"format": "...", "based_on": [0], ...the cartoon's fields...}}, ...]}}"""


# The next free Flash models, each with its own free allowance (20 requests a day, 5 a minute): used when the one
# before is busy (503) or out of allowance (429). Pro and image models have no free tier, so they are never used.
FALLBACKS = ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]


def _ask(prompt: str, key: str, timeout: int = 120) -> str:
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"temperature": 1.0, "responseMimeType": "application/json",
                                            "thinkingConfig": {"thinkingLevel": "high"}}}).encode()
    models = [MODEL] + [m for m in FALLBACKS if m != MODEL]
    for i, model in enumerate(models):
        req = urllib.request.Request(API.format(model=model), data=body, method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": key})  # key in a header, not the URL
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < len(models) - 1:  # busy or out of allowance: the next model
                continue
            raise
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return text[text.find("{"):text.rfind("}") + 1]  # the JSON, without any fence around it


def _clean(t) -> str | None:
    if not isinstance(t, str):
        return None
    t = " ".join(t.split()).strip()
    return t if 0 < len(t) <= MAX else None


def check(m: dict, stories: list[dict]) -> dict | None:
    """The meme in memes.py's shape, or None if it breaks a rule."""
    f = m.get("format")
    if f not in TEMPLATES:
        return None
    based = [i for i in m.get("based_on") or [] if isinstance(i, int) and 0 <= i < len(stories)][:3]
    if not based:
        return None
    out = {"format": f, "based_on": [stories[i]["title"] for i in based]}
    try:
        if f == "nopeyep":
            out.update(who=_clean(m["who"]), nope=_clean(m["nope"]), yep=_clean(m["yep"]))
        elif f in ("distracted", "yelling"):
            n = 3 if f == "distracted" else 2
            out["labels"] = [_clean(x) for x in m["labels"]][:n]
            if len(out["labels"]) != n:
                return None
        elif f in ("buttons", "pigeon"):
            out["labels"] = [_clean(x) for x in m["labels"]][:2]
            out["caption"] = _clean(m["caption"])
            if len(out["labels"]) != 2:
                return None
        elif f == "fine":
            out.update(caption=_clean(m["caption"]), under=_clean(m["under"]))
        elif f == "brain":
            out["rows"] = [_clean(x) for x in m["rows"]]
            if len(out["rows"]) != 4:
                return None
        elif f == "panik":
            rows = [(k, _clean(t)) for k, t in m["rows"]]
            if [k for k, _ in rows] != ["Panik", "Kalm", "Panik"]:
                return None
            out["rows"] = rows
    except (KeyError, TypeError, ValueError):
        return None
    texts = []
    for k, v in out.items():
        if k not in ("format", "based_on"):
            for x in v if isinstance(v, list) else [v]:
                texts += list(x) if isinstance(x, tuple) else [x]
    if None in texts:  # a caption missing, empty or too long
        return None
    source = " ".join(f"{c['title']} {c.get('summary') or ''}" for c in stories)
    for t in texts:
        if memes._SERIOUS.search(t) or _POLITICS.search(t) or re.search(r"https?://|www\.|@|#", t):
            return None
        for num in re.findall(r"\d[\d.,]*", t):  # every number comes from a headline
            if num.rstrip(".,") not in source:
                return None
    return out


def write(cards: list[dict], span: str, key: str | None = None, ask=None) -> dict | None:
    """A Gemini meme for these stories, checked, or None (no key, no light stories, an error or no candidate passed)."""
    key = key or os.environ.get("GEMINI_API_KEY")
    stories = sorted([c for c in cards if memes.light(c)], key=lambda c: -len(c.get("also") or []))[:30]
    if not key or len(stories) < 3:
        return None
    try:
        answer = json.loads((ask or _ask)(_prompt(stories, span), key))
    except Exception as e:  # network, quota, a malformed answer: the rule-based meme is used
        print(f"Gemini meme skipped: {type(e).__name__} {getattr(e, 'code', '')}".rstrip())
        return None
    for m in (answer.get("memes") if isinstance(answer, dict) else None) or []:
        if isinstance(m, dict) and (ok := check(m, stories)):
            return {**ok, "by": "gemini"}
    print("Gemini meme skipped: no candidate passed the checks")
    return None


def stored(conn, kind: str, when: date, cards: list[dict], make: bool) -> dict | None:
    """The period's Gemini meme from the database; with make, ask Gemini once and keep its answer (or that it failed)."""
    k = f"meme:{kind}:{when.isoformat()}"
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (k,)).fetchone()
    if row:
        return json.loads(row[0]) or None
    if not make:
        return None
    if kind == "week":
        period = [c for c in cards if when.isoformat() <= (c.get("date") or "") < (when + timedelta(days=7)).isoformat()]
    else:
        period = [c for c in cards if c.get("date") == when.isoformat()]
    meme = write(period, "week" if kind == "week" else "day")
    if meme or os.environ.get("GEMINI_API_KEY"):  # keep a failure too, so a bad day isn't retried at every build
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (k, json.dumps(meme)))
        conn.commit()
    return meme


def prepare(conn, cards: list[dict], today: date | None = None, day: date | None = None, make: bool = False) -> None:
    """Put last week's (and with day, that day's) Gemini meme where memes.py finds it. Without make, only what the
    database already holds (the site's build); with make, Gemini is asked for what's missing."""
    today = today or date.today()
    monday = today - timedelta(days=today.weekday() + 7)
    if (m := stored(conn, "week", monday, cards, make)):
        memes.GENERATED[("week", monday)] = m
    if day and (m := stored(conn, "day", day, cards, make)):
        memes.GENERATED[("day", day)] = m
