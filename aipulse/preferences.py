"""A reader's own daily email: what they want more of and what to leave out, chosen from exactly the labels and
tags the site shows (every one of them, nothing kept back), plus a few words of their own.

The choices: every story type the site labels (Industry's News, AI-incident, Study, Opinion & analysis, Company
blog, Tutorial, Event; the tracker's Proposal, Law adopted, AI body, Standard) and every tag a story carries
(topics, companies, countries, people). build() writes them to tags.json for the sign-up form, most used in the
last DAYS days first. What a reader leaves out never reaches their email; the full email (daily/) stays the same
for everyone.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from . import brief, classify, digest, sources

DAYS = 30
TYPES = [label for label, _, _ in digest.KIND.values()] + list(digest.ACTION_LABEL.values())
# "Gentler start": the heavier kinds of story, named as the site names them
GENTLE = ["AI-incident", "Misuse", "Deepfakes", "Defense", "Jobs & Labor"]
GROUPS = ["Story types", "Topics", "Companies", "Countries", "People"]
_PEOPLE = {name for name, _ in sources.PROFESSORS} | {name for name, _, _ in sources.EXPERTS}
_COMPANIES = set(classify.COMPANY_TERMS) | set(sources.COMPANIES)
_SKIP = {"Research"}  # every paper carries it: the Research stream is the choice for that


def story_type(c: dict) -> str | None:
    """The label the site shows on a card, when it's one of TYPES."""
    if c.get("category") == "news":
        return digest.KIND.get(c.get("kind") or "news", digest.KIND["news"])[0]
    if c.get("category") == "regulation":
        return digest.ACTION_LABEL.get(c.get("action") or "")
    return None


def labels(c: dict) -> set[str]:
    """Everything a reader can choose that this story has: its type and all its tags (the site shows the first
    five; a filter sees every one)."""
    tags = set(c.get("tags") or [])
    if c.get("category") != "research":
        tags |= set(classify.tags_for(c.get("title") or "", c.get("summary") or "", limit=99))
    return tags - _SKIP | ({story_type(c)} - {None})


def group_of(label: str) -> str:
    if label in TYPES or label == classify.UNTRANSLATED_TAG:
        return "Story types"
    if label in brief._PLACE_TAGS or label == "International bodies":
        return "Countries"
    if label in _COMPANIES:
        return "Companies"
    if label in _PEOPLE:
        return "People"
    return "Topics"


def options(cards: list[dict], today: date | None = None) -> dict:
    """tags.json: every label any stored story has, grouped as the form shows them, each with how many stories
    had it in the last DAYS days (the most used first; the rest, down to those not seen lately, after them)."""
    since = ((today or date.today()) - timedelta(days=DAYS)).isoformat()
    every, recent = set(TYPES), Counter()
    for c in cards:
        mine = labels(c)
        every |= mine
        if (c.get("date") or "") >= since:
            recent.update(mine)
    groups = {g: [] for g in GROUPS}
    for label in every:
        groups[group_of(label)].append({"t": label, "n": recent[label]})
    for items in groups.values():
        items.sort(key=lambda i: (-i["n"], i["t"].lower()))
    return {"days": DAYS, "gentle": GENTLE, "groups": [{"name": g, "items": groups[g]} for g in GROUPS]}
