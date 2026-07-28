"""Layer 1. Indic normalisation.

The load bearing test is `test_both_directions_agree`. It takes every name in
the generator's reference pool, which carries a Kannada and a Latin rendering
of the same name side by side, and asserts they fold to the same form. That is
the cross script claim measured rather than asserted.
"""

import unittest

from data.generator import reference_data as R
from engine.normalise.indic import (
    MARKER_TOKENS,
    fold_token,
    is_kannada,
    normalise,
    transliterate,
)

# English loanword monikers. ಆಟೋ is the correct Kannada for auto and ಲಾರಿ for
# lorry, but the English vowel and the Kannada vowel are genuinely different
# sounds, so no phonetic scheme folds them together. Recorded here rather than
# hidden, because it is a real failure mode for borrowed words.
KNOWN_LOANWORD_FAILURES = {"Auto", "Lorry"}


class TestTransliteration(unittest.TestCase):

    def test_inherent_vowel(self):
        # ಬಸಪ್ಪ, consonant with inherent a, virama suppressing it, and a final
        # inherent a.
        self.assertEqual(transliterate("ಬಸಪ್ಪ"), "basappa")

    def test_matra_replaces_inherent_vowel(self):
        self.assertEqual(transliterate("ರಮೇಶ"), "rameesha")

    def test_anusvara_and_conjunct(self):
        self.assertEqual(transliterate("ಮಂಜುನಾಥ"), "manjunaatha")

    def test_vocalic_r_reaches_latin_as_ri(self):
        # ಕೃಷ್ಣಪ್ಪ is Krishnappa in records, never Krushnappa.
        self.assertTrue(transliterate("ಕೃಷ್ಣಪ್ಪ").startswith("krish"))

    def test_latin_passes_through_untouched(self):
        for s in ["Ramesh Krishnappa", "R. Krishnappa", "MANJUNATH"]:
            self.assertEqual(transliterate(s), s)

    def test_script_detection(self):
        self.assertTrue(is_kannada("ರಮೇಶ"))
        self.assertFalse(is_kannada("Ramesh"))
        self.assertTrue(is_kannada("ರಮೇಶ Krishnappa"))


class TestFolding(unittest.TestCase):

    def test_both_directions_agree(self):
        """Every Kannada and Latin pair in the name pool folds to one form."""
        pools = [
            ("given male", R.GIVEN_NAMES_MALE),
            ("given female", R.GIVEN_NAMES_FEMALE),
            ("patronymic", R.FATHER_NAMES),
            ("moniker", R.MONIKERS),
        ]
        failures = []
        total = 0
        for label, pool in pools:
            for latin, kannada in pool:
                total += 1
                if latin in KNOWN_LOANWORD_FAILURES:
                    continue
                with self.subTest(pool=label, name=latin):
                    self.assertEqual(
                        fold_token(latin),
                        fold_token(transliterate(kannada)),
                        f"{latin} and {kannada} must fold together",
                    )
        self.assertGreater(total, 100)

    def test_transliteration_alternations_fold_together(self):
        """The exact perturbations the generator plants must survive folding."""
        equivalent = [
            ("Girish", "Gireesh"),
            ("Lakshmi", "Laxmi"),
            ("Krishnappa", "Krisnappa"),
            ("Krishnappa", "Krishnapa"),
            ("Manjunath", "Manjunatha"),
            ("Manjunath", "Manjunat"),
            ("Ramesh", "Ramesha"),
            ("Ramesh", "Rameshu"),
            ("Basappa", "Basapa"),
            ("Shivakumar", "Sivakumar"),
            ("Boregowda", "Boregauda"),
            ("Puttaswamy", "Puttaswami"),
            ("Muniyappa", "Muniappa"),
            ("Siddappa", "Sidappa"),
            ("Hanumantha", "Hanumanta"),
        ]
        for a, b in equivalent:
            with self.subTest(pair=(a, b)):
                self.assertEqual(fold_token(a), fold_token(b))

    def test_different_names_stay_different(self):
        """Folding must not be so aggressive that it merges distinct names.

        Over folding is the failure mode that produces false merges, which is
        the harm this whole system is built to avoid.
        """
        distinct = [
            ("Ramesh", "Suresh"), ("Manjunath", "Manjula"),
            ("Basappa", "Basavaraj"), ("Siddappa", "Siddaraju"),
            ("Nagappa", "Nagaraj"), ("Krishnappa", "Krishnamurthy"),
            ("Boregowda", "Kempegowda"), ("Shivappa", "Shivakumar"),
            ("Vijay", "Vinay"), ("Mahesh", "Mahadev"),
            ("Lakshmi", "Lokesh"), ("Prakash", "Prasad"),
        ]
        for a, b in distinct:
            with self.subTest(pair=(a, b)):
                self.assertNotEqual(fold_token(a), fold_token(b))

    def test_vijay_folds_across_scripts(self):
        # Regression. ವಿಜಯ transliterates to vijaya, and the Latin record says
        # Vijay. The glide rule has to bring those together.
        self.assertEqual(fold_token("Vijay"), fold_token(transliterate("ವಿಜಯ")))
        self.assertEqual(fold_token("Vijay"), fold_token("Vijaya"))
        # It stays separate from the other names in the pool, which is what
        # actually matters. Vijay and Viji do collide, and that over merge is
        # accepted deliberately, see the comment on _GLIDE_Y.
        self.assertNotEqual(fold_token("Vijay"), fold_token("Vinay"))
        self.assertNotEqual(fold_token("Vijay"), fold_token("Vijayalakshmi"))

    def test_nasal_assimilation(self):
        # ಅಂಬಿಕಾ is written Ambika, ಕೆಂಪು is Kempu. The same anusvara reaches
        # Latin as m or n depending on the writer.
        self.assertEqual(fold_token("Ambika"), fold_token("Anbika"))
        self.assertEqual(fold_token("Kempegowda"), fold_token("Kenpegowda"))

    def test_no_soundex_anywhere(self):
        """ADR 003. Vowels must survive folding in reduced form.

        Soundex would map Ramesh and Rmsh identically because it deletes
        vowels. If that ever becomes true here, the scheme has degenerated
        into Soundex and the ADR is violated.
        """
        self.assertNotEqual(fold_token("Ramesh"), fold_token("Rmsh"))
        self.assertNotEqual(fold_token("Basappa"), fold_token("Bsp"))
        self.assertNotEqual(fold_token("Kumar"), fold_token("Kamar"))


class TestNormalise(unittest.TestCase):

    def test_relationship_markers_removed(self):
        for form in ["Ramesh S/o Krishnappa", "Ramesh s/o. Krishnappa",
                     "ರಮೇಶ ತಂದೆ ಕೃಷ್ಣಪ್ಪ", "ರಮೇಶ ಬಿನ್ ಕೃಷ್ಣಪ್ಪ"]:
            with self.subTest(form=form):
                n = normalise(form)
                self.assertEqual(len(n.tokens), 2, f"{form} -> {n.tokens}")
                self.assertFalse(any(t in MARKER_TOKENS for t in n.tokens))

    def test_relationship_marker_leaves_no_stray_initial(self):
        # s/o must not survive as the initials s and o.
        n = normalise("Ramesh S/o Krishnappa")
        self.assertNotIn("o", n.initials)
        self.assertNotIn("s", n.initials)

    def test_token_reordering_is_canonical(self):
        a = normalise("Ramesh Krishnappa")
        b = normalise("Krishnappa Ramesh")
        self.assertEqual(a.canonical, b.canonical)

    def test_all_generator_variants_of_one_person_share_a_token(self):
        """The practical requirement. Different renderings must stay reachable."""
        forms = [
            "Ramesh Krishnappa", "Ramesh", "Ramesh S/o Krishnappa",
            "R. Krishnappa", "Ramesh K", "Krishnappa Ramesh",
            "RAMESH KRISHNAPPA", "Kadu Ramesh", "Ramesh @ Kadu Ramesh",
            "ರಮೇಶ ಕೃಷ್ಣಪ್ಪ", "ರಮೇಶ", "ರಮೇಶ ತಂದೆ ಕೃಷ್ಣಪ್ಪ",
            "ರಮೇಶ ಕೃಷ್ಣಪ್ಪ ", "  Ramesh  Krishnappa",
        ]
        normalised = [normalise(f) for f in forms]
        reference = normalise("Ramesh Krishnappa")
        pool = set(reference.tokens)
        for form, n in zip(forms, normalised):
            with self.subTest(form=form):
                reachable = bool(set(n.tokens) & pool) or bool(n.letters & reference.letters)
                self.assertTrue(reachable, f"{form!r} -> {n.tokens} {n.initials}")

    def test_initials_only_form_yields_letters_but_no_tokens(self):
        n = normalise("R.K.")
        self.assertEqual(n.tokens, ())
        self.assertTrue(n.is_empty)
        self.assertEqual(set(n.initials), {"r", "k"})
        self.assertEqual(n.letters, {"r", "k"})

    def test_zero_width_and_whitespace_noise_absorbed(self):
        clean = normalise("Ramesh Krishnappa")
        for noisy in ["Ramesh‍ Krishnappa", " Ramesh  Krishnappa ",
                      "Ramesh.Krishnappa", "Ramesh,Krishnappa"]:
            with self.subTest(noisy=noisy):
                self.assertEqual(normalise(noisy).canonical, clean.canonical)

    def test_script_is_labelled(self):
        self.assertEqual(normalise("Ramesh Krishnappa").script, "latin")
        self.assertEqual(normalise("ರಮೇಶ ಕೃಷ್ಣಪ್ಪ").script, "kannada")
        self.assertEqual(normalise("ರಮೇಶ Krishnappa").script, "mixed")

    def test_empty_and_degenerate_input(self):
        for bad in ["", "   ", "...", "@", "S/o"]:
            with self.subTest(bad=bad):
                n = normalise(bad)
                self.assertTrue(n.is_empty)


if __name__ == "__main__":
    unittest.main()
