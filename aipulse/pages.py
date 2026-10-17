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
.cp .what{font-size:15px;margin-top:4px;max-width:64ch}
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
.cp .def{font-size:17px;line-height:1.55;margin:10px 0 14px;max-width:64ch}
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
.cp .sd .what{font-size:14.5px}
@media (max-width:860px){.cp .sd .cols{display:flex;overflow-x:auto;scroll-snap-type:x mandatory;gap:16px;padding-bottom:8px}
  .cp .sd section{flex:0 0 85%;scroll-snap-align:start}}
.cp:has(> .tp) > .back{margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .tp{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .topic-hero{position:relative;height:clamp(240px,34vw,380px);margin-top:16px;border:2px solid var(--line);overflow:hidden;box-shadow:6px 6px 0 var(--line)}
.cp .topic-hero .photo{object-position:right center}  /* the cartoon sits on the right, clear of the title */
.cp .topic-hero .over{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;gap:10px;padding:clamp(18px,3vw,34px);background:linear-gradient(100deg,rgba(0,0,0,.85) 0%,rgba(0,0,0,.55) 45%,transparent 80%),linear-gradient(transparent 50%,rgba(0,0,0,.6))}
.cp .topic-hero .kind{margin:0;background:#F0E442;color:#000;align-self:flex-start;padding:2px 8px;border:2px solid var(--line)}
.cp .topic-hero h1{color:#fff;margin:0;font-size:clamp(34px,6vw,64px);max-width:16ch}
.cp .topic-hero .done{position:static;align-self:flex-start}
.cp .topic-hero .badges .flag{width:36px;height:27px}
.cp .topic-hero .badges .logo{width:34px;height:34px}
.cp .tp > .intro{margin:18px 0 6px;font-size:clamp(17px,2vw,20px);line-height:1.45;color:var(--ink);max-width:62ch}
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
.cp:has(> .mi) > .back{text-decoration-color:#D55E00}
.cp .mi .topic-hero .kind{background:#D55E00}
.cp .mi .lg.official::before,.cp .mi .timeline .official .dot{background:#D55E00}
.cp .mi .timeline .ev.official .box{border-top-color:#D55E00}
.cp .mi .timeline .now span{background:#D55E00}
.cp .credits li{padding:8px 0;font-size:14px;overflow-wrap:anywhere}
.cp .credits li a{font-weight:400;text-decoration:underline;text-underline-offset:2px}
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
.cp .ft > .intro{max-width:70ch;font-size:17px;line-height:1.5;color:var(--ink)}
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
.cp .er .det p{max-width:70ch;margin:8px 0 4px;line-height:1.5}
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
.cp .ins-head{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;border-top:4px solid var(--line);border-bottom:1px solid var(--line);padding:14px 0 18px;margin-top:8px}
.cp .ins-head .kind{font:600 12.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.cp .ins-head h1{margin:8px 0 0;font-size:clamp(22px,2.8vw,34px);line-height:1.25}
.cp .ins-side{display:flex;flex-direction:column;align-items:flex-end;gap:10px}
.cp .ins-head .no{font:400 clamp(44px,6vw,68px)/1 var(--display);color:transparent;-webkit-text-stroke:1.5px var(--ink)}
.cp .ins-pdf{font:600 12px var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--ink);background:var(--bg);border:1px solid var(--ink);padding:6px 10px;cursor:pointer}
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
.cp .ins-head h1 .hl{background:#F0E442;color:#000;padding:0 10px;-webkit-box-decoration-break:clone;box-decoration-break:clone}
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
.cp .ins-risk td.hx{font:600 17px var(--body);background:color-mix(in srgb,#D55E00 var(--a),transparent)}
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
  body:has(.ins-head) header.top,body:has(.ins-head) footer,body:has(.ins-head) .back,.cp .ins-pdf,.cp .mi .issue-nav{display:none!important}
  body:has(.ins-head){background:#fff!important;color:#000}
  .cp .mi,:root[data-theme] .cp .mi{--bg:#fff;--ink:#000;--muted:#3B3B3B;--line:#000;--ctx:#AADAF4;--ctx2:#D9ECF6;--focus:#0072B2;
    --f-tool:#009E73;--f-news:#56B4E9;--f-research:#C85BC3;--f-reg:#D55E00;--f-policy:#E69F00;--f-infra:#8BEC8B;--f-all:#F0E442}
  .cp .ex{break-inside:avoid;page-break-inside:avoid;margin-top:28px}
  .cp .ins-kf{break-after:page}
  .cp .kf .fl,.cp .kf .fd{animation:none!important}
  *{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
@media (max-width:700px){
  .cp .ins-head .no{display:none}
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
.cp .jb-q{font:400 clamp(20px,2.6vw,26px)/1.3 var(--body);margin:0 0 10px;max-width:46ch}
.cp .jb .jb-answer > .intro,.cp .jb .jb-ch > .intro{max-width:70ch;font-size:17px;line-height:1.5;color:var(--ink)}
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
.cp .ct-cards{column-count:3;column-gap:22px;margin-top:14px}
.cp .ct-card{break-inside:avoid;display:inline-block;width:100%;margin:0 0 22px;padding:14px 16px 10px;border-top:5px solid var(--c);background:color-mix(in srgb,var(--c) 7%,var(--bg));border-radius:0 0 6px 6px}
.cp .ct-top{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
.cp .ct-meta{font:600 11px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.cp .ct-hero{display:grid;grid-template-columns:1fr 420px;gap:28px;align-items:center}
.cp .ct-art{width:100%;height:auto;display:block}
@media (max-width:640px){.cp .ct-hero{grid-template-columns:1fr 130px;gap:12px;align-items:start}}
@media (max-width:640px){.cp .ct-hero > div{display:contents}.cp .ct-hero h1,.cp .ct-hero .jb-q{grid-column:1}.cp .ct-hero .ct-art{grid-column:2;grid-row:1/3;align-self:center}.cp .ct-hero .intro{grid-column:1/-1}}
.cp .ct-cap{display:grid;grid-template-columns:auto 1fr;gap:1px 10px;align-items:baseline;margin:12px 0 6px;padding:8px 0;border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent);border-bottom:1px solid color-mix(in srgb,var(--ink) 25%,transparent)}
.cp .ct-cap b{font:400 17px/1.2 var(--head);letter-spacing:-.01em}
.cp .ct-cap i{grid-column:2;font:800 13px var(--body);text-transform:uppercase;letter-spacing:.06em;font-style:normal;color:var(--muted)}
.cp .ct-side{font:600 10.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .ct-stamp{display:inline-block;color:color-mix(in srgb,var(--c) 75%,var(--ink));border:3px double currentColor;font:800 13px var(--mono);letter-spacing:.12em;text-transform:uppercase;padding:3px 9px;transform:rotate(-5deg);border-radius:4px}
.cp .ct-track li.ct-rule::before{width:19px;height:19px;left:-10px;top:-1px;border-radius:0;box-shadow:none;-webkit-mask:var(--gavel) center/contain no-repeat;mask:var(--gavel) center/contain no-repeat}
.cp .ct{--gavel:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cg transform='rotate(-40 12 10)'%3E%3Crect x='5' y='2' width='12' height='7' rx='1.5'/%3E%3Crect x='9.6' y='9' width='2.8' height='11' rx='1.2'/%3E%3C/g%3E%3Crect x='2' y='20' width='12' height='3.5' rx='1'/%3E%3C/svg%3E")}
.cp .ct-about{font:500 14.5px/1.4 var(--body);color:var(--muted);margin:0 0 10px}
.cp .ct-firms{margin-top:28px}
.cp .ct-firms h4{font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
.cp .ct-firms ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:0 28px}
.cp .ct-firms li{padding:7px 0;border-top:1px solid color-mix(in srgb,var(--ink) 18%,transparent);display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.cp .ct-firms li b{font:600 14px var(--body)}
.cp .ct-firms li span{font:500 12px var(--mono);color:var(--muted);white-space:nowrap}
@media (max-width:640px){.cp .ct-firms ul{grid-template-columns:1fr 1fr;gap:0 16px}.cp .ct-firms li{display:block}.cp .ct-firms li span{display:block;margin-top:2px}}
.cp .ct-track{list-style:none;margin:0;padding:0 0 0 2px;font-size:13.5px;line-height:1.4}
.cp .ft .ct-track li{position:relative;border-bottom:0;padding:0 0 10px 20px;border-left:2px solid color-mix(in srgb,var(--ink) 18%,transparent);margin-left:5px}
.cp .ft .ct-track li:last-child{border-left-color:transparent;padding-bottom:2px}
.cp .ct-track li::before{content:"";position:absolute;left:-7px;top:2px;width:12px;height:12px;border-radius:50%;background:var(--c);box-shadow:0 0 0 2px var(--bg)}
.cp .ct-d{display:block;font:600 11px var(--mono);letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.cp .ft .ct-track a{font-weight:400;color:var(--muted);text-decoration:underline}
@media (max-width:1000px){.cp .ct-cards{column-count:2}}
@media (max-width:640px){.cp .ct-cards{columns:auto;max-height:72vh;overflow-y:auto;overscroll-behavior-y:contain;padding-right:6px;border-bottom:3px solid var(--ink)}}
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
.cp .iw-wrap{max-height:78vh;overflow:auto;overscroll-behavior:contain;border-bottom:3px solid var(--ink)}
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
.cp .iw-t tr[hidden]{display:none}
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
  .cp .ft .rc-t{min-width:760px}
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
.cp .lt-r,.cp .lt-t .lt-p,.cp .lt-t .lt-s{display:block;margin:0 0 3px}
.cp .lt-p{color:var(--accent);font-weight:600}
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
/* AI pacts and orders: two halves side by side (stacked on a phone), green Pacts and vermillion Orders (Okabe-Ito
   tints, dark text); the bans as thin bars on the year, their words as page text so they read at any width */
.cp .pc h1{font-size:clamp(24px,3.6vw,30px)}
.cp .pc .jb-q{font-size:clamp(17px,2vw,20px);max-width:none}
.cp .pc-halves{display:grid;grid-template-columns:1fr 1fr;gap:22px;align-items:start;margin-top:14px}
.cp .pc-half{border:2px solid var(--line);box-shadow:5px 5px 0 var(--line);background:var(--bg);min-width:0}
.cp .pc-hh{padding:10px 14px 8px;border-bottom:2px solid var(--line)}
.cp .pc-pacts .pc-hh{background:color-mix(in srgb,#009E73 24%,var(--bg))}
.cp .pc-orders .pc-hh{background:color-mix(in srgb,#D55E00 20%,var(--bg))}
.cp .ft .pc-hh h2{font:400 26px/1.1 var(--display);margin:0;border:0;padding:0}
.cp .pc-hh p{margin:3px 0 0;font-size:14px;font-weight:600}
.cp .pc-in{padding:12px 14px 14px}
.cp .pc-lead{font:700 16.5px/1.4 var(--body);margin:2px 0 4px;padding-left:10px;border-left:5px solid var(--ink)}
.cp .pc .pc-in h3{font:700 12px var(--body);letter-spacing:.06em;text-transform:uppercase;color:var(--ink);margin:18px 0 8px;padding-top:8px;border-top:1px solid color-mix(in srgb,var(--ink) 25%,transparent)}
.cp .pc-tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(92px,1fr));gap:7px}
.cp .ft a.pc-tile{display:block;border:2px solid var(--line);padding:7px 8px;font:400 12.5px/1.3 var(--body);color:var(--ink);text-decoration:none}
.cp .ft a.pc-tile:hover,.cp .ft a.pc-tile:focus-visible{box-shadow:3px 3px 0 var(--line)}
.cp .pc-tile b{display:block;font:400 30px/1 var(--display);margin:3px 0 1px}
.cp .pc-tn{display:block;font-weight:700;font-size:13.5px}
.cp .pc-tm{display:block}
.cp .pc-no{display:block;margin-top:4px;font-weight:700;color:#A33F00}
.cp .pc-all{display:block;margin-top:4px;color:var(--muted)}
.cp .pc-bind{display:block;margin-top:4px;font-weight:700}
.cp .pc-y.pc-rat{background:var(--ink);box-shadow:0 0 0 2px #009E73}
:root[data-theme=dark] .cp .pc-no{color:#F5A36B}
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
.cp .pc-y.pc-r{background:#D55E00}
.cp .pc-n.pc-ring{border:1.5px solid var(--ink)}
.cp .pc-key{display:flex;flex-wrap:wrap;gap:3px 14px;align-items:center;font-size:12.5px;color:var(--muted);margin:6px 0 0}
.cp .pc-key > span{display:inline-flex;gap:5px;align-items:center}
.cp .pc-rows{width:100%;border-collapse:collapse}
.cp .pc-rows td{font-size:13.5px;line-height:1.3;padding:6px 8px 6px 0;border-top:1px solid color-mix(in srgb,var(--ink) 15%,transparent);vertical-align:top}
.cp .pc-rows td.pc-d{white-space:nowrap;font-weight:700;width:1%}
.cp .pc-rows td.pc-s{white-space:nowrap;width:1%;text-align:right}
.cp .ft .pc-rows td.pc-s a,.cp .ft .pc-ban a{font-weight:400;color:var(--ink);text-decoration:underline;text-underline-offset:3px}
.cp .ft .pc-rows td.pc-s a{display:block;font-size:12px;margin-top:3px}
.cp .pc-k{display:inline-block;font:700 11px var(--body);text-transform:uppercase;letter-spacing:.04em;border:1.5px solid var(--line);padding:0 5px;color:#111}
.cp .pc-ord{background:#E9B9D5}.cp .pc-inv{background:#A8D8F2}.cp .pc-crt{background:#9CC3E0}
.cp .pc-mo{display:grid;grid-template-columns:repeat(12,1fr);font-size:11px;color:var(--muted);padding:0 1.5%}
.cp .pc-ban{margin:9px 0 2px}
.cp .pc-ban p{margin:0 0 3px;font-size:13.5px;line-height:1.35}
.cp .ft .pc-ban p a{text-decoration:none}
.cp .ft .pc-ban p a:hover{text-decoration:underline}
.cp .pc-ban p span{display:block;color:var(--muted);font-size:12.5px}
.cp .ft .pc-ban p span a{color:var(--muted)}
.cp .pc-ban svg{display:block;height:auto}
.cp .pc-gl{stroke:var(--ink);stroke-opacity:.14}
.cp .pc-today{stroke:var(--ink);stroke-dasharray:2 2}
.cp .pc-bar{stroke:#D55E00;stroke-width:6}
.cp .pc-bar.pc-on{stroke-dasharray:10 4}
.cp .pc-mk{fill:#D55E00;stroke:var(--ink);stroke-width:1.5}
.cp .pc-end{fill:var(--bg);stroke:var(--ink);stroke-width:1.5}
.cp .pc-tick{stroke:var(--ink);stroke-width:2.5}
@media (max-width:900px){.cp .pc-halves{grid-template-columns:1fr}}
@media (max-width:640px){.cp .pc-gw{max-height:72vh;overflow-x:auto}.cp .pc-tiles{grid-template-columns:repeat(2,1fr)}
  .cp .pc-grid th,.cp .pc-grid td{padding:4px 1px;font-size:13px}
  .cp .pc-grid thead th{font-size:9.5px;letter-spacing:0}
  .cp .pc-grid thead th small{font-size:9.5px}
  .cp .pc-grid th[scope=row]{padding-right:4px;line-height:1.2}
  .cp .pc-in{padding:12px 10px 14px}}
.cp .ft .cs-t td.cs-canada a{background:color-mix(in srgb,#D55E00 28%,var(--bg))}
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
"""


def write_css(out: Path) -> None:
    """site.css: the front page's styles (its masthead and footer) and these pages' own."""
    style = re.search(r"<style>(.*?)</style>", TEMPLATE.read_text(encoding="utf-8"), re.S).group(1)
    (out / "site.css").write_text(style + STYLE, encoding="utf-8")


def frame(conn=None, total: int = 0) -> tuple[str, str]:
    """The front page's masthead (no stream links; Subscribe and Glossary open on the front page) and footer. Without
    a database (the photo credits and privacy pages) the masthead leaves out the story count and last update."""
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


def share_tags(title: str, path: str, description: str) -> str:
    """The head lines search results and link previews read, for a page built by hand (privacy, photo credits)."""
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
