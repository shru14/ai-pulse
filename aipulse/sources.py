"""Feeds AI Pulse collects from.

Each source has a default category ("tool", "news", "policy", "research" or "regulation").
The classifier can override it per item based on keywords, so a policy story
from a general tech feed still lands under "policy". Research sources always
stay under "research", and carry only papers.

Optional per-source keys:
  format        "feed" (RSS/Atom, the default) or "hf_daily" (Hugging Face Daily Papers JSON)
  org           a company tag for every item (e.g. Apple's own paper feed)
  professors    arXiv author searches: names that must appear among a paper's authors
  companies     True when items are kept only if a big-tech company is matched (see COMPANIES)
  expert        regulation tracker: the ethics / philosophy / law scholar a source follows
                (True for arXiv searches covering several of them)
  ai_only       True when every item is about AI (skips the AI keyword filter)
  ai_in_title   True for general feeds where only items with AI in the title count
  max_age_days  look back further than the run default (for feeds that post weekly or monthly)
  max_items     only take the first N entries of each fetch
  pause         seconds to wait after fetching (arXiv asks for 3)
  expect_entries True when the source always lists its latest items, so an empty reply is a glitch:
                it is retried, and counts as a failed fetch if it stays empty
  label         name shown in source health checks when several sources share a name (arXiv)
  jurisdictions regulation sources: codes to use when a story doesn't name a place (e.g. ["EU"])

Policy stories from any source move to the regulation tracker when they report a proposal or an
adopted law in a recognisable country; see collect.apply_regulation.

Add, remove or edit entries freely. Any RSS 2.0 or Atom feed works.
"""

from urllib.parse import quote_plus

SOURCES = [
    # --- Labs and product blogs (mostly releases) ---
    {"name": "OpenAI News", "url": "https://openai.com/news/rss.xml", "category": "tool"},
    {"name": "Google AI Blog", "url": "https://blog.google/technology/ai/rss/", "category": "tool"},
    {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml", "category": "tool"},

    # --- Industry news ---
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "category": "news"},
    {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "category": "news"},
    {"name": "Ars Technica AI", "url": "https://arstechnica.com/ai/feed/", "category": "news"},
    {"name": "MIT Technology Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed", "category": "news"},
    # VentureBeat's own feed (venturebeat.com/category/ai/feed/) answers every request with 429,
    # so its stories come through a Google News search limited to the site.
    {"name": "VentureBeat AI", "url": "https://news.google.com/rss/search?q=site:venturebeat.com+AI+when:2d&hl=en-US&gl=US&ceid=US:en",
     "category": "news"},
    {"name": "The Decoder", "url": "https://the-decoder.com/feed/", "category": "news"},

    # --- Policy and politics ---
    # The newsletter's Substack feed sits behind a Cloudflare check that blocks cloud servers (GitHub Actions);
    # the publisher's own site feed carries its explainers and analysis.
    {"name": "EU AI Act Newsletter", "url": "https://artificialintelligenceact.eu/feed/", "category": "policy"},
    {"name": "Google News: AI regulation",
     "url": "https://news.google.com/rss/search?q=%22AI%22+(regulation+OR+legislation+OR+%22AI+Act%22+OR+executive+order)+when:2d&hl=en-US&gl=US&ceid=US:en",
     "category": "policy"},
    {"name": "Google News: AI policy Europe",
     "url": "https://news.google.com/rss/search?q=%22artificial+intelligence%22+(EU+OR+Commission+OR+Bundestag+OR+Parliament)+policy+when:2d&hl=en-GB&gl=GB&ceid=GB:en",
     "category": "policy"},
]

# --- Regulation tracker: proposals and adopted laws ---
_GN = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q="
_REG = {"category": "regulation"}
SOURCES += [
    {**_REG, "name": "European Data Protection Board", "url": "https://www.edpb.europa.eu/feed/news_en",
     "jurisdictions": ["EU"]},
    {**_REG, "name": "European Commission: Digital Strategy", "url": "https://digital-strategy.ec.europa.eu/en/rss.xml",
     "jurisdictions": ["EU"]},
    {**_REG, "name": "Google News: AI laws passed",
     "url": _GN + "AI+(law+OR+bill+OR+act)+(passed+OR+signed+OR+enacted+OR+%22takes+effect%22+OR+%22into+force%22+OR+approved)+when:3d"},
    {**_REG, "name": "Google News: AI bills and draft rules",
     "url": _GN + "AI+(bill+OR+%22draft+law%22+OR+%22draft+rules%22+OR+%22proposed+rules%22+OR+consultation+OR+legislation)+(introduced+OR+proposes+OR+unveils+OR+tabled)+when:3d"},
    {**_REG, "name": "Google News: AI rules in Asia-Pacific",
     "url": _GN + "AI+(regulation+OR+law+OR+rules+OR+bill)+(China+OR+India+OR+Japan+OR+Korea+OR+Singapore+OR+Indonesia+OR+Vietnam+OR+Australia)+when:3d"},
    {**_REG, "name": "Google News: AI rules in the Americas, Africa & Middle East",
     "url": _GN + "AI+(regulation+OR+law+OR+bill+OR+rules)+(Brazil+OR+Canada+OR+Mexico+OR+Chile+OR+Nigeria+OR+Kenya+OR+%22South+Africa%22+OR+UAE+OR+Saudi)+when:3d"},
    {**_REG, "name": "Google News: AI rules in Europe",
     "url": _GN + "AI+(law+OR+bill+OR+rules+OR+%22AI+Act%22)+(EU+OR+UK+OR+France+OR+Germany+OR+Italy+OR+Spain+OR+%22European+Commission%22)+when:3d"},
]

# --- Regulation tracker: AI ethics, philosophy and law scholars, followed daily ---
# Each person gets a Google News search (their op-eds, interviews and work covered in the press);
# their arXiv papers are picked up by the author searches further down.
EXPERTS = [
    # Philosophy and ethics
    ("Luciano Floridi", "Philosophy", "Yale"),
    ("Shannon Vallor", "Philosophy", "University of Edinburgh"),
    ("Seth Lazar", "Philosophy", "Australian National University"),
    ("Carissa Véliz", "Philosophy", "University of Oxford"),
    ("David Chalmers", "Philosophy", "NYU"),
    ("Jonathan Birch", "Philosophy", "LSE"),
    ("Mark Coeckelbergh", "Philosophy", "University of Vienna"),
    ("Atoosa Kasirzadeh", "Philosophy", "Carnegie Mellon"),
    ("Iason Gabriel", "Ethics", "Google DeepMind"),
    ("Virginia Dignum", "Ethics", "Umeå University"),
    ("Joanna Bryson", "Ethics", "Hertie School"),
    ("Timnit Gebru", "Ethics", "DAIR"),
    ("Margaret Mitchell", "Ethics", "Hugging Face"),
    ("Abeba Birhane", "Ethics", "Trinity College Dublin"),
    ("Kate Crawford", "Ethics", "USC / Microsoft Research"),
    ("Rumman Chowdhury", "Ethics", "Humane Intelligence"),
    ("Arvind Narayanan", "Ethics", "Princeton"),
    ("Sayash Kapoor", "Ethics", "Princeton"),
    ("Brent Mittelstadt", "Ethics", "Oxford Internet Institute"),
    # Law and governance
    ("Sandra Wachter", "Law", "Oxford Internet Institute"),
    ("Lilian Edwards", "Law", "Newcastle University"),
    ("Michael Veale", "Law", "UCL"),
    ("Ryan Calo", "Law", "University of Washington"),
    ("Frank Pasquale", "Law", "Cornell"),
    ("Danielle Citron", "Law", "University of Virginia"),
    ("Margot Kaminski", "Law", "University of Colorado"),
    ("Woodrow Hartzog", "Law", "Boston University"),
    ("Pamela Samuelson", "Law", "UC Berkeley"),
    ("Mark Lemley", "Law", "Stanford"),
    ("Anu Bradford", "Law", "Columbia"),
    ("Lawrence Lessig", "Law", "Harvard"),
    ("Gillian Hadfield", "Law", "Johns Hopkins"),
    ("Mireille Hildebrandt", "Law", "Vrije Universiteit Brussel"),
    ("Urs Gasser", "Law", "TU Munich"),
    ("Angela Huyue Zhang", "Law", "USC"),
    ("Nita Farahany", "Law", "Duke"),
    ("Chinmayi Arun", "Law", "Yale"),
    ("Helen Toner", "Governance", "CSET, Georgetown"),
    ("Matt Sheehan", "Governance", "Carnegie Endowment"),
]
EXPERT_FIELDS = {name: field for name, field, _ in EXPERTS}
for _name, _field, _org in EXPERTS:
    SOURCES.append({
        "name": f"Google News: {_name}", "category": "regulation", "expert": _name,
        "url": _GN + quote_plus(f'"{_name}"') + "+AI+when:7d", "max_age_days": 7, "max_items": 3, "pause": 1,
    })

# --- Research: papers only, tagged by professor or company ---
# Papers by leading AI professors worldwide (arXiv author search). A paper is kept only when one of
# its authors matches a listed name exactly (see collect.py), which filters out namesakes.
PROFESSORS = [
    # United States and Canada
    ("Yoshua Bengio", "Mila / Université de Montréal"), ("Aaron Courville", "Mila / Université de Montréal"),
    ("Doina Precup", "McGill / Mila"), ("Geoffrey Hinton", "University of Toronto"),
    ("Raquel Urtasun", "University of Toronto"), ("Sanja Fidler", "University of Toronto"),
    ("Roger Grosse", "University of Toronto"), ("Richard Sutton", "University of Alberta"),
    ("Yann LeCun", "NYU"), ("Kyunghyun Cho", "NYU"), ("Fei-Fei Li", "Stanford"),
    ("Christopher Manning", "Stanford"), ("Percy Liang", "Stanford"), ("Chelsea Finn", "Stanford"),
    ("Yejin Choi", "Stanford"), ("Stefano Ermon", "Stanford"), ("Tengyu Ma", "Stanford"), ("Diyi Yang", "Stanford"),
    ("Sergey Levine", "UC Berkeley"), ("Pieter Abbeel", "UC Berkeley"), ("Dawn Song", "UC Berkeley"),
    ("Trevor Darrell", "UC Berkeley"), ("Jitendra Malik", "UC Berkeley"), ("Stuart Russell", "UC Berkeley"),
    ("Tommi Jaakkola", "MIT"), ("Regina Barzilay", "MIT"), ("Antonio Torralba", "MIT"), ("Jacob Andreas", "MIT"),
    ("Phillip Isola", "MIT"), ("Kaiming He", "MIT"), ("Graham Neubig", "CMU"), ("Ruslan Salakhutdinov", "CMU"),
    ("Zico Kolter", "CMU"), ("Sanjeev Arora", "Princeton"), ("Danqi Chen", "Princeton"),
    ("Luke Zettlemoyer", "University of Washington"), ("Noah A. Smith", "University of Washington"),
    ("Mohit Bansal", "UNC Chapel Hill"), ("Anima Anandkumar", "Caltech"),
    # Europe
    ("Max Welling", "University of Amsterdam"), ("Bernhard Schölkopf", "Max Planck Institute for Intelligent Systems"),
    ("Andreas Krause", "ETH Zurich"), ("Thomas Hofmann", "ETH Zurich"), ("Yee Whye Teh", "University of Oxford"),
    ("Philip Torr", "University of Oxford"), ("Michael Bronstein", "University of Oxford"),
    ("Andrea Vedaldi", "University of Oxford"), ("Shimon Whiteson", "University of Oxford"),
    ("Zoubin Ghahramani", "University of Cambridge"), ("Neil Lawrence", "University of Cambridge"),
    ("Tim Rocktäschel", "UCL"), ("Mirella Lapata", "University of Edinburgh"), ("Ivan Titov", "University of Edinburgh"),
    ("Sepp Hochreiter", "JKU Linz"), ("Jürgen Schmidhuber", "IDSIA / KAUST"), ("Iryna Gurevych", "TU Darmstadt"),
    ("Frank Hutter", "University of Freiburg"), ("Cordelia Schmid", "Inria"), ("Francis Bach", "Inria"),
    ("Volkan Cevher", "EPFL"), ("Martin Jaggi", "EPFL"),
    # Asia, Middle East and Oceania
    ("Maosong Sun", "Tsinghua University"), ("Minlie Huang", "Tsinghua University"),
    ("Zhi-Hua Zhou", "Nanjing University"), ("Jiaya Jia", "HKUST"), ("Dahua Lin", "CUHK"),
    ("Masashi Sugiyama", "University of Tokyo / RIKEN"), ("Yutaka Matsuo", "University of Tokyo"),
    ("Yang You", "National University of Singapore"), ("Dacheng Tao", "Nanyang Technological University"),
    ("Jinwoo Shin", "KAIST"), ("Sung Ju Hwang", "KAIST"), ("Mitesh Khapra", "IIT Madras"),
    ("Soumen Chakrabarti", "IIT Bombay"), ("Yoav Goldberg", "Bar-Ilan University"),
    ("Amnon Shashua", "Hebrew University of Jerusalem"), ("Eric Xing", "MBZUAI"), ("Timothy Baldwin", "MBZUAI"),
    ("Anton van den Hengel", "University of Adelaide"),
]

# Big tech and frontier AI labs. Patterns match a Hugging Face organization or a team author name
# such as "DeepSeek-AI" or "Qwen Team" (case-insensitive).
COMPANIES = {
    "Google": r"\bgoogle|deepmind|gemini team", "Microsoft": r"microsoft",
    "Meta": r"^meta\b|facebook|meta[- ]?(ai|fair|llama)", "Apple": r"\bapple\b", "Amazon": r"amazon|\baws\b",
    "NVIDIA": r"nvidia", "IBM": r"\bibm\b", "Intel": r"^intel\b|intel ?labs", "Qualcomm": r"qualcomm",
    "Salesforce": r"salesforce", "Adobe": r"adobe", "Samsung": r"samsung", "Sony": r"\bsony\b",
    "LG AI Research": r"\blg ?ai|^lgai", "Huawei": r"huawei|noah.?s ark",
    "Alibaba": r"alibaba|qwen|tongyi|damo academy", "Ant Group": r"\bant ?group|inclusionai|antgroup",
    "Tencent": r"tencent|hunyuan", "ByteDance": r"bytedance", "Baidu": r"baidu|\bernie\b", "Xiaomi": r"xiaomi",
    "Kuaishou": r"kuaishou|\bkwai", "Meituan": r"meituan|longcat", "DeepSeek": r"deepseek",
    "Moonshot AI": r"moonshot|kimi team", "Zhipu AI": r"zhipu|z\.ai|glm team", "MiniMax": r"^minimax",
    "StepFun": r"stepfun", "OpenAI": r"openai", "Anthropic": r"anthropic", "xAI": r"^xai\b|xai-org",
    "Mistral AI": r"mistral", "Cohere": r"cohere", "NAVER": r"naver", "Kakao": r"kakao", "Sakana AI": r"sakana",
    "Databricks": r"databricks", "Snowflake": r"snowflake",
}

ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.RO", "cs.CR", "cs.MA", "cs.NE", "cs.IR", "stat.ML"]
ARXIV_ETHICS_CATEGORIES = ["cs.CY", "cs.AI", "cs.HC", "cs.LG", "cs.CL"]


def arxiv_rss_url(categories) -> str:
    return "https://rss.arxiv.org/rss/" + "+".join(categories)


# Each day's new arXiv papers in these categories, kept only when a listed person is an author. (arXiv's
# search API would find them by name, but it refuses requests from cloud servers such as GitHub Actions.)
# The lists are empty on weekends and holidays, when arXiv announces nothing.
SOURCES += [
    {"name": "arXiv", "label": f"arXiv new papers: {len(PROFESSORS)} professors", "format": "arxiv_rss",
     "url": arxiv_rss_url(ARXIV_CATEGORIES), "category": "research", "ai_only": True, "max_age_days": 14,
     "professors": [n for n, _ in PROFESSORS]},
    {"name": "arXiv", "label": f"arXiv new papers: {len(EXPERTS)} scholars", "format": "arxiv_rss",
     "url": arxiv_rss_url(ARXIV_ETHICS_CATEGORIES), "category": "regulation", "ai_only": True, "max_age_days": 14,
     "professors": [n for n, _, _ in EXPERTS], "expert": True},
]

SOURCES += [
    # Papers big tech and frontier labs claim on Hugging Face (listed professors are matched here too).
    {"name": "Hugging Face Daily Papers", "url": "https://huggingface.co/api/daily_papers?limit=100",
     "format": "hf_daily", "category": "research", "ai_only": True, "max_age_days": 7, "companies": True,
     "expect_entries": True},
    # Apple publishes its research papers as a feed.
    {"name": "Apple Machine Learning Research", "url": "https://machinelearning.apple.com/rss.xml",
     "category": "research", "ai_only": True, "max_age_days": 30, "org": "Apple"},
]
