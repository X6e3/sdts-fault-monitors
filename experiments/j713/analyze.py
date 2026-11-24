"""J713 thermal step test: phase summaries and a two-node model fit (exploratory, not a result).

  python -B analyze.py STEPDIR [--fit]

Model, 1 s steps, as the simulated plant of the paper: a core node c (heated by the measured power P) and a sensor
node s (the chassis, the monitored sensor), exchanging heat (k) and losing it to the ambient TA (h):
    c[k+1] = c[k] + kc (s[k] - c[k]) + bc P[k]
    s[k+1] = s[k] + ks (c[k] - s[k]) + hs (TA - s[k])
The core is not measured in the paper's set-up; here it is fitted by output error on s alone (open-loop simulation
from the first sample with the measured P), with TA a constant. The residual of s is what the noise bound and the
model error would have to cover.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares


def load(d):
    rows = list(csv.reader(open(d / "log.csv")))
    h = rows[0]
    X = np.array([[float(x) for x in r] for r in rows[1:] if len(r) == len(h)])
    col = {name: X[:, i] for i, name in enumerate(h)}
    t0 = col["t_unix"][0]
    ph = [(n, float(u) - t0) for n, u in list(csv.reader(open(d / "phases.csv")))[1:]]
    return col, ph


def signals(col):
    die = [k for k in col if "tdie" in k and np.nanmin(col[k]) > 0]
    return {
        "P_PSTR": col["smc:PSTR"], "P_PDTR": col["smc:PDTR"],
        "die_mean": np.nanmean(np.array([col[k] for k in die]), axis=0),
        "Tp_mean": np.mean(np.array([col[k] for k in col if k.startswith("smc:Tp")]), axis=0),
        "Ts0x_mean": np.mean(np.array([col[k] for k in col if k.startswith("smc:Ts0") and k not in ("smc:Ts0P",)]), axis=0),
        "TPD_mean": np.mean(np.array([col[k] for k in col if k.startswith("smc:TPD")]), axis=0),
        "TRD_mean": np.mean(np.array([col[k] for k in col if k.startswith("smc:TRD")]), axis=0),
        "Ts0P": col["smc:Ts0P"], "Ts1P": col["smc:Ts1P"], "TAOL": col["smc:TAOL"], "TVA0": col["smc:TVA0"],
        "TB0T": col["smc:TB0T"], "TH0T": col["smc:TH0T"], "TDeL": col["smc:TDeL"],
    }


def phase_table(t, sig, ph):
    out = []
    bounds = [p for _, p in ph] + [t[-1] + 1]
    for (name, a), b in zip(ph, bounds[1:]):
        m = (t >= a) & (t < b)
        if not m.any():
            continue
        last = np.nonzero(m)[0][-1]
        out.append({"phase": name, "seconds": round(b - a), **{
            k: {"mean": round(float(np.mean(v[m])), 3), "end": round(float(v[last]), 3)} for k, v in sig.items()}})
    return out


def simulate(p, P, s0):
    kc, bc, ks, hs, TA, c0 = p
    n = len(P)
    c, s = np.empty(n), np.empty(n)
    c[0], s[0] = c0, s0
    for k in range(n - 1):
        c[k + 1] = c[k] + kc * (s[k] - c[k]) + bc * P[k]
        s[k + 1] = s[k] + ks * (c[k] - s[k]) + hs * (TA - s[k])
    return c, s


def fit(P, s):
    def res(p):
        return simulate(p, P, s[0])[1] - s
    p0 = np.array([0.01, 0.01, 0.002, 0.002, s[0] - 2.0, s[0] + 5.0])
    lb = [1e-6, 1e-6, 1e-7, 1e-7, s[0] - 15, s[0] - 5]
    ub = [1.0, 1.0, 0.5, 0.5, s[0] + 5, s[0] + 60]
    r = least_squares(res, p0, bounds=(lb, ub), x_scale="jac")
    e = res(r.x)
    return {"params": dict(zip(("kc", "bc", "ks", "hs", "TA", "c0"), map(float, r.x))),
            "rms": float(np.sqrt(np.mean(e ** 2))), "max_abs": float(np.max(np.abs(e))),
            "p99_abs": float(np.percentile(np.abs(e), 99))}


def main():
    d = Path(sys.argv[1])
    col, ph = load(d)
    t = col["t_mono"]
    sig = signals(col)
    rep = {"samples": len(t), "phases": ph, "summary": phase_table(t, sig, ph)}
    if "--fit" in sys.argv:
        rep["fit"] = {}
        for sname in ("Ts0P", "Ts1P"):
            for pname in ("P_PSTR",):
                rep["fit"][f"{sname}~{pname}"] = fit(sig[pname], sig[sname])
    (d / "analysis.json").write_text(json.dumps(rep, indent=1) + "\n")
    for row in rep["summary"]:
        print(row["phase"], row["seconds"], {k: v["end"] for k, v in row.items() if isinstance(v, dict)})
    if "fit" in rep:
        print(json.dumps(rep["fit"], indent=1))


if __name__ == "__main__":
    main()
