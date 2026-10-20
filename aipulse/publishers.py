"""Who publishes AI research on Hugging Face (who-publishes-ai-research/): the year's papers on our Research cards that a
company put out, counted by company, the research subject whose share is rising, and the researchers we follow who
published most. Built only from the Research cards we already hold (no request of its own): a paper counts for a
company when Hugging Face's daily papers list names it as the paper's organization or a company team is an author
(collect.match_companies), or it comes from the company's own research blog. Companies that rarely use the list show
few papers here even when they publish elsewhere, which the page says.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

from . import classify, kind_pages, pages, rss, sources

PATH = "who-publishes-ai-research/"
TITLE = "Who publishes AI research on Hugging Face"
QUESTION = "Which companies share the most AI papers, and which research subject is rising?"
TOP = 15  # company rows shown before "Show all"
MIN = 3  # papers a company needs this year to be listed
PEOPLE = 15  # researcher rows
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
_COMPANY = {n.lower(): n for n in sources.COMPANIES}  # "NVIDIA" (a Hugging Face organization's spelling) is Nvidia
_PEOPLE = {n for n, _ in sources.PROFESSORS} | {n for n, *_ in sources.EXPERTS}


def papers(cards: list[dict], today: date) -> list[dict]:
    """This year's Research cards."""
    year = f"{today.year}-01-01"
    return [c for c in cards if c["category"] == "research" and c["date"] >= year]


def subjects(title: str) -> list[str]:
    """The Research subjects a paper's title names (the Research-by-subject pages' rule)."""
    return [label for label, _, rx in kind_pages.SUBJECTS.values() if re.search(rx, title, re.I)]


def companies(rows: list[dict]) -> list[dict]:
    """[{name, home, papers, subject}] for each company with MIN or more papers, most first."""
    n, subj = Counter(), {}
    for c in rows:
        for name in {_COMPANY[t.lower()] for t in c["tags"] if t.lower() in _COMPANY}:
            n[name] += 1
            subj.setdefault(name, Counter()).update(subjects(c["title"]))
    homes = classify.paper_homes()
    return [{"name": k, "home": homes.get(k, ""), "papers": v,
             "subject": subj[k].most_common(1)[0][0] if subj[k] else ""}
            for k, v in sorted(n.items(), key=lambda kv: (-kv[1], kv[0])) if v >= MIN]


def people(rows: list[dict]) -> list[dict]:
    """[{name, papers, subjects}] for the PEOPLE researchers we follow with the most papers."""
    n, subj = Counter(), {}
    for c in rows:
        for name in {t for t in c["tags"] if t in _PEOPLE}:
            n[name] += 1
            subj.setdefault(name, Counter()).update(subjects(c["title"]))
    return [{"name": k, "papers": v, "subjects": [s for s, _ in subj[k].most_common(2)]}
            for k, v in sorted(n.items(), key=lambda kv: (-kv[1], kv[0]))[:PEOPLE]]


def by_month(rows: list[dict], today: date) -> tuple[list[str], dict[str, list[float]]]:
    """The year's months so far and each subject's share of that month's papers (%)."""
    months = [f"{today.year}-{m:02d}" for m in range(1, today.month + 1)]
    total = Counter(c["date"][:7] for c in rows)
    months = [m for m in months if total[m]]
    hits = Counter((s, c["date"][:7]) for c in rows for s in subjects(c["title"]))
    labels = [label for label, _, _ in kind_pages.SUBJECTS.values()]
    return months, {s: [100 * hits[(s, m)] / total[m] for m in months] for s in labels}


def rising(rows: list[dict], today: date) -> tuple[str, list[str], list[float]] | None:
    """The subject whose share rose most from the year's first 3 months to its last 3 full months, with its monthly
    shares; None when no subject rose or there aren't 6 full months yet."""
    months, shares = by_month(rows, today)
    full = [i for i, m in enumerate(months) if m != f"{today.year}-{today.month:02d}"]
    if len(full) < 6:
        return None
    gain = {s: sum(v[i] for i in full[-3:]) / 3 - sum(v[i] for i in full[:3]) / 3 for s, v in shares.items()}
    best = max(gain, key=gain.get)
    return (best, months, shares[best]) if gain[best] > 0 else None


def _month(m: str) -> str:
    return _MONTHS[int(m[5:]) - 1]


def _glance(comp: list[dict], rise, today: date) -> str:
    home = Counter()
    for r in comp:
        home[r["home"]] += r["papers"]
    bigs = [("#CC79A7", f'{home["China"]:,} vs {home["United States"]:,}',
             f"papers put out by Chinese companies vs US companies in {today.year}")]
    if comp:
        bigs.append(("#E69F00", f'{comp[0]["papers"]}',
                     f'papers from {comp[0]["name"]}, the most of any company in {today.year}'))
    if rise:
        s, months, v = rise
        last = len(months) - 1 - (months[-1] == f"{today.year}-{today.month:02d}")  # the last full month
        bigs.append(("#56B4E9", f"{round(v[0])}% → {round(v[last])}%",
                     f"of papers are about {s.lower()}, {_month(months[0])} vs {_month(months[last])}"))
    tiles = "".join(f'<div class="iw-big" style="--c:{c}"><b>{escape(b)}</b><span>{escape(t)}</span></div>'
                    for c, b, t in bigs)
    return f'<section class="iw-glance"><h2>At a glance</h2>\n<div class="iw-bigs">{tiles}</div></section>\n'


def _companies(comp: list[dict], today: date) -> str:
    def rows(part):
        return "".join(f'<tr><td><b>{escape(r["name"])}</b></td><td>{escape(r["home"])}</td>'
                       f'<td class="pn-num"><b>{r["papers"]}</b></td><td>{escape(r["subject"])}</td></tr>'
                       for r in part)
    head = ('<thead><tr><th>Company</th><th>Based in</th><th>Papers</th><th>Most papers on</th></tr></thead>')
    more = (f'<details class="wp-more"><summary>Show all {len(comp)} companies</summary><table class="mt wp-table">'
            f'{head}<tbody>{rows(comp[TOP:])}</tbody></table></details>' if len(comp) > TOP else "")
    return (f'<section><h2>Papers each company put out in {today.year}</h2>\n'
            f'<table class="mt wp-table">{head}<tbody>{rows(comp[:TOP])}</tbody></table>{more}</section>\n')


def chart(subject: str, months: list[str], v: list[float], today: date) -> str:
    """The rising subject's share each month: one thin line, each month's % on its dot."""
    w, h, top = 640, 160, max(v) * 1.25
    xs = [40 + i * (w - 80) / max(len(v) - 1, 1) for i in range(len(v))]
    ys = [h - 28 - p / top * (h - 60) for p in v]
    now = f"{today.year}-{today.month:02d}"
    dots = "".join(
        f'<circle cx="{x:.0f}" cy="{y:.0f}" r="3.5"/><text class="wp-v" x="{x:.0f}" y="{y - 9:.0f}">{round(p)}%</text>'
        f'<text class="wp-m" x="{x:.0f}" y="{h - 6}">{_month(m)}{" so far" if m == now else ""}</text>'
        for x, y, p, m in zip(xs, ys, v, months))
    line = " ".join(f"{x:.0f},{y:.0f}" for x, y in zip(xs, ys))
    return (f'<section class="wp-rise"><h2>Rising: {escape(subject)}</h2>\n<p class="nt-how">Papers about '
            f'{escape(subject.lower())} as a share of all the papers we read, each month of {today.year}.</p>'
            f'<svg class="wp-chart" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(subject)} papers as a share of '
            f'all papers, by month"><polyline points="{line}"/>{dots}</svg></section>\n')


def _people(ppl: list[dict], today: date) -> str:
    body = "".join(f'<tr><td><b>{escape(r["name"])}</b></td><td class="pn-num"><b>{r["papers"]}</b></td>'
                   f'<td>{escape(", ".join(r["subjects"]))}</td></tr>' for r in ppl)
    return (f'<section><h2>Researchers we follow who published most</h2>\n<table class="mt wp-table"><thead><tr>'
            f'<th>Researcher</th><th>Papers in {today.year}</th><th>Mostly on</th></tr></thead><tbody>{body}</tbody>'
            '</table></section>\n')


def _limits(rows: list[dict], comp: list[dict]) -> str:
    n = sum(any(t.lower() in _COMPANY for t in c["tags"]) for c in rows)
    notes = [
        ("Papers", f"{n:,} of the {len(rows):,} papers we read this year are a company's: Hugging Face's daily papers "
         "list names the company as the paper's organization, a company team is an author, or it comes from the "
         "company's own research blog. Companies that rarely use the list show few papers here even when they "
         "publish elsewhere."),
        ("Companies", f"Those with {MIN} or more papers this year; a paper with two companies counts for both. "
         "Based in is where the company has its head office."),
        ("Subjects", "Read from each paper's title, as on Research's subject pages; a paper can have several, and "
         "some have none."),
        ("Rising", "The subject whose share of papers grew most from the year's first three months to its last "
         "three full months."),
        ("Researchers", "Only the professors and scholars whose papers we follow, not all researchers."),
    ]
    body = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in notes)
    return f'<section><h2>About these counts</h2>\n<table class="mt pn-notes"><tbody>{body}</tbody></table></section>\n'


def page_body(rows: list[dict], today: date) -> str:
    comp, rise = companies(rows), rising(rows, today)
    n = sum(any(t.lower() in _COMPANY for t in c["tags"]) for c in rows)
    intro = (f"{n:,} AI papers that companies put out in {today.year}, counted by "
             "company, mostly from Hugging Face's daily papers list. Also the research subject that is rising, and "
             "the researchers we follow who published most.")
    return ('<div class="ft jb nt wp">\n' + pages.feature_head(PATH, TITLE, QUESTION, escape(intro))
            + _glance(comp, rise, today) + _companies(comp, today) + (chart(*rise, today) if rise else "")
            + _people(people(rows), today) + _limits(rows, comp) + '</div>\n')


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write who-publishes-ai-research/. Returns its path, or nothing when no company paper is among the cards."""
    rows = papers(cards, today)
    if not companies(rows):
        return []
    what = (f"{QUESTION} AI papers companies put out this year, counted by company, the research subject that is "
            "rising, and the researchers we follow who published most.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": TITLE, "description": what,
            "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page(f"{TITLE} · AI Pulse", what, PATH, page_body(rows, today), data, pages.frame(conn, len(cards)),
                   ("/research/", "Back to Research"), "Counts are read from the papers on our Research cards."),
        encoding="utf-8")
    return [PATH]
