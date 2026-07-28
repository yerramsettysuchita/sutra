"""Build the corpus into a real SQLite database.

    python -m eval.build_db

Writes data/corpus/sutra.db.

WHY THIS EXISTS

`data/schema/ksp_schema.sql` was written in the first session, is the schema
every claim in this project is made against, and until now was read by no code
at all. It was documentation shaped like a program.

Worse, `eval/gold/questions.yaml` holds 150 hand written SQL queries and the
headline claim drawn from them is that 76 cannot be answered on this schema.
That claim was checked by looking at whether the query *text* mentioned a
resolved table. Nobody had ever executed one. A gold set of 150 unparsed
queries is a document, not an artefact.

This loads the DDL, loads every CSV into it, and adds the three tables SUTRA
constructs. `eval/validate_sql.py` then runs all 150 against it.

The database is a build output. It is never queried by the engine, never
shipped to Catalyst, and never used to compute a metric. The engine reads CSVs
exactly as before. This exists so the SQL can be proved to run.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
from pathlib import Path

from engine.console import configure as _configure_console

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "data" / "schema" / "ksp_schema.sql"
DEFAULT_CORPUS = ROOT / "data" / "corpus"

# The tables SUTRA adds. Not in the KSP schema, which is the entire point.
ADDED = """
CREATE TABLE resolved_identity (
    AccusedMasterID    INTEGER PRIMARY KEY,
    CaseMasterID       INTEGER NOT NULL,
    ResolvedIdentityID TEXT    NOT NULL
);
CREATE INDEX ix_ri_identity ON resolved_identity(ResolvedIdentityID);

CREATE TABLE resolved_victim (
    VictimID           INTEGER PRIMARY KEY,
    CaseMasterID       INTEGER NOT NULL,
    ResolvedIdentityID TEXT    NOT NULL
);

CREATE TABLE resolved_complainant (
    ComplainantID      INTEGER PRIMARY KEY,
    CaseMasterID       INTEGER NOT NULL,
    ResolvedIdentityID TEXT    NOT NULL
);
"""


def table_names(ddl: str) -> list[str]:
    return re.findall(r"CREATE TABLE (\w+)", ddl)


def load_csv(conn: sqlite3.Connection, table: str, path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return 0

    # Only load columns the DDL declares. The CSV and the DDL agree today and a
    # test asserts it, but loading positionally would fail silently the day a
    # column moves.
    declared = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    columns = [c for c in declared if c in rows[0]]
    placeholders = ",".join("?" for _ in columns)
    conn.executemany(
        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})",
        [tuple(r[c] if r[c] != "" else None for c in columns) for r in rows],
    )
    return len(rows)


def build(corpus_dir: Path, quiet: bool = False) -> Path:
    target = corpus_dir / "sutra.db"
    target.unlink(missing_ok=True)

    ddl = SCHEMA.read_text(encoding="utf-8")
    conn = sqlite3.connect(target)
    conn.executescript(ddl)
    conn.executescript(ADDED)

    loaded: dict[str, int] = {}
    for table in table_names(ddl):
        loaded[table] = load_csv(conn, table, corpus_dir / f"{table}.csv")

    # The resolved tables, from what the engine actually wrote.
    resolved = corpus_dir / "resolved_identities.csv"
    if resolved.exists():
        with resolved.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        conn.executemany(
            "INSERT INTO resolved_identity "
            "(AccusedMasterID, CaseMasterID, ResolvedIdentityID) VALUES (?,?,?)",
            [(r["AccusedMasterID"], r["CaseMasterID"], r["ResolvedIdentityID"])
             for r in rows])
        loaded["resolved_identity"] = len(rows)

    conn.commit()
    if not quiet:
        print(f"built {target}")
        for table, count in sorted(loaded.items()):
            if count:
                print(f"    {table:<26} {count:>8,} rows")
        empty = [t for t, c in loaded.items() if not c]
        if empty:
            print(f"    empty, no CSV: {', '.join(sorted(empty))}")
    conn.close()
    return target


def main() -> int:
    _configure_console()
    parser = argparse.ArgumentParser(description="Build the corpus into SQLite.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    build(args.corpus, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
