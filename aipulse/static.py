"""A static copy of the site for hosts without Python (GitHub Pages).

build() writes the page, the two maps, a daily-digest RSS feed per stream (rss.py) and data.json: every card with its other outlets' versions and bill
lifecycle, plus the header's status. The page sees data-static="1" and filters, searches and pages
data.json in the browser instead of calling /api/items.
"""

from __future__ import annotations

import csv
import io
import json
import re
from html import escape
import shutil
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import brands, classify, digest, glossary, jurisdictions, memegen, memes, photos, preferences, rss, store
from . import subscribers
from .server import EU_MEMBERS, TEMPLATE

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
DAILY_FROM = date(2026, 9, 28)  # the first daily email's day: every day since has its full email under daily/


# Bots that gather pages to train AI models. Search engines may read everything; these may not, as AI Pulse only
# reads sites that allow it and carries other publishers' headlines (Google-Extended doesn't affect Google Search).
AI_TRAINING_BOTS = ("GPTBot", "Google-Extended", "CCBot", "ClaudeBot", "anthropic-ai", "Applebot-Extended",
                    "meta-externalagent", "Bytespider", "cohere-training-data-crawler", "Amazonbot")


def robots_txt() -> str:
    """robots.txt: search engines read the site (not the readers' dossier data); AI-training bots read nothing."""
    blocked = "".join(f"User-agent: {bot}\nDisallow: /\n\n" for bot in AI_TRAINING_BOTS)
    return f"{blocked}User-agent: *\nDisallow: /dossier/\n\nSitemap: {rss.SITE}sitemap.xml\n"


def sitemap(days: list[date], today: date, pages: list[str] = ()) -> str:
    """sitemap.xml: the pages search engines should index: the front page, the streams', the tracker's pages by
    country and the glossary's (`pages`, paths under the site) and each day's full edition."""
    urls = ([(rss.SITE, today)] + [(f"{rss.SITE}{p}", today) for p in pages]
            + [(f"{rss.SITE}daily/{d.isoformat()}.html", d) for d in sorted(days, reverse=True)])
    rows = "".join(f"  <url><loc>{u}</loc><lastmod>{d.isoformat()}</lastmod></url>\n" for u, d in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n'


# Each stream's own address: the page, opened at that stream, with its own title and description for search engines
# (the page sets the same titles, PAGE_TITLE).
STREAM_PAGES = {
    "all": ("all", "All stories", "All AI stories, newest first", "Every AI story from 100+ public sources, newest first."),
    "tool": ("releases", "Releases", "AI model and product releases", rss.FEEDS["releases"][2]),
    "news": ("industry", "Industry", "AI industry news: companies, deals and markets", rss.FEEDS["news"][2]),
    "research": ("research", "Research", "New AI research papers", rss.FEEDS["research"][2]),
    "regulation": ("regulation", "Regulation tracker", "AI regulation tracker: bills, laws and standards by country",
                   rss.FEEDS["regulation"][2]),
    "policy": ("policy", "Policy", "AI policy news: governments, courts and politics", rss.FEEDS["policy"][2]),
    "infra": ("infra", "Infra & climate", "AI data centres, energy and climate", rss.FEEDS["infra"][2]),
}


def stream_page(page: str, cat: str) -> str:
    """The front page as `cat`'s own page: its title, description and address, and its heading already written."""
    path, name, title, desc = STREAM_PAGES[cat]
    title, desc, url = escape(f"{title} · AI Pulse"), escape(f"{desc} Updated every 6 hours, free, no ads."), f"{rss.SITE}{path}/"
    page = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", page, count=1)
    page = re.sub(r'(<meta (?:name="description"|property="og:description") content=")[^"]*', rf"\g<1>{desc}", page)
    page = re.sub(r'(<meta property="og:title" content=")[^"]*', rf"\g<1>{title}", page, count=1)
    page = re.sub(r'(<link rel="canonical" href="|<meta property="og:url" content=")[^"]*', rf"\g<1>{url}", page)
    return page.replace('<h2 id="sec-title"></h2><p id="sec-desc"></p>',
                        f'<h2 id="sec-title">{escape(name)}</h2><p id="sec-desc">{escape(STREAM_PAGES[cat][3])}</p>', 1)


def opml(title: str = "AI Pulse") -> str:
    """feeds/all.opml: every stream's RSS feed in one file, for a feed reader to import at once."""
    rows = "".join(f'    <outline type="rss" text="{escape(f"{title} · {name}")}" title="{escape(f"{title} · {name}")}" '
                   f'xmlUrl="{rss.SITE}feeds/{key}.xml" htmlUrl="{rss.SITE}#{category}"/>\n'
                   for key, (category, name, *_) in rss.FEEDS.items())
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<opml version="2.0">\n  <head><title>{title}</title></head>\n'
            f'  <body>\n{rows}  </body>\n</opml>\n')


def tracker_csv(cards: list[dict]) -> str:
    """tracker.csv: the Regulation tracker's official records only (legislatures, OECD.AI, ISO/IEC, IEEE): facts and
    a link to each record, newest first. News outlets' stories in the tracker stay out: their headlines are theirs."""
    from .bills import OFFICIAL_SOURCES
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["date", "countries", "type", "title", "source", "link"])
    for c in sorted((c for c in cards if c["category"] == "regulation" and c["source"] in OFFICIAL_SOURCES),
                    key=lambda c: c["date"], reverse=True):
        w.writerow([c["date"], " ".join(c.get("jurisdictions") or []), c.get("action") or "", c["title"].strip(),
                    c["source"], c["url"]])
    return out.getvalue()


SAMPLE_PER_STREAM = 4  # stories a section shows in the sample email (daily/sample.html)


def sample_cards(cards: list[dict], day: date) -> list[dict]:
    """A day's cards with every word of theirs replaced by a placeholder: the email's format, none of its content."""
    seen: dict[str, int] = {}
    out = []
    for c in sorted((c for c in cards if (c.get("date") or "")[:10] == day.isoformat()), key=lambda c: c["id"]):
        k = seen[c["category"]] = seen.get(c["category"], 0) + 1
        if k <= SAMPLE_PER_STREAM:
            out.append({**c, "title": "Example headline: what happened, as the outlet put it",
                        "summary": "A line or two of summary, from the publisher's own description of the story.",
                        "source": f"Outlet {'ABCD'[k - 1]}", "url": rss.SITE, "also": [], "tags": [], "jurisdictions": [],
                        "authors": ""})
    return out


def sample_page(cards: list[dict], day: date) -> str | None:
    """daily/sample.html: what the daily email looks like, with placeholder stories (the front page links to it)."""
    page = digest.build(sample_cards(cards, day), list(rss.FEEDS), day, layout="full", web=True)
    if not page:
        return None
    note = ('<div style="max-width:720px;margin:16px auto;padding:12px 16px;border:2px solid #000;background:#F0E442;'
            'font:600 15px Arial,sans-serif;color:#000">A sample of the daily email: this is its format, and the stories '
            'are placeholders. <a href="/#subscribe" style="color:#000">Subscribe to get the real one every morning →</a></div>')
    html = page[2].replace("<head>", '<head><meta name="robots" content="noindex">', 1)
    return re.sub(r"<body[^>]*>", lambda m: m.group(0) + note, html, count=1)


def daily_index(conn, total: int, days: list[date], out: Path) -> None:
    """daily/: every day's email as a page, newest first, by month; Sunday's email (it covers the Saturday) also
    brings the week in AI."""
    from . import pages
    months: dict[str, list[str]] = {}
    for d in sorted(days, reverse=True):
        sunday = " <span class=\"grp\">Sunday's email: the week in AI</span>" if digest.weekly(d) else ""
        months.setdefault(f"{d:%B %Y}", []).append(
            f'<li><a href="/daily/{d.isoformat()}.html">{digest.long_day(d)}</a>{sunday}</li>')
    body = ('<h1>Daily editions</h1>\n<p class="intro">Every morning\'s email as a page: the day before in AI, every '
            'story from every stream in one tagged table. On Sundays the email is the weekly edition: the week in AI '
            '(Monday to Saturday), then Saturday\'s stories. <a href="/#subscribe">Get it in your inbox</a></p>\n'
            + "\n".join(f'<h2>{m}</h2>\n<ul class="days">\n' + "\n".join(rows) + "\n</ul>" for m, rows in months.items()))
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI Pulse daily editions",
            "url": f"{rss.SITE}daily/"}
    pages.write_css(out)
    (out / "daily" / "index.html").write_text(pages.page(
        "Daily AI news, every edition · AI Pulse", "Every AI Pulse daily email as a page: the day's AI releases, "
        "industry news, research, laws and policy in one table. On Sundays, the week in AI.", "daily/", body, data,
        pages.frame(conn, total), ("/", "Back to AI Pulse")), encoding="utf-8")


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
    (out / "feeds" / "all.opml").write_text(opml(), encoding="utf-8")  # every stream's feed in one file
    (out / "tracker.csv").write_text(tracker_csv(cards), encoding="utf-8")
    # Each recent day's full email (every story, every stream, one tagged table) as a page: every daily email
    # links to it, whatever streams its reader chose.
    (out / "daily").mkdir()
    # The newest is also daily/latest.html: the front page's "See yesterday's full table".
    today = datetime.now(timezone.utc).date()
    published = []
    for back in range((today - DAILY_FROM).days, 0, -1):
        day = today - timedelta(days=back)
        page = digest.build(cards, list(rss.FEEDS), day, layout="full", web=True)
        if page:
            published.append(day)
            for name in (day.isoformat(), "latest"):
                (out / "daily" / f"{name}.html").write_text(page[2], encoding="utf-8")
    sample = next((s for d in reversed(published) if (s := sample_page(cards, d))), None)
    if sample:  # the front page's "See what the email looks like"
        (out / "daily" / "sample.html").write_text(sample, encoding="utf-8")
    daily_index(conn, len(cards), published, out)  # daily/: every edition, by month
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
    # "total": every card of all time, so the front page's count needs no archive file
    data = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"), "cards": recent, "archive": archive,
            "total": len(cards),
            "stories": store.story_count(conn), "lastRun": store.last_run(conn),
            "jurisdictions": jurisdictions.meta(), "euMembers": sorted(EU_MEMBERS),
            "regions": {k: v[0] for k, v in jurisdictions.REGIONS.items()}, "paperHomes": classify.paper_homes()}
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
    for cat, (path, *_) in STREAM_PAGES.items():  # /policy/ and the rest: the same page, opened at that stream
        (out / path).mkdir()
        (out / path / "index.html").write_text(stream_page(page, cat), encoding="utf-8")
    # readers' weekly dossiers: the page, and each interest's section the full run kept (weekly.prepare)
    from . import weekly
    (out / "dossier.html").write_text((TEMPLATE.parent / "dossier.html").read_text(encoding="utf-8"), encoding="utf-8")
    # the Sunday email's "Get my dossier" button opens it, to ask the dossier's questions
    (out / "ask.html").write_text(subscribers.fill((TEMPLATE.parent / "ask.html").read_text(encoding="utf-8")), encoding="utf-8")
    weekly.publish(conn, out, today)
    weekly.publish_vectors(conn, out, today)  # the dossier page's search by meaning, in the reader's browser
    (out / "robots.txt").write_text(robots_txt(), encoding="utf-8")
    from . import countries
    places = countries.build(conn, cards, out, today)  # the tracker by country (tracker/), for search engines
    from . import glossary_pages
    places += glossary_pages.build(conn, cards, out, today)  # the glossary as a page per word (glossary/)
    (out / "sitemap.xml").write_text(sitemap(published, today, [f"{p}/" for p, *_ in STREAM_PAGES.values()] + ["daily/"] + places), encoding="utf-8")
    shutil.copy(TEMPLATE.parent / "og.png", out / "og.png")  # the link preview image (our own drawing)
    (out / ".nojekyll").write_text("")
    return len(cards)
