"""BASELINE-PLAN.md: the baselines and the v3 trackers on one run, with the same prior and the same decision.

The prior (FREEZE-V3 section 1, as F3 has it): the exact recurrence of thermal.py (each matrix entry rounded once),
the slab delta + eta, the ambient rate rho_A, the box [LO, HI] for TA and the implied boxes for ac and as, the start
segment {t (1, 1, 1) : t in [LO, HI]}. The decision: an alarm at the first sample t at which the method shows that
the measurement z_t cannot be explained; the set used for z_t holds the measurements up to t - 1 only.

Methods (BASELINE-PLAN.md section 3):
  B2  strip-intersection zonotope (Alamo, Bravo, Camacho 2005), the intersection weight minimizing the F-radius,
      Girard's order reduction; the boxes enter as virtual strips at every sample
  B3  zonotopic observer with a constant gain (predictor form, Combastel 2015): the gain is the steady-state Kalman
      gain for a process-to-measurement weight q; the boxes as in B2. (With the gain re-optimized at every sample
      for the F-radius it would equal B2, which is Combastel's own result; the constant gain is the cheap variant.)
  B4  interval observer: A - L C nonnegative (cooperative), interval bounds, clamped to the boxes
  B5  F3 with the smoothing fold off: the base of the window is folded from the measurements up to the base only
      (forward filtering, the Kesavan and Lee style); everything else is F3's
  cyl16p  freeze 1's template state (template_state.TemplateMachine, as validated)
B1 (constrained zonotopes) is in baselines_cz.py.
B2-B4 run in plain binary64, as published, with no outward rounding.
"""
import math
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import diag3_cw as C  # noqa: E402
import diag3_cw_dev as CD  # noqa: E402

G, S, T, V = C.G, C.S, C.T, C.V
MX = np.array([[float(x) for x in r] for r in C.MX])   # the exact recurrence, each entry rounded once
SIG = C.DELTA_F                                         # delta + eta
RHO = T.RHO_A
LO, HI = V.LO, V.HI
assert LO == -HI
P2 = np.array([0.0, 1.0, 0.0])
E3 = np.array([0.0, 0.0, 1.0])
EYE = np.eye(3)
N = T.N


# ---- zonotopes ----------------------------------------------------------------------------------------------------
def girard(Gm, order):
    """Girard's reduction to at most order * n generators."""
    n, m = Gm.shape
    if m <= order * n:
        return Gm
    k = m - n * (order - 1)
    score = np.abs(Gm).sum(axis=0) - np.abs(Gm).max(axis=0)
    idx = np.argsort(score, kind="stable")
    return np.hstack([Gm[:, idx[k:]], np.diag(np.abs(Gm[:, idx[:k]]).sum(axis=1))])


def span(c, Gm, p):
    """the interval of p . x over the zonotope"""
    r = float(np.abs(Gm.T @ p).sum())
    m = float(p @ c)
    return m - r, m + r


def strip(c, Gm, p, y, sig):
    """the zonotope intersected with {x : |p . x - y| <= sig}, outer, the weight minimizing the F-radius"""
    gp = Gm.T @ p
    lam = (Gm @ gp) / (gp @ gp + sig * sig)
    return c + lam * (y - p @ c), np.hstack([Gm - np.outer(lam, gp), (sig * lam)[:, None]])


# the reachable-set bounds of Lemma 2 (V3_NOTES section 4) in four error-plane directions: ac - TA, as - TA, ac - as
# and the as-velocity v = M' e2 - e2 (|v . s| <= rho_A); with the boxes they are the prior every method gets
_V = MX[1] - P2
ERR_DIRS = [np.array([1.0, 0.0, -1.0]), np.array([0.0, 1.0, -1.0]), np.array([1.0, -1.0, 0.0]), _V]
ERR_BOUNDS = [V.invariant_support(q[:2]) for q in ERR_DIRS]
PRIORS = {"box": [(EYE[i], HI) for i in range(3)]}
PRIORS["box+err"] = PRIORS["box"] + list(zip(ERR_DIRS, ERR_BOUNDS))
PRIOR = PRIORS["box+err"]


def boxes(c, Gm, prior="box+err"):
    """the prior (boxes, and the reachable-set bounds with "box+err") as virtual strips, where the set sticks out.
    Both are given in the DEV tuning grid: an outer intersection with a thin strip can widen other directions."""
    for q, beta in PRIORS[prior]:
        lo, hi = span(c, Gm, q)
        if lo < -beta or hi > beta:
            c, Gm = strip(c, Gm, q, 0.0, beta)
    return c, Gm


def misses(lo, hi, z):
    return hi < z - SIG or lo > z + SIG


class StripZonotope:
    """B2"""

    def __init__(self, order, prior="box+err"):
        self.order, self.prior = order, prior
        self.c, self.G = np.zeros(3), np.full((3, 1), HI)          # the start segment
        self.max_gen = 1

    def memory(self):
        return 3 + 3 * 3 * self.order

    def check_and_update(self, z):
        if misses(*span(self.c, self.G, P2), z):
            return True
        self.c, self.G = strip(self.c, self.G, P2, z, SIG)
        self.G = girard(self.G, self.order)
        self.max_gen = max(self.max_gen, self.G.shape[1])
        return False

    def predict(self):
        self.c = MX @ self.c
        self.G = np.hstack([MX @ self.G, (RHO * E3)[:, None]])
        self.c, self.G = boxes(self.c, self.G, self.prior)

    def contains_hull(self, x):
        return all(span(self.c, self.G, EYE[i])[0] - 1e-9 <= x[i] <= span(self.c, self.G, EYE[i])[1] + 1e-9
                   for i in range(3))


def kalman_gain(q, iters=20000):
    """steady-state predictor gain for x' = MX x + e3 w, y = x_2 + v, weights Q = q rho^2 e3 e3', R = sig^2"""
    Q = q * RHO * RHO * np.outer(E3, E3)
    R = SIG * SIG
    Pm = np.eye(3)
    for _ in range(iters):
        K = MX @ Pm @ P2 / (P2 @ Pm @ P2 + R)
        Pn = MX @ Pm @ MX.T - np.outer(K, P2 @ Pm @ MX.T) + Q
        if np.max(np.abs(Pn - Pm)) < 1e-18:
            Pm = Pn
            break
        Pm = Pn
    return MX @ Pm @ P2 / (P2 @ Pm @ P2 + R)


class GainObserver:
    """B3: Z_{t+1} = (MX - L p') Z_t + L [y_t +- sig] + rho e3 [-1, 1], then the boxes and the reduction"""

    def __init__(self, q, order, prior="box+err"):
        self.q, self.order, self.prior = q, order, prior
        self.L = kalman_gain(q)
        self.A = MX - np.outer(self.L, P2)
        self.c, self.G = np.zeros(3), np.full((3, 1), HI)
        self.max_gen = 1
        self.pending = None

    def memory(self):
        return 3 + 3 * 3 * self.order

    def check_and_update(self, z):
        if misses(*span(self.c, self.G, P2), z):
            return True
        self.pending = z
        return False

    def predict(self):
        z = self.pending
        self.c = self.A @ self.c + self.L * z
        self.G = np.hstack([self.A @ self.G, (SIG * self.L)[:, None], (RHO * E3)[:, None]])
        self.c, self.G = boxes(self.c, self.G, self.prior)
        self.G = girard(self.G, self.order)
        self.max_gen = max(self.max_gen, self.G.shape[1])

    def contains_hull(self, x):
        return StripZonotope.contains_hull(self, x)


class IntervalObserver:
    """B4: A = MX - L p' >= 0; x+ = A x+ + L y + |L| sig + rho e3, x- likewise, clamped to the boxes"""

    def __init__(self, L):
        self.L = np.asarray(L, dtype=float)
        self.A = MX - np.outer(self.L, P2)
        if (self.A < 0).any():
            raise ValueError("A - L C is not nonnegative")
        self.lo, self.hi = np.full(3, LO), np.full(3, HI)              # the hull of the start segment
        self.pending = None
        self.max_gen = 0

    def memory(self):
        return 6

    def check_and_update(self, z):
        if misses(self.lo[1], self.hi[1], z):
            return True
        self.pending = z
        return False

    def predict(self):
        z, aL = self.pending, np.abs(self.L) * SIG
        self.hi = np.minimum(self.A @ self.hi + self.L * z + aL + RHO * E3, HI)
        self.lo = np.maximum(self.A @ self.lo + self.L * z - aL - RHO * E3, LO)

    def contains_hull(self, x):
        return bool(np.all(self.lo - 1e-9 <= x) and np.all(x <= self.hi + 1e-9))


def run_set_method(m, zs, truth=None, horizon=None):
    """B2-B4 online: z_0 against the start, then predict, check, update. Returns (detect, seconds, truth_out)."""
    last = len(zs) - 1 if horizon is None else min(len(zs) - 1, horizon)
    t0, out = time.monotonic(), []
    if m.check_and_update(zs[0]):
        return 0, time.monotonic() - t0, out
    for t in range(1, last + 1):
        m.predict()
        if truth is not None and not m.contains_hull(truth[t]):
            out.append(t)
        if m.check_and_update(zs[t]):
            return t, time.monotonic() - t0, out
    return None, time.monotonic() - t0, out


# ---- B5: F3 with the smoothing fold off -----------------------------------------------------------------------------
class Forward(C.Failsafe):
    """F3's Failsafe with the fold's LP over the measurements up to the new base only (no smoothing)"""

    def fold(self, t):
        tau2 = self.tau + C.B
        n = len(self.D)
        vals, failed = np.full(n, np.inf), []
        for i, d in enumerate(self.D):
            self.role = ("fold", i)
            v, cub = self.lp_cert(tau2, tau2, tau2, d)               # F3: lp_cert(t, t, tau2, d)
            if isinstance(v, C.Failed):
                self._count("fold_dir_fallbacks", v)
                failed.append(i)
                continue
            if cub > v + C.PAD:
                self.n_short += 1
                self.max_short = max(self.max_short, cub - v - C.PAD)
            vals[i] = max(v + C.PAD, cub)
        if len(failed) == n:
            self.fs["fold_full_resets"] += 1
            self.tau, self.base = tau2, self.tp.clamp(np.full(n, np.inf))
            self.zs, self.last_active = {}, {}
            return
        if not failed:
            self.tau, self.base = tau2, self.tp.clamp(vals)
        else:
            h = self.tp.clamp(vals)
            J = [j for j in range(n) if j not in failed]
            for i in failed:
                b = self.implied(i, J, h)
                if b is not None:
                    self.fs["fold_implied"] += 1
                    h[i] = min(h[i], b)
            self.tau, self.base = tau2, self.tp.clamp(h)
        self.zs = {j: z for j, z in self.zs.items() if j >= tau2}
        self.last_active = {j: a for j, a in self.last_active.items() if j in self.zs}


_make = C.make


def _make_with_b5(var, cy):
    return Forward(cy) if var == "B5" else _make(var, cy)


C.make = _make_with_b5


def run_b5(zs, t_star=None, horizon=None):
    """B5 through the same online loop as F3 (diag3_cw_dev.online), W = 256, K = 64"""
    return CD.online("B5", zs, C.W, 64, t_star, horizon)


# ---- cyl16p, as validated in freeze 1 -----------------------------------------------------------------------------
_CY = None


def run_cyl16p(y, P):
    global _CY
    if _CY is None:
        _CY = V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    m, t0 = V.TemplateMachine(_CY), time.monotonic()
    for k, (yy, pp) in enumerate(zip(y, P)):
        m.observe(yy, pp)
        if m.inconsistent:
            return k, time.monotonic() - t0
    return None, time.monotonic() - t0


# ---- the true physical state of a simulated run (for the containment check) ------------------------------------
def truth_of(run):
    """(ac, as, TA) - 25 of the ambient part, from thermal.step with no command (float; a sanity check only)"""
    TA = run["TA"]
    tc, ts = TA[0], TA[0]
    out = []
    for ta in TA:
        out.append(np.array([tc, ts, ta]) - V.SHIFT)
        tc, ts = T.step(tc, ts, 0.0, ta)
    return out


METHODS = {
    "B2": lambda cfg: StripZonotope(cfg["order"], cfg.get("prior", "box+err")),
    "B3": lambda cfg: GainObserver(cfg["q"], cfg["order"], cfg.get("prior", "box+err")),
    "B4": lambda cfg: IntervalObserver(cfg["L"]),
}
