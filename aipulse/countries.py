"""The Regulation tracker by country: a plain page per place (tracker/<place>/) that search engines can index,
and tracker/ listing them. Official records only (legislatures, OECD.AI, ISO/IEC, IEEE), as in tracker.csv: news
outlets' stories stay on the live tracker, their headlines being theirs. A place gets a page once it has
MIN_RECORDS records, so no page is near empty; the live tracker has the rest.
"""
from __future__ import annotations

import json
import re
from datetime import date
from html import escape
from pathlib import Path

from . import jurisdictions, rss
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


STYLE = """
@font-face{font-family:'Archivo Black';font-weight:400;font-display:swap;src:url("/fonts/archivo-black-latin-400-normal.woff2") format("woff2")}
@font-face{font-family:'Archivo';font-weight:400;font-display:swap;src:url("/fonts/archivo-latin-400-normal.woff2") format("woff2")}
@font-face{font-family:'Archivo';font-weight:600;font-display:swap;src:url("/fonts/archivo-latin-600-normal.woff2") format("woff2")}
:root{--ink:#000;--muted:#3B3B3B;--bg:#FFF;--line:#000;--tag:#D55E00;--link:#0072B2}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 Archivo,Arial,sans-serif}
.wrap{max-width:780px;margin:0 auto;padding:24px 16px 48px}
header{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;border-bottom:3px solid var(--line);padding-bottom:12px}
header a{color:var(--ink);text-decoration:none}
.brand{font:400 22px 'Archivo Black',Arial,sans-serif}
.back{font-weight:600;font-size:14px;text-decoration:underline;text-decoration-color:var(--tag);text-decoration-thickness:2px;text-underline-offset:4px}
h1{font:400 clamp(28px,5vw,40px)/1.1 'Archivo Black',Arial,sans-serif;margin:28px 0 8px}
.lead{color:var(--muted);margin:0 0 20px}
.lead a{color:var(--link)}
h2{font:600 15px Archivo,Arial,sans-serif;text-transform:uppercase;letter-spacing:.06em;margin:30px 0 4px;border-top:6px solid var(--tag);padding-top:10px}
ul{list-style:none;margin:0;padding:0}
li{padding:12px 0;border-bottom:1px solid color-mix(in srgb,var(--line) 25%,transparent)}
li a{color:var(--ink);font-weight:600;text-decoration:none}
li a:hover,li a:focus-visible{text-decoration:underline}
.meta{color:var(--muted);font-size:14px;margin-top:2px}
.steps{color:var(--muted);font-size:13.5px;margin-top:2px}
.places{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-top:20px}
.places a{display:block;border:2px solid var(--line);padding:12px 14px;color:var(--ink);font-weight:600;text-decoration:none}
.places a:hover,.places a:focus-visible{background:color-mix(in srgb,var(--tag) 15%,transparent)}
footer{margin-top:36px;font-size:14px;color:var(--muted)}
footer a{color:var(--link)}
"""


def _page(title: str, description: str, path: str, body: str, data: dict) -> str:
    url = f"{rss.SITE}{path}"
    return (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{escape(title)}</title>\n<meta name="description" content="{escape(description)}">\n'
            f'<link rel="canonical" href="{url}">\n<link rel="icon" href="/favicon.ico">\n'
            f'<meta property="og:title" content="{escape(title)}">\n<meta property="og:description" content="{escape(description)}">\n'
            f'<meta property="og:url" content="{url}">\n<meta property="og:image" content="{rss.SITE}og.png">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n'
            f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>\n'
            f'<style>{STYLE}</style>\n</head>\n<body><div class="wrap">\n'
            f'<header><a class="brand" href="/">AI Pulse</a><a class="back" href="/#regulation">Live Regulation tracker →</a></header>\n'
            f'{body}\n<footer>Official records only, each linking to its source. '
            f'<a href="/tracker.csv">Download them all (CSV)</a> · '
            f'<a href="https://github.com/shru14/ai-pulse#credits-and-licences">Sources and licences</a></footer>\n'
            f'</div></body>\n</html>\n')


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
        body = (f'<h1>{escape(heading(code, name))}</h1>\n'
                f'<p class="lead">Official records, newest first. Updated {updated}. '
                f'<a href="/tracker/">All places</a></p>\n' + "\n".join(sections))
        (out / path).mkdir(parents=True, exist_ok=True)
        (out / path / "index.html").write_text(_page(title, description, path, body, data), encoding="utf-8")
        paths.append(path)
    links = "\n".join(f'<a href="/tracker/{slug(names[code])}/">{escape(names[code])}</a>' for code in places)
    body = (f'<h1>AI laws by country</h1>\n<p class="lead">The Regulation tracker\'s official records, a page per '
            f'place. Updated {updated}. Places with fewer records are on the live tracker.</p>\n'
            f'<div class="places">\n{links}\n</div>')
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI laws by country",
            "url": f"{rss.SITE}tracker/"}
    (out / "tracker").mkdir(parents=True, exist_ok=True)
    (out / "tracker" / "index.html").write_text(
        _page("AI laws by country · AI Pulse", "AI bills, laws, regulators and standards by country, from official "
              "records, updated every 6 hours.", "tracker/", body, data), encoding="utf-8")
    return ["tracker/", *paths]
