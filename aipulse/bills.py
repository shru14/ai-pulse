"""Follow AI bills through their lifecycle from official sources.

- US Congress: the congress.gov API (free key from https://api.congress.gov/sign-up/, set CONGRESS_API_KEY;
  without one the public DEMO_KEY is used, which allows only ~30 requests an hour). Each collection asks for
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
- Australia: the Federal Register of Legislation API (no key; CC BY 4.0, credited on the page). It holds Acts
  and instruments once made (bills in Parliament aren't there), so these cards start at assent.

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

from . import feeds, store, translate

# Cards made from official records; the keyword rules for news stories never re-sort them.
OFFICIAL_SOURCES = ("congress.gov", "European Parliament", "UK Parliament", "Parliament of Canada",
                    "Câmara dos Deputados", "legislation.gov.au", "Cyberspace Administration of China",
                    "Parliament of India")

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
    name = bill.get("short_title") or bill["title"]
    summary = _summary(bill["jurisdiction"], bill["history"])
    lang = bill.get("lang")  # an official record in another language: its English version, if made
    english = lang and translate.cached(conn, lang, bill["title"])
    if english:
        name = english
        summary += f" Title machine-translated from {translate.LANGUAGE_NAMES[lang]}; the official text is linked."
    title = f"{bill['number']}: {name}" if bill["number"] else name
    if len(title) > 220:  # long official summaries: cut at a word
        title = title[:219].rsplit(" ", 1)[0].rstrip(",;:") + "…"
    item = {"title": title, "summary": summary, "url": bill["url"], "source": bill["source"],
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
        history = uk_history(b, stages)
        # Bills are often reintroduced under the same name in a later session: the year tells them apart.
        year = next((h["date"][:4] for h in history if h["stage"] == "introduced"), "")
        short = re.sub(r"\s*\[HL\]$", "", b["shortTitle"])
        bill = {"key": f"GB-{bill_id}", "jurisdiction": "GB", "number": "", "title": b["shortTitle"],
                "short_title": f"{short} ({year})" if year else short,
                "url": f"https://bills.parliament.uk/bills/{bill_id}", "source": "UK Parliament", "history": history}
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
    done = conn.execute("SELECT value FROM meta WHERE key = 'canada_sessions'").fetchone()
    past = [s for s in CA_PAST_SESSIONS if not done or s not in done[0].split(",")]
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
                    "source": "Parliament of Canada", "history": ca_history(b, CA_PAST_SESSIONS.get(s, ""))}
            if bill["history"]:
                changed += upsert(conn, bill)
        conn.commit()
        time.sleep(1)
    if past:
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('canada_sessions', ?)", (",".join(CA_PAST_SESSIONS),))
        conn.commit()
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


def retitle(conn, jurisdiction: str, lang: str) -> int:
    """Give every card from one jurisdiction the English version of its title (translating the ones not
    done yet, when the translator is available). Returns how many cards have one."""
    rows = conn.execute("SELECT * FROM bills WHERE jurisdiction = ?", (jurisdiction,)).fetchall()
    found = translate.english(conn, lang, [r["title"] for r in rows])
    for r in rows:
        if r["title"] in found:
            upsert(conn, {"key": r["key"], "jurisdiction": jurisdiction, "number": r["number"], "title": r["title"],
                          "short_title": r["short_title"], "url": r["url"], "source": r["source"],
                          "history": json.loads(r["history"]), "lang": lang})
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
                          ("Parliament of India API", IN_API, sync_india)):
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
