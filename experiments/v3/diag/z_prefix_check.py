"""Validation 3: the smallest measurement z on the prefixes the oracle judged (RECORD-2026-11-23-review3-checks.md).

The oracle shifts z by 25 before its LPs; z - 25 is exact for z >= 12.5 (Sterbenz up to 50; above 50 it is a multiple
of z's ulp below 2^53). This regenerates every fault run of validation 3 (data only, no monitor, no LP) and reports the
smallest z on z[0:t*+1] for the certified events and on z[0:N] for the certified-consistent runs, with the counts below
12.5, and the smallest z over all samples (after t* a stuck sensor can read far below the plant).

  python -B experiments/v3/diag/z_prefix_check.py [WORKERS]
"""
import hashlib
import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for sub in ("experiments/v3", "experiments/oracle", "experiments/machine", "experiments/generators", "env"):
    sys.path.insert(0, str(ROOT / sub))
import dev_scenarios as S  # noqa: E402
import thermal_oracle as O  # noqa: E402

T = O.T
MAN = ROOT / "experiments/v3/frozen/MANIFEST-V3.json"
ROWS = ROOT / "results/v3/freeze3/validation-440400-440599-948b46b0/rows.jsonl"


def one(r):
    S.unlock_validation(hashlib.sha256(MAN.read_bytes()).hexdigest())
    c = next(c for c in T.CELLS if c.name == r["cell"])
    z = S.run(r["seed"], c, r["arm"], r["amb"], r["noise"])["z"]
    ts = r["oracle"]["t_star"]
    pre = z[:ts + 1] if ts is not None else z
    return r["key"], ts, float(min(pre)), int(sum(1 for v in pre if v < 12.5)), float(min(z))


def main(workers):
    todo = []
    for line in open(ROWS):
        r = json.loads(line)
        if r["cell"] != "healthy" and r["oracle"]["status"] == "certified":
            todo.append({"key": f'{r["seed"]}-{r["cell"]}-{r["arm"]}-{r["ambient"]}-{r["noise"]}', "seed": r["seed"],
                         "cell": r["cell"], "arm": r["arm"], "amb": r["ambient"], "noise": r["noise"],
                         "oracle": r["oracle"]})
    with Pool(workers) as p:
        out = p.map(one, todo, chunksize=20)
    ev = [o for o in out if o[1] is not None]
    co = [o for o in out if o[1] is None]
    res = {"runs": len(out), "events": len(ev), "consistent": len(co),
           "min_z_event_prefix": min(o[2] for o in ev), "below_12.5_event_prefix": sum(o[3] for o in ev),
           "min_z_consistent": min(o[2] for o in co), "below_12.5_consistent": sum(o[3] for o in co),
           "min_z_all_samples": min(o[4] for o in out),
           "argmin_event_prefix": min(ev, key=lambda o: o[2])[0]}
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
