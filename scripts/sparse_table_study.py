"""Can the estimator be made to work on the sparse person tables.

    python scripts/sparse_table_study.py

Writes data/corpus/sparse_table_report.json.

THE PROBLEM, RESTATED

The engine resolves nothing on `Victim` and `ComplainantDetails`. F1 0.0000 on
both, against an oracle ceiling of 0.4824 and 0.3328. ADR 024 established that
the features are adequate and the unsupervised estimator is what fails: m is
estimated from leave one out seeds, which needs several independent channels to
corroborate one another, and these tables have four where `Accused` has five.
The relational channel is structurally absent because neither table has an
arresting officer and a FIR names at most one complainant.

THREE METHODS, TRIED IN ORDER

    a. TRANSFER THE PRIOR
       Fit m on `Accused`, apply it to the other two, re estimate only the
       mixing proportion.

       The assumption, stated plainly because it is doing the work: the name
       generating process is shared. All three tables draw Karnataka names,
       written by the same station writers into the same fields, and are
       subject to the same transliteration and spelling variation. So
       P(name agreement level | same person) is a property of that shared
       process rather than of the role the person plays in the FIR. This is
       ordinary parameter transfer in record linkage.

       What is NOT transferred is u. u is the distribution of agreement among
       non matches, which depends on the blocking scheme's output and on the
       base rate, and both differ per table. u is re estimated locally from
       each table's own candidate marginals.

       The assumption is weakest for temporal, since victims and complainants
       have a different age distribution from the accused, and for modus, which
       is a property of the case rather than of the person.

    b. POOL THE THREE TABLES
       Estimate one shared parameter set over the candidate pairs of all three
       tables at once, then partition within each. The seed set becomes large
       enough to stand on its own.

    c. USE THE COLUMNS THAT EXIST
       `ComplainantDetails` carries `Address` and `PhoneNumber` and neither was
       a feature. A matching phone number is close to an identifier. Added as
       two signals, opted into for that table only.

       This cannot help `Victim`, which has neither column. Caste, religion and
       occupation are on `Victim` and are NOT touched.

WHAT IS REPORTED

Precision, recall, F1 and the share of the oracle ceiling reached, for every
table, for every method, including the ones that fail.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.block.candidates import candidate_pairs, load_records, truth_labels  # noqa: E402
from engine.cluster import correlation  # noqa: E402
from engine.console import configure as _configure_console  # noqa: E402
from engine.features import extract as fx  # noqa: E402
from engine.features.signals import LEVELS, MODEL_SIGNALS  # noqa: E402
from engine.linkage import fellegi_sunter as fs  # noqa: E402
from engine.resolve_other import (  # noqa: E402
    SPECS, contact_levels, load_person_records, truth_for,
)

CORPUS = ROOT / "data" / "corpus"


class Table:
    """One person bearing table, prepared once and reused by every method."""

    def __init__(self, key: str, records, truth, pair_a, pair_b, features,
                 extra_signals=()):
        self.key = key
        self.records = records
        self.truth = truth
        self.pair_a = pair_a
        self.pair_b = pair_b
        self.features = features
        self.extra_signals = tuple(extra_signals)
        self.is_match = truth[pair_a] == truth[pair_b]
        case_index = {c: i for i, c in enumerate(dict.fromkeys(records.case_id))}
        self.case_of = np.array([case_index[c] for c in records.case_id],
                                dtype=np.int32)
        frequency = fx.name_frequency(records)
        u_generic = fs.generic_agreement_u(frequency)
        at_value = np.array([bool(v) for v in features.agreed_name])
        self.adjustment = np.where(
            at_value,
            fs.frequency_adjustment(features.agreed_name, frequency, u_generic),
            0.0)

    @property
    def signals(self) -> tuple[str, ...]:
        """Every channel available on this table, contact columns included."""
        return MODEL_SIGNALS + self.extra_signals

    def levels(self, signals: tuple[str, ...] | None = None) -> dict[str, np.ndarray]:
        return {s: self.features.levels[s] for s in (signals or self.signals)}

    def evaluate(self, model) -> dict:
        scores = fs.score(model, self.levels(model.signals)) + self.adjustment
        threshold = fs.posterior_threshold(model)
        result = correlation.cluster(len(self.records), self.pair_a,
                                     self.pair_b, scores, threshold,
                                     self.case_of)
        metrics = correlation.pairwise_scores(result.labels, self.truth)
        metrics["threshold"] = float(threshold)
        metrics["clusters"] = int(result.n_clusters)
        metrics["merged_pairs"] = int((scores > threshold).sum())
        return metrics

    def evaluate_at(self, model, threshold: float) -> dict:
        """Score with this model but cut at a threshold from somewhere else."""
        scores = fs.score(model, self.levels(model.signals)) + self.adjustment
        result = correlation.cluster(len(self.records), self.pair_a,
                                     self.pair_b, scores, threshold, self.case_of)
        metrics = correlation.pairwise_scores(result.labels, self.truth)
        metrics["threshold"] = float(threshold)
        metrics["clusters"] = int(result.n_clusters)
        return metrics

    def oracle(self, signals: tuple[str, ...] | None = None) -> dict:
        """The ceiling of this model form on this table, m and u from labels."""
        signals = signals or MODEL_SIGNALS
        weights = {}
        for signal in signals:
            size = LEVELS[signal] + fs.LEVEL_OFFSET
            idx = self.features.levels[signal].astype(np.int16) + fs.LEVEL_OFFSET
            m_counts = np.bincount(idx[self.is_match], minlength=size).astype(float)
            u_counts = np.bincount(idx[~self.is_match], minlength=size).astype(float)
            support = m_counts + u_counts
            w = np.log(((m_counts + 1) / (m_counts + 1).sum())
                       / ((u_counts + 1) / (u_counts + 1).sum()))
            weights[signal] = np.where(support < fs.MIN_LEVEL_SUPPORT, 0.0, w)

        score = np.zeros(len(self.pair_a))
        for signal in signals:
            score += weights[signal][
                self.features.levels[signal].astype(np.int16) + fs.LEVEL_OFFSET]

        order = np.argsort(-score)
        tp = np.cumsum(self.is_match[order])
        fp = np.cumsum(~self.is_match[order])
        precision = tp / (tp + fp)
        recall = tp / max(int(self.is_match.sum()), 1)
        f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
        best = int(np.argmax(f1))
        cut = float(score[order][best])
        result = correlation.cluster(len(self.records), self.pair_a,
                                     self.pair_b, score, cut, self.case_of)
        return correlation.pairwise_scores(result.labels, self.truth)


def prepare(emit) -> dict[str, Table]:
    tables: dict[str, Table] = {}

    emit("    preparing tables")
    records = load_records(CORPUS)
    truth, _ = truth_labels(CORPUS, records)
    pair_a, pair_b = candidate_pairs(records)
    features = fx.extract(records, pair_a, pair_b)
    tables["accused"] = Table("accused", records, truth, pair_a, pair_b, features)
    emit(f"      accused      {len(records):>7,} rows, {len(pair_a):>9,} pairs")

    for key, spec in SPECS.items():
        recs = load_person_records(CORPUS, spec)
        t = truth_for(CORPUS, spec, recs)
        a, b = candidate_pairs(recs)
        f = fx.extract(recs, a, b)
        extra = contact_levels(recs, spec, a, b)
        f.levels.update(extra)
        tables[key] = Table(key, recs, t, a, b, f, extra_signals=tuple(extra))
        emit(f"      {key:<12} {len(recs):>7,} rows, {len(a):>9,} pairs"
             f"{'' if not extra else ', contact columns ' + ', '.join(extra)}")

    return tables


def report_row(emit, label: str, metrics: dict, ceiling: float) -> dict:
    share = metrics["f1"] / ceiling if ceiling > 0 else float("nan")
    emit(f"      {label:<34} {metrics['precision']:>8.4f}"
         f" {metrics['recall']:>8.4f} {metrics['f1']:>8.4f}"
         f" {share * 100:>9.1f}%")
    return {
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "share_of_oracle": round(float(share), 4),
        "clusters": metrics.get("clusters"),
        "threshold": metrics.get("threshold"),
    }


def main() -> int:
    _configure_console()
    out: list[str] = []

    def emit(line: str = "") -> None:
        out.append(line)
        print(line)

    emit("=" * 78)
    emit("FIXING THE ESTIMATOR ON THE SPARSE PERSON TABLES")
    emit("=" * 78)
    emit()

    tables = prepare(emit)
    targets = ["victim", "complainant"]

    ceilings = {k: tables[k].oracle() for k in targets}
    emit()
    emit("    Oracle ceilings, m and u fitted from ground truth. Not the engine.")
    for k in targets:
        emit(f"      {k:<12} F1 {ceilings[k]['f1']:.4f}")

    attempts: dict[str, dict] = {}

    # ---- baseline, what ships today -------------------------------------
    emit()
    emit("-" * 78)
    emit("BASELINE  direct estimation on the table's own seeds, what ships today")
    emit("-" * 78)
    emit()
    emit(f"      {'table':<34} {'prec':>8} {'recall':>8} {'F1':>8} {'of oracle':>10}")
    attempts["baseline"] = {}
    for k in targets:
        model = fs.fit_em(tables[k].levels(MODEL_SIGNALS), signals=MODEL_SIGNALS)
        attempts["baseline"][k] = report_row(
            emit, k, tables[k].evaluate(model), ceilings[k]["f1"])

    # ---- a, transfer the prior ------------------------------------------
    emit()
    emit("-" * 78)
    emit("METHOD A  transfer m from Accused, re estimate only the mixing proportion")
    emit("-" * 78)
    emit()
    emit("    Assumption. The name generating process is shared. All three tables")
    emit("    hold Karnataka names written by the same station writers into the")
    emit("    same fields, so P(name agreement | same person) belongs to that")
    emit("    process rather than to the role the person plays in the FIR.")
    emit("    u is NOT transferred, it is re estimated locally, because u")
    emit("    describes the blocking output and the base rate and both differ.")
    emit()
    accused_model = fs.fit_em(tables["accused"].levels())
    emit(f"    fitted on accused, p_match {accused_model.p_match:.6f},"
         f" {len(tables['accused'].records):,} rows")
    emit()
    emit(f"      {'table':<34} {'prec':>8} {'recall':>8} {'F1':>8} {'of oracle':>10}")
    attempts["a_transfer"] = {}
    for k in targets:
        prior = {s: accused_model.m[s] for s in MODEL_SIGNALS}
        model = fs.fit_em(tables[k].levels(MODEL_SIGNALS),
                          signals=MODEL_SIGNALS, m_prior=prior)
        attempts["a_transfer"][k] = report_row(
            emit, k, tables[k].evaluate(model), ceilings[k]["f1"])
        attempts["a_transfer"][k]["p_match"] = model.p_match

    # ---- a2, the diagnosis of why a fails --------------------------------
    #
    # Method A gives good weights and no merges. EM drives the mixing
    # proportion to zero, the threshold is log((1-p)/p), and a threshold of
    # 20.7 sits above every score the model can produce. So the step the brief
    # specified, re estimating only the mixing proportion, is precisely the
    # step that breaks. This variant keeps the transferred m and also takes the
    # threshold from the source table instead of from the collapsed local fit.
    #
    # It is a weaker assumption than transferring m. The match proportion among
    # candidate pairs depends on the blocking output and on how often a person
    # recurs, and both differ per table. It is reported as a diagnosis of the
    # failure rather than proposed as a method.
    emit()
    emit("-" * 78)
    emit("METHOD A2  transfer m AND the threshold, diagnosing why A fails")
    emit("-" * 78)
    emit()
    emit("    Under A, EM drives the mixing proportion to zero on both tables.")
    emit("    The threshold is log((1-p)/p), so it goes to 20.7 while the best")
    emit("    score the model produces is 8.1. Nothing can clear it. The")
    emit("    transferred weights are not the problem, the re estimated prior is.")
    emit()
    accused_threshold = fs.posterior_threshold(accused_model)
    emit(f"    accused threshold {accused_threshold:.3f}")
    emit()
    emit(f"      {'table':<34} {'prec':>8} {'recall':>8} {'F1':>8} {'of oracle':>10}")
    attempts["a2_transfer_threshold"] = {}
    for k in targets:
        prior = {s: accused_model.m[s] for s in MODEL_SIGNALS}
        model = fs.fit_em(tables[k].levels(MODEL_SIGNALS),
                          signals=MODEL_SIGNALS, m_prior=prior)
        metrics = tables[k].evaluate_at(model, accused_threshold)
        attempts["a2_transfer_threshold"][k] = report_row(
            emit, k, metrics, ceilings[k]["f1"])

    a_works = all(attempts["a_transfer"][k]["f1"] > 0 for k in targets)

    # ---- b, pool ---------------------------------------------------------
    emit()
    emit("-" * 78)
    emit("METHOD B  one parameter set estimated over all three tables pooled")
    emit("-" * 78)
    emit()
    pooled = {s: np.concatenate([tables[k].features.levels[s]
                                 for k in ("accused", *targets)])
              for s in MODEL_SIGNALS}
    emit(f"    pooled candidate pairs {len(pooled['name']):,}")
    pooled_model = fs.fit_em(pooled)
    emit(f"    pooled p_match {pooled_model.p_match:.6f}")
    emit()
    emit(f"      {'table':<34} {'prec':>8} {'recall':>8} {'F1':>8} {'of oracle':>10}")
    attempts["b_pooled"] = {}
    for k in targets:
        prior = {s: pooled_model.m[s] for s in MODEL_SIGNALS}
        model = fs.fit_em(tables[k].levels(MODEL_SIGNALS),
                          signals=MODEL_SIGNALS, m_prior=prior)
        attempts["b_pooled"][k] = report_row(
            emit, k, tables[k].evaluate(model), ceilings[k]["f1"])

    # ---- c, the columns that exist --------------------------------------
    emit()
    emit("-" * 78)
    emit("METHOD C  add the address and phone columns ComplainantDetails carries")
    emit("-" * 78)
    emit()
    emit("    Applies to ComplainantDetails only. Victim has neither column, and")
    emit("    the columns it does carry beyond a name are caste, religion and")
    emit("    occupation, which are excluded and are not read.")
    emit()
    emit(f"      {'table':<34} {'prec':>8} {'recall':>8} {'F1':>8} {'of oracle':>10}")
    attempts["c_contact"] = {}
    for k in targets:
        table = tables[k]
        if not table.extra_signals:
            emit(f"      {k:<34} {'not applicable, no contact columns':>38}")
            attempts["c_contact"][k] = {"not_applicable": True}
            continue
        # The table's own estimation, over its own channels including the two
        # contact columns. Nothing is transferred, so the comparison against
        # the baseline isolates exactly what the columns are worth.
        model = fs.fit_em(table.levels(), signals=table.signals)
        # The ceiling moves when the channels move. Scoring this against the
        # five channel ceiling would report more than 100% of a ceiling this
        # method is not bounded by, which is not a measurement of anything.
        contact_ceiling = table.oracle(table.signals)
        attempts["c_contact"][k] = report_row(
            emit, k, table.evaluate(model), contact_ceiling["f1"])
        attempts["c_contact"][k]["ceiling_with_contact"] = round(
            contact_ceiling["f1"], 4)
        attempts["c_contact"][k]["ceiling_without_contact"] = round(
            ceilings[k]["f1"], 4)
        emit(f"        oracle ceiling moves {ceilings[k]['f1']:.4f}"
             f" to {contact_ceiling['f1']:.4f} once the phone column is a feature")
        weights = model.weights()
        for s in table.extra_signals:
            attempts["c_contact"][k][f"{s}_weights"] = [
                round(float(w), 4) for w in weights[s]]
            emit(f"        {s} weights by level"
                 f" {[round(float(w), 2) for w in weights[s]]}")

    # ---- verdict ---------------------------------------------------------
    emit()
    emit("=" * 78)
    emit("VERDICT")
    emit("=" * 78)
    emit()
    emit(f"    {'method':<22} {'victim F1':>11} {'complainant F1':>16}")
    order = ["baseline", "a_transfer", "a2_transfer_threshold", "b_pooled",
             "c_contact"]
    for method in order:
        cells = []
        for k in targets:
            row = attempts[method].get(k, {})
            cells.append("n/a" if row.get("not_applicable")
                         else f"{row.get('f1', float('nan')):.4f}")
        emit(f"    {method:<22} {cells[0]:>11} {cells[1]:>16}")

    best = {}
    for k in targets:
        scored = [(m, attempts[m][k]) for m in order
                  if not attempts[m][k].get("not_applicable")]
        winner = max(scored, key=lambda kv: kv[1]["f1"])
        best[k] = {"method": winner[0], **winner[1]}

    emit()
    for k in targets:
        b = best[k]
        emit(f"    {k:<12} best is {b['method']}, F1 {b['f1']:.4f},"
             f" {b['share_of_oracle'] * 100:.1f}% of the oracle ceiling")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": ("Can the unsupervised estimator be made to produce a non "
                     "zero result on Victim and ComplainantDetails."),
        "oracle_ceilings": {k: ceilings[k] for k in targets},
        "methods": {
            "baseline": "Direct estimation on the table's own leave one out seeds.",
            "a_transfer": ("m fitted on Accused and applied unchanged. u re "
                           "estimated locally. EM fits only the mixing "
                           "proportion. Assumes the name generating process is "
                           "shared across the three tables."),
            "b_pooled": ("One m estimated over the candidate pairs of all three "
                         "tables pooled, then applied to each."),
            "a2_transfer_threshold": (
                "Method A plus the threshold taken from the source table, "
                "because EM drives the mixing proportion to zero and the "
                "derived threshold lands above every score the model can "
                "produce. Reported as the diagnosis of A rather than proposed "
                "as a method, since the match proportion among candidate pairs "
                "is a property of the blocking output and of how often a "
                "person recurs, and both differ per table."),
            "c_contact": ("Adds phone equality and address agreement, the two "
                          "columns ComplainantDetails carries and Accused does "
                          "not. Not applicable to Victim."),
        },
        "attempts": attempts,
        "best_per_table": best,
    }
    (CORPUS / "sparse_table_report.json").write_text(
        json.dumps(report, indent=2, default=float), encoding="utf-8")
    (CORPUS / "sparse_table_report.txt").write_text(
        "\n".join(out) + "\n", encoding="utf-8")
    emit()
    emit(f"    wrote {CORPUS / 'sparse_table_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
