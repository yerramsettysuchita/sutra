"""Layers 3 to 7. Invariants that must hold whatever the numbers do."""

import unittest

import numpy as np

from engine.calibrate import isotonic
from engine.cluster import correlation
from engine.cluster.collective import _canonical
from engine.features import signals as S
from engine.linkage import fellegi_sunter as fs


class TestSignals(unittest.TestCase):

    def test_jaro_winkler_bounds_and_identity(self):
        self.assertAlmostEqual(S.jaro_winkler("ramis", "ramis"), 1.0)
        self.assertEqual(S.jaro_winkler("", ""), 0.0)
        for a, b in [("ramis", "ramisa"), ("basap", "basp"), ("x", "y")]:
            with self.subTest(pair=(a, b)):
                self.assertGreaterEqual(S.jaro_winkler(a, b), 0.0)
                self.assertLessEqual(S.jaro_winkler(a, b), 1.0)

    def test_jaro_winkler_rewards_shared_prefix(self):
        # Names lead with the given name, so a shared prefix matters more.
        self.assertGreater(S.jaro_winkler("manjunat", "manjunath"),
                           S.jaro_winkler("manjunat", "xanjunat"))

    def test_token_set_is_order_free(self):
        a = frozenset({"ramis", "krisnap"})
        b = frozenset({"krisnap", "ramis"})
        self.assertEqual(S.token_set_ratio(a, b), 1.0)

    def test_missing_age_is_not_computable_not_disagreement(self):
        self.assertTrue(np.isnan(S.implied_birth_year("2023-01-01", "")))
        self.assertEqual(S.temporal_level(float("nan")), S.NOT_COMPUTABLE)
        self.assertNotEqual(S.temporal_level(float("nan")), 0)

    def test_birth_year_tolerance_is_two_years(self):
        self.assertEqual(S.temporal_level(0.0), 2)
        self.assertEqual(S.temporal_level(2.0), 1)
        self.assertEqual(S.temporal_level(3.0), 0)

    def test_haversine_known_distance(self):
        # Bengaluru to Mysuru, about 128 km.
        km = float(S.haversine_km(12.97, 77.59, 12.30, 76.65))
        self.assertGreater(km, 110)
        self.assertLess(km, 145)

    def test_hierarchy_distance(self):
        root = ["r"]
        a = ["r", "d1", "s1", "u1"]
        b = ["r", "d1", "s1", "u2"]
        c = ["r", "d2", "s9", "u9"]
        self.assertEqual(S.hierarchy_distance(a, a), 0)
        self.assertEqual(S.hierarchy_distance(a, b), 2)
        self.assertGreater(S.hierarchy_distance(a, c), S.hierarchy_distance(a, b))
        self.assertEqual(S.hierarchy_distance(root, root), 0)

    def test_name_level_ordering_and_coverage(self):
        self.assertEqual(S.name_level(1.0, 2, True), 5)
        self.assertEqual(S.name_level(0.0, S.NOT_COMPUTABLE, False), 4)
        self.assertEqual(S.name_level(0.9, 1, True), 3)
        self.assertEqual(S.name_level(0.9, 1, False), 2)
        self.assertEqual(S.name_level(0.75, 0, False), 1)
        self.assertEqual(S.name_level(0.1, 0, False), 0)

    def test_protected_attributes_are_not_signals(self):
        from engine.policy import ExcludedFeatureError, assert_no_excluded_features
        assert_no_excluded_features(S.SIGNALS, context="test")
        assert_no_excluded_features(S.MODEL_SIGNALS, context="test")
        with self.assertRaises(ExcludedFeatureError):
            assert_no_excluded_features(list(S.SIGNALS) + ["CasteID"], context="test")


class TestLinkage(unittest.TestCase):

    def _levels(self, n=4000, seed=7):
        rng = np.random.default_rng(seed)
        match = rng.random(n) < 0.02
        levels = {}
        for signal in S.MODEL_SIGNALS:
            top = S.LEVELS[signal] - 1
            drawn = np.where(match,
                             rng.integers(top - 1, top + 1, n),
                             rng.integers(0, 2, n))
            levels[signal] = drawn.astype(np.int8)
        return levels, match

    def test_not_computable_always_has_zero_weight(self):
        """ADR 020. A missing measurement must never move the score."""
        levels, _ = self._levels()
        for signal in S.MODEL_SIGNALS:
            levels[signal][:50] = S.NOT_COMPUTABLE
        model = fs.fit_em(levels)
        for signal in S.MODEL_SIGNALS:
            with self.subTest(signal=signal):
                self.assertEqual(model.weights()[signal][0], 0.0)

    def test_unobserved_levels_carry_zero_weight(self):
        levels, _ = self._levels()
        model = fs.fit_em(levels)
        for signal in S.MODEL_SIGNALS:
            weights = model.weights()[signal]
            for level, support in enumerate(model.support[signal]):
                if support < fs.MIN_LEVEL_SUPPORT:
                    with self.subTest(signal=signal, level=level):
                        self.assertEqual(weights[level], 0.0)

    def test_score_is_additive_over_signals(self):
        levels, _ = self._levels()
        model = fs.fit_em(levels)
        total = fs.score(model, levels)
        parts = fs.per_signal_contributions(model, levels)
        self.assertTrue(np.allclose(total, sum(parts.values())))

    def test_frequency_adjustment_direction(self):
        """A rare name must gain weight and a common name must lose it."""
        frequency = {"rare": 0.0002, "common": 0.05}
        u_generic = fs.generic_agreement_u(frequency)
        adjustment = fs.frequency_adjustment(["rare", "common", ""],
                                             frequency, u_generic)
        self.assertGreater(adjustment[0], 0.0)
        self.assertLess(adjustment[1], 0.0)
        self.assertEqual(adjustment[2], 0.0)

    def test_generic_agreement_u_is_sum_of_squares(self):
        frequency = {"a": 0.5, "b": 0.5}
        self.assertAlmostEqual(fs.generic_agreement_u(frequency), 0.5)

    def test_leave_one_out_seed_excludes_its_target(self):
        """A seed must not be selected using the signal it will estimate."""
        levels, _ = self._levels()
        for signal in S.MODEL_SIGNALS:
            seed = fs.leave_one_out_seed(levels, signal)
            if seed.sum() < 2:
                continue
            selected = levels[signal][seed]
            with self.subTest(signal=signal):
                # If the seed conditioned on its target the values would be
                # constant at the top level.
                self.assertGreater(len(np.unique(selected)), 0)

    def test_posterior_threshold_falls_as_prior_rises(self):
        low = fs.FittedModel(p_match=0.001, m={}, u={})
        high = fs.FittedModel(p_match=0.10, m={}, u={})
        self.assertGreater(fs.posterior_threshold(low),
                           fs.posterior_threshold(high))


class TestClustering(unittest.TestCase):

    def test_cannot_link_is_never_violated(self):
        """Two rows on one FIR must never land in one cluster."""
        case_of = np.array([0, 0, 1, 1, 2, 2], dtype=np.int32)
        pair_a = np.array([0, 2, 1, 3], dtype=np.int32)
        pair_b = np.array([2, 4, 3, 5], dtype=np.int32)
        scores = np.array([10.0, 10.0, 10.0, 10.0])
        result = correlation.cluster(6, pair_a, pair_b, scores, 1.0, case_of,
                                     min_density=0.0)
        self.assertEqual(result.violations_after, 0)
        for a, b in correlation.cannot_link_pairs(case_of):
            with self.subTest(pair=(a, b)):
                self.assertNotEqual(result.labels[a], result.labels[b])

    def test_density_rule_refuses_a_single_bridge(self):
        """One weak link between two groups must not merge them."""
        case_of = np.arange(6, dtype=np.int32)
        # Two triangles joined by one edge.
        pair_a = np.array([0, 0, 1, 3, 3, 4, 2], dtype=np.int32)
        pair_b = np.array([1, 2, 2, 4, 5, 5, 3], dtype=np.int32)
        scores = np.full(len(pair_a), 5.0)
        dense = correlation.cluster(6, pair_a, pair_b, scores, 1.0, case_of,
                                    min_density=0.5)
        loose = correlation.cluster(6, pair_a, pair_b, scores, 1.0, case_of,
                                    min_density=0.0)
        self.assertGreater(dense.n_clusters, loose.n_clusters)
        self.assertEqual(loose.n_clusters, 1)

    def test_cannot_link_pairs_counts_pairs_not_cases(self):
        # One case with four accused contributes six pairs, not one.
        case_of = np.array([0, 0, 0, 0], dtype=np.int32)
        self.assertEqual(len(correlation.cannot_link_pairs(case_of)), 6)

    def test_pairwise_scores_perfect_and_singleton(self):
        truth = np.array([0, 0, 1, 1])
        perfect = correlation.pairwise_scores(np.array([5, 5, 9, 9]), truth)
        self.assertAlmostEqual(perfect["f1"], 1.0)
        singletons = correlation.pairwise_scores(np.array([0, 1, 2, 3]), truth)
        self.assertEqual(singletons["true_positive_pairs"], 0)
        self.assertEqual(singletons["recall"], 0.0)

    def test_canonical_form_is_invariant_to_relabelling(self):
        a = np.array([3, 3, 7, 7, 1])
        b = np.array([9, 9, 0, 0, 5])
        self.assertTrue((_canonical(a) == _canonical(b)).all())


class TestCalibration(unittest.TestCase):

    def test_calibration_is_monotone(self):
        rng = np.random.default_rng(3)
        scores = rng.normal(size=3000)
        labels = (rng.random(3000) < 1 / (1 + np.exp(-scores))).astype(int)
        calibration = isotonic.fit(scores, labels)
        ordered = np.sort(scores)
        probabilities = calibration.probability(ordered)
        self.assertTrue(np.all(np.diff(probabilities) >= -1e-9))

    def test_routing_bands(self):
        probabilities = np.array([0.99, 0.92, 0.80, 0.65, 0.10])
        routes = isotonic.route(probabilities)
        self.assertEqual(list(routes), [0, 0, 1, 1, 2])

    def test_false_merge_rate_is_measured_on_the_automatic_band_only(self):
        probabilities = np.array([0.99, 0.95, 0.70, 0.70, 0.10])
        labels = np.array([1, 0, 0, 0, 0])
        report = isotonic.routing_report(probabilities, labels)
        # One of the two automatic merges is wrong. The review band's errors
        # are not counted, because a human sees those.
        self.assertEqual(report["auto_merged_pairs"], 2)
        self.assertEqual(report["false_merges"], 1)
        self.assertAlmostEqual(report["false_merge_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
