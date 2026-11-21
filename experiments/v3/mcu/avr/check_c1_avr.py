"""C1-PLAN.md addendum, checks U1 and U2 for the Uno's c1 port.

U1: avr_state_c1.c differs from avr_state.c only in the ETA define and the two slab lines.
U2: BUILD_DIR/tables_progmem.h is make_progmem.py's copy of c1/tables_cyl16p1_float.h (its check passes, and its
    first line names that file and its sha256).
usage: python -B check_c1_avr.py BUILD_DIR [--out FILE.json]
"""
import argparse
import difflib
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
V3 = HERE.parent.parent
sys.path.insert(0, str(HERE))
import make_progmem as MP  # noqa: E402


def u1():
    a = (HERE / "avr_state.c").read_text().splitlines()
    b = (HERE / "avr_state_c1.c").read_text().splitlines()
    d = [l for l in difflib.unified_diff(a, b, lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    removed = [l[1:].strip() for l in d if l.startswith("-")]
    added = [l[1:].strip() for l in d if l.startswith("+")]
    want_removed = ["v3_real lo = DOWN((v3_real)down_d(down_d(zs) - DELTA));",
                    "v3_real hi = UP((v3_real)up_d(up_d(zs) + DELTA));"]
    want_added = [l for l in added if l.startswith("#define ETA 1e-9")][:1] + \
                 [w.replace("- DELTA)", "- (DELTA + ETA))").replace("+ DELTA)", "+ (DELTA + ETA))") for w in want_removed]
    return {"removed": removed, "added": added,
            "holds": removed == want_removed and added == want_added and len(want_added) == 3}


def u2(build):
    src = V3 / "c1" / "tables_cyl16p1_float.h"
    raw = src.read_bytes()
    out = (build / "tables_progmem.h").read_text()
    try:
        MP.check(raw.decode(), out)
        same = True
    except SystemExit:
        same = False
    sha = hashlib.sha256(raw).hexdigest()
    first = out.split("\n", 1)[0]
    return {"source_sha256": sha, "first_line": first, "holds": same and src.name in first and sha in first}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("build", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    rep = {"U1": u1(), "U2": u2(a.build)}
    rep["U1_U2_hold"] = rep["U1"]["holds"] and rep["U2"]["holds"]
    txt = json.dumps(rep, indent=1)
    print(txt)
    if a.out:
        a.out.write_text(txt + "\n")


if __name__ == "__main__":
    main()
