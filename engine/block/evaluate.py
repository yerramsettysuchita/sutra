"""Layer 2 measurement.

Answers the question Phase 0 left open. The 99.96% recall ceiling reported by
the corpus audit assumed that normalisation folds scripts correctly and that
blocking does not lose the pair. Neither was measured. This measures both and
replaces the optimistic number with the real one.

Three figures matter.

  reduction ratio       how much work blocking avoided
  pairs completeness    what share of true matching pairs survived into the
                        candidate set, which is a hard ceiling on recall for
                        every layer after this one
  revised recall ceiling  pairs completeness, restated as the ceiling, since a
                        pair that is never proposed can never be resolved

Run
    python -m engine.block.evaluate

Writes data/corpus/blocking_report.json, read by the audit screen.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from engine.block.keys import FAMILIES, keys_for
from engine.normalise.indic import normalise
from engine.console import configure as _configure_console

# Above this many accused rows the exact candidate pair union stops being
# something to hold in memory. The cap is stated rather than silently exceeded.
MAX_EXACT_ROWS = 60_000


def load(path: Path):
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def pct(n, d):
    return 0.0 if not d else 100.0 * n / d


def run(corpus_dir: Path, quiet: bool = False):
    accused = load(corpus_dir / "Accused.csv")
    cases = {c["CaseMasterID"]: c for c in load(corpus_dir / "CaseMaster.csv")}
    units = {u["UnitID"]: u for u in load(corpus_dir / "Unit.csv")}
    identity = load(corpus_dir / "ground_truth" / "identity_map.csv")
    manifest = json.loads((corpus_dir / "manifest.json").read_text(encoding="utf-8"))

    # The pre blocking ceiling is read from the corpus audit rather than
    # restated here, so the two reports can never drift apart.
    stats_path = corpus_dir / "corpus_stats.json"
    if not stats_path.exists():
        raise SystemExit("run python -m data.generator.audit first, "
                         "this report quotes its recall ceiling")
    corpus_stats = json.loads(stats_path.read_text(encoding="utf-8"))
    prior_ceiling = corpus_stats["recoverability"]["recall_ceiling_pct"]
    exact_match = corpus_stats["recoverability"]["exact_match_pct"]

    n = len(accused)
    if n > MAX_EXACT_ROWS:
        raise SystemExit(
            f"{n:,} accused rows exceeds the exact evaluation cap of "
            f"{MAX_EXACT_ROWS:,}. The candidate pair union would not fit in "
            f"memory. Re-run on the development corpus, make gen, or raise "
            f"MAX_EXACT_ROWS if the machine can carry it."
        )

    out = []

    def emit(line=""):
        out.append(line)

    # ---- normalise -----------------------------------------------------
    index = {}
    records = []
    for i, row in enumerate(accused):
        case = cases[row["CaseMasterID"]]
        station = units[case["UnitID"]]
        # The station circle is the sub division the station reports to.
        circle = station["ParentUnitID"] or station["UnitID"]
        norm = normalise(row["AccusedName"])
        records.append({
            "i": i,
            "accused_id": row["AccusedMasterID"],
            "case_id": row["CaseMasterID"],
            "circle": circle,
            "norm": norm,
        })
        index[row["AccusedMasterID"]] = i

    empty = sum(1 for r in records if r["norm"].is_empty)
    script_counts = Counter(r["norm"].script for r in records)

    # ---- keys ----------------------------------------------------------
    blocks = {f: defaultdict(list) for f in FAMILIES}
    for r in records:
        for family, keys in keys_for(r["norm"], r["circle"]).items():
            for key in keys:
                blocks[family][key].append(r["i"])

    def pairs_of(family):
        """Packed candidate pairs contributed by one key family."""
        seen = set()
        for members in blocks[family].values():
            if len(members) < 2:
                continue
            members.sort()
            for a, b in combinations(members, 2):
                seen.add(a * n + b)
        return seen

    family_pairs = {f: pairs_of(f) for f in FAMILIES}
    union = set()
    for f in FAMILIES:
        union |= family_pairs[f]

    # Two accused rows on one FIR are provably different people, so proposing
    # them is wasted scoring. Layer 5 would reject the merge anyway. Dropping
    # them here is a free reduction, and it is derived from the schema rather
    # than from a threshold.
    same_case = {r["i"]: r["case_id"] for r in records}
    cannot_link_dropped = 0
    filtered = set()
    for packed in union:
        a, b = divmod(packed, n)
        if same_case[a] == same_case[b]:
            cannot_link_dropped += 1
            continue
        filtered.add(packed)

    all_pairs = n * (n - 1) // 2
    candidates = len(filtered)
    reduction_ratio = 1.0 - (candidates / all_pairs)

    # ---- truth ---------------------------------------------------------
    by_person = defaultdict(list)
    for row in identity:
        by_person[row["TruePersonID"]].append(row)

    true_pairs = []
    for pid, rows in by_person.items():
        if len(rows) < 2:
            continue
        for a, b in combinations(rows, 2):
            ia, ib = index[a["AccusedMasterID"]], index[b["AccusedMasterID"]]
            lo, hi = (ia, ib) if ia < ib else (ib, ia)
            true_pairs.append((lo, hi, a, b))

    def packed(lo, hi):
        return lo * n + hi

    blocked = sum(1 for lo, hi, _, _ in true_pairs if packed(lo, hi) in filtered)
    completeness = pct(blocked, len(true_pairs))

    family_completeness = {}
    for f in FAMILIES:
        hit = sum(1 for lo, hi, _, _ in true_pairs if packed(lo, hi) in family_pairs[f])
        family_completeness[f] = {
            "candidate_pairs": len(family_pairs[f]),
            "pairs_completeness_pct": round(pct(hit, len(true_pairs)), 3),
            "reduction_ratio": round(1.0 - len(family_pairs[f]) / all_pairs, 6),
        }

    # ---- cross script survival ----------------------------------------
    cross_total = cross_shared_token = cross_blocked = 0
    for lo, hi, a, b in true_pairs:
        na, nb = records[lo]["norm"], records[hi]["norm"]
        if {na.script, nb.script} != {"latin", "kannada"}:
            continue
        cross_total += 1
        if set(na.tokens) & set(nb.tokens):
            cross_shared_token += 1
        if packed(lo, hi) in filtered:
            cross_blocked += 1

    # ---- what blocking lost -------------------------------------------
    lost_examples, lost_variants = [], Counter()
    for lo, hi, a, b in true_pairs:
        if packed(lo, hi) in filtered:
            continue
        lost_variants[tuple(sorted((a["Variant"], b["Variant"])))] += 1
        if len(lost_examples) < 10:
            lost_examples.append({
                "a": a["RenderedName"], "b": b["RenderedName"],
                "variant_a": a["Variant"], "variant_b": b["Variant"],
                "same_district": a["DistrictID"] == b["DistrictID"],
            })

    block_sizes = Counter()
    for f in FAMILIES:
        for members in blocks[f].values():
            block_sizes[len(members)] += 1
    largest = max((len(m) for f in FAMILIES for m in blocks[f].values()), default=0)
    total_blocks = sum(len(blocks[f]) for f in FAMILIES)

    # ---- report --------------------------------------------------------
    emit("=" * 78)
    emit("SUTRA  Layer 1 normalisation and Layer 2 blocking")
    emit(f"corpus seed {manifest['seed']}   {manifest['counts']['cases']:,} cases   "
         f"{n:,} accused rows")
    emit("=" * 78)
    emit()
    emit("LAYER 1  NORMALISATION")
    emit()
    for script, count in script_counts.most_common():
        emit(f"    {script:<10} {count:>7,}  {pct(count, n):>5.1f}%")
    emit(f"    names left with no usable token after folding  {empty:,}"
         f"  {pct(empty, n):.2f}%")
    emit()
    emit("    Cross script true pairs, does normalisation bring them together")
    emit()
    emit(f"    cross script true pairs              {cross_total:>7,}")
    emit(f"    share a folded token after Layer 1   {cross_shared_token:>7,}"
         f"  {pct(cross_shared_token, cross_total):>5.1f}%")
    emit(f"    survive into the candidate set       {cross_blocked:>7,}"
         f"  {pct(cross_blocked, cross_total):>5.1f}%")

    emit()
    emit("LAYER 2  BLOCKING")
    emit()
    emit(f"    all possible pairs        {all_pairs:>12,}")
    emit(f"    candidate pairs proposed  {candidates:>12,}")
    emit(f"    dropped as cannot link    {cannot_link_dropped:>12,}"
         f"   two accused on one FIR")
    emit(f"    reduction ratio           {reduction_ratio:>12.6f}")
    emit(f"    blocks across families    {total_blocks:>12,}")
    emit(f"    largest single block      {largest:>12,}")
    emit()
    emit("    Per family, before the union")
    emit()
    emit(f"    {'family':<6} {'candidate pairs':>16} {'reduction':>11} {'completeness':>13}")
    for f in FAMILIES:
        fc = family_completeness[f]
        emit(f"    {f:<6} {fc['candidate_pairs']:>16,} {fc['reduction_ratio']:>11.6f} "
             f"{fc['pairs_completeness_pct']:>12.2f}%")
    emit()
    emit(f"    {'union':<6} {candidates:>16,} {reduction_ratio:>11.6f} "
         f"{completeness:>12.2f}%")

    # Which combination of families is actually worth running. Stated as a
    # table rather than asserted, because the union is a cost decision and the
    # cost lands on every layer downstream.
    emit()
    emit("    Every combination, so the choice of families is a measurement")
    emit()
    emit(f"    {'families':<12} {'candidate pairs':>16} {'reduction':>11} {'completeness':>13}")
    combos = [("PH",), ("P4",), ("TR",), ("PH", "TR"), ("PH", "P4"),
              ("P4", "TR"), ("PH", "P4", "TR")]
    combo_table = []
    for combo in combos:
        merged = set()
        for f in combo:
            merged |= family_pairs[f]
        merged = {p for p in merged
                  if same_case[p // n] != same_case[p % n]}
        hit = sum(1 for lo, hi, _, _ in true_pairs if packed(lo, hi) in merged)
        row = {
            "families": "+".join(combo),
            "candidate_pairs": len(merged),
            "reduction_ratio": round(1.0 - len(merged) / all_pairs, 6),
            "pairs_completeness_pct": round(pct(hit, len(true_pairs)), 3),
        }
        combo_table.append(row)
        emit(f"    {row['families']:<12} {row['candidate_pairs']:>16,} "
             f"{row['reduction_ratio']:>11.6f} {row['pairs_completeness_pct']:>12.2f}%")

    lookup = {r["families"]: r for r in combo_table}
    ph_tr, p4_tr = lookup["PH+TR"], lookup["P4+TR"]
    emit()
    emit("    PH is a strict subset of P4. Truncating a token to four characters")
    emit("    can only merge blocks, never split them, so PH+P4 equals P4 exactly")
    emit("    and the full token key contributes nothing once the prefix key is")
    emit("    present. It is kept as a diagnostic and not shipped.")
    emit()
    emit("    That leaves one real choice, and it is a cost decision.")
    emit()
    emit(f"      PH+TR   {ph_tr['candidate_pairs']:>10,} pairs   "
         f"{ph_tr['pairs_completeness_pct']:.2f}% complete")
    emit(f"      P4+TR   {p4_tr['candidate_pairs']:>10,} pairs   "
         f"{p4_tr['pairs_completeness_pct']:.2f}% complete")
    extra_pairs = p4_tr["candidate_pairs"] - ph_tr["candidate_pairs"]
    extra_pts = p4_tr["pairs_completeness_pct"] - ph_tr["pairs_completeness_pct"]
    extra_true = round(extra_pts / 100 * len(true_pairs))
    emit()
    emit(f"    P4+TR costs {extra_pairs:,} more candidate pairs, {extra_pairs / ph_tr['candidate_pairs'] * 100:.1f}% more")
    emit(f"    scoring work, to recover about {extra_true} more true pairs. That is")
    emit(f"    roughly {extra_pairs // max(extra_true, 1):,} pairs scored per true pair gained.")
    emit()
    emit("    We take it. The ceiling constrains every layer downstream and cannot")
    emit("    be recovered later, while scoring cost is a batch job that runs")
    emit("    overnight. That is the same asymmetry argument as ADR 004. Shipped")
    emit("    scheme is P4 plus TR.")

    emit()
    emit("    Block size, per family")
    emit()
    for f in FAMILIES:
        sizes = [len(m) for m in blocks[f].values()]
        emit(f"    {f:<4} blocks {len(sizes):>6,}   largest {max(sizes):>6,}   "
             f"mean {sum(sizes) / len(sizes):>7.1f}")
    emit()
    emit("    Caveat on these numbers. The corpus draws names from 58 given and")
    emit("    28 patronymic forms, so it carries about 100 distinct folded tokens")
    emit("    across 7,600 rows. Real Karnataka has orders of magnitude more, so")
    emit("    phonetic blocks here are far larger than they would be in the field")
    emit("    and this reduction ratio is pessimistic. Pairs completeness is not")
    emit("    affected by that, which is why it is the figure we carry forward.")

    emit()
    emit("=" * 78)
    emit("THE CEILING, RESTATED")
    emit("=" * 78)
    emit()
    emit(f"    true matching pairs                  {len(true_pairs):>8,}")
    emit(f"    proposed by blocking                 {blocked:>8,}")
    emit(f"    lost at Layer 2, unrecoverable       {len(true_pairs) - blocked:>8,}")
    emit()
    emit(f"    PAIRS COMPLETENESS                   {completeness:>7.2f}%")
    emit(f"    REVISED RECALL CEILING               {completeness:>7.2f}%")
    emit()
    emit(f"    The corpus audit reported {prior_ceiling:.2f}% on the assumption that")
    emit("    blocking would not lose anything. It does. Every layer from 3 to 7")
    emit(f"    is now working against a ceiling of {completeness:.2f}% and not "
         f"{prior_ceiling:.2f}%.")
    emit()
    emit(f"    Exact name matching still reaches only {exact_match:.2f}%. The gap")
    emit(f"    from there to {completeness:.2f}% is what Layers 3 to 7 have to earn.")

    if lost_variants:
        emit()
        emit("    Which renderings blocking loses, most frequent first")
        emit()
        for (va, vb), count in lost_variants.most_common(8):
            emit(f"      {va:<22} against {vb:<22} {count:>5,}")
    if lost_examples:
        emit()
        emit("    Sample of lost pairs")
        emit()
        for ex in lost_examples[:6]:
            flag = "same district" if ex["same_district"] else "different districts"
            emit(f"      {ex['a']!r:<32} {ex['variant_a']}")
            emit(f"      {ex['b']!r:<32} {ex['variant_b']}  {flag}")
            emit()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus_seed": manifest["seed"],
        "corpus_generated_at": manifest.get("generated_at"),
        "cases": manifest["counts"]["cases"],
        "accused_rows": n,
        "normalisation": {
            "script_counts": dict(script_counts),
            "empty_after_folding": empty,
            "cross_script_true_pairs": cross_total,
            "cross_script_shared_token": cross_shared_token,
            "cross_script_shared_token_pct": round(pct(cross_shared_token, cross_total), 3),
            "cross_script_blocked": cross_blocked,
            "cross_script_blocked_pct": round(pct(cross_blocked, cross_total), 3),
        },
        "blocking": {
            "shipped_families": ["P4", "TR"],
            "all_possible_pairs": all_pairs,
            "candidate_pairs": candidates,
            "cannot_link_dropped": cannot_link_dropped,
            "reduction_ratio": round(reduction_ratio, 6),
            "total_blocks": total_blocks,
            "largest_block": largest,
            "by_family": family_completeness,
            "by_combination": combo_table,
            "block_sizes": {
                f: {
                    "blocks": len(blocks[f]),
                    "largest": max((len(m) for m in blocks[f].values()), default=0),
                    "mean": round(
                        sum(len(m) for m in blocks[f].values()) / max(len(blocks[f]), 1), 2),
                } for f in FAMILIES
            },
        },
        "ceiling": {
            "true_pairs": len(true_pairs),
            "blocked": blocked,
            "lost": len(true_pairs) - blocked,
            "pairs_completeness_pct": round(completeness, 3),
            "revised_recall_ceiling_pct": round(completeness, 3),
            "prior_ceiling_pct": prior_ceiling,
            "exact_name_match_pct": exact_match,
        },
        "lost_pair_variants": [
            {"variant_a": va, "variant_b": vb, "count": c}
            for (va, vb), c in lost_variants.most_common(12)
        ],
        "lost_pair_examples": lost_examples,
    }

    text = "\n".join(out)
    if not quiet:
        print(text)
    (corpus_dir / "blocking_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (corpus_dir / "blocking_report.txt").write_text(text + "\n", encoding="utf-8")
    return report


def main():
    _configure_console()
    parser = argparse.ArgumentParser(description="Layer 1 and Layer 2 measurement.")
    parser.add_argument("--corpus", type=Path,
                        default=Path(__file__).resolve().parents[2] / "data" / "corpus")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    run(args.corpus, quiet=args.quiet)


if __name__ == "__main__":
    main()
