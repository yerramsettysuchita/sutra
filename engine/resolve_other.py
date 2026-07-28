"""The same engine, run over Victim and ComplainantDetails.

    python -m engine.resolve_other

Writes data/corpus/other_persons_report.json.

WHY THIS EXISTS

Accused is not the only table in the KSP schema that holds a person without a
person key. Victim and ComplainantDetails have exactly the same gap. The deck
says so in one line and it had never been measured, so the claim was an
assertion.

This runs the engine that already exists. Not a variant of it, not a second
implementation. Layers 1, 2, 3, 4 and 5 are imported from the same modules the
accused pipeline uses, so a figure here is comparable to a figure there by
construction rather than by assurance.

WHAT DIFFERS BETWEEN THE THREE TABLES, AND WHY THAT IS THE POINT

Neither victims nor complainants have an arresting officer, and each FIR names
at most one complainant, so the relational signal has nothing to compute from
on either table. It reports as NOT_COMPUTABLE and Layer 4 already forces the
weight of an unobserved level to zero, so nothing has to be special cased. That
is a property of the design and it is worth stating that it held.

The complainant row carries an Address and a PhoneNumber. The accused row
carries neither. The schema file itself comments on that asymmetry and calls it
the direct cause of the identity gap. Measuring all three tables through one
engine turns that comment into a number.

THE POLICY GUARD, EXERCISED HERE EXPLICITLY

Victim carries CasteID, ReligionID and OccupationID. Accused carries them too,
but this is the first table where the protected columns sit next to a person we
are actively trying to identify, and a caste field is exactly the sort of thing
that gets quietly added to a similarity function because it improves a number.

So the guard is not merely called here, it is demonstrated. The run asserts
that the raw Victim header would be rejected, then projects the permitted
columns, then asserts the projection passes. If someone deletes the projection
the first assertion still fails the run.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from engine.block.candidates import Records, candidate_pairs, read_csv
from engine.cluster import correlation
from engine.features import extract as fx
from engine.features import signals as S
from engine.features.signals import LEVELS, MODEL_SIGNALS
from engine.linkage import fellegi_sunter as fs
from engine.normalise.indic import normalise
from engine.policy import ExcludedFeatureError, assert_no_excluded_features
from engine.console import configure as _configure_console

DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus"


@dataclass(frozen=True)
class TableSpec:
    """One person bearing table, described the same way for all three."""

    key: str
    table: str
    row_id: str
    name_column: str
    truth_file: str
    # Columns that may reach the feature path. Everything else on the row is
    # display or provenance and is never read by a model.
    permitted: tuple[str, ...]
    note: str


SPECS = {
    "victim": TableSpec(
        key="victim",
        table="Victim.csv",
        row_id="VictimID",
        name_column="VictimName",
        truth_file="victim_identity_map.csv",
        permitted=("VictimID", "CaseMasterID", "PersonID", "VictimName",
                   "AgeYear", "GenderID"),
        note=("Carries CasteID, ReligionID and OccupationID, none of which is "
              "read. No arresting officer and no address, so this table has "
              "strictly less identifying information than Accused."),
    ),
    "complainant": TableSpec(
        key="complainant",
        table="ComplainantDetails.csv",
        row_id="ComplainantID",
        name_column="ComplainantName",
        truth_file="complainant_identity_map.csv",
        permitted=("ComplainantID", "CaseMasterID", "ComplainantName",
                   "AgeYear", "GenderID", "Address", "PhoneNumber",
                   "RelationToVictim"),
        note=("Carries an Address and a PhoneNumber, which Accused does not. "
              "The schema comments on that asymmetry itself. This is the easy "
              "table and Accused is the hard one."),
    ),
}


def contact_levels(records: Records, spec: TableSpec,
                   pair_a: np.ndarray, pair_b: np.ndarray) -> dict[str, np.ndarray]:
    """Phone and address agreement, for the table that carries them.

    `ComplainantDetails` has an `Address` and a `PhoneNumber`. `Accused` has
    neither, and the schema file comments on that asymmetry itself. Those two
    columns were sitting unused while the resolver failed on the table that
    has them, which was the wrong way round.

    Neither is a protected attribute. Caste, religion and occupation are on
    `Victim` and are not read here or anywhere else.

    A phone number is close to a deterministic key. Two rows carrying the same
    number are almost certainly one person, so the channel is binary: equal, or
    not. It is deliberately not graded, because a partial match on a phone
    number carries no meaning.

    Address is graded, because it is free text and a locality is not a house.
    Exact string, then shared locality stem, then neither.
    """
    n_pairs = len(pair_a)
    out: dict[str, np.ndarray] = {}

    def column(name: str) -> list[str]:
        return [(row.get(name) or "").strip() for row in records.accused]

    if "PhoneNumber" in spec.permitted:
        phone = column("PhoneNumber")
        left = np.array([phone[i] for i in pair_a])
        right = np.array([phone[i] for i in pair_b])
        known = (left != "") & (right != "")
        out["phone"] = np.where(
            ~known, S.NOT_COMPUTABLE, np.where(left == right, 1, 0)
        ).astype(np.int8)

    if "Address" in spec.permitted:
        address = column("Address")
        # The locality stem, which is the part before the comma. Two people in
        # the same locality is weak evidence, the same full address is strong.
        stem = [a.split(",")[0].strip().lower() for a in address]
        left = np.array([address[i] for i in pair_a])
        right = np.array([address[i] for i in pair_b])
        left_stem = np.array([stem[i] for i in pair_a])
        right_stem = np.array([stem[i] for i in pair_b])
        known = (left != "") & (right != "")
        out["address"] = np.where(
            ~known, S.NOT_COMPUTABLE,
            np.where(left == right, 2, np.where(left_stem == right_stem, 1, 0)),
        ).astype(np.int8)

    return out


def load_person_records(corpus_dir: Path, spec: TableSpec) -> Records:
    """Build the engine's Records from a table that is not Accused.

    The protected columns are dropped here, before anything downstream can see
    them, and the guard is asserted on what survives.
    """
    raw = read_csv(corpus_dir / spec.table)
    cases = {c["CaseMasterID"]: c for c in read_csv(corpus_dir / "CaseMaster.csv")}
    units = {u["UnitID"]: u for u in read_csv(corpus_dir / "Unit.csv")}

    projected = [{k: row[k] for k in spec.permitted if k in row} for row in raw]
    assert_no_excluded_features(
        projected[0].keys() if projected else [],
        f"engine.resolve_other feature path for {spec.table}")

    norms, case_id, circle, district, unit = [], [], [], [], []
    for row in projected:
        case = cases[row["CaseMasterID"]]
        station = units[case["UnitID"]]
        norms.append(normalise(row[spec.name_column]))
        case_id.append(row["CaseMasterID"])
        unit.append(case["UnitID"])
        district.append(case["DistrictID"])
        circle.append(station["ParentUnitID"] or station["UnitID"])

    return Records(
        accused=projected, norms=norms, case_id=case_id, circle=circle,
        district=district, unit=unit, cases=cases, units=units,
        # Neither table has an arrest. The relational signal is therefore not
        # computable on any pair, which is reported rather than worked around.
        arrest_officer=[""] * len(projected),
        # Both tables carry GenderID and it is a permitted column on each.
        gender=[(row.get("GenderID") or "").strip() for row in projected],
    )


def truth_for(corpus_dir: Path, spec: TableSpec, records: Records):
    rows = read_csv(corpus_dir / "ground_truth" / spec.truth_file)
    by_row = {r[spec.row_id]: r["TruePersonID"] for r in rows}
    codes: dict[str, int] = {}
    out = np.empty(len(records), dtype=np.int32)
    for i, row in enumerate(records.accused):
        out[i] = codes.setdefault(by_row[row[spec.row_id]], len(codes))
    return out


def guard_demonstration(corpus_dir: Path, spec: TableSpec) -> dict:
    """Prove the guard would fire on the raw table, not merely that it was called.

    A control that is never seen to trip is indistinguishable from a control
    that does not work.
    """
    header = list(read_csv(corpus_dir / spec.table)[0].keys())
    excluded = [c for c in header
                if c in {"CasteID", "ReligionID", "OccupationID"}]
    if not excluded:
        return {"table_carries_protected_columns": False,
                "raw_header_rejected": None,
                "projected_header_accepted": True}

    try:
        assert_no_excluded_features(header, f"raw {spec.table} header")
    except ExcludedFeatureError as error:
        rejected, message = True, str(error).split(".")[0]
    else:
        raise AssertionError(
            f"{spec.table} carries {excluded} and the guard did not fire. "
            f"engine/policy.py is not doing its job.")

    assert_no_excluded_features(spec.permitted, f"projected {spec.table}")
    return {
        "table_carries_protected_columns": True,
        "protected_columns_present": excluded,
        "raw_header_rejected": rejected,
        "rejection_message": message,
        "projected_header_accepted": True,
        "columns_permitted_into_features": list(spec.permitted),
    }


def resolve_table(corpus_dir: Path, spec: TableSpec, emit) -> dict:
    emit()
    emit("-" * 78)
    emit(f"{spec.table}")
    emit("-" * 78)

    guard = guard_demonstration(corpus_dir, spec)
    if guard["table_carries_protected_columns"]:
        emit()
        emit(f"    policy guard   raw header REJECTED, carrying "
             f"{', '.join(guard['protected_columns_present'])}")
        emit(f"    policy guard   projected header accepted, "
             f"{len(spec.permitted)} columns reach the features")
    else:
        emit()
        emit("    policy guard   this table carries no protected column")

    records = load_person_records(corpus_dir, spec)
    n_rows = len(records)
    truth = truth_for(corpus_dir, spec, records)
    n_people = len(set(truth.tolist()))

    pair_a, pair_b = candidate_pairs(records)
    is_match = truth[pair_a] == truth[pair_b]

    # Pairs completeness against every true pair in the table, not against the
    # pairs blocking proposed. Measuring against the candidate set would hide
    # exactly the pairs Layer 2 lost.
    counts = np.bincount(truth)
    all_true_pairs = int((counts * (counts - 1) // 2).sum())
    completeness = (int(is_match.sum()) / all_true_pairs * 100.0
                    if all_true_pairs else float("nan"))
    all_possible = n_rows * (n_rows - 1) // 2
    reduction = 1.0 - len(pair_a) / all_possible if all_possible else float("nan")

    emit()
    emit(f"    rows                {n_rows:>10,}")
    emit(f"    true people         {n_people:>10,}")
    emit(f"    hidden by fragmentation {n_rows - n_people:>6,}"
         f"   rows that are somebody already in the table")
    emit(f"    candidate pairs     {len(pair_a):>10,}")
    emit(f"    reduction ratio     {reduction:>10.4f}")
    emit(f"    pairs completeness  {completeness:>9.2f}%")

    if len(pair_a) == 0:
        emit("    no candidate pairs, nothing to resolve")
        return {"spec": spec.key, "rows": n_rows, "true_people": n_people,
                "resolved": None, "guard": guard}

    features = fx.extract(records, pair_a, pair_b)

    # ---- the columns this table actually carries ------------------------
    # ComplainantDetails has an Address and a PhoneNumber. Both were sitting
    # unused while the resolver failed on the very table that has them, which
    # was the wrong way round. Opted into per table, so nothing reaches the
    # accused pipeline. Measured in scripts/sparse_table_study.py: these two
    # columns move this table from F1 0.0000 to 0.3706. See ADR 026.
    contact = contact_levels(records, spec, pair_a, pair_b)
    features.levels.update(contact)
    signals = MODEL_SIGNALS + tuple(contact)
    if contact:
        emit(f"    contact channels    {', '.join(contact):>10}"
             f"   columns this table has and Accused does not")

    # ---- oracle diagnostic ---------------------------------------------
    # Fitted from ground truth. Not part of the engine. It exists so that a
    # poor unsupervised result can be attributed either to the features or to
    # the fit, which a single F1 cannot distinguish. engine/resolve.py runs the
    # same diagnostic on Accused for the same reason.
    oracle_w = {}
    for signal in signals:
        size = LEVELS[signal] + fs.LEVEL_OFFSET
        idx = features.levels[signal].astype(np.int16) + fs.LEVEL_OFFSET
        m_counts = np.bincount(idx[is_match], minlength=size).astype(float)
        u_counts = np.bincount(idx[~is_match], minlength=size).astype(float)
        support = m_counts + u_counts
        w = np.log(((m_counts + 1) / (m_counts + 1).sum())
                   / ((u_counts + 1) / (u_counts + 1).sum()))
        oracle_w[signal] = np.where(support < fs.MIN_LEVEL_SUPPORT, 0.0, w)

    oracle_score = np.zeros(len(pair_a))
    for signal in signals:
        oracle_score += oracle_w[signal][
            features.levels[signal].astype(np.int16) + fs.LEVEL_OFFSET]

    order = np.argsort(-oracle_score)
    tp = np.cumsum(is_match[order])
    fp = np.cumsum(~is_match[order])
    o_precision = tp / (tp + fp)
    o_recall = tp / max(int(is_match.sum()), 1)
    o_f1 = 2 * o_precision * o_recall / np.maximum(o_precision + o_recall, 1e-12)
    best = int(np.argmax(o_f1))
    oracle_cut = float(oracle_score[order][best])

    levels = {s: features.levels[s] for s in signals}
    model = fs.fit_em(levels, signals=signals)
    frequency = fx.name_frequency(records)
    u_generic = fs.generic_agreement_u(frequency)
    plain = fs.score(model, levels)
    at_value = np.array([bool(v) for v in features.agreed_name])
    adjustment = np.where(
        at_value,
        fs.frequency_adjustment(features.agreed_name, frequency, u_generic),
        0.0)
    adjusted = plain + adjustment
    threshold = fs.posterior_threshold(model)

    case_index = {c: i for i, c in enumerate(dict.fromkeys(records.case_id))}
    case_of = np.array([case_index[c] for c in records.case_id], dtype=np.int32)
    result = correlation.cluster(n_rows, pair_a, pair_b, adjusted, threshold, case_of)
    metrics = correlation.pairwise_scores(result.labels, truth)

    # The cost weighted threshold, ADR 028, demands four to one odds before
    # merging. On Accused that is the right standard and it lifted F0.5 from
    # 0.5490 to 0.6473. On these tables the score distribution is compressed
    # and almost nothing clears it, so the same policy that helps the table the
    # project is about suppresses the table it fixed in ADR 026.
    #
    # Both are reported. Hiding the equal cost figure would overstate the
    # engine; hiding the cost weighted one would misrepresent what ships.
    equal_cost_threshold = fs.posterior_threshold(model, cost_ratio=1.0)
    equal_result = correlation.cluster(n_rows, pair_a, pair_b, adjusted,
                                       equal_cost_threshold, case_of)
    equal_metrics = correlation.pairwise_scores(equal_result.labels, truth)

    oracle_result = correlation.cluster(
        n_rows, pair_a, pair_b, oracle_score, oracle_cut, case_of)
    oracle_metrics = correlation.pairwise_scores(oracle_result.labels, truth)

    # Which signals could be computed at all. On these tables the relational
    # channel has no support and that is a finding, not a defect.
    coverage = {
        signal: round(float((features.levels[signal] != -1).mean()), 6)
        for signal in signals
    }

    emit()
    emit(f"    threshold           {threshold:>10.3f}")
    emit(f"    clusters formed     {result.n_clusters:>10,}")
    emit()
    emit(f"    {'fit':<34} {'prec':>8} {'recall':>8} {'F1':>8}")
    emit(f"    {'unsupervised, cost weighted, ships':<34}"
         f" {metrics['precision']:>8.4f} {metrics['recall']:>8.4f}"
         f" {metrics['f1']:>8.4f}")
    emit(f"    {'unsupervised, equal cost cut':<34}"
         f" {equal_metrics['precision']:>8.4f} {equal_metrics['recall']:>8.4f}"
         f" {equal_metrics['f1']:>8.4f}")
    emit(f"    {'oracle, m and u from ground truth':<34}"
         f" {oracle_metrics['precision']:>8.4f} {oracle_metrics['recall']:>8.4f}"
         f" {oracle_metrics['f1']:>8.4f}")

    if metrics["f1"] < 0.01 <= oracle_metrics["f1"]:
        emit()
        emit("    The features separate and the fit does not. The signals carry")
        emit(f"    enough to reach F1 {oracle_metrics['f1']:.4f} when m and u come from")
        emit("    labels, and the unsupervised estimator recovers none of it.")
        emit("    Layer 4 estimates m from leave one out seeds, which needs")
        emit("    several independent channels to corroborate each other. This")
        emit("    table has one fewer than Accused, because the relational")
        emit("    signal has nothing to compute from, and the estimator does not")
        emit("    degrade gracefully below that. See ADR 024.")

    return {
        "spec": spec.key,
        "table": spec.table,
        "note": spec.note,
        "rows": n_rows,
        "true_people": n_people,
        "hidden_by_fragmentation": n_rows - n_people,
        "true_pairs_in_table": all_true_pairs,
        "candidate_pairs": int(len(pair_a)),
        "true_pairs_in_candidates": int(is_match.sum()),
        "reduction_ratio": round(float(reduction), 6),
        "pairs_completeness_pct": round(float(completeness), 4),
        "threshold_llr": float(threshold),
        "clusters": result.n_clusters,
        "identities_found": result.n_clusters,
        "signals_modelled": list(signals),
        "contact_channels": list(contact),
        "signal_coverage": coverage,
        "results": metrics,
        "results_at_equal_cost": {
            **equal_metrics,
            "threshold_llr": float(equal_cost_threshold),
            "note": ("The same model cut at posterior 0.5 instead of at the "
                     "cost weighted boundary. Reported because the cost policy "
                     "that lifts Accused suppresses this table, and both facts "
                     "belong in the record. See ADR 028."),
        },
        "oracle_diagnostic": {
            "note": ("Fitted from ground truth. Not part of the engine. It "
                     "separates a feature problem from a fit problem, which a "
                     "single F1 cannot do."),
            "best_cut": oracle_cut,
            "pairwise_at_best_cut": {
                "precision": float(o_precision[best]),
                "recall": float(o_recall[best]),
                "f1": float(o_f1[best]),
            },
            "clustered": oracle_metrics,
        },
        "verdict": (
            "features adequate, unsupervised fit failed"
            if metrics["f1"] < 0.01 <= oracle_metrics["f1"]
            else "resolved"),
        "guard": guard,
    }


def run(corpus_dir: Path, quiet: bool = False) -> dict:
    out: list[str] = []

    def emit(line: str = "") -> None:
        out.append(line)
        if not quiet:
            print(line)

    emit("=" * 78)
    emit("THE SAME ENGINE, OVER VICTIM AND COMPLAINANTDETAILS")
    emit("=" * 78)
    emit()
    emit("    Layers 1 to 5, imported from the modules the accused pipeline")
    emit("    uses. No second implementation, so the figures are comparable.")

    tables = {key: resolve_table(corpus_dir, spec, emit)
              for key, spec in SPECS.items()}

    # ---- the combined statement ----------------------------------------
    accused_report = corpus_dir / "resolution_report.json"
    accused = None
    if accused_report.exists():
        payload = json.loads(accused_report.read_text(encoding="utf-8"))
        accused = {
            "spec": "accused",
            "table": "Accused.csv",
            "rows": payload["corpus"]["accused_rows"],
            "true_people": payload["corpus"]["true_persons"],
            "hidden_by_fragmentation": (payload["corpus"]["accused_rows"]
                                        - payload["corpus"]["true_persons"]),
            "identities_found": payload["layer5_cluster"]["clusters"],
            "results": payload["results"]["with_frequency_adjustment"],
            "note": ("No father's name, no address, no phone, no biometric key "
                     "and no arresting officer on most rows. The hardest of the "
                     "three, which is why it is the one the project is about."),
        }

    present = [t for t in ([accused] if accused else []) + list(tables.values()) if t]
    total_rows = sum(t["rows"] for t in present)
    total_people = sum(t["true_people"] for t in present)
    total_found = sum(t.get("identities_found") or 0 for t in present)

    # Relationships that no join on the raw schema can see. A relationship here
    # is a pair of rows in different FIRs that are the same person. The raw
    # schema has no column that connects them, so every one of these is
    # invisible until an identity is constructed.
    total_relationships = sum(
        t.get("true_pairs_in_table")
        or (t["rows"] - t["true_people"])
        for t in present)

    emit()
    emit("=" * 78)
    emit("ALL THREE TABLES")
    emit("=" * 78)
    emit()
    emit(f"    {'table':<22} {'rows':>8} {'people':>8} {'hidden':>8}"
         f" {'prec':>7} {'recall':>7} {'F1':>7}")
    emit()
    for t in present:
        r = t.get("results") or {}
        emit(f"    {t['table']:<22} {t['rows']:>8,} {t['true_people']:>8,}"
             f" {t['hidden_by_fragmentation']:>8,}"
             f" {r.get('precision', float('nan')):>7.4f}"
             f" {r.get('recall', float('nan')):>7.4f}"
             f" {r.get('f1', float('nan')):>7.4f}")
    emit()
    emit(f"    {total_rows:,} person bearing rows across the three tables collapse")
    emit(f"    to {total_people:,} actual people. {total_rows - total_people:,} rows are somebody the")
    emit(f"    record already holds, and {total_relationships:,} same person relationships")
    emit("    exist that no join on the raw KSP schema can see, because there is")
    emit("    no column to join on.")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tables": {t["spec"]: t for t in present},
        "combined": {
            "person_bearing_rows": total_rows,
            "actual_people": total_people,
            "rows_that_are_a_repeat": total_rows - total_people,
            "identities_found_by_sutra": total_found,
            "invisible_relationships": total_relationships,
            "statement": (
                f"Across Accused, Victim and ComplainantDetails, "
                f"{total_rows:,} person bearing rows collapse to "
                f"{total_people:,} actual people, and {total_relationships:,} "
                f"same person relationships exist that no join on the raw KSP "
                f"schema can see."
            ),
        },
        "method": (
            "Layers 1 to 5 imported from engine.block, engine.features, "
            "engine.linkage and engine.cluster. The same code path as the "
            "accused pipeline, with a different table projected into it."
        ),
    }
    (corpus_dir / "other_persons_report.json").write_text(
        json.dumps(report, indent=2, default=float), encoding="utf-8")
    (corpus_dir / "other_persons_report.txt").write_text(
        "\n".join(out) + "\n", encoding="utf-8")
    emit()
    emit(f"    wrote {corpus_dir / 'other_persons_report.json'}")
    return report


def main() -> int:
    _configure_console()
    parser = argparse.ArgumentParser(
        description="Resolve Victim and ComplainantDetails with the same engine.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    run(args.corpus, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
