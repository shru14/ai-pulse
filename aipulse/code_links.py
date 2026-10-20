"""Code and demo links (Research): for each paper on New tests for AI and Papers in the news, the links its authors
give, so a reader can see at a glance whether there's something to run. Read from two places: the paper's whole
abstract and comments on arXiv (the authors' own words), and the code repository and project page that Hugging Face's
papers page lists for it (huggingface.co/api/papers/<id>). Each link is sorted by where it points:

  Code    a code host (GitHub, GitLab, Bitbucket, Anonymous GitHub)
  Data    a dataset (a Hugging Face dataset, Zenodo, Kaggle)
  Try it  a demo someone can use in the browser (a Hugging Face Space)
  Site    any other page: the paper's project page, leaderboard or blog post

One link of each kind is kept, the abstract's first. Read in `collect` full runs, for papers not read in the past
week (meta key "links"); a paper that can't be read keeps the links last read. Papers off arXiv have none.
"""
from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlsplit

from . import feeds, store

KEY = "links"  # the meta row: {arXiv id: {"read": ISO time, "links": {kind: url}}}
HEALTH = "Code and demo links: arXiv abstracts and Hugging Face papers"
ARXIV_API = "http://export.arxiv.org/api/query"
HF_API = "https://huggingface.co/api/papers/"
STALE = timedelta(days=7)
KINDS = ("Code", "Data", "Try it", "Site")
CODE_HOSTS = {"github.com", "gitlab.com", "bitbucket.org", "anonymous.4open.science"}
DATA_HOSTS = {"zenodo.org", "www.kaggle.com", "kaggle.com"}
_ATOM = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
_URL = re.compile(r"https?://[^\s,;<>\"')\]}]+")


def arxiv_id(url: str) -> str:
    """The arXiv id in a paper's address, without its version ("" when it isn't an arXiv paper)."""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})", url or "")
    return m.group(1) if m else ""


def kind(url: str) -> str | None:
    """Which kind of link `url` is, or None for links that aren't the paper's own (arXiv, a DOI, a Hugging Face
    account page)."""
    host = urlsplit(url).netloc.lower().removeprefix("www.") if url.startswith("http") else ""
    path = urlsplit(url).path.strip("/")
    if not host or host in {"arxiv.org", "doi.org", "dx.doi.org"}:
        return None
    if host in CODE_HOSTS:
        return "Code" if "/" in path or host == "anonymous.4open.science" else None
    if host == "huggingface.co":
        if path.startswith("datasets/") and path.count("/") >= 2:
            return "Data"
        if path.startswith("spaces/") and path.count("/") >= 2:
            return "Try it"
        return None  # a model or an account page
    if host in DATA_HOSTS or f"www.{host}" in DATA_HOSTS:
        return "Data"
    return "Site"


def sort(urls: list[str]) -> dict[str, str]:
    """The first link of each kind among `urls`, in KINDS order."""
    out: dict[str, str] = {}
    for u in urls:
        u = u.rstrip(".")
        k = kind(u)
        if k and k not in out:
            out[k] = u
    return {k: out[k] for k in KINDS if k in out}


def _abstracts(ids: list[str], fetcher) -> dict[str, list[str]]:
    """Each paper's links in its abstract and comments, by arXiv id, 100 papers a request, a request every 3.5 s."""
    out = {}
    for i in range(0, len(ids), 100):
        if i:
            time.sleep(3.5)
        batch = ids[i:i + 100]
        xml = ET.fromstring(fetcher(f"{ARXIV_API}?id_list={','.join(batch)}&max_results={len(batch)}"))
        for e in xml.findall("a:entry", _ATOM):
            aid = arxiv_id(e.findtext("a:id", "", _ATOM))
            text = " ".join([e.findtext("a:summary", "", _ATOM)] + [c.text or "" for c in e.findall("x:comment", _ATOM)])
            if aid:
                out[aid] = _URL.findall(text)
    return out


def _hugging_face(aid: str, fetcher) -> list[str]:
    """The code repository and project page Hugging Face lists for the paper ([] when it has no page for it)."""
    try:
        d = json.loads(fetcher(HF_API + aid))
    except Exception:
        return []
    return [u for u in (d.get("githubRepo"), d.get("projectPage")) if isinstance(u, str) and u.startswith("http")]


def refresh(conn, urls: list[str], fetcher=feeds.fetch, now: datetime | None = None) -> str:
    """Read the links of the arXiv papers among `urls` not read in the past week. Logged in the sources table like a
    news source, so failing 3 runs in a row reaches the project inbox."""
    now = now or datetime.now(timezone.utc)
    saved = load(conn)
    due = sorted({a for a in map(arxiv_id, urls) if a} - {a for a, v in saved.items()
                                                          if now - datetime.fromisoformat(v["read"]) < STALE})
    if not due:
        return "all read this week"
    try:
        found = _abstracts(due, fetcher)
        if not found:
            raise RuntimeError("arXiv returned no papers")
    except Exception as e:
        store.record_source(conn, HEALTH, ARXIV_API, ok=False, error=str(e) or type(e).__name__)
        return f"not read ({e})"
    for aid in due:
        if aid in found:
            saved[aid] = {"read": now.isoformat(timespec="minutes"),
                          "links": sort(found[aid] + _hugging_face(aid, fetcher))}
            time.sleep(0.5)
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (KEY, json.dumps(saved)))
    conn.commit()
    store.record_source(conn, HEALTH, ARXIV_API, ok=True, entries=len(found))
    return f"{len(found)} papers read, {sum(bool(saved[a]['links']) for a in found)} with links"


def load(conn) -> dict:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (KEY,)).fetchone() if conn else None
    return json.loads(row[0]) if row else {}


def of(saved: dict, url: str) -> dict[str, str]:
    """The paper's links by kind ({} when it has none or isn't on arXiv)."""
    return saved.get(arxiv_id(url), {}).get("links", {})


def html(links: dict[str, str]) -> str:
    """The links as small labelled links, "Code · Data · Try it · Site" ("" when there are none)."""
    return " · ".join(f'<a href="{escape(u)}" rel="noopener">{k}</a>' for k, u in links.items())
