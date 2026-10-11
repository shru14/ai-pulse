"""Topics: storylines AI Pulse follows over time (topics/), laws and news together, a page each (topics/<slug>/).

Each topic is a rule kept by hand: the tracked bills it follows (their stages are its official record) and the words
a story must have (`words`, in its headline or summary) and must not (`exclude`). A card joins a topic when it matches
the words; a tracked bill's own card joins only the topics that list it, so a US bill named "... AI Act" never lands in
the EU AI Act's story. Research papers stay in Research. A topic with nothing new for QUIET_DAYS is Concluded.

The stories are the outlets' own headlines, so a topic's page loads them in the reader's browser from its events.json,
as the industry pages do; the page itself holds only our own words.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import pages, rss

QUIET_DAYS = 90  # a topic with no new event for this long is Concluded (kept, never deleted)
STREAMS = ("news", "policy", "regulation", "infra", "tool")  # not research: papers aren't events

# slug: name, kind (the block's label), what (our own words), bills, words, exclude, related topics
TOPICS = {
    "eu-ai-act": dict(
        name="EU AI Act", kind="Law",
        what="The EU's law on AI: its adoption, the rules for general-purpose models, and the Digital Omnibus that "
             "amended it.",
        bills=("EU-2021-0106", "EU-2025-0359"),
        words=r"\bEU AI Act\b|\bEuropean AI Act\b|\bAI Act\b.{0,80}\b(EU|Europe|European|Brussels|Commission|GPAI)\b"
              r"|\b(EU|Europe|European|Brussels|Commission)\b.{0,80}\bAI Act\b|\bGPAI\b|general[- ]purpose AI code"
              r"|\bEU AI Office\b|Digital Omnibus"),
    "nvidia-chips-china": dict(
        name="Nvidia chips to China", kind="Trade",
        what="US rules on selling AI chips to China, and how Nvidia, Beijing and other countries responded.",
        bills=("US-119-hr-5885", "US-119-s-3150"),
        words=r"\b(H20|H200|Blackwell|Nvidia|AI chips?)\b.{0,60}\b(China|Chinese|Beijing|exports?)\b"
              r"|\b(China|Chinese|Beijing)\b.{0,60}\b(H20|H200|Nvidia)\b|export controls?.{0,40}\b(chips?|AI)\b"
              r"|\bchip exports?\b|\bGAIN AI Act\b"),
    "anthropic-pentagon": dict(
        name="Anthropic and the Pentagon", kind="Company",
        what="Anthropic's dispute with the US Department of Defense over military use of Claude, and the "
             "supply-chain-risk label that followed.",
        words=r"\bAnthropic\b.{0,120}\b(Pentagon|Department of War|Defense Department|Department of Defense|Hegseth"
              r"|supply[- ]chain risk)\b|\b(Pentagon|Department of War|Hegseth)\b.{0,120}\bAnthropic\b"),
    "chatbots-teens": dict(
        name="Chatbots and teens", kind="Safety",
        what="Lawsuits, laws and company changes over how AI chatbots treat children and teenagers.",
        bills=("US-119-hr-10719", "US-119-hr-8382", "US-119-s-5171"),
        words=r"\bCharacter\.AI\b|\b(chatbots?|ChatGPT|AI companions?)\b.{0,60}\b(teens?|teenagers?|minors?|child"
              r"|children|kids|suicide)\b|\b(teens?|teenagers?|minors|children|kids)\b.{0,40}\b(chatbots?|AI "
              r"companions?)\b|ChatGPT for Teens|\bSB ?243\b",
        related=("grok-deepfakes", "california-ai-laws")),
    "copyright-court": dict(
        name="AI training and copyright in court", kind="Courts",
        what="Court cases and settlements over training AI on copyrighted books, music, news and images.",
        words=r"\b(copyright|fair use)\b.{0,80}\b(lawsuit|suit|court|ruling|rules|judge|settle\w*|sues?|sued|trial)\b"
              r"|\b(lawsuit|court|ruling|judge|settle\w*|sues?|sued)\b.{0,80}\b(copyright|fair use)\b|\bBartz\b"),
    "grok-deepfakes": dict(
        name="Grok deepfakes", kind="Safety",
        what="The sexualised images made with xAI's Grok, and the bans, orders and lawsuits that followed.",
        words=r"\bGrok\b.{0,80}\b(deepfakes?|sexual\w*|obscene|nude|undress\w*|nonconsensual|CSAM|child)\b"
              r"|\b(ban|bans|banned|block|blocks|blocked)\b.{0,40}\bGrok\b",
        related=("chatbots-teens",)),
    "openai-restructuring": dict(
        name="OpenAI's restructuring", kind="Company",
        what="OpenAI's move from a nonprofit-controlled lab to a for-profit company, and the deals and challenges "
             "along the way.",
        words=r"\bOpenAI\b.{0,60}\b(restructur\w*|for-profit|nonprofit|non-profit|public benefit corporation"
              r"|recapitali[sz]\w*)\b",
        related=("musk-v-openai",)),
    "musk-v-openai": dict(
        name="Musk v. OpenAI", kind="Courts",
        what="Elon Musk's lawsuit against OpenAI and Sam Altman, from filing to trial and verdict.",
        words=r"\bMusk\b.{0,60}\b(lawsuit|suit|trial|sues?|sued|jury|court|deposition|testif\w*)\b.{0,60}\bOpenAI\b"
              r"|\bOpenAI\b.{0,60}\b(lawsuit|trial|jury|deposition)\b.{0,40}\bMusk\b|Musk-OpenAI trial"
              r"|\bMusk v\.? OpenAI\b",
        related=("openai-restructuring",)),
    "california-ai-laws": dict(
        name="California's AI laws", kind="Law",
        what="California's AI bills and orders: SB 53 on frontier AI safety, SB 243 on companion chatbots, and what "
             "came after.",
        words=r"\bSB ?53\b|\bSB ?243\b|\bSB ?1047\b|\bNewsom\b.{0,60}\bAI\b|\bAI\b.{0,40}\bNewsom\b"
              r"|\bCalifornia\b.{0,40}\bAI (law|laws|bill|bills|safety)\b",
        related=("us-state-preemption", "chatbots-teens")),
    "us-state-preemption": dict(
        name="US preemption of state AI laws", kind="Law",
        what="The federal push to stop US states from passing their own AI laws: the moratorium, the executive "
             "orders and the pushback.",
        bills=("US-119-s-3557",),
        words=r"\bpreempt\w*.{0,40}\b(state|AI)\b|\bstate AI laws?\b|\bmoratorium on state|block states.{0,40}\bAI\b"
              r"|\bone rulebook\b",
        related=("california-ai-laws",)),
    "data-centre-power-bills": dict(
        name="Data centres and power bills", kind="Energy",
        what="Who pays for the electricity AI data centres need: pledges, bills and grid limits.",
        bills=("US-119-hr-6529",),
        words=r"\bdata cent(er|re)s?\b.{0,60}\b(electricity|energy costs?|power bills?|ratepayers?|grid)\b"
              r"|\b(electricity|power) (bills?|prices?)\b.{0,40}\bdata cent(er|re)s?\b",
        related=("stargate",)),
    "stargate": dict(
        name="Stargate", kind="Infrastructure",
        what="OpenAI's data centre venture with SoftBank and Oracle, site by site.",
        words=r"\bStargate\b",
        related=("data-centre-power-bills",)),
    "apple-google-siri": dict(
        name="Apple, Google and Siri", kind="Company",
        what="Apple's deal to rebuild Siri on Google's Gemini models.",
        words=r"\bSiri\b.{0,60}\bGemini\b|\bGemini\b.{0,60}\bSiri\b|\bApple\b.{0,40}\bGoogle\b.{0,40}\b(Siri|deal)\b"),
    "korea-ai-basic-act": dict(
        name="South Korea's AI Basic Act", kind="Law",
        what="South Korea's AI law, its enforcement decree and the guidelines that put it into practice.",
        words=r"\bAI Basic Act\b|\bKorea\w*\b.{0,40}\bAI (law|act)\b"),
}

_RULES = {slug: (re.compile(t["words"], re.I), re.compile(t["exclude"], re.I) if t.get("exclude") else None)
          for slug, t in TOPICS.items()}


def matches(slug: str, card: dict) -> bool:
    """Whether this card belongs to the topic."""
    t = TOPICS[slug]
    if card.get("category") not in STREAMS:
        return False
    if card.get("bill"):  # a tracked bill: only where the topic lists it
        return card["bill"] in t.get("bills", ())
    words, exclude = _RULES[slug]
    text = f"{card.get('title') or ''} {card.get('summary') or ''}"
    return bool(words.search(text)) and not (exclude and exclude.search(text))


def events(slug: str, cards: list[dict]) -> list[dict]:
    """The topic's events, oldest first: each matching story (with how many outlets carried it), and each stage of
    its tracked bills as an official record."""
    out = []
    for c in cards:
        if not matches(slug, c):
            continue
        if c.get("lifecycle"):
            life = c["lifecycle"]
            name = c["title"].split(": ", 1)[-1]
            out += [{"date": s["date"], "title": f"{name}: {s['label']}", "url": life["url"],
                     "source": life["source"], "outlets": 1, "official": True}
                    for s in life["steps"] if s.get("date")]
            continue
        out.append({"date": c["date"], "title": c["title"].strip(), "url": c["url"], "source": c["source"],
                    "outlets": 1 + len({a["source"] for a in c.get("also") or []} - {c["source"]}),
                    "official": False})
    return sorted(out, key=lambda e: (e["date"], not e["official"]))


def path(slug: str) -> str:
    return f"topics/{slug}/"


EVENTS_JS = r"""<script>
(() => {
  const ol = document.getElementById("topic-events");
  const day = d => new Date(d.slice(0, 10) + "T00:00:00Z").toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"});
  const month = d => new Date(d.slice(0, 7) + "-01T00:00:00Z").toLocaleDateString(undefined, {month: "long", year: "numeric", timeZone: "UTC"});
  const note = text => { const li = document.createElement("li"); li.className = "meta"; li.textContent = text; ol.replaceChildren(li); };
  fetch(ol.dataset.src, {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(list => {
    if(!list.length) return note("Nothing yet.");
    ol.replaceChildren();
    let last = "";
    list.forEach(e => {
      if(e.date.slice(0, 7) !== last) {
        last = e.date.slice(0, 7);
        const h = document.createElement("li"); h.className = "month"; h.textContent = month(e.date); ol.append(h);
      }
      const li = document.createElement("li"), a = document.createElement("a"), meta = document.createElement("div");
      if(e.official) li.className = "official";
      a.href = e.url; a.rel = "noopener"; a.textContent = e.title;
      meta.className = "meta";
      meta.textContent = [day(e.date), e.official ? "Official record · " + e.source : e.source,
                          e.outlets > 1 ? e.outlets + " outlets" : ""].filter(Boolean).join(" · ");
      li.append(a, meta); ol.append(li);
    });
  }).catch(() => note("Couldn't load the story. Try reloading the page."));
})();
</script>"""


def _block(slug: str, latest: str | None) -> str:
    t = TOPICS[slug]
    when = f'<span class="meta">Latest: {_day(latest)}</span>' if latest else ""
    return (f'<a href="/{path(slug)}"><span class="kind">{escape(t["kind"])}</span>'
            f'<b>{escape(t["name"])}</b><span class="what">{escape(t["what"])}</span>{when}</a>')


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write topics/ (a block per topic) and each topic's page with its events.json. Returns the pages' paths."""
    parts = pages.frame(conn, len(cards))
    latest, paths = {}, []
    for slug, t in TOPICS.items():
        ev = events(slug, cards)
        latest[slug] = ev[-1]["date"] if ev else None
        p = path(slug)
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "events.json").write_text(json.dumps(ev, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        related = " · ".join(f'<a href="/{path(r)}">{escape(TOPICS[r]["name"])}</a>' for r in t.get("related", ()))
        body = (f'<span class="kind">{escape(t["kind"])}</span>\n<h1>{escape(t["name"])}</h1>\n'
                f'<p class="intro">{escape(t["what"])}</p>\n'
                f'<p class="intro">How it unfolded, oldest first: each event links to the official record or the '
                f'outlet\'s own page.</p>\n'
                f'<ol class="events" id="topic-events" data-src="/{p}events.json"><li class="meta">Loading…</li></ol>\n'
                f'{EVENTS_JS}')
        data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": t["name"],
                "description": t["what"], "url": f"{rss.SITE}{p}"}
        (out / p / "index.html").write_text(
            pages.page(f"{t['name']} · AI Pulse", t["what"], p, body, data, parts, ("/topics/", "All topics"),
                       f"Related: {related}" if related else ""), encoding="utf-8")
        paths.append(p)
    quiet = (today - timedelta(days=QUIET_DAYS)).isoformat()
    order = sorted(TOPICS, key=lambda s: latest[s] or "", reverse=True)
    live = [s for s in order if (latest[s] or "") >= quiet]
    done = [s for s in order if (latest[s] or "") < quiet]
    what = "Stories AI Pulse follows over time, laws and news together. Open one to see how it unfolded."
    body = (f'<h1>Topics</h1>\n<p class="intro">{escape(what)}</p>\n'
            f'<h2>Following</h2>\n<div class="topics">{"".join(_block(s, latest[s]) for s in live)}</div>\n'
            + (f'<h2>Concluded</h2>\n<p class="meta">Nothing new for {QUIET_DAYS} days.</p>\n'
               f'<div class="topics">{"".join(_block(s, latest[s]) for s in done)}</div>\n' if done else ""))
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Topics", "description": what,
            "url": f"{rss.SITE}topics/"}
    (out / "topics" / "index.html").write_text(
        pages.page("Topics · AI Pulse", what, "topics/", body, data, parts, ("/", "Back to AI Pulse")), encoding="utf-8")
    return ["topics/", *paths]
