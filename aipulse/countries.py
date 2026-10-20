"""The Regulation tracker by country: a plain page per place (tracker/<place>/) that search engines can index,
and tracker/ listing them; and standards/, every AI standard on the tracker in one place. Official records only (legislatures, OECD.AI, ISO/IEC, IEEE), as in tracker.csv: news
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

MIN_RECORDS = 2  # the owner's choice, 12 Oct 2026 (was 3)
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


def record(c: dict, place_name: str) -> dict:
    """A record as search engines' labels (schema.org): a law or a bill is Legislation, in force or not yet."""
    kind = c.get("action") or "proposal"
    item = {"@type": "Legislation" if kind in ("law", "proposal") else "CreativeWork", "name": c["title"].strip(),
            "url": c["url"], "datePublished": c["date"][:10]}
    if item["@type"] == "Legislation":
        item.update(legislationJurisdiction=place_name, legislationDate=c["date"][:10],
                    legislationLegalForce="InForce" if kind == "law" else "NotInForce")
    return item


def dataset(records: list[dict], places: list[str], today: date) -> dict:
    """tracker.csv as a Dataset, for Google Dataset Search: what it holds, where and when, and the file."""
    days = sorted({c["date"][:10] for c in records}) or [today.isoformat()]
    return {"@type": "Dataset", "name": "AI Pulse Regulation tracker: AI laws, bills, bodies and standards",
            "description": ("Official records of artificial intelligence laws, bills, regulators and technical "
                            "standards worldwide, from legislatures, OECD.AI, ISO/IEC and IEEE: each record's date, "
                            "countries, type, title, source and link. Updated every 6 hours."),
            "url": f"{rss.SITE}tracker/", "isAccessibleForFree": True,
            "keywords": ["artificial intelligence", "AI regulation", "AI law", "legislation", "AI standards"],
            "creator": {"@type": "Organization", "name": "AI Pulse", "url": rss.SITE},
            "license": "https://github.com/shru14/ai-pulse#credits-and-licences",
            "spatialCoverage": places, "temporalCoverage": f"{days[0]}/{days[-1]}", "dateModified": today.isoformat(),
            "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv",
                              "contentUrl": f"{rss.SITE}tracker.csv"}]}


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
    parts = pages.frame(conn, len(cards))
    pages.write_css(out)
    back = ("/regulation/", "Back to the live Regulation tracker page")
    note = 'Official records only, each linking to its source.'
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
                stage = LABELS.get(code, LABELS["US"]).get(steps[-1]["stage"], "") if steps else ""
                trail = (" → ".join(f'{escape(s.get("text") or s["stage"])} ({_day(s["date"])})' for s in steps)
                         if len(steps) > 1 else "")
                rows.append((f'<td><a href="{escape(c["url"])}">{escape(c["title"].strip())}</a></td>'
                             f'<td>{escape(c["source"])}</td>', stage, trail, _day(c["date"])))
            if rows:  # a grid per kind; Stage and Steps columns only where a record has them
                staged, stepped = any(r[1] for r in rows), any(r[2] for r in rows)
                head = ("<tr><th>Title</th><th>Source</th>" + ("<th>Stage</th>" if staged else "")
                        + ("<th>Steps</th>" if stepped else "") + "<th>Date</th></tr>")
                body_rows = "\n".join(f'<tr>{cells}' + (f'<td>{escape(stage)}</td>' if staged else "")
                                      + (f'<td class="gt-steps">{trail}</td>' if stepped else "")
                                      + f'<td>{day}</td></tr>' for cells, stage, trail, day in rows)
                sections.append(f'<h2>{label}</h2>\n<div class="gt-wrap"><table class="gt"><thead>{head}</thead><tbody>\n'
                                + body_rows + "\n</tbody></table></div>")
        title = f"{heading(code, name)} · AI Pulse"
        description = (f"AI bills, laws, regulators and standards {'from international bodies' if code == 'INTL' else 'in ' + place(name)}"
                       f": official records with their stages and links to the sources, updated every 6 hours.")
        data = {"@context": "https://schema.org", "@type": "ItemList", "name": heading(code, name),
                "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": record(c, name)}
                                    for i, c in enumerate(items[:100])]}
        ask = "What have international bodies agreed on AI?" if code == "INTL" else f"What has {place(name)} decided on AI?"
        body = (pages.band("reg", f'<img src="flags/{flag(code)}" alt="">', "photos/cartoons/pages/tracker.svg",
                           heading(code, name), ask, 'Official records of bills, laws, regulators and standards, newest '
                           'first, each with its stage and a link to the source. <a href="/tracker/">All places</a>')
                + "\n".join(sections))
        (out / path).mkdir(parents=True, exist_ok=True)
        (out / path / "index.html").write_text(pages.page(title, description, path, body, data, parts, back, note), encoding="utf-8")
        paths.append(path)
    links = "\n".join(f'<a href="/tracker/{slug(names[code])}/"><img class="flag" src="flags/{flag(code)}" alt="">{escape(names[code])}</a>' for code in places)
    body = (pages.band("reg", "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
                       "photos/cartoons/pages/tracker.svg", "AI laws by country", "Where are AI rules being made?",
                       "The Regulation tracker's official records, a page per place. Places with fewer records are on "
                       'the live tracker. <a href="/standards/">AI standards</a>')
            + f'<div class="places">\n{links}\n</div>')
    data = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": "AI laws by country", "url": f"{rss.SITE}tracker/"},
        dataset([c for code in by_place for c in by_place[code]], [names[code] for code in places], today)]}
    (out / "tracker").mkdir(parents=True, exist_ok=True)
    (out / "tracker" / "index.html").write_text(
        pages.page("AI laws by country · AI Pulse", "AI bills, laws, regulators and standards by country, from official "
              "records, updated every 6 hours.", "tracker/", body, data, parts, back, note), encoding="utf-8")
    return ["tracker/", *paths]


TYPE_PAGES = {  # the Regulation strip's buttons: one kind of record from every place, path → (kind, title, question, intro)
    "tracker/laws-adopted/": ("law", "AI laws adopted", "Which places have passed AI laws?",
                              "Laws, decrees and rules on AI that governments have adopted, from every place on the "
                              "tracker, newest first, each linking to the official text."),
    "tracker/bills/": ("proposal", "AI bills", "Which AI bills are lawmakers working on?",
                       "AI bills put before legislatures, from every place on the tracker, newest first, each with "
                       "its latest stage and a link to the legislature's page."),
    "tracker/ai-bodies/": ("body", "AI bodies", "Who has been set up to oversee AI?",
                           "AI offices, councils, units and panels that governments have set up, from every place on "
                           "the tracker, newest first, each linking to its record on OECD.AI."),
}


def type_pages(conn, cards: list[dict], out: Path) -> list[str]:
    """TYPE_PAGES: one kind of official record from every place, as one table, newest first. A place with its own
    page (build, run first) links to it."""
    names = {code: m["name"] for code, m in jurisdictions.meta().items()}
    records = [c for c in cards if c["category"] == "regulation" and c["source"] in OFFICIAL_SOURCES]
    with_page = {p.name for p in (out / "tracker").iterdir() if p.is_dir()} if (out / "tracker").exists() else set()
    parts = pages.frame(conn, len(cards))
    back = ("/regulation/", "Back to the live Regulation tracker page")
    note = 'Official records only, each linking to its source.'
    (out / "flags").mkdir(parents=True, exist_ok=True)
    paths = []
    for path, (kind, title, question, intro) in TYPE_PAGES.items():
        items = sorted((c for c in records if (c.get("action") or "proposal") == kind), key=lambda c: c["date"], reverse=True)
        if not items:
            continue
        bills = kind == "proposal"
        rows = []
        for c in items:
            code = next((code for code in c.get("jurisdictions") or [] if code in names), "INTL")
            name = names.get(code, "International")
            where = escape(name)
            if (FLAGS / flag(code)).exists():
                shutil.copy(FLAGS / flag(code), out / "flags" / flag(code))
                where = f'<img class="flag" src="/flags/{flag(code)}" alt="">{where}'
            if slug(name) in with_page:
                where = f'<a href="/tracker/{slug(name)}/">{where}</a>'
            stage = ""
            if bills:
                steps = _history(conn, c.get("bill", ""))
                stage = f'<td class="tp-stage">{escape(LABELS.get(code, LABELS["US"]).get(steps[-1]["stage"], "") if steps else "")}</td>'
            rows.append(f'<tr><td class="tp-where">{where}</td><td class="tp-title"><a href="{escape(c["url"])}">{escape(c["title"].strip())}</a>'
                        f'<div class="meta">{escape(c["source"])}</div></td>{stage}<td>{_day(c["date"])}</td></tr>')
        head = "<tr><th>Place</th><th>Title</th>" + ("<th>Stage</th>" if bills else "") + "<th>Date</th></tr>"
        others = " · ".join(f'<a href="/{p}">{t[1]}</a>' for p, t in TYPE_PAGES.items() if p != path)
        body = (pages.band("reg", "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
                           "photos/cartoons/pages/tracker.svg", title, question,
                           f'{intro} <a href="/tracker/">AI laws by country</a> · {others}')
                + f'<table class="mt tp-t"><thead>{head}</thead><tbody>\n' + "\n".join(rows) + "\n</tbody></table>")
        data = {"@context": "https://schema.org", "@type": "ItemList", "name": title,
                "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": record(c, names.get(
                    next((x for x in c.get("jurisdictions") or [] if x in names), "INTL"), "International"))}
                    for i, c in enumerate(items[:100])]}
        (out / path).mkdir(parents=True, exist_ok=True)
        (out / path / "index.html").write_text(pages.page(f"{title} · AI Pulse", intro, path, body, data, parts, back, note),
                                               encoding="utf-8")
        paths.append(path)
    return paths


def _month(c: dict) -> str:
    """ISO gives only a standard's month of publication (standards.py dates it the 1st)."""
    d = date.fromisoformat(c["date"][:10])
    return f"{d:%b %Y}" if c["source"] == "ISO/IEC" else _day(c["date"])


def standards_page(conn, cards: list[dict], out: Path) -> list[str]:
    """standards/: the tracker's published AI standards, ISO/IEC's and IEEE's (with our own line on what each
    covers) and national ones (OECD.AI), newest first, each linking to its official page. No date of its own:
    the list changes only when a standard is added."""
    from .standards import SOURCES
    names = {code: m["name"] for code, m in jurisdictions.meta().items()}
    items = sorted((c for c in cards if c["category"] == "regulation" and c.get("action") == "standard"
                    and c["source"] in OFFICIAL_SOURCES), key=lambda c: c["date"], reverse=True)
    if not items:
        return []
    groups = [(f"International: {src}", [c for c in items if c["source"] == src]) for src in SOURCES]
    groups.append(("National", [c for c in items if c["source"] not in SOURCES]))
    sections = []
    for label, rows in groups:
        if not rows:
            continue
        lines = []
        for c in rows:
            where = ", ".join(names.get(code, code) for code in c.get("jurisdictions") or [] if code != "INTL")
            meta = " · ".join(x for x in (f"Published {_month(c)}", c["source"], where) if x)
            lines.append(f'<li><a href="{escape(c["url"])}">{escape(c["title"].strip())}</a>'
                         f'<div class="meta">{escape(meta)}</div>'
                         + (f'<div class="what">{escape(c["summary"])}</div>' if c["source"] in SOURCES and c.get("summary") else "")
                         + "</li>")
        sections.append(f"<section>\n<h2>{escape(label)}</h2>\n<ul>\n" + "\n".join(lines) + "\n</ul>\n</section>")
    parts = pages.frame(conn, len(cards))
    back = ("/regulation/", "Back to the live Regulation tracker page")
    note = 'Official records only, each linking to its source.'
    body = ('<div class="sd">\n' + pages.band("reg", "M6 3h9l4 4v14H6zM15 3v4h4M9 12h7M9 16h7", "photos/cartoons/pages/standards.svg",
                                               "AI standards", "Which AI standards have been published?",
                                               "Published standards for AI from ISO/IEC, IEEE and national bodies, newest "
                                               'first, each linking to its official page. <a href="/tracker/">AI laws by country</a>')
            + '<div class="cols">\n' + "\n".join(sections) + "\n</div>\n</div>")
    data = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": "AI standards", "url": f"{rss.SITE}standards/"},
        {"@type": "ItemList", "name": "AI standards", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "item": record(c, "International")} for i, c in enumerate(items)]}]}
    (out / "standards").mkdir(parents=True, exist_ok=True)
    (out / "standards" / "index.html").write_text(pages.page(
        "AI standards: ISO/IEC, IEEE and national · AI Pulse",
        "Published AI standards from ISO/IEC (JTC 1/SC 42), IEEE and national standards bodies: what each covers, "
        "when it was published and a link to its official page.", "standards/", body, data, parts, back, note),
        encoding="utf-8")
    return ["standards/"]
