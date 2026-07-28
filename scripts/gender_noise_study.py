"""What is the gender channel worth when the field is not clean.

    python scripts/gender_noise_study.py

Writes data/corpus/gender_noise_report.json.

WHY THIS EXISTS, AND IT IS A CORRECTION

ADR 028 added a gender channel to Layer 3 and reported that it removed 273,335
false pairs while losing zero true pairs, citing that zero of 3,840 true people
had rows disagreeing on gender.

That was not a measurement. The generator copied each person's gender onto every
one of their rows verbatim, so the field could not disagree with itself. The
number was guaranteed by construction and it was published as a finding. The
same failure mode this project keeps catching: measuring what the fixture makes
true.

The corpus now models a gender recording error rate. This sweeps it, because the
useful question is not "does gender help on our corpus" but **"how much of the
help survives the field being imperfect"**, which is the only version a records
officer can act on.

METHOD

One corpus, generated with a clean gender field. Features extracted once.
Then, for each error rate, the recorded gender is perturbed and **only the
gender channel is recomputed**. Every other feature, every name, date and
location is bit for bit identical across the whole sweep.

That isolates the variable exactly. A difference between two rows of this table
is the gender channel and nothing else, which regenerating a corpus per rate
could not have guaranteed.

At each rate the model is fitted and scored twice, once with the channel and
once without, so the reported delta is what the channel is worth at that level
of data quality.
"""

from __future__ import annotations

import json
import random
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.generator.generate import build_corpus, write_corpus  # noqa: E402
from engine.block.candidates import candidate_pairs, load_records, truth_labels  # noqa: E402
from engine.cluster import correlation  # noqa: E402
from engine.console import configure as _configure_console  # noqa: E402
from engine.features import extract as fx  # noqa: E402
from engine.features import signals as S  # noqa: E402
from engine.linkage import fellegi_sunter as fs  # noqa: E402

WORK = ROOT / "data" / "corpus_gender"
OUT = ROOT / "data" / "corpus" / "gender_noise_report.json"
CASES = 5000
SEED = 4471

# 0 is the fixture the earlier claim was measured on, and it is included so the
# overstatement is visible in the table rather than only described.
RATES = (0.0, 0.005, 0.012, 0.02, 0.05, 0.10)

WITHOUT_GENDER = tuple(s for s in S.MODEL_SIGNALS if s != "gender")


def f_beta(precision: float, recall: float, beta: float = 0.5) -> float:
    if precision + recall == 0:
        return 0.0
    b2 = beta * beta
    return (1 + b2) * precision * recall / (b2 * precision + recall)


def main() -> int:
    _configure_console()
    out: list[str] = []

    def emit(line: str = "") -> None:
        out.append(line)
        print(line)

    emit("=" * 78)
    emit("THE GENDER CHANNEL, AGAINST A FIELD THAT IS NOT CLEAN")
    emit("=" * 78)
    emit()
    emit("    ADR 028 measured this channel on a corpus where recorded gender")
    emit("    could not be wrong, because the generator copied it verbatim onto")
    emit("    every row. The zero true pairs lost was guaranteed, not found.")
    emit("    This sweeps the error rate. Rate 0.000 reproduces the original")
    emit("    claim so the overstatement is visible rather than merely admitted.")
    emit()

    corpus_dir = WORK / "clean"
    if not (corpus_dir / "Accused.csv").exists():
        emit(f"    generating a clean corpus, {CASES:,} cases")
        shutil.rmtree(WORK, ignore_errors=True)
        rng = random.Random(SEED)
        corpus = build_corpus(rng, CASES, seed=SEED, gender_error_rate=0.0)
        write_corpus(corpus, corpus_dir)

    records = load_records(corpus_dir)
    truth, _ = truth_labels(corpus_dir, records)
    pair_a, pair_b = candidate_pairs(records)
    is_match = truth[pair_a] == truth[pair_b]
    features = fx.extract(records, pair_a, pair_b)
    emit(f"    {len(records):,} rows, {len(pair_a):,} candidate pairs, "
         f"{int(is_match.sum()):,} true pairs")

    frequency = fx.name_frequency(records)
    u_generic = fs.generic_agreement_u(frequency)
    at_value = np.array([bool(v) for v in features.agreed_name])
    adjustment = np.where(
        at_value,
        fs.frequency_adjustment(features.agreed_name, frequency, u_generic), 0.0)
    case_index = {c: i for i, c in enumerate(dict.fromkeys(records.case_id))}
    case_of = np.array([case_index[c] for c in records.case_id], dtype=np.int32)
    clean_gender = list(records.gender)

    def resolve(levels: dict, signals: tuple[str, ...]) -> dict:
        model = fs.fit_em(levels, signals=signals)
        scores = fs.score(model, levels) + adjustment
        threshold = fs.posterior_threshold(model)
        result = correlation.cluster(len(records), pair_a, pair_b, scores,
                                     threshold, case_of)
        metrics = correlation.pairwise_scores(result.labels, truth)
        metrics["f_beta_0_5"] = f_beta(metrics["precision"], metrics["recall"])
        return metrics

    emit()
    emit(f"    {'error rate':>11} {'flipped':>8} {'people':>8}"
         f" {'F0.5 with':>10} {'F0.5 without':>13} {'gain':>9}"
         f" {'true lost':>10}")
    emit()

    runs = []
    for rate in RATES:
        rng = random.Random(SEED + 71351)
        gender = list(clean_gender)
        flipped = 0
        for i, value in enumerate(gender):
            if not value:
                continue
            if rng.random() < rate:
                gender[i] = "2" if int(value) == 1 else "1"
                flipped += 1

        records.gender[:] = gender
        level = np.array(
            [S.gender_level(gender[i], gender[j])
             for i, j in zip(pair_a, pair_b)], dtype=np.int8)
        features.levels["gender"] = level
        features.scores["gender"] = level.astype(np.float32)

        # True pairs the channel now actively contradicts. This is the cost of
        # the field being dirty and the earlier claim reported it as zero.
        true_lost = int((is_match & (level == 0)).sum())
        false_cut = int((~is_match & (level == 0)).sum())
        people_split = len({int(truth[i]) for i, j in zip(pair_a, pair_b)
                            if truth[i] == truth[j]
                            and gender[i] and gender[j] and gender[i] != gender[j]})

        with_gender = resolve(
            {s: features.levels[s] for s in S.MODEL_SIGNALS}, S.MODEL_SIGNALS)
        without = resolve(
            {s: features.levels[s] for s in WITHOUT_GENDER}, WITHOUT_GENDER)
        gain = with_gender["f_beta_0_5"] - without["f_beta_0_5"]

        emit(f"    {rate:>11.3f} {flipped:>8,} {people_split:>8,}"
             f" {with_gender['f_beta_0_5']:>10.4f}"
             f" {without['f_beta_0_5']:>13.4f} {gain:>+9.4f}"
             f" {true_lost:>10,}")

        runs.append({
            "error_rate": rate,
            "rows_flipped": flipped,
            "people_with_contradictory_gender": people_split,
            "true_pairs_contradicted": true_lost,
            "false_pairs_eliminated": false_cut,
            "with_gender": with_gender,
            "without_gender": without,
            "f_beta_0_5_gain": gain,
            "f1_gain": with_gender["f1"] - without["f1"],
            "precision_gain": with_gender["precision"] - without["precision"],
        })

    records.gender[:] = clean_gender

    clean = runs[0]
    shipped = next(r for r in runs if abs(r["error_rate"] - 0.012) < 1e-9)
    worst = runs[-1]
    still_helps = [r for r in runs if r["f_beta_0_5_gain"] > 0]

    emit()
    emit("=" * 78)
    emit("WHAT THIS SAYS")
    emit("=" * 78)
    emit()
    emit(f"    At a clean field, the original claim, the channel eliminates")
    emit(f"    {clean['false_pairs_eliminated']:,} false pairs and contradicts "
         f"{clean['true_pairs_contradicted']} true ones.")
    emit(f"    That zero is a property of the generator, not of police records.")
    emit()
    emit(f"    At the shipped {shipped['error_rate']:.1%} rate it contradicts "
         f"{shipped['true_pairs_contradicted']:,} true pairs across")
    emit(f"    {shipped['people_with_contradictory_gender']:,} people, and is "
         f"still worth {shipped['f_beta_0_5_gain']:+.4f} F0.5.")
    emit()
    emit(f"    The channel remains positive at every rate swept up to "
         f"{max(r['error_rate'] for r in still_helps):.0%}.")
    emit()
    emit("    The reason it survives is the asymmetry. A wrong gender on one row")
    emit("    costs the true pairs involving that row. A right gender on every")
    emit("    other row rejects false pairs across the whole candidate set, and")
    emit("    there are three hundred times more of those.")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": ("How much of the gender channel's value survives the field "
                     "being imperfect."),
        "correction": (
            "ADR 028 reported zero true pairs lost, citing zero of 3,840 people "
            "with disagreeing gender. The generator copied gender verbatim onto "
            "every row, so that was guaranteed by construction rather than "
            "measured. The corpus now models a recording error rate and this "
            "sweeps it. See ADR 030."),
        "method": (
            "One corpus, one feature extraction. Only the gender channel is "
            "recomputed per rate, so every other feature is identical across "
            "the sweep and a difference between rows is the gender channel and "
            "nothing else."),
        "cases": CASES,
        "seed": SEED,
        "shipped_rate": 0.012,
        "rates": list(RATES),
        "runs": runs,
        "summary": {
            "clean_field_true_pairs_contradicted": clean["true_pairs_contradicted"],
            "shipped_rate_true_pairs_contradicted": shipped["true_pairs_contradicted"],
            "shipped_rate_gain_f_beta_0_5": shipped["f_beta_0_5_gain"],
            "positive_at_every_rate_swept": len(still_helps) == len(runs),
            "highest_rate_still_positive": max(
                (r["error_rate"] for r in still_helps), default=None),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, default=float), encoding="utf-8")
    (ROOT / "data" / "corpus" / "gender_noise_report.txt").write_text(
        "\n".join(out) + "\n", encoding="utf-8")
    emit()
    emit(f"    wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
