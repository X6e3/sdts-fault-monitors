"""Post-hoc, exploratory: the primal point HiGHS reports with status 4 for direction 40 (t = 945 fold of 440243).
Its objective is a lower estimate of the support only if the point is feasible, so the residuals are reported too.
usage: python -B posthoc_primal.py DIAG_DIR REPO_ROOT"""
import json, sys
from pathlib import Path
import numpy as np
from scipy.optimize import linprog
diag, root = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(root / "experiments" / "v3" / "diag"))
import diag_fold_440243 as DF
lp = DF.load_lp(diag / "lp-dir40.npz")
kw = {k: lp[k] for k in ("A_ub", "b_ub", "A_eq", "b_eq", "bounds")}
out = []
for method, opts in DF.FROZEN_ATTEMPTS + DF.OTHER_SETTINGS:
    res = linprog(lp["c"], method=method, options=opts, **kw)
    r = {"method": method, "presolve": opts.get("presolve", True), "status": int(res.status), "x": res.x is not None}
    if res.x is not None:
        x = res.x
        lb, ub = kw["bounds"][:, 0], kw["bounds"][:, 1]
        r["objective"] = float(-lp["c"] @ x)
        r["max_ub_violation"] = float(max(0.0, (kw["A_ub"] @ x - kw["b_ub"]).max()))
        r["max_eq_residual"] = float(np.abs(kw["A_eq"] @ x - kw["b_eq"]).max())
        r["max_box_violation"] = float(max(0.0, (lb - x).max(), (x - ub).max()))
    out.append(r)
print(json.dumps(out, indent=1))
