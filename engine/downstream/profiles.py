"""Layer 8. Repeat offender profiles.

One record per resolved identity. Everything here is an aggregate over the
records Layer 5 merged, so a profile is only as good as the merge that
produced it, and the merge confidence travels with it.

The before and after counts are the point. Before resolution this person was
several apparently unrelated accused rows, each carrying a fraction of their
history. The profile states both numbers so the difference is visible rather
than claimed.

No protected attribute is read here. CasteID, ReligionID and OccupationID
exist on the Accused row and are never touched, which the guard in
engine/policy.py enforces on the column list.
"""

from __future__ import annotations

from collections import Counter

import networkx as nx

from engine.downstream.context import ResolvedCorpus
from engine.policy import assert_no_excluded_features

PROFILE_FIELDS = [
    "identity", "records", "cases", "districts", "circles", "mo_signature",
    "co_accused", "first_case", "last_case", "active_days",
]
assert_no_excluded_features(PROFILE_FIELDS, context="engine.downstream.profiles")


def build(corpus: ResolvedCorpus, graph: nx.Graph, limit: int | None = None) -> list[dict]:
    ranked = sorted(
        corpus.rows_of_identity.items(),
        key=lambda kv: (-len({corpus.case_of_row[r] for r in kv[1]}), kv[0]),
    )
    if limit:
        ranked = ranked[:limit]

    out = []
    for identity, rows in ranked:
        case_ids = [corpus.case_of_row[row] for row in rows]
        unique_cases = sorted(set(case_ids))
        dates = sorted(corpus.case_date(c) for c in unique_cases)

        districts = Counter(corpus.district_name(c) for c in unique_cases)
        stations = Counter(corpus.station_name(c) for c in unique_cases)
        circles = Counter(corpus.circle_of(c) for c in unique_cases)
        mo = Counter(
            corpus.subheads.get(corpus.cases[c]["CrimeSubHeadID"], "unknown")
            for c in unique_cases
        )
        renderings = Counter(corpus.accused[row]["AccusedName"] for row in rows)

        neighbours = []
        if graph.has_node(identity):
            for other in graph.neighbors(identity):
                data = graph.edges[identity, other]
                neighbours.append({
                    "identity": other,
                    "label": graph.nodes[other].get("label", other),
                    "shared_cases": data["shared_cases"],
                    "recovered": data["recovered"],
                })
            neighbours.sort(key=lambda x: -x["shared_cases"])

        out.append({
            "identity": identity,
            "label": renderings.most_common(1)[0][0],
            "records": len(rows),
            "cases": len(unique_cases),
            "distinct_renderings": len(renderings),
            "renderings": [
                {"name": name, "times": times} for name, times in renderings.most_common()
            ],
            "districts_touched": len(districts),
            "districts": [{"district": d, "cases": c} for d, c in districts.most_common()],
            "stations": [{"station": s, "cases": c} for s, c in stations.most_common()],
            "primary_circle": circles.most_common(1)[0][0] if circles else None,
            "circles_touched": len(circles),
            "mo_signature": [
                {"offence": name, "cases": count, "share": round(count / len(unique_cases), 4)}
                for name, count in mo.most_common()
            ],
            "co_accused_circle": neighbours,
            "co_accused_count": len(neighbours),
            "recovered_relationships": sum(1 for x in neighbours if x["recovered"]),
            "first_case": dates[0].isoformat() if dates else None,
            "last_case": dates[-1].isoformat() if dates else None,
            "active_days": (dates[-1] - dates[0]).days if len(dates) > 1 else 0,
            # The before and after. A naive join would have produced one node
            # per distinct rendering, each holding only its own cases.
            "before_resolution": {
                "apparent_people": len(renderings),
                "largest_fragment_cases": max(
                    len({corpus.case_of_row[row] for row in rows
                         if corpus.accused[row]["AccusedName"] == name})
                    for name in renderings
                ),
            },
            "after_resolution": {"people": 1, "cases": len(unique_cases)},
        })
    return out


def report(profiles: list[dict]) -> dict:
    merged = [p for p in profiles if p["records"] > 1]
    multi_district = [p for p in profiles if p["districts_touched"] > 1]
    return {
        "profiles": len(profiles),
        "merged_identities": len(merged),
        "single_record_identities": len(profiles) - len(merged),
        "identities_touching_more_than_one_district": len(multi_district),
        "max_cases_on_one_identity": max((p["cases"] for p in profiles), default=0),
        "max_renderings_on_one_identity": max(
            (p["distinct_renderings"] for p in profiles), default=0),
        "identities_with_co_accused": sum(1 for p in profiles if p["co_accused_count"]),
        "total_recovered_relationships": sum(
            p["recovered_relationships"] for p in profiles),
    }
