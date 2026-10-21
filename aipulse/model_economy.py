"""The model economy (model-economy/): what new AI models cost and how long before you must switch. Two tables, one
under the other. Launch prices: each new model's launch price on its lab's own API (from Release cards) against the
model before it in the same line, that model's launch price checked by hand here. How long before you must switch: the
days between a lab telling developers a model will shut down and the day it does, from Models being retired, so nothing
is entered twice. Linked from Releases' strip.
"""
from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path
from statistics import median

from . import pages, release_cards, retired, rss

PATH = "model-economy/"
# a new model (as Release cards names it): the model before it in the same line, as Release cards names it (its
#  launch price and story taken from there); or, for one Release cards doesn't hold at a single per-token price, a tuple
#  of (that model, its launch price on the lab's own API as "$in / $out" per 1M tokens, its story or the lab's page)
BEFORE = {
    "Claude Opus 5": "Claude Opus 4.8",
    "Claude Opus 5.5": "Claude Opus 5",
    "Grok 4.6": "Grok 4.5",
    "Grok 4.7": "Grok 4.6",
    "Muse Spark 1.3": "Muse Spark 1.1",
    "Gemini 3.7 Flash": "Gemini 3.5 Flash",
    "Gemini 3.8 Flash": "Gemini 3.7 Flash",
    "GPT-6.1 Sol": ("GPT-6 Sol", "$2 / $10",
                    "https://the-decoder.com/openais-gpt-6-sol-and-luna-cut-prices-in-half-but-barely-move-the-needle-on-performance/"),
    "DeepSeek V4.1 Flash": ("DeepSeek V4 Flash", "$0.14 / $0.28",
                            "https://the-decoder.com/as-agentic-ai-pushes-rivals-to-raise-prices-and-cap-usage-deepseek-ships-a-good-enough-model-for-almost-nothing/"),
}
# priced releases checked and left out of Launch prices, with why
LEFT_OUT = {}
FROM = "2026-01-01"  # How long before you must switch counts shutdowns from this day
SHOWN = 10  # model rows shown before "Show all"
_PRICE = re.compile(r"^\$([\d.]+) / \$([\d.]+)$")
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _day(d: str) -> str:
    y, m, day = d.split("-")
    return f"{int(day)} {_MONTHS[int(m) - 1]} {y}"


def _days(n: int) -> str:
    return f"{n} day{'s' * (n != 1)}"


def _per_token(price: str) -> tuple[float, float] | None:
    """'$4 / $20' as (4.0, 20.0); None for a price per image, minute or hour, or one naming several models."""
    m = _PRICE.match(price.split("|")[0].strip())
    unit = re.match(r"(a|an) ", price.split("|")[1]) if "|" in price else None  # "|a minute of audio", "|an image"
    return (float(m[1]), float(m[2])) if m and not unit else None


def candidates(cards: list[dict] | None = None, since: str = "") -> list[dict]:
    """Release cards rows with a per-token launch price that neither BEFORE nor LEFT_OUT holds: to find the model
    before each in the same line and its launch price on the lab's own page. Newest first."""
    return [{"date": r["day"], "source": r["lab"], "title": f"{r['model']} ({r['price'].split('|')[0]})", "url": r["url"]}
            for r in release_cards.rows() if _per_token(r["price"]) and r["model"] not in BEFORE
            and r["model"] not in LEFT_OUT and r["day"] >= since]


def prices() -> list[dict]:
    """Each model in BEFORE that Release cards has at a per-token price: both prices and how the new one compares."""
    rows, out = release_cards.rows(), []
    held = {r[2]: (r[2], r[9].split("|")[0], r[10]) for r in release_cards.RELEASES}  # before July too
    for r in rows:
        if r["model"] not in BEFORE or not (new := _per_token(r["price"])):
            continue
        was_model, was_price, was_url = held[BEFORE[r["model"]]] if isinstance(BEFORE[r["model"]], str)             else BEFORE[r["model"]]
        was = _per_token(was_price)
        if new == was:
            way, say = "same", "Same"
        elif new[0] <= was[0] and new[1] <= was[1]:
            cut = {round(100 * (1 - n / w)) for n, w in zip(new, was)}
            way, say = "down", f"{cut.pop()}% cheaper" if len(cut) == 1 else "Cheaper"
        elif new[0] >= was[0] and new[1] >= was[1]:
            rise = {round(100 * (n / w - 1)) for n, w in zip(new, was)}
            way, say = "up", f"{rise.pop()}% pricier" if len(rise) == 1 else "Pricier"
        else:
            way, say = "mixed", "Input " + ("cheaper" if new[0] < was[0] else "pricier") + ", output " + \
                ("cheaper" if new[1] < was[1] else "pricier")
        if say in ("Cheaper", "Pricier"):  # in and out moved by different amounts: say both
            say += ": in " + ", out ".join(f"{round(100 * (n / w - 1)):+d}%" for n, w in zip(new, was))
        note =r["price"].split("|")[1] if "|" in r["price"] else ""
        out.append(r | {"was_model": was_model, "was_price": was_price, "was_url": was_url, "way": way, "say": say,
                        "price_note": note[:1].upper() + note[1:]})
    return out


def warnings(saved: dict) -> list[dict]:
    """Every model (not a whole product) set to shut down from FROM on, with the days between the lab telling
    developers and the shutdown ('days' None when the lab's page gives no such day). Latest shutdown first."""
    rows = [r | {"days": (date.fromisoformat(r["shuts"]) - date.fromisoformat(r["told"])).days if r.get("told") else None}
            for got in saved.values() for r in got.get("rows", []) if r.get("kind", "model") == "model"
            and r["shuts"] >= FROM]
    return sorted(rows, key=lambda r: (r["shuts"], r["model"]), reverse=True)


_WAY = {"down": "pc-yes", "same": "me-same", "up": "pc-no", "mixed": "me-mixed"}


def _line(model: str) -> str:
    """The first model of `model`'s line, following BEFORE back, so a line's rows sit together."""
    while isinstance(BEFORE.get(model), str):
        model = BEFORE[model]
    return BEFORE[model][0] if model in BEFORE else model


def _price(p: str) -> str:
    """'$5 / $25' as '$5 in · $25 out'."""
    m = _PRICE.match(p.strip())
    return f"${m[1]} in · ${m[2]} out" if m else p


def _prices_box(ps: list[dict]) -> str:
    n = {w: sum(p["way"] == w for p in ps) for w in _WAY}
    said = [f"{n['same']} kept the price of the model before", f"{n['down']} cost less", f"{n['up']} cost more"] \
        + [f"{n['mixed']} cost less on one side and more on the other"] * bool(n["mixed"])
    lead = f"Of {len(ps)} new models, " + ", ".join(said[:-1]) + f" and {said[-1]}."
    newest: dict[str, str] = {}
    for p in ps:
        newest[_line(p["model"])] = max(newest.get(_line(p["model"]), ""), p["day"])
    # a line's rows together, newest first; the line with the newest launch on top
    ps = sorted(ps, key=lambda p: (newest[_line(p["model"])], _line(p["model"]), p["day"]), reverse=True)
    rows = "".join(
        f'<tr class="{"me-top" if k and _line(ps[k - 1]["model"]) != _line(p["model"]) else ""}">'
        f'<td>{escape(p["lab"])}</td>'
        f'<td data-l="Before">{escape(p["was_model"])}<span class="me-p"><a href="{escape(p["was_url"])}" '
        f'rel="noopener">{escape(_price(p["was_price"]))}</a></span></td>'
        f'<td data-l="New"><a href="{escape(p["url"])}" rel="noopener"><b>{escape(p["model"])}</b></a>'
        f'<span class="me-p"><b>{escape(_price(p["price"].split("|")[0]))}</b></span>'
        + (f'<span class="fx-c">{escape(p["price_note"])}</span>' if p["price_note"] else "")
        + f'<span class="fx-c">Launched {_day(p["day"])}</span></td>'
        f'<td><span class="pc-k {_WAY[p["way"]]}">{escape(p["say"])}</span></td></tr>'
        for k, p in enumerate(ps))
    return _box("Launch prices", "Is the new model cheaper or pricier than the one before it?",
                f'<p class="pc-lead">{escape(lead)}</p><p class="me-unit">Each price is in US dollars per million '
                "tokens (the chunks of text a model reads and writes), on the lab's own API at launch: one price for "
                'text sent in, one for text the model writes out.</p><table class="pc-rows fx-t me-prices"><thead>'
                '<tr><th>Lab</th><th>The model before</th><th>The new model</th><th>Price change</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>')


def _tag(n: int) -> str:
    return f'<span class="pc-k {"pc-no" if n < 30 else "me-mid" if n < 90 else "pc-yes"}">{_days(n)}</span>'


def _warnings_box(ws: list[dict]) -> str:
    told = [w for w in ws if w["days"] is not None]
    labs = []
    for lab in retired.LABS:
        mine = [w for w in ws if w["lab"] == lab]
        d = [w["days"] for w in mine if w["days"] is not None]
        if mine:
            labs.append((lab, len(mine), d))
    labs.sort(key=lambda x: (-median(x[2]) if x[2] else 1, x[0]))
    lead = []
    if told:
        top, short = labs[0], min(told, key=lambda w: w["days"])
        lead = [f"{top[0]} gives the most warning: a median of {_days(int(median(top[2])))}.",
                f"The shortest was {short['lab']}'s: {_days(short['days'])}."]
    lab_rows = "".join(
        f'<tr><td><b>{escape(lab)}</b></td><td data-l="Models shutting down">{n}</td>'
        + (f'<td data-l="Median warning"><b>{_days(int(median(d)))}</b></td><td data-l="Shortest">{_days(min(d))}</td>'
           f'<td data-l="Longest">{_days(max(d))}</td>' if d else
           '<td colspan="3" class="fx-c">Its page gives no day it told developers</td>') + "</tr>"
        for lab, n, d in labs)

    def row(w: dict) -> str:
        url, _ = retired.LABS[w["lab"]]
        return (f'<tr><td class="pc-d">{_day(w["shuts"])}</td><td><b>{escape(w["model"])}</b></td>'
                f'<td><a href="{escape(url)}" rel="noopener">{escape(w["lab"])}</a></td><td data-l="Told developers">'
                f'{_day(w["told"])}</td><td data-l="Warning">{_tag(w["days"])}</td><td>{escape(w.get("replace") or "–")}</td></tr>')
    head = ("<thead><tr><th>Shuts down</th><th>Model</th><th>Lab</th><th>Told developers</th><th>Warning</th>"
            "<th>Replace with</th></tr></thead>")
    rest = told[SHOWN:]
    more = (f'<tbody class="me-rest" hidden>{"".join(row(w) for w in rest)}</tbody>' if rest else "")
    button = (f'<button type="button" class="lt-more me-more" aria-expanded="false" data-show="Show all {len(told)}" '
              f'data-hide="Show fewer">Show all {len(told)}</button>' if rest else "")
    return _box("How long before you must switch", "How much warning do labs give before a model stops working?",
                (f'<p class="pc-lead">{escape(" ".join(lead))}</p>' if lead else "")
                + '<table class="pc-rows fx-t me-labs"><thead><tr><th>Lab</th><th>Models shutting down</th>'
                '<th>Median warning</th><th>Shortest</th><th>Longest</th></tr></thead><tbody>' + lab_rows
                + f'</tbody></table><table class="pc-rows fx-t me-models">{head}<tbody>'
                + "".join(row(w) for w in told[:SHOWN]) + f"</tbody>{more}</table>{button}")


def _box(title: str, question: str, inner: str) -> str:
    return (f'<section class="pc-half me-box"><div class="pc-hh"><h2>{title}</h2><p>{escape(question)}</p></div>'
            f'<div class="pc-in">{inner}</div></section>')


# "Show all", in the reader's browser
SCRIPT = """<script>
(()=>{const b=document.querySelector('.me-more');if(b)b.addEventListener('click',()=>{const t=document.querySelector('.me-rest'),
open=t.hidden;t.hidden=!open;b.setAttribute('aria-expanded',open);b.textContent=open?b.dataset.hide:b.dataset.show})})();
</script>"""


def body(ps: list[dict], ws: list[dict]) -> str:
    limits = [
        ("Launch prices", "The price on the lab's own API when the model launched, per million tokens sent in "
         "and written out, from Release cards. The model before is the last one in the same line (Opus after "
         "Opus, Flash after Flash), its launch price checked by hand against its story or the lab's page. Models "
         "priced per image, minute or hour, and models with no earlier one in their line, aren't shown."),
        ("Warning", "The days between the day a lab told developers a model will shut down and the shutdown, from "
         "each lab's own deprecation page (Models being retired). Models shutting down since 1 Jan 2026, including "
         "those scheduled; whole products (an app builder, an API) are left out."),
        ("Median", "The middle value: half the lab's models had more warning, half less."),
    ]
    return ('<div class="ft jb pc me">\n'
            + pages.feature_head(PATH, "The model economy", "What do new models cost, and how long before you must "
                                 "switch?", "Launch prices from each lab's own API, set against the last model in the "
                                 "same line; shutdown dates and the day the lab told developers from each lab's "
                                 "deprecation page.", sub="The cost of keeping up")
            + '<div class="pc-stack">' + (_prices_box(ps) if ps else "") + (_warnings_box(ws) if ws else "")
            + "</div>\n"
            '<section class="jb-lim"><h2>About these rows</h2>\n<table class="mt jb-small jb-limits"><tbody>'
            + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
            + f"</tbody></table></section></div>\n{SCRIPT}")


def build(conn, cards: list[dict], out: Path, today) -> list[str]:
    ps, ws = prices(), warnings(retired.load(conn))
    if not ps and not ws:
        return []
    what = ("What do new AI models cost, and how long before you must switch? Each new model's launch price against "
            "the one before it, and how much warning each lab gives before a model shuts down.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "The model economy",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("The model economy · AI Pulse", what, PATH, body(ps, ws), data, pages.frame(conn, len(cards)),
                   ("/releases/", "Back to Releases"),
                   "Launch prices come from Release cards and the labs' own pages; shutdowns from the labs' own "
                   "deprecation pages."),
        encoding="utf-8")
    return [PATH]
