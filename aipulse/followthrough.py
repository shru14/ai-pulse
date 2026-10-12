"""Follow-through (follow-through/): two experiments on one page, for the owner's review. The page isn't linked from
the site or listed in the sitemap.

Rule echoes: the Regulation tracker's official records grouped by subject (sexual deepfakes, AI companions,
labelling...). Each subject lists the places that took it up, in the order they first did, and the furthest any of
their records got (proposed, passed, adopted). A subject in common is not a claim that one place copied another. The
grouping reads only each record's title and its official description, where the source gives one.

Promised vs shipped: headlines in which a company says it will release something ("OpenAI plans to launch its GPT
Store next week"), each matched to a later headline saying it did ("OpenAI launches GPT Store"). The company must be
the subject of both headlines, and every name the promise gives ("GPT", "Store") must be in the launch's headline. A
promise with no launch found is "Not found yet", never "broken": a launch may have been reported in words we don't
match. FIXES corrects the matcher by hand. Headlines are the outlets' own, so the promises load in the reader's browser
from promises.json, as the topics' timelines do; the page itself holds only our own words and official titles.
"""
from __future__ import annotations

import bisect
import json
import re
import shutil
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import classify, cluster, countries, jurisdictions, pages, rss
from .bills import OFFICIAL_SOURCES

PATH = "follow-through/"

# ---- Rule echoes -------------------------------------------------------------------------------------------------

MIN_PLACES = 2  # a subject only one place has taken up has no echo yet

# slug: name, what (our own words), words (in the record's title or description)
THEMES = {
    "sexual-deepfakes": dict(
        name="Sexual deepfakes",
        what="Making or sharing sexual images of real people made with AI.",
        words=r"deepfake\w*.{0,60}\b(sexual\w*|intimate|porn\w*|nud\w*)|\b(sexual\w*|intimate|porn\w*|nud\w*)\b.{0,80}"
              r"(deepfake|false video|synthetic|generated|digital(ly)? (manipulat|alter)\w*|artificial intelligence)"
              r"|undress\w*|non-?consensual intimate"),
    "deepfakes": dict(
        name="Deepfakes and digital likeness",
        what="Fakes of a real person's face or voice, and rights over one's own likeness.",
        words=r"deepfake|digital (replica|imitation|likeness)|realistic digital imitation|voice clon\w*|\blikeness\b"
              r"|image, voice"),
    "companions": dict(
        name="AI companions and chatbots",
        what="Rules for chatbots and AI companions that talk with people as a person would.",
        words=r"\bcompanion\w*|chatbot\w*|human-like interactive|conversational (AI|agent|artificial)"),
    "children": dict(
        name="Children and AI",
        what="Protecting children and teenagers from AI products and AI-made abuse.",
        words=r"\b(child|children|minors?|teen\w*|kids|adolescen\w*|youth)\b"),
    "labelling": dict(
        name="Labelling AI-made content",
        what="Marking text, images, audio and video made by AI so people can tell.",
        words=r"\blabel\w*|watermark\w*|provenance|synthetic content|disclos\w*.{0,60}(AI|artificial intelligence|generated"
              r"|synthetic)|(AI|artificial intelligence)[- ]generated content.{0,40}(identif|inform|notice)\w*"),
    "framework": dict(
        name="A general AI law",
        what="One law setting the ground rules for AI across a whole country or bloc.",
        words=r"\bArtificial Intelligence Act\b(?! of)|\bAI Act\b|\bLaw on Artificial Intelligence\b"
              r"|\bBasic (Act|Law) on (the Development of )?(AI|Artificial Intelligence)\b|\bAI Basic Act\b"
              r"|\bFramework Act on the Development of AI\b|\bRegulation of Artificial Intelligence\b"
              r"|\bRegulating Artificial Intelligence\b|\bArtificial Intelligence \(Regulation\)|"
              r"\bRegulation of Artificial Intelligence Systems\b|\bAI Regulatory Authority\b"
              r"|Artificial Intelligence Technology Regulatory Authority|harmonised rules on artificial intelligence"),
    "safety-institutes": dict(
        name="AI safety institutes",
        what="Public bodies that test the most capable AI models for risks.",
        words=r"\b(AI|Artificial Intelligence) (Safety|Security) Institute\b|\bAISI\b|\bEU AI Office\b"),
    "work": dict(
        name="AI at work",
        what="Workers' rights when employers use AI to hire, watch or manage them.",
        words=r"\b(workers?|employees?|employment|workplace|labou?r|hiring|job applicants?)\b"),
    "public-sector": dict(
        name="Government's own use of AI",
        what="How public bodies may use AI and algorithms, and what they must tell people.",
        words=r"\bpublic (authorit\w*|administration|sector|bodies)|\bfederal (agenc\w*|administration|government)"
              r"|government use|algorithms? used in administration|AI- and Data-Based Public Administration"),
    "bias": dict(
        name="Bias and automated decisions",
        what="Discrimination by AI systems, and rights over decisions a machine makes.",
        words=r"discriminat\w*|\bbias\w*|automated decision|algorithmic (accountability|fairness|discrimination)"
              r"|impact assessment"),
    "copyright": dict(
        name="Copyright and AI training",
        what="Whether AI may learn from protected works, and what creators are owed.",
        words=r"copyright|intellectual property|\bauthors?\b.{0,60}(content|works?)|training data|text and data mining"
              r"|computational data analysis|Law No\.? 9,610"),
    "health": dict(
        name="AI in health care",
        what="AI in diagnosis, treatment and medical devices.",
        words=r"\b(health|healthcare|medical|clinical|patients?|hospitals?|medicine)\b"),
    "elections": dict(
        name="Elections",
        what="AI in election campaigns and political advertising.",
        words=r"\belection\w*|electoral|political (ad|advert)\w*|\bcandidates?\b|\bvoters?\b"),
    "education": dict(
        name="AI in schools",
        what="AI in classrooms, homework and exams.",
        words=r"\bschools?\b|\bstudents?\b|\bteachers?\b|cheating"),
    "data-centres": dict(
        name="Data centres and compute",
        what="Building and powering the data centres and computing that AI runs on.",
        words=r"data cent(er|re)s?|\bcompute\b|computing (infrastructure|capacity)|\bCloud and AI\b|energy grid"),
    "surveillance": dict(
        name="Facial recognition and surveillance",
        what="Recognising faces and bodies, and watching people with AI.",
        words=r"facial recognition|biometric\w*|surveillance|body-borne|hidden monitoring|smart glasses"),
    "security": dict(
        name="Security, defence and crime",
        what="AI in the military, policing and national security, and AI used for crime.",
        words=r"\bmilitary\b|\bdefen[cs]e\b|national security|terroris\w*|\bweapons?\b|public security|\bpolic(e|ing)\b"),
    "agents": dict(
        name="AI agents",
        what="AI that acts on its own: booking, buying and working for people.",
        words=r"\bAI agents?\b|\bagentic\b"),
}
_THEME_RE = {slug: re.compile(t["words"], re.I) for slug, t in THEMES.items()}
# The tracker also keeps privacy and data laws; a subject counts only records that are about AI.
_ABOUT_AI = re.compile(r"\b(AI|artificial intelligence|algorithm\w*|automated|deepfake\w*|synthetic|machine learning"
                       r"|chatbot\w*|generated|intelligent systems?)\b", re.I)


def themes_of(card: dict) -> list[str]:
    """The subjects an official record is about, from its title and its official description."""
    text = f"{card['title']} {classify._TRANSLATED.sub('', card.get('summary') or '')}"
    if not _ABOUT_AI.search(text):
        return []
    return [slug for slug, rx in _THEME_RE.items() if rx.search(text)]


# How far a record got, for each place's furthest: (rank, words)
def _reached(card: dict) -> tuple[int, str]:
    life = card.get("lifecycle")
    if life:
        stage = life.get("current") or ""
        if stage in ("signed", "in_force"):
            return 4, "Adopted"
        if stage in ("vetoed", "withdrawn"):
            return 0, stage.capitalize()
        if stage in ("passed_chamber", "passed_legislature"):
            return (3, "Passed") if stage == "passed_legislature" else (2, "Passed one chamber")
        return 1, "Proposed"
    return {"law": (4, "Adopted"), "body": (4, "Set up"), "standard": (4, "Published")}.get(card.get("action") or "",
                                                                                         (1, "Proposed"))


def _started(card: dict) -> str:
    """When the record first appeared: a bill's introduction, else its own date."""
    steps = [s["date"] for s in (card.get("lifecycle") or {}).get("steps", []) if s.get("date")]
    return min(steps) if steps else card["date"]


def _when(card: dict, iso: str) -> str:
    # OECD.AI gives only the year, stored as 1 January
    d = date.fromisoformat(iso[:10])
    return str(d.year) if card["source"] == "OECD.AI" and iso.endswith("-01-01") else f"{d:%b %Y}"


def echoes(cards: list[dict]) -> list[dict]:
    """Each subject with MIN_PLACES places or more, most places first: its places in the order they first took it up,
    each with its records and the furthest one got."""
    names = {code: m["name"] for code, m in jurisdictions.meta().items()}
    found: dict[str, dict[str, list[dict]]] = {}
    for c in cards:
        if c["category"] != "regulation" or c["source"] not in OFFICIAL_SOURCES:
            continue
        for slug in themes_of(c):
            for code in {j.split("-")[0] for j in c.get("jurisdictions") or []} & set(names):
                found.setdefault(slug, {}).setdefault(code, []).append(c)
    out = []
    for slug, by_place in found.items():
        if len(by_place) < MIN_PLACES:
            continue
        places = []
        for code, records in by_place.items():
            records.sort(key=_started)
            best = max(records, key=lambda c: _reached(c)[0])
            places.append({"code": code, "name": names[code], "first": records[0], "since": _started(records[0]),
                           "furthest": _reached(best)[1], "rank": _reached(best)[0], "records": records})
        places.sort(key=lambda p: (p["since"], p["name"]))
        latest = max(_started(c) for p in places for c in p["records"])
        out.append({"slug": slug, **THEMES[slug], "places": places, "latest": latest})
    out.sort(key=lambda t: (len(t["places"]), t["latest"]), reverse=True)
    return out


def _echo_html(t: dict) -> str:
    adopted = sum(p["rank"] == 4 for p in t["places"])
    chain = "".join(
        f'<li><img class="flag" src="flags/{countries.flag(p["code"])}" alt=""><span class="pl">{escape(p["name"])}</span>'
        f'<span class="when">{_when(p["first"], p["since"])}</span>'
        f'<span class="rk r{p["rank"]}">{escape(p["furthest"])}</span></li>' for p in t["places"])
    rows = []
    for p in t["places"]:
        for i, c in enumerate(p["records"]):
            rows.append(f'<tr{" class=first" if i == 0 else ""}><td class="when">{_when(c, _started(c))}</td>'
                        f'<td>{escape(p["name"]) if i == 0 else ""}</td>'
                        f'<td><a href="{escape(c["url"])}" rel="noopener">{escape(c["title"].strip())}</a>'
                        f'<div class="meta">{escape(c["source"])}</div></td><td>{escape(_reached(c)[1])}</td></tr>')
    n = sum(len(p["records"]) for p in t["places"])
    first = t["places"][0]
    return (f'<section class="echo" id="{t["slug"]}"><h3>{escape(t["name"])}</h3>\n'
            f'<p class="what">{escape(t["what"])} <span class="meta">{len(t["places"])} places; the first on the tracker, '
            f'{escape(countries.place(first["name"]))} in {_when(first["first"], first["since"])}'
            f'{f"; adopted or set up in {adopted}" if adopted else ""}.</span></p>\n'
            f'<ol class="chain">{chain}</ol>\n'
            f'<details><summary>The {n} official record{"s" * (n != 1)}</summary><table class="mt">'
            f'<thead><tr><th>Since</th><th>Place</th><th>Record</th><th>Furthest</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></details></section>')


# ---- Promised vs shipped -----------------------------------------------------------------------------------------

SINCE = "2023-01-01"
WINDOW_DAYS = 548  # a launch counts up to 18 months after the promise
RARE_BEFORE = 20  # a name in fewer headlines than this before the promise is the promise's own ("Orion", "Operator")
SUBJECT = 32  # a headline's subject: a company named within its first characters, before the verb

# Hand corrections, by the promise's card id: the launch's URL where the matcher missed one, or None to drop a
# headline that isn't a promise.
FIXES: dict[str, str | None] = {}

_V = (r"(launch|release|ship|roll out|unveil|debut|open[- ]source|introduce|bring|add|offer|start|begin"
      r"|make .{0,30} available)\b")
PROMISE = re.compile(
    r"\b(coming soon|(is|are) coming to|is coming|comes? (later|next)|in the coming (weeks|months)"
    r"|later this (year|month|summer|fall|autumn|spring|winter)|(early|late|by) next year|next (month|week)"
    r"|by (the )?end of (the |this )?year|by year-end|will (soon )?(be )?" + _V
    + r"|(plans?|planning|set|expected|preparing|prepares|poised|gearing up|readies|readying|hopes) to" + _V
    + r"|\bto " + _V + r"|teases)", re.I)
# not a company's promise: predictions, money, people leaving, research write-ups, lists
NOISE = re.compile(
    r"\b(predict\w*|AI is coming for|coming to (Disrupt|TechCrunch|Sessions|SXSW)|Disrupt 20|top \d+|best|vs\.?"
    r"|compar\w+|raises|raised|funding|seed|Series [A-F]|IPO|public offering|valuation|valued|revenue|grow|hire"
    r"|hiring|layoffs?|invest\w*|billion|spend|\$\d|data cent(er|re)|demand|lawsuit|sue|startup|former|ex-\w+"
    r"|researchers?|GPUs|too \w+ to|TechCabal Daily|thinks|talks|ha(s|ve) to|needs? to|ready to|able to|how to"
    r"|why)\b", re.I)
# a verb before the "to ..." makes it a purpose ("Microsoft unveils Copilot to bring AI to ..."), not a promise
DONE = re.compile(
    r"\b(launch(es|ed)|releas(es|ed)|unveil(s|ed)|introduc(es|ed)|debut(s|ed)|announc(es|ed)|partner(s|ed|ing)?"
    r"|teams? up|teamed up|join(s|ed)?|signs?|inks?|taps|uses|used|leaves|left|publishes|nears|eyes|bets|backed"
    r"|deal|rolls out|brings|gives|adds|opens|expands|wants|working|acquires|buys|collaborate\w*|gets|aims?)\b", re.I)
SHIP = re.compile(
    r"\b(launch(es|ed)?|releas(es|ed)|rolls? out|rolled out|rolling out|now available|available (now|today|to|in|for"
    r"|on)|is here|are here|is live|goes live|unveil(s|ed)|debut(s|ed)|introduc(es|ed|ing)|opens?( up)? to|ships?"
    r"|shipped|generally available|general availability|arrives?|out now|brings|open[- ]sources?d?"
    r"|open[- ]sourcing)\b", re.I)
# a launch headline's words after these are about something else ("... powered by Gemini", "... rival to o1")
_ASIDE = re.compile(r"\b(powered by|built on|based on|using|with|rival\w*|response|against|vs\.?|than|like|alongside"
                    r"|after)\b.*", re.I)
_PEOPLE = set("altman sam musk elon cook tim zuckerberg mark jensen huang nadella satya pichai sundar amodei dario "
              "hassabis demis suleyman mustafa".split())
_GENERIC = set("ai new report ceo us uk eu says plans plan next year month week later coming soon early end launch "
               "release model models app apps chip chips tool tools feature features genai generative ai-powered "
               "ai-generated agent agents chatbot assistant llm llms".split()) | _PEOPLE
# a description, not a name ("AI-powered", "Gemini-powered"), and everyday words that name nothing of their own
_DESCRIBES = re.compile(r"ai-\w+|[\w.]+-(powered|based|focused|fueled|optimi[sz]ed|native|enhanced|generated|driven)")
_COMMON = set("tv home health search cloud store music tag app phone mac pc browser glasse speaker car kid teen chat "
              "voice video image photo mode workspace office".split())
_MONTHS = "january february march april may june july august september october november december".split()
_WORD = re.compile(r"[A-Za-z0-9][\w.+\-]*")
_COMPANY_WORDS = {w for c in classify.COMPANY_TERMS for w in c.lower().split()} - {"ai"} | {"deepmind", "aws"}
_PREFIX = re.compile(r"^(Report|Exclusive|Sources?)\s*:\s*")


def _word(w: str) -> str:
    """A headline's word in one form: lower case, no possessive or plural ("Macs" -> "mac")."""
    w = re.sub(r"['’]s$", "", w.lower().strip("."))
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def _words(title: str) -> set[str]:
    return {_word(w) for w in _WORD.findall(title)}


def _owner(word: str) -> str | None:
    return next((c for c, rx in classify._companies.items() if rx.search(word)), None)


def subject(title: str, before: int) -> str | None:
    """The company a headline is about: one named in its first SUBJECT characters, before position `before`."""
    t = _PREFIX.sub("", title)
    end = min(SUBJECT, before - (len(title) - len(t)))
    found = [(m.start(), c) for c, rx in classify._companies.items() if (m := rx.search(t)) and m.start() < end]
    return min(found)[1] if found else None


def names(title: str, company: str) -> set[str]:
    """What the promise names: capitalised words after the first, words with digits ("GPT-5", "A3"), not the
    company's own name, months, years, people or another company's product."""
    t = _PREFIX.sub("", _ASIDE.sub("", title))
    out = set()
    for w in _WORD.findall(t):
        lw = _word(w)
        if (lw in _GENERIC or lw in _MONTHS or lw in cluster._STOP or lw in _COMPANY_WORDS or _DESCRIBES.fullmatch(lw)
                or re.fullmatch(r"(19|20)\d\d", lw) or _owner(w) not in (None, company)):
            continue
        if re.search(r"\d", w) or (w[0].isupper() and not t.startswith(w)) or re.search(r"[a-z][A-Z]", w):
            out.add(lw)
    return out


def due(title: str, d: date) -> date | None:
    """The date the headline gives for the release, read generously (the last day it could mean)."""
    t, y = title.lower(), d.year
    if re.search(r"coming weeks|next week|later this month|this month", t):
        return d + timedelta(days=60)
    if "coming months" in t:
        return d + timedelta(days=183)
    if re.search(r"later this year|this (summer|fall|autumn|winter)|by (the )?end of (the |this )?year|by year-end", t):
        return date(y, 12, 31)
    if "next month" in t:
        return d + timedelta(days=62)
    if "early next year" in t:
        return date(y + 1, 6, 30)
    if "next year" in t:
        return date(y + 1, 12, 31)
    if m := re.search(r"\b(?:by|in) (" + "|".join(_MONTHS) + r")\b", t):
        month = _MONTHS.index(m.group(1)) + 1
        return _month_end(y if month >= d.month else y + 1, month)
    if m := re.search(r"\b(spring|summer|fall|autumn) ((?:19|20)\d\d)", t):
        return _month_end(int(m.group(2)), {"spring": 6, "summer": 9, "fall": 12, "autumn": 12}[m.group(1)])
    if (m := re.search(r"\b(early |late )?((?:19|20)\d\d)\b", t)) and int(m.group(2)) >= y:
        return date(int(m.group(2)), 6, 30) if m.group(1) == "early " else date(int(m.group(2)), 12, 31)
    if m := re.search(r"\bq([1-4])\b|(first|second|third|fourth) quarter", t):
        q = int(m.group(1)) if m.group(1) else ["first", "second", "third", "fourth"].index(m.group(2)) + 1
        return _month_end(y if q >= (d.month - 1) // 3 + 1 else y + 1, q * 3)
    if "coming soon" in t:
        return d + timedelta(days=120)
    return None


def _month_end(y: int, m: int) -> date:
    return (date(y, m, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def promises(cards: list[dict], today: date) -> list[dict]:
    """Every promise found since SINCE, newest first, with the launch found for it (or not) and its status."""
    stories = [s for c in cards if c["category"] in ("tool", "news") for s in [c, *(c.get("also") or [])]]
    seen_on: dict[str, list[str]] = {}  # each word: the dates of the headlines it is in, to tell new names from old
    for s in stories:
        for w in _words(s["title"]):
            seen_on.setdefault(w, []).append(s["date"])
    for dates in seen_on.values():
        dates.sort()
    launches = []
    for s in stories:
        # the part of the headline with the verb: not a subtitle ("X releases Y: ... on DGX Spark") or a lead-in
        # ("Finally, the wait is over: Meta unveils Llama 3")
        t = next((part for part in s["title"].split(": ") if SHIP.search(part)), "")
        if (m := SHIP.search(t)) and not PROMISE.search(s["title"]) and (who := subject(t, m.start())):
            launches.append((s["date"], who, _words(_ASIDE.sub("", t)), s))
    launches.sort(key=lambda x: x[0])
    starts = [x[0] for x in launches]
    by_url = {s["url"]: s for s in stories}
    out, seen = [], set()
    for c in sorted(cards, key=lambda c: c["date"]):
        if c["category"] not in ("tool", "news") or c["date"] < SINCE or FIXES.get(c["id"], "") is None:
            continue
        title = c["title"].strip()
        m = PROMISE.search(title)
        if not m or NOISE.search(title) or DONE.search(title[:m.start()]):
            continue
        who = subject(title, m.start())
        named = who and names(title, who)
        if not named:
            continue
        # something new: a name rarely in the news before, a name with a number ("GPT-5"), or a new number of the
        # company's own product ("Llama 3")
        own = {w for w in named if re.search(r"[a-z]", w) and w not in _COMMON and (
            re.search(r"\d", w) or bisect.bisect_left(seen_on.get(w, []), c["date"]) < RARE_BEFORE)}
        own |= {w for w in named if re.fullmatch(r"[\d.]+", w) and any(_owner(n) == who for n in named)}
        if not own or (who, frozenset(named)) in seen:  # nothing new named; or the same promise reported again
            continue
        seen.add((who, frozenset(named)))
        d = date.fromisoformat(c["date"])
        until = (d + timedelta(days=WINDOW_DAYS)).isoformat()
        # A promise of several versions ("GPT-4.1, o3 and o4 mini") is kept when one of them is out; a promise to
        # open-source something, only when it is open-sourced.
        versions = {w for w in named if re.search(r"\d", w)}
        need = named - versions if len(versions) > 1 else named
        opened = re.search(r"open[- ]sourc", title, re.I)
        launch = by_url.get(FIXES.get(c["id"]) or "")
        if not launch:  # the same day counts: "Meta prepares to launch Llama 4" and "Meta releases Llama 4", 5 Apr 2025
            launch = next((s for when, w, words, s in launches[bisect.bisect_left(starts, c["date"]):]
                           if when <= until and w == who and s["url"] != c["url"] and need <= words
                           and (len(versions) < 2 or versions & words)
                           and (not opened or re.search(r"open[- ]?(sourc|weight)", s["title"], re.I))), None)
        out.append(_promise(c, who, d, due(title, d), launch, today))
    return sorted(out, key=lambda p: p["date"], reverse=True)


def _promise(c: dict, who: str, d: date, by: date | None, launch: dict | None, today: date) -> dict:
    row = {"date": c["date"], "company": who, "title": c["title"].strip(), "url": c["url"], "source": c["source"],
           "due": by.isoformat() if by else ""}
    if launch:
        took = (date.fromisoformat(launch["date"]) - d).days
        late = (date.fromisoformat(launch["date"]) - by).days if by else 0
        row |= {"status": "late" if late > 0 else "shipped", "days": took, "late": max(late, 0),
                "launch": {k: launch[k] for k in ("date", "title", "url", "source")}}
    elif (by and by >= today) or (not by and (today - d).days <= WINDOW_DAYS):
        row["status"] = "waiting"  # before its date, or without one and not yet WINDOW_DAYS old
    else:
        row["status"] = "not-found"
    return row


PROMISES_JS = r"""<script>
(() => {
  const box = document.getElementById("promises");
  const fmt = d => new Date(d + "T00:00:00Z").toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"});
  const month = d => new Date(d + "T00:00:00Z").toLocaleDateString(undefined, {month: "short", year: "numeric", timeZone: "UTC"});
  const el = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const link = (e) => { const a = el("a", "", e.title); a.href = e.url; a.rel = "noopener"; return a; };
  const days = n => n === 1 ? "1 day" : n + " days";
  const WORDS = {shipped: "Shipped", late: "Shipped late", waiting: "Waiting", "not-found": "Not found yet"};
  fetch(box.dataset.src, {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(list => {
    const count = s => list.filter(p => p.status === s).length;
    document.getElementById("promise-counts").textContent = list.length + " promises since 2023: " +
      (count("shipped") + count("late")) + " shipped (" + count("late") + " of them late), " + count("waiting") +
      " waiting, " + count("not-found") + " with no launch found yet.";
    const table = el("table", "mt promises"), head = el("tr");
    ["Promise", "Due", "What happened"].forEach(h => head.append(el("th", "", h)));
    table.append(el("thead")); table.tHead.append(head);
    const body = el("tbody");
    list.forEach(p => {
      const tr = el("tr"), what = el("td"), promise = el("td");
      promise.append(link(p), el("div", "meta", p.company + " · " + p.source + " · " + fmt(p.date)));
      what.append(el("span", "ps " + p.status, WORDS[p.status]));
      if(p.launch) {
        what.append(link(p.launch), el("div", "meta", p.launch.source + " · " + fmt(p.launch.date) + " · " +
          days(p.days) + " later" + (p.late ? ", " + days(p.late) + " after its date" : "")));
      } else {
        what.append(el("div", "meta", p.status === "waiting" ? (p.due ? "Its date is still ahead" : "No date was given") :
          (p.due ? "Its date has passed" : "Nothing in the 18 months after")));
      }
      tr.append(promise, el("td", "when", p.due ? month(p.due) : "No date"), what);
      body.append(tr);
    });
    table.append(body); box.replaceChildren(table);
  }).catch(() => box.replaceChildren(el("p", "meta", "Couldn't load the promises. Try reloading the page.")));
})();
</script>"""


# ---- The page ----------------------------------------------------------------------------------------------------

def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write follow-through/: the rule echoes, and the promises (from promises.json). Returns its path."""
    parts = pages.frame(conn, len(cards))
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / "flags").mkdir(exist_ok=True)
    found = echoes(cards)
    for code in {p["code"] for t in found for p in t["places"]}:
        shutil.copy(countries.FLAGS / countries.flag(code), out / "flags" / countries.flag(code))
    (out / PATH / "promises.json").write_text(json.dumps(promises(cards, today), separators=(",", ":"),
                                                         ensure_ascii=False), encoding="utf-8")
    what = ("Two ways to see whether AI's big moments lead anywhere: which rules spread from place to place, and which "
            "companies' promises turned into launches.")
    contents = "".join(f'<li><a href="#{t["slug"]}">{escape(t["name"])}</a> <span class="meta">{len(t["places"])}'
                       f'</span></li>' for t in found)
    body = (f'<div class="ft">\n<h1>Follow-through</h1>\n<p class="intro">{escape(what)}</p>\n'
            '<h2 id="echoes">Rule echoes</h2>\n'
            '<p class="what">The subjects AI laws and bills keep returning to, from the Regulation tracker\'s official '
            'records. Each one lists the places that took it up, in the order they first did, and the furthest any of '
            'their records got. The same subject doesn\'t mean one place copied another.</p>\n'
            f'<ul class="themes">{contents}</ul>\n' + "\n".join(_echo_html(t) for t in found) + "\n"
            '<h2 id="promises-h">Promised vs shipped</h2>\n'
            '<p class="what">When a company says it will release something, we look for a later headline saying it '
            'did. The company must lead both headlines, and the launch must name everything the promise named. '
            'We look for a launch up to 18 months after the promise. "Not found yet" means we found no launch, not '
            'that there wasn\'t one.</p>\n'
            '<p class="meta" id="promise-counts"></p>\n'
            f'<div id="promises" data-src="/{PATH}promises.json"><p class="meta">Loading…</p></div>\n'
            f'</div>\n{PROMISES_JS}\n')
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Follow-through", "description": what,
            "url": f"{rss.SITE}{PATH}"}
    (out / PATH / "index.html").write_text(
        pages.page("Follow-through · AI Pulse", what, PATH, body, data, parts, ("/", "Back to AI Pulse"),
                   "Official records link to their sources; headlines are the outlets' own."), encoding="utf-8")
    return [PATH]
