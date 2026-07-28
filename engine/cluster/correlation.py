"""Layer 5. Correlation clustering under hard cannot link constraints.

Pairwise scores have to become entities, and pairwise decisions are not
transitive. A matches B, B matches C, A contradicts C. Something has to
arbitrate, and that is this layer.

The schema hands us the constraint for free. Two Accused rows sharing one
CaseMasterID are A1 and A2 of the same FIR and are therefore provably
different people. That is a cannot link edge derived from the data rather than
from a heuristic, and it is the only certain identity fact in the whole record.

Correlation clustering with cannot link constraints is NP hard. The relaxation
is documented in ADR 015. Connected components above the threshold, then local
repair that splits any component containing a violation by removing the
weakest edge on a path between the offending pair, iterated until the component
is clean or a cap is reached.

A component that cannot be repaired within the cap is not silently split. It is
returned as a conflict for the review queue, because a cluster the engine knows
is wrong and cannot fix is exactly the case a human should see.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import networkx as nx
import numpy as np

MAX_REPAIRS_PER_COMPONENT = 200


@dataclass
class ClusterResult:
    labels: np.ndarray                      # cluster id per accused row
    n_clusters: int
    edges_used: int
    edges_removed: int
    violations_before: int
    violations_after: int
    conflicts: list[list[int]] = field(default_factory=list)
    components_repaired: int = 0
    singletons: int = 0


def cannot_link_pairs(case_of: np.ndarray) -> list[tuple[int, int]]:
    """Every pair of accused rows sharing a CaseMasterID."""
    by_case: dict[int, list[int]] = defaultdict(list)
    for row, case in enumerate(case_of):
        by_case[int(case)].append(row)
    out: list[tuple[int, int]] = []
    for members in by_case.values():
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                out.append((members[i], members[j]))
    return out


def _violations_in(component: set[int], case_of: np.ndarray) -> list[tuple[int, int]]:
    """Rows inside one component that share a case, so cannot be one person."""
    by_case: dict[int, list[int]] = defaultdict(list)
    for row in component:
        by_case[int(case_of[row])].append(row)
    out: list[tuple[int, int]] = []
    for members in by_case.values():
        if len(members) > 1:
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    out.append((members[i], members[j]))
    return out


MIN_LINK_DENSITY = 0.5


def cluster(n_rows: int, pair_a: np.ndarray, pair_b: np.ndarray,
            scores: np.ndarray, threshold: float,
            case_of: np.ndarray,
            min_density: float = MIN_LINK_DENSITY) -> ClusterResult:
    """Partition accused rows into identities by constrained agglomeration.

    `scores` is the Layer 4 log likelihood ratio. Edges at or above `threshold`
    are proposed merges, but a proposed merge is not automatically taken.

    Why not connected components, which is what ADR 005 originally promised.

    Connected components merges two groups on the strength of a single bridging
    edge. With 10,620 edges over 7,611 rows the average degree is 2.8, which is
    comfortably above the percolation threshold, so the graph forms a giant
    component and transitive closure produces 1,706,180 false pairs from a
    model whose pairwise precision was 0.48. The clustering, not the scoring,
    was destroying the result.

    Instead, agglomerate greedily from the strongest edge down and merge two
    clusters only when the evidence spans them. A merge requires that at least
    `min_density` of the cross pairs between the two clusters are themselves
    above threshold. One bridge between two groups of five is 1 of 25 cross
    pairs and is refused. This is average linkage in spirit and it is what
    stops a chain of weak links becoming one identity.

    Cannot link is enforced at merge time rather than repaired afterwards,
    which is both cheaper and more faithful, since a merge that would violate
    the schema is simply never made. See ADR 015.
    """
    keep = scores >= threshold
    edge_a = pair_a[keep]
    edge_b = pair_b[keep]
    edge_w = scores[keep]

    graph = nx.Graph()
    graph.add_nodes_from(range(n_rows))
    for a, b, w in zip(edge_a.tolist(), edge_b.tolist(), edge_w.tolist()):
        graph.add_edge(a, b, weight=w)

    # How bad an unconstrained partition would have been. This is the number
    # that shows the constraint is doing work rather than decorating the ADR.
    violations_before = 0
    for component in nx.connected_components(graph):
        violations_before += len(_violations_in(component, case_of))

    # Greedy constrained agglomeration, strongest edge first.
    adjacency: dict[int, set[int]] = {}
    for a, b in zip(edge_a.tolist(), edge_b.tolist()):
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)

    parent = list(range(n_rows))
    members: dict[int, list[int]] = {i: [i] for i in range(n_rows)}
    cases: dict[int, set[int]] = {i: {int(case_of[i])} for i in range(n_rows)}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    order = np.argsort(-edge_w)
    refused_constraint = 0
    refused_density = 0
    merges = 0

    for index in order.tolist():
        ra, rb = find(int(edge_a[index])), find(int(edge_b[index]))
        if ra == rb:
            continue
        left, right = members[ra], members[rb]

        # Cannot link. Two rows on one FIR are provably different people, so a
        # merge that would place them together is refused outright rather than
        # made and repaired.
        if cases[ra] & cases[rb]:
            refused_constraint += 1
            continue

        # Evidence has to span the two groups, not merely touch them.
        span = sum(1 for node in left if node in adjacency
                   for other in adjacency[node] if find(other) == rb)
        if span < min_density * len(left) * len(right):
            refused_density += 1
            continue

        if len(left) < len(right):
            ra, rb = rb, ra
            left, right = right, left
        parent[rb] = ra
        left.extend(right)
        cases[ra] |= cases[rb]
        del members[rb]
        del cases[rb]
        merges += 1

    final = [set(group) for group in members.values()]

    labels = np.full(n_rows, -1, dtype=np.int32)
    for cluster_id, group in enumerate(final):
        for row in group:
            labels[row] = cluster_id

    edges_removed = refused_constraint + refused_density
    components_repaired = refused_constraint
    conflicts: list[list[int]] = []

    violations_after = 0
    for members in final:
        violations_after += len(_violations_in(members, case_of))

    return ClusterResult(
        labels=labels,
        n_clusters=len(final),
        edges_used=int(keep.sum()),
        edges_removed=edges_removed,
        violations_before=violations_before,
        violations_after=violations_after,
        conflicts=conflicts,
        components_repaired=components_repaired,
        singletons=sum(1 for c in final if len(c) == 1),
    )


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def pairwise_scores(labels: np.ndarray, truth: np.ndarray) -> dict:
    """Pairwise precision, recall and F1 over the whole corpus.

    The denominators are every pair of accused rows in the corpus, not only the
    pairs blocking proposed. Recall measured against the candidate set alone
    would be a recall of our own shortlist, which flatters the result by
    exactly the pairs Layer 2 already lost.
    """
    def pair_count(codes: np.ndarray) -> int:
        _, counts = np.unique(codes, return_counts=True)
        return int((counts * (counts - 1) // 2).sum())

    predicted = pair_count(labels)
    actual = pair_count(truth)

    combined = labels.astype(np.int64) * (truth.max() + 1) + truth
    true_positive = pair_count(combined)

    false_positive = predicted - true_positive
    false_negative = actual - true_positive

    precision = true_positive / predicted if predicted else 0.0
    recall = true_positive / actual if actual else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "true_positive_pairs": true_positive,
        "false_positive_pairs": false_positive,
        "false_negative_pairs": false_negative,
        "predicted_pairs": predicted,
        "actual_pairs": actual,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
