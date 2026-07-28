"""Does a clone with no corpus reproduce the headline.

Every other test in this suite runs against artefacts that are already on disk.
That checks the numbers are consistent with each other. It does not check they
can be produced again, and a result that cannot be produced again is a claim
rather than a measurement.

So this copies the source tree into a temporary directory with no corpus, no
reports and no exports, runs the chain from empty, and asserts the headline
comes back byte for byte identical to `eval/canonical.json`.

It takes about four minutes, so it does not run by default.

    SUTRA_COLD_CLONE=1 python -m unittest tests.test_cold_clone -v

On a machine with GNU make it runs `make all` and `make eval` exactly as an
evaluator would. Where make is absent, which includes the authoring machine, it
parses those two recipes out of the Makefile and runs the same command lines
directly, so the Makefile is still the thing under test rather than a
reimplementation of it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = "5000"
CO = "moderate"
CORPUS = "data/corpus"

# What a fresh clone carries. Everything else is an output and must be rebuilt,
# because handing the run its own previous answers would prove nothing.
COPY = ["data/generator", "data/schema", "engine", "eval", "scripts", "tests",
        "benchmark", "web/src/screens", "Makefile", "requirements.txt"]

# Outputs that must not travel with the source.
EXCLUDE_NAMES = {"__pycache__", "corpus", "work", "vocab_work"}
EXCLUDE_SUFFIXES = {".json", ".csv"}


def ignore(directory, names):
    dropped = set()
    for name in names:
        if name in EXCLUDE_NAMES:
            dropped.add(name)
        elif Path(name).suffix in EXCLUDE_SUFFIXES:
            dropped.add(name)
    return dropped


def have_make() -> bool:
    return shutil.which("make") is not None


def recipe(target: str) -> list[str]:
    """The command lines of one Makefile target, with variables expanded."""
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    body = re.search(rf"^{target}:\n((?:\t.*\n)+)", text, re.M)
    if not body:
        raise AssertionError(f"the Makefile has no {target} target")
    lines = []
    for line in body.group(1).splitlines():
        line = line.lstrip("\t").lstrip("@-")
        line = (line.replace("$(PYTHON)", sys.executable)
                    .replace("$(CORPUS)", CORPUS)
                    .replace("$(CASES)", CASES)
                    .replace("$(CO)", CO))
        lines.append(line)
    return lines


class TestColdClone(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if os.environ.get("SUTRA_COLD_CLONE") != "1":
            raise unittest.SkipTest(
                "slow, about four minutes. Run with SUTRA_COLD_CLONE=1")
        canonical = ROOT / "eval" / "canonical.json"
        if not canonical.exists():
            raise unittest.SkipTest("no eval/canonical.json to compare against")
        cls.expected = json.loads(canonical.read_text(encoding="utf-8"))

        cls.tmp = tempfile.mkdtemp(prefix="sutra-cold-")
        clone = Path(cls.tmp) / "sutra"
        clone.mkdir()
        for item in COPY:
            source = ROOT / item
            target = clone / item
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, ignore=ignore)
            else:
                shutil.copy2(source, target)
        cls.clone = clone

        env = dict(os.environ, PYTHONPATH=str(clone), PYTHONIOENCODING="utf-8")
        cls.log: list[str] = []
        for target in ("all", "eval"):
            if have_make():
                commands = [f"make {target} PYTHON={sys.executable} "
                            f"CASES={CASES} CO={CO}"]
            else:
                commands = recipe(target)
            for command in commands:
                cls.log.append(command)
                result = subprocess.run(command, cwd=clone, env=env, shell=True,
                                        capture_output=True, text=True)
                if result.returncode != 0:
                    raise AssertionError(
                        f"cold clone failed on: {command}\n"
                        f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}")

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "tmp", None):
            shutil.rmtree(cls.tmp, ignore_errors=True)

    def rebuilt(self, name: str):
        path = self.clone / "eval" / name
        self.assertTrue(path.exists(), f"the cold run did not write eval/{name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_the_headline_reproduces_exactly(self):
        """Same seed, same corpus, same chain, so the same figures or a bug."""
        got = self.rebuilt("canonical.json")["headline"]
        want = self.expected["headline"]
        for key in ("precision", "recall", "f1", "f_beta_0_5",
                    "false_merge_rate"):
            with self.subTest(metric=key):
                self.assertEqual(
                    got[key], want[key],
                    f"{key} came back {got[key]} from a cold clone, "
                    f"the repository publishes {want[key]}")

    def test_the_definition_reproduces(self):
        got = self.rebuilt("canonical.json")["definition"]
        want = self.expected["definition"]
        for key in ("corpus", "cases", "accused_rows", "seed",
                    "operating_point", "threshold_llr"):
            if key not in want:
                continue
            with self.subTest(key=key):
                self.assertEqual(got.get(key), want[key])

    def test_make_all_regenerates_the_published_documents(self):
        """The README claims it is written by the run. It must actually be.

        An audit found `build_readme.py` and `build_status_md.py` were not in
        the Makefile, while README.md said every figure in it came from that
        run. A cold clone therefore shipped whatever README happened to be
        committed. This asserts the chain writes them.
        """
        for name in ("README.md", "docs/build-status.md",
                     "benchmark/leaderboard.md"):
            path = self.clone / name
            with self.subTest(document=name):
                self.assertTrue(path.exists(),
                                f"{name} was not written by make all")

    def test_the_headline_reaches_the_readme(self):
        readme = self.clone / "README.md"
        if not readme.exists():
            self.skipTest("README not regenerated")
        text = readme.read_text(encoding="utf-8")
        self.assertIn(f"{self.expected['headline']['f1']:.4f}", text)

    def test_the_gold_sql_was_validated_by_the_run(self):
        """make all must execute the 150 queries, not merely ship them."""
        report = self.clone / "eval" / "sql_validation.json"
        if not report.exists():
            self.skipTest("validation report not produced")
        payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(payload["fail_to_execute"], 0)
        self.assertEqual(payload["requires_person_key_contradicted"], 0)

    def test_the_run_used_the_makefile(self):
        """If this ever runs zero commands it would pass while proving nothing."""
        self.assertGreaterEqual(len(self.log), 2)
        self.assertTrue(any("eval.report" in c or "make eval" in c
                            for c in self.log))


if __name__ == "__main__":
    unittest.main()
