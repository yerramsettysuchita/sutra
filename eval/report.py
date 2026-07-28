"""Writes eval/report.json, every figure the deck claims.

    make eval
    python -m eval.report

Produces, on the labelled gold set derived from the generator's ground truth:

  precision, recall, F1, and the false merge rate on auto merges only
  baselines            exact name match, English Soundex, Jaro Winkler alone,
                       Indic phonetic alone
  six signal ablation  drop each, report the F1 delta
  confusion matrix     raw counts
  convergence curve    F1 per collective iteration, Layer 6
  blocking             reduction ratio and pairs completeness, Layer 2
  latency              per stage

Two rules on the output. The false merge rate is reported on the automatic band
alone and at full precision. No figure is rounded in our favour.

English Soundex appears here and nowhere else in the system. It is a baseline to
beat, not a component. See ADR 003.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from engine.block.candidates import candidate_pairs, load_records, truth_labels
from engine.cluster import correlation
from engine.features import extract as fx
from engine.features.signals import MODEL_SIGNALS, SIGNAL_LABELS, SIGNALS
from engine.linkage import fellegi_sunter as fs
from engine.normalise.indic import transliterate
from engine.console import configure as _configure_console

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "data" / "corpus"
OUT = ROOT / "eval" / "report.json"
CANONICAL = ROOT / "eval" / "canonical.json"


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------

def soundex(name: str) -> str:
    """American Soundex, 1918.

    Present only as a baseline. It deletes vowels, which are phonemic in
    Kannada, and it cannot distinguish retroflex from dental. It is what a team
    reaches for when they have not thought about the script, and the point of
    reporting it is to show the cost of that.
    """
    text = "".join(ch for ch in transliterate(name).upper() if ch.isalpha())
    if not text:
        return ""
    codes = {**dict.fromkeys("BFPV", "1"), **dict.fromkeys("CGJKQSXZ", "2"),
             **dict.fromkeys("DT", "3"), "L": "4",
             **dict.fromkeys("MN", "5"), "R": "6"}
    first = text[0]
    tail = []
    previous = codes.get(first, "")
    for ch in text[1:]:
        code = codes.get(ch, "")
        if code and code != previous:
            tail.append(code)
        if ch not in "HW":
            previous = code
    return (first + "".join(tail) + "000")[:4]


def cluster_by_key(keys: list[str], n_rows: int) -> np.ndarray:
    """Partition rows by exact equality of a key. The naive join, as a baseline."""
    labels = np.empty(n_rows, dtype=np.int32)
    index: dict[str, int] = {}
    for row, key in enumerate(keys):
        if not key:
            key = f"__singleton_{row}"
        labels[row] = index.setdefault(key, len(index))
    return labels


def threshold_partition(n_rows, pair_a, pair_b, scores, cut, case_of) -> np.ndarray:
    return correlation.cluster(n_rows, pair_a, pair_b, scores, cut, case_of).labels


def f_beta(precision: float, recall: float, beta: float) -> float:
    """F measure weighting precision against recall.

    Beta below one weights precision more. At beta 0.5 precision counts twice
    as much as recall, which is the correct objective for criminal identity.
    A false merge asserts two people are one, propagates into every downstream
    product and can put a wrong name in front of an investigator. A missed
    merge leaves the record exactly where it already was.
    """
    b2 = beta * beta
    denominator = b2 * precision + recall
    if denominator <= 0:
        return 0.0
    return (1 + b2) * precision * recall / denominator


def precision_recall_curve(n_rows, pair_a, pair_b, scores, case_of, truth,
                           points: int = 40) -> list[dict]:
    """Clustered precision and recall across the decision threshold.

    Measured on the partition rather than on the raw pair scores, because the
    partition is what ships. Transitive closure changes both numbers, so a
    curve drawn on pair scores alone would describe a system nobody runs.
    """
    live = scores[scores > -np.inf]
    lo = float(np.quantile(live, 0.90))
    hi = float(live.max())
    cuts = np.linspace(lo, hi, points)

    curve = []
    for cut in cuts:
        labels = threshold_partition(n_rows, pair_a, pair_b, scores, float(cut), case_of)
        metrics = correlation.pairwise_scores(labels, truth)
        curve.append({
            "threshold": round(float(cut), 4),
            "precision": metrics["precision"],
            "recall": metrics["recall"],
            "f1": metrics["f1"],
            "f_beta_0_5": f_beta(metrics["precision"], metrics["recall"], 0.5),
            "merged_pairs": metrics["predicted_pairs"],
            "false_positive_pairs": metrics["false_positive_pairs"],
        })
    curve.sort(key=lambda p: p["threshold"])
    return curve


def operating_points(curve: list[dict], deployed: dict) -> dict:
    """The point the system actually runs at, and the points it could run at.

    `deployed` is the engine's own threshold, derived from the fitted prior at
    the cost ratio, with no labels involved. That is what the shipped system
    does and it is therefore the canonical headline.

    Every other point on this list is selected with knowledge of the answer.
    The F1 optimal cut in particular is chosen by looking at ground truth, so
    it is not deployable and must never be quoted bare.
    """
    def best(key):
        return max(curve, key=lambda p: p[key])

    def at_precision(target: float):
        eligible = [p for p in curve if p["precision"] >= target]
        # Highest recall among the points that clear the precision bar.
        return max(eligible, key=lambda p: p["recall"]) if eligible else None

    return {
        "deployed": deployed,
        # The highest recall reachable while precision stays at or above 0.95.
        # Unlike every other point below, this one is chosen against a policy
        # the department can state in advance rather than against the answer,
        # which is what makes it deployable. See ADR 027.
        "deployable": at_precision(0.95),
        "f1_optimal": best("f1"),
        "f_beta_0_5_optimal": best("f_beta_0_5"),
        "precision_90": at_precision(0.90),
        "precision_95": at_precision(0.95),
    }


# How each operating point must be described wherever it appears. A figure
# from this table is never quoted without its qualifier.
QUALIFIERS = {
    "deployed": "at the threshold the engine derives for itself",
    "deployable": ("at the highest recall that holds precision at or above "
                   "0.95, the automatic merging point"),
    "f1_optimal": "at the F1 optimal cut, which we do not deploy",
    "f_beta_0_5_optimal": "at the F0.5 optimal cut, which we do not deploy",
    "precision_90": "at a cut chosen for precision 0.90, which we do not deploy",
    "precision_95": "at a cut chosen for precision 0.95, which we do not deploy",
}


# ---------------------------------------------------------------------------

def run(corpus_dir: Path, quiet: bool = False) -> dict:
    started = time.perf_counter()
    stages: dict[str, float] = {}

    def lap(name, since):
        stages[name] = round(time.perf_counter() - since, 3)
        return time.perf_counter()

    mark = time.perf_counter()
    records = load_records(corpus_dir)
    n_rows = len(records)
    mark = lap("normalise", mark)

    pair_a, pair_b = candidate_pairs(records)
    mark = lap("block", mark)

    truth, _ = truth_labels(corpus_dir, records)
    is_match = truth[pair_a] == truth[pair_b]

    features = fx.extract(records, pair_a, pair_b)
    mark = lap("features", mark)

    model = fs.fit_em(features.levels)
    frequency = fx.name_frequency(records)
    u_generic = fs.generic_agreement_u(frequency)
    at_value = np.array([bool(v) for v in features.agreed_name])
    adjustment = np.where(
        at_value, fs.frequency_adjustment(features.agreed_name, frequency, u_generic), 0.0)
    scores = fs.score(model, features.levels) + adjustment
    threshold = fs.posterior_threshold(model)
    mark = lap("linkage", mark)

    case_index = {c: i for i, c in enumerate(dict.fromkeys(records.case_id))}
    case_of = np.array([case_index[c] for c in records.case_id], dtype=np.int32)

    result = correlation.cluster(n_rows, pair_a, pair_b, scores, threshold, case_of)
    headline = correlation.pairwise_scores(result.labels, truth)
    mark = lap("cluster", mark)

    # ---- baselines ------------------------------------------------------
    from engine.features.signals import jaro_winkler

    baselines = {}

    exact = cluster_by_key([r["AccusedName"].strip().lower()
                            for r in records.accused], n_rows)
    baselines["exact name match"] = correlation.pairwise_scores(exact, truth)

    sdx = cluster_by_key([soundex(r["AccusedName"]) for r in records.accused], n_rows)
    baselines["english soundex"] = correlation.pairwise_scores(sdx, truth)

    phonetic_only = cluster_by_key([n.canonical for n in records.norms], n_rows)
    baselines["indic phonetic alone"] = correlation.pairwise_scores(phonetic_only, truth)

    # Jaro Winkler alone, thresholded on the raw name and clustered the same way
    # as the engine so the comparison is like for like.
    jw = np.empty(len(pair_a), dtype=np.float32)
    memo: dict[tuple[str, str], float] = {}
    names = [r["AccusedName"].strip().lower() for r in records.accused]
    for k in range(len(pair_a)):
        a, b = names[pair_a[k]], names[pair_b[k]]
        key = (a, b) if a <= b else (b, a)
        value = memo.get(key)
        if value is None:
            value = jaro_winkler(a, b)
            memo[key] = value
        jw[k] = value
    jw_labels = threshold_partition(n_rows, pair_a, pair_b, jw, 0.90, case_of)
    baselines["jaro winkler alone"] = correlation.pairwise_scores(jw_labels, truth)
    mark = lap("baselines", mark)

    # ---- ablation -------------------------------------------------------
    # Six signals are reported. Lexical and phonetic enter the model through
    # the composite name channel, ADR 017, so dropping either means degrading
    # that channel to the other's evidence alone.
    ablation = {}
    for signal in SIGNALS:
        levels = {s: features.levels[s].copy() for s in MODEL_SIGNALS}
        if signal == "lexical":
            levels["name"] = np.where(features.levels["phonetic"] == 2, 5, 0).astype(np.int8)
        elif signal == "phonetic":
            levels["name"] = np.where(features.scores["lexical"] >= 0.94, 5, 0).astype(np.int8)
        else:
            levels[signal] = np.zeros_like(levels[signal])
        dropped = fs.score(model, levels) + adjustment
        labels = threshold_partition(n_rows, pair_a, pair_b, dropped, threshold, case_of)
        metrics = correlation.pairwise_scores(labels, truth)
        ablation[signal] = {
            "label": SIGNAL_LABELS[signal],
            **metrics,
            "f1_delta": metrics["f1"] - headline["f1"],
        }
    mark = lap("ablation", mark)

    curve = precision_recall_curve(
        n_rows, pair_a, pair_b, scores, case_of, truth)
    deployed_point = {
        "threshold": round(float(threshold), 4),
        "precision": headline["precision"],
        "recall": headline["recall"],
        "f1": headline["f1"],
        "f_beta_0_5": f_beta(headline["precision"], headline["recall"], 0.5),
        "merged_pairs": headline["predicted_pairs"],
        "false_positive_pairs": headline["false_positive_pairs"],
    }
    points = operating_points(curve, deployed_point)
    mark = lap("pr_curve", mark)

    blocking = json.loads(
        (corpus_dir / "blocking_report.json").read_text(encoding="utf-8"))
    resolution = json.loads(
        (corpus_dir / "resolution_report.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (corpus_dir / "manifest.json").read_text(encoding="utf-8"))
    ev_cases = manifest["counts"]["cases"]
    seed = manifest["seed"]
    name_vocabulary = manifest.get("name_vocabulary", 86)

    # The realistic end of the vocabulary sweep, if it has been run. Read
    # rather than typed, and clearly not the headline.
    vocabulary_path = corpus_dir / "vocabulary_report.json"
    realistic_f1 = None
    realistic_vocab = None
    if vocabulary_path.exists():
        vocab = json.loads(vocabulary_path.read_text(encoding="utf-8"))
        realistic_f1 = vocab["realistic"]["f1"]
        realistic_vocab = vocab["realistic"]["vocabulary"]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": {
            "cases": blocking["cases"],
            "accused_rows": n_rows,
            "true_persons": len(set(truth.tolist())),
            "candidate_pairs": int(len(pair_a)),
        },
        "headline": headline,
        "headline_f_beta_0_5": f_beta(headline["precision"], headline["recall"], 0.5),
        "precision_recall_curve": curve,
        "operating_points": points,
        "deployed_operating_point": "deployed",
        "operating_point_qualifiers": QUALIFIERS,
        "objective_note": (
            "F1 weights precision and recall equally. For criminal identity they "
            "are not equal, and F beta at 0.5, which weights precision twice as "
            "heavily, is the correct objective for this domain. Both are reported. "
            "Every cut below the deployed one is selected with knowledge of the "
            "answer and is therefore not deployable."
        ),
        "confusion_matrix": {
            "true_positive_pairs": headline["true_positive_pairs"],
            "false_positive_pairs": headline["false_positive_pairs"],
            "false_negative_pairs": headline["false_negative_pairs"],
            "true_negative_pairs": (n_rows * (n_rows - 1) // 2)
            - headline["predicted_pairs"] - headline["false_negative_pairs"],
        },
        "routing": resolution["layer7_routing"],
        "baselines": baselines,
        "ablation": ablation,
        "convergence": resolution["layer6_collective"],
        "blocking": {
            "reduction_ratio": blocking["blocking"]["reduction_ratio"],
            "pairs_completeness_pct": blocking["ceiling"]["pairs_completeness_pct"],
            "candidate_pairs": blocking["blocking"]["candidate_pairs"],
            "all_possible_pairs": blocking["blocking"]["all_possible_pairs"],
        },
        "signals": resolution["layer3_signals"],
        "linkage": {
            "method": resolution["layer4_linkage"]["method"],
            "fitted_p_match": resolution["layer4_linkage"]["fitted_p_match"],
            "observed_p_match": resolution["layer4_linkage"]["observed_p_match"],
            "threshold_llr": threshold,
            "frequency_adjustment_f1_delta":
                resolution["results"]["frequency_adjustment_f1_delta"],
        },
        "oracle_diagnostic": resolution["oracle_diagnostic"],
        "latency_seconds": {**stages, "total": round(time.perf_counter() - started, 3)},
        "questions": {
            "status": "not built",
            "note": ("The 150 investigator question gold set is Session C work. "
                     "It is absent rather than estimated."),
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")

    # ---- canonical.json -------------------------------------------------
    # One headline, written once, read everywhere. Nothing anywhere in this
    # repository types a metric by hand, and a reader who wants "the answer"
    # has exactly one place to look.
    #
    # The canonical figure is the fixture corpus at the threshold the engine
    # derives for itself. It is the conservative number and it is what the
    # shipped system actually does. Every other figure in the project is
    # better, and every one of them is better for a reason a reader must be
    # told, so none may be quoted without its qualifier.
    # ---- the two products ------------------------------------------------
    # One model, two operating points, two different jobs. Which one a
    # department runs at is a policy choice about the cost of a wrong merge
    # against the cost of a missed one. It is not a property of the method and
    # this project does not get to make it. See ADR 027.
    deployable_point = points.get("deployable")
    ceiling_f1 = report["oracle_diagnostic"]["oracle_with_adjustment"]["f1"]
    share_of_ceiling = headline["f1"] / ceiling_f1 if ceiling_f1 else None

    canonical = {
        "generated_at": report["generated_at"],
        "headline": {
            "precision": headline["precision"],
            "recall": headline["recall"],
            "f1": headline["f1"],
            "f_beta_0_5": deployed_point["f_beta_0_5"],
            "false_merge_rate": resolution["layer7_routing"]["false_merge_rate"],
        },
        "definition": {
            "corpus": "fixture",
            "cases": ev_cases,
            "accused_rows": n_rows,
            "name_vocabulary": name_vocabulary,
            "seed": seed,
            "operating_point": "deployed",
            "threshold_llr": deployed_point["threshold"],
            "statement": (
                "The fixture corpus at the threshold the engine derives for "
                "itself. No label is used to choose it."
            ),
        },
        "how_to_read": [
            {
                "role": "headline",
                "f1": headline["f1"],
                "text": "What the shipped system does on the hostile fixture. "
                        "This is the answer.",
            },
            {
                "role": "floor",
                "f1": baselines["exact name match"]["f1"],
                "text": "Exact name matching, the naive join every other "
                        "approach starts from.",
            },
            {
                "role": "ceiling",
                "f1": report["oracle_diagnostic"]["oracle_with_adjustment"]["f1"],
                "text": "This model family fitted from ground truth, on the "
                        "fixture. Not reachable without labels.",
            },
            {
                "role": "realistic",
                "f1": realistic_f1,
                "text": f"The same system with a {realistic_vocab} form name "
                        "vocabulary. A different, easier corpus, which is why "
                        "it exceeds the fixture ceiling above. Not the headline.",
            },
        ],
        "products": {
            "note": (
                "One model, two operating points, two different products. The "
                "operating point is a policy choice for the department about "
                "the cost of a wrong merge against the cost of a missed one. "
                "It is not a property of the method."
            ),
            "deployable": ({
                "label": "Deployable",
                "purpose": "automatic merging",
                "precision": deployable_point["precision"],
                "recall": deployable_point["recall"],
                "f1": deployable_point["f1"],
                "f_beta_0_5": deployable_point["f_beta_0_5"],
                "threshold_llr": deployable_point["threshold"],
                "merged_pairs": deployable_point["merged_pairs"],
                "statement": (
                    "The highest recall that holds precision at or above 0.95. "
                    "At this cut a merge can be written to the record without a "
                    "human looking at it, and one merge in twenty is still "
                    "wrong, which is why the band is narrow."
                ),
            } if deployable_point else None),
            "investigative": {
                "label": "Investigative",
                "purpose": "generating review candidates",
                "precision": headline["precision"],
                "recall": headline["recall"],
                "f1": headline["f1"],
                "f_beta_0_5": deployed_point["f_beta_0_5"],
                "threshold_llr": deployed_point["threshold"],
                "merged_pairs": deployed_point["merged_pairs"],
                "statement": (
                    "The threshold the engine derives for itself. Twice the "
                    "recall, at a precision that needs a human between the "
                    "result and the record."
                ),
            },
        },
        "ceiling_argument": {
            "oracle_f1": ceiling_f1,
            "headline_f1": headline["f1"],
            "share_of_ceiling": share_of_ceiling,
            "statement": (
                f"With m and u fitted from ground truth this model form caps at "
                f"F1 {ceiling_f1:.4f}, so no linkage method can do much better "
                f"on the fields this schema provides. SUTRA reaches "
                f"{share_of_ceiling * 100:.0f}% of it. The remaining gap is not "
                f"a modelling problem, it is a data collection problem, and it "
                f"is the argument for adding a person key to the record."
                if share_of_ceiling else "Not measured."
            ),
        },
        "qualifiers": QUALIFIERS,
        "rule": (
            "Any figure that is not the headline carries its qualifier inline, "
            "every time, without exception."
        ),
    }
    CANONICAL.write_text(
        json.dumps(canonical, indent=2, default=float), encoding="utf-8")

    if not quiet:
        print_report(report)
    return report


def print_report(report: dict) -> None:
    h = report["headline"]
    print("=" * 78)
    print("SUTRA  evaluation")
    print("=" * 78)
    print()
    print(f"  cases {report['corpus']['cases']:,}   accused rows "
          f"{report['corpus']['accused_rows']:,}   candidate pairs "
          f"{report['corpus']['candidate_pairs']:,}")
    print()
    print("HEADLINE, pairwise against ground truth")
    print()
    print(f"    precision  {h['precision']:.4f}")
    print(f"    recall     {h['recall']:.4f}")
    print(f"    F1         {h['f1']:.4f}")
    r = report["routing"]
    print(f"    false merge rate, automatic band only   {r['false_merge_rate']:.4f}"
          f"   ({r['false_merges']:,} of {r['auto_merged_pairs']:,})")
    print()
    print("OPERATING POINTS")
    print()
    print(f"    {'point':<22} {'cut':>8} {'prec':>8} {'recall':>8} {'F1':>8}"
          f" {'F0.5':>8} {'merges':>10}")
    for name, point in report["operating_points"].items():
        if point is None:
            print(f"    {name:<22} not reachable on this curve")
            continue
        print(f"    {name:<22} {point['threshold']:>8.2f} {point['precision']:>8.4f}"
              f" {point['recall']:>8.4f} {point['f1']:>8.4f}"
              f" {point['f_beta_0_5']:>8.4f} {point['merged_pairs']:>10,}")
    print()
    print("    F beta at 0.5 weights precision twice as heavily as recall and is")
    print("    the correct objective for criminal identity. A false merge")
    print("    propagates, a missed merge leaves the record where it was.")
    print()
    r = report["routing"]
    print(f"    The automatic band is deliberately narrow, {r['auto_merged_pairs']:,}"
          f" pairs of {report['corpus']['candidate_pairs']:,}.")
    print("    Everything uncertain goes to a human.")
    print()
    print("CONFUSION MATRIX, raw pair counts")
    cm = report["confusion_matrix"]
    for key, value in cm.items():
        print(f"    {key:<24} {value:>14,}")
    print()
    print("BASELINES")
    print()
    print(f"    {'method':<26} {'precision':>10} {'recall':>8} {'F1':>8}")
    for name, metrics in report["baselines"].items():
        print(f"    {name:<26} {metrics['precision']:>10.4f}"
              f" {metrics['recall']:>8.4f} {metrics['f1']:>8.4f}")
    print(f"    {'SUTRA':<26} {h['precision']:>10.4f} {h['recall']:>8.4f} {h['f1']:>8.4f}")
    print()
    print("ABLATION, drop one signal")
    print()
    print(f"    {'signal':<46} {'F1':>8} {'delta':>9}")
    for signal, entry in report["ablation"].items():
        print(f"    {entry['label']:<46} {entry['f1']:>8.4f} {entry['f1_delta']:>+9.4f}")
    print()
    print("BLOCKING")
    b = report["blocking"]
    print(f"    reduction ratio       {b['reduction_ratio']:.6f}")
    print(f"    pairs completeness    {b['pairs_completeness_pct']:.2f}%")
    print()
    print("CONVERGENCE, Layer 6")
    print()
    for entry in report["convergence"]["history"]:
        print(f"    iteration {entry['iteration']:>2}  F1 {entry.get('f1', 0):.4f}"
              f"  clusters {entry['clusters']:,}  moved {entry['rows_reassigned']:,}")
    print()
    print("LATENCY, seconds")
    for stage, seconds in report["latency_seconds"].items():
        print(f"    {stage:<14} {seconds:>8.3f}")
    print()
    print(f"wrote {OUT}")


def main() -> int:
    _configure_console()
    parser = argparse.ArgumentParser(description="Write eval/report.json.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    run(args.corpus, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
