"""SDTS v3, alternative explanations: the template state over (ac, as, TA, b), b a constant sensor offset.

The set kept is every (physical state, offset) pair that some admissible past explains with |z - as - b| <= DELTA.
Its projection on b is the set of constant offsets the record can not exclude (v2's offset interval, but with the
plant's own dynamics, which v2's offset recursion drops). Same construction as template_state.py, in 4-D: bases
are 4-subsets of the directions, precomputed offline; run-time support is a min of 4-term dot products.
The first measurement initialises the state exactly (b is unbounded before it).
"""
import itertools
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import template_state as V  # noqa: E402

T = V.T
DIM = 4
M4 = np.zeros((4, 4))
M4[:3, :3] = V.M
M4[3, 3] = 1.0
E4 = np.eye(4)
EPS = V.EPS
GAMMA5 = 5 * EPS / (1 - 5 * EPS)


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


def directions(N=4):
    D = [s * E4[c] for c in range(4) for s in (1, -1)]
    lift = lambda d3, b=0.0: np.concatenate([d3, [b]])
    for d in V.directions("inv", N=N):
        if abs(d[0]) + abs(d[1]) + abs(d[2]) > 0 and not any(abs(abs(d[c]) - 1) < 1e-12 for c in range(3)):
            D.append(lift(d))
    u = _unit([0, 1, 0, 1])                              # as + b: the measured direction
    D += [u, -u, _unit([0, 0, 1, 1]), -_unit([0, 0, 1, 1]), _unit([1, 0, 0, 1]), -_unit([1, 0, 0, 1])]
    out = []
    for d in D:
        d = _unit(d)
        if all(np.dot(d, q) < 1 - 1e-9 for q in out):
            out.append(d)
    return np.array(out)


def _bases(D, g, tol=1e-12):
    sub = np.array(list(itertools.combinations(range(len(D)), DIM)))
    mats = D[sub].transpose(0, 2, 1)
    ok = np.abs(np.linalg.det(mats)) > 1e-12
    sub, mats = sub[ok], mats[ok]
    lam = np.linalg.solve(mats, np.broadcast_to(g, (len(sub), DIM))[..., None])[..., 0]
    keep = np.all(lam >= -tol, axis=1)
    sub, lam = sub[keep], np.maximum(lam[keep], 0.0)
    terms = lam[..., None] * D[sub]
    r = np.abs(g[None, :] - terms.sum(axis=1)).sum(axis=1)
    res = np.nextafter(r + 8 * EPS * (np.abs(g).sum() + np.abs(terms).sum(axis=(1, 2))), np.inf)
    return sub, lam, np.abs(lam).sum(axis=1), res


class OffsetTemplate:
    def __init__(self, D):
        self.D, self.n = np.asarray(D, dtype=float), len(D)
        key = {tuple(np.round(d, 12)): i for i, d in enumerate(self.D)}
        self.ip = [key[tuple(E4[c])] for c in range(4)]
        self.im = [key[tuple(-E4[c])] for c in range(4)]
        u = _unit([0, 1, 0, 1])
        self.iu, self.imu = key[tuple(np.round(u, 12))], key[tuple(np.round(-u, 12))]
        self.rho_pad = np.array([T.RHO_A * abs(d[2]) for d in self.D])
        self.pred = [_bases(self.D, M4.T @ d) for d in self.D]
        self.supp_u = [_bases(self.D, s * u) for s in (1, -1)]
        self.supp_b = [_bases(self.D, s * E4[3]) for s in (1, -1)]
        self.cap = np.full(self.n, np.inf)               # reachable-set clamps for directions without b
        for i, d in enumerate(self.D):
            if d[3] == 0:
                sigma = float(d[:3].sum())
                self.cap[i] = math.nextafter(max(sigma * V.HI, sigma * V.LO) + V.invariant_support(d[:2]) + 8 * EPS, math.inf)
        starts = np.cumsum([0] + [len(b[0]) for b in self.pred[:-1]])
        self._flat = (np.concatenate([b[0] for b in self.pred]), np.concatenate([b[1] for b in self.pred]),
                      np.concatenate([b[2] for b in self.pred]), np.concatenate([b[3] for b in self.pred]), starts)
        self.table_entries = int(sum(len(b[0]) for b in self.pred + self.supp_u + self.supp_b))

    def _cap_s(self, h):
        return float(max(max(abs(h[self.ip[c]]), abs(h[self.im[c]])) for c in range(4)))

    def support(self, h, bases):
        idx, lam, lsum, res = bases
        vals = (lam * h[idx]).sum(axis=1) + GAMMA5 * lsum * np.max(np.abs(h)) + res * self._cap_s(h)
        return math.nextafter(float(vals.min()), math.inf)

    def first_state(self, zs):
        """Exact supports of {(t,t,t,b) : t in box, |zs - t - b| <= DELTA}, rounded up."""
        h = np.empty(self.n)
        for i, d in enumerate(self.D):
            sigma = float(d[:3].sum())
            h[i] = 2.0 * abs(sigma - d[3]) + d[3] * zs + abs(d[3]) * T.DELTA
        h = np.nextafter(h + 8 * EPS * (np.abs(h) + abs(zs) + 3), np.inf)
        return self.clamp(h)

    def clamp(self, h):
        h = np.minimum(h, self.cap)
        for c in range(3):
            h[self.ip[c]] = min(h[self.ip[c]], V.HI)
            h[self.im[c]] = min(h[self.im[c]], -V.LO)
        return h

    def predict(self, h):
        idx, lam, lsum, res, starts = self._flat
        vals = (lam * h[idx]).sum(axis=1) + GAMMA5 * lsum * np.max(np.abs(h)) + res * self._cap_s(h)
        out = np.minimum.reduceat(vals, starts) + self.rho_pad
        return self.clamp(np.nextafter(out + 2 * EPS * np.abs(out), np.inf))


class OffsetMachine:
    """Online: inconsistent iff no (state, constant offset) explains the record; offset() is a sound outer
    interval of the offsets that do."""

    def __init__(self, template):
        self.t = template
        self.h = None
        self._tc, self._ts = T.equilibrium(T.P0, 0.0)
        self.inconsistent = False

    def observe(self, y, power):
        z = y - self._ts
        self._tc, self._ts = T.step(self._tc, self._ts, power, 0.0)
        if self.inconsistent:
            return True
        zs = z - V.SHIFT
        if self.h is None:
            self.h = self.t.predict(self.t.first_state(zs))
            return False
        r2 = math.sqrt(2.0)
        lo = math.nextafter((math.nextafter(zs, -math.inf) - T.DELTA) / r2, -math.inf)
        hi = math.nextafter((math.nextafter(zs, math.inf) + T.DELTA) / r2, math.inf)
        lo, hi = math.nextafter(lo, -math.inf), math.nextafter(hi, math.inf)
        top, bottom = self.t.support(self.h, self.t.supp_u[0]), -self.t.support(self.h, self.t.supp_u[1])
        if top < lo or bottom > hi:
            self.inconsistent = True
            return True
        h = self.h.copy()
        h[self.t.iu] = min(h[self.t.iu], hi)
        h[self.t.imu] = min(h[self.t.imu], -lo)
        self._last = h
        self.h = self.t.predict(h)
        return False

    def offset(self):
        """Outer interval of the non-excludable constant offsets (None once inconsistent)."""
        if self.inconsistent or self.h is None:
            return None
        h = self._last
        return (-self.t.support(h, self.t.supp_b[1]), self.t.support(h, self.t.supp_b[0]))

    def verdict(self, radius):
        if self.inconsistent:
            return "TUTARSIZ"
        lo, hi = self.offset()
        return "TUTARLI" if -radius <= lo and hi <= radius else "AYIRT EDİLEMEZ"
