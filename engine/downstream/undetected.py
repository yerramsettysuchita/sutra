"""Layer 8. Candidate ranking for undetected cases.

For every case closed as `ChargesheetDetails.cstype = 'C'`, true but the
offender not traced, rank resolved identities by how well the case fits what
that person is already on record for.

Three signals, all reused from Layer 3 rather than reimplemented.

  modus operandi   cosine between the case narrative and the identity's
                   centroid over BriefFacts
  spatial          Haversine from the case to the identity's nearest known
                   case, via engine.features.signals.haversine_km
  temporal         whether the case falls inside the identity's known active
                   window, and how far outside if not

Weights are fixed a priori at 0.5, 0.3, 0.2 and are not tuned against ground
truth. Each signal is also ranked on its own and reported, so a reader can see
which one is doing the work rather than taking the combination on trust.

WHAT THIS IS NOT. It scores a pair of cases, not a person. It produces no
persistent attribute of anybody, it does not rank the population, and asked
about a named individual it has nothing to say. It is a retrieval index over
records an investigator could have found by hand with unlimited time. See
docs/ethics.md section 4.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize

from engine.downstream.context import ResolvedCorpus
from engine.features.signals import haversine_km

WEIGHTS = {"modus": 0.5, "spatial": 0.3, "temporal": 0.2}

# Distance at which the spatial score reaches zero. Beyond a district's width
# the fact that two offences happened in Karnataka is not evidence.
SPATIAL_HORIZON_KM = 120.0

# Days outside the known active window at which the temporal score reaches
# zero. Roughly two years, which is the span over which the co offending
# literature still treats a criminal career as continuous.
TEMPORAL_HORIZON_DAYS = 730.0

TOP_K = 10


def _identity_case_index(corpus: ResolvedCorpus) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for row, identity in enumerate(corpus.identity_of_row):
        out[identity].append(corpus.case_of_row[row])
    return {k: sorted(set(v)) for k, v in out.items()}


def rank(corpus: ResolvedCorpus, top_k: int = TOP_K) -> dict:
    """Rank identities against every undetected case."""
    undetected_ids = [c["CaseMasterID"] for c in corpus.undetected]
    if not undetected_ids:
        return {"cases": [], "note": "no cstype C cases in this corpus"}

    identity_cases = _identity_case_index(corpus)
    identities = sorted(identity_cases)
    index_of = {identity: i for i, identity in enumerate(identities)}

    # ---- modus operandi -------------------------------------------------
    # One vector space over every case, so an undetected case and an
    # identity's history are comparable. Character n grams are included
    # because part of the corpus is written in Kannada and a word level model
    # alone treats the two scripts as disjoint vocabularies.
    all_cases = sorted(corpus.cases)
    case_index = {c: i for i, c in enumerate(all_cases)}
    briefs = [corpus.cases[c]["BriefFacts"] or "" for c in all_cases]

    word = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True,
                           min_df=2, max_features=40_000)
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 4), sublinear_tf=True,
                           min_df=3, max_features=40_000)
    matrix = normalize(hstack([word.fit_transform(briefs),
                               char.fit_transform(briefs)]).tocsr())

    # Identity centroid over its known cases.
    centroid_rows = []
    for identity in identities:
        rows = [case_index[c] for c in identity_cases[identity]]
        centroid_rows.append(np.asarray(matrix[rows].mean(axis=0)).ravel())
    centroids = normalize(np.vstack(centroid_rows))

    # ---- geography and time ---------------------------------------------
    lat = {c: float(corpus.cases[c]["Latitude"] or "nan") for c in all_cases}
    lon = {c: float(corpus.cases[c]["Longitude"] or "nan") for c in all_cases}

    identity_lat = [np.array([lat[c] for c in identity_cases[i]]) for i in identities]
    identity_lon = [np.array([lon[c] for c in identity_cases[i]]) for i in identities]
    identity_first = np.array([
        min(corpus.case_date(c) for c in identity_cases[i]).toordinal()
        for i in identities], dtype=float)
    identity_last = np.array([
        max(corpus.case_date(c) for c in identity_cases[i]).toordinal()
        for i in identities], dtype=float)

    results = []
    for case_id in undetected_ids:
        case = corpus.cases[case_id]
        vector = np.asarray(matrix[case_index[case_id]].todense()).ravel()
        modus = centroids @ vector
        modus = np.clip(modus, 0.0, 1.0)

        here_lat, here_lon = lat[case_id], lon[case_id]
        nearest = np.array([
            float(np.nanmin(haversine_km(here_lat, here_lon,
                                         identity_lat[i], identity_lon[i])))
            for i in range(len(identities))
        ])
        spatial = np.clip(1.0 - nearest / SPATIAL_HORIZON_KM, 0.0, 1.0)

        when = corpus.case_date(case_id).toordinal()
        outside = np.maximum(0.0, np.maximum(identity_first - when, when - identity_last))
        temporal = np.clip(1.0 - outside / TEMPORAL_HORIZON_DAYS, 0.0, 1.0)

        combined = (WEIGHTS["modus"] * modus
                    + WEIGHTS["spatial"] * spatial
                    + WEIGHTS["temporal"] * temporal)

        order = np.argsort(-combined)[:top_k]
        candidates = []
        for position, i in enumerate(order.tolist(), start=1):
            identity = identities[i]
            candidates.append({
                "rank": position,
                "identity": identity,
                "score": round(float(combined[i]), 4),
                "signals": {
                    "modus": round(float(modus[i]), 4),
                    "spatial": round(float(spatial[i]), 4),
                    "temporal": round(float(temporal[i]), 4),
                    "nearest_km": round(float(nearest[i]), 2),
                    "days_outside_window": int(outside[i]),
                },
                "known_cases": len(identity_cases[identity]),
            })

        results.append({
            "case_id": case_id,
            "crime_no": case["CrimeNo"],
            "registered": case["CrimeRegisteredDate"],
            "district": corpus.district_name(case_id),
            "station": corpus.station_name(case_id),
            "subhead": corpus.subheads.get(case["CrimeSubHeadID"], "unknown"),
            "brief_facts": case["BriefFacts"],
            "candidates": candidates,
            # Retained for the measurement pass, dropped before export.
            "_full_order": np.argsort(-combined),
            "_single": {
                "modus": np.argsort(-modus),
                "spatial": np.argsort(-spatial),
                "temporal": np.argsort(-temporal),
            },
        })

    return {"cases": results, "identities": identities, "index_of": index_of,
            "weights": WEIGHTS}


def measure(corpus: ResolvedCorpus, ranking: dict,
            identity_map: dict[str, str], culprits: dict[str, str]) -> dict:
    """Hit rate at 1, 3 and 10, and mean reciprocal rank, against ground truth.

    The target is not a single identity. Layer 5 may have split the true
    culprit across several resolved identities, so the correct target is the
    set of identities holding any of that person's records. A hit at rank k
    means any of them appears in the top k.

    That is the fair test. Penalising the ranker for a split the resolver
    caused would be measuring the wrong layer.
    """
    identities = ranking["identities"]
    cases = ranking["cases"]

    # True person to the set of resolved identities carrying their records.
    person_to_identities: dict[str, set[str]] = defaultdict(set)
    for record in corpus.accused:
        amid = record["AccusedMasterID"]
        person = identity_map.get(amid)
        if person:
            person_to_identities[person].add(corpus.identity_of[amid])

    def evaluate(order_key: str | None) -> dict:
        ranks: list[int | None] = []
        for entry in cases:
            culprit = culprits.get(entry["case_id"])
            if culprit is None:
                continue
            targets = person_to_identities.get(culprit, set())
            if not targets:
                ranks.append(None)
                continue
            order = (entry["_full_order"] if order_key is None
                     else entry["_single"][order_key])
            found = None
            for position, i in enumerate(order.tolist(), start=1):
                if identities[i] in targets:
                    found = position
                    break
            ranks.append(found)

        scored = [r for r in ranks if r is not None]
        total = len(ranks)
        if total == 0:
            return {"cases_measured": 0}

        def hit_at(k: int) -> float:
            return sum(1 for r in scored if r <= k) / total

        mrr = sum(1.0 / r for r in scored) / total
        return {
            "cases_measured": total,
            "culprit_unreachable": total - len(scored),
            "hit_at_1": round(hit_at(1), 4),
            "hit_at_3": round(hit_at(3), 4),
            "hit_at_10": round(hit_at(10), 4),
            "hit_at_50": round(hit_at(50), 4),
            "mean_reciprocal_rank": round(mrr, 4),
            "median_rank_when_found": (
                int(np.median(scored)) if scored else None),
            "candidate_pool": len(identities),
            "random_baseline_hit_at_10": round(10 / len(identities), 6),
        }

    return {
        "combined": evaluate(None),
        "modus_only": evaluate("modus"),
        "spatial_only": evaluate("spatial"),
        "temporal_only": evaluate("temporal"),
    }


def strip_internals(ranking: dict) -> list[dict]:
    """Drop the numpy orderings kept for measurement, leaving exportable rows."""
    out = []
    for entry in ranking["cases"]:
        row = {k: v for k, v in entry.items() if not k.startswith("_")}
        out.append(row)
    return out
