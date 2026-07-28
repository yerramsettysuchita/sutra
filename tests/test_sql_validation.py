"""The gold SQL, proved to run rather than asserted to be right.

An audit found the sharpest gap in this project: 150 hand written SQL queries
whose headline claim was that 76 of them cannot be answered on the KSP schema,
and not one had ever been executed. `data/schema/ksp_schema.sql` was read by no
code at all. The validation that existed checked whether the query *text*
mentioned a resolved table, which is checking our own bookkeeping.

Running them found 36 broken queries, all of them referencing columns that do
not exist. `CSType` was invented and the real column is `CaseMaster.CaseStatus`.
`ActAbbreviation` is `ActAbbr`. `SectionNumber` is `SectionNo`. Every one of
those would have been read as authoritative by a reviewer.

These tests keep that fixed. They skip cleanly if the database has not been
built, so a fresh clone still passes.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "eval" / "sql_validation.json"
DB = ROOT / "data" / "corpus" / "sutra.db"


class TestGoldSqlExecutes(unittest.TestCase):

    def setUp(self):
        if not REPORT.exists():
            self.skipTest("run: make validate-sql")
        self.report = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_every_query_executes(self):
        """Not 'looks like SQL'. Executes, against the real DDL."""
        broken = [r["id"] for r in self.report["results"]
                  if not r["runs_on_full_schema"]]
        self.assertEqual(broken, [], "queries that do not run")

    def test_all_150_were_run(self):
        self.assertEqual(self.report["total"], 150)
        self.assertEqual(self.report["execute_on_full_schema"], 150)

    def test_the_headline_claim_is_enforced_by_the_database(self):
        """Every question marked unanswerable must genuinely fail on raw KSP.

        This is what turns the headline from something we wrote into something
        the schema demonstrates. If a query marked as needing the person key
        runs fine without the resolved tables, the count of 76 is wrong.
        """
        self.assertEqual(self.report["requires_person_key_contradicted"], 0)
        self.assertEqual(
            self.report["requires_person_key_confirmed_by_database"],
            self.report["requires_person_key_claimed"])

    def test_nothing_was_undercounted(self):
        """A query not marked as needing the key must run on the raw schema.

        The mirror of the test above. If an unmarked query also fails on raw
        KSP, then the true count is higher than 76 and we are understating our
        own argument, which is a different kind of wrong but still wrong.
        """
        self.assertEqual(self.report["unmarked_but_failing_on_raw_schema"], 0)

    def test_no_query_reads_a_protected_column(self):
        self.assertEqual(self.report["queries_reading_protected_columns"], 0)

    def test_the_database_was_built_from_the_shipped_ddl(self):
        """If the DDL stops being the thing loaded, this all proves nothing."""
        if not DB.exists():
            self.skipTest("database not built")
        import sqlite3
        conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        present = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        ddl = (ROOT / "data" / "schema" / "ksp_schema.sql").read_text(
            encoding="utf-8")
        import re
        for table in re.findall(r"CREATE TABLE (\w+)", ddl):
            with self.subTest(table=table):
                self.assertIn(table, present)
        # And the tables SUTRA adds, which are the whole argument.
        for added in ("resolved_identity", "resolved_victim",
                      "resolved_complainant"):
            with self.subTest(table=added):
                self.assertIn(added, present)


if __name__ == "__main__":
    unittest.main()
