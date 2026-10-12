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
import math
import re
from collections import Counter
from datetime import date, timedelta
from html import escape
from pathlib import Path
from statistics import median

from . import classify, jurisdictions, money, monthly, pages, rss

TOP = 10    # companies and places shown
FUND_THEMES = 6  # Money moves: themes shown,
LADDER = 8       # valuations,
DEALS = 6        # and deals
LABS = [re.compile(classify.COMPANY_TERMS[k], re.I) for k in ("OpenAI", "Anthropic", "xAI", "Mistral", "DeepSeek")
        if k in classify.COMPANY_TERMS] + [re.compile(r"Moonshot|MiniMax|Zhipu|Safe Superintelligence|SSI|Thinking Machines|"
                                                    r"Reflection|Prometheus|Cohere|Sakana|Kimi", re.I)]
EXPOSED = 6     # Legal and risk: companies shown
# Legal and risk: a court story is a lawsuit, a ruling or a settlement; a regulator story has a regulator acting
COURT = re.compile(r"\blawsuits?\b|\bsues?\b|\bsued\b|\bsuing\b|\bsuits?\b(?! up)|\bcourts?\b(?!room)|"
                   r"\bjudges? (?:rules?|ruled|says|orders?|blocks?|dismiss\w*|toss\w*|sides?|finds?)|\bjury\b|"
                   r"\bcopyright (?:case|claim|suit|infringement)|\bantitrust (?:case|suit|trial)|class action|"
                   r"\bsettle(?:s|d|ment)\b|\bverdict\b", re.I)
REGULATOR = re.compile(r"\b(?:FTC|DOJ|SEC|FCC|CMA|ICO|CNIL|European Commission|EU|Commission|regulators?|watchdogs?|"
                       r"attorneys? general|data protection (?:authority|board|regulator)|privacy regulator|"
                       r"authorit(?:y|ies)|government)\b.{0,60}?\b(?:probe[sd]?|investigat\w*|fine[sd]?|sues?|orders?|"
                       r"bans?|banned|charges?|subpoena\w*|warns?)\b|\b(?:probe|investigation|inquiry) (?:into|of)\b|"
                       r"\bfined\b|\bto investigate (?:if|whether)\b|\bunder investigation\b", re.I)
ENOUGH = 10     # US vs China: a split shown only with this many from the two
# IPO watch: headlines about a listing (the "IPO" tag alone is too loose: it rides on any story about a big lab)
IPO = re.compile(r"\bIPOs?\b|\bgo(?:es|ing)? public\b|\bpublic listing\b|\bfiles? (?:confidentially )?(?:for|to) "
                 r"(?:an? )?(?:IPO|list)|\bS-1\b|\bstock market debut\b", re.I)
IPO_MIN = 3     # IPO watch shown only with this many headlines in the month
IPO_SHOWN = 5   # ...and lists the ones most outlets carried
HF_UPLOAD = re.compile(r"(.+?) publishes .+ on Hugging Face$")  # feeds.py's open-weight uploads
# Where the labs Hugging Face uploads name are based, beyond the news tags' companies (classify.COMPANY_HOME)
LAB_HOME = {"Qwen": "China", "Ant Group": "China", "inclusionAI": "China", "Zhipu": "China", "Z.ai": "China",
            "ByteDance": "China", "Moonshot": "China", "Kuaishou": "China", "Baidu": "China", "Tencent": "China",
            "Xiaomi": "China", "StepFun": "China", "MiniMax": "China", "Meituan": "China", "OpenBMB": "China",
            "Cloudflare": "United States", "NVIDIA": "United States", "Hugging Face": "United States", "Microsoft": "United States",
            "IBM": "United States", "Allen": "United States", "Ai2": "United States", "Liquid": "United States",
            "Nous": "United States", "Arcee": "United States", "Salesforce": "United States", "ServiceNow": "United States",
            "Sakana": "Japan", "LG": "South Korea", "Upstage": "South Korea", "NAVER": "South Korea", "Kakao": "South Korea"}
NOT_THEMES = {"Funding", "M&A", "IPO", "Study Report", "Benchmarks", "Law", "Regulation", "Governance"}  # not what's funded
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


def funds(month: str, ledger: dict[str, list[dict]]) -> dict:
    """Money moves (money.py): the month's funding rounds by theme (against the three months before), the valuations
    named (each with the company's last one before, when we have it), and the biggest acquisitions and compute deals."""
    mine = ledger.get(month, [])
    rounds = [r for r in mine if r["kind"] == "round" and r["amount"]]
    def theme(r):  # the frontier labs' rounds apart (the biggest money), else the first theme the story names
        if any(p.fullmatch(r["company"]) for p in LABS):
            return "AI labs"
        return next((t for t, p in classify._topics.items() if t not in NOT_THEMES and p.search(r["text"])), "Other")
    by = {}
    for r in rounds:
        t = by.setdefault(theme(r), [0, 0.0])
        t[0] += 1
        t[1] += r["amount"]
    usual = Counter()
    for k in range(1, 4):
        usual.update(theme(r) for r in ledger.get(_prev(month, k), []) if r["kind"] == "round" and r["amount"])
    themes = sorted(((t, n, v, usual[t] / 3) for t, (n, v) in by.items() if t != "Other"), key=lambda x: (-x[1], -x[2]))
    earlier = {}
    for m in sorted(k for k in ledger if k < month):
        for r in ledger[m]:
            if r["valuation"]:
                earlier[r["company"].lower()] = (r["valuation"], m)
    vals = sorted((r for r in mine if r["valuation"]), key=lambda r: -r["valuation"])[:LADDER]
    ladder = [dict(r, before=earlier.get(r["company"].lower())) for r in vals]
    deals = sorted((r for r in mine if r["kind"] in ("acquisition", "compute")), key=lambda r: -r["amount"])[:DEALS]
    year = [r for m, rs in ledger.items() if m[:4] == month[:4] and m <= month for r in rs if r["kind"] == "compute"]
    return {"rounds": len(rounds), "raised": sum(r["amount"] for r in rounds),
            "biggest": max(rounds, key=lambda r: r["amount"], default=None), "themes": themes[:FUND_THEMES],
            "ladder": ladder, "deals": deals, "compute_year": (len(year), sum(r["amount"] for r in year))}


def home(lab: str) -> str | None:
    """Where a lab is based (classify.COMPANY_HOME, and LAB_HOME for the names Hugging Face uploads use)."""
    return (classify.COMPANY_HOME.get(lab)
            or next((v for k, v in LAB_HOME.items() if k.lower() in lab.lower()), None))


def open_models(cards: list[dict]) -> list[dict]:
    """The month's open-weight models: the labs' uploads to Hugging Face in our Releases stream ("Xiaomi MiMo publishes
    MiMo-V2.6-Flash on Hugging Face"; verified organisations, feeds.py), each with its lab as the news tags name it."""
    out = []
    for c in cards:
        m = HF_UPLOAD.match(c.get("title") or "") if c["category"] == "tool" else None
        if m:
            who = m.group(1)
            lab = next((k for k in classify.COMPANY_HOME if k.lower() in who.lower()), who)  # "Xiaomi MiMo" -> Xiaomi
            out.append({"lab": lab, "date": c["date"][:10]})
    return sorted(out, key=lambda x: x["date"])


def rivals(month: str, by_month: dict[str, list[dict]]) -> list[tuple]:
    """US vs China: papers and open-weight models from each, this month and China's share for the YEAR months to this
    one. A paper counts for the country of each lab or scholar it names (classify.paper_homes)."""
    homes = classify.paper_homes()
    def counts(m: str) -> dict[str, Counter]:
        out = {"Papers": Counter(), "Open-weight models": Counter()}
        for c in by_month.get(m, []):
            if c["category"] == "research":
                out["Papers"].update({homes[t] for t in c.get("tags") or [] if t in homes})
        out["Open-weight models"].update(home(x["lab"]) for x in open_models(by_month.get(m, [])))
        return out
    ms = [_prev(month, k) for k in range(YEAR - 1, -1, -1)]
    history = {m: counts(m) for m in ms}
    rows = []
    for what in ("Papers", "Open-weight models"):
        now = history[month][what]
        us, cn = now["United States"], now["China"]
        if us + cn < ENOUGH:  # a share of a handful says nothing
            continue
        trend = [(m, h[what]["China"] / (h[what]["China"] + h[what]["United States"]))
                 for m, h in history.items() if h[what]["China"] + h[what]["United States"] >= ENOUGH]
        rows.append((what, us, cn, trend))
    return rows


def exposure(mine: list[dict]) -> list[tuple]:
    """Legal and risk: for each company, the month's stories that take it to court (lawsuits, copyright, antitrust),
    before regulators (probes, fines, privacy) or into the AI Incident Database. The most exposed first."""
    n: dict[str, Counter] = {}
    for c in mine:
        t = c.get("title") or ""
        kind = ("incidents" if c.get("action") == "incident" else "courts" if COURT.search(t) else
                "regulators" if REGULATOR.search(t) else None)
        if kind:
            # the companies the story is about: "Perplexity sued over data sharing with Meta and Google" -> Perplexity
            head = t if kind == "incidents" else re.split(r"\b(?:with|over|about|from|after)\b", t)[0]
            for co in classify.company_tags(head, c.get("summary") or "" if kind == "incidents" else ""):
                n.setdefault(co, Counter())[kind] += 1
    rows = sorted(n.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))
    return [(co, k["courts"], k["regulators"], k["incidents"]) for co, k in rows if sum(k.values()) >= 2][:EXPOSED]


def pace(month: str, ledger: dict[str, list[dict]]) -> list[tuple]:
    """Funding pace: for this month and the 11 before (those with rounds), the rounds, the money disclosed, and the
    biggest round (its amount and company), oldest first."""
    out = []
    for m in (_prev(month, k) for k in range(YEAR - 1, -1, -1)):
        rs = [r for r in ledger.get(m, []) if r["kind"] == "round" and r["amount"]]
        if rs:
            b = max(rs, key=lambda r: r["amount"])
            out.append((m, len(rs), sum(r["amount"] for r in rs), b["amount"], b["company"]))
    return out


def _ipo(cards: list[dict]) -> list[dict]:
    return [c for c in cards if c["category"] in ("news", "tool", "policy", "infra") and IPO.search(c.get("title") or "")]


def ipos(month: str, by_month: dict[str, list[dict]]) -> dict:
    """IPO watch: the month's headlines about listings (most outlets first), and how many there were each month over
    the year to this one."""
    trend = [(m, len(_ipo(by_month.get(m, [])))) for m in (_prev(month, k) for k in range(YEAR - 1, -1, -1))]
    return {"trend": trend, "stories": [monthly._story(c) for c in monthly.ranked(_ipo(by_month.get(month, [])))][:IPO_SHOWN]}


def numbers(month: str, by_month: dict[str, list[dict]], ledger: dict[str, list[dict]] | None = None) -> dict:
    """The month's counts, each with last month's beside it. `ledger` is each month's money stories (money.month)."""
    if ledger is None:
        ledger = {m: money.month(cs) for m, cs in by_month.items()}
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
            "rise": rise, "fade": fade, "money": funds(month, ledger), "opens": Counter(x["lab"] for x in open_models(mine)),
            "rivals": rivals(month, by_month), "exposure": exposure(mine), "pace": pace(month, ledger),
            "ipo": ipos(month, by_month)}


# ---------- The page ----------

def _riser(rows: list[tuple]) -> tuple | None:
    """The row that grew most against the month before (from FEW or more), if any grew."""
    return max([r for r in rows if r[2] >= FEW and r[1] > r[2]], key=lambda r: r[1] / r[2], default=None)


def _call(text: str, w: float) -> str:
    """A yellow tag at the end of a bar (inside it when the bar runs long)."""
    return f'<span class="call{" in" if w > 62 else ""}" style="left:{w:.1f}%">{escape(text)}</span>'


def _bars(rows: list[tuple], focus: str | None = None, tag: str = "") -> str:
    """A grey bar per row (name, count, last month's count), longest = the most; `focus` in the accent, with `tag`."""
    top = max((r[1] for r in rows), default=1) or 1
    out = []
    for r in rows:
        w, on = max(r[1] / top * 100, 1), r[0] == focus
        out.append(f'<li class="{"on" if on else ""}" title="{escape(r[0])}: {r[1]} {"story" if r[1] == 1 else "stories"}'
                   f'{f", {r[2]} the month before" if len(r) > 2 else ""}"><span class="nm">{escape(r[0])}</span>'
                   f'<span class="tr"><i style="width:{w:.1f}%"></i>{_call(tag, w) if on and tag else ""}</span>'
                   f'<b class="v">{r[1]:,}</b><span class="ch">{change(r[1], r[2]) if len(r) > 2 else ""}</span></li>')
    return '<ol class="ins-bars">' + "".join(out) + "</ol>"


def _tiles(rows: list[tuple]) -> str:
    """Places as tiles, darker the more stories named them: the place, its count and the change against last month."""
    top = max((r[1] for r in rows), default=1) or 1
    return '<ol class="ins-tiles">' + "".join(
        f'<li style="--a:{r[1] / top * 75 + 10:.0f}%" title="{escape(r[0])}: {r[1]} stories, {r[2]} the month before">'
        f'<span class="nm">{escape(r[0])}</span><b>{r[1]}</b><span class="ch">{change(r[1], r[2])}</span></li>'
        for r in rows) + "</ol>"


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%" if v < .1 else f"{v * 100:.0f}%"


def _pts(d: float) -> str:
    d *= 100
    return "same" if abs(d) < .05 else f"{'+' if d > 0 else '−'}{abs(d):.1f} pts"


def _compare(rows: list[tuple[str, list[tuple[str, float]]]]) -> str:
    """A row per stream on one scale: its usual share (hollow square, the months before) and this month's (filled, in
    the stream's colour), the share, and how far it moved. The stream that moved most gets a yellow tag."""
    stats = []
    for s, ms in rows:
        now, before = ms[-1][1], [v for _, v in ms[:-1]]
        stats.append((s, now, sum(before) / len(before) if before else None, before, len(ms)))
    scale = math.ceil(max(max(now, u or 0) for _, now, u, _, _ in stats) * 10 + .5) / 10
    moved = max((t for t in stats if t[2]), key=lambda t: abs(t[1] / t[2] - 1), default=None)
    def at(v):
        return f"{v / scale * 100:.1f}%"
    out = []
    for t in stats:
        s, now, usual, before, n = t
        note = (f"Biggest in {n} months" if len(before) >= 3 and now > max(before) else
                f"Smallest in {n} months" if len(before) >= 3 and now < min(before) else "")
        trk = ""
        if usual is not None:
            lo, hi = min(now, usual), max(now, usual)
            trk = (f'<i class="seg" style="left:{at(lo)};width:calc({at(hi)} - {at(lo)})"></i>'
                   f'<i class="us" style="left:{at(usual)}" title="Usual: {_pct(usual)}"></i>')
        trk += f'<i class="now" style="left:{at(now)};--c:var(--f-{COL[s]})" title="This month: {_pct(now)}"></i>'
        on = t is moved
        if on:
            trk += f'<span class="call" style="left:{at(max(now, usual or 0))}">{escape(note or "Moved most")}</span>'
        small = f"<small>{note}</small>" if note and not on else ""
        out.append(f'<li class="{"on" if on else ""}"><span class="nm">{monthly.STREAMS[s]}</span><span class="trk">{trk}</span>'
                   f'<b class="v">{_pct(now)}</b><span class="ch">{_pts(now - usual) if usual is not None else ""}{small}</span></li>')
    ticks = "".join(f'<span style="left:{k / 10 / scale * 100:.1f}%">{k * 10}%</span>' for k in range(round(scale * 10) + 1))
    return ('<p class="ins-key"><span><i class="sw us"></i>Usual (the months before)</span><span><i class="sw"></i>This month</span></p>'
            f'<ol class="ins-db">{"".join(out)}</ol><div class="ins-axis"><span></span><span class="tk">{ticks}</span></div>')


def _days(daily: list[tuple[date, int]], peaks: list[dict], src: str) -> str:
    """Stories a day as grey columns (weekends lighter), the days that stood out in the accent with a numbered tag and
    a line at a normal weekday, then a table of what drove each of those days."""
    top = max((n for _, n in daily), default=1) or 1
    marks = {p["day"]: k + 1 for k, p in enumerate(peaks)}
    normal = round(median([n for d, n in daily if d.weekday() < 5] or [0]))
    cols = "".join(
        f'<li class="{"we" if d.weekday() >= 5 else ""}{" pk" if d.isoformat() in marks else ""}" title="{d.strftime("%a")} {d.day} {d.strftime("%b")}: {n} {"story" if n == 1 else "stories"}">'
        + (f'<b class="mk" style="bottom:calc({n / top * 100:.1f}% + 5px)">{marks[d.isoformat()]}</b>' if d.isoformat() in marks else "")
        + f'<i style="height:{max(n / top * 100, 1):.1f}%"></i><span>{d.day if d.day in (1, 8, 15, 22, 29) else ""}</span></li>'
        for d, n in daily)
    ref = (f'<span class="ref" style="bottom:{normal / top * 100:.1f}%"><em>Normal weekday ≈ {normal}</em></span>'
           if normal else "")
    rows = "".join(
        f'<tr data-day="{p["day"]}"><td class="dt"><b class="mk">{k + 1}</b>{_day(date.fromisoformat(p["day"]))}</td>'
        '<td><ol><li class="meta">Loading…</li></ol></td>'
        f'<td class="n">{p["x"]:g}×<small>{p["n"]} stories</small></td></tr>' for k, p in enumerate(peaks))
    return (f'<div class="ins-plot"><ol class="ins-days" style="--n:{len(daily)}">{cols}</ol>{ref}</div>'
            '<p class="ins-note">How to read: one column a day, its height the stories that day (weekends lighter). '
            'The numbered columns stood out against a normal day; the table says what drove them.</p>'
            + (f'<table class="mt ins-drv" id="peaks" data-src="{src}"><thead><tr><th>Day</th><th>What drove it</th>'
               f'<th>vs a normal day</th></tr></thead><tbody>{rows}</tbody></table>{PEAKS_JS}' if peaks else ""))


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


def _pace(rows: list[tuple]) -> str:
    """A column a month: the money disclosed, the biggest round its darker top, the amount above, the month below."""
    top = max(r[2] for r in rows) or 1
    cols = "".join(
        f'<li class="{"now" if k == len(rows) - 1 else ""}" title="{monthly.name(m)}: {n} rounds, {money.usd(v)}; '
        f'biggest {escape(co)}, {money.usd(b)}"><span class="amt">{money.usd(v)}</span>'
        f'<span class="col" style="height:{max(v / top * 100, 1):.1f}%"><i style="height:{b / v * 100:.1f}%"></i></span>'
        f'<span class="mo">{date.fromisoformat(m + "-01").strftime("%b")}</span></li>'
        for k, (m, n, v, b, co) in enumerate(rows))
    return (f'<ol class="ins-pace" style="--n:{len(rows)}">{cols}</ol>'
            '<p class="ins-key"><span><i class="sw rest"></i>Other rounds</span><span><i class="sw big"></i>The month\'s biggest round</span></p>')


def _ipos(x: dict, src: str) -> str:
    """IPO talk over the year as small columns, then the month's headlines (loaded in the browser)."""
    top = max(n for _, n in x["trend"]) or 1
    cols = "".join(f'<i class="{"now" if k == len(x["trend"]) - 1 else ""}" style="height:{max(n / top * 100, 3):.0f}%" '
                   f'title="{monthly.name(m)}: {n}"></i>' for k, (m, n) in enumerate(x["trend"]))
    return (f'<div class="ins-ipo"><span class="ins-spark" style="--c:var(--focus)">{cols}</span>'
            f'<span class="meta">IPO headlines a month, past {len(x["trend"])} months</span></div>'
            f'<table class="mt ins-ipot" id="ipo-rows" data-src="{src}"><tbody><tr><td class="meta">Loading…</td></tr></tbody></table>'
            + IPO_JS)


IPO_JS = r"""<script>
(() => {
  const box = document.getElementById("ipo-rows");
  const el = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const day = d => new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", {day: "numeric", month: "short", timeZone: "UTC"});
  fetch(box.dataset.src, {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(d => {
    box.tBodies[0].replaceChildren(...d.ipo.map(e => {
      const tr = el("tr"), a = el("a", null, e.title), td = el("td"); a.href = e.url; a.rel = "noopener";
      td.append(a, el("div", "meta", e.source + (e.outlets > 1 ? " · " + e.outlets + " outlets" : "")));
      tr.append(td, el("td", "when", day(e.date))); return tr; }));
  }).catch(() => box.tBodies[0].replaceChildren(el("tr", "meta", "Couldn't load the headlines. Try reloading the page.")));
})();
</script>"""


def _themes(rows: list[tuple], up: bool) -> str:
    """A row per theme: about how many a month before, how many now, and an arrow."""
    if not rows:
        return '<p class="meta">None this month.</p>'
    return '<ol class="ins-move">' + "".join(
        f'<li title="{escape(t)}: {n} stories, about {round(u)} a month before"><span class="nm">{escape(t)}</span>'
        f'<span class="was">~{round(u)}</span><span class="to">→</span><b class="v">{n}</b>'
        f'<span class="ar {"up" if up else "dn"}">{"▲" if up else "▼"}</span></li>' for t, n, u in rows) + "</ol>"


def _day(d: date) -> str:
    return f'{d.strftime("%A")} {d.day} {d.strftime("%B")}'


def _since(m: str, month: str) -> str:
    """"May" in the same year, "Jan '25" before it."""
    d = date.fromisoformat(m + "-01")
    return d.strftime("%b") if m[:4] == month[:4] else d.strftime("%b ’%y")


# each exhibit's colour: the site's stream fills (Okabe-Ito), full for what matters and a pale mix for the rest
HUE = {"compare": "all", "days": "news", "money": "tool", "pace": "tool", "ipo": "research", "rivals": "policy",
       "risk": "reg", "companies": "news", "themes": "infra", "places": "policy"}
THEME_NAMES = {"Compute & Data Centers": "Data centres", "Image & Video Generation": "Image & video"}  # short labels


def _money(f: dict, month: str) -> str:
    """Three figures, where the money went (rounds by theme) beside the valuations named, then the big deals."""
    rep = '<span class="rep" title="The headline says reportedly, in talks or the like">reported</span>'
    b = f["biggest"]
    score = ('<div class="ins-score">'
             f'<div><b>{f["rounds"]}</b><span>funding rounds</span></div><div><b>{money.usd(f["raised"])}</b><span>disclosed</span></div>'
             + (f'<div><b>{money.usd(b["amount"])}</b><span>biggest · <a href="{escape(b["url"])}" rel="noopener">'
                f'{escape(b["company"])}</a></span></div>' if b else "") + "</div>")
    top = max((t[1] for t in f["themes"]), default=1)
    themes = "".join(
        f'<li class="{"on" if k == 0 else ""}" title="{escape(t)}: {n} rounds, {money.usd(v)}; about {u:.0f} a month before">'
        f'<span class="nm">{escape(THEME_NAMES.get(t, t))}</span><span class="tr"><i style="width:{n / top * 100:.0f}%"></i></span>'
        f'<b class="v">{n}</b><span class="ch">{money.usd(v)}</span></li>' for k, (t, n, v, u) in enumerate(f["themes"]))
    left = (f'<div><h3>Where the money went</h3><ol class="ins-bars ins-fund">{themes}</ol>'
            '<p class="ins-note">How to read: bar = funding rounds in each theme; on the right, the money they disclosed.</p></div>'
            if themes else "")
    right = ""
    if f["ladder"]:
        rows = []
        for r in f["ladder"]:
            note = ""
            if r["before"]:
                v0, m0 = r["before"]
                k = r["valuation"] / v0
                note = (f"×{k:.1f} since {_since(m0, month)}" if k >= 1.05 else f"down from {money.usd(v0)}" if k <= .95
                        else f"same as {_since(m0, month)}")
            rows.append(f'<tr><td><a href="{escape(r["url"])}" rel="noopener">{escape(r["company"])}</a>{rep if r["reported"] else ""}</td>'
                        f'<td class="ch">{note}</td><td class="n">{money.usd(r["valuation"])}</td></tr>')
        right = ('<div><h3>Valuations named</h3><table class="mt ins-val"><tbody>' + "".join(rows) + "</tbody></table>"
                 '<p class="ins-note">Valuations the headlines named this month; the change is against the last one we saw.</p></div>')
    deals = ""
    if f["deals"]:
        rows = "".join(
            f'<tr><td><a href="{escape(d["url"])}" rel="noopener">{escape(d["company"])} {"→" if d["kind"] == "acquisition" else "↔"} '
            f'{escape(d["partner"] or "—")}</a>{rep if d["reported"] else ""}</td>'
            f'<td><span class="dk dk-{d["kind"]}">{"Acquisition" if d["kind"] == "acquisition" else "Compute deal"}</span></td>'
            f'<td class="n">{money.usd(d["amount"])}</td></tr>' for d in f["deals"])
        n, v = f["compute_year"]
        deals = (f'<h3 class="ins-h">Big deals</h3><table class="mt ins-deals"><tbody>{rows}</tbody></table>'
                 + (f'<p class="ins-note">Compute deals reported in {month[:4]} so far: <b>{money.usd(v)}</b> across {n}.</p>' if n else ""))
    return (f'{score}<div class="ins-two ins-money">{left}{right}</div>{deals}'
            '<p class="ins-note">Amounts as the headlines give them, in US dollars.</p>')


def _rivals(rows: list[tuple], opens: Counter) -> str:
    labs = " · ".join(f"{escape(lab)} {n}" for lab, n in opens.most_common())
    line = (f'<p class="ins-opens"><b>Open-weight models on Hugging Face this month:</b> {labs}</p>' if opens else "")
    if not rows:
        return line
    out = []
    for what, us, cn, trend in rows:
        share = cn / (us + cn)
        usual = [v for _, v in trend[:-1]]
        cols = "".join(f'<i class="{"now" if k == len(trend) - 1 else ""}" style="height:{max(v * 100, 3):.0f}%" '
                       f'title="{monthly.name(m)}: China {v:.0%}"></i>' for k, (m, v) in enumerate(trend))
        out.append(f'<li><span class="nm">{what}</span><span class="split" title="US {us}, China {cn}">'
                   f'<i class="us" style="width:{(1 - share) * 100:.1f}%">US {us}</i><i class="cn" style="width:{share * 100:.1f}%">China {cn}</i></span>'
                   f'<span class="ins-spark" style="--c:#E69F00">{cols}</span>'
                   f'<span class="ch">China {share:.0%}{f" · usually {sum(usual) / len(usual):.0%}" if usual else ""}</span></li>')
    return ('<ol class="ins-bars ins-riv">' + "".join(out) + f"</ol>{line}"
            '<p class="ins-note">Counting only the two, and only with 10 or more between them. A paper counts for the '
            'country of each lab or scholar it names; open-weight models are the labs\' uploads to Hugging Face. Small '
            'columns: China\'s share, month by month over the past year.</p>')


def _exposure(rows: list[tuple]) -> str:
    top = max(max(r[1:]) for r in rows) or 1
    def cell(n):
        return (f'<td class="hx" style="--a:{n / top * 70 + 10:.0f}%">{n}</td>' if n else '<td class="hx z">–</td>')
    return ('<table class="mt ins-risk"><thead><tr><th>Company</th><th>In court</th><th>Regulators</th><th>Incidents</th>'
            '</tr></thead><tbody>' + "".join(f'<tr><td>{escape(co)}</td>{cell(a)}{cell(b)}{cell(c)}</tr>' for co, a, b, c in rows)
            + '</tbody></table><p class="ins-note">Stories naming each company with lawsuits, copyright or antitrust (court), '
            'probes, fines or privacy (regulators), and reports in the AI Incident Database.</p>')


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
                         _compare(rows) + f'<p class="ins-note">How to read: each stream\'s share of {monthly.name(month)}\'s stories '
                         f'(filled square) against its average over the {n - 1} months before (hollow). '
                         'A share, not a count, as the count grows with our sources.</p>'))
    # what made the busiest days
    pk = x["peaks"]
    if pk:
        days = [f"{date.fromisoformat(p['day']).day} {date.fromisoformat(p['day']).strftime('%B')}" for p in pk]
        say = f"{['One day', 'Two days', 'Three days'][len(pk) - 1]} stood out: {_and(days)}."
    else:
        say = "No day stood out: the news ran evenly all month."
    sections.append(("days", "What made the busiest days", say, _days(x["daily"], pk, f"/{path(month)}insights.json")))
    # money moves
    f = x["money"]
    if f["rounds"] or f["deals"]:
        say = []
        if f["rounds"]:
            say.append(f"{f['rounds']} funding rounds disclosed {money.usd(f['raised'])}"
                       + (f"; {THEME_NAMES.get(f['themes'][0][0], f['themes'][0][0])} drew the most ({f['themes'][0][1]})."
                          if f["themes"] else "."))
            rich = max(f["themes"], key=lambda t: t[2], default=None)
            if rich and rich is not f["themes"][0] and rich[2] >= .5 * f["raised"]:  # the money in a few big rounds
                say.append(f"{THEME_NAMES.get(rich[0], rich[0])} took {rich[2] / f['raised']:.0%} of the money with "
                           f"{rich[1]} round{'s' if rich[1] > 1 else ''}.")
        if f["deals"]:
            d = f["deals"][0]
            say.append(f"The biggest deal: {d['company']} {'buying' if d['kind'] == 'acquisition' else 'with'} "
                       f"{d['partner'] or 'a partner'}, {money.usd(d['amount'])}{' (reported)' if d['reported'] else ''}.")
        sections.append(("money", "Money moves", " ".join(say), _money(f, month)))
    # funding pace: is the money speeding up, or is it one big round?
    pc = x["pace"]
    if len(pc) >= 3 and pc[-1][0] == month:
        m, n, v, b, co = pc[-1]
        usual = median([r[2] for r in pc[:-1]])
        cmp = ("more than" if v > usual * 1.1 else "less than" if v < usual * .9 else "about the same as")
        say = (f"{monthly.name(month).split()[0]}'s {money.usd(v)} in funding was {cmp} a typical month ({money.usd(usual)}). "
               f"The biggest round, {co} at {money.usd(b)}, was {b / v:.0%} of it.")
        sections.append(("pace", "Funding pace", say, _pace(pc)
                         + '<p class="ins-note">How to read: one column a month, its height the money disclosed in funding '
                           'rounds; the darker top is that month\'s single biggest round. A typical month is the median of '
                           'the months before.</p>'))
    # IPO watch
    ip = x["ipo"]
    n = ip["trend"][-1][1]
    if n >= IPO_MIN:
        before = [k for _, k in ip["trend"][:-1]]
        usual = sum(before) / len(before) if before else 0
        say = (f"IPO talk: {n} headlines about listings, against about {round(usual)} a month."
               if usual else f"IPO talk: {n} headlines about listings.")
        sections.append(("ipo", "IPO watch", say, _ipos(ip, f"/{path(month)}insights.json")
                         + '<p class="ins-note">How to read: headlines that name an IPO, a listing or a filing to go public; '
                           'the most-carried first. Small columns: how many such headlines a month.</p>'))
    # US vs China
    if x["rivals"]:
        def line(what, us, cn, trend):
            now, before = cn / (us + cn), [v for _, v in trend[:-1]]
            usual = sum(before) / len(before) if before else None
            verb = "wrote" if what == "Papers" else "made"
            return (f"China {verb} {now:.0%} of the {what.lower()} from the two ({cn} to {us})"
                    + ("." if usual is None else ", about its usual." if abs(now - usual) < .04
                       else f", {'up' if now > usual else 'down'} from a usual {usual:.0%}."))
        say = " ".join(line(*w) for w in x["rivals"])
        sections.append(("rivals", "US vs China", say, _rivals(x["rivals"], x["opens"])))
    # legal and risk
    if x["exposure"]:
        co, a, b, c = x["exposure"][0]
        parts = [f"{n} {w}" for n, w in ((a, "in court"), (b, "with regulators"), (c, "incidents")) if n]
        sections.append(("risk", "Legal and risk", f"{co} drew the most legal and risk stories: {_and(parts)}.",
                         _exposure(x["exposure"])))
    # companies
    if x["companies"]:
        c0, up = x["companies"][0], _riser(x["companies"])
        say = f"{c0[0]} was in the most stories ({c0[1]})."
        if up and up[0] != c0[0]:
            say += f" {up[0]} rose most ({change(up[1], up[2])})."
        else:
            up = None
        sections.append(("companies", "Companies in the news", say,
                         _bars(x["companies"], *((up[0], f"Rose most · {change(up[1], up[2])}") if up else ()))
                         + f'<p class="ins-note">How to read: bar = stories naming each company; the change is against {last}, the biggest riser in blue.</p>'))
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
                         '<p class="ins-note">Stories a month: about how many in the three months before, and now.</p>'))
    # places
    if x["places"]:
        p0 = x["places"][0]
        say = f"{p0[0]} came up most ({p0[1]})"
        say += f", then {x['places'][1][0]} ({x['places'][1][1]})." if len(x["places"]) > 1 else "."
        say += f" Stories named {x['nplaces']} countries and blocs."
        sections.append(("places", "Where in the world", say,
                         _tiles(x["places"]) + f'<p class="ins-note">Stories naming each place, darker = more. Change against {last}.</p>'))
    # each section is an exhibit headed by its finding (the first sentence); the findings open the page, each a link
    heads = [re.split(r"(?<=[.!?])\s+(?=[A-Z0-9$])", s, maxsplit=1) for _, _, s, _ in sections]
    # ...on a departures board: split-flap numbers, each exhibit's colour as its "airline", the exhibit as its gate
    def flap(n):
        return "".join(f'<b class="fl">{d}</b>' for d in f"{n:02d}")
    found = "".join(f'<tr style="--hue:var(--f-{HUE[k]});--i:{i}"><td class="no">{flap(i)}</td>'
                    f'<td class="fd"><i class="air"></i>{escape(hd[0])}</td>'
                    f'<td class="gt"><a href="/{path(month)}#{k}" aria-label="Exhibit {i}"><span>EX</span>{flap(i)}</a></td></tr>'
                    for i, ((k, *_), hd) in enumerate(zip(sections, heads), 1))
    return (f'<section class="ins-kf"><div class="bd-top"><span class="bd-t">Key findings</span>'
            f'<span class="bd-c">{escape(monthly.name(month).upper())}</span></div><table class="kf"><thead><tr><th>No.</th>'
            f'<th>Finding</th><th>Gate</th></tr></thead><tbody>{found}</tbody></table></section>\n'
            + "".join(f'<section class="ex" id="{k}" style="--hue:var(--f-{HUE[k]})"><p class="ex-k"><b>Exhibit {i}</b>{t}</p><h2>{escape(hd[0])}</h2>'
                      + (f'<p class="ins-say">{escape(hd[1])}</p>' if len(hd) > 1 else "") + f'{h}</section>\n'
                      for i, ((k, t, _, h), hd) in enumerate(zip(sections, heads), 1)))


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write each issue's insights page. Returns the pages' paths."""
    parts = pages.frame(conn, len(cards))
    by_month: dict[str, list[dict]] = {}
    for c in cards:
        by_month.setdefault((c.get("date") or "")[:7], []).append(c)
    paths = []
    issues = [m for m in monthly.months(today) if by_month.get(m)]
    ledger = {m: money.month(cs) for m, cs in by_month.items() if m and m <= issues[-1]} if issues else {}
    for i, m in enumerate(issues):
        x = numbers(m, by_month, ledger)
        p = path(m)
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "insights.json").write_text(json.dumps({"peaks": x["peaks"], "ipo": x["ipo"]["stories"]}, separators=(",", ":"), ensure_ascii=False),
                                               encoding="utf-8")
        prev = f'<a href="/{path(issues[i - 1])}">← {monthly.name(issues[i - 1])}</a>' if i else "<span></span>"
        nxt = f'<a href="/{path(issues[i + 1])}">{monthly.name(issues[i + 1])} →</a>' if i + 1 < len(issues) else "<span></span>"
        html = (f'<div class="mi">\n<div class="ins-head"><div><span class="kind">AI Pulse · Monthly report · Insights</span>'
                f'<h1><span class="hl">{monthly.name(m)} in numbers</span></h1></div><div class="ins-side"><span class="no">{monthly.number(m):02d}</span><button class="ins-pdf" type="button" onclick="window.print()">Save as PDF</button></div></div>\n{body(m, x)}'
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
