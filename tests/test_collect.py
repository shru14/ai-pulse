"""Fetching and reading sources: feeds, pages, APIs, retries, translation, summaries, storage."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from aipulse import classify, feeds, store
from aipulse.collect import collect, reclassify

FIX = Path(__file__).parent / "fixtures"
from helpers import _seed


def test_parse_rss_1():
    """RSS 1.0, as the BIS writes it: items beside the channel, every tag in the RSS 1.0 namespace."""
    xml = (b'<?xml version="1.0"?><rdf:RDF xmlns="http://purl.org/rss/1.0/" '
           b'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/">'
           b'<channel rdf:about="https://www.bis.org/x.rss"><title>Media releases</title></channel>'
           b'<item rdf:about="https://www.bis.org/media-releases/ai"><title>BIS report on AI in finance</title>'
           b'<description>Central banks and AI.</description><dc:date>2026-10-16T00:00:00Z</dc:date></item></rdf:RDF>')
    [e] = feeds.parse(xml)
    assert e["title"] == "BIS report on AI in finance" and e["url"] == "https://www.bis.org/media-releases/ai"
    assert e["summary"] == "Central banks and AI." and e["published"].isoformat() == "2026-10-16T00:00:00+00:00"


def test_parse_rss_and_atom():
    rss = feeds.parse((FIX / "sample_rss.xml").read_bytes())
    atom = feeds.parse((FIX / "sample_atom.xml").read_bytes())
    assert rss[0]["title"] == "OpenAI releases a new open-weight model"
    assert rss[0]["published"] is not None
    assert "<p>" not in rss[0]["summary"]
    assert atom[0]["url"] == "https://example.com/blog/gemini-update"


def test_dedupe_by_url():
    assert store.item_id("https://www.x.com/a/?utm_source=t") == store.item_id("https://x.com/a")


def test_collect_end_to_end(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    sources = [{"name": "Fixture", "url": "rss", "category": "news"},
               {"name": "Fixture Atom", "url": "atom", "category": "tool"}]
    files = {"rss": FIX / "sample_rss.xml", "atom": FIX / "sample_atom.xml"}
    fetch = lambda u: files[u].read_bytes()
    n = collect(conn, sources, max_age_days=100000, fetcher=fetch, log=lambda *_: None)
    assert n == 3  # the non-AI story is skipped
    assert collect(conn, sources, max_age_days=100000, fetcher=fetch, log=lambda *_: None) == 0
    items = {i["title"]: i for i in store.query(conn)}
    consultation = items["EU Commission opens consultation on AI Act rules"]
    assert consultation["category"] == "regulation"
    assert (consultation["jurisdictions"], consultation["action"]) == (["EU"], "proposal")


def test_professor_papers_need_an_exact_author_match(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    sources = [{"name": "arXiv", "url": "arxiv", "category": "research", "ai_only": True,
                "professors": ["Sergey Levine", "Fei-Fei Li"]}]
    fetch = lambda u: (FIX / "sample_arxiv.xml").read_bytes()
    assert collect(conn, sources, max_age_days=100000, fetcher=fetch, log=lambda *_: None) == 2
    items = {i["title"]: i for i in store.query(conn, "research")}
    assert "Antichiral hinge states in a photonic lattice" not in items
    paper = items["Long-Horizon Reinforcement Learning for Language Agents"]
    assert paper["category"] == "research"
    assert paper["tags"] == ["Sergey Levine", "Research"]  # papers: professor or company, and #Research
    assert paper["authors"] == ["Jane Doe", "Sergey Levine"]
    assert items["Visual world models for robots"]["tags"] == ["Fei-Fei Li", "Research"]
    assert store.counts(conn)["research"] == 2


def test_name_key():
    assert classify.name_key("Fei-Fei Li") == classify.name_key("Li Fei-Fei") != classify.name_key("Fei Li")
    assert classify.name_key("Christopher D. Manning") == classify.name_key("Christopher Manning")
    assert classify.name_key("Bernhard Schölkopf") == classify.name_key("Bernhard Scholkopf")


def test_migrates_old_schema(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE items (id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL, source TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('tool','news','policy')), date TEXT NOT NULL,
            tags TEXT NOT NULL DEFAULT '', added_at TEXT NOT NULL);
        CREATE INDEX idx_items_date ON items(date DESC);
        INSERT INTO items VALUES ('a','Old story','s','https://x.com/a','X','news','2026-01-01','EU','2026-01-01T00:00:00');
    """)
    old.commit(); old.close()
    conn = store.connect(path)
    assert [i["title"] for i in store.query(conn)] == ["Old story"]
    assert store.insert(conn, {"title": "A paper", "summary": "", "url": "https://arxiv.org/abs/1", "source": "arXiv",
                               "category": "research", "date": "2026-01-02", "authors": ["A B"]})
    conn.commit()
    assert store.connect(path).execute("SELECT COUNT(*) FROM items").fetchone()[0] == 2


def test_hugging_face_papers_keep_big_tech_and_professors():
    import json
    data = [
        {"paper": {"id": "2609.1", "title": "Qwen tech report", "summary": "s", "publishedAt": "2026-09-20T00:00:00Z",
                   "authors": [{"name": "Qwen Team"}, {"name": "A B"}]}, "organization": {"name": "Qwen", "fullname": "Qwen"}},
        {"paper": {"id": "2609.2", "title": "Robot paper", "summary": "s", "publishedAt": "2026-09-20T00:00:00Z",
                   "authors": [{"name": "Sergey Levine"}]}},
        {"paper": {"id": "2609.3", "title": "Unaffiliated paper", "summary": "s", "publishedAt": "2026-09-20T00:00:00Z",
                   "authors": [{"name": "Bernie Smith"}]}},
    ]
    entries = feeds.parse_hf_daily(json.dumps(data).encode())
    assert entries[0]["url"] == "https://arxiv.org/abs/2609.1" and entries[0]["orgs"] == ["Qwen"]
    from aipulse.collect import match_companies
    assert match_companies(["Qwen"], []) == ["Alibaba"]
    assert match_companies([], ["DeepSeek-AI", "Jane Doe"]) == ["DeepSeek"]
    assert match_companies([], ["Bernie Smith", "Ernie Banks"]) == []  # people, not Baidu's ERNIE


def test_hugging_face_collect(tmp_path):
    import json
    data = [
        {"paper": {"id": "2609.1", "title": "Gemini robotics report", "summary": "s", "publishedAt": "2020-09-20T00:00:00Z",
                   "authors": [{"name": "A B"}]}, "organization": {"name": "google", "fullname": "Google"}},
        {"paper": {"id": "2609.3", "title": "Unaffiliated paper", "summary": "s", "publishedAt": "2020-09-20T00:00:00Z",
                   "authors": [{"name": "C D"}]}},
    ]
    conn = store.connect(tmp_path / "t.db")
    sources = [{"name": "HF", "url": "hf", "format": "hf_daily", "category": "research", "ai_only": True,
                "companies": True}]
    assert collect(conn, sources, max_age_days=100000, fetcher=lambda u: json.dumps(data).encode(),
                   log=lambda *_: None) == 1
    [paper] = store.query(conn, "research")
    assert paper["tags"] == ["Google", "Research"]


def test_clean_title():
    from aipulse.brief import clean_title
    assert clean_title("UK regulator proposes AI rules \u2014 Cyprus Mail") == "UK regulator proposes AI rules"
    assert clean_title("Eurobites: CMA tweaks search-screen proposals") == "CMA tweaks search-screen proposals"
    assert clean_title("A Simple Guide to AI - American Enterprise Institute", "AEI") == "A Simple Guide to AI"
    assert clean_title("AI: key updates (10 \u2013 23 Sep)") == "AI: key updates (10 \u2013 23 Sep)"  # a date range
    assert clean_title("Newsom signs bill \u2014 and critics react") == "Newsom signs bill \u2014 and critics react"


def test_clean_summary_never_repeats_the_headline():
    from aipulse.brief import clean_summary
    title = "Massachusetts gaming commission probes DraftKings AI practices"
    assert clean_summary(title + " qz.com", title, "qz.com") == ""
    text = ("Jane Doe is a senior reporter at Example News. Regulators opened a review of how the operator uses AI "
            "to target promotions. The commission will hold hearings next month. A third sentence is dropped.")
    assert clean_summary(text, title) == ("Regulators opened a review of how the operator uses AI to target "
                                          "promotions. The commission will hold hearings next month.")
    assert clean_summary("Great story. The post Great story appeared first on Blog.", "x") == ""


def test_headline_only_items_get_a_draft():
    from aipulse.collect import fill_summary
    item = {"title": "Kotek issues executive order establishing AI procurement safeguards", "summary": "",
            "url": "https://example.com/a", "category": "regulation", "action": "law",
            "jurisdictions": ["US"], "tags": ["Google"]}
    fill_summary(item)
    assert item["summary"] == "A law adopted in the United States, involving Google."
    kept = {**item, "summary": "The order sets safety standards."}
    fill_summary(kept)
    assert kept["summary"] == "The order sets safety standards."  # a real summary is left alone


# Duplicate grouping, scored on hand-labelled events (tests/fixtures/duplicates.json).
def test_duplicate_stories_group_into_one_card():
    from aipulse import cluster
    s = cluster.score()
    # 225 labelled stories (the Sept 25 set added the Copilot, Muse and court duplicates). Grouping favours
    # precision: a wrong "Also reported by" is a visible mistake, a missed one only a repeated headline.
    # Before the same-outlet and headline-name rules: precision 91%, recall 73%, 7 of 15 events on one card.
    assert s["precision"] >= 0.95 and s["recall"] >= 0.75 and s["events_on_one_card"] >= 7, s
    items = __import__("json").loads(cluster.FIXTURE.read_text(encoding="utf-8"))
    cards = [{**g[0], "also": g[1:]} for g in cluster.group([it for it in items if not cluster._alone(it)])]
    cards += [{**it, "also": []} for it in items if cluster._alone(it)]
    assert all(o.get("source") != c.get("source") for c in cards for o in c["also"] if c.get("source"))  # never itself
    # One blog's two posts about a product, and two outlets' different stories about OpenAI, stay apart.
    card_of = {o["title"]: c["title"] for c in cards for o in [c, *c["also"]]}
    assert card_of["Better prompt caching for GPT-6"] != card_of["Introducing GPT-6 Sol and Luna"]
    assert card_of["OpenAI Admits AI is Killing the Internet"] != next(t for t in card_of if t.startswith("Unsecured OpenAI agents"))
    ma = [c for c in cards if c["title"].startswith("Massachusetts") and c["also"]]
    assert len(ma) == 1 and len(ma[0]["also"]) == 7  # all 8 outlets on one card
    # Different governors' orders stay apart even though the wording is similar.
    pritzker = next(c for c in cards if "Pritzker" in c["title"])
    assert not any("Kotek" in o["title"] for o in pritzker["also"])


def test_search_index_follows_edits(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    _seed(conn, [("Old headline about chips", "X", "news", {})])
    [card], _ = store.cards(conn, q="chips")
    store.update_text(conn, card["id"], "New headline about robots", "")
    conn.commit()
    assert store.cards(conn, q="chips")[1] == 0 and store.cards(conn, q="robots")[1] == 1


# --- Source health: retries, empty replies, and failure tracking ---
class _Resp:
    def __init__(self, body): self.body = body
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _http_error(code, retry_after=None):
    import email.message, urllib.error
    headers = email.message.Message()
    if retry_after:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError("https://x", code, "err", headers, None)


def test_fetch_retries_rate_limits_with_backoff(monkeypatch):
    waits, replies = [], [_http_error(429), _http_error(503, retry_after="7"), _Resp(b"<rss/>")]
    def urlopen(req, timeout, **kw):
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(feeds.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(feeds, "allowed", lambda url: True)
    monkeypatch.setattr(feeds.time, "sleep", waits.append)
    assert feeds.fetch("https://x") == b"<rss/>"
    assert waits == [2.0, 7.0]  # our backoff first, then the server's Retry-After


def test_fetch_does_not_retry_permanent_errors(monkeypatch):
    import pytest, urllib.error
    calls = []
    def urlopen(req, timeout, **kw):
        calls.append(1)
        raise _http_error(404)
    monkeypatch.setattr(feeds.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(feeds, "allowed", lambda url: True)
    monkeypatch.setattr(feeds.time, "sleep", lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        feeds.fetch("https://x")
    assert len(calls) == 1


def test_empty_arxiv_replies_are_retried_then_fail(monkeypatch):
    import pytest
    from aipulse import collect as collect_mod
    monkeypatch.setattr(collect_mod.time, "sleep", lambda s: None)
    empty, full = b"<feed xmlns='http://www.w3.org/2005/Atom'/>", (FIX / "sample_arxiv.xml").read_bytes()
    replies = [empty, full]
    src = {"name": "arXiv", "url": "arxiv", "expect_entries": True}
    assert len(collect_mod.fetch_entries(src, lambda u: replies.pop(0))) == 3  # second try worked
    with pytest.raises(collect_mod.EmptyFeed):
        collect_mod.fetch_entries(src, lambda u: empty)
    # A normal feed may legitimately be empty.
    assert collect_mod.fetch_entries({"url": "x"}, lambda u: b"<rss><channel/></rss>") == []


def test_source_is_flagged_after_three_failed_runs(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    good = {"name": "Good", "url": "rss", "category": "news"}
    bad = {"name": "Dead feed", "url": "dead", "category": "news"}
    def fetch(u):
        if u == "dead":
            raise OSError("HTTP Error 404: Not Found")
        return (FIX / "sample_rss.xml").read_bytes()
    quiet = lambda *_: None
    for run in range(3):
        collect(conn, [good, bad], max_age_days=100000, fetcher=fetch, log=quiet)
        failing = [h["name"] for h in store.source_health(conn) if h["failing"]]
        assert failing == ([] if run < 2 else ["Dead feed"])
    health = {h["name"]: h for h in store.source_health(conn)}
    assert health["Dead feed"]["failures"] == 3 and "404" in health["Dead feed"]["last_error"]
    assert health["Dead feed"]["last_success"] == ""
    assert health["Good"]["failures"] == 0 and health["Good"]["entries"] == 3
    # The project inbox hears about it once: a table row with why; not again on the next runs
    from aipulse.collect import source_alert
    rows = store.newly_failing(conn, ["rss", "dead"])
    subject, text, html = source_alert(rows)
    assert subject == "AI Pulse: 1 source stopped working" and "Dead feed" in text and "404" in html and "<table" in html
    store.mark_alerted(conn, ["dead"])
    collect(conn, [bad], max_age_days=100000, fetcher=fetch, log=quiet)
    assert store.newly_failing(conn, ["rss", "dead"]) == []
    # One good run clears the warning, and a later failure is told again
    collect(conn, [bad], max_age_days=100000, fetcher=lambda u: (FIX / "sample_rss.xml").read_bytes(), log=quiet)
    assert not any(h["failing"] for h in store.source_health(conn))
    for _ in range(3):
        collect(conn, [bad], max_age_days=100000, fetcher=fetch, log=quiet)
    assert [r["name"] for r in store.newly_failing(conn, ["rss", "dead"])] == ["Dead feed"]


def test_arxiv_rss_splits_authors_and_skips_revisions(tmp_path):
    entries = feeds.parse_arxiv_rss((FIX / "sample_arxiv_rss.xml").read_bytes())
    assert [e["url"][-5:] for e in entries] == ["00001", "00002"]  # the "replace" item is left out
    assert entries[0]["authors"] == ["Jane Q. Doe", "Chelsea Finn", "Sergey Levine"]
    assert entries[1]["authors"] == ["A. Person", "Percy Liang"]
    assert entries[0]["summary"].startswith("We train a robot policy")  # "arXiv:... Announce Type" dropped
    assert entries[1]["summary"] == "Alignment & oversight for language models."
    conn = store.connect(tmp_path / "t.db")
    src = [{"name": "arXiv", "url": "x", "format": "arxiv_rss", "category": "research", "ai_only": True,
            "professors": ["Sergey Levine", "Fei-Fei Li"]}]
    collect(conn, src, max_age_days=100000, fetcher=lambda u: (FIX / "sample_arxiv_rss.xml").read_bytes(),
            log=lambda *_: None)
    assert [(i["title"], i["tags"]) for i in store.query(conn)] == [("Robot Learning from Play at Scale", ["Sergey Levine", "Research"])]


def test_cards_for_more_stories_than_sqlite_takes_in_one_query(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    for i in range(1200):  # over SQLite's per-query limit on older builds (999)
        store.insert(conn, {"title": f"Story number {i} about AI", "summary": "", "url": f"https://e.com/{i}",
                            "source": "E", "category": "news", "date": "2026-09-01", "tags": [], "authors": []})
    conn.commit()
    cards, total = store.cards(conn, limit=10**9)
    assert total == 1200 and len(cards) == 1200 and all(c["also"] == [] for c in cards)


def test_headline_plus_subtitle_is_not_a_summary():
    from aipulse.brief import clean_summary
    title = "Pre-training a 1.11B LLM on a 6 GB Laptop GPU"
    assert clean_summary(title + " — Measured, Not Claimed Hugging Face", title, "Hugging Face") == ""
    assert clean_summary("OpenAI releases GPT-6. The new model handles longer tasks and costs less for developers.",
                         "OpenAI releases GPT-6", "X") == "The new model handles longer tasks and costs less for developers."


def test_msit_summaries_lose_the_stray_mark(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    store.insert(conn, {"title": "Pilot AI app for grocery shopping", "summary": "﻿- The price body was launched.",
                        "url": "https://www.msit.go.kr/eng/1", "source": "Ministry of Science and ICT (Korea)",
                        "category": "policy", "date": "2026-09-30", "tags": [], "authors": []})
    reclassify(conn, fetcher=lambda u: b"")
    assert conn.execute("SELECT summary FROM items").fetchone()[0] == "The price body was launched."


def test_government_apis_parse():
    fr = b'{"results": [{"title": "Artificial Intelligence Safety Rule", "html_url": "https://www.federalregister.gov/d/1",' \
         b' "abstract": "The agency proposes rules for AI systems.", "publication_date": "2024-02-01"}]}'
    [e] = feeds.parse_federal_register(fr)
    assert (e["url"], e["summary"], e["published"].date().isoformat()) == (
        "https://www.federalregister.gov/d/1", "The agency proposes rules for AI systems.", "2024-02-01")
    uk = b'{"results": [{"title": "AI white paper", "link": "/government/publications/ai-white-paper",' \
         b' "description": "A pro-innovation approach.", "public_timestamp": "2023-03-29T09:00:00Z"}]}'
    [g] = feeds.parse_govuk(uk)
    assert g["url"] == "https://www.gov.uk/government/publications/ai-white-paper" and g["published"].year == 2023


def test_feed_archive_pages_back_to_the_start_date(tmp_path, monkeypatch):
    from datetime import date
    from aipulse import backfill
    def rss(*items):
        body = "".join(f"<item><title>AI story {t}</title><link>https://e.com/{t}</link>"
                       f"<description>An AI model story number {t} with enough words.</description>"
                       f"<pubDate>{d}</pubDate></item>" for t, d in items)
        return f"<rss><channel>{body}</channel></rss>".encode()
    pages = {1: rss(("a", "Mon, 01 Sep 2025 10:00:00 GMT")), 2: rss(("b", "Mon, 01 Jan 2024 10:00:00 GMT")),
             3: rss(("c", "Mon, 01 Jan 2022 10:00:00 GMT")), 4: rss(("d", "Mon, 01 Jan 2021 10:00:00 GMT"))}
    asked = []
    def fetch(url):
        n = int(url.rsplit("paged=", 1)[1]) if "paged=" in url else 1
        asked.append(n)
        return pages[n]
    monkeypatch.setattr(backfill, "SOURCES", [{"name": "Blog", "url": "https://e.com/feed/", "category": "news",
                                               "ai_only": True, "paged": True}])
    import aipulse.collect as col
    monkeypatch.setattr(col.time, "sleep", lambda s: None)  # collect's pause between sources
    conn = store.connect(tmp_path / "t.db")
    assert backfill.feed_archives(conn, date(2023, 1, 1), fetch, log=lambda *_: None) == 2
    assert asked == [1, 2, 3]  # page 3 reaches before 2023: stop there (its old story is left out)
    assert backfill.feed_archives(conn, date(2023, 1, 1), fetch, log=lambda *_: None) == 0  # remembered as done


def test_feed_archive_skips_a_bad_page_and_keeps_the_source_name(tmp_path, monkeypatch):
    from datetime import date
    from aipulse import backfill
    import aipulse.collect as col
    monkeypatch.setattr(col.time, "sleep", lambda s: None)
    monkeypatch.setattr(backfill.time, "sleep", lambda s: None)
    good = lambda t, d: (f"<rss><channel><item><title>AI story {t}</title><link>https://e.com/{t}</link>"
                         f"<description>An AI model story number {t} with enough words.</description>"
                         f"<pubDate>{d}</pubDate></item></channel></rss>").encode()
    pages = {1: good("a", "Mon, 01 Sep 2025 10:00:00 GMT"), 2: b"<rss><channel><item>broken",
             3: good("c", "Mon, 01 Jan 2024 10:00:00 GMT")}
    def fetch(url):
        n = int(url.rsplit("paged=", 1)[1]) if "paged=" in url else 1
        if n not in pages:
            raise __import__("urllib.error").error.HTTPError(url, 404, "Not Found", {}, None)
        return pages[n]
    monkeypatch.setattr(backfill, "SOURCES", [{"name": "Blog", "url": "https://e.com/feed/", "category": "news",
                                               "ai_only": True, "paged": True}])
    conn = store.connect(tmp_path / "t.db")
    assert backfill.feed_archives(conn, date(2023, 1, 1), fetch, log=lambda *_: None) == 2  # page 2 skipped
    assert {r[0] for r in conn.execute("SELECT source FROM items")} == {"Blog"}  # not "Blog page 3"


def test_machine_translation_is_tidied_and_used_for_the_card_title(tmp_path):
    from aipulse import bills, translate
    assert translate.tidy("It▁amends Law No.▁8,069 and gives other measures.") ==         "Amends Law No. 8,069 and makes other provisions."
    assert translate.tidy("It has on the use of artificial intelligence.") == "Provides for the use of artificial intelligence."
    conn = store.connect(tmp_path / "t.db")
    translate.connect(conn)
    pt = "Dispõe sobre o uso da inteligência artificial."
    conn.execute("INSERT INTO translations VALUES (?, 'pt', ?)", (translate._key("pt", pt), "Provides for the use of AI."))
    bill = {"key": "BR-PL-1-2026", "jurisdiction": "BR", "number": "PL 1/2026", "title": pt, "url": "https://e.br/1",
            "source": "Câmara dos Deputados", "lang": "pt",
            "history": [{"date": "2026-01-05", "stage": "introduced", "text": ""}]}
    bills.connect_tables(conn)
    bills.upsert(conn, bill)
    title, summary = conn.execute("SELECT title, summary FROM items").fetchone()
    assert title == "PL 1/2026: Provides for the use of AI." and "Machine-translated from Portuguese" in summary
    assert translate.english(conn, "pt", ["Texto novo sem tradução."]) == {}  # no model in tests: left as is


def test_bills_with_similar_titles_keep_their_own_cards(tmp_path):
    from aipulse import bills, cluster
    conn = store.connect(tmp_path / "t.db")
    bills.connect_tables(conn)
    for key, n, title in (("US-119-s-1", "S. 1", "A bill to establish the Department of Artificial Intelligence"),
                          ("US-119-hr-2", "H.R. 2", "To establish the Department of Artificial Intelligence and for other purposes")):
        bills.upsert(conn, {"key": key, "jurisdiction": "US", "number": n, "title": title,
                            "url": f"https://congress.gov/{key}", "source": "congress.gov",
                            "history": [{"date": "2026-09-01", "stage": "introduced", "text": ""}]})
    conn.commit()
    cluster.assign(conn, days=None)
    assert conn.execute("SELECT COUNT(DISTINCT cluster) FROM items").fetchone()[0] == 2


def test_reclassify_keeps_the_source_default_place(tmp_path):
    from aipulse import collect
    conn = store.connect(tmp_path / "t.db")
    store.insert(conn, {"title": "Basic Act on AI passed at the National Assembly", "summary": "", "url": "https://k.kr/1",
                        "source": "Ministry of Science and ICT (Korea)", "category": "regulation", "action": "law",
                        "date": "2024-12-26", "jurisdictions": ["KR"], "tags": [], "authors": []})
    conn.commit()
    collect.reclassify(conn)
    row = conn.execute("SELECT category, jurisdictions FROM items").fetchone()
    assert tuple(row) == ("regulation", "KR")


def test_dinum_news_list():
    from aipulse import feeds
    listing = ('<h3 class="fr-card__title"><a href="/actualites/pacte-numerique-ia/">Le Pacte &quot;Numérique et IA&quot;</a>'
               '</h3><div class="fr-card__desc">Signé le 10 septembre 2026, le Pacte…</div>'
               '<p class="fr-card__detail">Publié le mardi 1er octobre 2026</p>').encode()
    [e] = feeds.parse_dinum(listing)
    assert (e["url"], e["title"], e["published"].date().isoformat()) == (
        "https://www.numerique.gouv.fr/actualites/pacte-numerique-ia/", 'Le Pacte "Numérique et IA"', "2026-10-01")
    assert e["summary"] == "Signé le 10 septembre 2026, le Pacte"


def test_norwegian_ai_proposals_from_the_storting(tmp_path, monkeypatch):
    import json
    from aipulse import bills, translate
    monkeypatch.setattr(bills.time, "sleep", lambda s: None)
    monkeypatch.setattr(translate, "english", lambda conn, lang, texts: {})  # no model in tests
    case = lambda title, ref: {"id": hash(title) % 1000, "korttittel": title, "tittel": title, "henvisning": ref,
                               "forslagstiller_liste": [{"fornavn": "A", "foedselsdato": "/Date(0)/"}]}
    steps = lambda *days: {"saksgang_steg_liste": [{"saksgang_hendelse_liste": [
        {"id": "FREMSATT" if i == 0 else "X", "dato": f"{d} 00:00:00"} for i, d in enumerate(days)]}]}
    cases = [case("Representantforslag om å forhindre juks med kunstig intelligens i skolen", "Dokument 8:241 S (2025-2026), Innst. 268 S"),
             case("Representantforslag om KI-briller", "Dokument 8:8 S (2026-2027)"),
             case("Riksrevisjonens undersøkelse av kunstig intelligens i staten", "Dokument 3:18 (2023-2024)"),
             case("Representantforslag om ferjer", "Dokument 8:9 S (2026-2027)")]
    details = {cases[0]["id"]: {"saksgang": steps("26.03.2026", "19.05.2026"), "ferdigbehandlet": True,
                                "kortvedtak": "Stortinget vedtok å be regjeringen sørge for tiltak."},
               cases[1]["id"]: {"saksgang": steps("05.10.2026", "01.01.0001"), "ferdigbehandlet": False}}
    def fetch(url):
        if "sesjoner" in url:
            return json.dumps({"innevaerende_sesjon": {"id": "2026-2027"},
                               "sesjoner_liste": [{"id": "2027-2028"}, {"id": "2026-2027"}]}).encode()
        if "saker?" in url:
            return json.dumps({"saker_liste": cases}).encode()
        return json.dumps(details[int(url.rsplit("=", 2)[1].split("&")[0])]).encode()
    conn = store.connect(tmp_path / "t.db")
    assert bills.sync_norway(conn, fetch, log=lambda *_: None) == 2  # AI proposals only: not the audit report, not ferries
    adopted = conn.execute("SELECT number, stage, stage_date FROM bills WHERE key = ?", (f"NO-{cases[0]['id']}",)).fetchone()
    assert tuple(adopted) == ("Dokument 8:241 S (2025-2026)", "passed_legislature", "2026-05-19")
    assert conn.execute("SELECT stage FROM bills WHERE key = ?", (f"NO-{cases[1]['id']}",)).fetchone()[0] == "introduced"
    assert not conn.execute("SELECT 1 FROM items WHERE summary LIKE '%A %' OR title LIKE '%Date(%'").fetchone()  # no people
    assert translate.AFTER["nb"][0][0].sub("AI", "a ban on KIC glasses") == "a ban on AI glasses"


def test_fetch_trusts_bundled_intermediates_only_up_to_a_root():
    from aipulse import feeds
    assert feeds.INTERMEDIATES.exists() and feeds.TLS.verify_mode == __import__("ssl").CERT_REQUIRED


def test_paper_summaries_say_what_the_paper_covers():
    from aipulse import brief
    abstract = ("What is an agent? What constitutes agency? With the rise of LLM systems marketed as ``coding agents'', "
                "it has become essential to clarify where automation ends. In this paper, we survey the current "
                "landscape of AI agents and analyze their architectures along five dimensions. We find that none are agentive.")
    assert brief.paper_summary(abstract) == ("Surveys the current landscape of AI agents and analyze their architectures "
                                             "along five dimensions. We find that none are agentive.")
    assert brief.paper_summary("To leverage agents for robots, this work introduces RAPID, which writes robot programs "
                               "from one demonstration.").startswith("Introduces RAPID, which writes")
    assert brief.paper_summary("Models are trained with $\\mathcal{L}_2$ loss. The method is fast and simple.") == \
        "Models are trained with L_2 loss."  # no contribution sentence: the first, with LaTeX removed


def test_stored_papers_are_resummarized_from_arxiv(tmp_path):
    from aipulse import collect
    conn = store.connect(tmp_path / "t.db")
    store.insert(conn, {"title": "RAPID", "summary": "Coding agents have demonstrated enormous success.",
                        "url": "https://arxiv.org/abs/2609.00001v1", "source": "arXiv", "category": "research",
                        "date": "2026-09-01", "tags": [], "authors": []})
    conn.commit()
    atom = (b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2609.00001v2</id>'
            b'<link href="http://arxiv.org/abs/2609.00001v2"/><title>RAPID</title><summary>Coding agents have '
            b'demonstrated enormous success. We present RAPID, which writes robot programs from one video.</summary>'
            b'<updated>2026-09-01T00:00:00Z</updated></entry></feed>')
    asked = []
    assert collect.resummarize_papers(conn, lambda u: (asked.append(u), atom)[1], log=lambda *_: None) == 1
    assert "id_list=2609.00001" in asked[0]
    assert conn.execute("SELECT summary FROM items").fetchone()[0].startswith("Presents RAPID, which writes")
    assert collect.resummarize_papers(conn, lambda u: atom, log=lambda *_: None) == 0  # done once


def test_news_summary_is_the_lede_in_full():
    from aipulse import brief
    lede = ("Copado Inc., a low-code DevOps solution provider for Salesforce, today announced it's extending its "
            "Agentia platform with Headless, bringing it directly into developer tools and operational workflows.")
    text = lede + " Agentia is Copado's AI-powered AgentOps platform that allows developers to build agents."
    assert brief.clean_summary(text, "Copado extends Agentia", "SiliconANGLE") == lede  # one full sentence
    short = "OpenAI paused training its models. The company cited safety incidents involving its agents."
    assert brief.clean_summary(short, "OpenAI pauses", "X") == short  # a very short lede gets the next sentence
    long = "Word " * 30 + "and then, " + "more " * 40 + "end."
    out = brief.clean_summary(long, "t", "X")
    assert len(out) <= brief.MAX_CHARS + 1 and out.endswith("…") and not out.endswith(" …")


def test_a_dropped_source_leaves_nothing_behind(tmp_path):
    from aipulse import bills
    from aipulse.collect import purge_dropped
    conn = store.connect(tmp_path / "t.db")
    bills.connect_tables(conn)
    bill = {"key": "CA-45-1-C-277", "jurisdiction": "CA", "number": "C-277", "title": "An Act to regulate deepfakes",
            "url": "https://www.parl.ca/legisinfo/en/bill/45-1/c-277", "source": "Parliament of Canada",
            "history": [{"date": "2026-05-01", "stage": "introduced", "text": "First reading"}]}
    bills.upsert(conn, bill)
    store.insert(conn, {"id": "k1", "source": "Canada Gazette", "category": "regulation", "title": "Kept",
                        "summary": "", "url": "https://gazette.gc.ca/k1", "date": "2026-05-01"})
    assert purge_dropped(conn, log=lambda *_: None) >= 1
    assert conn.execute("SELECT count(*) FROM bills").fetchone()[0] == 0
    assert [r[0] for r in conn.execute("SELECT source FROM items")] == ["Canada Gazette"]  # other Canadian sources stay
    assert purge_dropped(conn, log=lambda *_: None) == 0


def test_article_lead_skips_menus_bylines_and_contents():
    from aipulse import feeds
    page = ('<header><p>Research blog home and all the other sections of this site you can visit.</p></header><h1>Title</h1>'
            '<nav><p>Contents: How it works, Results, Limitations of this approach and how to use the model.</p></nav>'
            '<p class="[&>:last-child]:mb-0">Upvote 33 +27 Jane Doe Follow Lab and more people who wrote the post.</p>'
            '<p>Jane Doe, Research Scientist, Google Research</p>'
            '<p>Today, we release an experimental draft model for our vision-language model, with faster inference.</p>')
    assert feeds.article_lead(page.encode()).startswith("Today, we release an experimental draft model")


def test_same_company_and_sum_is_one_story():
    from aipulse import cluster
    item = lambda i, title, src: {"id": f"s{i}", "title": title, "summary": "", "url": f"https://ex.com/{i}",
                                  "source": src, "category": "news", "date": "2026-10-09"}
    a = item(1, "The maker of non-text AI model Jev valued at $7.5B just weeks after launch", "TechCrunch AI")
    b = item(2, "Jev creator TypeSafe closes $870M round at $7.5B valuation", "SiliconANGLE AI")
    c = item(3, "Jev creator TypeSafe signs $7.5B chip deal", "Other")
    assert cluster._sums(b["title"]) == {("$", 870_000_000), ("$", 7_500_000_000)}
    assert cluster._sums("Anthropic lost $8 billion last year") == cluster._sums("reveals $8B operating loss")
    assert cluster._same_sum(a, b) and cluster._same_sum(b, c)
    assert not cluster._same_sum(a, item(4, "Mistral raises $7.5B", "Other"))  # another company
    assert [len(g) for g in cluster.group([a, b])] == [2]


def test_translation_note_and_next_day_names():
    from aipulse import cluster
    note = " Machine-translated from Spanish; the original is linked."
    item = lambda i, title, summary, day, src: {"id": f"t{i}", "title": title, "summary": summary, "url": f"https://ex.com/{i}",
                                                "source": src, "category": "news", "date": day}
    # our own note on two translations isn't something the stories share
    a = item(1, "Google Cloud presents its agent Gemini, an AI partner for companies", "Gemini agent acts proactively." + note,
             "2026-10-09", "DPL News")
    b = item(2, "The open web was designed for humans", "Wikipedia has been an open website for 25 years." + note,
             "2026-10-10", "Xataka")
    assert "spanish" not in cluster.tokens(a) and [len(g) for g in cluster.group([a, b])] == [1, 1]
    # the next day, two rare names in common (Gemini, Cloud) are one story; one alone (Muse) is not
    c = item(3, "Google Cloud introduces Gemini agent to change enterprise work", "", "2026-10-08", "SiliconANGLE AI")
    idf = {"gemini": 3.9, "cloud": 3.5, "agent": 2.5, "muse": 4.0}
    assert cluster._anchored(a, c, idf, 2)
    m1 = item(4, "Meta's Muse agent is outpacing ChatGPT's early mobile launch", "", "2026-09-21", "TechCrunch AI")
    m2 = item(5, "Meta Tests Muse AI Agent Calls Made By Humans", "", "2026-09-22", "404 Media")
    assert cluster._anchored(m1, m2, idf) and not cluster._anchored(m1, m2, idf, 2)


def _xlsx(sheets: dict[str, list[list[str]]]) -> bytes:
    """A minimal .xlsx (inline strings) with the given sheets' rows, first row the header."""
    import io, zipfile
    from xml.sax.saxutils import escape
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        names = list(sheets)
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                   + "".join(f'<sheet name="{n}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, 1)) + "</sheets></workbook>")
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   + "".join(f'<Relationship Id="rId{i}" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(names) + 1)) + "</Relationships>")
        for i, n in enumerate(names, 1):
            rows = "".join(f'<row r="{r}">' + "".join(f'<c r="{chr(65 + k)}{r}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
                                                      for k, v in enumerate(row)) + "</row>" for r, row in enumerate(sheets[n], 1))
            z.writestr(f"xl/worksheets/sheet{i}.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                       f"<sheetData>{rows}</sheetData></worksheet>")
    return buf.getvalue()


def test_ai_incidents_one_card_each_under_industry(tmp_path):
    # One card per incident since 2023 from the AI Incident Database (its editors' title, description and date),
    # labelled AI-incident, always under Industry. Our stories are labelled only when the database lists that
    # very article; reports it hasn't assigned to an incident are ignored.
    from aipulse import cluster, incidents
    export = "https://pub-x.r2.dev/AIID_Excel_Export-20260921.xlsx"
    xlsx = _xlsx({
        "Incidents": [["AI Incident Database - Incidents"], ["INCIDENT IDENTITY", "COVERAGE", "RISK CLASSIFICATION"], ["Incident ID", "date", "title", "description", "Country Code"],
                      ["1714", "46283", "Z.ai's ZCode Uploaded Developers' Code to Alibaba Cloud", "Developers reported uploads.", ""],
                      ["1600", "2026-05-02", "Deepfake scam in Mumbai costs retiree savings", "A retiree in India lost money.", "IN"],
                      ["12", "2019-03-01", "Old incident before 2023", "Too old.", "US"]],
        "Reports": [["Report Number", "Title", "URL", "Is Incident Report"],
                    ["9001", "Mumbai deepfake scam", "https://example-news.com/mumbai-scam", "1"],
                    ["9002", "Some issue", "https://example-news.com/issue", "0"]]})
    feed = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>AIID</title>
<item><title>China's Z.ai disables features</title><description>Text (https://incidentdatabase.ai/cite/1714#8006)</description>
<link>https://www.reuters.com/zai</link><pubDate>Sun, 27 Sep 2026 00:00:00 GMT</pubDate></item>
<item><title>New rogue agent attack</title><description>Text (https://incidentdatabase.ai/cite/1720#8010)</description>
<link>https://www.nytimes.com/rogue</link><pubDate>Sun, 27 Sep 2026 00:00:00 GMT</pubDate></item>
<item><title>Unassigned report</title><description>Text (report_number: 7999)</description>
<link>https://example-news.com/unassigned</link><pubDate>Sun, 27 Sep 2026 00:00:00 GMT</pubDate></item>
</channel></rss>"""
    page = ('<meta property="og:title" content="Incident 1720: OpenAI Agents Reportedly Attacked Websites"/>'
            '<meta property="og:description" content="Agents attacked sites."/><div>Incident Date</div><div>2026-09-24</div>').encode()
    pages = {incidents.SNAPSHOTS: f'<a href="{export}">x</a>'.encode(), export: xlsx, incidents.FEED: feed,
             incidents.incident_url("1720") + "/": page}
    conn = store.connect(tmp_path / "t.db")
    for url, title, cat in [("https://example-news.com/mumbai-scam", "Mumbai deepfake scam hits retiree", "policy"),
                            ("https://reuters.com/zai", "Z.ai disables coding assistant uploads", "tool"),
                            ("https://example-news.com/issue", "An issue report", "news"),
                            ("https://example-news.com/unassigned", "Unassigned report", "news")]:
        store.insert(conn, {"title": title, "summary": "", "url": url, "source": "Outlet " + url[-4:], "category": cat, "date": "2026-09-27"})
    assert incidents.sync(conn, fetcher=lambda u: pages[u], log=lambda *_: None) == 3  # 1714, 1600, 1720; not 12
    assert incidents.sync(conn, fetcher=lambda u: pages[u], log=lambda *_: None) == 0  # the export is read once
    cards = {i["url"]: i for i in store.query(conn, None, limit=100)}
    zai = cards[incidents.incident_url("1714")]
    assert (zai["category"], zai["action"], zai["date"], zai["source"]) == ("news", "incident", "2026-09-18", "AI Incident Database")
    assert zai["summary"] == "Developers reported uploads."
    assert "India" in cards[incidents.incident_url("1600")]["tags"]
    assert cards[incidents.incident_url("1720")]["title"] == "OpenAI Agents Reportedly Attacked Websites"
    assert incidents.incident_url("12") not in cards
    # Our stories: labelled only when listed as reports of an incident, and then under Industry.
    assert [cards[u]["action"] for u in ("https://example-news.com/mumbai-scam", "https://reuters.com/zai",
                                         "https://example-news.com/issue", "https://example-news.com/unassigned")] == ["incident", "incident", "", ""]
    assert cards["https://example-news.com/mumbai-scam"]["category"] == "news" and cards["https://reuters.com/zai"]["category"] == "news"
    assert reclassify(conn) == 0  # never re-sorted out of Industry
    cluster.assign(conn, days=None)
    news, _ = store.cards(conn, "news", limit=100)
    zcard = next(c for c in news if c["url"] == incidents.incident_url("1714"))
    assert zcard["kind"] == "incident" and [o["url"] for o in zcard["also"]] == ["https://reuters.com/zai"]  # same incident
    assert {c["kind"] for c in news if c["url"].startswith("https://incidentdatabase.ai")} == {"incident"}
    assert next(c for c in news if c["url"] == "https://example-news.com/mumbai-scam")["kind"] == "incident"
    assert next(c for c in news if c["url"] == "https://example-news.com/issue")["kind"] != "incident"
    rel = {"category": "tool", "action": ""}
    assert cluster._release_and_incident(rel, {"category": "news", "action": "incident"})


def test_anthropic_news_page_and_its_launches():
    from aipulse import collect as col
    page = b'''<a href="/claude-sonnet-5-5" class="x"><h2 class="t">Introducing Claude Sonnet 5.5</h2><div><div>
      <span>Announcements</span><time class="d">Sep 28, 2026</time></div><p class="[&>:last-child]:mb-0">A clear upgrade
      over Sonnet 5.</p></div></a>
      <a href="/news/claude-discovers-novel-enzyme-system"><div><time>Sep 23, 2026</time><span>Science</span></div>
      <span> Claude discovers a novel enzyme system</span></a>
      <a href="/news/improving-alignment-security-efforts"><div><time>Aug 31, 2026</time><span>Announcements</span></div>
      <span>Improving our alignment and security efforts</span></a>
      <a href="/claude-corps">Claude Corps</a><a href="/claude-sonnet-5-5">Try it</a>'''
    posts = feeds.parse_anthropic(page)
    assert [(p["title"], p["url"][25:], p["published"].date().isoformat()) for p in posts] == [
        ("Introducing Claude Sonnet 5.5", "/claude-sonnet-5-5", "2026-09-28"),
        ("Claude discovers a novel enzyme system", "/news/claude-discovers-novel-enzyme-system", "2026-09-23"),
        ("Improving our alignment and security efforts", "/news/improving-alignment-security-efforts", "2026-08-31")]
    assert posts[0]["summary"] == "A clear upgrade over Sonnet 5." and posts[1]["summary"] == ""  # undated links skipped
    # Anthropic News was dropped (7 Oct 2026 terms audit); its old settings keep the reader tested.
    src = {"name": "Anthropic News", "category": "tool", "launch_pages": r"^https://www\.anthropic\.com/(?!news/)"}
    # A launch has its own page; other posts are judged by the headline, not by launch words in their description.
    assert col.blog_category(src, posts[0]["title"], posts[0]["summary"], posts[0]["url"]) == "tool"
    assert col.blog_category(src, posts[1]["title"], "We're introducing a new life sciences research group", posts[1]["url"]) == "news"
    assert col.blog_category(src, posts[2]["title"], "Claude models gained unauthorized access to systems", posts[2]["url"]) == "news"
    other = {"name": "Blog", "category": "tool"}
    assert col.blog_category(other, "Introducing Gemma 4", "", "https://ex.com/gemma-4") == "tool"  # other blogs unchanged


def test_labs_without_a_feed_are_read_from_their_news_page(tmp_path):
    from datetime import datetime, timezone
    from aipulse import collect as col
    conn = store.connect(tmp_path / "t.db")
    listing = {"v": b'<a href="/blog/kimi-k3">K3</a><a href="/blog/perception-bench">PB</a><a href="/about">x</a>'}
    pages = {"https://lab.test/blog/kimi-k3": b'<meta property="og:title" content="Kimi K3 | Moonshot AI">'
                                              b'<meta property="og:description" content="Kimi K3 is an open 3T-class model.">'
                                              b'<meta property="article:published_time" content="2026-09-27T08:00:00Z">',
             "https://lab.test/blog/new-agent": b"<title>Introducing Kimi Agent 2 - Moonshot</title>"
                                                b'<meta name="description" content="Today we launch Kimi Agent 2.">'}
    fetched = []
    def fetch(url):
        fetched.append(url)
        if url == "https://lab.test/news":
            return listing["v"]
        if url not in pages:
            raise OSError("HTTP Error 400")
        return pages[url]
    src = {"name": "Lab", "url": "https://lab.test/news", "format": "page_list", "link": r"^https://lab\.test/blog/[a-z0-9-]+$",
           "category": "tool", "pause": 0}
    assert col.page_list_entries(conn, src, fetch) == [] and fetched == ["https://lab.test/news"]  # first read: remembered only
    listing["v"] = b'<a href="/blog/new-agent">N</a><a href="/blog/gone">G</a>' + listing["v"]
    got = col.page_list_entries(conn, src, fetch)
    assert [(e["title"], e["summary"]) for e in got] == [("Introducing Kimi Agent 2", "Today we launch Kimi Agent 2.")]
    assert got[0]["published"].date() == datetime.now(timezone.utc).date()  # no date on the page: the day it's first seen
    assert "https://lab.test/blog/kimi-k3" not in fetched  # an already-listed post isn't read
    fetched.clear()
    assert col.page_list_entries(conn, src, fetch) == [] and fetched == ["https://lab.test/news"]  # nothing read twice
    meta = feeds.page_meta(pages["https://lab.test/blog/kimi-k3"])
    assert meta["title"] == "Kimi K3" and meta["published"].isoformat() == "2026-09-27T08:00:00+00:00"
    assert feeds.listed_links(b"<loc>https://lab.test/blog/a</loc><loc> https://lab.test/c </loc>", "https://lab.test/",
                              r"/blog/") == ["https://lab.test/blog/a"]


def test_lab_paper_pages_give_the_papers_title_and_abstract():
    # IBM's preview title adds the venue, Google's preview text is the site's slogan: a paper page's citation title
    # and "Abstract" section are used instead (sources.py "abstract")
    page = (b'<meta property="og:title" content="SPARC: Separating Perception for ICML 2026">'
            b'<meta name="citation_title" content="SPARC: Separating Perception" data-next-head=""/>'
            b'<meta property="og:description" content="Our teams advance the state of the art.">'
            b'<meta name="citation_publication_date" content="2026/07/06">'
            b'<section><h2 id="abstract">Abstract</h2><div><p>Test-time scaling remains <b>brittle</b> for VLMs.</p></div>'
            b'</section><h2>Related</h2><p>Other papers</p>')
    meta = feeds.paper_meta(page)
    assert (meta["title"], meta["summary"]) == ("SPARC: Separating Perception", "Test-time scaling remains brittle for VLMs.")
    assert meta["published"] is None  # the conference's date, not the day it was posted
    assert feeds.paper_meta(b'<meta property="og:title" content="A paper"><meta name="description" content="Its abstract.">'
                            ) == {"title": "A paper", "summary": "Its abstract.", "published": None}


def test_every_story_is_shown_in_english(monkeypatch, tmp_path):
    from aipulse import collect as col, translate
    assert translate.detect("Noticias Telemundo: Las empresas de telecomunicaciones no han protegido los datos") == "es"
    assert translate.detect("Nemotron-Personas-Japan: ソブリン AI のための合成データセット") == "ja"
    assert translate.detect("Ley de IA: el Senado aprueba la regulación") == "es"
    assert translate.detect("L'intelligence artificielle est une priorité pour le gouvernement") == "fr"
    assert translate.detect("삼성전자, 새로운 AI 칩 공개") == "ko" and translate.detect("Новый закон об ИИ принят") == "ru"
    # English stays English: model names, a name in Chinese characters, words shared with other languages
    for english in ("Addendum to OpenAI o3 and o4-mini system card", "Lai marks Teachers' Day, highlights AI plan (賴清德)",
                    "Con Instruction: Universal Jailbreaking of Multimodal Large Language Models",
                    "Microsoft's AI rulebook: readable thinking, no inner life, and definitely no sex"):
        assert translate.detect(english) is None, english
    conn = store.connect(tmp_path / "t.db")
    made = {"Ley de IA: el Senado aprueba la regulación": "AI Law: The Senate approves the regulation"}
    monkeypatch.setattr(translate, "english", lambda conn, lang, texts: {t: made[t] for t in texts if t in made})
    assert col.in_english(conn, "Ley de IA: el Senado aprueba la regulación", "", "https://ex.es/ley") == (
        "AI Law: The Senate approves the regulation", "Machine-translated from Spanish; the original is linked.",
        "https://ex.es/ley")
    # A headline too short to show its language is translated with its summary, unless it reads as English
    made.update({"China restringe chatbots que simulam namoros": "China restricts chatbots that simulate dating",
                 "As regras exigem avisos aos usuários e proíbem parceiros virtuais para menores, em uma tentativa de conter a dependência":
                 "Chinese rules require user notices and ban virtual partners for minors"})
    assert col.in_english(conn, "China restringe chatbots que simulam namoros",
                          "As regras exigem avisos aos usuários e proíbem parceiros virtuais para menores, em uma tentativa de conter a dependência")[:2] == (
        "China restricts chatbots that simulate dating",
        "Chinese rules require user notices and ban virtual partners for minors Machine-translated from Portuguese; the original is linked.")
    assert translate.reads_english("OpenAI fires 3 safety researchers in a dispute over the risks")
    assert not translate.reads_english("China restringe chatbots que simulam namoros")
    assert not translate.reads_english("Nvidia contrata a un exfiscal para investigar acusaciones contra Jensen Huang")
    # The publisher's own English version wins, and the card links to it ("-ja" dropped from the address).
    pages = {"https://huggingface.co/blog/nvidia/nemotron-personas-japan":
             b'<meta property="og:title" content="Nemotron-Personas-Japan: Synthesized Data for Sovereign AI">'
             b'<meta property="og:description" content="Synthetic personas for building AI in Japan.">'}
    def fetch(url):
        if url not in pages:
            raise OSError("404")
        return pages[url]
    assert col.in_english(conn, "Nemotron-Personas-Japan: ソブリン AI のための合成データセット", "",
                          "https://huggingface.co/blog/nvidia/nemotron-personas-japan-ja", "Hugging Face Blog", fetch) == (
        "Nemotron-Personas-Japan: Synthesized Data for Sovereign AI", "Synthetic personas for building AI in Japan.",
        "https://huggingface.co/blog/nvidia/nemotron-personas-japan")
    # No English version, no translation: kept, with an English headline and line, tagged "Translate and read".
    title, summary, url = col.in_english(conn, "Nemotron-Personas-Japan: ソブリン AI のための合成データセット", "",
                                         "https://ex.jp/x", "Hugging Face Blog", fetch)
    assert title == "Nemotron-Personas-Japan (in Japanese)" and url == "https://ex.jp/x"
    assert summary == "A Japanese-language story from Hugging Face Blog. Translate and read: the original is in Japanese."
    assert classify.tags_for(title, summary)[0] == "Translate and read"
    assert col.in_english(conn, "삼성전자 새로운 칩", "", "", "Yonhap")[0] == "A Korean-language story from Yonhap"
    assert col.in_english(conn, "Next Wave: Can African banks pick up the baton?",
                          "Cet article est aussi disponible en français First published 17 Aug")[:2] == (
        "Next Wave: Can African banks pick up the baton?", "First published 17 Aug")
    assert col.in_english(conn, "TechCabal Daily", "In partnership with Lire en Français اقرأ هذا باللغة العربية Good morning!")[:2] == (
        "TechCabal Daily", "Good morning!")
    page = (Path(__file__).resolve().parent.parent / "templates" / "index.html").read_text(encoding="utf-8")
    assert "Read the original in English" in page and "translate.google.com/translate?sl=auto&tl=en&u=" in page
    assert '"Translate and read"' in page
    assert classify.tags_for("AI Law", "Machine-translated from Spanish; the original is linked.") == classify.tags_for("AI Law", "")


def test_mojibake_is_repaired_and_real_accents_are_kept(tmp_path):
    from aipulse import feeds, store
    from aipulse.collect import reclassify
    assert feeds.unmangle("Enhance PeopleÃ¢Â\x80Â\x99s Ability") == "Enhance People’s Ability"  # decoded twice
    assert feeds.unmangle("Ministerâ€™s plan") == "Minister’s plan"
    assert feeds.unmangle("CafÃ© rÃ©sumÃ©") == "Café résumé"
    for fine in ("Café résumé naïve", "São Paulo — AI", "Zürich “quotes”", "東京 AI", "£5bn", "Ça va", "¿Qué?"):
        assert feeds.unmangle(fine) == fine
    assert feeds.clean_text("<b>Peopleâ€™s</b> AI") == "People’s AI"
    conn = store.connect(str(tmp_path / "t.db"))
    store.insert(conn, {"id": "m1", "source": "Bernama", "category": "news", "title": "Boost NationÃ¢Â\x80Â\x99s AI",
                        "summary": "", "url": "https://ex.com/m1", "date": "2026-09-29"})
    reclassify(conn)
    assert conn.execute("SELECT title FROM items WHERE url = 'https://ex.com/m1'").fetchone()[0] == "Boost Nation’s AI"


def test_a_capped_source_keeps_only_its_newest_stories(tmp_path, monkeypatch):
    from aipulse import collect
    monkeypatch.setattr(collect, "SOURCES", [{"name": "ScienceDaily", "url": "https://www.sciencedaily.com/rss",
                                              "category": "news", "keep_max": 2}])
    conn = store.connect(tmp_path / "t.db")
    for n in range(1, 5):
        store.insert(conn, {"title": f"AI story {n}", "summary": "", "url": f"https://www.sciencedaily.com/{n}",
                            "source": "ScienceDaily", "category": "news", "date": f"2026-09-0{n}", "tags": [], "authors": []})
    store.insert(conn, {"title": "Other", "summary": "", "url": "https://ex.com/1", "source": "MIT News",
                        "category": "news", "date": "2026-09-01", "tags": [], "authors": []})
    collect.purge_dropped(conn, log=lambda *_: None)
    assert sorted(r[0] for r in conn.execute("SELECT url FROM items")) == [
        "https://ex.com/1", "https://www.sciencedaily.com/3", "https://www.sciencedaily.com/4"]


def test_a_microsoft_research_blog_post_on_its_own_paper_gives_way_to_the_paper(tmp_path, monkeypatch):
    from aipulse import collect
    from aipulse.sources import SOURCES
    monkeypatch.setattr(collect, "SOURCES", [s for s in SOURCES if s["name"] == "Microsoft Research"])
    conn = store.connect(tmp_path / "t.db")
    base = "https://www.microsoft.com/en-us/research/"
    for source, url, title, category in (
            ("Microsoft Research papers", base + "publication/lazare/", "Lazare veni foras: Backdoor AI Agents", "research"),
            ("Microsoft Research", base + "blog/lazare/", "Lazare, veni foras: Backdoor AI Agents", "news"),
            ("Microsoft Research", base + "blog/other/", "A post about something else", "news")):
        store.insert(conn, {"title": title, "summary": "", "url": url, "source": source, "category": category,
                            "date": "2026-11-10", "tags": [], "authors": []})
    collect.purge_dropped(conn, log=lambda *_: None)
    assert sorted(r[0] for r in conn.execute("SELECT url FROM items")) == [base + "blog/other/", base + "publication/lazare/"]


def test_hugging_face_trending_adds_verified_organisations_new_models_not_copies(monkeypatch):
    import json, urllib.error
    from datetime import datetime, timezone
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    m = lambda id, likes=500, created="2026-09-30T00:00:00Z", tags=(), task="image-text-to-text": {
        "id": id, "likes": likes, "createdAt": created, "tags": list(tags), "pipeline_tag": task}
    models = [m("Cloudflare/clef", tags=["base_model:finetune:Qwen/Qwen3.8-27B"]),
              m("Cactus-Compute/whistle", 302, task="automatic-speech-recognition"),
              m("Qwen/Qwen3.8-27B", 17000),  # a lab we follow by name (hf_models)
              m("someone/humanizer", 900, tags=["base_model:finetune:google/gemma-4-12B"]),  # a person's upload
              m("Cloudflare/clef-GGUF", 900), m("Cloudflare/clef-uncensored", 900),  # copies
              m("Cloudflare/clef-q", 900, tags=["base_model:quantized:Cloudflare/clef"]),
              m("Cloudflare/old", 900, created="2026-01-01T00:00:00Z"), m("Cloudflare/small", 150)]
    orgs = {"Cloudflare": {"fullname": "Cloudflare", "isVerified": True},
            "Cactus-Compute": {"fullname": "Cactus Compute, Inc.", "isVerified": True}}

    def fetcher(url):
        name = url.split("/organizations/")[1].split("/")[0]
        if name not in orgs:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        return json.dumps(orgs[name]).encode()
    monkeypatch.setattr(feeds, "_hf_orgs", {})
    entries = feeds.parse_hf_trending(json.dumps(models).encode(), fetcher=fetcher, now=now)
    assert [(e["title"], e["summary"]) for e in entries] == [
        ("Cloudflare publishes clef on Hugging Face", "Vision-language model weights published on Hugging Face, built on Qwen3.8-27B."),
        ("Cactus Compute publishes whistle on Hugging Face", "Speech recognition model weights published on Hugging Face.")]


def test_the_labs_own_model_lists_name_each_model_once():
    import json
    anthropic = {"data": [{"type": "model", "id": "claude-sonnet-4-5-20250929", "display_name": "Claude Sonnet 4.5",
                           "created_at": "2025-09-29T00:00:00Z"}]}
    [a] = feeds.parse_anthropic_models(json.dumps(anthropic).encode())
    assert (a["title"], a["published"].date()) == ("Anthropic releases Claude Sonnet 4.5 in its API", date(2025, 9, 29))
    openai = {"data": [{"id": "gpt-4o", "created": 1715367049, "owned_by": "system"},
                       {"id": "gpt-4o-2024-08-06", "created": 1722814719, "owned_by": "system"},  # a snapshot of gpt-4o
                       {"id": "o1-2024-12-17", "created": 1734326976, "owned_by": "system"},  # only listed dated
                       {"id": "ft:gpt-4o:acme::abc", "created": 1730000000, "owned_by": "user-acme"},
                       {"id": "chatgpt-4o-latest", "created": 1723515131, "owned_by": "system"}]}
    assert [e["title"] for e in feeds.parse_openai_models(json.dumps(openai).encode())] == [
        "OpenAI releases gpt-4o in its API", "OpenAI releases o1-2024-12-17 in its API"]


def test_hacker_news_keeps_recent_ai_threads_only(tmp_path):
    import json
    from aipulse import social
    conn = store.connect(tmp_path / "t.db")
    now = 1_800_000_000
    items = {1: {"id": 1, "type": "story", "title": "OpenAI releases a new model", "url": "https://x.com/a", "score": 300,
                 "descendants": 120, "time": now - 3600},
             2: {"id": 2, "type": "story", "title": "Show HN: my bread recipe", "score": 900, "descendants": 400, "time": now - 60},
             3: {"id": 3, "type": "story", "title": "LLM agents in production", "score": 50, "descendants": 10,
                 "time": now - 5 * 86400},  # too old
             4: {"id": 4, "type": "job", "title": "AI startup hiring", "time": now - 60}}
    def fetcher(url):
        if url.endswith("topstories.json"):
            return json.dumps(list(items)).encode()
        return json.dumps(items[int(url.rsplit("/", 1)[1][:-5])]).encode()
    assert social.payload(conn)["threads"] == []
    assert social.hacker_news(conn, fetcher=fetcher, now=now) == 1
    (t,) = social.payload(conn)["threads"]
    assert t["title"] == "OpenAI releases a new model" and t["hn"] == "https://news.ycombinator.com/item?id=1" and t["comments"] == 120


def test_a_story_is_never_dated_after_the_day_it_was_found(tmp_path):
    conn = store.connect(tmp_path / "d.db")
    later = (date.today() + timedelta(days=40)).isoformat()
    store.insert(conn, {"title": "Industry event in December", "summary": "", "url": "https://x.com/e",
                        "source": "X", "category": "infra", "date": later})
    store.insert(conn, {"title": "Act comes into force", "summary": "", "url": "https://x.com/r",
                        "source": "X", "category": "regulation", "date": later})
    conn.commit()
    got = dict(conn.execute("SELECT category, date FROM items").fetchall())
    assert got["infra"] <= date.today().isoformat() and got["regulation"] == later
    conn.execute("UPDATE items SET date = ? WHERE category = 'infra'", (later,))  # one stored before the rule
    conn.commit()
    assert store.connect(tmp_path / "d.db").execute("SELECT date FROM items WHERE category = 'infra'").fetchone()[0] < later


def test_feed_date_from_time_tag_when_no_date_field():
    from aipulse import feeds
    xml = (b'<rss><channel><item><title>ESMA news</title><link>https://www.esma.europa.eu/a</link>'
           b'<description>&lt;time datetime="2026-10-22T16:51:53+02:00"&gt;22 October 2026&lt;/time&gt;</description>'
           b'</item></channel></rss>')
    (e,) = feeds.parse(xml)
    assert e["published"] and e["published"].isoformat().startswith("2026-10-22")
