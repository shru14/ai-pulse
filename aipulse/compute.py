"""Compute behind notable models (compute-behind-notable-models/): how much computing went into training each notable
AI model, from Epoch AI's open dataset of notable models (CC BY 4.0, credited on the page), read on every full run.
Each estimate is Epoch's own, with how sure Epoch is of it; models it has no estimate for are counted, never guessed.
Numbers are shown against GPT-4's training run (Epoch's estimate), so 10× means ten times what trained GPT-4.
A model built on another (Epoch's "Base model") has a figure that includes its base model's training, so it is shown
with what it was built on and its own post-training compute where Epoch gives one, and is left out of the largest-run
ranking and labels so a base model's training isn't counted twice.

Model data, not papers, so it is a Research feature page only, never a Research card. Linked from Research's strip.
"""
from __future__ import annotations

import csv
import io
import json
import math
from datetime import date, datetime, timezone
from html import escape
from pathlib import Path

from . import feeds, pages, rss, store

PATH = "compute-behind-notable-models/"
KEY = "compute"  # the meta row holding the dataset's rows and when it was last read
CSV = "https://epoch.ai/data/notable_ai_models.csv"
DATASET = "https://epoch.ai/data/ai-models"  # the dataset's page: its licence, criteria and documentation
HEALTH = "Compute behind notable models: Epoch AI notable models"
QUESTION = "How much computing went into training each notable AI model?"
YARDSTICK = "GPT-4 (Mar 2023)"  # the row every number is measured against
CHART_FROM = 2020  # the chart's first year
MONTHS = 3  # "Newest estimates" and the counts beside it: from the 1st of the month this many months back
TOP = 15  # rows in "The largest training runs"
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def parse(text: str) -> list[dict]:
    """The CSV's rows as the few fields the page shows: model, lab, day, training compute (FLOP, None when Epoch has
    no estimate), how sure Epoch is, the model's own page, whether its weights can be downloaded, the model it was
    built on ('' for none) and its post-training compute (FLOP, None when Epoch gives none)."""
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        day = (r.get("Publication date") or "")[:10]
        if not r.get("Model") or len(day) != 10:
            continue
        flop, post = _float(r.get("Training compute (FLOP)")), _float(r.get("Finetune compute (FLOP)"))
        out.append({"model": r["Model"].strip(), "lab": ", ".join(o.strip() for o in (r.get("Organization") or "").split(",") if o.strip()), "date": day,
                    "flop": flop, "sure": (r.get("Confidence") or "").strip(), "link": (r.get("Link") or "").strip(),
                    "open": (r.get("Model accessibility") or "").startswith("Open weights"),
                    "base": ", ".join(b.strip() for b in (r.get("Base model") or "").split(",") if b.strip()),
                    "post": post})
    return out


def _float(v: str | None) -> float | None:
    try:
        return float(v) if v else None
    except ValueError:
        return None


def own(r: dict) -> bool:
    """A model trained from scratch, not built on another: only these are ranked as training runs."""
    return not r.get("base")


def refresh(conn, fetcher=feeds.fetch) -> str:
    """Read the dataset again. When it can't be read, or yields no estimates, the rows last read are kept; the read is
    logged in the sources table like a news source, so one failing 3 runs in a row reaches the project inbox."""
    try:
        if not feeds.allowed(CSV):
            raise RuntimeError("robots.txt refuses")
        rows = parse(fetcher(CSV).decode("utf-8", "replace"))
        if not any(r["flop"] for r in rows):
            raise RuntimeError("no estimates found")
    except Exception as e:
        store.record_source(conn, HEALTH, CSV, ok=False, error=str(e) or type(e).__name__)
        return f"not read ({e})"
    saved = {"read": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "rows": rows}
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (KEY, json.dumps(saved)))
    conn.commit()
    store.record_source(conn, HEALTH, CSV, ok=True, entries=len(rows))
    return f"{sum(bool(r['flop']) for r in rows)} of {len(rows)} models with an estimate"


def load(conn) -> dict:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (KEY,)).fetchone() if conn else None
    return json.loads(row[0]) if row else {}


# --- the page ---

def _day(d: str) -> str:
    y, m, day = d.split("-")
    return f"{int(day)} {_MONTHS[int(m) - 1]} {y}"


def _month(d: str) -> str:
    return f"{_MONTHS[int(d[5:7]) - 1]} {d[:4]}"


def times(flop: float, base: float) -> str:
    """A training run against GPT-4's: '45×', '1.8×', 'GPT-4' for the same, '1/20' below it."""
    r = flop / base
    if 0.95 <= r < 1.05:
        return "1×"
    if r >= 10:
        return f"{r:,.0f}×"
    if r >= 1:
        return f"{r:.1f}×"
    n = 1 / r
    return f"1/{n:,.0f}" if n < 10 else f"1/{float(f'{n:.2g}'):,.0f}"


def flops(flop: float) -> str:
    """9.4e26 as '9.4 × 10²⁶ FLOP'."""
    e = math.floor(math.log10(flop))
    m = flop / 10 ** e
    sup = str(e).translate(str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻"))
    return f"{m:.2g} × 10{sup}"


def since(today: date) -> str:
    """The 1st of the month MONTHS months back: 1 Jul for any day in October."""
    m = today.year * 12 + today.month - 1 - MONTHS
    return f"{m // 12}-{m % 12 + 1:02d}-01"


def _glance(rows: list[dict], base: dict, today: date) -> str:
    est = [r for r in rows if r["flop"]]
    big = max((r for r in est if own(r)), key=lambda r: r["flop"])
    start = since(today)
    recent = [r for r in rows if r["date"] >= start]
    first = min((r for r in est if own(r) and r["date"][:4] == str(CHART_FROM)), key=lambda r: -r["flop"], default=None)
    tiles = [(times(big["flop"], base["flop"]), f"GPT-4's training compute went into {big['model']} "
              f"({_month(big['date'])}), the largest run trained from scratch with an estimate", "#CC79A7"),
             (f"{sum(bool(r['flop']) for r in recent)} of {len(recent)}", f"notable models released since "
              f"{_day(start)} that have an estimate", "#E69F00")]
    if first:
        tiles.append((f"{big['flop'] / first['flop']:,.0f}×", f"{big['model']}'s compute against {first['model'].split(' (')[0]}'s, "
                      f"the largest run of {CHART_FROM}", "#56B4E9"))
    body = "".join(f'<div class="iw-big" style="--c:{c}"><b>{escape(n)}</b><span>{escape(label)}</span></div>'
                   for n, label, c in tiles)
    return f'<section class="iw-glance"><h2>At a glance</h2>\n<div class="iw-bigs">{body}</div></section>\n'


def chart(rows: list[dict], base: dict, today: date) -> str:
    """Every model from CHART_FROM with an estimate, as a dot: left to right by release day, up by training compute on
    a scale where each line is 100 times the one below. A model built on another is a hollow dot, as its figure
    includes its base model's training. Each year's largest run trained from scratch is named."""
    est = [r for r in rows if r["flop"] and int(r["date"][:4]) >= CHART_FROM]
    if not est:
        return ""
    W, H, L, R, T, B = 900, 460, 128, 18, 14, 34
    x0 = date(CHART_FROM, 1, 1).toordinal()
    x1 = date(today.year + 1, 1, 1).toordinal()
    g = math.log10(base["flop"])
    lo = math.floor((math.log10(min(r["flop"] for r in est)) - g) / 2) * 2
    hi = max(2, math.ceil((math.log10(max(r["flop"] for r in est)) - g) / 2) * 2)

    def x(d: str) -> float:
        return L + (date.fromisoformat(d).toordinal() - x0) / (x1 - x0) * (W - L - R)

    def y(f: float) -> float:
        return T + (hi - (math.log10(f) - g)) / (hi - lo) * (H - T - B)

    parts = []
    for k in range(lo, hi + 1, 2):  # a line every 100 times
        yy = y(base["flop"] * 10 ** k)
        label = "GPT-4" if k == 0 else f"{10 ** k:,}×" if k > 0 else f"1/{10 ** -k:,}"
        parts.append(f'<line class="cg-grid{" cg-base" * (k == 0)}" x1="{L}" x2="{W - R}" y1="{yy:.1f}" y2="{yy:.1f}"/>'
                     f'<text class="cg-y" x="{L - 8}" y="{yy + 4:.1f}">{label}</text>')
    for yr in range(CHART_FROM, today.year + 1):
        xx = x(f"{yr}-01-01")
        parts.append(f'<line class="cg-tick" x1="{xx:.1f}" x2="{xx:.1f}" y1="{H - B}" y2="{H - B + 5}"/>'
                     f'<text class="cg-x" x="{x(f"{yr}-07-01"):.1f}" y="{H - B + 22}">{yr}</text>')
    tops = {}
    for r in filter(own, est):
        if r["date"][:4] not in tops or r["flop"] > tops[r["date"][:4]]["flop"]:
            tops[r["date"][:4]] = r
    for r in sorted(est, key=lambda r: r["flop"]):
        title = escape(f"{r['model']} ({r['lab']}, {_month(r['date'])}): {times(r['flop'], base['flop'])} GPT-4"
                       + (f", built on {r['base']}" if r["base"] else ""))
        parts.append(f'<circle class="cg-dot{"" if own(r) else " cg-built"}" cx="{x(r["date"]):.1f}" cy="{y(r["flop"]):.1f}" r="3.4"><title>{title}'
                     '</title></circle>')
    named = sorted([*tops.values(), base], key=lambda r: r["date"])
    spots = [(x(r["date"]), y(r["flop"])) for r in named]
    line = y(base["flop"])
    boxes = []  # each name's box, so no name is written over another, a named dot or the GPT-4 line

    def clear(b: tuple, own: int) -> bool:
        bx, by, bw, bh = b
        return (bx >= L and bx + bw <= W - R and by >= T and by + bh <= H - B
                and not by - 2 < line < by + bh + 2
                and all(bx + bw + 3 < ox or ox + ow + 3 < bx or by + bh + 2 < oy or oy + oh + 2 < by
                        for ox, oy, ow, oh in boxes)
                and all(not (bx - 6 < sx < bx + bw + 6 and by - 6 < sy < by + bh + 6)
                        for i, (sx, sy) in enumerate(spots) if i != own))

    for i, r in enumerate(named):
        xx, yy = spots[i]
        name = r["model"].split(" (")[0]
        bw, bh = len(name) * 6.9 + 8, 18
        # beside the dot, then centred above or below it, then off to one side, then further off with a line back
        tries = ([(1, 0, False), (-1, 0, False), (0, -16, False), (0, 16, False)]
                 + [(dx, dy, far) for far, dys in ((False, (-14, 14)), (True, (-30, 30, -46, 46))) for dy in dys
                    for dx in (1, -1)])
        for dx, dy, far in tries:
            bx = xx + 8 if dx > 0 else xx - 8 - bw if dx < 0 else xx - bw / 2
            b = (bx, yy + dy - bh / 2, bw, bh)
            if clear(b, i):
                break
        else:
            dx, dy, far = tries[0]
            b = (xx + 8, yy - bh / 2, bw, bh)
        boxes.append(b)
        bx, by = b[0], b[1]
        if dy:  # not level with its dot: a line shows which dot it names
            ex = min(max(xx, bx + 6), bx + bw - 6)  # the box edge nearest the dot, so the line shows its whole length
            ey = by + bh if by + bh < yy else by if by > yy else by + bh / 2
            parts.append(f'<line class="cg-lead" x1="{xx:.1f}" y1="{yy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}"/>')
        parts.append(f'<rect class="cg-label" x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh}" rx="3"/>'
                     f'<circle class="cg-top" cx="{xx:.1f}" cy="{yy:.1f}" r="4.6"/>'
                     f'<text class="cg-name" x="{bx + 4:.1f}" y="{by + 13.5:.1f}">{escape(name)}</text>')
    svg = (f'<svg class="cg" viewBox="0 0 {W} {H}" role="img" aria-label="Training compute of {len(est)} notable '
           f'models since {CHART_FROM}, against GPT-4">{"".join(parts)}</svg>')
    return ('<section><h2>Training compute, model by model</h2>\n<p class="nt-how">Each dot is one notable model since '
            f'{CHART_FROM} with an estimate ({len(est)} models), placed by its release day and how much computing '
            'trained it. Each line up is 100 times the one below; GPT-4 is the bold line. A hollow dot is a model built '
            "on another, so its figure includes that model's training. The largest run of each year trained from "
            f'scratch is named.</p>\n<div class="cg-wrap">{svg}</div></section>\n')


def _rows(rows: list[dict], base: dict, built: bool = True) -> str:
    """Table rows; built=False leaves out "Built on" (the largest runs, where every model was trained from scratch)."""
    def name(r: dict) -> str:
        n = escape(r["model"])
        return f'<a href="{escape(r["link"])}" rel="noopener">{n}</a>' if r["link"].startswith("http") else n

    return "".join(
        f'<tr><td>{name(r)}</td><td>{escape(r["lab"])}</td>' + (f'<td>{escape(r["base"]) or "—"}</td>' if built else "")
        + f'<td>{_month(r["date"])}</td>'
        f'<td class="pn-num"><b>{times(r["flop"], base["flop"])}</b> GPT-4<small>{flops(r["flop"])} FLOP</small>'
        + (f'<small>Post-training: {times(r["post"], base["flop"])} GPT-4</small>' if r["post"] else "") + '</td>'
        f'<td>{escape(r["sure"])}</td><td>{"Yes" if r["open"] else "No"}</td></tr>' for r in rows)


def _head(built: bool = True) -> str:
    return ('<thead><tr><th>Model</th><th>Made by</th>' + '<th>Built on</th>' * built + '<th>Released</th>'
            '<th>Training compute</th><th>How sure Epoch is</th><th>Weights to download</th></tr></thead>')


def _tables(rows: list[dict], base: dict, today: date) -> str:
    est = [r for r in rows if r["flop"]]
    top = sorted(filter(own, est), key=lambda r: -r["flop"])[:TOP]
    start = since(today)
    new = sorted((r for r in est if r["date"] >= start), key=lambda r: r["date"], reverse=True)
    out = (f'<section><h2>The {len(top)} largest training runs from scratch with an estimate</h2>\n'
           f'<table class="mt cg-table">{_head(False)}<tbody>{_rows(top, base, False)}</tbody></table></section>\n')
    if new:
        out += (f'<section><h2>Newest estimates <span class="iw-when">Released since {_day(start)}</span></h2>\n'
                f'<table class="mt cg-table">{_head()}<tbody>{_rows(new, base)}</tbody></table></section>\n')
    return out


def _limits(rows: list[dict], base: dict, read: str, today: date) -> str:
    start = since(today)
    missing = [r for r in rows if not r["flop"] and r["date"] >= start]
    closed = sum(not r["open"] for r in missing)
    notes = [
        ("Source", f"Epoch AI's dataset of notable AI models (CC BY 4.0), last read {_day(read[:10])}. "
         "Notable means it meets Epoch's criteria, such as being the best at something, widely cited or "
         "historically important."),
        ("Estimates", "Epoch's own, from what the makers published, each marked Confident, Likely or Speculative "
         "(Epoch's documentation says what each means)."),
        ("Built on another model", f"{sum(bool(r['base']) for r in rows if r['flop'])} models with an estimate were "
         "built on another model. Epoch's figure for them includes the base model's training, so they aren't ranked "
         "among the largest runs; post-training is shown on its own where Epoch gives it."),
        ("Against GPT-4", f"1× is Epoch's estimate for GPT-4 ({flops(base['flop'])} FLOP, marked {base['sure']}). "
         "FLOP counts the single calculations a computer made while training the model."),
        *([("No estimate", f"{len(missing)} notable models released since {_day(start)} have none, so they aren't "
            f"shown; {closed} of them {'does' if closed == 1 else 'do'}n't share their weights.")] if missing else []),
    ]
    body = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in notes)
    return (f'<section><h2>About these counts</h2>\n<table class="mt pn-notes"><tbody>{body}</tbody></table>'
            f'<p class="nt-how">Data: <a href="{DATASET}" rel="noopener">Epoch AI, Data on AI Models</a>, '
            '<a href="https://creativecommons.org/licenses/by/4.0/" rel="noopener">CC BY 4.0</a>.</p></section>\n')


def page_body(saved: dict, today: date) -> str:
    rows = saved["rows"]
    base = next(r for r in rows if r["model"] == YARDSTICK)
    n = sum(bool(r["flop"]) for r in rows)
    intro = (f"Epoch AI's estimates of the computing used to train {n:,} notable AI models, read from its open dataset "
             "every day. Every number is measured against GPT-4: 1× is what trained GPT-4, 10× is ten times that. "
             "Models with no estimate are counted, never guessed.")
    return ('<div class="ft jb nt">\n' + pages.feature_head(PATH, "Compute behind notable models", QUESTION,
                                                            escape(intro))
            + _glance(rows, base, today) + chart(rows, base, today) + _tables(rows, base, today)
            + _limits(rows, base, saved["read"], today) + '</div>\n')


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write the page from the rows last read. Returns its path, or nothing before the dataset was first read."""
    saved = load(conn)
    if not any(r.get("flop") for r in saved.get("rows", [])) or not any(
            r["model"] == YARDSTICK and r["flop"] for r in saved["rows"]):
        return []
    what = (f"{QUESTION} Epoch AI's estimates of the training compute of notable AI models, measured against GPT-4, "
            "with the largest runs and the newest estimates.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Compute behind notable models",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("Compute behind notable models · AI Pulse", what, PATH, page_body(saved, today), data,
                   pages.frame(conn, len(cards)), ("/research/", "Back to Research"),
                   "Estimates are Epoch AI's (CC BY 4.0); model names link to each model's own page."),
        encoding="utf-8")
    return [PATH]
