"""Layer 2. Blocking keys."""

import unittest

from engine.block.keys import FAMILIES, keys_for
from engine.normalise.indic import normalise


def keys(name, circle=42):
    return keys_for(normalise(name), circle)


def flat(name, circle=42):
    return set().union(*keys(name, circle).values())


class TestBlockingKeys(unittest.TestCase):

    def test_every_family_is_produced(self):
        k = keys("Ramesh Krishnappa")
        self.assertEqual(set(k), set(FAMILIES))

    def test_one_phonetic_key_per_token(self):
        k = keys("Ramesh Krishnappa")
        self.assertEqual(len(k["PH"]), 2)

    def test_variants_of_one_person_collide(self):
        """The requirement. Different renderings must land in a shared block."""
        forms = [
            "Ramesh Krishnappa", "Ramesh", "Ramesh S/o Krishnappa",
            "R. Krishnappa", "Ramesh K", "Krishnappa Ramesh",
            "RAMESH KRISHNAPPA", "ರಮೇಶ ಕೃಷ್ಣಪ್ಪ", "ರಮೇಶ ತಂದೆ ಕೃಷ್ಣಪ್ಪ",
            "Ramesha Krishnapa", "R.K.",
        ]
        reference = flat("Ramesh Krishnappa")
        for form in forms:
            with self.subTest(form=form):
                self.assertTrue(flat(form) & reference,
                                f"{form!r} shares no block with the reference")

    def test_initials_only_reachable_through_territory(self):
        """R.K. has no phonetic key at all, so TR is the only way to reach it."""
        k = keys("R.K.")
        self.assertEqual(k["PH"], frozenset())
        self.assertEqual(k["P4"], frozenset())
        self.assertTrue(k["TR"])
        self.assertTrue(k["TR"] & keys("Ramesh Krishnappa")["TR"])

    def test_territorial_key_separates_circles(self):
        a = keys("Ramesh Krishnappa", circle=11)["TR"]
        b = keys("Ramesh Krishnappa", circle=22)["TR"]
        self.assertFalse(a & b)

    def test_phonetic_key_ignores_territory(self):
        a = keys("Ramesh Krishnappa", circle=11)["PH"]
        b = keys("Ramesh Krishnappa", circle=22)["PH"]
        self.assertEqual(a, b)

    def test_ph_is_subsumed_by_p4(self):
        """Empirical result from the evaluator, asserted as an invariant.

        Truncating to four characters can only merge blocks, never split them,
        so any two records sharing a PH key must share a P4 key. This is why
        the shipped scheme is P4 plus TR and PH is a diagnostic only.
        """
        names = ["Ramesh Krishnappa", "Ramesha Krisnapa", "Manjunath Basappa",
                 "Manjunatha Basapa", "ರಮೇಶ ಕೃಷ್ಣಪ್ಪ", "Suresh Basappa"]
        for a in names:
            for b in names:
                ka, kb = keys(a), keys(b)
                if ka["PH"] & kb["PH"]:
                    with self.subTest(a=a, b=b):
                        self.assertTrue(ka["P4"] & kb["P4"])

    def test_distinct_people_do_not_share_a_phonetic_key(self):
        self.assertFalse(flat("Ramesh Krishnappa", 1) & flat("Suresh Basappa", 2))

    def test_empty_name_produces_no_keys_at_all(self):
        k = keys("")
        self.assertEqual(k["PH"], frozenset())
        self.assertEqual(k["P4"], frozenset())
        self.assertEqual(k["TR"], frozenset())


if __name__ == "__main__":
    unittest.main()
