"""Data of the preprint's figures, from the records and from runs regenerated on development seeds.

  python -B paper/figures/make_data.py        (the project Python; writes paper/preprint/figdata/*.dat, figures.json)

fig1  memory against D_paired. Development points are scored here with the scorer of the baselines' DEV run
      (baselines_run.score): IM by definition 0; inv4p from dev-45cff1d's template "inv4+I" (pruning it to inv4p left
      every result identical, RESULTS.md); TS from the ambient study's part (b) at the frozen box; the windows from
      DIAG-3-RESULTS.md's size-loss table (paper Table 2). Validation points from the three validation records.
      Memory: the numbers kept between samples; for a window, the 42 supports of its base plus its largest number of
      kept measurements on that data (their sample indices, tau and the LP workspace are not counted).
fig2  development run 430010, drift 0.0005 C/s, E0, ramp ambient, uniform noise: for each sample, the a_s-range each
      monitor tests the measurement against (IM: the feasible interval advanced by rho within the box; TS: the
      template's supports before the update; WM: the window's range given z up to t - 1, as F3 computes it).
fig4  validation 3, per fault cell: the lag of IM and of WM over the certified events (a miss counted as N - t*).
"""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "experiments" / "v3"
sys.path[:0] = [str(V3 / "diag"), str(V3), str(ROOT / "experiments" / "machine")]
import baselines_run as R  # noqa: E402
import baselines as BL  # noqa: E402
from thermal_machine import ThermalMachine  # noqa: E402

S, T, G, V, C, CD = BL.S, BL.T, BL.G, BL.V, BL.C, BL.CD
OUT = ROOT / "paper" / "preprint" / "figdata"
N = T.N


def fig1():
    rows = R.dev_rows()
    by = {R.key(r): r for r in rows}
    dev = [json.loads(l) for l in (ROOT / "results/v3/dev-45cff1d/rows.jsonl").read_text().splitlines() if l.strip()]
    inv4 = [{"key": R.key(r), "detect": r["templates"]["inv4+I"]["first"] if isinstance(r["templates"]["inv4+I"], dict)
             else r["templates"]["inv4+I"], "seconds": 0.0, "memory": 16, "lp_fail": 0} for r in dev]
    s_inv4 = R.score(inv4, [by[x["key"]] for x in inv4])
    amb = [json.loads(p.read_text()) for p in sorted((ROOT / "results/v3/ambient/amb-443d8b30-mac").glob("b-*.json"))]
    cy = [{"key": x["key"], "detect": x["cyl16p@23-27"], "seconds": 0.0, "memory": 42, "lp_fail": 0} for x in amb]
    s_cy = R.score(cy, [by[x["key"]] for x in cy])
    devpts = [("IM", 2, 0.0), ("inv4p", 16, s_inv4["D_paired"]), ("TS", 42, s_cy["D_paired"]),
              ("W = 64", 42 + 18, 0.643), ("W = 128", 42 + 28, 0.815), ("W = 192", 42 + 35, 0.824),
              ("W = 256", 42 + 45, 0.9992)]
    valpts = [("inv4p", 16, 0.152), ("TS", 42, 0.387), ("WM", 42 + 65, 0.9952)]
    fam = {"IM": 0, "inv4p": 1, "TS": 1, "WM": 2}
    for name, pts in (("fig1_dev.dat", devpts), ("fig1_val.dat", valpts)):
        with (OUT / name).open("w") as f:
            f.write("mem D fam\n")                  # fam: 0 IM, 1 template, 2 window
            for lab, m, d in pts:
                f.write(f"{m} {d:.4f} {fam.get(lab, 2)}\n")
    return {"dev": devpts, "val": valpts, "inv4p_dev": {k: s_inv4[k] for k in ("events", "paired", "D_paired", "misses")},
            "TS_dev": {k: s_cy[k] for k in ("events", "paired", "D_paired", "misses")}}


def fig2(seed=430010, cell="drift_0.0005", arm="E0", amb="ramp", noise="uniform"):
    run = S.run(seed, next(c for c in T.CELLS if c.name == cell), arm, amb, noise)
    zs = G.zs_of(run)
    sh = V.SHIFT
    # IM: the interval the measurement at k is tested against
    im, m, det_im = [], ThermalMachine(), None
    for k, (y, p) in enumerate(zip(run["y"], run["P"])):
        f_lo, f_hi = m._feasible
        if k == 0:
            lo, hi = T.TA_LO, T.TA_HI
        else:
            lo, hi = max(T.TA_LO, f_lo - T.RHO_A), min(T.TA_HI, f_hi + T.RHO_A)
        im.append((lo - sh, hi - sh))
        if m.observe(y, p):
            det_im = k
            break
    # TS: the template's a_s-range before the update at k
    tp = V.load_frozen(V3 / "frozen" / "cyl16p.json")
    ts, tm, det_ts = [], V.TemplateMachine(tp), None
    for k, (y, p) in enumerate(zip(run["y"], run["P"])):
        ts.append((-tm.t.support(tm.h, tm.t.supp_as[1]), tm.t.support(tm.h, tm.t.supp_as[0])))
        if tm.observe(y, p):
            det_ts = k
            break
    # WM: F3's own online loop, its as_range calls recorded
    wm = {}
    make = CD.C.make

    def rec_make(var, cy):
        w = make(var, cy)
        f = w.as_range

        def as_range(t):
            out = f(t)
            wm[t] = out
            return out
        w.as_range = as_range
        return w
    CD.C.make = rec_make
    try:
        res = CD.online("F3", zs, C.W, 64)
    finally:
        CD.C.make = make
    det_wm = res["detect"]
    dev = {R.key(r): r for r in R.dev_rows()}
    t_star = dev[f"{seed}-{cell}-{arm}-{amb}-{noise}"]["t_star"]
    with (OUT / "fig2_trace.dat").open("w") as f:
        # *top = the upper edge of the acceptance band (hi + delta); *w = the width of the range (hi - lo);
        # *med = the median of *w over the 61 samples centred on k (only where all 61 exist)
        f.write("k z imlo imhi tslo tshi wmlo wmhi imtop tstop wmtop imw tsw wmw immed tsmed wmmed\n")
        d = T.DELTA
        n = max(len(im), len(ts))
        cols = []
        for k in range(n):
            a = im[k] if k < len(im) else (math.nan, math.nan)
            b = ts[k] if k < len(ts) else (math.nan, math.nan)
            c = wm.get(k, (math.nan, math.nan))
            c = tuple(math.nan if v is None else v for v in c)
            cols.append([a[0], a[1], b[0], b[1], c[0], c[1], a[1] + d, b[1] + d, c[1] + d, a[1] - a[0], b[1] - b[0],
                         c[1] - c[0]])

        def med(j, k):
            w = [cols[i][j] for i in range(k - 30, k + 31) if 0 <= i < n]
            if len(w) < 61 or any(math.isnan(x) for x in w):
                return math.nan
            return sorted(w)[30]
        for k in range(n):
            row = cols[k] + [med(9, k), med(10, k), med(11, k)]
            f.write(f"{k} {zs[k]:.6f} " + " ".join("nan" if math.isnan(v) else f"{v:.6f}" for v in row) + "\n")
    return {"run": f"{seed}-{cell}-{arm}-{amb}-{noise}", "t_f": run["t_f"], "t_star": t_star,
            "detect": {"IM": det_im, "TS": det_ts, "WM": det_wm}, "delta": T.DELTA}


def fig4():
    rows = [json.loads(l) for l in (ROOT / "results/v3/freeze3/validation-440400-440599-948b46b0/rows.jsonl")
            .read_text().splitlines() if l.strip()]
    ev = [r for r in rows if r["oracle"]["status"] == "certified" and r["oracle"]["t_star"] is not None]
    cells = defaultdict(lambda: {"events": 0, "IM": 0, "WM": 0, "IM_miss": 0, "WM_miss": 0})
    for r in ev:
        c = cells[r["cell"]]
        c["events"] += 1
        for name, d in (("IM", r["v2"]), ("WM", r["F3"]["detect"])):
            c[name] += (N if d is None else d) - r["oracle"]["t_star"]
            c[name + "_miss"] += d is None
    order = ["jump_0.5", "jump_0.2", "stuck", "noise_x2", "gain_0.01", "drift_0.02", "drift_0.005", "drift_0.002",
             "drift_0.001", "drift_0.0005"]
    with (OUT / "fig4_cells.dat").open("w") as f:
        f.write("i events im wm immiss wmmiss\n")       # i: the row of `order` (labels in the figure)
        for i, name in enumerate(order):
            c = cells[name]
            f.write(f"{i} {c['events']} {c['IM']} {c['WM']} {c['IM_miss']} {c['WM_miss']}\n")
    return {k: dict(v) for k, v in cells.items()}


def main():
    rep = {"fig1": fig1(), "fig4": fig4(), "fig2": fig2()}
    (OUT / "figures.json").write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
