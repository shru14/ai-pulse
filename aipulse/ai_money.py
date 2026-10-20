"""AI money, the sections added to Who owns a piece of whom (owners.py, same page and address): where the big money
in AI went in 2026, month by month, and the deals where it comes back. A lane each for funding rounds, compute
deals and buyouts of $1B or more (a dot per deal along the year, bigger for more money), then the circular deals: a company puts money into an AI lab or cloud that, in the same deal or an
earlier one, agreed to buy from it, or a seller hands its buyer shares. Every row was checked by hand against the story
that reported it: funding rounds are closed (not talks, plans or "is raising"), loans, bonds and venture funds are left
out, and amounts are as each story gives them, marked "reported" when they come from a news report rather than the
companies. Buyouts come from buyouts.DEALS.
"""
from __future__ import annotations

from datetime import date, timedelta
from html import escape

from . import buyouts

PATH = "who-owns-a-piece-of-whom/"
SINCE = "2026-01-01"

# Funding rounds of $1B or more, closed: (day, who raised, amount as the story gives it, in billions of US dollars for
#  the dot's size, the valuation or a note as the same story gives it, or "", the story)
ROUNDS = [
    ("2026-01-06", "xAI", "$20B", 20, "Late-stage round",
     "https://siliconangle.com/2026/01/06/xai-raises-20b-funding-round-backed-nvidia-cisco/"),
    ("2026-01-14", "Skild AI", "$1.4B", 1.4, "Robot software",
     "https://siliconangle.com/2026/01/14/robot-software-startup-skild-ai-raises-1-4b-round-backed-nvidia-jeff-bezos/"),
    ("2026-02-12", "Anthropic", "$30B", 30, "At a $380B valuation",
     "https://siliconangle.com/2026/02/12/anthropic-closes-30b-round-annualized-revenue-tops-14b/"),
    ("2026-02-18", "World Labs", "$1B", 1, "Fei-Fei Li's world-model startup",
     "https://the-decoder.com/fei-fei-lis-world-labs-raises-one-billion-dollars-for-spatial-intelligence/"),
    ("2026-02-27", "OpenAI", "$110B", 110, "At $730B before the money; Amazon $50B, Nvidia and SoftBank $30B each",
     "https://techcrunch.com/2026/02/27/openai-raises-110b-in-one-of-the-largest-private-funding-rounds-in-history/"),
    ("2026-03-10", "AMI Labs", "Over $1B", 1, "Yann LeCun's startup; Europe's largest seed round",
     "https://the-decoder.com/investors-bet-1-billion-on-yann-lecuns-vision-for-ai-beyond-llms/"),
    ("2026-04-22", "Vast Data", "About $1B", 1, "At a $30B valuation",
     "https://siliconangle.com/2026/04/22/vast-data-raises-1b-30b-valuation-ai-infrastructure-demand-accelerates/"),
    ("2026-04-27", "Ineffable Intelligence", "$1.1B", 1.1, "At a $5.1B valuation; David Silver's lab",
     "https://techcrunch.com/2026/04/27/deepminds-david-silver-just-raised-1-1b-to-build-an-ai-that-learns-without-human-data/"),
    ("2026-05-07", "Moonshot AI", "$2B", 2, "At over $20B",
     "https://siliconangle.com/2026/05/07/open-source-ai-developer-moonshot-ai-raises-2b-20b-valuation/"),
    ("2026-05-27", "Cognition", "$1B", 1, "At $25B before the money",
     "https://techcrunch.com/2026/05/27/ai-coding-startup-cognition-raises-1b-at-25b-pre-money-valuation/"),
    ("2026-05-28", "Anthropic", "$65B", 65, "At $965B after the money",
     "https://techcrunch.com/2026/05/28/anthropic-raises-65-billion-nears-1t-valuation-ahead-of-ipo/"),
    ("2026-06-11", "Prometheus", "$12B", 12, "At a $41B valuation; Jeff Bezos' AI startup",
     "https://the-decoder.com/jeff-bezos-ai-startup-prometheus-closes-12-billion-round-at-a-41-billion-valuation/"),
    ("2026-06-16", "DeepSeek", "About $7.4B", 7.4, "Its first outside money, at $50B",
     "https://the-decoder.com/deepseek-takes-outside-money-for-the-first-time-at-a-50-billion-valuation/"),
    ("2026-07-03", "Kling", "About $2B", 2, "Kuaishou's AI video unit",
     "https://the-decoder.com/chinese-ai-video-maker-kling-raises-2-billion-as-it-gears-up-for-hong-kong-ipo/"),
    ("2026-07-08", "SambaNova", "$1B", 1, "First close, at $11B",
     "https://techcrunch.com/2026/07/08/sambanova-draws-1b-at-11b-valuation-in-series-f-first-close/"),
    ("2026-07-22", "Atoms", "$1.7B", 1.7, "Travis Kalanick's robotics company",
     "https://techcrunch.com/2026/07/22/travis-kalanicks-robotics-company-raises-1-7b-led-by-a16z/"),
    ("2026-08-11", "River AI", "$1.1B", 1.1, "Early-stage round",
     "https://siliconangle.com/2026/08/11/personalized-ai-startup-river-ai-raises-1-1b-consortium-backed-nvidia-amd/"),
    ("2026-08-12", "Thrive Holdings", "$2B", 2, "At a $12B valuation",
     "https://techcrunch.com/2026/08/12/openai-backed-thrive-holdings-raises-2b-to-bring-ai-to-the-enterprise/"),
    ("2026-08-13", "Databricks", "$5B", 5, "At a $190B valuation",
     "https://techcrunch.com/2026/08/13/databricks-wanted-to-raise-1b-investors-wanted-15b-it-settled-on-5b-at-a-190b-valuation/"),
    ("2026-09-08", "Mistral", "€3B", 3.5, "At €21B; led by Samsung",
     "https://techcrunch.com/2026/09/08/mistral-raises-e3b-as-sovereign-ai-becomes-big-business/"),
    ("2026-09-17", "Crusoe", "$3.9B", 3.9, "At $30.9B",
     "https://techcrunch.com/2026/09/17/crusoe-raises-3-9b-to-build-massive-data-centers-and-small-modular-ai-factories/"),
    ("2026-09-28", "Instinct", "$1B", 1, "Series C at a $10B valuation",
     "https://techcrunch.com/2026/09/28/viral-ai-agent-instinct-raises-1b-series-c-at-a-10b-valuation/"),
]

# Compute deals of $1B or more, signed: (day, buyer, seller, amount as the story gives it, billions for the dot,
#  reported?, the story)
COMPUTE = [
    ("2026-01-14", "OpenAI", "Cerebras", "$10B", 10, True,
     "https://techcrunch.com/2026/01/14/openai-signs-deal-reportedly-worth-10-billion-for-compute-from-cerebras/"),
    ("2026-02-24", "Meta", "AMD", "Up to $100B", 100, False,
     "https://techcrunch.com/2026/02/24/meta-strikes-up-to-100b-amd-chip-deal-as-it-chases-personal-superintelligence/"),
    ("2026-03-16", "Meta", "Nebius", "Up to $27B", 27, False,
     "https://the-decoder.com/meta-signs-27-billion-cloud-deal-with-nebius-in-one-of-the-largest-ai-infrastructure-bets-yet/"),
    ("2026-04-20", "Anthropic", "Amazon", "$100B", 100, False,
     "https://techcrunch.com/2026/04/20/anthropic-takes-5b-from-amazon-and-pledges-100b-in-cloud-spending-in-return/"),
    ("2026-05-06", "Anthropic", "Google Cloud", "About $200B", 200, True,
     "https://the-decoder.com/anthropic-commits-200-billion-to-google-cloud-over-five-years/"),
    ("2026-05-20", "Anthropic", "xAI", "$1.25B a month", 1.25, False,
     "https://techcrunch.com/2026/05/20/anthropic-will-pay-xai-1-25-billion-per-month-for-compute/"),
    ("2026-05-27", "Snowflake", "Amazon", "$6B", 6, False,
     "https://techcrunch.com/2026/05/27/in-more-good-news-for-amazon-snowflake-signs-6b-deal-with-aws-for-ai-cpu-chips/"),
    ("2026-07-14", "Reflection AI", "Nebius", "$1B", 1, False,
     "https://techcrunch.com/2026/07/14/reflection-inks-1b-compute-deal-with-nebius/"),
    ("2026-08-04", "Anthropic", "Volta", "$10B", 10, True,
     "https://techcrunch.com/2026/08/04/anthropic-signs-10-billion-deal-with-ai-cloud-startup-volta/"),
    ("2026-08-11", "Anthropic", "Riot Platforms", "$9.1B", 9.1, True,
     "https://the-decoder.com/anthropic-signs-9-1-billion-data-center-deal-with-bitcoin-miner-riot-platforms/"),
    ("2026-08-26", "Anthropic", "Nscale", "$45B", 45, False,
     "https://techcrunch.com/2026/08/26/anthropic-continues-compute-gobbling-streak-in-45-billion-deal-with-nscale/"),
    ("2026-09-01", "Anthropic", "Lambda", "$35B", 35, False,
     "https://siliconangle.com/2026/09/01/anthropic-launches-claude-fable-5-1-inking-35b-cloud-deal-with-lambda/"),
    ("2026-09-25", "Anthropic", "Akamai", "$11.6B", 11.6, True,
     "https://the-decoder.com/anthropic-signs-11-6-billion-cloud-deal-with-akamai-pushing-its-compute-spending-past-500-billion-in-under-a-year/"),
]

# Money that comes back: (who put money in or handed over shares, into whom, what went in, month, what comes back,
#  month, story for the money in, story for what comes back ("" when the same story says both), reported?)
INVEST_SELL = [
    ("Amazon", "Anthropic", "Up to $25B", "Apr 2026", "Anthropic agreed to spend $100B on Amazon's cloud", "Apr 2026",
     "https://siliconangle.com/2026/04/20/amazon-invest-25b-anthropic-part-expanded-cloud-partnership/",
     "https://techcrunch.com/2026/04/20/anthropic-takes-5b-from-amazon-and-pledges-100b-in-cloud-spending-in-return/", False),
    ("Google", "Anthropic", "Up to $40B, in cash and compute", "Apr 2026",
     "Anthropic committed about $200B to Google Cloud over five years", "May 2026",
     "https://techcrunch.com/2026/04/24/google-to-invest-up-to-40b-in-anthropic-in-cash-and-compute/",
     "https://the-decoder.com/anthropic-commits-200-billion-to-google-cloud-over-five-years/", True),
    ("AMD", "Anthropic", "Up to $5B", "Jul 2026", "Anthropic will deploy up to 2 GW of AMD chips", "Jul 2026",
     "https://the-decoder.com/anthropic-will-deploy-2-gigawatts-of-amd-gpus-for-claude-in-a-deal-worth-up-to-5-billion/",
     "", False),
    ("Amazon", "OpenAI", "$50B", "Feb 2026", "OpenAI is buying $38B of Amazon cloud over seven years", "Nov 2025",
     "https://techcrunch.com/2026/02/27/openai-raises-110b-in-one-of-the-largest-private-funding-rounds-in-history/",
     "https://techcrunch.com/2025/11/03/openai-and-amazon-ink-38b-cloud-computing-deal/", False),
    ("Nvidia", "OpenAI", "$30B", "Feb 2026", "OpenAI agreed to deploy 10 GW of Nvidia chips", "Sep 2025",
     "https://techcrunch.com/2026/02/27/openai-raises-110b-in-one-of-the-largest-private-funding-rounds-in-history/",
     "https://techcrunch.com/2025/09/22/nvidia-plans-to-invest-up-to-100b-in-openai/", False),
    ("Nvidia", "CoreWeave", "$2B", "Jan 2026", "CoreWeave builds Nvidia's chips, Rubin among them, into its cloud",
     "Jan 2026", "https://techcrunch.com/2026/01/26/nvidia-invests-2b-to-help-debt-ridden-coreweave-add-5gw-of-ai-compute/",
     "", False),
    ("Nvidia", "SoftBank's data-centre developer", "$1.5B", "Aug 2026",
     "Nvidia's chips will power the OpenAI data centre it builds", "Aug 2026",
     "https://techcrunch.com/2026/08/17/nvidia-investing-1-5b-in-softbank-data-center-developer-behind-openai-project/",
     "", False),
]
# a seller hands its buyer the right to its shares (a warrant) with a deal to buy from it
SHARES_BACK = [
    ("AMD", "OpenAI", "Shares in AMD", "Oct 2025", "OpenAI buys tens of billions of dollars of AMD hardware", "Oct 2025",
     "https://siliconangle.com/2025/10/06/openai-buy-10b-worth-amd-hardware-stock-new-partnership/", "", False),
    ("AMD", "Meta", "A warrant for 160 million AMD shares", "Feb 2026", "Meta buys up to $100B of AMD chips", "Feb 2026",
     "https://techcrunch.com/2026/02/24/meta-strikes-up-to-100b-amd-chip-deal-as-it-chases-personal-superintelligence/",
     "", False),
    ("Akamai", "Anthropic", "A warrant for up to 5% of Akamai", "Sep 2026", "Anthropic signs an $11.6B, seven-year cloud deal",
     "Sep 2026",
     "https://the-decoder.com/anthropic-signs-11-6-billion-cloud-deal-with-akamai-pushing-its-compute-spending-past-500-billion-in-under-a-year/",
     "", True),
]

LANES = [("round", "Funding rounds"), ("compute", "Compute deals"), ("buyout", "Buyouts")]
REP = '<span class="am-rep" title="The figure comes from a news report, not the companies">reported</span>'


def deals() -> list[dict]:
    """Every $1B+ move this year as {day, kind, who, other, shown, b, reported, url, note}, oldest first."""
    out = [dict(day=d, kind="round", who=w, other="", shown=s, b=b, reported=False, url=u, note=n)
           for d, w, s, b, n, u in ROUNDS]
    out += [dict(day=d, kind="compute", who=w, other=o, shown=s, b=b, reported=r, url=u, note="")
            for d, w, o, s, b, r, u in COMPUTE]
    out += [dict(day=d if len(d) == 10 else d + "-15", kind="buyout", who=buyer, other=bought, shown=price.replace(", reported", ""),
                 b=b, reported="reported" in price, url=url, note=what)
            for d, buyer, bought, what, price, b, st, url, *_ in buyouts.DEALS if b and b >= 1 and st != "blocked"]
    return sorted(out, key=lambda r: r["day"])


def _size(b: float) -> int:
    """A dot's width in pixels: its area grows with the money, so $200B is the largest."""
    return round(9 + 2.6 * b ** 0.5)


def _name(r: dict) -> str:
    return f'{r["who"]} → {r["other"]}' if r["kind"] == "buyout" else f'{r["who"]} ↔ {r["other"]}' if r["other"] else r["who"]


def _lanes(rows: list[dict], today: date) -> str:
    """A lane per kind: a dot per deal along the year, the biggest named above its dot."""
    lo = date.fromisoformat(SINCE)
    hi = date(today.year, today.month, 1) + timedelta(days=32)
    hi = date(hi.year, hi.month, 1)
    x = lambda d: round((date.fromisoformat(d) - lo).days / (hi - lo).days * 100, 2)
    months, m = [], lo
    while m < hi:
        months.append(f'<i class="by-gl" style="left:{x(m.isoformat())}%"></i>'
                      f'<span class="by-mo" style="left:{x(m.isoformat())}%">{m:%b}</span>')
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    out = []
    for kind, label in LANES:
        mine = [(n, r) for n, r in enumerate(rows) if r["kind"] == kind]
        top = {n for n, _ in sorted(mine, key=lambda t: -t[1]["b"])[:1]}
        dots = []
        for n, r in sorted(mine, key=lambda t: -t[1]["b"]):
            left, s = x(r["day"]), _size(r["b"])
            tip = f'{_day(r["day"])} · {_name(r)} · {r["shown"]}{" · reported" * r["reported"]}'
            dots.append(f'<a class="by-dot am-{kind}{" am-r" * r["reported"]}{" by-l" * (left > 60)}" href="{PATH}#am-{n}" '
                        f'style="left:{left}%;--s:{s}px" aria-label="{escape(tip)}" data-tip="{escape(tip)}"></a>')
            if n in top:  # named above its dot, so the name never covers another dot
                side = "r" if left > 75 else "l" if left < 15 else ""
                dots.append(f'<span class="am-lb{" am-lb-" + side if side else ""}" style="left:{left}%">'
                            f'{escape(_name(r))} {escape(r["shown"])}</span>')
        out.append(f'<div class="by-r am-lane"><span class="by-n">{label} <b>{len(mine)}</b></span>'
                   f'<div class="by-tr">{"".join(dots)}</div></div>')
    key = ('<p class="by-key"><span><i class="by-k am-k-round"></i>Funding round</span><span><i class="by-k am-k-compute">'
           '</i>Compute deal</span><span><i class="by-k am-k-buyout"></i>Buyout</span><span><i class="by-k am-k-r"></i>'
           'Figure from a news report</span><span>A bigger dot is more money. Point at a dot to see the deal, click to '
           'jump to its row.</span></p>')
    return (f'<section class="by-ls am-ls"><h2>The big money, month by month</h2>{key}<div class="by-g">'
            f'<div class="by-ax">{"".join(months)}</div>{"".join(out)}</div></section>')


def _day(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{x.day} {x:%b}"


def _lead(rows: list[dict]) -> str:
    """Two plain findings, from the rows: the biggest round, and who buys the compute since April."""
    big = max((r for r in rows if r["kind"] == "round"), key=lambda r: r["b"])
    late = [r for r in rows if r["kind"] == "compute" and r["day"] >= "2026-04-01"]
    buyers: dict[str, int] = {}
    for r in late:
        buyers[r["who"]] = buyers.get(r["who"], 0) + 1
    who, n = max(buyers.items(), key=lambda t: t[1])
    since = date.fromisoformat(SINCE)
    return (f'<p class="by-lead">Since April, <b>{escape(who)}</b> was the buyer in <b>{n} of the {len(late)}</b> compute '
            f'deals of $1B or more. The biggest funding round: <b>{escape(big["who"])}</b>, {escape(big["shown"])} in '
            f'{date.fromisoformat(big["day"]):%B}.</p>'
            f'<p class="by-sub">Every funding round, compute deal and buyout of $1B or more in our stories since 1 Jan '
            f'{since.year}, each checked by hand against its story.</p>')


def _table(rows: list[dict]) -> str:
    kinds = dict(LANES)
    body = "".join(
        f'<tr id="am-{n}"><td class="pc-d" data-f="{date.fromisoformat(r["day"]):%b}">{_day(r["day"])}</td>'
        f'<td data-f="{kinds[r["kind"]]}"><span class="pc-k am-t-{r["kind"]}">{kinds[r["kind"]][:-1]}</span></td>'
        f'<td data-f="{escape(r["who"])}"><b>{escape(_name(r))}</b>'
        + (f'<span class="fx-c">{escape(r["note"])}</span>' if r["note"] else "") + "</td>"
        f'<td class="by-p" data-f="{"Reported" if r["reported"] else "Stated"}">{escape(r["shown"])}{REP if r["reported"] else ""}'
        f'<span class="fx-c"><a href="{escape(r["url"])}" rel="noopener">story</a></span></td></tr>'
        for n, r in sorted(enumerate(rows), key=lambda t: t[1]["day"], reverse=True))
    return (f'<section class="iw by-all"><h2>Every deal, newest first</h2>'
            f'<div class="iw-fbar"></div><p class="iw-count" aria-live="polite">Showing <b>{len(rows)}</b> of {len(rows)} '
            'deals. Pick a ▾ to filter. <button type="button" class="iw-clear" hidden>Clear filters</button></p>'
            '<table class="pc-rows fx-t xf-t"><thead><tr><th data-seen>Date</th><th>Kind</th><th data-nof>Who</th>'
            f'<th>Amount</th></tr></thead><tbody>{body}</tbody></table></section>\n')


def _circle(rows: list) -> str:
    def link(u, words):
        return f'<a href="{escape(u)}" rel="noopener">{escape(words)}</a>'
    return "".join(
        f'<tr><td><b>{escape(a)}</b></td><td><b>{escape(b)}</b></td>'
        f'<td>{link(u1, put)}<span class="fx-c">{m1}</span></td>'
        f'<td>{link(u2 or u1, back)}{REP if rep else ""}<span class="fx-c">{m2}</span></td></tr>'
        for a, b, put, m1, back, m2, u1, u2, rep in rows)


def _circles() -> str:
    makers = sorted({r[0] for r in INVEST_SELL})
    head = '<thead><tr><th>From</th><th>Into</th><th>What went in</th><th>What comes back</th></tr></thead>'
    return ('<section class="am-cc"><h2>Money that comes back</h2>'
            f'<p class="ins-say">{escape(", ".join(makers[:-1]))} and {escape(makers[-1])} each put money into a company '
            'that, in the same deal or an earlier one, agreed to buy their chips or cloud.</p>'
            '<h3>They invest, and the company buys from them</h3>'
            f'<table class="mt am-ct">{head}<tbody>{_circle(INVEST_SELL)}</tbody></table>'
            '<h3>They sell, and hand the buyer a share of themselves</h3>'
            f'<table class="mt am-ct">{head}<tbody>{_circle(SHARES_BACK)}</tbody></table></section>\n')


# "About these deals" rows for the added sections, after the stakes' own
LIMITS = [
    ("Big money", "Funding rounds, compute deals (chips, cloud or data-centre capacity bought for years ahead) and "
     "buyouts of $1B or more since 1 Jan 2026. Loans, bonds and venture funds raising money are left out. Rounds are "
     "closed ones: talks, plans and \"is raising\" stories wait until a story says the money came in. Buyouts are the "
     "ones on AI buyouts."),
    ("Reported", "The figure came from a news report, not the companies."),
    ("Money that comes back", "Only pairs where our stories say both halves: the money in, and the buying back."),
]


def sections(today: date) -> tuple[str, str, str]:
    """The added parts of the page: (the lead line and the month-by-month lanes, money that comes back, every deal)."""
    rows = deals()
    return _lead(rows) + _lanes(rows, today), _circles(), _table(rows)
