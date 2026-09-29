# AI Pulse

A free, non-commercial, worldwide briefing on AI. It reads ~95 public sources, keeps only AI stories, sorts
them into five streams and links every card to the original.

**Live site:** https://shru14.github.io/ai-pulse/

Only what is legal to collect and publicly accessible is used. No AI model, paid API or billed service:
summaries are the publishers' own text, sorting is keyword rules, and translation runs offline.

## Streams

| Stream | What's in it | Updated |
|---|---|---|
| **Releases** | New models, products and open-source launches. A company's post counts only if it launches something | Lab and company blogs every 30 min; the rest every 6 h |
| **Industry** | Company news, deals and market moves, each labelled **News**, **AI-incident**, **Study**, **Opinion & analysis**, **Company blog**, **Tutorial** or **Event** | Every 6 h |
| **Research** | Research papers only: arXiv papers by ~120 leading AI and AI-ethics scholars, and big-lab papers | Every 6 h (arXiv publishes on weekdays) |
| **Regulation tracker** | AI proposals, adopted laws, AI bodies and AI standards, by country | Every 6 h; Korea, Vietnam and OECD.AI weekly; standards by hand |
| **Policy** | What governments, courts and politicians do about AI; government publications always land here | Every 6 h |

## Features

- **Filters:** by stream, region, country and time range; search covers headlines, summaries, tags and authors back to 2023.
- **Everything in English, nothing left out:** a story in another language shows the publisher's own English version when there is one, else an offline translation (OPUS-MT, no API) marked as such; one that can't be translated gets an English headline and line and the **#Translate and read** tag. Both link to the original through Google Translate's page, opened by the reader.
- **One card per event:** the same story from several outlets is grouped, led by the company's own post when there is one.
- **RSS:** one feed per stream, one post a day ([Releases](https://shru14.github.io/ai-pulse/feeds/releases.xml), [Industry](https://shru14.github.io/ai-pulse/feeds/news.xml), [Research](https://shru14.github.io/ai-pulse/feeds/research.xml), [Regulation tracker](https://shru14.github.io/ai-pulse/feeds/regulation.xml), [Policy](https://shru14.github.io/ai-pulse/feeds/policy.xml)).
- **Daily email:** one email a day with the reader's streams: the 10 things that mattered most (ranked by how many outlets reported them), then each stream's top headlines; on a lighter day (12 stories or fewer) all of them. Every email links to that day's full email on the site (`daily/`: every story, every stream, one table). Sent each morning from 05:17 UTC to readers who confirmed their sign-up.
- **Quality check:** before sending, every story is checked (sorting, text, links, duplicates, unusual counts); any problem holds the email for everyone and alerts the project inbox.
- **Subscriptions:** email and streams entered on the site, confirmed by one link, one-click unsubscribe in every email; addresses stay in the project's Google account, never in this repository or its logs.

## How we keep it legal

1. **robots.txt must allow us.** It's checked before every request (`feeds.allowed`); official APIs whose terms allow programmatic use are the only exception (arXiv, Wikidata, congress.gov, jsDelivr).
2. **Terms must allow** showing a headline, a short description and a link.
3. **No workarounds:** nothing behind a login, bot check or rate limit. Sites that block automated readers (xAI's and Perplexity's news pages, iso.org) aren't read.
4. **Only what's needed:** headline, short description, date and link. No personal data from records.
5. **Credit and non-commercial use**, as the licences below require.

Requests go one at a time with pauses and identify themselves as `AIPulse/1.0`.

## Sources

Every source below allows automated access in its robots.txt, and its terms allow headline, description and link.

| Stream | Sources |
|---|---|
| Releases (feeds) | OpenAI, Google AI, Google DeepMind, Google Research, Hugging Face, Mistral, Microsoft Research, NVIDIA, AWS Machine Learning, Engineering at Meta, GitHub, Databricks, Cloudflare, Ollama, Sakana AI, Character.AI, Stability AI; AI stories from the newsrooms of Microsoft, Meta, Apple and Amazon |
| Releases (news pages, no feed) | Anthropic, Meta AI, DeepSeek, Cohere, MiniMax, Moonshot AI (Kimi): each new post is read once; a post with no date gets the day it's first seen |
| Releases (developer release notes) | xAI (docs.x.ai) and Perplexity (docs.perplexity.ai), their news pages being closed to readers; only launches of their own products |
| Industry | **Global:** TechCrunch, The Verge, Ars Technica, MIT Technology Review, The Decoder, SiliconANGLE, MarkTechPost, ZDNET, 404 Media, Engadget, MIT News, Tech Xplore, ScienceDaily, Rest of World · **Asia:** South China Morning Post, Pandaily, TechNode, Focus Taiwan, Bernama, VnExpress International · **Africa:** TechCabal, iAfrikan, TechCentral, ITWeb, IT News Africa, Nairametrics · **MENA:** Wamda · **Latin America:** MercoPress, The Rio Times, Buenos Aires Times, LatinAmerica Reports |
| AI incidents (Industry) | AI Incident Database: every incident its editors confirmed since 2023, one card each (terms bar only high-volume and commercial use; text CC BY-SA 4.0) |
| Research | arXiv, Hugging Face Daily Papers, Apple Machine Learning Research |
| Policy | EU AI Act Newsletter, CSET, AI Now Institute, Future of Life Institute, EFF, EPIC, NIST, Federal Register (US), GOV.UK, Korea's Ministry of Science and ICT, Malaysia's Ministry of Digital, Russia's State Duma (English news) |
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
| International AI standards | ISO/IEC and IEEE: 18 published standards, kept by hand in `aipulse/standards.py` | Facts only (number, title, date, link) |

## Run it

```bash
python -m aipulse collect     # fetch every source into aipulse.db
python -m aipulse serve       # http://127.0.0.1:8000
python -m pytest -q           # tests
```

Other commands: `collect --labs`, `bills`, `backfill`, `reclassify`, `regroup`, `build --out site`, `digest`, `status`.

## Hosting

- **Site:** `.github/workflows/pages.yml` collects and publishes to GitHub Pages every 6 hours and on every push to `main`, with a quick run of lab and company blogs every 30 minutes.
- **Daily email:** `.github/workflows/digest.yml`, four tries each morning from 05:17 UTC, sent once (secrets `DIGEST_EMAIL`, `DIGEST_APP_PASSWORD`, `DIGEST_LIST_KEY`).
- **Sign-ups:** `apps-script/Code.gs`, a Google Apps Script web app in the project's Google account.

## Layout

```
aipulse/               collection, sorting, grouping, site build, RSS, email, quality check, subscribers
apps-script/Code.gs    the sign-up web app
templates/index.html   the page
tests/                 tests
```

## Credits and licences

European Parliament, European Commission and EDPB content: © European Union, reused with acknowledgement of the source. UK Parliament data: Open Parliament Licence v3.0. GOV.UK: Open Government Licence v3.0. Federal Register and
congress.gov: US public domain. Canada: reproduced with the Speaker's permission for non-commercial use.
Swiss parliamentary records: The Federal Assembly — The Swiss Parliament, open data. Korean laws: National
Law Information Center (https://www.law.go.kr), Ministry of Government Legislation. Taiwanese laws:
Legislative Yuan law system (https://lis.ly.gov.tw). Malaysian bills: Parliament of Malaysia
(https://www.parlimen.gov.my). Russian parliamentary news: State Duma (http://duma.gov.ru). OECD.AI Policy
Observatory (https://oecd.ai): CC BY 4.0. Japanese laws: e-Gov Law Search (https://laws.e-gov.go.jp),
Government of Japan Standard Terms of Use 2.0; titles machine-translated by AI Pulse. Vietnamese legal
documents: National Legal Database (https://vbpl.vn). Australian legislation: based on content from the
Federal Register of Legislation (CC BY 4.0); for the latest information go to https://www.legislation.gov.au.
AI incidents: [AI Incident Database](https://incidentdatabase.ai) (Responsible AI Collaborative), incident titles and descriptions CC BY-SA 4.0 (shared here under the same licence). Translations: OPUS-MT (Helsinki-NLP, CC BY 4.0) via Argos Translate (MIT). Logos: [Lobe Icons](https://github.com/lobehub/lobe-icons)
(MIT, © 2023 LobeHub), [Simple Icons](https://simpleicons.org) (CC0) or the brand's own site icon.
