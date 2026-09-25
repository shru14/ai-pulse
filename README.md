# AI Pulse (self-hosted)

A small, dependency-free tracker for AI news. It pulls RSS/Atom feeds, keeps only AI stories,
sorts each into **Releases & tools**, **Industry news**, **Policy & politics**, **Research papers** or the
**Regulation tracker**,
and shows them as a filterable feed with the source link, a summary of what the story covers, and the date.

The **Research papers** tab lists papers only (no news or blog posts), each tagged with the professor
or company behind it:

- **Professors**: new arXiv papers (CS and ML categories) by about 80 leading AI professors across North
  America, Europe, Asia, the Middle East and Oceania (`PROFESSORS` in `aipulse/sources.py`). A paper is kept
  only when one of its authors matches a listed name exactly, which filters out namesakes
- **Big tech and frontier labs**: papers claimed on Hugging Face Daily Papers by one of the companies in
  `COMPANIES` (Google/DeepMind, Microsoft, Meta, Apple, Amazon, NVIDIA, Alibaba/Qwen, Tencent, ByteDance,
  DeepSeek, OpenAI, Anthropic and others), plus Apple's own paper feed

The **Regulation tracker** tab is a daily feed of AI **proposals** (bills, draft rules, consultations) and
**adopted laws** (signed, passed, in force, executive orders), each tagged with its jurisdiction, plus
**expert views**: what about 40 AI ethics, philosophy and law scholars (`EXPERTS` in `aipulse/sources.py`)
publish or are quoted on, from a daily Google News search per person and their arXiv papers.

Requires Python 3.10+. No packages to install.

## Quick start

```bash
python -m aipulse collect     # fetch all sources once into aipulse.db
python -m aipulse serve       # open http://127.0.0.1:8000
```

Or run both together, re-collecting every 6 hours:

```bash
python -m aipulse run --every-hours 6
```

## What you get

| URL | What it is |
|---|---|
| `/` | The feed page: category tabs, search, time range, stories grouped by day |
| `/api/items?category=policy&q=EU&days=7&page=1` | One page of cards (40 by default, `per_page` up to 200) plus tab counts; `place=FR` filters the tracker by country; `grouped=0` returns separate stories |
| `/api/sources` | Health of every source |

### Regulation tracker details

Proposals and laws are tagged with the jurisdiction (country, `EU`, or `INTL` for bodies like the UN and
OECD). A world map at the end shades each country by how many proposals and laws it had in the selected
time range (EU-wide ones count for every member state); click a country or a row in the table under it
to filter the list. Open the tab directly at `/#regulation`.

Proposals and laws get there two ways: policy stories from any feed whose headline names both the action
and a jurisdiction, and dedicated sources (the EDPB, the European Commission's digital strategy news, and
Google News searches for new laws, bills and rules by region). Enforcement, investigations and guidance
stay under Policy. The keyword rules live in `ACTIONS` in `aipulse/classify.py` and
`aipulse/jurisdictions.py`; `TRACKED_ACTIONS` in `aipulse/collect.py` picks which actions the tracker
shows. After changing them, run `python -m aipulse reclassify` to re-sort stories already stored.

Expert views are articles that mention the person, found by searching their name, so some are interviews
or quotes rather than pieces they wrote. To follow someone else, add them to `EXPERTS`.

## Headlines and summaries (no API key needed)

`aipulse/brief.py` tidies every story as it's collected: headlines lose desk labels ("Watch:",
"Eurobites:") and trailing site names, and summaries keep the first one or two informative sentences
without boilerplate (author bios, "The post … appeared first on", newsletter prompts). Google News
items carry only a headline, so the collector looks the headline up on Bing News RSS and uses the lead
text of the matching story; if there's no close match it writes a short draft from what it knows
("A proposal in the United Kingdom, involving Google."). A summary never repeats its headline.
Run `python -m aipulse resummarize` to apply changes to stories already stored.

## Bills through their lifecycle

The regulation tracker follows AI bills from official records, not just the news:

| Source | What it gives | Access |
|---|---|---|
| congress.gov API | US federal bills and joint resolutions with AI in the title: introduced, passed one chamber, passed Congress, signed, became law (or vetoed) | Free key from https://api.congress.gov/sign-up/; without one the shared `DEMO_KEY` is used (about 30 requests an hour) |
| European Parliament open data | EU legislative procedures (COD) with AI in the title: proposed, Parliament position, final vote, signed, published in the Official Journal | No key |

Each bill is one card in the tracker, dated at its latest stage so it moves up the feed when it advances,
with the whole timeline on the card. News stories that name the bill (by number, e.g. "H.R. 10538", or by
short title, e.g. "Artificial Intelligence Act") are attached to the same card. Every collection checks
for bills updated since the last sync; the one-time backfill is:

```bash
python -m aipulse bills --eu-since 2019 --us-days 30
```

Set your congress.gov key for the scheduled tasks with `setx CONGRESS_API_KEY your-key` (then restart the
tasks). Not connected yet: US state legislatures (needs an Open States API key) and the OECD.AI policy
database (no public API).

US stories also record their state (`US-OR` next to `US`, from state names, governors and abbreviations
like "Ore."), and the tracker's map section has a second map of the US by state.

## Search and paging

The page never downloads every story. The server filters, searches and pages the stories, and the page
asks for 40 cards at a time ("Load more" appears at the bottom and also loads by itself as you scroll).

- **Search** uses SQLite's FTS5 full-text index over headlines, summaries, sources, tags and authors, kept
  in sync by triggers. Words match by prefix and stem ("regulat" and "regulate" find "regulation"),
  accents are ignored, and a card matches if any outlet's version of the story does.
- **Cards** are stored: each story records its card's lead story (`cluster`). New stories are grouped
  after every collection (the last 14 days are regrouped); `python -m aipulse regroup` regroups everything.
- On a test database of 40,000 stories (over a year at ~100 a day) page requests take 30-250 ms and
  adding a story takes under a millisecond.

## Source health

Every fetch is retried when a host is busy: HTTP 429 (rate limit) and 5xx errors and network timeouts
wait 2s, then 6s (or the server's `Retry-After`, up to 60s) before giving up. arXiv and Hugging Face
always list their latest papers, so an empty reply from them is retried too and counts as a failure if
it stays empty. Each source's last attempt, last success, failures in a row and last error are stored,
and the page header shows "⚠ N sources failing" once a source has failed 3 collections in a row (click
it for details). One good fetch clears the warning.

- `python -m aipulse sources` prints the health of every source
- `/api/sources` returns the same as JSON

## Measuring the sorting rules

`tests/fixtures/labels.csv` holds 100 stories labelled by hand with the right tab, and for tracker
stories the action and jurisdictions. `python -m aipulse evaluate` runs the keyword rules over them and
prints accuracy plus every mistake; a test keeps the scores from dropping below the floors in
`tests/test_aipulse.py`. Labelling rules:

- **regulation**: a government, legislature or regulator officially *proposes* a rule (bill, draft
  rules, formal proposal) or *adopts* one (law passed or signed, in force, executive order).
  Jurisdictions are where the acting government is, not countries it's about.
- **policy**: other government and AI stories: investigations, lawsuits, debates, statements,
  explainers, guidance, and companies' submissions to governments.
- **news** / **tool**: industry news; product, model or feature releases.

To correct a label, edit the `category`, `action` or `jurisdictions` cell (codes like `US`, `EU`,
comma-separated) and re-run the evaluation.

## Better summaries with Claude (optional)

Set an API key and the collector will ask Claude to write a neutral 1-2 sentence summary,
pick the category, add tags, and drop stories that aren't really about AI:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export AIPULSE_MODEL=claude-haiku-4-5-20251001   # optional; this is the default
python -m aipulse collect
```

Without a key it uses keyword rules (`aipulse/classify.py`), which work offline and cost nothing.

## Customize

- **Sources:** edit `aipulse/sources.py`. Any RSS or Atom feed works; give each a default category.
  To follow another researcher, add their name to `PROFESSORS`.
  Google News search feeds (`news.google.com/rss/search?q=...`) are a quick way to follow a topic,
  e.g. a country's AI legislation.
- **Categories and tags:** keyword lists live in `aipulse/classify.py`.
- **Retention:** `python -m aipulse prune --keep-days 180`.

## Keep it updating every 6 hours

Run the web server and the collector as two separate scheduled jobs, so updates survive restarts and
don't depend on a terminal staying open. `--log FILE` appends output to a file for windowless runs.

**Windows (Task Scheduler)** — this machine uses two tasks:

| Task | Trigger | Runs |
|---|---|---|
| `AI Pulse server` | at logon; restarts if it crashes | `pythonw -m aipulse --log server.log serve --port 8080` |
| `AI Pulse collect` | every 6 hours (00:00, 06:00, 12:00, 18:00); a run missed while the PC was off or asleep starts as soon as possible | `pythonw -m aipulse --log collect.log collect` |

Check them with `Get-ScheduledTask "AI Pulse*" | Get-ScheduledTaskInfo`, run a collection now with
`Start-ScheduledTask "AI Pulse collect"`, and see what each run did in `collect.log`. Remove them with
`Unregister-ScheduledTask "AI Pulse server"` (and `"AI Pulse collect"`).

**Linux / macOS (cron):**

```cron
0 */6 * * * cd /path/to/ai-pulse-app && python3 -m aipulse --log collect.log collect
@reboot     cd /path/to/ai-pulse-app && python3 -m aipulse --log server.log serve --host 0.0.0.0
```

For a quick single process instead, `python -m aipulse run --every-hours 6` serves and collects on a
timer (a failed collection is logged and retried next cycle), but it stops when that process does.

## Publish on GitHub Pages (free, no PC needed)

`python -m aipulse build --out site` writes a static copy of the site: the page, the two maps and
`data.json` with every card. The page sees `data-static="1"` and filters, searches and pages
`data.json` in the browser instead of calling `/api/items` (search is a close match to the server's:
every word must start a word of the story, with light stemming).

`.github/workflows/pages.yml` does this on GitHub every 6 hours (00:00, 06:00, 12:00, 18:00 UTC), on
every push to `main`, and on demand (Actions → Collect and publish → Run workflow). It carries the
database between runs in the Actions cache and starts from `data/seed.db` when there is none.

1. Push this folder to a **public** GitHub repository.
2. Settings → Pages → Source: **GitHub Actions**.
3. Optional: Settings → Secrets and variables → Actions → `CONGRESS_API_KEY`.

The site is then at `https://<user>.github.io/<repo>/`. GitHub pauses scheduled workflows in a repository
with no commits for 60 days; it emails a warning, and one click (or any commit) turns them back on.

## Tests

```bash
python -m pytest -q
```

## Project layout

```
aipulse/
  sources.py    feed list
  feeds.py      RSS/Atom fetching and parsing (stdlib XML)
  classify.py   AI relevance, category, tag and regulatory-action rules
  jurisdictions.py  countries/blocs the regulation tracker recognises
  geo.py        builds templates/world.json (the tracker's map) from Natural Earth data
  enrich.py     optional Claude summaries via the Messages API
  store.py      SQLite schema, dedupe, queries
  collect.py    the collection run
  server.py     page + JSON API
  static.py     static copy of the site for GitHub Pages
templates/index.html   the feed page
templates/world.json   pre-projected world map paths (regenerate with python -m aipulse.geo)
tests/                 unit and end-to-end tests with fixture feeds
```
