"""BASELINE2-PLAN.md: the strengthened baselines B1s and B4s (baselines_strong.py). Reuses baselines_run.py's DEV
grid, scoring and tuning rule with its own grid and plan; the block runs only the chosen configurations.
  python -B baselines2_run.py dev OUT [--workers 14]           the grid on the 1400 DEV rows (resumable)
  python -B baselines2_run.py tune OUT                         the tuning rule -> OUT/chosen.json
  python -B baselines2_run.py block OUT --chosen FILE [--workers 14]   refused unless BASELINE2-PLAN.md says FROZEN
  python -B baselines2_run.py score OUT                        measures and hypotheses (plan section 5)
"""
import argparse, gzip, hashlib, json, random, sys, time, warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import baselines_run as R  # noqa: E402
import baselines_strong  # noqa: E402,F401  (registers B1s, B4s)
BL, S, T, G = R.BL, R.S, R.T, R.G
PLAN = HERE.parent / "BASELINE2-PLAN.md"
MAN = R.ROOT / "experiments/v3/frozen/MANIFEST-V3.json"
VAL3 = R.ROOT / "results/v3/freeze3/validation-440400-440599-948b46b0/rows.jsonl"
BLOCK1 = R.ROOT / "results/v3/baselines/block-9438dffa/rows.jsonl.gz"
R.GRID = {
    "B1s": [{"n_c": n, "order": o, "policy": "fifo", "prior": "box+err"} for n, o in ((2, 1), (1, 2), (3, 1))]
           + [{"n_c": n, "order": o, "policy": "fifo", "prior": "box+err"} for n in (4, 16, 64) for o in (2, 8)],
    "B4s": [{"L": [a * float(BL.MX[0, 1]), b * float(BL.MX[1, 1]), c]} for a in (0.0, 0.5, 1.0)
            for b in (0.0, 0.25, 0.5, 0.75, 1.0) for c in (0.0, -0.01, -0.05)],
}
R.PLAN = PLAN


def block_job(args):
    r, ids, unlock = args
    warnings.filterwarnings("ignore")
    S.unlock_validation(unlock)
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    zs = G.zs_of(run)
    return {"key": R.key(r)} | {i: R.run_one(i, run, zs, r["oracle"]["t_star"]) for i in ids}


def block(out, chosen_path, workers):
    plan = PLAN.read_text()
    csha = hashlib.sha256(chosen_path.read_bytes()).hexdigest()
    if not any(l.startswith("Status: FROZEN") for l in plan.splitlines()) or csha not in plan:
        raise SystemExit("BASELINE2-PLAN.md is not FROZEN with this chosen.json: the block is not run")
    chosen = json.loads(chosen_path.read_text())
    ids = []
    for i in chosen.values():
        if i is None:
            raise SystemExit("a chosen configuration is missing")
        if i not in ids:
            ids.append(i)
    rows = [json.loads(l) for l in VAL3.read_text().splitlines() if l.strip()]
    out.mkdir(parents=True, exist_ok=False)
    head, dirty = R.git_state()
    (out / "meta.json").write_text(json.dumps({"stage": "block2", "git_head": head, "git_dirty_tracked": dirty,
        "chosen": chosen, "chosen_sha256": csha, "rows": len(rows), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
        indent=1) + "\n")
    unlock = hashlib.sha256(MAN.read_bytes()).hexdigest()
    with ProcessPoolExecutor(workers) as pool, (out / "rows.jsonl").open("x") as f:
        futs = [pool.submit(block_job, (r, ids, unlock)) for r in rows]
        for n, fut in enumerate(as_completed(futs), 1):
            f.write(json.dumps(fut.result(), sort_keys=True) + "\n")
            if n % 200 == 0:
                f.flush(); print(f"{n}/{len(rows)} {time.strftime('%H:%M:%S')}", flush=True)
    meta = json.loads((out / "meta.json").read_text()); meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


def score(out):
    """plan section 5: per chosen configuration, against IM (v2) on validation 3's paired events; the hypotheses by a
    seed bootstrap (2,000 draws over the 200 seeds, random.Random(20261123)) of paired-lag differences"""
    val = {R.key(r): r for r in map(json.loads, VAL3.read_text().splitlines()) if r}
    new = {j["key"]: j for j in map(json.loads, (out / "rows.jsonl").read_text().splitlines()) if j}
    old = {j["key"]: j for j in map(json.loads, gzip.decompress(BLOCK1.read_bytes()).decode().splitlines()) if j}
    chosen = json.loads((out / "meta.json").read_text())["chosen"]
    assert set(new) == set(val)
    ev = [k for k, r in val.items() if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is not None]
    paired = [k for k in ev if val[k]["v2"] is not None]
    adm = [k for k, r in val.items() if r["cell"] == "healthy" or (r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is None)]
    ts = lambda k: val[k]["oracle"]["t_star"]
    lag = lambda d, k: (T.N if d is None else d) - ts(k)
    det = {"IM": {k: val[k]["v2"] for k in val}, "WM": {k: val[k]["F3"]["detect"] for k in val}}
    for i in dict.fromkeys(chosen.values()):
        det[i] = {k: new[k][i]["detect"] for k in val}
    det["TS"] = {k: old[k]["cyl16p"]["detect"] for k in val}
    for i in (k for k in next(iter(old.values())) if k.startswith(("B1:", "B4:"))):
        det["first block " + i] = {k: old[k][i]["detect"] for k in val}
    LIM = sum(lag(det["IM"][k], k) for k in paired)
    table = {}
    for name, d in det.items():
        L = sum(lag(d[k], k) for k in paired)
        table[name] = {"paired_lag": L, "D_paired": 1 - L / LIM, "misses": sum(d[k] is None for k in ev),
                       "at_t_star": sum(d[k] == ts(k) for k in ev),
                       "admissible_alarms": [k for k in adm if d[k] is not None],
                       "early": [k for k in ev if d[k] is not None and d[k] < ts(k)]}
    seeds = sorted({val[k]["seed"] for k in paired})
    by_seed = {s: [k for k in paired if val[k]["seed"] == s] for s in seeds}
    def boot(a, b):
        diff = {s: sum(lag(det[a][k], k) - lag(det[b][k], k) for k in by_seed[s]) for s in seeds}
        rng, draws = random.Random(20261123), []
        for _ in range(2000):
            draws.append(sum(diff[rng.choice(seeds)] for _ in seeds))
        draws.sort()
        return {"point": sum(diff.values()), "ci95": [draws[49], draws[1949]],
                "supported": draws[1949] < 0}
    hyp = {}
    if "B1s@M2" in chosen:
        hyp["H-S1 WM < B1s@M2"] = boot("WM", chosen["B1s@M2"])
    if True:
        for b in ("B1s@M1", "B4s@M1"):
            if chosen.get(b):
                hyp[f"H-S2 TS < {b}"] = boot("TS", chosen[b])
    res = {"chosen": chosen, "table": table, "hypotheses": hyp}
    (out / "scores.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print(json.dumps(res, indent=1, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("dev", "tune", "block", "score"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--chosen", type=Path)
    ap.add_argument("--subset", type=int)
    a = ap.parse_args()
    if a.cmd == "dev":
        R.dev(a.out, a.workers, None, a.subset)
    elif a.cmd == "tune":
        R.tune(a.out)
    elif a.cmd == "block":
        block(a.out, a.chosen, a.workers)
    else:
        score(a.out)


if __name__ == "__main__":
    main()
