"""Lemma lem:olow (the oracle's lower certificate), a numerical sanity check (RECORD-2026-11-23-review3-checks.md).

For the validation 3 events with the smallest inconsistent room (RECORD-2026-11-23-oracle-margin.md), the prefix
z[0:t*+1] is regenerated, the oracle's LP solved with each of its attempts, and its lower certificate (_dual_bound,
in floating point) compared with the same weak-duality bound in exact arithmetic (fractions): the sum of the exact
products of right-hand sides and bounds with the multipliers the code uses, minus the exact stationarity residual
against the stored caps. The float value must not exceed the exact one. Not part of the proof.

  python -B experiments/v3/diag/olow_check.py        (from the repository root; the project Python)
"""
import hashlib
import sys
import tempfile
from fractions import Fraction as Fr
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
for sub in ("experiments/v3", "experiments/oracle", "experiments/machine", "experiments/generators", "env"):
    sys.path.insert(0, str(ROOT / sub))
import dev_scenarios as S  # noqa: E402
import thermal_oracle as O  # noqa: E402

T = O.T
MAN = ROOT / "experiments/v3/frozen/MANIFEST-V3.json"
EVENTS = [(440402, "drift_0.0005", "E0", "ramp", 1414), (440402, "drift_0.0005", "E1", "ramp", 1414)]


def exact_bound(res, c, Aub, bub, Aeq, beq, bounds, caps):
    lo = [b[0] for b in bounds]
    up = [b[1] for b in bounds]
    y_ub = np.minimum(res.ineqlin.marginals, 0.0)
    y_eq = res.eqlin.marginals
    lam_l = [max(float(x), 0.0) if lo[j] is not None else 0.0 for j, x in enumerate(res.lower.marginals)]
    lam_u = [min(float(x), 0.0) if up[j] is not None else 0.0 for j, x in enumerate(res.upper.marginals)]
    n = len(c)
    r = [Fr(float(c[j])) - Fr(lam_l[j]) - Fr(lam_u[j]) for j in range(n)]
    for A, y in ((Aub.tocoo(), y_ub), (Aeq.tocoo(), y_eq)):
        for i, j, v in zip(A.row, A.col, A.data):
            r[j] -= Fr(float(v)) * Fr(float(y[i]))
    terms = sum(Fr(float(b)) * Fr(float(y)) for b, y in zip(bub, y_ub))
    terms += sum(Fr(float(b)) * Fr(float(y)) for b, y in zip(beq, y_eq))
    terms += sum(Fr(lo[j]) * Fr(lam_l[j]) for j in range(n) if lo[j] is not None)
    terms += sum(Fr(up[j]) * Fr(lam_u[j]) for j in range(n) if up[j] is not None)
    return terms - sum(abs(r[j]) * Fr(float(caps[j])) for j in range(n))


def main():
    S.unlock_validation(hashlib.sha256(MAN.read_bytes()).hexdigest())
    for seed, cell, arm, amb, ts in EVENTS:
        c_ = next(c for c in T.CELLS if c.name == cell)
        z = S.run(seed, c_, arm, amb, "uniform")["z"]
        m = ts + 1
        c, Aub, bub, Aeq, beq, bounds, zs = O._build(z, m, True, True, "margin", 0.0)
        caps = O._optimum_caps(zs, True, True, "margin")
        with tempfile.TemporaryDirectory() as d:
            for method, presolve in O.ATTEMPTS:
                res = O._attempt(z, m, True, True, "margin", 0.0, method, presolve, Path(d))
                if res is None or res.status != 0:
                    print(seed, cell, arm, amb, method, presolve, "no solution")
                    continue
                d_lo = O._dual_bound(res, c, Aub, bub, Aeq, beq, bounds, caps)
                ex = exact_bound(res, c, Aub, bub, Aeq, beq, bounds, caps)
                ok = d_lo is None or Fr(d_lo) <= ex
                print(f"{seed} {cell} {arm} {amb} m={m} {method} presolve={presolve}: d_lo {d_lo!r}, exact bound "
                      f"{float(ex)!r}, d_lo - delta {None if d_lo is None else d_lo - T.DELTA:.6e}, "
                      f"exact - d_lo {None if d_lo is None else float(ex - Fr(d_lo)):.3e}, float <= exact {ok}")


if __name__ == "__main__":
    main()
