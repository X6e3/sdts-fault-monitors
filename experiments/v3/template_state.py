"""SDTS v3 candidate: a fixed-memory, LP-free, sound template-polyhedral information state.

The exact information state of the v2 thermal problem (b = 0, assumptions (a)(b)(c)(e) and the plant's own
filter dynamics) at sample k is a convex polytope X_k in the 3-D physical state s = (ac, as, TA):

    s_{k+1} = M s_k + e3 w,  |w| <= RHO_A,  TA in [TA_LO, TA_HI],  |z[k] - as[k]| <= DELTA,
    s_0 = (TA0, TA0, TA0), TA0 in the box.

Every future constraint involves only s_k, so X_k carries all the information the full history holds about
consistency (MATH; see V3_NOTES.md). This module keeps an outer approximation of X_k in a fixed set of
directions D = {d_1..d_n} (a "template"): P_k = {s : d_i . s <= h_i}. The state is the vector h (n numbers).

Per sample (all upper bounds are rounded outward, so P_k contains X_k):
  1. as-range of P_k: [-supp(-e2), supp(e2)]. If it misses [z - DELTA, z + DELTA]: TUTARSIZ (absorbing).
  2. Tighten h(+-e2) with the measurement.
  3. Predict: h'_i = supp_{P_k}(M^T d_i) + RHO_A |d_i3|, then apply the TA box and the implied (ac, as) box.

supp_P(g) = min { lam . h : lam >= 0, D^T lam = g } (LP duality, exact for nonempty P). Its optimum is at a
basic solution, i.e. a triple of directions. Because M and D are fixed, all feasible triples and their lam are
computed offline; at run time supp is a min over a fixed list of 3-term dot products. No LP is solved online.
"""
import itertools
import math
import os
import sys
from fractions import Fraction

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "generators"))
import thermal as T  # noqa: E402

A11, A12 = 1.0 - T.K / T.CC, T.K / T.CC
A21, A22, B2 = T.K / T.CS, 1.0 - (T.K + T.H) / T.CS, T.H / T.CS
M = np.array([[A11, A12, 0.0], [A21, A22, B2], [0.0, 0.0, 1.0]])
SHIFT = 25.0
LO, HI = T.TA_LO - SHIFT, T.TA_HI - SHIFT          # -2, +2 (shifted box; also implied for ac and as)
EPS = np.finfo(float).eps
GAMMA4 = 4 * EPS / (1 - 4 * EPS)                    # rounding of a 3-term dot product plus one addition
E = np.eye(3)


F2 = M[:2, :2]                                      # error dynamics e = (ac - TA, as - TA): e' = F2 e + g w
G2 = np.array([-1.0, -1.0])


def invariant_support(q, terms=6000):
    """Upper bound on sup over every reachable error e of q . e  (= RHO_A sum_j |q F2^j g|, tail bounded)."""
    q = np.asarray(q, dtype=float)
    total, v = 0.0, G2.copy()
    for _ in range(terms):
        total += abs(float(q @ v))
        v = F2 @ v
    rate = max(abs(np.linalg.eigvals(F2)))
    tail = float(np.linalg.norm(q) * np.linalg.norm(v)) / (1 - rate) * 2.0      # generous geometric tail
    return math.nextafter(T.RHO_A * (total + tail) * (1 + 1e-12), math.inf)


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def directions(kind, L=0, N=0):
    """Template families. Every family contains +-e1, +-e2, +-e3."""
    base = [E[0], -E[0], E[1], -E[1], E[2], -E[2]]
    diff = [_unit([1, -1, 0]), _unit([-1, 1, 0]), _unit([0, 1, -1]), _unit([0, -1, 1])]
    if kind == "box":
        D = base
    elif kind == "box+diff":
        D = base + diff
    elif kind == "modal":
        _, W = np.linalg.eig(M.T)
        D = base + diff + [s * _unit(np.real(W[:, i])) for i in range(3) for s in (1, -1)]
    elif kind == "orbit":                     # orbits of e1, e2, e3 under M^T, L steps each
        D = base + diff
        for start in E:
            g = start.copy()
            for _ in range(L):
                g = M.T @ g
                D += [_unit(g), -_unit(g)]
    elif kind in ("inv", "inv+orbit"):         # error-plane directions (sum of components 0), K angles
        D = base + diff
        v = M.T @ E[1] - E[1]                 # the direction of as[k+1] - as[k]
        D += [_unit(v), -_unit(v)]
        for i in range(N):
            a = math.pi * i / N
            q = np.array([math.cos(a), math.sin(a)])
            D += [_unit([q[0], q[1], -q.sum()]), -_unit([q[0], q[1], -q.sum()])]
        if kind == "inv+orbit":
            for start in E:
                g = start.copy()
                for _ in range(L):
                    g = M.T @ g
                    D += [_unit(g), -_unit(g)]
    elif kind == "sphere":                    # quasi-uniform (Fibonacci) directions, both signs
        D = base + diff
        for i in range(N):
            z = 1 - (2 * i + 1) / (2 * N)
            r, phi = math.sqrt(max(0.0, 1 - z * z)), math.pi * (3 - math.sqrt(5)) * i
            D += [_unit([r * math.cos(phi), r * math.sin(phi), z]), -_unit([r * math.cos(phi), r * math.sin(phi), z])]
    else:
        raise ValueError(kind)
    out = []
    for d in D:                               # drop near-duplicates
        if all(np.dot(d, q) < 1 - 1e-9 for q in out):
            out.append(d)
    return np.array(out)


def _exact_residual(g, lam, rows):
    """|g - sum lam_j d_j|_1 in exact arithmetic on the stored floats, rounded up."""
    r = [Fraction(float(g[c])) - sum(Fraction(float(l)) * Fraction(float(d[c])) for l, d in zip(lam, rows))
         for c in range(3)]
    return math.nextafter(float(sum(abs(x) for x in r)), math.inf)


def _bases(D, g, tol=1e-12):
    """All feasible triples for supp(g): (idx[T,3], lam[T,3], lam_abs_sum[T], residual_l1[T])."""
    n = len(D)
    trip = np.array(list(itertools.combinations(range(n), 3)))
    mats = D[trip].transpose(0, 2, 1)                        # columns are the three directions
    ok = np.abs(np.linalg.det(mats)) > 1e-12
    trip, mats = trip[ok], mats[ok]
    lam = np.linalg.solve(mats, np.broadcast_to(g, (len(trip), 3))[..., None])[..., 0]
    keep = np.all(lam >= -tol, axis=1)
    trip, lam = trip[keep], np.maximum(lam[keep], 0.0)
    # |g - sum lam_j d_j|_1, computed in float plus a bound on that computation's own rounding error
    terms = lam[..., None] * D[trip]                                   # [T, 3 directions, 3 coords]
    r = np.abs(g[None, :] - terms.sum(axis=1)).sum(axis=1)
    err = 8 * EPS * (np.abs(g).sum() + np.abs(terms).sum(axis=(1, 2)))
    res = np.nextafter(r + err, np.inf)
    return trip, lam, np.abs(lam).sum(axis=1), res


class Template:
    """Offline tables for a direction set D. Everything the run-time update needs, nothing else."""

    def __init__(self, D, name="", invariant=False):
        self.D, self.n, self.name = np.asarray(D, dtype=float), len(D), name
        self.invariant = invariant
        # reachable-set clamp per direction: d.s = sigma TA + q.e with TA in the box and e in E_inf
        self.cap_inv = np.full(self.n, np.inf)
        if invariant:
            for i, d in enumerate(self.D):
                sigma = float(d.sum())
                self.cap_inv[i] = math.nextafter(max(sigma * HI, sigma * LO) + invariant_support(d[:2])
                                                 + 8 * EPS, math.inf)
        idx = {tuple(np.round(d, 12)): i for i, d in enumerate(self.D)}
        self.ip = [idx[tuple(E[c])] for c in range(3)]       # +e1, +e2, +e3
        self.im = [idx[tuple(-E[c])] for c in range(3)]      # -e1, -e2, -e3
        self.rho_pad = np.array([T.RHO_A * abs(d[2]) for d in self.D])
        self.pred = [_bases(self.D, M.T @ d) for d in self.D]           # predict: supp(M^T d_i)
        self.supp_as = [_bases(self.D, s * E[1]) for s in (1, -1)]      # as-range: supp(+e2), supp(-e2)
        if any(len(b[0]) == 0 for b in self.pred + self.supp_as):
            raise ValueError("a direction has no feasible basis: D must positively span R^3")
        sigma = self.D @ np.ones(3)
        self.h0 = np.array([math.nextafter(2.0 * abs(s) * (1 + 4 * EPS), math.inf) for s in sigma])
        # flatten for a vectorised step
        self._flat = self._flatten(self.pred)
        self.table_entries = int(sum(len(b[0]) for b in self.pred + self.supp_as))

    @staticmethod
    def _flatten(groups):
        idx = np.concatenate([b[0] for b in groups])
        lam = np.concatenate([b[1] for b in groups])
        lsum = np.concatenate([b[2] for b in groups])
        res = np.concatenate([b[3] for b in groups])
        starts = np.cumsum([0] + [len(b[0]) for b in groups[:-1]])
        return idx, lam, lsum, res, starts

    def cost(self):
        """Run-time cost per sample and memory, counted from the tables."""
        macs = 3 * self.table_entries
        return {"state_floats": self.n, "table_entries": self.table_entries, "mac_per_sample": macs,
                "flash_bytes_float32": self.table_entries * (3 * 1 + 3 * 4 + 2 * 4) + self.n * 4}

    def support(self, h, bases):
        """Upper bound on supp_P(g) for the basis table of g (outward rounding)."""
        idx, lam, lsum, res = bases
        hv = h[idx]
        vals = (lam * hv).sum(axis=1)
        cap = self._cap(h)
        bound = vals + GAMMA4 * lsum * np.max(np.abs(h)) + res * cap
        return math.nextafter(float(bound.min()), math.inf)

    def _cap(self, h):
        """max |s_c| over P, from the box directions (P is inside the box they define)."""
        return float(max(max(abs(h[self.ip[c]]), abs(h[self.im[c]])) for c in range(3)))

    def predict(self, h):
        idx, lam, lsum, res, starts = self._flat
        vals = (lam * h[idx]).sum(axis=1) + GAMMA4 * lsum * np.max(np.abs(h)) + res * self._cap(h)
        out = np.minimum.reduceat(vals, starts) + self.rho_pad
        out = np.nextafter(out + 2 * EPS * np.abs(out), np.inf)
        return self.clamp(out)

    def clamp(self, h):
        """The TA box (assumption c) and the implied box of ac and as (convex combinations of TA)."""
        h = np.minimum(h, self.cap_inv)
        for c in range(3):
            h[self.ip[c]] = min(h[self.ip[c]], HI)
            h[self.im[c]] = min(h[self.im[c]], -LO)
        return h


class TemplateMachine:
    """Online consistency check (b = 0) with the template state. Same API idea as v2's ThermalMachine."""

    def __init__(self, template):
        self.t = template
        self.h = template.clamp(template.h0)
        self._tc, self._ts = T.equilibrium(T.P0, 0.0)       # the known command part S, as in v2
        self.inconsistent = False
        self.k = 0

    def observe(self, y, power):
        if not math.isfinite(y) or not T.P_LO <= power <= T.P_HI:
            raise ValueError("expected a finite measurement and an admissible command")
        z = y - self._ts
        self._tc, self._ts = T.step(self._tc, self._ts, power, 0.0)
        if not self.inconsistent:
            zs = z - SHIFT
            lo = math.nextafter(math.nextafter(zs, -math.inf) - T.DELTA, -math.inf)
            hi = math.nextafter(math.nextafter(zs, math.inf) + T.DELTA, math.inf)
            top = self.t.support(self.h, self.t.supp_as[0])
            bottom = -self.t.support(self.h, self.t.supp_as[1])
            if top < lo or bottom > hi:
                self.inconsistent = True
            else:
                h = self.h.copy()
                h[self.t.ip[1]] = min(h[self.t.ip[1]], hi)
                h[self.t.im[1]] = min(h[self.t.im[1]], -lo)
                self.as_range = (max(bottom, lo), min(top, hi))
                self._last_tightened = h
                self.h = self.t.predict(h)
        self.k += 1
        return self.inconsistent


def first_inconsistent(template, y, P):
    m = TemplateMachine(template)
    for k, (yk, pk) in enumerate(zip(y, P)):
        if m.observe(yk, pk):
            return k
    return None


# ---- flash budget: pruning the basis tables ------------------------------------------------------------
# Any subset of a direction's bases still gives an upper bound (min over fewer candidates), so pruning keeps
# soundness and can only loosen the state. Bases that make the template dominate v2 are always kept:
# for the +-e2 prediction groups, the basis containing +-e2 and the as-velocity direction.

def usage(template, runs):
    """How often each table entry is the argmin, over the given (y, P) runs (selection set)."""
    groups = template.pred + template.supp_as
    counts = [np.zeros(len(g[0]), dtype=int) for g in groups]
    for y, P in runs:
        m = TemplateMachine(template)
        for yk, pk in zip(y, P):
            if m.inconsistent:
                break
            h_before = m.h.copy()
            for gi, g in zip((len(template.pred), len(template.pred) + 1), template.supp_as):
                counts[gi][int(np.argmin((g[1] * h_before[g[0]]).sum(axis=1)))] += 1
            m.observe(yk, pk)
            if not m.inconsistent:
                h = m._last_tightened
                for gi, g in enumerate(template.pred):
                    counts[gi][int(np.argmin((g[1] * h[g[0]]).sum(axis=1)))] += 1
    return counts


def pruned(template, counts, keep_top=None):
    """A copy that keeps, per group, the entries ever used (or the keep_top most used) plus the v2 bases."""
    import copy
    t = copy.copy(template)
    v_dirs = [i for i, d in enumerate(template.D) if abs(abs(np.dot(d, _unit(M.T @ E[1] - E[1]))) - 1) < 1e-12]
    groups = template.pred + template.supp_as
    new = []
    for gi, (g, c) in enumerate(zip(groups, counts)):
        order = np.argsort(-c, kind="stable")
        keep = set(order[: (keep_top if keep_top else len(order))][c[order[: (keep_top if keep_top else len(order))]] > 0].tolist())
        if gi in (template.ip[1], template.im[1]):   # prediction of +-e2: keep every basis using e2 and v
            e2 = template.ip[1] if gi == template.ip[1] else template.im[1]
            keep |= {j for j, tri in enumerate(g[0]) if e2 in tri and any(v in tri for v in v_dirs)}
        if not keep:
            keep = {int(order[0])}
        k = np.array(sorted(keep))
        new.append(tuple(x[k] for x in g))
    t.pred, t.supp_as = new[: template.n], new[template.n:]
    t._flat = t._flatten(t.pred)
    t.table_entries = int(sum(len(b[0]) for b in t.pred + t.supp_as))
    return t
