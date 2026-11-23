"""Lemma lem:ocert (the oracle's upper certificate), a numerical sanity check (RECORD-2026-11-23-review3-checks.md).

For a path type and 3,600 samples, the oracle's own functions (_project, _residual_range, _forward with offset 0.0)
against the binary64 matrix taken exactly (fractions) along the projected path: every exact z_k - a_s,k must lie in
the returned interval [low, high], and max_k |z_k - a_s,k| <= d_up. Also reported: the largest error of the oracle's
float simulation of z - a_s in units of u * sigma, beside the lemma's bound (3.01 m + 4.2) and the pad 64 (m + 1).
Not part of the proof.

Path types (shifted units, box [-2, 2]):
  walk   random steps up to 1.5 rho from a random start, measurements within 0.3 (the first version of this check)
  top    T_A at +2 throughout, z = -2.3 (the wall)
  bottom T_A at -2 throughout, z = +2.3
  fault  T_A at +2, z = 350 (a measurement far outside, so sigma = 350)
  ramp   T_A ramps at rate rho from -2 to +2 and back, crossing the binades at +-1, z = T_A

  python -B experiments/v3/diag/ocert_check.py TYPE [SEED]      (from the repository root; about 50 s per type)
"""
import random
import sys
import time
from fractions import Fraction as Fr

import numpy as np

sys.path.insert(0, "experiments/oracle")
sys.path.insert(0, "experiments/generators")
import thermal_oracle as O  # noqa: E402

T = O.T
U = Fr(1, 2 ** 53)
A11, A12, A21, A22, B2 = (Fr(x) for x in (O.A11, O.A12, O.A21, O.A22, O.B2))
M = 3600
LO, HI = T.TA_LO - O.SHIFT, T.TA_HI - O.SHIFT


def paths(kind, seed):
    rnd = random.Random(seed)
    if kind == "walk":
        raw = [rnd.uniform(LO, HI)]
        for _ in range(1, M):
            raw.append(raw[-1] + rnd.choice([-1, 1]) * T.RHO_A * rnd.uniform(0.5, 1.5))
        return raw, None
    if kind == "top":
        return [HI] * M, [-2.3] * M
    if kind == "bottom":
        return [LO] * M, [2.3] * M
    if kind == "fault":
        return [HI] * M, [350.0] * M
    if kind == "ramp":
        raw, x, step = [], LO, T.RHO_A
        for _ in range(M):
            raw.append(x)
            if not LO <= x + step <= HI:
                step = -step
            x += step
        return raw, list(raw)
    raise SystemExit(f"unknown type {kind}")


def main(kind, seed):
    raw, z = paths(kind, seed)
    TA = [float(x) for x in O._project(raw, True, True)]
    if z is None:
        rnd = random.Random(seed + 1)
        z = [x + rnd.uniform(-0.3, 0.3) for x in TA]
    zn = np.asarray(z, dtype=float)                 # the oracle passes numpy arrays
    low, high = O._residual_range(raw, zn, True, True)
    d_up = O._forward(raw, zn, 0.0, True, True)
    t0 = time.time()
    ac = as_ = TA[0]                                  # the oracle's float simulation, as in _residual_range
    eac = eas = Fr(TA[0])
    worst, inside, ex_max = Fr(0), True, Fr(0)
    for k in range(M):
        exact = Fr(z[k]) - eas
        worst = max(worst, abs(Fr(z[k] - as_) - exact))
        inside &= Fr(low) <= exact <= Fr(high)
        ex_max = max(ex_max, abs(exact))
        ac, as_ = O.A11 * ac + O.A12 * as_, O.A21 * ac + O.A22 * as_ + O.B2 * TA[k]
        eac, eas = A11 * eac + A12 * eas, A21 * eac + A22 * eas + B2 * Fr(TA[k])
    sigma = Fr(max(1.0, max(abs(x) for x in TA), max(abs(x) for x in z)))
    adm = all(abs(Fr(TA[k]) - Fr(TA[k - 1])) <= Fr(T.RHO_A) for k in range(1, M)) and all(LO <= x <= HI for x in TA)
    print(f"{kind} seed {seed}: admissible {adm}, exact residuals inside [low, high] {inside}, "
          f"max|exact| <= d_up {ex_max <= Fr(d_up)}, worst |err| / (u sigma) {float(worst / (U * sigma)):.3f}, "
          f"bound {3.01 * M + 4.2}, pad / (u sigma) {64 * (M + 1)}, sigma {float(sigma)}, {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1)
