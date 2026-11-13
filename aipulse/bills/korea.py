"""Korea: laws from the National Law Information Center."""
from __future__ import annotations

import re
import time
from datetime import date, timedelta

from .. import feeds

from .core import DATA_LAWS, connect_tables, upsert


# --- South Korea (National Law Information Center, law.go.kr, Ministry of Government Legislation) ---

KR_SEARCH = "https://www.law.go.kr/LSW/lsScListR.do"


KR_LINK = "https://www.law.go.kr/법령/"  # the centre's permanent address for a law, by name


KR_REFRESH_DAYS = 7


# Each version of a law is listed as "NAME[시행 2026. 1. 22.] [법률 제20676호, 2025. 1. 21., 제정]".
_KR_ITEM = re.compile(r'title="([^"\[]*)\[시행 (\d{4})\. ?(\d{1,2})\. ?(\d{1,2})\.\] '
                      r'\[([^\]]*?) 제(\d+)호, (\d{4})\. ?(\d{1,2})\. ?(\d{1,2})\., ([^\]]+)\]"')


_KR_TYPES = {"법률": "Act", "대통령령": "Presidential Decree", "총리령": "Prime Minister's Decree"}


# English names (as the government translates them) and what each does. Korea's offline translation model
# is unusable, so names come from this list; a new law keeps its Korean name until it's added here.
KR_NAMES = {
    "인공지능 발전과 신뢰 기반 조성 등에 관한 기본법": (
        "Framework Act on the Development of AI and the Establishment of a Foundation for Trust (AI Basic Act)",
        "Korea's comprehensive AI law: national AI policy and industry support, and duties for high-impact and "
        "generative AI such as risk management, transparency and labelling of AI-generated content."),
    "인공지능 데이터센터 산업 진흥에 관한 특별법": (
        "Special Act on Promoting the AI Data Center Industry", "Support for building and running AI data centres."),
    "산업 디지털 전환 및 인공지능 활용 촉진법": (
        "Act on Promoting Industrial Digital Transformation and the Use of AI",
        "Promotes digital transformation and the use of AI across industry."),
    "인공지능 및 데이터 기반 행정 활성화에 관한 법률": (
        "Act on Promoting AI- and Data-Based Public Administration",
        "Promotes the use of AI and data in government administration."),
    "국가인공지능위원회의 설치 및 운영에 관한 규정": (
        "Regulation on the National AI Committee", "Set up the presidential committee that coordinated national AI policy."),
    "국가인공지능전략위원회의 설치 및 운영에 관한 규정": (
        "Regulation on the National AI Strategy Committee",
        "Set up the presidential committee that coordinates national AI strategy."),
    "개인정보 보호법": (
        "Personal Information Protection Act",
        "Korea's data protection law: how personal information may be collected, used and shared, and people's "
        "rights over theirs."),
}


def kr_english(name: str) -> tuple[str, str]:
    """(English name, what it does) for a Korean AI law, its enforcement decree or rule; ("", "") if unknown."""
    for suffix, kind, what in ((" 시행령", "Enforcement Decree of the ", "Sets out how the {} is applied."),
                               (" 시행규칙", "Enforcement Rule of the ", "Detailed rules for applying the {}.")):
        if name.endswith(suffix):
            base = KR_NAMES.get(name[: -len(suffix)])
            return (kind + base[0], what.format(base[0].split(" (")[0])) if base else ("", "")
    return KR_NAMES.get(name, ("", ""))


def kr_laws(page: str) -> dict[str, dict]:
    """Each law's first enactment, first entry into force and (if its latest version repeals it) repeal."""
    laws = {}
    for m in _KR_ITEM.finditer(page):
        name, kind = m.group(1).strip(), m.group(10).strip()
        if "인공지능" not in name and not DATA_LAWS["KR"].search(name):
            continue
        effective = f"{m.group(2)}-{int(m.group(3)):02d}-{int(m.group(4)):02d}"
        promulgated = f"{m.group(7)}-{int(m.group(8)):02d}-{int(m.group(9)):02d}"
        law = laws.setdefault(name, {"versions": []})
        law["versions"].append({"type": m.group(5).strip(), "no": m.group(6), "effective": effective,
                                "promulgated": promulgated, "kind": kind})
    for law in laws.values():
        versions = sorted(law["versions"], key=lambda v: (v["promulgated"], v["effective"]))
        first, last = versions[0], versions[-1]
        kind = _KR_TYPES.get(first["type"], "Ministerial Decree" if first["type"].endswith("부령") else first["type"])
        law["number"] = f"{kind} No. {first['no']}"
        history = [{"date": first["promulgated"], "stage": "signed", "text": "공포"}]
        if first["effective"] <= date.today().isoformat():
            history.append({"date": max(first["effective"], first["promulgated"]), "stage": "in_force", "text": "시행"})
        if "폐지" in last["kind"]:
            history.append({"date": last["promulgated"], "stage": "withdrawn", "text": "폐지"})
        law["history"] = history
    return laws


def sync_korea(conn, fetcher=None, log=print) -> int:
    """Korea's laws and decrees with AI in their name, from the official law database (robots.txt allows it;
    laws aren't protected by copyright in Korea, Copyright Act Art. 7). Read about once a week."""
    connect_tables(conn)
    last = conn.execute("SELECT value FROM meta WHERE key = 'kr_sync'").fetchone()
    if last and last[0] > (date.today() - timedelta(days=KR_REFRESH_DAYS)).isoformat():
        return 0
    import urllib.parse
    import urllib.request
    if not feeds.allowed(KR_SEARCH):
        raise feeds.Disallowed(KR_SEARCH)
    page = ""
    for term in ("인공지능", "개인정보 보호법"):  # AI; the Personal Information Protection Act
        form = urllib.parse.urlencode({"q": term, "query": term, "section": "lawNm", "outmax": "100", "pg": "1"}).encode()
        req = urllib.request.Request(KR_SEARCH, data=form, headers={"User-Agent": feeds.USER_AGENT})
        with urllib.request.urlopen(req, timeout=40, context=feeds.TLS) as resp:
            page += resp.read().decode("utf-8", "replace")
        time.sleep(1)
    from urllib.parse import quote
    changed = 0
    for name, law in kr_laws(page).items():
        english, what = kr_english(name)
        changed += upsert(conn, {"key": "KR-" + name, "jurisdiction": "KR", "number": law["number"],
                                 "title": name, "short_title": english, "url": KR_LINK + quote(name),
                                 "source": "National Law Information Center (Korea)", "summary": what,
                                 "history": law["history"]})
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('kr_sync', ?)", (date.today().isoformat(),))
    conn.commit()
    return changed
