"""What governments use AI for (government-ai-use/): the lists governments publish of the AI they themselves use.
The page: who publishes such a list (the four read in full here, and the others checked by hand), whose AI they run
(the suppliers named in the registers that name one), then a card per full list linking to its own page with every
entry and Excel-style filters. Each government's own words and categories; linked from Policy's strip.

The four full lists, read once a day on full runs (terms in terms.py; robots.txt allows each):
- United States: the federal agencies' yearly AI use case inventory, as the White House budget office (OMB) puts it
  together on GitHub (a US government work, public domain).
- Canada: the Government of Canada AI Register on the open data portal (Open Government Licence - Canada).
- Netherlands: the national Algorithm Register's own download (its copyright page: the content may be reused); names
  and descriptions stay in Dutch as registered, only its areas and statuses are given in English.
- United Kingdom: the algorithmic transparency records on GOV.UK (Open Government Licence v3.0).
"""
from __future__ import annotations

import collections
import csv
import io
import json
import math
import re
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from . import feeds, infra_watch, pages, rss, store

PATH = "government-ai-use/"
KEY = "gov_ai"  # the meta row holding each list's rows and when it was last read
EVERY = timedelta(hours=20)  # a list is read again on the first full run this long after the last (once a day)
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

# place: (its page's address under PATH, flag, name, the list's own page, the list's name, who keeps it)
PLACES = {
    "US": ("united-states/", "us", "United States", "https://github.com/ombegov/2025-Federal-Agency-AI-Use-Case-Inventory",
           "Federal Agency AI Use Case Inventory", "White House budget office (OMB)"),
    "NL": ("netherlands/", "nl", "Netherlands", "https://algoritmes.overheid.nl/nl/algoritme", "Algoritmeregister",
           "Ministry of the Interior"),
    "CA": ("canada/", "ca", "Canada", "https://open.canada.ca/data/dataset/fcbc0200-79ba-4fa4-94a6-00e32facea6b",
           "Government of Canada AI Register", "Treasury Board of Canada Secretariat"),
    "UK": ("united-kingdom/", "gb", "United Kingdom", "https://www.gov.uk/algorithmic-transparency-records",
           "Algorithmic Transparency Records", "Department for Science, Innovation and Technology"),
}
# The other governments' own lists, checked by hand (official ones only: France's inventory is kept by an independent
# observatory and Chile's by a university: LEFT_OUT). Lists that couldn't be opened wait in RECHECK.
# (place, flag, the list's name, its page, what it holds, who keeps it, tag, checked on)
OTHERS = [
    ("Norway", "no", "Offentlige KI-tiltak", "https://ki.norge.no/ki-tiltak", "149 initiatives",
     "KI Norge (Digdir)", "Reported by choice", "2026-10-20"),
    ("Estonia", "ee", "Kratid: AI use stories", "https://www.kratid.ee/kasutuslood-kratid", "about 200 uses",
     "Ministry of Justice and Digital Affairs", "Selected stories", "2026-10-20"),
    ("Brazil", "br", "AI in the federal executive",
     "https://www.gov.br/governodigital/pt-br/infraestrutura-nacional-de-dados/inteligencia-artificial-1",
     "182 in operation", "Ministry of Management (MGI)", "A count, no list", "2026-10-20"),
]
# what each full list holds, for the tag in "Who tells you"
FULL_TAG = {"US": "Every use", "NL": "Every algorithm", "CA": "Every system", "UK": "Tools chosen to record"}

# The daily job (python -m aipulse govai, a scheduled Claude routine) keeps OTHERS right, and the owner approves each
# govai/<day> branch: what each list's own page says it holds today (COUNTS reads it), the lists that couldn't be
# opened (RECHECK), and Policy, Regulation and Industry stories from after CHECKED_TO reporting a government publishing
# a list of the AI it uses.
CHECKED_TO = "2026-10-20"
# where each list's page states how many entries it holds (read live; the job updates OTHERS when it changes)
COUNTS = {
    "Norway": r"(\d[\d\s.,]*)\s*tiltak\b",
    "Estonia": r"umbes\s+(\d+)\s+korral",
    "Brazil": r"(\d[\d.]*)\s+soluç(?:ões|oes) de IA em operaç",
}
# official lists that couldn't be opened when last checked: (place, flag, the list's name, its page, who keeps it, why)
RECHECK = [
    ("Scotland", "gb-sct", "Scottish AI Register", "https://www.scottishairegister.com/", "Scottish Government",
     "its security certificate had expired (20 Oct 2026)"),
    ("Australia", "au", "AI transparency statements", "https://www.digital.gov.au/policy/ai/list-of-transparency-statements",
     "Digital Transformation Agency", "the site didn't answer our reader (20 Oct 2026)"),
]
# stories and lists checked by hand and left out, with why, so they aren't checked again
LEFT_OUT: dict[str, str] = {
    "https://www.data.gouv.fr/datasets/inventaire-des-algorithmes-publics-de-lodap":
        "France: kept by an independent observatory (ODAP), not the government",
    "https://algoritmospublicos.cl/": "Chile: kept by a university (GobLab UAI), not the government",
}
# a headline or summary that may report a government's list of the AI it uses
_LIST = re.compile(r"\b(AI|artificial intelligence|algorithm(ic|s)?)\b[^.]{0,60}\b(register|registry|inventory|"
                   r"inventories|transparency (record|statement)s?|use cases?)\b|\b(register|registry|inventory) of "
                   r"(AI|artificial intelligence|algorithms)\b", re.I)
_GOV = re.compile(r"\b(government|ministry|minister|department|agency|agencies|public sector|federal|council|"
                  r"municipal|state|OMB|GAO|civil service|public bod(y|ies)|parliament)\b", re.I)


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Policy, Regulation and Industry stories from after CHECKED_TO (or `since`, if later) that may report a
    government's list of its own AI, not in LEFT_OUT or OTHERS: newest first."""
    since = max(since, CHECKED_TO + "~")  # '~' sorts after any time of day
    done = set(LEFT_OUT) | {o[3] for o in OTHERS} | {r[3] for r in RECHECK} | {p[3] for p in PLACES.values()}
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["date"] >= since and c.get("category") in ("policy", "regulation", "news")
            and not any(s["url"] in done for s in [c, *(c.get("also") or [])])
            and _LIST.search(text := f"{c['title']} {c.get('summary') or ''}") and _GOV.search(text)]


def recheck(fetcher=feeds.fetch) -> list[tuple[str, str, str]]:
    """Each hand-kept list's page read again: (place, what OTHERS shows, what its page says now, or why it couldn't be
    read); then each RECHECK list, whether it opens now."""
    import html as _html
    out = []
    for place, _, _, url, holds, *_ in OTHERS:
        try:
            text = _html.unescape(re.sub(r"<[^>]+>", " ", fetcher(url).decode("utf-8", "replace")))
            m = re.search(COUNTS.get(place, r"$^"), text, re.I)
            out.append((place, holds, f"page says {m.group(1).strip()}" if m else "no count found on the page"))
        except Exception as e:
            out.append((place, holds, f"not read ({e})"))
    for place, _, _, url, _, why in RECHECK:
        try:
            fetcher(url)
            out.append((place, f"couldn't be opened: {why}", "opens now: check it"))
        except Exception as e:
            out.append((place, f"couldn't be opened: {why}", f"still not read ({e})"))
    return out


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a govai/<day> branch: each list it adds to or changes in OTHERS, and what it left
    out; None when it changes nothing. `base` is main's copy of this file."""
    import ast
    from . import approve
    had_rows = set()
    for node in ast.parse(base).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "OTHERS" for t in node.targets):
            had_rows = {tuple(r) for r in ast.literal_eval(node.value)}
    had = approve.lists_in(base, ("LEFT_OUT",))
    rows = [(o[0], o[2], o[4], o[5], o[6], _when(o[7]), o[3]) for o in OTHERS if tuple(o) not in had_rows]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("What governments use AI for", f"government list{'s' * (len(rows) != 1)}", branch,
                        ("Place", "List", "Holds", "Kept by", "Covers", "Checked", "Its page"), rows, dropped)

# OMB publishes each year's inventory in a repository of its own; the newest one found is read
US_CSV = ("https://raw.githubusercontent.com/ombegov/{y}-Federal-Agency-AI-Use-Case-Inventory/HEAD/Data/"
          "{y}_individually_reported_AI_use_cases.csv")
US_FIRST = 2025
CA_DATASET = "https://open.canada.ca/data/api/action/package_show?id=fcbc0200-79ba-4fa4-94a6-00e32facea6b"
NL_CSV = "https://algoritmes.overheid.nl/api/downloads/NLD?filetype=csv"
NL_ENTRY = "https://algoritmes.overheid.nl/nl/algoritme/{id}"
UK_API = ("https://www.gov.uk/api/search.json?filter_format=algorithmic_transparency_record&count=1000"
          "&order=-public_timestamp&fields=title,link,description,public_timestamp")
# The Dutch register's own areas, statuses and kinds, in English (our words; the entries themselves stay in Dutch)
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
NL_KINDS = {"Hoog-risico AI-systeem": "High-risk AI system", "Impactvolle algoritmes": "Impactful algorithm",
            "Overige algoritmes": "Other algorithm"}
NL_HIGH = "High-risk AI system"  # the register's own mark for a high-risk AI system under the EU AI Act
US_HIGH = "High-impact"
US_STAGES = ("Deployed", "Pilot", "Pre-deployment", "Retired")
CA_PUBLIC = ("Members of public", "Both employees and public")
# Suppliers: an entry counts for a company when its supplier field names the company or one of its AI products, or
# its own name names one of those products (company names alone could be something else there: "Amazon basin").
# Checked by hand against every match on 20 Oct 2026. "Azure OpenAI" names both Microsoft and OpenAI.
# company: (in the supplier field, in the entry's name)
SUPPLIERS = {
    "Microsoft": (r"\bmicrosoft\b|\bcopilot\b|\bazure\b", r"\bmicrosoft\b|\bcopilot\b|\bazure\b"),
    "OpenAI": (r"\bopenai\b|\bchatgpt\b", r"\bopenai\b|\bchatgpt\b"),
    "Google": (r"\bgoogle\b|\bgemini\b|\bvertex ai\b", r"\bgoogle\b|\bgemini (code assist|ai|for)\b|\bvertex ai\b|^gemini\b"),
    "Amazon": (r"\bamazon\b|\baws\b|\brekognition\b",
               r"\baws\b|\bamazon (web services|q|connect|bedrock|transcribe|comprehend|textract|lex|polly|rekognition|"
               r"sagemaker)\b|\brekognition\b"),
    "Palantir": (r"\bpalantir\b", r"\bpalantir\b"),
    "ServiceNow": (r"\bservicenow\b", r"\bservicenow\b"),
    "IBM": (r"\bibm\b|\bwatsonx?\b", r"\bibm\b|\bwatsonx\b"),
    "Anthropic": (r"\banthropic\b|\bclaude\b", r"\banthropic\b|\bclaude (code|ai|for|chat)\b|^claude\b"),
}
NAMES_SUPPLIER = ("US", "CA", "NL")  # the lists with a supplier field
# Entries that touch people, shown on each card: names as registered, checked by hand; if a list no longer has them,
# the card takes the first entries its own rule gives
EXAMPLES = {
    "US": ["Passive Body Scanner", "AI-Assisted Resume Screening Tool", "Passenger Security Assessment Model"],
    "CA": ["Primary Inspection Kiosk", "Develop a public facing Generative AI Chatbot for general enquiries leveraging "
           "ChatGPT LLM", "AgPal Chat"],
    "NL": ["Biometrische identificatie en verificatie van vreemdelingen", "Werkzoekenden matchen met vacatures", "Bodycam"],
    "UK": ["Check-In with your probation officer (E-Supervision)", "BenchNotes", "VAT Assist"],
}


def _the(place: str) -> str:
    """A place's name as a sentence needs it: "the United States", "Canada"."""
    return f"the {place}" if place.startswith(("United", "Netherlands")) else place


def _short(text: str, n: int = 160) -> str:
    t = " ".join((text or "").split())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _csv(raw: bytes) -> list[dict]:
    return list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig", "replace"))))


# --- each list ---

def read_us(fetcher, today: date) -> dict:
    """The newest yearly federal inventory OMB has published: every use an agency listed."""
    for y in range(today.year, US_FIRST - 1, -1):
        url = US_CSV.format(y=y)
        try:
            raw = fetcher(url)
        except Exception:
            if y > US_FIRST:  # that year's inventory isn't out yet
                continue
            raise
        rows = [{"ag": r.get("agency", "").strip(), "body": r.get("agency_name", "").strip(),
                 "name": r["use_case_name"].strip(), "what": _short(r.get("problem_solved") or r.get("benefits") or ""),
                 "area": r.get("topic_area", "").strip(), "kind": r.get("classification", "").strip(),
                 "stage": r.get("development_stage", "").strip(), "impact": r.get("is_high_impact", "").strip(),
                 "vendor": r.get("vendor_name", "").strip()}
                for r in _csv(raw) if (r.get("use_case_name") or "").strip()]
        return {"year": y, "rows": rows}
    return {}


def read_ca(fetcher, today: date) -> dict:
    """The Government of Canada AI Register: the newest CSV its open data record lists."""
    found = json.loads(fetcher(CA_DATASET))["result"]
    url = next(r["url"] for r in found["resources"] if (r.get("format") or "").upper() == "CSV")

    def status(s: str) -> str:
        s = " ".join(s.split())
        return s[:1].upper() + s[1:].lower() if s else ""
    rows = [{"body": r.get("government_organization", "").split(" / ")[0].strip(),
             "name": r["name_ai_system_en"].strip(), "what": _short(r.get("description_ai_system_en", "")),
             "users": r.get("ai_system_primary_users_en", "").strip(), "by": r.get("developed_by_en", "").strip(),
             "vendor": r.get("vendor_information", "").strip(), "status": status(r.get("ai_system_status_en", "")),
             "personal": r.get("involves_personal_information", "").strip()}
            for r in _csv(fetcher(url)) if (r.get("name_ai_system_en") or "").strip()]
    return {"rows": rows}


def read_nl(fetcher, today: date) -> dict:
    """The Dutch Algorithm Register's own download: every algorithm registered."""
    rows = [{"body": r["organization"].strip(), "name": r["name"].strip(), "what": _short(r.get("description_short", "")),
             "area": NL_AREAS.get(r.get("category", "").split(",")[0].strip(), r.get("category", "").split(",")[0].strip()),
             "status": NL_STATUSES.get(r.get("status", "").strip(), r.get("status", "").strip()),
             "kind": NL_KINDS.get(r.get("publication_category", ""), r.get("publication_category", "")),
             "vendor": " ".join(r.get("provider", "").split()), "id": r.get("algorithm_id", "").strip()}
            for r in _csv(fetcher(NL_CSV)) if (r.get("name") or "").strip()]
    return {"rows": rows}


def read_uk(fetcher, today: date) -> dict:
    """Every algorithmic transparency record on GOV.UK, through its search API. A title is "Body: Tool"."""
    rows = []
    for r in json.loads(fetcher(UK_API)).get("results") or []:
        if not (r.get("title") and r.get("link")):
            continue
        body, _, tool = r["title"].partition(":")
        body, tool = (body.strip(), tool.strip()) if tool.strip() else ("", r["title"].strip())
        rows.append({"body": body, "name": tool, "what": _short(r.get("description") or ""),
                     "day": (r.get("public_timestamp") or "")[:10],
                     "url": "https://www.gov.uk" + r["link"] if r["link"].startswith("/") else r["link"]})
    return {"rows": sorted(rows, key=lambda r: r["day"], reverse=True)}


READERS = {"US": read_us, "NL": read_nl, "CA": read_ca, "UK": read_uk}


def health_name(place: str) -> str:
    return f"What governments use AI for: {PLACES[place][4]} ({place})"


def refresh(conn, fetcher=feeds.fetch, now: datetime | None = None) -> str:
    """Read each list again once a day. A list that can't be read keeps the rows last read, and is logged in the
    sources table like a news source, so one failing 3 runs in a row reaches the project inbox
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
            saved[place] = {"read": now.strftime("%Y-%m-%dT%H:%MZ"), **got}
            said.append(f"{place} {len(got.get('rows') or [])}")
            store.record_source(conn, health_name(place), PLACES[place][3], ok=True, entries=len(got.get("rows") or []))
        except Exception as e:
            said.append(f"{place} not read ({e})")
            store.record_source(conn, health_name(place), PLACES[place][3], ok=False, error=str(e) or type(e).__name__)
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (KEY, json.dumps(saved)))
    conn.commit()
    return ", ".join(said)


def load(conn) -> dict:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (KEY,)).fetchone() if conn else None
    return json.loads(row[0]) if row else {}


# --- what the page says about each list ---

def _when(d: str) -> str:
    y, m, day = d[:10].split("-")
    return f"{int(day)} {_MONTHS[int(m) - 1]} {y}"


def suppliers(rows: list[dict]) -> dict[str, int]:
    """How many entries name each supplier, in their supplier field or (a product) in their name."""
    out = {}
    for v, (field, name) in SUPPLIERS.items():
        fx, nx = re.compile(field, re.I), re.compile(name, re.I)
        out[v] = sum(bool(fx.search(r.get("vendor", "")) or nx.search(r["name"])) for r in rows)
    return out


def _touch(place: str, rows: list[dict]) -> list[dict]:
    """The entries that touch people, by each list's own answer: US high-impact uses in use or on trial; Canadian
    systems the public uses; Dutch high-risk AI systems; for the UK, every record (each is a tool the public meets or
    one that informs decisions about people, by the standard's own scope)."""
    if place == "US":
        return [r for r in rows if r["impact"] == US_HIGH and r["stage"] in ("Deployed", "Pilot")]
    if place == "CA":
        return [r for r in rows if r["users"] in CA_PUBLIC]
    if place == "NL":
        return [r for r in rows if r["kind"] == NL_HIGH]
    return rows


def _top(counter: collections.Counter) -> tuple[str, int]:
    k = [(a, n) for a, n in counter.most_common() if a and a != "Other"]
    return k[0] if k else ("", 0)


def _facts(place: str, rows: list[dict], today: date) -> tuple[str, str, list[tuple[str, str]]]:
    """A card's big number, what it counts, and three facts, each saying what it counts."""
    touch = len(_touch(place, rows))
    if place == "US":
        area, n_area = _top(collections.Counter(r["area"] for r in rows))
        body, n_body = _top(collections.Counter(r["body"] for r in rows))
        return f"{len(rows):,}", f"AI uses at {len({r['body'] for r in rows})} federal agencies", [
            ("High-impact (the agency's own flag), in use or on trial", f"<b>{touch:,}</b>"),
            ("Biggest area", f"{escape(area)} <b>{n_area:,}</b>"), ("Most uses", f"{escape(body)} <b>{n_body:,}</b>")]
    if place == "CA":
        return f"{len(rows):,}", f"AI systems at {len({r['body'] for r in rows})} federal bodies", [
            ("Used by the public", f"<b>{touch:,}</b>"),
            ("Use personal information", f"<b>{sum(r['personal'] == 'Y' for r in rows):,}</b>"),
            ("In production", f"<b>{sum(r['status'] == 'In production' for r in rows):,}</b>")]
    if place == "NL":
        area, n_area = _top(collections.Counter(r["area"] for r in rows))
        return f"{len(rows):,}", "algorithms, every level of government", [
            ("High-risk AI under the EU AI Act (the body's own mark)", f"<b>{touch:,}</b>"),
            ("Biggest area", f"{escape(area)} <b>{n_area:,}</b>"),
            ("In use", f"<b>{sum(r['status'] == 'In use' for r in rows):,}</b>")]
    bodies = collections.Counter(r["body"] for r in rows if r["body"])
    most = bodies.most_common(1)[0][1] if bodies else 0
    tops = [b for b, n in bodies.most_common() if n == most][:2]
    first = min((r["day"][:4] for r in rows if r["day"]), default="")
    return f"{len(rows):,}", f"transparency records since {first}", [
        (f"Published in {today.year}", f"<b>{sum(r['day'][:4] == str(today.year) for r in rows):,}</b>"),
        ("Most records", f"{escape(' and '.join(tops))} <b>{most}</b>{' each' * (len(tops) > 1)}"),
        ("Newest", _when(rows[0]["day"]) if rows and rows[0]["day"] else "–")]


# --- the main page ---

def _who(saved: dict) -> str:
    full = [(p, PLACES[p], saved[p]["rows"]) for p in PLACES if saved.get(p, {}).get("rows")]
    full.sort(key=lambda x: -len(x[2]))
    unit = {"US": "uses", "NL": "algorithms", "CA": "systems", "UK": "records"}
    rows = [f'<tr><td><img src="flags/{fl}.svg" alt="" class="gv-f"><b>{escape(name)}</b></td>'
            f'<td><a href="{escape(url, quote=True)}" rel="noopener">{escape(reg)}</a><span class="fx-c">{escape(kept)}</span></td>'
            f'<td class="gv-n">{len(rows):,} {unit[p]}</td><td><span class="pc-k gv-live">{FULL_TAG[p]}</span></td>'
            f'<td><a class="gv-go" href="{PATH}{sub}">Explore →</a></td></tr>'
            for p, (sub, fl, name, url, reg, kept), rows in full]
    rows += [f'<tr><td><img src="flags/{fl}.svg" alt="" class="gv-f"><b>{escape(name)}</b></td>'
             f'<td><a href="{escape(url, quote=True)}" rel="noopener">{escape(reg)}</a><span class="fx-c">{escape(kept)}</span></td>'
             f'<td class="gv-n">{escape(n)}</td><td><span class="pc-k gv-trial">{escape(tag)}</span></td>'
             f'<td class="gv-chk">Checked {_when(day)}</td></tr>'
             for name, fl, reg, url, n, kept, tag, day in OTHERS]
    return ('<h2 class="gv-h">Who tells you</h2><p class="gv-sub">Every government list of its own AI we found. The '
            "first ones are read in full every day; the others are checked by hand.</p>"
            '<div class="gv-scroll"><table class="gv-who"><thead><tr><th>Government</th><th>Its list</th><th>Holds</th>'
            "<th>What it covers</th><th></th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>\n")


def _whose(counts: dict[str, dict[str, int]]) -> str:
    """Suppliers (rows) by list (columns): a dot whose area grows with the number of entries, and the number."""
    places = [p for p in NAMES_SUPPLIER if p in counts]
    biggest = max([n for c in counts.values() for n in c.values()] or [1]) or 1
    order = sorted(SUPPLIERS, key=lambda v: -sum(counts[p][v] for p in places))

    def cell(n: int) -> str:
        if not n:
            return '<td class="gv-z">–</td>'
        d = 8 + 34 * math.sqrt(n / biggest)
        return f'<td><span class="gv-dot" style="width:{d:.0f}px;height:{d:.0f}px"></span><b>{n:,}</b></td>'
    head = "".join(f'<th><img src="flags/{PLACES[p][1]}.svg" alt="" class="gv-f">{escape(PLACES[p][2])}</th>' for p in places)
    body = "".join(f'<tr><th scope="row">{escape(v)}</th>' + "".join(cell(counts[p][v]) for p in places) + "</tr>"
                   for v in order if any(counts[p][v] for p in places))
    return ('<h2 class="gv-h">Whose AI they run</h2><p class="gv-sub">Entries naming each company or one of its AI '
            "products (Copilot, ChatGPT, Gemini, AWS…) as supplier or in their name, in the lists that name a supplier. "
            "One entry can name two (Azure OpenAI counts for Microsoft and OpenAI).</p>"
            f'<table class="gv-whose"><thead><tr><th></th>{head}</tr></thead><tbody>{body}</tbody></table>\n')


def _card(place: str, rows: list[dict], today: date) -> str:
    sub, flag, name = PLACES[place][:3]
    big, unit, facts = _facts(place, rows, today)
    touch = _touch(place, rows)
    picked = [r for n in EXAMPLES.get(place, []) for r in touch if r["name"] == n][:3] or touch[:3]
    ex = "".join(f'<li><b>{escape(r["body"] or r.get("ag", ""))}</b> · <span{" lang=nl" * (place == "NL")}>'
                 f'{escape(r["name"])}</span><span class="fx-c"{" lang=nl" * (place == "NL")}>{escape(_short(r["what"], 95))}</span></li>'
                 for r in picked)
    fa = "".join(f"<tr><td>{escape(a)}</td><td>{b}</td></tr>" for a, b in facts)
    return (f'<section class="pc-half gv-card gv-{place.lower()}"><div class="pc-hh"><h2><img src="flags/{flag}.svg" '
            f'alt="" class="gv-f">{escape(name)}</h2></div><div class="pc-in"><p class="gv-big"><b>{big}</b> '
            f'{escape(unit)}</p><table class="gv-facts">{fa}</table>'
            + (f'<h3>Uses that touch people</h3><ul class="gv-ex">{ex}</ul>' if ex else "")
            + f'<a class="gv-all" href="{PATH}{sub}">See all {len(rows):,} →</a></div></section>')


def _lead(saved: dict, counts: dict[str, dict[str, int]]) -> str:
    full = [p for p in PLACES if saved.get(p, {}).get("rows")]
    out = (f"<b>{len(full)} governments</b> publish a full list of the AI they use as open data; {len(OTHERS)} more "
           "publish part of one, or a count.")
    tops = {p: max(counts[p], key=counts[p].get) for p in counts if any(counts[p].values())}
    if len(tops) > 1 and len(set(tops.values())) == 1:
        v = next(iter(tops.values()))
        out += (f" In all {len(tops)} that name suppliers, <b>{escape(v)}</b> is named most ("
                + ", ".join(f"{counts[p][v]:,} {adj}" for p, adj in (("US", "US"), ("CA", "Canadian"), ("NL", "Dutch"))
                            if p in tops) + ").")
    return f'<p class="gv-lead">{out}</p>\n'


def _about(read: str) -> str:
    """The notes under each page; `read` is when the lists were last read."""
    limits = [
        ("Counted", "What each government lists, in its own categories. The lists count different things: the US its "
                    "AI uses, Canada its AI systems, the Netherlands every algorithm (AI or not), the UK the tools a "
                    "public body published a record for."),
        ("Uses that touch people", "Each list's own answer: US uses the agency calls high-impact (they can affect "
                                   "people's rights or safety) that are in use or on trial; Canadian systems the public "
                                   "uses; Dutch systems the body marked as high-risk AI under the EU AI Act; every UK "
                                   "record."),
        ("Suppliers", "Counted from each entry's supplier field and its name, matched to company and product names "
                      "and checked by hand. Entries with no supplier given aren't counted."),
        ("Other lists", "Only lists a government keeps itself. France's inventory is kept by an independent "
                        "observatory and Chile's by a university, so they aren't counted."),
        ("Left out", "Uses an agency kept out of its public list, as the rules allow. The US Department of Defense and "
                     "intelligence agencies aren't in the US inventory."),
    ]
    if read:
        limits.append(("Last read", f"{_when(read)}, {read[11:16]} UTC (once a day)"))
    return ('<section class="jb-lim"><h2>About these counts</h2>\n<table class="mt jb-small jb-limits"><tbody>'
            + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
            + "</tbody></table></section>\n")


def body(saved: dict, today: date) -> str:
    counts = {p: suppliers(saved[p]["rows"]) for p in NAMES_SUPPLIER if saved.get(p, {}).get("rows")}
    cards = "".join(_card(p, saved[p]["rows"], today) for p in PLACES if saved.get(p, {}).get("rows"))
    return ('<div class="ft pc gv">\n'
            + pages.feature_head(PATH, "What governments use AI for",
                                 "Which jobs do governments give to AI, and whose AI do they run?",
                                 "From the lists governments publish of the AI they use: every one we found, four "
                                 "read in full every day, each in its own words.")
            + _lead(saved, counts) + _who(saved) + (_whose(counts) if counts else "")
            + '<h2 class="gv-h">The full lists</h2><p class="gv-sub">Each government\'s own numbers, by its own '
              f'definitions.</p><div class="gv-cards">{cards}</div>\n'
            + _about(max((v.get("read", "") for v in saved.values()), default="")) + "</div>\n")


# --- each list's own page: every entry, with Excel-style filters ---

def _cell(text: str, f: str | None = None, cls: str = "") -> str:
    fv = f' data-f="{escape(f or "–", quote=True)}"' if f is not None else ""
    return f'<td{fv}{f" class={cls}" if cls else ""}>{text or "–"}</td>'


def _tag(text: str, cls: str) -> str:
    return f'<span class="pc-k {cls}">{escape(text)}</span>' if text else "–"


def _table_rows(place: str, rows: list[dict]) -> tuple[list[str], str]:
    live = {"Deployed": "gv-live", "In production": "gv-live", "In use": "gv-live",
            "Pilot": "gv-trial", "In development": "gv-trial", "Being built": "gv-trial"}
    if place == "US":
        order = {s: i for i, s in enumerate(US_STAGES)}
        rows = sorted(rows, key=lambda r: (r["impact"] != US_HIGH, order.get(r["stage"], 9), r["body"], r["name"]))
        head = ["Agency", "AI use and what it does", "Used for", "Kind of AI", "Stage", "High-impact"]
        trs = "".join(
            "<tr>" + _cell(f'<b title="{escape(r["body"])}">{escape(r["ag"] or r["body"])}</b>'
                           f'<span class="fx-c">{escape(r["body"])}</span>', r["body"])
            + _cell(f'{escape(r["name"])}<span class="fx-c">{escape(r["what"])}</span>')
            + _cell(escape(r["area"]), r["area"]) + _cell(escape(r["kind"]), r["kind"])
            + _cell(_tag(r["stage"], live.get(r["stage"], "gv-off")), r["stage"])
            + _cell(_tag(r["impact"], "gv-high") if r["impact"] == US_HIGH else escape(r["impact"]), r["impact"]) + "</tr>"
            for r in rows)
    elif place == "CA":
        rows = sorted(rows, key=lambda r: (r["users"] not in CA_PUBLIC, r["status"] != "In production", r["body"], r["name"]))
        head = ["Public body", "AI system and what it does", "Used by", "Supplier", "Status"]
        trs = "".join(
            "<tr>" + _cell(f'<b>{escape(r["body"])}</b>', r["body"])
            + _cell(f'{escape(r["name"])}<span class="fx-c">{escape(r["what"])}</span>')
            + _cell(escape(r["users"]), r["users"]) + _cell(escape(r["vendor"] or r["by"]), r["vendor"] or r["by"])
            + _cell(_tag(r["status"], live.get(r["status"], "gv-off")), r["status"]) + "</tr>"
            for r in rows)
    elif place == "NL":
        kinds = {k: i for i, k in enumerate(NL_KINDS.values())}
        rows = sorted(rows, key=lambda r: (kinds.get(r["kind"], 9), r["status"] != "In use", r["body"], r["name"]))
        head = ["Public body", "Algorithm and what it does", "Kind", "Area", "Status"]
        trs = "".join(
            "<tr>" + _cell(f'<b>{escape(r["body"])}</b>', r["body"])
            + _cell(f'<a href="{escape(NL_ENTRY.format(id=r["id"]), quote=True)}" rel="noopener" lang="nl">'
                    f'{escape(r["name"])}</a><span class="fx-c" lang="nl">{escape(r["what"])}</span>')
            + _cell(_tag(r["kind"], "gv-high") if r["kind"] == NL_HIGH else escape(r["kind"]), r["kind"])
            + _cell(escape(r["area"]), r["area"]) + _cell(_tag(r["status"], live.get(r["status"], "gv-off")), r["status"])
            + "</tr>" for r in rows)
    else:
        head = ["Published", "Public body", "Tool and what it does"]
        trs = "".join(
            "<tr>" + _cell(_when(r["day"]) if r["day"] else "", r["day"][:4], "pc-d") + _cell(f'<b>{escape(r["body"])}</b>', r["body"])
            + _cell(f'<a href="{escape(r["url"], quote=True)}" rel="noopener">{escape(r["name"])}</a>'
                    f'<span class="fx-c">{escape(r["what"])}</span>') + "</tr>"
            for r in rows)
    return head, trs


def place_body(place: str, data: dict, today: date) -> str:
    sub, flag, name, url, reg, kept = PLACES[place]
    rows = data["rows"]
    big, unit, facts = _facts(place, rows, today)
    head, trs = _table_rows(place, rows)
    nofilter = {"AI use and what it does", "AI system and what it does", "Algorithm and what it does", "Tool and what it does"}
    ths = "".join(f'<th{" data-nof" * (h in nofilter)}{" data-seen" * (h == "Published")}>{h}</th>' for h in head)
    first = {"US": "high-impact uses first", "CA": "systems the public uses first", "NL": "high-risk AI first",
             "UK": "newest first"}[place]
    dutch = " Names and descriptions are in Dutch, as registered." if place == "NL" else ""
    return ('<div class="ft pc gv">\n'
            + pages.band("policy", f'<img src="flags/{flag}.svg" alt="">', f"photos/cartoons/features/{PATH.strip('/')}.svg",
                         f"What {_the(name)} uses AI for", f"Every entry in the {reg}.",
                         f'From the <a href="{escape(url, quote=True)}" rel="noopener">{escape(reg)}</a>, kept by '
                         f"{escape(kept)}.{dutch} Pick a ▾ to filter.")
            + f'<p class="gv-lead"><b>{big}</b> {escape(unit)}.</p><table class="gv-facts gv-wide">'
            + "".join(f"<tr><td>{escape(a)}</td><td>{b}</td></tr>" for a, b in facts) + "</table>"
            f'<h2 class="gv-h">Every entry, {first}</h2><div class="iw"><div class="iw-fbar"></div>'
            f'<p class="iw-count" aria-live="polite">Showing <b>{len(rows):,}</b> of {len(rows):,}. Pick a ▾ to filter. '
            '<button type="button" class="iw-clear" hidden>Clear filters</button></p><div class="gv-sc">'
            f'<table class="pc-rows xf-t gv-t gv-{place.lower()}-t"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody>'
            f'</table></div></div>\n' + _about(data.get("read", "")) + "</div>\n" + infra_watch.SCRIPT + "\n")


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write the page and each full list's own page from the lists last read. Returns their paths, or nothing before
    any list was read."""
    saved = load(conn)
    if not any(v.get("rows") for v in saved.values()):
        return []
    what = ("Which jobs do governments give to AI, and whose AI do they run? From the lists governments publish of the "
            "AI they use: the US, Canada, the Netherlands and the UK in full, and the others we found.")
    written = []
    for path, title, desc, html_body, back in [
        (PATH, "What governments use AI for", what, body(saved, today), ("/policy/", "Back to Policy")),
        *[(PATH + PLACES[p][0], f"What {_the(PLACES[p][2])} uses AI for",
           f"Every entry in the {PLACES[p][4]}, kept by {PLACES[p][5]}, with filters.",
           place_body(p, saved[p], today), (f"/{PATH}", "Back to What governments use AI for"))
          for p in PLACES if saved.get(p, {}).get("rows")]]:
        data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc,
                "url": f"{rss.SITE}{path}"}
        (out / path).mkdir(parents=True, exist_ok=True)
        (out / path / "index.html").write_text(
            pages.page(f"{title} · AI Pulse", desc, path, html_body, data, pages.frame(conn, len(cards)), back,
                       "Every entry is the government's own, in its own words."),
            encoding="utf-8")
        written.append(path)
    return written
