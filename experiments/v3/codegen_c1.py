"""C1-PLAN.md: freeze 1's C tables with every start support raised to at least the exact start-segment support.

The tables come from frozen/cyl16p.json through the unchanged codegen_c.py. Only H0 changes:
H0_i = max(frozen H0_i, 2 |sum_c d_ic| rounded up), with the sum taken exactly over the stored coordinates; it is
then clamped and rounded up to the header's precision as before.
usage: python codegen_c1.py --real double|float --out FILE
"""
import argparse
import hashlib
import math
import sys
from fractions import Fraction as Fr
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import codegen_c as CG  # noqa: E402

V = CG.V
FROZEN = HERE / "frozen" / "cyl16p.json"


def up(q):
    """the exact rational q rounded up to binary64"""
    f = float(q)
    if Fr(f) < q:
        f = math.nextafter(f, math.inf)
    return f


def start_support(d):
    """support of the start segment {t (1, 1, 1) : |t| <= 2} in direction d, exactly: 2 |sum d|"""
    return 2 * abs(sum(Fr(float(x)) for x in d))


def c1_tables(real):
    tp = V.load_frozen(FROZEN)
    tp, hmax, idx, lam, starts, pads = CG.build(None, 0, 0, real, template=tp)
    tp.h0 = np.maximum(tp.h0, np.array([up(start_support(d)) for d in tp.D]))
    sha = hashlib.sha256(FROZEN.read_bytes()).hexdigest()
    label = f"frozen {FROZEN.name} sha256 {sha} {real}; c1: start supports >= the exact start segment's, C1-PLAN.md"
    return tp, hmax, idx, lam, starts, pads, label


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--real", choices=("float", "double"), required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    tp, hmax, idx, lam, starts, pads, label = c1_tables(a.real)
    a.out.write_text(CG.emit(tp, hmax, idx, lam, starts, pads, a.real, label))


if __name__ == "__main__":
    main()
