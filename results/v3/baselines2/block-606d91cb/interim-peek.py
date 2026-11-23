"""Interim look at the BASELINE2 block (read-only; not part of the plan): score() restricted to the finished rows."""
import json, sys
from pathlib import Path
sys.path[:0] = ["experiments/v3/diag", "experiments/v3"]
import baselines2_run as B
OUT = Path("/home/x6e3/Research/sdts-runs/baselines2-block-606d91cb")
R, T = B.R, B.T
val = {R.key(r): r for r in map(json.loads, B.VAL3.read_text().splitlines()) if r}
new = {}
for l in (OUT / "rows.jsonl").read_text().splitlines():
    try: j = json.loads(l); new[j["key"]] = j
    except Exception: pass
old = B.first_block()
chosen = json.loads((OUT / "meta.json").read_text())["chosen"]
keys = [k for k in val if k in new]
ev = [k for k in keys if val[k]["oracle"]["status"] == "certified" and val[k]["oracle"]["t_star"] is not None]
paired = [k for k in ev if val[k]["v2"] is not None]
adm = [k for k in keys if val[k]["cell"] == "healthy" or (val[k]["oracle"]["status"] == "certified" and val[k]["oracle"]["t_star"] is None)]
ts = lambda k: val[k]["oracle"]["t_star"]
det = {"IM": {k: val[k]["v2"] for k in keys}, "WM": {k: val[k]["F3"]["detect"] for k in keys},
       "TS": {k: old[k]["cyl16p"]["detect"] for k in keys}}
for n, i in chosen.items():
    det[n] = {k: new[k][i]["detect"] for k in keys}
lag = lambda d, k: (T.N if d is None else d) - ts(k)
LIM = sum(lag(det["IM"][k], k) for k in paired)
print(f"rows {len(keys)}/9600, seeds {len({val[k]['seed'] for k in keys})}, events {len(ev)}, paired {len(paired)}, admissible {len(adm)}")
for n, d in det.items():
    L = sum(lag(d[k], k) for k in paired)
    print(f"{n:8s} paired_lag {L:9d}  D_paired {1 - L / LIM:+.4f}  misses {sum(d[k] is None for k in ev):3d}  "
          f"adm_alarms {sum(d[k] is not None for k in adm)}  early {sum(d[k] is not None and d[k] < ts(k) for k in ev)}")
lf = {n: sum(new[k][i].get("lp_fail", 0) for k in keys) for n, i in chosen.items()}
print("lp_fail", lf)
Rrows = [{"seed": val[k]["seed"], **{n: lag(det[n][k], k) for n in det}} for k in paired]
for a, b in (("WM", "B1s@M2"), ("TS", "B1s@M1"), ("TS", "B4s@M1")):
    if b in det:
        print(f"{a} < {b}:", json.dumps(R.boot_diff(Rrows, a, b)))
