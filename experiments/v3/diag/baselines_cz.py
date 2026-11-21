"""BASELINE-PLAN.md, B1: constrained zonotopes (Scott, Raimondo, Marseglia, Braatz 2016), with the prior of
baselines.py.

A constrained zonotope is Z = {c + G xi : |xi|_inf <= 1, A xi = b}.
- prediction: c <- M c, G <- [M G, rho e3], A <- [A, 0] (exact);
- a strip {x : |p . x - y| <= s} or a box side: the generalized intersection with an interval, one generator and one
  constraint more (exact; Scott, Prop. 1);
- the alarm test at t: the range of x_2 over the predicted set (boxes included), by two LPs (Scott, Prop. 2's
  emptiness test, in the form the decision needs); an infeasible LP is an empty set, so an alarm;
- complexity control, after each update:
  1. rescaling: the bounds of xi implied by the constraints (interval propagation), then xi reparametrized to
     [-1, 1] (exact: the set does not change);
  2. constraint elimination down to n_c constraints: a constraint row i solved for xi_j and xi_j's box dropped.
     Dropping a constraint can only enlarge the set, so this is always an outer approximation; it is exact when the
     range of xi_j implied by row i lies in [-1, 1]. The pair (i, j) is the one with the smallest overshoot of that
     range beyond [-1, 1] times |g_j| (a proxy of the error bound of Scott section 4.2; our implementation);
  3. generator reduction: Girard's method on the lifted zonotope {(c, -b) + [G; A] xi} down to 3 o + n_c generators
     (an outer approximation in the lifted space is one of the constrained zonotope).
Plain binary64, scipy's HiGHS dual simplex; no outward rounding (as published).
"""
import math
import time

import numpy as np
from scipy.optimize import linprog

import baselines as BL

MX, SIG, RHO, HI, P2, E3, EYE = BL.MX, BL.SIG, BL.RHO, BL.HI, BL.P2, BL.E3, BL.EYE
TOL = 1e-12


class ConZono:
    def __init__(self, n_c, order, policy="fifo", prior="box+err"):
        self.n_c, self.order, self.policy, self.prior = n_c, order, policy, prior
        self.t, self.age = 0, np.zeros(0)
        self.ng_max = 3 * order + n_c
        self.c, self.G = np.zeros(3), np.full((3, 1), HI)
        self.A, self.b = np.zeros((0, 1)), np.zeros(0)
        self.n_lp, self.lp_fail, self.max_gen, self.max_con = 0, 0, 1, 0

    def memory(self):
        ng, nc = self.ng_max, self.n_c
        return 3 + 3 * ng + nc * (ng + 1)

    # ---- the range of p . x ------------------------------------------------------------------------------------
    def _hull(self, p):
        return BL.span(self.c, self.G, p)

    def range(self, p):
        """(lo, hi) of p . x over Z, or None if Z is empty"""
        if self.A.shape[0] == 0:
            return self._hull(p)
        f = self.G.T @ p
        out = []
        for s in (1.0, -1.0):
            self.n_lp += 1
            r = linprog(s * f, A_eq=self.A, b_eq=self.b, bounds=(-1, 1), method="highs-ds")
            if r.status == 2:
                return None
            if r.status != 0:
                self.lp_fail += 1
                return self._hull(p)                  # cannot use the LP: the unconstrained hull is still outer
            out.append(s * r.fun)                     # min of f . xi, then max of f . xi
        m = float(p @ self.c)
        return m + out[0], m + out[1]

    # ---- exact operations ------------------------------------------------------------------------------------------
    def _intersect_strip(self, p, y, s):
        ng = self.G.shape[1]
        self.G = np.hstack([self.G, np.zeros((3, 1))])
        self.A = np.vstack([np.hstack([self.A, np.zeros((self.A.shape[0], 1))]),
                            np.hstack([p @ self.G[:, :ng], [-s]])[None, :]])
        self.b = np.append(self.b, y - p @ self.c)
        self.age = np.append(self.age, self.t)

    def predict(self):
        self.t += 1
        self.c = MX @ self.c
        self.G = np.hstack([MX @ self.G, (RHO * E3)[:, None]])
        self.A = np.hstack([self.A, np.zeros((self.A.shape[0], 1))])
        for q, beta in BL.PRIORS[self.prior]:         # the boxes (and reachable-set bounds), where the set sticks out
            lo, hi = self._hull(q)
            if lo < -beta or hi > beta:
                self._intersect_strip(q, 0.0, beta)
        self.max_con = max(self.max_con, self.A.shape[0])

    # ---- reduction -----------------------------------------------------------------------------------------------
    def _rescale(self, sweeps=3):
        A, b = self.A, self.b
        ng = self.G.shape[1]
        lo, hi = -np.ones(ng), np.ones(ng)
        absA = np.abs(A)
        nz = absA > TOL
        for _ in range(sweeps):
            for i in range(A.shape[0]):
                row, idx = A[i], np.nonzero(nz[i])[0]
                if idx.size == 0:
                    continue
                r = row[idx]
                tlo, thi = np.minimum(r * lo[idx], r * hi[idx]), np.maximum(r * lo[idx], r * hi[idx])
                slo, shi = tlo.sum(), thi.sum()
                rest_lo, rest_hi = slo - tlo, shi - thi            # the row without each term
                a1, a2 = (b[i] - rest_hi) / r, (b[i] - rest_lo) / r
                lo[idx] = np.maximum(lo[idx], np.minimum(a1, a2))
                hi[idx] = np.minimum(hi[idx], np.maximum(a1, a2))
        if np.any(lo > hi + 1e-9):
            return                                    # numerically empty: leave the set as it is (the LP decides)
        hi = np.maximum(hi, lo)
        m, r = (hi + lo) / 2, (hi - lo) / 2
        self.c = self.c + self.G @ m
        self.b = self.b - self.A @ m
        self.G = self.G * r
        self.A = self.A * r
        keep = r > TOL                                # a fixed xi has no column left
        self.G, self.A = self.G[:, keep], self.A[:, keep]

    def _eliminate_one(self):
        A, b, Gm = self.A, self.b, self.G
        absA = np.abs(A)
        ok = absA > 1e-9
        zero = ~ok.any(axis=1)
        if zero.any():                                # a row 0 = b_i: satisfied (drop it) or the set is empty
            if np.any(np.abs(b[zero]) > 1e-9):
                self.empty = True
            keep = ~zero
            self.A, self.b, self.age = A[keep], b[keep], self.age[keep]
            return
        with np.errstate(divide="ignore", invalid="ignore"):
            rad = (absA.sum(axis=1)[:, None] - absA) / absA
            over = np.maximum(0.0, np.abs(b[:, None] / A) + rad - 1.0)
        gn = np.linalg.norm(Gm, axis=0)[None, :] * np.ones_like(A)
        # a variable with no generator (a strip's own variable) is eliminated last unless that is exact: solving the
        # row for it and dropping its box would drop the whole constraint
        bad = (gn <= TOL) & (over > 0)
        score = np.where(ok, over * gn, np.inf)
        score = np.where(bad, np.inf, score)
        if not np.isfinite(score).any():
            score = np.where(ok, over, np.inf)
        exact = ok & (over <= 0)
        if exact.any():                               # an exact elimination first (a redundant box, ...)
            score = np.where(exact, gn, np.inf)
        elif self.policy == "fifo":                    # else the oldest constraint, the best variable in it
            oldest = self.age == self.age.min()
            score = np.where(oldest[:, None], score, np.inf)
            if not np.isfinite(score).any():
                score = np.where(oldest[:, None] & ok, over, np.inf)
        flat = np.argmin(score)
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

    def _reduce_generators(self):
        nc = self.A.shape[0]
        if self.G.shape[1] <= self.ng_max:
            return
        L = np.vstack([self.G, self.A])               # the lifted generators; the lifted centre (c, -b) is kept
        d = L.shape[0]
        k = L.shape[1] - (self.ng_max - d)            # boxed into d generators
        score = np.abs(L).sum(axis=0) - np.abs(L).max(axis=0)
        idx = np.argsort(score, kind="stable")
        L = np.hstack([L[:, idx[k:]], np.diag(np.abs(L[:, idx[:k]]).sum(axis=1))])
        self.G, self.A = L[:3], L[3:3 + nc]

    def reduce(self):
        self._rescale()
        while self.A.shape[0] > self.n_c:
            self._eliminate_one()
        self._reduce_generators()
        self.max_gen = max(self.max_gen, self.G.shape[1])

    # ---- the online step -------------------------------------------------------------------------------------------
    def check_and_update(self, z):
        if getattr(self, "empty", False):
            return True
        rg = self.range(P2)
        if rg is None or BL.misses(rg[0], rg[1], z):
            return True
        self._intersect_strip(P2, z, SIG)
        self.max_con = max(self.max_con, self.A.shape[0])
        self.reduce()
        return False

    def contains_hull(self, x):
        for i in range(3):
            rg = self.range(EYE[i])
            if rg is None or not rg[0] - 1e-9 <= x[i] <= rg[1] + 1e-9:
                return False
        return True


BL.METHODS["B1"] = lambda cfg: ConZono(cfg["n_c"], cfg["order"], cfg.get("policy", "fifo"), cfg.get("prior", "box+err"))
