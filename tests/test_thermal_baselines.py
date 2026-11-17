"""Checks for the score adapters, reference identity and evaluation mask."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments" / "baselines"))
import thermal_baselines as B


class Baselines(unittest.TestCase):
    def test_reference_and_finite_input(self):
        self.assertEqual(B.verify_reference(), B.CORE_SHA256)
        with self.assertRaises(ValueError):
            B.dmreda_score([40.0, float("nan")])

    def test_two_sided_cusum_on_first_differences(self):
        score = B.cusum_score([0.0, 1.0, 2.0, 1.0, 0.0], allowance=0.25)
        np.testing.assert_allclose(score.values, [0.0, 0.75, 1.5, 0.75, 1.5])

    def test_threshold_uses_only_eligible_scores(self):
        trace = B.ScoreTrace(np.array([99.0, 1.0, 2.0]), 1)
        self.assertEqual(B.training_threshold([trace]), 2.1)
        self.assertIsNone(B.first_alarm(trace, 2.0))
        self.assertEqual(B.first_alarm(trace, 1.5), 2)


class AddendumA1(unittest.TestCase):
    def test_scaled_profiles_change_only_the_four_threshold_levels(self):
        base, doubled = B.core.DEFAULT_PROFILES, B.scaled_profiles(2.0)
        self.assertEqual(B.scaled_profiles(1.0), base)
        for i, p in base.items():
            q = doubled[i]
            for name in ("th_d", "th_g", "th_d2", "th_a"):
                self.assertEqual(getattr(q, name), 2.0 * getattr(p, name))
            others = {f.name for f in B.dataclasses.fields(p)} - {"th_d", "th_g", "th_d2", "th_a"}
            self.assertEqual({n: getattr(q, n) for n in others}, {n: getattr(p, n) for n in others})

    def test_native_statistic_is_the_edge_of_the_event_set(self):
        rng = np.random.default_rng(7)
        y = 50 + 0.1 * rng.uniform(-1, 1, 1500)
        y[900:960] += 0.6 * rng.uniform(-1, 1, 60)          # a burst of extra variability
        s = B.native_statistic(y)
        self.assertGreater(s, 0)
        self.assertTrue(B._has_event(y, s))
        self.assertFalse(B._has_event(y, s * 1.001))

    def test_outcome_counts_pre_onset_and_flagged_separately(self):
        y = np.concatenate((np.zeros(400), np.ones(200), np.zeros(100), 3.0 * np.ones(300)))
        # cusum a=0: score 1 from 400 (S+ after the rise), 1 from 600 (S- after the fall), 3 from 700
        out = B.outcome("cusum_a0", y, 2.0, t_f=650)
        self.assertEqual((out["first_alarm"], out["pre_onset_alarm"], out["flagged"]), (700, False, True))
        out = B.outcome("cusum_a0", y, 0.5, t_f=650)
        self.assertEqual((out["first_alarm"], out["pre_onset_alarm"], out["flagged"]), (400, True, True))
