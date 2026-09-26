"""New AI models, with release date, context window and price, for the Releases stream's model tracker.

Source: OpenRouter's public model list (https://openrouter.ai/api/v1/models, no key), which covers
closed models (GPT, Claude, Gemini, Grok) and open-weight ones, with the date each was added, context
length, price per token and, for open weights, the Hugging Face repository. Every collection stores
new models and refreshes known ones; a model stays listed after OpenRouter drops it.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import feeds, store

API = "https://openrouter.ai/api/v1/models"
SOURCE_NAME = "OpenRouter models"

SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
    id          TEXT PRIMARY KEY,          -- OpenRouter id, e.g. "anthropic/claude-opus-5.5"
    name        TEXT NOT NULL,             -- "Claude Opus 5.5"
    lab         TEXT NOT NULL,             -- "Anthropic"
    released    TEXT NOT NULL,             -- date added to OpenRouter (YYYY-MM-DD)
    context     INTEGER NOT NULL DEFAULT 0,
    price_in    REAL,                      -- US$ per million input tokens (0 = free)
    price_out   REAL,                      -- US$ per million output tokens
    weights     TEXT NOT NULL DEFAULT '',  -- Hugging Face repo when the weights are open
    inputs      TEXT NOT NULL DEFAULT '',  -- "text,image,audio"
    outputs     TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_models_released ON models(released DESC);
"""


def _ensure(conn) -> None:
    conn.executescript(SCHEMA)


def _per_million(price) -> float | None:
    try:
        return round(float(price) * 1_000_000, 4)
    except (TypeError, ValueError):
        return None


def parse(data: dict) -> list[dict]:
    """Models from OpenRouter's reply, without routers, variants (":free", ":batch") or unpriced entries."""
    out = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        price_in = _per_million((m.get("pricing") or {}).get("prompt"))
        if ":" in mid or mid.startswith(("openrouter/", "stealth/")) or price_in is None or price_in < 0:
            continue
        lab, _, name = (m.get("name") or mid).partition(": ")
        if not name:  # names are "Lab: Model"; fall back to the id's owner
            lab, name = mid.split("/")[0], lab
        arch = m.get("architecture") or {}
        created = m.get("created") or 0
        out.append({
            "id": mid, "name": name.strip(), "lab": lab.strip(),
            "released": datetime.fromtimestamp(created, timezone.utc).date().isoformat(),
            "context": int(m.get("context_length") or 0),
            "price_in": price_in, "price_out": _per_million((m.get("pricing") or {}).get("completion")),
            "weights": m.get("hugging_face_id") or "",
            "inputs": ",".join(arch.get("input_modalities") or []),
            "outputs": ",".join(arch.get("output_modalities") or []),
            "description": (m.get("description") or "").strip()[:400],
        })
    return out


def save(conn, models: list[dict]) -> int:
    """Insert new models and refresh known ones. Returns how many are new."""
    _ensure(conn)
    known = {r[0] for r in conn.execute("SELECT id FROM models")}
    cols = ("id", "name", "lab", "released", "context", "price_in", "price_out", "weights", "inputs", "outputs",
            "description")
    conn.executemany(f"INSERT INTO models ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                     f"ON CONFLICT(id) DO UPDATE SET {', '.join(f'{c}=excluded.{c}' for c in cols[1:])}",
                     [tuple(m[c] for c in cols) for m in models])
    conn.commit()
    return sum(m["id"] not in known for m in models)


def sync(conn, fetcher=feeds.fetch, log=print) -> int:
    """Fetch the model list and store it; recorded in source health like a feed."""
    try:
        n = save(conn, parse(json.loads(fetcher(API))))
        store.record_source(conn, SOURCE_NAME, API, ok=True, added=n)
        log(f"  {SOURCE_NAME}: {n} new")
        return n
    except Exception as exc:
        store.record_source(conn, SOURCE_NAME, API, ok=False, error=str(exc) or type(exc).__name__)
        log(f"  ! {SOURCE_NAME}: {exc}")
        return 0


def recent(conn, days: int | None = None) -> list[dict]:
    """Models released in the last `days` days (all when None), newest first."""
    _ensure(conn)
    since = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat() if days else ""
    cur = conn.execute("SELECT * FROM models WHERE released >= ? ORDER BY released DESC, lab, name", (since,))
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur]
