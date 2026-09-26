# AI Pulse

A self-hosted briefing on what's happening in AI. AI Pulse reads company blogs, newsrooms, government
sites and research archives every 6 hours, keeps only AI stories, sorts each into one of five streams and
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
- **This week** (top of every stream): the three biggest stories of the last 7 days, ranked by how many
  outlets covered them (research: by the tracked professors and labs behind a paper; regulation tracker:
  adopted laws first). Hidden while searching.
- **Search** and the **time range** (7, 30, 90 days, all time) stay pinned while you scroll. Search matches
  word beginnings and stems ("regulate" finds "regulation") across headlines, summaries, sources, tags and authors.
- **Cards** show a logo for the company involved (or the country, or a topic symbol), a summary
  (long ones fold behind "Read more"), clickable tags, and the date and source link. The same event
  reported by several outlets is one card with "N sources".
- **Regulation tracker**: click a country chip on a card to see only that country. US bills and EU procedures show their stage,
  from introduced to in force.
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
| `summaries --since DATE` | Look up real summaries for headline-only stories since a date |
| `backfill --since DATE` | One-time history for every stream (see below) |
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
removed). Google News items carry only a headline, so the collector follows the link to the original
article and uses the description its publisher wrote (its meta tags); failing that, the lead text of
the same story on Bing News; only then a short factual draft. Every collection retries recent stories
that ended up with a draft, and `python -m aipulse summaries --since 2026-01-01` repairs a longer span
(several lookups at a time).

No AI model or paid API is used: summaries are the publishers' own text, and sorting is keyword rules.

## History back to 2023

Daily collection only sees what feeds hold today, so `python -m aipulse backfill` fills every stream back
to 1 January 2023 (`--since` for another date, `--only news|experts|research|papers` for one group):

- **News, policy, regulation:** the site's own Google News searches, one month at a time, plus searches
  standing in for the publisher and lab feeds (TechCrunch, The Verge, OpenAI, ...). Google News returns up
  to 100 stories per search, so each month is capped at that; old headline-only stories get a short
  draft summary.
- **Expert views:** each scholar's Google News search, a year at a time.
- **Research:** arXiv's search API for every listed professor and scholar, and Hugging Face Daily Papers
  day by day (from May 2023) for big tech and frontier lab papers.

It takes a couple of hours and must run on a PC (arXiv refuses cloud servers); finished searches are
remembered, so it can be stopped and resumed. To publish the result, gzip the database to
`data/seed.db.gz`, bump the `v2` in the workflow's database cache key, and push: the next run starts
from the new seed. The site loads the last 90 days at once and older cards (one file per year) only
for "All time".

## Bills from official records

| Source | Stages | What you need |
|---|---|---|
| congress.gov API | Introduced → passed one chamber → passed Congress → signed → became law (or vetoed) | A free API key ([sign up](https://api.congress.gov/sign-up/)) |
| European Parliament open data | Proposed → Parliament position → final vote → signed → Official Journal | Nothing: open data, no sign-up |

Each bill is one card dated at its latest stage, with news that names the bill attached. The key is read
from `CONGRESS_API_KEY` and never stored in the repository: set it as a repository secret for the public
site (Settings → Secrets and variables → Actions) and with `setx CONGRESS_API_KEY your-key` on this PC.
One-time backfill: `python -m aipulse bills --eu-since 2019 --us-days 30`.

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
  `PROFESSORS` or `EXPERTS` to follow more people. Google News search feeds are a quick way to follow a topic.
- **Rules and tags:** `aipulse/classify.py` and `aipulse/jurisdictions.py`.
- **Company logos:** the 12 AI companies in `COMPANY_TERMS` use the colour logos in `LOGOS`
  (`templates/index.html`). Any other brand a headline names is found automatically by `aipulse/brands.py`:
  Simple Icons' index of ~3,000 brands first, then Wikidata (a company or product with an official website,
  shown with that site's icon). Plain words like "Astra" count only if Wikidata confirms a company by that
  name. Lookups are cached in `data/` (and in the Actions cache on GitHub), so each name is checked once.

## Project layout

```
aipulse/
  sources.py        feed list, professors, experts, companies
  feeds.py          RSS/Atom fetching and parsing
  classify.py       AI relevance, stream, tag and regulatory-action rules
  jurisdictions.py  countries, blocs and US states the tracker recognises
  brief.py          headline and summary cleaning
  brands.py         brand logos found in headlines (Simple Icons, Wikidata)
  bills.py          congress.gov and European Parliament bill stages
  backfill.py       one-time history back to 2023
  cluster.py        grouping the same event into one card
  store.py          SQLite schema, full-text search, queries
  collect.py        the collection run
  evaluate.py       scoring the rules against labelled stories
  server.py         page and JSON API
  static.py         static site for GitHub Pages
templates/index.html  the page
tests/                unit and end-to-end tests with fixture feeds (python -m pytest -q)
```

AI company logos: [Lobe Icons](https://github.com/lobehub/lobe-icons), MIT License, © 2023 LobeHub. Other brand
logos: [Simple Icons](https://simpleicons.org) (CC0) or the brand's own website icon.
