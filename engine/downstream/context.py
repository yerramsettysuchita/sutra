"""Shared loading for Layer 8.

Every downstream product works from the same three things: the corpus, the
resolved identity assignment written by Layer 5, and the case metadata. This
module loads them once so the four products cannot drift apart.

Ground truth is loaded separately and only by the measurement functions. No
product reads it.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@dataclass
class ResolvedCorpus:
    accused: list[dict]
    cases: dict[str, dict]
    units: dict[str, dict]
    districts: dict[str, dict]
    subheads: dict[str, str]
    identity_of: dict[str, str]          # AccusedMasterID -> ResolvedIdentityID
    rows_of_identity: dict[str, list[int]] = field(default_factory=dict)
    case_of_row: list[str] = field(default_factory=list)
    identity_of_row: list[str] = field(default_factory=list)
    undetected: list[dict] = field(default_factory=list)

    def case_date(self, case_id: str) -> date:
        return date.fromisoformat(self.cases[case_id]["CrimeRegisteredDate"])

    def circle_of(self, case_id: str) -> str:
        station = self.units[self.cases[case_id]["UnitID"]]
        return station.get("ParentUnitID") or station["UnitID"]

    def station_name(self, case_id: str) -> str:
        return self.units[self.cases[case_id]["UnitID"]]["UnitName"]

    def district_name(self, case_id: str) -> str:
        return self.districts[self.cases[case_id]["DistrictID"]]["DistrictName"]


def load(corpus_dir: Path) -> ResolvedCorpus:
    resolved_path = corpus_dir / "resolved_identities.csv"
    if not resolved_path.exists():
        raise SystemExit(
            f"{resolved_path} is missing. Layer 8 works on resolved identities, "
            f"so run: make resolve")

    accused = read_csv(corpus_dir / "Accused.csv")
    cases = {c["CaseMasterID"]: c for c in read_csv(corpus_dir / "CaseMaster.csv")}
    units = {u["UnitID"]: u for u in read_csv(corpus_dir / "Unit.csv")}
    districts = {d["DistrictID"]: d for d in read_csv(corpus_dir / "District.csv")}
    subheads = {s["CrimeSubHeadID"]: s["CrimeSubHeadName"]
                for s in read_csv(corpus_dir / "CrimeSubHead.csv")}
    identity_of = {r["AccusedMasterID"]: r["ResolvedIdentityID"]
                   for r in read_csv(resolved_path)}

    # Cases closed as true but undetected. These carry no Accused rows, which
    # is exactly why they need a candidate ranking.
    undetected = [c for c in read_csv(corpus_dir / "ChargesheetDetails.csv")
                  if c["cstype"] == "C"]

    rows_of_identity: dict[str, list[int]] = defaultdict(list)
    case_of_row: list[str] = []
    identity_of_row: list[str] = []
    for row, record in enumerate(accused):
        identity = identity_of[record["AccusedMasterID"]]
        rows_of_identity[identity].append(row)
        case_of_row.append(record["CaseMasterID"])
        identity_of_row.append(identity)

    return ResolvedCorpus(
        accused=accused, cases=cases, units=units, districts=districts,
        subheads=subheads, identity_of=identity_of,
        rows_of_identity=dict(rows_of_identity), case_of_row=case_of_row,
        identity_of_row=identity_of_row, undetected=undetected,
    )


def load_ground_truth(corpus_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """AccusedMasterID to TruePersonID, and undetected CaseMasterID to culprit.

    Read only by the measurement functions in undetected.py. No product in
    Layer 8 may call this.
    """
    gt = corpus_dir / "ground_truth"
    identity_map = {r["AccusedMasterID"]: r["TruePersonID"]
                    for r in read_csv(gt / "identity_map.csv")}
    culprits = {r["CaseMasterID"]: r["TruePersonID"]
                for r in read_csv(gt / "undetected_truth.csv")}
    return identity_map, culprits
