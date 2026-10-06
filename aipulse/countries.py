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

from . import jurisdictions, rss, store
from .bills import LABELS, OFFICIAL_SOURCES
from .server import TEMPLATE

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


STYLE = """
.cp{max-width:780px;margin:0 auto;padding-bottom:12px}
.cp .back{display:inline-block;margin-top:24px;font-weight:600;font-size:15px;color:var(--ink);text-decoration:underline;text-decoration-color:#D55E00;text-decoration-thickness:2px;text-underline-offset:4px}
.cp h1{display:flex;align-items:center;gap:16px;font:400 clamp(28px,5vw,40px)/1.1 var(--display);letter-spacing:0;margin:18px 0 8px}
.cp .flag{flex:none;width:32px;height:24px;object-fit:cover;border:1px solid #000}
.cp h1 .flag{width:60px;height:45px;border-width:2px}
.cp .intro{color:var(--muted);margin:0 0 20px}
.cp .intro a{color:#0072B2}
.cp h2{font:600 15px var(--body);text-transform:uppercase;letter-spacing:.06em;margin:30px 0 4px;border-top:6px solid #D55E00;padding-top:10px}
.cp ul{list-style:none;margin:0;padding:0}
.cp li{padding:12px 0;border-bottom:1px solid color-mix(in srgb,#000 25%,transparent)}
.cp li a{color:var(--ink);font-weight:600;text-decoration:none}
.cp li a:hover,.cp li a:focus-visible{text-decoration:underline}
.cp .meta{color:var(--muted);font-size:14px;margin-top:2px}
.cp .steps{color:var(--muted);font-size:13.5px;margin-top:2px}
.cp .places{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-top:20px}
.cp .places a{display:flex;align-items:center;gap:12px;border:2px solid #000;background:var(--bg);padding:12px 14px;color:var(--ink);font-weight:600;text-decoration:none}
.cp .places a:hover,.cp .places a:focus-visible{background:color-mix(in srgb,#D55E00 15%,var(--bg))}
.cp .note{margin-top:28px;font-size:14px;color:var(--muted)}
.cp .note a{color:#0072B2}
a.subscribe-btn{text-decoration:none}
"""


def _frame(total: int, last: str) -> tuple[str, str, str]:
    """The site's own styles, masthead (no stream links; Subscribe and Glossary open on the front page) and footer."""
    t = TEMPLATE.read_text(encoding="utf-8")
    style = re.search(r"<style>(.*?)</style>", t, re.S).group(1)
    header = re.search(r'<header class="top home">.*?</header>', t, re.S).group(0)
    header = re.sub(r"\s*<!-- Each stream.*?</nav>", "", header, flags=re.S)
    header = re.sub(r'<button class="(subscribe-btn[^"]*)" id="(\w+)-open" type="button" aria-haspopup="dialog"',
                    r'<a class="\1" href="/#\2"', header).replace("</button>", "</a>")
    when = (f'<div>Last update <time datetime="{escape(last)}">{escape(last[:16].replace("T", " "))} UTC</time></div>'
            if last else "")
    header = header.replace("Loading feed…", f"<div><b>{total}</b> stories in total</div>{when}")
    footer = re.search(r'<footer class="site-foot">.*?</footer>', t, re.S).group(0)
    return style, header, footer


# the masthead's time in the reader's own time zone, as on the front page
LOCAL_TIME = ('<script>document.querySelectorAll("time[datetime]").forEach(t => t.textContent = new Date(t.dateTime)'
              '.toLocaleString(undefined,{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}))</script>')


def _page(title: str, description: str, path: str, body: str, data: dict, frame: tuple[str, str, str]) -> str:
    url = f"{rss.SITE}{path}"
    style, header, footer = frame
    return (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8"><meta name="color-scheme" content="light">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<base href="/">\n'
            f'<title>{escape(title)}</title>\n<meta name="description" content="{escape(description)}">\n'
            f'<link rel="canonical" href="{url}">\n<link rel="icon" href="/favicon.ico">\n'
            f'<meta property="og:title" content="{escape(title)}">\n<meta property="og:description" content="{escape(description)}">\n'
            f'<meta property="og:url" content="{url}">\n<meta property="og:image" content="{rss.SITE}og.png">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n'
            f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>\n'
            f'<style>{style}{STYLE}</style>\n</head>\n<body>\n<div class="wrap">\n{header}\n<main class="cp">\n'
            f'<a class="back" href="/regulation/">← Back to the live Regulation tracker page</a>\n{body}\n'
            f'<p class="note">Official records only, each linking to its source. '
            f'<a href="/tracker.csv">Download them all (CSV)</a></p>\n</main>\n{footer}\n</div>\n{LOCAL_TIME}\n</body>\n</html>\n')


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
    last = (store.last_run(conn) or {}).get("ran_at") or ""
    frame = _frame(len(cards), last)
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
        (out / path / "index.html").write_text(_page(title, description, path, body, data, frame), encoding="utf-8")
        paths.append(path)
    links = "\n".join(f'<a href="/tracker/{slug(names[code])}/"><img class="flag" src="flags/{flag(code)}" alt="">{escape(names[code])}</a>' for code in places)
    body = (f'<h1>AI laws by country</h1>\n<p class="intro">The Regulation tracker\'s official records, a page per '
            f'place. Updated {updated}. Places with fewer records are on the live tracker.</p>\n'
            f'<div class="places">\n{links}\n</div>')
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI laws by country",
            "url": f"{rss.SITE}tracker/"}
    (out / "tracker").mkdir(parents=True, exist_ok=True)
    (out / "tracker" / "index.html").write_text(
        _page("AI laws by country · AI Pulse", "AI bills, laws, regulators and standards by country, from official "
              "records, updated every 6 hours.", "tracker/", body, data, frame), encoding="utf-8")
    return ["tracker/", *paths]
