"""DIAG-1 run selection (amendment 1): cyl16p's lag behind the oracle on the DEV evaluation rows of the three cells.

Rows: results/v3/dev-45cff1d/rows.jsonl (run_dev.py, DEV 430000-430029), cells drift_0.002/rw, drift_0.001/ramp,
drift_0.0005/ramp, arms E0 and E1, uniform noise, certified oracle t*. For each, the frozen cyl16p and inv4p first
inconsistent sample. Writes the table; the rule that picks from it is in DIAG-1-PLAN.md, amendment 1.
usage: python -B select_runs.py OUT_JSON [--workers 10]
"""
import argparse
import json
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
V3 = HERE.parent
ROOT = V3.parents[1]
sys.path[:0] = [str(V3), str(V3.parent / "generators")]
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402

CELLS = (("drift_0.002", "rw"), ("drift_0.001", "ramp"), ("drift_0.0005", "ramp"))
TP = None


def _init():
    global TP
    TP = {n: V.load_frozen(V3 / "frozen" / f"{n}.json") for n in ("cyl16p", "inv4p")}


def _job(r):
    cell = next(c for c in V.T.CELLS if c.name == r["cell"])
    run = S.run(r["seed"], cell, r["arm"], r["ambient"], r["noise"])
    return {n: V.first_inconsistent(tp, run["y"], run["P"]) for n, tp in TP.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=10)
    a = ap.parse_args()
    rows = [json.loads(l) for l in (ROOT / "results/v3/dev-45cff1d/rows.jsonl").read_text().splitlines() if l.strip()]
    rows = [r for r in rows if (r["cell"], r["ambient"]) in CELLS and r["noise"] == "uniform"
            and r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is not None]
    with ProcessPoolExecutor(a.workers, initializer=_init) as pool:
        firsts = list(pool.map(_job, rows, chunksize=2))
    out = []
    for r, f in zip(rows, firsts):
        t = r["oracle"]["t_star"]
        lag = lambda x: None if x is None else x - t
        out.append({"seed": r["seed"], "cell": r["cell"], "ambient": r["ambient"], "arm": r["arm"], "t_star": t,
                    "v2": r["v2"], "inv4p": f["inv4p"], "cyl16p": f["cyl16p"], "lag_v2": lag(r["v2"]),
                    "lag_inv4p": lag(f["inv4p"]), "lag_cyl16p": lag(f["cyl16p"])})
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    for cell, amb in CELLS:
        rs = sorted((x for x in out if x["cell"] == cell and x["ambient"] == amb),
                    key=lambda x: (-(x["lag_cyl16p"] if x["lag_cyl16p"] is not None else 10**9), x["seed"], x["arm"]))
        print(cell, amb, [(x["seed"], x["arm"], x["lag_cyl16p"], x["lag_v2"]) for x in rs[:5]])


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
