"""Freeze 1 and the gap of DIAG-3 amendment 9: does the frozen template state change when that gap is covered? DEV only.

The frozen TemplateMachine (inv4p, cyl16p) predicts with the float M and widens the slab of z by one ulp only.
Amendment 9 found two terms that this does not cover (check_model.py):
  model  the recurrence of thermal.py's step(), taken exactly (MX), differs from the float M by about u per entry;
  data   the float data differ from the exact recurrence's data by up to 1.2e-13 degC on DEV (measured).
The covered machine uses the frozen tables unchanged and adds:
  - to each predicted support, ||(MX - M)^T d_i||_1 * max_c |s_c| over P (exact rationals, rounded up), which bounds
    supp_P(MX^T d_i) - supp_P(M^T d_i);
  - the slab delta + ETA (ETA = 1e-9 degC, amendment 9's allowance).
Its clamps are the frozen file's: cyl16p's hold under MX (check_model.py), and inv4p's must be a subset of them.

Per row: the first alarm of the frozen and of the covered machine, and the gap min(top - lo, hi - bottom) between the
as-range and the slab: at the alarm (negative), and its smallest value before it (or over the run, without an alarm).
The frozen machine is replayed here and must equal template_state.first_inconsistent on every row.

Rows: the 1320 DEV comparison rows (dev-45cff1d, uniform noise) and amendment 7's 80 healthy edge-noise runs
(430070-430089, both arms, rw and ramp).
usage: python -B check_freeze1_model.py OUT_DIR [--workers 8]
"""
import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diag3_cw as C  # noqa: E402

V, T, S = C.V, C.T, C.S
ROOT = HERE.parents[2]
CELL = {c.name: c for c in T.CELLS}
DELTA_COV = math.nextafter(T.DELTA + C.ETA, math.inf)
CANDS, MPAD = None, None


def model_pad(tp):
    """||(MX - M)^T d_i||_1 per direction, exact, rounded up."""
    Mq = [[Fraction(float(V.M[i, j])) for j in range(3)] for i in range(3)]
    out = []
    for d in tp.D:
        dq = [Fraction(float(x)) for x in d]
        g = [sum((C.MX[r][c] - Mq[r][c]) * dq[r] for r in range(3)) for c in range(3)]
        out.append(math.nextafter(float(sum(abs(x) for x in g)), math.inf))
    return np.array(out)


def _init():
    global CANDS, MPAD
    m = json.loads((HERE.parent / "frozen" / "MANIFEST.json").read_text())
    CANDS = {k: V.load_frozen(ROOT / c["file"], c["sha256"]) for k, c in m["candidates"].items()}
    MPAD = {k: model_pad(tp) for k, tp in CANDS.items()}


def predict(tp, h, mpad):
    if mpad is None:
        return tp.predict(h)
    idx, lam, lsum, res, starts = tp._flat
    cap = tp._cap(h)
    vals = (lam * h[idx]).sum(axis=1) + V.GAMMA4 * lsum * np.max(np.abs(h)) + res * cap
    low = np.minimum.reduceat(vals, starts)
    out = low + tp.rho_pad + mpad * cap
    out = np.nextafter(out + 4 * V.EPS * (np.abs(low) + tp.rho_pad + mpad * cap), np.inf)  # 3 operations
    return tp.clamp(out)


def replay(tp, y, P, delta, mpad):
    """first alarm, the gap at it, the smallest gap before it (the whole run without an alarm)."""
    h = tp.clamp(tp.h0)
    tc, ts = T.equilibrium(T.P0, 0.0)
    ip, im = tp.ip[1], tp.im[1]
    gmin = math.inf
    for k, (yk, pk) in enumerate(zip(y, P)):
        z = yk - ts
        tc, ts = T.step(tc, ts, pk, 0.0)
        zs = z - V.SHIFT
        lo = math.nextafter(math.nextafter(zs, -math.inf) - delta, -math.inf)
        hi = math.nextafter(math.nextafter(zs, math.inf) + delta, math.inf)
        top, bottom = tp.support(h, tp.supp_as[0]), -tp.support(h, tp.supp_as[1])
        gap = min(top - lo, hi - bottom)
        if top < lo or bottom > hi:
            return k, gap, gmin
        gmin = min(gmin, gap)
        h2 = h.copy()
        h2[ip], h2[im] = min(h2[ip], hi), min(h2[im], -lo)
        h = predict(tp, h2, mpad)
    return None, None, gmin


def job(row):
    run = S.run(row["seed"], CELL[row["cell"]], row["arm"], row["ambient"], row["noise"])
    out = {k: row[k] for k in ("seed", "cell", "arm", "ambient", "noise")}
    out["admissible"] = row["admissible"]
    if row["noise"] == "edge":                    # the k = 1 boundary case: v_0 and v_1 of opposite sign
        out["first_signs_opposite"] = (run["v"][0] > 0) != (run["v"][1] > 0)
    t0 = time.perf_counter()
    for name, tp in CANDS.items():
        ref = V.first_inconsistent(tp, run["y"], run["P"])
        f, fg, fmin = replay(tp, run["y"], run["P"], T.DELTA, None)
        c, cg, cmin = replay(tp, run["y"], run["P"], DELTA_COV, MPAD[name])
        out[name] = {"reference": ref, "frozen": f, "frozen_alarm_gap_C": fg, "frozen_min_gap_C": fmin,
                     "covered": c, "covered_alarm_gap_C": cg, "covered_min_gap_C": cmin}
    out["seconds"] = round(time.perf_counter() - t0, 2)
    return out


def rows():
    dev = [json.loads(l) for l in (ROOT / "results" / "v3" / "dev-45cff1d" / "rows.jsonl").read_text().splitlines()
           if l.strip()]
    out = [{k: r[k] for k in ("seed", "cell", "arm", "ambient", "noise")} |
           {"admissible": r["cell"] == "healthy" or (r["oracle"]["t_star"] is None and r["oracle"]["status"] == "certified")}
           for r in dev]
    out += [{"seed": s, "cell": "healthy", "arm": a, "ambient": amb, "noise": "edge", "admissible": True}
            for s in range(430070, 430090) for a in ("E0", "E1") for amb in ("rw", "ramp")]
    return out


def clamps_covered():
    """inv4p's directions and clamps must occur in cyl16p, whose clamps check_model.py proved under MX."""
    cyl = {tuple(d): c for d, c in zip(CANDS["cyl16p"].D.tolist(), CANDS["cyl16p"].cap_inv.tolist())}
    inv = CANDS["inv4p"]
    return [i for i, (d, c) in enumerate(zip(inv.D.tolist(), inv.cap_inv.tolist())) if cyl.get(tuple(d)) != c]


def summary(res):
    s = {"rows": len(res), "delta_covered": DELTA_COV, "eta_C": C.ETA,
         "model_pad_max": {k: float(v.max()) for k, v in MPAD.items()},
         "inv4p_clamps_not_in_cyl16p": clamps_covered(), "candidates": {}}
    for name in CANDS:
        x = [r[name] for r in res]
        alarm = [v for v in x if v["frozen"] is not None]
        adm = [(r, r[name]) for r in res if r["admissible"]]
        s["candidates"][name] = {
            "replay_differs_from_reference": sum(v["frozen"] != v["reference"] for v in x),
            "rows_differ": [[r[k] for k in ("seed", "cell", "arm", "ambient", "noise")] + [r[name]["frozen"],
                            r[name]["covered"]] for r in res if r[name]["frozen"] != r[name]["covered"]],
            "alarms_frozen": len(alarm), "alarms_covered": sum(v["covered"] is not None for v in x),
            "alarms_on_admissible": sum(v["frozen"] is not None or v["covered"] is not None for _, v in adm),
            "smallest_alarm_margin_C": min((-v["frozen_alarm_gap_C"] for v in alarm), default=None),
            "smallest_gap_on_admissible_C": {nz: min((v["frozen_min_gap_C"] for r, v in adm if r["noise"] == nz),
                                                     default=None) for nz in ("uniform", "edge")},
            "smallest_gap_on_admissible_covered_C": {nz: min((v["covered_min_gap_C"] for r, v in adm
                                                              if r["noise"] == nz), default=None)
                                                     for nz in ("uniform", "edge")},
            "edge_runs_by_first_signs": {
                lab: {"runs": len(g), "gap_below_1e-13": sum(v < 1e-13 for v in g),
                      "smallest_gap_C": min(g, default=None), "largest_gap_C": max(g, default=None)}
                for lab, g in (("opposite", [r[name]["frozen_min_gap_C"] for r in res if r.get("first_signs_opposite")]),
                               ("same", [r[name]["frozen_min_gap_C"] for r in res
                                         if r["noise"] == "edge" and not r.get("first_signs_opposite")]))}}
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("out", type=Path)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    todo = rows()[:a.limit] if a.limit else rows()
    _init()
    t0 = time.time()
    with ProcessPoolExecutor(a.workers, initializer=_init) as pool:
        res = list(pool.map(job, todo, chunksize=4))
    with (a.out / "rows.jsonl").open("w") as f:
        for r in res:
            f.write(json.dumps(r) + "\n")
    import hashlib
    import platform
    import subprocess
    import scipy
    s = summary(res) | {"wall_seconds": round(time.time() - t0, 1), "meta": {
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True, text=True).stdout.strip(),
        "platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version(),
        "numpy": np.__version__, "scipy": scipy.__version__,
        "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z")}}
    (a.out / "summary.json").write_text(json.dumps(s, indent=1) + "\n")
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
