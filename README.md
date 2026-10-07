# AI Pulse

A free, non-commercial, worldwide briefing on AI. It reads 119 public sources (101 feeds, 18 official records and
databases), keeps only AI stories, sorts them into six streams and links every card to the original.

**Live site:** https://projectaipulse.com/ · **Version 2** (3 October 2026)

Only legal, publicly accessible sources are used.

## Streams

| Stream | What's in it | Updated |
|---|---|---|
| **Releases** | New models, products and open-source launches | Lab and company blogs every 30 min; the rest every 6 h |
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
- **AI glossary:** a [page per word](https://projectaipulse.com/glossary/) (130 words, written by hand), with related terms, the words often in the same stories and its latest stories.
- **Open data:** the tracker's official records as a [CSV](https://projectaipulse.com/tracker.csv): date, country, type, title, source and link.
- **Make it yours:** more of, or leave out, any topic, company, place or scholar, plus up to 5 own words.
- **Subscriptions:** confirm by one link, unsubscribe in one click. Addresses and questions stay in the project's Google account, never in this repository or its logs.

## How we keep it legal

1. **robots.txt must allow us**, checked before every request; the only exceptions are official APIs whose terms allow programmatic use (arXiv, Wikidata, congress.gov, jsDelivr).
2. **Terms must allow** showing a headline, a short description and a link.
3. **No workarounds:** nothing behind a login, bot check or paywall; sites that block automated readers aren't read.
4. **Only what's needed:** headline, short description, date and link. No personal data.
5. **Credit and non-commercial use**, as the licences below require.
6. **Readers' privacy:** the site and email load nothing from other servers and track no one. Questions: projectaipulse@gmail.com.

Requests go one at a time with pauses and identify themselves as `AIPulse/1.0`. AI Pulse's own robots.txt lets search engines in and keeps AI-training bots out.

## Sources

| Stream | Sources |
|---|---|
| Releases (feeds) | OpenAI, Google AI, Google DeepMind, Google Research, Hugging Face, Mistral, Microsoft Research, NVIDIA, AWS Machine Learning, Engineering at Meta, GitHub, Databricks, Cloudflare, Ollama, Sakana AI, Character.AI, Stability AI; AI stories from the newsrooms of Microsoft, Meta, Apple and Amazon |
| Releases (news pages, no feed) | Anthropic, Meta AI, DeepSeek, Cohere, MiniMax, Moonshot AI (Kimi) |
| Releases (developer release notes) | xAI (docs.x.ai) and Perplexity (docs.perplexity.ai) |
| Industry | **Global:** TechCrunch, The Verge, Ars Technica, MIT Technology Review, The Decoder, SiliconANGLE, MarkTechPost, ZDNET, 404 Media, Engadget, MIT News, Tech Xplore, ScienceDaily · **Asia:** South China Morning Post, Pandaily, Focus Taiwan, Bernama, VnExpress International · **Africa:** TechCabal, iAfrikan, TechCentral, ITWeb, IT News Africa, Nairametrics · **MENA:** Wamda · **Latin America:** MercoPress, The Rio Times, Buenos Aires Times, LatinAmerica Reports · **Chips and servers:** Semiconductor Digest, ServeTheHome · **Practitioners and evaluators:** Simon Willison, Lil'Log, METR |
| AI incidents (Industry) | AI Incident Database (CC BY-SA 4.0) |
| Research | arXiv, Hugging Face Daily Papers, Apple Machine Learning Research |
| Policy | EU AI Act Newsletter, CSET, AI Now Institute, Future of Life Institute, EFF, EPIC, NIST, Federal Register (US), GOV.UK, Korea's Ministry of Science and ICT, Malaysia's Ministry of Digital, Russia's State Duma (English news), Innovation, Science and Economic Development Canada, CLTC (UC Berkeley), ITU, DARPA, NSF, UK AI Security Institute |
| Infra & climate | **Global:** Carbon Brief, Climate Home News, Mongabay, Energy Monitor, The Conversation (energy), Capacity Media, Data Center Knowledge · **Europe:** European Commission (energy), Data Centre Review · **Asia-Pacific:** W.Media, iTnews · **Africa:** ESI Africa · **North America:** US Energy Information Administration, Canary Media |
| Regulation tracker | European Data Protection Board, European Commission (Digital Strategy), and the official records below |

### Official records (Regulation tracker)

| Place | Source | Legal basis |
|---|---|---|
| United States | congress.gov API | Official API, free key; public domain |
| European Union | European Parliament open data | Reuse with credit |
| United Kingdom | UK Parliament Bills API | Open Parliament Licence v3.0 |
| Canada | Canada Gazette, Parts I and II | No robots.txt rules; non-commercial reproduction with credit |
| Brazil | Câmara dos Deputados open data | Open data |
| Australia | Federal Register of Legislation | CC BY 4.0 |
| China | Cyberspace Administration of China | Title, date and link only; regulations aren't copyrighted |
| India | Parliament of India (sansad.in): AI bills and the Digital Personal Data Protection Act | Public API; no restriction on automated use |
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
python -m pytest -q           # tests (run locally, not on GitHub)
```

## Hosting

- **Site:** GitHub Pages (`.github/workflows/pages.yml`), every 6 hours and on every push.
- **Domain:** projectaipulse.com, about $11 a year (the project's only cost).
- **Daily email:** `.github/workflows/digest.yml`, from 05:12 UTC.
- **Sign-ups:** `apps-script/Code.gs`, a Google Apps Script web app in the project's Google account.

## Credits and licences

European Parliament, European Commission and EDPB content: © European Union, reused with acknowledgement of the source. UK Parliament data: Open Parliament Licence v3.0. GOV.UK and UK AI Security Institute: Open Government Licence v3.0. Federal Register,
congress.gov, US Energy Information Administration, DARPA and NSF: US public domain. ITU: non-commercial use with credit. ServeTheHome: short synopses as its copyright policy allows. Canada: Canada Gazette and ISED content reproduced from gazette.gc.ca and canada.ca, not affiliated with or endorsed by the Government of Canada.
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
(MIT, © 2023 LobeHub), [Simple Icons](https://simpleicons.org) (CC0) or the brand's own site icon. Fonts: Archivo Black, Archivo, Anton and IBM Plex Mono (SIL Open Font License 1.1), served
from this site. Section icons: [Phosphor Icons](https://phosphoricons.com) (MIT, © 2023 Phosphor Icons).
Meme templates: via [Imgflip](https://imgflip.com), used as parody and commentary. Flags: [flag-icons](https://github.com/lipis/flag-icons) (MIT, © 2013 Panayiotis Lipiridis), served from this site.
Photos: 84 openly licensed photos from [Wikimedia Commons](https://commons.wikimedia.org) (CC BY, CC BY-SA, CC0 or public
domain), chosen to illustrate a story's topic; each photo's author, licence and source are on the site's Photo credits page.
