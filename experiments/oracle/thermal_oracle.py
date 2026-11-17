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

Consistency is decided through the smallest noise bound that explains the data, d* = min d. That LP is
always feasible, so no verdict rests on the solver declaring infeasibility. The run (or prefix) is
consistent iff d* <= DELTA. |d* - DELTA| <= BORDER marks a borderline verdict, which is reported.
(A first version asked HiGHS for feasibility at d = DELTA directly. Near the boundary it returned
"model status unknown" on some prefixes, so it was replaced before any result was kept.)

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
BORDER = 1e-6


class OracleError(RuntimeError):
    pass


def _solve(z, m, box, rate, mode, sense=0.0):
    """mode "margin": minimize d (b = 0). mode "offset": d = DELTA, b free, objective sense*b."""
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
    for method in ("highs", "highs-ipm", "highs-ds"):
        res = linprog(c, A_ub=Aub, b_ub=np.array(ub), A_eq=Aeq, b_eq=beq, bounds=bounds, method=method)
        if res.status == 0 or (mode == "offset" and res.status == 2):
            return res
    raise OracleError(f"LP status {res.status} ({mode}, m={m}): {res.message}")


def margin(z, m=None, box=True, rate=True):
    """d*: the smallest noise bound under which z[0:m] has an admissible explanation."""
    return float(_solve(z, len(z) if m is None else m, box, rate, "margin").fun)


def consistent(z, m=None, box=True, rate=True):
    return margin(z, m, box, rate) <= T.DELTA


def first_inconsistent(z, box=True, rate=True):
    """(t*, d*_at_t*, borderline). t* is the smallest index with d*(z[0:t*+1]) > DELTA, None if the whole
    run is consistent. d* is monotone in the prefix length, so the binary search is exact."""
    n = len(z)
    d_full = margin(z, n, box, rate)
    if d_full <= T.DELTA:
        return None, d_full, abs(d_full - T.DELTA) <= BORDER
    lo, hi, d_hi = 0, n, d_full          # prefix lo consistent (empty prefix), prefix hi inconsistent
    while hi - lo > 1:
        mid = (lo + hi) // 2
        d = margin(z, mid, box, rate)
        if d <= T.DELTA:
            lo = mid
        else:
            hi, d_hi = mid, d
    d_lo = margin(z, lo, box, rate) if lo > 0 else 0.0
    return hi - 1, d_hi, min(abs(d_hi - T.DELTA), abs(d_lo - T.DELTA)) <= BORDER


def offset_interval(z, box=True, rate=True):
    """[b_min, b_max]: the constant sensor offsets the whole run can not exclude; None if none."""
    lo = _solve(z, len(z), box, rate, "offset", sense=1.0)
    if lo.status != 0:
        return None
    hi = _solve(z, len(z), box, rate, "offset", sense=-1.0)
    return float(lo.x[3 * len(z)]), float(hi.x[3 * len(z)])
