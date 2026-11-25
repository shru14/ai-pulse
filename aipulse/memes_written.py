"""Memes written by the evening memes draft job (a local Claude routine), one a day, approved by the owner.

The job reads the day's light stories (`python -m aipulse meme-stories`), writes one meme on a known template and adds
it to WRITTEN on a memes/<day> branch; the push emails the project inbox, and nothing is used until the owner merges
it. A written meme goes ahead of Gemini's and the rule-based ones, after the same checks (memegen.check: a known
template, short lines, no harm, politics or promotion, every number and headline from that period's stories). One
that fails a check is skipped as if it weren't there.

Keys: "day:<YYYY-MM-DD>" for a day's email, "week:<Monday>" for the meme of the week (Monday to Saturday: Sunday's
email and the site's tile). On a Saturday the job writes the week's meme, as Saturday's email has no meme of the day.
"""

from __future__ import annotations

import ast
import re
from datetime import date, timedelta
from html import escape

# One meme a key: the template's fields as memes.py keeps them, and "based_on": the headlines it jokes about, word for word.
WRITTEN: dict[str, dict] = {
    "day:2026-11-25": {
        "format": "panik",
        "rows": [
            ["Panik", "Codex is down"],
            ["Kalm", "Fine, I'll write it myself"],
            ["Panik", "Wait, how does our repo work?"],
        ],
        "based_on": ["ChatGPT and Codex failures reach OpenAI services this Wednesday"],
    },
    "day:2026-11-24": {
        "format": "pigeon",
        "labels": ["The mailer", "A data center"],
        "caption": "Is this a research computing center?",
        "based_on": ["University of Michigan Mailer Promises Its Data Center Isn’t Really a Data Center"],
    },
    "day:2026-11-23": {
        "format": "pooh",
        "labels": ["Running 28 layers twice", "Loop architecture"],
        "based_on": ["Z.ai follows OpenAI into loop transformer territory with its new 750B flagship model"],
    },
}


def period(cards: list[dict], kind: str, when: date) -> list[dict]:
    """The stories a meme may use: that day's, or Monday to Saturday's for a week."""
    if kind == "week":
        upto = (when + timedelta(days=6)).isoformat()
        return [c for c in cards if when.isoformat() <= (c.get("date") or "") < upto]
    return [c for c in cards if c.get("date") == when.isoformat()]


def stories(cards: list[dict], kind: str, when: date) -> list[dict]:
    """The period's stories a joke may touch (memes.light), the most-covered first."""
    from . import memes
    return sorted([c for c in period(cards, kind, when) if memes.light(c)], key=lambda c: -len(c.get("also") or []))


def checked(meme: dict, cards: list[dict], kind: str, when: date) -> dict | None:
    """The written meme in memes.py's shape if it passes every check, else None."""
    from . import memegen, memes
    light = stories(cards, kind, when)
    index = {c["title"]: i for i, c in enumerate(light)}
    based = meme.get("based_on") or []
    if not based or any(t not in index for t in based):  # every headline is one of the period's light stories
        return None
    ok = memegen.check({**meme, "based_on": [index[t] for t in based]}, light)
    return ok and not memes.plugs(ok) and {**ok, "by": "written"} or None


def get(cards: list[dict], kind: str, when: date) -> dict | None:
    """The approved written meme for the day or week (its Monday), checked; None if there's none or it fails."""
    meme = WRITTEN.get(f"{kind}:{when.isoformat()}")
    return checked(meme, cards, kind, when) if meme else None


def recent_templates(day: date, days: int = 6) -> list[str]:
    """The templates of the days before: the written meme's, else the day's turn in memes.ROTATION (what Gemini and
    the rules use), so the job picks another."""
    from . import memes
    out = []
    for d in (day - timedelta(days=k) for k in range(days, 0, -1)):
        m = WRITTEN.get(f"day:{d.isoformat()}") or WRITTEN.get(f"week:{(d - timedelta(days=5)).isoformat()}")
        out.append(m["format"] if m and m.get("format") else memes.template_of(d))
    return list(dict.fromkeys(out))


def brief(cards: list[dict], kind: str, when: date, recent: list[str]) -> str:
    """What the job reads before writing: the stories, numbered, and the templates with their fields."""
    from . import memegen
    rows = stories(cards, kind, when)[:40]
    lines = [f"{'Week from ' if kind == 'week' else 'Day '}{when.isoformat()}: {len(rows)} stories a meme may use "
             "(most-covered first; copy a headline exactly into based_on)", ""]
    lines += [f"{i}. {c['title']}  ({c.get('source') or ''}; {1 + len(c.get('also') or [])} outlets)\n   "
              f"{(c.get('summary') or '')[:220]}" for i, c in enumerate(rows)]
    lines += ["", "Templates (key: what it shows; fields):"]
    lines += [f'- "{k}": {d} Fields: ' + "; ".join(f"{f}: {h}" for f, h in fields.items())
              for k, (d, fields) in memegen.TEMPLATES.items()]
    lines += ["", f"Shown in the last 6 days (pick another): {', '.join(recent) or 'none'}"]
    return "\n".join(lines)


def _entries(source: str) -> dict:
    """WRITTEN as a file's text holds it (main's copy, for the note)."""
    body = re.search(r"^WRITTEN: dict\[str, dict\] = (\{.*?^\})", source, re.M | re.S)
    try:
        return ast.literal_eval(body.group(1)) if body else {}
    except (ValueError, SyntaxError):
        return {}


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for a memes/<day> branch: the meme it adds, caption by caption; None if none."""
    from .glossary import REPO
    from . import memes
    had = _entries(base)
    rows = [(k.replace(":", " of "), m.get("format", ""),
             ([f"Above: {m['who']}"] if m.get("who") else []) + memes.captions(m), m.get("based_on") or [])
            for k, m in WRITTEN.items() if k not in had and m.get("format") in memes.TEMPLATES]
    if not rows:
        return None
    subject = f"Pulse Central, Meme: {len(rows)} new meme{'s' * (len(rows) != 1)} to approve"
    lead = f"Drafted today on the branch {branch}, not in any email yet:"
    tail = f"To use it, tell Claude: merge {branch}. To change it, say what. Changes: {REPO}/compare/main...{branch}"
    text = [lead, ""]
    for when, fmt, caps, heads in rows:
        text += [f"{when} ({fmt})", *(f"  {i}. {c}" for i, c in enumerate(caps, 1)), "  From: " + "; ".join(heads), ""]
    text.append(tail)
    p = 'style="margin:4px 0;font-size:14px"'
    body = "".join(f'<div style="border:1px solid #e3e5e8;border-radius:8px;padding:12px 14px;margin:0 0 12px">'
                   f'<p style="margin:0 0 6px;font-size:13px;color:#5f6368">{escape(when)} · {escape(fmt)}</p>'
                   + "".join(f"<p {p}>{i}. {escape(c)}</p>" for i, c in enumerate(caps, 1))
                   + f'<p style="margin:8px 0 0;font-size:13px;color:#5f6368">From: {escape("; ".join(heads))}</p></div>'
                   for when, fmt, caps, heads in rows)
    html = ('<!doctype html><html><body style="margin:0;padding:16px;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a">'
            f'<div style="max-width:640px"><p style="font-size:15px">{escape(lead)}</p>{body}'
            f'<p style="font-size:13px;color:#5f6368">To use it, tell Claude: merge {escape(branch)}. To change it, say what. '
            f'<a href="{REPO}/compare/main...{escape(branch)}" style="color:#1a4fd6">See the changes</a></p></div></body></html>')
    return subject, "\n".join(text), html
