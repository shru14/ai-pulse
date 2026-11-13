"""Sorting stories: AI or not, which stream, release vs news vs policy vs regulation, places and tags."""
from datetime import date
from pathlib import Path

from aipulse import classify, feeds, store
from aipulse.collect import apply_regulation, collect, reclassify

FIX = Path(__file__).parent / "fixtures"


def test_categorize():
    assert classify.categorize("Senate passes AI Act amendment on frontier models", "") == "policy"
    assert classify.categorize("Mistral launches new open-weight model, available via API", "") == "tool"
    assert classify.categorize("AI startup raises $200M", "", "news") == "news"
    assert classify.is_ai_related("Weather today", "Sunny") is False


def test_policy_search_story_about_a_private_person_is_news():
    # A place that only describes a person or business doesn't keep a story under "policy".
    for title in ['The bank executive who used AI to dress her family in "Lake America" sweatshirts is no longer employed',
                  "Michigan CEO loses job after posting AI-made image of her family in 'Lake America' sweaters",
                  "Michigan credit union CEO out after posting AI photo"]:
        assert classify.categorize(title, "", "policy") == "news", title
    assert classify.categorize("Maryland Sets AI Guardrails as States Confront Data Center Boom", "", "policy") == "policy"


def test_policy_groups_own_stories_stay_policy():
    # A policy newsroom's own piece is Policy whatever its headline (Tech Policy Press, 12 Nov 2026, was Industry).
    from aipulse.collect import policy_feed_keeps, stream_of
    from aipulse.sources import SOURCES
    by = {s["name"]: s for s in SOURCES}
    dublin = "Europe’s AI Future and Security Challenges Take Center Stage at Dublin Summit"
    assert policy_feed_keeps(by["Tech Policy Press"]) and stream_of(by["Tech Policy Press"], dublin, "", "https://e.com/1") == "policy"
    # Groups that also repost general press have each story checked: government stays, business news goes.
    cset = by["CSET"]
    assert not policy_feed_keeps(cset)
    for title in ["Hegseth warns Anthropic to let the military use the company’s AI tech as it sees fit, AP sources say",
                  "DOD expands its classified AI work with 8 companies — excluding Anthropic — amid ongoing dispute",
                  "AI Now Senior Fellow Dr. Katie J. Wells Testifies before the House Subcommittee on Workforce Protections",
                  "NextGov: OMB wants public input on privacy impact assessments",
                  "How Trump’s new H-1B fee will hurt Silicon Valley and AI startups"]:
        assert stream_of(cset, title, "", "https://e.com/2") == "policy", title
    for title in ["Chipmaker Nvidia joins exclusive club of companies with a $1 trillion market capitalization",
                  "SpaceX Files to Go Public, Setting Stage for Huge I.P.O.", "How Nvidia became an AI giant"]:
        assert stream_of(cset, title, "", "https://e.com/3") == "news", title
    # The wider words only keep a policy story; a tech outlet's Pentagon deal is still Industry.
    assert classify.categorize("OpenAI signs Pentagon contract for military AI", "", "news") == "news"
    # A staff line in a summary ("leader of its AI and human rights project") doesn't keep a press repost.
    assert classify.categorize("CNBC: OpenAI is pursuing a new way to fight A.I. ‘hallucinations’",
                               "Ben Winters, leader of its AI and human rights project, expressed skepticism", "policy") == "news"


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


def test_any_country_can_be_a_tag():
    assert classify.tags_for("Japan and Brazil weigh new AI rules for OpenAI", "") == ["OpenAI", "Japan", "Brazil"]
    assert classify.tags_for("EU Commission opens AI consultation", "") == ["European Union"]
    assert "Kenya" in classify.tags_for("Kenya signs AI framework", "")


def test_an_order_about_names_is_policy_not_law():
    from aipulse.classify import regulatory_action
    assert regulatory_action("Trump orders US government to call AI ‘Super Intelligence’") is None
    assert regulatory_action("Newsom orders new steps on AI safety") == "law"


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


def test_msit_press_releases_parse():
    page = ("""$('#td_'+'NTT_SJ'+'_0').html('<a href="javascript:;" onclick="fn_detail("1290")" class="" data-value="1290">"""
            """<span>MSIT Announces the Enforcement Decree of the AI Basic Act</span></a></b>');"""
            """ //$('#td_'+'NTT_SJ'+'_0').html('<a href="javascript:;" onclick="fn_detail("1290")" class="" data-value="1290">"""
            """<span>MSIT Announces the Enforcement Decree of the AI Basic Act</span>');"""
            """ if('REG_DT' == 'REG_DT'){ $('#td_'+'REG_DT'+'_0').html('Jan 22, 2026'); }""").encode()
    [e] = feeds.parse_msit(page)
    assert e["title"] == "MSIT Announces the Enforcement Decree of the AI Basic Act"
    assert e["url"].endswith("bbsSeqNo=42&nttSeqNo=1290") and e["published"].date().isoformat() == "2026-01-22"


def test_non_ai_agents():
    from aipulse import classify
    assert not classify.is_ai_related("New law on foreign agents", "") and classify.is_ai_related("OpenAI ships agents", "")


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


def test_standards_news_is_never_a_release():
    from aipulse.classify import categorize
    assert categorize("NIST launches AI Agent Standards Initiative as autonomous AI moves into production", "", "news") == "policy"
    assert categorize("NIST releases a tool for testing AI model risk", "", "news") == "policy"
    assert categorize("Acme achieves ISO/IEC 42001 certification for its AI platform", "", "tool") == "news"
    assert categorize("OpenAI launches GPT-6 with new API features", "", "news") == "tool"  # releases unaffected


def test_lab_blog_posts_that_launch_nothing_and_what_counts_as_policy():
    # Seen on the labs' blogs restored on 10 Oct 2026: how-tos, roundups, donations and customer stories aren't releases,
    # and a security team's investigation isn't a regulator's.
    from aipulse.classify import categorize
    for title in ["Best practices guide for customizing Gemini models via Reinforcement Learning (RL)",
                  "Why your startup needs open models alongside frontier APIs",
                  "The latest AI news we announced in September 2026",
                  "See what 4 builders are making with Gemini 3.8 Flash",
                  "Meta Donates 1,000 AI Glasses to Singapore's Disability Community",
                  "Radisson Hotel Group brings hotel discovery into ChatGPT",
                  "Sophos cuts threat investigation time by 96% with OpenAI Daybreak",
                  "Automate remediation post AWS DevOps Agent investigation"]:
        assert categorize(title, "", "tool") == "news", title
    assert categorize("OpenAI brings GPT-6 to ChatGPT", "", "tool") == "tool"
    assert categorize("Gemini 4 Argon: our next era of frontier intelligence", "", "tool") == "tool"
    assert categorize("FTC opens investigation into OpenAI", "", "news") == "policy"
    # summits of governments and elections are policy; trade events and "Selection" aren't
    assert categorize("Balancing the AI revolution: Lessons from BRICS New Delhi Summit", "", "news") == "policy"
    assert categorize("Containment is dead: Five takeaways from the AI ROI in Contact Center Summit", "", "news") == "news"
    assert categorize("Kenyan political operator used Claude to mass-produce election propaganda", "", "news") == "policy"
    assert categorize("Selection Result Announced for the AI Foundation Model Programme", "", "news") != "policy"


def test_translation_note_is_not_a_place():
    from aipulse.classify import tags_for
    note = " Machine-translated from Portuguese; the official text is linked."
    assert "Portugal" not in tags_for("PL 3392/2026: Establishes minimum standards for AI in judicial procedures", note)
    assert "Germany" not in tags_for("Motion: AI in the federal administration", note.replace("Portuguese", "German"))
    assert "Portugal" in tags_for("Portugal adopts an AI strategy", "")


def test_release_notes_keep_only_the_labs_own_launches(tmp_path):
    from aipulse import collect as col
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
    labs = [  # both dropped (7 Oct 2026 terms audit); their readers stay tested
        {"name": "xAI", "url": "https://docs.x.ai/developers/release-notes", "format": "page_list", "notes": "xai_notes",
         "keep": r"^(?:Grok|SpaceXAI|xAI)\b", "category": "tool"},
        {"name": "Perplexity", "url": "https://docs.perplexity.ai/changelog", "format": "page_list",
         "notes": "perplexity_notes", "keep": r"\b(?:Perplexity|Sonar|Comet)\b", "category": "tool"}]
    for src in labs:
        assert col.page_list_entries(conn, src, pages.get) == []  # first read: remembered only
        conn.execute("INSERT OR REPLACE INTO meta VALUES (?, '[]')", (f"page_list:{src['name']}",))  # as if all were new
    kept = {src["name"]: [e["title"] for e in col.page_list_entries(conn, src, pages.get)] for src in labs}
    # Only their own products' launches: not an API field, a retirement, or another lab's model Perplexity now offers.
    assert kept == {"xAI": ["Grok 4.7"], "Perplexity": ["Introducing New and Improved Sonar Models"]}


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
    # a feed that gives its links as paths (as the EIA's did) is stored with full addresses
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    feed = (f"<rss><channel><item><title>Data centers drive US electricity demand</title><link>/pressroom/releases/press592.php</link>"
            f"<pubDate>{day}</pubDate></item></channel></rss>").encode()
    energy = {"name": "Energy office", "url": "https://energy.example/rss/press_rss.xml", "category": "infra", "infra_filter": True}
    collect(conn, [energy], fetcher=lambda u: feed, log=lambda m: None, official_bills=False)
    assert store.exists(conn, "https://energy.example/pressroom/releases/press592.php")
    # a feed's paid posts, marked by their category (IEEE Spectrum's), are never stories
    feed = (f"<rss><channel><item><title>AI servers keep cool</title><link>https://mag.example/ad</link><category>Type-sponsored"
            f"</category><pubDate>{day}</pubDate></item><item><title>AI agents collude</title><link>https://mag.example/news</link>"
            f"<category>Type-news</category><pubDate>{day}</pubDate></item></channel></rss>").encode()
    mag = {"name": "Mag", "url": "https://mag.example/rss", "category": "news", "skip_category": r"^Type-sponsored$"}
    collect(conn, [mag], fetcher=lambda u: feed, log=lambda m: None, official_bills=False)
    assert store.exists(conn, "https://mag.example/news") and not store.exists(conn, "https://mag.example/ad")


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


def test_a_labs_new_github_repositories_people_took_up_are_releases():
    import json
    repos = [{"name": "Kimi-K3", "description": "Open Frontier Intelligence model weights", "fork": False,
              "stargazers_count": 8899, "created_at": "2026-07-27T08:00:00Z", "html_url": "https://github.com/MoonshotAI/Kimi-K3",
              "owner": {"login": "MoonshotAI"}},
             {"name": "kimi-internal-tool", "description": "An internal component", "fork": False, "stargazers_count": 12,
              "created_at": "2026-07-28T08:00:00Z", "html_url": "https://github.com/MoonshotAI/kimi-internal-tool",
              "owner": {"login": "MoonshotAI"}},
             {"name": "awesome-kimi", "description": "A list", "fork": False, "stargazers_count": 900,
              "created_at": "2026-07-28T08:00:00Z", "html_url": "https://github.com/MoonshotAI/awesome-kimi",
              "owner": {"login": "MoonshotAI"}},
             {"name": "vllm", "description": "A fork", "fork": True, "stargazers_count": 5000,
              "created_at": "2026-07-28T08:00:00Z", "html_url": "https://github.com/MoonshotAI/vllm", "owner": {"login": "MoonshotAI"}}]
    entries = feeds.parse_github_repos(json.dumps(repos).encode(), lab="Moonshot AI")
    assert [e["title"] for e in entries] == ["Moonshot AI publishes Kimi-K3 on GitHub"]
    assert entries[0]["published"].date() == date(2026, 7, 27)


def test_a_labs_hugging_face_release_is_one_story_for_all_its_sizes():
    import json
    models = [{"id": "Qwen/Qwen3-8B", "createdAt": "2025-04-27T03:00:00Z", "likes": 900, "pipeline_tag": "text-generation"},
              {"id": "Qwen/Qwen3-0.6B-Base", "createdAt": "2025-04-27T02:00:00Z", "likes": 200},
              {"id": "Qwen/Qwen3-235B-A22B", "createdAt": "2025-04-28T00:00:00Z", "likes": 1200, "pipeline_tag": "text-generation"},
              {"id": "Qwen/Qwen3-8B-GGUF", "createdAt": "2025-04-20T00:00:00Z", "likes": 400},  # a compressed copy
              {"id": "Qwen/Qwen3-Coder-480B-A35B-Instruct", "createdAt": "2025-07-22T00:00:00Z", "likes": 1500},
              {"id": "Qwen/Qwen-tiny-test", "createdAt": "2025-08-01T00:00:00Z", "likes": 12},
              {"id": "Qwen/Qwen3.6-2603", "createdAt": "2025-12-01T00:00:00Z", "likes": 500}]
    entries = feeds.parse_hf_models(json.dumps(models).encode(), lab="Qwen")
    assert [(e["title"], e["url"], e["published"].date()) for e in entries] == [
        ("Qwen publishes Qwen3 on Hugging Face", "https://huggingface.co/Qwen/Qwen3-0.6B-Base", date(2025, 4, 27)),
        ("Qwen publishes Qwen3-Coder-480B-A35B-Instruct on Hugging Face",
         "https://huggingface.co/Qwen/Qwen3-Coder-480B-A35B-Instruct", date(2025, 7, 22)),
        ("Qwen publishes Qwen3.6-2603 on Hugging Face", "https://huggingface.co/Qwen/Qwen3.6-2603", date(2026, 3, 1))]
    assert entries[0]["summary"] == "Text model weights published on Hugging Face in 3 versions."


def test_open_source_projects_major_and_minor_releases_are_releases():
    import json
    r = lambda tag, body="", pre=False: {"tag_name": tag, "prerelease": pre, "draft": False, "body": body,
                                         "published_at": "2026-10-05T10:00:00Z", "html_url": f"https://github.com/v/v/releases/tag/{tag}"}
    releases = [r("v0.31.0", "## Highlights\n\nThis release features 717 commits from 307 contributors (96 new)!"),
                r("v0.31.1"), r("v0.32.0rc1"), r("v0.32.0", pre=True), r("b11552"),
                r("jax-v0.11.0", "* Added a doc on defining custom derivative rules with the experimental\n  `custom_vjp` API.\n"),
                r("v2.0", "![logo](x.png)\n[Full Changelog](https://x)\nShort.\n- Ollama now runs models on MLX on Apple Silicon by default"),
                r("v3.0", "A few defaults changed in this release, so skim these first:\n\n☎️ Realtime voice calls, in any chat, with any model.")]
    entries = feeds.parse_github_releases(json.dumps(releases).encode(), lab="vLLM")
    assert [(e["title"], e["summary"]) for e in entries] == [
        ("vLLM releases version 0.31", "This release features 717 commits from 307 contributors (96 new)!"),
        ("vLLM releases version 0.11", "Added a doc on defining custom derivative rules with the experimental custom_vjp API."),
        ("vLLM releases version 2.0", "Ollama now runs models on MLX on Apple Silicon by default"),
        ("vLLM releases version 3.0", "Realtime voice calls, in any chat, with any model.")]


def test_papers_on_ai_footprint_are_told_from_ai_for_energy():
    from aipulse.classify import ai_footprint_paper
    assert ai_footprint_paper("Measuring the Carbon Footprint of LLM Inference")
    assert ai_footprint_paper("Energy-Efficient Training of Transformers on GPUs")
    assert ai_footprint_paper("Water Consumption of AI Data Centers")
    assert ai_footprint_paper("Carbon-Aware Scheduling of Machine Learning Workloads")
    assert not ai_footprint_paper("Energy Consumption Forecasting for Buildings with Deep Learning")  # AI for energy
    assert not ai_footprint_paper("Neural Networks Forecast Solar Output")
    assert not ai_footprint_paper("Energy-Based Models for Image Generation")  # a kind of model, not its energy
