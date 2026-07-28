"""Layer 9. Reconciled counting across the July 2024 boundary.

Two ways to count the same thing.

  naive        filter on the section number as written, which is what an
               analyst types and what a text to SQL system generates
  reconciled   filter on the offence, following Section.SuccessorSectionID
               across the boundary and respecting which Act was in force on
               the date of registration

The difference is the damage a naive query does. It is reported per offence
and never averaged into a single flattering figure.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from engine.reconcile.mapping import (
    BY_IPC,
    CORRESPONDENCES,
    TRANSITION,
    ambiguous_codes,
    equivalents,
)


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@dataclass
class Corpus:
    """Only what Layer 9 needs. Sections, their act, and the cases citing them."""

    case_date: dict[str, date]
    sections_of_case: dict[str, set[str]]     # CaseMasterID -> {"IPC:302", ...}
    codes_of_case: dict[str, set[str]]        # CaseMasterID -> {"302", ...}
    window: tuple[date, date]


def load(corpus_dir: Path) -> Corpus:
    acts = {a["ActID"]: a["ActAbbr"] for a in read_csv(corpus_dir / "Act.csv")}
    sections = {
        s["SectionID"]: (acts[s["ActID"]], s["SectionNo"])
        for s in read_csv(corpus_dir / "Section.csv")
    }
    cases = {
        c["CaseMasterID"]: date.fromisoformat(c["CrimeRegisteredDate"])
        for c in read_csv(corpus_dir / "CaseMaster.csv")
    }

    qualified: dict[str, set[str]] = defaultdict(set)
    bare: dict[str, set[str]] = defaultdict(set)
    for link in read_csv(corpus_dir / "ActSectionAssociation.csv"):
        act, number = sections[link["SectionID"]]
        qualified[link["CaseMasterID"]].add(f"{act}:{number}")
        bare[link["CaseMasterID"]].add(number)

    dates = sorted(cases.values())
    return Corpus(
        case_date=cases,
        sections_of_case=dict(qualified),
        codes_of_case=dict(bare),
        window=(dates[0], dates[-1]),
    )


def count(
    corpus: Corpus,
    code: str,
    date_from: date,
    date_to: date,
) -> dict:
    """Naive and reconciled counts for one offence over one window.

    Naive is a string match on the section number, which is what gets typed.
    Reconciled follows the correspondence and additionally requires the Act
    that was actually in force, which is what removes the ambiguous code
    problem rather than merely widening the net.
    """
    naive = 0
    reconciled = 0
    naive_wrong_offence = 0

    pair = equivalents(code)
    correspondence = BY_IPC.get(code)
    ipc_code = correspondence.ipc if correspondence else code
    bns_code = correspondence.bns if correspondence else code

    for case_id, when in corpus.case_date.items():
        if not (date_from <= when <= date_to):
            continue
        codes = corpus.codes_of_case.get(case_id, set())
        qualified = corpus.sections_of_case.get(case_id, set())

        if code in codes:
            naive += 1
            # The naive filter matched, but did it match the offence intended?
            # A pre transition IPC 324 and a post transition BNS 324 are
            # different offences sharing a number.
            wanted = f"{'IPC' if when < TRANSITION else 'BNS'}:{code}"
            if wanted not in qualified:
                naive_wrong_offence += 1

        # Reconciled. Before the boundary the offence is the IPC section,
        # after it the BNS successor. The Act qualifier is what makes this
        # exact rather than a fuzzy union of both numbers.
        wanted = f"IPC:{ipc_code}" if when < TRANSITION else f"BNS:{bns_code}"
        if wanted in qualified:
            reconciled += 1

    missed = reconciled - naive + naive_wrong_offence
    error = (naive - reconciled) / reconciled if reconciled else 0.0

    return {
        "code": code,
        "offence": correspondence.offence if correspondence else "unknown",
        "head": correspondence.head if correspondence else "unknown",
        "ipc": ipc_code,
        "bns": bns_code,
        "equivalents": sorted(pair),
        "naive_count": naive,
        "reconciled_count": reconciled,
        "naive_missed": max(missed, 0),
        "naive_wrong_offence": naive_wrong_offence,
        "naive_error_pct": round(error * 100, 4),
        "naive_undercount_pct": round(
            ((reconciled - naive) / reconciled * 100) if reconciled else 0.0, 4),
    }


def report(corpus_dir: Path,
           date_from: date | None = None,
           date_to: date | None = None) -> dict:
    corpus = load(corpus_dir)
    start = date_from or corpus.window[0]
    end = date_to or corpus.window[1]

    spans_boundary = start < TRANSITION <= end

    rows = [count(corpus, c.ipc, start, end) for c in CORRESPONDENCES]
    rows.sort(key=lambda r: -r["reconciled_count"])

    total_naive = sum(r["naive_count"] for r in rows)
    total_reconciled = sum(r["reconciled_count"] for r in rows)
    total_error = (
        (total_naive - total_reconciled) / total_reconciled if total_reconciled else 0.0
    )

    before = sum(1 for d in corpus.case_date.values()
                 if start <= d <= end and d < TRANSITION)
    after = sum(1 for d in corpus.case_date.values()
                if start <= d <= end and d >= TRANSITION)

    ambiguous = ambiguous_codes()
    ambiguous_rows = [r for r in rows if r["naive_wrong_offence"] > 0]

    return {
        "window": {"from": start.isoformat(), "to": end.isoformat(),
                   "spans_transition": spans_boundary},
        "transition": TRANSITION.isoformat(),
        "cases_before_transition": before,
        "cases_on_or_after_transition": after,
        "correspondences": len(CORRESPONDENCES),
        "totals": {
            "naive_count": total_naive,
            "reconciled_count": total_reconciled,
            "naive_missed": total_reconciled - total_naive,
            "naive_error_pct": round(total_error * 100, 4),
            "naive_undercount_pct": round(
                ((total_reconciled - total_naive) / total_reconciled * 100)
                if total_reconciled else 0.0, 4),
        },
        "ambiguous_codes": ambiguous,
        "offences_returning_the_wrong_offence": [
            {"code": r["code"], "offence": r["offence"],
             "wrong_offence_rows": r["naive_wrong_offence"]}
            for r in ambiguous_rows
        ],
        "by_offence": rows,
    }
