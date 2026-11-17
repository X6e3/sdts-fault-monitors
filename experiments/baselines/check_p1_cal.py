"""P1 for the baselines on all CAL twin pairs, with the committed TRAIN thresholds (addendum A1.4).

Every variant, with each arm's threshold, must give the same alarm/no-alarm verdict on both members of every
pair (offset open loop, offset closed loop, stuck at rest). CAL only: an implementation check before FINAL.
usage: python -B check_p1_cal.py OUT --thresholds FILE [--workers 8]
"""
import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "generators"))
sys.path.insert(0, str(HERE.parents[2] / "env"))
import thermal_baselines as B  # noqa: E402
import thermal_twins  # noqa: E402
import thermal_v2_env  # noqa: E402

T = B.T
THRESHOLDS = None


def init(th):
    global THRESHOLDS
    THRESHOLDS = th


def job(item):
    seed, case, arm, draw, b, (y_a, _, y_b, _) = item
    row = {"seed": seed, "case": case, "arm": arm, "draw": draw, "differs": [], "alarms": {}}
    for v in B.VARIANTS:
        for arm_t in T.ARMS:
            th = THRESHOLDS[v][arm_t]["threshold"]
            a, c = B.outcome(v, y_a, th)["alarm"], B.outcome(v, y_b, th)["alarm"]
            row["alarms"][f"{v}@{arm_t}"] = [a, c]
            if a != c:
                row["differs"].append(f"{v}@{arm_t}")
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--thresholds", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    env = thermal_v2_env.check()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    th = json.loads(a.thresholds.read_text())["thresholds"]
    a.out.mkdir(parents=True, exist_ok=False)
    items = list(thermal_twins.pairs(T))
    with ProcessPoolExecutor(a.workers, initializer=init, initargs=(th,)) as pool:
        rows = list(pool.map(job, items, chunksize=8))
    with (a.out / "P1_baselines.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    alarm_counts = {k: sum(r["alarms"][k][0] for r in rows) for k in rows[0]["alarms"]}
    summary = {"git_head_at_start": head, "env": env, "pairs": len(rows),
               "pairs_with_a_differing_verdict": sum(bool(r["differs"]) for r in rows),
               "differing": [[r["seed"], r["case"], r["arm"], r["draw"], r["differs"]] for r in rows if r["differs"]],
               "alarm_counts_member_a": alarm_counts}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: summary[k] for k in ("pairs", "pairs_with_a_differing_verdict")}))


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
