"""Countries and blocs the regulation tracker recognises, and how to spot them in a headline.

Patterns are case-sensitive on purpose ("US" the country, not "us"). Each entry:
    code: (display name, [patterns])
"EU" actions also count for every member state when the tracker is filtered to one; "INTL" covers the UN,
OECD, G7 and similar bodies.
"""

from __future__ import annotations

import re


JURISDICTIONS: dict[str, tuple] = {
    "INTL": ("International bodies", [r"\bUN\b", r"United Nations", r"\bOECD\b", r"\bG7\b", r"\bG20\b",
                                      r"Council of Europe", r"UNESCO", r"Bletchley", r"AI Safety Summit",
                                      r"AI Action Summit", r"AI Impact Summit"]),
    "EU": ("European Union", [r"\bEU\b", r"European Union", r"European Commission", r"European Parliament",
                              r"\bEDPB\b", r"European Data Protection", r"EU AI Act", r"AI Office", r"Brussels",
                              r"Council of the EU", r"\bMEPs?\b"]),
    "US": ("United States", [r"\bU\.S\.(?!\w)", r"\bUS\b", r"\bUSA\b", r"United States",
                             r"(?<!Latin )(?<!South )(?<!Central )(?<!Lake )(?<!Captain )(?<!Bank of )\bAmerica(ns?)?\b", r"\bCongress",
                             r"White House", r"\bFTC\b", r"Federal Trade Commission", r"\bFCC\b", r"\bSEC\b",
                             r"\bFDA\b", r"\bNIST\b", r"\bDOJ\b", r"Justice Department", r"Trump administration",
                             r"\bCalifornia", r"\bColorado", r"\bTexas", r"New York(?! Times)", r"\bIllinois",
                             r"\bUtah\b", r"\bConnecticut", r"\bVirginia", r"\bMassachusetts", r"\bFlorida",
                             r"\bNewsom\b", r"Washington state", r"New Mexico", r"\bMichigan", r"\bOregon",
                             r"\bMinnesota", r"\bMaryland", r"\bTennessee", r"\bNew Jersey",
                             r"\bOre\.", r"\bCalif\.", r"House,? (and )?Senate", r"Senate and House",
                             # lawmakers and governors who often lead AI headlines without naming the US
                             r"\bSanders\b", r"\bCasar\b", r"\bSchumer\b", r"\bHawley\b", r"\bBlumenthal\b",
                             r"\bCruz\b", r"\bPritzker\b", r"\bKotek\b", r"\bSpanberger\b", r"\bHochul\b",
                             r"\bDeSantis\b", r"\bPolis\b"]),
    "GB": ("United Kingdom", [r"\bUK\b", r"\bU\.K\.", r"United Kingdom", r"\bBritain", r"\bBritish",
                              r"\bEngland\b", r"\bScotland", r"\bOfcom\b", r"\bICO\b",
                              r"Information Commissioner", r"\bCMA\b", r"Competition and Markets Authority",
                              r"Downing Street", r"Westminster"]),
    "CN": ("China", [r"\bChina\b", r"\bChinese\b", r"\bBeijing\b", r"Cyberspace Administration", r"\bCAC\b"]),
    "IN": ("India", [r"\bIndia\b", r"\bIndian\b(?! Ocean)", r"\bMeitY\b", r"New Delhi"]),
    "JP": ("Japan", [r"\bJapan", r"\bTokyo\b"]),
    "KR": ("South Korea", [r"(?<!North )\bKorea(n)?\b", r"\bSeoul\b"]),
    "TW": ("Taiwan", [r"\bTaiwan"]),
    "HK": ("Hong Kong", [r"Hong Kong"]),
    "SG": ("Singapore", [r"\bSingapore", r"\bIMDA\b", r"\bPDPC\b"]),
    "ID": ("Indonesia", [r"\bIndonesia", r"\bJakarta\b"]),
    "MY": ("Malaysia", [r"\bMalaysia"]),
    "TH": ("Thailand", [r"\bThailand\b", r"\bThai\b"]),
    "VN": ("Vietnam", [r"\bVietnam", r"Viet Nam"]),
    "PH": ("Philippines", [r"\bPhilippine", r"\bFilipino", r"\bCHEd\b"]),
    "PK": ("Pakistan", [r"\bPakistan"]),
    "BD": ("Bangladesh", [r"\bBangladesh"]),
    "AU": ("Australia", [r"\bAustralia", r"\bCanberra\b", r"\beSafety\b"]),
    "NZ": ("New Zealand", [r"New Zealand"]),
    "CA": ("Canada", [r"\bCanada\b", r"\bCanadian", r"\bOttawa\b", r"\bOntario\b", r"\bQu[eé]bec\b"]),
    "MX": ("Mexico", [r"(?<!New )\bMexico\b", r"\bMexican"]),
    "BR": ("Brazil", [r"\bBrazil", r"\bBras[ií]lia\b", r"\bANPD\b"]),
    "AR": ("Argentina", [r"\bArgentin"]),
    "CL": ("Chile", [r"\bChile\b", r"\bChilean"]),
    "CO": ("Colombia", [r"\bColombia"]),
    "PE": ("Peru", [r"\bPeru\b", r"\bPeruvian"]),
    "FR": ("France", [r"\bFrance\b", r"\bFrench\b", r"\bCNIL\b", r"\bMacron\b", r"\bParis\b"]),
    "DE": ("Germany", [r"\bGerman", r"\bBerlin\b", r"\bBundestag\b"]),
    "IT": ("Italy", [r"\bItaly\b", r"\bItalian", r"\bGarante\b"]),
    "ES": ("Spain", [r"\bSpain\b", r"\bSpanish\b", r"\bMadrid\b", r"\bAESIA\b", r"\bAEPD\b"]),
    "NL": ("Netherlands", [r"\bNetherlands\b", r"\bDutch\b"]),
    "IE": ("Ireland", [r"\bIreland\b", r"\bIrish\b", r"Data Protection Commission", r"\bDPC\b"]),
    "BE": ("Belgium", [r"\bBelgi"]),
    "LU": ("Luxembourg", [r"\bLuxembourg"]),
    "SE": ("Sweden", [r"\bSweden\b", r"\bSwedish\b"]),
    "DK": ("Denmark", [r"\bDenmark\b", r"\bDanish\b"]),
    "FI": ("Finland", [r"\bFinland\b", r"\bFinnish\b"]),
    "PL": ("Poland", [r"\bPoland\b", r"\bPolish government"]),
    "AT": ("Austria", [r"\bAustria"]),
    "PT": ("Portugal", [r"\bPortugal", r"\bPortuguese\b"]),
    "GR": ("Greece", [r"\bGreece\b", r"\bGreek\b"]),
    "CZ": ("Czechia", [r"\bCzech"]),
    "HU": ("Hungary", [r"\bHungar"]),
    "RO": ("Romania", [r"\bRomania"]),
    "EE": ("Estonia", [r"\bEstonia"]),
    "MT": ("Malta", [r"\bMalta\b", r"\bMaltese\b"]),
    "CH": ("Switzerland", [r"\bSwitzerland\b", r"\bSwiss\b"]),
    "NO": ("Norway", [r"\bNorway\b", r"\bNorwegian\b"]),
    "RU": ("Russia", [r"\bRussia", r"\bKremlin\b", r"\bMoscow\b"]),
    "UA": ("Ukraine", [r"\bUkrain", r"\bKyiv\b"]),
    "TR": ("Türkiye", [r"\bT[üu]rkiye\b", r"\bTurkey\b", r"\bTurkish\b"]),
    "IL": ("Israel", [r"\bIsrael"]),
    "AE": ("United Arab Emirates", [r"\bUAE\b", r"United Arab Emirates", r"\bEmirati", r"\bDubai\b",
                                    r"Abu Dhabi"]),
    "SA": ("Saudi Arabia", [r"\bSaudi\b"]),
    "QA": ("Qatar", [r"\bQatar"]),
    "EG": ("Egypt", [r"\bEgypt"]),
    "NG": ("Nigeria", [r"\bNigeria"]),
    "KE": ("Kenya", [r"\bKenya"]),
    "GH": ("Ghana", [r"\bGhana"]),
    "RW": ("Rwanda", [r"\bRwanda"]),
    "ZA": ("South Africa", [r"South Africa"]),
}

EU_MEMBERS = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT",
              "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"]


_patterns = {code: re.compile("|".join(v[1])) for code, v in JURISDICTIONS.items()}


# A place right after these is what a story is about, not who is acting:
# "US bill seeks AI pact with China", "CEOs urge UN to act".
_OBJECT = re.compile(r"\b(with|against|on|toward|towards|urg(e|es|ed|ing)|asks?|pressures?)\s+(the\s+)?$", re.I)


# A place right before these describes a person or business, not a government acting:
# "Michigan CEO loses job", "Michigan credit union CEO out", "Texas startup raises $50M".
_PRIVATE = re.compile(r"^\s+(?:[\w'’-]+\s+){0,2}?(CEOs?|executives?|execs?|founders?|bosses|boss|man|men|woman|"
                      r"women|teens?|students?|couples?|family|families|startups?|compan(y|ies)|firms?|banks?|"
                      r"credit unions?)\b", re.I)


def _in_order(text: str, actors_only: bool, governments_only: bool = False) -> list[str]:
    hits = []
    for code, pattern in _patterns.items():
        for m in pattern.finditer(text):
            if actors_only and _OBJECT.search(text[max(0, m.start() - 20) : m.start()]):
                continue
            if governments_only and _PRIVATE.search(text[m.end() : m.end() + 40]):
                continue
            hits.append((m.start(), code))
            break
    return [code for _, code in sorted(hits)]


def acting(title: str) -> list[str]:
    """Places named in the headline as governments acting, with no fallback: [] for "Michigan CEO loses job"."""
    return _in_order(title, True, governments_only=True)


def detect(title: str, summary: str = "", limit: int = 4, actors_only: bool = False) -> list[str]:
    """Jurisdiction codes named in the story, in order of mention, title first.

    actors_only skips places a story is about rather than the one acting (see _OBJECT); if that
    leaves nothing, all mentions count.
    """
    found = _in_order(title, actors_only) or (_in_order(title, False) if actors_only else [])
    found += [c for c in _in_order(summary, actors_only) if c not in found]
    return found[:limit]


def meta() -> dict:
    """Display names for the page, plus which codes are EU members and which are US states."""
    out = {code: {"name": v[0], "eu": code in EU_MEMBERS} for code, v in JURISDICTIONS.items()}
    for code, name in US_STATES.items():
        out[f"US-{code}"] = {"name": name, "eu": False, "state": code}
    return out


# --- US states: the tracker records e.g. "US-CA" next to "US" so the map can split the US by state ---
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
# Names that need care: "Washington" alone usually means the federal government, "New York Times" is a paper,
# "Georgia" is also a country, "District of Columbia" is rarely written out.
_STATE_PATTERN = {code: rf"\b{name}\b" for code, name in US_STATES.items()}
_STATE_PATTERN.update({"WA": r"Washington [Ss]tate|state of Washington", "NY": r"New York(?! Times)(?! City)",
                       "DC": r"District of Columbia|\bD\.C\. Council"})
# Governors and state abbreviations that name a state without saying it.
_STATE_EXTRA = {"CA": r"\bNewsom\b|\bCalif\.", "OR": r"\bKotek\b|\bOre\.", "IL": r"\bPritzker\b|\bIll\.",
                "VA": r"\bSpanberger\b", "NY": r"\bHochul\b", "FL": r"\bDeSantis\b|\bFla\.", "CO": r"\bPolis\b|\bColo\.",
                "MA": r"\bMass\.", "TX": r"\bTex\.", "MI": r"\bMich\.", "PA": r"\bPa\.", "WA": r"\bWash\. state"}
_states = {code: re.compile("|".join(filter(None, [_STATE_PATTERN[code], _STATE_EXTRA.get(code)])))
           for code in US_STATES}


def us_states(title: str, summary: str = "", limit: int = 3) -> list[str]:
    """US state codes ("US-CA") a story names, title first."""
    found = [f"US-{c}" for c, p in _states.items() if p.search(title)]
    found += [f"US-{c}" for c, p in _states.items() if f"US-{c}" not in found and p.search(summary)]
    return found[:limit]
