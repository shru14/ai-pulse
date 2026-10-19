"""A stream's stories split into pages, the stream's strip on the front page linking to them: Industry by kind of
story (industry/<kind>/: opinion and analysis, company blogs, studies, AI-incidents, tutorials and events),
Releases by company (releases/<company>/), Policy by who is speaking (policy/<who>/), Research by subject
(research/<subject>/) and Infra by its subjects (infra/<subject>/). The stories are the outlets' own headlines, so
each page loads them in the reader's browser from data.json (the last 3 months), as the glossary's word pages do;
the page itself holds only our own words and the rule that picks its stories. No date of its own. Company blogs
are grouped by company, a tile each with its logo, like the tracker's places with their flags; the other pages by
topic (Research's by company and scholar, Infra's by place). Each tile previews its newest story.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import brands, classify, digest, jurisdictions, pages, rss, sources
from .server import TEMPLATE

# kind (classify.news_kind): (address under industry/, heading, what's on the page)
KINDS = {
    "analysis": ("opinion", "AI opinion and analysis", "Columns, essays and analysis on AI: what's being said about it, "
                 "beyond the news."),
    "blog": ("company-blogs", "AI company blogs", "What AI companies post on their own blogs besides launches: "
             "partnerships, customer stories and how they work."),
    "study": ("studies", "AI studies and reports", "News of what surveys, studies and reports on AI found."),
    "incident": ("ai-incidents", "AI incidents", "When AI went wrong: news reports of harms and failures, each one "
                 "the AI Incident Database records."),
    "tutorial": ("tutorials", "AI tutorials", "How-to guides and walkthroughs for building and using AI."),
    "event": ("events", "AI events", "AI conferences, summits and meetups, and what happened at them."),
}

# Releases: a page per big AI lab (the most tagged in Releases, October 2026), its stories naming it in the
# headline or from one of its own blogs (company())
RELEASE_COMPANIES = ["Google", "OpenAI", "Anthropic", "Meta", "Microsoft", "Nvidia", "Amazon", "Apple", "xAI",
                     "Mistral", "Alibaba", "DeepSeek", "Hugging Face"]

# Policy, by who is speaking: governments are the sources marked government (sources.SOURCES), think tanks and
# civil society the other sources that publish only policy, and every other outlet is reporting.
SPEAKERS = {
    "governments": ("Governments", "AI policy from governments", "What governments, ministries and public bodies "
                    "publish on AI, on their own sites."),
    "think-tanks": ("Think tanks & civil society", "AI policy from think tanks and civil society",
                    "What research institutes, advocacy groups and policy newsletters publish on AI."),
    "news": ("News reports", "AI policy in the news", "News outlets' reports on what governments, courts and "
             "politicians do about AI."),
}

# Research, by subject, read from a paper's title (a paper can have several; one with none is on no page). The
# reader's browser matches them too, so they use only what Python and JavaScript read alike.
SUBJECTS = {
    "language-models": ("Language models", "New papers on language models: how they are built and trained, and how "
                        "they reason.",
                        r"\bLLMs?\b|\bSLMs?\b|(?<!vision[- ])(?<!visual[- ])\blanguage models?|\btransformers?\b|"
                        r"\battention\b|tokeni[sz]|chain[- ]of[- ]thought|\breasoning\b|post[- ]training|"
                        r"pre[- ]?training|instruction[- ]tun|\bRLHF\b|\bprompt"),
    "agents": ("Agents", "New papers on AI agents: tool use, computer use, multi-agent systems and the harnesses "
               "around them.", r"\bagents?\b|agentic|tool[- ](?:use|calling|learning)|computer[- ]use|\bGUI\b|harness"),
    "vision": ("Vision, image and video", "New papers on seeing and making pictures: images, video, 3D and "
               "vision-language models.",
               r"\bvision\b|visual|\bimages?\b|\bvideos?\b|\bVLMs?\b|\bMLLMs?\b|multimodal|\b3D\b|"
               r"\bdiffusion\b|segmentation|object detection|\bdepth\b|\bpixels?\b|\bcameras?\b"),
    "speech": ("Speech and audio", "New papers on speech, voice, music and sound.",
               r"\bspeech|\baudio|\bvoices?\b|\bASR\b|\bTTS\b|text-to-speech|\bmusic|\bspoken\b|acoustic"),
    "robotics": ("Robotics and world models", "New papers on robots, embodied AI, self-driving and the world models "
                 "they learn.", r"robot|humanoid|manipulation|embodied|\bVLAs?\b|vision-language-action|"
                 r"world[- ](?:action )?models?|locomotion|dexterous|autonomous driving|self-driving"),
    "safety": ("Safety and security", "New papers on making AI safe and secure: alignment, attacks, jailbreaks, "
               "privacy, hallucination and interpretability.",
               r"safety|\bsafer?\b|(?<!modal )(?<!document )alignment|red[- ]team|jailbreak|guardrail|unlearning|privacy|hallucinat|"
               r"adversarial|\battacks?\b|backdoor|poison|trustworth|interpretab|misuse|decepti|security"),
    "reinforcement-learning": ("Reinforcement learning", "New papers on learning by trial and reward: RL, reward "
                               "models, self-play and policies.",
                               r"reinforcement learning|\bRL\b|\brewards?\b|self-play|\bpolic(?:y|ies)\b"),
    "efficiency": ("Efficiency and training", "New papers on training and running AI for less: compression, "
                   "fine-tuning, mixture of experts and scaling laws.",
                   r"quantiz|pruning|distill|efficien|speculative decoding|mixture[- ]of[- ]experts|\bMoE\b|"
                   r"scaling laws?|fine[- ]tun|\bLoRA\b|compress|\bsparse|sparsity|kv[- ]cache|\bGPUs?\b|"
                   r"throughput|latency|optimi[sz]er"),
    "science": ("Science and medicine", "New papers on AI for science and health: biology, chemistry, physics, "
                "maths and medicine.", r"protein|molecul|medical|medicine|clinical|\bhealth|patients?\b|chemi|"
                r"\bmaterials?\b|biolog|genom|physics|weather|climate|\bdrugs?\b|\bcells?\b|\bPDEs?\b|"
                r"scientific|mathemati|theorem"),
    "benchmarks": ("Benchmarks and evaluation", "New papers that test AI: benchmarks, leaderboards and how to "
                   "evaluate models.", r"bench(?:mark)?(?:s|ing)?\b|evaluat|leaderboard|\barena\b"),
}

# Infra, by its subjects (classify.INFRA_TOPICS), each with the general tags it replaces (classify.INFRA_SAYS)
INFRA = {
    "power-and-grid": ("Power & grid", "AI's demand for electricity: grids, power plants, nuclear and gas, and the "
                       "deals that supply data centres."),
    "water": ("Water", "How much water AI's data centres use to keep cool, and where it comes from."),
    "emissions-and-climate": ("Emissions & climate", "The carbon and climate cost of AI's data centres, and the "
                              "clean power meant to cut it."),
    "land-and-local-pushback": ("Land & local pushback", "Where data centres meet their neighbours: local "
                                "opposition, zoning, farmland and moratoriums."),
    "builds-and-deals": ("Builds & deals", "New data centres and campuses: what is being built, where, how big and "
                         "who is paying."),
    "rules-and-permits": ("Rules & permits", "Permits, planning, tax breaks and the rules governments set for data "
                          "centres."),
    "hardware-and-compute": ("Hardware & compute", "The machines inside: supercomputers, GPU clusters, chips, "
                             "servers and cooling."),
}

STORIES_JS = r"""<script>
(() => {
  const ul = document.getElementById("kind-stories"), more = document.getElementById("more-stories");
  const tiles = document.getElementById("cats"), json = id => JSON.parse(document.getElementById(id).textContent);
  const firms = document.getElementById("firms") ? json("firms") : null, rule = json("rule");
  // the page's stories (stream_pages()): its stream's, and of its kind, listed, with its title's subject, from
  // its sources or with its tags, or from none of the sources listed
  const title = rule.title && new RegExp(rule.title, "i"), ids = new Set(rule.ids);
  const has = c => c.category === rule.category && (rule.kind ? c.kind === rule.kind : rule.ids ? ids.has(c.id)
    : title ? title.test(c.title)
    : rule.notSources ? !rule.notSources.includes(c.source)
    : (rule.sources || []).includes(c.source) || (rule.tags || []).some(t => c.tags.includes(t)));
  const firm = src => (firms && firms.of[src]) || src;
  let all = [], groups = c => [];
  const day = d => new Date(d.slice(0, 10) + "T00:00:00Z").toLocaleDateString(undefined, {day: "numeric", month: "short", year: "numeric", timeZone: "UTC"});
  const note = text => { const li = document.createElement("li"); li.className = "meta"; li.textContent = text; ul.replaceChildren(li); };
  let list = [], shown = 0;
  // A tile per category (company blogs: per company, with its logo; the rest: per topic), each previewing its
  // newest story; a tile shows only its category's stories, and clicked again, all of them again
  const pick = name => {
    list = name ? all.filter(c => groups(c).includes(name)) : all;
    tiles.querySelectorAll("button").forEach(b => b.setAttribute("aria-pressed", b.dataset.cat === name));
    ul.replaceChildren(); shown = 0; show();
  };
  const buildTiles = () => {
    if(firms) groups = c => [firm(c.source)];
    else {
      // topics (or the page's other tile names) with 3+ stories, the most-told first (at most 11); a story in
      // none of them is under Other
      const topics = new Set(JSON.parse(document.getElementById("topics").textContent)), n = {};
      all.forEach(c => c.tags.filter(t => topics.has(t)).forEach(t => n[t] = (n[t] || 0) + 1));
      const top = new Set(Object.keys(n).filter(t => n[t] >= 3).sort((a, b) => n[b] - n[a] || a.localeCompare(b)).slice(0, 11));
      groups = c => { const g = c.tags.filter(t => top.has(t)); return g.length ? g : ["Other"]; };
    }
    const count = {}, newest = {};
    all.forEach(c => groups(c).forEach(g => { count[g] = (count[g] || 0) + 1; newest[g] = newest[g] || c; }));
    const tile = (name, n, c) => {
      const b = document.createElement("button"), head = document.createElement("span"), label = document.createElement("span");
      b.type = "button"; b.dataset.cat = name; head.className = "head";
      if(firms) {
        const mark = document.createElement("span");
        mark.className = "logo"; mark.setAttribute("aria-hidden", "true");
        if(firms.logo[name]) mark.innerHTML = firms.logo[name];  // fixed markup from our build, never story text
        else mark.textContent = name[0];
        head.append(mark);
      }
      label.textContent = name;
      const num = document.createElement("small"), peek = document.createElement("span");
      num.textContent = n; peek.className = "peek"; peek.textContent = c.title.trim();
      head.append(label, num); b.append(head, peek); b.addEventListener("click", () => pick(b.getAttribute("aria-pressed") === "true" ? "" : name));
      return b;
    };
    const names = Object.keys(count).filter(g => g !== "Other").sort((a, b) => count[b] - count[a] || a.localeCompare(b));
    if(count.Other) names.push("Other");
    tiles.replaceChildren(...names.map(g => tile(g, count[g], newest[g])));
  };
  const show = () => {
    list.slice(shown, shown += 20).forEach(c => {
      const li = document.createElement("li"), a = document.createElement("a"), meta = document.createElement("div");
      a.href = c.url; a.rel = "noopener"; a.textContent = c.title.trim();
      meta.className = "meta"; meta.textContent = [day(c.date), c.source].filter(Boolean).join(" · ");
      li.append(a, meta); ul.append(li);
    });
    more.hidden = shown >= list.length;
  };
  fetch("/data.json", {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(d => {
    list = all = d.cards.filter(has)
      .sort((a, b) => a.date < b.date ? 1 : a.date > b.date ? -1 : 0);
    document.getElementById("stories-count").textContent = list.length + " " + (list.length === 1 ? ul.dataset.noun : ul.dataset.nouns);
    if(!list.length) return note("None in the last 3 months.");
    buildTiles(); pick("");
  }).catch(() => note("Couldn't load the stories. Try reloading the page."));
  more.addEventListener("click", show);
})();
</script>"""


_SUFFIX = re.compile(r"\s+(?:Blog|News|Newsroom)\b.*$")


def company(source: str) -> str:
    """The company behind a blog: one of the companies we tag ("Google Research Blog", "Engineering at Meta"),
    else the source's name without "Blog" or "News" ("Cloudflare Blog" -> Cloudflare)."""
    for name, rx in classify._companies.items():
        if rx.search(source):
            return name
    return _SUFFIX.sub("", source)


def _front_logos() -> dict[str, str]:
    """The front page's colour logos for the big AI companies (its LOGOS table)."""
    m = re.search(r"const LOGOS = (\{.*?\n\});", TEMPLATE.read_text(encoding="utf-8"), re.S)
    return json.loads(re.sub(r",\s*\}$", "}", m.group(1))) if m else {}


def _dark(hex_: str) -> str:
    """Logo tiles are white, so very light brand colours use the text colour instead (as on the front page)."""
    r, g, b = (int(hex_[i:i + 2], 16) for i in (0, 2, 4))
    return hex_ if (.299 * r + .587 * g + .114 * b) / 255 <= .8 else "141925"


def logos(names) -> dict[str, str]:
    """An SVG logo per company: the front page's, else Simple Icons' in its brand colour. None: its initial."""
    front, si, out = {k.lower(): v for k, v in _front_logos().items()}, brands.si_index(), {}
    for name in names:
        if name.lower() in front:
            out[name] = front[name.lower()]
            continue
        brand = si.get(name)
        d = brand and brands.si_path(brand["slug"])
        if d:
            out[name] = f'<svg viewBox="0 0 24 24"><path fill="#{_dark(brand["hex"])}" d="{escape(d)}"/></svg>'
    return out


# Each stream with pages: (its address, its name)
STREAMS = {"news": ("industry", "Industry"), "tool": ("releases", "Releases"), "policy": ("policy", "Policy"),
           "research": ("research", "Research"), "infra": ("infra", "Infra")}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def stream_pages(cards: list[dict] = ()) -> list[tuple[str, str, str, str, str, dict]]:
    """Every page: (stream, address, its button's words, heading, what's on it, the rule that picks its stories).
    Releases' rules list their stories of the last 3 months (data.json's): the company named in the headline (a
    summary's passing mention isn't its release) or from one of its own blogs."""
    out = [("news", f"industry/{a}/", digest.KIND[k][0], h, w, {"kind": k}) for k, (a, h, w) in KINDS.items()]
    since = (date.today() - timedelta(days=92)).isoformat()
    ids: dict[str, list[str]] = {}
    for c in cards:
        if c["category"] == "tool" and c["date"] >= since:
            for n in {*classify.company_tags(c["title"]), company(c["source"])}:
                ids.setdefault(n, []).append(c["id"])
    out += [("tool", f"releases/{slug(n)}/", n, f"AI releases from {n}",
             f"{n}'s new AI models and products, from its own blogs and the news.",
             {"ids": ids.get(n, [])}) for n in RELEASE_COMPANIES]
    gov = sorted(s["name"] for s in sources.SOURCES if s.get("government"))
    tanks = sorted(s["name"] for s in sources.SOURCES if s.get("category") == "policy" and not s.get("government"))
    rules = {"governments": {"sources": gov}, "think-tanks": {"sources": tanks}, "news": {"notSources": gov + tanks}}
    out += [("policy", f"policy/{a}/", label, h, w, rules[a]) for a, (label, h, w) in SPEAKERS.items()]
    out += [("research", f"research/{a}/", label, f"AI papers on {label.lower()}", w, {"title": rx})
            for a, (label, w, rx) in SUBJECTS.items()]
    out += [("infra", f"infra/{a}/", label, f"AI infra: {label.lower()}", w,
             {"tags": [label, *(k for k, v in classify.INFRA_SAYS.items() if v == label)]})
            for a, (label, w) in INFRA.items()]
    return [(cat, p, label, h, w, {"category": cat, **rule}) for cat, p, label, h, w, rule in out]


def paths() -> list[str]:
    return [p for _, p, *_ in stream_pages()]


def tile_names(cat: str) -> list[str]:
    """What a page's tiles group its stories by: Research's papers by company and scholar, Infra's stories by
    place, the rest by topic."""
    if cat == "research":
        return sorted(classify.paper_homes())
    if cat == "infra":
        return sorted({v[0] for v in jurisdictions.JURISDICTIONS.values()})
    return sorted(classify.TOPIC_TAGS)


# Each page's one-line question in its header band: by address, else by stream ({0} its name, {1} in lower case)
ASK = {
    "industry/opinion/": "What are people saying about AI?",
    "industry/company-blogs/": "What are AI companies posting on their blogs?",
    "industry/studies/": "What are studies of AI finding?",
    "industry/ai-incidents/": "Where has AI gone wrong?",
    "industry/tutorials/": "How do you build and use AI?",
    "industry/events/": "What happened at AI events?",
    "releases": "What has {0} released lately?",
    "policy/governments/": "What are governments saying about AI?",
    "policy/think-tanks/": "What are think tanks and civil society saying about AI?",
    "policy/news/": "What is the news reporting on AI policy?",
    "research": "What's new in AI research on {1}?",
    "infra/power-and-grid/": "Where will AI's electricity come from?",
    "infra/water/": "How much water does AI use?",
    "infra/emissions-and-climate/": "What does AI cost the climate?",
    "infra/land-and-local-pushback/": "Where are data centres meeting local resistance?",
    "infra/builds-and-deals/": "What data centres are being built?",
    "infra/rules-and-permits/": "What rules do data centres have to follow?",
    "infra/hardware-and-compute/": "What machines does AI run on?",
}


def _icon(p: str, label: str) -> str:
    """A page's icon in its header band: the one its tile on the front page's stream strip has (a company's logo for
    a Releases page), as a path or ready HTML (pages.band)."""
    m = re.search(rf'<a href="{re.escape(p)}"><span class="bc-ic[^"]*"(?: data-logo="[^"]*")?>(.*?)</span>',
                  TEMPLATE.read_text(encoding="utf-8"))
    if m and m.group(1):
        inner = m.group(1)
        d = re.fullmatch(r'<svg viewBox="0 0 24 24"><path d="([^"]+)"/></svg>', inner)
        return d.group(1) if d else inner
    return logos([label]).get(label) or f"<b>{escape(label[:1])}</b>"


def build(conn, cards: list[dict], out: Path) -> list[str]:
    """Write every stream's pages. Returns their paths."""
    parts = pages.frame(conn, len(cards))
    safe = lambda v: json.dumps(v).replace("</", "<\\/")
    of = {s: company(s) for s in sorted({c["source"] for c in cards if c.get("kind") == "blog"})}
    firms = safe({"of": of, "logo": logos(set(of.values()))})
    every = stream_pages(cards)
    paths = []
    for cat, p, label, heading, what, rule in every:
        home, name = STREAMS[cat]
        others = " · ".join(f'<a href="/{q}">{escape(label)}</a>' for c, q, label, *_ in every if c == cat)
        tiles = (f'<script type="application/json" id="firms">{firms}</script>\n' if rule.get("kind") == "blog" else
                 f'<script type="application/json" id="topics">{safe(tile_names(cat))}</script>\n')
        noun, nouns = ("paper", "papers") if cat == "research" else ("story", "stories")
        where = "the paper" if cat == "research" else "the outlet's own page"
        body = (f'<div class="kd">' + pages.band(cat, _icon(p, label), f"photos/cartoons/streams/{cat}.svg", heading,
                                                 ASK.get(p) or ASK[p.split("/")[0]].format(label, label.lower()), escape(what))
                + f'<p class="intro"><span id="stories-count">The {nouns}</span> in the last 3 months, newest first, '
                f'each linking to {escape(where)}.</p>\n'
                + '<div class="places companies" id="cats"></div>\n' + tiles
                + f'<script type="application/json" id="rule">{safe(rule)}</script>\n'
                f'<ul id="kind-stories" data-noun="{noun}" data-nouns="{nouns}"><li class="meta">Loading the {nouns}…</li></ul>\n'
                f'<button type="button" class="more-stories" id="more-stories" hidden>Show more {nouns}</button>\n'
                f'{STORIES_JS}</div>')
        data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": heading, "description": what,
                "url": f"{rss.SITE}{p}"}
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "index.html").write_text(pages.page(f"{heading} · AI Pulse", what, p, body, data, parts,
                                                       (f"/{home}/", f"Back to {name}"), f"More from {name}: {others}"),
                                            encoding="utf-8")
        paths.append(p)
    return paths
