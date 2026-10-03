"""Every country, and the blocs, the regulation tracker recognises, and how to spot them in a headline.

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
                              r"\bEDPB\b", r"European Data Protection", r"EU AI Act", r"(?<!National )AI Office", r"Brussels",
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
                              r"\bEngland\b", r"\bScotland", r"(?<!New South )\bWales\b", r"Northern Ireland", r"\bOfcom\b", r"\bICO\b",
                              r"Information Commissioner", r"\bCMA\b", r"Competition and Markets Authority",
                              r"Downing Street", r"Westminster"]),
    "CN": ("China", [r"\bChina\b", r"\bChinese\b", r"\bBeijing\b", r"Cyberspace Administration", r"\bCAC\b",
                     r"Inner Mongolia"]),
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
    "IE": ("Ireland", [r"(?<!Northern )\bIreland\b", r"(?<!Northern )\bIrish\b", r"Data Protection Commission", r"\bDPC\b"]),
    "BE": ("Belgium", [r"\bBelgi"]),
    "LU": ("Luxembourg", [r"\bLuxembourg"]),
    "SE": ("Sweden", [r"\bSweden\b", r"\bSwedish\b"]),
    "DK": ("Denmark", [r"\bDenmark\b", r"\bDanish\b"]),
    "FI": ("Finland", [r"\bFinland\b", r"\bFinnish\b"]),
    "PL": ("Poland", [r"\bPoland\b", r"\bPolish government"]),
    "AT": ("Austria", [r"\bAustria"]),
    "PT": ("Portugal", [r"\bPortugal", r"(?<!Brazilian )\bPortuguese\b"]),  # the language of Brazil too
    "GR": ("Greece", [r"\bGreece\b", r"\bGreek\b"]),
    "CZ": ("Czechia", [r"\bCzech"]),
    "HU": ("Hungary", [r"\bHungar"]),
    "RO": ("Romania", [r"\bRomania"]),
    "EE": ("Estonia", [r"\bEstonia"]),
    "MT": ("Malta", [r"\bMalta\b", r"\bMaltese\b"]),
    "BG": ("Bulgaria", [r"\bBulgaria"]),
    "HR": ("Croatia", [r"\bCroatia"]),
    "CY": ("Cyprus", [r"\bCyprus\b", r"\bCypriot"]),
    "LV": ("Latvia", [r"\bLatvia"]),
    "LT": ("Lithuania", [r"\bLithuania"]),
    "SK": ("Slovakia", [r"\bSlovakia\b", r"\bSlovak\b"]),
    "SI": ("Slovenia", [r"\bSloveni"]),
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
    "NG": ("Nigeria", [r"\bNigeria", r"\bNITDA\b", r"\bFCCPC\b", r"\bNDPC\b"]),  # its IT, competition and data regulators
    "KE": ("Kenya", [r"\bKenya"]),
    "GH": ("Ghana", [r"\bGhana"]),
    "RW": ("Rwanda", [r"\bRwanda"]),
    "ZA": ("South Africa", [r"South Africa"]),
    # Countries in the OECD.AI policy database (oecd.py)
    "AM": ("Armenia", [r"\bArmenia"]),
    "BJ": ("Benin", [r"\bBenin\b"]),
    "BN": ("Brunei", [r"\bBrunei"]),
    "CI": ("Côte d'Ivoire", [r"C[ôo]te d.Ivoire", r"Ivory Coast"]),
    "CM": ("Cameroon", [r"\bCameroon"]),
    "CR": ("Costa Rica", [r"Costa Rica"]),
    "CU": ("Cuba", [r"\bCuba\b", r"\bCuban\b"]),
    "DO": ("Dominican Republic", [r"Dominican Republic"]),
    "DZ": ("Algeria", [r"\bAlgeria"]),
    "EC": ("Ecuador", [r"\bEcuador"]),
    "ET": ("Ethiopia", [r"\bEthiopia"]),
    "IS": ("Iceland", [r"\bIceland(ic)?\b"]),
    "KH": ("Cambodia", [r"\bCambodia"]),
    "KZ": ("Kazakhstan", [r"\bKazakh"]),
    "LS": ("Lesotho", [r"\bLesotho"]),
    "LY": ("Libya", [r"\bLibya"]),
    "MA": ("Morocco", [r"\bMorocc"]),
    "MR": ("Mauritania", [r"\bMauritania"]),
    "MU": ("Mauritius", [r"\bMauritius"]),
    "RS": ("Serbia", [r"\bSerbia"]),
    "SN": ("Senegal", [r"\bSenegal"]),
    "TN": ("Tunisia", [r"\bTunisia"]),
    "UG": ("Uganda", [r"\bUganda"]),
    "UY": ("Uruguay", [r"\bUruguay"]),
    "UZ": ("Uzbekistan", [r"\bUzbek"]),
    "VA": ("Holy See", [r"Holy See", r"\bVatican\b"]),
    "ZM": ("Zambia", [r"\bZambia"]),
    "ZW": ("Zimbabwe", [r"\bZimbabwe"]),
    # Every other country, so news about any of them is tagged (and a law it reports reaches the tracker).
    # Names that are also people or US states only count in forms that mean the country.
    # Europe (outside the EU)
    "AL": ("Albania", [r"\bAlbania"]),
    "AD": ("Andorra", [r"\bAndorra"]),
    "AZ": ("Azerbaijan", [r"\bAzerbaijan", r"\bBaku\b"]),
    "BY": ("Belarus", [r"\bBelarus"]),
    "BA": ("Bosnia and Herzegovina", [r"\bBosnia"]),
    "GE": ("Georgia", [r"\bTbilisi\b", r"Republic of Georgia", r"Georgian (government|parliament|president|prime minister)"]),
    "XK": ("Kosovo", [r"\bKosovo"]),
    "LI": ("Liechtenstein", [r"\bLiechtenstein"]),
    "MD": ("Moldova", [r"\bMoldova"]),
    "MC": ("Monaco", [r"\bMonaco\b"]),
    "ME": ("Montenegro", [r"\bMontenegr"]),
    "MK": ("North Macedonia", [r"\bMacedonia"]),
    "SM": ("San Marino", [r"San Marino"]),
    # Asia-Pacific
    "AF": ("Afghanistan", [r"\bAfghan"]),
    "BT": ("Bhutan", [r"\bBhutan"]),
    "FJ": ("Fiji", [r"\bFiji"]),
    "KG": ("Kyrgyzstan", [r"\bKyrgyz"]),
    "KI": ("Kiribati", [r"\bKiribati"]),
    "KP": ("North Korea", [r"North Korea", r"\bPyongyang\b", r"\bDPRK\b"]),
    "LA": ("Laos", [r"\bLaos\b", r"\bLao PDR\b"]),
    "LK": ("Sri Lanka", [r"Sri Lanka"]),
    "MH": ("Marshall Islands", [r"Marshall Islands"]),
    "FM": ("Micronesia", [r"\bMicronesia"]),
    "MM": ("Myanmar", [r"\bMyanmar", r"\bBurm(a|ese)\b"]),
    "MN": ("Mongolia", [r"(?<!Inner )\bMongolia"]),  # Inner Mongolia is a region of China
    "MV": ("Maldives", [r"\bMaldiv"]),
    "NP": ("Nepal", [r"\bNepal"]),
    "NR": ("Nauru", [r"\bNauru"]),
    "PG": ("Papua New Guinea", [r"Papua New Guinea"]),
    "PW": ("Palau", [r"\bPalau\b"]),
    "SB": ("Solomon Islands", [r"Solomon Islands"]),
    "TJ": ("Tajikistan", [r"\bTajik"]),
    "TL": ("Timor-Leste", [r"Timor-Leste", r"East Timor"]),
    "TM": ("Turkmenistan", [r"\bTurkmen"]),
    "TO": ("Tonga", [r"\bTonga\b"]),
    "TV": ("Tuvalu", [r"\bTuvalu"]),
    "VU": ("Vanuatu", [r"\bVanuatu"]),
    "WS": ("Samoa", [r"(?<!American )\bSamoa"]),
    # Americas
    "AG": ("Antigua and Barbuda", [r"\bAntigua"]),
    "BS": ("Bahamas", [r"\bBahamas\b", r"\bBahamian"]),
    "BB": ("Barbados", [r"\bBarbad"]),
    "BZ": ("Belize", [r"\bBelize"]),
    "BO": ("Bolivia", [r"\bBolivia"]),
    "DM": ("Dominica", [r"\bDominica\b"]),
    "GD": ("Grenada", [r"\bGrenada\b"]),
    "GT": ("Guatemala", [r"\bGuatemala"]),
    "GY": ("Guyana", [r"\bGuyan"]),
    "HN": ("Honduras", [r"\bHondura"]),
    "HT": ("Haiti", [r"\bHaiti"]),
    "JM": ("Jamaica", [r"\bJamaica"]),
    "KN": ("Saint Kitts and Nevis", [r"\bS(ain)?t\.? Kitts"]),
    "LC": ("Saint Lucia", [r"\bS(ain)?t\.? Lucia"]),
    "NI": ("Nicaragua", [r"\bNicaragua"]),
    "PA": ("Panama", [r"\bPanama"]),
    "PY": ("Paraguay", [r"\bParaguay"]),
    "SR": ("Suriname", [r"\bSurinam"]),
    "SV": ("El Salvador", [r"El Salvador", r"\bSalvadoran"]),
    "TT": ("Trinidad and Tobago", [r"\bTrinidad"]),
    "VC": ("Saint Vincent and the Grenadines", [r"\bGrenadines\b"]),
    "VE": ("Venezuela", [r"\bVenezuela"]),
    # Middle East & Africa
    "AO": ("Angola", [r"\bAngola"]),
    "BF": ("Burkina Faso", [r"Burkina Faso"]),
    "BH": ("Bahrain", [r"\bBahrain"]),
    "BI": ("Burundi", [r"\bBurundi"]),
    "BW": ("Botswana", [r"\bBotswana"]),
    "CD": ("DR Congo", [r"Democratic Republic of (the )?Congo", r"\bDRC\b", r"\bKinshasa\b",
                        r"\bCongo(lese)?\b(?!-Brazzaville)"]),
    "CF": ("Central African Republic", [r"Central African Republic"]),
    "CG": ("Republic of the Congo", [r"\bBrazzaville\b"]),
    "CV": ("Cabo Verde", [r"Cabo Verde", r"Cape Verde"]),
    "DJ": ("Djibouti", [r"\bDjibouti"]),
    "ER": ("Eritrea", [r"\bEritrea"]),
    "GA": ("Gabon", [r"\bGabon"]),
    "GM": ("Gambia", [r"\bGambia"]),
    "GN": ("Guinea", [r"(?<!New )(?<!Equatorial )\bGuinea\b(?!-Bissau)(?! pigs?\b)"]),
    "GQ": ("Equatorial Guinea", [r"Equatorial Guinea"]),
    "GW": ("Guinea-Bissau", [r"Guinea-Bissau"]),
    "IQ": ("Iraq", [r"\bIraq", r"\bBaghdad\b"]),
    "IR": ("Iran", [r"\bIran(ian)?s?\b", r"\bTehran\b"]),
    "JO": ("Jordan", [r"\bJordanian", r"\bAmman\b", r"Kingdom of Jordan", r"Jordan's (government|parliament|king)"]),
    "KM": ("Comoros", [r"\bComoros"]),
    "KW": ("Kuwait", [r"\bKuwait"]),
    "LB": ("Lebanon", [r"\bLeban"]),
    "LR": ("Liberia", [r"\bLiberia"]),
    "MG": ("Madagascar", [r"\bMadagascar", r"\bMalagasy"]),
    "ML": ("Mali", [r"\bMali\b", r"\bMalian\b"]),
    "MW": ("Malawi", [r"\bMalawi"]),
    "MZ": ("Mozambique", [r"\bMozambi"]),
    "NA": ("Namibia", [r"\bNamibia"]),
    "NE": ("Niger", [r"\bNiger\b", r"\bNigerien"]),
    "OM": ("Oman", [r"\bOman(i)?\b", r"\bMuscat\b"]),
    "PS": ("Palestine", [r"\bPalestin", r"\bGaza\b", r"West Bank"]),
    "SC": ("Seychelles", [r"\bSeychell"]),
    "SD": ("Sudan", [r"(?<!South )\bSudan"]),
    "SL": ("Sierra Leone", [r"Sierra Leone"]),
    "SO": ("Somalia", [r"\bSomali"]),
    "SS": ("South Sudan", [r"South Sudan"]),
    "ST": ("São Tomé and Príncipe", [r"S[ãa]o Tom[ée]"]),
    "SY": ("Syria", [r"\bSyria"]),
    "SZ": ("Eswatini", [r"\bEswatini", r"\bSwaziland"]),
    "TD": ("Chad", [r"\bChadian\b", r"N'Djamena", r"Chad's (government|parliament|president)", r"\bin Chad\b"]),
    "TG": ("Togo", [r"\bTogo\b", r"\bTogolese\b"]),
    "TZ": ("Tanzania", [r"\bTanzania"]),
    "YE": ("Yemen", [r"\bYemen"]),
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


# The tracker's regions (a filter, nothing more). The EU and its members are Europe; "INTL" (the UN, OECD,
# Council of Europe, G7, ...) is its own region. Russia belongs to none (the user's choice); it keeps its
# own country chip.
NO_REGION = {"RU"}
REGIONS = {
    "europe": ("Europe", ["EU", *EU_MEMBERS, "GB", "CH", "NO", "IS", "UA", "RS", "TR", "VA", "AM", "AL", "AD", "AZ",
                          "BY", "BA", "GE", "XK", "LI", "MD", "MC", "ME", "MK", "SM"]),
    "americas": ("Americas", ["US", "CA", "MX", "BR", "AR", "CL", "CO", "PE", "EC", "UY", "CR", "CU", "DO", "AG", "BS",
                              "BB", "BZ", "BO", "DM", "GD", "GT", "GY", "HN", "HT", "JM", "KN", "LC", "NI", "PA", "PY",
                              "SR", "SV", "TT", "VC", "VE"]),
    "asia": ("Asia-Pacific", ["CN", "IN", "JP", "KR", "AU", "NZ", "SG", "ID", "MY", "PH", "TH", "VN", "HK", "TW",
                              "BD", "PK", "KH", "BN", "KZ", "UZ", "AF", "BT", "FJ", "KG", "KI", "KP", "LA", "LK", "MH",
                              "FM", "MM", "MN", "MV", "NP", "NR", "PG", "PW", "SB", "TJ", "TL", "TM", "TO", "TV", "VU",
                              "WS"]),
    "mea": ("Middle East & Africa", ["AE", "SA", "QA", "IL", "EG", "NG", "KE", "GH", "RW", "ZA", "MA", "TN", "DZ",
                                     "LY", "MR", "SN", "CI", "CM", "BJ", "ET", "UG", "ZM", "ZW", "LS", "MU", "AO", "BF",
                                     "BH", "BI", "BW", "CD", "CF", "CG", "CV", "DJ", "ER", "GA", "GM", "GN", "GQ", "GW",
                                     "IQ", "IR", "JO", "KM", "KW", "LB", "LR", "MG", "ML", "MW", "MZ", "NA", "NE", "OM",
                                     "PS", "SC", "SD", "SL", "SO", "SS", "ST", "SY", "SZ", "TD", "TG", "TZ", "YE"]),
    "intl": ("International", ["INTL"]),
}
REGION_OF = {code: region for region, (_, codes) in REGIONS.items() for code in codes}


def region_codes(region: str) -> list[str]:
    """Every code in a region, US states included with the Americas."""
    codes = list(REGIONS.get(region, ("", []))[1])
    return codes + ([f"US-{s}" for s in US_STATES] if region == "americas" else [])


def meta() -> dict:
    """Display names for the page, plus which codes are EU members, which are US states and each one's region."""
    out = {code: {"name": v[0], "eu": code in EU_MEMBERS, "region": REGION_OF.get(code, "")}
           for code, v in JURISDICTIONS.items()}
    for code, name in US_STATES.items():
        out[f"US-{code}"] = {"name": name, "eu": False, "state": code, "region": "americas"}
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
