"""A tiny web server: the feed page and its JSON API."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from . import brands, jurisdictions, store
from .sources import SOURCES

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
    per_page = _int(qs.get("per_page"), PER_PAGE, 1, MAX_PER_PAGE)
    page = _int(qs.get("page"), 1, 1, 10**6)
    items, total = store.cards(conn, category, q, days, place, per_page, (page - 1) * per_page, EU_MEMBERS)
    brands.add_logos(conn, items, lookups=10)  # collection looks names up ahead; this only catches stragglers
    health = store.source_health(conn, [s["url"] for s in SOURCES])
    payload = {"items": items, "page": page, "perPage": per_page, "total": total,
               "hasMore": page * per_page < total, "counts": store.card_counts(conn, q, days),
               "stories": store.story_count(conn), "lastRun": store.last_run(conn),
               "jurisdictions": jurisdictions.meta(), "failingSources": [h for h in health if h["failing"]]}
    if category == "regulation":
        payload["map"] = store.regulation_tally(conn, q, days)
    return payload


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
                if url.path == "/":
                    self._send(TEMPLATE.read_bytes(), "text/html; charset=utf-8")
                elif url.path == "/api/items":
                    if qs.get("grouped") == "0":  # every story separately, for other tools
                        payload = {"items": store.query(conn, qs.get("category"), qs.get("q"), days,
                                                        _int(qs.get("limit"), 500, 1, 5000))}
                    else:
                        payload = items_payload(conn, qs)
                    self._send(json.dumps(payload).encode(), "application/json")
                elif url.path.startswith("/brand-icons/"):
                    name = url.path.rsplit("/", 1)[1]
                    f = brands.ICON_DIR / name
                    if name.startswith("site-") and name.endswith((".png", ".jpg")) and "/" not in name and f.is_file():
                        self._send(f.read_bytes(), "image/jpeg" if name.endswith(".jpg") else "image/png")
                    else:
                        self._send(b"Not found", "text/plain", 404)
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
