"""WIDEBOX-PLAN.md: the vertex check of Appendix A.5, for the frozen box and the wider ones.

The clamp set C = {x : D x <= c} of cyl16p (c: the reachable-set clamps cap_inv, with the box on +-e1, +-e2, +-e3) must
be invariant under one step of the exact recurrence x' = M x + e3 w, |w| <= rho, T_A' = T_A + w in the box. For each
direction d_i the step's largest d_i . x' is affine in x on each piece of C cut by T_A = hi - rho and T_A = lo + rho,
so the vertices of C and of the two cuts suffice. Everything is checked in rational arithmetic, with the float
directions, clamps and parameters read exactly. Also checked: the two ends of the start segment {(T, T, T)} lie in C,
and for the frozen box, the clamps rebuilt by ambient_study.cyl16p equal the frozen tables'.

  python -B widebox_vertices.py OUT.json
"""
import itertools
import json
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import ambient_study as A  # noqa: E402

C, V, T = A.C, A.V, A.T
BOXES = {"23-27": (23.0, 27.0), "22-28": (22.0, 28.0), "21-29": (21.0, 29.0)}


def clamps(tp, box):
    """the clamp vector of tp at `box`, as the base update applies it (Template.clamp)"""
    old = (V.LO, V.HI)
    V.LO, V.HI = box[0] - V.SHIFT, box[1] - V.SHIFT
    try:
        return tp.clamp(np.full(tp.n, np.inf))
    finally:
        V.LO, V.HI = old


def solve3(rows, rhs):
    """the exact solution of a 3 x 3 rational system, None if it is singular"""
    (a, b, c), (d, e, f), (g, h, i) = rows
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if det == 0:
        return None
    p, q, r = rhs
    x = (p * (e * i - f * h) - b * (q * i - f * r) + c * (q * h - e * r)) / det
    y = (a * (q * i - f * r) - p * (d * i - f * g) + c * (d * r - q * g)) / det
    z = (a * (e * r - q * h) - b * (d * r - q * g) + p * (d * h - e * g)) / det
    return (x, y, z)


def dot(u, v):
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def check(tp, box):
    lo, hi = Fraction(box[0] - V.SHIFT), Fraction(box[1] - V.SHIFT)
    assert Fraction(box[0]) - Fraction(V.SHIFT) == lo and Fraction(box[1]) - Fraction(V.SHIFT) == hi
    rho = Fraction(T.RHO_A)
    Dq = [tuple(Fraction(float(x)) for x in d) for d in tp.D]
    cf = clamps(tp, box)
    assert np.all(np.isfinite(cf))
    cq = [Fraction(float(x)) for x in cf]
    n = len(Dq)

    def inside(x):
        return all(dot(Dq[i], x) <= cq[i] for i in range(n))

    planes = list(zip(Dq, cq))
    verts = set()
    for (a, b, c) in itertools.combinations(range(n), 3):
        x = solve3([planes[a][0], planes[b][0], planes[c][0]], [planes[a][1], planes[b][1], planes[c][1]])
        if x is not None and inside(x):
            verts.add(x)
    e3 = (Fraction(0), Fraction(0), Fraction(1))
    cuts = set()
    for cut in (hi - rho, lo + rho):
        for (a, b) in itertools.combinations(range(n), 2):
            x = solve3([e3, planes[a][0], planes[b][0]], [cut, planes[a][1], planes[b][1]])
            if x is not None and inside(x) and x not in verts:
                cuts.add(x)
    MX = C.exact_matrix()
    worst, over, steps = None, 0, 0
    for x in sorted(verts | cuts):
        assert lo <= x[2] <= hi
        w_hi, w_lo = min(rho, hi - x[2]), max(-rho, lo - x[2])
        assert w_lo <= w_hi
        mx = tuple(dot(MX[k], x) for k in range(3))
        for w in (w_lo, w_hi):
            y = (mx[0], mx[1], mx[2] + w)
            for i in range(n):
                s = dot(Dq[i], y) - cq[i]
                steps += 1
                over += s > 0
                worst = s if worst is None or s > worst else worst
    start = [(lo, lo, lo), (hi, hi, hi)]
    return {"box": list(box), "directions": n, "vertices_C": len(verts), "vertices_cuts": len(cuts),
            "checked": steps, "steps_above_a_clamp": over, "largest_step_minus_clamp": float(worst),
            "start_segment_ends_in_C": all(inside(x) for x in start),
            "box_on_axes": [float(cf[tp.ip[k]]) for k in range(3)] + [float(-cf[tp.im[k]]) for k in range(3)]}


def main():
    out = Path(sys.argv[1])
    frozen = A.cyl16p()
    rebuilt = A.cyl16p(BOXES["23-27"])
    rep = {"rebuilt_equals_frozen": {"cap_inv": bool(np.array_equal(rebuilt.cap_inv, frozen.cap_inv)),
                                     "h0": bool(np.array_equal(rebuilt.h0, frozen.h0))}, "boxes": {}}
    for name, box in BOXES.items():
        tp = frozen if name == "23-27" else A.cyl16p(box)
        rep["boxes"][name] = check(tp, box)
        print(name, json.dumps(rep["boxes"][name]), flush=True)
    out.write_text(json.dumps(rep, indent=1) + "\n")
    print(json.dumps(rep["rebuilt_equals_frozen"]))


if __name__ == "__main__":
    main()
