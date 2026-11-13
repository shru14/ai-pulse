"""United Kingdom: bills in Parliament, from the UK Parliament Bills API."""
from __future__ import annotations

import re
import time

from .. import feeds

from .core import AI_TITLE, DATA_LAWS, ENDED, STAGES, _get_json, connect_tables, describe, upsert


# --- UK (UK Parliament Bills API) ---

UK_API = "https://bills-api.parliament.uk/api/v1"


# The API's search matches bill titles; AI_TITLE then keeps only AI bills.
UK_SEARCHES = ("artificial intelligence", "algorithm", "automated decision", "deepfake", "machine learning", "chatbot",
               "data protection", "data use and access")


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
            if AI_TITLE.search(b.get("shortTitle") or "") or DATA_LAWS["GB"].search(b.get("shortTitle") or ""):
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
