"""Export engine output into web/public/data for the client.

    python scripts/export_web.py

Reads what the engine has already written and produces five files. It never
invents a value. If an input is missing it fails and names the command that
produces it.

Note on cost. Per pair evidence is not persisted by the engine, only
aggregates are, so the scoring path is recomputed here to recover the review
band with its per signal contributions. That takes about ninety seconds, so
the export is skipped when its outputs are newer than every input. Pass
--force to rebuild anyway.

Nothing in engine/, data/ or eval/ is modified. This module imports and reads.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Runnable from anywhere, including as an npm prebuild step from web/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from engine.block.candidates import candidate_pairs, load_records, truth_labels
from engine.calibrate import isotonic
from engine.cluster import correlation
from engine.features import extract as fx
from engine.features.signals import MODEL_SIGNALS, SIGNAL_LABELS
from engine.linkage import fellegi_sunter as fs
from engine.normalise.indic import is_kannada

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "corpus"
EVAL = ROOT / "eval" / "report.json"
OUT = ROOT / "web" / "public" / "data"

MAX_REVIEW_ROWS = 300
MAX_IDENTITIES = 200
# Undetected cases carry their full BriefFacts narrative and ten candidates
# each, so the whole set is about two megabytes. The accuracy figures in this
# feed are measured over every case regardless of how many are exported.
MAX_CASES = 150

REQUIRED = [
    (EVAL, "make eval"),
    (ROOT / "eval" / "canonical.json", "make eval"),
    (CORPUS / "resolution_report.json", "make resolve"),
    (CORPUS / "downstream_report.json", "make downstream"),
    (CORPUS / "reconciliation_report.json", "make reconcile"),
    (CORPUS / "resolved_identities.csv", "make resolve"),
    (CORPUS / "blocking_report.json", "make block"),
    (CORPUS / "manifest.json", "make gen"),
    (CORPUS / "Accused.csv", "make gen"),
    (CORPUS / "CaseMaster.csv", "make gen"),
]


def die(message: str) -> None:
    raise SystemExit(f"\nEXPORT FAILED\n\n  {message}\n")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def script_of(text: str) -> str:
    kn = is_kannada(text)
    la = any(ch.isascii() and ch.isalpha() for ch in text)
    if kn and la:
        return "mixed"
    return "kannada" if kn else "latin"


def is_stale(force: bool) -> bool:
    if force:
        return True
    outputs = [OUT / n for n in ("eval.json", "routing.json", "identities.json",
                                 "network.json", "runlog.json", "cases.json",
                                 "profiles.json", "reconciliation.json",
                                 "hotspots.json")]
    if not all(p.exists() for p in outputs):
        return True
    newest_input = max(p.stat().st_mtime for p, _ in REQUIRED)
    oldest_output = min(p.stat().st_mtime for p in outputs)
    return newest_input > oldest_output


def main() -> int:
    parser = argparse.ArgumentParser(description="Export engine output for the web client.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    missing = [(p, cmd) for p, cmd in REQUIRED if not p.exists()]
    if missing:
        lines = [f"{p.relative_to(ROOT)} is missing, produced by: {cmd}"
                 for p, cmd in missing]
        die("\n  ".join(lines))

    OUT.mkdir(parents=True, exist_ok=True)

    if not is_stale(args.force):
        print("export up to date, nothing to do")
        return 0

    print("exporting engine output for the web client")

    evaluation = read_json(EVAL)
    resolution = read_json(CORPUS / "resolution_report.json")
    blocking = read_json(CORPUS / "blocking_report.json")
    manifest = read_json(CORPUS / "manifest.json")

    accused = read_csv(CORPUS / "Accused.csv")
    cases = {c["CaseMasterID"]: c for c in read_csv(CORPUS / "CaseMaster.csv")}
    units = {u["UnitID"]: u for u in read_csv(CORPUS / "Unit.csv")}
    districts = {d["DistrictID"]: d for d in read_csv(CORPUS / "District.csv")}
    subheads = {s["CrimeSubHeadID"]: s["CrimeSubHeadName"]
                for s in read_csv(CORPUS / "CrimeSubHead.csv")}
    resolved = {r["AccusedMasterID"]: r["ResolvedIdentityID"]
                for r in read_csv(CORPUS / "resolved_identities.csv")}

    # ---- recompute the scoring path -------------------------------------
    print("  recomputing the scoring path for per pair evidence")
    records = load_records(CORPUS)
    pair_a, pair_b = candidate_pairs(records)
    truth, _ = truth_labels(CORPUS, records)
    is_match = truth[pair_a] == truth[pair_b]
    features = fx.extract(records, pair_a, pair_b)
    model = fs.fit_em(features.levels)
    frequency = fx.name_frequency(records)
    u_generic = fs.generic_agreement_u(frequency)
    at_value = np.array([bool(v) for v in features.agreed_name])
    adjustment = np.where(
        at_value,
        fs.frequency_adjustment(features.agreed_name, frequency, u_generic), 0.0)
    scores = fs.score(model, features.levels) + adjustment
    contributions = fs.per_signal_contributions(model, features.levels)
    calibration = isotonic.fit(scores, is_match)
    probabilities = calibration.probability(scores)
    routes = isotonic.route(probabilities)

    amid = [r["AccusedMasterID"] for r in records.accused]
    label_of = np.array([int(resolved[a][1:]) for a in amid], dtype=np.int64)

    # Cases touched by each resolved identity, for the cannot link check.
    cases_of_identity: dict[int, set[str]] = defaultdict(set)
    for row, identity in enumerate(label_of.tolist()):
        cases_of_identity[identity].add(records.case_id[row])

    # ---- routing.json ----------------------------------------------------
    review = np.flatnonzero(routes == 1)
    review = review[np.argsort(-probabilities[review])][:MAX_REVIEW_ROWS]
    print(f"  routing, {len(review)} review band pairs of {int((routes == 1).sum())}")

    routing_rows = []
    for k in review.tolist():
        i, j = int(pair_a[k]), int(pair_b[k])
        left_id, right_id = int(label_of[i]), int(label_of[j])
        # A merge is refused when it would place two accused from one FIR into
        # one identity. Direct same case pairs never reach scoring, so the
        # conflicts that matter are transitive, discovered through the two
        # identities the rows already belong to.
        shared = cases_of_identity[left_id] & cases_of_identity[right_id]
        conflict = bool(shared) and left_id != right_id

        evidence = []
        for signal in MODEL_SIGNALS:
            weight = float(contributions[signal][k])
            if abs(weight) < 1e-9:
                continue
            evidence.append({
                "signal": signal,
                "label": SIGNAL_LABELS.get(signal, signal),
                "level": int(features.levels[signal][k]),
                "weight": round(weight, 4),
            })
        evidence.sort(key=lambda e: -abs(e["weight"]))
        if abs(float(adjustment[k])) > 1e-9:
            evidence.append({
                "signal": "frequency",
                "label": "inverse name frequency adjustment",
                "level": None,
                "weight": round(float(adjustment[k]), 4),
            })

        def side(row: int) -> dict:
            record = records.accused[row]
            case = cases[records.case_id[row]]
            return {
                "amid": record["AccusedMasterID"],
                "name": record["AccusedName"],
                "script": script_of(record["AccusedName"]),
                "person_label": record["PersonID"],
                "age": record["AgeYear"] or None,
                "case_id": records.case_id[row],
                "crime_no": case["CrimeNo"],
                "registered": case["CrimeRegisteredDate"],
                "district": districts[case["DistrictID"]]["DistrictName"],
                "station": units[case["UnitID"]]["UnitName"],
                "identity": f"R{label_of[row]:06d}",
            }

        routing_rows.append({
            "pair_id": f"P{k}",
            "left": side(i),
            "right": side(j),
            "score_llr": round(float(scores[k]), 4),
            "probability": round(float(probabilities[k]), 6),
            "route": isotonic.ROUTES[int(routes[k])],
            "evidence": evidence,
            "cannot_link_conflict": conflict,
            "conflict_reason": (
                f"Merging these would place two accused from FIR "
                f"{sorted(shared)[0]} into one identity. The schema proves they "
                f"are different people." if conflict else None),
        })

    # ---- identities.json -------------------------------------------------
    by_identity: dict[int, list[int]] = defaultdict(list)
    for row, identity in enumerate(label_of.tolist()):
        by_identity[identity].append(row)

    edge_probability: dict[tuple[int, int], list[float]] = defaultdict(list)
    for k in range(len(pair_a)):
        i, j = int(pair_a[k]), int(pair_b[k])
        if label_of[i] == label_of[j]:
            edge_probability[(int(label_of[i]), 0)].append(float(probabilities[k]))

    ranked = sorted(by_identity.items(),
                    key=lambda kv: (-len(kv[1]), kv[0]))[:MAX_IDENTITIES]
    print(f"  identities, top {len(ranked)} by record count")

    identities = []
    for identity, rows in ranked:
        variants = []
        seen = set()
        for row in rows:
            name = records.accused[row]["AccusedName"]
            if name in seen:
                continue
            seen.add(name)
            variants.append({"name": name, "script": script_of(name),
                             "amid": records.accused[row]["AccusedMasterID"]})
        implied = []
        for row in rows:
            age = records.accused[row]["AgeYear"]
            if age:
                implied.append(int(records.case_id[row] and
                                   cases[records.case_id[row]]["CrimeRegisteredDate"][:4])
                               - int(age))
        linked = []
        for row in rows:
            case = cases[records.case_id[row]]
            linked.append({
                "case_id": records.case_id[row],
                "crime_no": case["CrimeNo"],
                "registered": case["CrimeRegisteredDate"],
                "district": districts[case["DistrictID"]]["DistrictName"],
                "station": units[case["UnitID"]]["UnitName"],
                "subhead": subheads.get(case["CrimeSubHeadID"], "unknown"),
                "amid": records.accused[row]["AccusedMasterID"],
                "name": records.accused[row]["AccusedName"],
            })
        linked.sort(key=lambda c: c["registered"])
        confidence = edge_probability.get((identity, 0), [])
        circles = Counter(units[cases[records.case_id[r]]["UnitID"]]["UnitName"]
                          for r in rows)
        identities.append({
            "identity": f"R{identity:06d}",
            "record_count": len(rows),
            "case_count": len({records.case_id[r] for r in rows}),
            "source_amids": [records.accused[r]["AccusedMasterID"] for r in rows],
            "variants": variants,
            "distinct_renderings": len(variants),
            "scripts": sorted({v["script"] for v in variants}),
            "implied_birth_year": {
                "min": min(implied) if implied else None,
                "max": max(implied) if implied else None,
                "values": sorted(set(implied)),
            },
            "primary_circle": circles.most_common(1)[0][0] if circles else None,
            "circles": [{"station": s, "cases": n} for s, n in circles.most_common()],
            "cases": linked,
            "merge_confidence": {
                "mean": round(float(np.mean(confidence)), 4) if confidence else None,
                "min": round(float(np.min(confidence)), 4) if confidence else None,
                "edges": len(confidence),
            },
        })

    # ---- network.json ----------------------------------------------------
    # An edge is recovered when it would have hung off a different apparent
    # person before resolution. Each identity's anchor is the name string it
    # carries most often, which is the node a naive join would have produced.
    # An edge attaching through any other rendering was invisible until the
    # records were merged.
    anchor: dict[int, str] = {}
    for identity, rows in by_identity.items():
        counts = Counter(records.accused[r]["AccusedName"] for r in rows)
        anchor[identity] = counts.most_common(1)[0][0]

    selected = {int(entry["identity"][1:]) for entry in identities}
    rows_by_case: dict[str, list[int]] = defaultdict(list)
    for row in range(len(records)):
        rows_by_case[records.case_id[row]].append(row)

    edges: dict[tuple[int, int], dict] = {}
    for case_id, rows in rows_by_case.items():
        if len(rows) < 2:
            continue
        for x in range(len(rows)):
            for y in range(x + 1, len(rows)):
                ra, rb = rows[x], rows[y]
                ia, ib = int(label_of[ra]), int(label_of[rb])
                if ia == ib or ia not in selected or ib not in selected:
                    continue
                key = (ia, ib) if ia < ib else (ib, ia)
                through_anchor = (
                    records.accused[ra]["AccusedName"] == anchor[ia]
                    and records.accused[rb]["AccusedName"] == anchor[ib]
                )
                entry = edges.setdefault(key, {
                    "source": f"R{key[0]:06d}", "target": f"R{key[1]:06d}",
                    "cases": [], "visible_before_resolution": False,
                })
                entry["cases"].append({
                    "case_id": case_id,
                    "crime_no": cases[case_id]["CrimeNo"],
                    "registered": cases[case_id]["CrimeRegisteredDate"],
                })
                if through_anchor:
                    entry["visible_before_resolution"] = True

    network_edges = []
    for entry in edges.values():
        entry["shared_cases"] = len(entry["cases"])
        entry["recovered"] = not entry["visible_before_resolution"]
        network_edges.append(entry)
    network_edges.sort(key=lambda e: -e["shared_cases"])

    node_index = {e["identity"]: e for e in identities}
    network_nodes = []
    degree = Counter()
    for edge in network_edges:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1
    for entry in identities:
        network_nodes.append({
            "identity": entry["identity"],
            "label": entry["variants"][0]["name"] if entry["variants"] else entry["identity"],
            "record_count": entry["record_count"],
            "case_count": entry["case_count"],
            "merged": entry["record_count"] > 1,
            "degree": degree.get(entry["identity"], 0),
            "circle": entry["primary_circle"],
        })

    recovered = sum(1 for e in network_edges if e["recovered"])
    print(f"  network, {len(network_nodes)} nodes, {len(network_edges)} edges, "
          f"{recovered} recovered")

    # ---- cases.json and profiles.json, Layer 8 --------------------------
    print("  layer 8, ranking undetected cases")
    from engine.downstream import co_offender, profiles as profiles_mod, undetected
    from engine.downstream.context import load as load_resolved

    resolved_corpus = load_resolved(CORPUS)
    graph = co_offender.build(resolved_corpus)
    ranking = undetected.rank(resolved_corpus)
    ranked_cases = undetected.strip_internals(ranking)
    total_ranked = len(ranked_cases)
    # Strongest top candidate first, so the screen opens on a case where the
    # ranking has something to say rather than on an arbitrary one.
    ranked_cases.sort(key=lambda c: -(c["candidates"][0]["score"] if c["candidates"] else 0))
    ranked_cases = ranked_cases[:MAX_CASES]
    downstream = read_json(CORPUS / "downstream_report.json")

    # Labels, so the client never has to join two feeds to show a name.
    label_of: dict[str, str] = {}
    for identity, rows in resolved_corpus.rows_of_identity.items():
        counts = Counter(resolved_corpus.accused[r]["AccusedName"] for r in rows)
        label_of[identity] = counts.most_common(1)[0][0]

    for entry in ranked_cases:
        for candidate in entry["candidates"]:
            candidate["label"] = label_of.get(candidate["identity"], candidate["identity"])
            candidate["script"] = script_of(candidate["label"])

    all_profiles = profiles_mod.build(resolved_corpus, graph)
    # Repeat offenders first. A single record profile has nothing to show.
    exportable = sorted(
        all_profiles, key=lambda p: (-p["cases"], -p["records"]))[:MAX_IDENTITIES]
    for profile in exportable:
        profile["script"] = script_of(profile["label"])

    # ---- runlog.json -----------------------------------------------------
    fingerprint = hashlib.sha256(
        json.dumps({
            "seed": manifest["seed"],
            "corpus": manifest.get("generated_at"),
            "eval": evaluation.get("generated_at"),
        }, sort_keys=True).encode()
    ).hexdigest()[:12]

    route_counts = {name: int((routes == index).sum())
                    for index, name in enumerate(isotonic.ROUTES)}

    runlog = {
        "run_id": fingerprint,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": manifest["seed"],
        "corpus_generated_at": manifest.get("generated_at"),
        "co_offending_preset": manifest.get("co_offending_preset"),
        "stages": [
            {"stage": stage, "seconds": seconds}
            for stage, seconds in evaluation["latency_seconds"].items()
        ],
        "route_counts": route_counts,
        "counts": {
            "cases": manifest["counts"]["cases"],
            "accused_rows": manifest["counts"]["accused_rows"],
            "candidate_pairs": int(len(pair_a)),
            "resolved_identities": len(by_identity),
            "true_persons": manifest["counts"]["true_persons_appearing"],
        },
        "files_read": [
            str(EVAL.relative_to(ROOT)).replace("\\", "/"),
            *[str(p.relative_to(ROOT)).replace("\\", "/")
              for p, _ in REQUIRED if p != EVAL],
        ],
        "engine": {
            "linkage_method": resolution["layer4_linkage"]["method"],
            "threshold_llr": resolution["layer4_linkage"]["threshold_llr"],
            "blocking_families": blocking["blocking"]["shipped_families"],
            "collective_iterations": resolution["layer6_collective"]["iterations"],
            "collective_converged": resolution["layer6_collective"]["converged"],
        },
    }

    # ---- write -----------------------------------------------------------
    payloads = {
        "eval.json": evaluation,
        "canonical.json": read_json(ROOT / "eval" / "canonical.json"),
        "routing.json": {
            "generated_at": runlog["exported_at"],
            "review_band": {"floor": isotonic.REVIEW_FLOOR, "ceiling": isotonic.AUTO_MERGE},
            "total_in_review_band": int((routes == 1).sum()),
            "shown": len(routing_rows),
            "pairs": routing_rows,
        },
        "identities.json": {
            "generated_at": runlog["exported_at"],
            "total_identities": len(by_identity),
            "shown": len(identities),
            "identities": identities,
        },
        "network.json": {
            "generated_at": runlog["exported_at"],
            "nodes": network_nodes,
            "edges": network_edges,
            "recovered_edges": recovered,
            "pre_existing_edges": len(network_edges) - recovered,
        },
        "cases.json": {
            "generated_at": runlog["exported_at"],
            "weights": ranking["weights"],
            "spatial_horizon_km": undetected.SPATIAL_HORIZON_KM,
            "temporal_horizon_days": undetected.TEMPORAL_HORIZON_DAYS,
            "candidate_pool": len(ranking["identities"]),
            "accuracy": downstream["undetected"]["accuracy"],
            "total_undetected_cases": total_ranked,
            "shown": len(ranked_cases),
            "cases": ranked_cases,
        },
        "profiles.json": {
            "generated_at": runlog["exported_at"],
            "total_identities": len(all_profiles),
            "shown": len(exportable),
            "graph": downstream["co_offender_graph"],
            "communities": downstream["communities"],
            "summary": downstream["profiles"],
            "profiles": exportable,
        },
        "reconciliation.json": read_json(CORPUS / "reconciliation_report.json"),
        "hotspots.json": {
            "generated_at": runlog["exported_at"],
            **downstream["hotspots"],
        },
        **({"scale.json": read_json(CORPUS / "scale_report.json")}
           if (CORPUS / "scale_report.json").exists() else {}),
        **({"vocabulary.json": read_json(CORPUS / "vocabulary_report.json")}
           if (CORPUS / "vocabulary_report.json").exists() else {}),
        # The 150 question set, and the two other person bearing tables. Both
        # are optional, so a clone that has run only the core chain still
        # exports, and the screens that read them say which command is missing.
        **({"questions.json": read_json(ROOT / "eval" / "questions_report.json")}
           if (ROOT / "eval" / "questions_report.json").exists() else {}),
        **({"persons.json": read_json(CORPUS / "other_persons_report.json")}
           if (CORPUS / "other_persons_report.json").exists() else {}),
        **({"gender_noise.json": read_json(CORPUS / "gender_noise_report.json")}
           if (CORPUS / "gender_noise_report.json").exists() else {}),
        "runlog.json": runlog,
    }

    for name, payload in payloads.items():
        target = OUT / name
        target.write_text(json.dumps(payload, indent=2, default=float,
                                     ensure_ascii=False), encoding="utf-8")
        print(f"  wrote {target.relative_to(ROOT)}  "
              f"{target.stat().st_size / 1024:.1f} KB")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
