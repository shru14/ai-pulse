"""Brazil: bills in the Chamber of Deputies, from its open data API."""
from __future__ import annotations

import re
import time
from datetime import date, timedelta

from .. import feeds, translate

from .core import ENDED, STAGES, _get_json, connect_tables, retitle, upsert


# --- Brazil (Câmara dos Deputados) ---

BR_API = "https://dadosabertos.camara.leg.br/api/v2"


BR_KEYWORD = "intelig%C3%AAncia%20artificial"


BR_AI = re.compile(r"intelig[êe]ncia artificial|\bIA\b|algor[íi]tm|deep ?fakes?|aprendizado de m[áa]quina|"
                   r"decis[õo]es automatizadas", re.I)


BR_ATTACHED = ("Tramitando em Conjunto", "Aguardando Apensação")


BR_DATA = (("PL", 4060, 2012),)  # the bill that became the LGPD (Law 13.709/2018), Brazil's data protection law


# Stages from an event's own description and dispatch. (The API stamps every event's "situation" with the
# bill's current status, so it says nothing about when a stage was reached.) First match wins.
_BR_RULES = [
    ("signed", re.compile(r"Transforma(do|ção) (em Norma Jurídica|na Lei)", re.I)),
    ("vetoed", re.compile(r"Vetad[oa] totalmente|Veto Total", re.I)),
    ("passed_legislature", re.compile(r"remessa à sanção|Remessa à Sanção|enviad[oa] à sanção", re.I)),
    ("passed_chamber", re.compile(r"Remessa ao Senado Federal|vai ao Senado Federal|"
                                  r"Recebido o Of[íi]cio .{0,40}do Senado Federal que submete à revisão", re.I)),
    ("withdrawn", re.compile(r"^(Retirada pel[oa]|Arquivamento)", re.I)),  # matched on the description only
]


def br_history(presented: str, events: list[dict]) -> list[dict]:
    """Lifecycle from a proposal's procedural events (tramitações). A bill that reached the Chamber from the
    Senate starts at "passed first chamber" (the day it arrived)."""
    reached: dict[str, dict] = {}
    from_senate = False
    for e in sorted(events, key=lambda e: e.get("dataHora") or ""):
        when = (e.get("dataHora") or "")[:10]
        what = e.get("descricaoTramitacao") or ""
        text = f"{what} | {e.get('despacho') or ''}"
        for stage, rule in _BR_RULES:
            if when and rule.search(what if stage == "withdrawn" else text):
                if stage == "passed_chamber" and "submete à revisão" in text and "introduced" not in reached:
                    from_senate = True
                reached.setdefault(stage, {"date": when, "stage": stage, "text": what[:200]})
                break
    if presented and not from_senate:
        reached.setdefault("introduced", {"date": presented[:10], "stage": "introduced", "text": "Apresentação"})
    if "withdrawn" in reached and any(s in reached for s in ("signed", "vetoed")):
        del reached["withdrawn"]  # a law is archived as a matter of course afterwards
    return sorted(reached.values(), key=lambda h: (h["date"], (STAGES + ENDED).index(h["stage"])))


def sync_brazil(conn, fetcher=feeds.fetch, log=print) -> int:
    """AI bills in Brazil's Chamber of Deputies: since 2023 on the first run, then those with any activity
    since the last run."""
    connect_tables(conn)
    if fetcher is feeds.fetch:  # the Chamber's API is slow to answer from abroad
        fetcher = lambda u: feeds.fetch(u, timeout=90)
    last = conn.execute("SELECT value FROM meta WHERE key = 'brazil_sync'").fetchone()
    started = date.today().isoformat()
    window = (f"dataInicio={(date.fromisoformat(last[0]) - timedelta(days=2)).isoformat()}" if last
              else "dataApresentacaoInicio=2023-01-01")
    found, page = [], 1
    while True:
        data = _get_json(f"{BR_API}/proposicoes?keywords={BR_KEYWORD}&{window}&itens=100&pagina={page}"
                         "&ordem=DESC&ordenarPor=id", fetcher)
        found += [p for p in data.get("dados", []) if p.get("siglaTipo") in ("PL", "PLP", "PEC")
                  and BR_AI.search(p.get("ementa") or "")]
        if not any(l.get("rel") == "next" for l in data.get("links", [])):
            break
        page += 1
        time.sleep(0.5)
    for kind, number, year in BR_DATA:
        if not conn.execute("SELECT 1 FROM bills WHERE key = ?", (f"BR-{kind}-{number}-{year}",)).fetchone():
            found += _get_json(f"{BR_API}/proposicoes?siglaTipo={kind}&numero={number}&ano={year}", fetcher).get("dados", [])
    translate.english(conn, "pt", [(p.get("ementa") or "").strip() for p in found])
    changed = 0
    for p in found:
        detail = _get_json(f"{BR_API}/proposicoes/{p['id']}", fetcher)["dados"]
        status = (detail.get("statusProposicao") or {}).get("descricaoSituacao") or ""
        if status in BR_ATTACHED:
            continue
        events = _get_json(f"{BR_API}/proposicoes/{p['id']}/tramitacoes", fetcher).get("dados", [])
        history = br_history(detail.get("dataApresentacao") or "", events)
        number = f"{p['siglaTipo']} {p['numero']}/{p['ano']}"
        bill = {"key": f"BR-{p['siglaTipo']}-{p['numero']}-{p['ano']}", "jurisdiction": "BR", "number": number,
                "title": (p.get("ementa") or "").strip(),
                "url": f"https://www.camara.leg.br/propostas-legislativas/{p['id']}",
                "source": "Câmara dos Deputados", "history": history, "lang": "pt"}
        if history:
            changed += upsert(conn, bill)
        conn.commit()
        time.sleep(0.5)
    conn.execute("INSERT OR REPLACE INTO meta VALUES ('brazil_sync', ?)", (started,))
    conn.commit()
    retitle(conn, "BR", "pt")
    return changed
