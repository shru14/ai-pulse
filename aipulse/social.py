"""What people are discussing: the most-discussed AI threads on Hacker News, for the front page.

Read through Hacker News' official API (hacker-news.firebaseio.com, whose robots.txt allows its .json files; terms in
terms.PLATFORM). Only each thread's title, links, points and comment count are kept: no comments are copied. Fetched
once per full run (not the labs' quick runs) and kept in the database, so the build itself calls nothing.
AI launches (Show HN, Launch HN) among those stories are also kept for two weeks, for Company of the day's candidates.
Reddit was considered and left out: its robots.txt refuses every reader, its API included (10 Oct 2026).
"""

from __future__ import annotations

import logging
import json
import time
from concurrent.futures import ThreadPoolExecutor

from . import classify, feeds

logger = logging.getLogger(__name__)

API = "https://hacker-news.firebaseio.com/v0/"
SCAN = 200       # how many of HN's top stories to look at
KEEP = 30        # threads kept: five on the front page, all on /discussing/
MAX_AGE_H = 48   # only threads from the last two days
KEY = "social-hn"
LAUNCH_DAYS = 14  # launches kept, for Company of the day's candidates (companies.py)
_LAUNCH = ("Show HN:", "Launch HN:")


def hacker_news(conn, fetcher=feeds.fetch, now: float | None = None) -> int:
    """Read HN's top stories, keep the AI ones from the last two days, most points first. Returns how many."""
    now = now or time.time()
    ids = json.loads(fetcher(API + "topstories.json"))[:SCAN]

    def item(i):
        try:
            return json.loads(fetcher(f"{API}item/{i}.json"))
        except Exception as exc:
            logger.debug("Hacker News item %s not read: %s", i, exc)
            return None

    with ThreadPoolExecutor(8) as ex:
        items = [x for x in ex.map(item, ids) if x]
    threads = [{"title": x["title"], "url": x.get("url") or f"https://news.ycombinator.com/item?id={x['id']}",
                "hn": f"https://news.ycombinator.com/item?id={x['id']}", "points": x.get("score", 0),
                "comments": x.get("descendants", 0), "time": x["time"]}
               for x in items
               if x.get("type") == "story" and not x.get("dead") and not x.get("deleted") and x.get("title")
               and now - x.get("time", 0) < MAX_AGE_H * 3600 and classify.is_ai_related(x["title"], "")]
    threads.sort(key=lambda t: (t["comments"] + t["points"]), reverse=True)
    # AI startups launching on HN (Show HN, Launch HN) among the same stories, kept LAUNCH_DAYS with their best points
    before = {t["hn"]: t for t in payload(conn).get("launches", []) if now - t["time"] < LAUNCH_DAYS * 86400}
    for t in threads:
        if t["title"].startswith(_LAUNCH) and t["points"] >= before.get(t["hn"], {}).get("points", -1):
            before[t["hn"]] = t
    launches = sorted(before.values(), key=lambda t: t["time"], reverse=True)
    value = json.dumps({"fetched": int(now), "threads": threads[:KEEP], "launches": launches})
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (KEY, value))
    conn.commit()
    return len(threads[:KEEP])


def payload(conn) -> dict:
    """The last fetch, as the front page reads it (social.json); empty before the first one."""
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (KEY,)).fetchone()
    return json.loads(row[0]) if row else {"fetched": None, "threads": []}
