"""Diagnosis after the freeze-2 verdict (decided by Can Koç on 2026-11-19, after the verdict was recorded).

It replays validation run (440243, healthy, E0, ramp, edge) with the frozen F up to the fold at t = 945, and looks
at that fold's LPs. It cannot change the verdict (RECORD-2026-11-19-validation.md). It uses the frozen files
unchanged; they are checked against frozen/MANIFEST-V2.json first. Nothing is scored.

Questions, fixed before the run:
  Q1  Does the replay reproduce the validation row? The fields compared are detect, the certificate's reason,
      evictions, n_lp, n_retry, folds raised, the largest raise, max_kept, max_nodes, max_rows, max_vars and steps.
  Q2  Does the fold at t = 945 fail again? If so, at which of the 42 directions, and with which status and message in
      each of the three attempts?
  Q3  The fold's other directions: does each one solve, and at which attempt? The window is unchanged when a fold
      raises, so every direction is rebuilt from the same state. The window's counters are restored afterwards.
  Q4  Is the failure repeatable? The failing LP is solved 5 more times with the frozen three attempts in this
      process, and once in a fresh process from the saved LP.
  Q5  (informational) The same LP with HiGHS's other settings (highs with presolve, highs-ipm with presolve). Also,
      the failing direction's a priori support (the exact clamps with the boxes), next to its previous base value
      and the values of the directions that solved.
Also logged: every LP attempt of the replay that ended neither optimal nor infeasible (sample, purpose, method,
status).
usage: python -B diag_fold_440243.py run OUT
       python -B diag_fold_440243.py resolve LP.npz      (Q4 and Q5 in a fresh process; prints JSON)
"""
import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import scipy
import scipy.sparse as sp
from scipy.optimize import linprog

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for sub in ("experiments/v3", "experiments/v3/diag", "experiments/oracle", "experiments/machine",
            "experiments/generators", "env"):
    sys.path.insert(0, str(ROOT / sub))

SEED, CELL, ARM, AMB, NOISE, T_FOLD = 440243, "healthy", "E0", "ramp", "edge", 945
ROW = ROOT / "results" / "v3" / "freeze2" / "validation-440200-440399-35b344df" / "rows.jsonl"
FROZEN_ATTEMPTS = (("highs-ds", {"presolve": False}), ("highs-ipm", {"presolve": False}), ("highs-ds", {}))
OTHER_SETTINGS = (("highs", {}), ("highs-ipm", {}))
COMPARED = ("detect", "alarm_certificate", "evictions", "unproved_primal_alarms", "max_kept", "max_nodes", "max_vars",
            "max_rows", "n_lp", "n_retry", "folds_raised_to_dual_bound", "largest_raise_C", "steps")


def _attempts(lp, settings, repeat=1):
    out = []
    for _ in range(repeat):
        for method, opts in settings:
            res = linprog(lp["c"], A_ub=lp["A_ub"], b_ub=lp["b_ub"], A_eq=lp["A_eq"], b_eq=lp["b_eq"],
                          bounds=lp["bounds"], method=method, options=opts)
            out.append({"method": method, "presolve": opts.get("presolve", True), "status": int(res.status),
                        "message": res.message, "value": None if res.status != 0 else float(-res.fun)})
    return out


def save_lp(path, c, kw):
    arrs = {"c": np.asarray(c, float), "bounds": np.asarray(kw["bounds"], float)}
    for name in ("A_ub", "A_eq"):
        A = kw.get(name)
        if A is not None:
            co = A.tocoo()
            arrs[name + "_data"], arrs[name + "_row"], arrs[name + "_col"] = co.data, co.row, co.col
            arrs[name + "_shape"] = np.array(co.shape)
            arrs["b" + name[1:]] = np.asarray(kw["b" + name[1:]], float)
    np.savez(path, **arrs)


def load_lp(path):
    z = np.load(path)
    lp = {"c": z["c"], "bounds": z["bounds"], "A_ub": None, "b_ub": None, "A_eq": None, "b_eq": None}
    for name in ("A_ub", "A_eq"):
        if name + "_data" in z:
            lp[name] = sp.csr_matrix((z[name + "_data"], (z[name + "_row"], z[name + "_col"])),
                                     shape=tuple(z[name + "_shape"]))
            lp["b" + name[1:]] = z["b" + name[1:]]
    return lp


def resolve(path):
    lp = load_lp(path)
    print(json.dumps({"frozen_attempts": _attempts(lp, FROZEN_ATTEMPTS), "other_settings": _attempts(lp, OTHER_SETTINGS)}))


def run(out):
    import dev_scenarios as S
    import template_state as V
    import thermal_v2_env
    import run_validation as RV1
    import diag1 as G
    import diag3_cw as C
    import diag3_cw_dev as CD

    T = V.T
    manifest = ROOT / "experiments" / "v3" / "frozen" / "MANIFEST-V2.json"
    m = json.loads(manifest.read_text())
    bad = [p for p, h in m["files"].items() if RV1.sha256(ROOT / p) != h]
    if bad:
        raise SystemExit(f"frozen manifest mismatch: {bad}")
    msha = RV1.sha256(manifest)
    try:
        env, env_ok = thermal_v2_env.check(), True
    except RuntimeError as e:
        env, env_ok = str(e), False
    out.mkdir(parents=True, exist_ok=False)
    meta = {"git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
            "git_dirty_tracked": bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ROOT).returncode),
            "manifest_sha256": msha, "env_lock_ok": env_ok, "env": env, "scipy": scipy.__version__,
            "platform": platform.platform(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    c = m["candidate"]
    tp = V.load_frozen(ROOT / c["directions_file"], c["directions_sha256"])
    S.unlock_validation(msha)
    r = S.run(SEED, next(x for x in T.CELLS if x.name == CELL), ARM, AMB, NOISE)
    zs = G.zs_of(r)

    ctx = {"w": None, "purpose": None, "dir": None, "diag": False, "rebuild": False}
    log, fold_attempts, rebuild, lps = [], [], [], {}
    orig_make, orig_rec, orig_lp, orig_fold = C.make, C.rec_linprog, C.Compressed.lp, C.Stats.fold

    def make(var, cy):
        ctx["w"] = orig_make(var, cy)
        return ctx["w"]

    def lp(self, t_end, meas_upto, obj_state, obj_vec):
        if obj_state != t_end:                                     # a fold support at tau + B
            i = int(np.flatnonzero((self.D == np.asarray(obj_vec, float)).all(axis=1))[0])
            ctx["purpose"], ctx["dir"] = ("rebuild" if ctx["rebuild"] else "fold") + f"-dir{i}", i
        else:
            ctx["purpose"], ctx["dir"] = f"range-{'up' if obj_vec[1] > 0 else 'down'}", None
        return orig_lp(self, t_end, meas_upto, obj_state, obj_vec)

    def rec(cv, **kw):
        res = orig_rec(cv, **kw)
        a = {"t": getattr(ctx["w"], "now", None), "purpose": ctx["purpose"], "method": kw.get("method"),
             "presolve": (kw.get("options") or {}).get("presolve", True), "status": int(res.status),
             "message": res.message}
        if res.status not in (0, 2):
            log.append(a)
        if ctx["diag"] or ctx["rebuild"]:
            (rebuild if ctx["rebuild"] else fold_attempts).append({**a, "dir": ctx["dir"]})
            if res.status not in (0, 2):
                lps[ctx["dir"]] = (cv, {k: v for k, v in kw.items() if k not in ("method", "options")})
        return res

    state = {}

    def fold(self, t):
        if t != T_FOLD:
            return orig_fold(self, t)
        state.update(tau=self.tau, kept=sorted(int(j) for j in self.zs), base=[float(x) for x in self.base])
        ctx["diag"] = True
        try:
            orig_fold(self, t)
            state["fold"] = "completed"
        except RuntimeError as e:
            state["fold"] = str(e)
            ctx["diag"] = False
            keep = (self.n_lp, self.n_retry, self.lp_seconds, self.max_vars, self.max_rows, self.max_nodes,
                    dict(self.last_active))
            ctx["rebuild"], vals = True, []
            for i, d in enumerate(self.D):
                try:
                    v, cub = self.lp_cert(t, t, self.tau + C.B, d)
                    vals.append({"dir": i, "value": v, "certified_bound": cub})
                except RuntimeError as e2:
                    vals.append({"dir": i, "error": str(e2)})
            ctx["rebuild"] = False
            (self.n_lp, self.n_retry, self.lp_seconds, self.max_vars, self.max_rows, self.max_nodes,
             self.last_active) = keep
            state["rebuild_values"] = vals
            raise e
        finally:
            ctx["diag"] = False

    C.make, C.rec_linprog, C.Compressed.lp, C.Stats.fold = make, rec, lp, fold
    t0 = time.monotonic()
    rec_f = CD.online(c["variant"], zs, c["W"], c["K"], None, horizon=T_FOLD, tp=tp)
    C.make, C.rec_linprog, C.Compressed.lp, C.Stats.fold = orig_make, orig_rec, orig_lp, orig_fold

    row = next(x for x in map(json.loads, ROW.read_text().splitlines())
               if (x["seed"], x["cell"], x["arm"], x["ambient"], x["noise"]) == (SEED, CELL, ARM, AMB, NOISE))
    q1 = {k: {"replay": rec_f.get(k), "validation": row["F"].get(k), "equal": rec_f.get(k) == row["F"].get(k)}
          for k in COMPARED}

    apriori = tp.clamp(np.full(len(tp.D), np.inf))
    failing = sorted(lps)
    q4 = {}
    for i in failing:
        p = out / f"lp-dir{i}.npz"
        save_lp(p, *lps[i])
        lpd = load_lp(p)
        fresh = subprocess.run([sys.executable, "-B", str(HERE), "resolve", str(p)], capture_output=True, text=True)
        q4[i] = {"direction": [float(x) for x in tp.D[i]], "rows_eq": None if lpd["A_eq"] is None else lpd["A_eq"].shape[0],
                 "rows_ub": None if lpd["A_ub"] is None else lpd["A_ub"].shape[0], "vars": len(lpd["c"]),
                 "repeat_in_process": _attempts(lpd, FROZEN_ATTEMPTS, repeat=5),
                 "fresh_process": json.loads(fresh.stdout) if fresh.returncode == 0 else fresh.stderr[-2000:],
                 "apriori_support": float(apriori[i]), "previous_base": state.get("base", [None] * len(tp.D))[i]}
    res = {"meta": {**meta, "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "seconds": round(time.monotonic() - t0, 1)},
           "key": [SEED, CELL, ARM, AMB, NOISE], "t_f": r["t_f"], "q1_reproduces": all(v["equal"] for v in q1.values()),
           "q1": q1, "fold_state": {k: v for k, v in state.items() if k != "rebuild_values"},
           "q2_fold_attempts": fold_attempts, "q3_rebuild_values": state.get("rebuild_values"),
           "q3_rebuild_attempts": rebuild, "failing_directions": failing, "q4_q5": q4,
           "apriori_support": [float(x) for x in apriori], "unusual_attempts_in_replay": log, "replay_record": rec_f}
    (out / "diag.json").write_text(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps({"q1_reproduces": res["q1_reproduces"], "fold": state.get("fold"), "failing": failing,
                      "unusual_attempts": len(log)}, default=str))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("run", "resolve"))
    ap.add_argument("path", type=Path)
    a = ap.parse_args()
    run(a.path) if a.cmd == "run" else resolve(a.path)


if __name__ == "__main__":
    main()
