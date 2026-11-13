"""Switzerland: business of the Federal Assembly, from its open data."""
from __future__ import annotations

import html
import re
import time
from datetime import datetime, timedelta, timezone

from .. import feeds, store, translate

from .core import DATA_LAWS, _get_json, connect_tables, upsert


# --- Switzerland (Swiss Parliament open data, ws.parlament.ch) ---

CH_API = "https://ws.parlament.ch/odata.svc/Business"


CH_SEARCHES = ("künstliche Intelligenz", "Künstliche Intelligenz", "KI", "Deepfake", "Algorithm", "Datenschutzgesetz")


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
    bill = r.get("BusinessTypeName") == "Geschäft des Bundesrates"  # "Erledigt": Parliament is done with it (final vote)
    stage = ("passed_legislature" if status.startswith(("Überwiesen an den Bundesrat", "Erfüllt")) or (bill and status == "Erledigt")
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
            if term == "Datenschutzgesetz" and not DATA_LAWS["CH"].search(r["Title"]):
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
