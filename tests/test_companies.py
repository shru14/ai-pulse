from datetime import date

import pytest

from aipulse import companies, poster

# The tests' own profiles and checked-to day, so the daily drafts (new PROFILES rows, a later CHECKED_TO) never break them
WEEK = [("2026-11-16", "Noeri", "d", "m", "$110M raised", "Concept", "b", "https://n.example", "N"),
        ("2026-11-17", "Model ML", "d", "m", "$250M raised", "Business model", "b", "https://m.example", "M")]


@pytest.fixture(autouse=True)
def _own_profiles(monkeypatch):
    monkeypatch.setattr(companies, "PROFILES", WEEK)
    monkeypatch.setattr(companies, "LEFT_OUT", [])
    monkeypatch.setattr(companies, "CHECKED_TO", "2026-11-17")


def _card(day, title, *others):
    return {"date": day, "title": title, "source": "A", "url": f"https://a.example/{day}",
            "also": [{"source": s, "title": title} for s in others]}


def test_no_profile_no_box():
    assert poster._company_of_day(date(2026, 11, 10)) == ([], "")


def test_week_ranks_by_outlets_then_days_then_latest():
    cards = [_card("2026-11-16", "Noeri raises $110M", "B", "C")]
    best, outlets, seen, picks, rule = companies.of_week(cards, date(2026, 11, 21))
    assert (best["name"], outlets, seen, picks, rule) == ("Noeri", 3, 1, 2, "outlets")
    assert "more than any" in companies.why_week(outlets, seen, picks, rule)
    best, *_, rule = companies.of_week([], date(2026, 11, 21))
    assert (best["name"], rule) == ("Model ML", "latest")  # a tie goes to the latest, and says so


def test_big_labs_left_out():
    cards = [_card("2026-11-18", "OpenAI raises $10B in new round", "B"),
             _card("2026-11-18", "Acme Robotics raises $40M Series B", "B")]
    assert [c["company"] for c in companies.candidates(cards)] == ["Acme Robotics"]


def test_hacker_news_keeps_ai_launches_two_weeks(tmp_path):
    import json
    from aipulse import social, store
    conn = store.connect(tmp_path / "t.db")
    now = 1_800_000_000
    items = {1: {"id": 1, "type": "story", "title": "Launch HN: Pomerado - an MCP for any website, for AI agents",
                 "url": "https://p.example", "score": 80, "descendants": 30, "time": now - 3600},
             2: {"id": 2, "type": "story", "title": "Show HN: my bread recipe", "score": 900, "descendants": 400, "time": now - 60}}
    fetcher = lambda url: json.dumps(list(items) if url.endswith("topstories.json")
                                     else items[int(url.rsplit("/", 1)[1][:-5])]).encode()
    social.hacker_news(conn, fetcher=fetcher, now=now)
    items.pop(1)  # gone from the top stories the next run: still kept
    social.hacker_news(conn, fetcher=fetcher, now=now + 86400)
    (t,) = social.payload(conn)["launches"]
    assert t["points"] == 80 and t["hn"].endswith("id=1")
    social.hacker_news(conn, fetcher=fetcher, now=now + 15 * 86400)
    assert social.payload(conn)["launches"] == []
    companies_rows = companies.launches({"launches": [t]})
    assert [r["title"] for r in companies_rows] == [t["title"]]
