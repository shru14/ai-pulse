"""The month in numbers (monthly/<YYYY-MM>/insights/): a page of charts for each monthly issue, linked from the issue.

Every number is a count of our own stories (a story many outlets carried counts once), compared with the month before:
the stories in each stream, day by day, the companies and the places the stories named most, and the themes that rose
or faded against the three months before. Companies, places and themes are the tags each story already carries
(classify.py). Only our own words and numbers are on the page, no headlines. Rebuilt with the site.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import classify, jurisdictions, monthly, pages, rss

TOP = 10    # companies and places shown
THEMES = 5  # themes rising, and fading
MIN = 10    # a theme rises or fades only with this many stories a month (now, or before)
FEW = 5     # fewer stories the month before: the change is shown as "was 3", not "+133%"
COMPANIES = set(classify.COMPANY_TERMS)
PLACES = {v[0] for k, v in jurisdictions.JURISDICTIONS.items() if k != "INTL"}  # international bodies aren't a place
TOPICS = set(classify.TOPIC_TAGS) - {"Research"}  # every paper has "Research": it says nothing of the month
COL = {"tool": "tool", "news": "news", "research": "research", "regulation": "reg", "policy": "policy", "infra": "infra"}


def path(month: str) -> str:
    return f"{monthly.path(month)}insights/"


def _prev(month: str, n: int = 1) -> str:
    d = date.fromisoformat(month + "-01")
    for _ in range(n):
        d = (d - timedelta(days=1)).replace(day=1)
    return d.strftime("%Y-%m")


def _tags(cards: list[dict], keep: set[str]) -> Counter:
    return Counter(t for c in cards for t in set(c.get("tags") or []) if t in keep)


def change(now: int, before: int) -> str:
    """'+32%', '−12%' or 'same'; 'was 3' when there were too few before for a share to mean much, 'new' for none."""
    if not before:
        return "new" if now else ""
    if before < FEW:
        return f"was {before}"
    p = round((now - before) / before * 100)
    return "same" if p == 0 else f"+{p}%" if p > 0 else f"−{-p}%"


def numbers(month: str, by_month: dict[str, list[dict]]) -> dict:
    """The month's counts, each with last month's beside it."""
    mine, last = by_month.get(month, []), by_month.get(_prev(month), [])
    streams = Counter(c["category"] for c in mine)
    before = Counter(c["category"] for c in last)
    days = Counter(c["date"][:10] for c in mine)
    d, end = date.fromisoformat(month + "-01"), monthly._last_day(month)
    daily = []
    while d <= end:
        daily.append((d, days[d.isoformat()]))
        d += timedelta(days=1)
    comp, comp0 = _tags(mine, COMPANIES), _tags(last, COMPANIES)
    place, place0 = _tags(mine, PLACES), _tags(last, PLACES)
    theme = _tags(mine, TOPICS)
    usual = Counter()
    for k in range(1, 4):
        usual.update(_tags(by_month.get(_prev(month, k), []), TOPICS))
    usual = {t: n / 3 for t, n in usual.items()}
    moves = [(t, theme[t], usual.get(t, 0)) for t in TOPICS if max(theme[t], usual.get(t, 0)) >= MIN]
    rise = sorted([m for m in moves if m[1] > m[2]], key=lambda m: -(m[1] - m[2]) / (m[2] + 5))[:THEMES]
    fade = sorted([m for m in moves if m[1] < m[2]], key=lambda m: (m[1] - m[2]) / (m[2] + 5))[:THEMES]
    return {"total": len(mine), "total0": len(last),
            "streams": [(s, streams[s], before[s]) for s in monthly.STREAMS if streams[s] or before[s]],
            "daily": daily,
            "companies": [(t, n, comp0[t]) for t, n in comp.most_common(TOP)],
            "places": [(t, n, place0[t]) for t, n in place.most_common(TOP)], "nplaces": len(place),
            "rise": rise, "fade": fade}


# ---------- The page ----------

def _bars(rows: list[tuple], colour=lambda r: "var(--f-news)", label=lambda r: escape(r[0])) -> str:
    """A bar per row (name, count, last month's count), longest = the most."""
    top = max((r[1] for r in rows), default=1) or 1
    return '<ol class="ins-bars">' + "".join(
        f'<li title="{escape(r[0])}: {r[1]} {"story" if r[1] == 1 else "stories"}'
        f'{f", {r[2]} the month before" if len(r) > 2 else ""}"><span class="nm">{label(r)}</span>'
        f'<span class="tr"><i style="width:{max(r[1] / top * 100, 1):.1f}%;--c:{colour(r)}"></i></span>'
        f'<b class="v">{r[1]:,}</b><span class="ch">{change(r[1], r[2]) if len(r) > 2 else ""}</span></li>'
        for r in rows) + "</ol>"


def _days(daily: list[tuple[date, int]]) -> str:
    top = max((n for _, n in daily), default=1) or 1
    peak = max(daily, key=lambda x: x[1])[0]
    cols = "".join(
        f'<li class="{"we" if d.weekday() >= 5 else ""}{" pk" if d == peak else ""}" title="{d.strftime("%a")} {d.day} {d.strftime("%b")}: {n} {"story" if n == 1 else "stories"}">'
        f'<i style="height:{max(n / top * 100, 1):.1f}%"></i><span>{d.day if d.day in (1, 8, 15, 22, 29) or d == peak else ""}</span></li>'
        for d, n in daily)
    return (f'<ol class="ins-days" style="--n:{len(daily)}">{cols}</ol>'
            '<p class="ins-key"><span><i class="sw"></i>Weekday</span><span><i class="sw we"></i>Weekend</span></p>')


def _themes(rows: list[tuple], up: bool) -> str:
    if not rows:
        return '<p class="meta">None this month.</p>'
    top = max(abs(n - u) / (u + 1) for _, n, u in rows) or 1
    return '<ol class="ins-bars ins-th">' + "".join(
        f'<li title="{escape(t)}: {n} stories, about {round(u)} a month before"><span class="nm">{escape(t)}</span>'
        f'<span class="tr"><i style="width:{max(abs(n - u) / (u + 1) / top * 100, 2):.1f}%;--c:{"#E69F00" if up else "#56B4E9"}"></i></span>'
        f'<b class="v">{n}</b><span class="ch">was ~{round(u)}</span></li>' for t, n, u in rows) + "</ol>"


def _day(d: date) -> str:
    return f'{d.strftime("%A")} {d.day} {d.strftime("%B")}'


def body(month: str, x: dict) -> str:
    last = monthly.name(_prev(month)).split()[0]
    sections = []
    # stories by stream
    grew = [s for s in x["streams"] if s[2] >= 10]
    big = max(grew, key=lambda s: (s[1] - s[2]) / s[2], default=None)
    say = f'{x["total"]:,} stories'
    if x["total0"]:
        ch = change(x["total"], x["total0"])
        say += f', {"as many as" if ch == "same" else ch.replace("+", "").replace("−", "") + (" more than" if ch[0] == "+" else " fewer than")} {last}'
    if big and big[1] > big[2]:
        say += f'. {monthly.STREAMS[big[0]]} grew most ({change(big[1], big[2])})'
    sections.append(("streams", "Stories by stream", say + ".",
                     _bars([(monthly.STREAMS[s], n, b) for s, n, b in x["streams"]],
                           colour=lambda r: f'var(--f-{COL[next(k for k, v in monthly.STREAMS.items() if v == r[0])]})')
                     + f'<p class="ins-note">Change against {last}.</p>'))
    # day by day
    daily = x["daily"]
    peak = max(daily, key=lambda d: d[1])
    wd = [n for d, n in daily if d.weekday() < 5]
    we = [n for d, n in daily if d.weekday() >= 5]
    say = f"The busiest day was {_day(peak[0])}, with {peak[1]} stories."
    if wd and we:
        say += f" A weekday had {round(sum(wd) / len(wd))} on average, a weekend day {round(sum(we) / len(we))}."
    sections.append(("days", "Day by day", say, _days(daily)))
    # companies
    if x["companies"]:
        c0 = x["companies"][0]
        up = max([c for c in x["companies"] if c[2] >= 5], key=lambda c: c[1] / c[2], default=None)
        say = f"{c0[0]} was in the most stories ({c0[1]})."
        if up and up[1] > up[2] and up[0] != c0[0]:
            say += f" {up[0]} rose most ({change(up[1], up[2])})."
        sections.append(("companies", "Companies in the news", say,
                         _bars(x["companies"]) + f'<p class="ins-note">Stories naming each company. Change against {last}.</p>'))
    # themes
    if x["rise"] or x["fade"]:
        say = []
        if x["rise"]:
            t, n, u = x["rise"][0]
            say.append(f"{t} rose most: {n} stories, against about {round(u)} a month before.")
        if x["fade"]:
            t, n, u = x["fade"][0]
            say.append(f"{t} faded most: {n}, against about {round(u)}.")
        sections.append(("themes", "Themes rising and fading", " ".join(say),
                         f'<div class="ins-two"><div><h3>Rising</h3>{_themes(x["rise"], True)}</div>'
                         f'<div><h3>Fading</h3>{_themes(x["fade"], False)}</div></div>'
                         '<p class="ins-note">Against the average of the three months before. Bar = how far it moved.</p>'))
    # places
    if x["places"]:
        p0 = x["places"][0]
        say = f"Stories named {x['nplaces']} countries and blocs. {p0[0]} came up most ({p0[1]})"
        say += f", then {x['places'][1][0]} ({x['places'][1][1]})." if len(x["places"]) > 1 else "."
        sections.append(("places", "Where in the world", say,
                         _bars(x["places"], colour=lambda r: "var(--f-policy)")
                         + f'<p class="ins-note">Stories naming each place. Change against {last}.</p>'))
    return ('<ol class="contents">' + "".join(f'<li><a href="/{path(month)}#{k}">{t}</a></li>' for k, t, *_ in sections)
            + "</ol>\n" + "".join(f'<section class="sheet ins" id="{k}"><h2>{t}</h2><p class="ins-say">{escape(s)}</p>{h}</section>\n'
                                  for k, t, s, h in sections))


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write each issue's insights page. Returns the pages' paths."""
    parts = pages.frame(conn, len(cards))
    by_month: dict[str, list[dict]] = {}
    for c in cards:
        by_month.setdefault((c.get("date") or "")[:7], []).append(c)
    paths = []
    issues = [m for m in monthly.months(today) if by_month.get(m)]
    for i, m in enumerate(issues):
        x = numbers(m, by_month)
        p = path(m)
        prev = f'<a href="/{path(issues[i - 1])}">← {monthly.name(issues[i - 1])}</a>' if i else "<span></span>"
        nxt = f'<a href="/{path(issues[i + 1])}">{monthly.name(issues[i + 1])} →</a>' if i + 1 < len(issues) else "<span></span>"
        html = (f'<div class="mi">\n<div class="ins-head"><span class="kind">AI Pulse · Insights · No. {monthly.number(m)}</span>'
                f'<h1>{monthly.name(m)} in numbers</h1></div>\n{body(m, x)}'
                f'<nav class="issue-nav">{prev}<a href="/{monthly.path(m)}">Back to the issue</a>{nxt}</nav>\n</div>')
        what = f"What the AI news of {monthly.name(m)} adds up to: the stories by stream and by day, the companies, places and themes."
        ld = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{monthly.name(m)} in numbers",
              "description": what, "url": f"{rss.SITE}{p}"}
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "index.html").write_text(
            pages.page(f"{monthly.name(m)} in numbers · AI Pulse", what, p, html, ld, parts,
                       (f"/{monthly.path(m)}", f"The {monthly.name(m)} issue")), encoding="utf-8")
        paths.append(p)
    return paths
