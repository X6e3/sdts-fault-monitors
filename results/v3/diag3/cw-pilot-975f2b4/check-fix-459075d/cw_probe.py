"""post-hoc probe of the largest C0 difference (430010, fold at t = 673, direction (1, -1, 0)/sqrt 2)"""
import json, sys
import numpy as np
from scipy.optimize import linprog
sys.path.insert(0, sys.argv[1])
import diag3_cw as C
seed, cell, amb = 430010, "drift_0.0005", "ramp"
t_star, _, zs, cy = C._run_info(seed, cell, amb)
a, e = C.W3.Window(cy, C.W, smooth=True), C.Compressed(cy, True, cert=False)
a.zs[0] = e.zs[0] = zs[0]
T_PROBE, d0 = 673, np.array([1.0, -1.0, 0.0]) / np.sqrt(2)
out = {}
for t in range(1, T_PROBE + 1):
    a.as_range(t), e.as_range(t)
    a.zs[t] = e.zs[t] = zs[t]
    if t - a.tau > C.W + C.B:
        tau2 = a.tau + C.B
        if t == T_PROBE:
            out["base_max_abs_diff_before"] = float(np.max(np.abs(a.base - e.base)))
            for name, win in (("dense", a), ("E", e)):
                v = win.lp(t, t, tau2, d0); c, kw, res = C.Rec.last
                x = res.x
                r_eq = float(np.max(np.abs(kw["A_eq"] @ x - kw["b_eq"]))) if kw.get("A_eq") is not None else 0.0
                r_ub = float(np.max(kw["A_ub"] @ x - kw["b_ub"])) if kw.get("A_ub") is not None else 0.0
                bnd = kw["bounds"]; r_bd = float(max(np.max(bnd[:, 0] - x), np.max(x - bnd[:, 1])))
                tight = linprog(c, method="highs-ds", options={"presolve": False, "primal_feasibility_tolerance": 1e-10,
                                "dual_feasibility_tolerance": 1e-10}, **{k: kw[k] for k in ("A_ub", "b_ub", "A_eq", "b_eq", "bounds")})
                C.Rec.last = (c, kw, tight)
                out[name] = {"value": v, "max_eq_residual": r_eq, "max_ub_violation": r_ub, "max_bound_violation": r_bd,
                             "value_tight_tol": -tight.fun, "status_tight": int(tight.status),
                             "dual_bound_tight": C.certified_max()}
            break
        va = [a.lp(t, t, tau2, d) for d in a.D]; vb = [e.lp(t, t, tau2, d) for d in e.D]
        C._fold_with(a, tau2, va); C._fold_with(e, tau2, vb)
print(json.dumps(out, indent=1))
