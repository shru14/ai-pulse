"""AI fines and bans (ai-fines-and-bans/): what regulators decided under the law against AI products and companies'
use of AI since 2022, in two halves side by side, the same look as AI pacts and orders. Bans: AI products a regulator
banned, blocked or stopped, and whether each was lifted. Fines: fines and settlements paid to a regulator, and whether
each still stands, is challenged in court or was annulled. Every row checked by hand against the regulator's own notice
(a news report where the regulator published none); investigations not yet decided, lawsuits by people and courts
fining lawyers are left out. What governments (rather than regulators) made AI companies do is on AI pacts and orders.
Linked from Regulation's strip.
"""
from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

from . import infra_watch, pages, rss

PATH = "ai-fines-and-bans/"
SINCE = "2022-01-01"

# Bans, blocks and orders to stop, newest first: (day announced, regulator, country, company, what, why, its notice,
# the day it was lifted or None when no lifting has been announced, what the lifting said, its notice)
BANS = [
    ("2026-01-11", "MCMC", "Malaysia", "xAI (Grok)", "Grok blocked in the country",
     "Sexual deepfakes of real people, including women and children",
     "https://www.bernama.com/en/news.php?id=2511254",
     "2026-01-23", "Lifted after X added safeguards", "https://www.bernama.com/en/news.php?id=2516031"),
    ("2026-01-10", "Komdigi", "Indonesia", "xAI (Grok)", "Grok blocked in the country",
     "Sexual deepfakes of real people, including women and children",
     "https://techcrunch.com/2026/01/11/indonesia-blocks-grok-over-non-consensual-sexualized-deepfakes/",
     "2026-02-01", "Lifted with conditions",
     "https://techcrunch.com/2026/02/01/indonesia-conditionally-lifts-ban-on-grok/"),
    ("2025-02-15", "PIPC", "South Korea", "DeepSeek", "New downloads suspended",
     "Sent users' data to companies in China and the US without consent",
     "https://www.nbcnews.com/news/world/south-korea-suspends-new-downloads-deepseek-citing-privacy-concerns-rcna192432",
     "2025-04-28", "Back in app stores after changes",
     "https://ceomorningbrief.theedgemalaysia.com/article/2025/0949/World/24/753217"),
    ("2025-01-30", "Garante", "Italy", "DeepSeek", "Blocked in the country",
     "Would not say what personal data it collects, from where, or whether it is kept in China",
     "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10097450", None, "", ""),
    ("2024-07-02", "ANPD", "Brazil", "Meta", "Ordered to stop training AI on Brazilians' posts",
     "Users weren't told clearly, and opting out was too hard",
     "https://www.gov.br/anpd/pt-br/assuntos/noticias/anpd-determina-suspensao-cautelar-do-tratamento-de-dados-"
     "pessoais-para-treinamento-da-ia-da-meta",
     "2024-08-30", "Allowed again with conditions, never on under-18s' data",
     "https://www.gov.br/anpd/pt-br/assuntos/noticias/meta-cumpre-exigencias-da-anpd-e-podera-retomar-com-"
     "restricoes-o-uso-de-dados-pessoais-para-treinamento-de-inteligencia-artificial"),
    ("2023-12-19", "FTC", "United States", "Rite Aid", "Banned from facial recognition for 5 years",
     "Store cameras wrongly flagged shoppers as shoplifters, more often women and people of colour",
     "https://www.ftc.gov/news-events/news/press-releases/2023/12/rite-aid-banned-using-ai-facial-recognition-after-"
     "ftc-says-retailer-deployed-technology-without", None, "", ""),
    ("2023-03-30", "Garante", "Italy", "OpenAI (ChatGPT)", "ChatGPT blocked in the country",
     "Trained on personal data without a legal basis, no age checks",
     "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/9870847",
     "2023-04-28", "Back after OpenAI made changes",
     "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/9881490"),
    ("2023-02-02", "Garante", "Italy", "Luka Inc. (Replika)", "Ordered to stop using Italians' data",
     "Risks to children and emotionally vulnerable people, no age checks",
     "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/9852506", None, "", ""),
]

# Where a fine stands: its label and the tag's class
STATUSES = {
    "force": ("In force", "fx-in"),
    "challenged": ("Challenged", "fx-ch"),
    "annulled": ("Annulled", "fx-an"),
    "awaiting": ("Awaiting judge", "fx-aw"),
}

# Fines and settlements paid to a regulator, newest first: (day announced, regulator, country, company, amount as set,
# "fine" or "settlement", why, its notice, where it stands (a STATUSES key), what changed and when, its notice)
FINES = [
    ("2026-08-27", "FTC", "United States", "Cox Media Group", "$930,000", "settlement",
     "Sold an “active listening” AI ad service that didn't listen at all",
     "https://www.ftc.gov/news-events/news/press-releases/2026/08/ftc-finalizes-orders-cox-media-group-two-other-"
     "firms-settling-charges-they-deceived-customers-about", "force", "", ""),
    ("2026-08-21", "Dutch DPA (AP)", "Netherlands", "Uber", "€824,990,000", "fine",
     "Automatically switched off drivers' accounts, with no person deciding",
     "https://www.autoriteitpersoonsgegevens.nl/en/current/uber-fined-nearly-825-million-euros-for-automated-driver-"
     "blocking", "challenged", "Uber says it will appeal",
     "https://nos.nl/artikel/2627738-uber-schond-rechten-chauffeurs-ap-legt-megaboete-van-825-miljoen-op"),
    ("2026-07-09", "Garante", "Italy", "Character Technologies (Character.AI)", "€158,000", "fine",
     "Weak age checks, impact assessment done late, unclear privacy notice",
     "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10269594", "force", "", ""),
    ("2026-03-24", "FTC", "United States", "Air AI", "$18,000,000", "settlement",
     "False promises of earnings from its AI calling agents",
     "https://www.ftc.gov/news-events/news/press-releases/2026/03/air-ai-its-owners-will-be-banned-marketing-business-"
     "opportunities-settle-ftc-charges-company-misled", "awaiting",
     "All but $50,000 suspended as the company can't pay; filed for a judge to sign", ""),
    ("2025-05-19", "Garante", "Italy", "Luka Inc. (Replika)", "€5,000,000", "fine",
     "No legal basis for using people's chats, no age checks",
     "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10132048", "force", "", ""),
    ("2024-12-20", "Garante", "Italy", "OpenAI (ChatGPT)", "€15,000,000", "fine",
     "Trained ChatGPT on personal data without a legal basis, a data breach not reported",
     "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10085432", "annulled",
     "Annulled by the Rome court, 18 Mar 2026", "https://www.diritto.it/?p=249907"),
    ("2024-11-22", "Garante", "Italy", "Foodinho (Glovo)", "€5,000,000", "fine",
     "Facial recognition on 35,000 riders and an algorithm they couldn't contest; face scans banned",
     "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10074840", "force", "", ""),
    ("2024-09-03", "Dutch DPA (AP)", "Netherlands", "Clearview AI", "€30,500,000", "fine",
     "Built a face-recognition database from photos scraped off the internet",
     "https://www.autoriteitpersoonsgegevens.nl/en/current/dutch-dpa-imposes-a-fine-on-clearview-because-of-illegal-"
     "data-collection-for-facial-recognition", "force", "", ""),
    ("2024-07-30", "Texas Attorney General", "United States", "Meta", "$1,400,000,000", "settlement",
     "Ran face recognition on Texans' photos without consent",
     "https://www.texasattorneygeneral.gov/news/releases/attorney-general-ken-paxton-secures-14-billion-settlement-"
     "meta-over-its-unauthorized-capture", "force", "", ""),
    ("2024-03-18", "SEC", "United States", "Delphia and Global Predictions", "$400,000", "settlement",
     "Told investors they used AI they didn't have",
     "https://www.sec.gov/newsroom/press-releases/2024-36", "force", "", ""),
    ("2023-04-13", "CNIL", "France", "Clearview AI", "€5,200,000", "fine",
     "Extra penalty for not obeying the 2022 order to delete French people's data",
     "https://www.cnil.fr/en/facial-recognition-cnil-imposes-penalty-payment-clearview-ai", "force", "", ""),
    ("2022-10-20", "CNIL", "France", "Clearview AI", "€20,000,000", "fine",
     "Face-recognition database built without consent",
     "https://www.cnil.fr/en/sanctions-issued-cnil", "force", "", ""),
    ("2022-07-13", "Hellenic DPA", "Greece", "Clearview AI", "€20,000,000", "fine",
     "Face-recognition database built without consent",
     "https://www.dpa.gr/en/en/enimerwtiko/prakseisArxis/imposition-fine-clearview-ai-inc", "force", "", ""),
    ("2022-05-23", "ICO", "United Kingdom", "Clearview AI", "£7,552,800", "fine",
     "Face-recognition database including UK people's photos",
     "https://ico.org.uk/media2/migrated/4020436/clearview-ai-inc-mpn-20220518.pdf", "challenged",
     "Overturned in 2023; restored on appeal in Oct 2025, now before the Court of Appeal",
     "https://ico.org.uk/about-the-ico/media-centre/news-and-blogs/2025/10/uk-upper-tribunal-hands-down-judgment-on-"
     "clearview-ai-inc/"),
    ("2022-03-09", "Garante", "Italy", "Clearview AI", "€20,000,000", "fine",
     "Face-recognition database built without consent",
     "https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/9751323", "force", "", ""),
]

# The regulators' own sites: a link to one says "notice"; any other link (a news report, where the regulator published
# nothing we could find) says "report"
OFFICIAL = ("garanteprivacy.it", "ftc.gov", "sec.gov", "gov.br", "cnil.fr", "dpa.gr", "ico.org.uk",
            "autoriteitpersoonsgegevens.nl", "texasattorneygeneral.gov")

# stories checked by hand and left out, with why, so they aren't checked again
LEFT_OUT: dict[str, str] = {}

# the newest day every story was read for the lists above; the candidates start after it
CHECKED_TO = "2026-10-19"
_REG = re.compile(r"\b(regulator|watchdog|data protection|privacy (authority|regulator|watchdog)|FTC|SEC|attorneys? "
                  r"general|AG|Garante|CNIL|ICO|ANPD|PIPC|DPA|DPC|Ofcom|CMA|authority|commission)\b", re.I)
_ACT = re.compile(r"\b(fines?|fined|penalty|penalties|settle\w*|bans?|banned|blocks?|blocked|suspends?|suspended|"
                  r"orders? \w+ to stop|ordered to stop|lifts?)\b", re.I)
_AI = re.compile(r"\b(AI|A\.I\.|artificial intelligence|chatbot|ChatGPT|OpenAI|Grok|xAI|DeepSeek|Replika|Character\.AI|"
                 r"facial recognition|face recognition|Clearview|algorithm\w*|deepfakes?)\b", re.I)


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Stories from after CHECKED_TO (or `since`, if later) that no row uses and LEFT_OUT doesn't hold: a regulator
    fining, banning or settling with a company over AI, or lifting a ban. One per event, newest first."""
    since = max(since, CHECKED_TO + "~")  # '~' sorts after any time of day, so CHECKED_TO itself is done
    used = {u for r in BANS for u in (r[6], r[9]) if u} | {u for r in FINES for u in (r[7], r[10]) if u} | set(LEFT_OUT)
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["date"] >= since and c.get("category") != "research"
            and not any(s["url"] in used for s in [c, *(c.get("also") or [])])
            and _ACT.search(c["title"]) and _AI.search(c["title"]) and _REG.search(c["title"] + " " + (c.get("summary") or ""))]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a fines/<day> branch: each row it adds or changes, and the stories it left out;
    None when it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("BANS", "FINES", "LEFT_OUT"))
    rows = ([(r[0], f"{r[1]}, {r[2]}", r[3], "Ban", r[4] + (f" (lifted {r[7]}: {r[8]})" if r[7] else ""), r[6])
             for r in BANS if r[6] not in had["BANS"] or (r[9] and r[9] not in had["BANS"])]
            + [(r[0], f"{r[1]}, {r[2]}", r[3], r[5].capitalize(), f"{r[4]}: {r[6]} ({STATUSES[r[8]][0]})", r[7])
               for r in FINES if r[7] not in had["FINES"] or (r[10] and r[10] not in had["FINES"])])
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("AI fines and bans", f"row{'s' * (len(rows) != 1)}", branch,
                        ("Day", "Regulator", "Company", "Kind", "What", "Notice"), rows, dropped)


def _short(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{x.day} {x:%b %Y}"


def _link(url: str) -> str:
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    word = "notice" if any(host == o or host.endswith("." + o) for o in OFFICIAL) else "report"
    return f'<a href="{escape(url)}" rel="noopener">{word}</a>'


def _row(rid: str, day: str, reg: str, country: str, company: str, cells: str, url: str, tag: tuple[str, str],
         after: str) -> str:
    """A row in real columns: day, company, regulator over its country, `cells` (what it did and why), where it
    stands. Its id is what its dot on the time line links to; each cell's data-f is what its column filters by."""
    return (f'<tr id="{rid}"><td class="pc-d" data-f="{day[:4]}">{_short(day)}</td><td><b>{escape(company)}</b></td>'
            f'<td data-f="{escape(f"{reg}, {country}")}">{escape(reg)}<span class="fx-c">{escape(country)}</span></td>'
            f'{cells}<td class="fx-s" data-f="{escape(tag[0])}">'
            f'<span class="pc-k {tag[1]}">{escape(tag[0])}</span>{after}<span class="fx-c">{_link(url)}</span></td></tr>')


def _head(*cols: str) -> str:
    """Headings that open Excel-style filters; the dates list newest first rather than by count."""
    return "<thead><tr>" + "".join(f'<th{" data-seen" * (c == "Date")}>{c}</th>' for c in cols) + "</tr></thead>"


def _count(n: int, noun: str) -> str:
    """The filter bar phones show for the hidden headings, and how many rows the filters leave."""
    return (f'<div class="iw-fbar"></div><p class="iw-count" aria-live="polite">Showing <b>{n}</b> of {n} {noun}. '
            'Pick a ▾ to filter. <button type="button" class="iw-clear" hidden>Clear filters</button></p>')


def _and(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _strip(bans: list, fines: list, today: date) -> str:
    """Every action as a dot on one time line from SINCE to the end of this year, bans above and fines below,
    coloured by where it stands; pointing at a dot names its action, clicking it jumps to its row."""
    lo, hi = date.fromisoformat(SINCE), date(today.year, 12, 31)
    x = lambda d: round((date.fromisoformat(d) - lo).days / (hi - lo).days * 100, 2)

    def dot(rid: str, d: str, tag: tuple[str, str], tip: str) -> str:
        side = " fx-l" if x(d) > 60 else ""  # near the right edge the tip opens to the left
        return (f'<a class="fx-dot {tag[1]}{side}" href="{PATH}#{rid}" style="left:{x(d)}%" aria-label="{escape(tip)}" '
                f'data-tip="{escape(tip)}"></a>')
    years = "".join(f'<i class="fx-gl" style="left:{x(f"{y}-01-01")}%"></i>'
                    f'<span class="fx-yr" style="left:{x(f"{y}-07-01")}%">{y}</span>' for y in range(lo.year, hi.year + 1))
    b = "".join(dot(f"fx-b{n}", d, ("Lifted", "fx-li") if end else ("In force", "fx-in"),
                    f"{_short(d)} · {co} · {w} · {'Lifted' if end else 'In force'}")
                for n, (d, reg, c, co, w, why, u, end, en, eu) in enumerate(bans))
    f = "".join(dot(f"fx-f{n}", d, STATUSES[st], f"{_short(d)} · {co} · {amt} {kind} · {STATUSES[st][0]}")
                for n, (d, reg, c, co, amt, kind, why, u, st, sn, su) in enumerate(fines))
    key = "".join(f'<span class="pc-k {c}">{escape(t)}</span>'
                  for t, c in [("In force", "fx-in"), ("Lifted", "fx-li")] + [v for k, v in STATUSES.items() if k != "force"])
    return (f'<section class="fx-tl"><h2>Every action since {SINCE[:4]}</h2><div class="fx-strip">{years}'
            f'<span class="fx-lane" style="top:6px">Bans · {len(bans)}</span><div class="fx-row" style="top:44px">{b}</div>'
            f'<span class="fx-lane" style="top:70px">Fines · {len(fines)}</span><div class="fx-row" style="top:108px">{f}'
            f'</div></div><p class="fx-key">{key}<span>One dot per action: point at a dot to see it, click to jump to '
            f'its row.</span></p></section>')


def body(today: date) -> str:
    bans = sorted(BANS, key=lambda r: r[0], reverse=True)
    fines = sorted(FINES, key=lambda r: r[0], reverse=True)
    brows = "".join(_row(f"fx-b{n}", d, reg, c, co, f'<td data-f="{escape(w)}"><b>{escape(w)}</b><span class="fx-c">{escape(why)}</span></td>',
                         u, ("Lifted", "fx-li") if end else ("In force", "fx-in"),
                         f'<span class="fx-c"><a href="{escape(eu)}" rel="noopener">{escape(en)}, {_short(end)}</a></span>'
                         if end else "")
                    for n, (d, reg, c, co, w, why, u, end, en, eu) in enumerate(bans))
    frows = "".join(_row(f"fx-f{n}", d, reg, c, co,
                         f'<td class="fx-n" data-f="{kind.capitalize()}">{escape(amt)}<span class="fx-c">{kind}</span></td>'
                         f'<td>{escape(why)}</td>',
                         u, STATUSES[st],
                         (f'<span class="fx-c">' + (f'<a href="{escape(su)}" rel="noopener">{escape(sn)}</a>' if su
                                                    else escape(sn)) + '</span>') if sn else "")
                    for n, (d, reg, c, co, amt, kind, why, u, st, sn, su) in enumerate(fines))
    on = sum(r[7] is None for r in bans)
    blead = (f"{_and(len(bans), 'ban or stop order', 'bans and stop orders')} in "
             f"{_and(len({r[2] for r in bans}), 'country', 'countries')}; {on} still in force.")
    court = sum(r[8] in ("challenged", "annulled") for r in fines)
    counts = {}
    for r in fines:
        counts[r[3]] = counts.get(r[3], 0) + 1
    most = max(counts, key=counts.get) if counts else ""
    flead = (f"{_and(len(fines), 'fine or settlement', 'fines and settlements')} in "
             f"{_and(len({r[2] for r in fines}), 'country', 'countries')}"
             + (f"; {court} challenged or annulled in court" if court else "")
             + (f". {counts[most]} are on {most}." if counts.get(most, 0) > 1 else "."))
    limits = [
        ("What counts", "A regulator deciding under the law against an AI product or a company's use of AI: a ban, "
         "block or order to stop, a fine, or a settlement paid to a regulator. Investigations not yet decided, "
         "lawsuits by people and courts fining lawyers are left out; what governments made AI companies do is on "
         "AI pacts and orders."),
        ("Amounts as set", "Each amount in the currency it was set in. Amounts aren't added up: some were annulled, "
         "suspended or never paid."),
        ("Where it stands", "A ban is in force until a lifting is announced; a fine stands until a court annuls it. "
         "Challenged: the company has appealed or said it will."),
        ("Checked by hand", "Each row links to the regulator's own notice, or to a news report where the regulator "
         "published none; new actions are added once checked."),
    ]
    return ('<div class="ft jb pc fx">\n'
            + pages.feature_head(PATH, "AI fines and bans",
                                 "Which AI products have regulators banned or fined, and does each action still stand?",
                                 f"Bans, blocks, fines and settlements regulators have decided against AI makers and "
                                 f"companies using AI since {SINCE[:4]}. Each row links to the regulator's notice and "
                                 "says whether the action was lifted, challenged or annulled.")
            + _strip(bans, fines, today) + '<div class="fx-stack">'
            f'<section class="pc-half pc-orders"><div class="pc-hh"><h2>Bans</h2><p>AI products a regulator banned, '
            f'blocked or stopped · since {SINCE[:4]}</p></div><div class="pc-in iw"><p class="pc-lead">{escape(blead)}</p>'
            f'{_count(len(bans), "bans")}<table class="pc-rows fx-t xf-t">{_head("Date", "Company", "Regulator", "What and why", "Where it stands")}'
            f'<tbody>{brows}</tbody></table></div></section>'
            f'<section class="pc-half pc-pacts"><div class="pc-hh"><h2>Fines</h2><p>Fines and settlements over AI · '
            f'since {SINCE[:4]}</p></div><div class="pc-in iw"><p class="pc-lead">{escape(flead)}</p>'
            f'{_count(len(fines), "fines")}<table class="pc-rows fx-t xf-t">{_head("Date", "Company", "Regulator", "Amount", "Why", "Where it stands")}'
            f'<tbody>{frows}</tbody></table></div></section></div>\n'
            '<section class="jb-lim"><h2>About these rows</h2>\n<table class="mt jb-small jb-limits"><tbody>'
            + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
            + "</tbody></table></section></div>\n" + infra_watch.SCRIPT + "\n")


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    what = ("Which AI products have regulators banned or fined, and does each action still stand? Every ban, block, "
            "fine and settlement regulators have decided against AI makers and companies using AI since 2022.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI fines and bans",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("AI fines and bans · AI Pulse", what, PATH, body(today), data, pages.frame(conn, len(cards)),
                   ("/regulation/", "Back to the Regulation tracker"),
                   "Every row links to the regulator's own notice, or a news report where it published none, checked "
                   "by hand."),
        encoding="utf-8")
    return [PATH]
