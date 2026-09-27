# AI Pulse

A self-hosted briefing on what's happening in AI. AI Pulse reads ~45 open sources (lab blogs, newsrooms,
government records and research archives) every 6 hours, keeps only AI stories, sorts each into one of five streams and
links every card to the original reporting.

**Live site:** https://shru14.github.io/ai-pulse/

Pure Python 3.10+, standard library only: nothing to install.

## The five streams

| Stream | What's in it |
|---|---|
| **Releases** | New models, product features and open-source launches |
| **Industry news** | Funding, deals, partnerships and company moves |
| **Policy** | What governments, courts and politicians are doing about AI: investigations, lawsuits, guidance, debates |
| **Research** | Papers only: new arXiv papers by ~80 leading AI professors (matched by exact author name), and papers from big tech and frontier labs via Hugging Face Daily Papers |
| **Regulation tracker** | AI **proposals** (bills, draft rules, consultations) and **adopted laws** (passed, signed, in force, executive orders), tagged by country, plus **expert views** from ~40 AI ethics, philosophy and law scholars |

## Using the page

- **Stream cards** at the top pick a stream and show its count; click the chosen card again (or its
  chip next to the search box, or the logo) to see everything.
- **Search** and the **time range** (7, 30, 90 days, all time) stay pinned while you scroll. Search matches
  word beginnings and stems ("regulate" finds "regulation") across headlines, summaries, sources, tags and authors.
- **Cards** show a logo for the company involved (or the country, or a topic symbol), a summary
  (long ones fold behind "Read more"), clickable tags, and the date and source link. The same event
  reported by several outlets is one card with "N sources".
- **Regulation tracker**: click a country chip on a card to see only that country. US bills and EU procedures show the stages
  they have reached so far (introduced, passed, signed, in force), each with its date.
- **Light / dark** follows your system; the button in the top bar overrides it.
- Links open a stream directly: `/#policy`, `/#regulation`; `/?q=nvidia` also searches.

## Quick start

```bash
python -m aipulse collect     # fetch every source once into aipulse.db
python -m aipulse serve       # open http://127.0.0.1:8000
```

Or `python -m aipulse run --every-hours 6` to serve and collect on a timer in one process.

| Command | Does |
|---|---|
| `collect` | Fetch all sources and store new stories (`--max-age-days 3`) |
| `serve` / `run` | Serve the page and JSON API / serve and collect on a timer |
| `reclassify` | Re-run the sorting and tagging rules over stored stories (after changing them) |
| `resummarize` | Re-clean stored headlines and summaries |
| `backfill --since DATE` | One-time history back to 2023 (see below) |
| `regroup` | Regroup every story into cards (one card per event) |
| `bills` | Sync bill stages from congress.gov and the European Parliament |
| `evaluate` | Score the sorting rules against hand-labelled stories |
| `sources` | Show each source's health |
| `build --out site` | Write the static site for GitHub Pages |
| `prune --keep-days 365` | Delete old stories |

The server also answers `/api/items?category=policy&q=EU&days=7&page=1` (one page of cards plus stream
counts; `place=FR` filters the tracker) and `/api/sources`.

## How stories are sorted

Keyword rules in `aipulse/classify.py` decide whether a story is about AI, which stream it belongs to,
and its tags (companies, places, topics). Each source has a default stream; a story from a policy search
with nothing about government in it drops to Industry news. A policy story moves to the Regulation
tracker when its headline reports a proposal or an adopted law and names who acted
(`aipulse/jurisdictions.py` knows ~60 countries and blocs plus US states). Enforcement, investigations and
guidance stay under Policy.

`tests/fixtures/labels.csv` holds 100 hand-labelled stories; `python -m aipulse evaluate` prints the
accuracy and every mistake, and a test stops the scores from dropping. After editing the rules, run
`python -m aipulse reclassify`; the GitHub workflow also runs it after every collection.

Headlines and summaries are cleaned in `aipulse/brief.py` (desk labels, site names and boilerplate
removed). A summary is the description the publisher put in its own feed; a story without one gets a
short factual line from its stream, places and companies.

No AI model or paid API is used: summaries are the publishers' own text, and sorting is keyword rules.

## Sources

Only free, open sources are read, and only ones whose **robots.txt allows automated access** and whose
**terms don't restrict** showing a headline with a short description and a link (checked September 2026).
The full list, with each feed's settings, is in `aipulse/sources.py`.

This is enforced in code: every request first checks the site's robots.txt (`feeds.allowed`) and a URL it
disallows is never fetched. The only exceptions are official APIs whose published terms allow programmatic
use (arXiv's API, Wikidata's API, the congress.gov API and the jsDelivr CDN; see `feeds.API_HOSTS`). Requests
go one at a time with pauses, arXiv at most once every 3 seconds as its terms ask, and identify themselves
as `AIPulse/1.0` with a link to this repository.

| Stream | Sources |
|---|---|
| Releases | OpenAI, Google AI, Google DeepMind, Google Research, Hugging Face, Mistral, Microsoft Research, NVIDIA, AWS Machine Learning, Engineering at Meta, GitHub, Databricks, Cloudflare, Ollama |
| Industry news | TechCrunch, The Verge, Ars Technica, MIT Technology Review, The Decoder, SiliconANGLE, MarkTechPost, ZDNET, 404 Media, Engadget, MIT News, Tech Xplore, ScienceDaily, Rest of World, South China Morning Post, TechCabal |
| Policy | EU AI Act Newsletter, CSET, AI Now Institute, Future of Life Institute, EFF, EPIC, NIST, **Federal Register** (US federal records), **GOV.UK** (UK government) |
| Regulation tracker | European Data Protection Board, European Commission, US Congress, European Parliament, UK Parliament, Parliament of Canada and Brazil's Chamber of Deputies bill records, arXiv papers by ~40 ethics and law scholars |
| Research | arXiv (new papers by ~80 professors), Hugging Face Daily Papers, Apple Machine Learning Research |

**Left out on purpose:** Google News (its robots.txt disallows automated access) and Bing News (its feed
terms allow only personal RSS readers), so neither is used for stories or summaries; BBC News (its terms
forbid modified feeds); The New York Times, The Guardian and Wired (their terms couldn't be confirmed);
The Register (its robots.txt disallows the feed). Before adding a source, check its robots.txt and terms.

## History back to 2023

Daily collection only sees what feeds hold today, so `python -m aipulse backfill` fills every stream back
to 1 January 2023 (`--since` for another date, `--only feeds|official|research|papers` for one group):

- **Feeds** (news, releases, policy): each source's own archive. Some feeds list years of posts (OpenAI,
  Hugging Face); WordPress feeds page back in time (`?paged=2, 3, ...`: TechCrunch, The Decoder,
  SiliconANGLE, Ars Technica, MIT Technology Review, MarkTechPost, NVIDIA, Microsoft Research, CSET,
  AI Now, EPIC, TechCabal), read page by page until the start date.
- **Official records:** the Federal Register and GOV.UK search APIs, one month at a time.
- **Research and expert papers:** arXiv's search API for every listed professor and scholar, and Hugging
  Face Daily Papers day by day (from May 2023) for big tech and frontier lab papers.

It takes a few hours and must run on a PC (arXiv refuses cloud servers); pages read and searches done
are remembered, so it can be stopped and resumed. To publish the result, gzip the database to
`data/seed.db.gz`, bump the version (now `v3`) in the workflow's database cache key, and push: the next run starts
from the new seed. The site loads the last 90 days at once and older cards (one file per year) only
for "All time".

## Bills from official records

| Source | Stages | What you need |
|---|---|---|
| congress.gov API | Introduced → passed one chamber → passed Congress → signed → became law (or vetoed) | A free API key ([sign up](https://api.congress.gov/sign-up/)) |
| European Parliament open data | Proposed → Parliament position → final vote → signed → Official Journal | Nothing: open data, no sign-up |
| UK Parliament Bills API | Introduced → passed first House → passed both Houses → Royal Assent (or withdrawn / defeated) | Nothing: Open Parliament Licence |
| Parliament of Canada (LEGISinfo) | First reading → passed first chamber → passed both chambers → Royal Assent (or died on the Order Paper) | Nothing; the Speaker permits accurate, non-commercial reproduction |
| Brazil: Câmara dos Deputados open data | Introduced → passed first chamber → passed Congress → became law (or vetoed, withdrawn, archived) | Nothing: open data. Only lead bills are shown; bills attached to one move with it. Summaries are the official Portuguese ones |

Each bill is one card dated at its latest stage, with news that names the bill attached. The key is read
from `CONGRESS_API_KEY` and never stored in the repository: set it as a repository secret for the public
site (Settings → Secrets and variables → Actions) and with `setx CONGRESS_API_KEY your-key` on this PC.
One-time backfill: `python -m aipulse bills --eu-since 2019 --us-days 30` (UK bills: every session the API holds).

More countries are added one at a time, each from its own official records (next: Australia, then the EU's legal database, India, Japan, South Korea, Singapore). Some of these licences allow only non-commercial use, so the site must stay
non-commercial.

## Hosting

**GitHub Pages (the public site).** `.github/workflows/pages.yml` runs every 6 hours (00, 06, 12, 18 UTC),
on every push to `main` and on demand. It collects, re-sorts stored stories, builds the static site and
deploys it, carrying the database between runs in the Actions cache (starting from `data/seed.db.gz`). The
static page filters, searches and pages `data.json` (and, for "All time", the yearly `archive/` files) in
the browser. A push shows up on the site after a
few minutes, once collection finishes. To set up your own copy: push to a public repository, set
Settings → Pages → Source to **GitHub Actions**, and add the `CONGRESS_API_KEY` secret.

**This PC (Windows Task Scheduler).**

| Task | When | Runs |
|---|---|---|
| `AI Pulse server` | At logon | `pythonw -m aipulse --log server.log serve --port 8080` |
| `AI Pulse collect` | Every 6 hours | `pythonw -m aipulse --log collect.log collect` |

The server reads `templates/index.html` on every request, so page changes show on reload; restart the
server task after changing Python code. On Linux or macOS, use cron with the same two commands.

## Source health

Busy hosts (HTTP 429, 5xx, timeouts) are retried with backoff. A source that fails 3 collections in a
row shows as "⚠ N sources failing" under the intro; `python -m aipulse sources` lists the details.

## Customize

- **Sources:** `aipulse/sources.py`. Any RSS or Atom feed works; give it a default stream. Add names to
  `PROFESSORS` or `EXPERTS` to follow more people. Check a site's robots.txt and terms before adding it.
- **Rules and tags:** `aipulse/classify.py` and `aipulse/jurisdictions.py`.
- **Company logos:** the 12 AI companies in `COMPANY_TERMS` use the colour logos in `LOGOS`
  (`templates/index.html`). Any other brand a headline names is found automatically by `aipulse/brands.py`:
  Simple Icons' index of ~3,000 brands first, then Wikidata (a company or product with an official website,
  shown with that site's own icon, if its robots.txt allows fetching it). Plain words like "Astra" count only if Wikidata confirms a company by that
  name. Lookups are cached in `data/` (and in the Actions cache on GitHub), so each name is checked once.

## Project layout

```
aipulse/
  sources.py        feed list, professors, experts, companies
  feeds.py          fetching and parsing: RSS/Atom, arXiv, Hugging Face, Federal Register, GOV.UK
  classify.py       AI relevance, stream, tag and regulatory-action rules
  jurisdictions.py  countries, blocs and US states the tracker recognises
  brief.py          headline and summary cleaning
  brands.py         brand logos found in headlines (Simple Icons, Wikidata)
  bills.py          congress.gov and European Parliament bill stages
  backfill.py       one-time history back to 2023 (feed archives, official records, papers)
  cluster.py        grouping the same event into one card
  store.py          SQLite schema, full-text search, queries
  collect.py        the collection run
  evaluate.py       scoring the rules against labelled stories
  server.py         page and JSON API
  static.py         static site for GitHub Pages
templates/index.html  the page
tests/                unit and end-to-end tests with fixture feeds (python -m pytest -q)
```

UK Parliament data: Open Parliament Licence v3.0. AI company logos: [Lobe Icons](https://github.com/lobehub/lobe-icons), MIT License, © 2023 LobeHub. Other brand
logos: [Simple Icons](https://simpleicons.org) (CC0) or the brand's own website icon. Federal Register
documents are US government works (public domain). GOV.UK items contain public sector information
licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
