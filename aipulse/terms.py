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
    "blog.character.ai": ("unconfirmed", "https://character.ai/tos", "The terms page shows only with JavaScript"),
    "www.minimax.io": ("unconfirmed", "https://www.minimax.io/terms-of-service",
                       "The terms page shows only with JavaScript"),
    "docs.x.ai": ("unconfirmed", "https://x.ai/legal/terms-of-service", "The terms page refuses automated readers (403)"),
    # --- Industry news ---
    "techcrunch.com": ("feed terms", "https://techcrunch.com/rss-terms-of-use/",
                       "RSS terms: display the feed's content with attribution and a link; may not modify it"),
    "the-decoder.com": ("terms read", "https://the-decoder.com/tos", "Nothing on feeds, robots or personal use"),
    "siliconangle.com": ("terms read", "https://siliconangle.com/terms-of-use/",
                         "No republishing 'unless content is specifically made for redistribution'; its RSS feed is"),
    "www.marktechpost.com": ("unconfirmed", "https://www.marktechpost.com/terms-and-conditions/",
                             "The terms page refuses automated readers (403)"),
    "www.404media.co": ("no terms", "", "No terms page linked from the site"),
    "www.engadget.com": ("feed terms", "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html",
                         "Yahoo RSS terms: display the feed's content unmodified, with attribution and a link"),
    "news.mit.edu": ("licence", "https://news.mit.edu/terms-of-use", "Allows republishing MIT News stories with credit"),
    "www.sciencedaily.com": ("feed terms", "https://www.sciencedaily.com/terms.htm",
                             "RSS terms encourage use on other sites, unmodified, with attribution; about 40 stored "
                             "headlines at most"),
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
    "epic.org": ("unconfirmed", "https://epic.org/terms-of-use/", "The terms page refuses automated readers (403)"),
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
