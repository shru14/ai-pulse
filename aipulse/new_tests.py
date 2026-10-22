"""New tests for AI (new-tests-for-ai/): each new benchmark in the papers we read, what it tests in one plain line, and
the best result the paper reports, with the model that got it where the paper names one, by Research subject. What
are researchers testing AI on, and how far short do the best models fall?

Every row in TESTS is a Research paper read by hand: a paper counts when its main point is a new test that scores AI
models other than the authors' own. Papers that mainly present a new model, a training method or a tool for building
tests are LEFT_OUT, with why. The plain line and the best result are written from the paper's whole abstract (fetched
from arXiv, not the stored summary) when the row is checked, by Claude as the glossary's words are; the owner approves.
A best result is the abstract's own number and model; a percentage is kept (for the score line) only when the abstract
gives the top score as a percentage or out of 100.

Each row shows its paper's code and demo links (code_links). A test a later paper beat, on the same measure, gets a
"Beaten" note from BEATEN, checked by hand from the later paper's whole abstract; beat_candidates() lists later papers
that name a test (`python -m aipulse tests-beaten`).

The sample starts on SINCE. Research papers after CHECKED_TO whose title names a benchmark are candidates()
(`python -m aipulse tests`). Linked from Research's strip on the front page.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

from . import code_links, kind_pages, pages, rss

PATH = "new-tests-for-ai/"
SINCE = "2026-07-17"
CHECKED_TO = "2026-10-22"
QUESTION = "What are researchers testing AI on, and how far short do the best models fall?"
# the Research stream's subjects (kind_pages.SUBJECTS), without "Benchmarks and evaluation": every row is one
SUBJECTS = {k: label for k, (label, _, _) in kind_pages.SUBJECTS.items() if k != "benchmarks"}
# a title that may present a benchmark: the Research pages' own rule for Benchmarks, less "evaluat" (too broad)
BENCHY = re.compile(r"bench(?:mark)?(?:s|ing)?\b|leaderboard|\barena\b", re.I)

# By the paper's address as the Research card gives it: (the test's name, its subject, what it tests in one plain line,
#  the best result the abstract reports, the model that got it as the abstract names it ("" when it names none), the top
#  score as a percentage when the abstract gives one (None otherwise))
TESTS: dict[str, tuple[str, str, str, str, str, float | None]] = {
    "https://arxiv.org/abs/2610.28679": (
        "VerifierBench", "agents",
        "Whether models can write the checking code that tells if an AI agent has really finished a task.",
        "Scores run from 10.6 to 62.1 (normalized balanced accuracy) across 19 models", "", None),
    "https://arxiv.org/abs/2610.29968": (
        "CulturalRiddles", "language-models",
        "Models solving original riddles written by people in 62 cultures and 51 languages.",
        "Even frontier models reach at most 22% accuracy in some communities", "", None),
    "https://arxiv.org/abs/2610.21397": (
        "Watts If? (DCBench-440)", "language-models",
        "Whether models can reason about what each early choice in planning an AI data centre (power, cooling, site) "
        "rules out.", "71.5% on its written-answer questions; only open-weight models were tested", "", 71.5),
    "https://arxiv.org/abs/2610.19005": (
        "CyberArena", "safety",
        "AI agents attacking and defending live computer systems against each other, round after round.",
        "No single score: it ranks 12 agents over 466 matches", "", None),
    "https://arxiv.org/abs/2610.19159": (
        "Into the Unknown", "science",
        "Whether AI agents can write a follow-up paper on an open science problem set by national-lab scientists.",
        "None of 135 papers met every condition; 114 failed the honesty check", "", 0.0),
    "https://arxiv.org/abs/2610.18092": (
        "LifeSearch", "agents",
        "Deep-research agents on 203 real everyday and work questions, in Chinese and English.",
        "63.4%", "GPT-5.6 Sol", 63.4),
    "https://arxiv.org/abs/2610.19128": (
        "CLASHarness", "agents",
        "Computer-use agents when other agents feed them out-of-date or clashing information.",
        "Even frontier models fail over 58% of closing steps, such as releasing shared files", "", None),
    "https://arxiv.org/abs/2610.14766": (
        "Last Secure Code Benchmark", "safety",
        "Whether code written by coding agents is secure, not only working, across 7 programming languages.",
        "25.1% of tasks both working and secure", "Claude Fable 5", 25.1),
    "https://arxiv.org/abs/2610.12452": (
        "BrickBench", "agents",
        "Agents designing LEGO sets that can actually be built from real parts.",
        "Falls short of human designs", "", None),
    "https://arxiv.org/abs/2610.12458": (
        "OmniCapBench", "vision",
        "Models describing who and what is seen and heard in 786 videos.",
        "Good on short moments, weak over long stretches", "", None),
    "https://arxiv.org/abs/2610.06748": (
        "BazaarBench", "safety",
        "Whether AI agents trading for people in a simulated online marketplace stay honest.",
        "All 5 models tried to promise one item to several buyers", "", None),
    "https://arxiv.org/abs/2610.00492": (
        "EurekaBench", "science",
        "Agents running long experiments to find the rules behind data in six sciences.",
        "Beat human scientists at prediction, but fell well short on scientific insight", "", None),
    "https://arxiv.org/abs/2610.02202": (
        "ScholarCatalyst", "science",
        "Finding the earlier papers that would help a new research project, as the projects' own authors judged.",
        "Found 51% of the helpful papers in its top 20", "an agent built on Claude Fable 5.1", 51.0),
    "https://arxiv.org/abs/2609.40284": (
        "cua-speedrun", "agents",
        "How fast and cheaply computer-use agents finish tasks, on one standard setup.",
        "No single score; no open-weight model was among the best for speed, cost and results together", "", None),
    "https://arxiv.org/abs/2609.40325": (
        "WorldAuditBench", "vision",
        "Agents searching 3D worlds for errors such as floating objects or walls you can walk through.",
        "42.3%, against 83.4% for people", "", 42.3),
    "https://arxiv.org/abs/2609.37709": (
        "VIF-Bench", "vision",
        "Image generators following picture instructions (arrows, layouts, poses) with up to 7 reference images.",
        "Following instructions more closely came with more flaws in the image", "", None),
    "https://arxiv.org/abs/2609.35025": (
        "AutoDataBench", "agents",
        "Agents writing new training tasks good enough for a real data pipeline.",
        "No agent scored above 20 out of 100 in 45 minutes", "", None),
    "https://arxiv.org/abs/2609.28921v1": (
        "PFArena", "science",
        "Protein models, language models and agents suggesting changes to proteins.",
        "All struggle as the search grows and mutations stack up", "", None),
    "https://arxiv.org/abs/2609.30199": (
        "ExplorationBench", "science",
        "Discovering made-up rules in 'alien worlds' by experimenting, so recalling what a model already knows can't "
        "help.", "The strongest systems learned the new rules, but gains could stall or reverse", "", None),
    "https://arxiv.org/abs/2609.23980v1": (
        "MobileCybench", "safety",
        "Agents finding security holes in 13 Android apps; running it turned up 23 holes nobody had reported.",
        "53.8% of apps, posing as a malicious app without the source code", "OpenCode with GPT-5.6 Sol", 53.8),
    "https://arxiv.org/abs/2609.24308": (
        "HappyWorld-Bench", "robotics",
        "Whether worlds made by world models stay consistent as agents explore and change them.",
        "70.14% placement accuracy, the best of the spatial models", "", 70.14),
    "https://arxiv.org/abs/2609.22069": (
        "OmniVBench", "vision",
        "Making videos from many reference images: people, objects, scenes and styles.",
        "Results vary widely between models and tasks", "", None),
    "https://arxiv.org/abs/2609.20794v1": (
        "PosteriorBench", "science",
        "Whether AI solvers for physics problems find every answer that fits, not only one.",
        "Large gaps across current solvers", "", None),
    "https://arxiv.org/abs/2609.20886": (
        "BI-Bench", "agents",
        "Answering business questions from raw company data, end to end, as people do in Power BI or Tableau.",
        "Frontier models below 50%", "", None),
    "https://arxiv.org/abs/2609.16443v1": (
        "Neverwhere", "robotics",
        "Robot parkour controllers in more than 60 photo-realistic copies of real places.",
        "Controllers trained on few scenes did worse in new ones", "", None),
    "https://arxiv.org/abs/2609.16090v1": (
        "MUUNRiver-Bench", "speech",
        "Finding music by instruction: a cover, the same voice, a new style.",
        "Sound-based and text-based models favour different matches", "", None),
    "https://arxiv.org/abs/2609.14992v1": (
        "MTAC-IFBench", "agents",
        "Coding agents following instructions over long sessions: about 7 turns and 91 rules each.",
        "Agents get worse the longer the session runs", "", None),
    "https://arxiv.org/abs/2609.10226": (
        "Φ-Bench", "agents",
        "Models doing real engineering on the code that trains and runs language models.",
        "36.53%", "Claude Opus 5", 36.53),
    "https://arxiv.org/abs/2609.05141v1": (
        "SciDocBench", "science",
        "Reading scientific papers: finding evidence in text, figures, tables and equations.",
        "62.6 out of 100", "Claude Opus 5", 62.6),
    "https://arxiv.org/abs/2609.05405": (
        "WearableQA", "science",
        "Health questions about 200 real people's fitness-tracker data and blood tests.",
        "72.9%, where guessing gets 10%", "", 72.9),
    "https://arxiv.org/abs/2609.04280v2": (
        "EvoHarnessBench", "agents",
        "Whether agents keep their skills as the tools, skills and helper agents around them change.",
        "Adding tools can make agents fail tasks they used to solve", "", None),
    "https://arxiv.org/abs/2609.00646": (
        "DramaChain Bench", "vision",
        "Every step of making short dramas, from the script to finished episodes.",
        "Flaws early on carry through to the final episode", "", None),
    "https://arxiv.org/abs/2608.30730": (
        "E-Commerce Bench", "agents",
        "Agents running online stores for a simulated year: buying stock, pricing, selling and handling returns.",
        "Grew 100,000 into 1,431,425, but came 16th of 18 at avoiding fraud", "GPT-5.6 Sol", None),
    "https://arxiv.org/abs/2608.29834v1": (
        "RepoRef", "agents",
        "Agents working out what a remark like 'the fix discussed yesterday' points to in developer chats.",
        "67.0% resolved", "", 67.0),
    "https://arxiv.org/abs/2608.23475v1": (
        "StrategyBench", "language-models",
        "Whether models can write down the rule behind a few examples, then use it.",
        "How much it helps depends a lot on the kind of task", "", None),
    "https://arxiv.org/abs/2608.23035": (
        "MobilePA-Bench", "agents",
        "Phone-assistant agents planning tasks and using 212 app tools.",
        "Scores drop sharply under strict tool order, permission limits or errors", "", None),
    "https://arxiv.org/abs/2608.21833": (
        "GameXpert-Bench", "agents",
        "Coding agents building, fixing and improving games.",
        "Better at making playable games than at finding their bugs", "", None),
    "https://arxiv.org/abs/2608.19741": (
        "Thinkingbox-bench", "agents",
        "Agents doing business workflows (retail, insurance, IT help) correctly every time, not just once.",
        "66.50% on the first try, 47.53% on all of 20 tries", "Claude Opus 5", 66.5),
    "https://arxiv.org/abs/2608.17800": (
        "StartupBench", "agents",
        "Agents doing the work that real AI startup products are used for.",
        "About 30% of tasks completed", "", 30.0),
    "https://arxiv.org/abs/2608.16344v4": (
        "IndicQE-APE", "language-models",
        "Judging and fixing machine translation between English and Indian languages.",
        "The unedited translation beat every fixing system on 3 of 4 language pairs", "", None),
    "https://arxiv.org/abs/2608.12781": (
        "PatternEval", "vision",
        "Answers to questions about images: leaked reasoning, repetition, contradictions.",
        "These failures are common, more so with thinking turned off", "", None),
    "https://arxiv.org/abs/2608.14546": (
        "CPI-Bench", "vision",
        "Image-editing models on real tasks: several images at once and instructions that need reasoning.",
        "Its ranking of models is the closest to people's own votes", "", None),
    "https://arxiv.org/abs/2608.12593v1": (
        "DiG-bench", "agents",
        "Discovering the hidden rules of 70 games by playing them.",
        "The hardest games still challenge the best models; people solved every game on their first try", "", None),
    "https://arxiv.org/abs/2608.10916v1": (
        "FaithformBench", "language-models",
        "Whether tools that turn maths reasoning into formal proofs keep wrong steps wrong.",
        "Many 'silently correct' wrong steps into provable ones", "", None),
    "https://arxiv.org/abs/2608.09802": (
        "SWE-Bench ProMax", "agents",
        "Coding agents making large changes across many files, in 7 programming languages.",
        "41.2% solved", "", 41.2),
    "https://arxiv.org/abs/2608.08621": (
        "Business Arena", "agents",
        "Agents running a cross-border shop: buying from suppliers and selling to buyers.",
        "Even the best model fell behind strategies designed by people", "", None),
    "https://arxiv.org/abs/2608.07004v1": (
        "CoDyControlBench", "science",
        "Models designing controllers for machines with many moving parts.",
        "94.8% of designs worked", "GPT (version not named)", 94.8),
    "https://arxiv.org/abs/2608.05747": (
        "GST-Bench", "vision",
        "Whether models can map a whole space from a long video.",
        "42.68, against 79.08 for people", "", 42.68),
    "https://arxiv.org/abs/2608.05139v1": (
        "Skill²-Bench", "language-models",
        "Long tasks that switch between different reasoning skills, such as maths then planning.",
        "Accuracy falls as the switches get harder", "", None),
    "https://arxiv.org/abs/2608.03569v1": (
        "Formula 1 and Magic: The Gathering", "science",
        "AI 'scientists' coming up with real new ideas: 2026 Formula 1 car designs and Magic: The Gathering decks.",
        "Matched 10 of 40 real Formula 1 innovations", "GPT-5.2", None),
    "https://arxiv.org/abs/2607.28956": (
        "MerchantBench", "agents",
        "Agents running an online shop for a simulated year, order by order.",
        "Ended with 27.3% of the money people did", "", None),
    "https://arxiv.org/abs/2607.26791": (
        "SecRespond", "safety",
        "Agents investigating a hacked computer and planning the clean-up.",
        "No model fully found and fixed any of the 10 hacked machines", "", None),
    "https://arxiv.org/abs/2607.25151v1": (
        "HiEviDR-Bench", "agents",
        "Whether deep-research answers are built on the right evidence.",
        "Reports read well, but citations and claims are weak", "", None),
    "https://arxiv.org/abs/2607.24957": (
        "PerceptionBench", "vision",
        "Basic seeing, one skill per question, in 3,000 questions.",
        "No model reaches 60%", "", None),
    "https://arxiv.org/abs/2607.23808v1": (
        "Indic DiarBench", "speech",
        "Who spoke when, and what they said, in all 22 scheduled languages of India.",
        "A first baseline for commercial speech systems; no score in the abstract", "", None),
    "https://arxiv.org/abs/2607.20911": (
        "Tencent WorkBuddy Bench", "agents",
        "Coding agents on real work: code, websites, office tasks and security.",
        "No overall score, by design: each part is scored differently", "", None),
    "https://arxiv.org/abs/2607.19322": (
        "GAMUT", "vision",
        "Whether long answers about photos from wearable cameras include every fact they should.",
        "58.7%", "Gemini 3.1 Pro", 58.7),
    "https://arxiv.org/abs/2607.19407v1": (
        "ITPEval", "language-models",
        "Translating formal maths proofs and statements between four proof-checking systems (Lean 4, Rocq, Isabelle, "
        "HOL Light); 6,848 theorems.",
        "Statement translation peaks at 29.1% pass@1 and proof translation at 10.5%", "", None),
    "https://arxiv.org/abs/2607.05783v1": (
        "LanEvil++", "robotics",
        "Lane-detection and driving vision-language models facing shadows, reflections, tire marks and 11 other road "
        "illusions in simulated scenes.",
        "Illusions cut lane-detection accuracy by 5.27% on average; shadows hurt most, by up to 7.20%", "", None),
    "https://arxiv.org/abs/2607.04293v1": (
        "CausalGame", "agents",
        "Agents designing experiments in 14 interactive games with hidden biases and confounders, to tell cause from "
        "correlation.",
        "Best model reaches 68.0% survival against 78-85% for the analytical best; 5-7% of sessions earn credit on "
        "causal reasoning", "", None),
    "https://arxiv.org/abs/2606.31179": (
        "HealthAgentBench", "agents",
        "Agents carrying out 54 end-to-end healthcare tasks, such as modelling patient records and medical imaging, "
        "each in its own environment.",
        "About 42% task success for the strongest agent", "Codex GPT-5.5", None),
    "https://arxiv.org/abs/2606.31154v1": (
        "PPT-Eval", "agents",
        "Computer-use agents creating and editing PowerPoint slides (120 tasks), graded by rubrics with partial credit.",
        "Strong models such as Claude-4.5-Opus reach only a 45% success rate", "", None),
    "https://arxiv.org/abs/2607.08964": (
        "Long-Horizon-Terminal-Bench", "agents",
        "Agents on 46 long terminal tasks that take hundreds of steps, with partial credit for progress.",
        "15.2% pass@1 at a 0.95 partial-reward threshold and 10.9% at a perfect score for the strongest model", "",
        None),
    "https://arxiv.org/abs/2606.29887": (
        "SafePyramid", "safety",
        "Whether safety guardrails can spot rule violations in conversations from policies given in the prompt "
        "(1,000 conversations, 10 domains).",
        "The best model finds every violated rule in only 54.0%, 35.3% and 12.9% of cases on the three levels",
        "GPT-5.5", None),
    "https://arxiv.org/abs/2606.30026v1": (
        "MuseBench", "vision",
        "Models explaining why film, painting, stage and game makers made their creative choices (4,016 questions).",
        "48.29% accuracy for the best model, against 87.18% for human experts", "", 48.29),
    "https://arxiv.org/abs/2606.27669": (
        "DiscoBench", "agents",
        "Search agents noticing a vague or wrong request and asking the user a clarifying question (211 samples).",
        "No top score in the abstract; searching again instead of asking often does worse than guessing", "", None),
    "https://arxiv.org/abs/2606.28480": (
        "TUA-Bench", "agents",
        "Agents working in a terminal on 120 everyday and scientific tasks, from editing documents to email and "
        "specialist software.",
        "65.8% overall", "Claude Code with Claude Opus 4.8 max reasoning effort", 65.8),
    "https://arxiv.org/abs/2606.24950v1": (
        "MacroLens", "language-models",
        "Forecasting prices, valuing companies and judging event effects for 4,416 small U.S. stocks from prices, "
        "filings, news and economic data.",
        "No result in the abstract", "", None),
    "https://arxiv.org/abs/2606.19157v2": (
        "IndicContextEval", "speech",
        "Whether audio models use hints such as domain descriptions and word lists to transcribe speech in 8 Indian "
        "languages.",
        "No top score in the abstract; models differ substantially in how they use context", "", None),
    "https://arxiv.org/abs/2606.16748v1": (
        "MyPCBench", "agents",
        "Computer-use agents acting as a personal assistant on a simulated desktop with 17 web apps and one persona "
        "(184 tasks).",
        "55.4% of tasks fully solved, the only model above 50%", "Claude Opus 4.6", 55.4),
    "https://arxiv.org/abs/2606.14383": (
        "IndustryBench-MIPU", "vision",
        "Reading technical specifications off several photos of industrial products (4,559 products).",
        "Precision of 86-94%, but the best recovers only 49.9% of product-level attributes", "", None),
    "https://arxiv.org/abs/2606.13802": (
        "Spreadsheet next-action benchmark", "agents",
        "Predicting a user's next step in a spreadsheet from the steps so far (52 sequences, 12K actions).",
        "No result in the abstract", "", None),
    "https://arxiv.org/abs/2606.13385v2": (
        "StakeBench", "safety",
        "Online-shopping web agents tricked by hidden instructions on web pages, by who is harmed (264 attacks).",
        "No attack goal is reliably resisted by current agents", "", None),
    "https://arxiv.org/abs/2606.11063v1": (
        "CIAware-Bench", "safety",
        "Whether a model can tell its own actions from ones a safety monitor has replaced.",
        "AUROC of 0.90 on essay writing, 0.91 on BigCodeBench, 0.86 on Bash Arena and 0.77 on SHADE-Arena",
        "GPT-6 Astra", None),
    "https://arxiv.org/abs/2606.09426": (
        "WeaveBench", "agents",
        "Computer-use agents mixing screen control, command line and code on 114 long real-world tasks.",
        "41.2% pass rate for the best model and runtime pairing", "", 41.2),
    "https://arxiv.org/abs/2606.09764v1": (
        "iOSWorld", "agents",
        "Phone agents using a person's own data across 26 simulated iOS apps (133 tasks).",
        "52% overall for the best setup, but only 37% on tasks spanning several apps", "", 52.0),
    "https://arxiv.org/abs/2606.08340v1": (
        "alem", "agents",
        "Teams of language-model agents coordinating in a long survival world of exploring, crafting, trading and "
        "combat.",
        "Models average only about 6% normalised return", "", None),
    "https://arxiv.org/abs/2606.05806": (
        "ToolMaze", "agents",
        "Agents recovering when the tools they call fail or return wrong results.",
        "Recovery rate falls by around 37% when failures are silent", "", None),
    "https://arxiv.org/abs/2606.01804": (
        "SpeechEditBench", "speech",
        "Speech models changing one thing about a recording on instruction (seven editing tasks, English and Chinese) "
        "while keeping the rest.",
        "No single model does well on every kind of edit; combined edits are hard for all", "", None),
    "https://arxiv.org/abs/2606.04460v2": (
        "CyberGym-E2E", "safety",
        "Agents finding real software vulnerabilities, writing exploits and patching them (920 vulnerabilities in 139 "
        "projects).",
        "No result in the abstract", "", None),
    "https://arxiv.org/abs/2606.03920v1": (
        "VSTAT", "vision",
        "Models following objects and events through a whole video, with questions no single frame can answer.",
        "Far below humans and only modestly above guessing from answer patterns", "", None),
    "https://arxiv.org/abs/2606.04184v2": (
        "GroupToM-Bench", "vision",
        "Models reading what groups of people believe and want, and how that leads to what the group does.",
        "A gap between current models and humans", "", None),
    "https://arxiv.org/abs/2606.03348v1": (
        "SynCred-Bench", "safety",
        "Spotting AI-made fake images that look credible, with realistic embedded text and layouts (600 images).",
        "Commercial detection services reach 57.6% at a 5% false-alarm rate; 15 multimodal models reach 10.5%", "",
        None),
    "https://arxiv.org/abs/2606.01057": (
        "3DCodeBench", "vision",
        "Vision-language models writing code that builds 3D objects in modeling software from text and image prompts.",
        "Most failures come from wrong software commands, and even working results often have floating or disconnected "
        "parts", "", None),
    "https://arxiv.org/abs/2605.30434": (
        "LongDS-Bench", "agents",
        "Agents carrying a data analysis through many turns while the analysis keeps changing (68 tasks, 2,225 turns).",
        "48.45% average accuracy", "", 48.45),
    "https://arxiv.org/abs/2605.29059v1": (
        "SCDBench", "language-models",
        "Whether models can turn smart-contract machine code back into source code that behaves the same (600 contracts).",
        "The best model perfectly decompiles only 42 of 600 contracts", "", None),
    "https://arxiv.org/abs/2605.27141": (
        "VitaBench 2.0", "agents",
        "Agents learning and using a person's changing preferences from long daily histories, and asking when "
        "information is missing.",
        "Personalization remains highly challenging even for the best models", "", None),
    "https://arxiv.org/abs/2605.25874": (
        "WBench", "robotics",
        "Interactive video world models over several turns: video quality, following the setting and the instructions, "
        "consistency and physics.",
        "No single model performs strongly across all dimensions", "", None),
    "https://arxiv.org/abs/2605.26329v1": (
        "JobBench", "agents",
        "Agents doing the work experts most want to hand over: 130 tasks across 35 occupations.",
        "45.9%", "Claude Opus 4.7 under Claude Code", 45.9),
    "https://arxiv.org/abs/2605.23215": (
        "FastKernels", "agents",
        "Agents writing GPU code that is fast and correct inside real AI models, not only on its own.",
        "Speedups of 1.6-6.6x on single kernels shrink to at most 1.25x end to end; only 20% of winning kernel sets "
        "run correctly as they are", "", None),
    "https://arxiv.org/abs/2605.22080v2": (
        "JMed48k", "science",
        "Vision-language models answering Japanese medical licensing exam questions, with and without the images.",
        "No top score in the abstract; models gain from images, medical-specific ones barely use them", "", None),
    "https://arxiv.org/abs/2605.20183": (
        "MSAVBench", "vision",
        "Models making videos of up to 15 shots with sound, judged on video, audio, shots and reference images.",
        "Current systems still struggle with director-level control and fine-grained sound-picture sync", "", None),
    "https://arxiv.org/abs/2605.18746v2": (
        "ESI-Bench", "robotics",
        "Whether models can move and handle things in a simulated home to gather what they need to answer spatial "
        "questions.",
        "Most failures come from poor choices of action, not weak seeing", "", None),
    "https://arxiv.org/abs/2605.16679v2": (
        "CHI-Bench (χ-Bench)", "agents",
        "Agents running long healthcare office workflows (prior approvals, insurance reviews, care management) in a "
        "simulated set of 20 apps.",
        "28.0% of tasks resolved by the best agent", "", 28.0),
    "https://arxiv.org/abs/2605.14906": (
        "MemLens", "vision",
        "Models remembering text and pictures across long conversations over many sessions (789 questions).",
        "Multi-session reasoning caps most systems below 30%", "", None),
    "https://arxiv.org/abs/2605.11633v1": (
        "DORA", "agents",
        "Agents handling disaster response with satellite images, maps and 108 tools: damage, evacuation plans, reports.",
        "No top score in the abstract; the gap to expert steps widens from 7% to 56% on long pipelines", "", None),
    "https://arxiv.org/abs/2605.10267": (
        "IndustryBench", "language-models",
        "Answering industrial buying questions in Chinese without breaking rules from national standards.",
        "2.083 on a 0-3 scale for the best system", "", None),
    "https://arxiv.org/abs/2605.10912v1": (
        "WildClawBench", "agents",
        "Agents doing 60 real long tasks, about 8 minutes each, inside real command-line agent tools.",
        "62.2% overall under OpenClaw; every other model below 60%", "Claude Opus 4.7", 62.2),
    "https://arxiv.org/abs/2605.09874v2": (
        "EgoMemReason", "vision",
        "Reasoning over a week of first-person video: remembering objects, events and habits (500 questions).",
        "39.6% overall accuracy", "", 39.6),
    "https://arxiv.org/abs/2605.08614": (
        "DiagnosticIQ", "language-models",
        "Picking the right maintenance action for an industrial sensor rule, in 6,690 multiple-choice questions.",
        "Top three models within one point; every model loses 13-60% of its accuracy when distractor answers are added",
        "", None),
    "https://arxiv.org/abs/2605.09063v3": (
        "Soohak", "language-models",
        "Research-level maths problems written from scratch by 64 mathematicians, and spotting ill-posed ones.",
        "30.4% on its Challenge subset; no model exceeds 50% at spotting ill-posed problems", "Gemini-3-Pro", 30.4),
    "https://arxiv.org/abs/2605.08678v3": (
        "MLS-Bench", "agents",
        "Whether AI agents can invent new machine-learning methods that work across settings and scales (140 tasks).",
        "Agents remain far from reliably beating human-designed methods", "", None),
    "https://arxiv.org/abs/2605.03546v1": (
        "ProgramBench", "agents",
        "Rebuilding real programs, such as FFmpeg, SQLite and the PHP interpreter, from the program and its docs alone.",
        "No model fully solves any task; the best passes 95% of tests on only 3% of tasks", "", None),
    "https://arxiv.org/abs/2605.01809v1": (
        "TMD-Bench", "vision",
        "Models making music and dance together from text, judged on quality, following the prompt and rhythm match.",
        "Veo 3 and Sora 2 make high-quality music and video, but rhythmic coupling is less consistent", "", None),
    "https://arxiv.org/abs/2604.24964v1": (
        "Odysseys", "agents",
        "Web agents on 200 long tasks across many sites on the live internet, graded by rubrics.",
        "44.5% success rate for the strongest models", "", 44.5),
    "https://arxiv.org/abs/2604.20157v1": (
        "HumanScore", "vision",
        "How faithfully AI video generators show human bodies and movement, on six measures.",
        "No top score; videos look plausible but show jitter, impossible poses and motion drift", "", None),
    "https://arxiv.org/abs/2604.19667": (
        "Chat2Workflow", "agents",
        "Models building ready-to-run visual workflows for platforms such as Dify and Coze from plain-language requests.",
        "Models grasp the goal but struggle to build correct, stable, runnable workflows", "", None),
    "https://arxiv.org/abs/2604.19151v4": (
        "Voice of India", "speech",
        "Speech recognition on real unscripted phone calls in 15 Indian languages.",
        "No score in the abstract; accuracy differs by district, audio quality, speaking rate and device", "", None),
    "https://arxiv.org/abs/2604.18240": (
        "AJ-Bench", "agents",
        "Agents acting as judges: using search, data and screens to check whether another agent's work is right.",
        "Beat plain language-model judges, but big open challenges remain", "", None),
    "https://arxiv.org/abs/2604.17969v3": (
        "E3VS-Bench", "robotics",
        "Agents moving a camera freely through 99 3D scenes to answer questions that need a look from the right angle.",
        "All models fall well short of people", "", None),
    "https://arxiv.org/abs/2604.18584v2": (
        "MathNet", "language-models",
        "Olympiad maths problems from 47 countries in 17 languages: solving them and finding matching problems.",
        "78.4% solving unaided; the highest scores came with retrieval help", "Gemini-3.1-Pro", None),
    "https://arxiv.org/abs/2604.17283v1": (
        "HorizonBench", "language-models",
        "Tracking how a user's preferences change over 6 months of chat, about 4,300 turns.",
        "52.8%, where chance is 20%", "", 52.8),
    "https://arxiv.org/abs/2610.23986": (
        "BlenderWorld", "agents",
        "Whether AI agents can build or edit 3D scenes in Blender from text, image, video or written references.",
        "GPT-6-Astra has the highest overall fused score, 79.9, ahead of Opus-5 (73.0) and GPT-5.6-Sol (67.7)",
        "GPT-6-Astra", None),
}
# papers checked by hand and left out, with why, so they aren't checked again
LEFT_OUT: dict[str, str] = {
    "https://arxiv.org/abs/2610.26081": "mainly a new model (DeOverlay), with a benchmark",
    "https://arxiv.org/abs/2610.13644": "SelectArena compares statistics methods for picking data columns, not AI models",
    "https://arxiv.org/abs/2610.13947": "mainly a new 3D-generation system (Artisan)",
    "https://arxiv.org/abs/2610.10619": "TestJack is a way to check other tests' results",
    "https://arxiv.org/abs/2610.05140": "AutoSciBench is a tool that builds tests",
    "https://arxiv.org/abs/2609.33295": "TraceDance is a tool that builds tests",
    "https://arxiv.org/abs/2609.21465": "mainly a data engine and training method (OmniVChat)",
    "https://arxiv.org/abs/2608.29481v1": "tests the authors' own simulators (SIC-Agents)",
    "https://arxiv.org/abs/2608.05850v2": "mainly a new model (MameLoshnLM)",
    "https://arxiv.org/abs/2607.05155": "mainly a scaling-law finding about how agents learn from experience (EdgeBench)",
    "https://arxiv.org/abs/2606.19704": "a position paper on how to rank agents, not a new test",
    "https://arxiv.org/abs/2606.09380": "Reasoning Arena is a training method, not a test",
    "https://arxiv.org/abs/2605.30188v2": "CalArena compares statistics methods for calibrating predictions, not AI models",
    "https://arxiv.org/abs/2605.28398": "HRBench compares methods for switching thinking modes, not AI models",
    "https://arxiv.org/abs/2605.28819v1": "PEFT-Arena compares finetuning methods, not AI models",
    "https://arxiv.org/abs/2605.23271": "EvalVerse is mainly a way to judge videos (an expert-tuned judge model)",
    "https://arxiv.org/abs/2605.20873": "PlanningBench is mainly a tool that generates planning data for tests and training",
    "https://arxiv.org/abs/2605.12501": "mainly a data-synthesis method and a new model (Phi-Ground-Any-4B), with a benchmark",
    "https://arxiv.org/abs/2605.12292v1": "STRABLE compares tabular learning methods, not AI models",
    "https://arxiv.org/abs/2605.12673v1": "BenchJack is a way to check other tests",
    "https://arxiv.org/abs/2605.10616v1": "MulTaBench compares tabular learning methods and the authors' tuning, not AI models",
    "https://arxiv.org/abs/2605.11209v1": "mainly a sampling method for measuring rare failures, not a new test",
    "https://arxiv.org/abs/2605.08518": "a retrospective on a competition, not a new test",
    "https://arxiv.org/abs/2604.19071v1": "mainly a way to grade writing (Tree-of-Writing)",
    "https://arxiv.org/abs/2604.17761": "an interpretability method for analysing failures, not a new test",
}
# Tests a later paper beat, by the test's address in TESTS: (the later paper's address, the day arXiv announced it, what
# it reports in its abstract's own numbers and words, and who got it as the abstract names them). A test counts as beaten
# only when the later abstract gives a better result on the same measure than the row's best result; gains over the
# later paper's own baseline, other measures or other versions of the test don't count. Checked to BEATS_CHECKED_TO.
BEATEN: dict[str, tuple[str, str, str, str]] = {
    "https://arxiv.org/abs/2608.12593v1": (
        "https://arxiv.org/abs/2609.39140", "2026-09-30", "Solves 100% of the public DiG-bench games",
        "the Schema agent harness"),
    "https://arxiv.org/abs/2606.09426": (
        "https://arxiv.org/abs/2608.01964", "2026-08-03", "80.7% on WeaveBench",
        "Qwen 3.7-Plus in the LongHorizon-Harness agent harness"),
}
BEATS_CHECKED_TO = "2026-10-21"
_ATOM = {"a": "http://www.w3.org/2005/Atom"}
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def tests(cards: list[dict]) -> list[dict]:
    """The rows in TESTS whose paper we have, newest first, each with its paper (title, date, url)."""
    by_url = {c["url"]: c for c in cards}
    out = [{"url": url, "name": n, "subject": s, "tests": t, "best": b, "model": m, "pct": p,
            "paper": by_url[url]["title"].strip(), "date": by_url[url]["date"][:10], "beaten": BEATEN.get(url)}
           for url, (n, s, t, b, m, p) in TESTS.items() if url in by_url]
    return sorted(out, key=lambda r: r["date"], reverse=True)


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Research papers after CHECKED_TO (or `since`) whose title names a benchmark and that are neither in TESTS nor
    LEFT_OUT, newest first."""
    after = max(since, CHECKED_TO)
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["category"] == "research" and c["date"][:10] > after and BENCHY.search(c["title"])
            and c["url"] not in TESTS and c["url"] not in LEFT_OUT]


def _key(name: str) -> str:
    """The words to look for in later abstracts: the test's name without what's in brackets."""
    return re.sub(r"\s*\(.*?\)", "", name).strip()


def beat_candidates(since: str = BEATS_CHECKED_TO, fetcher=None) -> list[dict]:
    """Papers on arXiv announced after `since` whose abstract names one of TESTS (not beaten yet, its own paper
    excluded), with the sentences that name it: to check by hand for a better result on the same measure. Ten names
    a request, a request every 3.5 s, as arXiv asks."""
    import time
    import xml.etree.ElementTree as ET
    from urllib.parse import urlencode
    from . import feeds
    fetcher = fetcher or feeds.fetch
    names = {_key(n): url for url, (n, *_) in TESTS.items() if url not in BEATEN}
    out = []
    keys = sorted(names)
    for i in range(0, len(keys), 10):
        if i:
            time.sleep(3.5)
        q = " OR ".join(f'abs:"{k}"' for k in keys[i:i + 10])
        xml = ET.fromstring(fetcher(f"{code_links.ARXIV_API}?" + urlencode(
            {"search_query": q, "max_results": 100, "sortBy": "submittedDate"})))
        for e in xml.findall("a:entry", _ATOM):
            day, text = e.findtext("a:published", "", _ATOM)[:10], " ".join(e.findtext("a:summary", "", _ATOM).split())
            aid = code_links.arxiv_id(e.findtext("a:id", "", _ATOM))
            for k in keys[i:i + 10]:
                said = [x for x in re.split(r"(?<=[.!?])\s+", text) if k.lower() in x.lower()]
                if said and day > since and aid != code_links.arxiv_id(names[k]):
                    out.append({"test": k, "url": f"https://arxiv.org/abs/{aid}", "date": day,
                                "title": " ".join(e.findtext("a:title", "", _ATOM).split()), "said": said[:3]})
    return sorted(out, key=lambda c: (c["test"].lower(), c["date"]))


def _day(d: str) -> str:
    day = date.fromisoformat(d[:10])
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"


def _num(p: float) -> str:
    return f"{p:g}"


def _glance(rows: list[dict]) -> str:
    """Three big numbers, each saying what it counts."""
    scored = [r for r in rows if r["pct"] is not None]
    under = sum(r["pct"] < 50 for r in scored)
    top, top_n = Counter(r["subject"] for r in rows).most_common(1)[0]
    tiles = [(len(rows), f"new tests for AI in papers since {_day(SINCE)}", "#CC79A7"),
             (f"{under} of {len(scored)}", "tests that give a top score as a percentage, where the best model scored "
              "under half", "#E69F00"),
             (top_n, f"of them test {SUBJECTS[top].lower()}, the most of any subject", "#56B4E9")]
    body = "".join(f'<div class="iw-big" style="--c:{c}"><b>{n}</b><span>{escape(label)}</span></div>'
                   for n, label, c in tiles)
    return f'<section class="iw-glance"><h2>At a glance</h2>\n<div class="iw-bigs">{body}</div></section>\n'


def _scores(rows: list[dict]) -> str:
    """Each test that gives its top score as a percentage, lowest first: the score as a dot on a line from 0 to 100."""
    scored = sorted((r for r in rows if r["pct"] is not None), key=lambda r: (r["pct"], r["name"]))
    if not scored:
        return ""
    lines = "".join(
        f'<li><a href="{escape(r["url"])}" rel="noopener">{escape(r["name"])}</a>'
        f'<span class="nt-track" aria-hidden="true"><i style="left:{r["pct"]:.2f}%"></i></span>'
        f'<span class="nt-pct"><b>{_num(r["pct"])}</b>{" · " + escape(r["model"]) if r["model"] else ""}</span></li>'
        for r in scored)
    return ('<section><h2>The best score on each test</h2>\n<p class="nt-how">0 means nothing done right, 100 means '
            'every task done right. Each dot is the best score the paper reports; the model is named where the paper '
            f'names it.</p>\n<ol class="nt-scores">{lines}</ol></section>\n')


def _table(rows: list[dict], links: dict) -> str:
    """Every test, by subject (the most tests first), newest first within each, with its paper's code and demo
    links."""
    groups = {k: [r for r in rows if r["subject"] == k] for k in SUBJECTS}
    out = []
    for k in sorted((k for k in groups if groups[k]), key=lambda k: -len(groups[k])):
        body = "".join(
            f'<tr><td><a href="{escape(r["url"])}" rel="noopener" title="{escape(r["paper"])}">{escape(r["name"])}</a>'
            f'</td><td>{escape(r["tests"])}</td><td>{escape(r["best"])}'
            + (f'<small>{escape(r["model"])}</small>' if r["model"] else "")
            + (f'<small class="nt-beat">Beaten {_day(r["beaten"][1])}: <a href="{escape(r["beaten"][0])}" '
               f'rel="noopener">{escape(r["beaten"][2])}</a>, by {escape(r["beaten"][3])}</small>' if r["beaten"] else "")
            + f'</td><td class="cl">{code_links.html(code_links.of(links, r["url"]))}</td><td>{_day(r["date"])}</td></tr>'
            for r in groups[k])
        out.append(f'<h3>{escape(SUBJECTS[k])} <span class="nt-n">{_plural(len(groups[k]), "test")}</span></h3>\n'
                   '<table class="mt nt-table"><thead><tr><th>Test</th><th>What it tests</th>'
                   f'<th>Best result reported</th><th>Links</th><th>Paper</th></tr></thead><tbody>{body}</tbody></table>\n')
    return f'<section><h2>Every test, by subject</h2>\n{"".join(out)}</section>\n'


def _limits(rows: list[dict]) -> str:
    """About these counts, as a small table: what each count is made of."""
    notes = [
        ("New tests", f"Papers from arXiv's AI sections and Hugging Face's daily list since {_day(SINCE)} whose title "
         "names a benchmark, each read by hand. A paper counts when its main point is a new test that scores AI "
         "models other than the authors' own."),
        ("Left out", f"{_plural(len(LEFT_OUT), 'paper')} that mainly present a new model, a training method or a tool "
         "for building tests."),
        ("Best result", "The paper's own words and numbers, from its whole abstract. Each test is scored its own way, "
         "so a score is only comparable with others on the same test."),
        ("Subjects", "Set by hand, one per test, from the Research stream's subjects."),
        ("Links", "The links the authors give in the paper's abstract on arXiv, and the code and project page Hugging "
         "Face lists for it: Code (a code host), Data (a dataset), Try it (a demo in the browser), Site (the project's "
         "own page). Read again every week."),
        ("Beaten", f"{_plural(len(BEATEN), 'test')} where a later paper's abstract reports a better result on the same "
         "measure, checked by hand. Gains over a later paper's own starting point don't count."),
    ]
    body = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in notes)
    return f'<section><h2>About these counts</h2>\n<table class="mt pn-notes"><tbody>{body}</tbody></table></section>\n'


def page_body(rows: list[dict], links: dict | None = None) -> str:
    intro = (f"{_plural(len(rows), 'new test')} for AI in the research papers we read since {_day(SINCE)}, each read "
             "by hand: what it tests in one plain line, and the best result its paper reports, with the model that got "
             "it where the paper names one. New tests are added once checked.")
    return ('<div class="ft jb nt">\n' + pages.feature_head(PATH, "New tests for AI", QUESTION, escape(intro))
            + _glance(rows) + _scores(rows) + _table(rows, links or {}) + _limits(rows) + '</div>\n')


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write new-tests-for-ai/. Returns its path, or nothing when no checked paper is among the cards."""
    rows = tests(cards)
    if not rows:
        return []
    (out / PATH).mkdir(parents=True, exist_ok=True)
    what = (f"{QUESTION} New benchmarks in the AI research papers we read since {_day(SINCE)}, each checked by hand: "
            "what it tests and the best result its paper reports.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "New tests for AI",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH / "index.html").write_text(
        pages.page("New tests for AI · AI Pulse", what, PATH, page_body(rows, code_links.load(conn)), data, pages.frame(conn, len(cards)),
                   ("/research/", "Back to Research"),
                   "Test names link to their paper. New tests are added once checked by hand."),
        encoding="utf-8")
    return [PATH]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a tests/<day> branch: each test it adds and the papers it left out; None when it
    adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("TESTS", "LEFT_OUT", "BEATEN"))
    rows = [(n, SUBJECTS.get(s, s), t, f"{b} ({m})" if m else b, u)
            for u, (n, s, t, b, m, _) in TESTS.items() if u not in had["TESTS"]]
    rows += [(TESTS[u][0], "Beaten", f"{TESTS[u][3]} ({TESTS[u][4]})" if TESTS[u][4] else TESTS[u][3],
              f"{r} ({by}), {_day(d)}", p) for u, (p, d, r, by) in BEATEN.items() if p not in had["BEATEN"]]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("New tests for AI", f"test{'s' * (len(rows) != 1)}", branch,
                        ("Test", "Subject", "What it tests", "Best result", "Paper"), rows, dropped)
