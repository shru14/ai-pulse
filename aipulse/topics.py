"""Topics: storylines AI Pulse follows over time (topics/), laws and news together, a page each (topics/<slug>/).

Each topic is a rule kept by hand: the tracked bills it follows (their stages are its official record) and the words
a story must have (`words`, in its headline or summary) and must not (`exclude`). A card joins a topic when it matches
the words; a tracked bill's own card joins only the topics that list it, so a US bill named "... AI Act" never lands in
the EU AI Act's story. Research papers stay in Research. A topic with nothing new for QUIET_DAYS is tagged Concluded.

The words decide; a topic's `net` of tags only catches what they miss. A story carrying one of those sets of tags that
the words don't match is a candidate (`python -m aipulse topics`): the daily job drafts each into ADDED or LEFT_OUT on a
topics/<day> branch, and it joins a topic only when the owner merges that.

The stories are the outlets' own headlines, so a topic's page loads them in the reader's browser from its events.json,
as the industry pages do; the page itself holds only our own words.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import countries, pages, rss

QUIET_DAYS = 90  # a topic with no new event for this long is Concluded (kept, never deleted)
# Topics are ranked by how much they're in the news: over the last TREND_DAYS, each event counts once per outlet that
# carried it, and three times over in the last HOT_DAYS. The top TRENDING with an event in the last HOT_DAYS are tagged.
TREND_DAYS, HOT_DAYS, TRENDING = 30, 7, 3
FRONT = 3  # topics the front page shows
STREAMS = ("news", "policy", "regulation", "infra", "tool")  # not research: papers aren't events

# slug: name, kind (the block's label), what (our own words), bills, words, exclude, net (sets of story tags that may
# mean the topic), related topics
TOPICS = {
    "eu-ai-act": dict(
        name="EU AI Act", kind="Law",
        what="The EU's law on AI: its adoption, the rules for general-purpose models, and the Digital Omnibus that "
             "amended it.",
        bills=("EU-2021-0106", "EU-2025-0359"),
        words=r"\bEU AI Act\b|\bEuropean AI Act\b|\bAI Act\b.{0,80}\b(EU|Europe|European|Brussels|Commission|GPAI)\b"
              r"|\b(EU|Europe|European|Brussels|Commission)\b.{0,80}\bAI Act\b|\bGPAI\b|general[- ]purpose AI code"
              r"|\bEU AI Office\b|Digital Omnibus|\bharmoni[sz]ed standards?\b.{0,80}\bAI Act\b",
        net=({"AI Act"}, {"European Union", "Regulation"})),
    "nvidia-chips-china": dict(
        name="Nvidia chips to China", kind="Trade",
        what="US rules on selling AI chips to China, and how Nvidia, Beijing and other countries responded.",
        bills=("US-119-hr-5885", "US-119-s-3150"),
        words=r"\b(H20|H200|Blackwell|Nvidia|AI chips?)\b.{0,60}\b(China|Chinese|Beijing|exports?)\b"
              r"|\b(China|Chinese|Beijing)\b.{0,60}\b(H20|H200|Nvidia)\b|export controls?.{0,40}\b(chips?|AI)\b"
              r"|\bchip exports?\b|\bGAIN AI Act\b",
        net=({"Nvidia", "China"}, {"Chips", "China"}, {"Export Controls"})),
    "anthropic-pentagon": dict(
        name="Anthropic and the Pentagon", kind="Company",
        what="Anthropic's dispute with the US Department of Defense over military use of Claude, and the "
             "supply-chain-risk label that followed.",
        words=r"\bAnthropic\b.{0,120}\b(Pentagon|Department of War|Defense Department|Department of Defense|Hegseth"
              r"|supply[- ]chain risk)\b|\b(Pentagon|Department of War|Hegseth)\b.{0,120}\bAnthropic\b",
        net=({"Anthropic", "Defense"},)),
    "chatbots-teens": dict(
        name="Chatbots and teens", kind="Safety",
        what="Lawsuits, laws and company changes over how AI chatbots treat children and teenagers.",
        bills=("US-119-hr-10719", "US-119-hr-8382", "US-119-s-5171"),
        words=r"\bCharacter\.AI\b.{0,100}\b(teens?|teenagers?|minors?|under-18s?|child|children|kids|suicide|parents?"
              r"|lawsuits?|suit|sues?|sued|settle\w*|FTC|attorneys? general)\b"
              r"|\b(teens?|teenagers?|minors?|children|kids|young people|suicide|parents?|lawsuits?|sues?|sued)\b.{0,100}\bCharacter\.AI\b"
              r"|\bCharacter\.AI\b.{0,100}\byoung people\b"
              r"|\b(chatbots?|ChatGPT|AI companions?)\b.{0,60}\b(teens?|teenagers?|minors?|child"
              r"|children|kids|suicide)\b|\b(teens?|teenagers?|minors|children|kids)\b.{0,40}\b(chatbots?|AI "
              r"companions?)\b|ChatGPT for Teens|\bSB ?243\b",
        net=({"Character.AI"},),
        related=("grok-deepfakes", "california-ai-laws")),
    "copyright-court": dict(
        name="AI training and copyright in court", kind="Courts",
        what="Court cases and settlements over training AI on copyrighted books, music, news and images.",
        words=r"\b(copyright|fair use)\b.{0,80}\b(lawsuit|suit|court|ruling|rules|judge|settle\w*|sues?|sued|trial)\b"
              r"|\b(lawsuit|court|ruling|judge|settle\w*|sues?|sued)\b.{0,80}\b(copyright|fair use)\b|\bBartz\b",
        net=({"Copyright", "Law"},)),
    "grok-deepfakes": dict(
        name="Grok deepfakes", kind="Safety",
        what="The sexualised images made with xAI's Grok, and the bans, orders and lawsuits that followed.",
        words=r"\bGrok\b.{0,80}\b(deepfakes?|sexual\w*|obscene|nude|undress\w*|nonconsensual|CSAM|child)\b"
              r"|\b(ban|bans|banned|block|blocks|blocked)\b.{0,40}\bGrok\b",
        net=({"xAI", "Deepfakes"}, {"xAI", "Law"}),
        related=("chatbots-teens",)),
    "openai-restructuring": dict(
        name="OpenAI's restructuring", kind="Company",
        what="OpenAI's move from a nonprofit-controlled lab to a for-profit company, and the deals and challenges "
             "along the way.",
        words=r"\bOpenAI\b.{0,60}\b(restructur\w*|for-profit|nonprofit|non-profit|public benefit corporation"
              r"|recapitali[sz]\w*)\b",
        net=({"OpenAI", "Law"},),
        related=("musk-v-openai",)),
    "musk-v-openai": dict(
        name="Musk v. OpenAI", kind="Courts",
        what="Elon Musk's lawsuit against OpenAI and Sam Altman, from filing to trial and verdict.",
        words=r"\bMusk\b.{0,60}\b(lawsuit|suit|trial|sues?|sued|jury|court|deposition|testif\w*)\b.{0,60}\bOpenAI\b"
              r"|\bOpenAI\b.{0,60}\b(lawsuit|trial|jury|deposition)\b.{0,40}\bMusk\b|Musk-OpenAI trial"
              r"|\bMusk v\.? OpenAI\b",
        net=({"OpenAI", "xAI"}, {"OpenAI", "Law"}),
        related=("openai-restructuring",)),
    "california-ai-laws": dict(
        name="California's AI laws", kind="Law",
        what="California's AI bills and orders: SB 53 on frontier AI safety, SB 243 on companion chatbots, and what "
             "came after.",
        words=r"\bSB ?53\b|\bSB ?243\b|\bSB ?1047\b|\bNewsom\b.{0,60}\bAI\b|\bAI\b.{0,40}\bNewsom\b"
              r"|\bCalifornia\b.{0,40}\bAI (law|laws|bill|bills|safety)\b|\bCalifornia\b.{0,40}\b(law|bill)\b.{0,60}\bAI\b",
        net=({"United States", "Regulation"},),
        related=("us-state-preemption", "chatbots-teens")),
    "us-state-preemption": dict(
        name="US preemption of state AI laws", kind="Law",
        what="The federal push to stop US states from passing their own AI laws: the moratorium, the executive "
             "orders and the pushback.",
        bills=("US-119-s-3557",),
        words=r"\bpreempt\w*.{0,40}\b(state|AI)\b|\bstate AI laws?\b|\bmoratorium on state|block states.{0,40}\bAI\b"
              r"|\bone rulebook\b",
        net=({"United States", "Regulation"},),
        related=("california-ai-laws",)),
    "data-centre-power-bills": dict(
        name="Data centres and power bills", kind="Energy",
        what="Who pays for the electricity AI data centres need: pledges, bills and grid limits.",
        bills=("US-119-hr-6529",),
        words=r"\bdata cent(er|re)s?\b.{0,60}\b(electricity|energy costs?|power bills?|ratepayers?|grid)\b"
              r"|\b(electricity|power) (bills?|prices?)\b.{0,40}\bdata cent(er|re)s?\b",
        exclude=r"\bbatter(y|ies)\b",
        net=({"Power & grid", "Rules & permits"}, {"Power & grid", "Energy"}, {"Power & grid", "Land & local pushback"}),
        related=("stargate",)),
    "stargate": dict(
        name="Stargate", kind="Infrastructure",
        what="OpenAI's data centre venture with SoftBank and Oracle, site by site.",
        words=r"\bStargate\b",
        net=({"OpenAI", "Compute & Data Centers"}, {"OpenAI", "Builds & deals"}, {"OpenAI", "Oracle"}),
        related=("data-centre-power-bills",)),
    "apple-google-siri": dict(
        name="Apple, Google and Siri", kind="Company",
        what="Apple's deal to rebuild Siri on Google's Gemini models.",
        words=r"\bSiri\b.{0,60}\bGemini\b|\bGemini\b.{0,60}\bSiri\b|\bApple\b.{0,40}\bGoogle\b.{0,40}\b(Siri|deal)\b",
        net=({"Apple", "Google"},)),
    "korea-ai-basic-act": dict(
        name="South Korea's AI Basic Act", kind="Law",
        what="South Korea's AI law, its enforcement decree and the guidelines that put it into practice.",
        words=r"\bAI Basic Act\b|\bKorea\w*\b.{0,40}\bAI (law|act)\b",
        net=({"South Korea", "Regulation"}, {"South Korea", "Law"})),
    "claude-mythos": dict(
        name="Anthropic's Mythos", kind="Safety",
        what="Anthropic's Mythos model, kept back over its hacking skills: who gets to use it, and what it found.",
        words=r"\bMythos\b", exclude=r"\bMythos Ventures\b",
        net=({"Anthropic", "Security"},)),
    "ai-ipos": dict(
        name="OpenAI and Anthropic go public", kind="Markets",
        what="The two biggest AI labs' road to the stock market: filings, hires and delays.",
        words=r"\b(OpenAI|Anthropic)\b.{0,40}\bIPO\b|\bIPO\b.{0,40}\b(OpenAI|Anthropic)\b",
        net=({"IPO", "OpenAI"}, {"IPO", "Anthropic"}),
        related=("openai-restructuring",)),
    "deepseek-us": dict(
        name="DeepSeek and the US", kind="Trade",
        what="How Washington and US labs answered DeepSeek: bans, chip questions and claims it copied their models.",
        words=r"\bDeepSeek\b.{0,80}\b(ban|banned|bans|security|exports?|distill\w*|Nvidia|chips?|probe|investigat\w*"
              r"|Commerce|Congress|White House|Sacks)\b|\b(ban|bans|banned|banning)\b.{0,40}\bDeepSeek\b|\b(remove|removal of|removing)\s+DeepSeek\b"
              r"|\bdistillation (campaigns?|attacks?)\b",
        exclude=r"\bR1-Distill|\bdistilled (new )?(R1|model)",
        net=({"DeepSeek", "United States"}, {"DeepSeek", "Chips"}),
        related=("nvidia-chips-china",)),
    "meta-superintelligence": dict(
        name="Meta's superintelligence push", kind="Company",
        what="Meta's bid to catch up in AI: the Scale AI deal, the hiring spree and its superintelligence lab.",
        words=r"\bMeta\b.{0,60}\b(superintelligence|MSL|Scale AI|Alexandr Wang|poach\w*)\b"
              r"|\bSuperintelligence Labs\b|\bScale AI\b.{0,60}\bMeta\b",
        net=({"Meta", "Compute & Data Centers"},)),
    "openai-device": dict(
        name="OpenAI's device", kind="Company",
        what="OpenAI's first hardware, designed with Jony Ive after it bought his company io.",
        words=r"\bOpenAI\b.{0,60}\b(device|hardware|gadget|smart speaker|Jony Ive)\b|\bJony Ive\b.{0,60}\bOpenAI\b",
        exclude=r"\b(recording|surveillance|covert) devices?\b|\bspy\b|\bplant(ed|ing|s)?\b.{0,20}\bdevices?\b|\b(prosecutors?|FBI|DOJ|arrest\w*)\b"
                r"|\b(AMD|Broadcom)\b|\bhardware-efficient\b|\bverification device\b|\bWorld\b.{0,30}\b(Orb|verification)\b",
        net=({"OpenAI", "Apple"}, {"OpenAI", "Hardware & compute"})),
    "ai-music-labels": dict(
        name="Suno, Udio and the record labels", kind="Courts",
        what="The record labels' fight with AI music makers Suno and Udio, from lawsuits to licensing deals.",
        words=r"\b(Suno|Udio)\b.{0,80}\b(labels?|Warner|Universal|Sony|UMG|lawsuits?|sues?|sued|settle\w*|licens\w*"
              r"|deals?|GEMA|court|copyright)\b|\b(labels?|Warner|Universal|Sony|UMG|GEMA)\b.{0,80}\b(Suno|Udio)\b",
        related=("copyright-court",)),
    "ai-summits": dict(
        name="Global AI summits", kind="Policy",
        what="The meetings where governments try to agree on AI, from Bletchley Park to Paris and New Delhi.",
        words=r"\b(AI Action Summit|AI Impact Summit|Bletchley|Seoul AI Summit|AI Safety Summit)\b"
              r"|\bIndia\b.{0,30}\bAI summit\b|\bParis\b.{0,30}\bAI summit\b",
        net=({"Governance", "International bodies"},)),
    "ai-bubble": dict(
        name="AI bubble talk", kind="Markets",
        what="Whether AI spending has run ahead of its returns: bubble warnings, circular deals and what markets did.",
        words=r"\bAI bubble\b|\bbubble\b.{0,40}\bAI\b|\bcircular (deals?|financing)\b",
        exclude=r"\bBubble (launches|raises|adds|lets|unveils)\b"),
    "google-antitrust-ai": dict(
        name="Google's antitrust cases and AI", kind="Courts",
        what="Google's search monopoly cases, and how AI changed the remedies and the complaints against it.",
        words=r"\bGoogle\b.{0,80}\b(antitrust|monopoly|Mehta|remed(y|ies))\b|\b(antitrust|monopoly)\b.{0,60}\bGoogle\b",
        net=({"Google", "Antitrust"},)),
    "perplexity-legal": dict(
        name="Perplexity's legal fights", kind="Courts",
        what="The publishers and companies taking Perplexity to court over its AI search and shopping agents.",
        words=r"\bPerplexity\b.{0,80}\b(sues?|sued|lawsuits?|suit|court|cease|judge|block\w*)\b"
              r"|\b(sues?|sued|lawsuits?|blocks?)\b.{0,60}\bPerplexity\b",
        net=({"Perplexity", "Law"},),
        related=("copyright-court",)),
    "openai-microsoft": dict(
        name="OpenAI and Microsoft", kind="Company",
        what="The partnership behind ChatGPT, renegotiated as OpenAI grew: stakes, exclusivity and the AGI clause.",
        words=r"\bOpenAI\b.{0,60}\bMicrosoft\b.{0,60}\b(partnership|deal|renegotiat\w*|AGI clause|stake|contract"
              r"|exclusiv\w*|blessing)\b|\bMicrosoft\b.{0,60}\bOpenAI\b.{0,60}\b(partnership|renegotiat\w*|AGI clause"
              r"|stake|exclusiv\w*)\b|\bMicrosoft\b.{0,60}\brevenues?\b.{0,40}\bOpenAI\b|\bOpenAI\b.{0,60}\bMicrosoft'?s? revenues?\b",
        net=({"OpenAI", "Microsoft"},),
        related=("openai-restructuring",)),
}

# Each topic's picture is our own cartoon, templates/photos/cartoons/<slug>.svg (no real people, no logos). LOOK holds
# the flags of the places whose laws it follows (beside its tracked bills' own). The logos come from its stories (brands.py).
LOOK = {
    "eu-ai-act": ("EU",),
    "nvidia-chips-china": ("US", "CN"),
    "anthropic-pentagon": ("US",),
    "chatbots-teens": (),
    "copyright-court": (),
    "grok-deepfakes": (),
    "openai-restructuring": (),
    "musk-v-openai": (),
    "california-ai-laws": ("US",),
    "us-state-preemption": ("US",),
    "data-centre-power-bills": (),
    "stargate": ("US",),
    "apple-google-siri": (),
    "korea-ai-basic-act": ("KR",),
    "claude-mythos": (),
    "ai-ipos": (),
    "deepseek-us": ("US", "CN"),
    "meta-superintelligence": (),
    "openai-device": (),
    "ai-music-labels": (),
    "ai-summits": (),
    "ai-bubble": (),
    "google-antitrust-ai": ("US",),
    "perplexity-legal": (),
    "openai-microsoft": (),
}
# Stories the words miss, checked by hand and approved: slug: {url: why it belongs, in our own words}
ADDED: dict[str, dict[str, str]] = {
    "ai-ipos": {
        "https://techcrunch.com/2026/10/30/anthropic-expected-to-receive-high-junk-rating-from-credit-agencies-following-ipo-report-says/": "Report on the credit rating Anthropic is expected to get after its IPO",
        "https://olhardigital.com.br/2026/10/15/pro/anthropic-investidores-reduzem-expectativa-de-avaliacao-para-ipo-de-r-8-1-trilhoes/": "Investors lower their valuation hopes for Anthropic's planned November IPO",
    },
    "deepseek-us": {
        "https://techcrunch.com/2026/10/22/deepseek-reportedly-raises-15b-days-after-us-restrictions/": "DeepSeek's reported $15B raise came days after the US ordered federal agencies to remove its technology",
    },
    "openai-device": {
        "https://olhardigital.com.br/2026/10/14/pro/openai-acusa-ex-funcionario-de-enviar-arquivos-secretos-a-apple/": "OpenAI accuses a former employee of sending trade secrets to Apple over new AI devices",
        "https://olhardigital.com.br/2026/10/13/pro/justica-obriga-openai-a-entregar-documentos-de-contratacao-em-processo-da-apple/": "Court orders OpenAI to hand over hiring documents in the Apple trade-secrets dispute over hardware products",
    },
    "data-centre-power-bills": {
        "https://www.canarymedia.com/articles/data-centers/virginia-new-energy-plan-ai-boom": "Virginia's new energy plan on utility bills and electricity demand from the AI boom",
    },
}
# Stories a topic's net caught that don't belong, checked by hand
LEFT_OUT: set[str] = {
    # data-centre pollution lawsuit under the Clean Air Act, not about Grok images
    "https://techcrunch.com/2026/10/31/judge-allows-naacp-lawsuit-over-xai-data-center-pollution-to-move-forward/",
    # opinion piece, reports nothing new in a case
    "https://www.eff.org/deeplinks/2026/10/rewriting-copyright-law-generative-ai-would-hurt-everyone",
    # company advocacy post, not a development in this storyline
    "https://openai.com/index/fair-use-benefits-everyone",
    # energy MOU for data centres, not about who pays or grid limits
    "https://w.media/dayone-sembcorp-collaborate-on-energy-solutions-for-dayones-asian-data-centers/",
    # Chinese labs targeting OpenAI's model, only shares tags with the topic
    "https://the-decoder.com/openais-astra-becomes-the-main-target-for-chinese-ai-labs-after-anthropic-tightens-its-defenses/",
    # shadow AI risk piece, shares only tags
    "https://www.itweb.co.za/article/its-in-the-shadows-unsanctioned-ai-tools-are-a-pervasive-risk-to-the-business/Pero3MZ3VjpqQb6m",
    # wrongful-death lawsuit against OpenAI, not about restructuring or the Musk case
    "https://olhardigital.com.br/2026/10/28/inteligencia-artificial/chatgpt-teria-orientado-mulher-a-abandonar-remedio-antes-de-morte-diz-processo/",
    # product launch, not a development in the IPO storyline
    "https://techcrunch.com/2026/10/28/anthropic-just-launched-tools-to-show-companies-what-their-ai-spending-is-buying/",
    # grid access incentive in the UK, can't tell from the summary that it fits
    "https://www.channelnewsasia.com/business/uks-healey-offers-grid-access-incentives-critical-data-centres-6500146",
    # security incident, summary doesn't mention Mythos or the Pentagon
    "https://the-decoder.com/ai-agents-hacked-anthropic-maker-of-arguably-the-most-capable-ai-models-for-cyberdefense/",
    # national renewable mandate, not about who pays or grid limits
    "https://w.media/malaysia-affirms-30-per-cent-minimum-renewable-energy-mandate-for-data-centers/",
    # wrongful-death lawsuit against OpenAI, not about restructuring or the Musk case
    "https://techcrunch.com/2026/10/27/parents-sue-openai-alleging-gpt-4o-coached-their-daughter-off-seizure-medication/",
    # analysis piece, reports nothing new about the IPO or state laws
    "https://www.engadget.com/2298214/anthropics-political-problem-will-get-worse-before-it-gets-better/",
    # Oracle product news, not about Stargate
    "https://openai.com/index/oracle-apps-in-chatgpt",
    # energy supply deal, not about who pays or grid limits
    "https://w.media/nxera-sembcorp-ink-deal-for-green-energy-supply-to-nxera-data-centers/",
    # consumer GPU supply story, not about US chip rules
    "https://www.xataka.com/componentes/rtx-5090-se-fabricaron-para-jugar-china-han-encontrado-negocio-mejor-desmontarlas-para-ia",
    # Meta engineering post, not about its superintelligence push
    "https://engineering.fb.com/2026/10/26/open-source/ocp-summit-2026-meta-networking-talks/",
    # Denmark deepfake plan, not about Grok
    "https://www.xataka.com/privacidad/dinamarca-tiene-plan-deepfakes-blindar-voz-rostro-sus-ciudadanos-ia",
    # election study of chatbots, not about the Musk case
    "https://techcrunch.com/2026/10/24/forced-to-pick-groks-ai-model-chooses-republicans-openais-picks-democrats/",
    # interview, summary doesn't mention Mythos
    "https://www.xataka.com/seguridad/van-a-empeorar-mucho-jason-clinton-subdirector-ciberseguridad-anthropic-advierte-que-esta-venir",
    # OpenAI security post, not about Stargate
    "https://openai.com/index/securing-our-frontier-model-training-environment",
    # podcast roundup, nothing on chatbots and teens
    "https://www.404media.co/podcast-reverse-engineer-anything-is-the-next-wave-of-ai-slop/",
    # safety blog, only shares tags with the topic
    "https://www.aisi.gov.uk/blog/investigating-alignment-failures-in-aisis-incident",
    # AWS product post, not about state AI laws
    "https://aws.amazon.com/blogs/machine-learning/deploy-ai-in-a-hipaa-eligible-environment-with-amazon-quick/",
    # Chile talks with OpenAI, not about Stargate sites
    "https://dplnews.com/los-planes-de-la-ministra-lincolao-para-instalar-a-chile-en-el-circuito-global-de-la-ia-estamos-cerca-de-cerrar-un-acuerdo-con-openai/",
    # Chinese chip software news, not about US chip rules
    "https://pandaily.com/baai-flagos-2-2-cross-chip-operator-libraries-1454-operators-ascend-kernelgen",
    # state chatbot bill, not California's laws or federal preemption
    "https://epic.org/new-jersey-advances-strong-chatbot-regulations-based-on-epics-people-first-model/",
    # compute struggles, can't tell from the summary it is an IPO development
    "https://techcrunch.com/2026/10/20/anthropics-cloud-partnerships-are-getting-messy/",
    # Chinese chip launch, not about US chip rules
    "https://pandaily.com/stars-micro-system-c82-4g-pcie-6-0-switch-800g-ai-nic-multi-mode-raid",
    # criminal case against a former engineer, not restructuring or the Musk case
    "https://olhardigital.com.br/2026/10/19/pro/grampo-na-openai-juiz-ve-risco-de-fuga-e-nega-liberdade-a-ex-engenheiro-da-empresa/",
    # city mayor's remarks, not a development in preemption
    "https://techcrunch.com/2026/10/19/mamdani-says-feds-have-abdicated-on-ai-urges-new-yorkers-to-push-back/",
    # China's own export controls, not US chip rules
    "https://www.xataka.com/robotica-e-ia/china-quiere-que-su-ia-conquiste-mundo-no-que-toda-su-tecnologia-salga-pais-controles-para-40-tecnologias-clave",
    # Texas data centre permits, not about state AI laws
    "https://www.404media.co/it-aint-right-texas-said-it-would-halt-data-center-permits-the-state-is-pushing-ahead-anyway/",
    # cyber programme access, summary doesn't mention Mythos
    "https://www.thelec.net/news/articleView.html?idxno=14680",
    # weekly roundup, can't tell from the summary
    "https://techpolicy.press/openai-faces-lawsuits-subpoenas-and-eu-scrutiny-in-a-single-week",
    # weekly roundup, can't tell from the summary
    "https://techpolicy.press/another-week-of-lawsuits-piling-up-at-openai",
    # Character.AI staff and asset sale, summary says nothing about teens
    "https://techcrunch.com/2026/10/18/disney-agrees-to-hire-the-majority-of-character-ais-workforce/",
    # draft federal bill, can't tell from the summary it fits a preemption or California story
    "https://www.dawn.com/news/2037803/anthropic-proposes-law-regulating-ai-to-us-lawmakers",
    # state lawsuits over young users, not restructuring or the Musk case
    "https://olhardigital.com.br/2026/10/14/pro/8-estados-dos-eua-processam-openai-e-acusam-chatgpt-de-colocar-jovens-em-risco/",
    # alignment proposal, only shares tags with the topic
    "https://metr.org/blog/2026-10-14-alignment-assessment-proposal/",
    # state lawsuits over children, not restructuring or the Musk case
    "https://www.engadget.com/2287111/iowa-nebraska-and-six-other-states-are-suing-openai-for-endangering-children/",
    # opinion on Character.ai bankruptcy, nothing on teens
    "https://www.404media.co/character-ai-bankruptcy-is-first-ai-bubble-domino-to-fall/",
    # security model launch, not about the Pentagon dispute
    "https://the-decoder.com/ai-guardrails-designed-to-stop-hackers-are-now-blocking-defenders-and-orion-1-aims-to-fill-the-gap/",
    # Japan asks for cyber help, summary doesn't mention Mythos
    "https://japantoday.com/category/tech/japan-seeks-anthropic%27s-help-to-bolster-cybersecurity",
    # bankruptcy economics, summary says nothing about teens
    "https://www.404media.co/character-ais-bankruptcy-documents-show-the-economics-of-ai-dont-work/",
    # summary doesn't say it concerns OpenAI's device
    "https://techcrunch.com/2026/10/13/judge-orders-openai-to-turn-over-hiring-records-in-apple-trade-secrets-case/",
    # Meta engineering post, not about its superintelligence push
    "https://engineering.fb.com/2026/10/13/ml-applications/generative-ads-model-gem-scaling-frontier-ads-ai/",
    # consumer GPU supply story, not about US chip rules
    "https://www.xataka.com/componentes/nvidia-deja-fabricar-rtx-5090-tarjeta-potente-para-jugadores-filtracion-su-chip-ira-destinado-a-ia",
    # Character.AI staff and asset sale, summary says nothing about teens
    "https://olhardigital.com.br/2026/10/13/inteligencia-artificial/character-ai-pede-falencia-e-negocia-venda-de-ativos-a-disney/",
    # bank regulators on AI risk, not about state laws
    "https://techcentral.co.za/banking-regulators-ai-scrutiny-financial-stability/287226/",
    # Character.AI bankruptcy notice, says nothing about teens
    "https://blog.character.ai/an-update-on-character-ai/",
    # Meta engineering post, not about its superintelligence push
    "https://engineering.fb.com/2026/10/12/open-source/ocp-summit-2026-powering-ai-with-open-innovations-in-scale-up-scale-out-and-scale-across-networks/",
    # Chinese chip or Huawei news, not about US chip rules
    "https://pandaily.com/huawei-xingji-positioning-tunnel-lane-level-sub-meter-parking-garage-mate-90-watch-gt-runner-2",
    # speech on AI regulation, nothing new in these laws
    "https://www.engadget.com/2283487/microsoft-president-ai-less-regulated-than-a-carton-of-milk/",
    # tool launch, summary doesn't mention Mythos
    "https://www.engadget.com/2282005/anthropic-offers-open-source-software-free-ai-security-checks/",
    # programme launch, summary doesn't mention Mythos
    "https://www.anthropic.com/news/anthropic-cyber-mission",
    # Oracle product news, not about Stargate
    "https://openai.com/index/oracle",
    # trend explainer on community opposition, nothing new
    "https://datacenterpost.com/early-community-engagement-becomes-critical-as-data-center-opposition-grows/?utm_source=rss&utm_medium=rss&utm_campaign=early-community-engagement-becomes-critical-as-data-center-opposition-grows",
    # usage policy change, not about the Pentagon dispute
    "https://the-decoder.com/being-mean-to-claude-can-now-get-your-account-suspended-under-anthropics-new-tos/",
    # vendor product news, not about state laws
    "http://www.bernama.com/en/news.php?id=2616954",
    # explainer on AI in courts, not about these cases
    "https://www.itweb.co.za/article/ai-takes-the-bench-before-the-rulebook-is-ready/rW1xLv5nDG37Rk6m",
    # market outlook, nothing new in this storyline
    "https://www.datacenterknowledge.com/data-center-site-selection/emea-data-center-expansion-faces-a-delivery-test",
    # Chinese chip or Huawei news, not about US chip rules
    "https://pandaily.com/richard-yu-huawei-381-tau-chips-mass-produced-phones-ai-networking-smart-cars",
    # opinion on regulation, nothing new in these laws
    "https://www.engadget.com/2276577/former-openai-employee-says-ai-should-be-regulated-like-nuclear-power-plants/",
    # SDK release notes, not about the IPO
    "https://github.com/openai/openai-agents-python/releases/tag/v0.23.0",
}
UPDATED_DAYS = 3  # a topic with a new story this recently shows "Updated" on its card
SMALL = 25  # a topic with this many events or fewer shows each as a card; a bigger one only its milestones
LOGOS = 3   # brand logos on a topic's picture: the ones its stories name most,
LOGO_MIN = 3  # each named by this many of its stories at least
KEY, KEY_OFFICIAL = 4, 2  # key moments at the top of a topic's page, at most this many of them official records

_RULES = {slug: (re.compile(t["words"], re.I), re.compile(t["exclude"], re.I) if t.get("exclude") else None)
          for slug, t in TOPICS.items()}


def _urls(card: dict) -> set[str]:
    """The card's story and its other outlets' versions of it: one event."""
    return {s.get("url") for s in [card, *(card.get("also") or [])]}


def matches(slug: str, card: dict) -> bool:
    """Whether this card belongs to the topic."""
    t = TOPICS[slug]
    if card.get("category") not in STREAMS:
        return False
    if _urls(card) & ADDED.get(slug, {}).keys():
        return True
    if card.get("bill"):  # a tracked bill: only where the topic lists it
        return card["bill"] in t.get("bills", ())
    words, exclude = _RULES[slug]
    text = f"{card.get('title') or ''} {card.get('summary') or ''}"
    return bool(words.search(text)) and not (exclude and exclude.search(text))


def part_of(card: dict) -> list[list[str]]:
    """The topics this card belongs to, as [slug, name], for its "Part of" link."""
    return [[slug, t["name"]] for slug, t in TOPICS.items() if matches(slug, card)]


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Stories from `since` that carry a topic's net of tags, but that its words don't match and no list holds yet:
    one per event, newest first, each with the topics to check it for (`for`). A tracked bill joins only where listed."""
    held = LEFT_OUT | {u for urls in ADDED.values() for u in urls}
    out = []
    for c in sorted(cards, key=lambda c: c["date"], reverse=True):
        if c["date"] < since or c.get("category") not in STREAMS or c.get("bill") or _urls(c) & held:
            continue
        tags = set(c.get("tags") or [])
        found = [slug for slug, t in TOPICS.items() if any(n <= tags for n in t.get("net", ())) and not matches(slug, c)]
        if found:
            out.append({**c, "for": found})
    return out


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a topics/<day> branch: each story it adds to a topic, and the stories it left out;
    None when it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("ADDED", "LEFT_OUT"))
    rows = [(TOPICS[slug]["name"], why, u) for slug, urls in ADDED.items() for u, why in urls.items() if u not in had["ADDED"]]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("Follow the story", "stories" if len(rows) != 1 else "story", branch,
                        ("Topic", "Why it belongs", "Source"), rows, dropped)


def _logo(card: dict) -> dict | None:
    lg = card.get("logo")
    return {k: lg[k] for k in ("name", "hex", "path")} if lg and lg.get("path") else None


def events(slug: str, cards: list[dict]) -> list[dict]:
    """The topic's events, oldest first: each matching story (with how many outlets carried it and the brand it
    names), and each stage of its tracked bills as an official record (with its place's flag). The few biggest
    milestones are its key moments (see KEY)."""
    out = []
    for c in cards:
        if not matches(slug, c):
            continue
        if c.get("lifecycle"):
            life = c["lifecycle"]
            name = c["title"].split(": ", 1)[-1]
            out += [{"date": s["date"], "title": f"{name}: {s['label']}", "url": life["url"],
                     "source": life["source"], "outlets": 1, "official": True, "bill": c["bill"], "stage": s["stage"],
                     "flag": countries.flag(c["bill"].split("-")[0])}
                    for s in life["steps"] if s.get("date")]
            continue
        out.append({"date": c["date"], "title": c["title"].strip(), "url": c["url"], "source": c["source"],
                    "outlets": 1 + len({a["source"] for a in c.get("also") or []} - {c["source"]}),
                    "official": False, "logo": _logo(c), "tags": c.get("tags") or [], "category": c["category"]})
    out.sort(key=lambda e: (e["date"], not e["official"]))
    big = len(out) > SMALL
    for i, e in enumerate(out):  # a milestone gets a card; the rest fold into "+N more" between them
        e["milestone"] = not big or e["official"] or e["outlets"] > 1 or i in (0, len(out) - 1)
    # key moments: each bill's furthest stage past its introduction (the latest two), then the stories most
    # outlets carried
    furthest = {}
    for e in out:
        if e["official"] and e["stage"] != "introduced":
            furthest[e["bill"]] = e
    key = sorted(furthest.values(), key=lambda e: e["date"])[-KEY_OFFICIAL:]
    news = sorted((e for e in out if not e["official"]), key=lambda e: (e["outlets"], e["date"]), reverse=True)
    key += news[:KEY - len(key)]
    for e in key:
        e["key"] = e["milestone"] = True
    for e in out:
        e.pop("tags", None), e.pop("category", None)
    return out


def trend(ev: list[dict], today: date) -> int:
    """How much the topic is in the news now (see TREND_DAYS)."""
    since, hot = ((today - timedelta(days=d)).isoformat() for d in (TREND_DAYS, HOT_DAYS))
    return sum(e["outlets"] * (3 if e["date"] >= hot else 1) for e in ev if e["date"] >= since)


def path(slug: str) -> str:
    return f"topics/{slug}/"


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%b %Y')}"


def _logo_svg(lg: dict) -> str:
    return (f'<span class="logo" title="{escape(lg["name"])}"><svg viewBox="0 0 24 24" aria-hidden="true">'
            f'<path fill="#{escape(lg["hex"].lstrip("#"))}" d="{escape(lg["path"])}"/></svg></span>')


def _badges(slug: str, ev: list[dict]) -> str:
    """The topic's flags, then the logos its stories name most."""
    flags = list(dict.fromkeys([countries.flag(f) for f in LOOK[slug]]
                               + [e["flag"] for e in ev if e.get("flag")]))
    count: dict[str, list] = {}
    for e in ev:
        if e.get("logo"):
            count.setdefault(e["logo"]["name"], [0, e["logo"]])[0] += 1
    logos = [lg for n, lg in sorted(count.values(), key=lambda x: -x[0])[:LOGOS] if n >= LOGO_MIN]
    return ("".join(f'<img class="flag" src="flags/{f}" alt="">' for f in flags)
            + "".join(_logo_svg(lg) for lg in logos))


def _photo(slug: str) -> str:
    return f'<img class="photo" src="photos/cartoons/{slug}.svg" alt="" loading="lazy">'


TIMELINE_JS = r"""<script>
(() => {
  const tl = document.getElementById("timeline"), moments = document.getElementById("moments");
  const fmt = (d, o) => new Date(d.slice(0, 10) + "T00:00:00Z").toLocaleDateString(undefined, {...o, timeZone: "UTC"});
  const day = d => fmt(d, {day: "numeric", month: "short"}), full = d => fmt(d, {day: "numeric", month: "short", year: "numeric"});
  const el = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const link = (e, cls) => { const a = el("a", cls, e.title); a.href = e.url; a.rel = "noopener"; return a; };
  const lane = e => el("span", "lane", e.official ? "Official record" : "In the news");
  const meta = e => el("div", "meta", e.source + (e.outlets > 1 ? " · " + e.outlets + " outlets" : ""));
  const icon = e => {
    if(e.flag) { const i = el("img", "flag"); i.src = "flags/" + e.flag; i.alt = ""; return i; }
    if(!e.logo) return null;
    const s = el("span", "logo"); s.title = e.logo.name;
    s.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path></path></svg>';
    const p = s.querySelector("path"); p.setAttribute("fill", "#" + e.logo.hex.replace("#", "")); p.setAttribute("d", e.logo.path);
    return s;
  };
  const card = (e, side) => {
    const li = el("li", "ev " + side + (e.official ? " official" : " news") + (e.outlets > 1 ? " wide" : "") + (e.key ? " key" : ""));
    const box = el("div", "box"), top = el("div", "top"), ic = icon(e);
    top.append(el("span", "when", day(e.date)), lane(e)); if(ic) top.append(ic);
    const txt = el("div", "txt"); txt.append(top, link(e), meta(e)); box.append(txt);
    li.append(el("span", "dot"), box);
    return li;
  };
  const more = list => {
    const li = el("li", "more"), b = el("button", "", "+" + list.length + (list.length === 1 ? " more story" : " more stories"));
    b.type = "button"; b.setAttribute("aria-expanded", "false");
    const ul = el("ul"); ul.hidden = true;
    list.forEach(e => { const r = el("li"); r.append(el("span", "when", day(e.date)), link(e), el("span", "src", e.source)); ul.append(r); });
    b.addEventListener("click", () => { ul.hidden = !ul.hidden; b.setAttribute("aria-expanded", String(!ul.hidden)); });
    li.append(b, ul); return li;
  };
  fetch(tl.dataset.src, {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(list => {
    tl.replaceChildren();
    if(!list.length) return tl.append(el("p", "meta", "Nothing yet."));
    const keys = list.filter(e => e.key);
    if(keys.length) {
      const ul = moments.querySelector(".mlist");
      keys.forEach(e => {
        const li = el("li"), a = el("a", "", e.title); a.href = e.url; a.rel = "noopener";
        li.append(a, el("span", "when", full(e.date))); ul.append(li);
      });
      moments.hidden = false;
    }
    let ol = null, n = 0, folded = [];
    const flush = () => { if(folded.length) ol.append(more(folded)); folded = []; };
    list.forEach(e => {
      const year = e.date.slice(0, 4);
      if(!ol || ol.dataset.year !== year) {  // a chapter a year, its number kept in view beside it
        if(ol) flush();
        const ch = el("section", "chapter"), yr = el("div", "yr");
        yr.append(el("span", "", year));
        ol = el("ol", "timeline"); ol.dataset.year = year;
        ch.append(yr, ol); tl.append(ch);
      }
      if(!e.milestone) return folded.push(e);
      flush();
      ol.append(card(e, n++ % 2 ? "right" : "left"));  // either side of the line in turn; the colour tells which kind
    });
    flush();
    const now = el("li", "now"); now.append(el("span", "", "Now")); ol.append(now);
  }).catch(() => tl.replaceChildren(el("p", "meta", "Couldn't load the timeline. Try reloading the page.")));
})();
</script>"""


CARDS_JS = r"""<script>
fetch("/topics/latest.json", {cache: "no-cache"}).then(r => r.ok ? r.json() : Promise.reject(r.status)).then(d => {
  document.querySelectorAll(".topics .last").forEach(box => {
    const e = d[box.dataset.slug]; if(e) box.querySelector(".lt").textContent = e.title;
  });
}).catch(() => {});
</script>"""


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write topics/ (a picture card per topic, the most in the news first) and each topic's page: its picture and its timeline, from its
    events.json. Returns the pages' paths."""
    parts = pages.frame(conn, len(cards))
    (out / "flags").mkdir(exist_ok=True)
    quiet = (today - timedelta(days=QUIET_DAYS)).isoformat()
    blocks, paths = [], []
    for slug, t in TOPICS.items():
        ev = events(slug, cards)
        for f in {countries.flag(f) for f in LOOK[slug]} | {e["flag"] for e in ev if e.get("flag")}:
            shutil.copy(countries.FLAGS / f, out / "flags" / f)
        latest = ev[-1]["date"] if ev else ""
        done = latest < quiet
        p = path(slug)
        (out / p).mkdir(parents=True, exist_ok=True)
        (out / p / "events.json").write_text(json.dumps(ev, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        badges = _badges(slug, ev)
        status = '<span class="done">Concluded</span>' if done else ""
        related = " · ".join(f'<a href="/{path(r)}">{escape(TOPICS[r]["name"])}</a>' for r in t.get("related", ()))
        body = (f'<div class="tp">\n<div class="topic-hero">{_photo(slug)}<div class="over"><span class="kind">'
                f'{escape(t["kind"])}</span>{status}<h1>{escape(t["name"])}</h1><p class="what">{escape(t["what"])}</p>'
                f'<div class="badges">{badges}</div></div></div>\n'
                '<section class="moments" id="moments" hidden><h2>Key moments</h2><ul class="mlist"></ul></section>\n'
                '<h2>How it unfolded</h2>\n'
                + ('<p class="legend"><span class="lg official">Official record</span>'
                   '<span class="lg news">In the news</span></p>\n' if any(e["official"] for e in ev) else "")
                + f'<div class="chapters" id="timeline" data-src="/{p}events.json"><p class="meta">Loading…</p></div>\n'
                + (f'<p class="related">Related: {related}</p>\n' if related else "")
                + f'</div>\n{TIMELINE_JS}')
        data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": t["name"],
                "description": t["what"], "url": f"{rss.SITE}{p}"}
        (out / p / "index.html").write_text(
            pages.page(f"{t['name']} · AI Pulse", t["what"], p, body, data, parts, ("/topics/", "All topics")), encoding="utf-8")
        paths.append(p)
        flags = sorted({countries.flag(f) for f in LOOK[slug]} | {e["flag"] for e in ev if e.get("flag")})
        blocks.append({"slug": slug, "done": done, "latest": latest, "badges": badges, "score": trend(ev, today),
                       "flags": flags,
                       "hot": latest >= (today - timedelta(days=HOT_DAYS)).isoformat(),
                       "updated": latest >= (today - timedelta(days=UPDATED_DAYS)).isoformat(),
                       "last": {k: ev[-1][k] for k in ("title", "source", "date")} if ev else None})
    blocks.sort(key=lambda b: b["latest"], reverse=True)
    blocks.sort(key=lambda b: (b["done"], -b["score"]))  # in the news most first (newest first on a tie), concluded last
    # each topic's newest event, the outlet's own headline, for its card to load in the reader's browser
    (out / "topics" / "latest.json").write_text(json.dumps({b["slug"]: b["last"] for b in blocks if b["last"]},
                                                           separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    # the front page's "Follow the story" strip: the FRONT topics most in the news (index.html, loadTopics)
    (out / "topics" / "front.json").write_text(json.dumps([
        {"href": f"/{path(b['slug'])}", "name": TOPICS[b["slug"]]["name"], "kind": TOPICS[b["slug"]]["kind"],
         "photo": [f"cartoons/{b['slug']}.svg", ""],
         "flags": b["flags"], "updated": b["updated"], **b["last"]}
        for b in blocks if not b["done"] and b["last"]][:FRONT], separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8")
    cards_html = []
    for i, b in enumerate(blocks):
        t = TOPICS[b["slug"]]
        tag = ('<span class="done">Concluded</span>' if b["done"] else
               '<span class="done hot">Trending</span>' if i < TRENDING and b["hot"] else "")
        cards_html.append(
            f'<a href="/{path(b["slug"])}"><span class="pic">{_photo(b["slug"])}{tag}'
            f'<span class="badges">{b["badges"]}</span></span><span class="txt">'
            f'<span class="kind">{escape(t["kind"])}</span><b>{escape(t["name"])}</b>'
            + (f'<span class="last" data-slug="{b["slug"]}"><span class="lt"></span>'
               f'<span class="meta">{"<span class=upd>Updated</span>" if b["updated"] else ""}{_day(b["latest"])}</span>'
               '</span>' if b["latest"] else "")
            + "</span></a>")
    what = "Pick a topic to see how it unfolded, from the first report to today, with laws and news on one timeline."
    body = (f'<div class="ti">\n' + pages.band("all", "M3 12h18M7 12v.01M12 12v.01M17 12v.01M7 8V5M12 16v3M17 8V5",
                                              "photos/cartoons/pages/topics.svg", "Follow the story",
                                              "How did the biggest AI stories unfold?", escape(what))
            + f'<div class="topics">{"".join(cards_html)}</div>\n</div>\n{CARDS_JS}\n')
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Topics", "description": what,
            "url": f"{rss.SITE}topics/"}
    (out / "topics" / "index.html").write_text(
        pages.page("Topics · AI Pulse", what, "topics/", body, data, parts, ("/", "Back to AI Pulse")), encoding="utf-8")
    return ["topics/", *paths]
