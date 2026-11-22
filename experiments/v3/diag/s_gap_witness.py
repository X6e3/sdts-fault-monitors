"""A healthy record on which freeze 1's Python template (TS, cyl16p) flags (RECORD-2026-11-22-review2.md).

Construction (from the second blind review of 2026-11-22): the ambient is held at 27 °C (the top of the box), the
plant starts at the steady state of P0 and the command is 42 W for 600 samples. The true surface temperature is
computed in exact rational arithmetic from the simulator's parameters read as rationals, and each measurement is the
largest binary64 number not above the true temperature plus delta, so |v| <= delta holds exactly at every sample
(asserted). The template's command part S is computed in binary64 with no pad for its rounding; once its error
exceeds the noise headroom the slab misses the true state and the template flags a healthy record.

  python -B s_gap_witness.py OUT_DIR       writes OUT_DIR/witness-42W.txt ("y P" per line, the C harness's input)
"""
import math
import sys
from fractions import Fraction as Q
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import widebox as wb  # noqa: E402  (sets the frozen box [23, 27] at import)

T, V = wb.T, wb.V


def main(out):
    tp = wb.template("23-27")                     # freeze 1's cyl16p, the validated template
    m = V.TemplateMachine(tp)
    H, K, CC, CS, DT, P0, DELTA = (Q(x) for x in (T.H, T.K, T.CC, T.CS, T.DT, T.P0, T.DELTA))
    ta = Q(27)
    ts = ta + P0 / H                              # steady state of P0 at ambient 27
    tc = ts + P0 / K
    first, lines = None, []
    for k in range(600):
        p = 42.0
        ceiling = ts + DELTA
        y = float(ceiling)
        if Q(y) > ceiling:
            y = math.nextafter(y, -math.inf)
        v = Q(y) - ts
        assert abs(v) <= DELTA, (k, v)
        s_err = Q(m._ts) - (ts - ta)              # the template's S (binary64) minus the exact command part
        lines.append(f"{y!r} {p!r}\n")
        if m.observe(y, p) and first is None:
            first = k
            print(f"first alarm at sample {k}: y = {y!r}, noise headroom delta - v = {float(DELTA - v):.3e} degC, "
                  f"S error = {float(s_err):.3e} degC")
        tc, ts = tc + DT * (Q(p) - K * (tc - ts)) / CC, ts + DT * (K * (tc - ts) - H * (ts - ta)) / CS
    if first is None:
        print("no alarm in 600 samples")
    out.mkdir(parents=True, exist_ok=True)
    (out / "witness-42W.txt").write_text("".join(lines))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
