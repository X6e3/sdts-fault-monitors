"""Neon Task N1: Independent verification of open MCU numbers (19 Nov 2026).

Checks all four items requested in Task N1 against checkout ~/Research/sdts-v3-a8-0e28951
(diag3_cw.py, variants F and N) on DEV run 430010 (drift_0.0005, E0, ramp, uniform, t*=695),
plus an edge-noise peak-size check on DEV seed 430070 (healthy, E0, ramp, edge, t=1..350).

Single-process, OPENBLAS_NUM_THREADS=1, read-only against the repository.
Outputs are written strictly under ~/Research/sdts-runs/v3-neon/N1/.
"""
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import numpy as np
import scipy
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.optimize._highspy import _core

REPO = Path("/home/x6e3/Research/sdts-v3-a8-0e28951")
OUT = Path("/home/x6e3/Research/sdts-runs/v3-neon/N1")
sys.path.insert(0, str(REPO / "experiments/v3/diag"))
import diag1 as G  # noqa: E402
import diag3_cw as CW  # noqa: E402

KBASIC = _core.HighsBasisStatus.kBasic
KLOWER = _core.HighsBasisStatus.kLower
KUPPER = _core.HighsBasisStatus.kUpper
STRAT_DUAL = int(_core.simplex_constants.SimplexStrategy.kSimplexStrategyDual)
STRAT_PRIMAL = int(_core.simplex_constants.SimplexStrategy.kSimplexStrategyPrimal)
INF = _core.kHighsInf

U64 = 2.0 ** -53
U32 = 2.0 ** -24


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def stats_summary(arr):
    if not arr:
        return None
    a = np.asarray(arr, dtype=float)
    return {
        "n": int(len(a)),
        "min": float(np.min(a)),
        "median": float(np.median(a)),
        "mean": float(np.mean(a)),
        "p95": float(np.percentile(a, 95)),
        "max": float(np.max(a)),
    }


# ---------------------------------------------------------------------------
# Direct LP builder matching diag3_cw.Compressed.lp (0e28951) with explicit
# column/row keys so bases can be mapped cleanly across consecutive steps.
# ---------------------------------------------------------------------------

def build_lp_data(w, t_end, meas_upto, obj_state, obj_vec):
    tau = w.tau
    meas = sorted(j for j in w.zs if tau <= j <= meas_upto and not (j == tau and w.base is not None))
    nodes = sorted({tau, obj_state, t_end, *meas})
    col_keys = []
    idx = {}
    if w.ta_path:
        for j in range(tau, t_end + 1):
            col_keys.append(("TA", j))
        nv = t_end - tau + 1
        for nd in nodes:
            idx[nd] = (nv, nv + 1, nd - tau)
            col_keys.append(("ac", nd))
            col_keys.append(("as", nd))
            nv += 2
    else:
        nv = 0
        for nd in nodes:
            idx[nd] = (nv, nv + 1, nv + 2)
            col_keys.append(("ac", nd))
            col_keys.append(("as", nd))
            col_keys.append(("TA", nd))
            nv += 3
    w0 = nv
    for j in range(tau, t_end):
        col_keys.append(("w", j))
    nv += t_end - tau

    lb = np.full(nv, CW.LO, dtype=float)
    ub = np.full(nv, CW.HI, dtype=float)
    lb[w0:], ub[w0:] = -CW.RHO, CW.RHO
    for j in meas:
        i = idx[j][1]
        zl, zu = w.zs[j] - CW.DELTA, w.zs[j] + CW.DELTA
        if w.harden:
            zl, zu = float(np.nextafter(zl, -np.inf)), float(np.nextafter(zu, np.inf))
        lb[i], ub[i] = max(lb[i], zl), min(ub[i], zu)
    if np.any(lb > ub):
        return None

    # Build A_ub first, then A_eq (fixed order for unified HiGHS matrix [A_ub; A_eq])
    ub_keys, ir, ic, iv = [], [], [], []
    b_ub_list = []
    if w.base is not None:
        x0 = idx[tau]
        for i, d in enumerate(w.D):
            for c in range(3):
                if d[c] != 0.0:
                    ir.append(i)
                    ic.append(x0[c])
                    iv.append(float(d[c]))
            ub_keys.append(("D0", i))
            b_ub_list.append(float(w.base[i]))
    q = len(ub_keys)
    A_ub = sp.csr_matrix((iv, (ir, ic)), shape=(q, nv)) if q else None
    b_ub = np.asarray(b_ub_list, dtype=float) if q else None

    eq_keys, er, ec, ev = [], [], [], []
    r = 0
    for a, b in zip(nodes, nodes[1:]):
        L, xa, xb = b - a, idx[a], idx[b]
        for c in (0, 1) if w.ta_path else (0, 1, 2):
            er.append(r); ec.append(xb[c]); ev.append(1.0)
            for col_c in range(3):
                val = float(CW.POW[L][c, col_c])
                if val != 0.0:
                    er.append(r); ec.append(xa[col_c]); ev.append(-val)
            for k in range(L):
                val = float(CW.GEN[k][c])
                if val != 0.0:
                    er.append(r); ec.append(w0 + (b - 1 - k - tau)); ev.append(-val)
            eq_keys.append(("seg", a, b, c))
            r += 1
    if w.ta_path:
        for j in range(t_end - tau):
            er += [r, r, r]
            ec += [j + 1, j, w0 + j]
            ev += [1.0, -1.0, -1.0]
            eq_keys.append(("ta_eq", tau + j))
            r += 1
    if w.base is None:
        x0 = idx[tau]
        er += [r, r, r + 1, r + 1]
        ec += [x0[0], x0[2], x0[1], x0[2]]
        ev += [1.0, -1.0, 1.0, -1.0]
        eq_keys.append(("init", 0))
        eq_keys.append(("init", 1))
        r += 2
    A_eq = sp.csr_matrix((ev, (er, ec)), shape=(r, nv)) if r else None
    b_eq = np.zeros(r, dtype=float) if r else None

    cvec = np.zeros(nv, dtype=float)
    cvec[list(idx[obj_state])] = -np.asarray(obj_vec, dtype=float)

    return {
        "c": cvec, "A_ub": A_ub, "b_ub": b_ub, "A_eq": A_eq, "b_eq": b_eq,
        "lb": lb, "ub": ub, "col_keys": col_keys, "row_keys": ub_keys + eq_keys,
        "nodes": nodes, "idx": idx, "tau": tau, "t_end": t_end, "m_ub": q, "m_eq": r,
        "nv": nv, "m": q + r, "meas": meas,
    }


def make_highs_lp(data, dtype=np.float64):
    A_list = []
    rl_list, ru_list = [], []
    if data["A_ub"] is not None:
        A_list.append(data["A_ub"])
        rl_list.append(np.full(data["m_ub"], -INF, dtype=np.float64))
        ru_list.append(data["b_ub"].astype(dtype).astype(np.float64))
    if data["A_eq"] is not None:
        A_list.append(data["A_eq"])
        rl_list.append(np.zeros(data["m_eq"], dtype=np.float64))
        ru_list.append(np.zeros(data["m_eq"], dtype=np.float64))
    A_csc = sp.vstack(A_list, format="csc")
    A_vals = A_csc.data.astype(dtype).astype(np.float64)
    lp = _core.HighsLp()
    lp.num_col_ = data["nv"]
    lp.num_row_ = data["m"]
    lp.col_cost_ = data["c"].astype(dtype).astype(np.float64)
    lp.col_lower_ = data["lb"].astype(dtype).astype(np.float64)
    lp.col_upper_ = data["ub"].astype(dtype).astype(np.float64)
    lp.row_lower_ = np.concatenate(rl_list)
    lp.row_upper_ = np.concatenate(ru_list)
    lp.a_matrix_.format_ = _core.MatrixFormat.kColwise
    lp.a_matrix_.start_ = A_csc.indptr.astype(np.int32)
    lp.a_matrix_.index_ = A_csc.indices.astype(np.int32)
    lp.a_matrix_.value_ = A_vals
    return lp, A_csc


def solve_highs(data, basis_in=None, strategy=STRAT_DUAL, dtype=np.float64, tol=None):
    h = _core._Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("presolve", "off")
    h.setOptionValue("simplex_strategy", strategy)
    if tol is not None:
        h.setOptionValue("primal_feasibility_tolerance", tol)
        h.setOptionValue("dual_feasibility_tolerance", tol)
    lp, A_csc = make_highs_lp(data, dtype=dtype)
    h.passModel(lp)
    set_st = None
    if basis_in is not None:
        set_st = h.setBasis(basis_in)
    h.run()
    ms = h.getModelStatus()
    info = h.getInfo()
    sol = h.getSolution()
    bas = h.getBasis()
    row_dual = np.asarray(sol.row_dual, dtype=np.float64)
    m_ub = data["m_ub"]
    y = np.maximum(0.0, -row_dual[:m_ub]) if m_ub else np.zeros(0, dtype=np.float64)
    nu = -row_dual[m_ub:] if data["m_eq"] else np.zeros(0, dtype=np.float64)
    return {
        "status": ms,
        "val": -float(info.objective_function_value),
        "nit": int(info.simplex_iteration_count),
        "y": y,
        "nu": nu,
        "x": np.asarray(sol.col_value, dtype=np.float64),
        "basis": bas,
        "set_st": str(set_st) if set_st is not None else None,
        "A_csc": A_csc,
        "h": h,
    }


def extract_basis_matrix(A_csc, bas, m):
    basic_cols = [j for j, st in enumerate(bas.col_status) if st == KBASIC]
    basic_rows = [i for i, st in enumerate(bas.row_status) if st == KBASIC]
    assert len(basic_cols) + len(basic_rows) == m, f"basic count mismatch: {len(basic_cols)}+{len(basic_rows)} != {m}"
    if basic_rows:
        slacks = -sp.eye(m, format="csc")[:, basic_rows]
        B = sp.hstack([A_csc[:, basic_cols], slacks], format="csc")
    else:
        B = A_csc[:, basic_cols].tocsc()
    return B, basic_cols, basic_rows


def map_step_basis(prev_data, prev_bas, cur_data, ta_path):
    """Map optimal basis from step t-1 to step t (same tau) with exact basic count = cur_data['m']."""
    if prev_data["tau"] != cur_data["tau"] or prev_data["t_end"] + 1 != cur_data["t_end"]:
        return None
    t_prev = prev_data["t_end"]
    t_cur = cur_data["t_end"]
    # Check whether t_prev stayed as a node (kept) or shifted to t_cur (dropped)
    prev_nodes = prev_data["nodes"]
    cur_nodes = cur_data["nodes"]
    kept_prev = (t_prev in cur_nodes)

    p_col_map = {k: st for k, st in zip(prev_data["col_keys"], prev_bas.col_status)}
    p_row_map = {k: st for k, st in zip(prev_data["row_keys"], prev_bas.row_status)}

    # Tail predecessor before t_prev
    p_tail = prev_nodes[-2]

    new_col_st = []
    for k in cur_data["col_keys"]:
        if k in p_col_map:
            new_col_st.append(p_col_map[k])
        elif not kept_prev and k[0] in ("ac", "as", "TA") and k[1] == t_cur and (k[0], t_prev) in p_col_map:
            # In N (ta_path=False), TA at t_prev shifts to t_cur; in F (ta_path=True), ac/as at t_prev shift to t_cur
            if ta_path and k[0] == "TA":
                new_col_st.append(KBASIC)
            else:
                new_col_st.append(p_col_map[(k[0], t_prev)])
        elif k == ("w", t_prev):
            new_col_st.append(KLOWER)
        elif k[0] in ("TA", "ac", "as") and k[1] == t_cur:
            new_col_st.append(KBASIC)
        else:
            return None

    new_row_st = []
    for k in cur_data["row_keys"]:
        if k in p_row_map:
            new_row_st.append(p_row_map[k])
        elif not kept_prev and k[0] == "seg" and k[1] == p_tail and k[2] == t_cur:
            new_row_st.append(p_row_map[("seg", p_tail, t_prev, k[3])])
        elif k[0] == "seg" and k[1] == t_prev and k[2] == t_cur:
            new_row_st.append(KLOWER)
        elif k == ("ta_eq", t_prev):
            new_row_st.append(KLOWER)
        else:
            return None

    nb = sum(1 for s in new_col_st if s == KBASIC) + sum(1 for s in new_row_st if s == KBASIC)
    if nb != cur_data["m"]:
        return None
    bas = _core.HighsBasis()
    bas.col_status = new_col_st
    bas.row_status = new_row_st
    return bas


# ---------------------------------------------------------------------------
# Certified bound evaluators (float64 exact, float32 u=2^-24, actual float32,
# mixed-precision float32 duals -> float64 cert, and int64 Q30 x Q24 cert).
# ---------------------------------------------------------------------------

def _gam(n, u):
    return (n * u) / (1.0 - n * u)


def cert_bound_general(data, y, nu, u=U64, harden=True, arith_f32=False):
    c = data["c"]
    lb, ub = data["lb"], data["ub"]
    if arith_f32:
        c = c.astype(np.float32)
        lb, ub = lb.astype(np.float32), ub.astype(np.float32)
        y = y.astype(np.float32)
        nu = nu.astype(np.float32)
        s = c.copy()
        sa = np.abs(c)
        k = 1
        parts = []
        if data["A_ub"] is not None:
            A = data["A_ub"].astype(np.float32)
            b = data["b_ub"].astype(np.float32)
            s = (s + (A.T @ y).astype(np.float32)).astype(np.float32)
            sa = (sa + (abs(A).T @ y).astype(np.float32)).astype(np.float32)
            k += CW._colnnz(data["A_ub"])
            parts.append((y * b).astype(np.float32))
        if data["A_eq"] is not None:
            A = data["A_eq"].astype(np.float32)
            b = data["b_eq"].astype(np.float32)
            s = (s + (A.T @ nu).astype(np.float32)).astype(np.float32)
            sa = (sa + (abs(A).T @ np.abs(nu)).astype(np.float32)).astype(np.float32)
            k += CW._colnnz(data["A_eq"])
            parts.append((nu * b).astype(np.float32))
        xm = np.maximum(np.abs(lb), np.abs(ub)).astype(np.float32)
        parts.append((-np.minimum((s * lb).astype(np.float32), (s * ub).astype(np.float32))).astype(np.float32))
        col_err = (np.float32(2.0 * _gam(k + 1, u)) * sa * xm).astype(np.float32)
        parts.append(col_err)
        harden_err = (np.float32(2.0 * u) * (sa - np.abs(c)) * xm).astype(np.float32) if harden else np.zeros_like(xm)
        if harden:
            parts.append(harden_err)
        p = np.concatenate(parts).astype(np.float64)
        tot = math.fsum(p)
        outer = 4.0 * (_gam(4, u) * math.fsum(np.abs(p)) + u * abs(tot))
        return {
            "bound": float(tot + outer),
            "col_err": float(math.fsum(col_err.astype(np.float64))),
            "harden_err": float(math.fsum(harden_err.astype(np.float64))),
            "outer_err": float(outer),
            "k": k,
            "sb": float(math.fsum((sa.astype(np.float64) * xm.astype(np.float64)))),
        }

    s = c.astype(np.float64).copy()
    sa = np.abs(c).astype(np.float64)
    k = 1
    parts = []
    if data["A_ub"] is not None:
        A = data["A_ub"]
        s += A.T @ y
        sa += abs(A).T @ y
        k += CW._colnnz(A)
        parts.append(y * data["b_ub"])
    if data["A_eq"] is not None:
        A = data["A_eq"]
        s += A.T @ nu
        sa += abs(A).T @ np.abs(nu)
        k += CW._colnnz(A)
        parts.append(nu * data["b_eq"])
    xm = np.maximum(np.abs(lb), np.abs(ub))
    parts.append(-np.minimum(s * lb, s * ub))
    col_err = 2.0 * _gam(k + 1, u) * sa * xm
    parts.append(col_err)
    harden_err = 2.0 * u * (sa - np.abs(c)) * xm if harden else np.zeros_like(xm)
    if harden:
        parts.append(harden_err)
    p = np.concatenate(parts)
    tot = math.fsum(p)
    outer = 4.0 * (_gam(4, u) * math.fsum(np.abs(p)) + u * abs(tot))
    return {
        "bound": float(tot + outer),
        "col_err": float(math.fsum(col_err)),
        "harden_err": float(math.fsum(harden_err)),
        "outer_err": float(outer),
        "k": k,
        "sb": float(math.fsum(sa * xm)),
    }


def cert_bound_int64_q30_q24(data, y_in, nu_in):
    """Exact int64 fixed-point weak-duality upper bound using Q30 data and Q24 multipliers.

    Every multiply-accumulate stays inside signed int64 (< 2^63 - 1).
    Matrix quantization error |a_exact - a_q30| <= (0.5 * 2^-30 + 2 * 2^-53 * |a|) <= 2^-30
    is enclosed upward in exact integer arithmetic.
    """
    SA = 1 << 30
    SY = 1 << 24
    I64_MAX = (1 << 63) - 1
    max_abs_acc = 0

    n = data["nv"]
    c_q30 = [int(round(float(v) * SA)) for v in data["c"]]
    # c has exact values 0, +/-1 or unit direction entries; bound |c - c_q30/SA| <= 0.5/SA
    c_err_q30 = [1 if abs(float(v) * SA - cq) > 0.0 else 0 for v, cq in zip(data["c"], c_q30)]

    # Outward-rounded bounds in Q30: lb_q30 <= lb * SA, ub_q30 >= ub * SA
    lb_q30 = [math.floor(float(v) * SA) for v in data["lb"]]
    ub_q30 = [math.ceil(float(v) * SA) for v in data["ub"]]
    xm_q30 = [max(abs(l), abs(u)) for l, u in zip(lb_q30, ub_q30)]

    y_q24 = [max(0, int(round(float(v) * SY))) for v in y_in]
    nu_q24 = [int(round(float(v) * SY)) for v in nu_in]

    s_q54 = [cq * SY for cq in c_q30]
    # Sum of |lambda_i| * (0.5 + 2*u64*|a|*SA <= 1 in Q30) -> per-col error in Q54
    col_err_q54 = [ce * SY for ce in c_err_q30]

    b_dot_q54 = 0
    if data["A_ub"] is not None:
        # b_ub rounded upward in Q30 since y >= 0
        b_q30 = [math.ceil(float(v) * SA) for v in data["b_ub"]]
        for bi, yi in zip(b_q30, y_q24):
            b_dot_q54 += bi * yi
            max_abs_acc = max(max_abs_acc, abs(b_dot_q54))
        co = data["A_ub"].tocoo()
        for i, j, a in zip(co.row, co.col, co.data):
            yi = y_q24[i]
            if yi == 0:
                continue
            aq = int(round(float(a) * SA))
            s_q54[j] += aq * yi
            col_err_q54[j] += yi  # |a_exact - aq/SA| < 1 / SA
            max_abs_acc = max(max_abs_acc, abs(s_q54[j]), abs(col_err_q54[j]))

    if data["A_eq"] is not None:
        co = data["A_eq"].tocoo()
        for i, j, a in zip(co.row, co.col, co.data):
            ni = nu_q24[i]
            if ni == 0:
                continue
            aq = int(round(float(a) * SA))
            s_q54[j] += aq * ni
            col_err_q54[j] += abs(ni)
            max_abs_acc = max(max_abs_acc, abs(s_q54[j]), abs(col_err_q54[j]))

    # Final sum in Q84? Keep product inside int64 by shifting s_q54 -> Q30 (outward interval [s_lo, s_hi])!
    # s_q54 / 2^24 has exact floor and ceil in Q30:
    # For any x in [lb, ub], -s*x <= -min(s_lo*lb, s_lo*ub, s_hi*lb, s_hi*ub)
    # Wait: (Q30 * Q30) = Q60 fits in signed int64 (max ~ 20 * 2 * 2^60? Wait: check max |s_q30 * xm_q30|!)
    # Even safer for int64: shift s_q54 to Q28 (>> 26), xm to Q28 (ceil >> 2) => product is Q56!
    # Let's track BOTH Q60-safe (Q28 x Q28 -> Q56) exact integer bound AND peak accumulator bits!
    SH_S = 26  # 54 - 26 = 28 (Q28)
    SH_X = 2   # 30 - 2  = 28 (Q28)
    # Convert b_dot_q54 (Q54) -> Q56 (<< 2)
    tot_q56 = b_dot_q54 << 2
    max_abs_acc = max(max_abs_acc, abs(tot_q56))
    for j in range(n):
        # Interval for true s_j in Q54: [s_q54[j] - col_err_q54[j], s_q54[j] + col_err_q54[j]]
        lo_s54 = s_q54[j] - col_err_q54[j]
        hi_s54 = s_q54[j] + col_err_q54[j]
        # Round outward to Q28
        lo_s28 = lo_s54 >> SH_S  # Python >> is arithmetic floor
        hi_s28 = -((-hi_s54) >> SH_S)  # exact ceil
        lb_28 = lb_q30[j] >> SH_X
        ub_28 = -((-ub_q30[j]) >> SH_X)
        m_q56 = min(lo_s28 * lb_28, lo_s28 * ub_28, hi_s28 * lb_28, hi_s28 * ub_28)
        tot_q56 += -m_q56
        max_abs_acc = max(max_abs_acc, abs(tot_q56), abs(m_q56))

    assert max_abs_acc <= I64_MAX, f"int64 overflow: {max_abs_acc}"
    return {
        "bound": tot_q56 / float(1 << 56),
        "max_abs_acc": int(max_abs_acc),
        "max_acc_bits": int(max_abs_acc.bit_length()),
        "fits_int64": bool(max_abs_acc <= I64_MAX),
    }


def basis_refine_duals_f64(data, bas):
    """Given a basis (from a float32-data solve), solve B^T [y_B; nu_B] = -c_B in float64."""
    A_list = []
    if data["A_ub"] is not None:
        A_list.append(data["A_ub"])
    if data["A_eq"] is not None:
        A_list.append(data["A_eq"])
    A_csc = sp.vstack(A_list, format="csc")
    m = data["m"]
    B, basic_cols, basic_rows = extract_basis_matrix(A_csc, bas, m)
    # Basis columns: [A[:, basic_cols], -I[:, basic_rows]]
    # Objective in min c^T x + 0^T s: c_B = [c[basic_cols], 0]
    # Dual optimality: B^T pi = c_B  (where HiGHS row_dual = pi, y = max(0, -pi_ub), nu = -pi_eq)
    c_B = np.zeros(m, dtype=np.float64)
    c_B[: len(basic_cols)] = data["c"][basic_cols]
    lu = spla.splu(B.T.tocsc(), permc_spec="COLAMD")
    pi = lu.solve(c_B)
    m_ub = data["m_ub"]
    y = np.maximum(0.0, -pi[:m_ub]) if m_ub else np.zeros(0, dtype=np.float64)
    nu = -pi[m_ub:] if data["m_eq"] else np.zeros(0, dtype=np.float64)
    return y, nu


def greedy_tsp_order(D):
    used = [0]
    rem = set(range(1, len(D)))
    while rem:
        cur = used[-1]
        nxt = max(rem, key=lambda j: float(np.dot(D[cur], D[j])))
        used.append(nxt)
        rem.remove(nxt)
    return used


def run_430010_audit(variant_name, K=64):
    """Run full 430010 audit for variant F (or N): LU fill, float32/mixed/int64 certs, warm starts."""
    run = CW.S.run(430010, next(c for c in CW.T.CELLS if c.name == "drift_0.0005"), "E0", "ramp", "uniform")
    zs = G.zs_of(run)
    cy = CW.V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    D_tsp = greedy_tsp_order(cy.D)

    w = CW.make(variant_name, cy)
    w.zs[0] = zs[0]
    if getattr(w, "track", False):
        w.last_active[0] = 0

    # Metrics containers
    lu_step = {k: [] for k in ("m", "n", "nnz_A", "nnz_B", "nnz_colamd", "fill_colamd", "nnz_mmd", "fill_mmd", "nnz_nat", "fill_nat")}
    lu_fold = {k: [] for k in ("m", "n", "nnz_A", "nnz_B", "nnz_colamd", "fill_colamd", "nnz_mmd", "fill_mmd", "nnz_nat", "fill_nat")}

    cert_step_f32_form = []
    cert_step_f32_arith = []
    cert_fold_f32_form = []
    cert_fold_f32_arith = []
    cert_fold_f32_col = []
    cert_fold_f32_harden = []
    cert_fold_f32_outer = []

    cert_step_y32_f64 = []
    cert_fold_y32_f64 = []
    cert_step_f32solve_tol6_raw = []
    cert_fold_f32solve_tol6_raw = []
    cert_step_f32solve_tol6_ref = []
    cert_fold_f32solve_tol6_ref = []
    cert_step_f32solve_tol5_raw = []
    cert_fold_f32solve_tol5_raw = []
    cert_step_f32solve_tol5_ref = []
    cert_fold_f32solve_tol5_ref = []

    cert_step_int64 = []
    cert_fold_int64 = []
    int64_max_bits = 0
    int64_sound_violations = 0
    f32_solve_fail_count = {"tol6": 0, "tol5": 0}

    # Warm-start stats
    nit_cold_step = []
    nit_warm_sep_dual = []      # up(t-1)->up(t), dn(t-1)->dn(t)
    nit_warm_sep_primal = []
    nit_warm_shared_dual = []   # dn(t-1)->up(t)->dn(t)
    warm_step_kept_nit = []
    warm_step_dropped_nit = []
    warm_step_max_obj_diff = 0.0
    warm_step_mapped_ok = 0
    warm_step_mapped_fail = 0
    primal_step_nonopt = []
    primal_fold_nonopt = []

    nit_fold_cold = []
    nit_fold_warm_dual_def = []
    nit_fold_warm_dual_tsp = []
    nit_fold_warm_primal_tsp = []
    nit_fold_per_fold_cold = []
    nit_fold_per_fold_primal_tsp = []
    nit_fold_per_fold_dual_tsp = []
    warm_fold_max_obj_diff = 0.0

    prev_step = {"up": None, "dn": None, "last": None}
    alarm_detail = None
    det = None

    for t in range(1, 700):
        w.now = t
        # Solve up and dn via official diag3_cw window state (we drive w directly with build_lp_data + HiGHS
        # AND verify against CW.certified_max!).
        step_res = {}
        for side, vec in (("up", (0.0, 1.0, 0.0)), ("dn", (0.0, -1.0, 0.0))):
            data = build_lp_data(w, t, t - 1, t, vec)
            assert data is not None, f"infeasible at {t}"
            sol_cold = solve_highs(data, basis_in=None, strategy=STRAT_DUAL)
            assert sol_cold["status"] == _core.HighsModelStatus.kOptimal
            nit_cold_step.append(sol_cold["nit"])
            step_res[side] = (data, sol_cold)

            # Warm start from previous step (same tau)
            if prev_step[side] is not None and prev_step[side][0]["tau"] == data["tau"]:
                p_data, p_sol, prev_was_kept = prev_step[side]
                mb = map_step_basis(p_data, p_sol["basis"], data, w.ta_path)
                if mb is not None:
                    warm_step_mapped_ok += 1
                    sw_d = solve_highs(data, basis_in=mb, strategy=STRAT_DUAL)
                    assert sw_d["status"] == _core.HighsModelStatus.kOptimal
                    warm_step_max_obj_diff = max(warm_step_max_obj_diff, abs(sw_d["val"] - sol_cold["val"]))
                    nit_warm_sep_dual.append(sw_d["nit"])
                    if prev_was_kept:
                        warm_step_kept_nit.append(sw_d["nit"])
                    else:
                        warm_step_dropped_nit.append(sw_d["nit"])
                    sw_p = solve_highs(data, basis_in=mb, strategy=STRAT_PRIMAL)
                    if sw_p["status"] == _core.HighsModelStatus.kOptimal:
                        nit_warm_sep_primal.append(sw_p["nit"])
                    else:
                        primal_step_nonopt.append((t, side, str(sw_p["status"])))
                else:
                    warm_step_mapped_fail += 1

            # Shared basis: up(t) from dn(t-1), dn(t) from up(t)
            if side == "dn":
                # same matrix/nodes as up(t), just flipped c!
                up_bas = step_res["up"][1]["basis"]
                mb_sh = _core.HighsBasis()
                mb_sh.col_status = list(up_bas.col_status)
                mb_sh.row_status = list(up_bas.row_status)
                sw_sh = solve_highs(data, basis_in=mb_sh, strategy=STRAT_DUAL)
                nit_warm_shared_dual.append(sw_sh["nit"])

            # Sparse LU audit on t = 300..695
            if 300 <= t <= 695:
                B, _, _ = extract_basis_matrix(sol_cold["A_csc"], sol_cold["basis"], data["m"])
                lu_c = spla.splu(B, permc_spec="COLAMD")
                lu_m = spla.splu(B, permc_spec="MMD_AT_PLUS_A")
                lu_n = spla.splu(B, permc_spec="NATURAL")
                lu_step["m"].append(data["m"])
                lu_step["n"].append(data["nv"])
                lu_step["nnz_A"].append(int(sol_cold["A_csc"].nnz))
                lu_step["nnz_B"].append(int(B.nnz))
                lu_step["nnz_colamd"].append(int(lu_c.nnz))
                lu_step["fill_colamd"].append(float(lu_c.nnz / B.nnz))
                lu_step["nnz_mmd"].append(int(lu_m.nnz))
                lu_step["fill_mmd"].append(float(lu_m.nnz / B.nnz))
                lu_step["nnz_nat"].append(int(lu_n.nnz))
                lu_step["fill_nat"].append(float(lu_n.nnz / B.nnz))

            # Cert audits on t >= 300 (and t == 695!)
            if t >= 300:
                v64 = sol_cold["val"]
                c32_form = cert_bound_general(data, sol_cold["y"], sol_cold["nu"], u=U32, harden=True, arith_f32=False)
                c32_arith = cert_bound_general(data, sol_cold["y"], sol_cold["nu"], u=U32, harden=True, arith_f32=True)
                cert_step_f32_form.append((c32_form["bound"] - v64) * 1e3)
                cert_step_f32_arith.append((c32_arith["bound"] - v64) * 1e3)

                # Level 3a: f64 duals rounded to f32, checked in f64
                y32 = sol_cold["y"].astype(np.float32).astype(np.float64)
                nu32 = sol_cold["nu"].astype(np.float32).astype(np.float64)
                c_y32 = cert_bound_general(data, y32, nu32, u=U64, harden=True)
                cert_step_y32_f64.append((c_y32["bound"] - v64) * 1e3)

                # Level 3c: int64 Q30 x Q24 on f64 duals
                ci64 = cert_bound_int64_q30_q24(data, sol_cold["y"], sol_cold["nu"])
                int64_max_bits = max(int64_max_bits, ci64["max_acc_bits"])
                if ci64["bound"] < v64 - 1e-12:
                    int64_sound_violations += 1
                cert_step_int64.append((ci64["bound"] - v64) * 1e3)

                # Level 3b: float32-quantized LP solve at tol=1e-6 and 1e-5 (every 10th step + t=695 to stay fast)
                if t % 10 == 0 or t == 695:
                    for tag, tol, raw_lst, ref_lst in (
                        ("tol6", 1e-6, cert_step_f32solve_tol6_raw, cert_step_f32solve_tol6_ref),
                        ("tol5", 1e-5, cert_step_f32solve_tol5_raw, cert_step_f32solve_tol5_ref),
                    ):
                        s32 = solve_highs(data, dtype=np.float32, tol=tol)
                        if s32["status"] == _core.HighsModelStatus.kOptimal:
                            yr = s32["y"].astype(np.float32).astype(np.float64)
                            nr = s32["nu"].astype(np.float32).astype(np.float64)
                            cr = cert_bound_general(data, yr, nr, u=U64, harden=True)
                            raw_lst.append((cr["bound"] - v64) * 1e3)
                            y_ref, nu_ref = basis_refine_duals_f64(data, s32["basis"])
                            cref = cert_bound_general(data, y_ref, nu_ref, u=U64, harden=True)
                            ref_lst.append((cref["bound"] - v64) * 1e3)
                        else:
                            f32_solve_fail_count[tag] += 1

        up_data, up_sol = step_res["up"]
        dn_data, dn_sol = step_res["dn"]
        upper, lower = up_sol["val"], -dn_sol["val"]
        m_val = G.margin(lower, upper, zs[t])

        # Exact alarm check at detection (or t == 695)
        zl_out = float(np.nextafter(zs[t] - CW.DELTA, -np.inf)) if w.harden else zs[t] - CW.DELTA
        zu_out = float(np.nextafter(zs[t] + CW.DELTA, np.inf)) if w.harden else zs[t] + CW.DELTA
        if upper < zs[t] - CW.DELTA or lower > zs[t] + CW.DELTA or t == 695:
            cup64 = cert_bound_general(up_data, up_sol["y"], up_sol["nu"], u=U64, harden=w.harden)["bound"]
            cdn64 = cert_bound_general(dn_data, dn_sol["y"], dn_sol["nu"], u=U64, harden=w.harden)["bound"]
            cm64 = 1e3 * min(zu_out + cdn64, cup64 - zl_out)

            # Detailed breakdown at alarm t=695
            up_f32_form = cert_bound_general(up_data, up_sol["y"], up_sol["nu"], u=U32, harden=True, arith_f32=False)
            dn_f32_form = cert_bound_general(dn_data, dn_sol["y"], dn_sol["nu"], u=U32, harden=True, arith_f32=False)
            up_f32_arith = cert_bound_general(up_data, up_sol["y"], up_sol["nu"], u=U32, harden=True, arith_f32=True)
            dn_f32_arith = cert_bound_general(dn_data, dn_sol["y"], dn_sol["nu"], u=U32, harden=True, arith_f32=True)

            up_y32_f64 = cert_bound_general(up_data, up_sol["y"].astype(np.float32).astype(np.float64), up_sol["nu"].astype(np.float32).astype(np.float64), u=U64, harden=True)
            dn_y32_f64 = cert_bound_general(dn_data, dn_sol["y"].astype(np.float32).astype(np.float64), dn_sol["nu"].astype(np.float32).astype(np.float64), u=U64, harden=True)

            up_i64 = cert_bound_int64_q30_q24(up_data, up_sol["y"], up_sol["nu"])
            dn_i64 = cert_bound_int64_q30_q24(dn_data, dn_sol["y"], dn_sol["nu"])

            f32_alarm = {}
            for tag, tol in (("tol6", 1e-6), ("tol5", 1e-5)):
                su = solve_highs(up_data, dtype=np.float32, tol=tol)
                sd = solve_highs(dn_data, dtype=np.float32, tol=tol)
                cu_raw = cert_bound_general(up_data, su["y"].astype(np.float32).astype(np.float64), su["nu"].astype(np.float32).astype(np.float64), u=U64, harden=True)["bound"]
                cd_raw = cert_bound_general(dn_data, sd["y"].astype(np.float32).astype(np.float64), sd["nu"].astype(np.float32).astype(np.float64), u=U64, harden=True)["bound"]
                yu_r, nuu_r = basis_refine_duals_f64(up_data, su["basis"])
                yd_r, nud_r = basis_refine_duals_f64(dn_data, sd["basis"])
                cu_ref = cert_bound_general(up_data, yu_r, nuu_r, u=U64, harden=True)["bound"]
                cd_ref = cert_bound_general(dn_data, yd_r, nud_r, u=U64, harden=True)["bound"]
                f32_alarm[tag] = {
                    "up_raw_gap_mC": (cu_raw - up_sol["val"]) * 1e3,
                    "dn_raw_gap_mC": (cd_raw - dn_sol["val"]) * 1e3,
                    "margin_raw_mC": 1e3 * min(zu_out + cd_raw, cu_raw - zl_out),
                    "up_refined_gap_mC": (cu_ref - up_sol["val"]) * 1e3,
                    "dn_refined_gap_mC": (cd_ref - dn_sol["val"]) * 1e3,
                    "margin_refined_mC": 1e3 * min(zu_out + cd_ref, cu_ref - zl_out),
                }

            alarm_detail = {
                "t": t,
                "primal_margin_mC": float(m_val * 1e3),
                "cert64_margin_mC": float(cm64),
                "f32_form_up_gap_mC": float((up_f32_form["bound"] - up_sol["val"]) * 1e3),
                "f32_form_dn_gap_mC": float((dn_f32_form["bound"] - dn_sol["val"]) * 1e3),
                "f32_form_margin_mC": float(1e3 * min(zu_out + dn_f32_form["bound"], up_f32_form["bound"] - zl_out)),
                "f32_arith_up_gap_mC": float((up_f32_arith["bound"] - up_sol["val"]) * 1e3),
                "f32_arith_dn_gap_mC": float((dn_f32_arith["bound"] - dn_sol["val"]) * 1e3),
                "f32_arith_margin_mC": float(1e3 * min(zu_out + dn_f32_arith["bound"], up_f32_arith["bound"] - zl_out)),
                "f32_form_up_breakdown_mC": {
                    "col_err": up_f32_form["col_err"] * 1e3,
                    "harden_err": up_f32_form["harden_err"] * 1e3,
                    "outer_err": up_f32_form["outer_err"] * 1e3,
                    "k": up_f32_form["k"],
                    "sb": up_f32_form["sb"],
                },
                "f32_form_dn_breakdown_mC": {
                    "col_err": dn_f32_form["col_err"] * 1e3,
                    "harden_err": dn_f32_form["harden_err"] * 1e3,
                    "outer_err": dn_f32_form["outer_err"] * 1e3,
                    "k": dn_f32_form["k"],
                    "sb": dn_f32_form["sb"],
                },
                "y32_checked_f64_up_gap_mC": float((up_y32_f64["bound"] - up_sol["val"]) * 1e3),
                "y32_checked_f64_dn_gap_mC": float((dn_y32_f64["bound"] - dn_sol["val"]) * 1e3),
                "y32_checked_f64_margin_mC": float(1e3 * min(zu_out + dn_y32_f64["bound"], up_y32_f64["bound"] - zl_out)),
                "int64_up_gap_mC": float((up_i64["bound"] - up_sol["val"]) * 1e3),
                "int64_dn_gap_mC": float((dn_i64["bound"] - dn_sol["val"]) * 1e3),
                "int64_margin_mC": float(1e3 * min(zu_out + dn_i64["bound"], up_i64["bound"] - zl_out)),
                "int64_max_bits": max(up_i64["max_acc_bits"], dn_i64["max_acc_bits"]),
                "f32_data_solve": f32_alarm,
            }
            if cm64 < 0:
                det = t
                break

        # Keep/drop measurement z_t (exact diag3_cw_dev rule)
        was_kept = False
        if not (lower >= zs[t] - CW.DELTA and upper <= zs[t] + CW.DELTA):
            was_kept = True
            if getattr(w, "track", False):
                w.keep(t, zs[t])
            else:
                w.zs[t] = zs[t]
            if K is not None and sum(1 for j in w.zs if j > w.tau) > K:
                w.evict()
        prev_step["up"] = (up_data, up_sol, was_kept)
        prev_step["dn"] = (dn_data, dn_sol, was_kept)

        # Fold every B=16 steps when t - w.tau > W + B
        if t - w.tau > CW.W + CW.B:
            tau2 = w.tau + CW.B
            vals = []
            # Build persistent HiGHS models for warm-start fold comparisons
            d0_data = build_lp_data(w, t, t, tau2, w.D[0])
            obj_cols = np.array(list(d0_data["idx"][tau2]), dtype=np.int32)

            # Warm dual (default order)
            h_wd = _core._Highs()
            h_wd.setOptionValue("output_flag", False)
            h_wd.setOptionValue("presolve", "off")
            h_wd.setOptionValue("simplex_strategy", STRAT_DUAL)
            lp_base, _ = make_highs_lp(d0_data)
            h_wd.passModel(lp_base)

            # Warm dual (TSP order)
            h_wt = _core._Highs()
            h_wt.setOptionValue("output_flag", False)
            h_wt.setOptionValue("presolve", "off")
            h_wt.setOptionValue("simplex_strategy", STRAT_DUAL)
            h_wt.passModel(lp_base)

            # Warm primal (TSP order: first direction dual, remaining 41 primal!)
            h_wp = _core._Highs()
            h_wp.setOptionValue("output_flag", False)
            h_wp.setOptionValue("presolve", "off")
            h_wp.setOptionValue("simplex_strategy", STRAT_DUAL)
            h_wp.passModel(lp_base)

            fold_cold_sum = 0
            fold_dualtsp_sum = 0
            fold_primaltsp_sum = 0
            cold_vals_by_i = {}

            for i, d in enumerate(w.D):
                fd = build_lp_data(w, t, t, tau2, d)
                sc = solve_highs(fd, strategy=STRAT_DUAL)
                assert sc["status"] == _core.HighsModelStatus.kOptimal
                v64 = sc["val"]
                cold_vals_by_i[i] = v64
                nit_fold_cold.append(sc["nit"])
                fold_cold_sum += sc["nit"]

                cub = cert_bound_general(fd, sc["y"], sc["nu"], u=U64, harden=w.harden)["bound"]
                vals.append(max(v64 + CW.PAD, cub))

                # Warm dual default order
                for col, val in zip(obj_cols, -np.asarray(d, dtype=np.float64)):
                    h_wd.changeColCost(int(col), float(val))
                h_wd.run()
                assert h_wd.getModelStatus() == _core.HighsModelStatus.kOptimal
                nit_wd = int(h_wd.getInfo().simplex_iteration_count)
                if i > 0:
                    nit_fold_warm_dual_def.append(nit_wd)
                warm_fold_max_obj_diff = max(warm_fold_max_obj_diff, abs(-h_wd.getInfo().objective_function_value - v64))

                # Sparse LU & Cert audits on folds in [300, 695]
                if 300 <= t <= 695:
                    B, _, _ = extract_basis_matrix(sc["A_csc"], sc["basis"], fd["m"])
                    lu_c = spla.splu(B, permc_spec="COLAMD")
                    lu_m = spla.splu(B, permc_spec="MMD_AT_PLUS_A")
                    lu_n = spla.splu(B, permc_spec="NATURAL")
                    lu_fold["m"].append(fd["m"])
                    lu_fold["n"].append(fd["nv"])
                    lu_fold["nnz_A"].append(int(sc["A_csc"].nnz))
                    lu_fold["nnz_B"].append(int(B.nnz))
                    lu_fold["nnz_colamd"].append(int(lu_c.nnz))
                    lu_fold["fill_colamd"].append(float(lu_c.nnz / B.nnz))
                    lu_fold["nnz_mmd"].append(int(lu_m.nnz))
                    lu_fold["fill_mmd"].append(float(lu_m.nnz / B.nnz))
                    lu_fold["nnz_nat"].append(int(lu_n.nnz))
                    lu_fold["fill_nat"].append(float(lu_n.nnz / B.nnz))

                    c32_f = cert_bound_general(fd, sc["y"], sc["nu"], u=U32, harden=True, arith_f32=False)
                    c32_a = cert_bound_general(fd, sc["y"], sc["nu"], u=U32, harden=True, arith_f32=True)
                    cert_fold_f32_form.append((c32_f["bound"] - v64) * 1e3)
                    cert_fold_f32_arith.append((c32_a["bound"] - v64) * 1e3)
                    cert_fold_f32_col.append(c32_f["col_err"] * 1e3)
                    cert_fold_f32_harden.append(c32_f["harden_err"] * 1e3)
                    cert_fold_f32_outer.append(c32_f["outer_err"] * 1e3)

                    y32 = sc["y"].astype(np.float32).astype(np.float64)
                    nu32 = sc["nu"].astype(np.float32).astype(np.float64)
                    cy32 = cert_bound_general(fd, y32, nu32, u=U64, harden=True)
                    cert_fold_y32_f64.append((cy32["bound"] - v64) * 1e3)

                    ci64 = cert_bound_int64_q30_q24(fd, sc["y"], sc["nu"])
                    int64_max_bits = max(int64_max_bits, ci64["max_acc_bits"])
                    if ci64["bound"] < v64 - 1e-12:
                        int64_sound_violations += 1
                    cert_fold_int64.append((ci64["bound"] - v64) * 1e3)

                    # Sample float32-data LP solves on every 3rd fold (all 42 directions!)
                    if ((t - 273) // CW.B) % 3 == 0:
                        for tag, tol, raw_lst, ref_lst in (
                            ("tol6", 1e-6, cert_fold_f32solve_tol6_raw, cert_fold_f32solve_tol6_ref),
                            ("tol5", 1e-5, cert_fold_f32solve_tol5_raw, cert_fold_f32solve_tol5_ref),
                        ):
                            s32 = solve_highs(fd, dtype=np.float32, tol=tol)
                            if s32["status"] == _core.HighsModelStatus.kOptimal:
                                yr = s32["y"].astype(np.float32).astype(np.float64)
                                nr = s32["nu"].astype(np.float32).astype(np.float64)
                                cr = cert_bound_general(fd, yr, nr, u=U64, harden=True)
                                raw_lst.append((cr["bound"] - v64) * 1e3)
                                y_ref, nu_ref = basis_refine_duals_f64(fd, s32["basis"])
                                cref = cert_bound_general(fd, y_ref, nu_ref, u=U64, harden=True)
                                ref_lst.append((cref["bound"] - v64) * 1e3)
                            else:
                                f32_solve_fail_count[tag] += 1

            # TSP order warm-starts (dual and primal)
            for pos, i in enumerate(D_tsp):
                d = w.D[i]
                for col, val in zip(obj_cols, -np.asarray(d, dtype=np.float64)):
                    h_wt.changeColCost(int(col), float(val))
                h_wt.run()
                assert h_wt.getModelStatus() == _core.HighsModelStatus.kOptimal
                nt = int(h_wt.getInfo().simplex_iteration_count)
                fold_dualtsp_sum += nt
                if pos > 0:
                    nit_fold_warm_dual_tsp.append(nt)
                warm_fold_max_obj_diff = max(warm_fold_max_obj_diff, abs(-h_wt.getInfo().objective_function_value - cold_vals_by_i[i]))

                if pos == 1:
                    h_wp.setOptionValue("simplex_strategy", STRAT_PRIMAL)
                for col, val in zip(obj_cols, -np.asarray(d, dtype=np.float64)):
                    h_wp.changeColCost(int(col), float(val))
                h_wp.run()
                st_p = h_wp.getModelStatus()
                if st_p != _core.HighsModelStatus.kOptimal:
                    primal_fold_nonopt.append((t, pos, i, str(st_p)))
                    h_wp.clearSolver()
                    h_wp.setOptionValue("simplex_strategy", STRAT_DUAL)
                    h_wp.run()
                    assert h_wp.getModelStatus() == _core.HighsModelStatus.kOptimal
                    h_wp.setOptionValue("simplex_strategy", STRAT_PRIMAL)
                np_it = int(h_wp.getInfo().simplex_iteration_count)
                fold_primaltsp_sum += np_it
                if pos > 0:
                    nit_fold_warm_primal_tsp.append(np_it)
                warm_fold_max_obj_diff = max(warm_fold_max_obj_diff, abs(-h_wp.getInfo().objective_function_value - cold_vals_by_i[i]))

            nit_fold_per_fold_cold.append(fold_cold_sum)
            nit_fold_per_fold_dual_tsp.append(fold_dualtsp_sum)
            nit_fold_per_fold_primal_tsp.append(fold_primaltsp_sum)

            w.tau, w.base = tau2, w.tp.clamp(np.array(vals, dtype=float))
            w.zs = {j: z for j, z in w.zs.items() if j >= tau2}
            if getattr(w, "track", False):
                w.last_active = {j: a for j, a in w.last_active.items() if j >= tau2}
            prev_step = {"up": None, "dn": None, "last": None}

    return {
        "variant": variant_name,
        "detect": det,
        "evictions": int(getattr(w, "n_evict", 0)),
        "alarm_detail": alarm_detail,
        "lu_step_t300_695": {k: stats_summary(v) for k, v in lu_step.items()},
        "lu_fold_t300_695": {k: stats_summary(v) for k, v in lu_fold.items()},
        "certs": {
            "f32_formula_u24_step_mC": stats_summary(cert_step_f32_form),
            "f32_arith_u24_step_mC": stats_summary(cert_step_f32_arith),
            "f32_formula_u24_fold_mC": stats_summary(cert_fold_f32_form),
            "f32_arith_u24_fold_mC": stats_summary(cert_fold_f32_arith),
            "f32_fold_col_err_mC": stats_summary(cert_fold_f32_col),
            "f32_fold_harden_err_mC": stats_summary(cert_fold_f32_harden),
            "f32_fold_outer_err_mC": stats_summary(cert_fold_f32_outer),
            "y32_from_f64_checked_f64_step_mC": stats_summary(cert_step_y32_f64),
            "y32_from_f64_checked_f64_fold_mC": stats_summary(cert_fold_y32_f64),
            "f32_data_solve_tol1e6_raw_step_mC": stats_summary(cert_step_f32solve_tol6_raw),
            "f32_data_solve_tol1e6_raw_fold_mC": stats_summary(cert_fold_f32solve_tol6_raw),
            "f32_data_solve_tol1e6_refined_step_mC": stats_summary(cert_step_f32solve_tol6_ref),
            "f32_data_solve_tol1e6_refined_fold_mC": stats_summary(cert_fold_f32solve_tol6_ref),
            "f32_data_solve_tol1e5_raw_step_mC": stats_summary(cert_step_f32solve_tol5_raw),
            "f32_data_solve_tol1e5_raw_fold_mC": stats_summary(cert_fold_f32solve_tol5_raw),
            "f32_data_solve_tol1e5_refined_step_mC": stats_summary(cert_step_f32solve_tol5_ref),
            "f32_data_solve_tol1e5_refined_fold_mC": stats_summary(cert_fold_f32solve_tol5_ref),
            "f32_solve_fail_count": f32_solve_fail_count,
            "int64_q30_q24_step_mC": stats_summary(cert_step_int64),
            "int64_q30_q24_fold_mC": stats_summary(cert_fold_int64),
            "int64_max_acc_bits": int64_max_bits,
            "int64_sound_violations": int64_sound_violations,
        },
        "warm_start": {
            "step_cold_dual": stats_summary(nit_cold_step),
            "step_warm_sep_dual": stats_summary(nit_warm_sep_dual),
            "step_warm_sep_primal": stats_summary(nit_warm_sep_primal),
            "step_warm_shared_up_to_dn_dual": stats_summary(nit_warm_shared_dual),
            "step_warm_sep_dual_when_prev_dropped": stats_summary(warm_step_dropped_nit),
            "step_warm_sep_dual_when_prev_kept": stats_summary(warm_step_kept_nit),
            "step_mapped_ok": warm_step_mapped_ok,
            "step_mapped_fail": warm_step_mapped_fail,
            "step_max_obj_diff": warm_step_max_obj_diff,
            "fold_cold_dual_per_lp": stats_summary(nit_fold_cold),
            "fold_warm_dual_default_d1_to_d41": stats_summary(nit_fold_warm_dual_def),
            "fold_warm_dual_tsp_d1_to_d41": stats_summary(nit_fold_warm_dual_tsp),
            "fold_warm_primal_tsp_d1_to_d41": stats_summary(nit_fold_warm_primal_tsp),
            "fold_total_42lp_cold_dual": stats_summary(nit_fold_per_fold_cold),
            "fold_total_42lp_warm_dual_tsp": stats_summary(nit_fold_per_fold_dual_tsp),
            "fold_total_42lp_warm_primal_tsp": stats_summary(nit_fold_per_fold_primal_tsp),
            "fold_max_obj_diff": warm_fold_max_obj_diff,
            "primal_step_nonopt_count": len(primal_step_nonopt),
            "primal_step_nonopt_sample": primal_step_nonopt[:5],
            "primal_fold_nonopt_count": len(primal_fold_nonopt),
            "primal_fold_nonopt_sample": primal_fold_nonopt[:5],
        },
    }


def run_mixed_precision_online_replay_430010(tol=1e-6, refine_basis=False):
    """True end-to-end online replay of 430010 (F) where every LP is solved on float32-quantized data
    at relaxed tolerance, and every fold/alarm bound is certified in float64 against exact float64 data."""
    run = CW.S.run(430010, next(c for c in CW.T.CELLS if c.name == "drift_0.0005"), "E0", "ramp", "uniform")
    zs = G.zs_of(run)
    cy = CW.V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    w = CW.make("F", cy)
    w.zs[0] = zs[0]
    w.last_active[0] = 0
    det, margin_det, margin_695 = None, None, None
    folds_raised, max_raise_mC = 0, 0.0
    solve_fallbacks = 0

    for t in range(1, 750):
        w.now = t
        vals_cert = {}
        for side, vec in (("up", (0.0, 1.0, 0.0)), ("dn", (0.0, -1.0, 0.0))):
            d = build_lp_data(w, t, t - 1, t, vec)
            s32 = solve_highs(d, dtype=np.float32, tol=tol)
            if s32["status"] != _core.HighsModelStatus.kOptimal:
                solve_fallbacks += 1
                s32 = solve_highs(d, dtype=np.float64, tol=tol)
            if refine_basis:
                y, nu = basis_refine_duals_f64(d, s32["basis"])
            else:
                y = s32["y"].astype(np.float32).astype(np.float64)
                nu = s32["nu"].astype(np.float32).astype(np.float64)
            cub = cert_bound_general(d, y, nu, u=U64, harden=True)["bound"]
            vals_cert[side] = (s32["val"], cub)

        zl_out = float(np.nextafter(zs[t] - CW.DELTA, -np.inf))
        zu_out = float(np.nextafter(zs[t] + CW.DELTA, np.inf))
        cm = 1e3 * min(zu_out + vals_cert["dn"][1], vals_cert["up"][1] - zl_out)
        if t == 695:
            margin_695 = float(cm)
        if cm < 0:
            det, margin_det = t, float(cm)
            break
        lower, upper = -vals_cert["dn"][1], vals_cert["up"][1]
        if not (lower >= zs[t] - CW.DELTA and upper <= zs[t] + CW.DELTA):
            w.keep(t, zs[t])
            if sum(1 for j in w.zs if j > w.tau) > 64:
                w.evict()
        if t - w.tau > CW.W + CW.B:
            tau2 = w.tau + CW.B
            bvals = []
            for dvec in w.D:
                fd = build_lp_data(w, t, t, tau2, dvec)
                s32 = solve_highs(fd, dtype=np.float32, tol=tol)
                if s32["status"] != _core.HighsModelStatus.kOptimal:
                    solve_fallbacks += 1
                    s32 = solve_highs(fd, dtype=np.float64, tol=tol)
                if refine_basis:
                    y, nu = basis_refine_duals_f64(fd, s32["basis"])
                else:
                    y = s32["y"].astype(np.float32).astype(np.float64)
                    nu = s32["nu"].astype(np.float32).astype(np.float64)
                cub = cert_bound_general(fd, y, nu, u=U64, harden=True)["bound"]
                if cub > s32["val"] + CW.PAD:
                    folds_raised += 1
                    max_raise_mC = max(max_raise_mC, (cub - s32["val"] - CW.PAD) * 1e3)
                bvals.append(max(s32["val"] + CW.PAD, cub))
            w.tau, w.base = tau2, w.tp.clamp(np.array(bvals, dtype=float))
            w.zs = {j: z for j, z in w.zs.items() if j >= tau2}
            w.last_active = {j: a for j, a in w.last_active.items() if j >= tau2}
    return {
        "tol": tol,
        "refine_basis": refine_basis,
        "detect": det,
        "margin_at_695_mC": margin_695,
        "margin_at_detect_mC": margin_det,
        "folds_raised": folds_raised,
        "max_raise_mC": max_raise_mC,
        "solve_fallbacks": solve_fallbacks,
    }


def run_edge_peak_lu_check():
    """Measure real sparse LU fill-in at edge-noise peak m=445 on DEV seed 430070 (healthy, E0, ramp, edge)."""
    run = CW.S.run(430070, next(c for c in CW.T.CELLS if c.name == "healthy"), "E0", "ramp", "edge")
    zs = G.zs_of(run)
    cy = CW.V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    w = CW.make("F", cy)
    w.zs[0] = zs[0]
    w.last_active[0] = 0
    rec = {k: [] for k in ("m", "n", "nnz_A", "nnz_B", "nnz_colamd", "fill_colamd", "nnz_mmd", "fill_mmd")}
    for t in range(1, 360):
        w.now = t
        up_d = build_lp_data(w, t, t - 1, t, (0.0, 1.0, 0.0))
        dn_d = build_lp_data(w, t, t - 1, t, (0.0, -1.0, 0.0))
        su = solve_highs(up_d)
        sd = solve_highs(dn_d)
        for d_lp, s_lp in ((up_d, su), (dn_d, sd)):
            if s_lp["status"] == _core.HighsModelStatus.kOptimal:
                cd = s_lp["h"].getSolution().col_dual
                for j in d_lp["meas"]:
                    if abs(cd[d_lp["idx"][j][1]]) > 1e-12:
                        w.last_active[j] = t
        if t >= 300 and su["status"] == _core.HighsModelStatus.kOptimal:
            B, _, _ = extract_basis_matrix(su["A_csc"], su["basis"], up_d["m"])
            lu_c = spla.splu(B, permc_spec="COLAMD")
            lu_m = spla.splu(B, permc_spec="MMD_AT_PLUS_A")
            rec["m"].append(up_d["m"])
            rec["n"].append(up_d["nv"])
            rec["nnz_A"].append(int(su["A_csc"].nnz))
            rec["nnz_B"].append(int(B.nnz))
            rec["nnz_colamd"].append(int(lu_c.nnz))
            rec["fill_colamd"].append(float(lu_c.nnz / B.nnz))
            rec["nnz_mmd"].append(int(lu_m.nnz))
            rec["fill_mmd"].append(float(lu_m.nnz / B.nnz))
        lower, upper = -sd["val"], su["val"]
        if not (lower >= zs[t] - CW.DELTA and upper <= zs[t] + CW.DELTA):
            w.keep(t, zs[t])
            if sum(1 for j in w.zs if j > w.tau) > 64:
                w.evict()
        if t - w.tau > CW.W + CW.B:
            tau2 = w.tau + CW.B
            bvals = []
            for dvec in w.D:
                fd = build_lp_data(w, t, t, tau2, dvec)
                sc = solve_highs(fd)
                cub = cert_bound_general(fd, sc["y"], sc["nu"], u=U64, harden=True)["bound"]
                bvals.append(max(sc["val"] + CW.PAD, cub))
            w.tau, w.base = tau2, w.tp.clamp(np.array(bvals, dtype=float))
            w.zs = {j: z for j, z in w.zs.items() if j >= tau2}
            w.last_active = {j: a for j, a in w.last_active.items() if j >= tau2}
    return {k: stats_summary(v) for k, v in rec.items()}


def sram_budget_model(m, n, nnz_A, nnz_lu_est, eta_pivots=50, avg_eta_nnz=40, real_bytes=4):
    """Explicit itemized Cortex-M SRAM breakdown (all indices uint16 = 2B, ptrs uint16/uint32)."""
    idx_b = 2
    # Constraint matrix A in CSC: values + row_idx + col_ptr (n+1)
    a_bytes = nnz_A * (real_bytes + idx_b) + (n + 1) * idx_b
    # Sparse LU (L + U stored in CSC with 1.25x static workspace headroom for dynamic fill)
    lu_cap = int(math.ceil(nnz_lu_est * 1.25))
    lu_bytes = lu_cap * (real_bytes + idx_b) + 2 * (m + 1) * idx_b + 4 * m * idx_b  # L,U + row/col perms
    # Forrest-Tomlin / PFI eta buffer (eta_pivots spikes, avg_eta_nnz each)
    eta_entries = eta_pivots * avg_eta_nnz
    eta_bytes = eta_entries * (real_bytes + idx_b) + (eta_pivots + 1) * 4
    # Simplex vectors:
    # per-col (x, lb, ub, c, rc = 5 real + status 1B + basic_map 2B)
    # per-row (y, b, row_val, rhs_work, ftran_work, btran_work, dse_wt = 7 real + status 1B + basic_idx 2B)
    vec_bytes = n * (5 * real_bytes + 3) + m * (7 * real_bytes + 3)
    # Two saved warm-start basis status arrays (up + dn): 2 * (n + m) bytes
    warm_bytes = 2 * (n + m)
    total = a_bytes + lu_bytes + eta_bytes + vec_bytes + warm_bytes
    return {
        "m": m, "n": n, "nnz_A": nnz_A, "nnz_lu_est": nnz_lu_est, "lu_cap": lu_cap,
        "real_bytes": real_bytes,
        "A_bytes": a_bytes, "LU_bytes": lu_bytes, "eta_bytes": eta_bytes,
        "vectors_bytes": vec_bytes, "warm_basis_bytes": warm_bytes,
        "total_bytes": total,
        "total_KiB": round(total / 1024.0, 2),
        "total_kB": round(total / 1000.0, 2),
    }


def main():
    t0 = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()

    # Item 1: Exact dense B^-1 arithmetic
    dense = {}
    for label, m in (("F_DEV_max", 409), ("F_edge_max", 445), ("N_DEV_max", 183), ("F_430010_max", 373)):
        b32 = m * m * 4
        b64 = m * m * 8
        dense[label] = {
            "m": m,
            "float32_bytes": b32, "float32_KiB": round(b32 / 1024.0, 2), "float32_kB": round(b32 / 1000.0, 2),
            "float64_bytes": b64, "float64_KiB": round(b64 / 1024.0, 2), "float64_kB": round(b64 / 1000.0, 2),
        }

    print("[N1] Running 430010 audit for F (K=64)...", flush=True)
    res_F = run_430010_audit("F", K=64)
    print(f"[N1] F done in {time.monotonic()-t0:.1f}s (det={res_F['detect']})", flush=True)

    t1 = time.monotonic()
    print("[N1] Running 430010 audit for N...", flush=True)
    res_N = run_430010_audit("N", K=None)
    print(f"[N1] N done in {time.monotonic()-t1:.1f}s (det={res_N['detect']})", flush=True)

    t2 = time.monotonic()
    print("[N1] Running mixed-precision online replays of 430010 (F)...", flush=True)
    replays = [
        run_mixed_precision_online_replay_430010(tol=1e-6, refine_basis=False),
        run_mixed_precision_online_replay_430010(tol=1e-6, refine_basis=True),
        run_mixed_precision_online_replay_430010(tol=1e-5, refine_basis=False),
        run_mixed_precision_online_replay_430010(tol=1e-5, refine_basis=True),
    ]
    print(f"[N1] Replays done in {time.monotonic()-t2:.1f}s", flush=True)

    t3 = time.monotonic()
    print("[N1] Running edge-noise peak LU check (430070, t=300..359)...", flush=True)
    edge_lu = run_edge_peak_lu_check()
    print(f"[N1] Edge LU done in {time.monotonic()-t3:.1f}s", flush=True)

    # Item 2: Itemized SRAM budgets grounded in observed COLAMD LU fill-in
    f_col_max = int(max(res_F["lu_step_t300_695"]["nnz_colamd"]["max"], res_F["lu_fold_t300_695"]["nnz_colamd"]["max"]))
    e_col_max = int(edge_lu["nnz_colamd"]["max"])
    n_col_max = int(max(res_N["lu_step_t300_695"]["nnz_colamd"]["max"], res_N["lu_fold_t300_695"]["nnz_colamd"]["max"]))
    # Scale 430010 COLAMD LU up to DEV peak (m=409 vs 373 -> ~1.15x, N m=183 vs 129 -> ~1.45x) and use observed edge peak directly!
    sram = {
        "F_DEV_m409_f32": sram_budget_model(409, 643, 1900, int(math.ceil(f_col_max * (409 / 373))), eta_pivots=50, avg_eta_nnz=45, real_bytes=4),
        "F_DEV_m409_f64": sram_budget_model(409, 643, 1900, int(math.ceil(f_col_max * (409 / 373))), eta_pivots=50, avg_eta_nnz=45, real_bytes=8),
        "F_edge_m445_f32": sram_budget_model(445, 679, int(edge_lu["nnz_A"]["max"]), e_col_max, eta_pivots=50, avg_eta_nnz=55, real_bytes=4),
        "N_DEV_m183_f32": sram_budget_model(183, 417, 1600, int(math.ceil(n_col_max * (183 / 129))), eta_pivots=50, avg_eta_nnz=30, real_bytes=4),
        "N_DEV_m183_f64": sram_budget_model(183, 417, 1600, int(math.ceil(n_col_max * (183 / 129))), eta_pivots=50, avg_eta_nnz=30, real_bytes=8),
    }

    payload = {
        "task": "Neon-N1",
        "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "checkout": str(REPO),
        "git_head": head,
        "diag3_cw_sha256": sha256_file(REPO / "experiments/v3/diag/diag3_cw.py"),
        "env": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "highs": f"{_core.HIGHS_VERSION_MAJOR}.{_core.HIGHS_VERSION_MINOR}.{_core.HIGHS_VERSION_PATCH}",
        },
        "elapsed_seconds": round(time.monotonic() - t0, 2),
        "item1_dense_Binv": dense,
        "item2_sram_budgets_estimated": sram,
        "item2_edge_peak_lu_430070": edge_lu,
        "audit_430010_F": res_F,
        "audit_430010_N": res_N,
        "mixed_precision_online_replays_430010": replays,
    }
    (OUT / "n1_results.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(f"[N1] All done in {payload['elapsed_seconds']}s -> {OUT / 'n1_results.json'}", flush=True)


if __name__ == "__main__":
    main()
