"""DIAG-3 amendment 2 (DIAG-3-PLAN.md): the compressed window, a pilot on the five diagnosis runs. W = 256, B = 16.

variants (all fold with the smoothing rule; every fold support is certified by a dual bound):
  A  the dense S256 window LP of diag3.Window (3 states per sample)
  E  (ac, as) only at nodes, the TA path kept at every sample; only measurements redundant at arrival are dropped.
     Between nodes ac and as stay in the box by convexity, so E is A without the dropped measurements.
  N  as E, but TA only at nodes, with the ambient increments w_j (|w_j| <= rho) explicit: the TA box between nodes
     is dropped (sound, looser).
nodes: tau, the kept measurements, tau + B (the fold), the objective state and t_end.
segment a -> b (L = b - a):  x_b = M^L x_a + sum_{k<L} M^k e3 w_{b-1-k}, exactly (M^L from exact rational powers).

usage:
  python -B diag3_cw.py check OUT [--workers 5]       # E with every measurement against diag3.Window, lockstep
  python -B diag3_cw.py run OUT [--workers 8] [--variants A E N]
  python -B diag3_cw.py summary OUT
"""
import argparse
import json
import math
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diag1 as G  # noqa: E402
import diag3 as W3  # noqa: E402

V, S, T, M = G.V, G.S, G.T, G.M
DELTA, RHO, LO, HI, NREC = G.DELTA, G.RHO, G.LO, G.HI, G.NREC
B, PAD, AFTER, W = W3.B, W3.PAD, W3.AFTER, 256
U = 2.0 ** -53
T3A_430010 = (695, -0.2855352673387656)        # the certified replay of the independent check, mC
CHECK_TOL = 1e-6                                # degC
MARGIN_TOL_E = 1e-3                             # mC
MARGIN_TOL_A = 1e-2                             # mC
LAZY_TOL, LAZY_MAX = 1e-9, 100                  # degC; re-solves per LP


def _powers(n):
    Mq = [[Fraction(float(M[i, j])) for j in range(3)] for i in range(3)]
    P = [[[Fraction(int(i == j)) for j in range(3)] for i in range(3)]]
    for _ in range(n):
        Q = P[-1]
        P.append([[sum(Q[i][k] * Mq[k][j] for k in range(3)) for j in range(3)] for i in range(3)])
    return np.array([[[float(x) for x in row] for row in p] for p in P])


POW = _powers(W + 2 * B + 4)
GEN = POW[:, :, 2]                              # GEN[k] = M^k e3
assert np.array_equal(M[2], [0.0, 0.0, 1.0]) and np.all(POW[:, 2] == [0.0, 0.0, 1.0])


class Rec:
    last = None


def rec_linprog(c, **kw):
    res = linprog(c, **kw)
    Rec.last = (c, kw, res)
    return res


W3.linprog = rec_linprog                        # diag3.Window.lp now leaves its LP data in Rec.last


def _gam(n):
    return n * U / (1 - n * U)


def _colnnz(A):
    return int(np.diff(A.tocsc().indptr).max()) if A.nnz else 0


def certified_max(harden=False):
    """a rigorous upper bound on max (-c) x of the last LP: weak duality with the solver's multipliers, every
    variable boxed, float rounding bounded explicitly. harden: also enclose the rounding of the LP coefficients
    themselves (each one correctly rounded from its exact value, so off by less than 2u |a|), so that the bound holds
    for the LP with the exact coefficients (exact powers of M), not only for its float64 copy."""
    c, kw, res = Rec.last
    bnd = kw["bounds"]
    lb, ub = bnd[:, 0], bnd[:, 1]
    s, sa, k, parts = c.astype(float).copy(), np.abs(c).astype(float), 1, []
    if kw.get("A_ub") is not None:
        A, y = kw["A_ub"], np.maximum(0.0, -np.asarray(res.ineqlin.marginals))
        s += A.T @ y
        sa += abs(A).T @ y
        k += _colnnz(A)
        parts.append(y * kw["b_ub"])
    if kw.get("A_eq") is not None:
        A, nu = kw["A_eq"], -np.asarray(res.eqlin.marginals)
        s += A.T @ nu
        sa += abs(A).T @ np.abs(nu)
        k += _colnnz(A)
        parts.append(nu * kw["b_eq"])
    parts.append(-np.minimum(s * lb, s * ub))
    xm = np.maximum(np.abs(lb), np.abs(ub))
    parts.append(2 * _gam(k + 1) * sa * xm)
    if harden:
        parts.append(2 * U * (sa - np.abs(c)) * xm)
    p = np.concatenate(parts)
    tot = math.fsum(p)
    return tot + 4 * (_gam(4) * math.fsum(np.abs(p)) + U * abs(tot))


def exact_bound():
    """the same bound as certified_max(harden=True), evaluated in exact rational arithmetic on the float data and the
    same multipliers; an audit of the float evaluation"""
    c, kw, res = Rec.last
    F = Fraction
    lb, ub = kw["bounds"][:, 0], kw["bounds"][:, 1]
    s = [F(float(x)) for x in c]
    ca = [F(0)] * len(c)
    tot = F(0)
    for A, b, m in ((kw.get("A_ub"), kw.get("b_ub"), None if kw.get("A_ub") is None else
                     np.maximum(0.0, -np.asarray(res.ineqlin.marginals))),
                    (kw.get("A_eq"), kw.get("b_eq"), None if kw.get("A_eq") is None else
                     -np.asarray(res.eqlin.marginals))):
        if A is None:
            continue
        mq = [F(float(x)) for x in m]
        tot += sum(mi * F(float(bi)) for mi, bi in zip(mq, b))
        co = A.tocoo()
        for i, j, a in zip(co.row, co.col, co.data):
            s[j] += F(float(a)) * mq[i]
            ca[j] += abs(F(float(a)) * mq[i])
    two_u = F(2, 2 ** 53)
    for j in range(len(c)):
        l, u = F(float(lb[j])), F(float(ub[j]))
        tot += -min(s[j] * l, s[j] * u) + two_u * ca[j] * max(abs(l), abs(u))
    return tot


def solve(win, cvec, **kw):
    t0 = time.monotonic()
    res = None
    for method, opts in (("highs-ds", {"presolve": False}), ("highs-ipm", {"presolve": False}), ("highs-ds", {})):
        res = rec_linprog(cvec, method=method, options=opts, **kw)
        if res.status in (0, 2):
            break
        win.n_retry += 1
    win.lp_seconds += time.monotonic() - t0
    win.n_lp += 1
    if res.status == 2:
        return None
    if res.status != 0:
        raise RuntimeError(f"LP status {res.status}: {res.message}")
    return -res.fun


class Stats:
    def _init_stats(self):
        self.n_short, self.max_short, self.max_nodes, self.max_kept = 0, 0.0, 0, 0

    def lp_cert(self, *a):
        v = self.lp(*a)
        return (None, None) if v is None else (v, certified_max(getattr(self, "harden", False)))

    def fold(self, t):
        tau2 = self.tau + B
        t_end, upto = (t, t) if self.smooth else (tau2, tau2)
        vals = []
        for d in self.D:
            v, cub = self.lp_cert(t_end, upto, tau2, d) if self.cert else (self.lp(t_end, upto, tau2, d), None)
            if v is None:
                raise RuntimeError("window LP infeasible during a fold")
            if self.cert:
                if cub > v + PAD:
                    self.n_short += 1
                    self.max_short = max(self.max_short, cub - v - PAD)
                vals.append(max(v + PAD, cub))
            else:
                vals.append(v + PAD)
        self.tau, self.base = tau2, self.tp.clamp(np.array(vals, dtype=float))
        self.zs = {j: z for j, z in self.zs.items() if j >= tau2}

    def certify_alarm(self, t, z):
        up, cup = self.lp_cert(t, t - 1, t, (0, 1.0, 0))
        dn, cdn = self.lp_cert(t, t - 1, t, (0, -1.0, 0))
        zl, zu = z - DELTA, z + DELTA
        if getattr(self, "harden", False):                         # the slab of z_t, rounded outward
            zl, zu = np.nextafter(zl, -np.inf), np.nextafter(zu, np.inf)
        m = 1e3 * min(zu + cdn, cup - zl)                          # G.margin with certified bounds; < 0: certified
        return {"certified": bool(m < 0), "certified_margin_mC": m}


class Dense(Stats, W3.Window):
    def __init__(self, tp, cert=True):
        W3.Window.__init__(self, tp, W, smooth=True)
        self.cert = cert
        self._init_stats()


class Compressed(Stats):
    def __init__(self, tp, ta_path, cert=True, lazy=False, harden=False, track=False):
        assert not (lazy and ta_path)
        self.tp, self.D, self.ta_path, self.cert, self.smooth, self.lazy = tp, tp.D, ta_path, cert, True, lazy
        self.harden, self.track, self.now, self.last_active, self.n_evict = harden, track, 0, {}, 0
        self.tau, self.base, self.zs = 0, None, {}
        self.n_lp, self.max_vars, self.max_rows, self.lp_seconds, self.n_retry = 0, 0, 0, 0.0, 0
        self.ta_rows, self.n_resolve, self.max_ta_rows = set(), 0, 0
        self._init_stats()

    def lp(self, t_end, meas_upto, obj_state, obj_vec):
        tau = self.tau
        meas = sorted(j for j in self.zs if tau <= j <= meas_upto and not (j == tau and self.base is not None))
        nodes = sorted({tau, obj_state, t_end, *meas})
        nv, idx = 0, {}
        if self.ta_path:
            nv = t_end - tau + 1                                   # TA_j at every sample: index j - tau
            for nd in nodes:
                idx[nd] = (nv, nv + 1, nd - tau)
                nv += 2
        else:
            for nd in nodes:
                idx[nd] = (nv, nv + 1, nv + 2)
                nv += 3
        w0 = nv                                                    # w_j, j = tau .. t_end - 1
        nv += t_end - tau
        lb, ub = np.full(nv, LO), np.full(nv, HI)
        lb[w0:], ub[w0:] = -RHO, RHO
        for j in meas:
            i = idx[j][1]
            zl, zu = self.zs[j] - DELTA, self.zs[j] + DELTA
            if self.harden:                                        # round the slab outward
                zl, zu = np.nextafter(zl, -np.inf), np.nextafter(zu, np.inf)
            lb[i], ub[i] = max(lb[i], zl), min(ub[i], zu)
        if np.any(lb > ub):
            return None
        er, ec, ev, r = [], [], [], 0
        for a, b in zip(nodes, nodes[1:]):
            L, xa, xb = b - a, idx[a], idx[b]
            for c in (0, 1) if self.ta_path else (0, 1, 2):
                er.append(r), ec.append(xb[c]), ev.append(1.0)
                for q in range(3):
                    if POW[L][c, q] != 0.0:
                        er.append(r), ec.append(xa[q]), ev.append(-POW[L][c, q])
                for k in range(L):
                    if GEN[k][c] != 0.0:
                        er.append(r), ec.append(w0 + (b - 1 - k - tau)), ev.append(-GEN[k][c])
                r += 1
        if self.ta_path:                                           # TA_{j+1} - TA_j - w_j = 0
            for j in range(t_end - tau):
                er += [r, r, r]
                ec += [j + 1, j, w0 + j]
                ev += [1.0, -1.0, -1.0]
                r += 1
        if self.base is None:                                      # the initial segment: ac = as = TA
            x0 = idx[tau]
            er += [r, r, r + 1, r + 1]
            ec += [x0[0], x0[2], x0[1], x0[2]]
            ev += [1.0, -1.0, 1.0, -1.0]
            r += 2
        A_eq = sp.csr_matrix((ev, (er, ec)), shape=(r, nv)) if r else None
        b_eq = np.zeros(r) if r else None
        A_ub = b_ub = None
        q = 0
        if self.base is not None:                                  # D0 x_tau <= b
            x0 = idx[tau]
            ir, ic, iv = [], [], []
            for i, d in enumerate(self.D):
                for c in range(3):
                    if d[c] != 0.0:
                        ir.append(i), ic.append(x0[c]), iv.append(d[c])
            q = len(self.D)
            A_ub, b_ub = sp.csr_matrix((iv, (ir, ic)), shape=(q, nv)), np.asarray(self.base, dtype=float)
        cvec = np.zeros(nv)
        cvec[list(idx[obj_state])] = -np.asarray(obj_vec, dtype=float)
        if self.lazy:
            self.max_nodes = max(self.max_nodes, len(nodes))
            v = self._lazy(nodes, idx, w0, nv, cvec, A_ub, b_ub, A_eq, b_eq, np.c_[lb, ub], r + q)
        else:
            self.max_vars, self.max_rows = max(self.max_vars, nv), max(self.max_rows, r + q)
            self.max_nodes = max(self.max_nodes, len(nodes))
            v = solve(self, cvec, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=np.c_[lb, ub])
        if self.track and v is not None:                           # a measurement is active if its bound binds
            res = Rec.last[2]
            for j in meas:
                i = idx[j][1]
                if abs(res.lower.marginals[i]) > 1e-12 or abs(res.upper.marginals[i]) > 1e-12:
                    self.last_active[j] = self.now
        return v

    def keep(self, t, z):
        self.zs[t] = z
        self.last_active[t] = t                                    # it cut the predicted range when it arrived

    def evict(self):
        """drop the kept measurement that has been inactive the longest (ties: the oldest). Dropping is sound."""
        j = min((j for j in self.zs if j > self.tau), key=lambda j: (self.last_active.get(j, -1), j))
        del self.zs[j]
        self.last_active.pop(j, None)
        self.n_evict += 1

    def _lazy(self, nodes, idx, w0, nv, cvec, A_ub, b_ub, A_eq, b_eq, bounds, nrows):
        """N plus only the TA box rows between nodes that the solution needs: solve, add the violated rows, solve
        again. Every LP on the way is a relaxation of E's LP (so sound); the last one's optimum is feasible for E's
        LP, so it is E's optimum. Rows found once are kept while their sample is in the window."""
        tau = self.tau
        prev = {j: a for a, b in zip(nodes, nodes[1:]) for j in range(a + 1, b)}
        self.ta_rows = {x for x in self.ta_rows if x[0] > tau}
        for _ in range(LAZY_MAX):
            rows = sorted(x for x in self.ta_rows if x[0] in prev)
            Au, bu = A_ub, b_ub
            if rows:
                ir, ic, iv, rhs = [], [], [], []
                for k, (j, sg) in enumerate(rows):
                    a = prev[j]
                    ir.append(k), ic.append(idx[a][2]), iv.append(float(sg))
                    for i in range(a, j):
                        ir.append(k), ic.append(w0 + (i - tau)), iv.append(float(sg))
                    rhs.append(HI if sg > 0 else -LO)
                Lm = sp.csr_matrix((iv, (ir, ic)), shape=(len(rows), nv))
                Au = Lm if A_ub is None else sp.vstack([A_ub, Lm]).tocsr()
                bu = np.asarray(rhs) if b_ub is None else np.concatenate([b_ub, rhs])
            self.max_vars, self.max_rows = max(self.max_vars, nv), max(self.max_rows, nrows + len(rows))
            self.max_ta_rows = max(self.max_ta_rows, len(rows))
            v = solve(self, cvec, A_ub=Au, b_ub=bu, A_eq=A_eq, b_eq=b_eq, bounds=bounds)
            if v is None:
                return None
            x, new = Rec.last[2].x, set()
            for a, b in zip(nodes, nodes[1:]):
                ta = x[idx[a][2]]
                for j in range(a + 1, b):
                    ta += x[w0 + (j - 1 - tau)]
                    if ta > HI + LAZY_TOL:
                        new.add((j, 1))
                    elif ta < LO - LAZY_TOL:
                        new.add((j, -1))
            new -= self.ta_rows
            if not new:
                return v
            self.ta_rows |= new
            self.n_resolve += 1
        raise RuntimeError("lazy TA rows did not settle")

    def as_range(self, t):
        up = self.lp(t, t - 1, t, (0, 1.0, 0))
        dn = self.lp(t, t - 1, t, (0, -1.0, 0))
        return (None, None) if up is None or dn is None else (-dn, up)


class Audited(Compressed):
    """F (E with the hardened certificate), with every fold and alarm bound, and every 8th as-range bound, also
    evaluated exactly (exact_bound) and compared with its float evaluation"""

    def __init__(self, tp):
        super().__init__(tp, True, harden=True)
        self.audit = {"n": 0, "min_slack_C": math.inf, "violations": 0, "max_gap_to_value_C": 0.0,
                      "max_coefficient_term_C": 0.0}

    def _check(self, v, cub):
        ex = exact_bound()
        slack = Fraction(cub) - ex
        a = self.audit
        a["n"] += 1
        a["min_slack_C"] = min(a["min_slack_C"], float(slack))
        a["violations"] += slack < 0
        a["max_gap_to_value_C"] = max(a["max_gap_to_value_C"], cub - v)
        a["max_coefficient_term_C"] = max(a["max_coefficient_term_C"], cub - certified_max(False))

    def lp_cert(self, *args):
        v = self.lp(*args)
        if v is None:
            return None, None
        cub = certified_max(True)
        self._check(v, cub)
        return v, cub

    def as_range(self, t):
        out = []
        for vec in ((0, 1.0, 0), (0, -1.0, 0)):
            v = self.lp(t, t - 1, t, vec)
            if v is None:
                return None, None
            if t % 8 == 0:
                self._check(v, certified_max(True))
            out.append(v)
        return -out[1], out[0]


def make(var, cy):
    return {"A": lambda: Dense(cy), "E": lambda: Compressed(cy, True), "N": lambda: Compressed(cy, False),
            "L": lambda: Compressed(cy, False, lazy=True),
            "F": lambda: Compressed(cy, True, harden=True, track=True), "Fa": lambda: Audited(cy)}[var]()


def _run_info(seed, cell, amb):
    j1 = json.load(open(W3.D1RUN / f"arms-{seed}-{cell}-{amb}-L256.json"))
    run = S.run(seed, next(c for c in T.CELLS if c.name == cell), "E0", amb, "uniform")
    return j1["t_star"], j1["t_cyl16p"], G.zs_of(run), V.load_frozen(G.V3 / "frozen" / "cyl16p.json")


def job(args):
    seed, cell, amb, var, out = args
    t_star, t_cyl, zs, cy = _run_info(seed, cell, amb)
    w = make(var, cy)
    last = min(NREC - 1, t_cyl + AFTER)
    det, cert, margins, steps, fold_steps, n_dropped, t00 = None, None, {}, [], [], 0, time.monotonic()
    w.zs[0] = zs[0]
    for t in range(1, last + 1):
        t0 = time.monotonic()
        lower, upper = w.as_range(t)                  # measurements up to t - 1 only
        if lower is None:
            raise RuntimeError(f"window LP infeasible before measurement {t}")
        margins[t] = G.margin(lower, upper, zs[t])
        if upper < zs[t] - DELTA or lower > zs[t] + DELTA:
            det, cert = t, w.certify_alarm(t, zs[t])
            break
        if var == "A" or not (lower >= zs[t] - DELTA and upper <= zs[t] + DELTA):
            w.zs[t] = zs[t]
        else:
            n_dropped += 1
        w.max_kept = max(w.max_kept, len(w.zs))
        folded = t - w.tau > W + B
        if folded:
            w.fold(t)                                 # after the alarm check, with z_t
        (fold_steps if folded else steps).append(time.monotonic() - t0)
    ms = 1e3 * np.array(steps) if steps else np.zeros(1)
    fs = 1e3 * np.array(fold_steps) if fold_steps else np.zeros(1)
    res = {"seed": seed, "cell": cell, "ambient": amb, "variant": var, "W": W, "B": B, "t_star": t_star,
           "t_cyl16p": t_cyl, "detect": det, "censored_at": None if det is not None else last,
           "margin_at_t_star_mC": 1e3 * margins[t_star] if t_star in margins else None,
           "margin_at_detect_mC": 1e3 * margins[det] if det is not None else None, "alarm_certificate": cert,
           "folds_raised_to_dual_bound": w.n_short, "largest_raise_C": w.max_short,
           "measurements_dropped": n_dropped, "max_kept": w.max_kept,
           "max_nodes": getattr(w, "max_nodes", 0) or None, "max_vars": w.max_vars, "max_rows": w.max_rows,
           "n_lp": w.n_lp, "n_retry": w.n_retry, "lp_seconds": round(w.lp_seconds, 2),
           "step_ms": {"median": float(np.median(ms)), "p95": float(np.percentile(ms, 95)), "max": float(ms.max())},
           "fold_step_ms": {"median": float(np.median(fs)), "max": float(fs.max())},
           "audit": getattr(w, "audit", None), "seconds": round(time.monotonic() - t00, 1)}
    (Path(out) / f"cw-{seed}-{cell}-{amb}-{var}.json").write_text(json.dumps(res, indent=1) + "\n")
    np.save(Path(out) / f"cw-{seed}-{cell}-{amb}-{var}-margins.npy", np.array(sorted(margins.items())))
    return seed, var, det, t_star, res["seconds"]


def _fold_with(win, tau2, vals):
    win.tau, win.base = tau2, win.tp.clamp(np.array(vals, dtype=float) + PAD)
    win.zs = {j: z for j, z in win.zs.items() if j >= tau2}


def check_job(args):
    """lockstep: diag3.Window (phase 1, pad fold) against E with every measurement and the same fold rule. The
    measurements are added up to t* - 1 and the as-range is compared up to t*, as in the runs (the measurement at t*
    is the alarm). Every fold support is also bounded by its dual certificate, on both sides."""
    seed, cell, amb, out = args
    t_star, _, zs, cy = _run_info(seed, cell, amb)
    a, e = W3.Window(cy, W, smooth=True), Compressed(cy, True, cert=False)
    a.zs[0] = e.zs[0] = zs[0]
    d_range, d_fold, n_fold, worst, short = 0.0, 0.0, 0, None, {"dense": 0, "E": 0}
    for t in range(1, t_star + 1):
        ra, re = a.as_range(t), e.as_range(t)
        d_range = max(d_range, abs(ra[0] - re[0]), abs(ra[1] - re[1]))
        if t == t_star:
            break
        a.zs[t] = e.zs[t] = zs[t]
        if t - a.tau > W + B:
            tau2, va, vb = a.tau + B, [], []
            for d in a.D:
                x, ux = a.lp(t, t, tau2, d), certified_max()
                y, uy = e.lp(t, t, tau2, d), certified_max()
                short["dense"] += ux > x + PAD
                short["E"] += uy > y + PAD
                if abs(x - y) > d_fold:
                    d_fold, worst = abs(x - y), {"t": t, "direction": list(map(float, d)), "dense": x,
                                                 "dense_dual_bound": ux, "E": y, "E_dual_bound": uy}
                va.append(x), vb.append(y)
            _fold_with(a, tau2, va)
            _fold_with(e, tau2, vb)
            n_fold += 1
    res = {"seed": seed, "cell": cell, "ambient": amb, "steps": t_star, "folds": n_fold,
           "max_abs_diff_as_range_C": d_range, "max_abs_diff_fold_C": d_fold, "largest_fold_diff": worst,
           "fold_supports_short_of_dual_bound_by_more_than_pad": short,
           "dense_max_vars_rows": [a.max_vars, a.max_rows], "E_max_vars_rows": [e.max_vars, e.max_rows]}
    (Path(out) / f"check-{seed}.json").write_text(json.dumps(res, indent=1) + "\n")
    return seed, d_range, d_fold, short


def summary(out):
    rows = {}
    for f in sorted(out.glob("cw-*.json")):
        r = json.loads(f.read_text())
        rows.setdefault(r["seed"], {})[r["variant"]] = r
    checks = [json.loads(f.read_text()) for f in sorted(out.glob("check-*.json"))]
    rep = {"criteria": {}, "runs": {}}
    if checks:
        mx = max(max(c["max_abs_diff_as_range_C"], c["max_abs_diff_fold_C"]) for c in checks)
        rep["criteria"]["C0_E_all_equals_dense"] = {"max_abs_diff_C": mx, "runs": len(checks),
                                                     "passes": bool(len(checks) == 5 and mx <= CHECK_TOL)}
    A = {s: v["A"] for s, v in rows.items() if "A" in v}
    if len(A) == 5:
        ok = all(r["detect"] == r["t_star"] for r in A.values())
        r10 = A[430010]
        ok10 = r10["detect"] == T3A_430010[0] and abs(r10["margin_at_detect_mC"] - T3A_430010[1]) <= MARGIN_TOL_A
        rep["criteria"]["C1_A_certified"] = {"all_at_t_star": bool(ok), "430010_matches_independent": bool(ok10),
                                             "passes": bool(ok and ok10)}
    E = {s: v["E"] for s, v in rows.items() if "E" in v}
    if len(E) == 5 and len(A) == 5:
        same = all(E[s]["detect"] == A[s]["detect"] for s in E)
        dm = max(abs(E[s]["margin_at_t_star_mC"] - A[s]["margin_at_t_star_mC"]) for s in E)
        rep["criteria"]["C2_E_equals_A"] = {"same_detections": bool(same), "max_abs_margin_diff_mC": dm,
                                            "passes": bool(same and dm <= MARGIN_TOL_E)}
    early = [(s, v) for s, vs in rows.items() for v, r in vs.items() if r["detect"] is not None and
             r["detect"] < r["t_star"]]
    uncert = [(s, v) for s, vs in rows.items() for v, r in vs.items() if v in ("A", "E") and r["detect"] is not None
              and not r["alarm_certificate"]["certified"]]
    rep["criteria"]["C3_no_early_alarm_and_certified"] = {"early": early, "uncertified": uncert,
                                                          "passes": bool(not early and not uncert)}
    for s, vs in rows.items():
        rep["runs"][s] = {v: {k: r[k] for k in ("detect", "t_star", "margin_at_t_star_mC", "margin_at_detect_mC",
                                                "alarm_certificate", "folds_raised_to_dual_bound", "largest_raise_C",
                                                "measurements_dropped", "max_kept", "max_nodes", "max_vars",
                                                "max_rows", "n_lp", "n_retry", "step_ms", "fold_step_ms", "seconds")}
                          for v, r in sorted(vs.items())}
    return rep


def _meta(out, cmd):
    import scipy
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=G.ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=G.ROOT, text=True)
    meta = {"cmd": cmd, "git_head": head, "git_dirty_tracked": bool(dirty), "W": W, "B": B, "pad": PAD,
            "machine": platform.machine(), "platform": platform.platform(), "python": platform.python_version(),
            "numpy": np.__version__, "scipy": scipy.__version__, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (out / f"meta-{cmd}.json").write_text(json.dumps(meta, indent=1) + "\n")
    return meta


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("check", "run", "summary"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--variants", nargs="+", default=["A", "E", "N"])
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "summary":
        rep = summary(a.out)
        (a.out / "summary.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
        print(json.dumps(rep["criteria"], indent=1, default=str))
        return
    meta = _meta(a.out, a.cmd)
    if a.cmd == "check":
        jobs, fn = [(s, c, amb, str(a.out)) for s, c, amb in W3.RUNS], check_job
    else:
        jobs, fn = [(s, c, amb, v, str(a.out)) for s, c, amb in W3.RUNS for v in a.variants], job
    with ProcessPoolExecutor(a.workers) as pool:
        for x in pool.map(fn, jobs):
            print(x, flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / f"meta-{a.cmd}.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
