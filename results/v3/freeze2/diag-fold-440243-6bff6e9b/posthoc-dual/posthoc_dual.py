"""Post-hoc, exploratory (not one of Q1-Q5): does a failed attempt still give a certified bound?

For each saved fold LP of 440243's t = 945 fold (lp-dirI.npz), and each of the frozen three attempts:
  - the status, and whether HiGHS returned multipliers;
  - if so, certified_max(harden=True) with those multipliers (weak duality holds for any multipliers, since every
    variable is boxed), and exact_bound(), the same bound in exact rationals;
  - the box-only bound (all multipliers zero), which is valid too.
For direction 40, also: the support in direction 40 implied by the other 41 faces of the new base (3 variables),
with the values the rebuild found, to see how much a loose value for face 40 would matter at this fold.
usage: python -B posthoc_dual.py DIAG_DIR REPO_ROOT
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

diag, root = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(root / "experiments" / "v3" / "diag"))
for sub in ("experiments/v3", "experiments/oracle", "experiments/machine", "experiments/generators", "env"):
    sys.path.insert(0, str(root / sub))
import diag_fold_440243 as DF  # noqa: E402
import diag3_cw as C  # noqa: E402

d = json.loads((diag / "diag.json").read_text())
out = {}
for i in d["failing_directions"]:
    lp = DF.load_lp(diag / f"lp-dir{i}.npz")
    kw = {k: lp[k] for k in ("A_ub", "b_ub", "A_eq", "b_eq", "bounds")}
    rows = []
    for method, opts in DF.FROZEN_ATTEMPTS:
        res = linprog(lp["c"], method=method, options=opts, **kw)
        r = {"method": method, "presolve": opts.get("presolve", True), "status": int(res.status),
             "value": None if res.status != 0 else float(-res.fun),
             "multipliers": res.ineqlin.marginals is not None and res.eqlin.marginals is not None}
        if r["multipliers"]:
            C.Rec.last = (lp["c"], kw, res)
            cub = C.certified_max(True)
            ex = C.exact_bound()
            r.update(certified_bound=float(cub), exact=float(ex), float_ge_exact=bool(C.Fraction(cub) >= ex))
        rows.append(r)

    class Z:                                                      # all multipliers zero: the box-only bound
        pass
    z = Z()
    z.ineqlin, z.eqlin = Z(), Z()
    z.ineqlin.marginals = np.zeros(0 if lp["A_ub"] is None else lp["A_ub"].shape[0])
    z.eqlin.marginals = np.zeros(0 if lp["A_eq"] is None else lp["A_eq"].shape[0])
    C.Rec.last = (lp["c"], kw, z)
    out[i] = {"attempts": rows, "box_only_bound": float(C.certified_max(True))}

vals = {v["dir"]: v for v in d["q3_rebuild_values"]}
import template_state as V  # noqa: E402
m = json.loads((root / "experiments/v3/frozen/MANIFEST-V2.json").read_text())
tp = V.load_frozen(root / m["candidate"]["directions_file"], m["candidate"]["directions_sha256"])
D = tp.D
k40 = 40
others = [k for k in range(len(D)) if k != k40 and "value" in vals[k]]
b = np.array([max(vals[k]["value"] + C.PAD, vals[k]["certified_bound"]) for k in others])
res = linprog(-D[k40], A_ub=D[others], b_ub=b, bounds=[(None, None)] * 3, method="highs")
out["implied_support_dir40"] = {"status": int(res.status), "value": None if res.status != 0 else float(-res.fun),
                                "apriori": d["apriori_support"][k40],
                                "previous_base": d["q4_q5"][str(k40)]["previous_base"]}
print(json.dumps(out, indent=1))
