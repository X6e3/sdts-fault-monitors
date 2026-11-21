"""BASELINE-PLAN.md: a report on the DEV tuning run, for its record. Written after the run (2026-11-21), from its
files only; it runs no method and changes no choice (the choice is OUT/chosen.json, by the plan's rule).

  python -B baselines_dev_report.py OUT [--ambient AMB] [--json FILE]

  - per family: the chosen configurations, the best configuration at each memory level (the memory-lag frontier)
  - soundness over every configuration: alarms on admissible rows and before t*
  - B1 with Scott's LP rescaling against the same configuration without it and v2, on the same 200 rows
  - CPU seconds per processed sample, per configuration
  - with --ambient (the ambient study's part (b) files): cyl16p's DEV paired lag, scored the same way
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import baselines_run as R

N = R.T.N


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--ambient", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    rows = R.dev_rows()
    by = {R.key(r): r for r in rows}
    recs = defaultdict(list)
    for j in map(json.loads, (a.out / "rows.jsonl").read_text().splitlines()):
        recs[j["id"]].append(j)
    tune = json.loads((a.out / "tune.json").read_text())
    table, chosen = tune["table"], tune["chosen"]
    rep = {"configurations": len(table), "records": sum(len(v) for v in recs.values()), "chosen": {}}
    for k, i in chosen.items():
        t = table[i]
        rep["chosen"][k] = {"id": i, "memory": t["memory"], "paired_lag": t["paired_lag"],
                            "D_paired": round(t["D_paired"], 4), "misses": t["misses"]}
    rep["soundness"] = {"admissible_alarms": sum(len(t["admissible_alarms"]) for t in table.values()),
                        "early": sum(len(t["early"]) for t in table.values()),
                        "lp_fail": {i: t["lp_fail"] for i, t in table.items() if t["lp_fail"]}}
    front = {}
    for fam in ("B1", "B2", "B3", "B4"):
        pts = sorted((t["memory"], t["paired_lag"], i) for i, t in table.items() if i.startswith(fam + ":"))
        best, f = None, []
        for m, lag, i in pts:
            if best is None or lag < best:
                best = lag
                f.append({"memory": m, "paired_lag": lag, "D_paired": round(table[i]["D_paired"], 4), "id": i})
        front[fam] = f
    rep["frontier"] = front
    sec = {}
    for i, v in recs.items():
        samples = sum((N if x["detect"] is None else x["detect"] + 1) for x in v)
        sec[i] = round(sum(x["seconds"] for x in v) / samples * 1e3, 4)
    rep["ms_per_sample"] = sec
    # Scott's LP rescaling, against the same configuration with interval rescaling and v2, on its 200 rows
    lp_id = next(i for i in table if i.startswith("B1lp:"))
    sub = {x["key"] for x in recs[lp_id]}
    ref_id = R.cfg_id("B1", {"n_c": 8, "order": 4, "policy": "fifo", "prior": "box+err"})
    sub_rows = [by[k] for k in sub]
    rep["B1lp_subset"] = {"rows": len(sub), "lp": R.score(recs[lp_id], sub_rows)}
    if ref_id in recs:
        rep["B1lp_subset"]["interval"] = R.score([x for x in recs[ref_id] if x["key"] in sub], sub_rows)
    else:
        rep["B1lp_subset"]["interval"] = "B1 (8, 4, fifo, box+err) is not in the grid"
    gr = R.cfg_id("B1", {"n_c": 8, "order": 4, "policy": "greedy", "prior": "box+err"})
    rep["B1lp_subset"]["greedy"] = R.score([x for x in recs[gr] if x["key"] in sub], sub_rows)
    for k in ("lp", "interval", "greedy"):
        if isinstance(rep["B1lp_subset"][k], dict):
            rep["B1lp_subset"][k] = {x: rep["B1lp_subset"][k][x] for x in
                                     ("rows", "events", "paired", "paired_lag", "v2_paired_lag", "D_paired", "misses")}
    if a.ambient:
        amb = [json.loads(p.read_text()) for p in sorted(a.ambient.glob("b-*.json"))]
        cy = [{"key": x["key"], "detect": x["cyl16p@23-27"], "seconds": 0.0, "memory": 42, "lp_fail": 0} for x in amb]
        edge = [k for k, r in by.items() if r["noise"] == "edge"]
        s = R.score(cy, [by[x["key"]] for x in amb])
        rep["cyl16p_dev_1320"] = {x: s[x] for x in ("rows", "events", "paired", "paired_lag", "v2_paired_lag",
                                                     "D_paired", "misses")} | {"edge_rows_not_in_ambient": len(edge)}
    txt = json.dumps(rep, indent=1)
    print(txt)
    if a.json:
        a.json.write_text(txt + "\n")


if __name__ == "__main__":
    main()
