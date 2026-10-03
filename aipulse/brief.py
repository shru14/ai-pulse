"""Short, clean headlines and a one- or two-sentence "what it covers" line, without an LLM.

- clean_title() drops desk labels ("Watch:", "Eurobites:") and trailing site names ("— Cyprus Mail").
- clean_summary() keeps the first informative sentences of the feed text, drops boilerplate
  (author bios, "The post ... appeared first on", newsletter prompts) and anything that only
  repeats the headline. It returns "" when nothing is left, so the page never shows the headline twice.
- draft() fills in a story whose feed has no description: a short line built from what the tracker
  already knows about the story
  (its kind, the places it names, the companies or people tagged), e.g.
  "A proposal in the United Kingdom, involving Google."
"""

from __future__ import annotations

import re

from . import classify, jurisdictions

MAX_CHARS = 240  # about three lines on the page
SHORT_LEDE = 110  # a first sentence shorter than this gets the next one too
_LABEL = re.compile(r"^(watch|video|exclusive|breaking|update[d]?|live|eurobites|podcast|listen|photos?|"
                    r"general|business|world|politics|sports?|technology)\s*[:|\-–—]\s*",  # Bernama: "General : ..."
                    re.I)
_SITE_SUFFIX = re.compile(r"\s+[|\-–—]\s+([^|\-–—]{2,40})$")
_FUNCTION_WORDS = re.compile(r"\b(and|or|but|the|a|to|of|in|on|for|with|as|is|are|was|says?|after|over)\b")

_BOILERPLATE = re.compile(
    r"appeared first on|add yahoo as a preferred source|preferred source|sign up for|subscribe to|"
    r"newsletter|click here|read more|continue reading|listen to this article|advertisement|"
    r"originally (published|appeared)|republished|all rights reserved|getty images|photo:|image:|credit:|"
    r"has a degree in|\bis a (senior |staff |contributing )?(reporter|writer|editor|journalist|correspondent)\b|"
    r"follow us on|share this article|cookies",
    re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“‘(])")
# A period after these (or after a single initial) doesn't end a sentence: "Gov. Tina Kotek", "U.S. Sen."
_ABBREV = re.compile(r"(\b[A-Z]|\b(Gov|Sen|Rep|Rev|Dr|Mr|Mrs|Ms|Prof|Gen|Lt|Col|Sgt|St|Jr|Sr|Inc|Corp|Co|Ltd|"
                     r"No|vs|Jan|Feb|Mar|Apr|Aug|Sept?|Oct|Nov|Dec|Ore|Calif|Mass|Wash|Fla|Ill|Pa|Va|"
                     r"U\.S|U\.K|U\.N|E\.U))\.$")


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for piece in _SENTENCE.split(text):
        if out and _ABBREV.search(out[-1]):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return out
_WORDS = re.compile(r"[a-z0-9]{3,}")


def _words(text: str) -> set[str]:
    return set(_WORDS.findall(text.lower()))


def similarity(a: str, b: str) -> float:
    """Word overlap (Jaccard) between two texts, 0..1."""
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if wa and wb else 0.0


def clean_title(title: str, source: str = "") -> str:
    title = _LABEL.sub("", title.strip())
    m = _SITE_SUFFIX.search(title)
    head = title[: m.start()] if m else ""
    if m and head.count("(") == head.count(")"):  # "(10 – 23 Sep)" is a date range, not a site name
        tail = m.group(1).strip()
        looks_like_site = (tail.lower() == source.lower() or re.search(r"\.\w{2,4}$", tail)
                           or (len(tail.split()) <= 4 and not _FUNCTION_WORDS.search(tail.lower())
                               and all(w[:1].isupper() or w[:1].isdigit() for w in tail.split())))
        if looks_like_site:
            title = title[: m.start()].rstrip()
    return title


def clean_summary(text: str, title: str, source: str = "") -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return ""
    # "<headline> <publisher>": nothing to add.
    if similarity(text, title) > 0.75 or text.lower().startswith(title.lower()[:60]):
        rest = text[len(title):].strip() if text.lower().startswith(title.lower()) else ""
        if source and rest.lower().endswith(source.lower()):
            rest = rest[:-len(source)].strip()
        # What's left is the publisher or a subtitle ("— Measured, Not Claimed"), not a summary.
        if not rest or len(rest.strip(" —–-:|").split()) <= 8:
            return ""
    # The lede: one full sentence says what happened. A second only when the first is very short and both fit.
    out = []
    for s in _sentences(text):
        s = s.strip()
        if not s or _BOILERPLATE.search(s) or similarity(s, title) > 0.7 or len(s.split()) < 4:
            continue
        if out and len(out[0]) + len(s) + 1 > MAX_CHARS:
            break
        out.append(s)
        if len(out) == 2 or len(out[0]) >= SHORT_LEDE:
            break
    summary = " ".join(out)
    if len(summary) > MAX_CHARS:  # one long sentence: end at a clause, not mid-phrase
        cut = summary[:MAX_CHARS]
        end = max(cut.rfind(", "), cut.rfind("; "), cut.rfind(" — "), cut.rfind(" – "))
        summary = (cut[:end] if end > MAX_CHARS * 0.5 else cut.rsplit(" ", 1)[0]).rstrip(",;:—– ") + "…"
    return re.sub(r"\s*(\.\.\.|…)+$", "…", summary)


# Papers: the abstract's own sentence saying what the paper does, not its opening background.
_LATEX = [(re.compile(p), r) for p, r in (
    (r"``|''", '"'), (r"\\(?:emph|textit|textbf|texttt|mathrm|mathbf|mathcal|text)\{([^{}]*)\}", r"\1"),
    (r"\$([^$]{1,40})\$", r"\1"), (r"\$[^$]*\$", ""), (r"\\[a-zA-Z]+", ""), (r"[{}]", ""), (r"(?<!\w)~(?!\w)|(?<=\w)~(?=\w)", " "),
    (r"\s+([,.;:])", r"\1"), (r"\s{2,}", " "))]
_VERBS = ("propose", "introduce", "present", "develop", "study", "show", "investigate", "examine", "analyze",
          "analyse", "argue", "describe", "design", "build", "release", "report", "find", "demonstrate", "explore",
          "offer", "provide", "evaluate", "formalize", "formalise", "survey", "review", "critique", "identify",
          "construct", "establish", "address", "tackle", "characterize", "quantify", "measure", "benchmark", "train",
          "leverage", "extend", "revisit", "consider", "examine", "compare", "outline", "discuss", "assess")
# "We propose X", "In this paper, we introduce X", "To leverage ..., this work introduces X".
_CONTRIBUTION = re.compile(
    r"(?:^|,\s+|^(?:In|Here|Thus|Therefore)\b[^,]*?\s)"
    r"(?:we|this (?:paper|work|study|article|position paper|essay|note|report)|our (?:paper|work|study)|the (?:paper|article))"
    r"\s+(?:(?:first|also|further|then|thus|therefore|here|now|\w+ly)\s+)?(" + "|".join(_VERBS) + r")(?:e?s)?\b\s*(.*)$",
    re.I | re.S)
_THIRD_PERSON = {"study": "Studies", "analyse": "Analyses", "formalise": "Formalises"}


def _as_post(sentence: str) -> str:
    """ "In this paper, we propose X." -> "Proposes X." (other sentences unchanged)"""
    m = _CONTRIBUTION.search(sentence)
    if not m or not m.group(2):
        return sentence
    verb = m.group(1).lower()
    verb = _THIRD_PERSON.get(verb) or (verb[:-1] + "ies" if verb.endswith("y") and verb[-2] not in "aeiou" else
                                       verb + ("es" if verb.endswith(("sh", "ss", "ch", "x")) else "s")).capitalize()
    return f"{verb} {m.group(2)}"


def paper_summary(abstract: str, title: str = "") -> str:
    """What a paper covers, in a sentence or two of its own abstract: the sentence stating its contribution
    ("We propose ...", "This paper introduces ..."), phrased like a post ("Proposes ..."), with LaTeX
    markup removed. Background and questions ("What is an agent?") are skipped; full sentences, no cut-offs."""
    text = re.sub(r"\s+", " ", abstract or "").strip()
    for pattern, repl in _LATEX:
        text = pattern.sub(repl, text)
    sentences = [s.strip() for s in _sentences(text) if len(s.split()) >= 5 and not s.strip().endswith("?")]
    if not sentences:
        return ""
    start = next((i for i, s in enumerate(sentences) if _CONTRIBUTION.search(s)), None)
    picked = [_as_post(sentences[start])] if start is not None else [sentences[0]]
    if start is not None and len(picked[0]) < 140 and start + 1 < len(sentences):
        picked.append(sentences[start + 1])  # a short contribution line: add what follows
    summary = " ".join(picked)
    if len(summary) > 420:  # one long sentence: end at a clause
        cut = summary[:420]
        end = max(cut.rfind("; "), cut.rfind(", "), cut.rfind(" — "))
        summary = (cut[:end] if end > 200 else cut.rsplit(" ", 1)[0]).rstrip(",;: ") + "…"
    return summary


_KIND = {"tool": "A release", "news": "Industry news", "policy": "Policy news", "research": "A paper",
         "infra": "Infrastructure news",
         ("regulation", "proposal"): "A proposal", ("regulation", "law"): "A law adopted",
         ("regulation", "expert"): "Commentary"}
# Tags that name places rather than companies or people.
_PLACE_TAGS = {v[0] for v in jurisdictions.JURISDICTIONS.values()} | {"EU", "US", "UK", "China", "India"}
# Topic and field tags; a draft names only the companies and people involved.
_TOPIC_TAGS = classify.TOPIC_TAGS | {"Law", "Ethics", "Philosophy", "Governance"}


_NEEDS_THE = ("United ", "European ", "Netherlands", "Philippines")


def _the(place: str) -> str:
    """ "the United States", "the European Union", "international bodies" """
    if place == "International bodies":
        return "international bodies"
    return "the " + place if place.startswith(_NEEDS_THE) else place


def is_draft(summary: str) -> bool:
    """True for a line written by draft(); those must never feed back into sorting."""
    return len(summary) < 160 and summary.endswith(".") and summary.startswith(tuple(set(_KIND.values())))


def _join(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def draft(item: dict, place_names: dict[str, str]) -> str:
    """A factual one-liner from the story's category, places and tags; "" if it would say nothing."""
    kind = _KIND.get((item["category"], item.get("action"))) or _KIND.get(item["category"], "A story")
    codes = item.get("jurisdictions") or jurisdictions.detect(item["title"])
    places = [_the(place_names.get(c, c)) for c in codes]
    who = [t for t in item.get("tags") or [] if t not in _PLACE_TAGS and t not in _TOPIC_TAGS]
    if not places and not who:
        return ""
    line = kind
    if places:
        line += (" in " if item["category"] == "regulation" and item.get("action") != "expert" else " about ") + _join(places)
    if who:
        line += (", featuring " if item.get("action") == "expert" else ", involving ") + _join(who[:3])
    return line + "."
