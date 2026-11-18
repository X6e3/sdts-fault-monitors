"""DIAG-1 (task T1): the arms A-F of DIAG-1-PLAN.md on DEV runs. A numerical diagnostic, not certified.

For each run, a base pass (phase 1) computes the exact information state X_k by vertex enumeration, with the same
valid constraints that the template update applies (the TA box, the implied box of ac and as, the reachable-set
clamps of the cyl16p directions D), and cyl16p's own state P_k. For each start k0 = t* - L, phase 2 runs the arms:

  A       X_k0 -> exact recursion (the base pass itself)
  B       H_k0 = hull_D(X_k0) -> exact recursion
  E       P_k0 -> exact recursion
  C       H_k0 -> cyl16p's online update (pruned frozen table)
  C_full  H_k0 -> online update with every basis of the same directions
  D       P_k0 -> cyl16p's online update (must reproduce cyl16p)
  F       P_k0 with h(-e3) set to the exact -min TA of X_k0 -> cyl16p's online update

All the sets are taken after measurement k has been applied, and compared on the prediction for k+1, before
measurement k+1:
- the signed margin min(z+DELTA - lower, upper - (z-DELTA)) of the predicted as-range, negative = inconsistent;
- the supports of the predicted set in every direction of D.

Checks written to the output: A detects at the certified t*; D detects where cyl16p does; nesting of the supports
(A <= B <= C <= D, B <= E <= D, C_full <= C) up to 1e-9. At t* (arm A) the facets carrying the separating support,
with dual weights, normals and their best-matching ages, are also written.
usage: python -B diag1.py OUT_DIR --run SEED:CELL:AMBIENT [--run ...] [--L 16 64 256] [--cap 300] [--workers 10]
"""
import argparse
import json
import os
import pickle
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.optimize import linprog, nnls
from scipy.spatial import ConvexHull, HalfspaceIntersection, QhullError

HERE = Path(__file__).resolve().parent
V3 = HERE.parent
ROOT = V3.parents[1]
sys.path[:0] = [str(V3), str(V3.parent / "generators")]
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402

T = V.T
M = V.M
DELTA, RHO, LO, HI = T.DELTA, T.RHO_A, V.LO, V.HI
NREC = T.N
TOL = 1e-12


# ---- exact sets by vertices -------------------------------------------------------------------------------------

def hull(P):
    P = np.unique(np.round(P, 13), axis=0)
    if len(P) <= 3:
        return P, None
    try:
        h = ConvexHull(P)
    except QhullError:
        h = ConvexHull(P, qhull_options="QJ")
    return P[h.vertices], h


def clip(P, a, b):
    """vertices of conv(P) cap {a.x <= b} (empty array if empty)"""
    vals = P @ a - b
    if np.all(vals <= TOL):
        return P
    if np.all(vals > TOL):
        return np.empty((0, 3))
    pts = [P[vals <= TOL]]
    _, h = hull(P)
    if h is None:
        Q = P
        edges = [(i, j) for i in range(len(P)) for j in range(i + 1, len(P))]
    else:
        Q = h.points
        edges = {tuple(sorted((s[i], s[j]))) for s in h.simplices for i in range(3) for j in range(i + 1, 3)}
    vq = Q @ a - b
    for i, j in edges:
        if (vq[i] > 0) != (vq[j] > 0):
            t = vq[i] / (vq[i] - vq[j])
            pts.append((Q[i] + t * (Q[j] - Q[i]))[None, :])
    return np.vstack(pts)


class Exact:
    """the exact recursion with the constraints the template update also applies"""

    def __init__(self, tp):
        caps = tp.cap_inv.copy()
        for c in range(3):
            caps[tp.ip[c]] = min(caps[tp.ip[c]], HI)
            caps[tp.im[c]] = min(caps[tp.im[c]], -LO)
        self.cons = [(d, c) for d, c in zip(tp.D, caps) if np.isfinite(c)]
        self.D = tp.D

    def predict(self, X):
        Q = np.vstack([X @ M.T + np.array([0.0, 0.0, s * RHO]) for s in (1, -1)])
        Q, _ = hull(Q)
        for a, b in self.cons:
            Q = clip(Q, a, b)
            if not len(Q):
                return Q
        Q, _ = hull(Q)
        return Q

    @staticmethod
    def measure(Q, zs):
        for a, b in ((np.array([0, 1.0, 0]), zs + DELTA), (np.array([0, -1.0, 0]), -(zs - DELTA))):
            Q = clip(Q, a, b)
            if not len(Q):
                return Q
        Q, _ = hull(Q)
        return Q

    def supports(self, Q):
        return (Q @ self.D.T).max(axis=0)


def margin(lower, upper, zs):
    return min(zs + DELTA - lower, upper - (zs - DELTA))


def template_vertices(D, h):
    """vertices of {s : D s <= h}, or None if it has no interior"""
    norms = np.linalg.norm(D, axis=1)
    res = linprog(np.r_[0, 0, 0, -1.0], A_ub=np.c_[D, norms], b_ub=h, bounds=[(None, None)] * 3 + [(0, None)],
                  method="highs")
    if res.status != 0 or res.x[3] <= 1e-12:
        return None
    hs = HalfspaceIntersection(np.c_[D, -h], res.x[:3])
    return hull(hs.intersections)[0]


# ---- the template update, step by step (as TemplateMachine) -------------------------------------------------------

def t_step(tp, h_pred, zs):
    """check measurement zs against the predicted template h; returns (inconsistent, margin, h_tight)"""
    import math
    lo = math.nextafter(math.nextafter(zs, -math.inf) - DELTA, -math.inf)
    hi = math.nextafter(math.nextafter(zs, math.inf) + DELTA, math.inf)
    top = tp.support(h_pred, tp.supp_as[0])
    bottom = -tp.support(h_pred, tp.supp_as[1])
    m = margin(bottom, top, zs)
    if top < lo or bottom > hi:
        return True, m, None
    h = h_pred.copy()
    h[tp.ip[1]] = min(h[tp.ip[1]], hi)
    h[tp.im[1]] = min(h[tp.im[1]], -lo)
    return False, m, h


def zs_of(run):
    return [z - V.SHIFT for z in run["z"]]


# ---- phase 1: the base pass --------------------------------------------------------------------------------------

def base(job):
    seed, cell, amb, t_star, Ls, out = job
    run = S.run(seed, next(c for c in T.CELLS if c.name == cell), "E0", amb, "uniform")
    zs = zs_of(run)
    cy = V.load_frozen(V3 / "frozen" / "cyl16p.json")
    ex = Exact(cy)
    k0s = sorted({t_star - L for L in Ls})
    lo_rec = min(k0s) + 1
    rec = {"X": {}, "A_sup": {}, "A_margin": {}, "P_tight": {}, "A_asrange": {}, "A_ta": {}, "nverts": []}
    # exact pass: X_k after measurement k; the prediction for k+1 is checked at k+1
    X = np.array([[LO] * 3, [HI] * 3])                       # the initial segment (start at the P0 steady state)
    t_exact = None
    t0 = time.monotonic()
    for k in range(t_star + 1):
        if k > 0:
            Q = ex.predict(X)
            lower, upper = Q[:, 1].min(), Q[:, 1].max()
            if k >= lo_rec:
                rec["A_sup"][k] = ex.supports(Q)
                rec["A_margin"][k] = margin(lower, upper, zs[k])
            rec["A_asrange"][k] = (lower, upper)
            if k == t_star:
                rec["Q_tstar"] = Q
        else:
            Q = X
        Xn = Exact.measure(Q, zs[k])
        if not len(Xn):
            t_exact = k
            break
        X = Xn
        rec["nverts"].append(len(X))
        rec["A_ta"][k] = (X[:, 2].min(), X[:, 2].max())
        if k in k0s:
            rec["X"][k] = X.copy()
    rec["t_exact"] = t_exact
    rec["seconds_exact"] = round(time.monotonic() - t0, 1)
    # cyl16p's own state, after each measurement, through the whole record
    m = V.TemplateMachine(cy)
    t_cy = None
    for k, (y, p) in enumerate(zip(run["y"], run["P"])):
        if m.observe(y, p):
            t_cy = k
            break
        if k in k0s:
            rec["P_tight"][k] = m._last_tightened.copy()
    rec["t_cyl16p"] = t_cy
    rec["zs"] = zs
    with open(Path(out) / f"base-{seed}-{cell}-{amb}.pkl", "wb") as f:
        pickle.dump(rec, f)
    return seed, cell, amb, t_exact, t_cy, rec["seconds_exact"], max(rec["nverts"]) if rec["nverts"] else 0


# ---- phase 2: the arms from one start -----------------------------------------------------------------------------

AGE_J = 3000


def ages(n):
    """best-matching ages of a facet normal (see the plan, section 3 and amendment 1)"""
    e3, one = np.array([0, 0, 1.0]), np.ones(3) / np.sqrt(3)
    u = e3.copy()
    best_amb = (abs(n @ u), 0)
    for j in range(1, AGE_J + 1):
        u = M @ u
        r = abs(n @ (u / np.linalg.norm(u)))
        if r < best_amb[0]:
            best_amb = (r, j)
    w = np.array([0, 1.0, 0])
    Minv_T = np.linalg.inv(M).T
    best_meas = (np.degrees(np.arccos(min(1.0, abs(n @ w)))), 0)
    for j in range(1, AGE_J + 1):
        w = Minv_T @ w
        w /= np.linalg.norm(w)
        a = np.degrees(np.arccos(min(1.0, abs(n @ w))))
        if a < best_meas[0]:
            best_meas = (a, j)
    return {"ambient_age": best_amb[1], "ambient_residual": best_amb[0], "abs_n_e3": abs(n @ e3),
            "abs_n_111": abs(n @ one), "measurement_age": best_meas[1], "measurement_angle_deg": best_meas[0]}


def separating_facets(Q, zs, D):
    lower, upper = Q[:, 1].min(), Q[:, 1].max()
    side = "-e2" if lower > zs + DELTA else ("+e2" if upper < zs - DELTA else None)
    if side is None:
        return {"side": None}
    g = np.array([0, 1.0, 0]) * (1 if side == "+e2" else -1)
    h = ConvexHull(Q)
    v = Q[np.argmax(Q @ g)]
    eq = h.equations
    act = eq[np.abs(eq[:, :3] @ v + eq[:, 3]) < 1e-9]
    normals = np.unique(np.round(act[:, :3], 9), axis=0)
    lam, res = nnls(normals.T, g)
    facets = []
    for n, l in zip(normals, lam):
        if l <= 1e-12:
            continue
        dmatch = float(np.max(np.abs(D @ n)))
        facets.append({"normal": n.tolist(), "weight": float(l), "max_abs_dot_D": dmatch, **ages(n)})
    facets.sort(key=lambda f: -f["weight"])
    return {"side": side, "nnls_residual": float(res), "facets": facets}


def arms(job):
    seed, cell, amb, t_star, L, cap, out = job
    with open(Path(out) / f"base-{seed}-{cell}-{amb}.pkl", "rb") as f:
        rec = pickle.load(f)
    zs = rec["zs"]
    k0 = t_star - L
    cy = V.load_frozen(V3 / "frozen" / "cyl16p.json")
    full = V.Template(cy.D, name="cyl16 full", invariant=True)
    ex = Exact(cy)
    D = cy.D
    X0, P0 = rec["X"][k0], rec["P_tight"][k0]
    H0 = (X0 @ D.T).max(axis=0)
    F0 = P0.copy()
    F0[cy.im[2]] = min(F0[cy.im[2]], -X0[:, 2].min())
    out_arms, sup = {}, {}
    # exact arms B and E
    for name, start in (("B", template_vertices(D, H0)), ("E", template_vertices(D, P0))):
        if start is None:
            out_arms[name] = {"error": "start set has no interior"}
            continue
        Xc, det, mar, s = start, None, {}, {}
        for k in range(k0 + 1, min(NREC, t_star + cap + 1)):
            Q = ex.predict(Xc)
            lower, upper = Q[:, 1].min(), Q[:, 1].max()
            mar[k] = margin(lower, upper, zs[k])
            if k <= t_star:
                s[k] = ex.supports(Q)
            Xn = Exact.measure(Q, zs[k])
            if not len(Xn):
                det = k
                break
            Xc = Xn
        out_arms[name] = {"detect": det, "censored_at": None if det is not None else min(NREC, t_star + cap + 1) - 1,
                          "margin": mar}
        sup[name] = s
    # template arms C, C_full, D, F
    for name, tp, h_start in (("C", cy, H0), ("C_full", full, H0), ("D", cy, P0), ("F", cy, F0)):
        h_tight, det, mar, s = h_start.copy(), None, {}, {}
        for k in range(k0 + 1, NREC):
            h_pred = tp.predict(h_tight.copy())
            if k <= t_star:
                vv = template_vertices(D, h_pred)
                s[k] = (vv @ D.T).max(axis=0) if vv is not None else h_pred
            inc, mk, h_tight = t_step(tp, h_pred, zs[k])
            mar[k] = mk
            if inc:
                det = k
                break
        out_arms[name] = {"detect": det, "margin": mar}
        sup[name] = s
    out_arms["A"] = {"detect": rec["t_exact"], "margin": {k: v for k, v in rec["A_margin"].items() if k > k0}}
    sup["A"] = {k: v for k, v in rec["A_sup"].items() if k > k0}
    # nesting checks on the recorded supports
    nest = {}
    for lo_, hi_ in (("A", "B"), ("B", "C"), ("C", "D"), ("B", "E"), ("E", "D"), ("C_full", "C")):
        ks = sorted(set(sup.get(lo_, {})) & set(sup.get(hi_, {})))
        worst = max((float(np.max(sup[lo_][k] - sup[hi_][k])) for k in ks), default=None)
        nest[f"{lo_}<={hi_}"] = {"steps": len(ks), "worst_excess": worst, "ok": worst is None or worst <= 1e-9}
    # gaps against A at the first step and at t*
    gaps = {}
    for name in sup:
        if name == "A":
            continue
        g = {}
        for k in (k0 + 1, t_star):
            if k in sup[name] and k in sup["A"]:
                d = sup[name][k] - sup["A"][k]
                i = int(np.argmax(d))
                g[str(k)] = {"max_gap": float(d[i]), "argmax_direction": D[i].tolist(),
                             "gap_minus_e3_TA_lower": float(d[cy.im[2]]), "gap_plus_e2": float(d[cy.ip[1]]),
                             "gap_minus_e2": float(d[cy.im[1]])}
        gaps[name] = g
    result = {"seed": seed, "cell": cell, "ambient": amb, "arm": "E0", "t_star": t_star, "L": L, "k0": k0,
              "t_exact_base": rec["t_exact"], "t_cyl16p": rec["t_cyl16p"],
              "checks": {"A_detects_at_t_star": rec["t_exact"] == t_star,
                         "D_reproduces_cyl16p": out_arms["D"]["detect"] == rec["t_cyl16p"], "nesting": nest},
              "detect": {n: a.get("detect") for n, a in out_arms.items()},
              "censored": {n: a.get("censored_at") for n, a in out_arms.items() if "censored_at" in a},
              "gaps_vs_A": gaps,
              "start": {"H_minus_P_TA_lower": float(H0[cy.im[2]] - P0[cy.im[2]]),
                        "H_minus_P_max": float(np.max(H0 - P0))}}
    result["separating_at_t_star"] = separating_facets(rec["Q_tstar"], zs[t_star], D) if "Q_tstar" in rec else None
    np.savez_compressed(Path(out) / f"arms-{seed}-{cell}-{amb}-L{L}.npz",
                        **{f"sup_{n}": np.array([s[k] for k in sorted(s)]) for n, s in sup.items() if s},
                        **{f"ks_{n}": np.array(sorted(s)) for n, s in sup.items() if s},
                        **{f"margin_{n}": np.array([[k, v] for k, v in sorted(a["margin"].items())]) for n, a in out_arms.items()})
    with open(Path(out) / f"arms-{seed}-{cell}-{amb}-L{L}.json", "w") as f:
        json.dump(result, f, indent=1, default=float)
    return seed, cell, amb, L, result["detect"], result["checks"]["A_detects_at_t_star"], \
        result["checks"]["D_reproduces_cyl16p"], all(v["ok"] for v in nest.values())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--run", action="append", required=True, help="SEED:CELL:AMBIENT (E0, uniform)")
    ap.add_argument("--L", type=int, nargs="+", default=[16, 64, 256])
    ap.add_argument("--cap", type=int, default=300)
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(l) for l in (ROOT / "results/v3/dev-45cff1d/rows.jsonl").read_text().splitlines() if l.strip()]
    runs = []
    for spec in a.run:
        seed, cell, amb = spec.split(":")
        r = next(r for r in rows if r["seed"] == int(seed) and r["cell"] == cell and r["ambient"] == amb
                 and r["arm"] == "E0" and r["noise"] == "uniform")
        assert r["oracle"]["status"] == "certified"
        runs.append((int(seed), cell, amb, r["oracle"]["t_star"]))
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True)
    meta = {"git_head": head, "git_dirty_tracked": bool(dirty), "runs": runs, "L": a.L, "cap": a.cap,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    with ProcessPoolExecutor(min(a.workers, len(runs))) as pool:
        for r in pool.map(base, [(*x, a.L, str(a.out)) for x in runs]):
            print("base", r, flush=True)
    jobs = [(*x, L, a.cap, str(a.out)) for x in runs for L in a.L if x[3] - L >= 0]
    with ProcessPoolExecutor(min(a.workers, len(jobs))) as pool:
        for r in pool.map(arms, jobs):
            print("arms", r, flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
