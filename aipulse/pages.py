"""The site's plain pages for search engines (the tracker by country, the glossary): the front page's own masthead
and footer around them, and one stylesheet, site.css (the front page's styles and these pages'), so each page stays
small. Nothing on them needs JavaScript but the masthead's time in the reader's time zone.
"""
from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

from . import rss, store
from .server import TEMPLATE

STYLE = """
.cp{max-width:780px;margin:0 auto;padding-bottom:12px}
.cp .back{display:inline-block;margin-top:24px;font-weight:600;font-size:15px;color:var(--ink);text-decoration:underline;text-decoration-color:#D55E00;text-decoration-thickness:2px;text-underline-offset:4px}
.cp h1{display:flex;align-items:center;gap:16px;font:400 clamp(28px,5vw,40px)/1.1 var(--display);letter-spacing:0;margin:18px 0 8px}
.cp .flag{flex:none;width:32px;height:24px;object-fit:cover;border:1px solid #000}
.cp h1 .flag{width:60px;height:45px;border-width:2px}
.cp .kind{display:block;margin-top:22px;font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .kind + h1{margin-top:8px}
.cp h1.word{font-size:clamp(24px,3.6vw,30px)}
.cp .intro{color:var(--muted);margin:0 0 20px}
.cp .intro a{color:#0072B2}
.cp h2{font:600 15px var(--body);text-transform:uppercase;letter-spacing:.06em;margin:30px 0 4px;border-top:6px solid #D55E00;padding-top:10px}
.cp ul{list-style:none;margin:0;padding:0}
.cp li{padding:12px 0;border-bottom:1px solid color-mix(in srgb,#000 25%,transparent)}
.cp li a{color:var(--ink);font-weight:600;text-decoration:none}
.cp li a:hover,.cp li a:focus-visible{text-decoration:underline}
.cp .meta{color:var(--muted);font-size:14px;margin-top:2px}
.cp .steps{color:var(--muted);font-size:13.5px;margin-top:2px}
.cp .what{font-size:15px;margin-top:4px;max-width:64ch}
.cp .places{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-top:20px}
.cp .places a{display:flex;align-items:center;gap:12px;border:2px solid #000;background:var(--bg);padding:12px 14px;color:var(--ink);font-weight:600;text-decoration:none}
.cp .places a:hover,.cp .places a:focus-visible{background:color-mix(in srgb,#D55E00 15%,var(--bg))}
.cp .def{font-size:17px;line-height:1.55;margin:10px 0 14px;max-width:64ch}
.cp .def a{color:var(--ink);text-decoration:underline;text-decoration-color:#0072B2;text-decoration-thickness:2px;text-underline-offset:3px}
.cp .more-stories{margin-top:14px;font:600 15px var(--body);color:#fff;background:#0072B2;border:2px solid #000;padding:9px 16px;cursor:pointer}
.cp .more-stories[hidden]{display:none}
.cp .letters{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px}
.cp .letters a{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border:2px solid #000;color:var(--ink);font-weight:600;text-decoration:none}
.cp .letters a:hover,.cp .letters a:focus-visible{background:color-mix(in srgb,#D55E00 15%,var(--bg))}
.cp .terms li{display:grid;grid-template-columns:minmax(150px,220px) 1fr;gap:4px 18px}
.cp .terms .short{color:var(--muted);font-size:15px}
.cp .terms .grp{display:block;color:var(--muted);font:500 11px var(--mono);letter-spacing:.06em;text-transform:uppercase;margin-top:3px}
@media (max-width:560px){.cp .terms li{grid-template-columns:1fr}}
.cp .cloud{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:center;gap:2px 12px;padding:12px 14px;border:2px solid #000;background:var(--bg);line-height:1.15}
.cp .cloud a{font-weight:600;text-decoration:none}
.cp .cloud a.big{font-family:var(--display);font-weight:400}
.cp .cloud a:hover,.cp .cloud a:focus-visible{text-decoration:underline}
.cp .cloud.roomy{gap:8px 16px;padding:26px 22px;min-height:150px;align-content:center;line-height:1.3}
.cp .terms.small li{padding:9px 0}
.cp .terms.small li a{font-size:14.5px}
.cp .terms.small .short{font-size:13.5px}
.cp .days li a{font-size:16px}
.cp .days .grp{margin-left:10px;color:var(--muted);font:500 11px var(--mono);letter-spacing:.06em;text-transform:uppercase}
.cp .note{margin-top:28px;font-size:14px;color:var(--muted)}
.cp .note a{color:#0072B2}
a.subscribe-btn{text-decoration:none}
"""


def write_css(out: Path) -> None:
    """site.css: the front page's styles (its masthead and footer) and these pages' own."""
    style = re.search(r"<style>(.*?)</style>", TEMPLATE.read_text(encoding="utf-8"), re.S).group(1)
    (out / "site.css").write_text(style + STYLE, encoding="utf-8")


def frame(conn, total: int) -> tuple[str, str]:
    """The front page's masthead (no stream links; Subscribe and Glossary open on the front page) and footer."""
    t = TEMPLATE.read_text(encoding="utf-8")
    last = (store.last_run(conn) or {}).get("ran_at") or ""
    header = re.search(r'<header class="top home">.*?</header>', t, re.S).group(0)
    header = re.sub(r"\s*<!-- Each stream.*?</nav>", "", header, flags=re.S)
    header = re.sub(r'<button class="(subscribe-btn[^"]*)" id="(\w+)-open" type="button" aria-haspopup="dialog"',
                    r'<a class="\1" href="/#\2"', header).replace("</button>", "</a>")
    when = (f'<div>Last update <time datetime="{escape(last)}">{escape(last[:16].replace("T", " "))} UTC</time></div>'
            if last else "")
    header = header.replace("Loading feed…", f"<div><b>{total}</b> stories in total</div>{when}")
    footer = re.search(r'<footer class="site-foot">.*?</footer>', t, re.S).group(0)
    return header, footer


# the masthead's time in the reader's own time zone, as on the front page
LOCAL_TIME = ('<script>document.querySelectorAll("time[datetime]").forEach(t => t.textContent = new Date(t.dateTime)'
              '.toLocaleString(undefined,{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}))</script>')


def page(title: str, description: str, path: str, body: str, data: dict, parts: tuple[str, str],
         back: tuple[str, str], note: str = "") -> str:
    """A whole page: `back` is (address, words) for the link above the heading, `note` a line under the content."""
    url = f"{rss.SITE}{path}"
    header, footer = parts
    return (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8"><meta name="color-scheme" content="light">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<base href="/">\n'
            f'<title>{escape(title)}</title>\n<meta name="description" content="{escape(description)}">\n'
            f'<link rel="canonical" href="{url}">\n<link rel="icon" href="/favicon.ico">\n'
            f'<meta property="og:title" content="{escape(title)}">\n<meta property="og:description" content="{escape(description)}">\n'
            f'<meta property="og:url" content="{url}">\n<meta property="og:image" content="{rss.SITE}og.png">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n'
            f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>\n'
            f'<link rel="stylesheet" href="site.css">\n</head>\n<body>\n<div class="wrap">\n{header}\n<main class="cp">\n'
            f'<a class="back" href="{back[0]}">← {escape(back[1])}</a>\n{body}\n'
            + (f'<p class="note">{note}</p>\n' if note else "")
            + f'</main>\n{footer}\n</div>\n{LOCAL_TIME}\n</body>\n</html>\n')
