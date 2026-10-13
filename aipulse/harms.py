"""Harm → rule (harm-to-rule/): AI harms the AI Incident Database's editors confirmed since 2023, grouped by subject,
beside the Regulation tracker's official records on the same subject (the subjects of Rule echoes). Each subject is a
panel: a line of the harms logged so far, and each rule a dot on that line on the day it was proposed, coloured by
how far it got, so the dot's height is the harms that came before it. Opening a subject lists its rules, with how
many harms on the subject came before each, and its latest harms. A rule after harms is "followed by", never
"caused". Harms are matched by their editors' title only, with stricter words than the tracker's (an incident's
description names schools, hospitals and police in passing). Rebuilt with the site. Linked from the Regulation
tracker's strip on the front page.
"""
from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

from . import echoes, incidents, jurisdictions, pages, rss
from .bills import OFFICIAL_SOURCES

PATH = "harm-to-rule/"
SINCE = incidents.SINCE
MIN_HARMS = 5  # fewer and the line says nothing
MIN_RULES = 2

# echoes.THEMES slug: words in an incident's title
HARM_WORDS = {
    "deepfakes": r"deepfake|voice clon\w*|cloned voice|impersonat\w*",
    "sexual-deepfakes": r"(deepfake|AI[- ]generat\w*|synthetic|manipulated).{0,80}\b(sexual\w*|explicit|nudes?|intimate"
                        r"|porn\w*|non-?consensual)\b|\b(sexual\w*|explicit|nudes?|intimate|porn\w*)\b.{0,80}"
                        r"(deepfake|AI[- ]generat\w*|synthetic)|nudif\w*|undress\w*",
    "companions": r"chatbot\w*|\bcompanion\w*|Character\.AI|Replika",
    "children": r"\b(child|children|minors?|teens?|teenagers?|kids|schoolchildren|underage)\b|\bCSAM\b",
    "elections": r"\belection\w*|electoral|\bcandidates?\b|\bvoters?\b|campaign ad",
    "surveillance": r"facial recognition|face recognition|biometric\w*|surveillance",
    "bias": r"\bbias\w*|discriminat\w*",
    "copyright": r"copyright\w*|plagiari\w*|\bpirat\w*",
}
_HARM_RE = {slug: re.compile(w, re.I) for slug, w in HARM_WORDS.items()}


def subjects_of(incident: dict) -> list[str]:
    """The subjects an incident is about, from its title."""
    return [slug for slug, rx in _HARM_RE.items() if rx.search(incident["title"])]


def _place(card: dict, names: dict[str, str]) -> str:
    return next((code for j in card.get("jurisdictions") or [] if (code := j.split("-")[0]) in names), "INTL")


def subjects(cards: list[dict]) -> list[dict]:
    """Each subject with MIN_HARMS harms and MIN_RULES rules since SINCE, most harms first: its harms and its rules,
    oldest first, each rule with how many harms on the subject came before it."""
    names = {code: m["name"] for code, m in jurisdictions.meta().items()}
    harms: dict[str, list[dict]] = {}
    rules: dict[str, list[dict]] = {}
    for c in cards:
        if c.get("action") == incidents.INCIDENT and c["source"] == incidents.SOURCE and c["date"] >= SINCE:
            for slug in subjects_of(c):
                harms.setdefault(slug, []).append(c)
        elif c["category"] == "regulation" and c["source"] in OFFICIAL_SOURCES and echoes._started(c) >= SINCE:
            for slug in set(echoes.themes_of(c)) & set(HARM_WORDS):
                rules.setdefault(slug, []).append(c)
    out = []
    for slug in HARM_WORDS:
        h, r = sorted(harms.get(slug, []), key=lambda c: c["date"]), sorted(rules.get(slug, []), key=echoes._started)
        if len(h) < MIN_HARMS or len(r) < MIN_RULES:
            continue
        found = []
        for c in r:
            code = _place(c, names)
            found.append({"card": c, "since": echoes._started(c), "code": code, "name": names.get(code, "International"),
                          "rank": echoes._reached(c)[0], "reached": echoes._reached(c)[1],
                          "before": sum(x["date"] < echoes._started(c) for x in h)})
        out.append({"slug": slug, **echoes.THEMES[slug], "harms": h, "rules": found})
    out.sort(key=lambda s: len(s["harms"]), reverse=True)
    return out


# a panel's chart, in its viewBox's units
W, H = 520, 210
L, R, T, B = 44, 12, 18, 30  # room for the harms axis (left) and the years (bottom)
STAGE = {4: "adopted", 3: "passed", 2: "passed", 1: "proposed", 0: "withdrawn"}
_STAGES = [("adopted", "Adopted or set up"), ("passed", "Passed a vote"), ("proposed", "Proposed"),
           ("withdrawn", "Withdrawn or vetoed")]


def _day(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {d:%b %Y}"


def _ticks(top: int) -> list[int]:
    """The harms axis: 0 up to a round number at or above `top`, in at most 5 steps."""
    step = next(s for s in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 10**9) if top / s <= 5)
    return list(range(0, -(-top // step) * step + 1, step))


def _chart(s: dict, start: date, today: date) -> str:
    """The harms logged so far as a stepped line, each rule a dot on it on the day it was proposed."""
    days = max((today - start).days, 1)
    ticks = _ticks(round(len(s["harms"]) * 1.25))  # room above the line for the places
    x = lambda iso: round(L + (date.fromisoformat(iso[:10]) - start).days / days * (W - L - R), 1)
    y = lambda n: round(H - B - n / ticks[-1] * (H - T - B), 1)
    path = f"M{L},{y(0)}" + "".join(f"H{x(c['date'])}V{y(i + 1)}" for i, c in enumerate(s["harms"])) + f"H{W - R}"
    grid = "".join(f'<line class="g" x1="{L}" x2="{W - R}" y1="{y(t)}" y2="{y(t)}"/>'
                   f'<text class="ax" x="{L - 6}" y="{y(t) + 4}" text-anchor="end">{t}</text>' for t in ticks)
    years = "".join(f'<line class="g" x1="{x(f"{yr}-01-01")}" x2="{x(f"{yr}-01-01")}" y1="{T}" y2="{H - B}"/>'
                    f'<text class="ax" x="{x(f"{yr}-01-01") + 4}" y="{H - B + 18}">{yr}</text>'
                    for yr in range(start.year, today.year + 1))
    dots = "".join(
        f'<circle class="dot {STAGE[r["rank"]]}" cx="{x(r["since"])}" cy="{y(r["before"])}" r="6.5">'
        f'<title>{escape(r["name"])}, {echoes._when(r["card"], r["since"])}: {escape(r["card"]["title"].strip())} '
        f'({r["reached"].lower()}; {r["before"]} harms before it)</title></circle>' for r in s["rules"])
    label = f'{s["name"]}: {len(s["harms"])} harms since January 2023 and {len(s["rules"])} rules'
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{escape(label)}">{grid}{years}'
            f'<path class="area" d="{path}V{y(0)}H{L}Z"/><path class="cum" d="{path}"/>{_labels(s, x, y)}{dots}</svg>')


SHORT = {"United States": "US", "United Kingdom": "UK", "European Union": "EU", "International bodies": "Intl"}
NEAR = 30  # viewBox units: dots closer than this share one block of labels
LINE = 12  # a label line's height


def _labels(s: dict, x, y) -> str:
    """The places of each bunch of dots, a line per place ("US ×3"), up and to the left of the bunch, where the line
    hasn't reached yet (to its right for a bunch at the very start). A block that would overlap another goes up."""
    bunches: list[dict] = []
    for r in s["rules"]:
        cx, cy = x(r["since"]), y(r["before"])
        if bunches and cx - bunches[-1]["x1"] < NEAR:
            b = bunches[-1]
            b.update(x1=cx, y=min(b["y"], cy))
        else:
            b = {"x0": cx, "x1": cx, "y": cy, "places": {}}
            bunches.append(b)
        name = SHORT.get(r["name"], r["name"])
        b["places"][name] = b["places"].get(name, 0) + 1
    # each block drawn, and each dot: left, right, top, bottom
    placed = [(x(r['since']) - 7, x(r['since']) + 7, y(r['before']) - 7, y(r['before']) + 7) for r in s['rules']]
    out = []
    for b in bunches:
        lines = [p + (f" ×{n}" if n > 1 else "") for p, n in b["places"].items()]
        w = max(len(t) for t in lines) * 6.4
        left = b["x0"] - 10 - w >= L
        edge = b["x0"] - 10 if left else b["x1"] + 10
        bottom = max(b["y"] - 4, T + len(lines) * LINE)
        box = lambda: (edge - w if left else edge, edge if left else edge + w, bottom - len(lines) * LINE, bottom)
        while any(a[0] < box()[1] + 4 and box()[0] < a[1] + 4 and a[2] < box()[3] and box()[2] < a[3] for a in placed):
            bottom -= LINE
        placed.append(box())
        anchor = "end" if left else "start"
        out.extend(f'<text class="pl" x="{round(edge, 1)}" y="{round(bottom - (len(lines) - 1 - i) * LINE, 1)}" '
                   f'text-anchor="{anchor}">{escape(t)}</text>' for i, t in enumerate(lines))
    return "".join(out)


def _panel(s: dict, start: date, today: date) -> str:
    return (f'<a class="hp" href="{PATH}#{s["slug"]}"><span class="hp-h"><b>{escape(s["name"])}</b>'
            f'<small>{len(s["harms"])} harms · {len(s["rules"])} rules</small></span>{_chart(s, start, today)}</a>')


def _details(s: dict) -> str:
    rows = "".join(
        f'<tr><td class="when">{echoes._when(r["card"], r["since"])}</td><td>{escape(r["name"])}</td>'
        f'<td><a href="{escape(r["card"]["url"])}" rel="noopener">{escape(r["card"]["title"].strip())}</a>'
        f'<div class="meta">{escape(r["card"]["source"])}</div></td><td>{escape(r["reached"])}</td>'
        f'<td class="n">{r["before"]}</td></tr>' for r in s["rules"])
    latest = "".join(f'<tr><td class="when">{_day(c["date"])}</td><td><a href="{escape(c["url"])}" rel="noopener">'
                     f'{escape(c["title"])}</a></td></tr>' for c in s["harms"][::-1][:5])
    places = len({r["code"] for r in s["rules"]})
    n, m = len(s["harms"]), len(s["rules"])
    adopted = sum(r["rank"] == 4 for r in s["rules"])
    lead = (f'{escape(s["what"])} The AI Incident Database logged {n} harms on this subject since January 2023. In that '
            f'time, {m} rules on it appeared on the tracker, in {places} place{"s" * (places != 1)}'
            + (f'; {adopted} {"was" if adopted == 1 else "were"} adopted or set up.' if adopted else '; none adopted yet.'))
    return (f'<details class="er hr" id="{s["slug"]}"><summary><span class="nm">{escape(s["name"])}'
            f'<small>{n} harms · {m} rules</small></span></summary>\n<div class="det"><p>{lead}</p>'
            '<h3>The rules, and the harms logged before each (from January 2023)</h3><table class="mt"><thead><tr>'
            '<th>Since</th><th>Place</th><th>Official record</th><th>Furthest</th><th>Harms before it</th></tr></thead>'
            f'<tbody>{rows}</tbody></table><h3>Latest harms</h3><table class="mt"><thead><tr><th>Date</th><th>Harm</th>'
            f'</tr></thead><tbody>{latest}</tbody></table></div></details>')


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write harm-to-rule/: a panel per subject, then each subject's rules and latest harms. Returns its path."""
    found = subjects(cards)
    (out / PATH).mkdir(parents=True, exist_ok=True)
    start = date.fromisoformat(SINCE)
    legend = ('<span><i class="cum-key"></i>Harms logged so far</span>'
              + "".join(f'<span><svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><circle class="dot {k}" '
                        f'cx="8" cy="8" r="6"/></svg>A rule: {w.lower()}</span>' for k, w in _STAGES))
    what = ("AI harms by subject, and the rules on the same subject, from January 2023. The line counts the harms the AI "
            "Incident Database logged; each dot is a rule, on the day it was proposed, so its height is the harms before it.")
    body = (f'<div class="ft">\n<h1>Harm → rule</h1>\n<p class="intro">{escape(what)} A rule that comes after harms '
            'isn\'t shown to be caused by them.</p>\n'
            f'<div class="ec-legend">{legend}</div>\n'
            f'<div class="hps">{"".join(_panel(s, start, today) for s in found)}</div>\n'
            '<h2>The rules and the latest harms, by subject</h2>\n'
            f'<div class="hr-list">{"".join(_details(s) for s in found)}</div>\n</div>\n'
            # a panel opens its subject below
            '<script>(() => {const f = () => {const d = location.hash && document.getElementById(location.hash.slice(1));'
            ' if (d && d.tagName === "DETAILS") d.open = true}; f(); addEventListener("hashchange", f)})()</script>\n')
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Harm → rule", "description": what,
            "url": f"{rss.SITE}{PATH}"}
    note = ('Harms: the <a href="https://incidentdatabase.ai/">AI Incident Database</a> (Responsible AI Collaborative), '
            'CC BY-SA 4.0, each linking to its incident. Rules: the Regulation tracker\'s official records. Updated with '
            'every run. <a href="/rule-echoes/">Rule echoes</a>')
    (out / PATH / "index.html").write_text(
        pages.page("Harm → rule · AI Pulse", what, PATH, body, data, pages.frame(conn, len(cards)),
                   ("/regulation/", "Back to the Regulation tracker"), note), encoding="utf-8")
    return [PATH]
