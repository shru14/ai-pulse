"""Short, clean headlines and a one- or two-sentence "what it covers" line, without an LLM.

- clean_title() drops desk labels ("Watch:", "Eurobites:") and trailing site names ("— Cyprus Mail").
- clean_summary() keeps the first informative sentences of the feed text, drops boilerplate
  (author bios, "The post ... appeared first on", newsletter prompts) and anything that only
  repeats the headline. It returns "" when nothing is left, so the page never shows the headline twice.
- article_summary() fills in Google News items, whose feed text is just the headline: it follows the
  link to the original article and uses the description the publisher wrote for it (its meta tags).
- lookup_snippet() is the fallback: it searches Bing News RSS for the headline and uses the lead text
  of the matching story.
- draft() is the last resort: a short line built from what the tracker already knows about the story
  (its kind, the places it names, the companies or people tagged), e.g.
  "A proposal in the United Kingdom, involving Google."
"""

from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import quote_plus, urlencode, urlsplit

from . import classify, feeds, jurisdictions

MAX_CHARS = 300
USER_AGENT = "Mozilla/5.0 (compatible; AIPulse/1.0; +https://github.com/shru14/ai-pulse) personal news reader"
# Site-wide descriptions that say nothing about the story.
_GENERIC = re.compile(r"^(a )?blog post by\b|democratize artificial intelligence|^we.re on a journey|"
                      r"^(read|discover|explore|learn|find out|get|stay|see) (more|the latest|about|up to date|all)\b|"
                      r"^(subscribe|sign up|log in|join)\b|all impacted services|^(the )?latest (news|updates)\b|"
                      r"^(official|welcome to)\b", re.I)

_LABEL = re.compile(r"^(watch|video|exclusive|breaking|update[d]?|live|eurobites|podcast|listen|photos?)\s*[:|\-–—]\s*",
                    re.I)
_SITE_SUFFIX = re.compile(r"\s+[|\-–—]\s+([^|\-–—]{2,40})$")
_FUNCTION_WORDS = re.compile(r"\b(and|or|but|the|a|to|of|in|on|for|with|as|is|are|was|says?|after|over)\b")

_BOILERPLATE = re.compile(
    r"appeared first on|add yahoo as a preferred source|preferred source|sign up for|subscribe to|"
    r"newsletter|click here|read more|continue reading|listen to this article|advertisement|"
    r"originally (published|appeared)|republished|all rights reserved|getty images|photo:|image:|credit:|"
    r"has a degree in|\bis a (senior |staff |contributing )?(reporter|writer|editor|journalist|correspondent)\b|"
    r"follow us on|share this article|cookies",
    re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“‘(])")
# A period after these (or after a single initial) doesn't end a sentence: "Gov. Tina Kotek", "U.S. Sen."
_ABBREV = re.compile(r"(\b[A-Z]|\b(Gov|Sen|Rep|Rev|Dr|Mr|Mrs|Ms|Prof|Gen|Lt|Col|Sgt|St|Jr|Sr|Inc|Corp|Co|Ltd|"
                     r"No|vs|Jan|Feb|Mar|Apr|Aug|Sept?|Oct|Nov|Dec|Ore|Calif|Mass|Wash|Fla|Ill|Pa|Va|"
                     r"U\.S|U\.K|U\.N|E\.U))\.$")


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for piece in _SENTENCE.split(text):
        if out and _ABBREV.search(out[-1]):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return out
_WORDS = re.compile(r"[a-z0-9]{3,}")


def _words(text: str) -> set[str]:
    return set(_WORDS.findall(text.lower()))


def similarity(a: str, b: str) -> float:
    """Word overlap (Jaccard) between two texts, 0..1."""
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def clean_title(title: str, source: str = "") -> str:
    title = _LABEL.sub("", title.strip())
    m = _SITE_SUFFIX.search(title)
    head = title[: m.start()] if m else ""
    if m and head.count("(") == head.count(")"):  # "(10 – 23 Sep)" is a date range, not a site name
        tail = m.group(1).strip()
        looks_like_site = (tail.lower() == source.lower() or re.search(r"\.\w{2,4}$", tail)
                           or (len(tail.split()) <= 4 and not _FUNCTION_WORDS.search(tail.lower())
                               and all(w[:1].isupper() or w[:1].isdigit() for w in tail.split())))
        if looks_like_site:
            title = title[: m.start()].rstrip()
    return title


def clean_summary(text: str, title: str, source: str = "") -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    # Google News style: "<headline> <publisher>"; nothing to add.
    if similarity(text, title) > 0.75 or text.lower().startswith(title.lower()[:60]):
        rest = text[len(title):].strip() if text.lower().startswith(title.lower()) else ""
        if source and rest.lower().endswith(source.lower()):
            rest = rest[:-len(source)].strip()
        # What's left is the publisher or a subtitle ("— Measured, Not Claimed"), not a summary.
        if not rest or len(rest.strip(" —–-:|").split()) <= 8:
            return ""
    out = []
    for s in _sentences(text):
        s = s.strip()
        if not s or _BOILERPLATE.search(s) or similarity(s, title) > 0.7 or len(s.split()) < 4:
            continue
        out.append(s)
        if len(out) == 2 or sum(len(x) for x in out) > MAX_CHARS * 0.7:
            break
    summary = " ".join(out)
    if len(summary) > MAX_CHARS:
        cut = summary[:MAX_CHARS].rsplit(" ", 1)[0].rstrip(",;:")
        summary = cut + "…"
    return re.sub(r"\s*(\.\.\.|…)+$", "…", summary)


def _http(url: str, data: bytes | None = None, headers: dict | None = None, timeout: int = 12,
          retry: bool = True) -> tuple[str, str]:
    """GET (or POST) a page; one retry after a pause when the host says it's busy (HTTP 429)."""
    for attempt in range(2 if retry else 1):
        req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read(2_000_000).decode("utf-8", "replace"), resp.geturl()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt or not retry:
                raise
            time.sleep(8)
    raise RuntimeError("unreachable")


# Google allows only a slow, steady pace for decoding its links: one request at a time across threads,
# 1.5 s apart. After it says "too many requests", links aren't decoded at all for a few minutes (the
# lookup falls back to Bing at once) instead of everyone waiting.
GOOGLE_GAP, GOOGLE_COOLDOWN = 1.5, 300
_google_lock = threading.Lock()
_google_next = [0.0]
_google_blocked_until = [0.0]


def _google(url: str, **kw) -> tuple[str, str]:
    if time.time() < _google_blocked_until[0]:
        raise RuntimeError("Google is rate-limiting; skipping for now")
    with _google_lock:
        wait = _google_next[0] - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            return _http(url, retry=False, **kw)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                _google_blocked_until[0] = time.time() + GOOGLE_COOLDOWN
            raise
        finally:
            _google_next[0] = time.time() + GOOGLE_GAP


def google_blocked() -> bool:
    """True while Google is rate-limiting link decoding (see _google)."""
    return time.time() < _google_blocked_until[0]


def google_news_target(url: str) -> str | None:
    """The original article behind a news.google.com/rss/articles/... link. Google encodes it; its
    article page carries a signature that its own decoding endpoint accepts."""
    art_id = urlsplit(url).path.rsplit("/", 1)[-1]
    page, _ = _google(f"https://news.google.com/articles/{art_id}")
    sig, ts = re.search(r'data-n-a-sg="([^"]+)"', page), re.search(r'data-n-a-ts="([^"]+)"', page)
    if not (sig and ts):
        return None
    inner = ["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None,
                             0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0],
             art_id, int(ts.group(1)), sig.group(1)]
    body = urlencode({"f.req": json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]])}).encode()
    resp, _ = _google("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"})
    m = re.search(r'\[\\"garturlres\\",\\"(.*?)\\"', resp)
    return m.group(1).encode().decode("unicode_escape") if m else None


_META = [re.compile(p, re.I) for p in (
    r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description',
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description',
    r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']+)')]


def article_summary(url: str, title: str, source: str = "") -> str:
    """The publisher's own description of the story (og:description / meta description), cleaned, or ""."""
    if os.environ.get("AIPULSE_OFFLINE"):  # tests
        return ""
    try:
        target = google_news_target(url) if "news.google.com" in url else url
        if not target:
            return ""
        page, _ = _http(target)
    except Exception:
        return ""
    head = page[: page.find("</head>")] if "</head>" in page else page[:200_000]
    for pattern in _META:
        m = pattern.search(head)
        if m:
            text = html.unescape(m.group(1)).strip()
            if text and not _GENERIC.search(text):
                return clean_summary(text, title, source)
    return ""


def find_summary(title: str, url: str, source: str = "", fetcher=feeds.fetch) -> str:
    """A real summary for a headline-only story: the article's own description, else Bing News."""
    return article_summary(url, title, source) or lookup_snippet(title, fetcher)


MATCH = 0.5  # headline word overlap needed to accept a Bing result as the same story


def lookup_snippet(title: str, fetcher=feeds.fetch, pause: float = 1.0) -> str:
    """Lead text of the same story from Bing News RSS, or "" if no close match is found.

    Tries the plain headline, then the quoted headline; each finds stories the other misses.
    """
    for query in (title, f'"{title}"'):
        try:
            entries = feeds.parse(fetcher("https://www.bing.com/news/search?format=rss&q=" + quote_plus(query)))
        except Exception:
            entries = []
        time.sleep(pause)
        best = max(entries, key=lambda e: similarity(e["title"], title), default=None)
        if best and similarity(best["title"], title) >= MATCH:
            snippet = clean_summary(best["summary"], title)
            if snippet:
                return snippet
    return ""


_KIND = {"tool": "A release", "news": "Industry news", "policy": "Policy news", "research": "A paper",
         ("regulation", "proposal"): "A proposal", ("regulation", "law"): "A law adopted",
         ("regulation", "expert"): "Commentary"}
# Tags that name places rather than companies or people.
_PLACE_TAGS = {v[0] for v in jurisdictions.JURISDICTIONS.values()} | {"EU", "US", "UK", "China", "India"}
# Topic and field tags; a draft names only the companies and people involved.
_TOPIC_TAGS = classify.TOPIC_TAGS | {"Law", "Ethics", "Philosophy", "Governance"}


_NEEDS_THE = ("United ", "European ", "Netherlands", "Philippines")


def _the(place: str) -> str:
    """ "the United States", "the European Union", "international bodies" """
    if place == "International bodies":
        return "international bodies"
    return "the " + place if place.startswith(_NEEDS_THE) else place


def is_draft(summary: str) -> bool:
    """True for a line written by draft(); those must never feed back into sorting."""
    return len(summary) < 160 and summary.endswith(".") and summary.startswith(tuple(set(_KIND.values())))


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def draft(item: dict, place_names: dict[str, str]) -> str:
    """A factual one-liner from the story's category, places and tags; "" if it would say nothing."""
    kind = _KIND.get((item["category"], item.get("action"))) or _KIND.get(item["category"], "A story")
    codes = item.get("jurisdictions") or jurisdictions.detect(item["title"])
    places = [_the(place_names.get(c, c)) for c in codes]
    who = [t for t in item.get("tags") or [] if t not in _PLACE_TAGS and t not in _TOPIC_TAGS]
    if not places and not who:
        return ""
    line = kind
    if places:
        line += (" in " if item["category"] == "regulation" and item.get("action") != "expert" else " about ") + _join(places)
    if who:
        line += (", featuring " if item.get("action") == "expert" else ", involving ") + _join(who[:3])
    return line + "."
