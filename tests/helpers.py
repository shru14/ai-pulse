"""Helpers more than one test file uses."""
import re
from pathlib import Path

from aipulse import store

FIX = Path(__file__).parent / "fixtures"


# --- Server-side search and paging ---
def _seed(conn, rows):
    """Insert (title, source, category, extra) rows dated today, then store card grouping."""
    from datetime import date
    from aipulse import cluster
    for n, (title, src, cat, extra) in enumerate(rows):
        store.insert(conn, {"title": title, "summary": extra.get("summary", ""), "url": f"https://x.com/{n}",
                            "source": src, "category": cat, "date": date.today().isoformat(),
                            "tags": extra.get("tags", []), "jurisdictions": extra.get("jurisdictions", []),
                            "action": extra.get("action")})
    conn.commit()
    cluster.assign(conn, days=None)


# ---------- The weekly briefing (in testing): vectors, hybrid search, the briefing ----------

def _fake_embedder(monkeypatch):
    """Stand-in for the model: a story's vector counts a few words, so stories sharing them sit close."""
    import numpy as np
    from aipulse import embed
    axes = ["water", "cooling", "data", "centre", "chip", "export", "china", "act", "eu", "fine", "model", "launch"]

    def encode(texts, query=False):
        out = np.zeros((len(texts), embed.DIM), dtype=np.float32)
        for k, t in enumerate(texts):
            words = re.findall(r"\w+", t.lower())
            v = out[k]
            v[len(axes)] = 0.25  # what every story has in common
            for w in words:
                if w in axes:
                    v[axes.index(w)] += 1
            out[k] = v / np.linalg.norm(v)
        return out
    monkeypatch.setattr(embed, "encode", encode)
    monkeypatch.setattr(embed, "available", lambda: True)
    monkeypatch.setattr(embed, "DAYS", 10 ** 5)  # the tests' stories have fixed dates, whatever today is


def _story(conn, n, title, day, summary="", source="S", category="infra"):
    store.insert(conn, {"title": title, "summary": summary, "url": f"https://ex.com/{n}", "source": source,
                        "category": category, "date": day, "tags": []})
