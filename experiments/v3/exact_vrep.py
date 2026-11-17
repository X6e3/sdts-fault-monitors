"""Diagnostic (not an MCU method, not certified): the exact information state X_k by vertex enumeration.

X_{k+1} = (M X_k (+) e3 [-RHO, RHO]) cap box cap slab, with Qhull for hulls and edge clipping for intersections.
Purpose: (1) check Theorem 1 numerically (first empty k should equal the oracle's certified t*), (2) measure
how many vertices the exact state needs over time. Floating point, no outward rounding: a diagnostic only.
usage: python -B exact_vrep.py SEED CELL ARM AMBIENT
"""
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import ConvexHull, QhullError

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "generators")]
import dev_scenarios as S  # noqa: E402
import template_state as V  # noqa: E402

T = V.T


def hull_vertices(P):
    P = np.unique(np.round(P, 13), axis=0)
    if len(P) <= 3:
        return P, None
    try:
        h = ConvexHull(P)
        return P[h.vertices], h
    except QhullError:
        h = ConvexHull(P, qhull_options="QJ")       # degenerate (early, flat) sets only
        return P[h.vertices], h


def clip(P, a, b):
    """Vertices of conv(P) cap {a.x <= b}."""
    vals = P @ a - b
    if np.all(vals <= 1e-12):
        return P
    if np.all(vals > 1e-12):
        return np.empty((0, 3))
    pts = [P[vals <= 1e-12]]
    V_, h = hull_vertices(P)
    if h is None:
        edges = [(i, j) for i in range(len(P)) for j in range(i + 1, len(P))]
        Q = P
    else:
        Q = h.points
        edges = {tuple(sorted((s[i], s[j]))) for s in h.simplices for i in range(3) for j in range(i + 1, 3)}
    vq = Q @ a - b
    for i, j in edges:
        if (vq[i] > 0) != (vq[j] > 0):
            t = vq[i] / (vq[i] - vq[j])
            pts.append((Q[i] + t * (Q[j] - Q[i]))[None, :])
    return np.vstack(pts)


def run(seed, cell_name, arm, law):
    r = S.run(seed, next(c for c in T.CELLS if c.name == cell_name), arm, law, "uniform")
    zs = np.asarray(r["z"]) - V.SHIFT
    P = np.array([[V.LO] * 3, [V.HI] * 3])                 # the initial segment
    sizes = []
    for k in range(len(zs)):
        for a, b in ((V.E[1], zs[k] + T.DELTA), (-V.E[1], -(zs[k] - T.DELTA)), (V.E[2], V.HI), (-V.E[2], -V.LO)):
            P = clip(P, a, b)
            if len(P) == 0:
                return k, sizes
        P, _ = hull_vertices(P)
        sizes.append(len(P))
        P = np.vstack([P @ V.M.T + np.array([0, 0, s * T.RHO_A]) for s in (1, -1)])
        P, _ = hull_vertices(P)
    return None, sizes


if __name__ == "__main__":
    seed, cell, arm, law = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
    k, sizes = run(seed, cell, arm, law)
    s = np.array(sizes)
    print(f"{seed} {cell} {arm} {law}: first empty k = {k}; vertices: median {np.median(s):.0f}, p90 {np.percentile(s, 90):.0f}, "
          f"max {s.max()} (over {len(s)} samples)")
