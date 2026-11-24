"""Reproduces the J713 step-3 evaluation (PLAN-step3.md section 4) from the released columns in data/j713/.

The frozen eval_step3.py reads the full logs, which also hold sensor columns that are not released; this script
reads only the released ones (time, PSTR, Ts0P, Ts1P) and calls the same model and fit (analyze.simulate,
analyze.fit) and the same refit of TA and c0. It can also write the measured and fitted Ts0P of step 3 for the figure.

The core c is not measured, so from (P, s) the six quantities (kc, bc, ks, hs, TA, c0) are identifiable only up to
a one-parameter family: the output depends on them only through kc+ks+hs, kc*hs, ks*bc, TA and
ks*(c0-s0)+hs*(TA-s0) (s0 is the first measurement). The fit stops at some point of that family, and where it stops
depends on the platform's floating point (the four rates move by under 1 % between macOS arm64 and Linux x86_64).
So the script checks what the data determine, not the individual parameters:
  1. with the step-1 rates frozen in step3-eval.json, the refit of step 3 gives its TA and residuals;
  2. the whole pipeline run here (fit step 1, then refit step 3) gives the same five invariants of step 1, the same
     TA and the same residual statistics, within the tolerances below.
The individual rates and c0 are printed, not compared.

  python3 -I -B experiments/j713/reproduce_step3.py [--figdata OUT.dat]      (from the repository root)
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402

DATA = HERE.parents[1] / "data" / "j713"


def series(step, sname):
    rows = list(csv.DictReader(open(DATA / f"{step}.csv")))
    t = np.array([float(r["t_mono"]) for r in rows])
    return np.array([float(r["PSTR"]) for r in rows]), np.array([float(r[sname]) for r in rows]), t


def refit(p, P, s):
    names = ("kc", "bc", "ks", "hs", "TA", "c0")
    base = dict(zip(names, p))

    def res(q):
        pp = dict(base)
        pp.update(zip(("TA", "c0"), q))
        return A.simulate([pp[n] for n in names], P, s[0])[1] - s
    r = least_squares(res, [base["TA"], base["c0"]])
    return dict(zip(("TA", "c0"), map(float, r.x))), res(r.x)


NAMES = ("kc", "bc", "ks", "hs", "TA", "c0")
STATS = ("val_rms", "val_p99_abs", "val_max_abs")
TOL_C = 1e-4      # degC, on TA and on residual statistics (the paper gives them to 0.001 degC or coarser)
TOL_REL = 1e-3    # relative, on the invariants of the step-1 fit


def invariants(p, s0):
    kc, bc, ks, hs, TA, c0 = (p[n] for n in NAMES)
    return {"kc+ks+hs": kc + ks + hs, "kc*hs": kc * hs, "ks*bc": ks * bc, "TA": TA,
            "ks*(c0-s0)+hs*(TA-s0)": ks * (c0 - s0) + hs * (TA - s0)}


def stats(e):
    return {"val_rms": float(np.sqrt(np.mean(e ** 2))), "val_p99_abs": float(np.percentile(np.abs(e), 99)),
            "val_max_abs": float(np.max(np.abs(e)))}


def main():
    ref = json.loads((HERE / "step3-eval.json").read_text())
    report, ok, fig = {}, True, None
    for sname in ("Ts0P", "Ts1P"):
        r = ref["sensors"][sname]
        P1, s1, _ = series("step1", sname)
        P3, s3, t3 = series("step3", sname)
        # 1. frozen step-1 rates, refit of step 3 on the released columns
        qf, ef = refit([r["dev_fit"]["params"][n] for n in NAMES], P3, s3)
        d1 = max([abs(qf["TA"] - r["val_refit"]["TA"])] + [abs(v - r[k]) for k, v in stats(ef).items()])
        # 2. the whole pipeline on this platform
        f1 = A.fit(P1, s1)
        q, e = refit([f1["params"][n] for n in NAMES], P3, s3)
        st = stats(e)
        d2 = max([abs(q["TA"] - r["val_refit"]["TA"])] + [abs(st[k] - r[k]) for k in STATS])
        iv, iv_ref = invariants(f1["params"], s1[0]), invariants(r["dev_fit"]["params"], s1[0])
        d3 = max(abs(iv[k] - iv_ref[k]) / abs(iv_ref[k]) for k in iv)
        good = d1 <= TOL_C and d2 <= TOL_C and d3 <= TOL_REL and len(e) == r["val_samples"]
        ok = ok and good
        report[sname] = {"ok": good, "frozen_rates_refit_max_diff_degC": d1, "pipeline_max_diff_degC": d2,
                         "pipeline_invariants_max_rel_diff": d3, "TA": q["TA"], **st,
                         "not_compared_rates_here": {n: f1["params"][n] for n in NAMES[:4]},
                         "not_compared_c0_here": q["c0"], "c0_in_step3_eval": r["val_refit"]["c0"]}
        if sname == "Ts0P":
            fig = (t3, P3, s3, s3 + ef, ef)
    print(json.dumps({"reproduced": ok, **report}, indent=1))
    if "--figdata" in sys.argv:
        t, P, s, fit, e = fig
        with open(sys.argv[sys.argv.index("--figdata") + 1], "w") as f:
            f.write("t_min P_W Ts0P_meas Ts0P_fit resid_meas_minus_fit\n")
            for row in zip(t / 60, P, s, fit, -e):
                f.write("{:.4f} {:.3f} {:.4f} {:.4f} {:.4f}\n".format(*row))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
