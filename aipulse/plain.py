"""Each paper in one plain English sentence, for readers who aren't AI researchers.

A paper's description on its card is the start of its abstract, written for other researchers. Under its title the
card also says what the paper does or finds in everyday words. The sentence is written by the same open-source
model as the monthly issue's summary (monthly.py: Qwen3-4B-Instruct-2507, Apache 2.0, run on this machine or the
GitHub runner with llama.cpp; no API is called and nothing is billed), from the paper's title and abstract only.

It is checked before it is kept: one sentence of at most MAX_WORDS words; every name and number in it must be in
the title or abstract (monthly.unsupported); and no acronym but "AI" (an acronym is the jargon the sentence is
there to avoid). A sentence that fails is written again, told what was wrong; after TRIES the paper has no plain
sentence and its card shows the description alone. Each sentence is written once and kept (table `plain`). Only
papers from the last DAYS days get one (the owner's choice, 13 Oct 2026: no older papers), newest first, for at most
MINUTES a run.

It's optional: without llama-cpp-python or the model, cards show the description alone, as before.
"""
from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timezone

from . import monthly

SCHEMA = """
CREATE TABLE IF NOT EXISTS plain (
    id       TEXT PRIMARY KEY,  -- the paper's id (items.id)
    sentence TEXT NOT NULL,     -- '' when every try failed the check: not tried again
    model    TEXT NOT NULL,
    made_at  TEXT NOT NULL
);
"""

PROMPT = ("Here is an AI research paper's title and abstract. In ONE plain English sentence of at most 25 words, say "
          "what the paper does or finds, for a reader who is not an AI researcher. No jargon and no acronyms: say any "
          "technical idea in everyday words. Use only what the abstract states: no names, numbers or claims that are "
          "not in it. Start with a verb such as \"Shows\", \"Finds\", \"Builds\" or \"Tests\".\n\n"
          "Title: {title}\nAbstract: {abstract}")
VERBS = set("""shows finds builds tests proposes introduces presents makes measures teaches trains studies compares
offers gives creates designs releases develops improves argues explores suggests uses lets helps turns checks
describes surveys reviews explains maps tracks""".split())
MAX_WORDS = 30
TRIES = 3
DAYS = 7  # papers this recent; older ones keep the description alone
MINUTES = 8  # a run's share, newest papers first (a full run already takes ~25 of its 45)
_ACRONYM = re.compile(r"\b(?!AI\b)[A-Z][A-Za-z]*[A-Z][A-Za-z]*s?\b")  # "LLM", "RLHF", "VLMs", "GPT", "LoRA"


def connect(conn) -> None:
    conn.executescript(SCHEMA)


def problems(text: str, title: str, abstract: str) -> list[str]:
    """What is wrong with a plain sentence (nothing: it can be kept)."""
    out = []
    if len(re.findall(r"[.!?](?:\s|$)", text)) > 1 or len(text.split()) > MAX_WORDS:
        out.append("length")
    if not text or text.split()[0].lower() not in VERBS:
        out.append("start")
    out += _ACRONYM.findall(text)
    rest = text[:1].lower() + text[1:]  # its opening verb is no name
    out += [w for w in monthly.unsupported(rest, f"{title} {abstract}") if not _ACRONYM.fullmatch(w)]
    return list(dict.fromkeys(out))


def write(title: str, abstract: str, generate=None) -> str | None:
    """The paper in one plain sentence, checked; None when the model is missing or every try failed.
    `generate(prompt, seed)` returns the model's text (tests pass their own)."""
    if generate is None:
        llm = monthly._model()
        if llm is None:
            return None
        def generate(p, seed):
            out = llm.create_chat_completion(messages=[{"role": "user", "content": p}], temperature=0.2,
                                             max_tokens=80, seed=seed)
            return out["choices"][0]["message"]["content"]
    told: list[str] = []
    for seed in range(1, TRIES + 1):
        text = monthly.clean(generate(PROMPT.format(title=title, abstract=abstract) + "".join(told), seed)).strip('"')
        bad = problems(text, title, abstract)
        if not bad:
            return text
        named = [b for b in bad if b not in ("length", "start")]
        told.append("".join([
            "\n\nOne sentence, at most 25 words." if "length" in bad else "",
            "\n\nStart with a verb such as \"Shows\" or \"Builds\"." if "start" in bad else "",
            f"\n\nDo not write {', '.join(named)}: say it in everyday words, or leave it out." if named else ""]))
    return None


def due(conn, limit: int | None = None) -> list[tuple[str, str, str]]:
    """The last DAYS days' papers without a plain sentence yet (id, title, abstract), newest first."""
    rows = conn.execute("SELECT i.id, i.title, i.summary FROM items i LEFT JOIN plain p ON p.id = i.id "
                        "WHERE i.category = 'research' AND p.id IS NULL AND i.summary != '' AND i.date >= date('now', ?) "
                        "ORDER BY i.date DESC, i.added_at DESC" + (" LIMIT ?" if limit else ""),
                        (f"-{DAYS} days", *([limit] if limit else []))).fetchall()
    return [tuple(r) for r in rows]


def update(conn, minutes: float = MINUTES, limit: int | None = None, log=print) -> int:
    """Write the sentences still due, newest papers first, for at most `minutes`. Returns how many were kept."""
    connect(conn)
    end, kept, tried = time.monotonic() + minutes * 60, 0, 0
    for pid, title, abstract in due(conn, limit):
        if time.monotonic() > end:
            break
        text = write(title, abstract)
        if text is None and monthly._model() is None:
            log("plain: no model (pip install llama-cpp-python); skipped")
            return kept
        conn.execute("INSERT OR REPLACE INTO plain VALUES (?, ?, ?, ?)",
                     (pid, text or "", monthly.MODEL, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        conn.commit()
        kept += bool(text)
        tried += 1
    left = len(due(conn))
    log(f"plain: {kept} of {tried} papers given a plain sentence; {left} still to do")
    return kept


def sentences(conn, ids: list[str]) -> dict[str, str]:
    """The plain sentence of each of these papers that has one."""
    try:
        out = {}
        for i in range(0, len(ids), 900):
            batch = ids[i:i + 900]
            out.update(conn.execute(f"SELECT id, sentence FROM plain WHERE sentence != '' AND id IN "
                                    f"({','.join('?' * len(batch))})", batch).fetchall())
        return out
    except sqlite3.OperationalError:  # no table yet: nothing written
        return {}
