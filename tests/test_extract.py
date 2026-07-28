"""Layer 3, the feature extractor.

An audit found this module had no tests. It computes every feature the model
consumes, which makes it the single highest consequence untested file in the
repository. `test_engine_layers.py` tests the level functions in isolation;
nothing tested the code that runs them over the candidate set and assembles the
FeatureSet.

The tests build a tiny corpus in a temp directory rather than mocking, because
the extractor reads cases, units and briefs together and a mock of that shape
would be a second implementation of the thing under test.
"""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

from engine.block.candidates import Records, candidate_pairs, load_records
from engine.features import extract as fx
from engine.features import signals as S
from engine.normalise.indic import normalise


def write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


class TinyCorpus:
    """Four accused rows over three cases, with known relationships.

    Rows 0 and 1 are the same man in two districts, written two ways, same
    gender. Row 2 is a woman with a similar name, which is the pair the gender
    channel must reject. Row 3 shares case 3 with nobody.
    """

    def __init__(self, directory: Path):
        self.dir = directory
        write(directory / "Accused.csv", [
            {"AccusedMasterID": "1", "CaseMasterID": "1", "PersonID": "A1",
             "AccusedName": "Suresh Mallappa", "AgeYear": "30", "GenderID": "1"},
            {"AccusedMasterID": "2", "CaseMasterID": "2", "PersonID": "A1",
             "AccusedName": "Suresha Mallappa", "AgeYear": "31", "GenderID": "1"},
            {"AccusedMasterID": "3", "CaseMasterID": "3", "PersonID": "A1",
             "AccusedName": "Suresha Mallappa", "AgeYear": "31", "GenderID": "2"},
            {"AccusedMasterID": "4", "CaseMasterID": "3", "PersonID": "A2",
             "AccusedName": "Ramesh Gowda", "AgeYear": "44", "GenderID": ""},
        ], ["AccusedMasterID", "CaseMasterID", "PersonID", "AccusedName",
            "AgeYear", "GenderID"])

        write(directory / "CaseMaster.csv", [
            {"CaseMasterID": str(i), "UnitID": "1" if i < 3 else "2",
             "DistrictID": "1" if i < 3 else "2",
             "CrimeRegisteredDate": f"202{i}-01-01",
             "Latitude": "12.97", "Longitude": "77.59",
             "BriefFacts": "mobile phone snatched near the bus stand"}
            for i in (1, 2, 3)
        ], ["CaseMasterID", "UnitID", "DistrictID", "CrimeRegisteredDate",
            "Latitude", "Longitude", "BriefFacts"])

        write(directory / "Unit.csv", [
            {"UnitID": "1", "UnitTypeID": "4", "DistrictID": "1",
             "ParentUnitID": "", "UnitName": "Station A"},
            {"UnitID": "2", "UnitTypeID": "4", "DistrictID": "2",
             "ParentUnitID": "", "UnitName": "Station B"},
        ], ["UnitID", "UnitTypeID", "DistrictID", "ParentUnitID", "UnitName"])

        write(directory / "ArrestSurrender.csv", [
            {"ArrestSurrenderID": "1", "CaseMasterID": "1",
             "AccusedMasterID": "1", "ArrestingOfficerID": "77"},
        ], ["ArrestSurrenderID", "CaseMasterID", "AccusedMasterID",
            "ArrestingOfficerID"])


class TestExtract(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="sutra-extract-")
        TinyCorpus(Path(cls.tmp))
        cls.records = load_records(Path(cls.tmp))
        cls.pair_a, cls.pair_b = candidate_pairs(cls.records)
        cls.features = fx.extract(cls.records, cls.pair_a, cls.pair_b)

    def test_the_loader_reads_gender(self):
        """It was ignored for the whole project. It must not be dropped again."""
        self.assertEqual(self.records.gender, ["1", "1", "2", ""])

    def test_every_modelled_signal_is_present(self):
        for signal in S.MODEL_SIGNALS:
            with self.subTest(signal=signal):
                self.assertIn(signal, self.features.levels)
                self.assertEqual(len(self.features.levels[signal]),
                                 len(self.pair_a))

    def test_levels_stay_inside_their_declared_range(self):
        """A level outside its range indexes past the fitted weight array."""
        for signal, levels in self.features.levels.items():
            with self.subTest(signal=signal):
                self.assertGreaterEqual(int(levels.min()), S.NOT_COMPUTABLE)
                self.assertLess(int(levels.max()), S.LEVELS[signal])

    def test_no_pair_shares_a_case(self):
        """Two accused on one FIR are provably different people, ADR 004."""
        case = self.records.case_id
        for i, j in zip(self.pair_a, self.pair_b):
            with self.subTest(pair=(int(i), int(j))):
                self.assertNotEqual(case[i], case[j])

    def test_gender_disagreement_is_scored_as_disagreement(self):
        """Rows 1 and 2 are a similar name and different recorded gender."""
        found = False
        for k, (i, j) in enumerate(zip(self.pair_a, self.pair_b)):
            if {int(i), int(j)} == {1, 2}:
                found = True
                self.assertEqual(int(self.features.levels["gender"][k]), 0)
        if not found:
            self.skipTest("blocking did not propose that pair on this fixture")

    def test_a_blank_gender_is_not_a_disagreement(self):
        """Row 3 has no recorded gender. Absence is never evidence, ADR 020."""
        for k, (i, j) in enumerate(zip(self.pair_a, self.pair_b)):
            if 3 in (int(i), int(j)):
                with self.subTest(pair=(int(i), int(j))):
                    self.assertEqual(int(self.features.levels["gender"][k]),
                                     S.NOT_COMPUTABLE)

    def test_agreed_name_is_only_set_at_full_agreement(self):
        """The frequency adjustment keys off this and must not fire loosely."""
        for k, value in enumerate(self.features.agreed_name):
            if value:
                with self.subTest(pair=k):
                    self.assertEqual(int(self.features.levels["name"][k]), 5)

    def test_temporal_is_not_computable_when_age_is_missing(self):
        records = Records(
            accused=[{"AccusedMasterID": "1", "CaseMasterID": "1",
                      "AccusedName": "A B", "AgeYear": ""},
                     {"AccusedMasterID": "2", "CaseMasterID": "2",
                      "AccusedName": "A B", "AgeYear": "30"}],
            norms=[normalise("A B"), normalise("A B")],
            case_id=["1", "2"], circle=["1", "1"], district=["1", "1"],
            unit=["1", "1"], cases=self.records.cases, units=self.records.units,
            arrest_officer=["", ""], gender=["1", "1"])
        a = np.array([0], dtype=np.int32)
        b = np.array([1], dtype=np.int32)
        features = fx.extract(records, a, b)
        self.assertEqual(int(features.levels["temporal"][0]), S.NOT_COMPUTABLE)

    def test_scores_and_levels_agree_in_length(self):
        for signal in self.features.levels:
            with self.subTest(signal=signal):
                self.assertEqual(len(self.features.scores[signal]),
                                 len(self.features.levels[signal]))

    def test_name_frequency_sums_to_one(self):
        frequency = fx.name_frequency(self.records)
        self.assertAlmostEqual(sum(frequency.values()), 1.0, places=9)


class TestCandidateGeneration(unittest.TestCase):
    """Layer 2. Also had no direct tests."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="sutra-block-")
        TinyCorpus(Path(cls.tmp))
        cls.records = load_records(Path(cls.tmp))

    def test_pairs_are_ordered_and_unique(self):
        a, b = candidate_pairs(self.records)
        packed = list(zip(a.tolist(), b.tolist()))
        self.assertEqual(len(set(packed)), len(packed), "duplicate pair")
        for i, j in packed:
            self.assertLess(i, j, "pair is not in ascending row order")

    def test_no_pair_indexes_outside_the_record_set(self):
        a, b = candidate_pairs(self.records)
        n = len(self.records)
        if len(a):
            self.assertLess(int(max(a.max(), b.max())), n)
            self.assertGreaterEqual(int(min(a.min(), b.min())), 0)

    def test_an_empty_corpus_returns_empty_arrays_rather_than_raising(self):
        empty = Records(accused=[], norms=[], case_id=[], circle=[],
                        district=[], unit=[], cases={}, units={},
                        arrest_officer=[], gender=[])
        a, b = candidate_pairs(empty)
        self.assertEqual(len(a), 0)
        self.assertEqual(len(b), 0)


if __name__ == "__main__":
    unittest.main()
