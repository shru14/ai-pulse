"""Command line: python -m aipulse {collect,serve,run,build,prune}"""

import argparse
import sys
import threading
import time
import traceback
from datetime import date, datetime, timedelta, timezone

from . import cluster, store
from .collect import collect, reclassify, resummarize, retag
from .server import serve


def main():
    p = argparse.ArgumentParser(prog="aipulse", description="Track AI releases, news and policy.")
    p.add_argument("--db", default="aipulse.db", help="SQLite database file (default: aipulse.db)")
    p.add_argument("--log", help="append all output to this file (for scheduled or windowless runs)")
    sub = p.add_subparsers(dest="cmd")
    p.set_defaults(cmd="run", host="127.0.0.1", port=8000, every_hours=6)

    c = sub.add_parser("collect", help="fetch all sources once and store new stories")
    c.add_argument("--max-age-days", type=int, default=3)

    s = sub.add_parser("serve", help="serve the feed page and JSON API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)

    r = sub.add_parser("run", help="serve AND collect on a timer (simplest always-on setup)")
    r.add_argument("--host", default="127.0.0.1")
    r.add_argument("--port", type=int, default=8000)
    r.add_argument("--every-hours", type=float, default=6)

    sub.add_parser("reclassify", help="re-run the sorting and tagging rules over stored stories")
    sub.add_parser("resummarize", help="re-clean stored headlines and fill in headline-only summaries")
    sub.add_parser("evaluate", help="score the sorting rules against hand-labelled stories")
    sub.add_parser("sources", help="show each source's health: last success, failures in a row, last error")
    sub.add_parser("regroup", help="regroup every stored story into cards (one card per event)")
    bf = sub.add_parser("backfill", help="one-time history: every stream back to --since (default 2023-01-01)")
    bf.add_argument("--since", default="2023-01-01", help="start date, YYYY-MM-DD")
    bf.add_argument("--only", action="append", choices=["news", "experts", "research", "papers"],
                    help="run just these groups (repeatable)")
    bl = sub.add_parser("bills", help="sync AI bills' stages from congress.gov and the European Parliament")
    bl.add_argument("--eu-since", type=int, help="also discover EU procedures from this year on (one-time backfill)")
    bl.add_argument("--us-days", type=int, help="look at US bills updated in the last N days (default: since last sync)")
    bl.add_argument("--max-pages", type=int, default=8, help="congress.gov pages of 250 updated bills per run")
    bl.add_argument("--only", choices=["us", "eu"], help="sync just one source")

    b = sub.add_parser("build", help="write a static copy of the site (for GitHub Pages)")
    b.add_argument("--out", default="site", help="output folder, replaced (default: site)")

    pr = sub.add_parser("prune", help="delete stories older than N days")
    pr.add_argument("--keep-days", type=int, default=365)

    a = p.parse_args()
    if a.log:
        sys.stdout = sys.stderr = open(a.log, "a", encoding="utf-8", buffering=1)

    if a.cmd == "collect":
        print(f"[{datetime.now():%Y-%m-%d %H:%M}] Collecting")
        conn = store.connect(a.db)
        print(f"[{datetime.now():%Y-%m-%d %H:%M}] Added {collect(conn, max_age_days=a.max_age_days)} new stories.")
    elif a.cmd == "serve":
        store.connect(a.db).close()
        serve(a.db, a.host, a.port)
    elif a.cmd == "run":
        def loop():
            while True:
                try:
                    conn = store.connect(a.db)
                    try:
                        print(f"[{datetime.now():%Y-%m-%d %H:%M}] Collected {collect(conn)} new stories.")
                    finally:
                        conn.close()
                except Exception:  # keep the timer alive; the next cycle retries
                    print(f"[{datetime.now():%Y-%m-%d %H:%M}] Collection failed:")
                    traceback.print_exc()
                time.sleep(a.every_hours * 3600)
        threading.Thread(target=loop, daemon=True).start()
        serve(a.db, a.host, a.port)
    elif a.cmd == "reclassify":
        conn = store.connect(a.db)
        print(f"Re-sorted {reclassify(conn)} stories; re-tagged {retag(conn)}; "
              f"regrouped {cluster.assign(conn, days=None)}.")
    elif a.cmd == "resummarize":
        conn = store.connect(a.db)
        print(f"Updated {resummarize(conn)} stories; regrouped {cluster.assign(conn, days=None)}.")
    elif a.cmd == "regroup":
        print(f"{cluster.assign(store.connect(a.db), days=None)} stories moved to a different card.")
    elif a.cmd == "evaluate":
        from .evaluate import evaluate, print_report
        print_report(evaluate())
    elif a.cmd == "sources":
        from .sources import SOURCES
        rows = store.source_health(store.connect(a.db), [s["url"] for s in SOURCES])
        tracked = {r["url"] for r in rows}
        failing = [r for r in rows if r["failing"]]
        print(f"{len(rows)} sources checked, {len(failing)} failing ({store.FAILING_AFTER}+ runs in a row)")
        for r in rows:
            state = "FAILING" if r["failing"] else f"{r['failures']} fail" if r["failures"] else "ok"
            last_ok = r["last_success"][:16].replace("T", " ") or "never"
            print(f"  {state:8} {r['name'][:48]:48} last ok (UTC) {last_ok:16} {r['last_error'][:60]}")
        never = [s for s in SOURCES if s["url"] not in tracked]
        if never:
            print(f"  {len(never)} sources not fetched yet")
    elif a.cmd == "bills":
        from . import bills
        conn = store.connect(a.db)
        since = datetime.now(timezone.utc) - timedelta(days=a.us_days) if a.us_days else None
        years = list(range(a.eu_since, date.today().year + 1)) if a.eu_since else None
        results = {}
        for name, run in (("us", lambda: bills.sync_congress(conn, since=since, max_pages=a.max_pages)),
                          ("eu", lambda: bills.sync_europarl(conn, years=years))):
            if a.only and a.only != name:
                continue
            try:  # one source failing (e.g. congress.gov's rate limit) doesn't stop the other
                results[name] = run()
            except Exception as exc:
                results[name] = f"failed ({exc})"
        us, eu = results.get("us", "skipped"), results.get("eu", "skipped")
        cluster.assign(conn, days=None)
        tracked = conn.execute("SELECT jurisdiction, stage, COUNT(*) FROM bills GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
        print(f"US: {us} bills changed stage; EU: {eu}. Tracking: " + ", ".join(f"{j} {s} {n}" for j, s, n in tracked))
    elif a.cmd == "build":
        from .static import build
        print(f"Wrote {build(store.connect(a.db), a.out)} cards to {a.out}/")
    elif a.cmd == "backfill":
        from datetime import date as _date
        from .backfill import run as backfill
        conn = store.connect(a.db)
        print(f"Added {backfill(conn, _date.fromisoformat(a.since), a.only)} stories.")
    elif a.cmd == "prune":
        print(f"Deleted {store.prune(store.connect(a.db), a.keep_days)} old stories.")


if __name__ == "__main__":
    main()
