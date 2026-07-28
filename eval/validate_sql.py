"""Execute every gold SQL query against the real database.

    python -m eval.validate_sql

Writes eval/sql_validation.json.

WHY

The question set's headline claim is that 76 of 150 questions cannot be
answered on the KSP schema as supplied. Until this file existed, that claim
rested on whether the query *text* mentioned a resolved table. The queries had
never been parsed, let alone run.

WHAT IS CHECKED, AND WHAT EACH CHECK PROVES

  1. Every query parses and executes against the schema.
     Proves the SQL is real SQL over real columns, not plausible looking text.

  2. Every query marked `requires_person_key` FAILS when the resolved tables
     are removed, and every query not so marked still SUCCEEDS.
     This is the important one. It turns the headline from a statement about
     what we wrote into a statement the database enforces. A question is
     unanswerable on the raw schema when the raw schema literally cannot run
     it, and here that is demonstrated rather than asserted.

  3. No query reads a protected column.
     The policy guard, applied to queries this project ships as exemplary.

Parameters are bound with values drawn from the corpus, so a query that
references a column that does not exist fails loudly rather than returning an
empty set for the wrong reason.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import yaml

from engine.console import configure as _configure_console

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "gold" / "questions.yaml"
OUT = ROOT / "eval" / "sql_validation.json"
DEFAULT_CORPUS = ROOT / "data" / "corpus"

RESOLVED_TABLES = ("resolved_identity", "resolved_victim", "resolved_complainant")
PROTECTED = ("CasteID", "ReligionID", "OccupationID")


def parameters(conn: sqlite3.Connection) -> dict[str, object]:
    """Real values from the corpus, so a bad column name cannot hide."""
    def one(sql: str, fallback):
        try:
            row = conn.execute(sql).fetchone()
            return row[0] if row and row[0] is not None else fallback
        except sqlite3.Error:
            return fallback

    districts = [r[0] for r in conn.execute(
        "SELECT DistrictName FROM District LIMIT 2").fetchall()] or ["A", "B"]
    return {
        "district": districts[0],
        "district_a": districts[0],
        "district_b": districts[-1],
        "district_id": one("SELECT DistrictID FROM District LIMIT 1", 1),
        "station": one("SELECT UnitName FROM Unit LIMIT 1", "Station"),
        "identity": one("SELECT ResolvedIdentityID FROM resolved_identity LIMIT 1",
                        "R000001"),
        "case_id": one("SELECT CaseMasterID FROM CaseMaster LIMIT 1", 1),
        "accused_id": one("SELECT AccusedMasterID FROM Accused LIMIT 1", 1),
        "name": one("SELECT AccusedName FROM Accused LIMIT 1", "X"),
        "prefix": "S",
        "head": one("SELECT CrimeHeadName FROM CrimeHead LIMIT 1", "Theft"),
        "offence": one("SELECT CrimeSubHeadName FROM CrimeSubHead LIMIT 1", "Theft"),
        "section": one("SELECT SectionNumber FROM Section LIMIT 1", "379"),
        "ipc_section": "379",
        "bns_section": "303",
        "from_date": "2021-01-01",
        "to_date": "2026-12-31",
        "as_of": "2026-06-30",
        "minimum": 2,
        "recent": "2025",
        "baseline": "2024",
    }


def bind(sql: str, values: dict[str, object]) -> tuple[str, list]:
    """Rewrite :named parameters into positional ones, in order of appearance."""
    order: list[object] = []

    def replace(match: re.Match) -> str:
        key = match.group(1)
        order.append(values.get(key))
        return "?"

    return re.sub(r":(\w+)", replace, sql), order


def strip_resolved(conn: sqlite3.Connection) -> None:
    """Make the database the raw KSP schema, with nothing SUTRA added."""
    for table in RESOLVED_TABLES:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()


def run_one(conn: sqlite3.Connection, sql: str, values: dict) -> tuple[bool, str]:
    statement, args = bind(sql, values)
    try:
        conn.execute(statement, args).fetchmany(5)
        return True, ""
    except sqlite3.Error as error:
        return False, f"{type(error).__name__}: {error}"


def main() -> int:
    _configure_console()
    parser = argparse.ArgumentParser(description="Execute every gold SQL query.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    db = args.corpus / "sutra.db"
    if not db.exists():
        raise SystemExit(f"{db} not found, run: python -m eval.build_db")

    questions = yaml.safe_load(GOLD.read_text(encoding="utf-8"))["questions"]

    full = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    values = parameters(full)

    # A second, writable copy with the resolved tables dropped. This is the raw
    # KSP schema exactly as supplied.
    raw = sqlite3.connect(":memory:")
    full.backup(raw)
    strip_resolved(raw)

    results = []
    for q in questions:
        ok_full, error_full = run_one(full, q["sql"], values)
        ok_raw, error_raw = run_one(raw, q["sql"], values)
        protected = [c for c in PROTECTED if re.search(rf"\b{c}\b", q["sql"])]
        results.append({
            "id": q["id"],
            "shape": q["shape"],
            "requires_person_key": q["requires_person_key"],
            "runs_on_full_schema": ok_full,
            "error_on_full_schema": error_full,
            "runs_on_raw_ksp_schema": ok_raw,
            "error_on_raw_ksp_schema": error_raw,
            "reads_protected_column": protected,
        })

    executes = [r for r in results if r["runs_on_full_schema"]]
    broken = [r for r in results if not r["runs_on_full_schema"]]
    # The claim, enforced by the database rather than by us.
    claimed = [r for r in results if r["requires_person_key"]]
    confirmed = [r for r in claimed if not r["runs_on_raw_ksp_schema"]]
    contradicted = [r for r in claimed if r["runs_on_raw_ksp_schema"]]
    not_claimed = [r for r in results if not r["requires_person_key"]]
    wrongly_broken = [r for r in not_claimed if not r["runs_on_raw_ksp_schema"]]
    protected_leaks = [r for r in results if r["reads_protected_column"]]

    if not args.quiet:
        print("=" * 78)
        print("GOLD SQL VALIDATION, every query executed")
        print("=" * 78)
        print()
        print(f"    queries                                  {len(results):>6,}")
        print(f"    execute against the full schema          {len(executes):>6,}")
        print(f"    fail to execute                          {len(broken):>6,}")
        print()
        print("    The claim, checked by the database rather than by us")
        print()
        print(f"    marked as needing a cross FIR person key {len(claimed):>6,}")
        print(f"      of those, genuinely fail on raw KSP    {len(confirmed):>6,}")
        print(f"      of those, actually run on raw KSP      {len(contradicted):>6,}"
              f"   <- would falsify the claim")
        print()
        print(f"    not so marked                            {len(not_claimed):>6,}")
        print(f"      of those, fail on raw KSP anyway       {len(wrongly_broken):>6,}"
              f"   <- would mean we undercounted")
        print()
        print(f"    queries reading a protected column       {len(protected_leaks):>6,}")
        print()
        for r in broken[:10]:
            print(f"    BROKEN {r['id']}  {r['error_on_full_schema'][:90]}")
        for r in contradicted[:10]:
            print(f"    CONTRADICTED {r['id']}  runs without the resolved tables")
        for r in wrongly_broken[:10]:
            print(f"    UNDERCOUNTED {r['id']}  {r['error_on_raw_ksp_schema'][:70]}")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "database": str(db.relative_to(ROOT)),
        "total": len(results),
        "execute_on_full_schema": len(executes),
        "fail_to_execute": len(broken),
        "requires_person_key_claimed": len(claimed),
        "requires_person_key_confirmed_by_database": len(confirmed),
        "requires_person_key_contradicted": len(contradicted),
        "unmarked_but_failing_on_raw_schema": len(wrongly_broken),
        "queries_reading_protected_columns": len(protected_leaks),
        "verdict": (
            "every query executes, and every question marked as needing a cross "
            "FIR person key is one the raw KSP schema cannot run"
            if not broken and not contradicted and not wrongly_broken
            else "validation failed, see results"
        ),
        "results": results,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not args.quiet:
        print(f"    wrote {OUT.relative_to(ROOT)}")

    failed = bool(broken or contradicted or wrongly_broken or protected_leaks)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
