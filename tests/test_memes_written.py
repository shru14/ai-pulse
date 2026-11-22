from datetime import date

from aipulse import memegen, memes, memes_written, shown, store

DAY = date(2026, 10, 18)  # a nope/yep day in memes.ROTATION, a Sunday
MONDAY = date(2026, 10, 12)  # its week: Monday to Saturday the 17th


def _cards(day=DAY):
    base = {"summary": "", "source": "E", "date": day.isoformat(), "also": [], "kind": "news", "tags": []}
    return [{**base, "title": t, "url": f"https://e.com/{day}/{i}", "category": c} for i, (t, c) in enumerate([
        ("NVIDIA Releases Kumo Tabular: open models", "tool"), ("Cohere Releases Embed 5", "tool"),
        ("Startup raises $55M for agents", "business"), ("Chatbot lawsuit goes to court", "business")])]


POOH = {"format": "pooh", "labels": ["An if statement", "Kumo Tabular reasoning layer"],
        "based_on": ["NVIDIA Releases Kumo Tabular: open models"]}


def test_a_written_meme_goes_first_on_any_template_and_gemini_isnt_asked(tmp_path, monkeypatch):
    cards = _cards()
    monkeypatch.setattr(memes_written, "WRITTEN", {f"day:{DAY}": POOH})
    monkeypatch.setattr(shown, "MEMES", {})
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    asked = []
    monkeypatch.setattr(memegen, "_ask", lambda p, k, **kw: asked.append(p) or "{}")
    memes.GENERATED.clear()
    memegen.prepare(store.connect(tmp_path / "m.db"), cards, today=date(2026, 10, 19), day=DAY, make=True)
    meme = memes.of_the_day(cards, DAY)
    assert meme["format"] == "pooh" != memes.template_of(DAY)  # not the day's turn in the rotation, still used
    assert meme["labels"] == POOH["labels"] and meme["by"] == "written"
    assert not [p for p in asked if "news for today" in p]  # the day's meme: Gemini never asked
    memes.GENERATED.clear()


def test_a_written_meme_that_fails_a_check_is_skipped():
    cards = _cards()
    bad = [{**POOH, "based_on": ["A headline from another day"]},           # not one of the day's stories
           {**POOH, "based_on": ["Chatbot lawsuit goes to court"]},         # a story no joke may touch
           {**POOH, "labels": ["An if statement", "What the President calls AI"]},  # politics
           {**POOH, "labels": ["An if statement", "A $90M reasoning layer"]},       # a number no headline has
           {**POOH, "labels": ["An if statement", "x" * 80]},                       # too long
           {**POOH, "labels": ["An if statement", "Our newsletter"]},               # a plug
           {**POOH, "format": "nope"}, {**POOH, "labels": ["Only one"]}]
    for m in bad:
        assert memes_written.checked(m, cards, "day", DAY) is None, m
    assert memes_written.checked(POOH, cards, "day", DAY)["by"] == "written"


def test_saturdays_job_writes_the_weeks_meme_from_monday_to_saturday(monkeypatch):
    week = _cards(MONDAY) + _cards(date(2026, 10, 17))
    m = {**POOH, "based_on": ["Cohere Releases Embed 5"], "labels": ["A search box", "Embed 5 retrieval layer"]}
    monkeypatch.setattr(memes_written, "WRITTEN", {f"week:{MONDAY}": m})
    assert memes_written.get(week, "week", MONDAY)["labels"] == m["labels"]
    assert memes_written.get(_cards(DAY), "week", MONDAY) is None  # Sunday's stories aren't the week's
    assert memes_written.get(week, "day", MONDAY) is None


def test_the_job_sees_light_stories_and_the_last_days_templates(monkeypatch):
    brief = memes_written.brief(_cards(), "day", DAY, ["gru"])
    assert "Kumo Tabular" in brief and "lawsuit" not in brief and '"pooh"' in brief and "pick another): gru" in brief
    monkeypatch.setattr(memes_written, "WRITTEN", {f"day:{date(2026, 10, 16)}": POOH})
    recent = memes_written.recent_templates(DAY)
    assert "pooh" in recent and memes.template_of(date(2026, 10, 17)) in recent and len(recent) <= 6


def test_the_note_lists_only_the_branchs_new_memes(monkeypatch):
    old = {**POOH, "labels": ["A", "B"]}
    monkeypatch.setattr(memes_written, "WRITTEN", {f"day:{date(2026, 10, 17)}": old, f"day:{DAY}": POOH})
    base = f'WRITTEN: dict[str, dict] = {{\n    "day:2026-10-17": {old!r},\n}}\n'
    subject, text, html = memes_written.note(base, f"memes/{DAY}")
    assert subject.endswith("1 new meme to approve") and "Kumo Tabular reasoning layer" in text and "1. A\n" not in text
    assert "merge memes/2026-10-18" in html
    assert memes_written.note(base.replace("{\n", "{\n" + f'    "day:{DAY}": {POOH!r},\n', 1), "b") is None
