"""Tests for the investigator question set.

The headline claim from this artefact is a single number: how many of the 150
questions cannot be answered on the KSP schema as supplied. That number is
derived from a hand written YAML file, and a hand written file with one
mislabelled row produces a headline that is quietly wrong.

So the invariant that makes the count trustworthy is tested directly: a
question is marked as needing the person key if and only if its gold SQL reads
one of the resolved tables. Nothing else can be asserted about SQL without a
database, and pretending otherwise would be theatre.
"""

import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "eval" / "gold" / "questions.yaml"

_spec = importlib.util.spec_from_file_location(
    "eval_questions", ROOT / "eval" / "questions.py")
questions_module = importlib.util.module_from_spec(_spec)
sys.modules["eval_questions"] = questions_module


def load_module():
    """Imported lazily so the suite skips cleanly when PyYAML is absent."""
    _spec.loader.exec_module(questions_module)
    return questions_module


class TestQuestionSet(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not GOLD.exists():
            raise unittest.SkipTest("eval/gold/questions.yaml not present")
        try:
            import yaml  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("PyYAML not installed, pip install -r requirements.txt")
        cls.module = load_module()
        cls.doc = cls.module.load()
        cls.questions = cls.doc["questions"]

    def test_the_set_validates(self):
        """The module's own checks, run as a test rather than only at build."""
        self.assertEqual(self.module.check(self.questions), [])

    def test_there_are_exactly_150(self):
        self.assertEqual(len(self.questions), 150)
        self.assertEqual(self.doc["meta"]["total"], 150)

    def test_ids_are_unique_and_sequential(self):
        ids = [q["id"] for q in self.questions]
        self.assertEqual(len(set(ids)), len(ids))
        self.assertEqual(ids[0], "Q001")
        self.assertEqual(ids[-1], "Q150")

    def test_person_key_flag_matches_the_sql(self):
        """The invariant the headline count rests on.

        If a question claims to need the resolved table and does not read it,
        or reads it and does not claim to, the headline is wrong by one.
        """
        for q in self.questions:
            with self.subTest(id=q["id"]):
                self.assertEqual(
                    q["requires_person_key"],
                    self.module.uses_resolved(q["sql"]),
                    f"{q['id']} disagrees with its own SQL")

    def test_no_gold_sql_reads_a_protected_column(self):
        """The policy guard applied to the questions we ship as exemplary.

        A gold query is a worked example. One that selected on caste would
        teach exactly the thing docs/ethics.md refuses.
        """
        for q in self.questions:
            for column in ("CasteID", "ReligionID", "OccupationID"):
                with self.subTest(id=q["id"], column=column):
                    self.assertIsNone(
                        re.search(rf"\b{column}\b", q["sql"]),
                        f"{q['id']} reads {column}")

    def test_every_shape_has_more_than_one_question(self):
        """A shape with one question is a category, not a pattern."""
        counts: dict[str, int] = {}
        for q in self.questions:
            counts[q["shape"]] = counts.get(q["shape"], 0) + 1
        for shape, n in counts.items():
            with self.subTest(shape=shape):
                self.assertGreater(n, 1)

    def test_kannada_questions_are_actually_kannada(self):
        kannada = re.compile(r"[ಀ-೿]")
        for q in self.questions:
            if not q.get("question_kn"):
                continue
            with self.subTest(id=q["id"]):
                self.assertRegex(q["question_kn"], kannada)

    def test_the_bands_partition_the_set(self):
        """Every question is in exactly one coverage band."""
        bands = [self.module.band(q) for q in self.questions]
        self.assertEqual(len(bands), len(self.questions))
        self.assertEqual(
            set(bands) - {"answerable_today", "needs_language_layer",
                          "impossible_on_raw_schema"},
            set())

    def test_answerable_today_never_claims_the_impossible_band(self):
        for q in self.questions:
            if q["answerable_today"]:
                with self.subTest(id=q["id"]):
                    self.assertNotEqual(
                        self.module.band(q), "impossible_on_raw_schema")

    def test_no_question_carries_an_accuracy(self):
        """Coverage is measured. Accuracy is not, and must not creep back in.

        The deck's 74 per cent is quoted in the file header, in the sentence
        that refuses it, so the presence of the string is not the test. The
        test is that no question and no report field carries a correctness
        figure, because there is nothing to measure one with.
        """
        forbidden = {"correct", "accuracy", "score", "graded", "passed"}
        for q in self.questions:
            with self.subTest(id=q["id"]):
                self.assertEqual(set(q.keys()) & forbidden, set())

    def test_the_report_records_accuracy_as_not_measured(self):
        report = ROOT / "eval" / "questions_report.json"
        if not report.exists():
            self.skipTest("run: make questions")
        import json
        payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(payload["accuracy"]["status"], "not measured")
        self.assertNotIn("74", payload["accuracy"]["status"])


if __name__ == "__main__":
    unittest.main()
