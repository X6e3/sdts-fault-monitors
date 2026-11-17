"""Check the streaming machine on CAL only, with oracle offset evidence for P3."""
import argparse
import json
import math
import os
import subprocess
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from thermal_machine import T, ThermalMachine
from thermal_twins import pairs

CAL = range(410000, 410200)
CELLS = {cell.name: cell for cell in T.CELLS}
RADII = (1, 3)


def replay(y, command, *, box=True):
    machine = ThermalMachine(box=box)
    first = None
    for k, (sample, power) in enumerate(zip(y, command, strict=True)):
        if machine.observe(sample, power):
            first = k
            break
    return machine, first


def job(args):
    seed, name, arm = args
    run = T.run(seed, CELLS[name], arm)
    machine, first = replay(run["y"], run["P"])
    row = {"seed": seed, "cell": name, "arm": arm, "t_f": run["t_f"],
           "first_inconsistent": first, "first_scored_alarm": max(first, T.T_WARM) if first is not None else None,
           "offset_outer": machine.offset_outer, "verdicts": {str(r): machine.verdict(r) for r in RADII}}
    if name != "healthy" and "TUTARLI" in row["verdicts"].values():
        # A feasible plant offset must fit every sample using A[k] inside the ambient box.
        lo_z, hi_z = min(run["z"]), max(run["z"])
        pad = 32 * math.ulp(1.0) * (len(run["z"]) + 1) * max(1.0, abs(lo_z), abs(hi_z))
        row["box_only_offset_enclosure"] = (hi_z - T.TA_HI - T.DELTA - pad, lo_z - T.TA_LO + T.DELTA + pad)
    if seed < 410050 and CELLS[name].kind == "offset":
        row["inconsistent_without_box"] = replay(run["y"], run["P"], box=False)[0].inconsistent
    return row


def write_rows(out, name, items):
    with (out / f"{name}.jsonl").open("w") as stream:
        for row in items:
            stream.write(json.dumps(row, allow_nan=False) + "\n")


def p1_rows():
    for seed, case, arm, draw, b, (first_y, first_p, twin_y, twin_p) in pairs(T):
        first, t1 = replay(first_y, first_p)
        twin, t2 = replay(twin_y, twin_p)
        v1, v2 = [first.verdict(r) for r in RADII], [twin.verdict(r) for r in RADII]
        yield {"seed": seed, "case": case, "arm": arm, "draw": draw, "offset": b,
               "first_inconsistent": t1, "twin_first_inconsistent": t2,
               "verdicts": v1, "twin_verdicts": v2, "match": v1 == v2 and t1 == t2}


def offset_check(row, oracle, radius):
    if row["verdicts"][str(radius)] != "TUTARLI":
        return "machine_did_not_certify"
    inner, outer = oracle["interval"], oracle["outer_interval"]
    if inner is not None and (inner[0] < -radius or inner[1] > radius):
        return "contradiction"
    if outer is not None and outer[0] >= -radius and outer[1] <= radius:
        return "corroborated"
    return "oracle_undetermined"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("oracle_out", type=Path)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    args = parser.parse_args()
    git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    args.out.mkdir(parents=True, exist_ok=False)
    oracle_summary = json.loads((args.oracle_out / "summary.json").read_text())
    oracle_rows = [json.loads(line) for line in (args.oracle_out / "V0_P6.jsonl").read_text().splitlines()]
    oracle = {(r["seed"], r["arm"]): r for r in oracle_rows}
    tasks = [(seed, name, arm) for seed in CAL for name in CELLS for arm in T.ARMS]
    with ProcessPoolExecutor(args.workers) as pool:
        items = list(pool.map(job, tasks, chunksize=16))
    write_rows(args.out, "cells", items)
    print(f"CAL machine cells complete ({len(items)} rows)", flush=True)

    p1 = list(p1_rows())
    write_rows(args.out, "P1", p1)
    by_run = {(r["seed"], r["cell"], r["arm"]): r for r in items}
    p2 = []
    for seed in CAL:
        for name, cell in CELLS.items():
            if not cell.additive or cell.kind == "healthy":
                continue
            e0, e1 = (by_run[seed, name, arm] for arm in T.ARMS)
            same_time = e0["first_inconsistent"] == e1["first_inconsistent"]
            same_verdict = e0["verdicts"] == e1["verdicts"]
            p2.append({"seed": seed, "cell": name, "match": same_time and same_verdict})
    write_rows(args.out, "P2", p2)

    p3 = [{"seed": r["seed"], "cell": r["cell"], "arm": r["arm"], "radius": radius,
           "offset_check": offset_check(r, oracle[r["seed"], r["arm"]], radius),
           "healthy_inconsistent": r["first_inconsistent"] is not None}
          for r in items if r["cell"] == "healthy" for radius in RADII]
    for row in items:
        if "box_only_offset_enclosure" not in row:
            continue
        lo, hi = row["box_only_offset_enclosure"]
        for radius in RADII:
            if row["verdicts"][str(radius)] == "TUTARLI":
                status = "corroborated_by_box_bound" if -radius <= lo <= hi <= radius else "oracle_undetermined"
                p3.append({"seed": row["seed"], "cell": row["cell"], "arm": row["arm"], "radius": radius,
                           "offset_check": status})
    p4 = [{**r, "at_fault_onset": r["first_inconsistent"] == r["t_f"]}
          for r in items if r["cell"] in ("jump_2", "jump_5")]
    p5 = [r for r in items if "inconsistent_without_box" in r]
    for name, result in (("P3", p3), ("P4", p4), ("P5", p5)):
        write_rows(args.out, name, result)
    summary = {
        "git_head": git_head,
        "oracle_git_head": oracle_summary["source"]["git_head"],
        "cal_seed_range": [CAL.start, CAL.stop - 1],
        "runs": len(items),
        "P1_twins_matching": [sum(r["match"] for r in p1), len(p1)],
        "P2_additive_matching": [sum(r["match"] for r in p2), len(p2)],
        "P3_healthy_inconsistent": [sum(r["first_inconsistent"] is not None for r in items if r["cell"] == "healthy"),
                                   len(oracle)],
        "P3_offset_crosscheck": dict(Counter(r["offset_check"] for r in p3)),
        "P4_jumps_at_fault_onset": [sum(r["at_fault_onset"] for r in p4), len(p4)],
        "P5_offset_consistent_without_box": [sum(not r["inconsistent_without_box"] for r in p5), len(p5)],
    }
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
