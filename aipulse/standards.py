"""Published AI standards for the regulation tracker: ISO/IEC (JTC 1/SC 42, the joint AI committee) and IEEE.

Neither publisher can be read automatically within this project's rules: iso.org sits behind a bot check and
IEEE's robots.txt disallows its feeds. So this is a hand-kept list of facts: each standard's number, title,
publication date and official page, every one checked against that page (ISO/IEC 42006's date against the
DIN Media record, as its ISO page wouldn't load). Nothing of a standard's text is copied; the one-line
summaries are our own. A new standard appears when it's added here.

ISO gives only the month of publication, so ISO cards are dated the 1st and the page shows the month.
Standards are international, so they sit under "International" in the tracker's region filter.
"""

from __future__ import annotations

from . import store

ISO, IEEE = "ISO/IEC", "IEEE SA"
SOURCES = (ISO, IEEE)
MARK = "STD-"  # items.bill: each standard stands alone (see cluster.py), never grouped with news

# (publisher, number, title, published, official page, what it covers)
STANDARDS = [
    (ISO, "ISO/IEC 42001:2023", "AI management systems", "2023-12-01", "https://www.iso.org/standard/42001",
     "Requirements for an organisation's AI management system: policies, risk and impact processes, and "
     "controls for developing, providing or using AI responsibly. Organisations can be certified against it."),
    (ISO, "ISO/IEC 42005:2025", "AI system impact assessment", "2025-05-01", "https://www.iso.org/standard/42005",
     "Guidance on assessing how an AI system and its foreseeable uses may affect individuals, groups and society, "
     "across the system's life cycle."),
    (ISO, "ISO/IEC 42006:2025", "Requirements for bodies providing audit and certification of AI management systems",
     "2025-07-01", "https://www.iso.org/standard/42006",
     "What audit and certification bodies need in order to certify organisations against ISO/IEC 42001."),
    (ISO, "ISO/IEC 23894:2023", "AI — Guidance on risk management", "2023-02-01", "https://www.iso.org/standard/77304.html",
     "How organisations that develop, deploy or use AI can manage its risks, adapting general risk management "
     "(ISO 31000) to AI."),
    (ISO, "ISO/IEC 22989:2022", "AI concepts and terminology", "2022-07-01", "https://www.iso.org/standard/74296.html",
     "The shared vocabulary for AI standards: terms and concepts such as AI system, machine learning, "
     "trustworthiness and life cycle."),
    (ISO, "ISO/IEC 23053:2022", "Framework for AI systems using machine learning", "2022-06-01",
     "https://www.iso.org/standard/74438.html",
     "A framework describing the components and functions of AI systems that use machine learning."),
    (ISO, "ISO/IEC 5338:2023", "AI system life cycle processes", "2023-12-01", "https://www.iso.org/standard/81118.html",
     "Processes for defining, controlling and improving each stage of an AI system's life cycle."),
    (ISO, "ISO/IEC 5339:2024", "Guidance for AI applications", "2024-01-01", "https://www.iso.org/standard/81120.html",
     "Guidance for identifying the context, opportunities and stakeholders of AI applications."),
    (ISO, "ISO/IEC 38507:2022", "Governance implications of the use of AI by organizations", "2022-04-01",
     "https://www.iso.org/standard/56641.html",
     "Guidance for boards and governing bodies on overseeing their organisation's use of AI."),
    (ISO, "ISO/IEC TR 24028:2020", "Overview of trustworthiness in AI", "2020-05-01",
     "https://www.iso.org/standard/77608.html",
     "A technical report surveying what makes AI trustworthy: transparency, robustness, reliability, safety, "
     "security and privacy."),
    (ISO, "ISO/IEC TR 24027:2021", "Bias in AI systems and AI aided decision making", "2021-11-01",
     "https://www.iso.org/standard/77607.html",
     "A technical report on sources of bias in AI systems and ways to measure and address it."),
    (ISO, "ISO/IEC TR 24029-1:2021", "Assessment of the robustness of neural networks — Part 1: Overview", "2021-03-01",
     "https://www.iso.org/standard/77609.html",
     "A technical report on methods for assessing how robust neural networks are."),
    (ISO, "ISO/IEC 25059:2023", "Quality model for AI systems", "2023-06-01", "https://www.iso.org/standard/80655.html",
     "Extends the software quality model (SQuaRE) with characteristics specific to AI systems."),
    (ISO, "ISO/IEC 8183:2023", "Data life cycle framework", "2023-07-01", "https://www.iso.org/standard/83002.html",
     "The stages data goes through in AI systems, from collection and preparation to use and decommissioning."),
    (ISO, "ISO/IEC 5259-1:2024", "Data quality for analytics and machine learning — Part 1: Overview, terminology, and examples",
     "2024-07-01", "https://www.iso.org/standard/81088.html",
     "The first part of the series on data quality for analytics and machine learning: concepts, terms and examples."),
    (IEEE, "IEEE 7000-2021", "Model Process for Addressing Ethical Concerns during System Design", "2021-09-15",
     "https://standards.ieee.org/ieee/7000/6781/",
     "A process for identifying stakeholders' values and ethical concerns and building them into system design."),
    (IEEE, "IEEE 7001-2021", "Transparency of Autonomous Systems", "2022-03-04",
     "https://standards.ieee.org/ieee/7001/6929/",
     "Measurable, testable levels of transparency for autonomous systems, for users, overseers and investigators."),
    (IEEE, "IEEE 7003-2024", "Algorithmic Bias Considerations", "2025-01-24",
     "https://standards.ieee.org/ieee/7003/11357/",
     "Processes for identifying and reducing unwanted bias when creating algorithms, including AI systems."),
]


def cards() -> list[dict]:
    return [{"title": f"{number} — {title}", "summary": what, "url": url, "source": publisher,
             "category": "regulation", "action": "standard", "date": published, "jurisdictions": ["INTL"],
             "authors": [], "tags": ["Standards"], "_key": MARK + number.split(":")[0].split("-20")[0].replace(" ", "-")}
            for publisher, number, title, published, url, what in STANDARDS]


def sync(conn, fetcher=None, log=print) -> int:
    """Store the list (updating any entry whose facts were corrected). Returns how many are new."""
    # OECD.AI lists a few ISO and IEEE standards too; this list has them with their official pages and dates.
    conn.execute("DELETE FROM items WHERE source = 'OECD.AI' AND (title LIKE '%(ISO/IEC %' OR title LIKE '%(IEEE) Standard%')")
    added = 0
    for c in cards():
        key = c.pop("_key")
        if store.exists(conn, c["url"]):
            conn.execute("UPDATE items SET title = ?, summary = ?, date = ?, source = ?, category = 'regulation',"
                         " action = 'standard', jurisdictions = 'INTL', bill = ? WHERE id = ?",
                         (c["title"], c["summary"], c["date"], c["source"], key, store.item_id(c["url"])))
        elif store.insert(conn, c):
            conn.execute("UPDATE items SET bill = ? WHERE id = ?", (key, store.item_id(c["url"])))
            added += 1
    conn.commit()
    return added
