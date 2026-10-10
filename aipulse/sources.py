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
  ai_only       True when every item is about AI (skips the AI keyword filter)
  format        "page_list": a lab with no feed; "link" is the pattern of its posts' addresses on the page
  english_only  skip posts whose headline is in Japanese, Chinese or Korean (a blog posting both languages)
  ai_in_title   True for general feeds where only items with AI in the title count
  max_age_days  look back further than the run default (for feeds that post weekly or monthly)
  max_items     only take the first N entries of each fetch
  pause         seconds to wait after fetching (arXiv asks for 3)
  page_lead     the feed has no real description, so each new post's opening paragraph is read from its page
                (once; robots.txt permitting)
  expect_entries True when the source always lists its latest items, so an empty reply is a glitch:
                it is retried, and counts as a failed fetch if it stays empty
  label         name shown in source health checks when several sources share a name (arXiv)
  jurisdictions regulation sources: codes to use when a story doesn't name a place (e.g. ["EU"])
  government    a government's own publications: always Policy (or the tracker for a bill or law), never
                Industry or Releases, however little the text sounds like government
  no_releases   a practitioner's or evaluator's blog: its posts are never Releases, however much they read like a
                launch (they comment on others' launches)
  lab           "github_repos", "hf_models" and the labs' APIs: the lab's name in headlines ("Qwen publishes
                Qwen-Image-2.1 on GitHub")
  key_env       the environment variable holding the project's API key for the source; skipped when unset
  skip          a pattern: posts whose headline matches it are never stories (Midjourney's weekly changelogs)
  paged         the feed pages back in time (WordPress: ?paged=2, 3, ...); the history run reads it back to 2023

Policy stories from any source move to the regulation tracker when they report a proposal or an
adopted law in a recognisable country; see collect.apply_regulation.

Add, remove or edit entries freely. Any RSS 2.0 or Atom feed works, as long as the site allows automated
access (its robots.txt and terms): Google News and Bing News don't, so neither is used.
"""

# Every source below was checked (September 2026; every terms page audited again on 7 Oct 2026): its robots.txt
# allows fetching it and its terms don't restrict showing headlines with a short description and a link. Feeds that
# forbid that (BBC News: no modified feeds) or whose terms couldn't be confirmed (NYT, The Guardian, Wired) are left out.
# Dropped in the 7 Oct 2026 audit, their terms forbidding robots or allowing personal use only (collect.DROPPED):
# SCMP, MIT Technology Review, The Verge, Ars Technica, Tech Xplore, The Rio Times, Semiconductor Digest, ServeTheHome,
# Data Centre Review, Capacity Media, iTnews, ESI Africa, ZDNET and Energy Monitor. The labs' and companies' own blogs
# dropped then are back since 10 Oct 2026 under the owner's rule for them: robots.txt decides. Each source's evidence
# (terms page, what it says, date checked) is in terms.py; `python -m aipulse audit` checks them all again. "as_provided": the feed's terms
# allow its text only unmodified.
GITHUB_ORG = "https://api.github.com/orgs/{}/repos?sort=created&direction=desc&per_page=100&type=public"
GITHUB_REPO = r"^https://github\.com/"  # every new repository that passes the star test is a release (collect.blog_category)
HF_ORG = "https://huggingface.co/api/models?author={}&sort=likes&direction=-1&limit=500"
HF_MODEL = r"^https://huggingface\.co/"  # every model family that passes the likes test is a release

SOURCES = [
    # --- Labs and product blogs (mostly releases) ---
    {"name": "Google AI Blog", "url": "https://blog.google/technology/ai/rss/", "category": "tool"},
    {"name": "Google DeepMind Blog", "url": "https://deepmind.google/blog/rss.xml", "category": "tool"},
    {"name": "Google Research Blog", "url": "https://research.google/blog/rss/", "category": "tool", "page_lead": True},
    {"name": "Mistral AI", "url": "https://mistral.ai/rss.xml", "category": "tool"},
    {"name": "Cloudflare Blog", "url": "https://blog.cloudflare.com/tag/ai/rss/", "category": "tool"},
    {"name": "Sakana AI", "url": "https://sakana.ai/feed.xml", "category": "tool", "english_only": True},
    # Added 7 Oct 2026 (evidence in terms.py): PyTorch's blog is the Linux Foundation's, CC BY; Together AI's and
    # ElevenLabs' terms say nothing against reading their feeds.
    {"name": "PyTorch Blog", "url": "https://pytorch.org/blog/feed.xml", "category": "tool"},
    {"name": "Together AI", "url": "https://www.together.ai/blog/rss.xml", "category": "tool"},
    {"name": "ElevenLabs", "url": "https://elevenlabs.io/blog/rss.xml", "category": "tool"},
    # Labs with no feed: their news page lists posts; each new post's page is read once (collect.page_list_entries).
    {"name": "MiniMax", "url": "https://www.minimax.io/news", "format": "page_list",
     "link": r"^https://www\.minimax\.io/(?:news|blog)/[a-z0-9-]+$", "category": "tool"},
    # Added 10 Oct 2026 for the labs whose launches reached us only through news outlets. The owner's rule for AI
    # labs' and companies' own blogs (10 Oct 2026): robots.txt decides, and a site without one may be read
    # (terms.py "robots.txt").
    {"name": "Sarvam AI", "url": "https://www.sarvam.ai/rss.xml", "category": "tool"},
    # Gemini's own section of Google's blog: model launches (Gemini 4 Argon) and the Gemini app's features, which the
    # AI feed above leaves out
    {"name": "Google Gemini Blog", "url": "https://blog.google/products/gemini/rss/", "category": "tool"},
    # Runway (now runway.com): its sitemap lists its posts; the section pages (/news/customers ...) aren't posts
    {"name": "Runway", "url": "https://runwayml.com/sitemap.xml", "format": "page_list", "category": "tool",
     "link": r"^https://runway\.com/(?:news/(?!(?:customers|company-news|safety|research|engineering|developers)$)"
             r"|research/(?!(?:publications|rna-sessions)$))[a-z0-9-]+$"},
    {"name": "Google Cloud Blog (AI)", "url": "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/",
     "category": "tool"},
    {"name": "Thinking Machines", "url": "https://thinkingmachines.ai/blog/index.xml", "category": "tool",
     "max_age_days": 60},  # a few posts a year
    {"name": "Midjourney", "url": "https://updates.midjourney.com/rss/", "category": "tool",
     "skip": r"(?i)^alpha changelog\b"},  # its weekly changelogs aren't launches
    # Its feed gives no dates, so its blog page is read like a lab without a feed (each post's page has its date).
    {"name": "Google Developers Blog", "url": "https://developers.googleblog.com/", "format": "page_list",
     "link": r"^https://developers\.googleblog\.com/[a-z0-9][a-z0-9-]{8,}/$", "category": "tool"},
    {"name": "Black Forest Labs", "url": "https://bfl.ai/blog", "format": "page_list",
     "link": r"^https://bfl\.ai/blog/[a-z0-9-]+$", "category": "tool"},
    {"name": "Liquid AI", "url": "https://www.liquid.ai/blog", "format": "page_list",
     "link": r"^https://www\.liquid\.ai/blog/[a-z0-9-]+$", "category": "tool"},
    {"name": "Reflection AI", "url": "https://reflection.ai/blog", "format": "page_list",
     "link": r"^https://reflection\.ai/blog/[a-z0-9-]+$", "category": "tool"},
    {"name": "Cognition", "url": "https://cognition.ai/blog", "format": "page_list",
     "link": r"^https://cognition\.ai/blog/[a-z0-9-]+$", "category": "tool"},
    {"name": "Poolside", "url": "https://poolside.ai/blog", "format": "page_list",
     "link": r"^https://poolside\.ai/blog/[a-z0-9-]+$", "category": "tool"},
    {"name": "Reka", "url": "https://reka.ai/news", "format": "page_list",
     "link": r"^https://reka\.ai/news/[a-z0-9-]+$", "category": "tool"},
    {"name": "Figure", "url": "https://www.figure.ai/news", "format": "page_list",
     "link": r"^https://www\.figure\.ai/news/[a-z0-9-]+$", "category": "tool"},
    # The labs' and companies' own blogs dropped in the 7 Oct 2026 audit, back on 10 Oct 2026 (robots.txt allows each).
    {"name": "OpenAI News", "url": "https://openai.com/news/rss.xml", "category": "tool"},
    # No feed: its news page. Launches have their own page (/claude-sonnet-5-5), other posts are under /news/.
    {"name": "Anthropic News", "url": "https://www.anthropic.com/news", "format": "anthropic", "category": "tool",
     "page_lead": True, "max_age_days": 90, "launch_pages": r"^https://www\.anthropic\.com/(?!news/)"},
    {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml", "category": "tool", "page_lead": True},
    {"name": "Microsoft Research", "url": "https://www.microsoft.com/en-us/research/feed/", "category": "tool",
     "ai_only": False, "paged": True},
    {"name": "NVIDIA Blog", "url": "https://blogs.nvidia.com/feed/", "category": "tool", "ai_only": False,
     "ai_in_title": True, "paged": True},
    {"name": "AWS Machine Learning Blog", "url": "https://aws.amazon.com/blogs/machine-learning/feed/", "category": "tool"},
    {"name": "Engineering at Meta", "url": "https://engineering.fb.com/feed/", "category": "tool", "ai_only": False,
     "ai_in_title": True, "paged": True},
    {"name": "GitHub Blog", "url": "https://github.blog/ai-and-ml/feed/", "category": "tool"},
    {"name": "Databricks Blog", "url": "https://www.databricks.com/feed", "category": "tool", "ai_only": False},
    {"name": "Ollama Blog", "url": "https://ollama.com/blog/rss.xml", "category": "tool"},
    {"name": "Character.AI", "url": "https://blog.character.ai/rss/", "category": "tool"},
    {"name": "Stability AI", "url": "https://stability.ai/news-updates?format=rss", "category": "tool"},
    {"name": "DeepSeek", "url": "https://api-docs.deepseek.com/sitemap.xml", "format": "page_list",
     "link": r"^https://api-docs\.deepseek\.com/news/news\d+$", "category": "tool"},
    {"name": "Meta AI", "url": "https://ai.meta.com/blog/", "format": "page_list",
     "link": r"^https://ai\.meta\.com/blog/[a-z0-9-]+/$", "category": "tool"},
    {"name": "Cohere", "url": "https://cohere.com/blog", "format": "page_list",
     "link": r"^https://cohere\.com/blog/[a-z0-9-]+$", "category": "tool"},
    {"name": "Moonshot AI (Kimi)", "url": "https://www.moonshot.ai/news", "format": "page_list",
     "link": r"^https://www\.kimi\.ai/blog/[a-z0-9-]+$", "category": "tool"},
    # Labs whose news pages block automated readers: their developer release notes (robots.txt allows them),
    # keeping only launches of their own products ("keep").
    {"name": "xAI", "url": "https://docs.x.ai/developers/release-notes", "format": "page_list", "notes": "xai_notes",
     "keep": r"^(?:Grok|SpaceXAI|xAI)\b", "category": "tool"},
    {"name": "Perplexity", "url": "https://docs.perplexity.ai/changelog", "format": "page_list",
     "notes": "perplexity_notes", "keep": r"\b(?:Perplexity|Sonar|Comet)\b", "category": "tool"},
    # Company-wide newsrooms: only their stories that name AI in the headline.
    {"name": "Microsoft", "url": "https://blogs.microsoft.com/feed/", "category": "tool", "ai_only": False,
     "ai_in_title": True},
    {"name": "Meta Newsroom", "url": "https://about.fb.com/feed/", "category": "tool", "ai_only": False,
     "ai_in_title": True},
    {"name": "Amazon", "url": "https://www.aboutamazon.com/rss/news.xml", "category": "tool", "ai_only": False,
     "ai_in_title": True},
    {"name": "Apple Newsroom", "url": "https://www.apple.com/newsroom/rss-feed.rss", "category": "tool",
     "ai_only": False, "ai_in_title": True},
    # Labs' new open models and tools, from their GitHub organisations through GitHub's API, whose terms allow it
    # (terms.py; the labs' own sites may not be read: OpenAI, Anthropic, Meta, Hugging Face, NVIDIA, DeepSeek...).
    # Only repositories 300+ people starred, back to 2023 (feeds.parse_github_repos); github.com pages are never read.
    {"name": "OpenAI on GitHub", "lab": "OpenAI", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("openai"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "Anthropic on GitHub", "lab": "Anthropic", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("anthropics"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "Meta Llama on GitHub", "lab": "Meta Llama", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("meta-llama"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "Hugging Face on GitHub", "lab": "Hugging Face", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("huggingface"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "NVIDIA on GitHub", "lab": "NVIDIA", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("nvidia"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "Mistral AI on GitHub", "lab": "Mistral AI", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("mistralai"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "xAI on GitHub", "lab": "xAI", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("xai-org"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "DeepSeek on GitHub", "lab": "DeepSeek", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("deepseek-ai"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "Qwen on GitHub", "lab": "Qwen", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("QwenLM"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "Moonshot AI on GitHub", "lab": "Moonshot AI", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("MoonshotAI"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "MiniMax on GitHub", "lab": "MiniMax", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("MiniMax-AI"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "Z.ai on GitHub", "lab": "Z.ai", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("zai-org"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "StepFun on GitHub", "lab": "StepFun", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("stepfun-ai"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "Tencent Hunyuan on GitHub", "lab": "Tencent Hunyuan", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("Tencent-Hunyuan"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "ByteDance Seed on GitHub", "lab": "ByteDance Seed", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("ByteDance-Seed"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "Baidu on GitHub", "lab": "Baidu", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("baidu"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    {"name": "Ant Group (inclusionAI) on GitHub", "lab": "Ant Group", "format": "github_repos", "category": "tool",
     "url": GITHUB_ORG.format("inclusionAI"), "max_age_days": 1400, "launch_pages": GITHUB_REPO},
    # Labs' open models, from their Hugging Face organisations through its public API (the terms of huggingface.co
    # don't restrict it; terms.py). One story per release (its sizes and variants together), only releases 300+
    # people liked, back to 2023 (feeds.parse_hf_models).
    {"name": "OpenAI on Hugging Face", "lab": "OpenAI", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("openai"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Meta Llama on Hugging Face", "lab": "Meta Llama", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("meta-llama"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Meta on Hugging Face", "lab": "Meta", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("facebook"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Google on Hugging Face", "lab": "Google", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("google"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Microsoft on Hugging Face", "lab": "Microsoft", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("microsoft"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "NVIDIA on Hugging Face", "lab": "NVIDIA", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("nvidia"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Apple on Hugging Face", "lab": "Apple", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("apple"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Amazon on Hugging Face", "lab": "Amazon", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("amazon"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "IBM Granite on Hugging Face", "lab": "IBM Granite", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("ibm-granite"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Mistral AI on Hugging Face", "lab": "Mistral AI", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("mistralai"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "xAI on Hugging Face", "lab": "xAI", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("xai-org"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "DeepSeek on Hugging Face", "lab": "DeepSeek", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("deepseek-ai"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Qwen on Hugging Face", "lab": "Qwen", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("Qwen"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Moonshot AI on Hugging Face", "lab": "Moonshot AI", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("moonshotai"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "MiniMax on Hugging Face", "lab": "MiniMax", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("MiniMaxAI"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Z.ai on Hugging Face", "lab": "Z.ai", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("zai-org"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "StepFun on Hugging Face", "lab": "StepFun", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("stepfun-ai"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Tencent on Hugging Face", "lab": "Tencent", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("tencent"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "ByteDance Seed on Hugging Face", "lab": "ByteDance Seed", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("ByteDance-Seed"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Baidu on Hugging Face", "lab": "Baidu", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("baidu"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Ant Group (inclusionAI) on Hugging Face", "lab": "Ant Group", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("inclusionAI"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Cohere Labs on Hugging Face", "lab": "Cohere Labs", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("CohereLabs"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Hugging Face on Hugging Face", "lab": "Hugging Face", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("HuggingFaceTB"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Black Forest Labs on Hugging Face", "lab": "Black Forest Labs", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("black-forest-labs"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Stability AI on Hugging Face", "lab": "Stability AI", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("stabilityai"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Ai2 on Hugging Face", "lab": "Ai2", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("allenai"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Liquid AI on Hugging Face", "lab": "Liquid AI", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("LiquidAI"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    # Added 10 Oct 2026: more labs whose open models people like (same API, same 300+ likes test)
    {"name": "Xiaomi MiMo on Hugging Face", "lab": "Xiaomi MiMo", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("XiaomiMiMo"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Aleph Alpha on Hugging Face", "lab": "Aleph Alpha", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("Aleph-Alpha"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Sarvam AI on Hugging Face", "lab": "Sarvam AI", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("sarvamai"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Nous Research on Hugging Face", "lab": "Nous Research", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("NousResearch"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Kyutai on Hugging Face", "lab": "Kyutai", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("kyutai"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "AI21 Labs on Hugging Face", "lab": "AI21 Labs", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("ai21labs"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "OpenBMB on Hugging Face", "lab": "OpenBMB", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("openbmb"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "LG AI Research on Hugging Face", "lab": "LG AI Research", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("LGAI-EXAONE"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Upstage on Hugging Face", "lab": "Upstage", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("upstage"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Meituan LongCat on Hugging Face", "lab": "Meituan LongCat", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("meituan-longcat"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Lightricks on Hugging Face", "lab": "Lightricks", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("Lightricks"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Wan (Alibaba) on Hugging Face", "lab": "Wan (Alibaba)", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("Wan-AI"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "TII Falcon on Hugging Face", "lab": "TII Falcon", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("tiiuae"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Salesforce on Hugging Face", "lab": "Salesforce", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("Salesforce"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "ServiceNow on Hugging Face", "lab": "ServiceNow", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("ServiceNow-AI"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Prime Intellect on Hugging Face", "lab": "Prime Intellect", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("PrimeIntellect"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Nari Labs on Hugging Face", "lab": "Nari Labs", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("nari-labs"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Sesame on Hugging Face", "lab": "Sesame", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("sesame"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Resemble AI on Hugging Face", "lab": "Resemble AI", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("ResembleAI"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    {"name": "Swiss AI on Hugging Face", "lab": "Swiss AI", "format": "hf_models", "category": "tool",
     "url": HF_ORG.format("swiss-ai"), "max_age_days": 1400, "launch_pages": HF_MODEL},
    # The labs' own model lists, through their APIs with the project's free keys (their terms allow access through
    # the API; terms.py): every model they serve, closed ones too. Skipped until the key is set (feeds.API_KEYS).
    {"name": "Anthropic API models", "lab": "Anthropic", "format": "anthropic_models", "category": "tool",
     "url": "https://api.anthropic.com/v1/models?limit=1000", "key_env": "ANTHROPIC_API_KEY", "max_age_days": 1400,
     "launch_pages": r"^https://docs\.claude\.com/"},
    {"name": "OpenAI API models", "lab": "OpenAI", "format": "openai_models", "category": "tool",
     "url": "https://api.openai.com/v1/models", "key_env": "OPENAI_API_KEY", "max_age_days": 1400,
     "launch_pages": r"^https://platform\.openai\.com/docs/models/"},

    # --- Industry news ---
    {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/", "category": "news",
     "paged": True, "as_provided": True},
    {"name": "The Decoder", "url": "https://the-decoder.com/feed/", "category": "news", "paged": True},
    {"name": "SiliconANGLE AI", "url": "https://siliconangle.com/category/ai/feed/", "category": "news", "paged": True},
    {"name": "MarkTechPost", "url": "https://www.marktechpost.com/feed/", "category": "news", "ai_only": True, "paged": True},
    {"name": "404 Media", "url": "https://www.404media.co/rss/", "category": "news"},
    # Added 7 Oct 2026: The Conversation (Creative Commons BY-ND), Quanta Magazine (no terms restrict it)
    {"name": "The Conversation (AI)", "url": "https://theconversation.com/global/topics/artificial-intelligence-ai-90/articles.atom",
     "category": "news", "ai_only": True},
    {"name": "Quanta Magazine", "url": "https://www.quantamagazine.org/feed/", "category": "news", "ai_in_title": True},
    {"name": "Engadget", "url": "https://www.engadget.com/rss.xml", "category": "news", "ai_in_title": True,
     "as_provided": True},
    {"name": "MIT News", "url": "https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml", "category": "news",
     "ai_only": True},
    # Its AI section also carries quantum computing, robotics and other science: each story must name AI.
    {"name": "ScienceDaily", "url": "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml",
     "category": "news", "as_provided": True, "keep_max": 40},  # its RSS terms: about 40 stored headlines at most
    # Beyond the US: Asia, Africa and the rest of the world.
    {"name": "TechCabal", "url": "https://techcabal.com/feed/", "category": "news", "paged": True},
    # China's AI labs and launches (DeepSeek, Qwen, Kimi...)
    {"name": "Pandaily", "url": "https://pandaily.com/feed/", "category": "news"},
    {"name": "iAfrikan", "url": "https://www.iafrikan.com/rss/", "category": "news"},
    # Regional news, so countries without an official source still show up. None has terms restricting
    # its feed; VnExpress's feed terms allow free use by individuals and non-profits with the source named.
    {"name": "Focus Taiwan", "url": "https://feeds.feedburner.com/rsscna/engnews/", "category": "news", "ai_in_title": True},
    {"name": "Bernama", "url": "https://www.bernama.com/en/rssfeed.php", "category": "news", "ai_in_title": True},
    {"name": "VnExpress International", "url": "https://e.vnexpress.net/rss/news.rss", "category": "news", "ai_in_title": True},
    # Added 10 Oct 2026 (regional search): Korea and Japan in English; their terms reserve copyright but ban neither
    # robots nor anything beyond personal use (terms.py)
    {"name": "The Elec", "url": "https://www.thelec.net/rss/allArticle.xml", "category": "news", "ai_in_title": True},
    {"name": "BusinessKorea", "url": "https://www.businesskorea.co.kr/rss/allArticle.xml", "category": "news", "ai_in_title": True,
     "english_only": True},  # its feed is mostly Korean
    {"name": "BRIDGE", "url": "https://thebridge.jp/en/feed", "category": "news", "ai_in_title": True},
    {"name": "TechCentral", "url": "https://techcentral.co.za/feed/", "category": "news", "ai_in_title": True},
    {"name": "ITWeb", "url": "https://www.itweb.co.za/rss", "category": "news", "ai_in_title": True},
    {"name": "Wamda", "url": "https://www.wamda.com/feed", "category": "news", "ai_in_title": True},
    # Global Voices (Creative Commons BY): citizen reporting from around the world
    {"name": "Global Voices", "url": "https://globalvoices.org/-/topics/technology/feed/", "category": "news", "ai_in_title": True},
    {"name": "MercoPress", "url": "https://en.mercopress.com/rss/", "category": "news", "ai_in_title": True},
    # Latin America
    {"name": "Buenos Aires Times", "url": "https://www.batimes.com.ar/feed", "category": "news", "ai_in_title": True},
    {"name": "LatinAmerica Reports", "url": "https://latinamericareports.com/feed/", "category": "news", "ai_in_title": True},
    {"name": "Contxto", "url": "https://contxto.com/en/feed/", "category": "news", "ai_in_title": True},  # added 10 Oct 2026
    # Africa
    {"name": "IT News Africa", "url": "https://www.itnewsafrica.com/feed/", "category": "news", "ai_in_title": True},
    {"name": "Nairametrics", "url": "https://nairametrics.com/feed/", "category": "news", "ai_in_title": True},
    # Added from the sources review (6 Oct 2026): robots.txt allows each feed and no terms forbid headlines with a short
    # description and a link.
    # Practitioners and evaluators
    {"name": "Simon Willison", "url": "https://simonwillison.net/atom/entries/", "category": "news", "no_releases": True},
    {"name": "Lil'Log", "url": "https://lilianweng.github.io/index.xml", "category": "news", "ai_only": True,
     "max_age_days": 60, "no_releases": True},  # a few long posts a year
    {"name": "METR", "url": "https://metr.org/feed.xml", "category": "news", "ai_only": True, "no_releases": True},

    # --- Infra & climate: AI's data centres and what they draw on (power, water, land, emissions) ---
    # Checked 3 Oct 2026: each robots.txt allows reading and each publishes this feed; articles are free to read.
    # Out: IRENA, Japan's METI, BNamericas, Dialogue Earth and the IEA (robots.txt disallows; the IEA's, from GitHub's
# servers, 6 Oct 2026); WRI, Ireland's CSO, AEMO and
    # Data Center Dynamics (bot checks); Eco-Business (its articles are marked subscriber-only). Only stories about
    # AI's infrastructure are kept (classify.is_infra).
    # Data-centre trade news, by region
    {"name": "Data Center Knowledge", "url": "https://www.datacenterknowledge.com/rss.xml", "category": "infra", "infra_filter": True},
    {"name": "W.Media", "url": "https://w.media/feed/", "category": "infra", "infra_filter": True, "paged": True},  # Asia-Pacific
    # Energy, climate and environment newsrooms, worldwide
    {"name": "Carbon Brief", "url": "https://www.carbonbrief.org/feed/", "category": "infra", "infra_filter": True, "paged": True},
    {"name": "Climate Home News", "url": "https://www.climatechangenews.com/feed/", "category": "infra", "infra_filter": True,
     "paged": True},
    {"name": "Mongabay", "url": "https://news.mongabay.com/feed/", "category": "infra", "infra_filter": True, "paged": True},
    {"name": "The Conversation (Energy)", "url": "https://theconversation.com/global/topics/energy-72/articles.atom",
     "category": "infra", "infra_filter": True},
    {"name": "Canary Media", "url": "https://www.canarymedia.com/rss", "category": "infra", "infra_filter": True},  # North America
    # Added 7 Oct 2026 for history back to 2023: each robots.txt allows reading; POWER's terms and UCS's pages say nothing
    # against feeds or automated reading. Out: Grist (RSS for private use only), Inside Climate News (no automatic
    # republishing), Uptime Institute (no republishing), Latitude Media (robots.txt disallows).
    {"name": "POWER Magazine", "url": "https://www.powermag.com/category/data-centers/feed/", "category": "infra",
     "infra_filter": True, "paged": True},  # North America: power for data centres
    {"name": "Union of Concerned Scientists", "url": "https://blog.ucsusa.org/feed/", "category": "infra",
     "infra_filter": True, "paged": True},  # North America
    # Added 7 Oct 2026 for AI's environmental impact and wider data-centre coverage (evidence in terms.py): the Union of
    # Concerned Scientists' whole blog (it replaces its data-centre tag), environmental groups and research, and
    # data-centre trade news in the UK, the US and Africa.
    {"name": "Southern Environmental Law Center", "url": "https://www.selc.org/news/feed/", "category": "infra",
     "infra_filter": True, "paged": True},  # US South: data centres' gas turbines and pollution
    {"name": "Food & Water Watch", "url": "https://www.foodandwaterwatch.org/feed/", "category": "infra", "infra_filter": True,
     "paged": True},
    {"name": "Energy Innovation", "url": "https://energyinnovation.org/feed/", "category": "infra", "infra_filter": True,
     "paged": True},
    {"name": "Greenpeace International", "url": "https://www.greenpeace.org/international/feed/", "category": "infra",
     "infra_filter": True, "paged": True},
    {"name": "Global Energy Monitor", "url": "https://globalenergymonitor.org/rss.xml", "category": "infra", "infra_filter": True},
    {"name": "Data Center POST", "url": "https://datacenterpost.com/feed/", "category": "infra", "infra_filter": True,
     "paged": True},
    {"name": "Techerati", "url": "https://www.techerati.com/feed/", "category": "infra", "infra_filter": True, "paged": True},
    {"name": "DCNN", "url": "https://dcnnmagazine.com/feed/", "category": "infra", "infra_filter": True, "paged": True},  # UK
    {"name": "Africa Data Centres Association", "url": "https://africadca.org/en/feed", "category": "infra",
     "infra_filter": True},
    # Official energy bodies
    # GOV.UK's search for data centres (Open Government Licence v3.0): planning directions, environmental permits,
    # statistics and announcements since 2023. Only news and official records: never pages about a person or
    # tribunal decisions, which name private individuals.
    {"name": "GOV.UK (data centres)", "format": "govuk", "category": "infra", "infra_filter": True, "jurisdictions": ["GB"],
     "max_age_days": 1400,
     "url": "https://www.gov.uk/api/search.json?q=%22data+centre%22&order=-public_timestamp&count=1000"
            "&fields=title,link,description,public_timestamp&filter_public_timestamp=from:2023-01-01"
            + "".join(f"&filter_content_store_document_type={t}" for t in (
                "press_release", "news_story", "speech", "notice", "decision", "research", "official_statistics",
                "national_statistics", "policy_paper", "open_consultation", "closed_consultation", "consultation_outcome",
                "detailed_guide", "guidance"))},
    {"name": "US Energy Information Administration", "url": "https://www.eia.gov/rss/press_rss.xml", "category": "infra",
     "infra_filter": True},
    {"name": "European Commission (Energy)", "url": "https://energy.ec.europa.eu/node/2/rss_en", "category": "infra",
     "infra_filter": True},

    # --- Policy and politics ---
    # The newsletter's Substack feed sits behind a Cloudflare check that blocks cloud servers (GitHub Actions);
    # the publisher's own site feed carries its explainers and analysis.
    {"name": "EU AI Act Newsletter", "url": "https://artificialintelligenceact.eu/feed/", "category": "policy"},
    {"name": "CSET", "url": "https://cset.georgetown.edu/feed/", "category": "policy", "ai_only": True, "paged": True},
    {"name": "AI Now Institute", "url": "https://ainowinstitute.org/feed", "category": "policy", "ai_only": True,
     "paged": True},
    {"name": "Future of Life Institute", "url": "https://futureoflife.org/feed/", "category": "policy", "ai_only": True},
    {"name": "EFF", "url": "https://www.eff.org/rss/updates.xml", "category": "policy", "ai_in_title": True},
    {"name": "EPIC", "url": "https://epic.org/feed/", "category": "policy", "paged": True},
    # Added from the sources review (6 Oct 2026). ITU allows non-commercial use with credit (itu.int terms of use).
    {"name": "CLTC (UC Berkeley)", "url": "https://cltc.berkeley.edu/feed/", "category": "policy"},
    {"name": "ITU", "url": "https://www.itu.int/hub/feed/", "category": "policy"},
    # Added 7 Oct 2026: Partnership on AI and Smart Africa (no terms restrict their feeds)
    {"name": "Partnership on AI", "url": "https://partnershiponai.org/feed/", "category": "policy", "ai_only": True},
    {"name": "Smart Africa", "url": "https://smartafrica.org/feed/", "category": "policy", "ai_in_title": True},
    # Governments' own publications (US federal records and GOV.UK are public-domain / Open Government Licence).
    {"name": "NIST", "url": "https://www.nist.gov/news-events/news/rss.xml", "category": "policy", "jurisdictions": ["US"],
     "government": True},
    # Added 7 Oct 2026 (US public domain): AI policy at the commerce department's telecoms agency (CISA, added the same day, was dropped: it
    # refuses even its robots.txt to GitHub's servers)
    {"name": "NTIA", "url": "https://www.ntia.gov/rss.xml", "category": "policy", "jurisdictions": ["US"],
     "ai_in_title": True, "government": True},
    {"name": "DARPA", "url": "https://www.darpa.mil/rss/news.xml", "category": "policy", "jurisdictions": ["US"],
     "government": True},
    {"name": "NSF", "url": "https://www.nsf.gov/rss/rss_www_news.xml", "category": "policy", "jurisdictions": ["US"],
     "government": True},
    # No feed: its blog page lists every post (a UK government body, Open Government Licence)
    {"name": "UK AI Security Institute", "url": "https://www.aisi.gov.uk/blog", "format": "page_list",
     "link": r"^https://www\.aisi\.gov\.uk/blog/[a-z0-9-]+$", "category": "policy", "ai_only": True,
     "jurisdictions": ["GB"], "government": True},
    {"name": "Federal Register", "format": "federal_register", "category": "policy", "jurisdictions": ["US"],
     "ai_in_title": True, "government": True,
     "url": "https://www.federalregister.gov/api/v1/documents.json?conditions%5Bterm%5D=%22artificial+intelligence%22"
            "&order=newest&per_page=50&fields%5B%5D=title&fields%5B%5D=html_url&fields%5B%5D=abstract"
            "&fields%5B%5D=publication_date"},
    # South Korea: the Ministry of Science and ICT runs the AI Basic Act; its English press releases carry the
    # country's AI rules as they're announced. (The National Assembly's bill API needs a key only available
    # with Korean identity verification, so Korean bills aren't tracked.)
    {"name": "Ministry of Science and ICT (Korea)", "format": "msit", "category": "policy", "jurisdictions": ["KR"],
     "ai_in_title": True, "government": True, "paged": True, "page_param": "pageIndex", "page_lead": True,
     "url": "https://www.msit.go.kr/eng/bbs/list.do?sCode=eng&mPid=2&mId=4"},
    # Malaysia: the Ministry of Digital (its National AI Office drafts the AI Governance Bill). Its English
    # media releases; no robots.txt or terms restrict them. The list is short, so older releases are kept.
    {"name": "Ministry of Digital (Malaysia)", "format": "digital_my", "category": "policy", "jurisdictions": ["MY"],
     "ai_in_title": True, "government": True, "max_age_days": 400, "url": "https://www.digital.gov.my/en-GB/siaran"},
    # Russia: the State Duma's English news (its bill search is closed to robots, and the Duma API needs
    # tokens). No terms restrict the news list; only items with AI in the headline are kept.
    {"name": "State Duma (Russia)", "format": "duma_en", "category": "policy", "jurisdictions": ["RU"],
     "ai_in_title": True, "government": True, "max_age_days": 400, "url": "http://duma.gov.ru/en/news/"},
    # Canada: Innovation, Science and Economic Development Canada, the department with the Minister of AI. Its news
    # releases from the Government of Canada's news API (no robots.txt rules; canada.ca's terms allow
    # non-commercial reproduction with credit); only those with AI in the headline are kept.
    {"name": "Innovation, Science and Economic Development Canada", "category": "policy", "jurisdictions": ["CA"],
     "ai_in_title": True, "government": True,
     "url": "https://api.io.canada.ca/io-server/gc/news/en/v2?dept=departmentofindustry&type=newsreleases"
            "&sort=publishedDate&orderBy=desc&pick=50&format=atom&atomtitle=ISED"},
    {"name": "GOV.UK", "format": "govuk", "category": "policy", "jurisdictions": ["GB"], "ai_in_title": True,
     "government": True,
     "url": "https://www.gov.uk/api/search.json?q=%22artificial+intelligence%22&order=-public_timestamp&count=50"
            "&fields=title,link,description,public_timestamp"},
]

# --- Regulation tracker: proposals and adopted laws ---
_REG = {"category": "regulation"}
SOURCES += [
    {**_REG, "name": "European Data Protection Board", "url": "https://www.edpb.europa.eu/feed/news_en",
     "jurisdictions": ["EU"]},
    {**_REG, "name": "European Commission: Digital Strategy", "url": "https://digital-strategy.ec.europa.eu/en/rss.xml",
     "jurisdictions": ["EU"]},
]

# --- Research: AI ethics, philosophy and law scholars, followed daily ---
# Their arXiv papers are picked up by the author matching further down, and filed under Research (a paper
# isn't a bill or a law), tagged with the scholar and their field.
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

# Where each listed scholar works (the country of their institution), so the Research stream can be filtered
# by region like the others: a paper counts where its scholar, or its company (classify.COMPANY_HOME), is based.
INSTITUTION_COUNTRY = {
    "Mila / Université de Montréal": "Canada", "McGill / Mila": "Canada", "University of Toronto": "Canada",
    "University of Alberta": "Canada", "NYU": "United States", "Stanford": "United States",
    "UC Berkeley": "United States", "MIT": "United States", "CMU": "United States",
    "Princeton": "United States", "University of Washington": "United States", "UNC Chapel Hill": "United States",
    "Caltech": "United States", "Yale": "United States", "Carnegie Mellon": "United States",
    "DAIR": "United States", "Hugging Face": "United States", "USC / Microsoft Research": "United States",
    "Humane Intelligence": "United States", "Cornell": "United States", "University of Virginia": "United States",
    "University of Colorado": "United States", "Boston University": "United States", "Columbia": "United States",
    "Harvard": "United States", "Johns Hopkins": "United States", "USC": "United States",
    "Duke": "United States", "CSET, Georgetown": "United States", "Carnegie Endowment": "United States",
    "University of Amsterdam": "Netherlands", "Max Planck Institute for Intelligent Systems": "Germany", "ETH Zurich": "Switzerland",
    "University of Oxford": "United Kingdom", "University of Cambridge": "United Kingdom", "UCL": "United Kingdom",
    "University of Edinburgh": "United Kingdom", "LSE": "United Kingdom", "Oxford Internet Institute": "United Kingdom",
    "Newcastle University": "United Kingdom", "Google DeepMind": "United Kingdom", "JKU Linz": "Austria",
    "University of Vienna": "Austria", "IDSIA / KAUST": "Switzerland", "TU Darmstadt": "Germany",
    "University of Freiburg": "Germany", "Hertie School": "Germany", "TU Munich": "Germany",
    "Inria": "France", "EPFL": "Switzerland", "Umeå University": "Sweden",
    "Trinity College Dublin": "Ireland", "Vrije Universiteit Brussel": "Belgium", "Tsinghua University": "China",
    "Nanjing University": "China", "HKUST": "Hong Kong", "CUHK": "Hong Kong",
    "University of Tokyo / RIKEN": "Japan", "University of Tokyo": "Japan", "National University of Singapore": "Singapore",
    "Nanyang Technological University": "Singapore", "KAIST": "South Korea", "IIT Madras": "India",
    "IIT Bombay": "India", "Bar-Ilan University": "Israel", "Hebrew University of Jerusalem": "Israel",
    "MBZUAI": "United Arab Emirates", "University of Adelaide": "Australia", "Australian National University": "Australia",
}
SCHOLAR_HOME = {name: INSTITUTION_COUNTRY[place] for name, place in PROFESSORS}
SCHOLAR_HOME |= {name: INSTITUTION_COUNTRY[place] for name, _, place in EXPERTS}

# Big tech and frontier AI labs. Patterns match a Hugging Face organization or a team author name
# such as "DeepSeek-AI" or "Qwen Team" (case-insensitive). Names are spelled as the news tags spell them
# (classify.COMPANY_TERMS), so a company is one tag on the site and one choice for readers.
COMPANIES = {
    "Google": r"\bgoogle|deepmind|gemini team", "Microsoft": r"microsoft",
    "Meta": r"^meta\b|facebook|meta[- ]?(ai|fair|llama)", "Apple": r"\bapple\b", "Amazon": r"amazon|\baws\b",
    "Nvidia": r"nvidia", "IBM": r"\bibm\b", "Intel": r"^intel\b|intel ?labs", "Qualcomm": r"qualcomm",
    "Salesforce": r"salesforce", "Adobe": r"adobe", "Samsung": r"samsung", "Sony": r"\bsony\b",
    "LG AI Research": r"\blg ?ai|^lgai", "Huawei": r"huawei|noah.?s ark",
    "Alibaba": r"alibaba|qwen|tongyi|damo academy", "Ant Group": r"\bant ?group|inclusionai|antgroup",
    "Tencent": r"tencent|hunyuan", "ByteDance": r"bytedance", "Baidu": r"baidu|\bernie\b", "Xiaomi": r"xiaomi",
    "Kuaishou": r"kuaishou|\bkwai", "Meituan": r"meituan|longcat", "DeepSeek": r"deepseek",
    "Moonshot AI": r"moonshot|kimi team", "Zhipu AI": r"zhipu|z\.ai|glm team", "MiniMax": r"^minimax",
    "StepFun": r"stepfun", "OpenAI": r"openai", "Anthropic": r"anthropic", "xAI": r"^xai\b|xai-org",
    "Mistral": r"mistral", "Cohere": r"cohere", "NAVER": r"naver", "Kakao": r"kakao", "Sakana AI": r"sakana",
    "Databricks": r"databricks", "Snowflake": r"snowflake",
}

ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.RO", "cs.CR", "cs.MA", "cs.NE", "cs.IR", "stat.ML"]
ARXIV_ETHICS_CATEGORIES = ["cs.CY", "cs.AI", "cs.HC", "cs.LG", "cs.CL"]


def arxiv_rss_url(categories) -> str:
    return "https://rss.arxiv.org/rss/" + "+".join(categories)


# arXiv's API terms allow one request every 3 seconds, hence "pause" (https://info.arxiv.org/help/api/tou.html).
# Each day's new arXiv papers in these categories, kept only when a listed person is an author. (arXiv's
# search API would find them by name, but it refuses requests from cloud servers such as GitHub Actions.)
# The lists are empty on weekends and holidays, when arXiv announces nothing.
SOURCES += [
    {"name": "arXiv", "label": f"arXiv new papers: {len(PROFESSORS)} professors", "format": "arxiv_rss",
     "url": arxiv_rss_url(ARXIV_CATEGORIES), "category": "research", "ai_only": True, "max_age_days": 14, "pause": 3.5,
     "professors": [n for n, _ in PROFESSORS]},
    {"name": "arXiv", "label": f"arXiv new papers: {len(EXPERTS)} scholars", "format": "arxiv_rss",
     "url": arxiv_rss_url(ARXIV_ETHICS_CATEGORIES), "category": "research", "ai_only": True, "max_age_days": 14,
     "pause": 3.5,
     "professors": [n for n, _, _ in EXPERTS]},
    # Papers on AI's own footprint (its energy, carbon, water and power), by anyone (classify.ai_footprint_paper), tagged
    # Infra & climate. Added 7 Oct 2026 so the stream's climate side has research behind it; arXiv's metadata is CC0.
    {"name": "arXiv", "label": "arXiv new papers: AI's footprint", "format": "arxiv_rss",
     "url": arxiv_rss_url(["cs.LG", "cs.AI", "cs.CL", "cs.DC", "cs.AR", "cs.PF", "cs.CY"]), "category": "research",
     "ai_only": True, "max_age_days": 14, "pause": 3.5, "footprint": True},
]

SOURCES += [
    # Papers big tech and frontier labs claim on Hugging Face (listed professors are matched here too).
    {"name": "Hugging Face Daily Papers", "url": "https://huggingface.co/api/daily_papers?limit=100",
     "format": "hf_daily", "category": "research", "ai_only": True, "max_age_days": 7, "companies": True,
     "expect_entries": True},
    # Apple's own papers (back 10 Oct 2026, under the owner's rule for labs' blogs)
    {"name": "Apple Machine Learning Research", "url": "https://machinelearning.apple.com/rss.xml",
     "category": "research", "ai_only": True, "max_age_days": 30, "org": "Apple"},
]
