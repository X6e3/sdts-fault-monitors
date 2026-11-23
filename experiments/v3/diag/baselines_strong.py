"""BASELINE2-PLAN.md: strengthened baselines, as subclasses; the frozen baselines.py and baselines_cz.py are unchanged,
and B1/B4 behave exactly as before.

B1s: B1 (constrained zonotopes, Scott et al. 2016) made stable and given its own fixes (reviews r2 and r3,
     2026-11-23). Review r3 found B1 chaotic: a 1e-15 shift of the data moves its first detection between 635, 1101,
     2247 and 2258, and Mac and Arch disagree. B1s changes only discrete choices and their tolerances:
     - each equality row of (A, b) whose largest coefficient is at least ROW_TOL is scaled to unit infinity norm
       before the lifted generator reduction (the set is unchanged);
     - an elimination counts as exact when its over-approximation is at most EXACT_TOL (B1: exactly 0);
     - Girard scores and elimination scores are rounded to SCORE_TOL before sorting, so near-ties go by index;
     - a prior strip is added only when the hull sticks out by more than PRIOR_TOL;
     - the interval rescaling uses every nonzero coefficient (B1 ignores those below 1e-12, which can lose the
       outer property).
     Every choice it makes is still an outer approximation. The grid has the greedy policy as well as fifo.
B4s: B4 (interval observer in cooperative form) with three outer tightenings after every step:
     - its as-range is intersected with the measurement slab [z - SIG, z + SIG], as IM does;
     - the prior (boxes, and the reachable-set bounds of Lemma 1 including the as-velocity plane) is applied by
       interval propagation, as B1 to B3 receive it with "box+err";
     - IM's rate rule: as at k+1 lies within RHO of the as-range at k.
     By the last two its as-range never contains more than IM's interval, so it is never later than IM (unit test).
All run in plain binary64, like B1 to B4.
"""
import numpy as np

import baselines as BL
import baselines_cz as CZ

ROW_TOL = 1e-9
PRIOR_TOL = 1e-9
EXACT_TOL = 1e-12
SCORE_TOL = 1e-10


class ConZonoStrong(CZ.ConZono):
    """B1 with row scaling, every nonzero coefficient in the rescaling, and tolerances that keep 1-ulp differences
    from switching its discrete choices (review r3: B1 flips between 635, 1101, 2247 and 2258 under a 1e-15 shift)."""

    def predict(self):                                # B1's predict, with a prior strip only beyond PRIOR_TOL
        self.t += 1
        self.c = CZ.MX @ self.c
        self.G = np.hstack([CZ.MX @ self.G, (CZ.RHO * CZ.E3)[:, None]])
        self.A = np.hstack([self.A, np.zeros((self.A.shape[0], 1))])
        for q, beta in BL.PRIORS[self.prior]:
            lo, hi = self._hull(q)
            if lo < -beta - PRIOR_TOL or hi > beta + PRIOR_TOL:
                self._intersect_strip(q, 0.0, beta)
        self.max_con = max(self.max_con, self.A.shape[0])

    def _eliminate_one(self):                         # B1's, with "exact" meaning over <= EXACT_TOL
        A, b, Gm = self.A, self.b, self.G
        absA = np.abs(A)
        ok = absA > 1e-9
        zero = ~ok.any(axis=1)
        if zero.any():
            if np.any(np.abs(b[zero]) > 1e-9):
                self.empty = True
            keep = ~zero
            self.A, self.b, self.age = A[keep], b[keep], self.age[keep]
            return
        with np.errstate(divide="ignore", invalid="ignore"):
            rad = (absA.sum(axis=1)[:, None] - absA) / absA
            over = np.maximum(0.0, np.abs(b[:, None] / A) + rad - 1.0)
        gn = np.linalg.norm(Gm, axis=0)[None, :] * np.ones_like(A)
        bad = (gn <= CZ.TOL) & (over > EXACT_TOL)
        score = np.where(ok, over * gn, np.inf)
        score = np.where(bad, np.inf, score)
        if not np.isfinite(score).any():
            score = np.where(ok, over, np.inf)
        exact = ok & (over <= EXACT_TOL)
        if exact.any():
            score = np.where(exact, gn, np.inf)
        elif self.policy == "fifo":
            oldest = self.age == self.age.min()
            score = np.where(oldest[:, None], score, np.inf)
            if not np.isfinite(score).any():
                score = np.where(oldest[:, None] & ok, over, np.inf)
        flat = np.argmin(_quantize(score))
        i, j = np.unravel_index(flat, A.shape)
        aij = A[i, j]
        g = Gm[:, j] / aij
        self.c = self.c + g * b[i]
        Gn = Gm - np.outer(g, A[i])
        an = A[:, j] / aij
        An = A - np.outer(an, A[i])
        bn = b - an * b[i]
        keep_r = np.arange(A.shape[0]) != i
        keep_c = np.arange(A.shape[1]) != j
        self.G, self.A, self.b = Gn[:, keep_c], An[np.ix_(keep_r, keep_c)], bn[keep_r]
        self.age = self.age[keep_r]

    def _reduce_generators(self):                     # row scaling, then B1's lifted Girard with quantized scores
        if self.A.shape[0]:
            s = np.max(np.abs(self.A), axis=1)
            s = np.where(s >= ROW_TOL, s, 1.0)
            self.A, self.b = self.A / s[:, None], self.b / s
        nc = self.A.shape[0]
        if self.G.shape[1] <= self.ng_max:
            return
        L = np.vstack([self.G, self.A])
        d = L.shape[0]
        k = L.shape[1] - (self.ng_max - d)
        score = np.abs(L).sum(axis=0) - np.abs(L).max(axis=0)
        idx = np.argsort(_quantize(score), kind="stable")
        L = np.hstack([L[:, idx[k:]], np.diag(np.abs(L[:, idx[:k]]).sum(axis=1))])
        self.G, self.A = L[:3], L[3:3 + nc]

    def _rescale(self, sweeps=3):
        tol, CZ.TOL = CZ.TOL, 0.0                     # every nonzero coefficient enters the propagation
        try:
            super()._rescale(sweeps)
        finally:
            CZ.TOL = tol


def _quantize(x):
    """scores rounded to a grid of SCORE_TOL, so that near-ties are broken by index, not by the last bits"""
    with np.errstate(invalid="ignore"):
        return np.where(np.isfinite(x), np.round(x / SCORE_TOL) * SCORE_TOL, x)


def _propagate(lo, hi, q, beta, sweeps=2):
    """tighten the box [lo, hi] by |q . x| <= beta (interval propagation; outer)"""
    idx = np.nonzero(q)[0]
    for _ in range(sweeps):
        t_lo, t_hi = np.minimum(q[idx] * lo[idx], q[idx] * hi[idx]), np.maximum(q[idx] * lo[idx], q[idx] * hi[idx])
        s_lo, s_hi = t_lo.sum(), t_hi.sum()
        for n, i in enumerate(idx):
            rest_lo, rest_hi = s_lo - t_lo[n], s_hi - t_hi[n]
            a1, a2 = (-beta - rest_hi) / q[i], (beta - rest_lo) / q[i]
            lo[i], hi[i] = max(lo[i], min(a1, a2)), min(hi[i], max(a1, a2))
    return lo, hi


class IntervalObserverStrong(BL.IntervalObserver):
    def _prior(self):
        for q, beta in BL.PRIORS["box+err"]:
            self.lo, self.hi = _propagate(self.lo, self.hi, np.asarray(q, dtype=float), beta)

    def check_and_update(self, z):
        if super().check_and_update(z):
            return True
        self.lo[1], self.hi[1] = max(self.lo[1], z - BL.SIG), min(self.hi[1], z + BL.SIG)
        self._prior()
        return bool(np.any(self.lo > self.hi))

    def predict(self):
        as_lo, as_hi = self.lo[1], self.hi[1]
        super().predict()
        self.lo[1], self.hi[1] = max(self.lo[1], as_lo - BL.RHO), min(self.hi[1], as_hi + BL.RHO)
        self._prior()


BL.METHODS["B1s"] = lambda cfg: ConZonoStrong(cfg["n_c"], cfg["order"], cfg.get("policy", "fifo"),
                                               cfg.get("prior", "box+err"), cfg.get("rescale", "interval"))
BL.METHODS["B4s"] = lambda cfg: IntervalObserverStrong(cfg["L"])
