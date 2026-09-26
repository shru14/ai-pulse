"""A static copy of the site for hosts without Python (GitHub Pages).

build() writes the page, the two maps and data.json: every card with its other outlets' versions and bill
lifecycle, plus the header's status. The page sees data-static="1" and filters, searches and pages
data.json in the browser instead of calling /api/items.
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from . import jurisdictions, store
from .server import EU_MEMBERS, TEMPLATE
from .sources import SOURCES

_WORD = re.compile(r"[^\W_]+")


def fold(text: str) -> str:
    """Lowercase without accents ("Véliz" -> "veliz"), as the page folds search words."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))


def search_text(conn) -> dict[str, str]:
    """Card lead id -> " word word ..." from every outlet's version (the columns full-text search covers)."""
    words: dict[str, set[str]] = {}
    for r in conn.execute("SELECT cluster, title, summary, source, tags, authors FROM items"):
        words.setdefault(r[0], set()).update(_WORD.findall(fold(" ".join(r[1:]))))
    return {k: " " + " ".join(sorted(v)) for k, v in words.items()}


def build(conn, out: str | Path) -> int:
    """Write the static site into `out` (replaced). Returns how many cards it holds."""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    cards, _ = store.cards(conn, limit=10**9, eu_members=EU_MEMBERS)
    text = search_text(conn)
    for c in cards:
        c["s"] = text.get(c["id"], "")
        for k in ("added_at", "cluster"):
            c.pop(k, None)
    health = store.source_health(conn, [s["url"] for s in SOURCES])
    data = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"), "cards": cards,
            "stories": store.story_count(conn), "lastRun": store.last_run(conn),
            "jurisdictions": jurisdictions.meta(), "euMembers": sorted(EU_MEMBERS),
            "failingSources": [h for h in health if h["failing"]]}
    (out / "data.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")

    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("<html ", '<html data-static="1" ', 1)
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / ".nojekyll").write_text("")
    return len(cards)
