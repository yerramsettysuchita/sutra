"""Invariants the corpus must hold, checked on a small fast run.

These are correctness properties of the measuring instrument. If any of them
breaks, every number measured downstream is meaningless, so they run on a
600 case corpus in a temporary directory rather than being skipped for speed.
"""

import random
import re
import tempfile
import unittest
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from data.generator import generate as G
from data.generator import reference_data as R


class TestCorpusInvariants(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.corpus = G.build_corpus(random.Random(4471), n_cases=600)

    def test_cannot_link_holds_by_construction(self):
        """Two Accused rows on one CaseMasterID must be different people.

        Layer 5 takes this as a hard constraint. If the generator ever violated
        it, the constraint would be unsound and the clustering result would be
        measured against a corpus that contradicts its own premise.
        """
        by_case = defaultdict(list)
        for row in self.corpus["identity_map"]:
            by_case[row["CaseMasterID"]].append(row["TruePersonID"])
        for case_id, people in by_case.items():
            with self.subTest(case=case_id):
                self.assertEqual(len(people), len(set(people)))

    def test_person_labels_are_sequential_within_a_case(self):
        by_case = defaultdict(list)
        for row in self.corpus["accused"]:
            by_case[row["CaseMasterID"]].append(row["PersonID"])
        for case_id, labels in by_case.items():
            with self.subTest(case=case_id):
                self.assertEqual(sorted(labels, key=lambda x: int(x[1:])),
                                 [f"A{i}" for i in range(1, len(labels) + 1)])

    def test_crime_number_format(self):
        """1 category, 4 district, 4 station, 4 year, 5 serial."""
        pattern = re.compile(r"^\d{1}\d{4}\d{4}\d{4}\d{5}$")
        for case in self.corpus["cases"]:
            with self.subTest(crime_no=case["CrimeNo"]):
                self.assertRegex(case["CrimeNo"], pattern)
                self.assertEqual(len(case["CrimeNo"]), 18)
                self.assertEqual(int(case["CrimeNo"][0]), case["CaseCategoryID"])
                self.assertEqual(int(case["CrimeNo"][1:5]), case["DistrictID"])
                self.assertEqual(int(case["CrimeNo"][9:13]),
                                 int(case["CrimeRegisteredDate"][:4]))

    def test_crime_numbers_are_unique(self):
        numbers = [c["CrimeNo"] for c in self.corpus["cases"]]
        self.assertEqual(len(numbers), len(set(numbers)))

    def test_ipc_before_transition_bns_after(self):
        """The whole point of Layer 9 depends on this being true in the data."""
        section_act = {s["SectionID"]: s["ActID"] for s in self.corpus["sections"]}
        act_abbr = {a["ActID"]: a["ActAbbr"] for a in self.corpus["acts"]}
        case_date = {c["CaseMasterID"]: c["CrimeRegisteredDate"]
                     for c in self.corpus["cases"]}
        transition = G.TRANSITION.isoformat()
        seen_ipc = seen_bns = 0
        for link in self.corpus["act_sections"]:
            abbr = act_abbr[section_act[link["SectionID"]]]
            when = case_date[link["CaseMasterID"]]
            if abbr == "IPC":
                seen_ipc += 1
                self.assertLess(when, transition)
            elif abbr == "BNS":
                seen_bns += 1
                self.assertGreaterEqual(when, transition)
        self.assertGreater(seen_ipc, 0)
        self.assertGreater(seen_bns, 0)

    def test_every_ipc_section_has_a_bns_successor(self):
        by_id = {s["SectionID"]: s for s in self.corpus["sections"]}
        act_abbr = {a["ActID"]: a["ActAbbr"] for a in self.corpus["acts"]}
        for section in self.corpus["sections"]:
            if act_abbr[section["ActID"]] == "IPC":
                with self.subTest(section=section["SectionNo"]):
                    self.assertIsNotNone(section["SuccessorSectionID"])
                    successor = by_id[section["SuccessorSectionID"]]
                    self.assertEqual(act_abbr[successor["ActID"]], "BNS")
                    self.assertEqual(section["Active"], "N")
                    self.assertEqual(successor["Active"], "Y")

    def test_undetected_cases_carry_no_accused_rows(self):
        undetected = {u["CaseMasterID"] for u in self.corpus["undetected_truth"]}
        with_accused = {a["CaseMasterID"] for a in self.corpus["accused"]}
        self.assertFalse(undetected & with_accused)

    def test_cstype_c_matches_the_undetected_set(self):
        c_cases = {cs["CaseMasterID"] for cs in self.corpus["chargesheets"]
                   if cs["cstype"] == "C"}
        undetected = {u["CaseMasterID"] for u in self.corpus["undetected_truth"]}
        self.assertEqual(c_cases, undetected)

    def test_accused_table_has_no_identifying_columns(self):
        """The finding, asserted as a test.

        If a future change adds a father name or a phone number to Accused, the
        corpus stops representing the problem and this test says so.
        """
        forbidden = {"FatherName", "Address", "PhoneNumber", "UID", "Aadhaar",
                     "FingerprintID", "BiometricID"}
        columns = set(self.corpus["accused"][0].keys())
        self.assertFalse(columns & forbidden)

    def test_protected_columns_are_present_but_never_promoted(self):
        """Present for schema fidelity, blocked at engine/policy.py."""
        from engine.policy import ExcludedFeatureError, assert_no_excluded_features
        columns = set(self.corpus["accused"][0].keys())
        self.assertTrue({"CasteID", "ReligionID", "OccupationID"} <= columns)
        with self.assertRaises(ExcludedFeatureError):
            assert_no_excluded_features(columns, context="test")

    def test_name_collisions_are_genuinely_distinct_people(self):
        by_id = {p["TruePersonID"]: p for p in self.corpus["persons"]}
        for group in self.corpus["collisions"]:
            names = {(by_id[m]["given_la"], by_id[m]["father_la"])
                     for m in group["Members"]}
            districts = {by_id[m]["HomeDistrictID"] for m in group["Members"]}
            with self.subTest(group=group["CollisionGroup"]):
                self.assertEqual(len(names), 1, "collision group must share one name")
                self.assertEqual(len(districts), 1, "and one district")
                self.assertGreater(len(set(group["Members"])), 1)

    def test_repeat_offenders_exist_in_useful_numbers(self):
        appearances = Counter(r["TruePersonID"] for r in self.corpus["identity_map"])
        repeat = sum(1 for v in appearances.values() if v >= 2)
        self.assertGreater(repeat / len(appearances), 0.20)

    def test_cross_script_renderings_actually_occur(self):
        scripts = Counter(r["Script"] for r in self.corpus["identity_map"])
        self.assertGreater(scripts["kannada"] / len(self.corpus["identity_map"]), 0.15)
        self.assertGreater(scripts["latin"] / len(self.corpus["identity_map"]), 0.30)

    def test_dates_sit_inside_the_corpus_window(self):
        for case in self.corpus["cases"]:
            when = date.fromisoformat(case["CrimeRegisteredDate"])
            self.assertGreaterEqual(when, G.CORPUS_START)
            self.assertLessEqual(when, G.CORPUS_END)

    def test_foreign_keys_resolve(self):
        unit_ids = {u["UnitID"] for u in self.corpus["units"]}
        case_ids = {c["CaseMasterID"] for c in self.corpus["cases"]}
        accused_ids = {a["AccusedMasterID"] for a in self.corpus["accused"]}
        employee_ids = {e["EmployeeID"] for e in self.corpus["employees"]}
        section_ids = {s["SectionID"] for s in self.corpus["sections"]}

        for case in self.corpus["cases"]:
            self.assertIn(case["UnitID"], unit_ids)
            self.assertIn(case["IOEmployeeID"], employee_ids)
        for row in self.corpus["accused"]:
            self.assertIn(row["CaseMasterID"], case_ids)
        for row in self.corpus["arrests"]:
            self.assertIn(row["AccusedMasterID"], accused_ids)
            self.assertIn(row["ArrestingOfficerID"], employee_ids)
        for link in self.corpus["act_sections"]:
            self.assertIn(link["SectionID"], section_ids)
            self.assertIn(link["CaseMasterID"], case_ids)

    def test_unit_hierarchy_is_a_tree_reaching_the_root(self):
        """Layer 3d walks ParentUnit, so a cycle would hang the feature step."""
        parent = {u["UnitID"]: u["ParentUnitID"] for u in self.corpus["units"]}
        for unit_id in parent:
            seen, cursor, depth = set(), unit_id, 0
            while cursor is not None:
                self.assertNotIn(cursor, seen, "cycle in the Unit tree")
                seen.add(cursor)
                cursor = parent[cursor]
                depth += 1
                self.assertLess(depth, 12)

    def test_generation_is_reproducible(self):
        a = G.build_corpus(random.Random(4471), n_cases=120)
        b = G.build_corpus(random.Random(4471), n_cases=120)
        self.assertEqual([r["AccusedName"] for r in a["accused"]],
                         [r["AccusedName"] for r in b["accused"]])
        self.assertEqual([r["CrimeNo"] for r in a["cases"]],
                         [r["CrimeNo"] for r in b["cases"]])

    def test_writes_a_full_csv_set(self):
        expected = {
            "State.csv", "District.csv", "UnitType.csv", "Unit.csv", "Rank.csv",
            "Designation.csv", "Employee.csv", "CaseCategory.csv",
            "GravityOffence.csv", "CrimeHead.csv", "CrimeSubHead.csv", "Act.csv",
            "Section.csv", "CaseMaster.csv", "ActSectionAssociation.csv",
            "Accused.csv", "Victim.csv", "ComplainantDetails.csv",
            "ArrestSurrender.csv", "ChargesheetDetails.csv",
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            G.write_corpus(self.corpus, out)
            G.write_manifest(self.corpus, out, 600)
            written = {p.name for p in out.glob("*.csv")}
            self.assertEqual(expected, written)
            gt = {p.name for p in (out / "ground_truth").glob("*.csv")}
            self.assertEqual(gt, {"persons.csv", "identity_map.csv",
                                  "undetected_truth.csv", "name_collisions.csv",
                                  "gangs.csv",
                                  # Victim and ComplainantDetails carry the
                                  # same missing person entity, so they get an
                                  # identity map too. See ADR 024.
                                  "victim_identity_map.csv",
                                  "complainant_identity_map.csv"})


if __name__ == "__main__":
    unittest.main()
