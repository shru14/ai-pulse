"""The Regulation tracker and its pages: bills, official records, countries, rules, fines, pacts."""
import sqlite3
from datetime import date
from pathlib import Path

from aipulse import classify, store
from aipulse import jurisdictions
from aipulse.collect import apply_regulation, reclassify

FIX = Path(__file__).parent / "fixtures"


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


def test_generated_drafts_do_not_feed_back_into_sorting():
    item = {"title": "US bill seeks AI safety pact with China", "category": "policy",
            "summary": "A proposal in the United States and China, involving safety."}
    apply_regulation(item)
    assert (item["category"], item["jurisdictions"]) == ("regulation", ["US"])


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


def test_tracker_has_a_page_per_country_with_official_records_only(tmp_path):
    from datetime import date
    from aipulse import countries
    conn = store.connect(tmp_path / "t.db")
    card = lambda i, source, code, action="proposal": {"category": "regulation", "source": source, "title": f"AI Act {i}",
        "date": f"2026-0{i}-01", "jurisdictions": [code], "action": action, "url": f"https://e.com/{code}{i}", "bill": ""}
    cards = ([card(i, "UK Parliament", "GB") for i in range(1, 4)] + [card(4, "OECD.AI", "GB", "body")]
             + [card(i, "TechCrunch AI", "IN") for i in range(1, 6)] + [card(1, "Parliament of India", "IN")]
             + [card(i, "ISO/IEC", "INTL", "standard") for i in range(1, 4)] + [card(5, "OECD.AI", "GB", "standard")])
    paths = countries.build(conn, cards, tmp_path, date(2026, 10, 6))
    assert paths == ["tracker/", "tracker/united-kingdom/"]  # India: one official record, news stories don't count
    # international bodies aren't a place, and standards are on standards/ alone
    assert "<h2>Standards</h2>" not in (tmp_path / "tracker" / "united-kingdom" / "index.html").read_text(encoding="utf-8")
    page = (tmp_path / "tracker" / "united-kingdom" / "index.html").read_text(encoding="utf-8")
    assert '<img src="flags/gb.svg" alt=""></span><div><h1>AI laws and bills in the United Kingdom</h1>' in page and "<h2>Proposals</h2>" in page
    assert "<h2>AI bodies</h2>" in page and page.index("AI Act 3") < page.index("AI Act 1")  # newest first
    assert page.count('<table class="gt">') == 2 and '<li><a href="https://e.com/' not in page  # a table per kind: Proposals, AI bodies
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


def test_type_pages_are_tables_with_column_filters(tmp_path):
    from aipulse import countries
    conn = store.connect(tmp_path / "t.db")
    card = lambda i, source, code, action: {"category": "regulation", "source": source, "title": f"AI Act {i}",
        "date": f"2026-0{i}-01", "jurisdictions": [code], "action": action, "url": f"https://e.com/{code}{i}", "bill": ""}
    cards = [card(1, "UK Parliament", "GB", "proposal"), card(2, "congress.gov", "US", "proposal"),
             card(3, "OECD.AI", "INTL", "body"), card(4, "OECD.AI", "GB", "law")]
    assert countries.type_pages(conn, cards, tmp_path) == ["tracker/laws-adopted/", "tracker/bills/", "tracker/ai-bodies/"]
    page = (tmp_path / "tracker" / "bills" / "index.html").read_text(encoding="utf-8")
    assert "<th>Place</th><th data-nof>Title</th><th>Stage</th><th>Source</th><th data-seen>Date</th>" in page
    assert 'data-f="United Kingdom"' in page and 'data-f="Feb 2026"' in page and "Showing <b>2</b> of 2 bills" in page
    assert "hasAttribute('data-nof')" in page and '<td class="tp-src">congress.gov</td>' in page
    assert "<th>Stage</th>" not in (tmp_path / "tracker" / "ai-bodies" / "index.html").read_text(encoding="utf-8")


def test_sector_rules_page_holds_hand_rows_and_filed_tracker_records(tmp_path):
    from aipulse import sector_rules as sr
    assert all(s in sr.NAMES for s in sr.TRACKER.values()) and all(r[0] in sr.NAMES and r[2] in ("Law", "Rule", "Guidance")
                                                                    for r in sr.HAND)
    conn = store.connect(tmp_path / "t.db")
    card = lambda bill, action: {"category": "regulation", "source": "congress.gov", "title": f"{bill} Act ",
        "date": "2026-03-04", "jurisdictions": ["US"], "action": action, "url": f"https://e.com/{bill}", "bill": bill}
    cards = [card("US-119-hr-5045", "proposal"), card("US-119-hr-1", "proposal")]  # one filed under healthcare, one not
    assert [r["title"] for r in sr.rules(cards, "health")] == ["US-119-hr-5045 Act"]
    assert len(sr.rules(cards, "finance")) == sum(r[0] == "finance" for r in sr.HAND)
    # a button per sector that holds rules, each saying whether its main rules are checked; a page per sector
    assert sr.page(conn, cards, tmp_path) == ["tracker/sector-specific/", "tracker/sector-specific/finance/",
                                              "tracker/sector-specific/comms/", "tracker/sector-specific/health/"]
    tiles = (tmp_path / "tracker" / "sector-specific" / "index.html").read_text(encoding="utf-8")
    assert 'href="/tracker/sector-specific/health/"' in tiles and "<small>1 rule</small><small>Tracker records only</small>" in tiles
    assert f"<small>{len(sr.rules(cards, 'finance'))} rules</small><small>Main rules checked</small>" in tiles
    page = (tmp_path / "tracker" / "sector-specific" / "health" / "index.html").read_text(encoding="utf-8")
    assert "<th>Place</th><th data-nof>Rule</th><th>Kind</th><th data-seen>Date</th>" in page and '<div class="sr-src">congress.gov</div>' in page
    assert 'data-f="United States"' in page and "US-119-hr-1 Act" not in page and '<td class="sr-kind">Bill</td>' in page
    assert "Showing <b>1</b>" in page and 'data-f="2026"' in page and "not checked yet" in page


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
    assert "Updated" not in page.split('<main')[1] and 'href="/standards/"' in (countries.build(conn, cards, tmp_path, date(2026, 10, 6)) and
                                                               (tmp_path / "tracker" / "index.html").read_text(encoding="utf-8"))
    assert "<url><loc>https://projectaipulse.com/standards/</loc></url>" in sitemap([], date(2026, 10, 6), ["standards/"])


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


def test_congress_is_skipped_without_a_personal_key(tmp_path, monkeypatch):
    from aipulse import bills
    monkeypatch.delenv("CONGRESS_API_KEY", raising=False)
    asked = []
    conn = store.connect(tmp_path / "t.db")
    assert bills.sync_congress(conn, lambda url: asked.append(url), log=lambda *_: None) == 0
    assert asked == []  # the DEMO_KEY is never used


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


def test_promises_and_rule_echoes(monkeypatch):
    from aipulse import echoes, promises
    card = lambda i, day, title, cat="news", **kw: {"id": i, "date": day, "title": title, "url": f"https://x/{i}",
                                                    "source": "Outlet", "category": cat, "also": [], **kw}
    cards = [card("p1", "2024-10-25", "OpenAI reportedly plans to release its Orion AI model by December"),
             card("l1", "2025-02-27", "OpenAI unveils GPT-4.5 'Orion,' its largest AI model yet"),
             card("p2", "2025-04-05", "Meta reportedly prepares to launch Llama 4 after delays"),
             card("l2", "2025-04-05", "Meta releases Llama 4, a new crop of flagship AI models"),
             card("p3", "2025-02-14", "Baidu to open-source its Ernie large language model series"),
             card("x3", "2025-03-16", "Baidu launches two new versions of its AI model Ernie"),
             card("l3", "2025-06-30", "Baidu open-sources Ernie 4.5"),
             # a purpose, not a promise; a prediction; a launch whose subtitle names the product
             card("n1", "2024-03-18", "Nvidia NIM aims to bring AI applications to businesses faster"),
             card("n2", "2025-12-31", "Investors predict AI is coming for labor in 2026"),
             card("p4", "2025-10-14", "Nvidia to start shipping AI-optimized DGX Spark desktop computer"),
             card("x4", "2026-01-05", "NVIDIA Releases PAIR: An Open Source Router for DGX Spark")]
    found = {p["url"].rsplit("/", 1)[1]: p for p in promises.found(cards, date(2026, 10, 12))}
    assert set(found) == {"p1", "p2", "p3", "p4"}
    assert found["p1"]["status"] == "late" and found["p1"]["launch"]["url"].endswith("/l1") and found["p1"]["late"] == 58
    assert found["p2"]["status"] == "shipped" and found["p2"]["days"] == 0  # the same day counts
    assert found["p3"]["launch"]["url"].endswith("/l3")  # open-sourced, not just a new version
    assert found["p4"]["status"] == "waiting" and "launch" not in found["p4"]  # no date given, under 18 months old
    # the page shows only what was checked by hand; the rest, and a launch for a checked one without, wait for a check
    monkeypatch.setattr(promises, "CHECKED", {"https://x/p1": "https://x/l1", "https://x/p2": None, "https://x/p4": ""})
    shown = promises.promises(cards, date(2026, 10, 12))
    assert [p["url"] for p in shown] == ["https://x/p4", "https://x/p1"] and shown[1]["late"] == 58
    assert {p["url"] for p in promises.candidates(cards, date(2026, 10, 12))} == {"https://x/p3"}
    monkeypatch.setitem(promises.CHECKED, "https://x/p4", "")
    cards.append(card("l4", "2025-10-15", "Nvidia releases DGX Spark"))
    assert "https://x/p4" in {p["url"] for p in promises.candidates(cards, date(2026, 10, 12))}
    # echoes: official records about AI only, grouped by subject, places in the order they first took it up
    rec = lambda i, day, title, place, src: {"id": i, "date": day, "title": title, "url": f"https://r/{i}",
                                             "source": src, "category": "regulation", "jurisdictions": [place],
                                             "action": "proposal"}
    records = [rec("a", "2024-09-02", "Criminal Code Amendment (Deepfake Sexual Material) Act 2024", "AU", "legislation.gov.au"),
               rec("b", "2026-03-20", "Motion 26.3458: Grok and sexualized deepfakes. Act now!", "CH", "Swiss Parliament"),
               rec("c", "2020-05-15", "Privacy Amendment (Public Health Contact Information) Act 2020", "AU", "legislation.gov.au"),
               rec("d", "2026-02-06", "The Artificial Intelligence (Human Health and Medical Education) Regulation Bill, 2026", "IN", "Parliament of India")]
    records[0]["action"] = "law"
    themes = {t["slug"]: t for t in echoes.echoes(records)}
    assert echoes.themes_of(records[2]) == []  # a privacy law that isn't about AI
    assert [p["code"] for p in themes["sexual-deepfakes"]["places"]] == ["AU", "CH"]
    assert themes["sexual-deepfakes"]["places"][0]["furthest"] == "Adopted"
    assert "health" not in themes  # one place only: no echo yet


def test_harm_to_rule():
    from aipulse import harms, incidents
    harm = lambda i, day, title: {"id": i, "date": day, "title": title, "url": f"https://h/{i}", "source": incidents.SOURCE,
                                  "category": "news", "action": incidents.INCIDENT}
    rec = lambda i, day, title, place: {"id": i, "date": day, "title": title, "url": f"https://r/{i}", "source": "congress.gov",
                                        "category": "regulation", "jurisdictions": [place], "action": "proposal"}
    # titles only, stricter than the tracker: a school named in passing isn't a harm to children
    assert harms.subjects_of(harm("x", "2024-01-01", "Robotaxi Reportedly Struck Pedestrian Near Elementary School")) == []
    assert harms.subjects_of(harm("y", "2024-01-01", "Man Reportedly Committed Suicide Following Conversation with Chai Chatbot")) == ["companions"]
    cards = [harm(f"h{i}", f"2024-0{i}-10", "Character.ai Chatbot Reportedly Targeted Minors") for i in range(1, 7)]
    cards += [rec("a", "2024-03-01", "H.R. 1: CHATBOT Act", "US"), rec("b", "2025-01-01", "S. 2: Chatbot Safety Act", "US"),
              rec("c", "2022-05-01", "H.R. 3: An AI chatbot bill", "US")]  # before 2023: left out
    found = {s["slug"]: s for s in harms.subjects(cards)}
    assert set(found) == {"companions"}  # children has its 6 harms but no rule
    assert [r["card"]["id"] for r in found["companions"]["rules"]] == ["a", "b"]
    assert [r["before"] for r in found["companions"]["rules"]] == [2, 6]


def test_ai_consultations_reads_each_list_keeps_titles_naming_ai_and_builds(tmp_path, monkeypatch):
    import json
    from datetime import date
    from aipulse import consultations
    monkeypatch.setattr(consultations, "ADDED", [])  # the lists' rows only, not the ones checked by hand
    uk = {"results": [
        {"title": "Copyright and AI: technical measures", "link": "/government/consultations/copyright-ai",
         "end_date": "2026-11-20T23:59:00.000+00:00", "organisations": [{"title": "Intellectual Property Office"}],
         "content_store_document_type": "open_consultation"},
        {"title": "Growing up in the online world", "link": "/government/consultations/online",  # AI only in its summary
         "end_date": "2026-05-26T23:59:00.000+01:00", "content_store_document_type": "consultation_outcome"},
        {"title": "Algorithmic transparency standard", "link": "/government/consultations/ats",
         "end_date": "2026-06-01T23:59:00.000+01:00", "content_store_document_type": "consultation_outcome"},
        {"title": "AI Management Essentials", "link": "/government/consultations/ame",  # closed too long ago
         "end_date": "2025-01-29T23:59:00.000+00:00", "content_store_document_type": "consultation_outcome"}]}
    us = {"results": [
        {"title": "Policy Statement Concerning Artificial Intelligence Systems", "html_url": "https://fr.example/1",
         "comments_close_on": "2026-10-20", "agency_names": ["Federal Trade Commission"]},
        {"title": "Aquatic Invasive Species (AIS) Rules", "html_url": "https://fr.example/2",
         "comments_close_on": "2026-10-25", "agency_names": ["Interior Department"]}]}
    eu = {"initiativeResultDtoPage": {"last": True, "content": [
        {"id": 19292.0, "shortTitle": "\rArticles 75c – 75d AI Act Implementing Act",
         "currentStatuses": [{"feedbackEndDate": "2026/11/09 23:59:59"}]},
        {"id": 14709.0, "shortTitle": "Digital Networks Act", "currentStatuses": [{"feedbackEndDate": "2026/09/07 00:00:00"}]}]}}
    ca = ("\ufeffregistration_number,title_en,start_date,end_date,status,profile_page_en,report_link_en,owner_org_title\n"
          "C-1,Consultation on trust in artificial intelligence,2026-07-23,2026-09-23,O,https://ca.example/ai,N/A,"
          "Innovation Canada | Innovation Canada FR\n"
          "C-2,Algorithmic pricing and competition,2025-06-10,2026-08-04,C,https://ca.example/ap,https://ca.example/r,"
          "Innovation Canada | Innovation Canada FR\n")
    def fetch(url):
        if "gov.uk" in url:
            return json.dumps(uk).encode()
        if "federalregister" in url:
            return json.dumps(us).encode()
        if "europa" in url:
            return json.dumps(eu).encode()
        if "canada" in url:
            return ca.encode()
        raise OSError("down")
    conn = store.connect(tmp_path / "t.db")
    today = date(2026, 10, 17)
    assert consultations.refresh(conn, fetch, today) == "UK 2, US 1, EU 1, Canada 2"  # one per title, both searches
    consultations.refresh(conn, lambda url: (_ for _ in ()).throw(OSError("down")), today)  # a list down keeps its rows
    assert len(consultations.load(conn)["Canada"]["rows"]) == 2
    for _ in range(2):  # a list down 3 runs in a row is failing, for source-alert to tell the inbox
        consultations.refresh(conn, lambda url: (_ for _ in ()).throw(OSError("down")), today)
    assert [r["name"] for r in store.newly_failing(conn, [u for u, _ in consultations.LISTS.values()])] == [
        "AI consultations: Consulting with Canadians (Canada)", "AI consultations: Federal Register (US)",
        "AI consultations: GOV.UK consultations (UK)", "AI consultations: Have Your Say (EU)"]
    consultations.refresh(conn, fetch, today)  # working again: no longer failing
    assert not store.newly_failing(conn, [u for u, _ in consultations.LISTS.values()])
    assert consultations.build(conn, [], tmp_path, today) == ["ai-consultations/"]
    page = (tmp_path / "ai-consultations" / "index.html").read_text(encoding="utf-8")
    open_, closed = page.split("Closed · past 6 months</h2>")
    assert open_.index("20 Oct 2026") < open_.index("9 Nov 2026") < open_.index("20 Nov 2026")  # closing soonest first
    assert open_.count('class="rm-soon"') == 1  # 20 Oct is within 14 days
    assert closed.index("23 Sep 2026") < closed.index("4 Aug 2026") < closed.index("1 Jun 2026")  # latest first
    assert "Growing up" not in page and "AIS" not in page and "Digital Networks" not in page
    assert 'href="https://ca.example/r" rel="noopener">Outcome published' in page and "Innovation Canada FR" not in page
    assert "<b>3</b><span>consultations on AI open now</span>" in page and "<b>4</b><span>places asked" in page


def test_ai_consultations_daily_job_finds_unchecked_ones_and_shows_rows_checked_by_hand(tmp_path, monkeypatch):
    import json
    from datetime import date
    from aipulse import consultations
    story = {"url": "https://news.example/au", "title": "Australia opens consultation on AI guardrails", "summary": "",
             "date": "2026-10-20T08:00:00", "category": "policy", "source": "Outlet"}
    quiet = dict(story, url="https://news.example/q", summary="The minister asked for public comments on AI rules.",
                 title="Minister speaks")  # asking the public, in the summary
    other = dict(story, url="https://news.example/o", title="Australia opens consultation on fishing quotas")
    old = dict(story, url="https://news.example/old", date="2026-10-01T08:00:00")
    industry = dict(story, url="https://news.example/i", category="news")
    assert [c["url"] for c in consultations.candidates([old, other, industry, story, quiet])] == [
        "https://news.example/au", "https://news.example/q"]
    monkeypatch.setattr(consultations, "LEFT_OUT", {"https://news.example/q": "not a consultation"})
    added = ("Australia", "Safe and responsible AI: mandatory guardrails", "Department of Industry", "2026-11-30",
             "https://consult.example/guardrails", "https://news.example/au")
    monkeypatch.setattr(consultations, "ADDED", [added])
    assert consultations.candidates([story, quiet]) == []  # both checked now
    uk = {"results": [{"title": "Growing up in the online world", "link": "/government/consultations/online",
                       "description": "Including AI chatbots", "end_date": "2026-10-30T23:59:00.000+00:00",
                       "content_store_document_type": "open_consultation"}]}
    empty = {"results": [], "initiativeResultDtoPage": {"last": True, "content": []}}
    fetch = lambda url: json.dumps(uk if "gov.uk" in url else empty).encode() if "canada" not in url else b"title_en\n"
    assert [r["title"] for r in consultations.summary_only(fetch, date(2026, 10, 17))] == ["Growing up in the online world"]
    conn = store.connect(tmp_path / "t.db")
    consultations.refresh(conn, fetch, date(2026, 10, 17))  # the page itself keeps titles naming AI only
    assert consultations.build(conn, [], tmp_path, date(2026, 10, 17)) == ["ai-consultations/"]
    page = (tmp_path / "ai-consultations" / "index.html").read_text(encoding="utf-8")
    assert "Growing up" not in page and "mandatory guardrails" in page
    assert 'class="rm-lab cs-australia"><span>Australia</span>' in page  # no list of its own to link
    base = open(consultations.__file__, encoding="utf-8").read()
    subject, text, html = consultations.note(base, "consultations/2026-10-20")
    assert subject == "AI Pulse, AI consultations: 1 new consultation to approve"
    assert "mandatory guardrails" in html and "30 Nov 2026" in html and "left out: 1 story" in text
    monkeypatch.setattr(consultations, "COMING", [
        ("India", "Paper on AI rules", "The ministry", "In the coming weeks", "https://news.example/in", "2026-10-26"),
        ("Atlantis", "An AI strategy", "The palace", "Next year", "https://news.example/at", "2026-06-01")])
    coming = consultations.body({}, date(2026, 10, 31))
    assert "<h2>Coming soon · not open yet</h2>" in coming and "Paper on AI rules" in coming and "said 26 Oct 2026" in coming
    assert "An AI strategy" not in coming  # said over 90 days ago: gone until said again
    assert 'data-v="soon" aria-pressed="false">Coming soon <b>1</b>' in coming
    assert "<b>1</b><span>places asked" in coming  # Australia's row: a promise isn't a place asking


def test_promises_approval_note_lists_new_promises_and_found_launches():
    from aipulse import promises
    src = open(promises.__file__, encoding="utf-8").read()
    shipped = next(u for u, v in promises.CHECKED.items() if v)
    left = next(u for u, v in promises.CHECKED.items() if v is None)
    base = src.replace(f'    "{left}": None,', "").replace(promises.CHECKED[shipped], "")  # a launch found since
    subject, text, html = promises.note(base, "promises/2026-10-18")
    assert "1 new promise to approve" in subject and promises.CHECKED[shipped] in text and "1 story" in text
    assert promises.note(src, "promises/2026-10-18") is None


def test_pacts_and_orders_halves_keep_only_rows_whose_story_we_have(tmp_path):
    from datetime import date
    from aipulse import pacts
    keep = [b for b in pacts.BANS if b[5] and b[5] != b[0]][0]  # one ban that was lifted
    cards = [{"url": u, "source": "Outlet", "title": "Story", "date": "2026-01-01"}
             for u in (keep[4], pacts.ORDERS[0][-1])]
    assert pacts.build(None, cards, tmp_path, date(2026, 10, 17)) == ["ai-pacts-and-orders/"]
    page = (tmp_path / "ai-pacts-and-orders" / "index.html").read_text(encoding="utf-8")
    assert keep[3] in page and pacts.ORDERS[0][4] in page and pacts.DEALS[0][3] not in page
    assert f"after {(date.fromisoformat(keep[5]) - date.fromisoformat(keep[0])).days} days" in page
    assert "New Delhi (2026) has the most signers: 92 countries and bodies" in page  # the official lists always show
    assert "pc-no\">China didn't sign" in page and "pc-no\">US didn't sign" in page  # US, UK, China per pledge
    assert 'class="pc-focus"' in page and "ratified 15/05/2026" in page and "law once 5 countries ratify; 1 so far" in page
    assert '<span class="pc-k fx-li">Lifted</span>' in page  # each ban tagged where it stands
    assert "Deals with AI companies" not in page  # no empty sections


def test_pacts_candidates_and_the_approval_note():
    from aipulse import pacts
    new = {"url": "https://x.example/a", "title": "Italy fines OpenAI over ChatGPT data", "date": "2026-10-20T08:00",
           "source": "Outlet", "category": "policy"}
    joins = new | {"url": "https://x.example/d", "title": "Bangladesh joins the New Delhi Declaration"}
    seen = new | {"url": pacts.ORDERS[0][-1]}
    old = new | {"url": "https://x.example/b", "date": "2026-10-16T09:00"}  # read for the lists already
    other = new | {"url": "https://x.example/c", "title": "OpenAI launches a new model"}  # no government acting
    assert pacts.candidates([new, joins, seen, old, other]) == [new, joins]
    base = open(pacts.__file__, encoding="utf-8").read().replace(pacts.ORDERS[-1][-1], "https://gone.example/")
    subject, text, html = pacts.note(base, "pacts/2026-10-18")
    assert "1 new row to approve" in subject and pacts.ORDERS[-1][-1] in text
    assert pacts.note(open(pacts.__file__, encoding="utf-8").read(), "pacts/2026-10-18") is None
    # pledge news is a row for the owner (the lists change only from the official list), not a story left out
    news = "https://x.example/joins"
    pacts.LEFT_OUT[news] = "pledge: Norway ratified the AI treaty on 1 Nov 2026"
    try:
        subject, text, html = pacts.note(open(pacts.__file__, encoding="utf-8").read(), "pacts/2026-11-02")
    finally:
        del pacts.LEFT_OUT[news]
    assert "1 new row to approve" in subject and "Norway ratified the AI treaty" in html and "left out" not in text


def test_fines_and_bans_halves_tags_and_links(tmp_path):
    from datetime import date
    from aipulse import fines
    assert fines.build(None, [], tmp_path, date(2026, 10, 19)) == ["ai-fines-and-bans/"]
    page = (tmp_path / "ai-fines-and-bans" / "index.html").read_text(encoding="utf-8")
    assert "<h1>AI fines and bans</h1>" in page and page.count('class="pc-half') == 2
    assert page.count("<td class=\"pc-d\" data-f=") == len(fines.BANS) + len(fines.FINES)
    # a dot per action on the time line, each linking to its row (with the page's path: every page has <base href="/">)
    assert page.count('class="fx-dot') == len(fines.BANS) + len(fines.FINES)
    assert all(f'id="fx-{h}{n}"' in page and f'href="ai-fines-and-bans/#fx-{h}{n}"' in page
               for h, rows in (("b", fines.BANS), ("f", fines.FINES)) for n in range(len(rows)))
    lifted = sum(r[7] is not None for r in fines.BANS)
    assert page.count(">Lifted<") == lifted + 1 and page.count(">In force<") == (  # + the time line's key
        len(fines.BANS) - lifted + sum(r[8] == "force" for r in fines.FINES) + 1)
    assert f"{len(fines.BANS) - lifted} still in force." in page and ">Annulled<" in page
    assert ">notice</a>" in page and ">report</a>" in page  # the regulator's own page, or a news report
    assert "€824,990,000 fine" in page and "$1,400,000,000 settlement" in page  # amounts as set, never added up
    # newest first in each half
    days = [fines._short(d) for d in sorted((r[0] for r in fines.BANS), reverse=True)]
    assert page.index(days[0]) < page.index(days[-1])


def test_fines_candidates_and_the_approval_note():
    from aipulse import fines
    new = {"url": "https://x.example/a", "title": "Spain's privacy watchdog fines AI app maker over face scans",
           "date": "2026-10-20T08:00", "source": "Outlet", "category": "policy"}
    sec = next(r[7] for r in fines.FINES if "sec.gov" in r[7])  # one notice written on one line
    seen = new | {"url": sec}
    old = new | {"url": "https://x.example/b", "date": "2026-10-18T09:00"}  # read for the lists already
    other = new | {"url": "https://x.example/c", "title": "Watchdog fines bank over late reports"}  # not about AI
    assert fines.candidates([new, seen, old, other]) == [new]
    base = open(fines.__file__, encoding="utf-8").read().replace(sec, "https://gone.example/")
    subject, text, html = fines.note(base, "fines/2026-10-20")
    assert "1 new row to approve" in subject and sec in text
    assert fines.note(open(fines.__file__, encoding="utf-8").read(), "fines/2026-10-20") is None


def test_chip_export_rules_grid_lists_and_notes(tmp_path):
    from datetime import date
    from aipulse import chip_rules as cr
    assert cr.build(None, [], tmp_path, date(2026, 10, 19)) == ["chip-export-rules/"]
    page = (tmp_path / "chip-export-rules" / "index.html").read_text(encoding="utf-8")
    assert "<h1>Chip export rules</h1>" in page and "photos/cartoons/features/chip-export-rules.svg" in page
    # a row per chip, a cell per US decision; the lead line holds only while every chip made for China was caught
    assert all(len(c[4]) == len(cr.COLUMNS) for c in cr.CHIPS) and cr.caught()
    assert page.count('<td class="') == len(cr.CHIPS) * len(cr.COLUMNS)
    assert "Every chip Nvidia and AMD made for China was caught by a later rule." in page
    # each list row links its official notice, or carries a footnote naming the outlet that reported it
    rows = cr.TOOLS + cr.BUYERS + cr.CHINA
    assert page.count("<li class=") == len(rows) and page.count(">notice</a>") == sum(cr.official(r[4]) for r in rows)
    assert all(r[4] in cr.REPORTS for r in rows if not cr.official(r[4])) and all(u in cr.REPORTS for u in cr.CHINA_SIDE)
    assert page.count("<li>Reported by ") == len(cr.CHINA_SIDE) + sum(not cr.official(r[4]) for r in rows)
    assert "<sup>1, 2</sup>" in page and ">Paused to 9 Nov 2026<" in page and ">update</a>" in page
    # newest first in each list
    assert page.index("2 Sep 2025") < page.index("13 Oct 2022")


def test_chip_rules_candidates_and_the_approval_note():
    from aipulse import chip_rules as cr
    new = {"url": "https://x.example/a", "title": "US tightens export controls on AI chips to Malaysia",
           "date": "2026-10-20T08:00", "source": "Outlet", "category": "policy"}
    fr = cr.BUYERS[0][4]
    seen = new | {"url": fr}
    old = new | {"url": "https://x.example/b", "date": "2026-10-18T09:00"}  # read for the lists already
    other = new | {"url": "https://x.example/c", "title": "Nvidia unveils a new gaming chip"}  # no rule
    assert cr.candidates([new, seen, old, other]) == [new]
    base = open(cr.__file__, encoding="utf-8").read().replace(fr, "https://gone.example/")
    subject, text, html = cr.note(base, "chips/2026-10-20")
    assert "1 new row to approve" in subject and fr in text
    assert cr.note(open(cr.__file__, encoding="utf-8").read(), "chips/2026-10-20") is None


def test_government_ai_use_reads_each_list_once_a_day_and_builds_the_page_and_each_lists_page(tmp_path):
    import json
    from datetime import datetime, timezone
    from aipulse import gov_ai
    us = ("﻿agency,agency_name,use_case_name,development_stage,is_high_impact,topic_area,classification,problem_solved,vendor_name\n"
          "VA,Department of Veterans Affairs,Suicide risk model,Deployed,High-impact,Health and Medical,Classical ML,Flags veterans at risk,\n"
          "NASA,National Aeronautics and Space Administration,Crater finder,Pre-deployment,Not High-impact,Science,Computer Vision,Maps craters,\n"
          "GSA,General Services Administration,Copilot Chat,Deployed,Not High-impact,Admin Functions,Generative AI,Drafts emails,Microsoft\n"
          "NASA,National Aeronautics and Space Administration,Amazon basin canopy model,Pilot,Not High-impact,Science,Classical ML,Maps forest,\n"
          "DOJ,Department of Justice,,Deployed,High-impact,Law Enforcement,NLP,No name given,\n")
    ca = ("﻿name_ai_system_en,government_organization,description_ai_system_en,ai_system_primary_users_en,developed_by_en,"
          "vendor_information,ai_system_status_en,involves_personal_information\n"
          "Primary Inspection Kiosk,Canada Border Services Agency / Agence des services frontaliers,Self-service for travellers,"
          "Members of public,Vendor,,In production ,Y\n"
          "Copilot for staff,Statistics Canada / Statistique Canada,Drafting,GC employees,Vendor,Microsoft Azure,in production,N\n")
    nl = ('﻿"name","organization","description_short","category","status","publication_category","algorithm_id","provider"\n'
          '"Werkzoekenden matchen","Gemeente Delft","Matchplaats ondersteunt de werkconsulent","Sociale zekerheid","In gebruik","Hoog-risico AI-systeem","111",""\n'
          '"Anonimiseren","Gemeente Midden-Groningen","Gevoelige informatie verbergen","Organisatie en bedrijfsvoering","In gebruik","Overige algoritmes","222","Microsoft"\n')
    uk = {"results": [
        {"title": "HMRC: VAT Assist", "link": "/algorithmic-transparency-records/hmrc-vat-assist",
         "description": "Compares tax return data", "public_timestamp": "2026-09-09T10:00:00Z"},
        {"title": "Disclosure and Barring Service Barring Referral AI Summary Tool",  # no "Body: Tool" colon
         "link": "/algorithmic-transparency-records/dbs", "description": "Summaries", "public_timestamp": "2026-10-14T10:00:00Z"}]}
    asked = []
    def fetch(url):
        asked.append(url)
        if "2025-Federal" in url:
            return us.encode()
        if "Federal" in url:
            raise OSError("404")  # next year's inventory isn't out yet
        if "package_show" in url:
            return json.dumps({"result": {"resources": [{"format": "PDF", "url": "https://ca.example/log.pdf"},
                                                        {"format": "CSV", "url": "https://ca.example/register.csv"}]}}).encode()
        if "ca.example/register.csv" in url:
            return ca.encode()
        if "algoritmes" in url:
            return nl.encode()
        if "gov.uk" in url:
            return json.dumps(uk).encode()
        raise OSError("down")
    conn = store.connect(tmp_path / "t.db")
    today = date(2026, 10, 20)
    assert gov_ai.build(conn, [], tmp_path, today) == []  # nothing read yet
    now = datetime(2026, 10, 20, 6, tzinfo=timezone.utc)
    assert gov_ai.refresh(conn, fetch, now) == "US 4, NL 2, CA 2, UK 2"
    n = len(asked)
    assert gov_ai.refresh(conn, fetch, now.replace(hour=12)) == "US read today, NL read today, CA read today, UK read today"
    assert len(asked) == n  # once a day
    down = lambda url: (_ for _ in ()).throw(OSError("down"))
    for d in (1, 2, 3):  # a list down 3 days running keeps its rows and is failing, for source-alert
        gov_ai.refresh(conn, down, now.replace(day=20 + d))
    assert len(gov_ai.load(conn)["US"]["rows"]) == 4
    assert len(store.newly_failing(conn, [p[3] for p in gov_ai.PLACES.values()])) == 4
    saved = gov_ai.load(conn)
    assert gov_ai.suppliers(saved["US"]["rows"])["Microsoft"] == 1 and gov_ai.suppliers(saved["US"]["rows"])["Amazon"] == 0
    assert gov_ai.build(conn, [], tmp_path, today) == ["government-ai-use/", "government-ai-use/united-states/",
                                                         "government-ai-use/netherlands/", "government-ai-use/canada/",
                                                         "government-ai-use/united-kingdom/"]
    page = (tmp_path / "government-ai-use" / "index.html").read_text(encoding="utf-8")
    assert "<h1>What governments use AI for</h1>" in page and "photos/cartoons/features/government-ai-use.svg" in page
    assert "<b>4 governments</b> publish a full list" in page and "Norway" in page and "Checked 20 Oct 2026" in page
    assert "In all 3 that name suppliers, <b>Microsoft</b> is named most (1 US, 1 Canadian, 1 Dutch)." in page
    assert page.index('href="government-ai-use/united-states/">Explore') < page.index("Norway")  # biggest list first
    assert "Suicide risk model" in page and "Crater finder" not in page  # cards show only uses that touch people
    assert "Primary Inspection Kiosk" in page and "<b>Canada Border Services Agency</b>" in page
    us_page = (tmp_path / "government-ai-use" / "united-states" / "index.html").read_text(encoding="utf-8")
    assert us_page.index("Suicide risk model") < us_page.index("Copilot Chat") < us_page.index("Crater finder")
    assert "<h1>What the United States uses AI for</h1>" in us_page and "Showing <b>4</b> of 4" in us_page
    nl_page = (tmp_path / "government-ai-use" / "netherlands" / "index.html").read_text(encoding="utf-8")
    assert 'href="https://algoritmes.overheid.nl/nl/algoritme/111"' in nl_page and nl_page.index("Werkzoekenden") < nl_page.index("Anonimiseren")
    ca_page = (tmp_path / "government-ai-use" / "canada" / "index.html").read_text(encoding="utf-8")
    assert ca_page.count('data-f="In production"') == 2  # "In production " and "in production" read as one status
    uk_page = (tmp_path / "government-ai-use" / "united-kingdom" / "index.html").read_text(encoding="utf-8")
    assert uk_page.index("14 Oct 2026") < uk_page.index("9 Sep 2026") and "<b>HMRC</b>" in uk_page
    assert ">Disclosure and Barring Service Barring Referral AI Summary Tool</a>" in uk_page


def test_government_ai_use_daily_job_finds_list_stories_rereads_counts_and_notes_changes(monkeypatch):
    from aipulse import gov_ai
    story = {"date": "2026-10-22", "title": "Scotland makes its AI register mandatory for all public bodies",
             "url": "https://news.example/sct", "source": "X", "category": "news"}
    business = {"date": "2026-10-22", "title": "Retailer shares 50 AI use cases with investors",
                "url": "https://news.example/biz", "source": "X", "category": "news"}
    old = dict(story, date="2026-10-01", url="https://news.example/old")
    assert [c["url"] for c in gov_ai.candidates([story, business, old])] == ["https://news.example/sct"]
    base = open(gov_ai.__file__, encoding="utf-8").read()
    assert gov_ai.note(base, "govai/2026-10-22") is None  # nothing changed
    pages = {"https://ki.norge.no/ki-tiltak": b"<p>151 tiltak</p>",
             "https://www.kratid.ee/kasutuslood-kratid": b"rakendatud kratte umbes 200 korral",
             "https://www.gov.br/governodigital/pt-br/infraestrutura-nacional-de-dados/inteligencia-artificial-1":
                 b"<b>182</b> solu&ccedil;&otilde;es de IA em opera&ccedil;&atilde;o"}
    def fetch(url):
        if url in pages:
            return pages[url]
        raise OSError("down")
    got = {p: now for p, _, now in gov_ai.recheck(fetch)}
    assert got["Norway"] == "page says 151" and got["Estonia"] == "page says 200" and got["Brazil"] == "page says 182"
    assert got["Scotland"].startswith("still not read")
    monkeypatch.setattr(gov_ai, "LEFT_OUT", {**gov_ai.LEFT_OUT, "https://news.example/sct": "already on the page"})
    assert gov_ai.candidates([story]) == []
    monkeypatch.setattr(gov_ai, "OTHERS", [("Norway", "no", "Offentlige KI-tiltak", "https://ki.norge.no/ki-tiltak",
                                             "151 initiatives", "KI Norge (Digdir)", "Reported by choice", "2026-10-22"),
                                            *gov_ai.OTHERS[1:]])
    subject, text, html = gov_ai.note(base, "govai/2026-10-22")
    assert subject == "AI Pulse, What governments use AI for: 1 new government list to approve"
    assert "151 initiatives" in text and "22 Oct 2026" in text and "Estonia" not in text
    assert "left out: 1 story" in text


def test_a_place_with_an_accent_gets_a_plain_address():
    from aipulse import countries
    assert countries.slug("Türkiye") == "turkiye" and countries.slug("United Kingdom") == "united-kingdom"
