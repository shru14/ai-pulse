"""Release cards (release-cards/): every major AI model release since 1 July 2026, newest first, with whether its
weights can be downloaded, under what licence, where it can be used and its price at launch. A release counts as
major when at least two news outlets reported it within three days of launch (the lab itself, its partners' blogs
and hosting services don't count). Every row was checked by hand: weights and licence on the model's Hugging Face
page and its licence text, the rest against the story or lab page it links to. Linked from Releases' strip.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from html import escape
from pathlib import Path

from . import pages, rss

PATH = "release-cards/"
SINCE = "2026-07-01"
# each lab's home country, as the stories give it
COUNTRY = {
    "Alibaba": "China", "Aleph Alpha": "Germany", "Anthropic": "US", "Black Forest Labs": "Germany", "Cisco": "US",
    "Cloudflare": "US", "DeepSeek": "China", "Google": "US", "IBM": "US", "Meta": "US", "Microsoft": "US",
    "MiniMax": "China", "Mistral": "France", "Moonshot": "China", "Nvidia": "US", "OpenAI": "US", "PolyAI": "UK",
    "Poolside": "France", "PrismML": "US", "Reflection AI": "US", "StepFun": "China", "Thinking Machines": "US",
    "Writer": "US", "xAI": "US", "Z.ai": "China",
}
# Open: weights can be downloaded and used commercially (a licence may still ask big companies for a deal);
# Weights only: weights can be downloaded but the licence bars commercial use; Closed: no weights to download
WEIGHTS = ("Open", "Weights only", "Closed")
# (day, lab, model, weights, access note, licence as the lab names it, its main limit, where it can be used ("" =
#  no limits stated), whether that leaves places out, price at launch on the lab's own API ($ in / $ out per 1M
#  tokens; "|" then a note), the story or lab page, the weights' Hugging Face page)
RELEASES = [
    ("2026-04-17", "Alibaba", "Qwen3.6-35B-A3B", "Open", "", "Apache-2.0", "", "", False, "",
     "https://the-decoder.com/alibabas-open-model-qwen3-6-leads-googles-gemma-4-across-agentic-coding-benchmarks/",
     "https://huggingface.co/Qwen/Qwen3.6-35B-A3B"),
    ("2026-04-20", "Moonshot", "Kimi K2.6", "Open", "", "Modified MIT License",
     "Products over 100M monthly users or $20M a month must show \"Kimi K2.6\"", "", False, "",
     "https://the-decoder.com/open-weight-kimi-k2-6-takes-on-gpt-5-4-and-claude-opus-4-6-with-agent-swarms/",
     "https://huggingface.co/moonshotai/Kimi-K2.6"),
    ("2026-04-23", "OpenAI", "GPT-5.5", "Closed", "API from 25 Apr", "", "", "", False, "$5 / $30",
     "https://the-decoder.com/openai-unveils-gpt-5-5-claims-a-new-class-of-intelligence-at-double-the-api-price/", ""),
    ("2026-04-24", "DeepSeek", "DeepSeek V4 Preview", "Open", "", "MIT", "", "", False,
     "Flash $0.14 / $0.28; Pro $1.74 / $3.48",
     "https://the-decoder.com/as-agentic-ai-pushes-rivals-to-raise-prices-and-cap-usage-deepseek-ships-a-good-enough-model-for-almost-nothing/",
     "https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro"),
    ("2026-04-28", "Nvidia", "Nemotron 3 Nano Omni", "Open", "", "NVIDIA Open Model Agreement",
     "Licence ends if you sue alleging the model infringes patents or copyright", "", False, "",
     "https://blogs.nvidia.com/blog/nemotron-3-nano-omni-multimodal-ai-agents/",
     "https://huggingface.co/nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16"),
    ("2026-05-05", "OpenAI", "GPT-5.5 Instant", "Closed", "In the API as chat-latest", "", "", "", False, "",
     "https://techcrunch.com/2026/05/05/openai-releases-gpt-5-5-instant-a-new-default-model-for-chatgpt/", ""),
    ("2026-05-19", "Google", "Gemini 3.5 Flash", "Closed", "", "", "", "", False, "$1.50 / $9",
     "https://the-decoder.com/googles-gemini-3-5-flash-follows-anthropic-and-openai-in-making-newer-ai-models-significantly-pricier/", ""),
    ("2026-05-19", "Google", "Gemini Omni Flash", "Closed", "No API at launch; preview from 30 Jun", "", "", "", False, "",
     "https://techcrunch.com/2026/05/19/googles-gemini-omni-turns-images-audio-and-text-into-video-and-thats-just-the-start/", ""),
    ("2026-05-28", "Anthropic", "Claude Opus 4.8", "Closed", "", "", "", "", False, "$5 / $25",
     "https://the-decoder.com/anthropic-ships-claude-opus-4-8-as-a-modest-but-tangible-improvement-that-tops-gpt-5-5-in-most-benchmarks/", ""),
    ("2026-05-31", "Nvidia", "Cosmos 3", "Open", "", "OpenMDW-1.1", "", "", False, "",
     "https://the-decoder.com/nvidia-bets-big-on-physical-ai-at-gtc-taipei-with-a-new-world-model-driving-brain-and-open-humanoid-robot/",
     "https://huggingface.co/nvidia/Cosmos3-Super"),
    ("2026-06-01", "MiniMax", "MiniMax M3", "Open", "Weights promised within 10 days", "MiniMax Community License",
     "Companies over $20M a year need MiniMax's permission", "", False, "",
     "https://the-decoder.com/minimax-m3-open-weight-model-with-a-million-token-context-challenges-proprietary-leaders/",
     "https://huggingface.co/MiniMaxAI/MiniMax-M3"),
    ("2026-06-01", "Nvidia", "Nemotron 3 Ultra", "Open", "Weights from 4 Jun", "OpenMDW-1.1", "", "", False, "",
     "https://the-decoder.com/nvidias-nemotron-3-ultra-becomes-the-smartest-open-us-model-but-china-still-leads/",
     "https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16"),
    ("2026-06-09", "Google", "Gemini 3.5 Live Translate", "Closed", "Preview for developers and businesses", "", "", "",
     False, "",
     "https://the-decoder.com/googles-gemini-3-5-live-translate-delivers-real-time-voice-translation-across-70-languages/", ""),
    ("2026-06-10", "Google", "DiffusionGemma", "Open", "", "Apache-2.0", "", "", False, "",
     "https://the-decoder.com/googles-new-open-model-diffusiongemma-generates-text-from-noise-instead-of-word-by-word/",
     "https://huggingface.co/google/diffusiongemma-26B-A4B-it"),
    ("2026-06-15", "Z.ai", "GLM-5.2", "Open", "", "MIT", "", "", False, "",
     "https://the-decoder.com/zhipu-ais-glm-5-2-closes-in-on-closed-source-leaders-in-coding-marathons/",
     "https://huggingface.co/zai-org/GLM-5.2"),
    ("2026-06-30", "Google", "Nano Banana 2 Lite", "Closed", "", "", "", "", False, "$0.034|an image at 1K",
     "https://the-decoder.com/google-launches-nano-banana-2-lite-for-fast-ai-images-and-gemini-omni-flash-for-video-via-api/", ""),
    ("2026-07-02", "Mistral", "Leanstral 1.5", "Open", "", "Apache-2.0", "", "", False, "Free API",
     "https://mistral.ai/news/leanstral-1-5/", "https://huggingface.co/mistralai/Leanstral-1.5-119B-A6B"),
    ("2026-07-08", "OpenAI", "GPT-Live", "Closed", "No API at launch", "", "", "", False, "",
     "https://www.marktechpost.com/2026/07/08/openai-releases-gpt-live-and-gpt-live-1-mini-full-duplex-voice-models-that-delegate-deeper-reasoning-to-gpt-5-5/", ""),
    ("2026-07-08", "xAI", "Grok 4.5", "Closed", "", "", "", "Not in the EU at launch; EU from 17 Jul", True, "$2 / $6",
     "https://docs.x.ai/developers/release-notes", ""),
    ("2026-07-09", "Meta", "Muse Spark 1.1", "Closed", "", "", "", "API preview in the US only at launch", True,
     "$1.25 / $4.25", "https://www.marktechpost.com/2026/07/09/meta-superintelligence-labs-releases-muse-spark-1-1/", ""),
    ("2026-07-14", "PrismML", "Bonsai 27B", "Open", "", "Apache-2.0", "", "", False, "",
     "https://the-decoder.com/bonsai-27b-is-a-full-open-reasoning-model-that-fits-on-an-iphone/",
     "https://huggingface.co/prism-ml/Bonsai-27B-gguf"),
    ("2026-07-15", "Thinking Machines", "Inkling", "Open", "", "Apache-2.0", "", "", False, "",
     "https://www.marktechpost.com/2026/07/15/thinking-machines-lab-releases-inkling-a-975b-parameter-open-weights-multimodal-moe-with-41b-active-parameters-and-controllable-thinking-effort/",
     "https://huggingface.co/thinkingmachines/Inkling"),
    ("2026-07-16", "Moonshot", "Kimi K3", "Open", "Weights from 27 Jul", "Kimi K3 License",
     "API businesses over $20M a year need a deal with Moonshot", "", False, "$3 / $15",
     "https://www.marktechpost.com/2026/07/16/moonshot-ai-releases-kimi-k3-a-2-8-trillion-parameter-open-moe-model-with-kimi-delta-attention-and-1m-context/",
     "https://huggingface.co/moonshotai/Kimi-K3"),
    ("2026-07-21", "Cisco", "Antares", "Open", "", "Apache-2.0", "", "", False, "",
     "https://siliconangle.com/2026/07/21/cisco-releases-antares-open-weight-small-models-locating-code-vulnerabilities/",
     "https://huggingface.co/fdtn-ai/antares-1b"),
    ("2026-07-21", "Poolside", "Laguna S 2.1", "Open", "", "OpenMDW-1.1", "", "", False, "",
     "https://the-decoder.com/poolsides-laguna-s-2-1-is-a-small-open-weight-coding-model-that-punches-well-above-its-size/",
     "https://huggingface.co/poolside/Laguna-S-2.1"),
    ("2026-07-24", "Anthropic", "Claude Opus 5", "Closed", "", "", "", "", False, "$5 / $25",
     "https://the-decoder.com/anthropic-claims-its-new-claude-opus-5-delivers-near-fable-5-performance-at-half-the-token-price/", ""),
    ("2026-07-27", "Microsoft", "MAI-Cyber-1-Flash", "Closed", "Gated access", "", "", "", False, "",
     "https://www.marktechpost.com/2026/07/28/microsoft-ai-releases-mai-cyber-1-flash-a-5b-active-parameter-cyber-model-that-pushes-mdash-to-95-95-on-cybergym/", ""),
    ("2026-07-28", "Google", "Gemini Robotics 2", "Closed", "Early access by waitlist", "", "", "", False, "",
     "https://the-decoder.com/google-deepmind-unveils-gemini-robotics-2-to-power-robots-of-all-shapes-from-tabletop-arms-to-humanoids/", ""),
    ("2026-07-28", "MiniMax", "MiniMax H3", "Open", "", "MiniMax H3 Community License",
     "Companies over $20M a year need MiniMax's permission", "", False, "",
     "https://the-decoder.com/chinas-minimax-h3-is-the-first-open-model-to-top-an-ai-video-ranking/",
     "https://huggingface.co/MiniMaxAI/MiniMax-H3"),
    ("2026-07-30", "PolyAI", "Dialog-RSN-1", "Closed", "Only on PolyAI's own platform", "", "", "", False, "",
     "https://www.marktechpost.com/2026/07/30/polyai-releases-dialog-rsn-1-an-audio-native-dialog-model-that-fuses-turn-taking-speech-recognition-function-calling-and-response/", ""),
    ("2026-07-31", "Thinking Machines", "Inkling Small", "Open", "", "Apache-2.0", "", "", False, "",
     "https://www.marktechpost.com/2026/08/02/thinking-machines-lab-releases-inkling-small-276b-open-weights-multimodal-moe-model/",
     "https://huggingface.co/thinkingmachines/Inkling-Small"),
    ("2026-08-03", "Alibaba", "Qwen3.8-Max", "Open", "Weights from 8 Aug", "Qwen3.8-Max License",
     "API businesses over $50M a year need a separate licence", "", False, "$2 / $6",
     "https://www.marktechpost.com/2026/08/03/alibaba-qwen-releases-qwen3-8-max/",
     "https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B"),
    ("2026-08-10", "Meta", "Muse Glimmer", "Open", "", "Apache-2.0", "", "", False, "",
     "https://www.marktechpost.com/2026/08/10/meta-ai-releases-muse-glimmer/",
     "https://huggingface.co/meta-models/Muse-Glimmer-30B"),
    ("2026-08-10", "OpenAI", "GPT-5.6-Cyber", "Closed", "Daybreak Red tier only", "", "", "", False, "",
     "https://the-decoder.com/openai-launches-gpt-5-6-cyber-to-help-defenders-find-vulnerabilities-before-attackers-do/", ""),
    ("2026-08-11", "Nvidia", "Nemotron 3.5 Lightning", "Open", "", "OpenMDW-1.1", "", "", False, "",
     "https://www.marktechpost.com/2026/08/11/nvidia-ai-releases-nemotron-3-5-lightning-and-nemo-switchyard/",
     "https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16"),
    ("2026-08-12", "xAI", "Grok 4.6", "Closed", "", "", "", "", False, "$2 / $6",
     "https://www.marktechpost.com/2026/08/12/spacexai-releases-grok-4-6/", ""),
    ("2026-08-13", "Google", "Gemini 3.7 Flash", "Closed", "", "", "", "", False,
     "$0.75 / $3.75|introductory, until 31 Dec",
     "https://deepmind.google/blog/introducing-gemini-3-7-flash/", ""),
    ("2026-08-13", "Writer", "Palmyra X6", "Closed", "", "", "", "", False, "$2 / $8",
     "https://siliconangle.com/2026/08/13/writer-launches-major-agentic-ai-improvements-palmyra-x6-flagship-model/", ""),
    ("2026-08-14", "Z.ai", "GLM-5.3", "Open", "Weights from 25 Aug", "GLM-5.3 License",
     "API businesses over $10B a year need Z.ai's security review", "", False, "",
     "https://siliconangle.com/2026/08/14/z-ai-debuts-glm-5-3-long-horizon-coding-cybersecurity-upgrades/",
     "https://huggingface.co/zai-org/GLM-5.3"),
    ("2026-08-24", "Alibaba", "Qwen3.8-Flash-Next", "Open", "", "Qwen Community License 1.0",
     "API and AI-assistant businesses need a separate licence", "", False, "",
     "https://www.marktechpost.com/2026/08/26/alibabas-qwen-team-releases-qwen3-8-flash-next-a-125b-multimodal-moe-with-6b-active-parameters-previewing-the-qwen4-architecture/",
     "https://huggingface.co/Qwen/Qwen3.8-Flash-Next"),
    ("2026-08-25", "Z.ai", "GLM-5.3-Flash", "Open", "", "MIT", "", "", False, "$0.15 / $0.50",
     "https://www.marktechpost.com/2026/08/26/z-ai-releases-glm-5-3-flash-a-320b-a18b-natively-multimodal-moe-with-a-1m-token-context/",
     "https://huggingface.co/zai-org/GLM-5.3-Flash"),
    ("2026-08-25", "IBM", "Granite 4.2", "Open", "", "Apache-2.0", "", "", False, "",
     "https://the-decoder.com/ibm-drops-open-weight-granite-4-2-family-with-built-in-agentic-capabilities-under-apache-2-0/",
     "https://huggingface.co/ibm-granite/granite-4.2-30b"),
    ("2026-08-26", "Google", "Gemini 3.5 Transcribe", "Closed", "", "", "",
     "Gemini app on Mac in English; Rambler on Android in some countries", True, "",
     "https://deepmind.google/blog/intelligent-transcription-with-gemini-3-5-transcribe/", ""),
    ("2026-09-01", "Anthropic", "Claude Fable 5.1", "Closed", "", "", "", "", False, "$10 / $50",
     "https://www.marktechpost.com/2026/09/01/anthropic-releases-claude-fable-5-1-and-claude-mythos-5-1-52-6-on-terminal-bench-science-and-75-cheaper-cache-reads/", ""),
    ("2026-09-02", "Google", "Gemini 3.8 Flash", "Closed", "Its Cyber version: trusted defenders only", "", "", "",
     False, "$0.75 / $3.75|introductory, until 31 Dec",
     "https://deepmind.google/blog/introducing-gemini-3-8-flash-and-38-flash-cyber/", ""),
    ("2026-09-02", "Meta", "Muse Spark 1.3", "Closed", "", "", "", "", False, "$1.25 / $4.25",
     "https://www.marktechpost.com/2026/09/03/meta-ai-released-muse-spark-1-3-an-agentic-coding-model-that-uses-20-fewer-tool-calls-and-25-fewer-tokens-than-muse-spark-1-2/", ""),
    ("2026-09-03", "OpenAI", "GPT-6 Astra", "Closed", "Gated at launch", "", "", "", False,
     "$10 / $50", "https://www.marktechpost.com/2026/09/03/openai-releases-gpt-6-astra-a-1-05m-context-computer-use-model-gated-behind-a-critical-cyber-threshold/", ""),
    ("2026-09-10", "DeepSeek", "DeepSeek V4.1 Flash", "Open", "", "MIT", "", "", False,
     "$0.15 / $0.60|off-peak; double at weekday peaks",
     "https://siliconangle.com/2026/09/10/deepseek-releases-v4-1-flash-says-it-outperforms-flagship-v4-pro/",
     "https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash"),
    ("2026-09-15", "Google", "Gemini 3.8 Live", "Closed", "", "", "", "", False, "$0.005 / $0.018|a minute of audio",
     "https://siliconangle.com/2026/09/15/googles-new-speech-model-gemini-3-8-live-supports-real-time-reasoning/", ""),
    ("2026-09-18", "Alibaba", "Qwen3.8-Omni-Flash", "Closed", "", "", "", "", False, "$0.15 / $0.47",
     "https://www.marktechpost.com/2026/09/18/alibaba-qwen-releases-qwen3-8-omni-flash/", ""),
    ("2026-09-21", "xAI", "Grok 4.7", "Closed", "", "", "", "", False, "$2 / $6",
     "https://the-decoder.com/xai-launches-grok-4-7-at-bargain-prices-but-benchmarks-reveal-a-wide-gap-to-claude-and-gpt-6/", ""),
    ("2026-09-22", "Anthropic", "Claude Opus 5.5", "Closed", "", "", "", "", False, "$4 / $20",
     "https://www.anthropic.com/claude-opus-5-5", ""),
    ("2026-09-22", "OpenAI", "GPT-6 Sol and Luna", "Closed", "", "", "", "", False, "Sol $2 / $10; Luna $0.10 / $0.50",
     "https://the-decoder.com/openais-gpt-6-sol-and-luna-cut-prices-in-half-but-barely-move-the-needle-on-performance/", ""),
    ("2026-09-24", "Black Forest Labs", "FLUX 3 Action", "Weights only", "", "FLUX Kommunity License",
     "Non-commercial use only", "", False, "",
     "https://www.marktechpost.com/2026/09/24/black-forest-labs-releases-flux-3-action-a-7b-open-weights-world-action-model-that-tops-robolab-120/",
     "https://huggingface.co/black-forest-labs/flux-3-action-base"),
    ("2026-09-28", "Anthropic", "Claude Sonnet 5.5", "Closed", "", "", "", "", False, "$2 / $10",
     "https://www.anthropic.com/claude-sonnet-5-5", ""),
    ("2026-09-29", "OpenAI", "GPT-6.1 Sol", "Closed", "", "", "", "", False, "$2 / $10",
     "https://the-decoder.com/gpt-6-1-sol-comes-close-to-astra-at-a-fifth-of-the-price/", ""),
    ("2026-09-30", "Google", "Gemini 4 Argon", "Closed", "Everyone from 13 Oct", "", "",
     "Worldwide from 13 Oct, says Google", False, "$2 / $10|introductory, until 30 Nov",
     "https://blog.google/innovation-and-ai/models-and-research/gemini-models/introducing-gemini-4-argon/", ""),
    ("2026-10-01", "Cloudflare", "Clef", "Open", "", "Apache-2.0", "", "", False, "",
     "https://blog.cloudflare.com/clef-decision-models/", ""),
    ("2026-10-02", "Microsoft", "MAI-Transcribe-2", "Closed", "Public preview", "", "", "", False,
     "$0.54|an hour of streaming audio",
     "https://www.marktechpost.com/2026/10/02/microsoft-ai-releases-mai-transcribe-2-streaming-1-real-time-speech-to-text-model-on-artificial-analysis/", ""),
    ("2026-10-02", "Aleph Alpha", "Kolibri", "Open", "", "Apache-2.0", "", "", False, "",
     "https://the-decoder.com/aleph-alpha-releases-kolibri-an-open-weight-model-that-makes-the-case-for-european-ai-sovereignty/",
     "https://huggingface.co/Aleph-Alpha/Kolibri-1"),
    ("2026-10-05", "Reflection AI", "Beam", "Open", "Weights from 16 Oct", "Apache-2.0", "", "",
     False, "", "https://the-decoder.com/reflections-beam-becomes-the-most-capable-open-weight-model-built-outside-china/",
     "https://huggingface.co/reflection/Beam-1.0-501B-A23B"),
    ("2026-10-06", "Mistral", "Mistral Large 4", "Closed", "Weights promised after safety testing",
     "", "", "", False, "",
     "https://techcrunch.com/2026/10/06/mistrals-new-1t-model-aims-to-leapfrog-closed-and-open-rivals/", ""),
    ("2026-10-07", "Anthropic", "Claude Haiku 5.5", "Closed", "", "", "", "", False,
     "$0.10 / $0.50|prompts up to 100K tokens",
     "https://www.marktechpost.com/2026/10/07/anthropic-releases-claude-haiku-5-5-a-small-model-with-1m-context-priced-at-0-10-per-million-input-tokens/", ""),
    ("2026-10-12", "Meta", "Muse Wonder", "Closed", "Wonder Full only in Muse Code", "", "", "", False, "$4 / $20",
     "https://the-decoder.com/metas-new-frontier-model-muse-wonder-full-breaks-into-the-ai-top-tier/", ""),
    ("2026-10-14", "xAI", "Grok Voice 3.0", "Closed", "", "", "", "", False, "$0.08|a minute",
     "https://siliconangle.com/2026/10/14/grok-voice-3-0-from-spacexsi-outscores-openai-and-google-on-speech-to-speech-index/", ""),
    ("2026-10-15", "Meta", "Muse Spark Open", "Open", "Download after Meta approves the request", "Muse Model License",
     "\"Built with Muse Spark Open\" label; API services over $20M a year need a deal", "", False, "",
     "https://the-decoder.com/muse-spark-open-is-metas-answer-to-qwen-glm-and-kimi-in-the-open-weight-race/",
     "https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B"),
    ("2026-10-15", "Nvidia", "Nemotron 3.5 Super VL", "Open", "", "OpenMDW-1.1", "", "", False, "",
     "https://www.marktechpost.com/2026/10/15/nvidia-nemotron-3-5-super-vl-release/",
     "https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16"),
    ("2026-10-15", "StepFun", "Step 5 Preview", "Open", "Weights from 15 Oct", "StepFun Model License 1.0",
     "API businesses over $20M a year and device makers need a commercial licence", "", False, "$1.00 / $2.70",
     "https://www.marktechpost.com/2026/10/16/stepfun-releases-step-5-preview-open-weights-600b-moe-27b-active-1m-context/",
     "https://huggingface.co/stepfun-ai/Step-5-Preview"),
    ("2026-10-15", "Nvidia", "Nemotron 3.5 Bolt 74B-A9B 24GB", "Open", "", "OpenMDW-1.1", "", "", False, "",
     "https://the-decoder.com/nvidias-nemotron-3-5-super-vl-is-an-open-model-built-to-run-enterprise-ai-agents-nonstop/",
     "https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Bolt-74B-A9B-24GB"),
    ("2026-10-19", "Cloudflare", "Clairic", "Closed", "Preview on Workers AI; weights promised soon", "", "", "", False, "",
     "https://blog.cloudflare.com/clairic-extraction-model/", ""),
    ("2026-10-19", "MiniMax", "MiniMax M3.1 Flash", "Closed", "Weights promised later", "", "", "", False, "$0.15 / $0.60",
     "https://www.minimax.io/blog/minimax-m31f", ""),
]
# the lab's first document with safety test results for a release (a system card, a safety report, a launch post that
# gives results, or a model card or technical report with a safety section that gives them): model -> (its day, its link, a note). A model missing
# here, or with no day, had none on the lab's own pages when last checked; text on safety with no results doesn't count.
# The daily job looks again for each release still without one until RECHECK days after its launch, and moves
# SAFETY_CHECKED on; every release was first checked on FIRST_CHECKED
FIRST_CHECKED = "2026-10-20"
SAFETY_CHECKED = "2026-10-20"
RECHECK = 30
SAFETY = {
    "GPT-Live": ("2026-07-08", "https://deploymentsafety.openai.com/gpt-live", ""),
    "Muse Spark 1.1": ("2026-07-09", "https://ai.meta.com/static-resource/muse-spark-1-1-evaluation-report", ""),
    "Inkling": ("2026-07-15", "https://huggingface.co/thinkingmachines/Inkling", "In its model card"),
    "Claude Opus 5": ("2026-07-24", "https://anthropic.com/claude-opus-5-system-card", ""),
    "MAI-Cyber-1-Flash": ("2026-07-27", "https://microsoft.ai/pdf/MAI-Cyber-1-Flash-Model-Card.pdf", "In its model card"),
    "Inkling Small": ("2026-07-31", "https://huggingface.co/thinkingmachines/Inkling-Small", "In its model card"),
    "Muse Glimmer": ("2026-08-10", "https://huggingface.co/meta-models/Muse-Glimmer-30B", "In its model card"),
    "Gemini 3.7 Flash": ("2026-08-13", "https://deepmind.google/models/model-cards/gemini-3-7-flash/", "In its model card"),
    "Palmyra X6": ("2026-08-17", "https://arxiv.org/abs/2608.16620", "In its technical report"),
    "Claude Fable 5.1": ("2026-09-01", "https://www.anthropic.com/claude-fable-5-1-mythos-5-1-system-card", ""),
    "Gemini 3.8 Flash": ("2026-09-02", "https://deepmind.google/models/model-cards/gemini-3-8-flash/", "In its model card"),
    "GPT-6 Astra": ("2026-09-03", "https://deploymentsafety.openai.com/gpt-6-astra", ""),
    "GPT-6 Sol and Luna": ("2026-09-22", "https://deploymentsafety.openai.com/gpt-6-astra",
                           "An appendix to the GPT-6 Astra card"),
    "Claude Opus 5.5": ("2026-09-22", "https://www.anthropic.com/claude-opus-5-5-system-card", ""),
    "Claude Sonnet 5.5": ("2026-09-28", "https://www.anthropic.com/claude-sonnet-5-5-system-card", ""),
    "GPT-6.1 Sol": ("2026-09-29", "https://deploymentsafety.openai.com/gpt-6-1-sol", ""),
    "Claude Haiku 5.5": ("2026-10-07", "https://www.anthropic.com/claude-haiku-5-5-system-card", ""),
    "Muse Wonder": ("2026-10-12", "https://research.meta.ai/static/muse-wonder-model-card", "In its model card"),
    "Gemini 4 Argon": ("2026-09-30", "https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-4-argon/",
                       "In the launch post; model card 13 Oct"),
    "Muse Spark Open": ("2026-10-15", "https://huggingface.co/meta-models/Muse-Spark-Open-816B-A42B",
                        "In its model card"),
    "Beam": ("2026-10-16", "https://reflection.ai/beam-safety-report", "With the weights"),
    "Grok 4.7": ("2026-09-21", "https://x.ai/news/grok-4-7", "In the launch post"),
    "Mistral Large 4": ("2026-10-06", "https://mistral.ai/news/mistral-large-4/", "In the launch post"),
    "Gemini Robotics 2": ("2026-07-29", "https://storage.googleapis.com/deepmind-media/gemini-robotics/Gemini-Robotics-2-Safety.pdf", ""),
    "Gemini 3.8 Live": ("", "https://deepmind.google/models/model-cards/gemini-3-8-audio/",
                        "Model card gives no test results for it"),
    "Gemini 3.5 Transcribe": ("", "https://deepmind.google/models/model-cards/gemini-3-5-audio/",
                              "Model card gives no test results for it"),
}
# release stories checked by hand and left out, with why, so they aren't checked again
LEFT_OUT = {
    "https://techcrunch.com/2026/06/30/google-introduces-a-faster-cheaper-image-generator-with-nano-banana-2-lite/":
        "same as Nano Banana 2 Lite",
    "https://deepmind.google/blog/fluid-natural-voice-translation-with-gemini-35-live-translate/":
        "same as Gemini 3.5 Live Translate",
    "https://www.marktechpost.com/2026/04/24/deepseek-ai-releases-deepseek-v4-compressed-sparse-attention-and-heavily-compressed-attention-enable-one-million-token-contexts/":
        "same as DeepSeek V4 Preview",
    "https://huggingface.co/blog/openai-privacy-filter-web-apps": "OpenAI Privacy Filter: one news outlet within 3 days",
    "https://the-decoder.com/googles-i-o-announcements-new-models-a-cloud-agent-that-never-sleeps-and-a-redesigned-gemini-app/":
        "same as Gemini 3.5 Flash and Gemini Omni Flash",
    "https://arstechnica.com/ai/2026/05/googles-gemma-4-open-ai-models-use-speculative-decoding-to-get-up-to-3x-faster/":
        "Gemma 4 MTP drafters: speed-up add-ons for Gemma 4, not a new model",
    "https://openai.com/index/previewing-gpt-5-6-sol": "GPT-5.6 Sol: one news outlet within 3 days",
    "https://the-decoder.com/google-bakes-computer-control-directly-into-gemini-3-5-flash-letting-the-model-see-and-operate-your-screen/":
        "same as Gemini 3.5 Flash",
    "https://mistral.ai/news/ocr-4/": "Mistral OCR 4: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/06/02/alibabas-qwen-team-launches-qwen3-7-plus-adding-vision-deep-reasoning-tool-invocation-and-autonomous-iteration-on-the-bailian-platform/":
        "Qwen3.7-Plus: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/05/21/qwen-introduces-qwen3-7-max-a-reasoning-agent-model-with-a-1m-token-context-window/":
        "Qwen3.7-Max: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/06/02/jetbrains-releases-mellum2-a-12b-moe-model-for-fast-specialized-tasks-in-multi-model-ai-pipelines/":
        "Mellum2: one news outlet within 3 days",
    "https://openai.com/index/introducing-openai-privacy-filter": "OpenAI Privacy Filter: one news outlet within 3 days",
    "https://techcrunch.com/2026/05/20/stability-ai-release-a-new-audio-model-that-can-create-six-minute-songs/":
        "Stable Audio 3.0: some sizes open, the largest closed; its licence terms unclear",
    "https://openai.com/index/advancing-voice-intelligence-with-new-models-in-the-api":
        "GPT-Realtime-2: one news outlet within 3 days",
    "https://github.com/Tencent-Hunyuan/Hy3": "Hy3: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/07/06/openai-gpt-realtime-2-1-mini-reasoning-realtime-api/":
        "GPT-Realtime-2.1: one news outlet within 3 days",
    "https://mistral.ai/news/robostral-navigate/": "Robostral Navigate: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/07/15/soofi-consortium-releases-soofi-s-30b-a3b-an-open-hybrid-mamba-transformer-moe-foundation-model-for-german-and-english/":
        "Soofi S: one news outlet within 3 days",
    "https://siliconangle.com/2026/07/16/nvidia-launches-cosmos-3-edge-model-expands-physical-ai-push-japan/":
        "Cosmos 3 Edge: one news outlet within 3 days",
    "https://deepmind.google/blog/introducing-gemini-3-6-flash-3-5-flash-lite-and-3-5-flash-cyber/":
        "Gemini 3.6 Flash: one news outlet within 3 days",
    "https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash-0731": "DeepSeek V4 Flash 0731: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/08/05/nvidia-alpamayo-2-super-open-vla-model-autonomous-driving/":
        "Alpamayo 2 Super: one news outlet within 3 days",
    "https://techcrunch.com/2026/08/05/meta-launches-muse-code-an-ai-agent-for-large-code-bases/":
        "Muse Code is an agent; its model Muse Spark 1.2 named by one outlet",
    "https://the-decoder.com/alibabas-qwen-team-releases-qwen-3-8-models-with-open-weights-under-the-apache-2-0-license/":
        "Qwen 3.8 (27B): one news outlet within 3 days",
    "https://the-decoder.com/gen-1-5-generalist-ai-teaches-robots-new-tasks-from-a-single-demo/":
        "GEN-1.5: one news outlet within 3 days",
    "https://the-decoder.com/deepseek-releases-experimental-flash-vision-model-that-rivals-opus-4-8-on-agent-benchmarks/":
        "DeepSeek V4 Flash Vision: one news outlet within 3 days",
    "https://the-decoder.com/chatgpt-images-2-5-faster-more-precise-but-not-the-same-for-everyone/":
        "ChatGPT Images 2.5: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/09/06/ifm-releases-k2-horizon-six-apache-2-0-models-from-0-9b-to-375b/":
        "K2 Horizon: one news outlet within 3 days",
    "https://huggingface.co/Qwen/Qwen-Image-2.1": "Qwen-Image-2.1: one news outlet within 3 days",
    "https://siliconangle.com/2026/09/18/prismml-launches-bonsai-2-27b-a-high-intelligence-ai-model-so-small-it-fits-on-consumer-hardware/":
        "Bonsai 2 27B: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/09/20/stepfun-launches-step-5-preview/":
        "Step 5 Preview's API: one news outlet; counted when its weights came out",
    "https://siliconangle.com/2026/09/22/xiaomi-introduces-mimo-v2-6-series-open-source-ai-model-family/":
        "MiMo-V2.6: one news outlet within 3 days",
    "https://the-decoder.com/alibaba-launches-qwen-audio-3-1-with-five-new-models-and-slashes-ai-audio-prices-by-up-to-95-percent/":
        "Qwen Audio 3.1: one news outlet within 3 days",
    "https://pandaily.com/meituan-longcat-2-5-preview-1-6t-moe-multimodal-agent-1m-context":
        "LongCat-2.5-Preview: one news outlet within 3 days",
    "https://the-decoder.com/odyssey-3-is-a-new-generative-world-model-that-you-can-try-for-free/":
        "Odyssey-3: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/10/09/alibaba-qwen-releases-qwen-image-2-1-turbo-an-8-step-7b-image-model/":
        "Qwen-Image-2.1-Turbo: one news outlet within 3 days",
    "https://blog.cloudflare.com/clef-faster-cheaper-multimodal/": "Clef-omni: one news outlet within 3 days",
    "https://www.liquid.ai/blog/lfm2-5-24b-a2b": "LFM2.5-24B-A2B: one news outlet (and Hugging Face's blog) within 3 days",
    "https://www.liquid.ai/blog/d1-ultra": "d1-ultra: one news outlet within 3 days",
    "https://api-docs.deepseek.com/news/news261017": "DeepSeek V4.1 Flash 1017: one news outlet within 3 days",
    "https://pandaily.com/skywork-matrix-game-4-open-source-game-engine-real-time-neural-rendering-rtx-5090":
        "Matrix-Game 4.0: one news outlet within 3 days",
    "https://the-decoder.com/kling-ai-drops-version-4-0-with-stereo-audio-multilingual-lip-sync-and-a-lighter-flash-variant/":
        "Kling 4.0: its weights, price and home country are not stated in the stories",
    "https://techcrunch.com/2026/10/19/nvidia-launches-new-open-models-to-run-agents-in-the-enterprise-and-on-pcs/":
        "same as Nemotron 3.5 Super VL and Nemotron 3.5 Bolt 74B-A9B 24GB",
    "https://siliconangle.com/2026/10/19/ai-developer-doubleai-debuts-maxwell-code-execution-model/":
        "Maxwell: one news outlet within 3 days",
    "https://ollama.com/blog/clef": "same as Clef",
    "https://aws.amazon.com/blogs/machine-learning/pegasus-1-5-from-twelvelabs-is-now-available-in-amazon-bedrock/":
        "Pegasus 1.5: no news outlet within 3 days (a hosting blog only)",
    "https://pandaily.com/ace-robotics-ace-brain-0-6-9b-visual-grounding-spatial-supervision-qwen3-5-gpt-6-astra":
        "ACE-Brain-0.6: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/10/18/mistral-timestral-time-series-foundation-model/":
        "Timestral: one news outlet within 3 days",
    "https://www.marktechpost.com/2026/10/19/minimax-m3-1-flash-release/": "same as MiniMax M3.1 Flash",
    "https://siliconangle.com/2026/10/19/minimax-launches-m3-1-flash-model-says-it-cuts-ai-agent-costs-by-70/":
        "same as MiniMax M3.1 Flash",
}
# the newest day every story was read for RELEASES and LEFT_OUT; the candidates start after it. The daily job moves
# it on to the last day it checked, so stories that aren't model releases need no entry
CHECKED_TO = "2026-10-19"
WINDOW = 3  # days a release has to be reported by a second outlet; a story is checked once they are over
# a headline from another stream that may be a model release: a release word and a model (the word, weights, or a
# name with a version number: "Grok 4.7", "Kimi K3", "GLM-5.3"), and not hardware, a product plan or a platform
_RELEASE = re.compile(r"\b(releases?|launch(es)?|introduc(es|ing)|unveils?|debuts?|open-sources?|drops|rolls out|ships|"
                      r"publishes|now available|is available|open weights?|open-weights?)\b", re.I)
_MODEL = re.compile(r"(?i:\b(models?|weights|llms?)\b)|\b[A-Z][\w.]*[- ]?[A-Z]?\d+(\.\d+)?\b")
_NOT = re.compile(r"\b(chips?|GPUs?|CPUs?|racks?|servers?|TV|HomePod|phones?|laptops?|platforms?|subscriptions?|"
                  r"plans|benchmark|harness|framework|sandbox|lines?|residency|funding|raises)\b", re.I)


def safety_due(today: date | None = None) -> list[str]:
    """Releases still without a safety report that the daily job should look for again: launched RECHECK days ago or
    less."""
    since = ((today or date.today()) - timedelta(days=RECHECK)).isoformat()
    return [m for d, _, m, *_ in sorted(RELEASES, reverse=True) if d >= max(since, SINCE) and not SAFETY.get(m, ("",))[0]]


def candidates(cards: list[dict], since: str = "", today: date | None = None) -> list[dict]:
    """Stories from after CHECKED_TO (or `since`, if later) up to WINDOW days ago, that no row uses and LEFT_OUT
    doesn't hold: every Releases story (but GitHub versions), and other streams' headlines that look like a model
    release. Newest first. Each needs a second outlet found among the stories, then the row's facts checked."""
    since = max(since, CHECKED_TO + "~")  # '~' sorts after any time of day, so CHECKED_TO itself is done
    until = ((today or date.today()) - timedelta(days=WINDOW)).isoformat() + "~"
    used = {r[10] for r in RELEASES} | set(LEFT_OUT)
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if since <= c["date"] <= until and "releases version" not in c["title"]
            and not any(s["url"] in used for s in [c, *(c.get("also") or [])])
            and (c.get("category") == "tool" or any(_RELEASE.search(s["title"]) and _MODEL.search(s["title"])
                                                    and not _NOT.search(s["title"])
                                                    for s in [c, *(c.get("also") or [])]))]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a releases/<day> branch: each release it adds or finds a safety report for, and
    the stories it left out; None when it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("RELEASES", "LEFT_OUT", "SAFETY"))

    def report(d: str, m: str) -> str:
        s = safety(d, m)
        said = {"day": "Day one", "later": f"{s['late']} day{'s' * (s['late'] != 1)} later", "none": "None found"}
        return said[s["when"]] + (f" ({s['url']})" if s["url"] and s["when"] != "none" else "")
    rows = [(d, lab, m, w, lic or "–", (p.split("|")[0] or "–"), report(d, m), u)
            for d, lab, m, w, _, lic, _, _, _, p, u, _ in RELEASES
            if u not in had["RELEASES"] or SAFETY.get(m, ("", ""))[1] not in had["SAFETY"] | {""}]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("Release cards", f"release{'s' * (len(rows) != 1)}", branch,
                        ("Day", "Lab", "Model", "Weights", "Licence", "Price", "Safety report", "Source"), rows, dropped)


def safety(day: str, model: str) -> dict:
    """When the release's safety report came: "day" (on or before launch), "later" with its days, or "none"."""
    on, url, note = SAFETY.get(model, ("", "", ""))
    late = (date.fromisoformat(on) - date.fromisoformat(day)).days if on else 0
    last = (date.fromisoformat(day) + timedelta(days=RECHECK)).isoformat()  # the last day it is looked for
    return {"when": "none" if not on else "later" if late > 0 else "day", "late": late, "url": url, "note": note,
            "checked": min(SAFETY_CHECKED, max(last, FIRST_CHECKED))}


def rows() -> list[dict]:
    return [{"day": d, "lab": lab, "country": COUNTRY.get(lab, ""), "model": m, "weights": w, "note": n, "licence": lic,
             "limit": lim, "where": where, "out": out, "price": p, "url": u, "hf": hf, "safety": safety(d, m)}
            for d, lab, m, w, n, lic, lim, where, out, p, u, hf in sorted(RELEASES, key=lambda r: r[0], reverse=True)
            if d >= SINCE]


_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _day(d: str) -> str:
    y, m, day = d.split("-")
    return f"{int(day)} {_MONTHS[int(m) - 1]} {y}"


def _row(r: dict) -> str:
    small = lambda t: f"<small>{escape(t)}</small>" if t else ""  # noqa: E731
    tag = {"Open": "rc-open", "Weights only": "rc-wo", "Closed": "rc-closed"}[r["weights"]]
    lic = (f'<a href="{escape(r["hf"])}" rel="noopener">{escape(r["licence"])}</a>' if r["hf"] else escape(r["licence"])) \
        if r["licence"] else "–"
    price, _, why = r["price"].partition("|")
    where = escape(r["where"]) if r["where"] else '<span class="rc-none">No limits stated</span>'
    text = escape(" ".join((r["model"], r["lab"], r["country"], r["licence"])).lower(), quote=True)
    s = r["safety"]
    said = {"day": "Day one", "later": f"{s['late']} day{'s' * (s['late'] != 1)} later",
            "none": "None found"}[s["when"]]
    pill = f'<span class="rc-w rc-s-{s["when"]}">{said}</span>'
    link = s["url"] and s["when"] != "none"
    checked = f"checked {_day(s['checked']).rsplit(' ', 1)[0]}" if s["when"] == "none" else ""
    report = (f'<a href="{escape(s["url"])}" rel="noopener">{pill}</a>' if link else pill) + small(checked) \
        + small(s["note"])
    return (f'<tr data-w="{r["weights"]}" data-out="{"1" if r["out"] else ""}" data-s="{s["when"]}" '
            f'data-text="{text}">'
            f'<td class="rm-d">{_day(r["day"])}</td>'
            f'<td class="rc-m"><a href="{escape(r["url"])}" rel="noopener">{escape(r["model"])}</a>'
            f'{small(r["lab"] + (" · " + r["country"] if r["country"] else ""))}</td>'
            f'<td><span class="rc-w {tag}">{escape(r["weights"])}</span>{small(r["note"])}</td>'
            f'<td>{lic}{small(r["limit"])}</td>'
            f'<td{" class=rc-out" if r["out"] else ""}>{where}</td>'
            f'<td class="rc-p{" rc-p0" * (not price)}">{escape(price) or "–"}{small(why)}</td>'
            f'<td class="rc-s">{report}</td></tr>')


def _filters(rs: list[dict]) -> str:
    """One row of tags: weights, then the releases that left places out; and a search of models, labs, countries."""
    items = [("w", w, w, sum(r["weights"] == w for r in rs)) for w in WEIGHTS] + \
            [("out", "1", "Left some places out", sum(r["out"] for r in rs)),
             ("s", "day", "Safety report on day one", sum(r["safety"]["when"] == "day" for r in rs))]
    return ('<div class="sh-filters rm-filters"><div class="sh-tabs" role="group" aria-label="Show">'
            f'<button type="button" class="sh-tab" data-f="" data-v="" aria-pressed="true">All <b>{len(rs)}</b></button>'
            + "".join(f'<button type="button" class="sh-tab" data-f="{f}" data-v="{v}" aria-pressed="false">{escape(t)} '
                      f'<b>{n}</b></button>' for f, v, t, n in items if n) + "</div>"
            '<input type="search" class="sh-q" placeholder="Search models, labs or countries" '
            'aria-label="Search models, labs or countries">'
            f'<p class="sh-count" aria-live="polite">Showing <b>{len(rs)}</b> of {len(rs)} releases</p></div>\n')


# the filters, in the reader's browser: one tag at a time, and every word typed in the search
SCRIPT = """<script>
(()=>{const pg=document.querySelector('.rc'),rows=[...pg.querySelectorAll('tbody tr[data-w]')],q=pg.querySelector('.sh-q'),
count=pg.querySelector('.sh-count b'),none=pg.querySelector('.sh-none');let f='',v='';
function run(){const words=q.value.toLowerCase().split(/\\s+/).filter(Boolean);let n=0;
rows.forEach(r=>{const ok=(!f||r.dataset[f]===v)&&words.every(w=>r.dataset.text.includes(w));r.hidden=!ok;n+=ok});
count.textContent=n;none.hidden=n>0}
pg.querySelectorAll('.sh-tab').forEach(b=>b.addEventListener('click',()=>{f=b.dataset.f;v=b.dataset.v;
pg.querySelectorAll('.sh-tab').forEach(t=>t.setAttribute('aria-pressed',t===b));run()}));
q.addEventListener('input',run)})();
</script>"""


def body(rs: list[dict]) -> str:
    since = _day(SINCE).rsplit(" ", 1)[0]
    down = [r for r in rs if r["weights"] != "Closed"]
    china = sum(r["country"] == "China" for r in down)
    bigs = [(f"{len(down)} of {len(rs)}", f"major releases since {since} came with weights you can download"),
            (f"{china}", f"of those {len(down)} came from labs in China"),
            (f"{sum(r['out'] for r in rs)}", f"releases since {since} left some places out at launch"),
            (f"{sum(r['safety']['when'] == 'day' for r in rs)} of {len(rs)}",
             f"major releases since {since} had a report of their safety tests out on launch day")]
    limits = [
        ("What counts", "A new AI model that at least two news outlets reported within three days of its launch. The "
         "lab's own posts, its partners' blogs and hosting services don't count towards the two."),
        ("Weights", "Open: you can download them and use them commercially, though some licences ask big companies "
         "for a deal. Weights only: you can download them, but the licence bars commercial use. Closed: nothing to "
         "download."),
        ("Licence", "Named as the lab names it, linking to the model's Hugging Face page; under it, the main limit "
         "from the licence text."),
        ("Where you can use it", "Only places the lab or a story names. \"No limits stated\" means neither names "
         "any, not that it works everywhere."),
        ("Launch price", "The lab's own API price on launch day, in US dollars, for 1 million tokens in and out "
         "unless the cell says otherwise. Left blank when the lab sold no API access at launch."),
        ("Safety report", "The lab's first document giving results of its safety tests on the model: a system card, "
         "a safety report, a launch post that gives results, or a model card or technical report with a safety "
         "section that gives them. Day one: out by launch day. \"None found\" means none was on the lab's own pages "
         "on the date shown; a line saying the model was tested, with no results, doesn't count."),
        ("Each model", "Links to the story or lab page its facts were checked against."),
    ]
    return ('<div class="ft jb rm rc">\n'
            + pages.feature_head(PATH, "Release cards", "What came out and can I use it?",
                                 f"Every major AI model release since {since}, newest first: whether you can download "
                                 "it, under what licence, where you can use it, its price at launch and whether the "
                                 "lab published its safety test results. Each row is "
                                 "checked by hand against the lab's own page, its licence text or Hugging Face.")
            + '<div class="rm-bigs">' + "".join(f'<div class="rm-big"><b>{escape(n)}</b><span>{escape(s)}</span></div>'
                                              for n, s in bigs) + "</div>\n"
            + _filters(rs)
            + '<div class="rm-wrap"><table class="mt rm-t rc-t"><thead><tr><th>Released</th><th>Model</th>'
              '<th>Weights</th><th>Licence</th><th>Where you can use it</th>'
              '<th>Launch price (in / out, per 1M tokens)</th><th>Safety report</th></tr></thead><tbody>'
            + "".join(_row(r) for r in rs) + "</tbody></table></div>\n"
            '<p class="sh-none" hidden>No release matches. Clear the tag or the search.</p>\n'
            '<section class="jb-lim"><h2>About these releases</h2>\n<table class="mt jb-small jb-limits"><tbody>'
            + "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
            + "</tbody></table></section></div>\n" + SCRIPT)


def build(conn, cards: list[dict], out: Path, today) -> list[str]:
    rs = rows()
    if not rs:
        return []
    what = ("What came out and can I use it? Every major AI model release since July 2026: whether you can download "
            "it, under what licence, where you can use it and its price at launch, each checked by hand.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Release cards", "description": what,
            "url": f"{rss.SITE}{PATH}"}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(
        pages.page("Release cards · AI Pulse", what, PATH, body(rs), data, pages.frame(conn, len(cards)),
                   ("/releases/", "Back to Releases"),
                   "Licences, prices and places are as the labs and stories give them, each model linking to its "
                   "source. New releases are added once checked by hand."),
        encoding="utf-8")
    return [PATH]
