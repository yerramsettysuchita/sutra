"""Layer 8. The co offender graph on resolved identities.

This is the product the problem statement asked for and the one the KSP schema
cannot supply. A graph built directly from Accused rows is a graph of
paperwork, because each row is scoped to one FIR. Built on resolved identities
it becomes a graph of people.

An edge joins two identities that appear on the same FIR.

The number that matters is how many edges exist only after resolution. Before
resolution, one offender written five ways is five nodes, each carrying a
fifth of their relationships. An edge is counted as recovered when it attaches
through a name rendering that a naive join would have treated as a different
person, so it was invisible until the records were merged.
"""

from __future__ import annotations

from collections import Counter, defaultdict

import networkx as nx

from engine.downstream.context import ResolvedCorpus


def anchor_names(corpus: ResolvedCorpus) -> dict[str, str]:
    """The name string each identity carries most often.

    This is the node a naive `GROUP BY AccusedName` would have produced for
    that person. Everything else they were written as would have been a
    different node.
    """
    out: dict[str, str] = {}
    for identity, rows in corpus.rows_of_identity.items():
        counts = Counter(corpus.accused[row]["AccusedName"] for row in rows)
        out[identity] = counts.most_common(1)[0][0]
    return out


def build(corpus: ResolvedCorpus) -> nx.Graph:
    """Co offender graph. Nodes are resolved identities, edges are shared FIRs."""
    anchors = anchor_names(corpus)

    rows_by_case: dict[str, list[int]] = defaultdict(list)
    for row, case_id in enumerate(corpus.case_of_row):
        rows_by_case[case_id].append(row)

    graph = nx.Graph()
    for identity, rows in corpus.rows_of_identity.items():
        graph.add_node(
            identity,
            records=len(rows),
            cases=len({corpus.case_of_row[row] for row in rows}),
            merged=len(rows) > 1,
            label=anchors[identity],
        )

    for case_id, rows in rows_by_case.items():
        if len(rows) < 2:
            continue
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                ia = corpus.identity_of_row[a]
                ib = corpus.identity_of_row[b]
                if ia == ib:
                    # Layer 5 placed two rows of one FIR in one identity. The
                    # cannot link constraint should make this impossible, and
                    # it is counted rather than silently skipped.
                    graph.graph.setdefault("constraint_violations", 0)
                    graph.graph["constraint_violations"] += 1
                    continue
                through_anchor = (
                    corpus.accused[a]["AccusedName"] == anchors[ia]
                    and corpus.accused[b]["AccusedName"] == anchors[ib]
                )
                if graph.has_edge(ia, ib):
                    data = graph.edges[ia, ib]
                    data["shared_cases"] += 1
                    data["cases"].append(case_id)
                    data["visible_before"] = data["visible_before"] or through_anchor
                else:
                    graph.add_edge(ia, ib, shared_cases=1, cases=[case_id],
                                   visible_before=through_anchor)

    for _, _, data in graph.edges(data=True):
        data["recovered"] = not data["visible_before"]

    return graph


def report(graph: nx.Graph) -> dict:
    edges = list(graph.edges(data=True))
    recovered = sum(1 for _, _, d in edges if d["recovered"])
    degrees = [d for _, d in graph.degree()]
    connected = [n for n, d in graph.degree() if d > 0]
    components = list(nx.connected_components(graph.subgraph(connected))) if connected else []

    return {
        "nodes": graph.number_of_nodes(),
        "nodes_with_at_least_one_edge": len(connected),
        "edges": len(edges),
        "edges_recovered_by_resolution": recovered,
        "edges_visible_before_resolution": len(edges) - recovered,
        "recovered_share": round(recovered / len(edges), 4) if edges else 0.0,
        "mean_degree": round(sum(degrees) / len(degrees), 4) if degrees else 0.0,
        "max_degree": max(degrees) if degrees else 0,
        "components_among_connected": len(components),
        "largest_component": max((len(c) for c in components), default=0),
        "constraint_violations": graph.graph.get("constraint_violations", 0),
    }
