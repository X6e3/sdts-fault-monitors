"""Implementation check of the A1.5 ablations on CAL seeds (addendum A1; CAL only, never TRAIN or FINAL).

Checks only relations that must hold mathematically:
  - a relaxation never turns a consistent run inconsistent (oracle: full consistent => no ablation inconsistent);
  - the machine is a relaxation of the oracle with the same families (machine X inconsistent => oracle X
    inconsistent, for X in full, without (b), without (c));
  - healthy runs are consistent in every variant; constant offsets are consistent without (c) (P5);
  - optionally, the full oracle verdict equals an earlier CAL map (--reference cells.jsonl).
usage: python -B validate_ablations_cal.py OUT [--seeds 410000 410004] [--workers 8] [--reference FILE]
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
sys.path.insert(0, str(HERE.parents[1] / "machine"))
sys.path.insert(0, str(HERE.parents[2] / "env"))
import thermal_oracle as O  # noqa: E402
from thermal_machine import ThermalMachine  # noqa: E402
import thermal_v2_env  # noqa: E402

T = O.T
VARIANTS = ("full", "no_b", "no_c", "no_d")


def machine_verdict(y, P, **kw):
    m = ThermalMachine(**kw)
    first = None
    for k, (yk, pk) in enumerate(zip(y, P)):
        if m.observe(yk, pk) and first is None:
            first = k
    return {"inconsistent": first is not None, "first_inconsistent": first,
            "R1": m.verdict(1), "R3": m.verdict(3)}


def job(args):
    seed, cell_name, arm, out = args
    cell = next(c for c in T.CELLS if c.name == cell_name)
    r = T.run(seed, cell, arm)
    log = Path(out) / "solver_attempts" / f"{cell_name}-{seed}-{arm}"
    t0 = time.monotonic()
    oracle = {"full": O.verdict(r["z"], attempt_dir=log / "full"),
              "no_b": O.verdict(r["z"], rate=False, attempt_dir=log / "no_b"),
              "no_c": O.verdict(r["z"], box=False, attempt_dir=log / "no_c"),
              "no_d": O.verdict_free_command(r["y"], attempt_dir=log / "no_d")}
    machine = {"full": machine_verdict(r["y"], r["P"]),
               "no_b": machine_verdict(r["y"], r["P"], rate=False),
               "no_c": machine_verdict(r["y"], r["P"], box=False)}
    return {"seed": seed, "cell": cell_name, "arm": arm, "t_f": r["t_f"],
            "oracle": {k: {"verdict": v[0], "d_lo": v[1], "d_up": v[2]} for k, v in oracle.items()},
            "machine": machine, "seconds": round(time.monotonic() - t0, 3)}


def checks(rows, reference):
    bad = []
    for r in rows:
        key = (r["seed"], r["cell"], r["arm"])
        o, m = r["oracle"], r["machine"]
        if o["full"]["verdict"] == "consistent":
            bad += [(key, f"{v} inconsistent while full consistent") for v in VARIANTS[1:]
                    if o[v]["verdict"] == "inconsistent"]
        for v in ("full", "no_b", "no_c"):
            if m[v]["inconsistent"] and o[v]["verdict"] != "inconsistent":
                bad.append((key, f"machine {v} inconsistent, oracle {v} {o[v]['verdict']}"))
            if m[v]["inconsistent"] and not m["full"]["inconsistent"]:
                bad.append((key, f"machine {v} inconsistent but machine full not"))
        if r["cell"] == "healthy":
            bad += [(key, f"healthy {v} {o[v]['verdict']}") for v in VARIANTS if o[v]["verdict"] != "consistent"]
        if r["cell"].startswith("offset") and (o["no_c"]["verdict"] != "consistent" or m["no_c"]["inconsistent"]):
            bad.append((key, "offset not consistent without (c)"))
        if reference is not None and key in reference and reference[key] != o["full"]["verdict"]:
            bad.append((key, f"full {o['full']['verdict']} vs reference {reference[key]}"))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--seeds", type=int, nargs=2, default=(410000, 410004))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--reference", type=Path)
    a = ap.parse_args()
    lo, hi = a.seeds
    if not (410000 <= lo <= hi <= 410199):
        raise SystemExit("CAL seeds only (410000-410199)")
    env = thermal_v2_env.check()
    source = {"git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "git_dirty_tracked": bool(subprocess.run(["git", "diff", "--quiet", "HEAD"]).returncode),
              "recorded": "at start"}
    a.out.mkdir(parents=True, exist_ok=False)
    reference = None
    if a.reference:
        reference = {(x["seed"], x["cell"], x["arm"]): x["verdict"]
                     for x in map(json.loads, a.reference.read_text().splitlines()) if x}
    tasks = [(s, c.name, arm, str(a.out)) for s in range(lo, hi + 1) for c in T.CELLS for arm in T.ARMS]
    t0 = time.monotonic()
    with ProcessPoolExecutor(a.workers) as pool:
        rows = list(pool.map(job, tasks))
    rows.sort(key=lambda r: (r["cell"], r["arm"], r["seed"]))
    with (a.out / "rows.jsonl").open("w") as f:
        for r in rows:
            f.write(json.dumps(r, allow_nan=False) + "\n")
    bad = checks(rows, reference)
    table = {}
    for r in rows:
        t = table.setdefault(f"{r['cell']}/{r['arm']}", {})
        for v in VARIANTS:
            t.setdefault(f"oracle_{v}", {}).setdefault(r["oracle"][v]["verdict"], 0)
            t[f"oracle_{v}"][r["oracle"][v]["verdict"]] += 1
        for v in ("full", "no_b", "no_c"):
            t.setdefault(f"machine_{v}_inconsistent", 0)
            t[f"machine_{v}_inconsistent"] += int(r["machine"][v]["inconsistent"])
    summary = {"source": source,
               "env": env, "seeds": [lo, hi], "runs": len(rows), "seconds": round(time.monotonic() - t0, 1),
               "undetermined": {v: sum(r["oracle"][v]["verdict"] == "undetermined" for r in rows) for v in VARIANTS},
               "check_failures": [[list(k), msg] for k, msg in bad], "by_cell": table}
    (a.out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps({k: summary[k] for k in ("runs", "seconds", "undetermined")}, indent=1))
    print("check failures:", len(bad))
    for k, msg in bad[:20]:
        print("  ", k, msg)


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    main()
