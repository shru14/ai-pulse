"""Topics: storylines AI Pulse follows over time (topics/), laws and news together, a page each (topics/<slug>/).

Each topic is a rule kept by hand: the tracked bills it follows (their stages are its official record) and the words
a story must have (`words`, in its headline or summary) and must not (`exclude`). A card joins a topic when it matches
the words; a tracked bill's own card joins only the topics that list it, so a US bill named "... AI Act" never lands in
the EU AI Act's story. Research papers stay in Research. A topic with nothing new for QUIET_DAYS is tagged Concluded.

The words decide; a topic's `net` of tags only catches what they miss. A story carrying one of those sets of tags that
the words don't match is a candidate (`python -m aipulse topics`): the daily job drafts each into ADDED or LEFT_OUT on a
topics/<day> branch, and it joins a topic only when the owner merges that.

The stories are the outlets' own headlines, so a topic's page loads them in the reader's browser from its events.json,
as the industry pages do; the page itself holds the newest too, for search engines (seo.py).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import countries, pages, rss, seo

QUIET_DAYS = 90  # a topic with no new event for this long is Concluded (kept, never deleted)
# Topics are ranked by how much they're in the news: over the last TREND_DAYS, each event counts once per outlet that
# carried it, and three times over in the last HOT_DAYS. The top TRENDING with an event in the last HOT_DAYS are tagged.
TREND_DAYS, HOT_DAYS, TRENDING = 30, 7, 3
FRONT = 3  # topics the front page shows
STREAMS = ("news", "policy", "regulation", "infra", "tool")  # not research: papers aren't events

# slug: name, kind (the block's label), what (our own words), bills, words, exclude, net (sets of story tags that may
# mean the topic), related topics
# The Huang scandal (from 29 Oct 2026). Its stories stay out of the chip-rules topic unless they also speak of exports
_HUANG = (r"\bAlice Huang\b|\b(Jensen )?Huang\b.{0,120}\b(spy|spies|spying|espionage|espionaje|affairs?|scandal"
          r"|infidelity|extramarital|lover|oust\w*|successors?|class[- ]action)\b|\b(spy|spies|spying|espionage"
          r"|espionaje|affairs?|scandal|infidelity|extramarital|lover)\b.{0,120}\b(Jensen )?Huang\b|\b(oust\w*|remov\w*"
          r"|investigar)\b.{0,40}\bJensen Huang\b|\bJensen Huang (problem|scandal|to court)\b|\bNvidia\b.{0,60}\b(scandal"
          r"|controvers(y|ies)|spy|spies|espionage|espionaje|intelligence asset|informant)\b|\b(scandal|controvers(y|ies)"
          r"|spy|spies|espionage|espionaje)\b.{0,60}\bNvidia\b")
_HUANG_ONLY = rf"(?s)^(?!.*\b(exports?|curbs?|export controls?|smuggl\w*)\b).*(?:{_HUANG})"
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
        exclude=_HUANG_ONLY,
        net=({"Nvidia", "China"}, {"Chips", "China"}, {"Export Controls"}),
        related=("nvidia-huang-scandal",)),
    "nvidia-huang-scandal": dict(
        name="Nvidia's Huang scandal", kind="Company",
        what="Claims that Nvidia's chief Jensen Huang had an affair with an alleged Chinese spy, and what followed: "
             "the board's inquiry, lawsuits, questions from Congress and the fall in Nvidia's shares.",
        words=_HUANG,
        related=("nvidia-chips-china",)),
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
        related=("stargate", "data-centre-backlash")),
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
    "data-centre-backlash": dict(
        name="The backlash against data centres", kind="Infrastructure",
        what="Towns, voters and activists pushing back on AI data centres: moratoriums, protests, ballot results and "
             "how the industry is answering.",
        bills=("US-119-s-4214", "US-119-hr-9442"),
        words=r"\bdata cent(er|re)s?\b.{0,80}\b(moratori(um|a)|opposition|opponents?|oppos(e|es|ed|ing)|protest\w*"
              r"|backlash|residents|zoning|bans?|banned|banning|block(s|ed|ing)?|reject\w*|NDAs?|secret deals?|pause)\b"
              r"|\b(moratori(um|a)|opposition|opponents?|oppos(e|es|ed|ing)|protest\w*|backlash|residents|bans?|banned"
              r"|banning|block(s|ed|ing)?|reject\w*|voters?)\b.{0,80}\bdata cent(er|re)s?\b",
        exclude=r"TechCabal Daily|Fraud Kingpin|\bOrganizer\b|Facebook Pages|PRC-Linked|explosion in data center "
                r"spending|really running AI|Power Challenge Behind",
        net=({"Land & local pushback"},),
        related=("data-centre-power-bills",)),
    "chatgpt-ads": dict(
        name="Ads in ChatGPT", kind="Company",
        what="OpenAI's move to put adverts in ChatGPT: the first tests, how ads are targeted, and their spread to "
             "more countries.",
        words=r"\b(ChatGPT|OpenAI)\b.{0,40}\b(ads|advert\w*|ad (format|stack|platform|business|revenue))\b"
              r"|\b(ads|advert\w*)\b.{0,30}\bChatGPT\b",
        exclude=r"top 10 AI mobile apps|Claude 2\.1|Super Bowl ads|theCUBE Pod",
        related=("openai-restructuring",)),
    "always-on-agents": dict(
        name="The always-on agent race", kind="Company",
        what="AI labs racing to sell agents that keep working in the background: OpenAI's Dots, Anthropic's Claude "
             "Duet, xAI's Grok Bot and Google's Gemini Spark.",
        words=r"\balways[- ]on (AI )?agents?\b|\bClaude Duet\b|\bGrok Bot\b|\bDots agents?\b"
              r"|\b(OpenAI|ChatGPT)'?s?\b.{0,40}\bDots\b|\bDots\b.{0,40}\b(OpenAI|agents?)\b",
        exclude=r"\bNemotron\b"),
}

# Each topic's picture is our own cartoon, templates/photos/cartoons/<slug>.svg (no real people, no logos). LOOK holds
# the flags of the places whose laws it follows (beside its tracked bills' own). The logos come from its stories (brands.py).
LOOK = {
    "eu-ai-act": ("EU",),
    "nvidia-chips-china": ("US", "CN"),
    "nvidia-huang-scandal": (),
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
    "data-centre-backlash": (),
    "chatgpt-ads": (),
    "always-on-agents": (),
}
# Stories the words miss, checked by hand and approved: slug: {url: why it belongs, in our own words}
ADDED: dict[str, dict[str, str]] = {
    "ai-ipos": {
        "https://www.channelnewsasia.com/business/anthropic-discloses-month-long-training-pause-ai-security-breaches-in-ipo-filing-6493811": "Anthropic's IPO filing discloses a month-long training pause and AI security breaches",
        "https://techcrunch.com/2026/10/30/anthropic-expected-to-receive-high-junk-rating-from-credit-agencies-following-ipo-report-says/": "Report on the credit rating Anthropic is expected to get after its IPO",
        "https://olhardigital.com.br/2026/10/15/pro/anthropic-investidores-reduzem-expectativa-de-avaliacao-para-ipo-de-r-8-1-trilhoes/": "Investors lower their valuation hopes for Anthropic's planned November IPO",
        "https://www.xataka.com/empresas-y-economia/salida-a-bolsa-anthropic-se-estaba-desinflando-ahora-tiene-demanda-institucional-que-spacex": "Anthropic sets its IPO share price range, with a valuation lower than earlier talk",
        "https://japantoday.com/category/tech/anthropic-seeks-valuation-of-about-1.3-trillion-when-it-becomes-a-publicly-traded-company": "Anthropic seeks a valuation of about $1.3 trillion when it goes public",
        "https://techcrunch.com/2026/11/10/all-7-anthropic-founders-will-each-cash-out-about-250m-in-ipo/": "All seven Anthropic co-founders plan to sell the same number of shares in the IPO",
        "https://www.xataka.com/empresas-y-economia/blackstone-advierte-que-anthropic-se-arriesga-a-salir-a-bolsa-buena-calificacion-crediticia-golpe-para-sus-planes": "Blackstone warns Anthropic risks going public without a good credit rating",
        "https://www.thelec.net/news/articleView.html?idxno=15023": "Anthropic's S-1 filing shows its cash holdings",
        "https://the-decoder.com/anthropic-opens-its-books-for-wall-street-showing-record-revenue-and-mounting-obligations/": "Anthropic files an S-1 with the SEC to list on the Nasdaq",
        "https://www.xataka.com/empresas-y-economia/anthropic-acaba-dar-uno-pasos-importantes-industria-ia-abrir-sus-cuentas-para-salir-a-bolsa": "Anthropic opens its accounts in a filing on the way to the stock market",
        "https://olhardigital.com.br/2026/10/20/pro/anthropic-revela-prejuizo-de-r-435-8-bilhoes-e-custos-bilionarios-com-ia/": "Anthropic's preliminary prospectus reveals its revenue, losses and computing commitments",
        "https://www.xataka.com/empresas-y-economia/anthropic-su-s-1-tenemos-historial-perdidas-posible-que-no-generemos-ingresos-suficientes-futuro": "Anthropic's S-1 warns of a record of losses and uncertain future revenue",
        "https://www.xataka.com/robotica-e-ia/anthropic-ha-disenado-peculiar-sistema-poder-para-evitar-que-sus-accionistas-controlen-despues-su-salida-a-bolsa": "Anthropic designs a power system to keep shareholders from controlling it after its stock market exit",
        "https://www.xataka.com/empresas-y-economia/anthropic-propone-destinar-5-sus-acciones-a-fondo-que-podria-abordar-impacto-laboral-ia": "Anthropic proposes putting 5 per cent of its shares into a fund for AI's labour impact",
    },
    "deepseek-us": {
        "https://dplnews.com/estados-unidos-ordena-retirar-deepseek/": "US bans federal civil agencies from buying DeepSeek products and orders existing ones removed",
        "https://techcrunch.com/2026/10/22/deepseek-reportedly-raises-15b-days-after-us-restrictions/": "DeepSeek's reported $15B raise came days after the US ordered federal agencies to remove its technology",
    },
    "openai-device": {
        "https://olhardigital.com.br/2026/10/14/pro/openai-acusa-ex-funcionario-de-enviar-arquivos-secretos-a-apple/": "OpenAI accuses a former employee of sending trade secrets to Apple over new AI devices",
        "https://olhardigital.com.br/2026/10/13/pro/justica-obriga-openai-a-entregar-documentos-de-contratacao-em-processo-da-apple/": "Court orders OpenAI to hand over hiring documents in the Apple trade-secrets dispute over hardware products",
    },
    "data-centre-power-bills": {
        "https://www.canarymedia.com/articles/data-centers/virginia-new-energy-plan-ai-boom": "Virginia's new energy plan on utility bills and electricity demand from the AI boom",
    },
    "data-centre-backlash": {
        "https://www.xataka.com/robotica-e-ia/zaragoza-sale-a-calle-centros-datos-no-generan-empleo-no-pagan-impuestos-se-quedan-todos-recursos": "Thousands march in Zaragoza against data centres",
        "https://www.foodandwaterwatch.org/press/2026/11/05/new-yorkers-to-governor-hochul-stop-the-rush-to-build-ai-data-centers/": "New Yorkers press Governor Hochul to stop the rush to build AI data centres",
        "https://www.engadget.com/2307590/openai-says-it-will-protect-local-resources-and-report-on-the-impact-of-its-data-centers/": "OpenAI pledges to protect local resources and report on its data centres' impact after the vote",
        "https://www.xataka.com/robotica-e-ia/centros-datos-tambien-se-presentaban-a-elecciones-eeuu-han-perdido-estrepitosamente": "Data centres lost heavily in the US elections",
        "https://www.engadget.com/2306534/americans-overwhelmingly-voted-against-data-centers-in-the-midterms/": "Americans voted overwhelmingly against data centres in the midterms",
        "https://www.xataka.com/robotica-e-ia/elon-musk-tiene-plan-para-acabar-vecinos-quejandose-centros-datos-cerca-comprar-sus-casas": "Plan to buy the houses of neighbours who complain about a nearby data centre",
        "https://tecnoblog.net/noticias/spacex-quer-comprar-casas-de-vizinhos-incomodados-com-seus-data-centers/": "SpaceX wants to buy houses from neighbours bothered by its data centres",
        "https://www.404media.co/west-virginia-american-chestnut-trees-data-center/": "Resistance to a West Virginia AI data centre centres on a grove of chestnut trees",
        "https://www.channelnewsasia.com/business/trump-says-companies-should-pay-dividend-communities-make-data-centers-popular-6478021": "Trump says companies should pay a dividend to communities to make data centres popular",
        "https://www.foodandwaterwatch.org/press/2026/10/14/allentown-planning-commission-bucks-public-opinion-greenlights-data-center/": "Allentown planning commission approves a data centre against public opinion",
    },
    "nvidia-huang-scandal": {
        "https://the-decoder.com/chinese-spies-targeted-nvidia-ceo-jensen-huang-according-to-the-new-york-times/": "Report that US intelligence believes an executive in Huang's circle is a Chinese informant",
        "http://www.bernama.com/en/news.php?id=2633535": "Nvidia announces Jensen Huang has resigned as CEO and board member amid the board investigation",
        "https://olhardigital.com.br/2026/11/11/pro/nvidia-contrata-empresa-para-encontrar-substituto-de-jensen-huang-diz-agencia/": "Nvidia reportedly hires a firm to find a replacement for Huang amid the crisis over his relationship",
        "https://dplnews.com/nvidia-contrata-exfiscal-investigar-jensen-huang/": "Nvidia hires a former prosecutor to investigate the allegations about Huang",
        "https://www.channelnewsasia.com/world/nvidia-shares-jensen-huang-probe-affair-6535186": "Nvidia's shares fall out of hours as the firm probes Huang",
    },
}
# Stories a topic's net caught that don't belong, checked by hand
LEFT_OUT: set[str] = {
    # Huang's personal relationship and Nvidia's internal probe, not about chip rules or China's response
    "https://techcentral.co.za/nvidia-jensen-huang-problem-rattles-investors/288157/",
    # Huang scandal and the auto industry, not about chip rules
    "https://www.businesskorea.co.kr/news/articleView.html?idxno=280843",
    # Nvidia investigating its CEO's relationship, not about chip rules or China's response
    "https://techcrunch.com/2026/11/08/nvidia-says-its-investigating-ceo-jensen-huangs-relationship-with-possible-chinese-spy/",
    # Karpathy's side project built with Claude, not about Mythos
    "https://the-decoder.com/andrej-karpathy-built-a-curated-video-platform-in-a-weekend-using-claude-and-20-years-of-hacker-news/",
    # Lithuanian laser factory, not about US chip rules
    "https://www.xataka.com/componentes/lituania-tiene-2-9-millones-habitantes-compite-china-fabricando-laseres-para-chips-ia-serie",
    # funding round, can't tell from the summary it is about the restructuring or the Musk case
    "https://the-decoder.com/openai-lands-an-11-billion-funding-round-but-has-to-court-dentists-for-more-capital/",
    # data-centre expansion plans, summary doesn't mention Stargate
    "https://www.channelnewsasia.com/business/openai-press-ahead-data-center-expansion-despite-midterm-sweep-cfo-tells-cnbc-6532086",
    # market selloff over regulation fears, no specific California law or preemption step
    "https://www.techerati.com/news-hub/global-tech-stocks-fall-amid-concerns-over-ai-spending/",
    # market selloff over regulation fears, no specific California law or preemption step
    "https://www.dawn.com/news/2042565/asia-stocks-tumble-after-ai-rout-rocks-us-markets",
    # market selloff over regulation fears, no specific California law or preemption step
    "https://japantoday.com/category/business/tech-firms-suffer-bloodbath-as-us-midterms-fuel-ai-fears",
    # midterm regulatory-risk analysis, no specific California law or preemption step
    "https://www.businesskorea.co.kr/news/articleView.html?idxno=280544",
    # revenue and loss figures, can't tell from the summary it is an IPO filing or other development
    "https://the-decoder.com/anthropic-grows-revenue-twelvefold-but-posts-23-billion-loss/",
    # utility programme for future compute campuses, summary doesn't mention Stargate
    "https://openai.com/index/grid-protectors-program",
    # research model that runs CUDA, not about US chip rules
    "https://www.marktechpost.com/2026/11/01/qwengpu-simt-gpu-compiled-into-qwen3-5-2b-weights-runs-cuda/",
    # Nvidia stake in Naver, not about the AI Basic Act
    "https://www.thelec.net/news/articleView.html?idxno=15117",
    # possible rebrand of data centers, summary doesn't mention Stargate
    "https://techcrunch.com/2026/11/01/openai-might-rebrand-its-data-centers-as-ai-compute-campuses/",
    # general data-centre politics piece, no specific state AI law or preemption development
    "https://www.telesemana.com/blog/2026/11/04/las-propuestas-regulatorias-para-los-centros-de-datos-tambien-ganaron-en-las-elecciones-de-medio-termino-de-estados-unidos/",
    # Google backlash over schools, only shares tags with the topics
    "https://techcrunch.com/2026/11/04/google-faces-backlash-for-plan-that-would-turn-off-search-for-schools-that-restrict-ai/",
    # UK land sale for a grid node, not about who pays for power
    "https://w.media/teesworks-sells-land-to-national-grid-for-ai-and-data-center-development/",
    # general explainer on power limits, nothing new in a specific case
    "https://www.datacenterknowledge.com/energy-power-supply/ai-s-expansion-hits-the-limits-of-local-power",
    # Huawei memory sourcing, not about US rules or Nvidia in China
    "https://the-decoder.com/huawei-tells-customers-to-find-their-own-ai-chip-memory-effectively-outsourcing-procurement-to-the-black-market/",
    # Chinese GPU cluster performance, not about US rules or DeepSeek's dealings with Washington
    "https://pandaily.com/moore-threads-wuxi-huishan-mtt-s5000-cluster-2112-gpus-92-9-percent-utilization-deepseek-v4-flash",
    # Tencent research agent, not about chip rules
    "https://pandaily.com/tencent-hunyuan-hyra-2-0-research-agent-builds-scientific-tools-hyinv-hyff-hyqec-open-results",
    # scraping suit against a browser, can't tell from the summary it is about AI training
    "https://techcrunch.com/2026/11/02/new-york-times-and-other-outlets-sue-web-browser-brave-over-alleged-content-scraping/",
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
    # voluntary commitments for future sites after the midterms, summary doesn't mention Stargate
    "https://the-decoder.com/after-midterm-rout-openai-tries-to-win-over-communities-it-needs-for-ai-expansion/",
    # community compact and policy blueprint, summary doesn't mention Stargate
    "https://openai.com/index/setting-new-standard-responsible-ai-infrastructure",
    # UK government note on an EU regulation, can't tell from the summary it is about the AI Act
    "https://www.gov.uk/government/publications/em-on-eu-regulation-20241689-on-artificial-intelligence",
    # Huang scandal and the spy claims, not about chip rules
    "https://www.channelnewsasia.com/world/jensen-huang-nvidia-affair-scrutiny-china-alice-6539171",
    # Huang scandal and the spy claims, not about chip rules
    "https://www.channelnewsasia.com/east-asia/nvidia-ceo-jensen-huang-affair-chinese-businesswoman-alice-huang-6538396",
    # Huang scandal and the spy claims, not about chip rules
    "https://www.xataka.com/empresas-y-economia/infidelidad-huang-ha-destapado-fragilidad-nvidia-depende-hombre-sucesor-isla-plan-b",
    # Huang scandal and the spy claims, not about chip rules
    "https://www.businesskorea.co.kr/news/articleView.html?idxno=280892",
    # Huang scandal and the spy claims, not about chip rules
    "https://olhardigital.com.br/2026/11/09/pro/nvidia-e-jensen-huang-sao-processados-por-caso-envolvendo-suposta-espia-chinesa/",
    # Huang scandal and the spy claims, not about chip rules
    "https://olhardigital.com.br/2026/11/09/pro/china-contesta-suspeitas-de-espionagem-ligadas-ao-ceo-da-nvidia/",
    # Huang scandal and the spy claims, not about chip rules
    "https://www.channelnewsasia.com/world/nvidia-alice-huang-spying-jensen-6535566",
    # Huang scandal and the spy claims, not about chip rules
    "https://olhardigital.com.br/2026/11/09/inteligencia-artificial/novela-geopolitica-da-nvidia-tem-china-eua-espionagem-e-traicao/",
    # Huang scandal and the spy claims, not about chip rules
    "https://olhardigital.com.br/2026/11/06/pro/china-recrutou-empresaria-para-espionar-ceo-da-nvidia-aponta-inteligencia-dos-eua/",
    # Huang scandal and the spy claims, not about chip rules
    "https://www.channelnewsasia.com/asia/trump-says-us-looking-closely-report-nvidia-ceo-target-china-spy-plot-6510641",
    # Huang scandal and the spy claims, not about chip rules
    "https://www.engadget.com/2301447/nvidia-ceo-jensen-huang-may-have-been-the-target-of-a-chinese-government-spy/",
    # Huang scandal and the spy claims, not about chip rules
    "https://techcrunch.com/2026/10/29/u-s-investigated-chinese-spy-plot-aimed-at-nvidia-ceo/",
    # Huang scandal and the spy claims, not about chip rules
    "https://japantoday.com/category/tech/nvidia-and-huang-face-class-action-lawsuit-over-affair",
    # Huang scandal and cloud providers, not about California's laws or preemption
    "https://www.channelnewsasia.com/world/jensen-huang-nvidia-scandal-scrutiny-cloud-providers-southeast-asia-6542471",
    # Chinese GPU maker's developer conference, not about US chip rules
    "https://pandaily.com/moore-threads-mdc-musa-developer-conference-s6000-lushan-huagang",
    # Huang's net worth, AGI talk and Europe visit, no step in the scandal that the summary shows
    "https://nairametrics.com/2026/11/09/nvidia-ceo-jensen-huang-loses-7-8-billion-in-24-hours/",
    # Huang's net worth, AGI talk and Europe visit, no step in the scandal that the summary shows
    "https://the-decoder.com/frontier-radar-5-if-agi-is-so-close-why-is-everyone-leaving-the-neolabs-and-their-bets/",
    # Huang's net worth, AGI talk and Europe visit, no step in the scandal that the summary shows
    "https://japantoday.com/category/tech/nvidia-ceo-encourages-europe%27s-lagging-ai-sector-and-offers-tools-to-accelerate-data-center-buildout",
    # chain-of-thought research, summary doesn't mention Stargate
    "https://the-decoder.com/openais-data-suggests-that-frontier-models-are-hiding-their-thoughts-because-developers-optimize-for-capability-and-compute/",
    # grid-access charge in Malaysia, can't tell from the summary it is about who pays for data centre power
    "https://w.media/malaysia-raises-by-10-times-penalty-for-data-center-phantom-power-demand-report/",
    # Malaysian parliament agenda, nothing decided about power bills
    "http://www.bernama.com/en/news.php?id=2620546",
    # podcast or video discussion, reports no new step in the topic
    "https://techcrunch.com/video/why-the-data-center-you-dread-might-never-even-be-built/",
    # podcast or video discussion, reports no new step in the topic
    "https://techcrunch.com/podcast/how-backlash-and-red-tape-continue-to-slow-data-centers-post-blue-wave/",
    # podcast or video discussion, reports no new step in the topic
    "https://techcrunch.com/podcast/how-a-blue-wave-midterm-might-reshape-the-ai-industry/",
    # podcast or video discussion, reports no new step in the topic
    "https://techcrunch.com/video/after-the-midterms-is-the-ai-industry-in-for-a-rough-two-years/",
    # explainer or feature on data-centre power or building, nothing new
    "https://www.powermag.com/powering-data-centers-seven-must-do-items-for-renewable-energy-developers/",
    # explainer or feature on data-centre power or building, nothing new
    "https://w.media/special-feature-greenfield-versus-brownfield-how-data-centers-projects-are-evolving-around-the-constraints/",
    # explainer or feature on data-centre power or building, nothing new
    "https://w.media/special-feature-can-america-be-at-peace-with-the-neighbourhood-data-center/",
    # explainer or feature on data-centre power or building, nothing new
    "https://www.datacenterknowledge.com/energy-power-supply/the-power-challenge-behind-hyperscale-ai-expansion",
    # Anthropic IPO comparison, summary doesn't say what is new
    "https://www.channelnewsasia.com/business/how-anthropic-stacks-up-against-some-biggest-us-ipos-6545926",
    # Anthropic model release, not a step in the IPO
    "https://japantoday.com/category/tech/anthropic-launches-powerful-new-models-ahead-of-wall-street-debut",
    # analysis or interview around the IPO filing, reports nothing new
    "https://www.xataka.com/empresas-y-economia/no-todos-tokens-que-producen-modelos-valen-dario-amodei-sugiere-modelo-precios-dinamicos-funcion-tarea",
    # analysis or interview around the IPO filing, reports nothing new
    "https://www.xataka.com/robotica-e-ia/negocio-que-anthropic-promete-a-sus-inversores-vale-40-billones-que-cobramos-quienes-hacemos-que-quiere-hacer-su-ia",
    # analysis or interview around the IPO filing, reports nothing new
    "https://www.xataka.com/empresas-y-economia/salida-a-bolsa-anthropic-ha-revelado-algo-oculto-a-simple-vista-todas-grandes-tecnologicas-quieren-ser-como-nvidia",
    # analysis or interview around the IPO filing, reports nothing new
    "https://www.xataka.com/robotica-e-ia/china-pone-jaque-a-anthropic-competencia-sus-modelos-amenaza-su-valoracion-antes-salir-a-bolsa",
    # chip financing for Anthropic, not a step in the IPO
    "https://olhardigital.com.br/2026/10/27/pro/bancos-e-blackstone-vao-financiar-r-340-bilhoes-em-chips-de-ia-para-a-anthropic/",
    # chip financing for Anthropic, not a step in the IPO
    "https://www.channelnewsasia.com/business/anthropic-offers-blackstone-double-digit-yield-in-chip-financing-deal-ft-reports-6467711",
    # quarterly revenue report, can't tell from the summary it comes from the IPO filing
    "https://www.thelec.net/news/articleView.html?idxno=14613",
    # New York AI safety law and copyright briefs, not about OpenAI's restructuring or the Musk case
    "https://techpolicy.press/friends-of-the-court-flock-to-the-openai-copyright-fight",
    # New York AI safety law and copyright briefs, not about OpenAI's restructuring or the Musk case
    "https://www.fayerwayer.com/internet/2026/11/11/mano-dura-en-nueva-york-openai-y-anthropic-deberan-reportar-fallas-criticas-de-ia-en-72-horas-o-enfrentar-multas-millonarias/",
    # New York AI safety law and copyright briefs, not about OpenAI's restructuring or the Musk case
    "https://techcrunch.com/2026/11/10/openai-anthropic-face-new-oversight-as-new-yorks-ai-safety-law-takes-effect/",
    # cloud customer story, not about California's laws or preemption
    "https://aws.amazon.com/blogs/machine-learning/how-dxc-technology-built-a-multi-model-ai-substrate-on-amazon-bedrock/",
    # Gemini on CarPlay, not about the Siri deal
    "https://blog.google/innovation-and-ai/products/gemini-app/gemini-on-apple-carplay/",
    # UK exam rules, not about chips
    "https://the-decoder.com/uk-regulator-threatens-universities-with-sanctions-unless-they-adopt-ai-proof-exam-formats/",
    # data-centre event, programme or business news that reports no pushback or answer to it
    "https://www.foodandwaterwatch.org/press/2026/11/11/experts-launch-webinar-series-on-public-health-data-centers-and-fracking-in-pa/",
    # data-centre event, programme or business news that reports no pushback or answer to it
    "https://dcnnmagazine.com/business/compliance/idca-launches-community-assurance-programme-for-data-centres/",
    # data-centre event, programme or business news that reports no pushback or answer to it
    "https://w.media/terravolt-plans-240-mw-behind-the-meter-data-center-campus-in-idaho/",
    # data-centre event, programme or business news that reports no pushback or answer to it
    "https://news.mit.edu/2026/at-new-york-climate-week-mit-connects-global-network-1026",
    # data-centre event, programme or business news that reports no pushback or answer to it
    "https://datacenterpost.com/duos-edge-ai-earns-global-recognition-for-bringing-compute-closer-to-communities/?utm_source=rss&utm_medium=rss&utm_campaign=duos-edge-ai-earns-global-recognition-for-bringing-compute-closer-to-communities",
    # data-centre event, programme or business news that reports no pushback or answer to it
    "https://w.media/thailand-moves-to-finalise-data-center-rules-amid-trillion-baht-investment-pipeline/",
    # data-centre event, programme or business news that reports no pushback or answer to it
    "https://w.media/batam-data-center-expansion-raises-demand-for-independent-water-and-power-supplies/",
    # data-centre event, programme or business news that reports no pushback or answer to it
    "https://www.aboutamazon.com/news/aws/amazon-data-centers-locations-news?utm_source=rss",
    # data-centre event, programme or business news that reports no pushback or answer to it
    "https://w.media/cdc-offers-australian-community-au-225m-in-proposed-data-centre-benefits/",
    # data-centre event, programme or business news that reports no pushback or answer to it
    "https://www.gov.uk/government/publications/data-centre-covenant",
    # opinion, roundtable or job ad on data centres, reports nothing new
    "https://ainowinstitute.org/news/2026-election-breakdown-americans-vote-down-data-centers-ai-and-oligarchy",
    # opinion, roundtable or job ad on data centres, reports nothing new
    "https://www.foodandwaterwatch.org/content/2026/11/06/temporary-washington-organizer/",
    # opinion, roundtable or job ad on data centres, reports nothing new
    "https://www.404media.co/there-is-one-fight-american-voters-reject-tech-oligarchy/",
    # opinion, roundtable or job ad on data centres, reports nothing new
    "https://www.foodandwaterwatch.org/news/2026/10/22/who-really-benefits-from-community-benefit-agreements/",
    # opinion, roundtable or job ad on data centres, reports nothing new
    "https://www.foodandwaterwatch.org/news/2026/10/16/californians-are-standing-up-to-data-centers/",
    # midterm politics or power prices, no specific pushback step in the summary
    "https://techcrunch.com/2026/10/31/data-centers-are-now-a-midterm-issue-even-in-brooklyn/",
    # midterm politics or power prices, no specific pushback step in the summary
    "https://www.dawn.com/news/2041193/power-bills-and-data-centres-cast-rare-spotlight-on-utilities-in-us-midterms",
    # water and land plans in Thailand, can't tell from the summary it is local pushback
    "https://www.channelnewsasia.com/asia/thailand-data-centres-water-elephants-6465091",
    # Anthropic turbine purchase, not a step in the IPO
    "https://techcrunch.com/2026/11/09/anthropic-joins-ais-natural-gas-frenzy-buys-3-4b-worth-of-turbines/",
    # election commentary, can't tell from the summary it reports a data-centre pushback step
    "https://olhardigital.com.br/2026/11/04/pro/eleicao-nos-eua-expoe-reacao-a-bilionarios-e-data-centers-de-ia/",
    # analysis around the IPO, reports nothing new
    "https://www.xataka.com/empresas-y-economia/anthropic-ingresa-17-000-millones-al-trimestre-su-factura-computacion-50-veces-mayor",
    # analysis around the IPO, reports nothing new
    "https://www.xataka.com/empresas-y-economia/salida-a-bolsa-anthropic-conseguira-algo-poco-habitual-como-que-80-su-plantilla-se-haga-millonaria",
    # stock exchange listing and a builder, can't tell from the summary it is a step in Anthropic's IPO
    "https://www.xataka.com/empresas-y-economia/que-anthropic-salga-a-bolsa-va-a-tener-consecuencias-para-constructora-espanola-ferrovial",
    # opinion on sharing AI's wealth, not a step in the IPO
    "https://www.xataka.com/robotica-e-ia/elon-musk-anthropic-discrepan-como-repartir-riqueza-generada-ia",
    # job ad story, not about the IPO
    "https://www.xataka.com/empresas-y-economia/anthropic-ofrece-172-000-euros-al-ano-a-alguien-que-quiera-hacer-exactamente-trabajo-que-deberia-hacer-agente-ia",
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


def _open(c: dict, since: str, held: set[str]) -> bool:
    """A story still to check: from `since`, in a stream topics follow, not a tracked bill, on no list yet."""
    return c["date"] >= since and c.get("category") in STREAMS and not c.get("bill") and not _urls(c) & held


# The model's net catches what words and tags both miss. Each story to check is compared, with the local story model
# (embed.py: runs on this machine, nothing billed), with each topic's newest NEAR_REF stories and NEAR_OTHER other
# stories that are in no topic. When VOTES of its NEIGHBOURS closest are one topic's, and the closest is at least NEAR
# alike, it's a candidate for that topic, with that closest story as the reason. Set on the stories of 27 Oct-10 Nov
# 2026: about seven in ten such finds belonged; a looser vote let in conference notices and grid-supplier adverts.
NEIGHBOURS, VOTES, NEAR = 10, 7, 0.77
NEAR_REF, NEAR_OTHER = 40, 1500
NEAR_DAYS = 7  # with no `since`, the model checks only this many days back (it reads about ten stories a second)


def near(cards: list[dict], since: str = "", encode=None) -> dict[str, dict[str, str]]:
    """{story URL: {topic slug: headline of the topic's story it reads most like}} for stories from `since` that a
    topic's words don't match; {} when the model isn't available. `encode` (texts -> unit vectors) is for tests."""
    if encode is None:
        from . import embed
        if not embed.available():
            return {}
        encode = embed.encode
    from . import embed
    import numpy as np
    since = since or (date.today() - timedelta(days=NEAR_DAYS)).isoformat()
    held = LEFT_OUT | {u for urls in ADDED.values() for u in urls}
    newest = sorted(cards, key=lambda c: c["date"], reverse=True)
    todo = [c for c in newest if _open(c, since, held)]
    if not todo:
        return {}
    ref = [(slug, c) for slug in TOPICS for c in [c for c in newest if matches(slug, c)][:NEAR_REF]]
    ref += [(None, c) for c in [c for c in newest if c["date"] < since and c.get("category") in STREAMS
                                and not part_of(c)][:NEAR_OTHER]]
    vecs = np.asarray(encode([embed.story_text(c["title"], c.get("summary") or "") for _, c in ref + [(None, c) for c in todo]]))
    alike = vecs[len(ref):] @ vecs[:len(ref)].T
    out = {}
    for c, row in zip(todo, alike):
        top = np.argsort(-row)[:NEIGHBOURS]
        for slug in {ref[j][0] for j in top} - {None}:
            if matches(slug, c):
                continue
            mine = [j for j in top if ref[j][0] == slug]
            if len(mine) >= VOTES and row[mine[0]] >= NEAR:
                out.setdefault(c["url"], {})[slug] = ref[mine[0]][1]["title"]
    return out


def candidates(cards: list[dict], since: str = "", alike: dict[str, dict[str, str]] | None = None) -> list[dict]:
    """Stories from `since` that carry a topic's net of tags, or that the model finds read like its stories (`alike`,
    from near()), but that its words don't match and no list holds yet: one per event, newest first, each with the
    topics to check it for (`for`) and, for the model's finds, the story each reads like (`like`). A tracked bill joins
    only where listed."""
    held = LEFT_OUT | {u for urls in ADDED.values() for u in urls}
    alike = alike or {}
    out = []
    for c in sorted(cards, key=lambda c: c["date"], reverse=True):
        if not _open(c, since, held):
            continue
        tags = set(c.get("tags") or [])
        like = alike.get(c["url"], {})
        found = [slug for slug, t in TOPICS.items()
                 if (any(n <= tags for n in t.get("net", ())) or slug in like) and not matches(slug, c)]
        if found:
            out.append({**c, "for": found, "like": {s: like[s] for s in found if s in like}})
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
                    "official": False, "logo": _logo(c), "tags": c.get("tags") or [], "category": c["category"],
                    "summary": ADDED.get(slug, {}).get(c["url"]) or c.get("summary") or ""})
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
    # the story's beats, told one at a time at the top of the page: how it started, its key moments, where it stands
    for e in (out[:1] + key + out[-1:]) if out else ():
        e["beat"] = True
        if not e["official"]:
            e["line"] = _line(e["title"], e["summary"])
    for e in out:
        e.pop("tags", None), e.pop("category", None), e.pop("summary", None)
    return out


def _line(title: str, summary: str) -> str:
    """A beat's one sentence: the first of the publisher's own summary (or our English note), unless it only repeats
    the headline."""
    s = re.split(r"(?<=[.!?])(?<!\.[A-Z]\.)(?<!\b[A-Z]\.)(?<!Mr\.)(?<!Ms\.)(?<!Dr\.)(?<!St\.)\s+(?=[A-Z\"“‘'])", " ".join(summary.split()), maxsplit=1)[0].strip()
    if len(s) < 25 or len(s) > 260:
        return ""
    words = lambda t: set(re.findall(r"\w+", t.lower()))
    return "" if len(words(s) - words(title)) < 4 else s


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
    if(window.tellStory) window.tellStory(list);
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
  }).catch(() => tl.querySelector(".ssr-list") || tl.replaceChildren(el("p", "meta", "Couldn't load the timeline. Try reloading the page.")));
})();
</script>"""


_WORDS = ["", "", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"]
SAY = "say"  # a beat's spoken clip: topics/<slug>/say/<clip>.mp3 (topic-voice), named after its words


def _gap(a: str, b: str) -> str:
    """How long after the last beat, in words (the card's cue uses the same, in STORY_JS)."""
    d = (date.fromisoformat(b) - date.fromisoformat(a)).days
    n = lambda k, unit: f"a {unit} later" if k == 1 else f"{(_WORDS[k] if k < len(_WORDS) else str(k)).lower()} {unit}s later"
    return ("the same day" if d == 0 else "the next day" if d == 1 else n(d, "day") if d < 7 else "a week later"
            if d < 14 else n(round(d / 7), "week") if d < 30 else n(round(d / 30.4), "month") if d < 365
            else n(round(d / 365), "year"))


def tell(name: str, ev: list[dict]) -> None:
    """What the voice says for each beat, like a presenter telling the story rather than reading the card: how it
    started, how each moment followed the last, where it stands. Fixed phrases joining the headline and the
    publisher's own sentence, credited to them ("As TechCrunch put it"); never a count of outlets, never words of
    ours about the people in it. Sets each beat's `say` and its clip's name."""
    from . import audio
    beats = [e for e in ev if e.get("beat")]
    if len(beats) < 2:
        return
    news = [e for e in beats[1:-1] if not e["official"]]
    loudest = max(news, key=lambda e: e["outlets"]) if news else None
    grew, more = iter(("it got bigger.", "it grew again.", "it kept growing.")), iter(("there was more.", "came the next turn.", "another part came out."))
    for i, e in enumerate(beats):
        when = date.fromisoformat(e["date"])
        on = f"{when:%A} the {audio._nth(when)} of {when:%B}"
        gap = _gap(beats[i - 1]["date"], e["date"]) if i else ""
        if i == 0:
            lead = f"Here's the story so far of {name}. It started on {on}."
        elif i == len(beats) - 1:
            lead = f"And the latest, {gap}."
        elif e is loudest and e["outlets"] > 1:
            lead = f"Then came the biggest moment, {gap}."
        elif e["official"]:
            lead = f"{gap[0].upper() + gap[1:]}, it reached the official record."
        elif e["outlets"] > beats[i - 1]["outlets"]:
            lead = f"{gap[0].upper() + gap[1:]}, {next(grew, 'it grew again.')}"
        else:
            lead = f"{gap[0].upper() + gap[1:]}, {next(more, 'there was more.')}"
        head = e["title"].strip()
        head = head if head.endswith((".", "?", "!")) else head + "."
        if e["official"]:
            body = f"{head} That's from {e['source']}."
        elif e.get("line"):
            body = f"{head} As {e['source']} put it: {e['line']}"
        else:
            body = f"{head} That's according to {e['source']}."
        tail = " That's the story so far. Every report is on the timeline below." if i == len(beats) - 1 else ""
        said = re.sub(r"\b[A-Z]{5,}\b", lambda m: m[0].title(), f"{lead} {body}{tail}")  # NVIDIA as a word, not letters
        e["say"] = audio._clean(said)
        e["clip"] = hashlib.sha1(e["say"].encode()).hexdigest()[:12] + ".mp3"


def speak(site: Path, cache: Path, log=print) -> int:
    """Each topic's beat clips into site/topics/<slug>/say/, read by the daily listen's offline voice (audio.speak):
    a clip already in `cache` (kept between runs) is copied, a new one spoken once, and clips no beat uses any more
    leave the cache. Without the voice (a quick run) only the kept ones are copied; a beat without its clip falls back
    to the browser's voice on the page. Returns how many were spoken."""
    from . import audio
    voice, spoken, used = audio._voice(), 0, set()
    if voice is None:
        log("topic-voice: no voice (pip install piper-tts lameenc, and audio.VOICE); copying the kept clips only")
    cache.mkdir(parents=True, exist_ok=True)
    for f in sorted((site / "topics").glob("*/events.json")):
        for e in json.loads(f.read_text(encoding="utf-8")):
            if not e.get("clip"):
                continue
            used.add(e["clip"])
            kept = cache / e["clip"]
            if not kept.exists() and voice is not None:
                kept.write_bytes(audio.speak(e["say"], voice))
                spoken += 1
            if kept.exists():
                (f.parent / SAY).mkdir(exist_ok=True)
                shutil.copyfile(kept, f.parent / SAY / e["clip"])
    for old in cache.glob("*.mp3"):
        if old.name not in used:
            old.unlink()
    return spoken


STORY_HTML = (
    '<section class="story" id="moments" hidden aria-label="The story so far">'
    '<div class="st-head"><h2>The story so far</h2><div class="st-ctl">'
    '<button type="button" class="st-prev" aria-label="Previous moment">Back</button>'
    '<button type="button" class="st-play">Play the story</button>'
    '<button type="button" class="st-next" aria-label="Next moment">Next</button>'
    '<button type="button" class="st-say" aria-pressed="false">Listen</button></div></div>'
    '<figure class="st-loud"><div class="st-chart"></div><figcaption class="st-note"></figcaption></figure>'
    '<div class="st-stage" tabindex="0" aria-live="polite"><article class="st-card"></article>'
    '<div class="st-bar"><span></span></div></div></section>\n')

# The story told a beat at a time: a thin line of how loud it got (reports a day, or a week for long stories) with the
# beats as dots, and a card per beat. Play steps through on its own; Listen tells it in the daily listen's offline
# voice (tell, speak), or the browser's own if a clip is missing. The words joining the beats are fixed phrases.
STORY_JS = r"""<script>
window.tellStory = list => {
  const box = document.getElementById("moments"), beats = list.filter(e => e.beat);
  if(beats.length < 2) return;
  const $ = s => box.querySelector(s), el = (tag, cls, text) => { const e = document.createElement(tag); if(cls) e.className = cls; if(text != null) e.textContent = text; return e; };
  const D = d => new Date(d.slice(0, 10) + "T00:00:00Z"), DAY = 864e5;
  const fmt = (d, o) => D(d).toLocaleDateString(undefined, {...o, timeZone: "UTC"});
  const full = d => fmt(d, {day: "numeric", month: "long", year: "numeric"}), short = d => fmt(d, {day: "numeric", month: "short"});
  const WORDS = ["", "", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve"];
  const n = (k, unit) => k === 1 ? "A " + unit + " later" : (WORDS[k] || k) + " " + unit + "s later";
  const gap = (a, b) => {
    const d = Math.round((D(b) - D(a)) / DAY);
    return d === 0 ? "The same day" : d === 1 ? "The next day" : d < 7 ? n(d, "day") : d < 14 ? "A week later"
      : d < 30 ? n(Math.round(d / 7), "week") : d < 365 ? n(Math.round(d / 30.4), "month") : n(Math.round(d / 365), "year");
  };
  const loudest = beats.slice(1, -1).reduce((m, e) => !e.official && (!m || e.outlets > m.outlets) ? e : m, null);
  const cue = (e, i) => {
    const g = i ? gap(beats[i - 1].date, e.date) : "", low = g.charAt(0).toLowerCase() + g.slice(1);
    if(!i) return "How it started";
    if(i === beats.length - 1) return "Where it stands now, " + low;
    if(e === loudest && e.outlets > 1) return "The biggest moment, " + low;
    if(e.official) return "On the record, " + low;
    return g;
  };
  // how loud it got: every event's outlets, by day (by week for a story over three months)
  const t0 = +D(list[0].date), t1 = Math.max(+D(list[list.length - 1].date), t0 + DAY), weekly = (t1 - t0) / DAY > 90;
  const bin = d => Math.floor((D(d) - t0) / DAY / (weekly ? 7 : 1)), nb = bin(new Date(t1).toISOString()) + 1;
  const vol = new Array(nb).fill(0); list.forEach(e => vol[bin(e.date)] += e.outlets);
  const peak = vol.indexOf(Math.max(...vol));
  $(".st-note").textContent = "How loud it got: reports " + (weekly ? "each week" : "each day") + ", every outlet counted once. "
    + "The dots are the moments below; tap one.";
  let at = 0, timer = null, playing = false;
  const chart = $(".st-chart");
  const draw = () => {
    const W = chart.clientWidth || 600, H = 120, L = 6, R = 6, T = 22, B = 22;
    const x = i => L + (nb > 1 ? i / (nb - 1) : .5) * (W - L - R), top = Math.max(...vol), y = v => T + (1 - v / top) * (H - T - B);
    const NS = "http://www.w3.org/2000/svg", mk = (tag, a) => { const e = document.createElementNS(NS, tag); for(const k in a) e.setAttribute(k, a[k]); return e; };
    const svg = mk("svg", {width: W, height: H, viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "How many reports each " + (weekly ? "week" : "day")});
    const pts = vol.map((v, i) => [x(i), y(v)]);
    svg.append(mk("line", {x1: L, x2: W - R, y1: H - B, y2: H - B, class: "ax"}));
    svg.append(mk("path", {d: "M" + pts.map(p => p.join(",")).join("L") + `L${x(nb - 1)},${H - B}L${x(0)},${H - B}Z`, class: "area"}));
    svg.append(mk("path", {d: "M" + pts.map(p => p.join(",")).join("L"), class: "ln"}));
    const lab = (t, xx, yy, anchor, cls) => { const e = mk("text", {x: xx, y: yy, "text-anchor": anchor, class: cls || "lb"}); e.textContent = t; svg.append(e); };
    lab(short(list[0].date), L, H - 6, "start"); lab(short(list[list.length - 1].date), W - R, H - 6, "end");
    const px = x(peak), pa = px < 90 ? "start" : px > W - 90 ? "end" : "middle";
    lab(vol[peak] + " reports" + (weekly ? " in the week of " : " on ") + short(new Date(+t0 + peak * DAY * (weekly ? 7 : 1)).toISOString()), px, T - 8, pa, "lb pk");
    beats.forEach((e, i) => {
      const g = mk("g", {class: "bt" + (i === at ? " on" : ""), tabindex: 0, role: "button", "aria-label": cue(e, i) + ", " + full(e.date)});
      const same = beats.filter(o => bin(o.date) === bin(e.date)), k = same.length - 1 - same.indexOf(e);
      const cx = x(bin(e.date)) - k * 13, cy = y(vol[bin(e.date)]) + k * 4;  // beats on one day fan out to the left
      if(i === at) g.append(mk("line", {x1: cx, x2: cx, y1: cy, y2: H - B, class: "drop"}));
      g.append(mk("circle", {cx, cy, r: 14, class: "hit"}), mk("circle", {cx, cy, r: i === at ? 6 : 4.5, class: "dot"}));
      g.addEventListener("click", () => { stop(); go(i); });
      g.addEventListener("keydown", k => { if(k.key === "Enter" || k.key === " ") { k.preventDefault(); stop(); go(i); } });
      svg.append(g);
    });
    chart.replaceChildren(svg);
  };
  // the card
  const logo = e => {
    if(!e.logo) return null;
    const s = el("span", "logo"); s.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path></path></svg>';
    const p = s.querySelector("path"); p.setAttribute("fill", "#" + e.logo.hex.replace("#", "")); p.setAttribute("d", e.logo.path);
    return s;
  };
  const card = $(".st-card");
  const show = () => {
    const e = beats[at], c = el("article", "st-card");
    const top = el("p", "st-cue"); top.append(el("span", "", cue(e, at)), el("span", "st-when", full(e.date)));
    c.append(top, el("h3", "", e.title));
    if(e.line) c.append(el("p", "st-line", e.line));
    const src = el("div", "st-src"), lg = logo(e); if(lg) src.append(lg);
    src.append(el("span", "", (e.official ? "From " : "Reported by ") + e.source + (e.outlets > 1 ? " and " + (e.outlets - 1) + " more outlet" + (e.outlets > 2 ? "s" : "") : "")));
    const a = el("a", "st-read", "Read the report"); a.href = e.url; a.rel = "noopener"; a.target = "_blank";
    src.append(a); c.append(src);
    const old = box.querySelector(".st-card"); old.replaceWith(c);
    $(".st-prev").disabled = at === 0; $(".st-next").disabled = at === beats.length - 1;
    draw();
  };
  const go = i => { at = Math.max(0, Math.min(beats.length - 1, i)); show(); };
  // Play and Listen
  const bar = $(".st-bar span"), play = $(".st-play"), say = $(".st-say");
  const synth = window.speechSynthesis;
  const voice = () => { const v = (synth && synth.getVoices() || []).filter(v => v.localService && /^en/i.test(v.lang));
    return v.find(v => /en-GB/i.test(v.lang)) || v[0] || null; };
  let listen = false;
  let clip = null;
  const stop = () => { playing = false; clearTimeout(timer); if(synth) synth.cancel(); if(clip) clip.pause(); bar.style.transition = "none"; bar.style.width = "0";
    play.textContent = at === beats.length - 1 ? "Play again" : "Play the story"; play.setAttribute("aria-pressed", "false"); };
  const step = () => {
    if(!playing) return;
    const next = () => { if(!playing) return; if(at === beats.length - 1) return stop(); go(at + 1); step(); };
    bar.style.transition = "none"; bar.style.width = "0"; void bar.offsetWidth;
    if(listen) {
      const e = beats[at], done = () => { timer = setTimeout(next, 600); };
      let fell = false;
      const browser = () => {  // no clip (a build without the voice): the browser's own, same words
        if(fell) return; fell = true;
        if(!synth) return done();
        const u = new SpeechSynthesisUtterance(e.say || e.title), v = voice(); if(v) u.voice = v;
        u.onend = done; synth.cancel(); synth.speak(u);
      };
      if(clip) clip.pause();
      if(!e.clip) return browser();
      clip = new Audio(document.getElementById("timeline").dataset.src.replace(/events\.json$/, "say/") + e.clip); clip.onended = done; clip.onerror = browser;
      clip.ontimeupdate = () => { if(clip.duration) bar.style.width = (100 * clip.currentTime / clip.duration) + "%"; };
      clip.play().catch(browser);
    } else {
      const ms = 6500 + (beats[at].line ? 2500 : 0);
      bar.style.transition = `width ${ms}ms linear`; bar.style.width = "100%"; timer = setTimeout(next, ms);
    }
  };
  play.addEventListener("click", () => {
    if(playing) return stop();
    if(at === beats.length - 1) go(0);
    playing = true; play.textContent = "Pause"; play.setAttribute("aria-pressed", "true"); step();
  });
  say.addEventListener("click", () => {
    listen = !listen; say.setAttribute("aria-pressed", String(listen)); say.textContent = listen ? "Listening" : "Listen";
    if(playing) { clearTimeout(timer); if(synth) synth.cancel(); if(clip) clip.pause(); step(); }
    else if(listen) { playing = true; play.textContent = "Pause"; play.setAttribute("aria-pressed", "true"); step(); }
  });
  $(".st-prev").addEventListener("click", () => { stop(); go(at - 1); });
  $(".st-next").addEventListener("click", () => { stop(); go(at + 1); });
  const stage = $(".st-stage");
  stage.addEventListener("keydown", k => { if(k.key === "ArrowLeft") { stop(); go(at - 1); } if(k.key === "ArrowRight") { stop(); go(at + 1); } });
  let sx = null;
  stage.addEventListener("pointerdown", p => { sx = p.clientX; });
  stage.addEventListener("pointerup", p => { if(sx == null) return; const dx = p.clientX - sx; sx = null;
    if(Math.abs(dx) > 45) { stop(); go(at + (dx < 0 ? 1 : -1)); } });
  box.hidden = false;
  show();
  new ResizeObserver(draw).observe(chart);
};
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
        tell(t["name"], ev)
        (out / p / "events.json").write_text(json.dumps(ev, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        badges = _badges(slug, ev)
        status = '<span class="done">Concluded</span>' if done else ""
        related = " · ".join(f'<a href="/{path(r)}">{escape(TOPICS[r]["name"])}</a>' for r in t.get("related", ()))
        body = (f'<div class="tp">\n<div class="topic-hero">{_photo(slug)}<div class="over"><span class="kind">'
                f'{escape(t["kind"])}</span>{status}<h1>{escape(t["name"])}</h1><p class="what">{escape(t["what"])}</p>'
                f'<div class="badges">{badges}</div></div></div>\n'
                + STORY_HTML +
                '<h2>How it unfolded</h2>\n'
                + ('<p class="legend"><span class="lg official">Official record</span>'
                   '<span class="lg news">In the news</span></p>\n' if any(e["official"] for e in ev) else "")
                + f'<div class="chapters" id="timeline" data-src="/{p}events.json">'
                + (f'<ul class="ssr-list">{seo.items(seo.newest(ev, 40))}</ul>' if ev else '<p class="meta">Loading…</p>')
                + '</div>\n'  # its newest events in the HTML for search engines (seo.py); the timeline replaces them
                + (f'<p class="related">Related: {related}</p>\n' if related else "")
                + f'</div>\n{STORY_JS}\n{TIMELINE_JS}')
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
