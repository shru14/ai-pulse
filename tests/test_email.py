"""The daily and weekly email: content, checks, readers' choices, audio, memes and approvals."""
import re
from datetime import date, timedelta
from pathlib import Path

from aipulse import classify, store

FIX = Path(__file__).parent / "fixtures"
from helpers import _fake_embedder, _story


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


def test_late_arrivals_reach_the_next_email_once(monkeypatch):
    from datetime import date
    from aipulse import digest
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    card = lambda i, day, added, **k: {"id": f"l{i}", "title": f"Story {i}", "summary": "", "url": f"https://ex.com/{i}",
                                       "source": f"S{i}", "category": "news", "date": day, "added_at": added, **k}
    since = "2026-10-10T05:00:00+00:00"  # the newest arrival the 9 Oct email saw
    cards = [card(1, "2026-10-10", "2026-10-10T18:00:00+00:00"),
             card(2, "2026-10-09", "2026-10-10T12:00:00+00:00"),  # dated 9 Oct, came in after that email: late
             card(3, "2026-10-09", "2026-10-09T20:00:00+00:00"),  # in the 9 Oct email already
             # a lab's own post that came late and leads a story first reported before that email: not again
             card(4, "2026-10-09", "2026-10-10T16:00:00+00:00", first_added="2026-10-09T21:00:00+00:00"),
             card(5, "2026-10-05", "2026-10-10T12:00:00+00:00")]  # too old to be news (LATE_DAYS)
    late = [c["id"] for n in digest.by_streams(cards, ["news"], date(2026, 10, 10), since).values() for c in n]
    assert late == ["l1", "l2"]
    assert [c["id"] for c in digest.by_streams(cards, ["news"], date(2026, 10, 10))["news"]] == ["l1"]  # no time: none
    # a late story leads only when enough outlets reported it (LATE_TOP); otherwise it's after the day's own
    two = [{"title": "x", "source": "Other", "url": "https://o.com/2", "date": "2026-10-09"}]
    assert digest._fits_top({"late": True, "source": "S2", "also": two}) and not digest._fits_top({"late": True, "source": "S2"})
    assert digest._fits_top({"source": "S1"})
    monkeypatch.setattr(digest, "LATE_TOP", 0)
    assert not digest._fits_top({"late": True, "source": "S2", "also": two})


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
    # A short real headline (OpenAI's "LifeVal" held 2 Nov's email) is fine; one with no letter isn't.
    short = [card(i, "news", title=t) for i, t in enumerate(("LifeVal", "GPT-5", "o3", "2026", "--"))]
    held = quality.problems(digest.by_streams(short, streams, day), short, day)
    assert [p for p in held if "no real headline" in p] == [p for p in held if '"2026"' in p or '"--"' in p] and len(held) == 2
    # A general outlet's story that doesn't name AI is left out of the email, not a reason to hold it.
    off = card(9, "news", source="404 Media", title="Alibaba Cloud opens data centres in Europe", summary="")
    assert off not in digest.by_streams([*good, off], streams, day)["news"] and digest.left_out([*good, off], streams, day) == [off]
    # A thin day is sent, saying so.
    _, text, _ = digest.build(good[:2], streams, day)
    assert "A quiet day for AI: only 2 stories" in text and "Weekends are usually slow" in text
    assert "quiet day" not in digest.build(good, streams, day)[1]
    subject, text, _ = quality.alert(day, ["x"], streams)
    assert "HELD" in subject and "was not sent to anyone" in text


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
    monkeypatch.setattr(sb.urllib.request, "urlopen", lambda req, timeout: (seen.append((req.full_url, req.data)), io.BytesIO(_json.dumps(data).encode()))[1])
    assert sb.current("k" * 32, "https://script.google.com/macros/s/X/exec") == got
    assert seen == [("https://script.google.com/macros/s/X/exec", b"action=list&key=" + b"k" * 32)]  # key in the body, never the address
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
    assert subject == "AI Pulse daily · Monday, 28 September 2026" and "Here are the stories that mattered the most." in text
    top = text.split("Here are the stories that mattered the most.")[1].split("THE REST OF THE DAY")[0]
    assert top.index("Story 0") < top.index("Story 1") and "Outlet 0 +4 outlets" in top  # most reported first
    assert top.count("• [") == 10 and "Story 20" not in top  # ten, never a tutorial
    assert "1. " not in top  # not numbered
    rest = text.split("THE REST OF THE DAY")[1]
    assert "Releases (" not in rest and "All in the top 10: Releases, Policy." in rest  # one row for them
    _, text2, _ = digest.build(cards, ["releases", "news", "infra"], date(2026, 9, 28))
    assert "Nothing new today: Infra." in text2 and "Infra (" not in text2  # an empty stream too
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
    assert "https://projectaipulse.com/glossary/" in text and "/glossary/\"" in html  # every email points to the glossary
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


def test_word_of_the_day_rotates_through_the_glossary(monkeypatch):
    from datetime import timedelta
    from aipulse import digest, glossary
    start, n = glossary.ROTATION_START, len(glossary.ENTRIES)
    words = [glossary.word_of_the_day(start + timedelta(days=k))["id"] for k in range(n)]
    assert len(set(words)) == n  # every word once before any comes back
    assert glossary.word_of_the_day(start + timedelta(days=n)) == glossary.word_of_the_day(start)
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    # RAG's day, or the day before if that's the weekly email's (it gives the week's word), whatever words get added
    day = start + timedelta(days=words.index("rag"))
    day -= timedelta(days=day.weekday() == digest.WEEKLY)
    card = {"id": "w1", "title": "A RAG pipeline for support teams", "summary": "", "url": "https://ex.com/rag",
            "source": "S", "category": "news", "kind": "news", "date": day.isoformat(), "added_at": f"{day}T10:00:00+00:00"}
    _, text, html = digest.build([card], ["news"], day)
    assert "WORD OF THE DAY: RAG" in text and "Where it came up: A RAG pipeline for support teams" in text
    assert "https://projectaipulse.com/glossary/\"" in html and "Word of the day</div>" in html


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


def test_word_of_the_day_from_a_smaller_story_does_not_come_back_within_a_week(monkeypatch):
    from datetime import date, timedelta
    from aipulse import digest
    monkeypatch.setenv("DIGEST_EMAIL", "digest@example.com")
    monday = date(2026, 10, 19)

    def card(d, i, title, outlets=0):
        return {"id": f"{d}-{i}", "title": title, "summary": "", "url": f"https://ex.com/{d}/{i}", "source": f"S{i}",
                "category": "news", "kind": "news", "date": d.isoformat(), "added_at": f"{d}T10:00:00+00:00",
                "also": [{"source": f"O{i}{k}", "title": title, "url": f"https://o.com/{d}/{i}/{k}"} for k in range(outlets)]}

    def day(d, *small):  # the 5 biggest stories use no specialist word; the words are in smaller ones
        return [card(d, i, f"Big story {i} about OpenAI", outlets=10 - i) for i in range(6)] + \
               [card(d, 10 + i, t) for i, t in enumerate(small)]
    tuesday = monday + timedelta(days=1)
    # TPU is the commoner word, so without the week before CUDA (the rarer) would come back on Tuesday
    cards = day(monday, "Nvidia opens up CUDA") + day(tuesday, "Nvidia opens up CUDA", "Google rents out its TPU",
                                                     "A TPU deal for Anthropic", "Meta weighs a TPU order")
    assert "WORD OF THE DAY: CUDA" in digest.build(cards, ["news"], monday)[1]
    assert "WORD OF THE DAY: TPU" in digest.build(cards, ["news"], tuesday)[1]  # not CUDA again


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
    assert "Here are the stories that mattered the most." in text and "of your top 10" not in text  # picks are marked, not announced
    top = text.split("Here are the stories that mattered the most.")[1].split("THE REST OF THE DAY")[0]
    yours = [l for l in top.splitlines() if "[Your choice]" in l]
    assert len(yours) == digest.PICKS and "Big story 0" in top and "Big story 4" in top  # 5 of theirs, then the biggest
    assert "Kerala launches" in top  # their own words, in the headline
    assert " · YOUR CHOICE</div>" in html and "Left out" not in text  # nothing left out: no note
    # 12 stories in their streams (one more than the top 10 holds): still a top 10, their own first
    twelve = big[2:10] + [kerala[0], robots[0], *guides[:2]]
    _, text, _ = digest.build(twelve, ["news"], day, prefs={"more": ["Robotics"], "less": [], "words": ["Kerala"]})
    assert "Here are the stories that mattered the most." in text and "lighter day" not in text
    top = text.split("Here are the stories that mattered the most.")[1].split("THE REST OF THE DAY")[0]
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


def test_a_busy_day_over_many_sources_is_sent_but_one_source_flooding_is_held():
    from datetime import date, timedelta
    from aipulse import quality
    day = date(2026, 10, 15)  # a Thursday
    labs = [f"Lab {i}" for i in range(20)]
    def launch(d, i, source, extra=""):
        return {"id": f"{d}-{i}{extra}", "category": "tool", "date": d.isoformat(), "title": f"Launch {d} {i}{extra}",
                "url": f"https://example.com/{d}/{i}{extra}", "source": source, "summary": "x"}
    history = []  # two weeks of ~12 releases a weekday, from 20 labs
    for k in range(1, 15):
        d = day - timedelta(days=k)
        history += [launch(d, i, labs[(k + i) % 20]) for i in range(3 if d.weekday() >= 5 else 12)]
    assert quality.usual(history, "tool", day) == 12
    busy = [launch(day, i, labs[i % 20]) for i in range(38)]  # over 3x usual, but no lab gives more than 2
    assert not [p for p in quality.problems({"releases": busy}, history + busy, day) if "usual" in p]
    flood = [launch(day, i, "Lab 0", "-old") for i in range(10)]  # one lab re-dates ten old posts
    held = [p for p in quality.problems({"releases": busy[:12] + flood}, history + busy[:12] + flood, day)
            if "usual" in p]
    assert held == []  # 22 stories: not over 3x usual, so not held
    flood = [launch(day, i, "Lab 0", "-old") for i in range(30)]  # one lab re-dates thirty old posts
    held = [p for p in quality.problems({"releases": busy[:12] + flood}, history + busy[:12] + flood, day)
            if "usual" in p]
    assert len(held) == 1 and "31 of them from Lab 0" in held[0]
    wild = [launch(day, i, labs[i % 20], "-x") for i in range(61)]  # every lab at once: over 5x the stream's usual
    assert [p for p in quality.problems({"releases": wild}, history + wild, day) if "61 stories, over 5x" in p]


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
    assert f"following button\nAdd Infra: {mine}" in text
    note = html.split("New on AI Pulse: Infra")[1].split("</div>")[0]
    assert f'href="{mine}"' in note and "Add Infra →" in note
    assert digest._new_stream(date(2026, 11, 1), ["research"]) == ""
    # its stories are on topic without naming AI, and carry the tag and theme readers can choose
    story = {"title": "Teraco opens a 40MW data centre in Cape Town", "summary": "", "source": "ESI Africa", "category": "infra"}
    assert quality.on_topic(story)
    assert {classify.INFRA_TAG} <= preferences.labels(story)
    assert "Chips, compute & energy" in preferences.labels(story)  # an older saved choice still matches
    assert classify.INFRA_TAG in digest.story_tags(story)


def test_the_email_introduces_one_new_feature_a_day_each_once():
    from aipulse import digest
    start = digest.FEATURES_FROM
    days = [start + timedelta(days=k) for k in range(40)]
    shown = [digest._feature(d) for d in days]
    # newest first, every one once, the Sunday email's day too, none before the start
    assert [f for f in shown if f] == digest.FEATURES
    assert all(f for d, f in zip(days, shown) if d < start + timedelta(days=len(digest.FEATURES)))
    assert digest._feature(start - timedelta(days=1)) is None
    # a small strip at the top, above the day's stories, with a link to the page on the site
    day = next(d for d in days if not digest.weekly(d))
    card = {"id": "r", "title": "A paper on AI agents", "summary": "", "url": "https://ex.com/r", "source": "arXiv",
            "category": "research", "date": day.isoformat(), "added_at": f"{day}T10:00:00+00:00"}
    _, text, html = digest.build([card], ["research"], day)
    name, _, path = digest._feature(day)
    assert f"NEW ON AI PULSE: {name}" in text and f"Have a look: {digest.rss.SITE}{path}" in text
    assert html.index("New on AI Pulse:") < html.index("A paper on AI agents") < html.index("Every story of the day in one table")


def test_the_email_on_a_month_s_first_links_the_new_issue_and_the_queue_waits_a_day(monkeypatch):
    from aipulse import digest
    # the emails of 1 Dec, 1 Jan and 1 Mar, each about the month's last day; 1 Nov's already went out as usual
    for day, month, name in [(date(2026, 11, 30), "2026-11", "November 2026"), (date(2026, 12, 31), "2026-12", "December 2026"),
                             (date(2027, 2, 28), "2027-02", "February 2027")]:
        title, _, path = digest._feature(day)
        assert title == f"Monthly issue: {name}" and path == f"monthly/{month}/"
    assert digest._feature(date(2026, 10, 31)) == digest.FEATURES[13]
    assert digest._feature(date(2026, 11, 1)) == digest.FEATURES[14]
    # a queue that still runs: the page due on the 1st's email comes the next day, and none is skipped
    queue = [(str(k), "", f"p{k}/") for k in range(120)]
    monkeypatch.setattr(digest, "FEATURES", queue)
    days = [digest.FEATURES_FROM + timedelta(days=k) for k in range(110)]
    shown = [digest._feature(d) for d in days]
    regular = [f for f in shown if not f[0].startswith("Monthly")]
    assert regular == queue[:len(regular)]
    assert sum(f[0].startswith("Monthly") for f in shown) == 3  # 30 Nov, 31 Dec, 31 Jan
    assert digest._feature(date(2026, 12, 1)) == queue[(date(2026, 11, 30) - digest.FEATURES_FROM).days]


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
    samples += [{"format": f, "labels": ["A"] * len(memes.TEMPLATES[f][2])} for f in memes.PLAIN]
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
    assert set(used[:16]) == set(memes.TEMPLATES)  # all sixteen in turn
    # a day whose stories can't fill its template still gets one (a standby joke, no names or numbers), on that template
    for d in days[:16]:
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
    # the site's meme of the week: the past 7 days (today and the 6 days before), the next template each day
    days7 = [date(2026, 10, 10) + timedelta(days=k) for k in range(8)]
    assert all(memes.template_of_7_days(a) != memes.template_of_7_days(b) for a, b in zip(days7, days7[1:]))
    today = date(2026, 10, 10)
    cards = [{"title": f"Story {k}", "summary": "", "url": f"https://e.com/{k}", "source": "E", "category": "news",
              "kind": "news", "date": (today - timedelta(days=k)).isoformat(), "also": [], "tags": []} for k in range(9)]
    assert [c["title"] for c in memes.last_7_days(cards, today)] == [f"Story {k}" for k in range(7)]
    p = memes.payload(cards, today)
    assert (p["from"], p["to"], p["week"]) == ("2026-10-04", "2026-10-10", 7)
    assert p["image"] == "memes/7days-2026-10-10.jpg" and p["format"] == memes.template_of_7_days(today)


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
    monkeypatch.setattr(digest, "_SHOWN", {})  # no words of the week shown before
    card = lambda i, day, cat="news", outlets=0, title=None: {
        "id": f"s{i}", "title": title or f"Story {i}", "summary": f"What happened in story {i}.", "url": f"https://ex.com/{i}",
        "source": f"Outlet {i}", "category": cat, "kind": "news" if cat == "news" else None, "date": day,
        "added_at": f"{day}T10:00:00+00:00", "tags": [],
        "also": [{"title": f"Story {i}", "source": f"Other {k}", "url": f"https://o{k}.com/{i}", "date": day} for k in range(outlets)]}
    cards = ([card(1, "2026-09-29", "news", 6, "Big chip deal for a new data center")]  # the week's most reported
             + [card(i, "2026-10-0" + str(1 + i % 3), "news", 0, f"Hyperscaler story {i}") for i in range(2, 9)]
             + [card(9, "2026-10-04", "news", 9, "Sunday's story is next week's email")]  # not Monday to Saturday
             + [card(i, "2026-10-03", "tool" if i % 2 else "news") for i in range(10, 22)])
    subject, text, html = digest.build(cards, ["releases", "news"], date(2026, 10, 3))
    assert subject == "AI Pulse · The week in AI, and Saturday, 3 October 2026"
    assert "THE WEEK IN AI, 28 Sep – 3 Oct" in text and "The week in AI" in html
    # the week's count and the day's, a line each
    assert "This week, 28 Sep – 3 Oct: 20 stories.\nSaturday: " in text  # Monday to Saturday, not Sunday's
    assert "STORY OF THE WEEK: Big chip deal for a new data center" in text and "Sunday's story" not in text
    assert "WORD OF THE WEEK: Hyperscaler" in text and "It came up in 7 of the week's stories" in text
    assert "Word of the day" not in html and "Meme of the day" not in html and "WORD OF THE DAY" not in text
    assert "The stories that mattered the most on Saturday." in text
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


def test_the_word_of_the_week_skips_the_words_of_the_8_weeks_before(tmp_path, monkeypatch):
    from datetime import date
    from aipulse import digest
    monkeypatch.setattr(digest, "_SHOWN", {date(2026, 10, 17): "jepa", date(2026, 8, 22): "vla"})
    monkeypatch.setattr(digest, "_WEEK_WORD", {})
    card = lambda i, day, text: {"id": f"w{i}", "title": text, "summary": "", "url": f"https://ex.com/w{i}",
                                 "source": "Ex", "category": "news", "date": day}
    cards = ([card(i, "2026-10-20", "An LLM on every phone") for i in range(6)]  # the commonest, but no hard word
             + [card(i, "2026-10-21", "KL divergence explained") for i in [6]]  # the hardest, but in one story only
             + [card(i, "2026-10-21", "JEPA for video") for i in range(7, 12)]
             + [card(i, "2026-10-22", "A new VLA for robots") for i in range(12, 14)]
             + [card(i, "2026-10-22", "A hyperscaler buys chips") for i in range(14, 18)])
    # JEPA was the word of the week 17 Oct; VLA's last week was more than 8 weeks before, and it's harder than hyperscaler
    assert digest._week_word(cards, date(2026, 10, 24)) == "vla"
    # kept once the week is over (each site run), and then the email shows the kept one
    conn = store.connect(tmp_path / "t.db")
    assert digest.record_week_word(conn, cards, date(2026, 10, 25)) == (date(2026, 10, 24), "vla")
    monkeypatch.setattr(digest, "_SHOWN", {})
    assert digest.load_week_words(conn)[date(2026, 10, 24)] == "vla"
    assert digest._week_word([], date(2026, 10, 24)) == "vla"


def test_top_news_takes_at_most_two_tiles_a_stream_on_a_quiet_day():
    from aipulse import poster
    stories = [{"id": f"s{i}", "title": f"Story {i}", "source": "Ex"} for i in range(12)]
    stream_of = {id(c): ("releases" if i < 8 else "news" if i < 10 else "infra") for i, c in enumerate(stories)}
    tiles = poster._spread(stories, stories[:1], 6, stream_of)  # the hot story (a release) isn't a tile
    assert [stream_of[id(c)] for c in tiles] == ["releases", "releases", "news", "news", "infra", "infra"]
    # a story more outlets carried keeps its place over the limit
    stories[3]["also"] = [{"source": "Other"}]
    assert stories[3] in poster._spread(stories, stories[:1], 6, stream_of)


def test_email_subjects_are_a_few_of_the_headlines_own_words_never_cut_with_dots(monkeypatch):
    from aipulse import poster
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(poster, "_SHORTENED", {})
    monkeypatch.setattr(poster, "GEMINI_ASKS", [3])
    assert poster._subject("Apple sues OpenAI over alleged trade secret theft") == "Apple sues OpenAI"
    assert poster._subject("AI drug development startup Pathos AI closes $237M investment") == "Pathos AI closes $237M investment"
    assert poster._subject("Amid hardware legal battle, OpenAI releases a $230 keyboard for Codex") == \
        "OpenAI releases a $230 keyboard for Codex"
    assert poster._subject("SpaceXAI releases Grok 4.5, which Elon describes as an Opus-class model") == "SpaceXAI releases Grok 4.5"
    # the reaction comes first, the news after "as": the subject keeps the news
    assert poster._subject("Nvidia’s stock drops as board reportedly preps to oust CEO Jensen Huang") == \
        "Nvidia’s board preps to oust Jensen Huang"
    assert poster._subject("Apple shares slip as investors weigh China risk") == "Apple shares slip"
    # no rule cuts it cleanly: Gemini picks the words, and only the headline's own, in order, pass
    hard = "U.S. court rules Pentagon's blacklisting of Anthropic was unlawful"
    assert poster._subject(hard, ask=lambda p: '{"subject": "court rules Pentagon\'s blacklisting of Anthropic unlawful"}') == \
        "Court rules Pentagon's blacklisting of Anthropic unlawful"
    assert not poster._kept("Court says Pentagon blacklisting was illegal", hard)  # words it didn't say
    assert not poster._kept("Pentagon blacklisting of Anthropic…", hard)
    # nor one that leaves out a name or a currency on the way
    assert not poster._kept("Claude is Anthropic's answer to Meta", "Claude Duet is Anthropic's answer to Meta Muse and OpenAI Dots")
    assert not poster._kept("OpenAI runs to raise 163.5 billion", "OpenAI runs to raise R $ 163.5 billion before IPO Anthropic")
    monkeypatch.setattr(poster, "_SHORTENED", {})
    short = poster._subject(hard, ask=lambda p: '{"subject": "Judges slam the Pentagon"}')  # refused: the rule's fallback
    assert "…" not in short and len(short.split()) <= poster.SUBJECT_WORDS and short.startswith("U.S. court rules")


def test_daily_listen_picks_one_per_stream_and_says_it_truly():
    from aipulse import audio, rss
    day = date(2026, 10, 23)  # a Friday
    cat = {n: rss.FEEDS[n][0] for n in rss.FEEDS}

    def card(i, n, outlets=0, title=None):
        return {"id": f"c{i}", "title": title or f"Story {i}", "summary": "First it said this. Then more.", "source": f"S{i}",
                "url": f"https://ex.com/{i}", "category": cat[n], "kind": "news", "date": day.isoformat(),
                "added_at": f"{day}T10:00:00+00:00", "tags": [],
                "also": [{"source": f"O{i}{k}", "title": "x", "url": f"https://o.com/{i}/{k}"} for k in range(outlets)]}
    every = list(rss.FEEDS)
    cards = [card(10 * k + j, n, outlets=5 - j) for k, n in enumerate(every) for j in range(3)]
    six = audio.plan(cards, day, every)["six"]
    assert sorted(n for n, _ in six) == sorted(every)  # one from each stream, each its biggest
    assert all(c["title"].endswith("0") or c["id"].endswith("0") for _, c in six)
    assert audio.line({"six": six}, every, None, 110) == "2 minutes · the day's top 6, one from each stream"
    # a stream with nothing: the biggest story left from the others takes its place, and the bar doesn't claim each
    quiet = [c for c in cards if c["category"] != cat["regulation"]]
    six = audio.plan(quiet, day, every)["six"]
    assert len(six) == 6 and "regulation" not in {n for n, _ in six}
    assert audio.line({"six": six}, every, None, 110) == "2 minutes · the day's top 6"
    # a reader's own: their streams only, their picks first, "your" in the bar and the voice
    mine = ["releases", "policy"]
    cards.append(card(99, "policy", title="A humanoid robot rule"))
    plan = audio.plan(cards, day, mine, {"more": ["Robotics"]})
    assert {n for n, _ in plan["six"]} <= set(mine) and plan["six"][0][1]["id"] == "c99"
    assert "your top 6" in audio.line(plan, mine, {"more": ["Robotics"]}, 100)
    assert "Here are your 6 top stories" in audio.script(day, plan, own=True)
    # never how many outlets, only who reported it
    said = audio.script(day, audio.plan(cards, day, every))
    assert "outlets" not in said and "Reported by S" in said and "First it said this." in said
    # the clip's address: "everyone", or a code of the settings alone (the same for readers who set the same)
    assert audio.url(day, every, {}) == f"{rss.SITE}listen/2026-10-23-everyone.mp3"
    code = audio.setup(mine, {"more": ["Robotics"], "often": ["weekly"], "interests": ["chips"]})
    assert code == audio.setup(mine, {"more": ["Robotics"]}) and re.fullmatch(r"[0-9a-f]{12}", code)


def test_sunday_listen_starts_with_the_week():
    from aipulse import audio, rss
    sat = date(2026, 10, 24)

    def card(i, d, outlets, cat="news"):
        return {"id": f"w{i}", "title": f"Week story {i}", "summary": "", "source": f"S{i}", "url": f"https://ex.com/w{i}",
                "category": cat, "kind": "news", "date": d.isoformat(), "added_at": f"{d}T10:00:00+00:00", "tags": [],
                "also": [{"source": f"O{i}{k}", "title": "x", "url": f"https://o.com/{i}/{k}"} for k in range(outlets)]}
    cards = [card(1, sat - timedelta(days=4), 8), card(2, sat - timedelta(days=3), 4), card(3, sat - timedelta(days=2), 0),
             card(4, sat, 0, "tool"), card(5, sat, 0, "policy")]
    plan = audio.plan(cards, sat, list(rss.FEEDS))
    assert plan["week"]["id"] == "w1" and [c["id"] for _, c in plan["also"]] == ["w2"]  # one outlet in a week: not important
    said = audio.script(sat, plan)
    assert said.index("These were the important updates this week") < said.index("The story of the week") \
        < said.index("Week story 2") < said.index("Now, Saturday the 24th, in short")
    assert audio.line(plan, list(rss.FEEDS), None, 140) == "2 minutes · the week's important updates, then Saturday in short"


def test_no_meme_is_promotional():
    """Memes joke about AI, never plug us (owner, 2026-10-21 and 2026-11-06): every standby wording passes, and a
    meme that plugs, whoever wrote it, is replaced."""
    from datetime import date
    from aipulse import memes
    for f, wordings in memes.STANDBY.items():
        for w in wordings:
            assert not memes.plugs({"format": f, **w}), (f, w)
    for t in ["Letting AI Pulse pick", "Asking a chatbot to read them for you", "Reading only the 10 that mattered",
              "Subscribe for more", "Keeping up with AI", "A data-driven AI insights engine", "A big spreadsheet"]:
        assert memes.PROMO.search(t), t
    day = date(2026, 11, 8)
    want = memes.template_of(day)
    memes.GENERATED[("day", day)] = {"format": want, **memes.STANDBY[want][0], "labels": ["Read AI Pulse"] * 4, "based_on": []}
    card = {"title": "x", "summary": "", "url": "u", "source": "E", "category": "news", "kind": "news",
            "date": day.isoformat(), "also": [], "tags": []}
    m = memes.of_the_day([card], day)
    memes.GENERATED.clear()
    assert m["format"] == want and not memes.plugs(m)


def test_every_meme_template_can_be_made_from_the_days_stories():
    """Each of the 16 templates has a rule built from the day's stories, so the meme is about that day's news
    (owner, 2026-11-09), and the launch names it uses are real names, not "AI Model"."""
    from aipulse import memes
    made = {g.__name__.strip("_").replace("_", "") for g in memes.FORMATS}
    assert set(memes.ROTATION) <= made, set(memes.ROTATION) - made
    assert memes.launch_of({"title": "Kakao launches AI Model for banks"}) is None
    assert memes.launch_of({"title": "Baidu releases ERNIE 5.5 Flash: a faster model"}) == ("Baidu", "ERNIE 5.5 Flash")
