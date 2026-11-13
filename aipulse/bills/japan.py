"""Japan: laws from the e-Gov law API."""
from __future__ import annotations

import time
from datetime import date

from .. import feeds, translate

from .core import DATA_LAWS, ENDED, STAGES, _get_json, connect_tables, retitle, upsert


# --- Japan (e-Gov law API) ---

JP_API = "https://laws.e-gov.go.jp/api/2/laws"


JP_SEARCHES = ("人工知能", "生成ＡＩ", "ディープフェイク")


JP_DATA = "個人情報の保護に関する法律"  # the APPI: its search also finds laws that only name it, so DATA_LAWS picks


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
    for term in (*JP_SEARCHES, JP_DATA):
        for law in _get_json(f"{JP_API}?law_title={quote(term)}", fetcher).get("laws") or []:
            title = (law.get("current_revision_info") or law.get("revision_info") or {}).get("law_title") or ""
            if term != JP_DATA or DATA_LAWS["JP"].search(title):
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
