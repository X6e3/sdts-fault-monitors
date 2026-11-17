"""Summarise a run_dev.py output: soundness checks, agreement with the oracle, lag, and cost per method.

lag = method first-inconsistent - oracle t* (same decision; >= 0 by soundness). "miss" = the oracle finds the
run inconsistent and the method never does. Reported per method over all fault runs, and per cell.
usage: python -I analyze_dev.py RUN_DIR
"""
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

d = Path(sys.argv[1])
rows = [json.loads(l) for l in (d / "rows.jsonl").read_text().splitlines() if l.strip()]
meta = json.loads((d / "meta.json").read_text())
methods = ["v2"] + meta["specs"]


def first(r, m):
    return r["v2"] if m == "v2" else r["templates"][m]["first"]


def q(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p * (len(xs) - 1) + 0.5))] if xs else None


out = {"runs": len(rows), "oracle_uncertified": sum(r["oracle"]["status"] != "certified" for r in rows),
       "methods": {}, "by_cell": defaultdict(dict)}
for m in methods:
    lags, miss, earlier, healthy_flag, equal, n_inc = [], 0, 0, 0, 0, 0
    for r in rows:
        f, t = first(r, m), r["oracle"]["t_star"]
        if r["cell"] == "healthy":
            healthy_flag += f is not None
            continue
        if t is None:
            earlier += f is not None            # oracle consistent, method inconsistent: unsound
            continue
        n_inc += 1
        if f is None:
            miss += 1
        elif f < t:
            earlier += 1
        else:
            lags.append(f - t)
            equal += f == t
    cost = {"state_numbers": 2, "table_entries": 0, "mac_per_sample": 6} if m == "v2" else meta["costs"][m]
    out["methods"][m] = {"unsound_events": earlier + healthy_flag, "oracle_inconsistent_runs": n_inc, "missed": miss,
                         "equal_to_oracle": equal, "lag_median": q(lags, .5), "lag_p90": q(lags, .9),
                         "lag_max": max(lags) if lags else None, "lag_sum": sum(lags), "cost": cost}
for m in methods:
    per = defaultdict(list)
    for r in rows:
        if r["cell"] == "healthy" or r["oracle"]["t_star"] is None:
            continue
        f = first(r, m)
        per[(r["cell"], r["ambient"])].append(None if f is None else f - r["oracle"]["t_star"])
    for (cell, amb), xs in per.items():
        got = [x for x in xs if x is not None]
        out["by_cell"][f"{cell}/{amb}"][m] = {"n": len(xs), "miss": len(xs) - len(got), "lag_mean": round(statistics.mean(got), 1) if got else None,
                                              "lag_max": max(got) if got else None}
(d / "analysis.json").write_text(json.dumps(out, indent=1) + "\n")
print(f"runs {out['runs']}  oracle uncertified t*: {out['oracle_uncertified']}")
print(f"{'method':16s} {'state':>5s} {'entries':>7s} {'MAC/s':>7s} | {'unsound':>7s} {'inc':>4s} {'miss':>4s} {'=orc':>5s} {'lag med':>7s} {'p90':>5s} {'max':>5s} {'sum':>7s}")
for m, v in out["methods"].items():
    c = v["cost"]
    print(f"{m:16s} {c['state_numbers'] if 'state_numbers' in c else c['state_floats']:5d} {c['table_entries']:7d} {c['mac_per_sample']:7d} | "
          f"{v['unsound_events']:7d} {v['oracle_inconsistent_runs']:4d} {v['missed']:4d} {v['equal_to_oracle']:5d} "
          f"{v['lag_median']!s:>7s} {v['lag_p90']!s:>5s} {v['lag_max']!s:>5s} {v['lag_sum']:7d}")
