"""TRAIN calibration of the baseline thresholds (addendum A1.2, A1.3). Healthy TRAIN runs only.

For each variant and arm: threshold = 1.05 x the maximum statistic over the 200 TRAIN healthy runs
(seeds 400000-400199). dmreda_native is then checked directly (zero events at k >= 300 on every TRAIN healthy
run of the arm) and raised by factors of 1.05 until that holds; score variants are checked the same way.
usage: python -B calibrate_train.py OUT [--workers 8]
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[2] / "env"))
import thermal_baselines as B  # noqa: E402
import thermal_v2_env  # noqa: E402

T = B.T
TRAIN = range(400000, 400200)
MARGIN = 1.05


def stats_job(args):
    seed, arm = args
    y = T.run(seed, T.CELLS[0], arm)["y"]
    t0 = time.monotonic()
    row = {"seed": seed, "arm": arm, "statistic": {v: B.statistic(v, y) for v in B.VARIANTS}}
    row["seconds"] = round(time.monotonic() - t0, 3)
    return row


def alarm_job(args):
    seed, arm, variant, threshold = args
    y = T.run(seed, T.CELLS[0], arm)["y"]
    return seed, bool(B.alarm_times(variant, y, threshold))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    env = thermal_v2_env.check()
    digest = B.verify_reference()
    a.out.mkdir(parents=True, exist_ok=False)
    t0 = time.monotonic()
    tasks = [(s, arm) for arm in T.ARMS for s in TRAIN]
    with ProcessPoolExecutor(a.workers) as pool:
        rows = list(pool.map(stats_job, tasks))
        with (a.out / "train_statistics.jsonl").open("w") as f:
            for r in rows:
                f.write(json.dumps(r, allow_nan=False) + "\n")
        thresholds = {}
        for variant, role in B.VARIANTS.items():
            for arm in T.ARMS:
                arm_rows = [r for r in rows if r["arm"] == arm]
                top = max(arm_rows, key=lambda r: r["statistic"][variant])
                threshold, steps = MARGIN * top["statistic"][variant], 0
                while True:
                    hits = [s for s, hit in pool.map(alarm_job, [(s, arm, variant, threshold) for s in TRAIN]) if hit]
                    if not hits:
                        break
                    threshold, steps = threshold * MARGIN, steps + 1
                thresholds.setdefault(variant, {"role": role})[arm] = {
                    "threshold": threshold, "max_statistic": top["statistic"][variant],
                    "argmax_seed": top["seed"], "raise_steps": steps, "train_alarms_at_threshold": 0}
    out = {"rule": "addendum A1.2/A1.3: 1.05 x max TRAIN healthy statistic per arm, then checked directly",
           "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
           "git_dirty_tracked": bool(subprocess.run(["git", "diff", "--quiet", "HEAD"]).returncode),
           "env": env, "dmreda_reference_sha256": digest, "train_seeds": [TRAIN[0], TRAIN[-1]],
           "runs_per_arm": len(TRAIN), "evaluation_from": B.EVAL_FROM, "seconds": round(time.monotonic() - t0, 1),
           "thresholds": thresholds}
    (a.out / "thresholds.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(thresholds, indent=1))


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()
