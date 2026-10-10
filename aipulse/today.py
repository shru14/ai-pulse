"""Today in AI's leaderboard: the last two days' stories (yesterday and today, UTC), ranked by how many outlets
carry them, as the front page shows them (the story of the week, on the cover, left out). Stories carried by as
many outlets go by their buzz: how many of the last 30 days' stories named the same thing (Jev, Qwen), so a story
people keep writing about comes before a one-off.

Each run (`board` command, before the database is saved) keeps two things for the day: each story's rank at the
day's first run (the board's arrows say how far it has moved since) and its best rank so far (a story that was in
the top 3 stays on the board all day, as "was #N today"). The build only reads them (today.json).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone

CATS = ("tool", "news", "research", "regulation", "policy", "infra")  # the front page's streams
KEEP = 30  # ranks kept for the arrows; a story further down counts as new when it climbs into view
TOP = 3    # a story that reached this rank today stays on the board all day
BUZZ_DAYS = 30  # buzz counts this many days' stories
BIG = 30   # a name in more of them (OpenAI, Anthropic) is always in the news: it says nothing about one story
WORD = re.compile(r"[A-Za-z][\w.+-]*\w")


def _outlets(c: dict) -> int:
    return len(c.get("also") or []) + 1


def _ranked(cards: list[dict]) -> list[dict]:
    """Most outlets first, then the newest day; otherwise the cards' own order (as the page's byWeight)."""
    newest = sorted(cards, key=lambda c: c.get("date") or "", reverse=True)  # Python's sorts keep ties in order
    return sorted(newest, key=lambda c: -_outlets(c))


def buzz(cards: list[dict], today: date) -> dict[str, int]:
    """Each story's buzz: of the names in its headline, the one the most of the last 30 days' stories carry (leaving
    out the big ones), and in how many. A name is a capitalised word never written in lower case in those headlines
    ("Model" and "Data" are words; "Jev" is a name)."""
    month = [c for c in cards if (c.get("date") or "") >= (today - timedelta(days=BUZZ_DAYS - 1)).isoformat()]
    words = {c["id"]: WORD.findall(c.get("title") or "") for c in month}
    lower = {w for ws in words.values() for w in ws if w[0].islower()}
    names = {i: {w for w in ws if w[0].isupper() and len(w) > 2 and w.lower() not in lower} for i, ws in words.items()}
    seen = Counter(n for ns in names.values() for n in ns)
    return {i: max((seen[n] for n in ns if seen[n] <= BIG), default=0) for i, ns in names.items()}


def ranking(cards: list[dict], today: date) -> list[str]:
    """Today's board as story ids, best first: yesterday's and today's stories, without the story of the week (the
    past 7 days' most reported, on the front page's cover)."""
    cards = [c for c in cards if c.get("category") in CATS]
    week = _ranked([c for c in cards if (c.get("date") or "") >= (today - timedelta(days=6)).isoformat()])
    cover = week[0]["id"] if week else None
    since = (today - timedelta(days=1)).isoformat()
    loud = buzz(cards, today)
    newest = sorted([c for c in cards if (c.get("date") or "") >= since and c["id"] != cover],
                    key=lambda c: c.get("date") or "", reverse=True)
    return [c["id"] for c in sorted(newest, key=lambda c: (-_outlets(c), -loud.get(c["id"], 0)))]


def _key(today: date) -> str:
    return f"board:{today.isoformat()}"


def record(conn, cards: list[dict], today: date | None = None) -> dict:
    """Keep the day's starting ranks (first run of the day) and each story's best rank so far."""
    today = today or datetime.now(timezone.utc).date()
    now = {i: r for r, i in enumerate(ranking(cards, today)[:KEEP], 1)}
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (_key(today),)).fetchone()
    day = json.loads(row[0]) if row else {"start": now, "peak": {}}
    for i, r in now.items():
        if r <= TOP and r < day["peak"].get(i, TOP + 1):
            day["peak"][i] = r
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (_key(today), json.dumps(day)))
    conn.execute("DELETE FROM meta WHERE key LIKE 'board:%' AND key < ?", (_key(today - timedelta(days=7)),))
    conn.commit()
    return day


def payload(conn, cards: list[dict], today: date | None = None) -> dict:
    """today.json: the board (ids, best first), the day's starting ranks and the stories that were in the top 3."""
    today = today or datetime.now(timezone.utc).date()
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (_key(today),)).fetchone()
    day = json.loads(row[0]) if row else {"start": {}, "peak": {}}
    ids = ranking(cards, today)
    shown = set(ids)
    return {"date": today.isoformat(), "ids": ids,
            "start": {i: r for i, r in day["start"].items() if i in shown},
            "peak": {i: r for i, r in day["peak"].items() if i in shown}}
