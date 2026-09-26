"""Brand logos for cards, found in the headline: "Ando wants to take on Slack ..." gets Slack's logo.

Nothing is listed by hand. For each name in a headline (a run of capitalised words such as "Slack",
"Black Forest Labs" or "Shield AI") it tries, in order:

1. Simple Icons (~3,000 brands, CC0, simpleicons.org): a vector logo in the brand's colour. The index
   is downloaded to data/brands.json and refreshed weekly.
2. Wikidata: if the name is an entity described as a company or product with an official website,
   that website's icon (via Google's favicon service). This covers brands Simple Icons had to remove,
   like Slack and Salesforce.

A plain one-word name ("Astra", "Make") must also be a company or product on Wikidata under exactly
that name, since such words are often something else. Results, including misses, are cached under
data/ so each name is looked up once. Without a network connection cards fall back to their topic or
category symbol. The AI companies in classify.COMPANY_TERMS keep their colour logos from the page.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

from . import classify, jurisdictions

SI_VERSION = "16"  # Simple Icons major version; jsDelivr serves its latest release
SI_INDEX_URL = f"https://cdn.jsdelivr.net/npm/simple-icons@{SI_VERSION}/data/simple-icons.json"
SI_ICON_URL = f"https://cdn.jsdelivr.net/npm/simple-icons@{SI_VERSION}/icons/{{slug}}.svg"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"
FAVICON_URL = "https://www.google.com/s2/favicons?domain={host}&sz=64"

DATA = Path(__file__).resolve().parent.parent / "data"
SI_INDEX_FILE = DATA / "brands.json"
WIKIDATA_FILE = DATA / "brands-wikidata.json"
ICON_DIR = DATA / "brand-icons"
SI_REFRESH = 7 * 24 * 3600
RECHECK_MISSES = 30 * 24 * 3600
USER_AGENT = "AIPulse/1.0 (personal AI news reader; https://github.com/shru14/ai-pulse)"

_CURATED = {name.lower() for name in classify.COMPANY_TERMS}
_PLACES = {v[0].lower() for v in jurisdictions.JURISDICTIONS.values()} | {
    n.lower() for n in jurisdictions.US_STATES.values()}

# A name: capitalised words (or ones starting with a digit), joined by spaces, hyphens, or "of"/"on"/"&".
_WORD = r"[A-Z0-9][\w.+&’'-]*"
_PHRASE = re.compile(rf"{_WORD}(?:(?:\s+(?:of|on|&)\s+|[ ‐-―-]){_WORD})*")
# Job titles after a company name ("ElevenLabs’ CEO") and suffixes that make it an adjective ("Qualcomm-powered").
_ROLE = re.compile(r"(?:\s+(?:CEO|CTO|CFO|COO|Chief|Founder|Co-founder|President|Chair|Chairman))+$")
_SUFFIX = re.compile(r"-(?:powered|backed|based|led|owned|made|funded|built|style|like)$")
# Wikidata descriptions that make an entity a brand we'd show, and ones that rule it out.
_BRANDLIKE = re.compile(r"company|corporation|startup|software|platform|service|\bapp\b|application|website|"
                        r"social network|search engine|messaging|technology|semiconductor|laborator|"
                        r"manufacturer|developer|automaker|conglomerate|retailer|\bbank\b|airline|brand|\bfirm\b|"
                        r"artificial intelligence|\bAI\b|cloud|internet|e-commerce|streaming|telecom|framework", re.I)
_NOT_BRAND = re.compile(r"family name|given name|surname|record label|album|song|film|novel|genus|species|river|"
                        r"city|town|village|municipality|human settlement|state of|country|programming language|"
                        r"file format|compression format|Wikimedia|scientific article|painting|character|magazine|"
                        r"newspaper|journal|periodical|publication|television|TV series|\bband\b|musician|"
                        r"politician", re.I)


def slug(title: str) -> str:
    """Simple Icons' file name for a brand title ("Monday.com" -> "mondaydotcom")."""
    s = title.lower().replace("+", "plus").replace(".", "dot").replace("&", "and")
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFD", s))


def _get(url: str, timeout: int = 10) -> bytes:
    if os.environ.get("AIPULSE_OFFLINE"):  # tests: use only what is cached
        raise OSError("offline")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ---------- Simple Icons ----------
_si: dict[str, dict] | None = None


def si_index() -> dict[str, dict]:
    """Brand title -> {title, slug, hex}, from the cached copy (downloaded when missing or a week old)."""
    global _si
    if _si is not None:
        return _si
    entries = None
    if not SI_INDEX_FILE.exists() or time.time() - SI_INDEX_FILE.stat().st_mtime > SI_REFRESH:
        try:
            raw = json.loads(_get(SI_INDEX_URL, timeout=20))
            icons = raw["icons"] if isinstance(raw, dict) else raw
            entries = [{"title": i["title"], "slug": i.get("slug") or slug(i["title"]), "hex": i["hex"]} for i in icons]
            DATA.mkdir(exist_ok=True)
            SI_INDEX_FILE.write_text(json.dumps(entries), encoding="utf-8")
        except Exception:
            entries = None  # offline: keep the old copy if there is one
    if entries is None and SI_INDEX_FILE.exists():
        entries = json.loads(SI_INDEX_FILE.read_text(encoding="utf-8"))
    _si = {e["title"]: e for e in entries or []}
    return _si


def si_path(brand_slug: str) -> str | None:
    """The logo's 24x24 SVG path, fetched once and cached."""
    f = ICON_DIR / f"{brand_slug}.svg"
    try:
        if not f.exists():
            ICON_DIR.mkdir(parents=True, exist_ok=True)
            f.write_bytes(_get(SI_ICON_URL.format(slug=brand_slug)))
        m = re.search(r'<path d="([^"]+)"', f.read_text(encoding="utf-8"))
        return m.group(1) if m else None
    except Exception:
        return None


# ---------- Wikidata: is it a company or product, and its website's icon ----------
_wd: dict[str, dict] | None = None


def _wd_cache() -> dict[str, dict]:
    global _wd
    if _wd is None:
        try:
            _wd = json.loads(WIKIDATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            _wd = {}
    return _wd


def _save_wd() -> None:
    DATA.mkdir(exist_ok=True)
    WIKIDATA_FILE.write_text(json.dumps(_wd_cache(), indent=0, sort_keys=True), encoding="utf-8")


def _lookup(name: str) -> dict:
    """{"brand": is there a company or product called exactly `name`, "site": its website's host}."""
    q = urllib.parse.urlencode({"action": "wbsearchentities", "search": name, "language": "en", "limit": 1,
                                "type": "item", "format": "json"})
    hits = json.loads(_get(f"{WIKIDATA_API}?{q}")).get("search", [])
    desc = hits[0].get("description", "") if hits else ""
    if not hits or hits[0].get("label") != name or not _BRANDLIKE.search(desc) or _NOT_BRAND.search(desc):
        return {"brand": False, "site": None}
    q = urllib.parse.urlencode({"action": "wbgetentities", "ids": hits[0]["id"], "props": "claims", "format": "json"})
    claims = json.loads(_get(f"{WIKIDATA_API}?{q}"))["entities"][hits[0]["id"]]["claims"].get("P856", [])
    sites = [(c.get("rank"), c["mainsnak"]["datavalue"]["value"]) for c in claims if "datavalue" in c["mainsnak"]]
    if not sites:
        return {"brand": True, "site": None}
    key = slug(name)
    # Prefer the preferred-rank site, then one whose address contains the name ("slack" in slack.com).
    sites.sort(key=lambda s: (s[0] != "preferred", key not in slug(urllib.parse.urlsplit(s[1]).hostname or "")))
    host = (urllib.parse.urlsplit(sites[0][1]).hostname or "").removeprefix("www.")
    return {"brand": True, "site": host or None}


def wikidata(name: str, budget: list[int]) -> dict | None:
    """Cached {brand, site, icon} for `name` (icon: a file in ICON_DIR with the website's icon), or None
    when it isn't cached and the budget of new lookups is spent. Misses are re-checked after 30 days."""
    cache = _wd_cache()
    hit = cache.get(name)
    if hit and (hit.get("brand") or time.time() - hit.get("checked", 0) < RECHECK_MISSES):
        if hit.get("icon") and not (ICON_DIR / hit["icon"]).exists():
            return dict(hit, icon=None)
        return hit
    if budget[0] <= 0:
        return None
    budget[0] -= 1
    try:
        entry = dict(_lookup(name), checked=int(time.time()), icon=None)
    except Exception:
        return None  # network trouble: try again next time
    if entry["site"]:
        try:
            data = _get(FAVICON_URL.format(host=urllib.parse.quote(entry["site"])))  # 404 raises when there's none
            ICON_DIR.mkdir(parents=True, exist_ok=True)
            entry["icon"] = f"site-{slug(name)}.{'jpg' if data[:3] == bytes([255, 216, 255]) else 'png'}"
            (ICON_DIR / entry["icon"]).write_bytes(data)
        except Exception:
            pass
    cache[name] = entry
    return entry


# ---------- Finding the brand in a headline ----------
def common_words(texts) -> set[str]:
    """Words the feed itself uses in lowercase at least twice ("slack" in "cut them some slack")."""
    counts: dict[str, int] = {}
    for text in texts:
        for w in re.findall(r"\b[a-z][a-z0-9.+-]*\b", text):
            counts[w] = counts.get(w, 0) + 1
    return {w for w, n in counts.items() if n >= 2}


def distinctive(name: str) -> bool:
    """Names that can't be ordinary words: several words, inner capitals or digits ("ElevenLabs", "GPT-5")."""
    return " " in name or bool(re.search(r"[a-z][A-Z]|\d|[.+&]", name)) or (name.isupper() and len(name) >= 3)


def title_case(title: str) -> bool:
    words = [w for w in re.findall(r"[A-Za-z][\w’'-]*", title)[1:] if len(w) > 3]
    return bool(words) and sum(w[0].isupper() for w in words) / len(words) >= 0.7


def names(title: str, common: set[str]) -> list[str]:
    """Candidate brand names in a headline, in order: runs of capitalised words, cleaned up.
    In Title Case Headlines every word is capitalised, so only distinctive names count there."""
    titled = title_case(title)
    out = []
    for m in _PHRASE.finditer(title):
        name = _ROLE.sub("", m.group().rstrip(".,:;!?"))
        name = _SUFFIX.sub("", re.sub(r"(['’]s|['’])$", "", name))
        words = name.split()
        if m.start() == 0:  # a sentence's first word is capitalised anyway: "Some Supabase customers"
            while words and words[0].lower() in common:
                words = words[1:]
            name = " ".join(words)
        # Title-case headlines run words together, so long runs are sentences, not names.
        if not name or len(words) > 4 or len(name) < 3 or name.isdigit() or name.lower() in _PLACES:
            continue
        if titled and not distinctive(name):
            continue
        if len(words) == 1 and name.lower() in common and m.start() == 0:
            continue  # "Discover ..." at the start could be the ordinary word
        out.append(name)
    return out


def logo_for(title: str, tags: list[str], common: set[str], budget: list[int]) -> dict | None:
    """{name, hex, path} (Simple Icons) or {name, src} (website icon) for a card, or None."""
    if any(t.lower() in _CURATED for t in tags):
        return None  # the page has its own logo for these
    si = si_index()
    for name in names(title, common):
        if name.lower() in _CURATED:
            return None
        wd = None
        if not distinctive(name):  # "Astra", "Make": only if Wikidata knows a company or product by that name
            wd = wikidata(name, budget)
            if not wd or not wd["brand"]:
                continue
        brand = si.get(name)
        path = brand and si_path(brand["slug"])
        if path:
            return {"name": brand["title"], "hex": "#" + brand["hex"], "path": path}
        wd = wd or wikidata(name, budget)
        if wd and wd.get("icon"):
            return {"name": name, "src": f"brand-icons/{wd['icon']}"}
    return None


def lab_logos(models: list[dict]) -> None:
    """Attach a Simple Icons logo to each model whose lab is a brand there ("Xiaomi", "Tencent")."""
    si = si_index()
    for m in models:
        if m["lab"].lower() in _CURATED:
            continue  # the page has its own logo
        brand = si.get(m["lab"])
        path = brand and si_path(brand["slug"])
        if path:
            m["logo"] = {"name": brand["title"], "hex": "#" + brand["hex"], "path": path}


_common_cache: tuple[int, set[str]] = (-1, set())


def add_logos(conn, cards: list[dict], lookups: int = 60) -> None:
    """Attach "logo" to each card whose headline names a brand. `lookups` caps new Wikidata lookups per call."""
    global _common_cache
    n = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    if _common_cache[0] != n:  # the lowercase vocabulary only changes when stories are added
        _common_cache = (n, common_words(f"{r[0]} {r[1]}" for r in conn.execute("SELECT title, summary FROM items")))
    budget = [lookups]
    for c in cards:
        logo = logo_for(c["title"], c.get("tags") or [], _common_cache[1], budget)
        if logo:
            c["logo"] = logo
    if budget[0] != lookups:
        _save_wd()
