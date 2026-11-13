"""India: bills in Parliament, from its API."""
from __future__ import annotations

import re
import time

from .. import feeds

from .core import AI_TITLE, DATA_LAWS, _get_json, connect_tables, upsert


# --- India (Parliament of India, sansad.in) ---

IN_API = "https://sansad.in/api_rs/legislation/getBills"


IN_SEARCHES = ("artificial intelligence", "deepfake", "algorithm", "machine learning", "automated decision",
               "digital personal data protection")


_IN_QUERY = ("loksabha=&sessionNo=&house=&ministryName=&billType=&billCategory=&billStatus=&introductionDateFrom="
             "&introductionDateTo=&passedInLsDateFrom=&passedInLsDateTo=&passedInRsDateFrom=&passedInRsDateTo="
             "&page=1&size=50&locale=en&sortOn=billIntroducedDate&sortBy=desc")


def in_history(b: dict) -> list[dict]:
    """Introduction, passing in each House and assent. (Lapsed or withdrawn bills have no date for it, so
    they stay at their last dated stage.)"""
    def day(k):  # "2023-08-03 00:00:00.0", or "11/08/2023" (day first) for some assent dates
        d = (b.get(k) or "")[:10]
        return f"{d[6:]}-{d[3:5]}-{d[:2]}" if re.fullmatch(r"\d\d/\d\d/\d{4}", d) else d
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
            if AI_TITLE.search(b.get("billName") or "") or DATA_LAWS["IN"].search(b.get("billName") or ""):
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
