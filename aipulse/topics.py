"""Topics: storylines AI Pulse follows over time (topics/), laws and news together, a page each (topics/<slug>/).

Each topic is a rule kept by hand: the tracked bills it follows (their stages are its official record) and the words
a story must have (`words`, in its headline or summary) and must not (`exclude`). A card joins a topic when it matches
the words; a tracked bill's own card joins only the topics that list it, so a US bill named "... AI Act" never lands in
the EU AI Act's story. Research papers stay in Research. A topic with nothing new for QUIET_DAYS is tagged Concluded.

The stories are the outlets' own headlines, so a topic's page loads them in the reader's browser from its events.json,
as the industry pages do; the page itself holds only our own words.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import countries, pages, photos, rss

QUIET_DAYS = 90  # a topic with no new event for this long is Concluded (kept, never deleted)
# Topics are listed by how much they're in the news: over the last TREND_DAYS, each event counts once per outlet that
# carried it, and three times over in the last HOT_DAYS. The top TRENDING with an event in the last HOT_DAYS are tagged.
TREND_DAYS, HOT_DAYS, TRENDING = 30, 7, 3
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
    "claude-mythos": dict(
        name="Anthropic's Mythos", kind="Safety",
        what="Anthropic's Mythos model, kept back over its hacking skills: who gets to use it, and what it found.",
        words=r"\bMythos\b", exclude=r"\bMythos Ventures\b"),
    "ai-ipos": dict(
        name="OpenAI and Anthropic go public", kind="Markets",
        what="The two biggest AI labs' road to the stock market: filings, hires and delays.",
        words=r"\b(OpenAI|Anthropic)\b.{0,40}\bIPO\b|\bIPO\b.{0,40}\b(OpenAI|Anthropic)\b",
        related=("openai-restructuring",)),
    "deepseek-us": dict(
        name="DeepSeek and the US", kind="Trade",
        what="How Washington and US labs answered DeepSeek: bans, chip questions and claims it copied their models.",
        words=r"\bDeepSeek\b.{0,80}\b(ban|banned|bans|security|exports?|distill\w*|Nvidia|chips?|probe|investigat\w*"
              r"|Commerce|Congress|White House|Sacks)\b|\b(ban|bans|banned)\b.{0,40}\bDeepSeek\b"
              r"|\bdistillation (campaigns?|attacks?)\b",
        exclude=r"\bR1-Distill|\bdistilled (new )?(R1|model)",
        related=("nvidia-chips-china",)),
    "meta-superintelligence": dict(
        name="Meta's superintelligence push", kind="Company",
        what="Meta's bid to catch up in AI: the Scale AI deal, the hiring spree and its superintelligence lab.",
        words=r"\bMeta\b.{0,60}\b(superintelligence|MSL|Scale AI|Alexandr Wang|poach\w*)\b"
              r"|\bSuperintelligence Labs\b|\bScale AI\b.{0,60}\bMeta\b"),
    "openai-device": dict(
        name="OpenAI's device", kind="Company",
        what="OpenAI's first hardware, designed with Jony Ive after it bought his company io.",
        words=r"\bOpenAI\b.{0,60}\b(device|hardware|gadget|smart speaker|Jony Ive)\b|\bJony Ive\b.{0,60}\bOpenAI\b"),
    "ai-music-labels": dict(
        name="Suno, Udio and the record labels", kind="Courts",
        what="The record labels' fight with AI music makers Suno and Udio, from lawsuits to licensing deals.",
        words=r"\b(Suno|Udio)\b.{0,80}\b(labels?|Warner|Universal|Sony|UMG|lawsuits?|sues?|sued|settle\w*|licens\w*"
              r"|deals?|GEMA|court|copyright)\b|\b(labels?|Warner|Universal|Sony|UMG|GEMA)\b.{0,80}\b(Suno|Udio)\b",
        related=("copyright-court",)),
    "ai-summits": dict(
        name="Global AI summits", kind="Policy",
        what="The meetings where governments try to agree on AI, from Bletchley Park to Paris and New Delhi.",
        words=r"\b(AI Action Summit|AI Impact Summit|Bletchley|Seoul AI Summit|AI Safety Summit)\b"
              r"|\bIndia\b.{0,30}\bAI summit\b|\bParis\b.{0,30}\bAI summit\b"),
    "ai-bubble": dict(
        name="AI bubble talk", kind="Markets",
        what="Whether AI spending has run ahead of its returns: bubble warnings, circular deals and what markets did.",
        words=r"\bAI bubble\b|\bbubble\b.{0,40}\bAI\b|\bcircular (deals?|financing)\b",
        exclude=r"\bBubble (launches|raises|adds|lets|unveils)\b"),
    "google-antitrust-ai": dict(
        name="Google's antitrust cases and AI", kind="Courts",
        what="Google's search monopoly cases, and how AI changed the remedies and the complaints against it.",
        words=r"\bGoogle\b.{0,80}\b(antitrust|monopoly|Mehta|remed(y|ies))\b|\b(antitrust|monopoly)\b.{0,60}\bGoogle\b"),
    "perplexity-legal": dict(
        name="Perplexity's legal fights", kind="Courts",
        what="The publishers and companies taking Perplexity to court over its AI search and shopping agents.",
        words=r"\bPerplexity\b.{0,80}\b(sues?|sued|lawsuits?|suit|court|cease|judge|block\w*)\b"
              r"|\b(sues?|sued|lawsuits?|blocks?)\b.{0,60}\bPerplexity\b",
        related=("copyright-court",)),
    "openai-microsoft": dict(
        name="OpenAI and Microsoft", kind="Company",
        what="The partnership behind ChatGPT, renegotiated as OpenAI grew: stakes, exclusivity and the AGI clause.",
        words=r"\bOpenAI\b.{0,60}\bMicrosoft\b.{0,60}\b(partnership|deal|renegotiat\w*|AGI clause|stake|contract"
              r"|exclusiv\w*|blessing)\b|\bMicrosoft\b.{0,60}\bOpenAI\b.{0,60}\b(partnership|renegotiat\w*|AGI clause"
              r"|stake|exclusiv\w*)\b",
        related=("openai-restructuring",)),
}

# Each topic's picture: one of the site's credited Wikimedia Commons photos (photos.py), and the flags of the places
# whose laws it follows (beside its tracked bills' own). The logos come from its stories (brands.py).
LOOK = {
    "eu-ai-act": ("parliament-1.jpg", ("EU",)),
    "nvidia-chips-china": ("chips-5.jpg", ("US", "CN")),
    "anthropic-pentagon": ("court-5.jpg", ("US",)),
    "chatbots-teens": ("school-3.jpg", ()),
    "copyright-court": ("court-1.jpg", ()),
    "grok-deepfakes": ("software-2.jpg", ()),
    "openai-restructuring": ("business-3.jpg", ()),
    "musk-v-openai": ("court-7.jpg", ()),
    "california-ai-laws": ("parliament-3.jpg", ("US",)),
    "us-state-preemption": ("court-8.jpg", ("US",)),
    "data-centre-power-bills": ("energy-7.jpg", ()),
    "stargate": ("datacenter-5.jpg", ("US",)),
    "apple-google-siri": ("business-6.jpg", ()),
    "korea-ai-basic-act": ("court-3.jpg", ("KR",)),
    "claude-mythos": ("software-3.jpg", ()),
    "ai-ipos": ("business-2.jpg", ()),
    "deepseek-us": ("chips-3.jpg", ("US", "CN")),
    "meta-superintelligence": ("lab-2.jpg", ()),
    "openai-device": ("software-4.jpg", ()),
    "ai-music-labels": ("conference-2.jpg", ()),
    "ai-summits": ("conference-5.jpg", ()),
    "ai-bubble": ("business-4.jpg", ()),
    "google-antitrust-ai": ("court-6.jpg", ("US",)),
    "perplexity-legal": ("court-2.jpg", ()),
    "openai-microsoft": ("business-5.jpg", ()),
}
SMALL = 25  # a topic with this many events or fewer shows each as a card; a bigger one only its milestones
LOGOS = 3   # brand logos on a topic's picture: the ones its stories name most,
LOGO_MIN = 3  # each named by this many of its stories at least

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


def _logo(card: dict) -> dict | None:
    lg = card.get("logo")
    return {k: lg[k] for k in ("name", "hex", "path")} if lg and lg.get("path") else None


def events(slug: str, cards: list[dict]) -> list[dict]:
    """The topic's events, oldest first: each matching story (with how many outlets carried it and the brand it
    names), and each stage of its tracked bills as an official record (with its place's flag)."""
    out = []
    for c in cards:
        if not matches(slug, c):
            continue
        if c.get("lifecycle"):
            life = c["lifecycle"]
            name = c["title"].split(": ", 1)[-1]
            out += [{"date": s["date"], "title": f"{name}: {s['label']}", "url": life["url"],
                     "source": life["source"], "outlets": 1, "official": True,
                     "flag": countries.flag(c["bill"].split("-")[0])}
                    for s in life["steps"] if s.get("date")]
            continue
        out.append({"date": c["date"], "title": c["title"].strip(), "url": c["url"], "source": c["source"],
                    "outlets": 1 + len({a["source"] for a in c.get("also") or []} - {c["source"]}),
                    "official": False, "logo": _logo(c)})
    out.sort(key=lambda e: (e["date"], not e["official"]))
    big = len(out) > SMALL
    for i, e in enumerate(out):  # a milestone gets a card; the rest fold into "+N more" between them
        e["milestone"] = not big or e["official"] or e["outlets"] > 1 or i in (0, len(out) - 1)
    return out


def trend(ev: list[dict], today: date) -> int:
    """How much the topic is in the news now (see TREND_DAYS)."""
    since, hot = ((today - timedelta(days=d)).isoformat() for d in (TREND_DAYS, HOT_DAYS))
    return sum(e["outlets"] * (3 if e["date"] >= hot else 1) for e in ev if e["date"] >= since)


def path(slug: str) -> str:
    return f"topics/{slug}/"


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def _logo_svg(lg: dict) -> str:
    return (f'<span class="logo" title="{escape(lg["name"])}"><svg viewBox="0 0 24 24" aria-hidden="true">'
            f'<path fill="#{escape(lg["hex"].lstrip("#"))}" d="{escape(lg["path"])}"/></svg></span>')


def _badges(slug: str, ev: list[dict]) -> str:
    """The topic's flags, then the logos its stories name most."""
    flags = list(dict.fromkeys([countries.flag(f) for f in LOOK[slug][1]]
                               + [e["flag"] for e in ev if e.get("flag")]))
    count: dict[str, list] = {}
    for e in ev:
        if e.get("logo"):
            count.setdefault(e["logo"]["name"], [0, e["logo"]])[0] += 1
    logos = [lg for n, lg in sorted(count.values(), key=lambda x: -x[0])[:LOGOS] if n >= LOGO_MIN]
    return ("".join(f'<img class="flag" src="flags/{f}" alt="">' for f in flags)
            + "".join(_logo_svg(lg) for lg in logos))


def _photo(slug: str, credits: dict) -> str:
    file = LOOK[slug][0]
    return (f'<img class="photo" src="photos/{file}" alt="" loading="lazy" '
            f'title="{escape(credits.get(file, "Photo: Wikimedia Commons"))}">')


TIMELINE_JS = r"""<script>
(() => {
  const tl = document.getElementById("timeline");
  const day = d => new Date(d.slice(0, 10) + "T00:00:00Z").toLocaleDateString(undefined, {day: "numeric", month: "short", timeZone: "UTC"});
  const el = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const icon = e => {
    if(e.flag) { const i = el("img", "flag"); i.src = "flags/" + e.flag; i.alt = ""; return i; }
    if(!e.logo) return null;
    const s = el("span", "logo"); s.title = e.logo.name;
    s.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path></path></svg>';
    const p = s.querySelector("path"); p.setAttribute("fill", "#" + e.logo.hex.replace("#", "")); p.setAttribute("d", e.logo.path);
    return s;
  };
  const pill = (cls, text) => { const li = el("li", cls); li.append(el("span", "", text)); return li; };
  const card = (e, side) => {
    const li = el("li", "ev " + side + (e.official ? " official" : " news") + (e.outlets > 1 ? " wide" : ""));
    const box = el("div", "box"), top = el("div", "top");
    top.append(el("span", "when", day(e.date)), el("span", "lane", e.official ? "Official record" : "In the news"));
    const ic = icon(e); if(ic) top.append(ic);
    const a = el("a", "", e.title); a.href = e.url; a.rel = "noopener";
    const meta = el("div", "meta", e.source + (e.outlets > 1 ? " · " + e.outlets + " outlets" : ""));
    box.append(top, a, meta); li.append(el("span", "dot"), box);
    return li;
  };
  const more = list => {
    const li = el("li", "more"), b = el("button", "", "+" + list.length + (list.length === 1 ? " more story" : " more stories"));
    b.type = "button"; b.setAttribute("aria-expanded", "false");
    const ul = el("ul"); ul.hidden = true;
    list.forEach(e => { const r = el("li"), a = el("a", "", e.title); a.href = e.url; a.rel = "noopener";
      r.append(el("span", "when", day(e.date)), a, el("span", "src", e.source)); ul.append(r); });
    b.addEventListener("click", () => { ul.hidden = !ul.hidden; b.setAttribute("aria-expanded", String(!ul.hidden)); });
    li.append(b, ul); return li;
  };
  fetch(tl.dataset.src, {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(list => {
    tl.replaceChildren();
    if(!list.length) return tl.append(el("li", "meta", "Nothing yet."));
    let year = "", n = 0, folded = [];
    const flush = () => { if(folded.length) tl.append(more(folded)); folded = []; };
    list.forEach(e => {
      if(e.date.slice(0, 4) !== year) { flush(); year = e.date.slice(0, 4); tl.append(pill("year", year)); }
      if(!e.milestone) return folded.push(e);
      flush();
      tl.append(card(e, n++ % 2 ? "right" : "left"));  // either side of the line in turn; the colour tells which kind
    });
    flush();
    tl.append(pill("year now", "Now"));
  }).catch(() => tl.replaceChildren(el("li", "meta", "Couldn't load the timeline. Try reloading the page.")));
})();
</script>"""


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write topics/ (a picture card per topic) and each topic's page: its picture and its timeline, from its
    events.json. Returns the pages' paths."""
    parts = pages.frame(conn, len(cards))
    credits = {c["photo"]: f"Photo: {photos._who(c)}, {c['licence']}" for c in photos.credits()}
    (out / "flags").mkdir(exist_ok=True)
    quiet = (today - timedelta(days=QUIET_DAYS)).isoformat()
    blocks, paths = [], []
    for slug, t in TOPICS.items():
        ev = events(slug, cards)
        for f in {countries.flag(f) for f in LOOK[slug][1]} | {e["flag"] for e in ev if e.get("flag")}:
            shutil.copy(countries.FLAGS / f, out / "flags" / f)
        latest = ev[-1]["date"] if ev else ""
        done = latest < quiet
        p = path(slug)
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "events.json").write_text(json.dumps(ev, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        badges = _badges(slug, ev)
        status = '<span class="done">Concluded</span>' if done else ""
        related = " · ".join(f'<a href="/{path(r)}">{escape(TOPICS[r]["name"])}</a>' for r in t.get("related", ()))
        body = (f'<div class="topic-hero">{_photo(slug, credits)}<div class="over"><span class="kind">{escape(t["kind"])}'
                f'</span>{status}<h1>{escape(t["name"])}</h1><div class="badges">{badges}</div></div></div>\n'
                f'<p class="intro">{escape(t["what"])}</p>\n'
                + ('<p class="legend"><span class="key official">Official record</span>'
                   '<span class="key news">In the news</span></p>\n' if any(e["official"] for e in ev) else "")
                + f'<ol class="timeline" id="timeline" data-src="/{p}events.json"><li class="meta">Loading…</li></ol>\n'
                f'{TIMELINE_JS}')
        data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": t["name"],
                "description": t["what"], "url": f"{rss.SITE}{p}"}
        (out / p / "index.html").write_text(
            pages.page(f"{t['name']} · AI Pulse", t["what"], p, body, data, parts, ("/topics/", "All topics"),
                       f"Related: {related}" if related else ""), encoding="utf-8")
        paths.append(p)
        blocks.append({"slug": slug, "done": done, "latest": latest, "badges": badges, "score": trend(ev, today),
                       "hot": latest >= (today - timedelta(days=HOT_DAYS)).isoformat()})
    blocks.sort(key=lambda b: b["latest"], reverse=True)
    blocks.sort(key=lambda b: (b["done"], -b["score"]))  # in the news most first (newest first on a tie), concluded last
    for i, b in enumerate(blocks):
        t = TOPICS[b["slug"]]
        tag = ('<span class="done">Concluded</span>' if b["done"] else
               '<span class="done hot">Trending</span>' if i < TRENDING and b["hot"] else "")
        b["html"] = (f'<a href="/{path(b["slug"])}"><span class="pic">{_photo(b["slug"], credits)}{tag}'
                     f'<span class="badges">{b["badges"]}</span></span><span class="txt">'
                     f'<span class="kind">{escape(t["kind"])}</span><b>{escape(t["name"])}</b>'
                     f'<span class="what">{escape(t["what"])}</span>'
                     + (f'<span class="meta">Latest: {_day(b["latest"])}</span>' if b["latest"] else "")
                     + "</span></a>")
    what = "Stories AI Pulse follows over time, laws and news together. Open one to see how it unfolded."
    body = (f'<h1>Topics</h1>\n<p class="intro">{escape(what)}</p>\n'
            f'<div class="topics">{"".join(b["html"] for b in blocks)}</div>\n')
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Topics", "description": what,
            "url": f"{rss.SITE}topics/"}
    (out / "topics" / "index.html").write_text(
        pages.page("Topics · AI Pulse", what, "topics/", body, data, parts, ("/", "Back to AI Pulse")), encoding="utf-8")
    return ["topics/", *paths]
