"""Build the IERB-P gold set from a generated corpus.

    python make_gold.py --corpus corpus --out gold

Two files, and the reason there are two.

`identities.csv` is the gold partition, one row per AccusedMasterID. It is the
complete answer and it is what `score.py` uses. Compact, 7,611 rows on the
default task.

`pairs.csv` is a labelled pair sample for methods that train on pairs. Every
positive pair is included. Negatives are sampled in two strata, hard negatives
that share a folded name token and easy ones that do not, because a uniform
negative sample from 29 million pairs is almost entirely trivial and teaches a
model nothing.

Pure standard library, so it runs anywhere the generator does.
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

SEED = 4471
HARD_NEGATIVES = 40_000
EASY_NEGATIVES = 10_000


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def fold(name: str) -> set[str]:
    """A deliberately crude token key, only for stratifying negatives.

    Not the benchmark's normalisation and not a hint at a solution. It exists
    so the hard negative stratum is genuinely hard.
    """
    for ch in "@./,-":
        name = name.replace(ch, " ")
    return {t for t in name.lower().split() if len(t) > 2}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the IERB-P gold set.")
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    gt = args.corpus / "ground_truth" / "identity_map.csv"
    if not gt.exists():
        raise SystemExit(f"{gt} not found. Run generate.sh first.")

    identity = read_csv(gt)
    accused = read_csv(args.corpus / "Accused.csv")
    args.out.mkdir(parents=True, exist_ok=True)

    person_of = {r["AccusedMasterID"]: r["TruePersonID"] for r in identity}
    name_of = {r["AccusedMasterID"]: r["AccusedName"] for r in accused}
    case_of = {r["AccusedMasterID"]: r["CaseMasterID"] for r in accused}
    amids = [r["AccusedMasterID"] for r in accused]

    with (args.out / "identities.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["AccusedMasterID", "GoldPersonID"])
        for amid in amids:
            writer.writerow([amid, person_of[amid]])

    by_person: dict[str, list[str]] = defaultdict(list)
    for amid in amids:
        by_person[person_of[amid]].append(amid)

    positives = []
    for members in by_person.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                positives.append((members[i], members[j]))

    rng = random.Random(SEED)
    tokens = {amid: fold(name_of[amid]) for amid in amids}
    by_token: dict[str, list[str]] = defaultdict(list)
    for amid, toks in tokens.items():
        for token in toks:
            by_token[token].append(amid)

    seen = {tuple(sorted(p)) for p in positives}
    hard: list[tuple[str, str]] = []
    token_keys = [k for k, v in by_token.items() if len(v) > 1]
    attempts = 0
    while len(hard) < HARD_NEGATIVES and attempts < HARD_NEGATIVES * 40 and token_keys:
        attempts += 1
        bucket = by_token[rng.choice(token_keys)]
        a, b = rng.choice(bucket), rng.choice(bucket)
        if a == b or person_of[a] == person_of[b]:
            continue
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        hard.append(key)

    easy: list[tuple[str, str]] = []
    attempts = 0
    while len(easy) < EASY_NEGATIVES and attempts < EASY_NEGATIVES * 40:
        attempts += 1
        a, b = rng.choice(amids), rng.choice(amids)
        if a == b or person_of[a] == person_of[b]:
            continue
        if tokens[a] & tokens[b]:
            continue
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        easy.append(key)

    with (args.out / "pairs.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["AccusedMasterID_A", "AccusedMasterID_B", "label", "stratum"])
        for a, b in positives:
            writer.writerow([a, b, 1, "positive"])
        for a, b in hard:
            writer.writerow([a, b, 0, "hard_negative"])
        for a, b in easy:
            writer.writerow([a, b, 0, "easy_negative"])

    same_case = sum(1 for a, b in hard if case_of[a] == case_of[b])

    print(f"gold written to {args.out}")
    print(f"  identities.csv  {len(amids):,} rows")
    print(f"  pairs.csv       {len(positives):,} positive,"
          f" {len(hard):,} hard negative, {len(easy):,} easy negative")
    print(f"  of the hard negatives, {same_case:,} share a CaseMasterID and are")
    print("  therefore provably different people by the schema alone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
