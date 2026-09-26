"""One-time history: fill every stream back to a start date (default 1 January 2023).

Daily collection only sees what feeds hold today, so this goes back with sources that can search by date:

- Research and expert papers: arXiv's search API for every listed professor and scholar (exact author match, as daily),
  and Hugging Face Daily Papers day by day for big tech and frontier lab papers.

Old stories go through the same sorting, tagging and dedupe as new ones. (News history came from Google
News searches until those were removed: Google doesn't allow automated access.) Finished searches are remembered in the database (meta
table), so an interrupted run picks up where it stopped. Run it on a PC: arXiv refuses cloud servers.

    python -m aipulse backfill                  # everything since 2023-01-01
    python -m aipulse backfill --only research  # research or papers
"""

from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import quote

from . import brands, cluster, feeds, store
from .collect import collect
from .sources import EXPERTS, PROFESSORS

def arxiv_sources(since: date, until: date) -> list[dict]:
    """arXiv search per person; only papers where they're really an author are kept (as daily)."""
    span = f"{since:%Y%m%d}0000+TO+{until:%Y%m%d}2359"
    people = [(n, "research", True) for n, _ in PROFESSORS] + [(n, "regulation", False) for n, _, _ in EXPERTS]
    return [{"name": f"arXiv: {name}", "category": category, "professors": [name], "ai_only": ai_only,
             "expert": category == "regulation" or None, "pause": 3.5,  # arXiv asks for 3 s between calls
             "expect_entries": True,  # arXiv sometimes answers with an empty list; retry those
             "url": f"http://export.arxiv.org/api/query?search_query=au:{quote(chr(34) + name + chr(34))}"
                    f"+AND+submittedDate:[{span}]&sortBy=submittedDate&sortOrder=descending&max_results=1000"}
            for name, category, ai_only in people]


def paper_sources(since: date, until: date) -> list[dict]:
    """Hugging Face Daily Papers, one day at a time (its history starts in May 2023)."""
    out, d = [], max(since, date(2023, 5, 1))
    while d <= until:
        out.append({"name": f"Hugging Face Daily Papers {d}", "format": "hf_daily", "category": "research",
                    "ai_only": True, "companies": True, "pause": 0.3,
                    "url": f"https://huggingface.co/api/daily_papers?date={d}&limit=100"})
        d += timedelta(days=1)
    return out


GROUPS = {"research": arxiv_sources, "papers": paper_sources}


def run(conn, since: date = date(2023, 1, 1), only: list[str] | None = None, fetcher=feeds.fetch, log=print) -> int:
    """Run every search not already done; returns how many stories were added."""
    until = date.today()
    age = (until - since).days + 2
    done = {r[0] for r in conn.execute("SELECT key FROM meta WHERE key LIKE 'backfill:%'")}
    added = 0
    for group in only or list(GROUPS):
        todo = [s for s in GROUPS[group](since, until) if f"backfill:{s['name']}" not in done]
        log(f"{group}: {len(todo)} searches to run")
        for i, src in enumerate(todo, 1):
            n = collect(conn, [src], max_age_days=age, fetcher=fetcher, log=lambda m: None, backfill=True)
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                         (f"backfill:{src['name']}", str(n)))
            conn.commit()
            added += n
            if i % 25 == 0 or i == len(todo):
                log(f"  {group}: {i}/{len(todo)} searches, {added} stories added so far")
    log("Regrouping every story into cards ...")
    cluster.assign(conn, days=None)
    log("Looking up brand logos ...")
    brands.add_logos(conn, store.cards(conn, limit=10**9)[0], lookups=300)
    return added
