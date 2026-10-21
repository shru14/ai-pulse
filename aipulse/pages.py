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

STYLE = """
.cp{max-width:780px;margin:0 auto;padding-bottom:12px}
.cp .back{display:inline-block;margin-top:24px;font-weight:600;font-size:15px;color:var(--ink);text-decoration:underline;text-decoration-color:var(--accent);text-decoration-thickness:2px;text-underline-offset:4px}
.cp h1{display:flex;align-items:center;gap:16px;font:400 clamp(28px,5vw,40px)/1.1 var(--display);letter-spacing:0;margin:18px 0 8px}
.cp .flag{flex:none;width:32px;height:24px;object-fit:cover;border:1px solid var(--line)}
.cp h1 .flag{width:60px;height:45px;border-width:2px}
.cp .kind{display:block;margin-top:22px;font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .kind + h1{margin-top:8px}
.cp h1.word{font-size:clamp(24px,3.6vw,30px)}
.cp .intro{color:var(--muted);margin:0 0 20px}
.cp .intro a{color:var(--accent)}
.cp h2{font:600 15px var(--body);text-transform:uppercase;letter-spacing:.06em;margin:30px 0 4px;border-top:6px solid var(--ink);padding-top:10px}
.cp ul{list-style:none;margin:0;padding:0}
.cp li{padding:12px 0;border-bottom:1px solid color-mix(in srgb,var(--ink) 25%,transparent)}
.cp li a{color:var(--ink);font-weight:600;text-decoration:none}
.cp li a:hover,.cp li a:focus-visible{text-decoration:underline}
.cp .meta{color:var(--muted);font-size:14px;margin-top:2px}
.cp .steps{color:var(--muted);font-size:13.5px;margin-top:2px}
.cp .what{font-size:15px;margin-top:4px}
.cp .places{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-top:20px}
.cp .places a{display:flex;align-items:center;gap:12px;border:2px solid var(--line);background:var(--bg);padding:12px 14px;color:var(--ink);font-weight:600;text-decoration:none}
.cp .places a:hover,.cp .places a:focus-visible{background:#F0E442;color:#000}
.cp:has(> .kd) > .back{margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .kd{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}  /* Industry's kinds run wide, like a topic page */
.cp .companies{grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;margin:4px 0 26px}  /* a tile per company or topic, each previewing its newest story */
.cp .companies button{display:flex;flex-direction:column;align-items:stretch;gap:10px;border:2px solid var(--line);background:var(--bg);padding:16px 18px;color:var(--ink);font:600 18px var(--body);text-align:left;cursor:pointer}
.cp .companies .head{display:flex;align-items:center;gap:12px}
.cp .companies .peek{font:400 15px/1.45 var(--body);color:var(--muted)}
.cp .companies button:hover,.cp .companies button:focus-visible{background:#F0E442;color:#000}
.cp .companies button:hover .peek,.cp .companies button:focus-visible .peek,.cp .companies button:hover small,.cp .companies button:focus-visible small{color:#3B3B3B}
.cp .companies button[aria-pressed="true"]{box-shadow:5px 5px 0 #0072B2}
.cp .companies .logo{color:#141925;font:700 15px var(--body)}
.cp .companies small{margin-left:auto;color:var(--muted);font-size:13px}
.cp .def{font-size:17px;line-height:1.55;margin:10px 0 14px}
.cp .def a{color:var(--ink);text-decoration:underline;text-decoration-color:var(--accent);text-decoration-thickness:2px;text-underline-offset:3px}
.cp .more-stories{margin-top:14px;font:600 15px var(--body);color:#fff;background:#0072B2;border:2px solid var(--line);padding:9px 16px;cursor:pointer}
.cp .more-stories[hidden]{display:none}
.cp .letters{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px}
.cp .letters a{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border:2px solid var(--line);color:var(--ink);font-weight:600;text-decoration:none}
.cp .letters a:hover,.cp .letters a:focus-visible{background:#F0E442;color:#000}
.cp .terms li{display:grid;grid-template-columns:minmax(150px,220px) 1fr;gap:4px 18px}
.cp .terms .short{color:var(--muted);font-size:15px}
.cp .terms .grp{display:block;color:var(--muted);font:500 11px var(--mono);letter-spacing:.06em;text-transform:uppercase;margin-top:3px}
@media (max-width:560px){.cp .terms li{grid-template-columns:1fr}}
.cp .cloud{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:center;gap:2px 12px;padding:12px 14px;border:2px solid var(--line);background:var(--bg);line-height:1.15}
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
.cp .note a{color:var(--accent)}
.cp:has(> .ti) > .back{margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .ti{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}  /* the topics index runs wide, like a topic page */
.cp .topics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-top:22px}
@media (max-width:860px){.cp .topics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:560px){.cp .topics{grid-template-columns:1fr}}
.cp .topics > a{display:flex;flex-direction:column;border:2px solid var(--line);background:var(--bg);color:var(--ink);text-decoration:none;box-shadow:3px 3px 0 var(--line);transition:transform .12s,box-shadow .12s}
.cp .topics > a:hover,.cp .topics > a:focus-visible{transform:translate(-2px,-2px);box-shadow:6px 6px 0 #0072B2}
.cp .topics .pic{position:relative;display:block;height:180px;border-bottom:2px solid var(--line);overflow:hidden}
.cp .photo{display:block;width:100%;height:100%;object-fit:cover}
.cp .badges{display:flex;gap:6px;align-items:center}
.cp .topics .pic .badges{position:absolute;left:10px;bottom:10px;gap:5px}
.cp .topics .pic .flag{width:28px;height:20px}
.cp .topics .pic .logo{width:28px;height:28px}
.cp .topics .pic .logo svg{width:15px;height:15px}
.cp .badges .flag{width:30px;height:22px;border:2px solid var(--line);object-fit:cover}
.cp .logo{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;background:#fff;border:2px solid var(--line);border-radius:50%;flex:none}
.cp .logo svg{width:17px;height:17px}
.cp .done{position:absolute;top:10px;right:10px;font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;background:#fff;color:#000;border:2px solid var(--line);padding:2px 7px}
.cp .topics .txt{display:flex;flex-direction:column;gap:8px;padding:14px 16px 16px;flex:1}
.cp .topics .pic .done{top:10px;right:10px;font-size:11px;padding:2px 7px}
.cp .done.hot{background:#F0E442;color:#000}
.cp .topics .kind{margin:0}
.cp .topics .kind{font-size:11.5px}
.cp .topics b{font:400 21px/1.2 var(--display)}
.cp .topics .last{display:flex;flex-direction:column;gap:4px;margin-top:auto;border:2px solid var(--line);background:color-mix(in srgb,#56B4E9 14%,var(--bg));padding:10px 12px}
.cp .topics .last .lt{font-size:15px;font-weight:600;line-height:1.35}
.cp .topics .last .lt:empty{display:none}
.cp .topics .last .meta{margin:0;font-size:11px}
.cp:has(> .sd) > .back{margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .sd{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}  /* standards: the three lists side by side */
.cp .sd .cols{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;align-items:start}
.cp .sd section ul{max-height:72vh;overflow-y:auto;padding-right:8px}
.cp .sd h2{font:400 22px/1.15 var(--display);letter-spacing:.01em}
.cp .tp-t .tp-where{white-space:nowrap;font-weight:600}  /* laws adopted, bills, AI bodies: the place, its flag */
.cp .tp-t .flag{width:24px;height:18px;vertical-align:-3px;margin-right:8px}
@media (min-width:641px){.cp .tp-grp tr:not(.tp-rep) td{border-top:2px solid var(--line)}.cp .tp-grp .tp-rep .tp-where span{visibility:hidden}}  /* laws adopted, bills, AI bodies: by place */
.cp .gt-wrap{overflow-x:auto;margin:10px 0 28px}  /* a place's page: each kind of record as a ruled grid */
.cp table.gt{width:100%;border-collapse:collapse;font-size:14.5px;border:2px solid var(--line)}
.cp .gt th{text-align:left;font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;background:color-mix(in srgb,var(--ink) 10%,var(--bg));padding:8px 10px;border:1px solid color-mix(in srgb,var(--ink) 30%,transparent)}
.cp .gt td{padding:8px 10px;vertical-align:top;border:1px solid color-mix(in srgb,var(--ink) 30%,transparent);line-height:1.35}
.cp .gt td a{color:var(--ink);font-weight:600;text-decoration:none}.cp .gt td a:hover{text-decoration:underline}
.cp .gt td:first-child{min-width:220px}.cp .gt td:not(:first-child):not(.gt-steps){white-space:nowrap}
.cp .gt .gt-steps{font-size:13.5px;color:var(--muted);min-width:200px}
/* phones: each record a card, its title on top, source, stage and date labelled side by side under it (data-l) */
@media (max-width:640px){.cp .gt-wrap{overflow:visible}
  .cp table.gt,.cp .gt tbody{display:block;border:0}
  .cp .gt thead{display:none}
  .cp .gt tr{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px 10px;margin:0 0 8px;padding:9px 10px;border:1.5px solid var(--line);box-shadow:2px 2px 0 var(--line)}
  .cp .gt td{display:block;border:0;padding:0;min-width:0!important;white-space:normal!important;font-size:12.5px}
  .cp .gt td:first-child{grid-column:1/-1;font-size:13.5px}
  .cp .gt td.gt-steps{grid-column:1/-1;order:1;font-size:12px;color:var(--muted)}  /* steps last, under source, stage and date */
  .cp .gt td:empty{display:none}
  .cp .gt td[data-l]::before{content:attr(data-l);display:block;font:600 9px/1.3 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:1px}}
@media (max-width:640px){.cp .tp-t thead{display:none}  /* phones: place and date, then the title, then the stage */
  .cp .tp-t tr{display:grid;grid-template-columns:1fr auto;column-gap:12px;border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent);padding:10px 0}
  .cp .mt.tp-t td{border:0;padding:2px 0}.cp .tp-t .tp-title{grid-column:1/-1;order:3}.cp .tp-t .tp-stage{grid-column:1/-1;order:4;color:var(--muted);font-size:14px}
  .cp .tp-t .tp-src{grid-column:1/-1;order:5;color:var(--muted);font-size:14px}
  .cp .tp-grp tr:not(.tp-rep){border-top:2px solid var(--line)}.cp .tp-grp .tp-rep .tp-where{display:none}.cp .tp-grp .tp-rep .tp-src{grid-column:1}.cp .tp-grp .tp-rep .tp-date{order:6;grid-column:2}}
.cp .sd .what{font-size:14.5px}
@media (max-width:860px){.cp .sd .cols{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:16px;padding-bottom:8px}
  .cp .sd section{flex:0 0 85%;scroll-snap-align:start}}
.cp:has(> .tp) > .back{margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .tp{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .topic-hero{position:relative;height:clamp(150px,18vw,220px);margin-top:16px;border:2px solid var(--line);overflow:hidden;box-shadow:6px 6px 0 var(--line)}
.cp .topic-hero .photo{object-position:right center}  /* the cartoon sits on the right, clear of the title */
.cp .topic-hero .over{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;gap:6px;padding:clamp(18px,3vw,34px);background:linear-gradient(100deg,rgba(0,0,0,.85) 0%,rgba(0,0,0,.55) 45%,transparent 80%),linear-gradient(transparent 50%,rgba(0,0,0,.6))}
.cp .topic-hero .kind{margin:0;background:#F0E442;color:#000;align-self:flex-start;padding:2px 8px;border:2px solid var(--line)}
.cp .topic-hero h1{color:#fff;margin:0;font-size:clamp(28px,4vw,44px);max-width:16ch}
.cp .topic-hero .done{position:static;align-self:flex-start}
.cp .topic-hero .badges .flag{width:36px;height:27px}
.cp .topic-hero .badges .logo{width:34px;height:34px}
/* a topic's description sits in its header box, which grows to fit it on narrow screens */
.cp .tp .topic-hero{height:auto}
.cp .tp .topic-hero .photo{position:absolute;inset:0}
.cp .tp .topic-hero .over{position:relative;min-height:clamp(150px,18vw,220px);box-sizing:border-box}
.cp .tp .topic-hero .what{margin:0;color:#fff;font-size:clamp(14px,1.5vw,17px);line-height:1.4;max-width:52ch}
@media (max-width:640px){.cp .tp .topic-hero{background:#1b1f27}  /* phones: the cartoon keeps to the right, the text to its left */
  .cp .tp .topic-hero .photo{inset:50% 12px auto auto;transform:translateY(-50%);width:30%;height:auto;aspect-ratio:1;border:2px solid var(--line)}  /* the drawing half, whole */
  .cp .tp .topic-hero .over{padding-right:calc(30% + 24px);background:none}}
.cp .tp h2{margin-top:34px}
.cp .mlist{list-style:none;margin:12px 0 0;padding:0}
.cp .mlist li{position:relative;padding:5px 0 5px 28px;font-size:15.5px;line-height:1.35;border:0}
.cp .mlist li::before{content:"✓";position:absolute;left:4px;top:4px;font-weight:700;color:var(--c-tool)}
.cp .tp > .related{margin-top:28px;font-size:15.5px;line-height:1.35}  /* in the key moments' font, on their left edge */
.cp .mlist a,.cp .tp > .related a{font-weight:600;color:var(--ink);text-decoration:underline;text-underline-offset:2px}
.cp .mlist .when{margin-left:8px;color:var(--muted);font-size:13px;white-space:nowrap}
.cp .when{font:600 12.5px var(--mono);letter-spacing:.03em}
.cp .lane{font:500 10.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .legend{display:flex;gap:18px;flex-wrap:wrap;margin:4px 0 0;font-size:14px}
.cp .lg::before{content:"";display:inline-block;width:12px;height:12px;border:2px solid var(--line);margin-right:7px;vertical-align:-1px}
.cp .lg.official::before{background:var(--ink)}
.cp .lg.news::before{background:#56B4E9}
.cp .chapters{margin-top:10px}
.cp .chapter{display:grid;grid-template-columns:150px minmax(0,1fr);gap:0 10px}
.cp .chapter .yr{position:relative;border-top:2px solid var(--line)}
.cp .chapter .yr span{position:sticky;top:calc(var(--bar-h,64px) + 14px);display:block;padding-top:10px;font:400 clamp(34px,4vw,50px)/1 var(--display);color:transparent;-webkit-text-stroke:2px var(--ink)}
.cp .chapter:nth-child(odd) .yr span{color:var(--accent);-webkit-text-stroke:0}
.cp ol.timeline{list-style:none;margin:0;padding:18px 0 22px;position:relative;border-top:2px dashed color-mix(in srgb,var(--ink) 30%,transparent)}
.cp ol.timeline::before{content:"";position:absolute;top:0;bottom:0;left:50%;width:4px;margin-left:-2px;background:var(--ink)}
.cp .timeline > li{border:0;padding:0;position:relative}
.cp .timeline .ev{display:flex;padding:9px 0}
.cp .timeline .ev.left{justify-content:flex-start;padding-right:calc(50% + 26px)}
.cp .timeline .ev.right{justify-content:flex-end;padding-left:calc(50% + 26px)}
.cp .timeline .ev .box{position:relative;display:flex;width:100%;border:2px solid var(--line);background:var(--bg);box-shadow:4px 4px 0 var(--line)}
.cp .timeline .ev.official .box{border-top:8px solid var(--ink)}
.cp .timeline .ev.news .box{border-top:8px solid #56B4E9}
.cp .timeline .ev.wide .box{box-shadow:4px 4px 0 #0072B2}
.cp .timeline .ev.key .box{box-shadow:6px 6px 0 var(--ink);background:color-mix(in srgb,#F0E442 40%,var(--bg))}
:root[data-theme="dark"] .cp .timeline .ev.key .box{background:color-mix(in srgb,#F0E442 16%,var(--bg))}
.cp .timeline .ev .txt{flex:1;min-width:0;padding:10px 12px 11px}
.cp .timeline .ev .box::after{content:"";position:absolute;top:22px;width:24px;height:3px;background:var(--ink)}
.cp .timeline .ev.left .box::after{right:-26px}
.cp .timeline .ev.right .box::after{left:-26px}
.cp .timeline .dot{position:absolute;left:50%;top:30px;width:16px;height:16px;margin-left:-8px;border:3px solid var(--line);border-radius:50%;background:#56B4E9;z-index:1}
.cp .timeline .official .dot{background:var(--ink);border-radius:2px;transform:rotate(45deg)}
.cp .timeline .key .dot{width:22px;height:22px;margin-left:-11px;top:27px}
.cp .timeline .top{margin-bottom:6px}
.cp .timeline .top .flag,.cp .timeline .top .logo{margin-left:auto}
.cp .timeline .top .flag{width:26px;height:19px;border:2px solid var(--line);object-fit:cover}
.cp .timeline .top .logo{width:26px;height:26px}
.cp .timeline .top .logo svg{width:14px;height:14px}
.cp .timeline .ev a{display:block;color:var(--ink);font-weight:600;line-height:1.35;text-decoration:none}
.cp .timeline .ev a:hover,.cp .timeline .ev a:focus-visible{text-decoration:underline}
.cp .timeline .more{display:flex;flex-direction:column;align-items:center;padding:8px 0}
.cp .timeline .more button{position:relative;z-index:1;font:600 13px var(--body);background:#fff;color:#000;border:2px solid var(--line);border-radius:999px;padding:4px 14px;cursor:pointer}
.cp .timeline .more button[aria-expanded="true"]{background:var(--ink);color:var(--bg)}
.cp .timeline .more ul{position:relative;z-index:1;width:min(600px,100%);margin-top:8px;border:2px solid var(--line);background:var(--bg);padding:2px 12px}
.cp .timeline .more ul[hidden]{display:none}
.cp .timeline .more ul li{display:grid;grid-template-columns:64px 1fr;gap:0 10px;padding:8px 0;font-size:14.5px}
.cp .timeline .more ul li:last-child{border-bottom:0}
.cp .timeline .more ul a{font-weight:600;color:var(--ink);text-decoration:none}
.cp .timeline .more .src{grid-column:2;color:var(--muted);font-size:13px}
.cp .timeline .now{display:flex;justify-content:center;padding:14px 0 0}
.cp .timeline .now span{position:relative;z-index:1;background:#F0E442;color:#000;border:2px solid var(--line);font:400 16px var(--display);padding:4px 16px;border-radius:999px}
@media (max-width:700px){
  .cp .chapter{grid-template-columns:1fr}
  .cp .chapter .yr{position:sticky;top:var(--bar-h,64px);z-index:2;background:var(--bg);border-top:0;border-bottom:2px solid var(--line)}
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
/* section heads in the poster look, as the front page's bands: the title over a thick ink rule, no marker before it.
   The monthly issue and its insights keep their own. */
.cp h2:not(.mi *){display:flex;align-items:center;gap:10px;margin:36px 0 10px;padding:0 0 6px;border-top:0;border-bottom:4px solid var(--ink);
  font:400 22px/1.15 var(--display);text-transform:none;letter-spacing:0}
/* the monthly issue and its insights keep their approved report look, as it was */
.cp:has(> .mi) > .back{text-decoration-color:#F85C48}
.cp .mi .topic-hero .kind{background:#F85C48}
.cp .mi .lg.official::before,.cp .mi .timeline .official .dot{background:#F85C48}
.cp .mi .timeline .ev.official .box{border-top-color:#F85C48}
.cp .mi .timeline .now span{background:#F85C48}
.cp .mt.pv td:last-child,.cp .mt.pv th:last-child{text-align:left;white-space:normal}
@media (max-width:600px){.cp .mt.pv thead{display:none}.cp .mt.pv tr{display:block;border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent);padding:8px 0}
  .cp .mt.pv td{display:block;border:0;padding:2px 0}}
/* the monthly issues (monthly.py): the shelf of covers and each issue's sheets */
.cp:has(> .mi) > .back{margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .mi{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .mi .topic-hero .kind{font-size:12.5px}
.cp .mi .topic-hero h1{max-width:none}
.cp .mi .topic-hero{background:#1b1f27;height:clamp(150px,18vw,220px)}
.cp .mi .topic-hero .over{gap:6px}
.cp .mi .topic-hero h1{font-size:clamp(28px,4vw,44px)}
.cp .mi .timeline .top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.cp .mi .topic-hero .num{color:#fff;font:600 14px var(--mono);letter-spacing:.06em}
.cp .contents{display:flex;flex-wrap:nowrap;justify-content:space-between;gap:6px 14px;list-style:none;margin:18px 0 0;padding:12px 0;border-bottom:2px solid var(--line);counter-reset:c}
.cp .contents li{padding:0;border:0;counter-increment:c;font-size:14px;white-space:nowrap}
.cp .contents li::before{content:counter(c,decimal-leading-zero);font:600 12px var(--mono);color:var(--ink);margin-right:7px}
.cp .contents a{font-weight:600;color:var(--ink);text-decoration:none}
.cp .contents a:hover{text-decoration:underline}
.cp .sheet{margin-top:34px;counter-increment:sheet}
.cp .mi{counter-reset:sheet}
.cp .sheet > h2::before{content:counter(sheet,decimal-leading-zero);margin-right:10px;color:var(--ink)}
.cp .brief{font-size:clamp(16px,1.6vw,17.5px);line-height:1.65;margin:12px 0 0;border-left:6px solid var(--line);padding-left:16px}
.cp .brief mark{color:inherit;font-weight:600;background:linear-gradient(transparent 58%,color-mix(in srgb,#F0E442 75%,transparent) 58%)}
.cp table.mt{width:100%;border-collapse:collapse;margin-top:10px;font-size:15px}
.cp .mt th{text-align:left;font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:0 12px 6px 0}
.cp .mt td{border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent);padding:10px 12px 10px 0;vertical-align:top}
.cp .mt tr.first td{border-top:2px solid var(--line)}
.cp .mt td a{color:var(--ink);font-weight:600;text-decoration:none;line-height:1.35}
.cp .mt td a:hover,.cp .mt td a:focus-visible{text-decoration:underline}
.cp .mt .meta{font-size:13px}
.cp .mt .n{font:400 20px var(--display)}
.cp .mt td:last-child,.cp .mt th:last-child{text-align:right;white-space:nowrap;padding-right:0}
.cp .mt .st{display:inline-block;margin:0 0 4px;font:600 10.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:#141925;background:var(--st);border:2px solid var(--line);padding:1px 6px;white-space:nowrap}
.cp .mt.streams td:first-child{width:1%;white-space:nowrap}
.cp .mt.sl th{padding-left:12px}.cp .mt.sl tr:first-child td{border-top:2px solid var(--line)}
.cp .mt.sl td{padding-left:12px;vertical-align:baseline}
.cp .mt.sl td+td,.cp .mt.sl th+th{border-left:1px solid color-mix(in srgb,var(--ink) 18%,transparent)}
.cp .mt.sl td:first-child,.cp .mt.sl th:first-child{padding-left:0;width:1%;font:500 14px var(--mono);color:var(--muted)}
.cp .mt.sl td:nth-child(2) a{font-weight:700}
.cp .mt.sl td:nth-child(3) a{font-weight:400;text-decoration:underline;text-decoration-color:color-mix(in srgb,var(--ink) 35%,transparent);text-underline-offset:3px}
.cp .mt.sl td:nth-child(4){white-space:nowrap;color:var(--muted);font-size:14px}
.cp .mt .new{display:inline-block;margin-left:8px;font:600 10px var(--mono);letter-spacing:.06em;text-transform:uppercase;background:#E69F00;color:#000;border:2px solid var(--line);padding:0 5px;vertical-align:2px}
.cp .groups .badge{display:inline-block;font:600 10.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:#000;background:#F0E442;border:2px solid var(--line);padding:1px 6px;white-space:nowrap}
.cp .groups .b-in_force{background:#009E73}.cp .groups .b-signed{background:#56B4E9}.cp .groups .b-standard{background:#CC79A7}
.cp .groups .b-vetoed,.cp .groups .b-withdrawn{background:#fff;border-style:dashed}
.cp .groups{border-top:2px solid var(--line);margin-top:10px}
.cp .grp{display:grid;grid-template-columns:170px 1fr;gap:10px;padding:10px 0;border-bottom:1px solid color-mix(in srgb,var(--ink) 25%,transparent)}
.cp .grp .n{font:400 22px var(--display);margin-left:8px;vertical-align:-3px}
.cp .chips{display:flex;flex-wrap:wrap;gap:6px}
.cp .chip{display:inline-flex;align-items:flex-start;gap:7px;max-width:100%;border:1.5px solid var(--line);border-radius:0;padding:5px 9px 5px 5px;font-size:13.5px;line-height:1.3;background:none}
.cp .chip .flag{width:20px;height:15px;margin-top:1px}
.cp .chip a{color:var(--ink);font-weight:600;text-decoration:none}
.cp .chip a:hover,.cp .chip a:focus-visible{text-decoration:underline}
.cp .chip .meta{display:block;font-size:12px;margin-top:2px}
.cp .key{display:flex;gap:14px;flex-wrap:wrap;margin:6px 0 8px;font:500 11.5px var(--mono);color:var(--muted)}
.cp .key span{display:inline-flex;align-items:center;gap:6px}
.cp .sq{display:inline-block;flex:none;width:12px;height:12px;background:var(--st);border:2px solid var(--line)}
.cp .tiles{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}  /* What mattered most */
@media (min-width:900px){.cp .tiles{grid-template-columns:repeat(5,minmax(0,1fr))}}
.cp .tiles li{display:flex;flex-direction:column;align-items:flex-start;gap:6px;padding:10px;border:2px solid var(--line);border-left:8px solid var(--st)}
.cp .tiles .r{font:400 20px/1 var(--display)}
.cp .tiles a{flex:1;color:var(--ink);font-weight:700;font-size:14.5px;line-height:1.3;text-decoration:none}
.cp .tiles a:hover,.cp .tiles a:focus-visible{text-decoration:underline}
.cp .tiles .out{font:600 11px var(--mono);padding:2px 6px;border:2px solid var(--line);background:var(--st);color:#000;white-space:nowrap}
.cp .sgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:12px}
.cp .scard{border:2px solid var(--line);box-shadow:4px 4px 0 var(--line);background:var(--bg)}
.cp .scard h3{margin:0;padding:7px 12px;background:var(--st);border-bottom:2px solid var(--line);color:#000;font:400 16px/1.2 var(--display)}
.cp .scard ol{list-style:none;margin:0;padding:0 12px}
.cp .scard li{padding:10px 0;border-bottom:1px solid color-mix(in srgb,var(--ink) 25%,transparent)}
.cp .scard li:last-child{border-bottom:0}
.cp .scard a{color:var(--ink);font-weight:400;text-decoration:none;line-height:1.35}
.cp .scard a:hover,.cp .scard a:focus-visible{text-decoration:underline}
.cp .scard .meta{font-size:12.5px;margin-top:3px}
@media (min-width:701px){
  .cp .mi .chapters{display:grid;grid-template-columns:repeat(var(--weeks,5),minmax(0,1fr));gap:0 12px;border-top:4px solid var(--line);margin-top:18px}
  .cp .mi .chapter{display:block}
  .cp .mi .chapter .yr{border-top:0;padding-top:14px}
  .cp .mi .chapter .yr::before{content:"";position:absolute;top:-12px;left:0;width:16px;height:16px;border:3px solid var(--line);border-radius:50%;background:#56B4E9}
  .cp .mi .chapter.wk .yr span{position:static;padding-top:6px;font-size:24px}
  .cp .mi .chapter.wk .yr small{position:static}
  .cp .mi ol.timeline{border-top:0;padding:10px 0 0}
  .cp .mi ol.timeline::before,.cp .mi .timeline .dot,.cp .mi .timeline .ev .box::after{display:none}
  .cp .mi .timeline .ev.left,.cp .mi .timeline .ev.right{padding:0 0 10px}
  .cp .mi .timeline .ev .box{box-shadow:3px 3px 0 var(--line);font-size:14px}
  .cp .mi .timeline .ev.wide .box{box-shadow:3px 3px 0 #0072B2}
  .cp .mi .timeline .ev .txt{padding:8px 10px 9px}
  .cp .mi .timeline .quiet{text-align:left}}
.cp .blocks{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:10px}
.cp .blk{display:flex;flex-direction:column;gap:5px;border:2px solid var(--line);padding:10px;color:var(--muted);font-size:13px;line-height:1.4;text-decoration:none}
.cp .blk b{color:var(--ink);font:400 16px/1.15 var(--display)}
.cp .blk .new{display:inline-block;margin-left:6px;font:600 9.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;background:#E69F00;color:#000;border:2px solid var(--line);padding:0 4px;vertical-align:2px}
.cp .blk .n{margin-top:auto;font:600 11px var(--mono);color:var(--muted)}
.cp .blk:hover b,.cp .blk:focus-visible b{text-decoration:underline}
.cp .mt .name{font:500 15px/1.3 var(--body)!important}
.cp .chapter.wk .yr span{font-size:clamp(26px,3vw,36px)}
.cp .chapter.wk .yr small{display:block;position:sticky;top:calc(var(--bar-h,64px) + 56px);margin-top:4px;font:600 12.5px var(--mono);color:var(--muted)}
.cp .timeline .quiet{text-align:center;color:var(--muted);font-size:14px;padding:12px 0;position:relative;z-index:1}
.cp .issue-nav{display:flex;justify-content:space-between;gap:12px;margin-top:36px;padding-top:14px;border-top:4px solid var(--ink);font-weight:600}
.cp .issue-nav a{color:var(--ink)}
.cp .shelf{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-top:14px}
.cp .shelf a{display:flex;flex-direction:column;border:2px solid var(--line);background:var(--bg);color:var(--ink);text-decoration:none;box-shadow:4px 4px 0 var(--line);transition:transform .12s,box-shadow .12s}
.cp .shelf a:hover,.cp .shelf a:focus-visible{transform:translate(-2px,-2px);box-shadow:6px 6px 0 #0072B2}
.cp .shelf .pic{display:block;aspect-ratio:4/3;border-bottom:2px solid var(--line);overflow:hidden;background:#1b1f27}
.cp .shelf .photo{object-position:right center}
.cp .shelf .txt{display:flex;flex-direction:column;gap:2px;padding:10px 12px 12px}
.cp .shelf .num{font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
.cp .shelf b{font:400 22px/1.1 var(--display)}
.cp .cloud{--g0:#0072B2;--g1:#9C4798;--g2:#007A5A;--g3:#000}
:root[data-theme="dark"] .cp .cloud{--g0:#56B4E9;--g1:#C85BC3;--g2:#009E73;--g3:#F2F2F2}
@media (max-width:1060px){.cp .contents{flex-wrap:wrap;justify-content:flex-start}}
@media (max-width:900px){.cp .shelf{grid-template-columns:repeat(3,minmax(0,1fr))}.cp .sgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.cp .shelf{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cp .grp{grid-template-columns:1fr;gap:6px}
  .cp .blocks{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cp .sgrid{grid-template-columns:1fr}
  .cp .chapter.wk .yr small{position:static;display:inline;margin-left:10px}}
.cp:has(> .ft) > .back,.cp:has(> .ft) > .note{margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .ft{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}  /* the timelines run wide */
.cp .ft > .intro{font-size:17px;line-height:1.5;color:var(--ink)}
.cp .ft h3{font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
.cp .ps{display:inline-block;font:600 10.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:#000;background:#fff;border:2px solid var(--line);padding:0 5px;white-space:nowrap}
.cp .ft .mt td:last-child,.cp .ft .mt th:last-child{text-align:left;white-space:normal}
.cp .ft .mt td.when{white-space:nowrap}
/* rule echoes: a row per subject on one timeline, each place's flag where it first acted, ringed by how far it got */
.cp .ec-legend{display:flex;flex-wrap:wrap;gap:8px 22px;margin:14px 0 0;font-size:14px}
.cp .ec-legend > span{display:inline-flex;align-items:center;gap:10px}
.cp .ec-legend .pin{position:relative;margin:0}
.cp .ec-wrap{overflow-x:auto;margin-top:14px;border:2px solid var(--line);background:var(--bg);box-shadow:5px 5px 0 var(--line)}
.cp .ec{min-width:760px;padding:0 22px 6px 0}
.cp .ec-axis,.cp .er > summary{display:grid;grid-template-columns:210px minmax(0,1fr);align-items:center}
.cp .ec-axis{border-bottom:2px solid var(--line);background:var(--bg)}
.cp .yrs{position:relative;display:block;height:30px;font:600 11.5px var(--mono);color:var(--muted)}
.cp .yrs > span{position:absolute;top:9px;white-space:nowrap;padding-left:5px;border-left:1px solid color-mix(in srgb,var(--ink) 35%,transparent)}
.cp .yrs .now{transform:translateX(-100%);padding:0 5px 0 0;border:0;border-right:3px solid var(--ink);color:var(--ink)}
.cp .er{border-bottom:1px solid color-mix(in srgb,var(--ink) 18%,transparent)}
.cp .er:last-child{border-bottom:0}
.cp .er > summary{list-style:none;cursor:pointer;padding:14px 0}
.cp .er > summary::-webkit-details-marker{display:none}
.cp .er > summary:hover,.cp .er[open] > summary{background:color-mix(in srgb,#F0E442 30%,var(--bg))}
.cp .er .nm{position:relative;padding:0 12px 0 34px;font-weight:600;font-size:15px;line-height:1.25}
.cp .er .nm::before{content:"+";position:absolute;left:12px;top:-1px;font:700 16px var(--mono);color:var(--accent)}
.cp .er[open] .nm::before{content:"−"}
.cp .er .nm small{display:block;margin-top:2px;color:var(--muted);font:500 11px var(--mono);letter-spacing:.04em}
.cp .trk{position:relative;display:block;min-height:24px;height:var(--h)}
.cp .yl,.cp .tn{position:absolute;top:-14px;bottom:-14px;width:1px;background:color-mix(in srgb,var(--ink) 12%,transparent)}
.cp .tn{width:2px;background:color-mix(in srgb,var(--accent) 55%,transparent)}
.cp .pin{position:absolute;top:var(--t,0);display:block;margin-left:-15px;width:30px;height:23px;transition:transform .12s;z-index:1}
.cp .pin img{display:block;width:30px;height:23px;object-fit:cover;border:2px solid var(--line);box-sizing:border-box;background:#fff}
.cp .pin.r4 img{outline:3px solid #009E73;outline-offset:1px}
.cp .pin.r4::after{content:"✓";position:absolute;right:-9px;top:-9px;width:15px;height:15px;border-radius:50%;background:#009E73;color:#000;border:2px solid var(--line);font:700 9px/15px var(--body);text-align:center;box-sizing:border-box}
.cp .pin.r2 img,.cp .pin.r3 img{outline:3px solid #56B4E9;outline-offset:1px}
.cp .pin.r0 img{opacity:.4;border-style:dashed}
.cp .pin:hover{transform:scale(1.25);z-index:3}
.cp .er .det{padding:2px 18px 18px 34px}
.cp .er .det p{margin:8px 0 4px;line-height:1.5}
/* harm → rule: a panel per subject, the harms logged so far as a line and each rule a dot on it */
.cp .hps{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:16px}
.cp .hp{display:block;border:2px solid var(--line);background:var(--bg);box-shadow:5px 5px 0 var(--line);padding:12px 14px 6px;color:var(--ink);text-decoration:none}
.cp .hp:hover,.cp .hp:focus-visible{background:color-mix(in srgb,#F0E442 18%,var(--bg))}
.cp .hp-h{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.cp .hp-h b{font-size:16px}
.cp .hp-h small{color:var(--muted);font:500 11.5px var(--mono);white-space:nowrap}
.cp .hp svg{display:block;width:100%;height:auto;margin-top:4px;overflow:visible}
.cp .hp .g{stroke:color-mix(in srgb,var(--ink) 12%,transparent);stroke-width:1}
.cp .hp .ax{fill:var(--muted);font:600 11px var(--mono)}
.cp .hp .pl{fill:var(--ink);font:600 11px var(--body);paint-order:stroke;stroke:var(--bg);stroke-width:3px}
.cp .hp .area{fill:color-mix(in srgb,#D62828 16%,transparent)}
.cp .hp .cum{fill:none;stroke:#D62828;stroke-width:2.5;stroke-linejoin:round}
.cp .hd{stroke:var(--line);stroke-width:2}
.cp .hd.adopted{fill:#009E73}.cp .hd.passed{fill:#56B4E9}.cp .hd.proposed{fill:var(--bg)}
.cp .hd.withdrawn{fill:color-mix(in srgb,var(--ink) 30%,var(--bg));stroke-dasharray:2 2}
.cp .ec-legend svg{flex:none}
.cp .ec-legend .cum-key{display:inline-block;width:22px;height:0;border-top:3px solid #D62828}
.cp .er.hr > summary{display:block}.cp .er.hr .nm small{display:inline;margin-left:10px}
.cp .hr-list{margin-top:12px;border:2px solid var(--line);background:var(--bg);box-shadow:5px 5px 0 var(--line)}
@media (max-width:640px){.cp .hps{grid-template-columns:minmax(0,1fr)}}
.cp .er .det h3{margin:18px 0 0}
/* promised vs shipped: the stats, then a bar per promise from the day it was made to the day it shipped */
.cp .ps.shipped,.cp .seg.shipped,.cp .dot.shipped,.cp .chip.shipped .sw{background:#009E73}
.cp .ps.late,.cp .seg.late,.cp .dot.late,.cp .chip.late .sw{background:#F0E442}
.cp .ps.waiting,.cp .seg.waiting,.cp .dot.waiting,.cp .chip.waiting .sw{background:#56B4E9}
.cp .pstats{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);gap:20px;margin:22px 0 6px}
.cp .pstats > div{min-width:0;border:2px solid var(--line);background:var(--bg);padding:16px 18px;box-shadow:5px 5px 0 var(--line)}
.cp .st-co{grid-column:1 / -1}
.cp .obar{display:flex;gap:2px;height:30px}
.cp .obar .seg{border:2px solid var(--line);min-width:6px;border-radius:0 4px 4px 0}
.cp .olab{display:flex;gap:2px;margin-top:8px;font-size:13.5px;line-height:1.3}
.cp .olab span{min-width:0;padding-right:6px}
.cp .olab b{display:block;font:400 26px/1 var(--display)}
.cp .st-hero{display:flex;flex-direction:column;justify-content:center;gap:16px}
.cp .st-hero b{display:block;font:400 34px/1 var(--display)}
.cp .st-hero span{display:block;margin-top:4px;color:var(--muted);font-size:14px}
.cp .crs{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px}
.cp .cr{display:flex;flex-direction:column;gap:7px;padding:10px 0 0;border-top:1px solid color-mix(in srgb,var(--ink) 15%,transparent)}
.cp .cr .cw{display:flex;align-items:center;gap:8px}
.cp .cr .nm{font-weight:600}
.cp .cr .logo{width:28px;height:28px}
.cp .cr .logo svg{width:15px;height:15px}
.cp .dots{display:flex;flex-wrap:wrap;gap:4px}
.cp .dot{display:block;width:18px;height:18px;border:2px solid var(--line);transition:transform .12s}
.cp .dot:hover,.cp .dot:focus-visible{transform:scale(1.3)}
.cp .logo.none{visibility:hidden}
.cp .logo.ini{font:800 10px/1 var(--body);letter-spacing:-.02em;color:#000}  /* a company without a mark: its initials */
.cp .ft .logo{color:#000}  /* the marks drawn in currentColor stay dark on their white tile in dark mode */
.cp .ft > h2{margin-top:34px}
.cp .pf{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 0}
.cp .chip{display:inline-flex;align-items:center;gap:7px;font:600 14px var(--body);background:var(--bg);color:var(--ink);border:2px solid var(--line);border-radius:999px;padding:5px 12px;cursor:pointer}
.cp .chip b{font:600 12px var(--mono);color:var(--muted)}
.cp .chip .sw{width:12px;height:12px;border:2px solid var(--line);border-radius:50%;background:var(--ink)}
.cp .chip[aria-pressed="true"]{background:var(--ink);color:var(--bg)}
.cp .chip[aria-pressed="true"] b{color:var(--bg)}
.cp .pf .chip{border-radius:0}  /* the promise filters: rectangles, not pills */
.cp .pr-wrap{overflow:hidden;margin-top:12px;border:2px solid var(--line);background:var(--bg);box-shadow:5px 5px 0 var(--line)}
.cp .pr-head,.cp .pr{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:0 22px}
.cp .pr-head{border-bottom:2px solid var(--line);padding:8px 18px;font:600 11px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.cp .pr-list{list-style:none;margin:0;padding:0}
.cp .pr{padding:14px 18px;border-top:1px solid color-mix(in srgb,var(--ink) 18%,transparent);align-items:center}
.cp .pr:first-child{border-top:0}
.cp .pr[hidden]{display:none}
.cp .pi .top{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.cp .pi .co{font:600 11.5px var(--mono);letter-spacing:.06em;text-transform:uppercase}
.cp .pi .ps{margin-left:auto}
.cp .pi .logo{width:26px;height:26px}
.cp .pi .logo svg{width:14px;height:14px}
.cp .pi a{display:block;color:var(--ink);font-weight:600;line-height:1.35;text-decoration:none}
.cp .pi a:hover,.cp .pi a:focus-visible{text-decoration:underline}
.cp .pi .ln{margin-top:8px;padding-left:10px;border-left:4px solid #009E73}
.cp .pi .ln a{font-weight:500;font-size:14.5px}
.cp .pi .lbl{display:block;font:600 10.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .pbar{display:block;height:16px;border:2px solid var(--line);box-sizing:border-box;border-radius:0 4px 4px 0}
.cp .pbar.shipped{background:#009E73}
.cp .pbar.late{background:#F0E442}
.cp .pbar.waiting{background:#56B4E9}
.cp .lab{display:block;margin-top:5px;font:600 13px var(--body);color:var(--ink)}
@media (max-width:760px){
  .cp .pstats{grid-template-columns:1fr}
  .cp .pr-head{display:none}
  .cp .pr{grid-template-columns:1fr;gap:10px;padding:14px}
  .cp .crs{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cp .olab{flex-wrap:wrap}.cp .olab span{flex-basis:45%}
  .cp .st-hero b{font-size:28px}
  .cp .er .det{padding-left:14px}
  .cp .ft .mt thead{display:none}
  .cp .ft .mt tr{display:block;border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent);padding:8px 0}
  .cp .ft .mt td{display:block;border:0;padding:2px 0}}
/* a phone: the rule echoes are the wide-screen chart, drawn 760px wide and shrunk to fit (--z, set by the page);
   an opened subject's records are back at full size, so they stay readable */
@media (max-width:640px){
  .cp .ec-wrap{overflow:hidden}
  .cp .ec{width:760px;box-sizing:border-box;zoom:var(--z,1)}
  .cp .er .det{zoom:calc(1 / var(--z,1))}
  .cp .ec-legend{gap:8px 16px;font-size:13px}
  .cp .yrs .now{font-size:0;height:13px;padding:0}  /* only the bar: the word would sit on the last year */
  .cp .er .mt tr.first td{border-top:0}
  .cp .er .mt tr.first{border-top:2px solid var(--line)}
  .cp .er .mt td.when,.cp .er .mt td.when + td{display:inline;font:600 12px var(--mono);color:var(--muted)}
  .cp .er .mt td.when + td:not(:empty)::before{content:" · "}
  .cp .er .mt td:last-child{margin-top:3px;font:600 11px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
  .cp .er.hr .mt td:last-child{margin-top:3px;font:inherit;letter-spacing:0;text-transform:none;color:var(--ink)}}
.cp .yrs i{font-style:normal}
.cp .yrs b{font-weight:inherit}
.cp .yrs .sm{display:none}
@media (max-width:640px){.cp .yrs .lg{display:none}.cp .yrs .sm{display:inline}}
/* the month in numbers (insights.py): the yellow link in each issue, and the page's bar and column charts */
.cp .ins-link{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 20px;margin-top:22px;padding:14px 20px;background:#F0E442;color:#000;border:3px solid var(--ink);text-decoration:none}
.cp .ins-link .label{font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase}
.cp .ins-link b{display:block;font:400 24px/1.1 var(--head);margin-top:4px}
.cp .ins-link .ins-go{font:800 17px var(--body);white-space:nowrap}
.cp .ins-link:hover .ins-go{text-decoration:underline}
/* the monthly report look (issue and insights pages): ink-black heads, grey context with one blue focus, yellow tags,
   square edges. Dark mode keeps the same jobs with its own greys and the lighter blue. */
.cp .mi{--ctx:#AADAF4;--ctx2:#D9ECF6;--focus:#0072B2;--mark:#F0E442;--rule:color-mix(in srgb,var(--ink) 22%,transparent)}
:root[data-theme="dark"] .cp .mi{--ctx:#2D5670;--ctx2:#1C3240;--focus:#56B4E9}
.cp .mi .sheet > h2{display:flex;align-items:center;gap:12px;border-top:2px solid var(--line);padding-top:12px;font:400 clamp(21px,2.3vw,27px)/1.15 var(--display);text-transform:none;letter-spacing:0}
.cp .mi .sheet > h2::before{content:counter(sheet);display:inline-grid;place-items:center;flex:none;width:30px;height:30px;margin:0;background:var(--ink);color:var(--bg);font:400 15px var(--display)}
.cp .mi .contents li::before{color:var(--muted)}
.cp .mi .brief{border-left-color:var(--line)}
.cp .mi .issue-nav{border-top:2px solid var(--line)}
.cp .mi .chapter .yr span,.cp .mi .chapter:nth-child(odd) .yr span{color:var(--ink);-webkit-text-stroke:0}
.cp .mi .chapter.wk .yr small{font:600 12px var(--mono);letter-spacing:.06em;text-transform:uppercase}
@media (min-width:701px){
  .cp .mi .chapter .yr::before{top:-10px;width:16px;height:16px;border:2px solid var(--line);border-radius:0;background:var(--focus)}
  .cp .mi .chapter.wk .yr span{font-size:22px}}
/* insights: the cover, the key findings, and each exhibit headed by its finding */
.cp .ins-pdf{font:600 12px var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--ink);background:var(--bg);border:1px solid var(--ink);padding:6px 10px;cursor:pointer}
.cp .fh .ins-pdf{display:block;margin-top:10px;background:transparent;color:#000;border:2px solid #000}
.cp .ins-pdf:hover,.cp .ins-pdf:focus-visible{background:var(--mark);color:#000}
/* funding pace: a column a month, the biggest round its darker top */
.cp .ins-pace{list-style:none;margin:28px 0 0;padding:0;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:6px;align-items:end;height:200px;max-width:900px;border-bottom:1px solid var(--line)}
.cp .ins-pace li{position:relative;height:100%;display:flex;flex-direction:column;justify-content:flex-end;padding:0;border:0}
.cp .ins-pace .col{display:flex;flex-direction:column;justify-content:flex-start;background:var(--ctx);min-height:2px}
.cp .ins-pace .col i{display:block;background:color-mix(in srgb,var(--focus) 55%,var(--ctx))}
.cp .ins-pace li.now .col{background:color-mix(in srgb,var(--focus) 45%,var(--bg))}
.cp .ins-pace li.now .col i{background:var(--focus)}
.cp .ins-pace .amt{font:600 10.5px var(--mono);color:var(--muted);text-align:center;margin-bottom:3px;white-space:nowrap}
.cp .ins-pace li.now .amt{color:var(--ink)}
.cp .ins-pace .mo{position:absolute;bottom:-20px;left:0;right:0;text-align:center;font:600 11px var(--mono);color:var(--muted)}
.cp .ins-pace li.now .mo{color:var(--ink)}
.cp .ins-pace + .ins-key{margin-top:30px}
.cp .ins-key .sw.rest{background:var(--ctx)}
.cp .ins-key .sw.big{background:var(--focus)}
/* IPO watch: the year's IPO talk, then the month's headlines */
.cp .ins-ipo{display:flex;align-items:center;gap:12px;margin:0 0 10px}
.cp .ins-ipo .ins-spark{width:220px;height:30px;border-bottom:1px solid var(--line)}
.cp .ins-ipot{max-width:900px}
.cp .ins-ipot td a{font-weight:600}
.cp .ins-ipot td.when{font:600 12px var(--mono);color:var(--muted)}
/* the key findings as a departures board: fixed dark in both themes, split-flap numbers, each exhibit's colour */
.cp .ins-kf{--board:#F0E442;margin-top:24px;padding:14px 16px 8px;background:#141925;color:#F2F2F2;border:1px solid var(--line)}
.cp .bd-top{display:flex;justify-content:space-between;align-items:center;gap:12px;padding-bottom:10px;border-bottom:1px solid #3A4150;font:600 12px var(--mono);letter-spacing:.14em;text-transform:uppercase}
.cp .bd-t{color:#141925;background:var(--board);padding:2px 8px}
.cp .bd-c{color:var(--board)}
.cp .kf{width:100%;border-collapse:collapse;perspective:600px}
.cp .kf th{text-align:left;font:600 10.5px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:#8A93A3;padding:10px 12px 6px 0}
.cp .kf th:last-child{text-align:right;padding-right:0}
.cp .kf td{border-top:1px solid #2A303C;padding:8px 12px 8px 0;vertical-align:middle;font:400 14.5px/1.45 var(--mono);color:#F2F2F2}
.cp .kf .no{width:58px;white-space:nowrap}
.cp .fl{position:relative;display:inline-grid;place-items:center;width:20px;height:26px;margin-right:2px;background:linear-gradient(#262C39 50%,#1D222D 50%);color:var(--board);font:600 15px var(--mono);border-radius:2px}
.cp .fl::after{content:"";position:absolute;left:0;right:0;top:50%;border-top:1px solid #0B0E13}
.cp .kf .air{display:inline-block;width:10px;height:10px;margin-right:10px;background:var(--hue);vertical-align:0}
.cp .kf .st{white-space:nowrap;font:600 10.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--board)}
.cp .kf .gt{white-space:nowrap;text-align:right;padding-right:0}
.cp .kf .gt a{display:inline-flex;align-items:center;gap:6px;color:var(--board);text-decoration:none;font:600 11px var(--mono);letter-spacing:.08em}
.cp .kf .gt .fl{width:16px;height:22px;font-size:13px}
.cp .kf .gt a:hover .fl,.cp .kf .gt a:focus-visible .fl{background:var(--board);color:#141925}
@media (prefers-reduced-motion:no-preference){
  .cp .kf .fl{animation:ins-flap .5s cubic-bezier(.3,1.4,.5,1) both;animation-delay:calc(var(--i) * 70ms)}
  .cp .kf .fd{animation:ins-fade .4s both;animation-delay:calc(var(--i) * 70ms + 150ms)}}
@keyframes ins-flap{from{transform:rotateX(90deg)}to{transform:none}}
@keyframes ins-fade{from{opacity:0}to{opacity:1}}
.cp .ex{--ctx:color-mix(in srgb,var(--hue) 38%,var(--bg));--ctx2:color-mix(in srgb,var(--hue) 18%,var(--bg));--focus:var(--hue);margin-top:52px;padding-top:12px;border-top:3px solid var(--hue);scroll-margin-top:calc(var(--bar-h,64px) + 12px)}
.cp .ex-k{display:flex;align-items:baseline;gap:12px;margin:0;font:600 12px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.cp .ex-k b{background:var(--hue);border:1px solid var(--line);color:#141925;padding:0 6px;font-weight:600}
.cp .mi .ex h2{border:0;padding:0;margin:10px 0 16px;font:400 clamp(20px,2.2vw,26px)/1.3 var(--body);text-transform:none;letter-spacing:0}
.cp .ins-say{font-size:16px;line-height:1.5;margin:-8px 0 18px;color:var(--muted)}
.cp .ins-note{font-size:13px;color:var(--muted);margin:8px 0 0}
.cp .ex > .ins-note:last-child{margin-top:14px;padding-top:8px;border-top:1px solid var(--rule);max-width:none}
.cp .call{position:absolute;top:50%;z-index:1;transform:translateY(-50%);margin-left:10px;background:var(--mark);color:#000;border:2px solid #000;font:600 11.5px/1.25 var(--mono);padding:2px 6px;white-space:nowrap}
.cp .call.in{transform:translate(-100%,-50%);margin-left:-6px}
.cp .ins-key{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;color:var(--muted);margin:0 0 10px}
.cp .ins-key span{display:inline-flex;align-items:center;gap:6px}
.cp .ins-key .sw{width:13px;height:13px;background:var(--ink);border:2px solid var(--line)}
.cp .ins-key .sw.us{background:var(--bg)}
.cp .ins-key .sw.dk-compute,.cp .ins-bars .tr i.dk-compute{background:#E69F00}
.cp .ins-key .sw.dk-acquisition,.cp .ins-bars .tr i.dk-acquisition{background:#CC79A7}
/* bars: grey, one in the focus colour */
.cp .ins-bars{list-style:none;margin:0;padding:0;max-width:820px}
.cp .ins-bars li{display:grid;grid-template-columns:minmax(90px,170px) minmax(0,1fr) 54px 64px;align-items:center;gap:12px;padding:4px 0;border:0}
.cp .ins-bars .nm{font-weight:600;font-size:14.5px;overflow-wrap:anywhere}
.cp .ins-bars .tr{position:relative;height:18px}
.cp .ins-bars .tr i{display:block;height:100%;background:var(--c,var(--ctx));min-width:3px}
.cp .ins-bars li.on .tr i{background:var(--focus)}
.cp .ins-bars .v{font:600 17px/1 var(--body);text-align:right}
.cp .ins-bars .ch{font:600 12.5px var(--mono);color:var(--muted);text-align:right;white-space:nowrap}
.cp .ins-bars li.on .ch{color:var(--ink)}
.cp .ins-bars li:hover .nm{text-decoration:underline}
.cp .ins-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 34px}
.cp .ins-two h3,.cp .ins-h{margin:0 0 8px;font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
/* how this month compares: usual (hollow) and now (filled) on one scale */
.cp .ins-db{list-style:none;margin:0;padding:0;max-width:900px}
.cp .ins-db li,.cp .ins-axis{display:grid;grid-template-columns:minmax(90px,130px) minmax(0,1fr) 64px minmax(80px,150px);gap:14px;align-items:center}
.cp .ins-db li{min-height:42px;padding:0;border:0;border-top:1px solid var(--rule)}
.cp .ins-db li:last-child{border-bottom:1px solid var(--rule)}
.cp .ins-db .nm{font-weight:600}
.cp .ins-db .trk{position:relative;align-self:stretch}
.cp .ins-db .trk::before{content:"";position:absolute;left:0;right:0;top:50%;border-top:1px dotted var(--ctx)}
.cp .ins-db .trk i{position:absolute;top:50%}
.cp .ins-db .seg{height:4px;margin-top:-2px;background:var(--ink)}
.cp .ins-db .us{width:14px;height:14px;margin:-7px 0 0 -7px;border:2px solid var(--ink);background:var(--bg)}
.cp .ins-db .now{width:18px;height:18px;margin:-9px 0 0 -9px;background:var(--c);border:2px solid var(--line)}
.cp .ins-db .call{margin-left:16px}
.cp .ins-db .v{font:600 18px/1 var(--body);text-align:right}
.cp .ins-db .ch{font:600 12.5px var(--mono);color:var(--muted)}
.cp .ins-db .ch small{display:block;font-size:11.5px}
.cp .ins-db li.on .ch{color:var(--ink)}
.cp .ins-axis{max-width:900px;height:22px}
.cp .ins-axis .tk{position:relative;align-self:stretch}
.cp .ins-axis .tk span{position:absolute;top:4px;transform:translateX(-50%);font:600 11px var(--mono);color:var(--muted)}
.cp .ins-axis .tk span:first-child{transform:none}
/* the busiest days: columns, a normal-weekday line, numbered tags, and a table of what drove them */
.cp .ins-plot{position:relative;max-width:900px;margin:40px 0 26px}
.cp .ins-days{list-style:none;margin:0;padding:0;height:170px;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:3px;align-items:end;border-bottom:2px solid var(--line)}
.cp .ins-days li{position:relative;height:100%;display:flex;align-items:flex-end;padding:0;border:0}
.cp .ins-days i{display:block;width:100%;background:var(--ctx);min-height:2px}
.cp .ins-days li.we i{background:var(--ctx2)}
.cp .ins-days li.pk i{background:var(--focus)}
.cp .ins-days li:hover i{outline:2px solid var(--ink)}
.cp .ins-days span{position:absolute;bottom:-20px;left:50%;transform:translateX(-50%);font:600 11px var(--mono);color:var(--muted)}
.cp .ins-days li.pk span{color:var(--ink)}
.cp .ins-days li .mk{position:absolute;left:50%;transform:translateX(-50%)}
.cp .mk{display:inline-grid;place-items:center;width:20px;height:20px;background:var(--mark);color:#000;border:2px solid #000;font:600 11px var(--mono)}
.cp .ins-plot .ref{position:absolute;left:0;right:0;border-top:2px dashed var(--muted);pointer-events:none}
.cp .ins-plot .ref em{position:absolute;left:0;top:-19px;font:600 11px var(--mono);font-style:normal;color:var(--muted);background:var(--bg);padding-right:6px}
.cp .ins-drv{max-width:900px;margin-top:18px}
.cp .ins-drv .dt{white-space:nowrap;font-weight:600}
.cp .ins-drv .dt .mk{margin-right:8px;vertical-align:1px}
.cp .ins-drv ol{list-style:none;margin:0;padding:0}
.cp .ins-drv li{padding:0 0 6px;border:0;font-size:14.5px;line-height:1.35}
.cp .ins-drv li:last-child{padding:0}
.cp .ins-drv li a{color:var(--ink);font-weight:600;text-decoration:none}
.cp .ins-drv li a:hover{text-decoration:underline}
.cp .ins-drv .n,.cp .ins-deals .n{font:600 17px var(--body)}
.cp .ins-drv .n small{display:block;font:600 11.5px var(--mono);color:var(--muted)}
/* money moves: three figures, rounds by theme, valuations (a table), deals by size */
.cp .ins-score{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));max-width:900px;margin:0 0 24px;border-top:2px solid var(--line);border-bottom:2px solid var(--line)}
.cp .ins-score div{padding:10px 14px 12px 0}
.cp .ins-score div + div{border-left:1px solid var(--rule);padding-left:14px}
.cp .ins-score b{display:block;font:400 clamp(26px,3vw,34px)/1.05 var(--body)}
.cp .ins-score span{font-size:13.5px;color:var(--muted)}
.cp .ins-score a{color:var(--ink);font-weight:600}
.cp .ins-fund li{grid-template-columns:minmax(80px,140px) minmax(0,1fr) 30px 58px}
.cp .ins-val{margin-top:0}
.cp .ins-val td{padding:7px 10px 7px 0;vertical-align:middle}
.cp .ins-val .ch{font:600 12px var(--mono);color:var(--muted);white-space:nowrap}
.cp .ins-val .n{font:600 17px var(--body)}
.cp .ins-money + .ins-h{margin-top:26px}
.cp .ins-deals{max-width:900px}
.cp .ins-deals li{grid-template-columns:minmax(150px,250px) minmax(0,1fr) 72px}
.cp .ins-deals .nm a{color:var(--ink);text-decoration:none}
.cp .ins-deals .nm a:hover{text-decoration:underline}
.cp .ins-deals + .ins-key{margin:10px 0 0}
.cp .dk{display:inline-block;font:600 10.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:#141925;border:2px solid var(--line);padding:1px 6px;white-space:nowrap}
.cp .dk-acquisition{background:#CC79A7}
.cp .dk-compute{background:#E69F00}
.cp .rep{display:inline-block;margin-left:6px;font:600 10px var(--mono);letter-spacing:.05em;text-transform:uppercase;color:var(--muted);border:1px solid currentColor;padding:0 4px;vertical-align:1px}
/* US vs China: split bars and China's share over the year */
.cp .ins-spark{display:flex;align-items:flex-end;gap:2px;height:34px;border-bottom:2px solid var(--line)}
.cp .ins-spark i{flex:1;background:var(--ctx);min-height:2px}
.cp .ins-spark i.now{background:var(--c)}
.cp .ins-riv li{grid-template-columns:minmax(90px,150px) minmax(0,1fr) 110px minmax(0,150px)}
.cp .ins-riv .split{display:flex;height:22px;gap:2px}
.cp .ins-riv .split i{display:flex;align-items:center;font:600 11.5px var(--mono);font-style:normal;color:#141925;padding:0 6px;white-space:nowrap;overflow:hidden;min-width:0;box-sizing:border-box}
.cp .ins-riv .split .us{background:#56B4E9}
.cp .ins-riv .split .cn{background:#E69F00;justify-content:flex-end}
.cp .ins-riv .ins-spark{height:22px}
.cp .ins-riv .ins-spark i.now{--c:#E69F00}
.cp .ins-riv .ch{text-align:left}
.cp .ins-opens{font-size:14px;margin:12px 0 0}
/* legal and risk: a shaded table */
.cp .ins-risk{max-width:620px}
.cp .ins-risk td,.cp .ins-risk th{padding:6px 10px 6px 0}
.cp .ins-risk th:not(:first-child),.cp .ins-risk td.hx{text-align:center;width:90px}
.cp .ins-risk td:first-child{font-weight:600}
.cp .ins-risk td.hx{font:600 17px var(--body);background:color-mix(in srgb,#F85C48 var(--a),transparent)}
.cp .ins-risk td.z{color:var(--muted);background:none;font:400 14px var(--body)}
/* themes rising and fading: was → now */
.cp .ins-move{list-style:none;margin:0;padding:0}
.cp .ins-move li{display:grid;grid-template-columns:minmax(0,1fr) 44px 18px 40px 18px;align-items:baseline;gap:8px;padding:7px 0;border:0;border-top:1px solid var(--rule)}
.cp .ins-move li:last-child{border-bottom:1px solid var(--rule)}
.cp .ins-move .nm{font-weight:600;font-size:15px}
.cp .ins-move .was{font:600 13px var(--mono);color:var(--muted);text-align:right}
.cp .ins-move .to{color:var(--muted);text-align:center}
.cp .ins-move .v{font:600 17px/1 var(--body);text-align:right}
.cp .ins-move .ar{font-size:12px;text-align:center}
.cp .ins-move .ar.up{color:var(--c-tool)}
.cp .ins-move .ar.dn{color:var(--c-reg)}
/* where in the world: tiles, darker = more stories (fixed light tiles in both themes) */
.cp .ins-tiles{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px}
.cp .ins-tiles li{display:flex;flex-direction:column;gap:2px;padding:10px 12px;border:1px solid var(--line);background:color-mix(in srgb,var(--hue) var(--a),#fff);color:#141925}
.cp .ins-tiles .nm{font-weight:600;font-size:14px;line-height:1.2}
.cp .ins-tiles b{font:400 26px/1.1 var(--body)}
.cp .ins-tiles .ch{font:600 12px var(--mono)}
@media (max-width:1000px){.cp .ins-tiles{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media print{
  body:has(.ins-top) header.top,body:has(.ins-top) footer,body:has(.ins-top) .back,.cp .ins-pdf,.cp .mi .issue-nav{display:none!important}
  body:has(.ins-top){background:#fff!important;color:#000}
  .cp .mi,:root[data-theme] .cp .mi{--bg:#fff;--ink:#000;--muted:#3B3B3B;--line:#000;--ctx:#AADAF4;--ctx2:#D9ECF6;--focus:#0072B2;
    --f-tool:#009E73;--f-news:#56B4E9;--f-research:#C85BC3;--f-reg:#F85C48;--f-policy:#E69F00;--f-infra:#8BEC8B;--f-all:#F0E442}
  .cp .ex{break-inside:avoid;page-break-inside:avoid;margin-top:28px}
  .cp .ins-kf{break-after:page}
  .cp .kf .fl,.cp .kf .fd{animation:none!important}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
@media (max-width:700px){
  .cp .kf thead,.cp .kf .gt span{display:none}
  .cp .kf .st{font-size:9px;letter-spacing:.04em;white-space:normal;width:44px}
  .cp .kf td{font-size:13px}
  .cp .kf .no{width:50px}
  .cp .ins-kf{padding:12px 10px 6px}
  .cp .ins-two,.cp .ins-score{grid-template-columns:1fr}
  .cp .ins-score div + div{border-left:0;border-top:1px solid var(--rule);padding-left:0}
  .cp .ins-db li,.cp .ins-axis{grid-template-columns:76px minmax(0,1fr) 48px;gap:8px}
  .cp .ins-db .ch{grid-column:2 / -1;padding-bottom:6px}
  .cp .ins-db .call{display:none}
  .cp .ins-bars li{grid-template-columns:minmax(76px,110px) minmax(0,1fr) 44px 50px;gap:7px}
  .cp .ins-fund li{grid-template-columns:minmax(70px,100px) minmax(0,1fr) 26px 52px}
  .cp .ins-deals li{grid-template-columns:minmax(0,1fr) 64px;row-gap:4px}
  .cp .ins-deals .tr{grid-column:1 / -1;grid-row:2}
  .cp .ins-riv li{grid-template-columns:minmax(70px,90px) minmax(0,1fr) 70px;row-gap:2px}
  .cp .ins-riv .ch{grid-column:2 / -1;font-size:12px}
  .cp .ins-days{height:120px}
  .cp .ins-tiles{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cp .call.in{display:none}
  .cp .ins-drv thead{display:none}
  .cp .ins-drv tr{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:6px 10px;border-top:1px solid var(--rule);padding:10px 0}
  .cp .ins-drv td{display:block;border:0;padding:0}
  .cp .ins-drv td:nth-child(2){grid-column:1 / -1;grid-row:2}
  .cp .ins-drv td.n{grid-column:2;grid-row:1}}
/* Phones: long lists scroll inside their own box and rows of cards swipe sideways (the front page's rule, for these pages) */
@media (max-width:640px){
  .cp .topics,.cp .sgrid,.cp .blocks,.cp .tiles{display:flex;flex-direction:row;overflow-x:auto;overscroll-behavior-x:contain;scroll-snap-type:x mandatory;gap:12px;padding:0 4px 10px 0;align-items:stretch}
  .cp .topics>*,.cp .sgrid>*{flex:0 0 84%;min-width:0;scroll-snap-align:start}
  .cp .blocks>*{flex:0 0 72%;min-width:0;scroll-snap-align:start}
  .cp .tiles>*{flex:0 0 46%;min-width:0;scroll-snap-align:start}
  .cp .topics .pic{height:130px}
  .cp .places{grid-auto-flow:column;grid-template-rows:repeat(2,auto);grid-template-columns:none;grid-auto-columns:46%;overflow-x:auto;overscroll-behavior-x:contain;scroll-snap-type:x mandatory;padding-bottom:10px}
  .cp .places>*{scroll-snap-align:start;min-width:0}
  .cp > ul,.cp .pr-list,.cp #az,#kind-stories,#word-stories{display:block;max-height:72vh;overflow-y:auto;overscroll-behavior-y:contain;border-bottom:3px solid var(--ink)}
  .cp table.mt.sl{display:block;overflow-x:auto}  /* Storylines that moved: swipe for the date and the rest */
  .cp .mt.sl td:nth-child(2),.cp .mt.sl td:nth-child(3){min-width:170px}
}
/* Jobs blamed on AI: the question, one plain bar per reason, then a chapter per reason with its cuts */
.cp .jb-q{font:400 clamp(20px,2.6vw,26px)/1.3 var(--body);margin:0 0 10px}
.cp .jb .jb-answer > .intro,.cp .jb .jb-ch > .intro{font-size:17px;line-height:1.5;color:var(--ink)}
.cp .jb-split{display:flex;flex-wrap:wrap;gap:16px 44px;align-items:center;margin-top:8px}
.cp .jb-ring{width:230px;flex:none;fill:none;stroke-width:26}
.cp .jb-ring text{fill:var(--muted);stroke:none;font:500 13px var(--mono);text-anchor:middle}
.cp .jb-ring text.big{fill:var(--ink);font:400 40px var(--head)}
.cp .jb-rt{flex:1;min-width:300px}
.cp .jb-rt td.n{font:600 14px var(--mono);white-space:nowrap}
.cp .jb-rt .sw{display:inline-block;width:11px;height:11px;border-radius:50%;background:var(--c);margin-right:9px}
.cp .jb-note{color:var(--muted);font-size:14px;margin:10px 0 0}
.cp .jb h2{font:600 20px var(--body);text-transform:none;letter-spacing:0;border:0;padding:0;margin:44px 0 10px}
.cp .jb h2::before{display:none}
.cp .jb-col{flex:none;max-width:100%;height:auto}
.cp .jb-col text{fill:var(--muted);font:500 12px var(--mono);text-anchor:middle}
.cp .jb-col text.top{fill:var(--ink);font-weight:600}
.cp .jb-col line{stroke:var(--muted)}
.cp .jb .jb-split .jb-small{align-self:flex-end}
.cp .jb table.jb-small{width:auto;font-size:13.5px}
.cp .jb-small td,.cp .jb-small th{padding:5px 22px 5px 0}
.cp .jb-small td.n{font:500 13px var(--mono);white-space:nowrap}
.cp .jb table.jb-limits{color:var(--muted)}
.cp .jb-limits td:first-child{width:30%}
.cp .jb-ch{margin:28px 0;padding:18px 22px 8px;background:color-mix(in srgb,var(--c) 9%,var(--bg));border-radius:6px}
.cp .jb-ch h3{font:600 20px var(--body);text-transform:none;letter-spacing:0;margin:0}
.cp .jb-ch h3 span{font:500 13px var(--mono);text-transform:none;letter-spacing:0;color:var(--muted);margin-left:10px;white-space:nowrap}
.cp .jb-ch > p{margin:4px 0 10px;color:var(--muted);font-size:15px}
.cp .jb-cuts{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:0 28px}
.cp .jb-cuts li{padding:12px 0;border-top:1px solid color-mix(in srgb,var(--ink) 12%,transparent)}
.cp .jb-cuts .co{font:600 16px var(--body)}
.cp .jb-cuts .said{font-size:16px;margin:2px 0 4px}
.cp .jb-cuts .meta{font:500 12px var(--mono);color:var(--muted)}
.cp .jb-cuts .src{font-size:11.5px;color:var(--muted);margin-top:3px;line-height:1.35}
.cp .ft .jb-cuts .src a{font-weight:400;color:var(--muted);text-decoration:underline}
/* Papers that made the news: the papers as a newspaper page (the newest leads, the rest in columns), then the
   subjects in a plain table */
.cp .np{margin:28px 0 8px;border-top:4px double var(--ink);border-bottom:4px double var(--ink);padding:0 0 18px}
.cp .np-mast{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font:600 12px var(--mono);text-transform:uppercase;letter-spacing:.08em;padding:8px 0;border-bottom:1px solid var(--ink)}
.cp .np-clip h3{font:700 21px/1.25 Georgia,'Times New Roman',serif;margin:4px 0 8px;letter-spacing:0;text-transform:none}
.cp .np-clip h3 a{color:var(--ink);text-decoration:none}
.cp .np-clip h3 a:hover{text-decoration:underline}
.cp .np-kick{font:600 11px var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.cp .np-deck{font:400 16px/1.5 Georgia,'Times New Roman',serif;margin:0 0 8px}
.cp .np-by{font-size:12px;color:var(--muted);margin:2px 0 0;line-height:1.4}
.cp .ft .np-by a{font-weight:400;color:var(--muted);text-decoration:underline}
.cp .np-lead{padding:20px 0;border-bottom:1px solid var(--ink);text-align:center;max-width:820px;margin:0 auto}
.cp .np-lead h3{font-size:clamp(26px,3.4vw,38px);line-height:1.15}
.cp .np-lead .np-deck{font-size:19px;font-style:italic}
.cp .np-cols{column-count:3;column-gap:28px;column-rule:1px solid color-mix(in srgb,var(--ink) 25%,transparent);margin-top:16px}
.cp .np-cols .np-clip{break-inside:avoid;padding:0 0 14px;margin:0 0 14px;border-bottom:1px solid color-mix(in srgb,var(--ink) 25%,transparent)}
.cp .pn > .intro{max-width:none}
.cp .pn-foot{display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-top:40px;font-size:14px}
.cp .pn-foot h2{font:600 13px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 8px;border:0;padding:0}
.cp .pn-foot h2::before{display:none}
.cp .pn-foot .mt td{padding:6px 12px 6px 0;font-weight:400}
.cp .pn-num b{font-weight:600;margin-right:2px}
.cp .pn-notes td:first-child{width:30%;color:var(--muted)}
.cp .pn-notes td:last-child{text-align:left;white-space:normal}
@media (max-width:760px){.cp .pn-foot{grid-template-columns:1fr}}
.cp .pn-pc{color:var(--muted);font-size:13px}
@media (max-width:900px){.cp .np-cols{column-count:2}}
@media (max-width:640px){.cp .np-cols{column-count:1}.cp .np-lead{text-align:left}}
@media (max-width:640px){.cp .jb-ring{margin:0 auto}.cp .jb-ch{padding:14px 14px 4px}}
/* AI in court: the ring of where cases stand, small tables by country and kind, then a table of cases per kind */
.cp .ct > .intro{max-width:none}
.cp .ct .ct-small{align-items:flex-start;margin-top:22px}
.cp .ct .jb-split.ct-small .jb-small{align-self:flex-start}
.cp .ct-kind{margin:30px 0}
.cp .ct-board{display:grid;grid-template-columns:3fr 2fr;gap:18px 40px;margin-top:6px}
.cp .ct-head{font:500 15px var(--body);border-bottom:2px solid var(--ink);padding-bottom:6px;margin-bottom:4px}
.cp .ct-head b{font:400 36px var(--head);margin-right:6px}
.cp .ct-head span{display:block;color:var(--muted);font-size:13px}
.cp .ct-row{display:grid;grid-template-columns:1fr auto;gap:4px 12px;align-items:center;padding:8px 0;border-bottom:1px solid color-mix(in srgb,var(--ink) 12%,transparent)}
.cp .ct-lab{font:600 14.5px var(--body)}
.cp .ct-lab::before{content:"";display:inline-block;width:10px;height:10px;background:var(--c);margin-right:8px;vertical-align:1px}
.cp .jb .ct-tables table.jb-small{font-size:15.5px}
.cp .ct-tables .jb-small td,.cp .ct-tables .jb-small th{padding:7px 26px 7px 0}
.cp .ct-tables .jb-small td.n{font-size:15px}
.cp .ct-n{font:600 15px var(--mono)}
.cp .ct-names{grid-column:1/-1;font-size:12.5px;color:var(--muted);line-height:1.45}
@media (max-width:760px){.cp .ct-board{display:flex;flex-direction:column}.cp .ct-board > div:first-child{display:contents}.cp .ct-board .ct-panel{order:1}.cp .ct-board .ct-small{order:3}}
@media (max-width:640px){.cp .ft .ct-small .mt thead{display:table-header-group}.cp .ft .ct-small .mt tr{display:table-row;padding:0}.cp .ft .ct-small .mt td{display:table-cell;border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent);padding:5px 18px 5px 0}}
.cp .ct-kind h3{font:600 20px var(--body);text-transform:none;letter-spacing:0;margin:0}
.cp .ct-kind h3 span{font:500 13px var(--mono);color:var(--muted);margin-left:10px;white-space:nowrap}
.cp .ct-kind > p{margin:4px 0 0;color:var(--muted);font-size:15px}
.cp .ct-st{display:inline-block;background:var(--c);color:#111;font:700 12.5px var(--body);letter-spacing:.07em;text-transform:uppercase;padding:4px 11px;border-radius:999px;box-shadow:0 0 0 3px color-mix(in srgb,var(--c) 30%,transparent)}
.cp .ct-stamp{display:inline-block;color:color-mix(in srgb,var(--c) 75%,var(--ink));border:3px double currentColor;font:800 13px var(--mono);letter-spacing:.12em;text-transform:uppercase;padding:3px 9px;transform:rotate(-5deg);border-radius:4px}
.cp .ct{--gavel:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cg transform='rotate(-40 12 10)'%3E%3Crect x='5' y='2' width='12' height='7' rx='1.5'/%3E%3Crect x='9.6' y='9' width='2.8' height='11' rx='1.2'/%3E%3C/g%3E%3Crect x='2' y='20' width='12' height='3.5' rx='1'/%3E%3C/svg%3E")}
.cp .ct-firms{margin-top:28px}
.cp .ct-firms h4{font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
.cp .ct-firms ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:0 28px}
.cp .ct-firms li{padding:7px 0;border-top:1px solid color-mix(in srgb,var(--ink) 18%,transparent);display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.cp .ct-firms li b{font:600 14px var(--body)}
.cp .ct-firms li span{font:500 12px var(--mono);color:var(--muted);white-space:nowrap}
@media (max-width:640px){.cp .ct-firms ul{grid-template-columns:1fr 1fr;gap:0 16px}.cp .ct-firms li{display:block}.cp .ct-firms li span{display:block;margin-top:2px}}
.cp .ct-d{display:block;font:600 11px var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.cp .ct-docket{margin-top:14px;border-top:2px solid var(--ink)}
.cp .ct-dhead,.cp .ct-case-row > summary,.cp div.ct-case-row{display:grid;grid-template-columns:170px minmax(0,2fr) 110px minmax(0,1.6fr) 74px;gap:0 18px;align-items:start}
.cp .ct-dhead{font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:8px 12px 8px 17px;border-bottom:2px solid var(--ink)}
.cp .ct-case-row{border-bottom:1px solid color-mix(in srgb,var(--ink) 15%,transparent);border-left:5px solid var(--c)}
.cp div.ct-case-row,.cp .ct-case-row > summary{padding:13px 12px}
.cp .ct-case-row > summary{list-style:none;cursor:pointer}
.cp .ct-case-row > summary::-webkit-details-marker{display:none}
.cp .ct-case-row > summary:hover{background:color-mix(in srgb,var(--c) 7%,var(--bg))}
.cp .ct-case b{font:700 16px/1.3 var(--body)}
.cp .ct-case i{font-style:normal;color:var(--muted);margin:0 2px}
.cp .ct-about{display:block;font:500 14px/1.4 var(--body);color:var(--muted);margin-top:3px}
.cp .ct-court{font:500 15px var(--body)}
.cp .ct-n2{text-align:right}
.cp .ct-n2 span{display:inline-block;font:600 12px var(--mono);white-space:nowrap;border:1px solid color-mix(in srgb,var(--ink) 30%,transparent);border-radius:4px;padding:2px 7px}
.cp details.ct-case-row .ct-n2 span::after{content:" ▾"}
.cp details.ct-case-row[open] .ct-n2 span{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.cp details.ct-case-row[open] .ct-n2 span::after{content:" ▴"}
.cp details.ct-case-row[open] > summary{background:color-mix(in srgb,var(--c) 7%,var(--bg))}
.cp .ct-track{list-style:none;margin:0;padding:0;font-size:14.5px;line-height:1.4}
.cp .ft .ct-track li{border:0;padding:0}
.cp .ft .ct-track a,.cp .ft .ct-line a{font-weight:400;color:var(--muted);text-decoration:underline}
.cp .ct-line{list-style:none;display:flex;margin:0;padding:22px 16px 14px;font-size:13.5px;line-height:1.4;background:color-mix(in srgb,var(--c) 4%,var(--bg))}
.cp .ft .ct-line li{flex:1;position:relative;padding:16px 18px 0 0;border:0;border-top:3px solid var(--c)}
.cp .ct-line li::before{content:"";position:absolute;left:0;top:-9px;width:13px;height:13px;border-radius:50%;background:var(--c);box-shadow:0 0 0 2px var(--bg)}
.cp .ct-line li.ct-rule::before{width:19px;height:19px;top:-12px;border-radius:0;box-shadow:none;-webkit-mask:var(--gavel) center/contain no-repeat;mask:var(--gavel) center/contain no-repeat}
.cp .ct-court .ct-d{margin-top:3px}
@media (max-width:900px){.cp .ct-dhead{display:none}.cp .ct-case-row > summary,.cp div.ct-case-row{grid-template-columns:1fr auto;gap:8px 12px}.cp .ct-case,.cp .ct-last{grid-column:1/-1}.cp .ct-mark{order:-2}.cp .ct-n2{order:-1}.cp .ct-court{grid-column:1/-1;display:flex;gap:10px;align-items:baseline}.cp .ct-court .ct-d{margin:0}.cp .ct-line{flex-direction:column;gap:14px;padding:12px 14px 14px 22px}.cp .ft .ct-line li{border-top:0;border-left:3px solid var(--c);padding:0 0 0 14px}.cp .ct-line li::before{left:-8px;top:2px}.cp .ct-line li.ct-rule::before{left:-11px;top:0}}
@media (max-width:640px){.cp .ct-docket{max-height:72vh;overflow-y:auto;overscroll-behavior-y:contain;padding-right:6px;border-bottom:3px solid var(--ink)}}
/* Infra's features (builds, power, permits): the court page's hero and small tables, then one table of rows */
.cp .iw-chip{display:inline-block;background:var(--c);color:#111;font:700 11px var(--body);letter-spacing:.06em;text-transform:uppercase;padding:3px 9px;border-radius:999px;white-space:nowrap}
.cp .iw .ct-tables .jb-small td{vertical-align:middle}
.cp .iw-glance h2{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.cp .iw-when{font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .iw-bigs{display:flex;flex-wrap:wrap;gap:14px 40px;margin:6px 0 30px}
.cp .iw-big{border-left:6px solid var(--c);padding:2px 0 2px 14px}
.cp .iw-big b{display:block;font:800 44px/1 var(--display,var(--body))}
.cp .iw-big span{display:block;margin-top:4px;font-size:14.5px;color:var(--muted)}
.cp .iw-fbar{display:none}
.cp .iw-count{margin:4px 0 8px;font:500 13px var(--mono);color:var(--muted)}
.cp .iw-count b{color:var(--ink)}
.cp .iw-clear{margin-left:10px;padding:0;border:0;background:none;color:var(--ink);font:600 13px var(--body);text-decoration:underline;cursor:pointer}
.cp .iw-wrap{max-height:78vh;overflow:auto;overscroll-behavior:contain;padding-right:16px;border-bottom:3px solid var(--ink)}
.cp .iw-wrap thead th{position:sticky;top:0;z-index:1;background:var(--bg)}
.cp .iw-hb{font:inherit;letter-spacing:inherit;text-transform:inherit;color:inherit;background:none;border:0;padding:2px 0;cursor:pointer;white-space:nowrap}
.cp .iw-hb::after{content:" ▾";color:var(--muted)}
.cp .iw-hb.on{color:var(--ink);border-bottom:2px solid var(--ink)}
.cp .iw-hb.on::after{content:" ▾ ●";color:var(--ink)}
.iw-pop{position:absolute;z-index:50;width:260px;background:var(--bg);color:var(--ink);border:2px solid var(--ink);box-shadow:0 8px 24px rgb(0 0 0/.25);padding:10px;font:500 14px var(--body)}
.iw-pop input[type=search]{width:100%;box-sizing:border-box;font:inherit;padding:6px 8px;border:1.5px solid var(--line);background:var(--bg);color:var(--ink)}
.iw-pop label{display:flex;align-items:center;gap:8px;padding:4px 2px;cursor:pointer}
.iw-pop label[hidden]{display:none}
.iw-pop .iw-all{border-bottom:1px solid var(--line);margin:6px 0 4px;font-weight:600}
.iw-pop .iw-vals{max-height:260px;overflow-y:auto}
.iw-pop label span{flex:1}
.iw-pop label b{font:500 12px var(--mono);color:var(--muted)}
.cp .iw-t tr[hidden],.cp .xf-t tr[hidden]{display:none}
@media (max-width:640px){.cp .iw-fbar{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 6px}
  .cp .iw-fbar .iw-hb{font:600 11.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);border:1.5px solid var(--line);padding:5px 8px}
  .cp .iw-fbar .iw-hb.on{color:var(--ink);border-color:var(--ink)}
  .cp .iw-wrap{max-height:none;overflow:visible;border-bottom:0}.cp .iw-big b{font-size:34px}}
.cp .iw-t{font-size:14.5px}
.cp .iw-t td.when{font:500 12.5px var(--mono);color:var(--muted);white-space:nowrap}
.cp .iw-t td.who{font-weight:600}
.cp .iw-t .meta{color:var(--muted)}
.cp .ft .iw-t td.src a{font-weight:400;color:var(--muted);text-decoration:underline}
@media (max-width:640px){.cp table.iw-t{display:block;max-height:72vh;overflow-y:auto;overscroll-behavior-y:contain;border-bottom:3px solid var(--ink)}
  .cp .iw-t td .iw-chip{margin:4px 0}}
/* Models being retired: three numbers in ink boxes, then the dates; rows shutting down soon are marked */
.cp .rm-bigs{display:flex;flex-wrap:wrap;gap:14px;margin:14px 0 6px}
.cp .rm-big{flex:1 1 180px;border:2px solid var(--line);box-shadow:4px 4px 0 var(--line);padding:12px 14px;background:var(--bg)}
.cp .rm-big b{display:block;font:400 44px/1 var(--display)}
.cp .rm-big span{display:block;margin-top:6px;font-weight:600;font-size:14.5px;line-height:1.3}
.cp .rm-t{font-size:14.5px}
.cp .rm-t td.rm-d{font-weight:700;white-space:nowrap}
.cp .rm-t td.rm-t{white-space:nowrap}
.cp .rm-t code{font:600 13px var(--mono);overflow-wrap:anywhere}
.cp .rm-t tr.rm-soon td{background:color-mix(in srgb,#F0E442 26%,var(--bg))}
.cp .ft .rm-t td a{font-weight:400;text-decoration:underline}
.cp .rm h1{font-size:clamp(24px,3.6vw,30px)}
.cp .rm .jb-q{font-size:clamp(17px,2vw,20px);max-width:none}
.cp .rm-part[hidden],.cp .rm-t tr[hidden]{display:none}
.cp .rm-t td.rm-d small{display:block;font:500 12px var(--mono);color:var(--muted)}
.cp .ft .rm-t td.rm-lab a{display:inline-block;border:1.5px solid var(--line);padding:1px 7px;font:600 12.5px var(--body);text-decoration:none;white-space:nowrap}
.cp .ft .rm-t td.rm-lab a:hover,.cp .ft .rm-t td.rm-lab a:focus-visible{background:var(--ink);color:var(--bg)}
.cp .rm-t td:last-child,.cp .rm-t th:last-child{text-align:left}
.cp .rm-filters .sh-tabs + .sh-tabs{margin-top:-4px}
@media (min-width:641px){.cp .rm-t td.rm-same{color:transparent}.cp .rm-t td.rm-same small{display:none}
  .cp .rm-t tr:has(td.rm-same) td{border-top-color:color-mix(in srgb,var(--ink) 8%,transparent)}}
@media (max-width:640px){.cp .rm-wrap{max-height:72vh;overflow-y:auto;overscroll-behavior-y:contain;border-bottom:3px solid var(--ink)}
  .cp .rm-big b{font-size:34px}
  .cp .rm-t td:nth-child(4)::before{content:"Replace with ";color:var(--muted);font:500 12.5px var(--body)}
  .cp .rm-t td:nth-child(5)::before{content:"Announced ";color:var(--muted);font:500 12.5px var(--body)}
  .cp .rm-t td.rm-d small{display:inline;margin-left:8px}}
/* AI consultations: Models being retired's table, without its phone labels; an outcome's link under the title */
@media (max-width:640px){.cp .cs-t td:nth-child(4)::before{content:none}}
.cp .ft .cs-t a.cs-out{font-size:13px;color:var(--muted)}
/* Release cards: Models being retired's table, a coloured weights tag per row (Okabe-Ito, dark text) */
.cp .rc-t td{vertical-align:top}
.cp .rc-t small{display:block;margin-top:2px;font:500 12.5px/1.35 var(--body);color:var(--muted)}
.cp .ft .rc-t td.rc-m a{font-weight:600;text-decoration:none}
.cp .ft .rc-t td.rc-m a:hover,.cp .ft .rc-t td.rc-m a:focus-visible{text-decoration:underline}
.cp .rc-w{display:inline-block;padding:1px 8px;border-radius:10px;font:600 12.5px var(--body);color:#111;white-space:nowrap}
.cp .rc-open{background:#56B4E9}.cp .rc-wo{background:#F0E442}.cp .rc-closed{background:#d9d9d9}
.cp .rc-t td.rc-out{font-weight:600}
.cp .rc-t .rc-none{color:var(--muted)}
.cp .rc-t td.rc-p{white-space:nowrap}
.cp .rc-t td.rc-s{white-space:nowrap}.cp .rc-t td.rc-s small{white-space:normal;max-width:190px}
.cp .rc-s-day{background:#009E73}.cp .rc-s-later{background:#E69F00}
.cp .rc-s-none{background:transparent;color:var(--ink);box-shadow:inset 0 0 0 1.5px #8C8C8C}
.cp .ft .rc-t td.rc-s a{text-decoration:none}.cp .ft .rc-t td.rc-s a .rc-w::after{content:" ↗"}
.cp .ft .rc-t td.rc-s a:hover .rc-w,.cp .ft .rc-t td.rc-s a:focus-visible .rc-w{outline:2px solid var(--ink)}
/* its title, big numbers and column headers a size smaller; the tags as buttons; on a phone still a table, which
   scrolls sideways in its box */
.cp .rc h1{font-size:clamp(22px,2.4vw,24px)}
.cp .rc .jb-q{font-size:17px}
.cp .rc .rm-big b{font-size:30px}
.cp .rc .rm-big span{font-size:13.5px}
.cp .rc .rc-t th{font-size:10px;letter-spacing:.05em}
.cp .rc .sh-tabs{gap:8px}
.cp .rc .sh-tab{padding:5px 12px;border:2px solid var(--line);color:var(--ink)}
.cp .rc .sh-tab[aria-pressed=true]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.cp .rc .sh-tab[aria-pressed=true] b{color:var(--bg)}
@media (max-width:640px){.cp .rc .rm-big b{font-size:26px}
  .cp .rc .rm-wrap{overflow:auto}
  .cp .ft .rc-t{min-width:880px}
  .cp .ft .rc-t thead{display:table-header-group}
  .cp .ft .rc-t tr{display:table-row;padding:0}
  .cp .ft .rc-t td{display:table-cell;border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent);padding:8px 12px 8px 0}
  .cp .ft .rc-t td::before{content:none}}
/* Lab timelines: labs down the side, months across, each cell naming what happened; the grey column is scheduled
   shutdowns. A lab's name opens its rows as a table; on a phone the grid scrolls sideways in its box */
.cp .lt-leg{display:flex;flex-wrap:wrap;gap:6px 20px;margin:10px 0 12px;font-size:14px;align-items:center}
.cp .lt-dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;vertical-align:1px}
.cp .lt-o{background:#009E73}.cp .lt-wo{background:#E69F00}.cp .lt-c{background:var(--ink)}
.cp .lt-t{table-layout:fixed;font-size:14px}
.cp .lt-t th{font:500 11px var(--mono);letter-spacing:.05em;text-align:left}
.cp .lt-t thead th:first-child{width:150px}
.cp .lt-t td{vertical-align:top;line-height:1.35}
.cp .lt-t th[scope=row]{vertical-align:top;text-transform:none;letter-spacing:0;color:var(--ink);border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent);padding:10px 12px 10px 0}
.cp .lt-t td:last-child,.cp .lt-t th:last-child{text-align:left;white-space:normal;padding-right:8px}
.cp .lt-t .lt-fut{padding-left:8px}
.cp .lt-name{all:unset;cursor:pointer;font:600 15px/1.35 var(--body);color:var(--ink)}
.cp .lt-name:hover,.cp .lt-name:focus-visible{text-decoration:underline}
.cp .lt-name[aria-pressed=true]{text-decoration:underline;text-decoration-thickness:2px}
.cp .lt-r,.cp .lt-t .lt-p,.cp .lt-t .lt-x,.cp .lt-t .lt-s{display:block;margin:0 0 3px}
.cp .lt-p{color:var(--accent);font-weight:600}.cp .lt-x{color:#D55E00;font-weight:700}
.cp .lt-s{color:var(--muted)}
.cp .lt-fut{background:color-mix(in srgb,var(--ink) 6%,var(--bg))}
.cp .lt-few[hidden],.cp .lt-lab[hidden]{display:none}
.cp .lt-more{all:unset;cursor:pointer;display:inline-block;margin:10px 0 4px;font-size:14px;color:var(--muted);text-decoration:underline}
.cp .lt-lab h2{margin:22px 0 8px}
.cp .lt-d small{display:block;margin-top:2px;font:500 12.5px/1.35 var(--body);color:var(--muted)}
@media (max-width:640px){.cp .lt-wrap{overflow:auto;max-height:72vh}
  .cp .ft .lt-t{min-width:760px}
  .cp .ft .lt-t thead{display:table-header-group}
  .cp .ft .lt-t tr{display:table-row;padding:0}
  .cp .ft .lt-t td,.cp .ft .lt-t th{display:table-cell;padding:8px 10px 8px 0}
  .cp .ft .lt-t td::before{content:none}}
/* a little colour, Okabe-Ito tints with dark text: the three numbers, and each place's label */
.cp .cs .cs-big0{background:color-mix(in srgb,#009E73 22%,var(--bg))}
.cp .cs .cs-big1{background:color-mix(in srgb,#56B4E9 26%,var(--bg))}
.cp .cs .cs-big2{background:color-mix(in srgb,#E69F00 26%,var(--bg))}
.cp .ft .cs-t td.cs-uk a{background:color-mix(in srgb,#F0E442 45%,var(--bg))}
.cp .ft .cs-t td.cs-us a{background:color-mix(in srgb,#CC79A7 35%,var(--bg))}
.cp .ft .cs-t td.cs-eu a{background:color-mix(in srgb,#56B4E9 40%,var(--bg))}
/* AI pacts and orders: four sections one under another, each a plain table (Pledges and Deals green, Bans and
   Orders vermillion; Okabe-Ito tints, dark text); status tags in AI fines and bans' colours */
.cp .pc h1{font-size:clamp(24px,3.6vw,30px)}
.cp .pc .jb-q{font-size:clamp(17px,2vw,20px);max-width:none}
.cp .pc-stack{display:grid;gap:26px;margin-top:14px}
.cp .pc-stack .pc-rows td{font-size:14px}
.cp .pc-yes{background:#A6DCC6}.cp .pc-no{background:#F3B08A}
.cp .pc-who .pc-k{margin:0 5px 4px 0;text-transform:none;letter-spacing:0;font-size:12.5px;padding:1px 6px}
@media (min-width:641px){.cp .fx-t td.pc-who{width:330px}}
.cp .ft .pc-stack .fx-c a{color:var(--muted);text-decoration:underline;text-underline-offset:3px;font-weight:400}
.cp .pc-stack details{font-size:13px;color:var(--muted);margin-top:4px}
.cp .pc-stack details p{margin:2px 0 0 14px;font-size:13px}
.cp .pc-stack summary{cursor:pointer;width:max-content;max-width:100%}
.cp .pc-every{margin-top:14px}
.cp .pc-stack .pc-every > summary{font:700 14px var(--body);color:var(--ink);margin-bottom:8px}
.cp .pc-half{border:2px solid var(--line);box-shadow:5px 5px 0 var(--line);background:var(--bg);min-width:0}
.cp .pc-hh{padding:10px 14px 8px;border-bottom:2px solid var(--line)}
.cp .pc-pacts .pc-hh{background:color-mix(in srgb,#009E73 24%,var(--bg))}
.cp .pc-orders .pc-hh{background:color-mix(in srgb,#F85C48 20%,var(--bg))}
.cp .ft .pc-hh h2{font:400 26px/1.1 var(--display);margin:0;border:0;padding:0}
.cp .pc-hh p{margin:3px 0 0;font-size:14px;font-weight:600}
.cp .pc-in{padding:12px 14px 14px}
.cp .pc-lead{font:700 16.5px/1.4 var(--body);margin:2px 0 4px;padding-left:10px;border-left:5px solid var(--ink)}
.cp .pc .pc-in h3{font:700 12px var(--body);letter-spacing:.06em;text-transform:uppercase;color:var(--ink);margin:18px 0 8px;padding-top:8px;border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent)}
.cp .pc-y.pc-rat{background:var(--ink);box-shadow:0 0 0 2px #009E73}
.cp .pc-find{font:14px var(--body);padding:6px 9px;border:2px solid var(--line);width:min(280px,100%);margin:0 0 6px;background:var(--bg);color:var(--ink)}
.cp .pc-gw{max-height:430px;overflow-y:auto;overscroll-behavior-y:contain;border-bottom:2px solid var(--ink)}
.cp .pc-grid{width:100%;border-collapse:collapse}
.cp .pc-grid th,.cp .pc-grid td{font-size:13.5px;padding:3px 4px;text-align:center;border-top:1px solid color-mix(in srgb,var(--ink) 12%,transparent)}
.cp .pc-grid thead th{position:sticky;top:0;background:var(--bg);font:600 11px var(--body);text-transform:uppercase;letter-spacing:.04em;border-top:0;border-bottom:2px solid var(--ink);vertical-align:bottom}
.cp .pc-grid thead th small{display:block;font-size:11px;text-transform:none;letter-spacing:0}
.cp .pc-grid th[scope=row],.cp .pc-grid thead th:first-child{text-align:left;font-weight:600}
.cp .pc-grid tr.pc-focus th,.cp .pc-grid tr.pc-focus td{background:color-mix(in srgb,#F0E442 24%,var(--bg))}
.cp .pc-grid tr[hidden]{display:none}
.cp .pc-y,.cp .pc-n{display:inline-block;width:12px;height:12px;border-radius:50%;vertical-align:-1px}
.cp .pc-y{background:#009E73;border:1.5px solid var(--ink)}
.cp .pc-n{border:1.5px dashed color-mix(in srgb,var(--ink) 45%,transparent)}
.cp .pc-key{display:flex;flex-wrap:wrap;gap:3px 14px;align-items:center;font-size:12.5px;color:var(--muted);margin:6px 0 0}
.cp .pc-key > span{display:inline-flex;gap:5px;align-items:center}
.cp .pc-rows{width:100%;border-collapse:collapse}
.cp .pc-rows td{font-size:13.5px;line-height:1.3;padding:6px 8px 6px 0;border-top:1px solid color-mix(in srgb,var(--ink) 15%,transparent);vertical-align:top}
.cp .pc-rows td.pc-d{white-space:nowrap;font-weight:700;width:1%}
.cp .pc-rows td.pc-s{white-space:nowrap;width:1%;text-align:right}
.cp .ft .pc-rows td.pc-s a{font-weight:400;color:var(--ink);text-decoration:underline;text-underline-offset:3px}
.cp .ft .pc-rows td.pc-s a{display:block;font-size:12px;margin-top:3px}
.cp .pc-k{display:inline-block;font:700 11px var(--body);text-transform:uppercase;letter-spacing:.04em;border:1.5px solid var(--line);padding:0 5px;color:#111}
.cp .pc-ord{background:#E9B9D5}.cp .pc-inv{background:#A8D8F2}.cp .pc-crt{background:#F2D27A}
/* The model economy: a second name under the title; tags for cheaper / same / pricier and for under 30, 30-89 and 90+
   days of warning */
.cp .fh-sub{margin:2px 0 0;font:700 17px/1.3 var(--body);color:#000}
.cp .me-same{background:var(--bg);color:var(--ink)}.cp .me-mixed{background:#F2D27A}.cp .me-mid{background:#E69F00}
.cp .me-models{margin-top:22px}.cp .me .me-more{margin-top:10px}
.cp .ft.me .pc-rows a{color:var(--ink);text-decoration:underline;text-underline-offset:3px}
@media (max-width:640px){.cp .me td[data-l]::before{content:attr(data-l) ": ";color:var(--muted);font-size:12.5px}}
/* AI fines and bans: a dot per action on one time line (each linking to its row), then the AI pacts and orders boxes
   stacked, each a table in real columns with a tag for where it stands and a muted line under it */
.cp .fx-tl{margin:26px 0 22px}
.cp .fx .fx-tl h2{margin:0 0 8px}
.cp .fx-strip{position:relative;height:136px;border-bottom:2px solid var(--ink);margin-bottom:30px}
.cp .fx-gl{position:absolute;top:0;bottom:0;border-left:1px dashed color-mix(in srgb,var(--ink) 30%,transparent)}
.cp .fx-yr{position:absolute;bottom:-24px;transform:translateX(-50%);font:600 12px var(--mono)}
.cp .fx-lane{position:absolute;left:6px;font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .fx-row{position:absolute;left:0;right:0}
.cp .fx-dot{position:absolute;width:14px;height:14px;border:2px solid var(--line);border-radius:50%;transform:translate(-50%,-50%);box-sizing:border-box}
.cp .fx-dot:hover,.cp .fx-dot:focus-visible{z-index:3;outline:2px solid var(--ink);outline-offset:2px}
.cp .fx-dot:hover::after,.cp .fx-dot:focus-visible::after{content:attr(data-tip);position:absolute;bottom:calc(100% + 8px);left:-4px;background:#111;color:#fff;font:500 12.5px/1.3 var(--body);padding:5px 8px;white-space:nowrap}
.cp .fx-dot.fx-l:hover::after,.cp .fx-dot.fx-l:focus-visible::after{left:auto;right:-4px}
.cp .fx-key{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:center;font-size:13px;color:var(--muted);margin:0}
.cp .fx-stack{display:grid;gap:22px}
.cp .fx-t th{text-align:left;font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:4px 10px 6px 0;border-bottom:3px solid var(--ink)}
.cp .fx-t td{padding:8px 10px 8px 0}
.cp .fx-t td.fx-n{text-align:right;white-space:nowrap;font:700 13.5px var(--mono)}
.cp .fx-t td.fx-n .fx-c{font-family:var(--body);font-weight:400}
.cp .fx-t td.fx-s{width:190px}
.cp .fx-t tr:target td{animation:fx-hit 2.5s ease-out}
@keyframes fx-hit{from{background:color-mix(in srgb,#F2D27A 70%,var(--bg))}to{background:transparent}}
@media (max-width:640px){.cp .fx-dot{width:11px;height:11px}
  .cp .fx-dot:hover::after,.cp .fx-dot:focus-visible::after{white-space:normal;width:200px}
  .cp .fx-yr{font-size:10.5px}
  .cp .fx-t thead{display:none}
  .cp .fx-t tr{display:grid;grid-template-columns:auto 1fr;column-gap:10px;border-top:1px solid color-mix(in srgb,var(--ink) 15%,transparent);padding:6px 0}
  .cp .fx-t td{border:0;padding:2px 0;grid-column:2}
  .cp .fx-t td.pc-d{grid-column:1;grid-row:1/span 6}
  .cp .fx-t td.fx-n{text-align:left}
  .cp .fx-t td.fx-s{width:auto}}
.cp .fx .pc-k{white-space:nowrap}
.cp .fx-c{display:block;color:var(--muted);font-size:12px;line-height:1.3;margin-top:3px}
.cp .ft.fx .fx-c a{display:inline;margin:0;font-size:12px;color:var(--muted);text-decoration:underline;text-underline-offset:3px}
.cp .ft.fx td.fx-s > .fx-c > a{color:var(--ink)}
.cp .fx .pc-hh{background:var(--f-reg)}
.cp .fx .pc-hh h2,.cp .fx .pc-hh p{color:#141925}
.cp .fx-in{background:#F85C48}.cp .fx-li{background:#56B4E9}.cp .fx-ch{background:#F0E442}.cp .fx-an{background:#8C8C8C}.cp .fx .fx-aw{background:var(--bg);border-style:dashed;color:var(--ink)}
/* AI buyouts: a quotable lead, then a shopping list per buyer (a row with a dot per deal along the year; the dot's area
   grows with the price, hollow when none was given, dashed while only agreed, a cross when blocked; each links to its
   row), then every deal in the fines and bans' table look. Names keep their size on phones; the tracks shrink */
.cp .by-lead{font:400 21px/1.4 var(--body);margin:24px 0 4px}
.cp .by-sub{font-size:13.5px;color:var(--muted);margin:0 0 6px}
.cp .by-ls{margin:22px 0 28px}
.cp .by .by-ls h2,.cp .by .by-all h2{margin:0 0 8px}
.cp .by-key{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:center;font-size:13px;color:var(--muted);margin:0 0 10px}
.cp .by-key > span{display:inline-flex;gap:6px;align-items:center}
.cp .by-k{display:inline-block;width:13px;height:13px;border-radius:50%;border:1.5px solid var(--ink);background:var(--f-news)}
.cp .by-k.by-a{border-style:dashed}.cp .by-k.by-un{background:var(--bg)}
.cp .by-kx{color:var(--f-reg);font-size:15px;line-height:1}
.cp .by-g{--nw:170px;position:relative;padding-top:24px}
.cp .by-ax{position:absolute;top:0;bottom:0;left:var(--nw);right:0;pointer-events:none}
.cp .by-gl{position:absolute;top:20px;bottom:0;border-left:1px dashed color-mix(in srgb,var(--ink) 22%,transparent)}
.cp .by-mo{position:absolute;top:0;padding-left:4px;font:600 12px var(--mono);color:var(--muted)}
.cp .by-r{display:grid;grid-template-columns:var(--nw) 1fr;align-items:center;border-bottom:1px solid color-mix(in srgb,var(--ink) 12%,transparent)}
.cp .by-n{font-weight:700;font-size:15px;line-height:1.2;padding-right:10px}
.cp .by-n b{font:600 12.5px var(--mono);color:var(--muted);margin-left:4px}
.cp .by-tr{position:relative;height:50px}
.cp .by-tr::before{content:"";position:absolute;left:0;right:0;top:50%;border-top:1px solid color-mix(in srgb,var(--ink) 35%,transparent)}
.cp .by-dot{position:absolute;top:50%;width:var(--s);height:var(--s);border:1.5px solid var(--ink);border-radius:50%;background:var(--f-news);transform:translate(-50%,-50%);box-sizing:border-box;z-index:1}
.cp .by-dot.by-a{border-style:dashed}.cp .by-dot.by-un{background:var(--bg)}
.cp .by-dot.by-x{width:18px;height:18px;border:0;border-radius:0;background:linear-gradient(45deg,transparent 41%,var(--f-reg) 41% 59%,transparent 59%),linear-gradient(-45deg,transparent 41%,var(--f-reg) 41% 59%,transparent 59%)}
.cp .by-dot:hover,.cp .by-dot:focus-visible{z-index:3;outline:2px solid var(--ink);outline-offset:2px}
.cp .by-dot:hover::after,.cp .by-dot:focus-visible::after{content:attr(data-tip);position:absolute;bottom:calc(100% + 8px);left:-4px;background:#111;color:#fff;font:500 12.5px/1.3 var(--body);padding:5px 8px;white-space:nowrap;border:0;transform:none}
.cp .by-dot.by-l:hover::after,.cp .by-dot.by-l:focus-visible::after{left:auto;right:-4px}
.cp .by-lb{position:absolute;top:50%;transform:translateY(-50%);font:600 12.5px var(--body);white-space:nowrap;pointer-events:none}
.cp .by-lb.by-up{top:1px;transform:none}
.cp .by-one{font-size:13.5px;color:var(--muted);margin:10px 0 0}
.cp .by-all{margin:0 0 26px}
.cp .fx-t td.by-p{white-space:nowrap;font:700 13.5px var(--mono)}
.cp .pc-k.by-b{background:#56B4E9}.cp .pc-k.by-a{background:var(--bg);border-style:dashed;color:var(--ink)}.cp .pc-k.by-x{background:#F85C48}
@media (max-width:640px){.cp .by-g{--nw:92px}
  .cp .by-n{font-size:13px}
  .cp .by-mo{font-size:10px;padding-left:2px}
  .cp .by-dot{width:max(9px,calc(var(--s) * .62));height:max(9px,calc(var(--s) * .62))}
  .cp .by-lb{top:3px;transform:none;font-size:10.5px}
  .cp .by-dot:hover::after,.cp .by-dot:focus-visible::after{white-space:normal;width:190px}
  .cp .fx-t td.by-p{white-space:normal}}
/* AI money (who-owns-a-piece-of-whom/): Buyouts' lanes, a dot colour per kind (Okabe-Ito blue, orange, reddish purple), dashed
   for a figure from a news report; "Money that comes back" as two plain tables */
.cp .am .by-lead{max-width:none}
.cp .am-lane .by-tr{height:84px}.cp .am-lane .by-tr::before,.cp .am-lane .by-dot{top:62%}
.cp .am-lb{position:absolute;top:2px;transform:translateX(-50%);font:600 12.5px var(--body);white-space:nowrap;pointer-events:none}
.cp .am-lb-l{transform:translateX(-14px)}.cp .am-lb-r{transform:translateX(calc(-100% + 14px))}
@media (max-width:640px){.cp .am-lb{font-size:10.5px}}
.cp .by-dot.am-round,.cp .by-k.am-k-round,.cp .pc-k.am-t-round{background:var(--f-news)}
.cp .by-dot.am-compute,.cp .by-k.am-k-compute,.cp .pc-k.am-t-compute{background:var(--f-policy)}
.cp .by-dot.am-buyout,.cp .by-k.am-k-buyout,.cp .pc-k.am-t-buyout{background:var(--f-research)}
.cp .by-dot.am-r,.cp .by-k.am-k-r{border-style:dashed}.cp .by-k.am-k-r{background:var(--bg)}
.cp .am-rep{display:inline-block;margin-left:6px;font:600 11px var(--mono);text-transform:uppercase;color:var(--muted)}
.cp .am-cc,.cp .ow-st{margin:30px 0 26px}.cp .am-cc h3{margin:18px 0 6px;font-size:16px}
.cp .am-ct{width:100%}.cp .am-ct td{vertical-align:top}.cp .am-ct td .fx-c{display:block;font-size:12.5px;color:var(--muted)}
/* What governments use AI for: a lead line; "Who tells you" (every list, a tag for what it covers); "Whose AI they
   run" (suppliers by list, a dot whose area grows with the count, and the number); a card per full list (2 a row,
   1 on phones), each linking to its own page: AI pacts and orders' boxes in Okabe-Ito tints, dark text */
.cp .gv-lead{font:400 22px/1.4 var(--body);margin:22px 0 18px}
.cp .gv-lead b{font-weight:700}
.cp .ft.gv h2.gv-h{font:400 28px/1.15 var(--display);margin:34px 0 4px}
.cp .gv p.gv-sub{margin:0 0 12px;color:var(--muted);font-size:15px}
.cp .gv-f{width:24px;height:16px;object-fit:cover;border:1px solid var(--line);margin-right:9px;vertical-align:-2px}
.cp .gv-who,.cp .gv-whose{width:100%;border-collapse:collapse}
.cp .gv-who th,.cp .gv-whose thead th{text-align:left;font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:4px 12px 6px 0;border-bottom:3px solid var(--ink)}
.cp .gv-who td{padding:8px 12px 8px 0;border-top:1px solid color-mix(in srgb,var(--ink) 15%,transparent);font-size:14.5px;vertical-align:top}
.cp .gv-n{font:700 14px var(--mono);white-space:nowrap}
.cp .ft.gv .gv-who a,.cp .ft.gv .gv-t td a{color:var(--ink);font-weight:600;text-decoration:none}
.cp .ft.gv .gv-who a:hover,.cp .ft.gv .gv-t td a:hover{text-decoration:underline}
.cp .ft.gv a.gv-go,.cp .ft.gv a.gv-all{font-weight:700;color:var(--ink);text-decoration:underline;text-underline-offset:3px;white-space:nowrap}
.cp .gv-chk{color:var(--muted);font-size:12.5px;white-space:nowrap}
.cp .gv-live{background:#A6DCC6}.cp .gv-trial{background:#F2D27A}.cp .gv-off{background:#DDDDDD}.cp .gv-high{background:#E9B9D5}
.cp .gv .pc-k{white-space:nowrap}
.cp .gv-whose{max-width:760px;table-layout:fixed}
.cp .gv-whose thead th:first-child{width:130px}
.cp .gv-whose tbody th{text-align:left;font:600 14.5px var(--body);padding:0 10px 0 0;border-top:1px solid color-mix(in srgb,var(--ink) 12%,transparent)}
.cp .gv-whose td{height:50px;padding:0;border-top:1px solid color-mix(in srgb,var(--ink) 12%,transparent);font:700 13.5px var(--mono);white-space:nowrap}
.cp .gv-dot{display:inline-block;vertical-align:middle;border-radius:50%;background:var(--f-policy);border:1.5px solid var(--ink);margin-right:8px}
.cp .gv-whose td.gv-z{color:var(--muted);font-weight:400}
.cp .gv-cards{display:grid;grid-template-columns:1fr 1fr;gap:26px;margin-top:10px}
.cp .gv .gv-us .pc-hh{background:color-mix(in srgb,#CC79A7 30%,var(--bg))}
.cp .gv .gv-ca .pc-hh{background:color-mix(in srgb,#D55E00 22%,var(--bg))}
.cp .gv .gv-nl .pc-hh{background:color-mix(in srgb,#E69F00 30%,var(--bg))}
.cp .gv .gv-uk .pc-hh{background:color-mix(in srgb,#56B4E9 32%,var(--bg))}
.cp .ft.gv .gv-card h2{font:400 24px/1.1 var(--display);margin:0;border:0;padding:0}
.cp .gv-big{margin:4px 0 8px;font-size:15px}.cp .gv-big b{font:400 44px/1 var(--display);margin-right:6px}
.cp .gv-facts{width:100%;border-collapse:collapse;margin-bottom:6px}
.cp .gv-facts.gv-wide{max-width:640px}
.cp .gv-facts td{font-size:13.5px;padding:5px 0;border-top:1px solid color-mix(in srgb,var(--ink) 15%,transparent)}
.cp .gv-facts td:last-child{text-align:right;padding-left:10px}.cp .gv-facts b{font:700 14px var(--mono)}
.cp .gv-ex{list-style:none;margin:0;padding:0}
.cp .gv-ex li{font-size:13.5px;padding:6px 0;border-top:1px solid color-mix(in srgb,var(--ink) 12%,transparent)}
.cp .ft.gv a.gv-all{display:inline-block;margin-top:10px}
.cp .gv-sc{max-height:620px;overflow-y:auto;overscroll-behavior-y:contain;border-bottom:2px solid var(--ink)}
.cp .gv-t thead th{position:sticky;top:0;z-index:1;background:var(--bg);text-align:left;font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);padding:4px 10px 6px 0;border-bottom:3px solid var(--ink)}
.cp .gv-t td{padding:8px 10px 8px 0}
.cp .gv-us-t td:first-child{width:150px}
@media (max-width:640px){.cp .gv-cards{grid-template-columns:1fr}
  .cp .gv-who thead{display:none}
  .cp .gv-who tr{display:block;border-top:1px solid color-mix(in srgb,var(--ink) 15%,transparent);padding:6px 0}
  .cp .gv-who td{display:inline-block;border:0;padding:2px 10px 2px 0}
  .cp .gv-who td:nth-child(2){display:block}
  .cp .gv-whose thead th:first-child{width:92px}.cp .gv-whose thead th{letter-spacing:0;font-size:10.5px}
  .cp .gv-whose .gv-f{display:block;margin-bottom:3px}
  .cp .gv-dot{margin-right:4px}
  .cp .gv-sc{max-height:72vh}
  .cp .gv-t thead{display:none}
  .cp .gv-t tr{display:block;border-top:1px solid color-mix(in srgb,var(--ink) 15%,transparent);padding:6px 0}
  .cp .gv-t td{display:inline-block;border:0;padding:2px 8px 2px 0;vertical-align:middle}
  .cp .gv-t td:nth-child(2){display:block}
  .cp .gv-us-t td:first-child{width:auto}.cp .gv-us-t td:first-child .fx-c{display:none}}
/* Chip export rules: a grid of chips (rows) by US decision (columns), a coloured cell per answer with its symbol so
   colour is never the only cue; then three short lists in columns, stacked on phones (the grid shrinks to fit) */
.cp .ce .fx-in{background:#A6DCC6}.cp .ce .fx-ch{background:#F2D27A}.cp .ce .fx-an{background:#F3B08A}.cp .ce .fx-aw{background:#DDDDDD}
.cp .ce-hero{margin:20px 0 6px;border:2px solid var(--ink);padding:16px 18px 14px}
.cp .ce .ce-hero h2{margin:0 0 8px}
.cp .ce-big{font:600 17px/1.4 var(--body);margin:0 0 14px}
.cp .ce-grid{width:100%;border-collapse:separate;border-spacing:4px;table-layout:fixed}
.cp .ce-grid th,.cp .ce-grid td{border:0;padding:0}
.cp .ce-grid thead th{font:700 13px var(--body);text-align:center;vertical-align:bottom;padding-bottom:4px}
.cp .ce-grid thead a{color:inherit}
.cp .ce-when{display:block;font:600 10.5px var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.cp .ce-grid th.ce-chip{text-align:left;width:22%}
.cp .ce-chip span{display:block;font:500 11px var(--body);color:var(--muted)}
.cp .ce-grid tbody th{text-align:left;font:700 15px var(--body);padding-right:6px;white-space:nowrap}
.cp .ce-grid tbody th small{font:500 11.5px var(--body);color:var(--muted)}
.cp .ce-co,.cp .ce-grid tbody th em{display:block;font:600 10px var(--mono);font-style:normal;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.cp .ce-grid td{height:42px;text-align:center;font:700 19px var(--body);color:#111;border-radius:3px}
.cp .ce-grid td i{display:block;font:700 10.5px var(--body);font-style:normal;margin-top:-2px}
.cp .ce .ok{background:#009E73}.cp .ce .cb{background:#F0E442}.cp .ce .no{background:#D55E00}
.cp .ce .na{background:repeating-linear-gradient(135deg,rgba(128,128,128,.3) 0 2px,transparent 2px 7px);border:1px solid rgba(128,128,128,.35)}
.cp .ce-grid td.ce-now{box-shadow:0 0 0 2px var(--bg),0 0 0 4px var(--ink)}
.cp .ce-grid thead th.ce-now{text-decoration:underline;text-underline-offset:3px}
.cp .ce-key{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12.5px;margin:12px 0 0}
.cp .ce-key span{display:inline-flex;align-items:center;gap:6px}
.cp .ce-k{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:3px;font-size:12px;color:#111;box-sizing:border-box}
.cp .ce-cn{font-size:13px;margin:12px 0 0;padding-top:10px;border-top:1px solid var(--line)}
.cp .ce-hw{font-size:13px;margin:10px 0 0;padding:8px 10px;border-left:6px solid #D55E00;background:rgba(128,128,128,.08)}
.cp .ce .ce-sec{margin:30px 0 12px}
.cp .ce-themes{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.cp .ce-th{border-top:6px solid #0072B2;padding-top:8px}
.cp .ce-th.cnh{border-top-color:#E69F00}
.cp .ce .ce-th h3{font:800 17px var(--body);margin:0}
.cp .ce-sub{font-size:12.5px;color:var(--muted);margin:2px 0 8px}
.cp .ce-th ol{list-style:none;margin:0;padding:0}
.cp .ce-th li{padding:8px 0 9px 12px;border-bottom:1px solid var(--line);position:relative;font-size:13.5px;line-height:1.35}
.cp .ce-th li:before{content:"";position:absolute;left:0;top:13px;width:6px;height:6px;border-radius:50%;background:#0072B2}
.cp .ce-th.cnh li:before,.cp .ce-th li.ot:before{background:#E69F00}
.cp .ce-th li time{display:block;font:700 11.5px var(--mono);color:var(--muted)}
.cp .ce-th li b{display:block}
.cp .ce-l{display:block;color:var(--muted);font-size:12.5px}
.cp .ce-f{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:5px;font-size:12px}
.cp .ce-f a{color:var(--muted)}
.cp .ce-th li.eased{opacity:.62}
.cp .ce-el{margin:24px 0 6px;font-size:14px;border-left:4px solid var(--ink);padding-left:10px}
.cp .ce-notes{font-size:11.5px;color:var(--muted);margin:12px 0 0;padding-left:18px}
.cp .ce-notes a{color:var(--muted)}
@media (max-width:700px){.cp .ce-hero{padding:12px 10px}.cp .ce-big{font-size:15px}.cp .ce-grid{border-spacing:2px}
.cp .ce-grid th.ce-chip{width:27%}.cp .ce-chip span{font-size:8px}.cp .ce-grid thead th{font-size:10.5px}
.cp .ce-when{font-size:8px;letter-spacing:0}.cp .ce-grid tbody th{font-size:12.5px;white-space:normal;line-height:1.15}
.cp .ce-grid tbody th small{display:block;font-size:10px}.cp .ce-co,.cp .ce-grid tbody th em{font-size:8px;letter-spacing:0}
.cp .ce-grid td{height:34px;font-size:15px}.cp .ce-grid td i{font-size:8px}.cp .ce-themes{grid-template-columns:1fr;gap:22px}}
@media (max-width:640px){.cp .pc-gw{max-height:72vh;overflow-x:auto}.cp .pc-tiles{grid-template-columns:repeat(2,1fr)}
  .cp .pc-grid th,.cp .pc-grid td{padding:4px 1px;font-size:13px}
  .cp .pc-grid thead th{font-size:9.5px;letter-spacing:0}
  .cp .pc-grid thead th small{font-size:9.5px}
  .cp .pc-grid th[scope=row]{padding-right:4px;line-height:1.2}
  .cp .pc-in{padding:12px 10px 14px}}
.cp .ft .cs-t td.cs-canada a{background:color-mix(in srgb,#F85C48 28%,var(--bg))}
/* Who owns a piece of whom: investors by labs, a box per deal (dashed: "up to"); phones scroll the grid sideways */
.cp .ow-key{display:flex;flex-wrap:wrap;gap:6px 20px;font-size:13.5px;margin:10px 0 8px}
.cp .ow-key i{display:inline-block;width:18px;height:12px;border:2px solid var(--line);margin-right:6px;vertical-align:-1px;background:color-mix(in srgb,#E69F00 30%,var(--bg))}
.cp .ow-key i.ow-up{border-style:dashed;background:color-mix(in srgb,#E69F00 14%,var(--bg))}
.cp .ow-wrap{overflow-x:auto;overscroll-behavior-x:contain}
.cp .ow-grid{width:100%;border-collapse:collapse;min-width:820px}
.cp .ow-grid th{font:600 12.5px var(--body);text-transform:uppercase;letter-spacing:.05em;padding:8px 6px;border-bottom:3px solid var(--ink);vertical-align:bottom}
.cp .ow-grid tbody th{text-transform:none;letter-spacing:0;font:700 15px var(--body);text-align:left;border-bottom:1px solid color-mix(in srgb,var(--ink) 22%,transparent);vertical-align:top;padding:12px 8px 12px 0;position:sticky;left:0;background:var(--bg)}
.cp .ow-grid td{border-bottom:1px solid color-mix(in srgb,var(--ink) 22%,transparent);padding:10px 6px;text-align:center;vertical-align:top}
.cp .ow-deal{display:inline-block;min-width:74px;max-width:130px;border:2px solid var(--line);padding:4px 6px;font-weight:700;font-size:13.5px;line-height:1.25;color:var(--ink);text-decoration:none;background:color-mix(in srgb,#E69F00 30%,var(--bg))}
.cp .ow-deal small{display:block;font-weight:400;font-size:11.5px}
.cp .ow-deal.ow-up{border-style:dashed;background:color-mix(in srgb,#E69F00 14%,var(--bg))}
.cp .ow-deal:hover,.cp .ow-deal:focus-visible{box-shadow:3px 3px 0 var(--line)}
/* AI safety hub: the search and filters, then a card per document (its kind's colour on top), newest first */
.cp .sh .jb-q{max-width:none}
.cp .sh-filters{position:sticky;top:0;z-index:2;background:var(--bg);padding:12px 0 10px;margin:18px 0 6px;border-bottom:2px solid var(--ink)}
.cp .sh-q{width:100%;box-sizing:border-box;font:500 16px var(--body);padding:10px 12px;border:2px solid var(--line);background:var(--bg);color:var(--ink)}
.cp .sh-tabs{display:flex;flex-wrap:wrap;gap:4px 22px;margin:0 0 10px}
.cp .sh-tab{font:600 14px var(--body);padding:4px 0;border:0;border-bottom:3px solid transparent;background:none;color:var(--muted);cursor:pointer}
.cp .sh-tab b{font:600 12px var(--mono);color:var(--muted);margin-left:4px}
.cp .sh-tab[aria-pressed=true]{color:var(--ink);border-bottom-color:var(--ink)}
.cp .sh-sel{display:flex;align-items:center;gap:6px;margin-top:10px}
.cp .sh-sel span{font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .sh-sel select{font:500 14px var(--body);padding:5px 6px;border:2px solid var(--line);background:var(--bg);color:var(--ink);max-width:62vw}
.cp .sh-count{margin:8px 0 0;font:500 13px var(--mono);color:var(--muted)}
.cp .sh-count b{color:var(--ink)}
.cp .sh-docs{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px;margin-top:16px;align-items:start}
.cp .sh-doc{border-top:5px solid var(--c);background:color-mix(in srgb,var(--c) 7%,var(--bg));border-radius:0 0 6px 6px;padding:12px 15px 10px;min-width:0}
.cp .sh-doc[hidden]{display:none}
.cp .sh-top{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.cp .sh-kind{background:var(--c);color:#111;font:700 11.5px var(--body);letter-spacing:.06em;text-transform:uppercase;padding:3px 9px;border-radius:999px}
.cp .sh-meta{font:600 11px var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.cp .sh-doc h3{font:600 17px/1.3 var(--body);text-transform:none;letter-spacing:0;margin:10px 0 6px}
.cp .sh-models{font-size:13.5px;margin:0 0 6px}
.cp .sh-models span{color:var(--muted)}
.cp .sh-risks{list-style:none;margin:0 0 8px;padding:0;display:flex;flex-wrap:wrap;gap:4px}
.cp .ft .sh-risks li{border:1px solid color-mix(in srgb,var(--ink) 30%,transparent);border-radius:4px;padding:1px 6px;font:500 11.5px var(--body)}
.cp .sh-ab span{display:block;font:600 10.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .sh-ab p{margin:3px 0 0;font-size:14px;line-height:1.45;display:-webkit-box;-webkit-line-clamp:5;-webkit-box-orient:vertical;overflow:hidden}
.cp .sh-doc.open .sh-ab p{display:block;-webkit-line-clamp:unset}
.cp .sh-more{margin-top:4px;padding:0;border:0;background:none;color:var(--ink);font:600 13px var(--body);text-decoration:underline;cursor:pointer}
.cp .sh-links{margin:8px 0 0;font-size:13px}
.cp .ft .sh-links a{font-weight:600;color:var(--ink)}
.cp .sh-none{margin:20px 0;font-size:16px}
@media (max-width:640px){.cp .sh-tabs{flex-wrap:nowrap;overflow-x:auto;overscroll-behavior-x:contain}.cp .sh-tab{flex:none}
  .cp .sh-sel{flex-direction:column;align-items:stretch;gap:2px}.cp .sh-sel select{max-width:none;width:100%}}
@media (max-width:640px){.cp .sh-filters{position:static}.cp .sh-docs{display:flex;flex-direction:column;max-height:72vh;overflow-y:auto;overscroll-behavior-y:contain;padding-right:6px;border-bottom:3px solid var(--ink)}.cp .sh-doc{flex:none}}
.cp .fh .kind{margin:10px 0 0;color:#000}  /* a glossary word's group, under its question */
.cp .fh .kind i{font-style:normal}.cp .fh .kind i + i::before{content:" · "}
/* phones: the two as tags, one below the other */
@media (max-width:640px){.cp .fh .kind{display:flex;flex-direction:column;align-items:flex-start;gap:4px;margin-top:8px}
  .cp .fh .kind i{font-size:9.5px;padding:1px 6px;border:1.5px solid #000;background:#fff;letter-spacing:.06em}
  .cp .fh .kind i + i::before{content:none}}
/* "Cite this": a ready-made citation under the question, opened over the page so the band keeps its size */
.cp .fh-cite{position:relative;margin-top:10px}
.cp .fh-cite summary{display:inline-block;cursor:pointer;list-style:none;padding:3px 10px;border:2px solid #000;
  font:700 13px/1.3 var(--body);color:#000;background:transparent}
.cp .fh-cite summary::-webkit-details-marker{display:none}
.cp .fh-cite[open] summary{background:#000;color:var(--f)}
.cp .fh-cite-box{position:absolute;z-index:5;left:0;top:calc(100% + 6px);width:min(440px,80vw);padding:14px;
  background:var(--bg);color:var(--ink);border:3px solid var(--line);box-shadow:4px 4px 0 var(--line)}
.cp .fh-cite-box p{margin:0 0 10px;font:400 14px/1.45 var(--body);color:inherit}
.cp .fh-cite-box .fh-cite-src{font-size:13px}
.cp .fh-cite-box button{padding:4px 12px;border:2px solid var(--line);background:var(--ink);color:var(--bg);
  font:700 13px/1.3 var(--body);cursor:pointer}
.cp .fh-cite-box{padding-right:36px}
.cp .fh-cite-box .fh-cite-x{position:absolute;top:6px;right:8px;padding:0 6px;border:0;background:none;color:var(--ink);font:700 20px/1 var(--body)}
@media (max-width:640px){.cp .fh-cite-box{position:relative;width:auto;margin-top:8px}}
/* New tests for AI and Compute behind notable models (Research's features) */
.cp .nt .nt-how{margin:0 0 14px;max-width:none;font-size:14.5px;color:var(--muted)}
.cp .nt-scores{list-style:none;margin:0 0 34px;padding:0;border-top:2px solid var(--line)}
.cp .nt-scores li{display:grid;grid-template-columns:minmax(0,15rem) minmax(0,1fr) minmax(0,15rem);gap:14px;align-items:center;
  padding:7px 0;border-bottom:1px solid color-mix(in srgb,var(--ink) 18%,transparent)}
.cp .nt-scores a{color:var(--ink);font-weight:600;text-decoration:none}
.cp .nt-scores a:hover{text-decoration:underline}
.cp .nt-track{position:relative;height:14px;background:linear-gradient(var(--line),var(--line)) 0 50%/100% 1.5px no-repeat}
.cp .nt-track::before,.cp .nt-track::after{content:"";position:absolute;top:2px;width:1.5px;height:10px;background:var(--line)}
.cp .nt-track::before{left:0}.cp .nt-track::after{right:0}
.cp .nt-track i{position:absolute;top:50%;width:13px;height:13px;margin:-6.5px 0 0 -6.5px;border-radius:50%;background:var(--f-research);border:2px solid var(--line)}
.cp .nt-pct{font-size:14px;color:var(--muted)}.cp .nt-pct b{font:700 16px var(--body);color:var(--ink)}
.cp .nt h3{margin:26px 0 6px;font:400 19px var(--display)}
.cp .nt-n{margin-left:8px;font:600 12px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.cp .nt-table td:first-child{width:12rem}.cp .nt-table td:nth-child(3){width:17rem}
.cp .nt-table td small,.cp .cg-table td small{display:block;margin-top:2px;font-size:13px;color:var(--muted)}
.cp .nt-table td:last-child{white-space:nowrap;color:var(--muted);font-size:14px}
/* Who publishes AI research on Hugging Face (Research's feature) */
.cp .wp-table td:first-child{width:14rem}.cp .wp-more{margin:10px 0 0}.cp .wp-more summary{cursor:pointer;font-weight:600}
.cp .wp-rise{border-left:4px solid var(--f-research);padding-left:14px}
.cp .wp-chart{display:block;width:100%;max-width:640px;height:auto}
.cp .wp-chart polyline{fill:none;stroke:var(--f-research);stroke-width:2}.cp .wp-chart circle{fill:var(--f-research)}
.cp .wp-chart text{font:12px var(--body);fill:var(--ink);text-anchor:middle}.cp .wp-chart .wp-m{fill:var(--muted)}
.cp .nt-table td small.nt-beat{margin-top:6px;color:var(--ink)}.cp .ft .nt-table td small.nt-beat a{font-weight:400;text-decoration:underline}
.cp .nt-table td.cl{font-size:14px;white-space:nowrap}.cp .ft .nt-table td.cl a{font-weight:400;text-decoration:underline}
.cp .cg-wrap{margin:0 0 34px;border-top:2px solid var(--line);padding-top:10px}
.cp .cg{display:block;width:100%;height:auto;font-family:var(--body)}
.cp .cg-grid{stroke:color-mix(in srgb,var(--ink) 16%,transparent);stroke-width:1}
.cp .cg-base{stroke:var(--ink);stroke-width:1.6}
.cp .cg-tick{stroke:var(--ink)}
.cp .cg-y{fill:var(--muted);font-size:13px;text-anchor:end}.cp .cg-x{fill:var(--muted);font-size:13px;text-anchor:middle}
.cp .cg-dot{fill:var(--f-research);fill-opacity:.55;stroke:color-mix(in srgb,var(--ink) 45%,transparent);stroke-width:.6}
.cp .cg-dot.cg-built{fill:var(--bg);fill-opacity:1;stroke:var(--ink);stroke-width:1}
.cp .cg-top{fill:var(--ink)}
.cp .cg-name{fill:var(--ink);font-size:13px;font-weight:600}
.cp .cg-label{fill:var(--bg);fill-opacity:.92;stroke:color-mix(in srgb,var(--ink) 30%,transparent);stroke-width:.8}
.cp .cg-lead{stroke:var(--ink);stroke-width:1}
.cp .cg-table td:nth-child(4){white-space:nowrap}.cp .cg-table td:nth-child(4) b{font:700 16px var(--body)}
@media (max-width:640px){.cp .nt-scores li{grid-template-columns:1fr auto;gap:2px 10px}
  .cp .nt-track{grid-column:1/-1;grid-row:2}.cp .nt-pct{grid-column:2;grid-row:1;text-align:right}
  .cp .nt-table td:first-child,.cp .nt-table td:nth-child(3){width:auto}
  .cp .cg-table td:nth-child(5)::before{content:"How sure Epoch is: ";color:var(--muted)}
  .cp .cg-table td:nth-child(6)::before{content:"Weights to download: ";color:var(--muted)}}
/* Phones, on every feature and page band: small type and a short header band (title and question beside a small
   cartoon, the description under them), small big-number tiles three to a row, smaller tabs, headings and tables */
@media (max-width:640px){
  :is(.cp,.about-page) .fh{grid-template-columns:minmax(0,1fr) auto;gap:8px 10px;margin:12px 0 18px;padding:12px;border-width:2px;box-shadow:3px 3px 0 var(--line)}
  :is(.cp,.about-page) .fh-t{grid-column:1;grid-row:1;gap:10px;align-items:flex-start}
  :is(.cp,.about-page) .fh-ic{width:32px;height:32px}
  :is(.cp,.about-page) .fh-ic svg{width:19px;height:19px}
  :is(.cp,.about-page) .fh-ic.pic img{width:28px;height:21px}
  :is(.cp,.about-page) .fh :is(h1,h2){font-size:19px}
  :is(.cp,.about-page) .fh-q,.cp .fh-sub{font-size:13px;margin-top:4px}
  :is(.cp,.about-page) .fh-art{grid-column:2;grid-row:1;align-self:start;height:56px;margin:0}
  :is(.cp,.about-page) .fh .fh-d{grid-column:1/-1;padding:8px 0 0;border-top-width:2px;font-size:12.5px;line-height:1.45}
  .cp .fh-cite{margin-top:6px}
  .cp .fh-cite summary{font-size:11px;padding:2px 8px}
  .cp h2{font-size:12.5px;margin-top:22px;border-top-width:4px;padding-top:8px}
  .cp .rm-bigs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
  .cp .rm-bigs:has(>:nth-child(4):last-child){grid-template-columns:repeat(2,minmax(0,1fr))}  /* four: two by two */
  .cp .rm-big{min-width:0;padding:8px;box-shadow:2px 2px 0 var(--line)}
  .cp .rm-big b,.cp .rc .rm-big b{font-size:22px}
  .cp .rm-big span,.cp .rc .rm-big span{font-size:11px;margin-top:4px}
  .cp .gv-big{font-size:12.5px}.cp .gv-big b{font-size:26px}
  .cp .st-hero b{font-size:24px}
  .cp .sh-tabs{gap:4px 14px}
  .cp .sh-tab{font-size:12.5px}.cp .sh-tab b{font-size:10.5px}
  .cp table.mt{font-size:13px}
  .cp .mt th{font-size:9.5px}
  .cp .mt td{padding:7px 10px 7px 0}
  .cp .mt .meta{font-size:11.5px}
  .cp .mt .name{font-size:13px!important}
  .cp p{font-size:13.5px}
  /* each feature's own section headings, question lines, tables and tags: the same smaller sizes */
  .cp .jb h2{font-size:16px;margin:28px 0 8px}
  .cp .jb-q,.cp .rm .jb-q,.cp .rc .jb-q{font-size:14px}
  .cp .sd h2,.cp .ft.gv .gv-card h2{font-size:17px}
  .cp .ft .pc-hh h2,.cp .ft.gv h2.gv-h,.cp .mi .sheet > h2{font-size:18px}
  .cp .rm-t{font-size:13px}
  .cp .rm-t code{font-size:11.5px}
  .cp .rm-t td.rm-d small{font-size:10.5px}
  .cp .ft .rm-t td.rm-lab a{font-size:11px}
  .cp .rm-t td:nth-child(4)::before,.cp .rm-t td:nth-child(5)::before{font-size:11px}
  .cp .rc .sh-tab{padding:3px 8px}
  .cp .rc-w{font-size:11px}
  .cp .rc-t small{font-size:11px}
  .cp .rc .rc-t th{font-size:9px}
  /* small summary tables (a ring's legend too) and the "About these" notes stay rows (a number per cell), not a cell per line */
  .cp .ft :is(table.jb-small,table.jb-rt){display:table;width:100%}
  .cp .ft :is(.jb-small,.jb-rt) thead{display:table-header-group}
  .cp .ft :is(.jb-small,.jb-rt) tr{display:table-row;padding:0}
  .cp .ft :is(.jb-small,.jb-rt) td{display:table-cell;border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent);padding:5px 10px 5px 0}
  .cp .ft :is(.jb-small,.jb-rt) td:last-child{padding-right:0}
  /* every filterable list of deals, fines or uses: a box to scroll in, as Infra's tables (the filters stay above it) */
  .cp table.xf-t,.cp table.am-ct,.cp table.fx-t{display:block;max-height:72vh;overflow-y:auto;overscroll-behavior-y:contain;border-bottom:3px solid var(--ink)}
  /* Money that comes back, stacked: each line says which column it was */
  .cp .am-ct td::before{color:var(--muted);font:500 11px var(--body)}
  .cp .am-ct td:nth-child(1)::before{content:"From: "}.cp .am-ct td:nth-child(2)::before{content:"Into: "}
  .cp .am-ct td:nth-child(3)::before{content:"What went in: "}.cp .am-ct td:nth-child(4)::before{content:"What comes back: "}
  /* AI money: the stakes lab by lab, a card each to swipe, each investor's box beside its name (the grid is for
     wide screens) */
  .cp .ow-wrap{display:none}
  .cp .ow-labs{display:flex;gap:10px;overflow-x:auto;overscroll-behavior-x:contain;scroll-snap-type:x mandatory;padding:2px 4px 10px 0;align-items:flex-start}
  .cp .ow-lab{flex:0 0 78%;scroll-snap-align:start;border:2px solid var(--line);box-shadow:3px 3px 0 var(--line);padding:10px 12px;background:var(--bg)}
  .cp .ow-lab b{display:block;font:400 17px var(--display);margin-bottom:6px}
  .cp .ow-lab ul{list-style:none;margin:0;padding:0}
  .cp .ow-lab li{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:7px 0;border-top:1px solid color-mix(in srgb,var(--ink) 18%,transparent)}
  .cp .ow-lab li span{font:600 13px var(--body);padding-top:3px}
  .cp .ow-lab .ow-deal{min-width:0;max-width:62%;text-align:right;font-size:11.5px;padding:3px 6px}
  .cp .ow-lab .ow-deal small{font-size:10px}
  .cp .ow-key{font-size:11.5px}
  /* Lab timelines: a card per lab to swipe, its months down the card (empty months left out), the grey column last */
  .cp .lt-wrap{overflow:visible;max-height:none}
  .cp .ft .lt-t{min-width:0;display:block}
  .cp .ft .lt-t thead{display:none}
  .cp .ft .lt-t tbody:not([hidden]){display:flex;gap:10px;overflow-x:auto;overscroll-behavior-x:contain;scroll-snap-type:x mandatory;padding:2px 4px 10px 0;align-items:flex-start}
  .cp .ft .lt-t tbody + tbody:not([hidden]){margin-top:10px}
  .cp .ft .lt-t tr{display:block;flex:0 0 72%;scroll-snap-align:start;border:2px solid var(--line);box-shadow:3px 3px 0 var(--line);padding:8px 10px;background:var(--bg)}
  .cp .ft .lt-t th{display:block;padding:0 0 4px}
  .cp .ft .lt-t td{display:grid;grid-template-columns:62px minmax(0,1fr);gap:8px;padding:6px 0;border-top:1px solid color-mix(in srgb,var(--ink) 18%,transparent);font-size:12.5px}
  .cp .ft .lt-t td:empty{display:none}
  .cp .ft .lt-t td::before{content:attr(data-l);font:600 10px/1.6 var(--mono);text-transform:uppercase;color:var(--muted)}
  .cp .ft .lt-t td > *{grid-column:2}
  .cp .ft .lt-t td.lt-fut{padding-left:0;margin:0 -10px -8px;padding:6px 10px 8px}
  /* Release cards: a card per release, its facts labelled, in the box that scrolls */
  .cp .rc .rm-wrap{overflow-x:visible;overflow-y:auto}
  .cp .ft .rc-t{min-width:0;display:block}
  .cp .ft .rc-t thead{display:none}
  .cp .ft .rc-t tbody{display:block}
  .cp .ft .rc-t tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 12px;padding:9px 10px;margin:0 0 8px;border:2px solid var(--line)}
  .cp .ft .rc-t tr[hidden]{display:none}
  .cp .ft .rc-t td{display:block;border:0;padding:0;white-space:normal;font-size:12.5px}
  .cp .ft .rc-t td:nth-child(2){grid-column:1;grid-row:1}
  .cp .ft .rc-t td:nth-child(1){grid-column:2;grid-row:1;text-align:right;font-size:11.5px}
  .cp .ft .rc-t td:nth-child(6){grid-column:2;grid-row:2}  /* weights and price side by side */
  .cp .ft .rc-t td:nth-child(4),.cp .ft .rc-t td:nth-child(5),.cp .ft .rc-t td:nth-child(7){grid-column:1/-1}
  .cp .ft .rc-t td:nth-child(n+3)::before{display:block;font:600 9.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin-bottom:2px}
  .cp .ft .rc-t td:nth-child(3)::before{content:"Weights"}.cp .ft .rc-t td:nth-child(4)::before{content:"Licence"}
  .cp .ft .rc-t td:nth-child(5)::before{content:"Where you can use it"}
  .cp .ft .rc-t td:nth-child(6)::before{content:"Launch price (in / out, per 1M tokens)"}
  .cp .ft .rc-t td:nth-child(7)::before{content:"Safety report"}
}
.cp .ow-labs{display:none}
@media (max-width:640px){.cp .ow-labs{display:flex}}
/* Phones: a table's row as a small card, its name on top and the rest side by side underneath (not one value a line);
   the tables re-laid out on their own above keep theirs */
@media (max-width:640px){
  .cp .ft table.mt:not(.rc-t,.lt-t,.jb-small,.jb-rt,.am-ct,.pn-notes){display:block;max-height:72vh;overflow-y:auto;overscroll-behavior-y:contain;padding-right:4px}
  .cp .ft .mt:not(.rc-t,.lt-t,.jb-small,.jb-rt,.am-ct,.pn-notes) tbody{display:block}
  .cp .ft .mt:not(.rc-t,.lt-t,.jb-small,.jb-rt,.am-ct,.pn-notes) tr{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:7px 12px;
    margin:0 0 8px;padding:9px 10px;border:1.5px solid var(--line);box-shadow:2px 2px 0 var(--line);background:var(--bg)}
  .cp .ft .mt:not(.rc-t,.lt-t,.jb-small,.jb-rt,.am-ct,.pn-notes) tr[hidden]{display:none}
  .cp .ft .mt:not(.rc-t,.lt-t,.jb-small,.jb-rt,.am-ct,.pn-notes) td{display:block;font-size:12.5px;line-height:1.4;padding:0;border:0;text-align:left;white-space:normal;width:auto}
  .cp .ft .mt:not(.rc-t,.lt-t,.jb-small,.jb-rt,.am-ct,.pn-notes) td:first-child,
  .cp .ft .mt:not(.rc-t,.lt-t,.jb-small,.jb-rt,.am-ct,.pn-notes) td.wd{grid-column:1/-1}
  .cp .ft .mt:not(.rc-t,.lt-t,.jb-small,.jb-rt,.am-ct,.pn-notes) td:first-child{font-size:14px;font-weight:600}
  .cp .ft .mt:not(.rc-t,.lt-t,.jb-small,.jb-rt,.am-ct,.pn-notes) td:empty{display:none}
  .cp .ft .mt:not(.rc-t,.lt-t,.jb-small,.jb-rt,.am-ct,.pn-notes) td[data-l]::before{content:attr(data-l);display:block;margin:0 0 1px;
    font:600 9px/1.3 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
  /* the deal lists: date on the left, the rest flowing beside it */
  .cp .pc-k{font-size:10px;font-weight:600;letter-spacing:.03em;padding:0 4px;line-height:1.5}  /* status tags lighter than the words they tag */
  .cp .fx-t .pc-who .pc-k{margin:1px 3px 1px 0;font-size:10.5px;font-weight:600;padding:0 4px}
  .cp .fx-t td.pc-who::before{display:block;margin-bottom:2px}
  /* AI pacts and orders: each row's tag first, under the date's line, and every tag on the page one style */
  .cp .pc-stack .fx-t td.fx-s{order:-1;margin-bottom:2px}
  .cp .pc-stack .pc-k,.cp .pc-stack .fx-t .pc-who .pc-k{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;padding:0 4px;line-height:1.6}
  .cp .pc-stack .fx-t .pc-who .pc-k{text-transform:none;font-size:10.5px;font-weight:600;letter-spacing:0;padding:0 4px;margin-right:2px}  /* signers as written (US signed), on one line */
  .cp .fx-t td[data-l]:not(.pc-d)::before{content:attr(data-l) ": ";color:var(--muted);font:500 10.5px var(--body)}  /* each value says its column */
  .cp .fx-t tr{grid-template-columns:62px minmax(0,1fr);column-gap:10px;padding:5px 0}  /* one date column: values line up */
  .cp .fx-t td{font-size:12px;padding:1px 0}
  .cp table.nt-table{display:block;max-height:72vh;overflow-y:auto;overscroll-behavior-y:contain;border-bottom:3px solid var(--ink)}  /* each subject's tests in a box */
  /* New tests' best scores: the name, score and dot on one short line each */
  .cp .nt-scores li{padding:4px 0;gap:0 8px}
  .cp .nt-scores a{font-size:12.5px}
  .cp .nt-pct{font-size:11px}.cp .nt-pct b{font-size:12.5px}
  .cp .nt-track{height:10px}
  .cp .nt-track i{width:10px;height:10px;margin:-5px 0 0 -5px}
  /* Papers that made the news: a newspaper on a phone, the lead across the top, then two ruled columns, small serif */
  .cp .np-mast{font-size:10px;padding:5px 0}
  .cp .np-lead{padding:12px 0;text-align:center}
  .cp .np-lead h3{font-size:18px}
  .cp .np-lead .np-deck{font-size:12.5px}
  .cp .np-cols{column-count:2;column-gap:14px;margin-top:10px}
  .cp .np-cols .np-clip{padding:0 0 9px;margin:0 0 9px}
  .cp .np-clip h3{font-size:13px;line-height:1.22;margin:2px 0 4px}
  .cp .np-deck{font-size:11px;line-height:1.4;margin:0 0 4px}
  .cp .np-kick{font-size:8.5px;letter-spacing:.05em}
  .cp .np-by{font-size:10px;line-height:1.35}
}
"""


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
    when = (f'<div>Last update <time datetime="{escape(last)}">{escape(last[:16].replace("T", " "))} UTC</time></div>'
            if last else "")
    header = header.replace("Loading feed…", (f"<div><b>{total}</b> stories in total</div>" if total else "") + when)
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
              '.toLocaleString(undefined,{day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}))</script>')


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


def share_tags(title: str, path: str, description: str) -> str:
    """The head lines search results and link previews read, for a page built by hand (privacy)."""
    url, description = f"{rss.SITE}{path}", escape(snippet(description))
    return (f'<meta name="description" content="{description}"><link rel="canonical" href="{url}">'
            f'<meta property="og:title" content="{escape(title)}"><meta property="og:description" content="{description}">'
            f'<meta property="og:url" content="{url}"><meta property="og:image" content="{rss.SITE}og.png">'
            f'<meta name="twitter:card" content="summary_large_image">{counter()}')


def page(title: str, description: str, path: str, body: str, data: dict, parts: tuple[str, str],
         back: tuple[str, str], note: str = "") -> str:
    """A whole page: `back` is (address, words) for the link above the heading, `note` a line under the content."""
    url = f"{rss.SITE}{path}"
    header, footer = parts
    description = snippet(description)
    return (f'<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n{THEME}\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n<base href="/">\n'
            f'<title>{escape(title)}</title>\n<meta name="description" content="{escape(description)}">\n'
            f'<link rel="canonical" href="{url}">\n<link rel="icon" href="/favicon.ico">\n'
            f'<meta property="og:title" content="{escape(title)}">\n<meta property="og:description" content="{escape(description)}">\n'
            f'<meta property="og:url" content="{url}">\n<meta property="og:image" content="{rss.SITE}og.png">\n'
            f'<meta name="twitter:card" content="summary_large_image">\n{counter()}'
            f'<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>\n'
            f'<link rel="stylesheet" href="site.css">\n</head>\n<body>\n<div class="wrap">\n{header}\n<main class="cp">\n'
            f'<a class="back" href="{back[0]}">← {escape(back[1])}</a>\n{body}\n'
            + (f'<p class="note">{note}</p>\n' if note else "")
            + f'</main>\n{footer}\n</div>\n{LOCAL_TIME}\n{THEME_BUTTON}\n</body>\n</html>\n')
