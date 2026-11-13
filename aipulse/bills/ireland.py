"""Ireland: bills in the Houses of the Oireachtas, from their API."""
from __future__ import annotations

import time

from .. import feeds

from .core import AI_TITLE, DATA_LAWS, ENDED, STAGES, _get_json, connect_tables, describe, upsert


# --- Ireland (Houses of the Oireachtas open data API) ---
# Every bill since IE_SINCE from api.oireachtas.ie (its robots.txt allows it), under the Oireachtas (Open Data) PSI
# Licence, which incorporates CC BY 4.0 (https://www.oireachtas.ie/en/open-data/license/); AI_TITLE keeps the AI
# bills. Only the bill's own record is kept: title, long title, stages and link (not its sponsors).

IE_API = "https://api.oireachtas.ie/v1/legislation"


IE_SINCE = "2020-01-01"


IE_PAGE = 500


IE_DATA_YEARS = (2018,)  # the Data Protection Act 2018's bill, from before IE_SINCE


def ie_history(b: dict) -> list[dict]:
    """Lifecycle from a bill's stages: First Stage, the Fifth Stage in each House, the Act signed; or how it ended."""
    reached: dict[str, dict] = {}
    passed: dict[str, str] = {}
    for s in b.get("stages") or []:
        e = s.get("event") or {}
        dates = sorted(d["date"] for d in e.get("dates") or [] if d.get("date"))
        if not dates:
            continue
        house = (e.get("house") or {}).get("houseCode") or ""
        where = (e.get("chamber") or {}).get("showAs") or ""
        if e.get("showAs") == "First Stage" and ("introduced" not in reached or dates[0] < reached["introduced"]["date"]):
            reached["introduced"] = {"date": dates[0], "stage": "introduced", "text": f"First Stage, {where}".rstrip(", ")}
        elif e.get("showAs") == "Fifth Stage" and e.get("stageCompleted") and house:
            passed.setdefault(house, dates[-1])
    if passed:
        reached["passed_chamber"] = {"date": min(passed.values()), "stage": "passed_chamber", "text": "Fifth Stage"}
        if len(passed) == 2:
            reached["passed_legislature"] = {"date": max(passed.values()), "stage": "passed_legislature",
                                             "text": "Passed by the Dáil and the Seanad"}
    act = b.get("act") or {}
    if act.get("dateSigned"):
        reached["signed"] = {"date": act["dateSigned"][:10], "stage": "signed",
                             "text": f"Signed into law: Act No. {act.get('actNo')} of {act.get('actYear')}"}
    status = b.get("status") or ""
    if status in ("Lapsed", "Withdrawn", "Defeated", "Rejected") and reached:
        recent = [d["date"] for d in ((b.get("mostRecentStage") or {}).get("event") or {}).get("dates") or []
                  if d.get("date")]
        last = max(recent) if recent else (b.get("lastUpdated") or "")[:10]
        stage = "withdrawn" if status in ("Lapsed", "Withdrawn") else "vetoed"
        reached[stage] = {"date": max(last, max(h["date"] for h in reached.values())), "stage": stage, "text": status}
    return sorted(reached.values(), key=lambda h: (h["date"], (STAGES + ENDED).index(h["stage"])))


def sync_ireland(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI bills in the Oireachtas (Dáil and Seanad) since IE_SINCE, and their stages."""
    connect_tables(conn)
    found, skip = [], 0
    while True:
        page = _get_json(f"{IE_API}?date_start={IE_SINCE}&limit={IE_PAGE}&skip={skip}", fetcher).get("results") or []
        found += [r["bill"] for r in page if AI_TITLE.search((r.get("bill") or {}).get("shortTitleEn") or "")
                  or DATA_LAWS["IE"].search((r.get("bill") or {}).get("shortTitleEn") or "")]
        if len(page) < IE_PAGE:
            break
        skip += IE_PAGE
        time.sleep(0.5)
    for year in IE_DATA_YEARS:
        page = _get_json(f"{IE_API}?bill_year={year}&limit={IE_PAGE}", fetcher).get("results") or []
        found += [r["bill"] for r in page if DATA_LAWS["IE"].search((r.get("bill") or {}).get("shortTitleEn") or "")]
    found = list({(b.get("billYear"), b.get("billNo")): b for b in found}.values())
    changed = 0
    for b in found:
        no, year = b.get("billNo"), b.get("billYear")
        bill = {"key": f"IE-{year}-{no}", "jurisdiction": "IE", "number": f"Bill {no} of {year}",
                "title": b["shortTitleEn"], "url": f"https://www.oireachtas.ie/en/bills/bill/{year}/{no}/",
                "source": "Houses of the Oireachtas", "history": ie_history(b),
                "summary": describe(b.get("longTitleEn") or "", b["shortTitleEn"])}
        changed += upsert(conn, bill)
        conn.commit()
    return changed
