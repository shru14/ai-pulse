"""What governments use AI for (government-ai-use/): three governments' own registers of the AI and algorithms they
use, read once a day on full runs, one box each. The US: every use in the federal agencies' yearly inventory, which the
White House budget office (OMB) puts together on GitHub, with Excel-style filters (agency, area, kind of AI, stage,
high-impact). The Netherlands: the national Algorithm Register's counts, and every system a public body marked as a
high-risk AI system under the EU AI Act, names and descriptions in Dutch as registered. The UK: every algorithmic
transparency record on GOV.UK, newest first. Each register's own words and categories; linked from Policy's strip.

Terms (terms.py): the US inventory is a US government work (public domain); GOV.UK is under the Open Government Licence
v3.0; the Dutch register's copyright page says its content may be reused. robots.txt allows all three.
"""
from __future__ import annotations

import collections
import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from . import feeds, infra_watch, pages, rss, store

PATH = "government-ai-use/"
KEY = "gov_ai"  # the meta row holding each register's rows and when it was last read
EVERY = timedelta(hours=20)  # a register is read again on the first full run this long after the last (once a day)
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

# place: (the register's own page, its name)
REGISTERS = {
    "US": ("https://github.com/ombegov/2025-Federal-Agency-AI-Use-Case-Inventory",
           "Federal Agency AI Use Case Inventory"),
    "NL": ("https://algoritmes.overheid.nl/nl/algoritme", "Algoritmeregister"),
    "UK": ("https://www.gov.uk/algorithmic-transparency-records", "Algorithmic Transparency Records"),
}
# OMB publishes each year's inventory in a repository of its own; the newest one found is read
US_CSV = ("https://raw.githubusercontent.com/ombegov/{y}-Federal-Agency-AI-Use-Case-Inventory/HEAD/Data/"
          "{y}_individually_reported_AI_use_cases.csv")
US_FIRST = 2025
NL_CSV = "https://algoritmes.overheid.nl/api/downloads/NLD?filetype=csv"
NL_ENTRY = "https://algoritmes.overheid.nl/nl/algoritme/{id}"
UK_API = ("https://www.gov.uk/api/search.json?filter_format=algorithmic_transparency_record&count=1000"
          "&order=-public_timestamp&fields=title,link,description,public_timestamp")
# The Dutch register's own areas and statuses, in English (our words; the rows themselves stay in Dutch)
NL_AREAS = {
    "Organisatie en bedrijfsvoering": "Running the organisation", "Sociale zekerheid": "Social security",
    "Openbare orde en veiligheid": "Public order and safety", "Overheidsfinanciën": "Public finances",
    "Verkeer": "Traffic", "Ruimte en infrastructuur": "Land and infrastructure", "Natuur en milieu": "Nature and environment",
    "Wonen": "Housing", "Zorg en gezondheid": "Care and health", "Werk": "Work", "Onderwijs en wetenschap": "Education and science",
    "Recht": "Justice", "Migratie en integratie": "Migration and integration", "Economie": "Economy",
    "Bestuur": "Public administration", "Cultuur en recreatie": "Culture and recreation", "Landbouw": "Agriculture",
    "Internationaal": "International", "Onderwijs": "Education", "Zorg": "Care", "Energie": "Energy",
}
NL_STATUSES = {"In gebruik": "In use", "In ontwikkeling": "Being built", "Buiten gebruik": "No longer used"}
NL_HIGH = "Hoog-risico AI-systeem"  # the register's own category for a high-risk AI system (EU AI Act)
US_STAGES = ("Deployed", "Pilot", "Pre-deployment", "Retired")
US_HIGH = "High-impact"


def _short(text: str, n: int = 160) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


# --- each register ---

def read_us(fetcher, today: date) -> dict:
    """The newest yearly federal inventory OMB has published: every use an agency listed."""
    for y in range(today.year, US_FIRST - 1, -1):
        url = US_CSV.format(y=y)
        try:
            text = fetcher(url).decode("utf-8-sig", "replace")
        except Exception:
            if y > US_FIRST:  # that year's inventory isn't out yet
                continue
            raise
        rows = []
        for r in csv.DictReader(io.StringIO(text)):
            name = (r.get("use_case_name") or "").strip()
            if not name:
                continue
            rows.append({"ag": r.get("agency", "").strip(), "agency": r.get("agency_name", "").strip(), "name": name,
                         "what": _short(r.get("problem_solved") or r.get("benefits") or ""),
                         "area": r.get("topic_area", "").strip(), "kind": r.get("classification", "").strip(),
                         "stage": r.get("development_stage", "").strip(), "impact": r.get("is_high_impact", "").strip()})
        return {"year": y, "url": url, "rows": rows}
    return {}


def read_nl(fetcher, today: date) -> dict:
    """The Dutch Algorithm Register's own download: its counts by area and status, and every high-risk AI system."""
    text = fetcher(NL_CSV).decode("utf-8-sig", "replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    high = [{"org": r["organization"].strip(), "name": r["name"].strip(), "what": _short(r.get("description_short", "")),
             "area": r.get("category", "").split(",")[0].strip(), "status": r.get("status", "").strip(),
             "id": r.get("algorithm_id", "").strip()}
            for r in rows if r.get("publication_category") == NL_HIGH and r.get("name")]
    return {"total": len(rows), "high": high,
            "areas": collections.Counter(r.get("category", "").split(",")[0].strip() for r in rows),
            "statuses": collections.Counter(r.get("status", "").strip() for r in rows)}


def read_uk(fetcher, today: date) -> dict:
    """Every algorithmic transparency record on GOV.UK, through its search API."""
    found = json.loads(fetcher(UK_API)).get("results") or []
    rows = [{"title": r["title"].strip(), "day": (r.get("public_timestamp") or "")[:10],
             "what": _short(r.get("description") or ""),
             "url": "https://www.gov.uk" + r["link"] if r["link"].startswith("/") else r["link"]}
            for r in found if r.get("title") and r.get("link")]
    return {"rows": sorted(rows, key=lambda r: r["day"], reverse=True)}


READERS = {"US": read_us, "NL": read_nl, "UK": read_uk}


def health_name(place: str) -> str:
    return f"What governments use AI for: {REGISTERS[place][1]} ({place})"


def refresh(conn, fetcher=feeds.fetch, now: datetime | None = None) -> str:
    """Read each register again once a day. A register that can't be read keeps the rows last read, and is logged in
    the sources table like a news source, so one failing 3 runs in a row reaches the project inbox
    (python -m aipulse source-alert)."""
    now = now or datetime.now(timezone.utc)
    saved, said = load(conn), []
    for place, read in READERS.items():
        last = saved.get(place, {}).get("read", "")
        if last and now - datetime.fromisoformat(last.replace("Z", "+00:00")) < EVERY:
            said.append(f"{place} read today")
            continue
        try:
            got = read(fetcher, now.date())
            n = len(got.get("rows") or []) or got.get("total", 0)
            saved[place] = {"read": now.strftime("%Y-%m-%dT%H:%MZ"), **got}
            said.append(f"{place} {n}")
            store.record_source(conn, health_name(place), REGISTERS[place][0], ok=True, entries=n)
        except Exception as e:
            said.append(f"{place} not read ({e})")
            store.record_source(conn, health_name(place), REGISTERS[place][0], ok=False,
                                error=str(e) or type(e).__name__)
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (KEY, json.dumps(saved)))
    conn.commit()
    return ", ".join(said)


def load(conn) -> dict:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (KEY,)).fetchone() if conn else None
    return json.loads(row[0]) if row else {}


# --- the page ---

def _when(d: str) -> str:
    y, m, day = d[:10].split("-")
    return f"{int(day)} {_MONTHS[int(m) - 1]} {y}"


def _counts(title: str, pairs) -> str:
    """A small table of a register's own categories and how many entries each has, biggest first."""
    return (f'<div><h3>{escape(title)}</h3><table>'
            + "".join(f'<tr><td>{escape(k)}</td><td class="gv-n">{v:,}</td></tr>' for k, v in pairs) + "</table></div>")


def _box(place: str, flag: str, name: str, lead: str, inner: str) -> str:
    url, register = REGISTERS[place]
    return (f'<section class="pc-half gv-{place.lower()}"><div class="pc-hh"><h2><img src="flags/{flag}.svg" alt="" '
            f'class="gv-f">{escape(name)}</h2><p>{lead} · <a href="{escape(url, quote=True)}" rel="noopener">'
            f'{escape(register)}</a></p></div><div class="pc-in">{inner}</div></section>\n')


def _tag(text: str, cls: str) -> str:
    return f'<span class="pc-k {cls}">{escape(text)}</span>'


def _us(us: dict) -> tuple[str, str]:
    """The US box and the page's lead line."""
    rows = us.get("rows") or []
    high = [r for r in rows if r["impact"] == US_HIGH]
    live = [r for r in high if r["stage"] in ("Deployed", "Pilot")]
    top = collections.Counter(r["agency"] for r in live).most_common(2)
    agencies = len({r["agency"] for r in rows})
    order = {s: i for i, s in enumerate(US_STAGES)}
    rows = sorted(rows, key=lambda r: (r["impact"] != US_HIGH, order.get(r["stage"], 9), r["agency"], r["name"]))
    stage = {"Deployed": "gv-live", "Pilot": "gv-trial"}
    trs = "".join(
        f'<tr><td data-f="{escape(r["agency"] or "–")}"><b title="{escape(r["agency"])}">{escape(r["ag"] or r["agency"])}</b>'
        f'<span class="fx-c">{escape(r["agency"])}</span></td>'
        f'<td>{escape(r["name"])}<span class="fx-c">{escape(r["what"])}</span></td>'
        f'<td>{escape(r["area"] or "–")}</td><td>{escape(r["kind"] or "–")}</td>'
        f'<td data-f="{escape(r["stage"] or "–")}">{_tag(r["stage"], stage.get(r["stage"], "gv-off")) if r["stage"] else "–"}</td>'
        f'<td data-f="{escape(r["impact"] or "–")}">'
        f'{_tag(r["impact"], "gv-high") if r["impact"] == US_HIGH else escape(r["impact"] or "–")}</td></tr>'
        for r in rows)
    lead = (f'US federal agencies list <b>{len(rows):,} AI uses</b>; <b>{len(live)}</b> in use or on trial are '
            "high-impact, meaning they can affect people's rights or safety"
            + (f', most at <b>{escape(top[0][0])}</b> ({top[0][1]})' if top else "")
            + (f" and {escape(top[1][0])} ({top[1][1]})" if len(top) > 1 else "") + ".")
    head = "".join(f'<th{" data-nof" * (h == "AI use and what it does")}>{h}</th>'
                   for h in ("Agency", "AI use and what it does", "Used for", "Kind of AI", "Stage", "High-impact"))
    inner = ('<div class="gv-two">'
             + _counts("Used for", collections.Counter(r["area"] or "Not given" for r in rows).most_common(8))
             + _counts("Kind of AI", collections.Counter(r["kind"] or "Not given" for r in rows).most_common(8))
             + "</div>"
             f'<h3>Every use, high-impact first</h3><div class="iw">'
             f'<div class="iw-fbar"></div><p class="iw-count" aria-live="polite">Showing <b>{len(rows):,}</b> of '
             f'{len(rows):,} uses. Pick a ▾ to filter. <button type="button" class="iw-clear" hidden>Clear filters'
             f'</button></p><div class="gv-sc"><table class="pc-rows xf-t gv-t gv-us-t"><thead><tr>{head}</tr></thead>'
             f"<tbody>{trs}</tbody></table></div></div>")
    box = _box("US", "us", "United States · federal agencies",
               f"{len(rows):,} AI uses listed by {agencies} agencies in the {us.get('year', '')} inventory, put "
               "together by the White House budget office (OMB)", inner)
    return box, lead


def _nl(nl: dict) -> str:
    high = sorted(nl.get("high") or [], key=lambda r: (list(NL_STATUSES).index(r["status"])
                                                         if r["status"] in NL_STATUSES else 9, r["org"], r["name"]))
    status = {"In gebruik": "gv-live", "In ontwikkeling": "gv-trial"}
    trs = "".join(
        f'<tr><td><b>{escape(r["org"])}</b></td><td><a href="{escape(NL_ENTRY.format(id=r["id"]), quote=True)}" '
        f'rel="noopener" lang="nl">{escape(r["name"])}</a><span class="fx-c" lang="nl">{escape(r["what"])}</span></td>'
        f'<td>{escape(NL_AREAS.get(r["area"], r["area"]) or "–")}</td>'
        f'<td>{_tag(NL_STATUSES.get(r["status"], r["status"]), status.get(r["status"], "gv-off"))}</td></tr>'
        for r in high)
    areas = collections.Counter()
    for k, v in (nl.get("areas") or {}).items():
        areas[NL_AREAS.get(k, k) or "Not given"] += v
    statuses = [(NL_STATUSES.get(k, k) or "Not given", v)
                for k, v in sorted((nl.get("statuses") or {}).items(), key=lambda kv: -kv[1])]
    inner = ('<div class="gv-two">' + _counts("Used for", areas.most_common(8))
             + _counts("Where they stand", statuses) + "</div>"
             f'<h3>High-risk AI systems ({len(high)}) · names and descriptions in Dutch, as registered</h3>'
             '<div class="gv-sc"><table class="pc-rows gv-t"><thead><tr><th>Public body</th><th>System and what it does'
             f"</th><th>Area</th><th>Status</th></tr></thead><tbody>{trs}</tbody></table></div>")
    return _box("NL", "nl", "Netherlands · all public bodies",
                f"{nl.get('total', 0):,} algorithms in the national Algorithm Register; {len(high)} marked by the body "
                "itself as a high-risk AI system under the EU AI Act", inner)


def _uk(uk: dict) -> str:
    rows = uk.get("rows") or []
    this_year = str(datetime.now(timezone.utc).year)
    first = min((r["day"][:4] for r in rows if r["day"]), default="")

    def split(title: str) -> tuple[str, str]:
        body, _, tool = title.partition(":")
        return (body.strip(), tool.strip()) if tool.strip() else ("", title)
    trs = []
    for r in rows:
        body, tool = split(r["title"])
        trs.append(f'<tr><td class="pc-d">{_when(r["day"]) if r["day"] else "–"}</td><td><b>{escape(body or "–")}</b></td>'
                   f'<td><a href="{escape(r["url"], quote=True)}" rel="noopener">{escape(tool)}</a>'
                   f'<span class="fx-c">{escape(r["what"])}</span></td></tr>')
    inner = ("<h3>Every record, newest first</h3>"
             '<div class="gv-sc"><table class="pc-rows gv-t"><thead><tr><th>Published</th><th>Public body</th>'
             f'<th>Tool and what it does</th></tr></thead><tbody>{"".join(trs)}</tbody></table></div>')
    n_year = sum(r["day"][:4] == this_year for r in rows)
    return _box("UK", "gb", "United Kingdom · public bodies",
                f"{len(rows)} algorithmic transparency records published on GOV.UK"
                + (f" since {first} ({n_year} so far in {this_year})" if first else ""), inner)


def body(saved: dict) -> str:
    us_box, lead = _us(saved["US"]) if saved.get("US", {}).get("rows") else ("", "")
    boxes = us_box + (_nl(saved["NL"]) if saved.get("NL", {}).get("total") else "") \
        + (_uk(saved["UK"]) if saved.get("UK", {}).get("rows") else "")
    read = max((v.get("read", "") for v in saved.values()), default="")
    limits = [
        ("Counted", "What each government lists in its own register, in its own categories. Registers count different "
                    "things: the US lists AI uses, the Dutch register every algorithm (AI or not), the UK the tools a "
                    "public body chose to publish a record for."),
        ("High-impact (US)", "The agency's own answer to whether a use can affect people's rights or safety, under the "
                             "White House's rules for federal AI (OMB memo M-25-21)."),
        ("High-risk (NL)", "The public body's own answer to whether a system is a high-risk AI system under the EU AI "
                           "Act."),
        ("Left out", "Uses an agency kept out of its public inventory, as OMB's rules allow. The Department of Defense "
                     "and the intelligence agencies aren't in the US inventory."),
        ("Links", "Dutch and UK rows link to their official entry; US rows come from OMB's file, linked above."),
    ]
    if read:
        limits.append(("Last read", f"{_when(read)}, {read[11:16]} UTC (once a day)"))
    return ('<div class="ft pc gv">\n'
            + pages.feature_head(PATH, "What governments use AI for",
                                 "Which jobs do governments give to AI, and which ones touch people's lives?",
                                 "Read from three governments' own registers of the AI they use: the US federal "
                                 "inventory, the Dutch Algorithm Register and the UK's algorithmic transparency "
                                 "records, each in its own words.")
            + (f'<p class="gv-lead">{lead}</p>\n' if lead else "")
            + f'<div class="pc-stack">{boxes}</div>\n'
            '<section class="jb-lim"><h2>About these counts</h2>\n<table class="mt jb-small jb-limits"><tbody>'
            + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
            + "</tbody></table></section></div>\n" + infra_watch.SCRIPT + "\n")


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write the page from the registers last read. Returns its path, or nothing before any register was read."""
    saved = load(conn)
    if not any(v.get("rows") or v.get("total") for v in saved.values()):
        return []
    what = ("Which jobs do governments give to AI, and which ones touch people's lives? Read from the US federal AI "
            "inventory, the Dutch Algorithm Register and the UK's algorithmic transparency records.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "What governments use AI for",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("What governments use AI for · AI Pulse", what, PATH, body(saved), data,
                   pages.frame(conn, len(cards)), ("/policy/", "Back to Policy"),
                   "Every row is the government's own entry, in its own words."),
        encoding="utf-8")
    return [PATH]
