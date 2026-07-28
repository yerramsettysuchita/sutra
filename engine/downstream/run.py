"""Layer 8 end to end.

    python -m engine.downstream.run

Writes data/corpus/downstream_report.json.

Requires `make resolve` first, because every product here works on resolved
identities and there is nothing to build a person graph from without them.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from engine.downstream import co_offender, communities, hotspots, profiles, undetected
from engine.downstream.context import load, load_ground_truth
from engine.console import configure as _configure_console

DEFAULT_CORPUS = Path(__file__).resolve().parents[2] / "data" / "corpus"


def run(corpus_dir: Path, quiet: bool = False) -> dict:
    started = time.perf_counter()
    out: list[str] = []

    def emit(line: str = "") -> None:
        out.append(line)
        if not quiet:
            print(line)

    emit("=" * 78)
    emit("SUTRA  Layer 8  downstream products")
    emit("=" * 78)

    corpus = load(corpus_dir)
    emit()
    emit(f"    accused rows          {len(corpus.accused):>10,}")
    emit(f"    resolved identities   {len(corpus.rows_of_identity):>10,}")
    emit(f"    undetected cases      {len(corpus.undetected):>10,}")

    # ---- co offender graph ---------------------------------------------
    graph = co_offender.build(corpus)
    graph_report = co_offender.report(graph)
    emit()
    emit("-" * 78)
    emit("CO OFFENDER GRAPH")
    emit("-" * 78)
    emit()
    for key, value in graph_report.items():
        emit(f"    {key:<38} {value:>12,}" if isinstance(value, int)
             else f"    {key:<38} {value:>12}")
    emit()
    emit("    An edge counts as recovered when it attaches through a name")
    emit("    rendering a naive join would have read as a different person.")

    # ---- communities ----------------------------------------------------
    found, community_report = communities.detect(graph)
    summaries = communities.summarise(found, graph, corpus)
    emit()
    emit("-" * 78)
    emit("COMMUNITIES")
    emit("-" * 78)
    emit()
    for key, value in community_report.items():
        if isinstance(value, dict):
            continue
        emit(f"    {key:<40} {value}")

    # ---- profiles -------------------------------------------------------
    built = profiles.build(corpus, graph)
    profile_report = profiles.report(built)
    emit()
    emit("-" * 78)
    emit("PROFILES")
    emit("-" * 78)
    emit()
    for key, value in profile_report.items():
        emit(f"    {key:<44} {value:>10,}")

    # ---- hotspots -------------------------------------------------------
    hotspot_report = hotspots.report(corpus)
    emit()
    emit("-" * 78)
    emit("HOTSPOTS AND TRENDS")
    emit("-" * 78)
    emit()
    totals = hotspot_report["totals"]
    emit(f"    grid cells at {hotspot_report['cell_degrees']} degrees"
         f"        {hotspot_report['cells']:>8,}")
    emit(f"    cases placed                     {totals['cases_placed']:>8,}")
    emit("")
    emit("    Summed over cells, so an offender working two cells counts in")
    emit("    both. Both rows are summed identically, so the ratio holds.")
    emit(f"    offender occupancies, resolved   {totals['offenders']:>8,}")
    emit(f"    the same, before resolution      {totals['apparent_offenders_before_resolution']:>8,}")
    emit(f"    inflation resolution removes     {totals['inflation_removed']:>8,}"
         f"   {totals['inflation_pct']:.1f}%")
    emit()
    emit("    A case density map shows where offences are recorded. Offender")
    emit("    density needs a person entity, and without one the same man")
    emit("    working three stations counts as three offenders.")
    emit()
    emit(f"    anomalous district months        "
         f"{hotspot_report['anomalous_district_months']:>8,}"
         f"   above {hotspot_report['anomaly_multiple']}x the trailing "
         f"{hotspot_report['trailing_months']} month median")

    # ---- undetected -----------------------------------------------------
    emit()
    emit("-" * 78)
    emit("UNDETECTED CASE MATCHER")
    emit("-" * 78)
    ranking = undetected.rank(corpus)
    identity_map, culprits = load_ground_truth(corpus_dir)
    accuracy = undetected.measure(corpus, ranking, identity_map, culprits)

    combined = accuracy["combined"]
    emit()
    emit(f"    cases ranked            {combined.get('cases_measured', 0):>8,}")
    emit(f"    candidate pool          {combined.get('candidate_pool', 0):>8,} identities")
    emit()
    emit(f"    {'ranking':<16} {'hit@1':>8} {'hit@3':>8} {'hit@10':>8} "
         f"{'hit@50':>8} {'MRR':>8}")
    emit()
    for name in ("combined", "modus_only", "spatial_only", "temporal_only"):
        entry = accuracy[name]
        emit(f"    {name:<16} {entry.get('hit_at_1', 0):>8.4f}"
             f" {entry.get('hit_at_3', 0):>8.4f} {entry.get('hit_at_10', 0):>8.4f}"
             f" {entry.get('hit_at_50', 0):>8.4f}"
             f" {entry.get('mean_reciprocal_rank', 0):>8.4f}")
    emit()
    emit(f"    random baseline hit@10  "
         f"{combined.get('random_baseline_hit_at_10', 0):.6f}")
    emit(f"    culprit unreachable     {combined.get('culprit_unreachable', 0):>8,}"
         f"   ground truth person holds no resolved record")
    emit()
    emit("    Measured against the generator's record of who actually committed")
    emit("    each undetected case. A hit means any resolved identity holding")
    emit("    that person's records appears in the top k, which does not")
    emit("    penalise this layer for a split the resolver caused.")

    elapsed = round(time.perf_counter() - started, 3)
    emit()
    emit(f"    total {elapsed:.3f} s")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "corpus": {
            "accused_rows": len(corpus.accused),
            "resolved_identities": len(corpus.rows_of_identity),
            "undetected_cases": len(corpus.undetected),
        },
        "co_offender_graph": graph_report,
        "communities": community_report,
        "community_summaries": summaries,
        "profiles": profile_report,
        "hotspots": hotspot_report,
        "undetected": {
            "weights": ranking["weights"],
            "spatial_horizon_km": undetected.SPATIAL_HORIZON_KM,
            "temporal_horizon_days": undetected.TEMPORAL_HORIZON_DAYS,
            "accuracy": accuracy,
        },
        "elapsed_seconds": elapsed,
    }

    (corpus_dir / "downstream_report.json").write_text(
        json.dumps(report, indent=2, default=float), encoding="utf-8")
    (corpus_dir / "downstream_report.txt").write_text(
        "\n".join(out) + "\n", encoding="utf-8")

    emit()
    emit(f"    wrote {corpus_dir / 'downstream_report.json'}")
    return report


def main() -> int:
    _configure_console()
    parser = argparse.ArgumentParser(description="Run Layer 8 downstream products.")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    run(args.corpus, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
