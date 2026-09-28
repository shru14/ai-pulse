# AI Pulse

A free, non-commercial, worldwide briefing on AI: new models and products, industry news, research,
government policy and AI laws in every country. It reads ~80 open sources every 6 hours, keeps only AI
stories, sorts them into five streams and links every card to the original.

**Live site:** https://shru14.github.io/ai-pulse/

The goal is one place that brings together the public sources needed to follow AI worldwide, using only
what is **legal to collect and publicly accessible**. No AI model, paid API or billed service is used:
summaries are the publishers' own text (or an official record's own words), and sorting is keyword rules.

## Streams

Every stream is updated every 6 hours (00:00, 06:00, 12:00 and 18:00 UTC) unless the table says otherwise.

| Stream | What's in it | Updated |
|---|---|---|
| **Releases** | New models, products and open-source launches from AI labs and companies. A company's own post counts only when it launches something; its deals, customer stories, guides and opinion go to Industry. Nothing a standards body publishes is a release | Labs' and companies' own blogs every 30 minutes; everything else every 6 hours |
| **Industry** | Company news, funding, deals, market moves and analysis, from global and regional tech press, including news about AI standards and certification, and **AI-incident** cards: every harm from an AI system that the AI Incident Database's editors confirmed since 1 January 2023, one card per incident with the editors' title and description, dated when it happened and linked to the incident's page. A story from our other feeds is labelled AI-incident only when the database lists that very article as a report of an incident (it then sits under Industry, and joins the incident's card when the database says which incident). Every other card is labelled: **News** (reporting on companies, products, deals and people), **Study** (news about research findings), **Opinion & analysis** (commentary, explainers, comparisons), **Company blog** (a lab's or company's own post that isn't a launch), **Tutorial** (guides and how-tos) or **Event** (previews, recaps, podcasts). Government publications are never Industry: they're Policy or the tracker. Filter by region, from the countries each story names | Every 6 hours; AI incidents: new ones every 6 hours, the full list weekly |
| **Research** | Research papers only: arXiv papers by ~80 leading AI professors and ~40 AI ethics, philosophy and law scholars (tagged with their field), and big-lab papers via Hugging Face Daily Papers. Every paper is tagged **#Research** | Every 6 hours (arXiv announces new papers on weekdays) |
| **Regulation tracker** | AI **proposals** and **adopted laws** by country, **AI bodies** (safety institutes, regulators, advisory offices) and published **AI standards**: international ones from ISO/IEC and IEEE (e.g. ISO/IEC 42001), and countries' own (e.g. Australia's Voluntary AI Safety Standard). Filter by region (Europe, Americas, Asia-Pacific, Middle East & Africa, International) or by country | Bills and laws every 6 hours (Korea, Vietnam and OECD.AI weekly); standards from a hand-kept list |
| **Policy** | Government, court and political action on AI: investigations, lawsuits, guidance, strategies, requests for government reports, and government standards work (e.g. NIST's frameworks, tools and initiatives) | Every 6 hours; OECD.AI records weekly |

Stories that mention standards in any stream are tagged **#Standards**.

**RSS feeds**, one per stream, with a daily digest (one post a day): [Releases](https://shru14.github.io/ai-pulse/feeds/releases.xml),
[Industry](https://shru14.github.io/ai-pulse/feeds/news.xml), [Research](https://shru14.github.io/ai-pulse/feeds/research.xml),
[Regulation tracker](https://shru14.github.io/ai-pulse/feeds/regulation.xml), [Policy](https://shru14.github.io/ai-pulse/feeds/policy.xml).

**Daily email**, free: the **Daily digest** button next to the theme switch opens a panel to pick streams and
subscribe. Every morning at about 05:00 UTC (7:00 in Germany in summer) it brings the previous UTC day in one table, with the chosen
streams' stories tagged by type (Industry's labels above; Release, Research paper, Proposal or Law adopted with
its country, Policy), a line of summary and the source. It's sent from the project's Gmail account, with no tracking
pixels or tracked links. Before sending, every story is checked, and any problem holds the email for everyone and
alerts the project inbox instead: a government publication in Industry or Releases, a paper in the tracker, a
standards story in Releases, an AI-incident outside Industry, an unlabelled Industry card, a missing or placeholder
headline, leftover HTML or garbled characters, a link that isn't a plain web address, the same story twice, a
stream with over three times its usual number of stories, or no stories at all. A story from a general outlet that
doesn't name AI is left out. A thin day (fewer than five stories) is still sent, and says it was a quiet day.

**Subscriptions** (`apps-script/Code.gs`, `aipulse/subscribers.py`): the reader types their email and picks
streams in the panel. The form posts to a Google Apps Script web app in the project's own Google account (free,
nothing billed), which keeps the list there and emails a short, plain confirm note; nothing is sent until the reader
clicks its link (link scanners can't confirm: the link opens a page with a button). Links in our emails go only to
the site, which talks to the web app (a script.google.com link in an email looks like phishing to spam filters). Entering the same address with other streams
asks to confirm the change. Every digest has the reader's own one-click unsubscribe link (also the mail apps'
Unsubscribe button), which deletes their address at once and moves our emails with them to the Trash. A hidden
field stops bots; each address gets at most three confirm emails a day, and all addresses together at most 80;
unconfirmed sign-ups are forgotten after a week; the list stops at 400 readers, under Gmail's daily sending
limit. Addresses are never in this (public) repository or its logs, which show counts only; each reader gets
their own email, so nobody sees another address.

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
5. **Credit and non-commercial use.** Every licence that asks for credit is credited below, in "Credits and licences"; every page of the site links there ("Sources and licences").
   Some licences allow only non-commercial use, so the site must stay non-commercial.

Requests go one at a time with pauses (arXiv at most every 3 seconds, as its terms ask) and identify
themselves as `AIPulse/1.0` with a link to this repository.

## Where the data comes from

### News, releases and research (`aipulse/sources.py`)

Each feed below allows automated access in its robots.txt, and its terms don't restrict headline + short
description + link (VnExpress's feed terms allow free use by non-profits that name the source; The Rio
Times' terms allow brief excerpts with credit and a link back). The AI Incident Database has no robots.txt;
its terms bar only high-volume automated access and commercial use. Incident titles and descriptions are
CC BY-SA 4.0: they're credited and stay under that licence here. A report's own text isn't under the licence,
so of the articles only their links are used.

| Stream | Sources |
|---|---|
| Releases | OpenAI, Anthropic (its news page, which has no feed; robots.txt allows all: a launch has its own page, other posts count by their headline), Google AI, Google DeepMind, Google Research, Hugging Face, Mistral, Microsoft Research, NVIDIA, AWS Machine Learning, Engineering at Meta, GitHub, Databricks, Cloudflare, Ollama, Sakana AI (English posts), Character.AI, Stability AI; AI stories from the company newsrooms of Microsoft, Meta, Apple and Amazon; and, from their news pages (no feed; robots.txt allows reading): Meta AI, DeepSeek, Cohere, MiniMax and Moonshot AI (Kimi). For those, each new post's own page is read once for its title, description and date (a page with no date gets the day it's first seen); the first read of a news page only remembers what it lists. xAI's and Perplexity's own news pages block automated readers, so from them we read only their developer release notes (docs.x.ai, docs.perplexity.ai; robots.txt allows them), keeping only launches of their own products (Grok; Perplexity, Sonar, Comet), not retirements, API settings or other labs' models they now offer; a new entry is dated the day it's first seen |
| AI incidents (Industry) | AI Incident Database (incidentdatabase.ai): its weekly Excel export (every incident since 2023, and the links of the articles attached to them) and its RSS feed of new reports, every 6 hours; a new incident's page is read once (`aipulse/incidents.py`) |
| Global news | TechCrunch, The Verge, Ars Technica, MIT Technology Review, The Decoder, SiliconANGLE, MarkTechPost, ZDNET, 404 Media, Engadget, MIT News, Tech Xplore, ScienceDaily, Rest of World |
| Regional news (AI headlines only) | **Asia:** South China Morning Post, Pandaily and TechNode (China's AI labs and launches), Focus Taiwan, Bernama (Malaysia), VnExpress International · **Africa:** TechCabal, iAfrikan, TechCentral, ITWeb, IT News Africa, Nairametrics · **Middle East & North Africa:** Wamda · **Latin America:** MercoPress, The Rio Times, Buenos Aires Times, LatinAmerica Reports |
| Policy | EU AI Act Newsletter, CSET, AI Now Institute, Future of Life Institute, EFF, EPIC, NIST, Federal Register (US), GOV.UK, Korea's Ministry of Science and ICT, Malaysia's Ministry of Digital, Russia's State Duma (English news) |
| Research | arXiv (API and daily listings: ~80 AI professors, ~40 AI ethics and law scholars), Hugging Face Daily Papers, Apple Machine Learning Research |
| Regulation tracker | European Data Protection Board, European Commission (Digital Strategy) |

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
| South Korea | National Law Information Center (law.go.kr, Ministry of Government Legislation): AI laws and decrees, read weekly. Also the Ministry of Science and ICT's English press releases | robots.txt allows everything; laws aren't copyrighted (Copyright Act, Art. 7) |
| Taiwan | Legislative Yuan law system (lis.ly.gov.tw): laws with AI in their name, e.g. the AI Basic Act | No robots.txt rules; laws aren't copyrighted (Copyright Act, Art. 9) |
| Malaysia | Parliament of Malaysia (Dewan Rakyat bill list) for AI bills when tabled, and the Ministry of Digital's English media releases | No robots.txt rules or terms restrict them |
| Vietnam | National Legal Database (vbpl.vn, Ministry of Justice), via its sitemap | robots.txt allows it; legal documents aren't copyrighted (IP Law, Art. 15) |
| Switzerland | Swiss Parliament open data (ws.parlament.ch) | opendata.swiss: "Open use. Must provide the source." |
| Russia | State Duma English news (AI headlines only) | robots.txt allows the news; no terms restrict it |
| ~60 more countries and international bodies (UN, UNESCO, G7, Council of Europe, African Union, ASEAN, ...) | OECD.AI Policy Observatory | CC BY 4.0; read weekly. For the countries above only guidance and AI bodies, so nothing appears twice. A record whose name is a standard ("Voluntary AI Safety Standard") is shown as a Standard; OECD.AI's ISO and IEEE records are left to the list below |
| International AI standards | ISO/IEC (JTC 1/SC 42, the joint AI committee) and IEEE: a hand-kept list in `aipulse/standards.py` of 18 published standards (ISO/IEC 42001, 42005, 42006, 23894, 22989, IEEE 7000, 7001, 7003, ...) | Facts only (number, title, publication date, link to the official page), each checked against that page; no standard text is copied. iso.org blocks automated readers and IEEE's robots.txt disallows its feeds, so nothing is fetched: new standards are added by hand |

How records are sorted: bills and laws go to the tracker with their stages (introduced → passed → signed
→ in force); a law stays a law after it's repealed. Switzerland's motions (demands for a law) go to the
tracker and its postulates (requests for a government report) to Policy; parliamentary questions are left
out. Standards are shown with their publication date (ISO gives the month only, so ISO cards show the month). A ministry release that reports a bill or law reaches the tracker; the rest go to Policy.

### Worldwide coverage

- **Every country is recognised** (193 places): a news story about any of them is tagged with that country
  and its region, and news of a law or bill there reaches the tracker even where no official record can be read.
- **Official records** from 14 places plus Russia's parliamentary news, **OECD.AI** for ~60 more, and
  **regional news** from Asia, Africa, the Middle East and Latin America for the rest.
- The EU counts as one (its rules apply in every member state). Russia belongs to no region.
- Coverage of any country is only as good as its official sources and the news about it.

## Run it

```bash
python -m aipulse collect     # fetch every source into aipulse.db
python -m aipulse serve       # http://127.0.0.1:8000
```

Other commands: `run --every-hours 6`, `bills` (sync official records), `backfill --since 2023-01-01`,
`reclassify`, `resummarize`, `regroup`, `evaluate`, `sources`, `status`, `build --out site`, `prune`,
`digest --to ADDRESS | --subscribers [--dry-run FILE]`. Tests: `python -m pytest -q`.

Optional: `pip install ctranslate2 sentencepiece certifi` for offline English translations and Mozilla's CA list.

## Hosting

- **GitHub Pages:** `.github/workflows/pages.yml` runs every 6 hours and on every push to `main`: it
  collects from every source, re-sorts, builds the static site and deploys it (~10–15 min). The database is carried in the Actions
  cache, starting from `data/seed.db.gz` (bump the `v4` cache key when replacing the seed).
  In between, at :25 and :55 every hour, a quick run (`collect --labs`, ~3 min) reads only the labs' and
  companies' own blogs, where launches appear first, and republishes. GitHub may start scheduled runs late.
- **Daily email:** `.github/workflows/digest.yml` sends it at 05:00 UTC from the database the 00:00 run saved,
  to the confirmed readers it reads from the sign-up web app. Secrets: `DIGEST_EMAIL`, `DIGEST_APP_PASSWORD`
  (a Gmail app password) and `DIGEST_LIST_KEY` (the web app's `LIST_KEY`). Started by hand it defaults to a dry run.
- **Sign-up web app:** `apps-script/Code.gs`, deployed from the project's Google account (script.google.com >
  New project, paste the file, set the `LIST_KEY` script property, Deploy > Web app, execute as me, anyone can
  access); its address goes in `SIGNUP_URL` in `aipulse/subscribers.py`.
- **This PC:** Task Scheduler runs `AI Pulse server` (`serve --port 8080`, at logon) and `AI Pulse collect`
  (every 6 hours).

## Layout

```
aipulse/  sources (every feed) · feeds (fetching, robots.txt, TLS) · classify · jurisdictions (193 places, regions)
          bills (official records) · oecd · standards (hand-kept AI standards) · incidents (AI Incident Database) · translate (offline) · brief · brands · backfill · cluster
          store · collect · server · static · evaluate · rss · digest (daily email) · quality (checks before sending) · subscribers
apps-script/Code.gs    the sign-up web app (runs in the project's Google account)
aipulse/certs/         public intermediate certificates some servers don't send
templates/index.html   the page
tests/                 unit and end-to-end tests
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
