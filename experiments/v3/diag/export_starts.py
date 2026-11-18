"""Export the DIAG-1 start sets for the independent check (task T2b): per run and L, k0, the directions D, the
constraint caps the exact arms apply at every step (TA box, implied ac/as box, reachable-set clamps), and the start
supports H_k0 = hull_D(X_k0) (arm B) and P_k0 (cyl16p's state after measurement k0; arm E), as float.hex.
usage: python -B export_starts.py RUN_DIR
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent), str(HERE.parent.parent / "generators")]
import template_state as V  # noqa: E402
from diag1 import Exact  # noqa: E402

run_dir = Path(sys.argv[1])
cy = V.load_frozen(HERE.parent / "frozen" / "cyl16p.json")
ex = Exact(cy)
hx = lambda a: [float(x).hex() for x in np.ravel(a)]
for pkl in sorted(run_dir.glob("base-*.pkl")):
    rec = pickle.load(open(pkl, "rb"))
    seed, cell, amb = pkl.stem.split("-", 1)[1].split("-")
    for k0, X in sorted(rec["X"].items()):
        H = (X @ cy.D.T).max(axis=0)
        P = rec["P_tight"][k0]
        out = {"seed": int(seed), "cell": cell, "ambient": amb, "arm": "E0", "noise": "uniform", "k0": k0,
               "t_star": rec["t_exact"], "after_measurement_k0": True,
               "D": [hx(d) for d in cy.D], "caps": [hx([c]) [0] for _, c in ex.cons],
               "caps_directions": [hx(d) for d, _ in ex.cons],
               "H_k0_arm_B": hx(H), "P_k0_arm_E": hx(P),
               "step": "x_j = M x_{j-1} + e3 w_j, |w_j| <= RHO_A; on every x_j (j > k0): caps_directions . x_j <= caps; "
                       "measurement j applied as |z_j - 25 - x_j[1]| <= DELTA for j < t*; at t*: the range of x_t*[1] "
                       "before measurement t*",
               "margin": "min(zs + DELTA - lower, upper - (zs - DELTA)), zs = z_t* - 25; negative = inconsistent"}
        (run_dir / f"starts-{seed}-{cell}-{amb}-k0{k0}.json").write_text(json.dumps(out, indent=1) + "\n")
        print(pkl.stem, k0)
