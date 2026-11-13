"""Topics (storylines) and the monthly issue with its insights."""
from pathlib import Path

from aipulse import store

FIX = Path(__file__).parent / "fixtures"


def test_monthly_issues_are_numbered_from_january_2026():
    from datetime import date
    from aipulse import monthly
    ms = monthly.months(date(2026, 10, 11))
    assert ms[0] == "2026-01" and ms[-1] == "2026-09"  # 2026 only, and only months that are over
    assert monthly.number("2026-01") == 1 and monthly.number("2026-09") == 9
    assert monthly.name("2026-09") == "September 2026"


def test_monthly_summary_keeps_only_names_and_numbers_its_headlines_have():
    from aipulse import monthly
    def card(i, title, n=1, d="2026-09-10", cat="news"):
        return {"id": i, "title": title, "date": d, "category": cat, "source": "A", "url": f"https://x/{i}",
                "also": [{"source": f"S{k}"} for k in range(n - 1)]}
    cards = [card("a", "Google releases Gemini 4 Argon", 7, cat="tool"), card("b", "Mistral raises €3B", 4),
             card("c", "A paper on attention", 9, cat="research")]  # papers stay out of what the model reads
    p = monthly.prompt("2026-09", cards)
    assert "September 2026" in p and "(7 outlets) Google releases Gemini 4 Argon" in p and "paper" not in p
    heads = "September 2026 Google releases Gemini 4 Argon Mistral raises €3B"
    assert monthly.unsupported("Google released Gemini 4 Argon. Mistral raised €3B in September.", heads) == []
    # a name or number the headlines don't have; a sentence's first word may be any word
    assert monthly.unsupported("Meanwhile, OpenAI released GPT-7 for 5 dollars.", heads) == ["OpenAI", "GPT-7", "7", "5"]
    assert monthly.unsupported("A Google-led group met in the U.S. today.", heads + " US") == []  # "-led", "U.S." = "US"
    # a place by its adjective in the headlines; a place they don't name at all is left out
    assert monthly.unsupported("Regulators in Italy and China acted. Indonesia too.", "Italian and Chinese regulators") == ["Indonesia"]
    good = ("Google released Gemini 4 Argon, its most powerful model. " * 5 + "Mistral raised €3B.").strip()
    tries, prompts = iter(["OpenAI made a rival model this month, and it was quite large and good. " * 5, good]), []
    logs = []
    assert monthly.write("2026-09", cards, generate=lambda p, seed: prompts.append(p) or next(tries), log=logs.append) == good
    assert logs == ["  2026-09: try 1 left out (OpenAI)"]
    assert prompts[1].endswith("Do not mention OpenAI: the headlines don't.")  # the next try is told what was wrong
    assert monthly.write("2026-09", cards, generate=lambda p, seed: "Too short.", log=lambda *_: None) is None
    long = "Google released Gemini 4 Argon. " * 8  # 8 sentences: a list of headlines, not a summary
    assert monthly.write("2026-09", cards, generate=lambda p, seed: long, log=lambda *_: None) is None


def test_monthly_issue_pages(tmp_path):
    import json
    from datetime import date
    from aipulse import monthly
    conn = store.connect(tmp_path / "m.db")
    monthly.connect(conn)
    conn.execute("INSERT INTO monthly VALUES ('2026-08', 'August in brief.', 'test', '2026-09-01')")
    def card(i, title, n=1, d="2026-08-10", cat="news"):
        return {"id": i, "title": title, "date": d, "category": cat, "source": "A", "url": f"https://x/{i}",
                "summary": "", "tags": [], "also": [{"source": f"S{k}"} for k in range(n - 1)]}
    cards = [card("a", "Big launch of a reasoning model", 5, "2026-08-03", "tool"), card("b", "Small news", 1, "2026-08-20"),
             card("c", "Funding round", 3, "2026-08-25"), card("d", "September story", 2, "2026-09-02")]
    paths = monthly.build(conn, cards, tmp_path, date(2026, 10, 11))
    assert paths == ["monthly/", "monthly/2026-08/", "monthly/2026-09/"]  # October isn't over
    page = (tmp_path / "monthly" / "2026-08" / "index.html").read_text(encoding="utf-8")
    assert "<h1>August 2026</h1>" in page and "No. 8" in page and "August in brief." in page
    # the top headlines are in the HTML for search engines (seo.py, owner 6 Nov 2026), the full view from issue.json
    assert 'rel="noopener">Big launch of a reasoning model</a>' in page and "September story" not in page
    assert 'href="/monthly/2026-09/">September 2026 →' in page
    assert '<a href="/monthly/2026-08/#streams">' in page  # the contents: this page's sections (its <base> is "/")
    issue = json.loads((tmp_path / "monthly" / "2026-08" / "issue.json").read_text(encoding="utf-8"))
    assert [e["title"] for e in issue["top"]] == ["Big launch of a reasoning model", "Funding round", "Small news"]
    assert "weeks" not in issue and 'id="weeks"' not in page  # Week by week: dropped, it repeated the sections above
    assert "Reasoning model" in [w["term"] for w in monthly.words(monthly.word_counts(cards * 5), [], "2026-08")]
    front = json.loads((tmp_path / "monthly" / "front.json").read_text(encoding="utf-8"))
    assert [f["name"] for f in front] == ["September 2026", "August 2026"]  # the newest two, newest first
    assert front[0]["lede"] == "" and front[1]["lede"] == "August in brief."  # no summary yet: none shown
    assert monthly.lede("A U.S. court ruled. Then more.") == "A U.S. court ruled."
    shelf = (tmp_path / "monthly" / "index.html").read_text(encoding="utf-8")
    assert shelf.index("September") < shelf.index("August")  # newest first


def test_monthly_rules_that_moved_reads_every_tracked_law():
    from aipulse import monthly
    def law(key, title, d, steps):
        return {"id": key, "title": f"{key}: {title}", "date": d, "category": "regulation", "bill": key, "source": "Gov",
                "url": f"https://x/{key}", "lifecycle": {"url": f"https://gov/{key}", "source": "Gov", "steps": steps}}
    s = lambda stage, label, d: {"stage": stage, "label": label, "date": d}
    laws = [law("KR-1", "AI Basic Act", "2026-09-30",  # dated its latest stage, months after the one it passed in August
                [s("introduced", "Introduced", "2026-05-01"), s("passed_chamber", "Passed", "2026-08-01"),
                 s("signed", "Promulgated", "2026-08-04"), s("in_force", "In force", "2026-09-30")]),
            law("CH-2", "Motion on AI", "2026-08-20", [s("introduced", "Submitted", "2026-08-02"),
                                                         s("withdrawn", "Closed", "2026-08-20")]),
            law("US-3", "An introduced bill", "2026-08-09", [s("introduced", "Introduced", "2026-08-09")]),
            {"id": "s", "title": "ISO/IEC 42099: AI something", "date": "2026-08-01", "category": "regulation",
             "bill": "STD-ISO/IEC-42099", "source": "ISO/IEC", "url": "https://iso/42099"}]
    rows = monthly.rules(laws, "2026-08")
    assert [(r["badge"], r["title"], r["label"]) for r in rows] == [
        ("signed", "AI Basic Act", "Promulgated"),  # the furthest stage of the month; the official wording kept
        ("standard", "ISO/IEC 42099: AI something", "Published"), ("withdrawn", "Motion on AI", "Closed")]
    assert rows[0]["flag"] == "kr.svg" and rows[1]["flag"] == "intl.svg"
    assert monthly.issue("2026-08", [], {}, laws)["rules"] == rows  # the month's cards alone would miss KR-1
    assert monthly.rules(laws, "2026-07") == []


def test_monthly_brief_marks_the_names_its_headlines_have():
    from aipulse import monthly
    cards = [{"title": t, "date": "2026-07-02", "category": "news", "source": "A", "url": f"https://x/{i}"}
             for i, t in enumerate(["Moonshot ships Kimi K3", "Google DeepMind shows Gemini Robotics 2",
                                    "An AI-powered hack hits Hugging Face", "Europe and Microsoft agree"])]
    html = monthly.marked("Moonshot AI released Kimi K3. Google DeepMind's Gemini Robotics 2 & an AI-powered hack.", cards)
    assert html == ("<mark>Moonshot AI</mark> released <mark>Kimi K3</mark>. <mark>Google DeepMind&#x27;s Gemini Robotics 2</mark>"
                    " &amp; an AI-powered hack.")  # escaped; "AI-powered" isn't a name


def test_monthly_summary_that_fails_every_try_is_not_tried_again(tmp_path, monkeypatch):
    from datetime import date
    from aipulse import monthly
    conn = store.connect(tmp_path / "f.db")
    monthly.connect(conn)
    monkeypatch.setattr(monthly, "months", lambda today: ["2026-08"])
    monkeypatch.setattr(monthly, "month_cards", lambda conn, m: [{"id": "a"}])
    monkeypatch.setattr(monthly, "write", lambda m, cards, log: None)
    monkeypatch.setitem(monthly._llm, "m", object())  # the model is there; its text failed the check
    assert monthly.summarise(conn, date(2026, 10, 11), log=lambda *_: None) == 0
    assert [tuple(r) for r in conn.execute("SELECT month, summary FROM monthly")] == [("2026-08", "")]
    assert monthly.due(conn, date(2026, 10, 11)) == []  # the next run doesn't download the model again for it


def test_insights_rivals_numbers_sit_outside_the_bar_and_labs_group_by_home():
    from collections import Counter
    from aipulse import insights
    html = insights._rivals([("Papers", 90, 10, [("2026-09", .4), ("2026-10", .1)])], Counter({"Baidu": 1, "KRAFTON": 2}), "2026-10")
    assert "China <b>10</b> · 10%" in html and '<i class="cn" style="width:10.0%"></i>' in html  # a narrow share can't clip its label
    assert "usual 40%" in html and "<b>10%</b>" in html
    assert "<td>China</td><td>Baidu 1</td>" in html and "<td>Others</td><td>KRAFTON 2</td>" in html and "<td>US</td>" not in html


def test_insights_counts_against_the_month_before():
    from aipulse import insights
    assert insights.change(13, 10) == "+30%" and insights.change(9, 10) == "−10%" and insights.change(10, 10) == "same"
    assert insights.change(7, 1) == "was 1" and insights.change(3, 0) == "new"
    card = lambda d, cat, tags: {"date": d, "category": cat, "tags": tags, "title": "A story", "url": "u", "source": "A"}
    by = {"2026-08": [card("2026-08-03", "news", ["OpenAI"])] * 10,
          "2026-09": [card("2026-09-01", "news", ["OpenAI", "United States"])] * 12 + [card("2026-09-06", "tool", ["Anthropic"])]}
    x = insights.numbers("2026-09", by)
    assert [s for s, _ in x["shares"]] == []  # too few stories in the year to say anything
    assert x["companies"][0] == ("OpenAI", 12, 10) and x["places"] == [("United States", 12, 0)]
    assert len(x["daily"]) == 30 and dict(x["daily"])[__import__("datetime").date(2026, 9, 1)] == 12
    assert "Companies in the news" in insights.body("2026-09", x)


def test_insights_busiest_days_need_a_story_two_outlets_carried():
    from datetime import date, timedelta
    from aipulse import insights
    def card(d, n, outlets=1):
        return [{"date": d, "category": "news", "title": f"Story {d} {k}", "url": f"u{d}{k}", "source": "A",
                 "also": [{"source": f"S{j}"} for j in range(outlets - 1)] if k == 0 else []} for k in range(n)]
    mine = []
    for k in range(30):
        d = (date(2026, 9, 1) + timedelta(days=k)).isoformat()
        mine += card(d, 30 if d == "2026-09-29" else 25 if d == "2026-09-15" else 10, outlets=3 if d == "2026-09-29" else 1)
    from collections import Counter
    days = Counter(c["date"] for c in mine)
    daily = [(date(2026, 9, 1) + timedelta(days=k), days[(date(2026, 9, 1) + timedelta(days=k)).isoformat()]) for k in range(30)]
    p = insights.peaks(mine, daily)
    assert [x["day"] for x in p] == ["2026-09-29"]  # the 15th was busy too, but no story two outlets carried
    assert p[0]["x"] == 3.0 and p[0]["stories"][0]["outlets"] == 3


def test_money_reads_rounds_valuations_and_deals_from_headlines():
    from aipulse import money
    def r(title):
        return money.read({"title": title, "url": "u"})
    a = r("Viral AI agent Instinct raises $1B Series C at a $10B valuation")
    assert (a["kind"], a["company"], a["amount"], a["valuation"]) == ("round", "Instinct", 1e9, 1e10)
    b = r("Nvidia confirms it will buy Hugging Face for $12.9 billion")
    assert (b["kind"], b["company"], b["partner"], b["amount"]) == ("acquisition", "Nvidia", "Hugging Face", 12.9e9)
    c = r("Anthropic signs $9.1 billion data center deal with Bitcoin miner Riot Platforms")
    assert (c["kind"], c["company"], c["partner"]) == ("compute", "Anthropic", "Riot Platforms")
    d = r("OpenAI reportedly in talks to raise $30B round at $1.4T valuation")
    assert d["reported"] and d["company"] == "OpenAI" and d["valuation"] == 1.4e12
    assert r("AI voice startup ElevenLabs doubles valuation to $22B")["company"] == "ElevenLabs"
    assert r("After Nvidia's $20B not-acqui-hire, AI chip startup Groq reportedly raising $650M")["amount"] == 650e6
    assert r("China blocks Meta's $2 billion acquisition of AI startup Manus") is None
    assert r("AI research startup Listen Labs scrubbed a $1.5B funding round for Salesforce talks") is None
    assert r("Nvidia boosts share buyback program by record $150B") is None
    assert money.usd(12.9e9) == "$12.9B" and money.usd(1.4e12) == "$1.4T" and money.usd(300e6) == "$300M"


def test_insights_legal_risk_needs_a_lawsuit_or_a_regulator_acting():
    from aipulse import insights
    def kind(t):
        return "court" if insights.COURT.search(t) else "reg" if insights.REGULATOR.search(t) else None
    assert kind("Class action lawsuit accuses Anthropic of overselling Claude subscriptions") == "court"
    assert kind("Judge Rules DOD Unlawfully Retaliated Against Anthropic") == "court"
    assert kind("FTC launches sweeping probe into OpenAI, Anthropic, and other AI labs") == "reg"
    assert kind("Australia to investigate if OpenAI hack of government health website broke the law") == "reg"
    assert kind("The Honourable Mr Justice Claude – generative AI in the courtroom") is None
    assert kind("Former OpenAI researcher builds an AI model that judges options instead of writing text") is None
    assert kind("Nvidia wants to keep AI agents on a short leash with a watchdog built into its chips") is None
    rows = insights.exposure([{"title": "Perplexity AI sued over alleged data sharing with Meta and Google", "summary": ""}] * 2)
    assert rows == [("Perplexity", 2, 0, 0)]
    ups = insights.open_models([{"title": "Xiaomi MiMo publishes MiMo-V2.6-Flash on Hugging Face", "category": "tool",
                                 "date": "2026-09-21"}])
    assert ups == [{"lab": "Xiaomi", "date": "2026-09-21"}] and insights.home("Qwen") == "China"


def test_topics_a_story_joins_by_words_or_approval_and_the_net_only_suggests(monkeypatch):
    from aipulse import topics
    card = {"category": "news", "title": "Anthropic expected to get a junk rating", "summary": "", "date": "2026-10-30",
            "url": "https://x.test/a", "source": "X", "tags": ["IPO", "Anthropic"], "also": [{"url": "https://x.test/b"}]}
    assert not topics.matches("ai-ipos", card)  # tags alone never join a story to a topic
    assert topics.part_of(card) == []
    assert [c["for"] for c in topics.candidates([card])] == [["ai-ipos"]]
    assert topics.candidates([card], "2026-10-31") == []
    monkeypatch.setattr(topics, "ADDED", {"ai-ipos": {"https://x.test/b": "Its rating after the IPO"}})  # another outlet's URL
    assert topics.matches("ai-ipos", card)
    assert topics.part_of(card) == [["ai-ipos", "OpenAI and Anthropic go public"]]
    assert topics.candidates([card]) == []
    monkeypatch.setattr(topics, "ADDED", {})
    monkeypatch.setattr(topics, "LEFT_OUT", {"https://x.test/a"})
    assert topics.candidates([card]) == [] and not topics.matches("ai-ipos", card)


def test_topics_model_net_suggests_only_on_a_clear_close_vote(monkeypatch):
    from aipulse import topics
    monkeypatch.setattr(topics, "ADDED", {}), monkeypatch.setattr(topics, "LEFT_OUT", set())

    def card(url, title, day, cat="news"):
        return {"category": cat, "title": title, "summary": "", "date": day, "url": url, "source": "X", "tags": []}
    ipo = [card(f"https://x.test/ipo{i}", f"Anthropic IPO filing {i}", "2026-10-01") for i in range(8)]
    other = [card(f"https://x.test/o{i}", f"Other news {i}", "2026-10-01") for i in range(5)]
    new = card("https://x.test/new", "Anthropic's stock listing", "2026-11-09")
    far = card("https://x.test/far", "Weather today", "2026-11-09")
    paper = card("https://x.test/p", "A paper on listings", "2026-11-09", "research")

    def encode(texts):  # IPO stories and the new listing story point one way, everything else the other
        import numpy as np
        return np.array([[1.0, 0.0] if ("IPO" in t or "listing" in t) else [0.0, 1.0] for t in texts])
    alike = topics.near(ipo + other + [new, far, paper], "2026-11-01", encode)
    assert alike == {"https://x.test/new": {"ai-ipos": "Anthropic IPO filing 0"}}  # not the weather, not a paper
    got = topics.candidates([new, far], "2026-11-01", alike)
    assert [(c["url"], c["for"], c["like"]) for c in got] == [("https://x.test/new", ["ai-ipos"], alike["https://x.test/new"])]
    assert topics.near(ipo[:6] + other + [new], "2026-11-01", encode) == {}  # six of ten isn't a clear vote
    monkeypatch.setattr(topics, "LEFT_OUT", {"https://x.test/new"})
    assert topics.near(ipo + other + [new], "2026-11-01", encode) == {}  # already decided


def test_topics_every_net_and_added_slug_is_sound():
    from aipulse import topics
    for t in topics.TOPICS.values():
        assert all(isinstance(n, set) and n for n in t.get("net", ()))
    assert set(topics.ADDED) <= set(topics.TOPICS)
    assert not topics.LEFT_OUT & {u for urls in topics.ADDED.values() for u in urls}


def test_topics_rule_fixes():
    from aipulse import topics
    def hit(slug, title, category="news"):
        return topics.matches(slug, {"category": category, "title": title, "summary": ""})
    assert hit("eu-ai-act", "First harmonised standard supporting the AI Act published in the Official Journal")
    assert hit("california-ai-laws", "California's new law bans companies from relying on AI to fire workers")
    assert hit("deepseek-us", "US banning Chinese AI DeepSeek from government agency IT systems")
    assert not hit("deepseek-us", "Perplexity AI removes Chinese censorship from Deepseek R1")
    assert hit("openai-microsoft", "Microsoft recorded $10 billion in revenue from OpenAI")
    assert hit("chatbots-teens", "Character.AI bans under-18s from open-ended chats")
    assert not hit("chatbots-teens", "Character.AI taps a new CEO")
    assert not hit("data-centre-power-bills", "A new class of batteries helps data centers play nicely with the grid")


def test_topics_note_lists_what_the_branch_adds(monkeypatch):
    from aipulse import topics
    base = 'ADDED = {"ai-ipos": {"https://x.test/old": "x"}}\nLEFT_OUT = {"https://x.test/gone"}\n'
    monkeypatch.setattr(topics, "ADDED", {"ai-ipos": {"https://x.test/old": "x", "https://x.test/new": "Rating after the IPO"}})
    monkeypatch.setattr(topics, "LEFT_OUT", {"https://x.test/gone", "https://x.test/no"})
    subject, text, html = topics.note(base, "topics/2026-10-31")
    assert subject == "AI Pulse, Follow the story: 1 new story to approve"
    assert "Rating after the IPO" in html and "https://x.test/old" not in html and "1 story" in text
    monkeypatch.setattr(topics, "ADDED", {"ai-ipos": {"https://x.test/old": "x"}})
    monkeypatch.setattr(topics, "LEFT_OUT", {"https://x.test/gone"})
    assert topics.note(base, "topics/2026-10-31") is None


def test_money_headlines_read_right():
    from aipulse import money
    read = lambda t: money.read({"url": "x", "title": t})
    assert read("Anthropic’s Computing Infrastructure Commitments Could Exceed $542 Billion") is None  # a tally
    assert read("DayOne secures US$3.7 billion loan for Malaysia expansion") is None  # debt, not a round
    assert read("Meta to raise up to $95 billion in equity to fund costly AI") is None  # a share sale, not a round
    assert read("AirTrunk raises US$2.3 billion in green financing for its campus") is None
    assert read("AirTrunk secures AU$4.25bn funding for Sydney campus") is None  # not US dollars
    d = read("Naver Signs $9 Billion AI Infrastructure Deal With Brookfield")
    assert (d["company"], d["partner"]) == ("Naver", "Brookfield")
    d = read("Anthropic to pay Akamai $11.6 billion over seven years in cloud deal")
    assert (d["company"], d["partner"]) == ("Anthropic", "Akamai")
    assert read("Chinese Tech Firms Order $35 Billion Nvidia GPUs in compute deal")["company"] != "Billion Nvidia GPUs"
    assert read("Anthropic targets November IPO at $2 trillion valuation")["company"] == "Anthropic"


def test_money_same_amount_different_companies_stay_apart():
    from aipulse import money
    card = lambda t, d: {"url": t, "title": t, "summary": "", "date": d, "source": "x", "category": "news"}
    rows = money.month([card("Partly raises $50M at a $500M valuation", "2026-06-23"), card("Patronus AI lands $50M for tests", "2026-06-25")])
    assert {(r["company"], r["valuation"]) for r in rows} == {("Partly", 5e8), ("Patronus", 0.0)}


def test_monthly_summary_corrections():
    from aipulse import monthly
    fixed = monthly.corrected("2026-10", "OpenAI reported finding a recording device in its offices and disabled its own safety systems.")
    assert "OpenAI’s agents disabled their own safety monitoring systems" in fixed
    for month, pairs in monthly.FIXES.items():
        assert all(wrong != right for wrong, right in pairs), month
