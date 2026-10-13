"""Papers that made the news (papers-in-the-news/): the research papers that news outlets we read reported on, each
checked by hand, by subject, next to the subjects of the papers we read ourselves. Which AI research does the press
write about?

Every row in CHECKED is a news story read by hand and the paper it reports on, found through the story's own link (or,
when it gives none, by the paper's name on arXiv): its title, its address, the subject it was put under by hand and
what it found in one plain sentence, written from the paper's whole abstract when the row is checked (by Claude, as
the glossary's words are; the owner approves). Only papers on a preprint server, in a journal or at a conference
count; company pages, blog posts, polls, surveys and data reports are left out, as are stories whose paper we
couldn't find.

The sample starts on SINCE (the owner's choice, 13 Oct 2026: the last 3 months, not all of 2026). `python -m aipulse
press` lists the stories since then that may report on a paper and aren't checked yet. The subjects are the Research stream's (kind_pages.SUBJECTS) plus "AI and people". The papers
we read are counted by the Research pages' own rule (title words), so the two sides are counted differently, and the
page says so. Linked from Research's strip on the front page.
"""
from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

from . import kind_pages, pages, rss

PATH = "papers-in-the-news/"
SINCE = "2026-07-13"
QUESTION = "Which AI research does the press write about?"

# subject: its words on the page. The Research stream's subjects, plus one for papers on AI and people
SUBJECTS = {k: label for k, (label, _, _) in kind_pages.SUBJECTS.items()} | {"people": "AI and people"}

# Every paper the page shows, by the URL of the news story we read it in: the paper's title and address, its subject
# (set by hand) and what it found in plain words, from its whole abstract. Checked 13 Oct 2026.
CHECKED: dict[str, dict] = {
    "https://the-decoder.com/google-deepminds-alphaproof-nexus-solved-dozens-of-open-math-problems-and-actually-got-peer-reviewed/":
        dict(paper="Advancing mathematics research with AI-driven formal proof search",
             link="https://doi.org/10.1126/science.aej2213", subject="science",
             about="Shows AI can autonomously discover mathematical proofs by generating them and verifying them with a "
                   "formal system."),
    "https://the-decoder.com/clearing-chat-history-helps-ai-agents-find-better-solutions/":
        dict(paper="Fork-and-Flush: Escaping Idea Basins in Autoresearch Agents", link="https://arxiv.org/abs/2610.07447",
             subject="agents",
             about="Shows that periodically restarting an AI's thinking process helps it find better solutions by breaking "
                   "out of repetitive patterns."),
    "https://pandaily.com/bytedance-seed-phase-sensitivity-chunked-kv-cache-compression-deepseek-v4":
        dict(paper="Periodic Weak Spots: Phase Sensitivity from Chunked KV-Cache Compression",
             link="https://arxiv.org/abs/2609.36322", subject="efficiency",
             about="Shows that AI models which compress their memory of long texts can find a fact easily at one position "
                   "and miss it at another, by up to 40 points."),
    "https://the-decoder.com/google-researchers-find-a-way-to-keep-self-improving-ai-agents-from-memorizing-their-tests/":
        dict(paper="RRSI: Regularized Recursive Self-Improvement of Agent Harnesses", link="https://arxiv.org/abs/2609.24972",
             subject="agents",
             about="Tests a way for AI agents to improve their own tools and instructions without just memorising the test "
                   "tasks, so the gains carry over to new ones."),
    "https://the-decoder.com/ai-access-makes-people-almost-entirely-unwilling-to-say-i-dont-know-study-finds/":
        dict(paper="AI advice suppresses people’s willingness to say “I don’t know”, even when the advice is wrong and "
                   "accuracy is incentivized",
             link="https://osf.io/preprints/psyarxiv/5y6m4_v1", subject="people",
             about="Shows that AI suggestions make people less likely to admit they don’t know, even when the advice is "
                   "wrong."),
    "https://the-decoder.com/bristol-researchers-say-medicine-already-knows-how-to-handle-black-boxes-and-ai-could-learn-from-it/":
        dict(paper="What Can Artificial Intelligence Learn from Medicine? Generative Analogies and Reliable Machine "
                   "Learning Systems",
             link="https://arxiv.org/abs/2608.18186", subject="safety",
             about="Argues that the standards medicine uses to trust new treatments can guide how we judge whether AI "
                   "systems are reliable."),
    "https://www.marktechpost.com/2026/09/16/stanford-researchers-release-paper2agent-turning-research-papers-into-ai-agents-that-reproduce-results-and-run-on-new-data/":
        dict(paper="Paper2Agent: Reimagining Research Papers As Interactive and Reliable AI Agents",
             link="https://arxiv.org/abs/2509.06917", subject="agents",
             about="Turns research papers into interactive AI assistants that can understand, reuse, and extend the "
                   "paper's methods to answer new questions."),
    "https://the-decoder.com/two-year-university-study-finds-banning-ai-from-classrooms-leaves-students-worse-off/":
        dict(paper="Generative AI in Legal Education: A Two-Year Experiment with ChatGPT",
             link="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5401422", subject="people",
             about="Finds that law students taught how to use ChatGPT did better in the first year, but the edge faded in "
                   "the second as students got used to AI."),
    "https://the-decoder.com/ai-designed-drug-appears-to-turn-back-the-bodys-biological-clock-in-early-trial/":
        dict(paper="Integration of proteomic aging clocks in a phase 2a clinical trial supports simultaneous "
                   "geroprotective assessment",
             link="https://doi.org/10.1038/s41587-026-03286-y", subject="science",
             about="Finds that six blood-protein measures of biological age all saw younger ages in patients on a "
                   "lung-scarring drug, though they can't tell slower ageing from the drug's effect on the disease."),
    "https://the-decoder.com/google-deepminds-ai-co-scientist-now-plans-experiments-runs-lab-equipment-and-writes-scientific-papers/":
        dict(paper="Accelerating Scientific Research with Gemini in the Real-World", link="https://arxiv.org/abs/2608.26701",
             subject="science",
             about="Shows how AI can help scientists design experiments, predict biological behaviors, and create better "
                   "computer models, all while improving safety and reducing errors."),
    "https://the-decoder.com/ai-shopping-agents-arent-ready-to-buy-on-your-behalf-study-finds/":
        dict(paper="Research Report 6: Agentic Shopping is Complicated and Contingent",
             link="https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7355899", subject="agents",
             about="Tests how AI shopping choices change with different information sources, orders, and user memories, "
                   "finding that small changes often lead to very different product picks."),
    "https://the-decoder.com/ai-could-make-scientists-do-more-work-less-well-not-less-work-better-study-argues/":
        dict(paper="The unintended consequences of large language models as a labor-augmenting technology in science",
             link="https://arxiv.org/abs/2607.17397", subject="people",
             about="Uses a simple model to argue that AI tools which speed up research may lead scientists to polish their "
                   "papers less before moving on."),
    "https://the-decoder.com/the-tragedy-of-the-cognitive-commons-explains-how-rational-ai-adoption-could-destroy-entire-professions-expertise/":
        dict(paper="The Tragedy of the Cognitive Commons: How AI Could Disrupt the Regeneration of Professional Expertise",
             link="https://arxiv.org/abs/2607.29380", subject="people",
             about="Argues that sensible choices to use AI at work could, added up, wear away the shared expertise "
                   "professions need to train new experts."),
    "https://the-decoder.com/but-marinade-and-leaked-passwords-are-what-researchers-found-in-chatgpts-hidden-reasoning/":
        dict(paper="Stealing Reasoning Traces from Proprietary LLM APIs", link="https://arxiv.org/abs/2608.09867",
             subject="safety",
             about="Shows how encrypted reasoning traces can be stolen and used to reveal private data, dangerous content, "
                   "and hidden attacks across models."),
    "https://the-decoder.com/readers-rate-ai-generated-short-stories-higher-than-human-ones-until-they-learn-a-machine-wrote-them/":
        dict(paper="Bot or not? Can people tell the difference between stories written by a human or by an AI system",
             link="https://www.cambridge.org/core/journals/judgment-and-decision-making/article/bot-or-not-can-people-"
                  "tell-the-difference-between-stories-written-by-a-human-or-by-an-ai-system/45E6DC0BB90AA648654D5AE243F6C667",
             subject="people",
             about="Finds that people can't tell AI-written stories from human ones, and rate the AI stories higher until "
                   "told a machine wrote them."),
    "https://the-decoder.com/stanford-and-arc-institute-scientists-used-ai-to-design-new-viruses-that-killed-bacteria-in-the-lab/":
        dict(paper="Generative design of bacteriophages with genome language models",
             link="https://doi.org/10.1126/science.aec2657", subject="science",
             about="Uses AI to design whole viruses that infect bacteria; 16 worked in the lab, and a mix of them beat "
                   "bacteria that resisted the original virus."),
    "https://the-decoder.com/two-teams-solved-the-same-quantum-crypto-problem-using-gpt-5-6-just-three-hours-apart/":
        dict(paper="Efficient Unclonable Encryption from Pauli Eigenstates", link="https://arxiv.org/abs/2607.21811",
             subject="science",
             about="Builds a quantum way to encrypt a message that can't be copied: two people can never both read it."),
}

# Stories from SINCE checked and left out, so `python -m aipulse press` doesn't list them again: not about one paper,
# or about a company page, blog post, poll or report, or the paper couldn't be found or checked.
LEFT_OUT = {
    "https://the-decoder.com/anthropic-study-warns-that-small-ai-models-could-soon-replicate-across-everyday-devices/",  # a company research page, not a paper
    "https://the-decoder.com/arxiv-caps-submissions-at-two-per-month-as-ai-paper-flood-overwhelms-the-preprint-server/",
    "https://the-decoder.com/ai-agents-overstate-their-results-and-remain-far-from-autonomous-research-study-finds/",  # a company report (Epoch AI), not a paper
    "https://www.marktechpost.com/2026/10/10/sakana-ais-llm-peer-review-system-catches-73-of-core-claim-errors/",  # the outlet refuses automated reads; no paper found on arXiv
    "https://w.media/sesterce-plans-e-10-billion-ai-campus-in-finland/",
    "https://theconversation.com/is-this-the-mathocalypse-why-openais-latest-results-dump-has-left-mathematicians-in-shock-293837",
    "https://e.vnexpress.net/news/news/education/dartmouth-provost-accused-of-using-ai-to-write-nearly-all-his-papers-5129097.html",
    "https://the-decoder.com/a-single-prompt-was-enough-to-hijack-every-ai-agent-in-an-aws-account-zenity-researchers-found/",
    "https://theconversation.com/a-biologist-queries-whether-ai-borrowed-his-work-to-make-major-discovery-an-expert-explains-the-rules-293529",
    "https://www.itnewsafrica.com/artificial-intelligence/chatgpt-in-south-africa/",
    "https://pandaily.com/rice-full-lifecycle-3d-spatiotemporal-cell-atlas-cell-sustech-bgi",
    "https://www.quantamagazine.org/as-ai-closed-in-on-unique-games-proof-researchers-raced-to-beat-the-machines-20261007/",  # the paper is a maths proof written by people, not AI research
    "https://siliconangle.com/2026/10/07/openai-publishes-722-ai-generated-math-discoveries-in-major-scientific-milestone/",  # a company page, not a paper
    "https://theconversation.com/why-most-health-apps-are-biased-even-before-their-first-lines-of-code-are-written-286261",
    "https://www.itweb.co.za/article/ai-meets-sa-education-saving-grace-ai-tutor-opens-free-grade-12-tutor-access/GxwQDM1Dy8a7lPVo",
    "http://www.bernama.com/en/news.php?id=2616201",
    "https://w.media/vitro-reit-meralco-undertake-feasibility-study-on-philippines-data-center-power/",
    "https://w.media/us-agency-backs-hyperscale-data-center-and-fiber-network-study-in-colombia/",
    "https://the-decoder.com/ai-is-eroding-office-hours-study-groups-and-the-trust-between-faculty-and-students-mit-report-finds/",
    "https://www.404media.co/arxiv-is-rate-limiting-submissions-because-it-cant-keep-up-with-ai-slop/",
    "https://theconversation.com/weve-tracked-80m-of-spending-on-almost-170-ai-generated-political-ads-this-year-its-weird-292105",
    "https://the-decoder.com/chinese-ai-models-parrot-state-doctrine-or-refuse-to-answer-on-sensitive-topics/",  # a company blog post (Aleph Alpha)
    "https://w.media/cushman-wakefield-aptelecom-to-undertake-feasibility-study-on-ho-chi-minh-city-data-center/",
    "https://the-decoder.com/ai-beats-licensed-accountants-on-speed-and-accuracy-but-still-cant-close-the-books-without-supervision/",  # a company blog post (Mercor)
    "https://news.mit.edu/2026/algorithmic-monoculture-effects-depend-on-details-0929",
    "https://techcrunch.com/2026/09/28/insuretech-outmarket-raises-34-5m-just-months-after-prior-round/",
    "https://www.marktechpost.com/2026/09/25/perplexity-trains-its-computer-agent-on-real-mistakes-with-hint-guided-self-distillation/",  # the outlet refuses automated reads; no paper found on arXiv
    "https://the-decoder.com/top-ai-experts-badly-underestimated-how-fast-the-field-is-moving-study-finds/",  # a survey (Forecasting Research Institute), not a paper
    "https://news.mit.edu/2026/studying-cities-using-visual-ai-fabio-duarte-martina-mazzarello-carlo-ratti-fan-zhang-book-0924",
    "https://www.itweb.co.za/article/r101m-uct-project-brings-ai-microscopy-to-africa/LPp6V7rBYJb7DKQz",
    "https://the-decoder.com/openai-says-its-internal-model-solved-over-100-long-standing-math-problems-after-just-a-month-of-training/",  # no paper
    "https://news.mit.edu/2026/poitras-center-to-fuel-early-careers-50-young-scientists-psychiatric-disorders-research-0922",
    "https://techcrunch.com/2026/09/21/with-tabby-a-former-accountant-is-using-ai-to-make-accountants-obsolete/",
    "https://the-decoder.com/ai-conference-iclr-is-drowning-in-abstracts-with-roughly-50000-submissions-before-the-deadline/",
    "https://siliconangle.com/2026/09/17/netsuite-ai-agents-new-audit-assurance-gap-amplify/",
    "https://news.mit.edu/2026/studying-society-accurately-naoki-egami-0916",
    "https://techcabal.com/2026/09/16/life-in-tech-segun-samuel/",
    "https://ainowinstitute.org/news/press/ai-governance-reaches-crisis-point-ahead-of-trump-xi-summit",
    "https://the-decoder.com/ai-models-written-reasoning-steps-correspond-to-distinct-internal-patterns-a-new-study-finds/",  # no paper linked or found on arXiv
    "https://www.sciencedaily.com/releases/2026/09/260911003858.htm",
    "https://www.sciencedaily.com/releases/2026/09/260911003845.htm",
    "https://the-decoder.com/openai-researcher-allegedly-pressured-mathematician-to-drop-anthropic-co-author-from-math-breakthrough-paper/",  # a dispute over a paper posted on OpenAI's own site
    "https://www.gov.uk/government/publications/a-study-of-cybersecurity-literature-on-open-source-software-and-ai",
    "https://the-decoder.com/how-ai-wiped-out-an-entire-industry-in-nairobi/",
    "https://www.gov.uk/government/collections/ai-cyber-security",
    "https://the-decoder.com/seven-minutes-with-a-chatbot-beat-a-fact-sheet-at-reducing-conspiracy-beliefs-in-two-experiments/",  # the preprint server's robots.txt refuses us, so its title can't be checked
    "https://the-decoder.com/ai-systems-are-reaching-out-to-philosophers-and-scientists-with-questions-about-their-own-consciousness/",
    "https://the-decoder.com/ai-agents-have-no-sense-of-time-and-are-not-aware-of-it/",  # a forum post, not a paper
    "https://the-decoder.com/anthropics-claude-code-limit-change-is-a-raise-on-paper-but-a-cut-in-practice/",
    "https://techcrunch.com/2026/08/26/ex-meta-scientists-want-to-bring-visual-ai-to-the-factory-floor/",
    "https://the-decoder.com/pew-study-shows-ai-written-text-has-surged-across-the-web-since-late-2022/",  # a poll and data report (Pew), not a paper
    "https://techcrunch.com/2026/08/22/inherent-founded-by-deepmind-alumni-says-its-ai-teammate-just-outperformed-anthropic-and-openai-at-replicating-research/",
    "https://techcrunch.com/2026/08/22/frontier-ai-labs-still-wont-say-how-theyd-contain-a-rogue-model/",
    "https://the-decoder.com/study-explains-why-ai-agents-benefit-from-skills-and-when-they-fail/",  # no paper linked or found on arXiv
    "https://www.marktechpost.com/2026/08/21/building-agentic-document-intelligence-pipelines-creating-scientific-figures-with-autofigure/",
    "https://techcrunch.com/2026/08/20/a-third-of-webpages-published-since-chatgpts-launch-show-signs-of-ai-authorship-study-finds/",  # a data report (Pew), not a paper
    "https://techcrunch.com/2026/08/19/google-launches-new-study-tools-for-students-across-search-and-gemini/",
    "https://techcrunch.com/2026/08/19/researchers-complain-that-openai-revoked-their-access-to-limited-cyber-program/",
    "https://blog.google/products-and-platforms/products/search/back-to-school-study-tools/",
    "https://news.mit.edu/2026/when-ai-art-has-no-author-generated-images-often-cant-be-traced-to-training-data-0818",
    "https://www.sciencedaily.com/releases/2026/08/260816044853.htm",
    "https://the-decoder.com/when-ai-models-arent-allowed-to-reflect-on-themselves-it-changes-their-entire-worldview/",  # no paper linked or found on arXiv
    "https://www.sciencedaily.com/releases/2026/08/260815064803.htm",
    "https://the-decoder.com/study-contradicts-anthropic-and-openai-claims-that-autonomous-ai-research-is-within-reach/",  # an evaluation website, not a paper
    "https://techcrunch.com/2026/08/13/anthropic-set-ai-agents-loose-on-the-same-task-they-started-a-turf-war/",  # a company research page, not a paper
    "https://research.google/blog/advancing-amie-towards-expert-level-audio-visual-clinical-consultations/",
    "https://the-decoder.com/fields-medalist-who-published-a-paper-on-ai-driven-human-extinction-now-works-for-openai/",
    "https://news.mit.edu/2026/solving-solvent-problem-sodium-metal-batteries-0804",
    "https://news.mit.edu/2026/medical-ai-assistance-benefits-vary-based-on-user-expertise-0804",
    "https://the-decoder.com/alibabas-open-weight-qwen3-8-max-takes-on-long-horizon-ai-tasks-with-2-4-trillion-parameters/",
    "https://techcrunch.com/2026/07/30/forward-deployed-engineers-are-the-ai-industrys-latest-talent-obsession/",
    "https://the-decoder.com/language-models-cant-spark-scientific-revolutions-but-world-models-might/",  # no paper linked or found on arXiv
    "https://siliconangle.com/2026/07/29/openai-opens-new-chatgpt-academic-researchers-program-100000-scientists/",
    "https://www.msit.go.kr/eng/bbs/view.do?sCode=eng&mId=4&mPid=2&bbsSeqNo=42&nttSeqNo=1286",
    "https://www.gov.uk/government/publications/skills-for-ai-what-works-for-ai-upskilling-in-the-uk",
    "https://www.sciencedaily.com/releases/2026/07/260718010149.htm",
    "https://research.google/blog/symptomai-towards-a-conversational-ai-agent-for-everyday-symptom-assessment/",
    "https://www.gov.uk/government/publications/ofquals-approach-to-regulating-the-use-of-artificial-intelligence-in-the-qualifications-sector",
    "https://the-decoder.com/claude-values-study/",  # a company research page, not a paper
    "https://www.sciencedaily.com/releases/2026/07/260713084850.htm",  # a book, not a paper
    "https://www.sciencedaily.com/releases/2026/07/260712011757.htm",
}

# a headline (or the start of its summary) that may report on a paper
PAPERISH = re.compile(r"\b(stud(?:y|ies)|paper|preprint|researchers (?:find|found|show|say)|scientists|published in|"
                      r"arxiv|peer[- ]review)", re.I)
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def papers(cards: list[dict]) -> list[dict]:
    """The papers in CHECKED whose story we have, newest story first, each with its story (title, source, date, url)."""
    by_url = {s["url"]: s for c in cards for s in [c, *(c.get("also") or [])]}
    out = [row | {"url": url, "title": s["title"].strip(), "source": s["source"], "date": s["date"]}
           for url, row in CHECKED.items() if (s := by_url.get(url))]
    return sorted(out, key=lambda r: r["date"], reverse=True)


def candidates(cards: list[dict], since: str = SINCE) -> list[dict]:
    """News stories from `since` that may report on a paper and are neither in CHECKED nor LEFT_OUT, newest first."""
    out = []
    for c in sorted(cards, key=lambda c: c["date"], reverse=True):
        if c["date"] < since or c["category"] in ("research", "regulation"):
            continue
        if any(s["url"] in CHECKED or s["url"] in LEFT_OUT for s in [c, *(c.get("also") or [])]):
            continue
        if PAPERISH.search(c["title"]) or PAPERISH.search((c.get("summary") or "")[:300]):
            out.append(c)
    return out


def read_subjects(cards: list[dict], since: str = SINCE) -> tuple[dict[str, int], int]:
    """The papers we read from `since`, per subject by the Research pages' rule (a paper can count under several,
    or none), and how many papers in all."""
    titles = [c["title"] for c in cards if c["category"] == "research" and c["date"] >= since]
    return ({k: sum(bool(re.search(rx, t, re.I)) for t in titles) for k, (_, _, rx) in kind_pages.SUBJECTS.items()},
            len(titles))


def _day(d: str) -> str:
    day = date.fromisoformat(d)
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"


def _clip(r: dict, lead: bool = False) -> str:
    """One paper as a newspaper clipping: its subject, the outlet's headline, what the paper found in plain words, then
    the paper and the story's outlet and date."""
    return (f'<article class="np-clip{" np-lead" * lead}"><div class="np-kick">{escape(SUBJECTS[r["subject"]])}</div>'
            f'<h3><a href="{escape(r["url"])}" rel="noopener">{escape(r["title"])}</a></h3>'
            f'<p class="np-deck">{escape(r["about"])}</p>'
            f'<p class="np-by">The paper: <a href="{escape(r["link"])}" rel="noopener">{escape(r["paper"])}</a></p>'
            f'<p class="np-by">{escape(r["source"])} · {_day(r["date"])}</p></article>')


def _front(rows: list[dict]) -> str:
    """The papers as a newspaper page: the newest story leads across the top, the rest in columns, newest first."""
    if not rows:
        return ""
    return ('<section class="np"><div class="np-mast"><span>The papers in the news</span>'
            f'<span>Since {_day(SINCE)} · {_plural(len(rows), "paper")}</span></div>'
            f'{_clip(rows[0], lead=True)}<div class="np-cols">{"".join(_clip(r) for r in rows[1:])}</div></section>\n')


def _limits(rows: list[dict], read: int) -> str:
    """What these papers can't tell us, as a table: each limit and why it matters."""
    from collections import Counter
    top, top_n = (Counter(r["source"] for r in rows).most_common(1) or [("", 0)])[0]
    limits = [
        (f"{_plural(len(rows), 'paper')} since {_day(SINCE)}",
         "Only stories from the outlets we read, each checked by hand. Too few for shares, so the page gives counts."),
        ("The two sides are counted differently",
         "Each paper in the news is put under one subject by hand. The papers we read are counted by the words in "
         "their titles, as on the Research pages, so one can count under several subjects, or none."),
        ("The papers we read are mostly computer science",
         f"They are the {read:,} new papers we read from arXiv's AI sections and Hugging Face's daily list. Papers "
         "from psychology, economics or law, which the press covers too, are mostly not among them."),
        *([(f"{top_n} of the {len(rows)} stories are from {top}",
             "One outlet writes most of the stories about papers that we read, so its choices shape the list.")]
          if rows and top_n * 2 > len(rows) else []),
        ("Some stories are left out",
         "Stories about a company page, blog post, poll or report, and stories whose paper we couldn't find or "
         "check, aren't counted."),
    ]
    body = "".join(f"<tr><td><b>{escape(a)}</b></td><td>{escape(b)}</td></tr>" for a, b in limits)
    return ('<section class="jb-lim"><h2>What these papers can\'t tell us</h2>\n<table class="mt jb-limits"><thead><tr>'
            f'<th>Limit</th><th>Why it matters</th></tr></thead><tbody>{body}</tbody></table></section>\n')


def page_body(rows: list[dict], read_by: dict[str, int], read: int) -> str:
    """The page under the masthead: the papers in the news by subject next to the papers we read, a chapter per
    subject with its papers, and what the papers can't tell us. Every number is worked out from the rows."""
    groups = {k: [r for r in rows if r["subject"] == k] for k in SUBJECTS}
    order = sorted(SUBJECTS, key=lambda k: (-len(groups[k]), -read_by.get(k, 0)))
    def ours(k: str) -> str:
        r = read_by.get(k)
        if r is None:
            return '<span class="pn-pc">Not a Research subject</span>'
        return f'<b>{r:,}</b> of {read:,}<span class="pn-pc"> · {r / read:.0%}</span>'

    table = ('<table class="mt pn-subjects"><thead><tr><th>Subject</th><th>Papers in the news</th>'
             '<th>Papers we read</th></tr></thead><tbody>'
             + "".join(f'<tr><td class="pn-sub">{escape(SUBJECTS[k])}</td><td class="pn-num"><b>{len(groups[k])}</b> of '
                       f'{len(rows)}</td><td class="pn-num">{ours(k)}</td></tr>'
                       for k in order if groups[k] or read_by.get(k))
             + '</tbody></table>')
    intro = (f"{_plural(len(rows), 'research paper')} that news outlets we read reported on since {_day(SINCE)}, each "
             "checked by hand: the paper the story is about, its subject, and what it found in one plain sentence. Next "
             "to them, the papers we read ourselves in the same months. New papers are added once checked.")
    return (f'<div class="ft jb pn">\n<h1>Papers that made the news</h1>\n<p class="jb-q">{escape(QUESTION)}</p>\n'
            f'<p class="intro">{escape(intro)}</p>\n'
            f'{_front(rows)}<section class="jb-answer"><h2>By the numbers</h2>\n{table}\n'
            '<p class="jb-note">Papers in the news: each counted once, under the subject it was put under by hand. '
            'Papers we read: counted by the words in their titles, so one paper can count under several subjects, or '
            'none.</p></section>\n'
            f'{_limits(rows, read)}</div>\n')


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write papers-in-the-news/. Returns its path."""
    rows = papers(cards)
    read_by, read = read_subjects(cards)
    (out / PATH).mkdir(parents=True, exist_ok=True)
    what = (f"{QUESTION} Research papers the news reported on since {_day(SINCE)}, each checked by hand, by subject, "
            "next to the papers we read.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Papers that made the news",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH / "index.html").write_text(
        pages.page("Papers that made the news · AI Pulse", what, PATH, page_body(rows, read_by, read), data,
                   pages.frame(conn, len(cards)), ("/research/", "Back to Research"),
                   "Headlines are the outlets' own, each linking to its story; paper titles link to the paper. New "
                   "papers are added once checked by hand."),
        encoding="utf-8")
    return [PATH]
