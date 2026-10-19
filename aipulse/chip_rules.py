"""Chip export rules (chip-export-rules/): who may sell AI chips to whom, and how each rule changed since 2022.
Infra's feature. At the top, a grid of what Nvidia and AMD could sell to China under each US decision since 2022, a
chip per row (most powerful at the top) and a decision per column, so the chips made for China and caught a column
later stand out. Under it, the other moves in three short lists: tools and memory, who else may buy, and China's
answers. Every cell and row checked by hand against the official notice (the Federal Register for US rules), the
companies' own SEC filings, or a news report where neither exists (footnoted in small type under the page).
"""
from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

from . import pages, rss

PATH = "chip-export-rules/"
SINCE = "2022-01-01"

# The US decisions the grid has a column for: (small word above, the month, its notice or None)
COLUMNS = [
    ("Before", "Oct 2022", None),
    ("Rule", "Oct 2022", "https://www.federalregister.gov/documents/2022/10/13/2022-21658"),
    ("Rule", "Oct 2023", "https://www.federalregister.gov/documents/2023/10/25/2023-23055"),
    ("Letters", "Apr 2025", "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000082/nvda-20250409.htm"),
    ("Licences", "Aug 2025", "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000209/nvda-20250727.htm"),
    ("Rule · now", "Jan 2026", "https://www.federalregister.gov/documents/2026/01/15/2026-00789"),
]

# What the US required for each chip sold to China in each column's period: ok sold freely, cb a licence decided
# case by case, no a licence presumed refused, na not on sale yet. (maker, chip, other names, made for China, cells,
# a word in the last cell). Most powerful first. Sources: Nvidia's 8-Ks of 26 Aug 2022, 23 Oct 2023 and 9 Apr 2025
# and its 10-Q of Aug 2025; AMD's 10-Q of Nov 2022 (MI250), 8-K of 15 Apr 2025 and 10-Q of Nov 2025 (MI308 licences);
# the rule of 15 Jan 2026 (TPP under 21,000 and memory bandwidth under 6,500 GB/s, naming the H200 and MI325X).
CHIPS = [
    ("Nvidia", "Blackwell", "B200, B300", False, ("na", "na", "no", "no", "no", "no"), ""),
    ("Nvidia", "H200", "", False, ("na", "na", "no", "no", "no", "cb"), "+25% tariff"),
    ("AMD", "MI300X", "MI325X", False, ("na", "na", "no", "no", "no", "cb"), ""),
    ("Nvidia", "H100", "", False, ("na", "no", "no", "no", "no", "cb"), ""),
    ("Nvidia", "A100", "", False, ("ok", "no", "no", "no", "no", "cb"), ""),
    ("AMD", "MI250", "MI250X", False, ("ok", "no", "no", "no", "no", "cb"), ""),
    ("Nvidia", "H800", "", True, ("na", "ok", "no", "no", "no", "cb"), ""),
    ("Nvidia", "A800", "", True, ("na", "ok", "no", "no", "no", "cb"), ""),
    ("Nvidia", "H20", "", True, ("na", "na", "ok", "no", "cb", "cb"), ""),
    ("AMD", "MI308", "", True, ("na", "na", "ok", "no", "cb", "cb"), ""),
]
CELLS = {"ok": ("✓", "Sold freely"), "cb": ("◐", "Licence, decided case by case"),
         "no": ("✕", "Licence presumed refused"), "na": ("", "Not on sale yet")}

# Where each row stands: (word, the tag's colour class)
STATUSES = {"force": ("In force", "fx-in"), "paused": ("Paused", "fx-aw"), "delayed": ("Delayed", "fx-aw"),
            "dropped": ("Dropped", "fx-an"), "draft": ("Draft", "fx-ch"), "breach": ("Found in breach", "fx-ch")}

# The other moves, newest first in each list: (day published, who, what, a line under it, its notice, where it stands,
# what changed since, that change's notice). who is "US" or another government; a link to a news report is
# footnoted instead (REPORTS).
TOOLS = [
    ("2025-09-02", "US", "Samsung, SK hynix and Intel plants in China lose standing permission for US tools",
     "Each shipment needs a licence from 31 Dec 2025",
     "https://www.federalregister.gov/documents/2025/09/02/2025-16735", "force", "", ""),
    ("2024-12-05", "US", "High-bandwidth memory and more chipmaking tools need a licence",
     "Including tools made abroad with US parts", "https://www.federalregister.gov/documents/2024/12/05/2024-28270",
     "force", "", ""),
    ("2023-06-30", "Netherlands", "Advanced chipmaking machines need a licence",
     "From 1 Sep 2023; widened in Sep 2024 and Apr 2025",
     "https://zoek.officielebekendmakingen.nl/stcrt-2023-18212.pdf", "force", "", ""),
    ("2023-05-23", "Japan", "23 kinds of chipmaking equipment need a licence", "From 23 Jul 2023",
     "https://www.meti.go.jp/policy/anpo/law_document/shourei/20230523_gaiyo.pdf", "force", "", ""),
    ("2022-10-13", "US", "US citizens barred from helping advanced Chinese chip plants", "",
     "https://www.federalregister.gov/documents/2022/10/13/2022-21658", "force", "", ""),
]
BUYERS = [
    ("2025-09-30", "US", "Firms 50% owned by a blacklisted company are blacklisted too",
     "Closes a route through subsidiaries", "https://www.federalregister.gov/documents/2025/09/30/2025-19001",
     "paused", "Paused to 9 Nov 2026", "https://www.federalregister.gov/documents/2025/11/12/2025-19846"),
    ("2025-06-14", "Taiwan", "Huawei and SMIC put on Taiwan's export blacklist", "",
     "https://techcrunch.com/2025/06/15/taiwan-places-export-controls-on-huawei-and-smic/", "force", "", ""),
    ("2025-01-16", "US", "Chip factories must check who designed an advanced chip before making it", "",
     "https://www.federalregister.gov/documents/2025/01/16/2025-00711", "delayed", "Delayed to 31 Dec 2026",
     "https://www.federalregister.gov/documents/2026/04/09/2026-06851"),
    ("2025-01-15", "US", "AI diffusion rule: caps on AI chips for every country, a first limit on model weights", "",
     "https://www.federalregister.gov/documents/2025/01/15/2025-00636", "dropped", "Rescinded 13 May 2025",
     "https://www.bis.gov/press-release/department-commerce-rescinds-biden-era-artificial-intelligence-diffusion-rule-"
     "strengthens-chip-related"),
    ("2024-10-02", "US", "Fast track for trusted data centres abroad",
     "Approved operators get AI chips without a licence each time",
     "https://www.federalregister.gov/documents/2024/10/02/2024-22587", "force", "", ""),
    ("2023-10-25", "US", "Licences also needed for countries chips could pass through",
     "Including Saudi Arabia, the UAE and Vietnam", "https://www.federalregister.gov/documents/2023/10/25/2023-23055",
     "force", "", ""),
]
CHINA = [
    ("2026-10-16", "China", "Plans export limits on 23 AI technologies",
     "Including the weights of models trained with over 10²⁶ operations",
     "https://the-decoder.com/china-plans-to-tighten-export-controls-on-open-weight-models-and-23-key-ai-technologies/",
     "draft", "", ""),
    ("2025-10-09", "China", "Rare-earth goods made abroad with Chinese rare earths need a licence", "",
     "https://www.mofcom.gov.cn/zwgk/zcfb/art/2025/art_b1ec77dd3f0d4762952904df7cdaadec.html", "paused",
     "Paused to 10 Nov 2026", "https://www.mofcom.gov.cn/zwgk/zcfb/art/2025/art_b1ec77dd3f0d4762952904df7cdaadec.html"),
    ("2024-12-09", "China", "Antitrust investigation of Nvidia opened", "",
     "https://www.samr.gov.cn/xw/zj/art/2024/art_ed4d3090401741a0894e475d35db652b.html", "breach",
     "Sep 2025, preliminary", "https://www.samr.gov.cn/xw/zj/art/2025/art_66b8363c3a194ba0a394a843d6cf3fd1.html"),
    ("2024-12-03", "China", "Gallium, germanium and antimony exports to the US presumed refused",
     "A day after the US announced its memory and tools rule (2 Dec 2024)",
     "https://www.mofcom.gov.cn/zwgk/zcfb/art/2024/art_3d5e990b43424e60828030f58a547b60.html", "paused",
     "Paused to 27 Nov 2026", "https://www.mofcom.gov.cn/zwgk/zcfb/art/2025/art_5c68985a6b1a46778e2e8dbff1bb1601.html"),
    ("2023-07-03", "China", "Gallium and germanium need an export licence", "From 1 Aug 2023",
     "https://aqygzj.mofcom.gov.cn/qdml/art/2023/art_c2ae3d2061e14e97ba608de1ed565f78.html", "force", "", ""),
]

# Official sites: a link to one is the notice; a link anywhere else is a news report, footnoted under the page
OFFICIAL = ("federalregister.gov", "sec.gov", "bis.gov", "mofcom.gov.cn", "samr.gov.cn", "meti.go.jp",
            "officielebekendmakingen.nl")

# China's own side of the H200, from reports (China publishes no notice of which firms may import)
CHINA_SIDE = [
    "https://the-decoder.com/china-reportedly-tightens-nvidia-h200-restrictions-limits-purchases-to-special-cases/",
    "https://the-decoder.com/china-greenlights-400000-nvidia-h200-chip-imports-for-tech-giants-according-to-reuters/",
]
# the news reports a few rows rest on (no official notice): url -> (outlet, day), footnoted under the page
REPORTS = {
    "https://techcrunch.com/2025/06/15/taiwan-places-export-controls-on-huawei-and-smic/": ("TechCrunch", "2025-06-15"),
    "https://the-decoder.com/china-plans-to-tighten-export-controls-on-open-weight-models-and-23-key-ai-technologies/":
        ("The Decoder", "2026-10-16"),
    CHINA_SIDE[0]: ("The Decoder", "2026-01-13"),
    CHINA_SIDE[1]: ("The Decoder, citing Reuters", "2026-01-28"),
}
HUAWEI = "https://media.bis.gov/media/documents/general-prohibition-10-guidance-may-13-2025.pdf"
H200_LICENCE = "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm"
# the Entity List (the US trade blacklist): rules adding or changing names since Oct 2022, counted from the Federal
# Register on CHECKED_TO, and the largest
ENTITY = (47, 35, 140, "2024-12-05", "https://www.federalregister.gov/documents/2024/12/05/2024-28267")

# stories checked by hand and left out, with why, so they aren't checked again
LEFT_OUT: dict[str, str] = {}

# the newest day every story was read for the lists above; the candidates start after it
CHECKED_TO = "2026-10-19"
_CHIP = re.compile(r"\b(chips?|semiconductors?|GPUs?|Nvidia|AMD|Huawei|Ascend|SMIC|ASML|H20|H200|Blackwell|"
                   r"rare earths?|gallium|germanium|antimony|model weights)\b", re.I)
_RULE = re.compile(r"\b(export (controls?|curbs?|rules?|bans?|restrictions?|licen[cs]es?)|licen[cs]es?|"
                   r"Entity List|blacklist\w*|Commerce Department|BIS|MOFCOM|bans? \w+ exports?)\b", re.I)


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Stories from after CHECKED_TO (or `since`, if later) that no row uses and LEFT_OUT doesn't hold: a government
    setting, easing or pausing an export rule on AI chips, chipmaking tools, the metals chips need or model weights.
    Newest first."""
    since = max(since, CHECKED_TO + "~")  # '~' sorts after any time of day, so CHECKED_TO itself is done
    used = {u for r in TOOLS + BUYERS + CHINA for u in (r[4], r[7]) if u} | set(CHINA_SIDE) | set(LEFT_OUT)
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["date"] >= since and c.get("category") != "research"
            and not any(s["url"] in used for s in [c, *(c.get("also") or [])])
            and _CHIP.search(c["title"]) and _RULE.search(c["title"] + " " + (c.get("summary") or ""))]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a chips/<day> branch: each row it adds or changes, and the stories it left out;
    None when it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("TOOLS", "BUYERS", "CHINA", "LEFT_OUT"))
    rows = [(r[0], r[1], name, r[2] + (f" ({r[6]})" if r[6] else ""), STATUSES[r[5]][0], r[4])
            for key, name, rs in (("TOOLS", "Tools and memory", TOOLS), ("BUYERS", "Who else may buy", BUYERS),
                                  ("CHINA", "China hits back", CHINA))
            for r in rs if r[4] not in had[key] or (r[7] and r[7] not in had[key])]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("Chip export rules", f"row{'s' * (len(rows) != 1)}", branch,
                        ("Day", "Who", "List", "What", "Stands", "Notice"), rows, dropped)


def _short(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{x.day} {x:%b %Y}"


def official(url: str) -> bool:
    host = re.sub(r"^https?://", "", url).split("/")[0]
    return any(host == o or host.endswith("." + o) for o in OFFICIAL)


def caught() -> bool:
    """True while every chip made for China was sold freely in one column and needed a licence presumed refused in a
    later one: what the grid's lead line says."""
    return all(any(c == "ok" and "no" in cells[i:] for i, c in enumerate(cells)) for *_, cn, cells, _ in CHIPS if cn)


def _grid(notes: list[str]) -> str:
    def foot(*urls: str) -> str:
        notes.extend(urls)
        return f"<sup>{', '.join(str(len(notes) - len(urls) + k + 1) for k in range(len(urls)))}</sup>"

    head = "".join(
        ("<th class=\"ce-now\">" if n == len(COLUMNS) - 1 else "<th>")
        + (f'<a href="{escape(u)}" rel="noopener">' if u else "")
        + f'<span class="ce-when">{escape(k)}</span>{escape(m)}' + ("</a>" if u else "") + "</th>"
        for n, (k, m, u) in enumerate(COLUMNS))
    rows = ""
    for maker, chip, also, cn, cells, word in CHIPS:
        tds = "".join(
            f'<td class="{c}{" ce-now" * (n == len(cells) - 1)}" title="{escape(CELLS[c][1])}">{CELLS[c][0]}'
            + (f"<i>{escape(word)}</i>" if word and n == len(cells) - 1 else "") + "</td>"
            for n, c in enumerate(cells))
        rows += (f'<tr><th><span class="ce-co">{escape(maker)}</span>{escape(chip)}'
                 + (f" <small>{escape(also)}</small>" if also else "")
                 + ("<em>made for China</em>" if cn else "") + f"</th>{tds}</tr>")
    key = "".join(f'<span><b class="ce-k {k}">{s}</b>{escape(t)}</span>' for k, (s, t) in CELLS.items())
    lead = ("Every chip Nvidia and AMD made for China was caught by a later rule. Since January 2026, the H200 and "
            "every weaker chip can be sold to China again, case by case." if caught() else
            "What the US required for each chip sold to China, decision by decision.")
    return (f'<section class="ce-hero"><h2>What Nvidia and AMD could sell to China, rule by rule</h2>'
            f'<p class="ce-big">{lead}</p><div class="ce-gw"><table class="ce-grid"><thead><tr><th class="ce-chip">Chip'
            f'<span>most powerful at top</span></th>{head}</tr></thead><tbody>{rows}</tbody></table></div>'
            f'<p class="ce-key">{key}</p>'
            f'<p class="ce-cn">Case by case in practice: the first H200 licence, in February 2026, let Nvidia ship small '
            f'amounts to specific customers, each chip inspected in the US and charged a 25% tariff '
            f'(<a href="{H200_LICENCE}" rel="noopener">Nvidia\'s annual report</a>). China decides for itself who may '
            f'buy: it first held H200 orders to special cases, then let big tech firms import them.'
            + foot(*CHINA_SIDE) + '</p>'
            f'<p class="ce-hw"><b>Huawei\'s own AI chips:</b> since 13 May 2025 the US says using Huawei\'s Ascend '
            f'910B, 910C or 910D anywhere in the world risks breaking US export rules '
            f'(<a href="{HUAWEI}" rel="noopener">US guidance</a>).</p></section>')


def _list(cls: str, title: str, sub: str, rows: list, notes: list[str]) -> str:
    items = ""
    for d, who, what, line, url, st, change, curl in sorted(rows, key=lambda r: r[0], reverse=True):
        tag, tc = STATUSES[st]
        if change:
            tag = change if st in ("paused", "delayed", "dropped") else f"{tag} · {change}"
        if official(url):
            src = f'<a href="{escape(url)}" rel="noopener">notice</a>'
        else:
            notes.append(url)
            src = f"<sup>{len(notes)}</sup>"
        link = (f' <a class="ce-ch" href="{escape(curl)}" rel="noopener">update</a>'
                if curl and curl != url and official(curl) else "")
        items += (f'<li class="{"ot" * (who != "US")}{" eased" * (st in ("paused", "delayed", "dropped"))}">'
                  f'<time>{_short(d)}{"" if who == "US" else " · " + escape(who)}</time><b>{escape(what)}</b>'
                  + (f'<span class="ce-l">{escape(line)}</span>' if line else "")
                  + f'<span class="ce-f"><span class="pc-k {tc}">{escape(tag)}</span>{link}{src}</span></li>')
    return f'<section class="ce-th {cls}"><h3>{title}</h3><p class="ce-sub">{sub}</p><ol>{items}</ol></section>'


def body(today: date) -> str:
    notes: list[str] = []
    grid = _grid(notes)
    lists = (_list("us", "Tools and memory", "Limits on the machines and parts that make chips", TOOLS, notes)
             + _list("us", "Who else may buy", "Rules for the rest of the world", BUYERS, notes)
             + _list("cnh", "China hits back", "Limits on the metals and tech others need", CHINA, notes))
    n, cn, big, day, url = ENTITY
    feet = "".join(f'<li>Reported by <a href="{escape(u)}" rel="noopener">{escape(REPORTS[u][0])}</a>, '
                   f'{_short(REPORTS[u][1])}</li>' for u in notes)
    limits = [
        ("The grid", "What the US required for each chip sold to China in each period, from the rules and the "
         "companies' own filings. China's own import decisions are in the line under it."),
        ("Dates", "The day a rule was published; the day it took effect is in the line under it when different."),
        ("Left out", "Smuggling cases, and tariffs unless they come with a rule."),
        ("Checked by hand", "Each row links to the official notice or the company's filing; the few that rest on a "
         "news report are numbered and listed under the page."),
    ]
    return ('<div class="ft ce">\n'
            + pages.feature_head(PATH, "Chip export rules",
                                 "Who may sell AI chips to whom, and how has each rule changed since 2022?",
                                 "Every US rule limiting exports of AI chips, chipmaking tools and AI model weights "
                                 "since October 2022, and how other governments answered. Each rule links to its "
                                 "official notice and says whether it still stands.")
            + grid + '<h2 class="ce-sec">The other moves</h2><div class="ce-themes">' + lists + "</div>"
            f'<p class="ce-el">Not shown one by one: {n} US rules since Oct 2022 adding or changing names on the Entity '
            f'List (the US trade blacklist), {cn} of them mentioning China; the largest added {big} on '
            f'<a href="{url}" rel="noopener">{_short(day)}</a>.</p>'
            + (f'<ol class="ce-notes">{feet}</ol>' if feet else "")
            + '<section class="jb-lim"><h2>About these rows</h2>\n<table class="mt jb-small jb-limits"><tbody>'
            + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
            + "</tbody></table></section></div>\n")


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    what = ("Who may sell AI chips to whom, and how has each rule changed since 2022? What Nvidia and AMD could sell "
            "to China under each US rule, and every rule on chips, chipmaking tools and the metals they need.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Chip export rules",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("Chip export rules · AI Pulse", what, PATH, body(today), data, pages.frame(conn, len(cards)),
                   ("/infra/", "Back to Infra"),
                   "Every cell and row checked by hand against the official notice, the company's filing, or a news "
                   "report where neither exists."),
        encoding="utf-8")
    return [PATH]
