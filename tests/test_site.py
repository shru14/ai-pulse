"""Building the site: pages, search, glossary, feeds, logos, settings and the paid pages' seal."""
import re
from datetime import date
from pathlib import Path

from aipulse import COMPASS, store
from aipulse.collect import collect

FIX = Path(__file__).parent / "fixtures"
from helpers import _fake_embedder, _seed, _story


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


def test_static_build_holds_every_card(tmp_path, monkeypatch):
    import json
    from aipulse import consultations
    from aipulse.static import build
    monkeypatch.setattr(consultations, "ADDED", [])  # the page is built once a list is read or a row checked by hand
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
    assert {p.name for p in (tmp_path / "site").iterdir()} == {"index.html", "data.json", "glossary.json", "tags.json", ".nojekyll", "feeds", "daily", "fonts", "meme.json", "photos", "dossier.html", "ask.html", "tracker.csv", "robots.txt", "sitemap.xml", "og-pulse.png", "favicon.ico", "apple-touch-icon.png", "tracker", "flags", "glossary", "site.css", "privacy.html", "terms", "about", "discussing", "saved", "review", "social.json", "today", "today.json", "topics", "monthly",
        "rule-echoes", "promises", "harm-to-rule", "jobs-blamed-on-ai", "papers-in-the-news", "ai-in-court", "ai-safety-hub", "data-centre-builds", "who-powers-ai", "pushback-and-permits", "release-cards", "ai-pacts-and-orders", "ai-fines-and-bans", "chip-export-rules", "ai-buyouts", "lab-timelines", "model-economy", "all", "releases", "industry", "research", "regulation", "policy", "infra"} | ({"planner", "og-pro.png", "pro.css"} if COMPASS else set()) | ({"memes"} if meme["image"] else set())  # the picture only when last week has one
    # the fonts are the site's own: nothing from Google Fonts (it would send every reader's address to Google)
    assert "fonts.googleapis" not in page and "fonts.gstatic" not in page
    assert {f for f in re.findall(r'url\("fonts/([^"]+)"\)', page)} <= {p.name for p in (tmp_path / "site" / "fonts").iterdir()}
    assert sorted(p.name for p in (tmp_path / "site" / "feeds").iterdir()) == ["all.opml", "infra.xml", "news.xml", "policy.xml", "regulation.xml", "releases.xml", "research.xml"]
    assert (tmp_path / "site" / "feeds" / "all.opml").read_text(encoding="utf-8").count("<outline ") == 6
    assert data["total"] == total  # the front page's all-time count, without the archive files
    # each page holds what it draws first (static.boot), so it needn't wait for data.json
    boot = lambda p: json.loads(re.search(r'<script type="application/json" id="boot">(.*?)</script>', p).group(1))
    front, news = boot(page), boot((tmp_path / "site" / "industry" / "index.html").read_text(encoding="utf-8"))
    assert front["total"] == total and not front["lite"] and "first" not in front
    assert news["lite"] and news["first"]["category"] == "news" and news["first"]["days"] == 30
    assert all("s" not in c for c in front["cards"] + news["first"]["items"])  # no search words: data.json has them
    assert page.index('id="boot"') < page.index("const BOOT")  # read by the page's script, so before it
    assert (tmp_path / "site" / "tracker.csv").read_text(encoding="utf-8").startswith("date,countries,type,title,source,link")
    # what search engines see: a description and a preview image; the sitemap lists each day's page; AI-training
    # bots are kept out, and readers' own pages are never indexed
    assert '<meta name="description"' in page and 'og:image" content="https://projectaipulse.com/og-pulse.png"' in page
    robots = (tmp_path / "site" / "robots.txt").read_text(encoding="utf-8")
    assert "User-agent: GPTBot\nDisallow: /" in robots and "Sitemap: https://projectaipulse.com/sitemap.xml" in robots
    assert "User-agent: *\nDisallow: /dossier/" in robots
    for private in ("dossier.html", "ask.html"):
        assert '<meta name="robots" content="noindex">' in (tmp_path / "site" / private).read_text(encoding="utf-8")
    sitemap = (tmp_path / "site" / "sitemap.xml").read_text(encoding="utf-8")
    tracker_pages = list((tmp_path / "site" / "tracker").glob("**/index.html"))
    tracker_pages += list((tmp_path / "site" / "glossary").glob("**/index.html"))  # and the glossary's
    from aipulse.kind_pages import MOVED
    for stream in ("industry", "releases", "policy", "research", "infra"):  # and each stream's pages within it
        tracker_pages += [q for q in (tmp_path / "site" / stream).glob("*/index.html")  # not the moved addresses
                          if f"{stream}/{q.parent.name}/" not in MOVED]
    tracker_pages += list((tmp_path / "site" / "topics").glob("**/index.html"))  # and the topics, a page each
    tracker_pages += list((tmp_path / "site" / "monthly").glob("**/index.html"))  # and the monthly issues
    tracker_pages += [tmp_path / "site" / "rule-echoes" / "index.html", tmp_path / "site" / "promises" / "index.html",
                     tmp_path / "site" / "harm-to-rule" / "index.html", tmp_path / "site" / "jobs-blamed-on-ai" / "index.html",
                     tmp_path / "site" / "papers-in-the-news" / "index.html", tmp_path / "site" / "ai-in-court" / "index.html",
                     tmp_path / "site" / "ai-safety-hub" / "index.html"]
    tracker_pages += [tmp_path / "site" / p / "index.html" for p in ("data-centre-builds", "who-powers-ai", "pushback-and-permits")]
    assert "<url><loc>https://projectaipulse.com/industry/tutorials/</loc></url>" in sitemap  # no date of its own
    tutorials = (tmp_path / "site" / "industry" / "tutorials" / "index.html").read_text(encoding="utf-8")
    assert "<h1>AI tutorials</h1>" in tutorials and '"kind": "tutorial"' in tutorials and "Updated" not in tutorials.split('<main')[1]  # the masthead's own update line aside
    # the front page's stream strips link to exactly the pages built
    from aipulse import kind_pages
    front = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    for p in kind_pages.paths():
        assert f'href="{p}"' in front and (tmp_path / "site" / p / "index.html").exists() and f"<loc>https://projectaipulse.com/{p}</loc>" in sitemap
    for old, new in kind_pages.MOVED.items():  # an old address sends readers to the new one
        assert f'url=/{new}"' in (tmp_path / "site" / old / "index.html").read_text(encoding="utf-8")
        assert f"/{old}<" not in sitemap
    assert sitemap.count("<url>") == 1 + 7 + 11 + len(tracker_pages) + len([p for p in (tmp_path / "site" / "daily").iterdir() if p.name not in ("latest.html", "sample.html") and p.suffix == ".html"]) + (daily_sample := (tmp_path / "site" / "daily" / "sample.html").exists())  # the front page, 7 stream pages, about/, discussing/, today/, release-cards/, ai-pacts-and-orders/, ai-fines-and-bans/, chip-export-rules/, ai-buyouts/, lab-timelines/, model-economy/, terms/ (the adoption planner's pages are Pro: none in the sitemap)
    # each stream has its own address: the same page, with its own title, description, canonical link and heading
    policy = (tmp_path / "site" / "policy" / "index.html").read_text(encoding="utf-8")
    assert "<title>AI policy news: governments, courts and politics · AI Pulse</title>" in policy
    assert policy.count('content="What governments, courts and politicians do about AI, worldwide. Updated every 6 hours') == 2
    assert 'rel="canonical" href="https://projectaipulse.com/policy/"' in policy and 'og:url" content="https://projectaipulse.com/policy/"' in policy
    assert '<h2 id="sec-title">Policy</h2>' in policy and '<base href="/">' in policy and 'data-static="1"' in policy
    # what Google reads without running the page's script (6 Nov 2026): each page's own part shown, its newest
    # headlines as links in the HTML, and canonical addresses with one slash
    from aipulse.static import stream_page
    fresh = {"title": "Lab ships a model & more", "url": "https://example.com/a?b=1&c=2", "source": "Example",
             "date": "2026-11-05", "category": "news"}
    news = stream_page(page, "news", [fresh, {**fresh, "category": "tool", "url": "https://example.com/other"}])
    assert '<section class="section" id="section">' in news and '<main id="feed" data-ssr="1">' in news
    assert 'href="https://example.com/a?b=1&amp;c=2" rel="noopener">Lab ships a model &amp; more</a>' in news
    assert "example.com/other" not in news and "Thu, 5 Nov 2026" in news
    assert '<section class="home" id="front">' in front and '<section class="section" id="section" hidden>' in front
    for p in ("about", "discussing", "today"):
        own = (tmp_path / "site" / p / "index.html").read_text(encoding="utf-8")
        assert f'rel="canonical" href="https://projectaipulse.com/{p}/"' in own and f'id="{p}-page">' in own
    for f in (tmp_path / "site").glob("**/*.html"):
        assert "projectaipulse.com//" not in f.read_text(encoding="utf-8"), f
    assert "<loc>https://projectaipulse.com/infra/</loc>" in sitemap
    from aipulse.static import STREAM_PAGES
    for cat, (path, _, title, _) in STREAM_PAGES.items():  # the page sets the same titles
        assert f'{cat}: "{title}"' in page
        assert (f'href="/{path}/" data-go="{cat}"' in page) == (cat != "all")  # All stories: no menu link, a tag or search lands there
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
    assert '<h1>Mixture of Experts</h1>' in page and '<a href="/glossary/parameters/">parameters</a>' in page
    assert "<h2>Related terms</h2>" in page and page.count('<li><div><a href="/glossary/') == glossary_pages.RELATED
    assert '<span class="kind"><i>AI glossary</i><i>Models</i></span>' in page and "Added to the glossary" not in page
    assert "Mentioned in 1 story in the last 7 days." in page and '/all/?' not in page
    # its latest stories, as the site's underlines find them, written into the page (no download of data.json)
    assert '<h2 id="stories">Latest stories with this word</h2>' in page and 'data-match="[&quot;MoE&quot;' in page and 'data-case=1' in page
    assert '<script type="application/json" id="story-data">[' in page and "data.json" not in page
    # what makes it worth a visit: the words in the same stories, and the week's words as a cloud on glossary/
    assert "<h2>Often in the same stories</h2>" in page and 'href="/glossary/parameters/" style="font-size:' in page
    assert '"@type": "DefinedTerm"' in page and 'rel="canonical" href="https://projectaipulse.com/glossary/mixture-of-experts/"' in page
    index = (tmp_path / "glossary" / "index.html").read_text(encoding="utf-8")
    az = index[index.index("<h2>A to Z</h2>"):]
    assert az.count('<li><div><a href="/glossary/') == len(glossary.ENTRIES) and '<h2 id="A">A</h2>' in az
    assert 'id="levels"' not in index and "Everyday" not in index  # no levels: one list, A to Z, each word with its group
    # no "New this month" list (a new word has its "New" tag and its added day on its own page)
    assert "New this month" not in index and index.index("<h2>In the news · past 7 days</h2>") < index.index("<h2>A to Z</h2>")
    assert "Added to the glossary on 10 Oct 2026." in (tmp_path / "glossary" / "synthid" / "index.html").read_text(encoding="utf-8")
    cloud = index[index.index('<div class="cloud"'):index.index("<h2>A to Z</h2>")]
    assert cloud.count("<a ") == 2 and "Mixture of Experts</a>" in cloud  # the past 7 days' words only
    assert (tmp_path / "site.css").is_file()


def test_static_build_escapes_hostile_titles_on_every_page(tmp_path, monkeypatch):
    """Titles are outside text, and the pages are built from strings, so escaping is by hand: whatever a title holds,
    no built page may carry it as live HTML or let it end a <script> early. Collecting already strips tags from feed
    titles; this puts them straight in the database, as an official record or a hand-kept list might, to check the
    pages' own escaping."""
    from aipulse import consultations
    from aipulse.static import build
    monkeypatch.setattr(consultations, "ADDED", [])
    hostile = ['<img src=x onerror=alert(1)>', '</script><script>alert(2)</script>']
    conn = store.connect(tmp_path / "t.db")
    collect(conn, [{"name": "Fixture", "url": "rss", "category": "news"}], max_age_days=100000,
            fetcher=lambda u: (FIX / "sample_rss.xml").read_bytes(), log=lambda *_: None)
    for url, bad in zip(("https://example.com/openai-open-model", "https://example.com/eu-ai-act"), hostile):
        assert conn.execute("UPDATE items SET title = title || ' ' || ? WHERE url = ?", (bad, url)).rowcount == 1
    conn.commit()
    assert sum(any(b in c["title"] for b in hostile) for c in store.cards(conn, limit=100)[0]) == 2
    build(conn, tmp_path / "site")
    pages = list((tmp_path / "site").rglob("*.html"))
    assert len(pages) > 20
    for page in pages:
        text = page.read_text(encoding="utf-8")
        where = page.relative_to(tmp_path)
        # anywhere, even in a <script>'s data: no title may close the script and start its own
        assert "</script><script>alert(2)" not in text, where
        # outside scripts (whose content the browser never reads as HTML): no title's tag as a real tag
        assert hostile[0] not in re.sub(r"<script[ >].*?</script>", "", text, flags=re.S | re.I), where


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
    assert logo("Ando wants to take on Slack") is None  # no icon from a brand's own site (7 Oct 2026 terms audit)
    assert logo("Astra and Opus just passed Turing's test") is None  # a plain word Wikidata doesn't call a brand
    assert logo("YouTube promises custom feeds")["hex"] == "#FF0000"  # distinctive: no confirmation needed
    assert logo("Meta's new glasses use Slack", ["Meta"]) is None  # the page's own AI-company logos come first


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
    # Emails link to the site, which handles the unsubscribe link (and confirm links sent before one-click sign-up).
    assert "#(confirm|unsubscribe)=" in page
    assert not re.search(r"getUrl\(\) \+ \"\?action=confirm", script)
    # One-click: signing up sends the reader no email, and the form can't change an existing reader's streams.
    signup = script.split("function subscribe(p) {")[1].split("\n}\n")[0]
    assert "MailApp" not in signup and "if (rec && rec.confirmed) return {ok: true};" in signup


def test_glossary_explains_the_hard_words_in_stories():
    from datetime import date
    from pathlib import Path
    from aipulse import glossary
    assert len({e["id"] for e in glossary.ENTRIES}) == len(glossary.ENTRIES)
    assert {e["group"] for e in glossary.ENTRIES} <= set(glossary.GROUPS)
    assert glossary.TECHNICAL | set(glossary.ADDED) <= {e["term"] for e in glossary.ENTRIES}  # spelled as the entries
    assert glossary.terms_in("introducing PipSqueak 3, ShortSqueak, and (c.ai) lite") == ["character-ai"]
    assert glossary.terms_in("Holo4 comes in 27B dense and 35B-A3B Mixture of Experts") == ["parameters", "mixture-of-experts"]
    assert "parameters" not in glossary.terms_in("Instinct raises $1B Series C at a $10B valuation")  # money, not model size
    assert glossary.terms_in("add 250 ml of milk") == []  # acronyms only in capitals
    cards = [{"date": "2026-09-28", "title": "A RAG pipeline for agents", "summary": ""},
             {"date": "2026-08-01", "title": "An old RAG story", "summary": ""}]
    rag = next(e for e in glossary.payload(cards, date(2026, 9, 29))["entries"] if e["id"] == "rag")
    assert rag["recent"] == 1 and rag["search"] == "RAG" and rag["match"] and rag["level"] == "Technical"
    assert "example" not in rag  # no news story or date on a glossary word
    assert not rag["new"] and rag["added"] == "2026-09-29"
    entries = {e["id"]: e for e in glossary.payload(cards, date(2026, 10, 12))["entries"]}
    assert entries["synthid"]["new"] and entries["kl-divergence"]["new"]  # both added after launch
    assert not glossary.payload(cards, date(2026, 11, 20))["entries"][0]["new"]
    # the words they spell differently in headlines
    assert glossary.terms_in("Self-Evolving Vision-Language Models") == ["vlm", "self-improving-agent"]
    assert glossary.terms_in("KV compression for long chats") == ["kv-cache"]
    page = Path("templates/index.html").read_text(encoding="utf-8")
    assert 'id="glossary-open"' in page and page.index('id="subscribe-open"') < page.index('id="glossary-open"') and 'id="theme"' not in page  # one light theme
    assert 'fetch("glossary.json"' in page


def test_glossary_candidates_are_new_words_several_outlets_use():
    from aipulse import glossary
    card = lambda src, title, also=(): {"date": "2026-10-08", "title": title, "summary": "", "source": src,
                                        "also": [{"source": a} for a in also]}
    cards = [card("A", "Agents get HyperFlow"), card("B", "HyperFlow beats baselines", ["C"]),
             card("D", "Real-time AI-powered tools from OpenAI"), card("E", "Real-time AI-powered tools"),
             card("F", "Real-time AI-powered tools"), card("G", "One more MoE model"), card("H", "MoE again"),
             card("I", "MoE at last"), card("J", "KUALA LUMPUR WINS DATA CENTRE DEAL")]
    words = {w["word"]: w for w in glossary.candidates(cards, date(2026, 10, 10))}
    # counted with a story's other outlets; everyday words, known entries, names and capitals headlines left out
    assert set(words) == {"HyperFlow"}
    assert words["HyperFlow"]["outlets"] == 3 and words["HyperFlow"]["stories"] == 2
    assert words["HyperFlow"]["examples"] == ["Agents get HyperFlow", "HyperFlow beats baselines"]


def test_page_script_declares_each_name_once():
    import re
    from pathlib import Path
    script = Path("templates/index.html").read_text(encoding="utf-8").split("<script>")[-1]
    names = [n for decl in re.findall(r"^(?:const|let|function)\s+(.+?)(?:=>|\(|;|$)", script, re.M)
             for n in re.findall(r"(?:^|,\s*)([A-Za-z_$][\w$]*)\s*(?:=|\(|$)", decl)]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"declared twice (the page's script would stop): {dupes}"


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


def test_todays_board_keeps_the_days_start_and_top_3(tmp_path):
    from datetime import date
    from aipulse import today as board
    conn = store.connect(tmp_path / "b.db")
    day = date(2026, 10, 11)
    def card(i, n, d="2026-10-11", cat="news"):
        return {"id": i, "date": d, "category": cat, "also": [{}] * (n - 1)}
    # the week's cover (most outlets in 7 days) is left out; older than yesterday and other streams too
    cards = [card("cover", 20, "2026-10-06"), card("a", 9), card("b", 5, "2026-10-10"), card("c", 5), card("d", 2),
             card("old", 3, "2026-10-09"), card("x", 50, cat="other")]
    assert board.ranking(cards, day) == ["a", "c", "b", "d"]  # ties: the newer first
    first = board.record(conn, cards, day)
    assert first["start"] == {"a": 1, "c": 2, "b": 3, "d": 4} and first["peak"] == {"a": 1, "c": 2, "b": 3}
    # later that day: "d" climbs to the top, "e" is new; the start stays, the best ranks too
    later = [card("d", 12), card("e", 10)] + [c for c in cards if c["id"] != "d"]
    board.record(conn, later, day)
    p = board.payload(conn, later, day)
    assert p["ids"] == ["d", "e", "a", "c", "b"] and p["start"] == {"a": 1, "c": 2, "b": 3, "d": 4}
    assert p["peak"] == {"a": 1, "c": 2, "b": 3, "d": 1, "e": 2}
    # the next day starts afresh
    assert board.record(conn, later, date(2026, 10, 12))["start"]["d"] == 1


def test_todays_board_breaks_ties_by_buzz():
    from datetime import date
    from aipulse import today as board
    day = date(2026, 10, 10)
    def card(i, title, n=1, d="2026-10-09"):
        return {"id": i, "date": d, "category": "news", "title": title, "also": [{}] * (n - 1)}
    cards = [card("rimac", "Rimac, Ecoblox develop data centre power", 2), card("jev", "Maker of Jev valued at $7.5B", 2),
             card("big", "OpenAI offers a new service", 2), card("cover", "The week's biggest story", 9, "2026-10-06")]
    cards += [card(f"j{k}", f"A guide to Jev, part {k}", d="2026-09-20") for k in range(5)]
    cards += [card(f"o{k}", f"OpenAI story {k}", d="2026-09-20") for k in range(board.BIG + 1)]  # always in the news
    cards += [card("m", "The Model of the year"), card("m2", "a model of data")]  # "Model" is a word, not a name
    loud = board.buzz(cards, day)
    assert loud["jev"] == 6 and loud["rimac"] == 1 and loud["big"] == 0 and loud["m"] == 0
    assert board.ranking(cards, day)[:3] == ["jev", "rimac", "big"]  # 2 outlets each: Jev's buzz first


def test_glossary_note_lists_the_branchs_new_words_to_approve():
    from aipulse import glossary
    e = {"term": "Vision-language model", "group": "Models", "def": "An AI model that reads pictures and text."}
    subject, text, html = glossary.note([e], "glossary/2026-10-11")
    assert subject == "AI Pulse glossary: 1 new word to approve"
    assert "not on the site yet" in text and "merge glossary/2026-10-11" in text
    assert "<th align" in html and "<b>Vision-language model</b>" in html  # a table: word, group, meaning


def test_every_feature_has_the_shared_header():
    """Each feature on the front page's Features panels has its colour and icon for pages.feature_head."""
    from aipulse import pages
    from aipulse.server import TEMPLATE
    linked = set()
    for panel in re.findall(r'<div class="bc-feats">(.*?)</div>', TEMPLATE.read_text(encoding="utf-8")):
        linked |= set(re.findall(r'<a href="([^"]+)"', panel))
    assert linked == set(pages.FEATURES)
    head = pages.feature_head("release-cards/", "Release cards", "What came out?", "Every release.")
    assert '--f:var(--f-tool)' in head and "<h1>Release cards</h1>" in head and 'class="fh-q"' in head


def test_the_words_of_the_week_are_glossary_words_and_the_front_page_gets_them():
    from aipulse import glossary
    ids = {e["id"] for e in glossary.ENTRIES}
    hard = glossary.payload([])["hard"]
    assert set(hard) <= ids and len(set(hard)) == len(hard)
    assert not {"llm", "gpt", "data-center", "ai-agent", "gpu"} & set(hard)


def test_settings_and_secrets_are_read_only_in_config():
    """aipulse/config.py lists every setting and secret the app reads; nothing else reads the environment itself."""
    here = Path(__file__).parent.parent / "aipulse"
    readers = [p.name for p in here.rglob("*.py") if p.name != "config.py"
               and re.search(r"os\.environ|os\.getenv|getenv\(", p.read_text(encoding="utf-8"))]
    assert not readers, f"read through aipulse/config.py instead: {readers}"
    from aipulse import config
    listed = config.__doc__
    named = set(re.findall(r'secret\("([A-Z_]+)"\)|os\.environ\.get\("([A-Z_]+)"', (here / "config.py").read_text(encoding="utf-8")))
    assert all((a or b) in listed for a, b in named)  # each one it reads is described at the top
