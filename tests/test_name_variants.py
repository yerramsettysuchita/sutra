"""Name rendering must be varied, reproducible, and honestly labelled."""

import random
import unittest

from data.generator import name_variants as NV

IDENTITY = {
    "given_la": "Ramesh", "given_kn": "ರಮೇಶ",
    "father_la": "Krishnappa", "father_kn": "ಕೃಷ್ಣಪ್ಪ",
    "moniker_la": "Kadu", "moniker_kn": "ಕಾಡು",
    "use_bin": True,
}

NO_MONIKER = {**IDENTITY, "moniker_la": None, "moniker_kn": None, "use_bin": False}


class TestRendering(unittest.TestCase):

    def test_every_variant_renders_non_empty(self):
        rng = random.Random(1)
        for vid in NV.VARIANT_IDS:
            with self.subTest(variant=vid):
                out = NV.render(IDENTITY, vid, rng, perturb_probability=0.0)
                self.assertTrue(out["rendered"].strip())
                self.assertEqual(out["variant"], vid)

    def test_script_label_matches_the_rendered_string(self):
        rng = random.Random(2)
        for vid in NV.VARIANT_IDS:
            declared = NV.SCRIPT_OF[vid]
            out = NV.render(IDENTITY, vid, rng, perturb_probability=0.0)
            actual = NV.script_of_string(out["rendered"])
            with self.subTest(variant=vid):
                if declared == "kannada":
                    # Kannada variants must contain no Latin letters at all,
                    # otherwise the cross script measurement in the audit is
                    # counting pairs that were never genuinely cross script.
                    self.assertEqual(actual, "kannada")
                elif declared == "latin":
                    self.assertEqual(actual, "latin")
                else:
                    self.assertEqual(actual, "mixed")

    def test_moniker_variants_are_skipped_without_a_moniker(self):
        rng = random.Random(3)
        chosen = {NV.choose_variant(NO_MONIKER, rng) for _ in range(600)}
        self.assertNotIn("LA_MONIKER", chosen)
        self.assertNotIn("KN_MONIKER", chosen)
        self.assertNotIn("LA_ALIAS", chosen)
        self.assertNotIn("KN_ALIAS", chosen)
        self.assertNotIn("KN_BIN", chosen)

    def test_choose_variant_produces_real_spread(self):
        rng = random.Random(4)
        chosen = {NV.choose_variant(IDENTITY, rng) for _ in range(1500)}
        # A generator that collapses onto two forms would make the corpus easy
        # in exactly the way real data is not.
        self.assertGreaterEqual(len(chosen), 12)

    def test_script_bias_shifts_the_distribution(self):
        rng = random.Random(5)
        kn = sum(NV.SCRIPT_OF[NV.choose_variant(IDENTITY, rng, "kannada")] == "kannada"
                 for _ in range(2000))
        rng = random.Random(5)
        la = sum(NV.SCRIPT_OF[NV.choose_variant(IDENTITY, rng, "latin")] == "kannada"
                 for _ in range(2000))
        self.assertGreater(kn, la * 2)

    def test_rendering_is_deterministic_for_a_fixed_seed(self):
        a = NV.render(IDENTITY, "LA_FULL", random.Random(99))
        b = NV.render(IDENTITY, "LA_FULL", random.Random(99))
        self.assertEqual(a["rendered"], b["rendered"])
        self.assertEqual(a["perturbations"], b["perturbations"])

    def test_provenance_is_recorded_when_perturbation_fires(self):
        rng = random.Random(7)
        seen = False
        for _ in range(400):
            out = NV.render(IDENTITY, "LA_FULL", rng, perturb_probability=1.0)
            if out["perturbations"]:
                seen = True
                # Anything the audit reports has to be traceable to a rule.
                for rule in out["perturbations"]:
                    self.assertIn(rule, {name for name, _ in NV.PERTURBATIONS})
        self.assertTrue(seen)

    def test_perturbation_changes_the_string_when_it_claims_to(self):
        rng = random.Random(11)
        for token in ["Ramesh", "Krishnappa", "Manjunath", "Girish", "Lakshmi",
                      "Siddappa", "Muniyappa", "Chandru"]:
            out, rule = NV.perturb_latin_token(token, rng)
            with self.subTest(token=token):
                if rule is not None:
                    self.assertNotEqual(out.lower(), token.lower())

    def test_initial_variants_are_flagged_as_abbreviated(self):
        rng = random.Random(13)
        for vid in ("LA_INITIAL_PREFIX", "LA_INITIAL_SUFFIX", "LA_INITIAL_BOTH"):
            out = NV.render(IDENTITY, vid, rng, perturb_probability=0.0)
            self.assertTrue(out["father_abbreviated"])


if __name__ == "__main__":
    unittest.main()
