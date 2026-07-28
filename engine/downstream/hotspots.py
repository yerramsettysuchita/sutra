"""Layer 8. Hotspots and trends.

The distinction that makes this more than another heatmap.

A case density map shows where offences are recorded. That is a map of
reporting, and every district in Karnataka already has one. This computes two
surfaces and reports both.

  case density        offences per grid cell, what any crime map shows
  offender density    distinct resolved identities per grid cell

The second is only computable after Layers 1 to 7. Without a person entity the
same offender working three stations under three renderings counts as three
offenders, so an area with one busy repeat offender looks identical to an area
with three occasional ones. Those need different responses and the raw schema
cannot tell them apart.

The ratio of the two is the number worth looking at. High cases per offender is
a small group working an area repeatedly. Low is a dispersed problem.

Anomaly rule, stated and not tuned. A district month is flagged when its case
count exceeds the trailing median of the twelve preceding months by a factor of
ANOMALY_MULTIPLE. Twelve months, because anything shorter tracks the seasonality
it is meant to see through. The multiple is fixed at 2.0 before any measurement
and is not adjusted afterwards.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import date

from engine.downstream.context import ResolvedCorpus

# Grid resolution in degrees. Karnataka spans roughly 5 degrees of latitude and
# 6 of longitude, so 0.25 gives cells of about 25 km, which is a district
# subdivision rather than a street.
CELL = 0.25

# Trailing window for the anomaly baseline, in months.
TRAILING_MONTHS = 12

# Fixed before measurement. Never adjusted.
ANOMALY_MULTIPLE = 2.0

# A district month with fewer cases than this is too small for a ratio to mean
# anything, so it is never flagged.
MIN_CASES_TO_FLAG = 5


def _cell(lat: float, lon: float) -> tuple[float, float]:
    return (round(lat // CELL * CELL, 4), round(lon // CELL * CELL, 4))


def grid(corpus: ResolvedCorpus, head: str | None = None) -> list[dict]:
    """Case and offender density per grid cell.

    Offender density counts distinct resolved identities, which is the whole
    reason this layer sits after resolution rather than before it.
    """
    cases_in: dict[tuple[float, float], set[str]] = defaultdict(set)
    people_in: dict[tuple[float, float], set[str]] = defaultdict(set)
    repeat_in: dict[tuple[float, float], set[str]] = defaultdict(set)
    raw_names_in: dict[tuple[float, float], set[str]] = defaultdict(set)

    cases_per_identity = Counter()
    for row, identity in enumerate(corpus.identity_of_row):
        cases_per_identity[identity] += 1

    for row, identity in enumerate(corpus.identity_of_row):
        case_id = corpus.case_of_row[row]
        case = corpus.cases[case_id]
        if head and corpus.subheads.get(case["CrimeSubHeadID"]) != head:
            continue
        try:
            key = _cell(float(case["Latitude"]), float(case["Longitude"]))
        except (TypeError, ValueError):
            continue
        cases_in[key].add(case_id)
        people_in[key].add(identity)
        raw_names_in[key].add(corpus.accused[row]["AccusedName"])
        if cases_per_identity[identity] > 1:
            repeat_in[key].add(identity)

    out = []
    for key, case_ids in cases_in.items():
        lat, lon = key
        people = len(people_in[key])
        out.append({
            "lat": lat,
            "lon": lon,
            "cases": len(case_ids),
            "offenders": people,
            "repeat_offenders": len(repeat_in[key]),
            # What a naive join would have counted here. The gap between this
            # and `offenders` is the inflation resolution removes.
            "apparent_offenders_before_resolution": len(raw_names_in[key]),
            "cases_per_offender": round(len(case_ids) / people, 3) if people else 0.0,
        })
    out.sort(key=lambda c: -c["cases"])
    return out


def districts(corpus: ResolvedCorpus) -> list[dict]:
    """District aggregates through the Unit hierarchy."""
    cases_in: dict[str, set[str]] = defaultdict(set)
    people_in: dict[str, set[str]] = defaultdict(set)
    repeat_in: dict[str, set[str]] = defaultdict(set)
    names_in: dict[str, set[str]] = defaultdict(set)
    heads_in: dict[str, Counter] = defaultdict(Counter)

    cases_per_identity = Counter()
    for identity in corpus.identity_of_row:
        cases_per_identity[identity] += 1

    for row, identity in enumerate(corpus.identity_of_row):
        case_id = corpus.case_of_row[row]
        name = corpus.district_name(case_id)
        cases_in[name].add(case_id)
        people_in[name].add(identity)
        names_in[name].add(corpus.accused[row]["AccusedName"])
        heads_in[name][corpus.subheads.get(
            corpus.cases[case_id]["CrimeSubHeadID"], "unknown")] += 1
        if cases_per_identity[identity] > 1:
            repeat_in[name].add(identity)

    out = []
    for name, case_ids in cases_in.items():
        people = len(people_in[name])
        out.append({
            "district": name,
            "cases": len(case_ids),
            "offenders": people,
            "repeat_offenders": len(repeat_in[name]),
            "apparent_offenders_before_resolution": len(names_in[name]),
            "cases_per_offender": round(len(case_ids) / people, 3) if people else 0.0,
            "top_offence": heads_in[name].most_common(1)[0][0] if heads_in[name] else None,
        })
    out.sort(key=lambda d: -d["cases"])
    return out


def _month(when: date) -> str:
    return f"{when.year:04d}-{when.month:02d}"


def trends(corpus: ResolvedCorpus) -> list[dict]:
    """Monthly case counts per district, with the anomaly flag."""
    per: dict[str, Counter] = defaultdict(Counter)
    for case_id in {corpus.case_of_row[r] for r in range(len(corpus.accused))}:
        per[corpus.district_name(case_id)][_month(corpus.case_date(case_id))] += 1
    # Undetected cases carry no accused row, so add them from the case table.
    for entry in corpus.undetected:
        case_id = entry["CaseMasterID"]
        per[corpus.district_name(case_id)][_month(corpus.case_date(case_id))] += 1

    all_months = sorted({m for counts in per.values() for m in counts})

    out = []
    for district, counts in per.items():
        series = []
        anomalies = 0
        for index, month in enumerate(all_months):
            value = counts.get(month, 0)
            window = [counts.get(m, 0)
                      for m in all_months[max(0, index - TRAILING_MONTHS):index]]
            baseline = statistics.median(window) if window else 0.0
            flagged = (
                len(window) >= TRAILING_MONTHS
                and value >= MIN_CASES_TO_FLAG
                and baseline > 0
                and value >= ANOMALY_MULTIPLE * baseline
            )
            if flagged:
                anomalies += 1
            series.append({
                "month": month,
                "cases": value,
                "trailing_median": round(baseline, 2),
                "anomaly": flagged,
            })
        out.append({
            "district": district,
            "total_cases": sum(counts.values()),
            "anomalous_months": anomalies,
            "series": series,
        })
    out.sort(key=lambda d: -d["total_cases"])
    return out, all_months


def report(corpus: ResolvedCorpus) -> dict:
    cells = grid(corpus)
    by_district = districts(corpus)
    trend_rows, months = trends(corpus)

    total_cases = sum(c["cases"] for c in cells)
    total_offenders = sum(c["offenders"] for c in cells)
    total_apparent = sum(c["apparent_offenders_before_resolution"] for c in cells)
    flagged = sum(d["anomalous_months"] for d in trend_rows)

    return {
        "cell_degrees": CELL,
        "anomaly_multiple": ANOMALY_MULTIPLE,
        "trailing_months": TRAILING_MONTHS,
        "min_cases_to_flag": MIN_CASES_TO_FLAG,
        "cells": len(cells),
        "totals": {
            "cases_placed": total_cases,
            "offenders": total_offenders,
            "apparent_offenders_before_resolution": total_apparent,
            "inflation_removed": total_apparent - total_offenders,
            "inflation_pct": round(
                ((total_apparent - total_offenders) / total_apparent * 100)
                if total_apparent else 0.0, 2),
        },
        "anomalous_district_months": flagged,
        "months": months,
        "grid": cells,
        "districts": by_district,
        "trends": trend_rows,
    }
