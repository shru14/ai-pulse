"""Norway: proposals in the Storting, from its open data."""
from __future__ import annotations

import re
import time

from .. import feeds, translate

from .core import DATA_LAWS, ENDED, STAGES, _get_json, connect_tables, upsert


# --- Norway (Stortinget open data, data.stortinget.no) ---
# The Storting's cases (saker) in the last NO_SESSIONS sessions, under the Norwegian Licence for Open Government
# Data (NLOD; Stortinget credited as the source: https://data.stortinget.no/om-datatjenesten/bruksvilkar/; robots.txt
# allows it, and a run makes a few calls of the 100 a minute allowed). NO_AI keeps the AI cases by title; for each,
# only the case's own record is read (title, its steps and dates, the decision), never the people in it.

NO_API = "https://data.stortinget.no/eksport"


NO_SESSIONS = 4  # the current session and the three before it


NO_DATA_FROM = "2017-2018"  # data protection cases from this session on: the Personal Data Act 2018 and its amendments


NO_AI = re.compile(r"kunstig intelligens|\bKI\b|algoritm|maskinlæring|deepfake|chatbot", re.I)


_NO_DATE = re.compile(r"^(\d\d)\.(\d\d)\.(\d{4})")


def _no_day(text: str) -> str:
    m = _NO_DATE.match(text or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m and m.group(3) != "0001" else ""


def no_history(case: dict) -> list[dict]:
    """Lifecycle from a case's steps: put forward (FREMSATT), then the Storting's decision once it's dealt with, as
    its short decision says: "Stortinget vedtok …" (adopted) or "Forslaget ble ikke vedtatt" (not adopted)."""
    events = [(h.get("id") or "", _no_day(h.get("dato")))
              for step in (case.get("saksgang") or {}).get("saksgang_steg_liste") or []
              for h in step.get("saksgang_hendelse_liste") or []]
    days = sorted(d for _, d in events if d)
    if not days:
        return []
    start = next((d for e, d in events if e == "FREMSATT" and d), days[0])
    reached = {"introduced": {"date": start, "stage": "introduced", "text": "Put forward in the Storting"}}
    if case.get("ferdigbehandlet"):
        said = f"{case.get('kortvedtak') or ''} {case.get('vedtakstekst') or ''}"
        adopted = not re.search(r"ikke vedtatt|bifalles ikke|vedlegges protokollen", said) and (
            re.search(r"\bvedtok\b|\bhar vedtatt\b", said) or "Lovvedtak" in (case.get("henvisning") or ""))  # a law decision
        stage = "passed_legislature" if adopted else "vetoed"
        reached[stage] = {"date": days[-1], "stage": stage,
                          "text": "Adopted by the Storting" if adopted else "Not adopted by the Storting"}
    return sorted(reached.values(), key=lambda h: (h["date"], (STAGES + ENDED).index(h["stage"])))


def sync_norway(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI cases in the Storting over the last NO_SESSIONS sessions, and how they were decided."""
    connect_tables(conn)
    sessions = _get_json(f"{NO_API}/sesjoner?format=json", fetcher)
    current = sessions["innevaerende_sesjon"]["id"]
    ids = [s["id"] for s in sessions["sesjoner_liste"] if NO_DATA_FROM <= s["id"] <= current]
    found: dict[int, dict] = {}
    for sid in ids:
        for c in _get_json(f"{NO_API}/saker?sesjonid={sid}&format=json", fetcher).get("saker_liste") or []:
            # proposals only: members' (Dokument 8) and the government's (Prop.), not reports or debates
            said = f"{c.get('korttittel') or ''} {c.get('tittel') or ''}"
            if ((sid in ids[:NO_SESSIONS] and NO_AI.search(said)) or DATA_LAWS["NO"].search(said)) \
                    and re.match(r"Dokument 8|Prop\.", c.get("henvisning") or ""):
                found[c["id"]] = c
        time.sleep(1)
    translate.english(conn, "nb", [c.get("korttittel") or c["tittel"] for c in found.values()])
    changed = 0
    for case_id, c in found.items():
        case = _get_json(f"{NO_API}/sak?sakid={case_id}&format=json", fetcher)
        title = c.get("korttittel") or c["tittel"]
        bill = {"key": f"NO-{case_id}", "jurisdiction": "NO", "number": (c.get("henvisning") or "").split(",")[0],
                "title": title, "url": f"https://www.stortinget.no/no/Saker-og-publikasjoner/Saker/Sak/?p={case_id}",
                "source": "Stortinget", "history": no_history(case), "lang": "nb"}
        changed += upsert(conn, bill)
        conn.commit()
        time.sleep(1)
    return changed
