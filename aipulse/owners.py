"""Who owns a piece of whom (who-owns-a-piece-of-whom/): the big companies with money in the AI labs, as a grid of
investors (rows) by labs (columns), a box per deal. Every deal was checked by hand against the story that reported it,
and only done deals are kept: talks, reported plans and rounds where the story says it isn't known whether the money
bought a share are left out. Amounts are as each story gives them, never added up; "up to" marks money promised and
paid in stages. Linked from Industry's strip.
"""
from __future__ import annotations

import re
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
    "https://techcrunch.com/2026/04/08/aws-boss-explains-why-investing-billions-in-both-anthropic-and-openai-is-an-ok-conflict/":
        "same as Amazon in Anthropic",
    "https://techcrunch.com/2026/04/06/openai-alums-have-been-quietly-investing-from-a-new-potentially-100m-fund/":
        "venture fund, not a company in a lab",
    "https://siliconangle.com/2026/04/03/spacexs-stratospheric-ipo-hopes-openais-ridiculous-round-agentic-ai-gap/":
        "no new stake named in an AI lab",
    "https://techcrunch.com/2026/04/02/openai-acquires-tbpn-the-buzzy-founder-led-business-talk-show/":
        "OpenAI buying a talk show, not an AI lab",
    "https://openai.com/index/openai-acquires-tbpn":
        "OpenAI buying a talk show, not an AI lab",
    "https://techcrunch.com/2026/03/31/openai-not-yet-public-raises-3b-from-retail-investors-in-monster-122b-fund-raise/":
        "no amounts per company; Amazon, Nvidia, SoftBank, Microsoft already in OpenAI",
    "https://techcrunch.com/2026/03/30/mistral-ai-raises-830m-in-debt-to-set-up-a-data-center-near-paris/":
        "debt, no share",
    "https://the-decoder.com/openai-expands-its-record-funding-round-to-over-120-billion-as-it-eyes-a-potential-ipo-later-this-year/":
        "no amounts per company; same as Microsoft in OpenAI",
    "https://techcrunch.com/2026/03/23/sam-altman-openai-fusion-energy-board-helion/":
        "talks to sell power, no share",
    "https://techcrunch.com/2026/03/09/openai-acquires-promptfoo-to-secure-its-ai-agents/":
        "OpenAI buying a security startup, not an AI lab",
    "https://the-decoder.com/softbank-seeks-record-40-billion-loan-to-fund-openai-stake/":
        "loan still under negotiation; same as SoftBank in OpenAI",
    "https://techcrunch.com/2026/03/04/jensen-huang-says-nvidia-is-pulling-back-from-openai-and-anthropic-but-his-explanation-raises-more-questions-than-it-answers/":
        "same as Nvidia in OpenAI and Nvidia in Anthropic",
    "https://siliconangle.com/2026/02/27/openai-raises-megaround-anthropics-battles-multiply-saaspocalypse-widens/":
        "same as Amazon in OpenAI",
    "https://techcrunch.com/2026/02/27/anthropic-vs-the-pentagon-whats-actually-at-stake/":
        "no investment in an AI lab",
    "https://cset.georgetown.edu/article/pentagon-sets-deadline-for-anthropic-amid-high-stakes-standoff/":
        "no investment in an AI lab",
    "https://techcrunch.com/2026/02/25/anthropic-acquires-vercept-ai-startup-agents-computer-use-founders-investors/":
        "Vercept builds agent tools, not stated to make AI models",
    "https://techcrunch.com/2026/02/20/anthropic-funded-group-backs-candidate-attacked-by-rival-ai-super-pac/":
        "political group, no share",
    "https://techcrunch.com/2026/02/19/openai-reportedly-finalizing-100b-deal-at-more-than-850b-valuation/":
        "reportedly, talks only",
    "https://siliconangle.com/2026/02/13/anthropic-databricks-raise-billions-next-stop-ipos/":
        "no investors named",
    "https://siliconangle.com/2026/02/12/anthropic-closes-30b-round-annualized-revenue-tops-14b/":
        "only funds named, plus Nvidia and Microsoft: same as them in Anthropic",
    "https://techcrunch.com/2026/02/12/anthropic-raises-another-30-billion-in-series-g-with-a-new-value-of-380-billion/":
        "investors are funds; no amounts per company",
    "https://techcrunch.com/2026/02/09/anthropic-closes-in-on-20b-round/":
        "round not closed; participation only expected",
    "https://cset.georgetown.edu/article/musks-mega-merger-of-spacex-and-xai-bets-on-sci-fi-future-of-data-centers-in-space/":
        "same as SpaceX in xAI",
    "https://the-decoder.com/cerebras-closes-1-billion-funding-round-at-23-billion-valuation-after-landing-openai-deal/":
        "Cerebras is a chip company, not an AI lab",
    "https://the-decoder.com/nvidia-is-reportedly-investing-20-billion-in-openai-says-it-will-proceed-one-step-at-a-time/":
        "reportedly, deal not final",
    "https://techcrunch.com/2026/01/31/nvidia-ceo-pushes-back-against-report-that-his-companys-100b-openai-investment-has-stalled/":
        "no amount done; talks and plans only",
    "https://techcrunch.com/2026/01/29/amazon-is-reportedly-in-talks-to-invest-50-billion-in-openai/":
        "Talks only",
    "https://siliconangle.com/2026/01/28/openai-anthropic-reportedly-raising-billions-dollars-new-funding/":
        "reportedly raising, not closed",
    "https://techcrunch.com/2026/01/22/voice-ai-engine-and-openai-partner-livekit-hits-1b-valuation/":
        "LiveKit is not an AI lab",
    "https://the-decoder.com/openai-promises-ai-data-centers-wont-raise-local-electricity-prices/":
        "no investment in an AI lab",
    "https://techcrunch.com/2026/01/20/humans-a-human-centric-ai-startup-founded-by-anthropic-xai-google-alums-raised-480m-seed-round/":
        "no amounts per investor; not stated to make AI models",
    "https://siliconangle.com/2026/01/19/chinas-moonshot-ai-close-another-massive-funding-round-two-biggest-rivals-go-public/":
        "Round not closed",
    "https://the-decoder.com/new-sequoia-leadership-greenlights-first-anthropic-investment-amid-25-billion-raise/":
        "venture fund, still preparing; Microsoft and Nvidia already in Anthropic",
    "https://techcrunch.com/2026/01/18/sequoia-to-invest-in-anthropic-breaking-vc-taboo-on-backing-rivals-ft/":
        "venture fund, plans only",
    "https://techcrunch.com/2026/01/15/openai-invests-in-sam-altmans-brain-computer-interface-startup-merge-labs/":
        "OpenAI investing in a non-AI-lab",
    "https://techcrunch.com/2026/01/13/ai-drug-discovery-startup-converge-bio-pulls-in-25m-from-bessemer-and-execs-from-meta-openai-and-wiz/":
        "venture fund, not an AI lab",
    "https://siliconangle.com/2026/01/08/minimax-raises-619m-hong-kong-ipo-investor-appetite-generative-ai-remains-strong/":
        "IPO; earlier backers only; same as Alibaba in MiniMax",
    "https://techcrunch.com/2026/01/07/anthropic-reportedly-raising-10b-at-350b-valuation/":
        "reportedly raising, not closed",
    "https://siliconangle.com/2026/01/06/xai-raises-20b-funding-round-backed-nvidia-cisco/":
        "Nvidia and Cisco took part but no amounts, equity or debt not said",
    "https://siliconangle.com/2026/01/01/moonshot-ai-one-chinas-leading-ai-tigers-raises-500m-fill-ai-infrastructure-war-chest/":
        "reportedly; only IDG Capital (a fund) has an amount",
    "https://the-decoder.com/openai-merges-internal-teams-to-fix-audio-ai-accuracy-gap-ahead-of-chatgpt-hardware-push/":
        "no investment in an AI lab",
}


# the newest day every story was read for DEALS and LEFT_OUT; the candidates start after it
CHECKED_TO = "2026-10-16"
# a headline that may be a stake in an AI lab: money words, and a lab (a column, or one that may become one)
_MONEY = re.compile(r"\b(stakes?|invest(s|ed|ing|ment)?|backs|backed|backing|raises?|raised|funding|round|shareholders?|"
                    r"acquir(es|ed)|merg(es|ed|er)|pours|valuation)\b", re.I)
_LAB = re.compile(r"\b(OpenAI|Anthropic|xAI|Mistral|SSI|Safe Superintelligence|Thinking Machines|Sarvam|MiniMax|"
                  r"DeepSeek|Moonshot|Zhipu|Z\.ai|StepFun|Perplexity|Cohere|Aleph Alpha|Reflection AI|Inflection|"
                  r"Character\.AI|Black Forest Labs|Ai2|AI21|Sakana|Liquid AI|Poolside|Cognition)\b")


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Stories from after CHECKED_TO (or `since`, if later) that no deal uses and LEFT_OUT doesn't hold and whose
    headline names an AI lab next to money words: one per event, newest first."""
    since = max(since, CHECKED_TO + "~")  # '~' sorts after any time of day, so CHECKED_TO itself is done
    used = {d[-1] for d in DEALS} | set(LEFT_OUT)
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["date"] >= since and c.get("category") != "research"
            and not any(s["url"] in used for s in [c, *(c.get("also") or [])])
            and _MONEY.search(c["title"]) and _LAB.search(c["title"])]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for an owners/<day> branch: each deal it adds, and the stories it left out; None when
    it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("DEALS", "LEFT_OUT"))
    rows = [(i, lab, w, m, u) for i, lab, w, m, _, u in DEALS if u not in had["DEALS"]]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("Who owns a piece of whom", f"deal{'s' * (len(rows) != 1)}", branch,
                        ("Investor", "Lab", "What", "When", "Source"), rows, dropped)


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
    return ('<div class="ft jb ow">\n'
            + pages.feature_head(PATH, "Who owns a piece of whom", "Which big companies have money in which AI labs?",
                                 f"{len(rows)} stakes in {len(labs)} AI labs, from the news we read, each checked by "
                                 f"hand against its story. {escape(_sentence(rows))}")
            + '<p class="ow-key"><span><i></i>Money in</span><span><i class="ow-up"></i>"Up to": promised, paid in '
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
