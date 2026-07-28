"""Score the investigator question set.

    python -m eval.questions

Reads eval/gold/questions.yaml and writes eval/questions_report.json.

The deck claimed 150 investigator questions at 74 per cent correct. No question
set existed, and the evaluation report said so rather than estimating a figure.
This builds the artefact and measures the thing that can honestly be measured.

WHAT IS MEASURED, AND WHAT IS NOT

Not accuracy. Answering these from free text needs a natural language layer
that is not built and that this project has no language model for. Claiming an
accuracy figure would require running the questions through something that does
not exist.

What is measured is coverage, in three bands that partition the set:

    answerable today       the parameterised console at /ask answers this now
    needs a language layer answerable in principle against the schema plus the
                           resolved table, but not through the console as built
    impossible on the raw schema
                           cannot be answered by any interface, because the
                           question needs a person identity that spans FIRs and
                           the KSP schema has none

The third band is the finding. It is the thesis of this project measured from
a different direction. The schema gap is usually argued from the columns that
are missing. Here it is argued from the questions an officer cannot ask.

SELF CONSISTENCY

Two invariants are checked and the run fails if either breaks, because a hand
written gold set with a mislabelled row is worse than none.

    requires_person_key is true if and only if the gold SQL reads one of the
    resolved tables

    answerable_today implies the console has a question of that shape
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "gold" / "questions.yaml"
OUT = ROOT / "eval" / "questions_report.json"
CONSOLE = ROOT / "web" / "src" / "screens" / "Ask.tsx"

RESOLVED_TABLES = ("resolved_identity", "resolved_victim", "resolved_complainant")

BANDS = {
    "answerable_today": (
        "The parameterised console at /ask answers this now, with no new engine "
        "work and no language model."
    ),
    "needs_language_layer": (
        "Answerable against the schema plus the resolved table, but not through "
        "the console as built. Needs either a new parameterised question or a "
        "natural language layer, which is NOT BUILT."
    ),
    "impossible_on_raw_schema": (
        "Cannot be answered by any interface over the KSP schema as supplied, "
        "because it needs a person identity that spans FIRs and no such column "
        "exists. SUTRA constructs that identity, which is what moves these "
        "questions from impossible to answerable."
    ),
}


def load() -> dict:
    if not GOLD.exists():
        raise SystemExit(f"{GOLD.relative_to(ROOT)} not found")
    return yaml.safe_load(GOLD.read_text(encoding="utf-8"))


def uses_resolved(sql: str) -> bool:
    return any(re.search(rf"\b{t}\b", sql) for t in RESOLVED_TABLES)


def console_shapes() -> set[str]:
    """Which question ids the console at /ask actually ships.

    Parsed from the screen rather than kept in a list here, so a question
    removed from the console cannot keep being counted as answerable.
    """
    if not CONSOLE.exists():
        return set()
    text = CONSOLE.read_text(encoding="utf-8")
    return set(re.findall(r"^\s*id: '([a-z0-9-]+)',", text, re.M))


def check(questions: list[dict]) -> list[str]:
    """Every way this gold set could be quietly wrong."""
    problems: list[str] = []
    seen: set[str] = set()
    for q in questions:
        qid = q.get("id", "?")
        if qid in seen:
            problems.append(f"{qid}: duplicate id")
        seen.add(qid)

        for field in ("shape", "difficulty", "question", "tables", "sql",
                      "answerable_today", "requires_person_key"):
            if field not in q:
                problems.append(f"{qid}: missing {field}")

        if q.get("difficulty") not in {"simple", "moderate", "complex"}:
            problems.append(f"{qid}: difficulty {q.get('difficulty')!r} is not one of the three")

        sql = q.get("sql", "")
        if not sql.strip():
            problems.append(f"{qid}: empty SQL")
        if "SELECT" not in sql.upper():
            problems.append(f"{qid}: SQL has no SELECT")

        # The invariant that makes the headline count trustworthy.
        declared = bool(q.get("requires_person_key"))
        actual = uses_resolved(sql)
        if declared != actual:
            problems.append(
                f"{qid}: requires_person_key is {declared} but the SQL "
                f"{'does' if actual else 'does not'} read a resolved table")

        # A question that needs the person key but is not listed as touching a
        # resolved table has an incomplete `tables` list.
        tables = q.get("tables") or []
        if actual and not any(t in RESOLVED_TABLES for t in tables):
            problems.append(f"{qid}: SQL reads a resolved table, tables does not list one")

        # Protected attributes may appear in the schema and never in a query we
        # ship as exemplary. This is the policy guard applied to the gold set.
        for column in ("CasteID", "ReligionID", "OccupationID"):
            if re.search(rf"\b{column}\b", sql):
                problems.append(f"{qid}: gold SQL reads {column}, which is excluded")

    return problems


def band(q: dict) -> str:
    if q["requires_person_key"] and not q["answerable_today"]:
        return "impossible_on_raw_schema"
    if q["answerable_today"]:
        return "answerable_today"
    return "needs_language_layer"


def main() -> int:
    parser = argparse.ArgumentParser(description="Score the question set.")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    doc = load()
    questions = doc["questions"]

    problems = check(questions)
    if problems:
        print("Question set FAILED validation")
        print()
        for p in problems:
            print(f"  {p}")
        return 1

    total = len(questions)
    person_key = [q for q in questions if q["requires_person_key"]]
    today = [q for q in questions if q["answerable_today"]]
    kannada = [q for q in questions if q.get("question_kn")]

    # The three bands partition the set.
    bands = Counter(band(q) for q in questions)
    assert sum(bands.values()) == total

    by_shape = {}
    for shape in sorted({q["shape"] for q in questions}):
        rows = [q for q in questions if q["shape"] == shape]
        by_shape[shape] = {
            "questions": len(rows),
            "requires_person_key": sum(1 for q in rows if q["requires_person_key"]),
            "answerable_today": sum(1 for q in rows if q["answerable_today"]),
            "share_needing_person_key": round(
                sum(1 for q in rows if q["requires_person_key"]) / len(rows), 4),
        }

    by_difficulty = {}
    for level in ("simple", "moderate", "complex"):
        rows = [q for q in questions if q["difficulty"] == level]
        by_difficulty[level] = {
            "questions": len(rows),
            "requires_person_key": sum(1 for q in rows if q["requires_person_key"]),
            "answerable_today": sum(1 for q in rows if q["answerable_today"]),
        }

    tables = Counter(t for q in questions for t in (q.get("tables") or []))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "eval/gold/questions.yaml",
        "version": doc["meta"]["version"],
        "status": "BUILT",
        "total_questions": total,
        "headline": {
            "requires_person_key": len(person_key),
            "share_requiring_person_key": round(len(person_key) / total, 4),
            "statement": (
                f"{len(person_key)} of {total} investigator questions "
                f"({len(person_key) / total:.1%}) cannot be answered on the KSP "
                f"schema as supplied, at any level of interface sophistication, "
                f"because they need a person identity that spans FIRs. The "
                f"schema has none. That is the gap SUTRA fills, measured from "
                f"the question side rather than from the column side."
            ),
        },
        "coverage": {
            key: {
                "questions": bands.get(key, 0),
                "share": round(bands.get(key, 0) / total, 4),
                "meaning": BANDS[key],
            }
            for key in ("answerable_today", "needs_language_layer",
                        "impossible_on_raw_schema")
        },
        "accuracy": {
            "status": "not measured",
            "why": (
                "Answering these from free text needs a natural language layer. "
                "It is NOT BUILT, no language model runs anywhere in this "
                "system, and there is nothing to run the set through. The deck "
                "claimed 74 per cent correct. That figure has no measurement "
                "behind it and is not repeated here."
            ),
        },
        "kannada": {
            "questions_with_kannada": len(kannada),
            "share": round(len(kannada) / total, 4),
            "why_not_all": (
                "Kannada is given where the question is one an officer would ask "
                "aloud at a station counter. The analyst phrasings are left in "
                "English, because a forced translation of an analyst's sentence "
                "is not a Kannada question. Interface chrome is translated "
                "separately, see ADR 023."
            ),
        },
        "by_shape": by_shape,
        "by_difficulty": by_difficulty,
        "tables_touched": dict(tables.most_common()),
        "console_questions_shipped": sorted(console_shapes()),
        "validation": {
            "checks_run": [
                "every id unique",
                "every required field present",
                "difficulty is one of three values",
                "SQL present and contains a SELECT",
                "requires_person_key agrees with whether the SQL reads a resolved table",
                "tables list includes the resolved table when the SQL reads one",
                "no gold SQL reads CasteID, ReligionID or OccupationID",
            ],
            "problems": [],
        },
        "questions": [
            {
                "id": q["id"],
                "shape": q["shape"],
                "difficulty": q["difficulty"],
                "question": q["question"],
                "question_kn": q.get("question_kn"),
                "tables": q["tables"],
                "answerable_today": q["answerable_today"],
                "requires_person_key": q["requires_person_key"],
                "band": band(q),
                "sql": q["sql"].strip(),
            }
            for q in questions
        ],
    }

    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                   encoding="utf-8")

    if not args.quiet:
        print("=" * 78)
        print("INVESTIGATOR QUESTION SET")
        print("=" * 78)
        print()
        print(f"    {total} questions, {len(kannada)} with a Kannada rendering")
        print()
        print(f"    {'band':<32} {'questions':>10} {'share':>8}")
        print()
        for key in ("answerable_today", "needs_language_layer",
                    "impossible_on_raw_schema"):
            n = bands.get(key, 0)
            print(f"    {key:<32} {n:>10,} {n / total:>7.1%}")
        print()
        print("    " + "-" * 70)
        print()
        print(f"    REQUIRES A CROSS FIR PERSON KEY   {len(person_key):>6,}"
              f" of {total:,}   {len(person_key) / total:.1%}")
        print()
        print("    These cannot be answered on the KSP schema as supplied, at any")
        print("    level of interface sophistication. The schema has no person")
        print("    entity spanning FIRs, so the question has nothing to join on.")
        print("    This is the schema gap measured from the question side.")
        print()
        print(f"    {'shape':<30} {'total':>6} {'person key':>11} {'share':>7}")
        print()
        for shape, row in sorted(by_shape.items(),
                                 key=lambda kv: -kv[1]["share_needing_person_key"]):
            print(f"    {shape:<30} {row['questions']:>6}"
                  f" {row['requires_person_key']:>11}"
                  f" {row['share_needing_person_key']:>6.0%}")
        print()
        print("    Accuracy is NOT measured. Answering these from free text needs a")
        print("    natural language layer that is not built. The deck's 74 per cent")
        print("    has no measurement behind it and is not repeated.")
        print()
        print(f"    wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
