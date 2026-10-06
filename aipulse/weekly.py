"""The weekly dossier (in testing): the week's stories on what a reader follows.

A reader names up to TOPICS interests in their own words ("How hospitals are using AI"). For each,
the briefing finds the week's (see last_week: Monday to Saturday on a Sunday, for the Sunday email; Monday to
Sunday from Monday on) stories that answer it best (search.py: by meaning and by
words and by the site's tags). Each topic opens with who and where it was about (the stories' tags), then the lead
story and earlier stories on it, then the rest of the week day by day. Every line is a story as
its publisher wrote it, linked to the original: the dossier picks and orders, and writes nothing of its own.

Every full site run works out every reader's interests (prepare) and keeps the result in the
database (table `dossiers`), under an id made from the interest with a secret key (interest_id): the site
publishes each as dossier/<id>.json, and a reader's link to their dossier (dossier.html#<id>.<id>) carries
only ids. The interests themselves stay in the sign-up web app, with the reader's other choices.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections import Counter
from datetime import date, timedelta
from html import escape

from . import rss, search
from .digest import GREY, HEADLINE, INK as DIGEST_INK, LINK, _outlets, _short, story_tags, tag

TOPICS = 3        # topics per reader
PER_TOPIC = 8     # stories per topic: the lead, then the rest of the week day by day
THREADED = 1      # of those, how many show the earlier stories they follow on from (the lead)
TRACKED = 20      # earlier stories followed per lead (the closest, in the HISTORY days before the week)
LEAD_FROM = 3     # the lead is the most widely reported of the topic's best this many
NAMES, PLACES = 6, 4  # who and where, per topic: the names and places its stories are tagged with most
HISTORY = 30      # days before the week searched for earlier stories ("Dig deeper"; embed.DAYS keeps their vectors)
SAME_STORY = 0.32  # cosine (shared direction out) for a story to follow on from an earlier one, which must also
                   # answer the reader's topic: closeness alone also joins stories that only share a company.
                   # Of those, the ones closest to both (by the lower of the two) are shown


def last_week(day: date) -> tuple[date, date]:
    """The dossier's week on `day`, as (its Monday, the day after it ends). On a Sunday, the Sunday email's: this
    week's Monday to Saturday. Any other day: the last whole week, Monday to Sunday, so a Sunday email's link
    shows the full week from Monday on (the same Monday: the same dossier, with Sunday's stories added)."""
    monday = day - timedelta(days=day.weekday())
    if day.weekday() == 6:
        return monday, day
    return monday - timedelta(days=7), monday


def earlier(conn, card: dict, week: search.Index, past: search.Index, topic, used: set[str] = frozenset()) -> list[dict]:
    """The stories before this week that this card follows on from: close to it in meaning and on the reader's
    topic (`topic`, its vector), the TRACKED closest to both, not `used` already, oldest first."""
    from . import store
    v = week.vector(card["id"])
    if v is None:
        return []
    on_topic = dict(past.nearest(topic, len(past)))
    both: dict[str, float] = {}
    for i, s in past.nearest(v, 400):
        c = past.cluster[i]
        if s < SAME_STORY:
            break
        if c != card["id"] and c not in used and on_topic.get(i, 0) >= search.MIN_SIMILARITY:
            both[c] = max(both.get(c, -1.0), min(s, on_topic[i]))
    picked = sorted(both, key=both.get, reverse=True)[:TRACKED]
    return sorted(store.cards_by_id(conn, picked), key=lambda c: c["date"])


def _indexes(conn, day: date) -> tuple[search.Index, search.Index]:
    """The week's stories, and those of the HISTORY days before it, ready to search."""
    since, until = last_week(day)
    week = search.Index(conn, since, until)
    return week, search.Index(conn, since - timedelta(days=HISTORY), since, mean=week.mean)


def _section(conn, topic: str, week: search.Index, past: search.Index, shown: set[str] = frozenset(),
             threaded: set[str] = frozenset()) -> dict:
    """One topic: its stories that week (none `shown` already), the lead first, and the earlier stories on it."""
    found = [c for c in search.search(conn, topic, week.since, week.until, k=PER_TOPIC + len(shown), index=week)
             if c["id"] not in shown][:PER_TOPIC]
    if found:  # the lead: the most widely reported of the best few (the best answer, if none was reported more)
        lead = max(found[:LEAD_FROM], key=_outlets)
        found = [lead, *(c for c in found if c is not lead)]
    for c in found[:THREADED]:
        c["earlier"] = earlier(conn, c, week, past, week.query(topic), threaded)
    return {"topic": topic, "cards": found}


# ---------- Readers' interests, worked out once a week and kept per interest ----------

INTEREST_MAX = 150  # characters in one interest
SCHEMA = """
CREATE TABLE IF NOT EXISTS dossiers (
    id    TEXT NOT NULL,  -- interest_id(key, interest)
    week  TEXT NOT NULL,  -- the Monday it starts
    topic TEXT NOT NULL,  -- the interest, as the reader wrote it
    count INTEGER NOT NULL,
    html  TEXT NOT NULL,  -- its section of the dossier (_body)
    PRIMARY KEY (id, week)
);
"""


def clean_interest(text) -> str:
    """An interest as kept: spaces tidied, at most INTEREST_MAX characters; "" if it has no words to search."""
    t = re.sub(r"\s+", " ", str(text or "")).strip()[:INTEREST_MAX].strip()
    return t if search.words(t) else ""


def interest_id(key: str, interest: str) -> str:
    """The interest's id: a keyed hash (HMAC-SHA256) of it, so its file name says nothing about it and can't be
    guessed without the key. The same interest, however capitalised, has one id."""
    return hmac.new(key.encode("utf-8"), clean_interest(interest).lower().encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def prepare(conn, interests: list[str], key: str, day: date, log=print) -> int:
    """The week's section for each distinct interest, kept in table `dossiers`; earlier weeks' are dropped.
    Returns how many interests were worked out."""
    conn.executescript("DROP TABLE IF EXISTS dossiers;" + SCHEMA)  # made afresh each run, so always in today's shape
    since, _ = last_week(day)
    distinct = {}
    for i in interests:
        t = clean_interest(i)
        if t:
            distinct.setdefault(interest_id(key, t), t)
    week, past = _indexes(conn, day) if distinct else (None, None)
    rows = []
    for id_, topic in distinct.items():
        sec = _section(conn, topic, week, past)
        rows.append((id_, since.isoformat(), topic, len(sec["cards"]), _body(sec)))
    conn.executemany("INSERT INTO dossiers (id, week, topic, count, html) VALUES (?, ?, ?, ?, ?)", rows)
    conn.commit()
    log(f"dossiers: {len(rows)} interests for the week of {since.isoformat()}")
    return len(rows)


def kept(conn, day: date) -> dict[str, dict]:
    """The dossier sections kept for the week (last_week(day)), by id: {topic, count, html}."""
    conn.executescript(SCHEMA)
    since, _ = last_week(day)
    return {r[0]: {"topic": r[1], "count": r[2], "html": r[3]} for r in conn.execute(
        "SELECT id, topic, count, html FROM dossiers WHERE week = ?", (since.isoformat(),))}


SAMPLES = 3  # sample questions on the dossier page: the first two to try, all three as the boxes' examples


def samples(conn, index: search.Index, k: int = SAMPLES) -> list[str]:
    """Sample questions for the dossier page, from the week's own stories, never readers' questions: the most
    reported topic (one word), company and place that week, as a reader might ask about them ("AI safety",
    "What Nvidia is building", "AI rules in China"), taking turns between the three kinds; one is kept only
    if the dossier's search finds at least 3 stories for it that week."""
    from .preferences import group_of
    counts: dict[str, Counter] = {"Topics": Counter(), "Companies": Counter(), "Places": Counter()}
    for (tags,) in conn.execute("SELECT tags FROM items WHERE id = cluster AND date >= ? AND date < ?",
                                (index.since.isoformat(), index.until.isoformat())):
        for t in filter(None, (tags or "").split(",")):
            if (g := group_of(t)) in counts:
                counts[g][t] += 1
    streams = {w.lower() for name in search.STREAM_WORDS.values() for w in name.split()}  # "Research" is a stream
    phrase = {"Topics": lambda t: f"AI {t.lower()}" if " " not in t and "&" not in t and t.lower() not in streams else None,
              "Companies": lambda t: f"What {t} is building",
              "Places": lambda t: f"AI rules in {'the ' if t.startswith('United') else ''}{t}"}
    ranked = {g: [q for t, _ in c.most_common(6) if (q := phrase[g](t))] for g, c in counts.items()}
    out, turn = [], 0
    while len(out) < k and any(ranked.values()):
        g = ("Topics", "Companies", "Places")[turn % 3]
        turn += 1
        while ranked[g]:
            q = ranked[g].pop(0)
            if len(search.search(conn, q, index.since, index.until, k=3, index=index)) >= 3:
                out.append(q)
                break
    return out


def publish_vectors(conn, out, day: date) -> int:
    """Last week's story vectors as the site's dossier/week.json, for the dossier page (ask.html) to answer a new
    question at once, in the reader's browser, by meaning as search.search does: each story's card, and its vector
    with the shared direction taken out (search.Index) as int8 (x127, base64), with that direction (`mean`) for
    the question's; and the HISTORY days before the week as dossier/month.json, for its "Dig deeper" (the page
    loads it only then). Without the model's vectors, nothing is written. Returns how many stories of the week."""
    import base64
    from pathlib import Path
    import numpy as np
    from . import embed
    since, until = last_week(day)
    week = search.Index(conn, since, until)
    if not len(week):
        return 0
    folder = Path(out) / "dossier"
    folder.mkdir(parents=True, exist_ok=True)
    def write(name: str, index: search.Index, **more) -> None:
        q = np.clip(np.round(index.matrix * 127), -127, 127).astype(np.int8)
        (folder / name).write_text(json.dumps(
            {"model": embed.MODEL, "query": embed.QUERY, "from": index.since.isoformat(),
             "to": (index.until - timedelta(days=1)).isoformat(), "until": index.until.isoformat(), **more,
             "cards": [index.cluster[i] for i in index.ids], "mean": [round(float(x), 5) for x in index.mean],
             "vec": base64.b64encode(q.tobytes()).decode("ascii")}, separators=(",", ":")), encoding="utf-8")
    write("week.json", week, samples=samples(conn, week))
    write("month.json", search.Index(conn, since - timedelta(days=HISTORY), since, mean=week.mean))
    return len(week)


def publish(conn, out, day: date) -> int:
    """The kept sections as the site's dossier/<id>.json files; returns how many."""
    from pathlib import Path
    since, until = last_week(day)
    folder = Path(out) / "dossier"
    rows = kept(conn, day)
    if rows:
        folder.mkdir(parents=True, exist_ok=True)
    for id_, row in rows.items():
        (folder / f"{id_}.json").write_text(json.dumps(
            {"topic": row["topic"], "count": row["count"], "html": row["html"], "from": since.isoformat(),
             "to": (until - timedelta(days=1)).isoformat()}, separators=(",", ":")), encoding="utf-8")
    return len(rows)


def note(conn, key: str, interests: list[str], day: date) -> dict | None:
    """For the Sunday email (the day it covers, `day`, is a Saturday): the reader's interests that have a dossier
    section for that week (Monday to Saturday), with their counts and the link; None if none has one yet."""
    ready = kept(conn, day + timedelta(days=1))
    entries = [{"topic": t, "count": ready[i]["count"]} for t in interests
               if (i := interest_id(key, t)) in ready and clean_interest(t)][:TOPICS]
    if not entries:
        return None
    since, until = last_week(day + timedelta(days=1))
    end = until - timedelta(days=1)
    return {"link": link(key, interests), "week": f"{since.day} {since:%b} – {end.day} {end:%b}", "entries": entries}


def link(key: str, interests: list[str]) -> str:
    """A reader's link to their dossier: the ids of their interests only."""
    ids = [interest_id(key, t) for t in interests if clean_interest(t)][:TOPICS]
    return f"{rss.SITE}dossier.html#" + ".".join(dict.fromkeys(ids))


def _when(d: str) -> str:
    """"2026-09-28" -> "28 Sep"."""
    day = date.fromisoformat(d)
    return f"{day.day} {day:%b}"


def who_and_where(cards: list[dict], topic: str) -> tuple[list[str], list[str]]:
    """The companies and people, and the places, a topic's stories are tagged with (grouped as the site's
    filters group them), most often first; not what the topic itself names."""
    from .preferences import group_of  # it builds on the digest, as this module does
    asked = set(search.words(topic))
    names, places = Counter(), Counter()
    for c in cards:
        for t in story_tags(c):
            if set(search.words(t)) <= asked:
                continue
            group = group_of(t)
            if group == "Places":
                places[t] += 1
            elif group in ("Companies", "People"):
                names[t] += 1
    return [t for t, _ in names.most_common(NAMES)], [t for t, _ in places.most_common(PLACES)]


def _stream(c: dict) -> str:
    """The digest's stream key for a card's category (the Releases stream is stored as "tool")."""
    return "releases" if c["category"] == "tool" else c["category"]


def _by(c: dict) -> str:
    more = _outlets(c) - 1
    return c["source"] + (f" +{more} outlet{'s' if more > 1 else ''}" if more else "")


# The daily email's look (digest.py): Arial, its ink, greys and blue
PAPER, INK, MUTED, LINE, ACCENT = "#f4f6fa", DIGEST_INK, GREY, "#e3e5e8", HEADLINE
SERIF = SANS = "Arial,Helvetica,sans-serif"


def _kicker(words: str) -> str:
    return (f'<div style="font-family:{SANS};font-size:10.5px;font-weight:bold;letter-spacing:2px;text-transform:uppercase;'
            f'color:{ACCENT};margin:0 0 8px">{escape(words)}</div>')


def _pill(t: str) -> str:
    return (f'<span style="display:inline-block;margin:0 6px 6px 0;padding:3px 9px;border:1px solid {INK};border-radius:12px;'
            f'font-family:{SANS};font-size:12px;color:{INK}">{escape(t)}</span>')


def _link(c: dict, size: int, weight: str = "bold") -> str:
    return (f'<a href="{escape(c["url"])}" style="color:{INK};text-decoration:none;font-family:{SERIF};font-size:{size}px;'
            f'font-weight:{weight};line-height:1.3">{escape(c["title"])}</a>')


def _meta(words: str) -> str:
    return f'<div style="font-family:{SANS};font-size:11.5px;color:{MUTED};margin-top:4px">{escape(words)}</div>'


def _chip(c: dict) -> str:
    """A story's kind as a small chip in its stream's colours ("Policy", "Proposal · Brazil")."""
    label, bg, fg = tag(c, _stream(c))
    return (f'<span style="display:inline-block;padding:1px 8px;border-radius:10px;background:{bg};color:{fg};'
            f'font-family:{SANS};font-size:10.5px;font-weight:bold;line-height:1.6">{escape(label)}</span>')


def _event(c: dict, lead: bool = False) -> str:
    """One story as an event card: its date as a calendar block, then its kind, headline, a line or two of the
    publisher's summary and who reported it. The lead has an accent edge and more of its summary."""
    on = date.fromisoformat(c["date"])
    summary = _short(c.get("summary") or "", 320 if lead else 160)
    edge = f"border-left:4px solid {ACCENT}" if lead else f"border-left:1px solid {LINE}"
    return (f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;'
            f'background:#ffffff;border:1px solid {LINE};{edge};margin:0 0 10px"><tr>'
            f'<td width="60" align="center" valign="top" style="padding:12px 4px;background:{PAPER};border-right:1px solid {LINE};'
            f'font-family:{SANS}"><div style="font-size:10px;font-weight:bold;letter-spacing:1px;color:{MUTED}">'
            f'{f"{on:%a}".upper()}</div><div style="font-family:{SERIF};font-size:22px;font-weight:bold;line-height:1.15;color:{INK}">{on.day}</div>'
            f'<div style="font-size:11px;color:{MUTED}">{on:%b}</div></td>'
            f'<td valign="top" style="padding:11px 14px 12px">'
            + (f'<span style="font-family:{SANS};font-size:10.5px;font-weight:bold;letter-spacing:1.5px;color:{ACCENT};'
               f'margin-right:6px">THE LEAD</span>' if lead else "")
            + _chip(c) + f'<div style="margin-top:5px">{_link(c, 19 if lead else 16)}</div>'
            + (f'<div style="font-family:{SANS};font-size:13.5px;line-height:1.45;color:#4a4f57;margin-top:5px">'
               f'{escape(summary)}</div>' if summary else "")
            + _meta(_by(c)) + '</td></tr></table>')


def _body(sec: dict) -> str:
    """A topic's section of the dossier: who and where, the lead, then the rest of the week, each story an event
    card; then, closed, an arrow to dig deeper into the earlier stories on it."""
    cards, topic = sec["cards"], sec["topic"]
    html = []
    if not cards:
        return (f'<p style="font-family:{SANS};font-size:14px;color:{MUTED};margin:0">'
                f'Nothing on this topic this week.</p>')
    names, places = who_and_where(cards, topic)
    row = lambda head, tags: (f'<tr><td width="64" valign="top" style="padding-top:4px;font-family:{SANS};font-size:10.5px;'
                              f'font-weight:bold;letter-spacing:1.5px;color:{MUTED}">{head}</td>'
                              f'<td>{"".join(_pill(t) for t in tags)}</td></tr>')
    if names or places:
        html.append('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;'
                    'margin-bottom:14px">' + (row("WHO", names) if names else "") + (row("WHERE", places) if places else "")
                    + '</table>')
    lead, rest = cards[0], cards[1:]
    line = lambda c, n: _short(c.get("summary") or "", n)
    html.append(_event(lead, lead=True))
    if rest:
        html.append(f'<div style="margin:22px 0 10px">{_kicker("The rest of the week")}</div>'
                    + "".join(_event(c) for c in sorted(rest, key=lambda c: c["date"])))
    # The month before: never on the dossier itself (it is the week's), only behind an arrow to dig deeper
    older = sorted(lead.get("earlier") or [], key=lambda e: e["date"], reverse=True)
    if older:
        many = f"{len(older)} earlier {'story' if len(older) == 1 else 'stories'} on this in the month before"
        step = lambda e: (
            f'<tr><td width="74" valign="top" style="padding:0 0 12px;font-family:{SANS};font-size:12px;color:{MUTED};'
            f'white-space:nowrap">{escape(_when(e["date"]))}</td><td valign="top" style="padding:0 0 12px">{_link(e, 14)}'
            + (f'<div style="font-family:{SANS};font-size:12.5px;line-height:1.4;color:#4a4f57;margin-top:2px">'
               f'{escape(line(e, 110))}</div>' if e.get("summary") else "")
            + f'<div style="font-family:{SANS};font-size:11px;color:{MUTED};margin-top:2px">{escape(e["source"])}</div></td></tr>')
        months: dict[str, list[dict]] = {}
        for e in older:
            months.setdefault(e["date"][:7], []).append(e)
        html.append(f'<details style="margin:6px 0 4px"><summary style="cursor:pointer;list-style:none;font-family:{SANS};'
                    f'font-size:14px;font-weight:bold;color:{LINK}">Dig deeper ↓ <span style="font-weight:normal;font-size:12px;'
                    f'color:{MUTED}">{escape(many)}</span></summary>'
                    + "".join(f'<div style="font-family:{SANS};font-size:10.5px;font-weight:bold;letter-spacing:1.5px;'
                              f'text-transform:uppercase;color:{MUTED};margin:14px 0 8px">'
                              f'{date.fromisoformat(m + "-01"):%B %Y}</div>'
                              '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                              'style="border-collapse:collapse">' + "".join(step(e) for e in es) + '</table>'
                              for m, es in months.items())
                    + '</details>')
    return "".join(html)
