"""Compare a run_final.py --rehearsal output (CAL seeds) with independent earlier CAL evidence.

  oracle full verdict, t*, P4, P7, healthy P6 intervals   vs  reviewer B's CAL package (cal-4e87cd3, cal-latency-final)
  machine first inconsistent and R=1/3 verdicts           vs  cal-machine-complete
  oracle and machine ablations                             vs  the A1.5 CAL check (validate_ablations_cal)
Read-only; every mismatch is printed.
usage: python -I check_rehearsal.py REHEARSAL_DIR EVIDENCE_DIR ABLATIONS_DIR
"""
import json
import sys
from pathlib import Path

reh, ev, abl = (Path(p) for p in sys.argv[1:4])


def rows(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def key(r):
    return (r["seed"], r["cell"], r["arm"])


R = {key(r): r for r in rows(reh / "runs.jsonl")}
cells = {key(r): r for r in rows(ev / "cal-4e87cd3/cells.jsonl")}
lat = {key(r): r for r in rows(ev / "cal-latency-final/latency.jsonl")}
p4 = {key(r): r for r in rows(ev / "cal-4e87cd3/P4.jsonl")}
p7 = {(r["seed"], "stuck", r["arm"]): r for r in rows(ev / "cal-4e87cd3/P7.jsonl")}
v0 = {(r["seed"], "healthy", r["arm"]): r for r in rows(ev / "cal-4e87cd3/V0_P6.jsonl")}
mach = {key(r): r for r in rows(ev / "cal-machine-complete/cells.jsonl")}
ab = {key(r): r for r in rows(abl / "rows.jsonl")}
bad, n = [], {}


def check(name, k, ours, theirs):
    n[name] = n.get(name, 0) + 1
    if ours != theirs:
        bad.append((name, k, ours, theirs))


for k, r in R.items():
    o, m = r["oracle"], r["machine"]
    if k in cells:
        check("oracle full verdict", k, o["full"]["verdict"], cells[k]["verdict"])
    if k in lat:
        check("t*", k, (o["full"]["t_star"], o["full"]["t_star_status"]), (lat[k]["t_star"], lat[k]["status"]))
    if k in p4:
        check("P4", k, (r["P4"]["before"], r["P4"]["at"]), (p4[k]["before"], p4[k]["at"]))
    if k in p7 and k[2] == "E1":
        mine = {x: r["P7"][x] for x in ("k_change", "at_tf", "before_change", "by_k_plus_30")}
        check("P7", k, mine, {x: p7[k][x] for x in mine})
    if k in v0:
        for f in ("interval", "outer_interval", "A_min", "A_max"):
            a, b = r["P6"][f], v0[k][f]
            same = (a is None and b is None) or (a is not None and b is not None and
                                                 max(abs(x - y) for x, y in zip(a if isinstance(a, list) else [a],
                                                                                 b if isinstance(b, list) else [b])) <= 1e-9)
            check(f"P6 {f}", k, True, same)
    if k in mach:
        check("machine first inconsistent", k, m["full"]["first_inconsistent"], mach[k]["first_inconsistent"])
        check("machine R1/R3", k, (m["full"]["R1"], m["full"]["R3"]), (mach[k]["verdicts"]["1"], mach[k]["verdicts"]["3"]))
    if k in ab:
        for v in ("no_b", "no_c", "no_d"):
            check(f"oracle {v}", k, o[v]["verdict"], ab[k]["oracle"][v]["verdict"])
        for v in ("no_b", "no_c"):
            check(f"machine {v}", k, m[v]["first_inconsistent"], ab[k]["machine"][v]["first_inconsistent"])

print("comparisons:", json.dumps(n, indent=1))
print("mismatches:", len(bad))
for b in bad[:30]:
    print("  ", b)
