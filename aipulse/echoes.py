"""Rule echoes (rule-echoes/): the Regulation tracker's official records grouped by subject (sexual deepfakes, AI
companions, labelling...), drawn as one timeline. Each subject is a row; each place's flag sits where that place first
took the subject up, ringed by the furthest its records got (proposed, passed, adopted), so a rule can be seen
spreading. Opening a row lists its records. A subject in common is not a claim that one place copied another. The
grouping reads only each record's title and its official description, where the source gives one. Rebuilt with the
site, so a new record joins at the next run. Linked from the Regulation tracker's strip on the front page.
"""
from __future__ import annotations

import re
import shutil
from datetime import date
from html import escape
from pathlib import Path

from . import classify, countries, jurisdictions, pages, rss
from .bills import OFFICIAL_SOURCES

PATH = "rule-echoes/"


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


LANE, LANE_PHONE = 30, 24  # px between a row's lines of flags (smaller flags on a phone)
# % of the timeline: flags closer than this go on the next line, so none hides another. A phone's timeline is about
# 330px wide, so its flags (22px, with their rings and ticks about 35px) need a wider share of it.
GAP, GAP_PHONE = 3.6, 12
_STAGES = [(4, "Adopted or set up"), (2, "Passed a vote"), (1, "Proposed"), (0, "Withdrawn or vetoed")]


def _x(iso: str, start: date, days: int) -> float:
    return round((date.fromisoformat(iso[:10]) - start).days / days * 100, 2)


def _lane(lines: list[float], x: float, gap: float) -> int:
    """The first line of flags with room at x (each line's last flag is `gap` or more before it), else a new one."""
    lane = next((i for i, last in enumerate(lines) if x - last >= gap), len(lines))
    lines[lane:lane + 1] = [x]
    return lane


def _row(t: dict, start: date, days: int, years: list[tuple[int, float]]) -> str:
    wide: list[float] = []  # each line's last flag, on a wide screen and on a phone
    phone: list[float] = []
    pins = []
    for p in t["places"]:
        x = _x(p["since"], start, days)
        lane = _lane(wide, x, GAP)
        small = _lane(phone, x, GAP_PHONE)
        tip = f'{p["name"]}: since {_when(p["first"], p["since"])}, {p["furthest"].lower()}'
        pins.append(f'<span class="pin r{p["rank"]}" style="left:{x}%;--t:{lane * LANE}px;--tp:{small * LANE_PHONE}px" '
                    f'title="{escape(tip)}"><img src="flags/{countries.flag(p["code"])}" alt="{escape(p["name"])}"></span>')
    grid = "".join(f'<i class="yl" style="left:{x}%"></i>' for _, x in years)
    rows = []
    for p in t["places"]:
        for i, c in enumerate(p["records"]):
            rows.append(f'<tr{" class=first" if i == 0 else ""}><td class="when">{_when(c, _started(c))}</td>'
                        f'<td>{escape(p["name"]) if i == 0 else ""}</td>'
                        f'<td><a href="{escape(c["url"])}" rel="noopener">{escape(c["title"].strip())}</a>'
                        f'<div class="meta">{escape(c["source"])}</div></td><td>{escape(_reached(c)[1])}</td></tr>')
    first, n = t["places"][0], len(t["places"])
    adopted = sum(p["rank"] == 4 for p in t["places"])
    lead = (f'{escape(t["what"])} {n} places took it up; the first on the tracker was '
            f'{escape(countries.place(first["name"]))}, in {_when(first["first"], first["since"])}'
            + (f'. {adopted} adopted it or set a body up.' if adopted else '. None has adopted it yet.'))
    return (f'<details class="er" id="{t["slug"]}"><summary><span class="nm">{escape(t["name"])}'
            f'<small>{n} places</small></span><span class="trk" style="--h:{len(wide) * LANE - 6}px;'
            f'--hp:{len(phone) * LANE_PHONE - 4}px">{grid}'
            f'{"".join(pins)}</span></summary>\n<div class="det"><p>{lead}</p><table class="mt"><thead><tr>'
            f'<th>Since</th><th>Place</th><th>Official record</th><th>Furthest</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></details>')


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write rule-echoes/: the timeline of subjects, each opening onto its records. Returns its path."""
    found = echoes(cards)
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / "flags").mkdir(exist_ok=True)
    for code in {p["code"] for t in found for p in t["places"]}:
        shutil.copy(countries.FLAGS / countries.flag(code), out / "flags" / countries.flag(code))
    start = date(min((int(p["since"][:4]) for t in found for p in t["places"]), default=today.year), 1, 1)
    days = max((today - start).days, 1)
    years = [(y, _x(f"{y}-01-01", start, days)) for y in range(start.year, today.year + 1)]
    # "2024", or "'24" on a phone
    axis = "".join(f'<span style="left:{x}%"><i>{str(y)[:2]}</i>{str(y)[2:]}</span>' for y, x in years)
    legend = "".join(f'<span><span class="pin r{r}"><img src="flags/{countries.flag("INTL")}" alt=""></span>{w}</span>'
                     for r, w in _STAGES)
    shutil.copy(countries.FLAGS / countries.flag("INTL"), out / "flags" / countries.flag("INTL"))
    what = ("The subjects AI laws keep coming back to, and the places that took each one up, in the order they did. "
            "Each flag sits where a place first acted; its ring shows how far it got.")
    body = (f'<div class="ft">\n<h1>Rule echoes</h1>\n<p class="intro">{escape(what)} Open a subject to see its '
            'official records. The same subject doesn\'t mean one place copied another.</p>\n'
            f'<div class="ec-legend">{legend}</div>\n'
            f'<div class="ec-wrap"><div class="ec"><div class="ec-axis"><span></span><span class="yrs">{axis}'
            f'<span class="now" style="left:100%">Now</span></span></div>\n'
            + "\n".join(_row(t, start, days, years) for t in found)
            + '</div></div>\n</div>\n')
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Rule echoes", "description": what,
            "url": f"{rss.SITE}{PATH}"}
    note = ("From the Regulation tracker's official records, each linking to its source; updated with the tracker. "
            '<a href="/tracker/">AI laws by country</a>')
    (out / PATH / "index.html").write_text(
        pages.page("Rule echoes · AI Pulse", what, PATH, body, data, pages.frame(conn, len(cards)),
                   ("/regulation/", "Back to the Regulation tracker"), note), encoding="utf-8")
    return [PATH]
