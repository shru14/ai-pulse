import os
import sqlite3
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
    assert paper["tags"] == ["Sergey Levine"]  # papers are tagged only by professor or company
    assert paper["authors"] == ["Jane Doe", "Sergey Levine"]
    assert items["Visual world models for robots"]["tags"] == ["Fei-Fei Li"]
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
    assert paper["tags"] == ["Google"]


def test_expert_feed_items_are_tagged_by_person(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    sources = [{"name": "Google News: Shannon Vallor", "url": "rss", "category": "regulation",
                "expert": "Shannon Vallor"}]
    collect(conn, sources, max_age_days=100000, fetcher=lambda u: (FIX / "sample_rss.xml").read_bytes(),
            log=lambda *_: None)
    items = store.query(conn, "regulation")
    assert items and all(i["action"] == "expert" and i["tags"] == ["Shannon Vallor", "Philosophy"] for i in items)
    assert reclassify(conn) == 0  # expert items are never re-sorted into policy


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


def test_headline_only_items_get_a_lookup_or_a_draft(monkeypatch):
    from aipulse import brief
    from aipulse.collect import fill_summary
    monkeypatch.setattr(brief.time, "sleep", lambda s: None)
    rss = b"""<rss><channel><item><title>Kotek issues executive order on AI procurement safeguards</title>
      <link>https://example.com/a</link><description>Gov. Tina Kotek issued an executive order directing Oregon
      to develop safety standards for the state's use of AI.</description></item></channel></rss>"""
    item = {"title": "Kotek issues executive order establishing AI procurement safeguards", "summary": "",
            "url": "https://news.google.com/rss/articles/x", "category": "regulation", "action": "law",
            "jurisdictions": ["US"], "tags": []}
    fill_summary(item, lambda u: rss)
    assert item["summary"].startswith("Gov. Tina Kotek issued an executive order")
    miss = {**item, "summary": "", "tags": ["Google"]}
    fill_summary(miss, lambda u: b"<rss><channel></channel></rss>")
    assert miss["summary"] == "A law adopted in the United States, involving Google."


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
    assert s["precision"] >= 0.92 and s["recall"] >= 0.82 and s["events_on_one_card"] >= 7, s
    items = __import__("json").loads(cluster.FIXTURE.read_text(encoding="utf-8"))
    cards = cluster.collapse(items)
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
    assert page1["counts"] == {"tool": 5, "news": 0, "policy": 1, "research": 0, "regulation": 0, "all": 6}
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
    def urlopen(req, timeout):
        r = replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(feeds.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(feeds.time, "sleep", waits.append)
    assert feeds.fetch("https://x") == b"<rss/>"
    assert waits == [2.0, 7.0]  # our backoff first, then the server's Retry-After


def test_fetch_does_not_retry_permanent_errors(monkeypatch):
    import pytest, urllib.error
    calls = []
    def urlopen(req, timeout):
        calls.append(1)
        raise _http_error(404)
    monkeypatch.setattr(feeds.urllib.request, "urlopen", urlopen)
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
    # One good run clears the warning.
    collect(conn, [bad], max_age_days=100000, fetcher=lambda u: (FIX / "sample_rss.xml").read_bytes(), log=quiet)
    assert not any(h["failing"] for h in store.source_health(conn))


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
    assert "Passed one chamber on 2026-10-02" in card["summary"]
    assert sorted(o["source"] for o in card["also"]) == ["AP", "Vox"]  # by number and by short title


def test_congress_next_page_link_is_made_requestable(tmp_path, monkeypatch):
    import json
    from aipulse import bills
    monkeypatch.setattr(bills.time, "sleep", lambda s: None)
    seen = []
    def fetch(url):
        seen.append(url)
        assert " " not in url
        if len(seen) == 1:
            return json.dumps({"bills": [], "pagination": {
                "next": "https://api.congress.gov/v3/bill?sort=updateDate desc&offset=250&limit=250&format=json"}}).encode()
        return json.dumps({"bills": [], "pagination": {}}).encode()
    bills.sync_congress(store.connect(tmp_path / "t.db"), fetch, log=lambda *_: None)
    assert len(seen) == 2 and "updateDate+desc" in seen[1]


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
    assert {p.name for p in (tmp_path / "site").iterdir()} == {"index.html", "data.json", ".nojekyll"}


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
    assert [(i["title"], i["tags"]) for i in store.query(conn)] == [("Robot Learning from Play at Scale", ["Sergey Levine"])]


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
    known = {"Slack": {"brand": True, "site": "slack.com", "icon": "site-slack.png"},
             "Astra": {"brand": False, "site": None, "icon": None}, "Ando": {"brand": False, "site": None, "icon": None}}
    monkeypatch.setattr(brands, "wikidata", lambda name, budget: known.get(name))
    logo = lambda title, tags=(): brands.logo_for(title, list(tags), set(), [10])
    assert logo("Ando wants to take on Slack")["src"] == "brand-icons/site-slack.png"
    assert logo("Astra and Opus just passed Turing's test") is None  # a plain word Wikidata doesn't call a brand
    assert logo("YouTube promises custom feeds")["hex"] == "#FF0000"  # distinctive: no confirmation needed
    assert logo("Meta's new glasses use Slack", ["Meta"]) is None  # the page's own AI-company logos come first


def test_models_from_openrouter(tmp_path):
    from aipulse import models
    reply = {"data": [
        {"id": "anthropic/claude-opus-5.5", "name": "Anthropic: Claude Opus 5.5", "created": 1790035200,
         "context_length": 1000000, "pricing": {"prompt": "0.000004", "completion": "0.00002"},
         "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]}},
        {"id": "qwen/qwen3.8-flash", "name": "Qwen: Qwen3.8 Flash", "created": 1790035200, "context_length": 262144,
         "pricing": {"prompt": "0", "completion": "0"}, "hugging_face_id": "Qwen/Qwen3.8-Flash"},
        {"id": "anthropic/claude-opus-5.5:batch", "name": "Anthropic: Claude Opus 5.5 (batch)", "created": 1790035200,
         "pricing": {"prompt": "0.000002", "completion": "0.00001"}},                      # a variant
        {"id": "typesafe/router", "name": "Router", "created": 1790035200, "pricing": {"prompt": "-1"}},  # a router
    ]}
    parsed = models.parse(reply)
    assert [m["id"] for m in parsed] == ["anthropic/claude-opus-5.5", "qwen/qwen3.8-flash"]
    opus = parsed[0]
    assert (opus["lab"], opus["name"], opus["price_in"], opus["price_out"], opus["weights"]) == \
        ("Anthropic", "Claude Opus 5.5", 4.0, 20.0, "")
    assert parsed[1]["weights"] == "Qwen/Qwen3.8-Flash" and parsed[1]["price_in"] == 0
    conn = store.connect(tmp_path / "t.db")
    assert models.save(conn, parsed) == 2 and models.save(conn, parsed) == 0  # refreshing isn't "new"
    rows = models.parse_epoch(
        "Model,Organization,Publication date,Domain,Task,Parameters,Model accessibility,Link\n"
        "Claude Opus 5.5,Anthropic,2026-09-22,\"Language,Multimodal\",\"Chat,Code generation\",,API access,https://a.example\n"
        "Qwen3.8 Flash,\"Alibaba,Qwen Team\",2026-09-20,Language,Chat,30000000000,Open weights (unrestricted),\n"
        "Veo 5,Google DeepMind,2026-09-01,Video,Text-to-video,,Hosted access (no API),\n"
        "Old model,Meta AI,2022-11-30,Language,Chat,,Unreleased,\n")
    assert [(r["name"], r["lab"], r["uses"], r["access"]) for r in rows] == [
        ("Claude Opus 5.5", "Anthropic", "language,coding,vision", "api"),
        ("Qwen3.8 Flash", "Alibaba", "language", "open"),
        ("Veo 5", "Google", "image-video", "app")]  # 2022 is before the tracker starts
    models.save_notable(conn, rows)
    listed = {m["name"]: m for m in models.recent(conn)}
    assert list(listed) == ["Claude Opus 5.5", "Qwen3.8 Flash", "Veo 5"]
    # OpenRouter's price and context join by name; models it doesn't serve have none.
    assert (listed["Claude Opus 5.5"]["price_in"], listed["Claude Opus 5.5"]["context"]) == (4.0, 1000000)
    assert "price_in" not in listed["Veo 5"]


def test_newest_models_fill_epochs_lag_from_labs_that_matter(tmp_path):
    from aipulse import models
    conn = store.connect(tmp_path / "t.db")
    epoch = [{"key": f"GPT-{i}|2026-0{i}-01", "name": f"GPT-{i}", "lab": "OpenAI", "released": f"2026-0{i}-01",
              "uses": "language", "access": "api", "params": None, "link": ""} for i in (1, 2, 3)]
    epoch.append({"key": "Tiny|2026-08-30", "name": "Tiny", "lab": "SmallCo", "released": "2026-08-30",
                  "uses": "language", "access": "open", "params": None, "link": ""})
    models.save_notable(conn, epoch)
    base = {"context": 1000000, "price_in": 2.0, "price_out": 8.0, "weights": "", "inputs": "text,image",
            "outputs": "text", "description": ""}
    models.save(conn, [
        {**base, "id": "openai/gpt-4", "name": "GPT-4", "lab": "OpenAI", "released": "2026-09-05"},  # after Epoch's last
        {**base, "id": "openai/gpt-latest", "name": "GPT Latest", "lab": "OpenAI", "released": "2026-09-05"},  # an alias
        {**base, "id": "smallco/tiny-2", "name": "Tiny 2", "lab": "SmallCo", "released": "2026-09-05"},  # not a big lab
        {**base, "id": "openai/gpt-0", "name": "GPT-0", "lab": "OpenAI", "released": "2026-01-01"},  # long before
    ])
    names = [m["name"] for m in models.recent(conn)]
    assert "GPT-4" in names and "GPT Latest" not in names and "Tiny 2" not in names and "GPT-0" not in names
    gpt4 = next(m for m in models.recent(conn) if m["name"] == "GPT-4")
    assert (gpt4["uses"], gpt4["access"], gpt4["price_in"]) == ("language,vision", "api", 2.0)


def test_cards_for_more_stories_than_sqlite_takes_in_one_query(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    for i in range(1200):  # over SQLite's per-query limit on older builds (999)
        store.insert(conn, {"title": f"Story number {i} about AI", "summary": "", "url": f"https://e.com/{i}",
                            "source": "E", "category": "news", "date": "2026-09-01", "tags": [], "authors": []})
    conn.commit()
    cards, total = store.cards(conn, limit=10**9)
    assert total == 1200 and len(cards) == 1200 and all(c["also"] == [] for c in cards)
