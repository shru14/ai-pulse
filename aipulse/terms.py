"""Why AI Pulse may read each site: its terms page, what it says, and when that was checked.

One entry per host in sources.SOURCES (tests/test_aipulse.py fails if a source has none). The standard
(README, "How we keep it legal"): robots.txt must allow us, and the site's terms, site-wide ones included, must not
forbid robots or scrapers or allow personal use only. `python -m aipulse audit` reads every terms page again and
reports what changed (aipulse/audit.py); run it monthly and before adding a source.

Kinds:
  official      a government or public body; its licence is named
  licence       an open licence or a republishing permission
  feed terms    the site's own RSS terms allow it (sometimes only unmodified: sources.py "as_provided")
  terms read    the terms page was read in full and says nothing against reading the feed
  no terms      no terms page is linked from the site
  unconfirmed   the terms page refuses automated readers: someone has to read it in a browser before it counts
  owner's choice  (PLATFORM only) a risk the project owner accepted knowingly
"""

from __future__ import annotations

CHECKED = "2026-10-07"

# host: (kind, terms page or "", what it says)
TERMS: dict[str, tuple[str, str, str]] = {
    # --- Labs and companies ---
    "blog.google": ("terms read", "https://policies.google.com/terms",
                    "Bans automated access only 'in violation of the machine-readable instructions on our web pages "
                    "(for example, robots.txt)'; robots.txt allows us"),
    "deepmind.google": ("terms read", "https://policies.google.com/terms", "Google's terms, as for blog.google"),
    "research.google": ("terms read", "https://policies.google.com/terms", "Google's terms, as for blog.google"),
    "mistral.ai": ("terms read", "https://legal.mistral.ai/terms",
                   "Terms cover Mistral's products only; no terms for the website"),
    "blog.cloudflare.com": ("terms read", "https://www.cloudflare.com/website-terms/",
                            "Bans automated access only to train AI models"),
    "sakana.ai": ("no terms", "", "Its terms (console.sakana.ai) cover its AI service, not the website"),
    "www.minimax.io": ("no terms", "", "No terms page linked from the site; the terms address shows nothing in a browser"),
    "pytorch.org": ("licence", "https://www.linuxfoundation.org/legal/terms",
                    "Linux Foundation site content is Creative Commons Attribution 3.0"),
    "www.together.ai": ("terms read", "https://www.together.ai/terms-of-service", "Nothing on feeds, robots or personal use"),
    "elevenlabs.io": ("terms read", "https://elevenlabs.io/terms-of-use", "Nothing on feeds, robots or personal use"),
    # --- Industry news ---
    "techcrunch.com": ("feed terms", "https://techcrunch.com/rss-terms-of-use/",
                       "RSS terms: display the feed's content with attribution and a link; may not modify it"),
    "the-decoder.com": ("terms read", "https://the-decoder.com/tos", "Nothing on feeds, robots or personal use"),
    "siliconangle.com": ("terms read", "https://siliconangle.com/terms-of-use/",
                         "No republishing 'unless content is specifically made for redistribution'; its RSS feed is"),
    "www.marktechpost.com": ("terms read", "https://www.marktechpost.com/privacy-policy/",
                             "Its 'Privacy & TC' page, the only terms linked: nothing on feeds, robots or personal use"),
    "www.404media.co": ("no terms", "", "No terms page linked from the site"),
    "www.engadget.com": ("feed terms", "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
                         "Yahoo RSS terms: display the feed's content unmodified, with attribution and a link"),
    "news.mit.edu": ("licence", "https://news.mit.edu/terms-of-use", "Allows republishing MIT News stories with credit"),
    "www.sciencedaily.com": ("feed terms", "https://www.sciencedaily.com/terms.htm",
                             "RSS terms encourage use on other sites, unmodified, with attribution; about 40 stored "
                             "headlines at most"),
    "www.quantamagazine.org": ("no terms", "", "No terms page linked from the site"),
    "globalvoices.org": ("licence", "https://globalvoices.org/about/global-voices-attribution-policy/",
                         "'All content created by Global Voices is published under a Creative Commons Attribution' licence"),
    "techcabal.com": ("terms read", "https://techcabal.com/terms/", "Nothing on feeds, robots or personal use"),
    "pandaily.com": ("no terms", "", "No terms page linked from the site"),
    "www.iafrikan.com": ("no terms", "", "No terms page linked from the site"),
    "feeds.feedburner.com": ("no terms", "", "Focus Taiwan (CNA): no terms page linked from the site"),
    "www.bernama.com": ("no terms", "", "No terms page linked from the site"),
    "e.vnexpress.net": ("feed terms", "https://e.vnexpress.net/rss",
                        "'These news feeds are provided for free to individuals and non-profit organizations', with "
                        "the source given"),
    "techcentral.co.za": ("no terms", "", "No terms page linked from the site"),
    "www.itweb.co.za": ("no terms", "", "No terms page linked from the site"),
    "www.wamda.com": ("licence", "https://www.wamda.com/legal", "Creative Commons Attribution-NonCommercial-NoDerivatives"),
    "en.mercopress.com": ("no terms", "", "No terms page linked from the site"),
    "www.batimes.com.ar": ("no terms", "", "No terms page linked from the site"),
    "latinamericareports.com": ("no terms", "", "No terms page linked from the site"),
    "www.itnewsafrica.com": ("no terms", "", "No terms page linked from the site"),
    "nairametrics.com": ("no terms", "", "No terms page linked from the site"),
    "simonwillison.net": ("no terms", "https://simonwillison.net/about/", "Offers its Atom feeds for anyone to follow"),
    "lilianweng.github.io": ("no terms", "", "No terms page linked from the site"),
    "metr.org": ("no terms", "", "No terms page linked from the site"),
    # --- Infra & climate ---
    "www.datacenterknowledge.com": ("terms read", "https://www.informatechtarget.com/terms-and-conditions",
                                    "Nothing on feeds, robots or personal use"),
    "w.media": ("terms read", "https://w.media/terms-conditions/", "Nothing on feeds, robots or personal use"),
    "www.carbonbrief.org": ("licence", "https://creativecommons.org/licenses/by-nc-nd/4.0/",
                            "Creative Commons Attribution-NonCommercial-NoDerivatives 4.0"),
    "www.climatechangenews.com": ("terms read", "https://www.climatechangenews.com/terms-of-use/",
                                  "Nothing on feeds, robots or personal use"),
    "news.mongabay.com": ("licence", "https://www.mongabay.com/terms",
                          "'You may republish Mongabay content in your publication at no cost'"),
    "theconversation.com": ("licence", "https://theconversation.com/global/republishing-guidelines",
                            "Creative Commons Attribution/No derivatives"),
    "www.canarymedia.com": ("no terms", "", "No terms page linked from the site"),
    "www.powermag.com": ("terms read", "https://www.powermag.com/privacy-policy-terms-conditions/",
                         "Nothing on feeds, robots or personal use"),
    "blog.ucsusa.org": ("no terms", "", "Only a privacy policy; no terms page"),
    "www.selc.org": ("no terms", "", "Only a privacy page; no terms page"),
    "www.foodandwaterwatch.org": ("terms read", "https://www.foodandwaterwatch.org/learn/legal/",
                                  "Nothing on feeds, robots or personal use"),
    "energyinnovation.org": ("licence", "https://energyinnovation.org/legal/", "'All research licensed under CC BY 4.0'"),
    "www.greenpeace.org": ("licence", "https://www.greenpeace.org/international/copyright/",
                           "'Greenpeace International encourages the reproduction and distribution of our materials'; "
                           "credit given"),
    "globalenergymonitor.org": ("no terms", "", "No terms page linked from the site"),
    "datacenterpost.com": ("no terms", "", "No terms page linked from the site"),
    "www.techerati.com": ("no terms", "", "Only a privacy policy, which says nothing on feeds or robots"),
    "dcnnmagazine.com": ("no terms", "", "Only its publisher's privacy policy, which says nothing on feeds or robots"),
    "africadca.org": ("no terms", "", "No terms page linked from the site"),
    "www.gov.uk": ("official", "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
                   "Open Government Licence v3.0; GOV.UK offers its content through feeds for other sites"),
    "www.eia.gov": ("official", "https://www.eia.gov/about/copyrights_reuse.php", "US government work, public domain"),
    "energy.ec.europa.eu": ("official", "https://commission.europa.eu/legal-notice_en",
                            "European Commission: reuse allowed with acknowledgement"),
    # --- Policy ---
    "artificialintelligenceact.eu": ("no terms", "", "No terms page linked from the site"),
    "cset.georgetown.edu": ("terms read", "https://cset.georgetown.edu/policies/", "Nothing on feeds, robots or personal use"),
    "ainowinstitute.org": ("no terms", "", "No terms page linked from the site"),
    "futureoflife.org": ("no terms", "", "No terms page linked from the site"),
    "www.eff.org": ("licence", "https://www.eff.org/copyright", "Creative Commons Attribution for EFF's own material"),
    "epic.org": ("no terms", "", "Only a privacy page is linked; no terms page"),
    "partnershiponai.org": ("no terms", "", "Only a privacy policy; no terms page"),
    "smartafrica.org": ("terms read", "https://smartafrica.org/terms-and-conditions/", "Nothing on feeds, robots or personal use"),
    "www.ntia.gov": ("official", "https://www.ntia.gov/page/web-policies", "US government work, public domain"),
    "www.cisa.gov": ("official", "https://www.cisa.gov/about/policies-plans", "US government work, public domain"),
    "cltc.berkeley.edu": ("no terms", "", "No terms page linked from the site"),
    "www.itu.int": ("official", "https://www.itu.int/en/about/Pages/terms-of-use.aspx",
                    "Personal, educational or non-commercial use with the source acknowledged"),
    "www.nist.gov": ("official", "https://www.nist.gov/copyrights-disclaimers", "US government work, public domain"),
    "www.darpa.mil": ("official", "https://www.darpa.mil/policies/usage-policy", "US government work, public domain"),
    "www.nsf.gov": ("official", "https://www.nsf.gov/policies", "US government work, public domain"),
    "www.aisi.gov.uk": ("official", "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
                        "Open Government Licence v3.0"),
    "www.federalregister.gov": ("official", "https://www.federalregister.gov/reader-aids/developer-resources",
                                "US government work, public domain; public API"),
    "www.msit.go.kr": ("official", "", "Korean government press releases; no robots.txt or terms restrict them"),
    "www.digital.gov.my": ("official", "", "Malaysian government media releases; no robots.txt or terms restrict them"),
    "duma.gov.ru": ("official", "", "State Duma English news; no terms restrict the news list"),
    "api.io.canada.ca": ("official", "https://www.canada.ca/en/transparency/terms.html",
                         "Non-commercial reproduction with credit"),
    "www.edpb.europa.eu": ("official", "https://www.edpb.europa.eu/copyright_en",
                           "'The reuse of any information of this website is authorized for commercial and "
                           "non-commercial purposes'"),
    "digital-strategy.ec.europa.eu": ("official", "https://commission.europa.eu/legal-notice_en",
                                      "European Commission: reuse allowed with acknowledgement"),
    # --- Research ---
    "rss.arxiv.org": ("licence", "https://info.arxiv.org/help/api/tou.html",
                      "arXiv's terms for its feeds and API; metadata is CC0"),
    "huggingface.co": ("terms read", "https://huggingface.co/terms-of-service",
                       "Daily Papers is a public API listing others' papers (arXiv), not Hugging Face's own material"),
}

# Everything else the platform reads or shows: the regulation tracker's official records (bills.py, oecd.py,
# incidents.py), and the icons, photos, fonts and data it uses. Same kinds; "owner's choice" marks a risk the
# project owner accepted knowingly (7 Oct 2026). The audit reads these terms pages too.
PLATFORM: dict[str, tuple[str, str, str]] = {
    "api.congress.gov": ("official", "https://www.loc.gov/legal/", "Official API with the project's own free key; public domain"),
    "data.europarl.europa.eu": ("official", "https://www.europarl.europa.eu/legal-notice/en", "Reuse with acknowledgement"),
    "oeil.secure.europarl.europa.eu": ("official", "https://www.europarl.europa.eu/legal-notice/en", "Reuse with acknowledgement"),
    "bills-api.parliament.uk": ("official", "", "Open Parliament Licence v3.0 (its page is closed to robots)"),
    "gazette.gc.ca": ("official", "https://www.canada.ca/en/transparency/terms.html", "Non-commercial reproduction with credit"),
    "dadosabertos.camara.leg.br": ("official", "https://dadosabertos.camara.leg.br/", "Open data"),
    "api.prod.legislation.gov.au": ("official", "https://www.legislation.gov.au/", "CC BY 4.0"),
    "www.cac.gov.cn": ("official", "", "Title, date and link only; regulations aren't copyrighted"),
    "sansad.in": ("official", "", "Public API; no terms restrict automated use"),
    "laws.e-gov.go.jp": ("official", "https://www.digital.go.jp/en/copyright-policy",
                         "Government of Japan Standard Terms of Use 2.0; credit and machine translation marked"),
    "www.law.go.kr": ("official", "", "robots.txt allows; laws aren't copyrighted"),
    "lis.ly.gov.tw": ("official", "", "No robots.txt rules; laws aren't copyrighted"),
    "law.moj.gov.tw": ("official", "", "Laws aren't copyrighted"),
    "www.parlimen.gov.my": ("official", "", "No robots.txt rules or restricting terms"),
    "vbpl.vn": ("official", "", "robots.txt allows; legal documents aren't copyrighted"),
    "ws.parlament.ch": ("official", "", "Swiss Parliament open data: open use with the source named"),
    "api.oireachtas.ie": ("official", "https://www.oireachtas.ie/en/open-data/license/", "Oireachtas (Open Data) PSI Licence, CC BY 4.0"),
    "data.stortinget.no": ("official", "https://data.stortinget.no/", "Norwegian Licence for Open Government Data, credited"),
    "api.oecdai.org": ("licence", "https://oecd.ai/en/terms", "OECD.AI data, CC BY 4.0"),
    "incidentdatabase.ai": ("licence", "https://incidentdatabase.ai/terms-of-use/",
                            "Incident data CC BY-SA 4.0; only 'high-volume' bots are banned, and we read it once per run"),
    "www.wikidata.org": ("licence", "https://www.wikidata.org/wiki/Wikidata:Licensing", "CC0; its API allows programmatic use"),
    "cdn.jsdelivr.net": ("licence", "https://www.jsdelivr.com/terms", "Serves Simple Icons (CC0) for brand logos"),
    "commons.wikimedia.org": ("licence", "https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia",
                              "84 photos, each CC0, public domain, CC BY or CC BY-SA, credited on photos/credits.html"),
    "imgflip.com": ("owner's choice", "", "Meme templates (copyrighted pictures) used as parody and commentary on a "
                    "non-commercial site; kept by the owner's decision of 7 Oct 2026"),
    "generativelanguage.googleapis.com": ("owner's choice", "https://ai.google.dev/gemini-api/terms",
                                          "Gemini free tier for meme captions; its terms ask for paid use when an app "
                                          "is offered to EU/UK users: we read it as a background job, not an app"),
}
