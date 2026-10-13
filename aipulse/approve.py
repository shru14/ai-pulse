"""The project inbox's note for a daily drafts branch (court/<day>, press/<day>): a table of what the branch adds, the
stories it left out, and how to publish them. Nothing goes on the site until the branch is merged (only with the
owner's yes). The job cuts' and the glossary's notes are written in their own modules; this is the same email.
"""
from __future__ import annotations

import ast
from html import escape


def lists_in(source: str, names: tuple[str, ...]) -> dict[str, set[str]]:
    """Every URL in each named list or dict of another copy of a module (main's, to tell what a branch adds)."""
    found = {n: set() for n in names}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            for t in (node.targets if isinstance(node, ast.Assign) else [node.target]):
                if isinstance(t, ast.Name) and t.id in found:
                    found[t.id] = {n.value for n in ast.walk(node.value)
                                   if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.startswith("http")}
    return found


def note(page: str, what: str, branch: str, head: tuple[str, ...], rows: list[tuple[str, ...]],
         dropped: list[str]) -> tuple[str, str, str]:
    """(subject, text, html) of the note: `rows` are the branch's new entries, each a tuple of cells under `head`, its
    last cell the story's URL."""
    from .glossary import REPO
    n = len(rows)
    subject = f"AI Pulse, {page}: {n} new {what} to approve"
    lead = f"Drafted today on the branch {branch}, not on the site yet:"
    tail = f"To publish them, tell Claude: merge {branch}. To change one, say which. Changes: {REPO}/compare/main...{branch}"
    left = f"Also checked and left out: {len(dropped)} stor{'ies' if len(dropped) != 1 else 'y'}." if dropped else ""
    text = [lead, ""] + ["\n  ".join(r) + "\n" for r in rows] + ([left, ""] if left else []) + [tail]
    cell = 'style="padding:8px 10px;border-bottom:1px solid #e3e5e8;vertical-align:top;font-size:14px"'
    body = "".join("<tr>" + "".join(f"<td {cell}>{escape(c)}</td>" for c in r[:-1])
                   + f'<td {cell}><a href="{escape(r[-1])}" style="color:#1a4fd6">Story</a></td></tr>' for r in rows)
    html = ('<!doctype html><html><body style="margin:0;padding:16px;font-family:Arial,Helvetica,sans-serif;color:#1a1a1a">'
            f'<p style="font-size:15px">{escape(lead)}</p>'
            '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;width:100%;max-width:820px"><tr>'
            + "".join(f'<th align="left" {cell}>{escape(h)}</th>' for h in head) + f'</tr>{body}</table>'
            + (f'<p style="font-size:14px">{escape(left)}</p>' if left else "")
            + f'<p style="font-size:13px;color:#5f6368">To publish them, tell Claude: merge {escape(branch)}. To change one, '
            f'say which. <a href="{REPO}/compare/main...{escape(branch)}" style="color:#1a4fd6">See the changes</a></p>'
            '</body></html>')
    return subject, "\n".join(text), html
