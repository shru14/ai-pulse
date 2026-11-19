"""The daily email's own parts, each with an archive page search engines can index: daily/memes/ (every meme of the
day, and on Sunday the meme of the week), daily/words/ (every word of the day or week, linked to its glossary page),
daily/top-news/ (each day's hot story and top news) and daily/companies/ (every company of the day or week). Each
day is picked as that day's poster email picked it for a reader who chose every stream and nothing else, and links
to that day's full edition (daily/<day>.html). Newest first, by month.
"""
from __future__ import annotations

from datetime import date
from html import escape
from pathlib import Path

from . import cluster, companies, digest, glossary, memes, pages, poster, rss

ART = "photos/cartoons/pages/daily.svg"  # the daily editions' own cartoon
# path: (header colour, icon, title, question, intro, page title, description)
ARCHIVES = {
    "memes": ("tool", "M4 4h16v16H4zM4 15l5-5 4 4 3-3 4 4M15 8.5h.01",
              "Meme of the day", "Which memes came with the news?",
              "Every meme of the day from the Pulse Daily email, made from that day's AI headlines. On Sundays, the meme "
              "of the week.", "AI memes of the day, every edition · Pulse Central",
              "Every AI meme of the day from the Pulse Daily email, made from that day's AI news, newest first."),
    "words": ("research", "M4 19.5V5a2 2 0 0 1 2-2h13v16H6.5A2.5 2.5 0 0 0 4 21.5M4 19.5A2.5 2.5 0 0 1 6.5 17H19",
              "Word of the day", "Which AI words came up each day?",
              "Every word of the day from the Pulse Daily email: the hardest AI term in that day's biggest stories, in "
              "plain English, and where it came up. On Sundays, the word of the week.",
              "AI word of the day, every edition · Pulse Central",
              "Every AI word of the day from the Pulse Daily email, explained in plain English, with the story it came up in."),
    "top-news": ("news", "M3 6h18v12H3zM7 10h10M7 14h6",
                 "Top AI news", "What were the biggest AI stories each day?",
                 "Each day's hot story and top news from the Pulse Daily email, ranked by how many outlets reported "
                 "them.", "Top AI news by day, every edition · Pulse Central",
                 "Each day's biggest AI stories from the Pulse Daily email: the hot story and top news, newest first."),
    "companies": ("policy", "M4 21V7l8-4 8 4v14M9 21v-6h6v6M8 10h.01M12 10h.01M16 10h.01",
                  "Company of the day", "Which AI startups stood out?",
                  "Every company of the day from the Pulse Daily email: an AI startup that stood out for its idea, its "
                  "revenue or how it makes money, checked by hand against its story. On Sundays, the company of the week.",
                  "AI startup of the day, every edition · Pulse Central",
                  "Every AI company of the day from the Pulse Daily email: what it does, how it makes money and why it stood out."),
}


def _entries(cards: list[dict], day: date, idf: dict[str, float]) -> dict[str, str]:
    """The day's parts as HTML, by archive (a part the day had none of is left out)."""
    streams = list(rss.FEEDS)
    by_stream = digest._leave_out(digest.by_streams(cards, streams, day), None)[0]
    week = digest.weekly(day)
    out: dict[str, str] = {}
    if not any(by_stream.values()):
        return out
    top, _, stream_of, _, _ = poster.top_news(cards, by_stream, streams, idf=idf)

    # Meme: the picture static.py wrote beside the day's edition
    meme = (memes.of_the_week([c for c in cards if (c.get("date") or "") <= day.isoformat()], digest._span(day)[0])
            if week else memes.of_the_day(cards, day))
    picture = meme and memes.render(meme)
    if meme and picture:
        name = f"{day.isoformat()}-{'week-' * week}meme.{'png' if digest._kind(picture) == 'png' else 'jpg'}"
        alt = " ".join(memes.text(meme)[1:])
        out["memes"] = (f'<p class="lab">Meme of the {"week" if week else "day"}</p>'
                        f'<img src="/daily/{name}" alt="{escape(alt)}" loading="lazy">'
                        f'<p class="meta">Template via imgflip.com</p>')

    # Word: the day's (from the email's biggest stories, then its top news, then any story), or the week's on Sunday
    came = ""
    if week:
        wid = digest._week_word(cards, day)
        e = next((x for x in glossary.ENTRIES if x["id"] == wid), None) if wid else None
    else:
        todays = [c for n in streams for c in by_stream[n]]
        e, story = digest._word_entry(cards, day, streams, None, [digest._biggest(by_stream, streams), top, todays])
        if story:
            came = (f'<p class="meta">Where it came up: <a href="{escape(story["url"])}" rel="noopener">'
                    f'{escape(story["title"])}</a></p>')
    if e:
        out["words"] = (f'<p class="lab">Word of the {"week" if week else "day"}</p>'
                        f'<p class="term"><a href="/glossary/{e["id"]}/">{escape(e["term"])}</a></p>'
                        f'<p class="what">{escape(e["def"])}</p>{came}')

    # Top news: the hot story, then the top news tiles
    if top:
        def row(c: dict) -> str:
            more = digest._outlets(c) - 1
            by = c["source"] + (f" and {more} more outlet{'s' * (more > 1)}" if more else "")
            return (f'<li><a href="{escape(c["url"])}" rel="noopener">{escape(c["title"])}</a>'
                    f'<div class="meta">{escape(rss.FEEDS[stream_of[id(c)]][1])} · {escape(by)}</div></li>')
        out["top-news"] = (f'<p class="lab">Hot today</p><ul>{row(top[0])}</ul>'
                           + (f'<p class="lab">Top news</p><ul>{"".join(row(c) for c in top[1:])}</ul>' if top[1:] else ""))

    # Company: the day's approved profile, or the week's on Sunday
    p: dict | None = None
    if week:
        ranked = companies.of_week(cards, day)
        if ranked:
            p, outlets, seen, picks, rule = ranked
            why = f'{p["why"]}. {p["because"]} {companies.why_week(outlets, seen, picks, rule)}'
    else:
        p = companies.of_day(day)
        why = f'{p["why"]}. {p["because"]}' if p else ""
    if p:
        rows = [("What it does", p["does"]), ("How it makes money", p["money"]), ("The number", p["number"]),
                ("Why it's here", why)]
        out["companies"] = (f'<p class="lab">Company of the {"week" if week else "day"}</p>'
                            f'<p class="term">{escape(p["name"])}</p><table><tbody>'
                            + "".join(f'<tr><th scope="row">{escape(k)}</th><td>{escape(v)}</td></tr>' for k, v in rows)
                            + f'</tbody></table><p class="meta">{escape(p["source"])} · '
                              f'<a href="{escape(poster.clean_url(p["url"]))}" rel="noopener">Read the story</a></p>')
    return out


def _links(here: str) -> str:
    """The other archives, as boxed links (the back link above the heading opens every edition)."""
    boxes = [(f"/daily/{p}/", a[2]) for p, a in ARCHIVES.items() if p != here]
    return '<nav class="places one" aria-label="Daily archives">' + "".join(
        f'<a href="{u}">{escape(w)}</a>' for u, w in boxes) + "</nav>\n"


def build(conn, cards: list[dict], days: list[date], total: int, out: Path) -> list[str]:
    """Write the four archive pages under daily/. Returns their paths (for the sitemap)."""
    found: dict[str, list[tuple[date, str]]] = {p: [] for p in ARCHIVES}
    idf = cluster.idf_weights(cards)  # once, not once a day
    for d in sorted(days, reverse=True):
        for p, html in _entries(cards, d, idf).items():
            found[p].append((d, html))
    paths = []
    for p, (colour, icon, title, question, intro, page_title, description) in ARCHIVES.items():
        months: dict[str, list[str]] = {}
        for d, html in found[p]:
            sunday = " · Sunday's email" if digest.weekly(d) else ""
            months.setdefault(f"{d:%B %Y}", []).append(
                f'<section class="arc"><h3><a href="/daily/{d.isoformat()}.html">{digest.long_day(d)}</a>'
                f'<span class="meta">{sunday}</span></h3>{html}</section>')
        body = (pages.band(colour, icon, ART, title, question,
                           escape(intro) + ' <a href="/#subscribe">Get it in your inbox</a>')
                + _links(p)
                + ("".join(f'<h2>{m}</h2>\n' + "\n".join(rows) for m, rows in months.items())
                   or '<p class="intro">Nothing here yet.</p>'))
        path = f"daily/{p}/"
        data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": page_title.split(" · ")[0],
                "description": description, "url": f"{rss.SITE}{path}",
                "isPartOf": {"@type": "WebSite", "name": "Pulse Central", "url": rss.SITE}}
        (out / path).mkdir(parents=True, exist_ok=True)
        (out / path / "index.html").write_text(pages.page(page_title, description, path, body, data,
                                                          pages.frame(conn, total), ("/daily/", "Every daily edition")),
                                               encoding="utf-8")
        paths.append(path)
    return paths
