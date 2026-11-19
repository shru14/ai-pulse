"""What the daily email has already shown, so it never shows it again (owner, 2026-11-19).

Each published day's word of the day and meme of the day (on Sunday's email, the meme of the week) is kept once in
the database (meta "shown:word:<day>", "shown:meme-day:<day>", "shown:meme-week:<day>"): what daily/words/ and
daily/memes/ list. From START, a day picks only what hasn't been shown; when every choice has been, the one shown
longest ago. A kept day is never picked again, so its email, its web edition and the archives always agree.
"""
from __future__ import annotations

import json
from datetime import date

START = date(2026, 11, 19)  # days before were sent before the rule; they are kept as they were
WORDS: dict[date, str] = {}  # day -> the word of the day's glossary id
MEMES: dict[tuple[str, date], dict] = {}  # ("day" | "week", day) -> the meme


def load(conn) -> None:
    """Read what was shown from the database (the build and the email both do, before picking)."""
    WORDS.clear()
    MEMES.clear()
    for key, value in conn.execute("SELECT key, value FROM meta WHERE key LIKE 'shown:%'"):
        _, kind, day = key.split(":", 2)
        if kind == "word":
            WORDS[date.fromisoformat(day)] = value
        else:
            MEMES[(kind.removeprefix("meme-"), date.fromisoformat(day))] = json.loads(value)


def keep(conn, day: date, word: str | None = None, meme: dict | None = None, kind: str = "day") -> None:
    """Keep a day's word and meme, once: a day already kept is never changed."""
    rows = []
    if word and day not in WORDS:
        WORDS[day] = word
        rows.append((f"shown:word:{day.isoformat()}", word))
    if meme and (kind, day) not in MEMES:
        MEMES[(kind, day)] = meme
        rows.append((f"shown:meme-{kind}:{day.isoformat()}", json.dumps(meme)))
    if rows:
        conn.executemany("INSERT OR IGNORE INTO meta VALUES (?, ?)", rows)
        conn.commit()


def meme_key(meme: dict) -> str:
    """A meme's template and words: two memes with the same key are the same joke."""
    from .memes import captions
    return "|".join([meme["format"], meme.get("who") or "", *captions(meme)])


def words_before(day: date) -> dict[str, date]:
    """Every word shown before the day, with the last day it was shown (none before START: the rule wasn't on)."""
    return {w: d for d, w in sorted(WORDS.items()) if d < day} if day >= START else {}


def memes_before(day: date) -> dict[str, date]:
    """Every meme shown before the day (day and week ones), by key, with the last day it was shown."""
    return {meme_key(m): d for (_, d), m in sorted(MEMES.items(), key=lambda x: x[0][1]) if d < day} if day >= START else {}


def fresh(options: list, before: dict[str, date], key=lambda o: o):
    """The first option not shown yet; when every one has been, the one shown longest ago (None without options)."""
    if not options:
        return None
    return next((o for o in options if key(o) not in before), None) or min(options, key=lambda o: before[key(o)])
