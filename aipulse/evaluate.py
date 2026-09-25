"""Score the keyword rules against hand-labelled stories (tests/fixtures/labels.csv).

    python -m aipulse evaluate

Each row has a headline, the story's lead text (blank when only a headline is known), the category
its feed starts it with, and the correct answer: category (tool / news / policy / regulation), and for
regulation the action (proposal / law) and jurisdictions. Labelling rules are in the file's header
comment in README.md ("Measuring the rules").
"""

from __future__ import annotations

import csv
from pathlib import Path

from . import classify
from .collect import apply_regulation

LABELS = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "labels.csv"


def load(path: Path = LABELS) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def predict(title: str, text: str, feed_default: str) -> dict:
    """What the collector would decide for this story (keyword rules only, no LLM)."""
    item = {"title": title, "summary": text, "category": classify.categorize(title, text, feed_default)}
    apply_regulation(item)
    # The labels are country-level; US state codes ("US-OR") are checked by their own tests.
    return {"category": item["category"], "action": item.get("action") or "",
            "jurisdictions": sorted(j for j in item.get("jurisdictions") or [] if not j.startswith("US-"))}


def evaluate(rows: list[dict] | None = None) -> dict:
    rows = load() if rows is None else rows
    report = {"n": len(rows), "mistakes": []}
    right_cat = tp = fp = fn = right_action = right_places = 0
    for r in rows:
        want_places = sorted(p for p in r["jurisdictions"].split(",") if p)
        got = predict(r["title"], r["text"], r["feed_default"])
        wrong = []
        if got["category"] == r["category"]:
            right_cat += 1
        else:
            wrong.append(f"category {got['category']} (want {r['category']})")
        is_reg, said_reg = r["category"] == "regulation", got["category"] == "regulation"
        tp += is_reg and said_reg
        fp += said_reg and not is_reg
        fn += is_reg and not said_reg
        if is_reg and said_reg:
            if got["action"] == r["action"]:
                right_action += 1
            else:
                wrong.append(f"action {got['action']} (want {r['action']})")
            if got["jurisdictions"] == want_places:
                right_places += 1
            else:
                wrong.append(f"places {','.join(got['jurisdictions'])} (want {','.join(want_places)})")
        if wrong:
            report["mistakes"].append({"title": r["title"], "wrong": wrong, "note": r.get("note", "")})
    report.update(
        category_accuracy=right_cat / len(rows),
        tracker_precision=tp / (tp + fp) if tp + fp else 1.0,
        tracker_recall=tp / (tp + fn) if tp + fn else 1.0,
        action_accuracy=right_action / tp if tp else 1.0,
        place_accuracy=right_places / tp if tp else 1.0,
    )
    return report


def print_report(report: dict) -> None:
    print(f"{report['n']} labelled stories")
    for key, label in [("category_accuracy", "Tab (category) accuracy"),
                       ("tracker_precision", "Tracker precision  (of stories put in the tracker, share that belong)"),
                       ("tracker_recall", "Tracker recall     (of stories that belong, share put in the tracker)"),
                       ("action_accuracy", "Action accuracy    (proposal vs law, on tracker hits)"),
                       ("place_accuracy", "Country accuracy   (exact set, on tracker hits)")]:
        print(f"  {label}: {report[key]:.0%}")
    print(f"\n{len(report['mistakes'])} stories with at least one mistake:")
    for m in report["mistakes"]:
        print(f"  - {m['title'][:90]}\n      {'; '.join(m['wrong'])}" + (f"  [{m['note']}]" if m["note"] else ""))
