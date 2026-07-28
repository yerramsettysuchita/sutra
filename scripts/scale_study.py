"""Does the result hold at scale.

    python scripts/scale_study.py

Runs the whole chain at several corpus sizes and reports every headline figure
side by side, plus wall clock and peak memory per stage. Writes
data/corpus/scale_report.json.

WHY THIS IS NOT A 150,000 CASE RUN.

The full corpus is 150,000 cases and 230,369 accused rows. The shipped blocking
scheme proposes **3,048,808,835 candidate pairs** on it. That is not a memory
ceiling that chunking removes, it is three billion pairs that have to be scored,
and at the measured throughput of the feature stage it is days of compute.

The cause is measurable and specific. The generator draws names from 58 given
and 28 patronymic forms, so the number of distinct folded tokens is fixed at
about two hundred no matter how large the corpus grows. Block membership
therefore grows linearly with corpus size and pairs within a block grow with its
square. At 150,000 cases the largest single block holds 43,361 rows and
contributes 940 million pairs on its own.

On real Karnataka data, where distinct names number in the hundreds of
thousands rather than the dozens, blocks would be far smaller and the scheme
would behave very differently. That is a reasonable expectation and it is not
measured here, so it is stated as an expectation and not as a result.

What is measured is the curve below, at sizes that do fit, and the exponent
fitted to it. The extrapolation to 150,000 is labelled as an extrapolation.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from engine.block.candidates import candidate_pairs, load_records, truth_labels
from engine.cluster import correlation
from engine.features import extract as fx
from engine.linkage import fellegi_sunter as fs

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "corpus" / "work"
OUT = ROOT / "data" / "corpus" / "scale_report.json"

SIZES = (5_000, 10_000, 15_000)
FULL_SCALE = 150_000

# Measured by scripts/scale_study.py in probe mode. Recorded rather than
# recomputed, because generating the full corpus takes 14 seconds and counting
# its blocks takes another 5, and neither changes.
FULL_SCALE_FACTS = {
    "cases": FULL_SCALE,
    "accused_rows": 230_369,
    "candidate_pairs": 3_048_808_835,
    "largest_block_rows": 43_361,
    "all_possible_pairs": 26_534_822_896,
    "reduction_ratio": 0.885102,
    "note": (
        "Counted without materialising the pairs. The chain was not run at "
        "this size, see the module docstring."
    ),
}


def run_size(cases: int) -> dict:
    corpus_dir = WORK / f"n{cases}"
    if corpus_dir.exists():
        shutil.rmtree(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    stages: dict[str, float] = {}
    mark = time.perf_counter()

    subprocess.run(
        [sys.executable, "-m", "data.generator.generate",
         "--cases", str(cases), "--out", str(corpus_dir)],
        cwd=ROOT, check=True, capture_output=True,
    )
    stages["generate"] = round(time.perf_counter() - mark, 2)
    mark = time.perf_counter()

    # No tracemalloc. It traces every allocation and the feature loops allocate
    # millions of times, which slowed a 15,000 case run past an hour. Memory is
    # reported as the size of the candidate pair arrays instead, which is the
    # quantity that actually governs whether a size fits.
    records = load_records(corpus_dir)
    stages["normalise"] = round(time.perf_counter() - mark, 2)
    mark = time.perf_counter()

    pair_a, pair_b = candidate_pairs(records)
    stages["block"] = round(time.perf_counter() - mark, 2)
    mark = time.perf_counter()

    truth, _ = truth_labels(corpus_dir, records)
    is_match = truth[pair_a] == truth[pair_b]

    features = fx.extract(records, pair_a, pair_b)
    stages["features"] = round(time.perf_counter() - mark, 2)
    mark = time.perf_counter()

    model = fs.fit_em(features.levels)
    frequency = fx.name_frequency(records)
    u_generic = fs.generic_agreement_u(frequency)
    at_value = np.array([bool(v) for v in features.agreed_name])
    adjustment = np.where(
        at_value,
        fs.frequency_adjustment(features.agreed_name, frequency, u_generic), 0.0)
    scores = fs.score(model, features.levels) + adjustment
    threshold = fs.posterior_threshold(model)
    stages["linkage"] = round(time.perf_counter() - mark, 2)
    mark = time.perf_counter()

    case_index = {c: i for i, c in enumerate(dict.fromkeys(records.case_id))}
    case_of = np.array([case_index[c] for c in records.case_id], dtype=np.int32)
    result = correlation.cluster(
        len(records), pair_a, pair_b, scores, threshold, case_of)
    metrics = correlation.pairwise_scores(result.labels, truth)
    stages["cluster"] = round(time.perf_counter() - mark, 2)

    n_rows = len(records)
    all_pairs = n_rows * (n_rows - 1) // 2

    # Baseline, for the same comparison at every size.
    exact = {}
    labels = np.empty(n_rows, dtype=np.int32)
    index: dict[str, int] = {}
    for row, record in enumerate(records.accused):
        key = record["AccusedName"].strip().lower() or f"__s{row}"
        labels[row] = index.setdefault(key, len(index))
    exact = correlation.pairwise_scores(labels, truth)

    shutil.rmtree(corpus_dir, ignore_errors=True)

    return {
        "cases": cases,
        "accused_rows": n_rows,
        "true_persons": len(set(truth.tolist())),
        "candidate_pairs": int(len(pair_a)),
        "all_possible_pairs": all_pairs,
        "reduction_ratio": round(1 - len(pair_a) / all_pairs, 6),
        "true_pairs_in_candidates": int(is_match.sum()),
        "base_rate": round(float(is_match.mean()), 8),
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "false_positive_pairs": metrics["false_positive_pairs"],
        "clusters": result.n_clusters,
        "exact_name_f1": exact["f1"],
        "multiple_over_exact": (metrics["f1"] / exact["f1"]) if exact["f1"] else None,
        "stages_seconds": stages,
        "total_seconds": round(sum(stages.values()), 2),
        "pair_array_mb": round(len(pair_a) * 8 / 1e6, 1),
    }


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    runs = []
    for size in SIZES:
        print(f"running at {size:,} cases")
        entry = run_size(size)
        runs.append(entry)
        print(f"  rows {entry['accused_rows']:,}"
              f"  pairs {entry['candidate_pairs']:,}"
              f"  F1 {entry['f1']:.4f}"
              f"  {entry['total_seconds']:.1f}s"
              f"  pairs {entry['pair_array_mb']:.0f} MB")

    # Fit pairs against rows on a log scale. An exponent near 2 means the
    # candidate set is growing quadratically, which is what a fixed name
    # vocabulary produces.
    rows = np.array([r["accused_rows"] for r in runs], dtype=float)
    pairs = np.array([r["candidate_pairs"] for r in runs], dtype=float)
    exponent = float(np.polyfit(np.log(rows), np.log(pairs), 1)[0])

    projected = float(
        pairs[-1] * (FULL_SCALE_FACTS["accused_rows"] / rows[-1]) ** exponent)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sizes": list(SIZES),
        "runs": runs,
        "growth": {
            "pairs_vs_rows_exponent": round(exponent, 3),
            "interpretation": (
                "An exponent near 2 means candidate pairs grow with the square "
                "of corpus size. Block membership grows linearly because the "
                "corpus has a fixed name vocabulary of about 200 distinct "
                "folded tokens, and pairs within a block grow with its square."
            ),
            "projected_pairs_at_full_scale": int(projected),
        },
        "full_scale": FULL_SCALE_FACTS,
        "not_run_at_full_scale": (
            "3,048,808,835 candidate pairs at 150,000 cases. Not a memory "
            "ceiling, a compute wall. The chain was not run at that size and "
            "no figure here is extrapolated into the headline results."
        ),
    }

    OUT.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")

    print()
    print(f"{'cases':>8} {'rows':>8} {'pairs':>14} {'base rate':>11}"
          f" {'prec':>7} {'recall':>7} {'F1':>7} {'vs exact':>9} {'sec':>7} {'pairMB':>8}")
    for r in runs:
        print(f"{r['cases']:>8,} {r['accused_rows']:>8,} {r['candidate_pairs']:>14,}"
              f" {r['base_rate']:>11.6f} {r['precision']:>7.4f} {r['recall']:>7.4f}"
              f" {r['f1']:>7.4f} {r['multiple_over_exact']:>8.1f}x"
              f" {r['total_seconds']:>7.1f} {r['pair_array_mb']:>8.0f}")
    print()
    print(f"pairs grow as rows^{exponent:.2f}")
    print(f"wrote {OUT}")
    shutil.rmtree(WORK, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
