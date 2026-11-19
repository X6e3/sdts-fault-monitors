"""DIAG-3 amendment 4 (DIAG-3-PLAN.md): the compressed windows E and N on every DEV evaluation row, online from k = 0.

The window code is diag3_cw's (Compressed, certified folds); the rows and the scoring are diag3_dev's.

usage:
  python -B diag3_cw_dev.py run OUT_DIR [--workers 8] [--variants E N] [--W 256]
  python -B diag3_cw_dev.py summary OUT_DIR [--ref 2A_OUT_DIR]                  # amendment 4 (E and N, W = 256)
  python -B diag3_cw_dev.py score OUT.json --src LABEL=DIR:VAR ... [--pair A,B ...]
      VAR is a cw variant (E, N, L) in a cw run directory, or S128, S256 or cyl16p in the 2a directory.
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


def online(var, zs, W=W, K=None, t_star=None, horizon=None, tp=None):
    """one run of a compressed window, online from k = 0: the alarm at t uses the measurements up to t - 1; z_t is
    kept only if it is not redundant at arrival, then evicted down to K, then the fold. Returns the record."""
    w = C.make(var, tp if tp is not None else V.load_frozen(G.V3 / "frozen" / "cyl16p.json"))
    last = len(zs) - 1 if horizon is None else min(len(zs) - 1, horizon)
    det, cert, m_det, m_ts, steps, folds, t00 = None, None, None, None, [], [], time.monotonic()
    unproved = 0                                      # F: LP values pointing to an alarm that the bound cannot prove
    w.zs[0] = zs[0]
    for t in range(1, last + 1):
        t0 = time.monotonic()
        w.now = t
        lower, upper = w.as_range(t)                  # measurements up to t - 1 only
        if lower is None:                             # cannot happen with sound folds; recorded, never hidden
            det, cert = t, {"certified": False, "reason": "window LP infeasible before the measurement"}
            break
        m = G.margin(lower, upper, zs[t])
        if t == t_star:
            m_ts = 1e3 * m
        d = getattr(w, "delta", DELTA)                # F: delta + eta (amendment 9); E, N, L: delta
        if upper < zs[t] - d or lower > zs[t] + d:
            c = w.certify_alarm(t, zs[t])
            if c["certified"] or not getattr(w, "harden", False):   # E, N, L (amendments 3-5): as they ran
                det, m_det, cert = t, 1e3 * m, c
                break
            unproved += 1                             # F raises only certified alarms; z_t is dropped (sound)
        elif not (lower >= zs[t] - d and upper <= zs[t] + d):
            if getattr(w, "track", False):
                w.keep(t, zs[t])
            else:
                w.zs[t] = zs[t]
            if K is not None and sum(1 for j in w.zs if j > w.tau) > K:
                w.evict()
        w.max_kept = max(w.max_kept, len(w.zs))
        folded = t - w.tau > W + B
        if folded:
            try:
                w.fold(t)                             # after the alarm check, with z_t
            except RuntimeError as e:                 # cannot happen with sound folds; recorded, never hidden
                det, cert = t, {"certified": False, "reason": str(e)}
                break
        (folds if folded else steps).append(time.monotonic() - t0)
    ms = 1e3 * np.array(steps) if steps else np.zeros(1)
    fs = 1e3 * np.array(folds) if folds else np.zeros(1)
    return {"variant": var, "W": W, "K": K, "evictions": getattr(w, "n_evict", 0), "unproved_primal_alarms": unproved,
            "detect": det,
            "margin_at_detect_mC": m_det, "margin_at_t_star_mC": m_ts,
            "alarm_certificate": cert, "folds_raised_to_dual_bound": w.n_short, "largest_raise_C": w.max_short,
            "max_kept": w.max_kept, "max_nodes": w.max_nodes, "max_vars": w.max_vars, "max_rows": w.max_rows,
            "n_lp": w.n_lp, "n_retry": w.n_retry, "n_resolve": w.n_resolve, "max_ta_rows": w.max_ta_rows,
            "steps": len(steps) + len(folds),
            "step_ms": {"median": float(np.median(ms)), "p95": float(np.percentile(ms, 95)), "max": float(ms.max())},
            "fold_step_ms": {"median": float(np.median(fs)), "max": float(fs.max())},
            "seconds": round(time.monotonic() - t00, 1)}


def job(args):
    r, var, out, horizon, W, *rest = args
    K = rest[0] if rest else None                     # the cap on kept measurements (None: no cap)
    path = Path(out) / f"cwdev-{D.key(r)}-{var}.json"
    if path.exists():
        return D.key(r), var, "done before"
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    ts = r["oracle"].get("t_star")
    res = {"key": D.key(r), **online(var, G.zs_of(run), W, K, ts, horizon)}
    if horizon is None:
        path.write_text(json.dumps(res) + "\n")
    return D.key(r), var, res["detect"], ts, res["seconds"]


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


def score(srcs, pairs):
    """scores and row-by-row comparisons of any cw runs and 2a arms, over every DEV row"""
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    det, extra = {}, {}
    for spec in srcs:
        label, rest = spec.split("=", 1)
        d, var = rest.rsplit(":", 1)
        d, vals, ext = Path(d), {}, {}
        for r in rows:
            k = D.key(r)
            if var in ("S128", "S256", "cyl16p"):
                x = json.loads((d / f"dev-{k}.json").read_text())
                vals[k] = x["cyl16p"] if var == "cyl16p" else x[var]["detect"]
            else:
                x = json.loads((d / f"cwdev-{k}-{var}.json").read_text())
                vals[k], ext[k] = x["detect"], x
        det[label], extra[label] = vals, ext
    getters = {"v2": lambda r: r["v2"]}
    for label in det:
        getters[label] = (lambda lb: lambda r: det[lb][D.key(r)])(label)
    rep = {"rows": len(rows), "sources": srcs, "score": _score(rows, getters), "pairs": {}, "cost": {}}
    for pr in pairs:
        x, y = pr.split(",")
        diff = [[D.key(r), det[x][D.key(r)], det[y][D.key(r)]] for r in rows if det[x][D.key(r)] != det[y][D.key(r)]]
        rep["pairs"][pr] = {"rows_differ": len(diff), "differ": diff}
    for label, ext in extra.items():
        if not ext:
            continue
        xs = list(ext.values())
        kept = np.array([x["max_kept"] for x in xs])
        unc = [k for k, x in ext.items() if x["detect"] is not None and not x["alarm_certificate"]["certified"]]
        rep["cost"][label] = {
            "W": xs[0].get("W"), "K": xs[0].get("K"), "evictions": int(sum(x.get("evictions", 0) for x in xs)),
            "rows_with_evictions": int(sum(1 for x in xs if x.get("evictions", 0))), "uncertified_alarms": unc,
            "max_kept": {"median": float(np.median(kept)), "p95": float(np.percentile(kept, 95)), "max": int(kept.max())},
            "max_nodes": int(max(x["max_nodes"] for x in xs)), "max_vars": int(max(x["max_vars"] for x in xs)),
            "max_rows": int(max(x["max_rows"] for x in xs)),
            "max_ta_rows": int(max(x.get("max_ta_rows", 0) for x in xs)),
            "resolves_per_lp": float(sum(x.get("n_resolve", 0) for x in xs) / max(1, sum(x["n_lp"] for x in xs))),
            "step_ms_median_of_medians": float(np.median([x["step_ms"]["median"] for x in xs])),
            "step_ms_p95_max": float(max(x["step_ms"]["p95"] for x in xs)),
            "fold_step_ms_max": float(max(x["fold_step_ms"]["max"] for x in xs)),
            "cpu_seconds": float(sum(x["seconds"] for x in xs)),
            "folds_raised": int(sum(x["folds_raised_to_dual_bound"] for x in xs)),
            "n_retry": int(sum(x["n_retry"] for x in xs))}
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("run", "summary", "smoke", "score"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--ref", type=Path)
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS))
    ap.add_argument("--W", type=int, default=W)
    ap.add_argument("--K", type=int)
    ap.add_argument("--src", action="append", default=[])
    ap.add_argument("--pair", action="append", default=[])
    a = ap.parse_args()
    if a.cmd == "score":
        rep = score(a.src, a.pair)
        a.out.write_text(json.dumps(rep, indent=1, default=str) + "\n")
        print(json.dumps({k: rep[k] for k in ("sources", "pairs")}, indent=1, default=str))
        return
    if a.cmd == "summary":
        rep = summary(a.out, a.ref)
        (a.out / "summary.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
        print(json.dumps({k: rep[k] for k in ("rows", "done_E_and_N", "ref_rows", "uncertified_alarms")}, indent=1))
        return
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "smoke":                              # a seed outside the evaluation rows, 300 steps, nothing written
        r = {"seed": 430050, "cell": "drift_0.002", "arm": "E1", "ambient": "ramp", "noise": "uniform",
             "oracle": {"t_star": None}}
        for v in a.variants:
            print(job((r, v, str(a.out), 300, a.W, a.K)))
        return
    import scipy
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=G.ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=G.ROOT, text=True)
    meta = {"git_head": head, "git_dirty_tracked": bool(dirty), "W": a.W, "K": a.K, "B": B, "pad": C.PAD,
            "variants": a.variants,
            "machine": platform.machine(), "platform": platform.platform(), "python": platform.python_version(),
            "numpy": np.__version__, "scipy": scipy.__version__, "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    rows.sort(key=lambda r: r["oracle"].get("t_star") is None)          # the rows that stop early first
    jobs = [(r, v, str(a.out), None, a.W, a.K) for r in rows for v in a.variants]
    with ProcessPoolExecutor(a.workers) as pool:
        for x in pool.map(job, jobs):
            print(x, flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
