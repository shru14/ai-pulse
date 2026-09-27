# AI Pulse

A free, non-commercial briefing on what's happening in AI. It reads ~45 open sources every 6 hours, keeps
only AI stories, sorts them into five streams and links every card to the original.

**Live site:** https://shru14.github.io/ai-pulse/

Python 3.10+, standard library only. No AI model, paid API or billed service is used: summaries are the
publishers' own text and sorting is keyword rules.

## Streams

| Stream | What's in it |
|---|---|
| **Releases** | New models, products and open-source launches |
| **Industry news** | Funding, deals and company moves |
| **Policy** | Government, court and political action on AI: investigations, lawsuits, guidance |
| **Research** | arXiv papers by ~80 leading AI professors, and big-lab papers via Hugging Face Daily Papers |
| **Regulation tracker** | AI **proposals** and **adopted laws** by country, **AI bodies** (safety institutes, regulators, advisory and coordination offices) and **expert views** from ~40 ethics and law scholars. Filter by region (Europe, Americas, Asia-Pacific, Middle East & Africa, International) or click a country chip |

Search matches word stems across headlines, summaries, tags and authors; the time range goes back to
January 2023. The same event reported by several outlets is one card.

Every country is recognised in news (EU members count as the EU), so a story about any of them gets its
country tag, and news of a law or bill there reaches the tracker even where no official record can be read.

## Run it

```bash
python -m aipulse collect     # fetch every source into aipulse.db
python -m aipulse serve       # http://127.0.0.1:8000
```

Other commands: `run --every-hours 6`, `bills` (sync official records), `backfill --since 2023-01-01`,
`reclassify`, `regroup`, `evaluate`, `sources`, `build --out site`, `prune`. Tests: `python -m pytest -q`.

Optional: `pip install ctranslate2 sentencepiece` gives non-English records (Brazil, China, Japan, Vietnam) an
English title, translated **offline** with OPUS-MT models (no API).

## Sources and access rules

Only free, open sources whose **robots.txt allows automated access** and whose **terms allow** a headline,
short description and link (checked September 2026). Every request checks robots.txt first (`feeds.allowed`);
the only exceptions are official APIs whose terms allow programmatic use (`feeds.API_HOSTS`). Requests go
one at a time with pauses and identify as `AIPulse/1.0`. Nothing is fetched past a login, key-gated
registration we can't lawfully get, rate limit or bot challenge. The full list is in `aipulse/sources.py`.

**Official records for the tracker:**

| Place | Source |
|---|---|
| United States | congress.gov API (free personal key in `CONGRESS_API_KEY`, a repository secret; never committed) |
| European Union (counted as one; member states aren't tracked separately) | European Parliament open data |
| United Kingdom | UK Parliament Bills API |
| Canada | Parliament of Canada (LEGISinfo) |
| Brazil | Câmara dos Deputados open data |
| Australia | Federal Register of Legislation |
| China | Cyberspace Administration of China (titles, dates and links only) |
| India | Parliament of India (sansad.in) |
| Japan | e-Gov law API |
| Vietnam | National Legal Database (vbpl.vn, Ministry of Justice): AI documents found through its sitemap, read weekly. Vietnamese legal documents aren't copyrighted (IP Law, Art. 15) |
| South Korea | Ministry of Science and ICT English press releases |
| ~60 more countries and international bodies | OECD.AI Policy Observatory: laws, guidance and AI bodies, read weekly (editors' names and emails never stored). For the countries above, only their guidance and bodies, so nothing appears twice |

**Left out on purpose:** Google News and Bing News (robots.txt or terms), BBC News, NYT, Guardian, Wired
and The Register (terms or robots.txt). Not reachable lawfully: Singapore's official sites (permission
needed even to link), Korea's National Assembly API (Korean ID verification), Vietnam's National Assembly site (bot challenge), Russia's official sites
(refuse foreign connections), China's NPC law database and India Code/MeitY/PIB (block automated access).
These places still appear through OECD.AI and the news. Russia is in no region.

## Hosting

- **GitHub Pages:** `.github/workflows/pages.yml` runs every 6 hours and on every push to `main`: it
  collects, builds the static site and deploys it (~10–15 min). The database is carried in the Actions
  cache, starting from `data/seed.db.gz` (bump the `v4` cache key when replacing the seed).
- **This PC:** Task Scheduler runs `AI Pulse server` (`serve --port 8080`, at logon) and `AI Pulse collect`
  (every 6 hours).

## Layout

```
aipulse/  sources · feeds · classify · jurisdictions (countries, regions) · brief · brands
          bills (official records) · oecd · translate · backfill · cluster · store · collect
          server · static · evaluate
templates/index.html   the page
tests/                 unit and end-to-end tests
```

## Credits and licences

Some licences allow only non-commercial use, so the site must stay non-commercial.
UK Parliament data: Open Parliament Licence v3.0. GOV.UK: Open Government Licence v3.0. Federal Register:
US public domain. Canada: reproduced with the Speaker's permission for non-commercial use. OECD.AI Policy
Observatory (https://oecd.ai): CC BY 4.0. Japanese laws: e-Gov Law Search (https://laws.e-gov.go.jp),
Government of Japan Standard Terms of Use 2.0; titles machine-translated by AI Pulse. Australian legislation:
based on content from the Federal Register of Legislation (CC BY 4.0); for the latest information go to
https://www.legislation.gov.au. Translations: OPUS-MT (Helsinki-NLP, CC BY 4.0) via Argos Translate (MIT).
Logos: [Lobe Icons](https://github.com/lobehub/lobe-icons) (MIT, © 2023 LobeHub),
[Simple Icons](https://simpleicons.org) (CC0) or the brand's own site icon.
