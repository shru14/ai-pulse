"""Industry's kinds of story, a page each (industry/<kind>/): its opinion and analysis, company blogs, studies,
AI-incidents, tutorials and events, the front page's Industry strip linking to them. The stories are the outlets'
own headlines, so each page loads them in the reader's browser from data.json (the last 3 months), as the
glossary's word pages do; the page itself holds only our own words. No date of its own.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from . import digest, pages, rss

# kind (classify.news_kind): (address under industry/, heading, what's on the page)
KINDS = {
    "analysis": ("opinion", "AI opinion and analysis", "Columns, essays and analysis on AI: what's being said about it, "
                 "beyond the news."),
    "blog": ("company-blogs", "AI company blogs", "What AI companies post on their own blogs besides launches: "
             "partnerships, customer stories and how they work."),
    "study": ("studies", "AI studies and reports", "News of what surveys, studies and reports on AI found."),
    "incident": ("ai-incidents", "AI incidents", "When AI went wrong: news reports of harms and failures, each one "
                 "the AI Incident Database records."),
    "tutorial": ("tutorials", "AI tutorials", "How-to guides and walkthroughs for building and using AI."),
    "event": ("events", "AI events", "AI conferences, summits and meetups, and what happened at them."),
}

STORIES_JS = r"""<script>
(() => {
  const ul = document.getElementById("kind-stories"), more = document.getElementById("more-stories");
  const day = d => new Date(d.slice(0, 10) + "T00:00:00Z").toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"});
  const note = text => { const li = document.createElement("li"); li.className = "meta"; li.textContent = text; ul.replaceChildren(li); };
  let list = [], shown = 0;
  const show = () => {
    list.slice(shown, shown += 20).forEach(c => {
      const li = document.createElement("li"), a = document.createElement("a"), meta = document.createElement("div");
      a.href = c.url; a.rel = "noopener"; a.textContent = c.title.trim();
      meta.className = "meta"; meta.textContent = [day(c.date), c.source].filter(Boolean).join(" · ");
      li.append(a, meta); ul.append(li);
    });
    more.hidden = shown >= list.length;
  };
  fetch("/data.json", {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(d => {
    list = d.cards.filter(c => c.category === "news" && c.kind === ul.dataset.kind)
      .sort((a, b) => a.date < b.date ? 1 : a.date > b.date ? -1 : 0);
    document.getElementById("stories-count").textContent = list.length + (list.length === 1 ? " story" : " stories");
    if(!list.length) return note("None in the last 3 months.");
    ul.replaceChildren(); show();
  }).catch(() => note("Couldn't load the stories. Try reloading the page."));
  more.addEventListener("click", show);
})();
</script>"""


def path(kind: str) -> str:
    return f"industry/{KINDS[kind][0]}/"


def build(conn, total: int, out: Path) -> list[str]:
    """Write a page per kind. Returns their paths."""
    parts = pages.frame(conn, total)
    back = ("/industry/", "Back to Industry")
    others = " · ".join(f'<a href="/{path(k)}">{escape(digest.KIND[k][0])}</a>' for k in KINDS)
    paths = []
    for kind, (_, heading, what) in KINDS.items():
        p = path(kind)
        body = (f'<h1>{escape(heading)}</h1>\n<p class="intro">{escape(what)}</p>\n'
                f'<p class="intro"><span id="stories-count">The stories</span> in the last 3 months, newest first, '
                f'each linking to the outlet\'s own page.</p>\n'
                f'<ul id="kind-stories" data-kind="{kind}"><li class="meta">Loading the stories…</li></ul>\n'
                f'<button type="button" class="more-stories" id="more-stories" hidden>Show more stories</button>\n'
                f'{STORIES_JS}')
        data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": heading, "description": what,
                "url": f"{rss.SITE}{p}"}
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "index.html").write_text(pages.page(f"{heading} · AI Pulse", what, p, body, data, parts, back,
                                                       f"More from Industry: {others}"), encoding="utf-8")
        paths.append(p)
    return paths
