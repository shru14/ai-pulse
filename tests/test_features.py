"""Feature pages from hand-checked tables: releases, labs, safety, money, infra, research."""
from pathlib import Path

from aipulse import store

FIX = Path(__file__).parent / "fixtures"


def test_papers_that_made_the_news(monkeypatch):
    from aipulse import press
    cards = [{"id": "a", "url": "https://x/a", "title": "Study finds AI helps", "source": "S", "date": "2026-09-02",
              "category": "news", "also": [{"url": "https://x/a2", "title": "AI helps, paper says", "source": "T",
                                            "date": "2026-09-03"}]},
             {"id": "b", "url": "https://x/b", "title": "Researchers find agents forget", "source": "S",
              "date": "2026-10-01", "category": "news"},
             {"id": "c", "url": "https://x/c", "title": "New study on chips", "source": "S", "date": "2026-10-02",
              "category": "news"},
             {"id": "d", "url": "https://x/d", "title": "Old study", "source": "S", "date": "2026-01-01", "category": "news"},
             {"id": "p1", "url": "https://arxiv.org/abs/1", "title": "Agents that plan", "source": "arXiv",
              "date": "2026-09-01", "category": "research"},
             {"id": "p2", "url": "https://arxiv.org/abs/2", "title": "A vision model", "source": "arXiv",
              "date": "2026-09-01", "category": "research"},
             {"id": "p3", "url": "https://arxiv.org/abs/3", "title": "Old agents", "source": "arXiv",
              "date": "2026-01-01", "category": "research"}]
    monkeypatch.setattr(press, "CHECKED", {
        "https://x/a2": dict(paper="Helping people", link="https://doi.org/10.1/x", subject="people", about="Finds help."),
        "https://x/b": dict(paper="Forgetful agents", link="https://arxiv.org/abs/9", subject="agents", about="Shows it."),
        "https://x/gone": dict(paper="G", link="https://g", subject="agents", about="-")})
    monkeypatch.setattr(press, "LEFT_OUT", {"https://x/c"})
    rows = press.papers(cards)
    assert [r["paper"] for r in rows] == ["Forgetful agents", "Helping people"]  # newest story first; missing skipped
    assert rows[1]["source"] == "T"  # found among a card's other stories
    assert press.candidates(cards) == []  # checked, left out, or before SINCE
    read_by, read = press.read_subjects(cards)
    assert read == 2 and read_by["agents"] == 1 and read_by["vision"] == 1  # only papers from SINCE
    body = press.page_body(rows, read_by, read)
    assert "2 research papers that news outlets we read reported on since 13 Jul 2026" in body
    assert body.index("Researchers find agents forget") < body.index("AI helps, paper says")  # the newest leads
    assert 'np-clip np-lead' in body and ">AI and people</div>" in body and ">Finds help.</p>" in body
    assert '<td class="pn-num"><b>1</b> of 2</td>' in body and "<b>1</b> of 2<span class=\"pn-pc\"> · 50%" in body
    assert "Not a Research subject" in body  # AI and people isn't counted on our side
    assert ">Vision, image and video</td>" not in body  # a subject the news didn't cover isn't listed
    assert "About these counts" in body


def test_ai_safety_hub(monkeypatch):
    from aipulse import safety
    # every document is complete and from a known publisher, and every model has a maker
    assert len({d["url"] for d in safety.DOCS}) == len(safety.DOCS)
    for d in safety.DOCS:
        assert d["by"] in safety.PUBLISHERS and d["kind"] in safety.KINDS and d["date"] >= safety.SINCE[:7]
        assert set(d["risks"]) <= set(safety.RISKS) and d["title"] and d["url"].startswith("https://")
        assert "  " not in d["abstract"] and " ." not in d["abstract"] and "‍" not in d["abstract"]
        [safety.maker(m) for m in d["models"]]
    assert safety.maker("GLM-5.3") == ("Z.ai", "open") and safety.maker("Claude Opus 5.5") == ("Anthropic", "closed")
    monkeypatch.setattr(safety, "DOCS", [
        dict(date="2026-09-03", by="OpenAI", kind="card", title="Model X System Card", url="https://o/x",
             original="https://o/x.pdf", models=("GPT-6 Astra",), risks=("cyber", "jailbreak"), abstract="We test X."),
        dict(date="2026-07-17", by="NIST (CAISI)", kind="eval", title="Assessment of GLM", url="https://n/glm",
             original="", models=("GLM-5.2",), risks=("cyber",), abstract=""),
        dict(date="2026-02", by="Frontier Model Forum", kind="framework", title="Brief", url="https://f/b",
             original="", models=(), risks=(), abstract="A brief.")])
    monkeypatch.setattr(safety, "LEFT_OUT", {"https://o/gone"})
    rows = safety.docs()
    assert [r["title"] for r in rows] == ["Model X System Card", "Assessment of GLM", "Brief"]  # newest first
    assert rows[1]["makers"] == ["Z.ai"] and rows[1]["weights"] == ["open"] and rows[2]["makers"] == []
    cards = [{"url": "https://o/x", "title": "Model X system card", "source": "OpenAI News", "date": "2026-09-03",
              "category": "tool"},
             {"url": "https://o/gone", "title": "A risk report", "source": "OpenAI News", "date": "2026-09-04",
              "category": "tool"},
             {"url": "https://n/new", "title": "CAISI evaluation of Model Y", "source": "The Decoder",
              "date": "2026-10-01", "category": "news"},
             {"url": "https://n/news", "title": "Model Y launches", "source": "The Decoder", "date": "2026-10-02",
              "category": "news"}]
    assert [c["url"] for c in safety.candidates(cards)] == ["https://n/new"]  # not listed, left out or off-topic
    body = safety.page_body(rows)
    assert "3 documents published in 2026" in body and "1 system card, 1 evaluation, 1 framework &amp; guidance" in body
    assert 'Showing <b>3</b> of 3 documents' in body and '<option value="cyber">Cyber attacks (2)</option>' in body
    assert '<option value="physical">' not in body  # no option for a risk no document covers
    assert 'data-kind="card" aria-pressed="false">System card <b>1</b>' in body and 'data-kind="redteam"' not in body
    assert "Z.ai, open weights" in body
    assert body.index("Model X System Card") < body.index("Assessment of GLM")
    assert "PDF ↗" in body and ">Feb 2026 · Frontier Model Forum<" in body
    assert body.count('class="sh-ab"') == 2  # a document without an abstract shows none
    assert "About these documents" in body


def test_jobs_blamed_on_ai(monkeypatch):
    from aipulse import jobs
    cards = [{"id": "a", "url": "https://x/a", "title": "A cuts 1,000 jobs", "source": "S", "date": "2026-05-02",
              "category": "news", "also": [{"url": "https://x/a2", "title": "A lays off staff", "source": "T",
                                            "date": "2026-05-03"}]},
             {"id": "b", "url": "https://x/b", "title": "B lays off 3,000", "source": "S", "date": "2025-03-01",
              "category": "news"},
             {"id": "c", "url": "https://x/c", "title": "C cuts staff as AI does the work", "source": "S",
              "date": "2026-06-01", "category": "news"},
             {"id": "d", "url": "https://x/d", "title": "D layoffs, report says", "source": "S", "date": "2026-07-01",
              "category": "news"},
             {"id": "e", "url": "https://x/e", "title": "E opens office", "source": "S", "date": "2026-07-01",
              "category": "news"}]
    monkeypatch.setattr(jobs, "CHECKED", {
        "https://x/a2": dict(company="A", month="2026-05", jobs="about 1,000", n=1000, reason="work", said="AI does it"),
        "https://x/b": dict(company="B", month="2025-03", jobs="about 3,000", n=3000, reason="never", said="Costs"),
        "https://x/c": dict(company="C", month="2026-06", jobs="several hundred", n=None, reason="pay", said="AI money"),
        "https://x/gone": dict(company="G", month="2026-01", jobs="1", n=1, reason="work", said="-")})
    monkeypatch.setattr(jobs, "LEFT_OUT", {"https://x/d"})
    rows = jobs.cuts(cards)
    assert [r["company"] for r in rows] == ["C", "A", "B"]  # newest first; a story we don't have is skipped
    assert rows[1]["source"] == "T" and rows[1]["when"] == "May 2026"  # found among a card's other stories
    assert jobs.candidates(cards) == []  # checked, left out, or not about cuts
    body = jobs.page_body(rows)
    assert "3 big job cuts since 2025" in body and "about 4,000 in all" in body and "C gave none" in body
    assert "Said AI now does the work: 1 cut" in body and "Mentioned AI" not in body  # only the reasons it has
    assert '<td>2026</td><td class="n">2</td><td class="n">about 1,000</td>' in body  # by year
    assert "B&#x27;s 3,000 jobs are about 3 in 4 of the jobs we could count" in body
    assert jobs._share(14000, 46985) == "about 3 in 10" and jobs._share(34335, 46985) == "nearly 3 in 4"


def test_models_being_retired_reads_each_labs_page_and_builds(tmp_path, monkeypatch):
    from datetime import date
    from aipulse import retired
    openai = ('<h3>2026-10-14: GPT-4 series</h3><table><tr><th>Shutdown date</th><th>Model / system</th>'
              '<th>Recommended replacement</th></tr><tr><td>January 14, 2027</td><td>gpt-4o-2024-08-06</td>'
              '<td>gpt-6-luna</td></tr><tr><td>Oct 23, 2026</td><td>o1-2024-12-17 | o1</td><td>gpt-5.6-sol</td></tr>'
              '</table><h3>2026-06-03: Evals platform</h3><table><tr><th>Date</th><th>Update</th></tr>'
              '<tr><td>June 3, 2026</td><td>Deprecation announced.</td></tr><tr><td>Nov 30, 2026</td>'
              '<td>The Evals dashboard and API are scheduled to shut down.</td></tr></table>'
              '<h3>Update to fine-tuning</h3><table><tr><th>Date</th><th>Update</th></tr>'
              '<tr><td>Jan 6, 2027</td><td>No new jobs.</td></tr></table>')
    google = ('<h2>Gemini 3</h2><table><tr><th>Model</th><th>Release date</th><th>Shutdown date</th>'
              '<th>Recommended replacement</th></tr><tr><td>gemini-3.8-flash</td><td>September 2, 2026</td>'
              '<td>No shutdown date announced</td><td></td></tr><tr><td>Preview models</td></tr>'
              '<tr><td>gemini-3.1-flash-tts-preview</td><td>February 26, 2026</td><td>November 17, 2026</td>'
              '<td>gemini-3.8-flash-tts</td></tr></table>')
    mistral = ('<table><tr><td>OCR 4.0 ↗</td><td>4.0</td><td>mistral-ocr-4-0</td><td>9/29/2026 9/30/2026</td>'
               '<td>OCR 4.1</td></tr><tr><td>Mistral Next ↗</td><td></td><td></td><td></td><td>Mistral Large 3</td></tr></table>')
    anthropic = ('<h2>Model status</h2><table><tr><th>API model name</th><th>Current state</th></tr>'
                 '<tr><td>claude-opus-5-5</td><td>Active</td></tr></table>'
                 '<h3>2026-09-30: Claude Sonnet 4.5 model</h3><table><tr><th>Retirement date</th>'
                 '<th>Deprecated model</th><th>Recommended replacement</th></tr><tr><td>November 30, 2026</td>'
                 '<td>claude-sonnet-4-5-20250929</td><td>claude-sonnet-5-5</td></tr></table>')
    got = {lab: retired.parse(lab, html) for lab, html in
           (("OpenAI", openai), ("Google", google), ("Mistral", mistral), ("Anthropic", anthropic))}
    assert [(r["model"], r["shuts"], r["replace"], r["told"]) for r in got["OpenAI"]] == [
        ("gpt-4o-2024-08-06", "2027-01-14", "gpt-6-luna", "2026-10-14"), ("o1-2024-12-17", "2026-10-23", "gpt-5.6-sol",
        "2026-10-14"), ("Evals platform", "2026-11-30", "", "2026-06-03")]  # undated notices and non-shutdowns left out
    assert [(r["model"], r["shuts"], r["told"]) for r in got["Google"]] == [("gemini-3.1-flash-tts-preview", "2026-11-17", "")]
    assert [(r["model"], r["shuts"], r["told"], r["replace"]) for r in got["Mistral"]] == [
        ("mistral-ocr-4-0", "2026-09-30", "2026-09-29", "OCR 4.1")]
    assert [r["model"] for r in got["Anthropic"]] == ["claude-sonnet-4-5-20250929"]  # active models have no date
    conn = store.connect(tmp_path / "t.db")
    pages_ = {retired.LABS[lab][0]: html.encode() for lab, html in
              (("OpenAI", openai), ("Google", google), ("Mistral", mistral), ("Anthropic", anthropic))}
    monkeypatch.setattr(retired.feeds, "allowed", lambda url: True)
    assert retired.refresh(conn, fetcher=pages_.__getitem__) == "OpenAI 3, Anthropic 1, Google 1, Mistral 1"
    retired.refresh(conn, fetcher=lambda url: b"<p>down</p>")  # a page that can't be read keeps the rows last read
    assert len(retired.load(conn)["OpenAI"]["rows"]) == 3
    assert retired.build(conn, [], tmp_path, date(2026, 10, 16)) == ["models-being-retired/"]
    page = (tmp_path / "models-being-retired" / "index.html").read_text(encoding="utf-8")
    ahead, gone = page.split("Already shut down")
    assert ahead.index("23 Oct 2026") < ahead.index("17 Nov 2026") < ahead.index("14 Jan 2027")  # soonest first
    assert ahead.count('class="rm-soon"') == 1 and "30 Sep 2026" in gone  # 23 Oct is within 30 days
    assert "<code>gpt-4o-2024-08-06</code>" in page and "<td>Evals platform</td>" in page
    assert "<b>1</b><span>models shut down in the next 30 days</span>" in page


def test_lab_timelines_grid_by_month_collapses_one_release_labs_and_drafts_changes(tmp_path, monkeypatch):
    from datetime import date
    from aipulse import lab_timelines as lt, retired
    conn = store.connect(tmp_path / "t.db")
    saved = {"OpenAI": {"rows": [{"lab": "OpenAI", "model": "o1-2024-12-17", "shuts": "2026-10-23"},
                                 {"lab": "OpenAI", "model": "gpt-4o", "shuts": "2026-07-23"},
                                 {"lab": "OpenAI", "model": "gpt-4", "shuts": "2027-05-01"}]}}  # past the 3 months
    conn.execute("INSERT INTO meta VALUES (?, ?)", (retired.KEY, __import__("json").dumps(saved)))
    assert lt.build(conn, [], tmp_path, date(2026, 10, 17)) == ["lab-timelines/"]
    page = (tmp_path / "lab-timelines" / "index.html").read_text(encoding="utf-8")
    assert "<th>Jul</th><th>Aug</th><th>Sep</th><th>Oct</th><th class=\"lt-fut\">Next 3 months</th>" in page
    assert "1 shut down (scheduled)" in page and "gpt-4<" not in page and "o1-2024-12-17" in page
    assert "↓ GPT-5.6 Luna 80% cheaper" in page and "+ Grok 4.5 now in the EU" in page
    grid, few = page.split('<tbody class="lt-few" hidden>')
    assert 'data-lab="Cisco"' in few and 'data-lab="Cisco"' not in grid.split("</tbody>")[0]  # one release: collapsed
    assert 'data-lab="Google"' in grid and "Google released the most models" in page
    story = {"url": "https://x.example/p", "title": "Mistral cuts API prices for Large 4", "date": "2026-10-20T08:00",
             "source": "Outlet", "category": "news"}
    other = story | {"url": "https://x.example/o", "title": "Mistral hires a new CFO"}
    old = story | {"url": "https://x.example/old", "date": "2026-10-10T08:00"}
    assert lt.candidates([story, other, old]) == [story]
    base = open(lt.__file__, encoding="utf-8").read()
    monkeypatch.setattr(lt, "PRICES", lt.PRICES + [("2026-10-20", "Mistral", "Large 4", "cut", "30% cheaper",
                                                    "Now $1.40 / $4.20 per 1M tokens in / out", story["url"])])
    assert lt.candidates([story]) == []
    subject, text, html = lt.note(base, "timelines/2026-10-21")
    assert subject == "AI Pulse, Lab timelines: 1 new change to approve" and "Price cut: Now $1.40" in html


def test_who_owns_whom_grid_shows_only_deals_whose_story_we_have(tmp_path):
    from datetime import date
    from aipulse import owners
    cards = [{"url": u, "source": "Outlet", "title": f"Story {n}", "date": "2026-01-01"}
             for n, (*_, u) in enumerate(owners.DEALS) if "anthropic" in u.lower() or "openai" in u.lower()]
    rows = owners.deals(cards)
    assert rows and {r["lab"] for r in rows} <= {"OpenAI", "Anthropic"}
    assert owners.build(None, cards, tmp_path, date(2026, 10, 16)) == ["who-owns-a-piece-of-whom/"]
    page = (tmp_path / "who-owns-a-piece-of-whom" / "index.html").read_text(encoding="utf-8")
    assert "<th scope=\"col\">OpenAI</th>" in page and "Thinking Machines" not in page  # no empty columns
    assert 'class="ow-deal ow-up"' in page and "Up to $40B" in page  # "up to" money is dashed
    assert "have money in both OpenAI and Anthropic" in page
    assert owners.build(None, [], tmp_path / "none", date(2026, 10, 16)) == []


def test_who_owns_whom_candidates_and_the_approval_note():
    from aipulse import owners
    new = {"url": "https://x.example/a", "title": "Nvidia invests $2B in Mistral", "date": "2026-10-20T08:00",
           "source": "Outlet", "category": "news"}
    seen = {"url": owners.DEALS[0][-1], "title": "Microsoft takes 27% stake in OpenAI", "date": "2026-10-21",
            "source": "Outlet", "category": "news"}
    old = new | {"url": "https://x.example/b", "date": "2026-10-16T09:00"}  # read for the list already
    other = new | {"url": "https://x.example/c", "title": "Nvidia invests in a chip startup"}  # no lab named
    assert owners.candidates([new, seen, old, other]) == [new]
    base = open(owners.__file__, encoding="utf-8").read().replace(owners.DEALS[-1][-1], "https://gone.example/")
    subject, text, html = owners.note(base, "owners/2026-10-17")
    assert "1 new deal to approve" in subject and owners.DEALS[-1][-1] in text
    assert owners.note(open(owners.__file__, encoding="utf-8").read(), "owners/2026-10-17") is None


def test_new_tests_for_ai_rows_scores_and_candidates(tmp_path):
    from datetime import date, timedelta
    from aipulse import new_tests as nt
    url = "https://arxiv.org/abs/2610.18092"  # LifeSearch: 63.4%, GPT-5.6 Sol
    after = (date.fromisoformat(nt.CHECKED_TO) + timedelta(days=1)).isoformat()  # a day the routine hasn't checked yet
    cards = [{"url": url, "title": "LifeSearch: Benchmarking Deep Research Agents", "date": "2026-10-13T00:00",
              "category": "research"},
             {"url": "https://arxiv.org/abs/2610.99999", "title": "FooBench: a new benchmark", "date": after + "T00:00",
              "category": "research"},
             {"url": "https://arxiv.org/abs/2610.13644", "title": "SelectArena", "date": "2026-10-17T00:00",
              "category": "research"}]  # left out already
    assert nt.build(None, [], tmp_path, date(2026, 10, 17)) == []  # no checked paper among the cards: no page
    assert nt.build(None, cards, tmp_path, date(2026, 10, 17)) == ["new-tests-for-ai/"]
    page = (tmp_path / "new-tests-for-ai" / "index.html").read_text(encoding="utf-8")
    assert "<h1>New tests for AI</h1>" in page and 'style="left:63.40%"' in page and "GPT-5.6 Sol" in page
    assert "0 of 1" in page and "<span class=\"nt-n1\">1</span><span>new tests for AI" in page
    assert [c["url"] for c in nt.candidates(cards)] == ["https://arxiv.org/abs/2610.99999"]
    assert all(s in nt.SUBJECTS for _, s, *_ in nt.TESTS.values())
    assert nt.note(open(nt.__file__, encoding="utf-8").read(), "tests/2026-10-18") is None
    base = open(nt.__file__, encoding="utf-8").read().replace(url, "https://gone.example/")
    subject, text, html = nt.note(base, "tests/2026-10-18")
    assert "1 new test to approve" in subject and url in text and "LifeSearch" in html


def test_code_links_sorted_by_kind_read_weekly_and_shown_on_both_pages(tmp_path):
    import json
    from datetime import date, datetime, timezone
    from aipulse import code_links as cl, new_tests as nt, store
    assert cl.sort(["https://arxiv.org/abs/1", "https://github.com/a/b.", "https://huggingface.co/datasets/a/b",
                    "https://huggingface.co/a", "https://huggingface.co/spaces/a/b", "https://a.github.io/x/",
                    "https://github.com/c/d"]) == {
        "Code": "https://github.com/a/b", "Data": "https://huggingface.co/datasets/a/b",
        "Try it": "https://huggingface.co/spaces/a/b", "Site": "https://a.github.io/x/"}
    assert cl.kind("https://github.com/org") is None and cl.arxiv_id("https://arxiv.org/abs/2608.12593v1") == "2608.12593"
    feed = ('<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom"><entry>'
            '<id>http://arxiv.org/abs/2610.18092v1</id><summary>Code at https://github.com/x/life.</summary>'
            '<arxiv:comment>Site: https://life.example/</arxiv:comment></entry></feed>').encode()
    asked = []
    def fetch(url):
        asked.append(url)
        if url.startswith(cl.HF_API):
            return json.dumps({"githubRepo": "https://github.com/y/other", "projectPage": None}).encode()
        return feed
    conn = store.connect(str(tmp_path / "t.db"))
    url = "https://arxiv.org/abs/2610.18092"
    now = datetime(2026, 10, 20, tzinfo=timezone.utc)
    assert "1 papers read, 1 with links" in cl.refresh(conn, [url, "https://doi.org/x"], fetch, now)
    assert cl.of(cl.load(conn), url) == {"Code": "https://github.com/x/life", "Site": "https://life.example/"}
    assert cl.refresh(conn, [url], fetch, now) == "all read this week" and len(asked) == 2
    cards = [{"url": url, "title": "LifeSearch", "date": "2026-10-13T00:00", "category": "research"}]
    nt.build(conn, cards, tmp_path, date(2026, 10, 20))
    page = (tmp_path / "new-tests-for-ai" / "index.html").read_text(encoding="utf-8")
    assert '<td class="cl"><a href="https://github.com/x/life" rel="noopener">Code</a> · <a' in page
    weave = "https://arxiv.org/abs/2606.09426"
    rows = nt.tests([{"url": weave, "title": "WeaveBench", "date": "2026-06-08T00:00", "category": "research"}])
    assert "Beaten 3 Aug 2026" in nt._table(rows, {})
    base = open(nt.__file__, encoding="utf-8").read().replace("https://arxiv.org/abs/2608.01964", "https://gone.example/")
    subject, text, html = nt.note(base, "tests/2026-10-21")
    assert "WeaveBench" in html and "Beaten" in html and "2608.01964" in text


def test_compute_page_measures_against_gpt4_and_counts_missing_estimates(tmp_path, monkeypatch):
    from datetime import date
    from aipulse import compute, feeds
    monkeypatch.setattr(feeds, "allowed", lambda url: True)
    conn = store.connect(tmp_path / "t.db")
    text = ("Model,Organization,Publication date,Training compute (FLOP),Confidence,Link,Model accessibility\n"
            "GPT-4 (Mar 2023),OpenAI,2023-03-15,2.1e+25,Likely,https://openai.com/gpt-4,API access\n"
            "GPT-3 175B (davinci),OpenAI,2020-05-28,3.14e+23,Confident,,API access\n"
            "Big One,\"Lab A,Lab B\",2026-09-03,9.4e+26,Likely,https://a.example,Open weights (unrestricted)\n"
            "Quiet One,Lab C,2026-09-10,,Confident,,API access\n")
    assert compute.build(conn, [], tmp_path, date(2026, 10, 17)) == []  # not read yet: no page
    assert compute.refresh(conn, fetcher=lambda url: text.encode()) == "3 of 4 models with an estimate"
    assert compute.build(conn, [], tmp_path, date(2026, 10, 17)) == ["compute-behind-notable-models/"]
    page = (tmp_path / "compute-behind-notable-models" / "index.html").read_text(encoding="utf-8")
    assert "<span class=\"nt-n1\">45×</span>" in page and "Lab A, Lab B" in page and "9.4 × 10²⁶" in page and "1/67" in page
    assert "1 of 2" in page
    assert "have none, so they aren&#x27;t shown; 1 of them doesn&#x27;t share their weights" in page
    assert compute.times(2.1e25, 2.1e25) == "1×" and compute.since(date(2026, 1, 5)) == "2025-10-01"


def test_who_publishes_counts_company_papers_finds_the_rising_subject_and_top_researchers(tmp_path):
    from datetime import date
    from aipulse import publishers as wp
    def paper(i, d, title, *tags):
        return {"id": f"p{i}", "category": "research", "date": d, "title": title, "tags": [*tags, "Research"]}
    cards = [paper(1, "2025-12-30", "Old agents paper", "Tencent")]  # last year: not counted
    for m in range(1, 10):  # agents papers grow from 1 in 4 to 3 in 4
        for k in range(4):
            agents = k < (1 if m <= 3 else 3 if m >= 7 else 2)
            cards.append(paper(m * 10 + k, f"2026-{m:02d}-1{k}", "An agents harness" if agents else "Image segmentation",
                               "Tencent", "NVIDIA", "Nvidia", "Dacheng Tao"))
    cards.append(paper(999, "2026-10-02", "A speech model", "Google"))  # 1 paper: under MIN, not listed
    cards.append({"id": "n", "category": "news", "date": "2026-05-01", "title": "Tencent agents", "tags": ["Tencent"]})
    day = date(2026, 10, 20)
    rows = wp.papers(cards, day)
    assert [(r["name"], r["home"], r["papers"]) for r in wp.companies(rows)] == [("Nvidia", "United States", 36),
                                                                                ("Tencent", "China", 36)]
    subject, months, shares = wp.rising(rows, day)
    assert subject == "Agents" and shares[0] == 25 and shares[8] == 75 and months[-1] == "2026-10"
    assert wp.people(rows) == [{"name": "Dacheng Tao", "papers": 36, "subjects": ["Agents", "Vision, image and video"]}]  # 18 each
    assert wp.build(None, cards, tmp_path, day) == ["who-publishes-ai-research/"]
    page = (tmp_path / "who-publishes-ai-research" / "index.html").read_text(encoding="utf-8")
    assert "<h1>Who publishes AI research on Hugging Face</h1>" in page and "Rising: Agents" in page
    assert "25% → 75%" in page and "Oct so far" in page and "36 vs 36" in page
    assert wp.build(None, [], tmp_path, day) == []


def test_buyouts_shopping_lists_table_and_links(tmp_path):
    from datetime import date
    from aipulse import buyouts as bo
    assert bo.build(None, [], tmp_path, date(2026, 10, 20)) == ["ai-buyouts/"]
    page = (tmp_path / "ai-buyouts" / "index.html").read_text(encoding="utf-8")
    assert "<h1>AI buyouts</h1>" in page and page.count('<td class="pc-d"') == len(bo.DEALS)
    # a row per buyer with two or more deals, a dot per deal there, each linking to its row in the table
    count = {}
    for r in bo.DEALS:
        count[r[1]] = count.get(r[1], 0) + 1
    assert page.count('class="by-r"') == sum(n > 1 for n in count.values())
    assert page.count('class="by-dot') == sum(n for n in count.values() if n > 1)
    assert all(f'id="by-{n}"' in page for n in range(len(bo.DEALS)))
    assert page.count('href="ai-buyouts/#by-') == page.count('class="by-dot')
    assert "<b>OpenAI</b> made the most deals" in page and "<b>Cursor</b> for <b>$60B in stock</b>" in page
    assert ">Blocked<" in page and "China ordered the deal undone" in page
    assert all(r[6] in bo.STATUSES and (r[5] is None) == (r[4] in ("Not disclosed", "Low nine figures")) for r in bo.DEALS)
    assert not set(r[7] for r in bo.DEALS) & set(bo.LEFT_OUT)
    # newest first
    assert page.index("<b>Elementary Data</b>") < page.index("<b>Convogo (team)</b>")


def test_buyouts_candidates_and_the_approval_note():
    from aipulse import buyouts as bo
    new = {"url": "https://x.example/a", "title": "Okta acquires AI agent security startup Foo",
           "date": "2026-10-21T08:00", "source": "Outlet", "category": "news"}
    seen = new | {"url": bo.DEALS[-1][7]}
    old = new | {"url": "https://x.example/b", "date": "2026-10-19T09:00"}  # read for the list already
    chips = new | {"url": "https://x.example/c", "title": "Lab to buy $10B of Nvidia chips"}  # not buying a company
    paper = new | {"url": "https://x.example/d", "category": "research"}
    assert bo.candidates([new, seen, old, chips, paper]) == [new]
    base = open(bo.__file__, encoding="utf-8").read().replace(bo.DEALS[-1][7], "https://gone.example/")
    subject, text, html = bo.note(base, "buyouts/2026-10-21")
    assert "1 new deal to approve" in subject and bo.DEALS[-1][7] in text
    assert bo.note(open(bo.__file__, encoding="utf-8").read(), "buyouts/2026-10-21") is None


def test_release_safety_reports(monkeypatch):
    from datetime import date
    from aipulse import release_cards as rc
    assert rc.safety("2026-09-01", "Claude Fable 5.1")["when"] == "day"
    late = rc.safety("2026-10-05", "Beam")
    assert (late["when"], late["late"]) == ("later", 11)
    none = rc.safety("2026-07-08", "Grok 4.5")  # long past the recheck window: shown as last looked for on the first check
    assert (none["when"], none["checked"]) == ("none", rc.FIRST_CHECKED)
    monkeypatch.setattr(rc, "SAFETY_CHECKED", "2026-11-30")
    assert rc.safety("2026-10-15", "Step 5 Preview")["checked"] == "2026-11-14"  # looked for until 30 days after launch
    assert "Step 5 Preview" in rc.safety_due(date(2026, 10, 20)) and "Grok 4.5" not in rc.safety_due(date(2026, 10, 20))
    assert "Safety report on day one" in rc.body(rc.rows())


def test_every_release_has_a_kind():
    from aipulse import release_cards as rc
    assert {r[2] for r in rc.RELEASES} == set(rc.KIND) and set(rc.KIND.values()) <= set(rc.KINDS)


def test_lab_timelines_pulled(monkeypatch):
    from datetime import date
    from aipulse import lab_timelines as lt
    today = date(2026, 10, 20)
    assert "pulled" not in lt.body(lt.events({}, today), today)  # no mark, legend or note until a model is pulled
    monkeypatch.setattr(lt, "PULLED", [("2026-08-05", "OpenAI", "GPT-Live", "a test reason", "https://x.example/p")])
    page = lt.body(lt.events({}, today), today)
    assert "✕ GPT-Live pulled" in page and "✕ pulled</span>" in page and "✕ Pulled" in page
    base = open(lt.__file__, encoding="utf-8").read()
    subject, text, html = lt.note(base, "timelines/2026-10-21")
    assert "Pulled: a test reason" in text
    story = {"date": "2026-10-19", "title": "Lab pulls its new model after backlash", "url": "https://x.example/q",
             "source": "Verge", "category": "news"}
    assert lt.candidates([story]) == [story]


def test_model_economy_prices_against_the_model_before_and_shutdown_warning(tmp_path, monkeypatch):
    from datetime import date
    from aipulse import model_economy as me, retired
    conn = store.connect(tmp_path / "t.db")
    saved = {"OpenAI": {"rows": [
        {"lab": "OpenAI", "model": "gpt-a", "shuts": "2026-12-01", "told": "2026-06-01", "kind": "model", "replace": "gpt-b"},
        {"lab": "OpenAI", "model": "Evals platform", "shuts": "2026-11-30", "told": "2026-06-03", "kind": "product", "replace": ""},
        {"lab": "OpenAI", "model": "gpt-old", "shuts": "2025-12-01", "told": "2025-06-01", "kind": "model", "replace": ""}]},
        "Mistral": {"rows": [{"lab": "Mistral", "model": "m-ocr", "shuts": "2026-09-30", "told": "2026-09-29",
                              "kind": "model", "replace": "OCR 4.1"}]},
        "Google": {"rows": [{"lab": "Google", "model": "gemini-x", "shuts": "2026-11-17", "told": "", "kind": "model",
                             "replace": "gemini-y"}]}}
    conn.execute("INSERT INTO meta VALUES (?, ?)", (retired.KEY, __import__("json").dumps(saved)))
    assert me.build(conn, [], tmp_path, date(2026, 10, 20)) == ["model-economy/"]
    page = (tmp_path / "model-economy" / "index.html").read_text(encoding="utf-8")
    assert '<h1>The model economy</h1><p class="fh-sub">The cost of keeping up</p>' in page
    ps = {p["model"]: p for p in me.prices()}
    assert ps["Claude Opus 5.5"]["say"] == "20% cheaper" and ps["Claude Opus 5.5"]["was_price"] == "$5 / $25"
    assert ps["Gemini 3.7 Flash"]["way"] == "down" and ps["Grok 4.7"]["say"] == "Same"
    assert ps["DeepSeek V4.1 Flash"]["way"] == "up" and ps["Gemini 3.7 Flash"]["price_note"] == "Introductory, until 31 Dec"
    assert "Of 9 new models, 6 kept the price of the model before, 2 cost less and 1 cost more." in page
    assert ps["DeepSeek V4.1 Flash"]["say"] == "Pricier: in +7%, out +114%" and "$5 in · $25 out" in page
    assert "Evals platform" not in page and "gpt-old" not in page  # a whole product; before 2026
    assert "OpenAI gives the most warning: a median of 183 days. The shortest was Mistral&#x27;s: 1 day." in page
    assert "Its page gives no day it told developers" in page and "gemini-x" not in page
    assert me._per_token("$0.005 / $0.018|a minute of audio") is None and me._per_token("$4 / $20") == (4, 20)
    assert not any(c["title"].startswith(("Claude Opus 5.5", "Gemini 3.8 Live")) for c in me.candidates())
