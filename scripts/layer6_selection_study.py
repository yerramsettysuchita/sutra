"""Does best partition selection rescue Layer 6.

    python scripts/layer6_selection_study.py

Writes data/corpus/layer6_selection_report.json.

THE QUESTION

Layer 6 does not converge. ADR 021 recorded that, and recorded that damping made
the oscillation worse rather than better, because the non convergence comes from
coupling a continuous score to a hard partition through step functions and not
from the step size.

So stop trying to make it converge. A non convergent search that visits good
states is still useful if you can tell which state was good. Score every
iteration's partition on the engine's own objective, which uses no labels, and
return the best scoring one rather than the last.

That is ordinary practice and it is honest, on one condition: the selection
criterion must never see a label. `engine.cluster.collective.objective` does
not. It is the correlation clustering objective the clusterer is already
implicitly maximising, total retained edge weight in log likelihood ratio units,
minus a charge for every edge cut to repair a cannot link violation.

WHAT WOULD COUNT AS SUCCESS

Two things, both required.

    1. The selected partition beats the last iteration on held out metrics.
       If selection picks a partition that is no better than whatever the loop
       stopped on, the machinery is decoration.

    2. It is stable across seeds. A selection rule that helps on one corpus and
       hurts on the next has found a property of that corpus.

If both hold, Layer 6 becomes BUILT as best partition selection over a non
convergent loop. If either fails it stays PARTIAL, the non convergence keeps
being reported, and we stop working on Layer 6. Two documented failures is
enough.
"""

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.generator.generate import build_corpus, write_corpus  # noqa: E402
from engine.block.candidates import candidate_pairs, load_records, truth_labels  # noqa: E402
from engine.cluster import correlation  # noqa: E402
from engine.cluster.collective import iterate  # noqa: E402
from engine.features import extract as fx  # noqa: E402
from engine.linkage import fellegi_sunter as fs  # noqa: E402

WORK = ROOT / "data" / "corpus_layer6"

# The shipped corpus seed, plus two others. Three is the minimum that can show
# a rule is not a property of one corpus, and each run is a full resolve.
SEEDS = (4471, 20260729, 815623)
CASES = 3000


def run_one(seed: int, cases: int, emit) -> dict:
    corpus_dir = WORK / f"seed{seed}"
    if not (corpus_dir / "Accused.csv").exists():
        emit(f"    generating seed {seed}, {cases:,} cases")
        rng = random.Random(seed)
        corpus = build_corpus(rng, cases, seed=seed)
        write_corpus(corpus, corpus_dir)

    started = time.perf_counter()
    records = load_records(corpus_dir)
    pair_a, pair_b = candidate_pairs(records)
    truth, _ = truth_labels(corpus_dir, records)

    features = fx.extract(records, pair_a, pair_b)
    model = fs.fit_em(features.levels)
    frequency = fx.name_frequency(records)
    u_generic = fs.generic_agreement_u(frequency)
    at_value = np.array([bool(v) for v in features.agreed_name])
    adjustment = np.where(
        at_value,
        fs.frequency_adjustment(features.agreed_name, frequency, u_generic),
        0.0)
    threshold = fs.posterior_threshold(model)

    def rescore(current):
        return fs.score(model, current.levels) + adjustment, threshold

    case_index = {c: i for i, c in enumerate(dict.fromkeys(records.case_id))}
    case_of = np.array([case_index[c] for c in records.case_id], dtype=np.int32)

    initial = correlation.cluster(
        len(records), pair_a, pair_b,
        fs.score(model, features.levels) + adjustment, threshold, case_of)

    run = iterate(records, features, pair_a, pair_b, case_of,
                  rescore=rescore, initial_labels=initial.labels,
                  truth=truth, damping=1.0)

    selected = correlation.pairwise_scores(run["best_labels"], truth)
    last = correlation.pairwise_scores(run["last_labels"], truth)
    layer5 = correlation.pairwise_scores(initial.labels, truth)

    emit()
    emit(f"    seed {seed}   {len(records):,} rows, {len(pair_a):,} pairs,"
         f" {time.perf_counter() - started:.0f}s")
    emit()
    emit(f"      {'iter':>5} {'objective':>14} {'moved':>8} {'clusters':>9} {'F1':>8}")
    for entry in run["history"]:
        mark = "  <- selected" if entry["iteration"] == run["best_iteration"] else ""
        emit(f"      {entry['iteration']:>5} {entry['objective']:>14,.1f}"
             f" {entry['rows_reassigned']:>8,} {entry['clusters']:>9,}"
             f" {entry.get('f1', 0):>8.4f}{mark}")
    emit()
    emit(f"      selected iteration {run['best_iteration']} of {run['iterations']}"
         f"{'' if run['selected_over_last'] else ', which is also the last'}")
    emit(f"      {'partition':<26} {'prec':>8} {'recall':>8} {'F1':>8}")
    emit(f"      {'Layer 5, before the loop':<26} {layer5['precision']:>8.4f}"
         f" {layer5['recall']:>8.4f} {layer5['f1']:>8.4f}")
    emit(f"      {'last iteration':<26} {last['precision']:>8.4f}"
         f" {last['recall']:>8.4f} {last['f1']:>8.4f}")
    emit(f"      {'selected by objective':<26} {selected['precision']:>8.4f}"
         f" {selected['recall']:>8.4f} {selected['f1']:>8.4f}")

    return {
        "seed": seed,
        "cases": cases,
        "rows": len(records),
        "candidate_pairs": int(len(pair_a)),
        "converged": run["converged"],
        "iterations": run["iterations"],
        "best_iteration": run["best_iteration"],
        "best_objective": run["best_objective"],
        "last_objective": run["last_objective"],
        "selected_is_not_last": run["selected_over_last"],
        "history": run["history"],
        "layer5": layer5,
        "last": last,
        "selected": selected,
        "delta_f1_vs_last": selected["f1"] - last["f1"],
        "delta_f1_vs_layer5": selected["f1"] - layer5["f1"],
    }


def main() -> int:
    out: list[str] = []

    def emit(line: str = "") -> None:
        out.append(line)
        print(line)

    emit("=" * 78)
    emit("LAYER 6, BEST PARTITION SELECTION")
    emit("=" * 78)
    emit()
    emit("    The loop does not converge and damping did not fix it, see ADR 021.")
    emit("    Instead of returning the last iteration, score every partition on")
    emit("    the engine's own objective, which uses no labels, and return the")
    emit("    best. Success needs both a gain over the last iteration and the")
    emit("    same behaviour across seeds.")

    runs = [run_one(seed, CASES, emit) for seed in SEEDS]

    deltas = [r["delta_f1_vs_last"] for r in runs]
    picked_earlier = [r for r in runs if r["selected_is_not_last"]]
    helped = [r for r in runs if r["delta_f1_vs_last"] > 0]
    hurt = [r for r in runs if r["delta_f1_vs_last"] < 0]

    # Selection is worth shipping only if it never loses. A rule that gains on
    # two corpora and loses on the third is a coin toss with extra steps.
    stable = len(hurt) == 0
    useful = len(helped) > 0
    verdict = "BUILT" if (stable and useful) else "PARTIAL"

    emit()
    emit("=" * 78)
    emit("VERDICT")
    emit("=" * 78)
    emit()
    emit(f"    {'seed':>10} {'selected':>9} {'of':>4} {'F1 last':>9}"
         f" {'F1 selected':>12} {'delta':>9}")
    for r in runs:
        emit(f"    {r['seed']:>10} {r['best_iteration']:>9} {r['iterations']:>4}"
             f" {r['last']['f1']:>9.4f} {r['selected']['f1']:>12.4f}"
             f" {r['delta_f1_vs_last']:>+9.4f}")
    emit()
    emit(f"    seeds where selection chose something other than the last   "
         f"{len(picked_earlier)} of {len(runs)}")
    emit(f"    seeds where it improved F1                                  "
         f"{len(helped)} of {len(runs)}")
    emit(f"    seeds where it made F1 worse                                "
         f"{len(hurt)} of {len(runs)}")
    emit(f"    mean delta F1                                               "
         f"{float(np.mean(deltas)):+.4f}")
    emit()

    if verdict == "BUILT":
        emit("    SELECTION WORKS. Layer 6 becomes BUILT, as best partition")
        emit("    selection over a non convergent loop. The loop still does not")
        emit("    converge and that is still reported. What changed is that the")
        emit("    layer no longer returns whichever partition it happened to")
        emit("    stop on.")
    else:
        emit("    SELECTION DOES NOT WORK. Layer 6 stays PARTIAL and keeps being")
        emit("    reported as non convergent. This was the second mechanism")
        emit("    tried after damping, and per the brief it is the last. No")
        emit("    further work on Layer 6.")
        if hurt:
            emit()
            emit(f"    It made F1 worse on {len(hurt)} of {len(runs)} seeds, which")
            emit("    is the disqualifying result. A selection rule that loses on")
            emit("    a corpus it has not seen is not a selection rule.")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": ("Does selecting the best scoring partition on the engine's "
                     "own objective beat returning the last iteration of a non "
                     "convergent loop."),
        "objective": ("Total retained edge weight in log likelihood ratio units, "
                      "sum of (score - threshold) over pairs placed in one "
                      "cluster, minus one unit per edge cut to repair a cannot "
                      "link violation. No ground truth is read."),
        "cases_per_seed": CASES,
        "seeds": list(SEEDS),
        "runs": runs,
        "summary": {
            "seeds_where_selection_differed": len(picked_earlier),
            "seeds_improved": len(helped),
            "seeds_worsened": len(hurt),
            "mean_delta_f1": float(np.mean(deltas)),
            "stable_across_seeds": stable,
            "verdict": verdict,
        },
        "consequence": (
            "Layer 6 is BUILT as best partition selection over a non convergent "
            "loop. Non convergence is unchanged and still reported."
            if verdict == "BUILT" else
            "Layer 6 stays PARTIAL. Selection was the second mechanism tried "
            "after damping and it is the last. See ADR 025."
        ),
    }

    target = ROOT / "data" / "corpus" / "layer6_selection_report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    (ROOT / "data" / "corpus" / "layer6_selection_report.txt").write_text(
        "\n".join(out) + "\n", encoding="utf-8")
    emit()
    emit(f"    wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
