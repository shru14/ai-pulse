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
.cp .topics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:18px}
@media (max-width:760px){.cp .topics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:560px){.cp .topics{grid-template-columns:1fr}}
.cp .topics > a{display:flex;flex-direction:column;border:2px solid #000;background:var(--bg);color:var(--ink);text-decoration:none;box-shadow:3px 3px 0 #000;transition:transform .12s,box-shadow .12s}
.cp .topics > a:hover,.cp .topics > a:focus-visible{transform:translate(-2px,-2px);box-shadow:6px 6px 0 #D55E00}
.cp .topics .pic{position:relative;display:block;height:92px;border-bottom:2px solid #000;overflow:hidden}
.cp .photo{display:block;width:100%;height:100%;object-fit:cover}
.cp .badges{display:flex;gap:6px;align-items:center}
.cp .topics .pic .badges{position:absolute;left:6px;bottom:6px;gap:4px}
.cp .topics .pic .flag{width:22px;height:16px}
.cp .topics .pic .logo{width:22px;height:22px}
.cp .topics .pic .logo svg{width:12px;height:12px}
.cp .badges .flag{width:30px;height:22px;border:2px solid #000;object-fit:cover}
.cp .logo{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;background:#fff;border:2px solid #000;border-radius:50%;flex:none}
.cp .logo svg{width:17px;height:17px}
.cp .done{position:absolute;top:10px;right:10px;font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;background:#fff;color:#000;border:2px solid #000;padding:2px 7px}
.cp .topics .txt{display:flex;flex-direction:column;gap:4px;padding:8px 10px 10px;flex:1}
.cp .topics .pic .done{top:6px;right:6px;font-size:9.5px;padding:1px 5px}
.cp .done.hot{background:#D55E00;color:#000}
.cp .topics .kind{margin:0}
.cp .topics .kind{font-size:10px}
.cp .topics b{font:400 15px/1.2 var(--display)}
.cp .topics .last{display:flex;flex-direction:column;gap:3px;margin-top:auto;border:2px solid #000;background:color-mix(in srgb,#56B4E9 14%,var(--bg));padding:6px 8px}
.cp .topics .last .lt{font-size:13.5px;font-weight:600;line-height:1.35}
.cp .topics .last .lt:empty{display:none}
.cp .topics .last .meta{margin:0;font-size:11px}
.cp:has(> .tp) > .back{margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .tp{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .topic-hero{position:relative;height:clamp(240px,34vw,380px);margin-top:16px;border:2px solid #000;overflow:hidden;box-shadow:6px 6px 0 #000}
.cp .topic-hero .photo{object-position:right center}  /* the cartoon sits on the right, clear of the title */
.cp .topic-hero .over{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;gap:10px;padding:clamp(18px,3vw,34px);background:linear-gradient(100deg,rgba(0,0,0,.85) 0%,rgba(0,0,0,.55) 45%,transparent 80%),linear-gradient(transparent 50%,rgba(0,0,0,.6))}
.cp .topic-hero .kind{margin:0;color:#fff;background:#D55E00;color:#000;align-self:flex-start;padding:2px 8px;border:2px solid #000}
.cp .topic-hero h1{color:#fff;margin:0;font-size:clamp(34px,6vw,64px);max-width:16ch}
.cp .topic-hero .done{position:static;align-self:flex-start}
.cp .topic-hero .badges .flag{width:36px;height:27px}
.cp .topic-hero .badges .logo{width:34px;height:34px}
.cp .tp > .intro{margin:18px 0 6px;font-size:clamp(17px,2vw,20px);line-height:1.45;color:var(--ink);max-width:62ch}
.cp .tp h2{margin-top:34px}
.cp .mlist{list-style:none;margin:12px 0 0;padding:0}
.cp .mlist li{position:relative;padding:5px 0 5px 28px;font-size:15.5px;line-height:1.35;border:0}
.cp .mlist li::before{content:"✓";position:absolute;left:4px;top:4px;font-weight:700;color:#D55E00}
.cp .tp > .related{margin-top:28px;font-size:15.5px;line-height:1.35}  /* in the key moments' font, on their left edge */
.cp .mlist a,.cp .tp > .related a{font-weight:600;color:var(--ink);text-decoration:underline;text-underline-offset:2px}
.cp .mlist .when{margin-left:8px;color:var(--muted);font-size:13px;white-space:nowrap}
.cp .when{font:600 12.5px var(--mono);letter-spacing:.03em}
.cp .lane{font:500 10.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .legend{display:flex;gap:18px;flex-wrap:wrap;margin:4px 0 0;font-size:14px}
.cp .lg::before{content:"";display:inline-block;width:12px;height:12px;border:2px solid #000;margin-right:7px;vertical-align:-1px}
.cp .lg.official::before{background:#D55E00}
.cp .lg.news::before{background:#56B4E9}
.cp .chapters{margin-top:10px}
.cp .chapter{display:grid;grid-template-columns:150px minmax(0,1fr);gap:0 10px}
.cp .chapter .yr{position:relative;border-top:2px solid #000}
.cp .chapter .yr span{position:sticky;top:calc(var(--bar-h,64px) + 14px);display:block;padding-top:10px;font:400 clamp(34px,4vw,50px)/1 var(--display);color:transparent;-webkit-text-stroke:2px #000}
.cp .chapter:nth-child(odd) .yr span{color:#D55E00}
.cp ol.timeline{list-style:none;margin:0;padding:18px 0 22px;position:relative;border-top:2px dashed color-mix(in srgb,#000 30%,transparent)}
.cp ol.timeline::before{content:"";position:absolute;top:0;bottom:0;left:50%;width:4px;margin-left:-2px;background:#000}
.cp .timeline > li{border:0;padding:0;position:relative}
.cp .timeline .ev{display:flex;padding:9px 0}
.cp .timeline .ev.left{justify-content:flex-start;padding-right:calc(50% + 26px)}
.cp .timeline .ev.right{justify-content:flex-end;padding-left:calc(50% + 26px)}
.cp .timeline .ev .box{position:relative;display:flex;width:100%;border:2px solid #000;background:var(--bg);box-shadow:4px 4px 0 #000}
.cp .timeline .ev.official .box{border-top:8px solid #D55E00}
.cp .timeline .ev.news .box{border-top:8px solid #56B4E9}
.cp .timeline .ev.wide .box{box-shadow:4px 4px 0 #0072B2}
.cp .timeline .ev.key .box{box-shadow:6px 6px 0 #D55E00}
.cp .timeline .ev .txt{flex:1;min-width:0;padding:10px 12px 11px}
.cp .timeline .ev .box::after{content:"";position:absolute;top:22px;width:24px;height:3px;background:#000}
.cp .timeline .ev.left .box::after{right:-26px}
.cp .timeline .ev.right .box::after{left:-26px}
.cp .timeline .dot{position:absolute;left:50%;top:30px;width:16px;height:16px;margin-left:-8px;border:3px solid #000;border-radius:50%;background:#56B4E9;z-index:1}
.cp .timeline .official .dot{background:#D55E00;border-radius:2px;transform:rotate(45deg)}
.cp .timeline .key .dot{width:22px;height:22px;margin-left:-11px;top:27px}
.cp .timeline .top{margin-bottom:6px}
.cp .timeline .top .flag,.cp .timeline .top .logo{margin-left:auto}
.cp .timeline .top .flag{width:26px;height:19px;border:2px solid #000;object-fit:cover}
.cp .timeline .top .logo{width:26px;height:26px}
.cp .timeline .top .logo svg{width:14px;height:14px}
.cp .timeline .ev a{display:block;color:var(--ink);font-weight:600;line-height:1.35;text-decoration:none}
.cp .timeline .ev a:hover,.cp .timeline .ev a:focus-visible{text-decoration:underline}
.cp .timeline .more{display:flex;flex-direction:column;align-items:center;padding:8px 0}
.cp .timeline .more button{position:relative;z-index:1;font:600 13px var(--body);background:#fff;color:#000;border:2px solid #000;border-radius:999px;padding:4px 14px;cursor:pointer}
.cp .timeline .more button[aria-expanded="true"]{background:#000;color:#fff}
.cp .timeline .more ul{position:relative;z-index:1;width:min(600px,100%);margin-top:8px;border:2px solid #000;background:var(--bg);padding:2px 12px}
.cp .timeline .more ul[hidden]{display:none}
.cp .timeline .more ul li{display:grid;grid-template-columns:64px 1fr;gap:0 10px;padding:8px 0;font-size:14.5px}
.cp .timeline .more ul li:last-child{border-bottom:0}
.cp .timeline .more ul a{font-weight:600;color:var(--ink);text-decoration:none}
.cp .timeline .more .src{grid-column:2;color:var(--muted);font-size:13px}
.cp .timeline .now{display:flex;justify-content:center;padding:14px 0 0}
.cp .timeline .now span{position:relative;z-index:1;background:#D55E00;color:#000;border:2px solid #000;font:400 16px var(--display);padding:4px 16px;border-radius:999px}
@media (max-width:700px){
  .cp .chapter{grid-template-columns:1fr}
  .cp .chapter .yr{position:sticky;top:var(--bar-h,64px);z-index:2;background:var(--bg);border-top:0;border-bottom:2px solid #000}
  .cp .chapter .yr span{position:static;padding:6px 0;font-size:30px}
  .cp ol.timeline::before{left:10px}
  .cp .timeline .ev.left,.cp .timeline .ev.right{padding:9px 0 9px 36px}
  .cp .timeline .dot{left:12px}
  .cp .timeline .ev.left .box::after,.cp .timeline .ev.right .box::after{left:-18px;right:auto;width:16px}
  .cp .timeline .more,.cp .timeline .now{align-items:flex-start;justify-content:flex-start}
  .cp .timeline .more{padding-left:36px}  /* beside the line, not on it */
  .cp .timeline .more ul li{grid-template-columns:52px 1fr}
  .cp .timeline .ev a{font-size:15px}
  .cp .tp h2{margin-top:26px}
}
a.subscribe-btn{text-decoration:none}
/* the monthly issues (monthly.py): the shelf of covers and each issue's sheets */
.cp:has(> .mi) > .back{margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .mi{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .mi .topic-hero .kind{font-size:12.5px}
.cp .mi .topic-hero h1{max-width:none}
.cp .mi .topic-hero{background:#1b1f27}
.cp .mi .timeline .top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.cp .mi .topic-hero .num{color:#fff;font:600 14px var(--mono);letter-spacing:.06em}
.cp .contents{display:flex;flex-wrap:wrap;gap:6px 22px;list-style:none;margin:18px 0 0;padding:12px 0;border-bottom:2px solid #000;counter-reset:c}
.cp .contents li{padding:0;border:0;counter-increment:c;font-size:15px}
.cp .contents li::before{content:counter(c,decimal-leading-zero);font:600 12px var(--mono);color:#D55E00;margin-right:7px}
.cp .contents a{font-weight:600;color:var(--ink);text-decoration:none}
.cp .contents a:hover{text-decoration:underline}
.cp .sheet{margin-top:34px;counter-increment:sheet}
.cp .mi{counter-reset:sheet}
.cp .sheet > h2::before{content:counter(sheet,decimal-leading-zero);margin-right:10px;color:#D55E00}
.cp .brief{font-size:clamp(18px,2.1vw,21px);line-height:1.55;max-width:64ch;margin:12px 0 0;border-left:6px solid #D55E00;padding-left:16px}
.cp table.mt{width:100%;border-collapse:collapse;margin-top:10px;font-size:15px}
.cp .mt th{text-align:left;font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:0 12px 6px 0}
.cp .mt td{border-top:1px solid color-mix(in srgb,#000 25%,transparent);padding:10px 12px 10px 0;vertical-align:top}
.cp .mt tr.first td{border-top:2px solid #000}
.cp .mt td a{color:var(--ink);font-weight:600;text-decoration:none;line-height:1.35}
.cp .mt td a:hover,.cp .mt td a:focus-visible{text-decoration:underline}
.cp .mt .meta{font-size:13px}
.cp .mt .n{font:400 20px var(--display)}
.cp .mt td:last-child,.cp .mt th:last-child{text-align:right;white-space:nowrap;padding-right:0}
.cp .mt .st{display:inline-block;margin:0 0 4px;font:600 10.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:#141925;background:var(--st);border:2px solid #000;padding:1px 6px;white-space:nowrap}
.cp .mt.streams td:first-child{width:1%;white-space:nowrap}
.cp .mt.top td:first-child{width:1%}
.cp .mt.top .st{display:table;margin-bottom:5px}
.cp .mt .new{display:inline-block;margin-left:8px;font:600 10px var(--mono);letter-spacing:.06em;text-transform:uppercase;background:#E69F00;color:#000;border:2px solid #000;padding:0 5px;vertical-align:2px}
.cp .groups .badge{display:inline-block;font:600 10.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:#000;background:#F0E442;border:2px solid #000;padding:1px 6px;white-space:nowrap}
.cp .groups .b-in_force{background:#009E73}.cp .groups .b-signed{background:#56B4E9}.cp .groups .b-standard{background:#CC79A7}
.cp .groups .b-vetoed,.cp .groups .b-withdrawn{background:#fff;border-style:dashed}
.cp .groups{border-top:2px solid #000;margin-top:10px}
.cp .grp{display:grid;grid-template-columns:170px 1fr;gap:10px;padding:10px 0;border-bottom:1px solid color-mix(in srgb,#000 25%,transparent)}
.cp .grp .n{font:400 22px var(--display);margin-left:8px;vertical-align:-3px}
.cp .chips{display:flex;flex-wrap:wrap;gap:6px}
.cp .chip{display:inline-flex;align-items:center;gap:6px;max-width:100%;border:1.5px solid var(--line);padding:3px 8px 3px 4px;font-size:13.5px}
.cp .chip .flag{width:20px;height:15px}
.cp .chip a{color:var(--ink);font-weight:500;text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px}
.cp .chip a:hover,.cp .chip a:focus-visible{text-decoration:underline}
.cp .mt.words td:nth-child(2){color:var(--muted);font-size:14.5px}
.cp .mt .name{font:400 16px/1.2 var(--display)!important}
.cp .chapter.wk .yr span{font-size:clamp(26px,3vw,36px)}
.cp .chapter.wk .yr small{display:block;position:sticky;top:calc(var(--bar-h,64px) + 56px);margin-top:4px;font:600 12.5px var(--mono);color:var(--muted)}
.cp .timeline .quiet{text-align:center;color:var(--muted);font-size:14px;padding:12px 0;position:relative;z-index:1}
.cp .issue-nav{display:flex;justify-content:space-between;gap:12px;margin-top:36px;padding-top:14px;border-top:6px solid #D55E00;font-weight:600}
.cp .issue-nav a{color:var(--ink)}
.cp .shelf{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-top:14px}
.cp .shelf a{display:flex;flex-direction:column;border:2px solid #000;background:var(--bg);color:var(--ink);text-decoration:none;box-shadow:4px 4px 0 #000;transition:transform .12s,box-shadow .12s}
.cp .shelf a:hover,.cp .shelf a:focus-visible{transform:translate(-2px,-2px);box-shadow:6px 6px 0 #D55E00}
.cp .shelf .pic{display:block;aspect-ratio:4/3;border-bottom:2px solid #000;overflow:hidden;background:#1b1f27}
.cp .shelf .photo{object-position:right center}
.cp .shelf .txt{display:flex;flex-direction:column;gap:2px;padding:10px 12px 12px}
.cp .shelf .num{font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:#D55E00}
.cp .shelf b{font:400 22px/1.1 var(--display)}
@media (max-width:900px){.cp .shelf{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:640px){.cp .shelf{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cp .grp{grid-template-columns:1fr;gap:6px}
  .cp .mt.top td:nth-child(3),.cp .mt.top th:nth-child(3){display:none}
  .cp .chapter.wk .yr small{position:static;display:inline;margin-left:10px}}
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
