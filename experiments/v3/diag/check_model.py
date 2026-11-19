"""DIAG-3 amendment 9: the model behind F's certificate, checked.

1. Rows: the float M read as rationals, and the exact recurrence of thermal.py's step() (exact_matrix()).
2. Powers: each of F's coefficients (POWX) is the exact power of the exact recurrence, rounded once; and how far the
   float M's exact powers are from it, in units of u.
3. Clamps: every cyl16p clamp (cap_inv) bounds d.x over the reachable set of the exact recurrence:
   sup d.x = max(sigma HI, sigma LO) + rho sum_j |q . M22^j g|, with e = (ac - TA, as - TA), e' = M22 e + g w,
   g = -(1, 1), e0 = 0. 60-digit decimals, N exact terms, a tail bound, and a 1e-40 allowance on both sides.
4. Data: |zs_float - zs_exact| on healthy DEV runs, with zs_exact from step() in 80-digit decimals on the same float
   inputs. It must stay far below ETA.

usage: python -B check_model.py [--seeds 430000 430005] [--out check-model.json]
"""
import argparse
import json
import sys
from decimal import Decimal as D, localcontext
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diag3_cw as C  # noqa: E402

T, V, M = C.T, C.V, C.M
U = Fraction(1, 2 ** 53)


def rows():
    mf = [[Fraction(float(M[i, j])) for j in range(3)] for i in range(3)]
    return {"float_M_row_sums_minus_1_in_2^-56": [float((sum(r) - 1) * 2 ** 56) for r in mf[:2]],
            "exact_row_sums_minus_1": [float(sum(r) - 1) for r in C.MX[:2]]}, mf


def powers(mf, n):
    mul = lambda A, B: [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    I3 = [[Fraction(int(i == j)) for j in range(3)] for i in range(3)]
    pf, px, worst, once = I3, I3, (0, 0), True
    for L in range(1, n + 1):
        pf, px = mul(pf, mf), mul(px, C.MX)
        for i in range(3):
            for j in range(3):
                once &= Fraction(float(C.POWX[L][i, j])) == Fraction(float(px[i][j]))
                once &= abs(Fraction(float(px[i][j])) - px[i][j]) <= U * abs(px[i][j])
                if px[i][j] != 0:
                    r = abs(pf[i][j] - px[i][j]) / abs(px[i][j])
                    worst = max(worst, (r, L))
    return {"POWX_is_the_exact_power_rounded_once": bool(once), "L_max": n,
            "float_M_power_gap_max_in_u": float(worst[0] / U), "at_L": worst[1]}


def clamps(n_terms=6000):
    tp = V.load_frozen(C.G.V3 / "frozen" / "cyl16p.json")
    with localcontext() as ctx:
        ctx.prec = 60
        cc, cs, k, h, dt = (D(x) for x in (T.CC, T.CS, T.K, T.H, T.DT))
        a11, a12, a21, a22 = 1 - dt * k / cc, dt * k / cc, dt * k / cs, 1 - dt * (k + h) / cs
        rho, hi, lo = D(T.RHO_A), D(T.TA_HI) - 25, D(T.TA_LO) - 25
        vs, v = [], (D(-1), D(-1))
        for _ in range(n_terms):
            vs.append(v)
            v = (a11 * v[0] + a12 * v[1], a21 * v[0] + a22 * v[1])
        m, A = 64, [[D(1), D(0)], [D(0), D(1)]]
        for _ in range(m):
            A = [[A[i][0] * a11 + A[i][1] * a21, A[i][0] * a12 + A[i][1] * a22] for i in range(2)]
        c = max(abs(A[i][0]) + abs(A[i][1]) for i in range(2))
        assert c < 1
        vinf, allow = max(abs(v[0]), abs(v[1])), D("1e-40")
        slack, below = None, []
        for i, d in enumerate(tp.D):
            dq = [D(float(x)) for x in d]
            sigma, q = sum(dq), dq[:2]
            s = sum(abs(q[0] * x + q[1] * y) for x, y in vs)
            tail = (abs(q[0]) + abs(q[1])) * vinf * m / (1 - c)
            ub = max(sigma * hi, sigma * lo) + rho * (s + tail) + allow
            cap = D(float(tp.cap_inv[i]))
            slack = cap - ub if slack is None or cap - ub < slack else slack
            if cap < ub:
                below.append(i)
        return {"directions": len(tp.D), "clamps_not_proved": below, "smallest_slack_C": float(slack),
                "terms": n_terms, "tail_bound_C": float(rho * vinf * m / (1 - c) * 2)}


def data(seeds):
    healthy = next(c for c in T.CELLS if c.name == "healthy")
    worst, n = 0.0, 0
    with localcontext() as ctx:
        ctx.prec = 80
        cc, cs, k, h, dt = (D(x) for x in (T.CC, T.CS, T.K, T.H, T.DT))

        def sim(P, TA, x0):
            tc, ts = x0
            out = []
            for p, ta in zip(P, TA):
                out.append(ts)
                tc, ts = tc + dt * (p - k * (tc - ts)) / cc, ts + dt * (k * (tc - ts) - h * (ts - ta)) / cs
            return out

        def eq(p, ta):
            ts = ta + p / h
            return ts + p / k, ts

        for seed in range(seeds[0], seeds[1] + 1):
            for arm in ("E0", "E1"):
                for amb in ("rw", "ramp"):
                    for nz in ("uniform", "edge"):
                        r = C.S.run(seed, healthy, arm, amb, nz)
                        P, TA, v = ([D(x) for x in r[key]] for key in ("P", "TA", "v"))
                        ts = sim(P, TA, eq(D(T.P0), TA[0]))
                        sk = sim(P, [D(0)] * len(P), eq(D(T.P0), D(0)))
                        zs = C.G.zs_of(r)
                        worst = max(worst, max(abs(float(D(z) - (a + b - c - 25))) for z, a, b, c in
                                               zip(zs, ts, v, sk)))
                        n += 1
    return {"healthy_runs": n, "seeds": list(seeds), "max_abs_zs_error_C": worst, "ETA_C": C.ETA,
            "ETA_over_max": C.ETA / worst if worst else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, nargs=2, default=[430000, 430005])
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    r, mf = rows()
    out = {"rows": r, "powers": powers(mf, len(C.POWX) - 1), "clamps": clamps(), "data": data(a.seeds)}
    out["pass"] = (out["rows"]["exact_row_sums_minus_1"] == [0.0, 0.0] and out["powers"]["POWX_is_the_exact_power_rounded_once"]
                   and not out["clamps"]["clamps_not_proved"] and out["data"]["max_abs_zs_error_C"] < C.ETA / 100)
    text = json.dumps(out, indent=1)
    print(text)
    if a.out:
        a.out.write_text(text + "\n")


if __name__ == "__main__":
    main()
