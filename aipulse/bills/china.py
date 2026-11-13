"""China: regulations from the Cyberspace Administration of China's own lists."""
from __future__ import annotations

import re
import time

from .. import feeds, translate

from .core import DATA_LAWS, connect_tables, retitle, upsert


# --- China (Cyberspace Administration of China) ---

CN_SITE = "https://www.cac.gov.cn"


# Laws, administrative regulations, departmental rules, normative documents and policy documents (the
# section's interpretations and judicial interpretations aren't regulations of their own).
CN_LISTS = ("fl/A09370301", "xzfg/A09370302", "bmgz/A09370303", "gfxwj/A09370305", "zcwj/A09370306")


CN_AI = re.compile(r"人工智能|生成式|深度合成|算法|大模型|智能体|合成内容|机器学习|\bAI\b")


_CN_ITEM = re.compile(r'<a href=([^ >]+) target=_blank title="([^"]+)">.*?<div class="times">(\d{4}-\d{2}-\d{2})</div>', re.S)


def sync_china(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI regulations the CAC lists, as title (in English), date and link."""
    connect_tables(conn)
    found = {}
    for path in CN_LISTS:
        page = fetcher(f"{CN_SITE}/wxzw/zcfg/{path}index_1.htm").decode("utf-8", "replace")
        for href, title, day in _CN_ITEM.findall(page):
            if CN_AI.search(title) or DATA_LAWS["CN"].search(title):
                url = "https:" + href if href.startswith("//") else href
                found[url] = (title.strip(), day)
        time.sleep(1)
    translate.english(conn, "zh", [t for t, _ in found.values()])
    changed = 0
    for url, (title, day) in found.items():
        draft = "征求意见" in title
        stage = "introduced" if draft else "signed"
        bill = {"key": "CN-" + url.rsplit("/", 1)[1].removesuffix(".htm"), "jurisdiction": "CN", "number": "",
                "title": title, "url": url, "source": "Cyberspace Administration of China", "lang": "zh",
                "history": [{"date": day, "stage": stage, "text": "征求意见稿" if draft else "发布"}]}
        changed += upsert(conn, bill)
    conn.commit()
    retitle(conn, "CN", "zh")
    return changed
