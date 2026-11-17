"""Generator self-checks and the P1 twin checks of
experiments/specs/thermal_single_sensor_consistency.md (protocol v2).

CAL seeds only (410000-410199). FINAL seeds are never touched here.
Run: .venv/bin/python -m unittest tests/test_thermal_generator.py
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments", "generators"))
import thermal as T  # noqa: E402

CAL = range(410000, 410200)
TOL = 1e-9


def maxdiff(a, b):
    return max(abs(x - y) for x, y in zip(a, b))


class Generator(unittest.TestCase):
    def test_assumptions_hold_on_generated_data(self):
        for seed in CAL:
            TA, v = T.ambient(seed), T.noise(seed)
            self.assertTrue(all(T.TA_LO <= x <= T.TA_HI for x in TA))
            self.assertTrue(all(abs(b - a) <= T.RHO_A + 1e-15 for a, b in zip(TA, TA[1:])))
            self.assertTrue(all(abs(x) <= T.DELTA for x in v))
            self.assertTrue(300 <= T.onset(seed) <= 600)

    def test_decomposition_Ts_equals_S_plus_A(self):
        worst = 0.0
        for seed in CAL:
            for arm in T.ARMS:
                P, TA = T.command(seed, arm), T.ambient(seed)
                Ts = T.simulate(P, TA, T.equilibrium(T.P0, TA[0]))
                S, A = T.known_part(P), T.ambient_part(TA)
                worst = max(worst, maxdiff(Ts, [s + a for s, a in zip(S, A)]))
        self.assertLessEqual(worst, TOL, worst)

    def test_ambient_part_inherits_box_and_rate(self):
        for seed in CAL:
            A = T.ambient_part(T.ambient(seed))
            self.assertTrue(all(T.TA_LO - 1e-12 <= a <= T.TA_HI + 1e-12 for a in A))
            self.assertTrue(all(abs(b - a) <= T.RHO_A + 1e-12 for a, b in zip(A, A[1:])))

    def test_paired_design(self):
        """Ambient, noise and onset of a seed do not depend on the cell or the arm."""
        for seed in list(CAL)[:20]:
            r0 = T.run(seed, T.CELLS[0], "E0")
            for cell in T.CELLS:
                for arm in T.ARMS:
                    r = T.run(seed, cell, arm)
                    self.assertEqual(r["TA"], r0["TA"])
                    self.assertEqual(r["v"], r0["v"])
                    self.assertEqual(r["t_f"], r0["t_f"])


class P1Twins(unittest.TestCase):
    def test_offset_equals_ambient_shift_open_loop(self):
        """Corollary 1a: y with offset b under TA == healthy y under TA+b, for every command sequence."""
        worst = 0.0
        rng = random.Random("P1-offsets")
        for seed in CAL:
            for arm in T.ARMS:
                P, TA, v = T.command(seed, arm), T.ambient(seed), T.noise(seed)
                for b in (1.0, 3.0, rng.uniform(-5, 5)):
                    Ts = T.simulate(P, TA, T.equilibrium(T.P0, TA[0]))
                    y = [ts + b + vk for ts, vk in zip(Ts, v)]
                    TA2 = [x + b for x in TA]
                    Ts2 = T.simulate(P, TA2, T.equilibrium(T.P0, TA2[0]))
                    y2 = [ts + vk for ts, vk in zip(Ts2, v)]
                    worst = max(worst, maxdiff(y, y2))
        print(f"\n  P1 offset twin, open loop, {len(CAL)} seeds x 2 arms x 3 offsets: max |y - y_twin| = {worst:.2e}")
        self.assertLessEqual(worst, TOL)

    def test_offset_equals_ambient_shift_closed_loop(self):
        worst = 0.0
        rng = random.Random("P1-closed")
        for seed in CAL:
            TA = T.ambient(seed)
            for b in (1.0, 3.0, rng.uniform(-5, 5)):
                worst = max(worst, _closed_pair(TA, b, seed))
        print(f"  P1 offset twin, closed loop on y, {len(CAL)} seeds x 3 offsets: max |y - y_twin| = {worst:.2e}")
        self.assertLessEqual(worst, TOL)

    def test_stuck_at_equilibrium_under_E0(self):
        """Proposition 3(i): E0, ambient at rest, plant at equilibrium -> stuck == healthy."""
        worst = 0.0
        for seed in CAL:
            ta0 = T.ambient(seed)[0]
            TA = [ta0] * T.N
            P = T.command(seed, "E0")
            Ts = T.simulate(P, TA, T.equilibrium(T.P0, ta0))
            v, t_f = T.noise(seed), T.onset(seed)
            y_stuck = T.sensor(T.Cell("stuck", "stuck", additive=False), Ts, v, t_f)
            y_ok = T.sensor(T.CELLS[0], Ts, v, t_f)
            worst = max(worst, maxdiff(y_stuck, y_ok))
        print(f"  P1 stuck twin (E0, ambient at rest), {len(CAL)} seeds: max |y_stuck - y_healthy| = {worst:.2e}")
        self.assertLessEqual(worst, TOL)


def _closed_pair(TA, b, seed):
    """Faulty (offset b, ambient TA) and twin (healthy, ambient TA+b), closed loop on y, same noise.
    The controller P = clip(P0 + 3*(50 - y)) reads the sensor, so P is not given in advance."""
    v = T.noise(seed)
    def loop(ta_seq, x0, off):
        tc, ts = x0
        out = []
        for k in range(T.N):
            y = ts + off + v[k]
            out.append(y)
            p = min(T.P_HI, max(T.P_LO, T.P0 + 3.0 * (50.0 - y)))
            tc, ts = T.step(tc, ts, p, ta_seq[k])
        return out
    TA2 = [x + b for x in TA]
    return maxdiff(loop(TA, T.equilibrium(T.P0, TA[0]), b), loop(TA2, T.equilibrium(T.P0, TA2[0]), 0.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
