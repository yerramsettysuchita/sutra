"""IERB-P scorer.

    python score.py my_output.csv

Input is a two column CSV, AccusedMasterID and PredictedPersonID, one row per
accused row in the corpus. Cluster identifiers are arbitrary strings.

Scored pairwise over every pair of accused rows in the corpus, not over a
candidate shortlist. Reporting against a shortlist measures the shortlist.

F beta at 0.5 is the primary ranking metric. It weights precision twice as
heavily as recall, because a false merge asserts two people are one and
propagates into everything computed downstream, while a missed merge leaves the
record exactly where it already was.

Pure standard library.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_two_column(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None:
            raise SystemExit(f"{path} is empty")
        return {row[0]: row[1] for row in reader if len(row) >= 2}


def pair_count(labels) -> int:
    return sum(c * (c - 1) // 2 for c in Counter(labels).values())


def f_beta(precision: float, recall: float, beta: float) -> float:
    b2 = beta * beta
    denominator = b2 * precision + recall
    return (1 + b2) * precision * recall / denominator if denominator else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Score an IERB-P submission.")
    parser.add_argument("submission", type=Path)
    parser.add_argument("--gold", type=Path, default=HERE / "gold" / "identities.csv")
    args = parser.parse_args()

    if not args.gold.exists():
        raise SystemExit(f"{args.gold} not found. Run generate.sh first.")

    gold = read_two_column(args.gold)
    predicted = read_two_column(args.submission)

    missing = set(gold) - set(predicted)
    extra = set(predicted) - set(gold)
    if missing:
        raise SystemExit(
            f"submission is missing {len(missing):,} AccusedMasterID values, "
            f"for example {sorted(missing)[:3]}")
    if extra:
        print(f"warning: {len(extra):,} ids in the submission are not in the gold "
              f"set and are ignored")

    ids = sorted(gold)
    gold_labels = [gold[i] for i in ids]
    pred_labels = [predicted[i] for i in ids]
    # Separated, so "B1" with "P23" cannot collide with "B12" with "P3".
    combined = [p + "\t" + g for p, g in zip(pred_labels, gold_labels)]

    actual = pair_count(gold_labels)
    proposed = pair_count(pred_labels)
    true_positive = pair_count(combined)
    false_positive = proposed - true_positive
    false_negative = actual - true_positive

    precision = true_positive / proposed if proposed else 0.0
    recall = true_positive / actual if actual else 0.0
    f1 = f_beta(precision, recall, 1.0)
    f05 = f_beta(precision, recall, 0.5)

    print("IERB-P score")
    print()
    print(f"  rows                    {len(ids):>12,}")
    print(f"  gold people             {len(set(gold_labels)):>12,}")
    print(f"  predicted clusters      {len(set(pred_labels)):>12,}")
    print()
    print(f"  true positive pairs     {true_positive:>12,}")
    print(f"  false positive pairs    {false_positive:>12,}   wrong merges")
    print(f"  false negative pairs    {false_negative:>12,}   missed merges")
    print()
    print(f"  precision               {precision:>12.4f}")
    print(f"  recall                  {recall:>12.4f}")
    print(f"  F1                      {f1:>12.4f}")
    print(f"  F beta 0.5              {f05:>12.4f}   primary ranking metric")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
