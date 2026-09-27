# AI Pulse

A free, non-commercial, worldwide briefing on AI: new models and products, industry news, research,
government policy and AI laws in every country. It reads ~65 open sources every 6 hours, keeps only AI
stories, sorts them into five streams and links every card to the original.

**Live site:** https://shru14.github.io/ai-pulse/

The goal is one place that brings together the public sources needed to follow AI worldwide, using only
what is **legal to collect and publicly accessible**. No AI model, paid API or billed service is used:
summaries are the publishers' own text (or an official record's own words), and sorting is keyword rules.

## Streams

| Stream | What's in it |
|---|---|
| **Releases** | New models, products and open-source launches from AI labs and companies |
| **Industry news** | Funding, deals and company moves, from global and regional tech press |
| **Policy** | Government, court and political action on AI: investigations, lawsuits, guidance, strategies, requests for government reports |
| **Research** | arXiv papers by ~80 leading AI professors, and big-lab papers via Hugging Face Daily Papers |
| **Regulation tracker** | AI **proposals** and **adopted laws** by country, **AI bodies** (safety institutes, regulators, advisory offices) and **expert views** from ~40 ethics and law scholars. Filter by region (Europe, Americas, Asia-Pacific, Middle East & Africa, International) or by country |

Search matches word stems across headlines, summaries, tags and authors, back to January 2023. The same
event reported by several outlets is one card.

## How we keep it legal

Every source was checked before it was added (September 2026), and the checks are enforced in code:

1. **robots.txt must allow us.** Every request first reads the site's robots.txt (`feeds.allowed`) and a
   disallowed URL is never fetched. A robots.txt that errors or refuses us counts as "keep out". The only
   exceptions are official APIs whose own terms allow programmatic use (`feeds.API_HOSTS`: arXiv, Wikidata,
   congress.gov, jsDelivr).
2. **Terms must allow it.** A site's terms must not forbid showing a headline, a short description and a
   link, or automated access. Where a site publishes no terms, it is treated as open, like the rest of the web.
3. **No workarounds.** Nothing is fetched past a login, a bot challenge (Cloudflare, Akamai), a rate limit,
   or a registration we can't lawfully complete. No shared or demo keys. Certificates are always verified.
4. **Only what's needed.** Headlines, short descriptions, dates and links. Official records keep their title,
   number, stages and a one- or two-sentence summary. Personal data in records (e.g. editors' emails) is
   never stored.
5. **Credit and non-commercial use.** Every licence that asks for credit is credited on the page and below.
   Some licences allow only non-commercial use, so the site must stay non-commercial.

Requests go one at a time with pauses (arXiv at most every 3 seconds, as its terms ask) and identify
themselves as `AIPulse/1.0` with a link to this repository.

## Where the data comes from

### News, releases and research (`aipulse/sources.py`)

Each feed below allows automated access in its robots.txt, and its terms don't restrict headline + short
description + link (VnExpress's feed terms explicitly allow free use by non-profits that name the source).

| Stream | Sources |
|---|---|
| Releases | OpenAI, Google AI, Google DeepMind, Google Research, Hugging Face, Mistral, Microsoft Research, NVIDIA, AWS Machine Learning, Engineering at Meta, GitHub, Databricks, Cloudflare, Ollama |
| Global news | TechCrunch, The Verge, Ars Technica, MIT Technology Review, The Decoder, SiliconANGLE, MarkTechPost, ZDNET, 404 Media, Engadget, MIT News, Tech Xplore, ScienceDaily, Rest of World |
| Regional news (AI headlines only) | Asia: South China Morning Post, Focus Taiwan, Bernama (Malaysia), VnExpress International · Africa: TechCabal, TechCentral, ITWeb · Middle East & North Africa: Wamda · Latin America: MercoPress |
| Policy | EU AI Act Newsletter, CSET, AI Now Institute, Future of Life Institute, EFF, EPIC, NIST, Federal Register (US), GOV.UK, Korea's Ministry of Science and ICT, Malaysia's Ministry of Digital |
| Research | arXiv (API), Hugging Face Daily Papers, Apple Machine Learning Research |

### Official records for the tracker (`aipulse/bills.py`, `aipulse/oecd.py`)

| Place | Official source | Why we may use it |
|---|---|---|
| United States | congress.gov API | Official API with a free personal key (a repository secret, never committed); US government works are public domain |
| European Union (one unit; member states aren't tracked separately) | European Parliament open data | Open data, reuse with credit |
| United Kingdom | UK Parliament Bills API | Open Parliament Licence v3.0 |
| Canada | Parliament of Canada (LEGISinfo) | The Speaker permits accurate, non-commercial reproduction |
| Brazil | Câmara dos Deputados open data | Open data |
| Australia | Federal Register of Legislation | CC BY 4.0 |
| China | Cyberspace Administration of China | Title, date and link only; official regulations aren't copyrighted (Copyright Law, Art. 5) |
| India | Parliament of India (sansad.in) | The public API behind its bill pages; nothing prohibits automated use |
| Japan | e-Gov law API (Digital Agency) | Government of Japan Standard Terms of Use 2.0 |
| Vietnam | National Legal Database (vbpl.vn, Ministry of Justice), via its sitemap | robots.txt allows it; legal documents aren't copyrighted (IP Law, Art. 15) |
| Switzerland | Swiss Parliament open data (ws.parlament.ch) | opendata.swiss: "Open use. Must provide the source." |
| South Korea | Ministry of Science and ICT English press releases | robots.txt allows; no terms restrict them |
| Malaysia | Ministry of Digital English media releases | No robots.txt or terms restrict them |
| ~60 more countries and international bodies (UN, UNESCO, G7, Council of Europe, African Union, ASEAN, ...) | OECD.AI Policy Observatory | CC BY 4.0; read weekly. For the countries above only guidance and AI bodies, so nothing appears twice |

How records are sorted: bills and laws go to the tracker with their stages (introduced → passed → signed
→ in force). Switzerland's motions (demands for a law) go to the tracker and its postulates (requests for a
government report) to Policy; parliamentary questions are left out. A ministry release that reports a bill
or law reaches the tracker; the rest go to Policy.

### Worldwide coverage

- **Every country is recognised** (193 places): a news story about any of them is tagged with that country
  and its region, and news of a law or bill there reaches the tracker even where no official record can be read.
- **Official records** from 13 places, **OECD.AI** for ~60 more, and **news** for the rest.
- The EU counts as one (its rules apply in every member state). Russia belongs to no region.

## Limitations we faced, and what we did

| Limitation | What we did |
|---|---|
| Google News and Bing News don't allow automated access (robots.txt; Bing's terms allow personal readers only) | Removed both. Stories come from publishers' own feeds and official records |
| Some well-known outlets' terms forbid aggregation, bots or reuse (BBC News, CNA, Korea Herald, MediaNama, Inc42, Rappler, Philstar, SoyaCincau) or couldn't be confirmed (NYT, The Guardian, Wired, The Africa Report) | Left out. Replaced with outlets whose terms allow it |
| Some sites refuse automated access (Japan Times, Malay Mail, e27, Techpoint Africa, The Register) | Left out |
| Most global tech press covers the US and Europe | Added regional news for Asia, Africa, the Middle East and Latin America, after checking each one |
| The shared congress.gov DEMO_KEY is only for trying the API | Uses a free personal key, stored as a secret |
| South Korea's bill API needs Korean identity verification; its bill site's robots.txt blocks bots | Korea's AI rules come from its science ministry's English press releases |
| China's national law database (flk.npc.gov.cn) forbids automated access | Uses the Cyberspace Administration's AI regulations (titles, dates and links) |
| India Code, MeitY and PIB turn away automated requests (Akamai) | Uses Parliament of India's bill data |
| Taiwan: the national law database's robots.txt blocks everything; the Legislative Yuan's open-data robots.txt errors | Taiwan comes through Focus Taiwan (its national news agency) and the news |
| Malaysia: the Attorney General's Chambers blocks bots, its law portal's robots.txt errors, the Parliament's certificate is broken | Uses the Ministry of Digital, whose National AI Office drafts the AI Governance Bill |
| Vietnam's National Assembly site serves a bot challenge | Uses the Ministry of Justice's National Legal Database through its public sitemap |
| Singapore's terms require permission even to link; Russia's official sites refuse foreign connections; the Council of Europe is behind Cloudflare | Not used. They appear through OECD.AI (which carries the Council of Europe AI Convention) and the news |
| ~150 countries have no usable official source | Every country is recognised in news, and OECD.AI covers ~60 at once |
| Records in Portuguese, Chinese, Japanese, Vietnamese and German | English titles and summaries translated **offline** with open-source OPUS-MT models; no API. Cards say they are machine translations and link the official text |
| The translation models get some legal terms wrong (Vietnamese "artificial intelligence" came out as "manic intelligence"; Chinese "办法" as "method") | Fixed term rules per language (`translate.py`). The Korean model was unusable, so Korean items come from English releases |
| No AI model may write summaries | Summaries are the publisher's description, an official record's own summary, the first paragraph of a release, or the translated sentence stating what a motion asks, plus the government's position |
| Some lists repeat the title as the description (Malaysia's releases) | The release's own first paragraph is read, once per new release |
| OECD.AI records have a start year only | Cards show "Since YYYY" |
| General news feeds carry non-AI stories | Regional and general feeds keep only items with AI in the headline |
| Windows' certificate store lacks some certificates official sites use | Fetching uses Mozilla's CA list (certifi): still fully verified, never switched off |
| "National AI Office" (Malaysia) read as the EU AI Office; names like Jordan or Georgia are also people and US states | Country patterns only match forms that mean the country; tests cover these cases |

**Still open:** Taiwan's and Malaysia's legislatures, Singapore, Russia, Korea's National Assembly and
China's and India's law databases, until they open automated access or give permission. Latin America and
Africa have fewer regional sources than Asia. Coverage of any country is only as good as the news about it.

## Run it

```bash
python -m aipulse collect     # fetch every source into aipulse.db
python -m aipulse serve       # http://127.0.0.1:8000
```

Other commands: `run --every-hours 6`, `bills` (sync official records), `backfill --since 2023-01-01`,
`reclassify`, `regroup`, `evaluate`, `sources`, `build --out site`, `prune`. Tests: `python -m pytest -q`.

Optional: `pip install ctranslate2 sentencepiece certifi` for offline English translations and Mozilla's CA list.

## Hosting

- **GitHub Pages:** `.github/workflows/pages.yml` runs every 6 hours and on every push to `main`: it
  collects, builds the static site and deploys it (~10–15 min). The database is carried in the Actions
  cache, starting from `data/seed.db.gz` (bump the `v4` cache key when replacing the seed).
- **This PC:** Task Scheduler runs `AI Pulse server` (`serve --port 8080`, at logon) and `AI Pulse collect`
  (every 6 hours).

## Layout

```
aipulse/  sources (every feed) · feeds (fetching, robots.txt) · classify · jurisdictions (193 places, regions)
          bills (official records) · oecd · translate (offline) · brief · brands · backfill · cluster
          store · collect · server · static · evaluate
templates/index.html   the page
tests/                 unit and end-to-end tests
```

## Credits and licences

UK Parliament data: Open Parliament Licence v3.0. GOV.UK: Open Government Licence v3.0. Federal Register and
congress.gov: US public domain. Canada: reproduced with the Speaker's permission for non-commercial use.
Swiss parliamentary records: The Federal Assembly — The Swiss Parliament, open data. OECD.AI Policy
Observatory (https://oecd.ai): CC BY 4.0. Japanese laws: e-Gov Law Search (https://laws.e-gov.go.jp),
Government of Japan Standard Terms of Use 2.0; titles machine-translated by AI Pulse. Vietnamese legal
documents: National Legal Database (https://vbpl.vn). Australian legislation: based on content from the
Federal Register of Legislation (CC BY 4.0); for the latest information go to https://www.legislation.gov.au.
Translations: OPUS-MT (Helsinki-NLP, CC BY 4.0) via Argos Translate (MIT). Logos: [Lobe Icons](https://github.com/lobehub/lobe-icons)
(MIT, © 2023 LobeHub), [Simple Icons](https://simpleicons.org) (CC0) or the brand's own site icon.
