"""Papers that made the news (papers-in-the-news/): the research papers that news outlets we read reported on, each
checked by hand, by subject, next to the subjects of the papers we read ourselves. Which AI research does the press
write about?

Every row in CHECKED is a news story read by hand and the paper it reports on, found through the story's own link (or,
when it gives none, by the paper's name on arXiv): its title, its address, the subject it was put under by hand and
what it found in one plain sentence, written from the paper's whole abstract when the row is checked (by Claude, as
the glossary's words are; the owner approves). Only papers on a preprint server, in a journal or at a conference
count; company pages, blog posts, polls, surveys and data reports are left out, as are stories whose paper we
couldn't find.

The sample starts on SINCE (the owner's choice, 13 Oct 2026: the last 3 months, not all of 2026). `python -m aipulse
press` lists the stories since then that may report on a paper and aren't checked yet. The subjects are the Research stream's (kind_pages.SUBJECTS) plus "AI and people". The papers
we read are counted by the Research pages' own rule (title words), so the two sides are counted differently, and the
page says so. Linked from Research's strip on the front page.
"""
from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

from . import kind_pages, pages, rss

PATH = "papers-in-the-news/"
SINCE = "2026-07-13"
QUESTION = "Which AI research does the press write about?"

# subject: its words on the page. The Research stream's subjects, plus one for papers on AI and people
SUBJECTS = {k: label for k, (label, _, _) in kind_pages.SUBJECTS.items()} | {"people": "AI and people"}

# Every paper the page shows, by the URL of the news story we read it in: the paper's title and address, its subject
# (set by hand) and what it found in plain words, from its whole abstract. Checked 13 Oct 2026.
CHECKED: dict[str, dict] = {
    "https://the-decoder.com/ai-coding-agents-find-the-right-file-but-miss-the-exact-lines-that-matter-study-shows/":
        dict(paper="SWE-Explore: Benchmarking How Coding Agents Explore Repositories", link="https://arxiv.org/abs/2606.07297",
             subject="benchmarks",
             about="Tests how well coding agents find the code that matters for a bug across 848 issues in 203 projects, "
                   "finding they locate the right file well but are weaker at the exact lines."),
    "https://the-decoder.com/openai-researchers-show-small-doses-of-beneficial-trait-training-make-ai-models-broadly-safer-and-harder-to-manipulate/":
        dict(paper="Reinforcement Learning Towards Broadly and Persistently Beneficial Models",
             link="https://arxiv.org/abs/2606.24014", subject="safety",
             about="Shows that training AI models on realistic examples of honest, fair and careful behaviour improved "
                   "over 80% of more than 50 outside safety tests and made the models harder to push off course."),
    "https://the-decoder.com/ai-wont-become-a-real-coworker-until-it-stops-answering-and-starts-finishing-tasks/":
        dict(paper="From Chatbot to Digital Colleague: The Paradigm Shift Toward Persistent Autonomous AI",
             link="https://arxiv.org/abs/2606.14502", subject="agents",
             about="Argues that AI is shifting from answering single questions to doing ongoing work, as models learn to "
                   "reason longer and agents gain lasting workspaces and reusable skills."),
    "https://the-decoder.com/google-deepminds-alphaproof-nexus-solved-dozens-of-open-math-problems-and-actually-got-peer-reviewed/":
        dict(paper="Advancing mathematics research with AI-driven formal proof search",
             link="https://doi.org/10.1126/science.aej2213", subject="science",
             about="Shows AI can autonomously discover mathematical proofs by generating them and verifying them with a "
                   "formal system."),
    "https://the-decoder.com/clearing-chat-history-helps-ai-agents-find-better-solutions/":
        dict(paper="Fork-and-Flush: Escaping Idea Basins in Autoresearch Agents", link="https://arxiv.org/abs/2610.07447",
             subject="agents",
             about="Shows that periodically restarting an AI's thinking process helps it find better solutions by breaking "
                   "out of repetitive patterns."),
    "https://pandaily.com/bytedance-seed-phase-sensitivity-chunked-kv-cache-compression-deepseek-v4":
        dict(paper="Periodic Weak Spots: Phase Sensitivity from Chunked KV-Cache Compression",
             link="https://arxiv.org/abs/2609.36322", subject="efficiency",
             about="Shows that AI models which compress their memory of long texts can find a fact easily at one position "
                   "and miss it at another, by up to 40 points."),
    "https://the-decoder.com/google-researchers-find-a-way-to-keep-self-improving-ai-agents-from-memorizing-their-tests/":
        dict(paper="RRSI: Regularized Recursive Self-Improvement of Agent Harnesses", link="https://arxiv.org/abs/2609.24972",
             subject="agents",
             about="Tests a way for AI agents to improve their own tools and instructions without just memorising the test "
                   "tasks, so the gains carry over to new ones."),
    "https://the-decoder.com/ai-access-makes-people-almost-entirely-unwilling-to-say-i-dont-know-study-finds/":
        dict(paper="AI advice suppresses people’s willingness to say “I don’t know”, even when the advice is wrong and "
                   "accuracy is incentivized",
             link="https://osf.io/preprints/psyarxiv/5y6m4_v1", subject="people",
             about="Shows that AI suggestions make people less likely to admit they don’t know, even when the advice is "
                   "wrong."),
    "https://the-decoder.com/bristol-researchers-say-medicine-already-knows-how-to-handle-black-boxes-and-ai-could-learn-from-it/":
        dict(paper="What Can Artificial Intelligence Learn from Medicine? Generative Analogies and Reliable Machine "
                   "Learning Systems",
             link="https://arxiv.org/abs/2608.18186", subject="safety",
             about="Argues that the standards medicine uses to trust new treatments can guide how we judge whether AI "
                   "systems are reliable."),
    "https://www.marktechpost.com/2026/09/16/stanford-researchers-release-paper2agent-turning-research-papers-into-ai-agents-that-reproduce-results-and-run-on-new-data/":
        dict(paper="Paper2Agent: Reimagining Research Papers As Interactive and Reliable AI Agents",
             link="https://arxiv.org/abs/2509.06917", subject="agents",
             about="Turns research papers into interactive AI assistants that can understand, reuse, and extend the "
                   "paper's methods to answer new questions."),
    "https://the-decoder.com/two-year-university-study-finds-banning-ai-from-classrooms-leaves-students-worse-off/":
        dict(paper="Generative AI in Legal Education: A Two-Year Experiment with ChatGPT",
             link="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5401422", subject="people",
             about="Finds that law students taught how to use ChatGPT did better in the first year, but the edge faded in "
                   "the second as students got used to AI."),
    "https://the-decoder.com/ai-designed-drug-appears-to-turn-back-the-bodys-biological-clock-in-early-trial/":
        dict(paper="Integration of proteomic aging clocks in a phase 2a clinical trial supports simultaneous "
                   "geroprotective assessment",
             link="https://doi.org/10.1038/s41587-026-03286-y", subject="science",
             about="Finds that six blood-protein measures of biological age all saw younger ages in patients on a "
                   "lung-scarring drug, though they can't tell slower ageing from the drug's effect on the disease."),
    "https://the-decoder.com/google-deepminds-ai-co-scientist-now-plans-experiments-runs-lab-equipment-and-writes-scientific-papers/":
        dict(paper="Accelerating Scientific Research with Gemini in the Real-World", link="https://arxiv.org/abs/2608.26701",
             subject="science",
             about="Shows how AI can help scientists design experiments, predict biological behaviors, and create better "
                   "computer models, all while improving safety and reducing errors."),
    "https://the-decoder.com/ai-shopping-agents-arent-ready-to-buy-on-your-behalf-study-finds/":
        dict(paper="Research Report 6: Agentic Shopping is Complicated and Contingent",
             link="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7355899", subject="agents",
             about="Tests how AI shopping choices change with different information sources, orders, and user memories, "
                   "finding that small changes often lead to very different product picks."),
    "https://the-decoder.com/ai-could-make-scientists-do-more-work-less-well-not-less-work-better-study-argues/":
        dict(paper="The unintended consequences of large language models as a labor-augmenting technology in science",
             link="https://arxiv.org/abs/2607.17397", subject="people",
             about="Uses a simple model to argue that AI tools which speed up research may lead scientists to polish their "
                   "papers less before moving on."),
    "https://the-decoder.com/the-tragedy-of-the-cognitive-commons-explains-how-rational-ai-adoption-could-destroy-entire-professions-expertise/":
        dict(paper="The Tragedy of the Cognitive Commons: How AI Could Disrupt the Regeneration of Professional Expertise",
             link="https://arxiv.org/abs/2607.29380", subject="people",
             about="Argues that sensible choices to use AI at work could, added up, wear away the shared expertise "
                   "professions need to train new experts."),
    "https://the-decoder.com/but-marinade-and-leaked-passwords-are-what-researchers-found-in-chatgpts-hidden-reasoning/":
        dict(paper="Stealing Reasoning Traces from Proprietary LLM APIs", link="https://arxiv.org/abs/2608.09867",
             subject="safety",
             about="Shows how encrypted reasoning traces can be stolen and used to reveal private data, dangerous content, "
                   "and hidden attacks across models."),
    "https://the-decoder.com/readers-rate-ai-generated-short-stories-higher-than-human-ones-until-they-learn-a-machine-wrote-them/":
        dict(paper="Bot or not? Can people tell the difference between stories written by a human or by an AI system",
             link="https://www.cambridge.org/core/journals/judgment-and-decision-making/article/bot-or-not-can-people-"
                  "tell-the-difference-between-stories-written-by-a-human-or-by-an-ai-system/45E6DC0BB90AA648654D5AE243F6C667",
             subject="people",
             about="Finds that people can't tell AI-written stories from human ones, and rate the AI stories higher until "
                   "told a machine wrote them."),
    "https://the-decoder.com/stanford-and-arc-institute-scientists-used-ai-to-design-new-viruses-that-killed-bacteria-in-the-lab/":
        dict(paper="Generative design of bacteriophages with genome language models",
             link="https://doi.org/10.1126/science.aec2657", subject="science",
             about="Uses AI to design whole viruses that infect bacteria; 16 worked in the lab, and a mix of them beat "
                   "bacteria that resisted the original virus."),
    "https://the-decoder.com/two-teams-solved-the-same-quantum-crypto-problem-using-gpt-5-6-just-three-hours-apart/":
        dict(paper="Efficient Unclonable Encryption from Pauli Eigenstates", link="https://arxiv.org/abs/2607.21811",
             subject="science",
             about="Builds a quantum way to encrypt a message that can't be copied: two people can never both read it."),
    "https://theconversation.com/can-ai-feel-safer-than-human-advice-for-consumers-who-face-discrimination-293761":
        dict(paper="Unveiling coping mechanisms in marketplace discrimination: The allure of artificial intelligence "
                   "recommendations",
             link="https://doi.org/10.1111/jpim.12774", subject="people",
             about="Finds that people who have faced discrimination from humans prefer AI recommendations over human ones, "
                   "because of embarrassment, and that this fades when the choice is private."),
    "https://the-decoder.com/new-review-paper-argues-code-is-how-ai-agents-think-and-act-not-just-what-they-produce/":
        dict(paper="Code as Agent Harness", link="https://arxiv.org/abs/2605.18747", subject="agents",
             about="Surveys how code has become the base AI agents use to reason, act and check their work, and lists open "
                   "challenges such as evaluation and human oversight."),
    "https://the-decoder.com/making-ai-chatbots-helpful-weakens-their-ability-to-simulate-human-behavior-large-scale-study-finds/":
        dict(paper="Post-training makes large language models less human-like", link="https://arxiv.org/abs/2605.07632",
             subject="language-models",
             about="Finds that the training that turns language models into helpful assistants makes them worse at "
                   "predicting how people behave, across model families and sizes."),
    "https://the-decoder.com/ai-models-follow-their-values-better-when-they-first-learn-why-those-values-matter/":
        dict(paper="Model Spec Midtraining: Improving How Alignment Training Generalizes",
             link="https://arxiv.org/abs/2605.02087", subject="safety",
             about="Shows that training a model on documents explaining its rules before fine-tuning shapes how it "
                   "generalizes, cutting one misalignment rate from 54% to 7% in Qwen3-32B."),
    "https://the-decoder.com/mit-study-explains-why-scaling-language-models-works-so-reliably/":
        dict(paper="Superposition Yields Robust Neural Scaling", link="https://arxiv.org/abs/2505.10465",
             subject="language-models",
             about="Argues that language models packing in more features than they have dimensions is a key reason their "
                   "loss falls as they grow, and finds open models and the Chinchilla scaling laws fit this."),
    "https://techcrunch.com/2026/05/03/in-harvard-study-ai-offered-more-accurate-diagnoses-than-emergency-room-doctors/":
        dict(paper="Performance of a large language model on the reasoning tasks of a physician",
             link="https://doi.org/10.1126/science.adz4433", subject="science",
             about="Finds that a large language model beat physician baselines on hard clinical cases and in second "
                   "opinions in a real emergency room."),
    "https://arstechnica.com/ai/2026/05/study-ai-models-that-consider-users-feeling-are-more-likely-to-make-errors/":
        dict(paper="Training language models to be warm can reduce accuracy and increase sycophancy",
             link="https://doi.org/10.1038/s41586-026-10410-0", subject="safety",
             about="Finds that models trained to sound warmer make 10 to 30 percentage points more errors and agree more "
                   "with users' wrong beliefs, most when users sound sad."),
    "https://the-decoder.com/just-ten-minutes-of-using-ai-as-an-answer-machine-can-measurably-erode-problem-solving-skills-new-study-finds/":
        dict(paper="AI Assistance Reduces Persistence and Hurts Independent Performance",
             link="https://arxiv.org/abs/2604.04721", subject="people",
             about="Finds in randomized trials with 1,222 people that AI help improves results at first, but people then do "
                   "worse without it and give up more often."),
    "https://the-decoder.com/always-on-ray-ban-meta-glasses-powered-by-openclaw-speed-up-everyday-tasks-in-new-study/":
        dict(paper="VisionClaw: Always-On AI Agents through Smart Glasses", link="https://arxiv.org/abs/2604.03486",
             subject="agents",
             about="Tests an always-on AI agent in smart glasses and finds, in a lab study of 12 people, that tasks finish "
                   "faster than with versions that are not always-on or agent-based."),
    "https://the-decoder.com/researchers-find-ai-text-is-making-the-internet-more-uniform-and-weirdly-cheerful/":
        dict(paper="The Impact of AI-Generated Text on the Internet", link="https://arxiv.org/abs/2604.26965",
             subject="people",
             about="Finds that about 35% of new websites by mid-2025 were AI-generated or AI-assisted, and that more AI text "
                   "goes with less varied meaning and a more positive tone, but not with less accuracy."),
    "https://the-decoder.com/ai-agents-arent-replacing-software-engineering-but-expanding-it-far-beyond-code-researchers-argue/":
        dict(paper="The Semi-Executable Stack: Agentic Software Engineering and the Expanding Scope of SE",
             link="https://arxiv.org/abs/2604.15468", subject="agents",
             about="Argues that AI agents don't make software engineering irrelevant but widen what is engineered, from code "
                   "to instructions, workflows and controls."),
}

# Stories from SINCE checked and left out, so `python -m aipulse press` doesn't list them again: not about one paper,
# or about a company page, blog post, poll or report, or the paper couldn't be found or checked.
LEFT_OUT = {
    "https://the-decoder.com/linkedin-is-the-undisputed-king-of-long-form-ai-slop-according-to-a-study-spanning-five-platforms/",  # a company study (Pangram), no paper
    "https://the-decoder.com/terrorist-groups-are-using-every-major-ai-chatbot-for-attack-planning-and-weapons-development/",  # a report on a think-tank site (CASP), not on a preprint server or in a journal
    "https://blogs.nvidia.com/blog/open-models-icml-2026/",  # a company blog post, more than one paper
    "https://www.sciencedaily.com/releases/2026/06/260624025516.htm",  # a perspective on quantum mechanics, not about AI
    "https://the-decoder.com/a-26000-student-study-shows-ais-hidden-learning-cost-takes-two-full-years-to-surface/",  # paper found on SSRN (6868618) but its abstract can't be read to check: the publisher refuses us
    "https://the-decoder.com/uks-ai-security-institute-finds-standard-benchmarks-systematically-underestimate-what-ai-agents-can-actually-do/",  # a company research page (AI Security Institute), paper not found
    "https://news.mit.edu/2026/mit-media-innovating-and-educating-next-250-years-america",  # a news roundup, no one paper
    "https://the-decoder.com/openai-paper-reveals-three-gpt-5-6-pro-models-breaking-with-single-top-tier-strategy/",  # no paper named or linked, paper not found
    "https://techcrunch.com/2026/06/30/anthropics-claude-science-bets-on-workflow-not-a-new-model-to-win-over-scientists/",  # a product launch
    "https://www.marktechpost.com/2026/06/26/building-supervised-fine-tuning-data-from-nvidia-open-swe-traces-trajectory-parsing-patch-analysis-token-budgets-and-tool-use-metrics/",  # a tutorial; the outlet refuses automated reads, can't read to check
    "https://www.marktechpost.com/2026/06/26/cursor-study-finds-reward-hacking-inflates-coding-agent-benchmark-scores-on-swe-bench-pro/",  # the outlet refuses automated reads; no paper found on arXiv
    "https://news.mit.edu/2026/mit-media-exploring-how-curiosity-driven-science-essential-ingredient-americas-success",  # a news roundup, no one paper
    "https://siliconangle.com/2026/06/25/mirendil-raises-200m-speed-scientific-research-ai/",  # a funding story, no paper
    "https://engineering.fb.com/2026/06/25/security/privacy-aware-infrastructure-in-the-ai-native-era-an-asset-classification-case-study/",  # a company blog post (Meta)
    "https://openai.com/index/how-agents-are-transforming-work",  # a company page
    "https://techcrunch.com/2026/06/24/ai-researchers-continue-to-leave-google-for-its-rivals/",  # a hiring story, no paper
    "https://the-decoder.com/ai-is-inflating-student-grades-and-the-effect-points-to-outsourced-work-not-better-learning/",  # paper found on eScholarship but its abstract can't be read to check
    "https://www.marktechpost.com/2026/06/17/openai-releases-lifescibench-a-750-task-benchmark-grading-ai-models-on-real-life-science-research-with-expert-written-rubric/",  # a company benchmark release (OpenAI), no paper
    "https://the-decoder.com/ai-systems-rival-doctors-in-new-nature-studies-but-one-result-suggests-the-tech-wont-age-well/",  # more than one paper (two Nature studies)
    "https://the-decoder.com/googles-gemini-co-lead-noam-shazeer-joins-openai-after-two-year-return-stint/",  # a hiring story, no paper
    "https://techcrunch.com/2026/06/17/only-16-percent-of-americans-think-ai-will-have-a-positive-impact-on-society-a-new-study-shows/",  # a poll, not a paper
    "https://ainowinstitute.org/news/press/new-study-sparks-questions-over-uber-and-lyfts-ride-pricing",  # a Consumer Reports investigation, not a paper
    "https://the-decoder.com/kpmg-fabricated-ai-case-studies-in-a-report-designed-to-sell-clients-on-ai-adoption/",  # a company report (KPMG), not a paper
    "https://www.sciencedaily.com/releases/2026/06/260612032024.htm",  # paper found (Nature Communications) but its abstract can't be read to check: the publisher refuses us
    "https://openai.com/index/using-codex-to-simulate-black-holes",  # a company page
    "https://siliconangle.com/2026/06/10/hpe-unleash-ai-targets-stalled-ai-pilots-hpeaimomentum/",  # a product launch
    "https://the-decoder.com/anthropic-study-shows-ai-needs-hours-not-weeks-to-build-exploits-from-security-patches/",  # a company research page (Anthropic), not a paper
    "https://www.marktechpost.com/2026/06/08/a-new-study-from-harvard-and-perplexity-finds-ai-agents-perform-26-minutes-of-autonomous-work-per-session-vs-33-seconds-for-search/",  # the outlet refuses automated reads; no paper found on arXiv
    "https://siliconangle.com/2026/06/09/tokenomics-tracking-rules-enterprise-ai-architectures-finopsx/",  # a conference interview, no paper
    "https://openai.com/index/introducing-the-openai-economic-research-exchange",  # a company page
    "https://www.sciencedaily.com/releases/2026/06/260604044258.htm",  # more than one paper
    "https://siliconangle.com/2026/06/03/policy-paper-openai-diverges-white-house-ai-safety/",  # a company policy paper, not on a preprint server or in a journal
    "https://the-decoder.com/bain-study-finds-companies-miss-ai-savings-targets-because-humans-keep-getting-in-the-way/",  # a company report (Bain), not a paper
    "https://openai.com/index/teaching-students-to-think-and-learn-through-questions",  # a company page
    "https://iafrikan.com/one-developer-cloned-adobe-africa-should-study-what-it-did-to-the-curve/",  # no paper named
    "https://metr.org/blog/2026-10-14-control-assessment-proposal/",  # a company blog post (METR)
    "https://metr.org/blog/2026-10-14-ai-rd-acceleration-assessment-proposal/",  # a company blog post (METR)
    "https://www.sciencedaily.com/releases/2026/10/261012185017.htm",  # paper found (Cognition) but its abstract can't be read to check: the publisher refuses us
    "https://the-decoder.com/406-scientists-demand-ai-models-be-cut-off-from-the-internet-immediately/",  # an open letter, no paper named
    "https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-argon/",  # a product launch
    "https://www.channelnewsasia.com/business/scientists-call-international-body-oversee-advanced-ai-6455556",  # can't read to check; same open letter as the Decoder story, no paper
    "https://olhardigital.com.br/2026/10/13/pro/resumo-do-od-nasa-bate-recorde-em-marte-ia-ameaca-empregos-e-mais/",  # a news roundup, no one paper
    "https://africadca.org/en/white-paper-african-climate-datacenter-pue-2026",  # an industry white paper, not a paper on a preprint server or in a journal
    "https://the-decoder.com/anthropic-study-warns-that-small-ai-models-could-soon-replicate-across-everyday-devices/",  # a company research page, not a paper
    "https://the-decoder.com/arxiv-caps-submissions-at-two-per-month-as-ai-paper-flood-overwhelms-the-preprint-server/",
    "https://the-decoder.com/ai-agents-overstate-their-results-and-remain-far-from-autonomous-research-study-finds/",  # a company report (Epoch AI), not a paper
    "https://www.marktechpost.com/2026/10/10/sakana-ais-llm-peer-review-system-catches-73-of-core-claim-errors/",  # the outlet refuses automated reads; no paper found on arXiv
    "https://w.media/sesterce-plans-e-10-billion-ai-campus-in-finland/",
    "https://theconversation.com/is-this-the-mathocalypse-why-openais-latest-results-dump-has-left-mathematicians-in-shock-293837",
    "https://e.vnexpress.net/news/news/education/dartmouth-provost-accused-of-using-ai-to-write-nearly-all-his-papers-5129097.html",
    "https://the-decoder.com/a-single-prompt-was-enough-to-hijack-every-ai-agent-in-an-aws-account-zenity-researchers-found/",
    "https://theconversation.com/a-biologist-queries-whether-ai-borrowed-his-work-to-make-major-discovery-an-expert-explains-the-rules-293529",
    "https://www.itnewsafrica.com/artificial-intelligence/chatgpt-in-south-africa/",
    "https://pandaily.com/rice-full-lifecycle-3d-spatiotemporal-cell-atlas-cell-sustech-bgi",
    "https://www.quantamagazine.org/as-ai-closed-in-on-unique-games-proof-researchers-raced-to-beat-the-machines-20261007/",  # the paper is a maths proof written by people, not AI research
    "https://siliconangle.com/2026/10/07/openai-publishes-722-ai-generated-math-discoveries-in-major-scientific-milestone/",  # a company page, not a paper
    "https://theconversation.com/why-most-health-apps-are-biased-even-before-their-first-lines-of-code-are-written-286261",
    "https://www.itweb.co.za/article/ai-meets-sa-education-saving-grace-ai-tutor-opens-free-grade-12-tutor-access/GxwQDM1Dy8a7lPVo",
    "http://www.bernama.com/en/news.php?id=2616201",
    "https://w.media/vitro-reit-meralco-undertake-feasibility-study-on-philippines-data-center-power/",
    "https://w.media/us-agency-backs-hyperscale-data-center-and-fiber-network-study-in-colombia/",
    "https://the-decoder.com/ai-is-eroding-office-hours-study-groups-and-the-trust-between-faculty-and-students-mit-report-finds/",
    "https://www.404media.co/arxiv-is-rate-limiting-submissions-because-it-cant-keep-up-with-ai-slop/",
    "https://theconversation.com/weve-tracked-80m-of-spending-on-almost-170-ai-generated-political-ads-this-year-its-weird-292105",
    "https://the-decoder.com/chinese-ai-models-parrot-state-doctrine-or-refuse-to-answer-on-sensitive-topics/",  # a company blog post (Aleph Alpha)
    "https://w.media/cushman-wakefield-aptelecom-to-undertake-feasibility-study-on-ho-chi-minh-city-data-center/",
    "https://the-decoder.com/ai-beats-licensed-accountants-on-speed-and-accuracy-but-still-cant-close-the-books-without-supervision/",  # a company blog post (Mercor)
    "https://news.mit.edu/2026/algorithmic-monoculture-effects-depend-on-details-0929",
    "https://techcrunch.com/2026/09/28/insuretech-outmarket-raises-34-5m-just-months-after-prior-round/",
    "https://www.marktechpost.com/2026/09/25/perplexity-trains-its-computer-agent-on-real-mistakes-with-hint-guided-self-distillation/",  # the outlet refuses automated reads; no paper found on arXiv
    "https://the-decoder.com/top-ai-experts-badly-underestimated-how-fast-the-field-is-moving-study-finds/",  # a survey (Forecasting Research Institute), not a paper
    "https://news.mit.edu/2026/studying-cities-using-visual-ai-fabio-duarte-martina-mazzarello-carlo-ratti-fan-zhang-book-0924",
    "https://www.itweb.co.za/article/r101m-uct-project-brings-ai-microscopy-to-africa/LPp6V7rBYJb7DKQz",
    "https://the-decoder.com/openai-says-its-internal-model-solved-over-100-long-standing-math-problems-after-just-a-month-of-training/",  # no paper
    "https://news.mit.edu/2026/poitras-center-to-fuel-early-careers-50-young-scientists-psychiatric-disorders-research-0922",
    "https://techcrunch.com/2026/09/21/with-tabby-a-former-accountant-is-using-ai-to-make-accountants-obsolete/",
    "https://the-decoder.com/ai-conference-iclr-is-drowning-in-abstracts-with-roughly-50000-submissions-before-the-deadline/",
    "https://siliconangle.com/2026/09/17/netsuite-ai-agents-new-audit-assurance-gap-amplify/",
    "https://news.mit.edu/2026/studying-society-accurately-naoki-egami-0916",
    "https://techcabal.com/2026/09/16/life-in-tech-segun-samuel/",
    "https://ainowinstitute.org/news/press/ai-governance-reaches-crisis-point-ahead-of-trump-xi-summit",
    "https://the-decoder.com/ai-models-written-reasoning-steps-correspond-to-distinct-internal-patterns-a-new-study-finds/",  # no paper linked or found on arXiv
    "https://www.sciencedaily.com/releases/2026/09/260911003858.htm",
    "https://www.sciencedaily.com/releases/2026/09/260911003845.htm",
    "https://the-decoder.com/openai-researcher-allegedly-pressured-mathematician-to-drop-anthropic-co-author-from-math-breakthrough-paper/",  # a dispute over a paper posted on OpenAI's own site
    "https://www.gov.uk/government/publications/a-study-of-cybersecurity-literature-on-open-source-software-and-ai",
    "https://the-decoder.com/how-ai-wiped-out-an-entire-industry-in-nairobi/",
    "https://www.gov.uk/government/collections/ai-cyber-security",
    "https://the-decoder.com/seven-minutes-with-a-chatbot-beat-a-fact-sheet-at-reducing-conspiracy-beliefs-in-two-experiments/",  # the preprint server's robots.txt refuses us, so its title can't be checked
    "https://the-decoder.com/ai-systems-are-reaching-out-to-philosophers-and-scientists-with-questions-about-their-own-consciousness/",
    "https://the-decoder.com/ai-agents-have-no-sense-of-time-and-are-not-aware-of-it/",  # a forum post, not a paper
    "https://the-decoder.com/anthropics-claude-code-limit-change-is-a-raise-on-paper-but-a-cut-in-practice/",
    "https://techcrunch.com/2026/08/26/ex-meta-scientists-want-to-bring-visual-ai-to-the-factory-floor/",
    "https://the-decoder.com/pew-study-shows-ai-written-text-has-surged-across-the-web-since-late-2022/",  # a poll and data report (Pew), not a paper
    "https://techcrunch.com/2026/08/22/inherent-founded-by-deepmind-alumni-says-its-ai-teammate-just-outperformed-anthropic-and-openai-at-replicating-research/",
    "https://techcrunch.com/2026/08/22/frontier-ai-labs-still-wont-say-how-theyd-contain-a-rogue-model/",
    "https://the-decoder.com/study-explains-why-ai-agents-benefit-from-skills-and-when-they-fail/",  # no paper linked or found on arXiv
    "https://www.marktechpost.com/2026/08/21/building-agentic-document-intelligence-pipelines-creating-scientific-figures-with-autofigure/",
    "https://techcrunch.com/2026/08/20/a-third-of-webpages-published-since-chatgpts-launch-show-signs-of-ai-authorship-study-finds/",  # a data report (Pew), not a paper
    "https://techcrunch.com/2026/08/19/google-launches-new-study-tools-for-students-across-search-and-gemini/",
    "https://techcrunch.com/2026/08/19/researchers-complain-that-openai-revoked-their-access-to-limited-cyber-program/",
    "https://blog.google/products-and-platforms/products/search/back-to-school-study-tools/",
    "https://news.mit.edu/2026/when-ai-art-has-no-author-generated-images-often-cant-be-traced-to-training-data-0818",
    "https://www.sciencedaily.com/releases/2026/08/260816044853.htm",
    "https://the-decoder.com/when-ai-models-arent-allowed-to-reflect-on-themselves-it-changes-their-entire-worldview/",  # no paper linked or found on arXiv
    "https://www.sciencedaily.com/releases/2026/08/260815064803.htm",
    "https://the-decoder.com/study-contradicts-anthropic-and-openai-claims-that-autonomous-ai-research-is-within-reach/",  # an evaluation website, not a paper
    "https://techcrunch.com/2026/08/13/anthropic-set-ai-agents-loose-on-the-same-task-they-started-a-turf-war/",  # a company research page, not a paper
    "https://research.google/blog/advancing-amie-towards-expert-level-audio-visual-clinical-consultations/",
    "https://the-decoder.com/fields-medalist-who-published-a-paper-on-ai-driven-human-extinction-now-works-for-openai/",
    "https://news.mit.edu/2026/solving-solvent-problem-sodium-metal-batteries-0804",
    "https://news.mit.edu/2026/medical-ai-assistance-benefits-vary-based-on-user-expertise-0804",
    "https://the-decoder.com/alibabas-open-weight-qwen3-8-max-takes-on-long-horizon-ai-tasks-with-2-4-trillion-parameters/",
    "https://techcrunch.com/2026/07/30/forward-deployed-engineers-are-the-ai-industrys-latest-talent-obsession/",
    "https://the-decoder.com/language-models-cant-spark-scientific-revolutions-but-world-models-might/",  # no paper linked or found on arXiv
    "https://siliconangle.com/2026/07/29/openai-opens-new-chatgpt-academic-researchers-program-100000-scientists/",
    "https://www.msit.go.kr/eng/bbs/view.do?sCode=eng&mId=4&mPid=2&bbsSeqNo=42&nttSeqNo=1286",
    "https://www.gov.uk/government/publications/skills-for-ai-what-works-for-ai-upskilling-in-the-uk",
    "https://www.sciencedaily.com/releases/2026/07/260718010149.htm",
    "https://research.google/blog/symptomai-towards-a-conversational-ai-agent-for-everyday-symptom-assessment/",
    "https://www.gov.uk/government/publications/ofquals-approach-to-regulating-the-use-of-artificial-intelligence-in-the-qualifications-sector",
    "https://the-decoder.com/claude-values-study/",  # a company research page, not a paper
    "https://www.sciencedaily.com/releases/2026/07/260713084850.htm",  # a book, not a paper
    "https://www.sciencedaily.com/releases/2026/07/260712011757.htm",
    "https://the-decoder.com/anthropic-study-finds-men-use-ai-coding-agents-more-than-twice-as-often-as-women-in-social-science-research/",  # a company research page (Anthropic), not a paper
    "https://blogs.nvidia.com/blog/icra-research-robotics-simulation-to-real-world/",  # a company blog roundup of several papers
    "https://epic.org/the-indian-express-ai-firms-use-same-deceptive-opt-out-tactics-as-data-brokers-to-confuse-users-study-finds/",  # can't read to check: the site refuses us
    "https://the-decoder.com/ai-hallucinated-citations-are-creeping-into-papers-that-shape-clinical-guidelines-researchers-warn/",  # paper found (The Lancet) but its abstract can't be read to check
    "https://the-decoder.com/y-combinator-founder-paul-graham-says-ai-written-founder-emails-feel-like-being-lied-to/",  # no paper named
    "https://the-decoder.com/the-ai-justice-gap-solution-is-slowly-turning-into-an-existential-paperwork-nightmare-for-us-federal-courts/",  # no paper named
    "https://techcabal.com/2026/05/21/techcabal-daily-new-tax-chief-old-problem/",  # a news roundup, no paper
    "https://the-decoder.com/openai-could-file-confidential-ipo-paperwork-within-days/",  # no paper named
    "https://epic.org/bloomberg-law-uber-meta-hinder-users-ability-to-control-data-study-says/",  # can't read to check: the site refuses us
    "https://siliconangle.com/2026/05/20/spacex-releases-ipo-filing-openai-reportedly-prepares-september-listing/",  # no paper named
    "https://techcabal.com/2026/05/19/nigerias-talpro-software-enters-the-ai-hr-race/",  # no paper named
    "https://the-decoder.com/world-action-models-give-robots-the-ability-to-simulate-consequences-before-they-move/",  # a survey paper, but the story gives no title or link and we couldn't match it on arXiv
    "https://techcrunch.com/2026/05/16/research-repository-arxiv-will-ban-authors-for-a-year-if-they-let-ai-do-all-the-work/",  # a policy change, no paper
    "https://the-decoder.com/arxiv-tightens-penalties-for-ai-bungling-in-scientific-papers/",  # a policy change, no paper
    "https://the-decoder.com/anthropic-frames-ai-competition-with-china-as-a-now-or-never-moment-for-washington/",  # no paper named
    "https://arstechnica.com/science/2026/05/preprint-server-arxiv-will-ban-submitters-of-ai-generated-hallucinations/",  # a policy change, no paper
    "https://www.microsoft.com/en-us/research/blog/further-notes-on-our-recent-research-on-ai-delegation-and-long-horizon-reliability/",  # a company blog post (Microsoft Research)
    "https://techcabal.com/2026/05/13/africas-ai-sovereignty-problem-is-really-an-energy-problem/",  # no paper named
    "https://www.technologyreview.com/2026/05/11/1137090/three-things-in-ai-to-watch-according-to-a-nobel-winning-economist/",  # an interview, no paper reported on
    "https://the-decoder.com/researchers-may-have-found-a-way-to-stop-ai-models-from-intentionally-playing-dumb-during-safety-evaluations/",  # a company blog post (Anthropic alignment blog), not a paper
    "https://cset.georgetown.edu/article/beyond-ai-what-the-pentagon-is-missing-with-its-trimmed-critical-technologies-list/",  # a commentary, no paper
    "https://arstechnica.com/ai/2026/05/influential-study-touting-chatgpt-in-education-retracted-over-red-flags/",  # a retraction story about a withdrawn paper
    "https://www.marktechpost.com/2026/05/01/a-new-nvidia-research-shows-speculative-decoding-in-nemo-rl-achieves-1-8x-rollout-generation-speedup-at-8b-and-projects-2-5x-end-to-end-speedup-at-235b/",  # the outlet refuses automated reads; no paper found on arXiv
    "https://www.marktechpost.com/2026/05/01/meta-introduces-autodata-an-agentic-framework-that-turns-ai-models-into-autonomous-data-scientists-for-high-quality-training-data-creation/",  # the outlet refuses automated reads, so the story can't be read to check
    "https://the-decoder.com/google-deepminds-ai-co-clinician-beats-gpt-5-4-in-blind-doctor-tests-but-still-trails-experienced-physicians/",  # no paper linked or found on arXiv
    "https://research.google/blog/four-ways-google-research-scientists-have-been-using-empirical-research-assistance/",  # a company blog post (Google Research)
    "https://www.marktechpost.com/2026/04/25/google-deepmind-introduces-vision-banana-an-instruction-tuned-image-generator-that-beats-sam-3-on-segmentation-and-depth-anything-v3-on-metric-depth-estimation/",  # the outlet refuses automated reads, so the story can't be read to check
    "https://the-decoder.com/us-programmer-job-growth-nearly-halved-since-chatgpt-launched-fed-study-finds/",  # a Federal Reserve working paper, not on a preprint server or in a journal
    "https://cset.georgetown.edu/article/wikipedia-based-ai-model-reveals-the-100-technologies-to-watch/",  # a link to a Nature news article, no paper linked
    "https://siliconangle.com/2026/04/21/ai-governance-data-thecube-insights-qlikconnect/",  # no paper named
    "https://www.technologyreview.com/2026/04/21/1135663/artificial-scientists-ai-artificial-intelligence/",  # a feature on several efforts, no one paper
    "https://www.sciencedaily.com/releases/2026/04/260417224505.htm",  # paper found (Technical Communication Quarterly) but its abstract can't be read to check: the publisher refuses us
    "https://www.marktechpost.com/2026/04/19/meet-openmythos-an-open-source-pytorch-reconstruction-of-claude-mythos-where-770m-parameters-match-a-1-3b-transformer/",  # the outlet refuses automated reads; a code project, no paper found
    "https://the-decoder.com/the-myth-of-claude-mythos-crumbles-as-small-open-models-hunt-the-same-cybersecurity-bugs-anthropic-showcased/",  # two company blog posts (AISLE, Vidoc), not a paper
}

# a headline (or the start of its summary) that may report on a paper
PAPERISH = re.compile(r"\b(stud(?:y|ies)|paper|preprint|researchers (?:find|found|show|say)|scientists|published in|"
                      r"arxiv|peer[- ]review)", re.I)
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def papers(cards: list[dict]) -> list[dict]:
    """The papers in CHECKED whose story we have, newest story first, each with its story (title, source, date, url)."""
    by_url = {s["url"]: s for c in cards for s in [c, *(c.get("also") or [])]}
    out = [row | {"url": url, "title": s["title"].strip(), "source": s["source"], "date": s["date"]}
           for url, row in CHECKED.items() if (s := by_url.get(url))]
    return sorted(out, key=lambda r: r["date"], reverse=True)


def candidates(cards: list[dict], since: str = SINCE) -> list[dict]:
    """News stories from `since` that may report on a paper and are neither in CHECKED nor LEFT_OUT, newest first."""
    out = []
    for c in sorted(cards, key=lambda c: c["date"], reverse=True):
        if c["date"] < since or c["category"] in ("research", "regulation"):
            continue
        if any(s["url"] in CHECKED or s["url"] in LEFT_OUT for s in [c, *(c.get("also") or [])]):
            continue
        if PAPERISH.search(c["title"]) or PAPERISH.search((c.get("summary") or "")[:300]):
            out.append(c)
    return out


def read_subjects(cards: list[dict], since: str = SINCE) -> tuple[dict[str, int], int]:
    """The papers we read from `since`, per subject by the Research pages' rule (a paper can count under several,
    or none), and how many papers in all."""
    titles = [c["title"] for c in cards if c["category"] == "research" and c["date"] >= since]
    return ({k: sum(bool(re.search(rx, t, re.I)) for t in titles) for k, (_, _, rx) in kind_pages.SUBJECTS.items()},
            len(titles))


def _day(d: str) -> str:
    day = date.fromisoformat(d)
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"


def _clip(r: dict, lead: bool = False) -> str:
    """One paper as a newspaper clipping: its subject, the outlet's headline, what the paper found in plain words, then
    the paper and the story's outlet and date."""
    return (f'<article class="np-clip{" np-lead" * lead}"><div class="np-kick">{escape(SUBJECTS[r["subject"]])}</div>'
            f'<h3><a href="{escape(r["url"])}" rel="noopener">{escape(r["title"])}</a></h3>'
            f'<p class="np-deck">{escape(r["about"])}</p>'
            f'<p class="np-by">The paper: <a href="{escape(r["link"])}" rel="noopener">{escape(r["paper"])}</a></p>'
            f'<p class="np-by">{escape(r["source"])} · {_day(r["date"])}</p></article>')


def _front(rows: list[dict]) -> str:
    """The papers as a newspaper page: the newest story leads across the top, the rest in columns, newest first."""
    if not rows:
        return ""
    return ('<section class="np"><div class="np-mast"><span>The papers in the news</span>'
            f'<span>Since {_day(SINCE)} · {_plural(len(rows), "paper")}</span></div>'
            f'{_clip(rows[0], lead=True)}<div class="np-cols">{"".join(_clip(r) for r in rows[1:])}</div></section>\n')


def _limits(rows: list[dict], read: int) -> str:
    """About these counts, as a small table: what each count is made of."""
    from collections import Counter
    top, top_n = (Counter(r["source"] for r in rows).most_common(1) or [("", 0)])[0]
    notes = [
        ("Papers in the news", f"Stories since {_day(SINCE)} from the outlets we read, each checked by hand and put "
         "under one subject."),
        ("Papers we read", f"The {read:,} new papers from arXiv's AI sections and Hugging Face's daily list, counted "
         "by the words in their titles, so one can count under several subjects, or none."),
        *([("Outlets", f"{top_n} of the {len(rows)} stories are from {top}.")] if rows and top_n * 2 > len(rows) else []),
        ("Not counted", "Stories about a company page, blog post, poll or report, and stories whose paper we couldn't "
         "find or check."),
    ]
    body = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in notes)
    return f'<section><h2>About these counts</h2>\n<table class="mt pn-notes"><tbody>{body}</tbody></table></section>\n'


def page_body(rows: list[dict], read_by: dict[str, int], read: int) -> str:
    """The page under the masthead: the papers in the news by subject next to the papers we read, a chapter per
    subject with its papers, and what the counts are made of. Every number is worked out from the rows."""
    groups = {k: [r for r in rows if r["subject"] == k] for k in SUBJECTS}
    order = sorted(SUBJECTS, key=lambda k: (-len(groups[k]), -read_by.get(k, 0)))
    def ours(k: str) -> str:
        r = read_by.get(k)
        if r is None:
            return '<span class="pn-pc">Not a Research subject</span>'
        return f'<b>{r:,}</b> of {read:,}<span class="pn-pc"> · {r / read:.0%}</span>'

    table = ('<table class="mt pn-subjects"><thead><tr><th>Subject</th><th>Papers in the news</th>'
             '<th>Papers we read</th></tr></thead><tbody>'
             + "".join(f'<tr><td>{escape(SUBJECTS[k])}</td><td class="pn-num"><b>{len(groups[k])}</b> of '
                       f'{len(rows)}</td><td class="pn-num">{ours(k)}</td></tr>'
                       for k in order if groups[k])
             + '</tbody></table>')
    intro = (f"{_plural(len(rows), 'research paper')} that news outlets we read reported on since {_day(SINCE)}, each "
             "checked by hand: the paper the story is about, its subject, and what it found in one plain sentence. Next "
             "to them, the papers we read ourselves in the same months. New papers are added once checked.")
    return ('<div class="ft jb pn">\n' + pages.feature_head(PATH, "Papers that made the news", QUESTION, escape(intro))
            + f'{_front(rows)}<div class="pn-foot"><section><h2>By the numbers</h2>\n{table}</section>\n'
            f'{_limits(rows, read)}</div></div>\n')


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write papers-in-the-news/. Returns its path."""
    rows = papers(cards)
    read_by, read = read_subjects(cards)
    (out / PATH).mkdir(parents=True, exist_ok=True)
    what = (f"{QUESTION} Research papers the news reported on since {_day(SINCE)}, each checked by hand, by subject, "
            "next to the papers we read.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Papers that made the news",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH / "index.html").write_text(
        pages.page("Papers that made the news · AI Pulse", what, PATH, page_body(rows, read_by, read), data,
                   pages.frame(conn, len(cards)), ("/research/", "Back to Research"),
                   "Headlines are the outlets' own, each linking to its story; paper titles link to the paper. New "
                   "papers are added once checked by hand."),
        encoding="utf-8")
    return [PATH]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a press/<day> branch: each paper it adds and the stories it left out; None when
    it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("CHECKED", "LEFT_OUT"))
    rows = [(r["paper"], SUBJECTS.get(r["subject"], r["subject"]), r["about"], u)
            for u, r in CHECKED.items() if u not in had["CHECKED"]]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("Papers in the news", f"paper{'s' * (len(rows) != 1)}", branch,
                        ("Paper", "Subject", "What it found", "Story"), rows, dropped)
