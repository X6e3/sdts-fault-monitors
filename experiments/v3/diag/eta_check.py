"""Validation 3 (RECORD-2026-11-22-review-checks.md): for the 12 events WM detected after t*, the oracle's certified
bounds on d* at the prefixes z[0:t*] (consistent) and z[0:t*+1] (inconsistent), and how far d_lo exceeds delta there
  python -B experiments/v3/diag/eta_check.py   (the project Python; regenerates the 12 runs, 24 oracle LPs)
"""
import hashlib, json, sys, tempfile
from multiprocessing import Pool
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
for sub in ("experiments/v3", "experiments/oracle", "experiments/machine", "experiments/generators", "env"):
    sys.path.insert(0, str(ROOT / sub))
import dev_scenarios as S
import thermal_oracle as O
T = O.T
MAN = ROOT / "experiments/v3/frozen/MANIFEST-V3.json"
LATE = [(440402, "drift_0.0005", "E0", "ramp", 1414, 1434), (440402, "drift_0.0005", "E1", "ramp", 1414, 1434),
        (440493, "drift_0.002", "E0", "rw", 789, 988), (440493, "drift_0.002", "E1", "rw", 789, 988),
        (440534, "drift_0.0005", "E0", "ramp", 1963, 1980), (440534, "drift_0.0005", "E1", "ramp", 1963, 1980),
        (440558, "drift_0.0005", "E0", "ramp", 2053, 2077), (440558, "drift_0.0005", "E1", "ramp", 2053, 2077),
        (440568, "drift_0.001", "E0", "ramp", 1345, 1505), (440568, "drift_0.001", "E1", "ramp", 1345, 1505),
        (440599, "drift_0.0005", "E0", "ramp", 2120, 2332), (440599, "drift_0.0005", "E1", "ramp", 2120, 2332)]
def one(x):
    S.unlock_validation(hashlib.sha256(MAN.read_bytes()).hexdigest())
    seed, cell, arm, amb, ts, det = x
    c = next(c for c in T.CELLS if c.name == cell)
    r = S.run(seed, c, arm, amb, "uniform")
    with tempfile.TemporaryDirectory() as d:
        lo1, up1 = O.margin(r["z"], ts, attempt_dir=Path(d) / "a")
        lo2, up2 = O.margin(r["z"], ts + 1, attempt_dir=Path(d) / "b")
    return {"row": f"{seed}-{cell}-{arm}-{amb}-uniform", "t_star": ts, "WM": det,
            "prefix_t*_d_up_minus_delta": up1 - T.DELTA, "prefix_t*+1_d_lo_minus_delta": lo2 - T.DELTA}
if __name__ == "__main__":
    with Pool(4) as p:
        for o in p.map(one, LATE):
            print(json.dumps(o))
