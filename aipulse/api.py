"""What we built as JSON, at api/v1/<name>.json: the rows each feature page draws, the monthly issues and their
numbers, and the daily and weekly emails' picks, one file each.

For our own use, not published: the site's build leaves it out; `aipulse api --build` writes it on a PC, into FOLDER
(not in git). Only what we built (the hand-checked lists and what we worked out from the stories), never the raw stream: a row
keeps the story's link, outlet, date and headline as its page shows them, and drops long text written by others
(abstracts, incident summaries). A new feature adds one line to ENDPOINTS and its date field to DATES.

Asking for part of a file: query() keeps the rows between two dates (each file names its row date field) and those
whose fields match, the same way the query page (api/v1/index.html, QUERY_JS) does in the browser and `aipulse api`
does in the terminal.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

from . import (compute, consultations, court, digest, echoes, glossary, harms, infra_watch, insights, jobs,
               lab_timelines, money, monthly, new_tests, owners, pacts, press, promises, release_cards, retired, rss,
               safety, standards, topics)
from . import today as board

PATH = "api/v1/"
FOLDER = "api-data"  # where `aipulse api --build` writes (FOLDER/api/v1/), ignored by git
# others' long text, our own matching patterns, and a story's internals (its id, cluster, other outlets' versions)
DROP = {"abstract", "summary", "words", "id", "cluster", "also", "added_at", "authors", "category", "lifecycle",
        "match", "search", "case"}


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


def _month_of(when: str) -> str:
    """'Nov 2023' as '2023-11' (a row's month, for the date filter)."""
    return datetime.strptime(when, "%b %Y").strftime("%Y-%m")


def _pacts(conn, cards, today):
    """One list, each row's `type` saying which it is: pledge, deal, ban or order."""
    have = _urls(cards)
    return ([{"type": "pledge", "date": _month_of(p[1]), "name": p[0], "url": p[2], "source": p[3],
              "signed": list(p[4]), "joined_later": p[5]} for p in pacts._pledges()]
            + [{"type": "deal", "date": d, "government": g, "company": c, "what": w, "url": u}
               for d, g, c, w, u in pacts.DEALS if u in have]
            + [{"type": "ban", "date": b[0], "government": b[1], "company": b[2], "what": b[3], "url": b[4],
                "ended": b[5] or "", "ended_url": b[6] or "", "how_ended": b[7] or ""}
               for b in pacts.BANS if b[4] in have]
            + [{"type": "order", "date": d, "government": g, "company": c, "kind": k, "what": w, "url": u}
               for d, g, c, k, w, u in pacts.ORDERS if u in have])


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
               lambda conn, cards, today: [dict(r, month=_month_of(r["when"])) for r in owners.deals(cards)]),
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


# each file's row date: the field the from/to filter reads (YYYY-MM-DD, or YYYY-MM for a month); None: no row date
# (the rows are subjects, each holding its own dated lists)
DATES = {"court": "latest", "safety": "date", "pacts": "date", "consultations": "closes", "jobs": "date",
         "owners": "month", "promises": "date", "release-cards": "day", "lab-timelines": "day",
         "models-being-retired": "shuts", "new-tests": "date", "papers-in-the-news": "date", "compute": "date",
         "data-centre-builds": "date", "who-powers-ai": "date", "pushback-and-permits": "date", "harm-to-rule": None,
         "rule-echoes": None, "glossary": "added", "monthly": "month", "monthly-insights": "month", "daily": "date",
         "weekly": "to", "today": "date"}


def _text(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v)


def _matches(v, wanted: str) -> bool:
    """A field against a filter: any of its |-separated values, in any case. Text (or a list's item, or anything
    nested) contains it; a number or true/false equals it."""
    options = [w.strip().lower() for w in wanted.split("|") if w.strip()]
    items = v if isinstance(v, list) else [v]
    return any((o in _text(i).lower()) if isinstance(i, (str, dict, list)) else _text(i).lower() == o
               for i in items for o in options)


def _within(d: str, start: str, end: str) -> bool:
    """Is a row's date (a day, a month or a year) inside start..end (both kept)? A month counts if it overlaps."""
    return bool(d) and (not start or d >= start[:len(d)]) and (not end or d <= end[:len(d)])


def query(doc: dict, start: str = "", end: str = "", where: dict[str, str] | None = None, q: str = "",
          limit: int = 0) -> dict:
    """A file's rows from `start` to `end` (YYYY-MM-DD, either may be empty) whose fields match each `where`
    value and whose text contains `q`, the first `limit` (0: all). A row with no date is left out once a date is
    asked for. Keep in step with QUERY_JS."""
    field = doc.get("date_field")
    rows = doc["rows"]
    if (start or end) and field:
        rows = [r for r in rows if _within(str(r.get(field) or "")[:10], start, end)]
    for k, v in (where or {}).items():
        rows = [r for r in rows if _matches(r.get(k), v)]
    if q:
        rows = [r for r in rows if q.lower() in json.dumps(r, ensure_ascii=False).lower()]
    shown = rows[:limit] if limit else rows
    return {**{k: doc[k] for k in ("name", "title", "page", "row", "updated", "date_field") if k in doc},
            "asked": {"from": start, "to": end, "where": where or {}, "q": q, "limit": limit},
            "matched": len(rows), "count": len(shown), "rows": shown}


QUERY_JS = (Path(__file__).resolve().parent.parent / "templates" / "api-query.js").read_text(encoding="utf-8")


def query_page(conn, cards: list[dict]) -> str:
    """api/v1/index.html: pick a file, dates and filters; the link keeps them (?name=&from=&to=&where=field:value)."""
    from . import pages
    options = "".join(f'<option value="{n}">{escape(t[0])}</option>' for n, t in ENDPOINTS.items())
    body = ('<h1>AI Pulse data</h1>\n<p class="intro">Pick the data, the dates and any filters. The link keeps them, '
            'so it can be saved or shared. Each filter is <code>field:value</code> on its own line; <code>|</code> '
            'between values means either.</p>\n'
            '<form id="aq" class="aq">\n'
            f'<label>Data <select name="name"><option value="">Choose…</option>{options}</select></label>\n'
            '<label>From <input type="date" name="from"></label>\n<label>To <input type="date" name="to"></label>\n'
            '<label>Filters <textarea name="where" rows="2" placeholder="status:won&#10;where:Japan|Germany">'
            '</textarea></label>\n<label>Search <input type="search" name="q"></label>\n'
            '<label>At most <input type="number" name="limit" min="1" placeholder="all"></label>\n'
            '<button type="submit">Show</button>\n</form>\n'
            '<p class="meta" id="aq-fields"></p>\n<p class="meta" id="aq-meta"></p>\n'
            '<button type="button" id="aq-dl" hidden>Download JSON</button>\n<pre id="aq-out" class="aq-out"></pre>\n'
            '<style>.aq{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;align-items:end;'
            'margin:12px 0}.aq label{display:grid;gap:4px;font-size:13px;min-width:0}.aq textarea,.aq input,.aq select{font:inherit;'
            'padding:6px;border:1px solid #9aa0aa;border-radius:4px;background:transparent;color:inherit;width:100%;'
            'min-width:0;box-sizing:border-box}'
            '.aq-out{overflow:auto;max-height:70vh;padding:12px;border:1px solid #9aa0aa;border-radius:4px;'
            'font-size:12.5px;white-space:pre-wrap;word-break:break-word}</style>\n'
            f'<script>\n{QUERY_JS}</script>\n')
    html = pages.page("AI Pulse data · AI Pulse", "Ask the AI Pulse data files for dates and filters.", PATH, body,
                      {"@context": "https://schema.org", "@type": "WebPage", "name": "AI Pulse data"},
                      pages.frame(conn, len(cards)), ("/", "Back to AI Pulse"))
    return html.replace('<meta name="description"', '<meta name="robots" content="noindex">\n<meta name="description"', 1)


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write api/v1/: a file per feature, index.json listing them and the query page. Returns nothing: no page for
    the sitemap."""
    (out / PATH).mkdir(parents=True, exist_ok=True)
    listed = []
    for name, (title, page, row, rows) in ENDPOINTS.items():
        found = _clean(rows(conn, cards, today))
        (out / PATH / f"{name}.json").write_text(json.dumps(
            {"name": name, "title": title, "page": f"{rss.SITE}{page}", "row": row, "updated": today.isoformat(),
             "date_field": DATES[name], "count": len(found), "rows": found}, separators=(",", ":"),
            ensure_ascii=False, default=str), encoding="utf-8")
        listed.append({"name": name, "title": title, "url": f"{rss.SITE}{PATH}{name}.json", "count": len(found),
                       "date_field": DATES[name]})
    (out / PATH / "index.json").write_text(json.dumps({"updated": today.isoformat(), "endpoints": listed},
                                                      separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (out / PATH / "index.html").write_text(query_page(conn, cards), encoding="utf-8")
    return []


def build_local(conn, folder: str = FOLDER) -> int:
    """Write the files and the query page (with the site's styles and fonts) into `folder`. Returns how many files."""
    import shutil
    from datetime import timezone
    from . import pages, store
    from .server import EU_MEMBERS, TEMPLATE
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    cards, _ = store.cards(conn, limit=10**9, eu_members=EU_MEMBERS)
    build(conn, cards, out, datetime.now(timezone.utc).date())
    pages.write_css(out)
    shutil.copytree(TEMPLATE.parent / "fonts", out / "fonts", dirs_exist_ok=True)
    return len(ENDPOINTS)


def fetch(name: str, folder: str = FOLDER) -> dict:
    """A file from the local build (`aipulse api --build`)."""
    return json.loads((Path(folder) / PATH / f"{name}.json").read_text(encoding="utf-8"))
