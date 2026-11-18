"""DIAG-3 amendment 4 (DIAG-3-PLAN.md): the compressed windows E and N on every DEV evaluation row, online from k = 0.

The window code is diag3_cw's (Compressed, certified folds); the rows and the scoring are diag3_dev's.

usage:
  python -B diag3_cw_dev.py run OUT_DIR [--workers 8]
  python -B diag3_cw_dev.py summary OUT_DIR [--ref 2A_OUT_DIR]
"""
import argparse
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import diag3_cw as C  # noqa: E402
import diag3_dev as D  # noqa: E402

G, S, T, V, SV = C.G, C.S, C.T, C.V, D.SV
DELTA, W, B = C.DELTA, C.W, C.B
VARIANTS = ("E", "N")


def job(args):
    r, var, out, horizon = args
    path = Path(out) / f"cwdev-{D.key(r)}-{var}.json"
    if path.exists():
        return D.key(r), var, "done before"
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    zs = G.zs_of(run)
    w = C.make(var, V.load_frozen(G.V3 / "frozen" / "cyl16p.json"))
    ts = r["oracle"].get("t_star")
    last = len(zs) - 1 if horizon is None else min(len(zs) - 1, horizon)
    det, cert, m_det, m_ts, steps, folds, t00 = None, None, None, None, [], [], time.monotonic()
    w.zs[0] = zs[0]
    for t in range(1, last + 1):
        t0 = time.monotonic()
        lower, upper = w.as_range(t)                  # measurements up to t - 1 only
        if lower is None:
            raise RuntimeError(f"{D.key(r)} {var}: window LP infeasible before measurement {t}")
        m = G.margin(lower, upper, zs[t])
        if t == ts:
            m_ts = 1e3 * m
        if upper < zs[t] - DELTA or lower > zs[t] + DELTA:
            det, m_det, cert = t, 1e3 * m, w.certify_alarm(t, zs[t])
            break
        if not (lower >= zs[t] - DELTA and upper <= zs[t] + DELTA):
            w.zs[t] = zs[t]
        w.max_kept = max(w.max_kept, len(w.zs))
        folded = t - w.tau > W + B
        if folded:
            w.fold(t)                                 # after the alarm check, with z_t
        (folds if folded else steps).append(time.monotonic() - t0)
    ms = 1e3 * np.array(steps) if steps else np.zeros(1)
    fs = 1e3 * np.array(folds) if folds else np.zeros(1)
    res = {"key": D.key(r), "variant": var, "detect": det, "margin_at_detect_mC": m_det, "margin_at_t_star_mC": m_ts,
           "alarm_certificate": cert, "folds_raised_to_dual_bound": w.n_short, "largest_raise_C": w.max_short,
           "max_kept": w.max_kept, "max_nodes": w.max_nodes, "max_vars": w.max_vars, "max_rows": w.max_rows,
           "n_lp": w.n_lp, "n_retry": w.n_retry, "steps": len(steps) + len(folds),
           "step_ms": {"median": float(np.median(ms)), "p95": float(np.percentile(ms, 95)), "max": float(ms.max())},
           "fold_step_ms": {"median": float(np.median(fs)), "max": float(fs.max())},
           "seconds": round(time.monotonic() - t00, 1)}
    if horizon is None:
        path.write_text(json.dumps(res) + "\n")
    return D.key(r), var, det, ts, res["seconds"]


def _score(rows, getters):
    rep = {}
    for label, subset in (("all", rows), ("without_diag_runs",
                          [r for r in rows if (r["seed"], r["cell"], r["ambient"]) not in D.DIAG_RUNS])):
        F, U, R, A = SV._sets(subset)
        sec = {"runs": len(subset), "R": len(R), "admissible": len(A), "undetermined": len(U)}
        for name, get in getters.items():
            d, lc, lv2, nb = SV.paired_delta(R, get)
            sec[name] = {"D_paired": d, "lag": lc, "lag_v2": lv2, "n_v2_detects": nb,
                         "soundness_findings": len(SV._soundness(subset, R, A, get)), **SV.describe(R, get),
                         "later_than_v2": sum(1 for r in R if r["v2"] is not None and
                                              (get(r) is None or get(r) > r["v2"]))}
            if name != "v2":
                sec[name]["bootstrap95"] = SV.bootstrap(R, get)
        sec["by_cell"] = SV.by_cell(R, getters)
        rep[label] = sec
    return rep


def summary(out, ref):
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    got = {v: {} for v in VARIANTS}
    for r in rows:
        for v in VARIANTS:
            p = out / f"cwdev-{D.key(r)}-{v}.json"
            if p.exists():
                got[v][D.key(r)] = json.loads(p.read_text())
    s256 = {}
    if ref is not None:
        for r in rows:
            p = ref / f"dev-{D.key(r)}.json"
            if p.exists():
                s256[D.key(r)] = json.loads(p.read_text())
    done = [r for r in rows if all(D.key(r) in got[v] for v in VARIANTS)]
    rep = {"rows": len(rows), "done_E_and_N": len(done), "ref_rows": len(s256)}
    getters = {"v2": lambda r: r["v2"], "E": lambda r: got["E"][D.key(r)]["detect"],
               "N": lambda r: got["N"][D.key(r)]["detect"]}
    both = [r for r in done if D.key(r) in s256]
    if len(both) == len(rows):
        getters["S256_2a"] = lambda r: s256[D.key(r)]["S256"]["detect"]
        getters["cyl16p_2a"] = lambda r: s256[D.key(r)]["cyl16p"]
    rep["score"] = _score(done if "S256_2a" not in getters else both, getters)
    rep["E_vs_S256_2a"] = {"rows_compared": len(both),
                           "differ": [[D.key(r), s256[D.key(r)]["S256"]["detect"], got["E"][D.key(r)]["detect"],
                                       s256[D.key(r)]["S256"]["margin_at_detect_mC"],
                                       got["E"][D.key(r)]["margin_at_detect_mC"]]
                                      for r in both if s256[D.key(r)]["S256"]["detect"] != got["E"][D.key(r)]["detect"]]}

    def later(a, b):                                  # a later than b (a miss is later than any detection)
        return (a is None and b is not None) or (a is not None and b is not None and a > b)

    nv = {"N_later_than_E": [], "N_earlier_than_E": []}
    by = {}
    for r in done:
        e, n = got["E"][D.key(r)]["detect"], got["N"][D.key(r)]["detect"]
        k = f"{r['cell']}|{r['ambient']}"
        by.setdefault(k, {"rows": 0, "N_later": 0, "N_earlier": 0})["rows"] += 1
        if later(n, e):
            nv["N_later_than_E"].append([D.key(r), e, n])
            by[k]["N_later"] += 1
        elif later(e, n):
            nv["N_earlier_than_E"].append([D.key(r), e, n])
            by[k]["N_earlier"] += 1
    nv["by_cell_ambient"] = by
    rep["N_vs_E"] = nv
    uncert = [[D.key(r), v] for r in done for v in VARIANTS if got[v][D.key(r)]["detect"] is not None
              and not got[v][D.key(r)]["alarm_certificate"]["certified"]]
    rep["uncertified_alarms"] = uncert
    for v in VARIANTS:
        xs = [got[v][D.key(r)] for r in done]
        kept = np.array([x["max_kept"] for x in xs]) if xs else np.zeros(1)
        rep[f"cost_{v}"] = {
            "max_kept": {"median": float(np.median(kept)), "p95": float(np.percentile(kept, 95)), "max": int(kept.max())},
            "max_nodes": int(max((x["max_nodes"] for x in xs), default=0)),
            "max_vars": int(max((x["max_vars"] for x in xs), default=0)),
            "max_rows": int(max((x["max_rows"] for x in xs), default=0)),
            "step_ms_p95_max": float(max((x["step_ms"]["p95"] for x in xs), default=0)),
            "fold_step_ms_max": float(max((x["fold_step_ms"]["max"] for x in xs), default=0)),
            "folds_raised": int(sum(x["folds_raised_to_dual_bound"] for x in xs)),
            "largest_raise_C": float(max((x["largest_raise_C"] for x in xs), default=0)),
            "n_retry": int(sum(x["n_retry"] for x in xs))}
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("run", "summary", "smoke"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--ref", type=Path)
    a = ap.parse_args()
    if a.cmd == "summary":
        rep = summary(a.out, a.ref)
        (a.out / "summary.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
        print(json.dumps({k: rep[k] for k in ("rows", "done_E_and_N", "ref_rows", "uncertified_alarms")}, indent=1))
        return
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "smoke":                              # a seed outside the evaluation rows, 300 steps, nothing written
        r = {"seed": 430050, "cell": "drift_0.002", "arm": "E1", "ambient": "ramp", "noise": "uniform",
             "oracle": {"t_star": None}}
        for v in VARIANTS:
            print(job((r, v, str(a.out), 300)))
        return
    import scipy
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=G.ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=G.ROOT, text=True)
    meta = {"git_head": head, "git_dirty_tracked": bool(dirty), "W": W, "B": B, "pad": C.PAD,
            "machine": platform.machine(), "platform": platform.platform(), "python": platform.python_version(),
            "numpy": np.__version__, "scipy": scipy.__version__, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    rows.sort(key=lambda r: r["oracle"].get("t_star") is None)          # the rows that stop early first
    jobs = [(r, v, str(a.out), None) for r in rows for v in VARIANTS]
    with ProcessPoolExecutor(a.workers) as pool:
        for x in pool.map(job, jobs):
            print(x, flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
