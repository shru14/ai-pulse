"""Company of the day and Company of the week, in the daily email: one AI startup a day that stood out for its idea,
its revenue or how it makes money, and on Sunday the week's most reported of them.

Rules find the startups (candidates): a story from our own feeds that reports a closed funding round, a revenue figure or a new way of charging, about a company that isn't one of the big labs or big tech
firms (classify.COMPANY_TERMS) and wasn't featured in the last GAP days. Stories 2 or more outlets carried come
first; a day without one can take a one-outlet story. Rules can't say why a company is
interesting, so each profile is written and checked by hand against its story (the daily companies routine drafts
it on a companies/<day> branch; it goes in the email only once the owner merges it). Numbers are as the story gives
them, marked "reported" when they come from a news report rather than the company. A day with no approved profile
has no box: nothing is padded and no company comes back.

Launches on Hacker News (Show HN, Launch HN) with their points are a second list of candidates (launches), a sign of
early interest; a profile still needs a story to check it against.

The week's company is ranked, never scored: the most outlets that reported it Monday to Saturday, then the most
days it was in the news, then the latest story.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from . import classify, money

CHECKED_TO = "2026-11-23"  # stories up to this day are checked
GAP = 30  # days before a company can be featured again
REASONS = ("Concept", "Revenue", "Business model")  # why it's here

# One a day, checked by hand: (the day the email covers, company, what it does, how it makes money, the number as the
#  story gives it, why it's here (one of REASONS), the reason in one line, the story, its outlet)
PROFILES: list[tuple[str, str, str, str, str, str, str, str, str]] = [
    ("2026-11-16", "Noeri", "AI systems that keep improving as they learn from a company's own data and work.",
     "Built for companies to run on their own data; the story gives no prices.", "$110M raised at launch",
     "Concept", "AI that keeps learning after it is set up, rather than a model that stays fixed.",
     "https://siliconangle.com/2026/11/16/noeri-raises-110m-to-help-companies-build-living-ai-systems-that-self-improve-over-time/",
     "SiliconANGLE"),
    ("2026-11-17", "Model ML", "Agents that update bankers' and consultants' financial models and slides when a deal changes.",
     "Built for investment banks and consulting firms; the story gives no prices.", "$250M raised",
     "Business model", "Takes on the routine model and slide updates that junior bankers do by hand.",
     "https://techcrunch.com/2026/11/17/model-ml-raises-250m-to-automate-investment-banking-grunt-work/", "TechCrunch"),
    ("2026-11-18", "Humyn Labs", "Records people doing everyday tasks on its own cameras and labels the footage as robot training data.",
     "Built for AI labs, robotics companies and world-model developers (12 paying customers); the story gives no prices.",
     "$10M revenue between April and October, reported", "Revenue",
     "Founded in February, it reports revenue within months and has raised $47M in a Series A.",
     "https://techcrunch.com/2026/11/18/accel-backs-indias-humyn-labs-to-supply-training-data-needed-by-u-s-robotics-ai-developers/",
     "TechCrunch"),
    ("2026-11-19", "Disseqt AI", "Software that tests, watches and audits companies' AI systems, with records meant to satisfy rules like the EU AI Act.",
     "Built for large companies; the story gives no prices.", "$8M raised", "Concept",
     "As AI rules come into force, it sells the proof that a company's AI follows them.",
     "https://yourstory.com/2026/11/disseqt-ai-raises-8m-to-build-enterprise-ai-safeguards", "YourStory"),
]

# A company's official website, checked by hand, for the front page's tile and the email's company box
SITES: dict[str, str] = {
    "Humyn Labs": "https://humynlabs.ai/",
    "Disseqt AI": "https://disseqt.ai/",
}

# Stories checked and not picked (a big company's, a round still in talks, a pick already made that day)
LEFT_OUT: list[str] = [
    # Not a company's news: banks' policy on AI agents
    "https://techcrunch.com/2026/11/18/more-banks-says-customers-using-ai-agents-are-on-their-own-even-if-they-get-hacked/",
    # Talks only: Nvidia "nearing a deal" to acquire Inception, not a closed round
    "https://the-decoder.com/nvidia-bets-at-least-500-million-on-inceptions-diffusion-models-to-strengthen-its-open-source-nemotron-lineup/",
    # Not a company's news: Tracxn's totals for India's AI funding
    "https://yourstory.com/2026/11/india-ai-funding-nearly-doubles-jan-sept-2026-tracxn",
]

_REVENUE = re.compile(r"\b(revenue|ARR|annuali[sz]ed|run[- ]rate|profitab\w*|customers|subscribers|paying users)\b", re.I)
_MODEL = re.compile(r"\b(pricing|per[- ](?:task|outcome|seat|use|token)|usage[- ]based|outcome[- ]based|subscription|"
                    r"marketplace|pay[- ]as[- ]you[- ]go|business model|charges?)\b", re.I)
# "Nvidia bets at least $500 million on Inception's diffusion models": an investor's stake in a startup is its round
_STAKE = re.compile(r"\b(?i:bets|invests|puts|pours|stakes)\b[^$€£]{0,25}[$€£]\s?[\d.,]+\s*(?i:billion|million|bn|mn|[bm])?\b"
                    r"[^$€£]{0,20}?\b(?i:in|into|on)\s+([A-Z][\w.-]*(?:\s+[A-Z][\w.-]*)?)")
_NOT = re.compile(r"\b(in talks|talks to|seeks?|seeking|plans? to raise|is raising|reportedly raising|could|may)\b", re.I)


def _outlets(c: dict) -> int:
    return len({o.get("source") for o in [c, *(c.get("also") or [])] if o.get("source")})


def profiles() -> list[dict]:
    keys = ("day", "name", "does", "money", "number", "why", "because", "url", "source")
    return [{**dict(zip(keys, p)), "site": SITES.get(p[1])} for p in PROFILES]


def of_day(day: date) -> dict | None:
    """The approved profile for the day the email covers, or None (no box that day)."""
    return next((p for p in profiles() if p["day"] == day.isoformat()), None)


def _named(name: str) -> re.Pattern:
    return re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")


def reach(name: str, cards: list[dict], days: list[str]) -> tuple[int, int, str]:
    """How the week's stories carried a company: (outlets that reported it, days it was in the news, latest day)."""
    pat, outlets, seen = _named(name), set(), set()
    for c in cards:
        d = (c.get("date") or "")[:10]
        if d not in days:
            continue
        for o in [c, *(c.get("also") or [])]:
            if pat.search(o.get("title") or "") or (o is c and pat.search(c.get("summary") or "")):
                outlets.add(o.get("source"))
                seen.add(d)
    outlets.discard(None)
    return len(outlets), len(seen), max(seen, default="")


def of_week(cards: list[dict], saturday: date) -> tuple[dict, int, int, int, str] | None:
    """The week's company (Monday to `saturday`): of the week's daily picks, the most outlets that reported it, then
    the most days in the news, then the latest. Returns (profile, outlets, days, how many picks it was chosen from,
    what put it first: "only", "outlets", "days" or "latest")."""
    monday = saturday - timedelta(days=saturday.weekday())
    return _ranked(cards, [(monday + timedelta(days=k)).isoformat() for k in range((saturday - monday).days + 1)])


def front(cards: list[dict], today: date) -> dict:
    """startup.json, for the front page's Startup of the week tile: the last finished week (Monday to Saturday), the
    same pick as that Sunday's email, so the tile changes once a week, on Sunday (owner, 2026-11-19). Until a finished
    week has picks, this week so far. None: no tile."""
    saturday = today - timedelta(days=(today.weekday() - 5) % 7 or 7)
    got = of_week(cards, saturday)
    if not got:
        saturday = min(saturday + timedelta(days=7), today)
        got = of_week(cards, saturday)
    keys = ("name", "does", "number", "why", "url", "source", "site")
    return {"from": (saturday - timedelta(days=saturday.weekday())).isoformat(), "to": saturday.isoformat(),
            "startup": got and {k: got[0][k] for k in keys}}


def _ranked(cards: list[dict], days: list[str]) -> tuple[dict, int, int, int, str] | None:
    picks = [p for p in profiles() if p["day"] in days]
    if not picks:
        return None
    ranked = sorted(((reach(p["name"], cards, days), p) for p in picks), key=lambda r: (*r[0], r[1]["day"]), reverse=True)
    (outlets, seen, _), best = ranked[0]
    if len(ranked) == 1:
        rule = "only"
    else:
        (o2, s2, _), _ = ranked[1]
        rule = "outlets" if outlets > o2 else "days" if seen > s2 else "latest"
    return best, outlets, seen, len(picks), rule


def why_week(outlets: int, seen: int, picks: int, rule: str) -> str:
    """The line that says why the week's company came first, in plain words."""
    n = f"{outlets} outlet{'s' * (outlets != 1)}"
    d = f"{seen} day{'s' * (seen != 1)}"
    return {"only": f"The only company of the day this week; reported by {n}.",
            "outlets": f"Reported by {n} this week, more than any of the week's other {picks - 1} companies of the day.",
            "days": f"Level on outlets ({n}) with another, and in the news on more days ({d}).",
            "latest": f"Level with another on outlets ({n}) and days ({d}); its story is the latest."}[rule]


def _company(c: dict) -> str:
    if not money.read(c) and (m := _STAKE.search(c.get("title") or "")):
        return m.group(1)
    r = money.read(c)
    return (r or {}).get("company") or money.subject(c.get("title") or "")


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Stories after CHECKED_TO (or `since`, if later) that may hold the day's startup: a closed round, a revenue figure or a way of charging, not a big lab's or big tech's, no profile or LEFT_OUT has it, and a company
    not featured in the last GAP days. Newest first, the most reported first within a day (`outlets`)."""
    since = max(since, CHECKED_TO + "~")
    used = {p["url"] for p in profiles()} | set(LEFT_OUT)
    out = []
    for c in cards:
        if (c.get("date") or "") < since or c.get("category") in ("research", "regulation"):
            continue
        if any(o.get("url") in used for o in [c, *(c.get("also") or [])]):
            continue
        t = c.get("title") or ""
        r = money.read(c)
        what = ("round" if (r and r.get("kind") == "round") or (not r and _STAKE.search(t)) else "revenue" if _REVENUE.search(t)
                else "model" if _MODEL.search(t) else "")
        if not what or _NOT.search(t):
            continue
        name = _company(c)
        if not name or any(rx.search(name) for rx in classify._companies.values()):  # a big lab or big tech
            continue
        day = date.fromisoformat(c["date"][:10])
        if any(p["name"].lower() == name.lower() and 0 <= (day - date.fromisoformat(p["day"])).days < GAP for p in profiles()):
            continue
        out.append(dict(c, company=name, signal=what, outlets=_outlets(c)))
    return sorted(out, key=lambda c: (c["date"][:10], c["outlets"]), reverse=True)


def launches(social: dict, since: str = "") -> list[dict]:
    """AI startups launching on Hacker News (Show HN, Launch HN; social.py keeps them two weeks) after CHECKED_TO (or
    `since`, if later) that no profile or LEFT_OUT has, the most points first: a sign of early interest, to check
    against a story before any profile. `social` is the site's social.json (social.payload)."""
    since = max(since, CHECKED_TO + "~")
    used = {p["url"] for p in profiles()} | set(LEFT_OUT)
    rows = [dict(t, date=datetime.fromtimestamp(t["time"], timezone.utc).strftime("%Y-%m-%d %H:%M"))
            for t in social.get("launches") or []]
    return sorted([t for t in rows if t["date"] >= since and t["url"] not in used and t["hn"] not in used],
                  key=lambda t: t["points"], reverse=True)


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a companies/<day> branch: each profile it adds, and the stories it left out; None
    when it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("PROFILES", "LEFT_OUT"))
    rows = [(p["day"], p["name"], p["does"], p["money"], p["number"], f'{p["why"]}: {p["because"]}', p["url"])
            for p in profiles() if p["url"] not in had["PROFILES"]]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        was = re.search(r'^CHECKED_TO = "([\d-]+)"', base, re.M)
        return _quiet(branch, was.group(1)) if was and was.group(1) < CHECKED_TO else None
    return approve.note("Company of the day", f"profile{'s' * (len(rows) != 1)}", branch,
                        ("Day", "Company", "What it does", "How it makes money", "The number", "Why it's here", "Story"),
                        rows, dropped)


def _quiet(branch: str, since: str) -> tuple[str, str, str]:
    """The note for a day with no pick: the branch only moves CHECKED_TO on, so a quiet day isn't silence."""
    from html import escape
    line = (f"No company today: no startup story after {since} passed the checks, so there is no profile to approve. "
            f"Nothing needs merging (the branch {branch} only records the day as checked).")
    html = ('<!doctype html><html><body style="margin:0;padding:16px;font-family:Arial,Helvetica,sans-serif;'
            f'color:#1a1a1a"><p style="font-size:15px">{escape(line)}</p></body></html>')
    return "Pulse Central, Company of the day: none today", line, html
