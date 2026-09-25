"""Optional: ask Claude to write the summary and pick the category.

Enabled only when ANTHROPIC_API_KEY is set. Uses the Messages API over plain
HTTPS (no SDK needed). Any failure falls back to the keyword classifier.
"""

from __future__ import annotations

import json
import os
import urllib.request

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("AIPULSE_MODEL", "claude-haiku-4-5-20251001")

PROMPT = """You are editing an AI news feed. For the story below, return JSON only:
{{"relevant": true|false, "category": "tool"|"news"|"policy"|"research"|"regulation", "summary": "...", "tags": ["..."],
 "jurisdictions": ["..."], "action": "enforcement"|"investigation"|"law"|"proposal"|"guidance"|null}}

- relevant: is this genuinely about AI (models, products, companies, research, regulation)?
- category: "tool" = a model/product/feature/open-source release; "policy" = regulation, legislation,
  government action, geopolitics, lawsuits; "research" = a research paper, technical report or lab/university
  research write-up; "regulation" = a concrete regulatory action on AI by a government or regulator
  (a fine or order, an investigation, a law passed or taking effect, a bill or draft rules, official guidance);
  "news" = everything else (funding, deals, incidents).
- jurisdictions (regulation only): ISO 3166-1 alpha-2 codes of the governments acting, "EU" for EU bodies,
  "INTL" for the UN, OECD, G7 and similar. Empty list otherwise.
- action (regulation only): the kind of action, else null.
- summary: 1-2 neutral sentences on what the story covers, with concrete facts. No hype. Max 45 words.
- tags: 1-4 short tags (company names or topics).

Title: {title}
Source: {source}
Feed text: {summary}
"""


def enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def enrich(title: str, summary: str, source: str) -> dict | None:
    if not enabled():
        return None
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 300,
        "messages": [{"role": "user", "content": PROMPT.format(title=title, source=source, summary=summary[:1500])}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, method="POST", headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        text = "".join(b.get("text", "") for b in data.get("content", []))
        start, end = text.find("{"), text.rfind("}")
        out = json.loads(text[start : end + 1])
        if out.get("category") not in {"tool", "news", "policy", "research", "regulation"}:
            return None
        return out
    except Exception:
        return None
