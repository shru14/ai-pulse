"""The monthly issue: a booklet for each month of 2026 on (monthly/<YYYY-MM>/), shelved at monthly/.

Each issue has the month in brief (a short summary), the stories most outlets carried, a week-by-week timeline (with
the tracker's laws that passed a stage that month), the top stories of each stream, the glossary's words of the
month and the storylines (topics.py) that moved. Rules that moved lists every tracked law that passed a stage that month
and every standard published that month, each with a badge for where it got to. An issue is made once its month is over.

The summary is written by an open-source model run on this machine or the GitHub runner: Qwen3-4B-Instruct-2507
(Alibaba's Qwen team, Apache 2.0; https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), as packaged in GGUF by
Unsloth (pinned below), with llama.cpp's Python library. No API is called and nothing is billed. The model (~2.5 GB)
is downloaded into data/summary-models/ when a summary is due. It reads only the month's most reported headlines and
is checked: every name and number it writes must be in them, else it tries again, and after TRIES it writes nothing
(the issue then has no summary). Each summary is written once and kept in the database (table `monthly`).

It's optional: without the library (`pip install llama-cpp-python`) or the model, issues have no summary and
everything else works as before. The stories load in the reader's browser from each issue's issue.json, so the
page itself holds only our own words, as on the topics' pages.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html import escape
from pathlib import Path

from . import countries, feeds, glossary, pages, rss, standards, topics

FIRST = "2026-01"  # the first issue (the owner's choice, 11 Oct 2026: 2026 on, no earlier years)
REPO = "unsloth/Qwen3-4B-Instruct-2507-GGUF"
REVISION = "a06e946bb6b655725eafa393f4a9745d460374c9"  # pinned: the same model writes every issue
FILE = "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
MODEL = "Qwen3-4B-Instruct-2507 Q4_K_M"  # stored with each summary
MODEL_DIR = Path(__file__).resolve().parent.parent / "data" / "summary-models"
HEADLINES = 40  # the summary reads this many of the month's most reported headlines
FEWER = {3: 30, 4: 25}  # ...and fewer on the last tries: a busy month (August 2026) otherwise runs long every time
TRIES = 4
MAX_CHARS = 900  # about 140 words: a longer summary is a list of headlines, not a summary
TOP = 10        # What mattered most
PER_WEEK = 4    # stories a week on the timeline (2+ outlets), besides the laws that passed a stage
PER_STREAM = 3
WORDS = 8
STORYLINES = 8
FRONT = 2  # issues on the front page
BADGES = {"in_force": "In force", "signed": "Signed", "passed_legislature": "Passed", "passed_chamber": "Passed a chamber",
          "standard": "Standard", "vetoed": "Vetoed", "withdrawn": "Withdrawn"}  # Rules that moved, in this order
STREAMS = {"tool": "Releases", "news": "Industry", "research": "Research", "regulation": "Regulation",
           "policy": "Policy", "infra": "Infra"}
LAB_PAPERS = {"Hugging Face Daily Papers", "Apple Machine Learning Research"}  # papers the labs put their name to

SCHEMA = """
CREATE TABLE IF NOT EXISTS monthly (
    month   TEXT PRIMARY KEY,  -- YYYY-MM
    summary TEXT NOT NULL,
    model   TEXT NOT NULL,
    made_at TEXT NOT NULL
);
"""

PROMPT = ("Below are the most reported AI news headlines of {month}, each with its date, its section and how many "
          "outlets carried it. Write what happened in AI that month in 4 or 5 plain sentences (about 110 words) for a "
          "general reader. Lead with the biggest stories and name the companies, models, laws and places involved. Use "
          "only facts stated in the headlines: no numbers, names or claims that are not in them, and keep their "
          "\"will\", \"plans to\", \"reportedly\" (a deal that will happen has not happened yet). Group related "
          "stories. No hype words, opinions, lists or headings.\n\n{lines}")


def connect(conn) -> None:
    conn.executescript(SCHEMA)


# ---------- Months ----------

def months(today: date) -> list[str]:
    """Every month with an issue, oldest first: FIRST to the last month that is over."""
    out, y, m = [], *map(int, FIRST.split("-"))
    while (y, m) < (today.year, today.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def name(month: str) -> str:
    return date.fromisoformat(month + "-01").strftime("%B %Y")


def number(month: str) -> int:
    """The issue's number: January 2026 is No. 1."""
    y, m = map(int, month.split("-"))
    fy, fm = map(int, FIRST.split("-"))
    return (y - fy) * 12 + m - fm + 1


def _last_day(month: str) -> date:
    d = date.fromisoformat(month + "-28") + timedelta(days=4)
    return d - timedelta(days=d.day)


# ---------- What the issue holds ----------

def outlets(c: dict) -> int:
    return 1 + len({a["source"] for a in c.get("also") or []} - {c["source"]})


def _names(cards: list[dict]) -> Counter:
    """How many of these cards' headlines carry each name (a capitalised word never written in lower case)."""
    words = [set(re.findall(r"[A-Za-z][\w.+-]*\w", c.get("title") or "")) for c in cards]
    lower = {w for ws in words for w in ws if w[0].islower()}
    return Counter(w for ws in words for w in ws if w[0].isupper() and len(w) > 2 and w.lower() not in lower)


def ranked(cards: list[dict]) -> list[dict]:
    """Most outlets first; on a tie, the story whose names the month's other headlines carry most, then the oldest."""
    seen = _names(cards)
    def buzz(c):
        return max((seen[w] for w in re.findall(r"[A-Z][\w.+-]*\w", c.get("title") or "") if seen[w] < 30), default=0)
    return sorted(cards, key=lambda c: (-outlets(c), -buzz(c), c.get("date") or ""))


def _story(c: dict) -> dict:
    return {"date": c["date"][:10], "title": c["title"].strip(), "url": c["url"], "source": c["source"],
            "outlets": outlets(c), "stream": c["category"]}


def _stages(cards: list[dict], month: str) -> list[dict]:
    """The tracker's bills that passed a stage past "introduced" this month, as timeline events: each bill once, at the
    furthest stage it reached that month. `cards` are all the tracker's, as a bill's card is dated its latest stage."""
    out = []
    for c in cards:
        life = c.get("lifecycle")
        if not life:
            continue
        bill = c["title"].split(": ", 1)[-1]
        for s in [s for s in life["steps"] if (s.get("date") or "").startswith(month) and s["stage"] != "introduced"][-1:]:
            out.append({"date": s["date"][:10], "title": f"{bill}: {s['label']}", "url": life["url"],
                        "source": life["source"], "outlets": 1, "stream": "regulation", "official": True,
                        "flag": countries.flag(c["bill"].split("-")[0]), "law": bill, "stage": s["stage"],
                        "label": s["label"]})
    return sorted(out, key=lambda e: e["date"])


def rules(laws: list[dict], month: str) -> list[dict]:
    """Rules that moved: the laws that passed a stage this month (furthest along first) and the standards published
    this month, each with its badge (BADGES). Official titles as the source gives them."""
    order = list(BADGES)
    out = [{"date": e["date"], "title": e["law"], "url": e["url"], "source": e["source"], "flag": e["flag"],
            "badge": e["stage"], "label": e["label"]} for e in _stages(laws, month)]
    out += [{"date": c["date"][:10], "title": c["title"].strip(), "url": c["url"], "source": c["source"],
             "flag": countries.flag("INTL"), "badge": "standard", "label": "Published"}
            for c in laws if (c.get("bill") or "").startswith(standards.MARK) and c["date"].startswith(month)]
    return sorted(out, key=lambda r: (order.index(r["badge"]), r["date"]))


def _weeks(month: str) -> list[tuple[date, date]]:
    """The month in weeks of 7 days from the 1st; the last one runs to the month's end."""
    start, end = date.fromisoformat(month + "-01"), _last_day(month)
    out = []
    while start <= end:
        stop = min(start + timedelta(days=6), end)
        if (end - stop).days < 3:  # a stub of 1-2 days joins the week before it
            stop = end
        out.append((start, stop))
        start = stop + timedelta(days=1)
    return out


def _day_range(a: date, b: date) -> str:
    return f"{a.day}–{b.day} {b.strftime('%b')}"


def word_counts(cards: list[dict]) -> Counter:
    """How many of these stories use each glossary word (in the headline or the description)."""
    n = Counter()
    for c in cards:
        text = f"{c.get('title') or ''} {c.get('summary') or ''}"
        n.update(e["id"] for e in glossary.ENTRIES if glossary._PATTERNS[e["id"]].search(text))
    return n


def words(now: Counter, before: list[Counter], month: str) -> list[dict]:
    """The glossary's words of the month: those added to it that month (New), then those the month's stories used
    most compared with the three months before (`before`; at least 5 stories)."""
    out = []
    for e in glossary.ENTRIES:
        new = e["added"].startswith(month) and e["added"] > glossary.LAUNCH.isoformat()
        if new or now[e["id"]] >= 5:
            then = sum(b[e["id"]] for b in before) / max(len(before), 1)
            out.append({"id": e["id"], "term": e["term"], "def": e["def"], "n": now[e["id"]], "new": new,
                        "rise": now[e["id"]] / (then + 1)})
    out.sort(key=lambda w: (not w["new"], -w["rise"], -w["n"]))
    return out[:WORDS]


def issue(month: str, cards: list[dict], storylines: dict[str, list[dict]], laws: list[dict] | None = None) -> dict:
    """The issue's stories (issue.json): `cards` are the month's, `storylines` each topic's events, `laws` all the
    tracker's bills and standards (the month's cards when not given)."""
    news = [c for c in cards if c["category"] in STREAMS and c["category"] != "research"]
    top = ranked(news)
    laws = cards if laws is None else laws
    stages = _stages(laws, month)
    weeks = []
    for a, b in _weeks(month):
        inside = [c for c in top if a.isoformat() <= c["date"][:10] <= b.isoformat() and outlets(c) > 1]
        ev = [_story(c) for c in inside[:PER_WEEK]] + [s for s in stages if a.isoformat() <= s["date"] <= b.isoformat()]
        weeks.append({"days": _day_range(a, b), "events": sorted(ev, key=lambda e: e["date"])})
    streams = {}
    shown = {c["url"] for c in top[:TOP]}  # What mattered most's stories aren't repeated
    for cat in STREAMS:
        mine = [c for c in cards if c["category"] == cat and c["url"] not in shown]
        if cat == "research":  # one outlet each: the labs' own papers first, the names most in the month's news next
            seen = _names(news)
            mine.sort(key=lambda c: (c["source"] not in LAB_PAPERS,
                                     -max((seen[w] for w in re.findall(r"[A-Z][\w.+-]*\w", c["title"])), default=0)))
            picks = [_story(c) for c in mine[:PER_STREAM]]
        elif cat == "regulation":  # laws that passed a stage first
            picks = (stages[-PER_STREAM:][::-1] + [_story(c) for c in ranked(mine) if not c.get("lifecycle")])[:PER_STREAM]
        else:
            picks = [_story(c) for c in ranked(mine)[:PER_STREAM]]
        if picks:
            streams[cat] = picks
    moved = []
    for slug, ev in storylines.items():
        this = [e for e in ev if e["date"].startswith(month)]
        if len(this) >= 2:  # one story isn't a storyline moving
            big = max(this, key=lambda e: (e["outlets"], e["date"]))
            moved.append({"slug": slug, "name": topics.TOPICS[slug]["name"], "href": "/" + topics.path(slug), "n": len(this),
                          "title": big["title"], "url": big["url"], "date": big["date"][:10]})
    moved.sort(key=lambda t: -t["n"])
    moved = moved[:STORYLINES]
    return {"month": month, "top": [_story(c) for c in top[:TOP]], "rules": rules(laws, month), "weeks": weeks,
            "streams": streams, "storylines": moved}


# ---------- The summary ----------

def headlines(cards: list[dict], n: int = HEADLINES) -> list[dict]:
    """What the summary reads: the month's `n` most reported news stories (2+ outlets first), no papers."""
    return ranked([c for c in cards if c["category"] in STREAMS and c["category"] != "research"])[:n]


def prompt(month: str, cards: list[dict], n: int = HEADLINES) -> str:
    lines = "\n".join(f"- {c['date'][:10]} [{STREAMS[c['category']]}] ({outlets(c)} outlets) {c['title'].strip()}"
                      for c in headlines(cards, n))
    return PROMPT.format(month=name(month), lines=lines)


_CAPS = re.compile(r"(?<![\w.])([A-Z][\w'’.+-]*\w|[A-Z])")
_NUM = re.compile(r"\d[\d.,]*\d|\d")


# words a sentence may start with that are no name ("Meanwhile, ..."); a word the headlines write in lower case too
STARTERS = set("""the a an in on at as by for from with while after before during also meanwhile elsewhere separately
finally overall several other others many some most more both each another this that these those it its they their
there however although though despite amid among across beyond later earlier then still yet such new major big
tech governments companies researchers regulators lawmakers officials one two three""".split())


def unsupported(text: str, source: str) -> list[str]:
    """The names and numbers in the summary that its headlines (`source`) don't have."""
    hay = source.lower().replace(".", "")
    bad = []
    for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text.strip()):
        for i, m in enumerate(_CAPS.finditer(sentence)):
            w = m.group(1).rstrip("'’s").rstrip("'’")
            first = m.start() == 0 and i == 0
            if re.fullmatch(r".+-[a-z]+", w):  # "Trump-led", "Google-backed": the name is the part before
                w = w.rsplit("-", 1)[0]
            stem = w.lower()[:max(4, len(w) - 1)]  # a place by its adjective: "Italy" for "Italian", "China" for "Chinese"
            if w in ("AI", "I") or w.lower().replace(".", "") in hay or re.search(rf"\b{re.escape(stem)}[a-z]*(?:n|ese|ish)\b", hay) or (first and (
                    w.lower() in STARTERS or re.search(rf"\b{re.escape(w.lower())}\b", source))):
                continue
            bad.append(w)
        bad += [n for n in _NUM.findall(sentence) if not re.search(rf"(?<![\d.,]){re.escape(n)}(?![\d])", source)]
    return bad


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "")).strip()


def _download() -> Path | None:
    path = MODEL_DIR / FILE
    if path.exists():
        return path
    if os.environ.get("AIPULSE_OFFLINE"):  # tests: never download
        return None
    url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{FILE}"
    if not feeds.allowed(url):
        return None
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".part")
    req = urllib.request.Request(url, headers={"User-Agent": feeds.USER_AGENT})
    with urllib.request.urlopen(req, timeout=120, context=feeds.TLS) as resp, open(part, "wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
    part.replace(path)
    return path


_llm: dict = {}


def _model():
    if "m" not in _llm:
        _llm["m"] = None
        try:
            from llama_cpp import Llama
        except ImportError:
            return None
        path = _download()
        if path:
            _llm["m"] = Llama(model_path=str(path), n_ctx=8192, verbose=False)  # threads: one per physical core
    return _llm["m"]


def write(month: str, cards: list[dict], generate=None, log=print) -> str | None:
    """The month's summary, checked against its headlines; None when the model is missing or every try failed.
    `generate(prompt, seed)` returns the model's text (tests pass their own)."""
    if generate is None:
        llm = _model()
        if llm is None:
            return None
        def generate(p, seed):
            out = llm.create_chat_completion(messages=[{"role": "user", "content": p}], temperature=0.2,
                                             max_tokens=260, seed=seed)
            return out["choices"][0]["message"]["content"]
    told: list[str] = []  # each try after the first is told what was wrong with the ones before
    for seed in range(1, TRIES + 1):
        n = FEWER.get(seed, HEADLINES)
        source = " ".join([name(month)] + [c["title"] for c in headlines(cards, n)])  # what the summary may say
        text = clean(generate(prompt(month, cards, n) + "".join(told), seed))
        bad = list(dict.fromkeys(unsupported(text, source)))
        if not bad and 300 <= len(text) <= MAX_CHARS and len(re.findall(r"[.!?](?:\s|$)", text)) <= 6:
            return text
        log(f"  {month}: try {seed} left out ({', '.join(bad[:6]) or 'length'})")
        told.append(f"\n\nDo not mention {', '.join(bad)}: the headlines don't." if bad else
                    "\n\nKeep it shorter: at most 5 sentences and 120 words.")
    return None


def due(conn, today: date) -> list[str]:
    """Months without a summary yet, newest first."""
    have = {r[0] for r in conn.execute("SELECT month FROM monthly")}
    return [m for m in reversed(months(today)) if m not in have]


def summarise(conn, today: date, limit: int = 4, only: str | None = None, log=print) -> int:
    """Write the summaries still due (newest month first, at most `limit` a run; `only`: just that month). Returns
    how many were written."""
    done = 0
    for month in [m for m in due(conn, today) if only in (None, m)][:limit]:
        cards = month_cards(conn, month)
        if not cards:
            continue
        text = write(month, cards, log=log)
        if text is None and _model() is None:
            log("monthly: no summary model (pip install llama-cpp-python); skipped")
            return done
        # every try failed the check: kept empty (the issue has no summary), so later runs don't try again; it is
        # written again only by hand (python -m aipulse monthly --month YYYY-MM)
        conn.execute("INSERT OR REPLACE INTO monthly VALUES (?, ?, ?, ?)",
                     (month, text or "", MODEL, datetime.now(timezone.utc).isoformat(timespec="seconds")))
        conn.commit()
        done += bool(text)
        log(f"monthly: {name(month)} " + ("summarised" if text else "left without a summary"))
    return done


def month_cards(conn, month: str) -> list[dict]:
    from . import store
    ids = [r[0] for r in conn.execute(
        "SELECT id FROM items WHERE date >= ? AND date < ? AND (cluster = '' OR cluster = id)",
        (month + "-01", (_last_day(month) + timedelta(days=1)).isoformat()))]
    return store.cards_by_id(conn, ids)


# ---------- The pages ----------

ISSUE_JS = r"""<script>
(() => {
  const BADGES = __BADGES__;
  const root = document.getElementById("issue");
  const NAMES = {tool: "Releases", news: "Industry", research: "Research", regulation: "Regulation", policy: "Policy", infra: "Infra"};
  const COL = {tool: "tool", news: "news", research: "research", regulation: "reg", policy: "policy", infra: "infra"};
  const day = d => new Date(d + "T00:00:00Z").toLocaleDateString(undefined, {day: "numeric", month: "short", timeZone: "UTC"});
  const el = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const link = e => { const a = el("a", null, e.title); a.href = e.url; a.rel = "noopener"; return a; };
  const meta = e => el("div", "meta", e.source + (e.outlets > 1 ? " · " + e.outlets + " outlets" : ""));
  const pill = s => { const p = el("span", "st", NAMES[s]); p.style.setProperty("--st", "var(--f-" + COL[s] + ")"); return p; };
  const row = cells => { const tr = el("tr"); cells.forEach(c => { const td = el("td"); if(c != null) td.append(...[].concat(c)); tr.append(td); }); return tr; };
  fetch(root.dataset.src, {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(d => {
    const sq = s => { const q = el("i", "sq"); q.style.setProperty("--st", "var(--f-" + COL[s] + ")"); return q; };
    document.getElementById("top-key").replaceChildren(...[...new Set(d.top.map(e => e.stream))].map(s => {
      const k = el("span"); k.append(sq(s), NAMES[s]); return k; }));
    document.getElementById("top-rows").replaceChildren(...d.top.map((e, i) => {
      const li = el("li"), body = el("div"), cnt = el("span", "cnt");
      cnt.style.setProperty("--st", "var(--f-" + COL[e.stream] + ")");
      cnt.title = NAMES[e.stream] + ": " + e.outlets + (e.outlets > 1 ? " outlets" : " outlet");
      cnt.append(el("b", null, String(e.outlets)), el("small", null, e.outlets > 1 ? "outlets" : "outlet"));
      body.append(link(e), el("div", "meta", NAMES[e.stream] + " · " + e.source + " · " + day(e.date)));
      li.append(el("b", "r", String(i + 1)), body, cnt);
      return li;
    }));
    const rr = document.getElementById("rule-groups"), by = {};
    d.rules.forEach(r => (by[r.badge] = by[r.badge] || []).push(r));
    if(rr) rr.replaceChildren(...Object.entries(by).map(([b, list]) => {
      const g = el("div", "grp"), head = el("div"), chips = el("div", "chips");
      head.append(el("span", "badge b-" + b, BADGES[b]), el("span", "n", String(list.length)));
      list.forEach(r => {
        const ch = el("span", "chip"), f = el("img", "flag"), txt = el("span");
        f.src = "flags/" + r.flag; f.alt = "";
        txt.append(link(r), el("span", "meta", r.label + " · " + day(r.date) + " · " + r.source));
        ch.append(f, txt); chips.append(ch);
      });
      g.append(head, chips); return g;
    }));
    const tl = document.getElementById("timeline"); tl.replaceChildren(); tl.style.setProperty("--weeks", d.weeks.length);
    let n = 0;
    d.weeks.forEach((w, i) => {
      const ch = el("section", "chapter wk"), yr = el("div", "yr"), ol = el("ol", "timeline");
      yr.append(el("span", "", "Week " + (i + 1)), el("small", null, w.days));
      if(!w.events.length) ol.append(el("li", "quiet", "A quiet week: no story two outlets carried."));
      w.events.forEach(e => {
        const li = el("li", "ev " + (n++ % 2 ? "right" : "left") + (e.official ? " official" : " news") + (e.outlets > 1 ? " wide" : ""));
        const box = el("div", "box"), top = el("div", "top"), txt = el("div", "txt");
        top.append(el("span", "when", day(e.date)), el("span", "lane", e.official ? "Official record" : NAMES[e.stream]));
        if(e.flag) { const f = el("img", "flag"); f.src = "flags/" + e.flag; f.alt = ""; top.append(f); }
        txt.append(top, link(e), meta(e)); box.append(txt); li.append(el("span", "dot"), box); ol.append(li);
      });
      ch.append(yr, ol); tl.append(ch);
    });
    document.getElementById("stream-rows").replaceChildren(...Object.entries(d.streams).map(([s, list]) => {
      const card = el("section", "scard"), ol = el("ol");
      card.style.setProperty("--st", "var(--f-" + COL[s] + ")");
      list.forEach(e => { const li = el("li"); li.append(link(e), el("div", "meta", e.source
        + (e.outlets > 1 ? " · " + e.outlets + " outlets" : "") + " · " + day(e.date))); ol.append(li); });
      card.append(el("h3", null, NAMES[s]), ol); return card;
    }));
    if(d.storylines.length) {
      document.getElementById("story-rows").replaceChildren(...d.storylines.map(t => {
        const a = el("a", "name", t.name); a.href = t.href;
        return row([a, [link(t), el("div", "meta", day(t.date))], el("b", "n", String(t.n))]);
      }));
    } else document.getElementById("storylines").remove(), document.querySelector('a[href$="#storylines"]')?.parentElement.remove();
  }).catch(() => root.querySelectorAll("tbody, #timeline, #top-rows, #rule-groups, #stream-rows").forEach(t => t.replaceChildren(el("p", "meta", "Couldn't load the stories. Try reloading the page."))));
})();
</script>""".replace("__BADGES__", json.dumps(BADGES))



def marked(summary: str, cards: list[dict]) -> str:
    """The summary as HTML with its names marked: each run of capitalised words holding a name the month's headlines
    use (a company, a model, a place) or a number (GPT-5.6), from its first name to its last."""
    names = _names(headlines(cards))
    def is_name(w):
        w = re.sub(r"[’']s$", "", w)
        return not w.startswith("AI-") and (w in names or bool(re.search(r"\d", w)))
    out, last = [], 0
    for m in re.finditer(r"[A-Z][\w.+’'-]*\w(?: [A-Z0-9][\w.+’'-]*\w| [0-9])*", summary):
        ws = m.group(0).split(" ")
        hits = [k for k, w in enumerate(ws) if is_name(w)]
        if not hits:
            continue
        while hits[-1] + 1 < len(ws) and ws[hits[-1] + 1] == "AI":  # Moonshot AI, Mistral AI
            hits.append(hits[-1] + 1)
        start = m.start() + sum(len(w) + 1 for w in ws[:hits[0]])
        end = start + len(" ".join(ws[hits[0]:hits[-1] + 1]))
        out += [escape(summary[last:start]), f"<mark>{escape(summary[start:end])}</mark>"]
        last = end
    return "".join(out) + escape(summary[last:])


def first_sentence(text: str) -> str:
    """A glossary meaning's first sentence ("e.g." and "i.e." don't end one)."""
    return re.split(r"(?<!e\.g)(?<!i\.e)\.\s+(?=[A-Z])", text, maxsplit=1)[0].rstrip(".") + "."


def lede(summary: str) -> str:
    """A summary's first sentence ("U.S." doesn't end one)."""
    return re.split(r"(?<=[a-z0-9)’'][.!?])\s+(?=[A-Z])", summary, maxsplit=1)[0]


def path(month: str) -> str:
    return f"monthly/{month}/"


def _cover(storylines: list[dict], used: set[str]) -> list | None:
    """The issue's cover: our own cartoon of the storyline that moved most that month (topics.py; no real people,
    no logos), one no other issue has where it can."""
    slugs = [t["slug"] for t in storylines]
    pick = next((sl for sl in slugs if sl not in used), slugs[0] if slugs else None)
    if pick is None:
        return None
    used.add(pick)
    return [f"cartoons/{pick}.svg", ""]


def _img(photo: list | None) -> str:
    return f'<img class="photo" src="photos/{escape(photo[0])}" alt="" loading="lazy">' if photo else ""


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write monthly/ (the shelf of issues), each issue's page and issue.json, and monthly/front.json (the front
    page's strip). Returns the pages' paths."""
    connect(conn)
    parts = pages.frame(conn, len(cards))
    summaries = {r[0]: r[1] for r in conn.execute("SELECT month, summary FROM monthly")}
    by_month: dict[str, list[dict]] = {}
    for c in cards:
        by_month.setdefault((c.get("date") or "")[:7], []).append(c)
    storylines = {slug: topics.events(slug, cards) for slug in topics.TOPICS}
    laws = [c for c in cards if c.get("lifecycle") or (c.get("bill") or "").startswith(standards.MARK)]
    issues = [m for m in months(today) if by_month.get(m)]
    counts = {m: word_counts(by_month[m]) for m in issues}
    (out / "monthly").mkdir(parents=True, exist_ok=True)
    used: set[str] = set()
    shelf, paths = [], []
    for i, m in enumerate(issues):
        mine = by_month[m]
        data = issue(m, mine, storylines, laws)
        p = path(m)
        (out / p).mkdir(parents=True, exist_ok=True)
        for f in {r["flag"] for r in data["rules"]}:  # the rules' flags (the timeline's are among them)
            (out / "flags").mkdir(exist_ok=True)
            shutil.copy(countries.FLAGS / f, out / "flags" / f)
        (out / p / "issue.json").write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        ws = words(counts[m], [counts[mm] for mm in months(date.fromisoformat(m + "-01"))[-3:] if mm in counts], m)
        photo = _cover(data["storylines"], used)
        summary = summaries.get(m)
        sections = ([("brief", "The month in brief")] if summary else []) + [
            ("top", "What mattered most")] + ([("rules", "Rules that moved")] if data["rules"] else []) + [
            ("weeks", "Week by week"), ("streams", "Stream by stream")] + (
            [("words", "Words of the month")] if ws else []) + [("storylines", "Storylines that moved")]
        word_rows = "".join(
            f'<a class="blk" href="/glossary/{w["id"]}/"><b>{escape(w["term"])}'
            + ('<span class="new">New</span>' if w["new"] else "")
            + f'</b><span class="def">{escape(first_sentence(w["def"]))}</span>'
            + f'<span class="n">{w["n"]} {"story" if w["n"] == 1 else "stories"}</span></a>' for w in ws)
        prev = f'<a href="/{path(issues[i - 1])}">← {name(issues[i - 1])}</a>' if i else "<span></span>"
        nxt = f'<a href="/{path(issues[i + 1])}">{name(issues[i + 1])} →</a>' if i + 1 < len(issues) else "<span></span>"
        body = (f'<div class="mi" id="issue" data-src="/{p}issue.json">\n'
                f'<div class="topic-hero">{_img(photo)}<div class="over"><span class="kind">AI Pulse · The month in AI</span>'
                f'<span class="num">No. {number(m)}</span><h1>{name(m)}</h1></div></div>\n'
                '<ol class="contents">' + "".join(f'<li><a href="/{p}#{k}">{t}</a></li>' for k, t in sections) + "</ol>\n"
                + (f'<section class="sheet" id="brief"><h2>The month in brief</h2><p class="brief">{marked(summary, mine)}</p></section>\n'
                   if summary else "")
                + '<section class="sheet" id="top"><h2>What mattered most</h2><p class="key" id="top-key"></p>'
                  '<ol class="ranked" id="top-rows"><li class="meta">Loading…</li></ol></section>\n'
                + ('<section class="sheet" id="rules"><h2>Rules that moved</h2><div class="groups" id="rule-groups">'
                   '<p class="meta">Loading…</p></div></section>\n' if data["rules"] else "")
                + '<section class="sheet" id="weeks"><h2>Week by week</h2>'
                '<p class="legend"><span class="lg official">A law passed a stage</span><span class="lg news">In the news</span></p>'
                '<div class="chapters" id="timeline"><p class="meta">Loading…</p></div></section>\n'
                '<section class="sheet" id="streams"><h2>Stream by stream</h2><div class="sgrid" id="stream-rows">'
                '<p class="meta">Loading…</p></div></section>\n'
                + (f'<section class="sheet" id="words"><h2>Words of the month</h2><div class="blocks">{word_rows}</div></section>\n'
                   if ws else "")
                + '<section class="sheet" id="storylines"><h2>Storylines that moved</h2><table class="mt"><thead><tr>'
                  '<th>Storyline</th><th>Its biggest story this month</th><th>Stories</th></tr></thead>'
                  '<tbody id="story-rows"></tbody></table></section>\n'
                f'<nav class="issue-nav">{prev}<a href="/monthly/">All issues</a>{nxt}</nav>\n'
                f'</div>\n{ISSUE_JS}')
        what = (summary or f"What happened in AI in {name(m)}: the biggest stories, week by week, and the words to know.")
        ld = {"@context": "https://schema.org", "@type": "PublicationIssue", "issueNumber": number(m),
              "name": f"The month in AI: {name(m)}", "description": what, "url": f"{rss.SITE}{p}",
              "datePublished": (_last_day(m) + timedelta(days=1)).isoformat()}
        (out / p / "index.html").write_text(
            pages.page(f"{name(m)} · The month in AI · AI Pulse", what[:300], p, body, ld, parts,
                       ("/monthly/", "All monthly issues")), encoding="utf-8")
        paths.append(p)
        shelf.append({"month": m, "photo": photo, "summary": summary})
    # the shelf: newest first, a row of covers a year
    years: dict[str, list[str]] = {}
    for s in reversed(shelf):
        years.setdefault(s["month"][:4], []).append(
            f'<a href="/{path(s["month"])}"><span class="pic">{_img(s["photo"])}</span><span class="txt">'
            f'<span class="num">No. {number(s["month"])}</span><b>{date.fromisoformat(s["month"] + "-01").strftime("%B")}</b>'
            f'<span class="meta">{s["month"][:4]}</span></span></a>')
    what = ("A booklet for every month since January 2026: what happened in brief, the stories that mattered most, "
            "week by week, and the words to know.")
    body = (f'<h1>The month in AI</h1>\n<p class="intro">{escape(what)}</p>\n'
            + "".join(f'<h2>{y}</h2>\n<div class="shelf">{"".join(c)}</div>\n' for y, c in years.items()))
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "The month in AI", "description": what,
          "url": f"{rss.SITE}monthly/"}
    (out / "monthly" / "index.html").write_text(
        pages.page("The month in AI · AI Pulse", what, "monthly/", body, ld, parts, ("/", "Back to AI Pulse")),
        encoding="utf-8")
    # the front page's monthly bar: the FRONT newest issues, each with its summary's first sentence (index.html, loadMonthly)
    (out / "monthly" / "front.json").write_text(json.dumps([
        {"href": f"/{path(s['month'])}", "name": name(s["month"]), "number": number(s["month"]), "photo": s["photo"],
         "lede": lede(s["summary"] or "")} for s in reversed(shelf[-FRONT:])],
        separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return ["monthly/", *paths]
