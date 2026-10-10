# AI Pulse

A free, non-commercial, worldwide briefing on AI. It reads 209 public sources, keeps only AI stories, sorts them into
six streams and links every card to the original.

**Live site:** https://projectaipulse.com/ · **Version 2** (3 October 2026)

## Streams

| Stream | What's in it | Updated |
|---|---|---|
| **Releases** | New models, products and open-source launches | Labs every 30 min; the rest every 6 h |
| **Industry** | Company news, deals, AI incidents, studies, opinion | Every 6 h |
| **Research** | Papers only | Every 6 h |
| **Regulation tracker** | AI proposals, laws, bodies and standards, by country | Every 6 h |
| **Policy** | What governments, courts and politicians do about AI | Every 6 h |
| **Infra & climate** | AI's data centres and their power, water, land and emissions | Every 6 h |

## Features

- **Site:** a front page (a ticker of the latest stories, Today in AI, the week's story, word and meme, each stream's top three, and what people are discussing), a page per stream, filters and search back to 2023, dark mode, an [About page](https://projectaipulse.com/about/).
- **One card per event**, in English (offline translation where needed).
- **Daily or weekly email** of the streams you pick, with a word and meme of the day.
- **Weekly dossier:** your own questions, answered with the week's stories.
- **Pages:** [AI laws by country](https://projectaipulse.com/tracker/), [AI standards](https://projectaipulse.com/standards/), [glossary](https://projectaipulse.com/glossary/).
- **RSS:** one feed per stream, or [all at once](https://projectaipulse.com/feeds/all.opml).

## How we keep it legal

1. **robots.txt must allow us**, checked before every request. github.com pages are never read, only GitHub's API.
2. **Terms:** news and other sites are read only if their terms don't forbid robots or limit use to personal use. AI labs' and companies' own blogs: robots.txt decides.
3. **No workarounds:** nothing behind a login, bot check or paywall.
4. **Only what's needed:** headline, short description, date and link.
5. **Credit and non-commercial use**, as the licences ask.
6. **No tracking:** see the [privacy page](https://projectaipulse.com/privacy.html).

Every source's robots.txt and terms were audited on 7 October 2026. The evidence for each is in `aipulse/terms.py`;
`python -m aipulse audit` checks them again. Questions: projectaipulse@gmail.com.

## Sources

| Stream | Sources |
|---|---|
| Releases (blogs) | OpenAI, Anthropic, Google AI, Google Gemini, Google DeepMind, Google Research, Google Cloud, Google Developers, Meta AI, Microsoft Research, NVIDIA, AWS, Hugging Face, GitHub, Databricks, Mistral, DeepSeek, Cohere, Moonshot AI, MiniMax, Sakana AI, Sarvam AI, Thinking Machines, Black Forest Labs, Liquid AI, Reflection AI, Stability AI, Midjourney, Runway, Cognition, Poolside, Reka, Figure, Character.AI, Ollama, Cloudflare, PyTorch, Together AI, ElevenLabs, Engineering at Meta |
| Releases (newsrooms and release notes) | Microsoft, Meta, Amazon, Apple, xAI, Perplexity |
| Releases (GitHub API) | 17 labs: OpenAI, Anthropic, Meta Llama, Hugging Face, NVIDIA, Mistral AI, xAI, DeepSeek, Qwen, Moonshot AI, MiniMax, Z.ai, StepFun, Tencent Hunyuan, ByteDance Seed, Baidu, Ant Group |
| Releases (Hugging Face API) | 47 labs: OpenAI, Meta, Google, Microsoft, NVIDIA, Apple, Amazon, IBM, Mistral AI, xAI, DeepSeek, Qwen, Moonshot AI, MiniMax, Z.ai, StepFun, Tencent, ByteDance Seed, Baidu, Ant Group, Cohere, Hugging Face, Black Forest Labs, Stability AI, Ai2, Liquid AI, Xiaomi MiMo, Aleph Alpha, Sarvam AI, Nous Research, Kyutai, AI21 Labs, OpenBMB, LG AI Research, Upstage, Meituan, Lightricks, Wan, TII Falcon, Salesforce, ServiceNow, Prime Intellect, Nari Labs, Sesame, Resemble AI, Swiss AI |
| Releases (labs' APIs) | Anthropic, OpenAI |
| Industry | **Global:** TechCrunch, The Decoder, SiliconANGLE, MarkTechPost, 404 Media, Engadget, MIT News, ScienceDaily, The Conversation, Quanta Magazine, Global Voices · **Asia:** Pandaily, Focus Taiwan, Bernama, VnExpress International, The Elec, BusinessKorea, BRIDGE · **Africa:** TechCabal, iAfrikan, TechCentral, ITWeb, IT News Africa, Nairametrics · **MENA:** Wamda · **Latin America:** MercoPress, Buenos Aires Times, LatinAmerica Reports, Contxto · **Practitioners:** Simon Willison, Lil'Log, METR · **Incidents:** AI Incident Database (CC BY-SA 4.0) |
| Research | arXiv, Hugging Face Daily Papers, Apple Machine Learning Research |
| Policy | EU AI Act Newsletter, CSET, AI Now Institute, Future of Life Institute, EFF, EPIC, NIST, Federal Register (US), GOV.UK, Korea's Ministry of Science and ICT, Malaysia's Ministry of Digital, Russia's State Duma, ISED Canada, CLTC (UC Berkeley), ITU, Partnership on AI, Smart Africa, NTIA, DARPA, NSF, UK AI Security Institute |
| Infra & climate | **Global:** Carbon Brief, Climate Home News, Mongabay, The Conversation, Data Center Knowledge, Data Center POST, Greenpeace International, Global Energy Monitor · **Europe:** European Commission (energy) · **UK:** GOV.UK, Techerati, DCNN · **Africa:** Africa Data Centres Association · **Asia-Pacific:** W.Media · **North America:** US Energy Information Administration, Canary Media, POWER Magazine, Union of Concerned Scientists, Southern Environmental Law Center, Food & Water Watch, Energy Innovation |
| People are discussing (front page) | Hacker News, through its [official API](https://github.com/HackerNews/API) (robots.txt allows its .json files): the most-discussed AI threads of the last 2 days, titles and comment counts only, every 6 h |
| Regulation tracker | European Data Protection Board, European Commission (Digital Strategy), and the official records below |

### Official records (Regulation tracker)

AI laws and bills, and each place's main data protection law with the bills amending it (not every privacy bill).

| Place | Source | Legal basis |
|---|---|---|
| United States | congress.gov API | Official API, free key; public domain |
| European Union | European Parliament open data | Reuse with credit |
| United Kingdom | UK Parliament Bills API | Open Parliament Licence v3.0 |
| Canada | Canada Gazette, Parts I and II | No robots.txt rules; non-commercial reproduction with credit |
| Brazil | Câmara dos Deputados open data | Open data |
| Australia | Federal Register of Legislation | CC BY 4.0 |
| China | Cyberspace Administration of China | Title, date and link only; regulations aren't copyrighted |
| India | Parliament of India (sansad.in) | Public API; no restriction on automated use |
| Japan | e-Gov law API | Government of Japan Standard Terms of Use 2.0 |
| South Korea | National Law Information Center (law.go.kr) | robots.txt allows; laws aren't copyrighted |
| Taiwan | Legislative Yuan law system | No robots.txt rules; laws aren't copyrighted |
| Malaysia | Parliament of Malaysia | No robots.txt rules or restricting terms |
| Vietnam | National Legal Database (vbpl.vn) | robots.txt allows; legal documents aren't copyrighted |
| Switzerland | Swiss Parliament open data | Open use with source |
| Ireland | Houses of the Oireachtas open data API | Oireachtas (Open Data) PSI Licence (CC BY 4.0) |
| Norway | Stortinget open data | Norwegian Licence for Open Government Data (NLOD), Stortinget credited |
| ~60 more countries and bodies (UN, UNESCO, G7, AU, ASEAN…) | OECD.AI Policy Observatory | CC BY 4.0 |
| International AI standards | ISO/IEC and IEEE, kept by hand | Facts only (number, title, date, link) |

## Run it

```bash
python -m aipulse collect     # fetch every source into aipulse.db
python -m aipulse serve       # http://127.0.0.1:8000
python -m aipulse audit       # check every source's robots.txt and terms again
python -m pytest -q           # tests (run locally)
```

Hosted on GitHub Pages (`.github/workflows/pages.yml`); the email is sent by `.github/workflows/digest.yml` and
sign-ups go to a Google Apps Script web app (`apps-script/Code.gs`). The domain (about $11 a year) is the only cost.

## Credits and licences

European Parliament, European Commission and EDPB content: © European Union, reused with acknowledgement of the source. UK Parliament data: Open Parliament Licence v3.0. GOV.UK and UK AI Security Institute: Open Government Licence v3.0. Federal Register,
congress.gov, US Energy Information Administration, DARPA and NSF: US public domain. ITU: non-commercial use with credit. Canada: Canada Gazette and ISED content reproduced from gazette.gc.ca and canada.ca, not affiliated with or endorsed by the Government of Canada.
Swiss parliamentary records: The Federal Assembly — The Swiss Parliament, open data. Korean laws: National
Law Information Center (https://www.law.go.kr), Ministry of Government Legislation. Taiwanese laws:
Legislative Yuan law system (https://lis.ly.gov.tw). Malaysian bills: Parliament of Malaysia
(https://www.parlimen.gov.my). Russian parliamentary news: State Duma (http://duma.gov.ru). OECD.AI Policy
Observatory (https://oecd.ai): CC BY 4.0. Japanese laws: e-Gov Law Search (https://laws.e-gov.go.jp),
Government of Japan Standard Terms of Use 2.0; titles machine-translated by AI Pulse. Vietnamese legal
documents: National Legal Database (https://vbpl.vn). Australian legislation: based on content from the
Federal Register of Legislation (CC BY 4.0); for the latest information go to https://www.legislation.gov.au.
Irish bills: Houses of the Oireachtas (https://www.oireachtas.ie), Oireachtas (Open Data) PSI Licence, which
incorporates CC BY 4.0. Norwegian proposals: Stortinget (https://data.stortinget.no), Norwegian Licence for Open
Government Data (NLOD); titles machine-translated by AI Pulse.
AI incidents: [AI Incident Database](https://incidentdatabase.ai) (Responsible AI Collaborative), incident titles and descriptions CC BY-SA 4.0 (shared here under the same licence). Translations: OPUS-MT (Helsinki-NLP, CC BY 4.0) via Argos Translate (MIT). Logos: [Lobe Icons](https://github.com/lobehub/lobe-icons)
(MIT, © 2023 LobeHub), [Simple Icons](https://simpleicons.org) (CC0) (no icons are fetched from brands' own sites). Fonts: Archivo Black, Archivo, Anton and IBM Plex Mono (SIL Open Font License 1.1), served
from this site. Section icons: [Phosphor Icons](https://phosphoricons.com) (MIT, © 2023 Phosphor Icons).
Meme templates: via [Imgflip](https://imgflip.com), used as parody and commentary. Flags: [flag-icons](https://github.com/lipis/flag-icons) (MIT, © 2013 Panayiotis Lipiridis), served from this site.
Photos: 84 openly licensed photos from [Wikimedia Commons](https://commons.wikimedia.org) (CC BY, CC BY-SA, CC0 or public
domain), chosen to illustrate a story's topic, resized and recoloured; each photo's author, licence and source are on the site's Photo credits page.
