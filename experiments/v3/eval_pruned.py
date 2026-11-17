"""Flash budget: prune the basis tables on a DEV selection set, evaluate on the run_dev seeds against the oracle.

Selection: DEV 430050-430069 (all cells/arms/laws below). Evaluation: the run_dev.py rows (DEV 430000-430029),
whose certified oracle t* are reused. Same decision as everywhere: first sample with no explanation at b = 0.
usage: python -B eval_pruned.py RUN_DEV_DIR
"""
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
SEL_SEEDS = range(430050, 430070)
SEL_CELLS = ("healthy", "jump_0.2", "jump_0.5", "drift_0.0005", "drift_0.001", "drift_0.002", "drift_0.005", "noise_x2",
             "stuck", "gain_0.01")


TP = None


def _init(tp):
    global TP
    TP = tp


def _first(r):
    run = S.run(r["seed"], CELL[r["cell"]], r["arm"], r["ambient"], r["noise"])
    return V.first_inconsistent(TP, run["y"], run["P"])


def main():
    d = Path(sys.argv[1])
    rows = [json.loads(l) for l in (d / "rows.jsonl").read_text().splitlines() if l.strip()]
    sel = [(r["y"], r["P"]) for s in SEL_SEEDS for c in SEL_CELLS for arm in T.ARMS for al in ("rw", "ramp")
           for r in [S.run(s, CELL[c], arm, al, "uniform")]]
    results = {}
    for kind, kw in (("inv", {"N": 4}), ("inv", {"N": 8})):
        full = V.Template(V.directions(kind, **kw), invariant=True)
        counts = V.usage(full, sel)
        variants = {f"{kind}{kw['N']} full": full}
        for top in (None, 3, 2, 1):
            variants[f"{kind}{kw['N']} pruned top={top or 'used'}"] = V.pruned(full, counts, keep_top=top)
        for name, tp in variants.items():
            stat, lags = Counter(), []
            with ProcessPoolExecutor(7, initializer=_init, initargs=(tp,)) as pool:
                firsts = list(pool.map(_first, rows, chunksize=8))
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
            results[name] = {"entries": tp.table_entries, "flash_bytes_float32": tp.table_entries * 15 + tp.n * 12,
                             "state_numbers": tp.n, **stat, "lag_sum": sum(lags),
                             "lag_p90": lags[int(0.9 * (len(lags) - 1))] if lags else None, "lag_max": lags[-1] if lags else None}
            print(name, json.dumps(results[name]))
    (d / "pruning.json").write_text(json.dumps({"selection_seeds": [SEL_SEEDS[0], SEL_SEEDS[-1]], "results": results}, indent=1) + "\n")


if __name__ == "__main__":
    main()
