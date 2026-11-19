"""DIAG-3 amendment 9: the model behind F's certificate, checked.

1. Rows: the float M read as rationals, and the exact recurrence of thermal.py's step() (exact_matrix()).
2. Powers: each of F's coefficients (POWX) is the exact power of the exact recurrence, rounded once; and how far the
   float M's exact powers are from it, in units of u.
3. Clamps: every cyl16p clamp (cap_inv) bounds d.x over the reachable set of the exact recurrence:
   sup d.x = max(sigma HI, sigma LO) + rho sum_j |q . M22^j g|, with e = (ac - TA, as - TA), e' = M22 e + g w,
   g = -(1, 1), e0 = 0. 60-digit decimals, N exact terms, a tail bound, and a 1e-40 allowance on both sides.
4. Data: |zs_float - zs_exact| on healthy DEV runs, with zs_exact from step() in 80-digit decimals on the same float
   inputs. It must stay far below ETA.
Added for the freeze-2 review (exact rational arithmetic throughout):
3'. clamps_exact: section 3 with no decimal rounding and no allowance.
5. oracle_gap: a bound on |as(Mf) - as(MX)| for the same admissible TA path over the record, Mf the oracle's float
   matrix; it ties the oracle's consistent verdicts to F's model.
6. ambient_rounding: how far the generated ambient increments exceed RHO_A by float rounding, and the box.

usage: python -B check_model.py [--seeds 430000 430005] [--out check-model.json]
"""
import argparse
import json
import math
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


def clamps_exact(n_terms=6000, m=64):
    """Section 3 in exact rational arithmetic, with no allowance: M22 = N / L with N an integer matrix, so
    M22^j g = w_j / L^j with integer w_j, and sum_j |q . w_j| / L^j is accumulated by Horner's rule.
    Tail: every entry of M22 is >= 0 and its rows sum to at most 1, so ||M22^j||_inf <= 1; with
    c = ||M22^m||_inf < 1, sum_{j >= n} ||M22^j g||_inf <= m ||M22^n g||_inf / (1 - c)."""
    tp = V.load_frozen(C.G.V3 / "frozen" / "cyl16p.json")
    m22 = [[C.MX[i][j] for j in range(2)] for i in range(2)]
    assert all(x >= 0 for r in m22 for x in r) and all(sum(r) <= 1 for r in m22)
    L = 1
    for x in (y for r in m22 for y in r):
        L = L * x.denominator // math.gcd(L, x.denominator)
    N = [[int(x * L) for x in r] for r in m22]
    assert all(Fraction(N[i][j], L) == m22[i][j] for i in range(2) for j in range(2))
    qs = []
    for d in tp.D:
        q0, q1 = Fraction(float(d[0])), Fraction(float(d[1]))
        Q = q0.denominator * q1.denominator // math.gcd(q0.denominator, q1.denominator)
        qs.append((int(q0 * Q), int(q1 * Q), Q, q0, q1, sum(Fraction(float(x)) for x in d)))
    acc = [0] * len(qs)
    w = (-1, -1)
    for _ in range(n_terms):
        for i, (r0, r1, *_rest) in enumerate(qs):
            acc[i] = acc[i] * L + abs(r0 * w[0] + r1 * w[1])
        w = (N[0][0] * w[0] + N[0][1] * w[1], N[1][0] * w[0] + N[1][1] * w[1])
    vinf = Fraction(max(abs(w[0]), abs(w[1])), L ** n_terms)            # ||M22^n g||_inf
    A = [[Fraction(int(i == j)) for j in range(2)] for i in range(2)]
    for _ in range(m):
        A = [[A[i][0] * m22[0][j] + A[i][1] * m22[1][j] for j in range(2)] for i in range(2)]
    c = max(A[0][0] + A[0][1], A[1][0] + A[1][1])
    assert c < 1
    rho, hi, lo = Fraction(T.RHO_A), Fraction(T.TA_HI) - 25, Fraction(T.TA_LO) - 25
    slack, below, den = None, [], L ** (n_terms - 1)
    for i, (r0, r1, Q, q0, q1, sigma) in enumerate(qs):
        s = Fraction(acc[i], Q * den)
        tail = (abs(q0) + abs(q1)) * vinf * m / (1 - c)
        ub = max(sigma * hi, sigma * lo) + rho * (s + tail)
        sl = Fraction(float(tp.cap_inv[i])) - ub
        slack = sl if slack is None or sl < slack else slack
        if sl < 0:
            below.append(i)
    return {"directions": len(qs), "clamps_not_proved": below, "smallest_slack_C": float(slack),
            "smallest_slack_C_is_exact_rational_rounded_to_float": True, "terms": n_terms, "tail_rows_c": float(c)}


def oracle_gap(n=T.N):
    """The oracle (experiments/oracle/thermal_oracle.py) explains z with the float matrix Mf (A11 ... B2 built entry
    by entry), the steady start ac = as = TA[0], an exactly admissible TA path (projected) and |z - as| <= d_up,
    with d_up enclosing its own float rounding. Run the same TA path through the exact recurrence MX. With
    d_k = x_k(Mf) - x_k(MX): d_0 = 0, the TA parts agree, and d_{k+1} = Mf d_k + (Mf - MX) x_k(MX), where
    |x_k(MX)| <= 2 componentwise (ac and as are convex combinations of TA in [-2, 2]). So
    |d_k|_inf <= e sum_{i<k} ||Mf22||_inf^i with e = 2 max_r sum_c |Mf - MX|_rc (rows ac and as).
    Exact rationals; the bound holds for every admissible TA path and every k <= n."""
    Mf = [[Fraction(float(M[i, j])) for j in range(3)] for i in range(3)]
    e = 2 * max(sum(abs(Mf[r][c] - C.MX[r][c]) for c in range(3)) for r in range(2))
    nf = max(abs(Mf[r][0]) + abs(Mf[r][1]) for r in range(2))
    total, p = Fraction(0), Fraction(1)
    for _ in range(n):
        total += e * p
        p *= nf
    return {"e_per_step_C": float(e), "Mf22_inf_norm_minus_1": float(nf - 1), "steps": n,
            "as_gap_bound_C": float(total), "ETA_C": C.ETA, "ETA_over_bound": float(Fraction(C.ETA) / total)}


def ambient_rounding(seeds):
    """The generated ambient path is the plant's input; its increments are float sums, so |TA[k+1] - TA[k]| can
    exceed RHO_A by rounding. Measured exactly on the DEV healthy runs used in section 4. Projecting the path onto
    the admissible set (each step clipped to the rate bound, then to the box) moves TA[k] by at most k times the
    excess, and as by no more, since the exact recurrence is a convex filter of TA."""
    worst, box_ok, n = None, True, 0
    rho = Fraction(T.RHO_A)
    for seed in range(seeds[0], seeds[1] + 1):
        for amb in ("rw", "ramp"):
            ta = [Fraction(x) for x in C.S.ambient(seed, amb)]
            box_ok &= all(Fraction(T.TA_LO) <= x <= Fraction(T.TA_HI) for x in ta)
            w = max(abs(b - a) - rho for a, b in zip(ta, ta[1:]))
            worst = w if worst is None else max(worst, w)
            n += 1
    half_ulp = Fraction(math.ulp(T.TA_HI)) / 2
    return {"paths": n, "rate_excess_max_C": float(worst), "box_holds": bool(box_ok),
            "a_priori_excess_C": float(half_ulp), "projection_shift_bound_C": float(half_ulp * (T.N - 1))}


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
    out = {"rows": r, "powers": powers(mf, len(C.POWX) - 1), "clamps": clamps(), "clamps_exact": clamps_exact(),
           "oracle_gap": oracle_gap(), "ambient_rounding": ambient_rounding(a.seeds), "data": data(a.seeds)}
    out["pass"] = (out["rows"]["exact_row_sums_minus_1"] == [0.0, 0.0] and out["powers"]["POWX_is_the_exact_power_rounded_once"]
                   and not out["clamps"]["clamps_not_proved"] and not out["clamps_exact"]["clamps_not_proved"]
                   and out["oracle_gap"]["as_gap_bound_C"] < C.ETA / 100
                   and out["ambient_rounding"]["box_holds"]
                   and out["ambient_rounding"]["rate_excess_max_C"] <= out["ambient_rounding"]["a_priori_excess_C"]
                   and out["data"]["max_abs_zs_error_C"] < C.ETA / 100)
    import subprocess
    out["meta"] = {"git_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, capture_output=True,
                                              text=True).stdout.strip(),
                   "git_dirty_tracked": bool(subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=HERE).returncode),
                   "seeds": list(a.seeds)}
    text = json.dumps(out, indent=1)
    print(text)
    if a.out:
        a.out.write_text(text + "\n")


if __name__ == "__main__":
    main()
