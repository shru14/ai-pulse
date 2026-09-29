"""Subscribers to the daily email. The site's sign-up form posts to a Google Apps Script web app in the project's
Google account (apps-script/Code.gs): it keeps the list there, emails each new reader a confirm link (double
opt-in: nobody gets the digest without clicking it) and handles each reader's unsubscribe link.
Nothing about readers is stored in this repository (it's public), and no address is ever printed (the Actions
logs are public too): only counts.

The daily send reads the confirmed readers from the web app with a secret key (DIGEST_LIST_KEY, the web app's
LIST_KEY property).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from . import rss

# The web app's address (public: the site's form posts to it).
SIGNUP_URL = "https://script.google.com/macros/s/AKfycbwJKOw8YErRzs9Oq0iUXU-2y4uqICixcHzvS6xkiFiHV7UCMm-1K20uJ4TEgfchyRR3RA/exec"
ADDRESS = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
TOKEN = re.compile(r"^[0-9a-f-]{36}$")


def fill(page: str) -> str:
    """The page with the sign-up form's address in it (until the web app is deployed the form says it opens soon)."""
    return page.replace("__SIGNUP_URL__", SIGNUP_URL) if SIGNUP_URL else page


LIMITS = {"more": 10, "less": 40, "words": 5}


def prefs_of(r: dict) -> dict[str, list[str]]:
    """A reader's choices ("Make it yours" on the site): labels they want more of or left out, and words of their
    own; capped and trimmed again here, whatever the web app sends."""
    def clean(values, n):
        out = []
        for v in values if isinstance(values, list) else []:
            v = re.sub(r"\s+", " ", str(v)).strip()
            if 1 < len(v) <= 60 and v not in out:
                out.append(v)
        return out[:n]
    prefs = {k: clean(r.get(k), n) for k, n in LIMITS.items()}
    prefs["more"] = [t for t in prefs["more"] if t not in prefs["less"]]
    return prefs


def choices_link(unsubscribe_link: str) -> str:
    """The reader's "Change my choices" link: the same private token as their unsubscribe link."""
    return unsubscribe_link.replace("#unsubscribe=", "#choices=")


def readers(data: dict) -> dict[str, tuple[list[str], str, str, dict[str, list[str]]]]:
    """{address: (streams, one-click unsubscribe address, unsubscribe link, choices)} from the web app's list,
    keeping only well-formed entries. The one-click address (the web app) goes only in the List-Unsubscribe
    header, for mail apps' Unsubscribe button; the link in the email goes to the site, since a script.google.com
    link in an email looks like phishing to spam filters. A reader who chose nothing has empty choices."""
    if not data.get("ok"):
        raise RuntimeError("the sign-up web app refused the list (check DIGEST_LIST_KEY)")
    base = str(data.get("unsubscribe") or "")
    out = {}
    for r in data.get("subscribers") or []:
        email, token = str(r.get("email") or "").lower(), str(r.get("token") or "")
        streams = [n for n in rss.FEEDS if n in (r.get("streams") or [])]
        if ADDRESS.match(email) and TOKEN.match(token) and streams and base.startswith("https://"):
            out[email] = (streams, base + token, f"{rss.SITE}#unsubscribe={token}", prefs_of(r))
    return out


def current(key: str, url: str = "") -> dict[str, tuple[list[str], str, str, dict[str, list[str]]]]:
    """The confirmed readers, each with their streams, own unsubscribe addresses and choices (see readers)."""
    url = url or SIGNUP_URL
    if not (url and key):
        raise RuntimeError("the sign-up web app's address and DIGEST_LIST_KEY must be set")
    query = urllib.parse.urlencode({"action": "list", "key": key})
    with urllib.request.urlopen(f"{url}?{query}", timeout=60) as r:  # follows Google's redirect to the answer
        return readers(json.loads(r.read().decode("utf-8")))
