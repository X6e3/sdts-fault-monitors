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
