"""Follow AI bills through their lifecycle from official sources.

- US Congress: the congress.gov API, with a free personal key (https://api.congress.gov/sign-up/, name and
  email only; set CONGRESS_API_KEY). Without one it's skipped: api.data.gov's DEMO_KEY is only for trying the
  API before signing up, not for a site that runs every 6 hours. Each collection reads the current Congress's
  bills updated since the last sync, keeps those with AI in the title, and reads their official actions.
- EU: the European Parliament's open data API (no key). AI procedures are found by their English title;
  their events give the stages.
- UK: the UK Parliament Bills API (no key; Open Parliament Licence). AI bills are found by title searches;
  their readings in each House give the stages.
- Canada: LEGISinfo (Parliament of Canada; no key). Each session's bills with their reading dates. The
  Speaker permits accurate, non-commercial reproduction that isn't presented as official.
- Brazil: the Chamber of Deputies' open data API (no key; published for reuse in apps). AI bills are found by
  keyword and their Portuguese summary; bills attached to a lead bill ("tramitando em conjunto") move with it
  and aren't shown separately. Their procedural events give the stages.
- China: the Cyberspace Administration of China's policy and regulation lists (robots.txt allows them; no API).
  Only each AI regulation's official title, date and link are read; the title is shown in English
  (machine translation) and nothing else is copied. Official regulations aren't copyrighted in China
  (Copyright Law, Article 5). The national law database (flk.npc.gov.cn) forbids automated access and
  gov.cn's search is closed to it, so neither is used.
- India: the Parliament of India's legislation API (sansad.in, the one its own bill pages use; no key).
  Bills in both Houses with their introduction, passing and assent dates. India Code, MeitY and PIB turn
  away automated requests, so they aren't used.
- Japan: the e-Gov law API (Digital Agency; no key). Laws and cabinet orders with 人工知能 (AI) in the
  title, with promulgation and enforcement dates. Government of Japan Standard Terms of Use 2.0: the source
  is credited on the page, and the titles are marked as machine-translated (an edit).
- Australia: the Federal Register of Legislation API (no key; CC BY 4.0, credited on the page). It holds Acts
  and instruments once made (bills in Parliament aren't there), so these cards start at assent.

Every bill has one tracker card (an item with source "congress.gov" or "European Parliament"), dated at
its latest stage so it moves up the feed when it advances. The card shows the whole timeline. News
stories that name the bill (by number, or by short title) are attached to that card.

State legislatures need an Open States API key and aren't connected yet; the OECD.AI policy database
has no public API.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone

from . import feeds, store, translate

# Cards made from official records; the keyword rules for news stories never re-sort them.
OFFICIAL_SOURCES = ("congress.gov", "European Parliament", "UK Parliament", "Parliament of Canada",
                    "Câmara dos Deputados", "legislation.gov.au", "Cyberspace Administration of China",
                    "Parliament of India", "e-Gov (Japan)", "National Legal Database (Vietnam)", "Swiss Parliament", "Parliament of Malaysia",
                    "Legislative Yuan (Taiwan)", "National Law Information Center (Korea)",
                    "OECD.AI")

# Lifecycle, in order. A bill's stage is the furthest one reached; vetoed / withdrawn end it.
STAGES = ["introduced", "passed_chamber", "passed_legislature", "signed", "in_force"]
ENDED = ["vetoed", "withdrawn"]
LABELS = {
    "US": {"introduced": "Introduced", "passed_chamber": "Passed one chamber", "passed_legislature": "Passed Congress",
           "signed": "Signed", "in_force": "Became law", "vetoed": "Vetoed", "withdrawn": "Withdrawn"},
    "EU": {"introduced": "Proposed", "passed_chamber": "Parliament position", "passed_legislature": "Final vote",
           "signed": "Signed", "in_force": "Published in Official Journal", "vetoed": "Rejected",
           "withdrawn": "Withdrawn"},
    "GB": {"introduced": "Introduced", "passed_chamber": "Passed first House", "passed_legislature": "Passed both Houses",
           "signed": "Royal Assent", "in_force": "In force", "vetoed": "Defeated", "withdrawn": "Withdrawn"},
    "CA": {"introduced": "First reading", "passed_chamber": "Passed first chamber",
           "passed_legislature": "Passed both chambers", "signed": "Royal Assent", "in_force": "In force",
           "vetoed": "Defeated", "withdrawn": "Died on the Order Paper"},
    "BR": {"introduced": "Introduced", "passed_chamber": "Passed first chamber", "passed_legislature": "Passed Congress",
           "signed": "Became law", "in_force": "In force", "vetoed": "Vetoed", "withdrawn": "Withdrawn or archived"},
    "CN": {"introduced": "Draft for comment", "passed_chamber": "Revised draft", "passed_legislature": "Adopted",
           "signed": "Issued", "in_force": "In force", "vetoed": "Withdrawn", "withdrawn": "Repealed"},
    "IN": {"introduced": "Introduced", "passed_chamber": "Passed one House", "passed_legislature": "Passed both Houses",
           "signed": "Assent", "in_force": "In force", "vetoed": "Negatived", "withdrawn": "Withdrawn"},
    "JP": {"introduced": "Submitted", "passed_chamber": "Passed one House", "passed_legislature": "Passed the Diet",
           "signed": "Promulgated", "in_force": "In force", "vetoed": "Rejected", "withdrawn": "Repealed"},
    "VN": {"introduced": "Draft", "passed_chamber": "Passed", "passed_legislature": "Adopted",
           "signed": "Issued", "in_force": "In force", "vetoed": "Rejected", "withdrawn": "Repealed"},
    "CH": {"introduced": "Submitted", "passed_chamber": "Adopted by one council",
           "passed_legislature": "Adopted by Parliament", "signed": "Enacted", "in_force": "In force",
           "vetoed": "Rejected", "withdrawn": "Closed"},
    "MY": {"introduced": "First reading", "passed_chamber": "Passed Dewan Rakyat",
           "passed_legislature": "Passed Dewan Negara", "signed": "Royal Assent", "in_force": "In force",
           "vetoed": "Rejected", "withdrawn": "Withdrawn"},
    "TW": {"introduced": "Introduced", "passed_chamber": "Passed", "passed_legislature": "Passed the Legislative Yuan",
           "signed": "Promulgated", "in_force": "In force", "vetoed": "Rejected", "withdrawn": "Repealed"},
    "KR": {"introduced": "Introduced", "passed_chamber": "Passed", "passed_legislature": "Passed the National Assembly",
           "signed": "Promulgated", "in_force": "In force", "vetoed": "Rejected", "withdrawn": "Repealed"},
    "AU": {"introduced": "Introduced", "passed_chamber": "Passed first House", "passed_legislature": "Passed Parliament",
           "signed": "Assented or made", "in_force": "In force", "vetoed": "Disallowed", "withdrawn": "Repealed"},
}

AI_TITLE = re.compile(r"artificial intelligence|\bAI\b|machine learning|algorithm|deepfake|automated decision|"
                      r"chatbot|digital replica|2024/1689", re.I)

SCHEMA = """
CREATE TABLE IF NOT EXISTS bills (
    key          TEXT PRIMARY KEY,   -- "US-119-hr-10538", "EU-2021-0106"
    jurisdiction TEXT NOT NULL,      -- US / EU
    number       TEXT NOT NULL,      -- "H.R. 10538", "2021/0106(COD)"
    title        TEXT NOT NULL,
    short_title  TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL,      -- the official page
    stage        TEXT NOT NULL,
    stage_date   TEXT NOT NULL,
    history      TEXT NOT NULL,      -- JSON [{date, stage, text}], first time each stage was reached
    source       TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS eu_procedures (   -- every procedure checked once, so discovery stays cheap
    id    TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    is_ai INTEGER NOT NULL
);
"""


def connect_tables(conn) -> None:
    conn.executescript(SCHEMA)
    if "summary" not in {r[1] for r in conn.execute("PRAGMA table_info(bills)")}:
        conn.execute("ALTER TABLE bills ADD COLUMN summary TEXT NOT NULL DEFAULT ''")


# --- Stages from official records ---

_US_TYPES = {"HR": ("H.R.", "house-bill"), "S": ("S.", "senate-bill"),
             "HJRES": ("H.J.Res.", "house-joint-resolution"), "SJRES": ("S.J.Res.", "senate-joint-resolution")}
_US_RULES = [  # (stage, pattern on the action text); checked for every action
    ("introduced", re.compile(r"^Introduced in (the )?(House|Senate)", re.I)),
    ("passed_chamber", re.compile(r"Passed/agreed to in (House|Senate)|^Passed (House|Senate)", re.I)),
    ("passed_legislature", re.compile(r"Presented to President|Cleared for White House", re.I)),
    ("signed", re.compile(r"Signed by President", re.I)),
    ("in_force", re.compile(r"Became Public Law|Became Private Law", re.I)),
    ("vetoed", re.compile(r"Vetoed by President|Pocket Vetoed", re.I)),
]


def us_history(actions: list[dict]) -> list[dict]:
    """Lifecycle from congress.gov actions: the first date each stage was reached, oldest first."""
    reached: dict[str, dict] = {}
    chambers: set[str] = set()
    for a in sorted(actions, key=lambda a: a.get("actionDate", "")):
        text = a.get("text", "")
        for stage, rule in _US_RULES:
            m = rule.search(text)
            if not m:
                continue
            if stage == "passed_chamber":
                chambers.add((m.group(1) or m.group(2) or "").lower())
                if len(chambers) == 2 and "passed_legislature" not in reached:
                    reached["passed_legislature"] = {"date": a["actionDate"], "stage": "passed_legislature",
                                                     "text": "Passed both House and Senate"}
            reached.setdefault(stage, {"date": a["actionDate"], "stage": stage, "text": text[:200]})
    return sorted(reached.values(), key=lambda h: (h["date"], (STAGES + ENDED).index(h["stage"])))


_EU_ACTIVITY = {  # European Parliament activity type -> stage
    "REFERRAL": "introduced",
    "PLENARY_VOTE": "passed_chamber",  # the first plenary vote; a later one after a deal is the final vote
    "SIGNATURE": "signed",
    "PUBLICATION_OFFICIAL_JOURNAL": "in_force",
    "WITHDRAWAL": "withdrawn",
    "PLENARY_REJECT": "vetoed",
}


def eu_history(procedure: dict) -> list[dict]:
    reached: dict[str, dict] = {}
    deal = False
    for e in sorted(procedure.get("consists_of", []), key=lambda e: e.get("activity_date") or ""):
        kind = (e.get("had_activity_type") or "").rsplit("/", 1)[-1]
        when = e.get("activity_date")
        if not when:
            continue
        if kind == "COMMITTEE_APPROVE_PROVISIONAL_AGREEMENT":
            deal = True
        stage = _EU_ACTIVITY.get(kind)
        if kind == "PLENARY_VOTE" and deal:
            stage = "passed_legislature"
        if stage:
            reached.setdefault(stage, {"date": when, "stage": stage, "text": kind.replace("_", " ").capitalize()})
    return sorted(reached.values(), key=lambda h: (h["date"], (STAGES + ENDED).index(h["stage"])))


def current(history: list[dict]) -> dict | None:
    """The furthest stage reached (an ending wins), with its date."""
    ended = [h for h in history if h["stage"] in ENDED]
    if ended:
        return ended[-1]
    reached = [h for h in history if h["stage"] in STAGES]
    return max(reached, key=lambda h: STAGES.index(h["stage"])) if reached else None


# --- Storing bills and their tracker cards ---

_TAGS = re.compile(r"<[^>]+>")
_HEADING = re.compile(r"^\s*(<p>)?\s*<(strong|b)>.*?</(strong|b)>\s*(</p>)?", re.S | re.I)


def describe(text: str, title: str = "") -> str:
    """An official description (a CRS summary, a long title) as one or two plain sentences, or ""."""
    from . import brief
    text = _HEADING.sub("", text or "")  # CRS summaries open with the bill's name in bold
    text = re.sub(r"\s+", " ", _TAGS.sub(" ", text)).strip()
    if title and text.lower().startswith(title.lower()):
        text = text[len(title):].lstrip(" .:-")
    return brief.clean_summary(text, title) if text else ""


def upsert(conn, bill: dict) -> bool:
    """Save a bill and its tracker card. Returns True if its stage changed (or it's new)."""
    now = current(bill["history"])
    if not now:
        return False
    prev = conn.execute("SELECT stage, stage_date FROM bills WHERE key = ?", (bill["key"],)).fetchone()
    changed = not prev or (prev[0], prev[1]) != (now["stage"], now["date"])
    if not bill.get("summary") and prev:  # a sync without a description keeps the one found before
        kept = conn.execute("SELECT summary FROM bills WHERE key = ?", (bill["key"],)).fetchone()
        bill = {**bill, "summary": kept[0] if kept else ""}
    conn.execute(
        "INSERT OR REPLACE INTO bills (key, jurisdiction, number, title, short_title, url, stage, stage_date, history,"
        " source, updated_at, summary) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (bill["key"], bill["jurisdiction"], bill["number"], bill["title"], bill.get("short_title", ""), bill["url"],
         now["stage"], now["date"], json.dumps(bill["history"]), bill["source"],
         datetime.now(timezone.utc).isoformat(timespec="seconds"), bill.get("summary", "")))
    name = bill.get("short_title") or bill["title"]
    # What the bill does, not its stages: those are on the card's timeline.
    summary = bill.get("summary", "")
    if bill["jurisdiction"] == "US":
        name = _US_OTHER.sub("", name)
        summary = summary or us_interim(conn, bill)
    lang = bill.get("lang")  # an official record in another language: its English version, if made
    english = lang and translate.cached(conn, lang, bill["title"])
    if english:
        name = english
        summary = (summary + " " if summary else "") + \
            f"Machine-translated from {translate.LANGUAGE_NAMES[lang]}; the official text is linked."
    title = f"{bill['number']}: {name}" if bill["number"] else name
    if len(title) > 220:  # long official summaries: cut at a word
        title = title[:219].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    item = {"title": title, "summary": summary, "url": bill["url"], "source": bill["source"],
            "category": "regulation", "date": now["date"],
            # A law stays a law once enacted, even if later repealed.
            "action": "law" if any(h["stage"] in ("signed", "in_force") for h in bill["history"]) else "proposal",
            "jurisdictions": [bill["jurisdiction"]], "tags": []}
    if store.exists(conn, item["url"]):
        conn.execute("UPDATE items SET title = ?, summary = ?, date = ?, category = 'regulation', action = ?,"
                     " jurisdictions = ?, bill = ? WHERE id = ?",
                     (item["title"], item["summary"], item["date"], item["action"],
                      ",".join(item["jurisdictions"]), bill["key"], store.item_id(item["url"])))
    else:
        store.insert(conn, item)
        conn.execute("UPDATE items SET bill = ? WHERE id = ?", (bill["key"], store.item_id(item["url"])))
    return changed


def lifecycle(conn, key: str) -> dict | None:
    """What a card shows: every stage with its date (or none yet), and where the bill is now."""
    row = conn.execute("SELECT * FROM bills WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    history = json.loads(row["history"])
    labels = LABELS[row["jurisdiction"]]
    when = {h["stage"]: h["date"] for h in history}
    now = current(history)
    steps = [{"stage": s, "label": labels[s], "date": when.get(s)} for s in STAGES]
    ended = [h for h in history if h["stage"] in ENDED]
    if ended:
        steps.append({"stage": ended[-1]["stage"], "label": labels[ended[-1]["stage"]], "date": ended[-1]["date"]})
    return {"key": key, "number": row["number"], "url": row["url"], "source": row["source"],
            "current": now["stage"] if now else None, "steps": steps}


# --- US Congress (congress.gov) ---

CONGRESS_API = "https://api.congress.gov/v3"


def _congress_key() -> str:
    return os.environ.get("CONGRESS_API_KEY", "")


def _get_json(url: str, fetcher=feeds.fetch) -> dict:
    return json.loads(fetcher(url))


def _crs_summary(congress, kind: str, number, title: str, key: str, fetcher=feeds.fetch) -> str:
    """The Congressional Research Service's latest summary of a bill (a US government work), or "" (CRS
    writes one some weeks after a bill is introduced)."""
    try:
        data = _get_json(f"{CONGRESS_API}/bill/{congress}/{kind.lower()}/{number}/summaries?format=json&api_key={key}",
                         fetcher)
    except Exception:
        return ""
    found = sorted(data.get("summaries") or [], key=lambda s: s.get("updateDate") or "")
    return describe(found[-1].get("text", ""), title) if found else ""


def _us_describe_old(conn, key: str, fetcher=feeds.fetch, limit: int = 40) -> None:
    """Look up CRS summaries for stored US bills that don't have one yet, a few per run, each at most weekly."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    # Bills with no context yet (sponsor, committee) are read at once; the rest at most weekly.
    rows = conn.execute("SELECT * FROM bills WHERE jurisdiction = 'US' AND summary = '' AND (key NOT IN"
                        " (SELECT substr(key, 11) FROM meta WHERE key LIKE 'crs-tried:%' AND value > ?) OR key NOT IN"
                        " (SELECT substr(key, 12) FROM meta WHERE key LIKE 'us-context:%')) LIMIT ?",
                        (week_ago, limit)).fetchall()
    for r in rows:
        _, congress, kind, number = r["key"].split("-")
        text = _crs_summary(congress, kind, number, r["title"], key, fetcher)
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (f"crs-tried:{r['key']}", date.today().isoformat()))
        short = r["short_title"] if text else (_us_remember_context(conn, r["key"], congress, kind, number, key, fetcher)
                                               or r["short_title"])
        upsert(conn, {"key": r["key"], "jurisdiction": "US", "number": r["number"], "title": r["title"],
                      "short_title": short, "url": r["url"], "source": r["source"],
                      "history": json.loads(r["history"]), "summary": text})
        conn.commit()
        time.sleep(0.2)


_US_OTHER = re.compile(r",? and for other purposes\.?$|\.$")
_US_PURPOSE = re.compile(r"^(?:A (?:bill|joint resolution|concurrent resolution|resolution) )?to (.+?)(?:,? and for other purposes)?\.?$",
                         re.I)


def us_purpose(title: str) -> str:
    """What a bill would do, from its official title: "A bill to establish X, and for other purposes." ->
    "Would establish X." (Resolutions titled "Expressing ..." etc. give "".)"""
    m = _US_PURPOSE.match(title.strip())
    return f"Would {re.sub(r',? and to ', ' and ', m.group(1))}." if m else ""


def _us_context(congress, kind: str, number, key: str, fetcher=feeds.fetch) -> dict:
    """From congress.gov, for a bill CRS hasn't summarised yet: its sponsor, cosponsors, committees and short
    title (a short title appears once the text is published)."""
    base = f"{CONGRESS_API}/bill/{congress}/{kind.lower()}/{number}"
    bill = _get_json(f"{base}?format=json&api_key={key}", fetcher).get("bill") or {}
    committees = _get_json(f"{base}/committees?format=json&api_key={key}", fetcher).get("committees") or []
    titles = _get_json(f"{base}/titles?format=json&api_key={key}", fetcher).get("titles") or []
    sponsor = (bill.get("sponsors") or [{}])[0]
    who = ""
    if sponsor.get("lastName"):
        role = "Sen." if kind.upper().startswith("S") else "Rep."
        who = f"{role} {sponsor.get('firstName', '')} {sponsor['lastName']} ({sponsor.get('party', '')}-{sponsor.get('state', '')})"
    short = next((t["title"] for t in titles if "Short Title" in (t.get("titleType") or "")), "")
    return {"sponsor": re.sub(r"\s+", " ", who).strip(), "cosponsors": (bill.get("cosponsors") or {}).get("count", 0),
            "committees": [f"{c['chamber']} {c['name']}" for c in committees if c.get("chamber") and c.get("name")],
            "short_title": short}


def us_interim(conn, bill: dict) -> str:
    """Until CRS publishes a summary: what the bill would do, who introduced it and where it was sent."""
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (f"us-context:{bill['key']}",)).fetchone()
    ctx = json.loads(row[0]) if row else {}
    parts = [us_purpose(bill["title"])]
    if ctx.get("sponsor"):
        with_co = f" with {ctx['cosponsors']} cosponsor{'s' if ctx['cosponsors'] != 1 else ''}" if ctx.get("cosponsors") else ""
        sent = f"; referred to the {' and the '.join(ctx['committees'])}" if ctx.get("committees") else ""
        parts.append(f"Introduced by {ctx['sponsor']}{with_co}{sent}.")
    return " ".join(p for p in parts if p)


def _us_remember_context(conn, bill_key: str, congress, kind, number, key, fetcher) -> str:
    """Store a bill's context for its interim summary; returns its short title, if it has one yet."""
    try:
        ctx = _us_context(congress, kind, number, key, fetcher)
    except Exception:
        return ""
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (f"us-context:{bill_key}", json.dumps(ctx)))
    return ctx["short_title"]


def _current_congress(today: date) -> int:
    """The 119th Congress runs 2025-2026; a new one starts every odd year."""
    return (today.year - 1789) // 2 + 1


def sync_congress(conn, fetcher=feeds.fetch, since: datetime | None = None, max_pages: int = 40,
                  log=print) -> int:
    """Read the current Congress's bills updated since the last sync, oldest update first, and keep those with
    AI in the title; returns how many AI bills changed stage.

    The place reached is saved after every page, so a run that stops at `max_pages` (or on the rate limit)
    carries on from there next time. A newest-first read restarted from the top each run and never got past
    the latest few thousand updates. The list gives update dates without times and one day can update
    thousands of bills, so the place is a page offset, not a date; a resumed run re-reads one page in case
    bills moved while it was away."""
    connect_tables(conn)
    key = _congress_key()
    if not key:
        log("  congress.gov: skipped, no CONGRESS_API_KEY (the DEMO_KEY is only for trying the API)")
        return 0
    started = datetime.now(timezone.utc)
    congress = _current_congress(started.date())
    saved = conn.execute("SELECT value FROM meta WHERE key = 'congress_cursor'").fetchone()
    cursor = json.loads(saved[0]) if saved else {}
    if since:
        cursor = {"congress": congress, "from": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "offset": 0}
    elif cursor.get("congress") != congress:  # first run, or a new Congress: read it from its first day
        cursor = {"congress": congress, "from": f"{2 * congress + 1787}-01-03T00:00:00Z", "offset": 0}
    offset = max(0, cursor["offset"] - 250)
    changed = pages = 0
    while pages < max_pages:
        data = _get_json(f"{CONGRESS_API}/bill/{congress}?format=json&limit=250&offset={offset}"
                         f"&sort=updateDate+asc&fromDateTime={cursor['from']}&api_key={key}", fetcher)
        pages += 1
        listed = data.get("bills", [])
        for b in listed:
            if b.get("type") not in _US_TYPES or not AI_TITLE.search(b.get("title", "")):
                continue
            acts = _get_json(f"{CONGRESS_API}/bill/{b['congress']}/{b['type'].lower()}/{b['number']}/actions"
                             f"?format=json&limit=250&api_key={key}", fetcher)
            label, path = _US_TYPES[b["type"]]
            bill = {"key": f"US-{b['congress']}-{b['type'].lower()}-{b['number']}", "jurisdiction": "US",
                    "number": f"{label} {b['number']}", "title": b["title"],
                    "url": f"https://www.congress.gov/bill/{b['congress']}th-congress/{path}/{b['number']}",
                    "source": "congress.gov", "history": us_history(acts.get("actions", [])),
                    "summary": _crs_summary(b["congress"], b["type"], b["number"], b["title"], key, fetcher)}
            if not bill["summary"]:
                bill["short_title"] = _us_remember_context(conn, bill["key"], b["congress"], b["type"], b["number"],
                                                           key, fetcher)
            changed += upsert(conn, bill)
            conn.commit()  # keep progress if a later request fails (e.g. the rate limit)
            time.sleep(0.2)
        offset += len(listed)
        done = len(listed) < 250 or not (data.get("pagination") or {}).get("next")
        # Done: next time, read what's updated from now on. Otherwise carry on from this page.
        cursor.update({"from": started.strftime("%Y-%m-%dT%H:%M:%SZ"), "offset": 0} if done else {"offset": offset})
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('congress_cursor', ?)", (json.dumps(cursor),))
        conn.commit()
        if done:
            break
    else:
        log(f"  congress.gov: {offset} bills read so far; the rest next run")
    _us_describe_old(conn, key, fetcher)
    conn.commit()
    return changed


# --- EU (European Parliament open data) ---

EP_API = "https://data.europarl.europa.eu/api/v2"
EP_FORMAT = "format=application%2Fld%2Bjson"


def _procedure(proc_id: str, fetcher=feeds.fetch) -> dict:
    return _get_json(f"{EP_API}/procedures/{proc_id}?{EP_FORMAT}", fetcher)["data"][0]


def sync_europarl(conn, fetcher=feeds.fetch, years: list[int] | None = None, log=print) -> int:
    """Find AI procedures (ordinary legislative procedure, COD) and refresh their stages."""
    connect_tables(conn)
    this_year = date.today().year
    years = years or [this_year - 1, this_year]
    changed = 0
    for year in years:
        listing = _get_json(f"{EP_API}/procedures?{EP_FORMAT}&limit=500&offset=0&process-type=COD&year={year}",
                            fetcher)
        for p in listing.get("data", []):
            pid = p["process_id"]
            if conn.execute("SELECT 1 FROM eu_procedures WHERE id = ?", (pid,)).fetchone():
                continue
            full = _procedure(pid, fetcher)
            title = (full.get("process_title") or {}).get("en") or ""
            conn.execute("INSERT OR REPLACE INTO eu_procedures VALUES (?,?,?)", (pid, title, int(bool(AI_TITLE.search(title)))))
            conn.commit()
            time.sleep(0.2)
    for pid, title in conn.execute("SELECT id, title FROM eu_procedures WHERE is_ai = 1").fetchall():
        full = _procedure(pid, fetcher)
        ref = full.get("label") or pid.replace("-", "/", 1)
        bill = {"key": f"EU-{pid}", "jurisdiction": "EU", "number": ref, "title": title,
                "short_title": _eu_short_title(title),
                "url": f"https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={ref}",
                "source": "European Parliament", "history": eu_history(full)}
        changed += upsert(conn, bill)
        time.sleep(0.2)
    conn.commit()
    return changed


def _eu_short_title(title: str) -> str:
    """"Harmonised rules on Artificial Intelligence (Artificial Intelligence Act) and ..." -> the name in brackets."""
    m = re.search(r"\(([^()]*\b(Act|Regulation|Directive)\b[^()]*)\)", title)
    return m.group(1) if m else ""


# --- UK (UK Parliament Bills API) ---

UK_API = "https://bills-api.parliament.uk/api/v1"
# The API's search matches bill titles; AI_TITLE then keeps only AI bills.
UK_SEARCHES = ("artificial intelligence", "algorithm", "automated decision", "deepfake", "machine learning", "chatbot")


def uk_history(bill: dict, stages: list[dict]) -> list[dict]:
    """Lifecycle from a bill's stages: first reading, third reading in each House, Royal Assent."""
    reached: dict[str, dict] = {}
    third: dict[str, str] = {}
    for st in stages:
        dates = sorted(s["date"][:10] for s in st.get("stageSittings") or [] if s.get("date"))
        if not dates:
            continue
        what, house = st.get("description", ""), st.get("house", "")
        if what == "1st reading":
            reached.setdefault("introduced", {"date": dates[0], "stage": "introduced", "text": f"1st reading, {house}"})
        elif what == "3rd reading":
            third.setdefault(house, dates[-1])
        elif what == "Royal Assent":
            reached["signed"] = {"date": dates[0], "stage": "signed", "text": "Royal Assent"}
    if third:
        first = min(third.values())
        reached["passed_chamber"] = {"date": first, "stage": "passed_chamber", "text": "3rd reading"}
        if len(third) == 2:
            reached["passed_legislature"] = {"date": max(third.values()), "stage": "passed_legislature",
                                             "text": "3rd reading in both Houses"}
    if bill.get("billWithdrawn"):
        reached["withdrawn"] = {"date": bill["billWithdrawn"][:10], "stage": "withdrawn", "text": "Withdrawn"}
    elif bill.get("isDefeated"):
        reached["vetoed"] = {"date": (bill.get("lastUpdate") or "")[:10], "stage": "vetoed", "text": "Defeated"}
    return sorted(reached.values(), key=lambda h: (h["date"], (STAGES + ENDED).index(h["stage"])))


def sync_uk(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI bills in the UK Parliament (every session the API holds) and their stages."""
    connect_tables(conn)
    found: dict[int, dict] = {}
    for term in UK_SEARCHES:
        data = _get_json(f"{UK_API}/Bills?SearchTerm={term.replace(' ', '%20')}&SortOrder=DateUpdatedDescending"
                         f"&Take=100", fetcher)
        for b in data.get("items", []):
            if AI_TITLE.search(b.get("shortTitle") or ""):
                found[b["billId"]] = b
        time.sleep(0.5)
    changed = 0
    for bill_id, b in found.items():
        stages = _get_json(f"{UK_API}/Bills/{bill_id}/Stages?Take=100", fetcher).get("items", [])
        long_title = (_get_json(f"{UK_API}/Bills/{bill_id}", fetcher) or {}).get("longTitle") or ""
        history = uk_history(b, stages)
        # Bills are often reintroduced under the same name in a later session: the year tells them apart.
        year = next((h["date"][:4] for h in history if h["stage"] == "introduced"), "")
        short = re.sub(r"\s*\[HL\]$", "", b["shortTitle"])
        bill = {"key": f"GB-{bill_id}", "jurisdiction": "GB", "number": "", "title": b["shortTitle"],
                "short_title": f"{short} ({year})" if year else short,
                "url": f"https://bills.parliament.uk/bills/{bill_id}", "source": "UK Parliament", "history": history,
                "summary": describe(long_title, b["shortTitle"])}
        changed += upsert(conn, bill)
        conn.commit()
        time.sleep(0.5)
    return changed


# --- Canada (LEGISinfo) ---

CA_API = "https://www.parl.ca/legisinfo/en/bills/json"
# Past sessions, read once for the history since 2023, with the day each ended (bills not passed by then
# died on the Order Paper; LEGISinfo leaves that date blank). The current session is read every time.
CA_PAST_SESSIONS = {"44-1": "2025-01-06"}  # 44th Parliament, 1st session: prorogued 6 January 2025


def ca_history(b: dict, session_end: str = "") -> list[dict]:
    """Lifecycle from a LEGISinfo bill: first and third readings in each chamber, Royal Assent, and the end of
    the session for a bill that didn't pass (it "dies on the Order Paper")."""
    day = lambda k: d if (d := (b.get(k) or "")[:10]) > "1900" else ""  # "0001-01-01" means no date
    first = [d for d in (day("PassedHouseFirstReadingDateTime"), day("PassedSenateFirstReadingDateTime")) if d]
    third = [d for d in (day("PassedHouseThirdReadingDateTime"), day("PassedSenateThirdReadingDateTime")) if d]
    history = []
    if first:
        history.append({"date": min(first), "stage": "introduced", "text": "First reading"})
    if third:
        history.append({"date": min(third), "stage": "passed_chamber", "text": "Third reading"})
    if len(third) == 2:
        history.append({"date": max(third), "stage": "passed_legislature", "text": "Third reading in both chambers"})
    if day("ReceivedRoyalAssentDateTime"):
        history.append({"date": day("ReceivedRoyalAssentDateTime"), "stage": "signed", "text": "Royal Assent"})
    elif b.get("IsSessionOngoing") is False and history:
        ended = session_end or day("LatestBillEventDateTime") or history[-1]["date"]
        history.append({"date": ended, "stage": "withdrawn", "text": "Died on the Order Paper"})
    return history


def sync_canada(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI bills in the Parliament of Canada: the current session every time, past sessions once."""
    connect_tables(conn)
    past = list(CA_PAST_SESSIONS)  # one request each: re-read so their cards stay current
    changed = 0
    for session in [None, *past]:
        url = CA_API + (f"?parlsession={session}" if session else "")
        for b in _get_json(url, fetcher):
            title = b.get("ShortTitleEn") or b.get("LongTitleEn") or ""
            if not AI_TITLE.search(f"{b.get('LongTitleEn') or ''} {b.get('ShortTitleEn') or ''}"):
                continue
            s = f"{b['ParliamentNumber']}-{b['SessionNumber']}"
            bill = {"key": f"CA-{s}-{b['NumberCode']}", "jurisdiction": "CA", "number": b["NumberCode"],
                    "title": b.get("LongTitleEn") or title, "short_title": b.get("ShortTitleEn") or "",
                    "url": f"https://www.parl.ca/legisinfo/en/bill/{s}/{b['NumberCode'].lower()}",
                    "source": "Parliament of Canada", "history": ca_history(b, CA_PAST_SESSIONS.get(s, "")),
                    "summary": describe(b.get("LongTitleEn") or "", title) if b.get("ShortTitleEn") else ""}
            if bill["history"]:
                changed += upsert(conn, bill)
        conn.commit()
        time.sleep(1)
    return changed


# --- Brazil (Câmara dos Deputados) ---

BR_API = "https://dadosabertos.camara.leg.br/api/v2"
BR_KEYWORD = "intelig%C3%AAncia%20artificial"
BR_AI = re.compile(r"intelig[êe]ncia artificial|\bIA\b|algor[íi]tm|deep ?fakes?|aprendizado de m[áa]quina|"
                   r"decis[õo]es automatizadas", re.I)
BR_ATTACHED = ("Tramitando em Conjunto", "Aguardando Apensação")
# Stages from an event's own description and dispatch. (The API stamps every event's "situation" with the
# bill's current status, so it says nothing about when a stage was reached.) First match wins.
_BR_RULES = [
    ("signed", re.compile(r"Transforma(do|ção) (em Norma Jurídica|na Lei)", re.I)),
    ("vetoed", re.compile(r"Vetad[oa] totalmente|Veto Total", re.I)),
    ("passed_legislature", re.compile(r"remessa à sanção|Remessa à Sanção|enviad[oa] à sanção", re.I)),
    ("passed_chamber", re.compile(r"Remessa ao Senado Federal|vai ao Senado Federal|"
                                  r"Recebido o Of[íi]cio .{0,40}do Senado Federal que submete à revisão", re.I)),
    ("withdrawn", re.compile(r"^(Retirada pel[oa]|Arquivamento)", re.I)),  # matched on the description only
]


def br_history(presented: str, events: list[dict]) -> list[dict]:
    """Lifecycle from a proposal's procedural events (tramitações). A bill that reached the Chamber from the
    Senate starts at "passed first chamber" (the day it arrived)."""
    reached: dict[str, dict] = {}
    from_senate = False
    for e in sorted(events, key=lambda e: e.get("dataHora") or ""):
        when = (e.get("dataHora") or "")[:10]
        what = e.get("descricaoTramitacao") or ""
        text = f"{what} | {e.get('despacho') or ''}"
        for stage, rule in _BR_RULES:
            if when and rule.search(what if stage == "withdrawn" else text):
                if stage == "passed_chamber" and "submete à revisão" in text and "introduced" not in reached:
                    from_senate = True
                reached.setdefault(stage, {"date": when, "stage": stage, "text": what[:200]})
                break
    if presented and not from_senate:
        reached.setdefault("introduced", {"date": presented[:10], "stage": "introduced", "text": "Apresentação"})
    if "withdrawn" in reached and any(s in reached for s in ("signed", "vetoed")):
        del reached["withdrawn"]  # a law is archived as a matter of course afterwards
    return sorted(reached.values(), key=lambda h: (h["date"], (STAGES + ENDED).index(h["stage"])))


def sync_brazil(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI bills in Brazil's Chamber of Deputies: since 2023 on the first run, then those with any activity
    since the last run."""
    connect_tables(conn)
    if fetcher is feeds.fetch:  # the Chamber's API is slow to answer from abroad
        fetcher = lambda u: feeds.fetch(u, timeout=90)
    last = conn.execute("SELECT value FROM meta WHERE key = 'brazil_sync'").fetchone()
    started = date.today().isoformat()
    window = (f"dataInicio={(date.fromisoformat(last[0]) - timedelta(days=2)).isoformat()}" if last
              else "dataApresentacaoInicio=2023-01-01")
    found, page = [], 1
    while True:
        data = _get_json(f"{BR_API}/proposicoes?keywords={BR_KEYWORD}&{window}&itens=100&pagina={page}"
                         "&ordem=DESC&ordenarPor=id", fetcher)
        found += [p for p in data.get("dados", []) if p.get("siglaTipo") in ("PL", "PLP", "PEC")
                  and BR_AI.search(p.get("ementa") or "")]
        if not any(l.get("rel") == "next" for l in data.get("links", [])):
            break
        page += 1
        time.sleep(0.5)
    translate.english(conn, "pt", [(p.get("ementa") or "").strip() for p in found])
    changed = 0
    for p in found:
        detail = _get_json(f"{BR_API}/proposicoes/{p['id']}", fetcher)["dados"]
        status = (detail.get("statusProposicao") or {}).get("descricaoSituacao") or ""
        if status in BR_ATTACHED:
            continue
        events = _get_json(f"{BR_API}/proposicoes/{p['id']}/tramitacoes", fetcher).get("dados", [])
        history = br_history(detail.get("dataApresentacao") or "", events)
        number = f"{p['siglaTipo']} {p['numero']}/{p['ano']}"
        bill = {"key": f"BR-{p['siglaTipo']}-{p['numero']}-{p['ano']}", "jurisdiction": "BR", "number": number,
                "title": (p.get("ementa") or "").strip(),
                "url": f"https://www.camara.leg.br/propostas-legislativas/{p['id']}",
                "source": "Câmara dos Deputados", "history": history, "lang": "pt"}
        if history:
            changed += upsert(conn, bill)
        conn.commit()
        time.sleep(0.5)
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('brazil_sync', ?)", (started,))
    conn.commit()
    retitle(conn, "BR", "pt")
    return changed


_LANGS = {"BR": "pt", "CN": "zh", "JP": "ja", "VN": "vi", "CH": "de", "TW": "zh"}  # records whose titles are translated


def refresh_cards(conn) -> int:
    """Rebuild every bill's card from its stored record (title, description, stages), so a change to how
    cards look reaches old bills too. Returns how many cards."""
    rows = conn.execute("SELECT * FROM bills").fetchall()
    for r in rows:
        upsert(conn, {"key": r["key"], "jurisdiction": r["jurisdiction"], "number": r["number"], "title": r["title"],
                      "short_title": r["short_title"], "url": r["url"], "source": r["source"],
                      "history": json.loads(r["history"]), "summary": r["summary"],
                      "lang": _LANGS.get(r["jurisdiction"])})
    conn.commit()
    return len(rows)


def retitle(conn, jurisdiction: str, lang: str) -> int:
    """Give every card from one jurisdiction the English version of its title (translating the ones not
    done yet, when the translator is available). Returns how many cards have one."""
    rows = conn.execute("SELECT * FROM bills WHERE jurisdiction = ?", (jurisdiction,)).fetchall()
    found = translate.english(conn, lang, [r["title"] for r in rows])
    for r in rows:
        if r["title"] in found:
            upsert(conn, {"key": r["key"], "jurisdiction": jurisdiction, "number": r["number"], "title": r["title"],
                          "short_title": r["short_title"], "url": r["url"], "source": r["source"],
                          "history": json.loads(r["history"]), "lang": lang, "summary": r["summary"]})
    conn.commit()
    return len(found)


# --- China (Cyberspace Administration of China) ---

CN_SITE = "https://www.cac.gov.cn"
# Laws, administrative regulations, departmental rules, normative documents and policy documents (the
# section's interpretations and judicial interpretations aren't regulations of their own).
CN_LISTS = ("fl/A09370301", "xzfg/A09370302", "bmgz/A09370303", "gfxwj/A09370305", "zcwj/A09370306")
CN_AI = re.compile(r"人工智能|生成式|深度合成|算法|大模型|智能体|合成内容|机器学习|\bAI\b")
_CN_ITEM = re.compile(r'<a href=([^ >]+) target=_blank title="([^"]+)">.*?<div class="times">(\d{4}-\d{2}-\d{2})</div>', re.S)


def sync_china(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI regulations the CAC lists, as title (in English), date and link."""
    connect_tables(conn)
    found = {}
    for path in CN_LISTS:
        page = fetcher(f"{CN_SITE}/wxzw/zcfg/{path}index_1.htm").decode("utf-8", "replace")
        for href, title, day in _CN_ITEM.findall(page):
            if CN_AI.search(title):
                url = "https:" + href if href.startswith("//") else href
                found[url] = (title.strip(), day)
        time.sleep(1)
    translate.english(conn, "zh", [t for t, _ in found.values()])
    changed = 0
    for url, (title, day) in found.items():
        draft = "征求意见" in title
        stage = "introduced" if draft else "signed"
        bill = {"key": "CN-" + url.rsplit("/", 1)[1].removesuffix(".htm"), "jurisdiction": "CN", "number": "",
                "title": title, "url": url, "source": "Cyberspace Administration of China", "lang": "zh",
                "history": [{"date": day, "stage": stage, "text": "征求意见稿" if draft else "发布"}]}
        changed += upsert(conn, bill)
    conn.commit()
    retitle(conn, "CN", "zh")
    return changed


# --- India (Parliament of India, sansad.in) ---

IN_API = "https://sansad.in/api_rs/legislation/getBills"
IN_SEARCHES = ("artificial intelligence", "deepfake", "algorithm", "machine learning", "automated decision")
_IN_QUERY = ("loksabha=&sessionNo=&house=&ministryName=&billType=&billCategory=&billStatus=&introductionDateFrom="
             "&introductionDateTo=&passedInLsDateFrom=&passedInLsDateTo=&passedInRsDateFrom=&passedInRsDateTo="
             "&page=1&size=50&locale=en&sortOn=billIntroducedDate&sortBy=desc")


def in_history(b: dict) -> list[dict]:
    """Introduction, passing in each House and assent. (Lapsed or withdrawn bills have no date for it, so
    they stay at their last dated stage.)"""
    day = lambda k: (b.get(k) or "")[:10]
    history = []
    if day("billIntroducedDate"):
        history.append({"date": day("billIntroducedDate"), "stage": "introduced",
                        "text": f"Introduced in {b.get('billIntroducedInHouse') or 'Parliament'}"})
    passed = sorted(d for d in (day("billPassedInLSDate"), day("billPassedInRSDate")) if d)
    if passed:
        history.append({"date": passed[0], "stage": "passed_chamber", "text": "Passed one House"})
    if len(passed) == 2:
        history.append({"date": passed[1], "stage": "passed_legislature", "text": "Passed both Houses"})
    if day("billAssentedDate"):
        history.append({"date": day("billAssentedDate"), "stage": "signed", "text": "Assent"})
    return history


def sync_india(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI bills in the Lok Sabha and Rajya Sabha (the API answers slowly, hence the long timeout)."""
    connect_tables(conn)
    get = (lambda u: feeds.fetch(u, timeout=120)) if fetcher is feeds.fetch else fetcher
    found = {}
    for term in IN_SEARCHES:
        data = _get_json(f"{IN_API}?billName={term.replace(' ', '%20')}&{_IN_QUERY}", get)
        for b in data.get("records") or []:
            if AI_TITLE.search(b.get("billName") or ""):
                house = "LS" if (b.get("billIntroducedInHouse") or "").startswith("Lok") else "RS"
                found[f"IN-{house}-{b.get('billYear')}-{b.get('billNumber')}"] = b
        time.sleep(1)
    changed = 0
    for key, b in found.items():
        url = (b.get("billIntroducedFile") or "https://sansad.in/ls/legislation/bills").replace(" ", "%20")
        bill = {"key": key, "jurisdiction": "IN", "number": "", "title": (b["billName"] or "").strip().rstrip("."),
                "url": url, "source": "Parliament of India", "history": in_history(b)}
        if bill["history"]:
            changed += upsert(conn, bill)
    conn.commit()
    return changed


# --- Japan (e-Gov law API) ---

JP_API = "https://laws.e-gov.go.jp/api/2/laws"
JP_SEARCHES = ("人工知能", "生成ＡＩ", "ディープフェイク")
# e-Gov's law number types, as Japan's official English translations name them.
_JP_TYPES = {"Act": "Act", "CabinetOrder": "Cabinet Order", "ImperialOrder": "Imperial Order",
             "MinisterialOrdinance": "Ministerial Ordinance", "Rule": "Rule"}


def jp_history(law: dict) -> list[dict]:
    """Promulgation, entry into force and repeal of a law from its e-Gov record."""
    info, rev = law.get("law_info") or {}, law.get("current_revision_info") or law.get("revision_info") or {}
    history = []
    if info.get("promulgation_date"):
        history.append({"date": info["promulgation_date"][:10], "stage": "signed", "text": "Promulgated"})
    first = [r for r in (law.get("revision_info") or {},) if r.get("amendment_enforcement_date")]
    if first and first[0]["amendment_enforcement_date"] <= date.today().isoformat():
        history.append({"date": first[0]["amendment_enforcement_date"][:10], "stage": "in_force", "text": "In force"})
    if rev.get("repeal_date"):
        history.append({"date": rev["repeal_date"][:10], "stage": "withdrawn", "text": "Repealed"})
    return sorted(history, key=lambda h: (h["date"], (STAGES + ENDED).index(h["stage"])))


def sync_japan(conn, fetcher=feeds.fetch, log=print) -> int:
    """Japanese laws and cabinet orders about AI, from the official e-Gov law database."""
    connect_tables(conn)
    from urllib.parse import quote
    found = {}
    for term in JP_SEARCHES:
        for law in _get_json(f"{JP_API}?law_title={quote(term)}", fetcher).get("laws") or []:
            found[law["law_info"]["law_id"]] = law
        time.sleep(1)
    titles = {lid: ((law.get("current_revision_info") or law.get("revision_info") or {}).get("law_title") or "")
              for lid, law in found.items()}
    translate.english(conn, "ja", list(titles.values()))
    changed = 0
    for lid, law in found.items():
        info = law["law_info"]
        kind = _JP_TYPES.get(info.get("law_num_type") or info.get("law_type"), "")
        year = (info.get("promulgation_date") or "")[:4]
        number = f"{kind} No. {int(info['law_num_num'])} of {year}" if kind and info.get("law_num_num") and year else ""
        bill = {"key": f"JP-{lid}", "jurisdiction": "JP", "number": number, "title": titles[lid],
                "url": f"https://laws.e-gov.go.jp/law/{lid}", "source": "e-Gov (Japan)", "lang": "ja",
                "history": jp_history(law)}
        if bill["history"] and bill["title"]:
            changed += upsert(conn, bill)
    conn.commit()
    retitle(conn, "JP", "ja")
    return changed


# --- Vietnam (National Legal Database, vbpl.vn, Ministry of Justice) ---

VN_SITE = "https://vbpl.vn"
# The database's sitemap lists every document with its title in the URL; "tri-tue-nhan-tao" is
# "artificial intelligence". Only national documents (the sitemaps before the provincial ones) are read.
VN_AI = re.compile(r"tri-tue-nhan-tao")
_VN_TYPES = {"luat": "Law", "nghi-dinh": "Decree", "nghi-quyet": "Resolution", "thong-tu": "Circular",
             "quyet-dinh": "Decision", "chi-thi": "Directive", "phap-lenh": "Ordinance"}
VN_REFRESH_DAYS = 7


def _vn_meta(page: str, prop: str) -> str:
    m = re.search(rf'<meta (?:property|name)="{prop}" content="([^"]*)"', page)
    return html.unescape(m.group(1)) if m else ""


def sync_vietnam(conn, fetcher=feeds.fetch, log=print) -> int:
    """Vietnamese laws, decrees and decisions about AI: title (in English), number, date and link.
    Legal documents aren't protected by copyright in Vietnam (Law on Intellectual Property, Art. 15)."""
    connect_tables(conn)
    last = conn.execute("SELECT value FROM meta WHERE key = 'vn_sync'").fetchone()
    if last and last[0] > (date.today() - timedelta(days=VN_REFRESH_DAYS)).isoformat():
        return 0
    index = fetcher(f"{VN_SITE}/sitemap.xml").decode("utf-8", "replace")
    national = index.split("Địa phương")[0]  # the provincial sitemaps follow this comment
    urls = []
    for sitemap in re.findall(r"<loc>(.*?)</loc>", national)[1:]:  # the first lists the site's own pages
        urls += [u for u in re.findall(r"<loc>(.*?)</loc>", fetcher(sitemap).decode("utf-8", "replace"))
                 if "/van-ban/chi-tiet/" in u and VN_AI.search(u)]
        time.sleep(1)
    known = {r[0] for r in conn.execute("SELECT url FROM bills WHERE jurisdiction = 'VN'")}
    records = []
    for url in urls:
        key = "VN-" + url.rsplit("--", 1)[-1]
        if url in known:
            continue
        page = fetcher(url).decode("utf-8", "replace")
        time.sleep(1)
        # "Tra cứu Luật 134/2025/QH15, LUẬT TRÍ TUỆ NHÂN TẠO SỐ 134/2025/QH15. Xem toàn văn và hiệu lực."
        m = re.match(r"Tra cứu \S+ (\S+), (.*?)(?: SỐ \S+)?\. Xem", _vn_meta(page, "description"))
        issued = _vn_meta(page, "article:published_time")
        if not (m and issued):
            continue
        day = (datetime.fromisoformat(issued.replace("Z", "+00:00")) + timedelta(hours=7)).date().isoformat()
        slug = url.rsplit("/", 1)[1]
        kind = next((v for k, v in _VN_TYPES.items() if slug.startswith(k + "-")), "")
        title = m.group(2).strip()
        title = title[0] + title[1:].lower() if title.isupper() else title
        records.append({"key": key, "jurisdiction": "VN", "number": f"{kind} No. {m.group(1)}" if kind else m.group(1),
                        "title": title, "url": url, "source": "National Legal Database (Vietnam)", "lang": "vi",
                        "history": [{"date": day, "stage": "signed", "text": "Ban hành"}]})
    translate.english(conn, "vi", [r["title"] for r in records])
    changed = sum(upsert(conn, r) for r in records)
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('vn_sync', ?)", (date.today().isoformat(),))
    conn.commit()
    retitle(conn, "VN", "vi")
    return changed


# --- Switzerland (Swiss Parliament open data, ws.parlament.ch) ---

CH_API = "https://ws.parlament.ch/odata.svc/Business"
CH_SEARCHES = ("künstliche Intelligenz", "Künstliche Intelligenz", "KI", "Deepfake", "Algorithm")
# Items that ask for a law go to the tracker; postulates (a request for a government report) to Policy.
# Interpellations and questions are only questions, so they're left out.
_CH_TYPES = {"Motion": "Motion", "Parlamentarische Initiative": "Parliamentary initiative",
             "Standesinitiative": "Cantonal initiative", "Geschäft des Bundesrates": "Federal Council bill"}
_CH_POLICY = {"Postulat": "Postulate"}
_CH_COUNCILS = {"Nationalrat": "National Council", "Ständerat": "Council of States"}
_CH_STANCE = {"Annahme": "The Federal Council recommends accepting it.",
              "Ablehnung": "The Federal Council recommends rejecting it."}
_CH_SELECT = ("ID,BusinessShortNumber,BusinessTypeName,Title,SubmittedText,FederalCouncilProposalText,"
              "SubmissionDate,SubmissionCouncilName,BusinessStatusText,BusinessStatusDate")


def _ch_date(raw: str | None) -> str:
    """OData "/Date(1724198400000)/" -> "2024-08-21" (Swiss time)."""
    m = re.search(r"-?\d+", raw or "")
    return (datetime.fromtimestamp(int(m.group()) / 1000, timezone.utc) + timedelta(hours=2)).date().isoformat() if m else ""


def ch_history(r: dict) -> list[dict]:
    """Submission and where the item stands now, from its record."""
    council = _CH_COUNCILS.get(r.get("SubmissionCouncilName") or "", "")
    history = [{"date": _ch_date(r.get("SubmissionDate")), "stage": "introduced",
                "text": f"Submitted in the {council}" if council else "Submitted"}]
    status, day = r.get("BusinessStatusText") or "", _ch_date(r.get("BusinessStatusDate"))
    stage = ("passed_legislature" if status.startswith(("Überwiesen an den Bundesrat", "Erfüllt"))
             else "passed_chamber" if "Erstrat angenommen" in status
             else "vetoed" if "abgelehnt" in status.lower()
             else "withdrawn" if status.startswith(("Erledigt", "Abgeschrieben", "Zurückgezogen")) else None)
    if stage and day:
        history.append({"date": max(day, history[0]["date"]), "stage": stage, "text": status})
    return [h for h in history if h["date"]]


def _ch_demand(text: str | None) -> str:
    """The sentence that says what the item asks for ("Der Bundesrat wird beauftragt, ..."), else the first."""
    plain = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()
    sentences = re.split(r"(?<=[.!?])\s", plain)
    first = next((s for s in sentences if re.search(r"Bundesrat (wird|ist)", s)), sentences[0])
    return first if len(first) <= 400 else first[:399].rsplit(" ", 1)[0] + "…"


def sync_switzerland(conn, fetcher=feeds.fetch, log=print) -> int:
    """Swiss motions and bills about AI (tracker) and postulates (Policy), with English titles and a
    summary of what each asks and the Federal Council's position. Open data: free use, source named."""
    connect_tables(conn)
    from urllib.parse import quote
    found = {}
    for term in CH_SEARCHES:
        query = quote(f"Language eq 'DE' and substringof('{term}',Title)")
        data = _get_json(f"{CH_API}?$filter={query}&$select={_CH_SELECT}&$format=json&$top=500", fetcher)["d"]
        for r in data["results"] if isinstance(data, dict) else data:
            if term == "KI" and not re.search(r"\bKI\b", r["Title"]):
                continue
            if r["BusinessTypeName"] in _CH_TYPES or r["BusinessTypeName"] in _CH_POLICY:
                found[r["ID"]] = r
        time.sleep(1)
    demands = {i: _ch_demand(r.get("SubmittedText")) for i, r in found.items()}
    english = translate.english(conn, "de", [r["Title"].strip() for r in found.values()] + list(demands.values()))
    changed = 0
    for i, r in found.items():
        title = r["Title"].strip()
        kind = _CH_TYPES.get(r["BusinessTypeName"]) or _CH_POLICY[r["BusinessTypeName"]]
        summary = " ".join(s for s in (english.get(demands[i], ""),
                                       _CH_STANCE.get(r.get("FederalCouncilProposalText") or "", "")) if s)
        url = f"https://www.parlament.ch/en/ratsbetrieb/suche-curia-vista/geschaeft?AffairId={i}"
        history = ch_history(r)
        if not history:
            continue
        if r["BusinessTypeName"] in _CH_TYPES:
            changed += upsert(conn, {"key": f"CH-{i}", "jurisdiction": "CH", "number": f"{kind} {r['BusinessShortNumber']}",
                                     "title": title, "url": url, "source": "Swiss Parliament", "lang": "de",
                                     "summary": summary, "history": history})
            continue
        # A postulate: a Policy card of its own, kept apart from news (items.bill) and never re-sorted.
        name = english.get(title)
        item = {"title": f"{kind} {r['BusinessShortNumber']}: {name or title}", "url": url, "source": "Swiss Parliament",
                "summary": summary + (" Machine-translated from German; the official text is linked." if name else ""),
                "category": "policy", "date": history[0]["date"], "jurisdictions": ["CH"], "tags": []}
        if store.exists(conn, url):
            conn.execute("UPDATE items SET title = ?, summary = ? WHERE id = ?", (item["title"], item["summary"],
                                                                                   store.item_id(url)))
        elif store.insert(conn, item):
            conn.execute("UPDATE items SET bill = ? WHERE id = ?", (f"CH-{i}", store.item_id(url)))
            changed += 1
    conn.commit()
    return changed


# --- Malaysia (Parliament of Malaysia, Dewan Rakyat bills) ---

MY_BILLS = "https://www.parlimen.gov.my/bills-dewan-rakyat.html?uweb=dr&lang=en"
MY_AI = re.compile(AI_TITLE.pattern + r"|kecerdasan buatan", re.I)
_MY_FIELD = r'>{}</td>\s*<td[^>]*>:</td>\s*<td[^>]*>(\d{{2}}/\d{{2}}/\d{{4}})</td>'


def _my_date(chunk: str, label: str) -> str:
    m = re.search(_MY_FIELD.format(label), chunk)
    return datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat() if m else ""


def sync_malaysia(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI bills in Malaysia's House of Representatives: number, title, readings and a link to the bill.
    (No AI bill has been tabled yet; the AI Governance Bill is in consultation, see the ministry's releases.)"""
    connect_tables(conn)
    page = fetcher(MY_BILLS).decode("utf-8", "replace")
    changed = 0
    for chunk in page.split('<tr class="maintable">')[1:]:
        cells = re.findall(r'<td[^>]*class="maintd"[^>]*>(.*?)</td>', chunk, re.S)
        if len(cells) < 3:
            continue
        number = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cells[0])).strip()
        title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cells[2]))).strip()
        if not MY_AI.search(title):
            continue
        pdf = re.search(r"loadResult\('([^']+\.pdf)'", chunk)
        status = re.search(r'<div class="parent[^"]*"[^>]*>(.*?)</div>', chunk, re.S)
        history = [h for h in (
            {"date": _my_date(chunk, "First reading"), "stage": "introduced", "text": "First reading"},
            {"date": _my_date(chunk, "Passed At"), "stage": "passed_chamber", "text": "Passed Dewan Rakyat"}) if h["date"]]
        if status and "withdraw" in status.group(1).lower() and history:
            history.append({"date": history[-1]["date"], "stage": "withdrawn", "text": "Withdrawn"})
        if not history:
            continue
        from urllib.parse import quote
        url = "https://www.parlimen.gov.my" + quote(pdf.group(1)) if pdf else MY_BILLS
        changed += upsert(conn, {"key": "MY-" + number.replace("/", "-"), "jurisdiction": "MY", "number": number,
                                 "title": title, "url": url, "source": "Parliament of Malaysia", "history": history})
    conn.commit()
    return changed


# --- Taiwan (Legislative Yuan law system, lis.ly.gov.tw) ---

TW_LAWS = "https://lis.ly.gov.tw/lglawc/lglawkm"
TW_SEARCHES = ("人工智慧",)  # "artificial intelligence", in law names
# The system's result links last one session, so a card links to the law's name on the national law database
# (a link for readers; that site's robots.txt closes it to automated reading, so it's never fetched).
TW_LINK = "https://law.moj.gov.tw/Law/LawSearchResult.aspx?ty=ONEBAR&kw="
_TW_ROW = re.compile(r"<tr[^>]*>((?:(?!</tr>).)*?\b(\d{7})\b(?:(?!</tr>).)*?\b(\d{7})\b(?:(?!</tr>).)*)</tr>", re.S)


def _roc(day: str) -> str:
    """Taiwan's calendar: "1141223" is 2025-12-23 (year 114 + 1911)."""
    return f"{int(day[:3]) + 1911:04d}-{day[3:5]}-{day[5:7]}"


def tw_laws(page: str) -> list[tuple[str, str, str]]:
    """(law name, passed, promulgated) for each law in a result page."""
    out = []
    for row, passed, promulgated in _TW_ROW.findall(page):
        cells = [re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", c)))
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        name = next((c for c in cells if re.search(r"[\u4e00-\u9fff]{2,}(法|條例|通則|規程|辦法)$", c)), "")
        if name:
            out.append((name, _roc(passed), _roc(promulgated)))
    return out


def sync_taiwan(conn, fetcher=None, log=print, opener=None) -> int:
    """Taiwan's laws with AI in their name, from the Legislative Yuan's law system: passage and promulgation.
    The system is a search form (robots.txt sets no rules); one search per term, then nothing else."""
    connect_tables(conn)
    import http.cookiejar
    import urllib.parse
    import urllib.request
    if not feeds.allowed(TW_LAWS):
        raise feeds.Disallowed(TW_LAWS)
    if opener is None:
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=feeds.TLS),
                                             urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        opener.addheaders = [("User-Agent", feeds.USER_AGENT)]
    found = {}
    for term in TW_SEARCHES:
        form = opener.open(TW_LAWS, timeout=30).read().decode("utf-8", "replace")
        action = re.search(r'<form[^>]*action="([^"]+)"', form).group(1)
        fields = dict(re.findall(r"<input type=hidden name=([^ >]+) value=[\"']?([^\"'>]*)", form))
        fields.update({"_1_6_T": term, "_IMG_檢索.x": "10", "_IMG_檢索.y": "10"})
        page = opener.open("https://lis.ly.gov.tw" + action, data=urllib.parse.urlencode(fields).encode(),
                           timeout=30).read().decode("utf-8", "replace")
        for name, passed, promulgated in tw_laws(page):
            found[name] = (passed, promulgated)
        time.sleep(1)
    from urllib.parse import quote
    translate.english(conn, "zh", list(found))
    changed = 0
    for name, (passed, promulgated) in found.items():
        changed += upsert(conn, {"key": "TW-" + name, "jurisdiction": "TW", "number": "", "title": name,
                                 "url": TW_LINK + quote(name), "source": "Legislative Yuan (Taiwan)", "lang": "zh",
                                 "history": [{"date": passed, "stage": "passed_legislature", "text": "三讀通過"},
                                             {"date": promulgated, "stage": "signed", "text": "公布"}]})
    conn.commit()
    retitle(conn, "TW", "zh")
    return changed


# --- South Korea (National Law Information Center, law.go.kr, Ministry of Government Legislation) ---

KR_SEARCH = "https://www.law.go.kr/LSW/lsScListR.do"
KR_LINK = "https://www.law.go.kr/법령/"  # the centre's permanent address for a law, by name
KR_REFRESH_DAYS = 7
# Each version of a law is listed as "NAME[시행 2026. 1. 22.] [법률 제20676호, 2025. 1. 21., 제정]".
_KR_ITEM = re.compile(r'title="([^"\[]*인공지능[^"\[]*)\[시행 (\d{4})\. ?(\d{1,2})\. ?(\d{1,2})\.\] '
                      r'\[([^\]]*?) 제(\d+)호, (\d{4})\. ?(\d{1,2})\. ?(\d{1,2})\., ([^\]]+)\]"')
_KR_TYPES = {"법률": "Act", "대통령령": "Presidential Decree", "총리령": "Prime Minister's Decree"}
# English names (as the government translates them) and what each does. Korea's offline translation model
# is unusable, so names come from this list; a new law keeps its Korean name until it's added here.
KR_NAMES = {
    "인공지능 발전과 신뢰 기반 조성 등에 관한 기본법": (
        "Framework Act on the Development of AI and the Establishment of a Foundation for Trust (AI Basic Act)",
        "Korea's comprehensive AI law: national AI policy and industry support, and duties for high-impact and "
        "generative AI such as risk management, transparency and labelling of AI-generated content."),
    "인공지능 데이터센터 산업 진흥에 관한 특별법": (
        "Special Act on Promoting the AI Data Center Industry", "Support for building and running AI data centres."),
    "산업 디지털 전환 및 인공지능 활용 촉진법": (
        "Act on Promoting Industrial Digital Transformation and the Use of AI",
        "Promotes digital transformation and the use of AI across industry."),
    "인공지능 및 데이터 기반 행정 활성화에 관한 법률": (
        "Act on Promoting AI- and Data-Based Public Administration",
        "Promotes the use of AI and data in government administration."),
    "국가인공지능위원회의 설치 및 운영에 관한 규정": (
        "Regulation on the National AI Committee", "Set up the presidential committee that coordinated national AI policy."),
    "국가인공지능전략위원회의 설치 및 운영에 관한 규정": (
        "Regulation on the National AI Strategy Committee",
        "Set up the presidential committee that coordinates national AI strategy."),
}


def kr_english(name: str) -> tuple[str, str]:
    """(English name, what it does) for a Korean AI law, its enforcement decree or rule; ("", "") if unknown."""
    for suffix, kind, what in ((" 시행령", "Enforcement Decree of the ", "Sets out how the {} is applied."),
                               (" 시행규칙", "Enforcement Rule of the ", "Detailed rules for applying the {}.")):
        if name.endswith(suffix):
            base = KR_NAMES.get(name[: -len(suffix)])
            return (kind + base[0], what.format(base[0].split(" (")[0])) if base else ("", "")
    return KR_NAMES.get(name, ("", ""))


def kr_laws(page: str) -> dict[str, dict]:
    """Each law's first enactment, first entry into force and (if its latest version repeals it) repeal."""
    laws = {}
    for m in _KR_ITEM.finditer(page):
        name, kind = m.group(1).strip(), m.group(10).strip()
        effective = f"{m.group(2)}-{int(m.group(3)):02d}-{int(m.group(4)):02d}"
        promulgated = f"{m.group(7)}-{int(m.group(8)):02d}-{int(m.group(9)):02d}"
        law = laws.setdefault(name, {"versions": []})
        law["versions"].append({"type": m.group(5).strip(), "no": m.group(6), "effective": effective,
                                "promulgated": promulgated, "kind": kind})
    for law in laws.values():
        versions = sorted(law["versions"], key=lambda v: (v["promulgated"], v["effective"]))
        first, last = versions[0], versions[-1]
        kind = _KR_TYPES.get(first["type"], "Ministerial Decree" if first["type"].endswith("부령") else first["type"])
        law["number"] = f"{kind} No. {first['no']}"
        history = [{"date": first["promulgated"], "stage": "signed", "text": "공포"}]
        if first["effective"] <= date.today().isoformat():
            history.append({"date": max(first["effective"], first["promulgated"]), "stage": "in_force", "text": "시행"})
        if "폐지" in last["kind"]:
            history.append({"date": last["promulgated"], "stage": "withdrawn", "text": "폐지"})
        law["history"] = history
    return laws


def sync_korea(conn, fetcher=None, log=print) -> int:
    """Korea's laws and decrees with AI in their name, from the official law database (robots.txt allows it;
    laws aren't protected by copyright in Korea, Copyright Act Art. 7). Read about once a week."""
    connect_tables(conn)
    last = conn.execute("SELECT value FROM meta WHERE key = 'kr_sync'").fetchone()
    if last and last[0] > (date.today() - timedelta(days=KR_REFRESH_DAYS)).isoformat():
        return 0
    import urllib.parse
    import urllib.request
    if not feeds.allowed(KR_SEARCH):
        raise feeds.Disallowed(KR_SEARCH)
    form = urllib.parse.urlencode({"q": "인공지능", "query": "인공지능", "section": "lawNm", "outmax": "100",
                                   "pg": "1"}).encode()
    req = urllib.request.Request(KR_SEARCH, data=form, headers={"User-Agent": feeds.USER_AGENT})
    with urllib.request.urlopen(req, timeout=40, context=feeds.TLS) as resp:
        page = resp.read().decode("utf-8", "replace")
    from urllib.parse import quote
    changed = 0
    for name, law in kr_laws(page).items():
        english, what = kr_english(name)
        changed += upsert(conn, {"key": "KR-" + name, "jurisdiction": "KR", "number": law["number"],
                                 "title": name, "short_title": english, "url": KR_LINK + quote(name),
                                 "source": "National Law Information Center (Korea)", "summary": what,
                                 "history": law["history"]})
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('kr_sync', ?)", (date.today().isoformat(),))
    conn.commit()
    return changed


# --- Australia (Federal Register of Legislation) ---

AU_API = "https://api.prod.legislation.gov.au/v1/titles"
AU_SEARCHES = ("artificial intelligence", "deepfake", "automated decision", "algorithm", "machine learning")


def au_history(t: dict) -> list[dict]:
    """Assent (an Act) or making (an instrument), the day it came into force, and repeal."""
    history = []
    made = (t.get("makingDate") or "")[:10]
    if made:
        history.append({"date": made, "stage": "signed", "text": "Royal Assent" if t.get("collection") == "Act" else "Made"})
    for s in t.get("statusHistory") or []:
        start = (s.get("start") or "")[:10]
        if s.get("status") == "InForce" and start and not any(h["stage"] == "in_force" for h in history):
            history.append({"date": start, "stage": "in_force", "text": "In force"})
        elif s.get("status") == "Repealed" and start:
            history.append({"date": start, "stage": "withdrawn", "text": "Repealed"})
    return sorted(history, key=lambda h: (h["date"], (STAGES + ENDED).index(h["stage"])))


def sync_australia(conn, fetcher=feeds.fetch, log=print) -> int:
    """Australian Acts and legislative instruments with AI in their name."""
    connect_tables(conn)
    found: dict[str, dict] = {}
    for term in AU_SEARCHES:
        data = _get_json(f"{AU_API}?$filter=contains(name,'{term.replace(' ', '%20')}')&$top=100", fetcher)
        for t in data.get("value", []):
            if AI_TITLE.search(t.get("name") or ""):
                found[t["id"]] = t
        time.sleep(0.5)
    changed = 0
    for tid, t in found.items():
        full = _get_json(f"{AU_API}('{tid}')", fetcher)  # the listing leaves out the status history
        bill = {"key": f"AU-{tid}", "jurisdiction": "AU", "number": "", "title": t["name"],
                "url": f"https://www.legislation.gov.au/{tid}/latest/text", "source": "legislation.gov.au",
                "history": au_history(full)}
        if bill["history"]:
            changed += upsert(conn, bill)
        conn.commit()
        time.sleep(0.5)
    return changed


# --- Attaching news to bills ---

_CA_BILL = re.compile(r"\bBill ([CS])-(\d{1,4})\b")
_BILL_NUMBER = re.compile(r"\b(H\.?\s?R\.?|S\.|H\.?\s?J\.?\s?Res\.?|S\.?\s?J\.?\s?Res\.?)\s?(\d{1,5})\b", re.I)


def _number_key(prefix: str, number: str) -> str:
    p = re.sub(r"[\s.]", "", prefix).upper()
    return {"HR": "hr", "S": "s", "HJRES": "hjres", "SJRES": "sjres"}.get(p, p.lower()) + "-" + number


def attach_news(conn) -> int:
    """Put news stories that name a tracked bill (by number or short title) on the bill's card."""
    connect_tables(conn)
    official = ",".join(f"'{s}'" for s in OFFICIAL_SOURCES)
    bills = conn.execute("SELECT b.key, b.short_title, i.id AS card FROM bills b JOIN items i ON i.bill = b.key"
                         f" AND i.source IN ({official})").fetchall()
    if not bills:
        return 0
    by_number = {}
    for b in sorted(bills, key=lambda b: b["key"]):  # a later session's bill with the same number wins
        parts = b["key"].split("-")  # US-119-hr-10538, CA-44-1-C-27
        if parts[0] == "US":
            by_number[f"{parts[2]}-{parts[3]}"] = b["card"]
        elif parts[0] == "CA":
            by_number[f"ca-{parts[3].lower()}-{parts[4]}"] = b["card"]
    # News names a bill without the year that tells same-named UK bills apart ("... Bill (2025)").
    names = [(re.sub(r" \(\d{4}\)$", "", b["short_title"]).lower(), b["card"]) for b in bills if len(b["short_title"]) >= 8]
    moved = 0
    for it in conn.execute("SELECT id, title, cluster FROM items WHERE category IN ('regulation', 'policy')"
                           f" AND source NOT IN ({official})").fetchall():
        card = None
        for m in _BILL_NUMBER.finditer(it["title"]):
            card = by_number.get(_number_key(m.group(1), m.group(2))) or card
        for m in _CA_BILL.finditer(it["title"]):  # "Bill C-27"
            card = by_number.get(f"ca-{m.group(1).lower()}-{m.group(2)}") or card
        low = it["title"].lower()
        card = card or next((c for name, c in names if name in low), None)
        if card and it["cluster"] != card:
            conn.execute("UPDATE items SET cluster = ? WHERE id = ?", (card, it["id"]))
            moved += 1
    conn.commit()
    return moved


def _oecd_api() -> str:
    from . import oecd
    return oecd.API


def _oecd_sync(conn, fetcher=feeds.fetch, log=print) -> int:
    from . import oecd  # oecd.py imports this module
    return oecd.sync(conn, fetcher, log=log)


def sync(conn, fetcher=feeds.fetch, log=print) -> int:
    """Every official source; each is recorded in source health like any feed."""
    total = 0
    for name, url, fn in (("congress.gov API", CONGRESS_API, sync_congress),
                          ("European Parliament API", EP_API, sync_europarl),
                          ("UK Parliament Bills API", UK_API, sync_uk),
                          ("Parliament of Canada LEGISinfo", CA_API, sync_canada),
                          ("Câmara dos Deputados API", BR_API, sync_brazil),
                          ("Federal Register of Legislation API", AU_API, sync_australia),
                          ("Cyberspace Administration of China", CN_SITE, sync_china),
                          ("Parliament of India API", IN_API, sync_india),
                          ("e-Gov law API (Japan)", JP_API, sync_japan),
                          ("National Legal Database (Vietnam)", VN_SITE, sync_vietnam),
                          ("Swiss Parliament open data", CH_API, sync_switzerland),
                          ("Parliament of Malaysia", MY_BILLS, sync_malaysia),
                          ("Legislative Yuan law system (Taiwan)", TW_LAWS, sync_taiwan),
                          ("National Law Information Center (Korea)", KR_SEARCH, sync_korea),
                          ("OECD.AI policy database", _oecd_api(), _oecd_sync)):
        try:
            n = fn(conn, fetcher, log=log)
            store.record_source(conn, name, url, ok=True, added=n)
            log(f"  {name}: {n} bills changed stage")
            total += n
        except Exception as exc:
            store.record_source(conn, name, url, ok=False, error=str(exc) or type(exc).__name__)
            log(f"  ! {name}: {exc}")
        conn.commit()
    refresh_cards(conn)
    return total
