"""Jobs blamed on AI (jobs-blamed-on-ai/): big job cuts the news linked to AI since 2023, each sorted by the reason
the company itself gave, in its own statement, memo or filing: AI now does the work, it cut jobs to spend more on AI,
AI took its customers, it mentioned AI but gave another reason, or it didn't mention AI. The page shows what companies
say, not whether AI was truly the cause, and leads with the number of cuts (a few giants would swing a count of jobs);
its last section says what the cuts can't tell us. Every cut is checked by hand against its
story and listed in CHECKED; only cuts the company confirmed are kept (no unconfirmed reports, forecasts or plans).
`python -m aipulse jobs` lists the job-cut stories not checked yet. The page's numbers and chapter words are worked
out from CHECKED, so they follow it as cuts are added. Linked from Industry's strip on the front page.
"""
from __future__ import annotations

import re
from datetime import date
from fractions import Fraction
from html import escape
from pathlib import Path

from . import pages, rss

PATH = "jobs-blamed-on-ai/"
SINCE = "2023-01-01"

# reason: (its words on the page, its colour: Okabe-Ito, dark text on it)
REASONS = {
    "work": ("Said AI now does the work", "#E69F00"),
    "pay": ("Cut jobs to spend more on AI", "#56B4E9"),
    "hurt": ("Said AI took its customers", "#CC79A7"),
    "mentioned": ("Mentioned AI, gave another reason", "#009E73"),
    "never": ("Didn't mention AI", "#9AA0AA"),
}

# Every cut the page shows, checked by hand, by the URL of the story we read it in: the month the cut was announced
# ("when" when it can't be put in a month), the jobs as the story gives them and as a number to add up (None when
# no number was given), the reason the company gave, and what it said, in short. "also": more sources for its words.
# Checked 13 Oct 2026.
CHECKED: dict[str, dict] = {
    "https://techcrunch.com/2026/07/22/monday-com-lays-off-hundreds-to-focuses-on-ai/":
        dict(company="Monday.com", month="2026-07", jobs="about 630 (20%)", n=630, reason="never",
             said='A “leaner, more focused operating model”'),
    "https://techcrunch.com/2026/07/06/microsoft-lays-off-nearly-5000-employees-across-xbox-commercial-sales/":
        dict(company="Microsoft", month="2026-07", jobs="about 4,800", n=4800, reason="never",
             said='Said the roles “are not being replaced by AI”'),
    "https://techcrunch.com/2026/06/16/robinhoods-note-on-10-layoffs-shows-blaming-ai-isnt-cutting-it/":
        dict(company="Robinhood", month="2026-06", jobs="about 290 (10%)", n=290, reason="never",
             said='A “restructuring exercise”'),
    "https://techcrunch.com/2026/05/25/what-clickups-mass-layoff-tells-us-about-the-future-of-work/":
        dict(company="ClickUp", month="2026-05", jobs="22% of staff", n=None, reason="work",
             said="Staff now direct AI agents"),
    "https://techcrunch.com/2026/05/14/cisco-cuts-nearly-4000-jobs-to-spend-more-on-ai-reports-record-quarterly-revenue/":
        dict(company="Cisco", month="2026-05", jobs="nearly 4,000 (5%)", n=4000, reason="pay",
             said="To invest in AI and cybersecurity"),
    "https://techcrunch.com/2026/05/11/gm-just-laid-off-hundreds-of-it-workers-to-hire-those-with-stronger-ai-skills/":
        dict(company="GM", month="2026-05", jobs="about 600 (IT)", n=600, reason="never",
             said="“Transforming its Information Technology organization”"),
    "https://techcrunch.com/2026/05/08/cloudflare-says-ai-made-1100-jobs-obsolete-even-as-revenue-hit-a-record-high/":
        dict(company="Cloudflare", month="2026-05", jobs="about 1,100 (20%)", n=1100, reason="work",
             said="Fewer support staff needed with AI"),
    "https://the-decoder.com/ai-translation-company-deepl-cuts-around-250-jobs-to-rebuild-as-an-ai-native-organization/":
        dict(company="DeepL", month="2026-05", jobs="about 250", n=250, reason="work",
             said="Rebuilding as “AI-native”"),
    "https://siliconangle.com/2026/04/23/meta-cuts-10-staff-cancels-6000-open-roles-ai-efficiency-push/":
        dict(company="Meta", month="2026-04", jobs="about 8,000 (10%)", n=8000, reason="never",
             said="To “run the company more efficiently” and “offset the other investments we're making”; the memo "
                  "didn't say which investments"),
    "https://techcrunch.com/2026/03/12/atlassian-follows-blocks-footsteps-and-cuts-staff-in-the-name-of-ai/":
        dict(company="Atlassian", month="2026-03", jobs="about 1,600 (10%)", n=1600, reason="pay",
             said="Frees money for AI and enterprise sales"),
    "https://the-decoder.com/block-cuts-nearly-half-its-workforce-as-dorsey-credits-ai-but-the-real-reasons-predate-the-hype/":
        dict(company="Block", month="2026-02", jobs="about 4,000 (40%)", n=4000, reason="work",
             said="AI tools let smaller teams do the work"),
    "https://cset.georgetown.edu/article/amazons-14000-layoffs-underscore-ais-uncertain-impact-on-jobs/":
        dict(company="Amazon", month="2025-10", jobs="about 14,000", n=14000, reason="mentioned",
             said="Called AI “the most transformative technology we've seen since the Internet”, but gave “fewer layers "
                  "and more ownership” as the reason",
             also=[("Amazon's memo to staff", "https://www.aboutamazon.com/news/company-news/amazon-workforce-reduction")]),
    "https://the-decoder.com/indeed-and-glassdoor-are-cutting-1300-jobs-citing-increased-use-of-ai-driven-recruitment/":
        dict(company="Indeed & Glassdoor", month="2025-07", jobs="about 1,300", n=1300, reason="work",
             said="“AI is changing the world, and we must adapt”"),
    "https://techcrunch.com/2025/05/15/programmers-bore-the-brunt-of-microsofts-layoffs-in-its-home-state-as-ai-writes-up-to-30-of-its-code/":
        dict(company="Microsoft", month="2025-05", jobs="about 6,000", n=6000, reason="never",
             said="Fewer management layers"),
    # the story doesn't quote Chegg; its chief executive blamed Google's AI Overviews when announcing the cut
    "https://the-decoder.com/chatgpt-forces-education-startup-chegg-to-make-massive-job-cuts/":
        dict(company="Chegg", month="2025-05", jobs="about 250 (22%)", n=250, reason="hurt",
             said="Google's AI answers in search cut its visitors"),
    "https://the-decoder.com/ibm-says-ai-and-ai-agents-have-cut-hundreds-of-hr-jobs/":
        dict(company="IBM", month="2025-05", jobs="several hundred (HR)", n=None, reason="work",
             said="AI agents do HR tasks; total staff grew"),
    "https://techcrunch.com/2024/03/07/turnitin-laid-off-staff-earlier-this-year-after-ceo-forecast-ai-would-allow-it-to-cut-headcount/":
        dict(company="Turnitin", month="2024-01", when="Early 2024", jobs="about 15", n=15, reason="never",
             said="To “evolve our business strategy”"),
    "https://techcrunch.com/2024/01/09/duolingo-cut-10-of-its-contractor-workforce-as-the-company-embraces-ai/":
        dict(company="Duolingo", month="2023-12", jobs="10% of contractors", n=None, reason="work",
             said="Said AI was partly behind it"),
    "https://techcrunch.com/2023/11/28/dataminr-the-4b-big-data-startup-is-laying-off-20-of-staff-today-or-150-people-as-it-preps-to-double-down-on-ai/":
        dict(company="Dataminr", month="2023-11", jobs="about 150 (20%)", n=150, reason="pay",
             said="To focus on its AI platform"),
    "https://the-decoder.com/amazon-cuts-hundreds-from-its-alexa-team-in-order-to-maximize-resources-on-generative-ai/":
        dict(company="Amazon (Alexa)", month="2023-11", jobs="several hundred", n=None, reason="pay",
             said="Moving resources to generative AI"),
}

# Job-cut stories checked and left out, so `python -m aipulse jobs` doesn't list them again: unconfirmed reports,
# forecasts and plans, cuts no one blamed on AI, and stories we can't read to check the company's words.
LEFT_OUT = {
    "https://the-decoder.com/employee-revolt-and-failing-agents-forced-meta-to-scrap-its-ai-layoff-plan/",  # a plan
    "https://techcrunch.com/2026/07/25/the-running-list-major-tech-layoffs-in-2026-where-employers-cited-ai/",  # a list
    "https://techcrunch.com/2026/06/08/as-openai-files-for-ipo-sam-altmans-eye-scanning-company-is-doing-layoffs-report-says/",
    "https://techcabal.com/2026/04/16/sama-lay-off-kenyan-workers-meta/",  # a contract ended; not blamed on AI
    "https://the-decoder.com/oracle-reportedly-lays-off-thousands-of-employees-to-bankroll-its-massive-ai-infrastructure-bet/",
    "https://the-decoder.com/oracle-to-cut-thousands-of-jobs-as-ai-spending-drains-cash/",  # unconfirmed
    "https://siliconangle.com/2026/03/15/report-meta-lay-off-20-staff-replace-many-ai-workers/",
    "https://techcrunch.com/2026/03/14/meta-reportedly-considering-layoffs-that-could-affect-20-of-the-company/",
    "https://the-decoder.com/meta-reportedly-plans-to-cut-up-to-20-percent-of-its-workforce-as-600-billion-ai-bet-drives-need-to-offset-costs/",
    "https://the-decoder.com/zuckerberg-reportedly-trades-headcount-for-compute-as-meta-readies-to-cut-10-percent-of-its-workforce-to-fund-ai-infrastructure/",
    "https://techcabal.com/2026/02/28/zap-africa-layoffs/",  # the outlet refuses automated reads: can't check
    "https://techcabal.com/2025/11/13/jumia-narrows-losses-in-q3-2025/",  # likewise
    "https://techcrunch.com/2026/01/01/european-banks-plan-to-cut-200000-jobs-as-ai-takes-hold/",  # a forecast
    "https://siliconangle.com/2025/10/22/meta-lays-off-600-ai-workers-looks-streamline-superintelligence-labs/",
    "https://techcrunch.com/2025/10/22/meta-cuts-600-ai-jobs-amid-ongoing-reorganization/",  # an AI team, not AI's doing
    "https://techcrunch.com/2025/09/13/xai-reportedly-lays-off-500-workers-from-data-annotation-team/",
    "https://techcrunch.com/2025/07/16/scale-ai-lays-off-14-of-staff-largely-in-data-labeling-business/",
    "https://techcrunch.com/2025/07/09/microsoft-shares-500m-in-ai-savings-internally-days-after-cutting-9000-jobs/",  # no reason given
    "https://techcrunch.com/2024/03/08/ai-fraud-detection-software-maker-inscribe-ai-lays-off-40-of-staff/",
    "https://the-decoder.com/startup-claims-to-have-replaced-90-percent-of-its-support-staff-with-a-chatbot/",  # a claim
    "https://the-decoder.com/axel-springer-announces-first-ai-related-layoffs/",  # no number, unconfirmed mail
    "https://techcrunch.com/2023/03/13/microsoft-lays-off-an-ethical-ai-team-as-it-doubles-down-on-openai/",
    "https://siliconangle.com/2024/04/18/stability-ai-lay-off-10-staff-wake-resignation-ceo/",
    "https://techcrunch.com/2023/01/24/soundhound-the-voice-ai-company-raises-25m-after-laying-off-40-of-staff-earlier-this-month/",
    "https://siliconangle.com/2023/01/10/ai-unicorn-scale-ai-valued-7-3-billion-lays-off-20-staff/",
}

# a headline (or the start of its summary) about jobs being cut
CUT = re.compile(r"layoffs?|lay(s|ing)? off|laid off|job cuts?|cut(s|ting)? (\S+ ){0,3}(jobs|workforce|staff|headcount|"
                 r"roles|positions|employees|workers)|[\d,]+ (jobs|roles|positions) (cut|eliminated|axed|obsolete)|"
                 r"eliminat\w+ (\S+ ){0,2}(jobs|roles|positions)|redundancies", re.I)
QUESTION = "When companies cut jobs, what do they say about AI?"
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def cuts(cards: list[dict]) -> list[dict]:
    """The cuts in CHECKED whose story we have, newest first, each with its story (title, source, date, url)."""
    by_url = {s["url"]: s for c in cards for s in [c, *(c.get("also") or [])]}
    out = []
    for url, cut in CHECKED.items():
        if s := by_url.get(url):
            y, m = cut["month"].split("-")
            out.append(cut | {"url": url, "title": s["title"].strip(), "source": s["source"], "date": s["date"],
                              "when": cut.get("when") or f"{_MONTHS[int(m) - 1]} {y}"})
    return sorted(out, key=lambda c: (c["month"], c["date"]), reverse=True)


def candidates(cards: list[dict], since: str = SINCE) -> list[dict]:
    """Job-cut stories from `since` that are neither in CHECKED nor LEFT_OUT: one per event, newest first."""
    out = []
    for c in sorted(cards, key=lambda c: c["date"], reverse=True):  # a card is one event, its other stories in "also"
        if c["date"] < since or c["category"] == "research":
            continue
        if any(s["url"] in CHECKED or s["url"] in LEFT_OUT for s in [c, *(c.get("also") or [])]):
            continue
        if CUT.search(c["title"]) or CUT.search((c.get("summary") or "")[:400]):
            out.append(c)
    return out


def _share(part: int, whole: int) -> str:
    """A share in plain words, the simplest fraction near it: "about 1 in 7", "nearly 3 in 4"."""
    p = Fraction(part, whole)
    fs = [Fraction(a, b) for b in (2, 3, 4, 5, 10, 6, 7, 8, 9) for a in range(1, b) if Fraction(a, b).denominator == b]
    f = next((f for f in fs if abs(f - p) <= Fraction(1, 50)), None) or min(fs, key=lambda f: abs(f - p))
    word = "nearly" if f - p > Fraction(1, 100) else "just over" if p - f > Fraction(1, 100) else "about"
    return f"{word} {f.numerator} in {f.denominator}"


def _num(n: int) -> str:
    """Jobs added up from "about" figures, to the nearest 50 (exact below 1,000)."""
    return f"{n:,}" if n < 1000 else f"{(n + 25) // 50 * 50:,}"


def _cuts_word(n: int) -> str:
    return f"{n} cut{'s' * (n != 1)}"


def _names(xs: list[str]) -> str:
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _table(rows: list[dict]) -> str:
    def src(c: dict) -> str:
        day = date.fromisoformat(c["date"])
        links = [f'<a href="{escape(c["url"])}" rel="noopener">{escape(c["source"])}, {day.day} {_MONTHS[day.month - 1]} '
                 f'{day.year} — {escape(c["title"])}</a>']
        links += [f'<a href="{escape(u)}" rel="noopener">{escape(w)}</a>' for w, u in c.get("also") or []]
        return f'<div class="src">Source{"s" * (len(links) > 1)}: {" · ".join(links)}</div>'
    body = "".join(f'<tr><td class="when">{escape(c["when"])}</td><td class="co">{escape(c["company"])}</td>'
                   f'<td class="jn">{escape(c["jobs"])}</td><td>{escape(c["said"])}{src(c)}</td></tr>' for c in rows)
    return ('<table class="mt jb-cuts"><thead><tr><th>When</th><th>Company</th><th>Jobs cut</th>'
            f'<th>What the company said</th></tr></thead><tbody>{body}</tbody></table>')


# what each reason means: the page's words describe the groups and count them, never draw a conclusion
MEANS = {
    "work": "The company said AI tools now do work that people did.",
    "pay": "The company said the cut frees money to spend on AI.",
    "hurt": "The company said AI products took business away from it.",
    "mentioned": "The company spoke about AI when announcing the cut, but gave another reason.",
    "never": "The company gave other reasons and didn't mention AI.",
}


def _limits(rows: list[dict], total: int) -> str:
    """What these cuts can't tell us, as a table: each limit and why it matters."""
    top = max((c for c in rows if c["n"]), key=lambda c: c["n"], default=None)
    unknown = sum(not c["n"] for c in rows)
    edge = [c for c in rows if c["reason"] == "mentioned"]
    limits = [
        ("What a company says isn't always the whole story",
         "A company may leave AI out of its reasons, or credit AI for a cut with other causes. The page shows what "
         "each company said, not whether AI was the cause."),
        ("Only announced layoffs",
         "Jobs that are never filled, or hiring that stops, don't appear in layoff announcements."),
        (f"{len(rows)} cuts from the news we read",
         "Big cuts that outlets we read linked to AI: not every job cut, and not a count of jobs lost to AI."),
    ]
    if top and total:
        limits.append(("A few big cuts weigh heavily",
                       f"{top['company']}'s {top['n']:,} jobs are {_share(top['n'], total)} of the jobs we could count, "
                       "so totals of jobs move with a single company. The bars count cuts."))
    if edge:
        limits.append(("Some cuts are judgement calls",
                       f"{_names([c['company'] for c in edge])} spoke about AI but gave another reason. Each cut is put "
                       "where its own words point, and they are quoted."))
    limits.append(("Some cuts are missing or partly known",
                   (f"{unknown} cut{'s' * (unknown != 1)} gave no job count. " if unknown else "")
                   + "Cuts the company didn't confirm, and stories we couldn't read to check, are left out."))
    body = "".join(f"<tr><td><b>{escape(a)}</b></td><td>{escape(b)}</td></tr>" for a, b in limits)
    return ('<section class="jb-lim"><h2>What these cuts can\'t tell us</h2>\n<table class="mt jb-limits"><thead><tr>'
            f'<th>Limit</th><th>Why it matters</th></tr></thead><tbody>{body}</tbody></table></section>\n')


def _jobs_text(n: int) -> str:
    return f" · about {_num(n)} jobs" if n else ""


def page_body(rows: list[dict]) -> str:
    """The page under the masthead: the cuts by the reason the company gave, the cuts per year, each reason's cuts,
    and what the cuts can't tell us. Every number is worked out from the rows."""
    counted = [c for c in rows if c["n"]]
    total = sum(c["n"] for c in counted)
    groups = {k: [c for c in rows if c["reason"] == k] for k in REASONS}
    jobs = {k: sum(c["n"] for c in g if c["n"]) for k, g in groups.items()}
    first = min((c["month"][:4] for c in rows), default=SINCE[:4])
    intro = (f"{len(rows)} big job cuts since {first} that the news linked to AI, each with the reason the company gave "
             "in its own statement, memo or filing. Only cuts the company confirmed are listed; new ones are added once "
             "checked.")
    # by reason: one bar per reason, its length the number of cuts
    top = max(len(g) for g in groups.values()) or 1
    bars = "".join(
        f'<div class="jb-bar" style="--c:{colour}"><div class="lab">{escape(label)}</div><div class="trk"><i style="width:'
        f'{len(groups[k]) / top * 100:.1f}%"></i></div><div class="val"><b>{_cuts_word(len(groups[k]))}</b>'
        f'{_jobs_text(jobs[k])}</div></div>'
        for k, (label, colour) in REASONS.items() if groups[k])
    uncounted = [c["company"] for c in rows if not c["n"]]
    note = (f"Each bar counts cuts. Jobs are added up where a number was given (about {_num(total)} in all)"
            + (f"; {_names(uncounted)} gave none." if uncounted else "."))
    # per year: one bar per year, split by reason in the same colours
    years = sorted({c["month"][:4] for c in rows})
    most = max((sum(c["month"][:4] == y for c in rows) for y in years), default=1)
    yrows = ""
    for y in years:
        ys = [c for c in rows if c["month"][:4] == y]
        segs = "".join(f'<i style="--c:{colour};width:{sum(c["reason"] == k for c in ys) / most * 100:.1f}%" '
                       f'title="{escape(label)}: {sum(c["reason"] == k for c in ys)}"></i>'
                       for k, (label, colour) in REASONS.items() if any(c["reason"] == k for c in ys))
        yrows += (f'<div class="jb-bar jb-yr"><div class="lab">{y}</div><div class="trk">{segs}</div><div class="val">'
                  f'<b>{_cuts_word(len(ys))}</b>{_jobs_text(sum(c["n"] for c in ys if c["n"]))}</div></div>')
    key = "".join(f'<span><i style="--c:{colour}"></i>{escape(label)}</span>' for k, (label, colour) in REASONS.items()
                  if groups[k])
    chapters = ""
    for k, (label, colour) in REASONS.items():
        if groups[k]:
            chapters += (f'<section class="jb-ch"><h2 style="--chip:{colour}">{escape(label)}: '
                         f'{_cuts_word(len(groups[k]))}</h2>\n<p class="intro">{escape(MEANS[k])}</p>\n'
                         f'{_table(groups[k])}</section>\n')
    return (f'<div class="ft jb">\n<h1>Jobs blamed on AI</h1>\n<p class="jb-q">{escape(QUESTION)}</p>\n'
            f'<p class="intro">{escape(intro)}</p>\n'
            f'<section class="jb-answer"><h2>The cuts, by the reason the company gave</h2>\n'
            f'<div class="jb-bars">{bars}</div>\n<p class="jb-note">{escape(note)}</p></section>\n'
            f'<section class="jb-years"><h2>The cuts, by year</h2>\n<div class="jb-key">{key}</div>\n'
            f'<div class="jb-bars">{yrows}</div>\n<p class="jb-note">Each bar counts the cuts announced that year, '
            f'coloured by the reason the company gave.</p></section>\n{chapters}{_limits(rows, total)}</div>\n')


def lists_in(source: str) -> tuple[set[str], set[str]]:
    """The URLs in CHECKED and LEFT_OUT of another copy of this file (main's, to tell what a branch adds)."""
    import ast
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                if isinstance(t, ast.Name) and t.id in ("CHECKED", "LEFT_OUT"):
                    items = node.value.keys if isinstance(node.value, ast.Dict) else node.value.elts
                    found[t.id] = {k.value for k in items if isinstance(k, ast.Constant)}
    return found.get("CHECKED", set()), found.get("LEFT_OUT", set())


def note(new: dict[str, dict], dropped: list[str], branch: str) -> tuple[str, str, str]:
    """(subject, text, html) of the project inbox's note: the cuts a jobs/<day> branch adds to CHECKED, a row each, the
    stories it adds to LEFT_OUT, and how to publish them (they go live only once approved)."""
    from .glossary import REPO
    n = len(new)
    subject = f"AI Pulse, Jobs blamed on AI: {n} new cut{'s' * (n != 1)} to approve"
    lead = f"Drafted today on the branch {branch}, not on the site yet:"
    tail = f"To publish them, tell Claude: merge {branch}. To change one, say which. Changes: {REPO}/compare/main...{branch}"
    left = f"Also checked and left out: {len(dropped)} stor{'ies' if len(dropped) != 1 else 'y'}." if dropped else ""
    text = [lead, ""] + [f"{c['company']}, {c['month']}: {c['jobs']} ({REASONS[c['reason']][0]})\n  {c['said']}\n  {u}\n"
                         for u, c in new.items()] + ([left, ""] if left else []) + [tail]
    cell = 'style="padding:8px 10px;border-bottom:1px solid #e3e5e8;vertical-align:top;font-size:14px"'
    rows = "".join(f'<tr><td {cell}><b>{escape(c["company"])}</b></td><td {cell}>{escape(c["month"])}</td>'
                   f'<td {cell}>{escape(c["jobs"])}</td><td {cell}>{escape(REASONS[c["reason"]][0])}</td>'
                   f'<td {cell}>{escape(c["said"])}</td><td {cell}><a href="{escape(u)}" style="color:#1a4fd6">Story</a></td>'
                   '</tr>' for u, c in new.items())
    html = ('<!doctype html><html><body style="margin:0;padding:16px;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a">'
            f'<p style="font-size:15px">{escape(lead)}</p>'
            '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;max-width:820px"><tr>'
            + "".join(f'<th align="left" {cell}>{h}</th>' for h in ("Company", "Month", "Jobs", "Reason", "What it said",
                                                                    "Source"))
            + f'</tr>{rows}</table>' + (f'<p style="font-size:14px">{escape(left)}</p>' if left else "")
            + f'<p style="font-size:13px;color:#5f6368">To publish them, tell Claude: merge {escape(branch)}. To change one, '
            f'say which. <a href="{REPO}/compare/main...{escape(branch)}" style="color:#1a4fd6">See the changes</a></p>'
            '</body></html>')
    return subject, "\n".join(text), html


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write jobs-blamed-on-ai/. Returns its path."""
    rows = cuts(cards)
    (out / PATH).mkdir(parents=True, exist_ok=True)
    what = (f"{QUESTION} Big job cuts the news linked to AI since 2023, each checked against the reason the company "
            "itself gave.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Jobs blamed on AI",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH / "index.html").write_text(
        pages.page("Jobs blamed on AI · AI Pulse", what, PATH, page_body(rows), data, pages.frame(conn, len(cards)),
                   ("/industry/", "Back to Industry"),
                   "Headlines are the outlets' own, each linking to its story. New cuts are added once checked by hand."),
        encoding="utf-8")
    return [PATH]
