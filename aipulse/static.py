"""A static copy of the site for hosts without Python (GitHub Pages).

build() writes the page, the two maps, a daily-digest RSS feed per stream (rss.py) and data.json: every card with its other outlets' versions and bill
lifecycle, plus the header's status. The page sees data-static="1" and filters, searches and pages
data.json in the browser instead of calling /api/items.
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import brands, classify, digest, glossary, jurisdictions, memegen, memes, photos, preferences, rss, store
from . import subscribers
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


RECENT_DAYS = 92  # a little over the page's longest range short of "All time"
DAILY_PAGES = 14  # days whose full email is published under daily/ (each email links to its day's page)


def build(conn, out: str | Path) -> int:
    """Write the static site into `out` (replaced). Returns how many cards it holds."""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    cards, _ = store.cards(conn, limit=10**9, eu_members=EU_MEMBERS)
    text = search_text(conn)
    brands.add_logos(conn, cards, lookups=400)
    icons = {c["logo"]["src"] for c in cards if c.get("logo", {}).get("src")}
    if icons:
        (out / "brand-icons").mkdir()
        for src in icons:
            shutil.copy(brands.ICON_DIR / Path(src).name, out / src)
    shutil.copytree(TEMPLATE.parent / "fonts", out / "fonts")  # the page's own fonts (no Google Fonts)
    shutil.copytree(TEMPLATE.parent / "photos", out / "photos")  # the stories' photos (Wikimedia Commons, credited)
    (out / "photos" / "credits.html").write_text(photos.credits_page(), encoding="utf-8")
    (out / "feeds").mkdir()
    for name in rss.FEEDS:
        (out / "feeds" / f"{name}.xml").write_bytes(rss.feed_xml(name, cards))
    # Each recent day's full email (every story, every stream, one tagged table) as a page: every daily email
    # links to it, whatever streams its reader chose.
    (out / "daily").mkdir()
    today = datetime.now(timezone.utc).date()
    for back in range(1, DAILY_PAGES + 1):
        day = today - timedelta(days=back)
        page = digest.build(cards, list(rss.FEEDS), day, layout="full", web=True)
        if page:
            (out / "daily" / f"{day.isoformat()}.html").write_text(page[2], encoding="utf-8")
    for c in cards:
        c["s"] = text.get(c["id"], "")
        for k in ("added_at", "cluster"):
            c.pop(k, None)
    # The page loads data.json at once (the 7, 30 and 90-day views); older cards go into one file per
    # year under archive/, fetched only when someone picks "All time".
    recent_since = (datetime.now(timezone.utc).date() - timedelta(days=RECENT_DAYS)).isoformat()
    recent = [c for c in cards if c["date"] >= recent_since]
    years: dict[str, list[dict]] = {}
    for c in cards:
        if c["date"] < recent_since:
            years.setdefault(c["date"][:4], []).append(c)
    if years:
        (out / "archive").mkdir()
    archive = []
    for year, year_cards in sorted(years.items(), reverse=True):
        (out / "archive" / f"{year}.json").write_text(json.dumps(year_cards, separators=(",", ":")), encoding="utf-8")
        archive.append({"file": f"archive/{year}.json", "cards": len(year_cards)})
    health = store.source_health(conn, [s["url"] for s in SOURCES])
    data = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"), "cards": recent, "archive": archive,
            "stories": store.story_count(conn), "lastRun": store.last_run(conn),
            "jurisdictions": jurisdictions.meta(), "euMembers": sorted(EU_MEMBERS),
            "regions": {k: v[0] for k, v in jurisdictions.REGIONS.items()}, "paperHomes": classify.paper_homes(),
            "failingSources": [h for h in health if h["failing"]]}
    (out / "data.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    (out / "glossary.json").write_text(json.dumps(glossary.payload(cards, today), separators=(",", ":")), encoding="utf-8")
    memegen.prepare(conn, cards, today)  # the week's Gemini meme, if the "memes" step made one (no call here)
    meme = memes.payload(cards, today)
    (out / "meme.json").write_text(json.dumps(meme, separators=(",", ":")), encoding="utf-8")
    if meme["image"]:  # the finished picture: the template with last week's captions written on
        monday = date.fromisoformat(meme["from"])
        (out / "memes").mkdir(exist_ok=True)
        (out / meme["image"]).write_bytes(memes.render(memes.of_the_week(cards, monday)))
    (out / "tags.json").write_text(json.dumps(preferences.options(cards, today), separators=(",", ":")), encoding="utf-8")

    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("<html ", '<html data-static="1" ', 1)
    page = photos.fill(subscribers.fill(page))
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / ".nojekyll").write_text("")
    return len(cards)
