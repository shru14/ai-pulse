"""Collect new AI stories from all sources into the database."""

from __future__ import annotations

import functools
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import time
from datetime import datetime, timedelta, timezone

from . import bills, brands, brief, classify, cluster, enrich, feeds, jurisdictions, models, store
from .sources import COMPANIES, EXPERT_FIELDS, PROFESSORS, SOURCES

# The regulation tracker follows proposals and adopted laws; other actions stay under "policy".
TRACKED_ACTIONS = ("proposal", "law")
# Items from the scholars the tracker follows carry this action instead of a regulatory one.
EXPERT = "expert"

_professor_keys = {classify.name_key(n): n for n, _ in PROFESSORS}
_companies = {name: re.compile(p, re.I) for name, p in COMPANIES.items()}
_team_author = re.compile(r"team|lab|research|\bai\b", re.I)


def match_companies(orgs: list[str], authors: list[str]) -> list[str]:
    """Companies named by a paper's claiming organization or a team author ("DeepSeek-AI", "Qwen Team")."""
    names = list(orgs) + [a for a in authors if " " not in a.strip() or _team_author.search(a)]
    return [c for c, p in _companies.items() if any(p.search(n) for n in names)]


class EmptyFeed(Exception):
    """A source that always lists its latest items (arXiv, Hugging Face) came back empty."""


EMPTY_RETRIES = 3
EMPTY_WAIT = 5.0  # seconds; grows 5s, 10s between tries


def fetch_entries(src: dict, fetcher=feeds.fetch) -> list[dict]:
    """Fetch and parse one source. Sources marked expect_entries are re-fetched when a reply comes back
    empty (arXiv does this intermittently), and count as failed if it stays empty."""
    parse = feeds.PARSERS[src.get("format", "feed")]
    for attempt in range(EMPTY_RETRIES if src.get("expect_entries") else 1):
        if attempt:
            time.sleep(EMPTY_WAIT * attempt)
        entries = parse(fetcher(src["url"]))
        if entries or not src.get("expect_entries"):
            return entries
    raise EmptyFeed(f"no entries after {EMPTY_RETRIES} tries")


def collect(conn, sources=SOURCES, max_age_days: int = 3, fetcher=feeds.fetch, log=print,
            official_bills: bool | None = None, backfill: bool = False) -> int:
    """official_bills: also sync bill stages from congress.gov and the European Parliament
    (default: only for the configured SOURCES, not for test feeds).
    backfill: a history run (aipulse/backfill.py). Its one-off searches stay out of source health, and
    headline-only stories get a short draft instead of a Bing lookup each."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    added, errors = 0, []
    use_llm = enrich.enabled()

    for src in sources:
        try:
            entries = fetch_entries(src, fetcher)
        except Exception as exc:  # one broken feed shouldn't stop the run
            errors.append(f"{src['name']}: {exc}")
            log(f"  ! {src['name']}: {exc}")
            if not backfill:
                store.record_source(conn, src.get("label", src["name"]), src["url"], ok=False, error=str(exc) or type(exc).__name__)
            conn.commit()
            continue

        new_here = 0
        src_cutoff = min(cutoff, datetime.now(timezone.utc) - timedelta(days=src.get("max_age_days", 0)))
        professors = {classify.name_key(n): n for n in src.get("professors", [])}
        expert = src.get("expert")
        for e in entries[: src.get("max_items")]:
            if not e["title"] or not e["url"]:
                continue
            published = e["published"] or datetime.now(timezone.utc)
            if published < src_cutoff:
                continue
            authors = e.get("authors", [])
            companies = []
            if src.get("companies"):
                # Hugging Face Daily Papers: keep papers from big tech, or by a listed professor.
                matched = [_professor_keys[k] for a in authors if (k := classify.name_key(a)) in _professor_keys]
                companies = match_companies(e.get("orgs", []), authors)
                if not matched and not companies:
                    continue
            else:
                # arXiv author search is fuzzy; keep a paper only if a tracked person is really an author.
                matched = [professors[k] for a in authors if (k := classify.name_key(a)) in professors]
                if professors and not matched:
                    continue
            # Google News titles end with " - Publisher"; keep the publisher as the source.
            title, source = e["title"], src["name"]
            if "news.google.com" in src["url"] and " - " in title:
                title, source = title.rsplit(" - ", 1)
            title = brief.clean_title(title, source)
            summary = brief.clean_summary(e["summary"], title, source)
            if backfill:
                from .backfill import is_noise  # forums, docs, status pages, other languages
                if is_noise(title, source):
                    continue

            ai_only = src.get("ai_only", src["category"] == "tool")
            if not ai_only and not classify.is_ai_related(title, e["summary"]):
                continue  # general feeds carry non-AI stories too
            if src.get("ai_in_title") and not classify.is_ai_related(title, ""):
                continue

            item = {
                "title": title.strip(),
                "summary": summary,
                "url": e["url"],
                "source": source.strip(),
                "category": classify.categorize(title, summary, src["category"]),
                "date": published.date().isoformat(),
                "tags": classify.tags_for(title, summary),
                "authors": authors[:30],
            }
            if src["category"] == "research":
                # Papers are tagged only with the professors and companies behind them.
                item["tags"] = list(dict.fromkeys([*matched, *companies, *filter(None, [src.get("org")])]))
            elif expert:
                people = [expert] if isinstance(expert, str) else matched
                fields = [EXPERT_FIELDS[p] for p in people if p in EXPERT_FIELDS]
                item.update(category="regulation", action=EXPERT, jurisdictions=[],
                            tags=list(dict.fromkeys(people + fields)))

            better = None
            if use_llm and not store.title_exists(conn, item["title"]):
                better = enrich.enrich(item["title"], item["summary"], item["source"])
                if better:
                    if better.get("relevant") is False:
                        continue
                    if src["category"] != "research" and not expert:  # these keep their tab and tags
                        item["category"] = better["category"]
                        item["tags"] = (better.get("tags") or item["tags"])[:4]
                    item["summary"] = better.get("summary") or item["summary"]
            if not expert:
                apply_regulation(item, src.get("jurisdictions", []), better)
                if src["category"] == "regulation" and item["category"] != "regulation":
                    continue  # the tracker's searches are broad; keep only proposals and laws from them

            if not store.exists(conn, item["url"]):
                if backfill and not item["summary"] and item["date"] < _days_ago(REFRESH_DAYS):
                    item["summary"] = brief.draft(item, PLACE_NAMES)  # old news: a lookup each would take hours
                else:
                    fill_summary(item, fetcher)
            if store.insert(conn, item):
                new_here += 1
        if not backfill:
            store.record_source(conn, src.get("label", src["name"]), src["url"], ok=True, entries=len(entries), added=new_here)
        conn.commit()
        added += new_here
        log(f"  {src['name']}: {new_here} new")
        time.sleep(src.get("pause", 0.5))  # be polite to feed hosts

    if official_bills if official_bills is not None else sources is SOURCES:
        bills.sync(conn, fetcher, log=log)  # official bill stages (congress.gov, European Parliament)
        models.sync(conn, fetcher, log=log)  # new AI models for the Releases stream's tracker
    if backfill:
        return added  # the backfill regroups and looks up logos once, at the end
    cluster.assign(conn)  # put new stories on the same card as other outlets' versions, and on bills' cards
    try:
        refresh_summaries(conn, fetcher, log=log)
    except Exception as e:
        log(f"  summaries: {e}")
    try:  # look up brand logos for recent cards now, so the page finds them cached
        brands.add_logos(conn, store.cards(conn, days=30, limit=1000)[0], lookups=300)
    except Exception as e:
        log(f"  brand logos: {e}")
    store.log_run(conn, added, errors)
    return added


PLACE_NAMES = {code: v[0] for code, v in jurisdictions.JURISDICTIONS.items()}


REFRESH_DAYS = 30  # stories this recent always get a real summary lookup


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).date().isoformat()


def refresh_summaries(conn, fetcher=feeds.fetch, limit: int | None = 300, log=print,
                      since: str | None = None, recent_only: bool = True, workers: int = 1) -> int:
    """Retry the Bing lookup for headline-only stories that ended up with a draft, nothing, or just
    their headline (a lookup that failed, or a history run), newest first. Returns how many got one.

    Every collection runs it for the last 30 days, retrying only stories added in the last 3 days so
    each gets a few chances without being looked up forever. `python -m aipulse summaries --since
    2026-01-01` runs it once over a longer span, several lookups at a time (`workers`)."""
    added = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat() if recent_only else ""
    rows = conn.execute(
        "SELECT id, title, summary, source, url FROM items "
        "WHERE date >= ? AND added_at >= ? AND url LIKE '%news.google.com%' ORDER BY date DESC",
        (since or _days_ago(REFRESH_DAYS), added)).fetchall()
    todo = [r for r in rows if _weak(r["summary"], r["title"], r["source"])][:limit]  # e.g. headline + publisher
    lookup = functools.partial(feeds.fetch, attempts=1) if fetcher is feeds.fetch else fetcher
    fixed = done = 0
    # Lookups run in threads (they're network waits); the database is written from this thread only.
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(brief.find_summary, r["title"], r["url"], r["source"], lookup): r for r in todo}
        for fut in as_completed(futures):
            r, done = futures[fut], done + 1
            snippet = fut.result()
            if snippet:
                store.update_text(conn, r["id"], r["title"], snippet)
                conn.commit()  # at once: the web server and collection need the lock too
                fixed += 1
            if done % 200 == 0:
                log(f"  summaries: {done}/{len(todo)} looked up, {fixed} found")
    conn.commit()
    if todo:
        log(f"  summaries: {fixed} of {len(todo)} headline-only stories found on Bing News")
    return fixed


def _weak(summary: str, title: str, source: str) -> bool:
    return not summary or brief.is_draft(summary) or not brief.clean_summary(summary, title, source)


def export_summaries(conn, since: str) -> dict[str, str]:
    """Real summaries of headline-only (Google News) stories since a date, by story id. The repair runs on
    a PC (Google limits how fast its links can be decoded); this carries its results to the public site."""
    rows = conn.execute("SELECT id, title, summary, source FROM items WHERE date >= ? AND url LIKE '%news.google.com%'",
                        (since,)).fetchall()
    return {r["id"]: r["summary"] for r in rows if not _weak(r["summary"], r["title"], r["source"])}


def apply_summaries(conn, summaries: dict[str, str]) -> int:
    """Fill in stories whose summary is still weak from an export_summaries() file. Returns how many changed."""
    changed = 0
    for i in range(0, len(summaries), 500):
        ids = list(summaries)[i:i + 500]
        for r in conn.execute(f"SELECT id, title, summary, source FROM items WHERE id IN ({','.join('?' * len(ids))})",
                              ids).fetchall():
            if _weak(r["summary"], r["title"], r["source"]):
                store.update_text(conn, r["id"], r["title"], summaries[r["id"]])
                changed += 1
    conn.commit()
    return changed


def fill_summary(item: dict, fetcher=feeds.fetch) -> None:
    """Give a headline-only story a "what it covers" line: the lead text of the same story found on
    Bing News, else a short draft from its category, places and tags."""
    if not item["summary"] and "news.google.com" in item["url"]:
        # Lookups are optional extras: one attempt, no retry waits.
        lookup = functools.partial(feeds.fetch, attempts=1) if fetcher is feeds.fetch else fetcher
        item["summary"] = brief.find_summary(item["title"], item["url"], item.get("source", ""), lookup)
    if not item["summary"]:
        item["summary"] = brief.draft(item, PLACE_NAMES)


def resummarize(conn, fetcher=feeds.fetch, log=print) -> int:
    """Re-clean stored headlines and summaries and fill in headline-only stories. Returns how many changed."""
    changed = 0
    for it in store.query(conn, None, None, None, limit=100000):
        title = brief.clean_title(it["title"], it["source"])
        # Drafts are rebuilt from scratch so they reflect the story's current sorting.
        summary = "" if brief.is_draft(it["summary"]) else brief.clean_summary(it["summary"], title, it["source"])
        updated = {**it, "title": title, "summary": summary}
        fill_summary(updated, fetcher)
        if (updated["title"], updated["summary"]) != (it["title"], it["summary"]):
            store.update_text(conn, it["id"], updated["title"], updated["summary"])
            changed += 1
            if changed % 25 == 0:
                conn.commit()
                log(f"  {changed} updated")
    conn.commit()
    return changed


def apply_regulation(item: dict, default_jurisdictions: list[str] = (), llm: dict | None = None) -> None:
    """Move a policy story into the regulation tracker when it reports a proposal or an adopted law.

    Needs both one of those actions and at least one jurisdiction; anything else (including
    enforcement, investigations and guidance) stays under "policy".
    """
    if item["category"] not in ("policy", "regulation") or item.get("action") == EXPERT:
        return
    if item.get("source") in bills.OFFICIAL_SOURCES:  # official bill records are sorted by bills.py
        return
    llm = llm or {}
    action = llm.get("action") if llm.get("action") in classify.ACTIONS else None
    action = action or classify.regulatory_action(item["title"])
    # Google News summaries repeat the headline plus the publisher's name, which can name a country.
    # Generated drafts ("A proposal in the United States and China.") are ignored so they can't feed back.
    summary = "" if item["summary"].startswith(item["title"][:40]) or brief.is_draft(item["summary"]) else item["summary"]
    places = [j for j in llm.get("jurisdictions") or [] if j in jurisdictions.JURISDICTIONS]
    places = places or jurisdictions.detect(item["title"], summary, actors_only=True) or list(default_jurisdictions)
    if action in TRACKED_ACTIONS and places:
        places = places[:4]
        if "US" in places:  # which state, for the US-by-state map ("US-OR" next to "US")
            places += [s for s in jurisdictions.us_states(item["title"], summary) if s not in places]
        item.update(category="regulation", action=action, jurisdictions=places)
    else:
        item.update(category="policy", action=None, jurisdictions=[])


def retag(conn) -> int:
    """Recompute keyword tags (companies, places, topics) for stored stories. Papers and expert pieces
    keep their person / company tags. Returns how many changed."""
    changed = 0
    for it in store.query(conn, None, None, None, limit=100000):
        if it["category"] == "research" or it["action"] == EXPERT:
            continue
        text = "" if brief.is_draft(it["summary"]) else it["summary"]
        tags = classify.tags_for(it["title"], text)
        if tags != it["tags"]:
            store.set_tags(conn, it["id"], tags)
            changed += 1
    conn.commit()
    return changed


def reclassify(conn) -> int:
    """Re-run the sorting and regulation rules over stored policy and regulation stories.
    Returns how many changed."""
    changed = 0
    for it in store.query(conn, None, None, None, limit=100000):
        if it["category"] not in ("policy", "regulation") or it["action"] == EXPERT:
            continue
        before = (it["category"], it["jurisdictions"], it["action"] or None)
        if it["category"] == "policy" and it["source"] not in bills.OFFICIAL_SOURCES:
            # A story only reaches "policy" from a policy feed or by scoring as policy, so re-sorting
            # with "policy" as the default drops the ones a policy search picked up by mistake.
            text = "" if brief.is_draft(it["summary"]) else it["summary"]
            it["category"] = classify.categorize(it["title"], text, "policy")
            if it["category"] != "policy":
                store.set_regulation(conn, it["id"], it["category"], [], None)
                changed += 1
                continue
        apply_regulation(it)
        if (it["category"], it["jurisdictions"], it["action"]) != before:
            store.set_regulation(conn, it["id"], it["category"], it["jurisdictions"], it["action"])
            changed += 1
    conn.commit()
    return changed
