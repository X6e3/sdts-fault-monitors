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
  d_lo  a weak-duality lower bound from sign-corrected multipliers. The stationarity residual must
        be below DUAL_TOL, and its worst-case contribution over an enclosing box is subtracted.
        If both LP attempts leave the verdict open, an adjacent-sample rate inequality can also
        give a lower bound, when the rate constraint is enabled.

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
  - The CAL rehearsal of the FINAL runner (2026-11-17) left two ablation LPs undetermined on x86_64 with
    both no-presolve methods at HiGHS status 4. With per-process isolation, presolve is safe as a last
    fallback and decided both, matching arm64. See ATTEMPTS.

All temperatures are shifted by -25 C inside the LP. The dynamics are shift invariant (A·1 + B_T = 1),
so this changes nothing but the conditioning.

Ablations (addendum A1.5): `verdict(..., rate=False)` drops (b), `verdict(..., box=False)` drops (c), and
`verdict_free_command(y)` drops (d). The (d) model works on y with the full plant:
  - the command P[k] is a decision variable in [P_LO, P_HI] at every sample;
  - (e) fixes the P0 steady state at TA[0];
  - the box is kept.
It carries the same two certificates. The caps for its dual bound follow from the plant being a positive
system: every state lies between the steady states for (P_LO, TA_LO) and (P_HI, TA_HI).
"""
import json
import math
import os
import pickle
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "generators"))
import thermal as T  # noqa: E402

A11, A12 = 1.0 - T.K / T.CC, T.K / T.CC
A21, A22, B2 = T.K / T.CS, 1.0 - (T.K + T.H) / T.CS, T.H / T.CS
BP = 1.0 / T.CC                     # command input to the core node; like A11..B2 this assumes DT = 1
assert T.DT == 1.0
SHIFT = 25.0
DUAL_TOL = 1e-7
EPS = np.finfo(float).eps
# The first two decide almost every LP. Presolve runs only as a last resort: it used to crash the process,
# but every attempt now runs in its own process (c04305a), and every answer is certified independently,
# so an extra attempt can only turn "undetermined" into a decision; it can not change one.
ATTEMPTS = (("highs-ds", False), ("highs-ipm", False), ("highs-ds", True), ("highs-ipm", True))
HERE = Path(__file__).resolve()
DEFAULT_ATTEMPT_DIR = HERE.parents[2] / "results" / "tmp" / "highs-attempts"
DEFAULT_TIMEOUT = 120


def _build(z, m, box, rate, mode, sense):
    if mode == "free_command":
        return _build_free_command(z, m, box, rate)
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


def _build_free_command(y, m, box, rate, p_bounds=None):
    """(d) ablation on y: variables TA, P, Tc, Ts, b (fixed 0), d. p_bounds fixes P per sample (tests)."""
    if not box:
        raise ValueError("the (d) ablation keeps the ambient box")
    ys = np.asarray(y[:m], dtype=float) - SHIFT
    iTA, iP, iTc, iTs, ib, idd = 0, m, 2 * m, 3 * m, 4 * m, 4 * m + 1
    nv = 4 * m + 2
    er, ec, ev, beq = [], [], [], []
    row = 0
    er += [row, row]; ec += [iTc, iTA]; ev += [1.0, -1.0]; beq.append(T.P0 / T.H + T.P0 / T.K); row += 1
    er += [row, row]; ec += [iTs, iTA]; ev += [1.0, -1.0]; beq.append(T.P0 / T.H); row += 1
    for k in range(m - 1):
        er += [row] * 4; ec += [iTc + k + 1, iTc + k, iTs + k, iP + k]; ev += [1.0, -A11, -A12, -BP]
        beq.append(0.0); row += 1
        er += [row] * 4; ec += [iTs + k + 1, iTc + k, iTs + k, iTA + k]; ev += [1.0, -A21, -A22, -B2]
        beq.append(0.0); row += 1
    Aeq = coo_matrix((ev, (er, ec)), shape=(row, nv)).tocsr()
    ur, uc, uv, ub = [], [], [], []
    row = 0
    for k in range(m):              # Ts + b - d <= y ; -Ts - b - d <= -y
        ur += [row] * 3; uc += [iTs + k, ib, idd]; uv += [1.0, 1.0, -1.0]; ub.append(ys[k]); row += 1
        ur += [row] * 3; uc += [iTs + k, ib, idd]; uv += [-1.0, -1.0, -1.0]; ub.append(-ys[k]); row += 1
    if rate:
        for k in range(m - 1):
            ur += [row, row]; uc += [iTA + k + 1, iTA + k]; uv += [1.0, -1.0]; ub.append(T.RHO_A); row += 1
            ur += [row, row]; uc += [iTA + k + 1, iTA + k]; uv += [-1.0, 1.0]; ub.append(T.RHO_A); row += 1
    Aub = coo_matrix((uv, (ur, uc)), shape=(row, nv)).tocsr()
    p = [(T.P_LO, T.P_HI)] * m if p_bounds is None else [(float(v), float(v)) for v in p_bounds[:m]]
    bounds = ([(T.TA_LO - SHIFT, T.TA_HI - SHIFT)] * m + p + [(None, None)] * (2 * m)
              + [(0.0, 0.0), (0.0, None)])
    c = np.zeros(nv)
    c[idd] = 1.0
    return c, Aub, np.array(ub), Aeq, np.array(beq), bounds, ys


def _free_command_caps(ys, m):
    """|x| bounds at an optimum of the (d) LP, in variable order (shifted temperatures)."""
    ambient = max(abs(T.TA_LO - SHIFT), abs(T.TA_HI - SHIFT))
    ts_hi = T.TA_HI - SHIFT + T.P_HI / T.H
    tc_hi = ts_hi + T.P_HI / T.K
    low = abs(T.TA_LO - SHIFT)
    grow = 1 + 8 * EPS * (m + 1)
    # TA = 25 C and P = P0 throughout is admissible and gives Ts = 25 + P0/H, so d* <= max |y - Ts| there.
    noise = float(np.max(np.abs(ys - T.P0 / T.H)))
    caps = ([ambient] * m + [max(abs(T.P_LO), abs(T.P_HI))] * m + [max(low, tc_hi) * grow] * m
            + [max(low, ts_hi) * grow] * m + [0.0, noise])
    return np.array(caps) * (1 + 8 * EPS)


def _residual_range_free(TA_shifted, P, ys, rate):
    """Enclose y - Ts after projecting TA, clipping P and simulating the full plant from (e)."""
    TA = _project(TA_shifted, True, rate)
    P = np.clip(np.asarray(P, dtype=float), T.P_LO, T.P_HI)
    tc, ts = TA[0] + T.P0 / T.H + T.P0 / T.K, TA[0] + T.P0 / T.H
    low, high, big = math.inf, -math.inf, 1.0
    for k in range(len(TA)):
        residual = ys[k] - ts
        low, high = min(low, residual), max(high, residual)
        big = max(big, abs(tc), abs(ts))
        tc, ts = A11 * tc + A12 * ts + BP * P[k], A21 * tc + A22 * ts + B2 * TA[k]
    pad = 32 * EPS * (len(TA) + 1) * max(big, float(np.max(np.abs(ys))), T.P_HI)
    return low - pad, high + pad


def _margin_free_command(y, m, rate, attempt_dir):
    if m == 0:
        return 0.0, 0.0
    c, Aub, bub, Aeq, beq, bounds, ys = _build_free_command(y, m, True, rate)
    caps = _free_command_caps(ys, m)
    best_lo, best_up = 0.0, np.inf
    for method, presolve in ATTEMPTS:
        res = _attempt(y, m, True, rate, "free_command", 0.0, method, presolve, attempt_dir)
        if res is None or res.status != 0 or not np.all(np.isfinite(res.x)):
            continue
        low, high = _residual_range_free(res.x[:m], res.x[m:2 * m], ys, rate)
        best_up = min(best_up, math.nextafter(max(abs(low), abs(high)), math.inf))
        d_lo = _dual_bound(res, c, Aub, bub, Aeq, beq, bounds, caps)
        if d_lo is not None and d_lo <= best_up:
            best_lo = max(best_lo, d_lo)
            if best_up <= T.DELTA or best_lo > T.DELTA:
                break
    return best_lo, best_up


def _worker(result_path):
    from scipy.optimize import linprog

    z, m, box, rate, mode, sense, method, presolve = pickle.load(sys.stdin.buffer)
    c, Aub, bub, Aeq, beq, bounds, _ = _build(z, m, box, rate, mode, sense)
    result = linprog(c, A_ub=Aub, b_ub=bub, A_eq=Aeq, b_eq=beq, bounds=bounds,
                     method=method, options={"presolve": presolve})
    with open(result_path, "wb") as stream:
        pickle.dump(result, stream, protocol=pickle.HIGHEST_PROTOCOL)


def _attempt(z, m, box, rate, mode, sense, method, presolve, attempt_dir):
    """Run one solver in a fresh interpreter and keep its OS and solver diagnostics."""
    log_root = Path(attempt_dir) if attempt_dir is not None else DEFAULT_ATTEMPT_DIR
    log_root.mkdir(parents=True, exist_ok=True)
    log = Path(tempfile.mkdtemp(prefix=f"{mode}-{m}-{method}-", dir=log_root))
    result_path = log / "result.pkl"
    command = [sys.executable, "-B", "-u", "-X", "faulthandler", str(HERE), str(result_path)]
    payload = pickle.dumps((np.asarray(z[:m], dtype=float), m, box, rate, mode, sense,
                            method, presolve), protocol=pickle.HIGHEST_PROTOCOL)
    timeout = float(os.environ.get("SDTS_HIGHS_TIMEOUT", DEFAULT_TIMEOUT))
    audit = {"method": method, "presolve": presolve, "problem": mode, "samples": m,
             "box": box, "rate": rate, "objective_sense": sense, "timeout_seconds": timeout,
             "exit_code": None, "signal": None, "solver_status": None, "solver_message": None,
             "outcome": "started"}
    metadata = log / "attempt.json"
    metadata.write_text(json.dumps(audit, indent=2) + "\n")
    t0 = time.monotonic()
    result = None
    try:
        with (log / "stdout.txt").open("wb") as stdout, (log / "stderr.txt").open("wb") as stderr:
            with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=stdout, stderr=stderr) as child:
                audit["pid"] = child.pid
                try:
                    child.communicate(input=payload, timeout=timeout)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.communicate()
                    audit["outcome"] = "timeout"
                audit["exit_code"] = child.returncode
        if audit["exit_code"] < 0:
            audit["signal"] = signal.Signals(-audit["exit_code"]).name
        if audit["outcome"] == "timeout":
            return None
        if audit["exit_code"] != 0:
            audit["outcome"] = "signal" if audit["signal"] else "worker_error"
            return None
        with result_path.open("rb") as stream:
            result = pickle.load(stream)
        audit["solver_status"] = int(result.status)
        audit["solver_message"] = str(result.message)
        audit["outcome"] = "returned"
    except (OSError, EOFError, pickle.UnpicklingError) as exc:
        audit["outcome"] = "process_io_error"
        audit["error"] = repr(exc)
    finally:
        audit["elapsed_seconds"] = round(time.monotonic() - t0, 6)
        completed = log / "attempt.json.tmp"
        completed.write_text(json.dumps(audit, indent=2) + "\n")
        completed.replace(metadata)
        result_path.unlink(missing_ok=True)
    return result


def _dual_bound(res, c, Aub, bub, Aeq, beq, bounds, caps):
    """Lower bound on c @ x using dual signs and |x| <= caps at an optimum."""
    if caps is None:
        return None
    lo = np.array([b[0] if b[0] is not None else -np.inf for b in bounds])
    up = np.array([b[1] if b[1] is not None else np.inf for b in bounds])
    y_ub, y_eq = np.minimum(res.ineqlin.marginals, 0.0), res.eqlin.marginals
    lam_l = np.where(np.isfinite(lo), np.maximum(res.lower.marginals, 0.0), 0.0)
    lam_u = np.where(np.isfinite(up), np.minimum(res.upper.marginals, 0.0), 0.0)
    resid = c - (Aub.T @ y_ub + Aeq.T @ y_eq + lam_l + lam_u)
    if not np.all(np.isfinite(resid)) or np.max(np.abs(resid)) > DUAL_TOL:
        return None
    terms = np.concatenate((bub * y_ub, beq * y_eq,
                            np.where(np.isfinite(lo), lo, 0.0) * lam_l,
                            np.where(np.isfinite(up), up, 0.0) * lam_u))
    scale = abs(c) + abs(Aub).T @ abs(y_ub) + abs(Aeq).T @ abs(y_eq) + abs(lam_l) + abs(lam_u)
    rounding = 8 * EPS * (len(terms) + 1)
    correction = (abs(resid) + rounding * scale) @ caps
    lower = terms.sum() - correction - rounding * (abs(terms).sum() + correction)
    return math.nextafter(lower, -math.inf) if np.isfinite(lower) else None


def _optimum_caps(zs, box, rate, mode):
    """Absolute bounds on TA, the states, b and d, in LP variable order."""
    m = len(zs)
    if box:
        ambient = max(abs(T.TA_LO - SHIFT), abs(T.TA_HI - SHIFT))
    elif rate and mode == "margin":
        ambient = abs(zs[0]) + max(abs(zs)) + (m - 1) * T.RHO_A
    else:
        return None
    # Zero shifted ambient is admissible, so min d <= max |zs|. At sample zero as[0] = TA[0].
    offset, noise = (0.0, max(abs(zs))) if mode == "margin" else (abs(zs[0]) + ambient + T.DELTA, T.DELTA)
    state = ambient * (1 + 8 * EPS * (m + 1))
    return np.array([ambient] * m + [state] * (2 * m) + [offset, noise]) * (1 + 8 * EPS)


def _project(TA_shifted, box, rate):
    """The nearest-in-spirit admissible path: each step clipped to the rate bound, then to the box. Starting
    inside the box, the two clips always intersect, so the result satisfies (b) and (c) exactly."""
    TA = np.asarray(TA_shifted, dtype=float).copy()
    lo, hi = (T.TA_LO - SHIFT, T.TA_HI - SHIFT) if box else (-np.inf, np.inf)
    TA[0] = min(hi, max(lo, TA[0]))
    for k in range(1, len(TA)):
        x = TA[k]
        if rate:
            prev = TA[k - 1]
            lower = math.nextafter(prev - T.RHO_A, prev)
            upper = math.nextafter(prev + T.RHO_A, prev)
            x = min(upper, max(lower, x))
        TA[k] = min(hi, max(lo, x))
    return TA


def _residual_range(TA_shifted, z_shifted, box, rate):
    """Enclose z - as after projecting the candidate and simulating the plant."""
    TA = _project(TA_shifted, box, rate)
    ac = as_ = TA[0]
    low, high = math.inf, -math.inf
    for k in range(len(TA)):
        residual = z_shifted[k] - as_
        low, high = min(low, residual), max(high, residual)
        ac, as_ = A11 * ac + A12 * as_, A21 * ac + A22 * as_ + B2 * TA[k]
    scale = max(1.0, max(abs(TA)), max(abs(z_shifted)))
    pad = 32 * EPS * (len(TA) + 1) * scale
    return low - pad, high + pad


def _forward(TA_shifted, z_shifted, b, box, rate):
    low, high = _residual_range(TA_shifted, z_shifted, box, rate)
    return math.nextafter(max(abs(low - b), abs(high - b)), math.inf)


def _adjacent_rate_bound(zs, caps):
    """2 d >= |z[k] - z[k-1]| - RHO_A because the ambient filter preserves rate."""
    steps = np.abs(np.diff(zs))
    edge = int(np.argmax(steps))
    scale = max(1.0, float(np.max(caps)))
    # Cover the shifted LP's floating-point state coefficients over the full prefix.
    pad = 64 * EPS * (len(zs) + 1) * scale
    lower = math.nextafter((steps[edge] - T.RHO_A - pad) / 2, -math.inf)
    return lower, edge + 1, float(steps[edge]), pad


def _margin(z, m, box, rate, attempt_dir):
    m = len(z) if m is None else m
    if m == 0:
        return 0.0, 0.0, None
    c, Aub, bub, Aeq, beq, bounds, zs = _build(z, m, box, rate, "margin", 0.0)
    caps = _optimum_caps(zs, box, rate, "margin")
    best_lo, best_up, best_path = 0.0, np.inf, None
    for method, presolve in ATTEMPTS:
        res = _attempt(z, m, box, rate, "margin", 0.0, method, presolve, attempt_dir)
        if res is None or res.status != 0 or not np.all(np.isfinite(res.x)):
            continue
        upper = _forward(res.x[:m], zs, 0.0, box, rate)
        if upper < best_up:
            best_up, best_path = upper, res.x[:m]
        d_lo = _dual_bound(res, c, Aub, bub, Aeq, beq, bounds, caps)
        if d_lo is not None and d_lo <= best_up:
            best_lo = max(best_lo, d_lo)
            if best_up <= T.DELTA or best_lo > T.DELTA:
                break
    if best_lo <= T.DELTA < best_up and rate and m > 1:
        lower, sample, step, pad = _adjacent_rate_bound(zs, caps)
        if lower > T.DELTA:
            best_lo = lower
            # The all-zero shifted ambient path is a feasible primal witness at this cap.
            zero_upper = float(np.max(np.abs(zs)))
            if zero_upper < best_up:
                best_up, best_path = zero_upper, np.zeros(m)
            log_root = Path(attempt_dir) if attempt_dir is not None else DEFAULT_ATTEMPT_DIR
            certificate = {"source": "adjacent_rate", "samples": m, "sample": sample, "step": step,
                           "rho": T.RHO_A, "rounding_padding": pad, "d_lo": best_lo, "d_up": best_up}
            with tempfile.NamedTemporaryFile(mode="w", dir=log_root, prefix=f"certificate-{m}-",
                                             suffix=".json", delete=False) as log:
                json.dump(certificate, log, indent=2)
                log.write("\n")
    return best_lo, best_up, best_path


def margin(z, m=None, box=True, rate=True, *, attempt_dir=None):
    """Certified bounds on d*, the smallest noise bound explaining z[0:m]."""
    d_lo, d_up, _ = _margin(z, m, box, rate, attempt_dir)
    return d_lo, d_up


def _verdict(d_lo, d_up):
    if d_up <= T.DELTA:
        return "consistent"
    if d_lo > T.DELTA:
        return "inconsistent"
    return "undetermined"


def verdict(z, m=None, box=True, rate=True, *, attempt_dir=None):
    d_lo, d_up = margin(z, m, box, rate, attempt_dir=attempt_dir)
    return _verdict(d_lo, d_up), d_lo, d_up


def verdict_free_command(y, m=None, *, rate=True, attempt_dir=None):
    """(d) ablation: the verdict on the raw measurement y when the command is unknown in [P_LO, P_HI]."""
    m = len(y) if m is None else m
    d_lo, d_up = _margin_free_command(y, m, rate, attempt_dir)
    return _verdict(d_lo, d_up), d_lo, d_up


def first_inconsistent(z, box=True, rate=True, *, attempt_dir=None):
    """(t*, status). t* is the smallest index with z[0:t*+1] certified inconsistent; None if the whole run
    is certified consistent. Adjacent certified prefixes fix t* even if an earlier probe was unknown.
    When the final upper prefix is unknown, t* is an estimate."""
    n = len(z)
    v, _, _ = verdict(z, n, box, rate, attempt_dir=attempt_dir)
    if v == "consistent":
        return None, "certified"
    status = "certified" if v == "inconsistent" else "undetermined"
    lo, hi = 0, n
    while hi - lo > 1:
        mid = (lo + hi) // 2
        v, _, _ = verdict(z, mid, box, rate, attempt_dir=attempt_dir)
        if v == "consistent":
            lo = mid
        else:
            hi = mid
            status = "certified" if v == "inconsistent" else "undetermined"
    return hi - 1, status


def _witness_interval(lo, hi):
    lo_b = math.nextafter(hi - T.DELTA, math.inf)
    hi_b = math.nextafter(lo + T.DELTA, -math.inf)
    return (lo_b, hi_b) if lo_b <= hi_b else None


def offset_enclosure(z, box=True, rate=True, *, attempt_dir=None, reference=None):
    """Return (witness interval, enclosing interval). Either may be unavailable."""
    if len(z) == 0:
        return None, None
    zs = np.asarray(z, dtype=float) - SHIFT
    outer = None
    if box:
        # States are positive combinations of bounded ambient values, up to LP coefficient roundoff.
        pad = 32 * EPS * (len(z) + 1) * max(1.0, max(abs(zs)))
        outer = [float(max(zs) - (T.TA_HI - SHIFT) - T.DELTA - pad),
                 float(min(zs) - (T.TA_LO - SHIFT) + T.DELTA + pad)]
    caps = _optimum_caps(zs, box, rate, "offset")
    inner = None
    if reference is not None:
        ref_path, ref_up = reference
        ref_path = _project(ref_path, box, rate)
    for end, sense in enumerate((1.0, -1.0)):
        c, Aub, bub, Aeq, beq, bounds, _ = _build(z, len(z), box, rate, "offset", sense)
        for method, presolve in ATTEMPTS:
            res = _attempt(z, len(z), box, rate, "offset", sense, method, presolve, attempt_dir)
            if res is None or res.status != 0 or not np.all(np.isfinite(res.x)):
                continue
            path, offset = res.x[:len(z)], res.x[3 * len(z)]
            lo, hi = _residual_range(path, zs, box, rate)
            witness = _witness_interval(lo, hi)
            if witness is None and reference is not None and ref_up < T.DELTA:
                # Mix a near-boundary path with the checked zero-offset path, then verify again.
                need = max(abs(lo - offset), abs(hi - offset))
                fraction = 0.999 * (T.DELTA - ref_up) / (need - ref_up)
                mixed = (1 - fraction) * ref_path + fraction * _project(path, box, rate)
                witness = _witness_interval(*_residual_range(mixed, zs, box, rate))
            if witness is not None:
                inner = witness if inner is None else (min(inner[0], witness[0]), max(inner[1], witness[1]))
            dual = _dual_bound(res, c, Aub, bub, Aeq, beq, bounds, caps)
            if dual is not None:
                outer[end] = max(outer[end], dual) if end == 0 else min(outer[end], -dual)
                if witness is not None:
                    break
    if outer is not None and (outer[0] > outer[1] or (inner and (inner[0] < outer[0] or inner[1] > outer[1]))):
        outer = None
    return inner, tuple(outer) if outer is not None else None


def offset_interval(z, box=True, rate=True, *, attempt_dir=None):
    """Constant offsets verified by projected ambient paths, as an inner bound."""
    return offset_enclosure(z, box, rate, attempt_dir=attempt_dir)[0]


def verdict_and_offsets(z, *, attempt_dir=None):
    """A zero-offset verdict and, when consistent, the checked offset enclosure."""
    d_lo, d_up, path = _margin(z, None, True, True, attempt_dir)
    v = _verdict(d_lo, d_up)
    reference = (path, d_up) if path is not None else None
    inner, outer = offset_enclosure(z, attempt_dir=attempt_dir, reference=reference) if v == "consistent" else (None, None)
    return v, d_lo, d_up, inner, outer


if __name__ == "__main__":
    _worker(sys.argv[1])
