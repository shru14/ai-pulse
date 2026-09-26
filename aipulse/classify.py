"""Decide whether an item is AI-related and which category it belongs in.

Keyword rules keep this free and offline. If ANTHROPIC_API_KEY is set, the
collector can optionally ask Claude for a better summary and category
(see enrich.py).
"""

from __future__ import annotations

import re
import unicodedata

from . import jurisdictions

AI_TERMS = [
    r"\bAI\b", r"artificial intelligence", r"machine learning", r"\bLLMs?\b", r"large language model",
    r"generative", r"chatbot", r"neural", r"deep learning", r"\bagents?\b", r"\bagentic\b",
    r"OpenAI", r"Anthropic", r"Claude", r"Gemini", r"ChatGPT", r"\bGPT-?\d", r"DeepMind", r"Mistral",
    r"DeepSeek", r"Qwen", r"Llama", r"Copilot", r"Hugging Face", r"Nvidia", r"diffusion model",
    r"foundation model", r"frontier model", r"superintelligence", r"\bAGI\b",
]

POLICY_TERMS = [
    r"regulat", r"legislat", r"\blaw\b", r"\blaws\b", r"\bbill\b", r"senate", r"congress", r"parliament",
    r"\bAI Act\b", r"European Commission", r"\bEU\b", r"executive order", r"white house", r"ministry",
    r"government", r"lawsuit", r"\bsue[sd]?\b", r"court", r"ruling", r"antitrust", r"\bFTC\b", r"\bDOJ\b",
    r"copyright", r"export control", r"sanction", r"privacy regulator", r"\bGDPR\b", r"data protection",
    r"\bban\b", r"\bbans\b", r"safety institute", r"\bAISI\b", r"summit", r"treaty", r"election",
    r"policy", r"governance", r"lawmakers", r"minister", r"president",
    # regulators, investigations and the executive branch
    r"investigat", r"\bprobes?\b", r"scrutin", r"regulators?\b", r"watchdog", r"\bgovernor\b", r"\bgov\.",
    r"\bMPs?\b", r"\bcabinet\b", r"attorneys? general", r"administration\b", r"\badmin\b",
]

TOOL_TERMS = [
    r"launch", r"releas", r"introduc", r"unveil", r"rolls? out", r"now available", r"generally available",
    r"open-?source", r"open-?weight", r"\bmodel\b", r"\bAPI\b", r"\bSDK\b", r"feature", r"update",
    r"\bbeta\b", r"preview", r"\bapp\b", r"plugin", r"version \d", r"\bv\d",
    # "Gemini can now call businesses", "lets Gemini phone businesses", "brings its LLMs to smart glasses"
    r"\bcan now\b", r"\blets\b", r"\bgives (every|users|you)\b", r"\bbrings\b", r"\badds?\b",
]

# Company blogs ("tool" feeds) also post partnerships and customer stories; those are industry news.
NEWS_SIGNALS = [r"\bpartner", r"\bprogramm?e\b", r"\bcustomers?\b", r"case study", r"\bskills\b",
                r"how \w+ uses", r"(widens|expands) access", r"\bdeal\b", r"\bIPO\b", r"\bfunding\b"]

_ai = re.compile("|".join(AI_TERMS), re.I)
_policy = [re.compile(p, re.I) for p in POLICY_TERMS]
_tool = [re.compile(p, re.I) for p in TOOL_TERMS]
_news = re.compile("|".join(NEWS_SIGNALS), re.I)


def is_ai_related(title: str, summary: str) -> bool:
    return bool(_ai.search(f"{title} {summary}"))


def categorize(title: str, summary: str, default: str = "news") -> str:
    """Title matches count double; policy wins ties because it's the rarer signal.

    Research sources are curated, so their items always stay under "research". Regulation sources
    start as "policy"; collect.apply_regulation decides whether an item is a trackable action.
    """
    if default == "research":
        return "research"
    if default == "regulation":
        default = "policy"
    def score(patterns):
        return sum(2 for p in patterns if p.search(title)) + sum(1 for p in patterns if p.search(summary))

    policy, tool = score(_policy), score(_tool)
    if policy >= 3 or (policy >= 2 and policy >= tool):
        return "policy"
    if default == "tool" and _news.search(title):
        return "news"
    if tool >= 3 and tool > policy:
        return "tool"
    if default == "policy" and policy == 0 and regulatory_action(title) is None and not jurisdictions.acting(title):
        return "news"  # a policy search picked up a story with nothing about government in it
    return default


COMPANY_TERMS = {
    "OpenAI": r"OpenAI|ChatGPT|\bGPT-?\d", "Anthropic": r"Anthropic|Claude", "Google": r"Google|Gemini|DeepMind",
    "Meta": r"\bMeta\b|Llama", "Microsoft": r"Microsoft|Copilot", "Nvidia": r"Nvidia", "Apple": r"\bApple\b",
    "Amazon": r"Amazon|AWS", "xAI": r"\bxAI\b|Grok", "Mistral": r"Mistral", "DeepSeek": r"DeepSeek",
    "Alibaba": r"Alibaba|Qwen",
}

TOPIC_TERMS = {
    # Tech & capabilities
    "Agents": r"\bagents?\b|agentic",
    "Open Models": r"open-?source|open-?weight",
    "Reasoning": r"reasoning|chain[- ]of[- ]thought",
    "Multimodal": r"multimodal|vision[- ]language",
    "Voice": r"\bvoice\b|speech|text-to-speech|\bTTS\b|\bASR\b",
    "Image & Video Generation": r"image generat|video generat|text-to-(image|video)|diffusion",
    "Coding Tools": r"coding|code assistant|copilot|\bIDE\b|developer tool",
    "Robotics": r"robot|humanoid|embodied",
    "Benchmarks": r"benchmark|leaderboard|\beval(uation)?s?\b",
    "Research": r"\bpaper\b|preprint|arXiv|researchers",
    "Training Data": r"training data|dataset|scrap(e|ing)",
    # Infrastructure
    "Chips": r"\bchips?\b|GPU|semiconductor|TSMC|\bTPU\b",
    "Compute & Data Centers": r"data cent(er|re)|compute|supercomputer|cluster",
    "Energy": r"energy|power grid|electricity|nuclear|gigawatt|\bGW\b",
    # Business
    "Funding": r"raises|funding|valuation|Series [A-F]",
    "M&A": r"acquir|acquisition|merger|buys\b",
    "IPO": r"\bIPO\b|going public|listing",
    "Jobs & Labor": r"\bjobs?\b|layoffs?|workforce|employment|labou?r",
    # Law & governance
    "Law": r"\blaws?\b|legislat|\bbill\b|lawsuit|\bsue[sd]?\b|court|ruling|judge",
    "Regulation": r"regulat|compliance|enforcement|regulator",
    "Governance": r"governance|oversight|standards?\b|treaty|summit|safety institute|\bAISI\b",
    "AI Act": r"\bAI Act\b",
    "Copyright": r"copyright|licens(e|ing) deal|fair use|pirat",
    "Privacy": r"privacy|\bGDPR\b|data protection|personal data",
    "Antitrust": r"antitrust|competition authority|monopol|\bFTC\b",
    "Export Controls": r"export control|sanction|entity list",
    "Defense": r"military|defen[cs]e|Pentagon|drone|national security",
    "Elections": r"election|misinformation|disinformation",
    "Deepfakes": r"deepfake|synthetic media|watermark",
    # Society & ideas
    "Ethics": r"ethic|bias|fairness|discriminat|accountab",
    "Philosophy": r"philosoph|conscious|sentien|moral status|\bAGI\b|superintelligence",
    "Safety": r"\bsafety\b|red[- ]team|guardrail",
    "Alignment": r"alignment|misalign",
    "Interpretability": r"interpretab|explainab",
    "Existential Risk": r"existential|extinction|doom",
    "Security": r"cyber|hack|vulnerab|exploit|breach|prompt injection",
    "Misuse": r"misuse|abuse|bioweapon|fraud|scam",
    "Surveillance": r"surveillance|facial recognition",
    "Education": r"educat|school|student|tutor",
    "Healthcare": r"health|medical|clinic|patient|drug",
    "Science": r"scientific|discover|protein|biology|physics|chemistry",
    "Climate": r"climate|emissions|carbon|sustainab",
}
TOPIC_TAGS = set(TOPIC_TERMS)
_companies = {k: re.compile(v, re.I) for k, v in COMPANY_TERMS.items()}
_topics = {k: re.compile(v, re.I) for k, v in TOPIC_TERMS.items()}


# Countries and blocs come from the regulation tracker's detector (aipulse/jurisdictions.py), so any of
# its ~60 places can be a tag, named in full ("Japan", "European Union").
PLACE_TAG_LIMIT = 2


def place_tags(title: str, summary: str = "") -> list[str]:
    return [jurisdictions.JURISDICTIONS[c][0] for c in jurisdictions.detect(title, summary)[:PLACE_TAG_LIMIT]]


def company_tags(title: str, summary: str = "") -> list[str]:
    text = f"{title} {summary}"
    return [k for k, p in _companies.items() if p.search(text)]


def tags_for(title: str, summary: str, limit: int = 5) -> list[str]:
    """Companies first, then places, then topics (see TOPIC_TERMS)."""
    text = f"{title} {summary}"
    topics = [k for k, p in _topics.items() if p.search(text)]
    return (company_tags(title, summary) + place_tags(title, summary) + topics)[:limit]


def name_key(name: str) -> tuple[str, ...] | None:
    """("fei", "fei", "li") for "Fei-Fei Li" and "Li Fei-Fei"; ignores accents, case, order and initials."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    parts = sorted(t for t in re.split(r"[^a-z]+", ascii_name) if len(t) > 1)
    return tuple(parts) if len(parts) >= 2 else None


# --- Regulation tracker: what kind of regulatory action a story reports ---
# Heads of government whose "orders" / "establishes" in a headline is an executive action.
EXECUTIVES = (r"governor|gov\.|president|premier|prime minister|newsom|pritzker|kotek|spanberger|hochul|"
              r"desantis|trump|starmer|macron|modi|albanese|carney|lula|sheinbaum")
# Checked in order; the first match wins, so "fined under the new law" counts as enforcement.
ACTIONS = {
    "enforcement": [r"\bfine[sd]?\b(?!-?tun)", r"\bpenalt", r"enforcement action", r"\bsanction(s|ed)\b",
                    r"cease[- ]and[- ]desist", r"\border(s|ed)? .{0,40}\bto (stop|halt|delete|suspend|remove)",
                    r"\bsettle(s|d|ment)\b", r"\bcharge[sd]\b", r"\bblock(s|ed)\b", r"\bsuspend(s|ed)\b"],
    "investigation": [r"investigat", r"\bprobes?\b", r"\bprobing\b", r"\binquiry\b", r"\benquiry\b",
                      r"\baudit", r"\bscrutin", r"request(s|ed)? information", r"opens? (a )?case"],
    "law": [r"signed into law", r"\bsigns? .{0,40}\b(bill|law|order|act)\b", r"\benact", r"\bratif",
            r"(comes?|came|enters?|entered|goes|went) into (force|effect)", r"\btakes? effect", r"\btook effect",
            r"\bin force\b",
            # a new executive order, not news that merely mentions an existing one
            r"\b(issu|sign|pass|creat|establish)\w* .{0,30}executive order", r"\bnew .{0,25}executive order",
            r"executive order (no\.? ?)?\d+",
            # "Pritzker establishes AI cabinet", "Newsom orders new steps", "ordered by Oregon governor"
            rf"\b({EXECUTIVES})\b.{{0,40}}\b(orders?|ordered|establish(es|ed)?|creates?|created|directs?|mandates?)\b",
            r"\bordered by\b.{0,40}\b(governor|president|prime minister)\b",
            r"\b(adopts?|introduces|imposes?) .{0,40}\b(scheme|rules|regulation|requirements|obligations)\b",
            r"\b(pass|approv|adopt)(es|ed|s)?\b.{0,60}\b(bill|law|act|legislation|regulation|rules)\b",
            r"\b(bill|law|act|legislation|regulation|rules)\b.{0,40}\b(passe[sd]|approved|adopted)\b"],
    "proposal": [r"\bbills?\b", r"\bdraft(s|ed|ing)?\b", r"\bpropos", r"\bintroduc\w* .{0,40}\b(bill|legislation|law|rules)",
                 r"\bconsultation", r"\btabled?\b", r"\bplans? to (regulate|ban|require)", r"\bwould (ban|require)"],
    "guidance": [r"\bguidance\b", r"\bguidelines?\b", r"code of (practice|conduct)", r"\bframework\b",
                 r"\bstandards?\b", r"\brecommendations?\b", r"\btoolkit\b", r"\bvoluntary commitments?\b"],
}
_actions = {k: re.compile("|".join(v), re.I) for k, v in ACTIONS.items()}
# "hasn't passed a law" or "urges China to adopt a law" is not a law being adopted.
_not_adopted = re.compile(r"n't|\bnot\b|\bfail(s|ed)? to\b|\burg(e|es|ed|ing)\b|\bcalls? (on|for)\b|\basks?\b|"
                          r"\bpush(es)? for\b|\bwithout\b", re.I)
_lobbying = re.compile(r"\b(asks?|urg(e|es|ed|ing)|submissions?|calls? (on|for)|push(es)? for|lobb\w*|"
                       r"letter to)\b", re.I)
# A lawsuit only counts as enforcement when a public authority brings it.
_suit = re.compile(r"\b(sues|sued|suing|lawsuit)\b", re.I)
_authority = re.compile(r"attorneys? general|\bFTC\b|\bDOJ\b|regulator|commission|authority|government|state of",
                        re.I)


def regulatory_action(title: str) -> str | None:
    """enforcement / investigation / law / proposal / guidance, judged on the headline.

    Only the title is used: feed summaries (Google News especially) carry publisher names such as
    "Business Standard" that would otherwise read as actions.
    """
    if _suit.search(title) and _authority.search(title):
        return "enforcement"
    for action, pattern in _actions.items():
        m = pattern.search(title)
        if not m:
            continue
        # Negations count only before the action: "hasn't passed a law", "urge China to adopt",
        # but not "establishes AI cabinet amid calls for greater regulation".
        if action == "law" and _not_adopted.search(title[: m.end()]):
            continue
        # "OpenAI, Anthropic ask Australia to ... propose", "My submission to the consultation":
        # lobbying a government, not a government proposing.
        if action == "proposal" and _lobbying.search(title[: m.start()]):
            continue
        return action
    return None
