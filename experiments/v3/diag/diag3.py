"""DIAG-3 (DIAG-3-PLAN.md), phase 1: a window LP that folds into a cyl16p-direction template, online from k = 0.
A numerical diagnostic on DEV runs (HiGHS tolerances), not certified.

usage:
  python -B diag3.py run OUT_DIR [--workers 12] [--only SEED] [--variants inf S64 ...]
  python -B diag3.py summary OUT_DIR
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diag1 as G  # noqa: E402

V, S, T, M = G.V, G.S, G.T, G.M
DELTA, RHO, LO, HI, NREC = G.DELTA, G.RHO, G.LO, G.HI, G.NREC
B, PAD, AFTER = 16, 1e-6, 300
RUNS = [(430007, "drift_0.002", "rw"), (430027, "drift_0.002", "rw"), (430000, "drift_0.001", "ramp"),
        (430010, "drift_0.0005", "ramp"), (430019, "drift_0.001", "ramp")]
HARD = (430007, 430027, 430000, 430010)
VARIANTS = ["inf"] + [f"{m}{w}" for w in (64, 128, 256) for m in ("S", "F")]
D1RUN = G.ROOT / "results/v3/diag1/run1-6fe3b54"


class Window:
    """base template at tau (or the exact initial segment) + the measurements of the window"""

    def __init__(self, tp, W, smooth):
        self.tp, self.D, self.W, self.smooth = tp, tp.D, W, smooth
        self.tau, self.base, self.zs = 0, None, {}
        self.n_lp, self.max_vars, self.max_rows, self.lp_seconds, self.n_retry = 0, 0, 0, 0.0, 0

    def lp(self, t_end, meas_upto, obj_state, obj_vec):
        """max obj_vec . x_{obj_state} over the window LP with states tau..t_end and measurements tau..meas_upto;
        None if infeasible"""
        n = t_end - self.tau + 1
        nv = 3 * n
        lb, ub = np.full(nv, LO), np.full(nv, HI)
        for j in range(self.tau, meas_upto + 1):
            if j == self.tau and self.base is not None:
                continue                                    # the base already holds measurement tau
            i = 3 * (j - self.tau) + 1
            lb[i], ub[i] = max(lb[i], self.zs[j] - DELTA), min(ub[i], self.zs[j] + DELTA)
        if np.any(lb > ub):
            return None
        er, ec, ev = [], [], []
        r = 0
        for m in range(n - 1):                              # rows 1, 2 of x_{m+1} = M x_m
            for c in range(2):
                er += [r] * 4
                ec += [3 * (m + 1) + c, 3 * m, 3 * m + 1, 3 * m + 2]
                ev += [1.0, -M[c, 0], -M[c, 1], -M[c, 2]]
                r += 1
        if self.base is None:                               # the initial segment: ac = as = TA
            er += [r, r, r + 1, r + 1]
            ec += [0, 2, 1, 2]
            ev += [1.0, -1.0, 1.0, -1.0]
            r += 2
        A_eq = sp.csr_matrix((ev, (er, ec)), shape=(r, nv)) if r else None
        b_eq = np.zeros(r) if r else None
        ir, ic, iv, bu = [], [], [], []
        q = 0
        for m in range(n - 1):                              # |TA_{m+1} - TA_m| <= RHO
            for s in (1.0, -1.0):
                ir += [q, q]
                ic += [3 * (m + 1) + 2, 3 * m + 2]
                iv += [s, -s]
                bu.append(RHO)
                q += 1
        if self.base is not None:                           # D0 x_tau <= b
            for d, bi in zip(self.D, self.base):
                for c in range(3):
                    if d[c] != 0.0:
                        ir.append(q)
                        ic.append(c)
                        iv.append(d[c])
                bu.append(bi)
                q += 1
        A_ub = sp.csr_matrix((iv, (ir, ic)), shape=(q, nv)) if q else None
        b_ub = np.array(bu) if q else None
        cvec = np.zeros(nv)
        cvec[3 * (obj_state - self.tau):3 * (obj_state - self.tau) + 3] = -np.asarray(obj_vec)
        t0 = time.monotonic()
        res = None
        for method, opts in (("highs-ds", {"presolve": False}), ("highs-ipm", {"presolve": False}),
                             ("highs-ds", {})):
            res = linprog(cvec, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=np.c_[lb, ub], method=method,
                          options=opts)
            if res.status in (0, 2):
                break
            self.n_retry += 1
        self.lp_seconds += time.monotonic() - t0
        self.n_lp += 1
        self.max_vars, self.max_rows = max(self.max_vars, nv), max(self.max_rows, r + q)
        if res.status == 2:
            return None
        if res.status != 0:
            raise RuntimeError(f"LP status {res.status}: {res.message}")
        return -res.fun

    def as_range(self, t):
        up = self.lp(t, t - 1, t, (0, 1.0, 0))
        dn = self.lp(t, t - 1, t, (0, -1.0, 0))
        return (None, None) if up is None or dn is None else (-dn, up)

    def fold(self, t):
        tau2 = self.tau + B
        t_end, upto = (t, t) if self.smooth else (tau2, tau2)
        b = np.array([self.lp(t_end, upto, tau2, d) for d in self.D])
        if np.any([x is None for x in b]):
            raise RuntimeError("window LP infeasible during a fold")
        b = self.tp.clamp(b.astype(float) + PAD)
        self.tau, self.base = tau2, b
        self.zs = {j: z for j, z in self.zs.items() if j >= tau2}


def job(args):
    seed, cell, amb, var, out = args
    j1 = json.load(open(D1RUN / f"arms-{seed}-{cell}-{amb}-L256.json"))
    t_star, t_cyl = j1["t_star"], j1["t_cyl16p"]
    run = S.run(seed, next(c for c in T.CELLS if c.name == cell), "E0", amb, "uniform")
    zs = G.zs_of(run)
    cy = V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    W = None if var == "inf" else int(var[1:])
    w = Window(cy, W, smooth=(var == "inf" or var[0] == "S"))
    last = (t_star + 1) if var == "inf" else min(NREC - 1, t_cyl + AFTER)
    det, margins, t0 = None, {}, time.monotonic()
    w.zs[0] = zs[0]
    for t in range(1, last + 1):
        lower, upper = w.as_range(t)
        if lower is None:
            raise RuntimeError(f"window LP infeasible before measurement {t}")
        margins[t] = G.margin(lower, upper, zs[t])
        if upper < zs[t] - DELTA or lower > zs[t] + DELTA:
            det = t
            break
        w.zs[t] = zs[t]
        if W is not None and t - w.tau > W + B:
            w.fold(t)
    res = {"seed": seed, "cell": cell, "ambient": amb, "variant": var, "W": W, "B": B, "t_star": t_star,
           "t_cyl16p": t_cyl, "detect": det, "censored_at": None if det is not None else last,
           "margin_at_t_star_mC": 1e3 * margins[t_star] if t_star in margins else None,
           "n_lp": w.n_lp, "n_retry": w.n_retry, "lp_seconds": round(w.lp_seconds, 1), "seconds": round(time.monotonic() - t0, 1),
           "max_vars": w.max_vars, "max_rows": w.max_rows}
    with open(Path(out) / f"w-{seed}-{cell}-{amb}-{var}.json", "w") as f:
        json.dump(res, f, indent=1)
    np.save(Path(out) / f"w-{seed}-{cell}-{amb}-{var}-margins.npy", np.array(sorted(margins.items())))
    return seed, var, det, t_star, t_cyl, res["seconds"]


def summary(out):
    rows = {}
    for f in sorted(out.glob("w-*.json")):
        r = json.load(open(f))
        rows.setdefault(r["seed"], {})[r["variant"]] = r
    rep = {"checks": {}, "R": {}, "criteria": {}}
    for seed, vs in rows.items():
        inf = vs.get("inf")
        rep["checks"][f"{seed} W=inf detects at t*"] = bool(inf and inf["detect"] == inf["t_star"])
        for v, r in vs.items():
            rep["checks"][f"{seed} {v} not before t*"] = r["detect"] is None or r["detect"] >= r["t_star"]
    for v in VARIANTS[1:]:
        Rs = {}
        for seed in HARD:
            r = rows[seed][v]
            td = r["detect"] if r["detect"] is not None else r["censored_at"]
            Rs[seed] = (r["t_cyl16p"] - td) / (r["t_cyl16p"] - r["t_star"])
        rep["R"][v] = Rs
        if v.startswith("S"):
            c1 = sum(x >= 0.5 for x in Rs.values()) >= 3
            c2 = all(rows[s][v]["detect"] is None or rows[s][v]["detect"] >= rows[s][v]["t_star"] for s in rows)
            c3 = rows[430019][v]["detect"] == 393
            rep["criteria"][v] = {"R_ge_half_in_3_of_4": bool(c1), "none_before_t_star": bool(c2),
                                  "control_at_t_star": bool(c3), "passes": bool(c1 and c2 and c3)}
    rep["detect"] = {seed: {v: (r["detect"], r["margin_at_t_star_mC"], r["seconds"], r["max_vars"])
                            for v, r in vs.items()} for seed, vs in rows.items()}
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("run", "summary"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--only", type=int)
    ap.add_argument("--variants", nargs="+", default=VARIANTS)
    a = ap.parse_args()
    if a.cmd == "summary":
        rep = summary(a.out)
        (a.out / "summary.json").write_text(json.dumps(rep, indent=1) + "\n")
        print(json.dumps(rep, indent=1))
        return
    a.out.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=G.ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=G.ROOT, text=True)
    meta = {"git_head": head, "git_dirty_tracked": bool(dirty), "B": B, "pad": PAD, "variants": a.variants,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    jobs = [(s, c, m, v, str(a.out)) for v in a.variants for s, c, m in RUNS if a.only in (None, s)]
    jobs.sort(key=lambda j: (j[0] != 430010, j[3] == "inf"))           # the long runs first
    with ProcessPoolExecutor(a.workers) as pool:
        for r in pool.map(job, jobs):
            print(r, flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
