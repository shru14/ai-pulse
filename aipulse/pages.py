"""The site's plain pages for search engines (the tracker by country, the glossary): the front page's own masthead
and footer around them, and one stylesheet, site.css (the front page's styles and these pages'), so each page stays
small. Nothing on them needs JavaScript but the masthead's time in the reader's time zone.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path

from . import rss, store
from .server import TEMPLATE

# the pages' own styles, in their own file so an editor reads them as CSS; site.css is built from them (write_css)
STYLE = Path(__file__).with_name("pages.css").read_text(encoding="utf-8")


def phone_type(css: str, scale: float = .85, floor: float = 11) -> str:
    """Every page's type the same size smaller on phones: each `.cp` rule's font size of 14px or more, scaled down
    (a clamp() by its smallest size), in one ≤640px block. Rules a phone block already sizes keep theirs; search
    boxes keep 16px (smaller makes iPhones zoom in on a tap)."""
    rules, tuned, depth, media = [], set(), 0, ""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for m in re.finditer(r"([^{}]*)\{|\}", css):
        if m.group(0) == "}":
            depth -= 1
            if depth == 0:
                media = ""
            continue
        head = m.group(1).strip()
        if head.startswith("@media"):
            media, depth = head, depth + 1
            continue
        body, depth = css[m.end():css.index("}", m.end())], depth + 1
        for sel in (s.strip() for s in head.split(",")):
            if "max-width" in media and "font" in body:
                tuned.add(sel)
            elif not media:
                rules.append((sel, body))
    sizes = {}
    for sel, body in rules:
        f = re.search(r"font(?:-size)?\s*:[^;]*?(?:clamp\()?(\d+(?:\.\d+)?)px", body)
        if not (sel.startswith(".cp ") and f) or sel in tuned or re.search(r"input|select|search|::?(?:before|after)", sel):
            continue
        if (px := float(f.group(1))) >= 14:
            sizes[sel] = f"{max(floor, round(px * scale * 2) / 2):g}px"
    return "@media (max-width:640px){\n" + "\n".join(f"  {s}{{font-size:{v}}}" for s, v in sizes.items()) + "\n}\n"


def write_css(out: Path) -> None:
    """site.css: the front page's styles (its masthead and footer) and these pages' own, then these pages' type a size
    smaller on phones."""
    style = re.search(r"<style>(.*?)</style>", TEMPLATE.read_text(encoding="utf-8"), re.S).group(1)
    (out / "site.css").write_text(style + STYLE + phone_type(STYLE), encoding="utf-8")


def frame(conn=None, total: int = 0) -> tuple[str, str]:
    """The front page's masthead (no stream links; Subscribe and Glossary open on the front page) and footer. Without
    a database (the privacy page) the masthead leaves out the story count and last update."""
    t = TEMPLATE.read_text(encoding="utf-8")
    last = ((store.last_run(conn) or {}).get("ran_at") or "") if conn else ""
    header = re.search(r'<header class="top home">.*?</header>', t, re.S).group(0)
    header = re.sub(r"\s*<!-- Each stream.*?</nav>", "", header, flags=re.S)
    header = re.sub(r'<button class="(subscribe-btn[^"]*)" id="(\w+)-open" type="button" aria-haspopup="dialog"',
                    r'<a class="\1" href="/#\2"', header).replace("</button>", "</a>")
    # one line, as on the front page: when it last updated and how often (pages.yml)
    when = (f'<div>Updated <time datetime="{escape(last)}">{escape(last[:16].replace("T", " "))} UTC</time>'
            ' · every 6 hours</div>' if last else "")
    header = header.replace("Loading feed…", when)
    footer = re.search(r'<footer class="site-foot">.*?</footer>', t, re.S).group(0)
    return header, footer


# dark or light before the first paint, and the masthead's moon button, as on the front page
THEME = ('<script>try{document.documentElement.dataset.theme=localStorage.getItem("aipulse-theme")||'
         '(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light")}catch(e){}</script>')
THEME_BUTTON = """<script>
(() => {
  const b = document.getElementById("theme-toggle"), root = document.documentElement;
  if(!b) return;
  const show = () => b.setAttribute("aria-pressed", String(root.dataset.theme === "dark"));
  b.addEventListener("click", () => {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    try{ localStorage.setItem("aipulse-theme", root.dataset.theme); }catch(e){}
    show();
  });
  try{ matchMedia("(prefers-color-scheme: dark)").addEventListener("change", e => {
    if(localStorage.getItem("aipulse-theme")) return;
    root.dataset.theme = e.matches ? "dark" : "light"; show();
  }); }catch(e){}
  show();
})();
</script>"""

# the masthead's time in the reader's own time zone, as on the front page
LOCAL_TIME = ('<script>document.querySelectorAll("time[datetime]").forEach(t => t.textContent = new Date(t.dateTime)'
              '.toLocaleString(undefined,{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}));'
              # the nameplate's date line: today's date, as on the front page
              # in its own block: a sealed page writes the page into the login box's window, so this script runs
              # twice there and a top-level const would be declared twice
              '{const npd=document.getElementById("np-date");if(npd)npd.textContent=new Date().toLocaleDateString("en-GB",'
              '{weekday:"long",day:"numeric",month:"long",year:"numeric"})}'
              # the sticky masthead's real height on wide screens, so the timeline's years stick just under it
              '{const m=document.querySelector("header.top"),w=matchMedia("(min-width:701px)"),f=()=>{if(m&&w.matches)'
              'document.documentElement.style.setProperty("--bar-h",m.offsetHeight+"px")};'
              'try{new ResizeObserver(f).observe(m)}catch(e){addEventListener("resize",f)}f()}</script>')


# Anonymous visit counts (GoatCounter, chosen 12 Oct 2026; terms.PLATFORM): no cookie, no stored IP address or
# ID. Only the page's path is sent, never its query or the #codes in sign-up links. Empty = no counter.
GOATCOUNTER = "ai-pulse"


def counter() -> str:
    """The visit counter's script for the published site's pages (nothing while GOATCOUNTER is empty)."""
    return (f'<script>window.goatcounter={{path:location.pathname}}</script><script data-goatcounter='
            f'"https://{GOATCOUNTER}.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>'
            if GOATCOUNTER else "")


def snippet(text: str, limit: int = 160) -> str:
    """A description short enough for a search result (they cut near 160 characters): whole words, then "…"."""
    return text if len(text) <= limit else text[:limit - 1].rsplit(" ", 1)[0].rstrip(",;:·—- ") + "…"


# Each feature's stream colour and its icon (the ones on the front page's Features panels). A new feature adds its row
# here and starts its page with feature_head(): its name, a one-line question and what it covers.
FEATURES = {
    "rule-echoes/": ("reg", "M4 18a8 8 0 0 1 16 0M7 18a5 5 0 0 1 10 0M10 18a2 2 0 0 1 4 0"),
    "harm-to-rule/": ("reg", "M12 3.5l9.5 17h-19zM12 10v5M12 17.8v.2"),
    "ai-fines-and-bans/": ("reg", "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M5.6 5.6l12.8 12.8"),
    "ai-in-court/": ("reg", "M12 4v16M8 20h8M5 7h14M5 7l-3 6.5a3 3 0 0 0 6 0zM19 7l-3 6.5a3 3 0 0 0 6 0z"),
    "promises/": ("news", "M4 5h16v14H4zM8 12l3 3 5-6"),
    "jobs-blamed-on-ai/": ("news", "M4 8h16v11H4zM9 8V5h6v3M4 13h16"),
    "who-owns-a-piece-of-whom/": ("news", "M4 5h16v14H4zM4 10h16M10 5v14"),
    "ai-buyouts/": ("news", "M2 4h3l2.5 11h11L21 7H6.2M9.5 19.5h.01M17 19.5h.01"),
    "models-being-retired/": ("tool", "M12 7v5l3 2M3.5 12a8.5 8.5 0 1 0 2.5-6M3 4v4h4"),
    "release-cards/": ("tool", "M4 4h16v16H4zM4 9h16M9 9v11"),
    "ai-safety-hub/": ("policy", "M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"),
    "ai-consultations/": ("policy", "M4 5h16v11H9l-5 4zM8 9h8M8 12h5"),
    "papers-in-the-news/": ("research", "M4 5h12v14H6a2 2 0 0 1-2-2zM16 9h4v8a2 2 0 0 1-2 2h-2M7.5 9h5M7.5 12.5h5M7.5 16h3"),
    "new-tests-for-ai/": ("research", "M9 4h6v3H9zM7 5.5H5V20h14V5.5h-2M8.5 13l2.5 2.5 4.5-4.5"),
    "compute-behind-notable-models/": ("research", "M4 20h16M4 20V4M8 16.5v.01M11.5 13v.01M15 9.5v.01M18.5 6v.01"),
    "who-publishes-ai-research/": ("research", "M4 20V9h4v11M10 20V5h4v15M16 20v-8h4v8M3 20h18"),
    "lab-timelines/": ("tool", "M3 6h18M3 12h18M3 18h18M8 4v4M15 10v4M11 16v4"),
    "model-economy/": ("tool", "M12 3v18M16.5 7.5c0-1.7-2-3-4.5-3s-4.5 1.3-4.5 3 2 2.6 4.5 3 4.5 1.3 4.5 3-2 3-4.5 3-4.5-1.3-4.5-3"),
    "ai-pacts-and-orders/": ("policy", "M7 4h10v16H7zM10 8h4M10 11.5h4M9.5 16l1.5 1.5 3-3"),
    "government-ai-use/": ("policy", "M4 21h16M6 18v-8M10 18v-8M14 18v-8M18 18v-8M3 10l9-6 9 6z"),
    "data-centre-builds/": ("infra", "M4 20V9h9v11M13 20V4h7v16M3 20h18M7 12.5h3M7 16h3M16 8h1M16 12h1M16 16h1"),
    "who-powers-ai/": ("infra", "M13 3L5 14h6l-1 7 8-11h-6z"),
    "pushback-and-permits/": ("infra", "M5 4h14v11H5zM9 15v5M15 15v5M8 8h8M8 11h5"),
    "chip-export-rules/": ("infra", "M7 7h10v10H7zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"),
}


def cite(path: str, title: str) -> str:
    """A feature's "Cite this" box: one citation with the page's address and the day it was built, and a Copy button."""
    day = datetime.now(timezone.utc)
    text = f'AI Pulse. "{title}." {rss.SITE}{path} (data as of {day.day} {day:%b %Y}).'
    return (f'<details class="fh-cite"><summary>Cite this</summary><div class="fh-cite-box"><p>{escape(text)}</p>'
            '<p class="fh-cite-src">Quoting one row? Cite the source linked in that row as well.</p>'
            '<button type="button" onclick="navigator.clipboard.writeText(this.parentNode.firstChild.textContent)'
            '.then(()=>{this.textContent=&quot;Copied&quot;})">Copy</button>'
            '<button type="button" class="fh-cite-x" aria-label="Close" onclick="this.closest(&quot;details&quot;).open=false">&times;</button>'
            '</div></details>'
            # Close it too on a click outside the box or on Esc
            '<script>document.addEventListener("click",e=>document.querySelectorAll(".fh-cite[open]").forEach(d=>{if(!d.contains(e.target))d.open=false}));'
            'document.addEventListener("keydown",e=>{if(e.key==="Escape")document.querySelectorAll(".fh-cite[open]").forEach(d=>d.open=false)});'
            # phones show a table's row as a card: each cell is labelled with its column's heading (data-l), and a long
            # one runs the card's width
            'addEventListener("DOMContentLoaded",()=>document.querySelectorAll(".ft table.mt,.ft table.fx-t").forEach(t=>{'
            'const h=[...t.querySelectorAll("thead th")].map(x=>x.textContent.trim());if(!h.length)return;'
            't.querySelectorAll("tbody tr").forEach(r=>[...r.children].forEach((c,i)=>{'
            'if(i&&h[i]&&!c.dataset.l)c.dataset.l=h[i];if(c.textContent.trim().length>38)c.classList.add("wd")}))}))</script>')


def band(colour: str, icon: str, art: str, title: str, question: str, intro: str, extra: str = "", sub: str = "") -> str:
    """Every page's header band: `colour` a stream's key (--f-<colour>), `icon` a 24×24 path or ready HTML (a flag,
    a logo), `art` our own cartoon's address, `extra` HTML under the question, `sub` a second name under the title.
    title, question and sub are plain text; intro is HTML."""
    pic = icon.startswith("<")
    ic = icon if pic else f'<svg viewBox="0 0 24 24"><path d="{icon}"/></svg>'
    q = (f'<p class="fh-sub">{escape(sub)}</p>' if sub else "") + (f'<p class="fh-q">{escape(question)}</p>' if question else "")
    return (f'<header class="fh" style="--f:var(--f-{colour})"><div class="fh-t"><span class="fh-ic{" pic" * pic}" '
            f'aria-hidden="true">{ic}</span><div><h1>{escape(title)}</h1>{q}{extra}</div></div>\n'
            f'<p class="fh-d">{intro}</p><img class="fh-art" src="{art}" alt="" aria-hidden="true"></header>\n')


def feature_head(path: str, title: str, question: str, intro: str, sub: str = "") -> str:
    """A feature's header band (the same on every feature). title, question and sub (a second name under the title)
    are plain text; intro is HTML."""
    stream, icon = FEATURES[path]
    return band(stream, icon, f"photos/cartoons/features/{path.strip('/')}.svg", title, question, intro, cite(path, title),
                sub)


def page(title: str, description: str, path: str, body: str, data: dict, parts: tuple[str, str],
         back: tuple[str, str], note: str = "") -> str:
    """A whole page: `back` is (address, words) for the link above the heading, `note` a line under the content."""
    url = f"{rss.SITE}{path}"
    header, footer = parts
    description = snippet(description)
    # class front-page: the front page's newspaper nameplate and date line (index.html's .front-page styles)
    return (f'<!doctype html>\n<html lang="en" class="front-page">\n<head>\n<meta charset="utf-8">\n{THEME}\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<base href="/">\n'
            f'<title>{escape(title)}</title>\n<meta name="description" content="{escape(description)}">\n'
            f'<link rel="canonical" href="{url}">\n<link rel="icon" href="/favicon.ico">\n'
            f'<meta property="og:title" content="{escape(title)}">\n<meta property="og:description" content="{escape(description)}">\n'
            f'<meta property="og:url" content="{url}">\n<meta property="og:image" content="{rss.SITE}og-pulse.png">\n'
            '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n{counter()}'
            f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>\n'
            f'<link rel="stylesheet" href="site.css">\n</head>\n<body>\n<div class="wrap">\n{header}\n<main class="cp">\n'
            f'<a class="back" href="{back[0]}">← {escape(back[1])}</a>\n{body}\n'
            + (f'<p class="note">{note}</p>\n' if note else "")
            + f'</main>\n{footer}\n</div>\n{LOCAL_TIME}\n{THEME_BUTTON}\n</body>\n</html>\n')
