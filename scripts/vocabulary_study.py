"""How much of the measured precision is the fixture, and how much is the method.

    python scripts/vocabulary_study.py

The generator draws from 58 given and 28 patronymic forms, so the folded token
vocabulary is fixed near 200 however large the corpus grows. Blocks are
therefore far larger than in the field, the reduction ratio sits well below the
record linkage norm, the candidate set floods and the base rate collapses.
Precision pays for all of it.

Real Karnataka records carry thousands of distinct names. This sweeps the
vocabulary and holds cases, seed and every other parameter fixed, so the effect
of that one variable is visible.

Writes data/corpus/vocabulary_report.json.

Which end is realistic. The 86 form pool is a deliberately hostile fixture and
nothing like a real jurisdiction. Karnataka's electoral rolls carry name
vocabularies in the hundreds of thousands. The 3,000 form end of this sweep is
still conservative against that, and it is the end a reader should treat as
indicative of field behaviour.

The headline figure published everywhere else in this project stays at the 86
form fixture. It is not replaced. A floor that is honestly labelled is worth
more than a ceiling that needs a footnote.
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
from engine.normalise.indic import normalise

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "data" / "corpus" / "vocab_work"
OUT = ROOT / "data" / "corpus" / "vocabulary_report.json"

CASES = 5_000
POOLS = (86, 300, 1_000, 3_000)


def run_pool(vocabulary: int) -> dict:
    corpus_dir = WORK / f"v{vocabulary}"
    if corpus_dir.exists():
        shutil.rmtree(corpus_dir)
    corpus_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    subprocess.run(
        [sys.executable, "-m", "data.generator.generate",
         "--cases", str(CASES), "--name-pool", str(vocabulary),
         "--out", str(corpus_dir)],
        cwd=ROOT, check=True, capture_output=True,
    )

    records = load_records(corpus_dir)
    pair_a, pair_b = candidate_pairs(records)
    truth, _ = truth_labels(corpus_dir, records)
    is_match = truth[pair_a] == truth[pair_b]

    # Folded token vocabulary actually realised, which is what drives block size.
    tokens = set()
    for norm in records.norms:
        tokens.update(norm.tokens)

    # Pairs completeness against every true pair in the corpus, not only those
    # blocking proposed.
    n_rows = len(records)
    all_pairs = n_rows * (n_rows - 1) // 2
    person_counts = np.bincount(truth)
    true_pairs_total = int((person_counts * (person_counts - 1) // 2).sum())

    features = fx.extract(records, pair_a, pair_b)
    model = fs.fit_em(features.levels)
    frequency = fx.name_frequency(records)
    u_generic = fs.generic_agreement_u(frequency)
    at_value = np.array([bool(v) for v in features.agreed_name])
    adjustment = np.where(
        at_value,
        fs.frequency_adjustment(features.agreed_name, frequency, u_generic), 0.0)
    scores = fs.score(model, features.levels) + adjustment
    threshold = fs.posterior_threshold(model)

    case_index = {c: i for i, c in enumerate(dict.fromkeys(records.case_id))}
    case_of = np.array([case_index[c] for c in records.case_id], dtype=np.int32)
    result = correlation.cluster(n_rows, pair_a, pair_b, scores, threshold, case_of)
    metrics = correlation.pairwise_scores(result.labels, truth)

    labels = np.empty(n_rows, dtype=np.int32)
    index: dict[str, int] = {}
    for row, record in enumerate(records.accused):
        key = record["AccusedName"].strip().lower() or f"__s{row}"
        labels[row] = index.setdefault(key, len(index))
    exact = correlation.pairwise_scores(labels, truth)

    shutil.rmtree(corpus_dir, ignore_errors=True)

    return {
        "requested_vocabulary": vocabulary,
        "folded_tokens_realised": len(tokens),
        "accused_rows": n_rows,
        "candidate_pairs": int(len(pair_a)),
        "reduction_ratio": round(1 - len(pair_a) / all_pairs, 6),
        "pairs_completeness_pct": round(
            100.0 * int(is_match.sum()) / max(true_pairs_total, 1), 3),
        "base_rate": round(float(is_match.mean()), 8),
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "false_positive_pairs": metrics["false_positive_pairs"],
        "exact_name_f1": exact["f1"],
        "multiple_over_exact": (metrics["f1"] / exact["f1"]) if exact["f1"] else None,
        "seconds": round(time.perf_counter() - started, 1),
    }


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    runs = []
    for vocabulary in POOLS:
        print(f"running at {vocabulary} name forms")
        entry = run_pool(vocabulary)
        runs.append(entry)
        print(f"  tokens {entry['folded_tokens_realised']:,}"
              f"  pairs {entry['candidate_pairs']:,}"
              f"  RR {entry['reduction_ratio']:.4f}"
              f"  P {entry['precision']:.4f}"
              f"  F1 {entry['f1']:.4f}")

    first, last = runs[0], runs[-1]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cases": CASES,
        "pools": list(POOLS),
        "runs": runs,
        "fixture": {
            "vocabulary": POOLS[0],
            "precision": first["precision"],
            "f1": first["f1"],
            "note": (
                "The pool the headline figures are measured on. A deliberately "
                "hostile fixture, not a jurisdiction."
            ),
        },
        "realistic": {
            "vocabulary": POOLS[-1],
            "precision": last["precision"],
            "f1": last["f1"],
            "note": (
                "Still conservative against a real electoral roll, which "
                "carries name vocabularies in the hundreds of thousands. This "
                "end is indicative of field behaviour."
            ),
        },
        "sensitivity": {
            "precision_gain": last["precision"] - first["precision"],
            "f1_gain": last["f1"] - first["f1"],
            "reduction_ratio_gain": last["reduction_ratio"] - first["reduction_ratio"],
            "base_rate_ratio": (last["base_rate"] / first["base_rate"]
                                if first["base_rate"] else None),
        },
        "headline_unchanged": (
            "The figures published elsewhere in this project remain those of "
            "the 86 form fixture. They are not replaced by this sweep. The "
            "sweep establishes that they are a floor."
        ),
    }
    OUT.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")

    print()
    print(f"{'forms':>7} {'tokens':>8} {'pairs':>12} {'RR':>8} {'complete':>9}"
          f" {'base':>10} {'prec':>7} {'recall':>7} {'F1':>7} {'vs exact':>9}")
    for r in runs:
        print(f"{r['requested_vocabulary']:>7,} {r['folded_tokens_realised']:>8,}"
              f" {r['candidate_pairs']:>12,} {r['reduction_ratio']:>8.4f}"
              f" {r['pairs_completeness_pct']:>8.2f}% {r['base_rate']:>10.6f}"
              f" {r['precision']:>7.4f} {r['recall']:>7.4f} {r['f1']:>7.4f}"
              f" {r['multiple_over_exact']:>8.1f}x")
    print()
    print(f"precision {first['precision']:.4f} to {last['precision']:.4f}, "
          f"{last['precision'] - first['precision']:+.4f}")
    print(f"F1        {first['f1']:.4f} to {last['f1']:.4f}, "
          f"{last['f1'] - first['f1']:+.4f}")
    print(f"wrote {OUT}")
    shutil.rmtree(WORK, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
