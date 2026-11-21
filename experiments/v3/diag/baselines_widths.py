"""BASELINE-PLAN.md, an explanatory diagnostic of the DEV tuning (written 2026-11-21, after the DEV run had shown
every baseline far behind v2): how wide each method's predicted as-range is, the range the alarm test uses.

On DEV seed 430010 (E0, rw ambient, uniform noise): the healthy run's width over time, and the detection on two
fault runs of the same seed (jump_0.2 and drift_0.002). v2's width is that of its feasible interval after the
update (the interval the next sample is tested against before the rate step); the baselines' is the predicted range
before the test. The chosen configurations are read from the DEV run's chosen.json. DEV data only.

  python -B baselines_widths.py CHOSEN [--json FILE]
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent.parent / "machine")]
import baselines as BL  # noqa: E402
import baselines_cz  # noqa: E402,F401
from thermal_machine import ThermalMachine  # noqa: E402

S, T, G = BL.S, BL.T, BL.G
MARKS = (10, 50, 100, 300, 1000, 3000)
RUNS = [(430010, c, "E0", "rw", "uniform") for c in ("healthy", "jump_0.2", "drift_0.002")]


def v2_widths(y, P):
    m, w = ThermalMachine(), []
    for k, (a, b) in enumerate(zip(y, P)):
        bad = m.observe(a, b)
        w.append(m._feasible[1] - m._feasible[0])
        if bad:
            return k, w
    return None, w


def set_widths(m, zs):
    def rg():
        if hasattr(m, "range"):
            return m.range(BL.P2)
        if hasattr(m, "lo"):
            return m.lo[1], m.hi[1]
        return BL.span(m.c, m.G, BL.P2)
    r, w = rg(), []
    w.append(r[1] - r[0])
    if m.check_and_update(zs[0]):
        return 0, w
    for t in range(1, len(zs)):
        m.predict()
        r = rg()
        w.append(float("inf") if r is None else r[1] - r[0])
        if m.check_and_update(zs[t]):
            return t, w
    return None, w


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("chosen", type=Path)
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    warnings.filterwarnings("ignore")
    chosen = json.loads(a.chosen.read_text())
    cfgs = {}
    for k, i in chosen.items():
        meth, cfg = i.split(":", 1)
        cfgs.setdefault(i, (meth, json.loads(cfg), []))[2].append(k)
    rep = {}
    for seed, cell, arm, al, nl in RUNS:
        run = S.run(seed, next(c for c in T.CELLS if c.name == cell), arm, al, nl)
        zs = G.zs_of(run)
        out = {"t_f": run["t_f"]}
        d, w = v2_widths(run["y"], run["P"])
        out["v2"] = {"detect": d, "widths": {t: round(w[t], 4) for t in MARKS if t < len(w)},
                     "median_100_end": round(float(np.median(w[100:])), 4)}
        for i, (meth, cfg, names) in cfgs.items():
            d, w = set_widths(BL.METHODS[meth](cfg), zs)
            out["/".join(names)] = {"id": i, "detect": d, "widths": {t: round(w[t], 4) for t in MARKS if t < len(w)},
                                    "median_100_end": round(float(np.median(w[100:])), 4)}
        rep[f"{seed}-{cell}-{arm}-{al}-{nl}"] = out
    txt = json.dumps(rep, indent=1)
    print(txt)
    if a.json:
        a.json.write_text(txt + "\n")


if __name__ == "__main__":
    main()
