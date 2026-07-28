"""Golden file tests for the benchmark scorer.

The scorer reproducing SUTRA's numbers from an independent code path is the
strongest reproducibility claim this project makes, and until now it was
unasserted. A stray null byte once collapsed the separator in its pair key and
only inspection caught it, which is not a process.

Every expected value below is worked out by hand in the docstring of the test
that asserts it, so a reader can check the arithmetic without running anything.
"""

import csv
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORE = ROOT / "benchmark" / "score.py"


def load_scorer():
    spec = importlib.util.spec_from_file_location("ierbp_score", SCORE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, header, rows):
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


class TestPairArithmetic(unittest.TestCase):

    def setUp(self):
        self.scorer = load_scorer()

    def test_pair_count(self):
        # Three in one cluster is 3 pairs, two in another is 1, total 4.
        self.assertEqual(self.scorer.pair_count(["a", "a", "a", "b", "b"]), 4)
        self.assertEqual(self.scorer.pair_count(["a", "b", "c"]), 0)
        self.assertEqual(self.scorer.pair_count([]), 0)

    def test_f_beta_weights_precision_at_half(self):
        # With precision 1.0 and recall 0.5, F1 is 0.6667 and F0.5 is 0.8333,
        # because beta below one pulls the score toward precision.
        self.assertAlmostEqual(self.scorer.f_beta(1.0, 0.5, 1.0), 2 / 3, places=6)
        self.assertAlmostEqual(self.scorer.f_beta(1.0, 0.5, 0.5), 5 / 6, places=6)
        # Symmetric case, both measures agree.
        self.assertAlmostEqual(self.scorer.f_beta(0.5, 0.5, 1.0), 0.5, places=6)
        self.assertAlmostEqual(self.scorer.f_beta(0.5, 0.5, 0.5), 0.5, places=6)

    def test_f_beta_is_zero_when_either_is_zero(self):
        self.assertEqual(self.scorer.f_beta(0.0, 0.9, 0.5), 0.0)
        self.assertEqual(self.scorer.f_beta(0.9, 0.0, 0.5), 0.0)

    def test_labels_cannot_collide_across_the_separator(self):
        """Regression. A null byte once ate the separator in the pair key.

        Without a separator, predicted "B1" with gold "P23" and predicted
        "B12" with gold "P3" both concatenate to "B1P23" and "B12P3", and a
        crafted pair collides. The separator is what keeps the cross product
        injective.
        """
        source = SCORE.read_text(encoding="utf-8")
        self.assertIn('p + "\\t" + g', source,
                      "the pair key must join with an explicit separator")
        self.assertNotIn("\x00", source, "null byte in the scorer")


class TestGoldenFixture(unittest.TestCase):
    """A six row fixture whose every figure is worked out by hand.

    Gold partition, six rows:
        r1 r2 r3  are person P1
        r4 r5     are person P2
        r6        is  person P3

    Gold pairs: P1 gives 3, P2 gives 1, P3 gives 0. Total 4.

    Submission:
        r1 r2 r3 r4  in cluster A
        r5 r6        in cluster B

    Predicted pairs: A gives 6, B gives 1. Total 7.

    True positives are predicted pairs that are also gold pairs. Inside A the
    three P1 pairs qualify and the three pairs joining r4 to r1, r2, r3 do not.
    Inside B, r5 and r6 are different people. So TP is 3.

    precision 3/7 = 0.428571
    recall    3/4 = 0.75
    F1        2 * 0.428571 * 0.75 / (0.428571 + 0.75) = 0.545455
    F0.5      1.25 * 0.428571 * 0.75 / (0.25 * 0.428571 + 0.75) = 0.468750
    """

    GOLD = [("r1", "P1"), ("r2", "P1"), ("r3", "P1"),
            ("r4", "P2"), ("r5", "P2"), ("r6", "P3")]
    SUBMISSION = [("r1", "A"), ("r2", "A"), ("r3", "A"),
                  ("r4", "A"), ("r5", "B"), ("r6", "B")]

    def setUp(self):
        self.scorer = load_scorer()
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.gold_path = base / "identities.csv"
        self.sub_path = base / "submission.csv"
        write_csv(self.gold_path, ["AccusedMasterID", "GoldPersonID"], self.GOLD)
        write_csv(self.sub_path, ["AccusedMasterID", "PredictedPersonID"],
                  self.SUBMISSION)

    def tearDown(self):
        self.tmp.cleanup()

    def _metrics(self):
        gold = self.scorer.read_two_column(self.gold_path)
        pred = self.scorer.read_two_column(self.sub_path)
        ids = sorted(gold)
        gold_labels = [gold[i] for i in ids]
        pred_labels = [pred[i] for i in ids]
        combined = [p + "\t" + g for p, g in zip(pred_labels, gold_labels)]
        actual = self.scorer.pair_count(gold_labels)
        proposed = self.scorer.pair_count(pred_labels)
        tp = self.scorer.pair_count(combined)
        precision = tp / proposed
        recall = tp / actual
        return actual, proposed, tp, precision, recall

    def test_pair_counts_are_exact(self):
        actual, proposed, tp, _, _ = self._metrics()
        self.assertEqual(actual, 4)
        self.assertEqual(proposed, 7)
        self.assertEqual(tp, 3)

    def test_precision_recall_f1_f05_are_exact(self):
        _, _, _, precision, recall = self._metrics()
        self.assertAlmostEqual(precision, 3 / 7, places=6)
        self.assertAlmostEqual(recall, 0.75, places=6)
        self.assertAlmostEqual(
            self.scorer.f_beta(precision, recall, 1.0), 0.5454545, places=6)
        self.assertAlmostEqual(
            self.scorer.f_beta(precision, recall, 0.5), 0.4687500, places=6)

    def test_cluster_labels_are_arbitrary(self):
        """Renaming every cluster must not change a single figure."""
        renamed = [(row, f"zzz_{label}") for row, label in self.SUBMISSION]
        write_csv(self.sub_path, ["AccusedMasterID", "PredictedPersonID"], renamed)
        _, _, tp, precision, recall = self._metrics()
        self.assertEqual(tp, 3)
        self.assertAlmostEqual(precision, 3 / 7, places=6)
        self.assertAlmostEqual(recall, 0.75, places=6)

    def test_perfect_and_degenerate_submissions(self):
        perfect = [(row, label) for row, label in self.GOLD]
        write_csv(self.sub_path, ["AccusedMasterID", "PredictedPersonID"], perfect)
        _, proposed, tp, precision, recall = self._metrics()
        self.assertEqual((proposed, tp), (4, 4))
        self.assertEqual((precision, recall), (1.0, 1.0))

        # Everything in one cluster. Recall is perfect, precision is not, which
        # is why recall alone is never a result.
        collapsed = [(row, "ONE") for row, _ in self.GOLD]
        write_csv(self.sub_path, ["AccusedMasterID", "PredictedPersonID"], collapsed)
        _, proposed, tp, precision, recall = self._metrics()
        self.assertEqual(proposed, 15)          # 6 choose 2
        self.assertEqual(tp, 4)
        self.assertEqual(recall, 1.0)
        self.assertAlmostEqual(precision, 4 / 15, places=6)

    def test_missing_row_is_rejected(self):
        short = self.SUBMISSION[:-1]
        write_csv(self.sub_path, ["AccusedMasterID", "PredictedPersonID"], short)
        result = subprocess.run(
            [sys.executable, str(SCORE), str(self.sub_path),
             "--gold", str(self.gold_path)],
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing", (result.stderr + result.stdout).lower())

    def test_end_to_end_through_the_command_line(self):
        result = subprocess.run(
            [sys.executable, str(SCORE), str(self.sub_path),
             "--gold", str(self.gold_path)],
            capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0.4286", result.stdout)   # precision
        self.assertIn("0.7500", result.stdout)   # recall
        self.assertIn("0.5455", result.stdout)   # F1
        self.assertIn("0.4688", result.stdout)   # F0.5


if __name__ == "__main__":
    unittest.main()
