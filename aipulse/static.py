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

from . import brands, classify, digest, glossary, jurisdictions, kind_pages, memegen, memes, photos, preferences, rss, store
from . import pages, subscribers
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


UNDATED = ("standards/", *kind_pages.paths())  # pages without a date of their own: they change only when an entry is added


def sitemap(days: list[date], today: date, pages: list[str] = ()) -> str:
    """sitemap.xml: the pages search engines should index: the front page, the streams', the tracker's pages by
    country and the glossary's (`pages`, paths under the site) and each day's full edition. A glossary word's page
    has no date: its meaning, written by hand, rarely changes; nor has a page in UNDATED."""
    word = lambda p: p in UNDATED or p.startswith("glossary/") and p != "glossary/"
    urls = ([(rss.SITE, today)] + [(f"{rss.SITE}{p}", None if word(p) else today) for p in pages]
            + [(f"{rss.SITE}daily/{d.isoformat()}.html", d) for d in sorted(days, reverse=True)])
    rows = "".join(f"  <url><loc>{u}</loc>" + (f"<lastmod>{d.isoformat()}</lastmod>" if d else "") + "</url>\n"
                   for u, d in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n'


# Each stream's own address: the page, opened at that stream, with its own title and description for search engines
# (the page sets the same titles, PAGE_TITLE).
STREAM_PAGES = {
    "all": ("all", "All stories", "All AI stories, newest first", "Every AI story from 200+ public sources, newest first."),
    "tool": ("releases", "Releases", "AI model and product releases", rss.FEEDS["releases"][2]),
    "news": ("industry", "Industry", "AI industry news: companies, deals and markets", rss.FEEDS["news"][2]),
    "research": ("research", "Research", "New AI research papers", rss.FEEDS["research"][2]),
    "regulation": ("regulation", "Regulation tracker", "AI regulation tracker: bills, laws and standards by country",
                   rss.FEEDS["regulation"][2]),
    "policy": ("policy", "Policy", "AI policy news: governments, courts and politics", rss.FEEDS["policy"][2]),
    "infra": ("infra", "Infra", "AI data centres and the power, water and land they draw on", rss.FEEDS["infra"][2]),
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


# What the daily email's sign-up keeps and why (EU GDPR, Art. 13); kept in step with apps-script/Code.gs.
PRIVACY_ROWS = [
    ("Your email address", "To send your email", "Until you unsubscribe (unconfirmed: 7 days)"),
    ("Your choices: streams, how often, topics, words, questions", "To pick your stories", "Until you unsubscribe"),
    ("Codes in your links", "So only you can change them", "Until you unsubscribe"),
]


def privacy_page() -> str:
    """The privacy notice: the site keeps nothing about visitors; the daily email keeps only what it needs."""
    rows = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td><td>{escape(c)}</td></tr>" for a, b, c in PRIVACY_ROWS)
    mail = '<a href="mailto:projectaipulse@gmail.com">projectaipulse@gmail.com</a>'
    what = "What AI Pulse keeps about you: nothing about site visitors, and for the daily email only what it needs to send it."
    body = (f'<h1>Privacy</h1>\n<p class="intro">AI Pulse is free and non-commercial. Responsible for your data: AI Pulse, {mail}.</p>\n'
            '<h2>The site</h2><p>No cookies or ads. Visits are counted anonymously with GoatCounter: the page, the site '
            'you came from, your browser, system, country and screen size. No IP address, cookie or ID is kept. '
            'Your settings stay in your own browser. GitHub Pages, '
            'which hosts the site, may log IP addresses for security.</p>'
            '<h2>The email</h2><p>Only if you sign up and confirm, and you can unsubscribe from any email.</p>'
            f'<table class="mt pv"><thead><tr><th>What we keep</th><th>Why</th><th>How long</th></tr></thead><tbody>{rows}</tbody></table>'
            '<p>Kept in the project’s Google account and sent from its Gmail. Never sold or shared.</p>'
            f'<h2>Your rights</h2><p>Ask to see, correct or delete your data: {mail}. You can also complain to your data '
            'protection authority.</p>')
    data = {"@context": "https://schema.org", "@type": "WebPage", "name": "Privacy", "description": what}
    return pages.page("Privacy · AI Pulse", what, "privacy.html", body, data, pages.frame(), ("/", "Back to AI Pulse"))


def about_page(page: str) -> str:
    """The site's page opened at About (the template holds its text): its own title, description and address."""
    return page_at(page, "about", "About · AI Pulse", "What AI Pulse is, where its stories come from and how it is made.")


def page_at(page: str, path: str, title: str, desc: str) -> str:
    """The site's page with its own title, description and address (/about/, /discussing/)."""
    url = f"{rss.SITE}/{path}/"
    page = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", page, count=1)
    page = re.sub(r'(<meta (?:name="description"|property="og:description") content=")[^"]*', rf"\g<1>{desc}", page)
    page = re.sub(r'(<meta property="og:title" content=")[^"]*', rf"\g<1>{title}", page, count=1)
    return re.sub(r'(<link rel="canonical" href="|<meta property="og:url" content=")[^"]*', rf"\g<1>{url}", page)


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
# the sample's placeholder stories, by stream: the kind of story each section carries, never a real one (each
# labelled as its row's type: Industry's as news, the tracker's in this order)
SAMPLE_ACTIONS = ("proposal", "law", "body", "standard")
SAMPLE_STORIES = {
    "tool": [("A lab releases a new model", "What it does better, and who can use it."),
             ("An app adds an AI feature", "What changes for its users."),
             ("An open-source model gets an update", "Where to get it, and under what licence."),
             ("A developer tool ships a new version", "What's new in this release.")],
    "news": [("A company raises funding for its AI work", "How much, from whom, and what it's for."),
             ("Two firms sign an AI deal", "What each side gets."),
             ("A chipmaker reports its results", "How AI demand shaped the quarter."),
             ("A startup changes its leadership", "Who's in, who's out, and why.")],
    "research": [("A paper proposes a new training method", "The idea in a sentence, from the abstract."),
                 ("A new benchmark tests what models can't do", "What it measures, and how today's models score."),
                 ("A study looks at AI in the workplace", "What the authors found."),
                 ("A paper makes models smaller and faster", "How, and at what cost to accuracy.")],
    "regulation": [("A bill on AI is introduced", "Where it is now, and what's next."),
                   ("A new AI law is adopted", "What it requires, and from when."),
                   ("A country sets up an AI office", "What it will oversee."),
                   ("A standards body publishes an AI standard", "What it covers.")],
    "policy": [("A government sets out its AI plan", "The main points, as announced."),
               ("A court rules in an AI case", "What was decided, and what it means."),
               ("Lawmakers question a tech company", "What they asked, and what it said."),
               ("Countries agree on AI cooperation", "Who signed, and what they agreed.")],
    "infra": [("A new data centre is announced", "Where, how big, and how it will be powered."),
              ("A report counts AI's energy use", "The headline figure, and how it was measured."),
              ("A grid operator plans for AI demand", "What it expects, and by when."),
              ("A cloud firm signs a clean power deal", "How much power, and from where.")],
}


def sample_cards(cards: list[dict], day: date) -> list[dict]:
    """A day's cards with every word of theirs replaced by a placeholder: the email's format, none of its content."""
    seen: dict[str, int] = {}
    out = []
    for c in sorted((c for c in cards if (c.get("date") or "")[:10] == day.isoformat()), key=lambda c: c["id"]):
        k = seen[c["category"]] = seen.get(c["category"], 0) + 1
        if k <= SAMPLE_PER_STREAM:
            title, summary = SAMPLE_STORIES.get(c["category"], SAMPLE_STORIES["news"])[k - 1]
            out.append({**c, "title": title, "summary": summary, "source": f"Outlet {'ABCD'[k - 1]}",
                        "kind": "news" if c["category"] == "news" else c.get("kind"),
                        "action": SAMPLE_ACTIONS[k - 1] if c["category"] == "regulation" else c.get("action"), "url": rss.SITE, "also": [], "tags": [], "jurisdictions": [],
                        "authors": ""})
    return out


def web_edition(html: str, path: str, description: str, title: str | None = None) -> str:
    """A daily email made a page search engines read well (the email itself is unchanged): its description, its
    one address (daily/latest.html points to the dated page), the link preview, and its opening line as the heading."""
    url = f"{rss.SITE}{path}"
    if title:
        html = re.sub(r"<title>.*?</title>", lambda m: f"<title>{escape(title)}</title>", html, count=1)
    title = re.search(r"<title>(.*?)</title>", html).group(1)
    head = (f'<meta name="description" content="{escape(description)}"><link rel="canonical" href="{url}">'
            f'<meta property="og:title" content="{title}"><meta property="og:description" content="{escape(description)}">'
            f'<meta property="og:url" content="{url}"><meta property="og:image" content="{rss.SITE}og.png">'
            f'<meta name="twitter:card" content="summary_large_image">{pages.counter()}')
    html = html.replace("</title>", "</title>" + head, 1).replace("<html>", '<html lang="en">', 1)
    return re.sub(r'<div style="(font-size:22px;font-weight:bold;line-height:1.3;margin:0 0 8px)">(.*?)</div>',
                  r'<h1 style="\1">\2</h1>', html, count=1)


def edition_description(html: str, day: date) -> str:
    """A day's page description: the day, how many stories, the streams."""
    read = re.search(r"We read (\d+ stor(?:y|ies) from \d+ sources?)", html)
    return (f"AI Pulse daily, {digest.long_day(day)}: " + (f"{read.group(1)} " if read else "stories ")
            + "on AI releases, industry, research, laws, policy and infrastructure.")


def sample_page(cards: list[dict], day: date, out: Path | None = None) -> str | None:
    """daily/sample.html: what the daily email looks like, with placeholder stories (the front page links to it),
    and the day's real meme of the day where the email has it (its picture saved beside the page, so search engines
    can index it)."""
    page = digest.build(sample_cards(cards, day), list(rss.FEEDS), day, layout="full", web=True)
    if not page:
        return None
    note = ('<div style="max-width:720px;margin:16px auto;padding:12px 16px;border:2px solid #000;background:#F0E442;'
            'font:600 15px Arial,sans-serif;color:#000">A sample of the daily email. '
            '<a href="/#subscribe" style="color:#000">Subscribe to get the real one every morning →</a></div>')
    html = re.sub(r"<body[^>]*>", lambda m: m.group(0) + note, page[2], count=1)
    html = re.sub(r"We read \d+ stor(y|ies) from \d+ sources?", "We read the day's stories from 200+ sources", html)
    meme = memes.of_the_day(cards, day)
    picture = meme and memes.render(meme)
    if picture and out:
        name = f"meme-of-the-day.{'png' if digest._kind(picture) == 'png' else 'jpg'}"
        (out / "daily" / name).write_bytes(picture)
        block = (f'<div style="margin:0 0 14px"><div style="font-size:11px;font-weight:bold;letter-spacing:2px;'
                 f'text-transform:uppercase;color:{digest.HEADLINE};margin-bottom:6px">Meme of the day</div>'
                 f'{memes.html(meme, name, small=True)}</div>')
        html = html.replace('20px 10px">', '20px 10px">' + block, 1)
    return web_edition(html, "daily/sample.html", "What the AI Pulse daily email looks like: the day's AI releases, "
                       "industry news, research, laws, policy and infrastructure in one table, with sample stories.",
                       "Sample daily email · AI Pulse")


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
    (out / "privacy.html").write_text(privacy_page(), encoding="utf-8")
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
            html = web_edition(page[2], f"daily/{day.isoformat()}.html", edition_description(page[2], day))
            for name in (day.isoformat(), "latest"):
                (out / "daily" / f"{name}.html").write_text(html, encoding="utf-8")
    for d in reversed(published):  # the day's Gemini meme, if the "memes" step made one (no call here)
        memegen.prepare(conn, cards, today, day=d)
        if (sample := sample_page(cards, d, out)):
            break
    else:
        sample = None
    if sample:  # the front page's "See what the email looks like"
        (out / "daily" / "sample.html").write_text(sample, encoding="utf-8")
    daily_index(conn, len(cards), published, out)  # daily/: every edition, by month
    for c in cards:
        c["s"] = text.get(c["id"], "")
        c.pop("cluster", None)
        if c["date"] < (today - timedelta(days=2)).isoformat():  # arrival times only for the ticker's two days
            c.pop("added_at", None)
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
    memegen.prepare(conn, cards, today)  # the past 7 days' Gemini meme, if the "memes" step made one (no call here)
    meme = memes.payload(cards, today)
    (out / "meme.json").write_text(json.dumps(meme, separators=(",", ":")), encoding="utf-8")
    if meme["image"]:  # the finished picture: the template with the past 7 days' captions written on
        (out / "memes").mkdir(exist_ok=True)
        (out / meme["image"]).write_bytes(memes.render(memes.of_the_7_days(cards, date.fromisoformat(meme["to"]))))
    from . import social, today as board
    (out / "today.json").write_text(json.dumps(board.payload(conn, recent, today), separators=(",", ":")), encoding="utf-8")
    (out / "social.json").write_text(json.dumps(social.payload(conn), separators=(",", ":")), encoding="utf-8")
    (out / "tags.json").write_text(json.dumps(preferences.options(cards, today), separators=(",", ":")), encoding="utf-8")

    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace("<html ", '<html data-static="1" ', 1)
    page = photos.fill(subscribers.fill(page)).replace("</head>", pages.counter() + "</head>", 1)
    (out / "index.html").write_text(page, encoding="utf-8")
    (out / "about").mkdir()
    (out / "about" / "index.html").write_text(about_page(page), encoding="utf-8")  # the same page, opened at About
    (out / "discussing").mkdir()
    (out / "discussing" / "index.html").write_text(page_at(page, "discussing", "People are discussing · AI Pulse",
        "The most-discussed AI threads on Hacker News in the last two days."), encoding="utf-8")
    (out / "saved").mkdir()  # the reader's bookmarks (kept in their browser): not in the sitemap
    (out / "saved" / "index.html").write_text(page_at(page, "saved", "Saved stories · AI Pulse",
        "The stories you saved on AI Pulse, kept in this browser."), encoding="utf-8")
    (out / "today").mkdir()
    (out / "today" / "index.html").write_text(page_at(page, "today", "Today in AI · AI Pulse",
        "Today's AI stories, ranked by how many outlets carry them."), encoding="utf-8")
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
    places += countries.standards_page(conn, cards, out)  # every AI standard on the tracker (standards/)
    places += kind_pages.build(conn, cards, out)  # each stream's stories split into pages (industry/opinion/, releases/openai/, ...)
    from . import glossary_pages
    places += glossary_pages.build(conn, cards, out, today)  # the glossary as a page per word (glossary/)
    from . import topics
    places += topics.build(conn, cards, out, today)  # storylines followed over time, a page each (topics/)
    from . import monthly
    places += monthly.build(conn, cards, out, today)  # a booklet for each month that is over (monthly/)
    from . import insights
    places += insights.build(conn, cards, out, today)  # each issue's month in numbers (monthly/<month>/insights/)
    from . import court, echoes, harms, infra_watch, jobs, press, promises, safety
    places += echoes.build(conn, cards, out, today)  # the tracker's subjects spreading place to place (rule-echoes/)
    places += promises.build(conn, cards, out, today)  # companies' promises and their launches (promises/)
    places += harms.build(conn, cards, out, today)  # AI harms by subject beside the rules on it (harm-to-rule/)
    places += jobs.build(conn, cards, out, today)  # job cuts linked to AI, by the reason the company gave (jobs-blamed-on-ai/)
    places += press.build(conn, cards, out, today)  # research papers the news reported on, by subject (papers-in-the-news/)
    places += court.build(conn, cards, out, today)  # lawsuits against AI makers and where each stands (ai-in-court/)
    places += safety.build(conn, cards, out, today)  # system cards, evaluations, red-teaming and frameworks (ai-safety-hub/)
    places += infra_watch.build(conn, cards, out, today)  # data-centre builds, power deals and permits (Infra's features)
    from . import retired
    places += retired.build(conn, cards, out, today)  # models the labs have set a shut-down date for (Releases' feature)
    from . import owners
    places += owners.build(conn, cards, out, today)  # the big companies' stakes in AI labs (Industry's feature)
    from . import consultations
    places += consultations.build(conn, cards, out, today)  # governments asking the public about AI (Policy's feature)
    from . import release_cards
    places += release_cards.build(conn, cards, out, today)  # every major model release: weights, licence, price (Releases' feature)
    (out / "sitemap.xml").write_text(sitemap(published, today, [f"{p}/" for p, *_ in STREAM_PAGES.values()] + ["daily/", "about/", "discussing/", "today/"] + ["daily/sample.html"] * bool(sample) + places), encoding="utf-8")
    shutil.copy(TEMPLATE.parent / "og.png", out / "og.png")  # the link preview image (our own drawing)
    (out / ".nojekyll").write_text("")
    return len(cards)
