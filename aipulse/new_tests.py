"""New tests for AI (new-tests-for-ai/): each new benchmark in the papers we read, what it tests in one plain line, and
the best result the paper reports, with the model that got it where the paper names one, by Research subject. What
are researchers testing AI on, and how far short do the best models fall?

Every row in TESTS is a Research paper read by hand: a paper counts when its main point is a new test that scores AI
models other than the authors' own. Papers that mainly present a new model, a training method or a tool for building
tests are LEFT_OUT, with why. The plain line and the best result are written from the paper's whole abstract (fetched
from arXiv, not the stored summary) when the row is checked, by Claude as the glossary's words are; the owner approves.
A best result is the abstract's own number and model; a percentage is kept (for the score line) only when the abstract
gives the top score as a percentage or out of 100.

The sample starts on SINCE. Research papers after CHECKED_TO whose title names a benchmark are candidates()
(`python -m aipulse tests`). Linked from Research's strip on the front page.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path

from . import kind_pages, pages, rss

PATH = "new-tests-for-ai/"
SINCE = "2026-07-17"
CHECKED_TO = "2026-10-16"
QUESTION = "What are researchers testing AI on, and how far short do the best models fall?"
# the Research stream's subjects (kind_pages.SUBJECTS), without "Benchmarks and evaluation": every row is one
SUBJECTS = {k: label for k, (label, _, _) in kind_pages.SUBJECTS.items() if k != "benchmarks"}
# a title that may present a benchmark: the Research pages' own rule for Benchmarks, less "evaluat" (too broad)
BENCHY = re.compile(r"bench(?:mark)?(?:s|ing)?\b|leaderboard|\barena\b", re.I)

# By the paper's address as the Research card gives it: (the test's name, its subject, what it tests in one plain line,
#  the best result the abstract reports, the model that got it as the abstract names it ("" when it names none), the top
#  score as a percentage when the abstract gives one (None otherwise))
TESTS: dict[str, tuple[str, str, str, str, str, float | None]] = {
    "https://arxiv.org/abs/2610.21397": (
        "Watts If? (DCBench-440)", "language-models",
        "Whether models can reason about what each early choice in planning an AI data centre (power, cooling, site) "
        "rules out.", "71.5% on its written-answer questions; only open-weight models were tested", "", 71.5),
    "https://arxiv.org/abs/2610.19005": (
        "CyberArena", "safety",
        "AI agents attacking and defending live computer systems against each other, round after round.",
        "No single score: it ranks 12 agents over 466 matches", "", None),
    "https://arxiv.org/abs/2610.19159": (
        "Into the Unknown", "science",
        "Whether AI agents can write a follow-up paper on an open science problem set by national-lab scientists.",
        "None of 135 papers met every condition; 114 failed the honesty check", "", 0.0),
    "https://arxiv.org/abs/2610.18092": (
        "LifeSearch", "agents",
        "Deep-research agents on 203 real everyday and work questions, in Chinese and English.",
        "63.4%", "GPT-5.6 Sol", 63.4),
    "https://arxiv.org/abs/2610.19128": (
        "CLASHarness", "agents",
        "Computer-use agents when other agents feed them out-of-date or clashing information.",
        "Even frontier models fail over 58% of closing steps, such as releasing shared files", "", None),
    "https://arxiv.org/abs/2610.14766": (
        "Last Secure Code Benchmark", "safety",
        "Whether code written by coding agents is secure, not only working, across 7 programming languages.",
        "25.1% of tasks both working and secure", "Claude Fable 5", 25.1),
    "https://arxiv.org/abs/2610.12452": (
        "BrickBench", "agents",
        "Agents designing LEGO sets that can actually be built from real parts.",
        "Falls short of human designs", "", None),
    "https://arxiv.org/abs/2610.12458": (
        "OmniCapBench", "vision",
        "Models describing who and what is seen and heard in 786 videos.",
        "Good on short moments, weak over long stretches", "", None),
    "https://arxiv.org/abs/2610.06748": (
        "BazaarBench", "safety",
        "Whether AI agents trading for people in a simulated online marketplace stay honest.",
        "All 5 models tried to promise one item to several buyers", "", None),
    "https://arxiv.org/abs/2610.00492": (
        "EurekaBench", "science",
        "Agents running long experiments to find the rules behind data in six sciences.",
        "Beat human scientists at prediction, but fell well short on scientific insight", "", None),
    "https://arxiv.org/abs/2610.02202": (
        "ScholarCatalyst", "science",
        "Finding the earlier papers that would help a new research project, as the projects' own authors judged.",
        "Found 51% of the helpful papers in its top 20", "an agent built on Claude Fable 5.1", 51.0),
    "https://arxiv.org/abs/2609.40284": (
        "cua-speedrun", "agents",
        "How fast and cheaply computer-use agents finish tasks, on one standard setup.",
        "No single score; no open-weight model was among the best for speed, cost and results together", "", None),
    "https://arxiv.org/abs/2609.40325": (
        "WorldAuditBench", "vision",
        "Agents searching 3D worlds for errors such as floating objects or walls you can walk through.",
        "42.3%, against 83.4% for people", "", 42.3),
    "https://arxiv.org/abs/2609.37709": (
        "VIF-Bench", "vision",
        "Image generators following picture instructions (arrows, layouts, poses) with up to 7 reference images.",
        "Following instructions more closely came with more flaws in the image", "", None),
    "https://arxiv.org/abs/2609.35025": (
        "AutoDataBench", "agents",
        "Agents writing new training tasks good enough for a real data pipeline.",
        "No agent scored above 20 out of 100 in 45 minutes", "", None),
    "https://arxiv.org/abs/2609.28921v1": (
        "PFArena", "science",
        "Protein models, language models and agents suggesting changes to proteins.",
        "All struggle as the search grows and mutations stack up", "", None),
    "https://arxiv.org/abs/2609.30199": (
        "ExplorationBench", "science",
        "Discovering made-up rules in 'alien worlds' by experimenting, so recalling what a model already knows can't "
        "help.", "The strongest systems learned the new rules, but gains could stall or reverse", "", None),
    "https://arxiv.org/abs/2609.23980v1": (
        "MobileCybench", "safety",
        "Agents finding security holes in 13 Android apps; running it turned up 23 holes nobody had reported.",
        "53.8% of apps, posing as a malicious app without the source code", "OpenCode with GPT-5.6 Sol", 53.8),
    "https://arxiv.org/abs/2609.24308": (
        "HappyWorld-Bench", "robotics",
        "Whether worlds made by world models stay consistent as agents explore and change them.",
        "70.14% placement accuracy, the best of the spatial models", "", 70.14),
    "https://arxiv.org/abs/2609.22069": (
        "OmniVBench", "vision",
        "Making videos from many reference images: people, objects, scenes and styles.",
        "Results vary widely between models and tasks", "", None),
    "https://arxiv.org/abs/2609.20794v1": (
        "PosteriorBench", "science",
        "Whether AI solvers for physics problems find every answer that fits, not only one.",
        "Large gaps across current solvers", "", None),
    "https://arxiv.org/abs/2609.20886": (
        "BI-Bench", "agents",
        "Answering business questions from raw company data, end to end, as people do in Power BI or Tableau.",
        "Frontier models below 50%", "", None),
    "https://arxiv.org/abs/2609.16443v1": (
        "Neverwhere", "robotics",
        "Robot parkour controllers in more than 60 photo-realistic copies of real places.",
        "Controllers trained on few scenes did worse in new ones", "", None),
    "https://arxiv.org/abs/2609.16090v1": (
        "MUUNRiver-Bench", "speech",
        "Finding music by instruction: a cover, the same voice, a new style.",
        "Sound-based and text-based models favour different matches", "", None),
    "https://arxiv.org/abs/2609.14992v1": (
        "MTAC-IFBench", "agents",
        "Coding agents following instructions over long sessions: about 7 turns and 91 rules each.",
        "Agents get worse the longer the session runs", "", None),
    "https://arxiv.org/abs/2609.10226": (
        "Φ-Bench", "agents",
        "Models doing real engineering on the code that trains and runs language models.",
        "36.53%", "Claude Opus 5", 36.53),
    "https://arxiv.org/abs/2609.05141v1": (
        "SciDocBench", "science",
        "Reading scientific papers: finding evidence in text, figures, tables and equations.",
        "62.6 out of 100", "Claude Opus 5", 62.6),
    "https://arxiv.org/abs/2609.05405": (
        "WearableQA", "science",
        "Health questions about 200 real people's fitness-tracker data and blood tests.",
        "72.9%, where guessing gets 10%", "", 72.9),
    "https://arxiv.org/abs/2609.04280v2": (
        "EvoHarnessBench", "agents",
        "Whether agents keep their skills as the tools, skills and helper agents around them change.",
        "Adding tools can make agents fail tasks they used to solve", "", None),
    "https://arxiv.org/abs/2609.00646": (
        "DramaChain Bench", "vision",
        "Every step of making short dramas, from the script to finished episodes.",
        "Flaws early on carry through to the final episode", "", None),
    "https://arxiv.org/abs/2608.30730": (
        "E-Commerce Bench", "agents",
        "Agents running online stores for a simulated year: buying stock, pricing, selling and handling returns.",
        "Grew 100,000 into 1,431,425, but came 16th of 18 at avoiding fraud", "GPT-5.6 Sol", None),
    "https://arxiv.org/abs/2608.29834v1": (
        "RepoRef", "agents",
        "Agents working out what a remark like 'the fix discussed yesterday' points to in developer chats.",
        "67.0% resolved", "", 67.0),
    "https://arxiv.org/abs/2608.23475v1": (
        "StrategyBench", "language-models",
        "Whether models can write down the rule behind a few examples, then use it.",
        "How much it helps depends a lot on the kind of task", "", None),
    "https://arxiv.org/abs/2608.23035": (
        "MobilePA-Bench", "agents",
        "Phone-assistant agents planning tasks and using 212 app tools.",
        "Scores drop sharply under strict tool order, permission limits or errors", "", None),
    "https://arxiv.org/abs/2608.21833": (
        "GameXpert-Bench", "agents",
        "Coding agents building, fixing and improving games.",
        "Better at making playable games than at finding their bugs", "", None),
    "https://arxiv.org/abs/2608.19741": (
        "Thinkingbox-bench", "agents",
        "Agents doing business workflows (retail, insurance, IT help) correctly every time, not just once.",
        "66.50% on the first try, 47.53% on all of 20 tries", "Claude Opus 5", 66.5),
    "https://arxiv.org/abs/2608.17800": (
        "StartupBench", "agents",
        "Agents doing the work that real AI startup products are used for.",
        "About 30% of tasks completed", "", 30.0),
    "https://arxiv.org/abs/2608.16344v4": (
        "IndicQE-APE", "language-models",
        "Judging and fixing machine translation between English and Indian languages.",
        "The unedited translation beat every fixing system on 3 of 4 language pairs", "", None),
    "https://arxiv.org/abs/2608.12781": (
        "PatternEval", "vision",
        "Answers to questions about images: leaked reasoning, repetition, contradictions.",
        "These failures are common, more so with thinking turned off", "", None),
    "https://arxiv.org/abs/2608.14546": (
        "CPI-Bench", "vision",
        "Image-editing models on real tasks: several images at once and instructions that need reasoning.",
        "Its ranking of models is the closest to people's own votes", "", None),
    "https://arxiv.org/abs/2608.12593v1": (
        "DiG-bench", "agents",
        "Discovering the hidden rules of 70 games by playing them.",
        "The hardest games still challenge the best models; people solved every game on their first try", "", None),
    "https://arxiv.org/abs/2608.10916v1": (
        "FaithformBench", "language-models",
        "Whether tools that turn maths reasoning into formal proofs keep wrong steps wrong.",
        "Many 'silently correct' wrong steps into provable ones", "", None),
    "https://arxiv.org/abs/2608.09802": (
        "SWE-Bench ProMax", "agents",
        "Coding agents making large changes across many files, in 7 programming languages.",
        "41.2% solved", "", 41.2),
    "https://arxiv.org/abs/2608.08621": (
        "Business Arena", "agents",
        "Agents running a cross-border shop: buying from suppliers and selling to buyers.",
        "Even the best model fell behind strategies designed by people", "", None),
    "https://arxiv.org/abs/2608.07004v1": (
        "CoDyControlBench", "science",
        "Models designing controllers for machines with many moving parts.",
        "94.8% of designs worked", "GPT (version not named)", 94.8),
    "https://arxiv.org/abs/2608.05747": (
        "GST-Bench", "vision",
        "Whether models can map a whole space from a long video.",
        "42.68, against 79.08 for people", "", 42.68),
    "https://arxiv.org/abs/2608.05139v1": (
        "Skill²-Bench", "language-models",
        "Long tasks that switch between different reasoning skills, such as maths then planning.",
        "Accuracy falls as the switches get harder", "", None),
    "https://arxiv.org/abs/2608.03569v1": (
        "Formula 1 and Magic: The Gathering", "science",
        "AI 'scientists' coming up with real new ideas: 2026 Formula 1 car designs and Magic: The Gathering decks.",
        "Matched 10 of 40 real Formula 1 innovations", "GPT-5.2", None),
    "https://arxiv.org/abs/2607.28956": (
        "MerchantBench", "agents",
        "Agents running an online shop for a simulated year, order by order.",
        "Ended with 27.3% of the money people did", "", None),
    "https://arxiv.org/abs/2607.26791": (
        "SecRespond", "safety",
        "Agents investigating a hacked computer and planning the clean-up.",
        "No model fully found and fixed any of the 10 hacked machines", "", None),
    "https://arxiv.org/abs/2607.25151v1": (
        "HiEviDR-Bench", "agents",
        "Whether deep-research answers are built on the right evidence.",
        "Reports read well, but citations and claims are weak", "", None),
    "https://arxiv.org/abs/2607.24957": (
        "PerceptionBench", "vision",
        "Basic seeing, one skill per question, in 3,000 questions.",
        "No model reaches 60%", "", None),
    "https://arxiv.org/abs/2607.23808v1": (
        "Indic DiarBench", "speech",
        "Who spoke when, and what they said, in all 22 scheduled languages of India.",
        "A first baseline for commercial speech systems; no score in the abstract", "", None),
    "https://arxiv.org/abs/2607.20911": (
        "Tencent WorkBuddy Bench", "agents",
        "Coding agents on real work: code, websites, office tasks and security.",
        "No overall score, by design: each part is scored differently", "", None),
    "https://arxiv.org/abs/2607.19322": (
        "GAMUT", "vision",
        "Whether long answers about photos from wearable cameras include every fact they should.",
        "58.7%", "Gemini 3.1 Pro", 58.7),
}
# papers checked by hand and left out, with why, so they aren't checked again
LEFT_OUT: dict[str, str] = {
    "https://arxiv.org/abs/2610.13644": "SelectArena compares statistics methods for picking data columns, not AI models",
    "https://arxiv.org/abs/2610.13947": "mainly a new 3D-generation system (Artisan)",
    "https://arxiv.org/abs/2610.10619": "TestJack is a way to check other tests' results",
    "https://arxiv.org/abs/2610.05140": "AutoSciBench is a tool that builds tests",
    "https://arxiv.org/abs/2609.33295": "TraceDance is a tool that builds tests",
    "https://arxiv.org/abs/2609.21465": "mainly a data engine and training method (OmniVChat)",
    "https://arxiv.org/abs/2608.29481v1": "tests the authors' own simulators (SIC-Agents)",
    "https://arxiv.org/abs/2608.05850v2": "mainly a new model (MameLoshnLM)",
}
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def tests(cards: list[dict]) -> list[dict]:
    """The rows in TESTS whose paper we have, newest first, each with its paper (title, date, url)."""
    by_url = {c["url"]: c for c in cards}
    out = [{"url": url, "name": n, "subject": s, "tests": t, "best": b, "model": m, "pct": p,
            "paper": by_url[url]["title"].strip(), "date": by_url[url]["date"][:10]}
           for url, (n, s, t, b, m, p) in TESTS.items() if url in by_url]
    return sorted(out, key=lambda r: r["date"], reverse=True)


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Research papers after CHECKED_TO (or `since`) whose title names a benchmark and that are neither in TESTS nor
    LEFT_OUT, newest first."""
    after = max(since, CHECKED_TO)
    return [c for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["category"] == "research" and c["date"][:10] > after and BENCHY.search(c["title"])
            and c["url"] not in TESTS and c["url"] not in LEFT_OUT]


def _day(d: str) -> str:
    day = date.fromisoformat(d[:10])
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' * (n != 1)}"


def _num(p: float) -> str:
    return f"{p:g}"


def _glance(rows: list[dict]) -> str:
    """Three big numbers, each saying what it counts."""
    scored = [r for r in rows if r["pct"] is not None]
    under = sum(r["pct"] < 50 for r in scored)
    top, top_n = Counter(r["subject"] for r in rows).most_common(1)[0]
    tiles = [(len(rows), f"new tests for AI in papers since {_day(SINCE)}", "#CC79A7"),
             (f"{under} of {len(scored)}", "tests that give a top score as a percentage, where the best model scored "
              "under half", "#E69F00"),
             (top_n, f"of them test {SUBJECTS[top].lower()}, the most of any subject", "#56B4E9")]
    body = "".join(f'<div class="iw-big" style="--c:{c}"><b>{n}</b><span>{escape(label)}</span></div>'
                   for n, label, c in tiles)
    return f'<section class="iw-glance"><h2>At a glance</h2>\n<div class="iw-bigs">{body}</div></section>\n'


def _scores(rows: list[dict]) -> str:
    """Each test that gives its top score as a percentage, lowest first: the score as a dot on a line from 0 to 100."""
    scored = sorted((r for r in rows if r["pct"] is not None), key=lambda r: (r["pct"], r["name"]))
    if not scored:
        return ""
    lines = "".join(
        f'<li><a href="{escape(r["url"])}" rel="noopener">{escape(r["name"])}</a>'
        f'<span class="nt-track" aria-hidden="true"><i style="left:{r["pct"]:.2f}%"></i></span>'
        f'<span class="nt-pct"><b>{_num(r["pct"])}</b>{" · " + escape(r["model"]) if r["model"] else ""}</span></li>'
        for r in scored)
    return ('<section><h2>The best score on each test</h2>\n<p class="nt-how">0 means nothing done right, 100 means '
            'every task done right. Each dot is the best score the paper reports; the model is named where the paper '
            f'names it.</p>\n<ol class="nt-scores">{lines}</ol></section>\n')


def _table(rows: list[dict]) -> str:
    """Every test, by subject (the most tests first), newest first within each."""
    groups = {k: [r for r in rows if r["subject"] == k] for k in SUBJECTS}
    out = []
    for k in sorted((k for k in groups if groups[k]), key=lambda k: -len(groups[k])):
        body = "".join(
            f'<tr><td><a href="{escape(r["url"])}" rel="noopener" title="{escape(r["paper"])}">{escape(r["name"])}</a>'
            f'</td><td>{escape(r["tests"])}</td><td>{escape(r["best"])}'
            + (f'<small>{escape(r["model"])}</small>' if r["model"] else "")
            + f'</td><td>{_day(r["date"])}</td></tr>' for r in groups[k])
        out.append(f'<h3>{escape(SUBJECTS[k])} <span class="nt-n">{_plural(len(groups[k]), "test")}</span></h3>\n'
                   '<table class="mt nt-table"><thead><tr><th>Test</th><th>What it tests</th>'
                   f'<th>Best result reported</th><th>Paper</th></tr></thead><tbody>{body}</tbody></table>\n')
    return f'<section><h2>Every test, by subject</h2>\n{"".join(out)}</section>\n'


def _limits(rows: list[dict]) -> str:
    """About these counts, as a small table: what each count is made of."""
    notes = [
        ("New tests", f"Papers from arXiv's AI sections and Hugging Face's daily list since {_day(SINCE)} whose title "
         "names a benchmark, each read by hand. A paper counts when its main point is a new test that scores AI "
         "models other than the authors' own."),
        ("Left out", f"{_plural(len(LEFT_OUT), 'paper')} that mainly present a new model, a training method or a tool "
         "for building tests."),
        ("Best result", "The paper's own words and numbers, from its whole abstract. Each test is scored its own way, "
         "so a score is only comparable with others on the same test."),
        ("Subjects", "Set by hand, one per test, from the Research stream's subjects."),
    ]
    body = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in notes)
    return f'<section><h2>About these counts</h2>\n<table class="mt pn-notes"><tbody>{body}</tbody></table></section>\n'


def page_body(rows: list[dict]) -> str:
    intro = (f"{_plural(len(rows), 'new test')} for AI in the research papers we read since {_day(SINCE)}, each read "
             "by hand: what it tests in one plain line, and the best result its paper reports, with the model that got "
             "it where the paper names one. New tests are added once checked.")
    return ('<div class="ft jb nt">\n' + pages.feature_head(PATH, "New tests for AI", QUESTION, escape(intro))
            + _glance(rows) + _scores(rows) + _table(rows) + _limits(rows) + '</div>\n')


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write new-tests-for-ai/. Returns its path, or nothing when no checked paper is among the cards."""
    rows = tests(cards)
    if not rows:
        return []
    (out / PATH).mkdir(parents=True, exist_ok=True)
    what = (f"{QUESTION} New benchmarks in the AI research papers we read since {_day(SINCE)}, each checked by hand: "
            "what it tests and the best result its paper reports.")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": "New tests for AI",
            "description": what, "url": f"{rss.SITE}{PATH}"}
    (out / PATH / "index.html").write_text(
        pages.page("New tests for AI · AI Pulse", what, PATH, page_body(rows), data, pages.frame(conn, len(cards)),
                   ("/research/", "Back to Research"),
                   "Test names link to their paper. New tests are added once checked by hand."),
        encoding="utf-8")
    return [PATH]


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a tests/<day> branch: each test it adds and the papers it left out; None when it
    adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("TESTS", "LEFT_OUT"))
    rows = [(n, SUBJECTS.get(s, s), t, f"{b} ({m})" if m else b, u)
            for u, (n, s, t, b, m, _) in TESTS.items() if u not in had["TESTS"]]
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("New tests for AI", f"test{'s' * (len(rows) != 1)}", branch,
                        ("Test", "Subject", "What it tests", "Best result", "Paper"), rows, dropped)
