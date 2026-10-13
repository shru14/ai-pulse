"""Promised vs shipped (promises/): headlines in which a company says it will release something ("OpenAI plans to
launch its GPT Store next week"), each matched to a later headline saying it did ("OpenAI launches GPT Store"), drawn
as a bar from the promise to the launch. The company must be the subject of both headlines, and every name the promise
gives ("GPT", "Store") must be in the launch's headline. A promise past its date (or 18 months old) with no launch
found is kept out of the list and the numbers, in a section of its own that says our matching found no launch: we
can't tell a broken promise from a launch reported in words we don't match. FIXES
corrects the matcher by hand. Rebuilt with the site, so a new promise or launch joins at the next run. Headlines are the outlets' own, so the promises load in the
reader's browser from promises.json, as the topics' timelines do; the page itself holds only our own words. Linked
from Industry's strip on the front page.
"""
from __future__ import annotations

import bisect
import json
import re
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import classify, cluster, pages, rss
from .static import TEMPLATE

PATH = "promises/"


SINCE = "2023-01-01"
WINDOW_DAYS = 548  # a launch counts up to 18 months after the promise
RARE_BEFORE = 20  # a name in fewer headlines than this before the promise is the promise's own ("Orion", "Operator")
SUBJECT = 32  # a headline's subject: a company named within its first characters, before the verb

# Hand corrections, by the promise's card id: the launch's URL where the matcher missed one, or None to drop a
# headline that isn't a promise.
FIXES: dict[str, str | None] = {}

_V = (r"(launch|release|ship|roll out|unveil|debut|open[- ]source|introduce|bring|add|offer|start|begin"
      r"|make .{0,30} available)\b")
PROMISE = re.compile(
    r"\b(coming soon|(is|are) coming to|is coming|comes? (later|next)|in the coming (weeks|months)"
    r"|later this (year|month|summer|fall|autumn|spring|winter)|(early|late|by) next year|next (month|week)"
    r"|by (the )?end of (the |this )?year|by year-end|will (soon )?(be )?" + _V
    + r"|(plans?|planning|set|expected|preparing|prepares|poised|gearing up|readies|readying|hopes) to" + _V
    + r"|\bto " + _V + r"|teases)", re.I)
# not a company's promise: predictions, money, people leaving, research write-ups, lists
NOISE = re.compile(
    r"\b(predict\w*|AI is coming for|coming to (Disrupt|TechCrunch|Sessions|SXSW)|Disrupt 20|top \d+|best|vs\.?"
    r"|compar\w+|raises|raised|funding|seed|Series [A-F]|IPO|public offering|valuation|valued|revenue|grow|hire"
    r"|hiring|layoffs?|invest\w*|billion|spend|\$\d|data cent(er|re)|demand|lawsuit|sue|startup|former|ex-\w+"
    r"|researchers?|GPUs|too \w+ to|TechCabal Daily|thinks|talks|ha(s|ve) to|needs? to|ready to|able to|how to"
    r"|why)\b", re.I)
# a verb before the "to ..." makes it a purpose ("Microsoft unveils Copilot to bring AI to ..."), not a promise
DONE = re.compile(
    r"\b(launch(es|ed)|releas(es|ed)|unveil(s|ed)|introduc(es|ed)|debut(s|ed)|announc(es|ed)|partner(s|ed|ing)?"
    r"|teams? up|teamed up|join(s|ed)?|signs?|inks?|taps|uses|used|leaves|left|publishes|nears|eyes|bets|backed"
    r"|deal|rolls out|brings|gives|adds|opens|expands|wants|working|acquires|buys|collaborate\w*|gets|aims?)\b", re.I)
SHIP = re.compile(
    r"\b(launch(es|ed)?|releas(es|ed)|rolls? out|rolled out|rolling out|now available|available (now|today|to|in|for"
    r"|on)|is here|are here|is live|goes live|unveil(s|ed)|debut(s|ed)|introduc(es|ed|ing)|opens?( up)? to|ships?"
    r"|shipped|generally available|general availability|arrives?|out now|brings|open[- ]sources?d?"
    r"|open[- ]sourcing)\b", re.I)
# a launch headline's words after these are about something else ("... powered by Gemini", "... rival to o1")
_ASIDE = re.compile(r"\b(powered by|built on|based on|using|with|rival\w*|response|against|vs\.?|than|like|alongside"
                    r"|after)\b.*", re.I)
_PEOPLE = set("altman sam musk elon cook tim zuckerberg mark jensen huang nadella satya pichai sundar amodei dario "
              "hassabis demis suleyman mustafa".split())
_GENERIC = set("ai new report ceo us uk eu says plans plan next year month week later coming soon early end launch "
               "release model models app apps chip chips tool tools feature features genai generative ai-powered "
               "ai-generated agent agents chatbot assistant llm llms".split()) | _PEOPLE
# a description, not a name ("AI-powered", "Gemini-powered"), and everyday words that name nothing of their own
_DESCRIBES = re.compile(r"ai-\w+|[\w.]+-(powered|based|focused|fueled|optimi[sz]ed|native|enhanced|generated|driven)")
_COMMON = set("tv home health search cloud store music tag app phone mac pc browser glasse speaker car kid teen chat "
              "voice video image photo mode workspace office".split())
_MONTHS = "january february march april may june july august september october november december".split()
_WORD = re.compile(r"[A-Za-z0-9][\w.+\-]*")
_COMPANY_WORDS = {w for c in classify.COMPANY_TERMS for w in c.lower().split()} - {"ai"} | {"deepmind", "aws"}
_PREFIX = re.compile(r"^(Report|Exclusive|Sources?)\s*:\s*")


def _word(w: str) -> str:
    """A headline's word in one form: lower case, no possessive or plural ("Macs" -> "mac")."""
    w = re.sub(r"['’]s$", "", w.lower().strip("."))
    return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w


def _words(title: str) -> set[str]:
    return {_word(w) for w in _WORD.findall(title)}


def _owner(word: str) -> str | None:
    return next((c for c, rx in classify._companies.items() if rx.search(word)), None)


def subject(title: str, before: int) -> str | None:
    """The company a headline is about: one named in its first SUBJECT characters, before position `before`."""
    t = _PREFIX.sub("", title)
    end = min(SUBJECT, before - (len(title) - len(t)))
    found = [(m.start(), c) for c, rx in classify._companies.items() if (m := rx.search(t)) and m.start() < end]
    return min(found)[1] if found else None


def names(title: str, company: str) -> set[str]:
    """What the promise names: capitalised words after the first, words with digits ("GPT-5", "A3"), not the
    company's own name, months, years, people or another company's product."""
    t = _PREFIX.sub("", _ASIDE.sub("", title))
    out = set()
    for w in _WORD.findall(t):
        lw = _word(w)
        if (lw in _GENERIC or lw in _MONTHS or lw in cluster._STOP or lw in _COMPANY_WORDS or _DESCRIBES.fullmatch(lw)
                or re.fullmatch(r"(19|20)\d\d", lw) or _owner(w) not in (None, company)):
            continue
        if re.search(r"\d", w) or (w[0].isupper() and not t.startswith(w)) or re.search(r"[a-z][A-Z]", w):
            out.add(lw)
    return out


def due(title: str, d: date) -> date | None:
    """The date the headline gives for the release, read generously (the last day it could mean)."""
    t, y = title.lower(), d.year
    if re.search(r"coming weeks|next week|later this month|this month", t):
        return d + timedelta(days=60)
    if "coming months" in t:
        return d + timedelta(days=183)
    if re.search(r"later this year|this (summer|fall|autumn|winter)|by (the )?end of (the |this )?year|by year-end", t):
        return date(y, 12, 31)
    if "next month" in t:
        return d + timedelta(days=62)
    if "early next year" in t:
        return date(y + 1, 6, 30)
    if "next year" in t:
        return date(y + 1, 12, 31)
    if m := re.search(r"\b(?:by|in) (" + "|".join(_MONTHS) + r")\b", t):
        month = _MONTHS.index(m.group(1)) + 1
        return _month_end(y if month >= d.month else y + 1, month)
    if m := re.search(r"\b(spring|summer|fall|autumn) ((?:19|20)\d\d)", t):
        return _month_end(int(m.group(2)), {"spring": 6, "summer": 9, "fall": 12, "autumn": 12}[m.group(1)])
    if (m := re.search(r"\b(early |late )?((?:19|20)\d\d)\b", t)) and int(m.group(2)) >= y:
        return date(int(m.group(2)), 6, 30) if m.group(1) == "early " else date(int(m.group(2)), 12, 31)
    if m := re.search(r"\bq([1-4])\b|(first|second|third|fourth) quarter", t):
        q = int(m.group(1)) if m.group(1) else ["first", "second", "third", "fourth"].index(m.group(2)) + 1
        return _month_end(y if q >= (d.month - 1) // 3 + 1 else y + 1, q * 3)
    if "coming soon" in t:
        return d + timedelta(days=120)
    return None


def _month_end(y: int, m: int) -> date:
    return (date(y, m, 28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


def promises(cards: list[dict], today: date) -> list[dict]:
    """Every promise found since SINCE, newest first, with the launch found for it (or not) and its status."""
    stories = [s for c in cards if c["category"] in ("tool", "news") for s in [c, *(c.get("also") or [])]]
    seen_on: dict[str, list[str]] = {}  # each word: the dates of the headlines it is in, to tell new names from old
    for s in stories:
        for w in _words(s["title"]):
            seen_on.setdefault(w, []).append(s["date"])
    for dates in seen_on.values():
        dates.sort()
    launches = []
    for s in stories:
        # the part of the headline with the verb: not a subtitle ("X releases Y: ... on DGX Spark") or a lead-in
        # ("Finally, the wait is over: Meta unveils Llama 3")
        t = next((part for part in s["title"].split(": ") if SHIP.search(part)), "")
        if (m := SHIP.search(t)) and not PROMISE.search(s["title"]) and (who := subject(t, m.start())):
            launches.append((s["date"], who, _words(_ASIDE.sub("", t)), s))
    launches.sort(key=lambda x: x[0])
    starts = [x[0] for x in launches]
    by_url = {s["url"]: s for s in stories}
    out, seen = [], set()
    for c in sorted(cards, key=lambda c: c["date"]):
        if c["category"] not in ("tool", "news") or c["date"] < SINCE or FIXES.get(c["id"], "") is None:
            continue
        title = c["title"].strip()
        m = PROMISE.search(title)
        if not m or NOISE.search(title) or DONE.search(title[:m.start()]):
            continue
        who = subject(title, m.start())
        named = who and names(title, who)
        if not named:
            continue
        # something new: a name rarely in the news before, a name with a number ("GPT-5"), or a new number of the
        # company's own product ("Llama 3")
        own = {w for w in named if re.search(r"[a-z]", w) and w not in _COMMON and (
            re.search(r"\d", w) or bisect.bisect_left(seen_on.get(w, []), c["date"]) < RARE_BEFORE)}
        own |= {w for w in named if re.fullmatch(r"[\d.]+", w) and any(_owner(n) == who for n in named)}
        if not own or (who, frozenset(named)) in seen:  # nothing new named; or the same promise reported again
            continue
        seen.add((who, frozenset(named)))
        d = date.fromisoformat(c["date"])
        until = (d + timedelta(days=WINDOW_DAYS)).isoformat()
        # A promise of several versions ("GPT-4.1, o3 and o4 mini") is kept when one of them is out; a promise to
        # open-source something, only when it is open-sourced.
        versions = {w for w in named if re.search(r"\d", w)}
        need = named - versions if len(versions) > 1 else named
        opened = re.search(r"open[- ]sourc", title, re.I)
        launch = by_url.get(FIXES.get(c["id"]) or "")
        if not launch:  # the same day counts: "Meta prepares to launch Llama 4" and "Meta releases Llama 4", 5 Apr 2025
            launch = next((s for when, w, words, s in launches[bisect.bisect_left(starts, c["date"]):]
                           if when <= until and w == who and s["url"] != c["url"] and need <= words
                           and (len(versions) < 2 or versions & words)
                           and (not opened or re.search(r"open[- ]?(sourc|weight)", s["title"], re.I))), None)
        out.append(_promise(c, who, d, due(title, d), launch, today))
    return sorted(out, key=lambda p: p["date"], reverse=True)


def _promise(c: dict, who: str, d: date, by: date | None, launch: dict | None, today: date) -> dict:
    row = {"date": c["date"], "company": who, "title": c["title"].strip(), "url": c["url"], "source": c["source"],
           "due": by.isoformat() if by else ""}
    if launch:
        took = (date.fromisoformat(launch["date"]) - d).days
        late = (date.fromisoformat(launch["date"]) - by).days if by else 0
        row |= {"status": "late" if late > 0 else "shipped", "days": took, "late": max(late, 0),
                "launch": {k: launch[k] for k in ("date", "title", "url", "source")}}
    elif (by and by >= today) or (not by and (today - d).days <= WINDOW_DAYS):
        row["status"] = "waiting"  # before its date, or without one and not yet WINDOW_DAYS old
    else:
        row["status"] = "not-found"
    return row


PROMISES_JS = r"""<script>
(() => {
  const box = document.getElementById("promises"), bar = document.getElementById("pf");
  const fmt = d => new Date(d + "T00:00:00Z").toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"});
  const el = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const link = e => { const a = el("a", "", e.title); a.href = e.url; a.rel = "noopener"; return a; };
  const days = n => n === 1 ? "1 day" : n + " days";
  const WORDS = {shipped: "Shipped", late: "Shipped late", waiting: "Waiting"};
  const ms = d => Date.parse(d + "T00:00:00Z"), DAY = 864e5, today = box.dataset.today;
  const LOGOS = JSON.parse(document.getElementById("logos").textContent);
  // a company's initials, for one without a mark: "IBM", "Baidu" -> "B", "Character.AI" -> "CA"
  const initials = n => /^[A-Z]{2,4}$/.test(n) ? n : n.split(/[\s.]+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();
  const logo = name => {  // the front page's own company marks, else the initials in the same circle
    const s = el("span", "logo"); s.title = name;
    if(LOGOS[name]) s.innerHTML = LOGOS[name]; else { s.classList.add("ini"); s.textContent = initials(name); }
    return s;
  };
  fetch(box.dataset.src, {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(all => {
    // the promises our matching found no launch for go in a table of their own, out of the list and the numbers
    const list = all.filter(p => p.status !== "not-found"), missed = all.filter(p => p.status === "not-found");
    const miss = document.getElementById("missed");
    if(missed.length) {
      const tb = el("tbody");
      missed.forEach(p => {
        const tr = el("tr"), co = el("td"), pr = el("td");
        co.append(p.company); pr.append(link(p), el("div", "meta", p.source));
        tr.append(co, pr, el("td", "", fmt(p.date)), el("td", "", p.due ? fmt(p.due) : "None given")); tb.append(tr);
      });
      const t = el("table", "mt pv"), th = el("thead"), hr = el("tr");
      ["Company", "The promise", "Promised", "Due"].forEach(w => hr.append(el("th", "", w)));
      th.append(hr); t.append(th, tb);
      miss.querySelector(".n").textContent = missed.length;
      miss.append(t); miss.hidden = false;
    }
    if(!list.length) return box.replaceChildren(el("p", "meta", "No promises yet."));
    // one plain bar per promise: its length is the days from the promise (up to 18 months), its colour how it went
    const SPAN = 548, after = d => Math.round(ms(d) / DAY);
    const head = el("div", "pr-head"); head.append(el("span", "", "The promise"), el("span", "", "Days from the promise"));
    const ol = el("ol", "pr-list");
    list.forEach(p => {
      const li = el("li", "pr"); li.dataset.s = p.status;
      const info = el("div", "pi"), top = el("div", "top");
      top.append(logo(p.company), el("span", "co", p.company), el("span", "ps " + p.status, WORDS[p.status]));
      info.append(top, link(p), el("div", "meta", p.source + " · " + fmt(p.date)));
      if(p.launch) {
        const l = el("div", "ln"); l.append(el("span", "lbl", "Launch"), link(p.launch),
          el("div", "meta", p.launch.source + " · " + fmt(p.launch.date)));
        info.append(l);
      }
      const since = d => after(d) - after(p.date);  // days from the promise
      // how long: to the launch; still waiting, so far
      const n = p.launch ? p.days : since(today);
      const t = el("div", "pt"), b = el("span", "pbar " + p.status);
      b.style.width = "max(6px, " + (Math.min(n, SPAN) / SPAN * 100).toFixed(2) + "%)";
      const said = p.launch ? (p.days === 0 ? "Same day" : days(p.days)) + (p.late ? ", " + days(p.late) + " late" : "") :
        days(n) + " so far" + (p.due ? ", due " + fmt(p.due) : "");
      t.append(b, el("span", "lab", said));
      li.append(info, t); ol.append(li);
    });
    box.replaceChildren(head, ol);
    // the stats: how the promises turned out, the typical wait and overrun, and each company's record
    const ORDER = ["shipped", "late", "waiting"];
    const median = a => { if(!a.length) return null; const s = [...a].sort((m, n) => m - n), h = s.length >> 1;
      return s.length % 2 ? s[h] : Math.round((s[h - 1] + s[h]) / 2); };
    const stats = document.getElementById("pstats"), out = el("div", "st-out"), obar = el("div", "obar"), olab = el("div", "olab");
    out.append(el("h3", "", "How " + list.length + " promises turned out"));
    ORDER.forEach(s => {
      const n = list.filter(p => p.status === s).length; if(!n) return;
      const seg = el("span", "seg " + s); seg.style.flexGrow = n; seg.title = WORDS[s] + ": " + n;
      obar.append(seg);
      const l = el("span", "", ""); l.style.flexGrow = n; l.append(el("b", "", n), " " + WORDS[s].toLowerCase()); olab.append(l);
    });
    out.append(obar, olab);
    const hero = el("div", "st-hero");
    const tile = (n, unit, words) => { if(n == null) return; const d = el("div"); d.append(el("b", "", n + " " + unit), el("span", "", words)); hero.append(d); };
    const wait = median(list.filter(p => p.launch).map(p => p.days)), over = median(list.filter(p => p.late).map(p => p.late));
    tile(wait, wait === 1 ? "day" : "days", "typical wait from promise to launch");
    tile(over, over === 1 ? "day" : "days", "typical overrun, when a launch came after its date");
    const co = el("div", "st-co"), grid = el("div", "crs"); co.append(el("h3", "", "By company"), grid);
    const by = {}; list.forEach(p => (by[p.company] = by[p.company] || []).push(p));
    Object.entries(by).sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0])).forEach(([name, ps]) => {
      const row = el("div", "cr"), dots = el("span", "dots");
      ps.sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status)).forEach(p => {
        const d = el("a", "dot " + p.status); d.href = p.url; d.rel = "noopener"; d.title = WORDS[p.status] + ": " + p.title; dots.append(d);
      });
      const kept = ps.filter(p => p.launch).length;
      const who = el("div", "cw"); who.append(logo(name), el("span", "nm", name));
      row.append(who, dots, el("span", "meta", kept + " of " + ps.length + " shipped"));
      grid.append(row);
    });
    stats.replaceChildren(out, hero, co);
    // the filter buttons, which are also the colours' key
    const count = s => list.filter(p => !s || p.status === s).length;
    [["", "All"], ["shipped", "Shipped"], ["late", "Shipped late"], ["waiting", "Waiting"]].forEach(([s, w]) => {
      const b = el("button", "chip " + (s || "all")); b.type = "button"; b.setAttribute("aria-pressed", String(!s));
      b.append(el("span", "sw"), w + " ", el("b", "", count(s)));
      b.addEventListener("click", () => {
        bar.querySelectorAll("button").forEach(o => o.setAttribute("aria-pressed", String(o === b)));
        ol.querySelectorAll(".pr").forEach(li => li.hidden = !!s && li.dataset.s !== s);
      });
      bar.append(b);
    });
  }).catch(() => box.replaceChildren(el("p", "meta", "Couldn't load the promises. Try reloading the page.")));
})();
</script>"""


def _logos() -> dict[str, str]:
    """The front page's company marks (its LOGOS, Lobe Icons, MIT), so a company looks the same on both pages."""
    found = re.search(r"const LOGOS = (\{.*?\n\});", TEMPLATE.read_text(encoding="utf-8"), re.S)
    return json.loads(re.sub(r",\s*\}$", "}", found.group(1))) if found else {}


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write promises/: the page, and promises.json it draws from. Returns its path."""
    (out / PATH).mkdir(parents=True, exist_ok=True)
    found = promises(cards, today)
    (out / PATH / "promises.json").write_text(json.dumps(found, separators=(",", ":"), ensure_ascii=False),
                                              encoding="utf-8")
    logos = {k: v for k, v in _logos().items() if k in {p["company"] for p in found}}
    marks = json.dumps(logos).replace("</", "<\\/")  # safe inside the page's <script>
    what = ("When an AI company says it will release something, how long until it ships? Promises since 2023 whose "
            "launch we found, or whose time isn't up yet, drawn from the day each was made to the day it shipped.")
    body = (f'<div class="ft">\n<h1>Promised vs shipped</h1>\n<p class="intro">{escape(what)} We look for a launch '
            'headline up to 18 months later.</p>\n'
            '<section class="pstats" id="pstats" aria-label="The promises in numbers"></section>\n'
            '<h2>The promises</h2>\n'
            '<div class="pf" id="pf" role="group" aria-label="Show"></div>\n'
            f'<div class="pr-wrap" id="promises" data-src="/{PATH}promises.json" data-today="{today.isoformat()}">'
            '<p class="meta">Loading…</p></div>\n'
            '<section id="missed" hidden><h2>No launch found: <span class="n"></span></h2>\n'
            '<p class="intro">These promises are past their date, or 18 months old, and our matching found no launch '
            'headline for them. That is a limit of our data, not a finding about the company: the launch may have been '
            'reported in words we don\'t match, or by an outlet we don\'t read.</p></section>\n</div>\n'
            f'<script type="application/json" id="logos">{marks}</script>\n'
            + PROMISES_JS + "\n")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Promised vs shipped",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH / "index.html").write_text(
        pages.page("Promised vs shipped · AI Pulse", what, PATH, body, data, pages.frame(conn, len(cards)),
                   ("/industry/", "Back to Industry"),
                   "Headlines are the outlets' own, each linking to its story; updated with every run."), encoding="utf-8")
    return [PATH]
