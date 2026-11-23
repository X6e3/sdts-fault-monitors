"""The frozen C template state against the exact recurrence: the gap of V3_NOTES section 5 and MCU-NOTES 2c.

The C state (c/v3_state.c with frozen/c/tables_cyl16p_{double,float}.h, freeze 1's cyl16p) computes the known
command part S in binary64 and its slab from z = y - S with a one-ulp outward rounding. Its tables were built
against the float matrix M. Theorem 2 (V3_NOTES) is stated for the exact model. F3 closed the same gap with
DIAG-3 amendment 9 (the exact recurrence and a data allowance eta); the C state has neither. This script checks,
in exact rational arithmetic, every step of Theorem 2's induction for the C state against the exact recurrence
MX (thermal.py's step() with its float parameters taken exactly; diag3_cw.exact_matrix()).

Criteria (fixed before the first run of this script):
  K1 tables: each frozen header is what codegen_c.py emits from frozen/cyl16p.json (text equal), so the values
     below are the header's values.
  K2 pads: for every entry e of every group g of each header: lam_e >= 0, and
        gamma3 * sum_j lam_e,j * HMAX + |g_true - sum_j lam_e,j d_idx(e,j)|_1 * CAP <= PAD_g,
     gamma3 = 3u/(1-3u) for the header's precision (a 3-term dot product), HMAX and CAP as in codegen_c.py,
     g_true = MX^T d_i for the prediction groups and +-e2 for the two as-range groups.
     Added 2026-11-23 (reviews r2, r3; RECORD-2026-11-23-review3-checks.md): the left side also carries 4 * tiny,
     tiny = 2^-1075 (binary64) or 2^-150 (binary32), a product's absolute loss under gradual underflow: three products,
     carried through two additions, lose at most 3 (1 + u)^2 tiny < 4 tiny. |h_i| <= HMAX holds while the exact set is
     nonempty: v3_observe keeps h_i <= CAP_i (at most 2.998 for cyl16p) and the start supports are clamped, and the
     measurement slab only lowers h_+-e2; and h_i, before and after that cut, is at least the support of the exact set,
     inside [-2, 2]^3, so at least -2 |d_i|_1 (at least -3.266 for cyl16p).
  K3 clamps: every header CAP_i >= the exact supremum of d_i . s over the reachable set of the exact recurrence
     (check_model.clamps_exact's bound, and the box [-2, 2] for the six axis directions).
  K4 rate pads: every header RHOPAD_i >= RHO_A |d_i3|.
  K5 start: every header H0_i >= 2 |sum_c d_ic|, the support of the start segment {t (1, 1, 1) : |t| <= 2}.
  K6 data: an a priori bound eps on |zs_C - zs_exact| for every admissible command sequence (P in [P_LO, P_HI])
     and every admissible record, where zs_exact uses the exact recurrence's S. Reported with the derivation;
     it must be below DIAG-3's ETA (1e-9), so that one allowance serves F3 and the C state.
Verdict: CLOSED if K1-K5 hold and K6's eps < ETA. Then the C state, in IEEE 754 binary64 round-to-nearest for S
and the header's precision for h, never flags a record that the exact recurrence explains with |v| <= DELTA - eps
(and (b), (c), (e)). Otherwise OPEN, with what fails.
Reported, not deciding: |S_float - S_exact| measured on DEV commands (80-digit decimals), and eps for a binary64
that is faithful only (the Uno, MCU-NOTES 2c): every u doubled.

usage: python -B check_c_state.py [--out FILE.json]
"""
import argparse
import hashlib
import json
import math
import sys
from decimal import Decimal as D, localcontext
from fractions import Fraction as Fr
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
V3 = HERE.parent
sys.path[:0] = [str(HERE), str(V3)]
import diag3_cw as C  # noqa: E402
import codegen_c as CG  # noqa: E402

T, V = C.T, C.V
FROZEN = V3 / "frozen" / "cyl16p.json"
TINY = Fr(1, 2 ** 1074)                     # bound on an absolute rounding error in the subnormal range


def headers():
    """K1, and the header values as exact rationals."""
    sha = hashlib.sha256(FROZEN.read_bytes()).hexdigest()
    out = {}
    for real in ("double", "float"):
        tp = V.load_frozen(FROZEN)
        tp, hmax, idx, lam, starts, pads = CG.build(None, 0, 0, real, template=tp)
        text = CG.emit(tp, hmax, idx, lam, starts, pads, real, f"frozen {FROZEN.name} sha256 {sha} {real}")
        same = text == (V3 / "frozen" / "c" / f"tables_cyl16p_{real}.h").read_text()
        up = lambda x: Fr(CG.up_to(x, real))
        out[real] = {
            "K1_header_equal": same, "tp": tp, "idx": idx, "lam": [[Fr(x) for x in r] for r in lam], "starts": starts,
            "pad": [up(p) for p in pads], "hmax": up(hmax), "cap_const": Fr(2.2),
            "rhopad": [up(math.nextafter(x, math.inf)) if x else Fr(0) for x in tp.rho_pad],
            "caps": [up(x) for x in CG._caps(tp)], "h0": [up(x) for x in tp.clamp(tp.h0)],
            "u": Fr(1, 2 ** 53) if real == "double" else Fr(1, 2 ** 24)}
    return out


def pads(h):
    """K2 for one header."""
    tp = h["tp"]
    Dq = [[Fr(float(x)) for x in d] for d in tp.D]
    MX = C.MX
    targets = [[sum(MX[k][j] * d[k] for k in range(3)) for j in range(3)] for d in Dq]      # MX^T d_i
    targets += [[Fr(0), Fr(1), Fr(0)], [Fr(0), Fr(-1), Fr(0)]]                                 # +e2, -e2
    u = h["u"]
    g3 = 3 * u / (1 - 3 * u)
    tiny = Fr(1, 2 ** 1075) if u == Fr(1, 2 ** 53) else Fr(1, 2 ** 150)      # 2026-11-23: gradual underflow
    worst, neg, bad = None, 0, []
    for g, tgt in enumerate(targets):
        for e in range(h["starts"][g], h["starts"][g + 1]):
            lam, ix = h["lam"][e], h["idx"][e]
            neg += sum(1 for x in lam if x < 0)
            res = sum(abs(tgt[c] - sum(lam[j] * Dq[ix[j]][c] for j in range(3))) for c in range(3))
            need = g3 * sum(lam) * h["hmax"] + res * h["cap_const"] + 4 * tiny
            sl = h["pad"][g] - need
            if worst is None or sl / h["pad"][g] < worst[0]:
                worst = (sl / h["pad"][g], g, e, float(need), float(h["pad"][g]))
            if sl < 0:
                bad.append([g, e, float(need), float(h["pad"][g])])
    return {"groups": len(targets), "entries": h["starts"][-1], "negative_lambdas": neg, "entries_not_covered": len(bad),
            "not_covered_first": bad[:10], "smallest_slack_fraction_of_pad": float(worst[0]),
            "at_group_entry": worst[1:3], "need_and_pad_there": worst[3:]}


def exact_sup(n_terms=6000, m=64):
    """check_model.clamps_exact's upper bound on sup d_i . s over the reachable set, per direction (exact)."""
    tp = V.load_frozen(FROZEN)
    m22 = [[C.MX[i][j] for j in range(2)] for i in range(2)]
    assert all(x >= 0 for r in m22 for x in r) and all(sum(r) <= 1 for r in m22)
    L = 1
    for x in (y for r in m22 for y in r):
        L = L * x.denominator // math.gcd(L, x.denominator)
    N = [[int(x * L) for x in r] for r in m22]
    qs = []
    for d in tp.D:
        q0, q1 = Fr(float(d[0])), Fr(float(d[1]))
        Q = q0.denominator * q1.denominator // math.gcd(q0.denominator, q1.denominator)
        qs.append((int(q0 * Q), int(q1 * Q), Q, q0, q1, sum(Fr(float(x)) for x in d)))
    acc, w = [0] * len(qs), (-1, -1)
    for _ in range(n_terms):
        for i, (r0, r1, *_r) in enumerate(qs):
            acc[i] = acc[i] * L + abs(r0 * w[0] + r1 * w[1])
        w = (N[0][0] * w[0] + N[0][1] * w[1], N[1][0] * w[0] + N[1][1] * w[1])
    vinf = Fr(max(abs(w[0]), abs(w[1])), L ** n_terms)
    A = [[Fr(int(i == j)) for j in range(2)] for i in range(2)]
    for _ in range(m):
        A = [[A[i][0] * m22[0][j] + A[i][1] * m22[1][j] for j in range(2)] for i in range(2)]
    c = max(A[0][0] + A[0][1], A[1][0] + A[1][1])
    assert c < 1
    rho, hi, lo = Fr(T.RHO_A), Fr(T.TA_HI) - 25, Fr(T.TA_LO) - 25
    den, ub = L ** (n_terms - 1), []
    for i, (r0, r1, Q, q0, q1, sigma) in enumerate(qs):
        s = Fr(acc[i], Q * den)
        tail = (abs(q0) + abs(q1)) * vinf * m / (1 - c)
        ub.append(max(sigma * hi, sigma * lo) + rho * (s + tail))
    return ub


def clamps_rate_start(h, ub):
    """K3, K4, K5 for one header."""
    tp = h["tp"]
    axis = set(tp.ip) | set(tp.im)
    k3, k4, k5 = [], [], []
    sl3 = sl5 = None
    for i, d in enumerate(tp.D):
        dq = [Fr(float(x)) for x in d]
        sup = min(ub[i], Fr(2)) if i in axis else ub[i]
        if h["caps"][i] < sup:
            k3.append(i)
        sl3 = h["caps"][i] - sup if sl3 is None else min(sl3, h["caps"][i] - sup)
        if h["rhopad"][i] < Fr(T.RHO_A) * abs(dq[2]):
            k4.append(i)
        s0 = 2 * abs(sum(dq))
        if h["h0"][i] < s0:
            k5.append([i, float(h["h0"][i]), float(s0)])
        sl5 = h["h0"][i] - s0 if sl5 is None else min(sl5, h["h0"][i] - s0)
    return ({"caps_not_proved": k3, "smallest_slack_C": float(sl3)}, {"rate_pads_too_small": k4},
            {"start_supports_too_small": k5, "smallest_slack_C": float(sl5)})


def data_bound(u):
    """K6: |zs_C - zs_exact| for every admissible command and record, from the standard model
    |fl(x) - x| <= u |x| + TINY. The C step (and thermal.step with ta = 0, DT = 1):
        a1 = fl(tc - ts); tc' = fl(tc + fl(fl(p - 2 a1) / CC)); ts' = fl(ts + fl(fl(2 a1 - fl(H ts)) / CS)).
    The exact recurrence on the same inputs is x' = A x + b p, A = MX[:2, :2], b = (DT/CC, 0). With e = x_C - x_exact,
    e' = A e + r, |r| <= R componentwise while the state stays in the invariant box, so
    |e_k| <= ||A||_inf^k |e_0|_inf + sum_j A^j R <= |e_0|_inf + (I - A)^-1 R (A >= 0, row sums 1 and 1 - H/CS).
    Invariant box of the exact recurrence for P in [P_LO, P_HI] from the P0 steady state: 0 <= ts <= P_HI/H,
    0 <= tc - ts <= P_HI/K (both shown in the notes); the bounds below add the final eps (an induction on k)."""
    CC, CS, K, H, DT = (Fr(x) for x in (T.CC, T.CS, T.K, T.H, T.DT))
    assert K == 2 and DT == 1
    A = [[C.MX[i][j] for j in range(2)] for i in range(2)]
    PHI, P0 = Fr(T.P_HI), Fr(T.P0)
    assert Fr(T.P_LO) == 0
    slack = Fr(1, 10 ** 9)                                   # induction hypothesis |e| <= 1e-9, checked below
    Bts = PHI / H + slack
    Bd = PHI / K + 2 * slack
    Btc = Bts + Bd
    q = 1 + u
    B3 = (PHI + 2 * Bd) * q                                  # |p - 2 a1|
    Rc = u * (Btc + B3 * q * q / CC) + u * B3 * q / CC + (u * B3 + 2 * u * Bd) / CC + 3 * TINY
    Bb3 = (2 * Bd * q + H * Bts * q) * q                     # |2 a1 - fl(H ts)|
    Rs = u * (Bts + Bb3 * q * q / CS) + u * Bb3 * q / CS + (u * Bb3 + 2 * u * Bd + u * H * Bts) / CS + 4 * TINY
    det = (1 - A[0][0]) * (1 - A[1][1]) - A[0][1] * A[1][0]
    inv = [[(1 - A[1][1]) / det, A[0][1] / det], [A[1][0] / det, (1 - A[0][0]) / det]]
    assert all(x >= 0 for r in inv for x in r)
    # the start: P0 steady state, machine vs exact
    ts0_m = Fr(T.P0 / T.H)
    tc0_m = Fr(T.P0 / T.H + T.P0 / T.K)
    ts0_x, tc0_x = P0 / H, P0 / H + P0 / K
    e0 = max(abs(ts0_m - ts0_x), abs(tc0_m - tc0_x))
    if u != Fr(1, 2 ** 53):                                  # faithful binary64: the start's two operations too
        e0 = max(e0, 2 * u * (ts0_x + tc0_x))
    Ec = e0 + inv[0][0] * Rc + inv[0][1] * Rs
    Es = e0 + inv[1][0] * Rc + inv[1][1] * Rs
    assert max(Ec, Es) <= slack                              # the induction hypothesis holds
    # z = fl(y - ts): on an admissible record zs_exact is in [LO - DELTA, HI + DELTA], so |y - ts_C| <= 27.3 + Es;
    # zs = fl(z - 25) is exact by Sterbenz (z in [12.5, 50]).
    zmax = Fr(T.TA_HI) + Fr(T.DELTA) + Es
    eps = Es + u * zmax + TINY
    return {"u": float(u), "R_tc": float(Rc), "R_ts": float(Rs), "inv_I_minus_A": [[float(x) for x in r] for r in inv],
            "e0": float(e0), "E_tc": float(Ec), "E_ts": float(Es), "z_rounding": float(u * zmax), "eps": float(eps),
            "eps_upper_float": math.nextafter(float(eps), math.inf)}


def measured(seeds=range(430000, 430030)):
    """|S_float - S_exact| (ts) on the DEV commands, 80-digit decimals; and the largest |S| seen."""
    worst, n = 0.0, 0
    with localcontext() as ctx:
        ctx.prec = 80
        cc, cs, k, h = (D(x) for x in (T.CC, T.CS, T.K, T.H))
        for arm in ("E0", "E1"):
            for seed in (seeds if arm == "E1" else [seeds[0]]):
                P = C.S.command(seed, arm)
                Sf = T.known_part(P)
                ts, tc = D(T.P0) / h, D(T.P0) / h + D(T.P0) / k
                for kk, p in enumerate(P):
                    worst = max(worst, abs(float(D(Sf[kk]) - ts)))
                    dp = D(p)
                    tc, ts = tc + (dp - k * (tc - ts)) / cc, ts + (k * (tc - ts) - h * ts) / cs
                n += 1
    return {"command_sequences": n, "max_abs_ts_error_C": worst}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    hs = headers()
    ub = exact_sup()
    rep = {"frozen_sha256": hashlib.sha256(FROZEN.read_bytes()).hexdigest(), "headers": {}}
    ok = True
    for real, h in hs.items():
        k2 = pads(h)
        k3, k4, k5 = clamps_rate_start(h, ub)
        r = {"K1_header_equal": h["K1_header_equal"], "K2_pads": k2, "K3_clamps": k3, "K4_rate_pads": k4,
             "K5_start": k5}
        r["holds"] = {"K1": h["K1_header_equal"], "K2": k2["entries_not_covered"] == 0 and k2["negative_lambdas"] == 0,
                      "K3": not k3["caps_not_proved"], "K4": not k4["rate_pads_too_small"],
                      "K5": not k5["start_supports_too_small"]}
        ok &= all(r["holds"].values())
        rep["headers"][real] = r
    k6 = data_bound(Fr(1, 2 ** 53))
    rep["K6_data"] = k6
    rep["K6_holds"] = k6["eps"] < C.ETA
    rep["faithful_binary64"] = data_bound(Fr(1, 2 ** 52))
    rep["measured"] = measured()
    rep["verdict"] = "CLOSED" if ok and rep["K6_holds"] else "OPEN"
    txt = json.dumps(rep, indent=1, default=str)
    print(txt)
    if a.out:
        a.out.write_text(txt + "\n")


if __name__ == "__main__":
    main()
