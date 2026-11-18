"""DIAG-3 amendment 7 (DIAG-3-PLAN.md): F on healthy runs with edge noise (|noise| = DELTA exactly), DEV seeds
430070-430089, both arms and both ambient laws: 80 runs, every one admissible by construction.

usage:
  python -B diag3_cw_edge.py run OUT_DIR [--workers 14]
  python -B diag3_cw_edge.py summary OUT_DIR
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

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import diag3_cw_dev as CWD  # noqa: E402

G, S, T = CWD.G, CWD.S, CWD.T
SEEDS, W, K = range(430070, 430090), 256, 64


def job(args):
    seed, arm, al, out = args
    run = S.run(seed, next(c for c in T.CELLS if c.name == "healthy"), arm, al, "edge")
    res = {"seed": seed, "arm": arm, "ambient": al, "noise": "edge", **CWD.online("F", G.zs_of(run), W, K)}
    (Path(out) / f"edge-{seed}-{arm}-{al}.json").write_text(json.dumps(res) + "\n")
    return seed, arm, al, res["detect"], res["seconds"]


def summary(out):
    xs = [json.loads(p.read_text()) for p in sorted(out.glob("edge-*.json"))]
    alarms = [[x["seed"], x["arm"], x["ambient"], x["detect"], x["alarm_certificate"]] for x in xs if x["detect"] is not None]
    return {"runs": len(xs), "alarms": alarms, "E1_passes": len(xs) == 80 and not alarms,
            "max_kept": max(x["max_kept"] for x in xs), "evictions": sum(x["evictions"] for x in xs),
            "max_rows": max(x["max_rows"] for x in xs), "n_retry": sum(x["n_retry"] for x in xs)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("run", "summary"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "summary":
        rep = summary(a.out)
        (a.out / "summary.json").write_text(json.dumps(rep, indent=1) + "\n")
        print(json.dumps(rep, indent=1))
        return
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=G.ROOT, text=True).strip()
    meta = {"git_head": head, "W": W, "K": K, "machine": platform.machine(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    jobs = [(s, arm, al, str(a.out)) for s in SEEDS for arm in ("E0", "E1") for al in ("rw", "ramp")]
    with ProcessPoolExecutor(a.workers) as pool:
        for x in pool.map(job, jobs):
            print(x, flush=True)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
