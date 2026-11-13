"""Follow AI bills through their lifecycle from official sources.

- US Congress: the congress.gov API, with a free personal key (https://api.congress.gov/sign-up/, name and
  email only; set CONGRESS_API_KEY). Without one it's skipped: api.data.gov's DEMO_KEY is only for trying the
  API before signing up, not for a site that runs every 6 hours. Each collection reads the current Congress's
  bills updated since the last sync, keeps those with AI in the title, and reads their official actions.
- EU: the European Parliament's open data API (no key). AI procedures are found by their English title;
  their events give the stages.
- UK: the UK Parliament Bills API (no key; Open Parliament Licence). AI bills are found by title searches;
  their readings in each House give the stages.
- Brazil: the Chamber of Deputies' open data API (no key; published for reuse in apps). AI bills are found by
  keyword and their Portuguese summary; bills attached to a lead bill ("tramitando em conjunto") move with it
  and aren't shown separately. Their procedural events give the stages.
- China: the Cyberspace Administration of China's policy and regulation lists (robots.txt allows them; no API).
  Only each AI regulation's official title, date and link are read; the title is shown in English
  (machine translation) and nothing else is copied. Official regulations aren't copyrighted in China
  (Copyright Law, Article 5). The national law database (flk.npc.gov.cn) forbids automated access and
  gov.cn's search is closed to it, so neither is used.
- India: the Parliament of India's legislation API (sansad.in, the one its own bill pages use; no key).
  AI bills, and the Digital Personal Data Protection Act 2023 with the bills amending it.
  Bills in both Houses with their introduction, passing and assent dates. India Code, MeitY and PIB turn
  away automated requests, so they aren't used.
- Japan: the e-Gov law API (Digital Agency; no key). Laws and cabinet orders with 人工知能 (AI) in the
  title, with promulgation and enforcement dates. Government of Japan Standard Terms of Use 2.0: the source
  is credited on the page, and the titles are marked as machine-translated (an edit).
- Australia: the Federal Register of Legislation API (no key; CC BY 4.0, credited on the page). It holds Acts
  and instruments once made (bills in Parliament aren't there), so these cards start at assent.

Every bill has one tracker card (an item with source "congress.gov" or "European Parliament"), dated at
its latest stage so it moves up the feed when it advances. The card shows the whole timeline. News
stories that name the bill (by number, or by short title) are attached to that card.

State legislatures need an Open States API key and aren't connected yet; the OECD.AI policy database
has no public API.
"""
from __future__ import annotations

import time  # noqa: F401  (tests pause the readers through bills.time)

from .. import feeds, store
from .core import (AI_TITLE, DATA_LAWS, ENDED, LABELS, OFFICIAL_SOURCES, SCHEMA, STAGES, _BILL_NUMBER, _CA_BILL, _EU_ACTIVITY, _HEADING, _LANGS, _TAGS, _US_RULES, _US_TYPES, _get_json, _number_key, attach_news, connect_tables, current, describe, eu_history, lifecycle, logger, refresh_cards, retitle, upsert, us_history)
from .us import (CONGRESS_API, _US_OTHER, _US_PURPOSE, _congress_key, _crs_summary, _current_congress, _us_context, _us_describe_old, _us_remember_context, sync_congress, us_interim, us_purpose)
from .eu import (EP_API, EP_FORMAT, EU_DATA, _eu_short_title, _procedure, sync_europarl)
from .uk import (UK_API, UK_SEARCHES, sync_uk, uk_history)
from .brazil import (BR_AI, BR_API, BR_ATTACHED, BR_DATA, BR_KEYWORD, _BR_RULES, br_history, sync_brazil)
from .china import (CN_AI, CN_LISTS, CN_SITE, _CN_ITEM, sync_china)
from .canada import (CA_GAZETTE, CA_GAZETTE_ISSUES, _CA_ISSUE, _CA_LISTS, _CA_REG, _ca_text, sync_canada_gazette)
from .india import (IN_API, IN_SEARCHES, _IN_QUERY, in_history, sync_india)
from .japan import (JP_API, JP_DATA, JP_SEARCHES, _JP_TYPES, jp_history, sync_japan)
from .vietnam import (VN_AI, VN_REFRESH_DAYS, VN_SITE, _VN_NAMES, _VN_TYPES, _vn_meta, sync_vietnam)
from .switzerland import (CH_API, CH_SEARCHES, _CH_COUNCILS, _CH_POLICY, _CH_SELECT, _CH_STANCE, _CH_TYPES, _ch_date, _ch_demand, ch_history, sync_switzerland)
from .malaysia import (MY_AI, MY_BILLS, _MY_FIELD, _my_date, sync_malaysia)
from .taiwan import (TW_LAWS, TW_LINK, TW_SEARCHES, _TW_ROW, _roc, sync_taiwan, tw_laws)
from .korea import (KR_LINK, KR_NAMES, KR_REFRESH_DAYS, KR_SEARCH, _KR_ITEM, _KR_TYPES, kr_english, kr_laws, sync_korea)
from .australia import (AU_API, AU_SEARCHES, au_history, sync_australia)
from .ireland import (IE_API, IE_DATA_YEARS, IE_PAGE, IE_SINCE, ie_history, sync_ireland)
from .norway import (NO_AI, NO_API, NO_DATA_FROM, NO_SESSIONS, _NO_DATE, _no_day, no_history, sync_norway)

# every name stays reachable as bills.<name>, as when this was one file
__all__ = ["AI_TITLE", "AU_API", "AU_SEARCHES", "BR_AI", "BR_API", "BR_ATTACHED", "BR_DATA", "BR_KEYWORD", "CA_GAZETTE", "CA_GAZETTE_ISSUES", "CH_API", "CH_SEARCHES", "CN_AI", "CN_LISTS", "CN_SITE", "CONGRESS_API", "DATA_LAWS", "ENDED", "EP_API", "EP_FORMAT", "EU_DATA", "IE_API", "IE_DATA_YEARS", "IE_PAGE", "IE_SINCE", "IN_API", "IN_SEARCHES", "JP_API", "JP_DATA", "JP_SEARCHES", "KR_LINK", "KR_NAMES", "KR_REFRESH_DAYS", "KR_SEARCH", "LABELS", "MY_AI", "MY_BILLS", "NO_AI", "NO_API", "NO_DATA_FROM", "NO_SESSIONS", "OFFICIAL_SOURCES", "SCHEMA", "STAGES", "TW_LAWS", "TW_LINK", "TW_SEARCHES", "UK_API", "UK_SEARCHES", "VN_AI", "VN_REFRESH_DAYS", "VN_SITE", "_BILL_NUMBER", "_BR_RULES", "_CA_BILL", "_CA_ISSUE", "_CA_LISTS", "_CA_REG", "_CH_COUNCILS", "_CH_POLICY", "_CH_SELECT", "_CH_STANCE", "_CH_TYPES", "_CN_ITEM", "_EU_ACTIVITY", "_HEADING", "_IN_QUERY", "_JP_TYPES", "_KR_ITEM", "_KR_TYPES", "_LANGS", "_MY_FIELD", "_NO_DATE", "_TAGS", "_TW_ROW", "_US_OTHER", "_US_PURPOSE", "_US_RULES", "_US_TYPES", "_VN_NAMES", "_VN_TYPES", "_ca_text", "_ch_date", "_ch_demand", "_congress_key", "_crs_summary", "_current_congress", "_eu_short_title", "_get_json", "_incidents_sync", "_my_date", "_no_day", "_number_key", "_oecd_api", "_oecd_sync", "_procedure", "_roc", "_standards_sync", "_us_context", "_us_describe_old", "_us_remember_context", "_vn_meta", "attach_news", "au_history", "br_history", "ch_history", "connect_tables", "current", "describe", "eu_history", "ie_history", "in_history", "jp_history", "kr_english", "kr_laws", "lifecycle", "logger", "no_history", "refresh_cards", "retitle", "sync", "sync_australia", "sync_brazil", "sync_canada_gazette", "sync_china", "sync_congress", "sync_europarl", "sync_india", "sync_ireland", "sync_japan", "sync_korea", "sync_malaysia", "sync_norway", "sync_switzerland", "sync_taiwan", "sync_uk", "sync_vietnam", "tw_laws", "uk_history", "upsert", "us_history", "us_interim", "us_purpose"]


def _oecd_api() -> str:
    from .. import oecd
    return oecd.API


def _oecd_sync(conn, fetcher=feeds.fetch, log=print) -> int:
    from .. import oecd  # oecd.py imports this module
    return oecd.sync(conn, fetcher, log=log)


def _incidents_sync(conn, fetcher=feeds.fetch, log=print) -> int:
    from .. import incidents
    return incidents.sync(conn, fetcher, log=log)


def _standards_sync(conn, fetcher=feeds.fetch, log=print) -> int:
    from .. import standards
    return standards.sync(conn, fetcher, log=log)


def sync(conn, fetcher=feeds.fetch, log=print) -> int:
    """Every official source; each is recorded in source health like any feed."""
    total = 0
    for name, url, fn in (("congress.gov API", CONGRESS_API, sync_congress),
                          ("European Parliament API", EP_API, sync_europarl),
                          ("UK Parliament Bills API", UK_API, sync_uk),
                          ("Canada Gazette", CA_GAZETTE.format(part=1), sync_canada_gazette),
                          ("Câmara dos Deputados API", BR_API, sync_brazil),
                          ("Federal Register of Legislation API", AU_API, sync_australia),
                          ("Cyberspace Administration of China", CN_SITE, sync_china),
                          ("Parliament of India API", IN_API, sync_india),
                          ("e-Gov law API (Japan)", JP_API, sync_japan),
                          ("National Legal Database (Vietnam)", VN_SITE, sync_vietnam),
                          ("Swiss Parliament open data", CH_API, sync_switzerland),
                          ("Parliament of Malaysia", MY_BILLS, sync_malaysia),
                          ("Legislative Yuan law system (Taiwan)", TW_LAWS, sync_taiwan),
                          ("National Law Information Center (Korea)", KR_SEARCH, sync_korea),
                          ("Houses of the Oireachtas API (Ireland)", IE_API, sync_ireland),
                          ("Stortinget open data (Norway)", NO_API, sync_norway),
                          ("OECD.AI policy database", _oecd_api(), _oecd_sync),
                          ("AI standards (ISO/IEC, IEEE; hand-kept list)", "https://www.iso.org/committee/6794475.html",
                           _standards_sync),
                          ("AI Incident Database", "https://incidentdatabase.ai/rss.xml", _incidents_sync)):
        try:
            n = fn(conn, fetcher, log=log)
            store.record_source(conn, name, url, ok=True, added=n)
            log(f"  {name}: {n} bills changed stage")
            total += n
        except Exception as exc:
            store.record_source(conn, name, url, ok=False, error=str(exc) or type(exc).__name__)
            log(f"  ! {name}: {exc}")
        conn.commit()
    refresh_cards(conn)
    return total
