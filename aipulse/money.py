"""Money in the headlines, for the monthly insights (insights.py): funding rounds, valuations, acquisitions and compute
deals, read from the amounts our stories' headlines give ("Instinct raises $1B Series C at a $10B valuation").

Only what a headline says is counted, in US dollars: an amount in the summary or in another currency isn't. A story
many outlets carried counts once, and one company's round reported in two stories counts once that month. A headline
saying "reportedly", "in talks" and the like is marked reported. The company is the name the headline's verb belongs
to ("Viral AI agent Instinct raises" -> Instinct). FIXES corrects the reader by hand.
"""
from __future__ import annotations

import re

from .jurisdictions import JURISDICTIONS

# Hand corrections, by the story's URL: a dict of fields to set ({"company": "Flow Engineering"}), or None to drop it.
FIXES: dict[str, dict | None] = {
    "https://the-decoder.com/jeff-bezos-nears-10-billion-funding-round-for-ai-lab-project-prometheus/": {"company": "Prometheus"},
}

_AMOUNT = re.compile(r"\$\s?(\d+(?:[.,]\d+)*)(?:\s?(trillion|billion|bn|million|mn|[TBM])\b)?", re.I)
_SCALE = {"t": 1e12, "trillion": 1e12, "b": 1e9, "billion": 1e9, "bn": 1e9, "m": 1e6, "million": 1e6, "mn": 1e6, "": 1}
_VALUATION = re.compile(r"(?:valued at|valuation of|valuation to|values? \w+(?: \w+)? at|value (?:\w+ )?to)\s+"
                        r"(?:a |about |nearly |over |up to )?\$"
                        r"|\$[^$]{0,22}?\bvaluation\b", re.I)
ROUND = re.compile(r"\b(raise[sd]?|raising|funding|financing|series [a-h]\b|seed round|round|lands|secures|collects|bags|nabs|"
                   r"snags|closes|pulls in)\b", re.I)
ACQUIRE = re.compile(r"\b(acquires?|acquired|acquiring|acquisition of|buys|buying|to buy|will buy|purchases?|takeover of|snaps up)\b", re.I)
COMPUTE = re.compile(r"\b(cloud|compute|computing|data cent(?:er|re)s?|GPUs?|gigawatts?|GW|chips? deal|capacity|infrastructure deal)\b", re.I)
_DEAL = re.compile(r"\b(deal|deals|contract|agreement|partnership|signs|inks|inking|commit\w*|order)\b", re.I)
NOT = re.compile(r"\b(scrap\w*|scrubbed|cancel\w*|abandon\w*|halts?|walks away|called off|buyback|fund (?:for|to|focus)|new fund|"
                 r"venture fund|loses|lost|fine[sd]?|penalt\w*|lawsuit|sues|settle\w*|scam\w*|stolen|salary|pay package|revenue|"
                 r"sales|spend(?:s|ing)?|budget|grant|blocks?|blocked|rejects?|probe\w*|shares (?:surge|jump|fall|slide|drop)\w*)\b"
                 r"|^(?:why|how|what|inside|opinion)\b|\b(?:biggest|largest|record)\b.*\bIPO\b|\bIPO (?:raises|prices)", re.I)
REPORTED = re.compile(r"\b(reported(?:ly)?|report says|reports?:|in talks|talks to|sources?|said to|nears?|closing in|plans? to|"
                      r"seeks?|eyes|could|may|weighs|considers?|explores?)\b", re.I)
_VERB = re.compile(r"\b(raises?|raised|raising|lands|secures|collects|bags|nabs|snags|closes|hits|reaches|doubles|triples|"
                   r"valued|nears|becomes|is now|acquires?|buys|to buy|will buy|signs|inks|inking|agrees|strikes|wins|gets|"
                   r"draws|attracts|announces|in talks|reportedly|said|plans|seeks|eyes|now valued|at a|confirms|launches|"
                   r"unveils|debuts|pulls in|is looking|looking for|is seeking|wants|acquiring|is acquiring|to acquire|"
                   r"commits?|will deploy|deploys|continues|to invest|invests|needs)\b", re.I)
_BACKED = re.compile(r"\b(backs?|invest(?:s|ing)? in|lead(?:s)? .{0,20}round (?:in|for))\b", re.I)
_SKIP = {"AI", "Source", "Sources", "Exclusive", "Report", "Scoop", "The", "A", "An", "US", "U.S.", "UK", "EU",
         "Series", "Seed", "Startup", "YC", "CEO", "After", "With", "Ahead", "Former", "Ex", "Inside", "How", "Why", "New"}
_JOIN = ("&", "de", "of")
PLACES = {v[0] for v in JURISDICTIONS.values()} | {"India", "China", "Europe", "Asia", "Africa"}


def _value(m: re.Match) -> float:
    return float(m.group(1).replace(",", "")) * _SCALE[(m.group(2) or "").lower()]


def amounts(text: str) -> list[tuple[int, float]]:
    """Each dollar amount and where it starts: "$1.5B", "$550,000" (a bare number under $100,000 isn't one)."""
    return [(m.start(), v) for m in _AMOUNT.finditer(text) if (v := _value(m)) >= 1e5]


def amount(text: str) -> float:
    return next((v for _, v in amounts(text)), 0.0)


def _name_tok(w: str) -> bool:
    w = w.strip(",.:;'’\"()")
    return (bool(w) and w not in _SKIP and not re.search(r"-(?:based|backed|led)$|%", w) and not w.startswith("$")
            and not re.fullmatch(r"\d[\d.,]*(?:GW|MW|K|M|B|x)?", w)
            and (any(ch.isupper() for ch in w) or w[0].isdigit()))


def _clean(words: list[str]) -> str:
    while words and words[-1] in _JOIN:
        words.pop()
    name = " ".join(w.strip(",.:;\"()‘’“”'") for w in words)
    return re.sub(r"[’']s?$", "", re.split(r"[’']s? ", name)[-1])  # "Elon Musk's xAI" -> xAI


def _run(words: list[str]) -> str:
    """The first run of name-like words."""
    out = []
    for w in words:
        if _name_tok(w) or (out and w in _JOIN):
            out.append(w)
        elif out:
            break
    return _clean(out)


def subject(title: str) -> str:
    """The company a money headline is about: the last name before its verb, or the first after "backs"."""
    b = _BACKED.search(title)
    if b:
        return _run(title[b.end():].split())
    v = _VERB.search(title)
    words = (title[:v.start()] if v else title).split()
    while words and not _name_tok(words[-1]):
        words.pop()
    run = []
    while words and (_name_tok(words[-1]) or words[-1] == "&"):
        run.insert(0, words.pop())
    return _clean(run) or _run(title.split())


def _last_run(text: str) -> str:
    """The last run of name-like words before a preposition: "AI cloud startup Volta in ..." -> Volta."""
    words, runs, cur = re.split(r"\s+(?:for|in|at|after|amid|as|to|over|and|—|–|-)\s+", text, maxsplit=1)[0].split(), [], []
    for w in words + [""]:
        if w and (_name_tok(w) or (cur and w in _JOIN)):
            cur.append(w)
        elif cur:
            runs.append(cur)
            cur = []
    return _clean(runs[-1]) if runs else ""


def _after(title: str, m: re.Match) -> str:
    return _last_run(title[m.end():])


def read(c: dict) -> dict | None:
    """What a headline says about money, or None: {kind, company, amount, valuation, partner, reported}."""
    if c["url"] in FIXES and FIXES[c["url"]] is None:
        return None
    t = c.get("title") or ""
    found = amounts(t)
    if not found or NOT.search(t):
        return None
    val = 0.0
    vm = _VALUATION.search(t)
    if vm:
        val = amount(vm.group(0)) if vm.group(0).startswith("$") else next((a for p, a in found if p >= vm.start()), 0.0)
    acq, rnd = ACQUIRE.search(t), ROUND.search(t)
    if acq and rnd and rnd.start() < acq.start():  # "Shield AI raises $2B, acquires Aechelon": the amount is the round's
        acq = None
    v = _VERB.search(t)
    # the amount the verb goes with: "After Nvidia's $20B not-acqui-hire, Groq reportedly raising $650M" -> $650M
    rest = [a for p, a in found if a != val and (not v or p > v.start())] or [a for p, a in found if a != val]
    out = {"reported": bool(REPORTED.search(t)), "valuation": val, "partner": "", "amount": rest[0] if rest else 0.0}
    if acq and out["amount"] and _after(t, acq):
        out.update(kind="acquisition", company=subject(t), partner=_after(t, acq))
    elif COMPUTE.search(t) and _DEAL.search(t) and out["amount"]:
        to = next((n for w in re.finditer(r"\b(?:with|to|from|in)\s+", t)
                   if (n := _last_run(t[w.end():])) and n not in PLACES), "")
        if not to and re.search(r"\bdeals\b", t, re.I):  # "signs $517 billion in compute deals": a tally, not a deal
            return None
        out.update(kind="compute", company=subject(t), partner=to)
    elif rnd and out["amount"]:
        out.update(kind="round", company=subject(t))
    elif val:
        out.update(kind="valuation", company=subject(t), amount=0.0)
    else:
        return None
    if (out["kind"] == "round" and out["amount"] > 1e11) or out["valuation"] > 1e13:  # a misread, not a round
        return None
    out.update(FIXES.get(c["url"]) or {})
    return out if out.get("company") else None


def month(cards: list[dict]) -> list[dict]:
    """The month's money stories, one per company and kind (the most reported kept), each with its story's fields."""
    best: dict[tuple, dict] = {}
    for c in cards:
        if c.get("category") == "research":
            continue
        r = read(c)
        if not r:
            continue
        outlets = 1 + len({a["source"] for a in c.get("also") or []} - {c["source"]})
        r.update(date=c["date"][:10], url=c["url"], source=c["source"], outlets=outlets, tags=list(c.get("tags") or []),
                 text=f"{c.get('title') or ''} {c.get('summary') or ''}")
        key = (r["company"].lower(), "round" if r["kind"] == "valuation" else r["kind"], r["partner"].lower())
        if key not in best and r["amount"]:  # one round told two ways in the same days ("Former Infosys chief's AI
            # startup nabs $53M", "Hang Ten raises $53M")
            key = next((k for k, o in best.items() if k[1] == key[1] and o["amount"]
                        and abs(o["amount"] - r["amount"]) <= .02 * r["amount"]
                        and abs(int(o["date"][8:]) - int(r["date"][8:])) <= 3), key)
        old = best.get(key)
        if old is None or (r["outlets"], r["amount"], r["valuation"]) > (old["outlets"], old["amount"], old["valuation"]):
            if old is not None:  # keep the amounts the other story gave
                r["valuation"] = r["valuation"] or old["valuation"]
                r["amount"] = r["amount"] or old["amount"]
                if old["kind"] == "round":
                    r["kind"] = "round"
            best[key] = r
        else:
            old["valuation"] = old["valuation"] or r["valuation"]
            old["amount"] = old["amount"] or r["amount"]
            if r["kind"] == "round":
                old["kind"] = "round"
    return sorted(best.values(), key=lambda r: r["date"])


def usd(v: float) -> str:
    for s, k in ((1e12, "T"), (1e9, "B"), (1e6, "M")):
        if v >= s:
            n = v / s
            return f"${n:.1f}{k}".replace(".0" + k, k) if n < 100 else f"${n:.0f}{k}"
    return f"${v / 1e3:.0f}K"
