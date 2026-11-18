"""DIAG-3 phase 2a (DIAG-3-PLAN.md, amendment 1): S128 and S256 on every DEV evaluation row, online from k = 0.

usage:
  python -B diag3_dev.py run OUT_DIR [--workers 14]
  python -B diag3_dev.py summary OUT_DIR
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import diag1 as G  # noqa: E402
import diag3 as W3  # noqa: E402
import score_validation as SV  # noqa: E402

V, S, T = G.V, G.S, G.T
ROWS = G.ROOT / "results/v3/dev-45cff1d/rows.jsonl"
DIAG_RUNS = {(430007, "drift_0.002", "rw"), (430027, "drift_0.002", "rw"), (430000, "drift_0.001", "ramp"),
             (430010, "drift_0.0005", "ramp"), (430019, "drift_0.001", "ramp")}


def key(r):
    return f"{r['seed']}-{r['cell']}-{r['arm']}-{r['ambient']}-{r['noise']}"


def job(args):
    r, out = args
    path = Path(out) / f"dev-{key(r)}.json"
    if path.exists():
        return key(r), "done before"
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    zs = G.zs_of(run)
    cy = V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    res = {"key": key(r), "cyl16p": V.first_inconsistent(cy, run["y"], run["P"])}
    for W in (128, 256):
        w = W3.Window(cy, W, smooth=True)
        w.zs[0] = zs[0]
        det, m_det, m_tstar, t0 = None, None, None, time.monotonic()
        ts = r["oracle"].get("t_star")
        for t in range(1, len(zs)):
            lower, upper = w.as_range(t)
            if lower is None:
                raise RuntimeError(f"{key(r)} S{W}: window LP infeasible before measurement {t}")
            m = G.margin(lower, upper, zs[t])
            if t == ts:
                m_tstar = 1e3 * m
            if upper < zs[t] - G.DELTA or lower > zs[t] + G.DELTA:
                det, m_det = t, 1e3 * m
                break
            w.zs[t] = zs[t]
            if t - w.tau > W + W3.B:
                w.fold(t)
        res[f"S{W}"] = {"detect": det, "margin_at_detect_mC": m_det, "margin_at_t_star_mC": m_tstar,
                        "n_lp": w.n_lp, "n_retry": w.n_retry, "seconds": round(time.monotonic() - t0, 1)}
    path.write_text(json.dumps(res) + "\n")
    return key(r), res["cyl16p"], res["S128"]["detect"], res["S256"]["detect"], r["oracle"].get("t_star")


def summary(out):
    rows = [json.loads(l) for l in ROWS.read_text().splitlines() if l.strip()]
    got = {}
    for r in rows:
        p = out / f"dev-{key(r)}.json"
        if p.exists():
            got[key(r)] = json.loads(p.read_text())
    rep = {"rows": len(rows), "done": len(got)}
    rows = [r for r in rows if key(r) in got]
    getters = {"v2": lambda r: r["v2"], "cyl16p": lambda r: got[key(r)]["cyl16p"],
               "S128": lambda r: got[key(r)]["S128"]["detect"], "S256": lambda r: got[key(r)]["S256"]["detect"]}
    for label, subset in (("all", rows), ("without_diag_runs",
                          [r for r in rows if (r["seed"], r["cell"], r["ambient"]) not in DIAG_RUNS])):
        F, U, R, A = SV._sets(subset)
        sec = {"runs": len(subset), "R": len(R), "admissible": len(A), "undetermined": len(U)}
        for name, get in getters.items():
            d, lc, lv2, nb = SV.paired_delta(R, get)
            sec[name] = {"D_paired": d, "lag": lc, "lag_v2": lv2, "n_v2_detects": nb,
                         "soundness_findings": len(SV._soundness(subset, R, A, get)), **SV.describe(R, get),
                         "later_than_v2": sum(1 for r in R if r["v2"] is not None and
                                              (get(r) is None or get(r) > r["v2"]))}
            if name in ("cyl16p", "S128", "S256"):
                sec[name]["bootstrap95"] = SV.bootstrap(R, get)
        sec["by_cell"] = SV.by_cell(R, getters)
        rep[label] = sec
    rep["cyl16p_recomputed_matches_frozen_rows"] = None
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("run", "summary"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    if a.cmd == "summary":
        rep = summary(a.out)
        (a.out / "summary.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
        print(json.dumps(rep, indent=1, default=str))
        return
    a.out.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=G.ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=G.ROOT, text=True)
    meta = {"git_head": head, "git_dirty_tracked": bool(dirty), "B": W3.B, "pad": W3.PAD,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    rows = [json.loads(l) for l in ROWS.read_text().splitlines() if l.strip()]
    rows.sort(key=lambda r: r["oracle"].get("t_star") is not None)        # the full-length runs first
    with ProcessPoolExecutor(a.workers) as pool:
        for x in pool.map(job, [(r, str(a.out)) for r in rows]):
            print(x, flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
