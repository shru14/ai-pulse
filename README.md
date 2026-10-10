# AI Pulse

A free, non-commercial, worldwide briefing on AI. It reads 203 public sources (121 feeds and news pages, 17 AI labs' GitHub
organisations, 47 AI labs' Hugging Face organisations, 18 official records and databases), keeps only AI stories, sorts them into six streams and links every card to the original.

**Live site:** https://projectaipulse.com/ · **Version 2** (3 October 2026)

Only legal, publicly accessible sources are used.

## Streams

| Stream | What's in it | Updated |
|---|---|---|
| **Releases** | New models, products and open-source launches | Lab and company blogs and model lists every 30 min; the rest every 6 h |
| **Industry** | Company news, deals and market moves, labelled **News**, **AI-incident**, **Study**, **Opinion & analysis**, **Company blog**, **Tutorial** or **Event** | Every 6 h |
| **Research** | Papers only: by ~120 leading AI and AI-ethics scholars, and big labs | Every 6 h (arXiv publishes on weekdays) |
| **Regulation tracker** | AI proposals, laws, bodies and standards, by country | Every 6 h; Korea, Vietnam and OECD.AI weekly; standards by hand |
| **Policy** | What governments, courts and politicians do about AI | Every 6 h |
| **Infra & climate** | AI's data centres and their power, water, land and emissions | Every 6 h |

## Features

- **Site:** a weekly front page (new each Monday): last week's story, word and meme, then each stream's top stories of that week; a page per stream; yesterday's full table; colour-blind-safe colours.
- **Filters and search:** stream, region, country and time range; search back to 2023.
- **English throughout:** the publisher's English version, else an offline translation (marked).
- **One card per event:** the same story from several outlets is grouped.
- **Glossary:** plain-English meanings of ~130 hard words.
- **Memes:** on well-known templates via imgflip.com, as parody; captions checked (no politics, harm, people or invented numbers), else rule-based.
- **RSS:** one feed per stream ([Releases](https://projectaipulse.com/feeds/releases.xml), [Industry](https://projectaipulse.com/feeds/news.xml), [Research](https://projectaipulse.com/feeds/research.xml), [Regulation tracker](https://projectaipulse.com/feeds/regulation.xml), [Policy](https://projectaipulse.com/feeds/policy.xml), [Infra & climate](https://projectaipulse.com/feeds/infra.xml)), or [all at once](https://projectaipulse.com/feeds/all.opml) (OPML).
- **Daily email:** the reader's streams: word and meme of the day, the top 10 (the reader's choices first), the rest in brief; checked before sending, dead links left out. On Sundays, the week's story, word and meme instead. Daily, or weekly (Sundays only).
- **Weekly dossier:** up to 3 questions in the reader's own words, asked on its own page from the button in every Sunday email, answered there at once and each Sunday: the week's stories that answer them, found by an open model (BGE-base; offline for the email, in the reader's browser on the page) and the site's tags. It picks and links; it writes nothing.
- **AI laws by country:** a [page per country](https://projectaipulse.com/tracker/) of the tracker's official records, with each bill's stages.
- **AI standards:** [one page](https://projectaipulse.com/standards/) of every AI standard on the tracker (ISO/IEC, IEEE, national), with what each covers.
- **Industry by kind:** a page each for [opinion](https://projectaipulse.com/industry/opinion/), company blogs, studies, AI incidents, tutorials and events (the last 3 months, newest first).
- **AI glossary:** a [page per word](https://projectaipulse.com/glossary/) (130 words, written by hand), with related terms, the words often in the same stories and its latest stories.
- **Open data:** the tracker's official records as a [CSV](https://projectaipulse.com/tracker.csv): date, country, type, title, source and link.
- **Make it yours:** more of, or leave out, any topic, company, place or scholar, plus up to 5 own words.
- **Subscriptions:** confirm by one link, unsubscribe in one click. Addresses and questions stay in the project's Google account, never in this repository or its logs.

## How we keep it legal

1. **robots.txt must allow us**, checked before every request; the only exceptions are official APIs whose terms allow programmatic use (arXiv, Wikidata, congress.gov, jsDelivr). The reverse holds for GitHub: its robots.txt lets us read its pages, but its terms allow scraping them only for research or archiving, so github.com pages are never read and only its API is used.
2. **Terms must allow** showing a headline, a short description and a link. A site whose terms forbid robots or scrapers, or allow personal use only, isn't read, even when its robots.txt lets us in. AI labs' and companies' own blogs follow the owner's rule for them instead (from 10 October 2026): robots.txt decides, and a blog without one may be read. Where a feed's own terms allow its text only unmodified (TechCrunch, Engadget, ScienceDaily), it is shown exactly as the feed gives it, and ScienceDaily's stored headlines are capped at 40 as its terms ask.
3. **No workarounds:** nothing behind a login, bot check or paywall; sites that block automated readers aren't read.
4. **Only what's needed:** headline, short description, date and link. No personal data.
5. **Credit and non-commercial use**, as the licences below require.
6. **Readers' privacy:** the site and email load nothing from other servers and track no one. What the daily email keeps, why and for how long is on the [privacy page](https://projectaipulse.com/privacy.html). Questions: projectaipulse@gmail.com.

Every source's robots.txt and terms were audited on 7 October 2026. Dropped then, with every story they gave: South China Morning Post, MIT Technology Review, The Verge, Ars Technica, ZDNET, Tech Xplore, The Rio Times, Semiconductor Digest, ServeTheHome, Data Centre Review, Capacity Media, iTnews, ESI Africa and Energy Monitor. A publisher that gives permission is added back, with the permission credited below. The AI labs' and companies' own blogs dropped then (OpenAI, Anthropic, Meta, Microsoft, NVIDIA, Apple, Amazon, AWS, Databricks, GitHub, Hugging Face, Perplexity, xAI, Character.AI, Stability AI, Ollama, DeepSeek, Cohere and Moonshot AI) are read again since 10 October 2026, under the rule for labs' blogs above. Alongside them, the labs' new open models and tools are tracked through GitHub's API, which GitHub's terms allow ("Scraping does not refer to the collection of information through our API"). Their open models are tracked through Hugging Face's API, whose terms say nothing against automated access; only a model's name, date and likes are read. Anthropic's and OpenAI's own model lists, closed models included, are read through their APIs once the project's free keys are set: both companies' terms ban scraping their websites but allow access through the API.

The evidence for every source, and for the official records, icons, photos and data the platform uses (its terms page, what it says and the date it was read), is kept in `aipulse/terms.py`; a source without it can't be added. `python -m aipulse audit` reads every terms page again and reports any that changed; it runs monthly and before any new source.

Requests go one at a time with pauses and identify themselves as `AIPulse/1.0`. AI Pulse's own robots.txt lets search engines in and keeps AI-training bots out.

## Sources

| Stream | Sources |
|---|---|
| Releases (feeds) | OpenAI, Hugging Face, Microsoft Research, NVIDIA, AWS Machine Learning, Engineering at Meta, GitHub, Databricks, Ollama, Character.AI, Stability AI, Google AI, Google DeepMind, Google Research, Google Cloud (AI), Mistral, Cloudflare, Sakana AI, PyTorch, Together AI, ElevenLabs, Sarvam AI, Thinking Machines, Midjourney (not its weekly changelogs) |
| Releases (news pages, no feed) | Anthropic, Meta AI, DeepSeek, Cohere, Moonshot AI, MiniMax, Google Developers Blog, Black Forest Labs, Liquid AI, Reflection AI, Cognition, Poolside, Reka, Figure |
| Releases (GitHub API: a lab's new repositories that 300+ people starred, back to 2023) | OpenAI, Anthropic, Meta Llama, Hugging Face, NVIDIA, Mistral AI, xAI, DeepSeek, Qwen, Moonshot AI, MiniMax, Z.ai, StepFun, Tencent Hunyuan, ByteDance Seed, Baidu, Ant Group (inclusionAI) |
| Releases (Hugging Face API: a lab's open models, one story per release with all its sizes, only releases 300+ people liked, back to 2023) | OpenAI, Meta Llama, Meta, Google, Microsoft, NVIDIA, Apple, Amazon, IBM Granite, Mistral AI, xAI, DeepSeek, Qwen, Moonshot AI, MiniMax, Z.ai, StepFun, Tencent, ByteDance Seed, Baidu, Ant Group (inclusionAI), Cohere Labs, Hugging Face, Black Forest Labs, Stability AI, Ai2, Liquid AI, Xiaomi MiMo, Aleph Alpha, Sarvam AI, Nous Research, Kyutai, AI21 Labs, OpenBMB, LG AI Research, Upstage, Meituan LongCat, Lightricks, Wan (Alibaba), TII Falcon, Salesforce, ServiceNow, Prime Intellect, Nari Labs, Sesame, Resemble AI, Swiss AI |
| Releases (developer release notes: only the lab's own launches) | xAI, Perplexity |
| Releases (company newsrooms: only stories that name AI in the headline) | Microsoft, Meta, Amazon, Apple |
| Releases (labs' own APIs: every model they serve, once the key is set) | Anthropic, OpenAI |
| Industry | **Global:** TechCrunch, The Decoder, SiliconANGLE, MarkTechPost, 404 Media, Engadget, MIT News, ScienceDaily, The Conversation (AI), Quanta Magazine, Global Voices · **Asia:** Pandaily, Focus Taiwan, Bernama, VnExpress International · **Africa:** TechCabal, iAfrikan, TechCentral, ITWeb, IT News Africa, Nairametrics · **MENA:** Wamda · **Latin America:** MercoPress, Buenos Aires Times, LatinAmerica Reports · **Practitioners and evaluators:** Simon Willison, Lil'Log, METR |
| AI incidents (Industry) | AI Incident Database (CC BY-SA 4.0) |
| Research | arXiv (listed professors and scholars, and papers on AI's own energy, carbon, water and power, tagged Infra & climate), Hugging Face Daily Papers, Apple Machine Learning Research |
| Policy | EU AI Act Newsletter, CSET, AI Now Institute, Future of Life Institute, EFF, EPIC, NIST, Federal Register (US), GOV.UK, Korea's Ministry of Science and ICT, Malaysia's Ministry of Digital, Russia's State Duma (English news), Innovation, Science and Economic Development Canada, CLTC (UC Berkeley), ITU, Partnership on AI, Smart Africa, NTIA, DARPA, NSF, UK AI Security Institute |
| Infra & climate | **Global:** Carbon Brief, Climate Home News, Mongabay, The Conversation (energy), Data Center Knowledge, Data Center POST, Greenpeace International, Global Energy Monitor · **Europe:** European Commission (energy) · **United Kingdom:** GOV.UK (data centres: planning, permits, statistics), Techerati, DCNN · **Africa:** Africa Data Centres Association · **Asia-Pacific:** W.Media · **North America:** US Energy Information Administration, Canary Media, POWER Magazine, Union of Concerned Scientists, Southern Environmental Law Center, Food & Water Watch, Energy Innovation |
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
python -m aipulse audit       # robots.txt and terms of every source, again (monthly, on a PC)
python -m pytest -q           # tests (run locally, not on GitHub)
```

## Hosting

- **Site:** GitHub Pages (`.github/workflows/pages.yml`), every 6 hours and on every push.
- **Domain:** projectaipulse.com, about $11 a year (the project's only cost).
- **Daily email:** `.github/workflows/digest.yml`, from 05:12 UTC.
- **Sign-ups:** `apps-script/Code.gs`, a Google Apps Script web app in the project's Google account.

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
