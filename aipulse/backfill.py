"""One-time history: fill every stream back to a start date (default 1 January 2023).

Daily collection only sees what feeds hold today, so this goes back with sources that can search by date:

- News, policy and regulation: the site's own Google News searches, one calendar month at a time
  ("when:3d" becomes "after:2023-01-01 before:2023-02-01"), plus site searches standing in for the
  publisher and lab feeds (TechCrunch, The Verge, OpenAI, ...) and a search for model launches.
  Google News returns up to 100 stories per search, so each month is capped at that per search.
- Expert views: each scholar's Google News search, one year at a time.
- Research: arXiv's search API for every listed professor and scholar (exact author match, as daily),
  and Hugging Face Daily Papers day by day for big tech and frontier lab papers.

Old stories go through the same sorting, tagging and dedupe as new ones; headline-only ones get a short
draft summary instead of a Bing lookup each. Finished searches are remembered in the database (meta
table), so an interrupted run picks up where it stopped. Run it on a PC: arXiv refuses cloud servers.

    python -m aipulse backfill                  # everything since 2023-01-01
    python -m aipulse backfill --only research  # news, experts, research or papers
"""

from __future__ import annotations

import re
import time
from datetime import date, timedelta
from urllib.parse import quote, quote_plus

from . import brands, cluster, feeds, store
from .collect import collect
from .sources import EXPERTS, PROFESSORS, SOURCES

_GN = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q="
_WHEN = re.compile(r"\+when:\d+[dh]")

# Stand-ins for daily feeds that only hold recent posts: the same publishers and labs via Google News.
FEED_SEARCHES = [
    ("OpenAI", "tool", "site:openai.com"),
    ("Google AI Blog", "tool", "site:blog.google AI"),
    ("Hugging Face Blog", "tool", "site:huggingface.co/blog"),
    ("Model launches", "tool",
     "(OpenAI OR Anthropic OR Gemini OR DeepMind OR Llama OR Mistral OR DeepSeek OR Qwen OR Grok) "
     "(launches OR releases OR unveils OR introduces) model"),
    ("TechCrunch AI", "news", "site:techcrunch.com AI"),
    ("The Verge AI", "news", "site:theverge.com AI"),
    ("Ars Technica AI", "news", "site:arstechnica.com AI"),
    ("MIT Technology Review AI", "news", "site:technologyreview.com AI"),
    ("The Decoder", "news", "site:the-decoder.com"),
]


def months(since: date, until: date):
    """(first day, first day of next month) for every month from `since` to `until`."""
    d = since.replace(day=1)
    while d <= until:
        nxt = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        yield max(d, since), nxt
        d = nxt


def news_sources(since: date, until: date) -> list[dict]:
    """Monthly Google News searches: the site's own (minus the per-person ones) and the feed stand-ins."""
    out = []
    for start, end in months(since, until):
        span = f"+after:{start}+before:{end}"
        for s in SOURCES:
            if "news.google.com/rss/search" in s["url"] and not s.get("expert") and _WHEN.search(s["url"]):
                out.append({**s, "name": f"{s['name']} {start:%Y-%m}", "url": _WHEN.sub(span, s["url"]),
                            "max_items": None, "max_age_days": 0, "pause": 1.2})
        for name, category, q in FEED_SEARCHES:
            # Google's blog covers far more than AI, so its posts must pass the AI check; the lab and
            # publisher searches are AI by construction, as their daily feeds are.
            out.append({"name": f"{name} {start:%Y-%m}", "category": category, "pause": 1.2,
                        "ai_only": name != "Google AI Blog", "url": _GN + quote_plus(q) + span})
    return out


def expert_sources(since: date, until: date) -> list[dict]:
    """Each scholar's Google News search, a year at a time (up to 10 stories a year)."""
    out = []
    for year in range(since.year, until.year + 1):
        start, end = max(since, date(year, 1, 1)), date(year + 1, 1, 1)
        for name, _, _ in EXPERTS:
            out.append({"name": f"Google News: {name} {year}", "category": "regulation", "expert": name,
                        "url": _GN + quote_plus(f'"{name}"') + f"+AI+after:{start}+before:{end}",
                        "max_items": 10, "pause": 1.2})
    return out


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


# Site searches also find a site's forums, docs, help pages and status incidents; the daily feeds don't.
# "OpenAI Help Center", "OpenAI Developer Community", "academy.openai.com" - but not "World Economic Forum".
_NOT_NEWS_SOURCE = re.compile(r"^\S+ (Developer Community|Community|Help Center|Platform|Academy|Forum|"
                              r"Status|Docs)$|^(academy|cdn|help|status|community|platform|developers?|docs|forum)\.",
                              re.I)
_STATUS = re.compile(r"^(Elevated|Increased|Degraded|Partial|Major|Intermittent)\b.*\b(errors?|latency|outage|"
                     r"performance|availability)\b|^(Outage|Incident)\b", re.I)
# Google News answers site searches in other languages too; the feed is English.
_FOREIGN = re.compile(r"\b(de|het|een|der|die|das|und|les|des|pour|avec|el|los|las|para|con|della|di|il|per|"
                      r"em|com|uma|dos|och|och|med|ile|ve|bir|nieuw|neue|nuevo|nueva|nouveau|nouvelle)\b", re.I)
_ENGLISH = re.compile(r"\b(the|a|an|and|of|to|in|for|on|with|is|are|how|what|why|new|now|your|our|we|you|it)\b", re.I)


def is_noise(title: str, source: str) -> str | None:
    """Why a backfilled story isn't news for this feed, or None."""
    if _NOT_NEWS_SOURCE.search(source or ""):
        return "forum, docs or help page"
    if _STATUS.search(title):
        return "status incident"
    letters = [c for c in title if c.isalpha()]
    if letters and sum(c.isascii() for c in letters) / len(letters) < 0.8:
        return "not in English"
    if len(_FOREIGN.findall(title)) >= 2 and not _ENGLISH.search(title):
        return "not in English"
    return None


GROUPS = {"news": news_sources, "experts": expert_sources, "research": arxiv_sources, "papers": paper_sources}


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
