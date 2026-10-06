"""The glossary as pages, like a dictionary: glossary/ lists every word A to Z, and glossary/<word>/ has its meaning
(other glossary words in it linked), its related terms and a link to the stories that mention it. The meanings are
our own writing, the part of AI Pulse search engines can rank; the site's Glossary panel stays as it is.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, timedelta
from html import escape
from pathlib import Path
from urllib.parse import quote

from . import glossary, pages, rss

RELATED = 6  # related terms per word: those its meaning names, those whose meanings name it, then its group's
CLOUD = 30  # words in glossary/'s "In the news this week" cloud
TOGETHER_DAYS, TOGETHER = 30, 8  # a word's page: the words most often in the same stories, over these days
# a word's colour in a cloud, by its group: Okabe-Ito blue, vermillion, bluish green, and ink (colour-blind safe)
CLOUD_COLOURS = ["#0072B2", "#D55E00", "#007A5A", "#000"]


def _first_sentence(text: str) -> str:
    m = re.match(r"(.+?[.!?])(?=\s+[A-Z\"(]|$)", text)  # not at "e.g. the UK"
    return m.group(1) if m else text


def _links(entry: dict) -> tuple[str, list[str]]:
    """The meaning as HTML, the first mention of each other glossary word linked to its page, and those words' ids."""
    text, spans = entry["def"], []
    for e in glossary.ENTRIES:
        if e["id"] == entry["id"]:
            continue
        found = list(glossary._PATTERNS[e["id"]].finditer(text))  # a word ("parameters") over shorthand ("35B")
        m = next((m for m in found if re.search(r"[A-Za-z]{3}", m.group())), found[0] if found else None)
        if m and not any(m.start() < b and a < m.end() for a, b, _ in spans):
            spans.append((m.start(), m.end(), e["id"]))
    spans.sort()
    out, at = [], 0
    for a, b, key in spans:
        out += [escape(text[at:a], quote=False), f'<a href="/glossary/{key}/">{escape(text[a:b], quote=False)}</a>']
        at = b
    return "".join(out) + escape(text[at:], quote=False), [key for _, _, key in spans]


def related(entry: dict, named: list[str]) -> list[dict]:
    by_id = {e["id"]: e for e in glossary.ENTRIES}
    naming = [e["id"] for e in glossary.ENTRIES if e["id"] != entry["id"] and glossary.mentions(entry["id"], e["def"])]
    group = [e["id"] for e in glossary.ENTRIES if e["group"] == entry["group"] and e["id"] != entry["id"]]
    ids = list(dict.fromkeys(named + naming + group))
    return [by_id[i] for i in ids[:RELATED]]


def cloud(counts: list[tuple[dict, int]], label: str) -> str:
    """Words sized by how many stories use them (the busiest biggest), A to Z, each linking to its page."""
    if not counts:
        return ""
    top = max(n for _, n in counts)
    words = []
    for e, n in sorted(counts, key=lambda x: x[0]["term"].lower()):
        size = 14 + round(14 * (math.log(n) / math.log(top) if top > 1 else 1))
        colour = CLOUD_COLOURS[glossary.GROUPS.index(e["group"]) % len(CLOUD_COLOURS)]
        words.append(f'<a href="/glossary/{e["id"]}/" style="font-size:{size}px;color:{colour}"'
                     f'{" class=big" if size >= 23 else ""} title="{n} {"story" if n == 1 else "stories"}">'
                     f'{escape(e["term"])}</a>')
    return f'<div class="cloud" aria-label="{escape(label)}">' + "\n".join(words) + "</div>"


def _row(e: dict) -> str:
    return (f'<li><div><a href="/glossary/{e["id"]}/">{escape(e["term"])}</a><span class="grp">{escape(e["group"])}</span></div>'
            f'<div class="short">{escape(_first_sentence(e["def"]))}</div></li>')


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write glossary/ and a page per word. Returns their paths."""
    parts = pages.frame(conn, len(cards))
    pages.write_css(out)
    # each recent story's glossary words: this week's counts (the cloud) and which words share stories
    week, since = (today - timedelta(days=7)).isoformat(), (today - timedelta(days=TOGETHER_DAYS)).isoformat()
    recent, together = Counter(), {e["id"]: Counter() for e in glossary.ENTRIES}
    for c in cards:
        if (c.get("date") or "") < since:
            continue
        ids = glossary.terms_in(f"{c.get('title') or ''} {c.get('summary') or ''}")
        if c["date"] >= week:
            recent.update(ids)
        for i in ids:
            together[i].update(j for j in ids if j != i)
    by_id = {e["id"]: e for e in glossary.ENTRIES}
    words = sorted(glossary.ENTRIES, key=lambda e: e["term"].lower())
    home = f"{rss.SITE}glossary/"
    note = 'Plain-English meanings, written by hand. The Glossary button on every page of the site opens them too.'
    paths = []
    for e in words:
        path = f"glossary/{e['id']}/"
        meaning, named = _links(e)
        n = recent[e["id"]]
        seen = (f"Mentioned in {n} {'story' if n == 1 else 'stories'} in the last 7 days." if n
                else "Not in the last 7 days' stories.")
        body = (f'<span class="kind">AI glossary · {escape(e["group"])}</span>\n<h1>{escape(e["term"])}</h1>\n'
                f'<p class="def">{meaning}</p>\n<p class="intro">{seen}</p>\n'
                f'<a class="search" href="/all/?q={quote(e["search"])}">See stories that mention it →</a>\n'
                + (f'<h2>Often in the same stories</h2>\n<p class="intro">The words that came up with {escape(e["term"])} '
                   f'in the last {TOGETHER_DAYS} days\' stories; the bigger, the more often.</p>\n'
                   + cloud([(by_id[i], k) for i, k in together[e["id"]].most_common(TOGETHER)], "Often in the same stories")
                   if together[e["id"]] else "")
                + f'<h2>Related terms</h2>\n<ul class="terms">\n' + "\n".join(_row(r) for r in related(e, named)) + "\n</ul>")
        data = {"@context": "https://schema.org", "@type": "DefinedTerm", "name": e["term"], "description": e["def"],
                "url": f"{rss.SITE}{path}", "inDefinedTermSet": home}
        (out / path).mkdir(parents=True, exist_ok=True)
        (out / path / "index.html").write_text(pages.page(
            f"{e['term']}: what it means in AI · AI Pulse glossary", f"{e['term']}: {_first_sentence(e['def'])}"[:300],
            path, body, data, parts, ("/glossary/", "Back to the AI glossary (all words)"), note), encoding="utf-8")
        paths.append(path)
    letters: dict[str, list[dict]] = {}
    for e in words:
        letters.setdefault(e["term"][0].upper() if e["term"][0].isalpha() else "#", []).append(e)
    jump = "".join(f'<a href="/glossary/#{"num" if k == "#" else k}">{k}</a>' for k in letters)
    sections = "\n".join(f'<h2 id="{"num" if k == "#" else k}">{k}</h2>\n<ul class="terms">\n' + "\n".join(_row(e) for e in es)
                         + "\n</ul>" for k, es in letters.items())
    body = (f'<h1>AI glossary</h1>\n<p class="intro">The hard words in AI news, in plain English: {len(words)} words, '
            f'A to Z. Updated {today.day} {today:%b %Y}.</p>\n'
            + (f'<h2>In the news this week</h2>\n<p class="intro">The glossary words in the last 7 days\' stories; '
               f'the bigger the word, the more stories used it.</p>\n'
               + cloud([(by_id[i], n) for i, n in recent.most_common(CLOUD)], "In the news this week") if recent else "")
            + f'<h2>A to Z</h2>\n<nav class="letters" aria-label="Jump to a letter">{jump}</nav>\n' + sections)
    data = {"@context": "https://schema.org", "@type": "DefinedTermSet", "name": "AI Pulse glossary", "url": home,
            "hasDefinedTerm": [{"@type": "DefinedTerm", "name": e["term"], "url": f"{rss.SITE}glossary/{e['id']}/"}
                               for e in words]}
    (out / "glossary").mkdir(parents=True, exist_ok=True)
    (out / "glossary" / "index.html").write_text(pages.page(
        "AI glossary: the hard words in AI news, in plain English · AI Pulse",
        f"{len(words)} AI words explained in plain English, from LLM and tokens to compute, agents and AI law. Written by hand.",
        "glossary/", body, data, parts, ("/", "Back to AI Pulse"), note), encoding="utf-8")
    return ["glossary/", *paths]
