"""The terms of service for the whole site, AI Pulse and Pulse Pro (owner, 12 Nov 2026), at terms/. Short and plain
(owner: the long version "looks like a lot"). The privacy notice stays at privacy.html (static.privacy_page)."""

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
    ("Changes and law", f"Updates are posted here with their date. The law of England and Wales applies. Questions: {MAIL}."),
]


def body() -> str:
    return (f'<p class="pol-date">Last updated {UPDATED}</p>'
            + "".join(f"<h2>{escape(h)}</h2><p>{escape(p)}</p>" for h, p in SECTIONS))


STYLE = "<style>.cp .pol-date{color:var(--muted);font-size:14px;margin:0 0 4px}</style>"


def build(conn, cards: list[dict], out: Path) -> list[str]:
    """Write terms/ for the news site, in the same shape as privacy.html; it goes in the sitemap."""
    head = pages.band("infra", "M7 3h8l4 4v14H7zM15 3v4h4M10 12h6M10 16h6", "photos/cartoons/pages/standards.svg",
                      TITLE, "What are the rules for using AI Pulse?", escape(WHAT))
    data = {"@context": "https://schema.org", "@type": "WebPage", "name": TITLE, "description": WHAT,
            "url": f"{rss.SITE}{PATH}"}
    html = pages.page(f"{TITLE} · AI Pulse", WHAT, PATH, STYLE + head + body(), data,
                      pages.frame(conn, len(cards)), ("/", "Back to AI Pulse"))
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(html, encoding="utf-8")
    return [PATH]
