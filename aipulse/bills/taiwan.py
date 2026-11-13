"""Taiwan: laws from the Legislative Yuan law system."""
from __future__ import annotations

import html
import re
import time

from .. import feeds, translate

from .core import DATA_LAWS, connect_tables, retitle, upsert


# --- Taiwan (Legislative Yuan law system, lis.ly.gov.tw) ---

TW_LAWS = "https://lis.ly.gov.tw/lglawc/lglawkm"


TW_SEARCHES = ("人工智慧", "個人資料保護法")  # "artificial intelligence" in law names; the Personal Data Protection Act


# The system's result links last one session, so a card links to the law's name on the national law database
# (a link for readers; that site's robots.txt closes it to automated reading, so it's never fetched).
TW_LINK = "https://law.moj.gov.tw/Law/LawSearchResult.aspx?ty=ONEBAR&kw="


_TW_ROW = re.compile(r"<tr[^>]*>((?:(?!</tr>).)*?\b(\d{7})\b(?:(?!</tr>).)*?\b(\d{7})\b(?:(?!</tr>).)*)</tr>", re.S)


def _roc(day: str) -> str:
    """Taiwan's calendar: "1141223" is 2025-12-23 (year 114 + 1911)."""
    return f"{int(day[:3]) + 1911:04d}-{day[3:5]}-{day[5:7]}"


def tw_laws(page: str) -> list[tuple[str, str, str]]:
    """(law name, passed, promulgated) for each law in a result page."""
    out = []
    for row, passed, promulgated in _TW_ROW.findall(page):
        cells = [re.sub(r"\s+", "", html.unescape(re.sub(r"<[^>]+>", "", c)))
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        name = next((c for c in cells if re.search(r"[\u4e00-\u9fff]{2,}(法|條例|通則|規程|辦法)$", c)), "")
        if name:
            out.append((name, _roc(passed), _roc(promulgated)))
    return out


def sync_taiwan(conn, fetcher=None, log=print, opener=None) -> int:
    """Taiwan's laws with AI in their name, from the Legislative Yuan's law system: passage and promulgation.
    The system is a search form (robots.txt sets no rules); one search per term, then nothing else."""
    connect_tables(conn)
    import http.cookiejar
    import urllib.parse
    import urllib.request
    if not feeds.allowed(TW_LAWS):
        raise feeds.Disallowed(TW_LAWS)
    if opener is None:
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=feeds.TLS),
                                             urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        opener.addheaders = [("User-Agent", feeds.USER_AGENT)]
    found = {}
    for term in TW_SEARCHES:
        form = opener.open(TW_LAWS, timeout=30).read().decode("utf-8", "replace")
        action = re.search(r'<form[^>]*action="([^"]+)"', form).group(1)
        fields = dict(re.findall(r"<input type=hidden name=([^ >]+) value=[\"']?([^\"'>]*)", form))
        fields.update({"_1_6_T": term, "_IMG_檢索.x": "10", "_IMG_檢索.y": "10"})
        page = opener.open("https://lis.ly.gov.tw" + action, data=urllib.parse.urlencode(fields).encode(),
                           timeout=30).read().decode("utf-8", "replace")
        for name, passed, promulgated in tw_laws(page):
            if "人工智慧" in name or DATA_LAWS["TW"].search(name):
                found[name] = (passed, promulgated)
        time.sleep(1)
    from urllib.parse import quote
    translate.english(conn, "zh", list(found))
    changed = 0
    for name, (passed, promulgated) in found.items():
        changed += upsert(conn, {"key": "TW-" + name, "jurisdiction": "TW", "number": "", "title": name,
                                 "url": TW_LINK + quote(name), "source": "Legislative Yuan (Taiwan)", "lang": "zh",
                                 "history": [{"date": passed, "stage": "passed_legislature", "text": "三讀通過"},
                                             {"date": promulgated, "stage": "signed", "text": "公布"}]})
    conn.commit()
    retitle(conn, "TW", "zh")
    return changed
