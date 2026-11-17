"""v3 template state: exactness of the LP-free support, soundness, monotonicity and dominance over v2.
DEV seeds only (430000-430099)."""
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

ROOT = Path(__file__).resolve().parents[1]
for sub in ("experiments/v3", "experiments/machine", "experiments/generators"):
    sys.path.insert(0, str(ROOT / sub))
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402
from thermal_machine import ThermalMachine  # noqa: E402

T = V.T
CELL = {c.name: c for c in T.CELLS}


def v2_first(y, P):
    m = ThermalMachine()
    for k, (a, b) in enumerate(zip(y, P)):
        if m.observe(a, b):
            return k
    return None


class Support(unittest.TestCase):
    def test_precomputed_bases_give_the_lp_support_and_never_less(self):
        rng = np.random.default_rng(3)
        for kind, kw in (("box+diff", {}), ("inv", {"N": 4}), ("inv+orbit", {"N": 4, "L": 2})):
            D = V.directions(kind, **kw)
            tp = V.Template(D)
            for _ in range(30):
                pts = rng.uniform(-2, 2, (rng.integers(1, 5), 3))
                h = (D @ pts.T).max(axis=1) + rng.uniform(0, 0.5, len(D)) * (rng.uniform(size=len(D)) < 0.4)
                g = rng.normal(size=3)
                exact = -linprog(-g, A_ub=D, b_ub=h, bounds=[(None, None)] * 3, method="highs").fun
                ours = tp.support(h, V._bases(D, g))
                self.assertGreaterEqual(ours, exact - 1e-12)
                self.assertLess(ours - exact, 1e-9)

    def test_any_subset_of_bases_is_still_an_upper_bound(self):
        D = V.directions("inv", N=4)
        tp = V.Template(D)
        rng = np.random.default_rng(4)
        pts = rng.uniform(-2, 2, (3, 3))
        h = (D @ pts.T).max(axis=1)
        g = rng.normal(size=3)
        full = V._bases(D, g)
        half = tuple(x[::2] for x in full)
        self.assertGreaterEqual(tp.support(h, half), tp.support(h, full))

    def test_reachable_set_recovers_the_v2_rate_lemma(self):
        v = V.M.T @ V.E[1] - V.E[1]                          # as[k+1] - as[k] = v . s
        self.assertAlmostEqual(V.invariant_support(v[:2]), T.RHO_A, places=12)
        self.assertAlmostEqual(V.invariant_support(-v[:2]), T.RHO_A, places=12)


class Machine(unittest.TestCase):
    TEMPLATES = None

    @classmethod
    def setUpClass(cls):
        cls.TEMPLATES = {"box+diff": V.Template(V.directions("box+diff")),
                         "inv4+I": V.Template(V.directions("inv", N=4), invariant=True),
                         "inv8+I": V.Template(V.directions("inv", N=8), invariant=True)}

    def test_healthy_dev_runs_are_never_flagged_even_at_the_noise_edge(self):
        for seed in (430010, 430011):
            for arm in T.ARMS:
                for al in ("rw", "ramp"):
                    for nl in ("uniform", "edge"):
                        r = S.run(seed, CELL["healthy"], arm, al, nl)
                        for name, tp in self.TEMPLATES.items():
                            self.assertIsNone(V.first_inconsistent(tp, r["y"], r["P"]), (seed, arm, al, nl, name))

    def test_a_step_the_plant_can_not_make_is_flagged_at_once(self):
        tp = self.TEMPLATES["inv4+I"]
        y = [50.0] * 50 + [52.0] * 5
        self.assertEqual(V.first_inconsistent(tp, y, [T.P0] * len(y)), 50)

    def test_more_directions_never_detect_later(self):
        small, big = self.TEMPLATES["inv4+I"], self.TEMPLATES["inv8+I"]
        for cell in ("drift_0.002", "jump_0.2"):
            for seed in (430012, 430013):
                r = S.run(seed, CELL[cell], "E0")
                a, b = V.first_inconsistent(small, r["y"], r["P"]), V.first_inconsistent(big, r["y"], r["P"])
                self.assertTrue(b is not None and (a is None or b <= a), (cell, seed, a, b))

    def test_clamped_template_never_detects_later_than_v2(self):
        tp = self.TEMPLATES["inv4+I"]
        for cell in ("drift_0.002", "drift_0.005", "jump_0.2", "noise_x2"):
            for seed in (430014, 430015):
                for arm in T.ARMS:
                    r = S.run(seed, CELL[cell], arm)
                    t, v2 = V.first_inconsistent(tp, r["y"], r["P"]), v2_first(r["y"], r["P"])
                    self.assertTrue(v2 is None or (t is not None and t <= v2), (cell, seed, arm, t, v2))


class Scenarios(unittest.TestCase):
    def test_dev_scenarios_respect_the_assumptions_and_refuse_other_seeds(self):
        for law in ("rw", "ramp"):
            ta = S.ambient(430020, law)
            self.assertTrue(all(T.TA_LO <= x <= T.TA_HI for x in ta))
            self.assertTrue(all(abs(b - a) <= T.RHO_A + 1e-15 for a, b in zip(ta, ta[1:])))
        self.assertTrue(all(abs(v) <= T.DELTA for v in S.noise(430020, "edge")))
        for seed in (410000, 420000, 440000):
            with self.assertRaises(ValueError):
                S.ambient(seed, "rw")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class Pruning(unittest.TestCase):
    def test_pruned_tables_stay_sound_and_never_detect_earlier_than_the_full_tables(self):
        full = V.Template(V.directions("inv", N=4), invariant=True)
        sel = [(r["y"], r["P"]) for r in (S.run(430090, CELL[c], "E0") for c in ("healthy", "drift_0.002", "jump_0.2"))]
        tiny = V.pruned(full, V.usage(full, sel), keep_top=1)
        self.assertLess(tiny.table_entries, full.table_entries)
        for cell in ("healthy", "drift_0.002", "drift_0.005", "jump_0.5"):
            for arm in T.ARMS:
                r = S.run(430091, CELL[cell], arm, "ramp", "edge" if cell == "healthy" else "uniform")
                a, b = V.first_inconsistent(full, r["y"], r["P"]), V.first_inconsistent(tiny, r["y"], r["P"])
                if cell == "healthy":
                    self.assertIsNone(b)
                else:
                    self.assertTrue(b is None or (a is not None and b >= a), (cell, arm, a, b))
