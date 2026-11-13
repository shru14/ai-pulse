"""European Union: procedures in the European Parliament, from its open data API."""
from __future__ import annotations

import re
import time
from datetime import date

from .. import feeds

from .core import AI_TITLE, DATA_LAWS, _get_json, connect_tables, eu_history, upsert


# --- EU (European Parliament open data) ---

EP_API = "https://data.europarl.europa.eu/api/v2"


EP_FORMAT = "format=application%2Fld%2Bjson"


EU_DATA = ("2012-0011", "2020-0340", "2022-0047")  # the GDPR, the Data Governance Act and the Data Act


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
            conn.execute("INSERT OR REPLACE INTO eu_procedures VALUES (?,?,?)",
                         (pid, title, int(bool(AI_TITLE.search(title) or DATA_LAWS["EU"].search(title)))))
            conn.commit()
            time.sleep(0.2)
    for pid, title in conn.execute("SELECT id, title FROM eu_procedures WHERE is_ai = 0").fetchall():
        if DATA_LAWS["EU"].search(title):  # read before data laws were kept
            conn.execute("UPDATE eu_procedures SET is_ai = 1 WHERE id = ?", (pid,))
    for pid in EU_DATA:
        if not conn.execute("SELECT 1 FROM eu_procedures WHERE id = ? AND is_ai = 1", (pid,)).fetchone():
            title = (_procedure(pid, fetcher).get("process_title") or {}).get("en") or ""
            conn.execute("INSERT OR REPLACE INTO eu_procedures VALUES (?,?,1)", (pid, title))
            time.sleep(0.2)
    conn.commit()
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
