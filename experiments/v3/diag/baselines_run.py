"""BASELINE-PLAN.md: the DEV tuning grid, the choice of configurations, and (after the freeze) the block run.

  python -B baselines_run.py dev OUT [--workers 10] [--only B2,B3]      the grid on the 1400 DEV rows (resumable)
  python -B baselines_run.py tune OUT                                   the tuning rule -> OUT/chosen.json
  python -B baselines_run.py block OUT --chosen FILE [--workers 10]     refused unless the plan says FROZEN

DEV rows: the 1320 comparison rows of results/v3/dev-45cff1d (oracle t*, status and v2 recorded there) and the 80
edge-noise healthy rows of DIAG-3 amendment 7 (admissible by construction). One JSON line per (row, method,
configuration) in OUT/rows.jsonl.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE)]
import baselines as BL  # noqa: E402
import baselines_cz  # noqa: E402,F401  (registers B1)

S, T, G = BL.S, BL.T, BL.G
ROOT = G.ROOT
PLAN = HERE.parent / "BASELINE-PLAN.md"
DEV_ROWS = ROOT / "results/v3/dev-45cff1d/rows.jsonl"

# the grid of BASELINE-PLAN.md section 3 (B1 reduced to what the DEV budget allows; see the plan)
GRID = {
    "B1": [{"n_c": n, "order": o, "policy": "fifo", "prior": p} for n, o in ((2, 1), (1, 2), (3, 1))
           for p in ("box", "box+err")]                                     # within M1 (<= 42 reals)
          + [{"n_c": n, "order": o, "policy": "fifo", "prior": p} for n in (4, 16, 64) for o in (2, 8)
             for p in ("box", "box+err")]
          + [{"n_c": 8, "order": 4, "policy": "greedy", "prior": "box+err"}],
    # Scott's LP rescaling costs 15-20 times more: run on a fixed 200-row DEV subset (--subset 200), reported only
    "B1lp": [{"n_c": 8, "order": 4, "policy": "fifo", "prior": "box+err", "rescale": "lp"}],
    "B2": [{"order": o, "prior": p} for o in (2, 4, 8, 16, 32) for p in ("box", "box+err")],
    "B3": [{"q": q, "order": o, "prior": p} for q in (1e-2, 1.0, 1e2, 1e4) for o in (2, 4, 8, 16, 32)
           for p in ("box", "box+err")],
    "B4": [{"L": [a * float(BL.MX[0, 1]), b * float(BL.MX[1, 1]), c]} for a in (0.0, 0.5, 1.0)
           for b in (0.0, 0.25, 0.5, 0.75, 1.0) for c in (0.0, -0.01, -0.05)],
}


def cfg_id(method, cfg):
    return method + ":" + json.dumps(cfg, sort_keys=True)


def key(r):
    return f"{r['seed']}-{r['cell']}-{r['arm']}-{r['ambient']}-{r['noise']}"


def dev_rows():
    rows = [json.loads(l) for l in DEV_ROWS.read_text().splitlines() if l.strip()]
    rows = [{k: r[k] for k in ("seed", "cell", "arm", "ambient", "noise")} | {"t_star": r["oracle"]["t_star"],
            "status": r["oracle"]["status"], "v2": r["v2"]} for r in rows]
    rows += [{"seed": s, "cell": "healthy", "arm": a, "ambient": al, "noise": "edge", "t_star": None,
              "status": "healthy", "v2": None} for s in range(430070, 430090) for a in T.ARMS for al in ("rw", "ramp")]
    assert len(rows) == 1400 and len({key(r) for r in rows}) == 1400
    assert all(r["seed"] in S.DEV for r in rows)
    return rows


def job(args):
    r, todo = args
    warnings.filterwarnings("ignore")
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    zs = G.zs_of(run)
    out = []
    for method, cfg in todo:
        m = BL.METHODS["B1" if method == "B1lp" else method](cfg)
        det, sec, _ = BL.run_set_method(m, zs)
        out.append({"key": key(r), "id": cfg_id(method, cfg), "method": method, "cfg": cfg, "detect": det,
                    "seconds": round(sec, 3), "memory": m.memory(),
                    "n_lp": getattr(m, "n_lp", 0), "lp_fail": getattr(m, "lp_fail", 0)})
    return out


def git_state():
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=HERE, capture_output=True,
                           text=True).stdout.strip()
    return head, bool(dirty)


def dev(out, workers, only, subset=None):
    out.mkdir(parents=True, exist_ok=True)
    path = out / "rows.jsonl"
    done = set()
    if path.exists():
        done = {(j["key"], j["id"]) for j in map(json.loads, path.read_text().splitlines()) if j}
    head, dirty = git_state()
    if not (out / "meta.json").exists():
        (out / "meta.json").write_text(json.dumps({"stage": "dev", "git_head": head, "git_dirty_tracked": dirty,
            "grid": GRID, "machine": platform.machine(), "platform": platform.platform(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=1) + "\n")
    methods = [m for m in GRID if (only is None and m != "B1lp") or (only is not None and m in only)]
    rows = dev_rows()
    if subset:
        rows = sorted(rows, key=lambda r: hashlib.sha256(key(r).encode()).hexdigest())[:subset]
    jobs = []
    for r in rows:
        todo = [(m, c) for m in methods for c in GRID[m] if (key(r), cfg_id(m, c)) not in done]
        if todo:
            jobs.append((r, todo))
    print(f"rows with work: {len(jobs)}", flush=True)
    with ProcessPoolExecutor(workers) as pool, path.open("a") as f:
        for n, fut in enumerate(as_completed([pool.submit(job, j) for j in jobs]), 1):
            for rec in fut.result():
                f.write(json.dumps(rec) + "\n")
            f.flush()
            if n % 50 == 0:
                print(f"{n}/{len(jobs)} rows {time.strftime('%H:%M:%S')}", flush=True)
    meta = json.loads((out / "meta.json").read_text())
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


def score(recs, rows):
    """paired lag against v2, misses, soundness findings; per configuration, over the rows it was run on: all 1400,
    or the 200-row subset of B1lp (`complete` says which; the tuning rule takes complete configurations only)"""
    det = {rec["key"]: rec["detect"] for rec in recs}
    by = {key(r): r for r in rows}
    assert set(det) <= set(by) and len(det) == len(recs)
    complete = set(det) == set(by)
    by = {k: r for k, r in by.items() if k in det}
    events = [k for k, r in by.items() if r["status"] == "certified" and r["t_star"] is not None]
    paired = [k for k in events if by[k]["v2"] is not None]
    admissible = [k for k, r in by.items() if r["cell"] == "healthy" or (r["status"] == "certified" and r["t_star"] is None)]
    Lv2 = sum(by[k]["v2"] - by[k]["t_star"] for k in paired)
    lag = sum((T.N if det[k] is None else det[k]) - by[k]["t_star"] for k in paired)
    return {"rows": len(det), "complete": complete, "events": len(events), "paired": len(paired),
            "paired_lag": lag, "v2_paired_lag": Lv2, "D_paired": 1 - lag / Lv2 if Lv2 else None,
            "misses": sum(det[k] is None for k in events),
            "admissible_alarms": [k for k in admissible if det[k] is not None],
            "early": [k for k in events if det[k] is not None and det[k] < by[k]["t_star"]],
            "memory": max(rec["memory"] for rec in recs), "seconds": round(sum(rec["seconds"] for rec in recs), 1),
            "lp_fail": sum(rec["lp_fail"] for rec in recs)}


def tune(out):
    rows = dev_rows()
    recs = {}
    for j in map(json.loads, (out / "rows.jsonl").read_text().splitlines()):
        recs.setdefault(j["id"], []).append(j)
    table = {i: score(v, rows) for i, v in recs.items()}
    chosen = {}
    for method in (m for m in GRID if m != "B1lp"):
        for budget, limit in (("M1", 42), ("M2", None)):
            ok = [(t["paired_lag"], i) for i, t in table.items() if i.startswith(method + ":") and t["complete"]
                  and not t["admissible_alarms"] and not t["early"] and (limit is None or t["memory"] <= limit)]
            chosen[f"{method}@{budget}"] = min(ok)[1] if ok else None
    head, dirty = git_state()
    (out / "tune.json").write_text(json.dumps({"git_head": head, "git_dirty_tracked": dirty, "table": table,
                                               "chosen": chosen}, indent=1, default=str) + "\n")
    (out / "chosen.json").write_text(json.dumps(chosen, indent=1) + "\n")
    print(json.dumps(chosen, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("dev", "tune", "block"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--only")
    ap.add_argument("--subset", type=int, help="only the N DEV rows with the smallest sha256 keys")
    ap.add_argument("--chosen", type=Path)
    a = ap.parse_args()
    if a.cmd == "dev":
        dev(a.out, a.workers, set(a.only.split(",")) if a.only else None, a.subset)
    elif a.cmd == "tune":
        tune(a.out)
    else:
        if "Status: FROZEN" not in PLAN.read_text():
            raise SystemExit("BASELINE-PLAN.md is not FROZEN: the block is not run")
        raise SystemExit("the block runner is written after the freeze")


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
