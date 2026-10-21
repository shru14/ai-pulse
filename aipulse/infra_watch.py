"""Infra's three features, each a table checked by hand against the stories that reported it:
Data-centre builds (data-centre-builds/): new data centres, who is behind each, where, how big and how far along;
Who powers AI (who-powers-ai/): deals to power data centres, and what the power comes from;
Pushback & permits (pushback-and-permits/): decisions to approve, pause or block data centres, and who made them.
Each row is the story's URL and what it says, in short; its date comes from the story. Sizes and money are as each story
gives them, never added up. `python -m aipulse infra` lists the stories from after CHECKED_TO not checked yet, to add
to one of the tables or to LEFT_OUT. Linked from Infra's strip on the front page.
"""
from __future__ import annotations

import re
from datetime import date
from html import escape
from pathlib import Path

from . import pages, rss

# the newest day every Infra story was read for these tables; the candidates start after it
CHECKED_TO = "2026-10-15"

# how far along a project is, as its story says: (its words on the page, its colour: Okabe-Ito, dark text on it)
STAGES = {
    "announced": ("Announced", "#56B4E9"),
    "building": ("Building", "#E69F00"),
    "open": ("Opened", "#009E73"),
    "dropped": ("Dropped", "#9AA0AA"),
}
# what the power comes from, as the story names it
SOURCES = {
    "nuclear": ("Nuclear", "#CC79A7"),
    "gas": ("Gas", "#E69F00"),
    "renewable": ("Solar, wind & renewables", "#F0E442"),
    "hydrogen": ("Fuel cells & hydrogen", "#56B4E9"),
    "utility": ("From a utility", "#B9C0CA"),
    "notstated": ("Not stated", "#E3E5E8"),
}
STATUSES = {"signed": "Signed", "planned": "Planned or in talks", "dropped": "Dropped"}
# what a decision did to data centres
OUTCOMES = {
    "approved": ("Approved", "#009E73"),
    "paused": ("Paused", "#E69F00"),
    "blocked": ("Blocked", "#F85C48"),
    "limits": ("New limits", "#CC79A7"),
    "review": ("More review ordered", "#56B4E9"),
    "refused": ("Pause turned down", "#9AA0AA"),
}

# Checked 15 Oct 2026 against each story's headline and summary, every Infra story from 15 Jul 2026 read.
# Builds: a new data centre or campus whose story names who is behind it, where, and its size or cost.
# (story, who, country, place, size, money, stage)
BUILDS: list[tuple[str, ...]] = [
    ("https://w.media/macquarie-data-centres-acquires-aud-240m-sydney-site-for-planned-200mw-ai-campus/", "Macquarie Data Centres", "Australia", "Macquarie Park, Sydney", "200 MW", "AUD 240m for the site", "announced"),
    ("https://w.media/verrus-eyes-us-5-1-billion-data-center-campus-in-salem-oregon/", "Verrus", "US", "Salem, Oregon", "", "US$ 5.1bn, the city's estimate", "announced"),
    ("https://w.media/us-government-picks-savannah-river-site-for-1-gw-ai-data-center/", "US Department of Energy (NNSA)", "US", "Savannah River Site", "1 GW", "", "announced"),
    ("https://w.media/yit-and-atnorth-to-build-us-343-million-data-center-in-finland/", "YIT and atNorth", "Finland", "Myllykoski, Kouvola", "", "US$ 343m", "announced"),
    ("https://www.techerati.com/news-hub/polar-announces-40mw-ai-ready-expansion-at-norway-data-centre-campus/", "Polar Data Centers", "Norway", "Drangedal", "40 MW", "", "announced"),
    ("https://w.media/openai-plans-to-build-its-own-3-2-gw-data-center-campus-in-georgia/", "OpenAI", "US", "Effingham County, Georgia", "3.2 GW", "", "announced"),
    ("https://w.media/naver-brookfield-and-nvidia-expand-south-korea-ai-infrastructure-project-to-200-mw/", "NAVER, Brookfield and NVIDIA", "South Korea", "", "200 MW, up from 55 MW", "", "announced"),
    ("https://w.media/rubix-data-centers-to-develop-us-1-14-billion-ai-data-center-in-catalonia/", "Rubix Data Centers", "Spain", "Flix, Catalonia", "", "US$ 1.14bn", "announced"),
    ("https://w.media/nebius-contemplating-1-2-gw-data-center-campus-in-pennsylvania/", "Nebius", "US", "Schuylkill County, Pennsylvania", "1.2 GW", "", "announced"),
    ("https://w.media/meta-hands-blackrock-majority-stake-in-1-gw-el-paso-data-center/", "Meta, with BlackRock", "US", "El Paso, Texas", "1 GW", "US$ 14bn", "announced"),
    ("https://w.media/us-doe-partners-with-brookfield-nextera-on-us-100-billion-ai-data-center-campus/", "US Department of Energy, Brookfield and NextEra", "US", "", "", "US$ 100bn", "announced"),
    ("https://w.media/thailands-true-idc-seeks-us-2-billion-loan-to-build-new-data-center/", "True IDC", "Thailand", "Near Bangkok", "", "US$ 2bn loan sought", "announced"),
    ("https://w.media/powerplay-ai-plans-400-mw-west-texas-ai-data-center/", "PowerPlay AI", "US", "Abilene area, West Texas", "400 MW", "", "announced"),
    ("https://w.media/shi-and-m3-sign-agreement-to-build-50-mw-floating-data-center-in-the-us/", "Samsung Heavy Industries and M3", "US", "Floating, at sea", "50 MW", "", "announced"),
    ("https://w.media/yondr-and-cerberus-partner-on-72-mw-northern-virginia-data-center-project/", "Yondr and Cerberus", "US", "Manassas, Virginia", "72 MW", "", "announced"),
    ("https://w.media/sunway-construction-bags-us-250-million-data-center-job-in-johor/", "Sunway Construction, builder", "Malaysia", "Johor", "", "US$ 250m contract", "announced"),
    ("https://w.media/coreweave-debuts-in-indonesia-with-360mw-across-three-data-centers/", "CoreWeave", "Indonesia", "Three sites", "360 MW", "", "announced"),
    ("https://w.media/gamuda-scores-us-420-million-hyperscale-buildout-job-its-second-in-port-dickson-malaysia/", "Gamuda, builder", "Malaysia", "Port Dickson", "", "US$ 420m contract", "announced"),
    ("https://w.media/envision-commissions-2-gw-ai-infrastructure-campus-in-inner-mongolia/", "Envision Energy", "China", "Ulanqab, Inner Mongolia", "2 GW", "", "open"),
    ("https://w.media/firebird-launches-ai-factory-in-armenia-with-300-mw-expansion-plans/", "Firebird", "Armenia", "", "300 MW planned in all", "", "open"),
    ("https://w.media/indosat-ooredoo-nokia-nvidia-partner-to-build-1gw-ai-factory-in-indonesia/", "Indosat, Ooredoo, Nokia and NVIDIA", "Indonesia", "", "1 GW", "", "announced"),
    ("https://w.media/kazakhstans-data-center-valley-on-track-to-complete-first-50-mw-facility-in-june-2027/", "Government of Kazakhstan", "Kazakhstan", "Ekibastuz", "50 MW first building", "", "building"),
    ("https://w.media/kio-data-centers-considering-100-mw-expansion-in-mexico/", "KIO Data Centers", "Mexico", "", "100 MW", "", "announced"),
    ("https://w.media/nvidia-openai-and-sb-energy-plan-4-25-gw-ai-data-center-campus-in-ohio/", "NVIDIA, OpenAI and SB Energy", "US", "Ohio", "4.25 GW", "", "announced"),
    ("https://w.media/infratech-capital-assembles-consortium-for-us-2-7-billion-data-center-campus-in-texas/", "InfraTech Capital", "US", "Carson County, Texas", "", "US$ 2.7bn", "announced"),
    ("https://w.media/dayone-buys-us-152-8-million-sepang-land-in-malaysia-to-build-data-center/", "DayOne", "Malaysia", "Sepang", "", "US$ 152.8m for the land", "announced"),
    ("https://w.media/ytl-power-and-jland-to-partner-to-build-up-to-1-5gw-data-center-in-johor/", "YTL Power and JLand", "Malaysia", "Johor", "Up to 1.5 GW", "", "announced"),
    ("https://w.media/amazon-adds-us-6-billion-to-northwest-louisiana-with-a-3rd-data-center-plan/", "Amazon Web Services", "US", "Northwest Louisiana", "", "US$ 6bn more, US$ 18bn in all", "announced"),
    ("https://w.media/amaco-seeks-approval-for-us-1-5-billion-off-grid-ai-data-center-in-kenya/", "AMACO Energy Group", "Kenya", "Mombasa", "", "US$ 1.5bn", "announced"),
    ("https://w.media/terranova-starts-construction-on-us-500-million-data-center-campus-in-brazil/", "Terranova", "Brazil", "Campinas", "", "US$ 500m", "building"),
    ("https://w.media/zerra-plans-1-44gw-aud-14-5bn-data-centre-campus-in-queensland/", "Zerra DC", "Australia", "Western Downs, Queensland", "1.44 GW", "AUD 14.5bn", "announced"),
    ("https://w.media/whittlesea-seeks-greater-oversight-as-dover-plans-200mw-victorian-facility/", "Dover", "Australia", "Whittlesea, Victoria", "200 MW", "", "announced"),
    ("https://w.media/gateway-considers-81mw-data-centre-at-sydneys-st-leonards/", "Gateway Capital", "Australia", "St Leonards, Sydney", "81 MW", "AUD 1bn", "announced"),
    ("https://w.media/evolution-leases-50000-sqm-land-to-build-52mw-data-center-in-ho-chi-minh-city/", "Evolution Data Centres", "Vietnam", "Saigon High-Tech Park, Ho Chi Minh City", "52 MW", "", "announced"),
    ("https://dcnnmagazine.com/business/real-estate/yamna-reserves-land-for-250mw-brazil-data-centre/", "Yamna", "Brazil", "Port of Açu", "250 MW", "", "announced"),
    ("https://w.media/cerebras-and-compute-nordic-finland-announce-new-165-mw-ai-data-center-in-mikkeli/", "Cerebras and Compute Nordic", "Finland", "Mikkeli", "165 MW", "", "announced"),
    ("https://dcnnmagazine.com/build/projects/pure-dc-begins-final-build-phase-of-90mw-lon01-campus/", "Pure DC", "UK", "Brent Cross, London", "90 MW", "£1bn", "building"),
    ("https://w.media/hypervault-secures-264-acres-for-1gw-ai-data-center-campus-in-hyderabad/", "HyperVault (Tata Consultancy Services)", "India", "Hyderabad, Telangana", "1 GW", "", "announced"),
    ("https://w.media/key-asic-and-ct-vision-ink-mou-to-build-300mw-green-ai-data-center-in-malaysia/", "Key ASIC and CT Vision", "Malaysia", "", "300 MW", "", "announced"),
    ("https://w.media/greenfield-and-finsbury-infrastructure-plan-36-mw-data-center-near-milan/", "Greenfield and Finsbury Infrastructure", "Italy", "East of Milan", "36 MW", "", "announced"),
    ("https://w.media/northampton-capital-and-provident-data-centers-form-jv-to-develop-54-mw-capacity-in-texas/", "Northampton Capital and Provident Data Centers", "US", "North Dallas, Texas", "54 MW", "", "announced"),
    ("https://w.media/egyptian-data-center-venture-targets-us-1-billion-investment-for-200-mw-buildout/", "Vodafone Business, Elsewedy Electric and Cassava", "Egypt", "", "200 MW", "US$ 1bn", "announced"),
    ("https://w.media/digital-realty-expands-kenyan-campus-with-6-2-mw-data-center/", "Digital Realty", "Kenya", "Nairobi", "6.2 MW", "", "open"),
    ("https://w.media/sb-gruppe-building-12-mw-nimb-data-center-in-bucharest-metro/", "S+B Gruppe", "Romania", "Bucharest", "12 MW", "", "building"),
    ("https://w.media/fortune-hospitality-infra-plans-us-6-2-billion-hyperscale-data-center-park-in-telangana/", "Fortune Hospitality & Infra", "India", "Near Hyderabad, Telangana", "Up to 1.6 GW", "US$ 6.2bn", "announced"),
    ("https://w.media/bell-canada-plots-path-to-1-2-gw-canadian-ai-hub-in-saskatchewan/", "Bell Canada", "Canada", "Saskatchewan", "Up to 900 MW more", "", "announced"),
    ("https://w.media/crypto-firm-sos-inks-indonesian-deal-to-build-500mw-ai-data-center/", "SOS Limited", "Indonesia", "", "500 MW", "", "announced"),
    ("https://w.media/airtrunk-proposes-aud-3-7bn-nsw-data-centre-with-aud-37m-community-offer/", "AirTrunk", "Australia", "Hunter region, New South Wales", "540 MW", "AUD 3.7bn", "announced"),
    ("https://www.techerati.com/news-hub/civo-launches-first-of-40-uk-edge-data-centres-in-1gw-ai-infrastructure-plan/", "Civo", "UK", "40 edge sites", "1 GW across all", "", "open"),
    ("https://w.media/cdc-plans-aud-15bn-1-4gw-data-centre-campus-near-wagga-wagga/", "CDC Data Centres", "Australia", "Near Wagga Wagga, New South Wales", "Up to 1.4 GW", "AUD 15bn", "announced"),
    ("https://w.media/bdx-breaks-ground-on-ai-data-center-in-west-java-first-120mw-building-to-be-ready-by-early-2027/", "BDx Data Centers", "Indonesia", "Jatiluhur, West Java", "120 MW first, up to 640 MW", "", "building"),
    ("https://w.media/egypts-intro-group-to-invest-us-270-million-in-80-mw-kemet-data-center/", "Intro Group", "Egypt", "", "80 MW", "US$ 270m", "announced"),
    ("https://w.media/zone-frontier-leases-land-for-up-to-500-mw-texas-data-center-campus/", "Zone Frontier", "US", "Potter County, Texas", "Up to 500 MW", "", "announced"),
    ("https://w.media/amazon-buys-2-million-sq-ft-land-in-selangor-malaysia-to-build-data-center/", "Amazon", "Malaysia", "Sepang, Selangor", "", "US$ 77.7m for the land", "announced"),
    ("https://dcnnmagazine.com/build/projects/atnorth-to-develop-230mw-data-centre-in-finland/", "atNorth", "Finland", "Salo", "75 MW first, up to 230 MW", "", "announced"),
    ("https://w.media/dayone-plans-200mw-data-center-in-japans-imari-city/", "DayOne", "Japan", "Imari City, Saga", "200 MW", "", "announced"),
    ("https://w.media/digital-realty-breaks-ground-on-24-mw-kix15-data-center-in-osaka/", "Digital Realty", "Japan", "Ibaraki City, Osaka", "24 MW", "", "building"),
    ("https://w.media/trentar-signs-mou-for-us-3-3-billion-500-mw-data-center-in-maharashtra/", "Trentar", "India", "Maharashtra", "500 MW", "US$ 3.3bn", "announced"),
    ("https://w.media/applied-digital-plans-a-1-gw-ai-campus-in-finland/", "Applied Digital", "Finland", "", "1 GW", "", "announced"),
    ("https://w.media/fivenines-group-joins-us-1-2-billion-nexus-ai-factory-project-in-morocco/", "FiveNines and Nexus Core Systems", "Morocco", "Near Casablanca", "20 MW", "US$ 1.2bn", "announced"),
    ("https://w.media/sesterce-plans-e-10-billion-ai-campus-in-finland/", "Sesterce", "Finland", "Jämsä", "", "€10bn", "announced"),
    ("https://www.datacenterknowledge.com/ai-data-centers/thisway-global-to-convert-bankrupt-rellis-site-into-73-mw-ai-hub", "ThisWay Global", "US", "Texas A&M RELLIS Campus", "73 MW", "", "announced"),
    ("https://w.media/renew-wind-energy-signs-mou-with-maharashtra-govt-for-us-7-3-billion-green-dc-park/", "ReNew", "India", "Maharashtra", "", "US$ 7.3bn", "announced"),
    ("https://w.media/ntt-data-in-talks-with-anthropic-to-build-us-6-3-billion-data-center-in-osaka/", "NTT Data, in talks with Anthropic", "Japan", "Osaka", "", "US$ 6.3bn", "announced"),
    ("https://w.media/iren-plans-900mw-data-centre-campus-near-wagga-wagga/", "IREN", "Australia", "Near Wagga Wagga, New South Wales", "900 MW", "Over AUD 10bn", "announced"),
    ("https://w.media/ctrls-to-invest-us1-billion-in-bihar-to-set-up-hyperscale-ai-infrastructure/", "CtrlS Datacenters", "India", "Bodh Gaya, Bihar", "150 MW", "US$ 1bn", "announced"),
    ("https://w.media/brightray-enters-us-with-loi-for-10-mw-ai-data-center-in-indiana/", "Brightray", "US", "Indiana", "10 MW", "", "announced"),
    ("https://w.media/uruguay-signs-multi-billion-dollar-deal-for-500-mw-data-center-park/", "Solaria, with Uruguay's government", "Uruguay", "", "500 MW", "US$ 5.7bn", "announced"),
    ("https://dcnnmagazine.com/projects-and-infrastructure/1-3gw-solar-farm-and-1gw-data-centre-proposed-in-norfolk/", "EPL Norfolk (Evolution Power)", "UK", "King's Lynn, west Norfolk", "1 GW", "", "announced"),
    ("https://w.media/canadian-government-eyes-up-to-us-1-3-billion-for-60-mw-data-center/", "Defence Construction Canada, for the Communications Security Establishment", "Canada", "Ottawa, Ontario", "60 MW", "CA$ 1.5-1.85bn, estimated", "announced"),    ("https://w.media/everwind-plans-us-7-billion-nova-scotia-data-center-campus-with-anthropic-as-tenant/", "EverWind, with Anthropic as tenant", "Canada", "Point Tupper, Richmond County, Nova Scotia", "95 MW first, 420 MW by 2028", "Over CA$ 8bn for the campus", "announced"),
    ("https://w.media/digital-realty-breaks-ground-on-22-mw-ankara-data-center/", "Digital Realty and Rönesans Infrastructure", "Türkiye", "Ankara", "22 MW", "", "building"),

]

# Power: a deal or plan to power data centres. (story, who, power from, what it powers, size, status)
POWER: list[tuple[str, ...]] = [
    ("https://dcnnmagazine.com/infrastructure/power-cooling/powercell-wins-hydrogen-power-order-for-ai-data-centre/", "PowerCell, for ECL", "hydrogen", "Hydrogen fuel cells for an AI data centre", "", "signed"),
    ("https://www.powermag.com/terra-innovatum-waiken-ilw-will-deploy-microreactors-for-data-center-infrastructure/", "Terra Innovatum and Waiken ILW", "nuclear", "Microreactors for data centres in Latin America and Brazil", "", "planned"),
    ("https://the-decoder.com/openais-project-camellia-in-georgia-secures-a-massive-3-2-gigawatt-power-deal-through-2032/", "Georgia Power, for OpenAI", "utility", "OpenAI's Project Camellia, Georgia, US, to 2032", "3.2 GW", "signed"),
    ("https://www.powermag.com/aalo-crusoe-plan-2027-inl-demonstration-pairing-nuclear-power-and-ai-data-center-load/", "Aalo Atomics and Crusoe", "nuclear", "A reactor beside an AI data centre at Idaho National Laboratory, US, from 2027", "", "planned"),
    ("https://w.media/ntt-data-to-source-renewable-energy-from-engie-in-europe/", "ENGIE, for NTT DATA", "renewable", "NTT DATA's data centres in Europe", "", "signed"),
    ("https://w.media/eskom-looks-to-hyperscalers-to-soak-up-south-africas-6-gw-power-surplus/", "Eskom", "utility", "Spare power offered to Amazon, Google, Microsoft and others, South Africa", "Up to 6 GW", "planned"),
    ("https://w.media/engie-signs-48-mwac-ppa-with-qts-to-power-irving-data-center-campus/", "ENGIE, for QTS", "notstated", "QTS's campus in Irving, Texas, US", "48 MW", "signed"),
    ("https://w.media/nano-nuclear-and-tillman-global-holdings-plan-potential-multi-gw-nuclear-deployment/", "NANO Nuclear and Tillman Global", "nuclear", "Tillman's data-centre platform; a non-binding framework", "Several GW", "planned"),
    ("https://www.powermag.com/one-nuclear-signs-deal-for-2-88-gw-gas-fired-plant-large-bess-for-louisiana-data-center-campus/", "ONE Nuclear Energy", "gas", "A gas plant and batteries for a data-centre campus in Louisiana, US", "2.88 GW", "signed"),
    ("https://w.media/dayone-tnb-to-explore-onsite-power-up-to-1-5gw-for-greater-kuala-lumpur-data-center/", "Tenaga Nasional (TNB), for DayOne", "notstated", "Power made on site for DayOne's campus near Kuala Lumpur, Malaysia", "Up to 1.5 GW", "planned"),
    ("https://w.media/oracle-signs-renewable-power-agreements-with-engie-for-its-texas-operations/", "ENGIE, for Oracle", "renewable", "Oracle's operations in Texas, US", "", "signed"),
    ("https://w.media/woodway-to-build-22-mile-gas-pipeline-for-behind-the-meter-data-center-project/", "Woodway Energy Infrastructure", "gas", "A 22-mile gas pipeline to a hyperscale data centre, US", "", "signed"),
    ("https://techcrunch.com/2026/09/25/crusoe-abandons-1-25b-plan-to-use-boom-turbines-at-ai-data-centers/", "Crusoe and Boom Supersonic", "notstated", "Boom's turbines at Crusoe's AI data centres, a US$ 1.25bn plan", "", "dropped"),
    ("https://w.media/hydro-weighs-444mw-firmus-load-as-tasmania-nears-energy-balance/", "Hydro Tasmania, for Firmus", "utility", "Firmus's AI data centres in Tasmania, Australia", "444 MW", "planned"),
    ("https://w.media/us-tech-firm-inks-deal-with-malaysian-consortium-for-proposed-680mw-solar-plus-storage-project-to-power-data-center/", "A Malaysian group, for a US tech company it doesn't name", "renewable", "Solar and batteries for a data centre in Malaysia", "680 MW", "signed"),
    ("https://www.powermag.com/fit-energy-will-use-gas-powered-fuel-cells-for-pennsylvania-data-center-project/", "Fit Energy", "gas", "Gas-powered fuel cells for a data centre in Luzerne County, Pennsylvania, US", "", "planned"),
    ("https://w.media/black-hills-lines-up-2-7-gw-of-power-for-googles-planned-wyoming-data-center/", "Black Hills Corp, for Google", "utility", "Google's data centre in Cheyenne, Wyoming, US, to 2048", "2.7 GW", "signed"),
    ("https://www.thelec.net/news/articleView.html?idxno=14464", "HD Hyundai Infracore, for ERock", "gas", "Gas generator engines at data centres in the US, a 390 billion won order", "", "signed"),
    ("https://www.thelec.net/news/articleView.html?idxno=14499", "SK Eternix and Mastern", "hydrogen", "A data centre run on fuel cells, South Korea", "", "planned"),
    ("https://www.xataka.com/energia/google-se-asegura-20-anos-energia-nuclear-para-alimentar-sus-centros-datos", "Google", "nuclear", "Google's data centres, for 20 years", "", "signed"),
    ("https://w.media/tata-power-announces-us-1-5-billion-mumbai-grid-expansion-for-data-centers/", "Tata Power", "utility", "A US$ 1.5bn grid expansion for data centres in Mumbai, India", "", "planned"),    ("https://www.xataka.com/empresas-y-economia/amazon-ha-encontrado-solucion-al-colosal-consumo-sus-centros-datos-para-ia-12-reactores-nucleares-smr-antigua-central-carbon", "Amazon, X-energy and AEP", "nuclear", "12 small reactors at the former Breed coal plant site, Sullivan County, Indiana, US; Amazon would help fund it and be the first customer", "About 960 MW", "planned"),

]

# Decisions on data centres by governments, councils, courts and grid operators; calls, protests and proposals aren't
# decisions. (story, country, place, who decided, what, outcome)
DECISIONS: list[tuple[str, ...]] = [
    ("https://w.media/cape-town-tribunal-approves-land-rezoning-for-two-equinix-data-centers/", "South Africa", "Cape Town", "City of Cape Town planning tribunal", "Rezoned land for two Equinix data centres", "approved"),
    ("https://www.techerati.com/news-hub/new-york-launches-first-statewide-hyperscale-data-centre-pause/", "US", "New York State", "New York State", "Paused environmental permits for new hyperscale data centres, the first statewide pause in the US", "paused"),
    ("https://w.media/nsw-approves-goodmans-aud-1-1bn-project-pluto-data-centre-in-western-sydney/", "Australia", "Western Sydney", "New South Wales planning department", "Approved Goodman's 68 MW Project Pluto", "approved"),
    ("https://dcnnmagazine.com/operations/hyperscale/croatia-approves-power-infrastructure-for-1gw-ai-data-centre/", "Croatia", "Topusko", "HOPS, the national grid operator", "Approved the power plan for Pantheon AI's 1 GW campus", "approved"),
    ("https://www.foodandwaterwatch.org/2026/07/28/montgomery-county-md-unanimously-passes-18-month-moratorium-on-hyperscale-data-centers/", "US", "Montgomery County, Maryland", "County Council", "An 18-month moratorium on new data centres, passed unanimously", "paused"),
    ("https://www.gov.uk/government/publications/ox11-7bf-amazon-data-services-uk-limited-environmental-permit-issued-eprgp3127lva001", "UK", "Didcot", "UK environmental permit", "Issued Amazon's permit for its Didcot North campus", "approved"),
    ("https://www.foodandwaterwatch.org/2026/08/06/allentown-pa-council-passes-restrictive-data-center-amendments/", "US", "Allentown, Pennsylvania", "City Council", "Passed amendments restricting data centres", "limits"),
    ("https://www.foodandwaterwatch.org/2026/08/25/new-mexico-supreme-court-pauses-air-permit-hearing-for-project-jupiter-ai-hyperscale-data-center/", "US", "New Mexico", "New Mexico Supreme Court", "Paused the air-permit hearing for the Project Jupiter data centre", "paused"),
    ("https://w.media/firmus-secures-approval-for-288mw-bell-bay-ai-factory/", "Australia", "Bell Bay, Tasmania", "Not named in the story", "Planning approval for Firmus's 288 MW AI factory", "approved"),
    ("https://www.foodandwaterwatch.org/2026/08/26/orangetown-passes-six-month-moratorium-on-new-data-centers-exempting-existing-databank-expansion-proposal/", "US", "Orangetown, New York", "Town of Orangetown", "A six-month moratorium on new data centres; an expansion already proposed is exempt", "paused"),
    ("https://www.datacenterknowledge.com/data-center-construction/california-judge-orders-full-environmental-review-of-330-mw-data-center", "US", "Imperial County, California", "A California judge", "Ordered a full environmental review of a proposed 330 MW data centre", "review"),
    ("https://w.media/goodman-wins-approval-for-135mw-macquarie-park-data-centre/", "Australia", "Macquarie Park, Sydney", "Not named in the story", "Approved Goodman's 135 MW data centre", "approved"),
    ("https://www.techerati.com/news-hub/uk-pm-rejects-call-for-data-centre-moratorium-amid-community-concerns/", "UK", "Whole country", "Prime Minister Andy Burnham", "Turned down a call to pause data-centre approvals", "refused"),
    ("https://w.media/amazon-receives-approval-for-aud-2-17bn-sydney-data-centre/", "Australia", "Western Sydney", "Not named in the story", "Approved Amazon's 235 MW, AUD 2.17bn data centre", "approved"),
    ("https://w.media/cdc-wins-approval-for-au203-5m-beard-2-data-centre-in-canberra/", "Australia", "Canberra", "Not named in the story", "Approved, with conditions, CDC's 84 MW Beard 2 data centre", "approved"),
    ("https://www.techerati.com/news-hub/aws-wins-approval-for-iver-data-centre-despite-environmental-concerns/", "UK", "Iver, Buckinghamshire", "Not named in the story", "Planning permission for an AWS data centre", "approved"),
    ("https://w.media/indonesia-pauses-bdx-data-centers-construction-pending-required-permits-and-eia-report/", "Indonesia", "Jakarta", "Not named in the story", "Ordered BDx to stop building until it has permits and an environmental study", "paused"),
    ("https://w.media/google-gets-approval-for-data-center-expansion-in-south-dublin/", "Ireland", "South Dublin", "Not named in the story", "Approved Google's expansion, overturning the county council's refusal", "approved"),
    ("https://w.media/microsoft-gets-approval-for-au1-26bn-96mw-sydney-data-centre/", "Australia", "Western Sydney", "New South Wales planning approval", "Approved Microsoft's 96 MW data centre over the local council's objections", "approved"),
    ("https://w.media/stockland-wins-approval-for-49mw-10-storey-macquarie-park-data-centre/", "Australia", "Macquarie Park, Sydney", "Not named in the story", "Approved Stockland's 49 MW data centre", "approved"),
    ("https://w.media/monash-rejects-centuria-data-centre-plans-as-victoria-tightens-planning-rules/", "Australia", "Melbourne", "Monash Council", "Rejected Centuria's 38 MW data centre against its planners' advice", "blocked"),
    ("https://www.selc.org/news/ace-basin-victory-data-centers-blocked-in-southern-conservation-area/", "US", "ACE Basin, South Carolina", "Not named in the story", "Blocked data centres in a conservation area", "blocked"),
    ("https://www.foodandwaterwatch.org/2026/10/07/oakland-city-council-passes-45-day-moratorium-on-data-centers/", "US", "Oakland", "City Council", "A 45-day moratorium on data centres", "paused"),
    ("https://w.media/cdc-rethinks-576mw-canberra-data-centre-after-planning-setback/", "Australia", "Canberra", "ACT Conservator of Flora and Fauna", "Rejected the assessment route for CDC's campus of up to 576 MW", "review"),
    ("https://www.datacenterknowledge.com/regulations/permits-not-power-halt-google-s-finland-data-centers", "Finland", "Two sites", "Finland's environmental rules", "Stopped site work at two Google data centres", "paused"),
    ("https://w.media/brazils-ons-awards-228-mw-of-grid-capacity-to-three-data-center-projects/", "Brazil", "Whole country", "ONS, the national grid operator", "Gave three data-centre projects 228 MW of grid capacity", "approved"),
    ("https://www.foodandwaterwatch.org/press/2026/10/13/governor-orders-deq-to-pause-data-center-permits/", "US", "Oregon", "Oregon's governor", "Ordered the state environment department to pause data-centre permits", "paused"),
    ("https://w.media/big-watt-powerhouse-secure-approval-for-hyperscale-data-center-campus-in-texas/", "US", "Texas", "Not named in the story", "Approved a hyperscale campus by Big Watt and PowerHouse", "approved"),
    ("https://www.foodandwaterwatch.org/press/2026/10/14/allentown-planning-commission-bucks-public-opinion-greenlights-data-center/", "US", "Allentown, Pennsylvania", "Planning Commission", "Approved a data centre", "approved"),
    ("http://www.bernama.com/en/news.php?id=2620497", "Malaysia", "Whole country", "Data Centre Task Force, Digital Ministry", "27 data-centre projects approved up to July 2026, RM 226bn in all", "approved"),
    ("https://w.media/odisha-cabinet-greenlights-us-18-62-million-backup-data-center/", "India", "Keonjhar, Odisha", "Odisha state cabinet", "Approved a US$ 18.6m backup data centre", "approved"),
]

# Infra stories from after CHECKED_TO checked and left out of all three tables
LEFT_OUT: set[str] = {
    "https://w.media/airtrunk-nears-deal-to-sell-its-johor-data-centers-for-us1-billion-report/",  # sale of existing data centres
    "https://www.thelec.net/news/articleView.html?idxno=14473",  # owner of the Cheongna project not named in the story
    "https://www.thelec.net/news/articleView.html?idxno=14800",  # supercapacitor orders, parts
    "https://www.thelec.net/news/articleView.html?idxno=14726",  # supercapacitor orders, parts
    "http://www.bernama.com/en/news.php?id=2623689",  # a GPU cluster, not a new data centre
    "https://www.foodandwaterwatch.org/press/2026/10/20/as-110-new-jersey-municipalities-have-blocked-ai-data-centers-advocates-and-impacted-residents-call-for-statewide-moratorium/",  # call for a statewide moratorium; no state decision
    "https://w.media/nextdc-cuts-fy27-guidance-pauses-new-projects-over-m3-power-delay/",  # the company's own pause, not a government decision
    "https://w.media/aolani-inks-malaysia-deal-for-500mw-ai-capacity-projects-580mw-commitment-by-2027/",  # lease of capacity; no builder or site named
    "https://www.404media.co/it-aint-right-texas-said-it-would-halt-data-center-permits-the-state-is-pushing-ahead-anyway/",  # the Texas pause is disputed in the story; unclear what was decided
    "http://www.bernama.com/en/news.php?id=2622718",  # market forecast
    "https://www.canarymedia.com/articles/batteries/illinois-storage-procurement-incentives-results",  # grid batteries, not data centres
    "http://www.bernama.com/en/news.php?id=2622651",  # works contract; the data centre's owner not named
}

# a headline that may be a build (a size or an amount beside a data centre), a power deal, or a decision
_SIZE = re.compile(r"\b\d[\d,.]*\s?(?:MW|GW|megawatts?|gigawatts?)\b", re.I)
_MONEY = re.compile(r"(?:US)?\$\s?\d|\d\s?(?:billion|bn|million)\b|€\s?\d|£\s?\d|₹|\bRM\s?\d", re.I)
_SITE = re.compile(r"data ?cent|campus|facility|\bpark\b|AI factory|hyperscale", re.I)
_POWER = re.compile(r"nuclear|\bSMRs?\b|reactor|\bgas\b|gas-fired|turbines?|solar|\bwind\b|geothermal|\bPPAs?\b|"
                    r"power purchase|hydro|batter|fuel cells?|(?:power|energy|electricity) (?:deal|agreement|supply)", re.I)
_DECISION = re.compile(r"moratorium|\bban(?:s|ned)?\b|paus|halt|reject|block|permit|approv|greenlight|zoning|rezon|"
                       r"tax (?:break|incentive|credit|exemption)|denied|\bdeny|orders?\b|court|judge", re.I)

QUESTIONS = {
    "builds": "Where are new data centres being planned and built, by whom, and how big?",
    "power": "Where will data centres get their electricity?",
    "decisions": "Where are data centres being approved, paused or blocked, and who decided?",
}
PATHS = {"builds": "data-centre-builds/", "power": "who-powers-ai/", "decisions": "pushback-and-permits/"}
_MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def _day(d: str) -> str:
    day = date.fromisoformat(d[:10])
    return f"{day.day} {_MONTHS[day.month - 1]} {day.year}"


def _used() -> set[str]:
    return {r[0] for t in (BUILDS, POWER, DECISIONS) for r in t} | LEFT_OUT


def candidates(cards: list[dict], since: str = "") -> list[dict]:
    """Infra stories from after CHECKED_TO (or `since`, if later) that no table uses and LEFT_OUT doesn't hold and whose
    headline may be a build, a power deal or a decision: one per event, newest first."""
    since = max(since, CHECKED_TO + "~")  # '~' sorts after any time of day, so CHECKED_TO itself is done
    used = _used()
    out = []
    for c in sorted(cards, key=lambda c: c["date"], reverse=True):
        if c["date"] < since or c["category"] != "infra":
            continue
        if any(s["url"] in used for s in [c, *(c.get("also") or [])]):
            continue
        t = c["title"]
        if _SIZE.search(t) or (_MONEY.search(t) and _SITE.search(t)) or _POWER.search(t) or _DECISION.search(t):
            out.append(c)
    return out


def _with_stories(table: list[tuple[str, ...]], cards: list[dict]) -> list[dict]:
    """A table's rows whose story we have, each with the story's date, source and headline, newest first."""
    by_url = {s["url"]: s | {"date": s.get("date") or c["date"]} for c in cards for s in [c, *(c.get("also") or [])]}
    rows = [dict(url=r[0], cells=r[1:], date=s["date"][:10], source=s["source"], title=s["title"].strip())
            for r in table if (s := by_url.get(r[0]))]
    return sorted(rows, key=lambda r: r["date"], reverse=True)


def _chip(label: str, colour: str) -> str:
    return f'<span class="iw-chip" style="--c:{colour}">{escape(label)}</span>'


def _src(r: dict) -> str:
    return f'<a href="{escape(r["url"])}" rel="noopener" title="{escape(r["title"])}">{escape(r["source"])}</a>'


def _glance(first: str, last: str, items: list[tuple[str, str, int]]) -> str:
    """The three commonest kinds in the table's chip column as big numbers, each saying what it counts, under about
    how long the table covers, in whole months."""
    top = sorted((i for i in items if i[2]), key=lambda i: -i[2])[:3]
    tiles = "".join(f'<div class="iw-big" style="--c:{c}"><b>{n}</b><span>{escape(label)}</span></div>'
                    for label, c, n in top)
    months = max(1, round((date.fromisoformat(last[:10]) - date.fromisoformat(first[:10])).days / 30.4))
    span = "Past month" if months == 1 else f"Past {months} months"
    return (f'<section class="iw-glance"><h2>At a glance <span class="iw-when">{span}</span>'
            f'</h2>\n<div class="iw-bigs">{tiles}</div></section>\n')


# Excel-style filters, in the reader's browser: each column heading opens a list of that column's values (a cell's
# data-f, else its text), each with how many rows have it among the rows the other filters leave; ticking narrows the
# table. Phones hide the headings, so the same buttons sit in a bar over the table there. Each .iw box on a page
# (AI fines and bans has two) filters its own table. A heading with data-nof
# (a column of titles, each its own) gets no filter.
SCRIPT = """<script>
document.querySelectorAll('.iw').forEach(p=>{const t=p.querySelector('.iw-t,.xf-t'),rows=[...t.tBodies[0].rows],
ths=[...t.tHead.rows[0].cells],count=p.querySelector('.iw-count b'),clear=p.querySelector('.iw-clear'),
bar=p.querySelector('.iw-fbar'),sets=ths.map(()=>null),btns=ths.map(()=>[]);let pop=null;
const val=(r,i)=>{const c=r.cells[i];return c.dataset.f||c.textContent.trim()};
const pass=(r,skip)=>sets.every((s,i)=>i===skip||!s||s.has(val(r,i)));
function run(){let n=0;rows.forEach(r=>{const ok=pass(r,-1);r.hidden=!ok;n+=ok});count.textContent=n;
clear.hidden=sets.every(s=>!s);btns.forEach((b,i)=>b.forEach(x=>x.classList.toggle('on',!!sets[i])))}
function close(){if(pop){pop.remove();pop=null}}
function open(i,b){if(pop&&pop.dataset.i==i){close();return}close();const counts=new Map();
rows.forEach(r=>{if(pass(r,i)){const v=val(r,i);counts.set(v,(counts.get(v)||0)+1)}});
const vals=[...counts.keys()];if(!ths[i].hasAttribute('data-seen'))vals.sort((a,c)=>counts.get(c)-counts.get(a)||a.localeCompare(c));
pop=document.createElement('div');pop.className='iw-pop';pop.dataset.i=i;
const q=document.createElement('input');q.type='search';q.placeholder='Search';q.setAttribute('aria-label','Search '+ths[i].dataset.h);
const all=document.createElement('label');all.className='iw-all';const ab=document.createElement('input');ab.type='checkbox';
all.append(ab,' Select all');const list=document.createElement('div');list.className='iw-vals';
const boxes=vals.map(v=>{const l=document.createElement('label'),c=document.createElement('input'),s=document.createElement('span'),
k=document.createElement('b');c.type='checkbox';c.checked=!sets[i]||sets[i].has(v);c.value=v;
s.textContent=v==='–'?'None given':v;k.textContent=counts.get(v);l.append(c,s,k);list.append(l);return c});
const sync=()=>{ab.checked=boxes.every(c=>c.checked)};
const apply=()=>{const on=boxes.filter(c=>c.checked).map(c=>c.value);sets[i]=on.length===boxes.length?null:new Set(on);sync();run()};
boxes.forEach(c=>c.addEventListener('change',apply));
ab.addEventListener('change',()=>{boxes.forEach(c=>{if(!c.parentNode.hidden)c.checked=ab.checked});apply()});
q.addEventListener('input',()=>{const w=q.value.toLowerCase();boxes.forEach(c=>c.parentNode.hidden=!c.value.toLowerCase().includes(w))});
pop.append(q,all,list);document.body.append(pop);sync();
const r=b.getBoundingClientRect();pop.style.top=(r.bottom+scrollY+4)+'px';
pop.style.left=Math.max(8,Math.min(r.left+scrollX,scrollX+document.documentElement.clientWidth-pop.offsetWidth-8))+'px';q.focus()}
ths.forEach((th,i)=>{if(th.hasAttribute('data-nof'))return;th.dataset.h=th.textContent;const mk=()=>{const b=document.createElement('button');b.type='button';
b.className='iw-hb';b.textContent=th.dataset.h;b.setAttribute('aria-haspopup','true');
b.addEventListener('click',e=>{e.stopPropagation();open(i,b)});btns[i].push(b);return b};
th.textContent='';th.append(mk());bar.append(mk())});
clear.addEventListener('click',()=>{sets.fill(null);close();run()});
document.addEventListener('click',e=>{if(pop&&!pop.contains(e.target))close()});
document.addEventListener('keydown',e=>{if(e.key==='Escape')close()});
p.querySelector('.iw-wrap')?.addEventListener('scroll',close)});
</script>"""


def _where(place: str, country: str) -> str:
    """The place over its country, filtered by the country; a whole-country row is just the country."""
    if not place or place == "Whole country":
        return f'<td data-f="{escape(country)}">{escape(country)}</td>'
    return f'<td data-f="{escape(country)}">{escape(place)}<br><span class="meta">{escape(country)}</span></td>'


def _dates(rows: list[dict]) -> tuple[str, str]:
    """The first and last days a table's stories were reported."""
    days = [r["date"] for r in rows] or [CHECKED_TO]
    return min(days), max(days)


def _when(d: str) -> str:
    """The day a story was reported, filtered by its month."""
    day = date.fromisoformat(d[:10])
    return f'<td class="when" data-f="{_MONTHS[day.month - 1]} {day.year}">{_day(d)}</td>'


def _limits(limits: list[tuple[str, str]]) -> str:
    body = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td></tr>" for a, b in limits)
    return ('<section class="jb-lim"><h2>About these counts</h2>\n'
            f'<table class="mt jb-small jb-limits"><tbody>{body}</tbody></table></section>\n')


def _page(title: str, key: str, intro: str, glance: str, heading: str, noun: str, n: int, table: str,
          limits: str) -> str:
    return ('<div class="ft jb ct iw">\n' + pages.feature_head(PATHS[key], title, QUESTIONS[key], escape(intro))
            + f'{glance}'
            f'<h2>{escape(heading)}</h2>\n<div class="iw-fbar"></div>'
            f'<p class="iw-count" aria-live="polite">Showing <b>{n}</b> of {n} {noun}. Pick a ▾ to filter.'
            f' <button type="button" class="iw-clear" hidden>Clear filters</button></p>\n'
            f'{table}{limits}</div>\n{SCRIPT}\n')


def _table(head: tuple[str, ...], body: str) -> str:
    """The table in its own scrolling box, its headings staying on top."""
    return ('<div class="iw-wrap"><table class="mt iw-t"><thead><tr>'
            + "".join(f'<th{" data-seen" * (h == "Reported")}>{escape(h)}</th>' for h in head)
            + f"</tr></thead><tbody>{body}</tbody></table></div>\n")


def builds_body(rows: list[dict]) -> str:
    """Every build, newest first, after counts by stage and by country."""
    first = _day(min((r["date"] for r in rows), default=CHECKED_TO))
    countries = [r["cells"][1] for r in rows]
    stages = [r["cells"][5] for r in rows]
    intro = (f"{len(rows)} new data centres and campuses in {len(set(countries))} countries, reported since {first}. "
             "Each row gives who is behind it, where, and its size and cost as the story states them.")
    glance = _glance(*_dates(rows), [(f"projects {label.lower()}", c, stages.count(k))
                                     for k, (label, c) in STAGES.items()])
    body = "".join(
        f'<tr>{_when(r["date"])}<td class="who">{escape(who)}</td>{_where(place, country)}'
        f'<td>{escape(size) or "–"}</td><td>{escape(money) or "–"}</td><td>{_chip(*STAGES[stage])}</td>'
        f'<td class="src">{_src(r)}</td></tr>'
        for r in rows for who, country, place, size, money, stage in [r["cells"]])
    table = _table(("Reported", "Who", "Where", "Size", "Money", "Stage", "Story"), body)
    limits = _limits([
        (f"{len(rows)} projects from the news we read",
         f"New data centres and campuses whose story names who is behind it, where it is, and its size or cost, since "
         f"{first}. Sales of existing data centres, loans for ones already running, leases of space and market "
         "forecasts are left out."),
        ("Stage", "What the story says: announced (a plan, an agreement or land bought), building (work has started) "
         "or opened."),
        ("Size and money", "As each story states them. Size is electrical power: 1 GW (gigawatt) is 1,000 MW "
         "(megawatts). Some stories give the power a whole site draws and others the power for its computers, so "
         "sizes aren't added up. A dash means the story gives none."),
        ("Planning decisions", "Approvals, pauses and refusals of data centres are on Pushback & permits."),
    ])
    return _page("Data-centre builds", "builds", intro, glance, "Every project", "projects", len(rows), table, limits)


def power_body(rows: list[dict]) -> str:
    """Every power deal, newest first, after counts by what the power comes from and by status."""
    first = _day(min((r["date"] for r in rows), default=CHECKED_TO))
    kinds = [r["cells"][1] for r in rows]
    status = [r["cells"][4] for r in rows]
    intro = (f"{len(rows)} deals and plans to power data centres, reported since {first}. Each row gives who "
             "is supplying the power, what it comes from, and what it will run.")
    glance = _glance(*_dates(rows), [(f"deals {STATUSES[k].lower()}", c, status.count(k)) for k, c in
                                     (("signed", "#009E73"), ("planned", "#56B4E9"), ("dropped", "#9AA0AA"))])
    body = "".join(
        f'<tr>{_when(r["date"])}<td class="who">{escape(who)}</td><td>{_chip(*SOURCES[kind])}</td>'
        f'<td>{escape(what)}</td><td>{escape(size) or "–"}</td><td>{escape(STATUSES[st])}</td>'
        f'<td class="src">{_src(r)}</td></tr>'
        for r in rows for who, kind, what, size, st in [r["cells"]])
    table = _table(("Reported", "Who", "Power from", "What it powers", "Size", "Status", "Story"), body)
    limits = _limits([
        (f"{len(rows)} deals from the news we read",
         f"Agreements to supply power to data centres, and plans to build it, reported since {first}. Orders for "
         "parts such as switchgear, or for batteries kept as backup, are left out."),
        ("Power from", "The source the story names. From a utility: power bought from a power company whose mix "
         "the story doesn't give. Not stated: the story doesn't say."),
        ("Status", "Signed: a contract, an order or a binding agreement. Planned or in talks: a plan, a non-binding "
         "agreement or talks. Dropped: called off."),
        ("Size", "Electrical power as the story states it: 1 GW (gigawatt) is 1,000 MW (megawatts). A dash means "
         "the story gives none."),
    ])
    return _page("Who powers AI", "power", intro, glance, "Every deal", "deals", len(rows), table, limits)


def decisions_body(rows: list[dict]) -> str:
    """Every decision, newest first, after counts by outcome and by country."""
    first = _day(min((r["date"] for r in rows), default=CHECKED_TO))
    countries = [r["cells"][0] for r in rows]
    outcomes = [r["cells"][4] for r in rows]
    intro = (f"{len(rows)} decisions on data centres in {len(set(countries))} countries, reported since {first}. "
             "Each row gives where, who decided, and what they decided.")
    glance = _glance(*_dates(rows), [(f"decisions: {label.lower()}", c, outcomes.count(k))
                                     for k, (label, c) in OUTCOMES.items()])
    body = "".join(
        f'<tr>{_when(r["date"])}{_where(place, country)}<td class="who">{escape(who)}</td>'
        f'<td>{escape(what)}</td><td>{_chip(*OUTCOMES[outcome])}</td><td class="src">{_src(r)}</td></tr>'
        for r in rows for country, place, who, what, outcome in [r["cells"]])
    table = _table(("Reported", "Where", "Who decided", "What", "Outcome", "Story"), body)
    limits = _limits([
        (f"{len(rows)} decisions from the news we read",
         f"Decisions on data centres by governments, councils, courts, regulators and grid operators, reported since "
         f"{first}. Calls for a pause, protests and proposals not yet decided are left out; they are on Infra's Land "
         "& local pushback page."),
        ("Outcome", "Approved: a permit, planning approval or grid capacity given. Paused: a moratorium or an order "
         "to stop. Blocked: a refusal. New limits: rules restricting where or how data centres are built. More "
         "review ordered: sent back for a fuller assessment. Pause turned down: a call to pause refused."),
        ("Who decided", "As the story names it; where it doesn't, the row says so."),
    ])
    return _page("Pushback & permits", "decisions", intro, glance, "Every decision", "decisions", len(rows), table,
                 limits)


# path: (title, what the page is, its table, its body, its question)
PAGES = {
    "data-centre-builds/": ("Data-centre builds", "New data centres worldwide, who is behind each, where, how big and "
                            "how far along, each checked by hand against its story.", BUILDS, builds_body, "builds"),
    "who-powers-ai/": ("Who powers AI", "Deals to power data centres and what the power comes from (nuclear, gas, "
                       "renewables or a utility), each checked by hand against its story.", POWER, power_body, "power"),
    "pushback-and-permits/": ("Pushback & permits", "Decisions to approve, pause or block data centres worldwide and "
                              "who made them, each checked by hand against its story.", DECISIONS, decisions_body,
                              "decisions"),
}


def build(conn, cards: list[dict], out: Path, today: date) -> list[str]:
    """Write the three pages. Returns their paths."""
    for path, (title, what, table, body, key) in PAGES.items():
        (out / path).mkdir(parents=True, exist_ok=True)
        what = f"{QUESTIONS[key]} {what}"
        data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": what,
                "url": f"{rss.SITE}{path}"}
        (out / path / "index.html").write_text(
            pages.page(f"{title} · AI Pulse", what, path, body(_with_stories(table, cards)), data,
                       pages.frame(conn, len(cards)), ("/infra/", "Back to Infra"),
                       "Headlines are the outlets' own, each linking to its story. New rows are added once checked "
                       "by hand."),
            encoding="utf-8")
    return list(PAGES)


def note(base: str, branch: str) -> tuple[str, str, str] | None:
    """The project inbox's note for an infra/<day> branch: each row it adds to the three tables, and the stories it
    left out; None when it adds nothing. `base` is main's copy of this file."""
    from . import approve
    had = approve.lists_in(base, ("BUILDS", "POWER", "DECISIONS", "LEFT_OUT"))
    rows = ([("Builds", f"{r[1]}, {r[3] or r[2]}", STAGES[r[6]][0], r[4] or r[5], r[0])
             for r in BUILDS if r[0] not in had["BUILDS"]]
            + [("Power", r[1], SOURCES[r[2]][0], r[3], r[0]) for r in POWER if r[0] not in had["POWER"]]
            + [("Permits", f"{r[2]}, {r[1]}", OUTCOMES[r[5]][0], r[4], r[0])
               for r in DECISIONS if r[0] not in had["DECISIONS"]])
    dropped = [u for u in LEFT_OUT if u not in had["LEFT_OUT"]]
    if not rows and not dropped:
        return None
    return approve.note("Infra features", f"row{'s' * (len(rows) != 1)}", branch,
                        ("Page", "Who / where", "Kind", "What", "Source"), rows, dropped)
