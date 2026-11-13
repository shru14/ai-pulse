"""What every official source shares: stages, labels, the bills table, upsert, lifecycle, describe."""
from __future__ import annotations

import logging
import json
import re
from datetime import datetime, timezone

from .. import feeds, store, translate


logger = logging.getLogger("aipulse.bills")  # one name for the whole package


# Cards made from official records; the keyword rules for news stories never re-sort them.
OFFICIAL_SOURCES = ("congress.gov", "European Parliament", "UK Parliament",
                    "Câmara dos Deputados", "legislation.gov.au", "Cyberspace Administration of China",
                    "Parliament of India", "e-Gov (Japan)", "National Legal Database (Vietnam)", "Swiss Parliament", "Parliament of Malaysia",
                    "Legislative Yuan (Taiwan)", "National Law Information Center (Korea)",
                    "Houses of the Oireachtas", "Stortinget", "OECD.AI", "ISO/IEC", "IEEE SA")


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
    "IE": {"introduced": "Introduced", "passed_chamber": "Passed one House", "passed_legislature": "Passed both Houses",
           "signed": "Signed into law", "in_force": "In force", "vetoed": "Defeated", "withdrawn": "Lapsed or withdrawn"},
    "NO": {"introduced": "Put forward", "passed_chamber": "Debated", "passed_legislature": "Adopted by the Storting",
           "signed": "Sanctioned", "in_force": "In force", "vetoed": "Not adopted", "withdrawn": "Withdrawn"},
    "AU": {"introduced": "Introduced", "passed_chamber": "Passed first House", "passed_legislature": "Passed Parliament",
           "signed": "Assented or made", "in_force": "In force", "vetoed": "Disallowed", "withdrawn": "Repealed"},
}


AI_TITLE = re.compile(r"artificial intelligence|\bAI\b|machine learning|algorithm|deepfake|automated decision|"
                      r"chatbot|digital replica|2024/1689", re.I)


# Each place's main data protection law (the data AI is built on), by its title in the place's own source, kept
# beside its AI records: the law itself and the bills amending it, never every privacy bill. (A Vietnamese
# document by its address; Brazil's LGPD and the EU's older data laws are looked up by number, BR_DATA, EU_DATA.)
DATA_LAWS = {code: re.compile(p, re.I) for code, p in {
    "IN": r"digital personal data protection",
    "GB": r"^Data Protection\b|^Data \(Use and Access\)",
    "EU": r"\((General Data Protection Regulation|Data Governance Act|Data Act)\)|Regulation \(EU\) 2016/679",
    "IE": r"^Data Protection\b",
    "AU": r"^Privacy\b.*\bAct \d{4}$",  # the Privacy Act 1988 and the Acts amending it
    "NO": r"personopplysningsloven",
    "CH": r"^Datenschutzgesetz|Datenschutzgesetz\w* anpassen|Präzisierung des Datenschutzgesetzes",
    "JP": r"^個人情報の保護に関する法律(施行令|施行規則)?$",
    "KR": r"^개인정보 보호법( 시행령| 시행규칙)?$",
    "TW": r"^個人資料保護法$",
    "CN": r"个人信息保护法|数据安全法|网络数据安全管理条例",
    "VN": r"bao-ve-du-lieu-ca-nhan",
}.items()}


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
    from .. import brief
    text = _HEADING.sub("", text or "")  # CRS summaries open with the bill's name in bold
    text = re.sub(r"\s+", " ", _TAGS.sub(" ", text)).strip()
    if title and text.lower().startswith(title.lower()):
        text = text[len(title):].lstrip(" .:-")
    return brief.clean_summary(text, title) if text else ""


def upsert(conn, bill: dict) -> bool:
    """Save a bill and its tracker card. Returns True if its stage changed (or it's new)."""
    from .us import _US_OTHER, us_interim  # here, not at the top: us.py imports this module
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


def _get_json(url: str, fetcher=feeds.fetch) -> dict:
    return json.loads(fetcher(url))


_LANGS = {"BR": "pt", "CN": "zh", "JP": "ja", "VN": "vi", "CH": "de", "TW": "zh", "NO": "nb"}  # records whose titles are translated


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
