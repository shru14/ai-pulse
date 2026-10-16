"""Who owns a piece of whom (who-owns-a-piece-of-whom/): the big companies with money in the AI labs, as a grid of
investors (rows) by labs (columns), a box per deal. Every deal was checked by hand against the story that reported it,
and only done deals are kept: talks, reported plans and rounds where the story says it isn't known whether the money
bought a share are left out. Amounts are as each story gives them, never added up; "up to" marks money promised and
paid in stages. Linked from Industry's strip.
"""
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

from . import pages, rss

PATH = "who-owns-a-piece-of-whom/"
# the labs, as columns, in this order
LABS = ["OpenAI", "Anthropic", "xAI", "Mistral", "SSI", "Thinking Machines", "Sarvam", "MiniMax"]
# (investor, lab, what the story says it put in or holds, month, paid in full? (False: "up to", promised in stages),
#  the story's URL)
DEALS = [
    ("Microsoft", "OpenAI", "27% stake", "Oct 2025", True,
     "https://the-decoder.com/openai-restructures-under-new-foundation-microsoft-takes-27-percent-stake/"),
    ("Microsoft", "Anthropic", "Up to $15B, with Nvidia", "Nov 2025", False,
     "https://siliconangle.com/2025/11/18/nvidia-microsoft-invest-15b-anthropic-part-new-cloud-partnership/"),
    ("Amazon", "OpenAI", "Up to $50B", "Feb 2026", False,
     "https://the-decoder.com/openais-up-to-110-billion-raise-lines-up-almost-exactly-with-the-111-billion-it-just-added-to-its-cash-burn-forecast/"),
    ("Amazon", "Anthropic", "Up to $25B", "Apr 2026", False,
     "https://siliconangle.com/2026/04/20/amazon-invest-25b-anthropic-part-expanded-cloud-partnership/"),
    ("Google", "Anthropic", "Up to $40B", "Apr 2026", False,
     "https://techcrunch.com/2026/04/24/google-to-invest-up-to-40b-in-anthropic-in-cash-and-compute/"),
    ("Nvidia", "OpenAI", "$30B", "Feb 2026", True,
     "https://techcrunch.com/2026/02/27/openai-raises-110b-in-one-of-the-largest-private-funding-rounds-in-history/"),
    ("Nvidia", "Anthropic", "Up to $15B, with Microsoft", "Nov 2025", False,
     "https://siliconangle.com/2025/11/18/nvidia-microsoft-invest-15b-anthropic-part-new-cloud-partnership/"),
    ("Nvidia", "SSI", "Undisclosed", "Jul 2026", True,
     "https://the-decoder.com/nvidia-invests-in-ilya-sutskevers-ai-lab-shifting-ssi-away-from-google-chips/"),
    ("Nvidia", "Thinking Machines", "Undisclosed", "Mar 2026", True,
     "https://siliconangle.com/2026/03/10/nvidia-makes-significant-investment-mira-muratis-thinking-machines/"),
    ("SoftBank", "OpenAI", "$30B", "Feb 2026", True,
     "https://techcrunch.com/2026/02/27/openai-raises-110b-in-one-of-the-largest-private-funding-rounds-in-history/"),
    ("SpaceX", "xAI", "Owns it: merged", "Feb 2026", True,
     "https://the-decoder.com/musk-merges-money-losing-xai-into-spacex-before-mega-ipo/"),
    ("Tesla", "xAI", "$2B, agreed", "Jan 2026", True,
     "https://techcrunch.com/2026/01/28/tesla-invested-2b-in-elon-musks-xai/"),
    ("ASML", "Mistral", "€1.3B, largest shareholder", "Sep 2025", True,
     "https://the-decoder.com/asml-becomes-the-largest-shareholder-in-mistral-ai/"),
    ("Samsung", "Mistral", "Co-led €3B round", "Sep 2026", True,
     "https://techcrunch.com/2026/09/08/mistral-raises-e3b-as-sovereign-ai-becomes-big-business/"),
    ("HCLTech", "Sarvam", "$150M", "Jun 2026", True,
     "https://techcrunch.com/2026/06/15/sarvam-becomes-indias-newest-ai-unicorn-with-234-million-funding-round-led-by-hcltech/"),
    ("Alibaba", "MiniMax", "Backer before its IPO", "Dec 2025", True,
     "https://siliconangle.com/2025/12/30/minimax-moves-toward-hong-kong-ipo-chinese-ai-firms-rush-go-public/"),
]
# stories checked by hand and left out, with why, so they aren't checked again
LEFT_OUT = {
    "https://techcrunch.com/2026/01/06/xai-says-it-raised-20b-in-series-e-funding/":
        "Nvidia among the investors, but xAI didn't say whether it was equity or debt",
    "https://siliconangle.com/2026/04/24/ai-startups-cohere-aleph-alpha-merge-600m-new-funding/":
        "Cohere and Aleph Alpha only intend to merge",
    "https://the-decoder.com/nvidia-in-talks-to-invest-in-perplexity-at-30-billion-plus-valuation/": "Talks only",
    "https://the-decoder.com/catl-and-tencent-back-deepseeks-ballooning-funding-round-as-the-ai-startup-eyes-a-2027-ipo/":
        "Round not closed",
    "https://siliconangle.com/2026/10/11/nvidia-reportedly-in-early-talks-to-buy-acqui-hire-or-invest-more-in-reflection-ai/":
        "Talks only",
}


def deals(cards: list[dict]) -> list[dict]:
    """Each deal with its story's outlet and headline; a deal whose story isn't in the site's cards is left out."""
    by_url = {s["url"]: s for c in cards for s in [c, *(c.get("also") or [])]}
    return [{"investor": i, "lab": lab, "what": w, "when": m, "paid": p, "url": u, "source": by_url[u]["source"],
             "title": by_url[u]["title"]} for i, lab, w, m, p, u in DEALS if u in by_url]


def _sentence(rows: list[dict]) -> str:
    """Who is in more than one lab, from the rows: 'Amazon and Microsoft have money in both OpenAI and Anthropic;
    Nvidia is in 4 labs.'"""
    labs: dict[str, list[str]] = {}
    for r in rows:
        labs.setdefault(r["investor"], []).append(r["lab"])
    most = max(labs, key=lambda i: len(labs[i]), default="")
    both = sorted(i for i, ls in labs.items() if {"OpenAI", "Anthropic"} <= set(ls) and i != most)
    said = []
    if both:
        said.append(f"{' and '.join(both)} {'has' if len(both) == 1 else 'have'} money in both OpenAI and Anthropic")
    if most and len(labs[most]) > 2:
        said.append(f"{most} is in {len(labs[most])} labs")
    return ("; ".join(said) + ".") if said else ""


def body(rows: list[dict]) -> str:
    investors = list(dict.fromkeys(r["investor"] for r in rows))
    labs = [lab for lab in LABS if any(r["lab"] == lab for r in rows)]
    cell = {(r["investor"], r["lab"]): r for r in rows}

    def box(r: dict) -> str:
        return (f'<a class="ow-deal{"" if r["paid"] else " ow-up"}" href="{escape(r["url"])}" rel="noopener" '
                f'title="{escape(r["source"])}: {escape(r["title"])}">{escape(r["what"])}<small>{r["when"]}</small></a>')

    head = '<tr><th scope="col">Investor ↓ · Lab →</th>' + "".join(f'<th scope="col">{escape(lab)}</th>' for lab in labs)
    grid = "".join(f'<tr><th scope="row">{escape(i)}</th>'
                   + "".join(f"<td>{box(cell[i, lab]) if (i, lab) in cell else ''}</td>" for lab in labs) + "</tr>"
                   for i in investors)
    limits = [
        ("What counts", "Money put into a lab in return for a share of it, or a stake it holds, as the story states it. "
         "Talks, reported plans, and rounds where it isn't known whether the money bought a share are left out."),
        ("Amounts", "As each story gives them, never added up: some are cash, some part cash and part computing "
         "power. A dashed box is money promised \"up to\" that amount, paid in stages."),
        ("Each box", "Links to the story that reported the deal; the month is when it was reported."),
    ]
    return (f'<div class="ft jb ow">\n<h1>Who owns a piece of whom</h1>\n'
            f'<p class="jb-q">Which big companies have money in which AI labs?</p>\n'
            f'<p class="intro">{len(rows)} stakes in {len(labs)} AI labs, from the news we read, each checked by hand '
            f'against its story. {escape(_sentence(rows))}</p>\n'
            '<p class="ow-key"><span><i></i>Money in</span><span><i class="ow-up"></i>"Up to": promised, paid in '
            'stages</span><span>Each box links to its story.</span></p>\n'
            f'<div class="ow-wrap"><table class="ow-grid"><thead>{head}</tr></thead><tbody>{grid}</tbody></table></div>\n'
            '<section class="jb-lim"><h2>About these deals</h2>\n<table class="mt jb-small jb-limits"><tbody>'
            + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
            + "</tbody></table></section></div>\n")


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    rows = deals(cards)
    if not rows:
        return []
    what = ("Which big companies have money in which AI labs? The biggest stakes in AI labs, each checked by hand "
            "against the story that reported it.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Who owns a piece of whom",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("Who owns a piece of whom · AI Pulse", what, PATH, body(rows), data, pages.frame(conn, len(cards)),
                   ("/industry/", "Back to Industry"),
                   "Amounts are the outlets' own, each box linking to its story. New deals are added once checked "
                   "by hand."),
        encoding="utf-8")
    return [PATH]
