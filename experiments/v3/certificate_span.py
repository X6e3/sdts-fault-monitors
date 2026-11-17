"""How much history does an inconsistency proof need? (DEV)

At the oracle's t*, the margin LP on z[0..t*] has d* > DELTA. Its dual solution (a vertex, so sparse) is a proof
of inconsistency: a nonnegative combination of measurement, rate and box constraints. The earliest measurement
with a nonzero multiplier gives the proof's span t* - j_min: the depth of history this detection needs. Also
reported: the number of measurements in the proof. A dual solution is not unique; this is the solver's vertex.
usage: python -B certificate_span.py RUN_DEV_DIR OUT_JSON
"""
import json
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "oracle"), str(HERE.parent / "generators")]
import dev_scenarios as S  # noqa: E402
import thermal_oracle as O  # noqa: E402

T = S.T


def job(row):
    r = S.run(row["seed"], next(c for c in T.CELLS if c.name == row["cell"]), row["arm"], row["ambient"], row["noise"])
    t = row["oracle"]["t_star"]
    m = t + 1
    with tempfile.TemporaryDirectory() as d:
        res = None
        for method, presolve in O.ATTEMPTS:
            res = O._attempt(r["z"], m, True, True, "margin", 0.0, method, presolve, d)
            if res is not None and res.status == 0:
                break
    if res is None or res.status != 0:
        return {**_key(row), "span": None}
    y = np.abs(np.asarray(res.ineqlin.marginals))
    meas = y[: 2 * m].reshape(m, 2).sum(axis=1)
    used = np.flatnonzero(meas > 1e-9 * max(1.0, meas.max()))
    return {**_key(row), "t_star": t, "t_f": row["t_f"], "d_star": float(res.fun),
            "span": int(t - used.min()) if len(used) else None, "measurements_in_proof": int(len(used)),
            "earliest": int(used.min()) if len(used) else None}


def _key(row):
    return {k: row[k] for k in ("seed", "cell", "arm", "ambient")}


def main():
    d, out = Path(sys.argv[1]), Path(sys.argv[2])
    rows = [json.loads(l) for l in (d / "rows.jsonl").read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r["oracle"]["t_star"] is not None and r["cell"] != "healthy"]
    with ProcessPoolExecutor(8) as pool:
        res = list(pool.map(job, rows))
    by = {}
    for x in res:
        if x["span"] is None:
            continue
        by.setdefault(x["cell"], []).append(x["span"])
    summary = {c: {"n": len(v), "median": float(np.median(v)), "p90": float(np.percentile(v, 90)), "max": int(max(v))}
               for c, v in sorted(by.items())}
    out.write_text(json.dumps({"summary": summary, "rows": res}, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
