"""Australia: legislation from the Federal Register of Legislation API."""
from __future__ import annotations

import time

from .. import feeds

from .core import AI_TITLE, DATA_LAWS, ENDED, STAGES, _get_json, connect_tables, upsert


# --- Australia (Federal Register of Legislation) ---

AU_API = "https://api.prod.legislation.gov.au/v1/titles"


AU_SEARCHES = ("artificial intelligence", "deepfake", "automated decision", "algorithm", "machine learning",
               "Privacy Act", "Privacy Amendment", "Privacy Legislation Amendment", "Privacy and Other Legislation")


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
            if AI_TITLE.search(t.get("name") or "") or (  # a privacy Act still in force
                    DATA_LAWS["AU"].search(t.get("name") or "") and t.get("status") != "Repealed"):
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
