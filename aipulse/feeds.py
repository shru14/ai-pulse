"""Fetch and parse RSS 2.0 / Atom feeds with the standard library only."""

from __future__ import annotations

import gzip
import html
import json
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit

USER_AGENT = "AIPulse/1.0 (+https://github.com/shru14/ai-pulse; personal news reader)"
ROBOT_NAME = "AIPulse"  # the name robots.txt rules are matched against
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


# ---------- Only what a site allows ----------
# Every request first checks the site's robots.txt, and a URL it disallows is never fetched. The only
# exceptions are official APIs whose published terms allow programmatic use, although their robots.txt
# (written for search crawlers) disallows everything:
#   export.arxiv.org  arXiv's API: https://info.arxiv.org/help/api/tou.html (metadata CC0; at most one
#                     request every 3 seconds, which the arXiv sources' "pause" keeps)
#   www.wikidata.org  Wikidata's API: https://www.mediawiki.org/wiki/API:Etiquette (serial requests with
#                     a descriptive User-Agent)
# and official services with no robots.txt of their own (the request for one is refused):
#   api.congress.gov  the Library of Congress's API (https://api.congress.gov; US government works)
#   cdn.jsdelivr.net  the npm package CDN serving Simple Icons (CC0; https://www.jsdelivr.com/terms)
API_HOSTS = {"export.arxiv.org", "www.wikidata.org", "api.congress.gov", "cdn.jsdelivr.net"}


class Disallowed(Exception):
    """The site's robots.txt doesn't allow fetching this URL."""


_robots: dict[str, urllib.robotparser.RobotFileParser] = {}
_robots_lock = threading.Lock()


def _rules(scheme: str, host: str) -> urllib.robotparser.RobotFileParser:
    rules = urllib.robotparser.RobotFileParser()
    req = urllib.request.Request(f"{scheme}://{host}/robots.txt", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20, context=TLS) as resp:
            body = resp.read()
        body = gzip.decompress(body) if body.startswith(GZIP_MAGIC) else body
        rules.parse(body.decode("utf-8", "replace").splitlines())
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):  # no robots.txt: no rules
            rules.parse([])
        else:  # 401/403 mean "keep out"; 5xx: can't tell, so don't fetch this time
            rules.parse(["User-agent: *", "Disallow: /"])
            if e.code >= 500:
                return rules  # not remembered: asked again on the next run
    _robots[host] = rules
    return rules


def allowed(url: str) -> bool:
    """May AI Pulse fetch this URL? (robots.txt, fetched once per site per run; see API_HOSTS)"""
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host in API_HOSTS:
        return True
    with _robots_lock:
        rules = _robots.get(host) or _rules(parts.scheme or "https", host)
    return rules.can_fetch(ROBOT_NAME, url)


INTERMEDIATES = Path(__file__).resolve().parent / "certs" / "intermediates.pem"


def _tls() -> ssl.SSLContext:
    """Certificates are always verified. Mozilla's CA list (certifi) is used when installed: Windows' store
    lacks some roots and intermediates that official sites rely on (e.g. digital.gov.my). certs/ holds public
    intermediate certificates that some servers forget to send (parlimen.gov.my), as browsers fetch them;
    a chain must still end at a trusted root."""
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    if INTERMEDIATES.exists():
        context.load_verify_locations(cafile=str(INTERMEDIATES))
    return context


TLS = _tls()


def fetch(url: str, timeout: int = 20, attempts: int = ATTEMPTS) -> bytes:
    """GET a URL the site allows (see allowed), retrying rate limits (429), 5xx errors and network
    timeouts with backoff."""
    if not allowed(url):
        raise Disallowed(f"robots.txt of {urlsplit(url).netloc} doesn't allow fetching {url}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=TLS) as resp:
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


def clean_text(raw: str | None, limit: int = 3000) -> str:
    """Strip HTML, unescape entities, collapse whitespace, trim to a sentence. (Summaries are shortened later,
    by brief.py; a paper's whole abstract is kept so its contribution sentence can be found.)"""
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


def parse_federal_register(json_bytes: bytes) -> list[dict]:
    """Federal Register API (documents.json): US federal rules, proposed rules, notices and presidential
    documents, each with its official abstract."""
    return [{"title": clean_text(d.get("title"), 200), "url": d.get("html_url") or "",
             "summary": clean_text(d.get("abstract") or ""), "published": parse_date(d.get("publication_date")),
             "authors": []}
            for d in json.loads(json_bytes).get("results") or []]


def parse_govuk(json_bytes: bytes) -> list[dict]:
    """GOV.UK search API: UK government news, policy papers, consultations and guidance."""
    return [{"title": clean_text(r.get("title"), 200),
             "url": r["link"] if r.get("link", "").startswith("http") else "https://www.gov.uk" + r.get("link", ""),
             "summary": clean_text(r.get("description") or ""), "published": parse_date(r.get("public_timestamp")),
             "authors": []}
            for r in json.loads(json_bytes).get("results") or [] if r.get("link")]


# Korea's Ministry of Science and ICT: its English press releases list writes each row's title and date in
# inline script. A release opens at view.do with the board's number (bbsSeqNo) and the release's (nttSeqNo).
MSIT_VIEW = "https://www.msit.go.kr/eng/bbs/view.do?sCode=eng&mId=4&mPid=2&bbsSeqNo=42&nttSeqNo="
_MSIT_ROW = re.compile(r"""\$\('#td_'\+'NTT_SJ'\+'_(\d+)'\)\.html\('<a href="javascript:;" onclick="fn_detail\("(\d+)"\)"[^>]*><span>(.*?)</span>""")
_MSIT_DATE = re.compile(r"""if\('REG_DT' == 'REG_DT'\)\{\s*\$\('#td_'\+'REG_DT'\+'_(\d+)'\)\.html\('([A-Z][a-z]{2} \d{1,2}, \d{4})'\)""")


def parse_msit(html_bytes: bytes) -> list[dict]:
    """MSIT's English press releases list (see MSIT_VIEW): title, link and date of each release."""
    text = html_bytes.decode("utf-8", "replace")
    dates = dict(_MSIT_DATE.findall(text))
    entries, seen = [], set()
    for row, nid, title in _MSIT_ROW.findall(text):
        if nid in seen:
            continue
        seen.add(nid)
        when = dates.get(row)
        entries.append({"title": clean_text(html.unescape(title), 200), "url": MSIT_VIEW + nid, "summary": "",
                        "published": datetime.strptime(when, "%b %d, %Y").replace(tzinfo=timezone.utc) if when else None,
                        "authors": []})
    return entries


DIGITAL_MY = "https://www.digital.gov.my"
_DIGITAL_MY_ITEM = re.compile(r'href="(/en-GB/siaran/[^"#?]+)".*?<p class="line-clamp-2[^"]*">(.*?)</p>.*?'
                              r'<time[^>]*>(\d{1,2} \w{3} \d{4})</time>', re.S)
_DATELINE = re.compile(r"^[A-Z][A-Z .'-]+,\s*(\d{1,2} \w+|\w+ \d{1,2},?) \d{4}\s*[–—-]\s*")


def parse_digital_my(html_bytes: bytes) -> list[dict]:
    """Malaysia's Ministry of Digital: its English list of media releases and speeches (title, link, date).
    The list repeats each title as its description, so the release's first paragraph is read later (see
    `lead` and collect.py), once per new release."""
    entries, seen = [], set()
    for path, title, day in _DIGITAL_MY_ITEM.findall(html_bytes.decode("utf-8", "replace")):
        if path in seen:
            continue
        seen.add(path)
        entries.append({"title": clean_text(html.unescape(title), 200), "url": DIGITAL_MY + html.unescape(path),
                        "summary": "", "published": datetime.strptime(day, "%d %b %Y").replace(tzinfo=timezone.utc),
                        "authors": [], "lead": True})
    return entries


# A speech's opening courtesies say nothing about its subject.
_COURTESY = re.compile(r"^(\d+\.\s*)?(first of all|thank|i would like to (thank|begin)|good (morning|afternoon|evening)|ladies and|"
                       r"salam|assalam|bismillah|yang (amat )?berhormat|distinguished|honourable|dear|it is (a|my) "
                       r"(great )?(pleasure|honour))", re.I)


def lead_paragraph(html_bytes: bytes, title: str = "") -> str:
    """A release's first paragraph ("PUTRAJAYA, 10 July 2026 – The Ministry ..."), without the dateline;
    for a speech (no dateline), the first paragraph after its title."""
    paragraphs = [re.sub(r"^\d+\.\s+", "", re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", raw))).strip())
                  for raw in re.findall(r"<p[^>]*>(.*?)</p>", html_bytes.decode("utf-8", "replace"), re.S)]
    for text in paragraphs:
        if _DATELINE.match(text):
            return _DATELINE.sub("", text)
    after = [i for i, text in enumerate(paragraphs) if title and text.lower() == title.lower()]
    return next((text for text in paragraphs[after[-1] + 1:] if len(text) > 80 and not _COURTESY.match(text)),
                "") if after else ""


# A <p> whose attributes may contain ">" (Tailwind classes like "[&>:last-child]:mb-0").
_P = re.compile(r"""<p\b(?:"[^"]*"|'[^']*'|[^"'>])*>(.*?)</p>""", re.S)
# Menus, tables of contents, bylines in headers, captions: not the article.
_CHROME = re.compile(r"<(nav|header|aside|footer|script|style|figure|button)\b.*?</\1>", re.S | re.I)


def article_lead(html_bytes: bytes) -> str:
    """A blog post's opening paragraph: the first full sentence-ending paragraph (12+ words) after the headline,
    skipping menus, tables of contents and author lines ("Upvote 33 ... Follow")."""
    page = _CHROME.sub(" ", html_bytes.decode("utf-8", "replace"))
    start = page.lower().find("</h1>")
    for raw in _P.findall(page[start:] if start >= 0 else page):
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", raw))).strip()
        if len(text.split()) >= 12 and text[-1:] in ".!?:\"”)" and not re.search(r"\b(Upvote|Follow)\b", text):
            return text
    return ""


DUMA = "http://duma.gov.ru"  # its HTTPS port times out from abroad
_DUMA_LINK = re.compile(r'<a href="(/en/news/\d+/)"')
_DUMA_TIME = re.compile(r'<time datetime="([\d-]+) ')
_DUMA_TITLE = re.compile(r'itemprop="headline">(.*?)</h6>', re.S)
_DUMA_LEAD = re.compile(r'itemprop="description">(.*?)</p>', re.S)


def parse_duma_en(html_bytes: bytes) -> list[dict]:
    """Russia's State Duma: its English news list (headline, lead paragraph and date of each item; items
    listed without a date get the day they're first seen)."""
    entries = []
    for chunk in html_bytes.decode("utf-8", "replace").split('<li class="article-list__item')[1:]:
        link, title = _DUMA_LINK.search(chunk), _DUMA_TITLE.search(chunk)
        if not (link and title):
            continue
        day, lead = _DUMA_TIME.search(chunk), _DUMA_LEAD.search(chunk)
        entries.append({"title": clean_text(html.unescape(title.group(1)), 220), "url": DUMA + link.group(1),
                        "summary": clean_text(html.unescape(lead.group(1))) if lead else "",
                        "published": datetime.fromisoformat(day.group(1)).replace(tzinfo=timezone.utc) if day else None,
                        "authors": []})
    return entries


PARSERS = {"feed": parse, "msit": parse_msit, "digital_my": parse_digital_my, "duma_en": parse_duma_en, "hf_daily": parse_hf_daily, "arxiv_rss": parse_arxiv_rss,
           "federal_register": parse_federal_register, "govuk": parse_govuk}
