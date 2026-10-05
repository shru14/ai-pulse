"""Hybrid search over stored stories, for the weekly briefing: by meaning and by words, returned as cards.

Three signals, for every story in the date range:
- meaning: each story's vector (embed.py) against the question's, by cosine similarity. Every story here is
  about AI, so all the vectors share one large direction that says little about any single story; it is
  taken out first (the average vector is subtracted), so stories compare on what sets them apart. The search
  is exact (every vector in the date range is compared): at tens of thousands of stories that takes
  milliseconds, so no approximate index is needed;
- words: every word of the question in the story (SQLite's full-text index, items_fts), so exact names
  ("S. 5518", "HBM4") count;
- the site's own tags: a story its rules tagged with what the question names ("Healthcare", "Nvidia").
A question that names a place ("AI in the USA") keeps only stories tagged with that place, not far off in meaning.
A card (one event, all its outlets) ranks by its closest outlet's similarity, plus BONUS for each of the other
two signals and a little for each other outlet that reported it: meaning leads, the others settle close
calls. A card is only kept if it is close enough in
meaning (MIN_SIMILARITY), has
every word of a longer question, or has the question's word or tag and is not far off in meaning; on a question
the site's tags cover, a story of few words needs one of those or to be clearly closer. So a quiet week returns little rather than filler.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date

from . import embed, store

CANDIDATES = 200      # stories Index.nearest returns unless asked for more
BONUS = 0.05          # added to a card's similarity for its tag, and for every word of the question
OUTLET_BONUS, OUTLETS = 0.01, 5  # and for each other outlet that reported it (up to OUTLETS): how much it mattered
MIN_SIMILARITY = 0.25  # (with the shared direction out) below this a story is about something else
WORDS_FLOOR = 0.15     # a story with the word or tag of a one-word question still needs to be this close in meaning
SHORT, SHORT_EXTRA = 20, 0.10  # a story of fewer words (headline and description) says little: on a question the
                               # site's tags cover, one without the tag or every word needs to be this much closer
# A stream's name counts as a tag of its stories ("AI regulation": the tracker's bills, laws and bodies)
STREAM_WORDS = {"tool": "Releases", "news": "Industry", "research": "Research", "regulation": "Regulation",
                "policy": "Policy", "infra": "Infra climate"}

_STOP = set("""a an and are as at be by for from has have how in into is it its of on or that the this to was were
what when where which who why will with about after over under than then there their they them we our you your
new news latest week ai artificial intelligence
i i'm im me my we us want wants know like interested follow following track anything everything something any all
more most also just really things stuff much many lot would could should do does did doing can get see keep tell
please happening update updates being""".split())  # also the filler of a request in a reader's own words


def parts(query: str) -> list[str]:
    """A reader's request split into its sentences and its "…, and what/how…" clauses: two subjects in one request
    pull its single vector between them, so each part is searched too (see search)."""
    split = re.split(r"(?<=[a-z]{2})\.+(?=\s|$)|[?!;\n]+|,?\s+and\s+(?=(?:what|how|whether|who|which|why|where|when)\b)", query or "", flags=re.I)
    return [p.strip(" ,") for p in split if words(p)]


def shared(conn):
    """The average of all stored vectors: the direction every AI story shares."""
    import numpy as np
    embed.connect(conn)
    total, n = np.zeros(embed.DIM, dtype=np.float64), 0
    for (vec,) in conn.execute("SELECT vec FROM vectors WHERE model = ?", (embed.MODEL,)):
        total += np.frombuffer(vec, dtype=np.float16)
        n += 1
    return (total / max(n, 1)).astype(np.float32)


def _apart(m, mean):
    """Vectors with the shared direction taken out, at length 1 again."""
    import numpy as np
    m = m - mean
    return m / np.maximum(np.linalg.norm(m, axis=-1, keepdims=True), 1e-9)


class Index:
    """The vectors of the stories dated from `since` (inclusive) to `until` (exclusive), in memory, with the
    shared direction (`mean`, else worked out from every stored vector) taken out."""

    def __init__(self, conn, since: date, until: date, mean=None):
        import numpy as np
        embed.connect(conn)
        self.mean = shared(conn) if mean is None else mean
        rows = conn.execute("SELECT v.id, i.cluster, v.vec FROM vectors v JOIN items i ON i.id = v.id "
                            "WHERE v.model = ? AND i.date >= ? AND i.date < ?",
                            (embed.MODEL, since.isoformat(), until.isoformat())).fetchall()
        self.since, self.until = since, until
        self.ids = [r[0] for r in rows]
        self.cluster = {r[0]: r[1] or r[0] for r in rows}
        self.row = {r[0]: k for k, r in enumerate(rows)}
        self.matrix = (_apart(np.frombuffer(b"".join(r[2] for r in rows), dtype=np.float16)
                              .reshape(len(rows), embed.DIM).astype(np.float32), self.mean)
                       if rows else np.zeros((0, embed.DIM), np.float32))

    def __len__(self) -> int:
        return len(self.ids)

    def vector(self, story_id: str):
        """A story's vector as the index holds it, or None."""
        k = self.row.get(story_id)
        return None if k is None else self.matrix[k]

    def query(self, text: str):
        """A question's vector, comparable with the index's."""
        return _apart(embed.encode([text], query=True)[0], self.mean)

    def nearest(self, vector, k: int = CANDIDATES) -> list[tuple[str, float]]:
        """(story id, cosine), closest first; `vector` as from vector() or query()."""
        import numpy as np
        if not self.ids:
            return []
        scores = self.matrix @ vector
        top = np.argsort(-scores)[:k]
        return [(self.ids[j], float(scores[j])) for j in top]


def words(query: str) -> list[str]:
    return [w for w in re.findall(r"[^\W_][\w'.\-]*[^\W_]|[^\W_]", (query or "").lower()) if w not in _STOP]


def keyword(conn, query: str, since: date, until: date, k: int = CANDIDATES) -> list[tuple[str, str, bool]]:
    """(story id, card id, has every word), best BM25 first: stories with any of the question's words (as prefixes)."""
    ws = words(query)
    if not ws:
        return []
    match = " OR ".join('"' + w.replace('"', "") + '"*' for w in ws)
    rows = conn.execute("SELECT i.id, i.cluster, i.title, i.summary FROM items_fts JOIN items i ON i.rowid = items_fts.rowid "
                        "WHERE items_fts MATCH ? AND i.date >= ? AND i.date < ? ORDER BY bm25(items_fts) LIMIT ?",
                        (match, since.isoformat(), until.isoformat(), k)).fetchall()
    out = []
    for i, c, title, summary in rows:
        text = f" {title} {summary} ".lower()
        out.append((i, c or i, all(re.search(r"(?<!\w)" + re.escape(w), text) for w in ws)))
    return out


def places(query: str) -> dict[str, str]:
    """The places a question names, as {code: name}, found the way the site tags stories with places
    (jurisdictions.py: "USA", "U.S.", "America", "the White House" are the United States; "UK", "Britain" the
    United Kingdom), in any capitals; "us" the pronoun is not the country."""
    from .jurisdictions import JURISDICTIONS
    found = {}
    for code, (name, patterns, *_) in JURISDICTIONS.items():
        for pattern in patterns:
            if any(m.group(0).lower() != "us" for m in re.finditer(pattern, query or "", re.I)):
                found[code] = name
                break
    return found


def stem(word: str) -> str:
    """A rough stem, so a question's word meets a tag in another form: "regulate" and "Regulation", "governments"
    and "Governance", "chips" and "Chips" (the first five letters of a longer word; else without a final s)."""
    return word[:5] if len(word) > 5 else word.rstrip("s") or word


def tagged(conn, query: str, since: date, until: date) -> set[str]:
    """Cards the site's own rules tagged with a tag the question names ("AI in healthcare": Healthcare;
    "Nvidia": Nvidia), from any of their outlets, or in a stream the question names (STREAM_WORDS)."""
    asked = {stem(w) for w in words(query)}
    names = {t for (tags,) in conn.execute("SELECT DISTINCT tags FROM items WHERE date >= ? AND date < ?",
                                           (since.isoformat(), until.isoformat())) for t in tags.split(",") if t}
    named = {t for t in names if (w := {stem(x) for x in words(t)}) and w <= asked}
    streams = {k for k, name in STREAM_WORDS.items() if {stem(x) for x in words(name)} & asked}
    if not named and not streams:
        return set()
    out = set()
    for cluster, tags, category in conn.execute("SELECT cluster, tags, category FROM items WHERE date >= ? AND date < ?",
                                                (since.isoformat(), until.isoformat())):
        if set(tags.split(",")) & named or category in streams:
            out.add(cluster)
    return out


def search(conn, query: str, since: date, until: date, k: int = 10, index: Index | None = None,
           category: str | None = None) -> list[dict]:
    """The `k` cards that best answer `query` among stories dated since..until, best first. Each card carries
    `similarity` (its closest outlet's cosine to the question) and `score` (that, plus the bonuses)."""
    index = index or Index(conn, since, until)
    def closeness(text: str) -> dict[str, float]:  # every card in the range: its closest outlet's cosine
        out: dict[str, float] = {}
        for i, s in index.nearest(index.query(text), len(index)):
            c = index.cluster[i]
            out[c] = max(out.get(c, -1.0), s)
        return out
    sim = closeness(query)
    pieces = parts(query)
    if len(pieces) > 1:  # a request of several parts: halfway between the whole and its closest part
        each = [closeness(piece) for piece in pieces]
        sim = {c: (s + max(e.get(c, -1.0) for e in each)) / 2 for c, s in sim.items()}
    whole = {c for _, c, every in keyword(conn, query, since, until, k=len(index) or 1) if every}
    tags = tagged(conn, query, since, until)
    several = len(words(query)) > 1  # every word of a longer question is telling; of a one-word one, less so
    outlets = Counter(index.cluster.values())  # the card's stories in the range: one per outlet
    score = {c: sim.get(c, 0.0) + BONUS * ((c in tags) + (c in whole)) + OUTLET_BONUS * min(outlets[c] - 1, OUTLETS)
             for c in set(sim) | whole | tags}
    keep = [c for c in score
            if sim.get(c, 0) >= MIN_SIMILARITY                               # close in meaning
            or (c in whole and several)                                      # every word of a longer question
            or ((c in whole or c in tags) and sim.get(c, 0) >= WORDS_FLOOR)]  # its word or tag, and not far off
    keep.sort(key=lambda c: score[c], reverse=True)
    backed = tags | (whole if several else set())  # found by the site's tags or by every word of a longer question
    named = places(query)  # a question about a place: only stories the site tagged with it ("AI in the USA")
    def in_place(c: dict) -> bool:  # its places as the site shows them: its tags and record, and what its text names now
        from .jurisdictions import detect
        found = set(c.get("jurisdictions") or []) | set(detect(c.get("title") or "", c.get("summary") or "", limit=99))
        return bool(set(named) & found or set(named.values()) & set(c.get("tags") or []))
    if named:  # the place is the filter, so a story about it needs only to be not far off in meaning
        keep = sorted((c for c in score if sim.get(c, 0) >= WORDS_FLOOR),
                      key=lambda c: score[c], reverse=True)
    cards = [c for c in store.cards_by_id(conn, keep[:k * 4] if not named else keep) if not category or c["category"] == category
             if not named or in_place(c)
             if c["id"] in backed or not tags or sim.get(c["id"], 0) >= MIN_SIMILARITY + SHORT_EXTRA
             or len(words(f"{c['title']} {c.get('summary') or ''}")) >= SHORT][:k]
    for c in cards:
        c["similarity"], c["score"] = round(sim.get(c["id"], 0.0), 4), round(score[c["id"]], 4)
    return cards
