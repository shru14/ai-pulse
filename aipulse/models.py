"""Notable AI models for the Releases stream's model tracker.

- Epoch AI's "Notable AI models" dataset (https://epoch.ai/data, CC BY 4.0) decides which models appear:
  models that mattered (state of the art, widely used, historically significant), with release date,
  lab, domain, tasks and access (open weights, API, app only).
- OpenRouter's public model list (https://openrouter.ai/api/v1/models, no key) adds what engineers
  compare: context window and price per million tokens, for the models it serves.

Every collection refreshes both. A model stays listed if a later download drops it.
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone

from . import feeds, store

API = "https://openrouter.ai/api/v1/models"
SOURCE_NAME = "OpenRouter models"
EPOCH_URL = "https://epoch.ai/data/notable_ai_models.csv"
EPOCH_NAME = "Epoch AI notable models"
EPOCH_SINCE = "2023-01-01"

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
CREATE TABLE IF NOT EXISTS notable (
    key         TEXT PRIMARY KEY,          -- name + date (Epoch has no ids)
    name        TEXT NOT NULL,
    lab         TEXT NOT NULL,             -- first organisation, tidied ("Google DeepMind" -> "Google")
    released    TEXT NOT NULL,
    uses        TEXT NOT NULL DEFAULT '',  -- keys of USES: "language,coding,vision"
    access      TEXT NOT NULL DEFAULT '',  -- open / api / app / unreleased
    params      REAL,                      -- parameter count when known
    link        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_notable_released ON notable(released DESC);
"""

# What a reader would use a model for, from Epoch's Domain and Task columns: (domain, task) patterns.
USES = {
    "language": (r"\bLanguage\b", r"Chat|Language modeling|Question answering"),
    "coding": (None, r"Code generation|\bCoding\b|Code autocompletion"),
    "vision": (r"Vision|Multimodal", r"Visual question answering|Image captioning"),
    "image-video": (r"Image generation|\bVideo\b|3D modeling", r"Text-to-image|Text-to-video|Image generation|Video generation"),
    "speech": (r"Speech|Audio", r"Speech recognition|Speech synthesis|Audio generation|Text-to-speech"),
    "science": (r"Biology|Medicine|Mathematics|Earth science|Materials science|Chemistry|Physics", r"Proteins"),
    "robotics": (r"Robotics", r"Robotic"),
}
_USES = {k: (re.compile(d) if d else None, re.compile(t)) for k, (d, t) in USES.items()}
# Organisation name variants folded into one lane.
_LAB_TIDY = [(re.compile(r"\s*\(.*?\)"), ""), (re.compile(r"^Google\b.*"), "Google"), (re.compile(r"^Meta\b.*"), "Meta"),
             (re.compile(r"^Microsoft\b.*"), "Microsoft"), (re.compile(r"^Alibaba\b.*"), "Alibaba"),
             (re.compile(r"\s+(AI|Research)$"), "")]


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
    """Refresh Epoch's notable models and OpenRouter's list; each is recorded in source health like a feed."""
    sync_epoch(conn, fetcher, log)
    try:
        n = save(conn, parse(json.loads(fetcher(API))))
        store.record_source(conn, SOURCE_NAME, API, ok=True, added=n)
        log(f"  {SOURCE_NAME}: {n} new")
        return n
    except Exception as exc:
        store.record_source(conn, SOURCE_NAME, API, ok=False, error=str(exc) or type(exc).__name__)
        log(f"  ! {SOURCE_NAME}: {exc}")
        return 0


def tidy_lab(org: str) -> str:
    lab = (org or "").split(",")[0].strip()
    for pattern, repl in _LAB_TIDY:
        lab = pattern.sub(repl, lab).strip()
    return lab or "Unknown"


def _access(value: str) -> str:
    v = (value or "").lower()
    return ("open" if v.startswith("open weights") else "api" if v.startswith("api") else
            "app" if v.startswith("hosted") else "unreleased")


def parse_epoch(text: str, since: str = EPOCH_SINCE) -> list[dict]:
    """Rows of Epoch's CSV released on or after `since`."""
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        released = (r.get("Publication date") or "")[:10]
        if not released or released < since or not (r.get("Model") or "").strip():
            continue
        domain, task = r.get("Domain") or "", r.get("Task") or ""
        uses = [k for k, (d, t) in _USES.items() if (d and d.search(domain)) or t.search(task)]
        try:
            params = float(r.get("Parameters") or "") or None
        except ValueError:
            params = None
        link = (r.get("Link") or "").split()
        out.append({"key": f"{r['Model'].strip()}|{released}", "name": r["Model"].strip(),
                    "lab": tidy_lab(r.get("Organization")), "released": released, "uses": ",".join(uses),
                    "access": _access(r.get("Model accessibility")), "params": params,
                    "link": link[0] if link else ""})
    return out


def save_notable(conn, rows: list[dict]) -> int:
    _ensure(conn)
    known = {r[0] for r in conn.execute("SELECT key FROM notable")}
    cols = ("key", "name", "lab", "released", "uses", "access", "params", "link")
    conn.executemany(f"INSERT INTO notable ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
                     f"ON CONFLICT(key) DO UPDATE SET {', '.join(f'{c}=excluded.{c}' for c in cols[1:])}",
                     [tuple(m[c] for c in cols) for m in rows])
    conn.commit()
    return sum(m["key"] not in known for m in rows)


def sync_epoch(conn, fetcher=feeds.fetch, log=print) -> int:
    try:
        n = save_notable(conn, parse_epoch(fetcher(EPOCH_URL).decode("utf-8")))
        store.record_source(conn, EPOCH_NAME, EPOCH_URL, ok=True, added=n)
        log(f"  {EPOCH_NAME}: {n} new")
        return n
    except Exception as exc:
        store.record_source(conn, EPOCH_NAME, EPOCH_URL, ok=False, error=str(exc) or type(exc).__name__)
        log(f"  ! {EPOCH_NAME}: {exc}")
        return 0


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def recent(conn, days: int | None = None) -> list[dict]:
    """Notable models released in the last `days` days (all when None), newest first, with OpenRouter's
    context and prices where it serves a model of the same name."""
    _ensure(conn)
    since = (datetime.now(timezone.utc).date() - timedelta(days=days)).isoformat() if days else ""
    served = {}
    for r in conn.execute("SELECT id, name, context, price_in, price_out FROM models ORDER BY length(id)"):
        served.setdefault(_norm(r[1]), {"router_id": r[0], "context": r[2], "price_in": r[3], "price_out": r[4]})
    cur = conn.execute("SELECT name, lab, released, uses, access, params, link FROM notable WHERE released >= ? "
                       "ORDER BY released DESC, lab, name", (since,))
    cols = [c[0] for c in cur.description]
    out = []
    for r in cur:
        m = dict(zip(cols, r))
        m.update(served.get(_norm(m["name"]), {}))
        out.append(m)
    out += _not_yet_in_epoch(conn, since, {_norm(m["name"]) for m in out})
    out.sort(key=lambda m: m["released"], reverse=True)
    return out


def _lab_key(lab: str) -> str:
    """"Qwen" and "Alibaba", "Z.ai" and "Z.ai (Zhipu AI)", "Mistral" and "Mistral AI" compare equal."""
    key = _norm(tidy_lab(lab))
    return "alibaba" if key == "qwen" else key


def _not_yet_in_epoch(conn, since: str, listed: set[str]) -> list[dict]:
    """Epoch adds models a few days after release. Until then, show OpenRouter's newest models from labs
    with at least three notable models since 2023 (so the chart stays on labs that matter)."""
    latest = conn.execute("SELECT max(released) FROM notable").fetchone()[0]
    if not latest:
        return []
    labs = {_lab_key(r[0]) for r in conn.execute(
        "SELECT lab FROM notable GROUP BY lab HAVING count(*) >= 3")}
    window = (datetime.fromisoformat(latest) - timedelta(days=14)).date().isoformat()
    out = []
    for r in conn.execute("SELECT id, name, lab, released, context, price_in, price_out, weights, inputs, outputs "
                          "FROM models WHERE released >= ? AND released >= ?", (window, since)):
        mid, name, lab, released, context, price_in, price_out, weights, inputs, outputs = r
        if _lab_key(lab) not in labs or _norm(name) in listed or re.search(r"\blatest\b", name, re.I):
            continue  # "GPT Sol Latest" is an alias for an existing model, not a release
        uses = ["language"] if "text" in outputs else []
        uses += ["vision"] * ("image" in inputs) + ["image-video"] * ("image" in outputs or "video" in outputs)
        uses += ["speech"] * ("audio" in inputs or "audio" in outputs)
        out.append({"name": name, "lab": tidy_lab("Alibaba" if _lab_key(lab) == "alibaba" else lab),
                    "released": released, "uses": ",".join(uses), "access": "open" if weights else "api",
                    "params": None, "link": "", "router_id": mid, "context": context,
                    "price_in": price_in, "price_out": price_out})
        listed.add(_norm(name))
    return out
