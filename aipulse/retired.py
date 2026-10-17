"""Models being retired (models-being-retired/): every model OpenAI, Anthropic, Google and Mistral have set a shut-down
date for, read from each lab's own deprecation page on every full run (robots.txt decides for labs' own pages, as for
their blogs). After that date, apps still calling the model get an error. Each row is the lab's own words: the model's
API name, the date, the replacement it recommends and, where the page gives one, the day it told developers. Models
with no date yet, and "not sooner than" dates for models still in full use, are left out. Linked from Releases' strip.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from html import escape, unescape
from pathlib import Path

from . import feeds, pages, rss

PATH = "models-being-retired/"
# lab: (its deprecation page, the page's name as the lab gives it)
LABS = {
    "OpenAI": ("https://platform.openai.com/docs/deprecations", "Deprecations"),
    "Anthropic": ("https://platform.claude.com/docs/en/about-claude/model-deprecations", "Model deprecations"),
    "Google": ("https://ai.google.dev/gemini-api/docs/deprecations", "Gemini deprecations"),
    "Mistral": ("https://docs.mistral.ai/getting-started/models/models_overview/", "Models"),
}
KEY = "retired"  # the meta row holding each lab's rows and when its page was last read
SOON = 30  # days: rows shutting down this soon are marked
PAST = 92  # days: how far back "Already shut down" goes
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
_FULL = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
         "november", "december"]


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).replace(" ,", ",").replace("( ", "(") \
        .replace(" )", ")").replace(" ↗", "").strip()


def _date(s: str) -> str:
    """'January 14, 2027', 'Jan 6, 2027', '2026-09-24' or '9/29/2026' as 2027-01-14; '' when it isn't one day."""
    s = s.strip()
    if m := re.fullmatch(r"(\d{4})-(\d\d)-(\d\d)", s):
        return s
    if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s):
        return f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}"
    if m := re.fullmatch(r"([A-Za-z]{3,9})\.? (\d{1,2}), (\d{4})", s):
        month = next((i for i, n in enumerate(_FULL, 1) if n.startswith(m[1].lower()[:3])), 0)
        if month:
            return f"{m[3]}-{month:02d}-{int(m[2]):02d}"
    return ""


def _tables(html: str) -> list[tuple[str, list[list[str]]]]:
    """Each table on the page as (the heading just above it, its rows of cell texts)."""
    html = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", "", html)
    out = []
    for m in re.finditer(r"(?s)<table.*?</table>", html):
        heads = re.findall(r"(?s)<h[234][^>]*>(.*?)</h[234]>", html[max(0, m.start() - 8000):m.start()])
        rows = [[_text(c) for c in re.findall(r"(?s)<t[hd][^>]*>(.*?)</t[hd]>", tr)]
                for tr in re.findall(r"(?s)<tr.*?</tr>", m.group(0))]
        out.append((_text(heads[-1]) if heads else "", [r for r in rows if r]))
    return out


def _notice(heading: str) -> tuple[str, str]:
    """'2026-10-14: GPT-4 series model deprecations' as ('2026-10-14', 'GPT-4 series model deprecations')."""
    m = re.match(r"(\d{4}-\d\d-\d\d):\s*(.*)", heading)
    return (m[1], m[2]) if m else ("", heading)


def parse_dated(lab: str, html: str) -> list[dict]:
    """OpenAI's and Anthropic's pages: a dated notice per batch (the day developers were told), each with a table of
    shut-down date, model and recommended replacement. OpenAI's notices for whole products (the Evals platform,
    Agent Builder) are a table of dates and updates instead: the row saying it will shut down gives the date."""
    rows = []
    for heading, table in _tables(html):
        told, title = _notice(heading)
        if not told or len(table) < 2:
            continue
        head = [h.lower() for h in table[0]]
        if head[:2] == ["date", "update"]:
            for r in table[1:]:
                if len(r) >= 2 and re.search(r"\bshut (down|off)\b", r[1], re.I) and _date(r[0]):
                    rows.append({"lab": lab, "model": title, "shuts": _date(r[0]), "replace": "", "told": told,
                                 "kind": "product"})
            continue
        if not re.search(r"shutdown|retirement", head[0]):
            continue
        for r in table[1:]:
            if len(r) >= 2 and _date(r[0]):
                rep = r[-1] if len(r) >= 3 else ""
                model = r[1].split(" | ")[0]  # OpenAI's older notices list a snapshot's aliases after it
                rows.append({"lab": lab, "model": model, "shuts": _date(r[0]), "kind": "model", "told": told,
                             "replace": "" if rep in ("", "—", "–", "-") else rep})
    return rows


def parse_google(html: str) -> list[dict]:
    """Google's page: a table per model family of model, release date, shutdown date (the earliest it may happen)
    and recommended replacement; "No shutdown date announced" and "N/A" rows are left out."""
    rows = []
    for _, table in _tables(html):
        head = [h.lower() for h in table[0]] if table else []
        if len(head) < 4 or "shutdown date" not in head:
            continue
        i = head.index("shutdown date")
        for r in table[1:]:
            if len(r) == len(head) and _date(r[i]):
                rows.append({"lab": "Google", "model": r[0], "shuts": _date(r[i]), "told": "", "kind": "model",
                             "replace": r[-1]})
    return rows


def parse_mistral(html: str) -> list[dict]:
    """Mistral's "Deprecated & retired models" table: name, version, API name, the deprecation and retirement dates
    in one cell, and the alternative."""
    rows = []
    for _, table in _tables(html):
        for r in table:
            if len(r) != 5:
                continue
            days = [_date(d) for d in r[3].split()]
            if len(days) == 2 and all(days) and r[2]:
                rows.append({"lab": "Mistral", "model": r[2], "shuts": days[1], "told": days[0], "kind": "model",
                             "replace": r[4]})
    return rows


def parse(lab: str, html: str) -> list[dict]:
    rows = parse_google(html) if lab == "Google" else parse_mistral(html) if lab == "Mistral" \
        else parse_dated(lab, html)
    seen, out = set(), []
    for r in rows:  # a model listed twice on one page (Google's Live API table repeats some) is kept once
        if (r["model"], r["shuts"]) not in seen:
            seen.add((r["model"], r["shuts"]))
            out.append(r)
    return out


def refresh(conn, fetcher=feeds.fetch) -> str:
    """Read every lab's page again. A lab whose page can't be read, or yields nothing, keeps the rows last read."""
    saved = load(conn)
    said = []
    for lab, (url, _) in LABS.items():
        try:
            if not feeds.allowed(url):
                raise RuntimeError("robots.txt refuses")
            rows = parse(lab, fetcher(url).decode("utf-8", "replace"))
            if not rows:
                raise RuntimeError("no dates found")
            saved[lab] = {"read": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "rows": rows}
            said.append(f"{lab} {len(rows)}")
        except Exception as e:
            said.append(f"{lab} not read ({e})")
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (KEY, json.dumps(saved)))
    conn.commit()
    return ", ".join(said)


def load(conn) -> dict:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (KEY,)).fetchone() if conn else None
    return json.loads(row[0]) if row else {}


def _day(d: str) -> str:
    y, m, day = d.split("-")
    return f"{int(day)} {_MONTHS[int(m) - 1]} {y}"


def _row(r: dict, when: str, today: date, same: bool) -> str:
    """A row; data- attributes for the filters. A date shared with the row above is shown once (wide screens)."""
    url, page = LABS[r["lab"]]
    model, rep = (f"<code>{escape(t)}</code>" if re.fullmatch(r"[\w.\-/]+", t) else escape(t) or "–"
                  for t in (r["model"], r["replace"]))  # an API name in code type; a product or family in words
    mark = ' class="rm-soon"' if when == "soon" else ""
    days = (date.fromisoformat(r["shuts"]) - today).days
    left = f'<small>{"today" if days == 0 else "in 1 day" if days == 1 else f"in {days} days"}</small>' \
        if days >= 0 else ""
    text = escape(f'{r["model"]} {r["replace"]}'.lower(), quote=True)
    return (f'<tr{mark} data-lab="{r["lab"]}" data-when="{when}" data-day="{r["shuts"]}" data-text="{text}">'
            f'<td class="rm-d{" rm-same" if same else ""}">{_day(r["shuts"])}{left}</td><td>{model}</td>'
            f'<td class="rm-lab"><a href="{escape(url)}" rel="noopener" title="{r["lab"]}: {page}">{r["lab"]}</a></td>'
            f'<td>{rep}</td><td class="rm-t">{_day(r["told"]) if r["told"] else "–"}</td></tr>')


def _rows(rows: list[dict], when, today: date) -> list[str]:
    return [_row(r, when(r), today, i > 0 and rows[i - 1]["shuts"] == r["shuts"]) for i, r in enumerate(rows)]


def _table(rows: list[str]) -> str:
    return ('<div class="rm-wrap"><table class="mt rm-t"><thead><tr><th>Shuts down</th><th>Model</th><th>Lab</th>'
            '<th>Replace with</th><th>Announced</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table></div>\n")


def _filters(shown: list[dict], counts: dict) -> str:
    """Tags for each lab and for when, each with its count of rows, and a search of model names."""
    def tags(f: str, label: str, items) -> str:
        return (f'<div class="sh-tabs" role="group" aria-label="{label}" data-f="{f}"><button type="button" '
                f'class="sh-tab" data-v="" aria-pressed="true">All <b>{len(shown)}</b></button>'
                + "".join(f'<button type="button" class="sh-tab" data-v="{v}" aria-pressed="false">{escape(t)} '
                          f'<b>{n}</b></button>' for v, t, n in items if n) + "</div>")
    labs = [(lab, lab, sum(r["lab"] == lab for r in shown)) for lab in LABS]
    when = [(k, t, counts[k]) for k, t in (("soon", f"Next {SOON} days"), ("later", "Later"),
                                           ("gone", "Shut down, past 3 months"))]
    return ('<div class="sh-filters rm-filters">' + tags("lab", "Lab", labs) + tags("when", "When", when) +
            '<input type="search" class="sh-q" placeholder="Search model names" aria-label="Search model names">'
            f'<p class="sh-count" aria-live="polite">Showing <b>{len(shown)}</b> of {len(shown)} models</p></div>\n')


# the filters, in the reader's browser: every tag set must match, the search every word typed; a table left empty
# is hidden, and each day's date is shown on its first row still showing
SCRIPT = """<script>
(()=>{const pg=document.querySelector('.rm'),rows=[...pg.querySelectorAll('tbody tr[data-lab]')],q=pg.querySelector('.sh-q'),
count=pg.querySelector('.sh-count b'),none=pg.querySelector('.sh-none'),f={lab:'',when:''};
function run(){const words=q.value.toLowerCase().split(/\s+/).filter(Boolean);let n=0;
rows.forEach(r=>{const ok=(!f.lab||r.dataset.lab===f.lab)&&(!f.when||r.dataset.when===f.when)&&words.every(w=>r.dataset.text.includes(w));
r.hidden=!ok;n+=ok});count.textContent=n;none.hidden=n>0;
pg.querySelectorAll('.rm-part').forEach(s=>{let day='',any=false;s.querySelectorAll('tbody tr').forEach(r=>{if(r.hidden)return;any=true;
r.firstElementChild.classList.toggle('rm-same',r.dataset.day===day);day=r.dataset.day});s.hidden=!any})}
pg.querySelectorAll('.sh-tabs').forEach(g=>g.querySelectorAll('.sh-tab').forEach(b=>b.addEventListener('click',()=>{
f[g.dataset.f]=b.dataset.v;g.querySelectorAll('.sh-tab').forEach(t=>t.setAttribute('aria-pressed',t===b));run()})));
q.addEventListener('input',run)})();
</script>"""


def body(saved: dict, today: date) -> str:
    rows = sorted((r for lab in LABS for r in saved.get(lab, {}).get("rows", [])),
                  key=lambda r: (r["shuts"], r["lab"], r["model"]))
    now, soon, past = today.isoformat(), (today + timedelta(days=SOON)).isoformat(), \
        (today - timedelta(days=PAST)).isoformat()
    ahead = [r for r in rows if r["shuts"] >= now]
    gone = [r for r in rows if past <= r["shuts"] < now][::-1]
    near = sum(r["shuts"] <= soon for r in ahead)
    labs = [lab for lab in LABS if saved.get(lab, {}).get("rows")]
    names = ", ".join(labs[:-1]) + f" and {labs[-1]}" if len(labs) > 1 else "".join(labs)
    bigs = [(near, f"models shut down in the next {SOON} days"),
            (len(ahead) - near, "more have a shut-down date set"),
            (len(gone), "shut down in the past 3 months")]
    out = ['<div class="ft jb rm">\n'
           + pages.feature_head(PATH, "Models being retired", "Which AI models stop working soon, and what replaces them?",
                                f"Every model {escape(names)} have set a shut-down date for, from each lab's own "
                                "deprecation page, read every 6 hours. After that date, apps still calling the model "
                                "get an error.")
           + '<div class="rm-bigs">' + "".join(f'<div class="rm-big"><b>{n}</b><span>{escape(s)}</span></div>'
                                             for n, s in bigs) + "</div>\n"]
    out.append(_filters(ahead + gone, {"soon": near, "later": len(ahead) - near, "gone": len(gone)}))
    if ahead:
        out.append('<section class="rm-part"><h2>Shutting down next</h2>\n'
                   + _table(_rows(ahead, lambda r: "soon" if r["shuts"] <= soon else "later", today)) + "</section>\n")
    if gone:
        out.append('<section class="rm-part"><h2>Already shut down · past 3 months</h2>\n'
                   + _table(_rows(gone, lambda r: "gone", today)) + "</section>\n")
    out.append('<p class="sh-none" hidden>No model matches. Clear a tag or the search.</p>\n')
    read = max((saved[lab]["read"] for lab in labs), default="")
    limits = [
        ("Shuts down", "The date on the lab's page. OpenAI calls it a shutdown date, Anthropic a retirement date and "
         "Mistral a retirement date; Google gives the earliest date it may happen."),
        ("Announced", "The day the lab told developers (OpenAI and Anthropic date each notice; for Mistral, the day "
         "it deprecated the model). Google's page gives none."),
        ("Marked rows", f"Models shutting down in the next {SOON} days."),
        ("Lab", "Each lab's name links to its deprecation page."),
        ("Left out", "Models with no shut-down date yet, and \"not sooner than\" dates for models still in full use."),
    ]
    if read:
        limits.append(("Last read", f"{_day(read[:10])}, {read[11:16]} UTC"))
    out.append('<section class="jb-lim"><h2>About these dates</h2>\n<table class="mt jb-small jb-limits"><tbody>'
               + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
               + "</tbody></table></section></div>\n" + SCRIPT)
    return "".join(out)


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write the page from the rows last read. Returns its path, or nothing before any lab's page was read."""
    saved = load(conn)
    if not any(v.get("rows") for v in saved.values()):
        return []
    what = ("Which AI models stop working soon, and what replaces them? Every model OpenAI, Anthropic, Google and "
            "Mistral have set a shut-down date for, from each lab's own deprecation page.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Models being retired",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("Models being retired · AI Pulse", what, PATH, body(saved, today), data,
                   pages.frame(conn, len(cards)), ("/releases/", "Back to Releases"),
                   "Dates and model names are the labs' own, each linking to the lab's page."),
        encoding="utf-8")
    return [PATH]
