"""The month in numbers (monthly/<YYYY-MM>/insights/): a page of charts for each monthly issue, linked from the issue.

Every number is a count of our own stories (a story many outlets carried counts once). How this month compares: each
stream's share of the month's stories against the 11 months before (a share, as raw counts grow with our sources).
What made the busiest days: the days that stood out against a normal day that month, each with the stories most outlets
carried. Then the companies and the places the stories named most (against the month before), and the themes that
rose or faded against the three months before. Companies, places and themes are the tags each story already carries
(classify.py). The busiest days' headlines load in the reader's browser from insights.json, so the page itself holds
only our own words. Rebuilt with the site.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from html import escape
from pathlib import Path
from statistics import median

from . import classify, jurisdictions, monthly, pages, rss

TOP = 10    # companies and places shown
THEMES = 5  # themes rising, and fading
MIN = 10    # a theme rises or fades only with this many stories a month (now, or before)
YEAR = 12   # How this month compares: this month and the 11 before
PEAKS = 3   # busiest days explained
STOOD_OUT = 1.3  # ...each at least this many times a normal day
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


def shares(month: str, by_month: dict[str, list[dict]]) -> list[tuple[str, list[tuple[str, float]]]]:
    """Each stream's share of all stories, month by month (oldest first, this month last), for the YEAR months to this
    one that have stories. Streams with too few stories in the year to say anything are left out."""
    ms = [m for m in (_prev(month, k) for k in range(YEAR - 1, -1, -1)) if by_month.get(m)]
    out = []
    for s in monthly.STREAMS:
        n = {m: sum(c["category"] == s for c in by_month[m]) for m in ms}
        if sum(n.values()) >= 30:
            out.append((s, [(m, n[m] / len(by_month[m])) for m in ms]))
    return out


def peaks(mine: list[dict], daily: list[tuple[date, int]]) -> list[dict]:
    """The days that stood out (most stories against the month's median day of the same kind, weekday or weekend),
    by date, each with the stories most outlets carried that day (Research left out: a paper is one outlet). A day
    with no story two outlets carried is only a busy feed, with nothing to explain it, so it's passed over."""
    usual = {k: median([n for d, n in daily if (d.weekday() >= 5) == k] or [1]) or 1 for k in (False, True)}
    out = []
    for d, n in sorted(daily, key=lambda x: -x[1] / usual[x[0].weekday() >= 5]):
        x = n / usual[d.weekday() >= 5]
        if x < STOOD_OUT or len(out) == PEAKS:
            break
        day = monthly.ranked([c for c in mine if c["date"][:10] == d.isoformat() and c["category"] != "research"])
        picks = [c for c in day if monthly.outlets(c) > 1][:2]
        if picks:
            out.append({"day": d.isoformat(), "n": n, "x": round(x, 1), "weekend": d.weekday() >= 5,
                        "stories": [monthly._story(c) for c in picks]})
    return sorted(out, key=lambda p: p["day"])


def numbers(month: str, by_month: dict[str, list[dict]]) -> dict:
    """The month's counts, each with last month's beside it."""
    mine, last = by_month.get(month, []), by_month.get(_prev(month), [])
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
    return {"shares": shares(month, by_month), "daily": daily, "peaks": peaks(mine, daily),
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


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%" if v < .1 else f"{v * 100:.0f}%"


def _compare(rows: list[tuple[str, list[tuple[str, float]]]]) -> str:
    """A row per stream: its share each month as small columns (this month in the stream's colour), the share, and
    where it stands against the months before."""
    out = []
    for s, ms in rows:
        top = max(v for _, v in ms) or 1
        now, before = ms[-1][1], [v for _, v in ms[:-1]]
        cols = "".join(f'<i class="{"now" if k == len(ms) - 1 else ""}" style="height:{max(v / top * 100, 3):.0f}%" '
                       f'title="{monthly.name(m)}: {_pct(v)}"></i>' for k, (m, v) in enumerate(ms))
        if len(before) >= 3 and now > max(before):
            note = f"Biggest in {len(ms)} months"
        elif len(before) >= 3 and now < min(before):
            note = f"Smallest in {len(ms)} months"
        else:
            note = f"usually {_pct(sum(before) / len(before))}" if before else ""
        out.append(f'<li><span class="nm">{monthly.STREAMS[s]}</span><span class="ins-spark" style="--c:var(--f-{COL[s]})">'
                   f'{cols}</span><b class="v">{_pct(now)}</b><span class="ch">{note}</span></li>')
    return '<ol class="ins-bars ins-cmp">' + "".join(out) + "</ol>"


def _days(daily: list[tuple[date, int]], peaks: list[dict], src: str) -> str:
    top = max((n for _, n in daily), default=1) or 1
    marks = {p["day"]: k + 1 for k, p in enumerate(peaks)}
    cols = "".join(
        f'<li class="{"we" if d.weekday() >= 5 else ""}{" pk" if d.isoformat() in marks else ""}" title="{d.strftime("%a")} {d.day} {d.strftime("%b")}: {n} {"story" if n == 1 else "stories"}">'
        + (f'<b class="mk" style="bottom:calc({n / top * 100:.1f}% + 4px)">{marks[d.isoformat()]}</b>' if d.isoformat() in marks else "")
        + f'<i style="height:{max(n / top * 100, 1):.1f}%"></i><span>{d.day if d.day in (1, 8, 15, 22, 29) else ""}</span></li>'
        for d, n in daily)
    cards = "".join(
        f'<div class="ins-peak" data-day="{p["day"]}"><b class="mk">{k + 1}</b><div><h3>{_day(date.fromisoformat(p["day"]))}</h3>'
        f'<p class="meta">{p["n"]} stories, {p["x"]:g}× a normal {"weekend day" if p["weekend"] else "weekday"} that month</p>'
        '<ol><li class="meta">Loading…</li></ol></div></div>' for k, p in enumerate(peaks))
    return (f'<ol class="ins-days" style="--n:{len(daily)}">{cols}</ol>'
            '<p class="ins-key"><span><i class="sw"></i>Weekday</span><span><i class="sw we"></i>Weekend</span>'
            '<span><i class="sw pk"></i>Stood out</span></p>'
            + (f'<div class="ins-peaks" id="peaks" data-src="{src}">{cards}</div>{PEAKS_JS}' if peaks else ""))


PEAKS_JS = r"""<script>
(() => {
  const box = document.getElementById("peaks");
  const NAMES = {tool: "Releases", news: "Industry", research: "Research", regulation: "Regulation", policy: "Policy", infra: "Infra"};
  const el = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  fetch(box.dataset.src, {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(d => d.peaks.forEach(p => {
    box.querySelector(`[data-day="${p.day}"] ol`).replaceChildren(...p.stories.map(e => {
      const li = el("li"), a = el("a", null, e.title); a.href = e.url; a.rel = "noopener";
      li.append(a, el("div", "meta", NAMES[e.stream] + " · " + e.source + (e.outlets > 1 ? " · " + e.outlets + " outlets" : "")));
      return li; }));
  })).catch(() => box.querySelectorAll("ol").forEach(o => o.replaceChildren(el("li", "meta", "Couldn't load the stories. Try reloading the page."))));
})();
</script>"""


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


def _and(words: list[str]) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def body(month: str, x: dict) -> str:
    last = monthly.name(_prev(month)).split()[0]
    sections = []
    # how this month compares: each stream's share of the news against the months before
    rows = x["shares"]
    if rows:
        n = len(rows[0][1])
        big = [monthly.STREAMS[s] for s, ms in rows if n >= 4 and ms[-1][1] > max(v for _, v in ms[:-1])]
        small = [monthly.STREAMS[s] for s, ms in rows if n >= 4 and ms[-1][1] < min(v for _, v in ms[:-1])]
        say = []
        if big:
            say.append(f"{_and(big)} took a bigger share of the news than in any of the {n - 1} months before.")
        if small:
            say.append(f"{_and(small)} took {'its' if len(small) == 1 else 'their'} smallest share.")
        if not say and n > 1:
            s, ms = max(rows, key=lambda r: abs(r[1][-1][1] / (sum(v for _, v in r[1][:-1]) / (n - 1) or 1) - 1))
            usual = sum(v for _, v in ms[:-1]) / (n - 1)
            say.append(f"{monthly.STREAMS[s]} moved most: {_pct(ms[-1][1])} of the month's stories, against a usual {_pct(usual)}.")
        sections.append(("compare", "How this month compares", " ".join(say) or "Each stream's share of the month's stories.",
                         _compare(rows) + f'<p class="ins-note">Each stream\'s share of all stories, month by month to {monthly.name(month)}. '
                         'A share, not a count, as the count grows with our sources.</p>'))
    # what made the busiest days
    pk = x["peaks"]
    if pk:
        days = [f"{date.fromisoformat(p['day']).day} {date.fromisoformat(p['day']).strftime('%B')}" for p in pk]
        say = (f"{['One day', 'Two days', 'Three days'][len(pk) - 1]} stood out: {_and(days)}. What drove "
               + ("it:" if len(pk) == 1 else "each:"))
    else:
        say = "No day stood out: the news ran evenly all month."
    sections.append(("days", "What made the busiest days", say, _days(x["daily"], pk, f"/{path(month)}insights.json")))
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
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "insights.json").write_text(json.dumps({"peaks": x["peaks"]}, separators=(",", ":"), ensure_ascii=False),
                                               encoding="utf-8")
        prev = f'<a href="/{path(issues[i - 1])}">← {monthly.name(issues[i - 1])}</a>' if i else "<span></span>"
        nxt = f'<a href="/{path(issues[i + 1])}">{monthly.name(issues[i + 1])} →</a>' if i + 1 < len(issues) else "<span></span>"
        html = (f'<div class="mi">\n<div class="ins-head"><span class="kind">AI Pulse · Insights · No. {monthly.number(m)}</span>'
                f'<h1>{monthly.name(m)} in numbers</h1></div>\n{body(m, x)}'
                f'<nav class="issue-nav">{prev}<a href="/{monthly.path(m)}">Back to the issue</a>{nxt}</nav>\n</div>')
        what = (f"What the AI news of {monthly.name(m)} adds up to: how it compares with the months before, what made the "
                "busiest days, and the companies, themes and places in the news.")
        ld = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{monthly.name(m)} in numbers",
              "description": what, "url": f"{rss.SITE}{p}"}
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "index.html").write_text(
            pages.page(f"{monthly.name(m)} in numbers · AI Pulse", what, p, html, ld, parts,
                       (f"/{monthly.path(m)}", f"The {monthly.name(m)} issue")), encoding="utf-8")
        paths.append(p)
    return paths
