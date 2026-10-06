"""Collect new AI stories from all sources into the database."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from . import bills, brands, brief, classify, cluster, feeds, jurisdictions, store, translate
from .sources import COMPANIES, EXPERT_FIELDS, PROFESSORS, SOURCES

# The regulation tracker follows proposals and adopted laws; other actions stay under "policy".
TRACKED_ACTIONS = ("proposal", "law")
# Papers by the ethics and law scholars used to go to the tracker with this action; reclassify moves them to Research.
EXPERT = "expert"
# AI incidents and stories the AI Incident Database lists as their reports: always under Industry (incidents.py).
INCIDENT = "incident"

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


# Lines some feeds add to a description pointing to the story's other-language editions ("Cet article est aussi
# disponible en français", "Lire en Français اقرأ هذا باللغة العربية").
_OTHER_EDITIONS = re.compile(r"\s*(?:Cet article est aussi disponible en français|Lire en français|"
                             r"اقرأ هذا باللغة العربية|Read (?:this )?in (?:French|Arabic|Portuguese))\.?", re.I)
TRANSLATED_NOTE = "Machine-translated from {}; the original is linked."
UNTRANSLATED_NOTE = "Translate and read: the original is in {}."  # also the story's tag (classify.tags_for)
# A language marker in an address, whose English page is the same address without it: "…/nemotron-personas-japan-ja",
# "…/es/…", "…?lang=fr".
_URL_LANG = re.compile(r"(?:-|_)(?:ja|zh|ko|ru|ar|vi|es|fr|pt|de)(?=/?$)|/(?:ja|zh|ko|ru|ar|vi|es|fr|pt|de)(?=/)|[?&](?:lang|hl)=\w+")


def english_version(url: str, fetcher=feeds.fetch) -> tuple[str, str, str] | None:
    """The publisher's own English version of a page: the address without its language marker, or the English
    page it declares (hreflang="en"). (title, summary, url), or None."""
    tries = [u for u in dict.fromkeys([_URL_LANG.sub("", url, count=1)]) if u != url]
    try:
        page = fetcher(url).decode("utf-8", "replace")
        declared = re.findall(r"""<link[^>]+hreflang=["']en(?:-[A-Za-z]+)?["'][^>]*href=["']([^"']+)""", page)
        tries += [u for u in declared if u not in tries and u != url]
    except Exception:
        pass
    for candidate in tries[:3]:
        try:
            post = feeds.page_meta(fetcher(candidate))
        except Exception:
            continue
        if post["title"] and not translate.detect(post["title"]) and not translate.detect(post["summary"]):
            return post["title"], post["summary"], candidate
    return None


def in_english(conn, title: str, summary: str, url: str = "", source: str = "",
               fetcher=None) -> tuple[str, str, str]:
    """A story's headline, summary and link in English, never leaving it out: as they are; else the publisher's own
    English version (with `fetcher`); else translated offline (translate.py), marked as such; else, when no
    translation is possible, an English headline from its Latin-script names and a line saying what it is, tagged
    "Translate and read"."""
    summary = re.sub(r"^In partnership with\s+(?=[A-Z])", "", _OTHER_EDITIONS.sub("", summary).strip())
    langs = [translate.detect(title), translate.detect(summary)]
    if not any(langs):
        return title, summary, url
    lang = next(l for l in langs if l)
    name = translate.LANGUAGE_NAMES[lang]
    if fetcher and url:
        found = english_version(url, fetcher)
        if found:
            return found
    out = []
    for text, text_lang in zip((title, summary), langs):
        if text_lang:
            text = translate.english(conn, text_lang, [text]).get(text)
            if not text or "<unk>" in text:
                break
        out.append(text)
    else:
        return out[0], f"{out[1]} {TRANSLATED_NOTE.format(name)}".strip(), url
    # the names written in Latin letters ("Nemotron-Personas-Japan"), not a stray "AI" inside the other text
    names = " ".join(n for n in re.findall(r"[A-Za-z][\w.+-]*(?:[ :][A-Z][\w.+-]*)*", title) if len(n) >= 3).strip(" :")
    return ((f"{names} (in {name})" if len(names) >= 3 else f"A {name}-language story from {source or 'the source'}"),
            f"A {name}-language story{' from ' + source if source else ''}. {UNTRANSLATED_NOTE.format(name)}", url)


PAGE_LIST_MEMORY = 400  # post addresses remembered per news page


def page_list_entries(conn, src: dict, fetcher=feeds.fetch) -> list[dict]:
    """A lab with no feed ("format": "page_list"): its news page (or sitemap) lists its posts ("link": the pattern
    of a post's address). A post not seen before is read once for its title, description and date; a page that
    states no date gets the day it's first seen (the quick run checks every 30 minutes). The first time a news
    page is read, the posts it lists are only remembered, so old posts don't show up as new. With "notes", the
    page is a lab's developer release notes and its entries are read from it directly."""
    key = f"page_list:{src['name']}"
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    notes = src.get("notes")  # a page of release notes: the entries are on it (feeds.parse_xai_notes, ...)
    listed = feeds.PARSERS[notes](fetcher(src["url"])) if notes else None
    links = [e["url"] for e in listed] if notes else feeds.listed_links(fetcher(src["url"]), src["url"], src["link"])
    if not links:
        raise EmptyFeed("no posts listed")
    seen = json.loads(row[0]) if row else []
    entries = []
    if row and notes:
        # Only launches of the lab's own products ("keep"): not retirements, API parameters or other labs' models
        # it now offers ("The Agent API now supports anthropic/claude-opus-5-5").
        for e in listed:
            if (e["url"] not in seen and re.search(src["keep"], e["title"])
                    and not re.search(r"retire|deprecat|sunset|end of life", f"{e['title']} {e['summary']}", re.I)
                    and classify.categorize(e["title"], e["summary"], "tool") == "tool"):
                entries.append({**e, "published": datetime.now(timezone.utc)})
    elif row:
        for url in [u for u in links if u not in seen][: src.get("max_new", 10)]:
            if store.exists(conn, url):
                continue
            try:
                post = feeds.page_meta(fetcher(url))
            except Exception:  # a listed page that's gone (a stale sitemap entry): skipped, and remembered
                continue
            if post["title"]:
                entries.append({**post, "url": url, "authors": [],
                                "published": post["published"] or datetime.now(timezone.utc)})
            time.sleep(src.get("pause", 0.5))
    remembered = links + [u for u in seen if u not in links]
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, json.dumps(remembered[:PAGE_LIST_MEMORY])))
    conn.commit()
    return entries


def blog_category(src: dict, title: str, summary: str, url: str) -> str:
    """A lab's or company's own post: a release only when it launches something. A site that gives each launch
    its own page ("launch_pages", e.g. anthropic.com/claude-sonnet-5-5) says so by the address; its other posts
    are judged by the headline alone, since their descriptions use launch words for anything ("We're introducing
    a new research group", "gained unauthorized access to")."""
    launch = src.get("launch_pages")
    if not launch:
        return classify.categorize(title, summary, "tool")
    if classify.about_standards(title):
        return classify.categorize(title, "", "news")
    return "tool" if re.search(launch, url) else classify.categorize(title, "", "tool")


def collect(conn, sources=SOURCES, max_age_days: int = 3, fetcher=feeds.fetch, log=print,
            official_bills: bool | None = None, backfill: bool = False) -> int:
    """official_bills: also sync bill stages from congress.gov and the European Parliament
    (default: only for the configured SOURCES, not for test feeds).
    backfill: a history run (aipulse/backfill.py). Its one-off searches stay out of source health."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    added, errors = 0, []
    purge_disallowed(conn, log)
    purge_dropped(conn, log)

    for src in sources:
        try:
            entries = (page_list_entries(conn, src, fetcher) if src.get("format") == "page_list"
                       else fetch_entries(src, fetcher))
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
        for e in entries[: src.get("max_items")]:
            if not e["title"] or not e["url"]:
                continue
            e["url"] = urljoin(src["url"], e["url"])  # a feed that gives its links as paths (the EIA's)
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
            source = src["name"]
            title = brief.clean_title(e["title"], source)
            if "arxiv.org/abs/" in e["url"]:  # a paper: what it covers, from its abstract
                summary = brief.paper_summary(e["summary"], title)
            else:
                summary = brief.clean_summary(e["summary"], title, source)
            if src.get("english_only") and translate.detect(title):
                continue  # the same post in Japanese (Sakana AI posts both): the English one is kept
            title, summary, url = in_english(conn, title, summary, e["url"], source, fetcher)

            ai_only = src.get("ai_only", src["category"] == "tool")
            if src.get("infra_filter"):
                if not classify.is_infra(title, e["summary"]):
                    continue  # an energy or climate newsroom: only its stories about AI's infrastructure
            elif not ai_only and not classify.is_ai_related(title, e["summary"]) and not classify.infra_story(title):
                continue  # general feeds carry non-AI stories too (a data-centre story counts: it's AI's infrastructure)
            if src.get("ai_in_title") and not classify.is_ai_related(title, "") and not classify.infra_story(title):
                continue
            if (e.get("lead") or src.get("page_lead")) and not summary and not store.exists(conn, e["url"]):
                try:  # a list without descriptions: the item's own first paragraph, read once
                    page = fetcher(e["url"])
                    lead = (feeds.LEAD_READERS.get(src.get("format"), feeds.article_lead)(page) if src.get("page_lead")
                            else feeds.lead_paragraph(page, e["title"]))
                    summary = brief.clean_summary(lead, title, source)
                except Exception:
                    pass

            item = {
                "title": title.strip(),
                "summary": summary,
                "url": url,  # the publisher's English version, when there is one
                "source": source.strip(),
                "category": stream_of(src, title, summary, url),
                "date": published.date().isoformat(),
                "tags": classify.tags_for(title, summary, source=source),
                "authors": authors[:30],
            }
            if src["category"] == "research":
                # Papers are tagged only with the people (and a scholar's field) and companies behind them.
                fields = [EXPERT_FIELDS[p] for p in matched if p in EXPERT_FIELDS]
                item["tags"] = list(dict.fromkeys([*matched, *fields, *companies, *filter(None, [src.get("org")]), RESEARCH_TAG]))

            if src.get("government"):
                item["category"] = "policy"  # a government's own publication (sources.py)
            apply_regulation(item, src.get("jurisdictions", []))
            if src["category"] == "regulation" and item["category"] != "regulation":
                continue  # the tracker's searches are broad; keep only proposals and laws from them

            if src.get("paywall_check") and not store.exists(conn, item["url"]):
                if subscriber_only(conn, item["url"], fetcher):
                    continue  # every story on the site must be free to read
                conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("free:" + item["url"], _days_ago(0)))

            if not store.exists(conn, item["url"]):
                fill_summary(item)
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
        resummarize_papers(conn, fetcher, log=log)
        fill_page_leads(conn, fetcher, log=log)
        drop_subscriber_only(conn, fetcher, log=log)
        if (conn.execute("SELECT value FROM meta WHERE key = 'summaries_version'").fetchone() or [""])[0] != SUMMARIES:
            log(f"  summaries re-cleaned: {resummarize(conn, log=lambda *_: None)}")  # once, after brief.py changes
            conn.execute("INSERT OR REPLACE INTO meta VALUES ('summaries_version', ?)", (SUMMARIES,))
            conn.commit()
    if backfill:
        return added  # the backfill regroups and looks up logos once, at the end
    cluster.assign(conn)  # put new stories on the same card as other outlets' versions, and on bills' cards
    try:  # look up brand logos for recent cards now, so the page finds them cached
        brands.add_logos(conn, store.cards(conn, days=30, limit=1000)[0], lookups=300)
    except Exception as e:
        log(f"  brand logos: {e}")
    store.log_run(conn, added, errors)
    return added


PLACE_NAMES = {code: v[0] for code, v in jurisdictions.JURISDICTIONS.items()}


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).date().isoformat()


PURGE_KEY = "purged:google-news"


def purge_disallowed(conn, log=print) -> int:
    """Delete stories collected through Google News: its robots.txt and terms don't allow automated
    access, and their summaries came from decoding Google's links or from Bing News, whose terms forbid
    showing its results publicly. Runs once per database; returns how many stories were deleted."""
    if conn.execute("SELECT 1 FROM meta WHERE key = ?", (PURGE_KEY,)).fetchone():
        return 0
    n = conn.execute("DELETE FROM items WHERE url LIKE '%news.google.com%'").rowcount
    conn.execute("DELETE FROM sources WHERE url LIKE '%news.google.com%'")
    conn.execute("DELETE FROM meta WHERE key LIKE 'summary-tried:%' OR (key LIKE 'backfill:%'"
                 " AND key NOT LIKE 'backfill:arXiv%' AND key NOT LIKE 'backfill:Hugging Face%')")
    conn.execute("UPDATE items SET cluster = id WHERE cluster NOT IN (SELECT id FROM items)")  # lead was deleted
    conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (PURGE_KEY, _days_ago(0)))
    conn.commit()
    if n:
        cluster.assign(conn, days=None)
        log(f"  removed {n} stories collected through Google News")
    return n


# Sources dropped because they turned automated readers away: everything they gave is deleted, so nothing of
# theirs stays on the site (source name -> the start of its addresses).
DROPPED = {"Parliament of Canada": "https://www.parl.ca/",  # 6 Oct 2026, each answering even robots.txt with a 403
           "Rest of World": "https://restofworld.org/", "TechNode": "https://technode.com/"}


def purge_dropped(conn, log=print) -> int:
    """Delete every story, bill record, health row and saved state of a DROPPED source. Cheap when there is
    nothing left, so it runs every collection (a database restored from the seed is cleaned too)."""
    n = 0
    for name, prefix in DROPPED.items():
        n += conn.execute("DELETE FROM items WHERE source = ? OR url LIKE ?", (name, prefix + "%")).rowcount
        conn.execute("DELETE FROM sources WHERE url LIKE ?", (prefix + "%",))
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'bills'").fetchone():
            conn.execute("DELETE FROM bills WHERE source = ? OR url LIKE ?", (name, prefix + "%"))
    conn.execute("DELETE FROM meta WHERE key = 'canada_sessions'")  # LEGISinfo's sessions already read
    if n:
        conn.execute("UPDATE items SET cluster = id WHERE cluster NOT IN (SELECT id FROM items)")  # lead was deleted
        log(f"  removed {n} stories from dropped sources")
    conn.commit()
    return n


PAYWALL_PER_RUN = 40  # stored stories from paywall_check sources whose pages one run reads


def subscriber_only(conn, url: str, fetcher=feeds.fetch) -> bool:
    """A paywall_check source's article that needs a subscription; its page is read once per URL. A page that
    can't be read counts as not free, so nothing behind a paywall slips through (the next run tries again)."""
    if conn.execute("SELECT 1 FROM meta WHERE key = ?", ("paid:" + url,)).fetchone():
        return True
    try:
        paid = not feeds.free_to_read(fetcher(url))
    except Exception:
        return True
    if paid:
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("paid:" + url, _days_ago(0)))
    return paid


def drop_subscriber_only(conn, fetcher=feeds.fetch, log=print) -> int:
    """Stories stored before their outlet's articles were checked for a paywall: read a few pages a run,
    delete the subscriber-only ones and remember the free ones. Returns how many were deleted."""
    names = [s["name"] for s in SOURCES if s.get("paywall_check")]
    if not names:
        return 0
    rows = conn.execute(f"SELECT id, url FROM items WHERE source IN ({','.join('?' * len(names))}) AND url NOT IN "
                        "(SELECT substr(key, 6) FROM meta WHERE key LIKE 'free:%') ORDER BY date DESC",
                        names).fetchall()
    gone = 0
    for it in rows[:PAYWALL_PER_RUN]:
        if subscriber_only(conn, it["url"], fetcher):
            conn.execute("DELETE FROM items WHERE id = ?", (it["id"],))
            gone += 1
        else:
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", ("free:" + it["url"], _days_ago(0)))
    if gone:
        conn.execute("UPDATE items SET cluster = id WHERE cluster NOT IN (SELECT id FROM items)")  # lead was deleted
        cluster.assign(conn, days=None)
        log(f"  removed {gone} subscriber-only stories")
    conn.commit()
    return gone


def status_report(conn) -> str:
    """A few lines of Markdown for the GitHub run page: size of the feed and failing sources."""
    week = conn.execute("SELECT COUNT(*) FROM items WHERE date >= ?", (_days_ago(7),)).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    failing = [h["name"] for h in store.source_health(conn, [s["url"] for s in SOURCES]) if h["failing"]]
    lines = ["### AI Pulse",
             f"- **Stories:** {total:,} in total, {week:,} from the last 7 days",
             f"- **Failing sources:** {', '.join(failing) if failing else 'none'}"]
    return "\n".join(lines) + "\n"


def source_alert(rows: list[dict]) -> tuple[str, str, str]:
    """(subject, text, html) of the project inbox's note that these sources stopped working: a row each, with how
    long it has failed, when it last worked and why (store.newly_failing)."""
    from html import escape
    when = lambda iso: datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M UTC") if iso else "never"
    n = len(rows)
    subject = f"AI Pulse: {n} source{'s' if n > 1 else ''} stopped working"
    text = [f"{n} source{'s have' if n > 1 else ' has'} failed {store.FAILING_AFTER} or more collections in a row:", ""]
    for r in rows:
        text += [r["name"], f"  failed {r['failures']} runs in a row; last worked {when(r['last_success'])}",
                 f"  {r['last_error'] or 'no error recorded'}", f"  {r['url']}", ""]
    text.append("You'll hear about each source once; it resets when the source works again.")
    cell = 'style="padding:8px 10px;border-bottom:1px solid #e3e5e8;vertical-align:top;font-size:14px"'
    html = ('<!doctype html><html><body style="margin:0;padding:16px;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a">'
            f'<p style="font-size:15px">{escape(text[0])}</p>'
            '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;max-width:680px">'
            + '<tr>' + "".join(f'<th align="left" {cell}>{h}</th>' for h in ("Source", "Failed runs", "Last worked", "Why")) + '</tr>'
            + "".join(f'<tr><td {cell}><a href="{escape(r["url"])}" style="color:#1a4fd6">{escape(r["name"])}</a></td>'
                      f'<td {cell}>{r["failures"]}</td><td {cell}>{escape(when(r["last_success"]))}</td>'
                      f'<td {cell}>{escape(r["last_error"] or "no error recorded")}</td></tr>' for r in rows)
            + f'</table><p style="font-size:13px;color:#5f6368">{escape(text[-1])}</p></body></html>')
    return subject, "\n".join(text), html


def fill_summary(item: dict) -> None:
    """Give a story whose feed has no description a short draft from its category, places and tags."""
    if not item["summary"]:
        item["summary"] = brief.draft(item, PLACE_NAMES)


def resummarize(conn, log=print) -> int:
    """Re-clean stored headlines and summaries and fill in headline-only stories. Returns how many changed."""
    changed = 0
    for it in store.query(conn, None, None, None, limit=100000):
        if it.get("bill") or "arxiv.org/abs/" in it["url"]:
            continue  # official records and papers have summaries of their own (bills.py, paper_summary)
        title = brief.clean_title(it["title"], it["source"])
        # Drafts are rebuilt from scratch so they reflect the story's current sorting.
        summary = "" if brief.is_draft(it["summary"]) else brief.clean_summary(it["summary"], title, it["source"])
        updated = {**it, "title": title, "summary": summary}
        fill_summary(updated)
        if (updated["title"], updated["summary"]) != (it["title"], it["summary"]):
            store.update_text(conn, it["id"], updated["title"], updated["summary"])
            changed += 1
            if changed % 25 == 0:
                conn.commit()
                log(f"  {changed} updated")
    conn.commit()
    return changed


def stream_of(src: dict, title: str, summary: str, url: str) -> str:
    """A new story's stream: an infrastructure source's are Infra & climate; an Industry story
    whose headline is about AI's data centres or footprint moves there too (classify.infra_story)."""
    if src["category"] == "infra":
        return "infra"
    category = (blog_category(src, title, summary, url) if src["category"] == "tool"
                else classify.categorize(title, summary, src["category"]))
    if category == "tool" and src.get("no_releases"):
        category = "news"  # a practitioner's commentary on a launch is not the launch (sources.py)
    return "infra" if category == "news" and classify.infra_story(title) else category


def apply_regulation(item: dict, default_jurisdictions: list[str] = ()) -> None:
    """Move a policy story into the regulation tracker when it reports a proposal or an adopted law.

    Needs both one of those actions and at least one jurisdiction; anything else (including
    enforcement, investigations and guidance) stays under "policy".
    """
    if item["category"] not in ("policy", "regulation") or item.get("action") == EXPERT:
        return
    if item.get("source") in bills.OFFICIAL_SOURCES:  # official bill records are sorted by bills.py
        return
    action = classify.regulatory_action(item["title"])
    # A summary that repeats the headline plus the publisher's name can name a country.
    # Generated drafts ("A proposal in the United States and China.") are ignored so they can't feed back.
    summary = "" if item["summary"].startswith(item["title"][:40]) or brief.is_draft(item["summary"]) else item["summary"]
    places = jurisdictions.detect(item["title"], summary, actors_only=True) or list(default_jurisdictions)
    if action in TRACKED_ACTIONS and places:
        places = places[:4]
        if "US" in places:  # which state, for the US-by-state map ("US-OR" next to "US")
            places += [s for s in jurisdictions.us_states(item["title"], summary) if s not in places]
        item.update(category="regulation", action=action, jurisdictions=places)
    else:
        item.update(category="policy", action=None, jurisdictions=[])


RESEARCH_TAG = "Research"  # every academic paper (news about a study gets "Study Report" instead)


def _is_paper(it: dict) -> bool:
    return it["category"] == "research" or "arxiv.org/abs/" in it["url"]


_RENAMED = {"NVIDIA": "Nvidia", "Mistral AI": "Mistral"}


def retag(conn) -> int:
    """Recompute keyword tags (companies, places, topics) for stored stories. Papers and expert pieces
    keep their person / company tags, and every paper carries "Research". Returns how many changed."""
    changed = 0
    for it in store.query(conn, None, None, None, limit=100000):
        if it["category"] == "research" or it["action"] == EXPERT:
            # company names as the news tags spell them (papers stored as "NVIDIA", "Mistral AI")
            tags = list(dict.fromkeys(_RENAMED.get(t, t) for t in it["tags"]))
            if _is_paper(it) and RESEARCH_TAG not in tags:
                tags.append(RESEARCH_TAG)
            if tags != it["tags"]:
                store.set_tags(conn, it["id"], tags)
                changed += 1
            continue
        text = "" if brief.is_draft(it["summary"]) else it["summary"]
        tags = classify.tags_for(it["title"], text, source=it["source"])
        if tags != it["tags"]:
            store.set_tags(conn, it["id"], tags)
            changed += 1
    conn.commit()
    return changed


SUMMARIES = "2"  # bump when brief.clean_summary changes: stored stories are re-cleaned once on the next run
ARXIV_API = "http://export.arxiv.org/api/query"
PAPER_BATCH = 100  # papers per arXiv API request; one request every 3.5 s, as arXiv asks


def fill_page_leads(conn, fetcher=feeds.fetch, limit: int = 150, log=print) -> int:
    """Stored posts from `page_lead` sources that have no summary (or only a draft): read each page's opening
    paragraph, once, a page a second and `limit` per run, in order until all are done. Returns how many filled."""
    names = [s["name"] for s in SOURCES if s.get("page_lead")]
    done = conn.execute("SELECT value FROM meta WHERE key = 'page_leads_filled'").fetchone()
    rows = conn.execute(f"SELECT rowid, id, url, title, source, summary FROM items WHERE source IN ({','.join('?' * len(names))})"
                        " AND rowid > ? ORDER BY rowid", (*names, int(done[0]) if done else 0)).fetchall()
    rows = [r for r in rows if not r["summary"] or brief.is_draft(r["summary"])][:limit]
    filled = 0
    for r in rows:
        try:
            summary = brief.clean_summary(feeds.article_lead(fetcher(r["url"])), r["title"], r["source"])
        except Exception:
            summary = ""
        if summary:
            conn.execute("UPDATE items SET summary = ? WHERE id = ?", (summary, r["id"]))
            filled += 1
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('page_leads_filled', ?)", (str(r["rowid"]),))
        conn.commit()
        time.sleep(1)
    if rows:
        log(f"  opening paragraphs: {filled} of {len(rows)} posts summarised")
    return filled


def resummarize_papers(conn, fetcher=feeds.fetch, limit: int = 3000, log=print) -> int:
    """Rewrite stored papers' summaries with brief.paper_summary, reading their full abstracts again from the
    arXiv API (earlier summaries were the abstract's first lines, cut short). A few thousand per run, in order,
    until all are done. Returns how many were updated."""
    done = conn.execute("SELECT value FROM meta WHERE key = 'papers_resummarized'").fetchone()
    after = int(done[0]) if done else 0
    rows = conn.execute("SELECT rowid, id, url, title FROM items WHERE url LIKE 'https://arxiv.org/abs/%' AND rowid > ?"
                        " ORDER BY rowid LIMIT ?", (after, limit)).fetchall()
    changed = 0
    for i in range(0, len(rows), PAPER_BATCH):
        batch = rows[i:i + PAPER_BATCH]
        ids = {re.sub(r"v\d+$", "", r["url"].rsplit("/abs/", 1)[1]): r for r in batch}
        try:
            entries = feeds.parse(fetcher(f"{ARXIV_API}?id_list={','.join(ids)}&max_results={len(ids)}"))
        except Exception as exc:
            log(f"  ! arXiv abstracts: {exc}")
            break
        for e in entries:
            r = ids.get(re.sub(r"v\d+$", "", e["url"].rsplit("/abs/", 1)[-1]))
            summary = brief.paper_summary(e["summary"], r["title"]) if r else ""
            if summary:
                conn.execute("UPDATE items SET summary = ? WHERE id = ?", (summary, r["id"]))
                changed += 1
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('papers_resummarized', ?)", (str(batch[-1]["rowid"]),))
        conn.commit()
        time.sleep(3.5)
    if rows:
        log(f"  arXiv abstracts: {changed} paper summaries rewritten")
    return changed


# Feeds once taken whole as AI-only whose AI sections turned out to carry other science too (quantum computing,
# physics): their stored stories must name AI, like everything they send from now on (sources.py).
AI_RECHECKED = ("ScienceDaily", "Tech Xplore")


LEADS_PER_RUN = 20  # stored headline-only releases whose pages one run reads


def reclassify(conn, fetcher=feeds.fetch) -> int:
    """Re-run the sorting and regulation rules over stored policy and regulation stories.
    Returns how many changed."""
    changed = 0
    lead_sources = {s["name"] for s in SOURCES if s.get("page_lead")}
    # Stories stored with mojibake ("Peopleâ€™s"), before collection repaired it (feeds.unmangle).
    for it in conn.execute("SELECT id, source, title, summary FROM items").fetchall():
        title, summary = feeds.unmangle(it["title"]), feeds.unmangle(it["summary"] or "")
        # MSIT summaries stored with the page's invisible byte-order mark and its "- " bullet
        title, summary = title.replace("\ufeff", ""), summary.replace("\ufeff", "")
        if it["source"] in lead_sources and summary.startswith("- "):
            summary = summary[2:]
        if (title, summary) != (it["title"], it["summary"] or ""):
            store.update_text(conn, it["id"], title, summary)
            store.set_tags(conn, it["id"], classify.tags_for(title, summary, source=it["source"]))
            changed += 1
    # Releases stored as a headline only, before their source's pages were read for their opening (a "page_lead"
    # source with its own reader, feeds.LEAD_READERS): read now, a few a run.
    readers = {s["name"]: feeds.LEAD_READERS[s["format"]] for s in SOURCES
               if s.get("page_lead") and s.get("format") in feeds.LEAD_READERS}
    bare = [it for it in conn.execute(f"SELECT id, source, url, title, summary FROM items WHERE source IN "
                                      f"({','.join('?' * len(readers))})", list(readers)).fetchall()
            if not it["summary"] or brief.is_draft(it["summary"])] if readers else []
    for it in bare[:LEADS_PER_RUN]:
        try:
            lead = brief.clean_summary(readers[it["source"]](fetcher(it["url"])), it["title"], it["source"])
        except Exception:
            continue
        if lead:
            store.update_text(conn, it["id"], it["title"], lead)
            store.set_tags(conn, it["id"], classify.tags_for(it["title"], lead, source=it["source"]))
            changed += 1
    # Stories stored before collection translated them (a Japanese headline, a Spanish press item), and feeds'
    # "also in French" lines: English now, where the offline translator can do it.
    for it in conn.execute("SELECT id, source, url, title, summary FROM items").fetchall():
        summary = it["summary"] or ""
        if _OTHER_EDITIONS.search(summary) or translate.detect(it["title"]) or translate.detect(summary):
            title, new_summary, url = in_english(conn, it["title"], summary, it["url"], it["source"], feeds.fetch)
            if (title, new_summary, url) != (it["title"], summary, it["url"]):
                store.update_text(conn, it["id"], title, new_summary)
                conn.execute("UPDATE items SET url = ? WHERE id = ?", (url, it["id"]))  # the English version
                store.set_tags(conn, it["id"], classify.tags_for(title, new_summary, source=it["source"]))
                changed += 1
    for it in conn.execute(f"SELECT id, title, summary FROM items WHERE source IN ({','.join('?' * len(AI_RECHECKED))})",
                           AI_RECHECKED).fetchall():
        if not classify.is_ai_related(it["title"], "" if brief.is_draft(it["summary"]) else it["summary"]):
            conn.execute("DELETE FROM items WHERE id = ?", (it["id"],))
            changed += 1
    # The same fallback places collection uses (e.g. Korea's ministry: "KR" when a story names none).
    defaults = {s["name"]: s.get("jurisdictions", []) for s in SOURCES}
    streams = {s["name"]: s["category"] for s in SOURCES}
    by_name = {s["name"]: s for s in SOURCES}
    government = {s["name"] for s in SOURCES if s.get("government")}
    for it in store.query(conn, None, None, None, limit=100000):
        if it["source"] in government and it["action"] != INCIDENT and it["category"] in ("news", "tool"):
            # A government's own publication is Policy (or the tracker, for a bill or law), never Industry.
            before = (it["category"], it["jurisdictions"], it["action"] or None)
            it["category"] = "policy"
            apply_regulation(it, defaults.get(it["source"], []))
            store.set_regulation(conn, it["id"], it["category"], it["jurisdictions"], it["action"])
            if brief.is_draft(it["summary"]):  # "Industry news about ..." names the old stream
                store.update_text(conn, it["id"], it["title"], brief.draft(it, PLACE_NAMES))
            changed += (it["category"], it["jurisdictions"], it["action"]) != before
            continue
        if it["action"] == EXPERT:  # a scholar's paper is research, not a regulatory action
            store.set_regulation(conn, it["id"], "research", [], None)
            changed += 1
            continue
        if it["action"] == INCIDENT:  # a confirmed AI incident stays under Industry
            if it["category"] != "news":
                store.set_regulation(conn, it["id"], "news", [], INCIDENT)
                changed += 1
            continue
        if it["category"] == "infra" and streams.get(it["source"]) != "infra" and not classify.infra_story(it["title"]):
            store.set_regulation(conn, it["id"], "news", it["jurisdictions"], it["action"] or None)  # the rule changed
            changed += 1
            continue
        if it["category"] in ("news", "tool"):
            # A news outlet's "release" that launched nothing (e.g. a study's findings) moves to industry news.
            # Only that check is re-run: summaries are shorter now, so re-scoring would drop real releases.
            text = "" if brief.is_draft(it["summary"]) else it["summary"]
            now = it["category"]
            if it["category"] == "tool" and by_name.get(it["source"], {}).get("no_releases"):
                now = "news"  # a practitioner's or evaluator's post is never a release (sources.py)
            elif it["category"] == "tool" and classify.about_standards(it["title"]):
                # What a standards body publishes or starts is policy or industry news, not a release.
                now = classify.categorize(it["title"], text, "news")
            elif it["category"] == "tool" and streams.get(it["source"]) == "news" and not classify.launched(it["title"], text):
                now = "news"
            # A company blog's post is a release only when it launches something (classify.released), either way:
            # a post whose opening paragraph arrives later (fill_page_leads) can turn out to be a launch.
            elif streams.get(it["source"]) == "tool" and blog_category(by_name[it["source"]], it["title"], text, it["url"]) in ("news", "tool"):
                now = blog_category(by_name[it["source"]], it["title"], text, it["url"])
            if now == "news" and classify.infra_story(it["title"]):
                now = "infra"  # Industry news about AI's data centres or footprint, back to 2023 (collect.stream_of)
            if now != it["category"]:
                store.set_regulation(conn, it["id"], now, it["jurisdictions"], it["action"] or None)
                if brief.is_draft(it["summary"]):  # "A release, involving Mistral." names the old stream
                    store.update_text(conn, it["id"], it["title"], brief.draft({**it, "category": now}, PLACE_NAMES))
                changed += 1
            continue
        if it["category"] not in ("policy", "regulation"):
            continue
        before = (it["category"], it["jurisdictions"], it["action"] or None)
        if it["category"] == "policy" and it["source"] not in bills.OFFICIAL_SOURCES and it["source"] not in government:
            # A story only reaches "policy" from a policy feed or by scoring as policy, so re-sorting
            # with "policy" as the default drops the ones a policy search picked up by mistake.
            text = "" if brief.is_draft(it["summary"]) else it["summary"]
            it["category"] = classify.categorize(it["title"], text, "policy")
            if it["category"] != "policy":
                store.set_regulation(conn, it["id"], it["category"], [], None)
                if brief.is_draft(it["summary"]):  # "A proposal in Nigeria." named the old stream
                    store.update_text(conn, it["id"], it["title"], brief.draft({**it, "action": None}, PLACE_NAMES))
                changed += 1
                continue
        apply_regulation(it, defaults.get(it["source"], []))
        if (it["category"], it["jurisdictions"], it["action"]) != before:
            store.set_regulation(conn, it["id"], it["category"], it["jurisdictions"], it["action"])
            if brief.is_draft(it["summary"]):  # "A proposal in Nigeria." for what is no longer a proposal
                store.update_text(conn, it["id"], it["title"], brief.draft(it, PLACE_NAMES))
            changed += 1
    conn.commit()
    return changed
