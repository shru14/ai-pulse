"""Countries and blocs the regulation tracker recognises, and how to spot them in a headline.

Patterns are case-sensitive on purpose ("US" the country, not "us"). Each entry:
    code: (display name, world-atlas numeric id or None, [patterns], optional (lon, lat) for a dot)
Countries too small for the 110m world map (Singapore, Hong Kong, Malta) get a dot instead.
"EU" actions are shaded on every member state; "INTL" (UN, OECD, G7...) is listed but not mapped.
"""

from __future__ import annotations

import re

from .geo import project

JURISDICTIONS: dict[str, tuple] = {
    "INTL": ("International bodies", None, [r"\bUN\b", r"United Nations", r"\bOECD\b", r"\bG7\b", r"\bG20\b",
                                             r"Council of Europe", r"UNESCO", r"Bletchley", r"AI Safety Summit",
                                             r"AI Action Summit", r"AI Impact Summit"]),
    "EU": ("European Union", None, [r"\bEU\b", r"European Union", r"European Commission", r"European Parliament",
                                    r"\bEDPB\b", r"European Data Protection", r"EU AI Act", r"AI Office", r"Brussels",
                                    r"Council of the EU", r"\bMEPs?\b"]),
    "US": ("United States", "840", [r"\bU\.S\.(?!\w)", r"\bUS\b", r"\bUSA\b", r"United States",
                                    r"(?<!Latin )(?<!South )(?<!Central )\bAmerica(ns?)?\b", r"\bCongress",
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
    "GB": ("United Kingdom", "826", [r"\bUK\b", r"\bU\.K\.", r"United Kingdom", r"\bBritain", r"\bBritish",
                                     r"\bEngland\b", r"\bScotland", r"\bOfcom\b", r"\bICO\b",
                                     r"Information Commissioner", r"\bCMA\b", r"Competition and Markets Authority",
                                     r"Downing Street", r"Westminster"]),
    "CN": ("China", "156", [r"\bChina\b", r"\bChinese\b", r"\bBeijing\b", r"Cyberspace Administration", r"\bCAC\b"]),
    "IN": ("India", "356", [r"\bIndia\b", r"\bIndian\b(?! Ocean)", r"\bMeitY\b", r"New Delhi"]),
    "JP": ("Japan", "392", [r"\bJapan", r"\bTokyo\b"]),
    "KR": ("South Korea", "410", [r"(?<!North )\bKorea(n)?\b", r"\bSeoul\b"]),
    "TW": ("Taiwan", "158", [r"\bTaiwan"]),
    "HK": ("Hong Kong", None, [r"Hong Kong"], (114.17, 22.3)),
    "SG": ("Singapore", None, [r"\bSingapore", r"\bIMDA\b", r"\bPDPC\b"], (103.82, 1.35)),
    "ID": ("Indonesia", "360", [r"\bIndonesia", r"\bJakarta\b"]),
    "MY": ("Malaysia", "458", [r"\bMalaysia"]),
    "TH": ("Thailand", "764", [r"\bThailand\b", r"\bThai\b"]),
    "VN": ("Vietnam", "704", [r"\bVietnam", r"Viet Nam"]),
    "PH": ("Philippines", "608", [r"\bPhilippine", r"\bFilipino"]),
    "PK": ("Pakistan", "586", [r"\bPakistan"]),
    "BD": ("Bangladesh", "050", [r"\bBangladesh"]),
    "AU": ("Australia", "036", [r"\bAustralia", r"\bCanberra\b", r"\beSafety\b"]),
    "NZ": ("New Zealand", "554", [r"New Zealand"]),
    "CA": ("Canada", "124", [r"\bCanada\b", r"\bCanadian", r"\bOttawa\b", r"\bOntario\b", r"\bQu[eé]bec\b"]),
    "MX": ("Mexico", "484", [r"(?<!New )\bMexico\b", r"\bMexican"]),
    "BR": ("Brazil", "076", [r"\bBrazil", r"\bBras[ií]lia\b", r"\bANPD\b"]),
    "AR": ("Argentina", "032", [r"\bArgentin"]),
    "CL": ("Chile", "152", [r"\bChile\b", r"\bChilean"]),
    "CO": ("Colombia", "170", [r"\bColombia"]),
    "PE": ("Peru", "604", [r"\bPeru\b", r"\bPeruvian"]),
    "FR": ("France", "250", [r"\bFrance\b", r"\bFrench\b", r"\bCNIL\b", r"\bMacron\b", r"\bParis\b"]),
    "DE": ("Germany", "276", [r"\bGerman", r"\bBerlin\b", r"\bBundestag\b"]),
    "IT": ("Italy", "380", [r"\bItaly\b", r"\bItalian", r"\bGarante\b"]),
    "ES": ("Spain", "724", [r"\bSpain\b", r"\bSpanish\b", r"\bMadrid\b", r"\bAESIA\b", r"\bAEPD\b"]),
    "NL": ("Netherlands", "528", [r"\bNetherlands\b", r"\bDutch\b"]),
    "IE": ("Ireland", "372", [r"\bIreland\b", r"\bIrish\b", r"Data Protection Commission", r"\bDPC\b"]),
    "BE": ("Belgium", "056", [r"\bBelgi"]),
    "LU": ("Luxembourg", "442", [r"\bLuxembourg"]),
    "SE": ("Sweden", "752", [r"\bSweden\b", r"\bSwedish\b"]),
    "DK": ("Denmark", "208", [r"\bDenmark\b", r"\bDanish\b"]),
    "FI": ("Finland", "246", [r"\bFinland\b", r"\bFinnish\b"]),
    "PL": ("Poland", "616", [r"\bPoland\b", r"\bPolish government"]),
    "AT": ("Austria", "040", [r"\bAustria"]),
    "PT": ("Portugal", "620", [r"\bPortugal", r"\bPortuguese\b"]),
    "GR": ("Greece", "300", [r"\bGreece\b", r"\bGreek\b"]),
    "CZ": ("Czechia", "203", [r"\bCzech"]),
    "HU": ("Hungary", "348", [r"\bHungar"]),
    "RO": ("Romania", "642", [r"\bRomania"]),
    "EE": ("Estonia", "233", [r"\bEstonia"]),
    "MT": ("Malta", None, [r"\bMalta\b", r"\bMaltese\b"], (14.4, 35.9)),
    "CH": ("Switzerland", "756", [r"\bSwitzerland\b", r"\bSwiss\b"]),
    "NO": ("Norway", "578", [r"\bNorway\b", r"\bNorwegian\b"]),
    "RU": ("Russia", "643", [r"\bRussia", r"\bKremlin\b", r"\bMoscow\b"]),
    "UA": ("Ukraine", "804", [r"\bUkrain", r"\bKyiv\b"]),
    "TR": ("Türkiye", "792", [r"\bT[üu]rkiye\b", r"\bTurkey\b", r"\bTurkish\b"]),
    "IL": ("Israel", "376", [r"\bIsrael"]),
    "AE": ("United Arab Emirates", "784", [r"\bUAE\b", r"United Arab Emirates", r"\bEmirati", r"\bDubai\b",
                                           r"Abu Dhabi"]),
    "SA": ("Saudi Arabia", "682", [r"\bSaudi\b"]),
    "QA": ("Qatar", "634", [r"\bQatar"]),
    "EG": ("Egypt", "818", [r"\bEgypt"]),
    "NG": ("Nigeria", "566", [r"\bNigeria"]),
    "KE": ("Kenya", "404", [r"\bKenya"]),
    "GH": ("Ghana", "288", [r"\bGhana"]),
    "RW": ("Rwanda", "646", [r"\bRwanda"]),
    "ZA": ("South Africa", "710", [r"South Africa"]),
}

EU_MEMBERS = ["AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT",
              "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"]
# Members the tracker doesn't detect by name still need their map id to be shaded for EU-wide actions.
_EU_EXTRA_IDS = {"BG": ("Bulgaria", "100"), "HR": ("Croatia", "191"), "CY": ("Cyprus", "196"),
                 "LV": ("Latvia", "428"), "LT": ("Lithuania", "440"), "SK": ("Slovakia", "703"),
                 "SI": ("Slovenia", "705")}

_patterns = {code: re.compile("|".join(v[2])) for code, v in JURISDICTIONS.items()}


# A place right after these is what a story is about, not who is acting:
# "US bill seeks AI pact with China", "CEOs urge UN to act".
_OBJECT = re.compile(r"\b(with|against|on|toward|towards|urg(e|es|ed|ing)|asks?|pressures?)\s+(the\s+)?$", re.I)


def _in_order(text: str, actors_only: bool) -> list[str]:
    hits = []
    for code, pattern in _patterns.items():
        for m in pattern.finditer(text):
            if actors_only and _OBJECT.search(text[max(0, m.start() - 20) : m.start()]):
                continue
            hits.append((m.start(), code))
            break
    return [code for _, code in sorted(hits)]


def detect(title: str, summary: str = "", limit: int = 4, actors_only: bool = False) -> list[str]:
    """Jurisdiction codes named in the story, in order of mention, title first.

    actors_only skips places a story is about rather than the one acting (see _OBJECT); if that
    leaves nothing, all mentions count.
    """
    found = _in_order(title, actors_only) or (_in_order(title, False) if actors_only else [])
    found += [c for c in _in_order(summary, actors_only) if c not in found]
    return found[:limit]


def meta() -> dict:
    """Names, map ids and dot positions for the page."""
    out = {}
    for code, v in JURISDICTIONS.items():
        entry = {"name": v[0], "mapId": v[1], "eu": code in EU_MEMBERS}
        if len(v) > 3:
            entry["dot"] = project(*v[3])
        out[code] = entry
    for code, (name, map_id) in _EU_EXTRA_IDS.items():
        out[code] = {"name": name, "mapId": map_id, "eu": True}
    for code, name in US_STATES.items():  # drawn on the US map (templates/us.json), not the world map
        out[f"US-{code}"] = {"name": name, "mapId": None, "eu": False, "state": code}
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
