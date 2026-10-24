"""AI pacts and orders (ai-pacts-and-orders/): four sections one under another, each a plain table. Pledges: the summit
pledges on AI and the Council of Europe's AI treaty, whether the US, the UK and China signed, every country folded below (from each official signatory list, kept here by hand: the lists hardly change once
a summit is over, and some sit behind pages our reader can't open). Deals governments signed with AI companies. Bans,
each tagged where it stands. Orders, investigations and court cases. Every deal, ban and order was checked by hand against the story that reported
it; talks, reported plans and threats are left out until they happen. Linked from Policy's strip.
"""
from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

from . import pages, rss

PATH = "ai-pacts-and-orders/"

# The summit pledges, oldest first: (name, month signed, the official list, its name, signers as that list gives them,
# those that joined after the summit with the day they joined). A pledge with no signers yet isn't shown.
PLEDGES = [
    ("Bletchley", "Nov 2023",
     "https://www.gov.uk/government/publications/ai-safety-summit-2023-the-bletchley-declaration/the-bletchley-"
     "declaration-by-countries-attending-the-ai-safety-summit-1-2-november-2023", "GOV.UK",
     ("Australia", "Brazil", "Canada", "Chile", "China", "European Union", "France", "Germany", "India", "Indonesia",
      "Ireland", "Israel", "Italy", "Japan", "Kenya", "Kingdom of Saudi Arabia", "Netherlands", "Nigeria",
      "The Philippines", "Republic of Korea", "Rwanda", "Singapore", "Spain", "Switzerland", "Türkiye", "Ukraine",
      "United Arab Emirates", "United Kingdom of Great Britain and Northern Ireland", "United States of America"),
     {"New Zealand": "23 Oct 2024"}),
    ("Seoul", "May 2024",
     "https://www.gov.uk/government/publications/seoul-declaration-for-safe-innovative-and-inclusive-ai-ai-seoul-"
     "summit-2024/seoul-declaration-for-safe-innovative-and-inclusive-ai-by-participants-attending-the-leaders-"
     "session-ai-seoul-summit-21-may-2024", "GOV.UK",
     ("Australia", "Canada", "the European Union", "France", "Germany", "Italy", "Japan", "the Republic of Korea",
      "the Republic of Singapore", "the United Kingdom", "the United States of America"), {}),
    # the Council of Europe's Framework Convention on AI, the only one binding in law; its treaty office's chart
    # (behind a browser check our reader can't pass), copied by hand on 17 Oct 2026: signer and the day it signed
    ("AI treaty", "Sep 2024",
     "https://www.coe.int/en/web/conventions/full-list?module=signatures-by-treaty&treatynum=225",
     "the Council of Europe's treaty office",
     {"Albania": "15/06/2026", "Andorra": "05/09/2024", "Armenia": "27/01/2026",
      "Bosnia and Herzegovina": "09/12/2025", "Georgia": "05/09/2024", "Iceland": "05/09/2024",
      "Liechtenstein": "27/02/2025", "Montenegro": "05/11/2024", "North Macedonia": "08/05/2026",
      "Norway": "05/09/2024", "Republic of Moldova": "05/09/2024", "San Marino": "05/09/2024",
      "Switzerland": "27/03/2025", "Ukraine": "15/05/2025", "United Kingdom": "05/09/2024", "Canada": "11/02/2025",
      "Israel": "05/09/2024", "Japan": "11/02/2025", "United States of America": "05/09/2024",
      "Uruguay": "02/09/2025", "European Union": "05/09/2024"}, {}),
    ("Paris", "Feb 2025",
     "https://www.elysee.fr/en/emmanuel-macron/2025/02/11/statement-on-inclusive-and-sustainable-artificial-"
     "intelligence-for-people-and-the-planet", "Élysée",
     ("Armenia", "Australia", "Austria", "Belgium", "Brazil", "Bulgaria", "Cambodia", "Canada", "Chile", "China",
      "Colombia", "Côte d’Ivoire", "Croatia", "Cyprus", "Czech Republic", "Denmark", "Djibouti", "Egypt", "Estonia",
      "Finland", "France", "Germany", "Greece", "Hungary", "Iceland", "India", "Indonesia", "Ireland", "Italy",
      "Japan", "Kazakhstan", "Kenya", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Malta", "Mexico",
      "Moldova", "Monaco", "Morocco", "Netherlands", "New Zealand", "Nigeria", "Norway", "Peru", "Poland",
      "Portugal", "Republic of Korea", "Romania", "Rwanda", "Senegal", "Serbia", "Singapore", "Slovakia", "Slovenia",
      "Spain", "Sweden", "Switzerland", "Thailand", "Ukraine", "Uruguay", "Zimbabwe", "African Union Commission",
      "European Union"), {}),
    # the annex to the Press Information Bureau's release ("as of 5th March 2026"; PIB refuses our reader), copied by
    # hand on 17 Oct 2026
    ("New Delhi", "Feb 2026", "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2231208",
     "the Press Information Bureau, as of 5 Mar 2026",
     ("Albania", "Armenia", "Australia", "Austria", "Bangladesh", "Belgium", "Bhutan", "Bolivia", "Botswana", "Brazil",
      "Bulgaria", "Cambodia", "Canada", "Chile", "China", "Croatia", "Colombia", "Costa Rica", "Cuba", "Cyprus",
      "Czech Republic", "Denmark", "Egypt", "Estonia", "Ethiopia", "Fiji", "Finland", "France", "Gambia", "Germany",
      "Greece", "Guatemala", "Guyana", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Ireland", "Israel", "Italy",
      "Japan", "Kazakhstan", "Kenya", "Kyrgyzstan", "Latvia", "Liechtenstein", "Lithuania", "Luxembourg", "Maldives",
      "Malta", "Mauritius", "Mexico", "Morocco", "Mozambique", "Myanmar", "Nepal", "Netherlands", "New Zealand",
      "Norway", "Oman", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Romania", "Russia", "Rwanda",
      "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Singapore", "Slovakia", "Slovenia", "South Korea", "Spain",
      "Sri Lanka", "Suriname", "Sweden", "Switzerland", "Tajikistan", "Tanzania", "Trinidad and Tobago", "UAE",
      "Ukraine", "UK", "USA", "Uzbekistan", "EU", "IFAD"), {}),
]
# ratified, for the treaty: signer and the day it ratified; it comes into force at 5 ratifications
RATIFIED = {"AI treaty": {"European Union": "15/05/2026"}}
IN_FORCE_AT = 5
# a grid row per country: the lists' longer names mapped to the one name used on the page
SAME = {"United Kingdom of Great Britain and Northern Ireland": "United Kingdom", "the United Kingdom": "United Kingdom",
        "United States of America": "United States", "the United States of America": "United States",
        "Republic of Korea": "South Korea", "the Republic of Korea": "South Korea", "the Republic of Singapore":
        "Singapore", "Kingdom of Saudi Arabia": "Saudi Arabia", "The Philippines": "Philippines",
        "the European Union": "European Union", "EU": "European Union", "UK": "United Kingdom",
        "USA": "United States", "UAE": "United Arab Emirates", "Republic of Moldova": "Moldova"}
# the rows at the top of the grid, marked: the ones readers ask about
FOCUS = ["United States", "United Kingdom", "China"]
# how a sentence names them
SAY = {"United States": "the US", "United Kingdom": "the UK", "US": "the US", "UK": "the UK",
       "AI treaty": "the AI treaty"}

# Deals a government signed with an AI company: (day, government, company, what, the story)
DEALS = [
    ("2026-10-14", "Singapore", "Anthropic", "An MoU with the Ministry of Digital Development and Information",
     "https://www.anthropic.com/news/singapore-office-opening"),
    ("2026-10-14", "Singapore", "Google DeepMind", "A scam-detection model built with GovTech Singapore",
     "https://deepmind.google/blog/on-device-ai-scam-detection-mddi/"),
    ("2026-09-30", "US (White House)", "Six tech companies", "A voluntary AI safety accord, not binding",
     "https://en.mercopress.com/2026/09/30/trump-and-six-tech-companies-sign-a-voluntary-artificial-intelligence-"
     "safety-accord?utm_source=feed&utm_medium=rss&utm_content=main&utm_campaign=rss"),
    ("2026-06-29", "California", "Anthropic", "State government use of Claude at half price",
     "https://techcrunch.com/2026/06/29/anthropic-and-gov-newsom-forge-deal-allowing-california-government-to-use-"
     "claude-at-half-price/"),
    ("2026-05-22", "Nigeria", "Meta", "A government information chatbot built on Meta AI",
     "https://techcabal.com/2026/05/22/nigeria-taps-meta-ai-to-help-citizens-access-government-services/"),
    ("2026-05-01", "US (Pentagon)", "Nvidia, Microsoft and AWS", "AI on classified networks",
     "https://techcrunch.com/2026/05/01/pentagon-inks-deals-with-nvidia-microsoft-and-aws-to-deploy-ai-on-"
     "classified-networks/"),
    ("2026-04-28", "US (Pentagon)", "Google", "Its AI models for classified work",
     "https://the-decoder.com/google-signs-ai-deal-with-the-pentagon-ignoring-protest-from-over-600-employees/"),
    ("2026-02-28", "US (Pentagon)", "OpenAI", "AI on classified networks",
     "https://the-decoder.com/openai-signs-pentagon-deal-for-classified-ai-networks-hours-after-anthropic-gets-"
     "banned-from-federal-agencies/"),
]

# Bans and holds, drawn start to end: (day it began, government, company, what, its story, the day it ended or None
# when no end has been reported, the story of its end, what the end was, court rulings on the way (day, what))
BANS = [
    ("2026-10-19", "US (Homeland Security)", "DeepSeek", "DeepSeek products to be removed from federal civilian "
     "agencies and barred from their purchases",
     "https://siliconangle.com/2026/10/19/trump-administration-orders-ban-on-deepseek-in-federal-agencies/", None, "",
     "", []),
    ("2026-06-26", "US", "OpenAI", "GPT-5.6 only for customers the government approves, one by one",
     "https://the-decoder.com/openais-gpt-5-6-rollout-now-requires-us-government-approval-on-a-customer-by-"
     "customer-basis/", None, "", "", []),
    ("2026-06-13", "US", "Anthropic", "Claude Fable 5 and Mythos 5 switched off worldwide",
     "https://the-decoder.com/us-government-forces-anthropic-to-disable-claude-fable-5-and-mythos-5-for-all-"
     "customers-worldwide/", "2026-06-30",
     "https://techcrunch.com/2026/06/30/trump-drops-restrictions-on-anthropics-mythos-and-fable-models/", "lifted",
     []),
    ("2026-04-27", "China", "Meta", "Told to unwind its $2B purchase of Manus",
     "https://techcrunch.com/2026/04/27/china-vetoes-metas-2b-manus-deal-after-months-long-probe/", "2026-04-27", "",
     "final", []),
    ("2026-02-27", "US", "Anthropic", "Federal agencies told to stop using Anthropic; the Pentagon bars it as a "
     "supply-chain risk",
     "https://siliconangle.com/2026/02/27/trump-orders-federal-agencies-stop-using-anthropic-products/", None, "", "",
     [("2026-03-27", "a judge blocks the ban"), ("2026-04-08", "an appeals court refuses to pause the Pentagon's bar"),
      ("2026-08-28", "a court rules the Pentagon's label unlawful"),
      ("2026-09-25", "an appeals court upholds the military bar")]),
]

# Orders, investigations and court cases a government brought: (day, government, company, kind, what, its story)
ORDERS = [
    ("2026-09-30", "US (FTC)", "OpenAI, Anthropic and others", "Investigation", "Consumer-protection probe",
     "https://the-decoder.com/ftc-launches-sweeping-probe-into-openai-anthropic-and-other-ai-labs-over-consumer-"
     "protection-concerns/"),
    ("2026-09-29", "Florida", "OpenAI", "Court case", "Asks a court to stop ChatGPT seeming human and marketing to "
     "children", "https://the-decoder.com/florida-wants-a-court-to-stop-chatgpt-from-pretending-to-be-human-and-"
     "talking-to-kids/"),
    ("2026-09-24", "Australia", "OpenAI", "Investigation", "Whether its agents' breach of a government health site "
     "broke the law", "https://techcrunch.com/2026/09/24/australia-to-investigate-if-openai-hack-of-government-"
     "health-website-broke-the-law/"),
    ("2026-06-13", "US states", "OpenAI", "Investigation", "Attorneys general ask about its ads and health data",
     "https://techcrunch.com/2026/06/13/openai-faces-investigation-from-state-attorneys-general/"),
    ("2026-06-03", "UK", "Google", "Order", "Give publishers an opt-out from AI Overviews",
     "https://siliconangle.com/2026/06/03/uk-orders-google-provide-ai-overviews-opt-option-publishers/"),
    ("2026-06-01", "Florida", "OpenAI", "Court case", "Sues OpenAI and Sam Altman over ignored safety warnings and "
     "violent incidents",
     "https://techcrunch.com/2026/06/01/florida-sues-openai-sam-altman-in-first-of-its-kind-lawsuit-over-violent-"
     "incidents/"),
    ("2026-04-09", "Florida (Attorney General)", "OpenAI", "Investigation",
     "ChatGPT's alleged part in the Florida State University shooting",
     "https://techcrunch.com/2026/04/09/florida-ag-investigation-openai-chatgpt-shooting/"),
    ("2026-01-16", "California", "xAI", "Order", "Cease and desist over sexual deepfakes from Grok",
     "https://techcrunch.com/2026/01/16/california-ag-sends-musks-xai-a-cease-and-desist-order-over-sexual-"
     "deepfakes/"),
    ("2026-01-14", "California (Attorney General)", "xAI", "Investigation",
     "Grok's nonconsensual sexually explicit material",
     "https://techcrunch.com/2026/01/14/musk-denies-awareness-of-grok-sexual-underage-images-as-california-ag-"
     "launches-probe/"),
    ("2026-01-13", "Brazil", "Meta", "Order", "Let other companies' AI chatbots onto WhatsApp",
     "https://techcrunch.com/2026/01/13/brazil-orders-meta-to-suspend-policy-banning-third-party-ai-chatbots-from-"
     "whatsapp/"),
    ("2026-01-12", "UK (Ofcom)", "X", "Investigation", "Grok's part in sexual deepfakes",
     "https://the-decoder.com/uk-regulator-investigates-x-over-grok-ais-role-in-generating-sexualized-deepfakes/"),
    ("2026-01-08", "EU (European Commission)", "X", "Order", "Keep all Grok-related documents through 2026",
     "https://the-decoder.com/eu-orders-x-to-preserve-all-grok-related-documents-through-2026/"),
    ("2026-01-02", "India", "X", "Order", "Fix Grok over obscene content within 72 hours",
     "https://techcrunch.com/2026/01/02/india-orders-musks-x-to-fix-grok-over-obscene-ai-content/"),
]
# stories checked by hand and left out, with why, so they aren't checked again
LEFT_OUT = {
    "https://dplnews.com/los-planes-de-la-ministra-lincolao-para-instalar-a-chile-en-el-circuito-global-de-la-ia-"
    "estamos-cerca-de-cerrar-un-acuerdo-con-openai/":
        "Chile's minister says it is close to an OpenAI agreement, not signed yet",
    "https://www.engadget.com/2290535/homeland-security-bans-deepseek-use-in-federal-civilian-agencies/":
        "Same as US (Homeland Security) → DeepSeek, 2026-10-19",
    "https://olhardigital.com.br/2026/10/20/pro/resumo-do-od-lula-acusa-meta-japao-lanca-sonda-a-marte-novo-"
    "financiamento-da-openai-e-mais/":
        "A campaign's planned electoral complaint against Meta, not filed or a government action",
    "https://techcrunch.com/2026/01/11/indonesia-blocks-grok-over-non-consensual-sexualized-deepfakes/":
        "A regulator's ban: on AI fines and bans",
    "https://techcrunch.com/2026/02/01/indonesia-conditionally-lifts-ban-on-grok/":
        "A regulator's ban lifted: on AI fines and bans",
    "https://the-decoder.com/white-house-worried-about-compute-limits-as-it-blocks-wider-access-to-anthropics-mythos/":
        "Reported by the Wall Street Journal only",
    "https://www.channelnewsasia.com/business/germany-unveil-nvidia-ai-agreement-next-week-government-sources-say-"
    "6465816": "Not signed yet",
    "https://the-decoder.com/openai-and-the-trump-administration-are-negotiating-a-government-stake-in-the-ai-startup/":
        "Talks only",
    "https://the-decoder.com/anthropics-fable-5-is-back-worldwide-after-a-two-week-go"
    "vernment-ban-over-a-jailbreak/":
        "same as US → Anthropic, 2026-06-13 (already ended 2026-06-30)",
    "https://the-decoder.com/anthropics-fable-5-could-return-within-days-as-trump-adm"
    "inistration-prepares-to-lift-restrictions/":
        "Lifting only planned; ban already held",
    "https://techcrunch.com/2026/06/27/asian-ai-startups-launch-mythos-like-models-as"
    "-anthropics-export-ban-drags-on/":
        "same as US → Anthropic, 2026-06-13; no new action",
    "https://techcrunch.com/2026/06/15/the-us-governments-anthropic-models-ban-was-ne"
    "ver-about-an-ai-jailbreak/":
        "same as US → Anthropic, 2026-06-13; commentary",
    "https://techcrunch.com/2026/06/15/cybersecurity-vets-protest-dangerous-us-govern"
    "ment-ban-on-anthropics-most-powerful-models/":
        "same as US → Anthropic, 2026-06-13; protest",
    "https://techcrunch.com/video/is-the-us-governments-anthropic-ban-accidentally-he"
    "lping-the-brand/":
        "same as US → Anthropic, 2026-06-13; commentary",
    "https://techcrunch.com/podcast/the-us-banned-anthropics-fable-5-release-but-the-"
    "numbers-dont-seem-to-care/":
        "same as US → Anthropic, 2026-06-13; commentary",
    "https://arstechnica.com/ai/2026/06/how-anthropic-may-have-talked-itself-into-an-"
    "ai-export-ban/":
        "Can't read to check; same event as US → Anthropic, 2026-06-13",
    "https://siliconangle.com/2026/06/10/anthropics-dario-amodei-wants-governments-po"
    "wer-block-dangerous-ai-systems/":
        "A company's call for powers; no government action against a company",
    "https://the-decoder.com/claude-codes-complicated-china-problem-involves-bans-on-"
    "both-sides-of-the-pacific/":
        "Company bans only (Anthropic's terms, Alibaba's own staff); no government action",
    "https://the-decoder.com/taiwan-raids-super-micro-offices-in-probe-over-nvidia-ch"
    "ip-smuggling-to-china/":
        "Super Micro is a server maker, not an AI company; the company itself is not charged",
    "https://techcrunch.com/2026/07/10/apple-sues-openai-over-alleged-trade-secret-th"
    "eft/":
        "Private lawsuit",
    "https://the-decoder.com/google-files-first-joint-lawsuit-with-fbi-over-chinese-a"
    "i-scam-network-openai-blocks-prc-influence-clusters/":
        "Google sues a scam network; OpenAI's own bans; no government action against an AI company",
    "https://techcrunch.com/2026/06/12/chinese-cybercrime-operation-that-used-ai-to-s"
    "cam-hundreds-of-thousands-of-victims-sued-by-google/":
        "Google sues a scam network; no government action against an AI company",
    "https://arstechnica.com/tech-policy/2026/06/google-ordered-to-put-clearer-links-"
    "in-ai-search-and-let-uk-publishers-opt-out/":
        "same as UK → Google, 2026-06-03 (can't read to check)",
    "https://the-decoder.com/anthropic-bans-ai-tools-during-job-interviews-to-see-how"
    "-candidates-actually-think/":
        "A company's own hiring policy",
    "https://epic.org/privacy-daily-paxton-investigates-meta-ai-glasses-over-privacy-"
    "concerns/":
        "Can't read to check (page refused); a Texas AG probe of Meta's AI glasses, 2026-05-20",
    "https://arstechnica.com/tech-policy/2026/05/authors-fight-for-higher-payouts-fro"
    "m-anthropics-1-5b-copyright-settlement/":
        "Private lawsuit settlement",
    "https://siliconangle.com/2026/05/01/ai-lifts-clouds-even-higher-aws-moves-stack-"
    "elon-sam-battle-court/":
        "Weekly roundup; Musk v. OpenAI is a private suit",
    "https://arstechnica.com/tech-policy/2026/04/florida-probes-chatgpt-role-in-mass-"
    "shooting-openai-says-bot-not-responsible/":
        "Can't read to check; same event as Florida → OpenAI, 2026-04-09",
    "https://www.marktechpost.com/2026/06/02/how-to-fine-tune-lfm2-using-qlora-and-dp"
    "o-a-complete-step-by-step-coding-tutorial-on-google-colab/":
        "Not a government action",
    "https://www.marktechpost.com/2026/05/14/poetiqs-meta-system-automatically-builds"
    "-a-model-agnostic-harness-that-improved-every-llm-tested-on-livecodebench-pro-wi"
    "thout-fine-tuning/":
        "Not a government action",
    "https://huggingface.co/blog/amazon/foundation-model-building-blocks":
        "Not a government action",
    "https://the-decoder.com/amazon-brings-agentic-fine-tuning-to-sagemaker-with-supp"
    "ort-for-llama-qwen-deepseek-and-nova/":
        "Not a government action",
    "https://www.marktechpost.com/2026/04/24/a-coding-implementation-on-microsofts-op"
    "enmementos-with-trace-structure-analysis-context-compression-and-fine-tuning-dat"
    "a-preparation/":
        "Not a government action",
    "https://www.marktechpost.com/2026/04/20/a-coding-implementation-on-microsofts-ph"
    "i-4-mini-for-quantized-inference-reasoning-tool-use-rag-and-lora-fine-tuning/":
        "Not a government action",
    "https://www.marktechpost.com/2026/04/20/openai-scales-trusted-access-for-cyber-d"
    "efense-with-gpt-5-4-cyber-a-fine-tuned-model-built-for-verified-security-defende"
    "rs/":
        "Not a government action",
    "https://the-decoder.com/always-on-ray-ban-meta-glasses-powered-by-openclaw-speed"
    "-up-everyday-tasks-in-new-study/":
        "Not a government action",
    "https://siliconangle.com/2026/04/09/florida-ag-opens-probe-chatgpt-alleging-connection-fsu-shooting/":
        "same as Florida → OpenAI, 2026-04-09",
    "https://techcrunch.com/2026/04/10/anthropic-temporarily-banned-openclaws-creator-from-accessing-claude/":
        "A company acting on a user",
    "https://techcrunch.com/2026/04/10/stalking-victim-sues-openai-claims-c"
    "hatgpt-fueled-her-abusers-delusions-and-ignored-her-warnings/":
        "Private lawsuit",
    "https://siliconangle.com/2026/04/08/appeals-court-rejects-anthropics-bid-block-pentagon-blacklisting/":
        "same as the 2026-04-08 ruling on US → Anthropic, 2026-02-27",
    "https://the-decoder.com/us-appeals-court-refuses-to-block-pentagons-blacklisting-of-anthropic/":
        "same as the 2026-04-08 ruling on US → Anthropic, 2026-02-27",
    "https://arstechnica.com/tech-policy/2026/04/trump-appointed-judges-ref"
    "use-to-block-trump-blacklisting-of-anthropic-ai-tech/":
        "same as the 2026-04-08 ruling on US → Anthropic, 2026-02-27",
    "https://the-decoder.com/perplexity-ai-sued-over-alleged-data-sharing-with-meta-and-google/":
        "Private class action",
    "https://siliconangle.com/2026/03/26/judge-issues-block-pentagon-label-anthropic-supply-chain-risk/":
        "same as the 2026-03-27 ruling on US → Anthropic, 2026-02-27",
    "https://research.google/blog/vibe-coding-xr-accelerating-ai-xr-prototyping-with-xr-blocks-and-gemini/":
        "Not a government action",
    "https://techcrunch.com/2026/03/17/openai-expands-government-footprint-with-aws-deal/":
        "A deal between two companies (AWS to distribute OpenAI to government customers), no government signing",
    "https://arstechnica.com/tech-policy/2026/03/elon-musks-xai-sued-for-tu"
    "rning-three-girls-real-photos-into-ai-csam/":
        "Private lawsuit",
    "https://techcrunch.com/2026/03/16/merriam-webster-openai-encyclopedia-brittanica-lawsuit/": "Private lawsuit",
    "https://the-decoder.com/bytedance-secures-access-to-nvidia-blackwell-c"
    "luster-in-malaysia-circumventing-us-export-ban-on-china/":
        "Companies' deal, not a government action",
    "https://the-decoder.com/amazon-gets-court-order-blocking-perplexitys-ai-shopping-agent/":
        "A company's suit against a company",
    "https://siliconangle.com/2026/03/09/anthropic-sues-scrap-trump-administrations-claude-ban/":
        "A company suing the government; the ban is already held (US → Anthropic, 2026-02-27)",
    "https://the-decoder.com/despite-pentagon-ban-google-aws-and-microsoft-stick-with-anthropics-ai-models/":
        "Companies acting on their own; ban already held",
    "https://techcrunch.com/2026/03/07/openai-robotics-lead-caitlin-kalinowski-quits-in-response-to-pentagon-deal/":
        "An employee quitting; deal already held",
    "https://techcabal.com/2026/03/06/kenyan-watchdog-asks-regulator-to-probe-meta-ai-glasses/":
        "A rights group asking a regulator, no action by a government",
    "https://siliconangle.com/2026/03/06/anthropic-says-productive-discussions-pentagon-claude-but-plans-sue-ban/":
        "Talks only",
    "https://arstechnica.com/tech-policy/2026/03/musk-fails-to-block-califo"
    "rnia-data-disclosure-law-he-fears-will-ruin-xai/":
        "A company's suit against a state law, no order on a named company",
    "https://techcrunch.com/2026/03/06/claudes-consumer-growth-surge-continues-after-pentagon-deal-debacle/":
        "Business story; ban already held",
    "https://techcrunch.com/2026/03/04/father-sues-google-claiming-gemini-chatbot-drove-son-into-fatal-delusion/":
        "Private lawsuit",
    "https://ainowinstitute.org/news/12263": "Opinion; same as US (Pentagon) → OpenAI, 2026-02-28",
    "https://siliconangle.com/2026/03/03/openai-revises-pentagon-contract-address-surveillance-concerns/":
        "same as US (Pentagon) → OpenAI, 2026-02-28",
    "https://techcrunch.com/2026/03/01/openai-shares-more-details-about-its-agreement-with-the-pentagon/":
        "same as US (Pentagon) → OpenAI, 2026-02-28",
    "https://the-decoder.com/openai-calls-stuart-russell-a-doomer-in-court-"
    "after-its-ceo-co-signed-his-ai-extinction-warning/":
        "Private court case (Musk v. OpenAI)",
    "https://the-decoder.com/trump-orders-all-federal-agencies-to-drop-anth"
    "ropic-after-the-ai-company-refused-to-bend-its-terms-for-the-pentagon/":
        "same as US → Anthropic, 2026-02-27",
    "https://the-decoder.com/anthropic-refuses-pentagon-demand-to-loosen-mi"
    "litary-ai-restrictions-faces-defense-production-act-threat/":
        "Threat only",
    "https://the-decoder.com/elon-musks-ai-company-finally-blocks-nude-imag"
    "e-generation-following-pressure-from-regulators/":
        "A company acting on its own",
    "https://arstechnica.com/ai/2026/01/google-removes-some-ai-health-summa"
    "ries-after-investigation-finds-dangerous-flaws/":
        "A company acting on its own after a newspaper investigation",
    "https://the-decoder.com/china-investigates-metas-manus-acquisition-for-export-control-violations/":
        "Reported by the Financial Times only, not confirmed in the story",
}

# a LEFT_OUT comment starting with this is pledge news (a country joining a pledge or ratifying the treaty): the lists
# above change only from the official list, so the note asks the owner for it
PLEDGE_NEWS = "pledge:"
# the newest day every story was read for the lists above; the candidates start after it
CHECKED_TO = "2026-10-17"
_GOV = re.compile(r"\b(government|ministry|minister|Pentagon|White House|Trump|regulator|watchdog|FTC|DOJ|attorneys? "
                  r"general|AG|Ofcom|CMA|Commission|court|judge|state|federal|declaration|pledge|summit|treaty|"
                  r"Framework Convention)\b", re.I)
# a strong action counts on its own; a weaker one only beside a government word
_ACTS = re.compile(r"\b(bans?|banned|blocks?|blocked|orders?|ordered|fines?|fined|probes?|investigat\w*|sues|sued|"
                   r"MoU|MOU|memorandum|cease-and-desist)\b", re.I)
_DOES = re.compile(r"\b(deal|agreement|accord|contract|signs?|signed|lifts?|suspends?|restrict\w*|approval)\b", re.I)
_COMPANY = re.compile(r"\b(OpenAI|ChatGPT|Anthropic|Claude|Google|DeepMind|Gemini|Meta|Microsoft|Nvidia|xAI|Grok|"
                      r"Mistral|DeepSeek|Amazon|AWS|Apple|Perplexity|Cohere)\b")
_PLEDGE = re.compile(r"\b(Bletchley|Seoul Declaration|Paris (statement|declaration)|New Delhi Declaration|"
                     r"Framework Convention on (AI|Artificial Intelligence))\b", re.I)


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Stories from after CHECKED_TO (or `since`, if later) that no row uses and LEFT_OUT doesn't hold: a government
    acting on or with an AI company, or a country joining a pledge. One per event, newest first."""
    since = max(since, CHECKED_TO + "~")  # '~' sorts after any time of day, so CHECKED_TO itself is done
    used = {u for r in DEALS + ORDERS for u in r[-1:]} | {u for b in BANS for u in (b[4], b[6]) if u} | set(LEFT_OUT)
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["date"] >= since and c.get("category") != "research"
            and not any(s["url"] in used for s in [c, *(c.get("also") or [])])
            and (_PLEDGE.search(c["title"]) or (_COMPANY.search(c["title"]) and (
                _ACTS.search(c["title"]) or (_GOV.search(c["title"]) and _DOES.search(c["title"])))))]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a pacts/<day> branch: each row it adds, and the stories it left out; None when it
    adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("DEALS", "BANS", "ORDERS", "LEFT_OUT"))
    rows = ([(d, g, c, "Deal", w, u) for d, g, c, w, u in DEALS if u not in had["DEALS"]]
            + [(b[0], b[1], b[2], "Ban or hold", b[3] + (f" (ended {b[5]}: {b[7]})" if b[5] else ""), b[4])
               for b in BANS if b[4] not in had["BANS"] or (b[6] and b[6] not in had["BANS"])]
            + [(d, g, c, k, w, u) for d, g, c, k, w, u in ORDERS if u not in had["ORDERS"]])
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    # a country joining a pledge or ratifying the treaty: shown to the owner, who adds it from the official list
    rows += [("", "", "", "Pledge news: check the official list", LEFT_OUT[u][len(PLEDGE_NEWS):].strip(), u)
             for u in dropped if LEFT_OUT[u].startswith(PLEDGE_NEWS)]
    dropped = [u for u in dropped if not LEFT_OUT[u].startswith(PLEDGE_NEWS)]
    if not rows and not dropped:
        return None
    return approve.note("AI pacts and orders", f"row{'s' * (len(rows) != 1)}", branch,
                        ("Day", "Government", "Company", "Kind", "What", "Source"), rows, dropped)


def _day(d: str) -> date:
    return date.fromisoformat(d)


def _short(d: str) -> str:
    x = _day(d)
    return f"{x.day} {x:%b}"


def _names(p: tuple) -> set[str]:
    return {SAME.get(n, n) for n in p[4]} | {SAME.get(n, n) for n in p[5]}


def _pledges() -> list[tuple]:
    return [p for p in PLEDGES if p[4]]


def _and(xs: list[str]) -> str:
    xs = [SAY.get(x, x) for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


YES, NO = '<i class="pc-y" title="signed"></i>', '<i class="pc-n" title="didn&#39;t sign"></i>'
PIN = ' class="pc-focus"'
RAT = '<i class="pc-y pc-rat" title="ratified {}"></i>'


def _ratified(p: tuple) -> dict[str, str]:
    return {SAME.get(n, n): d for n, d in RATIFIED.get(p[0], {}).items()}


SHORT = {"United States": "US", "United Kingdom": "UK"}


def _box(cls: str, title: str, question: str, inner: str) -> str:
    """One section of the page: a coloured heading with its plain question, then its table."""
    return (f'<section class="pc-half {cls}"><div class="pc-hh"><h2>{title}</h2><p>{escape(question)}</p></div>'
            f'<div class="pc-in">{inner}</div></section>')


def _head(*cols: str) -> str:
    return "<thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead>"


def _story(u: str) -> str:
    return f'<span class="fx-c"><a href="{escape(u)}" rel="noopener">story</a></span>'


def _pledges_box(pl: list[tuple]) -> str:
    """The pledges and the treaty, a row each: when, how many signed, and whether the US, the UK and China did; every
    country's answer folded below."""
    sets = [_names(p) for p in pl]
    most = max(range(len(pl)), key=lambda i: len(sets[i]))
    lead = f"{pl[most][0]} ({pl[most][1][-4:]}) has the most signers: {len(sets[most])} countries and bodies."
    rows = ""
    for p, s in zip(pl, sets):
        who = "".join(f'<span class="pc-k pc-yes">{SHORT.get(c, c)} signed</span>' if c in s else
                      f'<span class="pc-k pc-no">{SHORT.get(c, c)} didn\'t sign</span>' for c in FOCUS)
        bind = (f'<span class="fx-c">Binding treaty: law once {IN_FORCE_AT} countries ratify; {len(_ratified(p))} '
                'so far</span>' if p[0] in RATIFIED else "")
        rows += (f'<tr><td class="pc-d">{p[1]}</td><td><b>{escape(p[0])}</b>{bind}</td>'
                 f'<td><b>{len(s)}</b> countries and bodies</td>'
                 f'<td class="pc-who">{who}<span class="fx-c"><a href="{escape(p[2])}" rel="noopener">official list'
                 f'</a></span></td></tr>')
    rats = [_ratified(p) for p in pl]
    every = set().union(*sets)
    rest = sorted(every - set(FOCUS), key=lambda c: (-sum(c in s for s in sets), c))
    head = "<tr><th scope=\"col\">Country or body</th>" + "".join(
        f'<th scope="col">{escape(p[0])}<small>{p[1][-4:]}</small></th>' for p in pl) + "</tr>"

    def row(c: str, focus: bool) -> str:
        cells = "".join(f'<td>{RAT.format(r[c]) if c in r else YES if c in s else NO}</td>' for s, r in zip(sets, rats))
        return f'<tr{PIN if focus else ""} data-name="{escape(c.lower())}"><th scope="row">{escape(c)}</th>{cells}</tr>'
    grid = (f'<div class="pc-gw"><table class="pc-grid"><thead>{head}</thead><tbody>'
            + "".join(row(c, True) for c in FOCUS) + "".join(row(c, False) for c in rest) + "</tbody></table></div>")
    later = [f"{c} joined {p[0]} on {d}" for p in pl for c, d in p[5].items()]
    return _box("pc-pacts", "Pledges", "Which AI pledges have governments signed?",
                f'<p class="pc-lead">{escape(lead)}</p>'
                f'<table class="pc-rows fx-t">{_head("Signed", "Pledge", "Signed by", "The US, the UK and China")}'
                f'<tbody>{rows}</tbody></table>'
                f'<details class="pc-every"><summary>See every country ({len(every)})</summary>'
                '<input class="pc-find" type="search" placeholder="Find a country" aria-label="Find a country">'
                f'{grid}<p class="pc-key"><span><i class="pc-y"></i> signed</span>'
                + ('<span><i class="pc-y pc-rat"></i> ratified</span>' if any(rats) else "")
                + '<span><i class="pc-n"></i> didn\'t sign</span></p>'
                + (f'<p class="pc-key">{escape("; ".join(later))}.</p>' if later else "") + "</details>")


def _deals_box(deals: list[tuple]) -> str:
    rows = "".join(f'<tr><td class="pc-d">{_short(d)}</td><td><b>{escape(g)}</b></td><td>{escape(c)}</td>'
                   f'<td>{escape(w)}{_story(u)}</td></tr>' for d, g, c, w, u in deals)
    return _box("pc-pacts", "Deals", f"What have governments agreed with AI companies? · {len(deals)} in "
                f"{_day(deals[0][0]).year}",
                f'<table class="pc-rows fx-t">{_head("Date", "Government", "Company", "The deal")}<tbody>{rows}'
                "</tbody></table>")


# where a ban stands, as AI fines and bans tags it: (tag, colour class)
STANDS = {"in": ("In force", "fx-in"), "lifted": ("Lifted", "fx-li"), "court": ("Challenged in court", "fx-ch"),
          "final": ("Final", "fx-aw")}


def _stands(end: str | None, start: str, marks: list) -> tuple[str, str]:
    return STANDS["final" if end == start else "lifted" if end else "court" if marks else "in"]


def _bans_box(bans: list[tuple], today: date) -> str:
    rows = ""
    for d, g, c, w, u, end, eu, enote, marks in bans:
        tag, cls = _stands(end, d, marks)
        after = ""
        if end and end != d:
            after = (f'<span class="fx-c"><a href="{escape(eu)}" rel="noopener">{escape(_cap(enote))} {_short(end)}'
                     f'</a>, after {(_day(end) - _day(d)).days} days</span>')
        if marks:
            after += ("<details><summary>" + f"{len(marks)} court ruling{'s' if len(marks) > 1 else ''}</summary>"
                      + "".join(f"<p>{_short(md)}: {escape(mt)}</p>" for md, mt in marks) + "</details>")
        rows += (f'<tr><td class="pc-d">{_short(d)}</td><td><b>{escape(g)}</b></td><td>{escape(c)}</td>'
                 f'<td>{escape(w)}{_story(u)}</td><td class="fx-s"><span class="pc-k {cls}">{tag}</span>{after}</td></tr>')
    return _box("pc-orders", "Bans", f"Which AI products have governments stopped? · {len(bans)} in {today.year}",
                f'<table class="pc-rows fx-t">{_head("Began", "Government", "Company", "What", "Where it stands")}'
                f"<tbody>{rows}</tbody></table>")


def _orders_box(orders: list[tuple], today: date) -> str:
    kinds = {"Order": "pc-ord", "Investigation": "pc-inv", "Court case": "pc-crt"}
    rows = "".join(f'<tr><td class="pc-d">{_short(d)}</td><td><b>{escape(g)}</b></td><td>{escape(c)}</td>'
                   f'<td>{escape(w)}{_story(u)}</td><td class="fx-s"><span class="pc-k {kinds[k]}">{k}</span></td></tr>'
                   for d, g, c, k, w, u in orders)
    return _box("pc-orders", "Orders and investigations", "What have governments ordered AI companies to do, or "
                f"looked into? · {len(orders)} in {today.year}",
                f'<table class="pc-rows fx-t">{_head("Date", "Government", "Company", "What", "Kind")}'
                f"<tbody>{rows}</tbody></table>")


_JS = """<script>(()=>{const f=document.querySelector('.pc-find');if(!f)return;
f.addEventListener('input',()=>{const q=f.value.trim().toLowerCase();
document.querySelectorAll('.pc-grid tbody tr').forEach(r=>{r.hidden=!!q&&!r.dataset.name.includes(q)})})})()</script>"""


def body(cards: list[dict], today: date) -> str:
    """The page's four sections, each row kept only if its story is among the site's cards (the official lists always)."""
    have = {s["url"] for c in cards for s in [c, *(c.get("also") or [])]}
    year = str(today.year)
    deals = [r for r in DEALS if r[-1] in have and r[0][:4] == year]
    bans = [b for b in BANS if b[4] in have and b[0][:4] == year]
    orders = [r for r in ORDERS if r[-1] in have and r[0][:4] == year]
    limits = [
        ("Pledges", "The summit statements bind no one in law; the Council of Europe's AI treaty binds each country "
         f"that ratifies it, once {IN_FORCE_AT} have. Who signed is as each official list gives it, a country's name "
         "written one way across the lists."),
        ("Deals, bans, orders", "Something a government did to or with a named AI company, each checked by hand "
         "against the story that reported it, which each row links. Talks, reported plans and threats are left out "
         "until they happen. Bans and fines a regulator decided under the law are on AI fines and bans."),
        ("Courts", "Only cases a government brought or answers; every other AI case is in AI in court."),
    ]
    return ('<div class="ft jb pc">\n'
            + pages.feature_head(PATH, "AI pacts and orders",
                                 "What have governments signed on AI, and what have they made AI companies do?",
                                 "The AI pledges and the AI treaty, from each official list of who signed; deals, bans, "
                                 "orders and investigations from our stories, each checked by hand.")
            + '<div class="pc-stack">' + _pledges_box(_pledges()) + (_deals_box(deals) if deals else "")
            + (_bans_box(bans, today) if bans else "") + (_orders_box(orders, today) if orders else "") + "</div>\n"
            '<section class="jb-lim"><h2>About these rows</h2>\n<table class="mt jb-small jb-limits"><tbody>'
            + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
            + f"</tbody></table></section></div>\n{_JS}")


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    what = ("What have governments signed on AI, and what have they made AI companies do? The summit pledges and who "
            "signed each, and every deal, ban, order and investigation between a government and an AI company.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI pacts and orders",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("AI pacts and orders · AI Pulse", what, PATH, body(cards, today), data, pages.frame(conn, len(cards)),
                   ("/policy/", "Back to Policy"),
                   "Pledges and the treaty as each official list gives them; every other row links to the story that reported it, "
                   "checked by hand."),
        encoding="utf-8")
    return [PATH]
