import os
import re
import sqlite3
from datetime import date
from pathlib import Path

os.environ["AIPULSE_OFFLINE"] = "1"  # brand logos: cached data only, no network

from aipulse import classify, feeds, store
from aipulse import jurisdictions
from aipulse.collect import apply_regulation, collect, reclassify

FIX = Path(__file__).parent / "fixtures"


def test_parse_rss_and_atom():
    rss = feeds.parse((FIX / "sample_rss.xml").read_bytes())
    atom = feeds.parse((FIX / "sample_atom.xml").read_bytes())
    assert rss[0]["title"] == "OpenAI releases a new open-weight model"
    assert rss[0]["published"] is not None
    assert "<p>" not in rss[0]["summary"]
    assert atom[0]["url"] == "https://example.com/blog/gemini-update"


def test_categorize():
    assert classify.categorize("Senate passes AI Act amendment on frontier models", "") == "policy"
    assert classify.categorize("Mistral launches new open-weight model, available via API", "") == "tool"
    assert classify.categorize("AI startup raises $200M", "", "news") == "news"
    assert classify.is_ai_related("Weather today", "Sunny") is False


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


def test_regulatory_action_and_jurisdiction():
    cases = {
        "Irish DPC fines Meta over AI training data": ("enforcement", ["IE"]),
        "Massachusetts is investigating gambling companies' use of AI": ("investigation", ["US"]),
        "Newsom signs AI companion chatbot bill into law": ("law", ["US"]),
        "South Korea's AI Basic Act takes effect": ("law", ["KR"]),
        "Texas attorney general sues AI company over deceptive claims": ("enforcement", ["US"]),
        "India's MeitY releases AI governance guidelines": ("guidance", ["IN"]),
    }
    for title, expected in cases.items():
        assert (classify.regulatory_action(title), jurisdictions.detect(title)) == expected, title
    assert classify.regulatory_action("OpenAI launches a fine-tuning API") is None
    assert classify.regulatory_action("Regulators move to examine DraftKings' use of AI") is None
    assert classify.regulatory_action("Washington still hasn't passed an AI safety law") != "law"
    assert classify.regulatory_action("EU businesses urge China to adopt comprehensive AI law") != "law"
    assert jurisdictions.detect("New Mexico passes AI law") == ["US"]  # a US state, not Mexico
    assert jurisdictions.detect("Latin America weighs AI rules") == []
    assert jurisdictions.detect('Family dressed in "Lake America" sweatshirts') == []


def test_policy_search_story_about_a_private_person_is_news():
    # A place that only describes a person or business doesn't keep a story under "policy".
    for title in ['The bank executive who used AI to dress her family in "Lake America" sweatshirts is no longer employed',
                  "Michigan CEO loses job after posting AI-made image of her family in 'Lake America' sweaters",
                  "Michigan credit union CEO out after posting AI photo"]:
        assert classify.categorize(title, "", "policy") == "news", title
    assert classify.categorize("Maryland Sets AI Guardrails as States Confront Data Center Boom", "", "policy") == "policy"


def test_policy_needs_action_and_place_to_become_regulation():
    opinion = {"title": "Why AI regulation matters", "summary": "", "category": "policy"}
    apply_regulation(opinion)
    assert opinion["category"] == "policy"
    no_place = {"title": "Senators introduce bill to regulate frontier AI", "summary": "", "category": "policy"}
    apply_regulation(no_place)
    assert no_place["category"] == "policy"
    apply_regulation(no_place, ["US"])  # a source can supply the jurisdiction
    assert (no_place["category"], no_place["action"]) == ("regulation", "proposal")
    # A Google News summary is the headline plus the publisher; the publisher must not add a country.
    gnews = {"title": "Regulator fines chatbot maker over AI claims", "category": "policy",
             "summary": "Regulator fines chatbot maker over AI claims The Times of India"}
    apply_regulation(gnews)
    assert gnews["category"] == "policy"


def test_regulation_searches_keep_only_concrete_actions(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    sources = [{"name": "Fixture", "url": "rss", "category": "regulation"}]
    collect(conn, sources, max_age_days=100000, fetcher=lambda u: (FIX / "sample_rss.xml").read_bytes(),
            log=lambda *_: None)
    assert {i["category"] for i in store.query(conn)} <= {"regulation"}


def test_reclassify_existing_policy_items(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    store.insert(conn, {"title": "Italy's senate approves national AI law", "summary": "", "url": "https://x.com/1",
                        "source": "X", "category": "policy", "date": "2026-09-01"})
    # Enforcement is no longer tracked: a stored fine moves back to policy.
    store.insert(conn, {"title": "Italy's Garante fines AI chatbot maker", "summary": "", "url": "https://x.com/2",
                        "source": "X", "category": "regulation", "date": "2026-09-01", "jurisdictions": ["IT"],
                        "action": "enforcement"})
    assert reclassify(conn) == 2
    [item] = store.query(conn, "regulation")
    assert (item["jurisdictions"], item["action"]) == (["IT"], "law")
    assert [i["title"] for i in store.query(conn, "policy")] == ["Italy's Garante fines AI chatbot maker"]
    assert reclassify(conn) == 0


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


def test_scholar_papers_are_research_not_regulation(tmp_path):
    # A paper by an ethics or law scholar is research, tagged with the scholar and field; the tracker is for
    # proposals and laws. Papers the tracker stored as "expert views" move to Research on reclassify.
    conn = store.connect(tmp_path / "t.db")
    store.insert(conn, {"title": "Agentic Economies for Autonomous Scientific Discovery", "summary": "",
                        "url": "https://arxiv.org/abs/2609.00001", "source": "arXiv", "category": "regulation",
                        "action": "expert", "date": "2026-09-28", "tags": ["Atoosa Kasirzadeh", "Philosophy", "Research"]})
    assert reclassify(conn) == 1
    [paper] = store.query(conn, "research")
    assert paper["action"] in ("", None) and paper["tags"] == ["Atoosa Kasirzadeh", "Philosophy", "Research"]
    assert not store.query(conn, "regulation")
    from aipulse.sources import SOURCES
    assert all(s["category"] == "research" for s in SOURCES if s.get("format") == "arxiv_rss")


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


# Accuracy floors on the hand-labelled stories (python -m aipulse evaluate). Raise them as the rules
# improve so a later change can't quietly make sorting worse.
FLOORS = {"category_accuracy": 0.96, "tracker_precision": 1.0, "tracker_recall": 1.0,
          "action_accuracy": 1.0, "place_accuracy": 1.0}


def test_sorting_rules_meet_accuracy_floors():
    from aipulse.evaluate import evaluate
    report = evaluate()
    assert report["n"] >= 100
    below = {k: round(report[k], 3) for k, floor in FLOORS.items() if report[k] < floor}
    assert not below, f"sorting got worse: {below}"


def test_generated_drafts_do_not_feed_back_into_sorting():
    item = {"title": "US bill seeks AI safety pact with China", "category": "policy",
            "summary": "A proposal in the United States and China, involving safety."}
    apply_regulation(item)
    assert (item["category"], item["jurisdictions"]) == ("regulation", ["US"])


def test_any_country_can_be_a_tag():
    assert classify.tags_for("Japan and Brazil weigh new AI rules for OpenAI", "") == ["OpenAI", "Japan", "Brazil"]
    assert classify.tags_for("EU Commission opens AI consultation", "") == ["European Union"]
    assert "Kenya" in classify.tags_for("Kenya signs AI framework", "")


# Duplicate grouping, scored on hand-labelled events (tests/fixtures/duplicates.json).
def test_duplicate_stories_group_into_one_card():
    from aipulse import cluster
    s = cluster.score()
    # 225 labelled stories (the Sept 25 set added the Copilot, Muse and court duplicates). Grouping favours
    # precision: a wrong "Also reported by" is a visible mistake, a missed one only a repeated headline.
    # Before the same-outlet and headline-name rules: precision 91%, recall 73%, 7 of 15 events on one card.
    assert s["precision"] >= 0.95 and s["recall"] >= 0.75 and s["events_on_one_card"] >= 7, s
    items = __import__("json").loads(cluster.FIXTURE.read_text(encoding="utf-8"))
    cards = cluster.collapse(items)
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


# --- Server-side search and paging ---
def _seed(conn, rows):
    """Insert (title, source, category, extra) rows dated today, then store card grouping."""
    from datetime import date
    from aipulse import cluster
    for n, (title, src, cat, extra) in enumerate(rows):
        store.insert(conn, {"title": title, "summary": extra.get("summary", ""), "url": f"https://x.com/{n}",
                            "source": src, "category": cat, "date": date.today().isoformat(),
                            "tags": extra.get("tags", []), "jurisdictions": extra.get("jurisdictions", []),
                            "action": extra.get("action")})
    conn.commit()
    cluster.assign(conn, days=None)


def test_api_serves_grouped_cards_one_page_at_a_time(tmp_path):
    from aipulse.server import items_payload
    conn = store.connect(tmp_path / "t.db")
    _seed(conn, [("Massachusetts gaming commission probes DraftKings AI practices", "qz.com", "policy", {}),
                 ("Massachusetts Gaming Commission Investigates DraftKings' AI practices", "Geek", "policy", {})]
                + [(t, "Verge", "tool", {}) for t in ["Mistral releases a speech model", "Apple adds AI photo search",
                                                       "Nvidia opens robotics simulator", "Zoom launches meeting agent",
                                                       "Adobe ships video upscaler"]])
    page1 = items_payload(conn, {"per_page": "4"})
    assert page1["total"] == 6 and page1["hasMore"] and len(page1["items"]) == 4
    page2 = items_payload(conn, {"per_page": "4", "page": "2"})
    assert len(page2["items"]) == 2 and not page2["hasMore"]
    ma = [c for c in page1["items"] + page2["items"] if c["category"] == "policy"]
    assert len(ma) == 1 and len(ma[0]["also"]) == 1  # two outlets, one card
    assert page1["counts"] == {"tool": 5, "news": 0, "policy": 1, "research": 0, "regulation": 0, "infra": 0, "all": 6}
    assert page1["stories"] == 7


def test_full_text_search_stems_and_finds_any_outlets_version(tmp_path):
    from aipulse.server import items_payload
    conn = store.connect(tmp_path / "t.db")
    _seed(conn, [("Massachusetts gaming commission probes DraftKings AI practices", "qz.com", "policy", {}),
                 ("Massachusetts Gaming Commission Investigates DraftKings' AI practices", "The Sports Geek",
                  "policy", {}),
                 ("EU lawmakers regulate AI chatbots", "Politico", "policy", {"tags": ["European Union"]}),
                 ("Carissa Véliz on AI and privacy", "El Pais", "policy", {})])
    search = lambda q: [c["title"] for c in items_payload(conn, {"q": q})["items"]]
    assert search("regulation") == ["EU lawmakers regulate AI chatbots"]  # stemmed: regulation ~ regulate
    assert search("sports geek") == search("draftkings")  # matches the card via the other outlet
    assert len(search("draftkings")) == 1
    assert search("veliz") == ["Carissa Véliz on AI and privacy"]  # accents ignored
    assert search("european union") == ["EU lawmakers regulate AI chatbots"]  # tags are searched
    assert search('"unbalanced (quotes') == []  # odd input doesn't break the query


def test_country_filter_includes_eu_wide_rules_for_members(tmp_path):
    from aipulse.server import items_payload
    conn = store.connect(tmp_path / "t.db")
    _seed(conn, [("France adopts national AI law", "Le Monde", "regulation", {"jurisdictions": ["FR"], "action": "law"}),
                 ("EU adopts AI liability rules", "Politico", "regulation", {"jurisdictions": ["EU"], "action": "law"}),
                 ("Texas passes AI bill", "Tribune", "regulation", {"jurisdictions": ["US"], "action": "law"})])
    titles = lambda place: sorted(c["title"] for c in items_payload(conn, {"category": "regulation", "place": place})["items"])
    assert titles("FR") == ["EU adopts AI liability rules", "France adopts national AI law"]
    assert titles("US") == ["Texas passes AI bill"]
    tally = items_payload(conn, {"category": "regulation"})["map"]
    assert tally["cards"] == 3 and tally["national"] == {"FR": 1, "EU": 1, "US": 1} and tally["laws"]["US"] == 1


def test_search_index_follows_edits(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    _seed(conn, [("Old headline about chips", "X", "news", {})])
    [card], _ = store.cards(conn, q="chips")
    store.update_text(conn, card["id"], "New headline about robots", "")
    conn.commit()
    assert store.cards(conn, q="chips")[1] == 0 and store.cards(conn, q="robots")[1] == 1


def test_older_database_gains_search_and_cards(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE items (id TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL, source TEXT NOT NULL,
            category TEXT NOT NULL CHECK (category IN ('tool','news','policy','research','regulation')),
            date TEXT NOT NULL, tags TEXT NOT NULL DEFAULT '', authors TEXT NOT NULL DEFAULT '',
            jurisdictions TEXT NOT NULL DEFAULT '', action TEXT NOT NULL DEFAULT '', added_at TEXT NOT NULL);
        INSERT INTO items VALUES ('a','Kenya drafts AI bill','','https://x.com/a','X','regulation','2026-09-01',
            '','','KE','proposal','2026-09-01T00:00:00');
    """)
    old.commit(); old.close()
    conn = store.connect(path)
    cards, total = store.cards(conn, q="kenya")
    assert total == 1 and cards[0]["cluster"] == "a"


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


def test_command_line_entry_point_starts(tmp_path):
    # The scheduled tasks run `python -m aipulse ...`; a syntax error there would stop every collection.
    import subprocess, sys
    root = Path(__file__).parent.parent
    run = lambda *a: subprocess.run([sys.executable, "-m", "aipulse", "--db", str(tmp_path / "t.db"), *a],
                                    cwd=root, capture_output=True, text=True, timeout=60)
    assert run("--help").returncode == 0
    result = run("sources")
    assert result.returncode == 0 and "sources checked" in result.stdout
    result = run("build", "--out", str(tmp_path / "site"))
    assert result.returncode == 0 and (tmp_path / "site" / "data.json").exists()
    # An import inside main() makes that name local to all of main(), so the other commands crash on it
    # (UnboundLocalError); collect can't run here (network), so check for it directly.
    from aipulse import __main__ as cli
    code = cli.main.__code__
    assert not set(code.co_varnames + code.co_cellvars) & set(vars(cli)), "a module-level name is re-imported in main()"


def test_us_tracker_stories_record_their_state():
    item = {"title": "Kotek signs order to regulate AI use in Oregon government", "summary": "", "category": "policy"}
    apply_regulation(item)
    assert item["jurisdictions"] == ["US", "US-OR"]
    georgia = {"title": "Georgia's parliament adopts AI law", "summary": "", "category": "policy"}
    apply_regulation(georgia)
    assert "US-GA" not in georgia["jurisdictions"]  # the country, not the state
    assert jurisdictions.us_states("New York Times sues OpenAI") == []
    assert jurisdictions.us_states("Washington still hasn't passed an AI law") == []


# --- Bill lifecycles from official sources ---
def test_eu_stages_from_the_ai_act_record():
    import json
    from aipulse import bills
    proc = json.loads((FIX / "europarl_ai_act.json").read_text(encoding="utf-8"))["data"][0]
    stages = {h["stage"]: h["date"] for h in bills.eu_history(proc)}
    assert stages == {"introduced": "2021-06-07", "passed_chamber": "2023-06-14", "passed_legislature": "2024-03-13",
                      "signed": "2024-06-13", "in_force": "2024-07-12"}
    assert bills._eu_short_title(proc["process_title"]["en"]) == "Artificial Intelligence Act"


def test_us_stages_from_congress_actions():
    from aipulse import bills
    acts = [{"actionDate": "2026-01-10", "text": "Introduced in House"},
            {"actionDate": "2026-01-10", "text": "Referred to the House Committee on Science."},
            {"actionDate": "2026-03-02", "text": "Passed/agreed to in House: On passage Passed by recorded vote."},
            {"actionDate": "2026-05-20", "text": "Passed Senate without amendment by Unanimous Consent."},
            {"actionDate": "2026-05-22", "text": "Presented to President."},
            {"actionDate": "2026-05-30", "text": "Signed by President."},
            {"actionDate": "2026-05-30", "text": "Became Public Law No: 119-88."}]
    history = bills.us_history(acts)
    assert [(h["stage"], h["date"]) for h in history] == [
        ("introduced", "2026-01-10"), ("passed_chamber", "2026-03-02"), ("passed_legislature", "2026-05-20"),
        ("signed", "2026-05-30"), ("in_force", "2026-05-30")]
    vetoed = bills.us_history(acts[:5] + [{"actionDate": "2026-06-01", "text": "Vetoed by President."}])
    assert bills.current(vetoed)["stage"] == "vetoed"


def test_congress_sync_keeps_ai_bills_and_builds_cards(tmp_path, monkeypatch):
    monkeypatch.setenv("CONGRESS_API_KEY", "test-key")
    import json
    from aipulse import bills
    monkeypatch.setattr(bills.time, "sleep", lambda s: None)
    listing = json.loads((FIX / "congress_bills.json").read_text(encoding="utf-8"))
    listing["pagination"] = {}
    actions = json.loads((FIX / "congress_actions.json").read_text(encoding="utf-8"))
    conn = store.connect(tmp_path / "t.db")
    fetch = lambda url: json.dumps(actions if "/actions" in url else listing).encode()
    assert bills.sync_congress(conn, fetch, log=lambda *_: None) == 5  # 5 AI bills in the 250 updated
    cards, total = store.cards(conn, "regulation")
    assert total == 5 and all(c["source"] == "congress.gov" for c in cards)
    card = next(c for c in cards if "10538" in c["title"])
    assert card["lifecycle"]["current"] == "introduced" and card["lifecycle"]["steps"][0]["label"] == "Introduced"
    assert card["url"] == "https://www.congress.gov/bill/119th-congress/house-bill/10538"
    assert bills.sync_congress(conn, fetch, log=lambda *_: None) == 0  # nothing new the second time


def test_bill_card_moves_up_when_it_advances_and_collects_news(tmp_path):
    from aipulse import bills, cluster
    conn = store.connect(tmp_path / "t.db")
    bill = {"key": "US-119-hr-10538", "jurisdiction": "US", "number": "H.R. 10538",
            "title": "To establish the Department of Artificial Intelligence", "short_title": "Department of AI Act",
            "url": "https://www.congress.gov/bill/119th-congress/house-bill/10538", "source": "congress.gov",
            "history": [{"date": "2026-09-24", "stage": "introduced", "text": "Introduced in House"}]}
    assert bills.upsert(conn, bill)
    bill["history"].append({"date": "2026-10-02", "stage": "passed_chamber", "text": "Passed House"})
    assert bills.upsert(conn, bill) and not bills.upsert(conn, bill)
    store.insert(conn, {"title": "House passes H.R. 10538 creating a Department of AI", "summary": "",
                        "url": "https://news.example/1", "source": "AP", "category": "regulation", "date": "2026-10-02",
                        "jurisdictions": ["US"], "action": "proposal"})
    store.insert(conn, {"title": "What the Department of AI Act would do", "summary": "",
                        "url": "https://news.example/2", "source": "Vox", "category": "policy", "date": "2026-10-03"})
    conn.commit()
    cluster.assign(conn, days=None)
    [card], _ = store.cards(conn, "regulation")
    assert card["date"] == "2026-10-02" and card["lifecycle"]["current"] == "passed_chamber"
    # What the bill would do (until CRS summarises it); stages are on the timeline, not repeated here.
    assert card["summary"] == "Would establish the Department of Artificial Intelligence."
    assert sorted(o["source"] for o in card["also"]) == ["AP", "Vox"]  # by number and by short title


def test_congress_sync_carries_on_where_it_stopped(tmp_path, monkeypatch):
    monkeypatch.setenv("CONGRESS_API_KEY", "test-key")
    import json
    from aipulse import bills
    monkeypatch.setattr(bills.time, "sleep", lambda s: None)
    seen = []
    def fetch(url):
        seen.append(url)
        full = "offset=0&" in url or "offset=250&" in url
        page = [{"congress": 119, "type": "SRES", "number": str(i), "title": "A resolution"} for i in range(250 if full else 10)]
        return json.dumps({"bills": page, "pagination": {"next": "more"} if full else {}}).encode()
    conn = store.connect(tmp_path / "t.db")
    bills.sync_congress(conn, fetch, max_pages=1, log=lambda *_: None)
    assert "/bill/119?" in seen[0] and "sort=updateDate+asc" in seen[0] and "fromDateTime=2025-01-03" in seen[0]
    cursor = json.loads(conn.execute("SELECT value FROM meta WHERE key = 'congress_cursor'").fetchone()[0])
    assert cursor["offset"] == 250 and cursor["from"].startswith("2025-01-03")
    seen.clear()
    bills.sync_congress(conn, fetch, log=lambda *_: None)  # re-reads one page, then reads on to the end
    assert ["offset=0&" in seen[0], "offset=250&" in seen[1], "offset=500&" in seen[2], len(seen)] == [True] * 3 + [3]
    cursor = json.loads(conn.execute("SELECT value FROM meta WHERE key = 'congress_cursor'").fetchone()[0])
    assert cursor["offset"] == 0 and not cursor["from"].startswith("2025-01-03")  # done: from now on


def test_reclassify_leaves_official_bill_cards_alone(tmp_path):
    from aipulse import bills
    conn = store.connect(tmp_path / "t.db")
    bills.upsert(conn, {"key": "EU-2021-0106", "jurisdiction": "EU", "number": "2021/0106(COD)",
                        "title": "Harmonised rules on Artificial Intelligence", "short_title": "Artificial Intelligence Act",
                        "url": "https://oeil.example/2021-0106", "source": "European Parliament",
                        "history": [{"date": "2024-07-12", "stage": "in_force", "text": "Published"}]})
    conn.commit()
    reclassify(conn)
    [card], _ = store.cards(conn, "regulation")
    assert card["jurisdictions"] == ["EU"] and card["action"] == "law"


def test_static_build_holds_every_card(tmp_path):
    import json
    from aipulse.static import build
    conn = store.connect(tmp_path / "t.db")
    sources = [{"name": "Fixture", "url": "rss", "category": "news"}]
    collect(conn, sources, max_age_days=100000, fetcher=lambda u: (FIX / "sample_rss.xml").read_bytes(),
            log=lambda *_: None)
    cards, total = store.cards(conn, limit=100)
    assert total >= 2 and build(conn, tmp_path / "site") == total
    data = json.loads((tmp_path / "site" / "data.json").read_text(encoding="utf-8"))
    assert [c["id"] for c in data["cards"]] == [c["id"] for c in cards]
    assert all(c["s"].startswith(" ") for c in data["cards"])  # search words, folded
    page = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert 'data-static="1"' in page and "feed.xml" not in page
    meme = json.loads((tmp_path / "site" / "meme.json").read_text(encoding="utf-8"))
    assert {p.name for p in (tmp_path / "site").iterdir()} == {"index.html", "data.json", "glossary.json", "tags.json", ".nojekyll", "feeds", "daily", "fonts", "meme.json", "photos", "dossier.html", "ask.html", "tracker.csv", "robots.txt", "sitemap.xml", "og.png", "tracker", "flags", "glossary", "site.css",
        "all", "releases", "industry", "research", "regulation", "policy", "infra"} | ({"memes"} if meme["image"] else set())  # the picture only when last week has one
    # the fonts are the site's own: nothing from Google Fonts (it would send every reader's address to Google)
    assert "fonts.googleapis" not in page and "fonts.gstatic" not in page
    assert {f for f in re.findall(r'url\("fonts/([^"]+)"\)', page)} <= {p.name for p in (tmp_path / "site" / "fonts").iterdir()}
    assert sorted(p.name for p in (tmp_path / "site" / "feeds").iterdir()) == ["all.opml", "infra.xml", "news.xml", "policy.xml", "regulation.xml", "releases.xml", "research.xml"]
    assert (tmp_path / "site" / "feeds" / "all.opml").read_text(encoding="utf-8").count("<outline ") == 6
    assert data["total"] == total  # the front page's all-time count, without the archive files
    assert (tmp_path / "site" / "tracker.csv").read_text(encoding="utf-8").startswith("date,countries,type,title,source,link")
    # what search engines see: a description and a preview image; the sitemap lists each day's page; AI-training
    # bots are kept out, and readers' own pages are never indexed
    assert '<meta name="description"' in page and 'og:image" content="https://projectaipulse.com/og.png"' in page
    robots = (tmp_path / "site" / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: GPTBot\nDisallow: /" in robots and "Sitemap: https://projectaipulse.com/sitemap.xml" in robots
    assert "User-agent: *\nDisallow: /dossier/" in robots
    for private in ("dossier.html", "ask.html"):
        assert '<meta name="robots" content="noindex">' in (tmp_path / "site" / private).read_text(encoding="utf-8")
    sitemap = (tmp_path / "site" / "sitemap.xml").read_text(encoding="utf-8")
    tracker_pages = list((tmp_path / "site" / "tracker").glob("**/index.html"))
    tracker_pages += list((tmp_path / "site" / "glossary").glob("**/index.html"))  # and the glossary's
    tracker_pages += list((tmp_path / "site" / "industry").glob("*/index.html"))  # and Industry's kinds, a page each
    assert "<url><loc>https://projectaipulse.com/industry/tutorials/</loc></url>" in sitemap  # no date of its own
    tutorials = (tmp_path / "site" / "industry" / "tutorials" / "index.html").read_text(encoding="utf-8")
    assert "<h1>AI tutorials</h1>" in tutorials and 'data-kind="tutorial"' in tutorials and "Updated" not in tutorials
    assert 'href="industry/tutorials/"' in (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert sitemap.count("<url>") == 1 + 7 + len(tracker_pages) + len([p for p in (tmp_path / "site" / "daily").iterdir() if p.name not in ("latest.html", "sample.html") and p.suffix == ".html"]) + (daily_sample := (tmp_path / "site" / "daily" / "sample.html").exists())
    # each stream has its own address: the same page, with its own title, description, canonical link and heading
    policy = (tmp_path / "site" / "policy" / "index.html").read_text(encoding="utf-8")
    assert "<title>AI policy news: governments, courts and politics · AI Pulse</title>" in policy
    assert policy.count('content="What governments, courts and politicians do about AI, worldwide. Updated every 6 hours') == 2
    assert 'rel="canonical" href="https://projectaipulse.com/policy/"' in policy and 'og:url" content="https://projectaipulse.com/policy/"' in policy
    assert '<h2 id="sec-title">Policy</h2>' in policy and '<base href="/">' in policy and 'data-static="1"' in policy
    assert "<loc>https://projectaipulse.com/infra/</loc>" in sitemap
    from aipulse.static import STREAM_PAGES
    for cat, (path, _, title, _) in STREAM_PAGES.items():  # the page sets the same titles
        assert f'{cat}: "{title}"' in page and f'href="/{path}/" data-go="{cat}"' in page
    # "See yesterday's full table" opens the newest day's page
    daily = tmp_path / "site" / "daily"
    days = sorted(p.name for p in daily.iterdir() if p.name not in ("latest.html", "index.html", "sample.html") and p.suffix == ".html")
    assert "<h1>Daily editions</h1>" in (daily / "index.html").read_text(encoding="utf-8")  # every edition, by month
    assert 'href="daily/sample.html"' in page and 'href="daily/"' not in page
    # "See what the email looks like": its format with placeholder stories, none of the day's own
    from aipulse.static import sample_cards
    sample = sample_cards(cards, date.fromisoformat(cards[0]["date"][:10]))
    from aipulse.static import SAMPLE_STORIES
    placeholders = {t for rows in SAMPLE_STORIES.values() for t, _ in rows}
    assert sample and all(c["source"].startswith("Outlet ") and c["title"] in placeholders for c in sample)
    assert len({c["title"] for c in sample}) == len(sample)  # no placeholder repeated
    assert not {c["title"] for c in cards} & {c["title"] for c in sample}
    if daily_sample:  # indexed, in the sitemap, with the day's real meme of the day as a picture beside it
        html = (daily / "sample.html").read_text(encoding="utf-8")
        assert "noindex" not in html and "https://projectaipulse.com/daily/sample.html" in sitemap
        assert "Meme of the day" not in html or 'src="meme-of-the-day.' in html
    assert not days or (daily / "latest.html").read_text(encoding="utf-8") == (daily / days[-1]).read_text(encoding="utf-8")


def test_tracker_csv_holds_official_records_only():
    from aipulse.static import tracker_csv
    card = lambda source, title: {"category": "regulation", "source": source, "title": title, "date": "2026-10-01",
                                  "jurisdictions": ["US"], "action": "proposal", "url": f"https://e.com/{source}"}
    rows = tracker_csv([card("congress.gov", "H.R. 1: An AI bill, with a comma"), card("TechCrunch AI", "A headline")]).splitlines()
    assert rows == ["date,countries,type,title,source,link",
                    '2026-10-01,US,proposal,"H.R. 1: An AI bill, with a comma",congress.gov,https://e.com/congress.gov']


def test_the_glossary_has_a_page_per_word_like_a_dictionary(tmp_path):
    from aipulse import glossary, glossary_pages
    conn = store.connect(":memory:")
    cards = [{"id": "a", "title": "A new MoE model", "summary": "35B-A3B, cheap to run", "date": "2026-10-05",
              "category": "tool", "source": "X"}]
    paths = glossary_pages.build(conn, cards, tmp_path, date(2026, 10, 6))
    assert paths[0] == "glossary/" and len(paths) == 1 + len(glossary.ENTRIES)
    page = (tmp_path / "glossary" / "mixture-of-experts" / "index.html").read_text(encoding="utf-8")
    # the site's masthead and footer, the meaning with the other words in it linked, related terms, the stories
    assert '<header class="top home">' in page and '<footer class="site-foot">' in page and 'href="site.css"' in page
    assert '<h1 class="word">Mixture of Experts</h1>' in page and '<a href="/glossary/parameters/">parameters</a>' in page
    assert "<h2>Related terms</h2>" in page and page.count('<li><div><a href="/glossary/') == glossary_pages.RELATED
    assert "Mentioned in 1 story in the last 7 days." in page and '/all/?' not in page
    # its latest stories, found on the page itself (from data.json, as the site's underlines find them)
    assert '<h2 id="stories">Latest stories with this word</h2>' in page and 'data-match="[&quot;MoE&quot;' in page and 'data-case=1' in page
    # what makes it worth a visit: the words in the same stories, and the week's words as a cloud on glossary/
    assert "<h2>Often in the same stories</h2>" in page and 'href="/glossary/parameters/" style="font-size:' in page
    assert '"@type": "DefinedTerm"' in page and 'rel="canonical" href="https://projectaipulse.com/glossary/mixture-of-experts/"' in page
    index = (tmp_path / "glossary" / "index.html").read_text(encoding="utf-8")
    assert index.count('<li><div><a href="/glossary/') == len(glossary.ENTRIES) and '<h2 id="A">A</h2>' in index
    cloud = index[index.index('<div class="cloud"'):index.index("<h2>A to Z</h2>")]
    assert cloud.count("<a ") == 2 and "Mixture of Experts</a>" in cloud  # this week's words only
    assert (tmp_path / "site.css").is_file()


def test_tracker_has_a_page_per_country_with_official_records_only(tmp_path):
    from datetime import date
    from aipulse import countries
    conn = store.connect(tmp_path / "t.db")
    card = lambda i, source, code, action="proposal": {"category": "regulation", "source": source, "title": f"AI Act {i}",
        "date": f"2026-0{i}-01", "jurisdictions": [code], "action": action, "url": f"https://e.com/{code}{i}", "bill": ""}
    cards = ([card(i, "UK Parliament", "GB") for i in range(1, 4)] + [card(4, "OECD.AI", "GB", "body")]
             + [card(i, "TechCrunch AI", "IN") for i in range(1, 6)] + [card(1, "Parliament of India", "IN")])
    paths = countries.build(conn, cards, tmp_path, date(2026, 10, 6))
    assert paths == ["tracker/", "tracker/united-kingdom/"]  # India: one official record, news stories don't count
    page = (tmp_path / "tracker" / "united-kingdom" / "index.html").read_text(encoding="utf-8")
    assert '<h1><img class="flag" src="flags/gb.svg" alt="">AI laws and bills in the United Kingdom</h1>' in page and "<h2>Proposals</h2>" in page
    assert "<h2>AI bodies</h2>" in page and page.index("AI Act 3") < page.index("AI Act 1")  # newest first
    assert 'rel="canonical" href="https://projectaipulse.com/tracker/united-kingdom/"' in page
    assert 'href="/tracker/united-kingdom/"' in (tmp_path / "tracker" / "index.html").read_text(encoding="utf-8")
    # labels for search engines: each bill is Legislation; tracker.csv is a Dataset (Google Dataset Search)
    assert '"@type": "Legislation"' in page and '"legislationJurisdiction": "United Kingdom"' in page
    assert '"@type": "Dataset"' in (tmp_path / "tracker" / "index.html").read_text(encoding="utf-8") and '"contentUrl": "https://projectaipulse.com/tracker.csv"' in (tmp_path / "tracker" / "index.html").read_text(encoding="utf-8")
    # the site's own masthead and footer, a plain way back, and each place's flag (copied beside the pages)
    assert '<header class="top home">' in page and '<footer class="site-foot">' in page and 'href="/#subscribe"' in page
    assert "← Back to the live Regulation tracker page" in page and 'src="flags/gb.svg"' in page
    assert 'src="flags/gb.svg"' in (tmp_path / "tracker" / "index.html").read_text(encoding="utf-8")
    assert (tmp_path / "flags" / "gb.svg").is_file() and not (tmp_path / "flags" / "in.svg").exists()


def test_standards_have_one_page_without_a_date(tmp_path):
    from datetime import date
    from aipulse import countries, standards
    from aipulse.static import sitemap
    conn = store.connect(tmp_path / "t.db")
    cards = standards.cards() + [{"category": "regulation", "source": "OECD.AI", "title": "Australian AI standard",
                                  "date": "2024-05-01", "jurisdictions": ["AU"], "action": "standard",
                                  "url": "https://e.com/au", "summary": "OECD's words"},
                                 {"category": "regulation", "source": "TechCrunch AI", "title": "A story on a standard",
                                  "date": "2025-01-01", "jurisdictions": ["INTL"], "action": "standard", "url": "https://e.com/n"}]
    assert countries.standards_page(conn, cards, tmp_path) == ["standards/"]
    page = (tmp_path / "standards" / "index.html").read_text(encoding="utf-8")
    assert "<h1>AI standards</h1>" in page and "<h2>International: ISO/IEC</h2>" in page and "<h2>National</h2>" in page
    assert "ISO/IEC 42001:2023" in page and "Published Dec 2023" in page and "Organisations can be certified" in page
    assert "Australia" in page and "OECD's words" not in page and "A story on a standard" not in page  # official only
    assert "Updated" not in page and 'href="/standards/"' in (countries.build(conn, cards, tmp_path, date(2026, 10, 6)) and
                                                               (tmp_path / "tracker" / "index.html").read_text(encoding="utf-8"))
    assert "<url><loc>https://projectaipulse.com/standards/</loc></url>" in sitemap([], date(2026, 10, 6), ["standards/"])


def test_static_build_puts_old_cards_in_yearly_archive(tmp_path):
    import json
    from datetime import date
    from aipulse.static import build
    conn = store.connect(tmp_path / "t.db")
    old = {"title": "OpenAI releases GPT-4 to developers", "summary": "", "url": "https://example.com/gpt4",
           "source": "Example", "category": "tool", "date": "2023-03-14", "tags": ["OpenAI"], "authors": []}
    store.insert(conn, old)
    store.insert(conn, {**old, "title": "A new model this week", "url": "https://example.com/new",
                        "date": date.today().isoformat()})
    conn.commit()
    build(conn, tmp_path / "site")
    data = json.loads((tmp_path / "site" / "data.json").read_text(encoding="utf-8"))
    assert [c["title"] for c in data["cards"]] == ["A new model this week"]  # the page loads this at once
    assert data["archive"] == [{"file": "archive/2023.json", "cards": 1}]  # fetched for "All time"
    year = json.loads((tmp_path / "site" / "archive" / "2023.json").read_text(encoding="utf-8"))
    assert [c["title"] for c in year] == ["OpenAI releases GPT-4 to developers"]


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


def test_sources_avoid_hosts_that_block_cloud_servers():
    # The site is built on GitHub Actions: arXiv's search API (406) and Substack (Cloudflare 403) refuse it.
    from aipulse.sources import SOURCES
    assert not [s["url"] for s in SOURCES if "export.arxiv.org/api" in s["url"] or "substack.com" in s["url"]]


def test_brand_names_in_headlines():
    from aipulse import brands
    common = {"some", "discover", "make"}
    assert brands.names("Ando wants to take on Slack with a team messaging app", common) == ["Ando", "Slack"]
    assert brands.names("Black Forest Labs launches FLUX 3 Action", common)[0] == "Black Forest Labs"
    assert brands.names("ElevenLabs’ CEO on margins and IPO timing", common)[0] == "ElevenLabs"
    assert brands.names("PrismML brings tiny LLMs to Qualcomm-powered glasses", common) == ["PrismML", "LLMs", "Qualcomm"]
    assert brands.names("Some Supabase customers are exposing data", common) == ["Supabase"]
    # Title Case Headlines: only distinctive names ("Discover", "Make" are ordinary words there)
    assert brands.names("Can AI Help Us Discover The Origin Of Consciousness?", common) == []
    assert brands.names("How to Make the U.S.-China AI Race Less Dangerous", common) == []


def test_brand_logo_needs_confirmation_for_plain_words(monkeypatch):
    from aipulse import brands
    monkeypatch.setattr(brands, "si_index", lambda: {"Astra": {"title": "Astra", "slug": "astra", "hex": "5C2EDE"},
                                                     "YouTube": {"title": "YouTube", "slug": "youtube", "hex": "FF0000"}})
    monkeypatch.setattr(brands, "si_path", lambda s: "M0 0h24v24H0z")
    known = {"Slack": {"brand": True, "site": "slack.com", "icon": "own-slack.ico"},
             "Astra": {"brand": False, "site": None, "icon": None}, "Ando": {"brand": False, "site": None, "icon": None}}
    monkeypatch.setattr(brands, "wikidata", lambda name, budget: known.get(name))
    logo = lambda title, tags=(): brands.logo_for(title, list(tags), set(), [10])
    assert logo("Ando wants to take on Slack")["src"] == "brand-icons/own-slack.ico"
    assert logo("Astra and Opus just passed Turing's test") is None  # a plain word Wikidata doesn't call a brand
    assert logo("YouTube promises custom feeds")["hex"] == "#FF0000"  # distinctive: no confirmation needed
    assert logo("Meta's new glasses use Slack", ["Meta"]) is None  # the page's own AI-company logos come first


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


def test_no_source_or_lookup_uses_sites_that_forbid_automated_access():
    # Google News (robots.txt) and Bing News (its feed terms) don't allow this use; neither does Google's
    # favicon service. Nothing in the app may fetch from them.
    code = "\n".join(f.read_text(encoding="utf-8") for f in (FIX.parent.parent / "aipulse").glob("*.py") if f.name != "collect.py")
    for host in ("news.google.com", "bing.com", "google.com/s2"):
        assert host not in code, host
    from aipulse.sources import SOURCES
    assert not [s["url"] for s in SOURCES if "google.com" in s["url"].split("/")[2] and "blog.google" not in s["url"]]


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


def test_only_free_articles_of_a_paywalled_outlet_are_kept(tmp_path):
    from aipulse.collect import drop_subscriber_only
    from aipulse.sources import SOURCES
    assert [s["name"] for s in SOURCES if s.get("paywall_check")] == ["The Verge AI"]
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


def test_msit_summaries_lose_the_stray_mark(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    store.insert(conn, {"title": "Pilot AI app for grocery shopping", "summary": "﻿- The price body was launched.",
                        "url": "https://www.msit.go.kr/eng/1", "source": "Ministry of Science and ICT (Korea)",
                        "category": "policy", "date": "2026-09-30", "tags": [], "authors": []})
    reclassify(conn, fetcher=lambda u: b"")
    assert conn.execute("SELECT summary FROM items").fetchone()[0] == "The price body was launched."


def test_an_order_about_names_is_policy_not_law():
    from aipulse.classify import regulatory_action
    assert regulatory_action("Trump orders US government to call AI ‘Super Intelligence’") is None
    assert regulatory_action("Newsom orders new steps on AI safety") == "law"


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


def test_nothing_is_fetched_against_robots_txt(monkeypatch):
    import pytest, urllib.robotparser
    rules = urllib.robotparser.RobotFileParser()
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
    from aipulse.sources import SOURCES
    arxiv = [s for s in SOURCES if "arxiv.org" in s["url"]]
    assert arxiv and all(s.get("pause", 0) >= 3 for s in arxiv)  # arXiv: one request every 3 seconds


def test_uk_stages_from_parliament_readings():
    from aipulse.bills import current, uk_history
    sit = lambda *d: [{"date": x + "T00:00:00"} for x in d]
    stages = [{"house": "Lords", "description": "1st reading", "stageSittings": sit("2024-10-23")},
              {"house": "Lords", "description": "3rd reading", "stageSittings": sit("2025-02-05")},
              {"house": "Commons", "description": "1st reading", "stageSittings": sit("2025-02-06")},
              {"house": "Commons", "description": "3rd reading", "stageSittings": sit("2025-05-07")},
              {"house": "Lords", "description": "Royal Assent", "stageSittings": sit("2025-06-19")}]
    history = uk_history({"billWithdrawn": None, "isDefeated": False}, stages)
    assert [(h["stage"], h["date"]) for h in history] == [
        ("introduced", "2024-10-23"), ("passed_chamber", "2025-02-05"), ("passed_legislature", "2025-05-07"),
        ("signed", "2025-06-19")]
    stalled = uk_history({"billWithdrawn": "2024-05-24T00:00:00", "isDefeated": False}, stages[:1])
    assert current(stalled)["stage"] == "withdrawn"


def test_brazil_stages_from_chamber_events():
    from aipulse.bills import br_history, current
    ev = lambda d, what, situ="", desp="": {"dataHora": d + "T10:00", "descricaoTramitacao": what,
                                            "descricaoSituacao": situ, "despacho": desp}
    law = [ev("2023-03-01", "Apresentação de Proposição"), ev("2024-05-02", "Remessa ao Senado Federal"),
           ev("2024-11-10", "Apresentação de Proposição", "", "Recebido Ofício n° 262/2025-SF que comunica remessa à sanção"),
           ev("2024-12-01", "Transformação em Norma Jurídica", "", "Transformado na Lei Ordinária 15123/2025."),
           ev("2024-12-05", "Arquivamento")]
    h = br_history("2023-03-01T09:00", law)
    assert [x["stage"] for x in h] == ["introduced", "passed_chamber", "passed_legislature", "signed"]
    from_senate = [ev("2025-03-17", "Recebimento", "Aguardando Parecer",
                      "Recebido o Ofício nº 235/ 2025 do Senado Federal que submete à revisão da Câmara")]
    h = br_history("2025-03-17T17:21", from_senate)
    assert [(x["stage"], x["date"]) for x in h] == [("passed_chamber", "2025-03-17")]
    withdrawn = [ev("2026-03-16", "Retirada pelo(a) Autor(a)", "Transformado em Norma Jurídica")]
    assert current(br_history("2024-01-10T09:00", withdrawn))["stage"] == "withdrawn"
    # The API stamps every event with the bill's current situation; that must not count as a stage.
    stamped = [ev("2024-02-27", "Despacho de Apensação", "Transformado em Norma Jurídica", "Apense-se à(ao) PL-5695/2023.")]
    assert [x["stage"] for x in br_history("2024-02-21T09:00", stamped)] == ["introduced"]


def test_australia_stages_from_the_register():
    from aipulse.bills import au_history, current
    act = {"makingDate": "2024-09-02T00:00:00", "collection": "Act",
           "statusHistory": [{"status": "InForce", "start": "2024-09-02T00:00:00"}]}
    assert [(h["stage"], h["date"]) for h in au_history(act)] == [("signed", "2024-09-02"), ("in_force", "2024-09-02")]
    gone = {"makingDate": "2019-01-10T00:00:00", "collection": "LegislativeInstrument",
            "statusHistory": [{"status": "InForce", "start": "2019-01-11T00:00:00"},
                              {"status": "Repealed", "start": "2023-04-01T00:00:00"}]}
    assert current(au_history(gone))["stage"] == "withdrawn"


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


def test_china_regulations_from_the_cac_list(tmp_path, monkeypatch):
    from aipulse import bills, translate
    page = ('<li><h5><a href=//www.cac.gov.cn/2023-07/13/c_1690898327029107.htm target=_blank '
            'title="生成式人工智能服务管理暂行办法">生成式人工智能服务管理暂行办法</a></h5><div class="times">2023-07-13</div></li>'
            '<li><h5><a href=//www.cac.gov.cn/2023-01/01/c_1.htm target=_blank title="网络安全审查办法">网络安全审查办法</a></h5>'
            '<div class="times">2023-01-01</div></li>'
            '<li><h5><a href=//www.cac.gov.cn/2026-09/01/c_2.htm target=_blank title="人工智能安全管理办法（征求意见稿）">x</a></h5>'
            '<div class="times">2026-09-01</div></li>').encode()
    monkeypatch.setattr(bills.time, "sleep", lambda s: None)
    conn = store.connect(tmp_path / "t.db")
    assert bills.sync_china(conn, fetcher=lambda url: page, log=lambda *_: None) == 2  # the non-AI one is left out
    rows = dict(conn.execute("SELECT key, stage FROM bills").fetchall())
    assert rows == {"CN-c_1690898327029107": "signed", "CN-c_2": "introduced"}  # a draft for comment is a proposal
    assert translate._after("zh", "Interim approach to the management of generated artificial intelligence services") == \
        "Interim Measures for the Administration of generative artificial intelligence services"


def test_canada_regulations_from_the_canada_gazette(tmp_path, monkeypatch):
    import json
    from aipulse import bills, store
    day = {1: ("October 3, 2026", "2026-10-03"), 2: ("February 10, 2027", "2027-02-10")}  # proposed, then registered
    feed = lambda part: (f'<rss><channel><item><title>Canada Gazette - Part {"I" * part}, {day[part][0]}, volume 160, '
                         f'number 40</title><link>https://gazette.gc.ca/rp-pr/p{part}/2026/{day[part][1]}/html/index-eng.html'
                         '</link></item></channel></rss>').encode()
    issue = ('<a href="./notice-avis-eng.html">Government notices</a>'
             '<a href="reg1-eng.html">Regulations Respecting Artificial Intelligence Systems — Part One</a>'
             '<a href="reg2-eng.html">Canadian Chicken Licensing Regulations</a>').encode("cp1252")  # an older page
    pages = {bills.CA_GAZETTE.format(part=p): feed(p) for p in (1, 2)}
    monkeypatch.setattr(bills.time, "sleep", lambda s: None)
    conn = store.connect(tmp_path / "t.db")
    assert bills.sync_canada_gazette(conn, fetcher=lambda url: pages.get(url, issue), log=lambda *_: None) == 1
    # proposed in Part I, then registered in Part II: one record, its card now a law
    (key, stage, history), = conn.execute("SELECT key, stage, history FROM bills").fetchall()
    assert key == "CA-GAZ-regulations-respecting-artificial-intelligence-systems-part-one" and stage == "signed"
    assert [h["stage"] for h in json.loads(history)] == ["introduced", "signed"]
    (title, action), = conn.execute("SELECT title, action FROM items WHERE source = 'Canada Gazette'").fetchall()
    assert title == "Regulations Respecting Artificial Intelligence Systems — Part One" and action == "law"
    # seen in Part I one run and registered months later: the same card becomes a law (the proposal isn't left behind)
    conn2 = store.connect(tmp_path / "t2.db")
    only = lambda part: lambda url: feed(part) if url == bills.CA_GAZETTE.format(part=part) else (
        b"<rss></rss>" if url.endswith(".xml") else issue)
    bills.sync_canada_gazette(conn2, fetcher=only(1), log=lambda *_: None)
    actions = lambda: [r[0] for r in conn2.execute("SELECT action FROM items WHERE source = 'Canada Gazette'")]
    assert actions() == ["proposal"]
    bills.sync_canada_gazette(conn2, fetcher=only(2), log=lambda *_: None)
    assert actions() == ["law"]
    assert [h["stage"] for h in json.loads(conn2.execute("SELECT history FROM bills").fetchone()[0])] == ["introduced", "signed"]


def test_india_bills_from_parliament(tmp_path, monkeypatch):
    import json
    from aipulse import bills
    record = {"billNumber": "59", "billName": "The Artificial Intelligence (Ethics and Accountability) Bill, 2025.",
              "billYear": 2025, "billIntroducedInHouse": "Lok Sabha", "billIntroducedDate": "2025-12-05 00:00:00.0",
              "billIntroducedFile": "https://sansad.in/getFile/BillsTexts/LSBillTexts/Asintroduced/59 of 2025.pdf",
              "billPassedInLSDate": "2026-03-02 00:00:00.0", "billPassedInRSDate": None, "billAssentedDate": None}
    other = {**record, "billNumber": "60", "billName": "The Seeds Bill, 2025"}
    monkeypatch.setattr(bills.time, "sleep", lambda s: None)
    conn = store.connect(tmp_path / "t.db")
    fetch = lambda url: json.dumps({"records": [record, other]}).encode()
    assert bills.sync_india(conn, fetcher=fetch, log=lambda *_: None) == 1
    title, url, summary = conn.execute("SELECT title, url, summary FROM items").fetchone()
    assert title == "The Artificial Intelligence (Ethics and Accountability) Bill, 2025" and " " not in url
    assert summary == ""  # no official description: nothing, rather than the stages again



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


def test_congress_is_skipped_without_a_personal_key(tmp_path, monkeypatch):
    from aipulse import bills
    monkeypatch.delenv("CONGRESS_API_KEY", raising=False)
    asked = []
    conn = store.connect(tmp_path / "t.db")
    assert bills.sync_congress(conn, lambda url: asked.append(url), log=lambda *_: None) == 0
    assert asked == []  # the DEMO_KEY is never used


def test_msit_press_releases_parse():
    page = ("""$('#td_'+'NTT_SJ'+'_0').html('<a href="javascript:;" onclick="fn_detail("1290")" class="" data-value="1290">"""
            """<span>MSIT Announces the Enforcement Decree of the AI Basic Act</span></a></b>');"""
            """ //$('#td_'+'NTT_SJ'+'_0').html('<a href="javascript:;" onclick="fn_detail("1290")" class="" data-value="1290">"""
            """<span>MSIT Announces the Enforcement Decree of the AI Basic Act</span>');"""
            """ if('REG_DT' == 'REG_DT'){ $('#td_'+'REG_DT'+'_0').html('Jan 22, 2026'); }""").encode()
    [e] = feeds.parse_msit(page)
    assert e["title"] == "MSIT Announces the Enforcement Decree of the AI Basic Act"
    assert e["url"].endswith("bbsSeqNo=42&nttSeqNo=1290") and e["published"].date().isoformat() == "2026-01-22"


def test_japan_laws_from_e_gov():
    from aipulse.bills import current, jp_history
    law = {"law_info": {"law_id": "507AC0000000053", "promulgation_date": "2025-06-04"},
           "revision_info": {"law_title": "人工知能関連技術の研究開発及び活用の推進に関する法律",
                             "amendment_enforcement_date": "2025-09-01", "repeal_date": None}}
    h = jp_history(law)
    assert [(x["stage"], x["date"]) for x in h] == [("signed", "2025-06-04"), ("in_force", "2025-09-01")]
    assert current(h)["stage"] == "in_force"


def test_bill_summary_explains_the_bill_not_its_stages(tmp_path):
    from aipulse import bills
    crs = ("<p><strong>Stop Rogue AI Act</strong></p><p>This bill requires developers of frontier AI models to "
           "report safety incidents to the Department of Commerce within 72 hours.</p>")
    assert bills.describe(crs, "Stop Rogue AI Act") == ("This bill requires developers of frontier AI models to "
                                                        "report safety incidents to the Department of Commerce within 72 hours.")
    conn = store.connect(tmp_path / "t.db")
    bills.connect_tables(conn)
    bill = {"key": "US-119-hr-9", "jurisdiction": "US", "number": "H.R. 9", "title": "Stop Rogue AI Act",
            "url": "https://congress.gov/9", "source": "congress.gov", "summary": bills.describe(crs, "Stop Rogue AI Act"),
            "history": [{"date": "2026-09-01", "stage": "introduced", "text": ""}]}
    bills.upsert(conn, bill)
    bills.upsert(conn, {**bill, "summary": "", "history": bill["history"] + [
        {"date": "2026-09-20", "stage": "passed_chamber", "text": ""}]})  # a later sync without the text keeps it
    assert conn.execute("SELECT summary FROM items").fetchone()[0].startswith("This bill requires developers")


def test_oecd_records_follow_the_rules(tmp_path):
    import json
    from aipulse import oecd
    base = {"category": "Regulations, guidelines and standards", "startYear": 2024, "description": "<p>Sets rules.</p>",
            "createdByEmail": "editor@example.org", "intergovernmentalOrganisation": None, "extentBinding": None}
    law = lambda code, name, kind="Law/legislation/act (by legislative body)": {
        **base, "id": hash(name) % 10**6, "englishName": name, "slug": name.lower().replace(" ", "-"),
        "initiativeType": {"name": kind}, "gaiinCountry": {"code": code}}
    records = [law("SGP", "Singapore AI Act"),                        # taken: a law, Singapore has no own source
               law("FRA", "French AI Act"),                           # EU member: the EU counts as one
               law("USA", "US AI Act"),                               # US law: already from congress.gov
               law("USA", "US AI Guidance", "Guidance document (instructions on how to implement a law, regulation, policy or other rule)"),
               {**base, "id": 9, "englishName": "Council of Europe Framework Convention on AI", "slug": "coe-convention",
                "category": "AI Policy Frameworks and Initiatives (intergovernmental or supranational)", "gaiinCountry": None,
                "initiativeType": {"name": "Treaty"}, "extentBinding": "Binding",
                "intergovernmentalOrganisation": {"name": "Council of Europe"}}]
    cards = {c["title"]: c for c in map(oecd.card, records) if c}
    assert set(cards) == {"Singapore AI Act", "US AI Guidance", "Council of Europe Framework Convention on AI"}
    assert (cards["Singapore AI Act"]["category"], cards["Singapore AI Act"]["jurisdictions"]) == ("regulation", ["SG"])
    assert cards["US AI Guidance"]["category"] == "policy"
    assert cards["Council of Europe Framework Convention on AI"]["jurisdictions"] == ["INTL"]
    assert all(c["date"] == "2024-01-01" and "editor@" not in json.dumps(c) for c in cards.values())
    conn = store.connect(tmp_path / "t.db")
    page = json.dumps({"data": records, "lastPage": 1}).encode()
    assert oecd.sync(conn, fetcher=lambda u: page, log=lambda *_: None, force=True) == 3
    assert conn.execute("SELECT COUNT(*) FROM items WHERE bill LIKE 'OECD-%'").fetchone()[0] == 3
    assert oecd.sync(conn, fetcher=lambda u: page, log=lambda *_: None) == 0  # read at most weekly


def test_every_place_has_a_region_and_the_filter_uses_it(tmp_path):
    from aipulse import jurisdictions as J
    assert not [c for c in J.JURISDICTIONS if c not in J.REGION_OF and c not in J.NO_REGION]  # none forgotten
    assert "RU" not in J.REGION_OF
    conn = store.connect(tmp_path / "t.db")
    base = {"summary": "", "source": "E", "category": "regulation", "date": "2026-01-01", "tags": [], "authors": []}
    for code, url in (("JP", "https://e.jp/1"), ("FR", "https://e.fr/1"), ("EU", "https://e.eu/1"), ("US-CA", "https://e.us/1")):
        store.insert(conn, {**base, "title": f"AI rule {code}", "url": url, "jurisdictions": [code]})
    conn.commit()
    pick = lambda region: sorted(c["title"] for c in store.cards(conn, "regulation", codes=J.region_codes(region))[0])
    assert pick("europe") == ["AI rule EU", "AI rule FR"]
    assert pick("americas") == ["AI rule US-CA"] and pick("asia") == ["AI rule JP"]
    # a paper names no place: it counts where its scholar or company is based
    paper = {**base, "category": "research", "jurisdictions": []}
    store.insert(conn, {**paper, "title": "A paper by Max Welling", "url": "https://arxiv.org/abs/1", "tags": ["Max Welling", "Research"]})
    store.insert(conn, {**paper, "title": "A Qwen paper", "url": "https://arxiv.org/abs/2", "tags": ["Alibaba", "Research"]})
    conn.commit()
    papers = lambda region: sorted(c["title"] for c in store.cards(conn, "research", codes=J.region_codes(region))[0])
    assert papers("europe") == ["A paper by Max Welling"] and papers("asia") == ["A Qwen paper"]
    assert not [n for n, _ in __import__("aipulse.sources").sources.PROFESSORS if n not in classify.paper_homes()]


def test_oecd_ai_bodies_become_body_cards():
    from aipulse import oecd
    body = {"id": 7, "englishName": "Japan AI Safety Institute (AISI Japan)", "slug": "aisi-japan", "startYear": 2024,
            "category": "National – AI governance bodies or mechanisms", "description": "Evaluates AI safety.",
            "initiativeType": {"name": "Oversight bodies, offices or processes"}, "gaiinCountry": {"code": "JPN"},
            "intergovernmentalOrganisation": None, "extentBinding": None}
    c = oecd.card(body)
    assert (c["category"], c["action"], c["jurisdictions"], c["tags"][0]) == ("regulation", "body", ["JP"], "Oversight body")
    assert oecd.card({**body, "gaiinCountry": {"code": "FRA"}}) is None  # EU member: the EU counts as one


def test_oecd_start_year_typo_is_corrected_from_the_records_own_text():
    from aipulse import oecd
    office = {"englishName": "EU AI Office", "startYear": 2004,
              "overview": "<p>The EU AI Office was established by European Commission Decision on 24 January 2024.</p>"}
    assert oecd._start_year(office) == 2024
    # Years that aren't the record's own start, or only a year or two off, are left alone.
    assert oecd._start_year({"englishName": "Fund", "startYear": 2018, "overview": "Created under Project Ireland 2040."}) == 2018
    assert oecd._start_year({"englishName": "NAIIO", "startYear": 2021,
                             "overview": "The NAIIO was established under the National AI Initiative Act of 2020."}) == 2021


def test_vietnam_ai_laws_from_the_sitemap(tmp_path):
    from aipulse import bills
    law = "https://vbpl.vn/van-ban/chi-tiet/luat-tri-tue-nhan-tao-so-134-2025-qh15--69ba65c0"
    pages = {
        "https://vbpl.vn/sitemap.xml": "<loc>https://vbpl.vn/sitemap/0.xml</loc><!-- Trung ương --><loc>https://vbpl.vn/sitemap/1.xml</loc>"
                                       "<!-- Địa phương --><loc>https://vbpl.vn/sitemap/2.xml</loc>",
        "https://vbpl.vn/sitemap/1.xml": f"<loc>{law}</loc><loc>https://vbpl.vn/van-ban/chi-tiet/luat-dat-dai--1</loc>",
        law: '<meta name="description" content="Tra cứu Luật 134/2025/QH15, LUẬT TRÍ TUỆ NHÂN TẠO SỐ 134/2025/QH15. Xem toàn văn và hiệu lực."/>'
             '<meta property="article:published_time" content="2025-12-09T17:00:00.000Z"/>'}
    seen = []
    fetch = lambda u: (seen.append(u), pages[u].encode())[1]
    conn = store.connect(tmp_path / "t.db")
    assert bills.sync_vietnam(conn, fetch, log=lambda *_: None) == 1
    assert "https://vbpl.vn/sitemap/2.xml" not in seen  # provincial documents aren't read
    row = conn.execute("SELECT number, title, stage, stage_date FROM bills WHERE jurisdiction = 'VN'").fetchone()
    assert tuple(row) == ("Law No. 134/2025/QH15", "Luật trí tuệ nhân tạo", "signed", "2025-12-10")
    assert bills.sync_vietnam(conn, fetch, log=lambda *_: None) == 0  # read at most weekly


def test_each_place_keeps_its_data_protection_law_not_every_privacy_bill(tmp_path):
    from aipulse import bills
    D = bills.DATA_LAWS
    assert D["GB"].search("Data Protection Act 2018") and D["GB"].search("Data (Use and Access) Act 2025")
    assert not D["GB"].search("Protection of Children (Digital Safety and Data Protection) Bill")
    assert D["AU"].search("Privacy Amendment (Notifiable Data Breaches) Act 2017") and D["AU"].search("Privacy Act 1988")
    assert not D["AU"].search("My Health Records Amendment (Strengthening Privacy) Act 2018")
    assert not D["AU"].search("Privacy (Credit Reporting) Code 2025")
    assert D["JP"].search("個人情報の保護に関する法律施行令") and not D["JP"].search("行政機関の保有する個人情報の保護に関する法律")
    assert D["EU"].search("Protection of individuals with regard to the processing of personal data, and the free "
                          "movement of such data (General Data Protection Regulation)")
    assert D["CN"].search("中华人民共和国个人信息保护法") and not D["CN"].search("个人信息出境认证办法")
    # a Vietnamese decree (two-word type, a line break in its description); a Norwegian law decision; a Swiss bill done
    decree = "https://vbpl.vn/van-ban/chi-tiet/nghi-dinh-so-356-2025-nd-cp-bao-ve-du-lieu-ca-nhan--187276"
    pages = {"https://vbpl.vn/sitemap.xml": "<loc>https://vbpl.vn/sitemap/0.xml</loc><loc>https://vbpl.vn/sitemap/1.xml</loc>",
             "https://vbpl.vn/sitemap/1.xml": f"<loc>{decree}</loc>",
             decree: '<meta name="description" content="Tra cứu Nghị định 356/2025/NĐ-CP, Nghị định số 356/2025/NĐ-CP '
                     'Quy định chi tiết \nLuật Bảo vệ dữ liệu cá nhân. Xem toàn văn và hiệu lực."/>'
                     '<meta property="article:published_time" content="2025-12-30T17:00:00.000Z"/>'}
    conn = store.connect(tmp_path / "t.db")
    assert bills.sync_vietnam(conn, lambda u: pages[u].encode(), log=lambda *_: None) == 1
    row = conn.execute("SELECT number, title FROM bills WHERE jurisdiction = 'VN'").fetchone()
    assert tuple(row) == ("Decree No. 356/2025/NĐ-CP", "Quy định chi tiết Luật Bảo vệ dữ liệu cá nhân")
    case = {"ferdigbehandlet": True, "henvisning": "Prop. 115 L (2017-2018), Innst. 80 L (2018-2019), Lovvedtak 14 (2018-2019)",
            "saksgang": {"saksgang_steg_liste": [{"saksgang_hendelse_liste": [{"id": "FREMSATT", "dato": "07.09.2018"},
                                                                               {"id": "X", "dato": "20.12.2018"}]}]}}
    assert bills.no_history(case)[-1]["stage"] == "passed_legislature"
    swiss = {"BusinessTypeName": "Geschäft des Bundesrates", "BusinessStatusText": "Erledigt",
             "SubmissionDate": "/Date(1505433600000)/", "BusinessStatusDate": "/Date(1600992000000)/"}
    assert [h["stage"] for h in bills.ch_history(swiss)] == ["introduced", "passed_legislature"]


def test_every_country_is_recognised_but_names_of_people_and_states_are_not():
    from aipulse import jurisdictions as J
    assert len(J.JURISDICTIONS) > 180
    assert J.detect("Jordanian parliament approves AI bill") == ["JO"] and J.detect("Iran bans chatbot") == ["IR"]
    assert J.detect("Papua New Guinea adopts AI policy") == ["PG"]  # not Guinea
    assert J.detect("South Sudan and Sudan sign AI pact") == ["SS", "SD"]
    for headline in ("Jim Jordan grills AI firms", "Georgia lawmakers pass deepfake bill", "Chad Smith on AI"):
        assert J.detect(headline) == []


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


def test_swiss_motions_go_to_the_tracker_and_postulates_to_policy(tmp_path):
    import json
    from aipulse import bills
    rec = lambda i, kind, title, status: {
        "ID": i, "BusinessShortNumber": f"26.{i}", "BusinessTypeName": kind, "Title": title,
        "SubmittedText": "<p>Die Schweiz diskutiert. Der Bundesrat wird beauftragt, Deepfakes zu regeln.</p>",
        "FederalCouncilProposalText": "Ablehnung", "SubmissionDate": "/Date(1781740800000)/",
        "SubmissionCouncilName": "Nationalrat", "BusinessStatusText": status, "BusinessStatusDate": "/Date(1782000000000)/"}
    records = [rec(1, "Motion", "Deepfakes regeln", "Überwiesen an den Bundesrat"),
               rec(2, "Postulat", "Deepfakes. Bericht", "Stellungnahme zum Vorstoss liegt vor"),
               rec(3, "Interpellation", "Deepfakes?", "Erledigt")]
    page = json.dumps({"d": records}).encode()
    conn = store.connect(tmp_path / "t.db")
    assert bills.sync_switzerland(conn, lambda u: page, log=lambda *_: None) == 2
    cards = {r["title"]: dict(r) for r in conn.execute("SELECT title, category, action, summary FROM items")}
    assert set(cards) == {"Motion 26.1: Deepfakes regeln", "Postulate 26.2: Deepfakes. Bericht"}  # no questions
    assert cards["Motion 26.1: Deepfakes regeln"]["category"] == "regulation"
    assert cards["Postulate 26.2: Deepfakes. Bericht"]["category"] == "policy"
    assert "The Federal Council recommends rejecting it." in cards["Motion 26.1: Deepfakes regeln"]["summary"]
    assert bills._ch_demand(records[0]["SubmittedText"]) == "Der Bundesrat wird beauftragt, Deepfakes zu regeln."
    assert [h["stage"] for h in bills.ch_history(records[0])] == ["introduced", "passed_legislature"]


def test_malaysia_ministry_releases_and_their_lead_paragraph():
    from aipulse import feeds, jurisdictions
    listing = (b'<a class="group" href="/en-GB/siaran/Rang-Undang-Undang-AI"><p class="font-semibold">Media Release</p>'
               b'<p class="line-clamp-2 font-semibold">Ministry Of Digital Initiates Engagement On Proposed AI Governance Bill</p>'
               b'<p class="line-clamp-3 text-sm">same</p><time class="text-dim-500">10 Jul 2026</time></a>')
    [e] = feeds.parse_digital_my(listing)
    assert (e["url"], e["published"].date().isoformat()) == ("https://www.digital.gov.my/en-GB/siaran/Rang-Undang-Undang-AI", "2026-07-10")
    release = "<p>Title</p><p>PUTRAJAYA, 10 July 2026 – The Ministry of Digital, through the National AI Office, began talks.</p>".encode()
    assert feeds.lead_paragraph(release) == "The Ministry of Digital, through the National AI Office, began talks."
    speech = (b"<p>AI Takeover</p><p>1. First of all, I would like to thank the organisers for inviting me today, truly.</p>"
              b"<p>2. Malaysia will set up an AI sandbox so that companies can test new systems safely before launch.</p>")
    assert feeds.lead_paragraph(speech, "AI Takeover").startswith("Malaysia will set up an AI sandbox")
    assert "EU" not in jurisdictions.detect("The National AI Office (NAIO) began talks")  # not the EU AI Office


def test_duma_english_news_and_non_ai_agents():
    from aipulse import feeds, classify
    page = ('<ul><li class="article-list__item "><a href="/en/news/1/"><time datetime="2026-09-22 13:01:00">x</time>'
            '<h6 class="t" itemprop="headline">State Duma adopts AI law</h6><p class="l" itemprop="description">It sets rules.</p></a></li>'
            '<li class="article-list__item "><a href="/en/news/2/"><h6 itemprop="headline">New law on foreign agents</h6></a></li></ul>').encode()
    first, second = feeds.parse_duma_en(page)
    assert (first["url"], first["summary"], first["published"].date().isoformat()) ==         ("http://duma.gov.ru/en/news/1/", "It sets rules.", "2026-09-22")
    assert second["published"] is None and second["title"] == "New law on foreign agents"  # no date listed
    assert not classify.is_ai_related(second["title"], "") and classify.is_ai_related("OpenAI ships agents", "")


def test_malaysian_ai_bills_from_parliament(tmp_path):
    from aipulse import bills
    row = lambda num, title, first, passed="": (
        '<tr class="maintable"><td class="maintd"><a onclick="loadResult(\'/files/billindex/pdf/2027/DR/' + title +
        '.pdf\',\'x\');">' + num + '</a></td><td class="maintd">2027</td><td class="maintd">' + title + '</td>'
        '<td class="maintd"><div class="parent ruustatus3" id="r">Passed</div><table>'
        '<tr><td>First reading</td><td>:</td><td>' + first + '</td></tr>' +
        ('<tr><td>Passed At</td><td>:</td><td>' + passed + '</td></tr>' if passed else '') + '</table></td></tr>')
    page = ("<table>" + row("D.R.5/2027", "Artificial Intelligence Governance Bill 2027", "03/03/2027", "10/03/2027")
            + row("D.R.6/2027", "National Trust Fund Bill 2027", "04/03/2027") + "</table>").encode()
    conn = store.connect(tmp_path / "t.db")
    assert bills.sync_malaysia(conn, lambda u: page, log=lambda *_: None) == 1
    r = conn.execute("SELECT number, stage, stage_date, url FROM bills WHERE jurisdiction = 'MY'").fetchone()
    assert (r["number"], r["stage"], r["stage_date"]) == ("D.R.5/2027", "passed_chamber", "2027-03-10")
    assert r["url"].endswith("/Artificial%20Intelligence%20Governance%20Bill%202027.pdf")


def test_irish_ai_bills_from_the_oireachtas(tmp_path, monkeypatch):
    import json
    from aipulse import bills
    monkeypatch.setattr(bills.time, "sleep", lambda s: None)
    stage = lambda name, house, day, done=True: {"event": {"showAs": name, "stageCompleted": done, "dates": [{"date": day}],
                                                           "house": {"houseCode": house}, "chamber": {"showAs": house}}}
    page = {"results": [
        {"bill": {"billNo": "69", "billYear": "2026", "shortTitleEn": "Regulation of Artificial Intelligence Bill 2026",
                  "longTitleEn": "<p>Bill entitled an Act to give effect to the EU AI Act.</p>", "status": "Enacted",
                  "sponsors": [{"sponsor": {"by": {"showAs": "A Minister"}}}],
                  "stages": [stage("First Stage", "dail", "2026-03-02"), stage("Fifth Stage", "dail", "2026-05-20"),
                             stage("Fifth Stage", "seanad", "2026-07-08")],
                  "act": {"actNo": "21", "actYear": "2026", "dateSigned": "2026-07-21"}}},
        {"bill": {"billNo": "7", "billYear": "2026", "shortTitleEn": "Online Safety (Recommender Algorithms) Bill 2026",
                  "status": "Defeated", "stages": [stage("First Stage", "dail", "2026-01-22")],
                  "mostRecentStage": {"event": {"dates": [{"date": "2026-09-17"}]}}}},
        {"bill": {"billNo": "8", "billYear": "2026", "shortTitleEn": "Planning Bill 2026", "status": "Current",
                  "stages": [stage("First Stage", "dail", "2026-01-23")]}}]}
    conn = store.connect(tmp_path / "t.db")
    assert bills.sync_ireland(conn, lambda u: json.dumps(page).encode(), log=lambda *_: None) == 2  # not the Planning Bill
    law = conn.execute("SELECT stage, stage_date, url, history FROM bills WHERE key = 'IE-2026-69'").fetchone()
    assert (law["stage"], law["stage_date"]) == ("signed", "2026-07-21") and law["url"].endswith("/bills/bill/2026/69/")
    assert [h["stage"] for h in json.loads(law["history"])] == ["introduced", "passed_chamber", "passed_legislature", "signed"]
    assert conn.execute("SELECT stage FROM bills WHERE key = 'IE-2026-7'").fetchone()[0] == "vetoed"  # defeated
    card = conn.execute("SELECT title, summary, source, action FROM items WHERE bill = 'IE-2026-69'").fetchone()
    assert card["source"] == "Houses of the Oireachtas" and card["action"] == "law" and "Minister" not in card["summary"]


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


def test_taiwan_laws_from_the_legislative_yuan():
    from aipulse import bills
    page = ('<table><tr><td>序號</td><td>法名稱</td><td>附帶決議</td><td>通過日期</td><td>公布日期</td></tr>'
            '<tr><td>1</td><td><a href=x><font class=hl>人工智慧</font>基本法</a></td><td></td>'
            '<td>1141223</td><td>1150114</td></tr></table>')
    assert bills.tw_laws(page) == [("人工智慧基本法", "2025-12-23", "2026-01-14")]


def test_korean_ai_laws_from_the_law_database(tmp_path):
    from aipulse import bills
    item = lambda name, eff, typ, no, prom, kind: f'<a title="{name}[시행 {eff}] [{typ} 제{no}호, {prom}, {kind}]">'
    page = (item("인공지능 발전과 신뢰 기반 조성 등에 관한 기본법", "2026. 1. 22.", "법률", "20676", "2025. 1. 21.", "제정")
            + item("인공지능 발전과 신뢰 기반 조성 등에 관한 기본법", "2026. 7. 21.", "법률", "21311", "2026. 1. 20.", "일부개정")
            + item("국가인공지능위원회의 설치 및 운영에 관한 규정", "2024. 8. 6.", "대통령령", "34787", "2024. 8. 6.", "제정")
            + item("국가인공지능위원회의 설치 및 운영에 관한 규정", "2025. 9. 4.", "대통령령", "35735", "2025. 9. 4.", "타법폐지"))
    laws = bills.kr_laws(page)
    act = laws["인공지능 발전과 신뢰 기반 조성 등에 관한 기본법"]
    assert act["number"] == "Act No. 20676"
    assert [(h["stage"], h["date"]) for h in act["history"]] == [("signed", "2025-01-21"), ("in_force", "2026-01-22")]
    assert laws["국가인공지능위원회의 설치 및 운영에 관한 규정"]["history"][-1] == \
        {"date": "2025-09-04", "stage": "withdrawn", "text": "폐지"}
    assert bills.kr_english("인공지능 발전과 신뢰 기반 조성 등에 관한 기본법 시행령")[0].startswith(
        "Enforcement Decree of the Framework Act on the Development of AI")
    assert bills.kr_english("새로운 인공지능 법") == ("", "")  # unknown: keeps its Korean name


def test_new_us_bills_get_an_interim_summary_until_crs_writes_one(tmp_path):
    import json
    from aipulse import bills
    assert bills.us_purpose("A bill to establish the Artificial Intelligence Horizon Fund, and for other purposes.") == \
        "Would establish the Artificial Intelligence Horizon Fund."
    assert bills.us_purpose("To amend title 18 to prohibit AI deepfakes.") == "Would amend title 18 to prohibit AI deepfakes."
    assert bills.us_purpose("To establish the Department of AI and to provide for its regulation.") ==         "Would establish the Department of AI and provide for its regulation."
    conn = store.connect(tmp_path / "t.db")
    bills.connect_tables(conn)
    ctx = {"sponsor": "Sen. Mark Kelly (D-AZ)", "cosponsors": 2, "committees": ["Senate Finance Committee"], "short_title": ""}
    conn.execute("INSERT INTO meta VALUES ('us-context:US-119-s-5518', ?)", (json.dumps(ctx),))
    bill = {"key": "US-119-s-5518", "jurisdiction": "US", "number": "S. 5518", "url": "https://c.gov/s5518",
            "title": "A bill to establish the Artificial Intelligence Horizon Fund, and for other purposes.",
            "source": "congress.gov", "history": [{"date": "2026-09-24", "stage": "introduced", "text": "Introduced"}]}
    bills.upsert(conn, bill)
    title, summary = conn.execute("SELECT title, summary FROM items").fetchone()
    assert title == "S. 5518: A bill to establish the Artificial Intelligence Horizon Fund"
    assert summary == ("Would establish the Artificial Intelligence Horizon Fund. Introduced by Sen. Mark Kelly (D-AZ) "
                       "with 2 cosponsors; referred to the Senate Finance Committee.")
    bills.upsert(conn, {**bill, "summary": "This bill establishes a fund for AI research."})  # CRS arrives
    assert conn.execute("SELECT summary FROM items").fetchone()[0] == "This bill establishes a fund for AI research."


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


def test_a_study_reported_by_the_news_is_not_a_release():
    from aipulse import classify as c
    study = ("AI agents do more of the work in model development, but humans still make the decisions",
             "A research team analyzed 769 task logs from building its own AI model. AI agents supplied up to 55 percent "
             "of method proposals, but humans made more than 85 percent of final decisions.")
    assert c.categorize(*study, "news") == "news" and not c.launched(*study)
    assert c.categorize("Nvidia drops a free 100M-parameter model that identifies up to eight speakers in real time",
                        "Nvidia released Nemotron 3 Diarization, an AI model that identifies which speaker is talking.",
                        "news") == "tool"
    assert c.launched("Researchers release open-source model for protein design", "A team at MIT released it.")
    assert c.launched("Robbyant Open Sources LingBot World: a Real Time World Model", "")
    assert not c.launched("Financial AI startup Model ML nabs $75M investment", "The startup raised money for its model.")


def test_a_practitioners_blog_is_never_a_release():
    from aipulse.collect import stream_of, reclassify
    from aipulse.sources import SOURCES
    launch = ("Jev introduces a new shape of LLM - System One, aka Decision Models", "Jev released System One today.")
    news = {"name": "E", "url": "https://e.com/feed", "category": "news"}
    blog = {**news, "name": "Simon Willison", "no_releases": True}
    assert stream_of(news, *launch, "https://e.com/1") == "tool"  # a newsroom reporting a launch: a release
    assert stream_of(blog, *launch, "https://e.com/2") == "news"  # a practitioner writing about it: Industry
    assert {s["name"] for s in SOURCES if s.get("no_releases")} >= {"Simon Willison", "Lil'Log", "METR"}
    # one already stored as a release moves to Industry
    conn = store.connect(":memory:")
    store.insert(conn, {"id": "p1", "source": "Simon Willison", "category": "tool", "title": launch[0], "summary": launch[1],
                        "url": "https://simonwillison.net/p1", "date": "2026-10-05"})
    reclassify(conn)
    assert conn.execute("SELECT category FROM items").fetchone()[0] == "news"


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


def test_people_leaving_comparisons_and_a_body_using_ai_are_not_misfiled():
    from aipulse import classify as c, cluster
    # someone leaving is never a release, whatever the summary says was "released"
    assert not c.launched("Another OpenAI safety departure adds to a pattern of researchers leaving with public warnings",
                          "He points to AI agents that were accidentally released.")
    assert not c.launched("Yann LeCun leaves Meta to launch new AI startup", "")
    assert c.launched("Meta releases first multimodal Llama-4 models, leaves EU out in the cold", "")
    assert c.launched("Google's Gemma 4 puts free agentic AI on your phone and no data ever leaves the device", "Google released Gemma 4.")
    # a comparison isn't a power story; the real thing still is
    assert not c.infra_story("Former OpenAI employee says AI should be regulated like nuclear power plants")
    assert c.infra_story("AI boom could delay US coal phase-out plans as electricity demand soars")
    # an agency using AI isn't a regulatory action; a proposal still is
    assert c.regulatory_action("NITDA deploys AI to turn Nigerian youths’ ideas into policy proposals") is None
    assert c.regulatory_action("Kenya proposes AI bill") == "proposal"
    # a body that "moves to regulate" proposes rules (the fine is a planned one); a move against one company doesn't
    assert c.regulatory_action("FCCPC moves to regulate AI marketing, businesses face N100 million penalty") == "proposal"
    assert c.regulatory_action("FCC moves to outlaw AI-generated robocalls") == "proposal"
    assert c.regulatory_action("Trump moves to ban Anthropic from the US government") is None
    # one person leaving, told by two outlets in different words, is one card
    a = {"id": "a", "date": "2026-10-03", "category": "news", "source": "The Decoder",
         "title": "Another OpenAI safety departure adds to a pattern of researchers leaving with public warnings",
         "summary": "David Robinson, who worked on safety systems at OpenAI, left the company and is blasting its safety culture."}
    b = {"id": "b", "date": "2026-10-03", "category": "news", "source": "TechCrunch AI",
         "title": "OpenAI safety employee resigns, claiming the company’s ‘culture is broken’",
         "summary": "By his own admission, David Robinson is “something of a cliché”: an employee who resigns with a warning."}
    idf = {"david": 6.0, "robinson": 6.0}
    assert cluster._same_person(a, b, idf)
    assert not cluster._same_person({**a, "title": "Meta launches Muse"}, b, idf)  # a shared name alone isn't one event


def test_papers_get_research_and_news_about_studies_gets_study_report():
    from aipulse import classify as c
    tags = c.tags_for("AI access makes people unwilling to say I don't know, study finds", "A new study found that...")
    assert "Study Report" in tags and "Research" not in tags
    assert "Study Report" not in c.tags_for("Another Google DeepMind researcher quits", "He left the lab.")



def test_article_lead_skips_menus_bylines_and_contents():
    from aipulse import feeds
    page = ('<header><p>Research blog home and all the other sections of this site you can visit.</p></header><h1>Title</h1>'
            '<nav><p>Contents: How it works, Results, Limitations of this approach and how to use the model.</p></nav>'
            '<p class="[&>:last-child]:mb-0">Upvote 33 +27 Jane Doe Follow Lab and more people who wrote the post.</p>'
            '<p>Jane Doe, Research Scientist, Google Research</p>'
            '<p>Today, we release an experimental draft model for our vision-language model, with faster inference.</p>')
    assert feeds.article_lead(page.encode()).startswith("Today, we release an experimental draft model")


def test_company_blog_posts_are_releases_only_when_something_launches():
    # 140 random 2026 posts from the labs' and companies' own blogs, labelled by hand: a release is something
    # new people can use (a model, product, feature, API, open release). Deals, customer stories, guides,
    # opinion, research explainers, programmes and events aren't. The old default (every post a release)
    # scored 35-46% here.
    import csv
    from aipulse import classify
    rows = list(csv.DictReader((FIX / "blog_releases.csv").open(encoding="utf-8", newline="")))
    right = sum((classify.categorize(r["title"], r["text"], "tool") == "tool") == (r["release"] == "1") for r in rows)
    assert right / len(rows) >= 0.9, right
    letter = ("Cloudflare’s 2026 Annual Founders’ Letter",
              "The Internet is changing more today than at any point since Cloudflare launched back on September 27, 2010.")
    assert classify.categorize(*letter, "tool") == "news"
    assert not classify.launched(*letter)  # a launch in 2010 is history


def test_rss_daily_digest_per_stream():
    import xml.etree.ElementTree as ET
    from datetime import date
    from aipulse import rss
    card = lambda i, cat, added, dated=None: {"id": f"c{i}", "title": f"Story {i} & more", "summary": "What happened.",
                                              "url": f"https://ex.com/{i}", "source": "Outlet", "category": cat,
                                              "date": dated or added[:10], "added_at": added, "tags": []}
    cards = [card(1, "tool", "2026-09-27T00:20:00+00:00"), card(2, "tool", "2026-09-27T18:25:00+00:00"),
             card(3, "news", "2026-09-27T06:10:00+00:00"), card(4, "tool", "2026-09-26T12:00:00+00:00"),
             card(5, "tool", "2026-09-28T06:00:00+00:00"),                 # today: not over yet
             card(6, "tool", "2026-09-27T12:00:00+00:00", "2026-09-22")]   # collected on the 27th, but happened on the 22nd
    days = rss.daily(cards, "tool", today=date(2026, 9, 28))
    assert list(days) == [date(2026, 9, 27), date(2026, 9, 26), date(2026, 9, 22)]  # by the day it happened
    assert [c["id"] for c in days[date(2026, 9, 27)]] == ["c2", "c1"]     # only what's dated the 27th, newest first
    root = ET.fromstring(rss.feed_xml("releases", cards, today=date(2026, 9, 28)))  # well-formed, "&" escaped
    posts = root.findall("channel/item")
    assert [p.findtext("title") for p in posts] == ["Releases · Sun 27 Sep 2026", "Releases · Sat 26 Sep 2026",
                                                    "Releases · Tue 22 Sep 2026"]
    assert 'href="https://ex.com/2"' in posts[0].findtext("description") and "Story 2 &amp; more" in posts[0].findtext("description")
    assert posts[0].findtext("pubDate") == "Mon, 28 Sep 2026 00:00:00 +0000"   # published once the day is over
    assert not ET.fromstring(rss.feed_xml("policy", cards, today=date(2026, 9, 28))).findall("channel/item")



def test_email_digest_lists_the_chosen_streams_for_one_day(monkeypatch):
    from datetime import date
    from aipulse import digest
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    card = lambda i, cat, added: {"id": f"c{i}", "title": f"Story {i} <b>", "summary": "What happened.", "url": f"https://ex.com/{i}",
                                  "source": "Outlet", "category": cat, "date": added[:10], "added_at": added}
    cards = [card(1, "tool", "2026-09-27T06:00:00+00:00"), card(2, "regulation", "2026-09-27T18:00:00+00:00"),
             card(3, "news", "2026-09-27T12:00:00+00:00"), card(4, "tool", "2026-09-28T00:30:00+00:00")]
    subject, text, html = digest.build(cards, ["releases", "regulation"], date(2026, 9, 27), layout="full")
    assert subject == "AI Pulse daily · Sunday, 27 September 2026"  # no short forms
    assert "Let's explore what happened in AI on Sunday, 27 September 2026." in text
    assert "6-hour" not in text + html and "Daily update" not in html  # the subject already names the day
    assert "Story 1" in text and "Story 2" in text and "Story 3" not in text and "Story 4" not in text  # chosen streams, that day
    assert "Story 1 &lt;b&gt;" in html                                     # headlines are escaped
    assert "https://projectaipulse.com/#subscribe" in html and "You chose: Releases, Regulation tracker" in html
    assert "mailto:" not in html  # changing streams and unsubscribing never need an email
    assert "Releases: 1 (" in text and "Regulation tracker: 1 (" in text and "vs Sat" not in text + html  # the day at a glance
    assert ">Regulation tracker</a>" in html and "came up most" not in text  # nobody named twice: no line
    assert "[Release] Story 1" in text and "Type</th>" in html  # one table: type | story | source
    assert "https://projectaipulse.com/feeds/releases.xml" in html and "feeds/news.xml" not in html  # chosen feeds
    cards[0]["also"] = [{"title": "Same outlet, other post", "source": "Outlet", "url": "https://ex.com/x", "date": "2026-09-27"},
                        {"title": "Story 1 elsewhere", "source": "Other", "url": "https://other.com/1", "date": "2026-09-27"}]
    _, text, html = digest.build(cards, ["releases"], date(2026, 9, 27), layout="full")
    assert "Also reported by Other" in text and ">Outlet</a>" not in html   # never the story's own outlet
    assert digest.build(cards, ["policy"], date(2026, 9, 27)) is None      # nothing that day: no email


def test_industry_news_is_labelled_not_moved(monkeypatch):
    from datetime import date
    from aipulse import classify, digest
    assert classify.news_kind("A Coding Guide to Google Research's MSEB: Writing Sound Encoders", "", False) == "tutorial"
    assert classify.news_kind("Inside cuDNN's Graph API", "Learn how to build custom kernel fusions", False) == "tutorial"
    assert classify.news_kind("What to expect at NetApp INSIGHT: Join theCUBE Sept. 30", "", False) == "event"
    assert classify.news_kind("How Trane gets building insights 60x faster with Amazon Bedrock", "", True) == "blog"
    assert classify.news_kind("Anthropic signs $11.6 billion cloud deal with Akamai", "", False) == "news"
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    card = lambda i, kind: {"id": f"n{i}", "title": f"Story {i}", "summary": "", "url": f"https://ex.com/{i}", "source": f"S{i}",
                            "category": "news", "kind": kind, "date": "2026-09-27", "added_at": "2026-09-27T10:00:00+00:00"}
    _, text, html = digest.build([card(1, "tutorial"), card(2, "news"), card(3, "blog")], ["news"], date(2026, 9, 27),
                                 layout="full")
    assert classify.news_kind("Can Muse overcome Meta's trust issues?", "", False) == "analysis"
    assert classify.news_kind("AI access makes people unwilling to say I don't know, study finds", "", False) == "study"
    assert classify.news_kind("Anthropic researcher quits, warns against self-improving AI", "", False) == "news"
    assert classify.news_kind("AI agents do more of the work in model development, but humans still make the decisions",
                              "A research team analyzed 769 task logs from building its own AI model.", False) == "study"
    # Industry in groups, each headed once with what it holds: News first, then company blogs, tutorials...
    # One table, Industry ordered by tag and every story tagged with its sub-category, never just "Industry".
    order = [text.index(t) for t in ("[News] Story 2", "[Company blog] Story 3", "[Tutorial] Story 1")]
    assert order == sorted(order) and "Industry: 3 (1 news · 1 company blog · 1 tutorial)" in text
    assert ">Opinion &amp; analysis<" not in html and ">Company blog<" in html and "[Industry]" not in text


def test_digest_is_checked_before_it_is_sent(monkeypatch):
    from datetime import date
    from aipulse import digest, quality
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    day = date(2026, 9, 27)
    card = lambda i, cat, **k: {"id": f"q{i}", "title": f"OpenAI story number {i}", "summary": "About AI.", "url": f"https://ex.com/{i}",
                                "source": "MarkTechPost", "category": cat, "kind": "news" if cat == "news" else None,
                                "date": "2026-09-27", "added_at": "2026-09-27T10:00:00+00:00", **k}
    good = [card(i, "news") for i in range(6)]
    streams = ["news", "policy"]
    assert quality.problems(digest.by_streams(good, streams, day), good, day) == []
    bad = [card(1, "news", source="GOV.UK"), card(2, "news", title="No title"), card(3, "regulation", url="https://arxiv.org/abs/1"),
           card(4, "tool", title="NIST publishes new AI standards profile"), card(5, "policy", action="incident"),
           card(6, "news", summary="Donâ€™t miss it"), card(7, "news", url="https://ex.com/1"), card(8, "news", kind="gossip")]
    found = "\n".join(quality.problems(digest.by_streams(bad, ["releases", *streams, "regulation"], day), bad, day))
    for p in ("government's own publication (GOV.UK) in Industry", "no real headline", "research paper in Regulation tracker",
              "standards story in Releases", "AI-incident in Policy", "garbled characters in the summary", "shown twice",
              "no label in Industry"):
        assert p in found, p
    assert "No stories at all" in "".join(quality.problems(digest.by_streams([], streams, day), [], day))
    # A general outlet's story that doesn't name AI is left out of the email, not a reason to hold it.
    off = card(9, "news", source="South China Morning Post", title="Alibaba Cloud opens data centres in Europe", summary="")
    assert off not in digest.by_streams([*good, off], streams, day)["news"] and digest.left_out([*good, off], streams, day) == [off]
    # A thin day is sent, saying so.
    _, text, _ = digest.build(good[:2], streams, day)
    assert "A quiet day for AI: only 2 stories" in text and "Weekends are usually slow" in text
    assert "quiet day" not in digest.build(good, streams, day)[1]
    subject, text, _ = quality.alert(day, ["x"], streams)
    assert "HELD" in subject and "was not sent to anyone" in text


def test_standards_are_tracker_cards_that_survive_reclassify(tmp_path):
    from datetime import date
    from aipulse import bills, standards
    conn = store.connect(tmp_path / "t.db")
    urls = [s[4] for s in standards.STANDARDS]
    assert len(set(urls)) == len(urls) and all(u.startswith("https://") for u in urls)
    assert all(date.fromisoformat(s[3]) <= date.today() for s in standards.STANDARDS)
    assert set(standards.SOURCES) <= set(bills.OFFICIAL_SOURCES)  # never re-sorted into Policy
    store.insert(conn, {"title": "Information technology — Artificial intelligence — Management system (ISO/IEC 42001)",
                        "summary": "", "url": "https://oecd.ai/x", "source": "OECD.AI", "category": "policy", "date": "2023-01-01"})
    assert standards.sync(conn) == len(urls)
    assert standards.sync(conn) == 0  # idempotent
    reclassify(conn)
    tracker = store.query(conn, "regulation", limit=100)
    assert len(tracker) == len(urls) and all(i["action"] == "standard" and i["jurisdictions"] == ["INTL"] for i in tracker)
    assert not store.query(conn, "policy")  # OECD.AI's copy of ISO/IEC 42001 is replaced by the official page


def test_standard_names_from_oecd():
    from aipulse.oecd import is_standard
    for t in ["Voluntary AI Safety Standard", "AI Technical Standard", "Algorithmic Transparency Recording Standard",
              "Standards for the Implementation of Inclusive AI Systems"]:
        assert is_standard(t), t
    for t in ["National Occupational Standard Framework for Data and Artificial Intelligence (NOSF)",
              "Plan for Federal Engagement in Developing Technical Standards and Related Tools",
              "Mechanism for the Implementation of Principles and International Standards in AI",
              "AI Standardisation Committee", "National Data Strategy"]:
        assert not is_standard(t), t


def test_standards_news_is_never_a_release():
    from aipulse.classify import categorize
    assert categorize("NIST launches AI Agent Standards Initiative as autonomous AI moves into production", "", "news") == "policy"
    assert categorize("NIST releases a tool for testing AI model risk", "", "news") == "policy"
    assert categorize("Acme achieves ISO/IEC 42001 certification for its AI platform", "", "tool") == "news"
    assert categorize("OpenAI launches GPT-6 with new API features", "", "news") == "tool"  # releases unaffected


def test_translation_note_is_not_a_place():
    from aipulse.classify import tags_for
    note = " Machine-translated from Portuguese; the official text is linked."
    assert "Portugal" not in tags_for("PL 3392/2026: Establishes minimum standards for AI in judicial procedures", note)
    assert "Germany" not in tags_for("Motion: AI in the federal administration", note.replace("Portuguese", "German"))
    assert "Portugal" in tags_for("Portugal adopts an AI strategy", "")


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



def test_subscribers_come_from_the_signup_web_app(monkeypatch):
    import io
    import json as _json
    from datetime import date
    from aipulse import digest, subscribers as sb
    token = "0b7c3a52-6f7e-4f53-9d38-1f2a3b4c5d6e"
    data = {"ok": True, "unsubscribe": "https://script.google.com/macros/s/X/exec?action=unsubscribe&t=",
            "subscribers": [{"email": "Ana@Example.org", "streams": ["policy", "news", "bogus"], "token": token},
                            {"email": "not an address", "streams": ["news"], "token": token},
                            {"email": "bob@example.org", "streams": ["news"], "token": "../../etc"},
                            {"email": "cy@example.org", "streams": ["bogus"], "token": token}]}
    got = sb.readers(data)
    site_link = "https://projectaipulse.com/#unsubscribe=" + token
    none = {"more": [], "less": [], "words": [], "interests": [], "often": "daily"}  # a reader who made no choices
    assert got == {"ana@example.org": (["news", "policy"], data["unsubscribe"] + token, site_link, none)}  # malformed dropped
    # choices come through capped and cleaned, never in both lists
    chosen = sb.prefs_of({"more": ["Agents", "Asia", "Asia", "x", "Tutorial"], "less": ["Tutorial", 7], "words": ["  Tesla   Optimus "],
                          "interests": ["How hospitals   use AI", "how hospitals use AI", "?!", "x" * 300, "Nvidia", "One too many"]})
    assert chosen == {"more": ["Agents", "Asia"], "less": ["Tutorial"], "words": ["Tesla Optimus"],
                      "interests": ["How hospitals use AI", "x" * 150, "Nvidia"], "often": "daily"}  # tidied, once each, at most 3 of 150
    # how often: "weekly" (Sunday's email only) when asked for, anything else daily
    assert sb.prefs_of({"often": "weekly"})["often"] == "weekly" and sb.prefs_of({"often": "hourly"})["often"] == "daily"
    assert sb.choices_link(site_link) == "https://projectaipulse.com/#choices=" + token
    try:
        sb.readers({"ok": False})
        raise AssertionError("a refused list must stop the send")
    except RuntimeError:
        pass
    seen = []
    monkeypatch.setattr(sb.urllib.request, "urlopen", lambda url, timeout: (seen.append(url), io.BytesIO(_json.dumps(data).encode()))[1])
    assert sb.current("k" * 32, "https://script.google.com/macros/s/X/exec") == got
    assert seen == ["https://script.google.com/macros/s/X/exec?action=list&key=" + "k" * 32]
    monkeypatch.setattr(sb, "SIGNUP_URL", "https://script.google.com/macros/s/X/exec")
    assert sb.fill('const SIGNUP_URL = "__SIGNUP_URL__";') == 'const SIGNUP_URL = "https://script.google.com/macros/s/X/exec";'
    # Each reader's email has their own one-click unsubscribe, in the footer and as the mail apps' button.
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    card = {"id": "p1", "title": "OpenAI sued over AI training data", "summary": "", "url": "https://ex.com/1", "source": "S",
            "category": "policy", "date": "2026-09-27", "added_at": "2026-09-27T10:00:00+00:00"}
    _, one_click, link, _ = got["ana@example.org"]
    subject, text, html = digest.build([card], ["policy"], date(2026, 9, 27), link)
    # the reader's own link opens the form filled in with their streams and choices
    assert f"Unsubscribe: {link}" in text and f"Change my streams and choices: {sb.choices_link(link)}" in text
    assert "script.google.com" not in text + html  # links in the email only go to the site (spam filters)
    msg = digest._message("ana@example.org", subject, text, html, one_click)
    assert msg["List-Unsubscribe"] == f"<{one_click}>" and msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "List-Unsubscribe" not in digest._message("digest@example.com", subject, text, html)  # a test send has none


def test_signup_page_and_web_app_agree():
    import re
    from pathlib import Path
    from aipulse import rss
    root = Path(__file__).resolve().parent.parent
    page = (root / "templates" / "index.html").read_text(encoding="utf-8")
    script = (root / "apps-script" / "Code.gs").read_text(encoding="utf-8")
    # The form's streams are the web app's streams, and the fields it posts are the ones the web app reads.
    assert re.findall(r'type="checkbox" value="(\w+)"', page) == list(rss.FEEDS)
    assert all(f"{n}:" in script for n in rss.FEEDS)
    assert 'action: "subscribe", email, streams: streams.join(","), website' in page
    assert all(f"p.{f}" in script for f in ("email", "streams", "website"))
    assert "LIST_KEY" in script and not re.search(r"LIST_KEY\s*=\s*['\"]", script)  # the key is never in the code
    assert 'type="email"' in page and "mailto:" not in page.split('id="subscribe"')[1].split("</dialog>")[0]
    # Emails link to the site, which handles the confirm and unsubscribe links; the web app sends only site links.
    assert "#(confirm|unsubscribe)=" in page and 'SITE + "#confirm="' in script
    assert not re.search(r"getUrl\(\) \+ \"\?action=confirm", script)


def test_anthropic_news_page_and_its_launches():
    from aipulse import collect as col
    from aipulse.sources import SOURCES
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
    src = next(s for s in SOURCES if s["name"] == "Anthropic News")
    # A launch has its own page; other posts are judged by the headline, not by launch words in their description.
    assert col.blog_category(src, posts[0]["title"], posts[0]["summary"], posts[0]["url"]) == "tool"
    assert col.blog_category(src, posts[1]["title"], "We're introducing a new life sciences research group", posts[1]["url"]) == "news"
    assert col.blog_category(src, posts[2]["title"], "Claude models gained unauthorized access to systems", posts[2]["url"]) == "news"
    other = {"name": "Blog", "category": "tool"}
    assert col.blog_category(other, "Introducing Gemma 4", "", "https://ex.com/gemma-4") == "tool"  # other blogs unchanged


def test_quick_run_reads_only_lab_blogs(tmp_path, monkeypatch):
    import sys
    from aipulse import __main__ as cli
    seen = {}
    monkeypatch.setattr(cli, "collect", lambda conn, sources, max_age_days: seen.setdefault("sources", sources) and 0)
    monkeypatch.setattr(sys, "argv", ["aipulse", "--db", str(tmp_path / "t.db"), "collect", "--labs"])
    cli.main()
    assert seen["sources"] and {s["category"] for s in seen["sources"]} == {"tool"}
    assert "Anthropic News" in {s["name"] for s in seen["sources"]}


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


def test_release_notes_keep_only_the_labs_own_launches(tmp_path):
    from aipulse import collect as col
    from aipulse.sources import SOURCES
    xai = (b'<h2 id="september">September</h2><h3 id="grok-47"><a href="#grok-47">Grok 4.7</a></h3><p>Grok 4.7, the '
           b'frontier model, is now available on the xAI API.</p><h3 id="safety-field">safety_identifier request field</h3>'
           b'<p>You can now send safety_identifier.</p><h3 id="old-retire">grok-imagine retirement on November 2</h3><p>Retired.</p>')
    pplx = (b'<span data-as="p"><strong>Claude Opus 5.5</strong></span><span data-as="p">The Agent API now supports '
            b'anthropic/claude-opus-5-5.</span><span data-as="p"><strong>Introducing New and Improved Sonar Models</strong>'
            b'</span><span data-as="p">We are excited to announce the launch of our latest Sonar models.</span>'
            b'<span data-as="p"><strong>Options: "low" : Faster</strong></span><span data-as="p">x</span>')
    entries = feeds.parse_xai_notes(xai)
    assert [e["title"] for e in entries] == ["Grok 4.7", "safety_identifier request field", "grok-imagine retirement on November 2"]
    assert entries[0]["url"] == "https://docs.x.ai/developers/release-notes?entry=grok-47#grok-47"
    assert len({store.item_id(e["url"]) for e in entries}) == 3  # each entry is its own story
    assert [e["title"] for e in feeds.parse_perplexity_notes(pplx)] == ["Claude Opus 5.5", "Introducing New and Improved Sonar Models"]
    conn = store.connect(tmp_path / "t.db")
    pages = {"https://docs.x.ai/developers/release-notes": xai, "https://docs.perplexity.ai/changelog": pplx}
    labs = [s for s in SOURCES if s["name"] in ("xAI", "Perplexity")]
    for src in labs:
        assert col.page_list_entries(conn, src, pages.get) == []  # first read: remembered only
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, '[]')", (f"page_list:{src['name']}",))  # as if all were new
    kept = {src["name"]: [e["title"] for e in col.page_list_entries(conn, src, pages.get)] for src in labs}
    # Only their own products' launches: not an API field, a retirement, or another lab's model Perplexity now offers.
    assert kept == {"xAI": ["Grok 4.7"], "Perplexity": ["Introducing New and Improved Sonar Models"]}


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


def test_daily_email_shows_the_ten_that_mattered_then_headlines(monkeypatch):
    from datetime import date
    from aipulse import digest
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    card = lambda i, cat, outlets=0, kind="news": {
        "id": f"s{i}", "title": f"Story {i}", "summary": f"What happened in story {i}.", "url": f"https://ex.com/{i}",
        "source": f"Outlet {i}", "category": cat, "kind": kind if cat == "news" else None, "date": "2026-09-28",
        "added_at": f"2026-09-28T{10 + i % 10:02d}:00:00+00:00",
        "also": [{"title": f"Story {i}", "source": f"Other {k}", "url": f"https://o{k}.com/{i}", "date": "2026-09-28"}
                 for k in range(outlets)]}
    cards = ([card(0, "tool", 4)] + [card(i, "news", 2 if i == 1 else 0) for i in range(1, 16)]
             + [card(20, "news", 0, "tutorial"), card(21, "policy")])
    subject, text, html = digest.build(cards, ["releases", "news", "policy"], date(2026, 9, 28))  # short by default
    assert subject == "AI Pulse daily · Monday, 28 September 2026" and "Here are the 10 that mattered most." in text
    top = text.split("Here are the 10 that mattered most.")[1].split("THE REST OF THE DAY")[0]
    assert top.index("Story 0") < top.index("Story 1") and "Outlet 0 +4 outlets" in top  # most reported first
    assert top.count("• [") == 10 and "Story 20" not in top  # ten, never a tutorial
    assert "1. " not in top  # not numbered
    rest = text.split("THE REST OF THE DAY")[1]
    assert "Releases (" not in rest and "All in the top 10: Releases, Policy." in rest  # one row for them
    _, text2, _ = digest.build(cards, ["releases", "news", "infra"], date(2026, 9, 28))
    assert "Nothing new today: Infra & climate." in text2 and "Infra & climate (" not in text2  # an empty stream too
    assert "+5 more: https://projectaipulse.com/#news (incl. 1 tutorial)" in rest  # 8 of 15 in the top, 3 listed
    assert "Choose the full email" not in html and html.count('class="cell"') == 10 and "@media" in html  # two by five, one column on a phone


def test_every_email_links_to_the_days_full_email(monkeypatch):
    from datetime import date
    from aipulse import digest
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    card = lambda i, cat: {"id": f"f{i}", "title": f"Story {i}", "summary": "", "url": f"https://ex.com/{i}",
                           "source": "S", "category": cat, "date": "2026-09-28", "added_at": "2026-09-28T10:00:00+00:00"}
    cards = [card(i, "research") for i in range(3)] + [card(9, "tool")]
    _, text, html = digest.build(cards, ["research"], date(2026, 9, 28))  # a Research-only reader
    assert "https://projectaipulse.com/daily/2026-09-28.html" in text + html
    assert "https://projectaipulse.com/#glossary" in text and "#glossary" in html  # every email points to the glossary
    assert "A lighter day in your streams: 3 stories" in text and "Here are all 3 stories of the day." in text
    # the page itself: every stream, the full table, a sign-up line instead of a reader's own settings
    _, text, html = digest.build(cards, ["releases", "news", "research", "regulation", "policy"], date(2026, 9, 28),
                                 layout="full", web=True)
    assert "Type</th>" in html and "Story 9" in text and "Get AI Pulse daily in your inbox" in text
    assert "Unsubscribe" not in text and "You chose" not in text


def test_stories_carry_a_country_and_the_email_shows_tags(monkeypatch):
    from datetime import date
    from aipulse import digest
    assert classify.tags_for("AMD is acquiring AI company World Labs in a deal worth more than $8 billion", "")[:3] == [
        "AMD", "World Labs", "United States"]
    assert classify.tags_for("StepFun Step 5 Preview: 600B MoE", "")[:2] == ["StepFun", "China"]
    assert "Germany" in classify.tags_for("Mistral opens a Munich hub", "Physics AI research in Germany")  # named place wins
    assert "France" not in classify.tags_for("Mistral opens a Munich hub", "Physics AI research in Germany")
    assert classify.tags_for("A minimax approach to games", "") == [] or "MiniMax" not in classify.tags_for("A minimax approach to games", "")
    assert "Perplexity" not in classify.tags_for("Perplexity of language models under distribution shift", "")
    assert "Perplexity" in classify.tags_for("Perplexity launches Comet for everyone", "")
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    card = {"id": "t1", "title": "Nvidia says its new AI safety platform can contain rogue agents", "summary": "",
            "url": "https://ex.com/1", "source": "The Verge AI", "category": "news", "kind": "news", "date": "2026-09-28",
            "added_at": "2026-09-28T10:00:00+00:00", "tags": []}  # stored before the new rules: tags worked out afresh
    assert digest.story_tags(card)[0] == "United States"  # countries first
    _, text, html = digest.build([card], ["news"], date(2026, 9, 28))
    assert "#United States #Nvidia #Agents #Safety" in text and "The Verge AI · #United States · #Nvidia<" in html  # two in the table


def test_glossary_explains_the_hard_words_in_stories():
    from datetime import date
    from pathlib import Path
    from aipulse import glossary
    assert len({e["id"] for e in glossary.ENTRIES}) == len(glossary.ENTRIES)
    assert {e["group"] for e in glossary.ENTRIES} <= set(glossary.GROUPS)
    assert glossary.terms_in("introducing PipSqueak 3, ShortSqueak, and (c.ai) lite") == ["character-ai"]
    assert glossary.terms_in("Holo4 comes in 27B dense and 35B-A3B Mixture of Experts") == ["parameters", "mixture-of-experts"]
    assert "parameters" not in glossary.terms_in("Instinct raises $1B Series C at a $10B valuation")  # money, not model size
    assert glossary.terms_in("add 250 ml of milk") == []  # acronyms only in capitals
    cards = [{"date": "2026-09-28", "title": "A RAG pipeline for agents", "summary": ""},
             {"date": "2026-08-01", "title": "An old RAG story", "summary": ""}]
    rag = next(e for e in glossary.payload(cards, date(2026, 9, 29))["entries"] if e["id"] == "rag")
    assert rag["recent"] == 1 and rag["search"] == "RAG" and rag["match"]
    page = Path("templates/index.html").read_text(encoding="utf-8")
    assert 'id="glossary-open"' in page and page.index('id="subscribe-open"') < page.index('id="glossary-open"') and 'id="theme"' not in page  # one light theme
    assert 'fetch("glossary.json"' in page


def test_word_of_the_day_rotates_through_the_glossary(monkeypatch):
    from datetime import timedelta
    from aipulse import digest, glossary
    start, n = glossary.ROTATION_START, len(glossary.ENTRIES)
    words = [glossary.word_of_the_day(start + timedelta(days=k))["id"] for k in range(n)]
    assert len(set(words)) == n  # every word once before any comes back
    assert glossary.word_of_the_day(start + timedelta(days=n)) == glossary.word_of_the_day(start)
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    day = start + timedelta(days=words.index("rag"))
    card = {"id": "w1", "title": "A RAG pipeline for support teams", "summary": "", "url": "https://ex.com/rag",
            "source": "S", "category": "news", "kind": "news", "date": day.isoformat(), "added_at": f"{day}T10:00:00+00:00"}
    _, text, html = digest.build([card], ["news"], day)
    assert "WORD OF THE DAY: RAG" in text and "Where it came up: A RAG pipeline for support teams" in text
    assert "#glossary=rag" in html and "Word of the day</div>" in html


def test_word_of_the_day_is_a_specialist_word(monkeypatch):
    from datetime import date
    from aipulse import digest, glossary
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    assert digest.SPECIALIST <= {e["id"] for e in glossary.ENTRIES} and "chain-of-thought" not in digest.SPECIALIST
    day = date(2026, 10, 5)
    card = lambda i, title: {"id": i, "title": title, "summary": "", "url": f"https://ex.com/{i}", "source": "S",
                             "category": "news", "kind": "news", "date": day.isoformat(), "added_at": f"{day}T10:00:00+00:00"}
    # an everyday word (Foundation model) is passed over for the specialist one (KV cache)
    _, text, _ = digest.build([card("a", "A new foundation model trims its KV cache")], ["news"], day)
    assert "WORD OF THE DAY: KV cache" in text
    # a day with no specialist word: the rotation, among the specialist words only
    _, text, _ = digest.build([card("b", "A foundation model for weather")], ["news"], day)
    assert f"WORD OF THE DAY: {glossary.word_of_the_day(day, digest.SPECIALIST)['term']}" in text


def test_email_asks_readers_to_forward_it(monkeypatch):
    from datetime import date
    from aipulse import digest
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    card = {"id": "f1", "title": "Story 1", "summary": "", "url": "https://ex.com/f1", "source": "S", "category": "news",
            "kind": "news", "date": "2026-10-05", "added_at": "2026-10-05T10:00:00+00:00"}
    _, text, html = digest.build([card], ["news"], date(2026, 10, 5))
    assert "Forward this email" in text and "Forward this email" in html
    _, text, _ = digest.build([card], ["news"], date(2026, 10, 5), layout="full", web=True)
    assert "Forward this email" not in text  # the site's page asks visitors to sign up instead


def test_dead_links_are_left_out_of_the_email(monkeypatch):
    import io
    import socket
    import urllib.error
    from aipulse import quality
    monkeypatch.setattr(quality.feeds, "allowed", lambda url: "blocked" not in url)
    def opener(req, timeout, context):
        url = req.full_url
        if "gone" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        if "nosite" in url:
            raise urllib.error.URLError(socket.gaierror("no such host"))
        if "shy" in url:
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)  # a careful site, not a dead link
        return io.BytesIO(b"ok")
    monkeypatch.setattr(quality.urllib.request, "urlopen", opener)
    stories = [{"url": f"https://ex.com/{k}", "title": k} for k in ("fine", "gone", "nosite", "shy", "blocked-gone")]
    assert [c["title"] for c in quality.dead_links({"news": stories})] == ["gone", "nosite"]


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


def test_email_opens_with_the_count_then_the_word_then_the_full_email(monkeypatch):
    from datetime import date
    from aipulse import digest
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    card = {"id": "o1", "title": "Story 1", "summary": "", "url": "https://ex.com/o1", "source": "S", "category": "news",
            "kind": "news", "date": "2026-09-28", "added_at": "2026-09-28T10:00:00+00:00"}
    _, text, html = digest.build([card], ["news"], date(2026, 9, 28))
    order = [text.index(s) for s in ("1 story from 1 source.", "WORD OF THE DAY", "Here is the one story", "Every story of the day")]
    assert order == sorted(order)
    order = [html.index(s) for s in ("1 story from 1 source.", "Word of the day</div>", "Here is the one story", "Every story of the day")]
    assert order == sorted(order)


def test_tags_only_where_the_story_means_it():
    from aipulse import jurisdictions
    tags = lambda title, summary="": classify.tags_for(title, summary, limit=99)
    # companies: whole words, and case where the name is also a word
    assert "Amazon" not in tags("Lawsuit demands OpenAI pay for new school", "It draws on flaws")  # "l-aws-uit"
    assert "Amazon" in tags("Grok 4.7 is now on AWS")
    assert "Meta" not in tags("Transformers now runs llama.cpp quants", "Ollama's transparent pricing")
    assert "Meta" in tags("Meta releases Llama 5")
    assert "Intel" not in tags("A ‘race’ may deter China from sharing safety intel")
    # topics: not a fragment of another word or another sense
    assert "Jobs & Labor" not in tags("A collaboration between Sakana AI and the University of Tokyo")
    assert "Compute & Data Centers" not in tags("Holo4: powering generalist computer-use agents", "Clustering, Retrieval")
    assert "Compute & Data Centers" in tags("Huawei unveils its Atlas 960 SuperPoD computing cluster")
    assert "Education" not in tags("A Coding Guide to MSEB", "A comprehensive coding tutorial")
    assert "Law" not in tags("Bill Gates says it's irresponsible for AI to not have safeguards")
    assert "Law" not in tags("Muse can send emails, book travel and negotiate bills")
    assert "Law" in tags("U.S. bill proposes permanent ban on artificial superintelligence")
    assert "Science" not in tags("Improving how customers discover and consume content")
    assert "Science" in tags("Claude discovers a novel enzyme system with CRISPR-like repeats")
    assert "Governance" not in tags("TechCrunch Founder Summit’s agenda revealed")
    assert "Governance" in tags("Why AI experts are freaked out over safety fears ahead of Xi-Trump summit")
    assert "Energy" not in tags("AI hallucination of Chinese nuclear components almost led to a US military attack")
    # places
    assert jurisdictions.detect("ByteDance to expand AI data centre cluster in Inner Mongolia") == ["CN"]
    assert jurisdictions.detect("Northern Ireland victim lost £250,000 in an AI scam") == ["GB"]
    assert jurisdictions.detect("New South Wales trials AI in schools") != ["GB"]
    # every UN member has a place: these 7 EU members were missing
    for name, code in [("Bulgaria", "BG"), ("Croatia", "HR"), ("Cyprus", "CY"), ("Latvia", "LV"), ("Lithuania", "LT"),
                       ("Slovakia", "SK"), ("Slovenia", "SI")]:
        assert jurisdictions.detect(f"{name} adopts a national AI strategy") == [code]
    assert jurisdictions.detect("A Slovak startup and a Slovenian lab") == ["SK", "SI"]


def test_the_preference_form_is_short_and_its_search_finds_every_tag():
    from datetime import date
    from aipulse import classify, preferences
    cards = [
        {"category": "news", "kind": "tutorial", "title": "A coding guide to Qwen agents", "summary": "", "date": "2026-09-28",
         "tags": ["Alibaba", "China", "Agents"]},
        {"category": "regulation", "action": "proposal", "title": "Kenya AI bill", "summary": "", "date": "2026-09-28",
         "tags": ["Kenya", "Law"]},
        {"category": "research", "title": "A paper", "summary": "", "date": "2026-01-01", "tags": ["Philip Torr", "Nvidia", "Research"]},
    ]
    o = preferences.options(cards, date(2026, 9, 29))
    shown = {g["name"]: g["items"] for g in o["groups"]}
    search = {g["name"]: g.get("search", []) for g in o["groups"]}
    # a few choices per section...
    assert shown["Story types"][:2] == ["News", "AI-incident"] and "Standard" in shown["Story types"]
    assert shown["Topics"] == list(preferences.THEMES) and len(shown["Topics"]) == 8
    assert shown["Companies"] == ["Alibaba", "Nvidia"]  # the most in the news; the rest through the search
    assert shown["Places"] == ["Africa", "Asia", "Europe", "North America", "South America", "Oceania", "International bodies"]
    assert shown["People"] == [] and search["People"] == ["Philip Torr"]
    # ...and the search finds the rest: every topic, every country
    assert {"Agents", "Law"} <= set(search["Topics"]) and {"Kenya", "Slovakia", "Russia"} <= set(search["Places"])
    assert set(classify.TOPIC_TERMS) <= set(preferences.THEME_OF)  # every topic tag is in a theme
    assert preferences.THEME_OF["Funding"] == "Business & work" and preferences.THEME_OF["Deepfakes"] == "Safety & security"
    assert preferences.CONTINENT_OF["Kenya"] == "Africa" and preferences.CONTINENT_OF["Israel"] == "Asia"
    assert preferences.CONTINENT_OF["Mexico"] == "North America" and preferences.CONTINENT_OF["European Union"] == "Europe"
    # every place has a continent, except Russia: no region, as on the site; chosen by name
    assert [p for p, c in preferences.CONTINENT_OF.items() if not c] == ["Russia"]
    # a story carries its theme and continent too, so choosing "Asia" or a theme reaches it
    assert {"Agents", "Models & products", "China", "Asia", "Tutorial"} <= preferences.labels(cards[0])
    assert all(isinstance(t, str) for g in o["groups"] for t in g["items"] + g.get("search", []))  # labels only, no counts
    assert "Research" not in {t for g in o["groups"] for t in g["items"] + g.get("search", [])}
    everything = {t for g in o["groups"] for t in g["items"] + g.get("search", [])}
    assert {"Tutorial", "Kenya", "Alibaba", "Nvidia", "Philip Torr", "Agents", "Law"} <= everything  # nothing out of reach



def test_page_script_declares_each_name_once():
    import re
    from pathlib import Path
    script = Path("templates/index.html").read_text(encoding="utf-8").split("<script>")[-1]
    names = [n for decl in re.findall(r"^(?:const|let|function)\s+(.+?)(?:=>|\(|;|$)", script, re.M)
             for n in re.findall(r"(?:^|,\s*)([A-Za-z_$][\w$]*)\s*(?:=|\(|$)", decl)]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"declared twice (the page's script would stop): {dupes}"


def test_each_reader_gets_their_own_top_10(monkeypatch):
    from datetime import date
    from aipulse import digest
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    day = date(2026, 9, 28)

    def card(i, title, outlets=0, kind="news", tags=()):
        return {"id": f"c{i}", "title": title, "summary": "", "url": f"https://ex.com/{i}", "source": f"S{i}",
                "category": "news", "kind": kind, "date": day.isoformat(), "added_at": f"{day}T10:00:00+00:00",
                "tags": list(tags), "also": [{"source": f"O{i}{k}", "title": title, "url": f"https://o.com/{i}/{k}"} for k in range(outlets)]}
    big = [card(i, f"Big story {i} about OpenAI", outlets=10 - i) for i in range(12)]  # the day's biggest
    robots = [card(20 + i, f"A humanoid robot demo {i}") for i in range(7)]            # Robotics, 1 outlet each
    guides = [card(40 + i, f"How to fine-tune {i}", kind="tutorial") for i in range(3)]
    kerala = [card(50, "Kerala launches an AI mission for schools", outlets=1)]  # outranks the robots
    cards = big + robots + guides + kerala
    everyone = digest.build(cards, ["news"], day)
    # no choices: exactly today's email
    assert digest.build(cards, ["news"], day, prefs={"more": [], "less": [], "words": []}) == everyone
    _, text, html = digest.build(cards, ["news"], day, prefs={"more": ["Robotics"], "less": [], "words": ["Kerala"]})
    assert "Here are the 10 that mattered most." in text and "of your top 10" not in text  # picks are marked, not announced
    top = text.split("Here are the 10 that mattered most.")[1].split("THE REST OF THE DAY")[0]
    yours = [l for l in top.splitlines() if "[Your choice]" in l]
    assert len(yours) == digest.PICKS and "Big story 0" in top and "Big story 4" in top  # 5 of theirs, then the biggest
    assert "Kerala launches" in top  # their own words, in the headline
    assert " · YOUR CHOICE</div>" in html and "Left out" not in text  # nothing left out: no note
    # 12 stories in their streams (one more than the top 10 holds): still a top 10, their own first
    twelve = big[2:10] + [kerala[0], robots[0], *guides[:2]]
    _, text, _ = digest.build(twelve, ["news"], day, prefs={"more": ["Robotics"], "less": [], "words": ["Kerala"]})
    assert "Here are the 10 that mattered most." in text and "lighter day" not in text
    top = text.split("Here are the 10 that mattered most.")[1].split("THE REST OF THE DAY")[0]
    firsts = [l for l in top.splitlines() if l.startswith("• ")]
    assert len(firsts) == 10 and all("[Your choice]" in l for l in firsts[:2]) and "[Your choice]" not in firsts[2]
    # left out: never in their email, counted, and still in the full email
    _, text, _ = digest.build(cards, ["news"], day, prefs={"more": [], "less": ["Tutorial", "Business & work"], "words": []})
    assert "How to fine-tune" not in text and "Left out, as you asked: 3 stories (Tutorial); they're in the full email." in text
    full = digest.build(cards, ["news"], day, layout="full", prefs={"more": [], "less": ["Tutorial"], "words": []})
    assert "How to fine-tune 0" in full[1]  # the full email is the same for everyone
    # word of the day: the hardest technical word in the day's 5 biggest stories of this reader's email
    hard = [card(60, "Nvidia ships HBM4 for AI data centers", outlets=20), card(61, "A new benchmark for agents", outlets=19),
            card(62, "Another data center opens")]  # "data center" is common; HBM is rare
    text = digest.build(cards + hard, ["news"], day)[1]
    assert "WORD OF THE DAY: HBM" in text  # rarer than "benchmark" or "agent" in these stories
    assert "Where it came up: Nvidia ships HBM4 for AI data centers" in text  # a story in their own email


def test_a_busy_weekday_is_compared_with_weekdays():
    from datetime import date, timedelta
    from aipulse import quality
    day = date(2026, 9, 29)  # a Tuesday
    papers = []
    for k in range(1, 15):  # two weeks: ~10 papers a weekday, ~2 at weekends (arXiv doesn't publish then)
        d = day - timedelta(days=k)
        n = 2 if d.weekday() >= 5 else 10
        papers += [{"id": f"p{k}-{i}", "category": "research", "date": d.isoformat(), "title": f"Paper {k}.{i}",
                    "url": f"https://arxiv.org/abs/2609.{k:02d}{i:03d}", "source": "arXiv", "summary": "x"} for i in range(n)]
    assert quality.usual(papers, "research", day) == 10  # weekdays only, not the weekend-dragged median
    assert quality.usual(papers, "research", date(2026, 9, 27)) == 2  # a Sunday: compared with weekends
    today = [{"id": f"t{i}", "category": "research", "date": day.isoformat(), "title": f"New paper {i}",
              "url": f"https://arxiv.org/abs/2609.9{i:04d}", "source": "arXiv", "summary": "x"} for i in range(27)]
    surge = [p for p in quality.problems({"research": today}, papers + today, day) if "usual" in p]
    assert not surge  # 27 on a busy Tuesday is normal
    flood = today + [dict(t, id=f"f{t['id']}", title=f"More {t['title']}", url=t["url"] + "v9") for t in today[:13]]
    assert [p for p in quality.problems({"research": flood}, papers + flood, day) if "usual" in p]  # 40: still held


def test_a_ministrys_release_gets_its_own_summary_and_country(tmp_path):
    from aipulse import feeds, store
    from aipulse.collect import reclassify, retag
    page = ('<h1>Pilot AI App</h1><div id="cont-wrap" class="view_cont"><p><span>﻿- The price information consultative '
            'body was launched, and the pilot app will be further improved.</span></p><p>【Relevant National Task】</p>'
            '<p>23. Realizing a “Universal Basic AI Society” to enhance public safety and universal quality of life.</p>'
            '<p>The Ministry of Science and ICT held a commemorative ceremony at the Cheongju Osong Convention Center to '
            'mark the launch of the pilot app.</p></div><div class="view_file">files</div>').encode()
    assert feeds.msit_lead(page) == "The price information consultative body was launched, and the pilot app will be further improved."
    no_dash = page.replace("﻿- The price".encode(), b"Short line")
    assert feeds.msit_lead(no_dash.replace(b"information consultative body was launched, and the pilot app will be further improved.", b"")
                           ).startswith("The Ministry of Science and ICT held")  # else the text itself, not the tasks
    # its country, though the headline names none; a named place still wins; a company's home comes after
    korea = "Ministry of Science and ICT (Korea)"
    assert classify.tags_for("Pilot AI App for Smart Grocery Shopping Launched in Five Regions", "", source=korea) == ["South Korea"]
    assert "South Korea" not in classify.tags_for("MSIT and Japan sign an AI pact", "", source=korea)
    assert classify.tags_for("OpenAI opens an office", "", source=korea)[:2] == ["OpenAI", "South Korea"]
    assert classify.tags_for("A guide to AI assurance", "", source="GOV.UK") == ["United Kingdom"]
    assert "Elections" not in classify.tags_for("Selection Result Announced for the AI Foundation Model Project", "")
    assert "Elections" in classify.tags_for("AI deepfakes ahead of the election", "")
    # a release already stored as a headline only is read once and tagged
    conn = store.connect(str(tmp_path / "t.db"))
    store.insert(conn, {"source": korea, "category": "policy", "title": "Pilot AI App for Smart Grocery Shopping Launched in Five Regions",
                        "summary": "", "url": feeds.MSIT_VIEW + "1310", "date": "2026-09-30"})
    asked = []
    reclassify(conn, fetcher=lambda url: (asked.append(url), page)[1])
    retag(conn)
    row = conn.execute("SELECT summary, tags FROM items").fetchone()
    assert asked == [feeds.MSIT_VIEW + "1310"] and row["summary"].startswith("The price information consultative body")
    assert "South Korea" in row["tags"]
    reclassify(conn, fetcher=lambda url: asked.append(url) or page)
    assert len(asked) == 1  # it has its summary now: not read again


def test_infrastructure_stories_are_about_ai_s_own_footprint():
    for t in ["Microsoft taps Three Mile Island nuclear plant to power AI", "AI data centres strain Arizona's water",
              "County pauses new data centers amid noise complaints", "Meta to build 5GW AI campus in Louisiana",
              "AI's energy appetite drives Nvidia and Amazon to pour billions into power infrastructure",
              "Texas halts data center connections to power grid amid overwhelming demand"]:
        assert classify.infra_story(t), t
    for t in ["Google AI weather model beats forecasters", "Fero Labs, which uses AI to cut carbon emissions in factories, raises $15M",
              "Scientists once hoarded pre-nuclear steel; now we're hoarding pre-AI content", "OpenAI raises $40B",
              "At TED AI, experts debate whether we've created “the new electricity”", "Nvidia unveils new GPU",
              "OpenAI weighs “nuclear option” of antitrust complaint", "Robbie G2: an AI agent that uses a grid to navigate GUIs"]:
        assert not classify.infra_story(t), t
    # the tag, in any stream: a paper or a bill about data centres carries it; a paper on privacy-utility doesn't
    assert classify.INFRA_TAG in classify.tags_for("S. 4214: Artificial Intelligence Data Center Moratorium Act", "")
    assert classify.INFRA_TAG in classify.tags_for("Cooling at scale", "We study water use in hyperscale data centres.")
    assert classify.INFRA_TAG not in classify.tags_for("Privacy-utility trade-offs in LLM training", "A better utility bound.")
    # what each infrastructure story is about, in place of the general tags that only repeat the stream
    tags = classify.tags_for("Data center guzzled 30 million gallons of water, and nobody noticed", "")
    assert "Water" in tags and "Compute & Data Centers" not in tags
    assert "Land & local pushback" in classify.tags_for("Residents oppose new AI data centre near farmland", "")
    assert "Water" not in classify.tags_for("Water polo team uses AI to plan plays", "")  # not about AI's infrastructure
    from aipulse import preferences
    story = {"title": "Texas halts data center connections to power grid", "summary": "", "source": "E", "category": "infra"}
    assert {"Power & grid", "Energy", "Compute & Data Centers", "Infrastructure & sustainability"} <= preferences.labels(story)


def test_infrastructure_stories_have_their_own_stream():
    from aipulse.collect import stream_of
    from aipulse.sources import SOURCES
    infra = [s for s in SOURCES if s["category"] == "infra"]
    assert len(infra) >= 10 and all(s.get("infra_filter") for s in infra)  # an energy newsroom: only AI's footprint
    news = {"name": "E", "url": "https://e.com/feed", "category": "news"}
    assert stream_of(infra[0], "Anything they publish", "", "https://e.com/1") == "infra"
    assert stream_of(news, "Local resistance blocks $98 billion in AI data center projects", "", "https://e.com/2") == "infra"
    assert stream_of(news, "OpenAI raises $40B", "", "https://e.com/3") == "news"
    # stored Industry stories move in (history back to 2023), and back out if the rule no longer holds
    conn = store.connect(":memory:")
    base = {"summary": "", "source": "E", "date": "2024-09-20", "tags": [], "authors": []}
    store.insert(conn, {**base, "title": "Microsoft taps Three Mile Island nuclear plant to power AI", "url": "https://e.com/4", "category": "news"})
    store.insert(conn, {**base, "title": "OpenAI raises $40B", "url": "https://e.com/5", "category": "infra"})
    reclassify(conn, fetcher=lambda u: b"")
    assert dict(conn.execute("SELECT url, category FROM items").fetchall()) == {"https://e.com/4": "infra", "https://e.com/5": "news"}
    # a feed that gives its links as paths (the EIA's) is stored with full addresses
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    feed = (f"<rss><channel><item><title>Data centers drive US electricity demand</title><link>/pressroom/releases/press592.php</link>"
            f"<pubDate>{day}</pubDate></item></channel></rss>").encode()
    eia = {"name": "EIA", "url": "https://www.eia.gov/rss/press_rss.xml", "category": "infra", "infra_filter": True}
    collect(conn, [eia], fetcher=lambda u: feed, log=lambda m: None, official_bills=False)
    assert store.exists(conn, "https://www.eia.gov/pressroom/releases/press592.php")


def test_infrastructure_reaches_the_email_and_its_readers():
    from datetime import date
    from aipulse import digest, preferences, quality, rss, subscribers
    assert list(rss.FEEDS)[-1] == "infra" and rss.FEEDS["infra"][0] == "infra"
    # a reader who had every stream gets the new one; a reader who chose some doesn't, but is told how to add it
    base = {"ok": True, "unsubscribe": "https://script.google.com/x?t=", "subscribers": [
        {"email": "a@x.org", "token": "0" * 36, "streams": ["releases", "news", "research", "regulation", "policy"]},
        {"email": "b@x.org", "token": "1" * 36, "streams": ["research"]}]}
    got = subscribers.readers(base)
    assert got["a@x.org"][0][-1] == "infra" and got["b@x.org"][0] == ["research"]
    # only for readers who haven't chosen the new stream
    assert digest._new_stream(date(2026, 10, 5), ["infra"]) == ""
    assert "Add it to your feed by clicking on following button" in digest._new_stream(date(2026, 10, 5), ["research"])
    # the note carries a highlighted button to the sign-up form, filled in with the reader's own email and choices
    one_click = "https://projectaipulse.com/#unsubscribe=0f8fad5b-d9cb-469f-a165-70867728950e"
    card = {"id": "r", "title": "A paper on AI agents", "summary": "", "url": "https://ex.com/r", "source": "arXiv",
            "category": "research", "date": "2026-10-05", "added_at": "2026-10-05T10:00:00+00:00"}
    _, text, html = digest.build([card], ["research"], date(2026, 10, 5), one_click)
    mine = one_click.replace("#unsubscribe=", "#choices=")
    assert f"following button\nAdd Infra & climate: {mine}" in text
    note = html.split("New on AI Pulse: Infra")[1].split("</div>")[0]
    assert f'href="{mine}"' in note and "Add Infra &amp; climate →" in note
    assert digest._new_stream(date(2026, 11, 1), ["research"]) == ""
    # its stories are on topic without naming AI, and carry the tag and theme readers can choose
    story = {"title": "Teraco opens a 40MW data centre in Cape Town", "summary": "", "source": "ESI Africa", "category": "infra"}
    assert quality.on_topic(story)
    assert {classify.INFRA_TAG} <= preferences.labels(story)
    assert "Chips, compute & energy" in preferences.labels(story)  # an older saved choice still matches
    assert classify.INFRA_TAG in digest.story_tags(story)


def test_a_new_stream_s_history_resumes_where_it_stopped(tmp_path):
    from aipulse import backfill
    conn = store.connect(tmp_path / "t.db")
    feed = (b'<rss><channel><item><title>Data centres draw on Ireland\'s grid</title><link>https://e.com/a</link>'
            b'<pubDate>Mon, 02 Jan 2023 10:00:00 GMT</pubDate></item></channel></rss>')
    asked = []
    added = backfill.feed_archives(conn, date(2023, 1, 1), fetcher=lambda u: asked.append(u) or feed, log=lambda *_: None,
                                   stream="infra", minutes=0)
    assert added == 0 and not asked  # out of time before the first source: nothing read, nothing marked done
    assert not conn.execute("SELECT 1 FROM meta WHERE key LIKE 'backfill-feed:%' AND value = 'done'").fetchone()


def test_memes_are_made_from_our_data_and_never_touch_serious_stories():
    from datetime import date
    from aipulse import memes
    day = date(2026, 9, 29)
    base = {"summary": "", "source": "E", "date": day.isoformat(), "also": [], "kind": "news"}
    titles = ["NVIDIA Releases Kumo Tabular: open models", "Supersonic Labs Releases Julia 1: a CPU model",
              "AWS debuts Strands Decider 2B, a decision model", "Google Research Introduces an AI Video Co-Director for films"]
    launches = [{**base, "title": t, "url": f"https://e.com/{i}", "category": "tool", "tags": []} for i, t in enumerate(titles)]
    # who launched what, only as the headline says it
    assert [memes.launch_of(c) for c in launches] == [("NVIDIA", "Kumo Tabular"), ("Supersonic Labs", "Julia 1"),
                                                       ("AWS", "Strands Decider 2B"), ("Google Research", "AI Video Co-Director")]
    assert memes.launch_of({"title": "DeepSeek Open-Sources Ascend Versions of TileLang"}) is None
    f = memes.facts(launches)
    assert memes._buttons(f, "today")["labels"] == ["Try NVIDIA's Kumo Tabular", "Try Supersonic Labs' Julia 1"]
    assert memes._fine(f, "today")["caption"] == "4 new AI models and tools today"
    assert memes._fine(f, "this week") is None  # a joke only when the stories back it up (15 launches a week)
    assert memes._nope_yep(f, "today") is None  # no raise, no money joke
    # harm, lawsuits, layoffs, children and politics are never joked about
    for title, cat in [("Chatbot linked to teen's death", "news"), ("Authors sue OpenAI", "news"), ("Startup lays off staff, layoffs hit AI", "news"),
                       ("Senate passes AI bill", "policy")]:
        assert not memes.light({**base, "title": title, "category": cat, "tags": []}), title
    assert memes.light({**base, "title": "Google releases Gemini 4", "category": "tool", "tags": ["Google"]})
    # the same day always gives the same meme: a real template with the captions written on, credited, a text version too
    cards = launches + [{**base, "title": "Big news story", "url": "https://e.com/n", "category": "news", "tags": [], "also": [{}, {}]}]
    one, two = memes.of_the_day(cards, day), memes.of_the_day(cards, day)
    assert one == two and one["title"] == "Meme of the day"
    page = memes.html(one, "cid:meme")
    assert 'src="cid:meme"' in page and "via imgflip.com" in page and memes.TEMPLATES[one["format"]][1] not in page
    assert memes.text(one)[0] == "MEME OF THE DAY:"
    # every template takes its captions and makes a picture (the email carries it; the site shows it)
    samples = [{"format": "distracted", "labels": ["A", "B", "C"]}, {"format": "buttons", "labels": ["A", "B"], "caption": "C"},
               {"format": "nopeyep", "who": "W", "nope": "A", "yep": "B"}, {"format": "fine", "caption": "A", "under": "B"},
               {"format": "brain", "rows": ["A", "B", "C", "D"]}, {"format": "yelling", "labels": ["A", "B"]},
               {"format": "pigeon", "labels": ["A", "B"], "caption": "C"},
               {"format": "panik", "rows": [("Panik", "A"), ("Kalm", "B"), ("Panik", "C")]}]
    assert {m["format"] for m in samples} == set(memes.TEMPLATES)
    for m in samples:
        assert (memes.render(m) or b"")[:3] == b"\xff\xd8\xff", m["format"]  # a JPEG
    # inside the email: the picture travels with it, and a dry run shows it in the file
    from aipulse import digest
    digest.INLINE[digest.MEME_CID] = memes.render(samples[0])
    msg = digest._message("a@b.c", "s", "t", f'<img src="cid:{digest.MEME_CID}">')
    assert any(part.get_content_type() == "image/jpeg" for part in msg.walk())
    assert "data:image/jpeg;base64," in digest.preview(f'<img src="cid:{digest.MEME_CID}">')
    digest.INLINE.clear()


def test_gemini_memes_are_checked_kept_once_and_fall_back(tmp_path, monkeypatch):
    import json
    from datetime import date
    from aipulse import memegen, memes, store
    day = date(2026, 10, 18)  # a nope/yep day (memes.ROTATION), not a Saturday (Sunday's email has the week's meme)
    assert memes.template_of(day) == "nopeyep"
    base = {"summary": "", "source": "E", "date": day.isoformat(), "also": [], "kind": "news", "tags": []}
    cards = [{**base, "title": t, "url": f"https://e.com/{i}", "category": "tool"} for i, t in enumerate(
        ["NVIDIA Releases Kumo Tabular: open models", "Cohere Releases Embed 5", "Startup raises $55M for agents"])]
    good = {"format": "nopeyep", "based_on": [2], "who": "AI startups", "nope": "A business plan", "yep": "Another $55M"}
    bad = [{**good, "yep": "Another $90M"},                     # a number no headline has
           {**good, "nope": "Asking the President"},            # politics
           {**good, "who": "Drake"}, {**good, "who": "Techie in a hoodie"},  # describes the picture, not the news
           {**good, "format": "unknown"}, {**good, "based_on": []}, {**good, "yep": "x" * 100}]
    asked = []
    def fake(prompt, key):
        asked.append(prompt)
        return json.dumps({"memes": bad + [good]})
    assert memegen.write(cards, "day", key="k", ask=fake) == {**{k: v for k, v in good.items() if k != "based_on"},
                                                              "based_on": [cards[2]["title"]], "by": "gemini"}
    assert "Kumo Tabular" in asked[0] and "k" not in asked[0].split("Rules")[0][-2:]
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert memegen.write(cards, "day", key=None, ask=fake) is None                      # no key: rule-based
    assert memegen.write(cards, "day", key="k", ask=lambda p, k: 1 / 0) is None        # an error: rule-based
    assert memegen.write(cards, "day", key="k", ask=lambda p, k: json.dumps({"memes": bad})) is None
    # made once and kept: the next build reads it from the database without asking again
    conn = store.connect(tmp_path / "m.db")
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setattr(memegen, "_ask", fake)
    n = len(asked)
    first = memegen.stored(conn, "day", day, cards, make=True)
    assert memegen.stored(conn, "day", day, cards, make=True) == first and len(asked) == n + 1
    memes.GENERATED.clear()
    memegen.prepare(conn, cards, day=day)
    assert memes.of_the_day(cards, day)["yep"] == "Another $55M"
    assert "Gemini" not in memes.html(memes.of_the_day(cards, day), "cid:meme")  # readers see only the source
    memes.GENERATED.clear()
    # on another day's template, Gemini is asked for that one only, and a kept meme on the wrong one is asked again
    other = date(2026, 10, 11)
    assert memes.template_of(other) == "yelling"
    assert '"yelling"' in memegen._prompt(cards, "day", set(memes.TEMPLATES) - {"yelling"}).split("Rules")[0]
    assert '"nopeyep"' not in memegen._prompt(cards, "day", set(memes.TEMPLATES) - {"yelling"}).split("Rules")[0]
    assert memegen.check(good, cards, {"nopeyep"}) is None
    conn.execute("INSERT INTO meta VALUES (?, ?)", (f"meme:day:{other.isoformat()}", json.dumps({**good, "by": "gemini"})))
    assert memegen.stored(conn, "day", other, cards, make=False, avoid={"nopeyep"}) is None


def test_each_days_meme_template_comes_back_only_after_5_days():
    from datetime import date, timedelta
    from aipulse import memes
    memes.GENERATED.clear()
    start = date(2026, 10, 1)
    days = [start + timedelta(days=k) for k in range(120)]
    used = [memes.template_of(d) for d in days]
    for i, t in enumerate(used):
        assert t not in used[max(0, i - 4):i], days[i]  # never within 5 days in a row
    assert set(used[:8]) == set(memes.TEMPLATES)  # all eight in turn
    # a day whose stories can't fill its template still gets one (a standby joke, no names or numbers), on that template
    for d in days[:8]:
        card = {"title": "Something happened", "summary": "", "url": "https://e.com/1", "source": "E", "category": "news",
                "kind": "news", "date": d.isoformat(), "also": [], "tags": []}
        m = memes.of_the_day([card], d)
        assert m and m["format"] == memes.template_of(d) and memes.render(m)
    assert memes.of_the_day([], start) is None  # no stories that day: no meme
    # the meme of the week takes the next template each Monday
    mondays = [date(2026, 9, 28) + timedelta(weeks=k) for k in range(16)]
    weekly = [memes.template_of_week(m) for m in mondays]
    assert all(a != b for a, b in zip(weekly, weekly[1:])) and set(weekly[:4]) == set(memes.WEEK_ROTATION)
    assert not set(memes.WEEK_ROTATION) & memes.TALL  # only wide ones, readable in the site's tile


# ---------- The weekly briefing (in testing): vectors, hybrid search, the briefing ----------

def _fake_embedder(monkeypatch):
    """Stand-in for the model: a story's vector counts a few words, so stories sharing them sit close."""
    import numpy as np
    from aipulse import embed
    axes = ["water", "cooling", "data", "centre", "chip", "export", "china", "act", "eu", "fine", "model", "launch"]

    def encode(texts, query=False):
        out = np.zeros((len(texts), embed.DIM), dtype=np.float32)
        for k, t in enumerate(texts):
            words = re.findall(r"\w+", t.lower())
            v = out[k]
            v[len(axes)] = 0.25  # what every story has in common
            for w in words:
                if w in axes:
                    v[axes.index(w)] += 1
            out[k] = v / np.linalg.norm(v)
        return out
    monkeypatch.setattr(embed, "encode", encode)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(embed, "DAYS", 10 ** 5)  # the tests' stories have fixed dates, whatever today is


def _story(conn, n, title, day, summary="", source="S", category="infra"):
    store.insert(conn, {"title": title, "summary": summary, "url": f"https://ex.com/{n}", "source": source,
                        "category": category, "date": day, "tags": []})


def test_wordpiece_matches_bert(tmp_path):
    from aipulse.embed import WordPiece
    vocab = tmp_path / "vocab.txt"
    vocab.write_text("\n".join(["[PAD]", "[UNK]", "[CLS]", "[SEP]", "data", "centre", "##s", "cafe", "gpt", "-", "6", "’", "s",
                                "人", "工"]), encoding="utf-8")
    wp = WordPiece(vocab)
    # lower case, accents off, punctuation and each Chinese character on its own, the rest in word pieces
    assert wp.tokens("Data centres Café GPT-6’s 人工 zzz") == ["[CLS]", "data", "centre", "##s", "cafe", "gpt", "-", "6", "’",
                                                              "s", "人", "工", "[UNK]", "[SEP]"]
    assert len(wp.tokens("data " * 500)) == 128  # cut to the model's limit, ends kept


def test_stories_are_embedded_once_and_again_when_changed(tmp_path, monkeypatch):
    from aipulse import embed
    _fake_embedder(monkeypatch)
    conn = store.connect(tmp_path / "t.db")
    _story(conn, 1, "Data centre water use rises", "2026-09-29")
    _story(conn, 2, "EU fines a chip maker", "2026-09-30")
    conn.commit()
    assert embed.update(conn, log=lambda *_: None) == 2
    assert embed.update(conn, log=lambda *_: None) == 0  # nothing new
    store.update_text(conn, store.item_id("https://ex.com/1"), "Data centre water use rises again", "")
    conn.execute("DELETE FROM items WHERE id = ?", (store.item_id("https://ex.com/2"),))
    conn.commit()
    assert embed.update(conn, log=lambda *_: None) == 1  # the changed one; the deleted one's vector goes too
    assert conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0] == 1


def test_search_by_meaning_and_by_words(tmp_path, monkeypatch):
    from aipulse import embed, search
    _fake_embedder(monkeypatch)
    conn = store.connect(tmp_path / "t.db")
    _story(conn, 1, "Data centre water cooling draws fire", "2026-09-29")
    _story(conn, 2, "Water and cooling for a new data centre", "2026-09-30", source="T")
    _story(conn, 3, "Chip export rules for China tighten", "2026-10-01", category="policy")
    _story(conn, 4, "S. 5518 introduced", "2026-10-02", category="regulation")  # no words the vectors know
    _story(conn, 5, "Data centre water cooling, last month", "2026-09-01")  # before the week
    conn.commit()
    embed.update(conn, log=lambda *_: None)
    since, until = date(2026, 9, 28), date(2026, 10, 5)
    found = [c["title"] for c in search.search(conn, "data centre water cooling", since, until)]
    assert found[:2] and set(found[:2]) == {"Data centre water cooling draws fire", "Water and cooling for a new data centre"}
    assert "Chip export rules for China tighten" not in found  # far in meaning, no shared words: left out
    assert "Data centre water cooling, last month" not in found  # only the week asked for
    assert [c["title"] for c in search.search(conn, "S. 5518", since, until)] == ["S. 5518 introduced"]  # exact words count


def test_dossier_sections_pick_the_week_and_never_write(tmp_path, monkeypatch):
    from aipulse import embed, weekly
    _fake_embedder(monkeypatch)
    conn = store.connect(tmp_path / "t.db")
    _story(conn, 1, "Data centre water cooling draws fire", "2026-09-29", summary="Residents object to water use.")
    _story(conn, 2, "Chip export rules for China tighten", "2026-10-01", category="policy")
    _story(conn, 3, "Data centre water cooling plan filed", "2026-09-10")  # the earlier story it follows on from
    _story(conn, 5, "Water cooling approved for a data centre", "2026-09-30", source="T")
    conn.commit()
    embed.update(conn, log=lambda *_: None)
    monkeypatch.setattr(weekly, "SAME_STORY", 0.8)
    key, monday = "k" * 32, date(2026, 10, 6)
    topics = ["data centre water cooling", "chip export China"]
    weekly.prepare(conn, topics, key, monday, log=lambda *_: None)
    first, second = (weekly.kept(conn, monday)[weekly.interest_id(key, t)]["html"] for t in topics)
    assert "THE LEAD" in first and "Data centre water cooling draws fire" in first and "Water cooling approved for a data centre" in first
    assert "WHO" not in first  # the stories name no company or person (their topics aren't names)
    assert "Dig deeper ↓" in first and "<details" in first and "1 earlier story on this in the month before" in first
    assert first.index("<details") < first.index("Data centre water cooling plan filed")  # the past only behind the arrow
    assert "The rest of the week" in first and "https://ex.com/1" in first
    assert "Chip export rules for China tighten" in second and "Data centre water cooling plan filed" not in second
    assert "Nothing on this topic this week." in weekly._body({"topic": "quantum sensing", "cards": []})
    assert "written by AI" not in first + second


def test_dossiers_kept_per_interest_published_by_id_and_noted_on_sunday(tmp_path, monkeypatch):
    import json
    from aipulse import digest, embed, weekly
    _fake_embedder(monkeypatch)
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    conn = store.connect(tmp_path / "t.db")
    _story(conn, 1, "Data centre water cooling draws fire", "2026-09-29", summary="Residents object to water use.")
    _story(conn, 2, "Chip export rules for China tighten", "2026-10-01", category="policy")
    _story(conn, 3, "Data centre water cooling plan shelved", "2026-10-04", summary="The water plan is off.")
    conn.commit()
    embed.update(conn, log=lambda *_: None)
    key, sunday, monday = "k" * 32, date(2026, 10, 4), date(2026, 10, 5)
    # the dossier's week: on a Sunday, Monday to Saturday (for the Sunday email); from Monday on, the whole week
    assert weekly.last_week(sunday) == (date(2026, 9, 28), sunday) and weekly.last_week(monday) == (date(2026, 9, 28), monday)
    assert weekly.last_week(date(2026, 10, 3)) == (date(2026, 9, 21), date(2026, 9, 28))
    mine = ["Data centre water cooling", "quantum sensing"]
    # the same interest from two readers (any capitals) is worked out once; an empty one never
    assert weekly.prepare(conn, [*mine, "data centre WATER cooling", "  ", "?!"], key, sunday, log=lambda *_: None) == 2
    ids = [weekly.interest_id(key, t) for t in mine]
    assert all(re.fullmatch(r"[0-9a-f]{24}", i) for i in ids) and weekly.interest_id("other" * 8, mine[0]) != ids[0]
    assert weekly.kept(conn, sunday)[ids[0]]["count"] == 1 and weekly.kept(conn, sunday)[ids[1]]["count"] == 0  # not Sunday's
    # the site: one file per interest, named by its id only; the reader's link carries ids, never their words
    assert weekly.publish(conn, tmp_path / "site", sunday) == 2
    page = json.loads((tmp_path / "site" / "dossier" / f"{ids[0]}.json").read_text(encoding="utf-8"))
    assert page["topic"] == "Data centre water cooling" and page["from"] == "2026-09-28" and page["to"] == "2026-10-03"
    assert "Data centre water cooling draws fire" in page["html"] and "https://ex.com/1" in page["html"]
    link = weekly.link(key, mine)
    assert link == f"https://projectaipulse.com/dossier.html#{ids[0]}.{ids[1]}" and "water" not in link.lower()
    # Sunday's email (the day it covers is the Saturday): the note, with each interest's count and the link
    note = weekly.note(conn, key, mine, date(2026, 10, 3))
    assert note == {"link": link, "week": "28 Sep – 3 Oct",
                    "entries": [{"topic": "Data centre water cooling", "count": 1}, {"topic": "quantum sensing", "count": 0}]}
    assert weekly.note(conn, key, ["Something nobody asked for"], date(2026, 10, 3)) is None  # not worked out: no note
    card = {"id": "x", "title": "Data centre water cooling draws fire", "summary": "", "url": "https://ex.com/1", "source": "S",
            "category": "infra", "date": "2026-10-03", "added_at": "2026-10-03T10:00:00+00:00"}
    one_click = "https://projectaipulse.com/#unsubscribe=0f8fad5b-d9cb-469f-a165-70867728950e"
    _, text, html = digest.build([card], ["infra"], date(2026, 10, 3), one_click, dossier=note)
    ask = "https://projectaipulse.com/ask.html#0f8fad5b-d9cb-469f-a165-70867728950e"  # their own dossier page
    assert "Change my questions" not in html and "Get my dossier" not in html  # a reader with a dossier: just the button to it
    # every subscriber's Sunday email has the box, questions or not; not on other days, nor without their own link
    _, new_text, new_html = digest.build([card], ["infra"], date(2026, 10, 3), one_click)
    assert "Get my dossier" in new_html and f'href="{ask.replace("&", "&amp;")}"' in new_html and f"Get my dossier: {ask}" in new_text
    assert "Open your weekly dossier" not in new_html and "Type your question" not in new_html
    friday = {**card, "date": "2026-10-02"}
    assert "Get my dossier" not in digest.build([friday], ["infra"], date(2026, 10, 2), one_click)[2]
    sample = digest.build([card], ["infra"], date(2026, 10, 3))[2]  # a sample, without a reader's link: to sign up
    assert "Get my dossier" in sample and 'href="https://projectaipulse.com/#subscribe"' in sample
    assert "YOUR WEEKLY DOSSIER, 28 Sep – 3 Oct" in text and "Data centre water cooling" not in text.split("YOUR WEEKLY")[1].split("\n\n")[0]
    assert f'href="{ask}"' in html and f'href="{link}"' not in html and "Open your weekly dossier" in html and f"cid:{digest.DOSSIER_CID}" in html  # the button
    assert digest.INLINE[digest.DOSSIER_CID][:4] == b"\x89PNG"  # its icon, inside the email
    msg = digest._message("a@b.c", "s", text, html)
    assert any(part.get_content_type() == "image/png" for part in msg.walk())
    digest.INLINE.clear()
    assert "Open your weekly dossier" not in digest.build([card], ["infra"], date(2026, 10, 3))[1]  # without one, no note
    # Monday's run: the same week, now with Sunday's story, under the same Monday (Sunday's links keep working)
    weekly.prepare(conn, mine, key, monday, log=lambda *_: None)
    assert weekly.kept(conn, monday)[ids[0]]["count"] == 2
    # next run: only the interests readers have now
    weekly.prepare(conn, ["quantum sensing"], key, monday, log=lambda *_: None)
    assert list(weekly.kept(conn, monday)) == [ids[1]]


def test_sunday_email_brings_the_week_and_skips_the_days_word_and_meme(monkeypatch):
    from datetime import date
    from aipulse import digest, memes
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    card = lambda i, day, cat="news", outlets=0, title=None: {
        "id": f"s{i}", "title": title or f"Story {i}", "summary": f"What happened in story {i}.", "url": f"https://ex.com/{i}",
        "source": f"Outlet {i}", "category": cat, "kind": "news" if cat == "news" else None, "date": day,
        "added_at": f"{day}T10:00:00+00:00", "tags": [],
        "also": [{"title": f"Story {i}", "source": f"Other {k}", "url": f"https://o{k}.com/{i}", "date": day} for k in range(outlets)]}
    cards = ([card(1, "2026-09-29", "news", 6, "Big chip deal for a new data center")]  # the week's most reported
             + [card(i, "2026-10-0" + str(1 + i % 3), "news", 0, f"Data center story {i}") for i in range(2, 9)]
             + [card(9, "2026-10-04", "news", 9, "Sunday's story is next week's email")]  # not Monday to Saturday
             + [card(i, "2026-10-03", "tool" if i % 2 else "news") for i in range(10, 22)])
    subject, text, html = digest.build(cards, ["releases", "news"], date(2026, 10, 3))
    assert subject == "AI Pulse · The week in AI, and Saturday, 3 October 2026"
    assert "THE WEEK IN AI, 28 Sep – 3 Oct" in text and "The week in AI" in html
    # the week's count and the day's, a line each
    assert "This week, 28 Sep – 3 Oct: 20 stories.\nSaturday: " in text  # Monday to Saturday, not Sunday's
    assert "STORY OF THE WEEK: Big chip deal for a new data center" in text and "Sunday's story" not in text
    assert "WORD OF THE WEEK: Data center" in text and "It came up in 8 of the week's stories" in text
    assert "Word of the day" not in html and "Meme of the day" not in html and "WORD OF THE DAY" not in text
    assert "The 10 that mattered most on Saturday." in text
    # a reader whose streams had nothing on Saturday (Research: arXiv doesn't publish at weekends) still gets the
    # week, and one line for the day instead of a top 10
    got = digest.build(cards, ["research"], date(2026, 10, 3))
    assert got and "STORY OF THE WEEK: Big chip deal for a new data center" in got[1]
    assert "Saturday: nothing new in your streams." in got[1] and "Nothing new in your streams on Saturday." in got[2]
    assert "mattered most" not in got[1] and "THE REST OF THE DAY" not in got[1] and "only 0 stories" not in got[1]
    assert digest.build(cards, ["research"], date(2026, 10, 2)) is None  # any other day: nothing, as before
    # weekly readers get Sunday's email only; daily readers get every one
    readers = {"d@x.org": (["news"], "", "", {"often": "daily"}), "w@x.org": (["news"], "", "", {"often": "weekly"})}
    assert list(digest.due(readers, date(2026, 10, 3))) == ["d@x.org", "w@x.org"]  # Sunday's email (a Saturday)
    assert list(digest.due(readers, date(2026, 10, 2))) == ["d@x.org"]
    # a weekly reader's Sunday email isn't headed "AI Pulse daily"; a daily reader's still is
    base = {"more": [], "less": [], "words": []}
    for often, headed in (("weekly", False), ("daily", True)):
        html = digest.build(cards, ["news"], date(2026, 10, 3), prefs={**base, "often": often})[2]
        assert ("AI Pulse daily</div>" in html) is headed and "Your week in AI" in html
    # the other days stay as they were
    friday = digest.build(cards, ["releases", "news"], date(2026, 10, 1))
    assert friday[0] == "AI Pulse daily · Thursday, 1 October 2026" and "Word of the day" in friday[2]
    assert "The week in AI" not in friday[2]
    # the full email (the site's daily page) is the same every day
    assert digest.build(cards, ["releases", "news"], date(2026, 10, 3), layout="full")[0] == "AI Pulse daily · Saturday, 3 October 2026"
    digest.INLINE.clear()
    memes.GENERATED.clear()


def test_a_question_about_a_place_keeps_to_that_place(tmp_path, monkeypatch):
    from aipulse import embed, search
    _fake_embedder(monkeypatch)
    assert search.places("how is ai in usa") == {"US": "United States"} and search.places("AI in Britain") == {"GB": "United Kingdom"}
    assert search.places("tell us about chips") == {}  # "us" the pronoun isn't the country
    conn = store.connect(tmp_path / "t.db")
    _story(conn, 1, "US data centre water cooling rules", "2026-09-29")
    _story(conn, 2, "UK data centre water cooling rules", "2026-09-30")
    _story(conn, 3, "Data centre water cooling in Britain", "2026-10-01")
    for n, title in enumerate(["Chip export rules tighten", "A new model launch", "EU fine for a chip maker", "Model launch in China"], 10):
        _story(conn, n, title, "2026-10-02", category="policy")  # the week's other stories, unlike these
    conn.commit()
    embed.update(conn, log=lambda *_: None)
    since, until = date(2026, 9, 28), date(2026, 10, 5)
    assert [c["title"] for c in search.search(conn, "data centre water cooling in the USA", since, until)] == ["US data centre water cooling rules"]
    uk = {c["title"] for c in search.search(conn, "data centre water cooling in the UK", since, until)}
    assert uk == {"UK data centre water cooling rules", "Data centre water cooling in Britain"}  # found as the site tags places
