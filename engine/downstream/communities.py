"""Layer 8. Community detection over the co offender graph.

ADR 008 chose Leiden, because Louvain can return communities that are
internally disconnected and presenting a criminal group whose halves have no
link between them is exactly the failure this product cannot afford.

Leiden is not available. `leidenalg` and `igraph` are not installed and this
session may not install them, so the implementation uses NetworkX greedy
modularity maximisation, which is Clauset Newman Moore.

That choice is recorded rather than hidden, and it is checked rather than
trusted. Every returned community is tested for internal connectivity and any
that fails is reported, which is the specific guarantee Leiden would have
given for free.
"""

from __future__ import annotations

import networkx as nx
from networkx.algorithms.community import greedy_modularity_communities, modularity

from engine.downstream.context import ResolvedCorpus

MIN_COMMUNITY = 2


def detect(graph: nx.Graph) -> tuple[list[set[str]], dict]:
    """Communities over the connected part of the co offender graph.

    Isolated nodes are excluded before detection. An offender with no co
    offender is not a community of one, they are a person with no known
    associates, and including them inflates the count without adding meaning.
    """
    connected_nodes = [node for node, degree in graph.degree() if degree > 0]
    subgraph = graph.subgraph(connected_nodes)

    if subgraph.number_of_edges() == 0:
        return [], {
            "algorithm": "none, the graph has no edges",
            "communities": 0,
            "modularity": None,
        }

    communities = [set(c) for c in greedy_modularity_communities(subgraph)]
    score = modularity(subgraph, communities)

    disconnected = []
    for index, community in enumerate(communities):
        if not nx.is_connected(subgraph.subgraph(community)):
            disconnected.append(index)

    sizes = sorted((len(c) for c in communities), reverse=True)
    return communities, {
        "algorithm": "networkx greedy_modularity_communities, Clauset Newman Moore",
        "intended_algorithm": "Leiden, see ADR 008",
        "substitution_reason": (
            "leidenalg and igraph are not installed. Greedy modularity does not "
            "guarantee internally connected communities, so connectivity is "
            "verified explicitly below instead of assumed."
        ),
        "nodes_considered": subgraph.number_of_nodes(),
        "edges_considered": subgraph.number_of_edges(),
        "communities": len(communities),
        "modularity": round(float(score), 4),
        "largest_community": sizes[0] if sizes else 0,
        "communities_of_two_or_more": sum(1 for s in sizes if s >= MIN_COMMUNITY),
        "size_distribution": dict(
            sorted({s: sizes.count(s) for s in set(sizes)}.items())),
        "internally_disconnected_communities": len(disconnected),
        "connectivity_guarantee_held": len(disconnected) == 0,
    }


def summarise(communities: list[set[str]], graph: nx.Graph,
              corpus: ResolvedCorpus, limit: int = 40) -> list[dict]:
    """The largest communities, with enough context to be recognisable."""
    ordered = sorted(communities, key=len, reverse=True)[:limit]
    out = []
    for index, community in enumerate(ordered):
        if len(community) < MIN_COMMUNITY:
            continue
        sub = graph.subgraph(community)
        districts: dict[str, int] = {}
        cases: set[str] = set()
        for identity in community:
            for row in corpus.rows_of_identity.get(identity, []):
                case_id = corpus.case_of_row[row]
                cases.add(case_id)
                name = corpus.district_name(case_id)
                districts[name] = districts.get(name, 0) + 1
        recovered = sum(1 for _, _, d in sub.edges(data=True) if d["recovered"])
        out.append({
            "community_id": f"C{index:04d}",
            "size": len(community),
            "members": sorted(community),
            "internal_edges": sub.number_of_edges(),
            "recovered_edges": recovered,
            "internally_connected": nx.is_connected(sub),
            "cases": len(cases),
            "districts": sorted(districts, key=lambda k: -districts[k])[:3],
        })
    return out
