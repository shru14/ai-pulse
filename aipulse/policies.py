"""The terms of service for the whole site, AI Pulse and Pulse Pro (owner, 12 Nov 2026), at terms/, and the quiet legal
layout it shares with the privacy notice (privacy.html, static.privacy_page). Short and plain (owner: the long version
"looks like a lot"); no header band and no big headings (owner: "they also can look sophisticated"): a small title,
then each section as a row, its name on the left and its text on the right, between hairlines."""

from __future__ import annotations

from html import escape
from pathlib import Path

from . import pages, rss

UPDATED = "12 November 2026"
MAIL = "projectaipulse@gmail.com"
PATH = "terms/"
TITLE = "Terms of service"
WHAT = "The terms for using AI Pulse, its emails and the paid Pulse Pro products."
SECTIONS = [
    ("The content", "AI Pulse summarises and links to news, official records and research by others; the source is what "
                    "counts. Nothing here is legal, financial or investment advice, so check anything you act on."),
    ("Pulse Pro", "Sold to firms by invoice. A login and its outputs are for the buying firm's own use: share them inside "
                  "your firm and with your advisers, but don't resell or republish them. The Pulse Store links to other "
                  "sellers, whose own prices and terms apply."),
    ("Copyright", "Our own text, design and code are © AI Pulse, all rights reserved. Others' material stays under its "
                  "owners' terms (see Sources and licences)."),
    ("Liability", "Provided as it is. As far as the law allows, we are not liable for losses from relying on the content; "
                  "for Pulse Pro, our liability is limited to what your firm paid us in the last twelve months."),
    ("Changes and law", "Updates are posted here with their date. The law of England and Wales applies. Questions? Email us."),
]

STYLE = ("<style>"
         ".cp .pol{margin:8px 0 24px}"
         ".cp .pol-head{padding:8px 0 28px}"
         ".cp .pol-kick{margin:0 0 10px;font-size:13px;color:var(--muted)}"
         ".cp .pol-head h1{margin:0;padding:0;border:0;font:500 34px/1.15 var(--body);letter-spacing:-.01em;text-transform:none}"
         ".cp .pol-lede{margin:12px 0 0;font-size:16.5px;line-height:1.55;color:var(--muted)}"
         ".cp .pol-date{margin:10px 0 0;font-size:13.5px;color:var(--muted)}"
         ".cp .pol-row{display:grid;grid-template-columns:170px minmax(0,1fr);gap:6px 32px;align-items:start;padding:22px 0;"
         "border-top:1px solid color-mix(in srgb,var(--ink) 14%,transparent)}"
         ".cp .pol-row h2{margin:0;padding:0;border:0!important;background:none;box-shadow:none;"
         "font:500 15px/1.5 var(--body);letter-spacing:0;text-transform:none}"
         ".cp .pol-row h2::before,.cp .pol-row h2::after{display:none}"
         ".cp .pol-row p{margin:0 0 10px;font-size:15.5px;line-height:1.6}.cp .pol-row p:last-child{margin-bottom:0}"
         ".cp .pol-row table{margin:4px 0 12px;font-size:14.5px}"
         ".cp .pol-also{display:flex;align-items:center;gap:12px;padding:22px 0 0;border-top:1px solid color-mix(in srgb,var(--ink) 14%,transparent);"
         "font-size:14px;color:var(--muted)}"
         ".cp .pol-acts{margin:14px 0 0}"
         ".cp .pol-also a,.cp .pol-btn{display:inline-flex;align-items:center;height:36px;padding:0 14px;border:1px solid var(--line);"
         "border-radius:8px;font-size:14px;color:var(--ink);text-decoration:none}.cp .pol-also a:hover,.cp .pol-btn:hover{border-color:var(--ink)}"
         "@media(max-width:640px){.cp .pol-head h1{font-size:28px}.cp .pol-row{grid-template-columns:1fr;padding:18px 0}}"
         "</style>")


def doc(title: str, lede: str, sections: list[tuple[str, str]], also: tuple[str, str]) -> str:
    """A legal page's body: `lede` and each section's text are HTML; `also` is (address, name) of the other page."""
    rows = "".join(f'<section class="pol-row"><h2>{escape(h)}</h2><div>{html}</div></section>' for h, html in sections)
    return (STYLE + f'<div class="pol"><header class="pol-head"><p class="pol-kick">Legal</p><h1>{escape(title)}</h1>'
            f'<p class="pol-lede">{lede}</p><p class="pol-date">Last updated {UPDATED}</p></header>{rows}'
            f'<p class="pol-also">Also read <a href="{also[0]}">{escape(also[1])}</a></p></div>')


def build(conn, cards: list[dict], out: Path) -> list[str]:
    """Write terms/ for the news site, in the same layout as privacy.html; it goes in the sitemap."""
    button = f'<p class="pol-acts"><a class="pol-btn" href="mailto:{MAIL}">Email us</a></p>'
    body = doc(TITLE, escape(WHAT), [(h, f"<p>{escape(p)}</p>" + (button if h == SECTIONS[-1][0] else "")) for h, p in SECTIONS], ("privacy.html", "Privacy"))
    data = {"@context": "https://schema.org", "@type": "WebPage", "name": TITLE, "description": WHAT,
            "url": f"{rss.SITE}{PATH}"}
    html = pages.page(f"{TITLE} · AI Pulse", WHAT, PATH, body, data, pages.frame(conn, len(cards)), ("/", "Back to AI Pulse"))
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(html, encoding="utf-8")
    return [PATH]
