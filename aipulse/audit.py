"""Legality audit: every source checked again against the standard in terms.py.

    python -m aipulse audit        # on a PC, monthly and before adding a source (not on GitHub Actions)

For each site: does robots.txt still allow each source, does the source still answer, and what does its terms page
say now. Sentences about robots, scraping, automated access or personal use are kept in data/terms-audit.json; the
report lists every site whose sentences changed since the last audit, every source without evidence in terms.py and
every "unconfirmed" one, so nothing is called legal on an old reading.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from . import feeds
from .sources import SOURCES
from .terms import PLATFORM, TERMS

SAVED = Path(__file__).resolve().parent.parent / "data" / "terms-audit.json"
RED_FLAGS = re.compile(r"\brobots?\b|spider|scrap|crawl|automat\w* (?:means|process|system|device|access|tool)|"
                       r"data[- ]mining|text and data mining|harvest|personal(?:,)? (?:and )?non-?commercial|"
                       r"personal use|\bRSS\b|republish|redistribut", re.I)


def page_text(body: bytes) -> str:
    text = body.decode("utf-8", "replace")
    text = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", text))).strip()


def flagged(text: str) -> list[str]:
    """The terms' sentences a person has to read: about robots, scraping, automated access, feeds or personal use."""
    return sorted({s.strip()[:400] for s in re.split(r"(?<=[.;:])\s+", text) if 30 < len(s) and RED_FLAGS.search(s)})


def run(fetcher=feeds.fetch, log=print, saved: Path = SAVED) -> list[str]:
    """Audit every source; returns the problems found (also printed) and saves what each terms page says now."""
    before = json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else {}
    hosts: dict[str, list[dict]] = {}
    for s in SOURCES:
        hosts.setdefault(urlsplit(s["url"]).netloc.lower(), []).append(s)
    problems, now = [], {}
    for host, srcs in sorted(hosts.items()):
        names = ", ".join(s["name"] for s in srcs)
        if host not in TERMS:
            problems.append(f"{names}: no evidence in terms.py")
            continue
        kind, terms_url, _ = TERMS[host]
        if kind == "unconfirmed":
            problems.append(f"{names}: unconfirmed, read {terms_url} in a browser")
        for s in srcs:
            try:
                fetcher(s["url"])
            except feeds.Disallowed:
                problems.append(f"{s['name']}: robots.txt no longer allows {s['url']}")
            except Exception as e:  # a 401/403 is a block: the source has to go (collect.DROPPED)
                problems.append(f"{s['name']}: {s['url']} answered {getattr(e, 'code', type(e).__name__)}")
        if not terms_url or kind == "unconfirmed":
            continue
        try:
            sentences = flagged(page_text(fetcher(terms_url)))
        except Exception as e:  # a page closed to robots (MarkTechPost's) is read by a person each audit instead
            problems.append(f"{names}: terms page {terms_url} closed to our reader "
                            f"({getattr(e, 'code', type(e).__name__)}): read it in a browser")
            continue
        digest = hashlib.sha256("\n".join(sentences).encode()).hexdigest()[:16]
        now[host] = {"terms": terms_url, "checked": date.today().isoformat(), "hash": digest, "sentences": sentences}
        old = before.get(host)
        if old and old.get("hash") != digest:
            new = [x for x in sentences if x not in old.get("sentences", [])]
            problems.append(f"{names}: terms changed since {old['checked']}; read {terms_url}"
                            + "".join(f"\n      new: {x}" for x in new[:5]))
    for host, (kind, terms_url, _) in sorted(PLATFORM.items()):  # official records, icons, photos, data
        if not terms_url:
            continue
        try:
            sentences = flagged(page_text(fetcher(terms_url)))
        except Exception as e:
            problems.append(f"{host}: terms page {terms_url} unreadable ({getattr(e, 'code', type(e).__name__)})")
            continue
        digest = hashlib.sha256("\n".join(sentences).encode()).hexdigest()[:16]
        old = before.get(host)
        now[host] = {"terms": terms_url, "checked": date.today().isoformat(), "hash": digest, "sentences": sentences}
        if old and old.get("hash") != digest:
            problems.append(f"{host}: terms changed since {old['checked']}; read {terms_url}")
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_text(json.dumps({**before, **now}, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in problems:
        log(f"  {p}")
    log(f"{len(hosts)} sites audited, {len(problems)} to look at")
    return problems
