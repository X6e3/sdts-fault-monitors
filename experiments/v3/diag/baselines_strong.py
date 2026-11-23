"""BASELINE2-PLAN.md: two strengthened baselines, as subclasses; the frozen baselines.py and baselines_cz.py are
unchanged, and B1/B4 behave exactly as before.

B1s: B1 (constrained zonotopes) with each equality row of (A, b) scaled to unit infinity norm before the lifted
     generator reduction. Row scaling leaves the set {c + G xi : A xi = b, |xi| <= 1} unchanged; it only puts the
     constraint rows of the lifted matrix [G; A] on one scale for the Girard score (review r2, 2026-11-23).
B4s: B4 (interval observer in cooperative form) with its as-range intersected with the measurement slab
     [z - SIG, z + SIG] after each check, as the interval monitor IM does.
Both run in plain binary64, like B1 to B4.
"""
import numpy as np

import baselines as BL
import baselines_cz as CZ


class ConZonoScaled(CZ.ConZono):
    def _reduce_generators(self):
        if self.A.shape[0]:
            s = np.max(np.abs(self.A), axis=1)
            s = np.where(s > 0, s, 1.0)
            self.A, self.b = self.A / s[:, None], self.b / s
        super()._reduce_generators()


class IntervalObserverMeas(BL.IntervalObserver):
    def check_and_update(self, z):
        if super().check_and_update(z):
            return True
        self.lo[1], self.hi[1] = max(self.lo[1], z - BL.SIG), min(self.hi[1], z + BL.SIG)
        return False


BL.METHODS["B1s"] = lambda cfg: ConZonoScaled(cfg["n_c"], cfg["order"], cfg.get("policy", "fifo"),
                                               cfg.get("prior", "box+err"), cfg.get("rescale", "interval"))
BL.METHODS["B4s"] = lambda cfg: IntervalObserverMeas(cfg["L"])
