"""Offline LP oracle for experiments/specs/thermal_single_sensor_consistency.md (protocol v2).

Ground truth for distinguishability, not a method under test. Given z = y - S (S known from the command),
it asks whether some admissible ambient path explains z within the noise bound, using the plant's own
dynamics for the ambient part (so the plant's smoothness is included):

    ac[0] = as[0] = TA[0]                                    (e) steady state at the unknown ambient
    ac[k+1] = (1 - K/CC) ac[k] + (K/CC) as[k]
    as[k+1] = (K/CS) ac[k] + (1 - (K+H)/CS) as[k] + (H/CS) TA[k]
    |z[k] - as[k] - b| <= DELTA                              (a), b = 0 unless an offset is asked for
    |TA[k+1] - TA[k]| <= RHO_A                               (b), optional
    TA_LO <= TA[k] <= TA_HI                                  (c), optional

Solved with scipy's HiGHS. A status other than optimal or infeasible raises.
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


def _lp(z, m, box=True, rate=True, offset="zero", sense=0.0):
    """Build and solve the LP on z[0:m]. offset: "zero" (b = 0) or "free" (b is a variable).
    sense: objective coefficient on b (0 feasibility, +1 minimize b, -1 maximize b)."""
    z = np.asarray(z[:m], dtype=float)
    iTA, iac, ias, ib = 0, m, 2 * m, 3 * m
    nv = 3 * m + 1
    er, ec, ev, eb = [], [], [], []
    row = 0
    # initial condition
    for idx in (iac, ias):
        er += [row, row]; ec += [idx, iTA]; ev += [1.0, -1.0]; eb.append(0.0); row += 1
    # dynamics
    for k in range(m - 1):
        er += [row, row, row]; ec += [iac + k + 1, iac + k, ias + k]; ev += [1.0, -A11, -A12]
        eb.append(0.0); row += 1
        er += [row, row, row, row]; ec += [ias + k + 1, iac + k, ias + k, iTA + k]
        ev += [1.0, -A21, -A22, -B2]; eb.append(0.0); row += 1
    Aeq = coo_matrix((ev, (er, ec)), shape=(row, nv)).tocsr()

    ur, uc, uv, ub = [], [], [], []
    row = 0
    for k in range(m):                       # (a): as + b <= z + d ; -as - b <= -(z - d)
        ur += [row, row]; uc += [ias + k, ib]; uv += [1.0, 1.0]; ub.append(z[k] + T.DELTA); row += 1
        ur += [row, row]; uc += [ias + k, ib]; uv += [-1.0, -1.0]; ub.append(-(z[k] - T.DELTA)); row += 1
    if rate:                                 # (b)
        for k in range(m - 1):
            ur += [row, row]; uc += [iTA + k + 1, iTA + k]; uv += [1.0, -1.0]; ub.append(T.RHO_A); row += 1
            ur += [row, row]; uc += [iTA + k + 1, iTA + k]; uv += [-1.0, 1.0]; ub.append(T.RHO_A); row += 1
    Aub = coo_matrix((uv, (ur, uc)), shape=(row, nv)).tocsr()

    bounds = ([(T.TA_LO, T.TA_HI) if box else (None, None)] * m
              + [(None, None)] * (2 * m)
              + [(0.0, 0.0) if offset == "zero" else (None, None)])
    c = np.zeros(nv)
    c[ib] = sense
    res = linprog(c, A_ub=Aub, b_ub=np.array(ub), A_eq=Aeq, b_eq=np.array(eb), bounds=bounds,
                  method="highs")
    if res.status not in (0, 2):
        raise RuntimeError(f"LP status {res.status}: {res.message}")
    return res


def feasible(z, m=None, box=True, rate=True):
    return _lp(z, len(z) if m is None else m, box, rate).status == 0


def first_inconsistent(z, box=True, rate=True, lo=1):
    """Smallest sample index t such that z[0:t+1] has no admissible explanation; None if the whole run
    is consistent. Feasibility is monotone in the prefix length, so a binary search is exact."""
    n = len(z)
    if feasible(z, n, box, rate):
        return None
    lo_m, hi_m = lo, n                       # prefix lo_m feasible (assumed), hi_m infeasible
    if not feasible(z, lo_m, box, rate):
        return lo_m - 1
    while hi_m - lo_m > 1:
        mid = (lo_m + hi_m) // 2
        if feasible(z, mid, box, rate):
            lo_m = mid
        else:
            hi_m = mid
    return hi_m - 1


def offset_interval(z, box=True, rate=True):
    """[b_min, b_max]: the constant sensor offsets the whole run can not exclude; None if none."""
    lo = _lp(z, len(z), box, rate, offset="free", sense=1.0)
    if lo.status != 0:
        return None
    hi = _lp(z, len(z), box, rate, offset="free", sense=-1.0)
    return float(lo.x[-1]), float(hi.x[-1])
