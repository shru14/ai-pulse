"""One-time history: fill every stream back to a start date (default 1 January 2023).

Daily collection only sees what feeds hold today, so this goes back with sources that can search by date:

- Every feed's own archive ("feeds"): what the feed lists today (OpenAI's and Hugging Face's list years of
  posts), then page after page for feeds that page back in time (WordPress's ?paged=N: TechCrunch,
  The Decoder, SiliconANGLE, Ars Technica, ...) until the start date.
- Government records ("official"): the Federal Register and GOV.UK search APIs, one month at a time.
- Research and expert papers: arXiv's search API for every listed professor and scholar (exact author match, as daily),
  and Hugging Face Daily Papers day by day for big tech and frontier lab papers.

Only sources whose robots.txt and terms allow it are read (see sources.py). Old stories go through the
same sorting, tagging and dedupe as new ones. Finished searches and pages are remembered in the database (meta
table), so an interrupted run picks up where it stopped. Run it on a PC: arXiv refuses cloud servers.

    python -m aipulse backfill                  # everything since 2023-01-01
    python -m aipulse backfill --only feeds     # feeds, official, research or papers
"""

from __future__ import annotations

import time
import urllib.error
from datetime import date, timedelta
from urllib.parse import quote

from . import brands, cluster, feeds, store
from .collect import collect
from .sources import EXPERTS, PROFESSORS, SOURCES

MAX_PAGES = 2000  # a feed with 10 posts a page and 10 posts a day reaches back about 5 years
PAGE_TRIES = 3  # a page that fails (dropped connection, a timeout, a garbled reply) is tried again
GIVE_UP_AFTER = 5  # pages in a row that fail every try: the host is down; the next run carries on


def months(since: date, until: date):
    """(first day, first day of next month) for every month from `since` to `until`."""
    d = since.replace(day=1)
    while d <= until:
        nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield max(d, since), nxt
        d = nxt


def official_sources(since: date, until: date) -> list[dict]:
    """The Federal Register and GOV.UK sources, one month at a time."""
    out = []
    for s in SOURCES:
        for start, end in months(since, until):
            last = end - timedelta(days=1)
            if s.get("format") == "federal_register":
                span = (f"&conditions%5Bpublication_date%5D%5Bgte%5D={start}"
                        f"&conditions%5Bpublication_date%5D%5Blte%5D={last}")
                url = s["url"].replace("per_page=50", "per_page=1000") + span
            elif s.get("format") == "govuk":
                url = s["url"].replace("count=50", "count=1000") + f"&filter_public_timestamp=from:{start},to:{last}"
            else:
                continue
            out.append({**s, "label": f"{s['name']} {start:%Y-%m}", "url": url, "pause": 1.0})
    return out


def page_url(url: str, n: int) -> str:
    return url if n == 1 else url + ("&" if "?" in url else "?") + f"paged={n}"


def feed_archives(conn, since: date, fetcher=feeds.fetch, log=print) -> int:
    """Each RSS/Atom source's own archive back to `since`: its feed as it stands, then (sources marked
    "paged") one page after another until a page reaches `since`, repeats the last one, or doesn't exist
    (404). A page that keeps failing is skipped; if several in a row do, the source is left unfinished.
    The last page read is remembered, so a stopped or unfinished run carries on from there."""
    age = (date.today() - since).days + 2
    added = 0
    for src in [s for s in SOURCES if s.get("format", "feed") == "feed"]:
        key = f"backfill-feed:{src['url']}"
        row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row and row[0] == "done":
            continue
        start, n_src, seen, failed, finished = (int(row[0]) + 1 if row else 1), 0, set(), 0, True
        for n in range(start, (MAX_PAGES if src.get("paged") else 1) + 1):
            body, entries, error = None, [], None
            for attempt in range(PAGE_TRIES):
                try:
                    body = fetcher(page_url(src["url"], n))
                    entries = feeds.parse(body)
                    error = None
                    break
                except urllib.error.HTTPError as e:
                    error = e
                    if e.code in (404, 410):  # past the last page
                        break
                except Exception as e:
                    error = e
                time.sleep(10 * (attempt + 1))
            if isinstance(error, urllib.error.HTTPError) and error.code in (404, 410):
                break
            if error:
                failed += 1
                log(f"  {src['name']}: skipped page {n} ({type(error).__name__})")
                if failed >= GIVE_UP_AFTER:
                    finished = False
                    break
                continue
            failed = 0
            urls = {e["url"] for e in entries}
            if not entries or urls <= seen:
                break
            seen |= urls
            n_src += collect(conn, [{**src, "label": f"{src['name']} page {n}", "pause": 1.0}], max_age_days=age,
                             fetcher=lambda u, b=body: b, log=lambda m: None, backfill=True)
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, str(n)))
            conn.commit()
            oldest = min((e["published"] for e in entries if e["published"]), default=None)
            if oldest and oldest.date() < since:
                break
            if n % 50 == 0:
                log(f"  {src['name']}: page {n}, back to {oldest.date() if oldest else '?'}, {n_src} stories so far")
        if finished:
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, 'done')", (key,))
            conn.commit()
        log(f"  {src['name']}: {n_src} stories" + ("" if finished else " (unfinished: its host kept failing)"))
        added += n_src
    return added

def arxiv_sources(since: date, until: date) -> list[dict]:
    """arXiv search per person; only papers where they're really an author are kept (as daily)."""
    span = f"{since:%Y%m%d}0000+TO+{until:%Y%m%d}2359"
    people = [(n, "research", True) for n, _ in PROFESSORS] + [(n, "regulation", False) for n, _, _ in EXPERTS]
    return [{"name": "arXiv", "label": f"arXiv: {name}", "category": category, "professors": [name], "ai_only": ai_only,
             "expert": category == "regulation" or None, "pause": 3.5,  # arXiv asks for 3 s between calls
             "expect_entries": True,  # arXiv sometimes answers with an empty list; retry those
             "url": f"http://export.arxiv.org/api/query?search_query=au:{quote(chr(34) + name + chr(34))}"
                    f"+AND+submittedDate:[{span}]&sortBy=submittedDate&sortOrder=descending&max_results=1000"}
            for name, category, ai_only in people]


def paper_sources(since: date, until: date) -> list[dict]:
    """Hugging Face Daily Papers, one day at a time (its history starts in May 2023)."""
    out, d = [], max(since, date(2023, 5, 1))
    while d <= until:
        out.append({"name": "Hugging Face Daily Papers", "label": f"Hugging Face Daily Papers {d}", "format": "hf_daily", "category": "research",
                    "ai_only": True, "companies": True, "pause": 0.3,
                    "url": f"https://huggingface.co/api/daily_papers?date={d}&limit=100"})
        d += timedelta(days=1)
    return out


GROUPS = {"feeds": feed_archives, "official": official_sources, "research": arxiv_sources, "papers": paper_sources}


def run(conn, since: date = date(2023, 1, 1), only: list[str] | None = None, fetcher=feeds.fetch, log=print) -> int:
    """Run every search not already done; returns how many stories were added."""
    until = date.today()
    age = (until - since).days + 2
    done = {r[0] for r in conn.execute("SELECT key FROM meta WHERE key LIKE 'backfill:%'")}
    added = 0
    for group in only or list(GROUPS):
        if group == "feeds":
            log("feeds: every source's own archive")
            added += feed_archives(conn, since, fetcher, log)
            continue
        todo = [s for s in GROUPS[group](since, until) if f"backfill:{s['label']}" not in done]
        log(f"{group}: {len(todo)} searches to run")
        for i, src in enumerate(todo, 1):
            n = collect(conn, [src], max_age_days=age, fetcher=fetcher, log=lambda m: None, backfill=True)
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                         (f"backfill:{src['label']}", str(n)))
            conn.commit()
            added += n
            if i % 25 == 0 or i == len(todo):
                log(f"  {group}: {i}/{len(todo)} searches, {added} stories added so far")
    log("Regrouping every story into cards ...")
    cluster.assign(conn, days=None)
    log("Looking up brand logos ...")
    brands.add_logos(conn, store.cards(conn, limit=10**9)[0], lookups=300)
    return added
