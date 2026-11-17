"""Offline LP oracle for experiments/specs/thermal_single_sensor_consistency.md (protocol v2).

Ground truth for distinguishability, not a method under test. Given z = y - S (S known from the command),
it asks whether some admissible ambient path explains z within the noise bound, using the plant's own
dynamics for the ambient part (so the plant's smoothness is included):

    ac[0] = as[0] = TA[0]                                    (e) steady state at the unknown ambient
    ac[k+1] = (1 - K/CC) ac[k] + (K/CC) as[k]
    as[k+1] = (K/CS) ac[k] + (1 - (K+H)/CS) as[k] + (H/CS) TA[k]
    |z[k] - as[k] - b| <= d                                  (a)
    |TA[k+1] - TA[k]| <= RHO_A                               (b), optional
    TA_LO <= TA[k] <= TA_HI                                  (c), optional

The oracle solves d* = min d, an LP that is always feasible, and does not take the solver's word for it.
Every answer carries two certificates:

  d_up  the solver's ambient path TA, projected onto the admissible set here (a forward pass that clips
        each step to the rate bound, then to the box, so both hold exactly) and run forward through the
        plant independently of the LP: the largest |z - as| it leaves. That projected path is admissible,
        so d* <= d_up.
  d_lo  a weak-duality lower bound from the solver's dual multipliers. It is accepted only if the dual
        stationarity residual is below DUAL_TOL; otherwise d_lo = 0 (no lower bound).

  verdict "consistent"    if d_up <= DELTA
          "inconsistent"  if d_lo >  DELTA
          "undetermined"  otherwise (reported, never guessed)

History of this file, before any result was kept:
  - Asking HiGHS for feasibility at d = DELTA gave "model status unknown" on some prefixes.
  - With d free, HiGHS's presolve failed on about 6 % of full runs (degenerate LPs, many active rate
    constraints).
  - Without presolve, IPM and dual simplex agree on those runs.
  - With presolve on, HiGHS also crashed a worker process outright.
  - Checking the solver's path against the rate bound at 1e-9 rejected paths that are within the solver's
    own tolerance (about 1e-7); the path is now projected instead of rejected.
So only IPM and dual simplex without presolve are used. A "consistent" verdict needs only d_up.

All temperatures are shifted by -25 C inside the LP. The dynamics are shift invariant (A·1 + B_T = 1),
so this changes nothing but the conditioning.
"""
import os
import sys

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "generators"))
import thermal as T  # noqa: E402

A11, A12 = 1.0 - T.K / T.CC, T.K / T.CC
A21, A22, B2 = T.K / T.CS, 1.0 - (T.K + T.H) / T.CS, T.H / T.CS
SHIFT = 25.0
DUAL_TOL = 1e-7
ATTEMPTS = (("highs-ds", False), ("highs-ipm", False))   # presolve can crash the process: never used; IPM segfaulted on CAL 410197 healthy E0


class OracleError(RuntimeError):
    pass


def _build(z, m, box, rate, mode, sense):
    z = np.asarray(z[:m], dtype=float) - SHIFT
    iTA, iac, ias, ib, idd = 0, m, 2 * m, 3 * m, 3 * m + 1
    nv = 3 * m + 2
    er, ec, ev = [], [], []
    row = 0
    for idx in (iac, ias):
        er += [row, row]; ec += [idx, iTA]; ev += [1.0, -1.0]; row += 1
    for k in range(m - 1):
        er += [row, row, row]; ec += [iac + k + 1, iac + k, ias + k]; ev += [1.0, -A11, -A12]; row += 1
        er += [row, row, row, row]; ec += [ias + k + 1, iac + k, ias + k, iTA + k]
        ev += [1.0, -A21, -A22, -B2]; row += 1
    Aeq = coo_matrix((ev, (er, ec)), shape=(row, nv)).tocsr()
    beq = np.zeros(row)
    ur, uc, uv, ub = [], [], [], []
    row = 0
    for k in range(m):              # as + b - d <= z ; -as - b - d <= -z
        ur += [row, row, row]; uc += [ias + k, ib, idd]; uv += [1.0, 1.0, -1.0]; ub.append(z[k]); row += 1
        ur += [row, row, row]; uc += [ias + k, ib, idd]; uv += [-1.0, -1.0, -1.0]; ub.append(-z[k]); row += 1
    if rate:
        for k in range(m - 1):
            ur += [row, row]; uc += [iTA + k + 1, iTA + k]; uv += [1.0, -1.0]; ub.append(T.RHO_A); row += 1
            ur += [row, row]; uc += [iTA + k + 1, iTA + k]; uv += [-1.0, 1.0]; ub.append(T.RHO_A); row += 1
    Aub = coo_matrix((uv, (ur, uc)), shape=(row, nv)).tocsr()
    ta_b = (T.TA_LO - SHIFT, T.TA_HI - SHIFT) if box else (None, None)
    if mode == "margin":
        bb, db = (0.0, 0.0), (0.0, None)
    else:
        bb, db = (None, None), (T.DELTA, T.DELTA)
    bounds = [ta_b] * m + [(None, None)] * (2 * m) + [bb, db]
    c = np.zeros(nv)
    if mode == "margin":
        c[idd] = 1.0
    else:
        c[ib] = sense
    return c, Aub, np.array(ub), Aeq, beq, bounds, z


def _dual_bound(res, c, Aub, bub, Aeq, beq, bounds):
    """Weak-duality bound from scipy's multipliers; None if stationarity does not hold to DUAL_TOL."""
    y_ub, y_eq = res.ineqlin.marginals, res.eqlin.marginals
    lam_l, lam_u = res.lower.marginals, res.upper.marginals
    resid = c - (Aub.T @ y_ub + Aeq.T @ y_eq + lam_l + lam_u)
    if np.max(np.abs(resid)) > DUAL_TOL:
        return None
    lo = np.array([b[0] if b[0] is not None else 0.0 for b in bounds])
    up = np.array([b[1] if b[1] is not None else 0.0 for b in bounds])
    return float(bub @ y_ub + beq @ y_eq + lo @ lam_l + up @ lam_u)


def _project(TA_shifted, box, rate):
    """The nearest-in-spirit admissible path: each step clipped to the rate bound, then to the box. Starting
    inside the box, the two clips always intersect, so the result satisfies (b) and (c) exactly."""
    TA = np.asarray(TA_shifted, dtype=float).copy()
    lo, hi = (T.TA_LO - SHIFT, T.TA_HI - SHIFT) if box else (-np.inf, np.inf)
    TA[0] = min(hi, max(lo, TA[0]))
    for k in range(1, len(TA)):
        x = TA[k]
        if rate:
            x = min(TA[k - 1] + T.RHO_A, max(TA[k - 1] - T.RHO_A, x))
        TA[k] = min(hi, max(lo, x))
    return TA


def _forward(TA_shifted, z_shifted, b, box, rate):
    """Project the solver's ambient path, run it through the plant here, return the noise level it needs."""
    TA = _project(TA_shifted, box, rate)
    ac = as_ = TA[0]
    worst = 0.0
    for k in range(len(TA)):
        worst = max(worst, abs(z_shifted[k] - as_ - b))
        ac, as_ = A11 * ac + A12 * as_, A21 * ac + A22 * as_ + B2 * TA[k]
    return worst


def margin(z, m=None, box=True, rate=True):
    """(d_lo, d_up): certified bounds on d*, the smallest noise bound explaining z[0:m].
    d_lo is 0.0 when no attempt produced a dual bound that passes the stationarity check."""
    m = len(z) if m is None else m
    if m == 0:
        return 0.0, 0.0
    c, Aub, bub, Aeq, beq, bounds, zs = _build(z, m, box, rate, "margin", 0.0)
    best_lo, best_up, last = 0.0, np.inf, None
    for method, presolve in ATTEMPTS:
        res = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds, method=method,
                      options={"presolve": presolve})
        last = res
        if res.status != 0:
            continue
        best_up = min(best_up, _forward(res.x[:m], zs, 0.0, box, rate))
        d_lo = _dual_bound(res, c, Aub, bub, Aeq, beq, bounds)
        if d_lo is not None and d_lo <= best_up + 1e-6:
            best_lo = max(best_lo, d_lo)
            return best_lo, best_up
    if np.isfinite(best_up):
        return best_lo, best_up
    raise OracleError(f"no solution (m={m}); last status {last.status}: {last.message}")


def verdict(z, m=None, box=True, rate=True):
    d_lo, d_up = margin(z, m, box, rate)
    if d_up <= T.DELTA:
        return "consistent", d_lo, d_up
    if d_lo > T.DELTA:
        return "inconsistent", d_lo, d_up
    return "undetermined", d_lo, d_up


def first_inconsistent(z, box=True, rate=True):
    """(t*, status). t* is the smallest index with z[0:t*+1] certified inconsistent; None if the whole run
    is certified consistent. status is "certified", or "undetermined" when a certificate along the search
    could not separate the bound from DELTA (t* is then the search's best estimate, reported as such)."""
    n = len(z)
    v, _, _ = verdict(z, n, box, rate)
    if v == "consistent":
        return None, "certified"
    status = "certified" if v == "inconsistent" else "undetermined"
    lo, hi = 0, n
    while hi - lo > 1:
        mid = (lo + hi) // 2
        v, _, _ = verdict(z, mid, box, rate)
        if v == "undetermined":
            status = "undetermined"
        if v == "consistent":
            lo = mid
        else:
            hi = mid
    return hi - 1, status


def offset_interval(z, box=True, rate=True):
    """Constant sensor offsets the whole run can not exclude, as (b_min, b_max) from the solver; each end
    is checked by running its ambient path forward (an inner bound). None if no offset is consistent."""
    out = []
    for sense in (1.0, -1.0):
        c, Aub, bub, Aeq, beq, bounds, zs = _build(z, len(z), box, rate, "offset", sense)
        got = None
        for method, presolve in ATTEMPTS:
            res = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds, method=method,
                          options={"presolve": presolve})
            if res.status == 2:
                return None
            if res.status == 0:
                b = float(res.x[3 * len(z)])
                if _forward(res.x[:len(z)], zs, b, box, rate) <= T.DELTA + 1e-7:
                    got = b
                    break
        if got is None:
            raise OracleError("offset interval: no verified solution")
        out.append(got)
    return out[0], out[1]
