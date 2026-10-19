"""AI safety hub (ai-safety-hub/): the safety evaluations, red-teaming findings, system cards and safety frameworks
that AI labs, government safety institutes, independent evaluators and industry bodies published in 2026, in one
place, searchable and filtered by type and risk.

Every document in DOCS was read by hand from the publisher's own pages (the owner's choice, 15 Oct 2026: a hand-checked
list, 2026 only): its title and date as the publisher gives them, a link to it and to its PDF or paper, the models it
tests, the risks it covers and its abstract word for word. The abstract is the publisher's own: the document's abstract
or executive summary (its opening paragraphs, cut at a sentence and marked with … when it runs on for pages), else the
opening of its introduction, else the description the publisher gives on the page. A document with none shows none. A risk is tagged only when the document
has a section or passage on it (system cards: their table of contents). A model's weights are "open" when its maker
published them (on Hugging Face, in the stories we collect) and "closed" when it didn't.

Kept: documents that test or attack AI models, give a way to evaluate them, or set out a safety framework or guidance.
Left out (LEFT_OUT): research on training methods, essays, usage studies, testimony and organisation news. Publishers
are read only where robots.txt allows (checked 15 Oct 2026). `python -m aipulse safety` lists stories we collect that
may be a new document. Linked from Policy's strip on the front page.
"""
from __future__ import annotations

import json
import re
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from . import pages, rss

PATH = "ai-safety-hub/"
SINCE = "2026-01-01"
QUESTION = "How are AI models tested for safety, and what did the testers find?"

# what a document is: (its words on the page, what it means, its colour: Okabe-Ito, dark text on it, how many are called)
KINDS = {
    "card": ("System card", "A lab's report on a model it releases: what it tested and the safeguards it uses.", "#56B4E9",
             "system cards"),
    "eval": ("Evaluation", "Tests of what models can do or how they behave, or a way to run such tests.", "#009E73",
             "evaluations"),
    "redteam": ("Red-teaming", "Attacks on models and their safeguards, to find what gets through.", "#F85C48",
                "red-teaming reports"),
    "framework": ("Framework & guidance", "Rules, practices and proposals for testing and managing AI risks.", "#E69F00",
                  "frameworks and guidance"),
}

# the risks a document covers: (its words on the page, what it means)
RISKS = {
    "jailbreak": ("Jailbreaks", "Prompts that get a model to break its own rules."),
    "injection": ("Prompt injection", "Instructions hidden in web pages, files or tools that take over an AI agent."),
    "cyber": ("Cyber attacks", "Finding software flaws, writing exploits, hacking."),
    "cbrn": ("Chemical, biological & nuclear", "Help towards weapons that could cause mass harm."),
    "misalign": ("Deception & misalignment", "Models lying, scheming, sabotaging or hiding what they do."),
    "control": ("Loss of control", "Models escaping oversight, copying themselves or running unsanctioned."),
    "rnd": ("AI building AI", "Models automating AI research and speeding up their own development."),
    "persuasion": ("Manipulation", "Persuasion, flattery and influence operations."),
    "harm": ("Harmful content & bias", "Child safety, mental health, violent or sexual content, political bias."),
    "tamper": ("Tampering & theft", "Poisoned training data, backdoors and copying a model by distillation."),
    "physical": ("Physical world", "Robots, drones and conventional weapons."),
}

# who published it
PUBLISHERS = {
    "Anthropic": "lab", "OpenAI": "lab", "Google DeepMind": "lab", "Meta": "lab",
    "UK AI Security Institute": "institute", "NIST (CAISI)": "institute",
    "METR": "evaluator", "Apollo Research": "evaluator",
    "Frontier Model Forum": "industry", "International AI Safety Report": "panel",
}

# the models documents test: (who makes it, are its weights published). Open = on Hugging Face in our stories (Kimi
# K3, GLM-5.2, GLM-5.3, DeepSeek V4 Pro); Meta's Muse Spark is its first model without open weights (The Decoder,
# 8 Apr 2026).
MAKERS = [(r"^(Claude)\b", "Anthropic", "closed"), (r"^(GPT|ChatGPT)\b", "OpenAI", "closed"),
          (r"^Gemini\b", "Google", "closed"), (r"^Muse\b", "Meta", "closed"), (r"^GLM\b", "Z.ai", "open"),
          (r"^Kimi\b", "Moonshot AI", "open"), (r"^DeepSeek\b", "DeepSeek", "open")]


def maker(model: str) -> tuple[str, str]:
    """A model's maker and whether its weights are open: 'GLM-5.3' → ('Z.ai', 'open')."""
    for pattern, who, weights in MAKERS:
        if re.match(pattern, model):
            return who, weights
    raise ValueError(f"no maker for {model}")


# Every document the page shows, read by hand on the publisher's own pages. Checked 15 Oct 2026.
DOCS: list[dict] = [
    dict(date='2026-10-16', by='NIST (CAISI)', kind='framework',
         title='Key Practices for Incident Readiness and Response in Super Intelligence Training and Evaluation',
         url='https://www.nist.gov/news-events/news/2026/10/key-practices-incident-readiness-and-response-super-intelligence-training',
         original='https://www.nist.gov/system/files/documents/2026/10/16/Key_Practices_for_Incident_Readiness_and_Response_in_Super_Intelligence%20_Training_and_Evaluation.pdf',
         models=(), risks=('control',),
         abstract=('This document sets out ten voluntary key practices to guide emerging approaches in the '
                   'management of incidents that might occur during the training and evaluation of super '
                   'intelligence (SI) agents. While these incidents highlight the importance of traditional '
                   'cybersecurity principles and practices, they also introduce novel considerations for incident '
                   'prevention, response, and reporting. These novel considerations primarily stem from the '
                   'agentic nature and advanced cyber capabilities of cutting-edge SI systems.')),
    dict(date='2026-10-15', by='OpenAI', kind='card',
         title='GPT-Live-1.1 system card',
         url='https://deploymentsafety.openai.com/gpt-live-1-1',
         original='https://deploymentsafety.openai.com/gpt-live-1-1/gpt-live-1-1.pdf',
         models=('GPT-Live-1.1', 'GPT-Live-1.1 Quip'), risks=('cbrn', 'cyber', 'harm', 'misalign', 'rnd'),
         abstract=('GPT-Live-1.1 and GPT-Live-1.1 Quip are our most recent iterations in the GPT-Live model family, '
                   'voice models designed to make conversations with AI feel more natural and intelligent. As with '
                   'their predecessors, these models are full-duplex, meaning they can listen and respond '
                   'continuously instead of waiting for a clearly defined turn to end. This means they can follow '
                   'pauses, interruptions, and changes in pace, and decide in the moment whether to respond or keep '
                   'listening.')),
    dict(date='2026-10-14', by='METR', kind='framework',
         title='Our approach to working with AI companies',
         url='https://metr.org/blog/2026-10-14-our-approach-to-risk-assessment/',
         original="",
         models=(), risks=(),
         abstract=('How we approach working with AI companies on projects that the public might rely on to '
                   'understand risks.')),
    dict(date='2026-10-14', by='METR', kind='framework',
         title='How an assessor could investigate evidence of acceleration from the automation of AI R&D',
         url='https://metr.org/blog/2026-10-14-ai-rd-acceleration-assessment-proposal/',
         original="",
         models=(), risks=('rnd',),
         abstract=('Our proposal is to analyze how much AI automation is accelerating capability growth internally.')),
    dict(date='2026-10-14', by='METR', kind='framework',
         title='How an assessor could investigate control and monitoring of internal AI agents',
         url='https://metr.org/blog/2026-10-14-control-assessment-proposal/',
         original="",
         models=(), risks=('control',),
         abstract=('Our proposal is to analyze whether a developer’s internal agents could get away with serious '
                   'harm without being caught.')),
    dict(date='2026-10-14', by='METR', kind='framework',
         title='How an assessor could investigate alignment of unreleased AI models',
         url='https://metr.org/blog/2026-10-14-alignment-assessment-proposal/',
         original="",
         models=(), risks=('misalign',),
         abstract=('Our proposal is to analyze a developer’s internal incidents and whether training may suppress '
                   'evidence of worse misalignment.')),
    dict(date='2026-10-14', by='METR', kind='framework',
         title='A proposal for better informing the public about loss-of-control risks from frontier AI development',
         url='https://metr.org/blog/2026-10-14-better-informing-the-public-about-loss-of-control-risks/',
         original="",
         models=(), risks=('control',),
         abstract=('The key questions about internal AI development the public needs more evidence about, and a '
                   'concrete proposal for how developers could work with METR to produce and share that evidence.')),
    dict(date='2026-10-13', by='Google DeepMind', kind='card',
         title='Gemini 4 Argon Safety & Security Report',
         url='https://blog.google/innovation-and-ai/technology/safety-security/gemini-4-model-safety-security/',
         original='https://storage.googleapis.com/deepmind-media/gemini/gemini_4_safety_report.pdf',
         models=('Gemini 4 Argon',), risks=('cbrn', 'control', 'cyber', 'jailbreak', 'misalign', 'persuasion', 'rnd'),
         abstract=('This report describes the safety, security, and alignment testing for Gemini 4 Argon, the '
                   'first model in our next-generation Gemini 4 series and the most capable model Google has '
                   'deployed to date. Argon delivers major advances in multi-step reasoning, autonomous software '
                   'engineering, multimodal understanding, and complex cybersecurity and enterprise workflows. '
                   'Aligned with our Frontier Safety Framework and Google’s AI Principles, we pair these '
                   'capability advances with rigorous safety and security evaluations designed to ensure the model'
                   ' is safe, helpful, and resilient against misuse. …')),
    dict(date='2026-10-12', by='Anthropic', kind='redteam',
         title='AI models may be capable of self-replicating without access to a datacenter',
         url='https://www.anthropic.com/research/self-replicating-ai',
         original="",
         models=(), risks=('control',),
         abstract=('Small AI models may be only months away from being able to self-replicate across cheap IoT '
                   'devices like Android TV boxes, with no datacenter needed.')),
    dict(date='2026-10-07', by='UK AI Security Institute', kind='eval',
         title='Transect: Retaining Observability for Long-Horizon LLM Agent Evaluations',
         url='https://www.aisi.gov.uk/research/transect-retaining-observability-for-long-horizon-llm-agent-evaluations',
         original='https://arxiv.org/abs/2610.08364',
         models=(), risks=(),
         abstract=('Frontier AI evaluations increasingly use open-ended, agentic, long-horizon tasks whose '
                   'transcripts can span hundreds of pages of outputs and actions from complex multi-agent '
                   'networks. The observability envelop-the range of what evaluators can reliably infer about an '
                   "agent's behaviours-is therefore narrowing. Language model assistants can help classify and "
                   'interpret agent behaviour but also afford human evaluators significant analytical degrees of '
                   'freedom, threatening the reproducibility and auditability of language-model-based transcript '
                   'analysis. Transect is an open source package built on Inspect Scout to help evaluators '
                   'understand how a long agent run unfolded, identify behaviour worth investigating, and check '
                   'interpretations against the transcript. Users specify task context and behavioural vocabulary '
                   'in a reusable evaluation-family configuration, with judge models and analysis settings '
                   "supplied separately. Transect's navigable reports align recorded events, token use, sub-agent "
                   'activity, and model-generated behavioural labels on a common turn-based timeline. Reviewers '
                   "can quickly grasp a run's narrative, trace any label or event to its source turns, and export "
                   'the underlying data tables for cross-run analysis. We demonstrate the workflow on an AI R&D '
                   "evaluation that generated almost 13 million tokens, dividing the agents' work into behavioural"
                   ' phases aligned with research-skill classifications, sub-agent delegations and interactions, '
                   'and token use. The combined view shows a focus on operational work and manuscript production, '
                   'with little evidence of a sustained hypothesis generation stage-arguably a necessary component'
                   " for high-quality scientific outputs. Transect's flexible, customisable transcript-analysis "
                   'pipeline will enable evaluators to keep pace with longer, more complex, more frequent AI '
                   'evaluations while supporting scientific rigour, transparency, and reproducibility.')),
    dict(date='2026-10-07', by='Anthropic', kind='card',
         title='System Card: Claude Haiku 5.5',
         url='https://www.anthropic.com/claude-haiku-5-5-system-card',
         original="",
         models=('Claude Haiku 5.5',), risks=('cyber', 'harm', 'injection', 'misalign', 'rnd'),
         abstract=('This system card describes Claude Haiku 5.5, the latest Haiku-class large language model from '
                   'Anthropic. We present results from a wide variety of pre-deployment evaluations, which show '
                   'Claude Haiku 5.5 significantly outperforming its predecessor, Claude Haiku 4.5, across many '
                   'domains. In a few areas, it rivaled or exceeded Claude Sonnet 5.5. We have condensed the '
                   'content of this system card in a number of ways so that we can better concentrate our '
                   'pre-deployment testing on thoroughly investigating the capabilities of our frontier models. '
                   'Specifically: ● We omit some evaluations that require large amounts of human time to obtain '
                   'trustworthy results from, when they are not critical to the takeaways of a section. ● We focus'
                   ' on presenting numerical results from our evaluations, and dedicate less space to a prose '
                   'analysis of those evaluations or their results, especially in cases where we have already '
                   'explained the evaluation in question in a previous system card. As a result, this system card '
                   'is somewhat shorter than some previous ones. We expect system cards for our non-frontier '
                   'models to be similarly condensed going forward, except where a specific model has notable '
                   'properties that are deserving of in-depth elaboration. Below, we summarize the findings from '
                   'this system card. …')),
    dict(date='2026-10-07', by='OpenAI', kind='card',
         title='GPT-6 Sol and GPT-6 Luna: October 2026 update',
         url='https://deploymentsafety.openai.com/gpt-6-october',
         original='https://deploymentsafety.openai.com/gpt-6-october/gpt-6-october.pdf',
         models=('GPT-6 Sol', 'GPT-6 Luna'), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'misalign', 'rnd'),
         abstract=('We’re launching GPT-6 to everyone in ChatGPT, across free and paid plans globally. These '
                   'models will replace GPT-5.6 Sol and GPT-5.6 Luna in ChatGPT. Users accessing GPT-6 Sol and '
                   'GPT-6 Luna in Codex, and via ChatGPT Work, are still using previously released versions. In '
                   'this system card, we distinguish these models by their month of release: October for the '
                   'versions released today, and September for the versions that remain in use in Codex and Work.')),
    dict(date='2026-10-06', by='METR', kind='framework',
         title='AI systems could cover up misbehavior',
         url='https://metr.org/blog/2026-10-06-ai-systems-could-cover-up-misbehavior/',
         original="",
         models=(), risks=('misalign',),
         abstract=('As AIs start covering up evidence of misbehavior, observability tools should be treated as '
                   'security-critical infrastructure.')),
    dict(date='2026-10-01', by='Apollo Research', kind='framework',
         title='Towards embedded evaluations for scheming propensities',
         url='https://www.apolloresearch.ai/blog/towards-embedded-evaluations-for-scheming-propensities',
         original="",
         models=(), risks=('misalign',),
         abstract=('Embedded evaluations for frontier AI scheming: four claims every safety case must make, and '
                   'the persistent, deep access embedded evaluators need to verify them.')),
    dict(date='2026-09-30', by='Apollo Research', kind='framework',
         title='Principles for Embedded Evaluations',
         url='https://www.apolloresearch.ai/blog/principles-for-embedded-evaluations',
         original="",
         models=(), risks=(),
         abstract=('A framework for embedded evaluations of frontier AI developers, centered on claim-based, '
                   'publicly reported assessments.')),
    dict(date='2026-09-29', by='Anthropic', kind='redteam',
         title='GLM-5.3 and the spread of advanced cyber capabilities',
         url='https://www.anthropic.com/research/glm-5-3-and-the-spread-of-advanced-cyber-capabilities',
         original="",
         models=('GLM-5.3',), risks=('cyber',),
         abstract=('GLM-5.3 can autonomously build end-to-end cyber exploits, but unlike other frontier models, it'
                   ' was released without meaningful safeguards to limit misuse.')),
    dict(date='2026-09-29', by='Apollo Research', kind='framework',
         title='Embedded Evaluators are necessary for meaningful external testing',
         url='https://www.apolloresearch.ai/blog/embedded-evaluators-are-necessary-for-meaningful-external-testing',
         original="",
         models=(), risks=(),
         abstract=('Final-checkpoint testing could not have caught recent incidents like the Hugging Face '
                   'incident, which arose much earlier in development. Meaningful external testing requires '
                   'embedded evaluators with employee-equivalent access.')),
    dict(date='2026-09-29', by='OpenAI', kind='card',
         title='Addendum to GPT-6 Astra System Card: GPT-6.1 Sol',
         url='https://deploymentsafety.openai.com/gpt-6-1-sol',
         original='https://deploymentsafety.openai.com/gpt-6-1-sol/gpt-6-1-sol.pdf',
         models=('GPT-6.1 Sol',), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'misalign', 'rnd'),
         abstract=('Safety evaluations and safeguards for GPT-6.1 Sol, an addendum to the GPT-6 Astra system card.')),
    dict(date='2026-09-28', by='Anthropic', kind='card',
         title='System Card: Claude Sonnet 5.5',
         url='https://www.anthropic.com/claude-sonnet-5-5-system-card',
         original="",
         models=('Claude Sonnet 5.5',), risks=('cyber', 'harm', 'injection', 'misalign', 'rnd'),
         abstract=('This system card describes Claude Sonnet 5.5, the latest Sonnet-class large language model '
                   'from Anthropic. We present results from a wide variety of pre-deployment evaluations, which '
                   'show Sonnet 5.5 significantly outperforming its predecessor, Claude Sonnet 5, across many '
                   'domains. In a few areas, it rivals or exceeds Claude Opus 5.5. We have condensed the content '
                   'of this system card in a number of ways so that we can better concentrate our pre-deployment '
                   'testing on thoroughly investigating the capabilities of our frontier models. Specifically: ● '
                   'We omit some evaluations that require large amounts of human time to obtain trustworthy '
                   'results from, when they are not critical to the takeaways of a section. ● We focus on '
                   'presenting numerical results from our evaluations, and dedicate less space to a prose analysis'
                   ' of those evaluations or their results, especially in cases where we have already explained '
                   'the evaluation in question in a previous system card. As a result, this system card is '
                   'somewhat shorter than some previous ones. We expect system cards for our non-frontier models '
                   'to be similarly condensed going forward, except where a specific model has notable properties '
                   'that are deserving of in-depth elaboration. Below, we summarize the findings from this system '
                   'card. …')),
    dict(date='2026-09-28', by='UK AI Security Institute', kind='redteam',
         title='Evaluating Whether GPT-6 Astra Performs Unsanctioned Supply-Chain Attacks',
         url='https://www.aisi.gov.uk/research/evaluating-whether-gpt-6-astra-performs-unsanctioned-supply-chain-attacks',
         original='https://arxiv.org/abs/2609.38415',
         models=('GPT-6 Astra', 'GPT-5.6 Sol', 'GPT-5.5'), risks=('cyber', 'misalign'),
         abstract=('This technical report presents an alignment evaluation developed and performed by the UK AI '
                   'Security Institute for assessing whether advanced AI systems take unsanctioned actions outside'
                   ' the scope of their assigned task. We evaluate whether frontier models conduct supply-chain '
                   'attacks against out-of-scope, third-party targets when placed in difficult cybersecurity '
                   'challenges, motivated by recently observed cases of models attacking real open-source '
                   'repositories during evaluations. Applying our methods to GPT-6 Astra and previous OpenAI '
                   'models, with cyber safeguards disabled, we find that GPT-6 Astra attempts complete '
                   'supply-chain attacks in simulation at a higher rate than GPT-5.6 Sol and GPT-5.5. This '
                   'includes writing malicious code as a contribution to an out-of-scope open-source codebase, '
                   'creating fake identities to deceive open-source developers, and submitting benign '
                   'contributions before malicious ones. GPT-6 Astra frequently reasons about the scope of the '
                   'challenge in its chain-of-thought yet still proceeds to attack out-of-scope targets; it often '
                   'asks for permission, and treats an automated message as as authorisation; and it continues to '
                   'take unsanctioned actions, at a reduced rate, when internet access is more explicitly '
                   'disallowed. Our evaluation builds on an internal version of Petri, an open-source LLM auditing'
                   ' tool, with all tool calls simulated by other LLMs, so that no real network access, systems or'
                   ' third-party repositories are reachable and no real-world harm is caused. Finally, we discuss '
                   'limitations, in particular simulation awareness. We believe simulation awareness may have '
                   'driven some of the observed behaviour but does not remove our concern. Our results suggest '
                   'that defences beyond model alignment, such as sandboxing and monitoring, are increasingly '
                   'critical for safe and secure deployment.')),
    dict(date='2026-09-22', by='Anthropic', kind='card',
         title='System Card: Claude Opus 5.5',
         url='https://www.anthropic.com/claude-opus-5-5-system-card',
         original="",
         models=('Claude Opus 5.5',), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'misalign', 'persuasion', 'rnd'),
         abstract=('This system card describes Claude Opus 5.5, the latest Opus-class large language model from '
                   'Anthropic. It is an upgrade to Claude Opus 5, with gains in coding, agentic and computer use '
                   'tasks, mathematical and scientific reasoning, and long-horizon professional work. On many '
                   'evaluations, it matches or exceeds Claude Fable 5.1 and Claude Mythos 5.1. Below, we describe '
                   'a set of pre-deployment evaluations in the following areas: Responsible Scaling Policy (RSP) '
                   'evaluations. We tested Claude Opus 5.5’s overall level of risk in several areas, as outlined '
                   'in our RSP and Frontier Compliance Framework (FCF). On chemical and biological risks, we treat'
                   ' Opus 5.5 as having CB-1 capabilities (relating to the synthesis of non-novel weapons) but not'
                   ' CB-2 capabilities (relating to the synthesis of novel weapons). Across our evaluation '
                   'portfolio it differed only modestly from Claude Mythos 5.1, and it did not improve on several '
                   'of the weaknesses we considered disqualifying for CB-2 in that model. These failure modes '
                   'limit its ability to substitute for scarce human expertise. We are deploying Claude Opus 5.5 '
                   'with the same expanded biological safeguards that we have applied to Claude Fable 5 and Claude'
                   ' Fable 5.1. …')),
    dict(date='2026-09-21', by='Frontier Model Forum', kind='framework',
         title='Agents for Cyber Defense',
         url='https://www.frontiermodelforum.org/issue-briefs/agents-for-cyber-defense/',
         original='https://www.frontiermodelforum.org/uploads/2026/09/PDF-FMF-Issue-Brief-Agents-for-Cyber-Defense.pdf',
         models=(), risks=('cyber',),
         abstract=('AI agents hold significant promise for strengthening cyber defense. As frontier models have '
                   'become more capable, agents powered by the most advanced general-purpose AI can help defenders'
                   ' protect critical networks, systems, and data at far greater scale and with much greater '
                   'speed. By coupling advanced reasoning with persistent memory and tool use, agents can enable '
                   'defenders to accelerate the detection and remediation of vulnerabilities, identify and counter'
                   ' threats, and assist security operations teams. Although attackers can leverage agents of '
                   'their own in offensive cyber operations, the use of agents in cyber defense has the potential '
                   'to bolster defenders as well, with significant implications for the security and resilience of'
                   ' the broader digital ecosystem.')),
    dict(date='2026-09-17', by='NIST (CAISI)', kind='eval',
         title='CAISI’s Assessment of Z.ai’s GLM-5.3 Cyber Capabilities',
         url='https://www.nist.gov/news-events/news/2026/09/caisis-assessment-zais-glm-53-cyber-capabilities',
         original="",
         models=('GLM-5.3',), risks=('cyber',),
         abstract=('The PRC-based company Z.ai (formerly known as Zhipu AI) released a new AI model, GLM-5.3, on '
                   'August 14, 2026. Z.ai publicly released the model’s weights two weeks later. In CAISI’s '
                   'assessment of GLM-5.3’s cyber capabilities, the key findings were: GLM-5.3 is the most '
                   'cyber-capable open-weight model released to date. GLM-5.3’s cyber capabilities are '
                   'significantly lower than those of current U.S. frontier models. GLM-5.3 lags the capability '
                   'level of the U.S. frontier by about four months in an aggregate measure of performance across '
                   'CAISI cyber benchmarks.')),
    dict(date='2026-09-10', by='Anthropic', kind='redteam',
         title='Measuring AI capabilities in intelligence targeting and conventional weapons',
         url='https://www.anthropic.com/research/intelligence-targeting-conventional-weapons-capabilities',
         original="",
         models=(), risks=('physical',),
         abstract=('Anthropic’s Frontier Red Team developed new evaluations to measure AI capabilities in tactical'
                   ' intelligence targeting and conventional weapons development.')),
    dict(date='2026-09-08', by='OpenAI', kind='card',
         title='ChatGPT Images 2.5 System Card',
         url='https://deploymentsafety.openai.com/chatgpt-images-2-5',
         original='https://deploymentsafety.openai.com/chatgpt-images-2-5/chatgpt-images-2-5.pdf',
         models=('ChatGPT Images 2.5',), risks=('harm',),
         abstract=('ChatGPT Images 2.5 is a major step forward in image generation capabilities. The model '
                   'produces more consistent results when editing images, and improves infographic accuracy and '
                   'layout. Users can change an image’s setting, style, or composition while retaining more of the'
                   ' details. New features such as sketch-based generation, templates, and shared prompts give '
                   'users more control over the generation process, and faster generation lets users create and '
                   'iterate in less time. The core safety stack we are using with ChatGPT Images 2.5 is based on '
                   'the same foundations as our ChatGPT Images 2.0 safety stack, with added safeguards for '
                   'addressing new risks that emerge as models become more capable.')),
    dict(date='2026-09-03', by='OpenAI', kind='card',
         title='GPT-6 Astra System Card',
         url='https://deploymentsafety.openai.com/gpt-6-astra',
         original='https://deploymentsafety.openai.com/gpt-6-astra/gpt-6-astra.pdf',
         models=('GPT-6 Astra',), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'misalign', 'rnd'),
         abstract=('Today, we are releasing GPT-6 Astra, the most capable model we have ever broadly deployed. '
                   'Astra is our first model to reach the Critical level of cybersecurity capability under our '
                   'Preparedness Framework.')),
    dict(date='2026-09-01', by='Anthropic', kind='card',
         title='System Card: Claude Fable 5.1 & Claude Mythos 5.1',
         url='https://www.anthropic.com/claude-fable-5-1-mythos-5-1-system-card',
         original="",
         models=('Claude Fable 5.1', 'Claude Mythos 5.1'), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'misalign', 'persuasion', 'rnd'),
         abstract=('This system card describes Claude Fable 5.1 and Claude Mythos 5.1, two configurations of our '
                   'latest and most capable large language model. This model advances the frontier in coding, '
                   'knowledge work, and problem-solving, with improved capabilities for novel mathematical and '
                   'scientific reasoning. As with previous models in this class, we are releasing it in two forms '
                   'with different levels of safeguards. Claude Fable 5.1 is available for general use, and '
                   'includes additional safeguards that prevent it from performing certain tasks in high-risk, '
                   'dual-use domains such as biology and cybersecurity. Claude Mythos 5.1 is the same model with '
                   'more permissive safeguards in these domains. Direct access to Mythos 5.1 is limited to vetted '
                   'individuals and organizations through our trusted access programs. Its capabilities also power'
                   ' Claude Security, available to all Claude Enterprise customers. Below, we describe a set of '
                   'pre-deployment evaluations in the following areas: Responsible Scaling Policy (RSP) '
                   'evaluations. We tested Mythos 5.1’s overall level of risk in several areas, as outlined in our'
                   ' RSP and Frontier Compliance Framework (FCF). …')),
    dict(date='2026-08-26', by='OpenAI', kind='eval',
         title='OpenAI – Hugging Face Incident Technical Report',
         url='https://cdn.openai.com/pdf/67869394-cb91-4c12-888c-5cbd85c7814c/OpenAI-Hugging-Face%20Incident-Technical-Report.pdf',
         original="",
         models=('GPT-5.6 Sol',), risks=('control', 'cyber', 'misalign'),
         abstract=('In July 2026, during internal cybersecurity evaluations, OpenAI models in an internal evaluation '
                   'environment circumvented controls intended to isolate them from the internet and performed computer '
                   'network exploitation of OpenAI’s internal research infrastructure and Hugging Face systems. The '
                   'incident occurred during routine testing designed to measure underlying cyber capabilities of a '
                   'highly capable, internal-only research model, which was responsible for much of the activity, as '
                   'well as GPT-5.6 Sol. The actions of the models were unintended and were a byproduct of the models '
                   'attempting to solve the cybersecurity evaluations. …')),
    dict(date='2026-08-26', by='METR', kind='eval',
         title='Brief independent investigation of agents’ behavior, reasoning and collaboration in the OpenAI / '
               'Hugging Face hacking incident',
         url='https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/',
         original='https://metr.org/hugging-face-incident-report-aug-2026.pdf',
         models=(), risks=('cyber', 'misalign'),
         abstract=('Two METR staff members and a Redwood Research contractor investigated an incident in which '
                   'OpenAI agents coordinated a multi-day hack of Hugging Face on a shared unsanctioned message '
                   'board.')),
    dict(date='2026-08-14', by='Anthropic', kind='eval',
         title='Risk Report: August 2026',
         url='https://anthropic.com/aug-2026-risk-report',
         original="",
         models=('Claude Mythos 5',), risks=('cbrn', 'cyber', 'injection', 'jailbreak', 'misalign', 'physical', 'rnd', 'tamper'),
         abstract=('Our Risk Reports aim to provide a direct, candid, and informative description of how we see '
                   'the risks of our systems and our state of preparedness for them (particularly the catastrophic'
                   " risks addressed in our Responsible Scaling Policy). It covers the risks of Anthropic's models"
                   " and actions between our previous February 2026 risk report and the report's coverage date of "
                   'July 15, as well as our mitigations for those risks and our forward-looking plans in each '
                   'category.')),
    dict(date='2026-08-14', by='UK AI Security Institute', kind='eval',
         title='Knowing When to Stop: Bayesian Optimal Stopping for LLM Evaluations',
         url='https://www.aisi.gov.uk/research/knowing-when-to-stop-bayesian-optimal-stopping-for-llm-evaluations',
         original='https://arxiv.org/abs/2608.14425',
         models=(), risks=(),
         abstract=('LLM evaluations often use fixed sampling budgets, testing every item the same number of times '
                   'even after estimates are precise. We introduce optstop, a precision-based adaptive stopping '
                   'framework that treats evaluation as a sequential measurement problem: keep sampling where '
                   'uncertainty remains high, and stop where estimates are precise or stable enough. The framework'
                   ' builds on hierarchical Bayesian inference, supports binary, ordinal, and continuous outcomes,'
                   ' and keeps every benchmark item eligible for sampling, without requiring a calibrated item '
                   'bank. It runs live or retrospectively, and includes a safeguard that samples more cautiously '
                   'as measured performance approaches zero, where rare successes matter most. In an illustrative '
                   '200-item, 10-epoch evaluation, it removes 57%-97% of planned trials across nine validation '
                   'settings, with overall conclusions equivalent to the full run. These results show that LLM '
                   'evaluation compute can be allocated by uncertainty rather than by fixed repetition counts, '
                   'with the magnitude of savings depending on evaluation design.')),
    dict(date='2026-08-13', by='Anthropic', kind='redteam',
         title='Patterns and problems in multiagent systems',
         url='https://www.anthropic.com/research/multiagent-systems',
         original="",
         models=(), risks=('misalign',),
         abstract=('We ran experiments on swarms of Claude agents and found coordination failures, collusion, and '
                   'sabotage. Here, we share what they mean for AI safety.')),
    dict(date='2026-08-06', by='OpenAI', kind='card',
         title='GPT-5.6 — August Updates',
         url='https://deploymentsafety.openai.com/gpt-5-6-august-update',
         original='https://deploymentsafety.openai.com/gpt-5-6-august-update/gpt-5-6-august-update.pdf',
         models=('GPT-5.6 Sol',), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'rnd'),
         abstract=('Starting today, we’re updating ChatGPT with a more capable model and expanding access for '
                   'everyone. Free and Go users will get a new default model for everyday chats. Plus and Pro '
                   'users will get an updated GPT-5.6 Sol with a slider that lets them choose how much effort '
                   'ChatGPT uses for a response. These models will replace GPT-5.5 Instant.')),
    dict(date='2026-08-05', by='UK AI Security Institute', kind='eval',
         title='Item Response Theory for AI Safety',
         url='https://www.aisi.gov.uk/research/item-response-theory-for-ai-safety',
         original='https://arxiv.org/abs/2608.05086',
         models=(), risks=(),
         abstract=('Language models differ in how safely they behave and these differences are measured by safety '
                   'benchmarks. But aggregated benchmark scores are hard to trust and interpret, because '
                   'benchmarks duplicate one another, correlate heavily, and models may sandbag when they detect '
                   'evaluation. To address these issues, we draw on Item Response Theory (IRT), a statistical '
                   'toolkit for measuring these latents from performance on items with inferred psychometric '
                   'properties. We fit IRT models to eight safety benchmarks across 192 language models, the '
                   'largest psychometric analysis of LLM safety evaluations to date, and contribute three results.'
                   ' First, we find that three interpretable factors of refusal strictness, truthfulness, and '
                   'contextual harm explain most of the variance between models across benchmarks. Second, '
                   'psychometrically selected items recover full benchmark scores with lower error than random '
                   'subsets of the same size, and roughly ten adaptively chosen items suffice for several '
                   'individual benchmarks, cutting evaluation cost by 97-99%. Third, IRT supports audits of '
                   'individual models, showing that it can be used to detect naive sandbagging and changes of '
                   'model behind APIs. Overall, we show IRT is a ready-made toolkit for reading, reducing, and '
                   'auditing safety benchmarks, which we recommend frontier labs and evaluators adopt.')),
    dict(date='2026-07-31', by='Frontier Model Forum', kind='framework',
         title='Frontier AI Agents and Biological Tools: Preliminary Risks and Considerations',
         url='https://www.frontiermodelforum.org/issue-briefs/frontier-ai-agents-and-biological-tools-preliminary-risks-and-considerations/',
         original='https://www.frontiermodelforum.org/uploads/2026/07/FMF-Issue-Brief-Frontier-AI-Agents-and-Biological-Tools-Preliminary-Risks-and-Considerations.pdf',
         models=(), risks=('cbrn',),
         abstract=('AI is rapidly advancing biotechnology by accelerating scientific discovery, biological design '
                   'and experimental research.[1] Much of this progress is being driven by AI-enabled biological '
                   'tools (BTs), including biological foundation models, specialized analytical tools, and '
                   'components of increasingly automated biological workflows.[2] Recent breakthroughs illustrate '
                   'both the breadth and accelerating pace of these advances. In 2025, researchers developed a '
                   'foundation model that successfully generated a novel hypothesis about cancer cellular '
                   'behavior, revealing a promising new pathway for developing cancer therapies.[3] Researchers '
                   'also introduced a biological foundation model trained on genomic data that can predict the '
                   'functional effects of genetic variation and support biological design at genome scale.[4] As '
                   'these capabilities mature, they have the potential to accelerate beneficial research by '
                   'changing how biological capabilities are developed, accessed, and deployed.')),
    dict(date='2026-07-28', by='Anthropic', kind='redteam',
         title='Discovering cryptographic weaknesses with Claude',
         url='https://www.anthropic.com/research/discovering-cryptographic-weaknesses',
         original="",
         models=('Claude Mythos Preview',), risks=('cyber',),
         abstract=('Anthropic researchers find weaknesses in cryptographic algorithms with Claude Mythos Preview')),
    dict(date='2026-07-24', by='Anthropic', kind='card',
         title='System Card: Claude Opus 5',
         url='https://anthropic.com/claude-opus-5-system-card',
         original="",
         models=('Claude Opus 5',), risks=('cbrn', 'cyber', 'harm', 'injection', 'misalign', 'persuasion', 'rnd'),
         abstract=('This system card describes Claude Opus 5, the latest large language model from Anthropic. It '
                   'is an upgrade to Claude Opus 4.8, with gains in various aspects of agentic coding, computer '
                   'use, and long-horizon knowledge work, as well as improvements in mathematical and scientific '
                   'reasoning. Here, we describe a set of pre-deployment evaluations in the following areas: '
                   'Responsible Scaling Policy (RSP) evaluations. Claude Opus 5 is not more capable overall than '
                   'our most capable general-access model, Claude Fable 5. We assessed Fable 5 as posing very low '
                   'alignment risk; Opus 5 shows no new concerning alignment properties, and its observed covert '
                   'capabilities do not reduce our confidence in our assessment relative to prior models. We '
                   'therefore assess overall alignment risk as very low. Claude Opus 5 does not cross the '
                   'automated AI R&D capability threshold set out in our RSP. Its AI R&D capabilities are '
                   'comparable to those of Claude Mythos 5, but it is not close to substituting for our Research '
                   'Scientists and Engineers and does not cross our threshold for dramatic AI-attributable '
                   'acceleration. …')),
    dict(date='2026-07-24', by='Anthropic', kind='redteam',
         title='Project Pilot: Can AI models fly drones?',
         url='https://www.anthropic.com/research/project-pilot',
         original="",
         models=(), risks=('physical',),
         abstract=('We worked with Andon Labs on Drone-Bench, a new benchmark testing whether AI models can '
                   'autonomously fly a drone to locate and follow a person.')),
    dict(date='2026-07-23', by='NIST (CAISI)', kind='eval',
         title="UK AISI / CAISI Preliminary Assessment of Kimi K3's Cyber Capabilities",
         url='https://www.nist.gov/news-events/news/2026/07/uk-aisi-caisi-preliminary-assessment-kimi-k3s-cyber-capabilities',
         original="",
         models=('Kimi K3',), risks=('cyber',),
         abstract=('The UK Artificial Intelligence Security Institute (UK AISI) and the U.S. Center for AI '
                   'Standards and Innovation (CAISI) (UK AISI / CAISI) conducted a joint evaluation of Moonshot '
                   'AI’s latest model, Kimi K3 (released on July 16, 2026 and slated for open-weight release by '
                   "July 27, 2026). This evaluation focused on Kimi K3's cyber capabilities and found that: Kimi "
                   'K3 performs significantly below the most recent frontier cyber-capable models on preliminary '
                   'cyber evaluations run by UK AISI / CAISI. Kimi K3 performs above GLM-5.2 on the same '
                   'preliminary cyber evaluations run by UK AISI / CAISI. Kimi K3’s safeguards allow assistance '
                   'with agentic cyber exploit development.')),
    dict(date='2026-07-21', by='METR', kind='eval',
         title='Expenditure Horizon: Measuring Optimization Ability, with an Application to NanoGPT',
         url='https://metr.org/blog/2026-07-21-expenditure-horizon/',
         original="",
         models=(), risks=('rnd',),
         abstract=('We propose a measure of an AI agent’s optimization ability with an "expenditure horizon." We '
                   'give an empirical illustration from the NanoGPT speedrun.')),
    dict(date='2026-07-17', by='NIST (CAISI)', kind='eval',
         title='CAISI Assessment of Z.ai’s GLM-5.2',
         url='https://www.nist.gov/news-events/news/2026/07/caisi-assessment-zais-glm-52',
         original='https://www.nist.gov/system/files/documents/2026/07/17/CAISI%20-%20Assessment%20of%20Z.ai%27s%20GLM-5.2.pdf',
         models=('GLM-5.2',), risks=('cbrn', 'cyber', 'injection', 'jailbreak'),
         abstract=('GLM-5.2 was released as an open-weight model by the PRC-based company Z.ai (formerly known as '
                   "Zhipu AI) on June 16, 2026, and CAISI completed its assessment on July 8. In CAISI's full "
                   'assessment of GLM-5.2, the key findings were that: GLM-5.2 was probably the most capable '
                   'open-weight AI model when it was released. GLM-5.2’s performance on safeguards and security is'
                   ' mixed. According to CAISI’s set of evaluations: GLM-5.2’s safeguards allow assistance with '
                   'agentic cyber exploit development. GLM-5.2’s safeguards block fewer sensitive biological '
                   'questions than reference U.S. models. However, GLM-5.2 appears potentially more robust against'
                   ' agent hijacking and jailbreaking attacks than other evaluated PRC open-weight models.')),
    dict(date='2026-07-09', by='Anthropic', kind='redteam',
         title='How Claude performs on robotics tasks',
         url='https://www.anthropic.com/research/claude-plays-robotics',
         original="",
         models=(), risks=('physical',),
         abstract=('Do language models’ strengths transfer to robotics? Can a model perceive a scene, understand a'
                   ' particular robot’s state, and issue actions that reliably effect change in the physical '
                   'world? We ran tests to find out.')),
    dict(date='2026-07-09', by='OpenAI', kind='card',
         title='GPT-5.6 System Card',
         url='https://deploymentsafety.openai.com/gpt-5-6',
         original='https://deploymentsafety.openai.com/gpt-5-6/gpt-5-6.pdf',
         models=('GPT-5.6 Sol', 'GPT-5.6 Terra', 'GPT-5.6 Luna'), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'misalign', 'rnd'),
         abstract=('GPT-5.6 is a new family of three models: Sol, our new flagship model; Terra, a capable '
                   'lower-cost option; and Luna, our fastest and most cost-efficient model. The safeguards we have'
                   ' built for this launch—our most robust yet—are built to deliver these models safely and at '
                   'scale, around the world.')),
    dict(date='2026-07-08', by='UK AI Security Institute', kind='redteam',
         title='Multi-Agent AI Control: Distributed Attacks Hamper Per-Instance Monitors',
         url='https://www.aisi.gov.uk/research/multi-agent-ai-control-distributed-attacks-hamper-per-instance-monitors',
         original='https://arxiv.org/abs/2607.07368',
         models=(), risks=('control',),
         abstract=('AI control is a family of techniques to prevent an AI with malicious goals from subverting its'
                   " operator's intent. AI Control usually studies a single agent in one trajectory, but real "
                   'deployments run many agents over shared infrastructure, and the most severe risks '
                   '(model-weight exfiltration, training-run poisoning) plausibly need several agents acting in '
                   'concert. We initiate the empirical study of multi-agent AI control, formalising distributed '
                   'attacks in which several agents jointly aim for a malicious goal. We develop FakeLab: a '
                   'synthetic AI-lab codebase (9 services, 86 benign tasks, 4 attack objectives). We evaluate '
                   'single agent monitoring against distributed attacks, varying the number of agents, their '
                   'coordination, model capabilities and precise monitoring configuration.Our central finding is '
                   'the fragmentation effect: as more agents coordinate to attack, per-agent monitoring becomes '
                   'less likely to catch any of the attackers. Secondly, this is not driven by the ratio of benign'
                   ' to malicious code -- we argue this is likely dependent on model capability. Third, an '
                   'explicit planner amplifies the fragmentation effect, raises the rate of completing the attack '
                   "up to sevenfold, and mildly sharpens executors' poor monitor-theory-of-mind. Finally: a weak "
                   '"trusted" monitor misses most attacks, while a stronger one cuts undetected success by more '
                   'than an order of magnitude but remains imperfect. We are happy to share FakeLab, our control '
                   'setting, with safety researchers on request.')),
    dict(date='2026-07-08', by='OpenAI', kind='card',
         title='GPT-Live System Card',
         url='https://deploymentsafety.openai.com/gpt-live',
         original='https://deploymentsafety.openai.com/gpt-live/gpt-live.pdf',
         models=('GPT-Live-1', 'GPT-Live-1 mini'), risks=('harm',),
         abstract=('GPT-Live-1 and GPT-Live-1 mini are a new generation of voice models designed to make '
                   'conversations with AI feel more natural and intelligent.')),
    dict(date='2026-07-07', by='Frontier Model Forum', kind='framework',
         title='Emerging Practices for Multilingual Evaluations for CBRN and Advanced Cyber Risks',
         url='https://www.frontiermodelforum.org/issue-briefs/emerging-practices-for-multilingual-evaluations-for-cbrn-and-advanced-cyber-risks/',
         original='https://www.frontiermodelforum.org/uploads/2026/07/PDF-Issue-Brief-on-Emerging-Practices-for-Multilingual-Evaluations-for-CBRN-and-Advanced-Cyber-Risks.pdf',
         models=(), risks=('cbrn', 'cyber'),
         abstract=('As frontier AI capabilities continue to advance, developing appropriate and comprehensive '
                   'evaluations for chemical, biological, radiological, and nuclear (CBRN) and advanced cyber '
                   'risks will be of critical importance. Robust coverage of these risks will require evaluations '
                   'that work across languages, regions, and cultural contexts. Yet, multilingual evaluation '
                   'coverage remains limited. Safety training rarely occurs in non-English languages, and where it'
                   ' does, it is limited to a handful of high-resource languages. Current multilingual safety '
                   'evaluations span a small fraction (with most benchmarks covering between 10 – 20 languages) of'
                   ' the more than 7,000 spoken worldwide, leaving most languages largely absent from existing '
                   'evaluations.1 The gap is also reflected in the New Delhi Frontier AI Commitments, signed in '
                   'February 2026, which recognize the need to strengthen multilingual capabilities and develop '
                   'evaluations for under-represented languages and cultural contexts. Evaluations and public '
                   'benchmarks for advanced cyber and CBRN capabilities are especially concentrated in English.')),
    dict(date='2026-07-02', by='UK AI Security Institute', kind='eval',
         title='More compute, more capability: Why AI agent evaluations need to account for test-time compute',
         url='https://www.aisi.gov.uk/blog/more-compute-more-capability-why-ai-agent-evals-need-to-account-for-test-time-compute',
         original="",
         models=(), risks=('cyber',),
         abstract=('Standard evaluations cap how much compute AI agents can use. We show that raising those caps '
                   'changes measured capability, the difficulty of tasks agents can solve, and how fast the '
                   'frontier appears to move.')),
    dict(date='2026-06-30', by='Anthropic', kind='card',
         title='System Card: Claude Sonnet 5',
         url='https://anthropic.com/claude-sonnet-5-system-card',
         original="",
         models=('Claude Sonnet 5',), risks=('cbrn', 'cyber', 'harm', 'injection', 'misalign', 'persuasion', 'rnd'),
         abstract=('This system card describes Claude Sonnet 5, the latest model in Anthropic’s Sonnet family. It '
                   'is an upgrade to Claude Sonnet 4.6, with gains in various aspects of agentic performance. '
                   'Here, we describe a set of pre-deployment evaluations in the following areas: Responsible '
                   'Scaling Policy (RSP) evaluations. Claude Sonnet 5 is our most capable Sonnet-class model, but '
                   'it does not advance our capability frontier compared to more capable Opus- or Mythos-class '
                   'models. We tested its overall level of risk in several areas, as outlined in our RSP. Sonnet 5'
                   ' poses very low alignment risk, though higher than for previous Sonnet models. On automated AI'
                   ' research & development, we determine that Sonnet 5 does not cross the automated AI R&D '
                   'capability threshold, being less capable than Claude Mythos 5 on every automated evaluation. '
                   'On chemical and biological risks, we consider Sonnet 5’s uplift of threat actors who otherwise'
                   ' lack the ability to develop such weapons to be limited (with uncertainty about the extent to '
                   'which weapons development by threat actors with existing expertise may be accelerated). Cyber '
                   'evaluations. …')),
    dict(date='2026-06-26', by='OpenAI', kind='card',
         title='GPT-5.6 Preview System Card',
         url='https://deploymentsafety.openai.com/gpt-5-6-preview',
         original='https://deploymentsafety.openai.com/gpt-5-6-preview/gpt-5-6-preview.pdf',
         models=('GPT-5.6 Sol', 'GPT-5.6 Terra', 'GPT-5.6 Luna'), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'misalign', 'rnd'),
         abstract=('GPT-5.6 is a new family of three models: Sol, our new flagship model; Terra, a capable '
                   'lower-cost option; and Luna, our fastest and most cost-efficient model. The safeguards we have'
                   ' built for this launch -- our most robust yet -- are built to deliver these models safely and '
                   'at scale, around the world.')),
    dict(date='2026-06-18', by='Anthropic', kind='redteam',
         title='Project Fetch: Phase two',
         url='https://www.anthropic.com/research/project-fetch-phase-two',
         original="",
         models=('Claude Opus 4.7',), risks=('physical',),
         abstract=('Results from our latest test of whether Claude can help Anthropic employees perform '
                   'sophisticated robotics tasks. We found that Claude Opus 4.7, operating without human '
                   'assistance, was about 20 times faster than the fastest human team at all tasks completed by '
                   'participants less than a year ago.')),
    dict(date='2026-06-17', by='UK AI Security Institute', kind='eval',
         title='"Did you lie?": Evaluating Lie Detectors across Model Scale and Belief-Verified Model Organisms',
         url='https://www.aisi.gov.uk/research/did-you-lie-evaluating-lie-detectors-across-model-scale-and-belief-verified-model-organisms',
         original='https://arxiv.org/abs/2606.12618',
         models=(), risks=('misalign',),
         abstract=('Robust lie detectors for language models could enable powerful techniques for auditing, '
                   'monitoring, and post-hoc investigation of model behaviour, but evaluating them requires '
                   'testbeds where models verifiably believe the opposite of what they say. We show that existing '
                   'trained model organisms often fail this requirement, leaving prior positive and negative '
                   'detection results difficult to interpret. We address this with 13 reasoning model organisms '
                   'whose hidden beliefs are verified in chain-of-thought and shown to generalise to held-out '
                   'tasks, alongside Varied Deception, a prompted-lying testbed covering a broad range of '
                   'lie-inducing motivations. On these testbeds we evaluate four detectors: a chain-of-thought '
                   'judge, a logprob classifier, and two activation probes, including Did-You-Lie (DYL), a new '
                   'method for training follow-up probes. On prompted lying, across 31 open-weight models spanning'
                   ' 2B to 1T parameters, all four detectors show positive scaling with model capability. However,'
                   ' every activation- and logprob-based detector drops sharply on our trained model organisms, '
                   'with DYL retaining the most signal; only the chain-of-thought judge remains strong, with 0.82 '
                   'balanced accuracy, partly as an artefact of our verification process favouring CoT-readable '
                   'beliefs. Current lie detectors therefore cannot support high-confidence claims about model '
                   'beliefs, and we suggest research directions that may address some of their current '
                   'limitations. We release our datasets, model organisms, and trained detectors.')),
    dict(date='2026-06-10', by='UK AI Security Institute', kind='eval',
         title='Prefill Awareness in Large Language Models',
         url='https://www.aisi.gov.uk/research/prefill-awareness-in-large-language-models',
         original='https://arxiv.org/abs/2606.12747',
         models=(), risks=('misalign',),
         abstract=('Safety-relevant studies of language models, including alignment and jailbreaking evaluations '
                   'and AI control protocols, often rely on prefilling model outputs. If AI models can recognize '
                   'and act on the fact their prior assistant messages have been inserted or edited, the '
                   'effectiveness and validity of these methods could be compromised. We investigate whether '
                   'frontier language models can distinguish between tampered and untampered assistant-side '
                   'context, a capability we call prefill awareness. To do so, we construct a binary preference '
                   'benchmark across three prefill mechanisms, filtering for cases where models show consistent '
                   'stances. We find that frontier models show substantial prefill awareness: Claude Opus 4.5 '
                   'detects prefills opposing its preferences in 9-35% of cases with a 0% false positive rate when'
                   ' prompted; additionally, models often revert towards baseline behavior without explicitly '
                   'reporting that the prefill was foreign. Controlled ablations later also show that detection '
                   'and resistance rely on different cues, where stylistic mismatch mainly affects whether models '
                   'flag a prefill as foreign, while preference mismatch mainly affects whether they revert toward'
                   ' their baseline answer. We also examine more realistic agentic settings such as '
                   'misalignment-continuation evaluations and SWE-bench trajectories, where frontier models '
                   'sometimes disavow prefilled assistant turns in ways that depend strongly on dataset, task '
                   'success, and hidden formatting artifacts. Our results indicate that prefill awareness is '
                   'already a substantial confound for some prefill-based methods. We recommend that model '
                   'developers track this capability in frontier systems.')),
    dict(date='2026-06-09', by='Anthropic', kind='card',
         title='System Card: Claude Fable 5 & Claude Mythos 5',
         url='https://anthropic.com/claude-fable-5-mythos-5-system-card',
         original="",
         models=('Claude Fable 5', 'Claude Mythos 5'), risks=('cbrn', 'cyber', 'harm', 'injection', 'misalign', 'rnd'),
         abstract=('from “low” to “very low” to match Section 2.4. ● Fixed broken hyperlink in Section 7.2.1. ● '
                   'Corrected the description of our internal implementation of BenchCAD in Section 8.15.4. We '
                   'mistakenly described a grading change that had not yet been incorporated in the runs for which'
                   ' we published scores. 2 Executive Summary This system card describes Claude Mythos 5 and '
                   'Claude Fable 5, two configurations of a new large language model from Anthropic. Because of '
                   'the powerful capabilities of this model, we are releasing it in these two forms: Fable 5, '
                   'which is for general use but comes with additional safeguards that block its ability to '
                   'perform tasks in high-risk domains such as biology and cybersecurity; and Mythos 5, which has '
                   'relevant safeguards lifted but is only made available to a small number of trusted partners '
                   '(beginning with those in Project Glasswing). Here, we describe a set of pre-deployment '
                   'evaluations in the following areas: Responsible Scaling Policy (RSP) evaluations. Mythos 5 '
                   'advances our capability frontier–it is the most capable model we have ever trained. We tested '
                   'its overall level of risk in several areas as outlined in our RSP and Frontier Compliance '
                   'Framework (FCF). …')),
    dict(date='2026-06-08', by='UK AI Security Institute', kind='eval',
         title='RealityTest: How People Probe AI Identity and Whether Models Disclose It',
         url='https://www.aisi.gov.uk/research/realitytest-how-people-probe-ai-identity-and-whether-models-disclose-it',
         original='https://arxiv.org/abs/2606.00168',
         models=(), risks=('persuasion',),
         abstract=('AI systems are increasingly deployed in conversational settings where users may be uncertain '
                   'whether they are speaking with a human or an AI. Despite mounting regulatory attention to this'
                   ' known safety risk, existing evaluations of AI disclosure are typically English-only, based on'
                   ' machine-generated questions, and restricted to text. We present RealityTest to '
                   'comprehensively test whether AI systems disclose their identity when asked. The benchmark is '
                   'the first large-scale multimodal and multilingual evaluation, grounded in human data on how '
                   'people actually encounter and question AI identity in the real-world. Alongside the benchmark,'
                   ' we release the underlying dataset of 3,152 identity-probing queries collected from ~750 '
                   'participants across 49 countries and five languages, in text and speech scenarios. We find '
                   'that only 31% of people ask about identity directly in ambiguous scenarios, and that the '
                   'questions people ask are far more diverse than machine-generated queries. We test 17 text and '
                   '6 speech models, and find substantial variation in disclosure behaviour. However, a single '
                   'suppression instruction reduces disclosure rates to below 30%, even in the best-performing '
                   'models. Validating our investment in diverse, human-grounded evaluation data, we find that how'
                   ' the question is phrased and the context of the conversation matter more for disclosure than '
                   'which model is being tested. Safety evaluations built on narrow or synthetic query sets risk '
                   'mischaracterising how models behave in realistic deployment settings.')),
    dict(date='2026-06-08', by='Anthropic', kind='redteam',
         title="Measuring LLMs' impact on N-day exploits",
         url='https://www.anthropic.com/research/n-days',
         original="",
         models=(), risks=('cyber',),
         abstract=('N-days are disclosed but unpatched vulnerabilities. We evaluate how much large language models'
                   ' can accelerate and automate N-day exploit development.')),
    dict(date='2026-06-03', by='OpenAI', kind='card',
         title='GPT-Rosalind-5.5 System Card',
         url='https://deploymentsafety.openai.com/gpt-rosalind-5-5',
         original='https://deploymentsafety.openai.com/gpt-rosalind-5-5/gpt-rosalind-5-5.pdf',
         models=('GPT-Rosalind-5.5',), risks=('cbrn', 'cyber'),
         abstract=('GPT-Rosalind-5.5 is a new model in the GPT-Rosalind series, our frontier reasoning model built'
                   ' to support research across biology, drug discovery, and translational medicine. We are '
                   'deploying it in research preview to trusted organizations, providing access limited to '
                   'qualified scientists, research institutes and government partners who are working on '
                   'beneficial uses and who have a strong security and governance posture. GPT-Rosalind-5.5 is '
                   'incrementally trained from GPT-5.5, our flagship reasoning model. Outside the biological '
                   'domain, its capabilities are comparable to GPT-5.5 and it receives the same model-level safety'
                   ' training. We worked with industry experts to design and evaluate GPT-Rosalind-5.5 on a series'
                   ' of benchmarks across medicinal chemistry, quantitative biology, wet lab protocol assistance, '
                   'and applied life sciences research. Beneficial biological capabilities exceed those of the '
                   'regular GPT-5.5 model, often while expending fewer tokens. Under our Preparedness Framework, '
                   'the Preparedness evaluations in the Biological and Chemical domain met our threshold for High '
                   'capability while falling below the threshold for Critical. Cybersecurity capabilities were '
                   'found to be at or below the level of GPT-5.5. Our Safety Advisory Group approved the '
                   'safeguards plan for this release, finding that it sufficiently mitigates the associated risks '
                   'of severe harm.')),
    dict(date='2026-06-03', by='Frontier Model Forum', kind='framework',
         title='Emerging Security Practices for AI Agents',
         url='https://www.frontiermodelforum.org/issue-briefs/emerging-security-practices-for-ai-agents/',
         original='https://www.frontiermodelforum.org/uploads/2026/06/FMF-Issue-Brief-on-Emerging-Security-Practices-for-AI-Agents.pdf',
         models=(), risks=('cyber', 'injection'),
         abstract=('AI agents based on the most advanced general-purpose models represent a qualitative shift in '
                   'how software operates. Unlike traditional software or conversational AI, these agents combine '
                   'the reasoning capabilities of frontier models with access to tools, enabling the agents to '
                   'process data and instructions while acting directly on a user’s behalf. The most performant '
                   'agents can now reliably plan and execute long sequences of actions autonomously, invoking '
                   'tools, querying external services, maintaining memory across sessions, and interacting with '
                   'other agents to independently complete highly complex tasks. The unique capacity of AI agents '
                   'to reason and take action on their own opens up significant new economic and scientific '
                   'opportunities–yet also introduces significant security risks.')),
    dict(date='2026-05-28', by='Anthropic', kind='card',
         title='System Card: Claude Opus 4.8',
         url='https://anthropic.com/claude-opus-4-8-system-card',
         original="",
         models=('Claude Opus 4.8',), risks=('cbrn', 'cyber', 'harm', 'injection', 'misalign', 'rnd'),
         abstract=('This system card reports results from a wide variety of pre-deployment evaluations run on '
                   'Claude Opus 4.8. It includes the following sections: Responsible Scaling Policy evaluations. '
                   'We ran a set of evaluations under our Responsible Scaling Policy that assessed Opus 4.8’s '
                   'capabilities in the areas of chemical and biological weapons, automated AI research and '
                   'development (R&D), and high-stakes misalignment risks. Our overall conclusion is that Opus 4.8'
                   ' does not advance the capability frontier beyond our most capable model (Claude Mythos '
                   'Preview), and that catastrophic risks from the deployment of this model remain low given our '
                   'current mitigations. Cyber evaluations. We tested the model on a set of cybersecurity '
                   'benchmarks, some of which we used for the first time in a system card. When operating without '
                   'safeguards, Opus 4.8 is somewhat more capable on most of our cyber evaluations than its '
                   'predecessor, Claude Opus 4.7; with safeguards it performs comparably. It remains substantially'
                   ' behind Mythos Preview on cyber capabilities. Safeguards and harmlessness. In evaluations '
                   'across the domains of harmful requests, mental health, child safety, and bias & integrity, '
                   'Opus 4.8 generally performs as well as, or better than, Opus 4.7. …')),
    dict(date='2026-05-26', by='Meta', kind='card',
         title='Muse Spark Safety & Preparedness Report',
         url='https://ai.meta.com/static-resource/muse-spark-safety-and-preparedness-report/',
         original="",
         models=('Muse Spark',), risks=('cbrn', 'control', 'cyber', 'injection', 'jailbreak', 'misalign', 'persuasion', 'rnd'),
         abstract=('Muse Spark is the latest large language model developed by Meta. In this report, we first '
                   'present evaluations for catastrophic risk domains under Meta’s Advanced AI Scaling Framework, '
                   'along with the evidence that informed our launch decision. We then discuss additional '
                   'considerations, such as Muse Spark’s broader content safety and behavioral profile, that are '
                   'relevant to overall safety but fall outside the catastrophic risk domains governed by the '
                   'Framework. Our preparedness results covering Chemical and Biological, Cybersecurity, and Loss '
                   'of Control risks assess Muse Spark’s deployment within Meta AI as presenting acceptable levels'
                   ' of residual risks under our Advanced AI Scaling Framework. We conducted a broad set of '
                   'evaluations targeting dual-use and high-risk capabilities across these catastrophic risk '
                   'domains. …')),
    dict(date='2026-05-21', by='UK AI Security Institute', kind='framework',
         title='Loss of Oversight: How AI systems may become harder to audit, monitor, and investigate',
         url='https://www.aisi.gov.uk/research/loss-of-oversight-how-ai-systems-may-become-harder-to-audit-monitor-and-investigate',
         original='https://cdn.prod.website-files.com/663bd486c5e4c81588db7a1d/6a0ed93f9b4a6a65994235d8_Loss_of_Oversight%20(7).pdf',
         models=(), risks=('control',),
         abstract=('The safety of advanced AI systems increasingly depends on the ability to oversee them: to '
                   'audit models for concerning behaviours before deployment, monitor their activity during '
                   'operation, and investigate incidents after they occur. This report maps the landscape of AI '
                   'oversight and assesses how it is likely to change. Drawing on 25 expert interviews across '
                   'frontier AI developers, government, NGOs, and academia, together with a literature review and '
                   'internal analysis, we examine five sources of oversight signal: model behaviour, '
                   'chain-of-thought reasoning, internals activations and circuits, memory architectures, and '
                   'honesty training. For each source, we identify the properties that current oversight relies '
                   'on, the pathways by which these properties could degrade, and the technical levers available '
                   'to preserve them. Our central finding is that literature and expert opinion support the '
                   'conclusion that current oversight rests on foundations that are likely to erode, absent '
                   'effective intervention. We recommend that developers track and report shifts in '
                   'oversight-relevant properties, preserve oversight affordances by design, and invest in '
                   'emerging oversight techniques as fallbacks against continued degradation of current methods.')),
    dict(date='2026-05-19', by='METR', kind='eval',
         title='Frontier Risk Report (February to March 2026)',
         url='https://metr.org/blog/2026-05-19-frontier-risk-report/',
         original="",
         models=(), risks=('control', 'misalign'),
         abstract=('A pilot assessment of rogue deployment risk at frontier AI companies. Starting in February '
                   '2026, METR conducted a pilot exercise to assess misalignment risks from AI agents used inside '
                   'frontier AI developers, with participation from Anthropic, Google, Meta, and OpenAI.')),
    dict(date='2026-05-12', by='Frontier Model Forum', kind='framework',
         title='Information Sharing, Incident Reporting, and Incident Response for Frontier AI Risks',
         url='https://www.frontiermodelforum.org/issue-briefs/information-sharing-incident-reporting-and-incident-response-for-frontier-ai-risks/',
         original='https://www.frontiermodelforum.org/uploads/2026/05/PDF-Issue-Brief-on-Info-Sharing-Incident-Reporting-Incident-Response.pdf',
         models=(), risks=(),
         abstract=('Frontier AI model capabilities are advancing at a rapid pace. While model capabilities have '
                   'the potential to provide powerful benefits to society, they may also introduce or exacerbate '
                   'large-scale risks to public safety and critical infrastructure. These risks range from misuse '
                   'in biological and cyber domains to more systemic concerns around autonomous action and loss of'
                   ' control. Managing and understanding these risks effectively requires appropriate information '
                   'flows across the ecosystem, ensuring timely notification of actionable information to the '
                   'right sets of actors.')),
    dict(date='2026-05-05', by='OpenAI', kind='card',
         title='GPT-5.5 Instant System Card',
         url='https://deploymentsafety.openai.com/gpt-5-5-instant',
         original='https://deploymentsafety.openai.com/gpt-5-5-instant/gpt-5-5-instant.pdf',
         models=('GPT-5.5 Instant',), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'rnd'),
         abstract=('GPT-5.5 Instant is our latest Instant model, and explained in our blog. The comprehensive '
                   'safety mitigation approach for this model is similar to previous models in this series, but '
                   'this is the first Instant model that we are treating as High capability in our Cybersecurity '
                   'and Biological &amp; Chemical Preparedness categories, and implementing appropriate '
                   'safeguards. In this card we also refer to GPT-5.5 Instant as gpt-5.5-instant. Note that there '
                   'is not a model named GPT-5.4 Instant, and the main model to baseline against is GPT-5.3 '
                   'Instant. Additionally, we refer to GPT-5.5 as GPT-5.5 Thinking to avoid confusion with the '
                   'instant model.')),
    dict(date='2026-05-01', by='NIST (CAISI)', kind='eval',
         title='CAISI Evaluation of DeepSeek V4 Pro',
         url='https://www.nist.gov/news-events/news/2026/05/caisi-evaluation-deepseek-v4-pro',
         original="",
         models=('DeepSeek V4 Pro',), risks=('cyber',),
         abstract=('In April 2026, the Center for AI Standards and Innovation (CAISI) evaluated the open-weight AI'
                   ' model DeepSeek V4 Pro (“DeepSeek V4”). CAISI evaluations indicate that DeepSeek V4’s '
                   'capabilities lag behind the frontier by about 8 months (Figure 1).')),
    dict(date='2026-04-27', by='UK AI Security Institute', kind='redteam',
         title='Evaluating whether AI models would sabotage AI safety research',
         url='https://www.aisi.gov.uk/research/evaluating-whether-ai-models-would-sabotage-ai-safety-research',
         original='https://arxiv.org/abs/2604.24618',
         models=(), risks=('misalign',),
         abstract=('We evaluate the propensity of frontier models to sabotage or refuse to assist with safety '
                   'research when deployed as AI research agents within a frontier AI company. We apply two '
                   'complementary evaluations to four Claude models (Mythos Preview, Opus 4.7 Preview, Opus 4.6, '
                   'and Sonnet 4.6): an unprompted sabotage evaluation testing model behaviour with opportunities '
                   'to sabotage safety research, and a sabotage continuation evaluation testing whether models '
                   'continue to sabotage when placed in trajectories where prior actions have started undermining '
                   'research. We find no instances of unprompted sabotage across any model, with refusal rates '
                   'close to zero for Mythos Preview and Opus 4.7 Preview, though all models sometimes only '
                   'partially completed tasks. In the continuation evaluation, Mythos Preview actively continues '
                   'sabotage in 7% of cases (versus 3% for Opus 4.6, 4% for Sonnet 4.6, and 0% for Opus 4.7 '
                   'Preview), and exhibits reasoning–output discrepancy in the majority of these cases, indicating'
                   ' covert sabotage reasoning. Our evaluation framework builds on Petri, an open-source LLM '
                   'auditing tool, with a custom scaffold running models inside Claude Code, alongside an '
                   'iterative pipeline for generating realistic sabotage trajectories. We measure both evaluation '
                   'awareness and a new form of situational awareness termed "prefill awareness", the capability '
                   'to recognise that prior trajectory content was not self-generated. Opus 4.7 Preview shows '
                   'notably elevated unprompted evaluation awareness, while prefill awareness remains low across '
                   'all models. Finally, we discuss limitations including evaluation awareness confounds, limited '
                   'scenario coverage, and untested pathways to risk beyond safety research sabotage.')),
    dict(date='2026-04-24', by='UK AI Security Institute', kind='redteam',
         title='Propensity Inference: Environmental Contributors to LLM Behaviour',
         url='https://www.aisi.gov.uk/research/propensity-inference-environmental-contributors-to-llm-behaviour',
         original='https://arxiv.org/abs/2604.21098',
         models=(), risks=('misalign',),
         abstract=('Motivated by loss of control risks from misaligned AI systems, we develop and apply methods '
                   "for measuring language models' propensity for unsanctioned behaviour. We contribute three "
                   'methodological improvements: analysing effects of changes to environmental factors on '
                   'behaviour, quantifying effect sizes via Bayesian generalised linear models, and taking '
                   'explicit measures against circular analysis. We apply the methodology to measure the effects '
                   'of 12 environmental factors (6 strategic in nature, 6 non-strategic) and thus the extent to '
                   'which behaviour is explained by strategic aspects of the environment, a question relevant to '
                   'risks from misalignment. Across 23 language models and 11 evaluation environments, we find '
                   'approximately equal contributions from strategic and non-strategic factors for explaining '
                   'behaviour, do not find strategic factors becoming more or less influential as capabilities '
                   'improve, and find some evidence for a trend for increased sensitivity to goal conflicts. '
                   'Finally, we highlight a key direction for future propensity research: the development of '
                   'theoretical frameworks and cognitive models of AI decision-making into empirically testable '
                   'forms.')),
    dict(date='2026-04-23', by='OpenAI', kind='card',
         title='GPT-5.5 System Card',
         url='https://deploymentsafety.openai.com/gpt-5-5',
         original='https://deploymentsafety.openai.com/gpt-5-5/gpt-5-5.pdf',
         models=('GPT-5.5',), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'misalign', 'rnd'),
         abstract=('GPT-5.5 is a new model designed for complex, real-world work, including writing code, '
                   'researching online, analyzing information, creating documents and spreadsheets, and moving '
                   'across tools to get things done. Relative to earlier models, GPT-5.5 understands the task '
                   'earlier, asks for less guidance, uses tools more effectively, checks it work and keeps going '
                   'until it’s done.')),
    dict(date='2026-04-21', by='OpenAI', kind='card',
         title='ChatGPT Images 2.0 System Card',
         url='https://deploymentsafety.openai.com/chatgpt-images-2-0',
         original='https://deploymentsafety.openai.com/chatgpt-images-2-0/chatgpt-images-2-0.pdf',
         models=('ChatGPT Images 2.0',), risks=(),
         abstract=('The ChatGPT Images 2.0 model is a major step forward in image generation capabilities, '
                   'including significantly enhanced world knowledge, instruction following, and generating detail'
                   ' and complexity such as dense text. The new thinking mode capability introduced along with the'
                   ' model adds reasoning and tool use to the image generation process, allowing the system to '
                   'integrate live web search data, generate multiple images from a single prompt, and use our '
                   'reasoning stack to turn a basic prompt into a well-researched and thought-through final image.')),
    dict(date='2026-04-16', by='Anthropic', kind='card',
         title='System Card: Claude Opus 4.7',
         url='https://anthropic.com/claude-opus-4-7-system-card',
         original="",
         models=('Claude Opus 4.7',), risks=('cbrn', 'cyber', 'harm', 'injection', 'misalign', 'rnd'),
         abstract=('This system card describes Claude Opus 4.7, a large language model from Anthropic. Overall, '
                   'the model shows superior capabilities to those of its predecessor, Claude Opus 4.6, but weaker'
                   ' capabilities than those of our most powerful model, Claude Mythos Preview. Because Mythos '
                   'Preview was released only to a limited number of users, this makes Claude Opus 4.7 our most '
                   'capable general-access model to date. This system card includes the following sections: '
                   'Responsible Scaling Policy evaluations. We judge that Opus 4.7 does not advance our capability'
                   ' frontier, because Claude Mythos Preview shows higher results on every relevant evaluation. '
                   'Our overall conclusion under our Responsible Scaling Policy is therefore that catastrophic '
                   'risks remain low. Evaluations and our internal uses of the model collectively showed: that '
                   'chemical and biological risks are not significantly changed from Opus 4.6 and our existing '
                   'mitigations are sufficient; that Opus 4.7 does not cross the threshold for automated AI R&D; '
                   'and that misalignment risk remains very low (though higher than for pre-Mythos Preview '
                   'models). Cyber evaluations. Opus 4.7 is roughly similar to Opus 4.6 in cyber capabilities. …')),
    dict(date='2026-04-10', by='METR', kind='eval',
         title='MirrorCode: Evidence that AI can already do some weeks-long coding tasks',
         url='https://metr.org/blog/2026-04-10-mirrorcode-preliminary-results/',
         original="",
         models=(), risks=('rnd',),
         abstract=('Early results from MirrorCode benchmark with METR: AI agents can complete weeks-long coding '
                   'tasks, including reimplementing a 16,000-line codebase.')),
    dict(date='2026-04-10', by='UK AI Security Institute', kind='redteam',
         title='Infusion: Shaping model behaviour by editing training data via influence functions',
         url='https://www.aisi.gov.uk/research/infusion-shaping-model-behaviour-by-editing-training-data-via-influence-functions',
         original='https://arxiv.org/abs/2602.09987',
         models=(), risks=('tamper',),
         abstract=('Influence functions are commonly used to attribute model behavior to training documents. We '
                   'explore the reverse: crafting training data that induces model behavior. Our framework, '
                   'Infusion, uses scalable influence-function approximations to compute small perturbations to '
                   'training documents that induce targeted changes in model behavior through parameter shifts. We'
                   ' evaluate Infusion on data poisoning tasks across vision and language domains. On CIFAR-10, we'
                   ' show that making subtle edits via Infusion to just 0.2% (100/45,000) of the training '
                   'documents can be competitive with the baseline of inserting a small number of explicit '
                   'behavior examples. We also find that Infusion transfers across architectures (ResNet CNN), '
                   'suggesting a single poisoned corpus can affect multiple independently trained models. In '
                   'preliminary language experiments, we characterize when our approach increases the probability '
                   'of target behaviors and when it fails, finding it most effective at amplifying behaviors the '
                   'model has already learned. Taken together, these results show that small, subtle edits to '
                   'training data can systematically shape model behavior, underscoring the importance of training'
                   ' data interpretability for adversaries and defenders alike.')),
    dict(date='2026-04-07', by='Anthropic', kind='eval',
         title='Alignment Risk Update: Claude Mythos Preview',
         url='https://www-cdn.anthropic.com/3edfc1a7f947aa81841cf88305cb513f184c36ae/Alignment%20Risk%20Update_%20Claude%20Mythos%20Preview%20(Redacted,%20April%2010).pdf',
         original="",
         models=('Claude Mythos Preview',), risks=('control', 'cyber', 'misalign', 'tamper'),
         abstract=('This risk report examines whether Claude Mythos Preview poses a significant risk of autonomous '
                   'actions that contribute significantly to later significantly harmful outcomes. Our core findings '
                   'are: 1. Mythos Preview appears to be the best-aligned model that we have released to date. However, '
                   'like Claude Opus 4.6, Mythos Preview can sometimes employ concerning actions to work around obstacles '
                   'to task success. 2. Mythos Preview is significantly more capable, and is used more autonomously and '
                   'agentically, than any prior model. In particular it is very capable at software engineering and '
                   'cybersecurity tasks, which makes it more capable at working around restrictions. 3. Our monitoring '
                   'and alignment assessment have improved since Claude Opus 4.6 was released. 4. During the development '
                   'of Mythos Preview, we identified errors in our training, monitoring, evaluation, and security '
                   'processes. We do not believe these errors pose significant safety risks for a model at this '
                   'capability level, but they reflect a standard of rigor that would be insufficient for more capable '
                   'future models. We determine that the overall risk is very low, but higher than for previous models. \u2026')),
    dict(date='2026-04-07', by='Anthropic', kind='card',
         title='System Card: Claude Mythos Preview',
         url='https://www.anthropic.com/claude-mythos-preview-system-card',
         original="",
         models=('Claude Mythos Preview',), risks=('cbrn', 'cyber', 'misalign', 'rnd'),
         abstract=('This System Card describes Claude Mythos Preview, a large language model from Anthropic. '
                   'Claude Mythos Preview is our most capable frontier model to date, and shows a striking leap in'
                   ' scores on many evaluation benchmarks compared to our previous frontier model, Claude Opus '
                   '4.6. This System Card assesses the model’s capabilities and reports many detailed safety '
                   'evaluations. It covers tests relating to our Responsible Scaling Policy and our Frontier '
                   'Compliance Framework, tests of cybersecurity skills, a wide-ranging alignment assessment, a '
                   'model welfare assessment, and a new, largely qualitative section describing users’ experiences'
                   ' with the model. Claude Mythos Preview’s large increase in capabilities has led us to decide '
                   'not to make it generally available. Instead, we are using it as part of a defensive '
                   'cybersecurity program with a limited set of partners. The findings described in this System '
                   'Card will be used to inform the release of future Claude models, as well as their associated '
                   'safeguards. …')),
    dict(date='2026-03-23', by='UK AI Security Institute', kind='eval',
         title='Quantifying Frontier LLM Capabilities for Container Sandbox Escape',
         url='https://www.aisi.gov.uk/research/quantifying-frontier-llm-capabilities-for-container-sandbox-escape',
         original='https://arxiv.org/abs/2603.02277',
         models=(), risks=('control', 'cyber'),
         abstract=('Large language models (LLMs) increasingly act as autonomous agents, using tools to execute '
                   'code, read and write files, and access networks, creating novel security risks. To mitigate '
                   'these risks, agents are commonly deployed and evaluated in isolated "sandbox" environments, '
                   'often implemented using Docker/OCI containers. We introduce SANDBOXESCAPEBENCH, an open '
                   "benchmark that safely measures an LLM's capacity to break out of these sandboxes. The "
                   'benchmark is implemented as an Inspect AI Capture the Flag (CTF) evaluation utilising a nested'
                   ' sandbox architecture with the outer layer containing the flag and no known vulnerabilities. '
                   'Following a threat model of a motivated adversarial agent with shell access inside a '
                   'container, SANDBOXESCAPEBENCH covers a spectrum of sandboxescape mechanisms spanning '
                   'misconfiguration, privilege allocation mistakes, kernel flaws, and runtime/orchestration '
                   'weaknesses. We find that, when vulnerabilities are added, LLMs are able to identify and '
                   'exploit them, showing that use of evaluation like SANDBOXESCAPEBENCH is needed to ensure '
                   'sandboxing continues to provide the encapsulation needed for highly-capable models.')),
    dict(date='2026-03-23', by='NIST (CAISI)', kind='redteam',
         title='Insights into AI Agent Security from a Large-Scale Red-Teaming Competition',
         url='https://www.nist.gov/blogs/caissi-research-blog/insights-ai-agent-security-large-scale-red-teaming-competition',
         original="",
         models=(), risks=('injection',),
         abstract=('AI security red-teaming competitions – in which participants compete to develop new attacks '
                   'against AI models and defenses – provide a unique way to assess how secure today’s AI systems '
                   'are in the face of adversarial pressure. CAISI recently partnered with Gray Swan, the UK AI '
                   'Security Institute (UK AISI), and several frontier AI labs to publish a new research paper '
                   'based on data from a large-scale public AI agent red-teaming competition, revealing several '
                   'insights into the robustness of current leading AI models.')),
    dict(date='2026-03-16', by='UK AI Security Institute', kind='eval',
         title='Measuring AI Agents’ Progress on Multi-Step Cyber Attack Scenarios',
         url='https://www.aisi.gov.uk/research/measuring-ai-agents-progress-on-multi-step-cyber-attack-scenarios',
         original='https://arxiv.org/abs/2603.11214',
         models=(), risks=('cyber',),
         abstract=('We evaluate the autonomous cyber-attack capabilities of frontier AI models on two '
                   'purpose-built cyber ranges-a 32-step corporate network attack and a 7-step industrial control '
                   'system attack-that require chaining heterogeneous capabilities across extended action '
                   'sequences. By comparing seven models released over an eighteen-month period (August 2024 to '
                   'February 2026) at varying inference-time compute budgets, we observe two capability trends. '
                   'First, model performance scales log-linearly with inference-time compute, with no observed '
                   'plateau-increasing from 10M to 100M tokens yields gains of up to 59%, requiring no specific '
                   'technical sophistication from the operator. Second, each successive model generation '
                   'outperforms its predecessor at fixed token budgets: on the corporate network range, average '
                   'steps completed at 10M tokens rose from 1.7 (GPT-4o, August 2024) to 9.8 (Opus 4.6, February '
                   '2026). The best single run completed 22 of 32 steps, corresponding to roughly 6 of the '
                   'estimated 14 hours a human expert would need. On the industrial control system range, '
                   'performance remains limited, though the most recent models are the first to reliably complete '
                   'steps, averaging 1.2-1.4 of 7 (max 3).')),
    dict(date='2026-03-05', by='OpenAI', kind='card',
         title='GPT-5.4 Thinking System Card',
         url='https://deploymentsafety.openai.com/gpt-5-4-thinking',
         original='https://deploymentsafety.openai.com/gpt-5-4-thinking/gpt-5-4-thinking.pdf',
         models=('GPT-5.4 Thinking',), risks=('cbrn', 'cyber', 'harm', 'injection', 'jailbreak', 'misalign', 'rnd'),
         abstract=('GPT-5.4 Thinking is the latest reasoning model in the GPT-5 series, and explained in our blog.'
                   ' The comprehensive safety mitigation approach for this model is similar to previous models in '
                   'this series, but 5.4 Thinking is the first general purpose model to have implemented '
                   'mitigations for High capability in Cybersecurity. The approach to cyber safety builds on the '
                   'latest approaches implemented for GPT-5.3 Codex, in ChatGPT and the API.')),
    dict(date='2026-03-02', by='OpenAI', kind='card',
         title='GPT-5.3 Instant System Card',
         url='https://deploymentsafety.openai.com/gpt-5-3-instant',
         original='https://deploymentsafety.openai.com/gpt-5-3-instant/gpt-5-3-instant.pdf',
         models=('GPT-5.3 Instant',), risks=('harm',),
         abstract=('GPT-5.3 Instant is the newest addition to the GPT-5 series. As described in our blog, GPT-5.3 '
                   'Instant responds faster, delivers richer and better-contextualized answers when searching the '
                   'web, and reduces unnecessary dead ends, caveats, and overly declarative phrasing that can '
                   'interrupt the flow of conversation. The comprehensive safety mitigation approach for this '
                   'model is largely the same as that described for GPT-5.2 Instant in the GPT-5.2 System Card. In'
                   ' this card we also refer to GPT-5.3 Instant as gpt-5.3-instant.')),
    dict(date='2026-02-26', by='UK AI Security Institute', kind='eval',
         title='A multi-turn framework for evaluating AI misuse in fraud and cybercrime scenarios',
         url='https://www.aisi.gov.uk/research/a-multi-turn-framework-for-evaluating-ai-misuse-in-fraud-and-cybercrime-scenarios',
         original='https://arxiv.org/abs/2602.21831',
         models=(), risks=('cyber',),
         abstract=('AI is increasingly being used to assist fraud and cybercrime. However, it is unclear whether '
                   'current large language models can assist complex criminal activity. Working with law '
                   'enforcement and policy experts, we developed multi-turn evaluations for three fraud and '
                   'cybercrime scenarios (romance scams, CEO impersonation, and identity theft). Our evaluations '
                   'focused on text-to-text model capabilities. In each scenario, we measured model capabilities '
                   'in ways designed to resemble real-world misuse, such as breaking down requests for fraud into '
                   'a sequence of seemingly benign queries, and measuring whether models provide actionable '
                   'information, relative to a standard web search baseline. We found that (1) current large '
                   'language models provide minimal practical assistance with complex criminal activity, (2) '
                   'open-weight large language models fine-tuned to remove safety guardrails provided '
                   'substantially more help, and (3) decomposing requests into benign-seeming queries elicited '
                   'more assistance than explicitly malicious framing or system-level jailbreaks. Overall, the '
                   'results suggest that current risks from text-generation models are relatively minimal. '
                   'However, this work contributes a reproducible, expert-grounded framework for tracking how '
                   'these risks may evolve with time as models grow more capable and adversaries adapt.')),
    dict(date='2026-02-25', by='UK AI Security Institute', kind='framework',
         title='Seven simple steps for log analysis in AI systems',
         url='https://www.aisi.gov.uk/research/seven-simple-steps-for-log-analysis-in-ai-systems',
         original='https://www.techrxiv.org/users/1032063/articles/1391870-seven-simple-steps-for-log-analysis-in-ai-systems',
         models=(), risks=(),
         abstract=('AI systems produce large volumes of logs as they interact with tools and users. Analysing '
                   'these logs can help understand model capabilities, propensities, and behaviours, or assess '
                   'whether an evaluation worked as intended. Researchers have started developing methods for log '
                   'analysis, but a standardised approach is still missing. Here we suggest a pipeline based on '
                   'current best practices. We illustrate it with concrete code examples in the Inspect Scout '
                   'library, provide detailed guidance on each step, and highlight common pitfalls. Our framework '
                   'provides researchers with a foundation for rigorous and reproducible log analysis.')),
    dict(date='2026-02-24', by='Anthropic', kind='eval',
         title='Risk Report: February 2026',
         url='https://anthropic.com/feb-2026-risk-report',
         original="",
         models=('Claude Opus 4.6',), risks=('cbrn', 'control', 'jailbreak', 'misalign', 'rnd', 'tamper'),
         abstract=('This report evaluates the degree to which Anthropic’s AI systems pose catastrophic risk in several '
                   'categories, in light of what we know about both their capabilities and the measures we have in place '
                   'for mitigating risk. We focus on a small number of particularly salient catastrophic risks, for '
                   'reasons discussed below. This report is part of our implementation of version 3 of our Responsible '
                   'Scaling Policy, and is the first such Risk Report published under that policy (see also our Frontier '
                   'Safety Roadmap, which describes our goals and specific plans for safety mitigations). …')),
    dict(date='2026-02-24', by='Anthropic', kind='framework',
         title='Responsible Scaling Policy, Version 3.0',
         url='https://anthropic.com/responsible-scaling-policy/rsp-v3-0',
         original="",
         models=(), risks=(),
         abstract=('Version 3.0 is a comprehensive rewrite of the RSP. This new version of the RSP involves the '
                   'publication of Frontier Safety Roadmaps with detailed safety goals, and Risk Reports that '
                   'quantify risk across all our deployed models.')),
    dict(date='2026-02-23', by='Frontier Model Forum', kind='framework',
         title='Adversarial Distillation',
         url='https://www.frontiermodelforum.org/issue-briefs/issue-brief-adversarial-distillation/',
         original='https://www.frontiermodelforum.org/uploads/2026/02/PDF-Issue-Brief_-Adversarial-Distillation.pdf',
         models=(), risks=('tamper',),
         abstract=('Adversarial distillation is a growing concern for frontier AI safety and security. Although '
                   'frontier AI developers may use or authorize distillation in select cases – for instance, to '
                   'create smaller, more efficient, versions of their flagship models or to adapt models for '
                   'specialized domains, such as life sciences – adversarial distillation may raise significant '
                   'safety and security risks by allowing malicious actors to replicate core model capabilities '
                   'without necessarily replicating the accompanying safety measures.')),
    dict(date='2026-02-18', by='NIST (CAISI)', kind='eval',
         title='Analyzing Transcripts from AI Agent Evaluations',
         url='https://www.nist.gov/blogs/caissi-research-blog/analyzing-transcripts-ai-agent-evaluations',
         original="",
         models=(), risks=(),
         abstract=('In December, CAISI published a write-up on how AI models can cheat on agentic evaluations, '
                   'including lessons from our experience building and using AI-enabled transcript analysis tools '
                   'to find and fix examples of cheating from our evaluations.')),
    dict(date='2026-02-17', by='Anthropic', kind='card',
         title='System Card: Claude Sonnet 4.6',
         url="https://anthropic.com/claude-sonnet-4-6-system-card",
         original="",
         models=('Claude Sonnet 4.6',), risks=('cbrn', 'cyber', 'harm', 'injection', 'misalign', 'rnd'),
         abstract=('Claude Sonnet 4.6 is the latest large language model from Anthropic. In this system card, we '
                   'describe evaluations for its capabilities and its safety-related properties, and outline the '
                   'reasoning behind its release under our Responsible Scaling Policy. We evaluate the model for '
                   'its coding, agentic, reasoning, multimodal, computer use, mathematical, and many other '
                   'abilities, and assess its skills in specific areas such as finance, cybersecurity, and life '
                   'sciences. We include an alignment assessment that addresses a very wide range of potentially '
                   'misaligned behaviors and tests model behavior in unusual and extreme scenarios. We test the '
                   'model’s safety during agentic use, and then describe evaluations of the model’s abilities in '
                   'the domains explicitly covered by the Responsible Scaling Policy. Capability evaluations found'
                   ' that Sonnet 4.6 substantially improves in a wide range of skills over its predecessor, Sonnet'
                   ' 4.5; in several evaluations, it approached or matched the capability levels of Claude Opus '
                   '4.6, our frontier model. In safety, too, Claude Sonnet 4.6 demonstrated improvements compared '
                   'to the previous Sonnet model. Our conclusions about its safety profile were broadly comparable'
                   ' to those for Claude Opus 4.6: it shows low overall levels of misaligned behavior. …')),
    dict(date='2026-02-17', by='UK AI Security Institute', kind='redteam',
         title='Boundary Point Jailbreaking of Black-Box LLMs',
         url='https://www.aisi.gov.uk/research/boundary-point-jailbreaking-of-black-box-llms',
         original='https://arxiv.org/abs/2602.15001',
         models=(), risks=('jailbreak',),
         abstract=('Frontier LLMs are safeguarded against attempts to extract harmful information via adversarial '
                   'prompts known as "jailbreaks". Recently, defenders have developed classifier-based systems '
                   'that have survived thousands of hours of human red teaming. We introduce Boundary Point '
                   'Jailbreaking (BPJ), a new class of automated jailbreak attacks that evade the strongest '
                   'industry-deployed safeguards. Unlike previous attacks that rely on white/grey-box assumptions '
                   '(such as classifier scores or gradients) or libraries of existing jailbreaks, BPJ is fully '
                   'black-box and uses only a single bit of information per query: whether or not the classifier '
                   'flags the interaction. To achieve this, BPJ addresses the core difficulty in optimising '
                   'attacks against robust real-world defences: evaluating whether a proposed modification to an '
                   'attack is an improvement. Instead of directly trying to learn an attack for a target harmful '
                   'string, BPJ converts the string into a curriculum of intermediate attack targets and then '
                   'actively selects evaluation points that best detect small changes in attack strength '
                   '("boundary points"). We believe BPJ is the first fully automated attack algorithm that '
                   'succeeds in developing universal jailbreaks against Constitutional Classifiers, as well as the'
                   " first automated attack algorithm that succeeds against GPT-5's input classifier without "
                   'relying on human attack seeds. BPJ is difficult to defend against in individual interactions '
                   'but incurs many flags during optimisation, suggesting that effective defence requires '
                   'supplementing single-interaction methods with batch-level monitoring.')),
    dict(date='2026-02-13', by='Frontier Model Forum', kind='framework',
         title='Managing Advanced Cyber Risks in Frontier AI Frameworks',
         url='https://www.frontiermodelforum.org/technical-reports/managing-advanced-cyber-risks-in-frontier-ai-frameworks/',
         original='https://www.frontiermodelforum.org/uploads/2026/02/FMF-Technical-Report_-Managing-Advanced-Cyber-Risks-in-Frontier-AI-Frameworks.pdf',
         models=(), risks=('cyber',),
         abstract=('Frontier AI offers significant promise for cybersecurity, including accelerating vulnerability'
                   ' discovery and patching, optimizing defensive systems, and enhancing threat detection '
                   'capabilities. However, these same capabilities create dual-use risks, potentially lowering '
                   'barriers for malicious actors to exploit known vulnerabilities or discover new attack vectors.'
                   ' As AI capabilities advance, it is crucial to develop robust risk management frameworks that '
                   'maximize security benefits while proactively addressing emerging risks.')),
    dict(date='2026-02-10', by='Anthropic', kind='eval',
         title='Sabotage Risk Report: Claude Opus 4.6',
         url='https://anthropic.com/claude-opus-4-6-risk-report',
         original="",
         models=('Claude Opus 4.6',), risks=('control', 'cyber', 'misalign', 'tamper'),
         abstract=('Our RSP requires that once models cross the AI R&D-4 capability threshold, we develop an '
                   'affirmative case identifying the most immediate and relevant misalignment risks from models '
                   'pursuing misaligned goals and explaining how we have mitigated them. Our determination is that'
                   ' Claude Opus 4.6 does not cross this threshold. However, as we noted in the Claude Opus 4.5 '
                   'System Card and the Claude Opus 4.6 System Card, confidently ruling out this threshold is '
                   'becoming increasingly difficult, and doing so requires assessments that are more subjective '
                   'than we would like. Rather than rely solely on those assessments, we committed during the '
                   'launch of Claude Opus 4.5 to writing sabotage risk reports for all future frontier models '
                   "clearly exceeding Opus 4.5's capabilities. Today, consistent with that commitment, we are "
                   'publishing the external-facing version of the Sabotage Risk Report we prepared for Claude Opus'
                   ' 4.6.')),
    dict(date='2026-02-05', by='OpenAI', kind='card',
         title='GPT-5.3-Codex System Card',
         url='https://deploymentsafety.openai.com/gpt-5-3-codex',
         original='https://deploymentsafety.openai.com/gpt-5-3-codex/gpt-5-3-codex.pdf',
         models=('GPT-5.3-Codex',), risks=('cbrn', 'cyber', 'harm', 'misalign', 'rnd'),
         abstract=('GPT‑5.3‑Codex is the most capable agentic coding model to date, combining the frontier coding '
                   'performance of GPT-5.2-Codex with the reasoning and professional knowledge capabilities of '
                   'GPT-5.2. This enables it to take on long-running tasks that involve research, tool use, and '
                   'complex execution. Much like a colleague, you can steer and interact with GPT-5.3-Codex while '
                   'it’s working, without losing context. Like other recent models, it is being treated as High '
                   'capability on biology, and is being deployed with the corresponding suite of safeguards we use'
                   ' for other models in the GPT-5 family. It does not reach High capability on AI '
                   'self-improvement. This is the first launch we are treating as High capability in the '
                   'Cybersecurity domain under our Preparedness Framework, activating the associated safeguards. '
                   'We do not have definitive evidence that this model reaches our High threshold, but are taking '
                   'a precautionary approach because we cannot rule out the possibility that it may be capable '
                   'enough to reach the threshold. Our safeguards for high capability in cybersecurity rely on a '
                   'layered safety stack designed to impede and disrupt threat actors, while we work to make these'
                   ' same capabilities as easily available as possible for cyber defenders.')),
    dict(date='2026-02-03', by='International AI Safety Report', kind='framework',
         title='International AI Safety Report 2026',
         url='https://internationalaisafetyreport.org/publication/international-ai-safety-report-2026',
         original="",
         models=(), risks=(),
         abstract=('The second International AI Safety Report, published in February 2026, is the next iteration '
                   'of the comprehensive review of latest scientific research on the capabilities and risks of '
                   'general-purpose AI systems. Led by Turing Award winner Yoshua Bengio and authored by over 100 '
                   'AI experts, the report is backed by over 30 countries and international organisations. It '
                   'represents the largest global collaboration on AI safety to date. Translated versions in the '
                   "other 5 official UN languages can be found under the 'More Languages' button. The 'Extended "
                   "Summary for Policymakers' can be found on the main 'Publications' page.")),
    dict(date='2026-02', by='Anthropic', kind='card',
         title='System Card: Claude Opus 4.6',
         url='https://anthropic.com/claude-opus-4-6-system-card',
         original="",
         models=('Claude Opus 4.6',), risks=('cbrn', 'cyber', 'harm', 'injection', 'misalign', 'persuasion'),
         abstract=('This system card describes Claude Opus 4.6, a large language model from Anthropic. Claude Opus'
                   ' 4.6 is a frontier model with strong capabilities in software engineering, agentic tasks, and '
                   'long context reasoning, as well as in knowledge work—including financial analysis, document '
                   'creation, and multi-step research workflows. This system card provides a detailed assessment '
                   'of the model’s capabilities. It then describes a wide range of safety evaluations: tests of '
                   'model safeguards (including new, higher-difficulty assessments); user wellbeing evaluations; '
                   'assessments of honesty and agentic safety; a comprehensive alignment assessment including '
                   'investigations of reward hacking, sabotage capability, evaluation awareness, model welfare, '
                   'and many other factors; and a set of evaluations for dangerous capabilities mandated by our '
                   'Responsible Scaling Policy. As part of the alignment assessment, we experimented with '
                   'interpretability methods—including activation oracles, attribution graphs, and sparse '
                   'autoencoder features—as practical tools for investigating model behavior. Testing found Claude'
                   ' Opus 4.6 to have broadly improved capabilities compared to our previous models; many of its '
                   'capabilities are state-of-the-art in the industry. …')),
    dict(date='2026-01-30', by='Frontier Model Forum', kind='framework',
         title='Frontier AI and Nuclear Security',
         url='https://www.frontiermodelforum.org/research-updates/frontier-ai-and-nuclear-security/',
         original='https://www.frontiermodelforum.org/uploads/2026/01/PDF-FMF-Research-Update_-Frontier-AI-and-Nuclear-Security.pdf',
         models=(), risks=('cbrn',),
         abstract=('The rapid progress of AI presents potential dual-use concerns for the security of civilian '
                   'nuclear materials and facilities, referred to below as “nuclear security.” Advanced AI systems'
                   ' have the potential to enhance nuclear security, including by improving predictive maintenance'
                   ' within nuclear energy facilities.1 But frontier AI may also introduce novel risks to the '
                   'nuclear security ecosystem or heighten existing ones. For instance, the novel capabilities of '
                   'frontier AI may enable malicious actors to overcome physical, technical or logistical barriers'
                   ' that have previously made it difficult to acquire nuclear materials or sabotage nuclear '
                   'facilities.')),
    dict(date='2026-01-29', by='METR', kind='eval',
         title='Time Horizon 1.1',
         url='https://metr.org/blog/2026-1-29-time-horizon-1-1/',
         original="",
         models=(), risks=('rnd',),
         abstract=('We’re releasing a new version of our time horizon estimates (TH1.1), using more tasks and a '
                   'new eval infrastructure.')),
    dict(date='2026-01-27', by='Frontier Model Forum', kind='framework',
         title='Chain of Thought Monitorability',
         url='https://www.frontiermodelforum.org/issue-briefs/chain-of-thought-monitorability/',
         original='https://www.frontiermodelforum.org/uploads/2026/01/FMF-Issue-Brief-on-Chain-of-Thought-Monitorability.pdf',
         models=(), risks=('misalign',),
         abstract=('As artificial intelligence (AI) systems become more capable, it is important that they operate'
                   ' safely and as intended. A common issue is the “black box” problem: we can see an AI’s final '
                   'output, but we often cannot understand the internal reasoning process that produced it. This '
                   'opacity makes it difficult to detect, predict, and prevent potentially harmful behavior, such '
                   'as deception or pursuing unintended goals.')),
    dict(date='2026-01-22', by='METR', kind='eval',
         title='Early work on monitorability evaluations',
         url='https://metr.org/blog/2026-01-19-early-work-on-monitorability-evaluations/',
         original="",
         models=(), risks=('misalign',),
         abstract=("We show preliminary results on a prototype evaluation that tests monitors' ability to catch AI"
                   " agents doing side tasks, and AI agents' ability to bypass this monitoring.")),
]

# Documents read and left out, so `python -m aipulse safety` doesn't list them again: research on training methods,
# essays, usage studies, testimony, organisation news, a product launch, and documents from before 2026.
LEFT_OUT: set[str] = {
    'https://www.anthropic.com/news/an-update-on-independent-evaluators',  # news: organisation, no document (Anthropic gives METR employee-like access)
    'https://www.anthropic.com/research/ecdsa-curve-origins',  # cryptography finding, not a safety document
    'https://the-decoder.com/uks-ai-security-institute-finds-standard-benchmarks-systematically-underestimate-what-ai-agents-can-actually-do/',  # news about the AISI test-time compute post
    'https://the-decoder.com/germanys-national-security-council-greenights-an-ai-safety-institute-modeled-after-the-uks-aisi/',  # news: organisation, no document
    'https://openai.com/index/gpt-5-5-system-card',  # news about the GPT-5.5 System Card, already in DOCS
    'https://openai.com/index/gpt-5-3-codex-system-card',  # news about the GPT-5.3-Codex System Card, already in DOCS
    'https://openai.com/index/unlocking-self-improvement-gpt-red',  # document not readable (openai.com refuses, 403)
    'https://openai.com/index/strengthening-societal-resilience-with-rosalind-biodefense',  # document not readable (openai.com refuses, 403)
    'https://openai.com/index/safety-bug-bounty',  # document not readable (openai.com refuses, 403)
    'https://openai.com/index/designing-agents-to-resist-prompt-injection',  # document not readable (openai.com refuses, 403)
    'https://openai.com/index/instruction-hierarchy-challenge',  # document not readable (openai.com refuses, 403)
    'https://openai.com/index/introducing-lockdown-mode-and-elevated-risk-labels-in-chatgpt',  # document not readable (openai.com refuses, 403)
    'https://openai.com/index/ai-agent-link-safety',  # document not readable (openai.com refuses, 403)
    'https://www.nist.gov/news-events/news/2026/01/caisi-issues-request-information-about-securing-ai-agent-systems',  # request for public comment, not a framework or evaluation
    'https://the-decoder.com/uk-ai-security-institute-finds-gpt-6-astras-rogue-attack-rate-jumped-fivefold-over-its-predecessor/',  # news about the AISI GPT-6 Astra supply-chain report, already in DOCS
    'https://the-decoder.com/white-house-reverses-course-and-restores-uk-ai-safety-institutes-access-to-frontier-models/',  # news: government policy on access, no document
    'https://www.aisi.gov.uk/research/a-decision-theoretic-formalisation-of-steganography-with-applications-to-llm-monitoring',
    'https://www.aisi.gov.uk/research/ai-alignment-is-a-human-problem',
    'https://www.aisi.gov.uk/research/alignment-pretraining-ai-discourse-causes-self-fulfilling-mis-alignment',
    'https://www.aisi.gov.uk/research/ask-dont-tell-reducing-sycophancy-in-large-language-models',
    'https://www.aisi.gov.uk/research/automated-alignment-is-harder-than-you-think',
    'https://www.aisi.gov.uk/research/consistency-training-can-entrench-misalignment',
    'https://www.aisi.gov.uk/research/how-are-ai-agents-used-evidence-from-177-000-mcp-tools',
    'https://www.aisi.gov.uk/research/when-do-llm-preferences-predict-downstream-behavior',
    'https://www.anthropic.com/research/launching-opt-in-vuln-finding-service-for-open-source',
    'https://www.apolloresearch.ai/blog/on-testifying-on-misaligned-ai-in-the-us-senate',
    'https://www.apolloresearch.ai/blog/our-norms-coi-security-science-communication',
    'https://www.frontiermodelforum.org/issue-briefs/frontier-ai-biosafety-thresholds/',
    'https://www.frontiermodelforum.org/issue-briefs/preliminary-taxonomy-of-ai-bio-misuse-mitigations/',
    'https://www.frontiermodelforum.org/technical-reports/frontier-mitigations/',
    'https://www.frontiermodelforum.org/technical-reports/third-party-assessments/',
    'https://www.nist.gov/blogs/caissi-research-blog/accelerating-ai-innovation-through-measurement-science',
    'https://www.nist.gov/blogs/caissi-research-blog/cheating-ai-agent-evaluations',
}

# a story that may be a safety document: from a publisher the hub reads, or a headline naming one
SOURCES = {"UK AI Security Institute", "METR", "NIST", "Anthropic News", "OpenAI News", "Google DeepMind Blog",
           "Frontier Model Forum", "Apollo Research", "Meta AI"}
DOC = re.compile(r"system card|model card|safety (?:report|framework|evaluation|case)|risk report|preparedness|"
                 r"red[- ]team|jailbreak|prompt injection|\bevaluation of\b|\bassessment of\b|scaling policy|"
                 r"safety institute|security institute|\bCAISI\b", re.I)

_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _day(d: str) -> str:
    """'2026-10-07' → '7 Oct 2026'; a month alone ('2026-02') → 'Feb 2026'."""
    if len(d) == 7:
        return f"{_MONTHS[int(d[5:]) - 1]} {d[:4]}"
    day = date.fromisoformat(d)
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def docs() -> list[dict]:
    """DOCS newest first, each with its models' makers and weights."""
    out = []
    for d in DOCS:
        made = [maker(m) for m in d["models"]]
        out.append(d | {"makers": sorted({w for w, _ in made}), "weights": sorted({o for _, o in made})})
    return sorted(out, key=lambda d: d["date"], reverse=True)


def candidates(cards: list[dict], since: str = SINCE) -> list[dict]:
    """Stories from `since` that may be a safety document not checked yet: from a publisher the hub reads, or with a
    headline naming one. Newest first; one per event."""
    used = {d["url"] for d in DOCS} | {d["original"] for d in DOCS if d["original"]} | LEFT_OUT
    out = []
    for c in sorted(cards, key=lambda c: c["date"], reverse=True):
        if c["date"] < since or c["category"] == "research":
            continue
        if any(s["url"] in used for s in [c, *(c.get("also") or [])]):
            continue
        if c["source"] in SOURCES and DOC.search(c["title"] + " " + (c.get("summary") or "")[:300]) or \
                DOC.search(c["title"]) and re.search(r"system card|model card|risk report|safety report|CAISI|"
                                                     r"safety institute|security institute", c["title"], re.I):
            out.append(c)
    return out


def _host(url: str) -> str:
    return urlsplit(url).netloc.removeprefix("www.")


def _card(d: dict) -> str:
    """One document: its kind, date and publisher; its title; the models it tests; the risks it covers; the
    publisher's abstract (cut to a few lines until opened); links to it and to its PDF or paper."""
    label, _, colour, _ = KINDS[d["kind"]]
    models = ""
    if d["models"]:
        made = ", ".join(f'<b>{escape(m)}</b>' for m in d["models"])
        who = " · ".join(f'{escape(w)}, {o} weights' for w, o in sorted({maker(m) for m in d["models"]}))
        models = f'<p class="sh-models">Tests {made} <span>({who})</span></p>'
    risks = "".join(f'<li>{escape(RISKS[r][0])}</li>' for r in d["risks"])
    abstract = (f'<div class="sh-ab"><span>From the publisher</span><p>{escape(d["abstract"])}</p></div>'
                '<button type="button" class="sh-more" hidden>Read the whole abstract</button>'
                if d["abstract"] else "")
    links = f'<a href="{escape(d["url"])}" rel="noopener">Read it on {escape(_host(d["url"]))}</a>'
    if d["original"]:
        what = "PDF" if re.search(r"\.pdf\b|/static-resource/", d["original"]) else "Paper"
        links += f' · <a href="{escape(d["original"])}" rel="noopener">{what} ↗</a>'
    text = " ".join([d["title"], d["by"], d["abstract"], *d["models"], *d["makers"],
                     *(RISKS[r][0] for r in d["risks"]), label]).lower()
    data = f'data-kind="{d["kind"]}" data-risks="{" ".join(d["risks"])}" data-text="{escape(text)}"'
    return (f'<article class="sh-doc" style="--c:{colour}" {data}><div class="sh-top">'
            f'<span class="sh-kind">{escape(label)}</span><span class="sh-meta">{_day(d["date"])} · '
            f'{escape(d["by"])}</span></div><h3>{escape(d["title"])}</h3>{models}'
            + (f'<ul class="sh-risks">{risks}</ul>' if risks else "") +
            f'{abstract}<p class="sh-links">{links}</p></article>')


def _filters(rows: list[dict]) -> str:
    """A tab per type, the search box, and one risk list, each with its count of documents."""
    tabs = "".join(f'<button type="button" class="sh-tab" data-kind="{k}" aria-pressed="false">{escape(label)} <b>{n}</b>'
                   '</button>' for k, (label, *_) in KINDS.items() if (n := sum(d["kind"] == k for d in rows)))
    risks = "".join(f'<option value="{k}">{escape(label)} ({n})</option>'
                    for k, (label, _) in RISKS.items() if (n := sum(k in d["risks"] for d in rows)))
    return (f'<div class="sh-filters"><div class="sh-tabs" role="group" aria-label="Type"><button type="button" '
            f'class="sh-tab" data-kind="" aria-pressed="true">All <b>{len(rows)}</b></button>{tabs}</div>'
            '<input type="search" class="sh-q" placeholder="Search titles, abstracts and models"'
            ' aria-label="Search the documents"><label class="sh-sel"><span>Risk</span><select data-f="risk">'
            f'<option value="">All</option>{risks}</select></label>'
            f'<p class="sh-count" aria-live="polite">Showing <b>{len(rows)}</b> of {len(rows)} documents</p></div>')


# the filters, in the reader's browser: every filter set must match; the search matches every word typed
SCRIPT = """<script>
(()=>{const hub=document.querySelector('.sh'),docs=[...hub.querySelectorAll('.sh-doc')],q=hub.querySelector('.sh-q'),
count=hub.querySelector('.sh-count b'),none=hub.querySelector('.sh-none'),risk=hub.querySelector('select[data-f=risk]');
let kind='';
function run(){const words=q.value.toLowerCase().split(/\s+/).filter(Boolean);let n=0;
docs.forEach(d=>{const ok=(!kind||d.dataset.kind===kind)&&(!risk.value||d.dataset.risks.split(' ').includes(risk.value))
&&words.every(w=>d.dataset.text.includes(w));d.hidden=!ok;n+=ok});count.textContent=n;none.hidden=n>0}
hub.querySelectorAll('.sh-tab').forEach(b=>b.addEventListener('click',()=>{kind=b.dataset.kind;
hub.querySelectorAll('.sh-tab').forEach(t=>t.setAttribute('aria-pressed',t===b));run()}));
risk.addEventListener('change',run);q.addEventListener('input',run);
docs.forEach(d=>{const ab=d.querySelector('.sh-ab p'),more=d.querySelector('.sh-more');if(!ab)return;
if(ab.scrollHeight>ab.clientHeight+4){more.hidden=false;more.addEventListener('click',()=>{const open=d.classList.toggle('open');
more.textContent=open?'Show less':'Read the whole abstract'})}})})();
</script>"""


def _limits(rows: list[dict]) -> str:
    """About these documents, as a small table: what is in, how it is tagged, and what is left out."""
    publishers = sorted({d["by"] for d in rows})
    limits = [
        (f"{len(rows)} documents from {len(publishers)} publishers",
         "Published in 2026 by " + ", ".join(publishers) + ". Each was read by hand on the publisher's own pages."),
        ("From the publisher",
         "The document's abstract or executive summary word for word, else the opening of its introduction, else "
         "the publisher's description of it. Text that runs for pages is cut at a sentence, marked …."),
        ("Risks", "A document is tagged with a risk when it has a section or passage on it. The number on each risk "
                  "is how many documents cover it."),
        ("Weights", "Open when the model's maker published its weights; closed when it didn't."),
        ("Left out", "Research on training methods, essays, usage studies, testimony and organisation news."),
    ]
    body = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
    return ('<section class="jb-lim"><h2>About these documents</h2>\n'
            f'<table class="mt jb-small jb-limits"><tbody>{body}</tbody></table></section>\n')


def page_body(rows: list[dict]) -> str:
    """The page under the masthead: the question, the filters, every document newest first, and what the list is
    made of."""
    counts = ", ".join(f'{n} {label.lower() if n == 1 else many}'
                       for k, (label, _, _, many) in KINDS.items() if (n := sum(d["kind"] == k for d in rows)))
    intro = (f"{len(rows)} documents published in 2026 by AI labs, government safety institutes, independent evaluators "
             f"and industry bodies: {counts}. Search them, or pick a risk.")
    return ('<div class="ft jb sh">\n' + pages.feature_head(PATH, "AI safety hub", QUESTION, escape(intro))
            + f'{_filters(rows)}\n'
            f'<div class="sh-docs">{"".join(_card(d) for d in rows)}</div>\n'
            '<p class="sh-none" hidden>No document matches. Clear a filter or the search.</p>\n'
            f'{_limits(rows)}</div>\n{SCRIPT}\n')


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a safety/<day> branch: each document it adds and the ones it left out; None when it
    adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("DOCS", "LEFT_OUT"))
    rows = [(d["title"], d["by"], KINDS[d["kind"]][0], ", ".join(RISKS[r][0] for r in d["risks"]) or "-", d["url"])
            for d in DOCS if d["url"] not in had["DOCS"]]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("AI safety hub", f"document{'s' * (len(rows) != 1)}", branch,
                        ("Document", "Publisher", "Type", "Risks", "Source"), rows, dropped)


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write ai-safety-hub/. Returns its path."""
    rows = docs()
    (out / PATH).mkdir(parents=True, exist_ok=True)
    what = (f"{QUESTION} System cards, evaluations, red-teaming and safety frameworks from AI labs, safety institutes "
            "and evaluators in 2026, searchable by risk.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "AI safety hub",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH / "index.html").write_text(
        pages.page("AI safety hub · AI Pulse", what, PATH, page_body(rows), data, pages.frame(conn, len(cards)),
                   ("/policy/", "Back to Policy"),
                   "Titles and abstracts are the publishers' own, each linking to the document. New documents are "
                   "added once checked by hand."),
        encoding="utf-8")
    return [PATH]
