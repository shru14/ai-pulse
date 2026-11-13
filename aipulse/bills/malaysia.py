"""Malaysia: bills in the Parliament of Malaysia."""
from __future__ import annotations

import html
import re
from datetime import datetime

from .. import feeds

from .core import AI_TITLE, connect_tables, upsert


# --- Malaysia (Parliament of Malaysia, Dewan Rakyat bills) ---

MY_BILLS = "https://www.parlimen.gov.my/bills-dewan-rakyat.html?uweb=dr&lang=en"


MY_AI = re.compile(AI_TITLE.pattern + r"|kecerdasan buatan", re.I)


_MY_FIELD = r'>{}</td>\s*<td[^>]*>:</td>\s*<td[^>]*>(\d{{2}}/\d{{2}}/\d{{4}})</td>'


def _my_date(chunk: str, label: str) -> str:
    m = re.search(_MY_FIELD.format(label), chunk)
    return datetime.strptime(m.group(1), "%d/%m/%Y").date().isoformat() if m else ""


def sync_malaysia(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI bills in Malaysia's House of Representatives: number, title, readings and a link to the bill.
    (No AI bill has been tabled yet; the AI Governance Bill is in consultation, see the ministry's releases.)"""
    connect_tables(conn)
    page = fetcher(MY_BILLS).decode("utf-8", "replace")
    changed = 0
    for chunk in page.split('<tr class="maintable">')[1:]:
        cells = re.findall(r'<td[^>]*class="maintd"[^>]*>(.*?)</td>', chunk, re.S)
        if len(cells) < 3:
            continue
        number = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cells[0])).strip()
        title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", cells[2]))).strip()
        if not MY_AI.search(title):
            continue
        pdf = re.search(r"loadResult\('([^']+\.pdf)'", chunk)
        status = re.search(r'<div class="parent[^"]*"[^>]*>(.*?)</div>', chunk, re.S)
        history = [h for h in (
            {"date": _my_date(chunk, "First reading"), "stage": "introduced", "text": "First reading"},
            {"date": _my_date(chunk, "Passed At"), "stage": "passed_chamber", "text": "Passed Dewan Rakyat"}) if h["date"]]
        if status and "withdraw" in status.group(1).lower() and history:
            history.append({"date": history[-1]["date"], "stage": "withdrawn", "text": "Withdrawn"})
        if not history:
            continue
        from urllib.parse import quote
        url = "https://www.parlimen.gov.my" + quote(pdf.group(1)) if pdf else MY_BILLS
        changed += upsert(conn, {"key": "MY-" + number.replace("/", "-"), "jurisdiction": "MY", "number": number,
                                 "title": title, "url": url, "source": "Parliament of Malaysia", "history": history})
    conn.commit()
    return changed
