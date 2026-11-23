"""IM (experiments/machine/thermal_machine.py, the implemented interval monitor) on the S-gap witness record
(results/v3/review2/witness-42W.txt, written by s_gap_witness.py; RECORD-2026-11-23-review3-checks.md).

IM pads the rounding of z and of z +- delta by one ulp each but computes the command part S in binary64 with no pad,
like freeze 1's Python template. On this healthy record (noise inside the bound at every sample) it flags.

  python -B im_s_gap.py        prints the witness sha256, the box, and the first sample at which IM flags
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments" / "machine"))
import thermal_machine as TM  # noqa: E402

T = TM.T


def main():
    w = ROOT / "results" / "v3" / "review2" / "witness-42W.txt"
    print("witness sha256", hashlib.sha256(w.read_bytes()).hexdigest())
    print("box", T.TA_LO, T.TA_HI, "DELTA", T.DELTA)
    m = TM.ThermalMachine()
    for k, line in enumerate(w.read_text().splitlines()):
        y, p = map(float, line.split())
        if m.observe(y, p):
            print("IM flags at sample", k, "feasible", m._feasible)
            return
    print("IM does not flag")


if __name__ == "__main__":
    main()
