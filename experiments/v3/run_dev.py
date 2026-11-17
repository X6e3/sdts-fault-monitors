"""v3 DEV comparison: oracle (full history) vs v2 machine vs template states, same decision semantics.

Decision for every method: the first sample k at which no admissible explanation with b = 0 and |noise| <= DELTA
exists for z[0..k] ("TUTARSIZ"). Oracle: certified LP prefix search (v2 oracle, unchanged). DEV seeds only.
Checks recorded per run: no method earlier than the oracle (soundness), healthy never flagged, and for the
templates with reachable-set clamps, never later than v2 (dominance, V3_NOTES.md).
usage: python -B run_dev.py OUT [--seeds 430000 430029] [--workers 14]
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
ROOT = HERE.parents[2]
for sub in ("experiments/v3", "experiments/oracle", "experiments/machine", "experiments/generators", "env"):
    sys.path.insert(0, str(ROOT / sub))
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402
import thermal_oracle as O  # noqa: E402
import thermal_v2_env  # noqa: E402
from thermal_machine import ThermalMachine  # noqa: E402

T = V.T
CELLS = ("healthy", "jump_0.2", "jump_0.5", "drift_0.0005", "drift_0.001", "drift_0.002", "drift_0.005",
         "drift_0.02", "noise_x2", "stuck", "gain_0.01")
LAWS = (("rw", "uniform"), ("ramp", "uniform"))
SPECS = [  # (name, kind, kwargs, invariant)
    ("box", "box", {}, False),
    ("box+diff", "box+diff", {}, False),
    ("box+diff+I", "box+diff", {}, True),
    ("inv2+I", "inv", {"N": 2}, True),
    ("inv4+I", "inv", {"N": 4}, True),
    ("inv8+I", "inv", {"N": 8}, True),
    ("inv16+I", "inv", {"N": 16}, True),
    ("inv4+orbit2+I", "inv+orbit", {"N": 4, "L": 2}, True),
    ("inv8+orbit4+I", "inv+orbit", {"N": 8, "L": 4}, True),
]
TEMPLATES = None


def init():
    global TEMPLATES
    TEMPLATES = {name: V.Template(V.directions(kind, **kw), name=name, invariant=inv) for name, kind, kw, inv in SPECS}


def v2_first(y, P):
    m = ThermalMachine()
    for k, (a, b) in enumerate(zip(y, P)):
        if m.observe(a, b):
            return k
    return None


def job(args):
    seed, cell_name, arm, al, nl, out = args
    cell = next(c for c in T.CELLS if c.name == cell_name)
    r = S.run(seed, cell, arm, al, nl)
    t0 = time.monotonic()
    t_star, status = O.first_inconsistent(r["z"], attempt_dir=Path(out) / "solver_attempts" / f"{cell_name}-{seed}-{arm}-{al}")
    t_oracle = time.monotonic() - t0
    row = {"seed": seed, "cell": cell_name, "arm": arm, "ambient": al, "noise": nl, "t_f": r["t_f"],
           "oracle": {"t_star": t_star, "status": status, "seconds": round(t_oracle, 2)},
           "v2": v2_first(r["y"], r["P"]), "templates": {}}
    for name, tp in TEMPLATES.items():
        t1 = time.monotonic()
        row["templates"][name] = {"first": V.first_inconsistent(tp, r["y"], r["P"]),
                                  "seconds": round(time.monotonic() - t1, 3)}
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--seeds", type=int, nargs=2, default=(430000, 430029))
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    lo, hi = a.seeds
    if not (S.DEV[0] <= lo <= hi <= S.DEV[-1]):
        raise SystemExit("DEV seeds only")
    env = thermal_v2_env.check()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=ROOT).returncode)
    a.out.mkdir(parents=True, exist_ok=False)
    init()
    costs = {name: tp.cost() for name, tp in TEMPLATES.items()}
    meta = {"git_head": head, "git_dirty_tracked": dirty, "env": env, "seeds": [lo, hi], "cells": CELLS,
            "laws": LAWS, "specs": [s[0] for s in SPECS], "costs": costs,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    tasks = [(s, c, arm, al, nl, str(a.out)) for c in CELLS for arm in T.ARMS for al, nl in LAWS for s in range(lo, hi + 1)]
    t0 = time.monotonic()
    with ProcessPoolExecutor(a.workers, initializer=init) as pool, (a.out / "rows.jsonl").open("w") as f:
        for row in pool.map(job, tasks, chunksize=1):
            f.write(json.dumps(row) + "\n")
            f.flush()
    meta["seconds"] = round(time.monotonic() - t0, 1)
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (a.out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(json.dumps({"runs": len(tasks), "seconds": meta["seconds"]}))


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()
