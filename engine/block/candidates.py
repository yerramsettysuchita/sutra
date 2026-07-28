"""Candidate generation, shared by the Layer 2 report and the resolver.

`engine.block.evaluate` measures every key family combination in order to
justify the choice. This module produces only the shipped scheme, P4 plus TR,
and hands it to Layers 3 onward. Both import `load_records` so the record
construction cannot drift between the report and the pipeline.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

import numpy as np

from engine.block.keys import keys_for
from engine.normalise.indic import NormalisedName, normalise

SHIPPED_FAMILIES = ("P4", "TR")


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@dataclass
class Records:
    """Accused rows with everything the feature layers need, indexed by row."""

    accused: list[dict]
    norms: list[NormalisedName]
    case_id: list[str]
    circle: list[str]
    district: list[str]
    unit: list[str]
    cases: dict[str, dict]
    units: dict[str, dict]
    arrest_officer: list[str]  # "" when there was no arrest
    # Recorded gender per row, "" when the field is blank. Read as a feature
    # by Layer 3g. See engine/features/signals.py gender_level.
    gender: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.accused)


def load_records(corpus_dir: Path) -> Records:
    accused = read_csv(corpus_dir / "Accused.csv")
    cases = {c["CaseMasterID"]: c for c in read_csv(corpus_dir / "CaseMaster.csv")}
    units = {u["UnitID"]: u for u in read_csv(corpus_dir / "Unit.csv")}

    officer_by_accused: dict[str, str] = {}
    for row in read_csv(corpus_dir / "ArrestSurrender.csv"):
        officer_by_accused[row["AccusedMasterID"]] = row["ArrestingOfficerID"]

    norms, case_id, circle, district, unit, officer = [], [], [], [], [], []
    gender = []
    for row in accused:
        case = cases[row["CaseMasterID"]]
        station = units[case["UnitID"]]
        norms.append(normalise(row["AccusedName"]))
        case_id.append(row["CaseMasterID"])
        unit.append(case["UnitID"])
        district.append(case["DistrictID"])
        circle.append(station["ParentUnitID"] or station["UnitID"])
        officer.append(officer_by_accused.get(row["AccusedMasterID"], ""))
        gender.append((row.get("GenderID") or "").strip())

    return Records(
        accused=accused, norms=norms, case_id=case_id, circle=circle,
        district=district, unit=unit, cases=cases, units=units,
        arrest_officer=officer, gender=gender,
    )


def candidate_pairs(
    records: Records, families: tuple[str, ...] = SHIPPED_FAMILIES
) -> tuple[np.ndarray, np.ndarray]:
    """Candidate pairs under the shipped blocking scheme.

    Returns two parallel int32 arrays holding the lower and higher row index of
    each pair, sorted and unique.

    Pairs on one FIR are dropped. Two Accused rows sharing a CaseMasterID are
    provably different people, so scoring them is wasted work and Layer 5 would
    reject the merge anyway. The constraint comes from the schema rather than
    from a threshold, which is what makes it free to apply here.
    """
    blocks: dict[str, list[int]] = {}
    for i, norm in enumerate(records.norms):
        keys = keys_for(norm, records.circle[i])
        for family in families:
            for key in keys[family]:
                blocks.setdefault(key, []).append(i)

    n = len(records)
    packed: set[int] = set()
    for members in blocks.values():
        if len(members) < 2:
            continue
        members.sort()
        for a, b in combinations(members, 2):
            packed.add(a * n + b)

    if not packed:
        return np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32)

    flat = np.fromiter(packed, dtype=np.int64, count=len(packed))
    flat.sort()
    pair_a = (flat // n).astype(np.int32)
    pair_b = (flat % n).astype(np.int32)

    case_index = {cid: k for k, cid in enumerate(dict.fromkeys(records.case_id))}
    case_of = np.array([case_index[c] for c in records.case_id], dtype=np.int32)
    keep = case_of[pair_a] != case_of[pair_b]
    return pair_a[keep], pair_b[keep]


def truth_labels(corpus_dir: Path, records: Records) -> tuple[np.ndarray, dict[str, int]]:
    """Ground truth person id per accused row, as integer codes.

    Read only by evaluation. No layer of the engine may call this.
    """
    identity = read_csv(corpus_dir / "ground_truth" / "identity_map.csv")
    by_accused = {r["AccusedMasterID"]: r["TruePersonID"] for r in identity}
    codes: dict[str, int] = {}
    out = np.empty(len(records), dtype=np.int32)
    for i, row in enumerate(records.accused):
        person = by_accused[row["AccusedMasterID"]]
        out[i] = codes.setdefault(person, len(codes))
    return out, codes
