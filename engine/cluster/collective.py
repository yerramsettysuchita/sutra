"""Layer 6. Collective iteration to a fixed point.

Layer 3f is self referential. Relational evidence asks whether two accused rows
share a co accused, and answering that needs to know who the co accused *are*,
which is the question resolution is trying to answer.

The first pass breaks the circle by identifying co accused on their folded name
key, which is exactly the naive join the project argues against. Once Layer 5
has produced identities, the relational evidence can be recomputed against those
identities instead. New edges appear, scores change, and the partition moves.

So iterate. Recompute relational evidence from the current partition, rescore,
recluster, and repeat until the partition stops moving.

Convergence is not guaranteed in theory. In practice it settles in a handful of
iterations, and the curve is reported rather than asserted, because a claim of
convergence without a curve is a claim.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np

from engine.cluster import correlation
from engine.features import signals as S


def relational_from_partition(
    case_id: list[str],
    labels: np.ndarray,
    arrest_officer: list[str],
    pair_a: np.ndarray,
    pair_b: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Recompute signal f against resolved identities rather than name keys.

    This is the only part of the feature set that changes between iterations,
    which is what makes the loop cheap.
    """
    by_case: dict[str, set[int]] = defaultdict(set)
    for row, cid in enumerate(case_id):
        by_case[cid].add(int(labels[row]))

    n_pairs = len(pair_a)
    level = np.empty(n_pairs, dtype=np.int8)
    score = np.zeros(n_pairs, dtype=np.float32)

    for k in range(n_pairs):
        i, j = int(pair_a[k]), int(pair_b[k])
        others_a = by_case[case_id[i]] - {int(labels[i])}
        others_b = by_case[case_id[j]] - {int(labels[j])}
        has_officers = bool(arrest_officer[i]) and bool(arrest_officer[j])
        computable = bool(others_a and others_b) or has_officers
        shared_co = bool(others_a & others_b)
        shared_off = has_officers and arrest_officer[i] == arrest_officer[j]
        level[k] = S.relational_level(shared_co, shared_off, computable)
        score[k] = (2.0 if shared_co else 0.0) + (1.0 if shared_off else 0.0)

    return level, score


def damp(new_score: np.ndarray, previous_score: np.ndarray | None,
         factor: float) -> np.ndarray:
    """Blend the new relational evidence with the previous iteration's.

    `factor` is the weight on the new evidence. 1.0 replaces outright, which is
    the undamped loop. Lower values let the partition move toward the new
    evidence rather than jumping onto it.

    Damping is applied to the continuous relational score rather than to the
    ordinal level, because averaging two ordinal codes is meaningless. Levels
    are re-derived from the blended score using the same cut points, so the
    method is unchanged and only its trajectory is.
    """
    if previous_score is None or factor >= 1.0:
        return new_score
    return factor * new_score + (1.0 - factor) * previous_score


def levels_from_score(score: np.ndarray, computable: np.ndarray) -> np.ndarray:
    """Re-derive relational levels from a blended score.

    Same cut points as engine.features.signals.relational_level. A blended
    score above 1.5 is dominated by shared co accused, above 0.5 by a shared
    arresting officer.
    """
    out = np.where(score >= 1.5, 2, np.where(score >= 0.5, 1, 0)).astype(np.int8)
    return np.where(computable, out, S.NOT_COMPUTABLE).astype(np.int8)


# Cost charged per edge cut to repair a cannot link violation. The repair is
# not free: it is the clusterer admitting it built something the schema forbids,
# and an objective that ignored it would prefer the partition that over merged
# hardest and then tore itself apart. One unit of log likelihood ratio per edge
# puts the penalty on the same scale as the evidence it is trading against.
REPAIR_COST = 1.0


def objective(labels: np.ndarray, pair_a: np.ndarray, pair_b: np.ndarray,
              scores: np.ndarray, threshold: float,
              edges_removed: int = 0) -> float:
    """The engine's own score for a partition. No ground truth anywhere.

    This is the correlation clustering objective the clusterer is already
    implicitly optimising, written down so it can be compared across
    iterations.

    Every candidate pair placed in one cluster contributes `score - threshold`.
    A pair the model likes contributes positively and a pair it does not
    contributes negatively, so the objective rewards merges the evidence
    supports and charges for merges it does not. Pairs left in separate
    clusters contribute nothing, which is what makes the sum well defined
    without needing to enumerate the non edges.

    Then the repairs are charged, because a partition that had to be cut apart
    to satisfy the schema is worse than one that never violated it.

    Returns log likelihood ratio units, so it is directly comparable to the
    weights in Layer 4 and to the threshold.
    """
    same = labels[pair_a] == labels[pair_b]
    retained = float((scores[same] - threshold).sum())
    return retained - REPAIR_COST * float(edges_removed)


def iterate(
    records,
    features,
    pair_a: np.ndarray,
    pair_b: np.ndarray,
    case_of: np.ndarray,
    rescore,
    initial_labels: np.ndarray,
    truth: np.ndarray | None = None,
    max_iterations: int = 8,
    damping: float = 1.0,
) -> dict:
    """Run the collective loop and report every partition it visited.

    `rescore` takes the feature levels and returns the pair scores and the
    threshold, so this module does not need to know about Layer 4.

    `labels` is the last iteration, and that is what ships.

    Every iteration is also scored against `objective` above, and the best
    scoring partition is returned separately as `best_labels`. That was an
    attempt to rescue the layer: the loop does not converge, so rather than
    returning whichever partition iteration eight happened to land on, select
    the best one on a criterion that reads no labels.

    It does not work. Measured across three corpus seeds it improved F1 on one
    and made it worse on two, for a mean change of -0.0000. The objective is
    close to uncorrelated with the metric anyone cares about over the narrow
    band of partitions this loop visits. So selection is measured and reported
    and is NOT used to choose what ships. See ADR 025 and
    scripts/layer6_selection_study.py.
    """
    labels = initial_labels
    history: list[dict] = []
    previous = labels.copy()
    previous_score: np.ndarray | None = None
    converged = False
    n_rows = len(records)
    best = {"objective": float("-inf"), "labels": initial_labels, "iteration": 0}

    for iteration in range(1, max_iterations + 1):
        level, score = relational_from_partition(
            records.case_id, labels, records.arrest_officer, pair_a, pair_b)
        computable = level != S.NOT_COMPUTABLE
        score = damp(score, previous_score, damping)
        previous_score = score
        level = levels_from_score(score, computable)
        features.levels["relational"] = level
        features.scores["relational"] = score

        scores, threshold = rescore(features)
        result = correlation.cluster(
            n_rows, pair_a, pair_b, scores, threshold, case_of)
        labels = result.labels

        # Cluster ids are arbitrary and are renumbered every iteration, so
        # comparing them directly reports the whole corpus as moved. Compare
        # canonical forms, where each row carries the lowest row index in its
        # cluster, which is invariant to relabelling.
        moved = int((_canonical(labels) != _canonical(previous)).sum())

        value = objective(labels, pair_a, pair_b, scores, threshold,
                          result.edges_removed)
        if value > best["objective"]:
            best = {"objective": value, "labels": labels.copy(),
                    "iteration": iteration}

        entry = {
            "iteration": iteration,
            "rows_reassigned": moved,
            "clusters": result.n_clusters,
            "violations": result.violations_after,
            "objective": round(value, 4),
        }
        if truth is not None:
            entry.update(correlation.pairwise_scores(labels, truth))
        history.append(entry)

        # Converged when the partition stops moving, or when it is only
        # flipping a handful of rows back and forth. The second condition
        # matters because the loop is not a contraction and a few borderline
        # records oscillate indefinitely without the answer changing.
        if moved == 0:
            converged = True
            break
        if iteration > 1 and moved <= max(1, int(0.002 * n_rows)):
            converged = True
            break
        previous = labels.copy()

    return {
        # The last iteration. This is what ships, because selecting on the
        # objective was measured and did not beat it.
        "labels": labels,
        "last_labels": labels,
        # Reported as a diagnostic, never used to choose.
        "best_labels": best["labels"],
        "best_iteration": best["iteration"],
        "best_objective": best["objective"],
        "last_objective": history[-1]["objective"] if history else None,
        "selected_over_last": best["iteration"] != len(history),
        "history": history,
        "converged": converged,
        "iterations": len(history),
        "damping": damping,
    }


def sweep(build_iteration, factors: tuple[float, ...] = (1.0, 0.5, 0.3)) -> dict:
    """Run the collective loop at several damping factors.

    Reported as a sweep rather than a single number, because a damping factor
    that happens to converge is a property of this corpus until it has been
    shown to hold across a range.
    """
    runs = {}
    for factor in factors:
        result = build_iteration(factor)
        runs[f"{factor:.2f}"] = {
            "damping": factor,
            "converged": result["converged"],
            "iterations": result["iterations"],
            "history": result["history"],
            "final_moved": result["history"][-1]["rows_reassigned"]
            if result["history"] else None,
        }
    return runs


def _canonical(labels: np.ndarray) -> np.ndarray:
    """Relabel a partition so each row carries the lowest row index in its group.

    Invariant to renumbering, so two labellings of the same grouping compare
    equal element by element.
    """
    first: dict[int, int] = {}
    out = np.empty_like(labels)
    for row, label in enumerate(labels.tolist()):
        if label not in first:
            first[label] = row
        out[row] = first[label]
    return out


def _same_partition(a: np.ndarray, b: np.ndarray) -> bool:
    """Whether two labellings induce the same grouping, ignoring label values."""
    mapping: dict[int, int] = {}
    reverse: dict[int, int] = {}
    for x, y in zip(a.tolist(), b.tolist()):
        if x in mapping:
            if mapping[x] != y:
                return False
        else:
            if y in reverse:
                return False
            mapping[x] = y
            reverse[y] = x
    return True
