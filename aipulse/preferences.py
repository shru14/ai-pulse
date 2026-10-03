"""A reader's own daily email: what they want more of and what to leave out, chosen from the labels and tags the
site shows, plus a few words of their own.

The form stays short: every section shows a handful of choices, and its search finds the rest, so nothing the site
tags is out of reach. Story types are the site's labels (Industry's News, AI-incident, Study, Opinion & analysis,
Company blog, Tutorial, Event; the tracker's Proposal, Law adopted, AI body, Standard); topics come as eight
themes, places as continents, companies as the ten most in the news this month, and people through the search.
build() writes it all to tags.json for the sign-up form. What a reader leaves out never reaches their email; the
full email (daily/) stays the same for everyone.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from . import brief, classify, digest, jurisdictions, sources

DAYS = 30
TYPES = [label for label, _, _ in digest.KIND.values()] + list(digest.ACTION_LABEL.values())
# "Gentler start": the heavier kinds of story, named as the site names them
GENTLE = ["AI-incident", "Misuse", "Deepfakes", "Defense", "Jobs & Labor"]
GROUPS = ["Story types", "Topics", "Companies", "Places", "People"]
TOP_COMPANIES = 10
_PEOPLE = {name for name, _ in sources.PROFESSORS} | {name for name, _, _ in sources.EXPERTS}
_COMPANIES = set(classify.COMPANY_TERMS) | set(sources.COMPANIES)
_SKIP = {"Research"}  # every paper carries it: the Research stream is the choice for that

# The site's topic tags in eight themes; a theme stands for every tag in it.
THEMES = {
    "Models & products": ["Agents", "Open Models", "Reasoning", "Multimodal", "Voice", "Image & Video Generation",
                          "Coding Tools", "Robotics", "Benchmarks", "Training Data"],
    classify.INFRA_TAG: [classify.INFRA_TAG, *classify.INFRA_TOPICS, "Chips", "Compute & Data Centers", "Energy", "Climate"],
    "Business & work": ["Funding", "M&A", "IPO", "Jobs & Labor"],
    "Law & regulation": ["Law", "Regulation", "AI Act", "Standards", "Governance", "Copyright", "Privacy",
                         "Antitrust", "Export Controls"],
    "Safety & security": ["Safety", "Alignment", "Interpretability", "Existential Risk", "Security", "Misuse",
                          "Deepfakes", "Surveillance"],
    "Defense & elections": ["Defense", "Elections"],
    "Science, health & education": ["Science", "Healthcare", "Education", "Study Report"],
    "Ethics & ideas": ["Ethics", "Philosophy"],
}
THEME_OF = {topic: theme for theme, topics in THEMES.items() for topic in topics}
# Themes renamed since readers chose them: a saved choice of the old name still means the new theme.
RENAMED = {"Chips, compute & energy": classify.INFRA_TAG, "Infrastructure & sustainability": classify.INFRA_TAG}

# Places are offered as continents (UN M49 geoscheme), not a long list of countries; every country can still be
# found with the form's search. Built from the site's own regions: Americas and Asia-Pacific split, the Middle
# East is Asia, Türkiye and the Caucasus and Cyprus are Asia (as M49 has them). Russia, as on the site, belongs to
# no region (jurisdictions.NO_REGION): readers choose it by name.
CONTINENTS = ["Africa", "Asia", "Europe", "North America", "South America", "Oceania", "International bodies"]
_SOUTH_AMERICA = {"AR", "BO", "BR", "CL", "CO", "EC", "GY", "PY", "PE", "SR", "UY", "VE"}
_OCEANIA = {"AU", "NZ", "FJ", "KI", "MH", "FM", "NR", "PG", "PW", "SB", "TO", "TV", "VU", "WS"}
_MIDDLE_EAST = {"AE", "SA", "QA", "IL", "BH", "IQ", "IR", "JO", "KW", "LB", "OM", "PS", "SY", "YE"}
_WESTERN_ASIA = {"TR", "GE", "AM", "AZ", "CY"}


def _continent(code: str) -> str:
    region = jurisdictions.REGION_OF.get(code, "")
    if code == "INTL":
        return "International bodies"
    if code in _WESTERN_ASIA or code in _MIDDLE_EAST:
        return "Asia"
    if region == "europe":
        return "Europe"
    if region == "americas":
        return "South America" if code in _SOUTH_AMERICA else "North America"
    if region == "asia":
        return "Oceania" if code in _OCEANIA else "Asia"
    return "Africa" if region == "mea" else ""


_ALIASES = {"EU": "EU", "US": "US", "UK": "GB", "China": "CN", "India": "IN"}
CONTINENT_OF = {name: _continent(code) for code, (name, *_) in jurisdictions.JURISDICTIONS.items()}
CONTINENT_OF |= {alias: _continent(code) for alias, code in _ALIASES.items()}
COUNTRIES = sorted(name for code, (name, *_) in jurisdictions.JURISDICTIONS.items() if code != "INTL")


def story_type(c: dict) -> str | None:
    """The label the site shows on a card, when it's one of TYPES."""
    if c.get("category") == "news":
        return digest.KIND.get(c.get("kind") or "news", digest.KIND["news"])[0]
    if c.get("category") == "regulation":
        return digest.ACTION_LABEL.get(c.get("action") or "")
    return None


def labels(c: dict) -> set[str]:
    """Everything a reader can choose that this story has: its type, all its tags (the site shows the first five;
    a filter sees every one), and the theme and continent they belong to."""
    tags = set(c.get("tags") or [])
    if c.get("category") != "research":
        tags |= set(classify.tags_for(c.get("title") or "", c.get("summary") or "", limit=99, source=c.get("source") or ""))
    tags -= _SKIP
    if c.get("category") == "infra":  # the stream's every story counts as the theme, tag or not
        tags.add(classify.INFRA_TAG)
    tags |= {old for old, new in classify.INFRA_SAYS.items() if new in tags}  # saved choices of the topics these replaced
    wider = {THEME_OF.get(t) for t in tags} | {CONTINENT_OF.get(t) for t in tags}
    wider |= {old for old, new in RENAMED.items() if new in wider}
    return tags | (wider - {None, ""}) | ({story_type(c)} - {None})


def group_of(label: str) -> str:
    if label in TYPES or label == classify.UNTRANSLATED_TAG:
        return "Story types"
    if label in brief._PLACE_TAGS or label in CONTINENT_OF or label in CONTINENTS:
        return "Places"
    if label in _COMPANIES:
        return "Companies"
    if label in _PEOPLE:
        return "People"
    return "Topics"


def options(cards: list[dict], today: date | None = None) -> dict:
    """tags.json: per section, the few choices the form shows (`items`), the rest that its search finds
    (`search`: every label any stored story has, the most used in the last DAYS days first) and a line saying so.
    `themes`: which topics each theme stands for."""
    since = ((today or date.today()) - timedelta(days=DAYS)).isoformat()
    every, recent = set(), Counter()
    for c in cards:
        mine = labels(c)
        every |= mine
        if (c.get("date") or "") >= since:
            recent.update(mine)
    found = {g: [] for g in GROUPS}
    for label in every - set(THEMES) - set(CONTINENTS) - set(TYPES):
        found[group_of(label)].append(label)
    for items in found.values():
        items.sort(key=lambda t: (-recent[t], t.lower()))
    companies = found["Companies"]
    groups = [
        {"name": "Story types", "items": TYPES + ([classify.UNTRANSLATED_TAG] if classify.UNTRANSLATED_TAG in every else [])},
        {"name": "Topics", "items": list(THEMES), "search": found["Topics"],
         "note": "Each theme covers several topics; search to pick one, such as Funding or Robotics."},
        {"name": "Companies", "items": companies[:TOP_COMPANIES], "search": companies[TOP_COMPANIES:],
         "note": f"The {TOP_COMPANIES} most in the news this month; search for any of the {len(companies)} we tag."},
        {"name": "Places", "items": CONTINENTS, "search": COUNTRIES, "note": "Search for any country."},
        {"name": "People", "items": [], "search": found["People"],
         "note": f"Search for any of the {len(found['People'])} scholars whose papers we follow."},
    ]
    return {"gentle": GENTLE, "themes": THEMES, "groups": groups}
