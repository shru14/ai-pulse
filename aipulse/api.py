"""What we built as JSON, at api/v1/<name>.json: the rows each feature page draws, the monthly issues and their
numbers, and the daily and weekly emails' picks, one file each.

Unlisted: nothing on the site links here, the sitemap leaves it out and robots.txt asks search engines not to read it.
Only what we built (the hand-checked lists and what we worked out from the stories), never the raw stream: a row
keeps the story's link, outlet, date and headline as its page shows them, and drops long text written by others
(abstracts, incident summaries). A new feature adds one line to ENDPOINTS.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from . import (compute, consultations, court, digest, echoes, glossary, harms, infra_watch, insights, jobs,
               lab_timelines, money, monthly, new_tests, owners, pacts, press, promises, release_cards, retired, rss,
               safety, standards, topics)
from . import today as board

PATH = "api/v1/"
# others' long text, our own matching patterns, and a story's internals (its id, cluster, other outlets' versions)
DROP = {"abstract", "summary", "words", "id", "cluster", "also", "added_at", "authors", "category", "lifecycle"}


def _clean(x):
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items() if k not in DROP}
    if isinstance(x, list):
        return [_clean(v) for v in x]
    return x


def _urls(cards: list[dict]) -> set[str]:
    return {s["url"] for c in cards for s in [c, *(c.get("also") or [])]}


def _infra(table, names):
    return lambda conn, cards, today: [{"url": r["url"], **dict(zip(names, r["cells"])), "date": r["date"],
                                        "source": r["source"], "title": r["title"]}
                                       for r in infra_watch._with_stories(table, cards)]


def _pacts(conn, cards, today):
    have = _urls(cards)
    return {"pledges": [{"name": p[0], "when": p[1], "url": p[2], "source": p[3], "signed": list(p[4]),
                         "joined_later": p[5]} for p in pacts._pledges()],
            "deals": [{"date": d, "government": g, "company": c, "what": w, "url": u}
                      for d, g, c, w, u in pacts.DEALS if u in have],
            "bans": [{"date": b[0], "government": b[1], "company": b[2], "what": b[3], "url": b[4],
                      "ended": b[5] or "", "ended_url": b[6] or "", "how_ended": b[7] or ""}
                     for b in pacts.BANS if b[4] in have],
            "orders": [{"date": d, "government": g, "company": c, "kind": k, "what": w, "url": u}
                       for d, g, c, k, w, u in pacts.ORDERS if u in have]}


def _saved(module):
    return lambda conn, cards, today: [r for v in module.load(conn).values() for r in v.get("rows", [])]


def _by_month(cards: list[dict]) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = {}
    for c in cards:
        by.setdefault((c.get("date") or "")[:7], []).append(c)
    return by


def _monthly(conn, cards, today):
    """Each monthly issue: its summary, the 10 stories that mattered most, the rules that moved, the storylines."""
    by = _by_month(cards)
    storylines = {slug: topics.events(slug, cards) for slug in topics.TOPICS}
    laws = [c for c in cards if c.get("lifecycle") or (c.get("bill") or "").startswith(standards.MARK)]
    monthly.connect(conn)
    summaries = {r[0]: r[1] for r in conn.execute("SELECT month, summary FROM monthly")}
    out = []
    for m in [m for m in monthly.months(today) if by.get(m)]:
        d = monthly.issue(m, by[m], storylines, laws)
        out.append({"month": m, "name": monthly.name(m), "number": monthly.number(m),
                    "page": f"{rss.SITE}{monthly.path(m)}", "in_brief": summaries.get(m) or "", "top": d["top"],
                    "rules": [{k: v for k, v in r.items() if k != "flag"} for r in d["rules"]],
                    "storylines": d["storylines"]})
    return out


def _money(r: dict) -> dict:
    return {k: v for k, v in r.items() if k != "text"}  # the story's own words


def _insights(conn, cards, today):
    """Each month in numbers, as its insights page draws them, every number named for what it counts."""
    by = _by_month(cards)
    issues = [m for m in monthly.months(today) if by.get(m)]
    ledger = {m: money.month(cs) for m, cs in by.items() if m and m <= issues[-1]} if issues else {}
    out = []
    for m in issues:
        x = insights.numbers(m, by, ledger)
        f = x["money"]
        out.append({
            "month": m, "page": f"{rss.SITE}{insights.path(m)}",
            "stories_each_day": [{"date": d.isoformat(), "stories": n} for d, n in x["daily"]],
            "busiest_days": [{"date": p["day"], "stories": p["n"], "times_a_usual_day": p["x"],
                              "weekend": p["weekend"], "top_stories": p["stories"]} for p in x["peaks"]],
            "stream_share_of_stories": [{"stream": s, "by_month": [{"month": mm, "share": round(v, 4)} for mm, v in t]}
                                        for s, t in x["shares"]],
            "companies_named": [{"company": t, "stories": n, "stories_last_month": n0} for t, n, n0 in x["companies"]],
            "places_named": [{"place": t, "stories": n, "stories_last_month": n0} for t, n, n0 in x["places"]],
            "places_named_count": x["nplaces"],
            "themes_rising": [{"theme": t, "stories": n, "usual_stories_3_months_before": round(u, 1)}
                              for t, n, u in x["rise"]],
            "themes_fading": [{"theme": t, "stories": n, "usual_stories_3_months_before": round(u, 1)}
                              for t, n, u in x["fade"]],
            "money": {"funding_rounds": f["rounds"], "raised_usd": f["raised"],
                      "biggest_round": f["biggest"] and _money(f["biggest"]),
                      "rounds_by_theme": [{"theme": t, "rounds": n, "raised_usd": v, "usual_rounds_3_months_before": round(u, 1)}
                                          for t, n, v, u in f["themes"]],
                      "valuations": [_money(dict(r, before=r["before"] and {"valuation_usd": r["before"][0],
                                                                             "month": r["before"][1]}))
                                     for r in f["ladder"]],
                      "acquisitions_and_compute_deals": [_money(r) for r in f["deals"]],
                      "compute_deals_this_year": {"deals": f["compute_year"][0], "amount_usd": f["compute_year"][1]}},
            "open_weight_models_by_lab": dict(x["opens"]),
            "us_vs_china": [{"what": w, "us": us, "china": cn,
                             "china_share_by_month": [{"month": mm, "share": round(v, 4)} for mm, v in t]}
                            for w, us, cn, t in x["rivals"]],
            "legal_and_risk": [{"company": co, "court_stories": a, "regulator_stories": b, "incidents": c}
                               for co, a, b, c in x["exposure"]],
            "funding_pace": [{"month": mm, "rounds": n, "raised_usd": v, "biggest_round_usd": b, "biggest_round_company": co}
                             for mm, n, v, b, co in x["pace"]],
            "ipo_watch": {"headlines_by_month": [{"month": mm, "headlines": n} for mm, n in x["ipo"]["trend"]],
                          "stories": x["ipo"]["stories"]}})
    return out


def _word(e: dict, story: dict | None) -> dict:
    return {"term": e["term"], "meaning": e["def"], "glossary": f"{rss.SITE}glossary/{e['id']}/",
            **({"story": monthly._story(story)} if story else {})}


DAYS = 30  # days in daily.json
WEEKS = 12  # weeks in weekly.json


def _daily(conn, cards, today):
    """The daily email's picks for each of the last DAYS days, as every reader with no choices gets them: the stories
    that mattered most and the word of the day."""
    streams = list(rss.FEEDS)
    out = []
    for k in range(DAYS, 0, -1):
        day = today - timedelta(days=k)
        by = digest.by_streams(cards, streams, day)
        todays = [c for n in streams for c in by[n]]
        if not todays:
            continue
        top = digest.top_stories(todays)
        e, story = digest.word_of_the_day(cards, day, streams, None, [digest._biggest(by, streams), top, todays])
        out.append({"date": day.isoformat(), "page": f"{rss.SITE}daily/{day.isoformat()}.html", "stories": len(todays),
                    "top": [monthly._story(c) for c in top], "word_of_the_day": _word(e, story)})
    return out


def _weekly(conn, cards, today):
    """The Sunday email's week for each of the last WEEKS weeks (Monday to Saturday): its story and word."""
    by_id = {e["id"]: e for e in glossary.ENTRIES}
    last = today - timedelta(days=(today.weekday() - digest.WEEKLY) % 7 or 7)  # the last Saturday that is over
    out = []
    for k in range(WEEKS - 1, -1, -1):
        day = last - timedelta(weeks=k)
        monday, days = digest._span(day)
        story = digest._week_story(cards, day)
        if not story:
            continue
        wid = digest._week_word(cards, day)
        out.append({"from": monday.isoformat(), "to": day.isoformat(),
                    "stories": sum(1 for c in cards if (c.get("date") or "") in days and c.get("category") in digest._STREAMS),
                    "story_of_the_week": monthly._story(story),
                    "word_of_the_week": _word(by_id[wid], None) if wid in by_id else None})
    return out


def _today(conn, cards, today):
    """Today in AI's leaderboard: each story's rank now, at the day's first run and at its best today."""
    p = board.payload(conn, cards, today)
    by_id = {c["id"]: c for c in cards}
    loud = board.buzz(cards, today)
    return [{"rank": i + 1, "rank_at_first_run": p["start"].get(cid), "best_rank_today": p["peak"].get(cid),
             "stories_naming_the_same_thing_30_days": loud.get(cid, 0), **monthly._story(by_id[cid])}
            for i, cid in enumerate(p["ids"])]


# name: (title, its page, what a row is, the rows); the order of api/v1/index.json
ENDPOINTS = {
    "court": ("AI in court", court.PATH, "a lawsuit against an AI maker, with its steps",
              lambda conn, cards, today: court.cases(cards)),
    "safety": ("AI safety hub", safety.PATH, "a safety document: system card, evaluation, red-teaming or framework",
               lambda conn, cards, today: safety.docs()),
    "pacts": ("AI pacts and orders", pacts.PATH, "pledges, deals, bans and orders between governments and AI companies",
              _pacts),
    "consultations": ("AI consultations", consultations.PATH, "a government consultation that names AI",
                      _saved(consultations)),
    "jobs": ("Jobs blamed on AI", jobs.PATH, "a job cut the news linked to AI, with the reason the company gave",
             lambda conn, cards, today: jobs.cuts(cards)),
    "owners": ("Who owns a piece of whom", owners.PATH, "a company's stake in an AI lab",
               lambda conn, cards, today: owners.deals(cards)),
    "promises": ("Promised vs shipped", promises.PATH, "a company's promise and whether it shipped",
                 lambda conn, cards, today: promises.promises(cards, today)),
    "release-cards": ("Release cards", release_cards.PATH, "a major model release: weights, licence, price",
                      lambda conn, cards, today: release_cards.rows()),
    "lab-timelines": ("Lab timelines", lab_timelines.PATH, "a lab's release, price change, new place or shutdown",
                      lambda conn, cards, today: lab_timelines.events(retired.load(conn), today)),
    "models-being-retired": ("Models being retired", retired.PATH, "a model a lab has set a shut-down date for",
                             _saved(retired)),
    "new-tests": ("New tests for AI", new_tests.PATH, "a new benchmark and the best result its paper reports",
                  lambda conn, cards, today: new_tests.tests(cards)),
    "papers-in-the-news": ("Papers that made the news", press.PATH, "a research paper and the story that reported it",
                           lambda conn, cards, today: press.papers(cards)),
    "compute": ("Compute behind notable models", compute.PATH, "Epoch AI's training-compute estimate for a model",
                lambda conn, cards, today: compute.load(conn).get("rows", [])),
    "data-centre-builds": ("Data-centre builds", "data-centre-builds/", "a data-centre project",
                           _infra(infra_watch.BUILDS, ("who", "country", "place", "size", "money", "stage"))),
    "who-powers-ai": ("Who powers AI", "who-powers-ai/", "a deal to power data centres",
                      _infra(infra_watch.POWER, ("who", "power", "what", "size", "status"))),
    "pushback-and-permits": ("Pushback & permits", "pushback-and-permits/", "a decision on a data centre",
                             _infra(infra_watch.DECISIONS, ("country", "place", "by", "what", "outcome"))),
    "harm-to-rule": ("Harm → rule", harms.PATH, "a subject, with the AI harms logged and the rules on it",
                     lambda conn, cards, today: harms.subjects(cards)),
    "rule-echoes": ("Rule echoes", echoes.PATH, "a subject AI laws come back to, and the places that took it up",
                    lambda conn, cards, today: echoes.echoes(cards)),
    "glossary": ("Glossary", "glossary/", "a word, in plain words",
                 lambda conn, cards, today: glossary.payload(cards, today)["entries"]),
    "monthly": ("The month in AI", "monthly/", "a monthly issue: summary, top 10, rules that moved, storylines",
                _monthly),
    "monthly-insights": ("Monthly insights", "monthly/", "a month in numbers", _insights),
    "daily": ("Daily email", "daily/", f"a day of the last {DAYS}: the stories that mattered most and the word of the day",
              _daily),
    "weekly": ("Weekly email", "daily/", f"a week of the last {WEEKS}: the story and the word of the week", _weekly),
    "today": ("Today in AI", "today/", "a story on today's leaderboard, with its rank", _today),
}


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write api/v1/: a file per feature and index.json listing them. Returns nothing: no page for the sitemap."""
    (out / PATH).mkdir(parents=True, exist_ok=True)
    listed = []
    for name, (title, page, row, rows) in ENDPOINTS.items():
        found = _clean(rows(conn, cards, today))
        n = sum(len(v) for v in found.values()) if isinstance(found, dict) else len(found)
        (out / PATH / f"{name}.json").write_text(json.dumps(
            {"name": name, "title": title, "page": f"{rss.SITE}{page}", "row": row, "updated": today.isoformat(),
             "count": n, "rows": found}, separators=(",", ":"), ensure_ascii=False, default=str), encoding="utf-8")
        listed.append({"name": name, "title": title, "url": f"{rss.SITE}{PATH}{name}.json", "count": n})
    (out / PATH / "index.json").write_text(json.dumps({"updated": today.isoformat(), "endpoints": listed},
                                                      separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return []
