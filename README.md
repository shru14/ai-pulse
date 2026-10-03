# AI Pulse

A free, non-commercial, worldwide briefing on AI. It reads ~90 public sources, keeps only AI stories, sorts
them into six streams and links every card to the original.

**Live site:** https://shru14.github.io/ai-pulse/ · **Version 2** (3 October 2026)

Only what is legal to collect and publicly accessible is used. No paid API or billed service, and no AI model for the
news itself: summaries are the publishers' own text, sorting is keyword rules, the glossary is written by hand and
translation runs offline. The one exception: the memes' captions, written by Google's Gemini on its free tier.

## Streams

| Stream | What's in it | Updated |
|---|---|---|
| **Releases** | New models, products and open-source launches; a company's post counts only if it launches something | Lab and company blogs every 30 min; the rest every 6 h |
| **Industry** | Company news, deals and market moves, labelled **News**, **AI-incident**, **Study**, **Opinion & analysis**, **Company blog**, **Tutorial** or **Event** | Every 6 h |
| **Research** | Papers only: arXiv papers by ~120 leading AI and AI-ethics scholars, and big-lab papers | Every 6 h (arXiv publishes on weekdays) |
| **Regulation tracker** | AI proposals, adopted laws, AI bodies and AI standards, by country | Every 6 h; Korea, Vietnam and OECD.AI weekly; standards by hand |
| **Policy** | What governments, courts and politicians do about AI | Every 6 h |
| **Infra & climate** | AI's data centres and what they draw on: power, water, land, emissions. Stories in other streams about them carry **#Infra & climate** | Every 6 h |

## Features

- **Site:** a magazine-style front page (story, word and meme of the week, then each stream's top stories) and a page per stream, over openly licensed photos; colour-blind-safe colours.
- **Filters:** stream, region, country and time range; search covers everything back to 2023.
- **English throughout:** the publisher's English version, else an offline translation (marked), else an English headline tagged **#Translate and read**.
- **One card per event:** the same story from several outlets is grouped.
- **Glossary:** plain-English meanings of ~120 hard words; a dotted word in a story opens its meaning.
- **Memes:** a meme of the day (email) and of the week (site) on well-known internet meme templates (via imgflip.com), used as parody on this free, non-commercial site. Gemini (free tier, no billing) writes the captions from public headlines; each is checked (no politics, harm, people or invented numbers), else rule-based captions are used. The site lists the stories behind each meme.
- **RSS:** one feed per stream, one post a day ([Releases](https://shru14.github.io/ai-pulse/feeds/releases.xml), [Industry](https://shru14.github.io/ai-pulse/feeds/news.xml), [Research](https://shru14.github.io/ai-pulse/feeds/research.xml), [Regulation tracker](https://shru14.github.io/ai-pulse/feeds/regulation.xml), [Policy](https://shru14.github.io/ai-pulse/feeds/policy.xml), [Infra & climate](https://shru14.github.io/ai-pulse/feeds/infra.xml)).
- **Daily email:** the reader's streams: the 10 that mattered most, the rest in brief, word and meme of the day, and every story in one table on the site.
- **Make it yours:** more of, or leave out, any topic, company, place or scholar, plus up to 5 own words.
- **Quality check:** before sending, every story is checked; any problem holds the email for everyone and alerts the project inbox.
- **Subscriptions:** confirm by one link, unsubscribe in one click. Addresses stay in the project's Google account, never in this repository or its logs.

## How we keep it legal

1. **robots.txt must allow us**, checked before every request; the only exceptions are official APIs whose terms allow programmatic use (arXiv, Wikidata, congress.gov, jsDelivr).
2. **Terms must allow** showing a headline, a short description and a link.
3. **No workarounds:** nothing behind a login, bot check, rate limit or paywall; sites that block automated readers aren't read.
4. **Only what's needed:** headline, short description, date and link. No personal data from records.
5. **Credit and non-commercial use**, as the licences below require.
6. **Readers' privacy:** the site and email load nothing from other servers and track no one. Questions or data requests: projectaipulse@gmail.com.

Requests go one at a time with pauses and identify themselves as `AIPulse/1.0`.

## Sources

| Stream | Sources |
|---|---|
| Releases (feeds) | OpenAI, Google AI, Google DeepMind, Google Research, Hugging Face, Mistral, Microsoft Research, NVIDIA, AWS Machine Learning, Engineering at Meta, GitHub, Databricks, Cloudflare, Ollama, Sakana AI, Character.AI, Stability AI; AI stories from the newsrooms of Microsoft, Meta, Apple and Amazon |
| Releases (news pages, no feed) | Anthropic, Meta AI, DeepSeek, Cohere, MiniMax, Moonshot AI (Kimi) |
| Releases (developer release notes) | xAI (docs.x.ai) and Perplexity (docs.perplexity.ai) |
| Industry | **Global:** TechCrunch, The Verge, Ars Technica, MIT Technology Review, The Decoder, SiliconANGLE, MarkTechPost, ZDNET, 404 Media, Engadget, MIT News, Tech Xplore, ScienceDaily, Rest of World · **Asia:** South China Morning Post, Pandaily, TechNode, Focus Taiwan, Bernama, VnExpress International · **Africa:** TechCabal, iAfrikan, TechCentral, ITWeb, IT News Africa, Nairametrics · **MENA:** Wamda · **Latin America:** MercoPress, The Rio Times, Buenos Aires Times, LatinAmerica Reports |
| AI incidents (Industry) | AI Incident Database: incidents its editors confirmed since 2023 (CC BY-SA 4.0) |
| Research | arXiv, Hugging Face Daily Papers, Apple Machine Learning Research |
| Policy | EU AI Act Newsletter, CSET, AI Now Institute, Future of Life Institute, EFF, EPIC, NIST, Federal Register (US), GOV.UK, Korea's Ministry of Science and ICT, Malaysia's Ministry of Digital, Russia's State Duma (English news) |
| Infra & climate | **Global:** Carbon Brief, Climate Home News, Mongabay, Energy Monitor, The Conversation (energy), Capacity Media, Data Center Knowledge · **Europe:** European Commission (energy), Data Centre Review · **Asia-Pacific:** W.Media, iTnews · **Africa:** ESI Africa · **North America:** US Energy Information Administration, Canary Media |
| Regulation tracker | European Data Protection Board, European Commission (Digital Strategy), and the official records below |

### Official records (Regulation tracker)

| Place | Source | Legal basis |
|---|---|---|
| United States | congress.gov API | Official API, free key; public domain |
| European Union | European Parliament open data | Reuse with credit |
| United Kingdom | UK Parliament Bills API | Open Parliament Licence v3.0 |
| Canada | Parliament of Canada (LEGISinfo) | Non-commercial reproduction permitted |
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
| ~60 more countries and bodies (UN, UNESCO, G7, AU, ASEAN…) | OECD.AI Policy Observatory | CC BY 4.0 |
| International AI standards | ISO/IEC and IEEE, kept by hand | Facts only (number, title, date, link) |

## Run it

```bash
python -m aipulse collect     # fetch every source into aipulse.db
python -m aipulse serve       # http://127.0.0.1:8000
python -m pytest -q           # tests (run locally, not on GitHub)
```

Other commands: `python -m aipulse --help`.

## Hosting

- **Site:** `.github/workflows/pages.yml` publishes to GitHub Pages every 6 hours and on every push, with a quick run of lab and company blogs every 30 minutes.
- **Daily email:** `.github/workflows/digest.yml`, each morning from 05:12 UTC, sent once.
- **Sign-ups:** `apps-script/Code.gs`, a Google Apps Script web app in the project's Google account.

## Credits and licences

European Parliament, European Commission and EDPB content: © European Union, reused with acknowledgement of the source. UK Parliament data: Open Parliament Licence v3.0. GOV.UK: Open Government Licence v3.0. Federal Register,
congress.gov and US Energy Information Administration: US public domain. Canada: reproduced with the Speaker's permission for non-commercial use.
Swiss parliamentary records: The Federal Assembly — The Swiss Parliament, open data. Korean laws: National
Law Information Center (https://www.law.go.kr), Ministry of Government Legislation. Taiwanese laws:
Legislative Yuan law system (https://lis.ly.gov.tw). Malaysian bills: Parliament of Malaysia
(https://www.parlimen.gov.my). Russian parliamentary news: State Duma (http://duma.gov.ru). OECD.AI Policy
Observatory (https://oecd.ai): CC BY 4.0. Japanese laws: e-Gov Law Search (https://laws.e-gov.go.jp),
Government of Japan Standard Terms of Use 2.0; titles machine-translated by AI Pulse. Vietnamese legal
documents: National Legal Database (https://vbpl.vn). Australian legislation: based on content from the
Federal Register of Legislation (CC BY 4.0); for the latest information go to https://www.legislation.gov.au.
AI incidents: [AI Incident Database](https://incidentdatabase.ai) (Responsible AI Collaborative), incident titles and descriptions CC BY-SA 4.0 (shared here under the same licence). Translations: OPUS-MT (Helsinki-NLP, CC BY 4.0) via Argos Translate (MIT). Logos: [Lobe Icons](https://github.com/lobehub/lobe-icons)
(MIT, © 2023 LobeHub), [Simple Icons](https://simpleicons.org) (CC0) or the brand's own site icon. Fonts: Archivo Black, Archivo, Anton and IBM Plex Mono (SIL Open Font License 1.1), served
from this site. Section icons: [Phosphor Icons](https://phosphoricons.com) (MIT, © 2023 Phosphor Icons).
Meme templates: via [Imgflip](https://imgflip.com)'s free template list, used as parody and commentary.
Photos: 84 openly licensed photos from [Wikimedia Commons](https://commons.wikimedia.org) (CC BY, CC BY-SA, CC0 or public
domain), chosen to illustrate a story's topic (not the story itself); each photo's author, licence and source are on the site's Photo credits page. No publisher's photo is used.
