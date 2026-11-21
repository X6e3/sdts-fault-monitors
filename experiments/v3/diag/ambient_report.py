"""AMBIENT-PLAN.md: the items of sections 1 and 2 that `ambient_study.py summary` does not compute.

Written after the run (2026-11-21), from the plan's list of what is reported. It reads the run's per-run files
only; it runs no method and generates no data.
  (a) A1: for each alarm, whether the true TA had left [23, 27] at or before the alarm sample;
      per scenario and method: the alarming runs, whether F3's alarms are certified, the alarm delay after the step
      (A4).
  (b) per cell: lag against the oracle's t* (frozen box), misses and detections at t*, per method and assumed box.

  python -B ambient_report.py OUT [--json FILE]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

N = 3600
METHODS_A = ("v2", "cyl16p", "F3")
COLS_B = ("v2@23-27", "v2@22-28", "v2@21-29", "cyl16p@23-27", "cyl16p@22-28", "cyl16p@21-29")


def part_a(out):
    A = [json.loads(p.read_text()) for p in sorted(out.glob("a-*.json"))]
    rep = {}
    for scen in sorted({x["scenario"] for x in A}):
        xs = [x for x in A if x["scenario"] == scen]
        r = {"runs": len(xs)}
        for m in METHODS_A:
            al = [x for x in xs if x[m] is not None]
            r[m] = {"alarming_runs": sorted(f"{x['seed']}-{x['arm']}" for x in al)}
            if m == "F3":
                r[m]["certified"] = sum(bool(x["F3_certified"]) for x in al)
            if scen == "A1":
                out_first = {f"{x['seed']}-{x['arm']}": (x["TA_outside_box"][0] if x["TA_outside_box"] else None)
                             for x in xs}
                r[m]["alarm_after_TA_left_box"] = sum(out_first[f"{x['seed']}-{x['arm']}"] is not None
                                                      and out_first[f"{x['seed']}-{x['arm']}"] <= x[m] for x in al)
                r[m]["delay_after_leaving"] = sorted(x[m] - out_first[f"{x['seed']}-{x['arm']}"] for x in al
                                                     if out_first[f"{x['seed']}-{x['arm']}"] is not None)
            if scen == "A4":
                r[m]["delay_after_step"] = sorted(x[m] - 1000 for x in al)
        if scen == "A1":
            r["runs_TA_outside"] = sorted(f"{x['seed']}-{x['arm']}" for x in xs if x["TA_outside_box"])
            r["start_outside"] = sum(1 for x in xs if x["TA_outside_box"] == [0])
        r["max_rate_over_rho"] = max(x["max_rate_over_rho"] for x in xs)
        rep[scen] = r
    return rep


def part_b(out):
    B = [json.loads(p.read_text()) for p in sorted(out.glob("b-*.json"))]
    ev = [x for x in B if x["status"] == "certified" and x["t_star"] is not None]
    cells = defaultdict(list)
    for x in ev:
        cells[x["cell"]].append(x)
    rep = {"events": len(ev), "by_cell": {}}
    for cell, xs in sorted(cells.items()):
        c = {"events": len(xs)}
        for k in COLS_B:
            c[k] = {"lag": sum((N if x[k] is None else x[k]) - x["t_star"] for x in xs),
                    "misses": sum(x[k] is None for x in xs),
                    "at_t_star": sum(x[k] == x["t_star"] for x in xs)}
        rep["by_cell"][cell] = c
    rep["at_t_star_all"] = {k: sum(x[k] == x["t_star"] for x in ev) for k in COLS_B}
    rep["earlier_than_t_star"] = {k: sum(x[k] is not None and x[k] < x["t_star"] for x in ev) for k in COLS_B}
    rep["cyl16p_later_than_v2_same_box"] = {
        b: sum((N if x[f"cyl16p@{b}"] is None else x[f"cyl16p@{b}"]) > (N if x[f"v2@{b}"] is None else x[f"v2@{b}"])
               for x in ev) for b in ("23-27", "22-28", "21-29")}
    return rep


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    rep = {"a": part_a(a.out), "b": part_b(a.out)}
    txt = json.dumps(rep, indent=1)
    print(txt)
    if a.json:
        a.json.write_text(txt + "\n")


if __name__ == "__main__":
    main()
