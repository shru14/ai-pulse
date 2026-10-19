"""The features' data as JSON, at api/v1/<name>.json: the rows each feature page draws, one file per feature.

Unlisted: nothing on the site links here, the sitemap leaves it out and robots.txt asks search engines not to read it.
Only what we built (the hand-checked lists and what we worked out from the stories), never the raw stream: a row
keeps the story's link, outlet, date and headline as its page shows them, and drops long text written by others
(abstracts, incident summaries). A new feature adds one line to ENDPOINTS.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import (compute, consultations, court, echoes, glossary, harms, infra_watch, jobs, lab_timelines, new_tests,
               owners, pacts, press, promises, release_cards, retired, rss, safety)

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
