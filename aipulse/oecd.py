"""AI rules from many countries at once: the OECD.AI Policy Observatory's database of policy initiatives.

The OECD publishes its content under CC BY 4.0 (its default licence; credited on the page). The public
dashboard reads https://api.oecdai.org/policy-initiatives (no key, no robots.txt); it's read about once a
week, a page a second. Only policy fields are kept: the records also carry the names and email addresses
of the OECD editors, which are never stored.

What's taken:
- regulations, guidelines and standards set by a country, and the frameworks of international bodies
  (Council of Europe convention, UNESCO, G7, African Union, ASEAN, UN, ...), when they're about AI;
- EU member states' own records are left out: the EU counts as one. EU-level binding acts are already
  tracked from the European Parliament, so only its non-binding ones come from here;
- for countries tracked from their own official records (bills.py) only non-binding items (guidance),
  so no law appears twice;
- AI governance bodies (safety institutes, regulators, advisory and coordination offices) for every
  country, as "AI body" cards tagged with their kind.
Binding items go to the regulation tracker as adopted rules, the rest to Policy. A record has a start year
only: its card is dated 1 January of that year and the page shows just the year.
"""

from __future__ import annotations

import json
import time
from datetime import date, timedelta

from . import classify, feeds, jurisdictions, store

API = "https://api.oecdai.org/policy-initiatives"
SITE = "https://oecd.ai/en/dashboards/policy-initiatives/"
SOURCE = "OECD.AI"
REFRESH_DAYS = 7
SYNC_KEY = "oecd_sync_v2"  # a new key makes the next run read everything again after the rules change
MARK = "OECD-"  # items.bill for these cards: each record stands alone (see cluster.py) and isn't re-sorted

# Countries with official records of their own in bills.py.
OWN_RECORDS = {"US", "GB", "CA", "BR", "AU", "CN", "IN", "JP", "VN"}
BINDING_TYPES = {"Law/legislation/act (by legislative body)", "Regulation (by government authority)",
                 "Amendment to/repeal of existing legislation", "Regulation", "Directive", "Treaty"}
# From international bodies, the frameworks themselves, not their projects, programmes or offices.
# (Their "other frameworks and initiatives" are the bodies' own offices, networks and tools.)
BODY_TYPES = {"Declaration, opinion, or outcome document", "Guidance/guidelines", "Policy", "Regulation",
              "Recommendation", "Directive", "Treaty"}
COUNTRY_CATEGORY = "Regulations, guidelines and standards"
# AI governance bodies (regulators, safety institutes, advisory and coordination offices), shown with their kind.
BODY_CATEGORIES = {"National – AI governance bodies or mechanisms",
                   "AI Governance Bodies and Mechanisms (intergovernmental or supranational)"}
BODY_KINDS = {"Oversight": "Oversight body", "Monitoring": "Monitoring body", "Advisory": "Advisory body",
              "Coordination": "Coordination body", "Other national AI governance": "AI body"}

ISO3 = {"ARE": "AE", "ARG": "AR", "ARM": "AM", "AUS": "AU", "AUT": "AT", "BEL": "BE", "BEN": "BJ", "BGR": "BG",
        "BRA": "BR", "BRN": "BN", "CAN": "CA", "CHE": "CH", "CHL": "CL", "CHN": "CN", "CIV": "CI", "CMR": "CM",
        "COL": "CO", "CRI": "CR", "CUB": "CU", "CYP": "CY", "CZE": "CZ", "DEU": "DE", "DNK": "DK", "DOM": "DO",
        "DZA": "DZ", "ECU": "EC", "EGY": "EG", "ESP": "ES", "EST": "EE", "ETH": "ET", "FIN": "FI", "FRA": "FR",
        "GBR": "GB", "GHA": "GH", "GRC": "GR", "HRV": "HR", "HUN": "HU", "IDN": "ID", "IND": "IN", "IRL": "IE",
        "ISL": "IS", "ISR": "IL", "ITA": "IT", "JPN": "JP", "KAZ": "KZ", "KEN": "KE", "KHM": "KH", "KOR": "KR",
        "LBY": "LY", "LSO": "LS", "LTU": "LT", "LUX": "LU", "LVA": "LV", "MAR": "MA", "MEX": "MX", "MLT": "MT",
        "MRT": "MR", "MUS": "MU", "MYS": "MY", "NGA": "NG", "NLD": "NL", "NOR": "NO", "NZL": "NZ", "PAK": "PK",
        "PER": "PE", "PHL": "PH", "POL": "PL", "PRT": "PT", "ROU": "RO", "RWA": "RW", "SAU": "SA", "SEN": "SN",
        "SGP": "SG", "SRB": "RS", "SVK": "SK", "SVN": "SI", "SWE": "SE", "THA": "TH", "TUN": "TN", "TUR": "TR",
        "UGA": "UG", "UKR": "UA", "URY": "UY", "USA": "US", "UZB": "UZ", "VAT": "VA", "VNM": "VN", "ZAF": "ZA",
        "ZMB": "ZM", "ZWE": "ZW"}


def card(r: dict) -> dict | None:
    """The card for one OECD record under the rules above, or None if it isn't taken."""
    kind = (r.get("initiativeType") or {}).get("name") or ""
    binding = r.get("extentBinding") == "Binding" or kind in BINDING_TYPES
    country, body = r.get("gaiinCountry") or {}, r.get("intergovernmentalOrganisation") or {}
    if r.get("category") in BODY_CATEGORIES:
        return _body_card(r, kind, country, body)
    if country:
        code = ISO3.get(country.get("code") or "")
        if (r.get("category") != COUNTRY_CATEGORY or not code or code in jurisdictions.EU_MEMBERS
                or code not in jurisdictions.JURISDICTIONS or (binding and code in OWN_RECORDS)):
            return None
    elif body:
        if kind not in BODY_TYPES:
            return None
        code = "EU" if body.get("name") == "European Union" else "INTL"
        if code == "EU" and binding:
            return None
    else:
        return None
    year = r.get("startYear")
    if not (year and r.get("englishName") and r.get("slug")):
        return None
    from .bills import describe
    title = r["englishName"].strip()
    summary = describe(r.get("description") or "", title)
    if not classify.is_ai_related(title, summary):  # general data, privacy or open-data rules
        return None
    return {"title": title[:220], "summary": summary, "url": SITE + r["slug"], "source": SOURCE,
            "category": "regulation" if binding else "policy", "action": "law" if binding else None,
            "date": f"{int(year):04d}-01-01", "jurisdictions": [code], "authors": [],
            "tags": classify.tags_for(title, summary), "_id": r["id"]}


def _body_card(r: dict, kind: str, country: dict, body: dict) -> dict | None:
    """An AI governance body (e.g. an AI safety institute) as a tracker card with its kind as a tag. Bodies are
    taken for every country, including those with official records (a body isn't a law, so nothing repeats)."""
    label = next((v for k, v in BODY_KINDS.items() if kind.startswith(k)), None)
    code = ISO3.get(country.get("code") or "") if country else ("EU" if body.get("name") == "European Union" else "INTL")
    if not label or not code or code in jurisdictions.EU_MEMBERS or (country and code not in jurisdictions.JURISDICTIONS):
        return None
    if not (r.get("startYear") and r.get("englishName") and r.get("slug")):
        return None
    from .bills import describe
    title = r["englishName"].strip()
    summary = describe(r.get("description") or "", title)
    if not classify.is_ai_related(title, summary):
        return None
    return {"title": title[:220], "summary": summary, "url": SITE + r["slug"], "source": SOURCE,
            "category": "regulation", "action": "body", "date": f"{int(r['startYear']):04d}-01-01",
            "jurisdictions": [code], "authors": [], "tags": [label, *classify.tags_for(title, summary)][:4],
            "_id": r["id"]}


def sync(conn, fetcher=feeds.fetch, log=print, force: bool = False) -> int:
    """Read the whole database about once a week and store its cards. Returns how many are new."""
    last = conn.execute("SELECT value FROM meta WHERE key = ?", (SYNC_KEY,)).fetchone()
    if last and not force and last[0] > (date.today() - timedelta(days=REFRESH_DAYS)).isoformat():
        return 0
    cards, page, pages = [], 1, 1
    while page <= pages:
        data = json.loads(fetcher(f"{API}?page={page}"))
        pages = data.get("lastPage") or 1
        cards += [c for c in map(card, data.get("data") or []) if c]
        page += 1
        time.sleep(1)
    added = 0
    for c in cards:
        mark = f"{MARK}{c.pop('_id')}"
        if store.exists(conn, c["url"]):
            conn.execute("UPDATE items SET title = ?, summary = ?, date = ?, category = ?, action = ?, jurisdictions = ?,"
                         " bill = ? WHERE id = ?", (c["title"], c["summary"], c["date"], c["category"], c["action"] or "",
                                                   ",".join(c["jurisdictions"]), mark, store.item_id(c["url"])))
        elif store.insert(conn, c):
            conn.execute("UPDATE items SET bill = ? WHERE id = ?", (mark, store.item_id(c["url"])))
            added += 1
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (SYNC_KEY, date.today().isoformat()))
    conn.commit()
    log(f"  OECD.AI: {len(cards)} records, {added} new")
    return added
