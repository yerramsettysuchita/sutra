"""Tests for the artefacts a reviewer actually reads.

The engine has 87 tests. Until now nothing tested the JSON the screens render,
the encoding of the source files, or whether a figure on a screen agrees with
the canonical headline. Those are the artefacts that carry the claim.

Every test here skips cleanly when its input has not been generated, so a
fresh clone that has not run `make all` still passes the suite rather than
failing on absence.
"""

import importlib.util
import json
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# scripts/ is not a package, so the encoding guard is loaded by path. Both the
# test suite and `make check` then run one implementation of the rule.
_spec = importlib.util.spec_from_file_location(
    "check_encoding", ROOT / "scripts" / "check_encoding.py")
check_encoding = importlib.util.module_from_spec(_spec)
sys.modules["check_encoding"] = check_encoding
_spec.loader.exec_module(check_encoding)

DATA = ROOT / "web" / "public" / "data"
CANONICAL = ROOT / "eval" / "canonical.json"

# Strings that mean a value was never filled in.
PLACEHOLDERS = {"", "tbd", "todo", "n/a", "na", "none", "null", "xxx",
                "placeholder", "fixme", "lorem ipsum"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def walk(value, path="$"):
    """Every leaf in a JSON document, with its path."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from walk(item, f"{path}[{i}]")
    else:
        yield path, value


class TestExportSchemas(unittest.TestCase):
    """Required keys, types, and no null, NaN or placeholder anywhere."""

    # feed -> required top level keys
    REQUIRED = {
        "canonical.json": ["headline", "definition", "how_to_read", "qualifiers"],
        "questions.json": ["total_questions", "headline", "coverage",
                           "accuracy", "by_shape", "questions"],
        "persons.json": ["tables", "combined", "method"],
        "eval.json": ["headline", "baselines", "ablation", "routing",
                      "confusion_matrix", "operating_points",
                      "precision_recall_curve", "latency_seconds"],
        "routing.json": ["review_band", "total_in_review_band", "pairs"],
        "identities.json": ["total_identities", "identities"],
        "network.json": ["nodes", "edges", "recovered_edges"],
        "cases.json": ["weights", "candidate_pool", "accuracy", "cases"],
        "profiles.json": ["total_identities", "graph", "communities", "profiles"],
        "reconciliation.json": ["totals", "by_offence", "transition"],
        "hotspots.json": ["totals", "grid", "districts", "trends"],
        "runlog.json": ["run_id", "seed", "stages", "route_counts", "files_read"],
    }

    # Keys allowed to be null, with the reason.
    NULLABLE = {
        "age",                  # 4% of accused rows carry no recorded age
        "question_kn",          # absent where the phrasing is not one an
                                # officer would ask aloud, see ADR 023
        "raw_header_rejected",  # null when the table carries no protected
                                # column, so there was nothing to reject
        "conflict_reason",      # only set on a cannot link conflict
        "top_offence",          # a district with no cases has none
        "min", "max", "mean",   # absent when an identity has no internal edges
        "primary_circle", "first_case", "last_case",
        "median_rank_when_found", "modularity", "level",
        "precision_90", "precision_95",   # may be unreachable on the curve
        "multiple_over_exact", "base_rate_ratio", "f1",
        "corpus_generated_at", "co_offending_preset",
    }

    def feeds(self):
        if not DATA.exists():
            self.skipTest("web/public/data not generated, run: make export")
        return sorted(DATA.glob("*.json"))

    def test_every_required_feed_exists(self):
        present = {p.name for p in self.feeds()}
        for name in self.REQUIRED:
            with self.subTest(feed=name):
                self.assertIn(name, present, f"{name} was not exported")

    def test_required_keys_present(self):
        for path in self.feeds():
            required = self.REQUIRED.get(path.name)
            if not required:
                continue
            payload = load(path)
            for key in required:
                with self.subTest(feed=path.name, key=key):
                    self.assertIn(key, payload)

    def test_no_null_nan_or_placeholder(self):
        for path in self.feeds():
            for where, value in walk(load(path), path.name):
                leaf = where.rsplit(".", 1)[-1].split("[")[0]
                if leaf in self.NULLABLE:
                    continue
                with self.subTest(where=where):
                    self.assertIsNotNone(value, f"{where} is null")
                    if isinstance(value, float):
                        self.assertFalse(math.isnan(value), f"{where} is NaN")
                        self.assertFalse(math.isinf(value), f"{where} is infinite")
                    if isinstance(value, str):
                        self.assertNotIn(value.strip().lower(), PLACEHOLDERS,
                                         f"{where} is a placeholder")

    def test_metrics_are_in_range(self):
        for path in self.feeds():
            for where, value in walk(load(path), path.name):
                leaf = where.rsplit(".", 1)[-1].split("[")[0]
                if leaf not in {"precision", "recall", "f1", "f_beta_0_5",
                                "false_merge_rate", "reduction_ratio",
                                "base_rate", "coverage", "auc"}:
                    continue
                if value is None:
                    continue
                with self.subTest(where=where):
                    self.assertGreaterEqual(value, 0.0, where)
                    self.assertLessEqual(value, 1.0, where)

    def test_counts_are_non_negative_integers(self):
        for path in self.feeds():
            for where, value in walk(load(path), path.name):
                leaf = where.rsplit(".", 1)[-1].split("[")[0]
                if leaf not in {"cases", "accused_rows", "candidate_pairs",
                                "true_positive_pairs", "false_positive_pairs",
                                "false_negative_pairs", "merged_pairs",
                                "record_count", "case_count", "shared_cases"}:
                    continue
                if not isinstance(value, (int, float)):
                    continue
                with self.subTest(where=where):
                    self.assertGreaterEqual(value, 0, where)


class TestCanonicalConsistency(unittest.TestCase):
    """No figure anywhere may disagree with canonical.json."""

    def setUp(self):
        if not CANONICAL.exists():
            self.skipTest("eval/canonical.json not generated, run: make eval")
        self.canonical = load(CANONICAL)
        self.headline = self.canonical["headline"]

    def test_eval_headline_matches_canonical(self):
        path = DATA / "eval.json"
        if not path.exists():
            self.skipTest("eval.json not exported")
        ev = load(path)
        for key in ("precision", "recall", "f1"):
            with self.subTest(key=key):
                self.assertAlmostEqual(
                    ev["headline"][key], self.headline[key], places=9,
                    msg=f"eval.json headline {key} disagrees with canonical")

    def test_deployed_operating_point_is_the_canonical_one(self):
        path = DATA / "eval.json"
        if not path.exists():
            self.skipTest("eval.json not exported")
        ev = load(path)
        self.assertEqual(ev["deployed_operating_point"], "deployed")
        deployed = ev["operating_points"]["deployed"]
        self.assertAlmostEqual(deployed["f1"], self.headline["f1"], places=9)
        self.assertAlmostEqual(
            deployed["threshold"], self.canonical["definition"]["threshold_llr"],
            places=6)

    def test_every_other_operating_point_has_a_qualifier(self):
        for key in self.canonical["qualifiers"]:
            with self.subTest(point=key):
                self.assertTrue(self.canonical["qualifiers"][key].strip())
        self.assertIn("do not deploy", self.canonical["qualifiers"]["f1_optimal"])

    def test_screens_hardcode_no_metric(self):
        """Every figure on a screen must come from JSON, never from source.

        A four decimal literal in a screen file is a number that will silently
        go stale the next time the engine is run.
        """
        pattern = re.compile(r"\b0\.\d{4}\b")
        allowed = {"0.0000"}
        offenders = []
        for path in (ROOT / "web" / "src").rglob("*.tsx"):
            for number, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), start=1):
                if line.lstrip().startswith(("*", "//")):
                    continue
                for match in pattern.findall(line):
                    if match in allowed:
                        continue
                    offenders.append(f"{path.name}:{number} {match}")
        self.assertEqual(offenders, [], "hardcoded metrics found in screens")

    def test_documents_agree_with_canonical(self):
        """The headline in README and the leaderboard must be the canonical one."""
        f1 = f"{self.headline['f1']:.4f}"
        precision = f"{self.headline['precision']:.4f}"
        for name in ("README.md", "benchmark/leaderboard.md"):
            path = ROOT / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            with self.subTest(document=name):
                self.assertIn(f1, text, f"{name} does not carry the canonical F1")
                self.assertIn(precision, text,
                              f"{name} does not carry the canonical precision")


class TestTwoProducts(unittest.TestCase):
    """The deployable operating point and the ceiling argument, ADR 027.

    Both are claims a reader will act on. The deployable point is what a
    department would merge on unattended, so a regression that quietly dropped
    its precision below the stated bar would be the worst kind of silent
    failure this project could ship.
    """

    def setUp(self):
        if not CANONICAL.exists():
            self.skipTest("run: make eval")
        self.canonical = load(CANONICAL)

    def test_both_products_are_present(self):
        products = self.canonical["products"]
        self.assertIsNotNone(products["deployable"])
        self.assertIsNotNone(products["investigative"])

    def test_the_deployable_point_actually_clears_the_bar(self):
        """It is defined as precision at or above 0.95. It must be."""
        deployable = self.canonical["products"]["deployable"]
        self.assertGreaterEqual(deployable["precision"], 0.95)

    def test_the_deployable_point_is_the_highest_recall_clearing_the_bar(self):
        """Any other point at precision 0.95 or better must have less recall."""
        path = DATA / "eval.json"
        if not path.exists():
            self.skipTest("eval.json not exported")
        curve = load(path)["precision_recall_curve"]
        deployable = self.canonical["products"]["deployable"]
        eligible = [p for p in curve if p["precision"] >= 0.95]
        self.assertTrue(eligible)
        self.assertAlmostEqual(deployable["recall"],
                               max(p["recall"] for p in eligible), places=9)

    def test_the_investigative_point_is_the_canonical_headline(self):
        investigative = self.canonical["products"]["investigative"]
        for key in ("precision", "recall", "f1"):
            with self.subTest(key=key):
                self.assertAlmostEqual(investigative[key],
                                       self.canonical["headline"][key], places=9)

    def test_deployable_trades_recall_for_precision(self):
        """The whole point of having two. If they agree, one is redundant."""
        deployable = self.canonical["products"]["deployable"]
        investigative = self.canonical["products"]["investigative"]
        self.assertGreater(deployable["precision"], investigative["precision"])
        self.assertLess(deployable["recall"], investigative["recall"])

    def test_the_ceiling_bounds_the_headline(self):
        """A headline above its own oracle ceiling would mean the oracle is wrong."""
        ceiling = self.canonical["ceiling_argument"]
        self.assertLessEqual(ceiling["headline_f1"], ceiling["oracle_f1"])
        self.assertAlmostEqual(
            ceiling["share_of_ceiling"],
            ceiling["headline_f1"] / ceiling["oracle_f1"], places=9)

    def test_the_ceiling_statement_carries_its_figures(self):
        ceiling = self.canonical["ceiling_argument"]
        statement = ceiling["statement"]
        self.assertIn(f"{ceiling['oracle_f1']:.4f}", statement)
        self.assertIn("data collection problem", statement)


class TestSparseTables(unittest.TestCase):
    """ADR 026. ComplainantDetails resolves, Victim does not, and both are stated."""

    PERSONS = ROOT / "data" / "corpus" / "other_persons_report.json"

    def setUp(self):
        if not self.PERSONS.exists():
            self.skipTest("run: make persons")
        self.persons = load(self.PERSONS)

    def test_complainant_resolves(self):
        """It was 0.0000 before the contact columns became features."""
        complainant = self.persons["tables"]["complainant"]
        self.assertGreater(complainant["results"]["f1"], 0.0)
        self.assertIn("phone", complainant["contact_channels"])
        self.assertIn("address", complainant["contact_channels"])

    def test_victim_has_no_contact_channels_and_is_not_claimed(self):
        victim = self.persons["tables"]["victim"]
        self.assertEqual(victim["contact_channels"], [])

    def test_no_protected_column_ever_became_a_signal(self):
        """The guard, checked on the shipped signal list rather than at the door."""
        for name, table in self.persons["tables"].items():
            for signal in table.get("signals_modelled", []):
                with self.subTest(table=name, signal=signal):
                    self.assertNotIn(
                        signal.lower(),
                        {"caste", "casteid", "religion", "religionid",
                         "occupation", "occupationid"})

    def test_the_guard_fired_on_the_table_that_carries_them(self):
        guard = self.persons["tables"]["victim"]["guard"]
        self.assertTrue(guard["table_carries_protected_columns"])
        self.assertTrue(guard["raw_header_rejected"])
        self.assertTrue(guard["projected_header_accepted"])


class TestStatusMirror(unittest.TestCase):
    """docs/build-status.md must carry every claim the screen carries.

    The mirror is parsed out of Status.tsx. When claim details grew {token}
    substitutions the parser's regex started matching the token instead of the
    object containing it, and every claim carrying a figure was silently
    dropped. The file still looked complete. This is the test that would have
    caught it.
    """

    SOURCE = ROOT / "web" / "src" / "screens" / "Status.tsx"
    TARGET = ROOT / "docs" / "build-status.md"

    def setUp(self):
        if not self.TARGET.exists():
            self.skipTest("run: python scripts/build_status_md.py")

    def claims_in_source(self) -> list[str]:
        text = self.SOURCE.read_text(encoding="utf-8")
        block = text.split("export const CLAIMS: Claim[] = [", 1)[1]
        return re.findall(r"claim: '([^']*)'", block)

    def test_every_claim_reaches_the_markdown(self):
        markdown = self.TARGET.read_text(encoding="utf-8")
        missing = [c for c in self.claims_in_source() if c not in markdown]
        self.assertEqual(missing, [], "claims dropped by the mirror")

    def test_the_counts_agree(self):
        rows = re.findall(r"^\| [A-Za-z]", self.TARGET.read_text(encoding="utf-8"),
                          re.M)
        self.assertGreaterEqual(len(rows), len(self.claims_in_source()))

    def test_no_token_survives_into_the_markdown(self):
        """A {token} in the output means the substitution table is missing one."""
        leftover = re.findall(r"\{[a-zA-Z]\w*\}",
                              self.TARGET.read_text(encoding="utf-8"))
        self.assertEqual(sorted(set(leftover)), [])


class TestSourceEncoding(unittest.TestCase):
    """No BOM, no null byte, no literal backtick n in a source file.

    All three have bitten this project. A BOM broke the generator's parse, a
    literal escape sequence landed in the middle of an argparse call, and a
    null byte silently ate a separator in the benchmark scorer.

    The scan itself lives in scripts/check_encoding.py so that `make check`
    runs exactly the same rule as the test suite. This class asserts the rule
    holds and that it fires on the real corruption.
    """

    def test_no_encoding_faults_anywhere(self):
        self.assertEqual(check_encoding.check(), [],
                         "run: python scripts/check_encoding.py")

    def test_the_escape_pattern_catches_the_real_thing(self):
        """The guard is only worth having if it fires on the actual corruption."""
        corrupted = '        "co_offending": preset,`n        "name_pool": 86,'
        self.assertTrue(check_encoding.ESCAPE.search(corrupted))
        for legitimate in ("`name` channel", "`num` cell", "`npm run check`",
                           "`n^${exponent}`"):
            with self.subTest(text=legitimate):
                self.assertIsNone(check_encoding.ESCAPE.search(legitimate))

    def test_the_scan_reaches_the_source_tree(self):
        """A guard that silently walks an empty tree passes forever."""
        names = {p.name for p in check_encoding.sources()}
        for expected in ("score.py", "generate.py", "Status.tsx"):
            with self.subTest(file=expected):
                self.assertIn(expected, names)


if __name__ == "__main__":
    unittest.main()
