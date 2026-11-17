"""Independent read-only checks: the TUTARLI-on-drift counterexample and the P7 E1 mechanism.
usage: python -I check_p7_tutarli.py <repo> <evidence-dir>  (evidence: SDTS-CAL-evidence.tar.gz, unpacked)"""
import json, sys
from collections import Counter
from pathlib import Path
repo, ev = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo / "experiments" / "generators")); sys.path.insert(0, str(repo / "experiments" / "machine"))
import thermal as T
from thermal_machine import ThermalMachine
rows = lambda p: [json.loads(l) for l in (ev / p).read_text().splitlines() if l.strip()]
O = {(r["seed"], r["cell"], r["arm"]): r["verdict"] for r in rows("cal-4e87cd3/cells.jsonl")}
M = rows("cal-machine-complete/cells.jsonl")
print("1. drift_0.001 machine TUTARLI(R=1): oracle verdict on the 50-seed overlap")
tut = [r for r in M if r["cell"] == "drift_0.001" and r["verdicts"]["1"] == "TUTARLI"]
print("  ", Counter(O.get((r["seed"], r["cell"], r["arm"]), "not in map") for r in tut))
print("   arms", Counter(r["arm"] for r in tut), " healthy TUTARLI(R=1):", sum(r["cell"]=="healthy" and r["verdicts"]["1"]=="TUTARLI" for r in M))
# one worked example, recomputed here from scratch with the machine
r0 = next(r for r in tut if (r["seed"], r["cell"], r["arm"]) in O and O[(r["seed"], r["cell"], r["arm"])] == "consistent")
s, arm = r0["seed"], r0["arm"]
run = T.run(s, next(c for c in T.CELLS if c.name == "drift_0.001"), arm)
m = ThermalMachine()
for y, p in zip(run["y"], run["P"]): m.observe(y, p)
err = [y - ts - v for y, ts, v in zip(run["y"], run["Ts"], run["v"])]
print(f"   example seed {s} {arm}: oracle {O[(s,'drift_0.001',arm)]}, machine outer {tuple(round(x,3) for x in m.offset_outer)}, "
      f"verdict R=1 {m.verdict(1)}, R=3 {m.verdict(3)}; true error at end {err[-1]:.3f} C; TA range {min(run['TA']):.2f}-{max(run['TA']):.2f}")
print("   stuck TUTARLI(R=3) arms:", Counter(r["arm"] for r in M if r["cell"]=="stuck" and r["verdicts"]["3"]=="TUTARLI"))
st = [r for r in M if r["cell"]=="stuck" and r["verdicts"]["3"]=="TUTARLI"]
worst = 0
for r in st:
    run = T.run(r["seed"], next(c for c in T.CELLS if c.name=="stuck"), r["arm"])
    worst = max(worst, max(abs(y - ts - v) for y, ts, v in zip(run["y"], run["Ts"], run["v"])))
print(f"   stuck TUTARLI(R=3): worst true |error| over run {worst:.3f} C")

print("2. P7 E1 mechanism")
D = rows("cal-p7-diagnostics.jsonl"); P7 = {r["seed"]: r for r in rows("cal-4e87cd3/P7.jsonl") if r["arm"] == "E1"}
tf_on_change = 0
for r in D:
    P = T.command(r["seed"], "E1"); tf = r["t_f"]
    if abs(P[tf] - P[tf-1]) >= 5: tf_on_change += 1
print("   runs where P changes by >=5 W exactly at index t_f (excluded by k>t_f):", tf_on_change)
grp = {"early": [], "window": []}
for r in D:
    S = T.known_part(T.command(r["seed"], "E1"))
    tf, k = r["t_f"], r["k_change"]
    dS = max(abs(S[j] - S[tf]) for j in range(tf, k))           # command-part motion between t_f and k
    slope = abs(S[tf+1] - S[tf])                                 # is the plant at rest at t_f?
    grp["early" if P7[r["seed"]]["before_change"] == "inconsistent" else "window"].append((k - tf, dS, slope))
for g, xs in grp.items():
    xs.sort()
    ks = [x[0] for x in xs]; ds = sorted(x[1] for x in xs); sl = sorted(x[2] for x in xs)
    print(f"   {g:6s} n={len(xs)}  k-t_f min/med/max {ks[0]}/{ks[len(ks)//2]}/{ks[-1]}  "
          f"max|S-S[t_f]| before k min/med/max {ds[0]:.3f}/{ds[len(ds)//2]:.3f}/{ds[-1]:.3f}  |dS/dt| at t_f med {sl[len(sl)//2]:.4f}")
# how far from rest is the E1 plant anywhere after warm-up? (fraction of samples with |dS| < 1e-3 C/s)
allsl = []
for s in range(410000, 410050):
    S = T.known_part(T.command(s, "E1"))
    allsl += [abs(S[j+1]-S[j]) for j in range(T.T_WARM, T.N-1)]
print(f"   E1 CAL, after warm-up: share of samples with |dS| < 1e-3 C/s: {sum(x < 1e-3 for x in allsl)/len(allsl):.4f}; median |dS| {sorted(allsl)[len(allsl)//2]:.4f} C/s")
