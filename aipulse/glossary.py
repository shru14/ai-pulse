"""The glossary: plain-English meanings of the hard words in AI stories, written by hand (no AI, nothing fetched).

Each entry: the term, its group, a short definition and `match`, the ways stories write it (regular expressions
that work in both Python and the browser; `case` makes them case-sensitive, for acronyms like RAG or MoE).
The site marks the first few terms in each card's summary and lists them all behind the Glossary button;
build() adds how many recent stories mention each term, so the panel can show what's in the news this week.
`python -m aipulse glossary` lists short capitalised words that recent stories use often but the glossary
doesn't explain yet: candidates to write up by hand.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta

GROUPS = ["Models", "Training", "Agents & products", "Safety & security", "Chips & compute", "Law & policy",
          "Money & business", "Research", "Names"]

# (term, group, definition, patterns, case-sensitive)
_ENTRIES = [
    # ---- Models ------------------------------------------------------------------------------------------------
    ("LLM", "Models", "Large language model: an AI system trained on huge amounts of text to predict the next word, "
     "which lets it write, answer questions, summarise and code. ChatGPT, Claude and Gemini are built on LLMs.",
     [r"LLMs?", r"large language models?"], True),
    ("Small language model", "Models", "A language model small enough to run cheaply or on a phone or laptop, "
     "trading some ability for speed, cost and privacy.", [r"small language models?", r"SLMs?"], False),
    ("Foundation model", "Models", "A large model trained on broad data that many products are then built on, "
     "instead of training a new model for every task.", [r"foundation models?"], False),
    ("Frontier model", "Models", "One of the most capable AI models at a given time, usually from the biggest labs. "
     "Laws and safety rules often apply to these first.", [r"frontier(?:-| )(?:AI|models?|labs?)"], False),
    ("GPT", "Models", "Generative Pre-trained Transformer: the name of OpenAI's model family (GPT-5, GPT-6…), "
     "also used loosely for any chatbot model.", [r"GPT(?=-|\b)"], True),
    ("Multimodal", "Models", "Able to take in or produce more than one kind of data, such as text, images, audio "
     "and video, in the same model.", [r"multi-?modal", r"MLLMs?"], False),
    ("VLM", "Models", "Vision-language model: a model that understands pictures (or video) and text together, "
     "e.g. describing a photo or reading a chart.", [r"VLMs?", r"vision[- ]language models?"], True),
    ("VLA", "Models", "Vision-language-action model: a model that sees, reads an instruction and outputs actions, "
     "used to control robots.", [r"VLAs?", r"vision[- ]language[- ]action"], True),
    ("Reasoning model", "Models", "A model that works through a problem step by step before answering, spending "
     "more computing time to get harder questions right.", [r"reasoning models?", r"LRMs?"], False),
    ("World model", "Models", "A model that learns how an environment behaves (objects, physics, cause and effect) "
     "so it can predict what happens next; used for robots, games and video.", [r"world models?"], False),
    ("Diffusion model", "Models", "A type of model that creates images, video or audio by starting from random noise "
     "and removing it step by step until a picture appears.", [r"diffusion models?", r"diffusion transformers?"], False),
    ("Transformer", "Models", "The neural-network design behind almost all modern language models (the T in GPT). "
     "It looks at how every word relates to every other word.", [r"transformers?(?! robot)"], False),
    ("Attention", "Models", "The part of a transformer that decides which earlier words matter most for the next one. "
     "Much research is about making it faster for long texts.", [r"self-attention", r"attention (?:mechanism|layers?|heads?)",
                                                                  r"sparse attention", r"linear attention"], False),
    ("Parameters", "Models", "The numbers inside a model that are adjusted during training; a rough measure of size. "
     "\"70B\" means 70 billion parameters, \"1.6T\" 1.6 trillion.", [r"parameters?", r"(?<!\$)\b\d+(?:\.\d+)?[BT](?=\b)"], False),
    ("Mixture of Experts", "Models", "MoE: a model split into many smaller \"expert\" parts, with only a few switched on "
     "for each word. \"35B-A3B\" means 35 billion parameters in all, 3 billion active at a time: big but cheap to run.",
     [r"MoE", r"[Mm]ixture[- ]of[- ][Ee]xperts", r"A\d+(?:\.\d+)?B"], True),
    ("Dense model", "Models", "A model that uses all of its parameters for every word, unlike a mixture of experts.",
     [r"dense models?"], False),
    ("Token", "Models", "The small chunk of text a model reads and writes: a word or part of a word (about ¾ of an "
     "English word on average). Usage and prices are counted in tokens.", [r"tokens?"], False),
    ("Tokenizer", "Models", "The tool that cuts text into tokens before a model reads it.", [r"tokeni[sz]ers?"], False),
    ("Context window", "Models", "How much text (in tokens) a model can take in at once: its working memory for one "
     "conversation or document.", [r"context windows?", r"context lengths?"], False),
    ("Embedding", "Models", "A list of numbers that stands for the meaning of a word, sentence or image, so that "
     "similar things get similar numbers. Search and recommendation run on them.", [r"embeddings?"], False),
    ("Open-weight model", "Models", "A model whose trained parameters (its \"weights\") anyone can download and run. "
     "Not always fully open source: the training data and code may stay private.",
     [r"open[- ]weights?", r"open models?", r"model weights"], False),
    ("Open source", "Models", "Software (or a model) released with its code under a licence that lets anyone use, "
     "change and share it.", [r"open[- ]sourced?", r"Apache[- ]2\.0", r"MIT licen[cs]e"], False),
    ("Checkpoint", "Models", "A saved copy of a model at one point in its training, which can be released or trained "
     "further.", [r"checkpoints?"], False),
    ("Hallucination", "Models", "When an AI states something false or made up as if it were fact.",
     [r"hallucinat\w*"], False),

    # ---- Training ----------------------------------------------------------------------------------------------
    ("Pre-training", "Training", "The first, most expensive stage: a model reads a vast amount of data to learn "
     "language and facts in general.", [r"pre-?train(?:ing|ed)?"], False),
    ("Post-training", "Training", "Everything done after pre-training to make a model useful and safe: "
     "fine-tuning, reinforcement learning, safety training.", [r"post-?train(?:ing|ed)?"], False),
    ("Fine-tuning", "Training", "Training an existing model a little more on a specific set of examples, so it "
     "gets better at one task or style.", [r"fine-?tun(?:e|es|ed|ing)", r"SFT"], False),
    ("LoRA", "Training", "Low-Rank Adaptation: a cheap way to fine-tune a big model by training a small add-on "
     "instead of changing every parameter.", [r"LoRAs?", r"QLoRA"], True),
    ("Reinforcement learning", "Training", "RL: training by trial and reward. The model tries, gets a score for the "
     "result, and learns to do more of what scored well.", [r"reinforcement learning", r"RL(?=\b|-)", r"RLVR", r"GRPO"], False),
    ("RLHF", "Training", "Reinforcement learning from human feedback: people rate a model's answers and the model "
     "learns to give the kind people prefer.", [r"RLHF"], True),
    ("Distillation", "Training", "Training a small, cheap model to copy a big model's answers, so it keeps much of "
     "the ability at a fraction of the cost.", [r"distill(?:ation|ed|ing|s)?"], False),
    ("Synthetic data", "Training", "Training data made by computers (often by other AI models) rather than collected "
     "from people or the real world.", [r"synthetic data"], False),
    ("Scaling laws", "Training", "The observed pattern that models get predictably better as you add more data, "
     "parameters and computing power.", [r"scaling laws?"], False),
    ("Quantization", "Training", "Storing a model's numbers with less precision (e.g. 4 bits instead of 16) so it "
     "needs less memory and runs faster, usually losing a little quality.",
     [r"quanti[sz](?:ation|ed|ing)", r"FP8", r"FP4", r"BF16", r"GGUF"], False),

    # ---- Agents & products -------------------------------------------------------------------------------------
    ("AI agent", "Agents & products", "An AI system that doesn't just answer but takes actions on its own, step by "
     "step (browsing, clicking, running code, sending emails) to finish a task.", [r"agents?", r"agentic"], False),
    ("Computer-use agent", "Agents & products", "An agent that operates a computer like a person: looking at the "
     "screen, moving the mouse and typing.", [r"computer[- ]use", r"CUAs?"], False),
    ("Coding agent", "Agents & products", "An AI that writes, runs and fixes code by itself inside a software "
     "project, rather than just suggesting lines.", [r"coding agents?", r"vibe[- ]coding"], False),
    ("Copilot", "Agents & products", "An AI assistant built into a tool you already use (an editor, Office, a browser) "
     "that helps as you work. Also Microsoft's brand name.", [r"copilots?"], False),
    ("MCP", "Agents & products", "Model Context Protocol: an open standard, started by Anthropic, for plugging AI "
     "assistants into tools and data (a calendar, a database, GitHub) in one common way.",
     [r"MCP", r"Model Context Protocol"], True),
    ("RAG", "Agents & products", "Retrieval-augmented generation: the AI first looks up relevant documents, then "
     "answers using them, so it can cite sources and use private or recent information.",
     [r"RAG", r"retrieval[- ]augmented"], True),
    ("Vector database", "Agents & products", "A database that stores embeddings and finds the most similar ones "
     "quickly; the usual memory behind RAG.", [r"vector (?:databases?|search|stores?)"], False),
    ("API", "Agents & products", "Application programming interface: the way one program talks to another. An AI "
     "company's API lets developers send text to its model and get answers back, paying per token.", [r"APIs?"], True),
    ("SDK", "Agents & products", "Software development kit: ready-made code that makes it easier to build on a "
     "product or API.", [r"SDKs?"], True),
    ("Inference", "Agents & products", "Running a trained model to get answers (as opposed to training it). Most of "
     "the everyday cost of AI is inference.", [r"inference"], False),
    ("Latency", "Agents & products", "The delay between asking and getting an answer.", [r"latency"], False),
    ("On-device AI", "Agents & products", "AI that runs on your own phone, laptop or car instead of in a company's "
     "data center: faster and more private. Also called edge AI.", [r"on-device", r"edge AI", r"at the edge"], False),
    ("Humanoid robot", "Agents & products", "A robot shaped roughly like a person, with arms and legs, meant to work "
     "in spaces built for people.", [r"humanoids?"], False),
    ("Speech recognition", "Agents & products", "ASR (automatic speech recognition) turns speech into text; "
     "TTS (text-to-speech) does the reverse.", [r"ASR", r"TTS", r"speech recognition", r"text-to-speech"], False),
    ("OCR", "Agents & products", "Optical character recognition: reading the text in images or scanned documents.",
     [r"OCR"], True),

    # ---- Safety & security -------------------------------------------------------------------------------------
    ("Alignment", "Safety & security", "Making an AI system do what its makers and users actually intend, and hold "
     "to human values, even in situations nobody tested. Misalignment is when it doesn't.",
     [r"alignment", r"misalign(?:ed|ment)"], False),
    ("AGI", "Safety & security", "Artificial general intelligence: a hypothetical AI as capable as people across "
     "almost all tasks. There's no agreed test for when it arrives.", [r"AGI", r"artificial general intelligence"], True),
    ("Superintelligence", "Safety & security", "A hypothetical AI far smarter than the best humans in nearly every "
     "field.", [r"superintelligen\w+", r"ASI"], False),
    ("Red teaming", "Safety & security", "Deliberately attacking your own AI system to find harmful or unsafe "
     "behaviour before others do.", [r"red[- ]team\w*"], False),
    ("Jailbreak", "Safety & security", "A trick prompt that gets an AI to ignore its safety rules.",
     [r"jailbreak\w*"], False),
    ("Prompt injection", "Safety & security", "Hidden instructions planted in a web page, email or file that hijack an "
     "AI which reads it, e.g. telling an agent to leak data.", [r"prompt injections?"], False),
    ("Guardrails", "Safety & security", "Rules and filters around an AI system that block harmful requests or "
     "answers.", [r"guardrails?"], False),
    ("Sandbox", "Safety & security", "A sealed-off space where software (or an AI agent) can run without touching "
     "the real system. A regulatory sandbox is the legal version: a supervised trial with relaxed rules.",
     [r"sandbox(?:es|ed|ing)?"], False),
    ("Evals", "Safety & security", "Evaluations: tests that measure what a model can do or how it misbehaves, e.g. "
     "whether it can help build a weapon.", [r"evals", r"(?:safety|model|capability|dangerous[- ]capability) evaluations?"], False),
    ("Interpretability", "Safety & security", "Research into what is happening inside a model: which parts do what, "
     "and why it gives the answers it gives.", [r"interpretab\w+", r"explainab\w+"], False),
    ("Deepfake", "Safety & security", "A realistic fake video, image or voice made with AI, often of a real person.",
     [r"deep-?fakes?"], False),
    ("Watermarking", "Safety & security", "Hiding an invisible signal in AI-made text, images or audio so it can be "
     "recognised as AI-made later. Content provenance (e.g. C2PA) records where a file came from.",
     [r"watermark\w*", r"provenance", r"C2PA"], False),
    ("AI Safety Institute", "Safety & security", "A government body that tests advanced AI models for risks (the UK, "
     "US, Japan, Korea and others have one; some were renamed, e.g. the UK AI Security Institute).",
     [r"AISIs?", r"AI (?:Safety|Security) Institutes?", r"CAISI"], False),

    # ---- Chips & compute ---------------------------------------------------------------------------------------
    ("Compute", "Chips & compute", "Computing power, used as a noun: the chips, servers and electricity it takes to "
     "train and run AI.", [r"compute(?= |,|\.|$)(?!r)"], False),
    ("GPU", "Chips & compute", "Graphics processing unit: a chip first made for games that does many small sums at "
     "once, which is exactly what AI needs. Nvidia makes most of them.", [r"GPUs?"], True),
    ("CPU", "Chips & compute", "Central processing unit: a computer's general-purpose main chip. AI agents lean on "
     "CPUs again, to run the code and tools they call.", [r"CPUs?"], True),
    ("TPU", "Chips & compute", "Tensor processing unit: Google's own chip designed just for AI.", [r"TPUs?"], True),
    ("NPU", "Chips & compute", "Neural processing unit: a small AI chip inside phones and laptops for on-device AI.",
     [r"NPUs?"], True),
    ("ASIC", "Chips & compute", "A chip custom-built for one job; many AI companies now design their own for AI.",
     [r"ASICs?", r"custom (?:AI )?(?:chips?|silicon)"], False),
    ("HBM", "Chips & compute", "High-bandwidth memory: fast memory stacked next to AI chips; often the bottleneck, "
     "made mainly by SK Hynix, Samsung and Micron.", [r"HBM\d?e?"], True),
    ("CUDA", "Chips & compute", "Nvidia's software for programming its GPUs; a big reason developers stay with Nvidia.",
     [r"CUDA"], True),
    ("Data center", "Chips & compute", "A building full of servers. AI data centers hold tens of thousands of chips "
     "and can use as much power as a small city.", [r"data cent(?:er|re)s?", r"datacent(?:er|re)s?"], False),
    ("KV cache", "Chips & compute", "Memory a model keeps of the conversation so far so it doesn't recompute it for "
     "every new word; managing it well makes long chats cheaper.", [r"KV[- ]cache\w*"], False),
    ("Speculative decoding", "Chips & compute", "A speed-up: a small model drafts several words ahead and the big "
     "model checks them in one go.", [r"speculative decoding"], False),
    ("FLOPs", "Chips & compute", "Floating-point operations: the count of basic sums a computer does. Some laws use "
     "training FLOPs (e.g. 10^25) to decide which models count as the most powerful.", [r"FLOPs?", r"FLOP/s"], True),
    ("Export controls", "Chips & compute", "Government rules limiting which countries can buy advanced chips or "
     "chip-making tools, mainly US rules aimed at China.", [r"export controls?"], False),
    ("Sovereign AI", "Chips & compute", "A country building its own AI models, data centers and chips so it doesn't "
     "depend on foreign companies.", [r"sovereign AI", r"AI sovereignty"], False),

    # ---- Law & policy ------------------------------------------------------------------------------------------
    ("EU AI Act", "Law & policy", "The European Union's AI law: it bans some uses, puts strict duties on high-risk "
     "systems and sets rules for general-purpose models, coming into force in stages from 2025.",
     [r"(?:EU )?AI Act"], False),
    ("General-purpose AI", "Law & policy", "GPAI: the EU AI Act's name for models that can do many different tasks "
     "(like LLMs), with their own transparency and safety duties.", [r"general-purpose AI", r"GPAI"], False),
    ("High-risk AI", "Law & policy", "In the EU AI Act, AI used where mistakes can hurt people's lives or rights "
     "(hiring, credit, policing, medical devices), which must meet strict checks.", [r"high-risk"], False),
    ("Code of practice", "Law & policy", "A voluntary rulebook that companies can sign to show they meet a law's "
     "requirements, e.g. the EU's for general-purpose AI.", [r"codes? of (?:practice|conduct)"], False),
    ("Executive order", "Law & policy", "A direction from a president (or governor) to government agencies; "
     "faster than a law, but the next leader can undo it.", [r"executive orders?"], False),
    ("Preemption", "Law & policy", "A national law overriding state or local laws on the same subject; in the US, "
     "a fight over whether states may pass their own AI rules.", [r"pre-?empt\w*", r"moratorium"], False),
    ("NIST", "Law & policy", "The US National Institute of Standards and Technology: it writes voluntary technical "
     "standards, including the AI Risk Management Framework.", [r"NIST"], True),
    ("ISO/IEC standard", "Law & policy", "International technical standards; ISO/IEC 42001, for example, sets out how "
     "an organisation should manage AI.", [r"ISO/IEC(?: \d+)?", r"ISO \d{4,5}"], True),
    ("Copyright and fair use", "Law & policy", "The legal fight over whether training AI on books, art and news "
     "without permission is allowed. In the US it turns on \"fair use\"; the EU has text-and-data-mining rules.",
     [r"fair use", r"text and data mining", r"TDM"], False),
    ("Liability", "Law & policy", "Who is legally responsible, and pays, when an AI system causes harm.",
     [r"liability"], False),
    ("Algorithmic bias", "Law & policy", "When an AI system treats groups of people unfairly because of patterns in "
     "its training data or design.", [r"algorithmic bias", r"AI bias", r"biased"], False),

    # ---- Money & business --------------------------------------------------------------------------------------
    ("Funding rounds", "Money & business", "Seed, Series A, B, C…: successive rounds in which a startup sells a share "
     "of itself to investors; later letters usually mean a bigger, older company.",
     [r"seed rounds?", r"pre-seed", r"Series [A-H]\b"], False),
    ("Valuation", "Money & business", "What investors agree a company is worth in a funding round. A $10B valuation "
     "is not money raised; it's the price put on the whole company.", [r"valuations?", r"valued at"], False),
    ("IPO", "Money & business", "Initial public offering: when a company first sells shares on a stock exchange.",
     [r"IPOs?"], True),
    ("Acquihire", "Money & business", "Buying a company mainly to hire its team, or a licensing deal that brings over "
     "the founders without buying the company.", [r"acqui-?hire\w*"], False),
    ("Hyperscaler", "Money & business", "The giant cloud companies (Amazon Web Services, Microsoft Azure, Google "
     "Cloud, and others) that build most of the world's AI data centers.", [r"hyperscalers?"], False),
    ("ARR", "Money & business", "Annual recurring revenue: what a company's subscriptions and contracts bring in per "
     "year, the headline figure for AI startups.", [r"ARR", r"annuali[sz]ed revenue"], True),
    ("PBC", "Money & business", "Public benefit corporation: a company legally required to weigh a public mission "
     "alongside profits (Anthropic and OpenAI's business arm are PBCs).", [r"PBCs?", r"public benefit corporations?"], True),

    # ---- Research ----------------------------------------------------------------------------------------------
    ("Benchmark", "Research", "A standard test used to compare models, such as maths problems or coding tasks. "
     "Scores can mislead if a model has seen the answers in training.", [r"benchmarks?"], False),
    ("State of the art", "Research", "SOTA: the best result anyone has published so far on a task.",
     [r"state-of-the-art", r"state of the art", r"SOTA"], False),
    ("arXiv", "Research", "A free website where researchers post papers before (or instead of) formal peer review; "
     "most AI research appears there first.", [r"arXiv"], False),
    ("Preprint", "Research", "A research paper shared publicly before it has been peer-reviewed.",
     [r"preprints?"], False),
    ("Zero-shot / few-shot", "Research", "Doing a task with no examples given (zero-shot) or only a handful "
     "(few-shot), without extra training.", [r"zero-shot", r"few-shot"], False),
    ("Chain of thought", "Research", "A model writing out its reasoning step by step before the answer; it tends to "
     "improve answers and lets people inspect the reasoning.", [r"chain[- ]of[- ]thought", r"CoT"], False),
    ("Test-time compute", "Research", "Letting a model think longer (spend more computing) when answering, rather "
     "than only making it bigger during training.", [r"test-time (?:compute|scaling)", r"inference-time"], False),
    ("Machine learning", "Research", "ML: the broad field of computer systems that learn patterns from data instead "
     "of following hand-written rules. Today's AI is mostly machine learning.", [r"ML", r"[Mm]achine [Ll]earning"], True),
    ("SWE-bench", "Research", "A benchmark of real bug reports from open-source projects; the standard test of how "
     "well AI can do a software engineer's (SWE's) work.", [r"SWE-?bench\w*", r"SWE"], True),
    ("JEPA", "Research", "Joint-embedding predictive architecture: Yann LeCun's approach to world models, predicting "
     "the meaning of what comes next rather than every pixel.", [r"V?-?JEPA\w*"], True),
    ("CSET and METR", "Research", "Research groups often cited on AI: CSET (Georgetown's Center for Security and "
     "Emerging Technology) studies AI policy and security; METR tests what frontier models can do on their own.",
     [r"CSET", r"METR"], True),
    ("Latent", "Research", "Hidden: a model's internal representation of data (a \"latent space\"), rather than the "
     "words or pixels you see.", [r"latent(?: space)?"], False),

    # ---- Names: companies' products and model families that headlines use without explaining -------------------
    ("Character.AI", "Names", "c.ai: an app for chatting and role-playing with AI characters. Its \"Chat Styles\" "
     "(such as PipSqueak and ShortSqueak) are the different AI models a user can pick to power a chat.",
     [r"Character\.AI", r"c\.ai", r"Chat Styles?", r"PipSqueak", r"ShortSqueak"], True),
    ("Claude", "Names", "Anthropic's AI assistant and model family. Opus is the largest, Sonnet the mid-size "
     "all-rounder, Haiku the small fast one; Claude Code is its coding agent.",
     [r"Claude(?: (?:Code|Opus|Sonnet|Haiku|Fable))?"], True),
    ("Gemini", "Names", "Google's AI assistant and model family. Gemma is Google's smaller open-weight family.",
     [r"Gemini", r"Gemma"], True),
    ("Grok", "Names", "The AI assistant and model family from xAI, Elon Musk's AI company, built into X.",
     [r"Grok"], True),
    ("Llama", "Names", "Meta's open-weight model family.", [r"Llama"], True),
    ("Qwen", "Names", "Alibaba's model family, one of the most used open-weight families (Qwen-Image, Qwen-Audio…).",
     [r"Qwen[\w-]*"], True),
    ("DeepSeek", "Names", "A Chinese AI lab known for strong open-weight models trained at low cost (V-series, "
     "R1 reasoning model).", [r"DeepSeek"], True),
    ("Kimi", "Names", "The model family and chatbot of Moonshot AI, a Chinese lab; its K-series (K2, K3) are "
     "open-weight.", [r"Kimi"], True),
    ("GLM", "Names", "The model family of Zhipu AI (Z.ai), a Chinese lab; many are open-weight.", [r"GLM[\w.-]*", r"Z\.ai"], True),
    ("Mistral", "Names", "Mistral AI, France's leading AI lab, and its models; several are open-weight.",
     [r"Mistral"], True),
    ("Nemotron", "Names", "Nvidia's own family of open models, often built on others' models and tuned for its chips.",
     [r"Nemotron"], True),
    ("Cosmos", "Names", "Nvidia's family of world models for robots and self-driving cars.", [r"(?:Nvidia |NVIDIA )?Cosmos"], True),
    ("LongCat", "Names", "The model family of Meituan, the Chinese food-delivery giant.", [r"LongCat[\w.-]*"], True),
    ("FLUX", "Names", "Image-generation models from Black Forest Labs, a German start-up.", [r"FLUX(?:\.\d)?"], True),
    ("Seedance", "Names", "ByteDance's video-generation model (ByteDance owns TikTok).", [r"Seedance"], True),
    ("Hugging Face", "Names", "The main website for sharing AI models and datasets, like GitHub for AI; also a company "
     "that builds open tools.", [r"Hugging ?Face"], True),
    ("Cloud AI platforms", "Names", "Amazon Bedrock, Google Vertex AI and Microsoft Foundry: services where companies "
     "rent many different AI models through one cloud account.", [r"Bedrock", r"Vertex AI", r"(?:Azure )?AI Foundry"], True),
]


def _key(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


# What "Show stories that mention it" types into the site's search, where the term itself isn't how stories write it
SEARCH = {"AI agent": "agent", "Open-weight model": "open-weight", "Parameters": "parameters", "Pre-training": "pretraining",
          "Speech recognition": "speech recognition", "Zero-shot / few-shot": "zero-shot", "CSET and METR": "METR",
          "Copyright and fair use": "fair use", "Cloud AI platforms": "Bedrock", "ISO/IEC standard": "ISO",
          "Funding rounds": "Series", "Preemption": "preemption", "AI Safety Institute": "AISI", "Evals": "evals",
          "Watermarking": "watermark", "Humanoid robot": "humanoid", "On-device AI": "on-device",
          "Algorithmic bias": "bias", "High-risk AI": "high-risk", "Test-time compute": "test-time",
          "Computer-use agent": "computer use", "Chain of thought": "chain of thought", "State of the art": "state-of-the-art"}

ENTRIES = [{"id": _key(t), "term": t, "group": g, "def": d, "match": m, "case": cs, "search": SEARCH.get(t, t)}
           for t, g, d, m, cs in _ENTRIES]


def _pattern(e: dict) -> re.Pattern:
    return re.compile(r"(?<!\w)(?:" + "|".join(e["match"]) + r")(?![\w])", 0 if e["case"] else re.I)


_PATTERNS = {e["id"]: _pattern(e) for e in ENTRIES}


def terms_in(text: str) -> list[str]:
    """The glossary entries a piece of text mentions, in glossary order."""
    return [e["id"] for e in ENTRIES if _PATTERNS[e["id"]].search(text or "")]


def payload(cards: list[dict], today: date | None = None, days: int = 7) -> dict:
    """glossary.json: every entry, plus how many of the last `days` days' cards mention each (for "In the news")."""
    since = ((today or date.today()) - timedelta(days=days)).isoformat()
    seen = Counter(t for c in cards if (c.get("date") or "") >= since
                   for t in terms_in(f"{c.get('title') or ''} {c.get('summary') or ''}"))
    return {"groups": GROUPS, "days": days,
            "entries": [{**e, "recent": seen.get(e["id"], 0)} for e in ENTRIES]}


def missing(cards: list[dict], top: int = 40) -> list[tuple[str, int]]:
    """Short capitalised words (acronyms) that many cards use but no entry explains: candidates to write up."""
    known = re.compile("|".join(f"(?:{p.pattern})" for p in _PATTERNS.values()))
    skip = {"AI", "US", "UK", "EU", "UN", "CEO", "CFO", "CTO", "VP", "IT", "PC", "PCs", "TV", "OS", "UI", "PDF", "PDFs",
            "URL", "ID", "HR", "PR", "QA", "CNN", "CNBC", "WIRED", "FBI", "FTC", "FAA", "UAE", "MIT", "LLC", "IBM",
            "AMD", "AWS", "NVIDIA", "HPE", "HP", "Q1", "Q2", "Q3", "Q4", "II", "III", "OR", "GO", "UP", "DATA", "JSON", "CLI"}
    n = Counter(w for c in cards for w in set(re.findall(r"\b[A-Z][A-Z0-9]{1,6}s?\b", f"{c.get('title') or ''} {c.get('summary') or ''}"))
                if w not in skip and w.rstrip("s") not in skip and not known.fullmatch(w))
    return n.most_common(top)
