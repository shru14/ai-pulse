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
.cp .flag{flex:none;width:32px;height:24px;object-fit:cover;border:1px solid var(--line)}
.cp h1 .flag{width:60px;height:45px;border-width:2px}
.cp .kind{display:block;margin-top:22px;font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .kind + h1{margin-top:8px}
.cp h1.word{font-size:clamp(24px,3.6vw,30px)}
.cp .intro{color:var(--muted);margin:0 0 20px}
.cp .intro a{color:var(--accent)}
.cp h2{font:600 15px var(--body);text-transform:uppercase;letter-spacing:.06em;margin:30px 0 4px;border-top:6px solid #D55E00;padding-top:10px}
.cp ul{list-style:none;margin:0;padding:0}
.cp li{padding:12px 0;border-bottom:1px solid color-mix(in srgb,var(--ink) 25%,transparent)}
.cp li a{color:var(--ink);font-weight:600;text-decoration:none}
.cp li a:hover,.cp li a:focus-visible{text-decoration:underline}
.cp .meta{color:var(--muted);font-size:14px;margin-top:2px}
.cp .steps{color:var(--muted);font-size:13.5px;margin-top:2px}
.cp .what{font-size:15px;margin-top:4px;max-width:64ch}
.cp .places{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px;margin-top:20px}
.cp .places a{display:flex;align-items:center;gap:12px;border:2px solid var(--line);background:var(--bg);padding:12px 14px;color:var(--ink);font-weight:600;text-decoration:none}
.cp .places a:hover,.cp .places a:focus-visible{background:color-mix(in srgb,#D55E00 15%,var(--bg))}
.cp:has(> .kd) > .back{margin-left:calc(50% - min(560px,50vw - 16px))}
.cp .kd{width:min(1120px,calc(100vw - 32px));margin-left:calc(50% - min(560px,50vw - 16px))}  /* Industry's kinds run wide, like a topic page */
.cp .companies{grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;margin:4px 0 26px}  /* a tile per company or topic, each previewing its newest story */
.cp .companies button{display:flex;flex-direction:column;align-items:stretch;gap:10px;border:2px solid var(--line);background:var(--bg);padding:16px 18px;color:var(--ink);font:600 18px var(--body);text-align:left;cursor:pointer}
.cp .companies .head{display:flex;align-items:center;gap:12px}
.cp .companies .peek{font:400 15px/1.45 var(--body);color:var(--muted)}
.cp .companies button:hover,.cp .companies button:focus-visible{background:color-mix(in srgb,#D55E00 15%,var(--bg))}
.cp .companies button[aria-pressed="true"]{box-shadow:4px 4px 0 #D55E00}
.cp .companies .logo{color:#141925;font:700 15px var(--body)}
.cp .companies small{margin-left:auto;color:var(--muted);font-size:13px}
.cp .def{font-size:17px;line-height:1.55;margin:10px 0 14px;max-width:64ch}
.cp .def a{color:var(--ink);text-decoration:underline;text-decoration-color:var(--accent);text-decoration-thickness:2px;text-underline-offset:3px}
.cp .more-stories{margin-top:14px;font:600 15px var(--body);color:#fff;background:#0072B2;border:2px solid var(--line);padding:9px 16px;cursor:pointer}
.cp .more-stories[hidden]{display:none}
.cp .letters{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px}
.cp .letters a{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;border:2px solid var(--line);color:var(--ink);font-weight:600;text-decoration:none}
.cp .letters a:hover,.cp .letters a:focus-visible{background:color-mix(in srgb,#D55E00 15%,var(--bg))}
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
.cp .topics > a:hover,.cp .topics > a:focus-visible{transform:translate(-2px,-2px);box-shadow:6px 6px 0 #D55E00}
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
.cp .done.hot{background:#D55E00;color:#000}
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
.cp .topic-hero .kind{margin:0;color:#fff;background:#D55E00;color:#000;align-self:flex-start;padding:2px 8px;border:2px solid var(--line)}
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
.cp .lg::before{content:"";display:inline-block;width:12px;height:12px;border:2px solid var(--line);margin-right:7px;vertical-align:-1px}
.cp .lg.official::before{background:#D55E00}
.cp .lg.news::before{background:#56B4E9}
.cp .chapters{margin-top:10px}
.cp .chapter{display:grid;grid-template-columns:150px minmax(0,1fr);gap:0 10px}
.cp .chapter .yr{position:relative;border-top:2px solid var(--line)}
.cp .chapter .yr span{position:sticky;top:calc(var(--bar-h,64px) + 14px);display:block;padding-top:10px;font:400 clamp(34px,4vw,50px)/1 var(--display);color:transparent;-webkit-text-stroke:2px var(--ink)}
.cp .chapter:nth-child(odd) .yr span{color:#D55E00}
.cp ol.timeline{list-style:none;margin:0;padding:18px 0 22px;position:relative;border-top:2px dashed color-mix(in srgb,var(--ink) 30%,transparent)}
.cp ol.timeline::before{content:"";position:absolute;top:0;bottom:0;left:50%;width:4px;margin-left:-2px;background:var(--ink)}
.cp .timeline > li{border:0;padding:0;position:relative}
.cp .timeline .ev{display:flex;padding:9px 0}
.cp .timeline .ev.left{justify-content:flex-start;padding-right:calc(50% + 26px)}
.cp .timeline .ev.right{justify-content:flex-end;padding-left:calc(50% + 26px)}
.cp .timeline .ev .box{position:relative;display:flex;width:100%;border:2px solid var(--line);background:var(--bg);box-shadow:4px 4px 0 var(--line)}
.cp .timeline .ev.official .box{border-top:8px solid #D55E00}
.cp .timeline .ev.news .box{border-top:8px solid #56B4E9}
.cp .timeline .ev.wide .box{box-shadow:4px 4px 0 #0072B2}
.cp .timeline .ev.key .box{box-shadow:6px 6px 0 #D55E00}
.cp .timeline .ev .txt{flex:1;min-width:0;padding:10px 12px 11px}
.cp .timeline .ev .box::after{content:"";position:absolute;top:22px;width:24px;height:3px;background:var(--ink)}
.cp .timeline .ev.left .box::after{right:-26px}
.cp .timeline .ev.right .box::after{left:-26px}
.cp .timeline .dot{position:absolute;left:50%;top:30px;width:16px;height:16px;margin-left:-8px;border:3px solid var(--line);border-radius:50%;background:#56B4E9;z-index:1}
.cp .timeline .official .dot{background:#D55E00;border-radius:2px;transform:rotate(45deg)}
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
.cp .timeline .now span{position:relative;z-index:1;background:#D55E00;color:#000;border:2px solid var(--line);font:400 16px var(--display);padding:4px 16px;border-radius:999px}
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
.cp .contents li::before{content:counter(c,decimal-leading-zero);font:600 12px var(--mono);color:#D55E00;margin-right:7px}
.cp .contents a{font-weight:600;color:var(--ink);text-decoration:none}
.cp .contents a:hover{text-decoration:underline}
.cp .sheet{margin-top:34px;counter-increment:sheet}
.cp .mi{counter-reset:sheet}
.cp .sheet > h2::before{content:counter(sheet,decimal-leading-zero);margin-right:10px;color:#D55E00}
.cp .brief{font-size:clamp(16px,1.6vw,17.5px);line-height:1.65;margin:12px 0 0;border-left:6px solid #D55E00;padding-left:16px}
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
.cp .ranked{list-style:none;margin:0;padding:0;border-top:2px solid var(--line)}
.cp .ranked li{display:grid;grid-template-columns:30px 1fr auto;gap:10px;align-items:start;padding:10px 0;border-bottom:1px solid color-mix(in srgb,var(--ink) 25%,transparent)}
.cp .ranked .cnt{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:52px;padding:3px 6px;background:var(--st);border:2px solid var(--line);color:#000}
.cp .ranked .cnt b{font:400 18px/1 var(--display)}
.cp .ranked .cnt small{font:600 9.5px var(--mono);letter-spacing:.04em;text-transform:uppercase}
.cp .ranked .r{font:400 18px/1.1 var(--display)}
.cp .ranked a{color:var(--ink);font-weight:600;text-decoration:none;line-height:1.35}
.cp .ranked a:hover,.cp .ranked a:focus-visible{text-decoration:underline}
.cp .ranked .meta{font-size:13px;margin-top:2px}
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
.cp .issue-nav{display:flex;justify-content:space-between;gap:12px;margin-top:36px;padding-top:14px;border-top:6px solid #D55E00;font-weight:600}
.cp .issue-nav a{color:var(--ink)}
.cp .shelf{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-top:14px}
.cp .shelf a{display:flex;flex-direction:column;border:2px solid var(--line);background:var(--bg);color:var(--ink);text-decoration:none;box-shadow:4px 4px 0 var(--line);transition:transform .12s,box-shadow .12s}
.cp .shelf a:hover,.cp .shelf a:focus-visible{transform:translate(-2px,-2px);box-shadow:6px 6px 0 #D55E00}
.cp .shelf .pic{display:block;aspect-ratio:4/3;border-bottom:2px solid var(--line);overflow:hidden;background:#1b1f27}
.cp .shelf .photo{object-position:right center}
.cp .shelf .txt{display:flex;flex-direction:column;gap:2px;padding:10px 12px 12px}
.cp .shelf .num{font:600 11px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:#D55E00}
.cp .shelf b{font:400 22px/1.1 var(--display)}
.cp .cloud{--g0:#0072B2;--g1:#D55E00;--g2:#007A5A;--g3:#000}
:root[data-theme="dark"] .cp .cloud{--g0:#56B4E9;--g1:#E36A12;--g2:#009E73;--g3:#F2F2F2}
@media (max-width:1060px){.cp .contents{flex-wrap:wrap;justify-content:flex-start}}
@media (max-width:900px){.cp .shelf{grid-template-columns:repeat(3,minmax(0,1fr))}.cp .sgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.cp .shelf{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cp .grp{grid-template-columns:1fr;gap:6px}
  .cp .blocks{grid-template-columns:repeat(2,minmax(0,1fr))}
  .cp .sgrid{grid-template-columns:1fr}
  .cp .chapter.wk .yr small{position:static;display:inline;margin-left:10px}}
.cp:has(> .ft) > .back{margin-left:calc(50% - min(560px,50vw - 16px))}
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
.cp .yrs .now{transform:translateX(-100%);padding:0 5px 0 0;border:0;border-right:3px solid #D55E00;color:var(--ink)}
.cp .er{border-bottom:1px solid color-mix(in srgb,var(--ink) 18%,transparent)}
.cp .er:last-child{border-bottom:0}
.cp .er > summary{list-style:none;cursor:pointer;padding:14px 0}
.cp .er > summary::-webkit-details-marker{display:none}
.cp .er > summary:hover,.cp .er[open] > summary{background:color-mix(in srgb,#D55E00 9%,var(--bg))}
.cp .er .nm{position:relative;padding:0 12px 0 34px;font-weight:600;font-size:15px;line-height:1.25}
.cp .er .nm::before{content:"+";position:absolute;left:12px;top:-1px;font:700 16px var(--mono);color:#D55E00}
.cp .er[open] .nm::before{content:"−"}
.cp .er .nm small{display:block;margin-top:2px;color:var(--muted);font:500 11px var(--mono);letter-spacing:.04em}
.cp .trk{position:relative;display:block;min-height:24px;height:var(--h)}
.cp .yl,.cp .tn{position:absolute;top:-14px;bottom:-14px;width:1px;background:color-mix(in srgb,var(--ink) 12%,transparent)}
.cp .tn{width:2px;background:color-mix(in srgb,#D55E00 55%,transparent)}
.cp .pin{position:absolute;top:var(--t,0);display:block;margin-left:-15px;width:30px;height:23px;transition:transform .12s;z-index:1}
.cp .pin img{display:block;width:30px;height:23px;object-fit:cover;border:2px solid var(--line);box-sizing:border-box;background:#fff}
.cp .pin.r4 img{outline:3px solid #009E73;outline-offset:1px}
.cp .pin.r4::after{content:"✓";position:absolute;right:-9px;top:-9px;width:15px;height:15px;border-radius:50%;background:#009E73;color:#000;border:2px solid var(--line);font:700 9px/15px var(--body);text-align:center;box-sizing:border-box}
.cp .pin.r2 img,.cp .pin.r3 img{outline:3px solid #56B4E9;outline-offset:1px}
.cp .pin.r0 img{opacity:.4;border-style:dashed}
.cp .pin:hover{transform:scale(1.25);z-index:3}
.cp .er .det{padding:2px 18px 18px 34px}
.cp .er .det p{max-width:70ch;margin:8px 0 4px;line-height:1.5}
/* promised vs shipped: the stats, then a bar per promise from the day it was made to the day it shipped */
.cp .ps.shipped,.cp .seg.shipped,.cp .dot.shipped,.cp .chip.shipped .sw{background:#009E73}
.cp .ps.late,.cp .seg.late,.cp .dot.late,.cp .chip.late .sw{background:#E69F00}
.cp .ps.waiting,.cp .seg.waiting,.cp .dot.waiting,.cp .chip.waiting .sw{background:#56B4E9}
.cp .seg.not-found,.cp .dot.not-found,.cp .chip.not-found .sw{background:repeating-linear-gradient(135deg,var(--bg) 0 3px,color-mix(in srgb,var(--ink) 45%,transparent) 3px 5px)}
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
.cp .pbar.late{background:#E69F00}
.cp .pbar.waiting{background:#56B4E9}
.cp .pbar.not-found{background:repeating-linear-gradient(135deg,var(--bg) 0 4px,color-mix(in srgb,var(--ink) 35%,transparent) 4px 6px)}
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
/* a phone: the rule echoes fit the screen, each subject's name above its own timeline, with smaller flags placed
   on their own lines (--tp, worked out for a narrow timeline in echoes.py) */
@media (max-width:640px){
  .cp .ec-wrap{overflow:visible}
  .cp .ec{min-width:0;padding:0 0 4px}
  .cp .ec-axis,.cp .er > summary{grid-template-columns:minmax(0,1fr)}
  .cp .ec-axis > span:first-child{display:none}
  .cp .ec-axis .yrs,.cp .er .trk{margin:0 18px 0 12px}
  .cp .yrs{font-size:10.5px}
  .cp .yrs i{display:none}
  .cp .yrs > span{padding-left:3px}
  .cp .er > summary{gap:10px;padding:12px 0 14px}
  .cp .er .nm{padding-left:30px}
  .cp .er .nm small{display:inline;margin-left:8px}
  .cp .er .trk{height:var(--hp)}
  .cp .pin{top:var(--tp,0);margin-left:-11px;width:22px;height:16px}
  .cp .pin img{width:22px;height:16px;border-width:1.5px}
  .cp .pin.r4::after{width:12px;height:12px;right:-7px;top:-7px;font-size:7px;line-height:12px;border-width:1.5px}
  .cp .pin.r4 img,.cp .pin.r2 img,.cp .pin.r3 img{outline-width:2px}
  .cp .ec-legend{gap:8px 16px;font-size:13px}}
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
.cp .ins-head{border-bottom:6px solid #D55E00;padding:6px 0 14px}
.cp .ins-head .kind{font:600 12.5px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .ins-head h1{margin:6px 0 0;font-size:clamp(28px,4vw,44px)}
.cp .ins-say{font-size:17px;line-height:1.5;margin:10px 0 14px;max-width:760px}
.cp .ins-note{font-size:13px;color:var(--muted);margin:8px 0 0}
.cp .ins-bars{list-style:none;margin:0;padding:0;max-width:820px}
.cp .ins-bars li{display:grid;grid-template-columns:minmax(90px,170px) minmax(0,1fr) 54px 56px;align-items:center;gap:10px;padding:5px 0;border:0}
.cp .ins-bars .nm{font-weight:600;font-size:14.5px;overflow-wrap:anywhere}
.cp .ins-bars .tr{height:20px}
.cp .ins-bars i{display:block;height:100%;background:var(--c);border:2px solid var(--line);border-left:0;border-radius:0 4px 4px 0;box-sizing:border-box;min-width:4px}
.cp .ins-bars .v{font:400 20px/1 var(--display);text-align:right}
.cp .ins-bars .ch{font:600 12.5px var(--mono);color:var(--muted);text-align:right;white-space:nowrap}
.cp .ins-bars li:hover .nm{text-decoration:underline}
.cp .ins-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 34px}
.cp .ins-two h3{margin:0 0 6px;font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .ins-th li{grid-template-columns:minmax(90px,150px) minmax(0,1fr) 40px 62px}
.cp .ins-days{list-style:none;margin:0;padding:0 0 18px;height:96px;display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:2px;align-items:end;border-bottom:2px solid var(--line);max-width:640px;margin-top:22px}
.cp .ins-days li{position:relative;height:100%;display:flex;align-items:flex-end;padding:0;border:0}
.cp .ins-days i{display:block;width:100%;background:#56B4E9;border:2px solid var(--line);border-bottom:0;border-radius:4px 4px 0 0;box-sizing:border-box;min-height:3px}
.cp .ins-days li.we i{background:color-mix(in srgb,#56B4E9 40%,var(--bg))}
.cp .ins-days li.pk i{background:#0072B2}
.cp .ins-days li:hover i{outline:2px solid var(--ink)}
.cp .ins-days span{position:absolute;bottom:-21px;left:50%;transform:translateX(-50%);font:600 11.5px var(--mono);color:var(--muted)}
.cp .ins-days li.pk span{color:var(--ink)}
.cp .ins-key{display:flex;gap:16px;font-size:13px;color:var(--muted);margin:10px 0 0}
.cp .ins-key span{display:inline-flex;align-items:center;gap:6px}
.cp .ins-key .sw{width:14px;height:14px;background:#56B4E9;border:2px solid var(--line)}
.cp .ins-key .sw.we{background:color-mix(in srgb,#56B4E9 40%,var(--bg))}
.cp .ins-cmp li{grid-template-columns:minmax(90px,170px) minmax(0,300px) 64px minmax(0,1fr)}
.cp .ins-cmp .ch{text-align:left;font-size:13px}
.cp .ins-spark{display:flex;align-items:flex-end;gap:2px;height:34px;border-bottom:2px solid var(--line)}
.cp .ins-spark i{flex:1;background:color-mix(in srgb,var(--ink) 22%,var(--bg));border:0;border-radius:2px 2px 0 0;min-height:2px}
.cp .ins-spark i.now{background:var(--c);border:2px solid var(--line);border-bottom:0}
.cp .ins-days li .mk{position:absolute;left:50%;transform:translateX(-50%)}
.cp .mk{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;background:var(--ink);color:var(--bg);font:600 11.5px var(--mono)}
.cp .ins-key .sw.pk{background:#0072B2}
.cp .ins-money{margin-top:4px}
.cp .ins-money h3,.cp .ins-h{margin:0 0 8px;font:600 12px var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.cp .ins-figs{display:flex;flex-wrap:wrap;gap:6px 22px;margin:0 0 12px;font-size:14px;color:var(--muted)}
.cp .ins-figs b{font:400 24px/1 var(--display);color:var(--ink);margin-right:4px}
.cp .ins-figs a{color:var(--ink);font-weight:600}
.cp .ins-fund li{grid-template-columns:minmax(80px,140px) minmax(0,1fr) 30px 58px}
.cp .ins-lad li{grid-template-columns:minmax(80px,130px) minmax(0,1fr) 74px minmax(0,104px)}
.cp .ins-lad a.nm{color:var(--ink);text-decoration:none}
.cp .ins-lad a.nm:hover{text-decoration:underline}
.cp .ins-lad .lt{position:relative;height:20px;margin:0 8px}
.cp .ins-lad .lt::before{content:"";position:absolute;left:0;right:0;top:9px;border-top:2px dotted color-mix(in srgb,var(--ink) 35%,transparent)}
.cp .ins-lad .lt i{position:absolute;top:3px;width:14px;height:14px;margin-left:-7px;border-radius:50%;border:2px solid var(--line);box-sizing:border-box}
.cp .ins-lad .lt .dot{background:#0072B2}
.cp .ins-lad .lt .was{background:var(--bg)}
.cp .ins-lad .ch{text-align:left;white-space:normal;line-height:1.25}
.cp .rep{display:inline-block;margin-left:6px;font:600 10px var(--mono);letter-spacing:.05em;text-transform:uppercase;color:var(--muted);border:1px solid currentColor;padding:0 4px;vertical-align:1px}
.cp .ins-money + .ins-h{margin-top:22px}
.cp .ins-deals{max-width:820px}
.cp .ins-deals td{padding:7px 12px 7px 0;vertical-align:middle}
.cp .ins-deals td:first-child a{font-weight:600}
.cp .ins-deals .n{font:400 20px var(--display)}
.cp .kd{display:inline-block;font:600 10.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:#141925;border:2px solid var(--line);padding:1px 6px;white-space:nowrap}
.cp .kd-acquisition{background:#CC79A7}
.cp .kd-compute{background:#E69F00}
.cp .ins-riv li{grid-template-columns:minmax(90px,150px) minmax(0,1fr) 110px minmax(0,150px)}
.cp .ins-riv .split{display:flex;height:22px;gap:2px}
.cp .ins-riv .split i{display:flex;align-items:center;font:600 11.5px var(--mono);font-style:normal;color:#141925;border:2px solid var(--line);padding:0 6px;white-space:nowrap;overflow:hidden;min-width:0;box-sizing:border-box}
.cp .ins-riv .split .us{background:#56B4E9;border-radius:4px 0 0 4px}
.cp .ins-riv .split .cn{background:#E69F00;border-radius:0 4px 4px 0;justify-content:flex-end}
.cp .ins-riv .ins-spark{height:22px}
.cp .ins-riv .ins-spark i.now{--c:#E69F00}
.cp .ins-riv .ch{text-align:left}
.cp .contents.ins-toc{flex-wrap:wrap;justify-content:flex-start;gap:6px 22px}
.cp .ins-opens{font-size:14px;margin:12px 0 0;max-width:820px}
.cp .ins-risk{max-width:620px}
.cp .ins-risk td,.cp .ins-risk th{padding:6px 10px 6px 0}
.cp .ins-risk th:not(:first-child),.cp .ins-risk td.hx{text-align:center;width:90px}
.cp .ins-risk td:first-child{font-weight:600}
.cp .ins-risk td.hx{font:400 18px var(--display);background:color-mix(in srgb,#D55E00 var(--a),transparent)}
.cp .ins-risk td.z{color:var(--muted);background:none;font:400 14px var(--body)}
@media (max-width:640px){  .cp .ins-riv li{grid-template-columns:minmax(70px,90px) minmax(0,1fr) 70px;row-gap:2px}
  .cp .ins-riv .ch{grid-column:2 / -1;font-size:12px}}
@media (max-width:640px){.cp .ins-lad li{grid-template-columns:minmax(70px,96px) minmax(0,1fr) 54px;row-gap:0}
  .cp .ins-lad .ch{grid-column:2 / -1;font-size:12px}
  .cp .ins-fund li{grid-template-columns:minmax(70px,100px) minmax(0,1fr) 26px 52px}
  .cp .ins-deals td{font-size:14px}}
.cp .ins-peaks{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:20px;max-width:1120px}
.cp .ins-peak{display:flex;gap:12px;align-items:flex-start;border:2px solid var(--line);background:var(--bg);padding:12px 14px;box-shadow:4px 4px 0 var(--line)}
.cp .ins-peak .mk{flex:none;margin-top:2px}
.cp .ins-peak h3{margin:0;font-size:16px}
.cp .ins-peak .meta{margin:2px 0 0}
.cp .ins-peak ol{list-style:none;margin:8px 0 0;padding:0}
.cp .ins-peak li{padding:6px 0 0;border:0;font-size:14.5px;line-height:1.35}
.cp .ins-peak li a{color:var(--ink);font-weight:600;text-decoration:none}
.cp .ins-peak li a:hover{text-decoration:underline}
@media (max-width:640px){.cp .ins-cmp li{grid-template-columns:minmax(70px,90px) minmax(0,1fr) 50px;row-gap:0}
  .cp .ins-cmp .ch{grid-column:2 / -1;font-size:12px}
  .cp .ins-two{grid-template-columns:1fr}
  .cp .ins-bars li,.cp .ins-th li{grid-template-columns:minmax(76px,110px) minmax(0,1fr) 44px 50px;gap:7px}
  .cp .ins-days{height:80px}}
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
