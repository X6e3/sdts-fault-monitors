"""v3 post-freeze fixes (2026-11-22, RECORD-2026-11-22-postfreeze-fixes.md): the known limits of FREEZE-V3.md
section 1 (review M3a), closed in diag3_cw.py after the freeze. No LP is solved here."""
import math
import sys
import unittest
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.optimize import OptimizeResult

ROOT = Path(__file__).resolve().parents[1]
for sub in ("experiments/v3/diag", "experiments/v3", "experiments/machine", "experiments/generators",
            "experiments/oracle", "env"):
    sys.path.insert(0, str(ROOT / sub))
import diag3_cw as C  # noqa: E402

NO_VARS = {"bounds": np.zeros((0, 2))}


def frozen_term(n, xmax):
    """the frozen code's evaluation (exact for the candidate's boxes only)"""
    v = n * (1.0 + 2.0 * xmax)
    return math.ldexp(math.ceil(v), -1074) if math.isfinite(v) else math.inf


class UnderflowTerm(unittest.TestCase):
    def test_same_as_frozen_for_the_candidate(self):
        for xmax in (2.0, 1.0, 0.5):                     # the candidate's boxes have max|x| = 2
            for n in range(1, 14796, 13):
                self.assertEqual(C._underflow_term(NO_VARS, n, xmax), frozen_term(n, xmax))

    def test_counterexample_is_closed(self):
        x = 2.0 ** -54                                   # review M3a: 10 units where 11 are needed
        self.assertEqual(Fraction(frozen_term(10, x)) * 2 ** 1074, 10)
        self.assertEqual(Fraction(C._underflow_term(NO_VARS, 10, x)) * 2 ** 1074, 11)

    def test_upper_bound_for_any_box(self):
        rng = np.random.default_rng(20261122)
        for _ in range(2000):
            n, xmax = int(rng.integers(1, 20000)), float(10.0 ** rng.uniform(-300, 300))
            exact = n * (1 + 2 * Fraction(xmax)) / 2 ** 1074
            self.assertGreaterEqual(Fraction(C._underflow_term(NO_VARS, n, xmax)), exact)

    def test_not_finite(self):
        self.assertEqual(C._underflow_term(NO_VARS, 10, math.inf), math.inf)


class Inputs(unittest.TestCase):
    def test_lp_without_variables_is_our_error(self):
        with self.assertRaises(ValueError):
            C._check_inputs(np.zeros(0), NO_VARS)


class Usable(unittest.TestCase):
    kw = {"bounds": np.zeros((2, 2))}

    def test_missing_fields_fail_the_attempt(self):
        self.assertFalse(C._usable(OptimizeResult(status=0, fun=1.0), self.kw))
        self.assertFalse(C._usable(OptimizeResult(status=0, fun=1.0, lower=OptimizeResult(),
                                                  upper=OptimizeResult(marginals=np.zeros(2))), self.kw))

    def test_well_formed_answer(self):
        m = OptimizeResult(marginals=np.zeros(2))
        self.assertTrue(C._usable(OptimizeResult(status=0, fun=1.0, lower=m, upper=m), self.kw))


if __name__ == "__main__":
    unittest.main()
