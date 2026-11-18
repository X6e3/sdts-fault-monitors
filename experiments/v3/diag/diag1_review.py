"""DIAG-1, review round 1: read-only analyses of the T1 outputs. No arm is rerun; nothing is written but stdout.

  steps  RUN_DIR   per L=256 job: the active side of the margin at t*; the step profile of the C-B gap in +-e3 and
                   +-e2; whether each rise of the TA gap (C-B, +-e3) over 1 mC follows a step at which z's slab cuts
                   the predicted as-range of arm C or B; the first steps of 430007 and 430010 (Hydrogen's H1 numbers).
  ages   RUN_DIR   for the separating facets at t*: |n . M^j e3| / |M^j e3| at several j (age 0 and age "infinity").
  k0gaps RUN_DIR   needs the base pickles (Arch only): the largest hull_D(X_k0) - X_k0 gaps over the facet normals of
                   X_k0 (k0 = t* - 256), with their angles to D and to the arc +-(M^T)^j e2, j <= 256.

usage: python -B diag1_review.py {steps|ages|k0gaps} RUN_DIR   (SDTS_V3=<checkout>/experiments/v3 if run elsewhere)
"""
import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
V3 = Path(os.environ.get("SDTS_V3", HERE.parent))      # SDTS_V3: run from outside a checkout
sys.path[:0] = [str(V3), str(V3.parent / "generators")]
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402

T = V.T
M = V.M
DELTA = T.DELTA
CY = V.load_frozen(V3 / "frozen" / "cyl16p.json")
D = CY.D
IP2, IM2, IP3, IM3 = CY.ip[1], CY.im[1], CY.ip[2], CY.im[2]
RUNS = [(430007, "drift_0.002", "rw"), (430027, "drift_0.002", "rw"), (430000, "drift_0.001", "ramp"),
        (430010, "drift_0.0005", "ramp"), (430019, "drift_0.001", "ramp")]


def zs_of(seed, cell, amb):
    run = S.run(seed, next(c for c in T.CELLS if c.name == cell), "E0", amb, "uniform")
    return [z - V.SHIFT for z in run["z"]]


def load(rd, seed, cell, amb, L=256):
    j = json.load(open(rd / f"arms-{seed}-{cell}-{amb}-L{L}.json"))
    z = np.load(rd / f"arms-{seed}-{cell}-{amb}-L{L}.npz")
    sup = {a: dict(zip(z[f"ks_{a}"].tolist(), z[f"sup_{a}"])) for a in "ABCDE"}
    return j, sup


def cuts(sup, zs, ks):
    """steps k at which z_k's slab cuts the predicted as-range of this arm"""
    return {k for k in ks if sup[k][IP2] > zs[k] + DELTA or -sup[k][IM2] < zs[k] - DELTA}


def steps(rd):
    total = [0, 0, 0.0, 0.0]
    for seed, cell, amb in RUNS:
        zs = zs_of(seed, cell, amb)
        j, sup = load(rd, seed, cell, amb)
        ts, k0 = j["t_star"], j["k0"]
        ks = list(range(k0 + 1, ts + 1))
        print(f"\n=== {seed} {cell} {amb} L=256 k0={k0} t*={ts} detect={j['detect']}")
        for a in "ABCDE":
            s = sup[a][ts]
            ml, mu = zs[ts] + DELTA + s[IM2], s[IP2] - (zs[ts] - DELTA)
            print(f"  t* arm {a}: lower side {ml * 1e3:+.3f} mC, upper side {mu * 1e3:+.3f} mC -> active "
                  f"{'lower' if ml < mu else 'upper'}")
        for lab, i in (("+e3", IP3), ("-e3", IM3), ("+e2", IP2), ("-e2", IM2)):
            cb = np.array([sup["C"][k][i] - sup["B"][k][i] for k in ks]) * 1e3
            prof = " ".join(f"{m}:{cb[m - 1]:.1f}" for m in (1, 4, 8, 16, 32, 64, 128, 192, 256))
            print(f"  C-B {lab} (mC) at dk  {prof}   max {cb.max():.1f} at dk={int(cb.argmax()) + 1}")
        cc, cbs = cuts(sup["C"], zs, ks), cuts(sup["B"], zs, ks)
        n_cut = n_other = 0
        m_cut = m_other = 0.0
        for i in (IP3, IM3):
            d = np.diff([sup["C"][k][i] - sup["B"][k][i] for k in ks])
            for t, r in enumerate(d):
                if r > 1e-3:
                    if ks[t] in cc or ks[t] in cbs:
                        n_cut, m_cut = n_cut + 1, m_cut + r
                    else:
                        n_other, m_other = n_other + 1, m_other + r
        total = [total[0] + n_cut, total[1] + n_other, total[2] + m_cut, total[3] + m_other]
        print(f"  slab cuts the predicted as-range at {len(cc)} of {len(ks)} steps in C, {len(cbs)} in B")
        print(f"  TA-gap rises (C-B, +-e3) over 1 mC: {n_cut} right after a cut step ({m_cut * 1e3:.1f} mC), "
              f"{n_other} after other steps ({m_other * 1e3:.1f} mC)")
    print(f"\nall 5 runs: {total[0]} rises right after a cut step ({total[2] * 1e3:.1f} mC), "
          f"{total[1]} after other steps ({total[3] * 1e3:.1f} mC)")
    i36 = 36
    mt = M.T @ D[i36]
    print(f"\nd[36] = {np.round(D[i36], 6)}; M^T d[36] = {np.round(mt, 6)}, "
          f"{np.degrees(np.arccos(np.max(D @ mt) / np.linalg.norm(mt))):.2f} deg from the nearest direction of D")
    for seed, cell, amb in [(430007, "drift_0.002", "rw"), (430010, "drift_0.0005", "ramp")]:
        zs = zs_of(seed, cell, amb)
        j, sup = load(rd, seed, cell, amb)
        print(f"\n{seed}: k | A: sup(+e3) sup(-e3) | C-A: +e3 -e3 | B-A: +e3 -e3 | d[36]: C-A B-A (mC) | "
              f"z+delta, A's as max | z-delta, A's as min")
        for k in range(j["k0"] + 1, j["k0"] + 11):
            a, b, c = sup["A"][k], sup["B"][k], sup["C"][k]
            print(f"  {k} | {a[IP3]:+.5f} {a[IM3]:+.5f} | {1e3 * (c[IP3] - a[IP3]):6.2f} {1e3 * (c[IM3] - a[IM3]):6.2f} | "
                  f"{1e3 * (b[IP3] - a[IP3]):6.2f} {1e3 * (b[IM3] - a[IM3]):6.2f} | "
                  f"{1e3 * (c[i36] - a[i36]):6.3f} {1e3 * (b[i36] - a[i36]):6.3f} | "
                  f"{zs[k] + DELTA:+.5f} {a[IP2]:+.5f} | {zs[k] - DELTA:+.5f} {-a[IM2]:+.5f}")


def ages(rd):
    ev = np.linalg.eigvals(M).real
    print("eigenvalues of M", np.round(np.sort(ev), 8), "time constants",
          [round(-1 / np.log(x), 2) for x in np.sort(ev)[:2]])
    js = (0, 4, 10, 16, 64, 256, 1000)
    print("seed | normal | weight | |n.(1,1,1)|/sqrt3 | |n . M^j e3| / |M^j e3| at j = " + ", ".join(map(str, js)))
    for f in sorted(rd.glob("arms-*-L256.json")):
        j = json.load(open(f))
        for fa in j["separating_at_t_star"]["facets"]:
            n, u, r = np.array(fa["normal"]), np.array([0, 0, 1.0]), {}
            for k in range(max(js) + 1):
                if k in js:
                    r[k] = abs(n @ (u / np.linalg.norm(u)))
                u = M @ u
            print(f"{j['seed']} | {np.round(n, 3)} | {fa['weight']:.2f} | {fa['abs_n_111']:.3f} | "
                  + " ".join(f"{r[k]:.3f}" for k in js))


def k0gaps(rd):
    from scipy.optimize import linprog
    from scipy.spatial import ConvexHull
    arc, u = [], np.array([0, 1.0, 0])
    for _ in range(257):
        arc.append(u / np.linalg.norm(u))
        u = M.T @ u
    arc = np.array(arc)
    for seed, cell, amb in RUNS[:4]:
        j = json.load(open(rd / f"arms-{seed}-{cell}-{amb}-L256.json"))
        rec = pickle.load(open(rd / f"base-{seed}-{cell}-{amb}.pkl", "rb"))
        X = rec["X"][j["k0"]]
        H0 = (X @ D.T).max(axis=0)
        N = np.unique(np.round(ConvexHull(X).equations[:, :3], 9), axis=0)
        gaps = np.array([-linprog(-n, A_ub=D, b_ub=H0, bounds=[(None, None)] * 3, method="highs").fun - (X @ n).max()
                         for n in N])
        print(f"{seed} k0={j['k0']}: {len(X)} vertices, {len(N)} facet normals; the 6 largest hull_D - X gaps:")
        for i in np.argsort(-gaps)[:6]:
            n = N[i]
            a_arc = np.degrees(np.arccos(min(1.0, np.abs(arc @ n).max())))
            a_d = np.degrees(np.arccos(min(1.0, (D @ n).max())))
            print(f"   n={np.round(n, 3)} gap {gaps[i] * 1e3:.3f} mC; {a_d:.1f} deg from D, {a_arc:.1f} deg from "
                  f"+-(M^T)^j e2")


if __name__ == "__main__":
    {"steps": steps, "ages": ages, "k0gaps": k0gaps}[sys.argv[1]](Path(sys.argv[2]))
