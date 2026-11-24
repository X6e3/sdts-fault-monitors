"""Reproduces the J713 step-3 evaluation (PLAN-step3.md section 4) from the released columns in data/j713/.

The frozen eval_step3.py reads the full logs, which also hold sensor columns that are not released; this script
reads only the released ones (time, PSTR, Ts0P, Ts1P) and calls the same model and fit (analyze.simulate,
analyze.fit) and the same refit of TA and c0, so it must give step3-eval.json's numbers. It can also write the
measured and fitted Ts0P of step 3 for the figure.

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


def main():
    out = {"dev": "step1", "val": "step3", "sensors": {}}
    fig = None
    for sname in ("Ts0P", "Ts1P"):
        P1, s1, _ = series("step1", sname)
        f1 = A.fit(P1, s1)
        p = [f1["params"][n] for n in ("kc", "bc", "ks", "hs", "TA", "c0")]
        P3, s3, t3 = series("step3", sname)
        q, e = refit(p, P3, s3)
        out["sensors"][sname] = {"dev_fit": f1, "val_refit": q, "val_rms": float(np.sqrt(np.mean(e ** 2))),
                                 "val_p99_abs": float(np.percentile(np.abs(e), 99)),
                                 "val_max_abs": float(np.max(np.abs(e))), "val_samples": int(len(e))}
        if sname == "Ts0P":
            fig = (t3, P3, s3, s3 + e, e)
    ref = json.loads((HERE / "step3-eval.json").read_text())
    same = all(out["sensors"][s][k] == ref["sensors"][s][k] for s in ("Ts0P", "Ts1P")
               for k in ("dev_fit", "val_refit", "val_rms", "val_p99_abs", "val_max_abs", "val_samples"))
    print(json.dumps({"equal_to_step3_eval_json": same,
                      "Ts0P": {k: out["sensors"]["Ts0P"][k] for k in ("val_rms", "val_p99_abs", "val_max_abs")}}, indent=1))
    if "--figdata" in sys.argv:
        t, P, s, fit, e = fig
        with open(sys.argv[sys.argv.index("--figdata") + 1], "w") as f:
            f.write("t_min P_W Ts0P_meas Ts0P_fit resid_meas_minus_fit\n")
            for row in zip(t / 60, P, s, fit, -e):
                f.write("{:.4f} {:.3f} {:.4f} {:.4f} {:.4f}\n".format(*row))
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
