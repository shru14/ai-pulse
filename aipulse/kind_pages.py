"""Industry's kinds of story, a page each (industry/<kind>/): its opinion and analysis, company blogs, studies,
AI-incidents, tutorials and events, the front page's Industry strip linking to them. The stories are the outlets'
own headlines, so each page loads them in the reader's browser from data.json (the last 3 months), as the
glossary's word pages do; the page itself holds only our own words. No date of its own. Company blogs are
grouped by company, a tile each with its logo, like the tracker's places with their flags.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

from . import brands, classify, digest, pages, rss
from .server import TEMPLATE

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
  const tiles = document.getElementById("companies"), firms = tiles ? JSON.parse(document.getElementById("firms").textContent) : null;
  const firm = src => (firms && firms.of[src]) || src;
  let all = [];
  const day = d => new Date(d.slice(0, 10) + "T00:00:00Z").toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"});
  const note = text => { const li = document.createElement("li"); li.className = "meta"; li.textContent = text; ul.replaceChildren(li); };
  let list = [], shown = 0;
  // Company blogs: a tile per company (its logo, else its initial); a tile shows only that company's posts
  const pick = name => {
    list = name ? all.filter(c => firm(c.source) === name) : all;
    tiles.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.firm === name));
    ul.replaceChildren(); shown = 0; show();
  };
  const buildTiles = () => {
    const count = {};
    all.forEach(c => count[firm(c.source)] = (count[firm(c.source)] || 0) + 1);
    const tile = (name, n) => {
      const b = document.createElement("button"), mark = document.createElement("span"), label = document.createElement("span");
      b.type = "button"; b.dataset.firm = name;
      mark.className = "logo"; mark.setAttribute("aria-hidden", "true");
      if(!name) mark.textContent = "∗";
      else if(firms.logo[name]) mark.innerHTML = firms.logo[name];  // fixed markup from our build, never story text
      else mark.textContent = name[0];
      label.textContent = name || "All companies";
      const num = document.createElement("small"); num.textContent = n;
      b.append(mark, label, num); b.addEventListener("click", () => pick(name));
      return b;
    };
    tiles.replaceChildren(tile("", all.length), ...Object.keys(count).sort((a, b) => count[b] - count[a] || a.localeCompare(b)).map(n => tile(n, count[n])));
  };
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
    list = all = d.cards.filter(c => c.category === "news" && c.kind === ul.dataset.kind)
      .sort((a, b) => a.date < b.date ? 1 : a.date > b.date ? -1 : 0);
    document.getElementById("stories-count").textContent = list.length + (list.length === 1 ? " story" : " stories");
    if(!list.length) return note("None in the last 3 months.");
    if(tiles) return (buildTiles(), pick(""));
    ul.replaceChildren(); show();
  }).catch(() => note("Couldn't load the stories. Try reloading the page."));
  more.addEventListener("click", show);
})();
</script>"""


_SUFFIX = re.compile(r"\s+(?:Blog|News|Newsroom)\b.*$")


def company(source: str) -> str:
    """The company behind a blog: one of the companies we tag ("Google Research Blog", "Engineering at Meta"),
    else the source's name without "Blog" or "News" ("Cloudflare Blog" -> Cloudflare)."""
    for name, rx in classify._companies.items():
        if rx.search(source):
            return name
    return _SUFFIX.sub("", source)


def _front_logos() -> dict[str, str]:
    """The front page's colour logos for the big AI companies (its LOGOS table)."""
    m = re.search(r"const LOGOS = (\{.*?\n\});", TEMPLATE.read_text(encoding="utf-8"), re.S)
    return json.loads(re.sub(r",\s*\}$", "}", m.group(1))) if m else {}


def _dark(hex_: str) -> str:
    """Logo tiles are white, so very light brand colours use the text colour instead (as on the front page)."""
    r, g, b = (int(hex_[i:i + 2], 16) for i in (0, 2, 4))
    return hex_ if (.299 * r + .587 * g + .114 * b) / 255 <= .8 else "141925"


def logos(names) -> dict[str, str]:
    """An SVG logo per company: the front page's, else Simple Icons' in its brand colour. None: its initial."""
    front, si, out = {k.lower(): v for k, v in _front_logos().items()}, brands.si_index(), {}
    for name in names:
        if name.lower() in front:
            out[name] = front[name.lower()]
            continue
        brand = si.get(name)
        d = brand and brands.si_path(brand["slug"])
        if d:
            out[name] = f'<svg viewBox="0 0 24 24"><path fill="#{_dark(brand["hex"])}" d="{escape(d)}"/></svg>'
    return out


def path(kind: str) -> str:
    return f"industry/{KINDS[kind][0]}/"


def build(conn, cards: list[dict], out: Path) -> list[str]:
    """Write a page per kind. Returns their paths."""
    parts = pages.frame(conn, len(cards))
    of = {s: company(s) for s in sorted({c["source"] for c in cards if c.get("kind") == "blog"})}
    firms = json.dumps({"of": of, "logo": logos(set(of.values()))}).replace("</", "<\\/")
    back = ("/industry/", "Back to Industry")
    others = " · ".join(f'<a href="/{path(k)}">{escape(digest.KIND[k][0])}</a>' for k in KINDS)
    paths = []
    for kind, (_, heading, what) in KINDS.items():
        p = path(kind)
        body = (f'<h1>{escape(heading)}</h1>\n<p class="intro">{escape(what)}</p>\n'
                f'<p class="intro"><span id="stories-count">The stories</span> in the last 3 months, newest first, '
                f'each linking to the outlet\'s own page.</p>\n'
                + (f'<div class="places companies" id="companies"></div>\n'
                   f'<script type="application/json" id="firms">{firms}</script>\n' if kind == "blog" else "")
                + f'<ul id="kind-stories" data-kind="{kind}"><li class="meta">Loading the stories…</li></ul>\n'
                f'<button type="button" class="more-stories" id="more-stories" hidden>Show more stories</button>\n'
                f'{STORIES_JS}')
        data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": heading, "description": what,
                "url": f"{rss.SITE}{p}"}
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "index.html").write_text(pages.page(f"{heading} · AI Pulse", what, p, body, data, parts, back,
                                                       f"More from Industry: {others}"), encoding="utf-8")
        paths.append(p)
    return paths
