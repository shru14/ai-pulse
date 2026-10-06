"""The Regulation tracker by country: a plain page per place (tracker/<place>/) that search engines can index,
and tracker/ listing them. Official records only (legislatures, OECD.AI, ISO/IEC, IEEE), as in tracker.csv: news
outlets' stories stay on the live tracker, their headlines being theirs. A place gets a page once it has
MIN_RECORDS records, so no page is near empty; the live tracker has the rest.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from html import escape
from pathlib import Path

from . import jurisdictions, pages, rss
from .bills import LABELS, OFFICIAL_SOURCES

MIN_RECORDS = 3
KINDS = [("law", "Laws adopted"), ("proposal", "Proposals"), ("body", "AI bodies"), ("standard", "Standards")]


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


_NEEDS_THE = ("United ", "European ", "Netherlands", "Philippines", "Czech Republic", "Dominican Republic")


def place(name: str) -> str:
    """The name as a sentence uses it: "the United Kingdom", "India"."""
    return f"the {name}" if name.startswith(_NEEDS_THE) else name


def heading(code: str, name: str) -> str:
    return "AI rules from international bodies" if code == "INTL" else f"AI laws and bills in {place(name)}"


def _day(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d:%b %Y}"


def _history(conn, key: str) -> list[dict]:
    if not key:
        return []
    row = conn.execute("SELECT history FROM bills WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row and row[0] else []


FLAGS = Path(__file__).resolve().parent.parent / "templates" / "flags"  # flag-icons (MIT), 4:3; intl.svg is our own


def flag(code: str) -> str:
    """The place's flag file under flags/: a US state's is the US flag; international bodies get a globe."""
    return "intl.svg" if code == "INTL" else f"{code.split('-')[0].lower()}.svg"


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write tracker/ and a page per place with MIN_RECORDS official records or more. Returns their paths."""
    names = {code: m["name"] for code, m in jurisdictions.meta().items()}
    by_place: dict[str, list[dict]] = {}
    for c in cards:
        if c["category"] == "regulation" and c["source"] in OFFICIAL_SOURCES:
            for code in c.get("jurisdictions") or []:
                if code in names:
                    by_place.setdefault(code, []).append(c)
    places = sorted((code for code, items in by_place.items() if len(items) >= MIN_RECORDS),
                    key=lambda code: (code != "INTL", names[code]))
    updated = _day(today.isoformat())
    parts = pages.frame(conn, len(cards))
    pages.write_css(out)
    back = ("/regulation/", "Back to the live Regulation tracker page")
    note = 'Official records only, each linking to its source. <a href="/tracker.csv">Download them all (CSV)</a>'
    (out / "flags").mkdir(parents=True, exist_ok=True)
    for code in places:
        shutil.copy(FLAGS / flag(code), out / "flags" / flag(code))
    paths = []
    for code in places:
        name, items = names[code], sorted(by_place[code], key=lambda c: c["date"], reverse=True)
        path = f"tracker/{slug(name)}/"
        sections = []
        for kind, label in KINDS:
            rows = []
            for c in (c for c in items if (c.get("action") or "proposal") == kind):
                steps = _history(conn, c.get("bill", ""))
                now = steps[-1] if steps else None
                stage = (LABELS.get(code, LABELS["US"]).get(now["stage"], "") if now else "")
                meta = " · ".join(x for x in (stage, _day(c["date"]), c["source"]) if x)
                trail = (" → ".join(f'{escape(s.get("text") or s["stage"])} ({_day(s["date"])})' for s in steps)
                         if len(steps) > 1 else "")
                rows.append(f'<li><a href="{escape(c["url"])}">{escape(c["title"].strip())}</a>'
                            f'<div class="meta">{escape(meta)}</div>'
                            + (f'<div class="steps">{trail}</div>' if trail else "") + "</li>")
            if rows:
                sections.append(f'<h2>{label}</h2>\n<ul>\n' + "\n".join(rows) + "\n</ul>")
        title = f"{heading(code, name)} · AI Pulse"
        description = (f"AI bills, laws, regulators and standards {'from international bodies' if code == 'INTL' else 'in ' + place(name)}"
                       f": official records with their stages and links to the sources, updated every 6 hours.")
        data = {"@context": "https://schema.org", "@type": "ItemList", "name": heading(code, name),
                "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": c["url"], "name": c["title"].strip()}
                                    for i, c in enumerate(items[:100])]}
        body = (f'<h1><img class="flag" src="flags/{flag(code)}" alt="">{escape(heading(code, name))}</h1>\n'
                f'<p class="intro">Official records, newest first. Updated {updated}. '
                f'<a href="/tracker/">All places</a></p>\n' + "\n".join(sections))
        (out / path).mkdir(parents=True, exist_ok=True)
        (out / path / "index.html").write_text(pages.page(title, description, path, body, data, parts, back, note), encoding="utf-8")
        paths.append(path)
    links = "\n".join(f'<a href="/tracker/{slug(names[code])}/"><img class="flag" src="flags/{flag(code)}" alt="">{escape(names[code])}</a>' for code in places)
    body = (f'<h1>AI laws by country</h1>\n<p class="intro">The Regulation tracker\'s official records, a page per '
            f'place. Updated {updated}. Places with fewer records are on the live tracker.</p>\n'
            f'<div class="places">\n{links}\n</div>')
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI laws by country",
            "url": f"{rss.SITE}tracker/"}
    (out / "tracker").mkdir(parents=True, exist_ok=True)
    (out / "tracker" / "index.html").write_text(
        pages.page("AI laws by country · AI Pulse", "AI bills, laws, regulators and standards by country, from official "
              "records, updated every 6 hours.", "tracker/", body, data, parts, back, note), encoding="utf-8")
    return ["tracker/", *paths]
