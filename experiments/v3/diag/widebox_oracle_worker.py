"""WIDEBOX-PLAN.md: the oracle's solver child, at the assumed box of the parent.

thermal_oracle solves each LP attempt in a fresh interpreter (`thermal_oracle.py RESULT`, its `_worker`), which
imports thermal.py and so builds the LP with the frozen box [23, 27]. widebox.py points `thermal_oracle.HERE` at this
file. It sets the box from WIDEBOX_TA ("lo,hi", set by widebox.box()), writes it to box.json next to the result, and
runs the same `_worker`. widebox.py checks the box.json of every attempt.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "experiments/oracle"), str(ROOT / "experiments/generators")]
import thermal as T  # noqa: E402
import thermal_oracle as O  # noqa: E402

if __name__ == "__main__":
    lo, hi = (float(x) for x in os.environ["WIDEBOX_TA"].split(","))
    assert O.T is T
    T.TA_LO, T.TA_HI = lo, hi
    result = Path(sys.argv[1])
    (result.parent / "box.json").write_text(json.dumps([lo, hi]) + "\n")
    O._worker(str(result))
