"""Lab timelines (lab-timelines/): what each AI lab released, repriced, took to new places and switched off, month by
month since July 2026, with the next three months' scheduled shutdowns in a grey column. Releases come from Release
cards and shutdowns from Models being retired, so nothing is entered twice; price changes and new places are checked
by hand here. Labs with a single release are collapsed under the grid. Linked from Releases' strip.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import pages, release_cards, retired, rss

PATH = "lab-timelines/"
SINCE = release_cards.SINCE
AHEAD = 92  # days of scheduled shutdowns in the grey column
# an existing model's API price changing: (day it took effect, lab as release_cards.COUNTRY writes it, model, "cut" or
#  "rise", what changed in a few words (shown in the grid), the prices (shown in the lab's table), the story or lab page)
PRICES = [
    ("2026-07-30", "OpenAI", "GPT-5.6 Luna", "cut", "80% cheaper", "Now $0.20 / $1.20 per 1M tokens in / out",
     "https://the-decoder.com/openai-goes-full-china-pricing-mode-with-an-80-percent-cut-to-its-most-affordable-gpt-5-6-model/"),
    ("2026-07-30", "OpenAI", "GPT-5.6 Terra", "cut", "20% cheaper", "Now $2 / $12 per 1M tokens in / out",
     "https://the-decoder.com/openai-goes-full-china-pricing-mode-with-an-80-percent-cut-to-its-most-affordable-gpt-5-6-model/"),
    ("2026-08-16", "DeepSeek", "V4-Pro", "rise", "dearer",
     "Off-peak $0.435 / $0.87 → $0.66 / $1.98 per 1M tokens in / out; a new peak rate of $1.32 / $3.96",
     "https://the-decoder.com/deepseek-launches-an-improved-v4-pro-model-raises-api-prices-and-makes-its-agent-software-open-source/"),
    ("2026-10-07", "Anthropic", "Sonnet 5.5 cache reads", "cut", "half price", "$0.20 → $0.10 per 1M tokens",
     "https://siliconangle.com/2026/10/07/anthropic-releases-claude-haiku-5-5-small-model-and-halves-sonnet-5-5-cache-read-prices/"),
]
# a model reaching places after its launch: (day, lab, model, where, in a few words, the story or lab page)
PLACES = [
    ("2026-07-17", "xAI", "Grok 4.5", "now in the EU", "https://docs.x.ai/developers/release-notes"),
    ("2026-10-13", "Google", "Gemini 4 Argon", "now worldwide",
     "https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-argon/"),
]
# a model the lab took away from its users after launch (not one cancelled before it, nor a feature or app): (day,
#  lab, model, why in a few words as the lab or story gives it, the story or lab page)
PULLED = []
# stories checked and left out, with why
LEFT_OUT = {
    "https://the-decoder.com/deepseek-makes-its-75-percent-discount-permanent-pricing-output-tokens-at-least-34x-below-gpt-5-5/":
        "A promotion made permanent: the old price and the date it took effect aren't stated",
    "https://the-decoder.com/metas-muse-spark-1-1-api-pricing-squeezes-openai-and-anthropic-as-the-ai-price-war-heats-up/":
        "A new model's launch price, not a change",
    "https://the-decoder.com/xai-drops-grok-4-3-with-steep-price-cuts-and-an-imagine-agent-mode-for-creative-projects/":
        "A new model's launch price, not a change",
    "https://the-decoder.com/claude-sonnet-5-continues-anthropics-pattern-of-hiding-price-increases-behind-unchanged-token-rates/":
        "A new model at unchanged token prices, not a change",
    "https://techcrunch.com/2026/06/29/anthropic-and-gov-newsom-forge-deal-allowing-california-government-to-use-claude-at-half-price/":
        "A deal for California agencies, not a public API price; the models and discount aren't stated",
    "https://the-decoder.com/openai-vs-anthropic-a-price-war-over-api-tokens-is-brewing/":
        "Price cuts weighed, none made",
    "https://techcrunch.com/2026/07/13/anthropic-starts-localizing-claude-pricing-for-india-its-biggest-market-after-the-us/":
        "Subscription prices in India, not the API",
    "https://www.marktechpost.com/2026/09/01/anthropic-releases-claude-fable-5-1-and-claude-mythos-5-1-52-6-on-terminal-bench-science-and-75-cheaper-cache-reads/":
        "75% cheaper cache reads: which models it covers isn't stated",
    "https://techcrunch.com/2026/09/01/anthropics-new-fable-release-is-cheaper-less-restrictive/":
        "A new model's launch price, not a change",
    "https://the-decoder.com/alibaba-launches-qwen-audio-3-1-with-five-new-models-and-slashes-ai-audio-prices-by-up-to-95-percent/":
        "New models' launch prices, not a change",
    "https://the-decoder.com/anthropic-drops-the-surcharge-for-million-token-context-windows-making-opus-4-6-and-sonnet-4-6-far-cheaper/":
        "Long-context surcharge dropped, standard price unchanged; its date and the API aren't stated",
    "https://siliconangle.com/2026/04/09/anthropic-openai-target-big-businesses-enterprise-grade-controls-lower-pricing/":
        "Subscription plan prices, not the API",
    "https://techcrunch.com/2026/04/09/chatgpt-pro-plan-100-month-codex/":
        "Subscription price, not the API",
    "https://the-decoder.com/openai-shifts-to-usage-based-pricing-for-codex-in-chatgpt-business-plans/":
        "Codex plan pricing, not the API",
    "https://openai.com/index/codex-flexible-pricing-for-teams":
        "Codex plan pricing, not the API",
    "https://the-decoder.com/claude-cowork-expands-to-all-paid-plans-on-macos-and-windows-with-new-org-controls/":
        "An app's plans, not a model reaching places",
    "https://techcrunch.com/2026/03/26/bytedances-new-ai-video-generation-model-dreamina-seedance-2-0-comes-to-capcut/":
        "An app, not a model reaching countries or regions",
    "https://deepmind.google/blog/gemini-3-1-flash-lite-built-for-intelligence-at-scale/":
        "A new model's launch price, not a change",
    "https://the-decoder.com/bytedances-seed2-0-adds-even-more-price-pressure-on-western-ai-models/":
        "New models' launch prices, not a change",
    "https://the-decoder.com/chinese-ai-lab-zhipu-releases-glm-5-under-mit-license-claims-parity-with-top-western-models/":
        "A new model's release, not a change",
    "https://techcrunch.com/2026/01/27/googles-ai-plus-plan-rolls-out-to-all-markets-including-the-u-s/":
        "A subscription plan, not a model",
    "https://openai.com/index/introducing-chatgpt-go":
        "A subscription plan, not a model",
    "https://techcrunch.com/2026/02/04/alexa-amazons-ai-assistant-is-now-available-to-everyone-in-the-u-s/":
        "An assistant app, not a model",
    "https://techcrunch.com/2026/01/05/alexa-without-an-echo-amazons-ai-chatbot-comes-to-the-web-and-a-revamped-alexa-app/":
        "An assistant app, not a model",
    "https://www.minimax.io/blog/minimax-m31f":
        "A new model's launch price, not a change",
    "https://www.businesskorea.co.kr/news/articleView.html?idxno=279066":
        "A temporary Google cut: the model, prices and dates aren't stated",
}
# the newest day every story was read for PRICES, PLACES and LEFT_OUT; the daily job moves it on
CHECKED_TO = "2026-10-18"
# a headline that may be a price change or a model reaching new places
_PRICE = re.compile(r"\b(price[sd]?|pricing|cheaper|dearer|discount|per million|per 1M|halves|slash(es)?)\b", re.I)
_PLACE = re.compile(r"\b(now available|available (in|to)|rolls? out (in|to)|expands? to|arrives? in|launch(es)? in|"
                    r"comes? to|reaches)\b", re.I)
_PULL = re.compile(r"\b(pull(s|ed)?|withdraw[sn]?|withdrew|roll(s|ed)? back|rollback|revert(s|ed)?|takes? down|"
                   r"taken down|removes?|suspend(s|ed)?|disables?)\b", re.I)


def candidates(cards: list[dict], since: str = "", today: date | None = None) -> list[dict]:
    """Stories from after CHECKED_TO (or `since`, if later) that no row uses and LEFT_OUT doesn't hold, whose headline
    may be an AI model's price change, its reaching new places or its being pulled. Newest first."""
    since = max(since, CHECKED_TO + "~")
    used = {r[-1] for r in PRICES + PLACES + PULLED} | set(LEFT_OUT)
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["date"] >= since and not any(s["url"] in used for s in [c, *(c.get("also") or [])])
            and any(_PRICE.search(s["title"]) or _PLACE.search(s["title"]) or _PULL.search(s["title"]) for s in [c, *(c.get("also") or [])])]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a timelines/<day> branch: each price change and new place it adds, and the
    stories it left out; None when it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("PRICES", "PLACES", "PULLED", "LEFT_OUT"))
    rows = [(d, lab, m, f"Price {k}: {detail}", u) for d, lab, m, k, _, detail, u in PRICES if u not in had["PRICES"]]
    rows += [(d, lab, m, where, u) for d, lab, m, where, u in PLACES if u not in had["PLACES"]]
    rows += [(d, lab, m, f"Pulled: {why}", u) for d, lab, m, why, u in PULLED if u not in had["PULLED"]]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("Lab timelines", f"change{'s' * (len(rows) != 1)}", branch,
                        ("Day", "Lab", "Model", "What changed", "Source"), sorted(rows), dropped)


def events(saved: dict, today: date) -> list[dict]:
    """Every row on the timelines since SINCE: releases, price changes, new places, and shutdowns up to AHEAD days
    from today (a shutdown day's models in one row)."""
    end = (today + timedelta(days=AHEAD)).isoformat()
    ev = [{"day": r["day"], "lab": r["lab"], "kind": "release", "weights": r["weights"], "text": r["model"],
           "detail": r["weights"] + (f" · launch price {r['price'].split('|')[0]}" if r["price"].split("|")[0] else ""),
           "url": r["url"]} for r in release_cards.rows()]
    ev += [{"day": d, "lab": lab, "kind": k, "text": f"{m} {short}", "detail": detail, "url": u}
           for d, lab, m, k, short, detail, u in PRICES if d >= SINCE]
    ev += [{"day": d, "lab": lab, "kind": "place", "text": f"{m} {where}", "detail": "", "url": u}
           for d, lab, m, where, u in PLACES if d >= SINCE]
    ev += [{"day": d, "lab": lab, "kind": "pulled", "text": f"{m} pulled", "detail": why, "url": u}
           for d, lab, m, why, u in PULLED if d >= SINCE]
    for lab, got in saved.items():
        days = defaultdict(list)
        for r in got.get("rows", []):
            if SINCE <= r["shuts"] <= end:
                days[r["shuts"]].append(r["model"])
        ev += [{"day": d, "lab": lab, "kind": "shut", "n": len(ms), "text": ", ".join(ms), "detail": "",
                "url": f"/{retired.PATH}"} for d, ms in days.items()]
    return sorted(ev, key=lambda e: e["day"])


_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _months(today: date) -> list[str]:
    y, m = map(int, SINCE[:7].split("-"))
    out = []
    while (y, m) <= (today.year, today.month):
        out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


DOT = {"Open": "lt-o", "Weights only": "lt-wo", "Closed": "lt-c"}


def _cell(es: list[dict], ahead: bool) -> str:
    out = [f'<span class="lt-r"><b class="lt-dot {DOT[e["weights"]]}"></b>{escape(e["text"])}</span>'
           for e in es if e["kind"] == "release"]
    out += [f'<span class="lt-p">{"↓" if e["kind"] == "cut" else "↑" if e["kind"] == "rise" else "+"} '
            f'{escape(e["text"])}</span>' for e in es if e["kind"] in ("cut", "rise", "place")]
    out += [f'<span class="lt-x">✕ {escape(e["text"])}</span>' for e in es if e["kind"] == "pulled"]
    n = sum(e["n"] for e in es if e["kind"] == "shut")
    if n:
        out.append(f'<span class="lt-s">{n} shut down{" (scheduled)" if ahead else ""}</span>')
    return "".join(out)


def _details(lab: str, es: list[dict], today: date) -> str:
    what = {"release": "Release", "cut": "Price cut", "rise": "Price rise", "place": "New places", "pulled": "Pulled",
            "shut": "Shut down"}
    rows = []
    for e in sorted(es, key=lambda e: e["day"], reverse=True):
        if e["kind"] == "shut":
            kind = "Shuts down" if e["day"] > today.isoformat() else "Shut down"
            text = (f'<a href="{e["url"]}">{e["n"]} model{"s" * (e["n"] != 1)}</a>'
                    f'<small>{escape(e["text"])}</small>')
        else:
            kind = what[e["kind"]]
            text = (f'<a href="{escape(e["url"])}" rel="noopener">{escape(e["text"])}</a>'
                    + (f'<small>{escape(e["detail"])}</small>' if e["detail"] else ""))
        rows.append(f'<tr><td class="rm-d">{_day(e["day"])}</td><td>{kind}</td><td>{text}</td></tr>')
    return (f'<section class="lt-lab" data-lab="{escape(lab, quote=True)}" hidden><h2>{escape(lab)}</h2>'
            '<div class="rm-wrap"><table class="mt rm-t lt-d"><thead><tr><th>Date</th><th>What</th><th>Details</th>'
            '</tr></thead><tbody>' + "".join(rows) + "</tbody></table></div></section>")


def _day(d: str) -> str:
    y, m, day = d.split("-")
    return f"{int(day)} {_MONTHS[int(m) - 1]} {y}"


def _lead(by: dict, today: date) -> str:
    since = _day(SINCE).rsplit(" ", 1)[0]
    rel = Counter({lab: sum(e["kind"] == "release" for e in es) for lab, es in by.items()})
    shut = Counter({lab: sum(e.get("n", 0) for e in es) for lab, es in by.items()})
    say = []
    for counts, verb in ((rel, "released the most models"), (shut, "shut down or scheduled for shutdown the most models")):
        if not counts or not max(counts.values()):
            continue
        top = max(counts.values())
        names = sorted(lab for lab, n in counts.items() if n == top)
        who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
        say.append(f"{who} {verb} ({top})")
    return f"Since {since}, " + ". ".join(say) + "." if say else ""


# the lab buttons and the collapsed labs, in the reader's browser
SCRIPT = """<script>
(()=>{const pg=document.querySelector('.lt');
pg.querySelectorAll('.lt-name').forEach(b=>b.addEventListener('click',()=>{const on=b.getAttribute('aria-pressed')!=='true';
pg.querySelectorAll('.lt-name').forEach(o=>o.setAttribute('aria-pressed','false'));
pg.querySelectorAll('.lt-lab').forEach(s=>s.hidden=!on||s.dataset.lab!==b.dataset.lab);
if(on){b.setAttribute('aria-pressed','true');pg.querySelector('.lt-lab:not([hidden])').scrollIntoView({behavior:'smooth',block:'nearest'})}}));
const more=pg.querySelector('.lt-more');if(more)more.addEventListener('click',()=>{const t=pg.querySelector('.lt-few'),open=t.hidden;
t.hidden=!open;more.setAttribute('aria-expanded',open);more.textContent=open?more.dataset.hide:more.dataset.show})})();
</script>"""


def body(ev: list[dict], today: date) -> str:
    months = _months(today)
    by = defaultdict(list)
    for e in ev:
        by[e["lab"]].append(e)
    nrel = lambda lab: sum(e["kind"] == "release" for e in by[lab])  # noqa: E731
    one = lambda lab: len(by[lab]) == 1 and by[lab][0]["kind"] == "release"  # noqa: E731
    order = sorted(by, key=lambda lab: (-nrel(lab), -len(by[lab]), lab))
    main, few = [lab for lab in order if not one(lab)], [lab for lab in order if one(lab)]
    now = today.isoformat()

    def row(lab: str) -> str:
        cells = "".join(f'<td data-l="{_MONTHS[int(m[5:]) - 1]} {m[:4]}">'
                        f"{_cell([e for e in by[lab] if e['day'][:7] == m and e['day'] <= now], False)}</td>"
                        for m in months)  # data-l: the month, for phones, where each lab is a card
        cells += f'<td class="lt-fut" data-l="Next 3 months">{_cell([e for e in by[lab] if e["day"] > now], True)}</td>'
        return (f'<tr><th scope="row"><button type="button" class="lt-name" data-lab="{escape(lab, quote=True)}" '
                f'aria-pressed="false">{escape(lab)}</button></th>{cells}</tr>')

    head = "".join(f"<th>{_MONTHS[int(m[5:]) - 1]}{' ' + m[:4] if m[5:] == '01' else ''}</th>" for m in months)
    limits = [
        ("Releases", "From Release cards: new AI models at least two news outlets reported within three days of "
         "launch. The dot is green when the weights can be downloaded and used commercially, orange when they can be "
         "downloaded but not used commercially, black when there is nothing to download."),
        ("↓ ↑ Price", "A model already on sale whose API price went down or up, from the day it took effect. A new "
         "model that costs less than the one before is a release, not a price cut. Each checked against its story or "
         "the lab's own page."),
        ("+ New places", "A model reaching countries or regions after its launch, as the lab or a story names them."),
        ("Shut down", "From Models being retired: models OpenAI, Anthropic, Google and Mistral switched off, or have "
         "set a date to switch off within the next three months (the grey column). Other labs publish no such dates."),
    ] + ([("✕ Pulled", "A model the lab took away from its users after launching it, as the lab or a story says. A "
           "model cancelled before launch, or a feature taken out of an app, is not counted.")] if PULLED else []) + [
        ("Each lab", "Tap a lab's name for its rows as a table, each linking to its source."),
    ]
    few_rows = (f'<tbody class="lt-few" hidden>{"".join(row(lab) for lab in few)}</tbody>' if few else "")
    more = (f'<button type="button" class="lt-more" aria-expanded="false" '
            f'data-show="{len(few)} more labs with one release each: show them" data-hide="Hide them">'
            f'{len(few)} more labs with one release each: show them</button>' if few else "")
    return ('<div class="ft jb rm lt">\n'
            + pages.feature_head(PATH, "Lab timelines", "Who ships, who reprices, who switches models off?",
                                 escape(_lead(by, today)))
            + '<div class="lt-leg"><span><b class="lt-dot lt-o"></b>Open weights</span><span><b class="lt-dot lt-wo"></b>'
            'Weights only</span><span><b class="lt-dot lt-c"></b>Closed</span><span class="lt-p">↓ price cut · ↑ price '
            'rise · + new places</span>' + ('<span class="lt-x">✕ pulled</span>' if PULLED else "")
            + '<span class="lt-s">grey = scheduled</span></div>\n'
            '<div class="rm-wrap lt-wrap"><table class="mt lt-t"><thead><tr><th>Lab</th>' + head
            + '<th class="lt-fut">Next 3 months</th></tr></thead><tbody>' + "".join(row(lab) for lab in main)
            + "</tbody>" + few_rows + "</table></div>\n" + more
            + "".join(_details(lab, by[lab], today) for lab in order)
            + '\n<section class="jb-lim"><h2>About these timelines</h2>\n<table class="mt jb-small jb-limits"><tbody>'
            + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
            + "</tbody></table></section></div>\n" + SCRIPT)


def build(conn, cards: list[dict], out: Path, today) -> list[str]:
    ev = events(retired.load(conn), today)
    if not ev:
        return []
    what = ("What each AI lab released, repriced and switched off, month by month since July 2026, with the "
            "shutdowns scheduled for the next three months.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Lab timelines", "description": what,
            "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("Lab timelines · AI Pulse", what, PATH, body(ev, today), data, pages.frame(conn, len(cards)),
                   ("/releases/", "Back to Releases"),
                   "Releases come from Release cards and shutdowns from the labs' own deprecation pages. Price "
                   "changes and new places are added once checked by hand."),
        encoding="utf-8")
    return [PATH]
