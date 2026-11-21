"""BASELINE-PLAN.md: the DEV tuning grid, the choice of configurations, and (after the freeze) the block run.

  python -B baselines_run.py dev OUT [--workers 10] [--only B2,B3]      the grid on the 1400 DEV rows (resumable)
  python -B baselines_run.py tune OUT                                   the tuning rule -> OUT/chosen.json
  python -B baselines_run.py unit OUT --chosen FILE                     DEV checks before the block (plan, step 1)
  python -B baselines_run.py block OUT --chosen FILE [--workers 14]     refused unless the plan says FROZEN
  python -B baselines_run.py score OUT                                  the block's measures and hypotheses

DEV rows: the 1320 comparison rows of results/v3/dev-45cff1d (oracle t*, status and v2 recorded there) and the 80
edge-noise healthy rows of DIAG-3 amendment 7 (admissible by construction). One JSON line per (row, method,
configuration) in OUT/rows.jsonl.
"""
import argparse
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import baselines as BL  # noqa: E402
import baselines_cz  # noqa: E402,F401  (registers B1)

S, T, G = BL.S, BL.T, BL.G
N = T.N
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



# ---- the block (BASELINE-PLAN.md sections 1, 5, 6; written after the DEV tuning, before the freeze) ----------------
BLOCK_ROWS = ROOT / "results/v3/freeze3/validation-440400-440599-948b46b0/rows.jsonl"
MANIFEST = HERE.parent / "frozen" / "MANIFEST-V3.json"
BOOT_REPS, BOOT_SEED = 2000, 20261121


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def chosen_methods(chosen):
    """the distinct chosen configurations, B5 (F3 with the fold off) and cyl16p"""
    ids = []
    for i in chosen.values():
        if i is None:
            raise SystemExit("a chosen configuration is missing")
        if i not in ids:
            ids.append(i)
    return ids + ["B5", "cyl16p"]


def run_one(i, run, zs, t_star):
    if i == "cyl16p":
        det, sec = BL.run_cyl16p(run["y"], run["P"])
        return {"detect": det, "seconds": round(sec, 3), "memory": 42}
    if i == "B5":
        t0 = time.monotonic()
        f = BL.run_b5(zs, t_star)
        keep = ("detect", "alarm_certificate", "evictions", "unproved_primal_alarms", "max_kept", "n_lp", "n_retry",
                "steps", "failsafe")
        return {k: f.get(k) for k in keep} | {"seconds": round(time.monotonic() - t0, 3)}
    meth, cfg = i.split(":", 1)
    m = BL.METHODS[meth](json.loads(cfg))
    det, sec, _ = BL.run_set_method(m, zs)
    return {"detect": det, "seconds": round(sec, 3), "memory": m.memory(), "n_lp": getattr(m, "n_lp", 0),
            "lp_fail": getattr(m, "lp_fail", 0)}


def block_job(args):
    r, ids, unlock = args
    warnings.filterwarnings("ignore")
    S.unlock_validation(unlock)
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    zs = G.zs_of(run)
    return {"key": key(r)} | {i: run_one(i, run, zs, r["oracle"]["t_star"]) for i in ids}


def block_rows():
    rows = [json.loads(l) for l in BLOCK_ROWS.read_text().splitlines() if l.strip()]
    assert len(rows) == 9600 and len({key(r) for r in rows}) == 9600
    assert {r["seed"] for r in rows} == set(range(440400, 440600))
    return rows


def identity_rows(rows):
    """one run per design cell (cell, arm, ambient, noise): the smallest sha256 key (plan section 1)"""
    best = {}
    for r in rows:
        c = (r["cell"], r["arm"], r["ambient"], r["noise"])
        h = hashlib.sha256(key(r).encode()).hexdigest()
        if c not in best or h < best[c][0]:
            best[c] = (h, r)
    return [r for _, r in sorted(best.values(), key=lambda x: x[0])]


def identity_job(args):
    r, unlock = args
    S.unlock_validation(unlock)
    import run_validation as RV1
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    return key(r), RV1.v2_first(run["y"], run["P"]), r["v2"]


def check_frozen(chosen_path):
    plan = PLAN.read_text()
    if "Status: FROZEN" not in plan:
        raise SystemExit("BASELINE-PLAN.md is not FROZEN: the block is not run")
    if f"Chosen sha256: {sha256(chosen_path)}" not in plan:
        raise SystemExit("BASELINE-PLAN.md does not quote this chosen.json's sha256")
    if f"Block rows sha256: {sha256(BLOCK_ROWS)}" not in plan:
        raise SystemExit("BASELINE-PLAN.md does not quote the block rows' sha256")


def block(out, chosen_path, workers):
    check_frozen(chosen_path)
    head, dirty = git_state()
    if dirty:
        raise SystemExit("the working tree has tracked changes: commit first")
    unlock = sha256(MANIFEST)
    chosen = json.loads(chosen_path.read_text())
    ids = chosen_methods(chosen)
    rows = block_rows()
    out.mkdir(parents=True, exist_ok=True)
    if not (out / "meta.json").exists():
        (out / "meta.json").write_text(json.dumps({"stage": "block", "git_head": head, "git_dirty_tracked": dirty,
            "chosen": chosen, "chosen_sha256": sha256(chosen_path), "methods": ids,
            "block_rows_sha256": sha256(BLOCK_ROWS), "manifest_sha256": unlock, "workers": workers,
            "machine": platform.machine(), "platform": platform.platform(), "host": platform.node(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=1) + "\n")
    idp = out / "identity.json"
    if not idp.exists():
        with ProcessPoolExecutor(workers) as pool:
            res = list(pool.map(identity_job, [(r, unlock) for r in identity_rows(rows)]))
        ok = all(a == b for _, a, b in res)
        idp.write_text(json.dumps({"rows": len(res), "equal": ok, "runs": res}, indent=1) + "\n")
        print(f"identity: {len(res)} runs, v2 equal to the record: {ok}", flush=True)
    if not json.loads(idp.read_text())["equal"]:
        raise SystemExit("identity check failed: nothing is run")
    path = out / "rows.jsonl"
    done = {json.loads(l)["key"] for l in path.read_text().splitlines() if l.strip()} if path.exists() else set()
    jobs = [(r, ids, unlock) for r in rows if key(r) not in done]
    print(f"rows to run: {len(jobs)}", flush=True)
    with ProcessPoolExecutor(workers) as pool, path.open("a") as f:
        for n, fut in enumerate(as_completed([pool.submit(block_job, j) for j in jobs]), 1):
            f.write(json.dumps(fut.result()) + "\n")
            f.flush()
            if n % 100 == 0:
                print(f"{n}/{len(jobs)} rows {time.strftime('%H:%M:%S')}", flush=True)
    meta = json.loads((out / "meta.json").read_text())
    meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


def unit(out, chosen_path):
    """the plan's step-1 checks, on DEV: each chosen set method contains the true state on healthy runs (B1-B4,
    every sample); B5 equals F3 while no fold has happened (horizon W)"""
    chosen = json.loads(chosen_path.read_text())
    ids = [i for i in chosen_methods(chosen) if i not in ("B5", "cyl16p")]
    rep = {"containment": {}, "b5_equals_f3_before_any_fold": []}
    runs = [(s, a, al) for s in (430000, 430001, 430002) for a in T.ARMS for al in ("rw", "ramp")]
    healthy = next(c for c in T.CELLS if c.name == "healthy")
    for i in ids:
        meth, cfg = i.split(":", 1)
        bad = []
        for s, a, al in runs:
            run = S.run(s, healthy, a, al, "uniform")
            m = BL.METHODS[meth](json.loads(cfg))
            det, _, outside = BL.run_set_method(m, G.zs_of(run), truth=BL.truth_of(run))
            bad.append({"run": f"{s}-{a}-{al}", "detect": det, "truth_outside": len(outside)})
        rep["containment"][i] = bad
    for s, a, al in runs[:4]:
        run = S.run(s, healthy, a, al, "uniform")
        zs = G.zs_of(run)
        b5 = BL.run_b5(zs, None, BL.C.W)
        f3 = BL.CD.online("F3", zs, BL.C.W, 64, None, BL.C.W)
        rep["b5_equals_f3_before_any_fold"].append({"run": f"{s}-{a}-{al}", "detect": [b5["detect"], f3["detect"]],
                                                    "n_lp": [b5.get("n_lp"), f3.get("n_lp")]})
    out.mkdir(parents=True, exist_ok=True)
    (out / "unit.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


def boot_diff(R, a, b):
    """seed-cluster bootstrap 95 % interval of the paired-lag difference a - b (plan section 6)"""
    by = {}
    for r in R:
        by.setdefault(r["seed"], []).append(r)
    seeds = sorted(by)
    per = {s: sum(r[a] - r[b] for r in by[s]) for s in seeds}
    rng = random.Random(BOOT_SEED)
    vals = sorted(sum(per[rng.choice(seeds)] for _ in seeds) for _ in range(BOOT_REPS))
    lo, hi = vals[int(0.025 * BOOT_REPS)], vals[int(0.975 * BOOT_REPS) - 1]
    return {"point": sum(per.values()), "ci95": [lo, hi],
            "verdict": "supported" if hi < 0 else "refuted" if lo > 0 else "not resolved"}


def score_block(out):
    meta = json.loads((out / "meta.json").read_text())
    rows = {key(r): r for r in block_rows()}
    got = {j["key"]: j for j in map(json.loads, (out / "rows.jsonl").read_text().splitlines()) if j}
    assert set(got) == set(rows), "the block run is not complete"
    ids = meta["methods"] + ["F3"]
    for k, r in rows.items():
        got[k]["F3"] = {"detect": r["F3"]["detect"]}
    events = [k for k, r in rows.items() if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is not None]
    admissible = [k for k, r in rows.items() if r["cell"] == "healthy"
                  or (r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is None)]
    paired = [k for k in events if rows[k]["v2"] is not None]
    Lv2 = sum(rows[k]["v2"] - rows[k]["oracle"]["t_star"] for k in paired)

    def d(k, i):
        x = got[k][i]["detect"]
        return N if x is None else x

    rep = {"rows": len(rows), "events": len(events), "paired": len(paired), "v2_paired_lag": Lv2, "methods": {}}
    for i in ids:
        lag = sum(d(k, i) - rows[k]["oracle"]["t_star"] for k in paired)
        sec = sum(got[k][i].get("seconds", 0.0) for k in rows) if i != "F3" else None
        samples = sum(d(k, i) + 1 if got[k][i]["detect"] is not None else N for k in rows)
        rep["methods"][i] = {
            "paired_lag": lag, "D_paired": 1 - lag / Lv2,
            "misses": sum(got[k][i]["detect"] is None for k in events),
            "at_t_star": sum(got[k][i]["detect"] == rows[k]["oracle"]["t_star"] for k in events),
            "admissible_alarms": [k for k in admissible if got[k][i]["detect"] is not None],
            "early": [k for k in events if got[k][i]["detect"] is not None
                      and got[k][i]["detect"] < rows[k]["oracle"]["t_star"]],
            "memory": max((got[k][i].get("memory") or 0) for k in rows) if i not in ("B5", "F3") else None,
            "ms_per_sample": None if sec is None else round(sec / samples * 1e3, 4),
            "lp_fail": sum(got[k][i].get("lp_fail", 0) for k in rows) if i not in ("B5", "F3") else None}
        if i == "B5":
            rep["methods"][i]["uncertified_alarms"] = sum(
                1 for k in rows if got[k][i]["detect"] is not None
                and not (got[k][i].get("alarm_certificate") or {}).get("certified"))
    R = [{"seed": rows[k]["seed"]} | {i: d(k, i) for i in ids} for k in paired]
    ch = meta["chosen"]
    hyp = {f"H-B1 cyl16p vs {m}@M1": boot_diff(R, "cyl16p", ch[f"{m}@M1"]) for m in ("B1", "B2", "B3", "B4")}
    hyp["H-B2 F3 vs B5"] = boot_diff(R, "F3", "B5")
    hyp["H-B3 F3 vs B1@M2"] = boot_diff(R, "F3", ch["B1@M2"])
    rep["hypotheses"] = hyp
    (out / "scores.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps({"methods": {i: {k: v for k, v in m.items() if k not in ("admissible_alarms", "early")}
                                  | {"admissible_alarms": len(m["admissible_alarms"]), "early": len(m["early"])}
                                  for i, m in rep["methods"].items()}, "hypotheses": hyp}, indent=1))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("dev", "tune", "unit", "block", "score"))
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
    elif a.cmd == "unit":
        unit(a.out, a.chosen)
    elif a.cmd == "block":
        block(a.out, a.chosen, a.workers)
    else:
        score_block(a.out)


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
