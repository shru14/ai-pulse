"""Decide whether an item is AI-related and which category it belongs in.

Keyword rules only: no AI model or paid API is used anywhere.
"""

from __future__ import annotations

import re
import unicodedata

from . import jurisdictions
from .sources import SCHOLAR_HOME, SOURCES

# "Agent" is AI unless it's another kind: "foreign agents" (a Russian law), "FBI agents", "nerve agent".
_AGENT = (r"(?<!foreign )(?<!secret )(?<!federal )(?<!FBI )(?<!border )(?<!customs )(?<!travel )(?<!estate )"
          r"(?<!free )(?<!nerve )(?<!chemical )\bagents?\b")

AI_TERMS = [
    r"\bAI\b", r"artificial intelligence", r"machine learning", r"\bLLMs?\b", r"large language model",
    r"generative", r"chatbot", r"neural", r"deep learning", _AGENT, r"\bagentic\b",
    r"OpenAI", r"Anthropic", r"Claude", r"Gemini", r"ChatGPT", r"\bGPT-?\d", r"DeepMind", r"Mistral",
    r"DeepSeek", r"Qwen", r"Llama", r"Copilot", r"Hugging Face", r"Nvidia", r"diffusion model",
    r"foundation model", r"frontier model", r"superintelligence", r"\bAGI\b",
]

POLICY_TERMS = [
    r"regulat", r"legislat", r"\blaw\b", r"\blaws\b", r"\bbill\b", r"senate", r"congress", r"parliament",
    r"\bAI Act\b", r"European Commission", r"\bEU\b", r"executive order", r"white house", r"ministry",
    r"government", r"lawsuit", r"\bsue[sd]?\b", r"court", r"ruling", r"antitrust", r"\bFTC\b", r"\bDOJ\b",
    r"copyright", r"export control", r"sanction", r"privacy regulator", r"\bGDPR\b", r"data protection",
    r"(?<!Ray-)\bban\b", r"\bbans\b", r"safety institute",  # not "Ray-Ban Meta" glasses r"\bAISI\b", r"summit", r"treaty", r"election",
    # "governance", but not enterprise products' "identity / data / runtime governance" (Collibra, Vanderbilt's IAM)
    r"policy", r"(?<!identity )(?<!data )(?<!runtime )(?<!access )(?<!cloud )(?<!security )(?<!model )governance",
    r"lawmakers", r"minister", r"president",
    # regulators, investigations and the executive branch
    r"investigat", r"\bprobes?\b", r"scrutin", r"regulators?\b", r"watchdog", r"\bgovernor\b", r"\bgov\.",
    r"\bMPs?\b", r"\bcabinet\b", r"\bNIST\b", r"attorneys? general", r"administration\b", r"\badmin\b(?! (?:plugin|console|panel|tools?|controls?|settings|dashboard|roles?|access|users?|api)\b)",
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
# A news outlet's story is a release only if something was actually launched: words like "model", "API" or
# "feature" appear in studies, deals and opinion too ("AI agents do more of the work in model development").
_LAUNCH = re.compile(r"launch|releas|introduc|unveil|announc|rolls? out|available|open[- ]?sourc|\bmeet\b|"
                     r"\bcomes? to\b|\barrives?\b|\baccess to\b|\bnow (?:supports?|offers?|works)\b|"
                     r"\b(?:new|newest|latest) (?:\w+ ){0,3}(?:models?|apps?|tools?|features?|versions?|agents?|assistants?|chatbots?|API|"
                     r"platforms?|services?|devices?|chips?|products?|glasses|browsers?|modes?)\b|"
                     r"\bbeta\b|preview|version \d|\bv\d|\bcan now\b|\bships?\b|\bdebuts?\b|\bdrops\b|"
                     r"\blets\b|\bbrings\b|\badds?\b|\bgives\b|\bexpands\b", re.I)
# A story reporting a study's findings ("A research team analyzed 769 task logs...") is news about research,
# not a release, unless its headline announces a launch.
_STUDY = re.compile(r"\b(stud(y|ies)|researchers?|research team|analy[sz]ed|surveyed|paper|preprint|findings|"
                    r"found that|finds that|report(s)? finds?|according to (a|new) (study|report|survey))\b", re.I)
_news = re.compile("|".join(NEWS_SIGNALS), re.I)
# Standards bodies and standards (ISO/IEC 42001, IEEE 7000, NIST's frameworks, EU harmonised standards). What they
# publish or start is policy (NIST is a government agency) or industry news, never a product release.
_STANDARDS = re.compile(r"\bNIST\b|\bISO/IEC\b|\bISO \d{4,5}\b|\bIEEE (?:SA\b|Standards?\b|P?\d{4})|\bCEN-CENELEC\b|\bETSI\b|"
                        r"\bstandards? (?:body|bodies|organi[sz]ations?|institutes?)\b|\bharmoni[sz]ed standards?\b|"
                        r"\b(?:AI|artificial intelligence) standards\b", re.I)


def is_ai_related(title: str, summary: str) -> bool:
    return bool(_ai.search(f"{title} {summary}"))


# A launch in the past is history, not news: "since Cloudflare launched back on September 27, 2010".
_HISTORY = re.compile(r"\b(?:since|when)\b[^.,;]{0,40}\blaunch\w*|\blaunch\w* (?:back )?(?:in|on) [^.,;]{0,25}(?:19|20)\d\d\b", re.I)
# Company blogs post much besides launches. Their launch phrasing: a product with a version ("Nemotron 3.5",
# "OCR 4", "Multilingual R2"), open licences, updates and new capabilities, "Access X through Y".
_BLOG_LAUNCH = re.compile(r"\b[A-Z][\w.-]*[ -](?:v|R)?\d+(?:\.\d+)*\b(?<!\b(?:19|20)\d\d)|\b[A-Z][A-Za-z]+-?\d+\.\d+|"
                          r"Apache 2\.0|open[- ]weights?|(?i:\brolling out\b)|"
                          r"\bexperimental\b|\bupgrades?\b|\bnext evolution\b|\bnew capabilities\b|\bbring(?:s|ing)\b|"
                          r"(?i:^access\b|\bupdates? (?:the )?[\w -]{0,40}\bwith\b|\bnow (?:supports?|available|lets)\b)")
# ...and posts that aren't launches even when they "announce" or "introduce": deals, people, programmes,
# customer stories and guides ("How Ramp engineers ..."), podcasts.
_NOT_RELEASE = re.compile(r"^how\b|\bhow (?:they|we|it|i)\b|\bpartner|collaborat|\bacquir|\bjoins?\b|\binitiative\b|\bprogram(?:me)?s?\b|"
                          r"\bpodcast\b|\btrailer\b|\bepisode\b|\bfor (?:countries|governments|nonprofits)\b|"
                          r"\bletter\b|\bstate of\b|\broundup\b|\bweek\b|\bcourses?\b", re.I)


# Industry news that isn't reporting gets a label on its card (it stays in the stream): tutorials and guides,
# event previews and podcasts, and a company's own blog posts that aren't launches.
_TUTORIAL = re.compile(r"^(a |an )?(coding |step[- ]by[- ]step |hands[- ]on |practical |complete |beginner'?s? )?"
                       r"(guide|tutorial|walkthrough)\b|^how to\b|\bcoding guide\b|\bfor beginners\b|\btutorial\b|"
                       r"\bstep[- ]by[- ]step\b|^build(ing)? (a|an|your)\b|"
                       # Cloud how-tos: "Deploying real-time speech with Qwen3-TTS on Amazon SageMaker AI"
                       r"^(deploying|running|fine-?tuning|scaling|optimizing|accelerating|implementing|automating|"
                       r"serving|hosting|migrating|orchestrating|evaluating|monitoring|securing)\b.{0,120}\b"
                       r"(on|with|using|in|from|to) (amazon|aws|azure|microsoft foundry|google cloud|vertex ai|"
                       r"databricks|snowflake)\b", re.I)
_TUTORIAL_LEAD = re.compile(r"\btutorial\b|\bstep[- ]by[- ]step\b|\blearn how to\b|"
                            r"\bin this (post|tutorial|guide),? (we|you)('ll| will)? (show|walk|build|learn)", re.I)
_EVENT = re.compile(r"\bwhat to expect (at|during)\b|\btheCUBE\b|\bwebinar\b|\blivestream\b|\bpodcast\b|"
                    r"\bepisode\b|\binsights from\b|^ITWeb TV\b|\bTechCrunch Disrupt\b", re.I)


# A customer's results with a product: "Proaction boosts sales 60% and saves 75+ hours with Codex".
_CUSTOMER = re.compile(r"\b(boosts?|cuts?|saves?|reduces?|doubles?|triples?|speeds? up|turns?|scales?|resolves?)\b"
                       r"[^.]{0,60}\b(with|using)\b", re.I)


# Reporting of a study's or researchers' findings: "AI models show a willingness to harm humans ...", told by
# its headline, or by a summary that says a study, paper or survey found it.
# A researcher who quits or is accused is news about a person, not a finding, so the headline must say what
# the research found or produced.
_STUDY_TITLE = re.compile(r"\bstud(y|ies)\b|\bsurvey (finds|found|shows|says)\b|\bpreprint\b|\b(new|a) paper\b|"
                          r"\b(researchers?|scientists) (find|finds|found|show|shows|showed|say|says|discover|discovered|"
                          r"warn|used|use|plug|build|built|develop|developed|create|created|propose|proposes|introduce|"
                          r"introduces|release|releases|test|tested|train|trained)\b|"
                          r"\b(finds|found|reveals?|shows?) that\b|\breport finds\b", re.I)
_STUDY_LEAD = re.compile(r"\b(a|the|new|recent) (study|paper|preprint|survey|experiment)\b|\bresearchers (at|from)\b|"
                         r"\b(study|paper|survey|researchers|scientists|research team) (found|find|finds|show|shows|showed|suggests?|"
                         r"report|reported|tested|analy[sz]ed)\b|\baccording to (a|new) (study|report|survey)\b", re.I)
# Analysis and opinion: questions, "why", explainers, comparisons, interviews ("Can Muse overcome Meta's trust
# issues?", "Why letting Claude clean your TV's bloatware isn't the best idea").
_ANALYSIS = re.compile(r"\?\s*$|^(why|what|who|can|could|should|is|are|will|would|does|do)\b|^how\b(?! to\b)|"
                       r"\b(opinion|(?<!artificial )analysis|explained|explainer|compared|comparison|interview|q&a|deep dive|"
                       r"lessons from|the case for|the case against|column|a look at)\b|\bvs\.?\b|"
                       r"\bhere'?s (what|why|how)\b|\bwhat'?s at stake\b|^\d+ (ways|tips|things|reasons|safeguards|lessons)\b|"
                       # opinion: first person and argument ("I tried ...", "It's time to ...", "The problem with ...")
                       r"^(I|my|we)\b|\bI('m| am| was| tried| put| asked| used| spent| think)\b|\bit'?s time (to|for)\b|"
                       r"\bthe (problem|trouble) with\b|\bin defen[cs]e of\b|\bthe myth of\b|\bwe need to\b|\bstop (calling|pretending)\b|"
                       r":\s*(why|how|what)\b|\bshould\b",  # "Larry Yon: Why Africa's tech ecosystem should be building ..."
                       re.I)
# A first-person summary is a column or a diary, not reporting ("I headed back to Amsterdam for ...").
_OPINION_LEAD = re.compile(r"(^|[.!?]\s+)I('m| am| was| think| believe| headed| went| tried| spent| wrote| asked| put)\b|"
                           r"\bin my (view|opinion)\b")


def news_kind(title: str, summary: str, company_blog: bool) -> str:
    """What an industry card is: "tutorial", "event", "blog" (a company's own post that isn't a launch),
    "study" (reporting findings), "analysis" (opinion, explainers, comparisons) or "news" (reporting of an
    event). AI-incidents are told apart by the AI Incident Database, not here (store.cards)."""
    if _TUTORIAL.search(title) or _TUTORIAL_LEAD.search(summary or ""):
        return "tutorial"
    if _EVENT.search(title):
        return "event"
    if company_blog:
        return "blog"
    if _ANALYSIS.search(title) or _OPINION_LEAD.search(summary or "") or re.match(r"(four|five|six|seven|eight|nine|ten|three) (ways|tips|things|reasons|safeguards)\b", title, re.I):
        return "analysis"
    if _STUDY_TITLE.search(title) or _STUDY_LEAD.search(summary or ""):
        return "study"
    return "news"


# A headline about people coming and going is never a release ("Another OpenAI safety departure ...", whose summary
# mentions agents that were "accidentally released"). A person leaving names where from ("leaves Meta", "leaves the
# company"); a technical "early exit" or "no data leaves the device" isn't one.
_PEOPLE = re.compile(r"(?i:\bdepartures?\b|\bresign(?:s|ed|ing|ation)?\b|\bquits?\b|\bsteps? down\b|\bfired\b|\bousted\b)|"
                     r"\b(?i:leav(?:es|ing))\s+(?:[A-Z]|(?i:the company|his|her|their|its board|to (?:launch|join|start|found|focus|work)))|"
                     r"(?:'s|’s) (?i:exit)\b|\b(?i:exits)\s+(?:[A-Z]|(?i:the company|as\b))")


def launched(title: str, summary: str) -> bool:
    """Does a news story report something being released? It needs launch language, and a study's findings
    count only when the headline itself announces a launch ("Researchers release ...")."""
    if (m := _PEOPLE.search(title)) and not _LAUNCH.search(title[:m.start()]):  # "Meta releases Llama 4, leaves EU out" still is
        return False
    text = _HISTORY.sub(" ", f"{title} {summary}")
    return bool(_LAUNCH.search(text)) and not (_STUDY.search(text) and not _LAUNCH.search(title))


def released(title: str, summary: str) -> bool:
    """Does a company blog post launch something? Launch language as for news, or the blog phrasing above,
    unless the headline is a deal, a person, a programme, a guide or a podcast, or the post is a tutorial ("Learn how
    to run SkyRL, an open-source framework...") or a customer story ("Proaction boosts sales 60% ... with Codex")."""
    if _NOT_RELEASE.search(title) or _CUSTOMER.search(title) or news_kind(title, summary, False) == "tutorial":
        return False
    return launched(title, summary) or bool(_BLOG_LAUNCH.search(title)) or bool(_BLOG_LAUNCH.search(_HISTORY.sub(" ", summary)))


def about_standards(title: str) -> bool:
    """Does a headline name a standards body or a standard (never a release; see _STANDARDS)?"""
    return bool(_STANDARDS.search(title))


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
    if _STANDARDS.search(title):  # whatever the feed (a policy one included, or re-sorting would flip it back)
        return "policy" if policy >= 2 or default == "policy" else "news"
    if default == "tool" and _news.search(title):
        return "news"
    if default == "tool":  # a company blog: a release only when something is launched
        return "tool" if released(title, summary) else "news"
    if tool >= 3 and tool > policy and launched(title, summary):
        return "tool"
    if default == "policy" and policy == 0 and regulatory_action(title) is None and not jurisdictions.acting(title):
        return "news"  # a policy search picked up a story with nothing about government in it
    return default


COMPANY_TERMS = {
    "OpenAI": r"OpenAI|ChatGPT|\bGPT-?\d", "Anthropic": r"Anthropic|Claude", "Google": r"Google|Gemini|DeepMind",
    # whole words, and case-sensitive where the name is also a word: not "lawsuit" (AWS), "Ollama" or "llama.cpp"
    # (Llama), "safety intel" (Intel), "apple", "meta-analysis"
    "Meta": r"(?-i:\bMeta\b)|\bLlama\b(?!\.cpp)", "Microsoft": r"Microsoft|(?<!GitHub )Copilot", "Nvidia": r"Nvidia",
    "Apple": r"(?-i:\bApple\b)", "Amazon": r"Amazon|(?-i:\bAWS\b)", "xAI": r"\bxAI\b|Grok", "Mistral": r"Mistral",
    "DeepSeek": r"DeepSeek",
    "Alibaba": r"Alibaba|Qwen",
    # chips and big tech
    "AMD": r"\bAMD\b", "Intel": r"(?-i:\bIntel\b)", "Qualcomm": r"Qualcomm", "IBM": r"\bIBM\b", "Oracle": r"\bOracle\b",
    "Samsung": r"Samsung", "SK Hynix": r"SK ?Hynix", "TSMC": r"\bTSMC\b", "Salesforce": r"Salesforce",
    "Tencent": r"Tencent|Hunyuan", "ByteDance": r"ByteDance|TikTok|Doubao", "Baidu": r"Baidu|\bERNIE\b",
    "Huawei": r"Huawei", "Xiaomi": r"Xiaomi",
    # AI labs and companies ((?-i:...): case matters where the name is also a word, as "minimax" or "perplexity"
    # in a paper)
    "Meituan": r"Meituan|LongCat", "Moonshot AI": r"Moonshot AI|\bKimi\b", "Zhipu AI": r"Zhipu|\bZ\.ai\b",
    "MiniMax": r"(?-i:MiniMax)", "StepFun": r"StepFun", "Cohere": r"(?-i:Cohere)", "Sakana AI": r"Sakana",
    # the company, not the measure ("Perplexity of language models ...")
    "Perplexity": r"(?-i:Perplexity(?: AI| Pro| Comet|['’]s|(?= (?:launches|releases|raises|says|adds|unveils|introduces"
                  r"|is|has|will|CEO|sues|signs|buys|opens)\b)))",
    "Hugging Face": r"Hugging ?Face", "Databricks": r"Databricks",
    "Snowflake": r"(?-i:Snowflake)", "Stability AI": r"Stability AI|Stable Diffusion", "Character.AI": r"Character\.?AI",
    "World Labs": r"World Labs",
}
# A company's home country: the country tag of a story that names no place ("Nvidia launches ..." -> United States).
COMPANY_HOME = {
    **dict.fromkeys(["OpenAI", "Anthropic", "Google", "Meta", "Microsoft", "Nvidia", "Apple", "Amazon", "xAI", "AMD",
                     "Intel", "Qualcomm", "IBM", "Oracle", "Salesforce", "Perplexity", "Databricks", "Snowflake",
                     "Character.AI", "World Labs"], "United States"),
    **dict.fromkeys(["DeepSeek", "Alibaba", "Tencent", "ByteDance", "Baidu", "Huawei", "Xiaomi", "Meituan", "Moonshot AI",
                     "Zhipu AI", "MiniMax", "StepFun"], "China"),
    "Mistral": "France", "Samsung": "South Korea", "SK Hynix": "South Korea", "TSMC": "Taiwan", "Sakana AI": "Japan",
    "Cohere": "Canada", "Stability AI": "United Kingdom",
}

TOPIC_TERMS = {
    # Tech & capabilities
    "Agents": _AGENT + r"|agentic",
    "Open Models": r"open-?source|open-?weight",
    "Reasoning": r"reasoning|chain[- ]of[- ]thought",
    "Multimodal": r"multimodal|vision[- ]language",
    "Voice": r"\bvoice\b|speech|text-to-speech|\bTTS\b|\bASR\b",
    "Image & Video Generation": r"image generat|video generat|text-to-(image|video)|diffusion",
    "Coding Tools": r"coding|code assistant|copilot|\bIDE\b|developer tool",
    "Robotics": r"robot|humanoid|embodied",
    "Benchmarks": r"benchmark|leaderboard|\beval(uation)?s?\b",
    # News reporting a study's findings (papers themselves are in the Research stream, tagged by author)
    "Study Report": r"\bstud(y|ies)\b|research team|\banaly[sz]ed\b|\bsurveyed\b|\bpaper\b|preprint|arXiv|"
                    r"\bfindings\b|\bfound that\b|\bfinds that\b|\breports? finds?\b|"
                    r"researchers (found|find|say|show|showed|discover|discovered|report|reported|tested|analy[sz]ed)",
    "Training Data": r"training data|dataset|scrap(e|ing)",
    # Infrastructure
    "Chips": r"\bchips?\b|GPU|semiconductor|TSMC|\bTPU\b",
    "Compute & Data Centers": r"data cent(er|re)|\bcompute\b|supercomputer|(?:GPU|compute|computing|AI|training) clusters?|computing (?:power|capacity)",  # not "computer", "clustering"
    "Energy": r"energy|power grid|electricity|nuclear (?:power|energy|reactors?|plants?)|gigawatt|\bGW\b",  # not "nuclear war"
    # Business
    "Funding": r"raises|funding|valuation|Series [A-F]",
    "M&A": r"acquir|acquisition|merger|buys\b",
    "IPO": r"\bIPO\b|going public|listing",
    "Jobs & Labor": r"\bjobs?\b|layoffs?|workforce|employment|\blabou?r\b",  # not "collaboration"
    # Law & governance
    "Standards": _STANDARDS.pattern + r"|\bAI RMF\b|risk management framework|\b42001\b",
    "Law": r"\blaws?\b|legislat|\bbill\b(?! Gates)|\b(?:AI|state|federal|Senate|House|draft|two|these|the) bills\b|lawsuit|\bsue[sd]?\b|court|ruling|judge",
    "Regulation": r"regulat|compliance|enforcement|regulator",
    # a summit or standard in AI governance, not an industry event or "the gold standard for ..."
    "Governance": r"governance|oversight|(?:AI|safety|technical|international|global) standards?\b|treaty|"
                  r"(?:AI|safety|action|impact|G7|G20|UN|global|bilateral|leaders['’]?|Trump-Xi|Xi-Trump) summit|safety institute|\bAISI\b",
    "AI Act": r"\bAI Act\b",
    "Copyright": r"copyright|licens(e|ing) deal|fair use|pirat",
    "Privacy": r"privacy|\bGDPR\b|data protection|personal data",
    "Antitrust": r"antitrust|competition authority|monopol|\bFTC\b",
    "Export Controls": r"export control|sanction|entity list",
    "Defense": r"military|defen[cs]e|Pentagon|drone|national security",
    "Elections": r"\belections?\b|\belectoral\b|misinformation|disinformation",  # not "selection"
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
    "Education": r"educat|school|student|teacher|classroom|\btutor(?:s|ing)?\b",  # not "tutorial"
    "Healthcare": r"health|medical|clinic|patient|drug",
    # a scientific discovery, not "customers discover ..." or "discovered during a review"
    "Science": r"scientific|(?:drug|materials?) discover|discover(?:s|ed|ing)? (?:a |an )?(?:novel|new) (?:\w+ )?"
               r"(?:enzymes?|proteins?|molecules?|materials?|drugs?|antibiotics?|compounds?|species|genes?)|protein|biology|physics|chemistry",
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


def lead_company(title: str) -> str | None:
    """The company a headline is about: the first one it names ("xAI launches Grok 4.7 ... Claude and GPT-6" -> xAI)."""
    found = [(m.start(), k) for k, p in _companies.items() if (m := p.search(title))]
    return min(found)[1] if found else None


# Our own note on translated official records ("Machine-translated from Portuguese; ...") names a language,
# not a place: a Brazilian bill isn't about Portugal, a Swiss one isn't about Germany.
_TRANSLATED = re.compile(r"\s*(?:Machine-translated from \w+; the (?:official text|original) is linked|"
                         r"Translate and read: the original is in \w+)\.")
UNTRANSLATED_TAG = "Translate and read"  # a story no translation could be made of (collect.in_english)


# An official source's own country (or the EU): the country tag of its publications that name no place ("Pilot AI
# App for Smart Grocery Shopping Launched in Five Regions", from Korea's ministry -> South Korea).
SOURCE_HOME = {s["name"]: jurisdictions.JURISDICTIONS[s["jurisdictions"][0]][0] for s in SOURCES
               if s.get("jurisdictions") and (s.get("government") or s["category"] == "regulation")}


# --- Infra & climate: AI's physical side (data centres and what they draw on) ---
INFRA_TAG = "Infra & climate"
# Data centres themselves: named anywhere in a story, they make it one about AI's infrastructure.
_DC = re.compile(r"data[- ]?cent(?:er|re)s?|\bhyperscalers?\b|\bhyperscale (?:data|campus|facilit)|server farms?|"
                 r"\bAI campus(?:es)?|gigafactor\w* of compute", re.I)
# In a headline, also the other places AI runs (a paper's summary mentioning its GPU cluster doesn't count).
_SITE = re.compile(_DC.pattern + r"|\bAI factor(?:y|ies)|\b(?:GPU|compute|AI|training) clusters?|supercomput\w*|"
                   r"\bcompute capacity", re.I)
# AI's own footprint: "AI's energy use", "emissions from AI", "energy-hungry AI". Not AI used *for* sustainability
# (a soil-quality model, AI that cuts a factory's emissions), and not "climate" or weather science.
_FOOTPRINT = re.compile(r"\bAI['’]s (?:energy|electricity|power|carbon|water|emissions|environmental|climate)\b|"
                        r"\b(?:emissions|energy|electricity|water) (?:from|of|used by|use of) (?:AI|data)\b|"
                        r"\benergy[- ]hungry", re.I)
# With AI in the headline: power and the grid ("Microsoft taps Three Mile Island nuclear plant to power AI"); not
# "the new electricity", "pre-nuclear steel" or a "nuclear option".
_POWER = re.compile(r"\belectricity (?:demand|use|usage|consumption|prices|bills|costs?|supply|needs|grid)\b|"
                    r"\bto power (?:AI\b|its AI|(?:AI |the |its |their )?data cent)|"
                    r"\bpower (?:plants?|deals?|supply|demand|grid|costs?|purchase|consumption|usage|infrastructure)\b|"
                    r"\bnuclear (?:power|plants?|reactors?|energy|deals?|startups?)\b|\b(?:giga|mega)watts?\b|"
                    r"\b\d+(?:\.\d+)? ?[GM]W\b|"
                    r"\benergy (?:demand|use|usage|consumption|costs?|appetite|bills?|needs|crunch)\b|"
                    r"\bwater (?:use|usage|consumption|supply)\b", re.I)


_LIKE = re.compile(r"\b(?:like|than)\s+(?:an?\s+|the\s+)?$", re.I)


def _power(title: str) -> bool:
    """Power named as itself, not in a comparison ("AI should be regulated like nuclear power plants")."""
    return any(not _LIKE.search(title[:m.start()]) for m in _POWER.finditer(title))


def infra_story(title: str) -> bool:
    """Judged on the headline, for moving an Industry story into the stream: about data centres or other places
    AI runs, AI's own footprint, or AI and power ("Microsoft taps Three Mile Island nuclear plant to power AI")."""
    return bool(_SITE.search(title) or _FOOTPRINT.search(title) or (_ai.search(title) and _power(title)))


def is_infra(title: str, summary: str) -> bool:
    """A story about AI's infrastructure or footprint: its headline says so (infra_story), or its text names data
    centres or AI's footprint. Tags the story in every stream, and filters the energy and climate newsrooms."""
    return infra_story(title) or bool(_DC.search(summary) or _FOOTPRINT.search(summary))


# What a story about AI's infrastructure is about, so its stream can be read by subject. Only for those stories
# (is_infra): "water" or "permit" elsewhere means something else. One story can have several.
INFRA_TOPICS = {
    "Power & grid": r"electricity|\bpower (?:grid|supply|demand|plants?|stations?|purchase|deals?|consumption|capacity|prices)|"
                    r"\bgrid\b|nuclear|\bSMRs?\b|small modular reactor|natural gas|gas[- ]fired|gas turbines?|"
                    r"\butilit(?:y|ies)\b|transmission lines?|baseload|geothermal|fuel cells?|"
                    r"energy (?:demand|use|usage|consumption|supply|costs?|prices|bills?)|"
                    r"power[- ]hungry|energy[- ]hungry|\bPPAs?\b|power purchase|energy[- ]efficien|"
                    r"energy (?:burden|impact|appetite|footprint|crunch|obsession)",
    "Water": r"\bwater (?:use|usage|consumption|supply|footprint|stress|scarcity|rights|bills?)|gallons|litres|liters|"
             r"drought|aquifer|water[- ]cooled|cooling water|\bwater\b.{0,40}\bcool|\bcool.{0,40}\bwater\b",
    "Emissions & climate": r"emission|carbon|greenhouse|\bCO2\b|net[- ]zero|renewabl|\bsolar\b|wind (?:power|farms?|energy|turbines?)|"
                           r"clean (?:energy|power)|green (?:energy|power|data cent)|sustainab|decarboni|\bPUE\b|e-waste|"
                           r"waste heat|heat reuse|climate (?:impact|goals?|targets?|pledges?|commitments?|costs?|footprint|change)|"
                           r"environmental (?:impact|costs?|footprint|toll|harm)",
    "Land & local pushback": r"oppos(?:e|es|ed|ing|ition)|protest|residents|neighbou?rs|\bcommunit(?:y|ies)\b|zoning|rezon|"
                             r"moratorium|backlash|pushback|resist|\bnoise\b|farmland|land use|\bacres?\b|"
                             r"(?:county|town|city) (?:board|council|commission)|local (?:officials|resistance|concerns)",
    "Builds & deals": r"\bbuild(?:s|ing)?\b|\bbuilt\b|construct|\bcampus(?:es)?\b|\bopens?\b|\bopened\b|break(?:s|ing)? ground|"
                      r"groundbreaking|expan(?:d|ds|sion)|\binvest(?:s|ed|ing|ments?)?\b|\$\s?\d|billion|\bbn\b|\blease[sd]?\b|"
                      r"acqui(?:re|res|red|sition)|\bstake\b|\b\d+(?:\.\d+)? ?[GM]W\b|megawatts?|gigawatts?|"
                      r"\bdeal\b|partners(?:hip)?\b|\bplans?\b|\bproposed\b",
    "Rules & permits": r"permits?\b|planning (?:permission|approval|application)|\bapprov(?:al|es|ed)\b|regulat|\blaws?\b|"
                       r"\bbills?\b(?! Gates)|legislat|tax (?:breaks?|incentives?|credits?|exemptions?)|incentives?|"
                       r"subsid|reporting (?:rules?|requirements?)|\bban(?:s|ned)?\b|moratorium|halts?\b|"
                       r"government (?:plan|policy|rules?|strategy)",
    # the machines themselves: supercomputers, "AI factories", GPU clusters, servers and their cooling
    "Hardware & compute": r"supercomput|AI factor(?:y|ies)|\bGPUs?\b|\bservers?\b|\bclusters?\b|\bchips?\b|\bracks?\b|"
                          r"cooling|accelerators?|compute capacity|\bTPUs?\b|Blackwell|Vera Rubin|Grace Hopper|semiconductor|networking",
}
_infra_topics = {k: re.compile(v, re.I) for k, v in INFRA_TOPICS.items()}
# A paper about AI's own footprint, judged on its title: a cost (energy, carbon, water, power) of AI's computing
# ("Measuring the Carbon Footprint of LLM Inference"), not AI used for energy ("Neural networks forecast solar output").
_FOOTPRINT_COST = re.compile(r"energy[- ](?:consumption|use|usage|cost|footprint|efficien\w*|demand|budget)|energy[- ]aware|"
                             r"carbon (?:footprint|emissions?|intensity|cost)|carbon[- ]aware|emissions|\bCO2\b|"
                             r"water (?:use|usage|consumption|footprint)|environmental (?:impact|cost|footprint)|"
                             r"power (?:consumption|draw|usage|demand)|sustainab\w*|green AI|\bjoules?\b|\bwatts?\b", re.I)
_FOOTPRINT_SUBJECT = re.compile(r"\bLLMs?\b|language models?|\binference\b|\btraining\b|\bGPUs?\b|data ?cent(?:er|re)s?|"
                                r"accelerators?|foundation models?|generative|transformers?|\bML workloads?|"
                                r"machine learning (?:models?|workloads?|systems?)|neural network training", re.I)
# Broader words that also name AI used *for* energy ("Deep learning forecasts building energy use"): they count only
# when the title isn't about forecasting or running a power system.
_FOOTPRINT_LOOSE = re.compile(r"\bAI\b|deep learning|machine learning|neural networks?", re.I)
_AI_FOR_ENERGY = re.compile(r"forecast\w*|predict\w*|buildings?|smart (?:grid|meter)s?|households?|HVAC|solar|wind|"
                            r"batter(?:y|ies)|electric vehicles?|power systems?|microgrids?", re.I)


def ai_footprint_paper(title: str) -> bool:
    """A paper on the energy, carbon, water or power that AI's computing costs (see above)."""
    if not _FOOTPRINT_COST.search(title) or "energy-based" in title.lower():
        return False
    return bool(_FOOTPRINT_SUBJECT.search(title) or (_FOOTPRINT_LOOSE.search(title) and not _AI_FOR_ENERGY.search(title)))


# What an infrastructure story's own tags already say: the stream's subject itself, and the general topics the
# finer ones above replace (a reader's saved choice of these still matches: preferences.labels).
INFRA_SAYS = {"Compute & Data Centers": INFRA_TAG, "Energy": "Power & grid", "Climate": "Emissions & climate",
              "Chips": "Hardware & compute"}


def paper_homes() -> dict[str, str]:
    """{tag: country} for a paper's scholar and company tags: where a paper counts in the region filter."""
    return {**COMPANY_HOME, **_PAPER_COMPANY_HOME, **SCHOLAR_HOME}


# Companies that publish papers (sources.COMPANIES) but aren't in the news tags' COMPANY_HOME
_PAPER_COMPANY_HOME = {"Adobe": "United States", "Sony": "Japan", "Ant Group": "China", "Kuaishou": "China",
                       "Kakao": "South Korea", "NAVER": "South Korea", "LG AI Research": "South Korea"}


def tags_for(title: str, summary: str, limit: int = 5, source: str = "") -> list[str]:
    """Companies first, then places, then topics (see TOPIC_TERMS); a story left in its own language leads with
    "Translate and read". `source`: the story's publisher; a government's own publication that names no place
    gets that government's country."""
    untranslated = "Translate and read: the original is in" in summary
    summary = _TRANSLATED.sub("", summary)
    text = f"{title} {summary}"
    # a topic named only in a comparison isn't the story's ("regulated like nuclear power plants" isn't Energy)
    topics = [k for k, p in _topics.items() if any(not _LIKE.search(text[:m.start()]) for m in p.finditer(text))]
    if is_infra(title, summary):  # in every stream, so Research, Policy and the tracker show it too
        finer = [k for k, p in _infra_topics.items() if p.search(text)]
        topics = [INFRA_TAG, *finer, *(t for t in topics if INFRA_SAYS.get(t) not in (INFRA_TAG, *finer))]
        limit += 1  # the stream's own page leaves out its name (templates/index.html), so it still shows `limit`
    companies, places = company_tags(title, summary), place_tags(title, summary)
    lead = lead_company(title) or (companies[0] if companies else None)
    if not places and source in SOURCE_HOME:
        places = [SOURCE_HOME[source]]
    elif not places and lead in COMPANY_HOME:  # a story naming no place: where the company it's about is based
        places = [COMPANY_HOME[lead]]
    return ([UNTRANSLATED_TAG] * untranslated + companies[:2] + places + topics)[:limit]


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
_naming = re.compile(r"\bto (call|rename|refer to|stop calling|use the (word|term|name))\b", re.I)
_lobbying = re.compile(r"\b(asks?|urg(e|es|ed|ing)|submissions?|calls? (on|for)|push(es)? for|lobb\w*|"
                       r"letter to)\b", re.I)
# A body putting AI to work is news about its use of AI, not an action on AI ("NITDA deploys AI to turn youths'
# ideas into policy proposals", "council uses chatbot to draft guidance").
_uses_ai = re.compile(r"\b(?:deploy|use|adopt|launch|roll|build|tap|turn)\w*\s+(?:out\s+)?(?:an?\s+|its\s+|new\s+)?"
                      r"(?:AI|artificial intelligence|chatbots?|generative AI|AI[- ]\w+)\b(?:\s+\w+){0,2}?\s+to\b", re.I)
# A lawsuit only counts as enforcement when a public authority brings it.
_suit = re.compile(r"\b(sues|sued|suing|lawsuit)\b", re.I)
_authority = re.compile(r"attorneys? general|\bFTC\b|\bDOJ\b|regulator|commission|authority|government|state of",
                        re.I)


def regulatory_action(title: str) -> str | None:
    """enforcement / investigation / law / proposal / guidance, judged on the headline.

    Only the title is used: feed summaries (Google News especially) carry publisher names such as
    "Business Standard" that would otherwise read as actions.
    """
    # A body that "moves to regulate" is proposing rules; the fines in such a headline are the ones it plans
    # ("FCCPC moves to regulate AI marketing, businesses face N100 million penalty").
    # Not a move against one company ("Trump moves to ban Anthropic from the US government"): that's no rule on AI.
    if (m := re.search(r"\bmov(?:es|ed|ing) to (?:regulate|ban|require|restrict|curb|outlaw)\b", title, re.I)) \
            and not _lobbying.search(title) and not company_tags(title[m.end():]):
        return "proposal"
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
        # "Trump orders US government to call AI 'Super Intelligence'": an order about what the
        # government calls something regulates nothing.
        if action == "law" and _naming.search(title[m.start():]):
            continue
        # "OpenAI, Anthropic ask Australia to ... propose", "My submission to the consultation":
        # lobbying a government, not a government proposing.
        if action == "proposal" and _lobbying.search(title[: m.start()]):
            continue
        if action in ("proposal", "guidance") and _uses_ai.search(title[: m.start()]):
            continue
        return action
    return None
