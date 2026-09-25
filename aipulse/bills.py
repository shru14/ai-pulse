"""Follow AI bills through their lifecycle from official sources.

- US Congress: the congress.gov API (free key from https://api.congress.gov/sign-up/, set CONGRESS_API_KEY;
  without one the public DEMO_KEY is used, which allows only ~30 requests an hour). Each collection asks for
  bills updated since the last sync, keeps those with AI in the title, and reads their official actions.
- EU: the European Parliament's open data API (no key). AI procedures are found by their English title;
  their events give the stages.

Every bill has one tracker card (an item with source "congress.gov" or "European Parliament"), dated at
its latest stage so it moves up the feed when it advances. The card shows the whole timeline. News
stories that name the bill (by number, or by short title) are attached to that card.

State legislatures need an Open States API key and aren't connected yet; the OECD.AI policy database
has no public API.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone

from . import feeds, store

# Cards made from official records; the keyword rules for news stories never re-sort them.
OFFICIAL_SOURCES = ("congress.gov", "European Parliament")

# Lifecycle, in order. A bill's stage is the furthest one reached; vetoed / withdrawn end it.
STAGES = ["introduced", "passed_chamber", "passed_legislature", "signed", "in_force"]
ENDED = ["vetoed", "withdrawn"]
LABELS = {
    "US": {"introduced": "Introduced", "passed_chamber": "Passed one chamber", "passed_legislature": "Passed Congress",
           "signed": "Signed", "in_force": "Became law", "vetoed": "Vetoed", "withdrawn": "Withdrawn"},
    "EU": {"introduced": "Proposed", "passed_chamber": "Parliament position", "passed_legislature": "Final vote",
           "signed": "Signed", "in_force": "Published in Official Journal", "vetoed": "Rejected",
           "withdrawn": "Withdrawn"},
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

def _summary(jur: str, history: list[dict]) -> str:
    labels = LABELS[jur]
    now = current(history)
    parts = [f"{labels[now['stage']]} on {now['date']}."]
    earlier = [h for h in history if h is not now]
    if earlier:
        parts.append("Earlier: " + "; ".join(f"{labels[h['stage']].lower()} {h['date']}" for h in earlier[-3:]) + ".")
    return " ".join(parts)


def upsert(conn, bill: dict) -> bool:
    """Save a bill and its tracker card. Returns True if its stage changed (or it's new)."""
    now = current(bill["history"])
    if not now:
        return False
    prev = conn.execute("SELECT stage, stage_date FROM bills WHERE key = ?", (bill["key"],)).fetchone()
    changed = not prev or (prev[0], prev[1]) != (now["stage"], now["date"])
    conn.execute(
        "INSERT OR REPLACE INTO bills (key, jurisdiction, number, title, short_title, url, stage, stage_date, history,"
        " source, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (bill["key"], bill["jurisdiction"], bill["number"], bill["title"], bill.get("short_title", ""), bill["url"],
         now["stage"], now["date"], json.dumps(bill["history"]), bill["source"],
         datetime.now(timezone.utc).isoformat(timespec="seconds")))
    item = {"title": f"{bill['number']}: {bill.get('short_title') or bill['title']}"[:220],
            "summary": _summary(bill["jurisdiction"], bill["history"]), "url": bill["url"], "source": bill["source"],
            "category": "regulation", "date": now["date"],
            "action": "law" if now["stage"] in ("signed", "in_force") else "proposal",
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
    return os.environ.get("CONGRESS_API_KEY") or "DEMO_KEY"


def _get_json(url: str, fetcher=feeds.fetch) -> dict:
    return json.loads(fetcher(url))


def sync_congress(conn, fetcher=feeds.fetch, since: datetime | None = None, max_pages: int = 8,
                  log=print) -> int:
    """Check bills updated since the last sync (or `since`); returns how many AI bills changed stage."""
    connect_tables(conn)
    key = _congress_key()
    last = conn.execute("SELECT value FROM meta WHERE key = 'congress_sync'").fetchone()
    start = since or (datetime.fromisoformat(last[0]) if last else datetime.now(timezone.utc) - timedelta(days=30))
    started = datetime.now(timezone.utc)
    url = (f"{CONGRESS_API}/bill?format=json&limit=250&sort=updateDate+desc"
           f"&fromDateTime={start.strftime('%Y-%m-%dT%H:%M:%SZ')}&api_key={key}")
    changed = pages = 0
    while url and pages < max_pages:
        data = _get_json(url, fetcher)
        pages += 1
        for b in data.get("bills", []):
            if b.get("type") not in _US_TYPES or not AI_TITLE.search(b.get("title", "")):
                continue
            acts = _get_json(f"{CONGRESS_API}/bill/{b['congress']}/{b['type'].lower()}/{b['number']}/actions"
                             f"?format=json&limit=250&api_key={key}", fetcher)
            label, path = _US_TYPES[b["type"]]
            bill = {"key": f"US-{b['congress']}-{b['type'].lower()}-{b['number']}", "jurisdiction": "US",
                    "number": f"{label} {b['number']}", "title": b["title"],
                    "url": f"https://www.congress.gov/bill/{b['congress']}th-congress/{path}/{b['number']}",
                    "source": "congress.gov", "history": us_history(acts.get("actions", []))}
            changed += upsert(conn, bill)
            conn.commit()  # keep progress if a later request fails (e.g. the rate limit)
            time.sleep(0.2)
        nxt = (data.get("pagination") or {}).get("next")
        # congress.gov's next-page link contains a raw space ("sort=updateDate desc").
        url = f"{nxt.replace(' ', '+')}&api_key={key}" if nxt else None
    if url is None:  # read everything: next time, start from here
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('congress_sync', ?)", (started.isoformat(),))
    else:
        log(f"  congress.gov: more updates than {max_pages} pages; the rest next run")
        # keep the old start so the next run continues; nothing is lost
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


# --- Attaching news to bills ---

_BILL_NUMBER = re.compile(r"\b(H\.?\s?R\.?|S\.|H\.?\s?J\.?\s?Res\.?|S\.?\s?J\.?\s?Res\.?)\s?(\d{1,5})\b", re.I)


def _number_key(prefix: str, number: str) -> str:
    p = re.sub(r"[\s.]", "", prefix).upper()
    return {"HR": "hr", "S": "s", "HJRES": "hjres", "SJRES": "sjres"}.get(p, p.lower()) + "-" + number


def attach_news(conn) -> int:
    """Put news stories that name a tracked bill (by number or short title) on the bill's card."""
    connect_tables(conn)
    bills = conn.execute("SELECT b.key, b.short_title, i.id AS card FROM bills b JOIN items i ON i.bill = b.key"
                         " AND i.source IN ('congress.gov', 'European Parliament')").fetchall()
    if not bills:
        return 0
    by_number = {}
    for b in bills:
        parts = b["key"].split("-")  # US-119-hr-10538
        if parts[0] == "US":
            by_number[f"{parts[2]}-{parts[3]}"] = b["card"]
    names = [(b["short_title"].lower(), b["card"]) for b in bills if len(b["short_title"]) >= 8]
    moved = 0
    for it in conn.execute("SELECT id, title, cluster FROM items WHERE category IN ('regulation', 'policy')"
                           " AND source NOT IN ('congress.gov', 'European Parliament')").fetchall():
        card = None
        for m in _BILL_NUMBER.finditer(it["title"]):
            card = by_number.get(_number_key(m.group(1), m.group(2))) or card
        low = it["title"].lower()
        card = card or next((c for name, c in names if name in low), None)
        if card and it["cluster"] != card:
            conn.execute("UPDATE items SET cluster = ? WHERE id = ?", (card, it["id"]))
            moved += 1
    conn.commit()
    return moved


def sync(conn, fetcher=feeds.fetch, log=print) -> int:
    """Both sources; each is recorded in source health like any feed."""
    total = 0
    for name, url, fn in (("congress.gov API", CONGRESS_API, sync_congress),
                          ("European Parliament API", EP_API, sync_europarl)):
        try:
            n = fn(conn, fetcher, log=log)
            store.record_source(conn, name, url, ok=True, added=n)
            log(f"  {name}: {n} bills changed stage")
            total += n
        except Exception as exc:
            store.record_source(conn, name, url, ok=False, error=str(exc) or type(exc).__name__)
            log(f"  ! {name}: {exc}")
        conn.commit()
    return total
