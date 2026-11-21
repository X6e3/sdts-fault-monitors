"""AMBIENT-PLAN.md: the v3 trackers under broken ambient assumptions (a) and under a wider assumed box (b).

  python -B ambient_study.py a OUT [--workers 8]     section 1 (v2, cyl16p, F3; 5 scenarios x 60 healthy runs)
  python -B ambient_study.py b OUT [--workers 8]     section 2 (v2, cyl16p; 3 boxes x 1320 DEV rows)
  python -B ambient_study.py summary OUT
"""
import argparse
import json
import math
import os
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import diag3_cw as C  # noqa: E402
import diag3_cw_dev as CD  # noqa: E402
import run_validation as RV1  # noqa: E402

G, S, T, V = C.G, C.S, C.T, C.V
DEV_ROWS = G.ROOT / "results/v3/dev-45cff1d/rows.jsonl"
SCEN = ("A0", "A1", "A2", "A3", "A4")
BOXES = {"23-27": (23.0, 27.0), "22-28": (22.0, 28.0), "21-29": (21.0, 29.0)}


def ambient(seed, scen, n=T.N):
    rng = random.Random(f"{seed}:ambient-study:{scen}")
    lo, hi, k = (20.0, 30.0, 1.0) if scen == "A1" else (T.TA_LO, T.TA_HI, {"A2": 2.0, "A3": 5.0}.get(scen, 1.0))
    ta = [rng.uniform(lo, hi)]
    for _ in range(n - 1):
        ta.append(min(hi, max(lo, ta[-1] + rng.uniform(-k * T.RHO_A, k * T.RHO_A))))
    if scen == "A4":
        ta = [x + (1.0 if i >= 1000 else 0.0) for i, x in enumerate(ta)]
    return ta


def healthy_run(seed, arm, scen):
    P, TA, v = S.command(seed, arm), ambient(seed, scen), S.noise(seed, "uniform")
    Ts = T.simulate(P, TA, T.equilibrium(T.P0, TA[0]))
    y = [a + b for a, b in zip(Ts, v)]
    Sk = T.known_part(P)
    return {"y": y, "P": P, "TA": TA, "z": [a - b for a, b in zip(y, Sk)]}


_CY = None


def cyl16p(box=None):
    """freeze 1's cyl16p; with `box` (lo, hi) the clamps and start supports are recomputed for that box"""
    tp = V.load_frozen(G.V3 / "frozen" / "cyl16p.json")
    if box is None:
        return tp
    lo, hi = box[0] - V.SHIFT, box[1] - V.SHIFT
    for i, d in enumerate(tp.D):
        sigma = float(d.sum())
        inv = V.invariant_support(d[:2])
        tp.cap_inv[i] = math.nextafter(max(sigma * hi, sigma * lo) + inv + 8 * V.EPS, math.inf)
    s = tp.D @ np.ones(3)
    tp.h0 = np.array([math.nextafter(max(hi, -lo) * abs(x) * (1 + 4 * V.EPS), math.inf) for x in s])
    return tp


def first_template(tp, y, P, box):
    old = (V.LO, V.HI)
    V.LO, V.HI = box[0] - V.SHIFT, box[1] - V.SHIFT
    try:
        m = V.TemplateMachine(tp)
        for k, (a, b) in enumerate(zip(y, P)):
            m.observe(a, b)
            if m.inconsistent:
                return k
        return None
    finally:
        V.LO, V.HI = old


def first_v2(y, P, box):
    old = (T.TA_LO, T.TA_HI)
    T.TA_LO, T.TA_HI = box
    try:
        return RV1.v2_first(y, P)
    finally:
        T.TA_LO, T.TA_HI = old


def job_a(args):
    seed, arm, scen, out = args
    path = Path(out) / f"a-{scen}-{seed}-{arm}.json"
    if path.exists():
        return path.name, "done before"
    r = healthy_run(seed, arm, scen)
    box = (T.TA_LO, T.TA_HI)
    t0 = time.monotonic()
    f3 = CD.online("F3", G.zs_of(r), C.W, 64)
    rec = {"seed": seed, "arm": arm, "scenario": scen, "v2": first_v2(r["y"], r["P"], box),
           "cyl16p": first_template(cyl16p(), r["y"], r["P"], box), "F3": f3["detect"],
           "F3_certified": (f3["alarm_certificate"] or {}).get("certified"), "F3_seconds": round(time.monotonic() - t0, 1),
           "TA_outside_box": [i for i, x in enumerate(r["TA"]) if not T.TA_LO <= x <= T.TA_HI][:1],
           "max_rate_over_rho": max(abs(b - a) for a, b in zip(r["TA"], r["TA"][1:])) / T.RHO_A}
    path.write_text(json.dumps(rec) + "\n")
    return path.name, rec["v2"], rec["cyl16p"], rec["F3"]


def job_b(args):
    r, out = args
    key = f"{r['seed']}-{r['cell']}-{r['arm']}-{r['ambient']}-{r['noise']}"
    path = Path(out) / f"b-{key}.json"
    if path.exists():
        return key, "done before"
    run = S.run(r["seed"], next(c for c in T.CELLS if c.name == r["cell"]), r["arm"], r["ambient"], r["noise"])
    rec = {"key": key, "cell": r["cell"], "t_star": r["oracle"]["t_star"], "status": r["oracle"]["status"],
           "v2_recorded": r["v2"]}
    for name, box in BOXES.items():
        rec[f"v2@{name}"] = first_v2(run["y"], run["P"], box)
        rec[f"cyl16p@{name}"] = first_template(cyl16p(None if name == "23-27" else box), run["y"], run["P"], box)
    path.write_text(json.dumps(rec) + "\n")
    return key, rec["v2@23-27"] == r["v2"]


def summary(out):
    rep = {"a": {}, "b": {}}
    A = [json.loads(p.read_text()) for p in out.glob("a-*.json")]
    for scen in SCEN:
        xs = [x for x in A if x["scenario"] == scen]
        if not xs:
            continue
        rep["a"][scen] = {"runs": len(xs)}
        for m in ("v2", "cyl16p", "F3"):
            d = sorted(x[m] for x in xs if x[m] is not None)
            rep["a"][scen][m] = {"alarms": len(d), "share": round(len(d) / len(xs), 3),
                                 "median": d[len(d) // 2] if d else None, "min": d[0] if d else None}
        if scen == "A1":
            rep["a"][scen]["runs_with_TA_outside"] = sum(bool(x["TA_outside_box"]) for x in xs)
    B = [json.loads(p.read_text()) for p in out.glob("b-*.json")]
    if B:
        ev = [x for x in B if x["status"] == "certified" and x["t_star"] is not None]
        adm = [x for x in B if x["cell"] == "healthy" or (x["status"] == "certified" and x["t_star"] is None)]
        rep["b"]["rows"] = len(B)
        rep["b"]["v2_identity_at_frozen_box"] = sum(x["v2@23-27"] == x["v2_recorded"] for x in B)
        for m in ("v2", "cyl16p"):
            for name in BOXES:
                k = f"{m}@{name}"
                lag = sum((T.N if x[k] is None else x[k]) - x["t_star"] for x in ev)
                drift = sum((T.N if x[k] is None else x[k]) - x["t_star"] for x in ev if x["cell"].startswith("drift"))
                rep["b"][k] = {"lag_all_events": lag, "lag_drift": drift, "misses": sum(x[k] is None for x in ev),
                               "admissible_alarms": sum(x[k] is not None for x in adm)}
    (out / "summary.json").write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=("a", "b", "summary"))
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    if a.cmd == "summary":
        summary(a.out)
        return
    if a.cmd == "a":
        jobs = [(s, arm, scen, str(a.out)) for scen in SCEN for s in range(430000, 430030) for arm in T.ARMS]
        fn = job_a
    else:
        rows = [json.loads(l) for l in DEV_ROWS.read_text().splitlines() if l.strip()]
        jobs = [(r, str(a.out)) for r in rows]
        fn = job_b
    with ProcessPoolExecutor(a.workers) as pool:
        for f in as_completed([pool.submit(fn, j) for j in jobs]):
            print(f.result(), flush=True)


if __name__ == "__main__":
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    main()
