"""Freeze 1's validated candidate, the Python template state (template_state.TemplateMachine with frozen/cyl16p.json),
against the exact recurrence: the same question as check_c_state.py asks of the C state (MCU-NOTES 2g), in exact
rational arithmetic.

The Python support of a group is  min_e (lam_e . h + GAMMA4 lsum_e max|h| + res_e cap(h))  rounded up, where res_e
is the stored residual (built against the float matrix M, with an 8 eps allowance for its own float evaluation),
cap(h) = max |h| over the six axis directions, and the dot product is numpy's (3 products, 2 sums). The prediction
adds rho_pad = fl(RHO_A |d_3|) and then 2 eps |out| and one ulp outward.

Criteria (fixed before the first run of this script):
  P1 the frozen file is the manifest's (sha256 7f9cc870...).
  P2 residuals: for every entry e of every group, the stored res_e >= the exact |g_true - sum_j lam_e,j d_j|_1,
     g_true = MX^T d_i (prediction groups) or +-e2 (as-range groups).
  P3 clamps: every cap_inv_i (with the boxes for the axis directions) >= the exact reachable supremum (as K3).
  P4 rate pads: for every direction, fl(RHO_A |d_3|) >= RHO_A |d_3| exactly (the Python template does not round it
     up; a shortfall is reported with its size).
  P5 start: every h0_i >= 2 |sum d_i| (as K5).
  P5' (only if P5 fails) the first step: for every entry using a short direction, the slack the Python support has
     beyond the exact need, (GAMMA4 - gamma3) lsum max|h0| + (res_e - exact residual) cap(h0), covers
     sum_j lam_e,j shortfall_j.
Verdict: CLOSED if P1-P4 hold and P5 or P5' holds; then the Python template is sound against the exact recurrence
for |v| <= delta - eps with check_c_state.py's eps (K6: same S recursion, same z). Otherwise OPEN.
usage: python -B check_py_template.py [--out FILE.json]
"""
import argparse
import hashlib
import json
import math
import sys
from fractions import Fraction as Fr
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import check_c_state as K  # noqa: E402

C, V, T = K.C, K.V, K.T
EPS = Fr(2) ** -52
U = Fr(2) ** -53


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    raw = K.FROZEN.read_bytes()
    rep = {"P1_sha256": hashlib.sha256(raw).hexdigest()}
    manifest = json.loads((HERE.parent / "frozen" / "MANIFEST.json").read_text())
    want = next((v for k, v in manifest["files"].items() if k.endswith("frozen/cyl16p.json")), None)
    rep["P1"] = want == rep["P1_sha256"]
    tp = V.load_frozen(K.FROZEN)
    Dq = [[Fr(float(x)) for x in d] for d in tp.D]
    MX = C.MX
    targets = [[sum(MX[k][j] * d[k] for k in range(3)) for j in range(3)] for d in Dq]
    groups = list(tp.pred) + list(tp.supp_as)
    targets += [[Fr(0), Fr(1), Fr(0)], [Fr(0), Fr(-1), Fr(0)]]
    worst, bad, exact_res = None, [], []
    for g, (bases, tgt) in enumerate(zip(groups, targets)):
        idx, lam, lsum, res = bases
        er = []
        for e in range(len(idx)):
            l = [Fr(float(x)) for x in lam[e]]
            r = sum(abs(tgt[c] - sum(l[j] * Dq[idx[e][j]][c] for j in range(3))) for c in range(3))
            er.append(r)
            sl = Fr(float(res[e])) - r
            if worst is None or sl < worst[0]:
                worst = (sl, g, e)
            if sl < 0:
                bad.append([g, e, float(r), float(res[e])])
        exact_res.append(er)
    rep["P2"] = not bad
    rep["P2_detail"] = {"entries_short": len(bad), "first": bad[:10], "smallest_slack": float(worst[0]),
                        "at_group_entry": worst[1:]}
    ub = K.exact_sup()
    axis = set(tp.ip) | set(tp.im)
    caps = list(tp.clamp(np.full(tp.n, np.inf)))
    short3 = [i for i in range(tp.n) if Fr(float(caps[i])) < (min(ub[i], Fr(2)) if i in axis else ub[i])]
    rep["P3"] = not short3
    rep["P3_detail"] = {"caps_not_proved": short3}
    rho = Fr(T.RHO_A)
    p4 = []
    for i, d in enumerate(Dq):
        need = rho * abs(d[2])
        have = Fr(float(tp.rho_pad[i]))
        if have < need:
            p4.append([i, float(need - have)])
    rep["P4"] = not p4
    rep["P4_detail"] = {"short_directions": p4}
    h0 = [Fr(float(x)) for x in tp.clamp(tp.h0)]
    short = {i: 2 * abs(sum(d)) - h0[i] for i, d in enumerate(Dq) if h0[i] < 2 * abs(sum(d))}
    rep["P5"] = not short
    rep["P5_detail"] = {"short_directions": {i: float(v) for i, v in short.items()}}
    if short:
        hmax0 = max(abs(x) for x in h0)
        cap0 = max(max(abs(h0[tp.ip[c]]), abs(h0[tp.im[c]])) for c in range(3))
        g3 = 3 * U / (1 - 3 * U)
        gam4 = Fr(float(V.GAMMA4))
        bad5, touched, worst5 = [], 0, None
        for g, bases in enumerate(groups):
            idx, lam, lsum, res = bases
            for e in range(len(idx)):
                l = [Fr(float(x)) for x in lam[e]]
                extra = sum(l[j] * short.get(int(idx[e][j]), 0) for j in range(3))
                if extra == 0:
                    continue
                touched += 1
                slack = (gam4 - g3) * sum(l) * hmax0 + (Fr(float(res[e])) - exact_res[g][e]) * cap0
                if worst5 is None or slack - extra < worst5:
                    worst5 = slack - extra
                if slack < extra:
                    bad5.append([g, e, float(extra), float(slack)])
        rep["P5prime"] = not bad5
        rep["P5prime_detail"] = {"entries_using_short": touched, "not_covered": bad5[:10],
                                 "smallest_margin": float(worst5) if worst5 is not None else None}
    eps = K.data_bound(Fr(1, 2 ** 53))["eps"]
    rep["eps_data"] = eps
    ok = rep["P1"] and rep["P2"] and rep["P3"] and rep["P4"] and (rep["P5"] or rep.get("P5prime", False))
    rep["verdict"] = "CLOSED" if ok else "OPEN"
    txt = json.dumps(rep, indent=1, default=str)
    print(txt)
    if a.out:
        a.out.write_text(txt + "\n")


if __name__ == "__main__":
    main()
