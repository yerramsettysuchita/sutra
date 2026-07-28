"""Layers 1 to 5 end to end.

    python -m engine.resolve

Writes data/corpus/resolution_report.json and data/corpus/resolved_identities.csv.

Nothing here reads ground truth except the evaluation section, which is clearly
separated and never feeds a parameter. The engine fits itself with expectation
maximisation and thresholds itself from the fitted prior, so the same code runs
against a corpus that has no labels.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from engine.block.candidates import (
    candidate_pairs,
    load_records,
    truth_labels,
)
from engine.calibrate import isotonic
from engine.cluster import correlation
from engine.cluster.collective import iterate, sweep as collective_sweep

# Weight on the new relational evidence each iteration. 1.00 replaces it
# outright, which is the undamped loop. Swept rather than chosen.
DAMPING_FACTORS = (1.0, 0.5, 0.3)
from engine.features import extract as fx
from engine.features.signals import (
    LEVELS,
    MODEL_SIGNALS,
    NOT_COMPUTABLE,
    ORIENTATION,
    SIGNAL_LABELS,
    SIGNALS,
)
from engine.linkage import fellegi_sunter as fs
from engine.console import configure as _configure_console

DEFAULT_CORPUS = Path(__file__).resolve().parents[1] / "data" / "corpus"


class Timer:
    def __init__(self):
        self.stages: dict[str, float] = {}
        self._start = time.perf_counter()
        self._mark = self._start

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.stages[name] = round(now - self._mark, 3)
        self._mark = now

    @property
    def total(self) -> float:
        return round(time.perf_counter() - self._start, 3)


def auc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Area under the ROC curve by rank, ties handled.

    Chosen as the separation measure because it is threshold free. A signal
    with a good AUC and a badly placed cut point is a binning problem, and a
    signal with a poor AUC has nothing to bin.
    """
    positive = labels.astype(bool)
    n_pos = int(positive.sum())
    n_neg = len(labels) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=np.float64)
    ranks[order] = np.arange(1, len(scores) + 1)
    # Average ranks within ties, otherwise a signal with few distinct levels
    # is penalised for its own discreteness.
    sorted_scores = scores[order]
    start = 0
    for i in range(1, len(sorted_scores) + 1):
        if i == len(sorted_scores) or sorted_scores[i] != sorted_scores[start]:
            if i - start > 1:
                ranks[order[start:i]] = (start + 1 + i) / 2.0
            start = i
    return float((ranks[positive].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def run(corpus_dir: Path, quiet: bool = False) -> dict:
    timer = Timer()
    out: list[str] = []

    def emit(line: str = "") -> None:
        out.append(line)
        if not quiet:
            print(line)

    emit("=" * 78)
    emit("SUTRA  Layers 1 to 5")
    emit("=" * 78)

    # ---- Layers 1 and 2 -------------------------------------------------
    records = load_records(corpus_dir)
    timer.lap("layer1_normalise")
    pair_a, pair_b = candidate_pairs(records)
    timer.lap("layer2_block")

    n_rows = len(records)
    n_pairs = len(pair_a)
    emit()
    emit(f"    accused rows      {n_rows:>12,}")
    emit(f"    candidate pairs   {n_pairs:>12,}")

    truth, _ = truth_labels(corpus_dir, records)
    is_match = (truth[pair_a] == truth[pair_b])
    emit(f"    true pairs inside {int(is_match.sum()):>12,}")

    # ---- Layer 3 --------------------------------------------------------
    emit()
    emit("-" * 78)
    emit("LAYER 3  six signal feature extraction")
    emit("-" * 78)
    features = fx.extract(records, pair_a, pair_b,
                          progress=None if quiet else lambda s: print(f"    {s}"))
    timer.lap("layer3_features")

    signal_report = {}
    emit()
    emit(f"    {'signal':<44} {'coverage':>9} {'AUC':>7} {'m/u top':>9}")
    emit()
    for signal in SIGNALS:
        levels = features.levels[signal]
        computable = levels != NOT_COMPUTABLE
        coverage = float(computable.mean())

        # Separation is measured only where the signal is computable, because
        # AUC over rows the signal cannot see is a measurement of the label
        # distribution rather than of the signal.
        sub_scores = features.scores[signal][computable] * ORIENTATION[signal]
        sub_labels = is_match[computable]
        signal_auc = auc(sub_scores, sub_labels) if computable.any() else float("nan")

        top = LEVELS[signal] - 1
        at_top = levels == top
        m_top = float((at_top & is_match).sum() / max(int(is_match.sum()), 1))
        u_top = float((at_top & ~is_match).sum() / max(int((~is_match).sum()), 1))
        ratio = (m_top / u_top) if u_top > 0 else float("inf")

        signal_report[signal] = {
            "label": SIGNAL_LABELS[signal],
            "coverage": round(coverage, 6),
            "auc": round(signal_auc, 6),
            "m_at_top_level": round(m_top, 6),
            "u_at_top_level": round(u_top, 8),
            "lift_at_top_level": None if ratio == float("inf") else round(ratio, 2),
            "level_distribution": {
                str(level): int((levels == level).sum())
                for level in range(NOT_COMPUTABLE, LEVELS[signal])
            },
        }
        lift = "inf" if ratio == float("inf") else f"{ratio:>9,.0f}"
        emit(f"    {SIGNAL_LABELS[signal]:<44} {coverage:>8.1%} {signal_auc:>7.3f} {lift:>9}")

    emit()
    emit("    Coverage is where the signal can be computed at all. AUC is measured")
    emit("    only on those pairs. Lift is P(top level | match) over")
    emit("    P(top level | non match), so it is the evidence a top level")
    emit("    agreement carries before any weighting.")

    weak = [s for s in SIGNALS if signal_report[s]["coverage"] < 0.5]
    if weak:
        emit()
        for signal in weak:
            emit(f"    {signal} is computable on only "
                 f"{signal_report[signal]['coverage']:.1%} of candidate pairs.")

    # ---- Layer 4 --------------------------------------------------------
    emit()
    emit("-" * 78)
    emit("LAYER 4  frequency adjusted Fellegi Sunter")
    emit("-" * 78)
    model = fs.fit_em(features.levels)
    timer.lap("layer4_em")

    emit()
    emit(f"    method            {model.method}")
    if model.seed_sizes:
        emit()
        emit("    Leave one out seeds, each estimating m for one signal from")
        emit("    strong agreement on the others, so no signal is fitted on itself")
        emit()
        for signal, size in model.seed_sizes.items():
            emit(f"      {signal:<12} {size:>7,} pairs")
    emit()
    emit(f"    EM iterations     {model.iterations}"
         f"{'  converged' if model.converged else '  hit the cap'}")
    emit(f"    fitted p(match)   {model.p_match:.6f}")
    emit(f"    observed p(match) {float(is_match.mean()):.6f}   ground truth, not used in the fit")

    emit()
    emit("    Convergence trace, log likelihood")
    emit()
    trace = model.trace
    show = trace[:5] + ([None] + trace[-3:] if len(trace) > 8 else trace[5:])
    for entry in show:
        if entry is None:
            emit("      ...")
            continue
        delta = "" if entry["delta"] is None else f"  delta {entry['delta']:+.6f}"
        emit(f"      {entry['iteration']:>3}  {entry['log_likelihood']:>18,.4f}"
             f"  p {entry['p_match']:.6f}{delta}")

    weights = model.weights()
    emit()
    emit("    Fitted m and u per level, with the resulting weight")
    emit()
    emit("    Layer 4 models five features, not six. Lexical and phonetic are two")
    emit("    readings of one string, 0.686 correlated, and modelling both counted")
    emit("    the name evidence twice. They are reported above and combined into")
    emit("    one `name` channel here. See ADR 017.")
    emit()
    emit(f"      {'signal':<12} {'level':>6} {'m':>10} {'u':>12} {'log(m/u)':>10}")
    linkage_params = {}
    for signal in MODEL_SIGNALS:
        rows = []
        for level in range(len(model.m[signal])):
            actual_level = level - fs.LEVEL_OFFSET
            name = "n/a" if actual_level == NOT_COMPUTABLE else str(actual_level)
            rows.append({
                "level": name,
                "m": round(float(model.m[signal][level]), 6),
                "u": round(float(model.u[signal][level]), 8),
                "weight": round(float(weights[signal][level]), 4),
            })
            emit(f"      {signal if level == 0 else '':<12} {name:>6}"
                 f" {model.m[signal][level]:>10.5f} {model.u[signal][level]:>12.7f}"
                 f" {weights[signal][level]:>10.3f}")
        linkage_params[signal] = rows

    # ---- frequency adjustment ------------------------------------------
    frequency = fx.name_frequency(records)
    u_generic = fs.generic_agreement_u(frequency)
    plain = fs.score(model, features.levels)
    # The adjustment applies only where a specific name value was agreed on,
    # meaning the two folded keys are equal. Below that the pair agreed on a
    # resemblance rather than on a value, and there is no frequency to look up.
    at_value = np.array([bool(v) for v in features.agreed_name])
    adjustment = fs.frequency_adjustment(features.agreed_name, frequency, u_generic)
    adjustment = np.where(at_value, adjustment, 0.0)
    adjusted = plain + adjustment
    timer.lap("layer4_score")

    agreed = at_value
    emit()
    emit(f"    sum of p_v squared, the generic agreement u   {u_generic:.8f}")
    emit(f"    pairs agreeing on a name value                {int(agreed.sum()):,}")
    if agreed.any():
        emit(f"    adjustment range                              "
             f"{adjustment[agreed].min():+.2f} to {adjustment[agreed].max():+.2f}")
        common = sorted(frequency.items(), key=lambda kv: -kv[1])[:1][0]
        emit(f"    most common name key {common[0]!r} at p_v {common[1]:.5f}"
             f" is penalised {np.log(u_generic / common[1]):+.2f}")

    threshold = fs.posterior_threshold(model)
    emit()
    posterior = fs.FALSE_MERGE_COST_RATIO / (1.0 + fs.FALSE_MERGE_COST_RATIO)
    emit(f"    threshold from the fitted prior and the cost ratio   {threshold:.3f}")
    emit(f"    false merge costs {fs.FALSE_MERGE_COST_RATIO:.0f} times a missed merge,"
         f" so the boundary sits at posterior {posterior:.2f}")
    emit("    That ratio is 1/beta squared at beta 0.5, which is the F0.5")
    emit("    objective this project has argued for from the start. It reads no")
    emit("    labels. See ADR 028.")

    # ---- oracle diagnostic ---------------------------------------------
    # Not part of the engine. Fits m and u from ground truth to establish what
    # this model form could achieve if expectation maximisation found the best
    # solution. The gap between this and the unsupervised result is the
    # difference between a model that cannot work and a fit that has not
    # converged on the right mixture, and without it the two are impossible to
    # tell apart from a single F1.
    oracle_w = {}
    for signal in MODEL_SIGNALS:
        size = LEVELS[signal] + fs.LEVEL_OFFSET
        idx = features.levels[signal].astype(np.int16) + fs.LEVEL_OFFSET
        m_counts = np.bincount(idx[is_match], minlength=size).astype(float)
        u_counts = np.bincount(idx[~is_match], minlength=size).astype(float)
        support = m_counts + u_counts
        w = np.log(((m_counts + 1) / (m_counts + 1).sum())
                   / ((u_counts + 1) / (u_counts + 1).sum()))
        oracle_w[signal] = np.where(support < fs.MIN_LEVEL_SUPPORT, 0.0, w)

    oracle_score = np.zeros(n_pairs)
    for signal in MODEL_SIGNALS:
        oracle_score += oracle_w[signal][
            features.levels[signal].astype(np.int16) + fs.LEVEL_OFFSET]

    def best_pairwise(score_array):
        order = np.argsort(-score_array)
        tp = np.cumsum(is_match[order])
        fp = np.cumsum(~is_match[order])
        precision = tp / (tp + fp)
        recall = tp / int(is_match.sum())
        f1s = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
        best = int(np.argmax(f1s))
        return {"f1": float(f1s[best]), "precision": float(precision[best]),
                "recall": float(recall[best]),
                "cut": float(score_array[order][best])}

    oracle_plain = best_pairwise(oracle_score)
    oracle_adjusted = best_pairwise(oracle_score + adjustment)
    unsupervised_best = best_pairwise(adjusted)

    emit()
    emit("    Oracle diagnostic, m and u fitted from ground truth")
    emit("    This is not the engine. It is the ceiling of this model form.")
    emit()
    emit(f"      {'fit':<38} {'F1':>7} {'prec':>7} {'recall':>7}")
    emit(f"      {'oracle m and u, no adjustment':<38} {oracle_plain['f1']:>7.4f}"
         f" {oracle_plain['precision']:>7.4f} {oracle_plain['recall']:>7.4f}")
    emit(f"      {'oracle m and u, with adjustment':<38} {oracle_adjusted['f1']:>7.4f}"
         f" {oracle_adjusted['precision']:>7.4f} {oracle_adjusted['recall']:>7.4f}")
    emit(f"      {'EM fitted, best possible cut':<38} {unsupervised_best['f1']:>7.4f}"
         f" {unsupervised_best['precision']:>7.4f} {unsupervised_best['recall']:>7.4f}")
    emit()
    emit(f"    The frequency adjustment moves oracle precision from "
         f"{oracle_plain['precision']:.4f} to {oracle_adjusted['precision']:.4f}.")
    emit("    That is the clean measurement of what inverse name frequency buys,")
    emit("    isolated from whether EM found the right parameters.")

    # ---- Layer 5 --------------------------------------------------------
    emit()
    emit("-" * 78)
    emit("LAYER 5  constrained correlation clustering")
    emit("-" * 78)

    case_index = {c: i for i, c in enumerate(dict.fromkeys(records.case_id))}
    case_of = np.array([case_index[c] for c in records.case_id], dtype=np.int32)

    cannot_link = correlation.cannot_link_pairs(case_of)
    emit()
    emit(f"    cannot link edges from the schema   {len(cannot_link):>10,}")

    variants = {}
    for name, scores in (("without frequency adjustment", plain),
                         ("with frequency adjustment", adjusted)):
        result = correlation.cluster(n_rows, pair_a, pair_b, scores, threshold, case_of)
        metrics = correlation.pairwise_scores(result.labels, truth)
        variants[name] = (result, metrics)

    timer.lap("layer5_cluster")

    final_result, final_metrics = variants["with frequency adjustment"]
    base_result, base_metrics = variants["without frequency adjustment"]

    emit(f"    violations if the constraint were ignored  {final_result.violations_before:>10,}")
    emit(f"    components repaired                        {final_result.components_repaired:>10,}")
    emit(f"    edges removed to repair them               {final_result.edges_removed:>10,}")
    emit(f"    violations remaining                       {final_result.violations_after:>10,}")
    emit(f"    clusters formed                            {final_result.n_clusters:>10,}")
    emit(f"    of which singletons                        {final_result.singletons:>10,}")
    emit(f"    unrepairable, escalated as conflicts       {len(final_result.conflicts):>10,}")
    emit(f"    true persons in the corpus                 "
         f"{len(set(truth.tolist())):>10,}")

    # ---- Layer 6 --------------------------------------------------------
    emit()
    emit("-" * 78)
    emit("LAYER 6  collective iteration")
    emit("-" * 78)

    def rescore(current_features):
        plain_now = fs.score(model, current_features.levels)
        return plain_now + adjustment, threshold

    def run_collective(factor: float):
        return iterate(
            records, features, pair_a, pair_b, case_of,
            rescore=rescore, initial_labels=final_result.labels, truth=truth,
            damping=factor)

    emit()
    emit("    Relational evidence is recomputed against resolved identities")
    emit("    instead of name keys, which changes the scores, which changes the")
    emit("    partition. Damping blends the new evidence with the previous")
    emit("    iteration's instead of replacing it, swept over three factors.")

    sweep_runs = collective_sweep(run_collective, DAMPING_FACTORS)
    timer.lap("layer6_collective")

    for key, run in sweep_runs.items():
        emit()
        emit(f"    damping {key}"
             f"   {'converged' if run['converged'] else 'non convergent'}"
             f" after {run['iterations']} iterations")
        emit()
        emit(f"      {'iter':>5} {'reassigned':>11} {'clusters':>9} {'F1':>8}")
        for entry in run["history"]:
            emit(f"      {entry['iteration']:>5} {entry['rows_reassigned']:>11,}"
                 f" {entry['clusters']:>9,} {entry.get('f1', 0):>8.4f}")

    # The shipped configuration is the lowest factor that converges. If none
    # does, the undamped loop is kept and the layer stays reported as non
    # convergent rather than tuned until a number looks acceptable.
    converged_runs = [r for r in sweep_runs.values() if r["converged"]]
    chosen = (min(converged_runs, key=lambda r: r["damping"])
              if converged_runs else sweep_runs[f"{DAMPING_FACTORS[0]:.2f}"])
    collective = run_collective(chosen["damping"])

    emit()
    if converged_runs:
        emit(f"    CONVERGES at damping {chosen['damping']:.2f}"
             f" after {chosen['iterations']} iterations")
    else:
        emit("    NON CONVERGENT at every damping factor swept. The partition")
        emit("    oscillates rather than settling, and that is reported as a")
        emit("    property of the coupling and not smoothed over. See ADR 021.")

    collective_labels = collective["labels"]
    collective_metrics = correlation.pairwise_scores(collective_labels, truth)

    # ---- Layer 7 --------------------------------------------------------
    emit()
    emit("-" * 78)
    emit("LAYER 7  calibration and three way routing")
    emit("-" * 78)

    calibration = isotonic.fit(adjusted, is_match)
    probabilities = calibration.probability(adjusted)
    routing = isotonic.routing_report(probabilities, is_match)
    timer.lap("layer7_calibrate")

    emit()
    emit("    Isotonic reliability, predicted against observed by score decile")
    emit()
    emit(f"      {'score from':>11} {'to':>9} {'pairs':>10} {'predicted':>10} {'observed':>9}")
    for row in calibration.bins:
        emit(f"      {row['score_from']:>11.2f} {row['score_to']:>9.2f}"
             f" {row['pairs']:>10,} {row['predicted']:>10.4f} {row['observed']:>9.4f}")

    emit()
    emit(f"    routing at {isotonic.AUTO_MERGE} and {isotonic.REVIEW_FLOOR}")
    emit()
    for name in isotonic.ROUTES:
        entry = routing[name]
        precision = entry.get("precision")
        detail = f"  precision {precision:.4f}" if precision is not None else ""
        emit(f"      {name:<12} {entry['pairs']:>10,} pairs{detail}")
    emit()
    emit(f"    FALSE MERGE RATE on the automatic band  {routing['false_merge_rate']:.4f}")
    emit(f"    false merges                            {routing['false_merges']:,}"
         f" of {routing['auto_merged_pairs']:,}")
    emit()
    emit("    Reported on the automatic band alone, because that is the band")
    emit("    where no human sees the decision. Errors in the review band are")
    emit("    what the review band is for.")

    # ---- results --------------------------------------------------------
    emit()
    emit("=" * 78)
    emit("END TO END, PAIRWISE AGAINST GROUND TRUTH")
    emit("=" * 78)
    emit()
    emit(f"    {'model':<32} {'precision':>10} {'recall':>9} {'F1':>8}")
    emit()
    for name in ("without frequency adjustment", "with frequency adjustment"):
        _, metrics = variants[name]
        emit(f"    {name:<32} {metrics['precision']:>10.4f}"
             f" {metrics['recall']:>9.4f} {metrics['f1']:>8.4f}")

    delta_f1 = final_metrics["f1"] - base_metrics["f1"]
    emit()
    emit(f"    frequency adjustment moves F1 by {delta_f1:+.4f}")

    emit()
    emit(f"    true positive pairs   {final_metrics['true_positive_pairs']:>10,}")
    emit(f"    false positive pairs  {final_metrics['false_positive_pairs']:>10,}"
         f"   merges that are wrong")
    emit(f"    false negative pairs  {final_metrics['false_negative_pairs']:>10,}"
         f"   merges that were missed")
    emit(f"    actual pairs          {final_metrics['actual_pairs']:>10,}")
    emit()
    emit("    Recall is measured against every true pair in the corpus, not")
    emit("    against the pairs blocking proposed. Measuring against the")
    emit("    candidate set would hide the pairs Layer 2 already lost.")

    emit()
    emit("    Stage timings, seconds")
    for stage, seconds in timer.stages.items():
        emit(f"      {stage:<24} {seconds:>8.3f}")
    emit(f"      {'total':<24} {timer.total:>8.3f}")

    # ---- persist --------------------------------------------------------
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": {
            "accused_rows": n_rows,
            "candidate_pairs": int(n_pairs),
            "true_pairs_in_candidates": int(is_match.sum()),
            "true_persons": len(set(truth.tolist())),
        },
        "layer3_signals": signal_report,
        "layer4_linkage": {
            "method": model.method,
            "seed_sizes": model.seed_sizes,
            "em_iterations": model.iterations,
            "em_converged": model.converged,
            "fitted_p_match": model.p_match,
            "observed_p_match": float(is_match.mean()),
            "trace": model.trace,
            "parameters": linkage_params,
            "generic_agreement_u": u_generic,
            "pairs_with_name_agreement": int(agreed.sum()),
            "threshold_llr": threshold,
        },
        "layer5_cluster": {
            "cannot_link_edges": len(cannot_link),
            "violations_if_unconstrained": final_result.violations_before,
            "components_repaired": final_result.components_repaired,
            "edges_removed": final_result.edges_removed,
            "violations_after": final_result.violations_after,
            "clusters": final_result.n_clusters,
            "singletons": final_result.singletons,
            "conflicts_escalated": len(final_result.conflicts),
        },
        "results": {
            "with_frequency_adjustment": final_metrics,
            "without_frequency_adjustment": base_metrics,
            "frequency_adjustment_f1_delta": delta_f1,
        },
        "layer6_collective": {
            "iterations": collective["iterations"],
            "converged": collective["converged"],
            "damping": collective["damping"],
            "history": collective["history"],
            "final": collective_metrics,
            "damping_sweep": sweep_runs,
            "factors_swept": list(DAMPING_FACTORS),
        },
        "layer7_routing": {
            "calibration_bins": calibration.bins,
            **routing,
        },
        "oracle_diagnostic": {
            "note": ("Fitted from ground truth. Not part of the engine. "
                     "Establishes the ceiling of this model form so an "
                     "unsupervised shortfall can be attributed to the fit "
                     "rather than to the features."),
            "oracle_no_adjustment": oracle_plain,
            "oracle_with_adjustment": oracle_adjusted,
            "em_fitted_best_cut": unsupervised_best,
        },
        "timings_seconds": {**timer.stages, "total": timer.total},
    }
    (corpus_dir / "resolution_report.json").write_text(
        json.dumps(report, indent=2, default=float), encoding="utf-8")
    (corpus_dir / "resolution_report.txt").write_text(
        "\n".join(out) + "\n", encoding="utf-8")

    with (corpus_dir / "resolved_identities.csv").open(
            "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["AccusedMasterID", "CaseMasterID", "ResolvedIdentityID"])
        for i, row in enumerate(records.accused):
            writer.writerow([row["AccusedMasterID"], row["CaseMasterID"],
                             f"R{final_result.labels[i]:06d}"])

    emit()
    emit(f"    wrote {corpus_dir / 'resolution_report.json'}")
    emit(f"    wrote {corpus_dir / 'resolved_identities.csv'}")
    return report


def main() -> int:
    _configure_console()
    parser = argparse.ArgumentParser(description="Run Layers 1 to 5.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    run(args.corpus, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
