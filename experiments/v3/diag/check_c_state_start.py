"""Follow-up of check_c_state.py, written after its K5 failed (2026-11-21): does the first step absorb the start gap?

K5 found that two start supports of the frozen C state are below the start segment's support: directions 14 and
15 (= -d14), whose stored coordinates sum to +-5.55e-17 instead of 0, have H0 = the smallest subnormal, while the
segment {t (1, 1, 1) : |t| <= 2} needs 2 |sum d| = 1.11e-16. So P_0 = {D s <= H0} does not contain X_0.

P_0' = {D s <= H0 + dh}, dh_j = max(0, 2 |sum d_j| - H0_j), does contain X_0 (and the box, since the axis
supports are unchanged). Every support the C state computes from H0 at k = 0 (the as-range test and the 42
predictions) is an upper bound on the same support of P_0' if, for every entry e of every group g,
    gamma3 * sum_j lam_e,j * HMAX + |g_true - sum_j lam_e,j d_idx(e,j)|_1 * CAP + sum_j lam_e,j dh_idx(e,j) <= PAD_g
(K2's inequality with the shortfall added). Then P_1 contains X_1 and K2-K4 carry the induction from k = 1 on.

Criterion (fixed before the first run of this script): K5' holds for both headers. It is a check written after
K5 failed, and is reported as such.
usage: python -B check_c_state_start.py [--out FILE.json]
"""
import argparse
import json
import sys
from fractions import Fraction as Fr
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_c_state as K  # noqa: E402


def k5prime(h):
    tp = h["tp"]
    Dq = [[Fr(float(x)) for x in d] for d in tp.D]
    dh = [max(Fr(0), 2 * abs(sum(d)) - h["h0"][i]) for i, d in enumerate(Dq)]
    MX = K.C.MX
    targets = [[sum(MX[k][j] * d[k] for k in range(3)) for j in range(3)] for d in Dq]
    targets += [[Fr(0), Fr(1), Fr(0)], [Fr(0), Fr(-1), Fr(0)]]
    u = h["u"]
    g3 = 3 * u / (1 - 3 * u)
    worst, bad, touched = None, [], 0
    for g, tgt in enumerate(targets):
        for e in range(h["starts"][g], h["starts"][g + 1]):
            lam, ix = h["lam"][e], h["idx"][e]
            res = sum(abs(tgt[c] - sum(lam[j] * Dq[ix[j]][c] for j in range(3))) for c in range(3))
            extra = sum(lam[j] * dh[ix[j]] for j in range(3))
            touched += extra > 0
            sl = h["pad"][g] - (g3 * sum(lam) * h["hmax"] + res * h["cap_const"] + extra)
            if extra > 0 and (worst is None or sl / h["pad"][g] < worst[0]):
                worst = (sl / h["pad"][g], g, e, float(extra))
            if sl < 0:
                bad.append([g, e, float(sl)])
    return {"shortfall_directions": {i: float(x) for i, x in enumerate(dh) if x > 0},
            "entries_using_them": touched, "entries_not_covered": len(bad), "not_covered_first": bad[:10],
            "smallest_slack_fraction_of_pad_among_them": float(worst[0]) if worst else None,
            "at_group_entry_extra": worst[1:] if worst else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    hs = K.headers()
    rep = {real: k5prime(h) for real, h in hs.items()}
    rep["K1_headers_equal"] = all(h["K1_header_equal"] for h in hs.values())
    rep["K5prime_holds"] = rep["K1_headers_equal"] and all(rep[r]["entries_not_covered"] == 0 for r in hs)
    txt = json.dumps(rep, indent=1, default=str)
    print(txt)
    if a.out:
        a.out.write_text(txt + "\n")


if __name__ == "__main__":
    main()
