"""Promised vs shipped (promises/): headlines in which a company says it will release something ("OpenAI plans to
launch its GPT Store next week"), each matched to a later headline saying it did ("OpenAI launches GPT Store"), drawn
as a bar from the promise to the launch. The company must be the subject of both headlines, and every name the promise
gives ("GPT", "Store") must be in the launch's headline. The matcher only proposes: the page shows the promises in
CHECKED, each checked by hand with its launch, and `python -m aipulse promises` lists what the matcher finds that
isn't checked yet. A promise past its date (or 18 months old) with no launch found is kept out of the list and the
numbers, in a section of its own that says we found no launch: we can't tell a broken promise from a launch reported
in words we don't match, or by an outlet we don't read. Headlines are the outlets' own, so the promises load in the
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

# Every promise the page shows, checked by hand, by its headline's URL: the URL of the launch's headline (the day it
# was available, not an announcement), "" when we found no launch, or None to leave it out: not a promise, or it
# shipped on a day no headline in our data gives. Checked 13 Oct 2026.
CHECKED: dict[str, str | None] = {
    # shipped
    "https://the-decoder.com/openai-prepares-to-launch-gpt-5-but-big-leaps-are-unlikely/":
        "https://www.marktechpost.com/2025/08/07/openai-just-released-gpt-5-the-smartest-fastest-and-most-useful-openai-model/",
    "https://the-decoder.com/openai-expected-to-release-gpt-4-1-o3-and-o4-mini-models/":
        "https://siliconangle.com/2025/04/14/openai-launches-new-gpt-4-1-series-language-models-developers/",
    "https://the-decoder.com/meta-reportedly-prepares-to-launch-llama-4-after-delays-and-internal-overhaul/":
        "https://www.marktechpost.com/2025/04/05/meta-ai-just-released-llama-4-scout-and-llama-4-maverick-the-first-set-of-llama-4-models/",
    "https://siliconangle.com/2025/02/14/baidu-open-source-ernie-large-language-model-series/":
        "https://siliconangle.com/2025/06/29/chinas-baidu-declares-war-openai-others-open-sourcing-ernie-ai-model/",
    "https://siliconangle.com/2024/11/13/openai-hopes-launch-first-ai-agent-called-operator-january/":
        "https://siliconangle.com/2025/01/23/openai-releases-operator-agent-rivals-enhance-ai-services/",
    "https://the-decoder.com/openai-reportedly-plans-to-release-full-version-of-its-o1-reasoning-model-this-year/":
        "https://the-decoder.com/openai-launches-o1-and-chatgpt-pro-for-200-per-month/",
    "https://techcrunch.com/2024/10/24/openai-reportedly-plans-to-release-its-orion-ai-model-by-december/":
        "https://techcrunch.com/2025/02/27/openai-unveils-gpt-4-5-orion-its-largest-ai-model-yet/",
    "https://siliconangle.com/2024/08/27/openai-reportedly-preparing-launch-new-strawberry-ai-model/":
        "https://www.marktechpost.com/2024/09/12/openai-introduces-openai-strawberry-o1-a-breakthrough-in-ai-reasoning-with-93-accuracy-in-math-challenges-and-ranks-in-the-top-1-of-programming-contests/",
    "https://the-decoder.com/apple-reportedly-plans-to-debut-on-device-llm-in-ios-18-prioritizing-privacy-and-performance/":
        "https://techcrunch.com/2024/10/28/apple-intelligence-goes-live-with-ios-181-update/",  # not the WWDC unveiling
    "https://siliconangle.com/2024/03/11/elon-musks-xai-open-source-grok-language-model/":
        "https://techcrunch.com/2024/03/17/xai-open-sources-base-model-of-grok-but-without-any-training-code/",
    "https://the-decoder.com/metas-llama-3-is-set-to-release-in-july-and-could-be-twice-the-size/":
        "https://www.marktechpost.com/2024/04/18/finally-the-wait-is-over-meta-unveils-llama-3-pioneering-a-new-era-in-open-source-a/",
    "https://techcrunch.com/2023/11/22/elon-musk-says-xais-chatbot-grok-will-launch-to-x-premium-subscribers-next-week/":
        "https://techcrunch.com/2023/12/08/xs-ai-chatbot-grok-now-rolled-out-to-all-u-s-premium-subscribers-english-language-users-are-next/",
    "https://the-decoder.com/googles-next-generation-ai-model-gemini-to-launch-this-fall/":
        "https://siliconangle.com/2023/12/06/google-debuts-gemini-powerful-generative-ai-model-yet-advanced-reasoning-native-multimodality/",
    "https://techcrunch.com/2023/07/21/chatgpt-comes-to-android-next-week-but-you-can-sign-up-today/":
        "https://the-decoder.com/openais-chatgpt-app-for-android-is-now-available/",
    # no launch found
    "https://www.itweb.co.za/article/netapp-and-oracle-to-launch-fully-managed-cloud-storage-service-for-demanding-ai-and-enterprise-workloads/rW1xL75nyEmMRk6m": "",
    "https://siliconangle.com/2026/03/13/aws-will-bring-cerebras-wafer-size-wse-3-chip-cloud-platform/": "",
    "https://the-decoder.com/openai-researcher-reveals-details-of-new-ai-model-with-potential-performance-leap/": "",
    "https://the-decoder.com/sap-and-openai-plan-to-launch-an-ai-platform-for-germanys-public-sector-using-microsoft-azure/": "",
    "https://techcrunch.com/2025/01/22/samsungs-smartthings-to-introduce-ai-features-that-simplify-your-daily-routines/": "",
    "https://techcrunch.com/2024/08/29/ibm-cloud-will-offer-intel-gaudi-3-chips-next-year/": "",  # shipped, no headline in our data
    "https://siliconangle.com/2024/04/11/report-apple-planning-bring-new-ai-focused-m4-chips-entire-line-macs/": "",  # likewise
    # left out
    "https://techcrunch.com/2025/05/07/apple-is-looking-to-add-ai-search-engines-to-safari/": None,  # court testimony, not a promise
    "https://techcrunch.com/2025/03/17/openai-to-start-testing-chatgpt-connectors-for-google-drive-and-slack/": None,  # a test
    "https://the-decoder.com/openai-reportedly-plans-to-unveil-ph-d-level-super-agents-at-the-end-of-january/": None,  # a rumour
    "https://siliconangle.com/2025/10/14/nvidia-start-shipping-ai-optimized-dgx-spark-desktop-computer/": None,  # shipped 15 Oct 2025
    "https://techcrunch.com/2025/05/02/google-will-soon-start-letting-kids-under-13-use-its-gemini-chatbot/": None,  # rolled out May 2025
    "https://techcrunch.com/2025/11/25/character-ai-will-offer-interactive-stories-to-kids-instead-of-open-ended-chat/": None,  # launch day's
    "https://siliconangle.com/2024/12/16/salesforce-launch-agentforce-2-0-change-digital-labor-enterprise/": None,  # announced Dec 2024, available Feb 2025
    "https://the-decoder.com/amazon-to-launch-ai-enhanced-alexa-subscription-in-october/": None,  # unveiled Feb 2025, out from late Mar
    "https://siliconangle.com/2023/05/23/microsofts-ai-powered-copilot-coming-windows-11/": None,  # announced 21 Sep 2023, out 26 Sep
}

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
    if "next week" in t:
        return d + timedelta(days=14)
    if re.search(r"coming weeks|later this month|this month", t):
        return d + timedelta(days=60)
    if "coming months" in t:
        return d + timedelta(days=183)
    if re.search(r"this year|this (summer|fall|autumn|winter)|by (the )?end of (the |this )?year|by year-end", t):
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
    """The promises the page shows: those in CHECKED, newest first, each with its checked launch (or none)."""
    by_url = {s["url"]: s for c in cards for s in [c, *(c.get("also") or [])]}
    out = []
    for url, launch in CHECKED.items():
        if launch is None or not (s := by_url.get(url)):
            continue
        title = s["title"].strip()
        m = PROMISE.search(title)
        d = date.fromisoformat(s["date"])
        out.append(_promise(s, subject(title, m.start() if m else len(title)), d, due(title, d), by_url.get(launch),
                            today))
    return sorted(out, key=lambda p: p["date"], reverse=True)


def candidates(cards: list[dict], today: date) -> list[dict]:
    """What the matcher finds that isn't checked yet: new promises, and a launch for a checked promise without one."""
    return [p for p in found(cards, today)
            if p["url"] not in CHECKED or (CHECKED[p["url"]] == "" and p.get("launch"))]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a promises/<day> branch: each promise it adds or gives a launch, and the ones it
    leaves out; None when it changes nothing. `base` is main's copy of this file."""
    import ast
    from . import approve
    had = next((ast.literal_eval(n.value) for n in ast.parse(base).body if isinstance(n, ast.AnnAssign)
                and isinstance(n.target, ast.Name) and n.target.id == "CHECKED"), {})
    changed = {u: v for u, v in CHECKED.items() if u not in had or had[u] != v}
    rows = [("Shipped" if v else "No launch found", v or "", u) for u, v in changed.items() if v is not None]
    dropped = [u for u, v in changed.items() if v is None]
    if not rows and not dropped:
        return None
    return approve.note("Promised vs shipped", f"promise{'s' * (len(rows) != 1)}", branch,
                        ("Found", "Launch headline", "Promise"), rows, dropped)


def found(cards: list[dict], today: date) -> list[dict]:
    """Every promise the matcher finds since SINCE, newest first, with the launch it finds for it (or not)."""
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
    out, seen = [], set()
    for c in sorted(cards, key=lambda c: c["date"]):
        if c["category"] not in ("tool", "news") or c["date"] < SINCE:
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
        # the same day counts: "Meta prepares to launch Llama 4" and "Meta releases Llama 4", 5 Apr 2025
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
  const WORDS = {shipped: "Shipped", late: "Shipped late", waiting: "No launch found yet"};
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
    // what the sample is, so its pattern is read as these companies', not the whole industry's
    const cos = {}; list.forEach(p => cos[p.company] = (cos[p.company] || 0) + 1);
    const [topCo, topN] = Object.entries(cos).sort((a, b) => b[1] - a[1])[0], years = list.map(p => p.date.slice(0, 4)).sort();
    document.getElementById("psample").textContent = list.length + " promises from " + Object.keys(cos).length +
      " companies, made " + years[0] + "–" + years[years.length - 1] + ", " + topN + " of them " + topCo + "'s. A small sample: " +
      "it shows these companies' record, not the whole industry's." +
      (missed.length ? " " + missed.length + " more, with no launch found, are listed at the end." : "");
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
      // how long: to the launch; with none found yet, since the promise
      const n = p.launch ? p.days : since(today);
      const t = el("div", "pt"), b = el("span", "pbar " + p.status);
      b.style.width = "max(6px, " + (Math.min(n, SPAN) / SPAN * 100).toFixed(2) + "%)";
      const said = p.launch ? (p.days === 0 ? "Same day" : days(p.days)) + (p.late ? ", " + days(p.late) + " late" : "") :
        days(n) + " since the promise" + (p.due ? ", due " + fmt(p.due) : "");
      t.append(b, el("span", "lab", said));
      li.append(info, t); ol.append(li);
    });
    box.replaceChildren(head, ol);
    // the stats: how the promises turned out, the typical wait and overrun, and each company's record
    const ORDER = ["shipped", "late", "waiting"];
    const median = a => { if(!a.length) return null; const s = [...a].sort((m, n) => m - n), h = s.length >> 1;
      return s.length % 2 ? s[h] : Math.round((s[h - 1] + s[h]) / 2); };
    const stats = document.getElementById("pstats"), out = el("div", "st-out"), obar = el("div", "obar"), olab = el("div", "olab");
    out.append(el("h3", "", "Where " + list.length + " promises stand"));
    ORDER.forEach(s => {
      const n = list.filter(p => p.status === s).length; if(!n) return;
      const seg = el("span", "seg " + s); seg.style.flexGrow = n; seg.title = WORDS[s] + ": " + n;
      obar.append(seg);
      const l = el("span", "", ""); l.style.flexGrow = n; l.append(el("b", "", n), " " + WORDS[s].toLowerCase()); olab.append(l);
    });
    out.append(obar, olab);
    const hero = el("div", "st-hero");
    const tile = (n, unit, words) => { if(n == null) return; const d = el("div"); d.append(el("b", "", n + " " + unit), el("span", "", words)); hero.append(d); };
    // a typical overrun only from 5 late launches up: from fewer it is one or two promises, not a pattern
    const lates = list.filter(p => p.late).map(p => p.late);
    const wait = median(list.filter(p => p.launch).map(p => p.days)), over = lates.length >= 5 ? median(lates) : null;
    const launched = list.filter(p => p.launch).length;
    tile(wait, wait === 1 ? "day" : "days", "median wait from promise to launch, across " + launched + " launches");
    tile(over, over === 1 ? "day" : "days", "median overrun, across " + lates.length + " launches after their date");
    const co = el("div", "st-co"), grid = el("div", "crs"); co.append(el("h3", "", "By company"), grid);
    const by = {}; list.forEach(p => (by[p.company] = by[p.company] || []).push(p));
    Object.entries(by).sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0])).forEach(([name, ps]) => {
      const row = el("div", "cr"), dots = el("span", "dots");
      ps.sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status)).forEach(p => {
        const d = el("a", "dot " + p.status); d.href = p.url; d.rel = "noopener"; d.title = WORDS[p.status] + ": " + p.title; dots.append(d);
      });
      // counts, not a rate: a rate would leave out the promises with no launch found, and flatter the company
      const kept = ps.filter(p => p.launch).length, open = ps.length - kept;
      const gone = missed.filter(p => p.company === name).length;
      const who = el("div", "cw"); who.append(logo(name), el("span", "nm", name));
      row.append(who, dots, el("span", "meta", [kept && kept + " shipped", open && open + " no launch yet",
        gone && gone + " none found"].filter(Boolean).join(", ")));
      grid.append(row);
    });
    stats.replaceChildren(out, hero, co);
    // the filter buttons, which are also the colours' key
    const count = s => list.filter(p => !s || p.status === s).length;
    [["", "All"], ["shipped", "Shipped"], ["late", "Shipped late"], ["waiting", WORDS.waiting]].forEach(([s, w]) => {
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
    what = ("When an AI company says it will release something, how long until it ships? Promises made since 2023, "
            "each checked by hand against the day a headline says it was out, drawn from the promise to that day.")
    body = ('<div class="ft">\n'
            + pages.feature_head(PATH, "Promised vs shipped", what.split("? ", 1)[0] + "?",
                                 f"{escape(what.split('? ', 1)[1])} We look for a launch headline up to 18 months later.")
            + '<p class="intro" id="psample"></p>\n'
            '<section class="pstats" id="pstats" aria-label="The promises in numbers"></section>\n'
            '<h2>The promises</h2>\n'
            '<div class="pf" id="pf" role="group" aria-label="Show"></div>\n'
            f'<div class="pr-wrap" id="promises" data-src="/{PATH}promises.json" data-today="{today.isoformat()}">'
            '<p class="meta">Loading…</p></div>\n'
            '<section id="missed" hidden><h2>No launch found: <span class="n"></span></h2>\n'
            '<p class="intro">These promises are past their date, or 18 months old, and we found no launch '
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
