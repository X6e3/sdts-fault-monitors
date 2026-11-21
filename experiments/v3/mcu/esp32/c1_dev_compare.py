"""C1-PLAN.md, check Y4: c1 against freeze 1's C state (both float64), side by side on MCU-2E's 1400 DEV rows (PC).

Per row: the first flagged sample of each, and the number of samples whose state dumps differ (they do, since the
slab is wider by eta). Y4 holds if c1 is never earlier, the first flagged sample is the same on every row, and no
edge-noise row flags.
usage: python -B c1_dev_compare.py OLD_HOST_TRACE NEW_HOST_TRACE OUT_DIR [--workers 4]
"""
import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "avr")]
import stream as ST  # noqa: E402
import dev_full as DF  # noqa: E402

S, T = ST.S, ST.S.T


def first(obs):
    return next((k for k, (f, _d) in enumerate(obs) if f), None)


def job(args):
    old, new, key = args
    seed, cell_name, arm, al, nl = key
    r = S.run(seed, next(c for c in T.CELLS if c.name == cell_name), arm, al, nl)
    oi, oo = ST.host_dumps(old, r["y"], r["P"])
    ni, no = ST.host_dumps(new, r["y"], r["P"])
    return {"key": list(key), "old_first": first(oo), "new_first": first(no), "samples": len(no),
            "init_differs": oi != ni, "samples_differing": sum(a != b for a, b in zip(oo, no))}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    keys = DF.rows()
    t0 = time.monotonic()
    with ProcessPoolExecutor(a.workers) as pool:
        recs = list(pool.map(job, [(str(a.old), str(a.new), k) for k in keys], chunksize=8))
    (a.out / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    earlier = [r["key"] for r in recs if r["new_first"] is not None and (r["old_first"] is None
                                                                         or r["new_first"] < r["old_first"])]
    differ = [[r["key"], r["old_first"], r["new_first"]] for r in recs if r["old_first"] != r["new_first"]]
    edge = [r["key"] for r in recs if r["key"][4] == "edge" and r["new_first"] is not None]
    s = {"rows": len(recs), "expected": len(keys), "complete": len(recs) == len(keys) and all(r["samples"] == T.N for r in recs),
         "c1_earlier": earlier, "first_differs": differ, "edge_rows_flagging": edge,
         "flagged_rows": sum(r["new_first"] is not None for r in recs),
         "rows_with_state_differences": sum(r["samples_differing"] > 0 for r in recs),
         "samples_differing": sum(r["samples_differing"] for r in recs), "init_differs_rows": sum(r["init_differs"] for r in recs),
         "seconds": round(time.monotonic() - t0, 1)}
    s["Y4_holds"] = s["complete"] and not earlier and not differ and not edge
    (a.out / "score.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
