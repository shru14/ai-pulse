"""Command line: python -m aipulse {collect,serve,run,build,prune}"""

import argparse
import os
import sys
import threading
import time
import traceback
from datetime import date, datetime, timedelta, timezone

from . import cluster, rss, store
from .collect import collect, reclassify, resummarize, retag
from .server import serve

# `bills --only` keys, in the order `bills.sync()` runs them during collection.
BILL_SOURCES = [("us", "US"), ("eu", "EU"), ("uk", "UK"), ("br", "Brazil"), ("au", "Australia"),
                ("cn", "China"), ("in", "India"), ("jp", "Japan"), ("vn", "Vietnam"), ("ch", "Switzerland"),
                ("my", "Malaysia"), ("tw", "Taiwan"), ("kr", "Korea"), ("ie", "Ireland"), ("no", "Norway"),
                ("oecd", "OECD.AI"),
                ("std", "AI standards"), ("aiid", "AI Incident Database")]


HELD = 3  # exit code of a digest the quality check held (an error is 1)


def main():
    p = argparse.ArgumentParser(prog="aipulse", description="Track AI releases, news and policy.")
    p.add_argument("--db", default="aipulse.db", help="SQLite database file (default: aipulse.db)")
    p.add_argument("--log", help="append all output to this file (for scheduled or windowless runs)")
    sub = p.add_subparsers(dest="cmd")
    p.set_defaults(cmd="run", host="127.0.0.1", port=8000, every_hours=6)

    c = sub.add_parser("collect", help="fetch all sources once and store new stories")
    c.add_argument("--max-age-days", type=int, default=3)
    c.add_argument("--labs", action="store_true",
                   help="only the labs' and companies' own blogs (the quick run between full updates)")

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
    sub.add_parser("status", help="Markdown summary of the feed and failing sources (for the run page)")
    sa = sub.add_parser("source-alert", help="email the project inbox about sources that just started failing (once each)")
    sa.add_argument("--dry-run", metavar="FILE", help="write the email's HTML to FILE instead of sending it")
    bf = sub.add_parser("backfill", help="one-time history: every stream back to --since (default 2023-01-01)")
    bf.add_argument("--since", default="2023-01-01", help="start date, YYYY-MM-DD")
    bf.add_argument("--only", action="append", choices=["feeds", "official", "research", "papers"],
                    help="run just these groups (repeatable)")
    hi = sub.add_parser("history", help="a new stream's sources back to 2023, a few minutes a run (resumes)")
    hi.add_argument("--stream", required=True, help="the stream's category, e.g. infra")
    hi.add_argument("--minutes", type=float, default=12, help="stop after this long; the next run carries on")
    bl = sub.add_parser("bills", help="sync AI bills' stages from official records (US, EU, UK, Canada, Brazil, Australia, China, India, "
                                        "Japan, Vietnam, Switzerland, Malaysia, Taiwan, Korea) and OECD.AI")
    bl.add_argument("--eu-since", type=int, help="also discover EU procedures from this year on (one-time backfill)")
    bl.add_argument("--us-days", type=int, help="look at US bills updated in the last N days (default: since last sync)")
    bl.add_argument("--max-pages", type=int, default=40, help="congress.gov pages of 250 updated bills per run")
    bl.add_argument("--only", choices=[k for k, _ in BILL_SOURCES], help="sync just one source")

    b = sub.add_parser("build", help="write a static copy of the site (for GitHub Pages)")
    b.add_argument("--out", default="site", help="output folder, replaced (default: site)")

    dg = sub.add_parser("digest", help="email one day's digest (the four 6-hour updates) to an address")
    who = dg.add_mutually_exclusive_group(required=True)
    who.add_argument("--to", help="recipient address")
    who.add_argument("--subscribers", action="store_true",
                     help="every confirmed subscriber, each with their streams (from the sign-up web app)")
    dg.add_argument("--streams", default=",".join(rss.FEEDS), help="comma-separated streams (default: all)")
    dg.add_argument("--day", help="UTC day, YYYY-MM-DD (default: yesterday)")
    dg.add_argument("--dry-run", metavar="FILE", help="write the email's HTML to FILE instead of sending it")
    dg.add_argument("--layout", choices=["short", "full"], default="short",
                    help="short (the daily email): the ten that mattered most, then headlines; full: every story in one table")
    sub.add_parser("glossary", help="acronyms recent stories use often that the glossary doesn't explain yet")
    sub.add_parser("memes", help="ask Gemini (GEMINI_API_KEY, free tier) for last week's meme once and keep it")
    em = sub.add_parser("embed", help="story vectors for the weekly dossier's search (offline model; new or changed stories)")
    em.add_argument("--limit", type=int, help="at most this many stories this run (the first run has them all to do)")
    ds = sub.add_parser("dossiers", help="the week's dossier for every reader's question, kept for the site and the "
                                         "Sunday email (offline model; reads the questions with DIGEST_LIST_KEY)")
    ds.add_argument("--interest", action="append", help="these instead of the readers' (testing)")
    pr = sub.add_parser("prune", help="delete stories older than N days")
    pr.add_argument("--keep-days", type=int, default=365)

    a = p.parse_args()
    if a.log:
        sys.stdout = sys.stderr = open(a.log, "a", encoding="utf-8", buffering=1)

    if a.cmd == "collect":
        print(f"[{datetime.now():%Y-%m-%d %H:%M}] Collecting")
        conn = store.connect(a.db)
        from .sources import SOURCES
        sources = [x for x in SOURCES if x["category"] == "tool"] if a.labs else SOURCES
        print(f"[{datetime.now():%Y-%m-%d %H:%M}] Added {collect(conn, sources, max_age_days=a.max_age_days)} new stories.")
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
        sync_fns = {"uk": bills.sync_uk, "br": bills.sync_brazil, "au": bills.sync_australia,
                    "cn": bills.sync_china, "in": bills.sync_india, "jp": bills.sync_japan, "vn": bills.sync_vietnam,
                    "ch": bills.sync_switzerland, "my": bills.sync_malaysia, "tw": bills.sync_taiwan,
                    "kr": bills.sync_korea, "ie": bills.sync_ireland, "no": bills.sync_norway,
                    "oecd": bills._oecd_sync,
                    "std": bills._standards_sync, "aiid": bills._incidents_sync}
        runs = {"us": lambda: bills.sync_congress(conn, since=since, max_pages=a.max_pages),
                "eu": lambda: bills.sync_europarl(conn, years=years)}
        for name, label in BILL_SOURCES:
            run = runs.get(name) or (lambda fn=sync_fns[name]: fn(conn))
            if a.only and a.only != name:
                continue
            try:  # one source failing (e.g. congress.gov's rate limit) doesn't stop the others
                results[name] = run()
            except Exception as exc:
                results[name] = f"failed ({exc})"
        cluster.assign(conn, days=None)
        tracked = conn.execute("SELECT jurisdiction, stage, COUNT(*) FROM bills GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
        print("Bills changed stage: " + "; ".join(f"{label}: {results.get(k, 'skipped')}" for k, label in BILL_SOURCES) + ". Tracking: " + ", ".join(f"{j} {s} {n}" for j, s, n in tracked))
    elif a.cmd == "memes":
        from . import memegen
        conn = store.connect(a.db)
        cards, _ = store.cards(conn, days=16, limit=10**6)
        memegen.prepare(conn, cards, make=True)
        from . import memes
        print("Meme of the week:", "by Gemini" if any(k[0] == "week" for k in memes.GENERATED) else "rule-based")
    elif a.cmd == "build":
        from .static import build
        print(f"Wrote {build(store.connect(a.db), a.out)} cards to {a.out}/")
    elif a.cmd == "status":
        from .collect import status_report
        print(status_report(store.connect(a.db)))
    elif a.cmd == "source-alert":
        # Sources failing store.FAILING_AFTER runs in a row, told once each (it resets when one works again)
        from . import digest
        from .collect import source_alert
        from .sources import SOURCES
        conn = store.connect(a.db)
        rows = store.newly_failing(conn, [s["url"] for s in SOURCES])
        if not rows:
            print("No source has newly stopped working.")
        elif a.dry_run:
            open(a.dry_run, "w", encoding="utf-8").write(source_alert(rows)[2])
            print(f"{len(rows)} newly failing -> wrote {a.dry_run}")
        elif not os.environ.get("DIGEST_EMAIL"):
            print(f"{len(rows)} newly failing; DIGEST_EMAIL isn't set, so nothing was sent")
        else:
            note = source_alert(rows)
            digest.send(digest.sender(), *note)
            store.mark_alerted(conn, [r["url"] for r in rows])
            print(f"Sent to the project inbox: {note[0]}")
    elif a.cmd == "backfill":
        from datetime import date as _date
        from .backfill import run as backfill
        conn = store.connect(a.db)
        print(f"Added {backfill(conn, _date.fromisoformat(a.since), a.only)} stories.")
    elif a.cmd == "history":
        from .backfill import stream_history
        print(f"Added {stream_history(store.connect(a.db), a.stream, a.minutes)} stories.")
    elif a.cmd == "digest":
        from . import digest
        streams = [x.strip() for x in a.streams.split(",") if x.strip()]
        if not streams or any(x not in rss.FEEDS for x in streams):
            sys.exit(f"streams must be among: {', '.join(rss.FEEDS)}")
        from . import quality
        if a.subscribers:
            streams = list(rss.FEEDS)  # the check covers every stream, whoever chose what
        day = date.fromisoformat(a.day) if a.day else digest.yesterday()
        conn = store.connect(a.db)
        # The day, and the four weeks before it (what a usual day looks like; Sunday's word of the week, never
        # the week before's, is worked out from 3 weeks back)
        cards, _ = store.cards(conn, days=(date.today() - day).days + max(quality.HISTORY_DAYS, 28) + 2, limit=10**6)
        from . import memegen
        # the day's meme by Gemini, if GEMINI_API_KEY is set; Sunday's email has the week's instead
        memegen.prepare(conn, cards, day=day, make=True)
        by_stream = digest.by_streams(cards, streams, day)
        counts = {x: len(v) for x, v in by_stream.items()}
        for c in digest.left_out(cards, streams, day):
            print(f"Left out (doesn't name AI): {c['title']!r} ({c['source']})")
        found = quality.problems(by_stream, cards, day)
        if found:
            # Held for everyone: nothing is sent to readers; the project inbox gets what's wrong (a dry run
            # only writes it). The run fails with HELD, so GitHub shows it red and the day counts as handled
            # (digest.yml doesn't retry a held day, so the alert comes once).
            note = quality.alert(day, found, streams)
            print(f"HELD: {len(found)} problem(s) in the {day} digest {counts}:", *(f"  - {p}" for p in found), sep="\n")
            if a.dry_run:
                open(a.dry_run, "w", encoding="utf-8").write(note[2])
                print(f"alert -> wrote {a.dry_run}")
            else:
                digest.send(digest.sender(), *note)
                print(f"Alert sent to the project inbox: {note[0]}")
            sys.exit(HELD)
        # A story whose link is dead is left out of every email (logged by headline)
        dead = quality.dead_links(by_stream)
        for c in dead:
            print(f"Left out (dead link): {c['title']!r} ({c['source']})")
        if dead:
            gone = {c["url"] for c in dead}
            cards = [c for c in cards if c.get("url") not in gone]
            by_stream = digest.by_streams(cards, streams, day)
            counts = {x: len(v) for x, v in by_stream.items()}
        if a.subscribers:
            from . import subscribers
            # Each confirmed reader gets their own streams and choices; nothing on a day their streams were empty.
            # Only counts are printed: addresses never appear in the (public) logs.
            key = os.environ.get("DIGEST_LIST_KEY", "")
            readers = subscribers.current(key, os.environ.get("DIGEST_SIGNUP_URL", ""))
            from . import weekly
            # Sunday's email (the day is a Saturday): a reader with questions gets the note of their weekly dossier
            dossier = (lambda prefs: weekly.note(conn, key, prefs.get("interests") or [], day)) if digest.weekly(day) else (lambda prefs: None)
            # a weekly reader gets Sunday's email only (the day is a Saturday); daily readers get every one
            weekly_only = sum(1 for r in readers.values() if r[3].get("often") == "weekly")
            readers = digest.due(readers, day)
            emails = [(to, *e, one_click) for to, (chosen, one_click, link, prefs) in readers.items()
                      if (e := digest.build(cards, chosen, day, link, a.layout, prefs=prefs, dossier=dossier(prefs)))]
            if a.dry_run:
                tuned = sum(1 for r in readers.values() if any(v for k, v in r[3].items() if k != "often"))
                print(f"Checked, no problems: {len(emails)} of {len(readers)} subscribers would get the {day} digest "
                      f"({tuned} with their own choices; {weekly_only} weekly only) {counts}")
            else:
                print(f"Checked, no problems. Sent the {day} digest to {digest.send_all(emails)} of {len(readers)} subscribers "
                      f"({weekly_only} weekly only{'' if digest.weekly(day) else ', not today'}) {counts}")
            return
        link, prefs, note = "", None, None
        if os.environ.get("DIGEST_LIST_KEY") and a.to:
            # a sample to a subscriber's own address (the project inbox): their own email, with their link, choices
            # and dossier, as they'd get it; the address itself never appears in the log
            from . import subscribers as sb, weekly as wk
            key = os.environ["DIGEST_LIST_KEY"]
            mine = sb.current(key, os.environ.get("DIGEST_SIGNUP_URL", "")).get(a.to.lower())
            if mine:
                streams, _, link, prefs = mine
                note = wk.note(conn, key, prefs.get("interests") or [], day) if digest.weekly(day) else None
            print(f"Sample as the subscriber's own email: {'yes' if mine else 'no, not subscribed'}")
        email = digest.build(cards, streams, day, link, a.layout, prefs=prefs, dossier=note)
        if a.dry_run:
            open(a.dry_run, "w", encoding="utf-8").write(digest.preview(email[2]))
            print(f"Checked, no problems: {email[0]} {counts} -> wrote {a.dry_run}")
        else:
            digest.send(a.to, *email)
            print(f"Checked, no problems. Sent: {email[0]} {counts}")
    elif a.cmd == "glossary":
        from . import glossary
        recent, _ = store.cards(store.connect(a.db), days=90, limit=10**6)
        print(f"{len(glossary.ENTRIES)} entries; not explained yet, by how many of the last 90 days' cards use them:")
        for word, n in glossary.missing(recent):
            print(f"  {word}: {n}")
    elif a.cmd == "embed":
        from . import embed
        embed.update(store.connect(a.db), limit=a.limit)
    elif a.cmd == "dossiers":
        from . import embed, subscribers, weekly
        key = os.environ.get("DIGEST_LIST_KEY", "")
        if not key or not embed.available():
            print("dossiers: skipped (needs DIGEST_LIST_KEY and the embedding model)")
        else:
            try:
                wanted = a.interest or subscribers.interests(key)
            except Exception as e:  # e.g. the web app not yet updated to send them: last run's dossiers stay
                print(f"dossiers: skipped, the interests couldn't be read ({type(e).__name__})")
            else:
                weekly.prepare(store.connect(a.db), wanted, key, datetime.now(timezone.utc).date())
    elif a.cmd == "prune":
        print(f"Deleted {store.prune(store.connect(a.db), a.keep_days)} old stories.")


if __name__ == "__main__":
    main()
