"""Vietnam: legal documents from the National Legal Database."""
from __future__ import annotations

import html
import re
import time
from datetime import date, datetime, timedelta

from .. import feeds, translate

from .core import DATA_LAWS, connect_tables, retitle, upsert


# --- Vietnam (National Legal Database, vbpl.vn, Ministry of Justice) ---

VN_SITE = "https://vbpl.vn"


# The database's sitemap lists every document with its title in the URL; "tri-tue-nhan-tao" is
# "artificial intelligence". Only national documents (the sitemaps before the provincial ones) are read.
VN_AI = re.compile(r"tri-tue-nhan-tao")


_VN_TYPES = {"luat": "Law", "nghi-dinh": "Decree", "nghi-quyet": "Resolution", "thong-tu": "Circular",
             "quyet-dinh": "Decision", "chi-thi": "Directive", "phap-lenh": "Ordinance"}


_VN_NAMES = "Nghị định|Nghị quyết|Thông tư|Quyết định|Chỉ thị|Pháp lệnh"  # document types of two words


VN_REFRESH_DAYS = 7


def _vn_meta(page: str, prop: str) -> str:
    m = re.search(rf'<meta (?:property|name)="{prop}" content="([^"]*)"', page)
    return html.unescape(m.group(1)) if m else ""


def sync_vietnam(conn, fetcher=feeds.fetch, log=print) -> int:
    """Vietnamese laws, decrees and decisions about AI: title (in English), number, date and link.
    Legal documents aren't protected by copyright in Vietnam (Law on Intellectual Property, Art. 15)."""
    connect_tables(conn)
    last = conn.execute("SELECT value FROM meta WHERE key = 'vn_sync'").fetchone()
    if last and last[0] > (date.today() - timedelta(days=VN_REFRESH_DAYS)).isoformat():
        return 0
    index = fetcher(f"{VN_SITE}/sitemap.xml").decode("utf-8", "replace")
    national = index.split("Địa phương")[0]  # the provincial sitemaps follow this comment
    urls = []
    for sitemap in re.findall(r"<loc>(.*?)</loc>", national)[1:]:  # the first lists the site's own pages
        urls += [u for u in re.findall(r"<loc>(.*?)</loc>", fetcher(sitemap).decode("utf-8", "replace"))
                 if "/van-ban/chi-tiet/" in u and (VN_AI.search(u) or DATA_LAWS["VN"].search(u))]
        time.sleep(1)
    known = {r[0] for r in conn.execute("SELECT url FROM bills WHERE jurisdiction = 'VN'")}
    records = []
    for url in urls:
        key = "VN-" + url.rsplit("--", 1)[-1]
        if url in known:
            continue
        page = fetcher(url).decode("utf-8", "replace")
        time.sleep(1)
        # "Tra cứu Luật 134/2025/QH15, LUẬT TRÍ TUỆ NHÂN TẠO SỐ 134/2025/QH15. Xem toàn văn và hiệu lực."
        # (or "Tra cứu Nghị định 13/2023/NĐ-CP, Nghị định số 13/2023/NĐ-CP Bảo vệ dữ liệu cá nhân. Xem ...")
        m = re.match(rf"Tra cứu (?:{_VN_NAMES}|\S+) (\S+), (.*?)(?: (?:SỐ|số) \S+)?\. Xem", _vn_meta(page, "description"), re.S)
        issued = _vn_meta(page, "article:published_time")
        if not (m and issued):
            continue
        day = (datetime.fromisoformat(issued.replace("Z", "+00:00")) + timedelta(hours=7)).date().isoformat()
        slug = url.rsplit("/", 1)[1]
        kind = next((v for k, v in _VN_TYPES.items() if slug.startswith(k + "-")), "")
        title = re.sub(rf"^(?:{_VN_NAMES}) số \S+\s+", "", re.sub(r"\s+", " ", m.group(2)).strip())
        title = title[0] + title[1:].lower() if title.isupper() else title
        records.append({"key": key, "jurisdiction": "VN", "number": f"{kind} No. {m.group(1)}" if kind else m.group(1),
                        "title": title, "url": url, "source": "National Legal Database (Vietnam)", "lang": "vi",
                        "history": [{"date": day, "stage": "signed", "text": "Ban hành"}]})
    translate.english(conn, "vi", [r["title"] for r in records])
    changed = sum(upsert(conn, r) for r in records)
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('vn_sync', ?)", (date.today().isoformat(),))
    conn.commit()
    retitle(conn, "VN", "vi")
    return changed
