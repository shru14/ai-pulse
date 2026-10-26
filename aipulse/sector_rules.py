"""Sector-specific AI rules (tracker/sector-specific/): the rules written for AI in one sector, from every place, on
the Regulation strip and free for everyone. Two kinds of row, both checked by hand: the main rules a firm in a sector
must follow, read from each official text (HAND), and the tracker's own laws, bills and AI bodies whose official title
shows they were written for one sector (TRACKER, by bill id). Pulse Compass's rule book reads its rules from here.
"""
from __future__ import annotations

import re
from html import escape
from pathlib import Path
from urllib.parse import urlparse

from . import infra_watch, jurisdictions, pages
from .bills import OFFICIAL_SOURCES

PATH = "tracker/sector-specific/"
# (id, name), in the page's order
SECTORS = [("finance", "Finance"), ("comms", "Electronic communications"), ("health", "Healthcare"),
           ("legal", "Legal and courts"), ("public", "Public sector"), ("policing", "Policing and borders"),
           ("education", "Education"), ("work", "Work and jobs"), ("elections", "Elections"), ("defence", "Defence"),
           ("farming", "Farming"), ("industry", "Manufacturing")]
NAMES = dict(SECTORS)

# The main rules for AI in a sector, checked by hand: (sector, place, kind, rule, since, what it asks of a firm that
# uses AI, link). Kinds: Law, Rule (a supervisor's binding rule), Guidance. Finance checked 26 Oct 2026 against each
# text (Pulse Compass's rule book); electronic communications and algorithmic trading added 26 Oct 2026
EU_AI_ACT = "https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng"
HAND = [
    ("finance", "EU", "Law", "AI Act: finance supervisors police AI at the firms they oversee (Article 74(6))",
     "From 2 Aug 2026",
     "Where a bank, insurer or investment firm uses AI, its own finance supervisor checks that the AI Act is met.",
     EU_AI_ACT),
    ("finance", "EU", "Law", "AI Act: credit scoring and life and health insurance pricing are high-risk (Annex III, "
     "point 5)", "From 2 Dec 2027, moved by the Digital Omnibus",
     "Such AI needs risk management, human oversight, records and checks before use. Finding fraud is left out.",
     EU_AI_ACT),
    ("finance", "EU", "Law", "AI Act: AI literacy (Article 4)", "Since 2 Feb 2025",
     "Staff who use AI are trained enough to use it well.", EU_AI_ACT),
    ("finance", "EU", "Law", "AI Act: telling people it is AI (Article 50)", "Since 2 Aug 2026",
     "Customers are told when they are dealing with an AI.", EU_AI_ACT),
    ("finance", "EU", "Law", "DORA: digital operational resilience", "Since 17 Jan 2025",
     "AI systems count as ICT: they sit inside ICT risk management, and an AI supplier's contract needs the terms in "
     "Article 30 and a line in the register of information.", "https://eur-lex.europa.eu/eli/reg/2022/2554/oj/eng"),
    ("finance", "EU", "Law", "GDPR", "Since 25 May 2018",
     "A contract with any AI supplier that handles personal data, safeguards when data leaves the EU, and a person in "
     "decisions about people (Article 22).", "https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng"),
    ("finance", "EU", "Law", "Consumer Credit Directive (2023/2225)", "From 20 Nov 2026",
     "A consumer whose creditworthiness is judged by automated means can ask for a person to look again and for an "
     "explanation (Article 18).", "https://eur-lex.europa.eu/eli/dir/2023/2225/oj/eng"),
    ("finance", "EU", "Law", "Anti-Money Laundering Regulation (2024/1624)", "From 10 Jul 2027",
     "Duties to monitor and report stay with the firm, whatever tool does the first sort.",
     "https://eur-lex.europa.eu/eli/reg/2024/1624/oj/eng"),
    ("finance", "EU", "Law", "MiFID II: algorithmic trading (Article 17)", "Since 3 Jan 2018",
     "A firm trading by algorithm has controls that stop faulty orders and disorderly markets, tests and monitors "
     "its systems, and tells its supervisor and the trading venue.", "https://eur-lex.europa.eu/eli/dir/2014/65/oj/eng"),
    ("finance", "EU", "Guidance", "EBA guidelines on loan origination and monitoring", "Since 30 Jun 2021",
     "Banks that use automated models to grant credit must understand the model, its data and its limits, and keep "
     "it under control.",
     "https://www.eba.europa.eu/activities/single-rulebook/regulatory-activities/credit-risk/guidelines-loan-origination-and-monitoring"),
    ("finance", "EU", "Guidance", "EIOPA opinion on AI governance and risk management", "Published 6 Aug 2025",
     "Insurers using AI that is not high-risk: governance in proportion to the risk, sound data, explanations, human "
     "oversight, under Solvency II and the Insurance Distribution Directive.",
     "https://www.eiopa.europa.eu/publications/opinion-artificial-intelligence-governance-and-risk-management_en"),
    ("finance", "EU", "Guidance", "ESMA statement on AI in investment services", "Published 30 May 2024",
     "Duties to clients stay the same when AI does part of the work; the board stays responsible.",
     "https://www.esma.europa.eu/sites/default/files/2024-05/ESMA35-335435667-5924__Public_Statement_on_AI_and_investment_services.pdf"),
    ("finance", "DE", "Law", "BaFin supervises AI at finance firms under the AI Act", "Since 29 Jul 2026",
     "Germany's AI Act law makes BaFin the market surveillance authority for AI tied to regulated financial "
     "business, alongside its usual supervision.",
     "https://www.bafin.de/SharedDocs/Veroeffentlichungen/DE/Pressemitteilung/2026/pm_2026_07_29_ki_verordnung.html"),
    ("finance", "DE", "Law", "Securities Trading Act: algorithmic trading (WpHG §80(2))", "Since 3 Jan 2018",
     "A firm trading by algorithm keeps resilient systems with trading limits, stops faulty orders, keeps continuity "
     "plans, and tells BaFin and each trading venue.", "https://www.gesetze-im-internet.de/wphg/__80.html"),
    ("finance", "DE", "Rule", "MaRisk: minimum requirements for risk management (Circular 05/2023)", "Since 29 Jun 2023",
     "Banks' risk management, now with a section on model risk: models used in decisions are governed, validated "
     "and documented.",
     "https://www.bundesbank.de/en/tasks/banking-supervision/individual-aspects/risk-management/marisk/marisk-in-the-version-of-29-06-2023-799528"),
    ("finance", "DE", "Guidance", "BaFin: ICT risks when using AI", "Published 18 Dec 2025",
     "How DORA's ICT and third-party rules apply across the AI life cycle, from data to shutdown, with a worked "
     "example of an assistant built on a large language model.",
     "https://www.bafin.de/SharedDocs/Veroeffentlichungen/EN/Meldung/2025/meldung_2025_12_18_orientierungshilfe_ikt_risiken_en.html"),
    ("finance", "DE", "Guidance", "BaFin: principles for algorithms in decision-making", "Published 15 Jun 2021",
     "Management stays responsible; data and models are checked for bias; results can be explained and corrected by "
     "a person.", "https://www.bafin.de/SharedDocs/Downloads/EN/Aufsichtsrecht/dl_Prinzipienpapier_BDAI_en.html"),
    ("finance", "DE", "Rule", "BAIT, VAIT, KAIT and ZAIT: BaFin's IT rules give way to DORA",
     "KAIT, VAIT, ZAIT ended 16 Jan 2025; BAIT ends by 31 Dec 2026",
     "Firms under DORA follow DORA for IT, AI included, instead of BaFin's own IT circulars.",
     "https://www.bundesbank.de/en/tasks/banking-supervision/individual-aspects/risk-management/bait/bait-dora-741194"),
    ("finance", "FR", "Guidance", "ACPR: governance of AI in finance", "Published 1 Jun 2020",
     "Four tests for an AI tool: how its data is managed, how well it performs, how stable it is, and how it can be "
     "explained, with governance from the design stage.",
     "https://acpr.banque-france.fr/en/publications-and-statistics/publications/governance-artificial-intelligence-finance"),
    ("finance", "IT", "Law", "Italy's AI law (Law 132/2025)", "Published 25 Sep 2025",
     "Applies the AI Act in Italy without adding duties; Banca d'Italia, CONSOB and IVASS keep their role over the "
     "firms they supervise (Article 20).", "https://www.normattiva.it/eli/id/2025/09/25/25G00143/ORIGINAL"),
    ("finance", "IT", "Law", "Who supervises AI in Italy (Legislative Decree 179/2026)", "Published 8 Oct 2026",
     "Banca d'Italia, CONSOB and IVASS use the AI Act's powers over the financial firms they supervise.",
     "https://www.normattiva.it/eli/id/2026/10/08/26G00200/ORIGINAL"),
    ("finance", "NL", "Guidance", "DNB: general principles for AI in the financial sector (SAFEST)", "Published 25 Jul 2019",
     "Six principles: soundness, accountability, fairness, ethics, skills and transparency.",
     "https://www.dnb.nl/media/voffsric/general-principles-for-the-use-of-artificial-intelligence-in-the-financial-sector.pdf"),
    ("finance", "IN", "Guidance", "RBI: FREE-AI framework for responsible AI in finance", "Published 13 Aug 2025",
     "Seven principles and 26 recommendations: a board-approved AI policy, AI inside risk assessment, approvals and "
     "audits, incident reporting, and protection for customers.",
     "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=61018"),
    ("finance", "IN", "Rule", "RBI Digital Lending Directions, 2025", "Since 8 May 2025",
     "Banks and NBFCs lending through apps: money moves straight between borrower and lender, apps are reported to "
     "the RBI, and the lender answers for its lending service providers.",
     "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12848&Mode=0"),
    ("finance", "IN", "Rule", "RBI IT governance, risk, controls and assurance directions, 2023", "Issued 7 Nov 2023",
     "A board-level IT strategy committee, and IT risk management, business continuity and audit for every system "
     "the firm runs.",
     "https://website.rbi.org.in/web/rbi/-/notifications/master-direction-on-information-technology-governance-risk-controls-and-assurance-practices"),
    ("finance", "IN", "Rule", "RBI outsourcing of IT services directions, 2023", "Since 1 Oct 2023",
     "Using an outside AI or cloud provider for material IT work needs a board-approved policy and risk-based checks "
     "on the provider, and must not weaken the RBI's supervision.",
     "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12486"),
    ("finance", "IN", "Rule", "SEBI: responsibility for AI tools (Intermediaries Regulations, Regulation 16C)",
     "Approved Dec 2024; notified Feb 2025",
     "Anyone SEBI regulates is solely responsible for the AI tools it uses, built or bought: for data privacy and "
     "security, for what the tools produce, and for following the law.",
     "https://www.sebi.gov.in/sebi_data/meetingfiles/dec-2024/1735042007618_1.pdf"),
    ("finance", "IN", "Rule", "SEBI: safer participation of retail investors in algorithmic trading", "Issued 4 Feb 2025",
     "The broker is the principal and any algo provider its agent; every algo order through an API carries the "
     "exchange's identifier; investors' own fast algos are registered with the exchange through the broker.",
     "https://www.sebi.gov.in/legal/circulars/feb-2025/safer-participation-of-retail-investors-in-algorithmic-trading_91614.html"),
    ("finance", "IN", "Rule", "SEBI Cybersecurity and Cyber Resilience Framework (CSCRF)", "Issued 20 Aug 2024",
     "Cyber governance, incident response and checks on outside providers' security for every SEBI-regulated firm, "
     "graded by size.",
     "https://www.sebi.gov.in/legal/circulars/aug-2024/cybersecurity-and-cyber-resilience-framework-cscrf-for-sebi-regulated-entities-res-_85964.html"),
    ("finance", "IN", "Law", "Digital Personal Data Protection Act, 2023 and DPDP Rules, 2025",
     "Rules notified Nov 2025; firms' duties apply from about May 2027",
     "Notice and consent for personal data, security safeguards, and a contract with any processor, such as an AI "
     "supplier.", "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf"),
    ("finance", "IN", "Law", "Prevention of Money-Laundering Act, 2002 and RBI KYC Master Direction",
     "KYC Direction since 25 Feb 2016, updated 14 Aug 2025",
     "Customer checks, transaction monitoring and reporting stay with the firm, whatever tool does the first sort.",
     "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=11566"),
    ("finance", "IN", "Rule", "CERT-In cyber security directions", "Issued 28 Apr 2022",
     "Report cyber incidents to CERT-In within 6 hours of noticing them, and keep system logs in India for 180 "
     "days.", "https://www.cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf"),
    ("finance", "GB", "Law", "UK GDPR and Data Protection Act 2018", "Since 1 Jan 2021 (UK GDPR)",
     "A contract with any AI supplier that handles personal data, and safeguards when data leaves the UK.",
     "https://www.legislation.gov.uk/ukpga/2018/12/contents"),
    ("finance", "GB", "Rule", "FCA Consumer Duty", "Since 31 Jul 2023",
     "What reaches customers is right, clear and fair, with evidence that the firm checked.",
     "https://www.handbook.fca.org.uk/handbook/PRIN/2A/"),
    ("finance", "GB", "Rule", "Senior Managers and Certification Regime", "Since 2016 for banks, 2019 for all FCA firms",
     "A named senior manager answers for each AI tool.", "https://www.fca.org.uk/firms/senior-managers-certification-regime"),
    ("finance", "GB", "Rule", "Operational resilience (FCA SYSC 15A)", "Since 31 Mar 2025",
     "An AI tool inside an important service is mapped and tested for what happens if its supplier stops.",
     "https://www.handbook.fca.org.uk/handbook/SYSC/15A/"),
    ("finance", "GB", "Rule", "FCA algorithmic trading (MAR 7A)", "Since 3 Jan 2018",
     "A firm trading by algorithm keeps resilient systems with trading limits that stop faulty orders and market "
     "abuse, and tells the FCA at once that it trades this way.", "https://handbook.fca.org.uk/handbook/MAR/7A/"),
    ("finance", "GB", "Rule", "PRA model risk management (SS1/23)", "Since 17 May 2024",
     "Banks with internal model approval keep an inventory of models, AI included, validate them independently and "
     "name who is accountable.",
     "https://www.bankofengland.co.uk/prudential-regulation/publication/2023/may/model-risk-management-principles-for-banks-ss"),
    ("finance", "GB", "Law", "Money Laundering Regulations 2017", "Since 26 Jun 2017",
     "The duty to spot and report suspicious activity stays with the firm.",
     "https://www.legislation.gov.uk/uksi/2017/692/contents"),
    ("finance", "US", "Rule", "Model risk management (SR 11-7)", "Since 4 Apr 2011",
     "Banks test a model before use, write down its limits and have it reviewed independently.",
     "https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm"),
    ("finance", "US", "Guidance", "Interagency guidance on third-party risk", "Since 6 Jun 2023",
     "Banks treat an AI company like any critical supplier: vetted before, watched after.",
     "https://www.federalregister.gov/documents/2023/06/09/2023-12340/interagency-guidance-on-third-party-relationships-risk-management"),
    ("finance", "US", "Law", "Equal Credit Opportunity Act, Regulation B: reasons for a refusal", "In force",
     "A lender that refuses credit gives the specific reasons, also when an AI model made the call.",
     "https://www.ecfr.gov/current/title-12/chapter-X/part-1002/section-1002.9"),
    ("finance", "US", "Law", "Gramm-Leach-Bliley Act: safeguarding customer data", "FTC Safeguards Rule, updated 2023",
     "Check an AI company's security before signing, put it in the contract, and keep checking it.",
     "https://www.ecfr.gov/current/title-16/chapter-I/subchapter-C/part-314"),
    ("finance", "US", "Law", "Unfair, deceptive or abusive practices (Consumer Financial Protection Act)", "Since 2011",
     "Customers get accurate answers and a way to reach a person.", "https://www.law.cornell.edu/uscode/text/12/5531"),
    ("finance", "US", "Guidance", "FINRA Regulatory Notice 24-09", "Published 27 Jun 2024",
     "Broker-dealers' AI-written client material meets the same content rules, and is supervised and kept the same "
     "way.", "https://www.finra.org/rules-guidance/notices/24-09"),
    ("finance", "US", "Guidance", "NAIC model bulletin on insurers' use of AI",
     "Adopted Dec 2023; taken up by 24 states by Aug 2025",
     "Insurers keep a written AI programme, and AI decisions still follow the laws on unfair discrimination.",
     "https://content.naic.org/article/naic-members-approve-model-bulletin-use-ai-insurers"),
    ("finance", "US", "Rule", "New York DFS Insurance Circular Letter No. 7", "Since 11 Jul 2024",
     "Insurers in New York show their AI and outside data don't discriminate unfairly in underwriting and pricing, "
     "and stay responsible for vendors' tools.", "https://www.dfs.ny.gov/industry-guidance/circular-letters/cl2024-07"),
    ("finance", "US", "Guidance", "New York DFS: cybersecurity risks from AI", "Published 16 Oct 2024",
     "Firms licensed in New York assess AI-driven threats, such as deepfakes, under the state's cybersecurity rule.",
     "https://www.dfs.ny.gov/industry-guidance/industry-letters/il20241016-cyber-risks-ai-and-strategies-combat-related-risks"),
    ("finance", "US", "Law", "Bank Secrecy Act: suspicious activity reports", "In force",
     "The duty to file reports stays with the firm.",
     "https://www.fincen.gov/resources/statutes-and-regulations/bank-secrecy-act"),
    ("finance", "US", "Law", "Colorado automated decision-making law (SB 26-189)", "Signed 14 May 2026",
     "Consumers are told when AI plays a part in a financial decision, given its role in a refusal, and offered a "
     "review by a person.", "https://leg.colorado.gov/bills/sb26-189"),
    # electronic communications: marketing by email, text or automated call, and cookies, AI-written or not
    ("comms", "EU", "Law", "ePrivacy Directive (2002/58/EC): marketing and cookies (Articles 13 and 5(3))",
     "Since 31 Oct 2003",
     "Marketing by email, text or automated call needs the person's prior consent, except for similar products to "
     "existing customers; storing or reading cookies on a device needs consent.",
     "https://eur-lex.europa.eu/eli/dir/2002/58/oj/eng"),
    ("comms", "DE", "Law", "Unfair Competition Act: unwanted advertising (UWG §7)", "In force",
     "Advertising by email or automated calling machine needs the addressee's prior express consent; existing "
     "customers may get emails about similar own products if told each time they can object.",
     "https://www.gesetze-im-internet.de/uwg_2004/__7.html"),
    ("comms", "DE", "Law", "Telecommunications and digital services data protection act (TDDDG §25)",
     "Since 1 Dec 2021, as the TTDSG",
     "Storing or reading information on a user's device, such as cookies, needs consent given on clear, full "
     "information.", "https://www.gesetze-im-internet.de/ttdsg/__25.html"),
    ("comms", "FR", "Law", "Post and Electronic Communications Code: email marketing (Article L34-5)", "Since 2004",
     "Email marketing to individuals needs their prior consent, given freely and by a positive act; existing "
     "customers may get offers for similar products.",
     "https://www.cnil.fr/fr/la-prospection-commerciale-par-courrier-electronique"),
    ("comms", "IT", "Law", "Privacy Code: unwanted communications (Article 130)", "Text in force since 19 Sep 2018",
     "Automated calls without an operator, and email, SMS, MMS or fax, for advertising, direct sales or market "
     "research need the person's consent.",
     "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2003-06-30;196~art130"),
    ("comms", "NL", "Law", "Telecommunications Act: unsolicited messages and cookies (Articles 11.7 and 11.7a)",
     "In force",
     "Automated calling systems without a person, fax and electronic messages for unsolicited commercial, ideal or "
     "charitable communication are banned unless the sender can show prior consent; cookies need clear information "
     "and consent.", "https://wetten.overheid.nl/BWBR0009950/"),
    ("comms", "GB", "Law", "Privacy and Electronic Communications Regulations: marketing emails (PECR reg. 22)",
     "Since 11 Dec 2003; charity exception added 5 Feb 2026",
     "Marketing emails and texts to individuals need their prior consent, except about similar products to existing "
     "customers who were given a simple way to refuse.",
     "https://www.legislation.gov.uk/uksi/2003/2426/regulation/22"),
    ("comms", "US", "Law", "Telephone Consumer Protection Act: artificial voices (47 U.S.C. §227(b))", "Since 1991",
     "Calls using an artificial or prerecorded voice need the called person's prior express consent; the FCC ruled on "
     "8 Feb 2024 that AI-generated voices count.",
     "https://www.govinfo.gov/content/pkg/USCODE-2023-title47/html/USCODE-2023-title47-chap5-subchapII-partI-sec227.htm"),
]

# The tracker's own records written for AI in one sector, checked by hand from each official title, 26 Oct 2026:
# bill id -> sector. Left out: laws for everyone that touch a sector, general crimes (deepfakes, fraud), copyright,
# data centres and cyber security, and bills about a group of people (children, older people) rather than a sector
TRACKER = {
    # finance
    "VN-99fa0140-c2ba-11f1-b8ec-99379998c900": "finance", "BR-PL-4391-2026": "finance", "US-119-hr-4801": "finance",
    "US-119-s-2528": "finance",
    # healthcare
    "BR-PL-2463-2026": "health", "US-119-hr-8526": "health", "EU-2025-0404": "health", "BR-PL-1254-2026": "health",
    "IN-RS-2026-XIII": "health", "US-119-hr-7064": "health", "US-119-hr-6361": "health", "BR-PL-5548-2025": "health",
    "US-119-hr-5045": "health", "BR-PL-1522-2024": "health", "US-119-s-501": "health",
    # legal and courts
    "BR-PL-3392-2026": "legal", "BR-PL-2543-2026": "legal", "US-119-s-4154": "legal", "US-119-hr-7997": "legal",
    "BR-PL-1130-2026": "legal", "OECD-2665": "legal",
    # public sector
    "KR-인공지능 및 데이터 기반 행정 활성화에 관한 법률": "public", "KR-인공지능 및 데이터 기반 행정 활성화에 관한 법률 시행령": "public",
    "KR-인공지능 및 데이터 기반 행정 활성화에 관한 법률 시행규칙": "public", "BR-PL-4388-2026": "public",
    "BR-PL-3743-2026": "public", "BR-PL-3560-2026": "public", "CH-20243796": "public", "US-119-s-3410": "public",
    "BR-PL-1290-2025": "public", "BR-PL-4589-2024": "public", "OECD-686": "public", "OECD-2596": "public",
    "OECD-2648": "public", "BR-PL-791-2023": "public",
    # policing and borders
    "BR-PL-6248-2025": "policing", "BR-PL-4369-2025": "policing", "BR-PL-649-2026": "policing",
    "US-119-hr-9566": "policing", "OECD-2380": "policing", "OECD-750": "policing",
    # education
    "US-119-hr-10515": "education", "BR-PL-3615-2026": "education", "NO-200178": "education",
    "US-119-s-3957": "education", "BR-PL-323-2026": "education", "BR-PL-7137-2025": "education",
    "BR-PL-7174-2025": "education", "US-119-hr-5351": "education", "BR-PL-3003-2025": "education",
    "BR-PL-2224-2025": "education", "BR-PL-2225-2025": "education", "BR-PL-2129-2025": "education",
    "BR-PL-1956-2025": "education", "BR-PL-1963-2025": "education", "BR-PL-1614-2025": "education",
    "BR-PL-1325-2025": "education", "BR-PL-899-2025": "education", "BR-PL-1559-2024": "education",
    # work and jobs
    "US-119-s-5664": "work", "BR-PL-5178-2026": "work", "US-119-hr-9352": "work", "US-119-s-3108": "work",
    "BR-PL-2067-2026": "work", "CH-20234492": "work", "CH-20263879": "work", "IN-RS-2023-LXIX": "work",
    "BR-PL-3088-2024": "work", "BR-PL-3423-2023": "work", "GB-3464": "work", "US-119-hr-10044": "work",
    # elections
    "US-119-hr-10841": "elections", "US-119-hr-10814": "elections", "US-119-hr-9922": "elections",
    "US-119-s-4774": "elections", "BR-PL-450-2026": "elections", "US-119-hr-5272": "elections",
    "US-119-s-1213": "elections", "US-119-s-2346": "elections",
    # defence
    "US-119-hr-10189": "defence", "US-119-s-4707": "defence", "US-119-s-4656": "defence", "US-119-hr-6530": "defence",
    "US-119-s-2606": "defence", "US-119-hr-3434": "defence", "US-119-s-1775": "defence", "OECD-754": "defence",
    # farming
    "US-119-hr-9686": "farming", "US-119-s-4627": "farming", "BR-PL-240-2026": "farming",
    # manufacturing
    "KR-산업 디지털 전환 및 인공지능 활용 촉진법": "industry", "KR-산업 디지털 전환 및 인공지능 활용 촉진법 시행령": "industry",
    "KR-산업 디지털 전환 및 인공지능 활용 촉진법 시행규칙": "industry",
}
KIND = {"law": "Law", "proposal": "Bill", "body": "AI body"}


def tracker_rows(cards: list[dict]) -> list[dict]:
    """The tracker's official records written for one sector, newest first, each with its "sector"."""
    return [{**c, "sector": TRACKER[c["bill"]]} for c in sorted(cards, key=lambda c: c["date"], reverse=True)
            if c["category"] == "regulation" and c["source"] in OFFICIAL_SOURCES and c.get("bill") in TRACKER]


def rules(cards: list[dict], sector: str | None = None) -> list[dict]:
    """Every sector rule as one shape: the hand-checked ones, then the tracker's, for one sector or all.
    place: a tracker place code (EU, GB, INTL, ...); since: the text the date column shows; year: its filter;
    iso: a tracker record's date, for newest first."""
    from .countries import _day
    out = [{"sector": s, "place": p, "kind": k, "title": n, "since": w, "year": (re.findall(r"\b(?:19|20)\d\d\b", w) or ["In force"])[0],
            "what": what, "url": u, "source": urlparse(u).netloc.removeprefix("www."), "hand": True, "iso": ""}
           for s, p, k, n, w, what, u in HAND]
    out += [{"sector": c["sector"], "place": next(iter(c.get("jurisdictions") or []), "INTL"),
             "kind": KIND.get(c.get("action") or "proposal", "Bill"), "title": c["title"].strip(),
             "since": _day(c["date"]),
             "year": c["date"][:4], "what": "", "url": c["url"], "source": c["source"], "hand": False, "iso": c["date"]}
            for c in tracker_rows(cards)]
    return [r for r in out if sector in (None, r["sector"])]


# each sector's button icon, a 24x24 path
ICONS = {"finance": "M12 3v18M17 7H9.5a3 3 0 0 0 0 6h5a3 3 0 0 1 0 6H6", "comms": "M3 6h18v12H3zM3 6l9 7 9-7",
         "health": "M9 3h6v6h6v6h-6v6H9v-6H3V9h6z",
         "legal": "M12 4v16M8 20h8M5 7h14M5 7l-3 6.5a3 3 0 0 0 6 0zM19 7l-3 6.5a3 3 0 0 0 6 0z",
         "public": "M3 20h18M5 20v-8M9.5 20v-8M14.5 20v-8M19 20v-8M3 12h18L12 5z",
         "policing": "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z", "education": "M2 9l10-5 10 5-10 5zM6 11v5c3 2 9 2 12 0v-5",
         "work": "M3 8h18v12H3zM8 8V5h8v3M3 13h18", "elections": "M4 11h16v9H4zM8 11V4h8v7M10 7h4",
         "defence": "M12 3l2.6 5.6 6.1.7-4.5 4.2 1.2 6L12 16.6l-5.4 2.9 1.2-6-4.5-4.2 6.1-.7z",
         "farming": "M5 19C5 11 11 5 19 5c0 8-6 14-14 14zM5 19l8-8", "industry": "M3 21V10l6 4v-4l6 4V5h6v16z"}
BACK = ("/regulation/", "Back to the live Regulation tracker page")
NOTE = "Official texts only, each linking to its source."


def page(conn, cards: list[dict], out: Path) -> list[str]:
    """tracker/sector-specific/: a button per sector, each saying what it holds; and a page per sector
    (tracker/sector-specific/<sector>/): its rules by place (A to Z, International last), the hand-checked ones first
    in each, then newest, with the type pages' column filters (place, kind, year) and each rule's source under it.
    A sector is "checked" once HAND holds its main rules; otherwise its page says it holds tracker records only."""
    from .countries import FLAGS, GROUP_SCRIPT, flag, slug
    names = {code: m["name"] for code, m in jurisdictions.meta().items()}
    name = lambda r: names.get(r["place"], "International")
    every = rules(cards)
    if not every:
        return []
    with_page = {p.name for p in (out / "tracker").iterdir() if p.is_dir()} if (out / "tracker").exists() else set()
    (out / "flags").mkdir(parents=True, exist_ok=True)
    parts, paths, tiles = pages.frame(conn, len(cards)), [], []
    for sid, sname in SECTORS:
        items = sorted((r for r in every if r["sector"] == sid), key=lambda r: r["iso"], reverse=True)  # newest first
        items.sort(key=lambda r: (name(r) == "International", name(r), not r["hand"]))  # by place, hand rows first
        if not items:
            continue
        checked = any(r["hand"] for r in items)
        rows = []
        for r in items:
            where = escape(name(r))
            if (FLAGS / flag(r["place"])).exists():
                (out / "flags" / flag(r["place"])).write_bytes((FLAGS / flag(r["place"])).read_bytes())
                where = f'<img class="flag" src="/flags/{flag(r["place"])}" alt="">{where}'
            if slug(name(r)) in with_page:
                where = f'<a href="/tracker/{slug(name(r))}/">{where}</a>'
            what = (f'<div class="sr-what">{escape(r["what"])}</div>' if r["what"] else "") + f'<div class="sr-src">{escape(r["source"])}</div>'
            rows.append(f'<tr><td class="tp-where" data-f="{escape(name(r))}"><span>{where}</span></td>'
                        f'<td class="tp-title"><a href="{escape(r["url"])}">{escape(r["title"])}</a>{what}</td>'
                        f'<td class="sr-kind">{escape(r["kind"])}</td>'
                        f'<td class="tp-date" data-f="{escape(r["year"])}">{escape(r["since"])}</td></tr>')
        low = sname if sid == "comms" else sname.lower()
        title, question = f"AI rules: {sname}", f"Which AI rules apply in {low}?"
        intro = (f"The main rules for AI in {low}, read by hand from each official text, then the laws, bills and AI "
                 "bodies from our tracker written for it, place by place, each linking to the source."
                 if checked else
                 f"Laws, bills and AI bodies from our tracker written for AI in {low}, place by place, each filed by "
                 f"hand and linking to the source. The main rules that already apply to {low} in each place are not "
                 "checked yet, so this is not the full list.")
        head = "<tr><th>Place</th><th data-nof>Rule</th><th>Kind</th><th data-seen>Date</th></tr>"
        body = ('<div class="iw">' + pages.band("reg", ICONS[sid], "photos/cartoons/pages/tracker.svg", title, question,
                                                f'{intro} <a href="/{PATH}">All sectors</a>')
                + f'<div class="iw-fbar"></div><p class="iw-count" aria-live="polite">Showing <b>{len(rows)}</b> of {len(rows)} '
                  f'rules. Pick a ▾ to filter. <button type="button" class="iw-clear" hidden>Clear filters</button></p>\n'
                + f'<div class="iw-wrap"><table class="mt tp-t iw-t tp-grp sr-t"><thead>{head}</thead><tbody>\n' + "\n".join(rows)
                + f"\n</tbody></table></div></div>\n{infra_watch.SCRIPT}\n{GROUP_SCRIPT}")
        data = {"@context": "https://schema.org", "@type": "ItemList", "name": title,
                "itemListElement": [{"@type": "ListItem", "position": i + 1,
                                     "item": {"@type": "Legislation", "name": r["title"], "url": r["url"],
                                              "legislationJurisdiction": name(r)}} for i, r in enumerate(items[:100])]}
        path = f"{PATH}{sid}/"
        (out / path).mkdir(parents=True, exist_ok=True)
        (out / path / "index.html").write_text(pages.page(f"{title} · AI Pulse", intro, path, body, data, parts,
                                                          (f"/{PATH}", "Back to all sectors"), NOTE), encoding="utf-8")
        paths.append(path)
        tiles.append(f'<a href="/{path}"><span class="sr-ic"><svg viewBox="0 0 24 24"><path d="{ICONS[sid]}"/></svg></span>'
                     f'<span><b>{escape(sname)}</b><small>{len(items)} rule{"s" * (len(items) != 1)}</small>'
                     f'<small>{"Main rules checked" if checked else "Tracker records only"}</small></span></a>')
    title, question = "Sector-specific AI rules", "Which AI rules apply to one sector?"
    intro = ("Pick a sector to see the rules written for AI in it, place by place. Sectors marked “main rules "
             "checked” hold the rules read by hand from each official text; the others hold only the laws, bills "
             "and AI bodies from our tracker so far.")
    body = (pages.band("reg", "M3 21h18M5 21V10l7-5 7 5v11M9 21v-6h6v6", "photos/cartoons/pages/tracker.svg", title,
                       question, f'{intro} <a href="/tracker/">AI laws by country</a>')
            + '<div class="sr-tiles">\n' + "\n".join(tiles) + "\n</div>")
    data = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title}
    (out / PATH).mkdir(parents=True, exist_ok=True)
    (out / PATH / "index.html").write_text(pages.page(f"{title} · AI Pulse", intro, PATH, body, data, parts, BACK, NOTE),
                                           encoding="utf-8")
    return [PATH, *paths]
