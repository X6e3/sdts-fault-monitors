"""Evaluation of PLAN-step3.md, run once on the validation run (step3) after it is recorded.

  python3 -I -B eval_step3.py step1 step3 > step3-eval.json

The two-node model and the fit are those of analyze.py. The four rate parameters (kc, bc, ks, hs) are fitted on
step1 (development) and frozen; on step3 only the constant ambient TA and the initial core state c0 are refitted.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as A          # noqa: E402
from scipy.optimize import least_squares  # noqa: E402


def series(d, sname):        # as crossval.py
    col, ph = A.load(Path(d))
    sig = A.signals(col)
    return sig["P_PSTR"], sig[sname], col["t_mono"], ph


def predict(p, P, s, free=("TA", "c0")):   # as crossval.py: only TA and c0 refitted
    names = ("kc", "bc", "ks", "hs", "TA", "c0")
    base = dict(zip(names, p))

    def res(q):
        pp = dict(base)
        pp.update(zip(free, q))
        return A.simulate([pp[n] for n in names], P, s[0])[1] - s
    r = least_squares(res, [base[n] for n in free])
    return dict(zip(free, map(float, r.x))), res(r.x)


def main(dev, val):
    out = {"dev": dev, "val": val, "sensors": {}}
    for sname in ("Ts0P", "Ts1P"):
        P1, s1, _, _ = series(dev, sname)
        f1 = A.fit(P1, s1)
        p = [f1["params"][n] for n in ("kc", "bc", "ks", "hs", "TA", "c0")]
        P3, s3, _, _ = series(val, sname)
        q, e = predict(p, P3, s3)
        out["sensors"][sname] = {
            "dev_fit": f1,
            "val_refit": q,
            "val_rms": float(np.sqrt(np.mean(e ** 2))),
            "val_p99_abs": float(np.percentile(np.abs(e), 99)),
            "val_max_abs": float(np.max(np.abs(e))),
            "val_samples": int(len(e)),
        }
    t = out["sensors"]["Ts0P"]
    out["delta_required_Ts0P"] = t["val_max_abs"]   # the noise bound this device would need (primary, reported)
    out["criterion"] = {"rms_le_0.25": t["val_rms"] <= 0.25, "max_le_0.60": t["val_max_abs"] <= 0.60}
    out["verdict"] = "PASS" if all(out["criterion"].values()) else "FAIL"
    return out


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1], sys.argv[2]), indent=1))
