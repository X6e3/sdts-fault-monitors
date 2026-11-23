"""ORACLE-MARGIN-PLAN.md: for every certified fault run of validation 3, the oracle's certified bounds at the prefixes
z[0:t*] (consistent side) and z[0:t*+1] (inconsistent side), or z[0:N] for a run certified consistent.
  python -B experiments/v3/diag/oracle_margin_check.py OUT.jsonl [--workers 14]   (the project Python)
"""
import argparse, hashlib, json, sys, tempfile, time
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


def one(row):
    S.unlock_validation(hashlib.sha256(MAN.read_bytes()).hexdigest())
    cell = next(c for c in T.CELLS if c.name == row["cell"])
    r = S.run(row["seed"], cell, row["arm"], row["ambient"], row["noise"])
    z, ts = r["z"], row["oracle"]["t_star"]
    out = {"row": f'{row["seed"]}-{row["cell"]}-{row["arm"]}-{row["ambient"]}-{row["noise"]}', "t_star": ts}
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory() as d:
        if ts is None:
            lo, up = O.margin(z, len(z), attempt_dir=Path(d) / "n")
            out.update(consistent_room=T.DELTA - up, verdict_n=O._verdict(lo, up))
        else:
            lo1, up1 = O.margin(z, ts, attempt_dir=Path(d) / "a")
            lo2, up2 = O.margin(z, ts + 1, attempt_dir=Path(d) / "b")
            out.update(consistent_room=T.DELTA - up1, inconsistent_room=lo2 - T.DELTA,
                       verdict_ts=O._verdict(lo1, up1), verdict_ts1=O._verdict(lo2, up2))
    out["seconds"] = round(time.monotonic() - t0, 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    rows = [json.loads(l) for l in ROWS.read_text().splitlines() if l.strip()]
    todo = [r for r in rows if r["cell"] != "healthy" and r["oracle"]["status"] == "certified"]
    print(f"{len(todo)} certified fault runs", flush=True)
    with Pool(a.workers) as p, open(a.out, "x") as f:
        for k, o in enumerate(p.imap_unordered(one, todo, chunksize=4)):
            f.write(json.dumps(o, sort_keys=True) + "\n")
            if k % 500 == 0:
                f.flush(); print(k, flush=True)
    res = [json.loads(l) for l in a.out.read_text().splitlines()]
    def stats(key):
        v = sorted(o[key] for o in res if key in o)
        return {"n": len(v), "min": v[0], "below_5e-13": sum(x <= 5e-13 for x in v),
                "below_1e-9": sum(x <= 1e-9 for x in v), "below_1e-6": sum(x <= 1e-6 for x in v)} if v else None
    changed = [o["row"] for o in res if o.get("verdict_ts", "consistent") != "consistent"
               or o.get("verdict_ts1", "inconsistent") != "inconsistent" or o.get("verdict_n", "consistent") != "consistent"]
    print(json.dumps({"runs": len(res), "consistent_room": stats("consistent_room"),
                      "inconsistent_room": stats("inconsistent_room"), "verdict_changed": changed}, indent=1))


if __name__ == "__main__":
    main()
