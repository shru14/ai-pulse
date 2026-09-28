"""AI incidents for the Industry stream, from the AI Incident Database (incidentdatabase.ai, Responsible AI
Collaborative): harms from AI systems that its editors confirmed. One card per incident since 1 January 2023,
labelled "AI-incident": the editors' title and description, the date it happened, linked to the incident's page.

- Weekly: the database's own Excel export (published every Monday on its snapshots page) gives every incident,
  and the links of the articles ("reports") its editors attached to incidents.
- Every run: its RSS feed of the latest reports. A report of an incident we don't have yet brings that incident
  (its page is read once for title, description and date); the snapshot confirms it the next Monday.
- Our own feeds' stories: labelled only when the database lists that very article (same link or headline).
  When the RSS feed says which incident it belongs to, the story joins that incident's card.

Legal: no robots.txt; the terms bar only high-volume automated access and commercial use. Incident data
(titles, descriptions) is CC BY-SA 4.0, credited on the page and in the README, and stays under that licence
here. A report's own text isn't under the licence, so it's never copied: of reports only the link is used.
"""

from __future__ import annotations

import html
import io
import re
import zipfile
from datetime import date, timedelta
from xml.etree import ElementTree as ET

from . import classify, feeds, jurisdictions, store

SITE = "https://incidentdatabase.ai"
SNAPSHOTS = SITE + "/research/snapshots/"
FEED = SITE + "/rss.xml"
SOURCE = "AI Incident Database"
SINCE = "2023-01-01"
INCIDENT = "incident"  # items.action
MARK = "AIID-"  # items.bill: the incident number; its card and our stories about it share a card (cluster.py)
SNAPSHOT_KEY = "aiid_export"  # meta: the export last read
_EXPORT = re.compile(r"https://[\w.-]+/AIID_Excel_Export-\d{8}\.xlsx")
_CITE = re.compile(r"incidentdatabase\.ai/cite/(\d+)")
_X = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def incident_url(number: str) -> str:
    return f"{SITE}/cite/{number}"


HEADERS = {"Incident ID", "Report Number"}  # the first column name of each sheet used here


def read_xlsx(data: bytes) -> dict[str, list[dict]]:
    """Each sheet's rows as dicts keyed by its header row: the first row starting with one of HEADERS (the
    export puts a title and a row of section names above it). Sheets without one come back empty."""
    z = zipfile.ZipFile(io.BytesIO(data))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        shared = ["".join(t.text or "" for t in si.iter(_X + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
    out = {}
    for sh in ET.fromstring(z.read("xl/workbook.xml")).find(_X + "sheets"):
        rid = sh.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
        target = rels[rid].lstrip("/").removeprefix("xl/")
        header, rows = None, []
        for r in ET.fromstring(z.read("xl/" + target)).iter(_X + "row"):
            cells = {}
            for c in r.findall(_X + "c"):
                col = "".join(ch for ch in c.get("r") if ch.isalpha())
                v = c.find(_X + "v")
                if v is None:
                    cells[col] = "".join(t.text or "" for t in c.iter(_X + "t")).strip()
                else:
                    cells[col] = (shared[int(v.text)] if c.get("t") == "s" else v.text or "").strip()
            if header is None:
                if cells.get("A") in HEADERS:
                    header = cells
                continue
            rows.append({header[k]: v for k, v in cells.items() if k in header})
        out[sh.get("name")] = rows
    return out


def _day(value: str) -> str:
    """An Excel date (days since 1899-12-30) or an ISO date, as YYYY-MM-DD ("" if neither)."""
    if re.fullmatch(r"\d+(\.\d+)?", value or ""):
        return (date(1899, 12, 30) + timedelta(days=int(float(value)))).isoformat()
    return value[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", value or "") else ""


def card(number: str, day: str, title: str, description: str, country: str = "") -> dict:
    """The Industry card for one incident. Places come from the database's country, else from the text."""
    tags = classify.tags_for(title, description)
    code = country.strip().upper()
    if code in jurisdictions.JURISDICTIONS and (name := jurisdictions.JURISDICTIONS[code][0]) not in tags:
        tags = [name, *tags]
    return {"title": title.strip()[:220], "summary": description.strip(), "url": incident_url(number), "source": SOURCE,
            "category": "news", "action": INCIDENT, "date": day, "tags": tags[:5], "authors": [], "bill": MARK + number}


def _store(conn, c: dict) -> bool:
    """Insert or update an incident's card. True if new."""
    if store.exists(conn, c["url"]):
        conn.execute("UPDATE items SET title = ?, summary = ?, date = ?, tags = ?, category = 'news', action = ?,"
                     " jurisdictions = '', bill = ? WHERE id = ?",
                     (c["title"], c["summary"], c["date"], ",".join(c["tags"]), INCIDENT, c["bill"], store.item_id(c["url"])))
        return False
    if store.insert(conn, c):
        conn.execute("UPDATE items SET bill = ? WHERE id = ?", (c["bill"], store.item_id(c["url"])))
        return True
    return False


def sync_snapshot(conn, fetcher=feeds.fetch, log=print) -> int:
    """Read the newest weekly export, once. Returns how many incidents are new."""
    newest = max(_EXPORT.findall(fetcher(SNAPSHOTS).decode("utf-8", "replace")), default=None)
    last = conn.execute("SELECT value FROM meta WHERE key = ?", (SNAPSHOT_KEY,)).fetchone()
    if not newest or (last and last[0] == newest):
        return 0
    sheets = read_xlsx(fetcher(newest))
    added = 0
    for r in sheets.get("Incidents", []):
        day = _day(r.get("date", ""))
        if r.get("Incident ID", "").isdigit() and day >= SINCE and r.get("title"):
            added += _store(conn, card(r["Incident ID"], day, r["title"], r.get("description", ""), r.get("Country Code", "")))
    labelled = sum(store.mark_incident(conn, r["URL"], r.get("Title", ""))
                   for r in sheets.get("Reports", []) if r.get("Is Incident Report") == "1" and r.get("URL"))
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (SNAPSHOT_KEY, newest))
    conn.commit()
    log(f"  AI Incident Database export: {added} new incidents, {labelled} of our stories labelled")
    return added


def _page(number: str, fetcher) -> tuple[str, str, str]:
    """(title, description, incident date) from an incident's page."""
    page = fetcher(incident_url(number) + "/").decode("utf-8", "replace")
    meta = lambda prop: html.unescape((re.search(rf'<meta[^>]*property="og:{prop}"[^>]*content="([^"]*)"', page) or [None, ""])[1])
    title = re.sub(rf"^Incident {number}:\s*", "", meta("title"))
    day = re.search(r"Incident Date\s*(?:<[^>]+>\s*)*(\d{4}-\d{2}-\d{2})", page)
    return title, meta("description"), day.group(1) if day else ""


def sync_feed(conn, fetcher=feeds.fetch, log=print) -> int:
    """The latest reports: new incidents, and our stories that are reports of an incident. Returns new incidents."""
    added = 0
    for e in feeds.parse(fetcher(FEED)):
        number = _CITE.search(e.get("summary") or "")
        if not number:
            continue  # a report not yet assigned to an incident: not confirmed
        n = number.group(1)
        seen = f"aiid_before_{SINCE}_{n}"  # an incident from before SINCE: its page is read once, not every run
        if not store.exists(conn, incident_url(n)) and not conn.execute("SELECT 1 FROM meta WHERE key = ?", (seen,)).fetchone():
            title, description, day = _page(n, fetcher)
            if title and day >= SINCE:
                added += _store(conn, card(n, day, title, description))
            elif title and day:
                conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (seen, day))
        if e.get("url"):
            store.mark_incident(conn, e["url"], e.get("title") or "", MARK + n)
    conn.commit()
    return added


def sync(conn, fetcher=feeds.fetch, log=print) -> int:
    return sync_snapshot(conn, fetcher, log) + sync_feed(conn, fetcher, log)
