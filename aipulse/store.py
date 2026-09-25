"""SQLite storage for feed items."""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

CATEGORIES = ("tool", "news", "policy", "research", "regulation")

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id         TEXT PRIMARY KEY,          -- hash of the normalized URL
    title      TEXT NOT NULL,
    summary    TEXT NOT NULL DEFAULT '',
    url        TEXT NOT NULL,
    source     TEXT NOT NULL,
    category   TEXT NOT NULL CHECK (category IN ('tool','news','policy','research','regulation')),
    date       TEXT NOT NULL,             -- YYYY-MM-DD the story was published / released
    tags       TEXT NOT NULL DEFAULT '',  -- comma-separated
    authors    TEXT NOT NULL DEFAULT '',  -- comma-separated, for papers
    jurisdictions TEXT NOT NULL DEFAULT '', -- comma-separated codes (US, EU, ...), for regulation
    action     TEXT NOT NULL DEFAULT '',  -- enforcement / investigation / law / proposal / guidance
    added_at   TEXT NOT NULL,
    cluster    TEXT NOT NULL DEFAULT '',  -- id of the card's lead story (its own id when it stands alone)
    bill       TEXT NOT NULL DEFAULT ''   -- key of the tracked bill this card follows (see bills.py)
);
CREATE INDEX IF NOT EXISTS idx_items_date ON items(date DESC);
CREATE INDEX IF NOT EXISTS idx_items_cat ON items(category);
CREATE INDEX IF NOT EXISTS idx_items_cluster ON items(cluster);
CREATE INDEX IF NOT EXISTS idx_items_title ON items(lower(title));  -- duplicate-headline check on insert
CREATE TABLE IF NOT EXISTS runs (
    ran_at TEXT PRIMARY KEY,
    added  INTEGER NOT NULL,
    errors TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sources (
    url          TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    last_attempt TEXT NOT NULL,
    last_success TEXT NOT NULL DEFAULT '',  -- '' if it has never worked
    failures     INTEGER NOT NULL DEFAULT 0,  -- consecutive failed runs; reset by a success
    last_error   TEXT NOT NULL DEFAULT '',
    entries      INTEGER NOT NULL DEFAULT 0,  -- entries in the last successful fetch
    added        INTEGER NOT NULL DEFAULT 0   -- new stories from the last successful fetch
);
"""

# Full-text search over every story's text, kept in sync with `items` by triggers. Porter stemming lets
# "regulate" find "regulation"; remove_diacritics lets "Veliz" find "Véliz".
FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    title, summary, source, tags, authors,
    content='items', content_rowid='rowid', tokenize='porter unicode61 remove_diacritics 2');
CREATE TRIGGER IF NOT EXISTS items_fts_ai AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, title, summary, source, tags, authors)
    VALUES (new.rowid, new.title, new.summary, new.source, new.tags, new.authors);
END;
CREATE TRIGGER IF NOT EXISTS items_fts_ad AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, summary, source, tags, authors)
    VALUES ('delete', old.rowid, old.title, old.summary, old.source, old.tags, old.authors);
END;
CREATE TRIGGER IF NOT EXISTS items_fts_au AFTER UPDATE OF title, summary, source, tags, authors ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, summary, source, tags, authors)
    VALUES ('delete', old.rowid, old.title, old.summary, old.source, old.tags, old.authors);
    INSERT INTO items_fts(rowid, title, summary, source, tags, authors)
    VALUES (new.rowid, new.title, new.summary, new.source, new.tags, new.authors);
END;
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""
FTS_VERSION = "1"  # bump to rebuild the search index on next connect

# A source is shown as failing after this many runs in a row without a successful fetch.
FAILING_AFTER = 3

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "ref", "fbclid", "gclid"}


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in TRACKING])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower().removeprefix("www."), parts.path.rstrip("/"), query, ""))


def item_id(url: str) -> str:
    return hashlib.sha1(normalize_url(url).encode()).hexdigest()[:16]


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    # WAL lets the web server read while a separate scheduled collection writes.
    conn.execute("PRAGMA journal_mode=WAL")
    rebuilt = _migrate(conn)
    conn.executescript(SCHEMA)
    conn.executescript(FTS_SCHEMA)
    from .bills import connect_tables  # bills.py imports this module
    connect_tables(conn)
    version = conn.execute("SELECT value FROM meta WHERE key = 'fts'").fetchone()
    if rebuilt or not version or version[0] != FTS_VERSION:
        conn.execute("INSERT INTO items_fts(items_fts) VALUES ('rebuild')")
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('fts', ?)", (FTS_VERSION,))
        conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> bool:
    """Bring an older items table up to date, keeping every row. Returns True if the table was rebuilt."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='items'").fetchone()
    if not row:
        return False
    rebuilt = False
    if not all(f"'{c}'" in row[0] for c in CATEGORIES):
        # SQLite can't alter a CHECK constraint: copy into a fresh table.
        old_cols = [r["name"] for r in conn.execute("PRAGMA table_info(items)")]
        cols = ",".join(old_cols)
        conn.executescript(
            "BEGIN; DROP TRIGGER IF EXISTS items_fts_ai; DROP TRIGGER IF EXISTS items_fts_ad;"
            " DROP TRIGGER IF EXISTS items_fts_au; ALTER TABLE items RENAME TO items_old;"
            " DROP INDEX IF EXISTS idx_items_date; DROP INDEX IF EXISTS idx_items_cat;"
            " DROP INDEX IF EXISTS idx_items_cluster; DROP INDEX IF EXISTS idx_items_title;"
            + SCHEMA
            + f"INSERT INTO items ({cols}) SELECT {cols} FROM items_old; DROP TABLE items_old; COMMIT;"
        )
        rebuilt = True
    have = {r["name"] for r in conn.execute("PRAGMA table_info(items)")}
    for column in ("cluster", "bill"):
        if column not in have:
            conn.execute(f"ALTER TABLE items ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
    # Stories without a card of their own yet stand alone until the next regroup.
    conn.execute("UPDATE items SET cluster = id WHERE cluster = ''")
    conn.commit()
    return rebuilt


def title_exists(conn: sqlite3.Connection, title: str) -> bool:
    return conn.execute("SELECT 1 FROM items WHERE lower(title) = lower(?)", (title,)).fetchone() is not None


def insert(conn: sqlite3.Connection, item: dict) -> bool:
    """Insert if new (by URL or identical title). Returns True when added."""
    if title_exists(conn, item["title"]):
        return False
    cur = conn.execute(
        "INSERT OR IGNORE INTO items (id,title,summary,url,source,category,date,tags,authors,jurisdictions,action,"
        "added_at,cluster) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (item_id(item["url"]), item["title"], item["summary"], item["url"], item["source"], item["category"],
         item["date"], ",".join(item.get("tags", [])), ",".join(item.get("authors", [])),
         ",".join(item.get("jurisdictions", [])), item.get("action") or "",
         datetime.now(timezone.utc).isoformat(timespec="seconds"), item_id(item["url"])),
    )
    return cur.rowcount == 1


def log_run(conn: sqlite3.Connection, added: int, errors: list[str]) -> None:
    conn.execute("INSERT OR REPLACE INTO runs VALUES (?,?,?)",
                 (datetime.now(timezone.utc).isoformat(timespec="seconds"), added, "\n".join(errors)))
    conn.commit()


def query(conn: sqlite3.Connection, category: str | None = None, q: str | None = None,
          days: int | None = None, limit: int = 300) -> list[dict]:
    sql, args = "SELECT * FROM items WHERE 1=1", []
    if category in CATEGORIES:
        sql += " AND category = ?"; args.append(category)
    if q:
        sql += " AND (title LIKE ? OR summary LIKE ? OR tags LIKE ? OR source LIKE ? OR authors LIKE ?)"; args += [f"%{q}%"] * 5
    if days:
        sql += " AND date >= date('now', ?)"; args.append(f"-{int(days)} days")
    sql += " ORDER BY date DESC, added_at DESC LIMIT ?"; args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    return [{**dict(r), "tags": [t for t in r["tags"].split(",") if t],
             "authors": [a for a in r["authors"].split(",") if a],
             "jurisdictions": [j for j in r["jurisdictions"].split(",") if j]} for r in rows]


def counts(conn: sqlite3.Connection, days: int | None = None) -> dict:
    sql, args = "SELECT category, COUNT(*) n FROM items", []
    if days:
        sql += " WHERE date >= date('now', ?)"; args.append(f"-{int(days)} days")
    out = dict.fromkeys(CATEGORIES, 0)
    out.update({r["category"]: r["n"] for r in conn.execute(sql + " GROUP BY category", args)})
    out["all"] = sum(out.values())
    return out


def last_run(conn: sqlite3.Connection) -> dict | None:
    r = conn.execute("SELECT * FROM runs ORDER BY ran_at DESC LIMIT 1").fetchone()
    return dict(r) if r else None


def prune(conn: sqlite3.Connection, keep_days: int) -> int:
    cur = conn.execute("DELETE FROM items WHERE date < date('now', ?)", (f"-{int(keep_days)} days",))
    conn.commit()
    return cur.rowcount


def set_regulation(conn: sqlite3.Connection, item_id_: str, category: str, jurisdictions: list[str],
                   action: str | None) -> None:
    conn.execute("UPDATE items SET category = ?, jurisdictions = ?, action = ? WHERE id = ?",
                 (category, ",".join(jurisdictions), action or "", item_id_))


def exists(conn: sqlite3.Connection, url: str) -> bool:
    return conn.execute("SELECT 1 FROM items WHERE id = ?", (item_id(url),)).fetchone() is not None


def update_text(conn: sqlite3.Connection, item_id_: str, title: str, summary: str) -> None:
    conn.execute("UPDATE items SET title = ?, summary = ? WHERE id = ?", (title, summary, item_id_))


def set_tags(conn: sqlite3.Connection, item_id_: str, tags: list[str]) -> None:
    conn.execute("UPDATE items SET tags = ? WHERE id = ?", (",".join(tags), item_id_))


def record_source(conn: sqlite3.Connection, name: str, url: str, ok: bool, error: str = "",
                  entries: int = 0, added: int = 0) -> None:
    """Log one fetch of a source: a success resets its failure count, a failure adds one."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute("INSERT OR IGNORE INTO sources (url, name, last_attempt) VALUES (?, ?, ?)", (url, name, now))
    if ok:
        conn.execute("UPDATE sources SET name = ?, last_attempt = ?, last_success = ?, failures = 0, last_error = '',"
                     " entries = ?, added = ? WHERE url = ?", (name, now, now, entries, added, url))
    else:
        conn.execute("UPDATE sources SET name = ?, last_attempt = ?, failures = failures + 1, last_error = ?"
                     " WHERE url = ?", (name, now, error[:300], url))


def source_health(conn: sqlite3.Connection, urls: list[str] | None = None) -> list[dict]:
    """Every tracked source (optionally only these URLs), failing ones first."""
    rows = [dict(r) for r in conn.execute("SELECT * FROM sources ORDER BY failures DESC, name")]
    if urls is not None:
        wanted = set(urls)
        rows = [r for r in rows if r["url"] in wanted]
    for r in rows:
        r["failing"] = r["failures"] >= FAILING_AFTER
    return rows


# --- Cards: one per event (its lead story plus the other outlets' versions), searched and paged in SQL ---

def _row(r) -> dict:
    return {**dict(r), "tags": [t for t in r["tags"].split(",") if t],
            "authors": [a for a in r["authors"].split(",") if a],
            "jurisdictions": [j for j in r["jurisdictions"].split(",") if j]}


def fts_query(q: str) -> str | None:
    """User text -> an FTS5 query: every word must appear, each as a prefix ("regulat" finds "regulation")."""
    words = re.findall(r"[^\W_][\w'\-]*", q or "")
    return " ".join('"' + w.replace('"', "") + '"*' for w in words) or None


def _card_where(category=None, q=None, days=None, place=None, eu_members=()) -> tuple[str, list]:
    where, args = ["i.id = i.cluster"], []  # leads only; members come with them
    if category in CATEGORIES:
        where.append("i.category = ?"); args.append(category)
    if days:
        where.append("i.date >= date('now', ?)"); args.append(f"-{int(days)} days")
    if place:
        # An EU-wide action applies in every member state.
        cond = "(',' || i.jurisdictions || ',') LIKE ?"; args.append(f"%,{place},%")
        if place in eu_members:
            cond = f"({cond} OR (',' || i.jurisdictions || ',') LIKE '%,EU,%')"
        where.append(cond)
    match = fts_query(q)
    if match:
        # A card matches if any outlet's version of the story matches.
        where.append("i.cluster IN (SELECT m.cluster FROM items_fts JOIN items m ON m.rowid = items_fts.rowid"
                     " WHERE items_fts MATCH ?)")
        args.append(match)
    return " AND ".join(where), args


def cards(conn: sqlite3.Connection, category=None, q=None, days=None, place=None, limit=40, offset=0,
          eu_members=()) -> tuple[list[dict], int]:
    """One page of cards, newest first, and how many cards match in total."""
    where, args = _card_where(category, q, days, place, eu_members)
    total = conn.execute(f"SELECT COUNT(*) FROM items i WHERE {where}", args).fetchone()[0]
    leads = [_row(r) for r in conn.execute(
        f"SELECT * FROM items i WHERE {where} ORDER BY i.date DESC, i.added_at DESC LIMIT ? OFFSET ?",
        [*args, limit, offset])]
    if leads:
        ids = [c["id"] for c in leads]
        also: dict[str, list[dict]] = {}
        marks = ",".join("?" * len(ids))
        for r in conn.execute(f"SELECT title, source, url, date, cluster FROM items WHERE cluster IN ({marks})"
                              f" AND id != cluster ORDER BY date, added_at", ids):
            also.setdefault(r["cluster"], []).append({k: r[k] for k in ("title", "source", "url", "date")})
        for c in leads:
            c["also"] = also.get(c["id"], [])
            if c.get("bill"):  # a tracked bill: its lifecycle timeline
                from .bills import lifecycle
                c["lifecycle"] = lifecycle(conn, c["bill"])
    return leads, total


def card_counts(conn: sqlite3.Connection, q=None, days=None) -> dict:
    """Cards per tab for the current search and time range."""
    where, args = _card_where(None, q, days)
    out = dict.fromkeys(CATEGORIES, 0)
    out.update({r[0]: r[1] for r in conn.execute(f"SELECT i.category, COUNT(*) FROM items i WHERE {where}"
                                                  f" GROUP BY i.category", args)})
    out["all"] = sum(out.values())
    return out


def regulation_tally(conn: sqlite3.Connection, q=None, days=None) -> dict:
    """Proposals and laws per jurisdiction for the map and its table (expert pieces have no place)."""
    where, args = _card_where("regulation", q, days)
    national: dict[str, int] = {}
    laws: dict[str, int] = {}
    n = 0
    for r in conn.execute(f"SELECT i.jurisdictions, i.action FROM items i WHERE {where} AND i.action != 'expert'",
                          args):
        n += 1
        for code in filter(None, r[0].split(",")):
            national[code] = national.get(code, 0) + 1
            if r[1] == "law":
                laws[code] = laws.get(code, 0) + 1
    return {"national": national, "laws": laws, "cards": n}


def story_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]


def set_clusters(conn: sqlite3.Connection, lead_of: dict[str, str]) -> int:
    """Point each story at its card's lead. Returns how many changed."""
    cur = conn.executemany("UPDATE items SET cluster = ? WHERE id = ? AND cluster != ?",
                           [(lead, sid, lead) for sid, lead in lead_of.items()])
    return cur.rowcount
