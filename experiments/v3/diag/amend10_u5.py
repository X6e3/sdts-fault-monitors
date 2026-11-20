"""DIAG-3 amendment 10, fourth addendum, U5 (DIAG-3-PLAN.md): the forced-fallback coverage test.

On DEV rows, a measurement 10 C above the box is written into F3a's window at chosen samples, past the keep gate.
Every LP that holds it fails with kind slab until the next fold resets. Checked against the generator's true states:
every fold's base contains the true state at the new tau, and every alarm certificate's bounds contain the true a_s.
Nothing here is part of the candidate.
usage: python -B amend10_u5.py OUT [--workers N]
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import amend10 as A  # noqa: E402  (sets the paths, as R0 does)

C, CD, G, S, T, V = A.C, A.CD, A.G, A.S, A.T, A.V
W, K = A.W, A.K
TOL = 1e-9
SEEDS = (430000, 430001)
HEALTHY = [(s, "healthy", arm, al, nl) for s in SEEDS for arm in ("E0", "E1") for al in ("rw", "ramp")
           for nl in ("uniform", "edge")]
FAULT = [(s, cell, "E0", "rw", "uniform") for s in SEEDS for cell in ("drift_0.002", "stuck")]
FORCE_HEALTHY, FORCE_FAULT, BOGUS = (300, 1000, 2000), (250,), 10.0


def truth(run):
    """x_t = (Tc - Sc, Ts - Ss, TA) - shift, with the generator's own step; checked against its Ts and S"""
    P, TA = run["P"], run["TA"]
    tc, ts = T.equilibrium(T.P0, TA[0])
    sc, ss = T.equilibrium(T.P0, 0.0)
    x = []
    for k, (p, ta) in enumerate(zip(P, TA)):
        assert ts == run["Ts"][k] and ss == run["S"][k], k
        x.append((tc - sc - V.SHIFT, ts - ss - V.SHIFT, ta - V.SHIFT))
        tc, ts = T.step(tc, ts, p, ta)
        sc, ss = T.step(sc, ss, p, 0.0)
    return np.array(x)


def one(args):
    key, force = args
    seed, cell, arm, al, nl = key
    run = S.run(seed, next(c for c in T.CELLS if c.name == cell), arm, al, nl)
    zs, x, t_f = G.zs_of(run), truth(run), (run["t_f"] if cell != "healthy" else None)
    tp = V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    D = np.asarray(tp.D, dtype=float)
    chk = {"folds": 0, "fold_checks": 0, "max_fold_excess_C": -np.inf, "certs": 0, "cert_checks": 0,
           "max_cert_excess_C": -np.inf, "forced_at": [], "resets_at": [], "fold_fail": []}
    box, cap = {}, {}
    o_make, o_range, o_fold, o_lc = C.make, C.Failsafe.as_range, C.Failsafe.fold, C.Failsafe.lp_cert
    o_ca = C.Failsafe.certify_alarm

    def make(var, cy):
        box["w"] = o_make(var, cy)
        return box["w"]

    def as_range(self, t):
        if force and (t - 1) in force:                     # just before step t: z at key t - 1 is the bogus one
            self.zs[t - 1] = BOGUS
            self.last_active.pop(t - 1, None)
            chk["forced_at"].append(t - 1)
        return o_range(self, t)

    def fold(self, t):
        r0 = self.fs["fold_full_resets"]
        o_fold(self, t)
        chk["folds"] += 1
        if self.fs["fold_full_resets"] > r0:
            chk["resets_at"].append(t)
        if t_f is None or t < t_f:
            ex = float(np.max(D @ x[self.tau] - np.asarray(self.base, dtype=float)))
            chk["fold_checks"] += 1
            chk["max_fold_excess_C"] = max(chk["max_fold_excess_C"], ex)
            if ex > TOL:
                chk["fold_fail"].append([t, self.tau, ex])

    def lp_cert(self, *a):
        v, cub = o_lc(self, *a)
        if self.role and self.role[0] == "cert":
            cap[self.role[1]] = (v, cub)
        return v, cub

    def certify_alarm(self, t, z):
        cap.clear()
        c = o_ca(self, t, z)
        chk["certs"] += 1
        if t_f is None or t <= t_f:
            up, dn = cap["up"], cap["down"]
            cup = C.HI if isinstance(up[0], C.Failed) else min(up[1], C.HI)
            cdn = -C.LO if isinstance(dn[0], C.Failed) else min(dn[1], -C.LO)
            a_s = x[t][1]
            ex = max(a_s - cup, -a_s - cdn)
            chk["cert_checks"] += 1
            chk["max_cert_excess_C"] = max(chk["max_cert_excess_C"], float(ex))
        return c

    C.make, C.Failsafe.as_range, C.Failsafe.fold, C.Failsafe.lp_cert = make, as_range, fold, lp_cert
    C.Failsafe.certify_alarm = certify_alarm
    t0 = time.monotonic()
    try:
        rec = CD.online("F3a", zs, W, K, None, tp=tp)
    finally:
        C.make, C.Failsafe.as_range, C.Failsafe.fold, C.Failsafe.lp_cert = o_make, o_range, o_fold, o_lc
        C.Failsafe.certify_alarm = o_ca
    w = box["w"]
    for k in ("max_fold_excess_C", "max_cert_excess_C"):
        chk[k] = None if chk[k] == -np.inf else chk[k]
    return {"key": list(key), "forced": bool(force), "t_f": t_f, "check": chk, "audit": w.audit,
            "record": {k: rec[k] for k in ("detect", "alarm_certificate", "failsafe", "steps", "max_kept",
                                           "unproved_primal_alarms")},
            "seconds": round(time.monotonic() - t0, 1)}


def judge(rows):
    by = {(tuple(r["key"]), r["forced"]): r for r in rows}
    res, ok = {}, {}
    healthy = [by[(k, True)] for k in HEALTHY]
    fault = [by[(k, True)] for k in FAULT]
    ok["no_alarm_healthy"] = all(r["record"]["detect"] is None for r in healthy)
    ok["fault_alarms_certified"] = all(r["record"]["detect"] is not None and r["record"]["alarm_certificate"]["certified"]
                                       for r in fault)
    ok["fold_coverage"] = all(not r["check"]["fold_fail"] and r["check"]["fold_checks"] > 0 for r in healthy + fault)
    ok["cert_coverage"] = all(r["check"]["max_cert_excess_C"] is None or r["check"]["max_cert_excess_C"] <= TOL
                              for r in healthy + fault)

    def counters_ok(r, n):
        fs = r["record"]["failsafe"]
        return (r["check"]["forced_at"] == list(FORCE_HEALTHY if n == 3 else FORCE_FAULT)
                and fs["fold_full_resets"] == n and len(r["check"]["resets_at"]) == n
                and fs["fold_dir_fallbacks"].get("slab", 0) == 42 * n and fs["range_failures"].get("slab", 0) > 0)
    ok["forcing_counters"] = all(counters_ok(r, 3) for r in healthy) and all(counters_ok(r, 1) for r in fault)
    ok["recovery"] = all(r["record"]["detect"] is not None and r["record"]["detect"] > r["check"]["resets_at"][-1]
                         for r in fault)
    ok["audit"] = all(r["audit"]["violations"] == 0 and r["audit"]["n"] > 0 for r in healthy + fault)
    res["lag_vs_unforced"] = {"/".join(map(str, k)): [by[(k, False)]["record"]["detect"], by[(k, True)]["record"]["detect"]]
                              for k in FAULT}
    res["measurements_not_kept"] = {"/".join(map(str, r["key"])): r["record"]["failsafe"]["measurements_not_kept"]
                                    for r in healthy + fault}
    res["samples_force_to_reset"] = {"/".join(map(str, r["key"])): [b - a for a, b in zip(r["check"]["forced_at"],
                                                                                          r["check"]["resets_at"])]
                                     for r in healthy + fault}
    res["max_fold_excess_C"] = max(r["check"]["max_fold_excess_C"] for r in healthy + fault)
    res["max_cert_excess_C"] = max((r["check"]["max_cert_excess_C"] for r in healthy + fault
                                    if r["check"]["max_cert_excess_C"] is not None), default=None)
    res["min_audit_slack_C"] = min(r["audit"]["min_slack_C"] for r in healthy + fault)
    return {k: bool(v) for k, v in ok.items()}, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    jobs = ([(k, FORCE_HEALTHY) for k in HEALTHY] + [(k, FORCE_FAULT) for k in FAULT] + [(k, ()) for k in FAULT])
    rows = []
    with ProcessPoolExecutor(a.workers) as ex, open(a.out / "rows.jsonl", "w") as f:
        for r in ex.map(one, jobs):
            rows.append(r)
            f.write(json.dumps(r, default=str) + "\n")
            f.flush()
            print(r["key"], r["forced"], r["record"]["detect"], r["check"]["max_fold_excess_C"], r["seconds"], flush=True)
    ok, res = judge(rows)
    rep = {"ok": ok, "U5": all(ok.values()), "details": res,
           "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip(),
           "git_dirty_tracked": bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=HERE).returncode)}
    (a.out / "u5.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
