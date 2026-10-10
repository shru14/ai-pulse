"""A tiny web server: the feed page and its JSON API."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import brands, glossary, jurisdictions, photos, preferences, rss, store, subscribers
from .sources import SOURCES

STREAM_PATHS = {"all", "releases", "industry", "research", "regulation", "policy", "infra"}
TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "index.html"

PER_PAGE = 40
MAX_PER_PAGE = 200
EU_MEMBERS = set(jurisdictions.EU_MEMBERS)


def _int(value, default: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value))) if str(value or "").isdigit() else default


def items_payload(conn, qs: dict) -> dict:
    """One page of cards for the page's current tab, search, time range and country, plus tab counts."""
    days = _int(qs.get("days"), 0, 0, 36500) or None
    category = qs.get("category") if qs.get("category") in store.CATEGORIES else None
    q, place = (qs.get("q") or "").strip() or None, qs.get("place") or None
    region = qs.get("region") if qs.get("region") in jurisdictions.REGIONS else None
    per_page = _int(qs.get("per_page"), PER_PAGE, 1, MAX_PER_PAGE)
    page = _int(qs.get("page"), 1, 1, 10**6)
    items, total = store.cards(conn, category, q, days, place, per_page, (page - 1) * per_page, EU_MEMBERS,
                               jurisdictions.region_codes(region) if region else None)
    brands.add_logos(conn, items, lookups=10)  # collection looks names up ahead; this only catches stragglers
    payload = {"items": items, "page": page, "perPage": per_page, "total": total,
               "hasMore": page * per_page < total, "counts": store.card_counts(conn, q, days),
               "stories": store.story_count(conn), "lastRun": store.last_run(conn),
               "jurisdictions": jurisdictions.meta(),
               "regions": {k: v[0] for k, v in jurisdictions.REGIONS.items()}}
    if category == "regulation":
        payload["map"] = store.regulation_tally(conn, q, days)
    return payload


ICON_TYPES = {"ico": "image/x-icon", "png": "image/png", "jpg": "image/jpeg", "gif": "image/gif"}


def make_handler(db_path: str):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, ctype: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlsplit(self.path)
            qs = {k: v[0] for k, v in parse_qs(url.query).items()}
            days = int(qs["days"]) if qs.get("days", "").isdigit() and qs["days"] != "0" else None
            conn = store.connect(db_path)
            try:
                if url.path == "/" or url.path.strip("/") in STREAM_PATHS:  # the front page and each stream's
                    self._send(photos.fill(subscribers.fill(TEMPLATE.read_text(encoding="utf-8"))).encode("utf-8"),
                               "text/html; charset=utf-8")
                elif url.path == "/api/items":
                    if qs.get("grouped") == "0":  # every story separately, for other tools
                        payload = {"items": store.query(conn, qs.get("category"), qs.get("q"), days,
                                                        _int(qs.get("limit"), 500, 1, 5000))}
                    else:
                        payload = items_payload(conn, qs)
                    self._send(json.dumps(payload).encode(), "application/json")
                elif url.path == "/meme.json":
                    from . import memes
                    recent, _ = store.cards(conn, days=16, limit=10**6, eu_members=EU_MEMBERS)
                    from . import memegen
                    memegen.prepare(conn, recent)  # only what the "memes" command already made (no Gemini call here)
                    self._send(json.dumps(memes.payload(recent)).encode(), "application/json")
                elif url.path in ("/about", "/about/"):
                    from .static import about_page
                    self._send(about_page().encode(), "text/html; charset=utf-8")
                elif url.path == "/social.json":
                    from . import social
                    self._send(json.dumps(social.payload(conn)).encode(), "application/json")
                elif url.path == "/glossary.json":
                    recent, _ = store.cards(conn, days=8, limit=10**6, eu_members=EU_MEMBERS)
                    self._send(json.dumps(glossary.payload(recent)).encode(), "application/json")
                elif url.path == "/tags.json":
                    every, _ = store.cards(conn, limit=10**6, eu_members=EU_MEMBERS)
                    self._send(json.dumps(preferences.options(every)).encode(), "application/json")
                elif url.path.startswith("/brand-icons/"):
                    name = url.path.rsplit("/", 1)[1]
                    f = brands.ICON_DIR / name
                    kind = ICON_TYPES.get(name.rsplit(".", 1)[-1])
                    if name.startswith("own-") and kind and "/" not in name and f.is_file():
                        self._send(f.read_bytes(), kind)
                    else:
                        self._send(b"Not found", "text/plain", 404)
                elif url.path.startswith("/fonts/") and url.path.endswith(".woff2") and "/" not in url.path[7:] \
                        and (TEMPLATE.parent / "fonts" / url.path[7:]).is_file():
                    self._send((TEMPLATE.parent / "fonts" / url.path[7:]).read_bytes(), "font/woff2")
                elif url.path.startswith("/memes/week-") and url.path.endswith(".jpg"):
                    from . import memegen, memes
                    from datetime import date as _date
                    recent, _ = store.cards(conn, days=16, limit=10**6, eu_members=EU_MEMBERS)
                    memegen.prepare(conn, recent)
                    try:
                        meme = memes.of_the_week(recent, _date.fromisoformat(url.path[12:-4]))
                    except ValueError:
                        meme = None
                    picture = meme and memes.render(meme)
                    self._send(picture, "image/jpeg") if picture else self._send(b"Not found", "text/plain", 404)
                elif url.path == "/photos/credits.html":
                    self._send(photos.credits_page().encode("utf-8"), "text/html; charset=utf-8")
                elif url.path.startswith("/photos/") and url.path.endswith(".jpg") and "/" not in url.path[8:] \
                        and (TEMPLATE.parent / "photos" / url.path[8:]).is_file():
                    self._send((TEMPLATE.parent / "photos" / url.path[8:]).read_bytes(), "image/jpeg")
                elif url.path.startswith("/feeds/") and url.path.endswith(".xml") and url.path[7:-4] in rss.FEEDS:
                    name = url.path[7:-4]
                    feed_cards, _ = store.cards(conn, rss.FEEDS[name][0], days=rss.DAYS + 1,
                                                limit=10**6, eu_members=EU_MEMBERS)
                    self._send(rss.feed_xml(name, feed_cards), "application/rss+xml; charset=utf-8")
                elif url.path == "/api/sources":
                    self._send(json.dumps(store.source_health(conn, [s["url"] for s in SOURCES])).encode(),
                               "application/json")
                else:
                    self._send(b"Not found", "text/plain", 404)
            finally:
                conn.close()

        def log_message(self, fmt, *args):
            pass

    return Handler


def serve(db_path: str, host: str = "127.0.0.1", port: int = 8000):
    httpd = ThreadingHTTPServer((host, port), make_handler(db_path))
    print(f"AI Pulse running at http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
