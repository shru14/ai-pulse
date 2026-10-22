"""AI consultations (ai-consultations/): governments asking the public about AI, open now or closed in the past 6
months, from each government's own list of consultations, read on every full run. Only consultations whose own title
names AI count (a summary that mentions AI in passing doesn't). Each row is the government's own words: the title,
who is asking, the closing date and, where the list gives one, the published outcome. Linked from Policy's strip.

The lists (terms in terms.py): GOV.UK's search API (open, closed and outcome consultations), the US Federal Register
API (documents taking comments), the European Commission's Have Your Say API, Canada's open data list of federal
consultations. Japan's e-Gov list was left out: its robots.txt refuses this project's reader (403, 17 Oct 2026);
Singapore's REACH: its terms forbid reproducing or displaying its content.
"""
from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from . import feeds, pages, rss, store

PATH = "ai-consultations/"
KEY = "consultations"  # the meta row holding each list's rows and when it was last read
PAST = 183  # days: how far back "Closed" goes
SOON = 14  # days: open consultations closing this soon are marked
# AI named in a title: "AI" itself only in capitals and not inside a word (so "Thai" or "AIS" never count)
AI = re.compile(r"(?<![A-Za-z])AI(?![A-Za-z])|(?i:artificial intelligence|machine learning|algorithm|"
                r"automated decision|deepfake|chatbot|large language model)")
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

# place: (its list, the list's name)
LISTS = {
    "UK": ("https://www.gov.uk/search/policy-papers-and-consultations?content_store_document_type=all_consultations",
           "GOV.UK consultations"),
    "US": ("https://www.federalregister.gov/documents/search?conditions%5Bterm%5D=%22artificial+intelligence%22",
           "Federal Register"),
    "EU": ("https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives_en", "Have Your Say"),
    "Canada": ("https://www.canada.ca/en/government/system/consultations/consultingcanadians.html",
               "Consulting with Canadians"),
}


# The daily job (python -m aipulse consultations, a scheduled Claude routine) checks by hand what the title rule
# misses, and the owner approves each branch: consultations an official list gives whose own summary is about AI, and
# consultations our Policy and Regulation stories report from places whose lists aren't read here. Stories and list
# entries from after CHECKED_TO are its candidates.
CHECKED_TO = "2026-10-17"
# (place, the consultation's title as its official page gives it, who is asking, the last day to respond (YYYY-MM-DD),
#  its official page, the story or list entry it was found through)
ADDED: list[tuple[str, str, str, str, str, str]] = [
    ("US", "Division of Program Coordination, Planning, and Strategic Initiatives, Office of the Director Notice of Proposed Reorganization",
     "Health and Human Services Department, National Institutes of Health", "2026-10-28",
     "https://www.federalregister.gov/documents/2026/10/14/2026-20891/division-of-program-coordination-planning-and-strategic-initiatives-office-of-the-director-notice-of",
     "https://www.federalregister.gov/documents/2026/10/14/2026-20891/division-of-program-coordination-planning-and-strategic-initiatives-office-of-the-director-notice-of"),
    ("UK", "Growing up in the online world: a national consultation", "Department for Science, Innovation and Technology",
     "2026-05-26", "https://www.gov.uk/government/consultations/growing-up-in-the-online-world-a-national-consultation",
     "https://www.gov.uk/government/consultations/growing-up-in-the-online-world-a-national-consultation"),
]
# stories and list entries checked by hand and left out, with why, so they aren't checked again
LEFT_OUT: dict[str, str] = {
    "https://www.federalregister.gov/documents/2026/09/30/2026-20023/request-for-information-rfi-regarding-the-digitization-and-modernization-of-the-national-technical":
        "AI only in passing (data more accessible to AI)",
    "https://www.federalregister.gov/documents/2026/06/05/2026-11353/reforming-the-high-cost-program-for-an-all-ip-future-connect-america-fund-a-national-broadband-plan":
        "AI only in passing (a reason for broadband rules)",
    "https://www.itweb.co.za/article/sa-firms-urged-to-be-more-proactive-with-ai-training-governance/Olx4zMkaB6nv56km":
        "no government asking the public (a conference keynote)",
    "https://www.xataka.com/robotica-e-ia/50-muertos-1-000-millones-dolares-danos-liston-que-anthropic-quiere-fijar-gobierno-pueda-frenar-modelo-ia":
        "a company proposing, no government asking the public",
    "https://the-decoder.com/anthropic-consults-law-firms-to-set-fair-negotiation-norms-before-ai-agents-start-cutting-deals/":
        "a company asking, not a government",
    "https://www.dawn.com/news/2037803/anthropic-proposes-law-regulating-ai-to-us-lawmakers":
        "a company sharing a draft bill with lawmakers, no government asking the public",
    "https://www.federalregister.gov/documents/2026/08/12/2026-16371/request-for-information-rfi-on-modernizing-the-national-vulnerability-database-in-the-age-of":
        "on the US list",
    "https://www.gov.uk/government/calls-for-evidence/data-regulation-in-the-age-of-ai-and-other-data-intensive-technologies":
        "on the UK list",
    "https://www.federalregister.gov/documents/2026/07/10/2026-13928/proposed-information-collection-atus-artificial-intelligence-ai-questions":
        "on the US list",
    "https://www.federalregister.gov/documents/2026/05/28/2026-10602/ai-enabled-optimization-of-early-phase-clinical-trials-pilot-program-request-for-information":
        "on the US list",
    "https://www.federalregister.gov/documents/2026/04/29/2026-08281/ai-enabled-optimization-of-early-phase-clinical-trials-pilot-program-request-for-information":
        "on the US list",
}
# a headline that may report a consultation: the words governments use for asking the public
_ASKS = re.compile(r"\b(consult(s|ed|ing|ation|ations)?|public comments?|call for (evidence|views|input|comments?)|"
                   r"requests? for (comments?|information|input)|seeks? (views|feedback|comments|input)|"
                   r"have your say|feedback on (a |the )?draft|draft (rules|guidelines|regulations?|framework|bill))\b",
                   re.I)


def names_ai(title: str) -> bool:
    return bool(AI.search(title))


def _about_ai(title: str, summary: str) -> bool:
    return names_ai(title) or names_ai(summary)


def _day(s: str) -> str:
    return s[:10]


# --- each list ---

def read_uk(fetcher, since: str) -> list[dict]:
    """GOV.UK's search API: consultations naming AI in the title or summary, open, closed or with the outcome
    published."""
    url = ("https://www.gov.uk/api/search.json?count=1000&order=-public_timestamp"
           "&fields=title,link,description,end_date,organisations,content_store_document_type"
           + "".join(f"&filter_content_store_document_type={t}"
                     for t in ("open_consultation", "closed_consultation", "consultation_outcome")))
    rows = []
    for q in ("%22artificial+intelligence%22", "AI"):
        for r in json.loads(fetcher(f"{url}&q={q}")).get("results") or []:
            closes = _day(r.get("end_date") or "")
            if closes >= since and _about_ai(r.get("title", ""), r.get("description") or ""):
                link = "https://www.gov.uk" + r["link"] if r["link"].startswith("/") else r["link"]
                orgs = [o.get("title", "") for o in r.get("organisations") or [] if o.get("title")]
                rows.append({"place": "UK", "title": r["title"], "url": link, "who": ", ".join(orgs[:2]),
                             "summary": r.get("description") or "",
                             "closes": closes, "outcome": link if r.get("content_store_document_type") ==
                             "consultation_outcome" else ""})
    return rows


def read_us(fetcher, since: str) -> list[dict]:
    """The Federal Register API: rules and notices taking comments, whose comment period ends from `since` on, naming
    AI in the title or abstract."""
    rows = []
    for term in ("%22artificial+intelligence%22", "AI"):
        url = (f"https://www.federalregister.gov/api/v1/documents.json?per_page=1000&order=newest"
               f"&conditions%5Bterm%5D={term}&conditions%5Bcomment_date%5D%5Bgte%5D={since}"
               + "".join(f"&fields%5B%5D={f}" for f in ("title", "abstract", "html_url", "comments_close_on",
                                                                   "agency_names")))
        for d in json.loads(fetcher(url)).get("results") or []:
            if d.get("comments_close_on") and _about_ai(d.get("title", ""), d.get("abstract") or ""):
                rows.append({"place": "US", "title": d["title"], "url": d["html_url"], "summary": d.get("abstract") or "",
                             "who": ", ".join((d.get("agency_names") or [])[:2]), "closes": d["comments_close_on"],
                             "outcome": ""})
    return rows


def read_eu(fetcher, since: str) -> list[dict]:
    """The Commission's Have Your Say API: initiatives naming AI whose feedback period ends from `since` on. The
    search gives the newest first; five pages of 100 reach back well past 6 months."""
    rows = []
    for page in range(5):
        found = json.loads(fetcher("https://ec.europa.eu/info/law/better-regulation/brpapi/searchInitiatives"
                                   f"?text=AI&language=EN&size=100&page={page}"))["initiativeResultDtoPage"]
        for r in found.get("content") or []:
            title = re.sub(r"\s+", " ", r.get("shortTitle") or "").strip()
            for s in r.get("currentStatuses") or []:
                closes = (s.get("feedbackEndDate") or "")[:10].replace("/", "-")
                if closes >= since and names_ai(title):  # the search gives no summary
                    rows.append({"place": "EU", "title": title, "who": "European Commission", "closes": closes,
                                 "url": "https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/"
                                        f"{int(r['id'])}_en", "outcome": ""})
        if found.get("last", True):
            break
    return rows


def read_canada(fetcher, since: str) -> list[dict]:
    """Canada's open data list of federal consultations (a CSV of them all, with each one's report when out)."""
    text = fetcher("https://open.canada.ca/static/consultations_open.csv").decode("utf-8-sig", "replace")
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        if r.get("end_date", "") >= since and _about_ai(r.get("title_en", ""), r.get("description_en", "")):
            report = r.get("report_link_en", "")
            rows.append({"place": "Canada", "title": r["title_en"].strip(), "url": r.get("profile_page_en", ""),
                         "summary": r.get("description_en", ""),
                         "who": r.get("owner_org_title", "").split(" | ")[0], "closes": r["end_date"][:10],
                         "outcome": report if report.startswith("http") else ""})
    return rows


def checked() -> set[str]:
    return {a[4] for a in ADDED} | {a[5] for a in ADDED} | set(LEFT_OUT)


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Policy and Regulation stories from after CHECKED_TO (or `since`, if later) whose headline or summary names AI
    and asking the public, that ADDED and LEFT_OUT don't hold: one per event, newest first."""
    since, done = max(since, CHECKED_TO + "~"), checked()  # '~' sorts after any time of day
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["date"] >= since and c.get("category") in ("policy", "regulation")
            and not any(s["url"] in done for s in [c, *(c.get("also") or [])])
            and _ASKS.search(f"{c['title']} {c.get('summary') or ''}")
            and _about_ai(c["title"], c.get("summary") or "")]


def summary_only(fetcher=feeds.fetch, today: date | None = None) -> list[dict]:
    """The official lists' consultations from the past 6 months whose summary names AI but whose title doesn't (the
    page leaves them out unless checked by hand), that ADDED and LEFT_OUT don't hold; closing soonest first."""
    since = ((today or datetime.now(timezone.utc).date()) - timedelta(days=PAST)).isoformat()
    done, out = checked(), []
    for read in READERS.values():
        out += [r for r in read(fetcher, since) if not names_ai(r["title"]) and r["url"] not in done]
    return sorted({r["url"]: r for r in out}.values(), key=lambda r: r["closes"], reverse=True)


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a consultations/<day> branch: each consultation it adds, and what it left out;
    None when it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("ADDED", "LEFT_OUT"))
    rows = [(p, t, w, _when(c), u, f) for p, t, w, c, u, f in ADDED if u not in had["ADDED"]]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("AI consultations", f"consultation{'s' * (len(rows) != 1)}", branch,
                        ("Place", "Consultation", "Asked by", "Closes", "Official page", "Found through"), rows, dropped)


def health_name(place: str) -> str:
    return f"AI consultations: {LISTS[place][1]} ({place})"


READERS = {"UK": read_uk, "US": read_us, "EU": read_eu, "Canada": read_canada}


def refresh(conn, fetcher=feeds.fetch, today: date | None = None) -> str:
    """Read every list again. A list that can't be read keeps the rows last read, and is logged in the sources table
    like a news source, so one failing 3 runs in a row reaches the project inbox (python -m aipulse source-alert)."""
    today = today or datetime.now(timezone.utc).date()
    since = (today - timedelta(days=PAST)).isoformat()
    saved = load(conn)
    said = []
    for place, read in READERS.items():
        try:
            rows = [r for r in read(fetcher, since) if names_ai(r["title"])]
            seen, out = set(), []
            for r in rows:  # found by both searches: kept once
                if r["url"] not in seen:
                    seen.add(r["url"])
                    out.append(r)
            saved[place] = {"read": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "rows": out}
            said.append(f"{place} {len(out)}")
            store.record_source(conn, health_name(place), LISTS[place][0], ok=True, entries=len(out))
        except Exception as e:
            said.append(f"{place} not read ({e})")
            store.record_source(conn, health_name(place), LISTS[place][0], ok=False, error=str(e) or type(e).__name__)
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (KEY, json.dumps(saved)))
    conn.commit()
    return ", ".join(said)


def load(conn) -> dict:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (KEY,)).fetchone() if conn else None
    return json.loads(row[0]) if row else {}


# --- the page ---

def _when(d: str) -> str:
    y, m, day = d.split("-")
    return f"{int(day)} {_MONTHS[int(m) - 1]} {y}"


def _slug(place: str) -> str:
    return re.sub(r"[^a-z]+", "-", place.lower()).strip("-")


def _place(place: str) -> str:
    """The place's label: a link to its official list where one is read, else its name (rows checked by hand)."""
    if place not in LISTS:
        return f"<span>{escape(place)}</span>"
    url, name = LISTS[place]
    return f'<a href="{escape(url, quote=True)}" rel="noopener" title="{escape(place)}: {escape(name)}">{escape(place)}</a>'


def _row(r: dict, when: str, today: date, same: bool) -> str:
    days = (date.fromisoformat(r["closes"]) - today).days
    left = f'<small>{"today" if days == 0 else "in 1 day" if days == 1 else f"in {days} days"}</small>' \
        if days >= 0 else ""
    title = r["title"]
    outcome = f'<br><a class="cs-out" href="{escape(r["outcome"], quote=True)}" rel="noopener">Outcome published</a>' \
        if r.get("outcome") else ""
    who = r["who"] or "–"
    mark = ' class="rm-soon"' if when == "open" and days <= SOON else ""
    text = escape(f"{title} {who}".lower(), quote=True)
    return (f'<tr{mark} data-place="{r["place"]}" data-when="{when}" data-day="{r["closes"]}" data-text="{text}">'
            f'<td class="rm-d{" rm-same" if same else ""}">{_when(r["closes"])}{left}</td>'
            f'<td><a href="{escape(r["url"], quote=True)}" rel="noopener">{escape(title)}</a>{outcome}</td>'
            f'<td>{escape(who)}</td><td class="rm-lab cs-{_slug(r["place"])}">{_place(r["place"])}</td></tr>')


def _table(rows: list[dict], when: str, today: date) -> str:
    trs = [_row(r, when, today, i > 0 and rows[i - 1]["closes"] == r["closes"]) for i, r in enumerate(rows)]
    return ('<div class="rm-wrap"><table class="mt rm-t cs-t"><thead><tr><th>Closes</th><th>Consultation</th>'
            '<th>Asked by</th><th>Place</th></tr></thead><tbody>' + "".join(trs) + "</tbody></table></div>\n")


def _filters(n: int, places: list[tuple[str, int]], counts: dict) -> str:
    def tags(f: str, label: str, items) -> str:
        return (f'<div class="sh-tabs" role="group" aria-label="{label}" data-f="{f}"><button type="button" '
                f'class="sh-tab" data-v="" aria-pressed="true">All <b>{n}</b></button>'
                + "".join(f'<button type="button" class="sh-tab" data-v="{v}" aria-pressed="false">{escape(t)} '
                          f'<b>{k}</b></button>' for v, t, k in items if k) + "</div>")
    return ('<div class="sh-filters rm-filters">'
            + tags("place", "Place", [(p, p, k) for p, k in places])
            + tags("when", "When", [("open", "Open now", counts["open"]),
                                    ("closed", "Closed, past 6 months", counts["closed"])])
            + '<input type="search" class="sh-q" placeholder="Search titles and who is asking" '
              'aria-label="Search titles and who is asking">'
            f'<p class="sh-count" aria-live="polite">Showing <b>{n}</b> of {n} consultations</p></div>\n')


# the filters, in the reader's browser: every tag set must match, the search every word typed; a table left empty
# is hidden, and each day's date is shown on its first row still showing (as on Models being retired)
SCRIPT = r"""<script>
(()=>{const pg=document.querySelector('.cs'),rows=[...pg.querySelectorAll('tbody tr[data-place]')],q=pg.querySelector('.sh-q'),
count=pg.querySelector('.sh-count b'),none=pg.querySelector('.sh-none'),f={place:'',when:''};
function run(){const words=q.value.toLowerCase().split(/\s+/).filter(Boolean);let n=0;
rows.forEach(r=>{const ok=(!f.place||r.dataset.place===f.place)&&(!f.when||r.dataset.when===f.when)&&words.every(w=>r.dataset.text.includes(w));
r.hidden=!ok;n+=ok});count.textContent=n;none.hidden=n>0;
pg.querySelectorAll('.rm-part').forEach(s=>{let day='',any=false;s.querySelectorAll('tbody tr').forEach(r=>{if(r.hidden)return;any=true;
r.firstElementChild.classList.toggle('rm-same',r.dataset.day===day);day=r.dataset.day});s.hidden=!any})}
pg.querySelectorAll('.sh-tabs').forEach(g=>g.querySelectorAll('.sh-tab').forEach(b=>b.addEventListener('click',()=>{
f[g.dataset.f]=b.dataset.v;g.querySelectorAll('.sh-tab').forEach(t=>t.setAttribute('aria-pressed',t===b));run()})));
q.addEventListener('input',run)})();
</script>"""


def body(saved: dict, today: date) -> str:
    seen = {r["url"] for p in LISTS for r in saved.get(p, {}).get("rows", [])}
    rows = [r for p in LISTS for r in saved.get(p, {}).get("rows", [])] + [
        {"place": p, "title": t, "who": w, "closes": c, "url": u, "outcome": ""}
        for p, t, w, c, u, _ in ADDED if u not in seen]
    now, past = today.isoformat(), (today - timedelta(days=PAST)).isoformat()
    open_ = sorted((r for r in rows if r["closes"] >= now), key=lambda r: (r["closes"], r["place"], r["title"]))
    closed = sorted((r for r in rows if past <= r["closes"] < now), key=lambda r: (r["closes"], r["place"]),
                    reverse=True)
    shown = open_ + closed
    places = [(p, sum(r["place"] == p for r in shown)) for p in dict.fromkeys([*LISTS, *(a[0] for a in ADDED)])]
    asking = [p for p, k in places if k]
    bigs = [(len(open_), "consultations on AI open now"),
            (len(closed), "closed in the past 6 months"),
            (len(asking), "places asked in the past 6 months")]
    out = ['<div class="ft jb rm cs">\n'
           + pages.feature_head(PATH, "AI consultations",
                                "Where can you tell a government what you think about AI and until when?",
                                "Consultations whose title names AI, from the official lists of the UK, the US, the EU "
                                "and Canada. Each title links to the page where you can respond while it is open.")
           + '<div class="rm-bigs">' + "".join(f'<div class="rm-big cs-big{i}"><b>{n}</b><span>{escape(s)}</span></div>'
                                             for i, (n, s) in enumerate(bigs)) + "</div>\n"]
    out.append(_filters(len(shown), places, {"open": len(open_), "closed": len(closed)}))
    if open_:
        out.append('<section class="rm-part"><h2>Open now</h2>\n' + _table(open_, "open", today) + "</section>\n")
    if closed:
        out.append('<section class="rm-part"><h2>Closed · past 6 months</h2>\n' + _table(closed, "closed", today)
                   + "</section>\n")
    out.append('<p class="sh-none" hidden>No consultation matches. Clear a tag or the search.</p>\n')
    read = max((saved[p]["read"] for p in LISTS if p in saved), default="")
    limits = [
        ("Counted", "Consultations whose own title names AI (artificial intelligence, algorithms, automated decisions, "
                    "deepfakes, chatbots), and ones checked by hand whose official summary is about AI or that our "
                    "stories reported from other places."),
        ("Closes", "The last day to respond, as the list gives it. The US counts proposed rules and notices taking "
                   "comments; the EU counts every stage of Have Your Say where feedback is open."),
        ("Marked rows", f"Open consultations closing in the next {SOON} days."),
        ("Place", "A place's name links to its official list where we read one."),
    ]
    if any(r.get("outcome") for r in shown):
        limits.insert(3, ("Outcome published", "Shown where the list links the government's response (GOV.UK and "
                                               "Canada's list do)."))
    if read:
        limits.append(("Last read", f"{_when(read[:10])}, {read[11:16]} UTC"))
    out.append('<section class="jb-lim"><h2>About these consultations</h2>\n<table class="mt jb-small jb-limits">'
               "<tbody>" + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
               + "</tbody></table></section></div>\n" + SCRIPT)
    return "".join(out)


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write the page from the rows last read. Returns its path, or nothing before any list was read."""
    saved = load(conn)
    if not any(v.get("rows") for v in saved.values()) and not ADDED:
        return []
    what = ("Where can you tell a government what you think about AI and until when? Consultations whose title names "
            "AI, from the official lists of the UK, the US, the EU and Canada.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI consultations",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("AI consultations · AI Pulse", what, PATH, body(saved, today), data,
                   pages.frame(conn, len(cards)), ("/policy/", "Back to Policy"),
                   "Titles, dates and who is asking are each government's own, linking to its page."),
        encoding="utf-8")
    return [PATH]
