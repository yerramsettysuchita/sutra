"""Layer 9 end to end.

    python -m engine.reconcile.run

Writes data/corpus/reconciliation_report.json.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from engine.reconcile.reconcile import report
from engine.console import configure as _configure_console

DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / "data" / "corpus"


def run(corpus_dir: Path, quiet: bool = False) -> dict:
    out: list[str] = []

    def emit(line: str = "") -> None:
        out.append(line)
        if not quiet:
            print(line)

    result = report(corpus_dir)
    totals = result["totals"]

    emit("=" * 78)
    emit("SUTRA  Layer 9  IPC to BNS reconciliation")
    emit("=" * 78)
    emit()
    emit(f"    window            {result['window']['from']} to {result['window']['to']}")
    emit(f"    transition        {result['transition']}")
    emit(f"    spans transition  {result['window']['spans_transition']}")
    emit(f"    cases before      {result['cases_before_transition']:>8,}")
    emit(f"    cases on or after {result['cases_on_or_after_transition']:>8,}")
    emit(f"    correspondences   {result['correspondences']:>8,}")

    emit()
    emit("-" * 78)
    emit("THE DAMAGE A NAIVE QUERY DOES")
    emit("-" * 78)
    emit()
    emit(f"    naive count, filtering on the section number as written"
         f"   {totals['naive_count']:>8,}")
    emit(f"    reconciled count, following the correspondence          "
         f"   {totals['reconciled_count']:>8,}")
    emit(f"    cases the naive query never sees                        "
         f"   {totals['naive_missed']:>8,}")
    emit()
    emit(f"    NAIVE UNDERCOUNT  {totals['naive_undercount_pct']:.2f}%")
    emit()
    emit("    An analyst asking for five years of one offence gets that share")
    emit("    of it, because the section number changed underneath the question")
    emit("    and nothing in the schema says so.")

    emit()
    emit("-" * 78)
    emit("THE AMBIGUOUS CODE HAZARD")
    emit("-" * 78)
    emit()
    for code, meanings in result["ambiguous_codes"].items():
        emit(f"    section number {code} means:")
        for meaning in meanings:
            emit(f"      {meaning}")
    emit()
    if result["offences_returning_the_wrong_offence"]:
        for entry in result["offences_returning_the_wrong_offence"]:
            emit(f"    section {entry['code']}, {entry['offence']}:"
                 f" {entry['wrong_offence_rows']:,} rows returned by the naive"
                 f" filter are a different offence entirely")
    else:
        emit("    This hazard does not manifest in this corpus. IPC 427, whose")
        emit("    successor number collides with IPC 324, has no cases here")
        emit("    because the generator's modus operandi families do not cover")
        emit("    mischief. The collision is real in the law and the guard is")
        emit("    built, but the measured harm from it in this run is zero and")
        emit("    is reported as zero.")

    emit()
    emit("-" * 78)
    emit("PER OFFENCE")
    emit("-" * 78)
    emit()
    emit(f"    {'IPC':>4} {'BNS':>4}  {'offence':<44} {'naive':>7} {'true':>7} {'miss %':>8}")
    emit()
    absent = 0
    for row in result["by_offence"]:
        if row["reconciled_count"] == 0:
            absent += 1
            continue
        emit(f"    {row['ipc']:>4} {row['bns']:>4}  {row['offence']:<44}"
             f" {row['naive_count']:>7,} {row['reconciled_count']:>7,}"
             f" {row['naive_undercount_pct']:>7.1f}%")
    if absent:
        emit()
        emit(f"    {absent} of {result['correspondences']} mapped offences have no")
        emit("    cases in this corpus, because the generator's modus operandi")
        emit("    families do not cover them. They are mapped and untested.")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **result,
    }
    (corpus_dir / "reconciliation_report.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8")
    (corpus_dir / "reconciliation_report.txt").write_text(
        "\n".join(out) + "\n", encoding="utf-8")

    emit()
    emit(f"    wrote {corpus_dir / 'reconciliation_report.json'}")
    return payload


def main() -> int:
    _configure_console()
    parser = argparse.ArgumentParser(description="Run Layer 9 reconciliation.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--from", dest="date_from", type=date.fromisoformat, default=None)
    parser.add_argument("--to", dest="date_to", type=date.fromisoformat, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    run(args.corpus, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
