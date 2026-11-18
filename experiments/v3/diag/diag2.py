"""DIAG-2 (DIAG-2-PLAN.md): T1, the cut steps of DIAG-1 split exactly; T2, the families B1 and B2 in the arms.
A numerical diagnostic on DEV runs, not certified. Reuses diag1.py's exact sets and template step.

usage:
  python -B diag2.py families                               B1/B2, checked against Hydrogen's posted list
  python -B diag2.py run OUT_DIR --diag1 DIAG1_RUN_DIR      T1 (5 jobs) and T2 (15 jobs); needs the base pickles
  python -B diag2.py summary OUT_DIR --diag1 DIAG1_RUN_DIR  the criteria of the plan, from the outputs
"""
import argparse
import json
import math
import os
import pickle
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diag1 as G  # noqa: E402

V, S, T, M = G.V, G.S, G.T, G.M
DELTA, RHO, LO, HI, NREC = G.DELTA, G.RHO, G.LO, G.HI, G.NREC
L, CAP = 256, 300
RUNS = [(430007, "drift_0.002", "rw"), (430027, "drift_0.002", "rw"), (430000, "drift_0.001", "ramp"),
        (430010, "drift_0.0005", "ramp"), (430019, "drift_0.001", "ramp")]
HARD = (430007, 430027, 430000, 430010)
E3 = (np.array([0, 0, 1.0]), np.array([0, 0, -1.0]))

# Hydrogen's posted list (DIAG1-H1, round 2): the 26 added pairs, +u, 6 decimals
HYDROGEN_H1 = [
    (0.211667, 0.973668, 0.084667), (0.136692, 0.628782, -0.765473), (0.874064, 0.484378, 0.037270),
    (0.410433, 0.908577, 0.077663), (0.025093, -0.995794, -0.088115), (0.284166, -0.954898, -0.086137),
    (0.878130, -0.476049, -0.047589), (0.959903, -0.278650, -0.030669), (0.995378, -0.094910, -0.014663),
    (0.768516, -0.623083, -0.145433), (0.786514, 0.607912, 0.108808), (0.694844, 0.647043, 0.313890),
    (0.813808, -0.464237, -0.349572), (0.923258, 0.363073, 0.125588), (0.966662, -0.170071, -0.191417),
    (0.939693, 0.000000, 0.342020), (0.000000, 0.939693, 0.342020), (0.664463, -0.664463, -0.342020),
    (0.939693, -0.000000, -0.342020), (0.664463, 0.664463, -0.342020), (0.000000, 0.939693, -0.342020),
    (0.766044, 0.000000, 0.642788), (0.383022, 0.663414, 0.642788), (0.383022, -0.663414, -0.642788),
    (0.383022, 0.663414, -0.642788), (0.383022, -0.663414, 0.642788)]


# ---- the families --------------------------------------------------------------------------------------------------

def _add(D, cands, min_deg):
    """add each candidate as a +- pair when it lies more than min_deg from the current set (Hydrogen's rule)"""
    out, added = [np.asarray(x, float) for x in D], []
    thr = math.cos(math.radians(min_deg))
    for raw in cands:
        u = np.asarray(raw, float)
        if np.linalg.norm(u) == 0:
            continue
        u = u / np.linalg.norm(u)
        first = next(c for c in u if abs(c) > 1e-12)
        u = -u if first < 0 else u
        if float(np.max(np.array(out) @ u)) < thr:
            out += [u, -u]
            added.append(u)
    return np.array(out), added


def families():
    D0 = V.load_frozen(V3 / "frozen" / "cyl16p.json").D
    D1, a1 = _add(D0, [M.T @ D0[i] for i in range(0, len(D0), 2)], 4.8)
    a2 = []
    for j in (2, 4):
        Mj = np.linalg.matrix_power(M.T, j)
        for i in (2, 6, 20, 22, 24, 36, 38):
            D1, new = _add(D1, [Mj @ D0[i]], 7.0)
            a2 += new
    D2, a3 = D1, []
    for lat, m in ((20.0, 8), (40.0, 6)):
        z, r = math.sin(math.radians(lat)), math.cos(math.radians(lat))
        for k in range(m):
            a = 2 * math.pi * k / m
            D2, new = _add(D2, [[r * math.cos(a), r * math.sin(a), z]], 12.0)
            a3 += new
    added = np.array(a1 + a2 + a3)
    return {"D0": D0, "B1": D1, "B2": D2}, added


V3 = G.V3
FAMS, ADDED = families()


def check_families():
    ref = np.array(HYDROGEN_H1)
    ok = len(ADDED) == len(ref) and float(np.max(np.abs(ADDED - ref))) < 1e-6
    return {"n": {k: len(v) for k, v in FAMS.items()}, "added_pairs": len(ADDED),
            "max_abs_diff_to_hydrogen_list": float(np.max(np.abs(ADDED - ref))) if len(ADDED) == len(ref) else None,
            "matches_hydrogen_list": ok}


# ---- helpers -------------------------------------------------------------------------------------------------------

def lp_supp(D, h, u):
    r = linprog(-u, A_ub=D, b_ub=h, bounds=[(None, None)] * 3, method="highs")
    if r.status != 0:
        raise RuntimeError(f"LP status {r.status}: {r.message}")
    return -r.fun


def slab(zs):
    lo = math.nextafter(math.nextafter(zs, -math.inf) - DELTA, -math.inf)
    hi = math.nextafter(math.nextafter(zs, math.inf) + DELTA, math.inf)
    return lo, hi


def cut_h(tp, h, zs):
    lo, hi = slab(zs)
    h = h.copy()
    h[tp.ip[1]] = min(h[tp.ip[1]], hi)
    h[tp.im[1]] = min(h[tp.im[1]], -lo)
    return h


def load_d1(d1, seed, cell, amb):
    j = json.load(open(d1 / f"arms-{seed}-{cell}-{amb}-L{L}.json"))
    z = np.load(d1 / f"arms-{seed}-{cell}-{amb}-L{L}.npz")
    sup = {a: dict(zip(z[f"ks_{a}"].tolist(), z[f"sup_{a}"])) for a in ("A", "B", "C", "C_full")}
    mar = {a: dict((int(k), v) for k, v in z[f"margin_{a}"]) for a in ("A", "C_full")}
    return j, sup, mar


def events_of(d1, seed, cell, amb, zs, cy):
    """the event steps of review1/steps.txt: a cut at k (C or B), then a rise over 1 mC of C - B in +-e3 at k+1"""
    j, sup, _ = load_d1(d1, seed, cell, amb)
    ks = list(range(j["k0"] + 1, j["t_star"] + 1))
    ip2, im2 = cy.ip[1], cy.im[1]

    def cuts(s):
        return {k for k in ks if s[k][ip2] > zs[k] + DELTA or -s[k][im2] < zs[k] - DELTA}
    cc = cuts(sup["C"]) | cuts(sup["B"])
    ev = set()
    for i in (cy.ip[2], cy.im[2]):
        g = [sup["C"][k][i] - sup["B"][k][i] for k in ks]
        for t in range(len(ks) - 1):
            if g[t + 1] - g[t] > 1e-3 and ks[t] in cc:
                ev.add(ks[t])
    return sorted(ev)


# ---- T1: the cut steps -------------------------------------------------------------------------------------------

def t1(job):
    seed, cell, amb, d1, out = job
    d1 = Path(d1)
    cy = V.load_frozen(V3 / "frozen" / "cyl16p.json")
    rec = pickle.load(open(d1 / f"base-{seed}-{cell}-{amb}.pkl", "rb"))
    zs = rec["zs"]
    j, sup1, _ = load_d1(d1, seed, cell, amb)
    t_star, k0 = j["t_star"], j["k0"]
    ev = events_of(d1, seed, cell, amb, zs, cy)
    ex = G.Exact(cy)
    # arm A again, keeping Q at the events
    X, Q_at, t_exact = np.array([[LO] * 3, [HI] * 3]), {}, None
    for k in range(t_star + 1):
        Q = ex.predict(X) if k > 0 else X
        if k in ev:
            Q_at[k] = Q
        Xn = G.Exact.measure(Q, zs[k])
        if not len(Xn):
            t_exact = k
            break
        X = Xn
    # arm C again (pruned cyl16p table, from hull_D(X_k0)), keeping its predicted h at the events
    h_tight, hC = (rec["X"][k0] @ cy.D.T).max(axis=0), {}
    for k in range(k0 + 1, t_star + 1):
        h_pred = cy.predict(h_tight.copy())
        if k in ev:
            hC[k] = h_pred.copy()
        inc, _, h_tight = G.t_step(cy, h_pred, zs[k])
        if inc:
            break
    tps = {f: V.Template(FAMS[f], name=f, invariant=True) for f in ("D0", "B1", "B2")}
    rows = []
    for k in ev:
        Q, h = Q_at[k], hC[k]
        QS = G.Exact.measure(Q, zs[k])
        hcut = cut_h(cy, h, zs[k])
        nextA_cut, nextA_skip = ex.predict(QS), ex.predict(Q)
        nextC_cut, nextC_skip = cy.predict(hcut.copy()), cy.predict(h.copy())
        r = {"k": k, "check_C_vs_diag1_mC": float(1e3 * max(abs(lp_supp(cy.D, h, u) - sup1["C"][k][i])
                                                                for u, i in zip(E3, (cy.ip[2], cy.im[2]))))}
        for name, u in zip(("+e3", "-e3"), E3):
            ex_pre, ex_cut = float((Q @ u).max()), float((QS @ u).max())
            c_pre, c_cut = lp_supp(cy.D, h, u), lp_supp(cy.D, hcut, u)
            geo = {}
            for f, tp in tps.items():
                hF = cut_h(tp, (Q @ tp.D.T).max(axis=0), zs[k])
                geo[f] = 1e3 * (lp_supp(tp.D, hF, u) - ex_cut)
            r[name] = {"gap_pre_mC": 1e3 * (c_pre - ex_pre), "gap_cut_mC": 1e3 * (c_cut - ex_cut),
                       "accumulated_mC": 1e3 * (c_cut - ex_cut) - geo["D0"], "geometry_mC": geo,
                       "next_gap_with_cut_mC": 1e3 * (lp_supp(cy.D, nextC_cut, u) - float((nextA_cut @ u).max())),
                       "next_gap_skip_mC": 1e3 * (lp_supp(cy.D, nextC_skip, u) - float((nextA_skip @ u).max()))}
        rows.append(r)
    res = {"seed": seed, "cell": cell, "ambient": amb, "t_star": t_star, "k0": k0, "t_exact_recomputed": t_exact,
           "A_reproduces_t_star": t_exact == t_star, "events": ev, "rows": rows}
    with open(Path(out) / f"t1-{seed}-{cell}-{amb}.json", "w") as f:
        json.dump(res, f, indent=1)
    return seed, len(ev), t_exact == t_star


# ---- T2: the families in the arms ----------------------------------------------------------------------------------

def t2(job):
    seed, cell, amb, fam, d1, out = job
    d1 = Path(d1)
    rec = pickle.load(open(d1 / f"base-{seed}-{cell}-{amb}.pkl", "rb"))
    zs = rec["zs"]
    j, _, _ = load_d1(d1, seed, cell, amb)
    t_star, k0 = j["t_star"], j["k0"]
    D0, F = FAMS["D0"], FAMS[fam]
    tp = V.Template(F, name=fam, invariant=True)
    HF = (rec["X"][k0] @ F.T).max(axis=0)
    arms, sup = {}, {}
    # B_F: exact recursion from hull_F(X_k0), with F's clamps
    ex = G.Exact(tp)
    Xc, det, mar, s = G.template_vertices(F, HF), None, {}, {}
    for k in range(k0 + 1, min(NREC, t_star + CAP + 1)):
        Q = ex.predict(Xc)
        mar[k] = G.margin(Q[:, 1].min(), Q[:, 1].max(), zs[k])
        if k <= t_star:
            s[k] = (Q @ D0.T).max(axis=0)
        Xn = G.Exact.measure(Q, zs[k])
        if not len(Xn):
            det = k
            break
        Xc = Xn
    arms["B"], sup["B"] = {"detect": det, "margin": mar}, s
    # C_F: F's online update from hull_F(X_k0)
    h_tight, det, mar, s = HF.copy(), None, {}, {}
    for k in range(k0 + 1, NREC):
        h_pred = tp.predict(h_tight.copy())
        if k <= t_star:
            vv = G.template_vertices(F, h_pred)
            s[k] = (vv @ D0.T).max(axis=0)
        inc, mk, h_tight = G.t_step(tp, h_pred, zs[k])
        mar[k] = mk
        if inc:
            det = k
            break
    arms["C"], sup["C"] = {"detect": det, "margin": mar}, s
    # D_F: F's own state from k = 0 (the candidate on this run)
    run = S.run(seed, next(c for c in T.CELLS if c.name == cell), "E0", amb, "uniform")
    arms["D"] = {"detect": V.first_inconsistent(tp, run["y"], run["P"])}
    res = {"seed": seed, "cell": cell, "ambient": amb, "family": fam, "n_directions": len(F),
           "table_entries": tp.table_entries, "t_star": t_star, "k0": k0, "t_cyl16p": rec["t_cyl16p"],
           "detect": {a: v["detect"] for a, v in arms.items()},
           "margin_at_t_star_mC": {a: 1e3 * arms[a]["margin"][t_star] for a in ("B", "C")
                                   if t_star in arms[a]["margin"]}}
    np.savez_compressed(Path(out) / f"t2-{seed}-{cell}-{amb}-{fam}.npz",
                        **{f"sup_{a}": np.array([v[k] for k in sorted(v)]) for a, v in sup.items()},
                        **{f"ks_{a}": np.array(sorted(v)) for a, v in sup.items()},
                        **{f"margin_{a}": np.array([[k, m] for k, m in sorted(arms[a]["margin"].items())])
                           for a in ("B", "C")})
    with open(Path(out) / f"t2-{seed}-{cell}-{amb}-{fam}.json", "w") as f:
        json.dump(res, f, indent=1)
    return seed, fam, res["detect"], res["table_entries"]


# ---- summary: the plan's criteria ----------------------------------------------------------------------------------

def summary(out, d1):
    cy = V.load_frozen(V3 / "frozen" / "cyl16p.json")
    i3 = (cy.ip[2], cy.im[2])
    rep = {"families": check_families(), "t1": {}, "t2": {}, "checks": {}, "criteria": {}}
    # T1
    tot = {"accumulated": 0.0, "geometry_D0": 0.0, "geometry_B1": 0.0, "geometry_B2": 0.0, "rise_cut": 0.0,
           "rise_skip": 0.0, "rise_at_cut": 0.0, "rise_beyond_geometry": 0.0, "n": 0}
    for seed, cell, amb in RUNS:
        t = json.load(open(out / f"t1-{seed}-{cell}-{amb}.json"))
        rep["checks"][f"t1 {seed} A reproduces t*"] = t["A_reproduces_t_star"]
        rep["checks"][f"t1 {seed} C matches DIAG-1 (max mC)"] = max((r["check_C_vs_diag1_mC"] for r in t["rows"]),
                                                                     default=0.0)
        per = {"events": len(t["rows"]), "accumulated_mC": 0.0, "geometry_mC": {"D0": 0.0, "B1": 0.0, "B2": 0.0},
               "rise_with_cut_mC": 0.0, "rise_skip_mC": 0.0, "rise_at_cut_mC": 0.0, "rise_beyond_geometry_mC": 0.0}
        for r in t["rows"]:
            for u in ("+e3", "-e3"):
                x = r[u]
                per["accumulated_mC"] += x["accumulated_mC"]
                for f in ("D0", "B1", "B2"):
                    per["geometry_mC"][f] += x["geometry_mC"][f]
                per["rise_with_cut_mC"] += x["next_gap_with_cut_mC"] - x["gap_pre_mC"]
                per["rise_skip_mC"] += x["next_gap_skip_mC"] - x["gap_pre_mC"]
                # at k itself: rise = gap_cut - gap_pre = geometry(D0) + (accumulated - gap_pre), exactly
                per["rise_at_cut_mC"] += x["gap_cut_mC"] - x["gap_pre_mC"]
                per["rise_beyond_geometry_mC"] += x["accumulated_mC"] - x["gap_pre_mC"]
        rep["t1"][seed] = per
        tot["n"] += per["events"]
        tot["accumulated"] += per["accumulated_mC"]
        for f in ("D0", "B1", "B2"):
            tot[f"geometry_{f}"] += per["geometry_mC"][f]
        tot["rise_cut"] += per["rise_with_cut_mC"]
        tot["rise_skip"] += per["rise_skip_mC"]
        tot["rise_at_cut"] += per["rise_at_cut_mC"]
        tot["rise_beyond_geometry"] += per["rise_beyond_geometry_mC"]
    rep["t1"]["total"] = tot
    # T2
    rises = {f: 0.0 for f in ("ref", "D0", "B1", "B2")}
    loss_ok = {f: 0 for f in ("B1", "B2")}
    recov = {f: 0 for f in ("B1", "B2")}
    for seed, cell, amb in RUNS:
        j1, sup1, mar1 = load_d1(d1, seed, cell, amb)
        ts = j1["t_star"]
        t = json.load(open(out / f"t1-{seed}-{cell}-{amb}.json"))
        ev = t["events"]
        row = {"t_star": ts, "cyl16p": j1["t_cyl16p"], "A_margin_mC": 1e3 * mar1["A"][ts],
               "C_full_D0_diag1": {"detect": j1["detect"]["C_full"], "margin_mC": 1e3 * mar1["C_full"][ts]}}
        sups = {"ref": sup1["C_full"]}
        for f in ("D0", "B1", "B2"):
            r2 = json.load(open(out / f"t2-{seed}-{cell}-{amb}-{f}.json"))
            z = np.load(out / f"t2-{seed}-{cell}-{amb}-{f}.npz")
            sups[f] = dict(zip(z["ks_C"].tolist(), z["sup_C"]))
            supB = dict(zip(z["ks_B"].tolist(), z["sup_B"]))
            row[f] = {"detect": r2["detect"], "margin_mC": r2["margin_at_t_star_mC"], "n": r2["n_directions"],
                      "table_entries": r2["table_entries"]}
            ks = sorted(set(sups[f]) & set(sup1["A"]))
            rep["checks"][f"t2 {seed} {f}: A <= B_F (worst excess mC)"] = float(
                1e3 * max(np.max(sup1["A"][k] - supB[k]) for k in ks))
            rep["checks"][f"t2 {seed} {f}: C_F <= C_full(D0) (worst excess mC)"] = float(
                1e3 * max(np.max(sups[f][k] - sup1["C_full"][k]) for k in ks))
        rep["checks"][f"t2 {seed} D_D0 reproduces cyl16p"] = bool(row["D0"]["detect"]["D"] == j1["t_cyl16p"])
        for f in rises:
            s = sups[f]
            rises[f] += sum(1e3 * ((s[k + 1][i] - sup1["A"][k + 1][i]) - (s[k][i] - sup1["A"][k][i]))
                            for k in ev for i in i3)
        if seed in HARD:
            ref_loss = 1e3 * (mar1["C_full"][ts] - mar1["A"][ts])
            for f in ("B1", "B2"):
                loss = row[f]["margin_mC"]["C"] - 1e3 * mar1["A"][ts]
                row[f]["margin_loss_vs_A_mC"] = loss
                loss_ok[f] += int(loss <= 0.5 * ref_loss)
                recov[f] += int(row[f]["detect"]["C"] == ts)
            row["ref_margin_loss_vs_A_mC"] = ref_loss
        rep["t2"][seed] = row
    rep["t2"]["event_rises_mC"] = rises
    for f in ("B1", "B2"):
        a = bool(rises[f] <= 0.5 * rises["ref"])
        b = bool(loss_ok[f] >= 3)
        rep["criteria"][f] = {"a_closes_cut_steps": a, "a_ratio": rises[f] / rises["ref"],
                              "b_closes_decision_loss": b, "b_runs": loss_ok[f], "c_recovers_decision_runs": recov[f],
                              "passes": a and b}
    return rep


# ---- main -------------------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("families", "run", "summary"))
    ap.add_argument("out", type=Path, nargs="?")
    ap.add_argument("--diag1", type=Path)
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()
    if a.cmd == "families":
        print(json.dumps(check_families(), indent=1))
        for f, D in FAMS.items():
            tp = V.Template(D, name=f, invariant=True)
            print(f, len(D), "directions,", tp.table_entries, "table entries")
        return
    if a.cmd == "summary":
        rep = summary(a.out, a.diag1)
        (a.out / "summary.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
        print(json.dumps(rep, indent=1, default=str))
        return
    a.out.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=G.ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=G.ROOT, text=True)
    meta = {"git_head": head, "git_dirty_tracked": bool(dirty), "diag1": str(a.diag1), "L": L, "cap": CAP,
            "families": check_families(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    assert meta["families"]["matches_hydrogen_list"], "families differ from Hydrogen's posted list"
    jobs1 = [(s, c, m, str(a.diag1), str(a.out)) for s, c, m in RUNS]
    jobs2 = [(s, c, m, f, str(a.diag1), str(a.out)) for f in ("B2", "B1", "D0") for s, c, m in RUNS]
    with ProcessPoolExecutor(a.workers) as pool:
        f1 = [pool.submit(t1, j) for j in jobs1]
        f2 = [pool.submit(t2, j) for j in jobs2]
        for f in f1 + f2:
            print(f.result(), flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
