"""Compare two run_final.py outputs of the same seeds made on different machines (platform check before FINAL).

Decisions must be identical: oracle verdicts (full and ablations), t* and its status, P4, P7, P6 labels, machine
outputs, baseline outcomes and twin verdicts. LP bound values (d_lo, d_up) and offset intervals may differ in
the last digits across platforms; their largest differences are reported, not required to be zero.
usage: python -I compare_rehearsals.py RUN_A RUN_B
"""
import json
import sys
from pathlib import Path

a_dir, b_dir = Path(sys.argv[1]), Path(sys.argv[2])
FLOAT_KEYS = {"d_lo", "d_up", "interval", "outer_interval", "seconds", "A_min", "A_max", "offset_box_bound",
              "sensor_error"}


def rows(d, name):
    return [json.loads(l) for l in (d / name).read_text().splitlines() if l.strip()]


def split(x, path=""):
    """Yield (path, value, is_float_field) leaves."""
    if isinstance(x, dict):
        for k, v in x.items():
            if k in FLOAT_KEYS:
                yield f"{path}/{k}", v, True
            else:
                yield from split(v, f"{path}/{k}")
    elif isinstance(x, list) and x and isinstance(x[0], dict):
        for i, v in enumerate(x):
            yield from split(v, f"{path}[{i}]")
    else:
        yield path, x, False


def flat_floats(v):
    if v is None:
        return []
    if isinstance(v, dict):
        return [y for k in sorted(v) for y in flat_floats(v[k])]
    if isinstance(v, list):
        return [y for e in v for y in flat_floats(e)]
    return [v]


mismatch, worst, compared = [], {}, 0
for name, key in (("runs.jsonl", lambda r: (r["seed"], r["cell"], r["arm"])),
                  ("twins.jsonl", lambda r: (r["seed"], r["case"], r["arm"], r["draw"]))):
    A = {key(r): r for r in rows(a_dir, name)}
    B = {key(r): r for r in rows(b_dir, name)}
    if A.keys() != B.keys():
        mismatch.append((name, "different row sets", len(A), len(B)))
    for k in A.keys() & B.keys():
        la, lb = dict((p, (v, f)) for p, v, f in split(A[k])), dict((p, (v, f)) for p, v, f in split(B[k]))
        for p in la.keys() | lb.keys():
            va, fa = la.get(p, (None, False))
            vb, _ = lb.get(p, (None, False))
            compared += 1
            if fa:
                if p.endswith("/seconds"):
                    continue
                xa, xb = flat_floats(va), flat_floats(vb)
                if len(xa) != len(xb) or any((x is None) != (y is None) for x, y in zip(xa, xb)):
                    mismatch.append((name, k, p, va, vb))
                    continue
                d = max((abs(x - y) for x, y in zip(xa, xb) if x is not None), default=0.0)
                field = p.rsplit("/", 1)[-1]
                worst[field] = max(worst.get(field, 0.0), d)
            elif va != vb:
                mismatch.append((name, k, p, va, vb))

print("leaves compared:", compared)
print("largest float differences (reported, not required to be zero):", json.dumps(worst, indent=1))
print("decision mismatches:", len(mismatch))
for m in mismatch[:30]:
    print("  ", m)
