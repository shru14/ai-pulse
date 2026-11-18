from datetime import date

from aipulse import companies, poster


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
