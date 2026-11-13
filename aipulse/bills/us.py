"""United States: bills in Congress, from the congress.gov API."""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timedelta, timezone

from .. import config, feeds

from .core import AI_TITLE, _US_TYPES, _get_json, connect_tables, describe, logger, upsert, us_history


# --- US Congress (congress.gov) ---

CONGRESS_API = "https://api.congress.gov/v3"


def _congress_key() -> str:
    return config.congress_key()


def _crs_summary(congress, kind: str, number, title: str, key: str, fetcher=feeds.fetch) -> str:
    """The Congressional Research Service's latest summary of a bill (a US government work), or "" (CRS
    writes one some weeks after a bill is introduced)."""
    try:
        data = _get_json(f"{CONGRESS_API}/bill/{congress}/{kind.lower()}/{number}/summaries?format=json",
                         fetcher)
    except Exception as exc:  # none yet, or congress.gov unreachable: asked again next run
        logger.debug("CRS summary of %s %s not read: %s", kind, number, exc)
        return ""
    found = sorted(data.get("summaries") or [], key=lambda s: s.get("updateDate") or "")
    return describe(found[-1].get("text", ""), title) if found else ""


def _us_describe_old(conn, key: str, fetcher=feeds.fetch, limit: int = 40) -> None:
    """Look up CRS summaries for stored US bills that don't have one yet, a few per run, each at most weekly."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    # Bills with no context yet (sponsor, committee) are read at once; the rest at most weekly.
    rows = conn.execute("SELECT * FROM bills WHERE jurisdiction = 'US' AND summary = '' AND (key NOT IN"
                        " (SELECT substr(key, 11) FROM meta WHERE key LIKE 'crs-tried:%' AND value > ?) OR key NOT IN"
                        " (SELECT substr(key, 12) FROM meta WHERE key LIKE 'us-context:%')) LIMIT ?",
                        (week_ago, limit)).fetchall()
    for r in rows:
        _, congress, kind, number = r["key"].split("-")
        text = _crs_summary(congress, kind, number, r["title"], key, fetcher)
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (f"crs-tried:{r['key']}", date.today().isoformat()))
        short = r["short_title"] if text else (_us_remember_context(conn, r["key"], congress, kind, number, key, fetcher)
                                               or r["short_title"])
        upsert(conn, {"key": r["key"], "jurisdiction": "US", "number": r["number"], "title": r["title"],
                      "short_title": short, "url": r["url"], "source": r["source"],
                      "history": json.loads(r["history"]), "summary": text})
        conn.commit()
        time.sleep(0.2)


_US_OTHER = re.compile(r",? and for other purposes\.?$|\.$")


_US_PURPOSE = re.compile(r"^(?:A (?:bill|joint resolution|concurrent resolution|resolution) )?to (.+?)(?:,? and for other purposes)?\.?$",
                         re.I)


def us_purpose(title: str) -> str:
    """What a bill would do, from its official title: "A bill to establish X, and for other purposes." ->
    "Would establish X." (Resolutions titled "Expressing ..." etc. give "".)"""
    m = _US_PURPOSE.match(title.strip())
    return f"Would {re.sub(r',? and to ', ' and ', m.group(1))}." if m else ""


def _us_context(congress, kind: str, number, key: str, fetcher=feeds.fetch) -> dict:
    """From congress.gov, for a bill CRS hasn't summarised yet: its sponsor, cosponsors, committees and short
    title (a short title appears once the text is published)."""
    base = f"{CONGRESS_API}/bill/{congress}/{kind.lower()}/{number}"
    bill = _get_json(f"{base}?format=json", fetcher).get("bill") or {}
    committees = _get_json(f"{base}/committees?format=json", fetcher).get("committees") or []
    titles = _get_json(f"{base}/titles?format=json", fetcher).get("titles") or []
    sponsor = (bill.get("sponsors") or [{}])[0]
    who = ""
    if sponsor.get("lastName"):
        role = "Sen." if kind.upper().startswith("S") else "Rep."
        who = f"{role} {sponsor.get('firstName', '')} {sponsor['lastName']} ({sponsor.get('party', '')}-{sponsor.get('state', '')})"
    short = next((t["title"] for t in titles if "Short Title" in (t.get("titleType") or "")), "")
    return {"sponsor": re.sub(r"\s+", " ", who).strip(), "cosponsors": (bill.get("cosponsors") or {}).get("count", 0),
            "committees": [f"{c['chamber']} {c['name']}" for c in committees if c.get("chamber") and c.get("name")],
            "short_title": short}


def us_interim(conn, bill: dict) -> str:
    """Until CRS publishes a summary: what the bill would do, who introduced it and where it was sent."""
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (f"us-context:{bill['key']}",)).fetchone()
    ctx = json.loads(row[0]) if row else {}
    parts = [us_purpose(bill["title"])]
    if ctx.get("sponsor"):
        with_co = f" with {ctx['cosponsors']} cosponsor{'s' if ctx['cosponsors'] != 1 else ''}" if ctx.get("cosponsors") else ""
        sent = f"; referred to the {' and the '.join(ctx['committees'])}" if ctx.get("committees") else ""
        parts.append(f"Introduced by {ctx['sponsor']}{with_co}{sent}.")
    return " ".join(p for p in parts if p)


def _us_remember_context(conn, bill_key: str, congress, kind, number, key, fetcher) -> str:
    """Store a bill's context for its interim summary; returns its short title, if it has one yet."""
    try:
        ctx = _us_context(congress, kind, number, key, fetcher)
    except Exception as exc:
        logger.debug("context of %s not read: %s", bill_key, exc)
        return ""
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (f"us-context:{bill_key}", json.dumps(ctx)))
    return ctx["short_title"]


def _current_congress(today: date) -> int:
    """The 119th Congress runs 2025-2026; a new one starts every odd year."""
    return (today.year - 1789) // 2 + 1


def sync_congress(conn, fetcher=feeds.fetch, since: datetime | None = None, max_pages: int = 40,
                  log=print) -> int:
    """Read the current Congress's bills updated since the last sync, oldest update first, and keep those with
    AI in the title; returns how many AI bills changed stage.

    The place reached is saved after every page, so a run that stops at `max_pages` (or on the rate limit)
    carries on from there next time. A newest-first read restarted from the top each run and never got past
    the latest few thousand updates. The list gives update dates without times and one day can update
    thousands of bills, so the place is a page offset, not a date; a resumed run re-reads one page in case
    bills moved while it was away."""
    connect_tables(conn)
    key = _congress_key()
    if not key:
        log("  congress.gov: skipped, no CONGRESS_API_KEY (the DEMO_KEY is only for trying the API)")
        return 0
    started = datetime.now(timezone.utc)
    congress = _current_congress(started.date())
    saved = conn.execute("SELECT value FROM meta WHERE key = 'congress_cursor'").fetchone()
    cursor = json.loads(saved[0]) if saved else {}
    if since:
        cursor = {"congress": congress, "from": since.strftime("%Y-%m-%dT%H:%M:%SZ"), "offset": 0}
    elif cursor.get("congress") != congress:  # first run, or a new Congress: read it from its first day
        cursor = {"congress": congress, "from": f"{2 * congress + 1787}-01-03T00:00:00Z", "offset": 0}
    offset = max(0, cursor["offset"] - 250)
    changed = pages = 0
    while pages < max_pages:
        data = _get_json(f"{CONGRESS_API}/bill/{congress}?format=json&limit=250&offset={offset}"
                         f"&sort=updateDate+asc&fromDateTime={cursor['from']}", fetcher)
        pages += 1
        listed = data.get("bills", [])
        for b in listed:
            if b.get("type") not in _US_TYPES or not AI_TITLE.search(b.get("title", "")):
                continue
            acts = _get_json(f"{CONGRESS_API}/bill/{b['congress']}/{b['type'].lower()}/{b['number']}/actions"
                             f"?format=json&limit=250", fetcher)
            label, path = _US_TYPES[b["type"]]
            bill = {"key": f"US-{b['congress']}-{b['type'].lower()}-{b['number']}", "jurisdiction": "US",
                    "number": f"{label} {b['number']}", "title": b["title"],
                    "url": f"https://www.congress.gov/bill/{b['congress']}th-congress/{path}/{b['number']}",
                    "source": "congress.gov", "history": us_history(acts.get("actions", [])),
                    "summary": _crs_summary(b["congress"], b["type"], b["number"], b["title"], key, fetcher)}
            if not bill["summary"]:
                bill["short_title"] = _us_remember_context(conn, bill["key"], b["congress"], b["type"], b["number"],
                                                           key, fetcher)
            changed += upsert(conn, bill)
            conn.commit()  # keep progress if a later request fails (e.g. the rate limit)
            time.sleep(0.2)
        offset += len(listed)
        done = len(listed) < 250 or not (data.get("pagination") or {}).get("next")
        # Done: next time, read what's updated from now on. Otherwise carry on from this page.
        cursor.update({"from": started.strftime("%Y-%m-%dT%H:%M:%SZ"), "offset": 0} if done else {"offset": offset})
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('congress_cursor', ?)", (json.dumps(cursor),))
        conn.commit()
        if done:
            break
    else:
        log(f"  congress.gov: {offset} bills read so far; the rest next run")
    _us_describe_old(conn, key, fetcher)
    conn.commit()
    return changed
