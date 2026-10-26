"""AI buyouts (ai-buyouts/): every company bought, merged in or hired away whole in 2026 where the company bought makes
AI (or tools built for AI), or the buyer is an AI lab. A shopping list per buyer with two or more deals (a dot per deal
along the year, bigger for a bigger price), then every deal in a table that filters like Excel. Every deal was checked
by hand against the story that reported it: the story states the deal as fact, or a company confirmed it. Talks,
letters of intent and deals known only from "reportedly" stories are left out; prices are as each story gives them,
marked "reported" when they come from someone other than the companies, and never added up. Linked from Industry's
strip. Stakes that don't buy the company are on Who owns a piece of whom.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import infra_watch, pages, rss

PATH = "ai-buyouts/"
SINCE = "2026-01-01"

# Where each deal stands, as its story (or a later one, in the note) says: (tag, class)
STATUSES = {
    "bought": ("Bought", "by-b"),    # done: the story says the company has acquired it, or the team has joined
    "agreed": ("Agreed", "by-a"),    # announced or signed, not completed when last reported
    "blocked": ("Blocked", "by-x"),  # a government stopped it or ordered it undone
}

# (day announced, or "YYYY-MM" when the story gives only the month; buyer; company bought ("(team)" when only its people
#  joined); what it does, short; price as the story gives it ("Not disclosed" when it gives none; ", reported" when the
#  figure comes from a report, not the companies); the price in billions of dollars, for the dot's size (None when not
#  disclosed); status (a STATUSES key); the story; a later note, or ""; that note's story, or "")
DEALS = [
    ("2026-01-08", "OpenAI", "Convogo (team)", "Executive-coaching AI; its founders joined OpenAI", "Not disclosed",
     None, "bought", "https://the-decoder.com/convogos-founders-join-openai-to-close-the-gap-between-ai-potential-and-actual-use/",
     "", ""),
    ("2026-01-12", "OpenAI", "Torch", "App that gathers a person's medical records", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/01/12/openai-buys-torch-bring-unified-medical-data-chatgpt-health/",
     "About $100M, The Information reported", "https://the-decoder.com/openai-acquires-torch-to-build-a-medical-memory-for-ai/"),
    ("2026-01-13", "Deepgram", "OfOne", "Voice AI for fast-food restaurants", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/01/13/deepgram-raises-130m-at-1-3b-valuation-and-buys-a-yc-ai-startup/", "", ""),
    ("2026-01-14", "Phenom", "Included", "AI people analytics", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/01/14/phenom-acquires-included-expand-agentic-people-analytics-capabilities/", "", ""),
    ("2026-01-15", "Cloudflare", "Human Native", "Marketplace for licensed AI training data", "Not disclosed", None,
     "bought", "https://siliconangle.com/2026/01/15/cloudflare-buys-human-native-strengthen-licensed-data-access-ai-developers/",
     "", ""),
    ("2026-01-16", "ClickHouse", "Langfuse", "Open-source monitoring for AI apps", "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/01/16/database-maker-clickhouse-raises-400m-acquires-ai-observability-startup-langfuse/",
     "", ""),
    ("2026-01-22", "Yelp", "Hatch", "AI lead management for local businesses", "Up to $300M", 0.3, "agreed",
     "https://siliconangle.com/2026/01/22/yelp-acquire-ai-lead-management-startup-hatch-300m/", "", ""),
    ("2026-01-24", "Google", "Common Sense Machines", "AI that turns 2D images into 3D objects", "Not disclosed", None,
     "bought", "https://the-decoder.com/google-deepmind-goes-on-acquisition-spree-with-three-ai-deals-in-one-week/", "",
     ""),
    ("2026-01-28", "Handshake", "Cleanlab", "Checks the quality of AI training data", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/01/28/ai-data-labeler-handshake-buys-cleanlab-an-acquisition-target-of-multiple-others/",
     "", ""),
    ("2026-01-29", "Apple", "Q.ai", "AI that reads whispered speech and cleans up audio", "About $2B, reported", 2.0,
     "bought", "https://siliconangle.com/2026/01/29/apple-acquires-ai-startup-q-ai-reported-2b/", "", ""),
    ("2026-02-03", "SpaceX", "xAI", "Maker of Grok, merged into SpaceX", "Not disclosed", None, "bought",
     "https://the-decoder.com/musk-merges-money-losing-xai-into-spacex-before-mega-ipo/", "", ""),
    ("2026-02-10", "Phenom", "Be Applied", "AI skills assessment", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/02/10/phenom-strengthens-ai-hiring-platform-applied-acquisition/", "", ""),
    ("2026-02-10", "Nebius", "Tavily", "Web search for AI agents", "$275M, reported", 0.275, "agreed",
     "https://siliconangle.com/2026/02/10/ai-infrastructure-giant-nebius-buys-agentic-search-startup-tavily/",
     "Up to $400M with milestones", ""),
    ("2026-02-17", "Mistral", "Koyeb", "Cloud platform to run AI apps", "Not disclosed", None, "agreed",
     "https://techcrunch.com/2026/02/17/mistral-ai-buys-koyeb-in-first-acquisition-to-back-its-cloud-ambitions/", "", ""),
    ("2026-02-25", "Anthropic", "Vercept", "AI agents that use a computer like a person", "Not disclosed", None,
     "bought", "https://techcrunch.com/2026/02/25/anthropic-acquires-vercept-ai-startup-agents-computer-use-founders-investors/",
     "", ""),
    ("2026-03", "MyFitnessPal", "Cal AI", "AI calorie-counting app", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/10/15/when-it-came-to-cal-ais-viral-success-a-small-army-of-influencers-paid-off/", "",
     ""),
    ("2026-03-05", "Netflix", "InterPositive", "AI model for editing a film's own footage", "Not disclosed", None,
     "agreed", "https://techcrunch.com/2026/03/05/netflix-buys-ben-afflecks-ai-filmmaking-company-interpositive/", "", ""),
    ("2026-03-09", "OpenAI", "Promptfoo", "Security testing for AI", "Not disclosed", None, "agreed",
     "https://techcrunch.com/2026/03/09/openai-acquires-promptfoo-to-secure-its-ai-agents/", "", ""),
    ("2026-03-09", "Fireworks AI", "Hathora", "Compute orchestration for real-time AI", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/03/09/fireworks-ai-bets-hathora-acquisition-power-next-phase-real-time-ai/", "", ""),
    ("2026-03-10", "Meta", "Moltbook", "Social network for AI agents", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/03/10/meta-acquired-moltbook-the-ai-agent-social-network-that-went-viral-because-of-fake-posts/",
     "", ""),
    ("2026-03-11", "Databricks", "Quotient AI", "Finds where AI agents break", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/03/11/databricks-launches-data-engineering-copilot-acquires-agent-evaluation-startup/",
     "", ""),
    ("2026-03-11", "Zendesk", "Forethought", "AI customer-service agents", "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/03/11/zendesk-announces-deal-acquire-customer-support-ai-startup-forethought/", "",
     ""),
    ("2026-03-19", "OpenAI", "Astral", "Python developer tools", "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/03/19/openai-acquires-open-source-python-tooling-startup-astral/", "", ""),
    ("2026-03-23", "Meta", "Dreamer (team)", "AI agents; its founders and staff joined Meta", "Not disclosed", None,
     "bought", "https://siliconangle.com/2026/03/23/meta-acqui-hires-co-founders-agentic-ai-startup-dreamer/", "", ""),
    ("2026-03-24", "Databricks", "Antimatter", "Safe data access for AI agents", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/03/24/databricks-buys-two-startups-lakewatch-antimatter-siftd-ai-security/", "", ""),
    ("2026-03-24", "Databricks", "SiftD.ai", "Notebook where people and AI agents work together", "Not disclosed", None,
     "bought", "https://techcrunch.com/2026/03/24/databricks-buys-two-startups-lakewatch-antimatter-siftd-ai-security/",
     "", ""),
    ("2026-04-02", "OpenAI", "TBPN", "Tech business talk show", "Not disclosed", None, "agreed",
     "https://techcrunch.com/2026/04/02/openai-acquires-tbpn-the-buzzy-founder-led-business-talk-show/", "", ""),
    ("2026-04-09", "Cisco", "Galileo", "Monitoring for AI agents", "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/04/09/cisco-buys-galileo-strengthen-splunks-agentic-monitoring-capabilities/", "", ""),
    ("2026-04-13", "OpenAI", "Hiro (team)", "AI financial planner; the app shut down", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/04/13/openai-has-bought-ai-personal-finance-startup-hiro/", "", ""),
    ("2026-04-23", "Sierra", "Fragment", "Helps businesses build AI into their work", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/04/23/bret-taylors-sierra-buys-yc-backed-ai-startup-fragment/", "", ""),
    ("2026-04-23", "Cyera", "Ryft", "Data lake for companies running AI agents", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/04/23/cyera-acquires-ryft-give-enterprises-traceable-data-access-ai-agents/", "", ""),
    ("2026-04-24", "Cohere", "Aleph Alpha", "German AI lab, merging into Cohere", "Not disclosed", None, "agreed",
     "https://the-decoder.com/cohere-takes-over-aleph-alpha-shortly-after-the-german-startup-ousted-its-original-founder/",
     "Merger signed 16 Sep 2026", "https://siliconangle.com/2026/09/16/cohere-and-aleph-alpha-agree-to-merge-in-reported-20b-deal/"),
    ("2026-04-27", "Meta", "Manus", "AI agents", "$2B", 2.0, "blocked",
     "https://the-decoder.com/china-blocks-metas-2-billion-acquisition-of-ai-startup-manus/",
     "Bought Dec 2025; China ordered the deal undone", ""),
    ("2026-05-01", "Meta", "Assured Robot Intelligence", "AI for humanoid robots", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/05/01/meta-buys-robotics-startup-to-bolster-its-humanoid-ai-ambitions/", "", ""),
    ("2026-05-01", "Nebius", "Eigen AI", "Makes AI models run faster", "$643M", 0.643, "agreed",
     "https://siliconangle.com/2026/05/01/nebius-acquires-ai-model-optimization-startup-eigen-ai-643m/", "", ""),
    ("2026-05-04", "SAP", "Prior Labs", "AI models for tables of data", "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/05/04/sap-acquires-dremio-prior-labs-enhance-tabular-ai-capabilities/", "", ""),
    ("2026-05-12", "Celonis", "Ikigai Labs", "Generative AI for a company's own data", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/05/12/celonis-buys-decision-intelligence-startup-ikigai-labs-provide-operational-context-enterprise-ai/",
     "", ""),
    ("2026-05-12", "Nebius", "Clarifai (team)", "AI compute orchestration; its engineers, patents and a licence",
     "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/05/12/nebius-snaps-clarifais-compute-orchestration-tech-talent-enhance-ai-inference/",
     "", ""),
    ("2026-05-16", "OpenAI", "Weights.gg", "AI voice clones of famous people", "Not disclosed", None, "bought",
     "https://the-decoder.com/openai-bought-a-voice-cloning-startup-famous-for-celebrity-imitations/", "", ""),
    ("2026-05-18", "Anthropic", "Stainless", "Writes the code kits developers use to call APIs", "Not disclosed", None,
     "bought", "https://techcrunch.com/2026/05/18/anthropic-has-acquired-the-dev-tools-startup-used-by-openai-google-and-cloudflare/",
     "", ""),
    ("2026-05-19", "Mistral", "Emmi AI", "Physical AI for industry", "Not disclosed", None, "bought",
     "https://the-decoder.com/mistral-ai-acquires-viennese-physical-ai-startup-emmi-ai/", "", ""),
    ("2026-05-21", "New AI services firm backed by Anthropic and Blackstone", "Fractional AI",
     "Helps companies put generative AI to work", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/05/21/new-anthropic-blackstone-backed-ai-services-firm-acquires-fractional-ai/", "", ""),
    ("2026-05-21", "Sonar", "Gitar", "AI code review", "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/05/21/ai-code-quality-startup-sonar-buys-ai-code-review-startup-gitar/", "", ""),
    ("2026-05-28", "Asana", "StackAI", "No-code builder for AI agents", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/05/28/asana-acquires-stackai-run-ai-agent-workflows-across-enterprise-systems/", "", ""),
    ("2026-06-03", "Nvidia", "Kumo AI", "AI models for business forecasts", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/06/03/nvidia-snaps-kumo-ai-predictive-ai-startup-known-extreme-accuracy/", "", ""),
    ("2026-06-09", "100", "Cobblestone Labs", "AI checks of renters' income and fraud", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/06/09/rental-screening-startup-100-acquires-fraud-detection-firm-cobblestone-labs/",
     "", ""),
    ("2026-06-10", "Warner Music", "Sureel AI", "Tracks artists' work in AI training and output", "Not disclosed",
     None, "agreed", "https://techcrunch.com/2026/06/10/warner-music-acquires-ai-attribution-startup-sureel-ai/", "", ""),
    ("2026-06-11", "OpenAI", "Ona", "Runs long AI coding agents (formerly Gitpod)", "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/06/11/openai-acquires-ai-agent-orchestration-startup-ona/", "", ""),
    ("2026-06-15", "Salesforce", "Fin", "AI customer service (formerly Intercom)", "$3.6B", 3.6, "agreed",
     "https://techcrunch.com/2026/06/15/salesforce-acquires-ai-customer-service-platform-fin-for-3-6b/", "", ""),
    ("2026-06-16", "SpaceX", "Cursor", "AI coding editor", "$60B in stock", 60.0, "bought",
     "https://techcrunch.com/2026/06/16/spacex-to-acquire-cursor-for-60b-in-stock-days-after-blockbuster-ipo/",
     "Closed 15 Aug 2026", "https://techcrunch.com/2026/08/15/spacex-officially-closes-its-cursor-acquisition/"),
    ("2026-06-24", "Qualcomm", "Modular", "Software to run AI models on any chip", "About $3.9B in stock", 3.92,
     "agreed", "https://siliconangle.com/2026/06/24/qualcomm-shares-jump-14-modular-acquisition-guidance-upgrade/", "",
     ""),
    ("2026-06-24", "Superhuman", "GPTZero", "Detects AI-written text", "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/06/24/grammarly-parent-superhuman-buys-ai-detector-gptzero/", "", ""),
    ("2026-06-25", "TrueFoundry", "Seldon", "Software to run AI models in production", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/06/25/truefoundry-acquires-mlops-pioneer-seldon-ai-accelerate-enterprise-agentic-ai/",
     "", ""),
    ("2026-06-30", "Schneider Electric", "Cognite", "Industrial AI", "$3.1B", 3.1, "agreed",
     "https://siliconangle.com/2026/06/30/schneider-electric-acquires-cognite-3-1b-industrial-ai-push/", "", ""),
    ("2026-07-09", "Mercor", "Deeptune", "Practice worlds for training AI agents", "Not disclosed", None, "bought",
     "https://siliconangle.com/2026/07/09/mercor-buys-deeptune-build-training-environments-ai-agents/", "", ""),
    ("2026-07-15", "Whatnot", "Shaped", "AI recommendations and search", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/07/15/whatnot-acquires-shaped-to-power-real-time-live-shopping-recommendations/", "",
     ""),
    ("2026-07-24", "Cognition", "Poke", "AI assistant you text like a friend", "Low nine figures", None, "bought",
     "https://techcrunch.com/2026/07/24/why-cognition-bought-poke-ai-personality-is-becoming-a-competitive-advantage/",
     "", ""),
    ("2026-07-24", "Midjourney", "Co-Star", "Astrology app", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/07/24/midjourney-acquired-the-astrology-app-co-star/", "", ""),
    ("2026-07-28", "Cyera", "Oasis Security", "Security for AI agents", "$1B", 1.0, "agreed",
     "https://techcrunch.com/2026/07/28/cyera-agrees-to-acquire-oasis-security-for-1b-to-safeguard-proliferating-ai-agents/",
     "", ""),
    ("2026-07-30", "Okta", "Permiso", "Identity security for AI agents", "About $200M, reported", 0.2, "agreed",
     "https://techcrunch.com/2026/07/30/okta-buys-ai-security-startup-permiso-source-says-for-about-200m/", "", ""),
    ("2026-07-30", "Nscale", "Anyscale", "Software that spreads AI work across many servers", "$1.65B, reported", 1.65,
     "agreed", "https://siliconangle.com/2026/07/30/nscale-buys-ai-infrastructure-optimization-startup-anyscale-reported-1-65b/",
     "", ""),
    ("2026-08-05", "Klaviyo", "Agency", "AI customer-success software", "Not disclosed", None, "agreed",
     "https://techcrunch.com/2026/08/05/klaviyo-acquires-elias-torres-agency-in-full-circle-reunion-for-tech-founders/",
     "", ""),
    ("2026-08-06", "AMD", "Taalas", "Chips with an AI model built in", "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/08/06/amd-acquires-taalas-hardwire-ai-models-silicon/", "", ""),
    ("2026-08-08", "OpenAI", "NextSlide", "AI-made presentations", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/08/08/openai-acquires-presentation-startup-nextslide/", "", ""),
    ("2026-08-19", "Stripe", "OpenRouter", "One gateway to 400+ AI models", "$7.5B, reported", 7.5, "agreed",
     "https://techcrunch.com/2026/08/19/stripe-didnt-really-buy-openrouter-because-of-the-singularity/", "", ""),
    ("2026-09-02", "Adobe", "Rilo", "AI workflows for marketing teams", "Not disclosed", None, "bought",
     "https://techcrunch.com/2026/09/02/adobe-acquires-indian-market-intelligence-startup-rilo/", "", ""),
    ("2026-09-03", "Nvidia", "Hugging Face", "Hub for open AI models", "$12.93B", 12.93, "agreed",
     "https://siliconangle.com/2026/09/03/nvidia-confirms-12-9b-acquisition-of-ai-hosting-platform-hugging-face/", "",
     ""),
    ("2026-09-14", "Superhuman", "Fathom", "AI meeting notetaker", "Not disclosed", None, "agreed",
     "https://techcrunch.com/2026/09/14/superhuman-acquires-yc-backed-notetaker-fathom-as-productivity-platforms-push-for-agentic-work/",
     "", ""),
    ("2026-09-28", "AMD", "World Labs", "AI world models", "$8.2B in stock", 8.2, "agreed",
     "https://siliconangle.com/2026/09/28/amd-acquires-world-model-developer-world-labs-for-8-2b/", "", ""),
    ("2026-10-08", "Automation Anywhere", "Boost.ai", "Conversational voice AI", "Not disclosed", None, "agreed",
     "https://siliconangle.com/2026/10/08/automation-anywhere-acquires-boost-ai-to-expand-customer-facing-voice-ai/", "",
     ""),
    ("2026-10-19", "Boomi", "Elementary Data", "Data checks for AI agents and workflows", "Not disclosed", None,
     "bought", "https://www.itweb.co.za/article/boomi-acquires-elementary-data-to-bring-trusted-governed-data-to-the-ai-era/KWEBbvyLd34qmRjO",
     "", ""),
]

# stories checked by hand and left out, with why, so they aren't checked again
LEFT_OUT = {
    "https://the-decoder.com/china-investigates-metas-manus-acquisition-for-export-control-violations/":
        "same as Meta buying Manus (blocked)",
    "https://the-decoder.com/beijing-brands-metas-manus-acquisition-as-conspiratorial-and-bars-founders-from-leaving-china/":
        "same as Meta buying Manus (blocked)",
    "https://siliconangle.com/2026/04/27/china-blocks-metas-acquisition-ai-agent-developer-manus/":
        "same as Meta buying Manus (blocked)",
    "https://the-decoder.com/tencent-moves-to-buy-majority-stake-in-manus-after-beijing-forced-meta-to-unwind-its-2-billion-deal/":
        "Talks only",
    "https://techcrunch.com/2026/01/08/snowflake-announces-its-intent-to-buy-observability-platform-observe/":
        "Observe doesn't make AI",
    "https://siliconangle.com/2026/01/08/snowflake-acquires-observe-enhance-observability-capabilities/":
        "Observe doesn't make AI",
    "https://techcabal.com/2026/01/22/andela-acquires-woven/": "Woven's assessments are run by people, not AI",
    "https://techcrunch.com/2026/01/23/legal-ai-giant-harvey-acquires-hexus-as-competition-heats-up-in-legal-tech/":
        "Hexus makes product-demo tools, not AI",
    "https://siliconangle.com/2026/03/09/mariadb-buys-memory-computing-pioneer-gridgain-accelerate-data-processing-ai-agents/":
        "GridGain doesn't make AI",
    "https://siliconangle.com/2026/06/04/cloudflare-acquires-voidzero-maker-vite-javascript-toolchain/":
        "VoidZero makes JavaScript tools, not AI",
    "https://siliconangle.com/2026/04/29/cognizant-acquire-astreya-600m-deepen-ai-infrastructure-services/":
        "Astreya is an IT services firm",
    "https://siliconangle.com/2026/05/04/opaque-buys-post-quantum-cryptographic-ai-tech-abu-dhabis-tii/":
        "bought technology, not a company",
    "https://siliconangle.com/2026/03/26/defense-startup-shield-ai-raises-2b-acquires-flight-simulation-company-aechelon/":
        "Aechelon makes flight simulators, not AI",
    "https://siliconangle.com/2026/04/28/phenom-adds-plum-psychometric-science-agentic-ai-hiring-stack/":
        "Plum makes psychometric tests, not AI",
    "https://siliconangle.com/2026/08/06/framewerx-acquires-ad-micro-technology-widen-ai-driven-managed-services/":
        "AD Micro is an IT services firm",
    "https://techcabal.com/2026/07/28/techcabal-daily-zedcrest-bags-leatherback/": "Leatherback is a payments firm",
    "https://www.itweb.co.za/article/netapp-announces-intent-to-acquire-peakaio-to-advance-scalable-ai-infrastructure-architecture/JBwErvn3lVD76Db2":
        "PEAK:AIO makes storage software, not AI",
    "https://techcabal.com/2026/05/29/techcabal-daily-going-yoco-for-ma/": "can't read to check",
    "https://techcabal.com/2026/05/13/techcabal-daily-jiji-goes-to-bangladesh/": "can't read to check",
    "https://techcrunch.com/2026/04/03/anthropic-buys-biotech-startup-coefficient-bio-in-400m-deal-reports/":
        "Reported only, from an investors' letter; neither company confirmed it",
    "https://siliconangle.com/2026/04/03/anthropic-reportedly-acquires-medical-ai-startup-coefficient-bio-400m/":
        "Reported only, from an investors' letter; neither company confirmed it",
    "https://techcrunch.com/2026/09/14/openai-buys-smartphone-camera-maker-glass-imaging-for-300-million-report-says/":
        "Reported only (The Wall Street Journal); neither company confirmed it",
    "https://siliconangle.com/2026/09/14/openai-reportedly-buys-ai-camera-startup-glass-imaging-for-more-than-300m/":
        "Reported only (The Wall Street Journal); neither company confirmed it",
    "https://techcrunch.com/2026/06/18/source-elastic-agrees-to-buy-crv-backed-deductiveai-for-up-to-85m/":
        "Reported only, from a source",
    "https://siliconangle.com/2026/06/19/elastic-reportedly-acquires-site-reliability-engineering-startup-deductive-ai/":
        "Reported only, from a source",
    "https://the-decoder.com/nvidia-is-acquiring-poolsides-model-factory-and-109-employees-for-6-billion/":
        "a licence, job offers and a stake; its investors' letter says it is not an acquisition or an acqui-hire",
    "https://techcrunch.com/2026/05/29/after-nvidias-20b-not-acqui-hire-ai-chip-startup-groq-reportedly-raising-650m/":
        "Nvidia's Groq deal was in Dec 2025, a licence and hires",
    "https://techcrunch.com/2026/06/22/ai-chipmaker-groq-confirms-650m-raise-re-staffs-after-nvidias-20b-not-acqui-hire-deal/":
        "Nvidia's Groq deal was in Dec 2025, a licence and hires",
    "https://cohere.com/blog/cohere-and-aisle-sign-letter-of-intent-to-advance-cyber-resilient-sovereign-ai":
        "Letter of intent only, not yet a deal",
    "https://www.channelnewsasia.com/business/cohere-moves-buy-ai-cybersecurity-startup-aisle-6461846":
        "Letter of intent only, not yet a deal",
    "https://www.channelnewsasia.com/business/nvidia-in-talks-invest-further-in-reflection-ai-or-buy-it-ft-reports-6449691":
        "Talks only",
    "https://siliconangle.com/2026/10/11/nvidia-reportedly-in-early-talks-to-buy-acqui-hire-or-invest-more-in-reflection-ai/":
        "Talks only",
    "https://techcrunch.com/2026/08/19/cognition-ceo-denies-report-that-spacex-tried-to-acquire-the-startup/":
        "Talks only, denied",
    "https://siliconangle.com/2026/08/23/report-ai-model-hub-hugging-face-exploring-sale-at-13b-valuation/":
        "Talks only (later: Nvidia buying Hugging Face)",
    "https://techcrunch.com/2026/08/24/hugging-face-reportedly-in-talks-to-be-acquired-for-13b/":
        "Talks only (later: Nvidia buying Hugging Face)",
    "https://techcrunch.com/2026/08/26/nvidia-closes-in-on-hugging-face-acquisition/":
        "same as Nvidia buying Hugging Face",
    "https://the-decoder.com/nvidia-snaps-up-hugging-face-for-12-9-billion-as-closed-ai-labs-pull-away/":
        "same as Nvidia buying Hugging Face",
    "https://siliconangle.com/2026/08/27/nvidia-reportedly-acquires-ai-project-hosting-platform-hugging-face-for-12-9b/":
        "same as Nvidia buying Hugging Face",
    "https://techcrunch.com/2026/08/16/stripe-will-reportedly-acquire-ai-gateway-startup-openrouter-for-7b/":
        "same as Stripe buying OpenRouter",
    "https://techcrunch.com/2026/01/29/elon-musk-spacex-tesla-xai-merger-talks-ipo-reuters/":
        "Talks only (later: SpaceX and xAI merged)",
    "https://the-decoder.com/spacex-eyes-merger-with-xai-that-would-unite-grok-starlink-and-x-under-one-roof/":
        "Talks only (later: SpaceX and xAI merged)",
    "https://techcrunch.com/2026/04/21/spacex-is-working-with-cursor-and-has-an-option-to-buy-the-startup-for-60-billion/":
        "an option to buy only (later: SpaceX buying Cursor)",
    "https://siliconangle.com/2026/04/24/ai-startups-cohere-aleph-alpha-merge-600m-new-funding/":
        "same as Cohere and Aleph Alpha merging",
    "https://techcrunch.com/2026/04/25/why-cohere-is-merging-with-aleph-alpha/": "same as Cohere and Aleph Alpha merging",
    "https://techcrunch.com/video/the-32b-acquisition-that-one-vc-is-calling-the-deal-of-the-decade/":
        "Google buying Wiz was agreed in 2025",
    "https://techcrunch.com/2026/03/19/jeff-bezos-reportedly-wants-100-billion-to-buy-and-transform-old-manufacturing-firms-with-ai/":
        "raising money to buy firms, no deal",
    "https://siliconangle.com/2026/07/15/agi-raises-70m-buy-transform-insurance-firms-ai-native-operations/":
        "raising money to buy firms, no deal",
    "https://the-decoder.com/microsoft-snaps-up-texas-data-center-that-oracle-and-openai-left-behind/":
        "a data centre lease, not a company",
    "https://w.media/sm-to-acquire-princeton-digital-groups-enterprise-data-center-business-in-indonesia/":
        "a data-centre business, not an AI company",
    ("https://datacenterpost.com/3c-and-datalec-merge-to-form-400m-ai-data-center-infrastructure-platform/?utm_source=rss"
     "&utm_medium=rss&utm_campaign=3c-and-datalec-merge-to-form-400m-ai-data-center-infrastructure-platform"):
        "data-centre builders, not AI companies",
    "https://techcrunch.com/2026/01/15/openai-invests-in-sam-altmans-brain-computer-interface-startup-merge-labs/":
        "a stake, not a buyout",
    "https://the-decoder.com/openai-invests-in-merge-labs-a-brain-computer-interface-startup-co-founded-by-sam-altman/":
        "a stake, not a buyout",
    "https://techcrunch.com/2026/01/12/why-amazon-bought-bee-an-ai-wearable/": "Amazon bought Bee in 2025",
    "https://the-decoder.com/openai-buys-ona-to-push-codex-toward-long-running-autonomous-coding-tasks/":
        "same as OpenAI buying Ona",
    "https://siliconangle.com/2026/04/02/openai-acquires-tech-industry-podcast-tbpn/": "same as OpenAI buying TBPN",
    "https://the-decoder.com/openai-acquires-astral-to-bring-pythons-most-popular-dev-tools-into-its-codex-ai-coding-platform/":
        "same as OpenAI buying Astral",
    "https://the-decoder.com/openai-plans-to-acquire-promptfoo-and-bake-ai-security-testing-directly-into-its-frontier-enterprise-platform/":
        "same as OpenAI buying Promptfoo",
    "https://techcrunch.com/2026/01/29/apple-buys-israeli-startup-q-ai-as-the-ai-race-heats-up/": "same as Apple buying Q.ai",
    "https://the-decoder.com/openai-cuts-off-cursor-after-spacex-acquisition-citing-musks-history-of-breaking-contracts/":
        "same as SpaceX buying Cursor",
    "https://dplnews.com/en-el-salvador-la-ia-y-tiktok-desplazan-a-google-en-decisiones-de-compra-de-usuarios/":
        "shoppers' purchases, not a company being bought",
    "https://www.xataka.com/servicios/amazon-cierra-puerta-a-agentes-ia-mayor-cadena-supermercados-eeuu-abre-par-par":
        "AI agents shopping, not a company being bought",
    "https://www.channelnewsasia.com/business/brazils-itau-agrees-buy-ai-startup-neospace-589-million-6492871":
        "can't read to check",
}

# the newest day every story was read for the list above; the candidates start after it
CHECKED_TO = "2026-10-20"
_BUY = re.compile(r"\b(acquir\w*|acquisitions?|buys|bought|to buy|buying|snaps? up|scoops? up|acqui-?hires?|"
                  r"acquihires?|takeover|takes over|merge with|merger|merges \w+ into|purchases?)\b", re.I)
# a headline using those words for something other than buying a company
_NOT = re.compile(r"\b(chips?|GPUs?|data cent(er|re)s?|merge rate|smart glasses|shopping|purchases? (on|for)|"
                  r"buy(ing)? (land|home|stocks?|shares)|acquisition of (data|skills))\b", re.I)


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Stories from after CHECKED_TO (or `since`, if later) that no deal uses and LEFT_OUT doesn't hold, whose headline
    names a company being bought, merged or hired away whole. One per event, newest first."""
    since = max(since, CHECKED_TO + "~")  # '~' sorts after any time of day, so CHECKED_TO itself is done
    used = {u for r in DEALS for u in (r[7], r[9]) if u} | set(LEFT_OUT)
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["date"] >= since and c.get("category") not in ("research", "regulation")
            and not any(s["url"] in used for s in [c, *(c.get("also") or [])])
            and _BUY.search(c["title"]) and not _NOT.search(c["title"])]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a buyouts/<day> branch: each deal it adds or changes, and the stories it left out;
    None when it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("DEALS", "LEFT_OUT"))
    rows = [(_day(r[0]), r[1], r[2], r[4], STATUSES[r[6]][0] + (f" ({r[8]})" if r[8] else ""), r[9] or r[7])
            for r in DEALS if r[7] not in had["DEALS"] or (r[9] and r[9] not in had["DEALS"])]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("AI buyouts", f"deal{'s' * (len(rows) != 1)}", branch,
                        ("Day", "Buyer", "Bought", "Price", "Where it stands", "Story"), rows, dropped)


def _day(d: str) -> str:
    """"5 Mar" (or "Mar" when the story gives only the month)."""
    if len(d) == 7:
        return f"{date.fromisoformat(d + '-01'):%b}"
    x = date.fromisoformat(d)
    return f"{x.day} {x:%b}"


def _mid(d: str) -> date:
    return date.fromisoformat(d + "-15") if len(d) == 7 else date.fromisoformat(d)


def _size(b: float | None) -> int:
    """A dot's width in pixels: its area grows with the price, so $60B is the largest and an undisclosed price the
    smallest."""
    return 12 if b is None else round(12 + 4.4 * b ** 0.5)


def _lists(deals: list, today: date) -> str:
    """A row per buyer with two or more deals, most deals first: a dot per deal along the year (bigger for a bigger
    price, hollow when the price wasn't given, dashed while only agreed, a cross when blocked), each linking to its row
    in the table. The biggest deals and blocked ones are named beside their dot."""
    lo = date.fromisoformat(SINCE)
    hi = date(today.year, today.month, 1) + timedelta(days=32)
    hi = date(hi.year, hi.month, 1)  # the end of this month
    x = lambda d: round((d - lo).days / (hi - lo).days * 100, 2)
    count: dict[str, int] = {}
    for r in deals:
        count[r[1]] = count.get(r[1], 0) + 1
    buyers = sorted((b for b, n in count.items() if n > 1), key=lambda b: (-count[b], b))
    months, m = [], lo
    while m < hi:
        months.append(f'<i class="by-gl" style="left:{x(m)}%"></i><span class="by-mo" style="left:{x(m)}%">{m:%b}</span>')
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    rows = []
    for b in buyers:
        dots = []
        for n, r in sorted(((n, r) for n, r in enumerate(deals) if r[1] == b), key=lambda t: -(t[1][5] or 0)):
            left = x(_mid(r[0]))
            tip = f"{_day(r[0])} · {r[2]} · {r[4]} · {STATUSES[r[6]][0]}"
            cls = STATUSES[r[6]][1] + (" by-un" if r[5] is None else "") + (" by-l" if left > 60 else "")
            dots.append(f'<a class="by-dot {cls}" href="{PATH}#by-{n}" style="left:{left}%;--s:{_size(r[5])}px" '
                        f'aria-label="{escape(tip)}" data-tip="{escape(tip)}"></a>')
            if (r[5] or 0) >= 2 or r[6] == "blocked":
                word = f"{r[2]} {r[4]}" if r[5] else r[2]
                side = "right" if left > 70 else "left"
                # another dot of this buyer where the label would run: the label goes above its dot instead
                near = [x(_mid(o[0])) for o in deals if o[1] == b and o is not r]
                up = any(0 < (left - o if side == "right" else o - left) < 22 for o in near)
                dots.append(f'<span class="by-lb{" by-up" * up}" style="{side}:calc({100 - left if side == "right" else left}% + '
                            f'{_size(r[5]) // 2 + 6}px)">{escape(word)}{" · blocked" * (r[6] == "blocked")}</span>')
        rows.append(f'<div class="by-r"><span class="by-n">{escape(b)} <b>{count[b]}</b></span>'
                    f'<div class="by-tr">{"".join(dots)}</div></div>')
    ones = sorted((b for b, n in count.items() if n == 1), key=str.lower)
    key = ('<p class="by-key"><span><i class="by-k by-b"></i>Bought</span><span><i class="by-k by-a"></i>Agreed, not '
           'yet completed</span><span><i class="by-k by-b by-un"></i>Price not given</span><span><b class="by-kx">✕</b>'
           'Blocked</span><span>A bigger dot is a bigger price. Point at a dot to see the deal, click to jump to its '
           'row.</span></p>')
    return (f'<section class="by-ls"><h2>Shopping lists</h2>{key}<div class="by-g"><div class="by-ax">{"".join(months)}'
            f'</div>{"".join(rows)}</div><p class="by-one">One deal each ({len(ones)} more buyers): '
            f'{escape(", ".join(ones))}.</p></section>')


def _price(r) -> str:
    kind = "Not disclosed" if r[4] == "Not disclosed" else "Reported" if "reported" in r[4] else "Disclosed"
    return f'<td class="by-p" data-f="{kind}">{escape(r[4])}</td>'


def _row(n: int, r) -> str:
    d, buyer, bought, what, price, b, st, url, nt, nu = r
    after = ""
    if nt:
        after = f'<span class="fx-c">' + (f'<a href="{escape(nu)}" rel="noopener">{escape(nt)}</a>' if nu
                                          else escape(nt)) + "</span>"
    return (f'<tr id="by-{n}"><td class="pc-d" data-f="{_mid(d):%b}">{_day(d)}</td><td><b>{escape(buyer)}</b></td>'
            f'<td data-f="{escape(bought)}"><b>{escape(bought)}</b><span class="fx-c">{escape(what)}</span></td>'
            f'{_price(r)}<td class="fx-s" data-f="{STATUSES[st][0]}"><span class="pc-k {STATUSES[st][1]}">'
            f'{STATUSES[st][0]}</span>{after}<span class="fx-c"><a href="{escape(url)}" rel="noopener">story</a></span>'
            "</td></tr>")


def body(today: date) -> str:
    deals = sorted(DEALS, key=lambda r: _mid(r[0]), reverse=True)
    count: dict[str, int] = {}
    for r in deals:
        count[r[1]] = count.get(r[1], 0) + 1
    most = max(count.values())
    top = sorted(b for b, n in count.items() if n == most)
    big = max((r for r in deals if r[5] and r[6] != "blocked"), key=lambda r: r[5])
    lead = (f'<p class="by-lead"><b>{" and ".join(top)}</b> made the most deals in {SINCE[:4]} ({most}). The biggest '
            f'price: <b>{escape(big[1])}</b> buying <b>{escape(big[2])}</b> for <b>{escape(big[4])}</b>.</p>'
            f'<p class="by-sub">{len(deals)} deals by {len(count)} buyers since 1 Jan {SINCE[:4]}, counting the ones '
            f'still waiting to complete and the ones blocked.</p>')
    limits = [
        ("What counts", "A company bought, merged in or hired away whole (its team joining the buyer) where the company "
         "bought makes AI or tools built for AI, or the buyer is an AI lab. Stakes that don't buy the company are on Who "
         "owns a piece of whom."),
        ("Checked by hand", "Each deal links to the story that reported it: the story states the deal as fact, or a "
         "company confirmed it. Talks, letters of intent and deals known only from \"reportedly\" stories are left "
         "out until confirmed."),
        ("Prices", "As each story gives them, in US dollars. \"Reported\" means the figure came from a news report, not "
         "the companies. Prices aren't added up: many weren't given."),
        ("Where it stands", "Bought: the story says the deal is done. Agreed: announced or signed, not completed when "
         "last reported. Blocked: a government stopped it."),
    ]
    rows = "".join(_row(n, r) for n, r in enumerate(deals))
    return ('<div class="ft jb pc fx by">\n'
            + pages.feature_head(PATH, "AI buyouts", f"Who is buying AI companies in {SINCE[:4]}, and for how much?",
                                 f"Every AI company bought, merged in or hired away whole since 1 Jan {SINCE[:4]}, from "
                                 "our own stories. Each deal links to the story that reported it, with the price only "
                                 "when one was given.")
            + lead + _lists(deals, today)
            + f'<section class="iw by-all"><h2>Every deal, newest first</h2>'
              f'<div class="iw-fbar"></div><p class="iw-count" aria-live="polite">Showing <b>{len(deals)}</b> of '
              f'{len(deals)} deals. Pick a ▾ to filter. <button type="button" class="iw-clear" hidden>Clear filters'
              '</button></p><table class="pc-rows fx-t xf-t"><thead><tr><th data-seen>Date</th><th>Buyer</th>'
              '<th data-nof>Bought</th><th>Price</th><th>Where it stands</th></tr></thead>'
              f'<tbody>{rows}</tbody></table></section>\n'
            '<section class="jb-lim"><h2>About these deals</h2>\n<table class="mt jb-small jb-limits"><tbody>'
            + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
            + "</tbody></table></section></div>\n" + infra_watch.SCRIPT + "\n")


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    what = (f"Who is buying AI companies in {SINCE[:4]}, and for how much? Every AI company bought, merged in or hired "
            "away whole, each deal checked by hand against its story.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI buyouts",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("AI buyouts · AI Pulse", what, PATH, body(today), data, pages.frame(conn, len(cards)),
                   ("/industry/", "Back to Industry"),
                   "Every deal links to the story that reported it, checked by hand."),
        encoding="utf-8")
    return [PATH]
