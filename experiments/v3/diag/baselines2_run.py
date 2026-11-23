"""BASELINE2-PLAN.md: the strengthened baselines B1s and B4s (baselines_strong.py). Reuses baselines_run.py's DEV
grid runner, scoring, tuning rule and bootstrap with its own grid and plan; the block runs only the chosen
configurations, after an identity check against the first comparison's block.
  python -B baselines2_run.py dev OUT [--workers 14]                    the grid on the 1400 DEV rows (resumable)
  python -B baselines2_run.py unit OUT                                  DEV checks: B4s never later than IM, soundness
  python -B baselines2_run.py tune OUT                                  the tuning rule -> OUT/chosen.json
  python -B baselines2_run.py block OUT --chosen FILE [--workers 14]   refused unless the plan is FROZEN with FILE
  python -B baselines2_run.py score OUT                                 measures and hypotheses (plan sections 4, 5)
"""
import argparse, gzip, hashlib, json, sys, time, warnings
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
FIRST_B1 = 'B1:{"n_c": 4, "order": 8, "policy": "fifo", "prior": "box+err"}'
SHIFTS = [0.0, 1e-15, -1e-15, 2e-15]
FIRST_B4 = 'B4:{"L": [0.06666666666666667, 0.7666666666666666, -0.01]}'
R.GRID = {
    "B1s": [{"n_c": n, "order": o, "policy": p, "prior": "box+err"}
            for n, o in ((1, 2), (3, 1), (4, 8), (16, 8), (64, 8)) for p in ("fifo", "greedy")],
    "B4s": [{"L": [0.0, 0.0, 0.0]}, {"L": [0.06666666666666667, 0.7666666666666666, -0.01]},
            {"L": [float(BL.MX[0, 1]), float(BL.MX[1, 1]), -0.01]}],
}
R.PLAN = PLAN


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def first_block():
    return {j["key"]: j for j in map(json.loads, gzip.decompress(BLOCK1.read_bytes()).decode().splitlines()) if j}


def unit(out):
    """plan section 3: on the DEV grid's rows, B4s is never later than IM (v2) and no configuration flags an
    admissible row or before t*"""
    rows = {R.key(r): r for r in R.dev_rows()}
    recs = [json.loads(l) for l in (out / "rows.jsonl").read_text().splitlines() if l.strip()]
    later, findings = [], []
    for j in recs:
        r = rows[j["key"]]
        adm = r["cell"] == "healthy" or (r["status"] == "certified" and r["t_star"] is None)
        if j["detect"] is not None and (adm or (r["t_star"] is not None and j["detect"] < r["t_star"])):
            findings.append([j["id"], j["key"], j["detect"]])
        if j["method"] == "B4s" and r["v2"] is not None and (j["detect"] is None or j["detect"] > r["v2"]):
            later.append([j["id"], j["key"], j["detect"], r["v2"]])
    stab = stability(out)
    res = {"records": len(recs), "B4s_later_than_IM": later, "soundness_findings": findings, "stability": stab}
    (out / "unit.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in res.items()}))


def stab_job(args):
    r, ids = args
    warnings.filterwarnings("ignore")
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    zs = G.zs_of(run)
    out = {}
    for i in ids:
        meth, cfg = i.split(":", 1)
        out[i] = [BL.run_set_method(BL.METHODS[meth](json.loads(cfg)), [z + e for z in zs])[0] for e in SHIFTS]
    return R.key(r), out


def stability(out, n=100, workers=14):
    """plan section 3: the first comparison's B1@M2 and every B1s configuration on n DEV rows (smallest sha256 keys),
    with the data shifted by each of SHIFTS; a row is unstable for a configuration if its detections differ"""
    rows = sorted(R.dev_rows(), key=lambda r: hashlib.sha256(R.key(r).encode()).hexdigest())[:n]
    ids = [FIRST_B1] + [R.cfg_id("B1s", c) for c in R.GRID["B1s"]]
    with ProcessPoolExecutor(workers) as pool:
        got = list(pool.map(stab_job, [(r, ids) for r in rows]))
    return {i: sum(len(set(d[i])) > 1 for _, d in got) for i in ids} | {"rows": n, "shifts": SHIFTS}


def block_job(args):
    r, ids, unlock = args
    warnings.filterwarnings("ignore")
    S.unlock_validation(unlock)
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    zs = G.zs_of(run)
    return {"key": R.key(r)} | {i: R.run_one(i, run, zs, r["oracle"]["t_star"]) for i in ids}


def block(out, chosen_path, workers):
    plan = PLAN.read_text()
    csha = sha(chosen_path)
    if not any(l.startswith("Status: FROZEN") for l in plan.splitlines()) or csha not in plan:
        raise SystemExit("BASELINE2-PLAN.md is not FROZEN with this chosen.json: the block is not run")
    if sha(VAL3) not in plan or sha(BLOCK1) not in plan:
        raise SystemExit("BASELINE2-PLAN.md does not quote the sha256 of the block rows and the first block")
    head, dirty = R.git_state()
    if dirty:
        raise SystemExit("tracked files are modified: the block is not run")
    chosen = json.loads(chosen_path.read_text())
    ids = list(dict.fromkeys(chosen.values()))
    if None in ids:
        raise SystemExit("a chosen configuration is missing")
    rows = [json.loads(l) for l in VAL3.read_text().splitlines() if l.strip()]
    assert len(rows) == 9600 and {r["seed"] for r in rows} == set(range(440400, 440600))
    out.mkdir(parents=True, exist_ok=False)
    unlock = sha(MAN)
    # identity: the first comparison's B1 and B4 on one run per design cell give the first block's detections
    first, ident = first_block(), R.identity_rows(rows)
    with ProcessPoolExecutor(workers) as pool:
        got = list(pool.map(block_job, [(r, [FIRST_B1, FIRST_B4], unlock) for r in ident]))
    bad = [g["key"] for g in got for i in (FIRST_B1, FIRST_B4) if g[i]["detect"] != first[g["key"]][i]["detect"]]
    (out / "identity.json").write_text(json.dumps({"rows": len(got), "differ": bad}, indent=1) + "\n")
    if bad:
        raise SystemExit(f"identity check failed on {len(bad)} rows: the block is not run")
    (out / "meta.json").write_text(json.dumps({"stage": "block2", "git_head": head, "chosen": chosen,
        "chosen_sha256": csha, "val3_sha256": sha(VAL3), "block1_sha256": sha(BLOCK1), "rows": len(rows),
        "identity_rows": len(got), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=1) + "\n")
    with ProcessPoolExecutor(workers) as pool, (out / "rows.jsonl").open("x") as f:
        futs = [pool.submit(block_job, (r, ids, unlock)) for r in rows]
        for n, fut in enumerate(as_completed(futs), 1):
            f.write(json.dumps(fut.result(), sort_keys=True) + "\n")
            if n % 200 == 0:
                f.flush(); print(f"{n}/{len(rows)} {time.strftime('%H:%M:%S')}", flush=True)
    meta = json.loads((out / "meta.json").read_text()); meta["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")


def score(out):
    """plan sections 4 and 5, on validation 3's paired events; the bootstrap is baselines_run.boot_diff"""
    val = {R.key(r): r for r in map(json.loads, VAL3.read_text().splitlines()) if r}
    new = {j["key"]: j for j in map(json.loads, (out / "rows.jsonl").read_text().splitlines()) if j}
    old = first_block()
    chosen = json.loads((out / "meta.json").read_text())["chosen"]
    assert set(new) == set(val) == set(old)
    ev = [k for k, r in val.items() if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is not None]
    paired = [k for k in ev if val[k]["v2"] is not None]
    adm = [k for k, r in val.items() if r["cell"] == "healthy" or (r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is None)]
    ts = lambda k: val[k]["oracle"]["t_star"]
    det = {"IM": {k: val[k]["v2"] for k in val}, "WM": {k: val[k]["F3"]["detect"] for k in val},
           "TS": {k: old[k]["cyl16p"]["detect"] for k in val}, FIRST_B1: {k: old[k][FIRST_B1]["detect"] for k in val},
           FIRST_B4: {k: old[k][FIRST_B4]["detect"] for k in val}}
    rec = {i: new for i in dict.fromkeys(chosen.values())} | {FIRST_B1: old, FIRST_B4: old}
    for i in dict.fromkeys(chosen.values()):
        det[i] = {k: new[k][i]["detect"] for k in val}
    lag = lambda d, k: (T.N if d is None else d) - ts(k)
    LIM = sum(lag(det["IM"][k], k) for k in paired)
    table = {}
    for name, d in det.items():
        L = sum(lag(d[k], k) for k in paired)
        row = {"paired_lag": L, "D_paired": 1 - L / LIM, "misses": sum(d[k] is None for k in ev),
               "at_t_star": sum(d[k] == ts(k) for k in ev), "admissible_alarms": [k for k in adm if d[k] is not None],
               "early": [k for k in ev if d[k] is not None and d[k] < ts(k)]}
        if name in rec:
            src = rec[name]
            samples = sum((T.N if d[k] is None else d[k] + 1) for k in val)
            row |= {"memory": max(src[k][name].get("memory", 0) for k in val),
                    "ms_per_sample": 1000 * sum(src[k][name]["seconds"] for k in val) / samples,
                    "n_lp": sum(src[k][name].get("n_lp", 0) for k in val),
                    "lp_fail": sum(src[k][name].get("lp_fail", 0) for k in val)}
        table[name] = row
    Rrows = [{"seed": val[k]["seed"], **{n: lag(det[n][k], k) for n in det}} for k in paired]
    hyp = {}
    if chosen.get("B1s@M2"):
        hyp["H-S1 WM < B1s@M2"] = R.boot_diff(Rrows, "WM", chosen["B1s@M2"])
    for b in ("B1s@M1", "B4s@M1"):
        if chosen.get(b):
            hyp[f"H-S2 TS < {b}"] = R.boot_diff(Rrows, "TS", chosen[b])
    res = {"chosen": chosen, "table": table, "hypotheses": hyp}
    (out / "scores.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print(json.dumps(res, indent=1, sort_keys=True))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("dev", "unit", "tune", "block", "score"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--chosen", type=Path)
    ap.add_argument("--subset", type=int)
    a = ap.parse_args()
    if a.cmd == "dev":
        R.dev(a.out, a.workers, None, a.subset)
    elif a.cmd == "unit":
        unit(a.out)
    elif a.cmd == "tune":
        R.tune(a.out)
    elif a.cmd == "block":
        block(a.out, a.chosen, a.workers)
    else:
        score(a.out)


if __name__ == "__main__":
    main()
