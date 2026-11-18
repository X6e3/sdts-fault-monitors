"""DIAG-3 amendment 2: the phase-2a rows of a fixed subset, run on a second machine, compared with the first.

The computation is diag3_dev.job, unchanged. Only the rows and the output directory differ.

usage:
  python -B diag3_platform.py run OUT_DIR [--workers 8]
  python -B diag3_platform.py compare OUT_DIR REF_DIR      # writes OUT_DIR/compare.json
"""
import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import diag3_dev as D  # noqa: E402

STEP = 5                      # the subset: (seed - 430000) % STEP == 0, every cell, arm and ambient
TOL_MC = 1e-3                 # a margin difference above this (= the 1e-6 degC fold pad) is a finding


def subset():
    rows = [json.loads(l) for l in D.ROWS.read_text().splitlines() if l.strip()]
    return [r for r in rows if (r["seed"] - 430000) % STEP == 0]


def env():
    import numpy
    import scipy
    try:
        cpu = subprocess.check_output(["sysctl", "-n", "machdep.cpu.brand_string"], text=True).strip()
    except Exception:
        cpu = platform.processor()
    return {"machine": platform.machine(), "platform": platform.platform(), "cpu": cpu,
            "python": platform.python_version(), "numpy": numpy.__version__, "scipy": scipy.__version__}


def run(out, workers):
    out.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=D.G.ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=D.G.ROOT, text=True)
    rows = subset()
    meta = {"git_head": head, "git_dirty_tracked": bool(dirty), "B": D.W3.B, "pad": D.W3.PAD,
            "subset": f"(seed - 430000) % {STEP} == 0", "rows": len(rows), "env": env(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    rows.sort(key=lambda r: r["oracle"].get("t_star") is not None)        # same order rule as diag3_dev
    with ProcessPoolExecutor(workers) as pool:
        for x in pool.map(D.job, [(r, str(out)) for r in rows]):
            print(x, flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


def compare(out, ref):
    rows = subset()
    rep = {"rows": len(rows), "both": 0, "missing_here": [], "missing_ref": [], "detect_differs": [],
           "margin_finding": [], "n_lp_differs": [], "n_retry_differs": [], "max_abs_margin_diff_mC": 0.0,
           "seconds": {"here": [], "ref": []}}
    for r in rows:
        k = D.key(r)
        a, b = out / f"dev-{k}.json", ref / f"dev-{k}.json"
        if not a.exists():
            rep["missing_here"].append(k)
        if not b.exists():
            rep["missing_ref"].append(k)
        if not (a.exists() and b.exists()):
            continue
        x, y = json.loads(a.read_text()), json.loads(b.read_text())
        rep["both"] += 1
        if x["cyl16p"] != y["cyl16p"]:
            rep["detect_differs"].append([k, "cyl16p", x["cyl16p"], y["cyl16p"]])
        for arm in ("S128", "S256"):
            p, q = x[arm], y[arm]
            if p["detect"] != q["detect"]:
                rep["detect_differs"].append([k, arm, p["detect"], q["detect"]])
            for f in ("margin_at_detect_mC", "margin_at_t_star_mC"):
                if (p[f] is None) != (q[f] is None):
                    rep["margin_finding"].append([k, arm, f, p[f], q[f]])
                elif p[f] is not None:
                    d = abs(p[f] - q[f])
                    rep["max_abs_margin_diff_mC"] = max(rep["max_abs_margin_diff_mC"], d)
                    if d > TOL_MC:
                        rep["margin_finding"].append([k, arm, f, p[f], q[f]])
            if p["n_lp"] != q["n_lp"]:
                rep["n_lp_differs"].append([k, arm, p["n_lp"], q["n_lp"]])
            if p["n_retry"] != q["n_retry"]:
                rep["n_retry_differs"].append([k, arm, p["n_retry"], q["n_retry"]])
            rep["seconds"]["here"].append(p["seconds"])
            rep["seconds"]["ref"].append(q["seconds"])
    for side in ("here", "ref"):
        s = rep["seconds"][side]
        rep["seconds"][side] = {"total": round(sum(s), 1), "median": statistics.median(s) if s else None}
    rep["passes"] = (rep["both"] == len(rows) and not rep["detect_differs"] and not rep["margin_finding"])
    (out / "compare.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("run", "compare"))
    ap.add_argument("out", type=Path)
    ap.add_argument("ref", type=Path, nargs="?")
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    if a.cmd == "run":
        run(a.out, a.workers)
    else:
        compare(a.out, a.ref)


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
