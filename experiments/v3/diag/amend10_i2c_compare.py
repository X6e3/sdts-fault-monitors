"""DIAG-3 amendment 10, I2c (fourth addendum, run at the fifth addendum's commit): compare two r4.json files of
amend10_r4.py. The record is compared in every field except seconds, step_ms and fold_step_ms (as I1 and I2a), and
the audit, the implied log, the key and U4 in every field. Written after the run; it only compares.
usage: python -B amend10_i2c_compare.py REF/r4.json NEW/r4.json
"""
import json
import sys
from pathlib import Path

WALL = {"seconds", "step_ms", "fold_step_ms"}


def diff(a, b, path=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}: missing on one side")
            else:
                out += diff(a[k], b[k], f"{path}/{k}")
        return out
    return [] if a == b else [f"{path}: {str(a)[:60]} != {str(b)[:60]}"]


ref, new = (json.loads(Path(p).read_text()) for p in sys.argv[1:3])
rep = {"record": diff({k: v for k, v in ref["record"].items() if k not in WALL},
                      {k: v for k, v in new["record"].items() if k not in WALL}),
       "audit": diff(ref["audit"], new["audit"]),
       "implied_log": diff({"x": ref["implied_log"]}, {"x": new["implied_log"]}),
       "key_and_U4": diff({k: ref[k] for k in ("key", "U4", "u4")}, {k: new[k] for k in ("key", "U4", "u4")}),
       "ref_meta": ref["meta"], "new_meta": new["meta"]}
rep["I2c"] = not (rep["record"] or rep["audit"] or rep["implied_log"] or rep["key_and_U4"])
print(json.dumps(rep, indent=1))
