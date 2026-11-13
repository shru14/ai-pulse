"""Which sources may be read: robots.txt, terms, paywalls, keys and the legality audit."""
from pathlib import Path

from aipulse import feeds, store
from aipulse.collect import collect

FIX = Path(__file__).parent / "fixtures"


def test_sources_avoid_hosts_that_block_cloud_servers():
    # The site is built on GitHub Actions: arXiv's search API (406) and Substack (Cloudflare 403) refuse it.
    from aipulse.sources import SOURCES
    assert not [s["url"] for s in SOURCES if "export.arxiv.org/api" in s["url"] or "substack.com" in s["url"]]


def test_no_source_or_lookup_uses_sites_that_forbid_automated_access():
    # Google News (robots.txt) and Bing News (its feed terms) don't allow this use; neither does Google's
    # favicon service. Nothing in the app may fetch from them.
    code = "\n".join(f.read_text(encoding="utf-8") for f in (FIX.parent.parent / "aipulse").glob("*.py") if f.name != "collect.py")
    for host in ("news.google.com", "bing.com", "google.com/s2"):
        assert host not in code, host
    from aipulse.sources import SOURCES
    assert not [s["url"] for s in SOURCES if "google.com" in s["url"].split("/")[2] and "blog.google" not in s["url"]
                   and s["url"].split("/")[2] != "cloudblog.withgoogle.com"]  # Google Cloud's blog, Google's terms


def test_stories_from_google_news_are_removed_once(tmp_path):
    from aipulse.collect import purge_disallowed
    conn = store.connect(tmp_path / "t.db")
    base = {"summary": "", "source": "E", "category": "news", "date": "2026-05-01", "tags": [], "authors": []}
    store.insert(conn, {**base, "title": "Chip deal announced", "url": "https://news.google.com/rss/articles/a"})
    store.insert(conn, {**base, "title": "Chip deal announced, says another outlet", "url": "https://e.com/1"})
    ids = {r[1]: r[0] for r in conn.execute("SELECT id, url FROM items")}
    conn.execute("UPDATE items SET cluster = ?", (ids["https://news.google.com/rss/articles/a"],))
    conn.commit()
    assert purge_disallowed(conn, log=lambda *_: None) == 1
    assert [tuple(r) for r in conn.execute("SELECT url, cluster = id FROM items")] == [("https://e.com/1", 1)]
    store.insert(conn, {**base, "title": "Later", "url": "https://news.google.com/rss/articles/b"})
    assert purge_disallowed(conn, log=lambda *_: None) == 0  # runs once per database


def test_only_free_articles_of_a_paywalled_outlet_are_kept(tmp_path, monkeypatch):
    from aipulse import collect
    from aipulse.collect import drop_subscriber_only
    # No source needs it since The Verge was dropped (7 Oct 2026 terms audit); a stand-in keeps the check tested.
    monkeypatch.setattr(collect, "SOURCES", [{"name": "The Verge AI", "url": "https://www.theverge.com/rss",
                                              "category": "news", "paywall_check": True}])
    paid = b'<script type="application/ld+json">{"@type":"NewsArticle","isAccessibleForFree":false}</script>'
    free = b'<script type="application/ld+json">{"@type":"NewsArticle","isAccessibleForFree":true}</script>'
    assert not feeds.free_to_read(paid) and feeds.free_to_read(free) and feeds.free_to_read(b"<html></html>")
    conn = store.connect(tmp_path / "t.db")
    base = {"summary": "", "source": "The Verge AI", "category": "news", "date": "2026-05-01", "tags": [], "authors": []}
    for n in (1, 2):
        store.insert(conn, {**base, "title": f"Chip deal {n}", "url": f"https://www.theverge.com/news/{n}"})
    pages, read = {"https://www.theverge.com/news/1": paid, "https://www.theverge.com/news/2": free}, []
    fetcher = lambda u: read.append(u) or pages[u]
    assert drop_subscriber_only(conn, fetcher, log=lambda *_: None) == 1
    assert [r[0] for r in conn.execute("SELECT url FROM items")] == ["https://www.theverge.com/news/2"]
    assert drop_subscriber_only(conn, fetcher, log=lambda *_: None) == 0 and len(read) == 2  # each page read once


def test_nothing_is_fetched_against_robots_txt(monkeypatch):
    import pytest
    rules = feeds.Robots()
    rules.parse(["User-agent: *", "Disallow: /private/", "", "User-agent: AIPulse", "Disallow: /feeds/"])
    monkeypatch.setattr(feeds, "_robots", {"news.example": rules, "export.arxiv.org": None})
    fetched = []
    monkeypatch.setattr(feeds.urllib.request, "urlopen", lambda req, timeout: fetched.append(req.full_url))
    assert not feeds.allowed("https://news.example/feeds/ai.xml")  # a rule for AI Pulse by name
    assert feeds.allowed("https://news.example/rss/ai.xml")
    with pytest.raises(feeds.Disallowed):
        feeds.fetch("https://news.example/feeds/ai.xml")
    assert fetched == []  # refused before any request
    assert feeds.allowed("https://export.arxiv.org/api/query?x")  # an API its terms allow (API_HOSTS)
    # read as the standard says: wildcards (The Decoder), the longest rule wins (EIA), groups split only by rules
    decoder, eia, hn, groups = feeds.Robots(), feeds.Robots(), feeds.Robots(), feeds.Robots()
    decoder.parse(["User-agent: *", "Disallow: /wp-admin/", "Disallow: */feed/"])
    assert not decoder.can_fetch("AIPulse", "https://the-decoder.com/feed/")
    assert decoder.can_fetch("AIPulse", "https://the-decoder.com/news-sitemap.xml")
    eia.parse(["User-agent: *", "Allow: /", "", "Disallow: /rss"])
    assert not eia.can_fetch("AIPulse", "https://www.eia.gov/rss/press_rss.xml")
    assert eia.can_fetch("AIPulse", "https://www.eia.gov/pressroom/")
    hn.parse(["User-agent: *", "Allow: /*.json$", "Allow: /*.json?*$", "Disallow: /"])
    assert hn.can_fetch("AIPulse", "https://hacker-news.firebaseio.com/v0/topstories.json")
    assert not hn.can_fetch("AIPulse", "https://hacker-news.firebaseio.com/v0/")
    groups.parse(["User-agent: *", "Crawl-delay: 10", "User-agent: BadBot", "Disallow: /"])
    assert groups.can_fetch("AIPulse", "https://news.example/")  # BadBot's rule isn't ours
    from aipulse.sources import SOURCES
    arxiv = [s for s in SOURCES if "arxiv.org" in s["url"]]
    assert arxiv and all(s.get("pause", 0) >= 3 for s in arxiv)  # arXiv: one request every 3 seconds


def test_a_source_whose_api_key_isnt_set_is_skipped(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    conn = store.connect(tmp_path / "t.db")
    asked = []
    src = {"name": "OpenAI API models", "lab": "OpenAI", "format": "openai_models", "category": "tool",
           "url": "https://api.openai.com/v1/models", "key_env": "OPENAI_API_KEY"}
    assert collect(conn, [src], fetcher=lambda u: asked.append(u) or b"{}", log=lambda *a: None) == 0
    assert asked == [] and conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 0


def test_github_pages_are_never_read_only_its_api():
    import pytest
    assert not feeds.allowed("https://github.com/MoonshotAI/Kimi-K3")  # its terms: scraping only for research or archives
    with pytest.raises(feeds.Disallowed):
        feeds.fetch("https://github.com/MoonshotAI/Kimi-K3")


def test_every_source_has_legal_evidence():
    # Each site read has its terms page, what it says and the kind of permission recorded (aipulse/terms.py).
    from urllib.parse import urlsplit
    from aipulse.sources import SOURCES
    from aipulse.terms import TERMS
    kinds = {"official", "licence", "feed terms", "terms read", "no terms", "unconfirmed", "robots.txt"}
    hosts = {urlsplit(s["url"]).netloc.lower() for s in SOURCES}
    assert sorted(hosts - set(TERMS)) == []  # a new source needs its evidence first
    assert all(TERMS[h][0] in kinds and TERMS[h][2] for h in hosts)


def test_no_source_is_read_on_unconfirmed_terms():
    # A site whose terms page refuses automated readers is read only after someone has read its terms by hand.
    from urllib.parse import urlsplit
    from aipulse.sources import SOURCES
    from aipulse.terms import TERMS
    assert sorted(s["name"] for s in SOURCES if TERMS[urlsplit(s["url"]).netloc.lower()][0] == "unconfirmed") == []


def test_the_audit_reports_changed_terms_and_blocks(tmp_path, monkeypatch):
    from aipulse import audit
    monkeypatch.setattr(audit, "SOURCES", [{"name": "Site", "url": "https://site.test/feed"},
                                           {"name": "Gone", "url": "https://gone.test/feed"}])
    monkeypatch.setattr(audit, "TERMS", {"site.test": ("terms read", "https://site.test/terms", "fine"),
                                         "gone.test": ("no terms", "", "none")})
    monkeypatch.setattr(audit, "PLATFORM", {})
    pages = {"https://site.test/feed": b"<rss/>", "https://site.test/terms": b"<p>Be kind to each other always.</p>"}
    def fetch(url):
        if url not in pages:
            raise feeds.Disallowed(url)
        return pages[url]
    saved = tmp_path / "audit.json"
    assert audit.run(fetch, log=lambda *_: None, saved=saved) == ["Gone: robots.txt no longer allows https://gone.test/feed"]
    pages["https://site.test/terms"] = b"<p>You may not use any robot or scraper to access the Site.</p>"
    problems = audit.run(fetch, log=lambda *_: None, saved=saved)
    assert any(p.startswith("Site: terms changed since") and "robot or scraper" in p for p in problems)
