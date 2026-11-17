"""Evaluate further template families on the run_dev rows (DEV 430000-430029) against the certified oracle t*.
Same decision and metrics as analyze_dev.py. usage: python -B eval_templates.py RUN_DEV_DIR OUT_JSON"""
import json
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "generators")]
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402

T = V.T
CELL = {c.name: c for c in T.CELLS}
SPECS = [("cyl8", "cyl", {"N": 4, "L": 8}), ("cyl16", "cyl", {"N": 4, "L": 16}), ("cyl24", "cyl", {"N": 4, "L": 24}),
         ("window8", "window", {"N": 4, "L": 8}), ("sphere30", "sphere", {"N": 30})]
TP = None


def _init(spec):
    global TP
    _, kind, kw = spec
    TP = V.Template(V.directions(kind, **kw), invariant=True)


def _first(r):
    run = S.run(r["seed"], CELL[r["cell"]], r["arm"], r["ambient"], r["noise"])
    return V.first_inconsistent(TP, run["y"], run["P"])


def main():
    d, out = Path(sys.argv[1]), Path(sys.argv[2])
    rows = [json.loads(l) for l in (d / "rows.jsonl").read_text().splitlines() if l.strip()]
    results = {}
    for spec in SPECS:
        tp = V.Template(V.directions(spec[1], **spec[2]), invariant=True)
        with ProcessPoolExecutor(8, initializer=_init, initargs=(spec,)) as pool:
            firsts = list(pool.map(_first, rows, chunksize=4))
        stat, lags = Counter(), []
        for r, f in zip(rows, firsts):
            t = r["oracle"]["t_star"]
            if r["cell"] == "healthy" or t is None:
                stat["unsound"] += f is not None
                continue
            if f is None:
                stat["miss"] += 1
            elif f < t:
                stat["unsound"] += 1
            else:
                lags.append(f - t)
                stat["equal"] += f == t
        lags.sort()
        results[spec[0]] = {"state_numbers": tp.n, "entries": tp.table_entries, **tp.cost(), **stat, "lag_sum": sum(lags),
                            "lag_p90": lags[int(0.9 * (len(lags) - 1))], "lag_max": lags[-1],
                            "firsts": firsts}
        print(spec[0], json.dumps({k: v for k, v in results[spec[0]].items() if k != "firsts"}), flush=True)
    out.write_text(json.dumps(results) + "\n")


if __name__ == "__main__":
    main()
