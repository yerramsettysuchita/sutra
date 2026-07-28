"""The excluded feature guard must fail hard, not warn.

If these tests are deleted or weakened, docs/ethics.md section 5 becomes a
claim rather than a control.
"""

import unittest

from engine.policy import (
    EXCLUDED_FEATURE_COLUMNS,
    ExcludedFeatureError,
    assert_no_excluded_features,
    is_excluded,
)


class TestExcludedFeatures(unittest.TestCase):

    def test_permitted_columns_pass(self):
        assert_no_excluded_features(
            ["AccusedName", "AgeYear", "DistrictID", "Latitude", "BriefFacts"],
            context="test",
        )

    def test_caste_raises(self):
        with self.assertRaises(ExcludedFeatureError):
            assert_no_excluded_features(["AccusedName", "CasteID"], context="test")

    def test_religion_raises(self):
        with self.assertRaises(ExcludedFeatureError):
            assert_no_excluded_features(["ReligionID"], context="test")

    def test_occupation_raises(self):
        with self.assertRaises(ExcludedFeatureError):
            assert_no_excluded_features(["OccupationID"], context="test")

    def test_case_and_separator_insensitive(self):
        # Renaming a column should not slip it past the guard by accident.
        for variant in ["casteid", "CASTE_ID", "caste id", "Caste_Id", "religionID"]:
            with self.subTest(variant=variant):
                self.assertTrue(is_excluded(variant))

    def test_error_names_the_offending_column_and_the_call_site(self):
        with self.assertRaises(ExcludedFeatureError) as ctx:
            assert_no_excluded_features(["CasteID", "ReligionID"],
                                        context="linkage.build_comparison_vectors")
        message = str(ctx.exception)
        self.assertIn("CasteID", message)
        self.assertIn("ReligionID", message)
        self.assertIn("linkage.build_comparison_vectors", message)

    def test_all_three_protected_families_are_covered(self):
        for family in ("Caste", "Religion", "Occupation"):
            self.assertTrue(
                any(c.startswith(family) for c in EXCLUDED_FEATURE_COLUMNS),
                f"{family} missing from the exclusion list",
            )


if __name__ == "__main__":
    unittest.main()
