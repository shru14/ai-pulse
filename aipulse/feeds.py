"""Fetch and parse RSS 2.0 / Atom feeds with the standard library only."""

from __future__ import annotations

import gzip
import html
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

USER_AGENT = "AIPulse/1.0 (+https://github.com/; personal news reader)"
ATOM = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
GZIP_MAGIC = bytes([0x1F, 0x8B])

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


# Rate limits and temporary server errors are retried; anything else (404, 403, bad XML) fails at once.
RETRY_STATUS = {429, 500, 502, 503, 504}
ATTEMPTS = 3
BACKOFF = 2.0  # seconds before the 2nd attempt; each later wait is 3x longer (2s, 6s)
MAX_WAIT = 60.0


def _retry_after(err: urllib.error.HTTPError) -> float | None:
    value = err.headers.get("Retry-After") if err.headers else None
    try:
        return float(value) if value else None
    except ValueError:
        return None  # an HTTP date; fall back to our own backoff


def fetch(url: str, timeout: int = 20, attempts: int = ATTEMPTS) -> bytes:
    """GET a URL, retrying rate limits (429), 5xx errors and network timeouts with backoff."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
            # Some hosts (e.g. deepmind.google) send gzip even when it wasn't requested.
            return gzip.decompress(body) if body.startswith(GZIP_MAGIC) else body
        except urllib.error.HTTPError as err:
            if err.code not in RETRY_STATUS or attempt == attempts - 1:
                raise
            wait = _retry_after(err) or BACKOFF * 3 ** attempt
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == attempts - 1:
                raise
            wait = BACKOFF * 3 ** attempt
        time.sleep(min(wait, MAX_WAIT))
    raise AssertionError("unreachable")


def clean_text(raw: str | None, limit: int = 400) -> str:
    """Strip HTML, unescape entities, collapse whitespace, trim to a sentence."""
    if not raw:
        return ""
    text = html.unescape(_TAG_RE.sub(" ", raw))
    text = _WS_RE.sub(" ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: end + 1] if end > limit * 0.5 else cut.rsplit(" ", 1)[0] + "…").strip()


def parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)  # RFC 822 (RSS)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))  # ISO 8601 (Atom)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def parse(xml_bytes: bytes) -> list[dict]:
    """Return entries as dicts: title, url, summary, published (datetime|None), authors (list)."""
    root = ET.fromstring(xml_bytes)
    entries: list[dict] = []

    if root.tag == f"{ATOM}feed":
        for e in root.findall(f"{ATOM}entry"):
            link = ""
            for l in e.findall(f"{ATOM}link"):
                if l.get("rel", "alternate") == "alternate":
                    link = l.get("href", "")
                    break
            summary = _text(e.find(f"{ATOM}summary")) or _text(e.find(f"{ATOM}content"))
            published = _text(e.find(f"{ATOM}published")) or _text(e.find(f"{ATOM}updated"))
            entries.append({
                "title": clean_text(_text(e.find(f"{ATOM}title")), 200),
                "url": link,
                "summary": clean_text(summary),
                "published": parse_date(published),
                "authors": [n for a in e.findall(f"{ATOM}author") if (n := clean_text(_text(a.find(f"{ATOM}name")), 80))],
            })
        return entries

    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else root.findall(".//item")
    for it in items:
        summary = _text(it.find("description")) or _text(it.find(f"{CONTENT}encoded"))
        published = _text(it.find("pubDate")) or _text(it.find(f"{DC}date"))
        entries.append({
            "title": clean_text(_text(it.find("title")), 200),
            "url": _text(it.find("link")) or _text(it.find("guid")),
            "summary": clean_text(summary),
            "published": parse_date(published),
            "authors": [n for a in it.findall(f"{DC}creator") if (n := clean_text(_text(a), 80))],
        })
    return entries


def parse_hf_daily(json_bytes: bytes) -> list[dict]:
    """Hugging Face Daily Papers API: entries like parse(), plus the organizations that claimed each paper."""
    entries = []
    for p in json.loads(json_bytes):
        paper = p.get("paper") or {}
        orgs = [o for o in (p.get("organization"), paper.get("organization")) if isinstance(o, dict)]
        arxiv_id = paper.get("id", "")
        entries.append({
            "title": clean_text(paper.get("title") or p.get("title"), 200),
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else "",
            "summary": clean_text(paper.get("summary") or p.get("summary")),
            "published": parse_date(paper.get("publishedAt") or p.get("publishedAt")),
            "authors": [n for a in paper.get("authors", []) if (n := clean_text(a.get("name"), 80))],
            "orgs": list(dict.fromkeys(v for o in orgs for v in (o.get("fullname"), o.get("name")) if v)),
        })
    return entries


ARXIV = "{http://arxiv.org/schemas/atom}"
_ARXIV_PREFIX = re.compile(r"^arXiv:\S+\s+Announce Type:\s*\S+\s*(Abstract:\s*)?", re.I)


def parse_arxiv_rss(xml_bytes: bytes) -> list[dict]:
    """rss.arxiv.org: each day's new papers in some categories. Its author field is one comma-separated
    string, and the abstract starts with "arXiv:<id> Announce Type: new Abstract:". Revised versions of
    older papers ("replace") are left out; new papers and cross-lists are kept."""
    entries = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        if (_text(it.find(f"{ARXIV}announce_type")) or "new").startswith("replace"):
            continue
        authors = re.split(r",\s*|\s+and\s+", html.unescape(_text(it.find(f"{DC}creator")) or ""))
        entries.append({
            "title": clean_text(_text(it.find("title")), 200),
            "url": _text(it.find("link")),
            "summary": clean_text(_ARXIV_PREFIX.sub("", html.unescape(_text(it.find("description")) or "").strip())),
            "published": parse_date(_text(it.find("pubDate"))),
            "authors": [n for a in authors if (n := clean_text(a, 80))],
        })
    return entries


PARSERS = {"feed": parse, "hf_daily": parse_hf_daily, "arxiv_rss": parse_arxiv_rss}
