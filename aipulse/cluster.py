"""Group stories that report the same event, so each shows once with all its sources.

Two stories are the same event when they're in the same tab, were reported within WINDOW_DAYS of each
other, and share enough *distinctive* words. Words are weighted by rarity across all stored stories
(inverse document frequency), so shared names like "DraftKings" or "Kotek" count for much more than
common words like "rules" or "new". Similarity is the weight of the shared words divided by the weight
of the shorter story's words, so a short headline fully contained in a longer one scores high.

Each group's lead is the story with the most informative summary (then the earliest); the others are
listed on the lead's card as "Also covered by".
"""

from __future__ import annotations

import math
import re
from datetime import date

from . import brief, classify, jurisdictions

WINDOW_DAYS = 3
THRESHOLD = 0.25
MIN_SHARED = 2  # distinctive words in common, so two short headlines can't match on one name

_STOP = set("""
a an the and or but of to in on for with as at by from into over under about after before amid than that this
these those its it is are was were be been being has have had will would can could may might must should not no
new says said say how why what when who which where more most over up out off just also still now amid via vs
ai artificial intelligence report reports reportedly first year years week today latest update news
""".split())
_TOKEN = re.compile(r"[a-z0-9][a-z0-9'\-]+")


def _stem(word: str) -> str:
    word = word.strip("'-").removesuffix("'s")
    for suffix in ("ing", "ies", "es", "ed", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return word


# Outlets describe one event in different words; map them to one (stemmed) form.
_SYNONYMS = {
    **dict.fromkeys(["probe", "investigat", "examine", "evaluate", "evaluation", "scrutiny", "review"], "investigat"),
    **dict.fromkeys(["regulator", "watchdog", "commission", "authority", "authorit"], "regulator"),
    **dict.fromkeys(["bill", "legislation"], "bill"),
    **dict.fromkeys(["unveil", "propos", "introduc"], "propos"),
    **dict.fromkeys(["sign", "issu", "establish", "creat", "pass"], "enact"),
    **dict.fromkeys(["safeguard", "safety", "oversight"], "safety"),
    **dict.fromkeys(["sportsbook", "bett", "gambl", "gaming"], "gambl"),
}


def _norm(word: str) -> str:
    s = _stem(word)
    return _SYNONYMS.get(s, s)


def tokens(item: dict) -> set[str]:
    """Distinctive words of the headline plus real lead text (generated drafts are ignored)."""
    return {_norm(w) for w in _TOKEN.findall(_text(item).lower()) if w not in _STOP and len(w) > 2} - _STOP


def _text(item: dict) -> str:
    text = item["title"]
    if item.get("summary") and not brief.is_draft(item["summary"]):
        text += " " + item["summary"][:200]
    return text


# Specifics that separate otherwise similar stories: which state or country, which company.
_US_STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
              "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
              "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri",
              "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York",
              "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island",
              "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
              "West Virginia", "Wisconsin", "Wyoming"]
_GOVERNORS = {"Newsom": "California", "Kotek": "Oregon", "Pritzker": "Illinois", "Spanberger": "Virginia",
              "Hochul": "New York", "DeSantis": "Florida", "Polis": "Colorado", "Abbott": "Texas"}
_STATE_RE = re.compile(r"\b(" + "|".join(_US_STATES) + r")\b")
_GOV_RE = re.compile(r"\b(" + "|".join(_GOVERNORS) + r")\b")


def specifics(item: dict) -> tuple[set[str], set[str]]:
    """(places, companies): US states or countries named, and companies tagged."""
    text = _text(item)
    places = set(_STATE_RE.findall(text)) | {_GOVERNORS[g] for g in _GOV_RE.findall(text)}
    if not places:
        places = set(jurisdictions.detect(item["title"]))
    companies = set(classify.company_tags(item["title"]))
    return places, companies


def _conflict(a: tuple[set[str], set[str]], b: tuple[set[str], set[str]]) -> bool:
    return any(x and y and not (x & y) for x, y in zip(a, b))


def idf_weights(items: list[dict]) -> dict[str, float]:
    df: dict[str, int] = {}
    for it in items:
        for t in tokens(it):
            df[t] = df.get(t, 0) + 1
    n = max(len(items), 1)
    return {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}


def similarity(a: set[str], b: set[str], idf: dict[str, float]) -> float:
    shared = a & b
    if len(shared) < MIN_SHARED:
        return 0.0
    w = lambda s: sum(idf.get(t, 1.0) for t in s)
    return w(shared) / min(w(a), w(b)) if a and b else 0.0


def _days(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def group(items: list[dict], idf: dict[str, float] | None = None) -> list[list[dict]]:
    """Groups of the same event (single-story groups included), lead first, in the input's order."""
    idf = idf if idf is not None else idf_weights(items)
    toks = [tokens(it) for it in items]
    specs = [specifics(it) for it in items]

    # Pair similarities; 0 across tabs, outside the time window, or when specifics conflict.
    # Only stories in the same tab within WINDOW_DAYS of each other are compared (sorted sweep).
    sim: dict[tuple[int, int], float] = {}
    days = [date.fromisoformat(it["date"]).toordinal() for it in items]
    order = sorted(range(len(items)), key=lambda k: (items[k]["category"], days[k]))
    for pos, i in enumerate(order):
        for j in order[pos + 1 :]:
            if items[j]["category"] != items[i]["category"] or days[j] - days[i] > WINDOW_DAYS:
                break
            if _conflict(specs[i], specs[j]):
                continue
            s = similarity(toks[i], toks[j], idf)
            if s > 0:
                sim[min(i, j), max(i, j)] = s

    # Average linkage: repeatedly merge the two groups whose stories are most similar on average, while
    # that average clears THRESHOLD. One look-alike pair can't chain two different events together.
    # nbr[g][h] = summed similarity between groups g and h; merging adds the rows (average linkage).
    groups: dict[int, list[int]] = {i: [i] for i in range(len(items))}
    nbr: dict[int, dict[int, float]] = {}
    for (i, j), s in sim.items():
        nbr.setdefault(i, {})[j] = s
        nbr.setdefault(j, {})[i] = s
    while True:
        best, best_avg = None, THRESHOLD
        for g, row in nbr.items():
            for h, total in row.items():
                if g < h:
                    avg = total / (len(groups[g]) * len(groups[h]))
                    if avg >= best_avg:
                        best, best_avg = (g, h), avg
        if not best:
            break
        g, h = best
        groups[g] += groups.pop(h)
        for k, total in nbr.pop(h).items():
            nbr[k].pop(h, None)
            if k != g:
                nbr[g][k] = nbr[g].get(k, 0.0) + total
                nbr[k][g] = nbr[g][k]

    def lead_key(i):
        s = items[i].get("summary") or ""
        return (brief.is_draft(s) or not s, items[i]["date"], items[i].get("added_at", ""))

    out = []
    for members in sorted(groups.values(), key=min):
        members.sort(key=lead_key)
        out.append([items[i] for i in members])
    return out


FIXTURE = __import__("pathlib").Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "duplicates.json"


def score(items: list[dict] | None = None) -> dict:
    """Pairwise precision / recall of group() against hand-labelled events, plus events shown as one card."""
    import json
    items = json.loads(FIXTURE.read_text(encoding="utf-8")) if items is None else items
    groups = group(items)
    predicted = {}
    for g_id, g in enumerate(groups):
        for it in g:
            predicted[id(it)] = g_id
    tp = fp = fn = 0
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            same = bool(items[i]["event"]) and items[i]["event"] == items[j]["event"]
            said = predicted[id(items[i])] == predicted[id(items[j])]
            tp += same and said
            fp += said and not same
            fn += same and not said
    events = {it["event"] for it in items if it["event"]}
    one_card = sum(1 for e in events if len({predicted[id(it)] for it in items if it["event"] == e}) == 1)
    return {"precision": tp / (tp + fp) if tp + fp else 1.0, "recall": tp / (tp + fn) if tp + fn else 1.0,
            "events_on_one_card": one_card, "events": len(events), "cards": len(groups), "stories": len(items)}


def collapse(items: list[dict]) -> list[dict]:
    """One entry per event: the lead story, with the others under "also" (title, source, url, date).
    Papers are never grouped. Order follows the input."""
    papers = [it for it in items if it["category"] == "research"]
    rest = [it for it in items if it["category"] != "research"]
    lead_of = {}
    for g in group(rest):
        lead = {**g[0], "also": [{k: it.get(k, "") for k in ("title", "source", "url", "date")} for it in g[1:]]}
        for it in g:
            lead_of[id(it)] = lead
    out, seen = [], set()
    for it in items:
        lead = it if it["category"] == "research" else lead_of[id(it)]
        if id(lead) not in seen:
            seen.add(id(lead))
            out.append(lead)
    return out


REGROUP_DAYS = 14  # after each collection, stories from this many recent days are regrouped


def assign(conn, days: int | None = REGROUP_DAYS) -> int:
    """Store each story's card (the lead's id) so the server can page through cards in SQL.
    days=None regroups everything. Papers always stand alone. Returns how many stories changed card."""
    from . import store
    items = store.query(conn, None, None, days, limit=10**7)
    lead_of = {it["id"]: it["id"] for it in items if it["category"] == "research"}
    for g in group([it for it in items if it["category"] != "research"]):
        for it in g:
            lead_of[it["id"]] = g[0]["id"]
    changed = store.set_clusters(conn, lead_of)
    conn.commit()
    from .bills import attach_news  # news naming a tracked bill joins the bill's card
    return changed + attach_news(conn)
