"""C1-USED-BLOCKS-PLAN.md: c1 against freeze 1's C state (both float64, PC host_trace) on the 19,200 runs of
validations 1 and 3 (used blocks: no new seeds, no oracle runs).

Per run: the first flagged sample of each build. Checks U1-U5 of the plan; c1 against the Python template, and c1's
paired lag, D_paired and misses per block, reported.
usage: python -B c1_val_compare.py OLD_HOST_TRACE NEW_HOST_TRACE OUT_DIR [--workers 14]
"""
import argparse
import gzip
import hashlib
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(HERE.parent / "avr")]
import stream as ST  # noqa: E402

S, T = ST.S, ST.S.T
OLD_SHA = "aa581fb2d783409352cbeec59409e27f656a9a9cc90d667954b40b66103d89cf"
NEW_SHA = "5d4fddeea11b3aa842e4101d16e843bf7a730443b99158ad3022ce12d9afff95"
BLOCKS = {
    "validation1": (ROOT / "results/v3/freeze1/validation-440000-440199/rows.jsonl", ROOT / "experiments/v3/frozen/MANIFEST.json"),
    "validation3": (ROOT / "results/v3/freeze3/validation-440400-440599-948b46b0/rows.jsonl",
                    ROOT / "experiments/v3/frozen/MANIFEST-V3.json"),
}
PY3 = ROOT / "results/v3/baselines/block-9438dffa/rows.jsonl.gz"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def key(r):
    return f"{r['seed']}-{r['cell']}-{r['arm']}-{r['ambient']}-{r['noise']}"


def first(obs):
    return next((k for k, (f, _d) in enumerate(obs) if f), None)


def job(args):
    old, new, man_sha, block, k = args
    S.unlock_validation(man_sha)
    seed, cell_name, arm, al, nl = k
    r = S.run(seed, next(c for c in T.CELLS if c.name == cell_name), arm, al, nl)
    _oi, oo = ST.host_dumps(old, r["y"], r["P"])
    _ni, no = ST.host_dumps(new, r["y"], r["P"])
    return {"block": block, "key": list(k), "old_first": first(oo), "new_first": first(no), "samples": len(no)}


def score(block, rows, recs, python):
    by = {key(r): r for r in rows}
    N = T.N
    out = {"runs": len(recs), "expected": len(rows), "complete": len(recs) == len(rows) == 9600
           and all(x["samples"] == N for x in recs)}
    kk = lambda x: "-".join(str(v) for v in x["key"])
    out["c1_earlier"] = [x["key"] for x in recs if x["new_first"] is not None
                         and (x["old_first"] is None or x["new_first"] < x["old_first"])]
    out["first_differs"] = [[x["key"], x["old_first"], x["new_first"]] for x in recs if x["old_first"] != x["new_first"]]
    if block == "validation1":
        out["frozen_vs_recorded_c_differs"] = [[x["key"], x["old_first"], by[kk(x)]["c"]["cyl16p_double"]] for x in recs
                                               if x["old_first"] != by[kk(x)]["c"]["cyl16p_double"]]
    adm = lambda r: r["cell"] == "healthy" or (r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is None)
    out["c1_admissible_alarms"] = [x["key"] for x in recs if adm(by[kk(x)]) and x["new_first"] is not None]
    out["c1_vs_python_differs"] = [[x["key"], x["new_first"], python[kk(x)]] for x in recs if x["new_first"] != python[kk(x)]]
    ev = [x for x in recs if by[kk(x)]["oracle"]["status"] == "certified" and by[kk(x)]["oracle"]["t_star"] is not None]
    paired = [x for x in ev if by[kk(x)]["v2"] is not None]
    ts = lambda x: by[kk(x)]["oracle"]["t_star"]
    lag_im = sum(by[kk(x)]["v2"] - ts(x) for x in paired)
    lag = sum((N if x["new_first"] is None else x["new_first"]) - ts(x) for x in paired)
    out |= {"events": len(ev), "paired": len(paired), "IM_paired_lag": lag_im, "c1_paired_lag": lag,
            "c1_D_paired": 1 - lag / lag_im, "c1_misses": sum(x["new_first"] is None for x in ev)}
    out["U_hold"] = {"U1": out["complete"], "U2": not out["c1_earlier"], "U3": not out["first_differs"],
                     "U4": (not out["frozen_vs_recorded_c_differs"]) if block == "validation1" else None,
                     "U5": not out["c1_admissible_alarms"]}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("old", type=Path)
    ap.add_argument("new", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=14)
    a = ap.parse_args()
    if sha(a.old) != OLD_SHA or sha(a.new) != NEW_SHA:
        raise SystemExit("host_trace binaries are not the plan's")
    a.out.mkdir(parents=True, exist_ok=False)
    blocks = {b: ([json.loads(l) for l in p.read_text().splitlines() if l.strip()], sha(m)) for b, (p, m) in BLOCKS.items()}
    py3 = {j["key"]: j["cyl16p"]["detect"] for j in map(json.loads, gzip.open(PY3, "rt"))}
    python = {"validation1": {key(r): r["candidates"]["cyl16p"] for r in blocks["validation1"][0]}, "validation3": py3}
    tasks = [(str(a.old), str(a.new), msha, b, (r["seed"], r["cell"], r["arm"], r["ambient"], r["noise"]))
             for b, (rows, msha) in blocks.items() for r in rows]
    t0 = time.monotonic()
    with ProcessPoolExecutor(a.workers) as pool:
        recs = list(pool.map(job, tasks, chunksize=8))
    (a.out / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    res = {"old_sha256": OLD_SHA, "new_sha256": NEW_SHA, "seconds": round(time.monotonic() - t0, 1)}
    for b, (rows, msha) in blocks.items():
        res[b] = {"manifest_sha256": msha} | score(b, rows, [x for x in recs if x["block"] == b], python[b])
    us = [v for b in BLOCKS for v in res[b]["U_hold"].values() if v is not None]
    res["verdict"] = "SAME ALARMS" if all(us) else ("INCOMPLETE" if not all(res[b]["U_hold"]["U1"] for b in BLOCKS)
                                                     else "DIFFERENT")
    (a.out / "score.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: v for k, v in res.items()}, indent=1)[:6000])


if __name__ == "__main__":
    main()
