"""Canada: regulations in the Canada Gazette."""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime

from .. import feeds

from .core import AI_TITLE, connect_tables, upsert


# --- Canada Gazette (the Government of Canada's official publication of regulations) ---
# Canada's AI rules are followed here (the Parliament of Canada's LEGISinfo was dropped on 6 Oct 2026: parl.ca turns
# automated readers away): proposed regulations (Part I, weekly) and registered ones (Part II,
# every other week). gazette.gc.ca has no robots.txt rules, and canada.ca's terms allow non-commercial reproduction
# with the title and a link to the original (https://www.canada.ca/en/transparency/terms.html).

CA_GAZETTE = "https://gazette.gc.ca/rss/p{part}-eng.xml"


CA_GAZETTE_ISSUES = 12  # the latest issues of each part: about three months of Part I, six of Part II


_CA_ISSUE = re.compile(r"<item>.*?<title>Canada Gazette - Part (I+), ([^<]+?), volume[^<]*</title>.*?<link>([^<]+)</link>", re.S)


_CA_REG = re.compile(r'<a[^>]+href="((?!https?:|/|#|\.\./)[^"]+-eng\.html)"[^>]*>(.*?)</a>', re.S)


_CA_LISTS = ("index-eng.html", "commis-eng.html", "notice-avis-eng.html", "misc-divers-eng.html",
             "parliament-parlement-eng.html")


def _ca_text(body: bytes) -> str:
    """A Gazette page: UTF-8, or Windows-1252 for the pages that are still in it (their dashes and quotes)."""
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("cp1252", "replace")


def sync_canada_gazette(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI regulations in the Canada Gazette: proposed (Part I) and registered (Part II), as title, date and link."""
    from urllib.parse import urljoin
    connect_tables(conn)
    found: dict[str, dict] = {}  # one record a regulation: proposed and registered under the same title
    for part in (1, 2):
        feed = _ca_text(fetcher(CA_GAZETTE.format(part=part)))
        for numeral, when, issue in _CA_ISSUE.findall(feed)[:CA_GAZETTE_ISSUES]:
            try:
                day = datetime.strptime(when.strip(), "%B %d, %Y").date().isoformat()
            except ValueError:
                continue
            page = _ca_text(fetcher(issue))
            for href, raw in _CA_REG.findall(page):
                title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", raw))).strip()
                if href.split("/")[-1] in _CA_LISTS or not AI_TITLE.search(title):
                    continue
                key = "CA-GAZ-" + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]
                rec = found.setdefault(key, {"title": title, "url": urljoin(issue, href), "history": []})
                rec["history"].append({"date": day, "stage": "introduced" if part == 1 else "signed",
                                       "text": "Proposed (Canada Gazette, Part I)" if part == 1
                                       else "Registered (Canada Gazette, Part II)"})
            time.sleep(1)
    changed = 0
    for key, rec in found.items():
        # the record keeps its first link (its card is found by it), and gains each later stage
        kept = conn.execute("SELECT history, url FROM bills WHERE key = ?", (key,)).fetchone()
        steps = {(h["date"], h["stage"]): h for h in [*(json.loads(kept[0]) if kept else []), *rec["history"]]}
        bill = {"key": key, "jurisdiction": "CA", "number": "", "title": rec["title"], "url": kept[1] if kept else rec["url"],
                "source": "Canada Gazette", "history": sorted(steps.values(), key=lambda h: h["date"])}
        changed += upsert(conn, bill)
    conn.commit()
    return changed
